"""Os contratos de fora no doctor: o que o Hefesto assume do mundo do outro, por capacidade.

O censo (``docs/data/contratos-de-fora.csv``) lista cada ponto de contato com o BlueZ, o
PipeWire, o systemd, a Steam, o Proton, o kernel e o COSMIC. Aqui moram as perguntas que o
``doctor`` faz a cada um, e a regra é a do censo: **a capacidade, nunca a versão**, salvo o GE e
o SDL, que mudam o padrão por dentro sem mudar porta (a faixa medida está nas constantes
``GE_*`` e ``SDL_DO_EDGE``). Todas as outras perguntam se a porta existe e responde do jeito
que o Hefesto usa (a interface D-Bus, o JSON do ``pactl``, o nó do kernel, o arquivo da Steam).

Quando uma sonda não converge, a linha do doctor nomeia o CONTRATO que quebrou e o comando
para conferir, em vez de falha calada. Dono que não existe nesta máquina (sem Steam, sem
COSMIC) é ``[INFO]``: o produto é para qualquer computador, e ausência não é defeito.

Só leitura: nenhuma sonda escreve no BlueZ, no servidor de som, na Steam nem no kernel. O
``busctl`` só faz ``tree``; o ``pactl``, só ``info``; o ``wpctl``, só ``status``.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from hefesto_dualsense4unix.integrations import bluez_dbus

ESPERA_S = 3.0

OK = "ok"
QUEBROU = "quebrou"
AUSENTE = "ausente"


@dataclass(frozen=True)
class Falta:
    """A ferramenta não respondeu. ``ausente`` separa as duas causas, que não são a mesma coisa.

    ``ausente=True``: a ferramenta não existe nesta máquina (o dono não está aqui, ``[INFO]``).
    ``ausente=False``: ela existe e não respondeu (o tempo esgotou, a permissão faltou): o
    contrato quebrou, e isso nunca se lê como ausência.
    """

    motivo: str
    ausente: bool = True


Rodar = Callable[[Sequence[str]], "tuple[int, str] | Falta"]


def rodar_de_verdade(argv: Sequence[str]) -> tuple[int, str] | Falta:
    """``(rc, saída)``, ou a ``Falta`` quando a ferramenta não existe (ou não respondeu a tempo)."""
    ambiente = dict(os.environ)
    ambiente["LC_ALL"] = "C"
    try:
        feito = subprocess.run(
            list(argv), capture_output=True, text=True, timeout=ESPERA_S, check=False, env=ambiente
        )
    except FileNotFoundError as erro:
        return Falta(f"{type(erro).__name__}: {erro}")
    except (OSError, subprocess.SubprocessError) as erro:
        return Falta(f"{type(erro).__name__}: {erro}", ausente=False)
    return feito.returncode, feito.stdout


def _sem_resposta(falta: Falta, ferramenta: str) -> Resultado:
    """Ferramenta que não existe é ``[INFO]``; ferramenta que existe e não respondeu quebrou."""
    if falta.ausente:
        return Resultado(AUSENTE, f"sem {ferramenta} nesta máquina")
    return Resultado(QUEBROU, f"o {ferramenta} não respondeu ({falta.motivo})")


@dataclass(frozen=True)
class Ambiente:
    """O que as sondas enxergam do mundo. Cada campo se troca por um dublê nos testes."""

    rodar: Rodar = rodar_de_verdade
    home: Path = field(default_factory=Path.home)
    env: dict[str, str] = field(default_factory=lambda: dict(os.environ))
    raiz: Path = Path("/")

    def caminho(self, absoluto: str) -> Path:
        return self.raiz / absoluto.lstrip("/")


@dataclass(frozen=True)
class Resultado:
    estado: str
    detalhe: str = ""


@dataclass(frozen=True)
class Contrato:
    """Uma promessa do outro lado. ``id`` é o que o censo cita em ``contrato:<id>``."""

    id: str
    dono: str
    promessa: str
    conferir: str
    sonda: Callable[[Ambiente], Resultado]
    #: os alvos de porta interna (ou de pergunta por versão) que a sonda pergunta DE FATO. Uma
    #: linha frágil do censo só cita este contrato se o alvo dela estiver aqui: a sonda da porta
    #: oficial não vê a interna quebrar, e dizer que vê é dar [ OK ] sobre o que mudou.
    cobre: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# As sondas. Cada uma pergunta uma capacidade e devolve o que faltou, com nome.


def _sonda_bluez(amb: Ambiente) -> Resultado:
    # A pergunta é do dono do D-Bus do BlueZ (BLUEZ-UM-DONO-01); aqui só se troca o executor,
    # para a sonda separar a ferramenta ausente da que não respondeu.
    faltas: list[Falta] = []

    def executar(argumentos: Sequence[str]) -> str | None:
        saida = amb.rodar([bluez_dbus.FERRAMENTA, "--system", *argumentos])
        if isinstance(saida, Falta):
            faltas.append(saida)
            return None
        rc, texto = saida
        return texto if rc == 0 else None

    responde = bluez_dbus.pelo_executor(executar).responde()
    if faltas:
        return _sem_resposta(faltas[0], bluez_dbus.FERRAMENTA)
    if responde:
        return Resultado(OK)
    return Resultado(QUEBROU, f"o nome {bluez_dbus.SERVICO} não responde no barramento do sistema")


def _sonda_pactl_json(amb: Ambiente) -> Resultado:
    saida = amb.rodar(["pactl", "--format=json", "info"])
    if isinstance(saida, Falta):
        return _sem_resposta(saida, "pactl")
    rc, texto = saida
    if rc != 0:
        return Resultado(QUEBROU, f"o pactl respondeu rc={rc} ao formato JSON")
    try:
        lido = json.loads(texto)
    except ValueError as erro:
        return Resultado(QUEBROU, f"o pactl não entrega o formato JSON que o Hefesto lê ({erro})")
    if isinstance(lido, dict):
        return Resultado(OK)
    return Resultado(QUEBROU, "o pactl entrega JSON, mas não o objeto que o Hefesto lê")


def _sonda_wpctl(amb: Ambiente) -> Resultado:
    saida = amb.rodar(["wpctl", "status"])
    if isinstance(saida, Falta):
        return _sem_resposta(saida, "wpctl")
    return (
        Resultado(OK) if saida[0] == 0 else Resultado(QUEBROU, "o wpctl não fala com o WirePlumber")
    )


def _sonda_systemd(amb: Ambiente) -> Resultado:
    saida = amb.rodar(["systemctl", "--user", "show-environment"])
    if isinstance(saida, Falta):
        return _sem_resposta(saida, "systemctl")
    return (
        Resultado(OK) if saida[0] == 0 else Resultado(QUEBROU, "o systemd de usuário não responde")
    )


def _sonda_nos_do_kernel(amb: Ambiente) -> Resultado:
    faltam = [
        nome
        for nome, caminho in (
            ("/dev/uinput", "/dev/uinput"),
            ("/dev/uhid", "/dev/uhid"),
            ("/sys/class/hidraw", "/sys/class/hidraw"),
            ("/dev/input", "/dev/input"),
        )
        if not amb.caminho(caminho).exists()
    ]
    if not faltam:
        return Resultado(OK)
    return Resultado(QUEBROU, "faltam " + ", ".join(faltam))


def _sonda_driver_sony(amb: Ambiente) -> Resultado:
    """O kernel TEM o driver: ligado ao barramento agora, ou disponível para carregar.

    O ``hid_playstation`` é módulo que o kernel carrega quando o primeiro controle Sony chega;
    numa máquina sem controle desde o boot a pasta do driver não existe, e isso não é defeito.
    A pergunta à porta oficial (o ``modinfo`` do kmod) é se o kernel em uso sabe carregá-lo.
    """
    if amb.caminho("/sys/bus/hid/drivers/playstation").is_dir():
        return Resultado(OK)
    saida = amb.rodar(["modinfo", "-F", "filename", "hid_playstation"])
    if isinstance(saida, Falta):
        if saida.ausente:
            return Resultado(
                AUSENTE, "sem controle Sony ligado desde o boot e sem modinfo para perguntar"
            )
        return _sem_resposta(saida, "modinfo")
    if saida[0] == 0 and saida[1].strip():
        return Resultado(OK)
    return Resultado(QUEBROU, "o kernel em uso não tem o driver playstation (hid_playstation)")


def _raizes_da_steam(amb: Ambiente) -> list[Path]:
    """Cada raiz uma vez só: ``~/.steam/steam`` costuma ser link de ``~/.local/share/Steam``."""
    raizes: list[Path] = []
    for r in (amb.home / ".steam" / "steam", amb.home / ".local" / "share" / "Steam"):
        if r.is_dir() and all(r.resolve() != vista.resolve() for vista in raizes):
            raizes.append(r)
    return raizes


def _pasta_xdg(amb: Ambiente, variavel: str, padrao: str) -> Path:
    """A pasta XDG do lar que a sonda enxerga: a variável do ambiente dele, ou o padrão no lar."""
    valor = amb.env.get(variavel, "").strip()
    return Path(valor) if valor else amb.home / padrao


def _perderam_o_wrapper(amb: Ambiente, conf: Path) -> list[str]:
    """Os jogos que o Hefesto JÁ viu com o wrapper e que a Steam devolveu sem ele.

    A pergunta é a da sentinela (``censo_do_wrapper``, a ``regressao`` dela), e não uma segunda
    cópia da regra: a Steam é a dona do arquivo e já apagou o ``hefesto-launch`` de um jogo sem
    aviso (17/09/2026). Jogo recusado, arquivo da Steam Flatpak/Snap (onde o wrapper não se
    escreve) e linha com o par estendido ficam de fora como lá; leitura sem nenhum app (a Steam no
    meio da regravação) não conclui nada. Só leitura: o registro não é anotado daqui.
    """
    from .sentinela_do_wrapper import REGISTRO_BASENAME, censo_do_wrapper
    from .steam_launch_options import ler_jogos_sem_wrapper, sem_wrapper_path

    config = _pasta_xdg(amb, "XDG_CONFIG_HOME", ".config")
    estado = _pasta_xdg(amb, "XDG_STATE_HOME", ".local/state")
    censo = censo_do_wrapper(
        home=amb.home,
        vdfs=[conf],
        registro=estado / "hefesto-dualsense4unix" / REGISTRO_BASENAME,
        recusados=ler_jogos_sem_wrapper(sem_wrapper_path(config)),
        anotar=False,
    )
    return sorted(j.appid for j in censo.regressoes)


def _opcoes_desfeitas(amb: Ambiente, confs: list[Path]) -> list[str]:
    """As opções por jogo da tabela do Hefesto que a Steam não guarda onde a lê.

    A pergunta é a do ``conferir`` do dono da tabela (``opcoes_por_jogo``), e não uma segunda
    cópia da regra: o ``aplicar`` já disse «aplicado» sobre uma linha que a Steam não leu
    (06/10/2026) e já foi desfeito pela própria Steam sem aviso. Só leitura; sem tabela, vazio.
    """
    from .opcoes_por_jogo import AVISO_DO_DEFEITO, conferir

    config = _pasta_xdg(amb, "XDG_CONFIG_HOME", ".config")
    estado = _pasta_xdg(amb, "XDG_STATE_HOME", ".local/state")
    achados = conferir(
        home=amb.home, vdfs=confs, config_home=config, estado_home=estado)["defeitos"]
    return sorted({
        f"{d['appid'] or 'conta'} ({AVISO_DO_DEFEITO[d['estado']].split(';')[0]})"
        for d in achados
    })


def _sonda_steam(amb: Ambiente) -> Resultado:
    raizes = _raizes_da_steam(amb)
    if not raizes:
        return Resultado(AUSENTE, "a Steam não está instalada para este usuário")
    ilegiveis: list[str] = []
    abriu = False
    perderam: list[str] = []
    opcoes: list[str] = []
    for raiz in raizes:
        confs = sorted((raiz / "userdata").glob("*/config/localconfig.vdf"))
        opcoes += _opcoes_desfeitas(amb, confs) if confs else []
        for conf in confs:
            try:
                texto = conf.read_text(encoding="utf-8", errors="replace")
            except OSError as erro:
                ilegiveis.append(f"{conf.name}: {erro.strerror}")
                continue
            if '"UserLocalConfigStore"' in texto[:4096]:
                abriu = True
                perderam += _perderam_o_wrapper(amb, conf)
    if abriu and (perderam or opcoes):
        partes = []
        if perderam:
            mostrados = ", ".join(sorted(set(perderam))[:5])
            partes.append(
                f"{len(set(perderam))} jogo(s) que tinham o wrapper do Hefesto voltaram sem ele "
                f"(a Steam reescreveu o localconfig.vdf): {mostrados}"
            )
        if opcoes:
            partes.append(
                f"{len(opcoes)} opção(ões) por jogo que o Hefesto escreveu a Steam não guarda "
                f"onde a lê: {', '.join(opcoes[:5])}"
            )
        return Resultado(QUEBROU, "; ".join(partes))
    if abriu:
        return Resultado(OK)
    detalhe = "nenhum localconfig.vdf com a raiz UserLocalConfigStore que o Hefesto lê"
    if ilegiveis:
        detalhe += " (ilegíveis: " + ", ".join(ilegiveis) + ")"
    return Resultado(QUEBROU, detalhe)


def _sonda_proton(amb: Ambiente) -> Resultado:
    pastas = [raiz / "compatibilitytools.d" for raiz in _raizes_da_steam(amb)]
    if not pastas:
        return Resultado(AUSENTE, "a Steam não está instalada para este usuário")
    achados = [
        p
        for pasta in pastas
        if pasta.is_dir()
        for p in sorted(pasta.glob("*/compatibilitytool.vdf"))
    ]
    if not achados:
        return Resultado(AUSENTE, "nenhum Proton de terceiros em compatibilitytools.d")
    sem_proton = [p.parent.name for p in achados if not (p.parent / "proton").exists()]
    if sem_proton:
        return Resultado(QUEBROU, "sem o executável `proton` em " + ", ".join(sem_proton))
    return Resultado(OK)


#: A EXCEÇÃO À REGRA DA CAPACIDADE (14/10/2026): o GE e o SDL mudam o que o jogo vê do controle sem
#: mudar porta nenhuma (a lista por appid do GE que virou PROTON_SONY_AUTO_XINPUT=1; o 054c:0df2 que
#: o SDL 3.4 passou a tratar como Edge). Para esses dois a única pergunta possível é a versão, e a
#: linha do censo diz `pergunta=versão`. O Proton da Valve e o UCM não são por versão.
#: A faixa do GE-Proton em que o Hefesto MEDIU o que o controle vê (o estudo do pino, 13/10/2026).
GE_COM_A_PILHA_DO_CONTROLE = (11, 4)  # o 11-4 trouxe o alto-falante e a vibração pelo som
GE_ULTIMO_COM_LISTA_POR_APPID = (11, 7)  # até aqui, PROTON_SONY_HIDRAW_XINPUT por appid
GE_ULTIMO_MEDIDO = (11, 8)  # lido no script; sem rodada de jogo (o recibo da qualificação)
_GE_RX = re.compile(r"GE-Proton(\d+)-(\d+)")

#: A env que só o Proton com a pilha de som do controle traz no script `proton`.
ENV_DA_PILHA_DE_SOM = "PROTON_ENABLE_MHWILDS_USB_AUDIO"

#: O SDL em que o Hefesto MEDIU o 054c:0df2 do controle virtual (a 3.4.x, lida em 09/10/2026).
SDL_DO_EDGE = (3, 4)
_SDL_RX = re.compile(r"libSDL3\.so\.0\.(\d+)\.(\d+)$")

#: As envs que o script do GE liga POR APPID e que trocam o controle que o jogo vê por cima da
#: máscara DualSense (as listas do `proton`, lidas no 11-7 e no 11-8 em 13/10/2026).
TROCAS_DO_GE_POR_APPID = {
    "PROTON_SONY_HIDRAW_XINPUT": "XInput",
    "PROTON_SONY_DUALSENSE_AS_DUALSHOCK4": "DualShock 4",
}
_LISTA_POR_APPID_RX = re.compile(
    r"if appid in \[(?P<lista>[^\]]*)\]:(?P<corpo>(?:\n[ \t]*(?:self\.env[^\n]*)?)+)"
)
_ENV_LIGADA_RX = re.compile(r'self\.env(?:\[\s*"(\w+)"\s*\]\s*=|\.setdefault\(\s*"(\w+)")')

#: O arquivo que o alsa-ucm-conf 1.2.15 traz para o DualSense (o commit `36a111ad` do
#: alsa-ucm-conf), e o verbo que o Hefesto grava.
UCM_DO_UPSTREAM = "USB-Audio/Sony/DualSense-PS5-HiFi.conf"
UCM_DO_HEFESTO = "USB-Audio/Hefesto/DualSense-HiFi.conf"


def _compatibilitytools(amb: Ambiente) -> list[Path]:
    return [
        p
        for raiz in _raizes_da_steam(amb)
        if (p := raiz / "compatibilitytools.d").is_dir()
    ]


def _texto_do_arquivo(caminho: Path, teto: int | None = None) -> str:
    """O texto do arquivo, ou vazio se ele não abre: a sonda pergunta, e ausência não é defeito."""
    try:
        return caminho.read_text(encoding="utf-8", errors="replace")[:teto]
    except OSError:
        return ""


def _versao_do_ge(pasta: Path) -> tuple[int, int] | None:
    """``(11, 7)`` de ``GE-Proton11-7-x86_64``, ou do arquivo ``version`` quando o nome não diz."""
    achou = _GE_RX.search(pasta.name) or _GE_RX.search(_texto_do_arquivo(pasta / "version", 200))
    return (int(achou.group(1)), int(achou.group(2))) if achou else None


def _fala_da_versao_do_ge(nome: str, versao: tuple[int, int]) -> str | None:
    rotulo = f"{versao[0]}-{versao[1]}"
    if versao < GE_COM_A_PILHA_DO_CONTROLE:
        return (
            f"{nome} é anterior ao 11-4, que trouxe o alto-falante e a vibração do controle pelo "
            "som: o jogo nessa versão fica sem os dois"
        )
    if versao > GE_ULTIMO_MEDIDO:
        return (
            f"{nome} é posterior ao último GE que o Hefesto mediu (11-{GE_ULTIMO_MEDIDO[1]}): o "
            "que ela liga por padrão para o controle não foi lido"
        )
    if versao > GE_ULTIMO_COM_LISTA_POR_APPID:
        return (
            f"{nome}: a lista por appid de PROTON_SONY_HIDRAW_XINPUT saiu e "
            "PROTON_SONY_AUTO_XINPUT=1 vale para todo jogo com o Steam Input desligado, então o "
            "controle virtual do Hefesto pode ganhar vaga XInput por cima da máscara escolhida "
            f"(medido no script do {rotulo}, ainda sem rodada de jogo)"
        )
    return None


def _o_mapa_dos_jogos(amb: Ambiente) -> dict[str, str]:
    """``{appid: ferramenta}`` do ``CompatToolMapping``, pelo dono (``proton_pin``).

    O appid ``"0"`` é o padrão da Steam, que vale para todo jogo sem escolha própria.
    """
    from .proton_pin import default_config_vdf, extract_compat_tool_mapping

    texto = _texto_do_arquivo(default_config_vdf(amb.home))
    return {a: f.lower() for a, f in extract_compat_tool_mapping(texto).items() if f}


def _nome_do_jogo(appid: str, amb: Ambiente) -> str:
    from .steam_launch_options import nome_do_appid

    if appid == "0":
        return "o padrão da Steam (os jogos sem escolha própria)"
    return nome_do_appid(appid, amb.home) or appid


def _jogos_na_ferramenta(nomes: set[str], mapa: dict[str, str], amb: Ambiente) -> set[str]:
    """Os appids que rodam na ferramenta: os mapeados nela e, se ela é o padrão, os sem escolha."""
    jogos = {a for a, f in mapa.items() if f in nomes and a != "0"}
    if mapa.get("0") in nomes:
        from .proton_pin import list_installed_appids

        jogos |= {a for a in list_installed_appids(amb.home) if a not in mapa}
    return jogos


def _trocas_por_appid(script: str) -> dict[str, set[str]]:
    """``{appid: {"XInput", ...}}``: as listas ``if appid in [...]`` do script do GE."""
    trocas: dict[str, set[str]] = {}
    for bloco in _LISTA_POR_APPID_RX.finditer(re.sub(r"#[^\n]*", "", script)):
        envs = {a or b for a, b in _ENV_LIGADA_RX.findall(bloco.group("corpo"))}
        efeitos = {TROCAS_DO_GE_POR_APPID[e] for e in envs if e in TROCAS_DO_GE_POR_APPID}
        for appid in re.findall(r'"(\d+)"', bloco.group("lista")) if efeitos else []:
            trocas.setdefault(appid, set()).update(efeitos)
    return trocas


def _fala_das_trocas_do_ge(pasta: Path, mapa: dict[str, str], amb: Ambiente) -> str | None:
    """O jogo nesse GE que a lista por appid do script troca de controle, pelo nome."""
    trocas = _trocas_por_appid(_texto_do_arquivo(pasta / "proton"))
    interno = re.search(
        r'"compat_tools"\s*\{\s*"([^"]+)"', _texto_do_arquivo(pasta / "compatibilitytool.vdf")
    )
    nomes = {pasta.name.lower()} | ({interno.group(1).lower()} if interno else set())
    por_efeito: dict[str, list[str]] = {}
    for appid in sorted(_jogos_na_ferramenta(nomes, mapa, amb) & trocas.keys(), key=int):
        for efeito in sorted(trocas[appid]):
            por_efeito.setdefault(efeito, []).append(_nome_do_jogo(appid, amb))
    if not por_efeito:
        return None
    partes = [f"como {efeito} a {', '.join(jogos[:5])}" for efeito, jogos in por_efeito.items()]
    return (
        f"{pasta.name} entrega o controle " + " e ".join(partes) + " (a lista por appid do "
        "script), por cima da máscara DualSense do Hefesto; no jogo que recebe XInput, a máscara "
        "Xbox no perfil dele põe o jogo e o Hefesto de acordo"
    )


def _sonda_ge_por_versao(amb: Ambiente) -> Resultado:
    pastas = _compatibilitytools(amb)
    if not _raizes_da_steam(amb):
        return Resultado(AUSENTE, "a Steam não está instalada para este usuário")
    instalados = [
        (p, v)
        for pasta in pastas
        for p in sorted(pasta.glob("GE-Proton*"))
        if p.is_dir() and (v := _versao_do_ge(p)) is not None
    ]
    if not instalados:
        return Resultado(AUSENTE, "nenhum GE-Proton em compatibilitytools.d")
    mapa = _o_mapa_dos_jogos(amb)
    avisos = [
        aviso
        for p, v in instalados
        for aviso in (_fala_da_versao_do_ge(p.name, v), _fala_das_trocas_do_ge(p, mapa, amb))
        if aviso
    ]
    return Resultado(QUEBROU, "; ".join(avisos)) if avisos else Resultado(OK)


def _chave_do_proton_da_valve(pasta: str) -> str:
    """O nome que o ``CompatToolMapping`` usa: ``Proton 10.0`` é ``proton_10``, e ``Proton 5.13``
    é ``proton_513``."""
    nome = re.sub(r"\s*\(.*?\)", "", pasta.lower()).strip()
    nome = re.sub(r"\.0$", "", nome).replace(".", "")
    return re.sub(r"[^a-z0-9]+", "_", nome).strip("_")


def _sonda_proton_da_valve(amb: Ambiente) -> Resultado:
    """O jogo que a Steam manda a um Proton da Valve perde a pilha de som do controle.

    A pergunta é ao script ``proton`` da pasta: sem a env do som do controle ele não sabe
    entregar o alto-falante nem a vibração pelo som. Só quem tem um jogo MAPEADO num desses
    Protons é avisado; um Proton da Valve sem jogo nenhum não tira nada de ninguém. As pastas da
    Steam, o mapa dos jogos e o nome de cada um vêm dos donos (``steam_launch_options``,
    ``proton_pin``): aqui não há leitura própria de ``steamapps`` nem de ``config.vdf``.
    """
    from .steam_launch_options import pastas_steamapps

    if not _raizes_da_steam(amb):
        return Resultado(AUSENTE, "a Steam não está instalada para este usuário")
    sem_pilha: dict[str, str] = {}
    com_script = False
    for biblioteca in pastas_steamapps(amb.home):
        for pasta in sorted((biblioteca / "common").glob("Proton*")):
            script = pasta / "proton"
            if not script.is_file():
                continue  # resíduo sem o script (`dist.lock` e `files`): não é um Proton instalado
            com_script = True
            texto = _texto_do_arquivo(script)
            if texto and ENV_DA_PILHA_DE_SOM not in texto:
                sem_pilha[_chave_do_proton_da_valve(pasta.name)] = pasta.name
    if not com_script:
        return Resultado(AUSENTE, "nenhum Proton da Valve instalado")
    nomes: dict[str, list[str]] = {}
    for appid, ferramenta in _o_mapa_dos_jogos(amb).items():
        do_proton = sem_pilha.get(ferramenta)
        if do_proton is not None:
            nomes.setdefault(do_proton, []).append(_nome_do_jogo(appid, amb))
    if not nomes:
        return Resultado(OK)
    partes = [
        f"{pasta}: {', '.join(sorted(set(jogos))[:5])}" for pasta, jogos in sorted(nomes.items())
    ]
    return Resultado(
        QUEBROU,
        "jogo(s) num Proton da Valve, que não traz a pilha de som do controle (" + "; ".join(partes)
        + "): perdem a vibração pelo som e o device KS do alto-falante",
    )


def _versoes_do_sdl(amb: Ambiente) -> list[tuple[str, tuple[int, int, int]]]:
    """``[(onde, (3, minor, micro))]`` das libSDL3 que um jogo pode carregar, lidas pelo nome."""
    pastas = [
        amb.caminho("/usr/lib/x86_64-linux-gnu"),
        amb.caminho("/usr/lib64"),
        amb.caminho("/usr/lib"),
    ]
    from .steam_launch_options import pastas_steamapps

    for biblioteca in pastas_steamapps(amb.home) if _raizes_da_steam(amb) else []:
        for runtime in sorted((biblioteca / "common").glob("SteamLinuxRuntime_*")):
            plataformas = sorted(runtime.glob("steamrt*_platform_*"))
            if plataformas:  # a mais nova: é a que o jogo carrega
                pastas.append(plataformas[-1] / "files" / "lib" / "x86_64-linux-gnu")
    achados: list[tuple[str, tuple[int, int, int]]] = []
    for pasta in pastas:
        if not pasta.is_dir():
            continue
        for arquivo in sorted(pasta.glob("libSDL3.so.0.*")):
            achou = _SDL_RX.search(arquivo.name)
            if achou:
                versao = (3, int(achou.group(1)), int(achou.group(2)))
                achados.append((str(arquivo.parent), versao))
    return achados


def _sonda_sdl_por_versao(amb: Ambiente) -> Resultado:
    achados = _versoes_do_sdl(amb)
    if not achados:
        return Resultado(AUSENTE, "nenhuma libSDL3 no sistema nem no runtime da Steam")
    adiante = [
        f"SDL {v[0]}.{v[1]}.{v[2]} em {onde}" for onde, v in achados if v[:2] > SDL_DO_EDGE
    ]
    if adiante:
        return Resultado(
            QUEBROU,
            "; ".join(adiante) + f": é posterior ao {SDL_DO_EDGE[0]}.{SDL_DO_EDGE[1]}, o último em "
            "que o Hefesto mediu o 054c:0df2 do controle virtual (Edge, rumble reforçado, "
            "paddles); confira a vibração e as teclas traseiras num jogo SDL",
        )
    return Resultado(OK)


def _sonda_ucm_de_um_dono_so(amb: Ambiente) -> Resultado:
    """O do sistema abre o alto-falante em mono e esconde os canais 3 e 4, que são a háptica.

    Com os dois no disco o dono é o do Hefesto: o ``ucm.conf`` lê o gancho de ``conf.d/`` antes
    do ``USB-Audio.conf`` do pacote (o ``UseCasePath.confd1``, igual no 1.2.10 e no 1.2.15).
    """
    raiz = amb.caminho("/usr/share/alsa") / "ucm2"
    if not raiz.is_dir():
        return Resultado(AUSENTE, "sem alsa-ucm-conf nesta máquina")
    if (raiz / UCM_DO_UPSTREAM).is_file() and not (raiz / UCM_DO_HEFESTO).is_file():
        return Resultado(
            QUEBROU,
            f"o alsa-ucm-conf do sistema traz {UCM_DO_UPSTREAM}, que abre o alto-falante do "
            "controle em mono e não mostra os canais da háptica, e o do Hefesto não está "
            "instalado: a vibração pelo som não chega ao controle no cabo. Instale o do Hefesto "
            "com scripts/install_ucm_dualsense.sh",
        )
    return Resultado(OK)


def _sonda_cosmic(amb: Ambiente) -> Resultado:
    if "COSMIC" not in amb.env.get("XDG_CURRENT_DESKTOP", "").upper():
        return Resultado(AUSENTE, "a sessão não é COSMIC")
    if (amb.home / ".config" / "cosmic").is_dir():
        return Resultado(OK)
    return Resultado(QUEBROU, "a sessão é COSMIC e ~/.config/cosmic não existe")


CONTRATOS: tuple[Contrato, ...] = (
    Contrato(
        id="bluez-dbus",
        dono="bluez",
        promessa="o BlueZ atende em org.bluez pelo D-Bus do sistema",
        conferir=f"{bluez_dbus.FERRAMENTA} --system tree {bluez_dbus.SERVICO}",
        sonda=_sonda_bluez,
    ),
    Contrato(
        id="pipewire-pactl-json",
        dono="pipewire",
        promessa="o pactl entrega JSON (`--format=json`)",
        conferir="LC_ALL=C pactl --format=json info",
        sonda=_sonda_pactl_json,
    ),
    Contrato(
        id="pipewire-wpctl",
        dono="pipewire",
        promessa="o wpctl fala com o WirePlumber",
        conferir="wpctl status",
        sonda=_sonda_wpctl,
    ),
    Contrato(
        id="systemd-usuario",
        dono="systemd",
        promessa="o systemd de usuário responde ao systemctl --user",
        conferir="systemctl --user show-environment",
        sonda=_sonda_systemd,
    ),
    Contrato(
        id="kernel-nos",
        dono="kernel",
        promessa="uinput, uhid, hidraw e evdev existem como nós",
        conferir="ls -l /dev/uinput /dev/uhid /dev/input /sys/class/hidraw",
        sonda=_sonda_nos_do_kernel,
    ),
    Contrato(
        id="kernel-driver-sony",
        dono="kernel",
        promessa="o kernel em uso tem o driver playstation, ligado ou pronto para carregar",
        conferir="modinfo -F filename hid_playstation",
        sonda=_sonda_driver_sony,
    ),
    Contrato(
        id="steam-localconfig",
        dono="steam",
        promessa=(
            "o localconfig.vdf da Steam abre com a raiz UserLocalConfigStore e guarda o wrapper "
            "e as opções por jogo que o Hefesto aplicou"
        ),
        conferir=(
            "head -c 200 ~/.steam/steam/userdata/*/config/localconfig.vdf; "
            "grep -c hefesto-launch ~/.steam/steam/userdata/*/config/localconfig.vdf; "
            "python3 -m hefesto_dualsense4unix.integrations.opcoes_por_jogo --conferir"
        ),
        sonda=_sonda_steam,
        cobre=("cfg:localconfig.vdf", "cfg:loginusers.vdf"),
    ),
    Contrato(
        id="proton-de-terceiros",
        dono="proton",
        promessa="cada Proton em compatibilitytools.d traz compatibilitytool.vdf e o `proton`",
        conferir="ls ~/.steam/steam/compatibilitytools.d/*/",
        sonda=_sonda_proton,
    ),
    Contrato(
        id="ge-por-versao",
        dono="proton",
        promessa=(
            "o GE-Proton instalado está na faixa em que o Hefesto mediu o que o controle vê "
            "(11-4 a 11-8), e a lista por appid do script não troca o controle de jogo nenhum"
        ),
        conferir="cat ~/.steam/steam/compatibilitytools.d/GE-Proton*/version",
        sonda=_sonda_ge_por_versao,
        cobre=("cfg:GE-Proton*",),
    ),
    Contrato(
        id="proton-da-valve-sem-som",
        dono="proton",
        promessa=(
            "nenhum jogo está num Proton da Valve, que não traz a pilha de som do controle "
            "(a vibração pelo som e o device KS do alto-falante)"
        ),
        conferir=(
            f"grep -c {ENV_DA_PILHA_DE_SOM} ~/.steam/steam/steamapps/common/Proton*/proton"
        ),
        sonda=_sonda_proton_da_valve,
        cobre=("cfg:Proton*",),
    ),
    Contrato(
        id="sdl-por-versao",
        dono="sdl",
        promessa=(
            "a libSDL3 que o jogo carrega não passa do 3.4, onde o Hefesto mediu o 054c:0df2 "
            "do controle virtual"
        ),
        conferir=(
            "ls /usr/lib/x86_64-linux-gnu/libSDL3.so.0.* "
            "~/.steam/steam/steamapps/common/SteamLinuxRuntime_*/*/files/lib/x86_64-linux-gnu/"
            "libSDL3.so.0.*"
        ),
        sonda=_sonda_sdl_por_versao,
        cobre=("path:/usr/lib/x86_64-linux-gnu",),
    ),
    Contrato(
        id="ucm-de-um-dono-so",
        dono="alsa-ucm-conf",
        promessa=(
            "o UCM do DualSense é de um dono só, o do Hefesto, que o ucm.conf lê antes do que o "
            "alsa-ucm-conf 1.2.15 traz (o do sistema esconde os canais da háptica)"
        ),
        conferir=(
            f"ls /usr/share/alsa/ucm2/{UCM_DO_UPSTREAM} /usr/share/alsa/ucm2/{UCM_DO_HEFESTO}"
        ),
        sonda=_sonda_ucm_de_um_dono_so,
    ),
    Contrato(
        id="cosmic-config",
        dono="cosmic",
        promessa="a configuração pública do COSMIC está em ~/.config/cosmic",
        conferir="ls ~/.config/cosmic",
        sonda=_sonda_cosmic,
    ),
)


def linhas_do_doctor(
    amb: Ambiente | None = None, contratos: Sequence[Contrato] = CONTRATOS
) -> list[tuple[str, str]]:
    """``[(tag, mensagem)]`` no formato do doctor. Quebrou nomeia o contrato e o comando."""
    amb = amb or Ambiente()
    linhas: list[tuple[str, str]] = []
    for c in contratos:
        r = c.sonda(amb)
        if r.estado == OK:
            linhas.append(("[ OK ]", f"{c.id} ({c.dono}): {c.promessa}"))
        elif r.estado == AUSENTE:
            linhas.append(("[INFO]", f"{c.id} ({c.dono}): não se aplica aqui ({r.detalhe})"))
        else:
            linhas.append(
                (
                    "[WARN]",
                    f"o contrato {c.id} ({c.dono}) quebrou: {r.detalhe}. Prometia: {c.promessa}. "
                    f"Confira: {c.conferir}",
                )
            )
    return linhas
