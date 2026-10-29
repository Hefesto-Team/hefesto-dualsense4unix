"""A troca que o install adiou porque havia um jogo aberto, aplicada quando o jogo fecha.

O-INSTALL-NAO-DERRUBA-O-CONTROLE-DO-JOGO-ABERTO-01 (28/10/2026): o install com o jogo em
cena grava o que deixou de trocar (o broker, o daemon, a janela e a bandeja) em
``$XDG_RUNTIME_DIR/hefesto-dualsense4unix/troca-no-fim-do-jogo``. O daemon, no tique do
sinal de jogo, vê o jogo fechado, colhe a pendência e a dispara FORA do próprio serviço,
porque o restart do daemon mata quem mora no cgroup dele.
"""
from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable, Sequence
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


def arquivo_da_troca() -> Path:
    """A pendência que o install grava (o mesmo caminho do ``adiar_para_o_fim_do_jogo``)."""
    declarado = os.environ.get(TROCA_ENV, "").strip()
    return Path(declarado) if declarado else runtime_dir() / ARQUIVO


def troca_pendente() -> bool:
    return arquivo_da_troca().is_file()


def colher_a_troca() -> list[str]:
    """Lê e apaga a pendência; o que volta é só o que a casa conhece, na ordem da troca."""
    arquivo = arquivo_da_troca()
    try:
        texto = arquivo.read_text(encoding="utf-8")
        arquivo.unlink()
    except OSError:
        return []
    pedidos = set(texto.split())
    return [item for item in ITENS if item in pedidos]


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
    try:
        feito = subprocess.run(
            list(cmd), stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=60, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return feito.returncode == 0


def aplicar(
    itens: Sequence[str],
    *,
    pedir_ao_broker: Callable[[], bool] = _pedir_a_troca_ao_broker,
    rodar: Callable[[Sequence[str]], bool] = _rodar,
) -> list[str]:
    """O broker primeiro (o daemon velho ainda segura os nós), depois o daemon, depois a tela."""
    feitos: list[str] = []
    if "broker" in itens and pedir_ao_broker():
        feitos.append("broker")
    if "daemon" in itens and rodar(["systemctl", "--user", "restart", UNIT_DO_DAEMON]):
        feitos.append("daemon")
    if "recarga" in itens and rodar([sys.executable, "-m", MODULO_DA_RECARGA]):
        feitos.append("recarga")
    return feitos


def main(argv: Sequence[str] | None = None) -> int:
    itens = [a for a in (sys.argv[1:] if argv is None else argv) if a in ITENS]
    feitos = aplicar(itens)
    logger.info("troca_no_fim_do_jogo_aplicada", pedidos=",".join(itens),
                feitos=",".join(feitos) or "-")
    return 0 if len(feitos) == len(itens) else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
