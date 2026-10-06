"""CONTAGEM-E-COOP-01 (E2) — a aba Emulação conta APARELHO, não nó.

O campo "Gamepads:" dizia ``len(glob("/dev/input/js*"))`` e chamava aquilo de
"controles detectados pelo sistema". Medido na máquina do usuário em 31/07/2026, com
UM DualSense no cabo, o vpad do Hefesto de pé e a Steam aberta, ele dizia
**SEIS**::

    js0  Sony … DualSense Wireless Controller          uniq=<MAC dela>
    js1  Sony … DualSense … Motion Sensors             uniq=<O MESMO MAC>
    js2  DualSense Wireless Controller (Hefesto P1)   uniq=02:fe:00:00:00:01
    js3  DualSense … (Hefesto P1) Motion Sensors       uniq=<O MESMO>
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


from tests.conftest import exigir_gi_real

exigir_gi_real("classificar_joysticks vive em emulation_actions, que importa GTK")

from hefesto_dualsense4unix.integrations.uinput_gamepad import (
    DUALSENSE_EDGE_NAME,
    XBOX360_NAME,
)

MAC_FISICO = "aa:bb:cc:dd:ee:ff"

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
            "DualSense Wireless Controller (Hefesto P1)",
            "02:fe:00:00:00:01",
            f"{_HID_UHID}/input/input325/js2",
        ),
        _no(
            "/dev/input/js3",
            "DualSense Wireless Controller (Hefesto P1) Motion Sensors",
            "02:fe:00:00:00:01",
            f"{_HID_UHID}/input/input326/js3",
        ),
        _no("/dev/input/js4", "Microsoft X-Box 360 pad 0", "", f"{_UINPUT}/input329/js4"),
        _no("/dev/input/js5", "Microsoft X-Box 360 pad 1", "", f"{_UINPUT}/input61/js5"),
    ]


class TestAQuartaRegra:
    """O buraco do porte: o vpad em uinput (fallback VPAD-05)."""


    def test_a_mascara_xbox_contem_hefesto_mas_nao_traz_a_marca_do_vpad(
        self,
    ) -> None:
        """Trava a premissa: é por isso que a terceira regra não bastava."""
        from hefesto_dualsense4unix.app.actions.emulation_actions import (
            _VPAD_MARCA_NO_NOME,
        )

        assert "Hefesto" in XBOX360_NAME
        assert _VPAD_MARCA_NO_NOME not in XBOX360_NAME

    def test_a_mascara_dualsense_nao_menciona_hefesto(self) -> None:
        assert "Hefesto" not in DUALSENSE_EDGE_NAME


