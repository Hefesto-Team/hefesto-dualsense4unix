"""A força e o teto de um controle trocam um campo; as escolhas da aba Vibração ficam.

A seção ``rumble`` de cada controle guarda a força (``policy``), as barras dos motores e as duas
escolhas (``efeito_haptico``, ``efeito_imersao``). Os dois gestos de força reescreviam a seção
inteira: um clique em Economia na aba Vibração, ou no teto da aba Conexões, apagava a Guarda e o
Coice escolhidos para aquele controle e as barras guardadas.
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
    """MORDIDA: volte o ``ControllerRumbleOverride(**campos)`` em ``with_controller_rumble``."""
    depois = _forca_da_aba_05(_perfil(**ESCOLHAS), "economia")
    assert depois == {**ESCOLHAS, "policy": "economia"}


def test_seguir_o_global_tira_so_a_forca() -> None:
    depois = _forca_da_aba_05(_perfil(policy="max", **ESCOLHAS), "balanceado")
    assert depois == ESCOLHAS


def test_o_teto_da_aba_conexoes_guarda_as_escolhas() -> None:
    """MORDIDA: volte o ``model_validate({"policy": policy})`` em ``_com_o_teto``."""
    from pacotes.a08_conexoes import _com_o_teto

    novo = _com_o_teto(_perfil(**ESCOLHAS), CHAVE, "economia")
    assert _secao(novo.controllers) == {**ESCOLHAS, "policy": "economia"}


def test_o_teto_que_volta_ao_global_nao_apaga_as_escolhas() -> None:
    """MORDIDA: volte o ``novo = None`` do «Segue o global» em ``_com_o_teto``."""
    from pacotes.a08_conexoes import _com_o_teto

    novo = _com_o_teto(_perfil(policy="economia", **ESCOLHAS), CHAVE, None)
    assert _secao(novo.controllers) == ESCOLHAS
    assert _com_o_teto(_perfil(**ESCOLHAS), CHAVE, None) is None, (
        "regravou o perfil sem ter força nenhuma a tirar")


def test_sem_nada_mais_a_secao_some() -> None:
    from pacotes.a08_conexoes import _com_o_teto

    novo = _com_o_teto(_perfil(policy="economia"), CHAVE, None)
    assert _secao(novo.controllers) is None
