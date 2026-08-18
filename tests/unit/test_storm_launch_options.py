"""DEDUP-04/UX-05: o botão 'Copiar opções p/ jogos' devolve a chamada do WRAPPER.

A cura da causa-raiz do "em BT nada funciona": a Launch Option deixou de ser
uma env ESTÁTICA por máscara/backend (que pressupunha vpad Edge vivo e, quando
o pressuposto falhava, escondia o único controle => ZERO controles) e virou a
string CONSTANTE `hefesto-launch %command%` — quem decide as envs é o wrapper
NA HORA do launch, via IPC, com degradação garantida.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from hefesto_dualsense4unix.app.actions.daemon_actions import DaemonActionsMixin
from hefesto_dualsense4unix.integrations.steam_launch_options import (
    IGNORE_SIGNATURE,
    WRAPPER_LAUNCH,
    WRAPPER_PREFIX,
)

_TODOS_OS_ESTADOS = (
    ("xbox", "uinput"),
    ("dualsense", "uhid"),
    ("dualsense", "uinput"),
    ("", ""),
)


def test_string_identica_para_qualquer_mascara_backend():
    """Critério (g) do DEDUP-04: a string é constante — a variação por estado
    morreu junto com o veneno (quem varia é o arquivo materializado que o
    wrapper lê depois do gate de vida IPC)."""
    strings = {DaemonActionsMixin.compose_launch(f, b) for f, b in _TODOS_OS_ESTADOS}
    assert strings == {(WRAPPER_LAUNCH, "")}


def test_nao_recomenda_mais_o_veneno_estatico():
    """UX-05: nenhuma variante emite IGNORE_DEVICES/SDL_JOYSTICK_HIDAPI — a
    env estática persistida era exatamente o que deixava o jogo com zero
    controles quando o vpad degradava."""
    for flavor, backend in _TODOS_OS_ESTADOS:
        launch, _extra = DaemonActionsMixin.compose_launch(flavor, backend)
        assert IGNORE_SIGNATURE not in launch
        assert "SDL_JOYSTICK_HIDAPI" not in launch
        assert "PROTON_ENABLE_HIDRAW" not in launch


def test_string_termina_em_command_e_embrulha_o_wrapper():
    launch, extra = DaemonActionsMixin.compose_launch("dualsense", "uhid")
    assert launch == WRAPPER_LAUNCH
    assert launch.endswith("%command%")
    assert launch.startswith("sh -c '")
    assert "hefesto-launch" in launch
    # `exec env "$@"` (nunca `exec "$@"`): LaunchOptions VAR=VAL viram
    # assignment do env(1) em vez de comando a executar.
    assert 'exec env "$@"' in launch
    assert extra == ""


def test_string_degrada_sozinha_sem_wrapper_instalado(tmp_path, monkeypatch):
    """Critério (e) do DEDUP-04: com o wrapper APAGADO, a própria string
    constante cai em `exec env "$@"` e o jogo AINDA abre (o modo de falha
    'caminho órfão no vdf = jogo que não abre' foi morto pela revisão)."""
    monkeypatch.setenv("HOME", str(tmp_path))  # nenhum wrapper neste $HOME
    argv = WRAPPER_PREFIX.replace("sh -c ", "", 1)
    inner = argv[argv.index("'") + 1 : argv.rindex("'")]
    result = subprocess.run(
        ["sh", "-c", inner, "hefesto-launch", "echo", "jogo-abriu"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "jogo-abriu"


def test_string_degrada_preservando_launch_options_do_usuario(tmp_path, monkeypatch):
    """Critério (f): `MANGOHUD=1 %command%` pré-existente vira `$1` após o
    prepend e o env(1) o processa como assignment — o jogo abre com a var."""
    monkeypatch.setenv("HOME", str(tmp_path))
    argv = WRAPPER_PREFIX.replace("sh -c ", "", 1)
    inner = argv[argv.index("'") + 1 : argv.rindex("'")]
    result = subprocess.run(
        [
            "sh", "-c", inner, "hefesto-launch",
            "VAR_DA_USUARIA=1", "sh", "-c", 'echo "veio=$VAR_DA_USUARIA"',
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "veio=1"


def test_doctor_nao_recomenda_o_veneno():
    """UX-05: o doctor pode ACUSAR o token persistido (check do UX-04), mas
    nenhuma linha volta a RECOMENDÁ-LO como opção a colar."""
    root = Path(__file__).resolve().parents[2]
    texto = (root / "scripts/doctor.sh").read_text(encoding="utf-8")
    for linha in texto.splitlines():
        if "SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6" in linha:
            assert "recomendada" not in linha
            assert "cole" not in linha.lower()
