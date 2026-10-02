#!/usr/bin/env python3
"""A FITA `Selecionar:` — que ela diga o que a aba faz, e que deixe escolher."""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (RAIZ / "src", RAIZ / "src/hefesto_dualsense4unix/interface"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"
MESA = [
    {"pref": "p1", "jogador": 1, "uniq": P1, "nome": "Cosmic Red", "via": "USB",
     "cor": "cosmic-red", "transporte": "usb"},
    {"pref": "p2", "jogador": 2, "uniq": P2, "nome": "Starlight Blue", "via": "BT",
     "cor": "starlight-blue", "transporte": "bt"},
]


@pytest.fixture(scope="module")
def hv():
    """O piloto DE VERDADE, importado — sem abrir janela nenhuma."""
    pytest.importorskip("gi", reason="o piloto precisa do PyGObject do sistema")
    from hefesto_dualsense4unix.interface import hefesto_vivo

    return hefesto_vivo


@pytest.fixture(autouse=True)
def escolha_limpa(hv):
    """A escolha é de MÓDULO — sem isto um teste herdaria o clique do anterior."""
    antes = hv.ESCOLHA_DA_FITA.uniq
    hv.ESCOLHA_DA_FITA.uniq = ""
    yield
    hv.ESCOLHA_DA_FITA.uniq = antes


def _monta():
    from hefesto_dualsense4unix.interface import monta

    return monta


def _paginas() -> list[str]:
    return [f"{a}.html" for _, a in _monta().ABAS]


@pytest.mark.parametrize("pagina", _paginas())  # noqa-acento (nome de parâmetro)
def test_a_fita_de_leitura_nasce_e_continua_esmaecida(hv, pagina):
    """O que o piloto REPINTA tem de concordar com o que o arquivo publica."""
    monta = _monta()
    vivo = hv._fita(MESA, pagina)
    assert vivo, f"{pagina}: `_fita` devolveu vazio — a fita ficaria no desenho"

    escolhe = monta.a_fita_escolhe(pagina)
    tem_inerte = 'class="fita inerte"' in vivo
    assert tem_inerte is (not escolhe), (
        f"{pagina}: a fita repintada {'PERDEU' if escolhe else 'GANHOU'} o "
        f"`inerte` — `monta.ABAS_QUE_ESCOLHEM` diz escolhe={escolhe}")

    publicado = (RAIZ / "src/hefesto_dualsense4unix/interface/paginas" / pagina)
    arquivo = publicado.read_text(encoding="utf-8")
    do_arquivo = re.search(r'<div class="(fita(?: inerte)?)"', arquivo)
    assert do_arquivo, f"{pagina}: não achei a `.fita` no HTML publicado"
    assert (do_arquivo.group(1) == "fita inerte") is tem_inerte, (
        f"{pagina}: o arquivo publica `{do_arquivo.group(1)}` e o produto "
        f"repinta o contrário — é a tela mudando de opinião no primeiro tique")


@pytest.mark.parametrize("pagina", _paginas())  # noqa-acento (nome de parâmetro)
def test_o_titulo_da_fita_nao_promete_o_que_a_aba_nao_faz(hv, pagina):
    """O `title` é a frase que ela lê ao passar o rato. Ele segue o `inerte`."""
    vivo = hv._fita(MESA, pagina)
    escolhe = _monta().a_fita_escolhe(pagina)
    promete = "vai para o controle escolhido aqui" in vivo
    assert promete is escolhe, (
        f"{pagina}: o `title` da fita {'promete' if promete else 'nega'} "
        f"escolha e a aba escolhe={escolhe}")


@pytest.mark.parametrize("pagina", _paginas())  # noqa-acento (nome de parâmetro)
def test_o_chip_e_um_controle(hv, pagina):
    """`<label>` nas dez, e `data-gesto` só nas que escolhem."""
    monta = _monta()
    vivo = hv._fita(MESA, pagina)
    assert '<span class="chip' not in vivo, (
        f"{pagina}: o chip voltou a ser `<span>` — um `<span>` não clica, e foi "
        f"assim que a fita mostrou o escolhido sem deixar escolher")
    quantos = vivo.count('<label class="chip')
    assert quantos == 3, (
        f"{pagina}: esperava 3 chips (Todos + dois da mesa) e vi {quantos}")

    tem_gesto = f'data-gesto="{monta.GESTO_DA_FITA}"' in vivo
    assert tem_gesto is monta.a_fita_escolhe(pagina), (
        f"{pagina}: o endereço do clique {'está' if tem_gesto else 'falta'} "
        f"numa fita que escolhe={monta.a_fita_escolhe(pagina)}")


def test_o_chip_leva_o_pref_de_quem_ele_e(hv):
    """Sem `data-pref` o clique chegaria ao Python sem dizer em quem clicou."""
    vivo = hv._fita(MESA, "02-controles.html")
    assert re.search(r'data-pref="todos"', vivo)
    for c in MESA:
        assert f'data-pref="{c["pref"]}"' in vivo, f'faltou o {c["pref"]}'


def _ctx(mesa):
    from hefesto_dualsense4unix.interface import pacotes

    return pacotes.Contexto(state={}, mesa=mesa, conectados=mesa)


def test_o_clique_no_chip_move_o_alvo(hv):
    """Antes desta cura o alvo era SEMPRE `mesa[0]` — clicar não movia nada."""
    assert hv._pref_escolhido(MESA) == "p1", "sem escolha, o primeiro da mesa"
    hv._escolher_na_fita(_ctx(MESA), {"pref": "p2"}, None)
    assert hv._pref_escolhido(MESA) == "p2", (
        "o clique no chip do P2 não moveu o alvo — é o produto de antes de "
        "05/09/2026, em que o `Selecionar:` mostrava sem deixar escolher")
    hv._escolher_na_fita(_ctx(MESA), {"pref": "p1"}, None)
    assert hv._pref_escolhido(MESA) == "p1", "e ele volta quando ela clica de volta"


def test_a_fita_acende_o_chip_que_ela_escolheu(hv):
    """A prova na TELA: o `on` sai de um chip e entra no outro."""
    hv._escolher_na_fita(_ctx(MESA), {"pref": "p2"}, None)
    vivo = hv._fita(MESA, "02-controles.html")
    aceso = re.findall(r'<label class="chip[^"]*\bon"[^>]*data-pref="([a-z0-9]+)"',
                       vivo)
    assert aceso == ["p2"], f"acesos={aceso} — esperava só o chip do P2"


def test_a_escolha_segue_o_aparelho_e_nao_a_posicao(hv):
    """`pref` é POSIÇÃO e reenumera a cada tique; a escolha é guardada por `uniq`."""
    hv._escolher_na_fita(_ctx(MESA), {"pref": "p2"}, None)
    so_o_segundo = [{**MESA[1], "pref": "p1"}]
    assert hv._pref_escolhido(so_o_segundo) == "p1"
    vivo = hv._fita(so_o_segundo, "02-controles.html")
    assert "Starlight Blue" in vivo


def test_a_escolha_nao_e_apagada_quando_o_controle_sai(hv):
    """Ela sobrevive à ausência e volta quando o aparelho volta."""
    hv._escolher_na_fita(_ctx(MESA), {"pref": "p2"}, None)
    assert hv._pref_escolhido([MESA[0]]) == "p1", "sem ele, desenha o que há"
    assert hv._pref_escolhido(MESA) == "p2", "e volta a ser ele quando ele volta"


def test_o_chip_de_quem_nao_esta_na_mesa_recusa_dizendo(hv):
    """Escolher calado o que sobrou é como a tela mostra um e mexe noutro."""
    with pytest.raises(ValueError, match="não está na mesa"):
        hv._escolher_na_fita(_ctx(MESA), {"pref": "p4"}, None)
    assert hv.ESCOLHA_DA_FITA.uniq == "", "a recusa não pode ter mexido na escolha"


def test_o_todos_so_se_escolhe_quando_ha_o_que_agrupar(hv):
    """Com um controle só na mesa ele É a escolha — `monta.cabe_o_todos`."""
    hv._escolher_na_fita(_ctx(MESA), {"pref": "todos"}, None)
    assert hv._pref_escolhido(MESA) == "todos"
    with pytest.raises(ValueError, match="Todos"):
        hv._escolher_na_fita(_ctx([MESA[0]]), {"pref": "todos"}, None)


def test_o_gesto_do_chip_tem_dono_nas_dez_abas(hv):
    """Sem dono no despachante o clique sai como *"gesto sem dono"* na tela."""
    from hefesto_dualsense4unix.interface import pacotes

    for pagina in _paginas():
        assert pacotes.gesto_da_pagina(pagina, _monta().GESTO_DA_FITA) is not None, (
            f"{pagina}: o chip da fita clicaria e ninguém atenderia")


def test_quem_diz_se_a_aba_escolhe_para_diante_de_pagina_que_nao_conhece(hv):
    """Responder `False` calado devolveria a fita esmaecida sem dizer por quê."""
    with pytest.raises(SystemExit, match="ABAS_QUE_ESCOLHEM"):
        _monta().a_fita_escolhe("03-gatihos")
    with pytest.raises(SystemExit, match="ABAS_QUE_ESCOLHEM"):
        _monta().a_fita_escolhe("10-perfil")
    assert _monta().a_fita_escolhe("99-inventada") is False
    assert _monta().a_fita_escolhe("98-prova-da-ressalva.html") is False


def test_a_resposta_nao_e_mais_digitada_nos_geradores(hv):
    """O parâmetro `fita_viva` saiu de `monta()` — dois donos divergem."""
    import inspect

    assinatura = inspect.signature(_monta().monta)
    assert "fita_viva" not in assinatura.parameters, (
        "`monta()` voltou a aceitar `fita_viva`: a pergunta 'esta aba escolhe?' "
        "tem UM dono, `monta.ABAS_QUE_ESCOLHEM`")
