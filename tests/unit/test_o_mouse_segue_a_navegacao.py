"""O-MOUSE-SEGUE-A-NAVEGACAO-01 — o liga/desliga do mouse é do modo, e o modo tem uma porta.

A bancada da demo de 29/09 (achado 13, o passo 7): ela tocou o chip
«Navegação», e o cursor não andou com o analógico. O arranjo obedecia ao
`mouse.enabled: false` do Freestyle — um `{false, 6, 1}` com a forma do estado
vivo copiado, e não de uma escolha dela —, o PS + R3 pela mesma porta ligava (o
`forcar_mouse`), e a ativação de perfil ligava e desligava o mouse em qualquer
modo. Três donos, e cada porta perguntava a um.

As duas perguntas da sprint foram decididas em 29/09 por quem coordena, pelo
padrão dela e com ela dormindo, e ela pode desfazer:
D-2909-A-NAVEGACAO-LIGA-O-MOUSE (entrar na Navegação liga o mouse, pelas duas
portas) e D-2909-A-NAVEGACAO-NAO-RELIGA-O-TECLADO (a entrada deixa o teclado com
a lista «Função do teclado»).

A BANCADA é um lar de mentira: o `Daemon` é SUBCLASSE do real (herda as
assinaturas), o `ProfileManager` é o real, os perfis e as flags de sessão moram
no `XDG_CONFIG_HOME` do teste, e só a borda é dublada — o device uinput do
mouse (a fábrica real do subsistema roda, e só o `UinputMouseDevice` é de
mentira), o teclado virtual, a fábrica do pad, o grab, o co-op, o launch env e
a notificação da supressão. Toda régua lê o que o daemon RECEBEU e o disco
relido pelo `loader`, nunca o relatório que a função devolve. Os números são
`speed 11`/`scroll 4` no perfil e `3` na flag de sessão, para o recuo não passar
pelo mesmo valor.

A MORDIDA de cada régua está no docstring dela.
"""
from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, Literal

import pytest

from hefesto_dualsense4unix.daemon import launch_env
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems import external_mask as em
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.integrations import uinput_mouse
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    Profile,
    ProfileModeConfig,
    ProfileMouseConfig,
)
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import session

P1 = "aabbcc000001"
FREESTYLE = loader.NOME_DO_PADRAO
PERFIL = "Perfil da Régua"


# ---------------------------------------------------------------------------
# A borda dublada
# ---------------------------------------------------------------------------
class _Bancada:
    """O que a borda anotou, e as duas chaves que fazem a fábrica recusar."""

    def __init__(self) -> None:
        self.mouse_sobe = True
        self.paradas_do_pad = 0


class _MouseDeMentira:
    """O `UinputMouseDevice` sem `/dev/uinput`: a fábrica real do subsistema o cria."""

    bancada: _Bancada

    def __init__(self, *, mouse_speed: int, scroll_speed: int, poll_hz: int) -> None:
        self.velocidades = (mouse_speed, scroll_speed)

    def start(self) -> bool:
        return self.bancada.mouse_sobe

    def stop(self) -> None:
        return

    def set_speed(self, *, mouse_speed: int, scroll_speed: int) -> None:
        self.velocidades = (mouse_speed, scroll_speed)


class _Vpad:
    def __init__(self, mascara: str, identity: str | None, caminho: str | None) -> None:
        self.flavor = mascara
        self.identity = identity
        self.backend = "uhid" if vp.quer_uhid(caminho, mascara) else "uinput"
        vp._pendurar_o_caminho(self, vp.caminho_resolvido(caminho, mascara))

    def stop(self) -> None:
        return


class _DaemonDaNavegacao(Daemon):
    """SUBCLASSE do daemon real. Os setters do mouse e do teclado rodam os REAIS.

    Eles só anotam o que receberam e seguem para o produto: a exclusão mútua do
    pad, a fábrica do mouse e a flag de sessão são as de verdade. O teclado
    virtual e a notificação da supressão são a borda.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.recebeu: list[tuple[str, tuple[Any, ...]]] = []

    def set_mouse_emulation(
        self,
        enabled: bool,
        speed: int | None = None,
        scroll_speed: int | None = None,
        *,
        origin: Literal["manual", "profile"],
    ) -> bool:
        self.recebeu.append(("set_mouse_emulation", (enabled, speed, scroll_speed)))
        return super().set_mouse_emulation(enabled, speed, scroll_speed, origin=origin)

    def set_mouse_speed(
        self, speed: int | None = None, scroll_speed: int | None = None
    ) -> bool:
        self.recebeu.append(("set_mouse_speed", (speed, scroll_speed)))
        return super().set_mouse_speed(speed, scroll_speed)

    def set_keyboard_emulation(self, enabled: bool, *, persist: bool = True) -> bool:
        self.recebeu.append(("set_keyboard_emulation", (enabled, persist)))
        return super().set_keyboard_emulation(enabled, persist=persist)

    def _start_keyboard_emulation(self) -> bool:
        self._keyboard_device = SimpleNamespace(set_bindings=lambda _m: None)
        return True

    def _stop_keyboard_emulation(self) -> None:
        self._keyboard_device = None

    def set_emulation_suppressed(
        self,
        value: bool | None = None,
        *,
        origin: Literal["manual", "profile"] = "manual",
    ) -> bool:
        self.recebeu.append(("set_emulation_suppressed", (value,)))
        self._emulation_suppressed = bool(value)
        return bool(value)

    def _stop_gamepad_emulation(self) -> None:
        self.recebeu.append(("_stop_gamepad_emulation", ()))
        super()._stop_gamepad_emulation()

    # --- as perguntas que a régua faz ao que foi recebido -------------------
    def chamadas(self, metodo: str) -> list[tuple[Any, ...]]:
        return [args for nome, args in self.recebeu if nome == metodo]

    def mouse_de_pe(self) -> bool:
        return bool(self.config.mouse_emulation_enabled and self._mouse_device is not None)


@pytest.fixture
def bancada(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Bancada]:
    b = _Bancada()
    _MouseDeMentira.bancada = b
    monkeypatch.setattr(uinput_mouse, "UinputMouseDevice", _MouseDeMentira)

    def _fabrica(flavor: Any, *, identity: Any = None, caminho: Any = None, **_k: Any) -> _Vpad:
        return _Vpad(em.mascara_efetiva(identity, flavor), identity, caminho)

    def _parar(daemon: Any, *, persist: bool = True, release_grab: bool = True) -> None:
        if daemon._gamepad_device is not None:
            b.paradas_do_pad += 1
        daemon._gamepad_device = None
        daemon.config.gamepad_emulation_enabled = False

    monkeypatch.setattr(vp, "make_virtual_pad", _fabrica)
    monkeypatch.setattr(gp, "stop_gamepad_emulation", _parar)
    dubles: dict[str, Any] = {
        "_set_controller_grab": lambda d, g: None,
        "_materialize_launch_env": lambda d: None,
        "start_motion_reader": lambda d, dev: None,
        "stop_motion_reader": lambda d: None,
        "read_primary_calibration": lambda d: None,
        "make_primary_rumble_sink": lambda d: None,
        "make_primary_replica_sinks": lambda d: {},
        "controller_allows_uhid": lambda d: False,
        "vpad_vivo": lambda dev: True,
        "_deve_promover_backend": lambda *a, **k: False,
    }
    for nome, valor in dubles.items():
        monkeypatch.setattr(gp, nome, valor)
    monkeypatch.setattr(coop_mod, "numero_do_nome_do_primario", lambda d, fallback=1: 1)
    monkeypatch.setattr(
        coop_mod, "get_coop_manager", lambda d: SimpleNamespace(sync=lambda force=False: None)
    )
    monkeypatch.setattr(launch_env, "materialize_launch_env", lambda d: None)
    em._zerar_registro_de_mascaras()
    yield b
    em._zerar_registro_de_mascaras()


def _daemon() -> _DaemonDaNavegacao:
    controle = FakeController(transport="bt")
    controle.primary_uniq = P1  # type: ignore[attr-defined]
    return _DaemonDaNavegacao(
        controller=controle, config=DaemonConfig(mouse_speed=6, mouse_scroll_speed=1)
    )


def _gerente(d: _DaemonDaNavegacao) -> ProfileManager:
    """O gerente real, com os dois appliers do daemon real que esta régua mede."""
    return ProfileManager(
        controller=d.controller,
        store=d.store,
        mouse_applier=d.apply_profile_mouse,
        mode_applier=d.apply_profile_mode,
    )


def _perfil(
    nome: str,
    *,
    mode: dict[str, Any] | None,
    mouse: dict[str, Any] | None,
) -> None:
    loader.save_profile(
        Profile(
            name=nome,
            match=MatchAny(),
            mode=ProfileModeConfig(**mode) if mode is not None else None,
            mouse=ProfileMouseConfig(**mouse) if mouse is not None else None,
        ),
        origem="régua",
    )


def _pad_de_pe(d: _DaemonDaNavegacao) -> None:
    desfecho = gp.start_gamepad_emulation_desfecho(d, None, origin="profile", caminho="dualsense")
    assert desfecho == gp.EMU_APLICADO, f"premissa da bancada: {desfecho}"


def _mouse_de_pe(d: _DaemonDaNavegacao) -> None:
    """A Navegação de pé: o pad caiu e o mouse está ligado (a premissa)."""
    assert d.set_mouse_emulation(True, origin="profile") is True, "premissa da bancada"
    d.recebeu.clear()


# ---------------------------------------------------------------------------
# 5. A ativação fora da Navegação não mexe no liga/desliga
# ---------------------------------------------------------------------------
def test_a_ativacao_de_um_perfil_de_pad_nao_liga_o_mouse(bancada: _Bancada) -> None:
    """O Freestyle com `mouse.enabled: true` e `kind: gamepad`, o pad de pé.

    O «Ativar» à mão aplica as velocidades e não liga o mouse: ligar derrubaria
    o pad pela exclusão mútua, e o `mode_applier` logo depois o levantaria de
    novo, com o co-op recriando os secundários (~2,9 s com quatro controles).

    MORDIDA: tire a pergunta pelo `kind` de `Daemon.apply_profile_mouse` e o
    pad para.
    """
    d = _daemon()
    _perfil(FREESTYLE, mode={"kind": "gamepad", "caminho": "dualsense"},
            mouse={"enabled": True, "speed": 11, "scroll_speed": 4})
    _pad_de_pe(d)

    _gerente(d).activate(FREESTYLE, origin="manual")

    assert bancada.paradas_do_pad == 0, "a ativação de um perfil de pad derrubou o pad"
    assert d.chamadas("_stop_gamepad_emulation") == []
    assert [a for a in d.chamadas("set_mouse_emulation") if a[0]] == [], (
        "a ativação de um perfil de pad ligou o mouse")
    assert (11, 4) in d.chamadas("set_mouse_speed"), (
        f"as velocidades do perfil não entraram: {d.recebeu}")


def test_o_perfil_sem_modo_nao_desliga_a_navegacao(bancada: _Bancada) -> None:
    """O mouse ligado na Navegação; entra um perfil sem `mode` com `enabled: false`.

    É a forma do perfil de um jogo que o autoswitch ativa: sem opinião de modo,
    ele não tem autoridade para desligar o mouse, e o chip «Navegação» seguiria
    aceso sobre um cursor morto.

    MORDIDA: a mesma da régua 5 — o mouse desliga.
    """
    d = _daemon()
    _perfil(PERFIL, mode=None, mouse={"enabled": False, "speed": 11, "scroll_speed": 4})
    _mouse_de_pe(d)

    _gerente(d).activate(PERFIL, origin="autoswitch")

    assert d.mouse_de_pe(), "o perfil sem opinião de modo desligou o mouse da Navegação"
    assert [a for a in d.chamadas("set_mouse_emulation") if not a[0]] == []


def test_o_perfil_de_navegacao_obedece_ao_que_ela_gravou(bancada: _Bancada) -> None:
    """Um perfil com `kind: desktop` e `enabled: false`, com o mouse ligado: desliga.

    É a suspensão do «Status do Modo» sobrevivendo a uma ativação.

    MORDIDA: ignore o `enabled` sempre (a Navegação que só liga) e o mouse fica
    ligado.
    """
    d = _daemon()
    _perfil(PERFIL, mode={"kind": "desktop"},
            mouse={"enabled": False, "speed": 11, "scroll_speed": 4})
    _mouse_de_pe(d)

    _gerente(d).activate(PERFIL, origin="manual")

    assert not d.mouse_de_pe(), (
        "o perfil de Navegação que diz mouse desligado não o desligou")


# ---------------------------------------------------------------------------
# 11. A tela da ativação não muda
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("modo", [{"kind": "gamepad", "caminho": "dualsense"}, {"kind": "desktop"}],
                         ids=["fora-da-navegacao", "na-navegacao"])
def test_o_rodape_da_ativacao_le_o_mouse_como_aplicado(
    bancada: _Bancada, modo: dict[str, Any]
) -> None:
    """Um `profile.switch` real, lido pelo leitor da TELA (`relato_da_ativacao`).

    A palavra do applier não muda: a aba Perfis lê qualquer outra como seção
    que não entrou, e diria no rodapé do «Ativar» que o mouse não entrou.

    MORDIDA: faça `apply_profile_mouse` devolver `ligado` no ramo que liga, e a
    célula `na-navegacao` reprova; devolver `nao_opina` no ramo das
    velocidades derruba a `fora-da-navegacao`. Nos dois, `failed` ganha o mouse.
    """
    import asyncio

    from tests.conftest import exigir_gi_real

    exigir_gi_real("o leitor da tela mora em `app.actions`, que carrega o GTK")
    from hefesto_dualsense4unix.app.actions.profiles_actions import relato_da_ativacao
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    class _Handlers(IpcHandlersMixin):
        def __init__(self, daemon: _DaemonDaNavegacao) -> None:
            self.daemon = daemon
            self.store = daemon.store
            self.profile_manager = _gerente(daemon)

    d = _daemon()
    _perfil(PERFIL, mode=modo, mouse={"enabled": True, "speed": 11, "scroll_speed": 4})
    _pad_de_pe(d)
    session.save_mouse_emulation(False)

    resposta = asyncio.run(_Handlers(d)._handle_profile_switch({"name": PERFIL}))
    relato = relato_da_ativacao(resposta)

    assert relato is not None, f"o daemon não disse as seções: {resposta}"
    assert "mouse" in relato["applied"], relato
    assert "mouse" not in " ".join(relato["failed"]).lower(), relato


# ---------------------------------------------------------------------------
# O commit 2: a entrada na Navegação é uma só, e liga o mouse
# ---------------------------------------------------------------------------
FLAG_DA_SESSAO = {"enabled": False, "speed": 3, "scroll_speed": 1}


def _flag_do_mouse(corpo: dict[str, Any] | None) -> None:
    session.save_mouse_emulation(
        bool(corpo and corpo["enabled"]),
        speed=(corpo or {}).get("speed"),
        scroll_speed=(corpo or {}).get("scroll_speed"),
    )


class _Handlers:
    """O mixin de IPC de verdade, com o daemon e o gerente da bancada."""

    def __new__(cls, daemon: _DaemonDaNavegacao) -> Any:
        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

        class _H(IpcHandlersMixin):
            pass

        h = _H()
        h.daemon = daemon  # type: ignore[assignment]
        h.store = daemon.store  # type: ignore[assignment]
        h.profile_manager = _gerente(daemon)  # type: ignore[assignment]
        return h


def _ativo(d: _DaemonDaNavegacao, nome: str) -> None:
    d.store.set_active_profile(nome)


def _o_chip(d: _DaemonDaNavegacao) -> dict[str, Any]:
    import asyncio

    return asyncio.run(_Handlers(d)._handle_desktop_arranjo_apply({"origin": "manual"}))


# ---------------------------------------------------------------------------
# 1. O chip liga o mouse com o perfil que diz desligado
# ---------------------------------------------------------------------------
def test_o_chip_liga_o_mouse_com_o_perfil_que_diz_desligado(bancada: _Bancada) -> None:
    """O perfil com `{enabled: false, 11, 4}` e o mouse desligado: o chip liga.

    MORDIDA: devolva ao arranjo o ramo que obedece ao `enabled` do perfil (pelo
    `apply_profile_mouse`); o ramo idempotente devolve antes do setter, e o
    `_mouse_device` segue `None`.
    """
    d = _daemon()
    _flag_do_mouse(FLAG_DA_SESSAO)
    _perfil(PERFIL, mode=None, mouse={"enabled": False, "speed": 11, "scroll_speed": 4})
    _ativo(d, PERFIL)

    _o_chip(d)

    assert (True, 11, 4) in d.chamadas("set_mouse_emulation"), (
        f"o chip não ligou o mouse com as velocidades do perfil: {d.recebeu}")
    assert d.mouse_de_pe(), "o chip entrou na Navegação sem cursor — o achado 13"


def test_o_chip_sem_a_secao_liga_com_as_velocidades_da_sessao(bancada: _Bancada) -> None:
    """O perfil sem a seção `mouse`, e a flag de sessão dizendo desligado com `speed 3`.

    O recuo de antes (`restore_mouse_preference`) obedecia à flag e deixava o
    mouse desligado. Agora a entrada liga, e as velocidades saem da flag.

    MORDIDA: devolva o recuo à preferência da flag e a régua reprova com o
    mouse desligado.
    """
    d = _daemon()
    _flag_do_mouse(FLAG_DA_SESSAO)
    _perfil(PERFIL, mode=None, mouse=None)
    _ativo(d, PERFIL)

    _o_chip(d)

    assert (True, 3, 1) in d.chamadas("set_mouse_emulation"), d.recebeu
    assert d.mouse_de_pe()


# ---------------------------------------------------------------------------
# 2. As duas portas dão o mesmo
# ---------------------------------------------------------------------------
def test_o_chip_e_o_ps_r3_dao_o_mesmo(bancada: _Bancada) -> None:
    """Dois daemons iguais, o mesmo perfil: o chip num, o PS + R3 no outro.

    As listas de chamadas aos setters do mouse, do teclado e da supressão são
    iguais, na ordem.

    MORDIDA: faça o gesto religar o teclado por conta própria antes do arranjo
    (`daemon.set_keyboard_emulation(True, persist=True)` no `hotkey.py`, o que
    ele fazia até o SEGUNDO-ESCRITOR-01) e as listas divergem.
    """
    from hefesto_dualsense4unix.daemon.subsystems import hotkey

    listas = []
    for porta in ("chip", "ps_r3"):
        d = _daemon()
        _flag_do_mouse(FLAG_DA_SESSAO)
        _perfil(PERFIL, mode={"kind": "gamepad", "caminho": "dualsense"},
                mouse={"enabled": False, "speed": 11, "scroll_speed": 4})
        _ativo(d, PERFIL)
        _pad_de_pe(d)
        d.recebeu.clear()
        if porta == "chip":
            import asyncio

            h = _Handlers(d)
            asyncio.run(h._handle_gamepad_emulation_set({"enabled": False, "origin": "manual"}))
            asyncio.run(h._handle_desktop_arranjo_apply({"origin": "manual"}))
        else:
            hotkey._aplicar_ponte(d, hotkey.PONTE_MOUSE_TECLADO)
        listas.append([
            (nome, args) for nome, args in d.recebeu
            if nome in ("set_mouse_emulation", "set_keyboard_emulation",
                        "set_emulation_suppressed")
        ])
    chip, ps_r3 = listas
    assert chip == ps_r3, f"o chip pediu {chip} e o PS + R3 pediu {ps_r3}"
    assert ("set_mouse_emulation", (True, 11, 4)) in chip


# ---------------------------------------------------------------------------
# 3. A entrada grava o que ligou
# ---------------------------------------------------------------------------
def test_a_entrada_grava_o_mouse_ligado_junto_com_o_modo(bancada: _Bancada) -> None:
    """O Freestyle ligado com `{false, 11, 4}` e `kind: gamepad`; o chip pela porta.

    O `freestyle.json` relido diz `mouse.enabled: true` e `mode.kind: desktop`,
    com UMA versão nova no `.historico`: o disco, o chip e o «Status do Modo»
    dizem a mesma coisa depois da entrada.

    MORDIDA: tire a escrita da seção `mouse` (o `mouse_ligado` que o arranjo
    passa ao escritor) e o disco segue `false`.
    """
    from hefesto_dualsense4unix.profiles.manager import ligar_o_freestyle

    d = _daemon()
    _flag_do_mouse(FLAG_DA_SESSAO)
    _perfil(FREESTYLE, mode={"kind": "gamepad", "caminho": "dualsense"},
            mouse={"enabled": False, "speed": 11, "scroll_speed": 4})
    ligar_o_freestyle(d.store, True)
    _ativo(d, FREESTYLE)
    versoes = len(loader.listar_historico(FREESTYLE))

    _o_chip(d)

    relido = loader.load_profile(FREESTYLE)
    assert relido.mode is not None and relido.mode.kind == "desktop", relido.mode
    assert relido.mouse is not None and relido.mouse.enabled is True, (
        f"a entrada ligou o mouse e o perfil seguiu dizendo {relido.mouse!r}")
    assert (relido.mouse.speed, relido.mouse.scroll_speed) == (11, 4), (
        "a entrada trocou as velocidades que as barras da aba gravaram")
    assert len(loader.listar_historico(FREESTYLE)) == versoes + 1, (
        "o modo e o mouse foram em duas gravações")


# ---------------------------------------------------------------------------
# 4. O arranjo chamado direto não grava
# ---------------------------------------------------------------------------
def test_o_arranjo_chamado_direto_liga_e_nao_grava(bancada: _Bancada) -> None:
    """Sem a porta, o arranjo liga o mouse e não muda o `sha256` do perfil.

    MORDIDA: grave por `origin == "manual"` em vez do `grava_o_modo`, e o
    `sha256` muda.
    """
    import hashlib

    d = _daemon()
    _flag_do_mouse(FLAG_DA_SESSAO)
    _perfil(PERFIL, mode=None, mouse={"enabled": False, "speed": 11, "scroll_speed": 4})
    _ativo(d, PERFIL)
    arquivo = loader._profile_path(loader.load_profile(PERFIL))
    antes = hashlib.sha256(arquivo.read_bytes()).hexdigest()

    d.aplicar_o_arranjo_do_desktop(origin="manual")

    assert d.mouse_de_pe()
    assert hashlib.sha256(arquivo.read_bytes()).hexdigest() == antes, (
        "o arranjo chamado direto escreveu no perfil")


# ---------------------------------------------------------------------------
# 9. O socorro não volta
# ---------------------------------------------------------------------------
def test_o_socorro_forcar_mouse_nao_volta() -> None:
    """Nenhum nome, argumento, atributo ou chave `forcar_mouse` em `src/`.

    Lido pela árvore: a prosa que conta a história (docstring, comentário) não
    conta.

    MORDIDA: devolva o parâmetro ao `hotkey.py` (`arranjo(..., forcar_mouse=True)`)
    e a régua nomeia a linha.
    """
    import ast
    from pathlib import Path

    src = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"
    achados: list[str] = []
    for py in sorted(src.rglob("*.py")):
        arvore = ast.parse(py.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            nome = (
                no.id if isinstance(no, ast.Name)
                else no.arg if isinstance(no, ast.arg | ast.keyword)
                else no.attr if isinstance(no, ast.Attribute)
                else no.value if isinstance(no, ast.Constant) and isinstance(no.value, str)
                else None
            )
            if nome == "forcar_mouse":
                achados.append(f"{py.relative_to(src)}:{getattr(no, 'lineno', '?')}")
    assert not achados, f"o socorro do PS + R3 voltou: {achados}"


# ---------------------------------------------------------------------------
# 10. O diário diz o estado
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(("sobe", "esperado"), [(True, "ligado"), (False, "desligado")],
                         ids=["o-device-subiu", "a-fabrica-recusou"])
def test_o_diario_diz_o_mouse_vivo(bancada: _Bancada, sobe: bool, esperado: str) -> None:
    """`arranjo_do_desktop_aplicado` diz `mouse_vivo`, lido do device.

    MORDIDA: escreva `mouse_vivo` a partir do pedido (o `True` que foi ao
    setter) em vez do device; com a fábrica recusando, a régua reprova.
    """
    import structlog

    d = _daemon()
    _flag_do_mouse(FLAG_DA_SESSAO)
    _perfil(PERFIL, mode=None, mouse={"enabled": True, "speed": 11, "scroll_speed": 4})
    _ativo(d, PERFIL)
    bancada.mouse_sobe = sobe

    with structlog.testing.capture_logs() as registros:
        d.aplicar_o_arranjo_do_desktop(origin="manual")

    linhas = [r for r in registros if r.get("event") == "arranjo_do_desktop_aplicado"]
    assert len(linhas) == 1, registros
    assert linhas[0].get("mouse_vivo") == esperado, linhas[0]
    assert linhas[0].get("mouse") in ("aplicado", "falhou"), (
        "a chave `mouse` saiu do vocabulário do applier")


# ---------------------------------------------------------------------------
# 12. O perfil de Navegação sem a seção liga na ativação
# ---------------------------------------------------------------------------
def test_o_perfil_de_navegacao_sem_secao_liga_o_mouse_na_ativacao(bancada: _Bancada) -> None:
    """O pad de pé, um perfil com `kind: desktop` e sem `mouse`, a flag com `speed 3`.

    A ativação à mão liga o mouse com as velocidades da flag, e o pad cai.

    MORDIDA: tire a chamada do `mouse_applier` sem a seção
    (`ProfileManager.apply_emulation`); o setter não é chamado e o
    `_mouse_device` segue `None`.
    """
    d = _daemon()
    _flag_do_mouse(FLAG_DA_SESSAO)
    _perfil(PERFIL, mode={"kind": "desktop"}, mouse=None)
    _pad_de_pe(d)

    _gerente(d).activate(PERFIL, origin="manual")

    assert (True, 3, 1) in d.chamadas("set_mouse_emulation"), d.recebeu
    assert d.mouse_de_pe(), "o perfil de Navegação sem a seção entrou sem cursor"
    assert d._gamepad_device is None, "o pad ficou de pé na Navegação"
