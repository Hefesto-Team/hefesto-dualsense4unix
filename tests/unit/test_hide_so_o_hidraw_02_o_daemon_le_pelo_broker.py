"""HIDE-SO-O-HIDRAW-02 — o daemon continua lendo o físico com os nós fechados.

Com os quatro nós de entrada do DualSense físico nascendo `0600 root`, o
daemon perde o `open(path)` do gamepad, do touchpad e dos sensores de
movimento. Sem outra porta, o cartão do touchpad fica CEGO — é o que a célula
`toque.touchpad` da bancada existe para acusar. A porta é a do hidraw: o `open`
do broker, que devolve o fd por SCM_RIGHTS.

Esta régua não toca /dev, o sysfs real nem o broker vivo. O `InputDevice` da
biblioteca é trocado por um que recusa o caminho com `PermissionError` (o que
o kernel faz com um nó `0600 root`); o broker é um abridor que devolve a ponta
de leitura de um `pipe`; e os ioctls de identidade (`_input.ioctl_*`) dão a
resposta de um DualSense. O resto é o produto: o filtro do sysfs, o objeto
montado em volta do fd, o laço do leitor e o `dev.read()` de verdade, que lê
`struct input_event` do pipe como leria do nó.
"""
from __future__ import annotations

import contextlib
import inspect
import os
import re
import struct
import time
from pathlib import Path
from typing import Any

import pytest

evdev = pytest.importorskip("evdev")

from hefesto_dualsense4unix.core import evdev_reader as er

#: Números de nó que não existem na máquina de ninguém: o `_is_virtual_evdev`
#: lê o `/sys/class/input` REAL, e um número baixo poderia casar um nó vivo.
NO_TOUCHPAD = "/dev/input/event9029"
NO_GAMEPAD = "/dev/input/event9027"
NO_TECLADO = "/dev/input/event9003"

#: `struct input_event` no x86_64: timeval (dois long) + type, code (u16) +
#: value (s32).
_FORMATO_DO_EVENTO = "llHHi"


def _evento(tipo: int, codigo: int, valor: int) -> bytes:
    return struct.pack(_FORMATO_DO_EVENTO, 0, 0, tipo, codigo, valor)


def _sysfs(raiz: Path, no: str, *, vendor: str, product: str, nome: str, teclas: str) -> None:
    base = Path(no).name
    dev = raiz / base / "device"
    (dev / "id").mkdir(parents=True)
    (dev / "id" / "vendor").write_text(vendor + "\n", encoding="ascii")
    (dev / "id" / "product").write_text(product + "\n", encoding="ascii")
    (dev / "name").write_text(nome + "\n", encoding="utf-8")
    (dev / "capabilities").mkdir()
    (dev / "capabilities" / "key").write_text(teclas + "\n", encoding="ascii")


#: O bitmap `capabilities/key` de um gamepad DualSense (BTN_SOUTH..BTN_THUMBR
#: na palavra 4) e o de um touchpad (BTN_LEFT, BTN_TOUCH, BTN_TOOL_*).
_TECLAS_DO_GAMEPAD = "7fdb000000000000 0 0 0 0"
_TECLAS_DO_TOUCHPAD = "e520 10000 0 0 0 0"


class _Recusa:
    """O `InputDevice` visto de um nó `0600 root`: o caminho é recusado."""

    def __init__(self, fechados: set[str]) -> None:
        self.fechados = fechados
        self.tentativas: list[str] = []

    def __call__(self, caminho: str) -> Any:
        self.tentativas.append(caminho)
        if caminho in self.fechados:
            raise PermissionError(13, "Permission denied", caminho)
        raise FileNotFoundError(2, "No such file or directory", caminho)


class _Broker:
    """O `open` do broker: devolve a ponta de leitura de um pipe por nó."""

    def __init__(self, servidos: set[str]) -> None:
        self.servidos = servidos
        self.pedidos: list[str] = []
        self.escritas: dict[str, int] = {}

    def __call__(self, caminho: str) -> int | None:
        self.pedidos.append(caminho)
        if caminho not in self.servidos:
            return None
        leitura, escrita = os.pipe()
        self.escritas[caminho] = escrita
        return leitura

    def fechar(self) -> None:
        for fd in self.escritas.values():
            with contextlib.suppress(OSError):
                os.close(fd)


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    """O físico fechado, o sysfs de mentira e o broker de pipe."""
    raiz = tmp_path / "sys-class-input"
    _sysfs(raiz, NO_TOUCHPAD, vendor="054c", product="0ce6",
           nome="DualSense Wireless Controller Touchpad", teclas=_TECLAS_DO_TOUCHPAD)
    _sysfs(raiz, NO_GAMEPAD, vendor="054c", product="0ce6",
           nome="DualSense Wireless Controller", teclas=_TECLAS_DO_GAMEPAD)
    _sysfs(raiz, NO_TECLADO, vendor="3554", product="fa09",
           nome="CX 2.4G Wireless Receiver Keyboard", teclas="1 0 0 0")
    monkeypatch.setattr(er, "SYS_CLASS_INPUT", str(raiz))

    recusa = _Recusa({NO_TOUCHPAD, NO_GAMEPAD, NO_TECLADO})
    monkeypatch.setattr("evdev.InputDevice.__init__", lambda self, dev: recusa(str(dev)))
    broker = _Broker({NO_TOUCHPAD, NO_GAMEPAD})
    monkeypatch.setattr(er, "_ABRIDOR_DO_BROKER", broker)

    from evdev import _input

    def _devinfo(fd: int) -> tuple[Any, ...]:
        return (0x0005, 0x054C, 0x0CE6, 0x8111, "DualSense Wireless Controller Touchpad",
                "", "e8:47:3a:00:00:07")

    monkeypatch.setattr(_input, "ioctl_devinfo", _devinfo)
    monkeypatch.setattr(_input, "ioctl_EVIOCGVERSION", lambda fd: 0x010001)
    monkeypatch.setattr(_input, "ioctl_capabilities", lambda fd: {})
    monkeypatch.setattr(_input, "ioctl_EVIOCGEFFECTS", lambda fd: 0)
    yield broker, recusa
    broker.fechar()


class TestAPortaDoNoFechado:
    def test_o_no_fechado_abre_pelo_broker(self, mesa: Any) -> None:
        broker, _ = mesa
        dev = er.abrir_input_device(NO_TOUCHPAD)
        try:
            assert broker.pedidos == [NO_TOUCHPAD]
            assert dev.path == NO_TOUCHPAD
            assert dev.info.vendor == 0x054C and dev.info.product == 0x0CE6
            assert dev.uniq == "e8:47:3a:00:00:07"
            assert os.get_blocking(dev.fd) is False
        finally:
            dev.close()

    def test_no_que_nao_e_dualsense_nunca_vai_ao_broker(self, mesa: Any) -> None:
        """O teclado dela não é assunto do broker. A MORDIDA: tire o
        `_no_de_dualsense_no_sysfs` e o broker recebe o pedido do teclado."""
        broker, _ = mesa
        with pytest.raises(PermissionError):
            er.abrir_input_device(NO_TECLADO)
        assert broker.pedidos == []

    def test_broker_que_recusa_devolve_a_permissao_negada(
        self, mesa: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        broker, _ = mesa
        broker.servidos.clear()
        with pytest.raises(PermissionError):
            er.abrir_input_device(NO_TOUCHPAD)
        assert broker.pedidos == [NO_TOUCHPAD]

    def test_o_filtro_do_chamador_poupa_o_broker(self, mesa: Any) -> None:
        broker, _ = mesa
        with pytest.raises(PermissionError):
            er.abrir_input_device(NO_TOUCHPAD, pede_ao_broker=lambda _c: False)
        assert broker.pedidos == []

    def test_no_aberto_nem_consulta_o_broker(
        self, mesa: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem a cura instalada, e no Modo Nativo, o caminho abre como sempre."""
        broker, _ = mesa
        aberto = object()
        monkeypatch.setattr("evdev.InputDevice", lambda _c: aberto)
        assert er.abrir_input_device(NO_TOUCHPAD) is aberto
        assert broker.pedidos == []


def _list_devices_da_biblioteca(pasta: Path) -> list[str]:
    """O `evdev.list_devices()` com o critério da BIBLIOTECA: só o nó que abre.

    O `evdev/util.py:is_device` pede `os.access(R_OK | W_OK)` — e a primeira
    versão desta régua trocava o `list_devices` por uma lista que devolvia
    também os nós FECHADOS, mais frouxa que a biblioteca: a descoberta real
    nunca via o físico, e a régua dava verde. O `S_ISCHR` da biblioteca fica de
    fora só porque a suíte não cria char device sem root; o critério que
    decide aqui é o do acesso, e ele é o de verdade.
    """
    return [str(c) for c in sorted(pasta.glob("event*")) if os.access(c, os.R_OK | os.W_OK)]


@pytest.fixture
def dev_input(mesa: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, str]:
    """O `/dev/input` de mentira: o gamepad e o touchpad do físico FECHADOS
    (modo 0000, como o `0600 root` é para ela), o teclado aberto, e o socket
    do broker de pé."""
    if os.geteuid() == 0:  # pragma: no cover - como root o 0000 não fecha nada
        pytest.skip("como root todo nó abre")
    broker, recusa = mesa
    pasta = tmp_path / "dev-input"
    pasta.mkdir()
    caminhos: dict[str, str] = {}
    for no, modo in ((NO_GAMEPAD, 0o000), (NO_TOUCHPAD, 0o000), (NO_TECLADO, 0o660)):
        arquivo = pasta / Path(no).name
        arquivo.write_text("", encoding="ascii")
        arquivo.chmod(modo)
        caminhos[no] = str(arquivo)
    monkeypatch.setattr(er, "DEV_INPUT_DIR", str(pasta))
    monkeypatch.setattr("evdev.list_devices", lambda: _list_devices_da_biblioteca(pasta))
    socket_do_broker = tmp_path / "broker.sock"
    socket_do_broker.write_text("", encoding="ascii")
    monkeypatch.setenv("HEFESTO_BROKER_SOCKET", str(socket_do_broker))
    fisicos = {caminhos[NO_GAMEPAD], caminhos[NO_TOUCHPAD]}
    recusa.fechados |= fisicos
    broker.servidos |= fisicos
    return caminhos


class TestADescobertaAchaOFisicoFechado:
    def test_a_biblioteca_filtra_pelo_acesso(self) -> None:
        """A premissa do dublê acima: a biblioteca filtra pelo acesso. Se uma
        versão do python-evdev parar de filtrar, esta régua avisa que o
        `_nos_de_evento` passou a ser redundante — não errado."""
        from evdev import util

        assert "os.access" in inspect.getsource(util.is_device)

    def test_o_touchpad_fechado_entra_no_mapa(
        self, mesa: Any, dev_input: dict[str, str]
    ) -> None:
        """Antes, o `except Exception: continue` engolia o EACCES e o
        controle saía do mapa «sem touchpad». A MORDIDA (conferência): faça o
        `_nos_de_evento` devolver só o `list_devices()` da biblioteca e o mapa
        sai vazio — o nó fechado nem chega ao `abrir_input_device`."""
        broker, _ = mesa
        mapa = er.discover_dualsense_touchpad_evdevs()
        assert list(mapa.values()) == [Path(dev_input[NO_TOUCHPAD])]
        # Ao broker foi SÓ o nó cujo nome é de touchpad.
        assert broker.pedidos == [dev_input[NO_TOUCHPAD]]

    def test_o_gamepad_fechado_entra_na_descoberta(
        self, mesa: Any, dev_input: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        broker, _ = mesa
        from evdev import ecodes

        monkeypatch.setattr(
            "evdev._input.ioctl_capabilities",
            lambda fd: {ecodes.EV_KEY: [ecodes.BTN_SOUTH], ecodes.EV_ABS: []},
        )
        achados = er.discover_gamepads(com_sysfs=False)
        assert [g.evdev_path for g in achados] == [dev_input[NO_GAMEPAD]]
        # O touchpad não tem BTN_GAMEPAD no sysfs: não foi pedido ao broker.
        assert broker.pedidos == [dev_input[NO_GAMEPAD]]

    def test_sem_broker_o_no_fechado_fica_de_fora(
        self, mesa: Any, dev_input: dict[str, str], monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Sem o socket, nó fechado não tem porta: a lista é a da biblioteca,
        e o broker nem é procurado. É também o que mantém a suíte longe do
        `/dev/input` real dela (o conftest aponta o socket para o vazio)."""
        broker, _ = mesa
        monkeypatch.setenv("HEFESTO_BROKER_SOCKET", str(tmp_path / "nao-ha.sock"))
        assert er.discover_dualsense_touchpad_evdevs() == {}
        assert broker.pedidos == []


class TestOCartaoDoTouchpadNaoFicaCego:
    def test_o_leitor_le_o_dedo_pelo_fd_do_broker(self, mesa: Any) -> None:
        """A célula `toque.touchpad` da bancada, no nível do leitor.

        O dedo entra pelo pipe como entraria pelo nó, e o `touch_state()` —
        o que o cartão desenha — tem de mostrá-lo. A MORDIDA: faça o
        `abrir_input_device` não perguntar ao broker e o leitor fica em
        `touchpad_reader_open_failed`, com o dedo nunca chegando.
        """
        broker, _ = mesa
        from evdev import ecodes

        leitor = er.TouchpadReader(device_path=Path(NO_TOUCHPAD), acumular_movimento=False)
        assert leitor.start()
        try:
            prazo = time.monotonic() + 3.0
            while NO_TOUCHPAD not in broker.escritas and time.monotonic() < prazo:
                time.sleep(0.02)
            assert NO_TOUCHPAD in broker.escritas, "o leitor nunca pediu o fd ao broker"
            os.write(
                broker.escritas[NO_TOUCHPAD],
                _evento(ecodes.EV_ABS, ecodes.ABS_X, 1500)
                + _evento(ecodes.EV_ABS, ecodes.ABS_Y, 300)
                + _evento(ecodes.EV_KEY, ecodes.BTN_TOUCH, 1)
                + _evento(ecodes.EV_SYN, ecodes.SYN_REPORT, 0),
            )
            prazo = time.monotonic() + 3.0
            estado = leitor.touch_state()
            while not estado.touching and time.monotonic() < prazo:
                time.sleep(0.02)
                estado = leitor.touch_state()
            assert estado.touching is True
            assert (estado.x, estado.y) == (1500, 300)
        finally:
            leitor.stop()


class TestOObjetoEspelhaABiblioteca:
    def test_o_input_device_do_fd_espelha_o_da_biblioteca(self) -> None:
        """Os campos que o `__init__` da biblioteca preenche são os nossos.

        A MORDIDA é de versão: um `python-evdev` que ganhe um campo novo no
        `__init__` reprova aqui antes de o objeto montado pelo fd quebrar
        num método que o use.
        """
        from evdev import InputDevice

        da_biblioteca = set(re.findall(r"self\.(\w+)\s*=", inspect.getsource(InputDevice.__init__)))
        nossos = set(re.findall(r"dev\.(\w+)\s*=", inspect.getsource(er._input_device_do_fd)))
        assert nossos == da_biblioteca


class TestONativoPedeOsQuatro:
    def test_o_pedido_do_modo_nativo_leva_os_nos_de_entrada(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """«Só o Modo Nativo devolve.» A MORDIDA: tire o `entradas=True` do
        `_reconciliar_exposicao_do_modo_nativo` e o jogo no Nativo recebe o
        hidraw sem o evdev — quem enumera /dev/input acha zero controles."""
        from hefesto_dualsense4unix.daemon import lifecycle as mod
        import hefesto_dualsense4unix.integrations.hidraw_broker_client as cli

        pedidos: list[tuple[str, str, bool]] = []

        class Cliente:
            def expor(self, no: str, *, entradas: bool = False) -> bool:
                pedidos.append(("expor", no, entradas))
                return True

            def desexpor(self, no: str) -> bool:
                pedidos.append(("desexpor", no, False))
                return True

        class Controller:
            def nos_hidraw_por_uniq(self) -> dict[str, str]:
                return {"aabbcc000001": "/dev/hidraw3"}

        monkeypatch.setattr(cli, "broker_client_for", lambda _d: Cliente())
        monkeypatch.setattr(cli, "broker_call_nonblocking", lambda _d, chamada: chamada())
        daemon = mod.Daemon.__new__(mod.Daemon)
        daemon.controller = Controller()  # type: ignore[assignment]
        daemon._exposicao_do_modo_nativo(True)
        daemon._exposicao_do_modo_nativo(False)
        assert pedidos == [
            ("expor", "/dev/hidraw3", True),
            ("desexpor", "/dev/hidraw3", False),
        ]

    def test_o_payload_so_leva_o_campo_quando_e_verdade(self) -> None:
        """Um broker antigo ignora o campo; o `with exposicao` do handle de
        controle não o manda."""
        from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
            HidrawBrokerClient,
        )

        enviados: list[dict[str, Any]] = []

        class Cliente(HidrawBrokerClient):
            def _request(self, payload: dict[str, Any]) -> dict[str, Any] | None:
                enviados.append(dict(payload))
                return {"ok": True, "state": "exposed"}

        c = Cliente(socket_path="/nao/existe")
        c.expor("/dev/hidraw3")
        c.expor("/dev/hidraw3", entradas=True)
        with c.exposicao("/dev/hidraw3"):
            pass
        assert enviados[0] == {"cmd": "expose", "node": "/dev/hidraw3"}
        assert enviados[1] == {"cmd": "expose", "node": "/dev/hidraw3", "entradas": True}
        assert enviados[2] == {"cmd": "expose", "node": "/dev/hidraw3"}

    def test_a_reafirmacao_pergunta_aos_nos_de_entrada_tambem(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Um replug renasce os nós de entrada fechados junto com o hidraw;
        se só o hidraw fosse conferido, um nó de entrada que ficasse fechado
        nunca seria reaberto no Nativo."""
        from hefesto_dualsense4unix.daemon import lifecycle as mod
        import hefesto_dualsense4unix.integrations.hidraw_broker_client as cli

        hidraw = tmp_path / "hidraw3"
        hidraw.write_text("", encoding="ascii")
        entrada = tmp_path / "event27"
        entrada.write_text("", encoding="ascii")
        monkeypatch.setattr(cli, "nos_de_entrada_do_hidraw", lambda _no: [str(entrada)])
        assert mod.Daemon._no_de_fisico_esta_aberto(str(hidraw)) is True
        entrada.chmod(0o000)
        try:
            if os.access(entrada, os.R_OK):  # pragma: no cover - rodando como root
                pytest.skip("como root o chmod não fecha nada")
            assert mod.Daemon._no_de_fisico_esta_aberto(str(hidraw)) is False
        finally:
            entrada.chmod(0o600)


class TestOsNosDeEntradaDoHidraw:
    def test_o_mesmo_criterio_do_broker(self, tmp_path: Path) -> None:
        from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
            nos_de_entrada_do_hidraw,
        )

        hid = tmp_path / "devices" / "0005:054C:0CE6.0006"
        for pasta, nome, filhos in (
            ("input45", "DualSense Wireless Controller", ("event27", "js1")),
            ("input46", "DualSense Wireless Controller Motion Sensors", ("event28", "js2")),
            ("input47", "DualSense Wireless Controller Touchpad", ("event29",)),
        ):
            d = hid / "input" / pasta
            d.mkdir(parents=True)
            (d / "name").write_text(nome + "\n", encoding="utf-8")
            for filho in filhos:
                (d / filho).mkdir()
        classe = tmp_path / "class"
        (classe / "hidraw5").mkdir(parents=True)
        (classe / "hidraw5" / "device").symlink_to(hid)
        nos = nos_de_entrada_do_hidraw(
            "/dev/hidraw5", sys_class_hidraw=str(classe), dev_input_root="/dev/input"
        )
        assert sorted(nos) == [
            "/dev/input/event27", "/dev/input/event28", "/dev/input/event29", "/dev/input/js1",
        ]

