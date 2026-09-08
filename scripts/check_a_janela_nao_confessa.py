#!/usr/bin/env python3
"""check_a_janela_nao_confessa.py — a MOLDURA também é tela dela.

POR QUE ELE NASCEU, e o achado é o valor durável desta frente
--------------------------------------------------------------
Em 08/09/2026 ela abriu o produto instalado, com os quatro DualSense na mesa, e
leu na barra de título da janela:

    Hefesto
    as dez abas, vivas

*"as dez abas, vivas"* é o nome que ESTA CASA deu ao piloto único — o jeito de a
equipe dizer que ele monta as dez abas de verdade. Registro de obra, vazando
para a moldura do produto.

**E ele atravessou incólume as duas réguas de tela desta casa.**
``check_a_conferencia_dela.py`` e ``check_a_tela_nao_confessa.py`` medem o
**corpo das dez páginas** — o HTML. A barra de título é GTK; o ``.desktop`` é
INI; a unit é systemd. *A régua parava na borda da* ``<body>``\\ *, e a tela dela
não para.* Enquanto as dez páginas eram varridas linha por linha, a primeira
coisa que ela lê ao abrir o programa não era medida por ninguém.

O QUE ELE LÊ — a moldura do PRODUTO
------------------------------------
1. **A janela**: todo ``titulo=``/``subtitulo=`` passado como literal, e todo
   ``set_title``/``set_subtitle``, nos arquivos de :data:`A_MOLDURA`. Por AST,
   sem importar módulo nenhum — os arquivos puxam GTK.
2. **Os ``.desktop``**: ``Name``, ``GenericName``, ``Comment``. É o que a dock e
   o menu do sistema mostram antes de a janela existir.
3. **As units systemd**: o nome do arquivo e a ``Description``, que é o que o
   ``systemctl status`` imprime.
4. **A identidade**: ``nome`` e ``nome_longo`` de ``utils/identidade.py``, que é
   o dono único de como o produto se chama.

O VOCABULÁRIO TEM DONO, E ELE NÃO É ESTE ARQUIVO
-------------------------------------------------
Duas das quatro peneiras são LIDAS de quem já as possui, e não copiadas:

* a **forma de confissão** vem de ``check_a_tela_nao_confessa.FORMA`` — por
  ``import``, porque é irmão nesta pasta e não custa dependência nenhuma;
* as **palavras que ela baniu** vêm de
  ``interface/frases_que_ela_baniu.PALAVRAS_BANIDAS`` — por AST, porque importar
  o módulo puxaria o pacote inteiro e o CI roda este arquivo no ``python3``
  pelado.

Uma segunda cópia de qualquer das duas seria a divergência calada que a lista de
portões já pagou: duas réguas respondendo números diferentes sobre a mesma
proibição.

As outras duas peneiras são desta régua, e são a novidade: a LÍNGUA DA OBRA
(:data:`OBRA`) e o APELIDO DA CASA (:data:`APELIDO`) — as palavras com que esta
equipe fala do próprio trabalho, e o jeito como ela chama o piloto.

O QUE ELE NÃO LÊ, e é DECISÃO — o ``<title>`` das dez páginas
--------------------------------------------------------------
As dez páginas trazem ``<title>Hefesto — aba JOGAR (mockup 26/08/2026)</title>``,
e isso É língua da casa. Ele fica de fora porque **nesta janela ninguém o lê**: o
``WebKit2.WebView`` mora dentro de uma ``Gtk.Window`` com ``HeaderBar`` própria,
sem barra de abas e sem barra de endereço — quem escreve o que aparece na
moldura é o ``set_title`` que esta régua já mede.

Pô-lo aqui daria DEZ vermelhos sobre texto que a tela dela não mostra, e isso
tem nome nesta casa: *o instrumento respondendo sobre outra coisa que não o
produto*. Se um dia a página abrir num navegador de verdade — onde o ``<title>``
vira o nome da aba —, ele passa a ser moldura e entra aqui. **Fica escrito para
que a ausência seja decisão e não esquecimento.**

POR QUE NÃO HÁ TABELA DE ISENÇÃO PARA O PRODUTO
------------------------------------------------
O irmão ``check_a_tela_nao_confessa`` tem duas tabelas (``FATOS`` e
``A_DIVIDA``) porque mede **milhares** de frases e nenhuma regex separa o
legítimo do confessado sem errar. Aqui a superfície é outra: **32 textos**, e
cada um é uma decisão de produto deliberada — o nome do app, a dica do lançador,
a descrição da unit. Numa lista desse tamanho, reprovar de vez é a severidade
certa: quem escrever "bancada" na barra de título tem de parar, e a mensagem de
falha diz o que fazer.

Se um dia a moldura precisar legitimamente de uma palavra desta lista, o
caminho é o mesmo do irmão — uma tabela com a razão escrita e a data —, e ela
nasce quando houver a primeira linha para pôr nela. **Tabela vazia criada por
precaução é convite para encher.**

A MORDIDA, e é a que a sprint pediu
------------------------------------
Devolva ``subtitulo="a onda 5 fechou"`` ao ``hefesto_vivo.py`` e esta régua tem
de REPROVAR. Sem isso ela não mede nada — e uma régua que só sabe passar foi o
que deixou este defeito chegar aos olhos dela.

A régua da régua é ``tests/unit/test_a_moldura_nao_fala_a_lingua_de_dentro.py``,
que morde as quatro peneiras uma a uma, o ``.desktop``, e as duas fontes lidas.
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

# o dono da forma de confissão — importado DEPOIS do `sys.path` acima, de
# propósito: é irmão nesta pasta, e uma segunda cópia da peneira aqui seria a
# divergência calada que a lista de portões já pagou.
from check_a_tela_nao_confessa import FORMA

FONTE = RAIZ / "src" / "hefesto_dualsense4unix"

# ---------------------------------------------------------------------------
# ONDE A MOLDURA DO PRODUTO É ESCRITA
# ---------------------------------------------------------------------------
#: Os arquivos que escrevem o que aparece FORA da página, no produto que o
#: lançador dela abre. Cada um com a razão de estar aqui — uma lista de
#: caminhos sem razão envelhece e ninguém sabe se um que falta é esquecimento.
A_MOLDURA: dict[str, str] = {
    "interface/hefesto_vivo.py":
        "o piloto único, e é o que o lançador abre — quem passa `titulo` e "
        "`subtitulo` para a janela",
    "gui/ponte_da_tela.py":
        "a dona da `Gtk.HeaderBar`: `set_title`, `set_subtitle` e o "
        "`Gtk.Window(title=…)` da janela oculta",
    "app/tray.py":
        "o ícone da bandeja — o nome que o sistema mostra fora da janela",
    "app/compact_window.py":
        "a janela compacta, que também chama `set_title`",
    "utils/identidade.py":
        "o dono único de como o produto se chama (`nome`, `nome_longo`), lido "
        "pelo `.desktop`, pelo `--version` e pela bandeja",
}

#: OS PILOTOS DE BANCADA FICAM FORA, e a lista existe para que isso seja
#: DECISÃO e não esquecimento. Eles abrem uma janela cada, com subtítulo
#: próprio, e alguns carregam a palavra que ela baniu em 06/09 — mas nenhum é o
#: produto: o lançador dela abre `hefesto_vivo.py`, e estes se chamam à mão, por
#: quem desenvolve.
#:
#: **SÓ OS CAMINHOS ESTÃO AQUI, e o texto de cada um é LIDO** — a régua abre o
#: arquivo e mostra o que ele diz HOJE. Digitar as frases faria a isenção
#: envelhecer calada no dia em que um deles mudasse de subtítulo, que é a forma
#: de instrumento falso que esta casa mais pagou: *a régua digitava o que devia
#: LER*.
#:
#: A régua IMPRIME esta lista a cada corrida, com as marcas de cada um, em vez de
#: calar: uma isenção silenciosa é como um defeito real vira paisagem. Se um dia
#: um destes virar produto, ele muda de tabela — não de silêncio.
A_BANCADA: tuple[str, ...] = (
    "interface/controles_vivos.py",
    "interface/jogar_vivo.py",
    "interface/conexoes_vivas.py",
    "interface/sistema_viva.py",
    "interface/perfis_vivos.py",
    "interface/ver.py",
)

#: Os `.desktop` e as units. O `.desktop` é o que a dock mostra ANTES de a
#: janela existir; a `Description` da unit é o que o `systemctl status` imprime.
CHAVES_DESKTOP = ("Name", "GenericName", "Comment")
CHAVES_UNIT = ("Description",)


# ---------------------------------------------------------------------------
# O VOCABULÁRIO — duas peneiras próprias, duas lidas do dono
# ---------------------------------------------------------------------------
#: A LÍNGUA DA OBRA: as palavras com que esta equipe fala do próprio trabalho.
#: Nenhuma delas diz nada a quem abriu o programa para configurar um controle.
#:
#: A lista é curta de propósito, e o que ficou de FORA foi medido: `frente`
#: (a tela diz *"o programa na frente"*, e é fato do mundo), `desenho` (a aba
#: Iluminação mostra o desenho do controle) e `nota` (a bateria e o volume não
#: são obra). Uma peneira que os pegasse obrigaria a declarar frase inocente, e
#: tabela que ninguém lê não segura nada.
OBRA = re.compile(
    r"\b(?:"
    r"onda|ondas|leva|levas|sprint|sprints"
    r"|mockup|bancada|piloto|gerador|geradores"
    r"|port[ãa]o|port[õo]es|r[ée]gua|r[ée]guas|mordida"
    r"|worktree|branch|merge|commit|rebase"
    r"|refator\w*|backlog|changelog|hotfix"
    r"|TODO|WIP"
    r")\b",
    re.IGNORECASE,
)

#: O APELIDO DA CASA — *"as dez abas"*, com ou sem o *"vivas"* atrás. É como
#: esta equipe chama o piloto único desde que ele nasceu, e foi o texto que ela
#: leu na barra de título. A contagem entra como número OU por extenso porque as
#: duas formas circulam nos documentos desta casa.
APELIDO = re.compile(
    r"\bas\s+(?:\d+|uma|duas|tr[êe]s|quatro|cinco|seis|sete|oito|nove|dez|onze|doze)"
    r"\s+abas\b"
    r"|\babas,?\s+vivas\b",
    re.IGNORECASE,
)

#: OS IDENTIFICADORES INTERNOS — a mesma família que
#: `check_a_conferencia_dela.a_tela_nao_narra_commit` já proíbe no corpo das
#: dez páginas. Aqui eles valem para a moldura, pela mesma razão.
IDS: tuple[tuple[str, str], ...] = (
    (r"\bD-\d{4}-[A-Z]", "um id de decisão interna"),
    (r"\b[A-Z]{3,}-[A-Z0-9-]+-\d{2}\b", "um id de sprint"),
    (r"\b[0-9a-f]{8}\b(?!\d)", "um hash de commit"),
    (r"\bnoqa\b", "uma marca de régua"),
)


def palavras_que_ela_baniu() -> tuple[str, ...]:
    """`PALAVRAS_BANIDAS`, lida do DONO por AST — nunca copiada para cá.

    A leitura é por AST e não por `import` porque o módulo mora dentro do
    pacote, e importá-lo puxaria `interface/` inteiro; o CI roda esta régua no
    `python3` pelado, sem o pacote instalado.

    **Achar zero é ERRO, não lista vazia.** Uma régua que perde a fonte e segue
    verde é o instrumento falso que esta casa mais paga: ela passaria a medir
    três peneiras onde deveria medir quatro, e ninguém veria.
    """
    dono = FONTE / "interface" / "frases_que_ela_baniu.py"
    arvore = ast.parse(dono.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if isinstance(no, ast.AnnAssign) and isinstance(no.target, ast.Name):
            nome, valor = no.target.id, no.value
        elif isinstance(no, ast.Assign) and len(no.targets) == 1 \
                and isinstance(no.targets[0], ast.Name):
            nome, valor = no.targets[0].id, no.value
        else:
            continue
        if nome != "PALAVRAS_BANIDAS" or not isinstance(valor, ast.Tuple):
            continue
        fora = tuple(e.value for e in valor.elts
                     if isinstance(e, ast.Constant) and isinstance(e.value, str))
        if not fora:
            raise SystemExit(
                f"ERRO: `PALAVRAS_BANIDAS` em {dono.relative_to(RAIZ)} está vazia. "
                f"Uma peneira sem palavra nenhuma dá verde sobre tudo.")
        return fora
    raise SystemExit(
        f"ERRO: não achei `PALAVRAS_BANIDAS` em {dono.relative_to(RAIZ)}. "
        f"O dono da lista mudou de nome ou de lugar, e esta régua ficou cega — "
        f"conserte o ponteiro em vez de deixá-la passar.")


#: As letras que fazem de uma ocorrência um IDENTIFICADOR e não uma palavra.
#: É a mesma borda do dono da lista: `mesa` é nome interno vivo (`mesa_viva.py`,
#: `data-campo="mesa-frase"`), e a sprint diz com todas as letras que o nome
#: fica. Quem trocasse identificador por causa desta lista faria estrago.
_COLADO = r"0-9A-Za-zÀ-ÖØ-öø-ÿ_\-"


def _acusar(texto: str, banidas: tuple[str, ...]) -> list[str]:
    """Tudo o que esta frase de moldura tem de errado, dito por extenso."""
    fora: list[str] = []
    for m in OBRA.finditer(texto):
        fora.append(f"a língua da obra: {m.group(0)!r}")
    for m in APELIDO.finditer(texto):
        fora.append(f"o apelido que esta casa deu ao piloto: {m.group(0)!r}")
    for m in FORMA.finditer(texto):
        fora.append(f"forma de confissão: {m.group(0)!r}")
    for pad, oque in IDS:
        for m in re.finditer(pad, texto):
            fora.append(f"{oque}: {m.group(0)!r}")
    for p in banidas:
        for m in re.finditer(rf"(?<![{_COLADO}]){re.escape(p)}(?![{_COLADO}])",
                             texto, re.IGNORECASE):
            fora.append(f"palavra que ela baniu da tela: {m.group(0)!r}")
    return fora


# ---------------------------------------------------------------------------
# A LEITURA
# ---------------------------------------------------------------------------
#: Os argumentos e os métodos que viram texto de moldura. `titulo_esperado` NÃO
#: entra: ele é a asserção de carga da página (`JanelaDaAba`), não texto que
#: alguém lê.
KWARGS = ("titulo", "subtitulo", "title", "subtitle")
METODOS = ("set_title", "set_subtitle")


def _texto_de_moldura(rel: str, lista: object) -> list[tuple[str, str]]:
    """Todo literal de moldura de UM arquivo de `src/`, por AST.

    **Um caminho que não existe é ERRO.** Esta régua nasceu porque uma tela ficou
    sem dono; uma lista dela apontando para arquivo apagado repetiria o defeito
    num nível acima — e um caminho morto numa lista de isenção é pior ainda,
    porque o vermelho que ele deveria causar simplesmente não acontece.
    """
    p = FONTE / rel
    if not p.is_file():
        raise SystemExit(
            f"ERRO: `{lista}` aponta para {rel}, que não existe. "
            f"A moldura mudou de lugar e esta régua ficou cega para ela.")
    fora: list[tuple[str, str]] = []
    arvore = ast.parse(p.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        metodo = no.func.attr if isinstance(no.func, ast.Attribute) else ""
        if metodo in METODOS:
            for arg in no.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    fora.append((f"{rel}:{no.lineno} ({metodo})", arg.value))
        for kw in no.keywords:
            if kw.arg in KWARGS and isinstance(kw.value, ast.Constant) \
                    and isinstance(kw.value.value, str):
                fora.append((f"{rel}:{no.lineno} ({kw.arg}=)", kw.value.value))
    # a identidade não é chamada: são campos de uma dataclass
    if rel.endswith("identidade.py"):
        for no in ast.walk(arvore):
            if isinstance(no, ast.keyword) and no.arg in ("nome", "nome_longo") \
                    and isinstance(no.value, ast.Constant) \
                    and isinstance(no.value.value, str):
                fora.append((f"{rel} ({no.arg}=)", no.value.value))
    return fora


def da_janela() -> list[tuple[str, str]]:
    """Todo literal de moldura dos arquivos de :data:`A_MOLDURA`."""
    return [t for rel in A_MOLDURA for t in _texto_de_moldura(rel, "A_MOLDURA")]


def da_bancada() -> list[tuple[str, str]]:
    """O mesmo, para os pilotos isentos — LIDO, para a isenção não envelhecer.

    **RÉGUA QUE ACHA ZERO NÃO É RÉGUA VERDE:** um piloto de bancada sem nenhum
    texto de moldura quer dizer que ele deixou de passar `subtitulo`, ou que
    esta régua deixou de saber onde olhar. Nos dois casos a isenção passou a
    isentar nada, e isso se diz em voz alta.
    """
    fora: list[tuple[str, str]] = []
    for rel in A_BANCADA:
        achado = _texto_de_moldura(rel, "A_BANCADA")
        if not achado:
            raise SystemExit(
                f"ERRO: {rel} está isento em `A_BANCADA` e não tem texto de "
                f"moldura nenhum. Ou ele parou de abrir janela — e sai da lista "
                f"—, ou esta régua parou de achar o texto dele.")
        fora += achado
    return fora


def _ini(p: pathlib.Path, chaves: tuple[str, ...]) -> list[tuple[str, str]]:
    """As chaves pedidas de um arquivo `chave=valor`, com a linha.

    O `.desktop` traduzido (`Comment[pt_BR]`) entra junto: a chave com locale é
    o que ela lê de fato, e uma régua que só olhasse a chave nua daria verde
    sobre a tradução.
    """
    fora = []
    for n, linha in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        chave, sep, valor = linha.partition("=")
        if not sep:
            continue
        nua = chave.strip().split("[", 1)[0]
        if nua in chaves:
            fora.append((f"{p.relative_to(RAIZ)}:{n} ({chave.strip()})", valor.strip()))
    return fora


def do_sistema() -> list[tuple[str, str]]:
    """Os `.desktop` e as units — o que o sistema mostra fora da janela.

    O NOME DO ARQUIVO entra junto do conteúdo: a sprint pede *"o nome da
    unit"*, e ele aparece em todo `systemctl --user status`.
    """
    fora: list[tuple[str, str]] = []
    for p in sorted(RAIZ.rglob("*.desktop")):
        if ".git" in p.parts:
            continue
        fora += _ini(p, CHAVES_DESKTOP)
    for p in sorted(RAIZ.rglob("*.service")):
        if ".git" in p.parts:
            continue
        fora.append((f"{p.relative_to(RAIZ)} (nome da unit)", p.name))
        fora += _ini(p, CHAVES_UNIT)
    return fora


def main() -> int:
    banidas = palavras_que_ela_baniu()
    achados: list[str] = []
    lidos = 0

    for onde, texto in da_janela() + do_sistema():
        lidos += 1
        for razao in _acusar(texto, banidas):
            achados.append(f"{onde}\n      {texto!r}\n      -> {razao}")

    print("A BANCADA FICA FORA, e por decisão — estes abrem janela própria, com "
          "subtítulo próprio, e nenhum é o que o lançador dela abre.\n"
          "O texto abaixo é LIDO do arquivo, não digitado nesta régua:")
    marcados = 0
    for onde, diz in da_bancada():
        marcas = _acusar(diz, banidas)
        marcados += bool(marcas)
        print(f"  {onde:<44} {diz!r}"
              + (f"   [{len(marcas)}: {marcas[0]}]" if marcas else ""))
    if marcados:
        print(f"  ({marcados} deles falam a língua de dentro na própria moldura. "
              f"São instrumentos, não o produto — mas o dia em que um virar "
              f"produto, ele muda de tabela, não de silêncio.)")

    if achados:
        print(f"\nFALHA: {len(achados)} texto(s) de MOLDURA falando a língua de "
              f"dentro.\n")
        for a in achados:
            print("  " + a)
        print("\nA moldura é a primeira coisa que ela lê, e o produto instalado a")
        print("mostra antes de qualquer página. O que cabe ali é o que serve a")
        print("QUEM USA; o registro de obra mora na sprint e no `docs/`.")
        print("Se a segunda linha não tem o que dizer a quem usa, ela SAI —")
        print("foi o que aconteceu com `subtitulo=\"as dez abas, vivas\"` em")
        print("08/09/2026, que ela leu na barra de título do produto instalado.")
        return 1

    print(f"\nOK: a moldura não fala a língua de dentro — {lidos} texto(s) de "
          f"janela, `.desktop` e unit, contra {len(banidas)} palavra(s) banida(s) "
          f"e quatro peneiras.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
