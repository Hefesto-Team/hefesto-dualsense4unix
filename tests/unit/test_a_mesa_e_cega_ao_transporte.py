"""A mesa do co-op não pergunta por qual fio o controle chegou — e isso é medido."""

from __future__ import annotations

import ast
import csv
import re
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
COOP = RAIZ / "src" / "hefesto_dualsense4unix" / "daemon" / "subsystems" / "coop.py"
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"

PALAVRAS_DE_TRANSPORTE = frozenset(
    {
        "usb",
        "bt",
        "bluetooth",
        "cabo",
        "radio",
        "rádio",
        "wired",
        "wireless",
        "bus_usb",
        "bus_bluetooth",
    }
)

NOMES_DE_TRANSPORTE = frozenset({"transport", "transporte", "bustype", "bus"})

ENDERECO_DE_COOP = re.compile(
    r"(?<![A-Za-z0-9_./-])`?(?P<arq>[A-Za-z0-9_./-]*coop\.py):(?P<a>\d+)"
    r"(?:-(?P<b>\d+))?`?"
)

NOME_DEPOIS = re.compile(r"\s*\(`(?P<nome>[A-Za-z_][A-Za-z0-9_]{2,})`\)")


def _docstrings(arvore: ast.AST) -> set[int]:
    """`id()` dos nós `Constant` que são docstring — prosa, não decisão."""
    fora: set[int] = set()
    for no in ast.walk(arvore):
        corpo = getattr(no, "body", None)
        if not isinstance(
            no, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        ):
            continue
        if (
            corpo
            and isinstance(corpo[0], ast.Expr)
            and isinstance(corpo[0].value, ast.Constant)
            and isinstance(corpo[0].value.value, str)
        ):
            fora.add(id(corpo[0].value))
    return fora


def gates_de_transporte(fonte: str) -> list[str]:
    """As decisões por FIO que este módulo toma. Vazio é a promessa desta área."""
    arvore = ast.parse(fonte)
    docs = _docstrings(arvore)
    achados: list[str] = []
    for no in ast.walk(arvore):
        if (
            isinstance(no, ast.Constant)
            and isinstance(no.value, str)
            and id(no) not in docs
            and no.value.strip().lower() in PALAVRAS_DE_TRANSPORTE
        ):
            achados.append(f"linha {no.lineno}: o texto {no.value!r}")
        if isinstance(no, ast.Attribute) and no.attr.lower() in NOMES_DE_TRANSPORTE:
            achados.append(f"linha {no.lineno}: o atributo `.{no.attr}`")
        if isinstance(no, ast.Name) and no.id.lower() in NOMES_DE_TRANSPORTE:
            achados.append(f"linha {no.lineno}: o nome `{no.id}`")
    return achados


def test_o_coop_nao_pergunta_o_transporte() -> None:
    """Nenhuma decisão do co-op olha por qual fio o controle chegou."""
    achados = gates_de_transporte(COOP.read_text(encoding="utf-8"))
    assert not achados, (
        "apareceu decisão de TRANSPORTE em daemon/subsystems/coop.py, e a área "
        "da mesa mediu em 03/09/2026 que não havia nenhuma:\n  "
        + "\n  ".join(achados)
        + "\nSe o gate é legítimo, ele precisa da razão escrita no lugar de onde "
        "não saiu — e desta lista, com a medição que o justifica."
    )


def test_a_regua_morde_um_gate_de_transporte() -> None:
    """A MORDIDA: com um gate de fio plantado, a régua tem de acusar."""
    mentira = (
        'def _pode_sentar(self, aparelho):\n'
        '    """Docstring falando de USB e de BT — isto NÃO pode acusar."""\n'
        '    if aparelho.transport == "bt":\n'
        "        return None\n"
        "    return aparelho\n"
    )
    achados = gates_de_transporte(mentira)
    assert achados, "a régua não viu o gate de transporte plantado"
    assert any("'bt'" in a or '"bt"' in a for a in achados), achados
    assert any("`.transport`" in a for a in achados), achados


def test_a_docstring_sozinha_nao_acusa() -> None:
    """E o contrário: falar de USB e de BT em prosa não é decidir por fio."""
    prosa = (
        'def _prazo():\n'
        '    """No caminho quente (USB, ou BT com o report_thread vivo) volta em '
        '~1ms."""\n'
        "    return 2.0\n"
    )
    assert gates_de_transporte(prosa) == []


def _linhas_do_mapa() -> dict[str, dict[str, str]]:
    with MAPA.open(encoding="utf-8", newline="") as arquivo:
        return {linha["id"]: linha for linha in csv.DictReader(arquivo)}


def test_a_linha_do_slot_no_radio_tem_o_caminho_escrito() -> None:
    """O caminho do rádio do número de jogador não pode voltar a ficar mudo."""
    linha = _linhas_do_mapa()["combinacao.slot_jogador.estabilidade@dualsense"]
    for coluna in ("radio_canal", "radio_comando", "radio_codigo_ref"):
        assert linha[coluna].strip(), f"`{coluna}` ficou muda de novo"
    assert linha["radio_de_onde_sei"] == "inferido-do-codigo"
    assert "numeros_de_jogador" in linha["radio_codigo_ref"], (
        "o caminho do rádio tem de citar quem decide o número que a tela mostra"
    )


def test_toda_citacao_de_coop_py_no_mapa_nomeia_o_simbolo() -> None:
    """Endereço para `coop.py` numa coluna de código tem de dizer o que promete.

    O DEFEITO QUE ISTO PEGA, medido em 03/09/2026: o mapa carregava CINCO faixas
    de `coop.py` que não continham mais nada do que a célula prometia —
    `:857-885` para o espelho de giroscópio (que mora em `:1181-1255`),
    `:590-636` para os sinks de réplica (`:909-955`), `:560-588` para o sink de
    rumble (`:879-907`), `:655-690` para a criação do vpad (`:804-854` e
    `:957-1048`) e `:304-380` para o filtro que só admite DualSense
    (`:679-683`, dentro do `sync`).

    **As cinco passavam VERDES** no `scripts/validar-citacoes-de-linha.py`, e não
    por falha dele: aquele portão só confere o CONTEÚDO de uma faixa quando a
    citação NOMEIA um símbolo entre crases, e nenhuma das cinco nomeava. Ele
    conferia que o arquivo tinha ao menos 885 linhas — e tinha, 2.004.

    A regra que fecha o buraco é de FORMA, e vale só para as colunas de
    endereço: prosa de evidência continua livre.
    """
    faltam: list[str] = []
    for ident, linha in _linhas_do_mapa().items():
        for coluna in ("cabo_codigo_ref", "radio_codigo_ref"):
            texto = linha.get(coluna) or ""
            for achado in ENDERECO_DE_COOP.finditer(texto):
                if not NOME_DEPOIS.match(texto[achado.end() : achado.end() + 80]):
                    faltam.append(f"{ident} · {coluna}: {achado.group(0)}")
    assert not faltam, (
        "citação de daemon/subsystems/coop.py sem o símbolo entre crases logo "
        "depois — é a forma que apodrece calada, porque o portão de citações não "
        "tem o que conferir:\n  " + "\n  ".join(faltam)
    )


def _faixas_de_coop_no_mapa() -> list[tuple[str, int, int, str]]:
    """``(id, início, fim, símbolo)`` de toda faixa de ``coop.py`` que nomeia o símbolo."""
    faixas: list[tuple[str, int, int, str]] = []
    for ident, linha in _linhas_do_mapa().items():
        for coluna in ("cabo_codigo_ref", "radio_codigo_ref"):
            texto = linha.get(coluna) or ""
            for achado in ENDERECO_DE_COOP.finditer(texto):
                nome = NOME_DEPOIS.match(texto[achado.end() : achado.end() + 80])
                if nome and achado.group("b"):
                    faixas.append(
                        (ident, int(achado.group("a")), int(achado.group("b")), nome.group("nome"))
                    )
    return faixas


def test_toda_faixa_de_coop_no_mapa_abre_dentro_da_funcao_prometida() -> None:
    """Cada faixa de ``coop.py`` que o mapa cita fica DENTRO da função que ela nomeia."""
    faixas = _faixas_de_coop_no_mapa()
    assert len(faixas) >= 10, (
        f"o mapa tem só {len(faixas)} faixa(s) de coop.py com símbolo — a régua ficaria vazia"
    )
    definicoes: dict[str, list[tuple[int, int]]] = {}
    for no in ast.walk(ast.parse(COOP.read_text(encoding="utf-8"))):
        if isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef):
            definicoes.setdefault(no.name, []).append((no.lineno, no.end_lineno or no.lineno))
    fora = []
    for ident, inicio, fim, simbolo in faixas:
        casas = definicoes.get(simbolo, [])
        if len(casas) != 1:
            continue
        de, ate = casas[0]
        if inicio < de or fim > ate + 1:
            fora.append(f"{ident}: coop.py:{inicio}-{fim} (`{simbolo}`), e ele mora em {de}-{ate}")
    assert not fora, (
        "faixa de coop.py fora da função que ela promete — rode "
        "`python3 scripts/reapontar-citacoes.py --escrever`:\n  " + "\n  ".join(fora)
    )
