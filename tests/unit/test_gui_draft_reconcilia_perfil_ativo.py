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


def _app_class() -> Any:
    """`HefestoApp` — ou pula quando o GTK real falta (CI headless).

    Padrão do repo (test_app_scroll_wrap): `app.app` importa
    `from gi.repository import GdkPixbuf, Gtk` no TOPO, e o CI headless tem `gi`
    mas não os typelibs. Importar aqui, dentro de um helper com try/except,
    evita quebrar a COLETA — `importorskip` de submódulo conflitaria com o Gtk
    4.0 já carregado.
    """
    try:
        from hefesto_dualsense4unix.app.app import HefestoApp
    except (ImportError, ValueError) as exc:  # pragma: no cover - ambiente
        pytest.skip(f"gi/GdkPixbuf indisponível: {exc}")
    return HefestoApp


def _draft_default() -> Any:
    from hefesto_dualsense4unix.app.draft_config import DraftConfig

    return DraftConfig.default()


class _AppFalsa:
    """Superfície mínima que `_reconciliar_draft_com_perfil_ativo` toca.

    Os métodos sob teste vêm da classe REAL (`HefestoApp`) — é o código de
    produção que roda aqui — mas ligados tarde, no `__init__`, para o import
    só acontecer quando um teste roda (nunca na coleta).
    """

    def __init__(self, ativo: str = "FPS") -> None:
        app_cls = _app_class()
        self._reconciliar_draft_com_perfil_ativo = (
            app_cls._reconciliar_draft_com_perfil_ativo.__get__(self)
        )
        self._tem_edicao_pendente = app_cls._tem_edicao_pendente.__get__(self)
        self.draft = _draft_default()
        self._draft_baseline: Any = self.draft
        self._active_profile_name = ativo
        self._draft_reload_for: str | None = None
        self._draft_reload_inflight = False
        self._draft_reload_inflight_since = 0.0
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


class _Relogio:
    """Relógio injetável — o tempo destes testes é o do TESTE, não o da máquina.

    JANELA-FIEL-01/E1: `test_nao_redispara_para_o_mesmo_alvo` dizia "5 segundos
    de ticks" e rodava dez chamadas em microssegundos de relógio real. Qualquer
    latch com PRAZO passaria nele sem nunca ser exercitado — o teste ficaria
    verde sem medir nada. Com o relógio na mão do teste, o prazo é atravessado
    de propósito.
    """

    def __init__(self, agora: float = 1000.0) -> None:
        self.agora = agora

    def monotonic(self) -> float:
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += segundos


@pytest.fixture
def relogio(monkeypatch: pytest.MonkeyPatch) -> _Relogio:
    """Troca o `time` que `app.py` enxerga por um relógio de mentira."""
    _app_class()  # pula quando o GTK real falta, antes de importar o módulo
    from hefesto_dualsense4unix.app import app as app_mod

    falso = _Relogio()
    monkeypatch.setattr(app_mod, "time", falso)
    return falso


def test_perfil_igual_nao_dispara_nada() -> None:
    app = _AppFalsa(ativo="FPS")
    app._reconciliar_draft_com_perfil_ativo({"active_profile": "FPS"})
    assert app.bootstraps == []
    assert app.toasts == []


def test_troca_de_perfil_sem_edicao_recarrega_o_draft() -> None:
    """O caso do autoswitch: ela abre o Sackboy e a GUI acompanha.

    NUNCA-TROCA-O-ALVO-01 (06/08/2026) — nota datada sobre o que caducou:
    até aqui este teste exigia `app.toasts == []`, ou seja, que a troca fosse
    MUDA. A decisão medida que continua de pé é a outra (não recarregar por
    baixo de uma edição pendente); o silêncio nunca foi medido, e virou defeito
    quando se mediu o outro lado: recarregar em silêncio move o alvo dos DOIS
    botões de salvar sem gesto dela, e o diálogo do rodapé passa a nascer
    perguntando "substituir 'sackboy_nativo'?" logo depois de ela ter ativado
    'vitoria' na mão. Seguro para os dados, enganoso para ela. A troca continua
    acontecendo — agora ela é anunciada.
    """
    app = _AppFalsa(ativo="FPS")
    app._reconciliar_draft_com_perfil_ativo({"active_profile": "sackboy_nativo"})
    assert app.bootstraps == ["sackboy_nativo"], (
        "sem recarregar, as abas passam a editar e salvar o perfil ERRADO"
    )
    assert len(app.toasts) == 1, "a janela trocou o alvo do Salvar em silêncio"
    contexto, msg = app.toasts[0]
    assert contexto == "draft-reload"
    assert "sackboy_nativo" in msg and "Salvar" in msg


def test_edicao_pendente_avisa_em_vez_de_descartar() -> None:
    app = _AppFalsa(ativo="FPS")
    _sujar(app)
    app._reconciliar_draft_com_perfil_ativo({"active_profile": "sackboy_nativo"})
    assert app.bootstraps == [], "recarregar por baixo da edição é perda de trabalho"
    assert len(app.toasts) == 1
    contexto, msg = app.toasts[0]
    assert contexto == "draft-reload"
    assert "sackboy_nativo" in msg and "FPS" in msg


def test_nao_redispara_enquanto_o_worker_nao_voltou(relogio: _Relogio) -> None:
    """O tick roda a 2 Hz e o carregamento é assíncrono."""
    from hefesto_dualsense4unix.app import app as app_mod

    app = _AppFalsa(ativo="FPS")
    app._draft_reload_inflight = True
    app._draft_reload_inflight_since = relogio.monotonic()
    app._reconciliar_draft_com_perfil_ativo({"active_profile": "sackboy_nativo"})
    assert app.bootstraps == []

    # ...mas o "em voo" tem PRAZO: uma chamada que nunca volta não pode calar a
    # reconciliação pelo resto da sessão. Passado o prazo, sai outra.
    relogio.avancar(app_mod.DRAFT_RELOAD_INFLIGHT_TIMEOUT_S + 0.1)
    app._reconciliar_draft_com_perfil_ativo({"active_profile": "sackboy_nativo"})
    assert app.bootstraps == ["sackboy_nativo"], (
        "worker que não volta prendia o latch e a janela seguia no perfil anterior"
    )


def test_nao_redispara_para_o_mesmo_alvo(relogio: _Relogio) -> None:
    """Guarda contra o loop de IPC+I/O a 2 Hz.

    `_active_profile_name` só é escrito quando o draft carrega com SUCESSO. Um
    perfil ativo que não existe em disco o deixaria stale para sempre — por
    isso o alvo do disparo é rastreado num campo separado.

    O relógio avança de VERDADE aqui (era "5 segundos de ticks" em
    microssegundos reais): nem o prazo do latch em voo pode transformar uma
    falha permanente em loop.
    """
    app = _AppFalsa(ativo="FPS")
    app._reconciliar_draft_com_perfil_ativo({"active_profile": "fantasma"})
    assert app.bootstraps == ["fantasma"]

    # Worker voltou sem draft (perfil não existe): `_active_profile_name`
    # continua "FPS", mas o alvo já foi tentado.
    app._draft_reload_inflight = False
    for _ in range(10):
        relogio.avancar(0.5)  # 5 segundos de ticks, no relógio do teste
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
