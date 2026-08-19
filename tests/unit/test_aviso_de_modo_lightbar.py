"""AVISO-DE-MODO-01 — o controle DIZ em que modo está, pela lightbar.

Pedido dela, 19/08/2026: *"um alerta visual no lightbar de todos os controles
dualsense conectados, seja via bt, seja via cabo. seja com steam aberta ou não.
(…) entramos no modo steam input azul clarinho, modo xbox verde claro, modo
sony nativo branco (…) o lightbar de todos pisca 3 vezes rápido"*.

Quatro blocos, e cada um morde uma coisa diferente:

1. **BACKEND** — a piscada sai em TODOS os controles, pelas rotas que o mapa de
   canais mede (sysfs no cabo, `0x31` avulso no rádio), e DEVOLVE a cor do
   perfil ao fim. O aviso que rouba a cor dela e não devolve é o defeito, não a
   cura.
2. **MODO VIGENTE** — os cinco estados lidos do VIVO, com a precedência certa
   (nativo > Steam Input > ponte).
3. **LEVEL-TRIGGERED** — o boot não pisca; a troca pisca; a cor é a do modo
   novo; e o carimbo só sai quando a piscada saiu.
4. **GATILHO** — os dois pontos de `daemon/subsystems/gamepad.py`, e a guarda
   que separa a parada de VERDADE do passo intermediário: `release_grab`, não
   `persist`. Errar essa guarda deixa o Modo Nativo mudo (ele desliga a
   emulação com `origin="profile"`, ou seja `persist=False`) ou faz a barra
   piscar âmbar no meio de uma troca de máscara.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from hefesto_dualsense4unix.core.backend_pydualsense import (
    AVISO_APAGADO,
    AVISO_PISCADAS,
    KERNEL_DEFAULT_BLUE,
    PyDualSenseController,
    _DesiredOutput,
)
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gamepad_sub
from hefesto_dualsense4unix.daemon.subsystems import hotkey as hotkey_sub
from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
    CORES_DO_MODO,
    MODO_NATIVO,
    MODO_STEAM_INPUT,
    PONTE_DUALSENSE,
    PONTE_MOUSE_TECLADO,
    PONTE_XBOX,
    avisar_troca_de_modo,
    modo_vigente,
)

#: Keys MAC-formadas (faixa forjada aa:bb:cc — teste-guarda de anonimato).
KEY_CABO = "AA:BB:CC:00:00:01"
KEY_RADIO = "AA:BB:CC:00:00:02"
UNIQ_CABO = "aabbcc000001"

ROXO_DELA = (129, 61, 156)


def _null_evdev() -> EvdevReader:
    reader = EvdevReader(device_path=None)
    reader._device_path = None
    return reader


# --- 1. backend: pinta em todos, pelas duas rotas, e devolve ----------------


class _FakeLight:
    def __init__(self) -> None:
        self.colors: list[tuple[int, int, int]] = []

    def setColorI(self, r: int, g: int, b: int) -> None:  # noqa: N802 — API pydualsense
        self.colors.append((r, g, b))


class _FakeHandle:
    def __init__(self, *, transport_name: str = "USB") -> None:
        self.connected = True
        self.light = _FakeLight()
        self.conType = type("CT", (), {"name": transport_name})()
        self.audio = SimpleNamespace(setMicrophoneLED=lambda _v: None)
        #: Reports `0x31` avulsos escritos no hidraw (a rota do rádio).
        self.reports: list[list[int]] = []

    def writeReport(self, out: list[int]) -> None:  # noqa: N802 — API pydualsense
        self.reports.append(list(out))


class _FakeNode:
    """Nó sysfs da classe LED — a rota preferida do cabo."""

    def __init__(self, *, aceita: bool = True) -> None:
        self.escritas: list[tuple[int, int, int]] = []
        self._aceita = aceita

    def set_rgb(self, r: int, g: int, b: int, **_kw: Any) -> bool:
        self.escritas.append((r, g, b))
        return self._aceita

    def set_players(self, _bits: Any) -> bool:
        return True


def _backend_com_dois() -> tuple[PyDualSenseController, _FakeHandle, _FakeHandle, _FakeNode]:
    """Um controle no CABO (com nó sysfs) e um no RÁDIO (só hidraw)."""
    inst = PyDualSenseController(evdev_reader=_null_evdev())
    cabo = _FakeHandle(transport_name="USB")
    radio = _FakeHandle(transport_name="BT")
    node = _FakeNode()
    inst._handles = {KEY_CABO: cabo, KEY_RADIO: radio}  # type: ignore[dict-item]
    inst._sysfs = {KEY_CABO: node}  # type: ignore[dict-item]
    inst._primary_key = KEY_CABO
    return inst, cabo, radio, node


def test_a_piscada_alcanca_os_dois_transportes() -> None:
    """O mapa de canais mede `luz.lightbar.cor` com `aciona=sim` nos DOIS.

    No cabo a rota preferida é o sysfs; no rádio é o `0x31` AVULSO escrito no
    hidraw (ROTA-BT-EM-REGIME-01), que é o que pinta quando a Steam tem o nó
    aberto — exatamente o caso "com a steam aberta" que ela pediu.
    """
    inst, _cabo, radio, node = _backend_com_dois()
    assert inst.pintar_lightbar_sem_lembrar((10, 20, 30)) == 2
    assert (10, 20, 30) in node.escritas, "o do cabo não recebeu pelo sysfs"
    assert radio.reports, "o do rádio não recebeu o 0x31 avulso"


def test_a_piscada_ignora_o_seletor_de_controle() -> None:
    """Ela pediu "o lightbar de TODOS" — o alvo da janela não pode calar os
    outros, e é isso que o `broadcast=True` compra."""
    inst, _cabo, radio, node = _backend_com_dois()
    inst.set_output_target(0)  # mira só o primeiro
    inst.pintar_lightbar_sem_lembrar((10, 20, 30))
    assert node.escritas and radio.reports, "o aviso ficou preso no alvo"


def test_o_aviso_nao_rouba_a_cor_dela() -> None:
    """A MORDIDA principal. O `set_led` GRAVA a cor no estado desejado — e no
    broadcast o `_record_desired_locked` ainda LIMPA o campo `led` de todos os
    overrides por-uniq. Um aviso por ali apagaria o perfil dela de verdade: o
    reassert seguinte devolveria a cor do AVISO."""
    inst, _cabo, _radio, _node = _backend_com_dois()
    inst._desired_by_uniq[UNIQ_CABO] = _DesiredOutput(led=ROXO_DELA)

    inst.pintar_lightbar_sem_lembrar((255, 0, 0))

    assert inst._desired_default.led is None, "o aviso gravou no default"
    assert inst._desired_by_uniq[UNIQ_CABO].led == ROXO_DELA, "o roxo dela sumiu"


def test_a_piscada_devolve_a_cor_do_perfil() -> None:
    """Fim da sequência = a cor dela de volta, nos dois transportes."""
    inst, _cabo, radio, node = _backend_com_dois()
    inst._desired_default.led = ROXO_DELA

    inst.piscar_aviso_de_modo((255, 0, 0), aceso_s=0.0, apagado_s=0.0)

    assert node.escritas[-1] == ROXO_DELA, "o cabo ficou com a cor do aviso"
    assert radio.reports, "o rádio não recebeu nada"


def test_a_piscada_e_por_cor_e_sao_tres() -> None:
    """`luz.lightbar.brilho` tem `aciona=não` nos dois transportes: apagar é
    escrever PRETO, nunca mexer no brilho. E ela pediu TRÊS."""
    inst, _cabo, _radio, node = _backend_com_dois()
    cor = (1, 2, 3)

    inst.piscar_aviso_de_modo(cor, aceso_s=0.0, apagado_s=0.0)

    assert node.escritas.count(cor) == AVISO_PISCADAS == 3
    assert node.escritas.count(AVISO_APAGADO) == AVISO_PISCADAS


def test_sem_cor_resolvida_devolve_o_azul_do_kernel() -> None:
    """Mesma escolha do priming: controle virgem volta ACESO, não apagado."""
    inst, _cabo, _radio, node = _backend_com_dois()
    inst.restaurar_lightbar_do_perfil()
    assert node.escritas[-1] == KERNEL_DEFAULT_BLUE


def test_um_controle_que_nao_obedece_nao_derruba_os_outros() -> None:
    """O caso MEDIDO do rádio travado: a barra ignora as escritas até o
    power-off físico. O produto registra e segue com os outros — travar ou
    mentir seria pior que não avisar."""
    inst, _cabo, radio, node = _backend_com_dois()

    def _explode(_out: list[int]) -> None:
        raise OSError("EPIPE")

    radio.writeReport = _explode  # type: ignore[assignment]

    inst.piscar_aviso_de_modo((1, 2, 3), aceso_s=0.0, apagado_s=0.0)

    assert node.escritas, "a falha de um controle calou o outro"


def test_em_modo_nativo_a_piscada_e_no_op() -> None:
    """Regra dela: no Modo Nativo o dono do aparelho é o jogo. Zero escrita."""
    inst, _cabo, radio, node = _backend_com_dois()
    inst._output_mute = True
    assert inst.pintar_lightbar_sem_lembrar((1, 2, 3)) == 0
    assert not node.escritas and not radio.reports


# --- 2. modo vigente --------------------------------------------------------


class _Store:
    def __init__(self, native: bool = False) -> None:
        self.native_mode_active = native
        self.bumps: list[str] = []

    def bump(self, chave: str) -> None:
        self.bumps.append(chave)


class _Daemon:
    """Daemon dublado: só o que o aviso lê, e a trilha do que ele pediu."""

    def __init__(
        self,
        *,
        flavor: str | None = PONTE_DUALSENSE,
        native: bool = False,
        steam_input: bool = False,
        com_backend: bool = True,
    ) -> None:
        self.store = _Store(native)
        self._gamepad_device: Any = (
            None if flavor is None else SimpleNamespace(flavor=flavor)
        )
        self._steam_input_excecao = steam_input
        self.piscadas: list[tuple[int, int, int]] = []
        self.controller: Any = (
            SimpleNamespace(piscar_aviso_de_modo=self._piscar)
            if com_backend
            else SimpleNamespace()
        )

    def is_native_mode(self) -> bool:
        return bool(self.store.native_mode_active)

    def _piscar(self, cor: tuple[int, int, int], **_kw: Any) -> int:
        self.piscadas.append(cor)
        return 2


def test_modo_vigente_le_os_cinco_estados() -> None:
    assert modo_vigente(_Daemon(flavor="dualsense")) == PONTE_DUALSENSE  # type: ignore[arg-type]
    assert modo_vigente(_Daemon(flavor="xbox")) == PONTE_XBOX  # type: ignore[arg-type]
    assert modo_vigente(_Daemon(flavor=None)) == PONTE_MOUSE_TECLADO  # type: ignore[arg-type]
    assert modo_vigente(_Daemon(steam_input=True)) == MODO_STEAM_INPUT  # type: ignore[arg-type]
    assert modo_vigente(_Daemon(native=True)) == MODO_NATIVO  # type: ignore[arg-type]


def test_o_nativo_vence_o_steam_input_que_vence_a_ponte() -> None:
    """Precedência = quem está NA FRENTE do controle. No nativo não há vpad
    nosso para consultar; na exceção quem entrega o dispositivo é a Steam,
    mesmo com o nosso vpad de pé."""
    d = _Daemon(flavor=PONTE_XBOX, steam_input=True, native=True)
    assert modo_vigente(d) == MODO_NATIVO  # type: ignore[arg-type]
    d.store.native_mode_active = False
    assert modo_vigente(d) == MODO_STEAM_INPUT  # type: ignore[arg-type]
    d._steam_input_excecao = False
    assert modo_vigente(d) == PONTE_XBOX  # type: ignore[arg-type]


def test_toda_cor_do_lexico_existe_e_nenhuma_se_repete() -> None:
    """Duas cores iguais em modos diferentes é a barra dizendo duas coisas com
    a mesma luz — e foi por isso que a máscara DualSense saiu do azul."""
    for modo in (
        MODO_STEAM_INPUT,
        MODO_NATIVO,
        PONTE_DUALSENSE,
        PONTE_XBOX,
        PONTE_MOUSE_TECLADO,
    ):
        assert modo in CORES_DO_MODO, f"modo {modo!r} sem cor"
    assert len(set(CORES_DO_MODO.values())) == len(CORES_DO_MODO)
    #: Os hex da paleta de `gui/theme.css` — o léxico visual desta casa.
    assert CORES_DO_MODO[PONTE_DUALSENSE] == (0xFF, 0x79, 0xC6), "o rosa da marca"
    assert CORES_DO_MODO[MODO_STEAM_INPUT] == (0x8B, 0xE9, 0xFD)
    assert CORES_DO_MODO[PONTE_XBOX] == (0x50, 0xFA, 0x7B)
    assert CORES_DO_MODO[MODO_NATIVO] == (0xF8, 0xF8, 0xF2)
    assert CORES_DO_MODO[PONTE_MOUSE_TECLADO] == (0xFF, 0xB8, 0x6C)


# --- 3. level-triggered -----------------------------------------------------


def _sem_thread(monkeypatch: Any) -> None:
    """Roda a piscada INLINE — o teste mede o que foi pedido, não o relógio."""

    class _Inline:
        def __init__(self, *, target: Any, **_kw: Any) -> None:
            self._target = target

        def start(self) -> None:
            self._target()

    monkeypatch.setattr(hotkey_sub.threading, "Thread", _Inline)


def test_o_boot_nao_pisca(monkeypatch: Any) -> None:
    """Um daemon que sobe já em máscara DualSense não pode piscar como se ela
    tivesse acabado de mexer em alguma coisa."""
    _sem_thread(monkeypatch)
    d = _Daemon(flavor=PONTE_DUALSENSE)
    assert avisar_troca_de_modo(d) is None  # type: ignore[arg-type]
    assert d.piscadas == []
    assert d._modo_anunciado == PONTE_DUALSENSE


def test_a_troca_pisca_na_cor_do_modo_novo(monkeypatch: Any) -> None:
    _sem_thread(monkeypatch)
    d = _Daemon(flavor=PONTE_DUALSENSE)
    avisar_troca_de_modo(d)  # type: ignore[arg-type]  — primeira leitura
    d._gamepad_device = SimpleNamespace(flavor=PONTE_XBOX)

    assert avisar_troca_de_modo(d) == PONTE_XBOX  # type: ignore[arg-type]
    assert d.piscadas == [CORES_DO_MODO[PONTE_XBOX]]


def test_sem_troca_nao_pisca_a_cada_tique(monkeypatch: Any) -> None:
    """O aviso é chamado do poll loop a cada tique. Piscar por estar chamado
    seria a barra piscando para sempre."""
    _sem_thread(monkeypatch)
    d = _Daemon(flavor=PONTE_DUALSENSE)
    for _ in range(50):
        avisar_troca_de_modo(d)  # type: ignore[arg-type]
    assert d.piscadas == []


def test_a_janela_pisca_igual_ao_gesto(monkeypatch: Any) -> None:
    """Ela pediu que valesse "seja com steam aberta ou não" e por qualquer
    porta. O aviso não sabe QUEM trocou — só que trocou —, então a troca pela
    janela (que aqui é só o estado vivo mudando) acende igual."""
    _sem_thread(monkeypatch)
    d = _Daemon(flavor=PONTE_XBOX)
    avisar_troca_de_modo(d)  # type: ignore[arg-type]
    d._steam_input_excecao = True
    assert avisar_troca_de_modo(d) == MODO_STEAM_INPUT  # type: ignore[arg-type]
    d.store.native_mode_active = True
    assert avisar_troca_de_modo(d) == MODO_NATIVO  # type: ignore[arg-type]
    assert d.piscadas == [
        CORES_DO_MODO[MODO_STEAM_INPUT],
        CORES_DO_MODO[MODO_NATIVO],
    ]


def test_sem_backend_o_modo_nao_e_carimbado(monkeypatch: Any) -> None:
    """O carimbo é a prova de que o aviso SAIU, não um "eu vi que mudou" — se
    fosse carimbado sem piscar, a troca ficaria muda para sempre."""
    _sem_thread(monkeypatch)
    d = _Daemon(flavor=PONTE_DUALSENSE, com_backend=False)
    d._modo_anunciado = PONTE_XBOX  # type: ignore[attr-defined]
    assert avisar_troca_de_modo(d) is None  # type: ignore[arg-type]
    assert d._modo_anunciado == PONTE_XBOX


# --- 4. o gatilho, nos dois pontos de gamepad.py ----------------------------


class _DaemonDeGatilho(_Daemon):
    """Acrescenta o mínimo que `stop_gamepad_emulation` toca."""

    def __init__(self, **kw: Any) -> None:
        super().__init__(**kw)
        self.config = SimpleNamespace(
            gamepad_emulation_enabled=True, rumble_active=None
        )
        self.controller = SimpleNamespace(
            piscar_aviso_de_modo=self._piscar,
            set_rumble=lambda *_a, **_kw: None,
        )


def test_o_dispatch_dispara_o_aviso(monkeypatch: Any) -> None:
    """Ponto 1: com vpad de pé, o poll loop passa por aqui a cada tique — é o
    que cobre a troca vinda da janela, da CLI e do autoswitch."""
    _sem_thread(monkeypatch)
    chamadas: list[Any] = []
    monkeypatch.setattr(gamepad_sub, "_reconciliar_launch", lambda _d: None)
    monkeypatch.setattr(
        hotkey_sub, "avisar_troca_de_modo", lambda d: chamadas.append(d)
    )
    d = _DaemonDeGatilho(flavor=None)
    gamepad_sub.dispatch_gamepad(d, SimpleNamespace(), frozenset())  # type: ignore[arg-type]
    assert chamadas == [d], "o dispatch não avisou (e o device era None)"


def test_a_troca_de_mascara_nao_anuncia_mouse_teclado(monkeypatch: Any) -> None:
    """`release_grab=False` é o carimbo de quem recria o vpad no instante
    seguinte. Anunciar mouse+teclado no meio seria a barra piscando âmbar num
    modo em que ela nunca esteve."""
    _sem_thread(monkeypatch)
    chamadas: list[Any] = []
    monkeypatch.setattr(
        hotkey_sub, "avisar_troca_de_modo", lambda d: chamadas.append(d)
    )
    monkeypatch.setattr(gamepad_sub, "stop_motion_reader", lambda _d: None)
    monkeypatch.setattr(gamepad_sub, "_set_controller_grab", lambda _d, _g: None)
    monkeypatch.setattr(gamepad_sub, "_materialize_launch_env", lambda _d: None)
    d = _DaemonDeGatilho(flavor=PONTE_DUALSENSE)

    gamepad_sub.stop_gamepad_emulation(d, persist=False, release_grab=False)  # type: ignore[arg-type]
    assert chamadas == [], "a troca de máscara anunciou um modo intermediário"

    gamepad_sub.stop_gamepad_emulation(d)  # type: ignore[arg-type]
    assert chamadas == [d], "o desligamento de verdade não avisou"


def test_o_release_do_modo_nativo_avisa_mesmo_sem_persist(monkeypatch: Any) -> None:
    """MORDE a guarda errada. `persist` significa "a PREFERÊNCIA dela mudou"
    (R-07: `persist=(origin == "manual")`), não "o vpad vai voltar já".

    `lifecycle._release_controller_to_game` desliga a emulação com
    `origin="profile"` — ou seja `persist=False` — e é EXATAMENTE a troca que
    tem de piscar branco. Com a guarda em `persist`, entrar em Modo Nativo
    ficava mudo, e ela pediu o branco por escrito.
    """
    _sem_thread(monkeypatch)
    chamadas: list[Any] = []
    monkeypatch.setattr(
        hotkey_sub, "avisar_troca_de_modo", lambda d: chamadas.append(d)
    )
    monkeypatch.setattr(gamepad_sub, "stop_motion_reader", lambda _d: None)
    monkeypatch.setattr(gamepad_sub, "_set_controller_grab", lambda _d, _g: None)
    monkeypatch.setattr(gamepad_sub, "_materialize_launch_env", lambda _d: None)
    d = _DaemonDeGatilho(flavor=PONTE_DUALSENSE, native=True)

    gamepad_sub.stop_gamepad_emulation(d, persist=False)  # type: ignore[arg-type]
    assert chamadas == [d], "entrar em Modo Nativo ficou mudo"


def test_o_shutdown_nao_anuncia_modo_nenhum(monkeypatch: Any) -> None:
    """O vpad cai porque o produto está saindo, não porque o modo mudou —
    e piscar na saída seria o controle mentindo no último gesto."""
    _sem_thread(monkeypatch)
    chamadas: list[Any] = []
    monkeypatch.setattr(
        hotkey_sub, "avisar_troca_de_modo", lambda d: chamadas.append(d)
    )
    monkeypatch.setattr(gamepad_sub, "stop_motion_reader", lambda _d: None)
    monkeypatch.setattr(gamepad_sub, "_set_controller_grab", lambda _d, _g: None)
    monkeypatch.setattr(gamepad_sub, "_materialize_launch_env", lambda _d: None)
    d = _DaemonDeGatilho(flavor=PONTE_DUALSENSE)
    d._is_stopping = lambda: True  # type: ignore[attr-defined]

    gamepad_sub.stop_gamepad_emulation(d, persist=False)  # type: ignore[arg-type]
    assert chamadas == [], "o shutdown anunciou um modo"
