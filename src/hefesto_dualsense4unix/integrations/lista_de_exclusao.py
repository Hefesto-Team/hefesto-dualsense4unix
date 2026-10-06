"""A lista de exclusão do Hefesto — OS-LANCADORES-IGUAIS-E-A-LISTA-DE-EXCLUSAO-01.

**O QUE ELA É, em uma frase (a do §3 da sprint):** o jogo que está aqui vê o
controle como se o Hefesto não estivesse instalado.

O pedido é de produto, 21/09/2026, olhando a aba Lançadores: *"(...) Adicionar jogo a
lista de exclusão do Hefesto (cujo objetivo é garantir que tal jogo não use
nenhuma feature do hefesto)"*. <!-- noqa-acento: citação literal -->

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
dispositivo»). O rótulo é anterior à decisão de 09/08/2026
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
Se o jogo já estava numa das duas por escolha do usuário antes de ser excluído, ele
continua lá depois do «Tirar». Quem diz de quem era a linha é o próprio dono:
``"adicionado"`` quer dizer que a escrita foi nossa; ``"ja_estava"`` quer dizer
que era do usuário. A entrada guarda só as listas em que NÓS escrevemos
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
from typing import TYPE_CHECKING

from hefesto_dualsense4unix.core import o_dono_do_evento as _ode
from hefesto_dualsense4unix.integrations import cura_por_estrada as cpe
from hefesto_dualsense4unix.integrations import proton_pin
from hefesto_dualsense4unix.integrations import steam_launch_options as slo
from hefesto_dualsense4unix.utils.leitura_pela_assinatura import LeituraPelaAssinatura

if TYPE_CHECKING:
    from hefesto_dualsense4unix.integrations.censo_dos_lancadores import BibliotecaDoLancador

RELPATH = "hefesto-dualsense4unix/lista_de_exclusao.json"
FORMATO = 1

LISTAS: tuple[str, ...] = ("pino", "atalho")

NOTA_DAS_LISTAS = "posto pela lista de exclusão do Hefesto"

_STEAM_APP = re.compile(r"^steam_app_(\d+)$")

PREFIXO_DO_EMULADOR = "emulador:"


def caminho(config_home: Path | None = None) -> Path:
    """``$XDG_CONFIG_HOME/hefesto-dualsense4unix/lista_de_exclusao.json``."""
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
    escritas: tuple[str, ...] = field(default_factory=tuple)
    janelas: tuple[str, ...] = field(default_factory=tuple)
    heroic: tuple[cpe.CopiaDoJogo, ...] = field(default_factory=tuple)
    lutris: tuple[cpe.YmlDoJogo, ...] = field(default_factory=tuple)


_POR: dict[str, Callable[[str], str]] = {
    "pino": lambda a: proton_pin.nomear_fora_do_pino(a, nota=NOTA_DAS_LISTAS),
    "atalho": lambda a: slo.marcar_jogo_sem_wrapper(a, nota=NOTA_DAS_LISTAS),
}
_TIRAR: dict[str, Callable[[str], str]] = {
    "pino": proton_pin.devolver_ao_pino,
    "atalho": slo.desmarcar_jogo_sem_wrapper,
}


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
    """A entrada como vai ao JSON — sem a chave ``heroic`` quando vazia."""
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
    """O que `cura_por_estrada.curar_todas_as_estradas` não escreve."""
    entradas = ler(config_home)
    return cpe.NaExclusao(
        caixas=frozenset(j.casefold() for e in entradas if e_caixa(e.chave)
                         for j in e.janelas),
        copias=tuple(c for e in entradas for c in e.heroic),
        ymls=tuple(y for e in entradas for y in e.lutris))


def anotar_os_ymls(ymls: Iterable[cpe.YmlDoJogo], config_home: Path | None = None) -> str:
    """A carona escreveu de novo nestes `.yml`: o registro da volta acompanha."""
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


_MORADORES_DO_HEROIC = "installed_games"

_DIVIDIDOS_DITOS: set[tuple[str, int, bool]] = set()


def _resolvido(caminho: str | Path) -> Path | None:
    try:
        return Path(caminho).expanduser().resolve()
    except (OSError, RuntimeError):  # pragma: no cover - caminho impossível
        return None


def _o_censo_do_heroic(casa: Path) -> BibliotecaDoLancador | None:
    """A biblioteca que o censo lê nesta casa do Heroic; ``None`` = o censo levantou."""
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

    try:
        return censo._heroic(casa)
    except Exception:
        return None


def _responde_pelo_instalado(biblioteca: BibliotecaDoLancador | None) -> bool:
    """O censo leu jogo e voltou sem erro: só então ele TIRA morador."""
    return biblioteca is not None and bool(biblioteca.jogos) and not biblioteca.erros


def _moradores(prefixo: Path, casa: Path) -> set[str]:
    """Os `app_name` dos jogos do Heroic que moram neste prefixo (resolvido)."""
    return _moradores_e_o_censo(prefixo, casa)[0]


def _moradores_e_o_censo(prefixo: Path, casa: Path) -> tuple[set[str], bool]:
    """``(os moradores deste prefixo, o censo leu)``."""
    biblioteca = _o_censo_do_heroic(casa)
    leu = _responde_pelo_instalado(biblioteca)
    desinstalados = ({j.chave for j in biblioteca.jogos if not j.instalado}
                     if leu and biblioteca is not None else set())
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
    if e_o_global and biblioteca is not None:
        fora.update(j.chave for j in biblioteca.jogos
                    if j.instalado and j.chave not in com_copia)
    return fora - desinstalados, leu


def prefixos_excluidos(config_home: Path | None = None) -> frozenset[Path]:
    """Os prefixos dos jogos excluídos do Heroic em que TODO morador está excluído."""
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
        moradores, leu = _moradores_e_o_censo(prefixo, casa)
        if moradores <= excluidos.get(casa, set()):
            fora.add(prefixo)
            continue
        dito = (str(prefixo), len(moradores), leu)
        if dito not in _DIVIDIDOS_DITOS:
            _DIVIDIDOS_DITOS.add(dito)
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.utils.logging_config import get_logger

                campos: dict[str, object] = {"moradores": len(moradores),
                                             "prefixo": prefixo.name}
                if not leu:
                    campos["sem_censo"] = 1
                get_logger(__name__).info("exclusao_prefixo_dividido", **campos)
    return frozenset(fora)


def ids_dos_prefixos(config_home: Path | None = None) -> list[str]:
    """O que o botão Vulkan pula: o appid na Steam, o caminho resolvido nos outros."""
    caminhos = sorted(str(p) for p in prefixos_excluidos(config_home))
    return list(dict.fromkeys([*appids(config_home), *caminhos]))


def appids(config_home: Path | None = None) -> list[str]:
    """Os appids da Steam (e do umu) excluídos — o que os donos por appid leem."""
    return [a for a in (appid_da_chave(e.chave) for e in ler(config_home)) if a]


def contem(chave: str, config_home: Path | None = None) -> bool:
    """Esta classe de janela está excluída — pela chave ou por uma das janelas?"""
    alvo = chave.strip()
    if not alvo:
        return False
    dobrado = alvo.casefold()
    return any(
        e.chave == alvo or any(j.casefold() == dobrado for j in e.janelas)
        for e in _ler_para_o_tique(config_home)
    )


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
    """Exclui o jogo. Status: ``"adicionado"`` | ``"ja_estava"`` |"""
    alvo = chave.strip()
    if not alvo:
        return "chave_invalida"
    destino = caminho(config_home)
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
    copias: tuple[cpe.CopiaDoJogo, ...] = ()
    ymls: tuple[cpe.YmlDoJogo, ...] = ()
    if appid is not None:
        copias, status = cpe.tirar_o_nosso_do_jogo_do_heroic(alvo, lar=lar)
        if status == "erro":
            desfazer_as_listas()
            return "erro"
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
    """Devolve o jogo ao Hefesto. Status: ``"removido"`` | ``"nao_estava"`` |"""
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
        cpe.curar_todas_as_estradas(lar=lar)
    return "removido"


_ESPERA_A_STEAM = frozenset({"steam_aberta", "jogo_da_steam_aberto"})


def tirar_do_disco(chave: str) -> str:
    """Tira do jogo o pino, o atalho e o que o Hefesto pôs no prefixo dele."""
    appid = appid_da_chave(chave)
    if appid is None:
        return "sem_appid"
    pino = proton_pin.destravar_um_jogo(appid)
    atalho = slo.tirar_o_atalho_dos_jogos([appid])
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
    """O prefixo Wine do jogo volta ao que era sem o Hefesto."""
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
