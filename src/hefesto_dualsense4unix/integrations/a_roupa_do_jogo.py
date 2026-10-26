"""A roupa do pad para UM jogo, por uma regra só (docs/protocol/a-identidade-do-pad-virtual.md).

`roupa_do_jogo(raiz) -> (roupa, fonte)`: o pad veste o `0ce6` só quando o jogo nomeia o
DualSense comum, não nomeia o Edge e nada no caminho dele pede o que só o Edge tem (o
contêiner USB do gadget, que a biblioteca Sony procura; o pad Sony, que o Modo Xbox e o Steam
Input não mostram ao jogo; o PID que a Launch Option dele não esconde). Em todo outro caso,
o Edge. O que o jogo nomeia se lê no disco (D-2210-A-ROUPA-DO-PAD-SE-LE-NO-BINARIO), em
cache pela assinatura dos arquivos; a regra é `_a_regra`, e nunca troca máscara nem perfil.
"""
from __future__ import annotations

import logging
import mmap
import os
import re
import threading
import time
from collections.abc import Callable, Collection
from dataclasses import dataclass
from pathlib import Path

try:
    from .api_de_entrada import escolher_executavel
    from .ficha_declarada import _bibliotecas_e_manifesto, _grafias, _ler_o_arquivo
    from .steam_launch_options import (
        discover_vdfs,
        has_poison,
        is_sandboxed_layout,
        read_launch_options_by_appid,
    )
except ImportError:  # pragma: no cover
    from api_de_entrada import escolher_executavel  # type: ignore[no-redef]
    from ficha_declarada import (  # type: ignore[no-redef]
        _bibliotecas_e_manifesto,
        _grafias,
        _ler_o_arquivo,
    )
    from steam_launch_options import (  # type: ignore[no-redef]
        discover_vdfs,
        has_poison,
        is_sandboxed_layout,
        read_launch_options_by_appid,
    )

logger = logging.getLogger(__name__)

ROUPA_DO_EDGE = "0df2"
ROUPA_DO_COMUM = "0ce6"

_NOME_DO_PERFIL = re.compile(rb"PlayStation5|DualSense")
_LETRAS_DE_NOME = frozenset(
    b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
)
_DUALSENSE_EDGE = _grafias("DualSense Edge")
_SONY_DUALSENSE = _grafias("Sony DualSense")
_DO_INCONTROL = frozenset({"global-metadata.dat", "incontrol.dll"})
_DA_SDL = frozenset({"sdl2.dll", "sdl3.dll"})
_DO_REWIRED = "rewired_core.dll"


@dataclass(frozen=True)
class _Declarado:
    """O que o disco do jogo nomeia do controle; cada campo é a fonte, ou `None`."""

    edge: str | None = None
    comum: str | None = None
    sony: str | None = None


_Chave = tuple[tuple[str, int, int], ...]
_CACHE: dict[str, tuple[_Chave, _Declarado]] = {}
_LIDO_EM: dict[str, int] = {}
_MARGEM_NS = 2 * 10**9
_TRAVA_DO_CACHE = threading.Lock()
_AQUECENDO = threading.Event()


def _perfis_do_incontrol(mapa: mmap.mmap) -> tuple[bool, bool]:
    """`(edge, comum)` dos nomes `…Profile` com `PlayStation5` ou `DualSense`, fora os `Hori…`."""
    comum = False
    for casou in _NOME_DO_PERFIL.finditer(mapa):
        inicio, fim = casou.start(), casou.end()
        while inicio > 0 and mapa[inicio - 1] in _LETRAS_DE_NOME:
            inicio -= 1
        while fim < len(mapa) and mapa[fim] in _LETRAS_DE_NOME:
            fim += 1
        nome = mapa[inicio:fim]
        if not nome.endswith(b"Profile") or nome.startswith(b"Hori"):
            continue
        if b"Edge" in nome:
            return True, comum
        comum = True
    return False, comum


def _tem(mapa: mmap.mmap, agulhas: tuple[bytes, ...]) -> bool:
    return any(mapa.find(a) != -1 for a in agulhas)


def _sinais_do_arquivo(arquivo: Path, *, rewired: bool) -> tuple[bool, bool]:
    """`(edge, comum)` que UM arquivo da roupa declara; nada se ele não se lê."""
    nome = arquivo.name.lower()
    try:
        if arquivo.stat().st_size == 0:
            return False, False
        with (
            arquivo.open("rb") as fh,
            mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as mapa,
        ):
            if nome in _DO_INCONTROL:
                return _perfis_do_incontrol(mapa)
            if nome in _DA_SDL or nome == _DO_REWIRED:
                return _tem(mapa, _DUALSENSE_EDGE), False
            if not rewired:
                return False, False
            if _tem(mapa, _DUALSENSE_EDGE):
                return True, False
            return False, _tem(mapa, _SONY_DUALSENSE)
    except (OSError, ValueError):
        return False, False


def _ler_o_disco(raiz: Path) -> tuple[_Declarado, list[Path]]:
    """O que o jogo nomeia, pela leitura do disco, e o que se olhou (a chave do cache).

    O que se olhou são as subpastas por onde a varredura andou e os arquivos lidos.
    """
    roupa: list[Path] = []
    pastas: list[Path] = []
    bibliotecas, _gdk = _bibliotecas_e_manifesto(raiz, roupa, pastas)
    executavel = escolher_executavel(raiz)
    lidos = (
        sorted(pastas) + sorted(roupa) + bibliotecas
        + ([executavel] if executavel is not None else [])
    )
    rewired = any(p.name.lower() == _DO_REWIRED for p in roupa)
    edge: str | None = None
    comum: str | None = None
    for arquivo in sorted(roupa):
        do_edge, do_comum = _sinais_do_arquivo(arquivo, rewired=rewired)
        relativo = _relativo(arquivo, raiz)
        if do_edge and edge is None:
            edge = f"{relativo} declara o DualSense Edge"
        if do_comum and comum is None:
            comum = f"{relativo} declara só o DualSense comum"
    sony: set[str] = {"libScePad"} if bibliotecas else set()
    pids: set[str] = set()
    for arquivo in bibliotecas + ([executavel] if executavel is not None else []):
        do_arquivo, dos_pids = _ler_o_arquivo(arquivo)
        sony |= do_arquivo
        pids |= dos_pids
    if edge is None and ROUPA_DO_EDGE in pids:
        edge = "o executável conhece o modelo 0DF2 do Edge"
    if comum is None and ROUPA_DO_COMUM in pids:
        comum = "o executável conhece só o modelo 0CE6 do DualSense comum"
    da_sony = f"a biblioteca Sony ({', '.join(sorted(sony))}) pede o Edge de hoje" if sony else None
    return _Declarado(edge=edge, comum=comum, sony=da_sony), lidos


def _o_caminho_pede_o_edge(
    opcoes_de_lancamento: str, no_steam_input: bool, modo_xbox: bool
) -> str | None:
    """Por que o caminho do jogo até o pad não mostra o `0ce6`; `None` se ele mostra."""
    if modo_xbox:
        return "o Modo Xbox não veste roupa Sony"
    if no_steam_input:
        return "o jogo está na lista do Steam Input"
    if opcoes_de_lancamento and has_poison(opcoes_de_lancamento):
        return "a Launch Option do jogo esconde o 0CE6 do SDL"
    return None


def _a_regra(declarado: _Declarado, caminho: str | None) -> tuple[str, str]:
    """A regra única: o `0ce6` onde ele é o único modelo que serve ao jogo; senão, o Edge."""
    pede_o_edge = caminho or declarado.edge or declarado.sony
    if declarado.comum is not None and pede_o_edge is None:
        return ROUPA_DO_COMUM, declarado.comum
    return ROUPA_DO_EDGE, pede_o_edge or "nenhum sinal do controle: o Edge de hoje"


def _relativo(arquivo: Path, raiz: Path) -> str:
    try:
        return str(arquivo.relative_to(raiz))
    except ValueError:
        return arquivo.name


def _chave(raiz: Path, lidos: list[Path]) -> _Chave:
    """O caminho, o tamanho e o `mtime` da raiz, das subpastas visitadas e de cada arquivo lido."""
    chave: list[tuple[str, int, int]] = []
    for caminho in [raiz, *lidos]:
        try:
            st = os.stat(caminho)
        except OSError:
            chave.append((str(caminho), -1, -1))
            continue
        chave.append((str(caminho), st.st_size, st.st_mtime_ns))
    return tuple(chave)


def _agora_ns() -> int:
    """O relógio com que os `mtime` dos arquivos se comparam (o de parede, em ns)."""
    return time.time_ns()


def _a_releitura_venceu(chave: _Chave, comecou: int | None) -> bool:
    """A leitura é suspeita (um `mtime` a menos de uma margem do começo dela) e a margem já passou?

    Num disco de tempo grosso, o arquivo que muda no mesmo tique deixa a chave igual. Enquanto a
    margem corre, a leitura guardada serve (é o melhor que se sabe); passada ela, vale UMA nova.
    """
    if comecou is None:
        return False
    suspeitos = [m for _c, _t, m in chave if m >= comecou - _MARGEM_NS]
    return bool(suspeitos) and _agora_ns() > max(suspeitos) + _MARGEM_NS


def _do_cache(raiz: Path) -> tuple[_Declarado | None, bool]:
    """A leitura guardada, se nada mudou desde então, e se ela pede uma releitura.

    Sem leitura útil: `(None, False)`. Com ela: `(declarado, a_reler)`, e quem não pode esperar
    o disco usa o `declarado` assim mesmo.
    """
    with _TRAVA_DO_CACHE:
        guardado = _CACHE.get(str(raiz))
        comecou = _LIDO_EM.get(str(raiz))
    if guardado is None:
        return None, False
    chave, declarado = guardado
    if _chave(raiz, [Path(c) for c, _t, _m in chave[1:]]) != chave:
        return None, False
    return declarado, _a_releitura_venceu(chave, comecou)


def _o_que_o_jogo_declara(raiz: Path, *, so_o_cache: bool) -> tuple[_Declarado | None, bool]:
    """`(declarado, a_reler)`: o que o jogo nomeia e se o cache pede leitura nova, fora do laço."""
    declarado, a_reler = _do_cache(raiz)
    if so_o_cache or (declarado is not None and not a_reler):
        return declarado, a_reler
    comecou = _agora_ns()
    declarado, lidos = _ler_o_disco(raiz)
    with _TRAVA_DO_CACHE:
        _CACHE[str(raiz)] = (_chave(raiz, lidos), declarado)
        _LIDO_EM[str(raiz)] = comecou
    return declarado, False


def _a_roupa(
    raiz: Path, opcoes_de_lancamento: str, no_steam_input: bool, modo_xbox: bool,
    *, so_o_cache: bool,
) -> tuple[tuple[str, str] | None, bool]:
    """`(roupa, a_reler)`; a roupa é `None` se o cache não tem o jogo e o caminho nada decide."""
    caminho = _o_caminho_pede_o_edge(opcoes_de_lancamento, no_steam_input, modo_xbox)
    declarado, a_reler = _o_que_o_jogo_declara(raiz, so_o_cache=so_o_cache)
    if declarado is None and caminho is None:
        return None, a_reler
    return _a_regra(declarado or _Declarado(), caminho), a_reler


def roupa_do_jogo(
    raiz: Path,
    *,
    opcoes_de_lancamento: str = "",
    no_steam_input: bool = False,
    modo_xbox: bool = False,
) -> tuple[str, str]:
    """`(roupa, fonte)` de UM jogo, pela `_a_regra`."""
    caminho = _o_caminho_pede_o_edge(opcoes_de_lancamento, no_steam_input, modo_xbox)
    declarado, _a_reler = _o_que_o_jogo_declara(raiz, so_o_cache=False)
    return _a_regra(declarado or _Declarado(), caminho)


def _aquecer(raizes: list[Path], ao_aquecer: Callable[[], None] | None) -> None:
    """Lê, fora do laço, os jogos que o cache ainda não tem, e avisa quem pediu."""
    try:
        for raiz in raizes:
            try:
                roupa_do_jogo(raiz)
            except Exception:
                logger.debug("a roupa de %s não aqueceu", raiz, exc_info=True)
    finally:
        _AQUECENDO.clear()
    if ao_aquecer is not None:
        ao_aquecer()


def _opcoes_de_lancamento(home: Path | None) -> dict[str, str]:
    opcoes: dict[str, str] = {}
    for vdf in discover_vdfs(home):
        if is_sandboxed_layout(vdf):
            continue
        try:
            texto = vdf.read_text(encoding="utf-8", errors="replace")
        except OSError as erro:
            logger.debug("as Launch Options não se leram: %s: %s", vdf, erro)
            continue
        for appid, valor in read_launch_options_by_appid(texto).items():
            opcoes.setdefault(appid, valor)
    return opcoes


def roupas_dos_jogos(
    home: Path | None = None,
    *,
    steam_input: Collection[object] = (),
    modo_xbox: bool = False,
    so_o_cache: bool = False,
    ao_aquecer: Callable[[], None] | None = None,
) -> dict[str, tuple[str, str]]:
    """`{appid: (roupa, fonte)}` dos jogos instalados com pasta em disco.

    Com `so_o_cache` (o laço do serviço, que não espera disco), o jogo que o cache
    não tem fica de fora (o Edge de hoje) e é lido num fio próprio, que chama
    `ao_aquecer` no fim; o jogo de leitura suspeita já passada a margem segue com a roupa
    guardada e ganha uma releitura nesse mesmo fio.
    """
    try:
        from .prontuario_dos_jogos import jogos_instalados
    except ImportError:  # pragma: no cover
        from prontuario_dos_jogos import jogos_instalados  # type: ignore[no-redef]
    na_lista = {str(a) for a in steam_input}
    opcoes = _opcoes_de_lancamento(home)
    roupas: dict[str, tuple[str, str]] = {}
    frios: list[Path] = []
    for appid, _nome, raiz in jogos_instalados(home):
        if raiz is None:
            continue
        resposta, a_reler = _a_roupa(
            raiz, opcoes.get(appid, ""), appid in na_lista, modo_xbox, so_o_cache=so_o_cache
        )
        if resposta is not None:
            roupas[appid] = resposta
        if resposta is None or a_reler:
            frios.append(raiz)
    if frios and not _AQUECENDO.is_set():
        _AQUECENDO.set()
        threading.Thread(
            target=_aquecer, args=(frios, ao_aquecer), name="hefesto-roupa", daemon=True
        ).start()
    return roupas


__all__ = ["ROUPA_DO_COMUM", "ROUPA_DO_EDGE", "roupa_do_jogo", "roupas_dos_jogos"]
