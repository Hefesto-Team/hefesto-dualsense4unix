#!/usr/bin/env python3
"""O remapeamento vale por jogador (O-REMAPEAMENTO-VALE-POR-JOGADOR-01, 20/10/2026).

A troca de botões tem dono por controle (`ControllerOverrides.remapeamento`), juntada à do perfil
(`core/remapeamento_de_botao.juntar`) e aplicada nos DOIS caminhos do pad virtual: o do primeiro
controle (`gamepad.dispatch_gamepad`) e o dos outros (`coop.forward_all`). O jogo manda: nada aqui
veta a saída dele, só troca o que o botão do controle diz.

A MORDIDA, e cada uma foi rodada na entrega:

- ponha o mapa da peça no mapa do perfil inteiro (`apply_remapeamento` sem `por_peca`) e
  :func:`test_a_troca_de_um_controle_nao_vaza_para_o_outro` reprova;
- tire o `juntar` de `apply_remapeamento` e :func:`test_o_perfil_deposita_a_troca_de_cada_peca`
  reprova;
- volte `coop.forward_all` ao mapa do perfil e
  :func:`test_a_troca_de_um_controle_nao_vaza_para_o_outro` reprova;
- volte `gamepad.dispatch_gamepad` ao mapa do perfil e
  :func:`test_o_primeiro_controle_tem_a_troca_dele` reprova;
- guarde pelo mapa sem o controle escolhido (`_aplicar_as_edicoes(..., None)`) e
  :func:`test_guardar_com_o_white_escolhido_grava_so_no_white` reprova;
- faça a linha ignorar a troca da peça e
  :func:`test_a_linha_mostra_a_troca_do_controle_escolhido_com_a_do_perfil_por_baixo` reprova;
- deixe a troca de controle não largar a edição e
  :func:`test_trocar_de_controle_largar_a_edicao_que_nao_se_guardou` reprova;
- tire o cancelamento `botão: botão` e
  :func:`test_soltar_no_controle_a_troca_do_perfil_cancela_so_nele` reprova.
"""
from __future__ import annotations

import ast
import pathlib
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.core import remapeamento_de_botao as remap

RAIZ = pathlib.Path(__file__).resolve().parents[2]
F = frozenset
P1 = "aabbcc000001"
P2 = "aabbcc000002"
P3 = "aabbcc000003"


# -- o motor -------------------------------------------------------------------


def test_sem_troca_propria_o_controle_segue_a_do_perfil() -> None:
    store = SimpleNamespace()
    remap.definir_ativo(store, {"cross": "circle"}, {P2: {"l1": "r1"}})
    assert remap.da_peca(store, P1) == {"cross": "circle"}
    assert remap.da_peca(store, P3) == {"cross": "circle"}
    assert remap.da_peca(store, P2) == {"l1": "r1"}


def test_a_identidade_do_controle_casa_por_hex_e_maiuscula() -> None:
    store = SimpleNamespace()
    remap.definir_ativo(store, None, {"AA:BB:CC:00:00:02": {"l1": "r1"}})
    assert remap.da_peca(store, P2) == {"l1": "r1"}
    assert remap.da_peca(store, P1) is None


def test_a_peca_sobrepoe_o_perfil_botao_a_botao() -> None:
    do_perfil = {"cross": "circle", "l1": "r1"}
    assert remap.juntar(do_perfil, {"square": "triangle"}) == {
        "cross": "circle", "l1": "r1", "square": "triangle"}
    assert remap.juntar(do_perfil, {"cross": "square"}) == {"cross": "square", "l1": "r1"}


def test_botao_igual_a_si_cancela_a_troca_do_perfil_so_nesta_peca() -> None:
    assert remap.juntar({"cross": "circle", "l1": "r1"}, {"cross": "cross"}) == {"l1": "r1"}
    assert remap.juntar(None, {"cross": "cross"}) == {}


def test_se_a_soma_recusa_vale_so_a_da_peca() -> None:
    # o perfil manda o Cruz para o Círculo; a peça manda o Quadrado também: dois no mesmo destino
    assert remap.juntar({"cross": "circle"}, {"square": "circle"}) == {"square": "circle"}


def test_a_troca_da_peca_recusa_o_que_o_motor_recusa() -> None:
    with pytest.raises(remap.RemapeamentoRecusadoError) as ps:
        remap.resolver_da_peca({"cross": "ps"})
    assert ps.value.motivo == remap.MOTIVO_PS
    with pytest.raises(remap.RemapeamentoRecusadoError) as cancela_ps:
        remap.resolver_da_peca({"ps": "ps"})
    assert cancela_ps.value.motivo == remap.MOTIVO_PS
    with pytest.raises(remap.RemapeamentoRecusadoError) as colisao:
        remap.resolver_da_peca({"cross": "circle", "square": "circle"})
    assert colisao.value.motivo == remap.MOTIVO_COLISAO
    with pytest.raises(remap.RemapeamentoRecusadoError) as nome:
        remap.resolver_da_peca({"botao_que_nao_existe": "botao_que_nao_existe"})
    assert nome.value.motivo == remap.MOTIVO_DESCONHECIDO


# -- o perfil ------------------------------------------------------------------


def _perfil(**campos: Any) -> Any:
    from hefesto_dualsense4unix.profiles.schema import Profile

    return Profile.model_validate({"name": "Dois Jogadores", "match": {"type": "any"}, **campos})


def test_perfil_sem_a_troca_da_peca_carrega_e_grava_igual() -> None:
    velho = _perfil(controllers={P2: {"mascara": None}})
    assert velho.controllers is not None
    assert velho.controllers[P2].remapeamento is None
    assert "remapeamento" not in velho.model_dump(mode="json")["controllers"][P2]
    assert "remapeamento" not in _perfil().model_dump(mode="json")


def test_a_troca_da_peca_ida_e_volta() -> None:
    p = _perfil(controllers={P2: {"remapeamento": {"cross": "circle", "l1": "l1"}}})
    assert p.controllers is not None
    assert p.controllers[P2].remapeamento == {"cross": "circle", "l1": "l1"}
    de_novo = _perfil(**p.model_dump(mode="json"))
    assert de_novo.controllers is not None
    assert de_novo.controllers[P2].remapeamento == {"cross": "circle", "l1": "l1"}


@pytest.mark.parametrize("troca", [{"cross": "ps"}, {"cross": "circle", "square": "circle"},
                                   {"cross": "xyz"}])
def test_o_perfil_recusa_a_troca_da_peca_que_o_motor_recusa(troca: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        _perfil(controllers={P2: {"remapeamento": troca}})


def _gerente(monkeypatch: pytest.MonkeyPatch, store: Any, perfil: Any) -> Any:
    from hefesto_dualsense4unix.profiles import manager as gerente

    m = gerente.ProfileManager(controller=SimpleNamespace(), store=store)  # type: ignore[arg-type]
    for nome_do_metodo in ("apply", "apply_keyboard", "apply_button_actions", "apply_emulation"):
        monkeypatch.setattr(m, nome_do_metodo, lambda *a, **k: None)
    monkeypatch.setattr(gerente, "load_profile", lambda nome: perfil)
    return m


def test_o_perfil_deposita_a_troca_de_cada_peca(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.state_store import StateStore

    store = StateStore()
    perfil = _perfil(
        remapeamento={"cross": "circle", "l1": "r1"},
        controllers={P2: {"remapeamento": {"cross": "cross", "square": "triangle"}}})
    m = _gerente(monkeypatch, store, perfil)
    relatorio: dict[str, str] = {}
    m.activate("Dois Jogadores", origin="system", relatorio=relatorio)
    assert relatorio["remapeamento"] == "aplicado"
    assert remap.da_peca(store, P1) == {"cross": "circle", "l1": "r1"}
    assert remap.da_peca(store, P2) == {"l1": "r1", "square": "triangle"}


def test_so_a_peca_troca_e_o_perfil_nao(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.state_store import StateStore

    store = StateStore()
    m = _gerente(monkeypatch, store, _perfil(
        controllers={P2: {"remapeamento": {"cross": "circle"}}}))
    relatorio: dict[str, str] = {}
    m.activate("Dois Jogadores", origin="system", relatorio=relatorio)
    assert relatorio["remapeamento"] == "aplicado"
    assert remap.da_peca(store, P1) is None
    assert remap.da_peca(store, P2) == {"cross": "circle"}


def test_o_perfil_seguinte_larga_a_troca_da_peca(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles import manager as gerente

    store = StateStore()
    m = _gerente(monkeypatch, store, _perfil(
        controllers={P2: {"remapeamento": {"cross": "circle"}}}))
    m.activate("Dois Jogadores", origin="system")
    assert remap.da_peca(store, P2)
    monkeypatch.setattr(gerente, "load_profile", lambda nome: _perfil())
    m.activate("Dois Jogadores", origin="system")
    assert remap.da_peca(store, P2) is None, "a troca do White ficou para o perfil seguinte"


# -- os dois caminhos do pad virtual ---------------------------------------------


class _Device:
    def __init__(self) -> None:
        self.analog: list[dict[str, int]] = []
        self.buttons: list[frozenset[str]] = []

    def forward_analog(self, **kw: int) -> None:
        self.analog.append(kw)

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        self.buttons.append(pressed)


def _o_primeiro(monkeypatch: pytest.MonkeyPatch, store: Any) -> tuple[Any, Any]:
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    dev = _Device()
    daemon = SimpleNamespace(
        store=store, _gamepad_device=dev, controller=SimpleNamespace(primary_uniq=P1))
    estado = SimpleNamespace(raw_lx=128, raw_ly=128, raw_rx=128, raw_ry=128, l2_raw=0, r2_raw=0)

    def tique(botoes: set[str]) -> frozenset[str]:
        gp.dispatch_gamepad(daemon, estado, F(botoes))
        return dev.buttons[-1]

    return dev, tique


def _o_segundo(store: Any, botoes: set[str], uniq: str = P2) -> tuple[Any, _Device]:
    from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer

    daemon = SimpleNamespace(
        store=store, controller=SimpleNamespace(), identity_registry=None,
        config=SimpleNamespace(coop_enabled=True, gamepad_flavor="dualsense"),
        _gamepad_device=object(), _coop_manager=None)
    mgr = CoopManager(daemon)
    vpad = _Device()
    foto = SimpleNamespace(lx=1, ly=2, rx=3, ry=4, l2_raw=0, r2_raw=0, buttons_pressed=F(botoes))
    leitor = SimpleNamespace(grab_state="held", snapshot=lambda: foto)
    mgr._players[uniq] = _SecondaryPlayer(
        identity=uniq, evdev_path="/dev/input/event9", reader=leitor, player_index=2,
        vpad=vpad)  # type: ignore[arg-type]
    return mgr, vpad


def test_a_troca_de_um_controle_nao_vaza_para_o_outro(monkeypatch: pytest.MonkeyPatch) -> None:
    """O White (o segundo) troca Cruz por Círculo; o primeiro joga com o controle de fábrica."""
    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    remap.definir_ativo(store, None, {P2: {"cross": "circle"}})
    _, tique = _o_primeiro(monkeypatch, store)
    assert tique({"cross"}) == F({"cross"}), "a troca do segundo jogador chegou ao primeiro"
    mgr, vpad = _o_segundo(store, {"cross"})
    mgr.forward_all()
    assert vpad.buttons[-1] == F({"circle"}), f"o segundo jogador não trocou: {vpad.buttons[-1]}"


def test_o_primeiro_controle_tem_a_troca_dele(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    remap.definir_ativo(store, None, {P1: {"cross": "square"}})
    _, tique = _o_primeiro(monkeypatch, store)
    assert tique({"cross"}) == F({"square"})
    mgr, vpad = _o_segundo(store, {"cross"})
    mgr.forward_all()
    assert vpad.buttons[-1] == F({"cross"}), "a troca do primeiro chegou ao segundo"


def test_cada_jogador_tem_a_disposicao_dele_ao_mesmo_tempo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    perfil = {"l1": "r1"}
    remap.definir_ativo(store, perfil, {P1: remap.juntar(perfil, {"cross": "square"}),
                                        P2: remap.juntar(perfil, {"cross": "circle"})})
    _, tique = _o_primeiro(monkeypatch, store)
    assert tique({"cross", "l1"}) == F({"square", "r1"})
    mgr, vpad = _o_segundo(store, {"cross", "l1"})
    mgr.forward_all()
    assert vpad.buttons[-1] == F({"circle", "r1"})
    mgr3, vpad3 = _o_segundo(store, {"cross", "l1"}, uniq=P3)
    mgr3.forward_all()
    assert vpad3.buttons[-1] == F({"cross", "r1"}), "o terceiro segue só a troca do perfil"


def test_o_gatilho_troca_por_controle_com_a_forca_do_gatilho(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    remap.definir_ativo(store, None, {P1: {"l2": "r2"}})
    dev, _ = _o_primeiro(monkeypatch, store)
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

    daemon = SimpleNamespace(
        store=store, _gamepad_device=dev, controller=SimpleNamespace(primary_uniq=P1))
    estado = SimpleNamespace(raw_lx=128, raw_ly=128, raw_rx=128, raw_ry=128, l2_raw=200, r2_raw=0)
    gp.dispatch_gamepad(daemon, estado, F({"l2_btn"}))
    assert dev.analog[-1]["r2"] == 200 and dev.analog[-1]["l2"] == 0
    assert dev.buttons[-1] == F({"r2_btn"})


def test_os_dois_caminhos_perguntam_pelo_controle() -> None:
    """Os dois caminhos leem a troca pelo dono único, passando o controle: nenhum lê a global."""
    for rel, quem in (("daemon/subsystems/gamepad.py", "dispatch_gamepad"),
                      ("daemon/subsystems/coop.py", "forward_all")):
        arvore = ast.parse((RAIZ / "src/hefesto_dualsense4unix" / rel).read_text(encoding="utf-8"))
        funcao = next(n for n in ast.walk(arvore)
                      if isinstance(n, ast.FunctionDef) and n.name == quem)
        chamadas = [n for n in ast.walk(funcao) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name) and n.func.id == "remapeamento_da_peca"]
        assert chamadas, f"{quem} não pergunta a troca pelo controle"
        assert all(len(c.args) == 2 for c in chamadas)


# -- a tela: o «Vale para» escolhe o dono da troca -----------------------------


def _ctx_de_dois(escolhido: str) -> Any:
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    mesa = [{"pref": "p1", "uniq": "aa:bb:cc:00:00:01", "nome": "Cosmic Red", "via": "USB",
             "jogador": 1, "cor": "cosmic-red"},
            {"pref": "p2", "uniq": "aa:bb:cc:00:00:02", "nome": "White", "via": "BT",
             "jogador": 2, "cor": "white"}]
    conectados = [{"uniq": m["uniq"], "inputs": {"buttons": []}} for m in mesa]
    return Contexto(state={"active_profile": "Regua"}, mesa=mesa, conectados=conectados,
                    escolhido=escolhido)


@pytest.fixture
def mapa() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import a13_mapa_do_controle as a13

    a13._largar()
    yield a13
    a13._largar()


def _perfil_no_disco() -> None:
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile

    loader.save_profile(Profile(name="Regua", match=MatchManual(),
                                remapeamento={"triangle": "cross"}))


def test_guardar_com_o_white_escolhido_grava_so_no_white(mapa: Any) -> None:
    from unittest.mock import MagicMock

    from hefesto_dualsense4unix.profiles import loader

    _perfil_no_disco()
    ctx = _ctx_de_dois("p2")
    mapa.mapa_botao(ctx, {"b": "square"}, None)
    mapa.mapa_escolher(ctx, {"v": "troca:circle"}, None)
    mapa.mapa_guardar(ctx, {}, MagicMock())
    gravado = loader.load_profile("Regua")
    assert gravado.remapeamento == {"triangle": "cross"}, "o perfil inteiro não muda"
    assert gravado.controllers is not None and set(gravado.controllers) == {P2}
    assert gravado.controllers[P2].remapeamento == {"square": "circle"}


def test_a_linha_mostra_a_troca_do_controle_escolhido_com_a_do_perfil_por_baixo(
        mapa: Any) -> None:
    from unittest.mock import MagicMock

    _perfil_no_disco()
    ctx = _ctx_de_dois("p2")
    mapa.mapa_botao(ctx, {"b": "square"}, None)
    mapa.mapa_escolher(ctx, {"v": "troca:circle"}, None)
    mapa.mapa_guardar(ctx, {}, MagicMock())
    no_white = mapa.pacote(_ctx_de_dois("p2"))["mesa"]
    no_red = mapa.pacote(_ctx_de_dois("p1"))["mesa"]
    assert no_white["atual-square"] == "troca:circle"
    assert not str(no_red["atual-square"]).startswith("troca:"), "o Cosmic Red não herda a do White"
    assert no_white["atual-triangle"] == no_red["atual-triangle"] == "troca:cross", (
        "a troca do perfil vale nos dois")


def test_trocar_de_controle_largar_a_edicao_que_nao_se_guardou(mapa: Any) -> None:
    _perfil_no_disco()
    mapa.mapa_botao(_ctx_de_dois("p2"), {"b": "square"}, None)
    mapa.mapa_escolher(_ctx_de_dois("p2"), {"v": "troca:circle"}, None)
    vista = mapa.pacote(_ctx_de_dois("p1"))["mesa"]
    assert not str(vista["atual-square"]).startswith("troca:"), (
        "a edição do White não pode cair no Cosmic Red")


def test_soltar_no_controle_a_troca_do_perfil_cancela_so_nele() -> None:
    from hefesto_dualsense4unix.interface.pacotes import a13_mapa_do_controle as a13
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile

    prof = Profile(name="x", match=MatchManual(), remapeamento={"triangle": "cross"})
    novo = a13._aplicar_as_edicoes(prof, {"triangle": ("nada", "")}, {}, P2)
    assert novo.remapeamento == {"triangle": "cross"}
    assert novo.controllers[P2].remapeamento == {"triangle": "triangle"}
    assert remap.juntar(novo.remapeamento, novo.controllers[P2].remapeamento) == {}


def test_o_que_mora_no_mapa_e_campo_do_esquema_e_o_mapa_o_le() -> None:
    """A isenção da coluna «Ajuste próprio» tem dono: o mapa lê e grava o campo por controle."""
    from hefesto_dualsense4unix.app.actions import perfis_web
    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides

    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/pacotes"
             / "a13_mapa_do_controle.py").read_text(encoding="utf-8")
    assert perfis_web.SECOES_QUE_MORAM_NO_MAPA
    for secao in perfis_web.SECOES_QUE_MORAM_NO_MAPA:
        assert secao in ControllerOverrides.model_fields
        assert f'"{secao}"' in fonte, f"o mapa do controle não lê nem grava `{secao}` por controle"
