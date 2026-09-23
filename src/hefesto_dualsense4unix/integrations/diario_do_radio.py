"""diario_do_radio.py — o diário comum e a trava de quem mexe no rádio.

O-DIARIO-DO-RADIO-01 (23/09/2026). Até aqui, três motores mexiam no rádio sem
se conhecer: o ``bt_health_watchdog.sh`` (root, a cada 2 min: ``Connect``,
``Trusted``, ``pair`` e ``restart``), o vigia de zumbis do daemon (a cada 5 s:
derruba o link morto pela ponte privilegiada) e a central que vai nascer (mover,
parear, equilibrar). Cada um escrevia no próprio log, e nenhum sabia que o outro
estava no meio de um gesto. O estudo de 23/09 (``arquiteto.md``, bloco «UMA TRAVA
E UM DIÁRIO») nomeia o risco: o watchdog fazendo ``Connect`` no adaptador antigo
enquanto a central move o controle.

AS DUAS PEÇAS
-------------

**A trava** é um ``flock`` num arquivo só, :data:`TRAVA_COMUM`. O kernel a solta
quando o processo morre, então não existe trava presa por quem caiu. Todo motor
pede a trava COM PRAZO (:func:`trava_do_radio`), e a espera é registrada — quem
esperou, quanto, e quem estava com ela. Quem não consegue no prazo desiste e diz
por quê: nenhum motor fica pendurado atrás de outro.

**O diário** é um JSONL de AÇÕES de rádio: quem, o quê, por quê, o antes e o
depois. É o «registro» da D7 (o anti-storm age sozinho e registra) e a fonte do
sino da tela: a tela LÊ o diário, não escreve texto próprio. Rotação por tamanho.

DOIS ARQUIVOS, UM DIÁRIO
------------------------

Quem roda como ela escreve em ``~/.local/state/hefesto-dualsense4unix/`` (o
:func:`caminho_do_diario`). Quem roda como ROOT — o watchdog e a ponte
privilegiada — NÃO escreve no lar dela: um processo root escrevendo numa pasta
que a usuária controla pode ser levado por um link simbólico a sobrescrever
qualquer arquivo da máquina. O root escreve em :data:`DIARIO_DO_ROOT`, numa
pasta que só o root escreve e que ela lê; o :func:`ler` junta os dois pela hora.
O formato é o mesmo, byte a byte — as linhas do root saem do ``_diario`` dos
scripts, e a régua confere que este leitor as entende.

A SUÍTE NÃO TOCA NA TRAVA DELA
------------------------------

Com a suíte no ar, a trava e o diário do root caem para dentro do lar de mentira
do ``tests/conftest.py``: um teste que segurasse a trava comum seguraria o
watchdog dela junto. Quem precisa de outro caminho passa por argumento, ou pelas
variáveis :data:`ENV_TRAVA` e :data:`ENV_DIARIO_DO_ROOT`.
"""

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

#: O nome do arquivo do diário, nos dois lados.
NOME_DO_DIARIO = "radio-diario.jsonl"

#: O diário dos motores ROOT. A pasta é do install (a mesma do acervo de bonds,
#: ``/var/lib/hefesto-dualsense4unix/bt-bonds``), escrita só pelo root e lida
#: por ela.
DIARIO_DO_ROOT = Path("/var/lib/hefesto-dualsense4unix") / NOME_DO_DIARIO

#: A trava comum. O diretório nasce do ``tmpfiles.d`` do install, com o grupo
#: dela, para que o root (watchdog, ponte) e ela (daemon) disputem o MESMO
#: arquivo.
TRAVA_COMUM = Path("/run/hefesto-dualsense4unix/radio.lock")

#: Desvios explícitos — a suíte e quem medir à mão.
ENV_TRAVA = "HEFESTO_RADIO_TRAVA"
ENV_DIARIO = "HEFESTO_RADIO_DIARIO"
ENV_DIARIO_DO_ROOT = "HEFESTO_RADIO_DIARIO_ROOT"

#: Acima disto o arquivo vira ``.1`` e um novo começa. Meio mega é folga de
#: meses: uma ação de rádio é uma linha de ~300 bytes.
TAMANHO_MAXIMO = 512 * 1024

#: O prazo padrão de quem pede a trava. O watchdog segura a trava por um tique
#: inteiro (até ~40 s com o ``pair``); trinta segundos cobrem o caso comum, e
#: quem não conseguir tenta na próxima volta.
PRAZO_DA_TRAVA_S = 30.0

#: De quanto em quanto tempo quem espera torna a perguntar. O ``flock`` não tem
#: prazo em Python, e 50 ms é imperceptível para um gesto de rádio.
PASSO_DA_ESPERA_S = 0.05

# --- o vocabulário ------------------------------------------------------------
#
# O ``o_que`` de uma entrada é texto curto e FIXO para o que mais de um motor
# escreve: o leitor (o sino, o ``storm_doctor``) procura por estas constantes,
# e um sinônimo escrito à mão seria uma entrada que ninguém acha.

ESPEROU_A_TRAVA = "esperou a trava"
DESISTIU_DA_TRAVA = "desistiu da trava"
#: A ponte de som ou de vibração de um controle. Quem escreve é o governador
#: (GOVERNADOR-DO-RADIO-01), com ``controle``, ``adaptador`` e ``tipo`` (``som``
#: ou ``vibracao``); quem lê é o :func:`pontes_de_pe`.
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
    """A trava que este processo vai disputar.

    Em ordem: o desvio explícito; com a suíte no ar, uma trava dentro do lar de
    mentira; a trava comum, se o install criou a pasta dela; e, sem ela, uma
    trava na pasta de execução dela — que ainda põe os motores DELA em fila
    (vigia e central moram no mesmo daemon), mas não enxerga o watchdog root.
    Esse último caso é dito no diário por quem pega a trava
    (:func:`a_trava_e_comum`).
    """
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


# --- o diário -------------------------------------------------------------------


def _agora_iso(carimbo: float) -> str:
    return datetime.fromtimestamp(carimbo).astimezone().isoformat(timespec="seconds")


def _anexar(caminho: Path, dado: bytes) -> None:
    """Uma linha no fim do arquivo, com rotação, sem intercalar escritores.

    O ``flock`` aqui é do PRÓPRIO arquivo do diário, e não a trava do rádio: ele
    só impede que duas escritas se misturem ou que a rotação corte uma linha ao
    meio. Depois de pegá-lo, confere que o nome ainda aponta para o arquivo que
    foi aberto — outro escritor pode ter rodado o diário entre o ``open`` e o
    ``flock``, e escrever no ``.1`` seria escrever no passado.
    """
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
    """Uma ação de rádio no diário. Devolve a entrada, escrita ou não.

    Nunca levanta por causa do disco: uma ação que JÁ aconteceu não pode ser
    desfeita porque o diário não gravou. O erro vai para o log do daemon.

    ``campos`` leva o que o leitor filtra — ``adaptador``, ``controle``,
    ``porta``, ``familia``, ``frase`` (o texto curto do sino) — e nada além de
    valor que o JSON aceita.
    """
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
    """As entradas dos dois diários, em ordem de hora. Nunca levanta.

    Linha que não é JSON, ou que não traz ``carimbo`` e ``o_que``, é pulada: o
    diário é escrito por shell e por Python, e uma linha torta não pode calar o
    resto. ``caminhos`` entra cru (sem o ``.1``) — é o que a régua usa.
    """
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
    """``{adaptador: {(controle, tipo)}}`` das pontes de pé em ``instante``.

    Reconstrói pelo diário: cada :data:`PONTE_SUBIU` acende, cada
    :data:`PONTE_DESCEU` apaga, até o instante pedido. Ponte sem adaptador
    conhecido cai em ``""`` — contada, mas sem casa.
    """
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


# --- a trava --------------------------------------------------------------------


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
    """Segura a trava do rádio enquanto o bloco roda. Entrega quanto esperou.

    Primeiro tenta sem esperar. Se outro motor está com ela, espera até
    ``prazo_s``, perguntando a cada :data:`PASSO_DA_ESPERA_S`, e registra no
    diário a espera — ou a desistência, que levanta :class:`TravaOcupadaError`. A
    trava sai sozinha no fim do bloco, e também quando o processo morre.
    """
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
