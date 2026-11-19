"""QUEM-JOGA-E-QUEM-VIBRA-01 — o jogo manda, e não há portão de quem mexe na volta do rádio."""

from __future__ import annotations

import os
import pathlib
import socket

import pytest

from hefesto_dualsense4unix.integrations import quem_o_jogo_le as qjl
from hefesto_dualsense4unix.integrations.quem_o_jogo_le import ENV_DO_JOGO, pids_de_jogo


def _proc_de_mentira(raiz: pathlib.Path, processos: dict[int, bool]) -> pathlib.Path:
    """`/proc` de mentira: `{pid: é_jogo}`."""
    base = raiz / "proc"
    for pid, e_jogo in processos.items():
        d = base / str(pid)
        d.mkdir(parents=True, exist_ok=True)
        env = f"{ENV_DO_JOGO}=/algum/prefixo\0HOME=/x\0" if e_jogo else "HOME=/x\0"
        (d / "environ").write_bytes(env.encode("utf-8"))
    return base


class TestOSinalDosPids:
    def test_so_e_jogo_quem_tem_a_env_do_proton(self, tmp_path):
        base = _proc_de_mentira(tmp_path, {11: True, 22: False})
        assert pids_de_jogo(base) == {11}

    def test_proc_ilegivel_nao_vira_jogo(self, tmp_path):
        assert pids_de_jogo(tmp_path / "nao-existe") == set()


class TestONaoHaPortaoDeQuemMexe:
    """O subsystem não consulta mais quem joga: o jogo manda, o controle obedece."""

    def _corpo(self) -> str:
        fonte = pathlib.Path(
            "src/hefesto_dualsense4unix/daemon/subsystems/alto_falante.py"
        ).read_text(encoding="utf-8")
        corpo = fonte[fonte.index("def _casar_as_pontes") :]
        return corpo[: corpo.index("\n    def ", 1)]

    def test_a_volta_nao_consulta_quem_joga(self) -> None:
        """MORDIDA: devolva a consulta de quem mexeu à condição da háptica."""
        corpo = self._corpo()
        assert "este_joga" not in corpo, "o portão de quem mexe voltou à volta do rádio"
        assert "_quem_mexeu_na_partida" not in corpo
        assert "self._quem_o_jogo_le(controles)" not in corpo, (
            "a varredura de /proc voltou a rodar a cada volta"
        )

    def test_a_haptica_no_fio_exige_so_o_canal_aberto_e_o_ganho(self) -> None:
        """Desde 03/10/2026 não há modo; desde 26/10/2026 não há portão de toque."""
        corpo = self._corpo()
        i = corpo.index("leva = bool(")
        condicao = corpo[i : corpo.index("\n", i)]
        assert "endpoint_aberto" in condicao, "o canal saiu da condição da háptica"
        assert "este_joga" not in condicao
        assert "som_toca" not in condicao, "o alto-falante voltou a decidir a háptica"


SERVICO = "0::/user.slice/user-1000.slice/user@1000.service/session.slice/{}.service\n"
APP = "0::/user.slice/user-1000.slice/user@1000.service/app.slice/app-{}-1.scope\n"


class _Maquina:
    """`/proc`, `/sys` e `/dev` de mentira, com o pad virtual e o físico."""

    def __init__(self, raiz: pathlib.Path) -> None:
        self.raiz = raiz
        self.proc, self.sys, self.dev = raiz / "proc", raiz / "sys", raiz / "dev"
        self.proximo = 500
        self.pad = self._hidraw("hidraw7", "HID_PHYS=hefesto-vpad-1\nHID_UNIQ=02:fe:00:00:00:01\n")
        self.fisico = self._hidraw("hidraw2", "HID_PHYS=usb-0000:00:14.0-1/input3\n"
                                   "HID_UNIQ=aa:bb:cc:00:00:01\n")

    def _hidraw(self, no: str, uevent: str) -> pathlib.Path:
        (self.sys / "class/hidraw" / no / "device").mkdir(parents=True)
        (self.sys / "class/hidraw" / no / "device/uevent").write_text(uevent)
        self.dev.mkdir(exist_ok=True)
        (self.dev / no).write_bytes(b"")
        return self.dev / no

    def processo(
        self, comm: str, cmdline: str, *nos: pathlib.Path, cgroup: str = "", pid: int = 0
    ) -> int:
        pid = pid or self.proximo
        self.proximo += 1
        pasta = self.proc / str(pid)
        (pasta / "fd").mkdir(parents=True)
        (pasta / "comm").write_text(comm + "\n")
        (pasta / "cmdline").write_bytes(cmdline.replace(" ", "\0").encode() + b"\0")
        (pasta / "environ").write_bytes(b"HOME=/x\0")
        (pasta / "cgroup").write_text(cgroup)
        (pasta / "stat").write_text(f"{pid} ({comm}) S 1 {pid}\n")
        for n, no in enumerate(nos, start=3):
            (pasta / "fd" / str(n)).symlink_to(no)
        return pid

    def ha_jogo(self) -> bool:
        return qjl.ha_jogo_aberto(str(self.proc), str(self.sys), str(self.dev), meu_pid=1)


@pytest.fixture
def maquina(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> _Maquina:
    (tmp_path / "run").mkdir()
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(qjl, "RAIZ_RUNTIME", str(tmp_path / "run"))
    return _Maquina(tmp_path)


class TestOJogoAbertoEmQualquerLancador:
    def test_o_emulador_sem_a_variavel_que_segura_o_pad_e_jogo(self, maquina: _Maquina) -> None:
        """D-1911-O-JOGO-ABERTO-SE-VE-EM-QUALQUER-LANCADOR: o emulador sem Proton conta."""
        assert maquina.ha_jogo() is False
        maquina.processo("retroarch", "/usr/bin/retroarch -L snes9x", maquina.pad,
                         cgroup=APP.format("retroarch"))
        assert maquina.ha_jogo() is True

    def test_o_compositor_o_lancador_e_o_fundo_no_pad_nao_sao_jogo(
        self, maquina: _Maquina
    ) -> None:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as compositor:
            compositor.bind(str(maquina.raiz / "run" / "wayland-0"))
            compositor.listen()
            maquina.processo(
                "kwin_wayland", "/usr/bin/kwin_wayland", maquina.pad, pid=os.getpid()
            )
            maquina.processo("heroic", "/opt/Heroic/heroic", maquina.pad)
            maquina.processo("input-remapper-", "/usr/bin/python3 /usr/bin/input-remapper-gtk",
                             maquina.pad, cgroup=SERVICO.format("input-remapper"))
            assert maquina.ha_jogo() is False

    def test_o_jogo_no_controle_fisico_nao_e_o_pad_do_hefesto(self, maquina: _Maquina) -> None:
        maquina.processo("retroarch", "/usr/bin/retroarch", maquina.fisico)
        assert maquina.ha_jogo() is False

    def test_o_mouse_e_o_teclado_do_hefesto_nao_sao_pad(self, maquina: _Maquina) -> None:
        from hefesto_dualsense4unix.integrations import uinput_gamepad, uinput_mouse

        def evento(no: str, nome: str) -> pathlib.Path:
            (maquina.sys / "class/input" / no / "device").mkdir(parents=True)
            (maquina.sys / "class/input" / no / "device/name").write_text(nome + "\n")
            (maquina.dev / "input").mkdir(exist_ok=True)
            (maquina.dev / "input" / no).write_bytes(b"")
            return maquina.dev / "input" / no

        teclas = [evento(f"event{n}", nome) for n, nome in enumerate(
            (uinput_mouse.DEVICE_NAME, uinput_mouse.NOME_DO_CURSOR_DO_TOQUE), start=20)]
        pads = [evento(f"event{n}", nome) for n, nome in enumerate(
            (uinput_gamepad.XBOX360_NAME, uinput_gamepad.NINTENDO_PROCON_NAME), start=30)]
        maquina.processo("libinput", "libinput debug-events", *teclas)
        assert maquina.ha_jogo() is False
        achados = qjl.nos_dos_pads_virtuais(str(maquina.sys), str(maquina.dev)).values()
        assert sorted(achados) == sorted(map(str, [maquina.pad, *pads]))
