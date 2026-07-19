"""8BIT-02 — helpers PUROS da superfície read-only de controles externos.

Tradução da identidade crua do inventário (8BIT-01) para linguagem de gente +
o aviso honesto do Nintendo/8BitDo por Bluetooth. Sem GTK, sem IPC.
"""
from __future__ import annotations

from hefesto_dualsense4unix.app.actions.external_controllers import (
    MODE_SELECTOR_ITEMS,
    MODE_SELECTOR_SUBTITLE,
    MODE_SELECTOR_TOOLTIP,
    brand_of,
    button_labels_for,
    detail_rows,
    external_key,
    external_slot,
    friendly_type,
    input_mode,
    mode_guidance,
    mode_selector_state,
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
#: 8BitDo em modo DualShock4: MENTE o VID (054c=Sony) e o nome ("Wireless
#: Controller"), IDÊNTICO a um DS4 Sony real — só o OUI do MAC o denuncia.
#: Caso vivo da mantenedora. MAC FORJADO (faixa e8:47:3a do gate de anonimato);
#: o OUI sintético é injetado em `_BRAND_BY_OUI` nos testes do mecanismo — a
#: entrada REAL da tabela (e417d8) é travada por assert próprio, sem MAC.
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
#: DualShock4 Sony GENUÍNO: mesmo VID:PID e nome do 8BitDo-DS4, mas OUI
#: desconhecido — deve continuar "Sony" (o OUI não desambigua a favor do 8BitDo).
_DS4_SONY = {**_8BITDO_DS4, "uniq": "aa:bb:cc:00:00:09"}
#: 8BitDo-DS4 por CABO: uniq vazio (USB não expõe MAC) — sem OUI, degrada p/ VID.
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


class TestMarcaPorOUI:
    """O OUI do MAC desambigua o 8BitDo-em-modo-DS4 do DualShock4 Sony real.

    O mecanismo é exercitado com OUI SINTÉTICO (e8473a, faixa forjada do gate
    de anonimato) injetado na tabela — nunca com o MAC real do controle da
    mantenedora. A entrada REAL da tabela é travada à parte, só pelo OUI.
    """

    def _com_oui_sintetico(self, monkeypatch) -> None:
        from hefesto_dualsense4unix.app.actions import external_controllers as ec

        monkeypatch.setitem(ec._BRAND_BY_OUI, "e8473a", "8BitDo")

    def test_tabela_real_tem_o_oui_da_8bitdo(self) -> None:
        # Trava a entrada de produção: OUI e417d8 (registro IEEE público da
        # 8BITDO TECHNOLOGY HK — 6 hex, não é MAC de device) → "8BitDo".
        from hefesto_dualsense4unix.app.actions import external_controllers as ec

        assert ec._BRAND_BY_OUI.get("e417d8") == "8BitDo"

    def test_oui_vence_vid_para_8bitdo_ds4(self, monkeypatch) -> None:
        # VID mente "054c" (Sony); OUI conhecido na tabela → marca = 8BitDo.
        self._com_oui_sintetico(monkeypatch)
        assert brand_of(_8BITDO_DS4) == "8BitDo"
        assert friendly_type(_8BITDO_DS4) == "8BitDo"

    def test_botao_e_slot_do_8bitdo_ds4(self, monkeypatch) -> None:
        self._com_oui_sintetico(monkeypatch)
        assert short_button_label(_8BITDO_DS4) == "8BitDo · BT"
        # com 2 DualSense conectados, o externo é o Controle 3.
        assert button_labels_for([_8BITDO_DS4], dualsense_count=2) == ["8BitDo 3 · BT"]

    def test_ds4_sony_genuino_continua_sony(self, monkeypatch) -> None:
        # mesmo VID:PID/nome, mas OUI fora da tabela → NÃO vira 8BitDo.
        self._com_oui_sintetico(monkeypatch)
        assert brand_of(_DS4_SONY) == "Sony"

    def test_sem_uniq_usb_degrada_para_vid(self, monkeypatch) -> None:
        # por cabo o uniq vem vazio (sem OUI) → cai no fabricante por VID.
        self._com_oui_sintetico(monkeypatch)
        assert brand_of(_8BITDO_DS4_CABO) == "Sony"

    def test_oui_desconhecido_preserva_comportamento_antigo(self) -> None:
        # fixtures com OUI forjado (aabbcc) seguem pelo VID, como antes.
        assert brand_of(_8BITDO_CABO) == "Nintendo"
        assert brand_of(_XBOX) == "Xbox"


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

    def test_detail_rows_nao_duplica_o_modo(self) -> None:
        """GUI-05/P4: a linha "O jogo vê como" saiu da grade — o modo mora no
        seletor segmentado read-only (`mode_selector_state`), fonte única."""
        rows = dict(detail_rows(_8BITDO_CABO))
        assert "O jogo vê como" not in rows


class TestSeletorSegmentadoReadOnly:
    """GUI-05/P4: camada PURA do segmentado read-only da ficha (Nintendo|Xbox)."""

    def test_itens_casam_com_input_mode(self) -> None:
        # Os ids do seletor são exatamente os retornos possíveis de
        # `input_mode` para controles de dois modos.
        assert [iid for iid, _ in MODE_SELECTOR_ITEMS] == ["nintendo", "xbox"]

    def test_nintendo_marca_nintendo(self) -> None:
        estado = mode_selector_state(_8BITDO_CABO)
        assert estado is not None
        itens, ativo = estado
        assert itens == MODE_SELECTOR_ITEMS
        assert ativo == "nintendo"

    def test_xbox_marca_xbox(self) -> None:
        estado = mode_selector_state(_XBOX)
        assert estado is not None
        assert estado[1] == "xbox"

    def test_outro_nao_tem_seletor(self) -> None:
        assert mode_selector_state(_DESCONHECIDO) is None

    def test_mesmo_gate_do_mode_guidance(self) -> None:
        # Seletor e texto de orientação aparecem JUNTOS (mesma condição) —
        # nunca um segmentado sem a explicação, nem o contrário.
        for entry in (_8BITDO_CABO, _8BITDO_BT, _XBOX, _DESCONHECIDO):
            assert (mode_selector_state(entry) is None) == (
                mode_guidance(entry) is None
            )

    def test_subtitulo_diz_que_a_troca_e_fisica(self) -> None:
        assert "física" in MODE_SELECTOR_SUBTITLE
        assert "manual" in MODE_SELECTOR_SUBTITLE

    def test_tooltip_explica_o_read_only(self) -> None:
        assert "leitura" in MODE_SELECTOR_TOOLTIP.lower()
        assert "software" in MODE_SELECTOR_TOOLTIP


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
