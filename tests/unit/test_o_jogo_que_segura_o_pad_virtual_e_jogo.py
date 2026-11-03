"""O jogo que segura o nó do pad virtual é jogo, venha de onde vier (P1 a P4, todo caminho)."""

from __future__ import annotations

import builtins
import os
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems.game_signal import GameSignal, classify
from hefesto_dualsense4unix.integrations import no_do_vpad
from hefesto_dualsense4unix.integrations import quem_segura_o_pad as qsp
from hefesto_dualsense4unix.integrations.uhid_gamepad import (
    VPAD_HID_PHYS,
    UhidDualSense,
    _GadgetDoPad,
)
from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad

MEU_PID = 4242
FISICOS = {
    1: "aa:bb:cc:00:00:01",
    2: "aa:bb:cc:00:00:02",
    3: "aa:bb:cc:00:00:03",
    4: "aa:bb:cc:00:00:04",
}
PRODUTO = {"dualsense": 0x0CE6, "edge": 0x0DF2}

SEM_OUTRA_EVIDENCIA: dict[str, Any] = {
    "window_healthy": True,
    "window_class_current": "cosmic-files",
    "window_seen_age": None,
    "profile_rule_match": False,
    "marker": None,
    "marker_pid_alive": False,
    "exit_marker": None,
    "session_open": True,
    "now": 0.0,
}

JOGOS = {
    "forja": "/opt/a-forja/forja",
    "retroarch": "/usr/bin/retroarch -L snes9x",
    "wine64-preloader": "/usr/lib/wine/wine64-preloader C:\\jogo\\jogo.exe",
}
NAO_JOGOS = {
    "steam": "/home/u/.steam/debian-installation/ubuntu12_32/steam -nominidumps",
    "steamwebhelper": "/home/u/.steam/.../steamwebhelper --type=utility",
    "reaper": "/home/u/.steam/debian-installation/ubuntu12_32/reaper",
    "reaper-install": "/x/reaper SteamLaunch AppId=99 Install=1 -- /x/evaluator",
    "hefesto-dualsen": "/venv/bin/python /home/u/.local/bin/hefesto-dualsense4unix daemon",
    "python3": "python3 -m hefesto_dualsense4unix.cli.app tray",
}
COMM_DE = {"reaper-install": "reaper"}


@dataclass
class Mesa:
    raiz: Path
    nos: dict[int, tuple[Path, ...]]
    proximo_pid: int = 5000

    @property
    def proc(self) -> Path:
        return self.raiz / "proc"

    def processo(self, comm: str, cmdline: str, *nos: Path, pid: int | None = None) -> int:
        pid = pid if pid is not None else self.proximo_pid
        self.proximo_pid += 1
        pasta = self.proc / str(pid)
        (pasta / "fd").mkdir(parents=True)
        (pasta / "comm").write_text(comm + "\n")
        (pasta / "cmdline").write_bytes(cmdline.replace(" ", "\0").encode() + b"\0")
        (pasta / "fd" / "0").symlink_to("/dev/null")
        for n, no in enumerate(nos, start=3):
            (pasta / "fd" / str(n)).symlink_to(no)
        return pid

    def larga(self, pid: int) -> None:
        for fd in (self.proc / str(pid) / "fd").iterdir():
            fd.unlink()


def _sysfs_do_pad(raiz: Path, player: int, vpad: Any, caminho: str) -> tuple[Path, Path]:
    """Os nós de um pad uhid ou gadget como o kernel os publica (o driver copia o uniq)."""
    evento, hidraw = f"event{30 + player}", f"hidraw{10 + player}"
    hid = raiz / "sys/devices" / caminho / f"0003:054C:{vpad.product:04X}.000{player}"
    entrada = hid / "input" / f"input{40 + player}"
    entrada.mkdir(parents=True)
    (entrada / "uniq").write_text(vpad.mac + "\n")
    (entrada / "name").write_text(vpad.name + "\n")
    phys = f"{VPAD_HID_PHYS}-{player}" if caminho == "uhid" else f"usb-vhci_hcd.0-{player}/input0"
    (hid / "uevent").write_text(f"HID_UNIQ={vpad.mac}\nHID_PHYS={phys}\n")
    (hid / "hidraw" / hidraw).mkdir(parents=True)
    classe = raiz / "sys/class/input" / evento
    classe.mkdir(parents=True)
    (classe / "device").symlink_to(entrada)
    no_evento, no_hidraw = raiz / "dev/input" / evento, raiz / "dev" / hidraw
    no_evento.write_bytes(b"")
    no_hidraw.write_bytes(b"")
    return no_evento, no_hidraw


def _pad(
    raiz: Path, player: int, modo: str, caminho: str, via: str
) -> tuple[Any, tuple[Path, ...]]:
    identidade = FISICOS[player].upper() if via == "radio" else FISICOS[player]
    if modo == "xbox":
        pad = UinputGamepad.for_flavor("xbox")
        no = raiz / "dev/input" / f"event{60 + player}"
        no.write_bytes(b"")
        pad._device = SimpleNamespace(device=SimpleNamespace(path=str(no)))
        return pad, (no,)
    pad = UhidDualSense(player=player, identity=identidade, product=PRODUTO[modo])
    nos = _sysfs_do_pad(raiz, player, pad, caminho)
    if caminho == "gadget":
        pad._gadget = _GadgetDoPad(
            cliente=None, fd=-1, gadget="g", serial=f"hefesto-pad-{player}", hidraw=nos[1].name
        )
    return pad, nos


@pytest.fixture
def raizes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for parte in ("proc", "dev/input", "sys/class/input"):
        (tmp_path / parte).mkdir(parents=True)
    monkeypatch.setattr(no_do_vpad, "RAIZ_CLASS_INPUT", str(tmp_path / "sys/class/input"))
    monkeypatch.setattr(no_do_vpad, "RAIZ_DEV_INPUT", str(tmp_path / "dev/input"))
    monkeypatch.setattr(no_do_vpad, "RAIZ_DEV", str(tmp_path / "dev"))
    monkeypatch.setattr(qsp, "RAIZ_PROC", str(tmp_path / "proc"))
    monkeypatch.setattr(qsp, "RAIZ_DEV", str(tmp_path / "dev"))
    return tmp_path


@pytest.fixture
def nunca_abre_o_no(monkeypatch: pytest.MonkeyPatch, raizes: Path) -> None:
    """O `open` de mentira reprova se a varredura abrir um nó ou o descritor dele."""
    nos = {str(raizes / "dev")}
    abrir, abrir_os = builtins.open, os.open

    def vigia(caminho: Any) -> None:
        real = os.path.realpath(caminho) if isinstance(caminho, (str, Path)) else ""
        if any(real.startswith(n) for n in nos) or "/fd/" in str(caminho):
            raise AssertionError(f"a varredura abriu o nó: {caminho}")

    def open_vigiado(caminho: Any, *args: Any, **kwargs: Any) -> Any:
        vigia(caminho)
        return abrir(caminho, *args, **kwargs)

    def os_open_vigiado(caminho: Any, *args: Any, **kwargs: Any) -> Any:
        vigia(caminho)
        return abrir_os(caminho, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", open_vigiado)
    monkeypatch.setattr(os, "open", os_open_vigiado)


COMBINACOES = [
    (player, modo, caminho, via)
    for player in (1, 2, 3, 4)
    for modo, caminho in (
        ("dualsense", "uhid"),
        ("dualsense", "gadget"),
        ("edge", "uhid"),
        ("edge", "gadget"),
        ("xbox", "uinput"),
    )
    for via in ("cabo", "radio")
]


def _mesa(
    raizes: Path, player: int, modo: str, caminho: str, via: str
) -> tuple[Mesa, list[Any]]:
    pads, nos = [], {}
    for p in range(1, player + 1):
        pad, nos_do_pad = _pad(raizes, p, modo, caminho, via)
        pads.append(pad)
        nos[p] = nos_do_pad
    return Mesa(raiz=raizes, nos=nos), pads


def _o_jogo(pads: list[Any]) -> Any:
    por_pad = qsp.jogos_por_pad({str(i): pad for i, pad in enumerate(pads)}, meu_pid=MEU_PID)
    return next(iter(por_pad.values()), None)


def _veredito(pads: list[Any]) -> str:
    segurador = _o_jogo(pads)
    return classify(**SEM_OUTRA_EVIDENCIA, processo_no_pad=segurador.nome if segurador else None)


@pytest.mark.parametrize(("player", "modo", "caminho", "via"), COMBINACOES)
@pytest.mark.parametrize("jogo", sorted(JOGOS))
def test_o_jogo_de_fora_no_no_do_pad_e_jogo(
    raizes: Path,
    nunca_abre_o_no: None,
    player: int,
    modo: str,
    caminho: str,
    via: str,
    jogo: str,
) -> None:
    mesa, pads = _mesa(raizes, player, modo, caminho, via)
    assert _veredito(pads) == "daemon"
    mesa.processo(jogo, JOGOS[jogo], mesa.nos[player][-1])
    segurador = _o_jogo(pads)
    assert segurador is not None and segurador.nome == jogo
    assert _veredito(pads) == "game"


@pytest.mark.parametrize(("player", "modo", "caminho", "via"), COMBINACOES)
@pytest.mark.parametrize("quem", sorted([*NAO_JOGOS, *qsp.LEITORES_SEM_JOGO, "meu-pid"]))
def test_a_steam_a_mesa_e_o_hefesto_no_no_nao_sao_jogo(
    raizes: Path,
    nunca_abre_o_no: None,
    player: int,
    modo: str,
    caminho: str,
    via: str,
    quem: str,
) -> None:
    mesa, pads = _mesa(raizes, player, modo, caminho, via)
    todos = [no for nos in mesa.nos.values() for no in nos]
    if quem == "meu-pid":
        mesa.processo("forja", JOGOS["forja"], *todos, pid=MEU_PID)
    else:
        mesa.processo(COMM_DE.get(quem, quem), NAO_JOGOS.get(quem, f"/usr/bin/{quem}"), *todos)
    assert _o_jogo(pads) is None
    assert _veredito(pads) == "daemon"


@pytest.mark.parametrize("player", [1, 2, 3, 4])
@pytest.mark.parametrize(
    ("modo", "caminho"),
    [("dualsense", "uhid"), ("dualsense", "gadget"), ("edge", "uhid"), ("edge", "gadget")],
)
def test_o_cabo_e_o_radio_dao_o_mesmo_no(
    raizes: Path, player: int, modo: str, caminho: str
) -> None:
    """O físico pelo rádio chega em maiúsculas (BlueZ), e pelo cabo, em minúsculas (0x09)."""
    pad_cabo, nos = _pad(raizes, player, modo, caminho, "cabo")
    pad_radio = UhidDualSense(
        player=player, identity=FISICOS[player].upper(), product=PRODUTO[modo]
    )
    pad_radio._gadget = pad_cabo._gadget
    pelo_cabo, pelo_radio = qsp.nos_do_pad(pad_cabo), qsp.nos_do_pad(pad_radio)
    assert set(pelo_cabo) == {str(no) for no in nos}
    assert pelo_radio == pelo_cabo


def test_o_reaper_do_jogo_conta_e_o_avaliador_nao() -> None:
    reaper_jogo = "/x/reaper SteamLaunch AppId=99 -- /x/proton waitforexitandrun /x/jogo.exe"
    assert qsp.conta_como_jogo("reaper", reaper_jogo, pid=1, meu_pid=2)
    assert not qsp.conta_como_jogo("reaper", NAO_JOGOS["reaper-install"], pid=1, meu_pid=2)
    assert not qsp.conta_como_jogo("reaper", NAO_JOGOS["reaper"], pid=1, meu_pid=2)


@pytest.mark.parametrize(
    ("modo", "caminho"), [("dualsense", "uhid"), ("edge", "gadget"), ("xbox", "uinput")]
)
def test_o_jogo_que_larga_o_no_devolve_daemon_depois_da_histerese(
    raizes: Path, modo: str, caminho: str
) -> None:
    mesa, pads = _mesa(raizes, 4, modo, caminho, "radio")
    pid = mesa.processo("forja", JOGOS["forja"], mesa.nos[3][0])
    relogio = [100.0]
    sinal = GameSignal(time_fn=lambda: relogio[0])
    assert sinal.evaluate(_veredito(pads), session_open=True) == "game"
    mesa.larga(pid)
    assert _veredito(pads) == "daemon"
    relogio[0] += 10.0
    assert sinal.evaluate(_veredito(pads), session_open=True) == "game"
    relogio[0] += 29.0
    assert sinal.evaluate(_veredito(pads), session_open=True) == "game"
    relogio[0] += 1.0
    assert sinal.evaluate(_veredito(pads), session_open=True) == "daemon"


def test_a_transicao_diz_quem_a_deu(raizes: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.subsystems import game_signal

    registros: list[dict[str, Any]] = []
    monkeypatch.setattr(
        game_signal.logger, "info", lambda evento, **kw: registros.append({"evento": evento, **kw})
    )
    sinal = GameSignal(time_fn=lambda: 0.0)
    sinal.evaluate("game", session_open=True, processo_no_pad="forja")
    assert registros == [
        {
            "evento": "game_signal_transition",
            "de": "unknown",
            "para": "game",
            "evidencia": "processo_no_pad",
            "processo": "forja",
        }
    ]


def test_o_tique_do_daemon_le_o_pad(raizes: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A evidência viaja pelo `_gather_game_signal_inputs` e o tique a nomeia na transição."""
    import asyncio

    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.daemon.subsystems import game_signal
    from hefesto_dualsense4unix.testing import FakeController

    mesa, pads = _mesa(raizes, 2, "dualsense", "uhid", "cabo")
    mesa.processo("forja", JOGOS["forja"], mesa.nos[2][1])
    daemon = Daemon(
        controller=FakeController(transport="usb"),
        config=DaemonConfig(ipc_enabled=False, udp_enabled=False),
    )
    daemon._gamepad_device = pads[0]
    daemon._coop_manager = SimpleNamespace(_players={"b": SimpleNamespace(vpad=pads[1])})
    assert daemon._processo_no_pad() == "forja"

    from hefesto_dualsense4unix.daemon import launch_env
    from hefesto_dualsense4unix.integrations import steam_launch_options
    from hefesto_dualsense4unix.profiles import manager

    (raizes / "launch_env").mkdir()
    monkeypatch.setattr(launch_env, "launch_env_dir", lambda ensure=False: raizes / "launch_env")
    monkeypatch.setattr(steam_launch_options, "steam_game_running_appid", lambda: None)
    monkeypatch.setattr(manager, "perfis_para_consulta", lambda: [])
    daemon.store.set_window_detect_backend("xlib", healthy=True)
    daemon.store.record_window_detect_read(
        "xlib", "cosmic-files", wm_name="Arquivos", exe_basename="cosmic-files"
    )
    entradas = daemon._gather_game_signal_inputs()
    assert entradas["processo_no_pad"] == "forja"
    assert entradas["appid_de_jogo_vivo"] is None and entradas["profile_rule_match"] is False
    monkeypatch.setattr(daemon, "_gather_game_signal_inputs", lambda: dict(entradas))

    async def _rodar(fn: Any) -> Any:
        return fn()

    monkeypatch.setattr(daemon, "_run_blocking", _rodar)
    daemon._game_signal = GameSignal(time_fn=lambda: 0.0)
    registros: list[dict[str, Any]] = []
    monkeypatch.setattr(
        game_signal.logger, "info", lambda evento, **kw: registros.append({"evento": evento, **kw})
    )
    asyncio.run(daemon._sync_game_signal())
    assert daemon._game_signal.authority == "game"
    assert {"evidencia": "processo_no_pad", "processo": "forja"}.items() <= registros[0].items()
