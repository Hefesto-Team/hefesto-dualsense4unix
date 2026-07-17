"""8BIT-02 — helpers PUROS da superfície read-only de controles externos.

Tradução da identidade crua do inventário (8BIT-01) para linguagem de gente +
o aviso honesto do Nintendo/8BitDo por Bluetooth. Sem GTK, sem IPC.
"""
from __future__ import annotations

from hefesto_dualsense4unix.app.actions.external_controllers import (
    button_labels_for,
    detail_rows,
    external_key,
    external_slot,
    friendly_type,
    input_mode,
    mode_guidance,
    nintendo_bt_warning,
    short_button_label,
    transport_label,
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


class TestFriendlyType:
    def test_pro_controller(self) -> None:
        assert friendly_type(_8BITDO_CABO) == "Pro Controller (modo Switch)"

    def test_xbox(self) -> None:
        assert friendly_type(_XBOX) == "Xbox 360"

    def test_vendor_por_vid_quando_pid_desconhecido(self) -> None:
        assert friendly_type({"vid": "2dc8", "pid": "ffff"}) == "8BitDo"

    def test_fallback_nome_cru(self) -> None:
        assert friendly_type(_DESCONHECIDO) == "Marca Xpto Pad"


class TestTransport:
    def test_usb(self) -> None:
        assert transport_label(_8BITDO_CABO) == "Cabo (USB)"

    def test_bluetooth(self) -> None:
        assert transport_label(_8BITDO_BT) == "Bluetooth"


class TestBotaoCurto:
    def test_nintendo_cabo(self) -> None:
        assert short_button_label(_8BITDO_CABO) == "Nintendo · cabo"

    def test_nintendo_bt(self) -> None:
        assert short_button_label(_8BITDO_BT) == "Nintendo · BT"


class TestAvisoBluetooth:
    def test_nintendo_bt_avisa(self) -> None:
        aviso = nintendo_bt_warning(_8BITDO_BT)
        assert aviso is not None
        assert "cabo" in aviso  # aponta a saída estável
        assert "Hefesto" in aviso  # deixa claro que a morte não é do Hefesto

    def test_nintendo_cabo_nao_avisa(self) -> None:
        assert nintendo_bt_warning(_8BITDO_CABO) is None

    def test_xbox_bt_nao_avisa(self) -> None:
        assert nintendo_bt_warning({**_XBOX, "bus": "bluetooth"}) is None


class TestFicha:
    def test_detail_rows_tem_o_essencial(self) -> None:
        rows = dict(detail_rows(_8BITDO_CABO))
        assert rows["Controle"] == "Pro Controller (modo Switch)"
        assert rows["Como conectou"] == "Cabo (USB)"
        assert rows["Driver do Linux"] == "nintendo"
        assert "não mexe" in rows["Gerenciado por"]

    def test_detail_rows_sem_caminho_cru_de_dev(self) -> None:
        # Nada de /dev/input ou /dev/hidraw na ficha do leigo.
        texto = " ".join(v for _, v in detail_rows(_8BITDO_CABO))
        assert "/dev/" not in texto


class TestModo:
    def test_input_mode_nintendo(self) -> None:
        assert input_mode(_8BITDO_CABO) == "nintendo"

    def test_input_mode_xbox(self) -> None:
        assert input_mode(_XBOX) == "xbox"
        assert input_mode({"vid": "0000", "driver": "xpad"}) == "xbox"

    def test_input_mode_outro(self) -> None:
        assert input_mode(_DESCONHECIDO) == "outro"

    def test_guidance_nintendo_aponta_xbox_como_estavel(self) -> None:
        guia = mode_guidance(_8BITDO_CABO)
        assert guia is not None
        atual, orient = guia
        assert atual == "Nintendo (modo Switch)"
        assert "Xbox" in orient  # aponta a raiz estável
        assert "Bluetooth" in orient  # e por que o Switch trava

    def test_guidance_xbox_menciona_gyro(self) -> None:
        guia = mode_guidance(_XBOX)
        assert guia is not None
        atual, orient = guia
        assert atual == "Xbox (X-input)"
        assert "giroscópio" in orient or "gyro" in orient

    def test_guidance_none_para_controle_sem_dois_modos(self) -> None:
        assert mode_guidance(_DESCONHECIDO) is None

    def test_detail_rows_inclui_o_modo(self) -> None:
        rows = dict(detail_rows(_8BITDO_CABO))
        assert rows["O jogo vê como"] == "Nintendo (modo Switch)"


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

    def test_labels_numeram_pelo_slot_global(self) -> None:
        externals = [_8BITDO_CABO, {**_8BITDO_CABO, "uniq": "AA:BB:CC:00:00:04"}]
        # com 2 DualSense conectados: os externos viram Controle 3 e 4.
        assert button_labels_for(externals, dualsense_count=2) == [
            "Nintendo 3 · cabo",
            "Nintendo 4 · cabo",
        ]

    def test_labels_sem_dualsense_comecam_em_1(self) -> None:
        assert button_labels_for([_8BITDO_CABO], dualsense_count=0) == ["Nintendo 1 · cabo"]

    def test_labels_tipos_diferentes_seguem_o_slot(self) -> None:
        assert button_labels_for([_8BITDO_CABO, _XBOX], dualsense_count=2) == [
            "Nintendo 3 · cabo",
            "Xbox 4 · cabo",
        ]
