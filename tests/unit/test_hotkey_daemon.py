"""Testes do HotkeyManager."""
from __future__ import annotations

import asyncio

from hefesto_dualsense4unix.integrations.hotkey_daemon import (
    DEFAULT_BUFFER_MS,
    HotkeyConfig,
    HotkeyManager,
    quem_faz_o_gesto,
)

#: Dois controles da faixa forjada (octetos 4 e 5 zerados).
UM = "aabbcc000001"
OUTRO = "aabbcc000002"


def test_combo_nao_dispara_antes_do_buffer():
    fired = []
    mgr = HotkeyManager(on_next=lambda: fired.append("next"))

    # t=0: pressiona combo
    assert mgr.observe(["ps", "dpad_up"], now=0.0) is None
    assert fired == []

    # t=0.1s: ainda dentro do buffer (150ms)
    assert mgr.observe(["ps", "dpad_up"], now=0.1) is None
    assert fired == []


def test_combo_dispara_apos_buffer():
    fired = []
    mgr = HotkeyManager(on_next=lambda: fired.append("next"))

    mgr.observe(["ps", "dpad_up"], now=0.0)
    result = mgr.observe(["ps", "dpad_up"], now=0.2)  # >150ms
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
    # solta
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


def test_passthrough_repassa_fora_de_emulation():
    mgr = HotkeyManager()
    assert mgr.should_passthrough(["ps", "dpad_up"], emulation_active=False) is True


def test_passthrough_bloqueia_combo_em_emulation():
    mgr = HotkeyManager()
    assert mgr.should_passthrough(["ps", "dpad_up"], emulation_active=True) is False


def test_passthrough_permite_botao_solo_em_emulation():
    mgr = HotkeyManager()
    assert mgr.should_passthrough(["cross"], emulation_active=True) is True


def test_passthrough_respeita_config_override():
    mgr = HotkeyManager(
        config=HotkeyConfig(passthrough_in_emulation=True)
    )
    assert mgr.should_passthrough(["ps", "dpad_up"], emulation_active=True) is True


def test_config_customizado():
    mgr = HotkeyManager(
        config=HotkeyConfig(buffer_ms=50, next_profile=("l1", "r1"))
    )
    fired = []
    mgr.on_next = lambda: fired.append("n")
    mgr.observe(["l1", "r1"], now=0.0)
    mgr.observe(["l1", "r1"], now=0.08)  # 80ms > buffer de 50ms
    assert fired == ["n"]


def test_default_buffer_configuracao():
    assert DEFAULT_BUFFER_MS == 150  # V3-2
    cfg = HotkeyConfig()
    assert cfg.buffer_ms == 150


# --- O-MODO-XBOX-NAO-E-QUEDA-02, item 5: o aperto de cada controle ------------


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
