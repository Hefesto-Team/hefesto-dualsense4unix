#!/usr/bin/env python3
"""Os restos da 07 e da Navegação saíram do código, e a recusa aponta o botão que existe.

A 07 trocou os cartões velhos pelo desenho publicado em 18/10/2026, mas a recusa do «Adicionar um
lançador» seguia citando o botão do modelo de antes. A frase pergunta à tela que se renderiza.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

PAGINA_PUBLICADA = INTERFACE / "paginas" / "07-lancadores.html"  # (noqa-acento): o nome da pasta
ENTRE_ASPAS = re.compile(r"«([^»]+)»")


@pytest.fixture(scope="module")
def desenho():
    from hefesto_dualsense4unix.interface import desenho_dos_lancadores as dl

    return dl


@pytest.fixture(scope="module")
def a07():
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores

    return a07_lancadores


@pytest.fixture(scope="module")
def exp():
    from hefesto_dualsense4unix.interface import desenho_da_experimental as e

    return e


def _texto_da_pagina() -> str:
    return PAGINA_PUBLICADA.read_text(encoding="utf-8")


def _fileira_acesa(chave: str) -> tuple[str, ...]:
    achou = re.search(rf'data-lancador="{chave}".*?<span class="lf-botoes">(.*?)</span>\s*</div>',
                      _texto_da_pagina(), flags=re.S)
    assert achou, f"o cartão {chave!r} não está na 07 publicada"
    return tuple(re.findall(r'<(?:a|button) class="btn mini"[^>]*>([^<]+)</', achou.group(1)))


def test_a_recusa_para_a_steam_cita_so_o_que_a_pagina_publicada_tem(a07, desenho):
    """Todo «rótulo» da frase existe em `07-lancadores.html`, e o botão citado está ACESO."""
    pagina = _texto_da_pagina()
    fileira = _fileira_acesa(desenho.STEAM)
    frase = a07._recusa_de_quem_ja_tem_cartao(desenho.STEAM, "Steam", fileira)

    citados = ENTRE_ASPAS.findall(frase)
    assert citados, f"a recusa da Steam não nomeia botão nenhum: {frase!r}"
    ausentes = [c for c in citados if f">{c}<" not in pagina and f"<span>{c}</span>" not in pagina]
    assert not ausentes, (
        f"a recusa cita {ausentes} e a 07 publicada não tem esse rótulo: {frase!r}")
    assert desenho.CONFIGURAR_ROTULO in citados and desenho.CONFIGURAR_ROTULO in fileira, (
        f"a recusa deve mandar ao «{desenho.CONFIGURAR_ROTULO}» aceso do cartão: {frase!r} "
        f"(fileira acesa: {fileira})")


def test_a_recusa_do_cartao_que_nao_foi_achado_diz_o_fato_e_para(a07, desenho):
    """O «Configurar» do não achado está apagado: a frase não manda clicar nele."""
    fileira = _fileira_acesa("heroic")
    assert desenho.CONFIGURAR_ROTULO not in fileira, (
        "o cartão do Heroic acendeu o «Configurar»: a régua mediria outro estado")
    frase = a07._recusa_de_quem_ja_tem_cartao("heroic", "Heroic", fileira)
    assert not ENTRE_ASPAS.findall(frase), (
        f"a frase manda clicar onde nada está aceso: {frase!r}")


def test_a_fileira_do_gesto_vem_da_mesma_regra_da_pagina(a07, desenho, exp, monkeypatch):
    """`_botoes_do_cartao_agora` e a página leem `exp.BOTOES` + `exp.botao_ativo`: uma regra só."""
    nomes = {rotulo for _, rotulo, _ in exp.BOTOES}
    assert {desenho.CONFIGURAR_ROTULO, desenho.IDENTIFICAR_ROTULO} <= nomes, (
        "o desenho da página deixou de ler os nomes do desenho: dois nomes para o mesmo botão")

    for presente, esperado in ((True, _fileira_acesa("steam")), (False, _fileira_acesa("heroic"))):
        da_regra = tuple(r for g, r, _ in exp.BOTOES if exp.botao_ativo(g, presente))
        assert da_regra == esperado, (
            f"a regra dá {da_regra} para presente={presente}; a página publicada mostra {esperado}")

    lida = desenho.Leitura(onde_estao=tuple((x.chave, "/bin/sh") for x in desenho.EMBUTIDOS))
    monkeypatch.setattr(a07.VIGIA, "agora", lambda: lida)
    cartao = next(c for c in desenho.cartoes(lida) if c.chave == desenho.STEAM)
    assert a07._botoes_do_cartao_agora(desenho.STEAM) == tuple(
        r for g, r, _ in exp.BOTOES if exp.botao_ativo(g, cartao.presente))


def test_as_pecas_mortas_e_o_orfao_fantasma_nao_existem_mais(a07, desenho):
    for nome in ("tela_da_escolha_html", "CSS_DA_EXCLUSAO"):
        assert not hasattr(desenho, nome), f"{nome} voltou ao desenho sem chamador"
    assert "criar-perfil" not in a07.SEM_DONO, (
        "o órfão `criar-perfil` voltou: nenhuma página tem esse endereço")
    pagina = _texto_da_pagina()
    assert 'data-campo="criar-perfil"' not in pagina


def test_os_dois_comentarios_trazem_a_frase_completa():
    entrada = (RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "actions"
               / "input_actions.py").read_text(encoding="utf-8")
    achou = re.search(r"# O ALTERNADOR é o preset do L3.*?\n(?:\s*#.*\n)*", entrada)
    assert achou, "o comentário do ALTERNADOR sumiu"
    texto = " ".join(linha.strip("# ").strip() for linha in achou.group(0).splitlines())
    assert not texto.rstrip().endswith("Sem esta"), f"o comentário segue truncado: {texto!r}"
    assert "`__TOGGLE_OSK__` cru" in texto, f"a frase do comentário não fecha: {texto!r}"

    aba06 = (INTERFACE / "aba06.py").read_text(encoding="utf-8")
    achou = re.search(r"# A lista é a da LINHA.*?\n(?:\s*#.*\n)*", aba06)
    assert achou, "o comentário da lista por linha sumiu"
    regra = achou.group(0)
    for parte in ("LINHAS_DA_ACAO_DE_EIXO", "Movimento do cursor", "Rolagem",
                  "Teclas WASD", "Setas", "a linha de botão não oferece nenhuma"):
        assert parte in regra, f"o comentário de `por_grupo` não diz {parte!r}: {regra!r}"
