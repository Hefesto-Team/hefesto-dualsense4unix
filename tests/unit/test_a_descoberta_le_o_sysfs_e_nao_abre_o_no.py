"""A-DESCOBERTA-LE-O-SYSFS-E-NAO-ABRE-O-NO-01 — a descoberta não abre o nó.

O que o diário de 26/09 mediu (o `journalctl` do daemon, relido em 28/09):

- das 7h51 às 10h42, com o controle de acelerômetro desligado (perfil
  Freestyle) fora da mesa, o daemon pediu ao broker o nó de movimento dos
  OUTROS dois controles a cada 5,30 s (mediana), 1.933 vezes em cada nó. É o
  leitor de movimento do ausente — que o hub mantém vivo por causa do
  sensor desligado — repetindo a descoberta no recuo que para em 5 s;
- das 10h42 às 11h47, depois do reinício do daemon, os mesmos dois nós a cada
  1,28 s (mediana), 3.023 vezes em cada um: não havia leitor do ausente, e o
  hub repetia a descoberta a cada volta de manutenção (1 s mais a volta) para
  achar a peça com o sensor desligado. É a «rajada das 11h45» da sprint, e ela
  começou às 10h42;
- das 16h16 às 18h23, o primeiro laço de novo, 1.444 vezes num dos nós.

Cada descoberta abria cada nó auxiliar de cada controle, pelo broker, só para
ler vendor, product, nome e endereço — que o sysfs publica sem abrir nada.

As réguas, com a Mesa de mentira (quatro controles, um vpad, os nós do físico
fechados como o `0600 root` e o socket do broker de pé):

1. a descoberta devolve os quatro endereços com ZERO `open` — nem pelo
   caminho, nem pelo broker. MORDIDA: devolva o `abrir_input_device` à
   descoberta e a conta passa de zero;
2. o leitor de um endereço ausente, com o aviso de `/dev/input` parado, faz no
   máximo UMA descoberta em 30 s; com o aviso disparado, descobre na hora;
3. o hub, com o sensor desligado de uma peça fora da mesa, só procura de novo
   quando `/dev/input` muda.
"""
from __future__ import annotations

import contextlib
import errno
import os
import time
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("evdev")

from hefesto_dualsense4unix.core import evdev_reader as er
from tests.unit.sysfs_de_entrada_de_mentira import publicar_no

#: Quatro controles de mentira (a faixa forjada da casa), um em cada lugar da
#: mesa, dois no cabo e dois no rádio — nunca só o P1.
CONTROLES = (
    ("aa:bb:cc:00:00:01", 0x03),
    ("aa:bb:cc:00:00:02", 0x03),
    ("aa:bb:cc:00:00:03", 0x05),
    ("aa:bb:cc:00:00:04", 0x05),
)
NOMES = {
    "gamepad": "DualSense Wireless Controller",
    "Motion Sensors": "DualSense Wireless Controller Motion Sensors",
    "Touchpad": "DualSense Wireless Controller Touchpad",
}
#: O bitmap `capabilities/key` que o kernel publica para cada nó (o mesmo da
#: régua da HIDE-SO-O-HIDRAW-02): o do gamepad tem BTN_SOUTH..BTN_THUMBR na
#: palavra 4, o do touchpad não tem o BTN_GAMEPAD, e o de movimento é vazio.
TECLAS = {
    NOMES["gamepad"]: "7fdb000000000000 0 0 0 0",
    NOMES["Motion Sensors"]: "0",
    NOMES["Touchpad"]: "e520 10000 0 0 0 0",
}

#: O vpad do próprio daemon: os mesmos nomes, o MAC forjado `02:fe`, e a
#: morada de `/devices/virtual/misc/uhid/`. Adotá-lo seria o daemon lendo a
#: própria saída.
VPAD = "02:fe:00:00:00:01"


class Mesa:
    """A mesa de mentira: sysfs, `/dev/input` e o contador de toda abertura."""

    def __init__(self, raiz: Path) -> None:
        self.sys = raiz / "sys-class-input"
        self.dev = raiz / "dev-input"
        self.devices = raiz / "devices"
        self.sys.mkdir()
        self.dev.mkdir()
        #: `/dev/input/eventN` -> (nome, uniq, bus) — o que o nó publica.
        self.nos: dict[str, tuple[str, str, int]] = {}
        #: Morada real de cada nó, para o `_is_virtual_evdev`.
        self.moradas: dict[str, str] = {}
        #: Toda abertura, venha de onde vier.
        self.aberturas: list[str] = []
        self.pedidos_ao_broker: list[str] = []
        numero = 9101
        for uniq, bus in CONTROLES:
            for nome in NOMES.values():
                self.acrescentar(f"event{numero}", nome, uniq, bus)
                numero += 1
        for nome in NOMES.values():
            self.acrescentar(f"event{numero}", nome, VPAD, 0x05, virtual=True)
            numero += 1

    def acrescentar(
        self, evento: str, nome: str, uniq: str, bus: int, *, virtual: bool = False
    ) -> str:
        caminho = str(self.dev / evento)
        publicar_no(self.sys, caminho, nome=nome, uniq=uniq, bus=bus, teclas=TECLAS[nome])
        morada = (
            self.devices / "virtual" / "misc" / "uhid" / "0005:054C:0CE6.0099" / evento
            if virtual
            else self.devices / "pci0000:00" / evento
        )
        morada.mkdir(parents=True)
        (morada / "uniq").write_text(uniq + "\n", encoding="ascii")
        (morada / "phys").write_text("\n", encoding="ascii")
        self.moradas[f"/sys/class/input/{evento}/device"] = str(morada)
        no = Path(caminho)
        no.write_text("", encoding="ascii")
        no.chmod(0o000)  # o `0600 root` do físico, visto por ela
        self.nos[caminho] = (nome, uniq, bus)
        return caminho

    def remover(self, uniq: str) -> None:
        """O controle saiu da mesa: os três nós somem do sysfs e do `/dev`."""
        for caminho, (_nome, dono, _bus) in list(self.nos.items()):
            if dono != uniq:
                continue
            evento = Path(caminho).name
            for arquivo in sorted((self.sys / evento).rglob("*"), reverse=True):
                arquivo.unlink() if arquivo.is_file() else arquivo.rmdir()
            (self.sys / evento).rmdir()
            Path(caminho).unlink()
            del self.nos[caminho]

    def abrir(self, caminho: Any, **_kw: Any) -> Any:
        """O dublê do `abrir_input_device`: publica o que o real publica."""
        from evdev import ecodes

        self.aberturas.append(str(caminho))
        nome, uniq, bus = self.nos[str(caminho)]
        caps: dict[int, list[Any]] = {
            NOMES["gamepad"]: {
                ecodes.EV_KEY: [ecodes.BTN_SOUTH, ecodes.BTN_EAST],
                ecodes.EV_ABS: [],
            },
            NOMES["Motion Sensors"]: {ecodes.EV_ABS: []},
            NOMES["Touchpad"]: {ecodes.EV_KEY: [ecodes.BTN_LEFT, ecodes.BTN_TOUCH]},
        }[nome]
        return SimpleNamespace(
            info=SimpleNamespace(vendor=0x054C, product=0x0CE6, bustype=bus),
            name=nome,
            uniq=uniq,
            path=str(caminho),
            capabilities=lambda **_kw: caps,
            close=lambda: None,
        )


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Mesa:
    if os.geteuid() == 0:  # pragma: no cover - como root o 0000 não fecha nada
        pytest.skip("como root todo nó abre")
    m = Mesa(tmp_path)
    monkeypatch.setattr(er, "SYS_CLASS_INPUT", str(m.sys))
    monkeypatch.setattr(er, "DEV_INPUT_DIR", str(m.dev))
    socket_do_broker = tmp_path / "broker.sock"
    socket_do_broker.write_text("", encoding="ascii")
    monkeypatch.setenv("HEFESTO_BROKER_SOCKET", str(socket_do_broker))

    # O `list_devices` da BIBLIOTECA: só o nó que o processo abre. Os do
    # físico estão fechados, e só entram pelo `_nos_de_evento` com o broker.
    def listar(*_a: Any) -> list[str]:
        return [str(c) for c in sorted(m.dev.glob("event*")) if os.access(c, os.R_OK | os.W_OK)]

    monkeypatch.setattr("evdev.list_devices", listar)

    real = os.path.realpath

    def morada(caminho: Any, *a: Any, **kw: Any) -> str:
        return m.moradas.get(str(caminho)) or real(caminho, *a, **kw)

    monkeypatch.setattr("os.path.realpath", morada)

    def input_device(caminho: Any, *_a: Any, **_kw: Any) -> Any:
        m.aberturas.append(str(caminho))
        raise PermissionError(errno.EACCES, "Permission denied", str(caminho))

    def broker(caminho: str) -> int | None:
        m.pedidos_ao_broker.append(caminho)
        return None

    monkeypatch.setattr("evdev.InputDevice", input_device)
    monkeypatch.setattr(er, "_ABRIDOR_DO_BROKER", broker)
    monkeypatch.setattr(er, "abrir_input_device", m.abrir)
    return m


# ---------------------------------------------------------------------------
# 1. A descoberta lê o sysfs e não abre o nó
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("marcador", "descobre"),
    [
        ("Motion Sensors", er.discover_dualsense_motion_evdevs),
        ("Touchpad", er.discover_dualsense_touchpad_evdevs),
    ],
)
def test_a_descoberta_devolve_os_quatro_sem_abrir_nada(
    mesa: Mesa, marcador: str, descobre: Any
) -> None:
    """Os quatro endereços, cabo e rádio, e nenhum `open`.

    **A MORDIDA:** devolva o `abrir_input_device` à descoberta (o laço de
    antes de 28/09) e a conta passa de zero — doze aberturas por volta com
    quatro controles, e o broker pedido para cada nó auxiliar fechado.
    """
    achados = descobre()

    esperado = {
        uniq.replace(":", ""): Path(caminho)
        for caminho, (nome, uniq, _bus) in mesa.nos.items()
        if nome == NOMES[marcador] and uniq != VPAD
    }
    assert len(esperado) == 4
    assert achados == esperado, f"a descoberta do nó «{marcador}» não achou os quatro"
    assert mesa.aberturas == [], (
        f"a descoberta abriu {len(mesa.aberturas)} nó(s) para ler o que o sysfs "
        "já publica"
    )
    assert mesa.pedidos_ao_broker == [], "a descoberta pediu nó ao broker"


def test_o_vpad_do_daemon_fica_de_fora(mesa: Mesa) -> None:
    """Os nós do vpad têm os MESMOS nomes: quem os separa é a morada e o `02:fe`."""
    achados = er.discover_dualsense_motion_evdevs()
    assert VPAD.replace(":", "") not in achados


def test_o_no_fechado_sem_broker_fica_de_fora(
    mesa: Mesa, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Sem o socket do broker, o nó fechado não tem porta: não entra no mapa.

    A descoberta continua devolvendo só o nó que alguém pode abrir depois, como
    antes — o `_nos_de_evento` é quem decide a lista, não o sysfs.
    """
    monkeypatch.setenv("HEFESTO_BROKER_SOCKET", str(tmp_path / "nao-ha.sock"))
    assert er.discover_dualsense_motion_evdevs() == {}
    assert mesa.aberturas == []


def test_a_descoberta_do_gamepad_nao_abre_os_nos_auxiliares(mesa: Mesa) -> None:
    """A descoberta do GAMEPAD não abre nó nenhum: o touchpad e o movimento
    ficam de fora pelo sysfs, e o nó de gamepad do DualSense se classifica
    pelo sysfs também (O-NO-DO-DUALSENSE-SE-CLASSIFICA-PELO-SYSFS-01).

    **A MORDIDA:** tire o `_sysfs_tem_tecla(path, _BTN_GAMEPAD)` de antes da
    abertura e os oito nós auxiliares dos quatro controles voltam a ser
    abertos em toda volta — e o filtro de caps os descarta logo depois; abra
    o nó de gamepad na descoberta e os quatro voltam à conta.
    """
    achados = er.discover_gamepads(com_sysfs=False)
    gamepads = {
        caminho for caminho, (nome, uniq, _bus) in mesa.nos.items()
        if nome == NOMES["gamepad"] and uniq != VPAD
    }
    assert {g.evdev_path for g in achados} == gamepads
    assert mesa.aberturas == [], (
        f"a descoberta do gamepad abriu {len(mesa.aberturas)} nó(s)"
    )
    assert mesa.pedidos_ao_broker == []


def test_o_controle_que_saiu_nao_aparece(mesa: Mesa) -> None:
    mesa.remover("aa:bb:cc:00:00:02")
    achados = er.discover_dualsense_motion_evdevs()
    assert set(achados) == {"aabbcc000001", "aabbcc000003", "aabbcc000004"}
    assert mesa.aberturas == []


# ---------------------------------------------------------------------------
# 2. O leitor de um controle ausente espera o aviso, e não o relógio
# ---------------------------------------------------------------------------
#: O passo da espera nos testes. Em produção é o `_SELECT_TIMEOUT_S` (0,5 s):
#: uma volta do aviso por passo, e 60 voltas são 30 s de produção.
PASSO = 0.01
VOLTAS_EM_30_S = int(30 / 0.5)


class _NoDoLeitor:
    """O nó que o leitor abre: um pipe, para o `select` de verdade ter um fd."""

    def __init__(self, caminho: str) -> None:
        self.path = caminho
        self.r, self.w = os.pipe()
        self.fd = self.r
        self.name = "dublê"

    def read(self) -> Any:
        os.read(self.r, 64)
        raise OSError(errno.ENODEV, "No such device")  # o controle saiu

    def absinfo(self, _codigo: int) -> Any:
        raise OSError(errno.EINVAL, "sem absinfo")

    def close(self) -> None:
        for fd in (self.r, self.w):
            with contextlib.suppress(OSError):
                os.close(fd)


class _AvisoContado:
    """O `InputDirWatch` DE VERDADE, sobre o `/dev/input` de mentira, contando as voltas."""

    def __init__(self, pasta: Path) -> None:
        self.real = er.InputDirWatch(str(pasta))
        self.voltas = 0

    @property
    def nasceu(self) -> bool:
        return self.real.nasceu

    def poll(self) -> bool:
        self.voltas += 1
        return self.real.poll()


def _esperar(condicao: Callable[[], bool], prazo: float = 5.0) -> bool:
    limite = time.monotonic() + prazo
    while not condicao():
        if time.monotonic() > limite:
            return False
        time.sleep(0.005)
    return True


LEITORES = {
    "Motion Sensors": (er.MotionSensorReader, "discover_dualsense_motion_evdevs"),
    "Touchpad": (er.TouchpadReader, "discover_dualsense_touchpad_evdevs"),
}


class _Cena:
    """Um leitor aberto no nó do P4, que a régua tira e devolve à mesa."""

    AUSENTE = "aa:bb:cc:00:00:04"

    def __init__(self, mesa: Mesa, monkeypatch: pytest.MonkeyPatch, marcador: str) -> None:
        self.mesa = mesa
        self.marcador = marcador
        self.buscas: list[float] = []
        self.abertos: list[_NoDoLeitor] = []
        self.avisos: list[_AvisoContado] = []
        classe, descobridor = LEITORES[marcador]
        original = getattr(er, descobridor)

        #: O que acontece na mesa DURANTE a próxima procura (uma vez só).
        self.na_busca: Callable[[], Any] | None = None

        def contar() -> dict[str, Path]:
            self.buscas.append(time.monotonic())
            achados: dict[str, Path] = original()
            acao, self.na_busca = self.na_busca, None
            if acao is not None:
                acao()
            return achados

        def abrir(caminho: Any, **_kw: Any) -> _NoDoLeitor:
            no = _NoDoLeitor(str(caminho))
            self.abertos.append(no)
            return no

        def aviso() -> _AvisoContado:
            self.avisos.append(_AvisoContado(mesa.dev))
            return self.avisos[-1]

        monkeypatch.setattr(er, descobridor, contar)
        monkeypatch.setattr(er, "abrir_input_device", abrir)
        monkeypatch.setattr(er, "_novo_aviso_de_entrada", aviso)
        self.no = next(
            c for c, (n, u, _b) in mesa.nos.items()
            if u == self.AUSENTE and n == NOMES[marcador]
        )
        self.leitor = classe(device_path=Path(self.no), target_uniq=self.AUSENTE.replace(":", ""))
        self.leitor._SELECT_TIMEOUT_S = PASSO  # type: ignore[misc]

    def abrir_e_perder(self) -> None:
        """Abre o nó, e o controle sai da mesa: os nós somem e a leitura cai."""
        assert self.leitor.start()
        assert _esperar(lambda: len(self.abertos) == 1), "o leitor nem abriu o nó"
        self.mesa.remover(self.AUSENTE)
        os.write(self.abertos[0].w, b"x")
        assert _esperar(lambda: len(self.buscas) >= 1), "o leitor não procurou o nó"

    def devolver(self, *, fechado: bool = True) -> str:
        """O controle volta: o kernel recria o nó, e a pasta muda."""
        caminho = self.mesa.acrescentar(
            "event9201", NOMES[self.marcador], self.AUSENTE, 0x05
        )
        if not fechado:
            Path(caminho).chmod(0o660)
        return caminho

    def parar(self) -> None:
        self.leitor.stop()
        for no in self.abertos:
            no.close()


@pytest.fixture(params=sorted(LEITORES))
def cena(mesa: Mesa, monkeypatch: pytest.MonkeyPatch, request: Any) -> Any:
    c = _Cena(mesa, monkeypatch, request.param)
    try:
        yield c
    finally:
        c.parar()


def test_sem_aviso_o_leitor_procura_uma_vez_em_30_s(cena: _Cena) -> None:
    """Com `/dev/input` parado, UMA descoberta em 30 s (60 passos de 0,5 s).

    **A MORDIDA:** troque o `_esperar_o_no(self)` do `_run` pelo recuo de
    antes (`_esperar_o_backoff(self, backoff)` e o `backoff` que dobra) e o
    leitor procura de novo a cada volta — 0,5, 1, 2, 4 e 5 s para sempre.
    """
    cena.abrir_e_perder()

    def trinta_segundos_ou_outra_busca() -> bool:
        voltas = cena.avisos[-1].voltas if cena.avisos else 0
        return voltas >= 1 + VOLTAS_EM_30_S or len(cena.buscas) > 1

    assert _esperar(trinta_segundos_ou_outra_busca, prazo=20.0)
    assert len(cena.buscas) == 1, (
        f"{len(cena.buscas)} descobertas em 30 s com o controle fora da mesa "
        "e `/dev/input` parado"
    )


def test_com_o_aviso_o_leitor_descobre_e_abre_na_hora(cena: _Cena) -> None:
    """O controle volta e a pasta muda: a descoberta é na volta seguinte."""
    cena.abrir_e_perder()
    assert _esperar(lambda: bool(cena.avisos)), "o leitor não armou o aviso"
    aviso = cena.avisos[-1]
    voltas = aviso.voltas
    caminho = cena.devolver()
    assert _esperar(lambda: len(cena.abertos) == 2, prazo=5.0), "o leitor não reabriu"
    assert cena.abertos[1].path == caminho
    assert len(cena.buscas) == 2
    assert aviso.voltas - voltas <= 3, (
        f"o leitor levou {aviso.voltas - voltas} voltas para ver o nó que voltou"
    )


def test_o_no_que_nasce_durante_a_procura_acorda_o_leitor(cena: _Cena) -> None:
    """O nó que nasce no meio da procura não pode sumir dentro da linha de base.

    O `_procurar_o_no` tira a linha de base do aviso ANTES do `_find_device`:
    o nó que nasce depois de a descoberta ler o sysfs muda a pasta depois da
    linha de base, e a primeira volta da espera o enxerga.

    **A MORDIDA:** tire a linha de base DEPOIS da procura e o nó que nasceu no
    meio dela entra na linha de base: o leitor dorme até o teto de 60 s com o
    nó do controle na pasta.
    """
    cena.na_busca = cena.devolver
    cena.abrir_e_perder()
    assert _esperar(lambda: len(cena.abertos) == 2, prazo=5.0), (
        "o nó nasceu durante a procura e o leitor não acordou: o aviso se perdeu"
    )
    assert cena.abertos[1].path == str(cena.mesa.dev / "event9201")


def test_o_controle_que_sai_nao_faz_o_ausente_procurar(cena: _Cena) -> None:
    """A pasta que só perde entradas não traz nó nenhum de volta.

    Outro controle sai da mesa (o P2): `/dev/input` muda, e o leitor do
    ausente segue dormindo. **A MORDIDA:** troque o `aviso.poll() and
    getattr(aviso, "nasceu", True)` por `aviso.poll()` e cada saída vira uma
    descoberta — mais as três no relógio.
    """
    cena.abrir_e_perder()
    assert _esperar(lambda: bool(cena.avisos)), "o leitor não armou o aviso"
    aviso = cena.avisos[-1]
    cena.mesa.remover("aa:bb:cc:00:00:02")
    voltas = aviso.voltas
    assert _esperar(lambda: aviso.voltas >= voltas + 10, prazo=5.0)
    assert len(cena.buscas) == 1, "a saída de outro controle fez o ausente procurar"


def test_o_no_que_nasce_sem_permissao_e_achado_no_relogio(
    cena: _Cena, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Sem broker, o nó nasce fechado e o udev o abre DEPOIS, sem mudar a pasta.

    É o que o recuo no relógio cobria antes e o aviso sozinho não cobre: a
    troca de dono e permissão não muda a lista de `/dev/input`. Depois de cada
    aviso, o leitor procura mais três vezes no relógio (0,5 → 1 → 2 s).

    **A MORDIDA:** ponha `_BUSCAS_DEPOIS_DO_AVISO = 0` e o leitor dorme até o
    teto de 60 s com o nó já aberto na pasta.
    """
    monkeypatch.setenv("HEFESTO_BROKER_SOCKET", str(tmp_path / "nao-ha.sock"))
    cena.abrir_e_perder()
    caminho = cena.devolver()  # nasce 0000: sem broker, a lista não o traz
    assert _esperar(lambda: len(cena.buscas) >= 2, prazo=5.0), "o aviso não chegou"
    assert len(cena.abertos) == 1
    Path(caminho).chmod(0o660)  # o udev deu dono e permissão
    assert _esperar(lambda: len(cena.abertos) == 2, prazo=5.0), (
        "o nó ficou aberto na pasta e o leitor não o achou — ele esperava um "
        "aviso que a troca de permissão não dá"
    )


def test_o_teto_acorda_o_leitor_sem_aviso(cena: _Cena) -> None:
    """O teto é de segurança: um aviso perdido custa no máximo ele."""
    cena.leitor._TETO_SEM_AVISO_S = 20 * PASSO  # type: ignore[misc]
    cena.abrir_e_perder()
    assert _esperar(lambda: len(cena.buscas) >= 2, prazo=5.0), "o teto não acordou o leitor"


def test_o_stop_acorda_o_leitor_que_espera(cena: _Cena) -> None:
    cena.leitor._SELECT_TIMEOUT_S = 5.0  # type: ignore[misc]
    cena.abrir_e_perder()
    inicio = time.monotonic()
    cena.leitor.stop()
    assert time.monotonic() - inicio < 1.0, "o stop esperou o passo inteiro"


# ---------------------------------------------------------------------------
# 3. O hub não procura de novo a peça desligada que não está na mesa
# ---------------------------------------------------------------------------
class _AvisoDoHub:
    def __init__(self) -> None:
        self.mudou = False

    def poll(self) -> bool:
        mudou, self.mudou = self.mudou, False
        return mudou


@pytest.fixture
def registro() -> Any:
    from hefesto_dualsense4unix.core.virtual_motion import REGISTRO

    REGISTRO.limpar()
    yield REGISTRO
    REGISTRO.limpar()


def _hub(descobrir: Callable[[], dict[str, Any]]) -> Any:
    from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub

    class _Leitor:
        grab_state = "off"

        def start(self) -> bool:
            return True

        def stop(self) -> None:
            pass

        def set_grab(self, grab: bool) -> bool:
            self.grab_state = "held" if grab else "off"
            return True

    hub = SensorHub(
        motion_factory=lambda _u, _n: _Leitor(),
        touch_factory=lambda _u, _n: _Leitor(),
        gamepad_factory=lambda _u, _n: _Leitor(),
        descobrir_motion=descobrir,
        descobrir_touch=dict,
        descobrir_gamepad=dict,
        auto_manutencao=False,
    )
    hub._watch = _AvisoDoHub()
    return hub


def test_o_hub_procura_a_peca_desligada_fora_da_mesa_uma_vez(registro: Any) -> None:
    """A «rajada» de 26/09: uma descoberta por volta de manutenção, das 10h42 às 11h47.

    **A MORDIDA:** tire o `not faltando <= self._desligados_procurados` e as
    dez voltas pagam dez descobertas.
    """
    chamadas: list[int] = []

    def descobrir() -> dict[str, Any]:
        chamadas.append(1)
        return {"aa:bb:cc:00:00:01": "/dev/input/event9102"}

    hub = _hub(descobrir)
    registro.definir("aa:bb:cc:00:00:04", acelerometro=False)
    for _ in range(10):
        hub.reconciliar()
    assert len(chamadas) == 1, f"{len(chamadas)} descobertas em dez voltas sem mudança"


def test_o_hub_procura_de_novo_quando_a_pasta_muda_e_acha(registro: Any) -> None:
    mesa_viva: dict[str, Any] = {"aa:bb:cc:00:00:01": "/dev/input/event9102"}
    chamadas: list[int] = []

    def descobrir() -> dict[str, Any]:
        chamadas.append(1)
        return dict(mesa_viva)

    hub = _hub(descobrir)
    registro.definir("aa:bb:cc:00:00:04", acelerometro=False)
    hub.reconciliar()
    hub.reconciliar()
    assert len(chamadas) == 1

    mesa_viva["aa:bb:cc:00:00:04"] = "/dev/input/event9111"  # o controle voltou
    hub._watch.mudou = True
    hub.reconciliar()

    assert hub.grab_do_movimento("aa:bb:cc:00:00:04") == "held", (
        "a peça voltou com o sensor desligado e o nó dela não ficou exclusivo"
    )


def test_o_hub_procura_de_novo_na_volta_seguinte_a_mudanca(registro: Any) -> None:
    """O nó nasce antes da permissão, e a troca de permissão não muda a pasta.

    Sem broker, a lista da descoberta só traz o nó que o processo abre, e o
    udev dá dono e permissão DEPOIS de o nó nascer. A volta da mudança procura,
    e a volta seguinte, sem mudança, procura mais uma vez: só então a peça vira
    «procurada». É o que as três buscas no relógio fazem no leitor.

    **A MORDIDA:** marque a peça como procurada já na volta da mudança e o nó
    que ganhou permissão uma volta depois nunca é achado.
    """
    mesa_viva: dict[str, Any] = {}
    hub = _hub(lambda: dict(mesa_viva))
    registro.definir("aa:bb:cc:00:00:04", acelerometro=False)
    hub.reconciliar()
    hub._watch.mudou = True  # o controle voltou: o nó nasceu, ainda fechado
    hub.reconciliar()
    mesa_viva["aa:bb:cc:00:00:04"] = "/dev/input/event9111"  # o udev o abriu
    hub.reconciliar()

    assert hub.grab_do_movimento("aa:bb:cc:00:00:04") == "held", (
        "o nó ganhou permissão uma volta depois de nascer e o hub não o procurou "
        "de novo: o sensor desligado continua chegando a quem lê o nó"
    )


def test_o_hub_procura_a_peca_que_ela_acabou_de_desligar(registro: Any) -> None:
    """Sensor desligado AGORA é pergunta nova, mesmo sem a pasta mudar."""
    chamadas: list[int] = []

    def descobrir() -> dict[str, Any]:
        chamadas.append(1)
        return {}

    hub = _hub(descobrir)
    registro.definir("aa:bb:cc:00:00:04", acelerometro=False)
    hub.reconciliar()
    registro.definir("aa:bb:cc:00:00:03", giroscopio=False)
    hub.reconciliar()
    assert len(chamadas) == 2
