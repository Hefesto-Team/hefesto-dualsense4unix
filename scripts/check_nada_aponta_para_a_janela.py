#!/usr/bin/env python3
"""Portão: NADA NOVO APONTA PARA A JANELA GTK.

Nasceu na sprint `GTK-1` (06/09/2026), da decisão dela
(`D-0609-GTK-LEVA-INTEIRA`): *"a ideia sempre foi reaproveitar o que fiz no gtk
e não apontar nada mais pra lá mas pro html"*. A frase inteira está na sprint
`docs/process/sprints/2026-09-06-GTK-1-*.md`.

**O QUE SAI É A JANELA. O QUE FICA É O MOTOR** (`app/actions/`, `app/widgets/`,
`app/telas/`, `daemon/`) — é o reuso que ela pediu, e é o que a interface nova
chama a cada tique.

Este portão não remove nada. Ele congela o inventário
`docs/data/o-que-ainda-aponta-para-a-janela.csv` e faz a lista **só diminuir**:

  METADE 1 — CITAÇÃO NOVA REPROVA
      Toda citação em CÓDIGO a um artefato da janela é varrida. O que a varredura
      acha e o CSV não declara reprova, **nomeando arquivo e linha**. Idem quando
      o número de ocorrências de um par (arquivo, alvo) já declarado CRESCE.

  METADE 2 — LINHA SEM VEREDITO REPROVA
      Toda linha do CSV precisa de `veredito` entre os três da sprint, e de
      `pergunta_respondida` e `razao` não vazias. Linha nova sem veredito
      reprova.

  O QUE NÃO REPROVA (de propósito): a lista ter ENCOLHIDO. Par declarado que
  sumiu, ou ocorrência a menos, é o resultado desejado — sai um aviso e a
  sugestão de rodar `--podar`. Fazer disso um vermelho obrigaria toda leva que
  apaga uma linha a editar o CSV no mesmo commit, e transformaria o portão em
  pedágio.

O `--podar` **só encolhe**: apaga linha cujo par sumiu e baixa contagem que caiu.
Ele nunca acrescenta — se acrescentasse, bastaria rodá-lo para lavar uma citação
nova, e o portão morreria.

------------------------------------------------------------------------------
A RÉGUA NÃO SE MEDE — e esta casa já achou três que se mediam nesta leva.

Este arquivo cita os nomes que procura (tem de citar: são as agulhas). O CSV
cita todos eles. O teste do portão também. Os três estão em `_NAO_SE_VARRE` e
ficam FORA da varredura; sem isso o portão nasceria acusando a si mesmo.
------------------------------------------------------------------------------

Uso:
    python3 scripts/check_nada_aponta_para_a_janela.py            # o portão
    python3 scripts/check_nada_aponta_para_a_janela.py --censo    # a varredura crua
    python3 scripts/check_nada_aponta_para_a_janela.py --podar    # só encolhe o CSV
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CSV_DO_INVENTARIO = RAIZ / "docs/data/o-que-ainda-aponta-para-a-janela.csv"

#: Os três vereditos da sprint GTK-1 (plano D-19, Passo 4). Não há um quarto:
#: o que fica de pé no fim da leva não aponta mais para a janela, e por isso
#: não tem linha aqui.
VEREDITOS = {
    # mede ou monta a janela — some na GTK-3
    "SAI-COM-A-JANELA",
    # mede o motor, e o CAMINHO é que está errado — a GTK-2/GTK-3 reaponta
    "MOTOR-MUDA-DE-CASA",
    # é da interface nova e cita a janela por hábito — corrige-se onde está
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

#: ONDE SE VARRE. `docs/` fica de fora **por medição**: são 1.115 citações de
#: `main.glade` em prosa histórica, e esta casa não apaga registro datado. O que
#: a remoção da janela faz com o `validar-referencias-docs.py` é problema da
#: GTK-3, e está escrito no cabeçalho do CSV com o número.
PASTAS_VARRIDAS = ("src", "tests", "scripts", "packaging", "flatpak")
ARQUIVOS_SOLTOS = (
    "install.sh",
    "uninstall.sh",
    "run.sh",
    "interface.sh",
    "pyproject.toml",
    "bancada.py",
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

#: A RÉGUA NÃO SE MEDE. Estes três citam os alvos porque SÃO o instrumento.
_NAO_SE_VARRE = {
    "scripts/check_nada_aponta_para_a_janela.py",
    "tests/unit/test_nada_novo_aponta_para_a_janela.py",
    "docs/data/o-que-ainda-aponta-para-a-janela.csv",
}

_PASTAS_IGNORADAS = {".git", ".code-review-graph", "__pycache__", ".venv", "node_modules"}

# --------------------------------------------------------------------------
# OS ALVOS — os artefatos da janela, e como se reconhece uma citação a cada um.
# --------------------------------------------------------------------------

_PACOTE = "hefesto_dualsense4unix"

#: `from …gui import a, b as c` — pega os nomes importados, um alvo por nome.
_GUI_FROM_IMPORT = re.compile(
    rf"from\s+{_PACOTE}\.gui\s+import\s+(?P<nomes>[A-Za-z_][\w, ]*(?:as\s+\w+)?[\w, ]*)"
)
#: `…gui.<sub>` em qualquer forma (import, atributo, ou prosa em comentário).
_GUI_PONTO = re.compile(rf"{_PACOTE}\.gui(?:\.(?P<sub>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?))?")
#: `gui/aba_conexoes.py`, `gui/widgets/button_glyph.py` — citação por CAMINHO.
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

#: O ARQUIVO NÃO CITA A SI MESMO. `app/app.py` falando de `app/app.py` não é
#: alguém apontando para a janela — é a janela. Sem isto o inventário nasceria
#: com dezenas de linhas que a GTK-3 apaga sem ler.
_O_PROPRIO_ALVO = {
    "gui/main.glade": "src/hefesto_dualsense4unix/gui/main.glade",
    "gui/theme.css": "src/hefesto_dualsense4unix/gui/theme.css",
    "app/app.py": "src/hefesto_dualsense4unix/app/app.py",
    "app/main.py": "src/hefesto_dualsense4unix/app/main.py",
}


def alvos_cumpridos() -> dict[str, str]:
    """Os alvos cujo ARTEFATO já não existe nesta árvore — 06/09/2026.

    POR QUE ELES SAEM DAS DUAS REGRAS, e a razão é o propósito do portão. Ele
    nasceu para impedir que a janela CRESÇA enquanto ela sai: *"a lista só
    diminui, senão a GTK-3 persegue um alvo que cresce"*. No dia em que o
    arquivo é apagado, o alvo parou de crescer da única maneira que importa —
    **não há mais o que importar.** `from hefesto_dualsense4unix.app import app`
    passa a ser `ModuleNotFoundError`, e nenhuma régua precisa proibir o que o
    interpretador já recusa.

    O que sobra citando um alvo cumprido é PROSA: a nota datada de quem apagou,
    o comentário que conta o que morreu, a razão no cabeçalho da régua que
    mudou de dono. Cobrar declaração no CSV para cada uma delas pediria o
    oposto do que esta casa manda — *não se apaga decisão medida* —, e o preço
    seria escrever no inventário a lápide de um arquivo que o inventário existe
    para ver morrer.

    **O ALVO CUMPRIDO NÃO PODE RESSUSCITAR CALADO:** se o arquivo voltar, ele
    volta às duas regras sozinho, porque esta função pergunta ao disco a cada
    execução. E o cabeçalho do relatório diz quantos são e quantas citações eles
    ainda carregam, para o número não sumir de vista.
    """
    return {
        alvo: caminho
        for alvo, caminho in _O_PROPRIO_ALVO.items()
        if not (RAIZ / caminho).exists()
    }


def _prosa_do_python(texto: str) -> dict[int, list[tuple[int, int]]]:
    """As posições que são COMENTÁRIO ou DOCSTRING — a prosa, e só ela.

    **É por isto que este portão não é um `grep`.** A sprint avisa: *"um grep
    sozinho confunde prosa com chamada, e boa parte destas citações é
    comentário"*. Medido nesta árvore: das 255 linhas do inventário, 111 são
    prosa pura — e uma docstring não começa com `#`, então a heurística de
    primeira letra as chamaria de código. O `tokenize` responde pela posição.

    **PROSA É COMENTÁRIO E ASPAS TRIPLAS, NÃO TODO LITERAL DE TEXTO** — e esta
    linha é uma cura, não uma escolha de gosto. A primeira versão marcava todo
    token `STRING` como prosa, e com isso

        MAIN_GLADE = GUI_DIR / "main.glade"     (`app/constants.py:12`)
        _CSS_PATH  = GUI_DIR / "theme.css"      (`app/theme.py:37`)

    — as duas dependências MAIS DURAS que existem — saíam do inventário
    carimbadas como `prosa`, e a `GTK-3` leria "é só um comentário" sobre o
    caminho canônico do arquivo. Um instrumento que apontava para outra coisa,
    que é a família de defeito que esta casa persegue acima de todas.

    O limite que fica: um caminho dentro de aspas SIMPLES é `código`, mesmo
    quando o texto ao redor é frase. É o lado seguro — classifica a mais, nunca
    a menos.

    Um arquivo que não tokeniza devolve vazio: tudo vira `código`, pelo mesmo
    motivo.
    """
    import io
    import tokenize

    #: Por LINHA, os intervalos de coluna que são prosa. Guardar coluna a coluna
    #: num conjunto custava minutos na árvore inteira (medido: o censo estourou
    #: 120 s); o intervalo faz o mesmo trabalho em segundos.
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
    """Diz o que a citação É, para quem for classificar o veredito.

    Não é conferido pelo portão: é coluna descritiva, e o olho humano manda.
    """
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
    """Normaliza para o MÓDULO citado, não para o símbolo dentro dele.

    `…gui.ponte_da_tela.PonteDaTela` e `…gui.ponte_da_tela` são a mesma
    dependência: quem some é o módulo. A exceção é `gui.widgets`, que é pacote —
    ali o módulo é o segundo nível.
    """
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

    #: O `from … import` já foi contado acima; o `_GUI_PONTO` casaria de novo o
    #: prefixo `hefesto_dualsense4unix.gui` da mesma linha. Descontamos.
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


#: A PENEIRA BARATA, antes do `tokenize`: um arquivo sem nenhuma agulha não pode
#: citar a janela, e tokenizá-lo seria pagar por nada. Medido em 06/09/2026: com
#: a peneira o portão fecha em ~2 s contra 6,6 s sem ela — a diferença entre
#: caber e não caber na camada rápida do `portoes.sh`.
#:
#: **ELA É DERIVADA DAS MESMAS AGULHAS, e isso não é elegância — é cicatriz.**
#: A primeira versão trazia uma lista de cadeias escrita à mão
#: (`"main.glade"`, `"theme.css"`, `"app/app.py"`, `".gui"`, …) e ela perdeu
#: **20 pares e 35 citações** de uma vez: nenhuma cobria
#: `hefesto_dualsense4unix.app.app` na forma pontuada. Uma peneira que não é a
#: mesma pergunta do filtro é um portão que mede menos do que diz medir, em
#: silêncio. Construída por união das expressões, ela não pode divergir — e
#: `test_a_peneira_nao_muda_a_conta` prova a igualdade.
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
        #: `lineterminator="\n"`: o padrão do módulo é CRLF, e o git avisa a cada
        #: gravação que vai trocar. Um arquivo versionado desta casa é LF.
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

    # --- METADE 2: toda linha do CSV declara veredito, pergunta e razão -------
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

    # --- METADE 1: nada NOVO aponta para a janela ----------------------------
    #
    # OS ALVOS CUMPRIDOS SAEM DAS DUAS REGRAS — ver `alvos_cumpridos()`. O
    # arquivo não existe mais, então não há import a proibir: o que sobra é
    # prosa datada, e esta casa não a apaga.
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

    # --- o que encolheu: aviso, nunca vermelho -------------------------------
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
