"""A escada da intensidade (30/100/150) e o teto que satura em 255."""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core.rumble import _effective_mult
from hefesto_dualsense4unix.daemon.ipc_rumble_policy import apply_rumble_policy
from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems.rumble import (
    RUMBLE_POLICY_MULT,
    reassert_rumble,
)
from hefesto_dualsense4unix.profiles.schema import (
    RUMBLE_CUSTOM_MULT_MAX,
    RumbleConfig,
)


def _config(policy: str, custom_mult: float = 1.0) -> DaemonConfig:
    cfg = DaemonConfig()
    cfg.rumble_policy = policy  # type: ignore[assignment]
    cfg.rumble_policy_custom_mult = custom_mult
    return cfg


def _atributo_do_trilho(nome: str) -> float:
    """`max`/`min` do trilho da Intensidade, na TELA QUE ELA USA."""
    pagina = (
        Path(__file__).resolve().parents[2]
        / "src" / "hefesto_dualsense4unix"
        / "interface" / "paginas" / "05-vibracao.html"  # noqa-acento (pasta)
    ).read_text(encoding="utf-8")
    trilho = re.search(
        r'<input[^>]*type="range"[^>]*data-campo="mult-pos"[^>]*>', pagina
    )
    assert trilho is not None, (
        "o trilho `mult-pos` sumiu de `05-vibracao.html` — a coluna "
        "Intensidade perdeu o ajuste livre, ou a régua ficou cega"
    )
    achado = re.search(rf'{nome}="([\d.]+)"', trilho.group(0))
    assert achado is not None, f"o trilho da Intensidade perdeu o atributo {nome}"
    return float(achado.group(1))


def test_a_escada_da_intensidade_e_30_100_150() -> None:
    """Os três degraus, no dono único, e cada um com a sua razão de ser."""
    assert RUMBLE_POLICY_MULT["economia"] == pytest.approx(0.3)
    assert RUMBLE_POLICY_MULT["balanceado"] == pytest.approx(1.0)
    assert RUMBLE_POLICY_MULT["max"] == pytest.approx(1.5)
    assert RUMBLE_POLICY_MULT["max"] > RUMBLE_POLICY_MULT["balanceado"], (
        'um botão chamado "Máximo" tem de entregar mais que o "Balanceado"'
    )


def test_balanceado_entrega_exatamente_o_que_o_jogo_pediu() -> None:
    """O que o tooltip promete: sem aumentar nem diminuir."""
    mult, _, _ = _effective_mult(_config("balanceado"), 80, 1.0, 1.0, 0.0)
    assert mult == pytest.approx(1.0)

    daemon = SimpleNamespace(config=_config("balanceado"), store=None)
    assert apply_rumble_policy(daemon, 200, 137) == (200, 137)


def test_maximo_amplifica_acima_do_que_o_jogo_pediu() -> None:
    daemon = SimpleNamespace(config=_config("max"), store=None)
    mult = RUMBLE_POLICY_MULT["max"]
    assert apply_rumble_policy(daemon, 100, 60) == (
        round(100 * mult), round(60 * mult)
    )


@pytest.mark.parametrize("bruto", [200, 220, 255])
def test_amplificar_satura_em_255_e_nunca_da_a_volta(bruto: int) -> None:
    """A MORDIDA: amplificar é multiplicar **e** saturar."""
    assert bruto * RUMBLE_POLICY_MULT["max"] > 255, (
        "o bruto escolhido tem de estourar o teto, senão o teste não fala de "
        "saturação nenhuma"
    )
    daemon = SimpleNamespace(config=_config("max"), store=None)
    for valor in apply_rumble_policy(daemon, bruto, bruto):
        assert valor == 255, "acima do teto, o motor tem de ficar NO teto"
        assert 0 <= valor <= 255, "o valor tem de caber num byte de motor"


def test_o_caminho_do_rumble_fixado_tambem_satura() -> None:
    """O rumble que ELA fixa passa pela mesma conta — e satura igual."""
    daemon = MagicMock()
    daemon.config = _config("max")
    daemon.config.rumble_active = (200, 30)
    daemon.store.snapshot.return_value.controller.battery_pct = 80
    daemon._last_auto_mult = 1.0
    daemon._last_auto_change_at = 0.0

    reassert_rumble(daemon, 1.0)

    mult = RUMBLE_POLICY_MULT["max"]
    daemon.controller.set_rumble.assert_called_once_with(
        weak=min(255, round(200 * mult)),
        strong=round(30 * mult),
    )


def test_o_teto_do_deslizador_e_o_do_esquema_do_perfil() -> None:
    teto = RUMBLE_CUSTOM_MULT_MAX
    assert teto == pytest.approx(2.0)
    assert _atributo_do_trilho("max") == RUMBLE_CUSTOM_MULT_MAX * 100
    RumbleConfig(policy="custom", custom_mult=RUMBLE_CUSTOM_MULT_MAX)


def test_o_deslizador_vai_mais_longe_que_o_botao_maximo() -> None:
    """Não é incoerência — é a divisão de papéis que ela decidiu em 11/08."""
    teto_do_botao = RUMBLE_POLICY_MULT["max"]
    assert teto_do_botao < RUMBLE_CUSTOM_MULT_MAX, (
        "o preset ficou tão longe quanto o ajuste livre — some a diferença "
        "entre atalho seguro e escolha informada"
    )
    assert teto_do_botao > 1.0, 'e mesmo assim o "Máximo" tem de amplificar'


def test_o_rascunho_da_janela_aceita_o_mesmo_teto_do_perfil() -> None:
    """As duas pontas eram inconsistentes — o rascunho aceitava o que o perfil"""
    from hefesto_dualsense4unix.app.draft_config import RumbleDraft

    RumbleDraft(policy="custom", custom_mult=RUMBLE_CUSTOM_MULT_MAX)
    with pytest.raises(ValueError):
        RumbleDraft(policy="custom", custom_mult=RUMBLE_CUSTOM_MULT_MAX + 0.1)


@pytest.mark.parametrize("bateria", [0, 5, 19, 20, 35, 50, 51, 80, 100])
def test_o_auto_nunca_amplifica(bateria: int) -> None:
    """Ele existe para POUPAR bateria — amplificar seria o oposto, e sozinho."""
    mult, _, _ = _effective_mult(_config("auto"), bateria, 1.0, 1.0, 0.0)
    assert mult <= 1.0, "o Auto passou de 100% — ele nunca deve aumentar"
    assert any(
        mult == pytest.approx(degrau) for degrau in (1.0, 0.7, 0.3)
    ), f"degrau fora da escada própria do Auto: {mult}"
