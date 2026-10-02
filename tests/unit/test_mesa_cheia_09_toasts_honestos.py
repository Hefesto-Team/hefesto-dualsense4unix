"""MESA-CHEIA-09/E3 — os toasts param de afirmar o que não aconteceu.

Metade de tela do
`test_mesa_cheia_09_aplicado_e_verdade.py` (que prova o daemon). Aqui prova-se
o que a JANELA diz, nos casos que a D-9 nomeia:

* **alvo fora da mesa** — *"Guardado — vai valer quando o Controle N voltar"*;
* **co-op ligado** — a aba Lightbar dizia *"Desenho das luzes aplicado"* no
  toast e *"com o co-op ligado, é ele que manda nas 5 luzes"* no rótulo três
  centímetros abaixo. A MESMA tela, contradizendo a si mesma;
* **Modo Nativo ligado** (entrou no conserto 1.3) — o jogo é o dono do
  `hidraw` e o backend muta toda escrita de output.

O vocabulário está num lugar só (`app/textos_de_aplicacao.py`) — a regra de
execução da própria D-9. Este arquivo também PROVA isso: as frases dos gestos
saem daquele módulo, e trocá-lo troca todas.

CONSERTO 1.5, e são três coisas que faltavam:

* o QUINTO gesto de saída da aba Lightbar — o botão "Apagar" — dizia "Lightbar
  apagada" pela mesma rota por-MAC do vizinho já curado (`TestOQuintoGesto…`);
* as razões SOMAM: co-op ligado E alvo fora da mesa é o estado normal da mesa
  dela, e a cadeia `if/elif` prometia só a primeira liberação
  (`TestAsPendenciasSomam` — e ali estão as QUATRO somas possíveis, inclusive a
  trinca, que na primeira volta do conserto ficou sem mordida nenhuma);
* mapa de conectados VAZIO não é "não sei quem está na mesa" — é "nenhum
  DualSense na mesa", e a guarda que os confundia devolvia a frase de sucesso
  no exato caso em que o daemon responde `guardado_em=[uniq]`.

GUI: precisa de `gi` real (padrão de `test_lightbar_todos_por_mac_r14.py`).
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("toasts honestos da mesa cheia 09")

import json
from pathlib import Path
from typing import Any

import pytest

gi = pytest.importorskip("gi")

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app import draft_config as draft_mod
from hefesto_dualsense4unix.app.actions import lightbar_actions, triggers_actions
from hefesto_dualsense4unix.app.actions.lightbar_actions import LightbarActionsMixin
from hefesto_dualsense4unix.app.textos_de_aplicacao import (
    GUARDADO,
    guardado_ate_o_alvo_voltar,
    nome_curto_do_alvo,
)
from hefesto_dualsense4unix.profiles.schema import LedsConfig, MatchAny, Profile

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "state_full_quatro_controles.json"
)
UNIQS: list[str] = [
    c["uniq"] for c in json.loads(FIXTURE.read_text(encoding="utf-8"))["controllers"]
]
NA_MESA, FORA_DA_MESA = UNIQS[0], UNIQS[1]
ROTULO_DO_AUSENTE = "Controle 2 (BT)"


class _Host(LightbarActionsMixin):
    """Host mínimo com o estado que a aba Status mantém do `state_full`."""

    def __init__(
        self,
        *,
        alvo: str | None,
        conectados: dict[int, str | None],
        coop: bool = False,
        nativo: bool = False,
    ) -> None:
        perfil = Profile(
            name="mesa",
            match=MatchAny(),
            priority=1,
            leds=LedsConfig(
                lightbar=(255, 0, 0),
                player_leds=[True, False, False, False, False],
                lightbar_brightness=1.0,
                auto_player_colors=False,
            ),
        )
        self.draft = draft_mod.DraftConfig.from_profile(perfil)
        self._edit_target_uniq = alvo
        self._edit_target_label = ROTULO_DO_AUSENTE
        self._target_uniq_by_index = conectados
        self._coop_ligado = coop
        self._modo_nativo_ligado = nativo
        _MESA_DO_DAEMON["conectados"] = {
            v for v in conectados.values() if isinstance(v, str) and v
        }
        _MESA_DO_DAEMON["nativo"] = nativo
        self._current_rgb = (255, 0, 0)
        self._current_brightness = 0.8
        self._widgets: dict[str, Any] = {}
        self._toasts: list[str] = []
        self._refresh_guard = False

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _toast_light(self, msg: str) -> None:
        self._toasts.append(msg)


_MESA_DO_DAEMON: dict[str, Any] = {"conectados": set(), "nativo": False}


def _corpo_por_uniq(uniq: str | None) -> dict[str, Any]:
    """A resposta que o daemon monta para um ``led.set``/``led.player_set``."""
    if uniq and uniq in _MESA_DO_DAEMON["conectados"]:
        return {"status": "ok", "aplicado_em": [uniq], "guardado_em": []}
    if uniq:
        return {"status": "ok", "aplicado_em": [], "guardado_em": [uniq]}
    return {"status": "ok", "aplicado_em": [], "guardado_em": []}


@pytest.fixture(autouse=True)
def _ipc_mudo(monkeypatch: pytest.MonkeyPatch) -> None:
    """O daemon responde como o daemon — o que está em julgamento é a FRASE."""
    monkeypatch.setattr(
        lightbar_actions,
        "led_set_detalhado",
        lambda _rgb, brightness=None, uniq=None: _corpo_por_uniq(uniq),
    )
    monkeypatch.setattr(
        lightbar_actions,
        "player_leds_set_detalhado",
        lambda _bits, uniq=None: _corpo_por_uniq(uniq),
    )


class _BarraDeStatus:
    def __init__(self) -> None:
        self.mensagens: list[str] = []

    def get_context_id(self, _k: str) -> int:
        return 1

    def push(self, _ctx: int, msg: str) -> None:
        self.mensagens.append(msg)


class TestOVocabularioMoraNumLugarSo:
    def test_o_nome_do_alvo_perde_o_transporte(self) -> None:
        assert nome_curto_do_alvo("Controle 2 (BT)") == "Controle 2"
        assert nome_curto_do_alvo(None) == "esse controle"

    def test_o_alvo_sem_nome_nao_compoe_portugues_quebrado(self) -> None:
        """CONSERTO 1.5 — o fallback compunha *"quando o esse controle"""
        assert guardado_ate_o_alvo_voltar("Cor", nome_curto_do_alvo(None)) == (
            "Cor — guardado, vai valer quando esse controle voltar."
        )
        assert guardado_ate_o_alvo_voltar("Cor", "Controle 2") == (
            "Cor — guardado, vai valer quando o Controle 2 voltar."
        )

    def test_os_modulos_que_o_importam_usam_a_mesma_palavra(self) -> None:
        """Se alguém escrever "guardado" à mão em outro arquivo, esta conta"""
        importadores = {
            caminho.name
            for caminho in Path(lightbar_actions.__file__).parent.parent.rglob(
                "*.py"
            )
            if "textos_de_aplicacao" in caminho.read_text(encoding="utf-8")
            and caminho.name != "textos_de_aplicacao.py"
        }
        assert importadores == {"lightbar_actions.py", "triggers_actions.py"}
        for modulo in (lightbar_actions, triggers_actions):
            fonte = Path(modulo.__file__).read_text(encoding="utf-8")
            assert "textos_de_aplicacao" in fonte, modulo.__name__
            escrita_a_mao = [
                trecho
                for trecho in fonte.split(f'"{GUARDADO}')[1:]
                if not trecho.startswith("_em")
            ]
            assert not escrita_a_mao, (
                f"{modulo.__name__} escreveu a palavra em vez de importá-la"
            )
