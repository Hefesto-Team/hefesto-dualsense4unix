#!/usr/bin/env python3
"""NO-DESLIGADO-A-STEAM-NAO-SE-METE-E-O-JOGO-MANDA-01 — Nativo e Steam Input no Desligado.

A escolha, 08/10/2026 (`ESCOLHAS.md`, opção a mudada): *«Desligar o hefesto
= Nativo na origem. Steam Input sai de Ligado.»* Com o Hefesto Ligado, os botões
são Sony DualSense, Xbox e Navegação; com ele Desligado, Nativo e Steam Input,
no mesmo estilo. O Nativo tira o jogo da vez da lista do Steam Input e o
`localconfig.vdf` fica em `"0"`; o guarda do vdf repete isso para todo jogo fora
da lista a cada saída da Steam (`scripts/disable_steam_input.sh --apply-quiet`).

O LAR É O DA RÉGUA DA STEAM-INPUT-01 (Steam de mentira em `tmp_path`, com
`localconfig.vdf` sintético), e o daemon de mentira é o da régua da fileira:
o plano do clique chega ao `state` que o tique lê.
"""
from __future__ import annotations

import re

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.integrations import steam_input_ponte as ponte
from hefesto_dualsense4unix.interface import aba01, onde
from hefesto_dualsense4unix.interface.pacotes import a01_jogar as aba
from tests.unit.test_o_modo_sai_do_steam_input import (  # noqa: F401
    DaemonDeMentira,
    _a_maquina,
    _aceso,
    _clicar,
    _ctx,
    _parar_a_vigia,
    _ponte_de_pe,
    _sem_pendencia,
)
from tests.unit.test_steam_input_01_o_chip_que_acende_por_jogo import (  # noqa: F401
    APPID,
    _steam_fechada,
    _valor,
    _vigia_limpa,
    lar,
)


def _secao(corpo: str, classe: str) -> str:
    """O miolo do `<div class="hef-modo {classe}">` da bancada."""
    achado = re.search(
        rf'<div class="hef-modo {classe}">\s*<div class="escada">(.*?)</div>',
        corpo, re.S)
    assert achado, f"a seção `{classe}` sumiu da bancada da 01"
    return achado.group(1)


def test_os_botoes_de_cada_lado_do_interruptor() -> None:
    """Ligado: DualSense, Xbox e Point and click. Desligado: Nativo, Steam Input e Navegação.

    A Navegação mudou de lado no todo de 15/10/2026 (A-ABA-JOGAR-DO-TODO-01, opção A).

    A MORDIDA: devolva o «Steam Input» ao `aba01.MODOS` (ou a faixa fixa do
    «Modo Nativo» ao Desligado) e a régua reprova.
    """
    corpo = onde.pagina("01-jogar.html").read_text(encoding="utf-8")
    ligado = re.findall(r'data-gesto="(modo-[a-z-]+)"', _secao(corpo, "so-ligado"))
    desligado = _secao(corpo, "so-desligado")
    assert ligado == ["modo-dualsense", "modo-xbox", "modo-point-and-click"], ligado
    assert re.findall(r'data-gesto="(modo-[a-z-]+)"', desligado) == [
        "modo-nativo", "modo-steam", "modo-navegacao"]
    classes = re.findall(r'<span class="([^"]+)"[^>]*data-gesto="modo-', desligado)
    assert [c.replace(" on", "") for c in classes] == ["degrau"] * 3, (
        f"os botões do Desligado não têm o estilo dos do Ligado: {classes}")
    assert "fixo" not in desligado and "Modo Nativo" not in desligado


def test_a_tabela_dos_dois_botoes_do_desligado() -> None:
    """Os dois são o modo `native`; só o Steam Input põe o jogo na lista."""
    assert tuple(aba.o_que_o_chip_faz(aba.CHIP_DO_NATIVO)) == ("native", None, False)
    assert tuple(aba.o_que_o_chip_faz(aba.CHIP_DO_STEAM_INPUT)) == ("native", None, True)


@pytest.mark.parametrize("jogo_aberto", [False, True], ids=["jogo-fechado", "jogo-aberto"])
def test_o_nativo_tira_a_steam_do_jogo(lar, monkeypatch, jogo_aberto) -> None:  # noqa: F811
    """Com o jogo na lista e a ponte de pé, o «Nativo» grava `"0"` e acende.

    A MORDIDA: faça a linha do Nativo em `o_que_o_chip_faz` pôr o jogo na lista
    (`steam_input=True`) e a régua reprova: o jogo fica na lista, o vdf fica em
    Steam Input e acende o «Steam Input».
    """
    _ponte_de_pe()
    _a_maquina(monkeypatch, jogo_aberto=jogo_aberto, steam_aberta=False)
    ctx = _ctx(aberto=jogo_aberto, modo="native")
    daemon = DaemonDeMentira(ctx.state, jogo_aberto=jogo_aberto)
    _parar_a_vigia(monkeypatch)
    assert _aceso(ctx) == aba.CHIP_DO_STEAM_INPUT

    _clicar(aba.CHIP_DO_NATIVO, ctx, daemon)

    assert APPID not in ponte.ler_allowlist(), "o «Nativo» deixou o jogo na lista"
    assert _valor(lar, APPID) == ponte.DESLIGADO, (
        f"a Steam fechada e o vdf ficou {_valor(lar, APPID)!r} depois do «Nativo»")
    assert _aceso(ctx) == aba.CHIP_DO_NATIVO
    assert ctx.state["native_mode"] is True


def test_o_steam_input_do_desligado_nao_liga_o_hefesto(lar, monkeypatch) -> None:  # noqa: F811
    """O «Steam Input» manda o modo `native`, e nunca o gamepad virtual.

    A MORDIDA: devolva ao «Steam Input» a linha antiga (gamepad + DualSense) e o
    plano liga o gamepad virtual: o interruptor sai do Desligado.
    """
    _a_maquina(monkeypatch, jogo_aberto=False, steam_aberta=False)
    ctx = _ctx(aberto=False, modo="native")
    daemon = DaemonDeMentira(ctx.state)
    _parar_a_vigia(monkeypatch)

    _clicar(aba.CHIP_DO_STEAM_INPUT, ctx, daemon)

    assert ctx.state["native_mode"] is True
    assert ctx.state["gamepad_emulation"]["enabled"] is False
    assert APPID in ponte.ler_allowlist()
    assert _valor(lar, APPID) == ponte.LIGADO
    assert aba.pacote(ctx)["hef-posicao"] == "desligado"
    assert _aceso(ctx) == aba.CHIP_DO_STEAM_INPUT


def test_no_ligado_a_lista_nao_acende_o_steam_input(lar) -> None:  # noqa: F811
    """Com o Hefesto Ligado o Steam Input não é botão: acende o caminho vivo."""
    _ponte_de_pe()
    fora = aba._estado_da_tela(_ctx(aberto=True).state)
    assert (fora["hef-posicao"], fora["modo-aceso"], fora["steam-input-aceso"]) == (
        "ligado", "dualsense", "")


def test_o_gerador_le_o_nativo_do_dono() -> None:
    """O rótulo e a chave do Nativo têm um dono só, o pacote da aba."""
    nativo = next(m for m in aba01.DO_DESLIGADO if m["chave"] == aba.CHIP_DO_NATIVO)
    assert nativo["rot"] == aba.ROTULO_DO_NATIVO == aba._rotulo_do_chip(aba.CHIP_DO_NATIVO)
