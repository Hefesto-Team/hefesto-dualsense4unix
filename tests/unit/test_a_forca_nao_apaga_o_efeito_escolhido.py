"""A força de um controle troca um campo; as escolhas da aba Vibração ficam.

A seção ``rumble`` de cada controle guarda a força (``policy``), as barras dos motores e as duas
escolhas (``efeito_haptico``, ``efeito_imersao``). O gesto de força reescrevia a seção inteira:
um clique em Economia na aba Vibração apagava a Guarda e o Coice escolhidos para aquele controle
e as barras guardadas. O segundo escritor, o teto da aba Conexões, saiu em 17/10/2026.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

CHAVE = "aabbcc000001"

ESCOLHAS = {
    "motor_forte_pct": 50,
    "haptica_pct": 80,
    "efeito_haptico": "guarda",
    "efeito_imersao": "coice",
}


def _perfil(rumble_global: str = "balanceado", **dele: Any) -> Any:
    from hefesto_dualsense4unix.profiles.schema import Profile

    return Profile.model_validate({
        "name": "Bancada",
        "match": {"type": "criteria"},
        "rumble": {"policy": rumble_global},
        "controllers": {CHAVE: {"rumble": dele}},
    })


def _secao(controllers: Any) -> dict[str, Any] | None:
    rumble = getattr((controllers or {}).get(CHAVE), "rumble", None)
    return None if rumble is None else rumble.model_dump(exclude_unset=True)


def _forca_da_aba_05(prof: Any, policy: str | None) -> dict[str, Any] | None:
    from hefesto_dualsense4unix.app.draft_config import DraftConfig, RumbleDraft

    draft = DraftConfig.from_profile(prof)
    pedido = RumbleDraft.model_validate({**draft.rumble.model_dump(), "policy": policy})
    return _secao(draft.with_controller_rumble(CHAVE, pedido).source_controllers)


def test_economia_na_aba_vibracao_guarda_as_escolhas() -> None:
    # D-1610-A-FORCA-NAO-APAGA-O-EFEITO-ESCOLHIDO
    """MORDIDA: volte o ``ControllerRumbleOverride(**campos)`` em ``with_controller_rumble``."""
    depois = _forca_da_aba_05(_perfil(**ESCOLHAS), "economia")
    assert depois == {**ESCOLHAS, "policy": "economia"}


def test_seguir_o_global_tira_so_a_forca() -> None:
    depois = _forca_da_aba_05(_perfil(policy="max", **ESCOLHAS), "balanceado")
    assert depois == ESCOLHAS


def test_sem_nada_mais_a_secao_some() -> None:
    assert _forca_da_aba_05(_perfil(policy="economia"), "balanceado") is None
