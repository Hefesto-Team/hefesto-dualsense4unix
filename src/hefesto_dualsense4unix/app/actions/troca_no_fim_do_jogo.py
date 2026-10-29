"""A troca que o install adiou porque havia um jogo aberto, aplicada quando o jogo fecha.

O install com o jogo em cena grava o que deixou de trocar em ``arquivo_da_troca``. Quem a
aplica, fora do cgroup do daemon: o tique do sinal de jogo do daemon e a vigia que o install
sobe (``--esperar``), que vale com o daemon de antes da cura, parado ou caído. O jogo tem de
ficar fechado por ``ESPERA_SEM_JOGO_S`` e é perguntado de novo antes de cada troca; o que
um jogo novo pegar volta à pendência (O-INSTALL-NAO-DERRUBA-O-CONTROLE-DO-JOGO-ABERTO-01).
"""
from __future__ import annotations

import contextlib
import fcntl
import os
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.xdg_paths import runtime_dir

logger = get_logger(__name__)

ARQUIVO = "troca-no-fim-do-jogo"
TROCA_ENV = "HEFESTO_TROCA_NO_FIM_DO_JOGO"
ITENS = ("broker", "daemon", "recarga")
UNIT_DO_DAEMON = "hefesto-dualsense4unix.service"
MODULO = "hefesto_dualsense4unix.app.actions.troca_no_fim_do_jogo"
MODULO_DA_RECARGA = "hefesto_dualsense4unix.app.actions.recarga_do_install"
ESPERA_SEM_JOGO_S = 10.0
PASSO_DA_VIGIA_S = 2.0
PRAZO_DA_VIGIA_S = 12 * 3600.0


def arquivo_da_troca() -> Path:
    """A pendência que o install grava (o mesmo caminho do ``adiar_para_o_fim_do_jogo``)."""
    declarado = os.environ.get(TROCA_ENV, "").strip()
    return Path(declarado) if declarado else runtime_dir() / ARQUIVO


def troca_pendente() -> bool:
    return arquivo_da_troca().is_file()


def _na_ordem(pedidos: Sequence[str]) -> list[str]:
    return [item for item in ITENS if item in set(pedidos)]


def colher_a_troca() -> list[str]:
    """Toma a pendência para si (o rename é de um só) e a apaga; volta só o que a casa conhece."""
    arquivo = arquivo_da_troca()
    colhida = arquivo.with_name(f".{arquivo.name}.colhida.{os.getpid()}")
    try:
        os.rename(arquivo, colhida)
    except OSError:
        return []
    try:
        texto = colhida.read_text(encoding="utf-8")
    except OSError:
        texto = ""
    with contextlib.suppress(OSError):
        colhida.unlink()
    return _na_ordem(texto.split())


def devolver_a_troca(itens: Sequence[str]) -> None:
    """Põe de volta na pendência o que não se trocou, sem repetir item."""
    arquivo = arquivo_da_troca()
    try:
        ja = arquivo.read_text(encoding="utf-8").split() if arquivo.is_file() else []
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text("".join(f"{i}\n" for i in _na_ordem([*ja, *itens])), encoding="utf-8")
    except OSError as erro:
        logger.warning("troca_no_fim_do_jogo_nao_devolvida", itens=",".join(itens), err=str(erro))


@dataclass
class EsperaSemJogo:
    """O jogo fechado de vez: ``espera_s`` seguidos sem jogo, e não um intervalo entre dois."""

    espera_s: float = ESPERA_SEM_JOGO_S
    desde: float | None = None

    def fechou_de_vez(self, jogo_aberto: bool, agora: float) -> bool:
        if jogo_aberto:
            self.desde = None
            return False
        if self.desde is None:
            self.desde = agora
        return agora - self.desde >= self.espera_s

    def zerar(self) -> None:
        self.desde = None


def _jogo_aberto() -> bool:
    """A mesma pergunta do daemon (``uhid_gamepad.JOGO_ABERTO``); na dúvida, há jogo."""
    from hefesto_dualsense4unix.integrations import uhid_gamepad

    try:
        return bool(uhid_gamepad.JOGO_ABERTO())
    except Exception as erro:
        logger.warning("troca_no_fim_do_jogo_sem_resposta_do_jogo", err=str(erro))
        return True


def disparar(itens: Sequence[str], *, abrir: Callable[..., Any] | None = None) -> None:
    """Abre ``python -m …troca_no_fim_do_jogo <itens>`` numa unidade própria do systemd."""
    from hefesto_dualsense4unix.integrations import fora_do_servico

    abertura = (abrir or fora_do_servico.abrir)(
        [sys.executable, "-m", MODULO, *itens],
        env=dict(os.environ),
        aplicativo="troca-no-fim-do-jogo",
    )
    logger.info("troca_no_fim_do_jogo_disparada", itens=",".join(itens),
                caminho=getattr(abertura, "caminho", None))


def _pedir_a_troca_ao_broker() -> bool:
    from hefesto_dualsense4unix.integrations.hidraw_broker_client import HidrawBrokerClient

    cliente = HidrawBrokerClient()
    try:
        return cliente.trocar_se_mudou()
    finally:
        cliente.close()


def _rodar(cmd: Sequence[str]) -> bool:
    """O prazo é o do systemd (``TimeoutStartSec`` da unit), como no install."""
    try:
        feito = subprocess.run(
            list(cmd), stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False,
        )
    except OSError as erro:
        logger.warning("troca_no_fim_do_jogo_sem_comando", cmd=cmd[0], err=str(erro))
        return False
    return feito.returncode == 0


def aplicar(
    itens: Sequence[str],
    *,
    pedir_ao_broker: Callable[[], bool] = _pedir_a_troca_ao_broker,
    rodar: Callable[[Sequence[str]], bool] = _rodar,
    jogo_aberto: Callable[[], bool] = _jogo_aberto,
) -> list[str]:
    """O broker primeiro (o daemon velho ainda segura os nós), depois o daemon, depois a tela.

    Antes do broker e do daemon o jogo é perguntado de novo: o jogo que abriu depois da
    colheita fica com o controle, e o resto da troca volta à pendência.
    """
    pedidos = _na_ordem(itens)
    feitos: list[str] = []
    for posicao, item in enumerate(pedidos):
        if item != "recarga" and jogo_aberto():
            devolver_a_troca(pedidos[posicao:])
            logger.info("troca_no_fim_do_jogo_esperou_outro_jogo",
                        devolvidos=",".join(pedidos[posicao:]))
            break
        if item == "broker":
            feito = pedir_ao_broker()
        elif item == "daemon":
            feito = rodar(["systemctl", "--user", "restart", UNIT_DO_DAEMON])
        else:
            feito = rodar([sys.executable, "-m", MODULO_DA_RECARGA])
        if feito:
            feitos.append(item)
    return feitos


def _aplicar_e_contar(
    itens: Sequence[str], aplicar_os: Callable[[Sequence[str]], list[str]]
) -> int:
    feitos = aplicar_os(itens)
    logger.info("troca_no_fim_do_jogo_aplicada", pedidos=",".join(itens),
                feitos=",".join(feitos) or "-")
    return 0 if len(feitos) == len(itens) else 1


def _a_trava_da_vigia() -> int | None:
    """Uma vigia só: a segunda que nasce acha a trava presa e sai."""
    arquivo = arquivo_da_troca()
    try:
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(arquivo.with_name(f".{arquivo.name}.vigia"), os.O_RDWR | os.O_CREAT, 0o600)
    except OSError:
        return None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return None
    return fd


def esperar(
    *,
    jogo_aberto: Callable[[], bool] = _jogo_aberto,
    aplicar_os: Callable[[Sequence[str]], list[str]] = aplicar,
    relogio: Callable[[], float] = time.monotonic,
    dormir: Callable[[float], None] = time.sleep,
    prazo_s: float = PRAZO_DA_VIGIA_S,
) -> int:
    """A vigia que o install sobe: espera o jogo fechar de vez, troca e sai.

    Sai sem pendência, quando outra vigia já está de pé, ou no prazo (a pendência fica para
    o daemon e para o próximo install). O jogo que abre no meio devolve o resto, e ela segue.
    """
    trava = _a_trava_da_vigia()
    if trava is None:
        return 0
    try:
        espera = EsperaSemJogo()
        inicio = relogio()
        while relogio() - inicio < prazo_s:
            if not troca_pendente():
                return 0
            if espera.fechou_de_vez(jogo_aberto(), relogio()):
                espera.zerar()
                itens = colher_a_troca()
                if itens:
                    _aplicar_e_contar(itens, aplicar_os)
            dormir(PASSO_DA_VIGIA_S)
        logger.info("troca_no_fim_do_jogo_vigia_no_prazo", pendente=troca_pendente())
        return 0
    finally:
        os.close(trava)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["--esperar"]:
        return esperar()
    return _aplicar_e_contar([a for a in args if a in ITENS], aplicar)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
