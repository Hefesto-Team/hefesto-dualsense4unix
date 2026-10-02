"""Mover UM por vez — MOVER-UM-POR-VEZ-01 (23/09/2026)."""

from __future__ import annotations

import os
import re
import subprocess
import threading
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import central_do_radio as cr
from hefesto_dualsense4unix.integrations import diario_do_radio
from tests.unit.radio_de_mentira import QUARTO, SALA, VARANDA, VERMELHO

RAIZ = Path(__file__).resolve().parents[2]
PONTE = RAIZ / "scripts" / "bt_ponte_privilegiada.sh"


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A trava e o diário numa pasta de teste — nunca os dela, em ``/run``."""
    monkeypatch.setenv(diario_do_radio.ENV_TRAVA, str(tmp_path / "radio.lock"))
    caminho = tmp_path / "radio-diario.jsonl"
    monkeypatch.setenv(diario_do_radio.ENV_DIARIO, str(caminho))
    return caminho


_INFO_COM_CHAVE = "[General]\nName=controle\n\n[LinkKey]\nKey=00\nType=4\nPINLength=0\n"


def _ambiente_da_ponte(tmp_path: Path) -> dict[str, str]:
    env = {c: v for c, v in os.environ.items() if c not in ("SUDO_UID", "SUDO_USER")}
    env.update(
        HEFESTO_BT_LIB=str(tmp_path / "bluetooth"),
        HEFESTO_BT_LOG_DEST="none",
        HEFESTO_BT_LAPIDES=str(tmp_path / ".lapides"),
        HEFESTO_RADIO_DIARIO_ROOT=str(tmp_path / "diario-root.jsonl"),
        HEFESTO_SYS_BLUETOOTH=str(tmp_path / "sys-bluetooth"),
    )
    return env


def test_o_esquecer_da_origem_guarda_o_cache_sdp_do_bond_novo(tmp_path: Path) -> None:
    """Quando o esquecer roda, o controle JÁ tem bond novo no destino (a ordem"""
    lib = tmp_path / "bluetooth"
    sala, quarto, varanda, vermelho = (m.upper() for m in (SALA, QUARTO, VARANDA, VERMELHO))
    for adaptador in (sala, quarto):
        (lib / adaptador / vermelho).mkdir(parents=True)
        (lib / adaptador / vermelho / "info").write_text(_INFO_COM_CHAVE, encoding="utf-8")
        (lib / adaptador / "cache").mkdir()
        (lib / adaptador / "cache" / vermelho).write_text("[ServiceRecords]\n", encoding="utf-8")
    (lib / varanda / "cache").mkdir(parents=True)
    (lib / varanda / "cache" / vermelho).write_text("[ServiceRecords]\n", encoding="utf-8")

    resultado = subprocess.run(
        ["bash", str(PONTE), "esquecer"],
        input=f"{SALA}\n{VERMELHO}\n",
        capture_output=True,
        text=True,
        timeout=60,
        env=_ambiente_da_ponte(tmp_path),
    )

    assert resultado.returncode == 0, resultado.stderr
    assert not (lib / sala / vermelho).exists()
    assert not (lib / sala / "cache" / vermelho).exists()
    assert (lib / quarto / vermelho / "info").exists()
    assert (lib / quarto / "cache" / vermelho).exists(), "o SDP do bond novo sobrevive"
    assert not (lib / varanda / "cache" / vermelho).exists(), "a sobra de scan sai"
    [lapide] = (tmp_path / ".lapides").read_text(encoding="utf-8").splitlines()
    assert lapide.split()[1:] == [sala, vermelho]


def _handlers(daemon: Any) -> Any:
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    class _Handlers(IpcHandlersMixin):
        def __init__(self, alvo: Any) -> None:
            self.daemon = alvo

    return _Handlers(daemon)


def _esperar(condicao: Any, teto: float = 5.0) -> bool:
    import time

    fim = time.monotonic() + teto
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(0.01)
    return bool(condicao())


_DEPOIS_DO_RADIO_MOVER = ("mira.set", "haptica.testar", "radio.busca.set", "radio.dispensar")


def test_radio_mover_e_o_ultimo_metodo_da_tabela() -> None:
    """Método IPC novo vai no FIM da tabela — regra da leva."""
    fonte = (RAIZ / "src/hefesto_dualsense4unix/daemon/ipc_server.py").read_text(encoding="utf-8")
    ultimo = fonte.index('"radio.mover": self._handle_radio_mover,')
    fecha = fonte.index("\n        }\n", ultimo)
    depois = re.findall(r'"([^"]+)": self\._handle_', fonte[ultimo:fecha])
    assert tuple(depois) == ("radio.mover", *_DEPOIS_DO_RADIO_MOVER), (
        f"depois do radio.mover a tabela traz {depois[1:]}, e só "
        f"{list(_DEPOIS_DO_RADIO_MOVER)} nasceram depois dele")


@pytest.mark.asyncio
async def test_o_daemon_abre_o_dono_no_arranque_fora_do_laco(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O dono do BlueZ abre no arranque, num fio — nunca no laço, nunca na tela."""
    import inspect

    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.testing import FakeController

    fios: list[str] = []
    monkeypatch.setattr(
        cr.CentralDoRadio, "ligar", lambda self: fios.append(threading.current_thread().name)
    )
    monkeypatch.delenv("HEFESTO_DUALSENSE4UNIX_FAKE", raising=False)
    daemon = Daemon(controller=FakeController(transport="bt"))

    await daemon._start_central_do_radio()

    assert isinstance(daemon._central_do_radio, cr.CentralDoRadio)
    assert fios and fios[0] != threading.main_thread().name
    assert '"central_do_radio", self._start_central_do_radio' in inspect.getsource(Daemon.run)

    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_FAKE", "1")
    falso = Daemon(controller=FakeController(transport="bt"))
    await falso._start_central_do_radio()
    assert falso._central_do_radio is None, "o daemon de fumaça não pareia nada"


def test_o_movimento_da_central_vem_do_sensor_hub_do_ipc() -> None:
    from types import SimpleNamespace

    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.testing import FakeController

    perguntas: list[str] = []

    def hz(uniq: str) -> float:
        perguntas.append(uniq)
        return 248.0

    hub = SimpleNamespace(hz_do_movimento=hz)
    daemon = Daemon(controller=FakeController(transport="bt"))
    assert daemon._movimento_para_a_central("aabbcc000001") is None
    daemon._ipc_server = SimpleNamespace(_garantir_sensor_hub=lambda: hub)
    assert daemon._movimento_para_a_central("aabbcc000001") == 248.0
    assert perguntas == ["aabbcc000001"]


def _bancada_com_trava(tmp_path: Path) -> tuple[Any, Path, Path]:
    from tests.unit.test_o_prefixo_vai_no_adaptador_que_hospeda_nintendo import Bancada

    banca = Bancada(tmp_path)
    trava = tmp_path / "run" / "radio.lock"
    trava.parent.mkdir()
    real = banca.fakes / "busctl-real"
    (banca.fakes / "busctl").rename(real)
    no_instante = tmp_path / "trava-no-set-property.txt"
    (banca.fakes / "busctl").write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$1" == "set-property" ]]; then\n'
        f"    if flock -n '{trava}' true; then echo livre; else echo presa; fi >> '{no_instante}'\n"
        "fi\n"
        f"exec '{real}' \"$@\"\n",
        encoding="utf-8",
    )
    (banca.fakes / "busctl").chmod(0o755)
    return banca, trava, no_instante


def _ambiente_do_script(banca: Any, trava: Path, **extra: str) -> dict[str, str]:
    return {
        "PATH": ":".join([str(banca.fakes), "/usr/bin", "/bin"]),
        "HOME": str(banca.tmp),
        "LANG": os.environ.get("LANG", "pt_BR.UTF-8"),
        "HEFESTO_SYS_BLUETOOTH": str(banca.sys_bt),
        "HEFESTO_BT_LIB": str(banca.lib),
        "HEFESTO_BT_LOG_DEST": str(banca.log),
        "HEFESTO_RADIO_TRAVA": str(trava),
        **extra,
    }


ATIVO = RAIZ / "scripts" / "bt_active_mode.sh"


def test_o_alias_e_escrito_com_a_trava_na_mao(tmp_path: Path) -> None:
    """MORDIDA: tire o ``_na_trava`` do laço do alias — o ``set-property`` roda"""
    from tests.unit.test_o_prefixo_vai_no_adaptador_que_hospeda_nintendo import (
        HOSPEDEIRO_DO_PRO,
    )

    banca, trava, no_instante = _bancada_com_trava(tmp_path)

    feito = subprocess.run(
        ["bash", str(ATIVO), "--quiet"], capture_output=True, text=True, timeout=60,
        env=_ambiente_do_script(banca, trava),
    )

    assert feito.returncode == 0, feito.stderr
    assert HOSPEDEIRO_DO_PRO in banca.aliases_escritos()
    assert no_instante.read_text(encoding="utf-8").split() == ["presa"]


def test_com_outro_motor_na_trava_o_alias_espera_o_prazo_e_desiste(tmp_path: Path) -> None:
    import fcntl

    banca, trava, _no_instante = _bancada_com_trava(tmp_path)
    with open(trava, "a+") as outro_motor:
        fcntl.flock(outro_motor, fcntl.LOCK_EX)
        feito = subprocess.run(
            ["bash", str(ATIVO), "--quiet"], capture_output=True, text=True, timeout=60,
            env=_ambiente_do_script(banca, trava, HEFESTO_RADIO_TRAVA_PRAZO_S="1"),
        )

    assert feito.returncode == 0, feito.stderr
    assert banca.aliases_escritos() == {}, "escreveu por cima de outro motor"
    assert "outro motor segura a trava do rádio" in banca.log.read_text(encoding="utf-8")


def test_a_trava_herdada_do_watchdog_nao_espera_o_proprio_pai(tmp_path: Path) -> None:
    """O watchdog chama o script com o tique inteiro na trava, e o descritor vem"""
    import time

    from tests.unit.test_o_prefixo_vai_no_adaptador_que_hospeda_nintendo import (
        HOSPEDEIRO_DO_PRO,
    )

    banca, trava, no_instante = _bancada_com_trava(tmp_path)
    tique = (
        f"exec {{fd}}<>'{trava}' && flock -n \"$fd\" || exit 9\n"
        f"bash '{ATIVO}' --quiet\n"
    )
    antes = time.monotonic()
    feito = subprocess.run(
        ["bash", "-c", tique], capture_output=True, text=True, timeout=60,
        env=_ambiente_do_script(banca, trava, HEFESTO_RADIO_TRAVA_PRAZO_S="3"),
    )

    assert feito.returncode == 0, feito.stderr
    assert time.monotonic() - antes < 3.0, "o filho esperou o próprio pai"
    assert HOSPEDEIRO_DO_PRO in banca.aliases_escritos()
    assert no_instante.read_text(encoding="utf-8").split() == ["presa"]
