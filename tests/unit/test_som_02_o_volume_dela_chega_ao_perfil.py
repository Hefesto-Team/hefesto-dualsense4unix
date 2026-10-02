"""SOM-02/E4 — o volume que ela ajusta CHEGA ao perfil salvo."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# (`test_perfil_salva_tudo_registrar_nao_e_aplicar.py`), que tranca a fiação
exigir_gi_real("som 02 o volume dela chega ao perfil")

from typing import Any, Final

import gi

gi.require_version("Gtk", "3.0")

import pytest

pytest.importorskip("cairo")


from hefesto_dualsense4unix.app import audio_saida, ipc_bridge
from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)

VOLUME_VELHO: Final[int] = 60

PORCENTAGEM_NOVA: Final[float] = 90.0

VOLUME_SATURADO: Final[int] = 200

_ENTRY: dict[str, Any] = {
    "index": 0,
    "connected": True,
    "transport": "usb",
    "is_primary": True,
    "uniq": "aabbcc000001",
    "battery_pct": 80,
    "player_slot": 1,
    "lightbar_rgb": [97, 53, 131],
    "lightbar_on": True,
    "inputs": {"buttons": [], "l2": 0, "r2": 0},
    "audio": {
        "fone_plugado": False,
        "mic_externo": False,
        "mic_mudo": False,
        "mic_mudo_desejado": None,
    },
}
_ESTADO: dict[str, Any] = {"native_mode": False}

_janelas_vivas: list[Any] = []


class _ResultadoDoSom:
    """O que ``tocar_confirmacao`` devolve — o card só lê o ``recado``."""

    recado = ""


class _Janela:
    """A `HefestoApp` reduzida ao que o card precisa: o rascunho."""

    def __init__(self, draft: DraftConfig) -> None:
        self.draft = draft
        self._edit_target_uniq = None


class _Seletor:
    """O `Gtk.ComboBoxText` do canal reduzido ao que o handler lê."""

    def __init__(self, canal: str) -> None:
        self._canal = canal

    def get_active_id(self) -> str:
        return self._canal


class _Pedidos:
    """Registra o que a interface MANDOU, e SEGURA o callback de sucesso."""

    def __init__(self, *, ok: bool = True) -> None:
        self.ok = ok
        self.pendentes: list[tuple[Any, Any]] = []
        self.chamadas: list[dict[str, Any]] = []

    def run_in_thread(self, fn: Any, on_ok: Any, _on_err: Any = None) -> None:
        self.pendentes.append((fn, on_ok))

    def speaker_set(self, **kwargs: Any) -> bool:
        self.chamadas.append(kwargs)
        return self.ok

    def rodar(self) -> None:
        """Executa o pedido e devolve o resultado ao callback de sucesso."""
        pendentes, self.pendentes = self.pendentes, []
        for fn, on_ok in pendentes:
            on_ok(fn())


@pytest.fixture
def pedidos(monkeypatch: pytest.MonkeyPatch) -> _Pedidos:
    espiao = _Pedidos()
    monkeypatch.setattr(ipc_bridge, "run_in_thread", espiao.run_in_thread)
    monkeypatch.setattr(ipc_bridge, "speaker_set", espiao.speaker_set)
    monkeypatch.setattr(
        audio_saida, "tocar_confirmacao", lambda *a, **k: _ResultadoDoSom()
    )
    monkeypatch.setattr(audio_saida, "garantir_saida_audivel", lambda *a, **k: None)
    return espiao


@pytest.fixture
def pedidos_recusados(monkeypatch: pytest.MonkeyPatch) -> _Pedidos:
    espiao = _Pedidos(ok=False)
    monkeypatch.setattr(ipc_bridge, "run_in_thread", espiao.run_in_thread)
    monkeypatch.setattr(ipc_bridge, "speaker_set", espiao.speaker_set)
    monkeypatch.setattr(
        audio_saida, "tocar_confirmacao", lambda *a, **k: _ResultadoDoSom()
    )
    return espiao


def _perfil(**speaker: Any) -> Profile:
    """O perfil dela, com (ou sem) a seção de alto-falante."""
    return Profile(
        name="pragmata",
        match=MatchCriteria(window_class=["pragmata_class"]),
        priority=10,
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Off"), right=TriggerConfig(mode="Off")
        ),
        leds=LedsConfig(lightbar=(0, 0, 0), player_leds=[False] * 5),
        speaker=speaker or None,  # type: ignore[arg-type]
    )


def test_perfil_com_rota_volta_para_o_rascunho_ao_abrir() -> None:
    """Round-trip: o canal salvo reaparece no rascunho, sem virar toque dela."""
    draft = DraftConfig.from_profile(_perfil(volume=120, rota=2))
    assert draft.speaker.rota == 2
    assert draft.speaker.dirty is False
    assert draft.to_profile("pragmata").speaker.rota == 2


def test_perfil_sem_rota_nao_grava_a_chave_nova() -> None:
    """Perfil sem opinião de canal sai do ``to_profile`` idêntico ao que era."""
    salvo = DraftConfig.from_profile(_perfil(volume=120)).to_profile("pragmata")
    assert "rota" not in salvo.speaker.model_dump(mode="json")


class _CardEspiao:
    """O card reduzido ao que a fiação da aba toca."""

    def __init__(self) -> None:
        self.dono: Any = None
        self.updates = 0

    def update(self, *_a: Any, **_k: Any) -> None:
        self.updates += 1

    def definir_dono_do_rascunho(self, janela: Any) -> None:
        self.dono = janela


class _SlotComAttach:
    """O `GtkGrid` do Glade reduzido: `_sync_status_cards` só exige o `attach`."""

    def attach(self, *_a: Any, **_k: Any) -> None:  # pragma: no cover - inerte
        raise AssertionError("rebuild não devia acontecer com as chaves estáveis")


class _BuilderDaAba:
    def __init__(self, slot: Any) -> None:
        self._slot = slot

    def get_object(self, wid: str) -> Any:
        return self._slot if wid == "status_players_slot" else None


class _AbaStatus(StatusActionsMixin):
    """A janela do produto reduzida ao que este caminho toca."""

    def __init__(self, card: _CardEspiao, draft: DraftConfig) -> None:
        self.builder = _BuilderDaAba(_SlotComAttach())
        self.draft = draft
        self._mic_monitor = None
        chave = (0, str(_ENTRY["uniq"]))
        self._status_cards = {chave: card}
        self._status_card_keys = [chave]
        self._edit_target_uniq = None


def _estado_com_um_controle() -> dict[str, Any]:
    return {"controllers": [dict(_ENTRY)]}


