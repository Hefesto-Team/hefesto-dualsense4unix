"""A janela do início da sessão não morre junto com o serviço que a abriu.

A unit `hefesto-dualsense4unix-gui-hotplug.service` é `Type=oneshot` e chama o
lançador, que desprende a janela com `setsid nohup … &` e sai na hora. O `setsid`
cria sessão nova mas NÃO tira o processo do cgroup da unit; com o padrão
`KillMode=control-group`, o systemd recolhe o cgroup inteiro quando a unit
termina, e a janela recém-nascida morre. Aberta pelo dock, pela bandeja ou pelo
terminal ela nasce em outro escopo e fica de pé: só a porta do início da sessão
passava por aqui.

MORDIDA: tirar o `KillMode=process` da unit (ou pô-lo de volta em
`control-group`) reprova a régua.
"""

from __future__ import annotations

import configparser
from pathlib import Path

import pytest

from hefesto_dualsense4unix.utils import units_de_usuario as udu

RAIZ = Path(__file__).resolve().parents[2]
UNIT = RAIZ / "assets" / "hefesto-dualsense4unix-gui-hotplug.service"
DOC = RAIZ / "docs" / "usage" / "hotplug.md"


def _servico(texto: str) -> dict[str, str]:
    """A seção `[Service]` como o systemd a lê (`#` comenta; a chave repetida vale a última)."""
    cfg = configparser.ConfigParser(
        interpolation=None, strict=False, delimiters=("=",), comment_prefixes=("#", ";")
    )
    cfg.optionxform = str  # type: ignore[assignment,method-assign]
    cfg.read_string(texto)
    return dict(cfg["Service"].items())


def _unit_solta_a_janela(texto: str) -> bool:
    """A unit deixa a janela viva: só o processo principal é morto, ou o `ExecStart` põe
    a janela num escopo próprio."""
    servico = _servico(texto)
    modo = servico.get("KillMode", "control-group").strip()
    escopo_proprio = "systemd-run" in servico["ExecStart"] and "--scope" in servico["ExecStart"]
    return modo in {"process", "none"} or escopo_proprio


def test_a_unit_do_inicio_da_sessao_e_oneshot_e_nao_recolhe_a_janela() -> None:
    texto = UNIT.read_text(encoding="utf-8")
    servico = _servico(texto)
    assert servico["Type"] == "oneshot", "a unit só abre; o Type diz a verdade"
    assert _unit_solta_a_janela(texto), (
        "oneshot com KillMode=control-group: o systemd recolhe o cgroup quando o lançador sai "
        "e leva a janela junto"
    )


def test_o_kill_mode_e_process_e_nao_none() -> None:
    """`process` mata o processo principal e só ele; é o que a unit diz, sem depender de
    `none` (que desliga a morte de qualquer processo da unit)."""
    assert _servico(UNIT.read_text(encoding="utf-8")).get("KillMode") == "process"


def test_o_formato_de_pacote_entrega_a_unit_com_a_mesma_cura(tmp_path: Path) -> None:
    """O `.deb`, o Arch e os demais vestem esta mesma unit pelo renderizador: a cura
    tem de chegar inteira, com o binário no lugar dele."""
    escritas = udu.renderizar_para(
        RAIZ / "assets", tmp_path, bin_dir="/usr/bin", python="/opt/hefesto/bin/python"
    )
    vestida = next(p for p in escritas if p.name == UNIT.name).read_text(encoding="utf-8")
    assert "ExecStart=/usr/bin/hefesto-dualsense4unix-gui" in vestida
    assert _unit_solta_a_janela(vestida)


@pytest.mark.parametrize(
    "texto, solta",
    [
        ("[Service]\nType=oneshot\nExecStart=/x\n", False),
        ("[Service]\nType=oneshot\nKillMode=control-group\nExecStart=/x\n", False),
        ("[Service]\nType=oneshot\nKillMode=mixed\nExecStart=/x\n", False),
        ("[Service]\nType=oneshot\n# KillMode=process\nExecStart=/x\n", False),
        ("[Service]\nType=oneshot\nKillMode=process\nExecStart=/x\n", True),
        ("[Service]\nType=oneshot\nExecStart=/usr/bin/systemd-run --user --scope /x\n", True),
    ],
)
def test_a_regua_distingue_a_unit_que_recolhe_da_que_solta(texto: str, solta: bool) -> None:
    """A régua não é frouxa: o padrão do systemd, `control-group` e `mixed` recolhem a
    janela; o comentário não conta como cura."""
    assert _unit_solta_a_janela(texto) is solta


def test_o_texto_de_uso_diz_o_que_a_unit_faz() -> None:
    doc = DOC.read_text(encoding="utf-8")
    assert "fica aberta" in doc and "KillMode=process" in doc, (
        "hotplug.md tem de dizer que a janela do início da sessão fica de pé depois que a "
        "unit termina, e por quê"
    )
