"""diario_do_radio.py — o diário comum e a trava de quem mexe no rádio."""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import sys
import time
from collections.abc import Callable, Iterable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

NOME_DO_DIARIO = "radio-diario.jsonl"

DIARIO_DO_ROOT = Path("/var/lib/hefesto-dualsense4unix") / NOME_DO_DIARIO

TRAVA_COMUM = Path("/run/hefesto-dualsense4unix/radio.lock")

ENV_TRAVA = "HEFESTO_RADIO_TRAVA"
ENV_DIARIO = "HEFESTO_RADIO_DIARIO"
ENV_DIARIO_DO_ROOT = "HEFESTO_RADIO_DIARIO_ROOT"

TAMANHO_MAXIMO = 512 * 1024

PRAZO_DA_TRAVA_S = 30.0

PASSO_DA_ESPERA_S = 0.05


ESPEROU_A_TRAVA = "esperou a trava"
DESISTIU_DA_TRAVA = "desistiu da trava"
PONTE_SUBIU = "ponte subiu"
PONTE_DESCEU = "ponte desceu"


def _a_suite_esta_rodando() -> bool:
    """A mesma pergunta de ``gesto_de_reconexao._a_suite_esta_rodando``."""
    return bool(os.environ.get("PYTEST_CURRENT_TEST")) or "pytest" in sys.modules


def _lar_de_estado() -> Path:
    from hefesto_dualsense4unix.utils.xdg_paths import state_dir

    return state_dir()


def caminho_do_diario() -> Path:
    """O diário de quem roda como ela."""
    desvio = os.environ.get(ENV_DIARIO, "").strip()
    if desvio:
        return Path(desvio)
    return _lar_de_estado() / NOME_DO_DIARIO


def caminho_do_diario_do_root() -> Path | None:
    """O diário dos motores root, ou ``None`` com a suíte no ar sem desvio."""
    desvio = os.environ.get(ENV_DIARIO_DO_ROOT, "").strip()
    if desvio:
        return Path(desvio)
    if _a_suite_esta_rodando():
        return None
    return DIARIO_DO_ROOT


def caminho_da_trava() -> Path:
    """A trava que este processo vai disputar."""
    desvio = os.environ.get(ENV_TRAVA, "").strip()
    if desvio:
        return Path(desvio)
    if _a_suite_esta_rodando():
        return _lar_de_estado() / "radio.lock"
    if TRAVA_COMUM.parent.is_dir():
        return TRAVA_COMUM
    from hefesto_dualsense4unix.utils.xdg_paths import runtime_dir

    return runtime_dir() / "radio.lock"


def a_trava_e_comum(caminho: Path) -> bool:
    """A trava em ``caminho`` é a que o root também disputa?"""
    return caminho == TRAVA_COMUM


def _agora_iso(carimbo: float) -> str:
    return datetime.fromtimestamp(carimbo).astimezone().isoformat(timespec="seconds")


def _anexar(caminho: Path, dado: bytes) -> None:
    """Uma linha no fim do arquivo, com rotação, sem intercalar escritores."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    bandeiras = os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW
    for _ in range(5):
        fd = os.open(caminho, bandeiras, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            aberto = os.fstat(fd)
            try:
                atual = os.stat(caminho, follow_symlinks=False)
            except FileNotFoundError:
                continue
            if (atual.st_ino, atual.st_dev) != (aberto.st_ino, aberto.st_dev):
                continue
            if aberto.st_size > 0 and aberto.st_size + len(dado) > TAMANHO_MAXIMO:
                os.replace(caminho, caminho.with_name(caminho.name + ".1"))
                continue
            os.write(fd, dado)
            return
        finally:
            os.close(fd)
    raise OSError(f"o diário {caminho} girou cinco vezes durante uma escrita")


def registrar(
    quem: str,
    o_que: str,
    por_que: str,
    *,
    antes: Any = None,
    depois: Any = None,
    caminho: Path | None = None,
    agora: float | None = None,
    **campos: Any,
) -> dict[str, Any]:
    """Uma ação de rádio no diário. Devolve a entrada, escrita ou não."""
    if not quem or not o_que:
        raise ValueError("uma entrada do diário precisa de quem e do quê")
    carimbo = time.time() if agora is None else agora
    entrada: dict[str, Any] = {
        "quando": _agora_iso(carimbo),
        "carimbo": carimbo,
        "quem": quem,
        "o_que": o_que,
        "por_que": por_que,
        "antes": antes,
        "depois": depois,
    }
    for chave, valor in campos.items():
        if valor is not None:
            entrada[chave] = valor
    linha = json.dumps(entrada, ensure_ascii=False, default=str) + "\n"
    alvo = caminho or caminho_do_diario()
    try:
        _anexar(alvo, linha.encode("utf-8"))
    except OSError:
        logger.warning("diario_do_radio_nao_gravou", caminho=str(alvo), exc_info=True)
    return entrada


def _linhas(caminho: Path) -> Iterator[dict[str, Any]]:
    try:
        texto = caminho.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        try:
            dado = json.loads(linha)
        except ValueError:
            continue
        if not isinstance(dado, dict):
            continue
        if not isinstance(dado.get("carimbo"), (int, float)):
            continue
        if not isinstance(dado.get("o_que"), str):
            continue
        yield dado


def _com_o_girado(caminho: Path) -> list[Path]:
    return [caminho.with_name(caminho.name + ".1"), caminho]


def ler(
    *,
    caminhos: Iterable[Path] | None = None,
    desde: float | None = None,
    limite: int | None = None,
) -> list[dict[str, Any]]:
    """As entradas dos dois diários, em ordem de hora. Nunca levanta."""
    if caminhos is None:
        fontes = _com_o_girado(caminho_do_diario())
        do_root = caminho_do_diario_do_root()
        if do_root is not None:
            fontes.extend(_com_o_girado(do_root))
    else:
        fontes = list(caminhos)
    entradas: list[dict[str, Any]] = []
    for fonte in fontes:
        entradas.extend(_linhas(fonte))
    if desde is not None:
        entradas = [e for e in entradas if float(e["carimbo"]) >= desde]
    entradas.sort(key=lambda e: float(e["carimbo"]))
    if limite is not None and limite >= 0:
        entradas = entradas[-limite:] if limite else []
    return entradas


def pontes_de_pe(
    entradas: Iterable[dict[str, Any]], instante: float
) -> dict[str, set[tuple[str, str]]]:
    """``{adaptador: {(controle, tipo)}}`` das pontes de pé em ``instante``."""
    de_pe: dict[tuple[str, str], str] = {}
    for entrada in entradas:
        if float(entrada.get("carimbo", 0.0)) > instante:
            break
        o_que = entrada.get("o_que")
        if o_que not in (PONTE_SUBIU, PONTE_DESCEU):
            continue
        controle = str(entrada.get("controle") or "")
        tipo = str(entrada.get("tipo") or "som")
        if not controle:
            continue
        chave = (controle, tipo)
        if o_que == PONTE_SUBIU:
            de_pe[chave] = str(entrada.get("adaptador") or "")
        else:
            de_pe.pop(chave, None)
    por_adaptador: dict[str, set[tuple[str, str]]] = {}
    for chave, adaptador in de_pe.items():
        por_adaptador.setdefault(adaptador, set()).add(chave)
    return por_adaptador


class TravaOcupadaError(RuntimeError):
    """O prazo acabou e a trava continuou com outro motor."""

    def __init__(self, dono: str, espera_s: float) -> None:
        self.dono = dono
        self.espera_s = espera_s
        super().__init__(
            f"a trava do rádio está com {dono or 'outro motor'} "
            f"(esperei {espera_s:.1f} s)"
        )


def dono_da_trava(caminho: Path) -> str:
    """Quem pegou a trava por último, como ele se escreveu nela. ``""`` = não sei."""
    try:
        texto = caminho.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return texto.strip().splitlines()[0][:120] if texto.strip() else ""


def _abrir_a_trava(caminho: Path) -> tuple[int, bool]:
    """``(fd, dá para escrever o dono)``. O ``flock`` vale em fd só de leitura."""
    with contextlib.suppress(OSError):
        caminho.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(caminho, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o664)
        return fd, True
    except PermissionError:
        fd = os.open(caminho, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        return fd, False


def _marcar_o_dono(fd: int, quem: str) -> None:
    with contextlib.suppress(OSError):
        os.ftruncate(fd, 0)
        os.pwrite(fd, f"{quem} {os.getpid()}\n".encode(), 0)


@contextlib.contextmanager
def trava_do_radio(
    quem: str,
    *,
    prazo_s: float = PRAZO_DA_TRAVA_S,
    caminho: Path | None = None,
    diario: Path | None = None,
    relogio: Callable[[], float] = time.monotonic,
    dormir: Callable[[float], None] = time.sleep,
) -> Iterator[float]:
    """Segura a trava do rádio enquanto o bloco roda. Entrega quanto esperou."""
    alvo = caminho or caminho_da_trava()
    fd, escreve = _abrir_a_trava(alvo)
    try:
        inicio = relogio()
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            espera = 0.0
        except BlockingIOError:
            dono = dono_da_trava(alvo)
            while True:
                dormir(PASSO_DA_ESPERA_S)
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    decorrido = relogio() - inicio
                    if decorrido >= prazo_s:
                        registrar(
                            quem,
                            DESISTIU_DA_TRAVA,
                            f"{dono or 'outro motor'} segurou a trava por mais "
                            f"de {prazo_s:g} s",
                            antes={"dono": dono},
                            depois={"espera_s": round(decorrido, 3)},
                            caminho=diario,
                        )
                        raise TravaOcupadaError(dono, decorrido) from None
            espera = relogio() - inicio
            registrar(
                quem,
                ESPEROU_A_TRAVA,
                f"{dono or 'outro motor'} estava com ela",
                antes={"dono": dono},
                depois={"espera_s": round(espera, 3)},
                caminho=diario,
            )
        if escreve:
            _marcar_o_dono(fd, quem)
        yield espera
    finally:
        os.close(fd)


__all__ = [
    "DESISTIU_DA_TRAVA",
    "DIARIO_DO_ROOT",
    "ENV_DIARIO",
    "ENV_DIARIO_DO_ROOT",
    "ENV_TRAVA",
    "ESPEROU_A_TRAVA",
    "NOME_DO_DIARIO",
    "PASSO_DA_ESPERA_S",
    "PONTE_DESCEU",
    "PONTE_SUBIU",
    "PRAZO_DA_TRAVA_S",
    "TAMANHO_MAXIMO",
    "TRAVA_COMUM",
    "TravaOcupadaError",
    "a_trava_e_comum",
    "caminho_da_trava",
    "caminho_do_diario",
    "caminho_do_diario_do_root",
    "dono_da_trava",
    "ler",
    "pontes_de_pe",
    "registrar",
    "trava_do_radio",
]
