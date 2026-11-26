"""Testes do HotkeyManager."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from hefesto_dualsense4unix.daemon.subsystems.gamepad import sem_o_gesto_do_ps
from hefesto_dualsense4unix.integrations.hotkey_daemon import (
    DEFAULT_BUFFER_MS,
    HotkeyConfig,
    HotkeyManager,
    quem_faz_o_gesto,
)

UM = "aabbcc000001"
OUTRO = "aabbcc000002"


def test_combo_nao_dispara_antes_do_buffer():
    fired = []
    mgr = HotkeyManager(on_next=lambda: fired.append("next"))

    assert mgr.observe(["ps", "dpad_up"], now=0.0) is None
    assert fired == []

    assert mgr.observe(["ps", "dpad_up"], now=0.1) is None
    assert fired == []


def test_combo_dispara_apos_buffer():
    fired = []
    mgr = HotkeyManager(on_next=lambda: fired.append("next"))

    mgr.observe(["ps", "dpad_up"], now=0.0)
    result = mgr.observe(["ps", "dpad_up"], now=0.2)
    assert result == "next"
    assert fired == ["next"]


def test_combo_so_dispara_uma_vez_enquanto_segurado():
    fired = []
    mgr = HotkeyManager(on_next=lambda: fired.append("n"))
    mgr.observe(["ps", "dpad_up"], now=0.0)
    mgr.observe(["ps", "dpad_up"], now=0.2)
    mgr.observe(["ps", "dpad_up"], now=0.3)
    mgr.observe(["ps", "dpad_up"], now=0.5)
    assert fired == ["n"]


def test_combo_pode_redisparar_apos_release():
    fired = []
    mgr = HotkeyManager(on_next=lambda: fired.append("n"))
    mgr.observe(["ps", "dpad_up"], now=0.0)
    mgr.observe(["ps", "dpad_up"], now=0.2)
    mgr.observe([], now=0.25)
    mgr.observe(["ps", "dpad_up"], now=0.3)
    mgr.observe(["ps", "dpad_up"], now=0.5)
    assert fired == ["n", "n"]


def test_combo_prev_separado():
    hits = {"next": 0, "prev": 0}
    mgr = HotkeyManager(
        on_next=lambda: hits.__setitem__("next", hits["next"] + 1),
        on_prev=lambda: hits.__setitem__("prev", hits["prev"] + 1),
    )
    mgr.observe(["ps", "dpad_down"], now=0.0)
    mgr.observe(["ps", "dpad_down"], now=0.2)
    assert hits == {"next": 0, "prev": 1}


def test_botao_solo_nao_dispara():
    fired = []
    mgr = HotkeyManager(on_next=lambda: fired.append("n"))
    for t in (0.0, 0.1, 0.2, 0.3):
        mgr.observe(["ps"], now=t)
    assert fired == []


def _ao_jogo(mgr: HotkeyManager | None, botoes: frozenset[str]) -> frozenset[str]:
    """O que o pad virtual recebe: o filtro que o `dispatch_gamepad` e o co-op chamam."""
    return sem_o_gesto_do_ps(SimpleNamespace(_hotkey_manager=mgr), UM, botoes)


def test_sem_gerente_de_atalhos_o_jogo_recebe_tudo():
    botoes = frozenset({"ps", "dpad_up"})
    assert _ao_jogo(None, botoes) is botoes


def test_o_combo_cala_o_direcional_e_deixa_o_ps():
    assert _ao_jogo(HotkeyManager(), frozenset({"ps", "dpad_up"})) == {"ps"}


def test_botao_solo_chega_ao_jogo_intacto():
    botoes = frozenset({"cross"})
    assert _ao_jogo(HotkeyManager(), botoes) is botoes


def test_passthrough_in_emulation_entrega_o_combo_ao_jogo():
    mgr = HotkeyManager(config=HotkeyConfig(passthrough_in_emulation=True))
    assert _ao_jogo(mgr, frozenset({"ps", "dpad_up"})) == {"ps", "dpad_up"}


def test_config_customizado():
    mgr = HotkeyManager(
        config=HotkeyConfig(buffer_ms=50, next_profile=("l1", "r1"))
    )
    fired = []
    mgr.on_next = lambda: fired.append("n")
    mgr.observe(["l1", "r1"], now=0.0)
    mgr.observe(["l1", "r1"], now=0.08)
    assert fired == ["n"]


def test_default_buffer_configuracao():
    assert DEFAULT_BUFFER_MS == 150
    cfg = HotkeyConfig()
    assert cfg.buffer_ms == 150


def test_o_ps_de_um_e_o_r3_de_outro_nao_sao_um_combo():
    """Cada controle aperta os dele: o PS de um e o R3 de outro não trocam o modo."""
    fired = []
    mgr = HotkeyManager(on_next_bridge=lambda: fired.append("ponte"))
    for t in (0.0, 0.2, 0.4):
        mgr.observe(["ps"], now=t, de=UM)
        mgr.observe(["r3"], now=t, de=OUTRO)
    assert fired == []


def test_o_mesmo_combo_em_dois_controles_dispara_nos_dois():
    fired = []
    mgr = HotkeyManager(on_next_bridge=lambda: fired.append(quem_faz_o_gesto()))
    for t in (0.0, 0.2, 0.4):
        mgr.observe(["ps", "r3"], now=t, de=UM)
        mgr.observe(["ps", "r3"], now=t, de=OUTRO)
    assert fired == [UM, OUTRO]


def test_o_ato_sabe_de_quem_e_o_gesto_e_fora_dele_ninguem():
    vistos = []
    mgr = HotkeyManager(on_ps_solo=lambda: vistos.append(quem_faz_o_gesto()))
    mgr.observe(["ps"], now=0.0, de=OUTRO)
    mgr.observe([], now=0.1, de=OUTRO)
    assert vistos == [OUTRO]
    assert quem_faz_o_gesto() is None


def test_o_ato_que_e_tarefa_leva_o_controle_que_fez_o_gesto():
    """A tarefa roda depois do `observe` de outro controle e ainda responde quem a fez."""
    vistos = []

    async def _ato():
        await asyncio.sleep(0)
        vistos.append(quem_faz_o_gesto())

    async def _laco():
        mgr = HotkeyManager(on_next_mask=_ato)
        mgr.observe(["ps", "l3"], now=0.0, de=OUTRO)
        mgr.observe(["ps", "l3"], now=0.2, de=OUTRO)
        mgr.observe(["ps"], now=0.2, de=UM)
        for _ in range(3):
            await asyncio.sleep(0)

    asyncio.run(_laco())
    assert vistos == [OUTRO]


def test_o_aperto_de_quem_saiu_e_esquecido():
    """Quem não é lido num tique perde o aperto: na volta, o PS velho não é um toque."""
    fired = []
    mgr = HotkeyManager(on_ps_solo=lambda: fired.append("ps_solo"))
    mgr.observe(["ps"], now=0.0, de=OUTRO)
    mgr.soltar_quem_saiu([UM])
    mgr.observe([], now=0.1, de=OUTRO)
    assert fired == []


def test_sem_de_o_aperto_e_o_de_sempre():
    """Quem chama sem dizer de quem são os botões segue com um aperto só (chave None)."""
    fired = []
    mgr = HotkeyManager(on_next_bridge=lambda: fired.append(quem_faz_o_gesto()))
    mgr.observe(["ps", "r3"], now=0.0)
    mgr.observe(["ps", "r3"], now=0.2)
    assert fired == [None]


def _o_toque(mgr: HotkeyManager, botao: str, *, ps_antes: float, toque_ms: int, de: str = UM,
             passo: float = 0.02) -> float:
    """O PS segurado por `ps_antes` segundos, o `botao` por `toque_ms` e a soltura de tudo."""
    t = 0.0
    while t < ps_antes:
        mgr.observe(["ps"], now=t, de=de)
        t += passo
    fim = t + toque_ms / 1000
    while t < fim - 1e-9:
        mgr.observe(["ps", botao], now=t, de=de)
        t += passo
    mgr.observe(["ps"], now=t, de=de)
    mgr.observe([], now=t + passo, de=de)
    return t


@pytest.mark.parametrize("toque_ms", [20, 60, 100, 140])
def test_o_toque_curto_com_o_ps_segurado_troca(toque_ms):
    """D-2511-O-ACORDE-DO-PS-DISPARA-NA-BORDA-DO-SEGUNDO-BOTAO: PS há 400 ms, toque rápido troca.

    Medido antes de curar: o `buffer_ms` contava do tique em que os dois se juntam, e o toque de
    60, 100 e 140 ms não fazia nada. MORDIDA: voltar a conta de `first_seen_at` reprova.
    """
    fired = []
    mgr = HotkeyManager(on_next=lambda: fired.append("n"), on_ps_solo=lambda: fired.append("solo"))
    _o_toque(mgr, "dpad_up", ps_antes=0.4, toque_ms=toque_ms)
    assert fired == ["n"], f"toque de {toque_ms} ms com o PS segurado: {fired}"


def test_o_toque_curto_com_o_ps_segurado_dispara_so_uma_vez_e_o_ps_nao_abre_a_steam():
    fired = []
    mgr = HotkeyManager(on_next=lambda: fired.append("n"), on_ps_solo=lambda: fired.append("solo"))
    _o_toque(mgr, "dpad_up", ps_antes=0.4, toque_ms=140)
    assert fired == ["n"]


@pytest.mark.parametrize("toque_ms", [20, 60, 100, 140])
def test_os_dois_que_chegam_juntos_seguem_amortecidos(toque_ms):
    """O amortecedor fica para os dois que chegam juntos: o toque curto sem PS antes não dispara."""
    fired = []
    mgr = HotkeyManager(on_next=lambda: fired.append("n"))
    _o_toque(mgr, "dpad_up", ps_antes=0.0, toque_ms=toque_ms)
    assert fired == [], f"os dois juntos por {toque_ms} ms dispararam: {fired}"


def test_o_ps_segurado_por_menos_que_o_buffer_ainda_amortece():
    fired = []
    mgr = HotkeyManager(on_next=lambda: fired.append("n"))
    _o_toque(mgr, "dpad_up", ps_antes=0.1, toque_ms=60)
    assert fired == []


def test_o_ps_de_um_controle_nao_adianta_o_acorde_de_outro():
    """Cada controle conta o PS dele: o PS longo de um não adianta o toque do outro."""
    fired = []
    mgr = HotkeyManager(on_next=lambda: fired.append(quem_faz_o_gesto()))
    for t in (0.0, 0.2, 0.4):
        mgr.observe(["ps"], now=t, de=UM)
    mgr.observe(["dpad_up"], now=0.4, de=OUTRO)
    mgr.observe(["ps", "dpad_up"], now=0.42, de=OUTRO)
    mgr.observe([], now=0.46, de=OUTRO)
    assert fired == []


def test_o_toque_curto_troca_nos_dois_controles_cada_um_com_o_seu_ps():
    fired = []
    mgr = HotkeyManager(on_next=lambda: fired.append(quem_faz_o_gesto()))
    for de in (UM, OUTRO):
        _o_toque(mgr, "dpad_up", ps_antes=0.4, toque_ms=60, de=de)
    assert fired == [UM, OUTRO]
