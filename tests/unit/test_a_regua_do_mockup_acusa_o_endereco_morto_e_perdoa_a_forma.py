#!/usr/bin/env python3
"""A RÉGUA DO MOCKUP acusa o endereço morto e perdoa a forma.

Nasceu com a pílula do Check-up (a cor é do achado, não da posição no desenho; 03/09/2026). A
pílula e as linhas do exame saíram em 04/10/2026 (AS-DICAS-SAO-CARTOES-COM-UM-GESTO-01), mas a
régua de campos (`regua_do_mockup`) é de todas as abas: o que ela precisa fazer continua aqui,
sobre campos de mentira.
"""
from __future__ import annotations

import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))


def _regua():  # type: ignore[no-untyped-def]
    from hefesto_dualsense4unix.interface import regua_do_mockup

    return regua_do_mockup


def _pilula(quando: str, classe: str = "on", aceso: bool = False):  # type: ignore[no-untyped-def]
    r = _regua()
    return r._Campo(chave="selo-x", dono="", alvo="classe",
                    valor=(quando if aceso else ""), quando=quando)


def test_o_estado_cru_num_elemento_de_um_estado_so_e_endereco_morto() -> None:
    """O veredito com o token errado, e o veredito com o certo. Lado a lado."""
    r = _regua()
    campo = _pilula("problema")

    cru = r._classificar([campo], [""], {("", "selo-x"): ["certo"]}, [True])
    assert cru[0].classe == r.MOCKUP, (
        "emitir `certo` num elemento que só sabe dizer `problema` TEM de ser "
        "acusado — é a régua fazendo o trabalho dela")
    assert "ENDEREÇO MORTO" in cru[0].nota

    curado = r._classificar([campo], [""], {("", "selo-x"): [""]}, [True])
    assert curado[0].classe == r.PRODUTO, (
        "com o vazio — o `não` desta pergunta — o campo é do produto: o piloto "
        "esteve nele e a tela mostra exatamente o que ele escreveu")


def test_o_interruptor_aceso_e_produto() -> None:
    """E o `sim` também: o elemento do estado que casa acende, e isso é produto."""
    r = _regua()
    campo = _pilula("certo")
    fora = r._classificar([campo], ["certo"], {("", "selo-x"): ["certo"]}, [True])
    assert fora[0].classe == r.PRODUTO


def test_a_regua_le_o_html_declarado_como_a_tela_o_mostra() -> None:
    """Uma declaração com `<b>` chega à comparação SEM as tags, como o DOM."""
    r = _regua()
    campo = r._Campo(chave="teto-explica", dono="p1", alvo="html",
                     valor="hoje segue o global")
    assert r._declarado_neste_elemento(campo, "hoje <b>segue o global</b>") == (
        "hoje segue o global"), (
        "a régua lê o alvo `html` pelo TEXTO (ver `_campo` e o `LER_CAMPOS` do "
        "piloto). Comparar a declaração COM as tags contra a tela SEM elas "
        "acusa endereço morto sobre a pintura que acertou.")


def test_o_teto_da_vibracao_nao_e_endereco_morto_quando_o_produto_o_pinta() -> None:
    """O caso medido em 03/09: o produto pinta o `?` e a régua o acusava."""
    r = _regua()
    texto = ("O teto da vibração deste controle. O global manda e o do controle "
             "sobrepõe: hoje este controle segue o global.")
    marcado = ("O teto da vibração <b>deste controle</b>. O global manda e o do "
               "controle sobrepõe: hoje este controle <b>segue o global</b>.")
    campo = r._Campo(chave="teto-explica", dono="p1", alvo="html", valor=texto)
    fora = r._classificar([campo], [texto], {("p1", "teto-explica"): marcado},
                          [True])
    assert fora[0].classe == r.PRODUTO, (
        f"o `?` do teto voltou a ser acusado: {fora[0].nota}")


def test_o_html_que_o_produto_nao_pintou_continua_acusado() -> None:
    """A cura do `html` NÃO pode cegar a régua: texto diferente segue acusado."""
    r = _regua()
    campo = r._Campo(chave="achado-explica", dono="", alvo="html",
                     valor="o desenho")
    fora = r._classificar([campo], ["o desenho"],
                          {("", "achado-explica"): "<b>o produto</b>"}, [True])
    assert fora[0].classe == r.MOCKUP, (
        "um endereço em que o produto declara UMA coisa e a tela mostra OUTRA "
        "continua sendo endereço morto — tirar as tags é normalizar a forma, "
        "nunca perdoar a diferença")
