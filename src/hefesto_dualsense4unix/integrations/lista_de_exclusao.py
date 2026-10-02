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
continua lendo o mesmo arquivo de antes.

FORA DA STEAM, O AMBIENTE (01/10/2026). O jogo do Heroic com a mesma janela
ganha a lista própria de ambiente sem o que é nosso (o Heroic monta
`{...globais, ...do jogo}`), e a entrada guarda o «antes» dela em ``heroic``;
a caixa do Flatpak de um emulador excluído perde o ambiente inteiro. A carona
de cada transição (`cura_por_estrada.curar_todas_as_estradas`) pergunta a esta
lista o que pular (:func:`o_que_a_carona_pula`), e a do device KS também
(:func:`prefixos_excluidos`). Desde 02/10/2026 (A-EXCLUSAO-MORA-NA-CAMADA-DO-JOGO-01)
o jogo do Lutris Flatpak com a mesma janela ganha a camada dele (o
`system.env` do `.yml`, cobrindo a caixa, que é de todos os jogos), com o
«antes» em ``lutris``; e o prefixo do Heroic que outro jogo divide fica com o
que é nosso (:func:`prefixos_excluidos`). Os donos dos arquivos continuam sendo os de
sempre; esta lista só diz QUAIS jogos. A alternativa (cada feature aprender a
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

import contextlib
import json
import os
import re
import tempfile
import time
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

from hefesto_dualsense4unix.core import o_dono_do_evento as _ode
from hefesto_dualsense4unix.integrations import cura_por_estrada as cpe
from hefesto_dualsense4unix.integrations import proton_pin
from hefesto_dualsense4unix.integrations import steam_launch_options as slo
from hefesto_dualsense4unix.utils.leitura_pela_assinatura import LeituraPelaAssinatura

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

#: A chave do emulador inteiro — a aba 07 a monta (`_chave_do_emulador`).
PREFIXO_DO_EMULADOR = "emulador:"


def caminho(config_home: Path | None = None) -> Path:
    """``$XDG_CONFIG_HOME/hefesto-dualsense4unix/lista_de_exclusao.json``.

    A conta é do dono da trava (`cura_por_estrada.caminho_da_lista`): a trava
    mora ao lado do arquivo, e quem escreve tem de achar a mesma.
    """
    return cpe.caminho_da_lista(config_home)


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
    #: As cópias do Heroic que esta exclusão mexeu, com o «antes» de cada uma
    #: (01/10/2026): o jogo do Heroic sai do ambiente pela lista própria, e o
    #: «Tirar» a devolve. Vazio para quem o Heroic não conhece.
    heroic: tuple[cpe.CopiaDoJogo, ...] = field(default_factory=tuple)
    #: Os `.yml` do Lutris Flatpak que esta exclusão cobriu, com o «antes» de
    #: cada um (02/10/2026). Vazio para quem o Lutris não conhece.
    lutris: tuple[cpe.YmlDoJogo, ...] = field(default_factory=tuple)


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
                heroic=tuple(c for c in (cpe.CopiaDoJogo.de_dado(x)
                                         for x in j.get("heroic", ())) if c),
                lutris=tuple(y for y in (cpe.YmlDoJogo.de_dado(x)
                                         for x in j.get("lutris", ())) if y),
            )
            for j in jogos
        ]
    except (ValueError, KeyError, TypeError) as exc:
        raise _ArquivoTortoError(str(exc)) from exc


def _como_dado(e: Entrada) -> dict[str, object]:
    """A entrada como vai ao JSON — sem a chave ``heroic`` quando vazia.

    Sem cópia do Heroic, a linha sai byte a byte como saía antes de 01/10: o
    `hefesto-launch.sh` lê este arquivo linha a linha, e uma lista vazia a
    mais não muda nada para ele, mas o arquivo de quem nunca excluiu um jogo
    do Heroic não tem por que mudar.
    """
    dado: dict[str, object] = asdict(e)
    dado.pop("heroic", None)
    dado.pop("lutris", None)
    if e.heroic:
        dado["heroic"] = [c.como_dado() for c in e.heroic]
    if e.lutris:
        dado["lutris"] = [y.como_dado() for y in e.lutris]
    return dado


def _gravar(destino: Path, entradas: list[Entrada]) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    corpo = json.dumps(
        {"formato": FORMATO, "jogos": [_como_dado(e) for e in entradas]},
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


#: O-REPOUSO-ESPERA-O-EVENTO-01, família 6 (29/09/2026): a lista que o
#: autoswitch pergunta a 2 Hz, guardada pela assinatura do `stat`. Medido na
#: sonda S.4: 117 `open` por minuto num arquivo que nem existia. Só com o dono
#: do evento armado; desarmar esquece.
_LISTA_PELA_ASSINATURA: LeituraPelaAssinatura[list[Entrada]] = LeituraPelaAssinatura(
    _ler_cru, copiar=list
)
_ode.ao_desarmar(_LISTA_PELA_ASSINATURA.esquecer)


def _ler_para_o_tique(config_home: Path | None = None) -> list[Entrada]:
    """A lista que o `contem` consulta: pela assinatura com o dono armado."""
    if not _ode.armado():
        return ler(config_home)
    try:
        return _LISTA_PELA_ASSINATURA.ler(caminho(config_home))
    except (_ArquivoTortoError, OSError):
        return []


def ler(config_home: Path | None = None) -> list[Entrada]:
    """Os jogos excluídos. Arquivo ausente ou torto = lista vazia. Nunca levanta."""
    try:
        return _ler_cru(caminho(config_home))
    except (_ArquivoTortoError, OSError):
        return []


def e_caixa(chave: str) -> bool:
    """A chave é de um emulador (``emulador:<cartão>``): um processo, uma caixa."""
    return chave.strip().startswith(PREFIXO_DO_EMULADOR)


def o_que_a_carona_pula(config_home: Path | None = None) -> cpe.NaExclusao:
    """O que `cura_por_estrada.curar_todas_as_estradas` não escreve.

    As caixas: as janelas das entradas de emulador (os `app-id` estão entre
    elas). As cópias: as do Heroic, que a carona mantém sem o que é nosso. Os
    `.yml`: os do Lutris Flatpak, que a carona mantém cobrindo a caixa.
    """
    entradas = ler(config_home)
    return cpe.NaExclusao(
        caixas=frozenset(j.casefold() for e in entradas if e_caixa(e.chave)
                         for j in e.janelas),
        copias=tuple(c for e in entradas for c in e.heroic),
        ymls=tuple(y for e in entradas for y in e.lutris))


def anotar_os_ymls(ymls: Iterable[cpe.YmlDoJogo], config_home: Path | None = None) -> str:
    """A carona escreveu de novo nestes `.yml`: o registro da volta acompanha.

    Cada um substitui o de mesmo arquivo na entrada que o tem. Sem isso, a
    volta byte a byte compararia o arquivo com o `sha256` de uma escrita velha
    e cairia na volta pelos pares. Status: ``"feito"`` | ``"nada"`` |
    ``"erro"``. Nunca levanta.
    """
    novos = {y.arquivo: y for y in ymls}
    if not novos:
        return "nada"
    destino = caminho(config_home)
    with cpe.trava_da_lista(destino) as na_mao:
        return _anotar_na_trava(destino, novos) if na_mao else "erro"


def _anotar_na_trava(destino: Path, novos: dict[str, cpe.YmlDoJogo]) -> str:
    try:
        atuais = _ler_cru(destino)
    except (_ArquivoTortoError, OSError):
        return "erro"
    mudou = False
    saida: list[Entrada] = []
    for e in atuais:
        if any(y.arquivo in novos for y in e.lutris):
            e = replace(e, lutris=tuple(novos.get(y.arquivo, y) for y in e.lutris))
            mudou = True
        saida.append(e)
    if not mudou:
        return "nada"
    try:
        _gravar(destino, saida)
    except OSError:
        return "erro"
    return "feito"


#: O arquivo em que o Heroic anota quem usa cada prefixo: a cada lançamento ele
#: acrescenta o `app_name` do jogo a `<winePrefix>/installed_games`, uma lista
#: JSON (lido no `app.asar` do Heroic 2.22.3 em 02/10/2026; no disco dela, o
#: prefixo do Guardiões tem um `app_name` só).
_MORADORES_DO_HEROIC = "installed_games"

#: Os prefixos divididos já ditos no diário, com o número de moradores — uma
#: linha por mudança, e não uma por transição.
_DIVIDIDOS_DITOS: set[tuple[str, int]] = set()


def _resolvido(caminho: str | Path) -> Path | None:
    try:
        return Path(caminho).expanduser().resolve()
    except (OSError, RuntimeError):  # pragma: no cover - caminho impossível
        return None


def _moradores(prefixo: Path, casa: Path) -> set[str]:
    """Os `app_name` dos jogos do Heroic que moram neste prefixo (resolvido).

    Três fontes, somadas: quem o Heroic anotou em `installed_games`; toda cópia
    da casa (`GamesConfig/<app>.json`) com o mesmo `winePrefix` resolvido; e,
    quando o prefixo é o da lista global (`defaultSettings.winePrefix`), todo
    jogo sem `winePrefix` próprio — as cópias sem ele e os instalados sem
    cópia. Nunca levanta: o que não se lê não entra.
    """
    fora: set[str] = set()
    try:
        anotados = json.loads((prefixo / _MORADORES_DO_HEROIC).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        anotados = []
    fora.update(str(a) for a in (anotados if isinstance(anotados, list) else ())
                if isinstance(a, str) and a)
    try:
        global_ = json.loads((casa / "config.json").read_text(encoding="utf-8"))
        padrao = global_.get("defaultSettings", {}).get("winePrefix")
    except (OSError, ValueError, AttributeError):
        padrao = None
    e_o_global = isinstance(padrao, str) and padrao.strip() != "" and (
        _resolvido(padrao.strip()) == prefixo)
    com_copia: set[str] = set()
    pasta = casa / "GamesConfig"
    for arquivo in sorted(pasta.glob("*.json")) if pasta.is_dir() else ():
        try:
            dado = json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        jogo = dado.get(arquivo.stem) if isinstance(dado, dict) else None
        if not isinstance(jogo, dict):
            continue
        com_copia.add(arquivo.stem)
        proprio = jogo.get("winePrefix")
        if isinstance(proprio, str) and proprio.strip():
            if _resolvido(proprio.strip()) == prefixo:
                fora.add(arquivo.stem)
        elif e_o_global:
            fora.add(arquivo.stem)
    if e_o_global:
        from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

        with contextlib.suppress(Exception):
            fora.update(j.chave for j in censo._heroic(casa).jogos
                        if j.instalado and j.chave not in com_copia)
    return fora


def prefixos_excluidos(config_home: Path | None = None) -> frozenset[Path]:
    """Os prefixos dos jogos excluídos do Heroic em que TODO morador está excluído.

    Caminho resolvido, porque quem compara (a carona do device KS e o
    «Corrigir Vulkan») lê o mesmo prefixo por outra fonte.

    **O PREFIXO DIVIDIDO FICA — 02/10/2026, A-EXCLUSAO-MORA-NA-CAMADA-DO-JOGO-01.**
    O Heroic aceita dois jogos no mesmo `winePrefix`, e o device KS e as camadas
    Vulkan moram no prefixo, não no jogo. Medido num lar de mentira na
    integração: com A e B no mesmo prefixo e só A excluído, a carona do KS
    pulava o prefixo, e B perdia a háptica pelo áudio sem ter sido excluído.
    Por delegação, a validar por ela: o prefixo em que mora alguém que ela não
    excluiu fica com o device KS e as camadas, porque tirar a háptica do jogo
    que ela não excluiu custa mais do que deixá-la no que ela excluiu. O diário
    diz ``exclusao_prefixo_dividido moradores=<n>`` (:func:`_moradores`).
    """
    excluidos: dict[Path, set[str]] = {}
    candidatos: dict[Path, Path] = {}
    for e in ler(config_home):
        for c in e.heroic:
            casa = Path(c.arquivo).parent.parent
            excluidos.setdefault(casa, set()).add(c.app)
            if c.prefixo.strip():
                real = _resolvido(c.prefixo.strip())
                if real is not None:
                    candidatos.setdefault(real, casa)
    fora: set[Path] = set()
    for prefixo, casa in candidatos.items():
        moradores = _moradores(prefixo, casa)
        if moradores <= excluidos.get(casa, set()):
            fora.add(prefixo)
            continue
        dito = (str(prefixo), len(moradores))
        if dito not in _DIVIDIDOS_DITOS:
            _DIVIDIDOS_DITOS.add(dito)
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.utils.logging_config import get_logger

                get_logger(__name__).info(
                    "exclusao_prefixo_dividido", moradores=len(moradores),
                    prefixo=prefixo.name)
    return frozenset(fora)


def ids_dos_prefixos(config_home: Path | None = None) -> list[str]:
    """O que o botão Vulkan pula: o appid na Steam, o caminho resolvido nos outros.

    `camadas_vulkan.curar_todos` compara o appid só com os prefixos de
    `compatdata` e o caminho com os demais (02/10/2026): pelo NOME da pasta, a
    exclusão de um jogo do Heroic pulava também o prefixo de outra casa com a
    mesma pasta. O prefixo dividido não entra (:func:`prefixos_excluidos`).
    """
    caminhos = sorted(str(p) for p in prefixos_excluidos(config_home))
    return list(dict.fromkeys([*appids(config_home), *caminhos]))


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
        for e in _ler_para_o_tique(config_home)
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
    lar: Path | None = None,
) -> str:
    """Exclui o jogo. Status: ``"adicionado"`` | ``"ja_estava"`` |
    ``"chave_invalida"`` | ``"erro"``. Nunca levanta.

    `escritas_herdadas`: listas em que o jogo já estava e que passam a ser
    DESTA exclusão (o «Tirar» sai delas também). Vazio no uso normal.
    `lar`: o `HOME` onde moram o Heroic e as caixas do Flatpak (``None`` = o
    de verdade).
    """
    alvo = chave.strip()
    if not alvo:
        return "chave_invalida"
    destino = caminho(config_home)
    # UM ESCRITOR POR VEZ (02/10/2026): a lista se lê com a trava na mão, e
    # tudo o que a exclusão escreve fica dentro dela (`cpe.trava_da_lista`).
    with cpe.trava_da_lista(destino) as na_mao:
        if not na_mao:
            return "erro"
        return _adicionar_na_trava(
            alvo, destino, lancador=lancador, nome=nome, nota=nota,
            escritas_herdadas=escritas_herdadas, janelas=janelas, lar=lar)


def _adicionar_na_trava(
    alvo: str, destino: Path, *, lancador: str, nome: str, nota: str,
    escritas_herdadas: tuple[str, ...], janelas: tuple[str, ...], lar: Path | None,
) -> str:
    """O corpo de :func:`adicionar`, com a trava na mão."""
    try:
        atuais = _ler_cru(destino)
    except (_ArquivoTortoError, OSError):
        return "erro"
    if any(e.chave == alvo for e in atuais):
        return "ja_estava"

    escritas = list(escritas_herdadas)
    appid = appid_da_chave(alvo)

    def desfazer_as_listas() -> None:
        # Uma escrita que falhou desfaz as que já foram feitas: um jogo meio
        # excluído é o estado que a D-2109-A-EXCLUSAO-E-TUDO-OU-NADA existe
        # para não ter.
        if appid is not None:
            for feita in escritas:
                if feita not in escritas_herdadas:
                    _TIRAR[feita](appid)

    if appid is not None:
        for lista in LISTAS:
            if lista in escritas:
                continue
            status = _POR[lista](appid)
            if status == "adicionado":
                escritas.append(lista)
            elif status != "ja_estava":
                desfazer_as_listas()
                return "erro"

    janelas_limpas = tuple(j.strip() for j in janelas if j.strip())
    # FORA DA STEAM, O AMBIENTE (01/10/2026). O jogo do Heroic com esta janela
    # ganha a lista própria sem o que é nosso; a caixa do emulador perde o
    # ambiente inteiro. Ver `cura_por_estrada`, «A EXCLUSÃO».
    copias: tuple[cpe.CopiaDoJogo, ...] = ()
    ymls: tuple[cpe.YmlDoJogo, ...] = ()
    if appid is not None:
        copias, status = cpe.tirar_o_nosso_do_jogo_do_heroic(alvo, lar=lar)
        if status == "erro":
            desfazer_as_listas()
            return "erro"
        # A CAMADA DO JOGO DO LUTRIS (02/10/2026): o `.yml` do jogo do Lutris
        # Flatpak com esta janela cobre a caixa, que é de todos os jogos dele.
        ymls, status = cpe.tirar_o_nosso_do_jogo_do_lutris(alvo, lar=lar)
        if status == "erro":
            cpe.devolver_ao_jogo_do_heroic(copias)
            desfazer_as_listas()
            return "erro"
    elif e_caixa(alvo) and cpe.tirar_o_nosso_da_caixa(janelas_limpas, lar=lar) == "erro":
        return "erro"

    nova = Entrada(
        chave=alvo, lancador=lancador, nome=nome,
        quando=time.strftime("%Y-%m-%dT%H:%M:%S"), nota=nota,
        escritas=tuple(x for x in LISTAS if x in escritas),
        janelas=janelas_limpas,
        heroic=copias,
        lutris=ymls,
    )
    try:
        _gravar(destino, [*atuais, nova])
    except OSError:
        desfazer_as_listas()
        cpe.devolver_ao_jogo_do_heroic(copias)
        cpe.devolver_ao_jogo_do_lutris(ymls)
        return "erro"
    return "adicionado"


def tirar(chave: str, *, config_home: Path | None = None, lar: Path | None = None) -> str:
    """Devolve o jogo ao Hefesto. Status: ``"removido"`` | ``"nao_estava"`` |
    ``"erro"``. Nunca levanta.

    Sai SÓ das listas em que esta exclusão escreveu (``Entrada.escritas``): uma
    linha que já era dela antes da exclusão continua lá.
    """
    alvo = chave.strip()
    destino = caminho(config_home)
    with cpe.trava_da_lista(destino) as na_mao:
        return _tirar_na_trava(alvo, destino, lar) if na_mao else "erro"


def _tirar_na_trava(alvo: str, destino: Path, lar: Path | None) -> str:
    """O corpo de :func:`tirar`, com a trava na mão (a carona entra nela)."""
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
    if cpe.devolver_ao_jogo_do_heroic(achada.heroic) == "erro":
        return "erro"
    if cpe.devolver_ao_jogo_do_lutris(achada.lutris) == "erro":
        return "erro"
    try:
        _gravar(destino, [e for e in atuais if e.chave != alvo])
    except OSError:
        return "erro"
    if e_caixa(alvo):
        # A caixa volta pela carona: fora da lista, ela recebe o ambiente de
        # agora — e, sem o ambiente publicado, na próxima transição.
        cpe.curar_todas_as_estradas(lar=lar)
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
    # O PREFIXO DIVIDIDO FICA (02/10/2026): só sai o prefixo em que todo
    # morador está excluído — a mesma regra da carona do device KS.
    inteiros = prefixos_excluidos()
    do_heroic = [Path(c.prefixo) for e in ler() if e.chave == chave.strip()
                 for c in e.heroic if c.prefixo.strip()
                 and _resolvido(c.prefixo.strip()) in inteiros]
    prefixo = _devolver_o_prefixo(appid, do_heroic)
    razoes = {str(e.get("reason", "")) for e in atalho["errors"]}
    if pino.get("status") == "recusado" or razoes & _ESPERA_A_STEAM or prefixo == "ocupado":
        return "espera_a_steam"
    if pino.get("status") == "erro" or atalho["errors"] or prefixo == "erro":
        return "erro"
    if pino.get("status") == "destravado" or atalho["removed"] or prefixo == "feito":
        return "feito"
    return "nada_a_tirar"


def _devolver_o_prefixo(appid: str, do_heroic: list[Path] | None = None) -> str:
    """O prefixo Wine do jogo volta ao que era sem o Hefesto.

    Duas coisas moram lá, e as duas são nossas: o device KS da háptica
    (`audio_ks_dualsense`) e as camadas Vulkan que a cura desligou
    (`camadas_vulkan`). O KS sai inteiro; as camadas voltam a ligar SÓ as que
    nós desligamos, sem virar escolha dela (``pela_exclusao``). Os prefixos
    são o `compatdata/<appid>` da Steam e, em ``do_heroic``, o prefixo próprio
    do mesmo jogo no Heroic.

    Com o jogo aberto o `wineserver` regravaria o registro ao sair, e a edição
    seria perdida: ``"ocupado"``. Status: ``"feito"`` | ``"nada"`` |
    ``"ocupado"`` | ``"erro"``. Nunca levanta.
    """
    from hefesto_dualsense4unix.integrations import audio_ks_dualsense as ks
    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

    status = "nada"
    raizes = [(pasta / appid, appid) for pasta in cv.pastas_compatdata()]
    raizes += [(raiz, raiz.name) for raiz in (do_heroic or [])]
    for raiz, nome in raizes:
        if not (raiz / "pfx" / "system.reg").is_file():
            continue
        if ks.wineserver_do_prefixo_vivo(raiz / "pfx"):
            return "ocupado"
        try:
            tirado = ks.aplicar(raiz, controles=[])
            camadas = cv.aplicar_no_prefixo(
                cv.prefixo_de_jogo(raiz, appid=nome), religar=True, pela_exclusao=True
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
    "PREFIXO_DO_EMULADOR",
    "Entrada",
    "adicionar",
    "appid_da_chave",
    "appids",
    "caminho",
    "contem",
    "e_caixa",
    "ids_dos_prefixos",
    "ler",
    "o_que_a_carona_pula",
    "prefixos_excluidos",
    "tirar",
    "tirar_do_disco",
]
