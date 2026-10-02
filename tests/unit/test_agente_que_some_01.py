"""A janela sem agente de pareamento é curta, e o agente sempre volta."""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
UNIT = RAIZ / "assets" / "systemd" / "hefesto-bt-agent.service"


def _texto() -> str:
    return UNIT.read_text(encoding="utf-8")


def test_o_agente_sempre_volta() -> None:
    """`Restart=always` — não há desfecho em que ficar fora seja correto."""
    assert re.search(r"^Restart=always$", _texto(), re.M), (
        "o `Restart` do agente de pareamento não é `always`. Com "
        "`SuccessExitStatus=SIGKILL` presente, `on-failure` NÃO religa a unit "
        "depois do SIGKILL — as duas linhas se anulam e ela fica sem agente. "
        "Ver docs/process/sprints/2026-08-08-BLUETOOTHD-MORTO-POR-NOS-01-*.md"
    )


def test_a_janela_sem_agente_e_curta() -> None:
    """`RestartSec` e `TimeoutStopSec` somados ficam bem abaixo de 2 s."""
    texto = _texto()

    restart = re.search(r"^RestartSec=(\S+)$", texto, re.M)
    assert restart, "a unit perdeu o `RestartSec`"
    assert restart.group(1) == "250ms", (
        f"`RestartSec={restart.group(1)}` — a janela sem agente voltou a crescer. "
        "Eram 5 s, e eram o grosso dos 3-5 s medidos."
    )

    parada = re.search(r"^TimeoutStopSec=(\S+)$", texto, re.M)
    assert parada, "a unit perdeu o `TimeoutStopSec`"
    assert parada.group(1) == "1s", (
        f"`TimeoutStopSec={parada.group(1)}` — esperar mais que 1 s por uma saída "
        "limpa que nunca vem (36 de 36 morreram por SIGKILL) só alonga a janela."
    )


def test_a_rede_de_seguranca_do_sigkill_continua() -> None:
    """As linhas que a cura de 04/08 trouxe não podem sair junto."""
    texto = _texto()
    assert re.search(r"^SendSIGKILL=yes$", texto, re.M), (
        "sumiu o `SendSIGKILL=yes` — sem ele o agente travado numa chamada D-Bus "
        "segura a parada do serviço, que foi o defeito de 03/08 (90 s de "
        "Bluetooth fora do ar)."
    )
    assert re.search(r"^SuccessExitStatus=SIGKILL$", texto, re.M), (
        "sumiu o `SuccessExitStatus=SIGKILL` — sem ele a unit fica `failed` "
        "depois de toda parada e o agente não volta (defeito de 04/08)."
    )


def test_o_limite_de_rajada_continua_de_guarda() -> None:
    """Baixar o `RestartSec` para 250 ms exige que o limite de rajada fique."""
    texto = _texto()
    assert re.search(r"^StartLimitBurst=\d+$", texto, re.M), (
        "sumiu o `StartLimitBurst` — com `RestartSec=250ms` ele é a única coisa "
        "entre um agente que morre ao subir e um laço de reinício apertado."
    )
    assert re.search(r"^StartLimitIntervalSec=\d+$", texto, re.M), (
        "sumiu o `StartLimitIntervalSec`, que dá sentido ao `StartLimitBurst`."
    )


def test_o_porque_esta_escrito_na_unit() -> None:
    """Quem abrir a unit encontra as três histórias que a moldaram."""
    texto = _texto()
    for marca in (
        "AGENTE-QUE-SOME-01",
        "BT-AGENT-TRAVA-O-RESTART-01",
        "BT-AGENT-MORTO-FICA-MORTO-01",
    ):
        assert marca in texto, (
            f"o registro de {marca} saiu da unit. Cada uma destas linhas nasceu "
            "de um defeito medido, e sem o porquê a próxima pessoa 'limpa' a "
            "unit e reabre um deles."
        )
