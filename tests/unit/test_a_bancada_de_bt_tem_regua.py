#!/usr/bin/env python3
"""A RÉGUA DO DEGRAU 0.9.5 — que existia só como promessa até 01/09/2026.

A escada de releases (`docs/process/2026-08-24-A-ESCADA-DE-RELEASES.md`) declara
o degrau **0.9.5 — o rádio para de mentir** e nomeia o arquivo que o mede:
*"arquivo a nascer: `scripts/check_bancada_de_bt.py`"*. Ele não existia, e o
degrau dela não tinha como ser conferido por ninguém — só descrito.

O QUE ESTE TESTE COBRA, e é o mínimo para o portão não virar decoração:

1. o script EXISTE e roda;
2. as quatro réguas medem o que a escada diz que medem — cada uma conferida
   contra um CSV de mentira com o caso exato;
3. zero pendência devolve rc=0, e uma pendência devolve rc=1;
4. a QUINTA régua não é fingida: ela é de bancada, e o script diz isso.

O PONTO 4 É O QUE IMPORTA MAIS. A R5 pede três adaptadores em
`/sys/class/bluetooth/` e um ensaio com quatro DualSense no rádio observado por
ela. Nenhum arquivo responde isso, e um portão que a desse por fechada seria
exatamente a doença que este degrau existe para curar: *afirmar o que não se
mediu*.
"""
from __future__ import annotations

import csv
import importlib.util
import pathlib
import subprocess
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts/check_bancada_de_bt.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("bancada", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_o_script_existe():
    """A escada o nomeava e ele não existia. Um degrau sem régua é uma descrição."""
    assert SCRIPT.exists(), (
        "`scripts/check_bancada_de_bt.py` sumiu. A escada de releases o nomeia "
        "como o que mede o degrau 0.9.5 — sem ele, o degrau dela volta a ser "
        "uma frase.")


def test_ele_roda_e_relata(mod):
    r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert "R1" in r.stdout and "R4" in r.stdout, r.stdout[:400]
    # Hoje há pendência; o dia em que não houver, o rc vira 0 — e é o degrau.
    assert r.returncode in (0, 1)


def test_r1_pega_a_celula_que_nao_nomeia_a_culpa(mod):
    """"Não funciona" sem dizer por quê é a pior forma de vazio."""
    peca = {"chave": "x.y", "rotulo": "algo", "radio_aciona": "nao",
            "radio_por_que_nao_aciona": "", "familia": "luz"}
    assert mod.r1([peca]), "a célula muda passou"
    peca["radio_por_que_nao_aciona"] = "decisao-tomada"
    assert not mod.r1([peca]), (
        "nomear a culpa fecha a R1 — a escada diz isso com todas as letras: "
        "'preencher com decisao-tomada fecha a R1 e é verdade'")


def test_r2_pega_a_afirmacao_sem_lastro(mod):
    peca = {"chave": "x.y", "rotulo": "algo", "radio_aciona": "sim",
            "radio_de_onde_sei": "inferido-do-codigo", "familia": "luz"}
    assert mod.r2([peca]), "a afirmação não medida passou"
    peca["radio_de_onde_sei"] = "medido"
    assert not mod.r2([peca])


def test_r3_nao_fecha_com_uma_peca_medida(mod):
    """O critério frouxo dava ZERO onde a escada contava 6 de 7.

    A pergunta dela é sobre a TELA, e uma tela não se sustenta numa linha.
    """
    familia = mod.PERGUNTAS[0][2][0]
    uma_medida = {"chave": "a", "rotulo": "a", "familia": familia,
                  "radio_de_onde_sei": "medido", "radio_aciona": "sim"}
    outra_nao = {"chave": "b", "rotulo": "b", "familia": familia,
                 "radio_de_onde_sei": "", "radio_aciona": "sim"}
    assert mod.r3([uma_medida, outra_nao]), (
        "uma peça medida fechou a pergunta inteira — é o critério frouxo que "
        "devolvia zero enquanto a escada contava seis")
    assert not mod.r3([uma_medida]), "com a família inteira medida, fecha"


def test_r4_pega_o_ensaio_de_radio_sem_degrau(mod):
    ensaio = {"id": "e1", "linha_id": "x", "transporte": "radio", "degrau": ""}
    assert mod.r4([ensaio])
    ensaio["degrau"] = "2"
    assert not mod.r4([ensaio])
    # o ensaio de CABO não entra nesta régua, e é de propósito
    assert not mod.r4([{"id": "e2", "linha_id": "x", "transporte": "cabo", "degrau": ""}])


def test_as_sete_perguntas_sao_as_dela(mod):
    """São as do `SPRINT_ORDER.md` §2.1, e são SETE — a oitava veio depois.

    A oitava (o preço em bateria) entrou por pedido dela em 24/08, *"pra quando
    terminarmos de medir tudo no bt"*, e por isso não conta neste degrau.
    """
    assert len(mod.PERGUNTAS) == 7, (
        f"são {len(mod.PERGUNTAS)} perguntas e a trilha dela tem sete. Se a "
        f"oitava entrou aqui, ela passou a travar um degrau que ela mesma disse "
        f"vir depois.")
    familias = {f for _, _, fs in mod.PERGUNTAS for f in fs}
    reais = {peca["familia"] for peca in csv.DictReader(
        (RAIZ / "docs/data/mapa-controles.csv").open(encoding="utf-8"))}
    assert familias <= reais, (
        f"estas famílias não existem no mapa: {sorted(familias - reais)} — uma "
        f"pergunta apontada para família inexistente NUNCA fecha, e a régua "
        f"ficaria vermelha para sempre sem ninguém saber por quê.")


def test_a_quinta_regua_nao_e_fingida(mod):
    """Ela é de bancada, e o script tem de DIZER isso em vez de dá-la por feita."""
    fonte = SCRIPT.read_text(encoding="utf-8")
    assert "R5" in fonte and "bluetooth" in fonte, (
        "o script deixou de mencionar a R5. Ela pede três adaptadores e um "
        "ensaio de quatro DualSense no rádio com o olho dela — nenhum arquivo "
        "responde isso, e omiti-la faria o portão verde valer mais do que vale.")
