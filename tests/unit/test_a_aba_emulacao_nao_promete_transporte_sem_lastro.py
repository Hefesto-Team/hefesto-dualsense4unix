"""EMULACAO-UM-DONO-SO-01/E8 e E9 — a aba para de afirmar o que o mapa não mede.

O DEFEITO, MEDIDO EM 25/08/2026
================================
Quatro frases da aba Emulação afirmavam que a vibração funciona, sem uma
palavra de transporte, e a mais forte prometia que jogos com suporte a
DualSense *"funcionam completos com «DualSense (PS)»: vibração, giroscópio e
lightbar"*. O mapa de canais não sustenta a vibração — e a sprint que mediu o
defeito errou o tamanho dele ao propor a cura *"provada no cabo, não medida no
rádio"*: em `docs/data/mapa-controles.csv`,
`vibracao.rumble.passthrough@dualsense` tem `de_onde_sei = inferido-do-codigo`
nos **DOIS** lados. O do cabo foi rebaixado de `medido` em 15/08/2026 (D-14),
porque a evidência da célula descrevia leitura de fonte e não medição no
aparelho, e a coluna `mordida` diz a mesma coisa por outro caminho: *"não desce
até o envelope do físico, então nem o cabo nem o rádio são provados de ponta a
ponta"*.

As outras duas afirmações da mesma frase SUSTENTAM, e por isso continuam na
tela: `movimento.giroscopio.jogo@dualsense` e `luz.lightbar.cor@dualsense` têm
`de_onde_sei = medido` e `aciona = sim` nos dois lados.

POR QUE UM PORTÃO NOVO, SE A Z6 JÁ ENTREGOU UM
===============================================
`scripts/validar-fala-de-tela.py` (Z6, 24/08) compara `Fala.afirma` com a
coluna `aciona` — e só com ela. Para esta célula `aciona` vale `sim` nos dois
lados: **a régua da Z6 licenciaria a frase forte**, porque a dúvida não está em
`aciona`, está em `de_onde_sei` e em `ate_onde_foi` (vazio no rádio). Régua que
não alcança o defeito não é redundância a remover; é o motivo de haver a
segunda. É regra desta casa, e foi medida duas vezes (o censo do `vdf` em
16/08, os dois portões de MAC em 25/08).

O QUE ESTE PORTÃO EXIGE — TRÊS REGRAS, E AS DUAS PRIMEIRAS SÃO UM PAR
======================================================================
R1 (declarado → com lastro): toda célula declarada em
   `AFIRMACOES_DE_TRANSPORTE_DA_ABA` que **não** tenha `de_onde_sei = medido` e
   `aciona = sim` nos dois lados obriga o texto daquele widget a carregar a
   ressalva de `RESSALVA_DE_TRANSPORTE`, verbatim.
R2 (radical → declarado): todo texto da página Emulação que cite um radical de
   `RADICAIS_DE_TRANSPORTE` tem de estar declarado para aquela célula. Sem R2,
   R1 só cobre o que alguém lembrou de declarar — e lembrança não é portão.
R3 (E9, o ponteiro): quando um texto desta aba cita um controle entre aspas
   **e** nomeia uma aba, o controle tem de existir no `gui/main.glade` e a aba
   nomeada tem de ser a aba onde ele mora. A frase antiga mandava *"use a
   exceção por jogo em «Steam Input» na aba Emulação"* — nesta aba há só
   "Verificar" e "Desligar Steam Input", que LEEM a allowlist; quem a escreve é
   a caixinha `profile_steam_input_check`, da aba **Perfis**. E o rótulo dela
   também mudou: a sprint ainda o chama de "Este jogo não funciona", e desde a
   ESCONDER-EM-VEZ-DE-SAIR-01 (09/08/2026, decisão de produto) ele é "Esconder os
   controles físicos neste jogo". Por isso R3 lê o rótulo do glade em vez de
   comparar com uma constante: a próxima renomeação reprova sozinha.

AS TRÊS FONTES SÃO INDEPENDENTES
=================================
O CSV (o que está medido), o `gui/main.glade` (o que ela lê) e o bloco de
declaração de `app/actions/emulation_actions.py` (a amarra entre os dois). O
bloco é lido por **AST**, nunca importado: `emulation_actions` puxa GTK, e um
runner sem GTK transformaria `ImportError` em "zero declarações encontradas" —
o jeito silencioso de este portão se desligar (mesma razão escrita em
`scripts/validar-fala-de-tela.py`).

A MORDIDA, PROVADA EM 25/08/2026 — ver o relatório da mordida E1.
"""
from __future__ import annotations

import ast
import csv
import re
from pathlib import Path


_RAIZ = Path(__file__).resolve().parents[2]
_PACOTE = _RAIZ / "src" / "hefesto_dualsense4unix"
_ACOES = _PACOTE / "app" / "actions" / "emulation_actions.py"
_MAPA = _RAIZ / "docs" / "data" / "mapa-controles.csv"

_ABA = "Emulação"

_ROTULO_CITADO = re.compile(r'["“]([^"”]{3,60})["”]')
_ABA_CITADA = re.compile(r"aba \*{0,2}([A-ZÁÉÍÓÚÃÕÂÊÔÇ][a-záéíóúãõâêôç]+)")


def _declaracao(nome: str) -> object:
    """Um dicionário de módulo de `emulation_actions.py`, lido por AST."""
    arvore = ast.parse(_ACOES.read_text(encoding="utf-8"), filename=str(_ACOES))
    for no in arvore.body:
        alvos: list[ast.expr] = []
        valor: ast.expr | None = None
        if isinstance(no, ast.Assign):
            alvos, valor = list(no.targets), no.value
        elif isinstance(no, ast.AnnAssign):
            alvos, valor = [no.target], no.value
        for alvo in alvos:
            if isinstance(alvo, ast.Name) and alvo.id == nome and valor is not None:
                return ast.literal_eval(valor)
    raise AssertionError(
        f"{nome} sumiu de {_ACOES.relative_to(_RAIZ)} — a amarra entre a frase "
        "de tela e a célula do mapa tem um dono só, e é esse bloco."
    )


def _fatos_do_mapa() -> dict[str, dict[str, dict[str, str]]]:
    """{id: {lado: {coluna: valor}}} do CSV, só das colunas de veredito."""
    saida: dict[str, dict[str, dict[str, str]]] = {}
    with _MAPA.open(encoding="utf-8") as fh:
        for linha in csv.DictReader(fh):
            ident = (linha.get("id") or "").strip()
            if not ident:
                continue
            saida[ident] = {
                lado: {
                    coluna: (linha.get(f"{lado}_{coluna}") or "").strip()
                    for coluna in ("aciona", "de_onde_sei", "ate_onde_foi")
                }
                for lado in ("cabo", "radio")
            }
    return saida


def tem_lastro_nos_dois(celula: dict[str, dict[str, str]]) -> bool:
    """A afirmação forte é permitida? Só com `medido` + `aciona=sim` nos DOIS."""
    return all(
        celula.get(lado, {}).get("de_onde_sei") == "medido"
        and celula.get(lado, {}).get("aciona") == "sim"
        for lado in ("cabo", "radio")
    )


def test_a_regua_le_o_mapa_e_nao_um_veredito_cravado() -> None:
    """A régua tem de mudar de resposta quando o mapa muda — os quatro casos."""
    medido = {"aciona": "sim", "de_onde_sei": "medido", "ate_onde_foi": "MONTOU"}
    inferido = {"aciona": "sim", "de_onde_sei": "inferido-do-codigo", "ate_onde_foi": ""}
    parcial = {"aciona": "parcial", "de_onde_sei": "medido", "ate_onde_foi": ""}
    assert tem_lastro_nos_dois({"cabo": medido, "radio": medido}) is True
    assert tem_lastro_nos_dois({"cabo": medido, "radio": inferido}) is False
    assert tem_lastro_nos_dois({"cabo": inferido, "radio": medido}) is False
    assert tem_lastro_nos_dois({"cabo": medido, "radio": parcial}) is False


def test_o_giroscopio_e_a_lightbar_seguem_com_lastro_para_serem_afirmados() -> None:
    """O outro lado da mesma régua: o que a tela PODE dizer."""
    fatos = _fatos_do_mapa()
    for chave in (
        "movimento.giroscopio.jogo@dualsense",
        "luz.lightbar.cor@dualsense",
    ):
        assert tem_lastro_nos_dois(fatos[chave]), (
            f"{chave} perdeu lastro nos dois lados; a frase da aba Emulação o "
            f"afirma sem ressalva. Mapa: {fatos[chave]!r}"
        )


_MANDA_MARCAR = re.compile(r"\bmarqu(?:e|em)\b|\bmarcar\b|\bmarcando\b", re.IGNORECASE)
_A_MARCA_POR_JOGO = "Esconder os controles físicos"


_BURACO = "{}"


