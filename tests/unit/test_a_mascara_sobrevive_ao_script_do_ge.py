"""A máscara sobrevive ao script do GE no lançamento.

Sprint A-MASCARA-DUALSENSE-SOBREVIVE-AO-SCRIPT-DO-GE-NO-LANCAMENTO-01. O ramo
Wayland do script `proton` apaga o IGNORE com o Steam Input desligado, e o
físico segue escondido: o barramento SDL do winebus do GE ignora todo Sony, e o
`PROTON_DISABLE_HIDRAW`, que o ramo não toca, fecha o hidraw. O
`PROTON_SONY_AUTO_XINPUT` do 11-8 fica com o padrão do GE, e a opção por jogo o
alcança pelo `exec env` do wrapper.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from hefesto_dualsense4unix.daemon import launch_env as le
from hefesto_dualsense4unix.integrations import qualificar_proton as qp

_RAIZ = Path(__file__).resolve().parents[2]
_WRAPPER = _RAIZ / "assets" / "hefesto-launch.sh"

FISICO = "0x054C/0x0CE6"

#: Os appids em que o 11-7 liga o `PROTON_STEAMINPUT_FALLBACK` (`proton:1953-1962`).
_APPIDS_DO_FALLBACK = ("2246340", "1151640", "2322010", "1034860", "330390", "3255380")


def _nonzero(valor: str) -> bool:
    return valor not in ("", "0")


def _script_do_ge(env: dict[str, str], appid: str = "", *, ge_118: bool = False) -> dict[str, str]:
    """Os ramos do script `proton` que mexem nas envs da máscara, copiados do GE.

    A ordem e as condições são as do 11-7 instalado: o fallback por appid
    (`:1953-1962`, `:2293-2296`), o `check_environment` do Wayland e o ramo
    Wayland (`:2633-2645`). O 11-8 acrescenta o `setdefault` do
    `PROTON_SONY_AUTO_XINPUT` (`:2579`). O ramo `sdlinput` fica de fora: só o
    `PROTON_PREFER_SDL` ou o `PROTON_USE_SDL` o ligam, e o Hefesto não os compõe.
    """
    env = dict(env)
    if appid in _APPIDS_DO_FALLBACK:
        env["PROTON_SONY_HIDRAW_XINPUT"] = "1"
        env["PROTON_STEAMINPUT_FALLBACK"] = "1"
    if env.get("PROTON_STEAMINPUT_FALLBACK") == "1":
        env.pop("PROTON_DISABLE_HIDRAW", None)
    if ge_118:
        env.setdefault("PROTON_SONY_AUTO_XINPUT", "1")
    if _nonzero(env.get("PROTON_ENABLE_WAYLAND", "")):
        env.setdefault("PROTON_NO_STEAMINPUT", "1")
        if _nonzero(env["PROTON_NO_STEAMINPUT"]):
            env.pop("SDL_GAMECONTROLLER_IGNORE_DEVICES", None)
    return env


def _o_lancamento_mostra_o_fisico(env: dict[str, str]) -> bool:
    """Se o lançamento deixa o winebus do GE entregar o DualSense físico ao jogo.

    O barramento SDL ignora todo Sony (patches 0014 e 0177: «ignoring SDL Sony
    controller»), e o udev adia o evdev de «input» a outro backend. Sobra o
    hidraw, que só o `PROTON_DISABLE_HIDRAW` com o par do físico (ou `1`) fecha.
    O ACL do broker é a outra camada, fora do lançamento.
    """
    desligados = {p.strip().upper() for p in env.get("PROTON_DISABLE_HIDRAW", "").split(",")}
    return "1" not in desligados and FISICO.upper() not in desligados


def _env_da_mascara(mascara: str, backend: str) -> dict[str, str]:
    return le.compose_env(
        native_mode=False, emulation_enabled=True, flavor=mascara,
        backends=[backend], fisicos=1,
    )


_MASCARAS = [("dualsense", "uhid"), ("dualsense", "uinput"), ("xbox", "uinput"),
             ("nintendo", "uinput")]


@pytest.mark.parametrize(("mascara", "backend"), _MASCARAS)
@pytest.mark.parametrize("ge_118", [False, True])
def test_o_ramo_wayland_apaga_o_ignore_e_o_fisico_segue_escondido(
    mascara: str, backend: str, ge_118: bool
) -> None:
    """MORDIDA: tire o `PROTON_DISABLE_HIDRAW` da máscara, e o físico reaparece."""
    env = _env_da_mascara(mascara, backend)
    assert env["SDL_GAMECONTROLLER_IGNORE_DEVICES"] == le._IGNORE_VALUE
    depois = _script_do_ge({**env, "PROTON_ENABLE_WAYLAND": "1"}, "1599660", ge_118=ge_118)
    assert "SDL_GAMECONTROLLER_IGNORE_DEVICES" not in depois
    assert depois["PROTON_DISABLE_HIDRAW"] == le._DISABLE_HIDRAW_VALUE
    assert not _o_lancamento_mostra_o_fisico(depois)


def test_sem_wayland_o_ignore_fica() -> None:
    env = _env_da_mascara("dualsense", "uhid")
    assert _script_do_ge(env, "1599660")["SDL_GAMECONTROLLER_IGNORE_DEVICES"] == le._IGNORE_VALUE


def test_o_modo_nativo_nao_esconde_nada() -> None:
    env = le.compose_env(native_mode=True, emulation_enabled=True, flavor="dualsense",
                         backends=["uhid"], fisicos=1)
    assert _o_lancamento_mostra_o_fisico(_script_do_ge(env, "1599660"))


@pytest.mark.parametrize("appid", _APPIDS_DO_FALLBACK)
def test_no_fallback_por_appid_quem_esconde_o_hidraw_e_o_broker(appid: str) -> None:
    """O fato medido: nos seis jogos do fallback o script tira o DISABLE_HIDRAW.

    Ali a camada do lançamento cai inteira, e o hidraw do físico fica só com o
    ACL do broker (`broker/hidraw_broker.py`). A régua guarda o fato para o dia em
    que a lista mudar.
    """
    env = _env_da_mascara("dualsense", "uhid")
    assert _o_lancamento_mostra_o_fisico(_script_do_ge(env, appid))


def test_o_hefesto_nunca_liga_o_ramo_sdlinput() -> None:
    """O `sdlinput` poria `PROTON_DISABLE_HIDRAW=1` e fecharia também o vpad."""
    for mascara, backend in _MASCARAS:
        env = _env_da_mascara(mascara, backend)
        assert "PROTON_PREFER_SDL" not in env and "PROTON_USE_SDL" not in env


def test_a_ficha_do_proton_exige_o_barramento_sdl_que_ignora_o_sony() -> None:
    """Sem o patch do GE, o físico apareceria pelo SDL no Wayland: a ficha reprova."""
    assert ("winebus", ("x86_64-unix/winebus.so",), "hidraw handles native reports") in (
        qp.CONTRATO_DE_STRINGS
    )


def test_o_hefesto_nao_compoe_o_auto_xinput() -> None:
    # D-1610-O-AUTO-XINPUT-FICA-FORA-DA-ALLOWLIST
    """O padrão do GE fica: nenhuma máscara compõe a env, e ela não está na allowlist."""
    for mascara, backend in _MASCARAS:
        assert "PROTON_SONY_AUTO_XINPUT" not in _env_da_mascara(mascara, backend)
    assert "PROTON_SONY_AUTO_XINPUT" not in le.ENV_ALLOWLIST
    assert "PROTON_SONY_AUTO_XINPUT" in qp.ENVS_ALEM_DA_ALLOWLIST


@pytest.fixture()
def runtime() -> Iterator[Path]:
    base = Path(tempfile.mkdtemp(prefix="hefg-", dir="/tmp"))
    (base / "hefesto-dualsense4unix").mkdir()
    yield base
    shutil.rmtree(base, ignore_errors=True)


def _wrapper(runtime: Path, state_home: Path, args: list[str]) -> str:
    mudos = runtime / "mudos"
    mudos.mkdir(exist_ok=True)
    state_home.mkdir(exist_ok=True)
    for nome in ("system76-power", "busctl", "dbus-send"):
        (mudos / nome).write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        (mudos / nome).chmod(0o755)
    env = {
        "PATH": f"{mudos}:{os.environ.get('PATH', '/usr/bin:/bin')}",
        "HOME": str(state_home),
        "XDG_RUNTIME_DIR": str(runtime),
        "XDG_STATE_HOME": str(state_home),
        "SteamAppId": "1599660",
    }
    feito = subprocess.run(["sh", str(_WRAPPER), *args], env=env, capture_output=True,
                           text=True, timeout=15, check=False)
    assert feito.returncode == 0, feito.stderr
    return feito.stdout.strip()


def test_a_opcao_por_jogo_desliga_o_auto_xinput_pelo_wrapper(
    runtime: Path, tmp_path: Path
) -> None:
    """A linha `<atalho> PROTON_SONY_AUTO_XINPUT=0 %command%` chega ao jogo.

    O wrapper põe as envs dele ANTES do `"$@"` no `exec env`, e o `setdefault` do
    11-8 não sobrepõe o `0`: a allowlist governa só o arquivo do daemon.
    """
    sonda = 'printf "AUTO=%s\\n" "${PROTON_SONY_AUTO_XINPUT-ausente}"'
    saida = _wrapper(runtime, tmp_path, ["PROTON_SONY_AUTO_XINPUT=0", "sh", "-c", sonda])
    assert saida == "AUTO=0"
    assert _script_do_ge({"PROTON_SONY_AUTO_XINPUT": "0"}, ge_118=True)[
        "PROTON_SONY_AUTO_XINPUT"] == "0"
    assert _wrapper(runtime, tmp_path / "b", ["sh", "-c", sonda]) == "AUTO=ausente"
