"""R-08 (auditoria 23/07) — o draft da GUI reconcilia com o perfil ATIVO.

`_bootstrap_draft_async` era o único ponto que populava `self.draft`, e só
rodava em `show()`/`run()`. Mas o perfil ativo muda por QUATRO caminhos que a
GUI conhece: botão "Ativar" da aba Perfis, menu do tray, hotkey PS+D-pad e o
**autoswitch quando ela abre o jogo**.

Sem recarregar, o resultado é exatamente a queixa dela:

1. GUI aberta com FPS ativo → abre o Sackboy (autoswitch ativa `sackboy_nativo`)
   → alt-tab para a GUI, que continua mostrando FPS;
2. ela ajusta a cor e clica "Aplicar" → o daemon recebe as seções GLOBAIS do
   FPS **por cima do perfil do jogo**;
3. clica "Salvar Perfil" → o diálogo vem preenchido com "FPS", não com o perfil
   do jogo.

A reconciliação NÃO pode ser incondicional: recarregar por baixo de uma edição
em andamento troca um jeito de perder trabalho por outro. Por isso o gate de
edição pendente é obrigatório, e a divergência com edição pendente vira AVISO.

Não exercita GTK real — o mixin de reconciliação é exercitado sobre um dublê
com a superfície mínima, no mesmo estilo de `test_mouse_actions_gui_sync.py`.
"""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("gi")

from hefesto_dualsense4unix.app.app import HefestoApp
from hefesto_dualsense4unix.app.draft_config import DraftConfig


class _AppFalsa:
    """Superfície mínima que `_reconciliar_draft_com_perfil_ativo` toca."""

    # Os três métodos sob teste vêm da classe real — é o código de produção
    # que roda aqui, não uma reimplementação.
    _reconciliar_draft_com_perfil_ativo = (
        HefestoApp._reconciliar_draft_com_perfil_ativo
    )
    _tem_edicao_pendente = HefestoApp._tem_edicao_pendente

    def __init__(self, ativo: str = "FPS") -> None:
        self.draft = DraftConfig.default()
        self._draft_baseline: DraftConfig | None = self.draft
        self._active_profile_name = ativo
        self._draft_reload_for: str | None = None
        self._draft_reload_inflight = False
        self.bootstraps: list[str | None] = []
        self.toasts: list[tuple[str, str]] = []

    def _bootstrap_draft_async(self) -> None:
        self.bootstraps.append(self._draft_reload_for)

    def _status_toast(self, contexto: str, msg: str) -> None:
        self.toasts.append((contexto, msg))


def _sujar(app: _AppFalsa) -> None:
    """Simula edição de aba: as abas gravam SÓ em `self.draft`."""
    app.draft = app.draft.model_copy(
        update={"leds": app.draft.leds.model_copy(update={"lightbar_rgb": [9, 9, 9]})}
    )


def test_perfil_igual_nao_dispara_nada() -> None:
    app = _AppFalsa(ativo="FPS")
    app._reconciliar_draft_com_perfil_ativo({"active_profile": "FPS"})
    assert app.bootstraps == []
    assert app.toasts == []


def test_troca_de_perfil_sem_edicao_recarrega_o_draft() -> None:
    """O caso do autoswitch: ela abre o Sackboy e a GUI acompanha."""
    app = _AppFalsa(ativo="FPS")
    app._reconciliar_draft_com_perfil_ativo({"active_profile": "sackboy_nativo"})
    assert app.bootstraps == ["sackboy_nativo"], (
        "sem recarregar, as abas passam a editar e salvar o perfil ERRADO"
    )
    assert app.toasts == []


def test_edicao_pendente_avisa_em_vez_de_descartar() -> None:
    app = _AppFalsa(ativo="FPS")
    _sujar(app)
    app._reconciliar_draft_com_perfil_ativo({"active_profile": "sackboy_nativo"})
    assert app.bootstraps == [], "recarregar por baixo da edição é perda de trabalho"
    assert len(app.toasts) == 1
    contexto, msg = app.toasts[0]
    assert contexto == "draft-reload"
    assert "sackboy_nativo" in msg and "FPS" in msg


def test_nao_redispara_enquanto_o_worker_nao_voltou() -> None:
    """O tick roda a 2 Hz e o carregamento é assíncrono."""
    app = _AppFalsa(ativo="FPS")
    app._draft_reload_inflight = True
    app._reconciliar_draft_com_perfil_ativo({"active_profile": "sackboy_nativo"})
    assert app.bootstraps == []


def test_nao_redispara_para_o_mesmo_alvo() -> None:
    """Guarda contra o loop de IPC+I/O a 2 Hz.

    `_active_profile_name` só é escrito quando o draft carrega com SUCESSO. Um
    perfil ativo que não existe em disco o deixaria stale para sempre — por
    isso o alvo do disparo é rastreado num campo separado.
    """
    app = _AppFalsa(ativo="FPS")
    app._reconciliar_draft_com_perfil_ativo({"active_profile": "fantasma"})
    assert app.bootstraps == ["fantasma"]

    # Worker voltou sem draft (perfil não existe): `_active_profile_name`
    # continua "FPS", mas o alvo já foi tentado.
    app._draft_reload_inflight = False
    for _ in range(10):  # 5 segundos de ticks
        app._reconciliar_draft_com_perfil_ativo({"active_profile": "fantasma"})
    assert app.bootstraps == ["fantasma"], "redisparo em loop de IPC + I/O de disco"


@pytest.mark.parametrize("valor", [None, "", 123, {}])
def test_estado_sem_perfil_util_e_ignorado(valor: Any) -> None:
    app = _AppFalsa(ativo="FPS")
    app._reconciliar_draft_com_perfil_ativo({"active_profile": valor})
    assert app.bootstraps == []
    assert app.toasts == []


def test_sem_baseline_nao_ha_edicao_pendente() -> None:
    """Antes do primeiro carregamento não existe "sujo" — só desconhecido."""
    app = _AppFalsa(ativo="FPS")
    app._draft_baseline = None
    _sujar(app)
    assert app._tem_edicao_pendente() is False
    app._reconciliar_draft_com_perfil_ativo({"active_profile": "sackboy_nativo"})
    assert app.bootstraps == ["sackboy_nativo"]
