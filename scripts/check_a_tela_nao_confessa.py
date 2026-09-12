#!/usr/bin/env python3
"""check_a_tela_nao_confessa.py — nenhum texto de tela confessa dívida NOSSA.

ORDEM DELA, 07/09/2026, e ela vale para a tela inteira
------------------------------------------------------
    *"O app tem que funcionar e não mostrar na tela que o app não presta. Se
     não tem como, ok. Testamos e criamos o canal. até lá tudo bem, o layout
     não informa os nossos defeitos."*

O que ela proíbe é a tela AFIRMAR que o Hefesto não faz algo que **devemos** —
capacidade por entregar, confessada no lugar onde a pessoa está tentando usar o
produto. O que ela permite é a tela dizer **fato do mundo**, **limite do
aparelho ou do sistema** e **estado presente**. As quatro que ela nomeou como
legais, medidas no mesmo dia:

    "o Hefesto não consegue nomear o que o sistema não nomeia"   limite do Linux
    "sem ela o Hefesto não consegue escrever nos controles"      explica o módulo
    "o Hefesto não está entregando o controle ao jogo agora"     estado de agora
    "o Hefesto não volta a perguntar"                            comportamento


A PARTE DIFÍCIL, e por que a régua NÃO é um `grep` de frases proibidas
----------------------------------------------------------------------
As duas famílias têm a MESMA forma. Estas quatro estão na tela hoje e as quatro
são legítimas::

    "O lugar está reservado e o jogo ainda não recebeu este controle"
    "Um traço no lugar do número quer dizer que a leitura ainda não chegou"
    "o menor número que ainda não existe em face nenhuma"
    "O PS+R3 ainda não para aqui"

O que separa não é a palavra — é **de quem é o sujeito**. Quando o sujeito é o
jogo, a leitura ou o número, `ainda não` é estado do mundo. Quando o sujeito
somos nós — o Hefesto, o produto, o perfil, ou a primeira pessoa (*"ainda não
sei olhar"*) —, `ainda não` é uma promessa, e promessa só se faz sobre trabalho
próprio.

Nenhuma expressão regular decide isso sem errar. **Então a régua não decide: ela
OBRIGA A DECLARAR.** Toda frase de tela com a FORMA de confissão tem de estar
numa das duas tabelas abaixo, com a razão escrita e a data:

    `FATOS`      — legítimas. Cada uma diz de quem é o sujeito e por quê.
    `A_DIVIDA`   — confissões que ainda estão na tela, com o endereço de quem
                   as tira e a data em que foram medidas. **Esta lista só
                   encolhe.**

Uma frase nova de qualquer das duas famílias reprova, e quem a escreveu tem de
parar e classificar. É a frição que a ordem dela pede: escrever "o Hefesto ainda
não faz X" na tela deixa de ser um ato de um segundo.

**A CHECAGEM É NOS DOIS SENTIDOS**, pela mesma razão que o portão da lista de
portões: uma frase declarada que a tela não tem mais é uma linha que envelhece
calada, e a próxima pessoa a lê como se a confissão continuasse lá.


O QUE ELE LÊ
------------
1. **As páginas**, na bancada (``mockup/``) e no publicado
   (``interface/paginas/``) — só o que está DENTRO da janela, isto é, tudo
   antes do ``<div class="nota">``. A `.nota` é a legenda do mockup, que a
   própria folha declara *"fora da janela"*: é o documento em que a casa conta
   a ela o que mudou e por quê, e é lá que a dívida DEVE ser nomeada.
   **RELATADO em 07/09/2026:** essa legenda viaja para o publicado, então o
   produto instalado carrega o registro de obra do mockup. Se ela deve ou não
   ir junto é decisão de tela, e a tela é dela.

2. **Toda `Fala`** declarada em ``src/``, pelo campo ``texto=`` — lido por AST,
   sem importar módulo nenhum, como o ``validar-fala-de-tela.py`` já faz. Uma
   `Fala` é texto de tela por construção; o ``porque=`` NÃO é lido, e a
   omissão é o ponto: ele é a razão escrita para quem desenvolve, e é onde a
   dívida deve continuar.

A LIMPEZA VEM ANTES DE QUALQUER CASAMENTO, e não é asseio
---------------------------------------------------------
Comentário HTML, ``<style>`` e ``<script>`` saem do texto ANTES de a régua
olhar. Esta casa pagou a mesma armadilha quatro vezes em quatro dias: *um
comentário que descreve o padrão proibido vira a primeira ocorrência dele*. O
CSS do gerador entra INTEIRO na página, e o comentário que explicava uma
remoção já deixou um portão verde sobre um botão que não existia. Medido: das
dez frases que a primeira varredura desta régua achou, DUAS estavam dentro de
comentários — a explicação, não o defeito.
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
BANCADA = RAIZ / "mockup"
PUBLICADO = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "paginas"  # noqa-acento: nome de PASTA, e caminho nao leva acento
FONTE = RAIZ / "src"


# ---------------------------------------------------------------------------
# A FORMA DA CONFISSÃO — o que a régua manda declarar
# ---------------------------------------------------------------------------
#: `ainda` é o advérbio da dívida: ele promete que a coisa vem. Sobre o mundo
#: ele também aparece ("o jogo ainda não recebeu"), e é por isso que ele MANDA
#: DECLARAR em vez de reprovar sozinho.
#:
#: A primeira pessoa (`não sei`, `não sabemos`, `não conseguimos`) é o produto
#: falando de si; `Hefesto não`, `produto não`, `app não` é o produto sendo
#: falado. As três formas entram na mesma peneira.
FORMA = re.compile(
    r"(?:"
    r"ainda\s+(?:n[ãa]o|falta|estamos)"
    r"|n[ãa]o\s+(?:sabemos|conseguimos|conseguimos|temos\s+como)"
    r"|(?:Hefesto|produto|aplicativo|app)\s+(?:ainda\s+)?n[ãa]o\b"
    r")",
    re.IGNORECASE,
)

# `não sei` SOZINHO NÃO ENTRA, e a exclusão foi MEDIDA nesta leva: a primeira
# peneira o tinha, e das 40 acusações 18 eram a PESSOA falando, não o produto —
# a opção "Não sei" de uma lista da Conexões, o botão "Não sei onde fica" do
# passo a passo, e a explicação de que *"sem resposta não é o mesmo que Não
# sei"*. Ali "não sei" é a voz DELA, e é resposta legítima a uma pergunta que só
# ela pode responder. O `não sei` do PRODUTO vem sempre com o advérbio da
# dívida (*"Ainda não sei olhar este lançador"*), e esse a primeira alternativa
# pega. Uma peneira que confunde a voz da pessoa com a voz do produto obrigaria
# a declarar dezoito frases que nada têm a ver com a ordem dela — e uma tabela
# assim ninguém lê.
#
# `perfil não` TAMBÉM SAIU, pela mesma medição: *"O perfil não guarda uma
# configuração: guarda uma por controle"* é uma afirmação POSITIVA sobre o
# desenho do produto. O caso que importava (*"O perfil ainda não tem por onde
# limitar estes"*) já cai na primeira alternativa, pelo `ainda`.

#: A JANELA DE CONTEXTO que a régua recorta para casar com as tabelas. Frase
#: inteira seria frágil (o `<br>` e o `<b>` entram no meio); um punhado de
#: palavras em volta do sinal é o que identifica sem exigir transcrição exata.
CONTEXTO = 55


def _forma(texto: str) -> list[str]:
    """Os trechos com FORMA de confissão, normalizados para casar com as tabelas."""
    fora = []
    for m in FORMA.finditer(texto):
        ini = max(0, m.start() - CONTEXTO)
        fim = min(len(texto), m.end() + CONTEXTO)
        pedaco = re.sub(r"<[^>]+>", " ", texto[ini:fim])
        fora.append(" ".join(pedaco.split()))
    return fora


# ---------------------------------------------------------------------------
# TABELA 1 — AS LEGÍTIMAS. Cada uma diz DE QUEM é o sujeito, e desde quando.
# ---------------------------------------------------------------------------
#: A chave é um pedaço LITERAL da frase, curto e distintivo. O valor é a razão
#: pela qual ela não é confissão — e ela tem de responder a UMA pergunta: *o
#: sujeito desta frase somos nós?* Se for, a linha pertence à outra tabela.
FATOS: dict[str, str] = {
    "o jogo ainda não recebeu este controle":
        "o sujeito é O JOGO. Estado de agora, e o número fica reservado até ele "
        "entregar — 07/09/2026",
    "a leitura ainda não chegou":
        "o sujeito é A LEITURA do aparelho. Estado de agora: o traço diz que o "
        "dado não veio ainda, não que não venha — 07/09/2026",
    "o menor número que ainda não existe em face nenhuma":
        "o sujeito é O NÚMERO. Fato de aritmética, descrevendo o que o botão "
        "faz — 07/09/2026",
    "O PS+R3 ainda não para aqui":
        "o sujeito é O ATALHO, e a frase diz ONDE ele age — o limite de escopo "
        "de um gesto, não capacidade por entregar — 07/09/2026",
    "o Hefesto não está entregando o controle ao jogo agora":
        "ESTADO DE AGORA, nomeado por ela como legal em 07/09/2026 — a escolha "
        "vale assim que ele voltar a entregar",
    "o Hefesto não volta a perguntar":
        "COMPORTAMENTO, nomeado por ela como legal em 07/09/2026 — a frase diz "
        "o que o botão faz",
    "o Hefesto não consegue nomear o que o sistema não nomeia":
        "LIMITE DO SISTEMA, nomeado por ela como legal em 07/09/2026 — o Linux "
        "não nomeia, e a frase o diz na mesma linha",
    "sem ela o Hefesto não consegue escrever nos controles":
        "LIMITE DE UM PRÉ-REQUISITO EXTERNO, nomeado por ela como legal em "
        "07/09/2026 — explica para que serve o módulo do kernel",
    "o Hefesto não transforma o clique dele em tecla":
        "CONFLITO DE FUNÇÃO, e a frase nomeia a condição na mesma oração "
        "(*enquanto o touchpad for o mouse do computador*). A escolha fica "
        "guardada e volta a valer quando isso mudar — 07/09/2026",
    # A LINHA *"O Hefesto não é só para a Steam"* SAIU EM 11/09/2026, e saiu
    # com a frase: o `?` da aba Lançadores perdeu os dois parágrafos que
    # definiam a aba por negação (A2-002, aprovada por ela). Ela era AFIRMAÇÃO
    # POSITIVA sobre o alcance do produto, declarada em 07/09/2026 porque a
    # peneira a pegava pela forma. **A declaração sai junto por ordem deste
    # próprio portão** — ele confere nos dois sentidos, e uma linha que
    # sobrevive à frase envelhece calada.
}


# ---------------------------------------------------------------------------
# TABELA 2 — A DÍVIDA QUE AINDA APARECE. Esta lista SÓ ENCOLHE.
# ---------------------------------------------------------------------------
#: Cada linha é uma confissão que continua na tela, com o endereço de quem a
#: tira. Ela existe porque a ordem dela chegou depois destas frases, e apagar
#: todas no mesmo commit passaria por arquivos de quatro frentes ao mesmo
#: tempo. **Acrescentar uma linha aqui é dívida nova na tela, e a revisão tem
#: de perguntar por quê.**
#: **AS TRÊS SAÍRAM DA TELA EM 08/09/2026, e a lista está VAZIA.** Elas
#: sobreviveram um dia pela razão escrita acima — apagar todas no mesmo commit
#: passaria por arquivos de quatro frentes ao mesmo tempo —, e caíram quando as
#: frentes fecharam e os quatro arquivos ficaram livres:
#:
#:   "Ainda não sei olhar este lançador"        `interface/desenho_dos_lancadores.py`
#:   "O perfil ainda não tem por onde limitar"  `interface/aba09.py`
#:   "O Hefesto ainda não lê a cor por rádio"   `app/widgets/external_card.py`
#:
#: E CAIU UMA QUARTA que não estava declarada aqui: o `DIZ_ACHEI` do mesmo
#: arquivo dos lançadores dizia *"mas ainda não sei olhar dentro dele: o
#: produto não lê a biblioteca deste lançador"*. Ela não casava com nenhuma
#: forma desta régua — a confissão vinha depois de um "Achei", e a régua olha o
#: começo da frase. **Isso é ponto cego declarado, não linha morta:** quem
#: acrescentar uma confissão no MEIO de uma frase que começa bem continua
#: passando. A cura de verdade é a régua olhar a oração, não a frase.
#:
#: O FATO ÚTIL SOBREVIVEU NAS QUATRO. Nenhuma virou silêncio: as três primeiras
#: passaram a dizer o que o produto FAZ (o perfil casa por processo e janela; o
#: teto não alcança estes; a cor vem da lista), e a dívida continua onde ela
#: mora — o `docs/data/mapa-controles.csv`.
A_DIVIDA: dict[str, str] = {}


# ---------------------------------------------------------------------------
# A LEITURA
# ---------------------------------------------------------------------------
def _limpo(html: str) -> str:
    """A página SEM comentário, `<style>` e `<script>` — nesta ordem, e antes de tudo."""
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    html = re.sub(r"<style\b.*?</style>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<script\b.*?</script>", " ", html, flags=re.S | re.I)
    return html


def _dentro_da_janela(html: str) -> str:
    corte = html.find('<div class="nota">')
    return html if corte < 0 else html[:corte]


def _paginas() -> list[tuple[str, str]]:
    fora = []
    for pasta in (BANCADA, PUBLICADO):
        if not pasta.is_dir():
            continue
        for p in sorted(pasta.glob("*.html")):
            texto = _dentro_da_janela(_limpo(p.read_text(encoding="utf-8")))
            fora.append((str(p.relative_to(RAIZ)), texto))
    return fora


def _falas() -> list[tuple[str, str]]:
    """Todo `texto=` de todo `Fala(...)` de `src/`, por AST — sem importar nada.

    A LEITURA É POR AST e não por regex pela razão que o `validar-fala-de-tela`
    já documenta: importar o módulo para ler a declaração faria a régua depender
    de o pacote inteiro carregar, e um `Fala` mora em arquivo que puxa GTK.
    """
    fora = []
    for p in sorted(FONTE.rglob("*.py")):
        try:
            arvore = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            nome = no.func.id if isinstance(no.func, ast.Name) else (
                no.func.attr if isinstance(no.func, ast.Attribute) else "")
            if nome != "Fala":
                continue
            for kw in no.keywords:
                if kw.arg == "texto" and isinstance(kw.value, ast.Constant) \
                        and isinstance(kw.value.value, str):
                    fora.append((f"{p.relative_to(RAIZ)}:{no.lineno}",
                                 kw.value.value))
    return fora


def main() -> int:
    achados: list[str] = []
    vistas: set[str] = set()

    for onde, texto in _paginas() + _falas():
        for trecho in _forma(texto):
            casou = next((k for k in {**FATOS, **A_DIVIDA} if k.lower() in trecho.lower()),
                         None)
            if casou is None:
                achados.append(f"{onde}\n      …{trecho}…")
            else:
                vistas.add(casou)

    orfas = [k for k in sorted(set(FATOS) | set(A_DIVIDA)) if k not in vistas]

    if achados:
        print(f"FALHA: {len(achados)} frase(s) de tela com forma de confissão "
              f"que ninguém declarou.\n")
        for a in achados[:30]:
            print("  " + a)
        if len(achados) > 30:
            print(f"  … e mais {len(achados) - 30}.")
        print("\nA ordem dela, 07/09/2026: *\"o layout não informa os nossos")
        print("defeitos\"*. Pergunte de quem é o sujeito da frase:")
        print("  • do mundo, do aparelho, do sistema, ou estado de agora")
        print("       -> declare em FATOS, com a razão e a data.")
        print("  • NOSSO, uma capacidade que ainda devemos")
        print("       -> TIRE DA TELA. A dívida fica no mapa e na sprint,")
        print("          que são de quem desenvolve.")
        print("  • sem tempo de tirar agora -> A_DIVIDA, com o endereço e a")
        print("    data. Essa lista só encolhe.")

    if orfas:
        print(f"\nFALHA: {len(orfas)} frase(s) declarada(s) que a tela não tem mais.")
        for k in orfas:
            print(f"  {k!r}")
        print("\nTire-as da tabela: uma declaração que sobrevive à frase")
        print("envelhece calada, e a próxima pessoa a lê como se a confissão")
        print("continuasse na tela.")

    if achados or orfas:
        return 1
    print(f"OK: a tela não confessa dívida nossa — {len(FATOS)} frase(s) "
          f"legítima(s) declarada(s), {len(A_DIVIDA)} dívida(s) ainda na tela.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
