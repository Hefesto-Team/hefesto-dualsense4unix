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
    "o Hefesto não volta a perguntar"                            comportamento


A PARTE DIFÍCIL, e por que a régua NÃO é um `grep` de frases proibidas
----------------------------------------------------------------------
As duas famílias têm a MESMA forma. Estas duas estão na tela hoje e as duas
são legítimas::

    "O jogo ainda não recebeu este controle"
    "Um traço no lugar do número quer dizer que a leitura ainda não chegou"

Eram QUATRO até 11/09/2026, e as duas que saíram caíram no mesmo dia, cada uma
por uma aprovação dela: a dica do «Acrescentar entrada» dizia *"o menor número
que ainda não existe em face nenhuma"* — a regra de unicidade é do motor, e
quem clica não escolhe o número —, e a dica dos modos dizia *"O PS+R3 ainda não
para aqui"*, que saiu quando ela mandou encurtar as dicas. Nenhuma das duas foi
tirada por esta peneira: as duas eram legítimas e continuariam podendo ficar.

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
PACOTES = FONTE / "hefesto_dualsense4unix" / "interface" / "pacotes"

#: O que fica no lugar de um pedaço que só existe RODANDO — o nome de um jogo, o
#: número de um assento, a resposta do daemon. Ele não é enfeite: as letras dele
#: não casam com `\s+`, então a peneira da confissão não consegue atravessar o
#: buraco e inventar uma frase que ninguém escreveu.
VALOR_DE_EXECUCAO = "‹…›"


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
    # TRÊS DECLARAÇÕES SAÍRAM DAQUI EM 11/09/2026, e nenhuma porque estivesse
    # errada: as três frases deixaram a tela por aprovação dela, e foi esta
    # régua que cobrou as três retiradas — ela confere nos DOIS sentidos, e
    # *uma classificação que sobrevive à frase envelhece calada*.
    #
    #   · *"o menor número que ainda não existe em face nenhuma"* — o sujeito
    #     era O NÚMERO, fato de aritmética sobre o que o botão faz (07/09).
    #   · *"O PS+R3 ainda não para aqui"* — o sujeito era O ATALHO, e a frase
    #     dizia ONDE ele age (07/09). Saiu com a A3-011: ela mandou encurtar as
    #     dicas dos modos.
    #   · *"o Hefesto não está entregando o controle ao jogo agora"* — estado
    #     de agora, que ela mesma nomeou como legítimo em 07/09. A A3-018
    #     reescreveu a ressalva da máscara, que repetia a entrega duas vezes na
    #     mesma frase.
    "o Hefesto não volta a perguntar":
        "COMPORTAMENTO, nomeado por ela como legal em 07/09/2026 — a frase diz "
        "o que o botão faz",
    "o Hefesto não consegue nomear o que o sistema não nomeia":
        "LIMITE DO SISTEMA, nomeado por ela como legal em 07/09/2026 — o Linux "
        "não nomeia, e a frase o diz na mesma linha",
    "sem ela o Hefesto não consegue escrever nos controles":
        "LIMITE DE UM PRÉ-REQUISITO EXTERNO, nomeado por ela como legal em "
        "07/09/2026 — explica para que serve o módulo do kernel",
    # DUAS DECLARAÇÕES SAÍRAM AQUI EM 11/09/2026, e nenhuma porque estivesse
    # errada: as duas FRASES deixaram de existir na tela, cada uma por uma
    # frente diferente da onda da língua — e foi o próprio portão que cobrou as
    # duas retiradas. Ele confere nos dois sentidos, e *uma declaração que
    # sobrevive à frase envelhece calada*.
    #
    # A PRIMEIRA era
    #
    #     "o Hefesto não transforma o clique dele em tecla"
    #       CONFLITO DE FUNÇÃO, e a frase nomeia a condição na mesma oração
    #       (*enquanto o touchpad for o mouse do computador*) — 07/09/2026
    #
    # e as A5-020 e A5-025, aprovadas por ela, reescreveram os dois lugares em
    # que ela aparecia (`aba06.D_DEFINICOES` e `aba06.MARCA_DO_TOUCHPAD`) para
    # *"o clique dele não vira tecla"*: o mesmo fato, com o sujeito no lugar
    # certo — quem não transforma o clique não somos nós por escolha, é o
    # touchpad, que já tem outro dono. Sem o "o Hefesto não", a peneira nem a
    # pega.
    #
    # A SEGUNDA era *"O Hefesto não é só para a Steam"*, AFIRMAÇÃO POSITIVA
    # sobre o alcance do produto, declarada em 07/09/2026 porque a peneira a
    # pegava pela forma. O `?` da aba Lançadores perdeu os dois parágrafos que
    # definiam a aba por negação (A2-002, aprovada por ela), e a frase foi
    # junto.

    # -- SETE DECLARAÇÕES SAÍRAM AQUI, e as sete no mesmo gesto: 11/09/2026 ---
    # As 352 mudanças de texto que ela aprovou reescreveram as frases que estas
    # linhas classificavam, e a checagem nos DOIS sentidos cobrou uma a uma —
    # que é exatamente o trabalho dela. Nenhuma saiu por estar errada.
    # Duas continuam cobertas por chave mais curta logo acima («o Hefesto não
    # confirmou», «o Hefesto não gravou esta barra»), porque a família inteira
    # de recusas passou a dizer o mesmo de um jeito só. As outras cinco não
    # existem mais em `src/`, conferido por busca antes de sair.

    # -- AS RECUSAS DE EXECUÇÃO, reescritas pela onda da língua de 11/09/2026 --
    # As quatro chaves abaixo cobrem treze recados que ganharam palavras novas
    # DEPOIS de a F5 ensinar o portão a ler o `raise RuntimeError` do gesto. O
    # sujeito gramatical é o produto, e por isso a peneira as pega — mas
    # nenhuma promete trabalho por fazer: as quatro contam o que aconteceu com
    # o ato que a pessoa acabou de pedir, e as três primeiras nomeiam as duas
    # causas possíveis na mesma oração.
    "o Hefesto não confirmou":
        "ESTADO DO ATO: o pedido saiu e a confirmação não voltou. A frase diz "
        "as duas causas na mesma oração (o serviço parou, ou o controle saiu "
        "da mesa) e o que fazer — 11/09/2026",
    "o Hefesto não aplicou":
        "ESTADO DO ATO: o aparelho recusou o que foi mandado, e a frase traz o "
        "que o controle respondeu. Não é capacidade por entregar — o gesto "
        "existe e funcionou antes — 11/09/2026",
    "o Hefesto não gravou esta barra":
        "ESTADO DO ATO, com o gesto que resolve na mesma frase (tentar de "
        "novo) — 11/09/2026",
    "este gatilho ainda não tem modo":
        "o sujeito é O GATILHO, e é estado do que a pessoa escolheu: sem modo "
        "não há ajuste a fazer. A frase diz o passo que falta — 11/09/2026",

    # -- O RECADO DO GESTO, visto pela primeira vez em 11/09/2026 -----------
    # As dezoito de baixo já estavam na tela antes desta data; o que mudou é
    # que a régua passou a ler o canal por onde elas chegam. Todas foram
    # classificadas pela mesma pergunta das de cima: *de quem é o sujeito?*
    "o Hefesto não respondeu":
        "ESTADO DO ATO que acabou de acontecer: o daemon não devolveu resposta, "
        "e a frase diz na mesma linha o que ficou como estava. É a família de "
        "*o Hefesto não está entregando o controle ao jogo agora* — cinco "
        "gestos da Navegação e da Iluminação, inclusive o das lâmpadas com o "
        "co-op ligado, em que a frase ainda nomeia o dono — 11/09/2026",
    "o Hefesto não está rodando — ligue na aba Sistema":
        "ESTADO DE AGORA, e ela diz onde ligar. O serviço parado é fato "
        "presente, não capacidade por entregar — 11/09/2026",
    "o Hefesto não aceitou mirar este controle":
        "ESTADO DO ATO, e a frase diz a consequência (*sem mira a vibração iria "
        "para todos*) e o que fazer — 11/09/2026",
    "o Hefesto não conseguiu mirar este":
        "ESTADO DO ATO, e diz AS DUAS METADES: para onde o volume foi e que o "
        "perfil deste controle não mudou — 11/09/2026",
    "o Hefesto ainda não disse se este sensor está ligado":
        "ESTADO DE AGORA: o dado do daemon não chegou, e a frase diz por que "
        "alternar sem ele seria chutar — 11/09/2026",
    "o Hefesto não precisa de ponte":
        "AFIRMAÇÃO POSITIVA: pelo cabo o PipeWire publica o canal sozinho. A "
        "peneira a pega pela forma, e ela diz o contrário de uma dívida — "
        "11/09/2026",
    "o Hefesto não tem como guardar a quem esta ponte pertence":
        "LIMITE DO APARELHO, e a frase nomeia a causa na mesma oração: este "
        "controle não tem endereço fixo, então não há chave por onde guardar — "
        "11/09/2026",
    "Esta instalação ainda não tem":
        "o sujeito é A INSTALAÇÃO dela — o Proton pinado, a aplicação em massa. "
        "Fato do que está no disco desta máquina — 11/09/2026",}


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
#:
#: **A LISTA VOLTOU A TER LINHA EM 11/09/2026, e nenhuma delas é dívida nova.**
#: As quatro de baixo estão na tela desde antes desta data; o que mudou é que a
#: régua passou a ler o canal por onde elas chegam — o `raise RuntimeError` do
#: gesto. Elas não foram curadas no mesmo gesto porque os quatro arquivos são de
#: outras frentes hoje (as 352 mudanças de texto dela), e reescrever a frase de
#: quem está com o arquivo na mão é como se perde trabalho de duas pessoas.
#: **O endereço de cada uma está aqui, e a lista volta a encolher.**
A_DIVIDA: dict[str, str] = {
    "está desenhado na tela e o Hefesto não sabe montar essa máscara":
        "`interface/pacotes/a01_jogar.py` — a tela OFERECE uma máscara que o "
        "produto não constrói. O que falta é o construtor, e a frase é o "
        "recibo disso no cartão dela — medida em 11/09/2026",
    "ainda não tem dono, e é o INVERSO":
        "`interface/pacotes/a06_navegacao.py` — a primeira metade da mesma "
        "frase, e ela precisa de chave própria: a peneira acha duas vezes na "
        "mesma oração, e cada achado casa com a janela que o cerca — medida "
        "em 11/09/2026",
    "o portão com o sinal trocado —, e ele ainda não existe":
        "`interface/pacotes/a06_navegacao.py` — a lista oferece *Só dentro do "
        "jogo* e o perfil não tem o campo que o sustenta. A opção sai da lista "
        "ou o campo nasce; as duas curas tiram a frase — medida em 11/09/2026",
    # AS DUAS ÚLTIMAS DESTA LISTA SAÍRAM EM 11/09/2026, e não por serem curadas:
    # as frases que elas endereçavam foram reescritas pelas 352 aprovadas por
    # ela. A de `a07_lancadores.py` dizia *"Ainda não sei abrir o …"* com o
    # «por enquanto» que a ordem dela proíbe; a de `a04_iluminacao.py` era um
    # laudo nosso no cartão dela. As duas foram medidas por busca em `src/`
    # antes de sair daqui. **Esta lista só encolhe, e encolheu.**
}


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


# ---------------------------------------------------------------------------
# 3. O RECADO DO GESTO — o terceiro canal, e o que esta régua nunca lia
# ---------------------------------------------------------------------------
# TRÊS AGENTES O ACHARAM SOZINHOS, cada um numa aba, sem se falarem (LINGUA-A2,
# A4 e A5, 11/09/2026). O contrato do piloto é explícito: um `RuntimeError`
# levantado dentro de um gesto quer dizer *"o produto recusou, e a frase VAI PARA
# A TELA"* — `hefesto_vivo._recusou_dizendo` faz `str(erro)` e deposita o texto
# no cartão da coluna em que ela clicou, laranja, por 30 segundos.
#
# Essa frase nunca passou por peneira nenhuma. Ela não é uma `Fala`, não está no
# HTML e nasce montada em execução: f-string, concatenação, uma constante do
# módulo vizinho. A mordida de quem achou foi chamar o casador desta régua com
# as frases dos gestos — elas CASAM. A régua não falhava em reconhecer; ela não
# olhava ali.
#
# POR QUE A RECONSTRUÇÃO É ESTÁTICA, e por que ela declara o que não alcança:
# importar o pacote para ler a frase pediria GTK, daemon e perfil da casa. Então
# a régua monta a frase do jeito que o fonte a escreve, e onde um pedaço só
# existe rodando ela põe :data:`VALOR_DE_EXECUCAO` no lugar. O que sobra sem uma
# letra de prosa não passa calado: cai na terceira tabela, :data:`SEM_LETRA`.
def _arvore(p: pathlib.Path) -> ast.Module | None:
    if p not in _ARVORES:
        try:
            _ARVORES[p] = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):
            _ARVORES[p] = None
    return _ARVORES[p]


_ARVORES: dict[pathlib.Path, ast.Module | None] = {}
_ESCOPOS: dict[pathlib.Path, tuple[dict, dict, dict]] = {}


def _modulo(nome: str, base: pathlib.Path, nivel: int) -> pathlib.Path | None:
    """O arquivo de um `import`, se ele morar DENTRO de `src/`.

    O `nivel` é o do `from . import x`: um ponto é o pacote do próprio arquivo.
    Import de biblioteca de fora devolve `None` e a régua para ali — ler o mundo
    inteiro para montar uma frase de tela seria trocar um ponto cego por uma
    varredura que ninguém termina.
    """
    if nivel:
        pasta = base.parent
        for _ in range(nivel - 1):
            pasta = pasta.parent
        rel = (nome or "").replace(".", "/")
        candidatos = ([pasta / f"{rel}.py", pasta / rel / "__init__.py"]
                      if rel else [pasta / "__init__.py"])
    else:
        if not nome:
            return None
        rel = nome.replace(".", "/")
        candidatos = [FONTE / f"{rel}.py", FONTE / rel / "__init__.py"]
    return next((c for c in candidatos if c.is_file()), None)


def _colher(corpo: list[ast.stmt], p: pathlib.Path) -> tuple[dict, dict, dict]:
    """O que um corpo declara: constantes, apelidos de import e funções.

    Serve para o módulo e para o corpo de uma função, e o segundo importa: meia
    dúzia de gestos faz `from ... import x` DENTRO da função, e quem só olhasse
    o topo do arquivo perderia a frase.
    """
    constantes: dict[str, ast.expr] = {}
    apelidos: dict[str, tuple[str, pathlib.Path, str]] = {}
    funcoes: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for no in corpo:
        if isinstance(no, ast.ImportFrom):
            de = _modulo(no.module or "", p, no.level)
            for n in no.names:
                if n.name == "*":
                    continue
                inteiro = (f"{no.module}.{n.name}" if no.module else n.name)
                sub = _modulo(inteiro, p, no.level)
                if sub is not None:
                    apelidos[n.asname or n.name] = ("módulo", sub, "")
                elif de is not None:
                    apelidos[n.asname or n.name] = ("nome", de, n.name)
        elif isinstance(no, ast.Import):
            for n in no.names:
                achado = _modulo(n.name, p, 0)
                if achado is not None:
                    apelidos[n.asname or n.name.split(".")[0]] = (
                        "módulo", achado, "")
        elif isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcoes[no.name] = no
        elif isinstance(no, ast.Assign):
            for alvo in no.targets:
                if isinstance(alvo, ast.Name):
                    constantes.setdefault(alvo.id, no.value)
        elif isinstance(no, ast.AnnAssign):
            if isinstance(no.target, ast.Name) and no.value is not None:
                constantes.setdefault(no.target.id, no.value)
    return constantes, apelidos, funcoes


def _escopo(p: pathlib.Path) -> tuple[dict, dict, dict]:
    if p not in _ESCOPOS:
        arvore = _arvore(p)
        _ESCOPOS[p] = _colher(arvore.body, p) if arvore else ({}, {}, {})
    return _ESCOPOS[p]


def _dentro(fn: ast.FunctionDef | ast.AsyncFunctionDef,
            p: pathlib.Path) -> tuple[dict, dict, dict]:
    """O corpo da função INTEIRO, e não só o primeiro nível.

    Um `from ... import` e uma frase de recusa moram com frequência dentro de um
    `try` ou de um `if`, que são corpos aninhados. Por isso a colheita percorre
    os filhos — o que se perde é a ORDEM (a régua lê a primeira atribuição a um
    nome, não a que valia naquela linha), e o que se ganha é a frase.
    """
    partes = [_colher([n], p) for n in ast.walk(fn) if isinstance(n, ast.stmt)]
    constantes: dict = {}
    apelidos: dict = {}
    funcoes: dict = {}
    for c, a, f in partes:
        for d, nova in ((constantes, c), (apelidos, a), (funcoes, f)):
            for k, v in nova.items():
                d.setdefault(k, v)
    return constantes, apelidos, funcoes


def _do_dono(fn: ast.FunctionDef | ast.AsyncFunctionDef, p: pathlib.Path,
             prof: int, vistos: frozenset) -> tuple[str, bool]:
    """O que uma função DEVOLVE, para a régua perguntar ao dono da frase.

    É a regra desta casa aplicada à leitura: *quando um valor tem dono, a régua
    PERGUNTA ao dono*. `raise RuntimeError(sem_resposta_do_daemon())` não é frase
    ilegível — é frase que mora uma porta adiante.

    OS RAMOS ENTRAM TODOS, separados pelo buraco: a régua não sabe qual `return`
    acontece, e emendá-los sem separador deixaria a peneira casar por cima da
    costura, inventando uma frase que nenhum caminho produz.
    """
    dentro = _dentro(fn, p)
    pedacos, inteiro, achou = [], True, False
    for no in ast.walk(fn):
        if isinstance(no, ast.Return) and no.value is not None:
            achou = True
            t, c = _montar(no.value, p, dentro, prof + 1, vistos)
            pedacos.append(t)
            inteiro = inteiro and c
    if not achou:
        return VALOR_DE_EXECUCAO, False
    return f" {VALOR_DE_EXECUCAO} ".join(pedacos), inteiro


_TETO = 12


def _montar(no: ast.expr, p: pathlib.Path, local: tuple[dict, dict, dict],
            prof: int = 0, vistos: frozenset = frozenset()) -> tuple[str, bool]:
    """A frase como ela CHEGA ao cartão — e se a régua a montou inteira.

    O segundo valor é o que separa *"li tudo"* de *"li o que deu"*: ele é
    `False` assim que um pedaço vira :data:`VALOR_DE_EXECUCAO`, e é por ele que
    a régua sabe quando tem de confessar o próprio limite.
    """
    if prof > _TETO:
        return VALOR_DE_EXECUCAO, False
    consts, apelidos, funcoes = _escopo(p)
    l_consts, l_apelidos, l_funcoes = local
    consts = {**consts, **l_consts}
    apelidos = {**apelidos, **l_apelidos}
    funcoes = {**funcoes, **l_funcoes}

    if isinstance(no, ast.Constant):
        return ((no.value, True) if isinstance(no.value, str)
                else (VALOR_DE_EXECUCAO, False))

    if isinstance(no, ast.Name):
        chave = (p, no.id)
        if chave in vistos:
            return VALOR_DE_EXECUCAO, False
        adiante = vistos | {chave}
        if no.id in consts:
            return _montar(consts[no.id], p, local, prof + 1, adiante)
        if no.id in funcoes:
            return _do_dono(funcoes[no.id], p, prof, adiante)
        if no.id in apelidos:
            tipo, onde, orig = apelidos[no.id]
            c2, _a2, f2 = _escopo(onde)
            if tipo == "nome" and orig in c2:
                return _montar(c2[orig], onde, ({}, {}, {}), prof + 1, adiante)
            if tipo == "nome" and orig in f2:
                return _do_dono(f2[orig], onde, prof, adiante)
        return VALOR_DE_EXECUCAO, False

    if isinstance(no, ast.Attribute):
        base = no.value
        if isinstance(base, ast.Name) and apelidos.get(base.id, ("", None, ""))[0] == "módulo":
            onde = apelidos[base.id][1]
            chave = (onde, no.attr)
            if chave in vistos:
                return VALOR_DE_EXECUCAO, False
            adiante = vistos | {chave}
            c2, _a2, f2 = _escopo(onde)
            if no.attr in c2:
                return _montar(c2[no.attr], onde, ({}, {}, {}), prof + 1, adiante)
            if no.attr in f2:
                return _do_dono(f2[no.attr], onde, prof, adiante)
        return VALOR_DE_EXECUCAO, False

    if isinstance(no, ast.Call):
        # `str(x)` é embrulho, não dono: a frase é o `x`. Sem esta linha a régua
        # perdia `return str(lightbar_actions._AVISO_HEFESTO_DESLIGADO)`, que é
        # o recado de três botões da Iluminação.
        if isinstance(no.func, ast.Name) and no.func.id == "str" and len(no.args) == 1:
            return _montar(no.args[0], p, local, prof + 1, vistos)
        if isinstance(no.func, (ast.Name, ast.Attribute)):
            return _montar(no.func, p, local, prof, vistos)
        return VALOR_DE_EXECUCAO, False

    if isinstance(no, ast.JoinedStr):
        pedacos, inteiro = [], True
        for parte in no.values:
            t, c = _montar(parte, p, local, prof + 1, vistos)
            pedacos.append(t)
            inteiro = inteiro and c
        return "".join(pedacos), inteiro

    if isinstance(no, ast.FormattedValue):
        t, c = _montar(no.value, p, local, prof + 1, vistos)
        return (t, c) if c else (VALOR_DE_EXECUCAO, False)

    if isinstance(no, ast.BinOp) and isinstance(no.op, ast.Add):
        a, ca = _montar(no.left, p, local, prof + 1, vistos)
        b, cb = _montar(no.right, p, local, prof + 1, vistos)
        return a + b, ca and cb

    if isinstance(no, ast.BoolOp):
        # `motivo or "o Hefesto não respondeu"` põe os DOIS na tela, conforme o
        # dia. Os dois entram, separados pelo buraco.
        pedacos, inteiro = [], True
        for parte in no.values:
            t, c = _montar(parte, p, local, prof + 1, vistos)
            pedacos.append(t)
            inteiro = inteiro and c
        return f" {VALOR_DE_EXECUCAO} ".join(pedacos), inteiro

    if isinstance(no, ast.IfExp):
        a, ca = _montar(no.body, p, local, prof + 1, vistos)
        b, cb = _montar(no.orelse, p, local, prof + 1, vistos)
        return f"{a} {VALOR_DE_EXECUCAO} {b}", ca and cb

    return VALOR_DE_EXECUCAO, False


def _recados() -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Os recados dos gestos: os que a régua LEU, e os que ela não alcançou.

    O primeiro par de cada item é o endereço e a frase montada. O segundo par é
    a lista do que ficou sem uma letra de prosa: `arquivo:gesto ← expressão`, que
    é a chave de :data:`SEM_LETRA`. A chave não leva NÚMERO DE LINHA de
    propósito — uma declaração presa a uma linha envelhece na primeira edição
    acima dela, e a régua que a cobra passaria a cobrar um lugar que se mudou.
    """
    lidos: list[tuple[str, str]] = []
    mudos: list[tuple[str, str]] = []
    for p in sorted(PACOTES.glob("*.py")):
        arvore = _arvore(p)
        if arvore is None:
            continue
        nome_do_arquivo = p.name
        for fn in ast.walk(arvore):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            local = _dentro(fn, p)
            for no in ast.walk(fn):
                if not (isinstance(no, ast.Raise) and isinstance(no.exc, ast.Call)):
                    continue
                alvo = no.exc.func
                qual = (alvo.id if isinstance(alvo, ast.Name)
                        else getattr(alvo, "attr", ""))
                if qual != "RuntimeError" or not no.exc.args:
                    continue
                texto, inteiro = _montar(no.exc.args[0], p, local)
                onde = f"{p.relative_to(RAIZ)}:{no.lineno}"
                if not inteiro and not texto.replace(VALOR_DE_EXECUCAO, "").strip():
                    mudos.append((
                        f"{nome_do_arquivo}:{fn.name} ← "
                        f"{ast.unparse(no.exc.args[0])}", onde))
                lidos.append((onde, texto))
    return lidos, mudos


# ---------------------------------------------------------------------------
# TABELA 3 — O RECADO QUE A RÉGUA NÃO CONSEGUE LER, e de quem ele é
# ---------------------------------------------------------------------------
#: A chave é `arquivo.py:gesto ← expressão`, e o valor diz QUEM é o dono da
#: frase. Ela existe porque um portão que lê 80% e cala os outros 20% é pior que
#: um que não lê nada: quem vê o verde conclui que a tela inteira passou.
#:
#: **Nenhuma linha aqui é permissão.** É o endereço de uma frase que mora fora
#: do alcance da reconstrução estática — quase sempre a resposta do daemon ou um
#: texto do motor (`app/actions/*`) que o gesto só repassa. Quando o dono ganhar
#: uma leitura própria, a linha sai daqui.
#:
#: A CHECAGEM É NOS DOIS SENTIDOS, como nas outras duas tabelas: uma chave que
#: o fonte não tem mais reprova, para a lista não envelhecer calada.
SEM_LETRA: dict[str, str] = {
    # -- A RESPOSTA DO DAEMON, repassada tal como veio ----------------------
    # O gesto pergunta, o daemon recusa com um `motivo`, e o gesto põe esse
    # motivo no cartão sem uma palavra própria. Quem escreve a frase é o
    # `daemon/ipc_handlers.py` e o motor que ele chama.
    "a01_jogar.py:mascara_do_controle ← motivo":
        "a recusa do `gamepad.mask.set`, palavra por palavra do daemon",
    "a02_controles.py:mudo ← frase":
        "a recusa do `mic.set`, montada pelo motor do microfone",
    "a02_controles.py:rota ← desfecho.motivo":
        "o campo `motivo` do desfecho de `app/actions` da rota do som",
    "a04_iluminacao.py:_cobrar_a_frase_do_desenho ← frase":
        "a frase do DONO do desenho das lâmpadas (`app/actions`), devolvida "
        "inteira quando ela difere do desfecho feliz",
    "a05_vibracao.py:parar ← motivo":
        "a recusa do `rumble.stop`, palavra do daemon",
    "a08_conexoes.py:luz_nao_acende ← resultado.porque":
        "o campo `porque` do resultado de `app/actions` da barra de luz",
    "a09_sistema.py:reiniciar ← motivo":
        "a recusa do `systemctl restart`, como o systemd a devolve",
    "a09_sistema.py:retomar ← motivo":
        "a recusa de retomar o serviço, idem",
    "a09_sistema.py:ver_plugins ← motivo":
        "a recusa da leitura dos plugins, idem",
    "a09_sistema.py:_systemctl ← f'{recusa}{(f': {detalhe}' if detalhe else '.')}'":
        "a recusa do systemd mais o detalhe que ele mesmo dá — as duas metades "
        "vêm de fora, e o `f''` só as costura",
    "a10_perfis.py:editor_ambiente ← str(editor.get('ambiente_recado') or '')":
        "o recado do editor de ambiente, escrito em `app/actions` do perfil",
    "a10_perfis.py:editor_jogo ← str(editor.get('ambiente_recado') or '')":
        "idem, pelo caminho do jogo",
    "a06_navegacao.py:guardar_definicoes ← ' '.join(recados)":
        "os recados juntados de várias gravações; cada um nasce no seu dono",
    "a02_controles.py:mudo ← acao.dica":
        "a dica da ação de microfone, que mora no dono da ação",

    # -- O TEXTO MORA EM `app/actions/*`, e o gesto só o busca --------------
    "a01_jogar.py:_plano ← painel.porque_nao_aplica(chave)":
        "`app/actions/jogar/painel.py:porque_nao_aplica` — a razão do cinza, "
        "montada por chave",
    "a01_jogar.py:reconectar ← _painel().RECONECTAR_SEM_SERVICO":
        "`app/actions/jogar/painel.py:RECONECTAR_SEM_SERVICO` — o import é "
        "tardio e vem por uma função, então a régua perde o rastro",
    "a09_sistema.py:restaurar_de_fabrica ← _rodape.frase_do_preset_ausente()":
        "`app/actions/footer_actions.py:frase_do_preset_ausente`",

    # -- A TABELA DO PRÓPRIO ARQUIVO, lida por chave de execução ------------
    "a01_jogar.py:_plano_do_chip ← BOTOES_SEM_DONO.get(f'modo-{chave}', 'sem dono no produto')":
        "o valor sai de um dicionário pela chave do clique; as frases estão no "
        "próprio `a01_jogar.py`, e ler qual delas sai pediria saber a chave",
}


def main() -> int:
    achados: list[str] = []
    vistas: set[str] = set()

    lidos, mudos = _recados()
    for onde, texto in _paginas() + _falas() + lidos:
        for trecho in _forma(texto):
            casou = next((k for k in {**FATOS, **A_DIVIDA} if k.lower() in trecho.lower()),
                         None)
            if casou is None:
                achados.append(f"{onde}\n      …{trecho}…")
            else:
                vistas.add(casou)

    orfas = [k for k in sorted(set(FATOS) | set(A_DIVIDA)) if k not in vistas]

    chaves_mudas = {chave for chave, _ in mudos}
    nao_declarados = sorted(
        (chave, onde) for chave, onde in mudos if chave not in SEM_LETRA)
    sem_dono = [k for k in sorted(SEM_LETRA) if k not in chaves_mudas]

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

    if nao_declarados:
        print(f"\nFALHA: {len(nao_declarados)} recado(s) de gesto que a régua "
              f"NÃO CONSEGUIU LER.\n")
        for chave, onde in nao_declarados:
            print(f"  {onde}\n      {chave}")
        print("\nA frase chega ao cartão dela por `str(erro)`, e aqui ela não")
        print("tem uma letra de prosa que a régua alcance. Diga de quem ela é")
        print("em SEM_LETRA — o dono costuma ser o daemon ou `app/actions/*`.")
        print("Se o dono for ESTE arquivo, escreva a frase no `raise` e a")
        print("régua passa a lê-la sozinha.")

    if sem_dono:
        print(f"\nFALHA: {len(sem_dono)} recado(s) declarado(s) em SEM_LETRA "
              f"que o fonte não tem mais.")
        for k in sem_dono:
            print(f"  {k!r}")
        print("\nTire-os da tabela, pela razão das outras duas: declaração que")
        print("sobrevive ao código vira ponto cego com aparência de cuidado.")

    if achados or orfas or nao_declarados or sem_dono:
        return 1
    print(f"OK: a tela não confessa dívida nossa — {len(FATOS)} frase(s) "
          f"legítima(s) declarada(s), {len(A_DIVIDA)} dívida(s) ainda na tela, "
          f"{len(lidos)} recado(s) de gesto lidos ({len(SEM_LETRA)} com o dono "
          f"declarado fora do alcance).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
