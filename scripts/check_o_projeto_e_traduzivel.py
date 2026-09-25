#!/usr/bin/env python3
"""check_o_projeto_e_traduzivel.py — as três medidas da catraca da tradução.

A ORDEM DELA, e é o desenho inteiro (TRADUZIR-O-PROJETO-01)::

    "minha ideia é depois que arrumarmos e validarmos todas as features isso   (noqa-acento: citação literal dela)
     precisa ser feito em larga escala pros demais. Tanto pra traduzirmos
     documentação quanto traduzirmos o projeto pra outras linguagens e afins.
     Um Hook que vá facilitando isso seria maravilhoso. Pois organicamente
     deixaríamos fácil pra gente e pro outro e deixaríamos o projeto menos
     verboso e bonito e agradável de ler"

Este portão **não traduz uma linha** e não pede mutirão. Ele impede três
números de SUBIREM, e cobra só de quem está escrevendo a linha nova. O motor é
`scripts/catraca.py`, um só; aqui moram as medidas.

AS TRÊS MEDIDAS
---------------
1. ``fronteira-de-lingua`` — arquivos que nenhuma regra de
   `docs/data/zonas-de-lingua.toml` alcança. Piso: ZERO. Arquivo novo fora de
   zona reprova pedindo uma REGRA, nunca uma exceção por nome: lista de arquivo
   envelhece a cada arquivo novo, e esta casa já tem uma congelada num mundo
   que acabou.

2. ``tela-sem-endereco`` — unidades de texto de tela sem endereço de tradução.
   **Hoje ela está PENDENTE, e é o estado honesto.** Não existe forma de
   endereço neste projeto (medido: zero `gettext` em oito dos dez geradores),
   e um contador de "frases sem endereço" sem saber o que é TER endereço
   devolveria zero — e zero se lê como verde. A forma do endereço é decisão da
   I18N-DA-TELA-NOVA-01; a medida a LÊ de um lugar só, e acorda sozinha no dia
   em que ela for escrita.

3. ``prosa-publicada`` — bytes de comentário dentro das dez páginas que o
   WebKit baixa. É a medida que responde ao *"menos verboso e bonito e
   agradável de ler"*: a razão de um CSS pertence ao GERADOR, que é onde a
   próxima pessoa procura, e não ao byte que o navegador consome e descarta.

E UMA CONFERÊNCIA QUE NÃO É CATRACA
------------------------------------
``--contagem`` refaz, do AST, a contagem que o `.github/CONTRIBUTING.md`
publica na seção *"A língua do produto"*, e reprova se o documento divergir.
Aquele número foi recontado à mão seis vezes conforme a pasta crescia
(18 -> 19 -> 20 -> 29 -> 31 -> 34). **Um número que já saiu de seis jeitos não
é fato, é opinião com cara de dado** — a frase é desta casa, e está no
cabeçalho de `scripts/gerar-contrato-ipc.py`. A partir daqui ele é GERADO.

O QUE ESTE PORTÃO NÃO FAZ
--------------------------
Não traduz, não cria idioma, não toca `po/`, `locale/` nem os `.mo`, não
escolhe a forma do endereço, não decide a fronteira entre "só a tela" e "a tela
mais o que ensina" — essa é dela —, não abre janela e não fala com o daemon.

OS FUROS, DECLARADOS
---------------------
* A zona responde sobre ONDE O ARQUIVO MORA, não sobre com quem ele fala. O
  `install.sh` fala português com quem instala e cai em CODIGO.
* O censo de frases de tela lê o HTML publicado com um parser que **não executa
  JavaScript**. Os pacotes escrevem texto em tempo de execução: o número é
  PISO, não total. O número honesto sai do piloto montado, com `--oculta`.
* A medida 3 conta comentário de HTML e de CSS com parser (não com regex, que
  casaria `/* */` dentro de string). **Comentário dentro de `<script>` NÃO é
  contado**: separar comentário de literal de expressão regular em JavaScript
  pede um analisador que eu escreveria no escuro, e contar errado aqui seria
  repetir o defeito que a medida existe para curar.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

try:
    import tomllib  # stdlib do Python 3.11+
except ImportError:  # pragma: no cover — 3.10, que o pyproject ainda declara
    # `requires-python = ">=3.10"`, e o `lint-test` do CI roda `pytest
    # tests/unit` nas TRÊS versões. Um `import tomllib` pelado morre na
    # COLETA do arquivo de mordidas na perna 3.10 — não como teste vermelho,
    # como módulo que some. O irmão `check_version_consistency.py:58-61` já
    # tinha esta cura, e cobrir um chamador deixa o próximo remedindo.
    import tomli as tomllib  # type: ignore[no-redef]

sys.path.insert(0, str(Path(__file__).resolve().parent))

from catraca import (
    Catraca,
    Censo,
    Medida,
    executar,
    montar_argumentos,
)

RAIZ = Path(__file__).resolve().parents[1]
ZONAS = Path("docs/data/zonas-de-lingua.toml")
CADERNO = Path("docs/data/traduzivel.json")
PAGINAS = Path("src/hefesto_dualsense4unix/interface/paginas")
GERADORES = Path("src/hefesto_dualsense4unix/interface")
ACOES = Path("src/hefesto_dualsense4unix/app/actions")
CONTRIBUINDO = Path(".github/CONTRIBUTING.md")

ZONAS_VALIDAS = ("TELA", "ENSINA", "REGISTRA", "CODIGO")

MARCA_ABRE = "<!-- CONTAGEM-GERADA — não edite à mão:"
MARCA_FECHA = "<!-- /CONTAGEM-GERADA -->"

_ACENTO = re.compile(r"[áàâãäéèêëíìîïóòôõöúùûüçñÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ]")
_LETRA = re.compile(r"[A-Za-zÀ-ÿ]")


# ---------------------------------------------------------------------------
# As zonas, lidas por REGRA
# ---------------------------------------------------------------------------
def _glob_para_regex(caminho: str) -> re.Pattern[str]:
    """Traduz o glob de caminho da tabela para expressão regular.

    `*` não atravessa `/`; `**` atravessa. Escrito à mão porque
    `fnmatch` não distingue os dois, e a distinção é o que separa
    "um arquivo na raiz de docs/" de "qualquer arquivo sob docs/".
    """
    saida = ["^"]
    i = 0
    while i < len(caminho):
        c = caminho[i]
        if c == "*":
            if caminho[i : i + 3] == "**/":
                saida.append("(?:.*/)?")
                i += 3
                continue
            if caminho[i : i + 2] == "**":
                saida.append(".*")
                i += 2
                continue
            saida.append("[^/]*")
        elif c == "?":
            saida.append("[^/]")
        else:
            saida.append(re.escape(c))
        i += 1
    saida.append("$")
    return re.compile("".join(saida))


class Regra:
    __slots__ = ("_re", "caminho", "razao", "zona")

    def __init__(self, caminho: str, zona: str, razao: str) -> None:
        self.caminho = caminho
        self.zona = zona
        self.razao = razao
        self._re = _glob_para_regex(caminho)

    def alcanca(self, caminho: str) -> bool:
        return self._re.match(caminho) is not None


def carregar_zonas(raiz: Path) -> tuple[list[Regra], dict]:
    """A tabela de regras e a seção do endereço de tradução (ou {})."""
    arquivo = raiz / ZONAS
    if not arquivo.exists():
        return [], {}
    dado = tomllib.loads(arquivo.read_text(encoding="utf-8"))
    regras: list[Regra] = []
    for bruta in dado.get("regra", []):
        zona = bruta.get("zona", "")
        if zona not in ZONAS_VALIDAS:
            raise SystemExit(
                f"zonas-de-lingua.toml: zona desconhecida {zona!r} em "
                f"{bruta.get('caminho')!r}. As quatro são: "
                + ", ".join(ZONAS_VALIDAS)
            )
        if not str(bruta.get("razao", "")).strip():
            raise SystemExit(
                f"zonas-de-lingua.toml: a regra {bruta.get('caminho')!r} não diz "
                "a razão. Regra sem razão é lista de arquivo com outro nome."
            )
        regras.append(Regra(bruta["caminho"], zona, bruta["razao"]))
    return regras, dado.get("endereco_de_traducao", {})


def zona_de(caminho: str, regras: list[Regra]) -> Regra | None:
    for regra in regras:
        if regra.alcanca(caminho):
            return regra
    return None


# ---------------------------------------------------------------------------
# O universo de arquivos
# ---------------------------------------------------------------------------
_BINARIO = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".mo", ".bin", ".gz", ".zip",
    ".woff", ".woff2", ".ttf", ".otf", ".pdf", ".webp", ".so", ".pyc",
}


def arquivos_da_arvore(raiz: Path) -> list[str]:
    """Os caminhos que o git rastreia MAIS os novos que ele ainda não viu.

    `--others --exclude-standard` é de propósito: esta casa tem a regra "os
    portões são cegos a arquivo novo, rode-os depois do `git add`", e uma
    catraca que só visse o índice deixaria o arquivo novo fora de zona passar
    até alguém lembrar de adicioná-lo. Aqui ele reprova na hora.

    Fora de uma árvore de git — que é como a mordida do vazio aponta o script
    para uma pasta vazia — cai para a varredura do disco.
    """
    try:
        saida = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=raiz,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return sorted({linha for linha in saida.splitlines() if linha.strip()})
    except (subprocess.CalledProcessError, FileNotFoundError):
        achados = []
        for p in raiz.rglob("*"):
            if p.is_file() and ".git" not in p.parts:
                achados.append(p.relative_to(raiz).as_posix())
        return sorted(achados)


# ---------------------------------------------------------------------------
# MEDIDA 1 — a fronteira
# ---------------------------------------------------------------------------
def censo_da_fronteira(raiz: Path) -> Censo:
    regras, _ = carregar_zonas(raiz)
    arquivos = arquivos_da_arvore(raiz)
    if not regras:
        return Censo(
            numero=None,
            universo=len(arquivos),
            indisponivel=(
                f"{ZONAS} não existe nesta árvore, ou não declara regra "
                "nenhuma. Sem a tabela não há fronteira a medir — e responder "
                "«zero arquivos fora de zona» seria verde sobre o vazio."
            ),
        )
    fora: list[str] = []
    por_zona: dict[str, int] = {z: 0 for z in ZONAS_VALIDAS}
    for caminho in arquivos:
        regra = zona_de(caminho, regras)
        if regra is None:
            fora.append(caminho)
        else:
            por_zona[regra.zona] += 1
    return Censo(
        numero=len(fora),
        universo=len(arquivos),
        por_item={c: 1 for c in fora},
        nomes=tuple(fora),
        nota="por zona: " + ", ".join(f"{z}={n}" for z, n in por_zona.items()),
    )


# ---------------------------------------------------------------------------
# MEDIDA 2 — a tela sem endereço
# ---------------------------------------------------------------------------
_ATRIBUTOS_DE_TELA = ("title", "placeholder", "alt", "aria-label", "aria-description")
_MUDOS = {"script", "style", "template"}


class _LeitorDeTela(HTMLParser):
    """Colhe frase e atributo de tela, sabendo quem é o ancestral de cada nó."""

    def __init__(self, atributo_de_endereco: str | None) -> None:
        super().__init__(convert_charrefs=True)
        self.atributo = atributo_de_endereco
        self.pilha: list[tuple[str, bool]] = []
        self.frases_sem: set[str] = set()
        self.frases_com: set[str] = set()
        self.atributos_sem: set[str] = set()
        self.atributos_com: set[str] = set()

    # -- a pilha -----------------------------------------------------------
    def _tem_endereco(self, attrs: list[tuple[str, str | None]]) -> bool:
        if not self.atributo:
            return False
        return any(nome == self.atributo for nome, _ in attrs)

    def _herda_endereco(self) -> bool:
        return any(marcado for _, marcado in self.pilha)

    def handle_starttag(self, tag, attrs):  # type: ignore[no-untyped-def]
        marcado = self._tem_endereco(attrs) or self._herda_endereco()
        self.pilha.append((tag, marcado))
        self._colher_atributos(tag, attrs, marcado)
        if tag in ("br", "hr", "img", "input", "meta", "link", "source"):
            self.pilha.pop()

    def handle_startendtag(self, tag, attrs):  # type: ignore[no-untyped-def]
        marcado = self._tem_endereco(attrs) or self._herda_endereco()
        self._colher_atributos(tag, attrs, marcado)

    def handle_endtag(self, tag):  # type: ignore[no-untyped-def]
        for i in range(len(self.pilha) - 1, -1, -1):
            if self.pilha[i][0] == tag:
                del self.pilha[i:]
                return

    # -- o que se colhe ----------------------------------------------------
    def _colher_atributos(self, tag, attrs, marcado):  # type: ignore[no-untyped-def]
        for nome, valor in attrs:
            if valor is None or not _LETRA.search(valor):
                continue
            if nome in _ATRIBUTOS_DE_TELA or (
                nome == "value" and tag in ("button", "input")
            ):
                alvo = self.atributos_com if marcado else self.atributos_sem
                alvo.add(f"{nome}={valor.strip()}")

    def handle_data(self, data):  # type: ignore[no-untyped-def]
        if any(tag in _MUDOS for tag, _ in self.pilha):
            return
        texto = " ".join(data.split())
        if not texto or not _LETRA.search(texto):
            return
        alvo = self.frases_com if self._herda_endereco() else self.frases_sem
        alvo.add(texto)


def _paginas_publicadas(raiz: Path) -> list[Path]:
    pasta = raiz / PAGINAS
    if not pasta.is_dir():
        return []
    return sorted(p for p in pasta.glob("[0-9][0-9]-*.html"))


def _geradores(raiz: Path) -> list[Path]:
    pasta = raiz / GERADORES
    if not pasta.is_dir():
        return []
    return sorted(pasta.glob("aba[0-9][0-9].py"))


def conferir_as_dez_abas(raiz: Path, censo: Censo) -> str:
    """A segunda peneira do vazio: PERGUNTA AO DONO quantas páginas há.

    O dono de "quantas abas existem" é a pasta dos geradores, não um número
    digitado aqui. Uma página que sumir — ou a pasta inteira renomeada — faz o
    censo achar menos do que há gerador, e isso é VERMELHO, não um total menor.
    """
    geradores = len(_geradores(raiz))
    if geradores == 0:
        return (
            "não encontrei gerador de aba nenhum em "
            f"{GERADORES}: sem o dono, não há com o que conferir o censo."
        )
    if censo.universo < geradores:
        return (
            f"o censo achou {censo.universo} página(s) publicada(s) e existem "
            f"{geradores} gerador(es) de aba. Página que some não faz o número "
            "cair: faz a régua parar de olhar."
        )
    return ""


def censo_da_tela(raiz: Path) -> Censo:
    _, endereco = carregar_zonas(raiz)
    paginas = _paginas_publicadas(raiz)

    atributo = str(endereco.get("atributo", "")).strip() or None
    if not endereco:
        return Censo(
            numero=None,
            universo=len(paginas),
            indisponivel=(
                "não há FORMA DE ENDEREÇO de tradução definida neste projeto. "
                f"A seção [endereco_de_traducao] de {ZONAS} está ausente, e "
                "quem a define é a I18N-DA-TELA-NOVA-01. Sem saber o que é TER "
                "endereço, «frases sem endereço» daria o total — ou zero, se "
                "alguém invertesse o sinal — e nenhum dos dois mede coisa "
                "alguma. A medida acorda sozinha no dia em que a seção "
                "existir."
            ),
            bruto=_bruto_da_tela(paginas),
        )
    if not atributo:
        return Censo(
            numero=None,
            universo=len(paginas),
            indisponivel=(
                "a seção [endereco_de_traducao] existe mas não declara "
                "`atributo`. Este censo lê o HTML PUBLICADO: se a forma "
                "escolhida for uma função dentro do gerador, quem a escolheu "
                "estende este censo para lê-la do fonte. Medir o HTML atrás de "
                "uma marca que não mora nele devolveria o total inteiro todo "
                "dia."
            ),
            bruto=_bruto_da_tela(paginas),
        )

    sem_frases: set[str] = set()
    sem_atributos: set[str] = set()
    por_item: dict[str, int] = {}
    for pagina in paginas:
        leitor = _LeitorDeTela(atributo)
        leitor.feed(pagina.read_text(encoding="utf-8", errors="replace"))
        sem_frases |= leitor.frases_sem
        sem_atributos |= leitor.atributos_sem
        por_item[pagina.name] = len(leitor.frases_sem) + len(leitor.atributos_sem)
    return Censo(
        numero=len(sem_frases) + len(sem_atributos),
        universo=len(paginas),
        por_item=por_item,
        nota=(
            f"{len(sem_frases)} frases distintas + {len(sem_atributos)} "
            "atributos. O TOTAL é de unidades DISTINTAS entre as páginas; a "
            "soma do `por_item` é maior, porque a tira, o rodapé e os botões "
            "de sempre aparecem em mais de uma aba — e a conta de quem "
            "traduzir é a dos distintos, não a da soma."
        ),
    )


def _bruto_da_tela(paginas: list[Path]) -> dict[str, int]:
    """O censo cru — quantas unidades existem —, para ficar ao lado do PENDENTE.

    Ele NÃO é o número da medida: enquanto não houver forma de endereço, todas
    as unidades estão sem endereço, e esse total é o retrato do custo, não uma
    catraca. Gravá-lo como piso faria a régua dar verde sobre uma medida que
    não mede.
    """
    frases: set[str] = set()
    atributos: set[str] = set()
    for pagina in paginas:
        leitor = _LeitorDeTela(None)
        leitor.feed(pagina.read_text(encoding="utf-8", errors="replace"))
        frases |= leitor.frases_sem
        atributos |= leitor.atributos_sem
    return {
        "frases_distintas": len(frases),
        "atributos_distintos": len(atributos),
        "unidades": len(frases) + len(atributos),
    }


# ---------------------------------------------------------------------------
# MEDIDA 3 — a prosa publicada
# ---------------------------------------------------------------------------
def comentarios_css(css: str) -> list[str]:
    """Os comentários de uma folha de estilo, com as aspas respeitadas.

    Um `re.findall(r"/\\*.*?\\*/")` casa `/*` dentro de `"url(/*)"` e dentro de
    qualquer literal que contenha a sequência. É por isto que os 33,1% da
    sprint eram ordem de grandeza, e por isto que aqui se varre caractere a
    caractere.
    """
    achados: list[str] = []
    i = 0
    n = len(css)
    while i < n:
        c = css[i]
        if c in ("'", '"'):
            aspas = c
            i += 1
            while i < n:
                if css[i] == "\\":
                    i += 2
                    continue
                if css[i] == aspas:
                    i += 1
                    break
                i += 1
            continue
        if c == "/" and i + 1 < n and css[i + 1] == "*":
            fim = css.find("*/", i + 2)
            if fim == -1:
                achados.append(css[i:])
                break
            achados.append(css[i : fim + 2])
            i = fim + 2
            continue
        i += 1
    return achados


class _LeitorDeProsa(HTMLParser):
    """Comentário de HTML e comentário de CSS, em bytes."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.bytes_html = 0
        self.bytes_css = 0
        self.blocos: list[str] = []
        self._dentro_de_style = False

    def handle_comment(self, data):  # type: ignore[no-untyped-def]
        bruto = f"<!--{data}-->"
        self.bytes_html += len(bruto.encode("utf-8"))
        self.blocos.append(bruto)

    def handle_starttag(self, tag, attrs):  # type: ignore[no-untyped-def]
        if tag == "style":
            self._dentro_de_style = True

    def handle_endtag(self, tag):  # type: ignore[no-untyped-def]
        if tag == "style":
            self._dentro_de_style = False

    def handle_data(self, data):  # type: ignore[no-untyped-def]
        if not self._dentro_de_style:
            return
        for bloco in comentarios_css(data):
            self.bytes_css += len(bloco.encode("utf-8"))
            self.blocos.append(bloco)


def censo_da_prosa(raiz: Path) -> Censo:
    paginas = _paginas_publicadas(raiz)
    por_item: dict[str, int] = {}
    total_bytes = 0
    blocos_por_pagina: list[set[str]] = []
    for pagina in paginas:
        leitor = _LeitorDeProsa()
        leitor.feed(pagina.read_text(encoding="utf-8", errors="replace"))
        bytes_da_pagina = leitor.bytes_html + leitor.bytes_css
        por_item[pagina.name] = bytes_da_pagina
        total_bytes += bytes_da_pagina
        blocos_por_pagina.append(set(leitor.blocos))
    repetidos = 0
    if blocos_por_pagina:
        em_todas = set.intersection(*blocos_por_pagina)
        repetidos = sum(
            len(b.encode("utf-8")) * (len(blocos_por_pagina) - 1) for b in em_todas
        )
    return Censo(
        numero=total_bytes,
        universo=len(paginas),
        por_item=por_item,
        nota=(
            f"{repetidos} bytes são cópia do mesmo bloco presente nas "
            f"{len(paginas)} páginas — o WebKit os baixa {len(paginas)} vezes "
            "e os descarta outras tantas. A razão de um CSS pertence ao "
            "gerador. CONTA comentário de HTML e de CSS, com parser; NÃO conta "
            "comentário dentro de <script>, porque separar comentário de "
            "literal de expressão regular em JavaScript pede um analisador "
            "escrito no escuro."
        ),
    )


# ---------------------------------------------------------------------------
# A CONFERÊNCIA — a contagem do CONTRIBUTING, gerada em vez de digitada
# ---------------------------------------------------------------------------
def censo_das_acoes(raiz: Path) -> dict[str, int]:
    """Quem de `app/actions/` escreve prosa fora da função de tradução.

    Por AST, e não por grep: `_("texto")` dentro de um comentário não importa,
    e um literal acentuado dentro de uma docstring não é prosa de tela.
    """
    pasta = raiz / ACOES
    if not pasta.is_dir():
        return {"arquivos": 0, "com_traducao": 0, "escrevem_prosa": 0}
    # Os `__init__.py` CONTAM: os três desta pasta têm código, e o denominador
    # publicado no CONTRIBUTING sempre os contou. Mudar o critério junto com a
    # automação faria o número novo parecer a sétima recontagem à mão.
    modulos = sorted(pasta.rglob("*.py"))
    com_traducao = 0
    escrevem_prosa = 0
    for modulo in modulos:
        try:
            arvore = ast.parse(modulo.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        traduz = False
        for no in ast.walk(arvore):
            if isinstance(no, ast.ImportFrom) and no.module:
                if "i18n" in no.module or no.module == "gettext":
                    traduz = True
            elif isinstance(no, ast.Import):
                traduz = traduz or any(a.name == "gettext" for a in no.names)
        docstrings = {
            id(n.body[0].value)
            for n in ast.walk(arvore)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and n.body
            and isinstance(n.body[0], ast.Expr)
            and isinstance(n.body[0].value, ast.Constant)
        }
        tem_prosa = any(
            isinstance(no, ast.Constant)
            and isinstance(no.value, str)
            and id(no) not in docstrings
            and _ACENTO.search(no.value)
            for no in ast.walk(arvore)
        )
        com_traducao += int(traduz)
        escrevem_prosa += int(tem_prosa and not traduz)
    return {
        "arquivos": len(modulos),
        "com_traducao": com_traducao,
        "escrevem_prosa": escrevem_prosa,
    }


def bloco_gerado(numeros: dict[str, int]) -> str:
    return (
        f"{MARCA_ABRE} scripts/check_o_projeto_e_traduzivel.py --publicar -->\n"
        f"Dos **{numeros['arquivos']}** arquivos `.py` de "
        "`src/hefesto_dualsense4unix/app/actions/`\n"
        f"— os que escrevem o texto vivo das abas —, **{numeros['escrevem_prosa']}** "
        "escrevem prosa com\n"
        "acentuação portuguesa fora da função de tradução, e "
        f"**{numeros['com_traducao']}** importam essa\n"
        "função. Quem traduzisse os catálogos inteiros veria o esqueleto fixo mudar\n"
        "de idioma e o recado da janela continuar em português.\n"
        "\n"
        "Critério, lido do AST e não de um grep: importa `_` de "
        "`hefesto_dualsense4unix.utils.i18n`\n"
        "ou `gettext`; tem literal com caractere acentuado fora de docstring.\n"
        f"{MARCA_FECHA}"
    )


def conferir_contribuindo(raiz: Path, publicar: bool) -> int:
    alvo = raiz / CONTRIBUINDO
    if not alvo.exists():
        print(f"AUSENTE: {CONTRIBUINDO} não existe nesta árvore.", file=sys.stderr)
        return 1
    texto = alvo.read_text(encoding="utf-8")
    novo = bloco_gerado(censo_das_acoes(raiz))
    padrao = re.compile(
        re.escape(MARCA_ABRE) + r".*?" + re.escape(MARCA_FECHA), re.DOTALL
    )
    if not padrao.search(texto):
        print(
            f"REPROVADO: {CONTRIBUINDO} não tem o bloco CONTAGEM-GERADA. "
            "A contagem da seção «A língua do produto» já saiu de seis jeitos "
            "diferentes conforme a pasta crescia; um número que já saiu de "
            "seis jeitos não é fato, é opinião com cara de dado. "
            "Rode com --publicar.",
            file=sys.stderr,
        )
        return 1
    if publicar:
        alvo.write_text(padrao.sub(lambda _: novo, texto, count=1), encoding="utf-8")
        print(f"publicado: bloco CONTAGEM-GERADA de {CONTRIBUINDO}")
        return 0
    if padrao.search(texto).group(0) != novo:  # type: ignore[union-attr]
        print(
            f"REPROVADO: a contagem publicada em {CONTRIBUINDO} não é a de "
            "hoje. Rode `scripts/check_o_projeto_e_traduzivel.py --publicar`.",
            file=sys.stderr,
        )
        return 1
    return 0


# ---------------------------------------------------------------------------
MEDIDAS = (
    Medida(
        nome="fronteira-de-lingua",
        o_que_conta="arquivos que nenhuma regra de zonas-de-lingua.toml alcança",
        censo=censo_da_fronteira,
        unidade="arquivos",
    ),
    Medida(
        nome="tela-sem-endereco",
        o_que_conta="unidades de texto de tela sem endereço de tradução",
        censo=censo_da_tela,
        unidade="unidades",
        conferir_universo=conferir_as_dez_abas,
    ),
    Medida(
        nome="prosa-publicada",
        o_que_conta="bytes de comentário dentro das páginas publicadas",
        censo=censo_da_prosa,
        unidade="bytes",
        conferir_universo=conferir_as_dez_abas,
    ),
)


def montar(raiz: Path) -> Catraca:
    return Catraca(caderno=raiz / CADERNO, medidas=MEDIDAS, raiz=raiz)


def main(argv: list[str] | None = None) -> int:
    p = montar_argumentos("A catraca da tradução — três medidas, um motor.")
    p.add_argument(
        "--publicar",
        action="store_true",
        help="reescreve o bloco CONTAGEM-GERADA do CONTRIBUTING.md",
    )
    p.add_argument(
        "--so-contagem",
        action="store_true",
        help="só a conferência do CONTRIBUTING.md",
    )
    argumentos = p.parse_args(argv)
    raiz = Path(argumentos.raiz).resolve() if argumentos.raiz else RAIZ

    if argumentos.publicar or argumentos.so_contagem:
        return conferir_contribuindo(raiz, argumentos.publicar)

    rc = executar(
        montar(raiz),
        argumentos,
        "A CATRACA DA TRADUÇÃO — o número não sobe.",
    )
    if argumentos.aceitar is not None or argumentos.forcar_piso:
        return rc
    return max(rc, conferir_contribuindo(raiz, publicar=False))


if __name__ == "__main__":
    raise SystemExit(main())
