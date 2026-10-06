"""A-SUITE-NAO-AVISA-NA-TELA-DELA-01 — nenhum teste manda aviso para a tela dela."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import desktop_notifications as avisos

RAIZ = Path(__file__).resolve().parents[2]

_AVISOS_DE_GESTO = (
    ("teclado na tela aberto", avisos.notify_teclado_na_tela_aberto, ()),
    ("teclado na tela ausente", avisos.notify_teclado_na_tela_ausente, (["wvkbd-mobintl"],)),
    ("modo jogo ligado", avisos.notify_emulation_suppressed, (True,)),
    ("modo jogo desligado", avisos.notify_emulation_suppressed, (False,)),
)


@pytest.fixture(autouse=True)
def _caches_zerados() -> Iterator[None]:
    """O `once_key` de um caso não pode calar o seguinte e fingir a cura."""
    avisos.reset_once_cache()
    yield
    avisos.reset_once_cache()


_JEEPNEY_DE_MENTIRA = textwrap.dedent(
    """
    import sys
    import types

    aberturas = []

    def _abrir(bus="SESSION", **_):
        aberturas.append(bus)
        raise ConnectionRefusedError("barramento de mentira: nada sai daqui")

    jeepney = types.ModuleType("jeepney")
    jeepney.DBusAddress = lambda *a, **k: None
    jeepney.new_method_call = lambda *a, **k: None
    jeepney_io = types.ModuleType("jeepney.io")
    jeepney_io_blocking = types.ModuleType("jeepney.io.blocking")
    jeepney_io_blocking.open_dbus_connection = _abrir
    jeepney.io = jeepney_io
    jeepney_io.blocking = jeepney_io_blocking
    """
)


@pytest.fixture
def aberturas_do_barramento(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Cada vez que o `notify` tenta abrir um barramento, uma linha aqui."""
    modulos: dict[str, Any] = {}
    exec(_JEEPNEY_DE_MENTIRA, modulos)
    monkeypatch.setitem(sys.modules, "jeepney", modulos["jeepney"])
    monkeypatch.setitem(sys.modules, "jeepney.io", modulos["jeepney_io"])
    monkeypatch.setitem(sys.modules, "jeepney.io.blocking", modulos["jeepney_io_blocking"])
    aberturas: list[str] = modulos["aberturas"]
    return aberturas


def test_com_a_suite_no_ar_nenhum_aviso_de_gesto_abre_o_barramento(
    aberturas_do_barramento: list[str],
) -> None:
    """A RÉGUA. Os quatro avisos de gesto recusam antes do barramento."""
    for nome, aviso, argumentos in _AVISOS_DE_GESTO:
        assert aviso(*argumentos) is False, f"o aviso «{nome}» saiu com a suíte no ar"
    assert aberturas_do_barramento == [], (
        "com a suíte no ar o `notify` abriu o barramento da sessão — na máquina "
        "dela é o aviso na tela dela, o defeito de 25/09/2026 às 20h18"
    )


def test_a_referencia_copiada_por_from_import_tambem_recusa(
    aberturas_do_barramento: list[str],
) -> None:
    """A bandeja faz `from … import notify`: a cópia recusa igual."""
    from hefesto_dualsense4unix.integrations.desktop_notifications import notify

    assert notify("Hefesto", "a bandeja não apareceu", once_key="copia") is False
    assert aberturas_do_barramento == []


def test_o_escape_devolve_o_caminho_inteiro(
    monkeypatch: pytest.MonkeyPatch, aberturas_do_barramento: list[str]
) -> None:
    """Com `HEFESTO_AVISO_DE_VERDADE=1` o `notify` chega ao barramento (dublado)."""
    monkeypatch.setenv(avisos.AVISO_DE_VERDADE_NA_SUITE, "1")
    assert avisos.notify_teclado_na_tela_aberto() is False
    assert aberturas_do_barramento == ["SESSION"]


def test_o_escape_herdado_nao_atravessa_para_o_teste() -> None:
    """O escape que viesse do terminal de quem roda a suíte não chega aqui."""
    assert avisos.AVISO_DE_VERDADE_NA_SUITE not in os.environ, (
        "o escape do aviso chegou a um teste que não o declarou: cada L3 da "
        "suíte voltaria a aparecer na tela dela"
    )


_FILHO = _JEEPNEY_DE_MENTIRA + textwrap.dedent(
    """
    sys.modules.update({
        "jeepney": jeepney,
        "jeepney.io": jeepney_io,
        "jeepney.io.blocking": jeepney_io_blocking,
    })
    from hefesto_dualsense4unix.integrations import desktop_notifications as avisos

    assert "pytest" not in sys.modules
    avisos.notify_teclado_na_tela_aberto()
    print(len(aberturas))
    """
)


def _aberturas_no_filho(ambiente: dict[str, str]) -> int:
    saida = subprocess.run(
        [sys.executable, "-c", _FILHO],
        env=ambiente,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return int(saida.stdout.strip().splitlines()[-1])


def test_o_processo_filho_de_um_teste_tambem_recusa() -> None:
    """Um daemon subido por um teste herda `PYTEST_CURRENT_TEST` e cala."""
    ambiente = dict(os.environ)
    ambiente["PYTHONPATH"] = str(RAIZ / "src")
    assert ambiente.get("PYTEST_CURRENT_TEST")
    assert _aberturas_no_filho(ambiente) == 0

    ambiente.pop("PYTEST_CURRENT_TEST")
    assert _aberturas_no_filho(ambiente) == 1


_CONFIG_DO_BARRAMENTO = """<!DOCTYPE busconfig PUBLIC
 "-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <type>session</type>
  <listen>unix:dir={pasta}</listen>
  <auth>EXTERNAL</auth>
  <policy context="default">
    <allow send_destination="*" eavesdrop="true"/>
    <allow eavesdrop="true"/>
    <allow own="*"/>
  </policy>
</busconfig>
"""


class _ServidorDeAvisos:
    """Dono de `org.freedesktop.Notifications` no barramento deste teste."""

    def __init__(self, endereco: str) -> None:
        from jeepney.bus_messages import message_bus
        from jeepney.io.blocking import open_dbus_connection

        self.notify: list[str] = []
        self._parar = threading.Event()
        self._conexao = open_dbus_connection(bus=endereco)
        resposta = self._conexao.send_and_get_reply(
            message_bus.RequestName("org.freedesktop.Notifications", 4), timeout=5
        )
        assert resposta.body[0] == 1, "o barramento de mentira já tinha dono do nome"
        self._fio = threading.Thread(target=self._servir, daemon=True)
        self._fio.start()

    def _servir(self) -> None:
        from jeepney import HeaderFields, MessageType, new_method_return

        while not self._parar.is_set():
            try:
                mensagem = self._conexao.receive(timeout=0.1)
            except TimeoutError:
                continue
            except Exception:
                return
            if mensagem.header.message_type != MessageType.method_call:
                continue
            if mensagem.header.fields.get(HeaderFields.member) == "Notify":
                self.notify.append(str(mensagem.body[3]))
                self._conexao.send(new_method_return(mensagem, "u", (len(self.notify),)))

    def fechar(self) -> None:
        self._parar.set()
        self._fio.join(timeout=2)
        self._conexao.close()


@pytest.fixture
def barramento_de_mentira(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[_ServidorDeAvisos]:
    pytest.importorskip("jeepney.io.blocking")
    dbus_daemon = shutil.which("dbus-daemon")
    if dbus_daemon is None:
        pytest.skip("sem `dbus-daemon` nesta máquina — as réguas de cima seguram a trava")
    config = tmp_path / "barramento.conf"
    config.write_text(_CONFIG_DO_BARRAMENTO.format(pasta=tmp_path), encoding="utf-8")
    daemon = subprocess.Popen(
        [dbus_daemon, f"--config-file={config}", "--nofork", "--print-address=1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    servidor: _ServidorDeAvisos | None = None
    try:
        assert daemon.stdout is not None
        endereco = daemon.stdout.readline().strip()
        assert endereco.startswith("unix:"), f"o dbus-daemon não disse o endereço: {endereco!r}"
        assert str(tmp_path) in endereco, "o endereço não é o do barramento deste teste"
        monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", endereco)
        servidor = _ServidorDeAvisos(endereco)
        yield servidor
    finally:
        if servidor is not None:
            servidor.fechar()
        daemon.terminate()
        try:
            daemon.wait(timeout=5)
        except subprocess.TimeoutExpired:
            daemon.kill()
            daemon.wait(timeout=5)


def _apertar_o_l3(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """O L3 pelo caminho do produto, com o teclado na tela de mentira."""
    from hefesto_dualsense4unix.core.keyboard_mappings import DEFAULT_BUTTON_BINDINGS
    from hefesto_dualsense4unix.daemon.subsystems import keyboard as subsistema
    from hefesto_dualsense4unix.integrations.uinput_keyboard import UinputKeyboardDevice

    abertos: list[list[str]] = []

    class _Processo:
        pid = 4242

        def poll(self) -> int | None:
            return None

        def terminate(self) -> None:
            pass

    def _popen(argv: list[str], **_: Any) -> _Processo:
        abertos.append(list(argv))
        return _Processo()

    monkeypatch.setattr(
        subsistema.shutil, "which",
        lambda nome: f"/usr/bin/{nome}" if nome == "wvkbd-mobintl" else None,
    )
    monkeypatch.setattr(subsistema.subprocess, "Popen", _popen)
    monkeypatch.setattr(subsistema, "_OSK_SONDA", [(float("-inf"), False)])

    controlador = subsistema._OSKController()
    teclado = UinputKeyboardDevice(
        bindings=dict(DEFAULT_BUTTON_BINDINGS),
        virtual_token_callback=controlador.dispatch_token,
    )
    teclado._device = object()
    teclado._uinput_mod = object()
    teclado.dispatch(frozenset({"l3"}))
    teclado.dispatch(frozenset())
    assert controlador.esperar_os_toques(5.0)
    return abertos


def test_o_l3_da_suite_nao_chega_ao_servidor_de_avisos(
    monkeypatch: pytest.MonkeyPatch, barramento_de_mentira: _ServidorDeAvisos
) -> None:
    """A PROVA DA SPRINT, no barramento: o L3 abre o teclado e o servidor conta zero."""
    abertos = _apertar_o_l3(monkeypatch)
    assert abertos, "o L3 não abriu o teclado de mentira — o caso não mediu nada"
    time.sleep(0.2)
    assert barramento_de_mentira.notify == [], (
        "o L3 de um teste chegou ao servidor de avisos: na máquina dela, é o "
        "aviso na tela dela"
    )


def test_com_o_escape_o_mesmo_l3_chega_ao_servidor_de_avisos(
    monkeypatch: pytest.MonkeyPatch, barramento_de_mentira: _ServidorDeAvisos
) -> None:
    """A contraprova do caso acima: o servidor conta, e o zero de lá não é surdez."""
    monkeypatch.setenv(avisos.AVISO_DE_VERDADE_NA_SUITE, "1")
    assert _apertar_o_l3(monkeypatch)
    assert barramento_de_mentira.notify == [avisos._OSK_ABERTO_TITULO]
