#!/usr/bin/env python3
"""O botão grava e toca uma sequência (O-BOTAO-GRAVA-E-TOCA-UMA-SEQUENCIA-01, 20/10/2026).

Um botão do controle vira uma lista de botões com tempo, tocada no pad virtual. O motor é o da
ativação (`core/ativacao_de_botao.traduzir`), o mesmo dos DOIS caminhos do pad (o do primeiro
controle, `gamepad.dispatch_gamepad`, e o dos outros, `coop.forward_all`); a sequência vale por
perfil e por controle; a gravação mora no daemon (o tique da tela, de 100 ms, é grosso demais).

A MORDIDA, e cada uma foi rodada na entrega:

- tire de `traduzir` o ramo que toca a sequência (`AtivacaoDoControle._sequencia`) e
  :func:`test_a_sequencia_sai_na_ordem_e_no_tempo` reprova;
- faça `tocar_a_volta` abrir só o último passo vencido e
  :func:`test_um_tique_atrasado_nao_pula_passo` reprova;
- tire a chamada `ativar_o_botao` de `gamepad.dispatch_gamepad` e
  :func:`test_o_primeiro_controle_toca_a_sequencia` reprova;
- tire a chamada de `coop.forward_all` e :func:`test_o_segundo_controle_toca_a_dele` reprova;
- junte a sequência da peça à do perfil (em vez de trocar) em `montar` e
  :func:`test_a_sequencia_da_peca_troca_a_do_perfil_em_vez_de_somar` reprova;
- deixe `traduzir` repassar o botão que dispara a sequência e
  :func:`test_o_botao_que_dispara_nao_chega_ao_jogo` reprova;
- tire o `observar` da gravação em `traduzir` e :func:`test_a_gravacao_guarda_a_ordem_e_o_tempo`
  reprova;
- tire o `_com_as_sequencias` de `_aplicar_as_edicoes` e
  :func:`test_guardar_grava_a_sequencia_no_perfil_ou_so_no_controle` reprova;
- tire a entrada `sequencia.tocar` de `ipc_server.py` e :func:`test_o_servidor_publica_os_dois`
  reprova.
"""
from __future__ import annotations

import asyncio
import pathlib
import re
import time
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.core import ativacao_de_botao as ab
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.profiles.schema import Profile, ProfileAtivacaoConfig

RAIZ = pathlib.Path(__file__).resolve().parents[2]
F = frozenset
P1 = "aabbcc000001"
P2 = "aabbcc000002"
P3 = "aabbcc000003"
ATIVACAO = "ativacao"  # (noqa-acento): a chave da seção do perfil
ACAO = "acao"  # (noqa-acento): o parâmetro do IPC
TRES = [{"botao": "cross", "ms": 80}, {"botao": "circle", "ms": 120}, {"botao": "r1", "ms": 0}]


def _cfg(jeito: str = "uma_vez", ritmo: str = "gravado", botao: str = "l1",
         passos: list[dict[str, Any]] | None = None) -> ProfileAtivacaoConfig:
    return ProfileAtivacaoConfig.model_validate({"sequencia": {botao: {
        "passos": passos or TRES, "jeito": jeito, "ritmo": ritmo}}})


def _loja(cfg: ProfileAtivacaoConfig | None = None, **por_peca: Any) -> Any:
    store = SimpleNamespace()
    ab.definir_ativo(store, ab.montar(cfg) if cfg else None,
                     {k: v for k, v in por_peca.items()})
    return store


def _tocar(store: Any, uniq: str | None, apertos: dict[int, set[str]], quadros: int,
           passo: float = 0.01) -> list[tuple[float, frozenset[str]]]:
    """Cada tique `i` aperta `apertos.get(i)`; devolve `(segundos, botões que o jogo vê)`."""
    saida = []
    for i in range(quadros):
        t = 100.0 + i * passo
        b, _, _, _ = ab.traduzir(store, uniq, F(apertos.get(i, set())), 0, 0, t)
        saida.append((round(i * passo, 4), b))
    return saida


def _primeira_vez(saida: list[tuple[float, frozenset[str]]], botao: str) -> float | None:
    return next((t for t, b in saida if botao in b), None)


def _subidas(saida: list[tuple[float, frozenset[str]]], botao: str,
             de: float = 0.0, ate: float = 1e9) -> int:
    n, antes = 0, False
    for t, b in saida:
        agora = botao in b
        if de <= t < ate and agora and not antes:
            n += 1
        antes = agora
    return n


# -- o motor: ordem, tempo, jeito e ritmo -------------------------------------


def test_a_sequencia_sai_na_ordem_e_no_tempo() -> None:
    store = _loja(_cfg())
    saida = _tocar(store, P1, {0: {"l1"}, 1: {"l1"}, 2: {"l1"}}, 40)
    cruz, circulo, r1 = (_primeira_vez(saida, n) for n in ("cross", "circle", "r1"))
    assert cruz is not None and circulo is not None and r1 is not None, saida
    assert cruz < circulo < r1, f"a ordem gravada não saiu: {cruz} {circulo} {r1}"
    assert abs(circulo - cruz - 0.08) <= 0.015, f"Círculo veio {circulo - cruz:.3f} s depois"
    assert abs(r1 - circulo - 0.12) <= 0.015, f"R1 veio {r1 - circulo:.3f} s depois"
    seguro = [t for t, b in saida if "cross" in b]
    assert seguro[-1] - seguro[0] >= ab.SEGURA_S - 0.011, "o botão não ficou apertado o bastante"


def test_o_botao_que_dispara_nao_chega_ao_jogo() -> None:
    store = _loja(_cfg())
    saida = _tocar(store, P1, {i: {"l1"} for i in range(8)}, 40)
    assert all("l1" not in b for _, b in saida), "o L1 vazou para o jogo junto da sequência"


def test_um_tique_atrasado_nao_pula_passo() -> None:
    store = _loja(_cfg())
    saida = _tocar(store, P1, {0: {"l1"}}, 12, passo=0.5)
    vistos = [n for _, b in saida for n in ("cross", "circle", "r1") if n in b]
    assert vistos == ["cross", "circle", "r1"], f"o laço atrasado pulou passo: {vistos}"


def test_o_acorde_sai_junto_com_ms_zero() -> None:
    store = _loja(_cfg(passos=[{"botao": "cross", "ms": 0}, {"botao": "circle", "ms": 0}]))
    saida = _tocar(store, P1, {0: {"l1"}}, 12)
    com_os_dois = [t for t, b in saida if {"cross", "circle"} <= b]
    assert com_os_dois, f"o acorde de ms=0 não apertou os dois juntos: {saida}"


def test_o_intervalo_curto_demais_sobe_ao_minimo() -> None:
    pronta = ab.pronta_para_tocar({"passos": [{"botao": "cross", "ms": 20},
                                              {"botao": "circle", "ms": 0}]})
    assert pronta.passos[1][1] - pronta.passos[0][1] == pytest.approx(ab.INTERVALO_MINIMO_S)


def test_o_ritmo_multiplica_so_os_intervalos() -> None:
    passos = [{"botao": "cross", "ms": 200}, {"botao": "circle", "ms": 300},
              {"botao": "r1", "ms": 0}]

    def quando(ritmo: str) -> list[float]:
        pronta = ab.pronta_para_tocar({"passos": passos, "ritmo": ritmo})
        return [round(t, 3) for _, t in pronta.passos]

    assert quando("gravado") == [0.0, 0.2, 0.5]
    assert quando("rapido") == [0.0, 0.1, 0.25]
    assert quando("devagar") == [0.0, 0.4, 1.0]


def test_uma_vez_ignora_o_aperto_no_meio_da_volta() -> None:
    store = _loja(_cfg("uma_vez"))
    saida = _tocar(store, P1, {0: {"l1"}, 10: {"l1"}, 60: {"l1"}}, 100)
    assert _subidas(saida, "cross", ate=0.5) == 1, "o aperto no meio da volta recomeçou a sequência"
    assert _subidas(saida, "cross", de=0.5) == 1, "depois da volta, o aperto toca de novo"


def test_repete_toca_enquanto_segura_e_a_volta_que_comecou_acaba() -> None:
    store = _loja(_cfg("repete"))
    seguro = {i: {"l1"} for i in range(0, 100)}
    saida = _tocar(store, P1, seguro, 200)
    voltas = _subidas(saida, "cross")
    assert voltas >= 2, f"segurar não repetiu a sequência: {voltas} volta(s)"
    assert _subidas(saida, "r1") == voltas, "uma volta começada tem de acabar, com o R1 dela"
    assert _subidas(saida, "cross", de=1.5) == 0, "soltou o botão e a sequência seguiu tocando"


def test_alterna_toca_sozinha_ate_o_segundo_aperto() -> None:
    store = _loja(_cfg("alterna"))
    saida = _tocar(store, P1, {0: {"l1"}, 120: {"l1"}}, 260)
    assert _subidas(saida, "cross", de=0.1, ate=1.15) >= 2, "ligou e não seguiu sozinha"
    assert _subidas(saida, "cross", de=1.6) == 0, "o segundo aperto não desligou"


def test_o_botao_sem_sequencia_passa_intacto() -> None:
    store = _loja(_cfg())
    b, _, _, _ = ab.traduzir(store, P1, F({"cross"}), 0, 0, 1.0)
    assert b == F({"cross"})


# -- por perfil e por controle ------------------------------------------------


def test_a_sequencia_da_peca_vale_so_nela() -> None:
    perfil = _cfg(passos=[{"botao": "cross", "ms": 0}])
    peca = _cfg(passos=[{"botao": "square", "ms": 0}])
    store = SimpleNamespace()
    ab.definir_ativo(store, ab.montar(perfil), {P2: ab.montar(perfil, peca)})
    assert _primeira_vez(_tocar(store, P1, {0: {"l1"}}, 6), "cross") is not None
    no_p2 = _tocar(store, P2, {0: {"l1"}}, 6)
    assert _primeira_vez(no_p2, "square") is not None
    assert _primeira_vez(no_p2, "cross") is None, "a sequência do perfil se somou à da peça"
    assert _primeira_vez(_tocar(store, P3, {0: {"l1"}}, 6), "cross") is not None, (
        "o terceiro controle, sem peça, segue o perfil")


def test_a_sequencia_da_peca_troca_a_do_perfil_em_vez_de_somar() -> None:
    perfil = _cfg(botao="l1", passos=[{"botao": "cross", "ms": 0}])
    peca = _cfg(botao="r1", passos=[{"botao": "square", "ms": 0}])
    store = SimpleNamespace()
    ab.definir_ativo(store, ab.montar(perfil), {P2: ab.montar(perfil, peca)})
    no_p2 = _tocar(store, P2, {0: {"l1", "r1"}}, 6)
    assert _primeira_vez(no_p2, "square") is not None
    assert _primeira_vez(no_p2, "cross") is None, "o L1 do perfil seguiu valendo na peça"
    assert any("l1" in b for _, b in no_p2), "o L1 solto da sequência volta a ser botão"


def test_o_perfil_sem_sequencia_nao_toca_nada_no_outro_controle() -> None:
    peca = _cfg(passos=[{"botao": "square", "ms": 0}])
    store = SimpleNamespace()
    ab.definir_ativo(store, None, {P2: ab.montar(peca)})
    assert _primeira_vez(_tocar(store, P2, {0: {"l1"}}, 6), "square") is not None
    b, _, _, _ = ab.traduzir(store, P1, F({"l1"}), 0, 0, 1.0)
    assert b == F({"l1"}), "o controle sem sequência perdeu o botão"


def test_o_perfil_seguinte_larga_a_sequencia_em_curso() -> None:
    store = _loja(_cfg("repete"))
    _tocar(store, P1, {i: {"l1"} for i in range(5)}, 6)
    assert ab.preso(store, P1)
    ab.definir_ativo(store, None)
    assert not ab.preso(store, P1)


# -- os dois caminhos do pad virtual ------------------------------------------


class _Device:
    def __init__(self) -> None:
        self.analog: list[dict[str, int]] = []
        self.buttons: list[frozenset[str]] = []

    def forward_analog(self, **kw: int) -> None:
        self.analog.append(kw)

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        self.buttons.append(pressed)


def _ordem(vistos: list[frozenset[str]]) -> list[str]:
    ordem: list[str] = []
    for b in vistos:
        for n in ("cross", "circle", "r1"):
            if n in b and n not in ordem:
                ordem.append(n)
    return ordem


def test_o_primeiro_controle_toca_a_sequencia(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    ab.definir_ativo(store, ab.montar(_cfg()))
    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    relogio = [200.0]
    monkeypatch.setattr(gp, "_agora", lambda: relogio[0])
    dev = _Device()
    daemon = SimpleNamespace(store=store, _gamepad_device=dev)
    estado = SimpleNamespace(raw_lx=128, raw_ly=128, raw_rx=128, raw_ry=128, l2_raw=0, r2_raw=0)
    for i in range(40):
        relogio[0] += 0.01
        gp.dispatch_gamepad(daemon, estado, F({"l1"}) if i < 3 else F())
    assert _ordem(dev.buttons) == ["cross", "circle", "r1"], dev.buttons
    assert all("l1" not in b for b in dev.buttons)


def test_o_segundo_controle_toca_a_dele(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
    from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer

    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    ab.definir_ativo(store, None, {P2: ab.montar(_cfg())})
    relogio = [300.0]
    monkeypatch.setattr(gp, "_agora", lambda: relogio[0])
    daemon = SimpleNamespace(
        store=store, controller=SimpleNamespace(), identity_registry=None,
        config=SimpleNamespace(coop_enabled=True, gamepad_flavor="dualsense"),
        _gamepad_device=object(), _coop_manager=None)
    mgr = CoopManager(daemon)
    vpad = _Device()
    snap = SimpleNamespace(lx=1, ly=2, rx=3, ry=4, l2_raw=0, r2_raw=0, buttons_pressed=F({"l1"}))
    leitor = SimpleNamespace(grab_state="held", snapshot=lambda: snap)
    mgr._players[P2] = _SecondaryPlayer(
        identity=P2, evdev_path="/dev/input/event9", reader=leitor,  # type: ignore[arg-type]
        player_index=2, vpad=vpad)  # type: ignore[arg-type]
    for i in range(40):
        snap.buttons_pressed = F({"l1"}) if i < 3 else F()
        relogio[0] += 0.01
        mgr.forward_all()
    assert _ordem(vpad.buttons) == ["cross", "circle", "r1"], vpad.buttons


def test_os_dois_caminhos_ainda_passam_pelo_dono_unico() -> None:
    import ast

    for arquivo, funcao in (("gamepad.py", "dispatch_gamepad"), ("coop.py", "forward_all")):
        arvore = ast.parse((RAIZ / "src/hefesto_dualsense4unix/daemon/subsystems" / arquivo)
                           .read_text(encoding="utf-8"))
        no = next(n for n in ast.walk(arvore)
                  if isinstance(n, ast.FunctionDef) and n.name == funcao)
        assert any(isinstance(c, ast.Call) and getattr(c.func, "id", None) == "ativar_o_botao"
                   for c in ast.walk(no)), f"{funcao} não chama o dono único"


# -- a gravação ---------------------------------------------------------------


def _ouvir(store: Any, eventos: list[tuple[float, str, set[str], int, int, set[str]]]) -> None:
    for t, uniq, botoes, l2, r2, soltos in eventos:
        b, a, c, s = ab.traduzir(store, uniq, F(botoes), l2, r2, t, F(soltos))
        if ab.gravar_estado(store)[0]:
            assert (b, a, c, s) == (F(), 0, 0, F()), "o que se grava não pode chegar ao jogo"


def test_a_gravacao_guarda_a_ordem_e_o_tempo() -> None:
    store = SimpleNamespace()
    ab.gravar_iniciar(store, P2, 10.0)
    assert ab.alguma(store)
    _ouvir(store, [
        (10.10, P2, {"cross"}, 0, 0, set()), (10.12, P2, set(), 0, 0, set()),
        (10.18, P2, {"circle"}, 0, 0, set()), (10.20, P2, set(), 0, 0, set()),
        (10.50, P2, {"r1"}, 0, 0, set()),
    ])
    assert ab.gravar_parar(store) == [
        {"botao": "cross", "ms": 80}, {"botao": "circle", "ms": 320}, {"botao": "r1", "ms": 0}]
    assert not ab.alguma(store)


def test_a_gravacao_conta_acorde_toque_curto_e_gatilho() -> None:
    store = SimpleNamespace()
    ab.gravar_iniciar(store, None, 10.0)
    _ouvir(store, [
        (10.1, P2, {"circle", "cross"}, 0, 0, set()),
        (10.2, P2, {"circle", "cross"}, 0, 0, set()),
        (10.3, P2, set(), 0, 0, {"square"}),
        (10.4, P2, {"l2_btn"}, 255, 0, set()),
        (10.5, P2, set(), 0, 255, set()),
    ])
    passos = ab.gravar_parar(store)
    assert [p["botao"] for p in passos] == ["cross", "circle", "square", "l2", "r2"], passos
    assert passos[0]["ms"] == 0, "o acorde grava os dois no mesmo instante"


def test_a_gravacao_ouve_so_o_controle_pedido() -> None:
    store = SimpleNamespace()
    ab.gravar_iniciar(store, P2, 10.0)
    b, _, _, _ = ab.traduzir(store, P1, F({"cross"}), 0, 0, 10.1)
    assert b == F({"cross"}), "a gravação do P2 engoliu o P1"
    ab.traduzir(store, P2, F({"circle"}), 0, 0, 10.2)
    assert [p["botao"] for p in ab.gravar_parar(store)] == ["circle"]


def test_a_gravacao_para_nos_32_passos_e_nos_30_segundos() -> None:
    store = SimpleNamespace()
    ab.gravar_iniciar(store, P2, 10.0)
    for i in range(40):
        ab.traduzir(store, P2, F({"cross"}), 0, 0, 10.0 + i * 0.1)
        ab.traduzir(store, P2, F(), 0, 0, 10.05 + i * 0.1)
    ouvindo, passos = ab.gravar_estado(store)
    assert not ouvindo and len(passos) == ab.MAXIMO_DE_PASSOS
    ab.gravar_iniciar(store, P2, 100.0)
    ab.traduzir(store, P2, F({"cross"}), 0, 0, 100.0 + ab.MAXIMO_DA_GRAVACAO_S + 1)
    assert ab.gravar_estado(store) == (False, [])


def test_trocar_de_perfil_aborta_a_gravacao() -> None:
    store = SimpleNamespace()
    ab.gravar_iniciar(store, P2, 10.0)
    ab.definir_ativo(store, None)
    assert ab.gravar_estado(store) == (False, [])


def test_a_tabela_de_teclas_nao_dobra_a_gravacao() -> None:
    store = SimpleNamespace()
    ab.gravar_iniciar(store, P2, 10.0)
    b, _, _, _ = ab.traduzir(store, P2, F({"cross"}), 0, 0, 10.1, F(), espaco="tabela")
    assert b == F({"cross"})
    assert ab.gravar_estado(store) == (True, [])


# -- o «Tocar para ouvir» -----------------------------------------------------


def test_o_teste_toca_uma_vez_no_controle_pedido_e_se_apaga() -> None:
    store = SimpleNamespace()
    ab.tocar_agora(store, P2, {"passos": TRES}, 5.0)
    assert ab.alguma(store)
    no_p1 = ab.traduzir(store, P1, F(), 0, 0, 5.0)[0]
    assert no_p1 == F(), "o teste do P2 tocou no P1"
    visto: list[frozenset[str]] = []
    for i in range(60):
        visto.append(ab.traduzir(store, P2, F({"l1"}) if i == 0 else F(), 0, 0, 5.0 + i * 0.01)[0])
    assert _ordem(visto) == ["cross", "circle", "r1"]
    assert "l1" in visto[0], "o botão que a mão aperta segue junto do teste"
    assert not ab.alguma(store), "o teste acabou e o motor ficou ligado"


# -- o esquema e a recusa -----------------------------------------------------


def test_o_perfil_guarda_e_devolve_a_sequencia_do_perfil_e_da_peca() -> None:
    cheio = Profile.model_validate({
        "name": "Cheio", "match": {"type": "any"},
        ATIVACAO: {"sequencia": {"l1": {"passos": TRES, "jeito": "repete"}}},
        "controllers": {P2: {ATIVACAO: {"sequencia": {"r1": {"passos": TRES[:1]}}}}}})
    volta = Profile.model_validate(cheio.model_dump(mode="json"))
    assert volta.ativacao is not None and volta.ativacao.sequencia["l1"].jeito == "repete"
    assert volta.controllers is not None
    assert volta.controllers[P2].ativacao.sequencia["r1"].passos[0].botao == "cross"  # type: ignore[union-attr]
    sem = Profile.model_validate({"name": "Sem", "match": {"type": "any"},
                                  ATIVACAO: {"alternar": ["l1"]}})
    assert "sequencia" not in sem.model_dump(mode="json", exclude_unset=True)[ATIVACAO]


@pytest.mark.parametrize("secao", [
    {"sequencia": {"l1": {"passos": []}}},
    {"sequencia": {"l1": {"passos": [{"botao": "cross", "ms": 0}] * 33}}},
    {"sequencia": {"l1": {"passos": [{"botao": "cross", "ms": 5001}]}}},
    {"sequencia": {"l1": {"passos": [{"botao": "cross", "ms": -1}]}}},
    {"sequencia": {"l1": {"passos": [{"botao": "botao_que_nao_existe", "ms": 0}]}}},
    {"sequencia": {"botao_que_nao_existe": {"passos": [{"botao": "cross", "ms": 0}]}}},
    {"sequencia": {"l1": {"passos": [{"botao": "cross", "ms": 0}], "jeito": "sempre"}}},
    {"sequencia": {"l1": {"passos": [{"botao": "cross", "ms": 0}], "ritmo": "voando"}}},
    {"sequencia": {"l1": {"passos": [{"botao": "cross", "ms": 0}], "campo_novo": 1}}},
    {"alternar": ["l1"], "sequencia": {"l1": {"passos": [{"botao": "cross", "ms": 0}]}}},
    {"repetir": ["l1"], "sequencia": {"l1": {"passos": [{"botao": "cross", "ms": 0}]}}},
    {"longo": {"l1": "cross"}, "sequencia": {"l1": {"passos": [{"botao": "cross", "ms": 0}]}}},
])
def test_o_perfil_recusa_a_sequencia_que_o_motor_recusa(secao: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Profile.model_validate({"name": "X", "match": {"type": "any"}, ATIVACAO: secao})


def test_texto_e_sequencia_se_conversam_sem_perder_nada() -> None:
    seq = {"passos": TRES, "jeito": "alterna", "ritmo": "devagar"}
    texto = ab.sequencia_em_texto(seq)
    assert texto == "cross:80,circle:120,r1:0|alterna|devagar"
    assert ab.sequencia_do_texto(texto) == seq


# -- o IPC --------------------------------------------------------------------


class _Handlers(IpcHandlersMixin):
    def __init__(self) -> None:
        self.store = SimpleNamespace()  # type: ignore[assignment]


def _pedir(h: _Handlers, metodo: str, **params: Any) -> dict[str, Any]:
    return asyncio.run(getattr(h, f"_handle_{metodo}")(params))


def test_o_ipc_grava_e_devolve_os_passos() -> None:
    h = _Handlers()
    assert _pedir(h, "sequencia_gravar", acao="iniciar", uniq=P2)["gravando"] is True
    ab.traduzir(h.store, P2, F({"cross"}), 0, 0, 1.0)
    ab.traduzir(h.store, P2, F(), 0, 0, 1.05)
    ab.traduzir(h.store, P2, F({"circle"}), 0, 0, 1.2)
    ao_vivo = _pedir(h, "sequencia_gravar", acao="estado")
    assert ao_vivo["gravando"] is True and len(ao_vivo["passos"]) == 2
    fim = _pedir(h, "sequencia_gravar", acao="parar")
    assert fim == {"status": "ok", "gravando": False,
                   "passos": [{"botao": "cross", "ms": 200}, {"botao": "circle", "ms": 0}]}


def test_o_ipc_recusa_o_que_nao_entende() -> None:
    h = _Handlers()
    with pytest.raises(ValueError):
        _pedir(h, "sequencia_gravar", acao="dancar")
    with pytest.raises(ValueError):
        _pedir(h, "sequencia_gravar", acao="iniciar", uniq=3)
    with pytest.raises(ValueError, match="recusado"):
        _pedir(h, "sequencia_tocar", passos=[{"botao": "nada", "ms": 0}])
    with pytest.raises(ValueError, match="recusado"):
        _pedir(h, "sequencia_tocar", passos=[])
    with pytest.raises(ValueError, match="não conhece"):
        _pedir(h, "sequencia_tocar", passos=TRES, velocidade=9)


def test_o_ipc_toca_no_controle_pedido() -> None:
    h = _Handlers()
    r = _pedir(h, "sequencia_tocar", passos=TRES, ritmo="rapido", uniq=P2)
    assert r == {"status": "ok", "passos": 3}
    assert ab.alguma(h.store)
    t0 = time.monotonic()
    visto = [ab.traduzir(h.store, P2, F(), 0, 0, t0 + i * 0.01)[0] for i in range(40)]
    assert _ordem(visto) == ["cross", "circle", "r1"]


def test_o_servidor_publica_os_dois() -> None:
    fonte = (RAIZ / "src/hefesto_dualsense4unix/daemon/ipc_server.py").read_text(encoding="utf-8")
    for metodo in ("gravar", "tocar"):
        assert re.search(rf'"sequencia\.{metodo}":\s*self\._handle_sequencia_{metodo}', fonte), (
            f"o servidor não publica sequencia.{metodo}")


# -- a tela: gravar, ajustar, tocar e guardar ---------------------------------


def _ctx(escolhido: str = "p2") -> Any:
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


def _perfil_no_disco(**campos: Any) -> None:
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchManual

    loader.save_profile(Profile(name="Regua", match=MatchManual(), **campos))


def _ponte(chamadas: list[tuple[str, dict[str, Any]]]) -> Any:
    def resultado(metodo: str, **params: Any) -> dict[str, Any]:
        chamadas.append((metodo, params))
        if metodo == "sequencia.gravar":
            fim = params.get(ACAO) in ("parar", "estado")
            return {"status": "ok", "gravando": params.get(ACAO) != "parar",
                    "passos": TRES if fim else []}
        return {"status": "ok", "passos": len(params.get("passos") or [])}

    return SimpleNamespace(resultado=resultado)


def test_a_tela_grava_ajusta_toca_e_guarda_so_no_controle(
        mapa: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import MagicMock

    from hefesto_dualsense4unix.interface.pacotes import ponte
    from hefesto_dualsense4unix.profiles import loader

    _perfil_no_disco()
    chamadas: list[tuple[str, dict[str, Any]]] = []
    p = _ponte(chamadas)
    monkeypatch.setattr(ponte, "resultado", p.resultado)
    ctx = _ctx("p2")
    mapa.mapa_botao(ctx, {"b": "cross"}, None)
    mapa.mapa_sequencia_gravar(ctx, {}, p)
    assert chamadas[0] == ("sequencia.gravar", {ACAO: "iniciar", "uniq": "aabbcc000002"})
    mapa.mapa_sequencia_gravar(ctx, {}, p)
    assert chamadas[-1][1] == {ACAO: "parar"}
    mapa.mapa_sequencia_jeito(ctx, {"valor": "repete"}, p)
    mapa.mapa_sequencia_ritmo(ctx, {"valor": "rapido"}, p)
    mapa.mapa_sequencia_tocar(ctx, {}, p)
    assert chamadas[-1][0] == "sequencia.tocar" and chamadas[-1][1]["ritmo"] == "rapido"
    mapa.mapa_guardar(ctx, {}, MagicMock())
    gravado = loader.load_profile("Regua")
    assert gravado.ativacao is None, "o perfil inteiro ganhou a sequência do White"
    assert gravado.controllers is not None and set(gravado.controllers) == {P2}
    seq = gravado.controllers[P2].ativacao.sequencia["cross"]  # type: ignore[union-attr]
    assert (seq.jeito, seq.ritmo) == ("repete", "rapido")
    assert [(q.botao, q.ms) for q in seq.passos] == [("cross", 80), ("circle", 120), ("r1", 0)]
    no_white = mapa.pacote(_ctx("p2"))["mesa"]
    no_red = mapa.pacote(_ctx("p1"))["mesa"]
    assert str(no_white["atual-cross"]).startswith("sequencia:")
    assert not str(no_red["atual-cross"]).startswith("sequencia:"), "o Cosmic Red herdou"


def test_o_servico_que_cai_ao_parar_nao_leva_embora_o_que_a_tela_mostrava(
        mapa: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.interface.pacotes import ponte

    _perfil_no_disco()
    chamadas: list[tuple[str, dict[str, Any]]] = []
    p = _ponte(chamadas)
    monkeypatch.setattr(ponte, "resultado", p.resultado)
    ctx = _ctx("p2")
    mapa.mapa_botao(ctx, {"b": "cross"}, None)
    mapa.mapa_sequencia_gravar(ctx, {}, p)
    mapa._acompanha_a_gravacao()

    def cai(metodo: str, **params: Any) -> dict[str, Any]:
        raise OSError("o serviço parou")

    monkeypatch.setattr(ponte, "resultado", cai)
    mapa._parar_de_ouvir(mapa._estado())
    seq = mapa._estado()["seq"]["cross"]
    assert [q["botao"] for q in seq["passos"]] == ["cross", "circle", "r1"]
    assert mapa._estado().get("gravando") is None
    assert mapa._estado()["edicoes"]["cross"][0] == "sequencia", "a linha não guardou o rascunho"


def test_a_tela_recusa_tocar_sem_ter_gravado(mapa: Any) -> None:
    _perfil_no_disco()
    ctx = _ctx("p2")
    mapa.mapa_botao(ctx, {"b": "cross"}, None)
    with pytest.raises(RuntimeError, match="grave antes"):
        mapa.mapa_sequencia_tocar(ctx, {}, _ponte([]))
    with pytest.raises(ValueError):
        mapa.mapa_sequencia_jeito(ctx, {"valor": "sempre"}, _ponte([]))


def test_guardar_grava_a_sequencia_no_perfil_ou_so_no_controle(mapa: Any) -> None:
    prof = Profile.model_validate({"name": "x", "match": {"type": "manual"}})
    texto = "cross:80,circle:120|repete|rapido"
    no_perfil = mapa._aplicar_as_edicoes(prof, {"l1": ("sequencia", texto)}, {}, None)
    assert no_perfil.ativacao.sequencia["l1"].jeito == "repete"
    na_peca = mapa._aplicar_as_edicoes(prof, {"l1": ("sequencia", texto)}, {}, P2)
    assert na_peca.ativacao is None
    assert na_peca.controllers[P2].ativacao.sequencia["l1"].ritmo == "rapido"
    tirada = mapa._aplicar_as_edicoes(no_perfil, {"l1": ("nada", "")}, {}, None)
    assert tirada.ativacao is None, "soltar o botão devia levar a sequência embora"
    trocada = mapa._aplicar_as_edicoes(no_perfil, {"l1": ("troca", "cross")}, {}, None)
    assert trocada.ativacao is None and trocada.remapeamento == {"l1": "cross"}


def test_a_sequencia_numa_peca_que_o_perfil_ja_alterna_volta_como_frase(mapa: Any) -> None:
    prof = Profile.model_validate({"name": "x", "match": {"type": "manual"},
                                   ATIVACAO: {"alternar": ["l1"]}})
    with pytest.raises(RuntimeError):
        mapa._aplicar_as_edicoes(prof, {"l1": ("sequencia", "cross:0|uma_vez|gravado")}, {}, None)
