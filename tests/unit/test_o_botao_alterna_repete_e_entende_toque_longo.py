#!/usr/bin/env python3
"""O botão alterna, repete e entende o toque longo e o duplo (acessibilidade, 16/10/2026).

O motor puro (`core/ativacao_de_botao.py`) com tempo falso; os dois caminhos do pad virtual
(`gamepad.dispatch_gamepad` do P1 e `coop.forward_all` de P2 a P4); a tabela de teclas com o
jogo; o depósito pela ativação do perfil e a soltura na troca.

A MORDIDA, e cada uma foi rodada na entrega:

- tire a chamada `ativar_o_botao` de `coop.forward_all` e
  :func:`test_o_segundo_jogador_alterna_sem_mexer_no_primeiro` reprova;
- tire a chamada de `gamepad.dispatch_gamepad` e :func:`test_o_primeiro_alterna_entre_os_toques`
  reprova;
- tire o `esquecer` de `definir_ativo` e :func:`test_o_perfil_seguinte_solta_o_botao_preso` reprova;
- troque o `>=` do limiar do longo por `>` e :func:`test_o_longo_vale_no_instante_exato`
  reprova.
"""
from __future__ import annotations

import ast
import itertools
import pathlib
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import ativacao_de_botao as ab

RAIZ = pathlib.Path(__file__).resolve().parents[2]
F = frozenset
P2 = "aabbcc000002"


def _rodar(
    ativacao: ab.Ativacao, quadros: list[tuple[set[str], int, int]], passo: float = 0.01
) -> list[tuple[float, frozenset[str], int, int]]:
    """Cada quadro `(botões, l2, r2)` um passo depois do outro; devolve `(t, botões, l2, r2)`."""
    estado = ab.AtivacaoDoControle()
    saida = []
    t = 100.0
    for botoes, l2, r2 in quadros:
        b, a, c, _ = estado.passo(ativacao, F(botoes), l2, r2, t)
        saida.append((round(t - 100.0, 4), b, a, c))
        t += passo
    return saida


def _bordas(saida: list[tuple[float, frozenset[str], int, int]], botao: str, de: float = 0.0,
            ate: float = 1e9) -> int:
    n = 0
    for (_, antes, _, _), (t, agora, _, _) in itertools.pairwise(saida):
        if de <= t < ate and botao in agora and botao not in antes:
            n += 1
    return n


def test_alternar_segura_no_primeiro_toque_e_solta_no_segundo() -> None:
    ativacao = ab.Ativacao(alternar=F({"l1"}))
    toque, solto = ({"l1"}, 0, 0), (set(), 0, 0)
    quadros = [toque] * 3 + [solto] * 5 + [toque] * 3 + [solto] * 3
    visto = [("l1" in b) for _, b, _, _ in _rodar(ativacao, quadros)]
    assert visto == [True] * 8 + [False] * 6, f"o jogo viu {visto}"


def test_o_toque_entre_dois_tiques_tambem_alterna() -> None:
    estado = ab.AtivacaoDoControle()
    ativacao = ab.Ativacao(alternar=F({"cross"}))
    b, _, _, resto = estado.passo(ativacao, F(), 0, 0, 10.0, F({"cross", "square"}))
    assert b == F({"cross"}), "o toque que veio e foi entre dois tiques não ligou o alternar"
    assert resto == F({"square"}), "o toque de outro botão deve seguir o caminho de antes"
    b, _, _, _ = estado.passo(ativacao, F(), 0, 0, 10.01, F({"cross"}))
    assert b == F()


def test_repetir_da_seis_bordas_em_um_segundo_depois_do_atraso() -> None:
    ativacao = ab.Ativacao(repetir=F({"cross"}))
    saida = _rodar(ativacao, [({"cross"}, 0, 0)] * 160)
    assert "cross" in saida[0][1], "o primeiro aperto tem de chegar logo"
    assert all("cross" in b for t, b, _, _ in saida if t < 0.5), "antes do atraso, segura"
    assert _bordas(saida, "cross", de=0.5, ate=1.5) == 6


def test_repetir_solta_com_o_botao() -> None:
    ativacao = ab.Ativacao(repetir=F({"cross"}))
    saida = _rodar(ativacao, [({"cross"}, 0, 0)] * 80 + [(set(), 0, 0)] * 30)
    assert all("cross" not in b for t, b, _, _ in saida if t > 0.85)


def test_o_longo_dispara_aos_800_e_nao_aos_790() -> None:
    ativacao = ab.Ativacao(longo={"cross": "circle"}, longo_s=0.8)
    saida = _rodar(ativacao, [({"cross"}, 0, 0)] * 100)
    antes = [b for t, b, _, _ in saida if t < 0.8]
    assert all("circle" not in b and "cross" not in b for b in antes)
    primeiro = next(t for t, b, _, _ in saida if "circle" in b)
    assert primeiro == 0.8, f"o longo disparou aos {primeiro} s"


def test_o_longo_vale_no_instante_exato() -> None:
    """Passos de 0,25 s são exatos em binário: no 0,5 s do limiar não há ruído de float."""
    ativacao = ab.Ativacao(longo={"cross": "circle"}, longo_s=0.5)
    saida = _rodar(ativacao, [({"cross"}, 0, 0)] * 4, passo=0.25)
    assert ["circle" in b for _, b, _, _ in saida] == [False, False, True, True]


def test_o_toque_curto_continua_sendo_do_proprio_botao() -> None:
    ativacao = ab.Ativacao(longo={"cross": "circle"}, longo_s=0.8)
    saida = _rodar(ativacao, [({"cross"}, 0, 0)] * 10 + [(set(), 0, 0)] * 30)
    vistos = {n for _, b, _, _ in saida for n in b}
    assert vistos == {"cross"}, f"o toque curto virou {vistos}"


def test_o_duplo_dentro_da_janela_dispara_o_destino() -> None:
    ativacao = ab.Ativacao(duplo={"cross": "triangle"}, duplo_s=0.3)
    quadros = ([({"cross"}, 0, 0)] * 5 + [(set(), 0, 0)] * 10 + [({"cross"}, 0, 0)] * 5
               + [(set(), 0, 0)] * 40)
    vistos = {n for _, b, _, _ in _rodar(ativacao, quadros) for n in b}
    assert "triangle" in vistos and "cross" not in vistos, vistos


def test_o_duplo_fora_da_janela_vira_dois_curtos() -> None:
    ativacao = ab.Ativacao(duplo={"cross": "triangle"}, duplo_s=0.3)
    quadros = ([({"cross"}, 0, 0)] * 5 + [(set(), 0, 0)] * 50 + [({"cross"}, 0, 0)] * 5
               + [(set(), 0, 0)] * 50)
    saida = _rodar(ativacao, quadros)
    assert all("triangle" not in b for _, b, _, _ in saida)
    assert _bordas(saida, "cross") == 2, "os dois toques fora da janela são dois curtos"


def test_o_gatilho_alternado_chega_com_a_forca_cheia() -> None:
    ativacao = ab.Ativacao(alternar=F({"l2"}))
    saida = _rodar(ativacao, [(set(), 200, 0)] * 2 + [(set(), 0, 0)] * 3)
    _, b, l2, _ = saida[-1]
    assert b == F({"l2_btn"}) and l2 == 255, (b, l2)
    assert saida[0][1] == F({"l2_btn"}), "o gatilho apertado pelo curso conta como aperto"


def test_o_laco_parado_esquece_o_estado() -> None:
    estado = ab.AtivacaoDoControle()
    ativacao = ab.Ativacao(alternar=F({"l1"}))
    assert estado.passo(ativacao, F({"l1"}), 0, 0, 5.0)[0] == F({"l1"})
    assert estado.passo(ativacao, F(), 0, 0, 5.01)[0] == F({"l1"})
    assert estado.passo(ativacao, F(), 0, 0, 9.0)[0] == F(), "um tropeço do laço deixou preso"


def test_um_botao_um_modo() -> None:
    assert ab.recusar(["cross"], ["cross"], {}, {}) is not None
    assert ab.recusar(["cross"], [], {"cross": "circle"}, {}) is not None
    assert ab.recusar([], [], {"cross": "cross"}, {}) is not None
    assert ab.recusar(["ps"], [], {}, {}) is not None
    assert ab.recusar(["cross"], ["circle"], {"l1": "r1"}, {"l2": "r2"}) is None


def test_a_peca_sobrepoe_campo_a_campo() -> None:
    perfil = SimpleNamespace(alternar=["l1"], longo_ms=800)
    peca = SimpleNamespace(repetir=["cross"])
    montado = ab.montar(perfil, peca)
    assert montado is not None
    assert montado.alternar == F({"l1"}) and montado.repetir == F({"cross"})
    assert montado.longo_s == 0.8
    assert ab.montar(None) is None and ab.montar(SimpleNamespace(alternar=[])) is None


def test_os_numeros_do_motor_sao_os_do_cursor_e_os_do_perfil() -> None:
    from hefesto_dualsense4unix.integrations.uinput_mouse import TRIGGER_PRESS_THRESHOLD
    from hefesto_dualsense4unix.profiles.schema import ProfileAtivacaoConfig as C

    assert ab.LIMIAR_DO_GATILHO == TRIGGER_PRESS_THRESHOLD
    f = C.model_fields
    assert f["longo_ms"].default == int(ab.LONGO_S * 1000)
    assert f["duplo_ms"].default == int(ab.DUPLO_S * 1000)
    assert f["repete_apos_ms"].default == int(ab.REPETE_APOS_S * 1000)
    assert f["repete_por_segundo"].default == ab.REPETE_POR_SEGUNDO
    assert (f["longo_ms"].metadata[0].ge, f["longo_ms"].metadata[1].le) == ab.FAIXA_DO_LONGO_MS


class _Device:
    def __init__(self) -> None:
        self.analog: list[dict[str, int]] = []
        self.buttons: list[frozenset[str]] = []

    def forward_analog(self, **kw: int) -> None:
        self.analog.append(kw)

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        self.buttons.append(pressed)


def _estado(l2: int = 0, r2: int = 0) -> Any:
    return SimpleNamespace(raw_lx=128, raw_ly=128, raw_rx=128, raw_ry=128, l2_raw=l2, r2_raw=r2)


def _o_primeiro(monkeypatch: pytest.MonkeyPatch, store: Any) -> Any:
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    relogio = [200.0]
    monkeypatch.setattr(gp, "_agora", lambda: relogio[0])
    dev = _Device()
    daemon = SimpleNamespace(store=store, _gamepad_device=dev)

    def tique(botoes: set[str], l2: int = 0, r2: int = 0, passo: float = 0.01) -> None:
        relogio[0] += passo
        gp.dispatch_gamepad(daemon, _estado(l2, r2), F(botoes))

    return SimpleNamespace(dev=dev, tique=tique)


def test_o_primeiro_alterna_entre_os_toques(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    ab.definir_ativo(store, ab.Ativacao(alternar=F({"l1"})))
    p1 = _o_primeiro(monkeypatch, store)
    p1.tique({"l1"})
    p1.tique(set())
    p1.tique(set())
    assert p1.dev.buttons[-1] == F({"l1"}), "o jogo devia ver o L1 segurado depois de soltar"
    p1.tique({"l1"})
    p1.tique(set())
    assert p1.dev.buttons[-1] == F(), "o segundo toque devia soltar"


def test_sem_modo_o_jogo_recebe_o_mesmo_objeto(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    p1 = _o_primeiro(monkeypatch, store)
    apertados = F({"cross", "l1"})
    p1.dev.buttons.clear()
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

    gp.dispatch_gamepad(SimpleNamespace(store=store, _gamepad_device=p1.dev), _estado(), apertados)
    assert p1.dev.buttons[-1] is apertados


def test_o_gatilho_do_primeiro_alterna_com_a_forca_cheia(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    ab.definir_ativo(store, ab.Ativacao(alternar=F({"r2"})))
    p1 = _o_primeiro(monkeypatch, store)
    p1.tique(set(), r2=255)
    p1.tique(set(), r2=0)
    assert p1.dev.analog[-1]["r2"] == 255 and "r2_btn" in p1.dev.buttons[-1]


def _o_segundo(store: Any, snap: Any) -> tuple[Any, _Device]:
    from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer

    daemon = SimpleNamespace(
        store=store, controller=SimpleNamespace(), identity_registry=None,
        config=SimpleNamespace(coop_enabled=True, gamepad_flavor="dualsense"),
        _gamepad_device=object(), _coop_manager=None)
    mgr = CoopManager(daemon)
    vpad = _Device()
    leitor = SimpleNamespace(grab_state="held", snapshot=lambda: snap)
    mgr._players[P2] = _SecondaryPlayer(
        identity=P2, evdev_path="/dev/input/event9", reader=leitor, player_index=2,
        vpad=vpad)  # type: ignore[arg-type]
    return mgr, vpad


def _foto(botoes: set[str], l2: int = 0) -> Any:
    return SimpleNamespace(lx=1, ly=2, rx=3, ry=4, l2_raw=l2, r2_raw=0,
                           buttons_pressed=F(botoes))


def test_o_segundo_jogador_alterna_sem_mexer_no_primeiro(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prova da D-1610-O-BOTAO-ALTERNA-REPETE-LONGO-E-DUPLO-COM-OS-NUMEROS-DE-FABRICA."""
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    ab.definir_ativo(store, None, {P2: ab.Ativacao(alternar=F({"l2"}))})
    relogio = [300.0]
    monkeypatch.setattr(gp, "_agora", lambda: relogio[0])
    snap = _foto({"l2_btn"}, 200)
    mgr, vpad = _o_segundo(store, snap)
    mgr.forward_all()
    snap.buttons_pressed, snap.l2_raw = F(), 0
    relogio[0] += 0.01
    mgr.forward_all()
    assert vpad.buttons[-1] == F({"l2_btn"}) and vpad.analog[-1]["l2"] == 255, (
        f"o jogador 2 soltou o gatilho: {vpad.buttons[-1]}")
    p1 = _o_primeiro(monkeypatch, store)
    p1.tique({"l2_btn"}, l2=200)
    p1.tique(set(), l2=0)
    assert p1.dev.buttons[-1] == F(), "o gatilho do jogador 1 ficou preso pelo modo do 2"
    assert p1.dev.analog[-1]["l2"] == 0


def test_o_segundo_jogador_sem_modo_passa_o_mesmo(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    ab.definir_ativo(store, ab.Ativacao(alternar=F({"l1"})), {P2: None})
    mgr, vpad = _o_segundo(store, _foto({"cross"}))
    mgr.forward_all()
    assert vpad.buttons[-1] == F({"cross"})


def test_o_perfil_seguinte_solta_o_botao_preso(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles import manager as gerente
    from hefesto_dualsense4unix.profiles.schema import Profile

    store = StateStore()
    m = gerente.ProfileManager(controller=SimpleNamespace(), store=store)  # type: ignore[arg-type]
    for nome_do_metodo in ("apply", "apply_keyboard", "apply_button_actions", "apply_emulation"):
        monkeypatch.setattr(m, nome_do_metodo, lambda *a, **k: None)
    com = Profile.model_validate({
        "name": "Com Alternar", "match": {"type": "any"},
        "ativacao": {"alternar": ["l1"]}})  # (noqa-acento)
    sem = Profile.model_validate({"name": "Sem Alternar", "match": {"type": "any"}})
    monkeypatch.setattr(gerente, "load_profile", lambda nome: com)
    relatorio: dict[str, str] = {}
    m.activate("Com Alternar", origin="system", relatorio=relatorio)
    assert relatorio["acessibilidade"] == "aplicado"
    p1 = _o_primeiro(monkeypatch, store)
    p1.tique({"l1"})
    p1.tique(set())
    assert p1.dev.buttons[-1] == F({"l1"})
    assert ab.preso(store, None)
    monkeypatch.setattr(gerente, "load_profile", lambda nome: sem)
    m.activate("Sem Alternar", origin="system")
    assert not ab.preso(store, None), "o perfil seguinte deixou o L1 preso"
    p1.tique(set())
    assert p1.dev.buttons[-1] == F(), "o jogo ainda via o L1 do perfil anterior"


def test_parar_o_pad_ou_a_sessao_do_jogador_solta(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

    store = SimpleNamespace()
    ab.definir_ativo(store, ab.Ativacao(alternar=F({"l1"})))
    estado = ab.AtivacaoDoControle()
    estado.passo(ab.Ativacao(alternar=F({"l1"})), F({"l1"}), 0, 0, 1.0)
    store._ativacao_de_botao_estados = {("", P2): estado, ("", "ff"): ab.AtivacaoDoControle()}
    daemon = SimpleNamespace(store=store, controller=SimpleNamespace())
    gp.end_game_output_session(daemon, target_uniq=P2)  # type: ignore[arg-type]
    assert list(store._ativacao_de_botao_estados) == [("", "ff")]
    gp.soltar_a_ativacao(daemon)
    assert not store._ativacao_de_botao_estados


def test_a_tabela_com_o_jogo_alterna_por_controle(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.subsystems import mouse

    relogio = [50.0]
    monkeypatch.setattr(mouse, "_agora", lambda: relogio[0])
    store = SimpleNamespace()
    ab.definir_ativo(store, ab.Ativacao(alternar=F({"l1"})))
    tabela = mouse.TabelaNoJogo(None, None, ligada=True)
    visto: list[frozenset[str]] = []
    tabela._mouse = SimpleNamespace(dispatch=lambda **kw: visto.append(kw["buttons"]))
    tabela._teclado = SimpleNamespace(dispatch=lambda b: None)
    daemon = SimpleNamespace(store=store, controller=SimpleNamespace(primary_uniq=None))
    for botoes in ({"l1"}, set(), set()):
        relogio[0] += 0.01
        tabela.tick(daemon, _estado(), F(botoes))
    assert visto[-1] == F({"l1"}), f"a tabela viu {visto[-1]} com o L1 solto"
    tabela.soltar()
    assert not ab.preso(store, None), "soltar a tabela deixou o L1 preso"


def _chama(arquivo: str, funcao: str, nome: str) -> bool:
    caminho = RAIZ / "src/hefesto_dualsense4unix/daemon/subsystems" / arquivo
    arvore = ast.parse(caminho.read_text())
    for no in ast.walk(arvore):
        if isinstance(no, ast.FunctionDef) and no.name == funcao:
            return any(
                isinstance(c, ast.Call) and getattr(c.func, "id", None) == nome
                for c in ast.walk(no))
    return False


def test_os_dois_caminhos_chamam_o_dono_unico() -> None:
    assert _chama("gamepad.py", "dispatch_gamepad", "ativar_o_botao")
    assert _chama("coop.py", "forward_all", "ativar_o_botao")


def test_perfil_sem_a_secao_nao_grava_a_chave_e_com_ela_volta_igual() -> None:
    from hefesto_dualsense4unix.profiles.schema import Profile

    vazio = Profile.model_validate({"name": "Vazio", "match": {"type": "any"}})
    assert "ativacao" not in vazio.model_dump(mode="json")  # (noqa-acento)
    cheio = Profile.model_validate({
        "name": "Cheio", "match": {"type": "any"},
        "ativacao": {"longo": {"cross": "circle"}, "longo_ms": 800},  # (noqa-acento)
        "controllers": {P2: {"ativacao": {"repetir": ["l1"]}}}})  # (noqa-acento)
    volta = Profile.model_validate(cheio.model_dump(mode="json"))
    assert volta.ativacao is not None and volta.ativacao.longo_ms == 800
    assert volta.controllers is not None and volta.controllers[P2].ativacao is not None


@pytest.mark.parametrize("secao", [
    {"alternar": ["botao_que_nao_existe"]},
    {"alternar": ["l1"], "repetir": ["l1"]},
    {"longo": {"cross": "cross"}},
    {"longo_ms": 10},
    {"repete_por_segundo": 99},
    {"campo_novo": 1},
])
def test_o_perfil_recusa_a_ativacao_que_o_motor_recusa(secao: dict[str, Any]) -> None:
    from pydantic import ValidationError

    from hefesto_dualsense4unix.profiles.schema import Profile

    with pytest.raises(ValidationError):
        Profile.model_validate({
            "name": "X", "match": {"type": "any"},
            "ativacao": secao})  # (noqa-acento)
