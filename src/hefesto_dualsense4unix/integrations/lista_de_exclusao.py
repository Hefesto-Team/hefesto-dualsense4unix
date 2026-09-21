"""A lista de exclusão do Hefesto — OS-LANCADORES-IGUAIS-E-A-LISTA-DE-EXCLUSAO-01.

**O QUE ELA É, em uma frase (a do §3 da sprint):** o jogo que está aqui vê o
controle como se o Hefesto não estivesse instalado.

O pedido é dela, 21/09/2026, olhando a aba Lançadores: *"(...) Adicionar jogo a
lista de exclusão do Hefesto (cujo objetivo é garantir que tal jogo não use
nenhuma feature do hefesto)"*. <!-- noqa-acento: citação literal dela -->

ESTA LISTA É UM GUARDA-CHUVA, e não um nono leitor
--------------------------------------------------
Duas listas por feature já existiam, cada uma com dono, leitor e régua (medido
na E0, §10.1 da sprint):

- ``pino`` — o Proton pinado; dono: ``proton_pin.nomear_fora_do_pino``;
- ``atalho`` — o atalho de inicialização; dono:
  ``steam_launch_options.marcar_jogo_sem_wrapper``.

**A LISTA DO STEAM INPUT NÃO ENTRA, e ela chegou a entrar.** A primeira redação
deste módulo punha o jogo excluído também no ``steam_input_apps.txt``, lendo o
rótulo ``launch_env.ESTADO_ALLOWLIST_STEAM_INPUT`` («físico é o único
dispositivo»). O rótulo é anterior à decisão dela de 09/08/2026
(ESCONDER-EM-VEZ-DE-SAIR-01): desde então a marca **esconde o físico e mantém os
virtuais de pé** — *"a allowlist do Steam Input NÃO tira o Hefesto da frente"*
(`gamepad.set_steam_input_exception`). Escrever nela deixaria o Hefesto NA
FRENTE do jogo que ela excluiu. Esta lista não toca na do Steam Input, em
nenhum sentido.

Excluir é ESCREVER nas duas; tirar é sair delas. Nenhum leitor muda — cada um
continua lendo o mesmo arquivo de antes. A alternativa (cada feature aprender a
perguntar a esta lista) faria oito donos lerem um arquivo novo, e o primeiro que
esquecesse deixaria uma feature viva num jogo que ela excluiu.

TIRAR DEVOLVE SÓ O QUE ESTA LISTA ESCREVEU
------------------------------------------
Se o jogo já estava numa das duas por escolha DELA antes de ser excluído, ele
continua lá depois do «Tirar». Quem diz de quem era a linha é o próprio dono:
``"adicionado"`` quer dizer que a escrita foi nossa; ``"ja_estava"`` quer dizer
que era dela. A entrada guarda só as listas em que NÓS escrevemos
(``escritas``), e o «Tirar» só sai delas. Sem isso, excluir e tirar apagaria uma
escolha anterior dela, calado — a exclusão viraria borracha.

A CHAVE É A IDENTIDADE DA JANELA
--------------------------------
``steam_app_<N>`` para a Steam e para todo jogo pelo umu, que é o que
``identidade_de_janela`` devolve e o endereço que o daemon vê em foco. As duas
listas falam só dígitos, então só uma chave com ``N`` as alcança; o atalho e o
pino são features só da Steam, e um jogo sem ``N`` não tem o que tirar ali. Os
emuladores entram com a chave do PROCESSO — um processo para todas as ROMs, e a
exclusão vale para o emulador inteiro (§4.3 da sprint).

NUNCA LEVANTA: quem chama é um clique de botão. Um arquivo torto não é
sobrescrito — é recusado com ``"erro"``, porque sobrescrevê-lo apagaria a lista
dela inteira para gravar uma linha.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from hefesto_dualsense4unix.integrations import proton_pin
from hefesto_dualsense4unix.integrations import steam_launch_options as slo

#: O arquivo, ao lado das outras listas, no ``XDG_CONFIG_HOME``.
RELPATH = "hefesto-dualsense4unix/lista_de_exclusao.json"
FORMATO = 1

#: As duas listas por feature, na ordem em que se escreve. A do Steam Input
#: NÃO está aqui — ver o topo do módulo.
LISTAS: tuple[str, ...] = ("pino", "atalho")

#: A nota que acompanha a linha em cada lista — é o que ela lê se abrir o
#: arquivo, e o que diz que a linha não é dela.
NOTA_DAS_LISTAS = "posto pela lista de exclusão do Hefesto"

_STEAM_APP = re.compile(r"^steam_app_(\d+)$")


def caminho(config_home: Path | None = None) -> Path:
    """``$XDG_CONFIG_HOME/hefesto-dualsense4unix/lista_de_exclusao.json``."""
    if config_home is None:
        xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
        config_home = Path(xdg) if xdg else Path.home() / ".config"
    return config_home / RELPATH


def appid_da_chave(chave: str) -> str | None:
    """O ``N`` de ``steam_app_<N>``, ou ``None`` — e só então as duas listas."""
    m = _STEAM_APP.match(chave.strip())
    return m.group(1) if m else None


@dataclass(frozen=True)
class Entrada:
    """UM jogo excluído."""

    chave: str
    lancador: str
    nome: str
    quando: str
    nota: str = ""
    #: As listas em que ESTA exclusão escreveu — e só delas o «Tirar» sai.
    escritas: tuple[str, ...] = field(default_factory=tuple)
    #: As OUTRAS classes de janela que esta entrada cobre. Um emulador é um
    #: processo para todas as ROMs, e o mesmo emulador anuncia classes
    #: diferentes conforme veio (o flatpak do RetroArch se chama
    #: `org.libretro.RetroArch` e a janela dele diz `com.libretro.RetroArch`,
    #: medido em 10/09/2026). Vazio para o jogo da Steam e do umu, cuja chave
    #: JÁ é a classe da janela.
    janelas: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# As duas listas — um adaptador por lista, os donos de verdade fazem a escrita
# ---------------------------------------------------------------------------
_POR: dict[str, Callable[[str], str]] = {
    "pino": lambda a: proton_pin.nomear_fora_do_pino(a, nota=NOTA_DAS_LISTAS),
    "atalho": lambda a: slo.marcar_jogo_sem_wrapper(a, nota=NOTA_DAS_LISTAS),
}
_TIRAR: dict[str, Callable[[str], str]] = {
    "pino": proton_pin.devolver_ao_pino,
    "atalho": slo.desmarcar_jogo_sem_wrapper,
}


# ---------------------------------------------------------------------------
# O arquivo
# ---------------------------------------------------------------------------
class _ArquivoTortoError(Exception):
    """O JSON existe e não se lê — recusa, nunca sobrescreve."""


def _ler_cru(destino: Path) -> list[Entrada]:
    try:
        texto = destino.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    try:
        dado = json.loads(texto)
        jogos = dado["jogos"]
        return [
            Entrada(
                chave=str(j["chave"]),
                lancador=str(j.get("lancador", "")),
                nome=str(j.get("nome", "")),
                quando=str(j.get("quando", "")),
                nota=str(j.get("nota", "")),
                escritas=tuple(x for x in j.get("escritas", ()) if x in LISTAS),
                janelas=tuple(str(x) for x in j.get("janelas", ()) if str(x).strip()),
            )
            for j in jogos
        ]
    except (ValueError, KeyError, TypeError) as exc:
        raise _ArquivoTortoError(str(exc)) from exc


def _gravar(destino: Path, entradas: list[Entrada]) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    corpo = json.dumps(
        {"formato": FORMATO, "jogos": [asdict(e) for e in entradas]},
        ensure_ascii=False, indent=2,
    ) + "\n"
    fd, provisorio = tempfile.mkstemp(dir=destino.parent, prefix=".lista_de_exclusao.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as saida:
            saida.write(corpo)
        os.replace(provisorio, destino)
    except BaseException:
        Path(provisorio).unlink(missing_ok=True)
        raise


def ler(config_home: Path | None = None) -> list[Entrada]:
    """Os jogos excluídos. Arquivo ausente ou torto = lista vazia. Nunca levanta."""
    try:
        return _ler_cru(caminho(config_home))
    except (_ArquivoTortoError, OSError):
        return []


def appids(config_home: Path | None = None) -> list[str]:
    """Os appids da Steam (e do umu) excluídos — o que os donos por appid leem."""
    return [a for a in (appid_da_chave(e.chave) for e in ler(config_home)) if a]


def contem(chave: str, config_home: Path | None = None) -> bool:
    """Esta classe de janela está excluída — pela chave ou por uma das janelas?

    É o que o autoswitch pergunta a cada tique, com a `wm_class` em foco. A
    comparação das `janelas` ignora maiúsculas porque a mesma aplicação chega
    com grafias diferentes: o journal de 21/09/2026 tem a janela do próprio
    Hefesto como `Hefesto-Dualsense4Unix` (113 vezes) e como
    `hefesto-dualsense4unix` (60).
    """
    alvo = chave.strip()
    if not alvo:
        return False
    dobrado = alvo.casefold()
    return any(
        e.chave == alvo or any(j.casefold() == dobrado for j in e.janelas)
        for e in ler(config_home)
    )


# ---------------------------------------------------------------------------
# Os dois atos
# ---------------------------------------------------------------------------
def adicionar(
    chave: str,
    *,
    lancador: str,
    nome: str,
    nota: str = "",
    config_home: Path | None = None,
    escritas_herdadas: tuple[str, ...] = (),
    janelas: tuple[str, ...] = (),
) -> str:
    """Exclui o jogo. Status: ``"adicionado"`` | ``"ja_estava"`` |
    ``"chave_invalida"`` | ``"erro"``. Nunca levanta.

    `escritas_herdadas`: listas em que o jogo já estava e que passam a ser
    DESTA exclusão (o «Tirar» sai delas também). Vazio no uso normal.
    """
    alvo = chave.strip()
    if not alvo:
        return "chave_invalida"
    destino = caminho(config_home)
    try:
        atuais = _ler_cru(destino)
    except (_ArquivoTortoError, OSError):
        return "erro"
    if any(e.chave == alvo for e in atuais):
        return "ja_estava"

    escritas = list(escritas_herdadas)
    appid = appid_da_chave(alvo)
    if appid is not None:
        for lista in LISTAS:
            if lista in escritas:
                continue
            status = _POR[lista](appid)
            if status == "adicionado":
                escritas.append(lista)
            elif status != "ja_estava":
                # Uma escrita que falhou desfaz as que já foram feitas: um jogo
                # meio excluído é o estado que a D-2109-A-EXCLUSAO-E-TUDO-OU-NADA
                # existe para não ter.
                for feita in escritas:
                    if feita not in escritas_herdadas:
                        _TIRAR[feita](appid)
                return "erro"

    nova = Entrada(
        chave=alvo, lancador=lancador, nome=nome,
        quando=time.strftime("%Y-%m-%dT%H:%M:%S"), nota=nota,
        escritas=tuple(x for x in LISTAS if x in escritas),
        janelas=tuple(j.strip() for j in janelas if j.strip()),
    )
    try:
        _gravar(destino, [*atuais, nova])
    except OSError:
        if appid is not None:
            for feita in nova.escritas:
                if feita not in escritas_herdadas:
                    _TIRAR[feita](appid)
        return "erro"
    return "adicionado"


def tirar(chave: str, *, config_home: Path | None = None) -> str:
    """Devolve o jogo ao Hefesto. Status: ``"removido"`` | ``"nao_estava"`` |
    ``"erro"``. Nunca levanta.

    Sai SÓ das listas em que esta exclusão escreveu (``Entrada.escritas``): uma
    linha que já era dela antes da exclusão continua lá.
    """
    alvo = chave.strip()
    destino = caminho(config_home)
    try:
        atuais = _ler_cru(destino)
    except (_ArquivoTortoError, OSError):
        return "erro"
    achada = next((e for e in atuais if e.chave == alvo), None)
    if achada is None:
        return "nao_estava"
    appid = appid_da_chave(alvo)
    if appid is not None:
        for lista in achada.escritas:
            if _TIRAR[lista](appid) not in ("removido", "nao_estava"):
                return "erro"
    try:
        _gravar(destino, [e for e in atuais if e.chave != alvo])
    except OSError:
        return "erro"
    return "removido"


# ---------------------------------------------------------------------------
# O disco — o que o jogo já tem sai AGORA, se a Steam deixar
# ---------------------------------------------------------------------------
#: As recusas que querem dizer "a Steam está aberta" nos dois donos.
_ESPERA_A_STEAM = frozenset({"steam_aberta", "jogo_da_steam_aberto"})


def tirar_do_disco(chave: str) -> str:
    """Tira do jogo o pino, o atalho e o que o Hefesto pôs no prefixo dele.

    Nunca levanta. O prefixo é o `_devolver_o_prefixo`: o device KS e as
    camadas Vulkan que a cura desligou.

    Status: ``"feito"`` | ``"nada_a_tirar"`` | ``"espera_a_steam"`` |
    ``"sem_appid"`` | ``"erro"``.

    As duas listas só fazem o jogo ser PULADO (§11.2 da sprint): entrar nelas
    não tira o que ele já tem. Quem tira é o vigia da Steam — o
    `sentinela_do_wrapper --reparar` e o `proton_pin --manter`, que desde
    21/09 honram a própria lista nos dois sentidos —, e ele roda quando a
    Steam fecha. Esta função é o mesmo passo feito na hora do clique, para o
    jogo não abrir uma vez com o Hefesto antes de a Steam fechar.

    Com a Steam aberta os dois donos recusam sem escrever, e o status diz
    ``"espera_a_steam"``: a lista já está gravada, e o vigia termina o serviço.
    """
    appid = appid_da_chave(chave)
    if appid is None:
        return "sem_appid"
    pino = proton_pin.destravar_um_jogo(appid)
    atalho = slo.tirar_o_atalho_dos_jogos([appid])
    prefixo = _devolver_o_prefixo(appid)
    razoes = {str(e.get("reason", "")) for e in atalho["errors"]}
    if pino.get("status") == "recusado" or razoes & _ESPERA_A_STEAM or prefixo == "ocupado":
        return "espera_a_steam"
    if pino.get("status") == "erro" or atalho["errors"] or prefixo == "erro":
        return "erro"
    if pino.get("status") == "destravado" or atalho["removed"] or prefixo == "feito":
        return "feito"
    return "nada_a_tirar"


def _devolver_o_prefixo(appid: str) -> str:
    """O prefixo Wine do jogo volta ao que era sem o Hefesto.

    Duas coisas moram lá, e as duas são nossas: o device KS da háptica
    (`audio_ks_dualsense`) e as camadas Vulkan que a cura desligou
    (`camadas_vulkan`). O KS sai inteiro; as camadas voltam a ligar SÓ as que
    nós desligamos, sem virar escolha dela (``pela_exclusao``).

    Com o jogo aberto o `wineserver` regravaria o registro ao sair, e a edição
    seria perdida: ``"ocupado"``. Status: ``"feito"`` | ``"nada"`` |
    ``"ocupado"`` | ``"erro"``. Nunca levanta.
    """
    from hefesto_dualsense4unix.integrations import audio_ks_dualsense as ks
    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

    status = "nada"
    for pasta in cv.pastas_compatdata():
        raiz = pasta / appid
        if not (raiz / "pfx" / "system.reg").is_file():
            continue
        if ks.wineserver_do_prefixo_vivo(raiz / "pfx"):
            return "ocupado"
        try:
            tirado = ks.aplicar(raiz, controles=[])
            camadas = cv.aplicar_no_prefixo(
                cv.prefixo_de_jogo(raiz, appid=appid), religar=True, pela_exclusao=True
            )
        except OSError:
            return "erro"
        if tirado.motivo == "ocupado":
            return "ocupado"
        if camadas.erro:
            return "erro"
        if tirado.escreveu or camadas.mexeu:
            status = "feito"
    return status


__all__ = [
    "LISTAS",
    "NOTA_DAS_LISTAS",
    "Entrada",
    "adicionar",
    "appid_da_chave",
    "appids",
    "caminho",
    "contem",
    "ler",
    "tirar",
    "tirar_do_disco",
]
