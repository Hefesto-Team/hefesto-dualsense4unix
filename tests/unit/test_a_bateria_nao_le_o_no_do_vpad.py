"""A varredura de bateria ignora o nosso próprio vpad — BATERIA-PARADA-01 (B2)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.broker.hidraw_broker import VPAD_UNIQ_PREFIX
from hefesto_dualsense4unix.core.backend_pydualsense import _VPAD_UNIQ_PREFIX
from hefesto_dualsense4unix.daemon.battery_journal import (
    PREFIXO_DO_VPAD,
    PREFIXO_NO_KERNEL,
    DiarioDaBateria,
    e_no_do_vpad,
    ler_no_do_kernel,
)
from hefesto_dualsense4unix.integrations.uhid_gamepad import player_mac

_REAL_1 = "aabbcc000003"
_REAL_2 = "e8473a0000d8"

_VPAD_1 = player_mac(1).replace(":", "")
_VPAD_2 = player_mac(2).replace(":", "")


def _no(raiz: Path, uniq: str, capacity: str, status: str) -> Path:
    """Cria um nó de bateria falso com o mesmo nome que o driver usa."""
    endereco = ":".join(uniq[i : i + 2] for i in range(0, 12, 2))
    no = raiz / f"{PREFIXO_NO_KERNEL}{endereco}"
    no.mkdir(parents=True, exist_ok=True)
    (no / "capacity").write_text(capacity, encoding="utf-8")
    (no / "status").write_text(status, encoding="utf-8")
    return no


@pytest.fixture()
def sysfs_com_quatro_nos(tmp_path: Path) -> Path:
    """O sysfs medido na bancada: quatro nós, dois deles nossos."""
    raiz = tmp_path / "power_supply"
    raiz.mkdir()
    _no(raiz, _VPAD_1, "100", "Charging")
    _no(raiz, _VPAD_2, "100", "Charging")
    _no(raiz, _REAL_1, "100", "Full")
    _no(raiz, _REAL_2, "45", "Discharging")
    return raiz


def _descreve(uniq: str, pct: int | None, estado: str | None) -> dict[str, Any]:
    """Uma entrada de ``describe_controllers()`` como o backend a devolve."""
    return {
        "index": 0,
        "connected": True,
        "transport": "usb",
        "is_primary": True,
        "uniq": uniq,
        "battery_pct": pct,
        "battery_state": estado,
    }


class TestAVarreduraDevolveDoisENaoQuatro:
    """QUATRO nós no disco, DOIS controles na resposta — o enunciado da sprint.

    **A varredura desta casa é a do produto:** ``DiarioDaBateria.observar``
    percorre o que o backend enxerga e chama ``ler_no_do_kernel`` por endereço.
    Não há (nem deve haver, enquanto ninguém a chame) uma função pública que
    enumere ``/sys/class/power_supply``: uma nasceu aqui em 06/09 e foi apagada
    no mesmo dia, acusada pelo nome pelo
    ``portao_a_casa_sabe_e_o_produto_nao_faz`` — promessa pública sem chamador
    em produção.

    Mordida: tire o filtro do vpad e o diário abre QUATRO curvas em vez de
    duas, duas delas cravadas em 100% ``Charging`` para sempre.
    """

    def test_quatro_nos_no_disco_dois_controles_na_resposta(
        self, sysfs_com_quatro_nos: Path
    ) -> None:
        no_disco = [
            p.name
            for p in sysfs_com_quatro_nos.iterdir()
            if p.name.startswith(PREFIXO_NO_KERNEL)
        ]
        assert len(no_disco) == 4, "o dublê tem de ter os quatro nós medidos"

        diario = DiarioDaBateria(raiz=sysfs_com_quatro_nos, intervalo_sonda=30.0)
        with structlog.testing.capture_logs() as registros:
            linhas = diario.observar(
                [
                    _descreve(_VPAD_1, 100, None),
                    _descreve(_VPAD_2, 100, None),
                    _descreve(_REAL_1, 100, "cheio"),
                    _descreve(_REAL_2, 45, "descarregando"),
                ],
                0.0,
            )

        assert linhas == 2, (
            "a varredura tem de devolver DOIS controles, não quatro — os dois "
            f"`{PREFIXO_DO_VPAD}:` são gamepads VIRTUAIS nossos, e o nó deles diz "
            "Charging/100 para sempre"
        )
        intrusos = [
            r["controle"]
            for r in registros
            if r.get("event") == "bateria_amostra" and e_no_do_vpad(r["controle"])
        ]
        assert not intrusos, (
            f"o diário abriu curva para gamepad VIRTUAL: {intrusos} — uma reta "
            "em 100% que se lê como 'o instrumento parou de olhar'"
        )


class TestONoDoVpadNaoSeLe:
    """Mordida: tire a guarda do ``ler_no_do_kernel`` e ele passa a devolver"""

    def test_ler_o_vpad_e_nao_sei_mesmo_com_o_no_no_disco(
        self, sysfs_com_quatro_nos: Path
    ) -> None:
        assert ler_no_do_kernel(_VPAD_1, raiz=sysfs_com_quatro_nos) == (None, None)

    def test_o_controle_de_verdade_continua_sendo_lido(
        self, sysfs_com_quatro_nos: Path
    ) -> None:
        assert ler_no_do_kernel(_REAL_2, raiz=sysfs_com_quatro_nos) == (
            45,
            "Discharging",
        )

    @pytest.mark.parametrize(
        "grafia",
        [
            "02fe00000001",
            "02:fe:00:00:00:01",
            "02:FE:00:00:00:01",
            f"{PREFIXO_NO_KERNEL}02:fe:00:00:00:01",
        ],
    )
    def test_as_grafias_que_circulam_no_produto_sao_todas_pegas(
        self, grafia: str
    ) -> None:
        assert e_no_do_vpad(grafia)

    @pytest.mark.parametrize(
        "valor", [None, "", "/dev/hidraw7", "deda4", _REAL_1, _REAL_2]
    )
    def test_na_duvida_e_controle_de_verdade(self, valor: str | None) -> None:
        """Errar para "pode ser controle do usuário" custa dois ``read`` de sysfs;"""
        assert not e_no_do_vpad(valor)


class TestODiarioNaoAbreCurvaParaOVpad:
    """Mordida: tire o ``continue`` do ``observar`` e o diário abre uma curva"""

    def test_so_o_controle_de_verdade_vira_linha(
        self, sysfs_com_quatro_nos: Path
    ) -> None:
        diario = DiarioDaBateria(raiz=sysfs_com_quatro_nos, intervalo_sonda=30.0)
        with structlog.testing.capture_logs() as registros:
            linhas = diario.observar(
                [
                    _descreve(_VPAD_1, 100, None),
                    _descreve(_REAL_1, 100, "cheio"),
                ],
                0.0,
            )

        assert linhas == 1, "o vpad não pode abrir curva nenhuma"
        eventos = [r for r in registros if r.get("event") == "bateria_amostra"]
        assert len(eventos) == 1
        assert eventos[0]["controle"].startswith("aa:bb:cc:")

    def test_o_estado_do_handle_vai_junto_com_o_do_kernel(
        self, sysfs_com_quatro_nos: Path
    ) -> None:
        """As duas réguas do ESTADO na mesma linha, como já valia para o"""
        diario = DiarioDaBateria(raiz=sysfs_com_quatro_nos, intervalo_sonda=30.0)
        with structlog.testing.capture_logs() as registros:
            diario.observar([_descreve(_REAL_1, 100, "cheio")], 0.0)

        evento = next(r for r in registros if r.get("event") == "bateria_amostra")
        assert evento["status"] == "Full"
        assert evento["estado_handle"] == "cheio"


class TestOEspelhoNaoDiverge:
    """O PORTÃO desta sprint — *sai NOMEANDO*."""

    def test_as_tres_copias_dizem_o_que_o_player_mac_forja(self) -> None:
        forjado = player_mac(1).replace(":", "").lower()
        for nome, copia in (
            ("daemon/battery_journal.PREFIXO_DO_VPAD", PREFIXO_DO_VPAD),
            ("broker/hidraw_broker.VPAD_UNIQ_PREFIX", VPAD_UNIQ_PREFIX),
            ("core/backend_pydualsense._VPAD_UNIQ_PREFIX", _VPAD_UNIQ_PREFIX),
        ):
            assert forjado.startswith(copia), (
                f"{nome} = {copia!r} não é mais o prefixo que player_mac() forja "
                f"({forjado!r}) — a varredura de bateria voltaria a ler o nó do "
                "vpad, e ele diz Charging/100 para sempre"
            )

    def test_todo_jogador_da_mesa_cai_na_mesma_faixa(self) -> None:
        """Quatro DualSense é a bancada; os quatro vpads têm de ser pegos."""
        for jogador in (1, 2, 3, 4):
            assert e_no_do_vpad(player_mac(jogador))
