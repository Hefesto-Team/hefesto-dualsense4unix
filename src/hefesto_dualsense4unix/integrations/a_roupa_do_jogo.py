"""A roupa do pad para UM jogo: o DualSense que o binário dele declara conhecer.

`roupa_do_jogo(raiz) -> (roupa, fonte)` (D-2210-A-ROUPA-DO-PAD-SE-LE-NO-BINARIO), em ordem: o
sinal do Edge em qualquer arquivo ganha; a biblioteca Sony (a háptica do Sackboy) pede o Edge;
o sinal só do comum veste o `0ce6`; sem sinal, o Edge de hoje. A Launch Option que esconde o
`0ce6`, o Steam Input e o Modo Xbox ficam no Edge. Lê o que o varredor da `ficha_declarada`
acha, em cache pela assinatura dos arquivos, e nunca troca máscara nem perfil.
"""
from __future__ import annotations

import logging
import mmap
import os
import re
import threading
from collections.abc import Callable, Collection
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
except ImportError:  # pragma: no cover - executado como script avulso
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

#: As duas roupas, como o `numeros_da_sony` as nomeia (aqui em texto: o módulo roda avulso).
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

_Chave = tuple[tuple[str, int, int], ...]
_CACHE: dict[str, tuple[_Chave, tuple[str, str]]] = {}
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


def _ler_a_roupa(raiz: Path) -> tuple[tuple[str, str], list[Path]]:
    """A roupa pela leitura do disco, e os arquivos lidos (a chave do cache)."""
    roupa: list[Path] = []
    bibliotecas, _gdk = _bibliotecas_e_manifesto(raiz, roupa)
    executavel = escolher_executavel(raiz)
    lidos = sorted(roupa) + bibliotecas + ([executavel] if executavel is not None else [])
    rewired = any(p.name.lower() == _DO_REWIRED for p in roupa)
    comum: str | None = None
    for arquivo in sorted(roupa):
        edge, do_comum = _sinais_do_arquivo(arquivo, rewired=rewired)
        relativo = _relativo(arquivo, raiz)
        if edge:
            return (ROUPA_DO_EDGE, f"{relativo} declara o DualSense Edge"), lidos
        if do_comum and comum is None:
            comum = f"{relativo} declara só o DualSense comum"
    sony: set[str] = {"libScePad"} if bibliotecas else set()
    pids: set[str] = set()
    for arquivo in bibliotecas + ([executavel] if executavel is not None else []):
        do_arquivo, dos_pids = _ler_o_arquivo(arquivo)
        sony |= do_arquivo
        pids |= dos_pids
    if ROUPA_DO_EDGE in pids:
        return (ROUPA_DO_EDGE, "o executável conhece o modelo 0DF2 do Edge"), lidos
    if sony:
        fonte = f"a biblioteca Sony ({', '.join(sorted(sony))}) pede o Edge de hoje"
        return (ROUPA_DO_EDGE, fonte), lidos
    if comum is None and ROUPA_DO_COMUM in pids:
        comum = "o executável conhece só o modelo 0CE6 do DualSense comum"
    if comum is not None:
        return (ROUPA_DO_COMUM, comum), lidos
    return (ROUPA_DO_EDGE, "nenhum sinal do controle: o Edge de hoje"), lidos


def _relativo(arquivo: Path, raiz: Path) -> str:
    try:
        return str(arquivo.relative_to(raiz))
    except ValueError:
        return arquivo.name


def _chave(raiz: Path, lidos: list[Path]) -> _Chave:
    """O caminho, o tamanho e o `mtime` da pasta e de cada arquivo lido."""
    chave: list[tuple[str, int, int]] = []
    for caminho in [raiz, *lidos]:
        try:
            st = os.stat(caminho)
        except OSError:
            chave.append((str(caminho), -1, -1))
            continue
        chave.append((str(caminho), st.st_size, st.st_mtime_ns))
    return tuple(chave)


def _do_cache(raiz: Path) -> tuple[str, str] | None:
    """A resposta guardada, se nenhum arquivo lido mudou desde então."""
    with _TRAVA_DO_CACHE:
        guardado = _CACHE.get(str(raiz))
    if guardado is None:
        return None
    chave, resposta = guardado
    if _chave(raiz, [Path(c) for c, _t, _m in chave[1:]]) != chave:
        return None
    return resposta


def _a_roupa(
    raiz: Path, opcoes_de_lancamento: str, no_steam_input: bool, modo_xbox: bool,
    *, so_o_cache: bool,
) -> tuple[str, str] | None:
    if modo_xbox:
        return ROUPA_DO_EDGE, "o Modo Xbox não veste roupa Sony"
    if no_steam_input:
        return ROUPA_DO_EDGE, "o jogo está na lista do Steam Input"
    if opcoes_de_lancamento and has_poison(opcoes_de_lancamento):
        return ROUPA_DO_EDGE, "a Launch Option do jogo esconde o 0CE6 do SDL"
    resposta = _do_cache(raiz)
    if resposta is not None or so_o_cache:
        return resposta
    resposta, lidos = _ler_a_roupa(raiz)
    with _TRAVA_DO_CACHE:
        _CACHE[str(raiz)] = (_chave(raiz, lidos), resposta)
    return resposta


def roupa_do_jogo(
    raiz: Path,
    *,
    opcoes_de_lancamento: str = "",
    no_steam_input: bool = False,
    modo_xbox: bool = False,
) -> tuple[str, str]:
    """`(roupa, fonte)` de UM jogo: `0ce6` só com o sinal do comum e sem o do Edge."""
    resposta = _a_roupa(
        raiz, opcoes_de_lancamento, no_steam_input, modo_xbox, so_o_cache=False
    )
    return resposta if resposta is not None else (ROUPA_DO_EDGE, "")


def _aquecer(raizes: list[Path], ao_aquecer: Callable[[], None] | None) -> None:
    """Lê, fora do laço, os jogos que o cache ainda não tem, e avisa quem pediu."""
    try:
        for raiz in raizes:
            roupa_do_jogo(raiz)
    except Exception:
        logger.debug("a roupa dos jogos não aqueceu", exc_info=True)
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
    `ao_aquecer` no fim.
    """
    try:
        from .prontuario_dos_jogos import jogos_instalados
    except ImportError:  # pragma: no cover - executado como script avulso
        from prontuario_dos_jogos import jogos_instalados  # type: ignore[no-redef]
    na_lista = {str(a) for a in steam_input}
    opcoes = _opcoes_de_lancamento(home)
    roupas: dict[str, tuple[str, str]] = {}
    frios: list[Path] = []
    for appid, _nome, raiz in jogos_instalados(home):
        if raiz is None:
            continue
        resposta = _a_roupa(
            raiz, opcoes.get(appid, ""), appid in na_lista, modo_xbox, so_o_cache=so_o_cache
        )
        if resposta is None:
            frios.append(raiz)
        else:
            roupas[appid] = resposta
    if frios and not _AQUECENDO.is_set():
        _AQUECENDO.set()
        threading.Thread(
            target=_aquecer, args=(frios, ao_aquecer), name="hefesto-roupa", daemon=True
        ).start()
    return roupas


__all__ = ["ROUPA_DO_COMUM", "ROUPA_DO_EDGE", "roupa_do_jogo", "roupas_dos_jogos"]
