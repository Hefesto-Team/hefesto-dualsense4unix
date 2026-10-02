"""O-MODO-SE-GRAVA-ONDE-ELE-MUDA-01 — quem troca o modo grava o modo.

A bancada da demo de 29/09 (achado 2, 01h43): com o Modo Freestyle ligado e os
quatro DualSense no rádio, ela clicou no «Sony DualSense» da aba Jogar. Os
quatro pads trocaram, e o `freestyle.json` seguiu dizendo `caminho: xbox`. Quem
gravava o modo do chip era a JANELA, depois da resposta do
`gamepad.emulation.set`; com quatro pads a troca levou ~2,9 s, a janela desistiu
aos 2,0 s, e a escolha nunca chegou ao perfil.

A cura: um escritor só, no daemon (`Daemon.gravar_o_modo_escolhido`), que os
três setters do modo chamam DEPOIS do aparelho, e só quando a porta diz que é
escolha dela (`grava_o_modo`). A janela deixou de gravar o modo.

A BANCADA é um lar de mentira: o `Daemon` é SUBCLASSE do real (herda as
assinaturas, e o dublê não pode ser mais frouxo que o produto), o
`ProfileManager` é o real, os perfis moram no `XDG_CONFIG_HOME` do teste, e só
a borda é dublada — a fábrica do pad (nenhum `/dev/uinput`, nenhum `/dev/uhid`),
o grab, o co-op, o mouse e o teclado virtuais, o launch env e a exposição do
Modo Nativo. O disco é lido pelo `loader`, antes e depois, e nunca pelo retorno
do escritor. Os endereços são da faixa forjada da casa.

A MORDIDA de cada régua está no docstring dela.
"""
from __future__ import annotations

import ast
import asyncio
import hashlib
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

import pytest
import structlog

from hefesto_dualsense4unix.daemon import launch_env
from hefesto_dualsense4unix.daemon import lifecycle
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems import external_mask as em
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems import hotkey
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from tests.unit.ponte_do_rodape import PonteDoRodape
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.manager import ProfileManager, ligar_o_freestyle
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    Profile,
    ProfileModeConfig,
)
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils.xdg_paths import config_dir, profiles_dir

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"

P1 = "aabbcc000001"
FREESTYLE = loader.NOME_DO_PADRAO
JOGO = "Jogo da Régua"
JANELA_DO_JOGO = "steam_app_480"


class _Vpad:
    """O pad de mentira. O canal sai da regra do produto (`quer_uhid`)."""

    def __init__(self, mascara: str, identity: str | None, caminho: str | None) -> None:
        self.flavor = mascara
        self.identity = identity
        self.backend = "uhid" if vp.quer_uhid(caminho, mascara) else "uinput"
        vp._pendurar_o_caminho(self, vp.caminho_resolvido(caminho, mascara))
        self.parado = False

    def stop(self) -> None:
        self.parado = True


class _Bancada:
    """O que a borda anotou: quantos pads pararam, e se a fábrica recusa."""

    def __init__(self) -> None:
        self.paradas = 0
        self.fabrica_recusa = False

    def fabrica(
        self, flavor: Any, *, identity: Any = None, caminho: Any = None, **_kw: Any
    ) -> _Vpad | None:
        if self.fabrica_recusa:
            return None
        return _Vpad(em.mascara_efetiva(identity, flavor), identity, caminho)

    def parar(self, daemon: Any, *, persist: bool = True, release_grab: bool = True) -> None:
        if daemon._gamepad_device is not None:
            daemon._gamepad_device.stop()
            self.paradas += 1
        daemon._gamepad_device = None
        daemon.config.gamepad_emulation_enabled = False


class _DaemonDaCasa(Daemon):
    """SUBCLASSE do daemon real. Só a borda que tocaria aparelho é interceptada."""

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
        return True

    def set_mouse_speed(
        self, speed: int | None = None, scroll_speed: int | None = None
    ) -> bool:
        return True

    def set_keyboard_emulation(self, enabled: bool, *, persist: bool = True) -> bool:
        return True

    def set_emulation_suppressed(
        self,
        value: bool | None = None,
        *,
        origin: Literal["manual", "profile"] = "manual",
    ) -> bool:
        return bool(value)

    def _exposicao_do_modo_nativo(self, ligar: bool) -> None:
        self.recebeu.append(("_exposicao_do_modo_nativo", (ligar,)))

    def _reapply_last_profile(self) -> None:
        self.recebeu.append(("_reapply_last_profile", ()))


class _Handlers(IpcHandlersMixin):
    """O mixin de IPC de verdade, com o daemon e o gerente da bancada."""

    def __init__(self, daemon: _DaemonDaCasa, gerente: ProfileManager) -> None:
        self.daemon = daemon
        self.store = daemon.store
        self.profile_manager = gerente


@pytest.fixture
def bancada(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Bancada]:
    b = _Bancada()
    monkeypatch.setattr(vp, "make_virtual_pad", b.fabrica)
    monkeypatch.setattr(gp, "stop_gamepad_emulation", b.parar)
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
        coop_mod,
        "get_coop_manager",
        lambda d: SimpleNamespace(sync=lambda force=False, origem=None: None),
    )
    monkeypatch.setattr(launch_env, "materialize_launch_env", lambda d: None)
    em._zerar_registro_de_mascaras()
    yield b
    em._zerar_registro_de_mascaras()


def _daemon() -> _DaemonDaCasa:
    controle = FakeController(transport="bt")
    controle.primary_uniq = P1  # type: ignore[attr-defined]
    return _DaemonDaCasa(controller=controle, config=DaemonConfig())


def _gerente(d: _DaemonDaCasa) -> ProfileManager:
    """O gerente real, com o applier do modo do daemon real."""
    return ProfileManager(controller=d.controller, store=d.store, mode_applier=d.apply_profile_mode)


def _perfil(nome: str, *, mode: dict[str, Any] | None, match: Any = None) -> None:
    loader.save_profile(
        Profile(
            name=nome,
            match=match if match is not None else MatchAny(),
            mode=ProfileModeConfig(**mode) if mode is not None else None,
        ),
        origem="régua",
    )


def _modo_no_disco(nome: str) -> ProfileModeConfig | None:
    return loader.load_profile(nome).mode


def _arquivo(nome: str) -> Path:
    return profiles_dir() / f"{loader.slugify(nome)}.json"


def _sha(caminho: Path) -> str | None:
    if not caminho.exists():
        return None
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def _versoes(nome: str) -> int:
    return len(loader.listar_historico(nome))


def _pad_de_pe(d: _DaemonDaCasa, caminho: str | None) -> None:
    """O pad do P1 de pé pelo perfil, no caminho dado (a premissa)."""
    desfecho = gp.start_gamepad_emulation_desfecho(
        d, None, origin="profile", caminho=caminho
    )
    assert desfecho == gp.EMU_APLICADO, f"premissa da bancada: {desfecho}"


def _freestyle_ligado_em(d: _DaemonDaCasa, caminho: str) -> None:
    """O Modo Freestyle ligado, com o modo dele no disco, e o pad naquele caminho."""
    _perfil(FREESTYLE, mode={"kind": "gamepad", "caminho": caminho})
    ligar_o_freestyle(d.store, True)
    d.store.set_active_profile(FREESTYLE)
    _pad_de_pe(d, caminho)


def _chip(h: _Handlers, caminho: str) -> dict[str, Any]:
    """O pedido que o chip da aba Jogar manda (o passo do plano, à mão)."""
    return asyncio.run(h._handle_gamepad_emulation_set(
        {"enabled": True, "caminho": caminho, "origin": "manual"}))


def test_o_chip_grava_no_freestyle_sem_depender_da_janela(bancada: _Bancada) -> None:
    """O Freestyle ligado em Xbox: o «Sony DualSense» vai ao disco pelo daemon.

    A janela não está nesta régua de propósito: é ela que desiste aos 2,0 s, e
    o que se mede é que a escolha chega ao perfil sem ela.

    MORDIDA: tire a chamada de `gravar_o_modo_escolhido` de
    `Daemon.set_gamepad_emulation_desfecho` e o disco segue `xbox`.
    """
    d = _daemon()
    _freestyle_ligado_em(d, "xbox")
    h = _Handlers(d, _gerente(d))
    antes = _modo_no_disco(FREESTYLE)
    versoes = _versoes(FREESTYLE)
    assert antes is not None and antes.caminho == "xbox", "premissa da bancada"

    resposta = _chip(h, "dualsense")

    assert resposta["status"] == "ok", resposta
    depois = _modo_no_disco(FREESTYLE)
    assert depois is not None and (depois.kind, depois.caminho) == ("gamepad", "dualsense"), (
        f"o «Sony DualSense» trocou o pad e o Freestyle seguiu {depois!r} no disco — "
        "o achado 2 da bancada de 29/09")
    assert _versoes(FREESTYLE) == versoes + 1, (
        "a gravação não deixou a versão de antes no `.historico`")


def test_a_escolha_sobrevive_ao_ativar_e_ao_boot(bancada: _Bancada) -> None:
    """Depois do chip, o «Ativar» do Freestyle não para nem recria o pad.

    E o primeiro pad do boot nasce no modo que ela escolheu
    (`_o_modo_do_perfil_do_boot`).

    MORDIDA: a mesma da régua 1. O `profile.switch` recria o pad em Xbox (uma
    parada, e o caminho vivo volta a `xbox`), e o boot diz `xbox`.
    """
    d = _daemon()
    _freestyle_ligado_em(d, "xbox")
    h = _Handlers(d, _gerente(d))
    _chip(h, "dualsense")
    paradas = bancada.paradas

    asyncio.run(h._handle_profile_switch({"name": FREESTYLE}))

    assert bancada.paradas == paradas, (
        f"a ativação à mão do Freestyle parou o pad {bancada.paradas - paradas} vez(es): "
        "o perfil ainda dizia o modo de antes do chip")
    assert d.config.gamepad_caminho == "dualsense"
    caminho_do_boot, _mascara, nome = lifecycle._o_modo_do_perfil_do_boot(d.store)
    assert (caminho_do_boot, nome) == ("dualsense", FREESTYLE), (
        f"o boot restauraria {nome!r} em {caminho_do_boot!r}")


def test_o_modo_que_o_aparelho_recusou_nao_vai_ao_disco(bancada: _Bancada) -> None:
    """A fábrica do pad recusa: o desfecho é `falhou`, e o disco não muda."""
    d = _daemon()
    _freestyle_ligado_em(d, "xbox")
    h = _Handlers(d, _gerente(d))
    antes = _sha(_arquivo(FREESTYLE))
    versoes = _versoes(FREESTYLE)
    bancada.fabrica_recusa = True

    resposta = _chip(h, "dualsense")

    assert resposta["status"] == "failed", f"premissa: a fábrica recusou, e {resposta}"
    assert _sha(_arquivo(FREESTYLE)) == antes, (
        "o perfil gravou um modo que o aparelho não aplicou")
    assert _versoes(FREESTYLE) == versoes


def test_so_a_porta_grava_o_cartao_e_a_chamada_direta_nao(bancada: _Bancada) -> None:
    """Um perfil sem `mode`, e o pad de pé."""
    d = _daemon()
    _perfil(JOGO, mode=None)
    d.store.set_active_profile(JOGO)
    _pad_de_pe(d, None)
    antes = _sha(_arquivo(JOGO))

    assert d.vestir_a_mascara_do_aparelho(P1) in (gp.EMU_APLICADO, gp.EMU_JA_ESTAVA), (
        "premissa: o cartão do P1 passa pelo setter do pad")
    assert _modo_no_disco(JOGO) is None, "o cartão escreveu opinião de modo no perfil"

    d.aplicar_o_arranjo_do_desktop(origin="manual")
    assert _modo_no_disco(JOGO) is None, (
        "o arranjo chamado direto escreveu opinião de modo no perfil")
    assert _sha(_arquivo(JOGO)) == antes


def test_com_o_freestyle_desligado_o_perfil_do_jogo_recebe(
    bancada: _Bancada, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O Freestyle desligado, o perfil de um jogo ativo e a janela dele em foco."""
    d = _daemon()
    _perfil(FREESTYLE, mode={"kind": "gamepad", "caminho": "xbox"})
    _perfil(JOGO, mode={"kind": "gamepad", "caminho": "xbox"},
            match=MatchCriteria(window_class=[JANELA_DO_JOGO]))
    ligar_o_freestyle(d.store, False)
    d.store.set_active_profile(JOGO)
    d.store.record_window_detect_read("xlib", JANELA_DO_JOGO)
    _pad_de_pe(d, "xbox")
    flag = config_dir() / "gamepad_caminho.flag"
    freestyle_antes, flag_antes = _sha(_arquivo(FREESTYLE)), _sha(flag)
    h = _Handlers(d, _gerente(d))

    _chip(h, "dualsense")

    do_jogo = _modo_no_disco(JOGO)
    assert do_jogo is not None and do_jogo.caminho == "dualsense", (
        f"o perfil do jogo ativo não recebeu o chip: {do_jogo!r}")
    assert _sha(_arquivo(FREESTYLE)) == freestyle_antes, (
        "o chip dentro do jogo gravou no Freestyle desligado")
    assert _sha(flag) == flag_antes, "o chip dentro do jogo virou lei para todo jogo"


def test_o_nativo_a_mao_grava_native(bancada: _Bancada) -> None:
    """`native.mode.set {enabled: true, origin: "manual"}` grava `kind: native`.

    A máscara padrão do perfil fica (o modo não escreve a máscara).

    MORDIDA: tire a chamada de `gravar_o_modo_escolhido` de `set_native_mode`.
    """
    d = _daemon()
    _perfil(JOGO, mode={"kind": "gamepad", "caminho": "xbox", "gamepad_flavor": "dualsense"})
    d.store.set_active_profile(JOGO)
    _pad_de_pe(d, "xbox")
    h = _Handlers(d, _gerente(d))

    asyncio.run(h._handle_native_mode_set({"enabled": True, "origin": "manual"}))

    modo = _modo_no_disco(JOGO)
    assert modo is not None and modo.kind == "native", f"o Nativo não foi ao perfil: {modo!r}"
    assert modo.gamepad_flavor == "dualsense", "o Nativo apagou a máscara padrão do perfil"


def test_o_nativo_ja_aceso_grava_native_no_perfil_que_divergiu(bancada: _Bancada) -> None:
    """O Nativo já ligado e o perfil dizendo `gamepad`: o clique à mão conserta o perfil.

    É o `ja_estava` do Nativo: o setter volta cedo (nada a trocar no aparelho),
    e a escolha dela vai ao perfil do mesmo jeito, como o chip aceso faz com o
    caminho. Sem isto, o «Desligado» aceso clicado de novo deixaria o perfil
    dizendo o modo de antes, e o boot o seguiria.

    MORDIDA: tire a chamada de `gravar_o_modo_escolhido` do ramo idempotente de
    `set_native_mode` (o `if enabled == self._native_mode`) e o perfil segue
    `gamepad`.
    """
    d = _daemon()
    _perfil(JOGO, mode={"kind": "gamepad", "caminho": "xbox"})
    d.store.set_active_profile(JOGO)
    d.set_native_mode(True, origin="profile")
    assert d.is_native_mode() is True, "premissa: o Nativo já está ligado"
    assert _modo_no_disco(JOGO).kind == "gamepad", "premissa: o perfil divergiu"  # type: ignore[union-attr]
    h = _Handlers(d, _gerente(d))

    asyncio.run(h._handle_native_mode_set({"enabled": True, "origin": "manual"}))

    modo = _modo_no_disco(JOGO)
    assert modo is not None and modo.kind == "native", (
        f"o clique no Nativo aceso deixou o perfil dizendo {modo!r}")


def test_a_navegacao_a_mao_grava_desktop(bancada: _Bancada) -> None:
    """`desktop.arranjo.apply {origin: "manual"}` grava `kind: desktop`.

    O caminho vai a `null` (a Navegação não diz por qual canal o pad sobe), e o
    `gamepad_flavor` fica.

    MORDIDA: tire a chamada de `gravar_o_modo_escolhido` de
    `aplicar_o_arranjo_do_desktop`.
    """
    d = _daemon()
    _perfil(JOGO, mode={"kind": "gamepad", "caminho": "xbox", "gamepad_flavor": "dualsense"})
    d.store.set_active_profile(JOGO)
    h = _Handlers(d, _gerente(d))

    asyncio.run(h._handle_desktop_arranjo_apply({"origin": "manual"}))

    modo = _modo_no_disco(JOGO)
    assert modo is not None and modo.kind == "desktop", f"a Navegação não foi ao perfil: {modo!r}"
    assert modo.caminho is None
    assert modo.gamepad_flavor == "dualsense", "a Navegação apagou a máscara padrão do perfil"


def test_ligar_sem_caminho_saindo_do_nativo_grava_gamepad(bancada: _Bancada) -> None:
    """O interruptor «Ligado» saindo do Nativo: `kind: gamepad`, e o caminho fica.

    O pedido não escolhe caminho, e o perfil (que dizia Nativo) não opina sobre
    o canal: o escritor grava o `kind` e deixa o `caminho` que a seção tinha.

    MORDIDA: tire a chamada de `gravar_o_modo_escolhido` de
    `set_gamepad_emulation_desfecho`, e o perfil segue `native`.
    """
    d = _daemon()
    _perfil(JOGO, mode={"kind": "native", "caminho": "xbox"})
    d.store.set_active_profile(JOGO)
    d.set_native_mode(True, origin="profile")
    h = _Handlers(d, _gerente(d))

    asyncio.run(h._handle_gamepad_emulation_set({"enabled": True, "origin": "manual"}))

    assert d.is_native_mode() is False, "premissa: o pedido saiu do Nativo"
    modo = _modo_no_disco(JOGO)
    assert modo is not None and (modo.kind, modo.caminho) == ("gamepad", "xbox"), (
        f"o «Ligado» saindo do Nativo gravou {modo!r}")


def test_desligar_o_pad_e_sair_do_nativo_nao_gravam(bancada: _Bancada) -> None:
    """Quem grava é o modo que ENTRA: os passos que saem não escrevem nada."""
    d = _daemon()
    _perfil(JOGO, mode=None)
    d.store.set_active_profile(JOGO)
    _pad_de_pe(d, "xbox")
    h = _Handlers(d, _gerente(d))

    asyncio.run(h._handle_native_mode_set({"enabled": False, "origin": "manual"}))
    asyncio.run(h._handle_gamepad_emulation_set({"enabled": False, "origin": "manual"}))

    assert _modo_no_disco(JOGO) is None


def _chamadas(arvore: ast.AST, nome: str) -> list[int]:
    linhas = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Call):
            alvo = no.func
            chamado = (alvo.id if isinstance(alvo, ast.Name)
                       else alvo.attr if isinstance(alvo, ast.Attribute) else "")
            if chamado == nome:
                linhas.append(no.lineno)
    return linhas


def _arvores(pasta: Path) -> Iterator[tuple[Path, ast.AST]]:
    for py in sorted(pasta.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        yield py, ast.parse(py.read_text(encoding="utf-8"))


def test_o_escritor_do_modo_e_um_so() -> None:
    """`gravar_o_modo_no_perfil_ativo` tem UM chamador no produto: o do daemon."""
    chamadores = [
        f"{py.relative_to(SRC)}:{linha}"
        for py, arvore in _arvores(SRC)
        for linha in _chamadas(arvore, "gravar_o_modo_no_perfil_ativo")
    ]
    assert len(chamadores) == 1 and chamadores[0].startswith("daemon/lifecycle.py:"), (
        f"o modo escolhido tem mais de um escritor, ou nenhum: {chamadores}")

    escritores: list[str] = []
    for py, arvore in _arvores(SRC / "interface"):
        onde = py.relative_to(SRC)
        for nome in ("secao_do_modo_com_o_caminho", "ProfileModeConfig"):
            escritores += [f"{onde}:{linha} chama {nome}" for linha in _chamadas(arvore, nome)]
        for no in ast.walk(arvore):
            if isinstance(no, ast.Assign | ast.AnnAssign | ast.AugAssign):
                alvos = no.targets if isinstance(no, ast.Assign) else [no.target]
                for alvo in alvos:
                    if isinstance(alvo, ast.Attribute) and alvo.attr == "mode":
                        escritores.append(f"{onde}:{no.lineno} atribui `.mode`")
    assert not escritores, (
        "a janela voltou a escrever a seção `mode` do perfil — quem grava o modo "
        "é o daemon, depois do aparelho:\n  " + "\n  ".join(escritores))


def _gravacoes(registros: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """`(porta, origem do profile_salvo)` de cada gravação do modo, na ordem."""
    portas = [r.get("porta") for r in registros
              if r.get("event") == "modo_escolhido_gravado_no_perfil"]
    origens = [r.get("origem") for r in registros if r.get("event") == "profile_salvo"]
    return list(zip(portas, origens, strict=False))


def test_o_diario_diz_por_qual_porta_o_modo_chegou(bancada: _Bancada) -> None:
    """O clique pelo IPC grava com `porta=ipc`; o PS + R3, com `porta=controle`."""
    d = _daemon()
    _freestyle_ligado_em(d, "xbox")
    h = _Handlers(d, _gerente(d))

    with structlog.testing.capture_logs() as registros:
        _chip(h, "dualsense")
    assert _gravacoes(registros) == [("ipc", "ipc")], (
        f"o clique no chip não disse a porta dele: {_gravacoes(registros)}")

    with structlog.testing.capture_logs() as registros:
        assert hotkey._aplicar_ponte(d, hotkey.PONTE_XBOX) is True
    assert _gravacoes(registros) == [("controle", "controle")], (
        f"o PS + R3 não disse a porta dele: {_gravacoes(registros)}")
    modo = _modo_no_disco(FREESTYLE)
    assert modo is not None and modo.caminho == "xbox"


def test_o_salvar_logo_depois_do_chip_nao_devolve_o_modo_velho(
    bancada: _Bancada, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O Freestyle em Xbox no disco; o «Salvar» antes do chip e depois dele."""
    from hefesto_dualsense4unix.interface.pacotes import perfil as pacote_perfil
    from hefesto_dualsense4unix.interface.pacotes import rodape

    monkeypatch.setattr(pacote_perfil, "com_a_carona", lambda frase="": "")
    d = _daemon()
    _freestyle_ligado_em(d, "xbox")
    h = _Handlers(d, _gerente(d))
    ctx = SimpleNamespace(state={"active_profile": FREESTYLE})

    rodape.salvar(ctx, {}, PonteDoRodape())
    assert _modo_no_disco(FREESTYLE).caminho == "xbox", "premissa: o Salvar antes do chip"  # type: ignore[union-attr]

    _chip(h, "dualsense")
    rodape.salvar(ctx, {}, PonteDoRodape())

    modo = _modo_no_disco(FREESTYLE)
    assert modo is not None and (modo.kind, modo.caminho) == ("gamepad", "dualsense"), (
        f"o «Salvar» logo depois do chip devolveu {modo!r} ao disco")


@pytest.mark.parametrize("pad_da_maquina", [True, False])
def test_o_perfil_sem_modo_nao_derruba_o_pad_que_a_maquina_deixa_ligado(
    bancada: _Bancada, pad_da_maquina: bool
) -> None:
    """O Freestyle (gamepad) valendo, e ela ativa à mão um jogo sem `mode`."""
    from hefesto_dualsense4unix.utils.session import save_gamepad_emulation

    save_gamepad_emulation(pad_da_maquina, "dualsense")
    d = _daemon()
    _perfil(FREESTYLE, mode={"kind": "gamepad", "caminho": "dualsense"})
    _perfil(JOGO, mode=None, match=MatchCriteria(window_class=[JANELA_DO_JOGO]))
    h = _Handlers(d, _gerente(d))
    asyncio.run(h._handle_profile_switch({"name": FREESTYLE}))
    assert d._gamepad_device is not None, "premissa: o Freestyle ligou o pad"
    paradas = bancada.paradas

    asyncio.run(h._handle_profile_switch({"name": JOGO}))

    if pad_da_maquina:
        assert bancada.paradas == paradas and d._gamepad_device is not None, (
            "o perfil sem `mode` derrubou o pad que a preferência dela deixa ligado: "
            "o controle caiu no mouse e teclado (22:40:34 de 01/10)")
        assert d.config.gamepad_emulation_enabled is True
    else:
        assert d._gamepad_device is None, (
            "com o pad desligado de propósito, a reversão de sempre não desligou")
