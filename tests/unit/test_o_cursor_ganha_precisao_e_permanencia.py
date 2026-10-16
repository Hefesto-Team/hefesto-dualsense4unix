#!/usr/bin/env python3
"""O cursor ganha precisão, permanência e clique travado (acessibilidade, 16/10/2026).

O motor está em `integrations/uinput_mouse.py` (o ajuste, o fator, a permanência e o
travador); a seção `cursor` do perfil, no esquema; a entrega ao device, nos dois caminhos que
o despacham (`dispatch_mouse` e `TabelaNoJogo.tick`); o depósito, em `apply_acessibilidade`.
O tempo é falso (`now`) e o device grava o que emitiu.

A MORDIDA, e cada uma foi rodada na entrega:

- ponha a zona morta e a curva de volta nas constantes (`_emit_move` sem passar as do ajuste) e
  :func:`test_a_zona_morta_e_a_curva_do_perfil_mudam_o_deslocamento` reprova;
- tire o `_fator` do `_emit_move` e :func:`test_a_precisao_reduz_o_stick_a_30_por_cento` reprova;
- tire o `_fator` do intervalo da rolagem e
  :func:`test_a_precisao_vale_para_o_toque_o_giro_e_a_rolagem` reprova;
- tire o `_andou` e :func:`test_a_permanencia_nao_clica_parada_sem_ter_andado` reprova;
- tire o `soltar_o_clique_travado` de `definir_ajuste` e
  :func:`test_o_clique_travado_solta_na_troca_de_perfil` reprova;
- tire o `_entregar_o_ajuste` de `dispatch_mouse` e
  :func:`test_o_dispatch_do_desktop_entrega_o_ajuste` reprova;
- tire o `definir_ajuste_ativo(…, None)` de `apagar_o_freestyle` e
  :func:`test_apagar_o_freestyle_sem_perfil_que_volte_larga_toda_a_acessibilidade` reprova;
- tire o `_soltar_o_travado` do topo de `despachar_no_jogo` e
  :func:`test_entrar_no_jogo_solta_o_clique_travado_do_mouse_do_desktop` reprova.
"""
from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.integrations import uinput_mouse as um
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    Profile,
    ProfileCursorConfig,
)

F = frozenset
PERIODO = 1.0 / um.DEFAULT_POLL_HZ


class _Gravador:
    """O nó do uinput: guarda `(código, valor)` na ordem em que saiu."""

    def __init__(self) -> None:
        self.emitidos: list[tuple[str, int]] = []

    def emit(self, codigo: str, valor: int, syn: bool = True) -> None:
        self.emitidos.append((codigo, valor))

    def syn(self) -> None:
        pass

    def destroy(self) -> None:
        pass

    def soma(self, codigo: str) -> int:
        return sum(v for c, v in self.emitidos if c == codigo)

    def conta(self, codigo: str, valor: int) -> int:
        return sum(1 for c, v in self.emitidos if (c, v) == (codigo, valor))


class _Modulo:
    """O módulo `uinput` de mentira: todo atributo é o próprio nome."""

    def __init__(self, no: _Gravador) -> None:
        self._no = no

    def Device(self, *_a: Any, **_k: Any) -> _Gravador:  # noqa: N802
        return self._no

    def __getattr__(self, nome: str) -> str:
        return nome


def _mouse(
    monkeypatch: pytest.MonkeyPatch, secao: Any = None, epoca: int = 1
) -> tuple[um.UinputMouseDevice, _Gravador]:
    no = _Gravador()
    monkeypatch.setitem(sys.modules, "uinput", _Modulo(no))
    dev = um.UinputMouseDevice()
    assert dev.start()
    dev.definir_ajuste(um.montar_o_ajuste(secao), epoca)
    return dev, no


def _cursor(**campos: Any) -> ProfileCursorConfig:
    return ProfileCursorConfig(**campos)


def _anda(dev: um.UinputMouseDevice, lx: int, ly: int = 128, ticks: int = 60,
          botoes: frozenset[str] = F(), l2: int = 0, t0: float = 0.0) -> float:
    """`ticks` tiques com o stick esquerdo em (lx, ly); devolve o relógio ao fim."""
    agora = t0
    for _ in range(ticks):
        dev.dispatch(lx=lx, ly=ly, rx=128, ry=128, l2=l2, r2=0, buttons=botoes, now=agora)
        agora += PERIODO
    return agora


def _parado(dev: um.UinputMouseDevice, t0: float, ate: float, botoes: frozenset[str] = F()) -> None:
    agora = t0
    while agora <= ate:
        dev.dispatch(lx=128, ly=128, rx=128, ry=128, l2=0, r2=0, buttons=botoes, now=agora)
        agora += PERIODO


def _esperado(lx: int, ly: int, ticks: int, zona: int = um.MOVE_DEADZONE,
              curva: float = um.MOUSE_EXPO, fator: float = 1.0) -> tuple[int, int]:
    """O deslocamento inteiro de `ticks` tiques, com o resto fracionário levado adiante."""
    carry_x = carry_y = 0.0
    total_x = total_y = 0
    for _ in range(ticks):
        vx, vy = um._compute_move_px_per_sec(lx, ly, um.DEFAULT_MOUSE_SPEED, zona, curva)
        carry_x += vx * PERIODO * fator
        carry_y += vy * PERIODO * fator
        ix, iy = int(carry_x), int(carry_y)
        carry_x -= ix
        carry_y -= iy
        total_x += ix
        total_y += iy
    return total_x, total_y


# -- o cursor sem ajuste é o de hoje --------------------------------------------------------


def test_o_perfil_sem_ajuste_anda_o_cursor_de_hoje(monkeypatch: pytest.MonkeyPatch) -> None:
    assert um.montar_o_ajuste(None) is None
    assert um.montar_o_ajuste(_cursor()) is None, "o padrão da seção é o cursor de hoje"
    dev, no = _mouse(monkeypatch)
    _anda(dev, 255, 200, 60)
    assert (no.soma("REL_X"), no.soma("REL_Y")) == _esperado(255, 200, 60)
    assert no.conta("BTN_LEFT", 1) == 0


def test_o_padrao_da_secao_e_a_zona_morta_e_a_curva_de_hoje() -> None:
    c = _cursor()
    assert (c.zona_morta, c.curva) == (um.MOVE_DEADZONE, um.MOUSE_EXPO)
    assert c.permanencia_ms == 0, "a permanência nasce desligada"
    assert c.precisao_botao is None and c.clique_travado is None


def test_a_zona_morta_e_a_curva_do_perfil_mudam_o_deslocamento(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    larga, no = _mouse(monkeypatch, _cursor(zona_morta=60))
    _anda(larga, 128 + 40, 128, 60)
    assert (no.soma("REL_X"), no.soma("REL_Y")) == (0, 0), "40 de 128 cai na zona morta de 60"
    de_hoje, hoje = _mouse(monkeypatch)
    _anda(de_hoje, 128 + 40, 128, 60)
    assert hoje.soma("REL_X") > 0, "com a zona de 20, o mesmo curso anda"
    linear, no = _mouse(monkeypatch, _cursor(curva=1.0))
    _anda(linear, 128 + 64, 128, 60)
    assert no.soma("REL_X") == _esperado(128 + 64, 128, 60, curva=1.0)[0]
    fechada, no2 = _mouse(monkeypatch, _cursor(curva=3.0))
    _anda(fechada, 128 + 64, 128, 60)
    assert no2.soma("REL_X") < no.soma("REL_X"), "a curva fechada afina o meio do curso"


# -- a precisão ---------------------------------------------------------------------------


def test_a_precisao_reduz_o_stick_a_30_por_cento(monkeypatch: pytest.MonkeyPatch) -> None:
    dev, no = _mouse(monkeypatch, _cursor(precisao_botao="l1", precisao=30))
    _anda(dev, 255, 255, 120, botoes=F({"l1"}))
    cheio, _ = _esperado(255, 255, 120)
    assert abs(no.soma("REL_X") - round(cheio * 0.3)) <= 1
    assert no.soma("REL_X") == _esperado(255, 255, 120, fator=0.3)[0]
    assert no.soma("REL_Y") == _esperado(255, 255, 120, fator=0.3)[1]


def test_solto_o_botao_o_cursor_volta_inteiro(monkeypatch: pytest.MonkeyPatch) -> None:
    dev, no = _mouse(monkeypatch, _cursor(precisao_botao="l1"))
    agora = _anda(dev, 255, 128, 30, botoes=F({"l1"}))
    devagar = no.soma("REL_X")
    _anda(dev, 255, 128, 30, t0=agora)
    assert no.soma("REL_X") - devagar >= _esperado(255, 128, 30)[0] - 1


def test_a_precisao_vale_para_o_toque_o_giro_e_a_rolagem(monkeypatch: pytest.MonkeyPatch) -> None:
    dev, no = _mouse(monkeypatch, _cursor(precisao_botao="l1", precisao=30))
    dev.dispatch(lx=128, ly=128, rx=128, ry=128, l2=0, r2=0, buttons=F({"l1"}), now=0.0)
    for _ in range(100):
        dev.emit_touchpad_move(10, 0, now=0.0)
        dev.emit_gyro_move(2.0, 0.0, now=0.0)
    cheio = um.UinputMouseDevice()
    fator = um.TOUCHPAD_SENSITIVITY * (dev.mouse_speed / um.DEFAULT_MOUSE_SPEED)
    do_toque = int(100 * 10 * fator * 0.3)
    do_giro = int(100 * 2.0 * 0.3)
    assert abs(no.soma("REL_X") - (do_toque + do_giro)) <= 2
    assert cheio._fator == 1.0
    # a rolagem: o intervalo de 50 ms vira 50/0,3 ms
    rapida, a = _mouse(monkeypatch, _cursor(clique_travado="l1"))
    devagar, b = _mouse(monkeypatch, _cursor(precisao_botao="l1", precisao=30))
    for i in range(100):
        rapida.dispatch(lx=128, ly=128, rx=128, ry=255, l2=0, r2=0, buttons=F(), now=i * 0.01)
        devagar.dispatch(
            lx=128, ly=128, rx=128, ry=255, l2=0, r2=0, buttons=F({"l1"}), now=i * 0.01)
    cheia, lenta = a.conta("REL_WHEEL", -1), b.conta("REL_WHEEL", -1)
    assert cheia >= 15, "sem precisão a rolagem anda a cada 50 ms"
    assert 0.2 * cheia <= lenta <= 0.45 * cheia, f"a 30 % esperava ~{cheia * 0.3:.0f}, veio {lenta}"


def test_o_botao_da_precisao_nao_clica_nem_vira_seta(monkeypatch: pytest.MonkeyPatch) -> None:
    clicando, no = _mouse(monkeypatch)
    clicando.dispatch(lx=128, ly=128, rx=128, ry=128, l2=0, r2=0, buttons=F({"cross"}), now=0.0)
    assert no.conta("BTN_LEFT", 1) == 1, "sem o ajuste, a Cruz clica"
    dev, gravado = _mouse(monkeypatch, _cursor(precisao_botao="cross"))
    dev.dispatch(lx=128, ly=128, rx=128, ry=128, l2=0, r2=0, buttons=F({"cross"}), now=0.0)
    assert gravado.conta("BTN_LEFT", 1) == 0, "a Cruz virou a precisão: não clica"
    seta, outro = _mouse(monkeypatch, _cursor(precisao_botao="dpad_up"))
    seta.dispatch(lx=128, ly=128, rx=128, ry=128, l2=0, r2=0, buttons=F({"dpad_up"}), now=0.0)
    assert outro.conta("KEY_UP", 1) == 0, "o d-pad virou a precisão: não vira seta"


def test_o_gatilho_como_precisao_vale_da_metade_do_curso(monkeypatch: pytest.MonkeyPatch) -> None:
    dev, no = _mouse(monkeypatch, _cursor(precisao_botao="l2", precisao=30))
    dev.dispatch(lx=128, ly=128, rx=128, ry=128, l2=um.PRECISAO_DO_GATILHO - 1, r2=0,
                 buttons=F(), now=0.0)
    dev.emit_gyro_move(10.0, 0.0, now=0.0)
    assert no.soma("REL_X") == 10, "abaixo da metade do curso, o cursor segue inteiro"
    dev.dispatch(lx=128, ly=128, rx=128, ry=128, l2=um.PRECISAO_DO_GATILHO, r2=0,
                 buttons=F(), now=0.1)
    antes = no.soma("REL_X")
    dev.emit_gyro_move(10.0, 0.0, now=0.1)
    assert no.soma("REL_X") - antes == 3, "da metade do curso em diante, a 30 %"
    assert no.conta("BTN_LEFT", 1) == 0, "o gatilho da precisão também não clica"


# -- a permanência ---------------------------------------------------------------------------


def test_a_permanencia_clica_uma_vez_aos_800_ms(monkeypatch: pytest.MonkeyPatch) -> None:
    dev, no = _mouse(monkeypatch, _cursor(permanencia_ms=800))
    parou = _anda(dev, 255, 128, 10) - PERIODO
    _parado(dev, parou + PERIODO, parou + 0.79)
    assert no.conta("BTN_LEFT", 1) == 0, "antes dos 800 ms parado, nada"
    _parado(dev, parou + 0.79, parou + 0.85)
    assert (no.conta("BTN_LEFT", 1), no.conta("BTN_LEFT", 0)) == (1, 1)
    _parado(dev, parou + 0.86, parou + 5.0)
    assert no.conta("BTN_LEFT", 1) == 1, "parado de novo não clica de novo"
    _anda(dev, 255, 128, 5, t0=parou + 6.0)
    _parado(dev, parou + 6.1, parou + 7.5)
    assert no.conta("BTN_LEFT", 1) == 2, "andou de novo e parou: um clique novo"


def test_a_permanencia_nao_clica_parada_sem_ter_andado(monkeypatch: pytest.MonkeyPatch) -> None:
    dev, no = _mouse(monkeypatch, _cursor(permanencia_ms=800))
    _parado(dev, 0.0, 10.0)
    assert no.conta("BTN_LEFT", 1) == 0


def test_a_permanencia_nasce_desligada(monkeypatch: pytest.MonkeyPatch) -> None:
    dev, no = _mouse(monkeypatch, _cursor(precisao_botao="l1"))
    parou = _anda(dev, 255, 128, 10)
    _parado(dev, parou, parou + 10.0)
    assert no.conta("BTN_LEFT", 1) == 0
    ajuste = um.montar_o_ajuste(_cursor(permanencia_ms=800))
    assert ajuste is not None and ajuste.permanencia_s == pytest.approx(0.8)


def test_a_permanencia_nao_clica_por_cima_do_clique_apertado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dev, no = _mouse(monkeypatch, _cursor(permanencia_ms=800))
    parou = _anda(dev, 255, 128, 10, botoes=F({"cross"}))
    _parado(dev, parou, parou + 3.0, botoes=F({"cross"}))
    assert no.conta("BTN_LEFT", 1) == 1, "só o clique real, com a Cruz segurada"
    assert no.conta("BTN_LEFT", 0) == 0


# -- o clique travado ------------------------------------------------------------------------


def _tique(dev: um.UinputMouseDevice, agora: float, botoes: frozenset[str] = F()) -> None:
    dev.dispatch(lx=128, ly=128, rx=128, ry=128, l2=0, r2=0, buttons=botoes, now=agora)


def test_o_clique_travado_prende_num_toque_e_solta_no_outro(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dev, no = _mouse(monkeypatch, _cursor(clique_travado="triangle"))
    _tique(dev, 0.0, F({"triangle"}))
    _tique(dev, 0.1)
    _tique(dev, 0.2)
    assert (no.conta("BTN_LEFT", 1), no.conta("BTN_LEFT", 0)) == (1, 0), "prendeu e segura"
    _tique(dev, 0.3, F({"triangle"}))
    _tique(dev, 0.4)
    assert (no.conta("BTN_LEFT", 1), no.conta("BTN_LEFT", 0)) == (1, 1), "o outro toque soltou"
    assert no.conta("BTN_RIGHT", 1) == 0, "o botão do travador é do cursor: não clica à direita"


def test_o_clique_travado_soma_com_o_clique_de_verdade(monkeypatch: pytest.MonkeyPatch) -> None:
    dev, no = _mouse(monkeypatch, _cursor(clique_travado="triangle"))
    _tique(dev, 0.0, F({"triangle"}))
    _tique(dev, 0.1, F({"cross"}))
    _tique(dev, 0.2)
    assert no.conta("BTN_LEFT", 0) == 0, "soltar a Cruz não solta o clique preso"
    _tique(dev, 0.3, F({"triangle"}))
    _tique(dev, 0.4)
    assert no.conta("BTN_LEFT", 0) == 1


def test_o_clique_travado_solta_na_troca_de_perfil(monkeypatch: pytest.MonkeyPatch) -> None:
    dev, no = _mouse(monkeypatch, _cursor(clique_travado="triangle"))
    _tique(dev, 0.0, F({"triangle"}))
    _tique(dev, 0.1)
    assert no.conta("BTN_LEFT", 0) == 0
    dev.definir_ajuste(um.montar_o_ajuste(_cursor(clique_travado="triangle")), 1)
    assert no.conta("BTN_LEFT", 0) == 0, "o mesmo perfil no mesmo tique não solta"
    dev.definir_ajuste(um.montar_o_ajuste(_cursor(clique_travado="triangle")), 2)
    assert no.conta("BTN_LEFT", 0) == 1, "uma ativação nova (época nova) solta"
    dev.definir_ajuste(None, 3)
    _tique(dev, 0.2)
    assert no.conta("BTN_LEFT", 1) == 1, "e nada prende de novo"


def test_o_clique_travado_solta_ao_trocar_a_tabela_e_ao_parar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dev, no = _mouse(monkeypatch, _cursor(clique_travado="triangle"))
    _tique(dev, 0.0, F({"triangle"}))
    dev.set_button_actions({"cross": "BTN_LEFT"})
    assert no.conta("BTN_LEFT", 0) == 1, "a tabela nova larga o que a velha segurava"
    _tique(dev, 0.1)
    _tique(dev, 0.2, F({"triangle"}))
    dev.stop()
    assert dev._preso is False
    assert dev.start()
    _tique(dev, 1.0)
    assert dev._codigos_apertados == F()


def test_o_clique_travado_solta_apos_silencio_do_controle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dev, no = _mouse(monkeypatch, _cursor(clique_travado="triangle"))
    _tique(dev, 0.0, F({"triangle"}))
    _tique(dev, 0.5)
    assert no.conta("BTN_LEFT", 0) == 0
    _tique(dev, 0.5 + um.TRAVA_SEM_NOTICIA_S + 0.5)
    assert no.conta("BTN_LEFT", 0) == 1, "o controle sumiu por mais de um segundo"


def test_soltar_o_cursor_solta_o_mouse_do_desktop_e_o_da_tabela(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hefesto_dualsense4unix.daemon.subsystems import mouse

    do_desktop, no = _mouse(monkeypatch, _cursor(clique_travado="triangle"))
    da_tabela, outro = _mouse(monkeypatch, _cursor(clique_travado="triangle"))
    _tique(do_desktop, 0.0, F({"triangle"}))
    _tique(da_tabela, 0.0, F({"triangle"}))
    tabela = SimpleNamespace(_mouse=da_tabela)
    mouse.soltar_o_cursor(SimpleNamespace(_mouse_device=do_desktop, _tabela_no_jogo=tabela))
    assert (no.conta("BTN_LEFT", 0), outro.conta("BTN_LEFT", 0)) == (1, 1)
    mouse.soltar_o_cursor(SimpleNamespace())


# -- o esquema --------------------------------------------------------------------------------


def test_o_esquema_aceita_a_faixa_e_recusa_o_resto() -> None:
    _cursor(zona_morta=0, curva=1.0, precisao=10, permanencia_ms=0)
    _cursor(zona_morta=60, curva=3.0, precisao=100, permanencia_ms=3000)
    _cursor(permanencia_ms=300)
    for ruim in (
        {"zona_morta": 61}, {"zona_morta": -1}, {"curva": 0.9}, {"curva": 3.1},
        {"precisao": 9}, {"precisao": 101},  # (noqa-acento)
        {"permanencia_ms": 100},
        {"permanencia_ms": 3001}, {"nao_existe": 1},
    ):
        with pytest.raises(ValidationError):
            _cursor(**ruim)


def test_o_esquema_recusa_botao_que_o_controle_nao_tem_e_o_mesmo_botao_em_dois_oficios() -> None:
    for ruim in (
        {"precisao_botao": "l3_direcao"}, {"clique_travado": "r3_direcao"},
        {"precisao_botao": "xis"}, {"clique_travado": "ps"},
    ):
        with pytest.raises(ValidationError):
            _cursor(**ruim)
    with pytest.raises(ValidationError):
        _cursor(precisao_botao="l1", clique_travado="l1")
    _cursor(precisao_botao="l2", clique_travado="r2")


def test_o_perfil_guarda_a_secao_e_o_controle_nao_tem_cursor() -> None:
    p = Profile.model_validate({
        "name": "P", "match": {"type": "any"}, "cursor": {"permanencia_ms": 800}})
    assert p.cursor is not None and p.cursor.permanencia_ms == 800
    assert Profile.model_validate({"name": "Q", "match": {"type": "any"}}).cursor is None
    with pytest.raises(ValidationError):
        ControllerOverrides.model_validate({"cursor": {"permanencia_ms": 800}})


# -- o depósito pelo perfil e o computador por baixo ----------------------------------------


def test_o_perfil_seguinte_larga_o_ajuste_do_anterior(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles import manager as gerente

    store = StateStore()
    m = gerente.ProfileManager(controller=SimpleNamespace(), store=store)  # type: ignore[arg-type]
    for nome_do_metodo in ("apply", "apply_keyboard", "apply_button_actions", "apply_emulation"):
        monkeypatch.setattr(m, nome_do_metodo, lambda *a, **k: None)
    com = Profile.model_validate({
        "name": "Com Cursor", "match": {"type": "any"},
        "cursor": {"precisao_botao": "l2", "permanencia_ms": 800}})
    sem = Profile.model_validate({"name": "Sem Cursor", "match": {"type": "any"}})
    monkeypatch.setattr(gerente, "load_profile", lambda nome: com)
    relatorio: dict[str, str] = {}
    m.activate("Com Cursor", origin="system", relatorio=relatorio)
    assert relatorio["acessibilidade"] == "aplicado"
    ajuste, epoca = um.ajuste_ativo(store)
    assert ajuste is not None and ajuste.precisao_botao == "l2"
    assert ajuste.permanencia_s == pytest.approx(0.8)
    monkeypatch.setattr(gerente, "load_profile", lambda nome: sem)
    m.activate("Sem Cursor", origin="system")
    larga, depois = um.ajuste_ativo(store)
    assert larga is None, "o perfil seguinte deixou o ajuste do anterior"
    assert depois > epoca, "cada ativação conta uma época nova"


def test_apagar_o_freestyle_sem_perfil_que_volte_larga_toda_a_acessibilidade() -> None:
    """O Freestyle apagado sem perfil para voltar: nada dele segue valendo sem perfil ativo."""
    from hefesto_dualsense4unix.core import ativacao_de_botao as ab
    from hefesto_dualsense4unix.core import curva_do_analogico as cv
    from hefesto_dualsense4unix.core import filtro_de_botao as fb
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles import manager as gerente

    store = StateStore()
    m = gerente.ProfileManager(controller=SimpleNamespace(), store=store)  # type: ignore[arg-type]
    m.apply_acessibilidade(Profile.model_validate({
        "name": "Freestyle", "match": {"type": "any"},
        "ativacao": {"alternar": ["l1"], "repique_ms": 120},  # (noqa-acento)
        "analogicos": {"zona_morta": 20},  # (noqa-acento)
        "cursor": {"clique_travado": "triangle"}}))
    _, epoca = um.ajuste_ativo(store)
    assert ab.alguma(store) and fb.alguma(store) and cv.alguma(store)
    assert um.ajuste_ativo(store)[0] is not None
    m.apagar_o_freestyle(None)
    assert not (ab.alguma(store) or fb.alguma(store)), "o botão do Freestyle seguiu valendo"
    assert not cv.alguma(store), "a curva do Freestyle seguiu valendo sem perfil"
    larga, depois = um.ajuste_ativo(store)
    assert larga is None and depois > epoca, "o cursor do Freestyle seguiu valendo sem perfil"


def test_o_computador_vale_por_baixo_e_o_conflito_fica_com_o_jogo() -> None:
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import perfil_que_vale
    from hefesto_dualsense4unix.utils.maquina import ComputadorDeclarado

    computador = ComputadorDeclarado.model_validate({
        "global": {"cursor": {"precisao_botao": "l1", "permanencia_ms": 800}}})
    sem_nada = Profile.model_validate({"name": "Jogo", "match": {"type": "any"}})
    vale = perfil_que_vale(sem_nada, computador)
    assert vale.cursor is not None
    assert (vale.cursor.precisao_botao, vale.cursor.permanencia_ms) == ("l1", 800)
    do_jogo = Profile.model_validate({
        "name": "Jogo", "match": {"type": "any"}, "cursor": {"clique_travado": "l1"}})
    vale = perfil_que_vale(do_jogo, computador)
    assert vale.cursor is not None
    assert vale.cursor.clique_travado == "l1" and vale.cursor.precisao_botao is None, (
        "o mesmo botão em dois ofícios: fica o que o jogo escreveu")


# -- a entrega ao device ----------------------------------------------------------------------


def _estado() -> Any:
    return SimpleNamespace(
        raw_lx=255, raw_ly=128, raw_rx=128, raw_ry=128, l2_raw=0, r2_raw=0)


def test_o_dispatch_do_desktop_entrega_o_ajuste(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.subsystems import mouse

    dev, no = _mouse(monkeypatch)
    store = SimpleNamespace()
    um.definir_ajuste_ativo(store, um.montar_o_ajuste(_cursor(precisao_botao="l1", precisao=30)))
    daemon = SimpleNamespace(_mouse_device=dev, store=store, _touchpad_reader=None)
    for _ in range(60):
        mouse.dispatch_mouse(daemon, _estado(), F({"l1"}))
    assert no.soma("REL_X") < _esperado(255, 128, 60)[0] * 0.5, "o ajuste não chegou ao device"
    # o perfil seguinte (sem ajuste) devolve o cursor inteiro
    um.definir_ajuste_ativo(store, None)
    antes = no.soma("REL_X")
    mouse.dispatch_mouse(daemon, _estado(), F({"l1"}))
    assert no.soma("REL_X") - antes >= 1 and dev._ajuste is None


def test_a_tabela_com_o_jogo_entrega_o_ajuste_e_solta_o_clique_travado() -> None:
    from hefesto_dualsense4unix.daemon.subsystems import mouse

    visto: list[Any] = []
    soltou: list[bool] = []
    tabela = mouse.TabelaNoJogo(None, None, ligada=True)
    tabela._mouse = SimpleNamespace(
        dispatch=lambda **kw: None,
        definir_ajuste=lambda ajuste, epoca: visto.append((ajuste, epoca)),
        soltar_o_clique_travado=lambda: soltou.append(True),
    )
    tabela._teclado = SimpleNamespace(dispatch=lambda b: None)
    store = SimpleNamespace()
    um.definir_ajuste_ativo(store, um.montar_o_ajuste(_cursor(clique_travado="l1")))
    daemon = SimpleNamespace(store=store, controller=SimpleNamespace(primary_uniq=None))
    tabela.tick(daemon, _estado(), F())
    assert visto and visto[-1][0] is not None and visto[-1][0].clique_travado == "l1"
    tabela.soltar()
    assert soltou, "sair do jogo tem de soltar o clique que o travador segura"


@pytest.mark.parametrize("suspenso", [False, True], ids=["com-a-emulacao", "suspensa-por-ela"])
def test_entrar_no_jogo_solta_o_clique_travado_do_mouse_do_desktop(
    monkeypatch: pytest.MonkeyPatch, suspenso: bool,
) -> None:
    """Com o pad do jogo despachando, o laço para de despachar o mouse do desktop.

    Sem esta soltura, o botão esquerdo que o travador prendeu fica apertado o jogo inteiro: a
    soltura por silêncio do device só roda quando ele volta a ser despachado.
    """
    from hefesto_dualsense4unix.daemon.subsystems import mouse

    dev, no = _mouse(monkeypatch, _cursor(clique_travado="triangle"))
    _tique(dev, 0.0, F({"triangle"}))
    _tique(dev, 0.1)
    daemon = SimpleNamespace(
        _mouse_device=dev, _tabela_no_jogo=None, _emulation_suppressed=suspenso)
    mouse.despachar_no_jogo(daemon, _estado(), F(), no_jogo=False)
    assert no.conta("BTN_LEFT", 0) == 0, "fora do jogo o mouse do desktop segue preso"
    mouse.despachar_no_jogo(daemon, _estado(), F(), no_jogo=True)
    assert no.conta("BTN_LEFT", 0) == 1, "o jogo abriu com o clique do desktop preso"
    mouse.despachar_no_jogo(daemon, _estado(), F(), no_jogo=True)
    assert no.conta("BTN_LEFT", 0) == 1, "a soltura é uma só"
