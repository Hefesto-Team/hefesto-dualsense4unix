"""UHID-04 + "carregamento completo": o botão 'Copiar opções p/ jogos' gera a
Launch Option da Steam certa pela máscara/backend ativos.

A cura que a Vitória pediu: a máscara DualSense (uhid Edge) AGORA desduplica com a
MESMA técnica do Xbox (IGNORE do físico), agora que o vpad tem PID próprio (0df2);
e todas as variantes embutem o pré-carregamento de shaders.
"""
from hefesto_dualsense4unix.app.actions.daemon_actions import DaemonActionsMixin

_IGNORE = "SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6"
_PRELOAD = "__GL_SHADER_DISK_CACHE"


def test_xbox_esconde_fisico_forca_evdev_e_precarrega():
    launch, extra = DaemonActionsMixin.compose_launch("xbox", "uinput")
    assert launch.startswith("SDL_JOYSTICK_HIDAPI=0")
    assert _IGNORE in launch
    assert _PRELOAD in launch
    assert launch.endswith("%command%")
    # Xbox volta pelo XInput/FF do vpad — não deve forçar o caminho hidraw
    assert "PROTON_ENABLE_HIDRAW" not in launch
    assert extra == ""


def test_dualsense_edge_desduplica_no_layout_ps():
    launch, extra = DaemonActionsMixin.compose_launch("dualsense", "uhid")
    assert _IGNORE in launch  # esconde SÓ o físico 0ce6; o vpad Edge (0df2) fica
    assert "PROTON_ENABLE_HIDRAW=1" in launch  # hidraw do vpad ao jogo pelo Proton
    assert "SDL_JOYSTICK_HIDAPI=0" not in launch  # HIDAPI LIGADO (driver PS5 no vpad)
    assert _PRELOAD in launch
    assert launch.endswith("%command%")
    assert extra == ""


def test_dualsense_fallback_uinput_e_honesto():
    """Se o uhid não subiu (backend uinput no flavor dualsense), o vpad ainda é
    054c:0ce6 — nenhuma opção o separa do físico. O botão AVISA em vez de prometer."""
    launch, extra = DaemonActionsMixin.compose_launch("dualsense", "uinput")
    assert _IGNORE not in launch  # esconderia o próprio vpad
    assert _PRELOAD in launch
    assert launch.endswith("%command%")
    assert extra != "" and "Xbox" in extra


def test_toda_variante_traz_command_e_preload():
    for flavor, backend in (("xbox", "uinput"), ("dualsense", "uhid"),
                            ("dualsense", "uinput"), ("", "")):
        launch, _ = DaemonActionsMixin.compose_launch(flavor, backend)
        assert launch.endswith("%command%")
        assert _PRELOAD in launch
