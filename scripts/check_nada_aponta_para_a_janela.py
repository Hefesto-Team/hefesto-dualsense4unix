#!/usr/bin/env python3
"""Portão: NADA NOVO APONTA PARA A JANELA GTK."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CSV_DO_INVENTARIO = RAIZ / "docs/data/o-que-ainda-aponta-para-a-janela.csv"

VEREDITOS = {
    "SAI-COM-A-JANELA",
    "MOTOR-MUDA-DE-CASA",
    "NUNCA-DEVIA-CITAR",
}

COLUNAS = [
    "arquivo",
    "linhas",
    "alvo",
    "natureza",
    "ocorrencias",
    "pergunta_respondida",
    "veredito",
    "razao",
]

PASTAS_VARRIDAS = ("src", "tests", "scripts", "packaging", "flatpak")
ARQUIVOS_SOLTOS = (
    "install.sh",
    "uninstall.sh",
    "run.sh",
    "pyproject.toml",
)
EXTENSOES = {
    ".py",
    ".sh",
    ".toml",
    ".cfg",
    ".ini",
    ".in",
    ".yml",
    ".yaml",
    ".json",
    ".desktop",
    ".service",
    ".spec",
}

_NAO_SE_VARRE = {
    "scripts/check_nada_aponta_para_a_janela.py",
    "tests/unit/test_nada_novo_aponta_para_a_janela.py",
    "docs/data/o-que-ainda-aponta-para-a-janela.csv",
}

_PASTAS_IGNORADAS = {".git", ".code-review-graph", "__pycache__", ".venv", "node_modules"}


_PACOTE = "hefesto_dualsense4unix"

_GUI_FROM_IMPORT = re.compile(
    rf"from\s+{_PACOTE}\.gui\s+import\s+(?P<nomes>[A-Za-z_][\w, ]*(?:as\s+\w+)?[\w, ]*)"
)
_GUI_PONTO = re.compile(rf"{_PACOTE}\.gui(?:\.(?P<sub>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?))?")
_GUI_CAMINHO = re.compile(r"(?<![\w/.])gui/(?P<caminho>(?:widgets/)?[a-z_][\w]*)\.py")

_ALVOS_LITERAIS = (
    ("gui/main.glade", re.compile(r"main\.glade")),
    ("gui/theme.css", re.compile(r"theme\.css")),
    (
        "app/app.py",
        re.compile(
            rf"{_PACOTE}\.app\.app\b|(?<![\w/])app/app\.py|from\s+{_PACOTE}\.app\s+import\s+app\b"
        ),
    ),
    (
        "app/main.py",
        re.compile(
            rf"{_PACOTE}\.app\.main\b|(?<![\w/])app/main\.py|from\s+{_PACOTE}\.app\s+import\s+main\b"
        ),
    ),
)

_O_PROPRIO_ALVO = {
    "gui/main.glade": "src/hefesto_dualsense4unix/gui/main.glade",
    "gui/theme.css": "src/hefesto_dualsense4unix/gui/theme.css",
    "app/app.py": "src/hefesto_dualsense4unix/app/app.py",
    "app/main.py": "src/hefesto_dualsense4unix/app/main.py",
}


def alvos_cumpridos() -> dict[str, str]:
    """Os alvos cujo ARTEFATO já não existe nesta árvore — 06/09/2026."""
    return {
        alvo: caminho
        for alvo, caminho in _O_PROPRIO_ALVO.items()
        if not (RAIZ / caminho).exists()
    }


def _prosa_do_python(texto: str) -> dict[int, list[tuple[int, int]]]:
    """As posições que são COMENTÁRIO ou DOCSTRING — a prosa, e só ela."""
    import io
    import tokenize

    faixas: dict[int, list[tuple[int, int]]] = defaultdict(list)
    try:
        for ficha in tokenize.generate_tokens(io.StringIO(texto).readline):
            if (ficha.type == tokenize.STRING
                    and ficha.string.lstrip("rbfuRBFU")[:3]
                    not in ('"""', "'''")):
                continue
            if ficha.type not in (tokenize.COMMENT, tokenize.STRING):
                continue
            (linha_ini, col_ini), (linha_fim, col_fim) = ficha.start, ficha.end
            for numero in range(linha_ini, linha_fim + 1):
                inicio = col_ini if numero == linha_ini else 0
                fim = col_fim if numero == linha_fim else 1 << 30
                faixas[numero].append((inicio, fim))
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
        return {}
    return dict(faixas)


def _natureza(
    linha: str, coluna: int, numero: int, sufixo: str, prosa: dict
) -> str:
    """Diz o que a citação É, para quem for classificar o veredito."""
    nua = linha.strip()
    if sufixo == ".py":
        if any(ini <= coluna < fim for ini, fim in prosa.get(numero, ())):
            return "prosa"
        if nua.startswith(("from ", "import ")) or " import " in nua:
            return "import"
        return "código"
    if nua.startswith("#"):
        return "prosa"
    return "código"


def _alvo_gui(sub: str | None) -> str:
    """Normaliza para o MÓDULO citado, não para o símbolo dentro dele."""
    if not sub:
        return "gui"
    pedacos = sub.split(".")
    if pedacos[0] == "widgets":
        return "gui." + ".".join(pedacos[:2])
    return f"gui.{pedacos[0]}"


def _alvos_da_linha(linha: str) -> list[tuple[str, int]]:
    """Todos os alvos da janela citados nesta linha: (alvo, coluna)."""
    achados: list[tuple[str, int]] = []

    for nome, agulha in _ALVOS_LITERAIS:
        achados.extend((nome, casado.start()) for casado in agulha.finditer(linha))

    for casado in _GUI_FROM_IMPORT.finditer(linha):
        for pedaco in casado.group("nomes").split(","):
            nome = pedaco.strip().split(" as ")[0].strip()
            if nome and nome.isidentifier():
                achados.append((f"gui.{nome}", casado.start()))

    ja_contados = len(_GUI_FROM_IMPORT.findall(linha))
    pontos = list(_GUI_PONTO.finditer(linha))
    for casado in pontos[ja_contados:]:
        achados.append((_alvo_gui(casado.group("sub")), casado.start()))

    for casado in _GUI_CAMINHO.finditer(linha):
        achados.append(("gui." + casado.group("caminho").replace("/", "."), casado.start()))

    return achados


def _arquivos_a_varrer() -> list[Path]:
    vistos: list[Path] = []
    for pasta in PASTAS_VARRIDAS:
        base = RAIZ / pasta
        if not base.is_dir():
            continue
        for caminho in sorted(base.rglob("*")):
            if not caminho.is_file() or caminho.suffix not in EXTENSOES:
                continue
            if _PASTAS_IGNORADAS & set(caminho.relative_to(RAIZ).parts):
                continue
            vistos.append(caminho)
    for solto in ARQUIVOS_SOLTOS:
        caminho = RAIZ / solto
        if caminho.is_file():
            vistos.append(caminho)
    return vistos


_PENEIRA = re.compile(
    "|".join(
        [agulha.pattern for _, agulha in _ALVOS_LITERAIS]
        + [_GUI_FROM_IMPORT.pattern, _GUI_PONTO.pattern, _GUI_CAMINHO.pattern]
    )
)


def varrer() -> dict[tuple[str, str], dict]:
    """A varredura: (arquivo, alvo) -> {linhas, ocorrencias, natureza}."""
    censo: dict[tuple[str, str], dict] = {}
    for caminho in _arquivos_a_varrer():
        relativo = caminho.relative_to(RAIZ).as_posix()
        if relativo in _NAO_SE_VARRE:
            continue
        try:
            texto = caminho.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if not _PENEIRA.search(texto):
            continue
        prosa = _prosa_do_python(texto) if caminho.suffix == ".py" else {}
        for numero, linha in enumerate(texto.splitlines(), start=1):
            for alvo, coluna in _alvos_da_linha(linha):
                if _O_PROPRIO_ALVO.get(alvo) == relativo:
                    continue
                registro = censo.setdefault(
                    (relativo, alvo),
                    {"linhas": [], "ocorrencias": 0, "natureza": set()},
                )
                if numero not in registro["linhas"]:
                    registro["linhas"].append(numero)
                registro["ocorrencias"] += 1
                registro["natureza"].add(
                    _natureza(linha, coluna, numero, caminho.suffix, prosa)
                )
    return censo


def ler_o_inventario() -> list[dict]:
    if not CSV_DO_INVENTARIO.exists():
        return []
    with CSV_DO_INVENTARIO.open(encoding="utf-8") as fonte:
        linhas = [linha for linha in fonte if not linha.lstrip().startswith("#")]
    return list(csv.DictReader(linhas))


def _gravar(linhas: list[dict]) -> None:
    cabecalho = []
    with CSV_DO_INVENTARIO.open(encoding="utf-8") as fonte:
        for linha in fonte:
            if linha.lstrip().startswith("#"):
                cabecalho.append(linha)
            else:
                break
    with CSV_DO_INVENTARIO.open("w", encoding="utf-8", newline="") as destino:
        destino.writelines(cabecalho)
        escritor = csv.DictWriter(destino, fieldnames=COLUNAS, lineterminator="\n")
        escritor.writeheader()
        for linha in linhas:
            escritor.writerow({coluna: linha.get(coluna, "") for coluna in COLUNAS})


def comando_censo() -> int:
    censo = varrer()
    for (arquivo, alvo), dado in sorted(censo.items()):
        linhas = ";".join(str(numero) for numero in dado["linhas"])
        natureza = "+".join(sorted(dado["natureza"]))
        print(f"{arquivo}\t{linhas}\t{alvo}\t{natureza}\t{dado['ocorrencias']}")
    print(
        f"\n# {len(censo)} pares (arquivo, alvo) · "
        f"{sum(d['ocorrencias'] for d in censo.values())} citações",
        file=sys.stderr,
    )
    return 0


def comando_podar() -> int:
    censo = varrer()
    sobrevivem: list[dict] = []
    podadas = 0
    for linha in ler_o_inventario():
        chave = (linha["arquivo"], linha["alvo"])
        if chave not in censo:
            podadas += 1
            continue
        vivas = censo[chave]["ocorrencias"]
        if int(linha["ocorrencias"]) > vivas:
            linha["ocorrencias"] = str(vivas)
            linha["linhas"] = ";".join(str(n) for n in censo[chave]["linhas"])
            podadas += 1
        sobrevivem.append(linha)
    _gravar(sobrevivem)
    print(f"OK: {podadas} linha(s) podada(s); {len(sobrevivem)} ficam.")
    return 0


def comando_portao() -> int:
    censo = varrer()
    inventario = ler_o_inventario()
    if not inventario:
        print(f"FALHA: o inventário {CSV_DO_INVENTARIO.relative_to(RAIZ)} não existe ou está vazio.")
        return 1

    declarado: dict[tuple[str, str], dict] = {}
    problemas: list[str] = []

    for numero, linha in enumerate(inventario, start=2):
        onde = f"{CSV_DO_INVENTARIO.relative_to(RAIZ)}:{numero}"
        chave = (linha.get("arquivo", ""), linha.get("alvo", ""))
        if chave in declarado:
            problemas.append(f"{onde}: par repetido ({chave[0]} · {chave[1]}).")
        declarado[chave] = linha
        veredito = (linha.get("veredito") or "").strip()
        if veredito not in VEREDITOS:
            problemas.append(
                f"{onde}: veredito {veredito or '(vazio)'!r} não é um dos três "
                f"({', '.join(sorted(VEREDITOS))}) — {chave[0]} · {chave[1]}."
            )
        if not (linha.get("pergunta_respondida") or "").strip():
            problemas.append(f"{onde}: `pergunta_respondida` vazia — {chave[0]} · {chave[1]}.")
        if not (linha.get("razao") or "").strip():
            problemas.append(f"{onde}: `razao` vazia — {chave[0]} · {chave[1]}.")
        try:
            int(linha.get("ocorrencias") or "")
        except ValueError:
            problemas.append(f"{onde}: `ocorrencias` não é número — {chave[0]} · {chave[1]}.")

    cumpridos = alvos_cumpridos()
    citacoes_cumpridas = sum(
        dado["ocorrencias"] for (_arq, alvo), dado in censo.items() if alvo in cumpridos
    )
    for chave in sorted(censo):
        arquivo, alvo = chave
        vivas = censo[chave]
        linhas = ";".join(str(numero) for numero in vivas["linhas"])
        if alvo in cumpridos:
            continue
        if chave not in declarado:
            problemas.append(
                f"{arquivo}:{linhas}: CITAÇÃO NOVA para a janela ({alvo}). "
                "A janela GTK está sendo aposentada (D-0609-GTK-LEVA-INTEIRA): o motor "
                "é que se reusa, não a janela. Se esta citação tem de existir, declare-a "
                f"em {CSV_DO_INVENTARIO.relative_to(RAIZ)} com veredito e razão."
            )
            continue
        try:
            antes = int(declarado[chave].get("ocorrencias") or "0")
        except ValueError:
            continue
        if vivas["ocorrencias"] > antes:
            problemas.append(
                f"{arquivo}:{linhas}: a lista CRESCEU em {alvo} "
                f"({antes} declarada(s), {vivas['ocorrencias']} viva(s)). "
                "Esta lista só diminui."
            )

    encolheu = [chave for chave in declarado if chave not in censo]
    encolheu_contagem = [
        chave
        for chave in declarado
        if chave in censo
        and (declarado[chave].get("ocorrencias") or "0").isdigit()
        and censo[chave]["ocorrencias"] < int(declarado[chave]["ocorrencias"])
    ]

    if problemas:
        print(f"FALHA: {len(problemas)} problema(s) — nada novo aponta para a janela.\n")
        for problema in problemas:
            print(f"  {problema}")
        return 1

    vivas_total = sum(dado["ocorrencias"] for dado in censo.values())
    vigiadas = len([c for c in censo if c[1] not in cumpridos])
    print(
        f"OK: {len(censo)} pares (arquivo, alvo) · {vivas_total} citações à janela, "
        f"todas declaradas com veredito."
    )
    if cumpridos:
        print(
            f"     ({len(cumpridos)} alvo(s) CUMPRIDO(S) — o artefato não existe mais: "
            + ", ".join(sorted(cumpridos))
            + f".\n      As {citacoes_cumpridas} citações a eles são prosa datada e "
            "saem das duas regras;\n      "
            f"{vigiadas} par(es) continuam vigiados. Se um deles voltar ao disco, "
            "volta às regras sozinho.)"
        )
    if encolheu or encolheu_contagem:
        print(
            f"     (a lista encolheu: {len(encolheu)} par(es) sumiram e "
            f"{len(encolheu_contagem)} tiveram menos ocorrências. "
            "Rode `--podar` para o CSV acompanhar.)"
        )
    return 0


def main() -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--censo", action="store_true", help="a varredura crua")
    analisador.add_argument("--podar", action="store_true", help="só encolhe o CSV")
    argumentos = analisador.parse_args()
    if argumentos.censo:
        return comando_censo()
    if argumentos.podar:
        return comando_podar()
    return comando_portao()


if __name__ == "__main__":
    raise SystemExit(main())
