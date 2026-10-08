"""A-NAVEGACAO-INTERNA-E-UM-MODO-QUE-SE-LIGA-EM-QUALQUER-ABA-01 — as doze réguas.

Com o desenho dela de 03/10/2026: a Interna liga em qualquer Modo, R1 e L1 de
qualquer controle dão a volta entre as abas 01 a 05, cada controle anda a SUA
seleção e o X dele grava no dele, o Start guarda, e enquanto a janela está na
frente os botões que navegam não chegam ao jogo nem saem como Alt+Tab.

O lar é de mentira pelo ``tests/conftest.py`` (``HOME`` e ``XDG_*`` desviados):
a flag da Interna que o daemon grava cai no ``tmp`` da régua.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from evdev import ecodes

from hefesto_dualsense4unix.core import remapeamento_de_botao as remap
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems import navegacao_interna as dono
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer
from hefesto_dualsense4unix.interface import navegacao_interna as nav
from hefesto_dualsense4unix.testing import FakeController

P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"
P3 = "aa:bb:cc:00:00:03"
DEZ = ("01-jogar.html", "02-controles.html", "03-gatilhos.html", "04-iluminacao.html",
       "05-vibracao.html", "06-navegacao.html", "07-lancadores.html", "08-conexoes.html",
       "09-sistema.html", "10-perfis.html")


class _Relogio:
    def __init__(self) -> None:
        self.agora = 100.0

    def __call__(self) -> float:
        return self.agora


def _interna(relogio: _Relogio, *, foco: bool = True) -> dono.NavegacaoInterna:
    n = dono.NavegacaoInterna(ligada=True, tipo=dono.TIPO_INTERNA, relogio=relogio)
    if foco:
        n.declarar_foco(True)
    return n


# 1 ─ O interruptor liga a Interna fora do Modo Navegação ─────────────────────


class _PonteQueAnota:
    def __init__(self) -> None:
        self.chamadas: list[tuple[str, dict[str, Any]]] = []

    def resultado(self, metodo: str, **kw: Any) -> dict[str, Any]:
        self.chamadas.append((metodo, kw))
        return {"status": "ok"}


def test_1_o_interruptor_liga_a_interna_no_modo_sony(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.interface import pacotes
    from hefesto_dualsense4unix.interface.pacotes import a06_navegacao as a06

    monkeypatch.setattr(a06, "_PEDIDO", {})
    estado = {
        "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
        "mouse_emulation": {"enabled": False},
        "navegacao": {"interna_ligada": False, "tipo": "interna", "foco": False},
        "controllers": [],
    }
    ctx = pacotes.Contexto(state=estado, mesa=[], conectados=[], estados={})
    ponte = _PonteQueAnota()
    try:
        a06.modo(ctx, {}, ponte)
    except RuntimeError as erro:
        pytest.fail(f"o interruptor no tipo Interna recusou no Modo Sony: {erro}")
    assert ponte.chamadas == [("navegacao.interna.set", {"ligada": True, "origin": "manual"})], (
        f"o interruptor mandou {ponte.chamadas} — a Interna não chegou ao daemon")


# 2 ─ O foco decide o R1 (D-20) ─────────────────────────────────────────────


def test_2_com_o_foco_vivo_o_r1_nao_sai_como_alt_tab_e_e_contado() -> None:
    relogio = _Relogio()
    n = _interna(relogio, foco=False)
    n.contar({P1: {}})
    assert n.calar_o_alt_tab(frozenset({"r1", "cross"})) == frozenset({"r1", "cross"}), (
        "sem foco, o R1 tem de sair como Alt+Tab")
    n.contar({P1: {"r1": 1}})
    assert n.toques()[P1]["r1"] == 0, "sem foco, o R1 que saiu como Alt+Tab não vira aba"
    n.declarar_foco(True)
    assert n.calar_o_alt_tab(frozenset({"r1", "l1", "cross"})) == frozenset({"cross"}), (
        "com a janela na frente, o R1 e o L1 saíram como Alt+Tab")
    n.contar({P1: {"r1": 2}})
    assert n.toques()[P1]["r1"] == 1


def test_2_o_laco_cala_o_alt_tab_antes_do_teclado_emulado() -> None:
    """O `_poll_loop` passa os botões pela Interna antes do despacho do teclado."""
    fonte = inspect.getsource(Daemon._poll_loop)
    calar = fonte.find("calar_o_alt_tab(emu_buttons)")
    despacho = fonte.find("_dispatch_mouse_emulation(state, emu_buttons)")
    assert calar != -1 and despacho != -1 and calar < despacho, (
        "o R1 do primário chega ao teclado emulado sem passar pela Interna")


def test_2_ligar_a_interna_nao_mexe_no_mouse() -> None:
    d = Daemon(controller=FakeController(transport="bt"), config=DaemonConfig())
    antes = d.config.mouse_emulation_enabled
    bloco = d.definir_a_navegacao_interna(ligada=True, tipo="interna")
    assert bloco["interna_ligada"] is True and bloco["tipo"] == "interna"
    assert d.config.mouse_emulation_enabled == antes, "ligar a Interna mexeu no mouse"
    from hefesto_dualsense4unix.utils.session import load_navegacao_interna

    assert load_navegacao_interna() == (True, "interna"), "a escolha não foi guardada"


# 3 e 4 ─ O que navega não chega ao pad virtual (D-22), e o foco tem prazo ───


class _Pad:
    def __init__(self) -> None:
        self.analog: list[dict[str, int]] = []
        self.buttons: list[frozenset[str]] = []

    def forward_analog(self, **kw: int) -> None:
        self.analog.append(kw)

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        self.buttons.append(pressed)


def _o_secundario_manda(interna: dono.NavegacaoInterna | None) -> _Pad:
    store = SimpleNamespace()
    remap.definir_ativo(store, None)
    daemon = SimpleNamespace(
        store=store, controller=SimpleNamespace(), identity_registry=None,
        config=SimpleNamespace(coop_enabled=True, gamepad_flavor="dualsense"),
        _gamepad_device=object(), _coop_manager=None, _navegacao_interna=interna)
    mgr = CoopManager(daemon)
    snap = SimpleNamespace(lx=200, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0,
                           buttons_pressed=frozenset({"cross", "l2_btn"}))
    pad = _Pad()
    leitor = SimpleNamespace(grab_state="held", snapshot=lambda: snap)
    mgr._players[P2] = _SecondaryPlayer(
        identity=P2, evdev_path="/dev/input/event9", reader=leitor,
        player_index=2, vpad=pad)  # type: ignore[arg-type]
    mgr.forward_all()
    return pad


def test_3_o_x_do_secundario_nao_chega_ao_pad_e_o_analogico_chega() -> None:
    pad = _o_secundario_manda(_interna(_Relogio()))
    assert pad.buttons == [frozenset({"l2_btn"})], (
        f"o jogador 2 mandou {pad.buttons} ao jogo com a janela na frente")
    assert pad.analog and pad.analog[-1]["lx"] == 200, "o analógico tem de chegar ao jogo"


def test_3_o_x_do_primario_nao_chega_ao_pad(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    remap.definir_ativo(store, None)
    pad = _Pad()
    estado = SimpleNamespace(raw_lx=128, raw_ly=128, raw_rx=128, raw_ry=128,
                             l2_raw=0, r2_raw=0)
    daemon = SimpleNamespace(store=store, _gamepad_device=pad,
                             _navegacao_interna=_interna(_Relogio()))
    gp.dispatch_gamepad(daemon, estado, frozenset({"cross", "r2_btn"}))
    assert pad.buttons == [frozenset({"r2_btn"})], f"o primário mandou {pad.buttons}"


def test_4_sem_renovacao_o_foco_cai_em_um_segundo_e_o_x_volta() -> None:
    relogio = _Relogio()
    interna = _interna(relogio)
    relogio.agora += dono.PRAZO_DO_FOCO_S - 0.1
    assert _o_secundario_manda(interna).buttons == [frozenset({"l2_btn"})]
    relogio.agora += 0.2
    assert _o_secundario_manda(interna).buttons == [frozenset({"cross", "l2_btn"})], (
        "uma janela que morreu sem se despedir deixou o X roubado")
    assert dono.PRAZO_DO_FOCO_S == 1.0


# 5, 6 e 7 ─ Os toques viram atos ───────────────────────────────────────────


def _toques(**contas: int) -> dict[str, int]:
    return dict(contas)


def test_5_um_toque_entre_dois_tiques_anda_uma_aba_em_volta() -> None:
    n = nav.Navegador(relogio=_Relogio())
    parado = {P1: {"buttons": []}}
    assert n.atos(pagina="10-perfis.html", dez=DEZ, toques={P1: _toques(r1=7)},
                  ativa=True, inputs=parado) == []
    atos = n.atos(pagina="10-perfis.html", dez=DEZ, toques={P1: _toques(r1=8)},
                  ativa=True, inputs=parado)
    assert nav.Ato("ir", pagina="01-jogar.html") in atos, atos
    n.atos(pagina="01-jogar.html", dez=DEZ, toques={P1: _toques(l1=0)}, ativa=True)
    atos = n.atos(pagina="01-jogar.html", dez=DEZ, toques={P1: _toques(l1=1)}, ativa=True)
    assert nav.Ato("ir", pagina="05-vibracao.html") in atos, (
        f"o L1 na 01 deu {atos}: a volta do desenho de 03/10 é entre a 01 e a 05")
    n.atos(pagina="05-vibracao.html", dez=DEZ, toques={P1: _toques(r1=0)}, ativa=True)
    atos = n.atos(pagina="05-vibracao.html", dez=DEZ, toques={P1: _toques(r1=1)}, ativa=True)
    assert nav.Ato("ir", pagina="01-jogar.html") in atos


def test_6_o_r1_do_p3_anda_a_aba() -> None:
    n = nav.Navegador(relogio=_Relogio())
    n.atos(pagina="02-controles.html", dez=DEZ, toques={P3: _toques(r1=0)}, ativa=True)
    atos = n.atos(pagina="02-controles.html", dez=DEZ, toques={P3: _toques(r1=1)},
                  ativa=True)
    assert nav.Ato("ir", pagina="03-gatilhos.html") in atos


def test_6_o_x_do_p2_escolhe_o_p2_na_fita_antes_do_clique(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.interface import hefesto_vivo as hv

    monkeypatch.setattr(hv.ESCOLHA_DA_FITA, "uniq", "todos")
    mesa = [{"uniq": P1, "pref": "p1"}, {"uniq": P2, "pref": "p2"}]
    ctx = SimpleNamespace(mesa=mesa)
    js: list[str] = []
    # Na 02 a fita ESCOLHE (`monta.ABAS_QUE_ESCOLHEM`); na 04 cada controle tem
    # a sua coluna, e o X no bloco do P2 já é do P2 (`caixas_do_leiaute`).
    piloto = SimpleNamespace(_selecoes=nav.Selecoes(), pagina="02-controles.html",
                             _js=js.append, _com_molduras=False, _ir=lambda p: False)
    leiaute = {"largura": 800, "altura": 600, "popup": False, "caixas": [
        {"endereco": "x|cor|c|v#0", "x": 10, "y": 10, "w": 100, "h": 30, "dono": "p2"}]}
    atos = [nav.Ato("passo", uniq=P2, direcao="baixo"), nav.Ato("x", uniq=P2)]
    hv.Piloto._agir(piloto, atos, leiaute, ctx,  # type: ignore[arg-type]
                    {P1: "p1", P2: "p2"}, {})
    assert hv.ESCOLHA_DA_FITA.uniq == "aabbcc000002", (
        f"o X do P2 escolheu {hv.ESCOLHA_DA_FITA.uniq!r} — grava no controle errado")
    assert js and '"op": "clicar"' in js[-1] and '"pref": "p2"' in js[-1], js


def test_7_a_janela_inativa_nao_anda() -> None:
    n = nav.Navegador(relogio=_Relogio())
    n.atos(pagina="01-jogar.html", dez=DEZ, toques={P1: _toques(r1=0, x=0)}, ativa=True)
    inputs = {P1: {"lx": 255, "ly": 128}}
    assert n.atos(pagina="01-jogar.html", dez=DEZ, toques={P1: _toques(r1=3, x=2)},
                  ativa=False, inputs=inputs) == []
    assert n.atos(pagina="01-jogar.html", dez=DEZ, toques={P1: _toques(r1=3, x=2)},
                  ativa=True) == [], "o R1 apertado com a janela atrás andou depois"


# 8 e 9 ─ O cartão não mente, e nenhuma opção sem dono ──────────────────────


def test_8_o_cartao_nao_mente() -> None:
    from hefesto_dualsense4unix.interface.pacotes import a06_navegacao as a06

    desligada = {"mouse_emulation": {"enabled": True},
                 "navegacao": {"interna_ligada": False, "tipo": "interna"}}
    assert a06.PAPEL_SO_A_JANELA not in a06.linha_do_cartao("BT", False, estado=desligada)
    sem_mouse = {"mouse_emulation": {"enabled": False},
                 "navegacao": {"interna_ligada": False, "tipo": "interna"}}
    linha = a06.linha_do_cartao("USB", True, estado=sem_mouse)
    assert a06.BOLINHA not in linha and a06.PAPEL_QUE_NAVEGA not in linha, linha
    ligada = {"mouse_emulation": {"enabled": True},
              "navegacao": {"interna_ligada": True, "tipo": "interna"}}
    assert a06.PAPEL_SO_A_JANELA in a06.linha_do_cartao("BT", False, estado=ligada)
    assert a06.PAPEL_QUE_NAVEGA in a06.linha_do_cartao("USB", True, estado=ligada)


def test_9_nenhuma_opcao_sem_dono() -> None:
    from hefesto_dualsense4unix.interface import pacotes
    from hefesto_dualsense4unix.interface.pacotes import a06_navegacao as a06

    assert "navegacao-interna" not in a06.SEM_GESTO
    assert "navegacao-tipo" not in a06.SEM_GESTO
    assert ("06-navegacao.html", "navegacao-tipo") in pacotes.GESTOS


# 10 ─ O contador sobe na borda ─────────────────────────────────────────────


@dataclass
class _Evento:
    type: int
    code: int
    value: int


def test_10_o_r1_segurado_por_tres_leituras_conta_um() -> None:
    leitor = EvdevReader(device_path=Path("/nao/existe/event-do-p2"))
    n = _interna(_Relogio())
    n.contar({P2: leitor.snapshot().apertos})
    leitor._handle_event(_Evento(ecodes.EV_KEY, ecodes.BTN_TR, 1), ecodes)
    for _ in range(3):
        n.contar({P2: leitor.snapshot().apertos})
        leitor._handle_event(_Evento(ecodes.EV_KEY, ecodes.BTN_TR, 2), ecodes)
    assert leitor.snapshot().apertos.get("r1") == 1
    assert n.toques()[P2]["r1"] == 1, f"um R1 segurado contou {n.toques()[P2]['r1']}"


# 11 e 12 ─ A seleção ───────────────────────────────────────────────────────


def _cruz() -> list[nav.Caixa]:
    """Cinco caixas em cruz; na ordem do DOM, a da direita vem antes da de baixo."""
    return [
        nav.Caixa("cima", 100, 0, 40, 20),
        nav.Caixa("esquerda", 0, 100, 40, 20),
        nav.Caixa("meio", 100, 100, 40, 20),
        nav.Caixa("direita", 200, 100, 40, 20),
        nav.Caixa("baixo", 100, 200, 40, 20),
    ]


def test_11_a_selecao_anda_para_o_vizinho_da_direcao() -> None:
    caixas = _cruz()
    meio = 2
    assert caixas[nav.vizinho(caixas, meio, "baixo") or 0].endereco == "baixo"
    assert caixas[nav.vizinho(caixas, meio, "direita") or 0].endereco == "direita"
    assert caixas[nav.vizinho(caixas, meio, "cima") or 0].endereco == "cima"
    assert caixas[nav.vizinho(caixas, meio, "esquerda") or 0].endereco == "esquerda"


def test_11_o_analogico_anda_e_repete_so_depois_da_repeticao() -> None:
    relogio = _Relogio()
    n = nav.Navegador(relogio=relogio)
    n.atos(pagina="04-iluminacao.html", dez=DEZ, toques={P2: {}}, ativa=True)
    inclinado = {P2: {"lx": 128 + nav.LIMIAR_DO_ANALOGICO + 10, "ly": 128}}
    passo = nav.Ato("passo", uniq=P2, direcao="direita")

    def atos() -> list[nav.Ato]:
        return n.atos(pagina="04-iluminacao.html", dez=DEZ, toques={P2: {}},
                      ativa=True, inputs=inclinado)

    assert atos() == [passo]
    relogio.agora += nav.REPETICAO_DO_ANALOGICO_S / 2
    assert atos() == [], "segurado, o analógico andou antes da repetição"
    relogio.agora += nav.REPETICAO_DO_ANALOGICO_S
    assert atos() == [passo]


def test_12_o_x_numa_lista_entra_e_o_direcional_troca_a_opcao() -> None:
    caixas = [nav.Caixa("lista", 100, 100, 80, 20, tipo="lista"),
              nav.Caixa("embaixo", 100, 200, 80, 20)]
    sel = nav.Selecoes()

    def aplicar(*atos: nav.Ato) -> list[dict[str, Any]]:
        return sel.aplicar(list(atos), lambda _u: caixas, pref_de={P2: "p2"}, popup=False)

    aplicar(nav.Ato("passo", uniq=P2, direcao="cima"))
    assert sel.de(P2) == "lista"
    assert aplicar(nav.Ato("x", uniq=P2)) == []
    assert aplicar(nav.Ato("passo", uniq=P2, direcao="baixo")) == [
        {"op": "escolha", "endereco": "lista", "passo": 1}], (
        "o ↓ dentro da lista não trocou a opção")
    assert sel.de(P2) == "lista"
    aplicar(nav.Ato("o", uniq=P2))
    assert aplicar(nav.Ato("passo", uniq=P2, direcao="baixo")) == []
    assert sel.de(P2) == "embaixo", "depois do O, o ↓ tem de andar a seleção"


def test_12_cada_controle_seleciona_so_o_seu_bloco() -> None:
    leiaute = {"caixas": [
        {"endereco": "a", "x": 0, "y": 0, "w": 10, "h": 10, "dono": "p1"},
        {"endereco": "b", "x": 0, "y": 20, "w": 10, "h": 10, "dono": "p2"},
        {"endereco": "c", "x": 0, "y": 40, "w": 10, "h": 10}]}
    assert [c.endereco for c in nav.caixas_do_leiaute(leiaute, "p2")] == ["b", "c"]
