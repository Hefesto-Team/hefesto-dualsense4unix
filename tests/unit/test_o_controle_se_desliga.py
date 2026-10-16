"""O controle se desliga pelo PS segurado por 10 s, e só ele
(O-CONTROLE-SE-DESLIGA-PELO-BOTAO-PELO-GESTO-E-PELA-OCIOSIDADE-01).

O verbo `desligar_o_controle` escreve o SET_FEATURE `0x08` («Set Bluetooth Control», 47 B,
`buf[1] = 2`, CRC-32 de semente `0x53`) no hidraw do controle pedido e em nenhum outro; no cabo
recusa sem escrever. O gesto assina a borda `ps_pressed` de cada handle adotado pelo `connect()`.

O dublê fica no fundo: um opener que abre o `/dev/null` e lembra o caminho, e o `fcntl.ioctl`
que anota o pedido; nenhum caminho é um hidraw de verdade. Os controles são o Starlight Blue e o
White, no rádio, em faixa forjada.
"""

from __future__ import annotations

import fcntl
import os
import threading
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest
from pydualsense.event_system import Event

from hefesto_dualsense4unix.core import backend_pydualsense as backend_mod
from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.ds_output_report import bt_crc32

STARLIGHT_BLUE = "AA:BB:CC:00:00:01"
WHITE = "AA:BB:CC:00:00:02"
_HIDIOCSFEATURE_47 = (3 << 30) | (47 << 16) | (ord("H") << 8) | 0x06


class _Handle:
    """O mínimo de um handle adotado: o nó, o transporte e as bordas dos botões da pydualsense."""

    dpad_up: Event

    def __init__(self, path: bytes, *, radio: bool = True) -> None:
        self._pinned_path = path
        self.conType = SimpleNamespace(name="BT" if radio else "USB")
        self.ps_pressed = Event()
        for nome in backend_mod._OS_OUTROS_BOTOES:
            setattr(self, nome, Event())


def _backend() -> PyDualSenseController:
    """O `PyDualSenseController` real, sem aparelho."""
    from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

    reader = EvdevReader(device_path=None)
    reader._device_path = None
    return PyDualSenseController(evdev_reader=reader)


def _mesa(**handles: _Handle) -> PyDualSenseController:
    inst = _backend()
    inst._handles = dict(handles)
    inst._primary_key = next(iter(handles))
    return inst


def _uniq(key: str) -> str:
    uniq = PyDualSenseController._key_to_uniq(key)
    assert uniq is not None
    return str(uniq)


class _Hidraw:
    """O dublê do hidraw: o opener abre o `/dev/null` e lembra o caminho; o ioctl anota."""

    def __init__(self) -> None:
        self.escritas: list[tuple[str, int, bytes]] = []
        self._caminhos: dict[int, str] = {}

    def abrir(self, caminho: str) -> int:
        fd = os.open(os.devnull, os.O_RDONLY)
        self._caminhos[fd] = caminho
        return fd

    def ioctl(self, fd: int, pedido: int, buf: Any, mutavel: bool = False) -> int:
        self.escritas.append((self._caminhos[fd], pedido, bytes(buf)))
        return len(buf)


@pytest.fixture()
def hidraw(monkeypatch: pytest.MonkeyPatch) -> _Hidraw:
    dubl = _Hidraw()
    monkeypatch.setattr(fcntl, "ioctl", dubl.ioctl)
    return dubl


def _mesa_no_hidraw(hidraw: _Hidraw, **handles: _Handle) -> PyDualSenseController:
    inst = _mesa(**handles)
    inst.set_feature_opener(hidraw.abrir)
    return inst


# --- o verbo -------------------------------------------------------------------------------------


def test_o_verbo_escreve_o_0x08_so_no_controle_pedido(hidraw: _Hidraw) -> None:
    """**A MORDIDA.** O White se desliga e o Starlight Blue, no mesmo adaptador, não recebe nada.

    MORDIDA: escrever o `0x08` em todo handle da mesa reprova aqui (duas escritas).
    """
    azul, branco = _Handle(b"/dev/hidraw-falso-3"), _Handle(b"/dev/hidraw-falso-5")
    inst = _mesa_no_hidraw(hidraw, **{STARLIGHT_BLUE: azul, WHITE: branco})

    assert inst.desligar_o_controle(_uniq(WHITE)) is True

    assert [(caminho, pedido) for caminho, pedido, _ in hidraw.escritas] == [
        ("/dev/hidraw-falso-5", _HIDIOCSFEATURE_47)
    ]


def test_o_pedido_e_o_0x08_com_valor_2_assinado_com_a_semente_de_escrita(
    hidraw: _Hidraw,
) -> None:
    inst = _mesa_no_hidraw(hidraw, **{WHITE: _Handle(b"/dev/hidraw-falso-5")})

    inst.desligar_o_controle(_uniq(WHITE))

    ((_, _, dados),) = hidraw.escritas
    assert len(dados) == 47
    assert dados[0] == 0x08 and dados[1] == 0x02
    assert dados[2:43] == bytes(41)
    assert int.from_bytes(dados[43:], "little") == bt_crc32(dados[:43], seed=0x53)
    assert int.from_bytes(dados[43:], "little") != bt_crc32(dados[:43], seed=0xA3), (
        "a semente da LEITURA (0xA3) o firmware recusa"
    )


def test_no_cabo_o_verbo_recusa_sem_escrever(hidraw: _Hidraw) -> None:
    """No cabo a energia vem do fio e o `0x08` não foi medido: nada sai."""
    inst = _mesa_no_hidraw(hidraw, **{STARLIGHT_BLUE: _Handle(b"/dev/hidraw-falso-3", radio=False)})

    assert inst.desligar_o_controle(_uniq(STARLIGHT_BLUE)) is False
    assert hidraw.escritas == []


def test_endereco_que_nao_esta_na_mesa_nao_escreve(hidraw: _Hidraw) -> None:
    inst = _mesa_no_hidraw(hidraw, **{STARLIGHT_BLUE: _Handle(b"/dev/hidraw-falso-3")})

    assert inst.desligar_o_controle(_uniq(WHITE)) is False
    assert hidraw.escritas == []


def test_o_hidraw_que_recusa_devolve_falso(
    hidraw: _Hidraw, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _recusa(*_a: Any, **_k: Any) -> int:
        raise OSError(32, "Broken pipe")

    monkeypatch.setattr(fcntl, "ioctl", _recusa)
    inst = _mesa_no_hidraw(hidraw, **{WHITE: _Handle(b"/dev/hidraw-falso-5")})

    assert inst.desligar_o_controle(_uniq(WHITE)) is False


# --- o gesto -------------------------------------------------------------------------------------


class _Prazo:
    """O `threading.Timer` de mentira: anota o prazo e só dispara quando o teste manda."""

    criados: ClassVar[list[_Prazo]] = []

    def __init__(self, segundos: float, alvo: Any) -> None:
        self.segundos = segundos
        self.alvo = alvo
        self.daemon = False
        self.iniciado = False
        self.cancelado = False
        _Prazo.criados.append(self)

    def start(self) -> None:
        self.iniciado = True

    def cancel(self) -> None:
        self.cancelado = True

    def vencer(self) -> None:
        if not self.cancelado:
            self.alvo()


@pytest.fixture()
def prazos(monkeypatch: pytest.MonkeyPatch) -> list[_Prazo]:
    _Prazo.criados = []
    monkeypatch.setattr(backend_mod, "_TEMPORIZADOR_DO_PS", _Prazo)
    return _Prazo.criados


@pytest.fixture()
def desligados(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    pedidos: list[str] = []

    def _desligar(self: PyDualSenseController, uniq: str) -> bool:
        pedidos.append(uniq)
        return True

    monkeypatch.setattr(PyDualSenseController, "desligar_o_controle", _desligar)
    return pedidos


def _connect(
    inst: PyDualSenseController, monkeypatch: pytest.MonkeyPatch, handles: dict[str, _Handle]
) -> None:
    """Roda o `connect()` REAL adotando os handles dados, sem aparelho."""
    chaves = list(handles)

    def _enumerar() -> list[tuple[str, str, bool]]:
        return [(k, f"/dev/hidraw-falso-{i}", False) for i, k in enumerate(chaves)]

    def _abrir(path: str, *, is_edge: bool = False) -> _Handle:
        return handles[chaves[int(path.rsplit("-", 1)[1])]]

    monkeypatch.setattr(inst, "_enumerate_device_keys", _enumerar)
    monkeypatch.setattr(inst, "_open_one", _abrir)
    monkeypatch.setattr(inst, "_refresh_sysfs_leds", lambda: None)
    monkeypatch.setattr(inst, "_conhecer_o_firmware", lambda key, handle: None)
    monkeypatch.setattr(inst, "assumir_volume_padrao_na_adocao", lambda key, handle: None)
    monkeypatch.setattr(inst, "_reapply_desired", lambda key, handle: None)
    monkeypatch.setattr(inst, "reassert_resolved_outputs", lambda: None)
    monkeypatch.setattr(inst, "_recompute_primary", lambda: None)
    inst.connect()


def test_segurar_o_ps_por_10_s_desliga_so_aquele_controle(
    monkeypatch: pytest.MonkeyPatch, prazos: list[_Prazo], desligados: list[str]
) -> None:
    # D-1610-O-PS-SEGURADO-10-S-DESLIGA-AQUELE-CONTROLE
    """**A MORDIDA.** O `connect()` adota os dois; o PS segurado do White desliga só o White.

    MORDIDA: tirar a assinatura do laço de `new_handles` (ou o prazo) reprova aqui.
    """
    azul, branco = _Handle(b"/dev/hidraw-falso-3"), _Handle(b"/dev/hidraw-falso-5")
    inst = _backend()
    _connect(inst, monkeypatch, {STARLIGHT_BLUE: azul, WHITE: branco})

    branco.ps_pressed(True)

    (prazo,) = prazos
    assert prazo.segundos == 10.0 and prazo.iniciado and prazo.daemon
    prazo.vencer()
    assert desligados == [_uniq(WHITE)]


def test_soltar_o_ps_antes_dos_10_s_cancela(
    monkeypatch: pytest.MonkeyPatch, prazos: list[_Prazo], desligados: list[str]
) -> None:
    """Um toque no PS (os Gestos do PS da aba Navegação são todos curtos) não desliga nada."""
    branco = _Handle(b"/dev/hidraw-falso-5")
    inst = _backend()
    _connect(inst, monkeypatch, {WHITE: branco})

    branco.ps_pressed(True)
    branco.ps_pressed(False)

    (prazo,) = prazos
    assert prazo.cancelado
    prazo.vencer()
    assert desligados == []


def test_o_ps_com_outro_botao_e_combo_e_nao_desliga(
    monkeypatch: pytest.MonkeyPatch, prazos: list[_Prazo], desligados: list[str]
) -> None:
    """**A MORDIDA.** Quem troca de perfil com PS + cima e segura o PS além dos 10 s não perde o
    controle: o combo é dos Gestos do PS, e o prazo cai no primeiro botão junto.

    MORDIDA: não assinar as bordas dos outros botões reprova aqui.
    """
    branco = _Handle(b"/dev/hidraw-falso-5")
    inst = _backend()
    _connect(inst, monkeypatch, {WHITE: branco})

    branco.ps_pressed(True)
    branco.dpad_up(True)
    branco.dpad_up(False)

    (prazo,) = prazos
    assert prazo.cancelado
    prazo.vencer()
    assert desligados == []


@pytest.mark.parametrize("gatilho", ["r2_changed", "l2_changed"])
def test_o_ps_com_o_gatilho_dos_acessorios_segurado_nao_desliga(
    monkeypatch: pytest.MonkeyPatch,
    prazos: list[_Prazo],
    desligados: list[str],
    gatilho: str,
) -> None:
    """**A MORDIDA.** O PS com R2 ou L2 comanda os acessórios e se segura além dos 10 s (o nível
    ao vivo): o gatilho junto do PS é combo, e o controle segue ligado na mão de quem joga.

    MORDIDA: tirar os gatilhos das bordas que cancelam o prazo reprova aqui.
    """
    branco = _Handle(b"/dev/hidraw-falso-5")
    inst = _backend()
    _connect(inst, monkeypatch, {WHITE: branco})

    branco.ps_pressed(True)
    getattr(branco, gatilho)(True)

    (prazo,) = prazos
    assert prazo.cancelado
    prazo.vencer()
    assert desligados == []


def test_a_readocao_do_mesmo_handle_nao_assina_de_novo(
    monkeypatch: pytest.MonkeyPatch, prazos: list[_Prazo], desligados: list[str]
) -> None:
    branco = _Handle(b"/dev/hidraw-falso-5")
    inst = _backend()
    backend_mod._vigiar_o_ps_segurado(inst, WHITE, branco)
    backend_mod._vigiar_o_ps_segurado(inst, WHITE, branco)

    assert len(branco.ps_pressed._event_handler) == 1


def test_o_controle_que_caiu_no_meio_nao_herda_o_gesto(
    prazos: list[_Prazo], desligados: list[str]
) -> None:
    """O White caiu e voltou com outro handle enquanto o PS do primeiro estava apertado."""
    velho, novo = _Handle(b"/dev/hidraw-falso-5"), _Handle(b"/dev/hidraw-falso-6")
    inst = _mesa(**{WHITE: velho})
    backend_mod._vigiar_o_ps_segurado(inst, WHITE, velho)

    velho.ps_pressed(True)
    inst._handles = {WHITE: novo}
    prazos[0].vencer()

    assert desligados == []


def test_o_prazo_de_verdade_dispara_fora_da_thread_de_report(
    monkeypatch: pytest.MonkeyPatch, desligados: list[str]
) -> None:
    """Com o `threading.Timer` real e o prazo encurtado, o desligar chega sozinho."""
    monkeypatch.setattr(backend_mod, "SEGUNDOS_DO_PS_QUE_DESLIGA", 0.05)
    branco = _Handle(b"/dev/hidraw-falso-5")
    inst = _mesa(**{WHITE: branco})
    backend_mod._vigiar_o_ps_segurado(inst, WHITE, branco)

    branco.ps_pressed(True)
    for _ in range(100):
        if desligados:
            break
        threading.Event().wait(0.01)

    assert desligados == [_uniq(WHITE)]
