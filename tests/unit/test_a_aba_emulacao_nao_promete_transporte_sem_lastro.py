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
   ESCONDER-EM-VEZ-DE-SAIR-01 (09/08/2026, decisão dela) ele é "Esconder os
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

A MORDIDA, PROVADA EM 25/08/2026 — ver o relatório do agente E1.
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

#: Rótulo citado entre aspas retas ou tipográficas dentro de uma frase de tela.
_ROTULO_CITADO = re.compile(r'["“]([^"”]{3,60})["”]')
#: "na aba Perfis" / "aba **Sistema**" — o nome da aba que a frase promete.
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


# ---------------------------------------------------------------------------
# A régua — pura, para poder ser exercida com um mapa sintético
# ---------------------------------------------------------------------------
def tem_lastro_nos_dois(celula: dict[str, dict[str, str]]) -> bool:
    """A afirmação forte é permitida? Só com `medido` + `aciona=sim` nos DOIS.

    Pura de propósito: é o miolo do veredito, e o caso
    `test_a_regua_le_o_mapa_e_nao_um_veredito_cravado` a exerce com um mapa
    sintético. Sem isso o portão poderia estar acertando por ter a resposta
    escrita, e não por ler o CSV.
    """
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


def test_a_celula_da_vibracao_ganhou_lastro_e_a_ressalva_saiu_junto() -> None:
    """INVERTIDO EM 05/09/2026, e a régua velha mandou inverter.

    Ela dizia, com todas as letras: *"Se um dia a medição de rádio chegar, este
    caso reprova, e é para reprovar: a ressalva da tela tem de sair junto com a
    dívida."* A medição chegou, ela reprovou, e este é o outro lado.

    O QUE ACONTECEU, e é a forma de defeito que ELA nomeou: a prova morava no
    repositório desde sempre — `integrations/uinput_gamepad.py:130` registra
    *"a vibração funciona — provado com SDL2 e validado em gameplay"* — e a
    célula do mapa continuava `inferido-do-codigo`. A régua, lendo o mapa,
    OBRIGAVA a tela a dizer que a vibração não fora conferida. A tela estava
    honesta perante o mapa; **o mapa é que estava atrás do código**.

    Palavra dela: *"isso já tá medido no projeto e implementado. talvez versão
    errada ou não documentada"*.

    A MORDIDA: devolva `inferido-do-codigo` a um dos lados da célula e este
    caso reprova, cobrando a ressalva de volta.
    """
    celula = _fatos_do_mapa()["vibracao.rumble.passthrough@dualsense"]
    assert tem_lastro_nos_dois(celula), (
        "a vibração perdeu o lastro no mapa — se isso for verdade, a ressalva "
        "tem de VOLTAR a `RESSALVA_DE_TRANSPORTE` e às frases da aba, senão a "
        "tela afirma o que o mapa não sustenta. O mapa hoje diz: " + repr(celula)
    )
    assert not _declaracao("RESSALVA_DE_TRANSPORTE"), (
        "a vibração tem lastro nos dois transportes e ainda há ressalva "
        "declarada — ressalva que sobrevive à dívida é fato errado na tela"
    )


def test_o_giroscopio_e_a_lightbar_seguem_com_lastro_para_serem_afirmados() -> None:
    """O outro lado da mesma régua: o que a tela PODE dizer.

    Sem este caso, apagar as duas afirmações da tela por excesso de zelo
    passaria calado — e tirar da tela uma medição que existe é a mesma família
    de defeito, na direção contrária.
    """
    fatos = _fatos_do_mapa()
    for chave in (
        "movimento.giroscopio.jogo@dualsense",
        "luz.lightbar.cor@dualsense",
    ):
        assert tem_lastro_nos_dois(fatos[chave]), (
            f"{chave} perdeu lastro nos dois lados; a frase da aba Emulação o "
            f"afirma sem ressalva. Mapa: {fatos[chave]!r}"
        )


#: A instrução que a tela dava até 28/08/2026 e que o produto tinha curado em
#: 09/08: mandar marcar a exceção por jogo para acabar com o controle dobrado.
#: São as formas de ORDEM ("marque", "marcar", "marcando"), não o substantivo
#: "a marca" — trocar o verbo não pode desligar a régua, e falar da caixinha
#: sem mandar usá-la continua permitido (a aba Perfis precisa disso).
_MANDA_MARCAR = re.compile(r"\bmarqu(?:e|em)\b|\bmarcar\b|\bmarcando\b", re.IGNORECASE)
_A_MARCA_POR_JOGO = "Esconder os controles físicos"


# ---------------------------------------------------------------------------
# BG-TOAST-01 — o recibo carrega a mesma ressalva do rótulo
# ---------------------------------------------------------------------------
# 26/08/2026. O tooltip de "Xbox 360" foi corrigido ONTEM pela E8 e passou a
# dizer *"A vibração ainda não foi conferida no aparelho — nem no cabo, nem no
# rádio"*. O recibo do MESMO botão continuou dizendo *"Gamepad Xbox 360 ligado
# (vibra no jogo)"* — e quem clica lê o toast, não o tooltip que precisa de
# meio segundo parado em cima do botão para aparecer.
#
# R1 (acima) não alcançava isso: ela lê o `gui/main.glade`, e o toast é montado
# em Python. Régua que não alcança o defeito não é redundância a remover; é o
# motivo de haver a segunda — a mesma razão escrita no topo deste arquivo sobre
# a `validar-fala-de-tela.py`.
#
# Como acima, `emulation_actions.py` é lido por AST e nunca importado: ele puxa
# GTK, e um runner sem GTK transformaria `ImportError` em "zero toasts
# encontrados" — o jeito silencioso de este portão se desligar.

#: Os escoadouros de RECIBO desta aba, e quais posições carregam o texto.
#: `_apply_mode(mode_id, flavor, msg)` tem a frase na posição 2;
#: `_toast_emulation(msg)`, na 0.
_ESCOADOUROS_DE_RECIBO: dict[str, tuple[int, ...]] = {
    "_toast_emulation": (0,),
    "_apply_mode": (2,),
}

_BURACO = "{}"


def _texto_do_no(no: ast.expr, ressalvas: dict[str, str]) -> str | None:
    """A expressão remontada como a pessoa a LÊ, ou None se não for texto.

    `RESSALVA_DE_TRANSPORTE["…"]` é resolvido para o valor real, de propósito:
    o produto deve citar a constante em vez de duplicar a frase (uma cópia só,
    que é a regra desta casa sobre fato errado), e a régua tem de enxergar o
    texto FINAL mesmo assim. Um pedaço calculado em tempo de execução vira
    `{}` — visível, para não inventar uma frase que ninguém escreveu.
    """
    if isinstance(no, ast.Constant):
        return no.value if isinstance(no.value, str) else None
    if isinstance(no, ast.Subscript):
        alvo, chave = no.value, no.slice
        if (
            isinstance(alvo, ast.Name)
            and alvo.id == "RESSALVA_DE_TRANSPORTE"
            and isinstance(chave, ast.Constant)
            and isinstance(chave.value, str)
        ):
            return ressalvas.get(chave.value, _BURACO)
        return None
    if isinstance(no, ast.JoinedStr):
        pedacos: list[str] = []
        for pedaco in no.values:
            texto = _texto_do_no(pedaco, ressalvas) if not isinstance(
                pedaco, ast.FormattedValue
            ) else None
            pedacos.append(texto if texto is not None else _BURACO)
        return "".join(pedacos)
    if isinstance(no, ast.BinOp) and isinstance(no.op, ast.Add):
        esquerda = _texto_do_no(no.left, ressalvas)
        direita = _texto_do_no(no.right, ressalvas)
        if esquerda is None and direita is None:
            return None
        return (esquerda or _BURACO) + (direita or _BURACO)
    return None


def _recibos_do_handler(handler: str, ressalvas: dict[str, str]) -> list[str]:
    """Os textos de recibo que o handler manda para a barra de estado."""
    arvore = ast.parse(_ACOES.read_text(encoding="utf-8"), filename=str(_ACOES))
    corpo: ast.FunctionDef | None = None
    for no in ast.walk(arvore):
        if isinstance(no, ast.FunctionDef) and no.name == handler:
            corpo = no
            break
    assert corpo is not None, (
        f"o glade liga o botão ao handler {handler!r}, que não existe em "
        f"{_ACOES.relative_to(_RAIZ)}"
    )
    saida: list[str] = []
    for no in ast.walk(corpo):
        if not isinstance(no, ast.Call) or not isinstance(no.func, ast.Attribute):
            continue
        posicoes = _ESCOADOUROS_DE_RECIBO.get(no.func.attr)
        if posicoes is None:
            continue
        for indice in posicoes:
            if indice < len(no.args):
                texto = _texto_do_no(no.args[indice], ressalvas)
                if texto and texto.replace(_BURACO, "").strip():
                    saida.append(texto)
        for nomeado in no.keywords:
            if nomeado.arg in ("msg", "texto"):
                texto = _texto_do_no(nomeado.value, ressalvas)
                if texto and texto.replace(_BURACO, "").strip():
                    saida.append(texto)
    return saida
