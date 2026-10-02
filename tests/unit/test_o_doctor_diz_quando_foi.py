"""O doctor não pode contar o passado no presente."""

from __future__ import annotations

import datetime
import os
import pathlib
import subprocess
import textwrap

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts/doctor.sh"

_PREAMBULO = textwrap.dedent(
    """
    set -uo pipefail
    HOME="$TMPHOME"
    warn() { printf 'WARN %s\\n' "$*"; }
    info() { printf 'INFO %s\\n' "$*"; }
    pass() { :; }
    conselho_de_instalacao() { :; }
    so_no_checkout() { :; }
    _o_endereco_do_storm() { :; }
    """
)


def _bloco_do_kernel_watch() -> str:
    """O corpo de ``check_kernel_watch``, do fonte — nunca uma cópia."""
    fonte = DOCTOR.read_text(encoding="utf-8")
    i = fonte.index("    local log=\"${HOME}/.local/state/hefesto-dualsense4unix/kernel.log\"")
    j = fonte.index("\n}\n", i)
    return fonte[i:j]


def _rodar(linhas: list[str], janela: int = 7) -> str:
    """Escreve um `kernel.log` de mentira e devolve o que o bloco imprime."""
    import tempfile

    with tempfile.TemporaryDirectory() as lar:
        estado = pathlib.Path(lar) / ".local/state/hefesto-dualsense4unix"
        estado.mkdir(parents=True)
        (estado / "kernel.log").write_text("\n".join(linhas) + "\n", encoding="utf-8")
        env = dict(os.environ, TMPHOME=lar, HEFESTO_DOCTOR_JANELA_DIAS=str(janela))
        roteiro = (_PREAMBULO + "\n_bloco() {\n"
                   + _bloco_do_kernel_watch() + "\n}\n_bloco\n")
        r = subprocess.run(
            ["bash", "-c", roteiro],
            capture_output=True, text=True, env=env, cwd=str(RAIZ))
        return r.stdout + r.stderr


def _linha(dias_atras: int, tag: str) -> str:
    d = datetime.date.today() - datetime.timedelta(days=dias_atras)
    return f"{d.isoformat()} 12:00:00 [{tag}] alguma coisa aconteceu"


def test_evento_de_hoje_vira_aviso() -> None:
    """O que acontece AGORA continua sendo aviso — a cura não pode calar."""
    saida = _rodar(["# 2026-07-20 kernel-watch iniciado", _linha(0, "JOYCON")])
    assert "WARN" in saida, saida
    assert "JOYCON" in saida


def test_evento_velho_nao_vira_aviso() -> None:
    """Um evento de 24 dias atrás é HISTÓRICO, e o doctor diz isso."""
    saida = _rodar(["# 2026-07-20 kernel-watch iniciado", _linha(24, "JOYCON")])
    assert "WARN" not in saida, (
        f"um evento de 24 dias atrás virou aviso:\n{saida}")
    assert "histórico" in saida, saida


def test_o_aviso_diz_a_data_do_ultimo() -> None:
    """Todo número vem com QUANDO — sem isso ele não é verificável."""
    d = datetime.date.today() - datetime.timedelta(days=2)
    saida = _rodar(["# 2026-07-20 kernel-watch iniciado",
                    _linha(30, "USB-71"), _linha(2, "USB-71")])
    assert f"{d.day:02d}/{d.month:02d}" in saida, saida
    assert "no log inteiro" in saida, (
        "o aviso deixou de separar a janela do total — as duas contas importam")


def test_o_total_do_log_continua_dito() -> None:
    """O histórico não se apaga: ele muda de lugar e de tempo verbal."""
    saida = _rodar(["# 2026-07-20 kernel-watch iniciado"]
                   + [_linha(40, "USB-71")] * 5)
    assert "USB-71=5" in saida, saida
    assert "log INTEIRO" in saida, saida


def test_a_rajada_conta_as_ocorrencias_e_nao_as_linhas() -> None:
    """Desde 23/09 o [BT-HCI] e o [XHCI] chegam em rajada: borda + resumo."""
    hoje = datetime.date.today().isoformat()
    saida = _rodar([
        "# 2026-07-20 kernel-watch iniciado",
        f"{hoje}T12:00:00-03:00 [BT-HCI] Bluetooth: hci0: Opcode 0x2042 failed: -19",
        f"{hoje}T12:01:00-03:00 [BT-HCI] segue +59 (60 desde {hoje}T12:00:00-03:00, 60 s):"
        " Bluetooth: hci0: Opcode 0x2042 failed: -19",
        f"{hoje}T12:01:40-03:00 [BT-HCI] repetiu +40 (100 desde {hoje}T12:00:00-03:00, 100 s):"
        " Bluetooth: hci0: Opcode 0x2042 failed: -19",
        f"{hoje}T13:00:00-03:00 [XHCI] xhci_hcd 0000:00:14.0: HC died",
    ])
    assert "BT-HCI=100" in saida, saida
    assert "XHCI=1" in saida, saida


def test_log_limpo_nao_diz_nada() -> None:
    """Sem evento nenhum, nem aviso nem histórico — só o resumo."""
    saida = _rodar(["# 2026-07-20 kernel-watch iniciado"])
    assert "WARN" not in saida, saida
    assert "histórico" not in saida, saida


@pytest.mark.parametrize("tag", ["JOYCON", "JOYCON-PROBE", "USB-71", "BT-ERR"])
def test_os_quatro_contadores_obedecem_a_janela(tag: str) -> None:
    """A janela vale para os QUATRO, e não só para o que ela notou."""
    velho = _rodar(["# 2026-07-20 kernel-watch iniciado", _linha(30, tag)])
    assert "WARN" not in velho, f"{tag} de 30 dias atrás virou aviso:\n{velho}"
    novo = _rodar(["# 2026-07-20 kernel-watch iniciado", _linha(1, tag)])
    assert "WARN" in novo, f"{tag} de ontem não virou aviso:\n{novo}"
