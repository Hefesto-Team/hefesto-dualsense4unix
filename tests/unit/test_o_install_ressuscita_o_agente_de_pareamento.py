"""O install tem de tirar o agente de pareamento do estado `failed`."""

from __future__ import annotations

import re
from pathlib import Path

from tests.unit.fonte_do_instalador import texto_do_instalador

RAIZ = Path(__file__).resolve().parents[2]
UNIT = RAIZ / "assets" / "systemd" / "hefesto-bt-agent.service"


def _corpo(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_o_install_reseta_o_failed_antes_de_ligar_o_agente() -> None:
    """`reset-failed` tem de vir ANTES do `enable --now`, no mesmo bloco."""
    corpo = texto_do_instalador()

    reset = corpo.find("systemctl reset-failed hefesto-bt-agent.service")
    assert reset != -1, (
        "o install não reseta o estado `failed` do hefesto-bt-agent.service.\n"
        "`enable --now` NÃO tira unit de `failed`: o systemd recusa iniciar quem\n"
        "bateu o StartLimitBurst. Sem esta linha o install imprime 'habilitado'\n"
        "e deixa o agente morto — e sem agente todo bond novo nasce meio-salvo.\n"
        "Medido em 14/08/2026: oito horas sem Bluetooth por causa disso."
    )

    enable = corpo.find("systemctl enable --now hefesto-bt-agent.service")
    assert enable != -1, "o install deixou de habilitar o hefesto-bt-agent.service"

    assert reset < enable, (
        "o `reset-failed` está DEPOIS do `enable --now`.\n"
        "Nessa ordem a cura não vale para a execução corrente: o enable já\n"
        "falhou, e a unit só voltaria no PRÓXIMO install."
    )


def test_a_unit_impede_o_agente_de_entrar_em_failed() -> None:
    """A cura irmã, na unit — as duas juntas, ou o buraco continua aberto."""
    corpo = _corpo(UNIT)

    assert re.search(r"^KillSignal=SIGKILL$", corpo, re.MULTILINE), (
        "a unit perdeu o `KillSignal=SIGKILL`.\n"
        "Sem ele, todo `stop` deixa a unit em `failed (Result: timeout)`, porque\n"
        "o `bt-agent` não trata SIGTERM e o systemd o mata depois do timeout.\n"
        "`SuccessExitStatus=SIGKILL` NÃO cobre isso: ele fala do código de saída,\n"
        "e o `Result: timeout` é o veredito do stop."
    )

    assert re.search(r"^SuccessExitStatus=SIGKILL$", corpo, re.MULTILINE), (
        "a unit perdeu o `SuccessExitStatus=SIGKILL` — a camada de 04/08 que faz\n"
        "a morte por SIGKILL contar como saída limpa."
    )

    assert re.search(r"^Restart=always$", corpo, re.MULTILINE), (
        "a unit perdeu o `Restart=always`. Para este serviço não há desfecho em\n"
        "que ficar fora seja correto: sem ele, o pareamento dela não funciona."
    )


def test_o_restore_de_bonds_religa_o_agente_que_ele_mesmo_derruba() -> None:
    """A terceira ponta: quem derruba o agente tem de religá-lo."""
    restore = RAIZ / "scripts" / "bt_bonds_restore.sh"
    corpo = _corpo(restore)

    assert "hefesto-bt-agent.service" in corpo, (
        "o `bt_bonds_restore.sh` não menciona o agente de pareamento.\n"
        "Ele PARA o bluetooth.service, o que derruba o agente pelo `Requires=`.\n"
        "Se o trap não o religar, o restore deixa a máquina sem quem confirma\n"
        "pareamento — e os bonds recém-restaurados somem em horas."
    )

    trap_ini = corpo.find("trap '")
    assert trap_ini != -1, "o `bt_bonds_restore.sh` perdeu o trap de EXIT"
    trap_fim = corpo.find("' EXIT", trap_ini)
    assert trap_fim != -1, "o trap de EXIT do restore não fecha"
    trap = corpo[trap_ini:trap_fim]

    assert "hefesto-bt-agent.service" in trap, (
        "o agente não é religado no TRAP de EXIT — só religar no caminho feliz\n"
        "não basta: se o restore abortar no meio (snapshot inválido, timeout do\n"
        "stop), o agente fica caído e ninguém percebe."
    )
    assert "reset-failed" in trap, (
        "o trap religa o agente sem `reset-failed` antes.\n"
        "Se ele estiver em `failed` — que é justamente o estado em que este\n"
        "script o deixa —, o `start` é recusado e a cura não cura nada."
    )
