"""O estado de carga atravessa do byte até o payload — BATERIA-PARADA-01 (B1).

A QUEIXA, e ela estava certa (26/08/2026):

    *"sinto que o percentual de bateria do controle inclusive nunca é
    atualizado enquanto o controle tá conectado seja por cabo seja por bt"*

O que estava congelado não era o número — era a AUSÊNCIA da outra metade. Três
leituras do daemon vivo com sete segundos entre elas devolveram
``bat=100 status=None`` nas três, com o kernel dizendo ``Full`` num controle e
``Charging`` no outro no mesmo instante. **O produto lia o NÚMERO e jogava fora
o ESTADO**, e "100%" mudo é indistinguível de uma barra travada.

Reconferido na bancada em 06/09/2026, e o aparelho concorda com o enunciado: o
nó ``status`` do DualSense dela em ``/sys/class/power_supply/`` dizia ``Full``
com ``capacity=100`` enquanto o produto não tinha campo nenhum para carregar
essa palavra. (O endereço do controle dela não entra aqui: em ``tests/`` só
circulam as faixas forjadas da casa — ver ``test_anonimato_de_fixtures.py``. A
leitura está na entrega, em ``docs/process/agentes/2026-09-06/``, com a
máscara.)

O QUE ESTE ARQUIVO TRANCA — e cada classe declara a própria mordida:

1. o byte vira PALAVRA pela tabela do driver, não pelos nomes da biblioteca;
2. ``Level == 0`` é "ninguém reportou", não "descarregando";
3. o campo existe no ``ControllerState`` e no payload de
   ``describe_controllers`` — que é o dicionário que o ``controller.list``
   repassa verbatim à janela.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import (
    ESTADO_DE_CARGA,
    PyDualSenseController,
)
from hefesto_dualsense4unix.core.controller import ControllerState


def _handle(nibble: int | None, level: int) -> Any:
    """Um handle da pydualsense como o ``report_thread`` dela o deixa.

    ``DSBattery`` é um objeto simples com ``Level`` (0-100) e ``State`` (um
    ``IntFlag`` cujo VALOR é o nibble alto do ``states[53]``). O dublê é um
    ``SimpleNamespace`` de propósito: usar o enum real da biblioteca faria o
    teste medir a biblioteca, e o que se quer medir é a nossa tradução.
    """
    battery = SimpleNamespace(Level=level)
    if nibble is not None:
        battery.State = nibble
    return SimpleNamespace(battery=battery)


class TestOByteViraPalavra:
    """Mordida: apague uma linha de :data:`ESTADO_DE_CARGA` e o caso reprova.

    A tabela é a do ``dualsense_parse_report`` do kernel, registrada em
    ``docs/protocol/driver-hid-playstation.md``: ``0x0`` descarregando, ``0x1``
    carregando, ``0x2`` cheia, ``0xa``/``0xb`` tensão ou temperatura fora de
    faixa, ``0xf`` erro.
    """

    @pytest.mark.parametrize(
        ("nibble", "palavra"),
        [
            (0x0, "descarregando"),
            (0x1, "carregando"),
            (0x2, "cheio"),
            (0xA, "fora_de_faixa"),
            (0xB, "fora_de_faixa"),
            (0xF, "erro"),
        ],
    )
    def test_cada_nibble_do_kernel_tem_a_sua_palavra(
        self, nibble: int, palavra: str
    ) -> None:
        lido = PyDualSenseController._read_battery_state_opt(_handle(nibble, level=95))
        assert lido == palavra, (
            f"nibble 0x{nibble:x} devia dizer {palavra!r} e disse {lido!r} — "
            "a tabela é a do driver, ver docs/protocol/driver-hid-playstation.md"
        )

    def test_o_driver_vence_a_biblioteca_no_0xb(self) -> None:
        """``0xB`` é fora de faixa pelo driver; a pydualsense o chama de
        ``POWER_SUPPLY_STATUS_NOT_CHARGING``.

        A ordem de precedência desta casa é o aparelho antes da biblioteca, e
        esta é a única linha em que as duas discordam. Se alguém trocar a
        tabela pelos nomes do enum, este teste nomeia a troca.
        """
        assert ESTADO_DE_CARGA[0xB] == "fora_de_faixa"

    def test_nibble_desconhecido_e_nao_sei_e_nao_um_chute(self) -> None:
        assert PyDualSenseController._read_battery_state_opt(_handle(0x7, level=55)) is None


class TestNinguemReportouAindaNaoEDescarregando:
    """Mordida: tire a guarda do ``Level`` e o controle recém-plugado passa a
    anunciar ``"descarregando"`` — inventando leitura antes do primeiro report.

    ``DSBattery.__init__`` nasce com ``Level = 0`` e ``State = 0``, e ``0`` é
    DESCARREGANDO na tabela do kernel. O discriminador é EXATO: um report de
    verdade dá ``nibble*10+5``, cujo mínimo é 5 — ``Level == 0`` só existe
    antes do primeiro report.
    """

    def test_level_zero_nao_diz_nada_sobre_a_carga(self) -> None:
        assert PyDualSenseController._read_battery_state_opt(_handle(0x0, level=0)) is None

    def test_o_menor_level_de_verdade_ja_responde(self) -> None:
        assert (
            PyDualSenseController._read_battery_state_opt(_handle(0x0, level=5))
            == "descarregando"
        )

    def test_sem_objeto_de_bateria_ou_sem_estado_e_none(self) -> None:
        assert PyDualSenseController._read_battery_state_opt(SimpleNamespace()) is None
        assert PyDualSenseController._read_battery_state_opt(_handle(None, level=95)) is None

    def test_lixo_no_lugar_do_numero_nao_derruba_o_tique(self) -> None:
        sujo = SimpleNamespace(battery=SimpleNamespace(Level="oitenta", State=0x1))
        assert PyDualSenseController._read_battery_state_opt(sujo) is None


class TestOCampoExisteEChegaAoPayload:
    """Mordida: tire ``battery_state`` do ``ControllerState`` ou do payload de
    ``describe_controllers`` e a tela volta a não ter onde ler "carregando".

    O ``daemon/ipc_handlers.py`` repassa o dicionário do
    ``describe_controllers`` VERBATIM em ``result["controllers"]``, então este
    é o ponto em que o dado entra na janela.
    """

    def test_o_snapshot_carrega_o_estado_ao_lado_do_percentual(self) -> None:
        estado = ControllerState(
            battery_pct=100,
            l2_raw=0,
            r2_raw=0,
            connected=True,
            transport="usb",
            battery_state="carregando",
        )
        assert estado.battery_pct == 100
        assert estado.battery_state == "carregando"

    def test_o_campo_e_novo_com_default_e_nao_quebra_quem_ja_construia(self) -> None:
        """Os cinco obrigatórios de sempre continuam bastando."""
        estado = ControllerState(
            battery_pct=42, l2_raw=0, r2_raw=0, connected=True, transport="bt"
        )
        assert estado.battery_state is None

    def test_o_campo_novo_entrou_no_fim_e_nao_mexeu_na_ordem_posicional(self) -> None:
        """Um campo intercalado trocaria o sentido de todo ``ControllerState``
        construído por POSIÇÃO — e a casa tem dezenas deles em ``tests/``.

        A régua olha a ORDEM declarada, não um valor: ``raw_buttons`` continua
        sendo o sexto campo, como era antes desta sprint.
        """
        nomes = list(ControllerState.__dataclass_fields__)
        assert nomes[:6] == [
            "battery_pct",
            "l2_raw",
            "r2_raw",
            "connected",
            "transport",
            "raw_buttons",
        ]
        assert nomes[-1] == "battery_state"

    def test_describe_controllers_publica_o_estado_por_controle(self) -> None:
        backend = PyDualSenseController.__new__(PyDualSenseController)
        handle = _handle(0x1, level=95)
        handle.connected = True
        handle.conType = SimpleNamespace(name="USB")
        backend._handles = {"aabbcc000003": handle}
        backend._primary_key = "aabbcc000003"

        import threading

        backend._io_lock = threading.RLock()

        entradas = backend.describe_controllers()
        assert len(entradas) == 1
        assert entradas[0]["battery_pct"] == 95
        assert entradas[0]["battery_state"] == "carregando"

    def test_controle_desconectado_nao_afirma_estado_nenhum(self) -> None:
        backend = PyDualSenseController.__new__(PyDualSenseController)
        handle = _handle(0x1, level=95)
        handle.connected = False
        backend._handles = {"aabbcc000003": handle}
        backend._primary_key = "aabbcc000003"

        import threading

        backend._io_lock = threading.RLock()

        entradas = backend.describe_controllers()
        assert entradas[0]["battery_state"] is None
        assert entradas[0]["battery_pct"] is None
