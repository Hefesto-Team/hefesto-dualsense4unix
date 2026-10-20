"""OS-ACIONADORES-USB-ENTRAM-COMO-BOTOES-DO-CONTROLE-01 — a tecla do acionador sai no pad.

Um aparelho de entrada qualquer (acionador adaptado, pedal, teclado no lugar deles), declarado no
``maquina.json`` como fonte de botões de um controle, tem cada tecla somada aos botões que a mão
aperta naquele controle. A mesa tem quatro controles no backend do produto (dois no cabo, dois no
rádio), o P1 no ``dispatch_gamepad`` e o P2 a P4 no ``forward_all`` do co-op, nas máscaras DualSense
e Xbox; o que se lê é o ``EV_KEY`` e o ``ABS_Z`` que o jogo veria em cada pad virtual.

A tela (a linha do aparelho de entrada e a janela «Usar como botões de», desenho r3-08-14): a linha
leva o botão, a janela diz as teclas e o controle pelo plástico, a tecla nova chega numa thread, o
clique no desenho escolhe o botão e o «Guardar» declara pelo ``machine.declare`` que já existe.

A régua nunca abre o ``/dev/input`` nem o ``/sys`` da máquina: o ``/sys/class/input`` é uma pasta
de mentira e o aparelho, um evdev de mentira; a ponte para no fim de cada caso.
"""
from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from evdev import ecodes
from pydualsense.enums import ConnectionType
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer
from hefesto_dualsense4unix.integrations.uinput_gamepad import (
    BOTOES_POR_FLAVOR,
    BUTTON_TO_UINPUT,
    UinputGamepad,
)
from hefesto_dualsense4unix.utils.maquina import (
    MaquinaConfig,
    chave_do_acionador,
    fundir_declaracao,
)

MACS = tuple(f"AA:BB:CC:00:00:0{n}" for n in range(1, 5))
UNIQS = tuple(m.replace(":", "").lower() for m in MACS)
TRANSPORTES = (ConnectionType.USB, ConnectionType.BT, ConnectionType.USB, ConnectionType.BT)
MASCARAS = ("dualsense", "xbox")

NOME = "Acionador de mentira"
FISICO = "usb-0000:00:14.0-9/input0"
VENDOR, PRODUCT = "1234", "abcd"
CHAVE = chave_do_acionador(VENDOR, PRODUCT, NOME, FISICO)
TECLA_1 = ecodes.KEY_ENTER
PEDAL = ecodes.KEY_SPACE


def _handle(transporte: ConnectionType) -> Any:
    inst = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    inst.leftMotor = 0
    inst.rightMotor = 0
    inst.light = DSLight()
    inst.audio = DSAudio()
    inst.triggerL = DSTrigger()
    inst.triggerR = DSTrigger()
    inst.conType = transporte
    inst._suppress_leds = True
    inst._rumble_active = False
    inst._rumble_stop_pending = False
    inst._bt_seq = 0
    inst._raw_trigger_right = None
    inst._raw_trigger_left = None
    inst.connected = True
    return inst


class _No:
    """O nó do uinput de mentira: as teclas que o jogo leria e o último ``ABS_Z`` (o L2)."""

    def __init__(self) -> None:
        self.teclas: set[int] = set()
        self.l2: int | None = None

    def write(self, tipo: int, codigo: int, valor: int) -> None:
        if tipo == ecodes.EV_KEY:
            (self.teclas.add if valor else self.teclas.discard)(codigo)
        elif tipo == ecodes.EV_ABS and codigo == ecodes.ABS_Z:
            self.l2 = valor

    def syn(self) -> None:
        pass


def _botao_do_pad(pad: UinputGamepad, nome: str) -> str:
    """O nome evdev do botão ``nome`` no pad, pela tabela da máscara que o jogo vê."""
    return str(BOTOES_POR_FLAVOR.get(pad.mascara_no_jogo, BUTTON_TO_UINPUT)[nome])


def _pad(mascara: str) -> tuple[UinputGamepad, _No]:
    no = _No()
    pad = UinputGamepad(flavor=mascara)
    pad._device = no
    pad._ecodes = ecodes
    return pad, no


class _Leitor:
    grab_state = "held"

    def snapshot(self) -> Any:
        return SimpleNamespace(lx=128, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0,
                               buttons_pressed=frozenset())


class _Acionador:
    """O evdev de mentira do acionador: a fila de eventos, o ``fd`` que o ``select`` vigia (um
    pipe, legível enquanto a fila tem evento), o grab e o fechar."""

    def __init__(self) -> None:
        self.fila: list[Any] = []
        self.preso = False
        self.fechado = False
        self.saiu = False
        self.fd, self._escreve = os.pipe()

    def apertar(self, codigo: int, valor: int = 1) -> None:
        self.fila.append(SimpleNamespace(type=ecodes.EV_KEY, code=codigo, value=valor))
        os.write(self._escreve, b"!")

    def read_one(self) -> Any:
        if self.saiu:
            raise OSError(19, "No such device")
        if not self.fila:
            return None
        os.read(self.fd, 1)
        return self.fila.pop(0)

    def grab(self) -> None:
        self.preso = True

    def ungrab(self) -> None:
        self.preso = False

    def close(self) -> None:
        self.fechado = True
        for fd in (self.fd, self._escreve):
            with contextlib.suppress(OSError):
                os.close(fd)


def _sys_de_mentira(raiz: Path) -> Path:
    """Um ``/sys/class/input`` com o teclado da casa e o acionador (só o acionador é declarado)."""
    for evento, nome, fisico, vendor, product in (
            ("event3", "Teclado da casa", "usb-0000:00:14.0-1/input0", "046d", "c31c"),
            ("event7", NOME, FISICO, VENDOR, PRODUCT)):
        dentro = raiz / evento / "device"
        (dentro / "id").mkdir(parents=True)
        (dentro / "name").write_text(nome + "\n")
        (dentro / "phys").write_text(fisico + "\n")
        (dentro / "id" / "vendor").write_text(vendor + "\n")
        (dentro / "id" / "product").write_text(product + "\n")
    return raiz


class _Mesa:
    """Quatro pads, a ponte com o ``/sys`` de mentira e o acionador declarado para ``controle``."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mascara: str,
                 controle: str | None, teclas: dict[str, str] | None = None) -> None:
        monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
        monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
        reader = EvdevReader(device_path=None)
        reader._device_path = None
        backend = bp.PyDualSenseController(evdev_reader=reader)
        backend._handles = {mac: _handle(t) for mac, t in zip(MACS, TRANSPORTES, strict=True)}
        backend._primary_key = MACS[0]
        pads = [_pad(mascara) for _ in UNIQS]
        self.pads = [pad for pad, _ in pads]
        self.nos = [no for _, no in pads]
        self.acionador = _Acionador()
        self.abertos: list[str] = []
        self.em_jogo = False
        self.agora = 0.0

        def abrir(evento: str) -> Any:
            self.abertos.append(evento)
            return self.acionador

        self.ponte = gp.PonteDosAcionadores(
            raiz=_sys_de_mentira(tmp_path / "input"), abrir=abrir, relogio=lambda: self.agora)
        declarado = {} if controle is None else {CHAVE: {
            "nome": NOME, "controle": controle,
            "teclas": teclas if teclas is not None else {str(TECLA_1): "cross",
                                                         str(PEDAL): "l2"}}}
        self.daemon = SimpleNamespace(
            store=StateStore(),
            controller=SimpleNamespace(primary_uniq=UNIQS[0]),
            config=SimpleNamespace(coop_enabled=True, gamepad_flavor=mascara),
            identity_registry=None,
            _gamepad_device=self.pads[0],
            _coop_manager=None,
            _hotkey_manager=None,
            _maquina=MaquinaConfig.model_validate({"acionadores": declarado}),
            _ponte_dos_acionadores=self.ponte,
            _janela_de_jogo_em_foco=lambda: self.em_jogo,
        )
        self.coop = CoopManager(self.daemon)
        for n, uniq in enumerate(UNIQS[1:], 2):
            self.coop._players[uniq] = _SecondaryPlayer(
                identity=uniq, evdev_path=f"/dev/input/event{n + 10}",
                reader=cast(Any, _Leitor()), player_index=n, vpad=self.pads[n - 1])

    def tique(self) -> None:
        estado = SimpleNamespace(raw_lx=128, raw_ly=128, raw_rx=128, raw_ry=128,
                                 l2_raw=0, r2_raw=0)
        gp.dispatch_gamepad(self.daemon, estado, frozenset())
        self.coop.forward_all()

    def com_a_cruz(self) -> list[bool]:
        """Em quais dos quatro pads o jogo vê a Cruz apertada."""
        cruz = [cast(int, getattr(ecodes, _botao_do_pad(pad, "cross"))) for pad in self.pads]
        return [c in no.teclas for c, no in zip(cruz, self.nos, strict=True)]





@pytest.fixture
def mesas() -> Any:
    criadas: list[_Mesa] = []
    yield criadas
    for mesa in criadas:
        mesa.ponte.parar()


@pytest.mark.parametrize("mascara", MASCARAS)
@pytest.mark.parametrize("jogador", range(4))
def test_a_tecla_do_acionador_sai_como_o_botao_escolhido_no_pad_daquele_controle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mesas: list[_Mesa], mascara: str,
    jogador: int,
) -> None:
    mesa = _Mesa(monkeypatch, tmp_path, mascara, UNIQS[jogador])
    mesas.append(mesa)
    mesa.tique()
    assert mesa.abertos == ["event7"], "a ponte abre só o aparelho declarado, achado pelo /sys"
    assert mesa.com_a_cruz() == [False] * 4

    mesa.acionador.apertar(TECLA_1)
    mesa.tique()
    esperado = [n == jogador for n in range(4)]
    assert mesa.com_a_cruz() == esperado

    mesa.acionador.apertar(TECLA_1, 2)  # a repetição do teclado não solta nada
    mesa.tique()
    assert mesa.com_a_cruz() == esperado

    mesa.acionador.apertar(TECLA_1, 0)
    mesa.tique()
    assert mesa.com_a_cruz() == [False] * 4


@pytest.mark.parametrize("mascara", MASCARAS)
@pytest.mark.parametrize("jogador", range(4))
def test_o_pedal_no_l2_aperta_o_gatilho_inteiro(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mesas: list[_Mesa], mascara: str,
    jogador: int,
) -> None:
    mesa = _Mesa(monkeypatch, tmp_path, mascara, UNIQS[jogador])
    mesas.append(mesa)
    mesa.acionador.apertar(PEDAL)
    mesa.tique()
    assert [no.l2 for no in mesa.nos] == [255 if n == jogador else 0 for n in range(4)]
    mesa.acionador.apertar(PEDAL, 0)
    mesa.tique()
    assert [no.l2 for no in mesa.nos] == [0, 0, 0, 0]


def test_sem_o_mapeamento_a_tecla_nao_chega_a_pad_nenhum(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mesas: list[_Mesa],
) -> None:
    """A mordida da declaração: sem acionador declarado, nada abre e nada chega."""
    mesa = _Mesa(monkeypatch, tmp_path, "dualsense", None)
    mesas.append(mesa)
    mesa.acionador.apertar(TECLA_1)
    mesa.tique()
    assert mesa.abertos == []
    assert mesa.com_a_cruz() == [False] * 4


def test_a_tecla_sem_botao_escolhido_nao_vira_botao(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mesas: list[_Mesa],
) -> None:
    mesa = _Mesa(monkeypatch, tmp_path, "dualsense", UNIQS[0], {str(PEDAL): "circle"})
    mesas.append(mesa)
    mesa.acionador.apertar(TECLA_1)
    mesa.tique()
    assert mesa.com_a_cruz() == [False] * 4


def test_fora_do_jogo_o_aparelho_e_do_sistema_e_no_jogo_fica_preso(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mesas: list[_Mesa],
) -> None:
    mesa = _Mesa(monkeypatch, tmp_path, "dualsense", UNIQS[0])
    mesas.append(mesa)
    mesa.tique()
    assert not mesa.acionador.preso
    mesa.em_jogo, mesa.agora = True, gp.OLHAR_O_FOCO_A_CADA_S
    mesa.tique()
    assert mesa.acionador.preso
    mesa.em_jogo, mesa.agora = False, 2 * gp.OLHAR_O_FOCO_A_CADA_S
    mesa.tique()
    assert not mesa.acionador.preso
    mesa.em_jogo, mesa.agora = True, 3 * gp.OLHAR_O_FOCO_A_CADA_S
    mesa.tique()
    assert mesa.acionador.preso
    # O modo que sai do pad virtual devolve o aparelho ao sistema (o resto da parada fica mudo).
    from hefesto_dualsense4unix.daemon.subsystems import rumble

    for nome in ("_largar_o_p1_que_nasce", "stop_motion_reader", "soltar_a_ativacao",
                 "_materialize_launch_env"):
        monkeypatch.setattr(gp, nome, lambda d: None)
    monkeypatch.setattr(rumble, "zero_motors_on_mode_exit", lambda d: None)
    mesa.daemon._gamepad_device = None
    gp.stop_gamepad_emulation(cast(Any, mesa.daemon), persist=False, release_grab=False)
    assert not mesa.acionador.preso and mesa.acionador.fechado


def test_o_aparelho_que_sai_da_porta_solta_a_tecla_e_volta_quando_volta(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mesas: list[_Mesa],
) -> None:
    mesa = _Mesa(monkeypatch, tmp_path, "dualsense", UNIQS[0])
    mesas.append(mesa)
    mesa.acionador.apertar(TECLA_1)
    mesa.tique()
    assert mesa.com_a_cruz()[0]
    mesa.acionador.saiu = True
    mesa.tique()
    assert mesa.com_a_cruz() == [False] * 4
    mesa.acionador.saiu = False
    mesa.agora = gp.PROCURAR_O_ACIONADOR_A_CADA_S
    mesa.tique()
    assert mesa.abertos == ["event7", "event7"]


def test_a_declaracao_que_esquece_o_acionador_fecha_o_aparelho(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mesas: list[_Mesa],
) -> None:
    mesa = _Mesa(monkeypatch, tmp_path, "dualsense", UNIQS[0])
    mesas.append(mesa)
    mesa.tique()
    bruto = fundir_declaracao(mesa.daemon._maquina.model_dump(), {"acionadores": {CHAVE: None}})
    mesa.daemon._maquina = MaquinaConfig.model_validate(bruto)
    mesa.tique()
    assert mesa.acionador.fechado


def test_daemon_sem_declaracao_nao_cria_ponte_nem_le_o_sys() -> None:
    """Custo zero sem acionador, e um ``_maquina`` de dublê qualquer não liga a ponte."""
    for maquina in (None, MaquinaConfig(), SimpleNamespace(acionadores=object())):
        daemon = SimpleNamespace(_maquina=maquina)
        gp.andar_os_acionadores(daemon)
        assert gp.ponte_dos_acionadores(daemon) is None
        assert not hasattr(daemon, "_ponte_dos_acionadores")


def test_o_maquina_json_guarda_o_acionador_pela_chave_sem_endereco() -> None:
    assert CHAVE.startswith(f"{VENDOR}:{PRODUCT}:") and len(CHAVE) == 18
    assert FISICO not in CHAVE
    doc = MaquinaConfig.model_validate({"acionadores": {CHAVE: {
        "controle": UNIQS[2], "teclas": {"28": "cross", "57": "l2"}}}})
    assert doc.acionadores[CHAVE].teclas == {"28": "cross", "57": "l2"}
    junto = fundir_declaracao(doc.model_dump(), {"acionadores": {CHAVE: {"teclas": {"57": None}}}})
    assert MaquinaConfig.model_validate(junto).acionadores[CHAVE].teclas == {"28": "cross"}
    ruins: tuple[dict[str, Any], ...] = (
        {"x": {}}, {CHAVE: {"teclas": {"28": "ps"}}},
        {CHAVE: {"teclas": {"tecla": "cross"}}}, {CHAVE: {"controle": "02bbcc0000ff"}})
    for ruim in ruins:
        with pytest.raises(ValueError):
            MaquinaConfig.model_validate({"acionadores": ruim})
    assert json.loads(doc.model_dump_json())["acionadores"][CHAVE]["controle"] == UNIQS[2]


# --- a tela: a linha, a janela e os gestos (desenho r3-08-14) ----------------------------------

RAIZ = Path(__file__).resolve().parents[2]
BANCADA = RAIZ / "mockup" / "08-conexoes.html"
DESENHO = RAIZ / "docs/research/2026-10-12-a-volta/paginas/todo-das-abas/todo/08-conexoes.html"
LUGAR = "AA:BB:CC:00:00:F0"
PLASTICOS = ("Cosmic Red", "Starlight Blue", "White", "Galactic Purple")
COLORWAYS = ("cosmic-red", "starlight-blue", "white", "galactic-purple")


@pytest.fixture
def a08() -> Any:
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes.a08_conexoes`, que carrega o GTK")
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    a08_conexoes._RASCUNHO = None
    yield a08_conexoes
    a08_conexoes._RASCUNHO = None


class _Ponte:
    """A ponte do produto, com o ``machine_declare`` gravando no ``maquina.json`` do teste."""

    def __init__(self) -> None:
        self.chamadas: list[dict[str, Any]] = []

    def machine_declare(self, declaracao: dict[str, Any]) -> tuple[bool, str | None]:
        from hefesto_dualsense4unix.utils import maquina

        self.chamadas.append(declaracao)
        maquina.gravar_maquina_com_descartes(declaracao)
        return True, None


def _declarado(teclas: dict[str, str] | None = None) -> MaquinaConfig:
    return MaquinaConfig.model_validate({"acionadores": {CHAVE: {
        "controle": UNIQS[1], "teclas": teclas or {str(TECLA_1): "cross", str(PEDAL): "l2"}}}})


def _cena(a08: Any, monkeypatch: pytest.MonkeyPatch, declaracao: MaquinaConfig) -> dict[str, Any]:
    """A cena viva do acionador declarado, com os quatro controles da mesa pelo plástico."""
    ctx = SimpleNamespace(mesa=[{"uniq": MACS[i], "nome": PLASTICOS[i], "cor": COLORWAYS[i]}
                                for i in range(4)])
    cena = {"aparelhos": a08._os_acionadores_declarados(declaracao, [{"id": LUGAR}]),
            "lugares": [{"id": LUGAR}],
            "quem_recebe": a08._quem_recebe_da_mesa(ctx, declaracao),
            "colorway_de": a08._colorways_da_mesa(ctx)}
    monkeypatch.setattr(a08, "_CENA_NA_TELA", cena)
    monkeypatch.setattr(a08, "_declaracao", lambda: declaracao)
    return cena


def test_a_linha_do_aparelho_de_entrada_leva_o_usar_como_botoes_do_desenho(a08: Any) -> None:
    """A linha A1 que o gerador pinta é a do desenho aprovado, byte a byte; o «⋮» e o arrastar
    ficam de fora (o aparelho só ocupa a porta), como na webcam."""
    def linha(texto: str) -> str:
        i = texto.index('data-id="A1"')
        return texto[texto.rfind("<div", 0, i):texto.index('</div><div class="linha', i) + 6]

    assert linha(BANCADA.read_text()) == linha(DESENHO.read_text())
    ap = {"id": CHAVE, "chave": CHAVE, "tipo": "entrada", "lugar": LUGAR, "nome": "",
          "rotulo": "Acionador USB", "fixo": True, "esperando": False}
    html = a08.html_da_linha(ap, {"aparelhos": [ap], "lugares": [{"id": LUGAR}]})
    assert 'data-r3="14"' in html and 'data-gesto="usar-como-botoes"' in html
    assert 'href="#acionador"' in html and "Usar como botões de…" in html
    assert "menu-da-linha" not in html and 'class="linha" draggable' not in html


def test_a_janela_diz_as_teclas_o_plastico_e_acende_os_botoes_escolhidos(
        a08: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    cena = _cena(a08, monkeypatch, _declarado())
    campos = a08.campos_do_acionador(cena)
    assert campos["acionador-titulo"] == "Acionador USB · usar como botões de"
    assert [o for o in PLASTICOS if f">{o}</option>" in campos["acionador-quem"]] == list(PLASTICOS)
    assert f'value="{UNIQS[1]}" selected>Starlight Blue' in campos["acionador-quem"]
    assert "P1" not in campos["acionador-quem"] and "P2" not in campos["acionador-quem"]
    assert ">Tecla 1<" in campos["acionador-teclas"] and ">Cruz<" in campos["acionador-teclas"]
    assert ">Tecla 2<" in campos["acionador-teclas"] and ">L2<" in campos["acionador-teclas"]
    assert campos["acionador-brilho"].startswith("#acionador #ac-cross,#acionador #ac-l2{")
    # o desenho veste o plástico do controle escolhido (o Starlight Blue), pelo endereço da cor
    assert campos["acionador-desenho"] == "starlight-blue"
    janela = BANCADA.read_text().split('id="acionador">', 1)[1].split('<div class="tela-nova"')[0]
    for campo in campos:
        assert f'data-campo="{campo}"' in janela


def test_o_desenho_da_janela_e_o_dualsense_real_e_cada_botao_que_troca_e_um_gesto(a08: Any) -> None:
    import re

    janela = BANCADA.read_text().split('id="acionador">', 1)[1].split('<div class="tela-nova"')[0]
    svg = re.search(r'<svg class="ac-svg".*?</svg>', janela, re.S)
    assert svg is not None
    pecas = set(re.findall(r'data-entrada="([^"]+)" data-gesto="acionador-botao" '
                           r'data-hef-forma="acionador"', svg.group(0)))
    assert pecas == {p for p, _, _ in a08._botoes_do_desenho()}
    assert {"ps", "mic", "touchpad"}.isdisjoint(pecas)
    desenho = re.search(r'<svg class="ac-svg".*?</svg>', DESENHO.read_text(), re.S)
    assert desenho is not None
    # A janela usa a tabela e a folha das cores da página (uma só) e endereça o `data-colorway`.
    endereco = (' data-campo="acionador-desenho" data-hef-alvo="atributo" '
                'data-hef-atributo="data-colorway"')
    assert endereco in svg.group(0) and "cores-do-dualsense" not in svg.group(0)
    do_desenho = re.sub(r'<defs id="ac-cores-do-dualsense">.*?</defs>', "", desenho.group(0),
                        flags=re.S)
    do_desenho = re.sub(r"#ac-(hachura-sem-hex|casca-[a-z0-9-]+)\b", r"#\1", do_desenho)
    sem_estilo = [re.sub(r"\s+", "", re.sub(r"<style.*?</style>", "", s, flags=re.S))
                  for s in (svg.group(0).replace(' data-gesto="acionador-botao" '
                                                  'data-hef-forma="acionador"', "")
                            .replace(endereco, ""),
                            do_desenho)]
    assert sem_estilo[0] == sem_estilo[1]


def test_o_clique_no_desenho_escolhe_o_botao_e_o_guardar_declara_pela_chave(
        a08: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.utils import maquina

    _cena(a08, monkeypatch, _declarado())
    monkeypatch.setattr(a08, "_reler_a_declaracao", lambda: None)
    ponte = _Ponte()
    assert a08.usar_como_botoes(None, {"alvo": CHAVE}, ponte) == {"armou": True}
    a08.acionador_botao(None, {"entrada": "circle", "forma": {"tecla": str(TECLA_1),
                                                               "acionador-quem": UNIQS[3]}}, ponte)
    a08.acionador_botao(None, {"entrada": "stick_r", "forma": {"tecla": str(PEDAL)}}, ponte)
    with pytest.raises(ValueError):
        a08.acionador_botao(None, {"entrada": "ps", "forma": {"tecla": str(PEDAL)}}, ponte)
    assert ponte.chamadas == []
    a08.acionador_guardar(None, {"forma": {"acionador-quem": UNIQS[3]}}, ponte)
    assert ponte.chamadas == [{"acionadores": {CHAVE: {
        "nome": None, "controle": UNIQS[3],
        "teclas": {str(TECLA_1): "circle", str(PEDAL): "r3"}}}}]
    gravado = maquina.carregar_maquina().acionadores[CHAVE]
    assert (gravado.controle, gravado.teclas) == (UNIQS[3], {str(TECLA_1): "circle",
                                                               str(PEDAL): "r3"})
    assert a08._RASCUNHO is None


def test_a_tecla_nova_chega_numa_thread_e_o_aparelho_nunca_fica_preso(
        a08: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import time

    _cena(a08, monkeypatch, _declarado({str(TECLA_1): "cross"}))
    monkeypatch.setattr(a08, "_RAIZ_DAS_ENTRADAS", str(_sys_de_mentira(tmp_path / "input")))
    acionador = _Acionador()
    abertos: list[str] = []

    def abrir(evento: str) -> _Acionador:
        abertos.append(evento)
        acionador.apertar(PEDAL, 0)
        acionador.apertar(PEDAL, 1)
        return acionador

    monkeypatch.setattr(a08, "_ABRIR_O_EVENTO", abrir)
    a08.usar_como_botoes(None, {"alvo": CHAVE}, None)
    assert a08.acionador_nova_tecla(None, {}, None) == {"armou": True}
    fim = time.monotonic() + 5
    while a08._RASCUNHO.esperando and time.monotonic() < fim:
        time.sleep(0.01)
    assert abertos == ["event7"] and acionador.fechado and not acionador.preso
    assert a08._RASCUNHO.teclas[-1] == [PEDAL, "Tecla 2", None]
    assert a08._RASCUNHO.sel == PEDAL
    teclas = a08.campos_do_acionador(a08._CENA_NA_TELA)["acionador-teclas"]
    assert f'value="{PEDAL}" data-linha="tecla" checked' in teclas


def test_o_aparelho_desligado_recusa_esperar_a_tecla(
        a08: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _cena(a08, monkeypatch, _declarado())
    (tmp_path / "vazio").mkdir()
    monkeypatch.setattr(a08, "_RAIZ_DAS_ENTRADAS", str(tmp_path / "vazio"))
    monkeypatch.setattr(a08, "_ABRIR_O_EVENTO", lambda e: pytest.fail("abriu sem aparelho"))
    with pytest.raises(RuntimeError, match="não está ligado"):
        a08.acionador_nova_tecla(None, {}, None)


def test_o_aparelho_que_o_sistema_nao_deixa_ler_falha_o_clique_e_nao_fica_esperando(
        a08: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Sem permissão no ``/dev/input`` o «Esperar a próxima tecla» falha no clique, e não numa
    thread calada que deixava o botão parecer morto.

    MORDIDA: devolva a abertura do nó para dentro da ``_esperar_a_tecla``.
    """
    _cena(a08, monkeypatch, _declarado())
    monkeypatch.setattr(a08, "_RAIZ_DAS_ENTRADAS", str(_sys_de_mentira(tmp_path / "input")))

    def recusar(evento: str) -> Any:
        raise PermissionError(13, "Permission denied", f"/dev/input/{evento}")

    monkeypatch.setattr(a08, "_ABRIR_O_EVENTO", recusar)
    a08.usar_como_botoes(None, {"alvo": CHAVE}, None)
    with pytest.raises(RuntimeError, match="não deixa o Hefesto ler"):
        a08.acionador_nova_tecla(None, {}, None)
    assert not a08._RASCUNHO.esperando


def test_sem_a_cor_lida_os_controles_se_separam_pela_via(a08: Any) -> None:
    """Dois DualSense sem cor lida nem declarada não viram duas opções «DualSense» iguais."""
    ctx = SimpleNamespace(mesa=[
        {"uniq": MACS[0], "nome": "DualSense", "cor": "", "via": "USB"},
        {"uniq": MACS[1], "nome": "DualSense", "cor": "", "via": "BT"},
        {"uniq": MACS[2], "nome": "White", "cor": "white", "via": "BT"}])
    assert a08._quem_recebe_da_mesa(ctx, MaquinaConfig()) == [
        (UNIQS[0], "DualSense · USB"), (UNIQS[1], "DualSense · BT"), (UNIQS[2], "White")]


def test_tirar_todas_as_teclas_esquece_o_acionador(
        a08: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _cena(a08, monkeypatch, _declarado())
    monkeypatch.setattr(a08, "_reler_a_declaracao", lambda: None)
    ponte = _Ponte()
    a08.usar_como_botoes(None, {"alvo": CHAVE}, ponte)
    for linha in a08._RASCUNHO.teclas:
        linha[2] = None
    a08.acionador_guardar(None, {"forma": {}}, ponte)
    assert ponte.chamadas == [{"acionadores": {CHAVE: None}}]


def test_os_quatro_gestos_novos_tem_linha_na_camada(a08: Any) -> None:
    from hefesto_dualsense4unix.interface.pacotes import camada

    for nome in ("usar-como-botoes", "acionador-nova-tecla", "acionador-botao",
                 "acionador-guardar"):
        assert ("08-conexoes.html", nome) in camada.CAMADA, nome


def test_o_tique_da_pagina_escreve_a_janela_do_acionador(
        a08: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Os campos da janela saem no tique (100 ms), ao lado dos da seção, e fora da `#rd-secao`.

    MORDIDA: tire o `campos.update(campos_do_acionador(cena))` do `campos_do_radio`.
    """
    from hefesto_dualsense4unix.interface import aba08

    monkeypatch.setattr(a08, "cena_do_radio", lambda _ctx: aba08.CENA_DO_RADIO)
    campos = a08.campos_do_radio(None)
    assert not set(campos) & {c for c in a08.campos_da_secao(aba08.CENA_DO_RADIO)
                              if c.startswith("acionador-")}
    assert campos["acionador-desenho"] == "cosmic-red"
    assert campos["acionador-titulo"] == "Acionador USB · usar como botões de"
    assert ">Pedal<" in campos["acionador-teclas"] and ">L2<" in campos["acionador-teclas"]
    assert 'selected>Cosmic Red' in campos["acionador-quem"]
    assert campos["acionador-brilho"] == (
        "#acionador #ac-cross,#acionador #ac-circle,#acionador #ac-l2"
        "{filter:drop-shadow(0 0 1.2px #bd93f9) drop-shadow(0 0 2.4px #bd93f9)}")


def test_a_tecla_que_perdeu_o_botao_sai_do_maquina_json(
        a08: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.utils import maquina

    maquina.gravar_maquina_com_descartes(_declarado().model_dump(exclude_none=True))
    _cena(a08, monkeypatch, _declarado())
    monkeypatch.setattr(a08, "_reler_a_declaracao", lambda: None)
    ponte = _Ponte()
    a08.usar_como_botoes(None, {"alvo": CHAVE}, ponte)
    next(t for t in a08._RASCUNHO.teclas if t[0] == PEDAL)[2] = None
    a08.acionador_guardar(None, {"forma": {}}, ponte)
    assert ponte.chamadas[-1]["acionadores"][CHAVE]["teclas"] == {str(TECLA_1): "cross",
                                                                  str(PEDAL): None}
    assert maquina.carregar_maquina().acionadores[CHAVE].teclas == {str(TECLA_1): "cross"}


_CLICAR_O_CIRCULO = r"""
(function(){
  const radio = document.querySelectorAll('#acionador .ac-tecla input')[1];
  const g = document.querySelector('#acionador g[data-entrada="circle"]');
  if (!radio || !g) { return 'sem a tecla 2 ou o círculo'; }
  radio.checked = true;
  g.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
  return 'clicou';
})()
"""


def test_o_clique_no_botao_do_desenho_sai_do_ouvinte_do_piloto_com_a_tecla() -> None:
    """O botão do desenho é um ``<g>`` do SVG: o ouvinte único do piloto lê a classe dele pelo
    atributo (o ``className`` de um elemento SVG não é texto), e o gesto sai com a peça e a tecla
    escolhida. Num WebKit fora da tela, sobre o desenho da 08, com o BOOTSTRAP do piloto."""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("abre a página num WebKit")
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    from hefesto_dualsense4unix.interface import hefesto_vivo, onde

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")
    mensagens: list[dict[str, Any]] = []
    respostas: list[str] = []
    ucm = WebKit2.UserContentManager()
    ucm.register_script_message_handler("hefesto")
    ucm.connect("script-message-received::hefesto",
                lambda _u, r: mensagens.append(json.loads(r.get_js_value().to_string())))
    view = WebKit2.WebView.new_with_user_content_manager(ucm)
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(1212, 809)
    janela.add(view)
    janela.show_all()
    fila = [hefesto_vivo.BOOTSTRAP, _CLICAR_O_CIRCULO]

    def seguinte() -> bool:
        if not fila:
            GLib.timeout_add(300, lambda: (Gtk.main_quit(), False)[1])
            return False
        js = fila.pop(0)

        def respondeu(v: Any, res: Any, _u: Any = None) -> None:
            try:
                respostas.append(v.evaluate_javascript_finish(res).to_string())
            except Exception as erro:
                respostas.append(f"ERRO {erro}")
            GLib.idle_add(seguinte)

        view.evaluate_javascript(js, -1, None, None, None, respondeu, None)
        return False

    def carregou(_v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            seguinte()

    view.connect("load-changed", carregou)
    view.load_uri(onde.pagina("08-conexoes.html", publicado=False).as_uri())
    guarda = GLib.timeout_add(30000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert respostas == ["ok", "clicou"], respostas
    gestos = [m for m in mensagens if m.get("gesto") == "acionador-botao"]
    assert len(gestos) == 1, f"o clique no Círculo não saiu do ouvinte: {mensagens}"
    assert gestos[0]["entrada"] == "circle"
    assert gestos[0]["forma"]["tecla"] == "257"
