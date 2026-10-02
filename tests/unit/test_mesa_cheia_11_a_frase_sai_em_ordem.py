"""MESA-CHEIA-11/E2 — a frase do banner sai em ORDEM CRESCENTE."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("mesa cheia 11: a frase do banner sai em ordem crescente")

import json
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.app.actions.home_actions import (
    controles_bt_frageis,
    jogadores_degradados,
    texto_coop_degradado,
    texto_native_bt_fragil,
    vpad_degradation_text,
)
from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp_mod

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "state_full_quatro_controles.json"
)


def mesa_cheia() -> dict[str, Any]:
    """O payload REAL de quatro controles (dois USB, dois BT), cópia fresca."""
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _mesa_com_motivo(motivo: str) -> dict[str, Any]:
    state = mesa_cheia()
    gp = state["gamepad_emulation"]
    gp["dedup_ok"] = False
    gp["dedup_motivo"] = motivo
    return state


class TestOsNumerosSaemCrescentes:
    def test_a_ordem_de_chegada_fora_de_ordem_sai_crescente(self) -> None:
        """O caso do jogador que sai e é substituído: 3, 4 e depois o 2."""
        assert jogadores_degradados(
            "jogador_3_uinput, jogador_4_uinput, jogador_2_uinput"
        ) == [2, 3, 4]

    def test_dois_numeros_invertidos(self) -> None:
        assert jogadores_degradados("jogador_4_uinput, jogador_2_uinput") == [2, 4]

    def test_a_desduplicacao_sobrevive_a_ordem_invertida(self) -> None:
        """Repetido E fora de ordem: um número só, e no lugar certo."""
        assert jogadores_degradados(
            "jogador_4_uinput, jogador_2_uinput, jogador_4_uinput"
        ) == [2, 4]

    def test_os_motivos_alheios_no_meio_nao_atrapalham(self) -> None:
        """O campo mistura motivos do primário e do wrapper (`", ".join`)."""
        assert jogadores_degradados(
            "jogador_3_uinput, jogo_sem_wrapper, jogador_2_uinput"
        ) == [2, 3]

    def test_a_frase_composta_a_partir_da_ordem_de_chegada(self) -> None:
        texto = texto_coop_degradado(
            jogadores_degradados("jogador_3_uinput, jogador_4_uinput, jogador_2_uinput")
        )
        assert "Jogadores 2, 3 e 4" in texto
        assert "3, 4 e 2" not in texto


class TestNaMesaRealAJanelaLeCrescente:
    def test_o_banner_da_mesa_cheia_sai_em_ordem(self) -> None:
        texto = vpad_degradation_text(
            _mesa_com_motivo("jogador_3_uinput, jogador_4_uinput, jogador_2_uinput")
        )
        assert texto is not None
        assert "Jogadores 2, 3 e 4" in texto
        assert "3, 4 e 2" not in texto

    def test_com_o_motivo_do_wrapper_colado_atras(self) -> None:
        """`ipc_handlers` anexa `jogo_sem_wrapper` ao motivo já existente."""
        texto = vpad_degradation_text(
            _mesa_com_motivo("jogador_4_uinput, jogador_2_uinput, jogo_sem_wrapper")
        )
        assert texto is not None
        assert "Jogadores 2 e 4" in texto
        assert "4 e 2" not in texto


class _VpadDegradado:
    """A máscara DualSense no uinput, que é o que faz um pad degradado."""

    flavor = "dualsense"
    backend = "uinput"


class _DeviceP1:
    flavor = "dualsense"
    backend = "uhid"


class _Config:
    gamepad_emulation_enabled = True


class _DaemonComCoop:
    """Só o que o `dedup_status` lê (ele é todo getattr defensivo)."""

    def __init__(self) -> None:
        self.config = _Config()
        self._gamepad_device = _DeviceP1()
        self._coop_manager: Any = None

    def is_native_mode(self) -> bool:
        return False


def _entra(manager: Any, mac: str) -> None:
    """Um jogador entra na mesa, com o índice que o produto daria a ele."""
    manager._players[mac] = coop_mod._SecondaryPlayer(
        identity=mac,
        evdev_path=f"/dev/input/event-{mac}",
        reader=object(),  # type: ignore[arg-type]
        player_index=manager._next_player_index(),
        vpad=_VpadDegradado(),  # type: ignore[arg-type]
    )


class TestOJogadorQueEntrouNoLugarDoP2:
    def test_o_numero_reusado_nao_vai_para_o_fim_da_frase(self) -> None:
        """Ponta a ponta com o produto: índice reusado -> motivo -> banner."""
        daemon = _DaemonComCoop()
        manager = coop_mod.CoopManager(daemon)  # type: ignore[arg-type]
        daemon._coop_manager = manager

        for mac in ("aa:2", "aa:3", "aa:4"):
            _entra(manager, mac)
        del manager._players["aa:2"]
        _entra(manager, "aa:novo")

        indices = [p.player_index for p in manager._players.values()]
        assert indices == [3, 4, 2], "a mesa da refutação não se reproduziu"

        ok, motivos = gp_mod.dedup_status(daemon)  # type: ignore[arg-type]
        assert ok is False
        motivo = ", ".join(motivos)
        assert motivo == "jogador_3_uinput, jogador_4_uinput, jogador_2_uinput"

        texto = vpad_degradation_text(_mesa_com_motivo(motivo))
        assert texto is not None
        assert "Jogadores 2, 3 e 4" in texto
        assert "Jogadores 3, 4 e 2" not in texto


class TestOAvisoDeBtFragilTambemChegaOrdenado:
    def test_a_janela_ordena_o_que_o_daemon_publicou(self) -> None:
        """O daemon de hoje já ordena; esta é a última parada antes do olho"""
        state = mesa_cheia()
        state["native_bt_fragil_controles"] = [4, 1, 3, 2]
        assert controles_bt_frageis(state) == [1, 2, 3, 4]

    def test_a_frase_do_bt_fragil_sai_crescente(self) -> None:
        state = mesa_cheia()
        state["native_bt_fragil_controles"] = [3, 2]
        texto = texto_native_bt_fragil(controles_bt_frageis(state))
        assert "Controles 2 e 3" in texto
        assert "Controles 3 e 2" not in texto
