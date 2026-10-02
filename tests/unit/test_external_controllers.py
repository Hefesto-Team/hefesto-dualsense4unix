"""8BIT-02 — helpers PUROS da superfície read-only de controles externos."""
from __future__ import annotations

from hefesto_dualsense4unix.app.actions.external_controllers import (
    brand_of,
    external_key,
    external_slot,
    friendly_type,
    nintendo_bt_warning,
    slot_label,
    slot_of,
)

_8BITDO_CABO = {
    "name": "Nintendo Co., Ltd. Pro Controller",
    "vid": "057e",
    "pid": "2009",
    "bus": "usb",
    "uniq": "AA:BB:CC:00:00:03",
    "driver": "nintendo",
    "evdev_path": "/dev/input/event8",
    "hidraw": "/dev/hidraw2",
}
_8BITDO_BT = {**_8BITDO_CABO, "bus": "bluetooth", "hidraw": "/dev/hidraw6"}
_XBOX = {"name": "X360 Controller", "vid": "045e", "pid": "028e", "bus": "usb"}
_DESCONHECIDO = {"name": "Marca Xpto Pad", "vid": "abcd", "pid": "0001", "bus": "usb"}
_8BITDO_DS4 = {
    "name": "Wireless Controller",
    "vid": "054c",
    "pid": "05c4",
    "bus": "bluetooth",
    "uniq": "e8:47:3a:00:00:07",
    "driver": "playstation",
    "evdev_path": "/dev/input/event9",
    "hidraw": "/dev/hidraw7",
}
_DS4_SONY = {**_8BITDO_DS4, "uniq": "aa:bb:cc:00:00:09"}
_8BITDO_DS4_CABO = {**_8BITDO_DS4, "bus": "usb", "uniq": ""}


class TestFriendlyType:
    def test_pro_controller(self) -> None:
        assert friendly_type(_8BITDO_CABO) == "Pro Controller (modo Switch)"

    def test_xbox(self) -> None:
        assert friendly_type(_XBOX) == "Xbox 360"

    def test_vendor_por_vid_quando_pid_desconhecido(self) -> None:
        assert friendly_type({"vid": "2dc8", "pid": "ffff"}) == "8BitDo"

    def test_fallback_nome_cru(self) -> None:
        assert friendly_type(_DESCONHECIDO) == "Marca Xpto Pad"


class TestMarcaPorOUI:
    """O OUI do MAC desambigua o 8BitDo-em-modo-DS4 do DualShock4 Sony real."""

    def _com_oui_sintetico(self, monkeypatch) -> None:
        from hefesto_dualsense4unix.app.actions import external_controllers as ec

        monkeypatch.setitem(ec._BRAND_BY_OUI, "e8473a", "8BitDo")

    def test_tabela_real_tem_o_oui_da_8bitdo(self) -> None:
        from hefesto_dualsense4unix.app.actions import external_controllers as ec

        assert ec._BRAND_BY_OUI.get("e417d8") == "8BitDo"

    def test_oui_vence_vid_para_8bitdo_ds4(self, monkeypatch) -> None:
        self._com_oui_sintetico(monkeypatch)
        assert brand_of(_8BITDO_DS4) == "8BitDo"
        assert friendly_type(_8BITDO_DS4) == "8BitDo"


    def test_ds4_sony_genuino_continua_sony(self, monkeypatch) -> None:
        self._com_oui_sintetico(monkeypatch)
        assert brand_of(_DS4_SONY) == "Sony"

    def test_sem_uniq_usb_degrada_para_vid(self, monkeypatch) -> None:
        self._com_oui_sintetico(monkeypatch)
        assert brand_of(_8BITDO_DS4_CABO) == "Sony"

    def test_oui_desconhecido_preserva_comportamento_antigo(self) -> None:
        assert brand_of(_8BITDO_CABO) == "Nintendo"
        assert brand_of(_XBOX) == "Xbox"


class TestAvisoBluetooth:
    def test_nintendo_bt_avisa(self) -> None:
        from hefesto_dualsense4unix.app.actions.home_actions import (
            palavra_do_transporte as palavra,
        )

        aviso = nintendo_bt_warning(_8BITDO_BT)
        assert aviso is not None
        assert f"pelo {palavra('usb')}" in aviso
        assert palavra("bt") in aviso
        assert "driver" in aviso
        assert len(aviso) < 120

    def test_nintendo_cabo_nao_avisa(self) -> None:
        assert nintendo_bt_warning(_8BITDO_CABO) is None

    def test_xbox_bt_nao_avisa(self) -> None:
        assert nintendo_bt_warning({**_XBOX, "bus": "bluetooth"}) is None


class TestChave:
    def test_usa_uniq_quando_ha(self) -> None:
        assert external_key(_8BITDO_CABO) == "AA:BB:CC:00:00:03"

    def test_fallback_path_sem_uniq(self) -> None:
        assert external_key({"evdev_path": "/dev/input/event9"}) == "/dev/input/event9"


class TestSlotGlobalDosBotoes:
    def test_external_slot_continua_dos_dualsense(self) -> None:
        # 2 DualSense (slots 1,2) -> 1º externo = 3, 2º = 4.
        assert external_slot(2, 0) == 3
        assert external_slot(2, 1) == 4
        # sem DualSense -> 1, 2.
        assert external_slot(0, 0) == 1


class TestSlotOfFimDoPosicional:
    """NUMA-05 (bloco 11 POSICIONAL) — `slot_of` nunca mais reembaralha.

    Com `player_slot` PRESENTE no payload do daemon (o normal desde o
    8BIT-01), a chave é a fonte ÚNICA — mesmo valendo ``None`` (registry sem
    opinião ainda). O posicional só roda quando a CHAVE está AUSENTE (daemon
    de antes do 8BIT-02).
    """

    def test_player_slot_inteiro_vence(self) -> None:
        entry = {**_8BITDO_CABO, "player_slot": 4}
        assert slot_of(entry, dualsense_count=0, index=0) == 4

    def test_player_slot_none_devolve_none_falha_sem(self) -> None:
        """FALHA-SEM: no HEAD pré-NUMA-05, isto devolvia o posicional (1)"""
        entry = {**_8BITDO_CABO, "player_slot": None}
        assert slot_of(entry, dualsense_count=0, index=0) is None

    def test_player_slot_none_estavel_sob_troca_de_ds_count(self) -> None:
        """POSICIONAL bloco 11: `ds_count` 1 -> 0 não move o slot None."""
        entry = {**_8BITDO_CABO, "player_slot": None}
        primeiro = slot_of(entry, dualsense_count=1, index=0)
        segundo = slot_of(entry, dualsense_count=0, index=0)
        assert primeiro is None
        assert segundo is None

    def test_chave_ausente_cai_no_posicional_legado(self) -> None:
        """Compat: daemon de antes do 8BIT-02 nunca manda `player_slot`."""
        entry = dict(_8BITDO_CABO)
        entry.pop("player_slot", None)
        assert slot_of(entry, dualsense_count=2, index=1) == external_slot(2, 1)

    def test_player_slot_zero_ou_negativo_degrada_pra_none(self) -> None:
        entry = {**_8BITDO_CABO, "player_slot": 0}
        assert slot_of(entry, dualsense_count=0, index=0) is None


class TestSlotLabel:
    def test_numero_vira_string(self) -> None:
        assert slot_label(3) == "3"

    def test_none_vira_traco(self) -> None:
        assert slot_label(None) == "—"


