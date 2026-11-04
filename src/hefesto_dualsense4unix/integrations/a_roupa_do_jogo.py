"""A roupa do pad para UM jogo, por uma regra só (docs/protocol/a-identidade-do-pad-virtual.md).

`roupa_do_jogo(raiz) -> (roupa, fonte)`: o pad veste o Edge só quando o caminho do jogo pede o
que só o Edge tem (o contêiner USB do gadget, que a biblioteca Sony procura; o pad Sony, que o
Modo Xbox e o Steam Input não mostram ao jogo; o PID que a Launch Option dele não esconde) ou
quando o jogo conhece o Edge e não conhece o comum. Em todo outro caso (o jogo que conhece os
dois modelos, só o comum ou nenhum), o DualSense comum (`0ce6`), que todo jogo do DualSense
conhece. O que o jogo conhece se lê no disco (D-2210-A-ROUPA-DO-PAD-SE-LE-NO-BINARIO), em cache
pela assinatura dos arquivos; a regra é `_a_regra`, e nunca troca máscara nem perfil.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable, Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .api_de_entrada import escolher_executavel
    from .ficha_declarada import (
        _bibliotecas_e_manifesto,
        _grafias,
        _gravar_no_disco,
        _guardado_no_disco,
        _janelas,
        _lote,
        _sinais_guardados,
    )
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
        _gravar_no_disco,
        _guardado_no_disco,
        _janelas,
        _lote,
        _sinais_guardados,
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

_NOMES_DO_PERFIL = (b"PlayStation5", b"DualSense")
_LETRAS_DE_NOME = frozenset(
    b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
)
_DUALSENSE_EDGE = _grafias("DualSense Edge")
_DUALSENSE_COMUM = _grafias("DualSense Wireless Controller")
_SONY_DUALSENSE = "Sony DualSense"
_SUFIXO_DO_EDGE = " Edge"
_DO_INCONTROL = frozenset({"global-metadata.dat", "incontrol.dll"})
_DA_SDL = frozenset({"sdl2.dll", "sdl3.dll"})
_DO_REWIRED = "rewired_core.dll"


@dataclass(frozen=True)
class _Declarado:
    """O que o disco do jogo conhece do controle.

    `edge` e `comum` dizem QUEM conhece cada modelo (o arquivo ou o executável), ou `None`;
    `sony` é a frase da biblioteca Sony, ou `None`.
    """

    edge: str | None = None
    comum: str | None = None
    sony: str | None = None


_Chave = tuple[tuple[str, int, int], ...]
_CACHE: dict[str, tuple[_Chave, _Declarado]] = {}
_LIDO_EM: dict[str, int] = {}
_MARGEM_NS = 2 * 10**9
_TRAVA_DO_CACHE = threading.Lock()
_AQUECENDO = threading.Event()
_NOME_NO_DISCO = "roupa-dos-jogos.json"


def _perfis_da_janela(janela: bytes, ultima: bool) -> tuple[bool, bool]:
    """`(edge, comum)` dos nomes `…Profile` com `PlayStation5` ou `DualSense`, fora os `Hori…`.

    O nome que encosta no fim de uma janela que não é a última fica para a seguinte, que o traz
    inteiro na sobra.
    """
    edge = comum = False
    for agulha in _NOMES_DO_PERFIL:
        posicao = janela.find(agulha)
        while posicao != -1:
            inicio, fim = posicao, posicao + len(agulha)
            while inicio > 0 and janela[inicio - 1] in _LETRAS_DE_NOME:
                inicio -= 1
            while fim < len(janela) and janela[fim] in _LETRAS_DE_NOME:
                fim += 1
            nome = janela[inicio:fim]
            if (fim < len(janela) or ultima) and nome.endswith(b"Profile") and not (
                nome.startswith(b"Hori")
            ):
                if b"Edge" in nome:
                    edge = True
                else:
                    comum = True
                if edge and comum:
                    return edge, comum
            posicao = janela.find(agulha, fim)
    return edge, comum


def _tem(janela: bytes, agulhas: tuple[bytes, ...]) -> bool:
    return any(a in janela for a in agulhas)


def _nomeia_sem_o_edge(janela: bytes, ultima: bool, nome: str) -> bool:
    """O `nome` aparece, em ASCII ou em UTF-16, ao menos uma vez sem o ` Edge` logo depois."""
    for codificacao in ("ascii", "utf-16-le"):
        agulha = nome.encode(codificacao)
        sufixo = _SUFIXO_DO_EDGE.encode(codificacao)
        posicao = janela.find(agulha)
        while posicao != -1:
            fim = posicao + len(agulha)
            if (fim + len(sufixo) <= len(janela) or ultima) and (
                janela[fim:fim + len(sufixo)] != sufixo
            ):
                return True
            posicao = janela.find(agulha, posicao + 1)
    return False


def _sinais_da_janela(
    janela: bytes, ultima: bool, nome: str, rewired: bool
) -> tuple[bool, bool]:
    if nome in _DO_INCONTROL:
        return _perfis_da_janela(janela, ultima)
    if nome in _DA_SDL or nome == _DO_REWIRED:
        return _tem(janela, _DUALSENSE_EDGE), _tem(janela, _DUALSENSE_COMUM)
    return _tem(janela, _DUALSENSE_EDGE), _nomeia_sem_o_edge(janela, ultima, _SONY_DUALSENSE)


def _sinais_do_arquivo(arquivo: Path, *, rewired: bool) -> tuple[bool, bool]:
    """`(edge, comum)`, as duas marcas independentes, que UM arquivo da roupa conhece."""
    nome = arquivo.name.lower()
    if not (nome in _DO_INCONTROL or nome in _DA_SDL or nome == _DO_REWIRED or rewired):
        return False, False
    edge = comum = False
    try:
        if arquivo.stat().st_size == 0:
            return False, False
        for janela, _primeira, ultima in _janelas(arquivo):
            do_edge, do_comum = _sinais_da_janela(janela, ultima, nome, rewired)
            edge, comum = edge or do_edge, comum or do_comum
            if edge and comum:
                break
    except (OSError, ValueError):
        return False, False
    return edge, comum


def _ler_o_disco(raiz: Path) -> tuple[_Declarado, list[Path]]:
    """O que o jogo conhece, pela leitura do disco, e o que se olhou (a chave do cache).

    Cada fonte (um arquivo da roupa, ou o executável pelos PIDs) dá as duas marcas; quem conhece
    os dois modelos responde pelos dois. O que se olhou são as subpastas por onde a varredura
    andou e os arquivos lidos.
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
    fontes: list[tuple[str, bool, bool]] = []
    for arquivo in sorted(roupa):
        do_edge, do_comum = _sinais_do_arquivo(arquivo, rewired=rewired)
        if do_edge or do_comum:
            fontes.append((_relativo(arquivo, raiz), do_edge, do_comum))
    sony: set[str] = {"libScePad"} if bibliotecas else set()
    pids: set[str] = set()
    for arquivo in bibliotecas + ([executavel] if executavel is not None else []):
        do_arquivo, dos_pids = _sinais_guardados(arquivo)
        sony |= do_arquivo
        pids |= dos_pids
    if ROUPA_DO_EDGE in pids or ROUPA_DO_COMUM in pids:
        fontes.append(("o executável", ROUPA_DO_EDGE in pids, ROUPA_DO_COMUM in pids))
    dos_dois = next((quem for quem, e, c in fontes if e and c), None)
    edge = dos_dois or next((quem for quem, e, _c in fontes if e), None)
    comum = dos_dois or next((quem for quem, _e, c in fontes if c), None)
    da_sony = f"a biblioteca Sony ({', '.join(sorted(sony))}) pede o Edge" if sony else None
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


def _o_que_o_jogo_conhece(declarado: _Declarado) -> str:
    """A frase de quem conhece cada modelo, para a fonte da roupa."""
    edge, comum = declarado.edge, declarado.comum
    if edge is not None and comum is None:
        return f"{edge} conhece só o DualSense Edge"
    if edge is None and comum is not None:
        return f"{comum} conhece só o DualSense comum"
    if edge is not None and comum is not None:
        if edge == comum:
            return f"{comum} conhece os dois modelos: o DualSense comum"
        return f"{comum} conhece o DualSense comum e {edge}, o Edge: o DualSense comum"
    return "nenhum sinal do controle: o DualSense comum"


def _a_regra(declarado: _Declarado, caminho: str | None) -> tuple[str, str]:
    """A regra única: o Edge onde o caminho o pede ou o jogo conhece só ele; senão, o `0ce6`."""
    so_o_edge = declarado.edge is not None and declarado.comum is None
    pede_o_edge = caminho or declarado.sony
    if pede_o_edge is None and so_o_edge:
        pede_o_edge = _o_que_o_jogo_conhece(declarado)
    if pede_o_edge is not None:
        return ROUPA_DO_EDGE, pede_o_edge
    return ROUPA_DO_COMUM, _o_que_o_jogo_conhece(declarado)


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
    """A leitura é suspeita (um `mtime` a menos de uma margem do início) e a margem já passou?

    Num disco de tempo grosso, o arquivo que muda no mesmo tique deixa a chave igual. Enquanto a
    margem corre, a leitura guardada serve (é o melhor que se sabe); depois, vale UMA nova.
    """
    if comecou is None:
        return False
    suspeitos = [m for _c, _t, m in chave if m >= comecou - _MARGEM_NS]
    return bool(suspeitos) and _agora_ns() > max(suspeitos) + _MARGEM_NS


def _para_o_disco(raiz: Path, chave: _Chave, declarado: _Declarado, comecou: int) -> object:
    base = str(raiz) + os.sep
    return {
        "chave": [[c.removeprefix(base), t, m] for c, t, m in chave],
        "edge": declarado.edge,
        "comum": declarado.comum,
        "sony": declarado.sony,
        "lido_em": comecou,
    }


def _texto_ou_nada(valor: object) -> bool:
    return valor is None or isinstance(valor, str)


def _do_disco(raiz: Path) -> tuple[_Chave, _Declarado, int] | None:
    """A leitura que o disco guarda para o jogo; `None` se falta ou não tem a forma esperada."""
    entrada: Any = _guardado_no_disco(_NOME_NO_DISCO).get(str(raiz))
    if not isinstance(entrada, dict):
        return None
    bruta, comecou = entrada.get("chave"), entrada.get("lido_em")
    edge, comum, sony = entrada.get("edge"), entrada.get("comum"), entrada.get("sony")
    if not (
        isinstance(bruta, list) and bruta and isinstance(comecou, int)
        and _texto_ou_nada(edge) and _texto_ou_nada(comum) and _texto_ou_nada(sony)
    ):
        return None
    chave: list[tuple[str, int, int]] = []
    for item in bruta:
        if not (
            isinstance(item, list) and len(item) == 3 and isinstance(item[0], str)
            and isinstance(item[1], int) and isinstance(item[2], int)
        ):
            return None
        caminho = item[0] if os.path.isabs(item[0]) else str(raiz / item[0])
        chave.append((caminho, item[1], item[2]))
    return tuple(chave), _Declarado(edge=edge, comum=comum, sony=sony), comecou


def _do_cache(raiz: Path, *, do_disco: bool) -> tuple[_Declarado | None, bool]:
    """A leitura guardada, se nada mudou desde então, e se pede uma releitura.

    Sem leitura útil: `(None, False)`. Com leitura: `(declarado, a_reler)`, e quem não pode esperar
    o disco usa o `declarado` assim mesmo. Com `do_disco` (fora do laço), o jogo que a memória
    não tem se procura no cache em disco, que sobrevive ao reinício do daemon.
    """
    with _TRAVA_DO_CACHE:
        guardado = _CACHE.get(str(raiz))
        comecou = _LIDO_EM.get(str(raiz))
    if guardado is None and do_disco:
        do_disco_lido = _do_disco(raiz)
        if do_disco_lido is not None:
            with _TRAVA_DO_CACHE:
                _CACHE.setdefault(str(raiz), do_disco_lido[:2])
                _LIDO_EM.setdefault(str(raiz), do_disco_lido[2])
                guardado = _CACHE[str(raiz)]
                comecou = _LIDO_EM.get(str(raiz))
    if guardado is None:
        return None, False
    chave, declarado = guardado
    if _chave(raiz, [Path(c) for c, _t, _m in chave[1:]]) != chave:
        return None, False
    return declarado, _a_releitura_venceu(chave, comecou)


def _o_que_o_jogo_declara(raiz: Path, *, so_o_cache: bool) -> tuple[_Declarado | None, bool]:
    """`(declarado, a_reler)`: o que o jogo nomeia e se o cache pede leitura nova, fora do laço."""
    declarado, a_reler = _do_cache(raiz, do_disco=not so_o_cache)
    if so_o_cache or (declarado is not None and not a_reler):
        return declarado, a_reler
    comecou = _agora_ns()
    declarado, lidos = _ler_o_disco(raiz)
    chave = _chave(raiz, lidos)
    with _TRAVA_DO_CACHE:
        _CACHE[str(raiz)] = (chave, declarado)
        _LIDO_EM[str(raiz)] = comecou
    _gravar_no_disco(_NOME_NO_DISCO, {str(raiz): _para_o_disco(raiz, chave, declarado, comecou)})
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
        with _lote():
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
    não tem fica de fora (sem roupa própria até a leitura) e é lido num fio próprio, que chama
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
    with _lote():
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
