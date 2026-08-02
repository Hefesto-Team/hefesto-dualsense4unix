"""CONTAGEM-E-COOP-01 (E2) — a aba Emulação conta APARELHO, não nó.

O campo "Gamepads:" dizia ``len(glob("/dev/input/js*"))`` e chamava aquilo de
"controles detectados pelo sistema". Medido na máquina dela em 31/07/2026, com
UM DualSense no cabo, o vpad do Hefesto de pé e a Steam aberta, ele dizia
**SEIS**::

    js0  Sony … DualSense Wireless Controller          uniq=<MAC dela>
    js1  Sony … DualSense … Motion Sensors             uniq=<O MESMO MAC>
    js2  Hefesto Virtual DualSense P1                  uniq=02:fe:00:00:00:01
    js3  Hefesto Virtual DualSense P1 Motion Sensors   uniq=<O MESMO>
    js4  Microsoft X-Box 360 pad 0   /devices/virtual/input/input329/js4
    js5  Microsoft X-Box 360 pad 1   /devices/virtual/input/input61/js5

Estes testes não usam o `/sys` da máquina: `classificar_joysticks` recebe os
atributos já lidos, e é ela que carrega o julgamento. O MAC real dela NÃO
aparece em lugar nenhum deste arquivo — o portão de anonimato da casa proíbe,
e a identidade do aparelho é o que importa, não o número.

As três funções são puras — mas o MÓDULO que as hospeda não é: importar
``emulation_actions`` puxa o GTK no topo. Por isso a guarda abaixo. Medido no CI
de 31/07: sem ela, este arquivo era o único que ainda derrubava a COLETA do job
headless, e coleta que morre não vira skip visível, vira módulo sumido.

O lugar certo destes casos passa a ser o job "Interface com GTK REAL", que
seleciona exatamente os arquivos com ``exigir_gi_real``. Se um dia as três
funções mudarem de casa para um módulo sem GTK, esta guarda sai junto — e aí a
frase "sem GTK" deixa de ser intenção e vira fato.
"""
from __future__ import annotations

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("classificar_joysticks vive em emulation_actions, que importa GTK")

from hefesto_dualsense4unix.app.actions.emulation_actions import (
    _atributos_do_joystick,
    classificar_joysticks,
    rotulo_gamepads,
)
from hefesto_dualsense4unix.integrations.uinput_gamepad import (
    DUALSENSE_EDGE_NAME,
    XBOX360_NAME,
)

#: MAC fictício de controle físico — dois nós do MESMO aparelho o compartilham.
MAC_FISICO = "aa:bb:cc:dd:ee:ff"

#: O segundo aparelho físico. Fica na MESMA faixa forjada `aa:bb:cc:` que o
#: primeiro porque `test_anonimato_de_fixtures.py` só reconhece três prefixos
#: (`02:fe:`, `aa:bb:cc:`, `e8:47:3a:`) e reprova qualquer outro — um MAC de
#: fantasia fora deles é indistinguível de identidade real vazada.
MAC_FISICO_SEGUNDO = "aa:bb:cc:11:22:33"

_HID_USB = "/sys/devices/pci0000:00/0000:0c:00.3/usb3/3-4/3-4:1.3/0003:054C:0CE6.0005"
_HID_UHID = "/sys/devices/virtual/misc/uhid/0003:054C:0DF2.000C"
_UINPUT = "/sys/devices/virtual/input"


def _no(path: str, name: str, uniq: str, sys_dir: str) -> dict[str, str]:
    return {"path": path, "name": name, "uniq": uniq, "sys": sys_dir}


def _mesa_de_hoje() -> list[dict[str, str]]:
    """A mesa medida hoje, nó a nó."""
    return [
        _no(
            "/dev/input/js0",
            "Sony Interactive Entertainment DualSense Wireless Controller",
            MAC_FISICO,
            f"{_HID_USB}/input/input21/js0",
        ),
        _no(
            "/dev/input/js1",
            "Sony Interactive Entertainment DualSense Wireless Controller Motion Sensors",
            MAC_FISICO,
            f"{_HID_USB}/input/input22/js1",
        ),
        _no(
            "/dev/input/js2",
            "Hefesto Virtual DualSense P1",
            "02:fe:00:00:00:01",
            f"{_HID_UHID}/input/input325/js2",
        ),
        _no(
            "/dev/input/js3",
            "Hefesto Virtual DualSense P1 Motion Sensors",
            "02:fe:00:00:00:01",
            f"{_HID_UHID}/input/input326/js3",
        ),
        _no("/dev/input/js4", "Microsoft X-Box 360 pad 0", "", f"{_UINPUT}/input329/js4"),
        _no("/dev/input/js5", "Microsoft X-Box 360 pad 1", "", f"{_UINPUT}/input61/js5"),
    ]


class TestAMesaMedidaHoje:
    def test_seis_nos_sao_quatro_aparelhos(self) -> None:
        assert classificar_joysticks(_mesa_de_hoje()) == (1, 1, 2)

    def test_o_rotulo_para_de_chamar_no_de_controle(self) -> None:
        nos = _mesa_de_hoje()
        texto = rotulo_gamepads(*classificar_joysticks(nos), len(nos))
        assert texto == (
            "1 controle físico, 1 gamepad virtual do Hefesto, "
            "2 gamepads virtuais de outros programas (Steam Input) — "
            "6 nós em /dev/input/js*"
        )
        assert "6 controles detectados pelo sistema" not in texto

    def test_o_numero_cru_continua_dito_no_fim(self) -> None:
        """A segunda metade EXPLICA a diferença em vez de escondê-la."""
        nos = _mesa_de_hoje()
        assert "6 nós" in rotulo_gamepads(*classificar_joysticks(nos), len(nos))


class TestAgrupamentoPorAparelho:
    def test_gamepad_e_sensores_do_mesmo_uniq_sao_um_controle(self) -> None:
        """Mordida 1 da sprint: sem o agrupamento, js0+js1 voltam a contar 2."""
        nos = _mesa_de_hoje()[:2]
        assert classificar_joysticks(nos) == (1, 0, 0)

    def test_dois_pads_de_uinput_distintos_nao_colapsam(self) -> None:
        """A correção (b) ao código de origem, medida aqui.

        Sem `uniq`, o commit `0c08e77` subia TRÊS níveis do nó — certo para
        device HID (``<hid>/input/inputNN/jsN``) e errado para uinput, cuja
        árvore não tem a camada ``input/``: três níveis chegam em
        ``/sys/devices/virtual`` e colapsam TODOS os pads de uinput num só.
        Os dois pads da Steam medidos hoje virariam um.
        """
        nos = [n for n in _mesa_de_hoje() if not n["uniq"]]
        assert len(nos) == 2
        assert classificar_joysticks(nos) == (0, 0, 2)

    def test_dois_fisicos_diferentes_continuam_dois(self) -> None:
        nos = [
            _no("/dev/input/js0", "Pro Controller", MAC_FISICO_SEGUNDO,
                f"{_HID_USB}/input/input10/js0"),
            _no("/dev/input/js1", "DualSense", MAC_FISICO,
                f"{_HID_USB}/input/input11/js1"),
        ]
        assert classificar_joysticks(nos) == (2, 0, 0)


class TestQuemESeparadoPelaIdentidade:
    def test_o_vpad_uhid_e_reconhecido_pelo_mac_forjado(self) -> None:
        """Mordida 2, ISOLADA: só o `02:fe:`, sem o nome ajudar.

        O vpad com máscara DualSense tem "o MESMO VID/PID/nome/caps do controle
        real" (`core.evdev_reader._is_virtual_evdev`) — mentir o nome é o
        propósito da máscara. Quem decide dentro de `/devices/virtual/misc/uhid/`
        é a IDENTIDADE, e é ela que este caso trava: um nó com o MAC forjado e
        o nome de um DualSense de verdade continua sendo NOSSO. Um teste com o
        nome "Hefesto Virtual" junto não pinaria nada — a segunda regra o
        salvaria e a troca do prefixo passaria batida.
        """
        nos = [
            _no("/dev/input/js0",
                "Sony Interactive Entertainment DualSense Wireless Controller",
                "02:fe:00:00:00:01", f"{_HID_UHID}/input/input325/js0")
        ]
        assert classificar_joysticks(nos) == (0, 1, 0)

    def test_o_vpad_uhid_e_reconhecido_pelo_nome_quando_o_uniq_falta(self) -> None:
        """A outra regra, também isolada: `uniq` ilegível não perde o vpad."""
        nos = [
            _no("/dev/input/js0", "Hefesto Virtual DualSense P1", "",
                f"{_HID_UHID}/input/input325/js0")
        ]
        assert classificar_joysticks(nos) == (0, 1, 0)

    def test_dualsense_bluetooth_fisico_mora_no_mesmo_lugar_e_nao_e_nosso(self) -> None:
        """BLUEZ-UHID-01: o BlueZ cria o HID dos físicos por rádio em
        `/devices/virtual/misc/uhid/`, exatamente onde mora o nosso vpad. Quem
        separa é a identidade, nunca o caminho.
        """
        nos = [
            _no("/dev/input/js0",
                "Sony Interactive Entertainment DualSense Wireless Controller",
                MAC_FISICO, f"{_HID_UHID}/input/input50/js0")
        ]
        assert classificar_joysticks(nos) == (1, 0, 0)

    def test_aparelho_desconhecido_cai_em_fisico(self) -> None:
        """Mordida 3: a leitura conservadora é o inverso de "nosso".

        Inflar o que dizemos ter criado é o defeito; um nó ilegível (atributos
        vazios) tem de contar como controle dela.
        """
        nos = [_no("/dev/input/js9", "", "", "")]
        assert classificar_joysticks(nos) == (1, 0, 0)


class TestAQuartaRegra:
    """O buraco do porte: o vpad em uinput (fallback VPAD-05).

    Ele não publica `uniq` e o nome não começa com "Hefesto Virtual" —
    na máscara dualsense o nome não contém "Hefesto" em lugar nenhum. Sem esta
    regra o classificador do `0c08e77` responderia "de outro programa (Steam
    Input)" sobre o NOSSO PRÓPRIO vpad: trocaria o silêncio por uma acusação
    errada.
    """

    @pytest.mark.parametrize("nome", [XBOX360_NAME, DUALSENSE_EDGE_NAME])
    def test_as_duas_mascaras_de_uinput_sao_nossas(self, nome: str) -> None:
        nos = [_no("/dev/input/js0", nome, "", f"{_UINPUT}/input400/js0")]
        assert classificar_joysticks(nos) == (0, 1, 0)

    def test_a_mascara_xbox_contem_hefesto_mas_nao_comeca_com_hefesto_virtual(
        self,
    ) -> None:
        """Trava a premissa: é por isso que a terceira regra não bastava."""
        assert "Hefesto" in XBOX360_NAME
        assert not XBOX360_NAME.startswith("Hefesto Virtual")

    def test_a_mascara_dualsense_nao_menciona_hefesto(self) -> None:
        assert "Hefesto" not in DUALSENSE_EDGE_NAME

    def test_um_edge_real_nao_e_confundido_com_a_nossa_mascara(self) -> None:
        """A restrição que a regra carrega: só vale DENTRO de uinput.

        Um DualSense Edge físico publica exatamente `DUALSENSE_EDGE_NAME`. O
        que o distingue da nossa máscara é morar sob o barramento (USB) ou sob
        `/devices/virtual/misc/uhid/` (Bluetooth), nunca sob uinput.
        """
        nos = [
            _no("/dev/input/js0", DUALSENSE_EDGE_NAME, MAC_FISICO,
                f"{_HID_USB}/input/input30/js0")
        ]
        assert classificar_joysticks(nos) == (1, 0, 0)

    def test_o_vpad_uinput_e_nosso_nos_dois_backends_juntos(self) -> None:
        nos = [
            _no("/dev/input/js0", "Hefesto Virtual DualSense P1", "02:fe:00:00:00:01",
                f"{_HID_UHID}/input/input325/js0"),
            _no("/dev/input/js1", DUALSENSE_EDGE_NAME, "", f"{_UINPUT}/input400/js1"),
        ]
        assert classificar_joysticks(nos) == (0, 2, 0)

    def test_o_pad_da_steam_continua_sendo_de_outro_programa(self) -> None:
        """A quarta regra não pode virar um "tudo em uinput é nosso"."""
        nos = [_no("/dev/input/js0", "Microsoft X-Box 360 pad 0", "",
                   f"{_UINPUT}/input329/js0")]
        assert classificar_joysticks(nos) == (0, 0, 1)


class TestOTextoDoRotulo:
    def test_sem_nos_a_frase_e_a_de_sempre(self) -> None:
        assert rotulo_gamepads(0, 0, 0, 0) == "Nenhum controle detectado pelo sistema"

    def test_com_nos_e_sem_aparelho_fisico_nao_diz_controles_detectados(self) -> None:
        """Mordida 5 da sprint."""
        texto = rotulo_gamepads(0, 1, 2, 6)
        assert "controles detectados pelo sistema" not in texto
        assert "1 gamepad virtual do Hefesto" in texto

    def test_plural_e_singular_de_cada_coluna(self) -> None:
        assert "2 controles físicos" in rotulo_gamepads(2, 0, 0, 4)
        assert "1 controle físico" in rotulo_gamepads(1, 0, 0, 2)
        assert "2 gamepads virtuais do Hefesto" in rotulo_gamepads(0, 2, 0, 4)
        assert "1 gamepad virtual de outro programa" in rotulo_gamepads(0, 0, 1, 1)
        assert "2 gamepads virtuais de outros programas" in rotulo_gamepads(0, 0, 2, 2)

    def test_nada_reconhecido_e_dito_em_vez_de_frase_vazia(self) -> None:
        assert "Nenhum aparelho reconhecido" in rotulo_gamepads(0, 0, 0, 3)


class TestALeituraDoSysfs:
    def test_no_inexistente_devolve_campos_vazios_sem_explodir(self) -> None:
        """Nó que sumiu entre o `glob` e a leitura não pode derrubar a aba."""
        atributos = _atributos_do_joystick("/dev/input/js999")
        assert atributos["path"] == "/dev/input/js999"
        assert atributos["name"] == ""
        assert atributos["uniq"] == ""

    def test_a_aba_usa_a_classificacao_e_nao_o_len(self) -> None:
        """Sem esta fiação as funções existiriam e o rótulo seguiria mentindo."""
        import inspect

        from hefesto_dualsense4unix.app.actions.emulation_actions import (
            EmulationActionsMixin,
        )

        fonte = inspect.getsource(EmulationActionsMixin._refresh_emulation_view)
        assert "classificar_joysticks(" in fonte
        assert "rotulo_gamepads(" in fonte
        # A forma EXATA do rótulo antigo, e não a frase solta: o corpo do método
        # cita "6 controles detectados" dentro do comentário da medição de
        # largura, e um `not in` sobre a frase reprovaria a própria memória do
        # defeito.
        assert 'palavra = "controle detectado"' not in fonte
