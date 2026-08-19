"""FEAT-HOTKEY-PONTE-CYCLE-01 — o gesto PS + seta direita = PRÓXIMA PONTE.

Ponte = a forma como o jogo enxerga o controle (máscara DualSense, máscara
Xbox, mouse+teclado). Ela pediu poder trocar de ponte SEM fechar o jogo.

Dois blocos:

1. DESPACHO. O `_fire` era uma CADEIA de ifs terminada em `else: cb =
   self.on_prev` — qualquer combo que não fosse "gamemode" nem "next" caía no
   perfil ANTERIOR. Um combo novo trocaria o perfil dela para trás no meio da
   partida. Os testes daqui mordem essa cadeia.

2. CICLO. O callback do gesto: origin="manual" (a única origem que atravessa o
   gate R-04 com o jogo aberto), Modo Nativo FORA do ciclo, e o aviso de risco
   pela lightbar ANTES de aplicar — porque foi medido que recriar o vpad com o
   jogo aberto invalida o handle que ele abriu.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import hotkey as hotkey_sub
from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
    CICLO_DE_PONTES,
    PONTE_DUALSENSE,
    PONTE_MOUSE_TECLADO,
    PONTE_XBOX,
    build_next_bridge_callback,
    ponte_atual,
    proxima_ponte,
    start_hotkey_manager,
)
from hefesto_dualsense4unix.integrations.hotkey_daemon import (
    DEFAULT_COMBO_PONTE,
    HotkeyConfig,
    HotkeyManager,
)

# --- 1. despacho: o combo novo NÃO pode cair no on_prev ---------------------


def test_combo_da_ponte_nao_dispara_o_perfil_anterior() -> None:
    """MORDE a cadeia de ifs do `_fire`.

    Com o `else: cb = self.on_prev`, o combo "ponte" chamava on_prev — trocar
    de ponte viraria trocar de perfil para trás no meio da partida dela.
    """
    eventos: list[str] = []
    mgr = HotkeyManager(
        on_next=lambda: eventos.append("next"),
        on_prev=lambda: eventos.append("prev"),
        on_next_bridge=lambda: eventos.append("ponte"),
    )
    mgr.observe(["ps", "dpad_right"], now=0.0)
    assert mgr.observe(["ps", "dpad_right"], now=0.2) == "ponte"
    assert eventos == ["ponte"], "o combo da ponte não pode disparar next/prev"


def test_combo_desconhecido_nao_dispara_callback_nenhum() -> None:
    """Nome sem entrada no despacho não pode virar `on_prev` por descuido."""
    eventos: list[str] = []
    mgr = HotkeyManager(
        on_next=lambda: eventos.append("next"),
        on_prev=lambda: eventos.append("prev"),
        on_next_bridge=lambda: eventos.append("ponte"),
    )
    assert mgr._callback_do_combo("combo_que_nao_existe") == (False, None)
    mgr._fire("combo_que_nao_existe", frozenset({"ps", "l3"}))
    assert eventos == []


def test_todo_combo_configurado_tem_despacho() -> None:
    """Rede para o próximo combo: registrar em `_combos_configurados` sem
    registrar no despacho volta a ser um gesto que cai no callback errado."""
    mgr = HotkeyManager()
    for nome in mgr._combos_configurados():
        conhecido, _cb = mgr._callback_do_combo(nome)
        assert conhecido, f"combo {nome!r} não tem entrada no despacho"


# --- combo: default, vazamento e desligamento -------------------------------


def test_default_do_combo_da_ponte() -> None:
    assert DEFAULT_COMBO_PONTE == ("ps", "dpad_right")
    assert HotkeyConfig().next_bridge == ("ps", "dpad_right")


def test_ponte_nao_vaza_para_o_desktop() -> None:
    """FEAT-HOTKEY-COMBO-NO-LEAK: sem isto o 'dpad_right' do gesto vira seta
    para o desktop (e pode travar segurado)."""
    mgr = HotkeyManager()
    assert mgr.should_passthrough(["ps", "dpad_right"], emulation_active=True) is False
    assert "dpad_right" in mgr.combo_buttons_active(["ps", "dpad_right"])


def test_tupla_vazia_desliga_o_gesto_da_ponte() -> None:
    eventos: list[str] = []
    mgr = HotkeyManager(
        on_next_bridge=lambda: eventos.append("ponte"),
        config=HotkeyConfig(next_bridge=()),
    )
    mgr.observe(["ps", "dpad_right"], now=0.0)
    assert mgr.observe(["ps", "dpad_right"], now=0.2) is None
    assert eventos == []


def test_combo_vazio_nao_dispara_com_nenhum_botao() -> None:
    """MORDE: `frozenset()` vazio é subconjunto de tudo. Antes só o `gamemode`
    tinha guarda de tupla vazia — `next_profile=()` disparava a CADA tick, sem
    ninguém tocar em botão."""
    eventos: list[str] = []
    mgr = HotkeyManager(
        on_next=lambda: eventos.append("next"),
        config=HotkeyConfig(next_profile=()),
    )
    mgr.observe([], now=0.0)
    assert mgr.observe([], now=0.5) is None
    assert eventos == []


# --- 2. ciclo de pontes -----------------------------------------------------


class _FakeDevice:
    def __init__(self, flavor: str) -> None:
        self.flavor = flavor


class _FakeController:
    def __init__(self, trilha: list[Any]) -> None:
        self._trilha = trilha

    def set_led(self, color: tuple[int, int, int]) -> None:
        self._trilha.append(("led", color))

    def reassert_resolved_outputs(self) -> None:
        self._trilha.append(("reassert", None))


class _FakeStore:
    def __init__(self, native: bool = False) -> None:
        self.native_mode_active = native
        self.bumps: list[str] = []

    def bump(self, chave: str) -> None:
        self.bumps.append(chave)


class _FakeDaemon:
    """Daemon dublado: registra a TRILHA (ordem) de LEDs e de chamadas."""

    def __init__(
        self,
        *,
        flavor: str | None = PONTE_DUALSENSE,
        authority: str = "unknown",
        native: bool = False,
        aplica: bool = True,
    ) -> None:
        self.trilha: list[Any] = []
        self.controller = _FakeController(self.trilha)
        self.store = _FakeStore(native)
        self.display_authority = authority
        self._gamepad_device: Any = None if flavor is None else _FakeDevice(flavor)
        self._aplica = aplica
        self.mouse: list[bool] = []
        self.mouse_origem: list[str] = []
        self.teclado: list[bool] = []
        self.supressao: list[bool | None] = []

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        return fn(*args)

    def set_gamepad_emulation(
        self, enabled: bool, flavor: str | None = None, *, origin: str = "manual"
    ) -> bool:
        self.trilha.append(("gamepad", enabled, flavor, origin))
        if not self._aplica:
            return False
        self._gamepad_device = _FakeDevice(flavor or PONTE_DUALSENSE) if enabled else None
        return True

    def set_mouse_emulation(
        self, enabled: bool, *, origin: str = "profile"
    ) -> bool:
        # ORIGEM-QUE-MENTE-01 (08/08): o protocolo exige `origin` explícito, e o
        # dublê tem de exigir também — senão a chamada real estoura, o
        # `contextlib.suppress` do produto engole, e o teste vira verde sobre uma
        # ponte que não subiu. Guardamos o par para PROVAR que a origem viaja.
        self.mouse.append(enabled)
        self.mouse_origem.append(origin)
        return enabled

    def set_keyboard_emulation(self, enabled: bool) -> bool:
        self.teclado.append(enabled)
        return enabled

    def set_emulation_suppressed(self, value: bool | None = None) -> bool:
        self.supressao.append(value)
        return bool(value)


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zera as durações da lightbar — o teste mede ORDEM, não relógio."""
    monkeypatch.setattr(hotkey_sub, "PULSO_SEG", 0.0)
    monkeypatch.setattr(hotkey_sub, "COR_PONTE_SEG", 0.0)


def test_ponte_atual_le_o_estado_vivo() -> None:
    """Lê o vpad, não a config: foi o papel dizer `xbox` e o vivo dizer
    `dualsense` que pôs o daemon em laço na noite de 18/08."""
    assert ponte_atual(_FakeDaemon(flavor="xbox")) == PONTE_XBOX  # type: ignore[arg-type]
    assert ponte_atual(_FakeDaemon(flavor=None)) == PONTE_MOUSE_TECLADO  # type: ignore[arg-type]


def test_proxima_ponte_da_a_volta() -> None:
    assert proxima_ponte(PONTE_DUALSENSE) == PONTE_XBOX
    assert proxima_ponte(PONTE_XBOX) == PONTE_MOUSE_TECLADO
    assert proxima_ponte(PONTE_MOUSE_TECLADO) == PONTE_DUALSENSE
    assert proxima_ponte("coisa_nenhuma") == CICLO_DE_PONTES[0]


@pytest.mark.asyncio
async def test_gesto_troca_a_mascara_com_origin_manual() -> None:
    """MORDE o item 3: só `origin="manual"` atravessa o gate R-04 com o jogo
    aberto. Com origin="profile" a troca é RECUSADA e o gesto vira nada."""
    d = _FakeDaemon(flavor=PONTE_DUALSENSE)
    await build_next_bridge_callback(d)()  # type: ignore[arg-type]
    chamadas = [t for t in d.trilha if t[0] == "gamepad"]
    assert chamadas == [("gamepad", True, PONTE_XBOX, "manual")]


@pytest.mark.asyncio
async def test_gesto_avisa_pela_lightbar_antes_de_derrubar_o_jogo() -> None:
    """HONESTIDADE (item 5): com o jogo na autoridade, a troca recria o vpad e
    pode invalidar o handle do jogo. O aviso vermelho tem de vir ANTES da
    troca — depois já não é aviso, é laudo."""
    d = _FakeDaemon(flavor=PONTE_DUALSENSE, authority="game")
    await build_next_bridge_callback(d)()  # type: ignore[arg-type]

    indice_vermelho = next(
        i
        for i, t in enumerate(d.trilha)
        if t[0] == "led" and t[1] == hotkey_sub.COR_AVISO_RISCO
    )
    indice_troca = next(i for i, t in enumerate(d.trilha) if t[0] == "gamepad")
    assert indice_vermelho < indice_troca, "o aviso saiu depois da troca"
    # E a cor da ponte nova aparece depois, dizendo qual ponte ficou de pé.
    assert ("led", hotkey_sub.CORES_DA_PONTE[PONTE_XBOX]) in d.trilha[indice_troca:]


@pytest.mark.asyncio
async def test_sem_jogo_na_autoridade_nao_ha_aviso_vermelho() -> None:
    """Aviso é para risco real. No desktop a troca não derruba nada, e piscar
    vermelho à toa ensinaria a ignorar o vermelho."""
    d = _FakeDaemon(flavor=PONTE_DUALSENSE, authority="daemon")
    await build_next_bridge_callback(d)()  # type: ignore[arg-type]
    assert ("led", hotkey_sub.COR_AVISO_RISCO) not in d.trilha
    assert ("led", hotkey_sub.CORES_DA_PONTE[PONTE_XBOX]) in d.trilha


@pytest.mark.asyncio
async def test_ponte_mouse_teclado_derruba_o_vpad_e_solta_a_supressao() -> None:
    """A ponte de point-and-click sobe MUDA se o modo jogo continuar ligado —
    é a supressão que gateia o dispatch de mouse/teclado no poll loop."""
    d = _FakeDaemon(flavor=PONTE_XBOX)
    await build_next_bridge_callback(d)()  # type: ignore[arg-type]
    assert ("gamepad", False, None, "manual") in d.trilha
    assert d.supressao == [False]
    assert d.mouse == [True]
    assert d.teclado == [True]


@pytest.mark.asyncio
async def test_modo_nativo_fica_fora_do_ciclo() -> None:
    """Item 4: o `observe` roda DEPOIS do gate do nativo no poll loop, e o
    nativo mata o vpad sem consultar o R-04 — seria queda sem porta de volta
    pelo controle. Nenhuma ponte do ciclo pode entrar nele."""
    assert "nativo" not in CICLO_DE_PONTES
    assert "native" not in CICLO_DE_PONTES
    d = _FakeDaemon(flavor=PONTE_DUALSENSE, native=True)
    await build_next_bridge_callback(d)()  # type: ignore[arg-type]
    assert d.trilha == [], "em Modo Nativo o gesto não pode mexer em nada"


@pytest.mark.asyncio
async def test_ponte_que_nao_sobe_avisa_em_vez_de_mentir() -> None:
    """`set_gamepad_emulation` devolve True para três desfechos diferentes
    (aplicou, já-estava, bloqueado). O sinal honesto compara com o estado
    VIVO — e, se a ponte não subiu, a lightbar diz isso."""
    d = _FakeDaemon(flavor=PONTE_DUALSENSE, aplica=False)
    await build_next_bridge_callback(d)()  # type: ignore[arg-type]
    assert ("led", hotkey_sub.CORES_DA_PONTE[PONTE_XBOX]) not in d.trilha
    assert ("led", hotkey_sub.COR_AVISO_RISCO) in d.trilha


@pytest.mark.asyncio
async def test_gesto_deixa_rastro_no_store() -> None:
    d = _FakeDaemon(flavor=PONTE_DUALSENSE)
    await build_next_bridge_callback(d)()  # type: ignore[arg-type]
    assert "hotkey.ponte.cycled" in d.store.bumps


# --- wiring no subsystem ----------------------------------------------------


class _Cfg:
    ps_long_press_ms = 0
    ps_button_action = "steam"


class _WireDaemon:
    config = _Cfg()
    controller = None
    store = None
    _keyboard_device = None
    _hotkey_manager: Any = None


def test_start_hotkey_manager_liga_o_gesto_da_ponte() -> None:
    d = _WireDaemon()
    start_hotkey_manager(d)  # type: ignore[arg-type]
    mgr = d._hotkey_manager
    assert mgr.config.next_bridge == DEFAULT_COMBO_PONTE
    assert mgr.on_next_bridge is not None
    # E o despacho leva o combo ao callback certo — não ao on_prev.
    assert mgr._callback_do_combo("ponte")[1] is mgr.on_next_bridge
