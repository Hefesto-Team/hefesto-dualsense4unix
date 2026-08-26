"""Os dois gates do PS solo: QUEM pode disparar, e QUANTO tempo cabe num toque.

**Parte 1 — M5 (auditoria + review).** O gate do PS-solo suprime a ação de
sistema quando o controle está DEDICADO a um jogo (Modo Nativo ou modo
jogo/`_emulation_suppressed`), mas NÃO no desktop. O gate usa flags EM MEMÓRIA
(sem subprocess): o `is_steam_running`/pgrep anterior bloqueava o poll loop até
2s (REVIEW-M5-PGREP-BLOCK-01) e deixava passar jogos não-Steam
(REVIEW-M5-NONSTEAM-FOCUS-01).

**Parte 2 — PS-TOQUE-CURTO-01 (E1/E2), 26/08/2026.** O outro gate, e ele é de
DURAÇÃO. O controle cai no rádio; ela segura o botão PS por cinco segundos para
religá-lo — que é como se liga um DualSense —, solta, e **a Steam abre**. Com a
Steam já aberta, abre uma segunda. Aconteceu duas vezes em 45 segundos.

Por que acontecia: `_observe_ps_solo` calculava `held_ms` no release, LOGAVA o
valor e disparava `_fire_ps_solo()` sem comparar com teto nenhum. A única
barreira era `_ps_long_press_fired`, e ela nunca arma — o long-press nasce
desligado (`ps_long_press_ms = 0`, por causa do modo-jogo acidental). As duas
decisões estão certas isoladamente; o defeito é a COMPOSIÇÃO: desligar o
long-press removeu, sem querer, o único teto que existia.

A mordida: `test_segurar_para_religar_nao_abre_a_steam` põe os dois holds lado a
lado — 5.038 ms (o religamento medido no journal dela) e 200 ms (um toque
humano). Arrancado o teto de `_observe_ps_solo`, o caso longo dispara e o teste
reprova imprimindo os dois `held_ms` juntos.

As duas partes moram no mesmo arquivo porque respondem à mesma pergunta — *este
release do PS vira ação?* — e separá-las faria a próxima pessoa curar uma e
esquecer a outra.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import structlog

from hefesto_dualsense4unix.daemon.subsystems import hotkey
from hefesto_dualsense4unix.integrations import steam_launcher
from hefesto_dualsense4unix.integrations.hotkey_daemon import (
    DEFAULT_PS_TOQUE_CURTO_TETO_MS,
    ENV_PS_TOQUE_CURTO_TETO_MS,
    HotkeyConfig,
    HotkeyManager,
    _teto_do_toque_curto_do_ambiente,
)


def _daemon(*, suppressed: bool = False, native: bool = False, action: str = "steam") -> Any:
    return SimpleNamespace(
        config=SimpleNamespace(ps_button_action=action, ps_button_command=""),
        _emulation_suppressed=suppressed,
        store=SimpleNamespace(native_mode_active=native),
    )


def _patch_steam(monkeypatch) -> list[Any]:
    opened: list[Any] = []
    monkeypatch.setattr(
        steam_launcher, "open_or_focus_steam", lambda: opened.append(True) or True
    )
    # Guard-rail do review: o gate NÃO pode chamar subprocess (pgrep) no poll loop.
    def _boom(*_a, **_kw):  # pragma: no cover
        raise AssertionError("gate do PS-solo não pode rodar subprocess/pgrep")

    monkeypatch.setattr(steam_launcher, "_default_pgrep", _boom)
    return opened


def test_ps_solo_abre_steam_no_desktop(monkeypatch):
    """Sem modo jogo e sem nativo → a ação roda (abre a Steam)."""
    opened = _patch_steam(monkeypatch)
    hotkey.build_ps_solo_callback(_daemon())()
    assert opened == [True]


def test_ps_solo_suprimido_em_modo_jogo(monkeypatch):
    """Emulação suprimida (modo jogo — inclui jogos NÃO-Steam) → suprime."""
    opened = _patch_steam(monkeypatch)
    hotkey.build_ps_solo_callback(_daemon(suppressed=True))()
    assert opened == []


def test_ps_solo_suprimido_no_modo_nativo(monkeypatch):
    opened = _patch_steam(monkeypatch)
    hotkey.build_ps_solo_callback(_daemon(native=True))()
    assert opened == []


def test_ps_solo_none_nao_faz_nada(monkeypatch):
    opened = _patch_steam(monkeypatch)
    hotkey.build_ps_solo_callback(_daemon(action="none"))()
    assert opened == []


# ===========================================================================
# PS-TOQUE-CURTO-01 — o gate de DURAÇÃO do toque curto
# ===========================================================================

# O hold do religamento, em segundos, como saiu do journal dela em 02/08/2026.
HOLD_RELIGAMENTO_S = 5.0382
# Um clique intencional humano fica em 80-250 ms.
HOLD_TOQUE_S = 0.200


def _press_release(mgr: HotkeyManager, *, hold_s: float) -> str | None:
    """Press do PS em t=0 e release em t=hold_s. Devolve o evento do release."""
    mgr.observe(["ps"], now=0.0)
    return mgr.observe([], now=hold_s)


# ---------------------------------------------------------------------------
# E1 — a mordida
# ---------------------------------------------------------------------------


def test_segurar_para_religar_nao_abre_a_steam() -> None:
    """5.038 ms NÃO é toque; 200 ms É. Os dois no mesmo teste, de propósito.

    Um teste que só afirmasse "o hold longo não dispara" passaria com a cura
    virando "o botão PS parou de funcionar". Um que só afirmasse "o toque curto
    dispara" passaria com a cura arrancada. Os dois juntos mordem dos dois
    lados.
    """
    longo: list[str] = []
    mgr_longo = HotkeyManager(on_ps_solo=lambda: longo.append("solo"))
    evento_longo = _press_release(mgr_longo, hold_s=HOLD_RELIGAMENTO_S)

    curto: list[str] = []
    mgr_curto = HotkeyManager(on_ps_solo=lambda: curto.append("solo"))
    evento_curto = _press_release(mgr_curto, hold_s=HOLD_TOQUE_S)

    teto = HotkeyConfig().ps_toque_curto_teto_ms
    assert longo == [] and evento_longo is None, (
        "o gesto de RELIGAR o controle abriu a Steam: "
        f"hold de {HOLD_RELIGAMENTO_S * 1000:.1f} ms passou pelo teto de "
        f"{teto} ms (o toque humano de comparação é "
        f"{HOLD_TOQUE_S * 1000:.1f} ms)"
    )
    assert curto == ["solo"] and evento_curto == "ps_solo", (
        "o toque curto de verdade parou de abrir a Steam: hold de "
        f"{HOLD_TOQUE_S * 1000:.1f} ms recusado por um teto de {teto} ms "
        f"(o religamento de comparação é {HOLD_RELIGAMENTO_S * 1000:.1f} ms)"
    )


def test_o_teto_default_cabe_no_toque_e_nao_no_religamento() -> None:
    """O número tem de ficar ENTRE as duas durações medidas, ou não separa nada."""
    assert (
        HOLD_TOQUE_S * 1000
        < DEFAULT_PS_TOQUE_CURTO_TETO_MS
        < HOLD_RELIGAMENTO_S * 1000
    )
    assert HotkeyConfig().ps_toque_curto_teto_ms == DEFAULT_PS_TOQUE_CURTO_TETO_MS


def test_o_release_exatamente_no_teto_ainda_e_toque() -> None:
    """A borda pertence ao toque: `>` teto recusa, `==` teto honra."""
    fired: list[str] = []
    mgr = HotkeyManager(
        on_ps_solo=lambda: fired.append("solo"),
        config=HotkeyConfig(ps_toque_curto_teto_ms=700),
    )
    assert _press_release(mgr, hold_s=0.700) == "ps_solo"
    assert fired == ["solo"]


def test_teto_zero_desliga_o_gate_e_restaura_o_comportamento_antigo() -> None:
    """Mesma semântica de `ps_long_press_ms`: 0 desliga o gesto."""
    fired: list[str] = []
    mgr = HotkeyManager(
        on_ps_solo=lambda: fired.append("solo"),
        config=HotkeyConfig(ps_toque_curto_teto_ms=0),
    )
    assert _press_release(mgr, hold_s=HOLD_RELIGAMENTO_S) == "ps_solo"
    assert fired == ["solo"]


def test_o_hold_longo_nao_arma_o_proximo_toque() -> None:
    """Recusar um release não pode deixar estado sujo para o toque seguinte."""
    fired: list[str] = []
    mgr = HotkeyManager(on_ps_solo=lambda: fired.append("solo"))

    mgr.observe(["ps"], now=0.0)
    assert mgr.observe([], now=HOLD_RELIGAMENTO_S) is None
    assert fired == []

    # Agora um toque de verdade, logo em seguida.
    mgr.observe(["ps"], now=6.0)
    assert mgr.observe([], now=6.2) == "ps_solo"
    assert fired == ["solo"]


def test_o_teto_nao_atrapalha_o_long_press_quando_ele_esta_ligado() -> None:
    """Com o long-press LIGADO, quem suprime o release continua sendo ele.

    O teto não transforma o gesto em nada: o long-press já disparou durante o
    hold, e o release só confirma a supressão que já existia.
    """
    solo: list[str] = []
    longp: list[str] = []
    mgr = HotkeyManager(
        on_ps_solo=lambda: solo.append("solo"),
        on_ps_long_press=lambda: longp.append("long"),
        config=HotkeyConfig(ps_long_press_ms=1000),
    )
    mgr.observe(["ps"], now=0.0)
    assert mgr.observe(["ps"], now=1.0) == "ps_long_press"
    assert mgr.observe([], now=HOLD_RELIGAMENTO_S) is None
    assert longp == ["long"]
    assert solo == []


# ---------------------------------------------------------------------------
# E2 — a recusa APARECE no journal
# ---------------------------------------------------------------------------


def test_a_recusa_do_hold_longo_vai_para_o_journal() -> None:
    """Um hold engolido em silêncio manda a próxima investigação ao lugar errado.

    O evento carrega `held_ms` E `teto_ms`: sem o segundo não dá para saber, no
    journal, se o teto de então era o de hoje.
    """
    mgr = HotkeyManager(on_ps_solo=lambda: None)
    with structlog.testing.capture_logs() as registros:
        _press_release(mgr, hold_s=HOLD_RELIGAMENTO_S)

    recusas = [r for r in registros if r.get("event") == "ps_solo_ignorado_hold_longo"]
    assert len(recusas) == 1, f"eventos vistos: {[r.get('event') for r in registros]}"
    assert recusas[0]["teto_ms"] == DEFAULT_PS_TOQUE_CURTO_TETO_MS
    assert recusas[0]["held_ms"] == round(HOLD_RELIGAMENTO_S * 1000, 1)


def test_as_tres_saidas_do_botao_tem_eventos_distintos() -> None:
    """Toque honrado, hold longo recusado e combo suprimido — três nomes."""
    def _eventos(fn) -> list[str]:
        with structlog.testing.capture_logs() as registros:
            fn()
        return [r.get("event") for r in registros]

    honrado = _eventos(
        lambda: _press_release(HotkeyManager(on_ps_solo=lambda: None), hold_s=0.2)
    )
    recusado = _eventos(
        lambda: _press_release(
            HotkeyManager(on_ps_solo=lambda: None), hold_s=HOLD_RELIGAMENTO_S
        )
    )

    assert "ps_solo_released" in honrado
    assert "ps_solo_ignorado_hold_longo" not in honrado
    assert "ps_solo_ignorado_hold_longo" in recusado
    assert "ps_solo_released" not in recusado


# ---------------------------------------------------------------------------
# A configuração — mesmo lugar e mesma forma do `ps_long_press_ms`
# ---------------------------------------------------------------------------


def test_o_teto_sai_da_env_var(monkeypatch) -> None:
    monkeypatch.setenv(ENV_PS_TOQUE_CURTO_TETO_MS, "450")
    assert _teto_do_toque_curto_do_ambiente() == 450
    assert HotkeyConfig().ps_toque_curto_teto_ms == 450


def test_env_ilegivel_cai_no_default_em_vez_de_desligar_o_teto(monkeypatch) -> None:
    """Um valor ilegível não pode DESLIGAR o teto por acidente — desligar é `=0`."""
    monkeypatch.setenv(ENV_PS_TOQUE_CURTO_TETO_MS, "setecentos")
    assert _teto_do_toque_curto_do_ambiente() == DEFAULT_PS_TOQUE_CURTO_TETO_MS
