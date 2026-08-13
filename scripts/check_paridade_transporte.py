#!/usr/bin/env python3
"""Censo do mapa de canais: reprova a AUSÊNCIA de rede em volta do que o mapa afirma.

É a CAMADA 0 do portão desenhado em
docs/process/sprints/2026-08-10-INDICE-o-mapa-que-vira-portao.md (seções 4 e 6,
sprint PARIDADE-PORTAO-01). Roda no CI, sem hardware, e responde uma pergunta
só: **o que este mapa afirma tem teste que morda?**

Por que ele existe
------------------
O mapa nasceu com a frase "o mapa de canais existe, e ele é portão — não
documentação". Medido em 11/08/2026: não era. O `--check` do `gerar-mapa.py`
existia e NINGUÉM o chamava — nem workflow, nem hook, nem teste. Pela régua da
casa (PORTÃO-VIVO-01), um gate que ninguém roda não é gate, é arquivo.

E o defeito que o mapa foi feito para pegar é o dela, textual: *"tínhamos algo
para o cabo e na hora do vamos ver a versão de BT não funcionava"*. Uma célula
que diz `aciona = sim, medido` e não aponta um teste é exatamente essa
promessa: se aquela feature quebrar naquele transporte, a suíte inteira
continua verde e ninguém fica sabendo.

O que ele NÃO pega, dito na cara
--------------------------------
Nada aqui toca byte, tempo ou aparelho. O latch da lightbar por rádio (o report
é bem-formado, o CRC bate, e o que separa travar de não travar é o tempo desde
a conexão) passa por este portão sorrindo — quem morde isso são as camadas 1, 2
e 3 do índice. Este arquivo mede AUSÊNCIA, e só.

As regras
---------
FALHA
  1. `sem-mordida`      — célula que afirma `aciona = sim` com
                          `confianca = medido` e `teste_que_morde` vazio.
                          Afirmação forte sem rede é o defeito-mãe da sprint.
  2. `mordida-fantasma` — `teste_que_morde` que aponta para algo que o pytest
                          NÃO coleta (arquivo, classe ou função que não existe,
                          ou nome fora da convenção de coleta). Conferido por
                          LEITURA DE AST de `tests/`, nunca executando a suíte:
                          o portão precisa rodar num runner pelado, e um
                          `ImportError` viraria "zero testes" — o que faria a
                          regra acusar todo mundo.
  3. `prova-vencida`    — `provado_em` + `validade_dias` já no passado. Se as
                          DUAS colunas estiverem vazias, não reprova: a política
                          de validade ainda é decisão dela, e portão que castiga
                          a honestidade é pior que portão nenhum. Data ilegível
                          ou `validade_dias` não inteiro reprovam, porque uma
                          régua que não se consegue ler é uma regra desligada em
                          silêncio.
  4. `integridade`      — coluna do cabeçalho que sumiu, `id` vazio ou
                          duplicado, valor fora do domínio declarado abaixo.
  5. `mapa-nao-publicado` — linha do CSV cujo `id` não aparece no `specs.html`
                          publicado. Ver a nota sobre ela, logo abaixo.
  6. `grau-sem-ensaio`  — célula que declara `grau = SAIU NO FIO` ou
                          `grau = O APARELHO OBEDECEU` e NÃO tem ensaio nenhum
                          em `docs/data/ensaios.csv` para aquele `id` NAQUELE
                          transporte. Ver "o buraco de 12/08", logo abaixo.

AVISO (não derruba o CI hoje)
  7. `assimetria-nao-declarada` — `cabo_aciona` e `radio_aciona` divergem (ou um
                          dos dois nem foi respondido) e `assimetria_declarada`
                          está vazia. Começa como AVISO PORQUE O CSV AINDA ESTÁ
                          SENDO PREENCHIDO: hoje a divergência mais comum é
                          "ninguém respondeu esse lado", que é buraco de censo,
                          não mentira do mapa. Promover para FALHA é trocar
                          `ASSIMETRIA_REPROVA` para True — uma linha, no topo
                          deste arquivo — quando as colunas estiverem fechadas.
  8. `validade-sem-data` — `validade_dias` preenchido com `provado_em` vazio:
                          prazo que não se consegue contar.
  9. `grau-sem-ensaio-que-obedeca` — `grau = O APARELHO OBEDECEU` com ensaios
                          naquele lado, mas nenhum deles dizendo que a FEATURE
                          obedeceu. Desde 13/08/2026 quem responde isso é
                          `resultado_da_feature` quando ela está preenchida, e
                          `resultado` quando não (ver "o preço do `resultado`"
                          abaixo). Segue AVISO e não FALHA porque a coluna nova
                          está preenchida em 1 dos 77 ensaios: enquanto os
                          outros 76 responderem por `resultado`, que é texto
                          livre com semântica de suspeito, promover reprovaria
                          afirmação verdadeira. Promoção por `RESULTADO_REPROVA`.
 10. `grau-sem-olho-dela` — o ensaio que sustenta o `O APARELHO OBEDECEU` existe
                          e diz que obedeceu, mas ninguém do `olho-dela` viu.
                          `docs/process/METODO-DE-ISOLAMENTO.md` (seção "o que
                          registrar em cada linha do mapa") diz que só o olho
                          dela sustenta esse degrau. Promoção por
                          `OLHO_DELA_REPROVA`.
 11. `mordida-nao-provada` — linha com grau forte e `teste_que_morde` preenchido
                          cuja `mordida_provada_em` está vazia: ninguém arrancou
                          a cura e viu reprovar. Medido em 12/08/2026: a coluna
                          está vazia em 293 de 293 linhas e nenhuma regra a lia.
 12. `veredicto-da-feature-mal-declarado` — a guarda da coluna nova, e a razão
                          de ela não ser um afrouxamento. DURA, em duas metades:
                          `resultado_da_feature` fora do vocabulário do caderno
                          reprova, e `resultado_da_feature` que DIVERGE de
                          `resultado` com a `nota` do ensaio vazia reprova
                          também. Quem quiser calar a regra 9 escrevendo
                          `obedece` nesta coluna tem de escrever no caderno, na
                          mesma linha, o que o aparelho fez — que é exatamente o
                          que a casa cobra em toda parte.

O buraco de 12/08/2026, e por que a regra 6 nasceu
--------------------------------------------------
Um agente escreveu numa cópia da árvore a afirmação mais forte que o vocabulário
da casa permite — `cabo_grau = radio_grau = O APARELHO OBEDECEU`, `provado_por =
olho-dela` — numa linha com ZERO ensaios no caderno de bancada, e o portão
devolveu exatamente o mesmo número de reprovações de antes: quinze. A mentira
passou inteira, e por três motivos que este arquivo tinha por escrito:

  - `docs/data/ensaios.csv` não era citado aqui uma única vez. O caderno de
    bancada — o arquivo onde mora o que o aparelho FEZ — não era fonte de
    verdade de portão nenhum;
  - as colunas `cabo_grau`/`radio_grau` não entravam em domínio nenhum, então
    `O APARELHO OBEDECEU` era escrevível em qualquer linha, de graça;
  - `mordida_provada_em` estava vazia em todas as linhas e ninguém a lia.

A regra que ela aprovou é uma frase: **grau forte exige ensaio correspondente**.
O casamento é por `linha_id` == `id` E por transporte, porque `SAIU NO FIO` no
cabo não se sustenta com ensaio de rádio — foi a assimetria cabo/rádio que fez
este mapa existir. Quem casa os dois é `scripts/eliminacao.py`, reusado aqui em
vez de reimplementado: uma segunda leitura do caderno seria uma segunda régua
para o mesmo dado, e nesta casa o instrumento já mentiu mais que o produto.

O preço do `resultado`, dito na cara
------------------------------------
`resultado` é texto livre. Os quatro valores que o caderno usa hoje (12/08/2026)
foram LIDOS dele, não inventados aqui: `obedece`, `não obedece`, `parcial`,
`inconclusivo`. E a semântica deles é do SUSPEITO da linha, não da feature: o
ensaio `gatilho-lado-nao-esta-invertido` está gravado como `não obedece` — o
suspeito "o mapeamento está invertido" foi eliminado — enquanto a nota do mesmo
ensaio diz que o R2 endureceu, isto é, que o aparelho obedeceu. Cobrar
`resultado` como FALHA seria reprovar uma afirmação verdadeira por causa de uma
coluna que responde outra pergunta. Por isso a regra 6 (dura) cobra a EXISTÊNCIA
do ensaio, e a 9 (aviso) é que olha o resultado.

A coluna que a casa já tinha encomendado (13/08/2026)
-----------------------------------------------------
A constante `RESULTADO_REPROVA` trazia a encomenda por escrito desde 12/08: "o
dia de promover isto é o dia em que o caderno ganhar uma coluna que diga o que a
FEATURE fez, separada do que o SUSPEITO provou". A coluna chegou, e chama-se
`resultado_da_feature` — o nome sai da frase da própria regra 9, que já dizia
"o `resultado` do SUSPEITO em vez do que a FEATURE fez".

Como ela funciona, e por que não é um afrouxamento:

  - VAZIA é o padrão, e vazia quer dizer "`resultado` também responde pela
    feature". Foi assim que 76 dos 77 ensaios ficaram intocados: nenhuma
    medição dela foi reescrita, que era a condição do pedido;
  - PREENCHIDA, ela responde pelas regras 9 e 10 no lugar de `resultado` — e só
    por elas. `scripts/eliminacao.py` continua julgando o suspeito por
    `resultado`, porque é o suspeito que ele julga. Uma coluna, duas perguntas,
    nenhuma régua nova;
  - e ela é CARA de preencher, pela regra 12: o valor tem de estar no
    vocabulário do caderno, e divergir de `resultado` exige `nota` escrita. É o
    que separa "corrigir a leitura de uma coluna" de "desligar a guarda".

O ensaio que motivou tudo isso é um só, e ele tem o par que o confirma: a MESMA
linha (`gatilho.direito.adaptativo@dualsense`) tem `gatilho-dir-radio-isolado-2221`
por rádio com `resultado = obedece`. O degrau estava certo; a coluna é que
estava sendo lida errado.

Por que a regra 5 nasceu, e o que ela ainda faz
-----------------------------------------------
Ela nasceu porque o `--check` do `gerar-mapa.py` comparava MTIME, e mtime no CI
é ordem de checkout, não histórico de edição: o `actions/checkout` escreve os
arquivos em ordem de caminho, e `specs.html` (raiz, "sp") sai depois de `docs/`
e de `scripts/` — então ele nascia sempre "mais novo" que as fontes e passava
SEMPRE, independente do conteúdo. Este censo era o único que mordia por
conteúdo no runner.

Desde a MAPA-CONTEUDO-01 (12/08/2026) aquele `--check` regenera a página em
memória e compara o CONTEÚDO inteiro, então ele morde no CI também — e morde
mais fundo que esta regra, que só pergunta pelo `id`. A regra 5 continua por
duas razões: ela roda sem depender do gerador (se ele quebrar, o censo ainda
responde) e ela aponta a LINHA do CSV que ficou de fora, enquanto o `--check`
manda regerar a página inteira.

Limite honesto da regra 5: ela pega a linha NOVA que ninguém publicou. Linha
REMOVIDA do CSV e ainda publicada no HTML ela não vê — quem vê isso é o
`--check` por conteúdo.

Uso:
    python3 scripts/check_paridade_transporte.py
    python3 scripts/check_paridade_transporte.py --raiz /outro/repo
    python3 scripts/check_paridade_transporte.py --csv /tmp/mapa.csv --raiz /tmp/arvore
"""
from __future__ import annotations

import argparse
import ast
import csv
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

#: `scripts/` não é pacote, e este portão precisa do `eliminacao.py`, que já sabe
#: casar `linha_id` do ensaio com `id` do mapa SEPARANDO cabo de rádio. O
#: `append` (e não `insert(0, …)`) é para um arquivo homônimo em `scripts/` nunca
#: sombrear módulo da biblioteca padrão. O `eliminacao.py` só importa `csv`,
#: `collections`, `dataclasses` e `pathlib`, então o portão continua rodando num
#: runner pelado, sem as dependências do projeto.
sys.path.append(str(Path(__file__).resolve().parent))

from eliminacao import carrega_por_lado

#: PROMOÇÃO DA REGRA 7. Trocar para True faz a assimetria não declarada
#: REPROVAR em vez de avisar. Fica False enquanto as colunas `cabo_*`/`radio_*`
#: estiverem sendo preenchidas: hoje a maior parte das divergências é ausência
#: de resposta, e reprovar ausência de resposta aqui seria cobrar duas vezes o
#: que a regra 1 já cobra, castigando quem está justamente preenchendo o mapa.
ASSIMETRIA_REPROVA = False

#: Os dois lados de cada linha. O par de colunas é descoberto por SUFIXO a
#: partir do cabeçalho (ver `pares_de_transporte`) — nunca por lista fixa, e
#: nunca por contagem: o CSV cresce todo dia, e régua com número dentro
#: apodrece no dia seguinte.
LADOS = ("cabo", "radio")

#: O nome do lado em prosa. As COLUNAS não levam acento (`radio_aciona` é
#: identificador), mas o texto que a pessoa lê, sim.
ROTULO_DO_LADO = {"cabo": "cabo", "radio": "rádio"}

#: PROMOÇÃO DA REGRA 9. Trocar para True faz o `O APARELHO OBEDECEU` sustentado
#: só por ensaios que NEGAM reprovar em vez de avisar.
#:
#: A coluna encomendada aqui em 12/08 — "o dia de promover isto é o dia em que o
#: caderno ganhar uma coluna que diga o que a FEATURE fez, separada do que o
#: SUSPEITO provou" — chegou em 13/08/2026: é `resultado_da_feature`. Mas
#: continua False, e o motivo é uma contagem, não teimosia: ela está preenchida
#: em 1 dos 77 ensaios. Nos outros 76 quem responde ainda é `resultado`, que
#: segue sendo texto livre com semântica de suspeito — promover hoje reprovaria
#: exatamente as afirmações verdadeiras que este arquivo passou uma seção
#: inteira explicando por que não se deve reprovar. O dia de promover é o dia em
#: que nenhum grau forte depender mais de `resultado` para ser lido.
RESULTADO_REPROVA = False

#: PROMOÇÃO DA REGRA 10. Trocar para True faz o degrau mais alto exigir que
#: alguém do `olho-dela` tenha visto. Fica False porque ela aprovou uma frase —
#: "grau forte exige ensaio correspondente" — e cobrar QUEM observou é uma
#: segunda regra, que ninguém pediu. Medido em 12/08/2026: promovê-la hoje
#: custaria ZERO reprovações novas, então o preço de deixá-la avisando é só o
#: futuro.
OLHO_DELA_REPROVA = False

CSV_RELATIVO = "docs/data/mapa-controles.csv"
ENSAIOS_RELATIVO = "docs/data/ensaios.csv"
SPECS_RELATIVO = "specs.html"
PASTA_DE_TESTES = "tests"

#: Colunas sem as quais este portão não tem o que medir. A ausência de qualquer
#: uma é FALHA de integridade, não motivo para o portão se desligar calado.
COLUNAS_EXIGIDAS = (
    "chave",
    "controle",
    "existe",
    "teste_que_morde",
    "provado_em",
    "validade_dias",
    "assimetria_declarada",
    "id",
)

#: Sufixos de par `cabo_X`/`radio_X` que as regras usam. Se um deles sumir do
#: cabeçalho, a regra que depende dele morre — por isso a ausência reprova.
#:
#: `grau` entra aqui, e a distinção com as colunas que apenas DESLIGAM a regra
#: (o `tests/`, o `specs.html`, o próprio caderno de ensaios) é esta: regra dura
#: não se desliga em silêncio. `cabo_grau` é onde mora a afirmação mais forte
#: que este mapa sabe fazer; perder a coluna é perder a régua da regra 6, e o
#: portão tem de gritar em vez de passar.
SUFIXOS_EXIGIDOS = ("aciona", "confianca", "canal", "grau")

#: Domínio de cada coluna. Vazio é SEMPRE aceito, e isso é decisão de desenho:
#: o próprio `specs.html` declara no rodapé que "vazio aqui é pergunta aberta,
#: nunca não". Valor novo que não estiver nesta tabela reprova — de propósito.
#: Acrescentar um valor ao mapa é acrescentá-lo aqui, no mesmo gesto, senão a
#: régua passa a aprovar o que não sabe ler.
#:
#: `aciona`/`aceita` entram aqui embora o pedido só citasse canal/confiança/
#: existe: a regra 1 e a 7 leem `aciona`, e um valor novo ali (um "sim?" com
#: interrogação, por exemplo) desligaria as duas EM SILÊNCIO.
#:
#: `grau` entrou em 12/08/2026 pelo mesmo motivo, e ele custou caro: sem domínio,
#: `O APARELHO OBEDECEU` era escrevível de graça em qualquer linha, e um degrau
#: escrito com outra tipografia (`o aparelho obedeceu`, minúsculo) passaria pela
#: regra 6 sem ser visto — a mentira sairia pela porta que a régua não olha.
DOMINIO_POR_SUFIXO = {
    "aciona": frozenset({"", "sim", "não", "parcial", "desconhecido"}),
    "aceita": frozenset({"", "sim", "não", "parcial", "desconhecido"}),
    "canal": frozenset(
        {"", "hidraw", "uhid", "evdev", "sysfs", "dbus", "alsa-pipewire", "outro"}
    ),
    "confianca": frozenset(
        {"", "medido", "inferido-do-codigo", "afirmado-no-doc", "incerto"}
    ),
    "grau": frozenset({"", "MONTOU", "SAIU NO FIO", "O APARELHO OBEDECEU"}),
}
DOMINIO_EXISTE = frozenset({"", "tem", "nao-tem", "parcial", "desconhecido"})

#: O que conta como "afirmação forte": o produto ACIONA aquilo, e alguém MEDIU.
#: `parcial` fica de fora de propósito — é uma afirmação com ressalva, e a
#: sprint quer a rede primeiro onde a promessa é inteira.
ACIONA_FORTE = "sim"
CONFIANCA_FORTE = "medido"

#: A escada de grau, tal como `docs/process/METODO-DE-ISOLAMENTO.md` a define:
#: MONTOU (montou o report) -> SAIU NO FIO (o byte saiu, algo voltou) ->
#: O APARELHO OBEDECEU (acendeu, girou, saiu som).
GRAU_MONTOU = "MONTOU"
GRAU_SAIU_NO_FIO = "SAIU NO FIO"
GRAU_OBEDECEU = "O APARELHO OBEDECEU"

#: Os dois degraus que só a bancada sustenta — e por isso os dois que a regra 6
#: cobra no caderno. `MONTOU` fica de fora de propósito: montar o report é o que
#: a suíte prova sozinha, sem aparelho, e cobrar ensaio dele seria pedir bancada
#: para algo que o pytest já morde.
GRAUS_QUE_EXIGEM_ENSAIO = (GRAU_SAIU_NO_FIO, GRAU_OBEDECEU)

#: O que, em `resultado`, conta como "o aparelho obedeceu". LIDO do caderno em
#: 12/08/2026 (`obedece`, `não obedece`, `parcial`, `inconclusivo`), não
#: inventado aqui — e por isso a regra que o usa é AVISO: um valor novo no
#: caderno não pode virar reprovação sem alguém ter dito o que ele significa.
RESULTADOS_QUE_SUSTENTAM = frozenset({"obedece"})

#: A coluna do caderno que diz o que a FEATURE fez, quando `resultado` está
#: respondendo pelo SUSPEITO. Vazia é o padrão e quer dizer "`resultado` também
#: responde pela feature" — por isso acrescentá-la não mexeu em ensaio nenhum.
COLUNA_DO_VEREDICTO_DA_FEATURE = "resultado_da_feature"

#: O vocabulário inteiro do caderno, LIDO dele em 12/08/2026 e recontado em
#: 13/08 (47 `obedece`, 24 `não obedece`, 5 `parcial`, 1 `inconclusivo`, em 77
#: ensaios). É o domínio da coluna nova: ela responde a MESMA pergunta que
#: `resultado`, só que sobre a feature, então inventar valor novo ali seria
#: inventar um segundo vocabulário para a mesma escala.
RESULTADOS_DO_CADERNO = frozenset(
    {"obedece", "não obedece", "parcial", "inconclusivo"}
)

#: Quem, em `observado_por`, sustenta o degrau mais alto. A régua é do
#: METODO-DE-ISOLAMENTO: "só `olho-dela` sustenta *O APARELHO OBEDECEU*".
OBSERVADOR_QUE_SUSTENTA = "olho-dela"

#: Convenção de coleta do pytest (não há `python_files`/`python_functions`
#: customizados no pyproject.toml desta árvore).
PREFIXO_DE_ARQUIVO = "test_"
SUFIXO_DE_ARQUIVO = "_test.py"
PREFIXO_DE_FUNCAO = "test"
PREFIXO_DE_CLASSE = "Test"

#: Separadores aceitos quando a célula aponta mais de um teste.
_SEPARADOR_DE_ALVOS = re.compile(r"[;\n]+")

#: Formatos de data aceitos em `provado_em`. O ISO é o da casa em arquivo de
#: dado (CHANGELOG, metainfo); o brasileiro entra porque é o que ela escreve em
#: prosa, e recusá-lo seria transformar tipografia em reprovação.
_FORMATOS_DE_DATA = ("%Y-%m-%d", "%d/%m/%Y")

FALHA = "FALHA"
AVISO = "AVISO"


@dataclass(frozen=True)
class Achado:
    """Uma reprovação (ou aviso): onde, qual regra, e o que está errado."""

    nivel: str
    regra: str
    linha: int
    ident: str
    lado: str
    texto: str

    def __str__(self) -> str:
        onde = f"linha {self.linha}"
        if self.ident:
            onde += f" ({self.ident})"
        if self.lado:
            onde += f" [{self.lado}]"
        return f"  {self.nivel} {self.regra}: {onde}: {self.texto}"


@dataclass
class ArquivoDeTeste:
    """O que o pytest coletaria de um arquivo, lido por AST."""

    funcoes: frozenset[str] = frozenset()
    classes: dict[str, frozenset[str]] = field(default_factory=dict)


@dataclass
class Resumo:
    """Os números que dizem onde o mapa está cego. Nenhum deles é limiar."""

    linhas: int = 0
    celulas: int = 0
    celulas_mudas: int = 0
    celulas_que_afirmam: int = 0
    celulas_medidas: int = 0
    afirmacoes_fortes: int = 0
    afirmacoes_fortes_sem_rede: int = 0
    linhas_com_mordida: int = 0
    linhas_mudas_dos_dois_lados: int = 0
    assimetrias_nao_declaradas: int = 0
    alvos_de_teste: int = 0
    graus_fortes: int = 0
    graus_fortes_sem_ensaio: int = 0
    ensaios_no_caderno: int = 0


def e_arquivo_que_pytest_coleta(nome: str) -> bool:
    """A convenção padrão: `test_*.py` ou `*_test.py`."""
    return nome.startswith(PREFIXO_DE_ARQUIVO) or nome.endswith(SUFIXO_DE_ARQUIVO)


def indexar_testes(raiz: Path) -> dict[str, ArquivoDeTeste]:
    """Mapeia `caminho relativo -> o que o pytest coletaria`, por AST.

    Ler por AST em vez de importar (ou de rodar `--collect-only`) é deliberado,
    e o motivo é o mesmo do `validar-referencias-docs.py`: o portão roda num
    runner sem as dependências do projeto, e qualquer tropeço de importação
    viraria "nenhum teste existe" — fazendo a regra 2 acusar TODA célula que
    aponta uma mordida. Um gate que reprova tudo quando tropeça é pior que gate
    nenhum, então a ausência de `tests/` devolve índice vazio e a regra 2 se
    desliga sozinha, dizendo isso em voz alta no resumo.
    """
    indice: dict[str, ArquivoDeTeste] = {}
    pasta = raiz / PASTA_DE_TESTES
    if not pasta.is_dir():
        return indice

    for caminho in sorted(pasta.rglob("*.py")):
        if not e_arquivo_que_pytest_coleta(caminho.name):
            continue
        try:
            arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):  # pragma: no cover - defensivo
            continue

        funcoes: set[str] = set()
        classes: dict[str, frozenset[str]] = {}
        for no in arvore.body:
            if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if no.name.startswith(PREFIXO_DE_FUNCAO):
                    funcoes.add(no.name)
            elif isinstance(no, ast.ClassDef) and no.name.startswith(PREFIXO_DE_CLASSE):
                classes[no.name] = frozenset(
                    metodo.name
                    for metodo in no.body
                    if isinstance(metodo, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and metodo.name.startswith(PREFIXO_DE_FUNCAO)
                )
        relativo = caminho.relative_to(raiz).as_posix()
        indice[relativo] = ArquivoDeTeste(frozenset(funcoes), classes)
    return indice


def alvos_da_celula(texto: str) -> list[str]:
    """Quebra a célula `teste_que_morde` nos alvos que ela aponta."""
    return [pedaco.strip() for pedaco in _SEPARADOR_DE_ALVOS.split(texto) if pedaco.strip()]


def motivo_de_o_pytest_nao_coletar(
    alvo: str, indice: dict[str, ArquivoDeTeste], raiz: Path
) -> str | None:
    """Devolve por que o pytest não coletaria este alvo, ou None se coletaria.

    A gramática aceita é a do id de nó do pytest, que é o que se copia da saída
    da suíte e se cola no terminal:
        tests/unit/test_x.py
        tests/unit/test_x.py::test_y
        tests/unit/test_x.py::test_y[algum-parametro]
        tests/unit/test_x.py::TestClasse::test_y
    """
    caminho, _, resto = alvo.partition("::")
    caminho = caminho.strip()

    if not caminho.startswith(f"{PASTA_DE_TESTES}/"):
        return (
            f"`{alvo}` não é alvo de pytest. Escreva o id do nó "
            f"({PASTA_DE_TESTES}/.../test_x.py::test_y) ou deixe a célula VAZIA "
            "— vazio é pergunta aberta, prosa aqui é rede que não existe"
        )

    arquivo = indice.get(caminho)
    if arquivo is None:
        if (raiz / caminho).is_file():
            return (
                f"`{caminho}` existe mas o pytest NÃO o coleta "
                f"(o nome precisa ser `{PREFIXO_DE_ARQUIVO}*.py` ou `*{SUFIXO_DE_ARQUIVO}`)"
            )
        return f"`{caminho}` não existe nesta árvore"

    partes = [parte for parte in resto.split("::") if parte.strip()]
    if not partes:
        return None
    partes[-1] = partes[-1].split("[", 1)[0].strip()

    if len(partes) == 1:
        nome = partes[0]
        if nome in arquivo.funcoes or nome in arquivo.classes:
            return None
        return f"`{caminho}` não tem `{nome}` que o pytest colete"

    if len(partes) == 2:
        classe, metodo = partes
        if classe not in arquivo.classes:
            return f"`{caminho}` não tem a classe `{classe}` que o pytest colete"
        if metodo not in arquivo.classes[classe]:
            return f"`{classe}` em `{caminho}` não tem o teste `{metodo}`"
        return None

    return f"`{alvo}` tem mais níveis do que um id de nó do pytest carrega"


def le_data(texto: str) -> date | None:
    """A data de `provado_em`, ou None se ilegível."""
    for formato in _FORMATOS_DE_DATA:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def pares_de_transporte(cabecalho: list[str]) -> dict[str, tuple[str, str]]:
    """Descobre os pares `cabo_X`/`radio_X` pelo SUFIXO, lendo o cabeçalho.

    Nunca por lista fixa e nunca por contagem: o mapa ganha colunas e linhas a
    cada leva, e uma régua com o número de hoje escrito dentro reprova amanhã
    por ter envelhecido, não por ter achado defeito.
    """
    colunas = set(cabecalho)
    pares: dict[str, tuple[str, str]] = {}
    prefixo = f"{LADOS[0]}_"
    for coluna in cabecalho:
        if not coluna.startswith(prefixo):
            continue
        sufixo = coluna[len(prefixo) :]
        irmao = f"{LADOS[1]}_{sufixo}"
        if irmao in colunas:
            pares[sufixo] = (coluna, irmao)
    return pares


def ids_publicados(specs: Path) -> str | None:
    """O texto do `specs.html`, ou None quando não há o que conferir.

    Devolver o texto inteiro e procurar o `id` dentro dele por substring é de
    propósito: o `id` (`chave@controle`) é distintivo o bastante, e assim a
    regra não fica refém do formato exato com que o `gerar-mapa.py` serializa o
    JSON embutido. Se o gerador trocar `json.dumps` por outra coisa, esta regra
    continua valendo.
    """
    try:
        return specs.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def caderno_de_ensaios(raiz: Path) -> tuple[dict[tuple[str, str], list[dict]] | None, str]:
    """O caderno de bancada indexado por (`linha_id`, transporte), ou None.

    Devolve `(índice, motivo)`: com `None` no índice, `motivo` diz por que a
    regra 6 não tem o que ler. A leitura é a do `scripts/eliminacao.py` — reuso
    deliberado, porque é ele quem já separa cabo de rádio e é ele que o resto da
    casa usa para julgar suspeito. Duas leituras do mesmo caderno seriam duas
    réguas para o mesmo dado, e uma delas envelheceria calada.

    Caderno ausente (ou sem as colunas que o casamento exige) DESLIGA a regra em
    vez de acusar todo mundo: é a mesma decisão do índice de testes por AST logo
    acima. O desligamento é DITO no resumo, nunca calado.
    """
    caminho = raiz / ENSAIOS_RELATIVO
    if not caminho.is_file():
        return None, (
            f"grau-sem-ensaio ({ENSAIOS_RELATIVO} ausente — sem o caderno de "
            "bancada não há o que casar com o grau)"
        )
    try:
        return carrega_por_lado(caminho), ""
    except (OSError, UnicodeDecodeError, KeyError, csv.Error) as erro:
        # `csv.Error` entra na lista porque sem ele um caderno MALFORMADO (aspas
        # abertas, campo gigante) derrubava o portão inteiro com traceback — o
        # oposto do que esta função promete duas linhas acima, que é desligar a
        # regra EM VOZ ALTA. Um portão que morre calado por causa do dado que
        # veio medir é a armadilha da casa: o instrumento mente mais que o
        # produto.
        return None, (
            f"grau-sem-ensaio ({ENSAIOS_RELATIVO} ilegível para o casamento: "
            f"{erro!r} — o caderno precisa das colunas `linha_id` e `transporte`)"
        )


def censo(
    caminho_csv: Path, raiz: Path, hoje: date
) -> tuple[list[Achado], Resumo, list[str]]:
    """Roda as regras. Devolve (achados, resumo, regras desligadas)."""
    achados: list[Achado] = []
    resumo = Resumo()
    desligadas: list[str] = []

    with caminho_csv.open(encoding="utf-8", newline="") as arquivo:
        leitor = csv.DictReader(arquivo)
        cabecalho = list(leitor.fieldnames or [])
        registros = [(leitor.line_num, linha) for linha in leitor]

    faltando = [coluna for coluna in COLUNAS_EXIGIDAS if coluna not in cabecalho]
    pares = pares_de_transporte(cabecalho)
    faltando += [
        f"{lado}_{sufixo}"
        for sufixo in SUFIXOS_EXIGIDOS
        if sufixo not in pares
        for lado in LADOS
    ]
    if faltando:
        achados.append(
            Achado(
                FALHA,
                "integridade",
                1,
                "",
                "",
                "o cabeçalho perdeu coluna(s): " + ", ".join(sorted(set(faltando))),
            )
        )
        return achados, resumo, desligadas

    indice_de_testes = indexar_testes(raiz)
    if not indice_de_testes:
        desligadas.append(
            "mordida-fantasma (nenhum arquivo de teste indexado sob "
            f"{PASTA_DE_TESTES}/ — a regra se desliga em vez de acusar tudo)"
        )

    texto_do_specs = ids_publicados(raiz / SPECS_RELATIVO)
    if texto_do_specs is None:
        desligadas.append(
            f"mapa-nao-publicado ({SPECS_RELATIVO} ausente — quem cobra a "
            "existência dele é scripts/gerar-mapa.py)"
        )

    ensaios_por_lado, motivo_sem_caderno = caderno_de_ensaios(raiz)
    if ensaios_por_lado is None:
        desligadas.append(motivo_sem_caderno)
    else:
        resumo.ensaios_no_caderno = sum(len(lista) for lista in ensaios_por_lado.values())

    #: A regra 11 é AVISO, e regra mole se DESLIGA quando falta a coluna (a dura
    #: reprova — ver SUFIXOS_EXIGIDOS). Cobrar `mordida_provada_em` no cabeçalho
    #: derrubaria toda árvore que ainda não a tem por causa de um aviso.
    tem_coluna_da_mordida = "mordida_provada_em" in cabecalho
    if not tem_coluna_da_mordida:
        desligadas.append(
            "mordida-nao-provada (a coluna `mordida_provada_em` não está no "
            "cabeçalho deste CSV)"
        )

    vistos: dict[str, int] = {}
    nao_publicados: list[str] = []

    for numero, linha in registros:
        resumo.linhas += 1
        ident = (linha.get("id") or "").strip()

        if not ident:
            achados.append(
                Achado(FALHA, "integridade", numero, "", "", "`id` vazio")
            )
        elif ident in vistos:
            achados.append(
                Achado(
                    FALHA,
                    "integridade",
                    numero,
                    ident,
                    "",
                    f"`id` duplicado — já usado na linha {vistos[ident]}",
                )
            )
        else:
            vistos[ident] = numero

        if None in linha:
            achados.append(
                Achado(
                    FALHA,
                    "integridade",
                    numero,
                    ident,
                    "",
                    "a linha tem MAIS campos que o cabeçalho (vírgula solta fora "
                    "de aspas costuma ser a causa)",
                )
            )
        elif any(valor is None for valor in linha.values()):
            achados.append(
                Achado(
                    FALHA,
                    "integridade",
                    numero,
                    ident,
                    "",
                    "a linha tem MENOS campos que o cabeçalho",
                )
            )

        existe = (linha.get("existe") or "").strip()
        if existe not in DOMINIO_EXISTE:
            achados.append(
                Achado(
                    FALHA,
                    "integridade",
                    numero,
                    ident,
                    "",
                    f"`existe` fora do domínio: {existe!r}",
                )
            )

        mordidas = alvos_da_celula(linha.get("teste_que_morde") or "")
        if mordidas:
            resumo.linhas_com_mordida += 1
            resumo.alvos_de_teste += len(mordidas)
        if mordidas and indice_de_testes:
            for alvo in mordidas:
                motivo = motivo_de_o_pytest_nao_coletar(alvo, indice_de_testes, raiz)
                if motivo:
                    achados.append(
                        Achado(FALHA, "mordida-fantasma", numero, ident, "", motivo)
                    )

        # --- as duas células de transporte da linha -------------------------
        mudas_nesta_linha = 0
        graus_fortes_nesta_linha: list[str] = []
        for lado in LADOS:
            resumo.celulas += 1
            aciona = (linha[f"{lado}_aciona"] or "").strip()
            confianca = (linha[f"{lado}_confianca"] or "").strip()

            for sufixo, (coluna_cabo, coluna_radio) in pares.items():
                dominio = DOMINIO_POR_SUFIXO.get(sufixo)
                if dominio is None:
                    continue
                coluna = coluna_cabo if lado == LADOS[0] else coluna_radio
                valor = (linha[coluna] or "").strip()
                if valor not in dominio:
                    achados.append(
                        Achado(
                            FALHA,
                            "integridade",
                            numero,
                            ident,
                            lado,
                            f"`{coluna}` fora do domínio: {valor!r}",
                        )
                    )

            if not aciona:
                resumo.celulas_mudas += 1
                mudas_nesta_linha += 1
            if aciona in {"sim", "parcial"}:
                resumo.celulas_que_afirmam += 1
            if confianca == CONFIANCA_FORTE:
                resumo.celulas_medidas += 1

            if aciona == ACIONA_FORTE and confianca == CONFIANCA_FORTE:
                resumo.afirmacoes_fortes += 1
                if not mordidas:
                    resumo.afirmacoes_fortes_sem_rede += 1
                    achados.append(
                        Achado(
                            FALHA,
                            "sem-mordida",
                            numero,
                            ident,
                            lado,
                            f"afirma `{lado}_aciona = {ACIONA_FORTE}` com "
                            f"`{lado}_confianca = {CONFIANCA_FORTE}` e "
                            "`teste_que_morde` está vazio: se isso quebrar, a "
                            "suíte inteira continua verde",
                        )
                    )

            grau = (linha[f"{lado}_grau"] or "").strip()
            if grau in GRAUS_QUE_EXIGEM_ENSAIO:
                resumo.graus_fortes += 1
                graus_fortes_nesta_linha.append(grau)
                if ensaios_por_lado is not None:
                    achados.extend(
                        _regra_do_caderno(
                            grau,
                            ensaios_por_lado.get((ident, lado), []),
                            numero,
                            ident,
                            lado,
                            resumo,
                        )
                    )

        if mudas_nesta_linha == len(LADOS):
            resumo.linhas_mudas_dos_dois_lados += 1

        if graus_fortes_nesta_linha and tem_coluna_da_mordida:
            achados.extend(_regra_da_mordida_nao_provada(linha, numero, ident))

        achados.extend(_regra_da_validade(linha, numero, ident, hoje))
        achados.extend(_regra_da_assimetria(linha, numero, ident, resumo))

        if texto_do_specs is not None and ident and ident not in texto_do_specs:
            nao_publicados.append(ident)

    if nao_publicados:
        amostra = ", ".join(nao_publicados[:5])
        resto = "" if len(nao_publicados) <= 5 else f" (e mais {len(nao_publicados) - 5})"
        achados.append(
            Achado(
                FALHA,
                "mapa-nao-publicado",
                1,
                "",
                "",
                f"{len(nao_publicados)} linha(s) do CSV não estão em "
                f"{SPECS_RELATIVO}: {amostra}{resto} — rode "
                "`python3 scripts/gerar-mapa.py`",
            )
        )

    return achados, resumo, desligadas


def _regra_da_validade(
    linha: dict[str, str], numero: int, ident: str, hoje: date
) -> list[Achado]:
    """Regra 3 e regra 8. Silenciosa quando as duas colunas estão vazias."""
    provado = (linha.get("provado_em") or "").strip()
    validade = (linha.get("validade_dias") or "").strip()

    if not provado and not validade:
        return []
    if validade and not provado:
        return [
            Achado(
                AVISO,
                "validade-sem-data",
                numero,
                ident,
                "",
                f"`validade_dias = {validade}` sem `provado_em`: prazo que não "
                "se consegue contar",
            )
        ]
    if provado and not validade:
        # Data sem prazo é registro, não promessa. A política de validade é
        # decisão dela (seção 8 do índice da sprint) e este portão não a inventa.
        return []

    data = le_data(provado)
    if data is None:
        return [
            Achado(
                FALHA,
                "prova-vencida",
                numero,
                ident,
                "",
                f"`provado_em = {provado!r}` é ilegível "
                f"(formatos aceitos: {', '.join(_FORMATOS_DE_DATA)})",
            )
        ]
    try:
        dias = int(validade)
    except ValueError:
        return [
            Achado(
                FALHA,
                "prova-vencida",
                numero,
                ident,
                "",
                f"`validade_dias = {validade!r}` não é um número inteiro de dias",
            )
        ]
    if dias < 0:
        return [
            Achado(
                FALHA,
                "prova-vencida",
                numero,
                ident,
                "",
                f"`validade_dias = {dias}` é negativo",
            )
        ]

    vence = data + timedelta(days=dias)
    if vence < hoje:
        return [
            Achado(
                FALHA,
                "prova-vencida",
                numero,
                ident,
                "",
                f"a prova venceu em {vence.isoformat()} "
                f"(provada em {data.isoformat()}, validade de {dias} dia(s)): "
                "meça de novo ou mude o prazo",
            )
        ]
    return []


def _regra_da_assimetria(
    linha: dict[str, str], numero: int, ident: str, resumo: Resumo
) -> list[Achado]:
    """Regra 7 — o caso que ela descreveu: consolidado no cabo, morto no rádio."""
    cabo = (linha[f"{LADOS[0]}_aciona"] or "").strip()
    radio = (linha[f"{LADOS[1]}_aciona"] or "").strip()
    if cabo == radio:
        return []
    if (linha.get("assimetria_declarada") or "").strip():
        return []

    resumo.assimetrias_nao_declaradas += 1
    if not cabo or not radio:
        respondido, mudo = (LADOS[0], LADOS[1]) if cabo else (LADOS[1], LADOS[0])
        valor = cabo or radio
        texto = (
            f"o {ROTULO_DO_LADO[respondido]} diz `{valor}` e o "
            f"{ROTULO_DO_LADO[mudo]} não foi respondido: é "
            "exatamente a forma da regressão que este mapa existe para pegar"
        )
    else:
        texto = (
            f"o cabo diz `{cabo}` e o rádio diz `{radio}`, e "
            "`assimetria_declarada` está vazia"
        )
    nivel = FALHA if ASSIMETRIA_REPROVA else AVISO
    return [Achado(nivel, "assimetria-nao-declarada", numero, ident, "", texto)]


def veredicto_da_feature(ensaio: dict) -> str:
    """O que a FEATURE fez neste ensaio — a pergunta das regras 9 e 10.

    `resultado_da_feature` quando preenchida; `resultado` quando não. A ordem
    importa e é o coração da cura de 13/08/2026: `resultado` responde pelo
    SUSPEITO da linha, e há ensaio em que as duas respostas são OPOSTAS sem que
    nenhuma delas esteja errada — o `gatilho-lado-nao-esta-invertido` eliminou o
    suspeito (`não obedece`) na mesma rodada em que o R2 endureceu no aparelho.

    Quem julga o suspeito é `scripts/eliminacao.py`, e ele segue lendo
    `resultado`: esta função não é uma segunda régua para o mesmo dado, é a
    régua da OUTRA pergunta.
    """
    declarado = (ensaio.get(COLUNA_DO_VEREDICTO_DA_FEATURE) or "").strip()
    return declarado or (ensaio.get("resultado") or "").strip()


def _regra_do_veredicto_da_feature(
    ensaios: list[dict], numero: int, ident: str, lado: str
) -> list[Achado]:
    """Regra 12 — a guarda da coluna nova, e o que a impede de ser uma saída.

    Uma coluna que sobrepõe `resultado` é, sem guarda, o botão de desligar a
    regra 9: bastaria escrever `obedece` nela. As duas metades desta regra são o
    preço de apertar esse botão, e as duas são DURAS de propósito — a regra 9 é
    aviso porque o dado dela é ambíguo; esta é sobre o dado NOVO, que nasce com
    o significado definido, e aí ambiguidade é defeito.
    """
    achados: list[Achado] = []
    for ensaio in ensaios:
        declarado = (ensaio.get(COLUNA_DO_VEREDICTO_DA_FEATURE) or "").strip()
        if not declarado:
            continue
        id_do_ensaio = (ensaio.get("id") or "").strip() or "(ensaio sem id)"
        if declarado not in RESULTADOS_DO_CADERNO:
            achados.append(
                Achado(
                    FALHA,
                    "veredicto-da-feature-mal-declarado",
                    numero,
                    ident,
                    lado,
                    f"o ensaio `{id_do_ensaio}` tem "
                    f"`{COLUNA_DO_VEREDICTO_DA_FEATURE} = {declarado!r}`, que não "
                    f"está no vocabulário do caderno "
                    f"({', '.join(sorted(RESULTADOS_DO_CADERNO))}). A coluna "
                    "responde a MESMA pergunta que `resultado`, só que sobre a "
                    "feature: valor novo aqui é vocabulário novo, e vocabulário "
                    "novo se declara em RESULTADOS_DO_CADERNO no mesmo gesto",
                )
            )
            continue
        if declarado == (ensaio.get("resultado") or "").strip():
            continue
        if not (ensaio.get("nota") or "").strip():
            achados.append(
                Achado(
                    FALHA,
                    "veredicto-da-feature-mal-declarado",
                    numero,
                    ident,
                    lado,
                    f"o ensaio `{id_do_ensaio}` diz que a feature "
                    f"`{declarado}` enquanto o `resultado` diz "
                    f"`{(ensaio.get('resultado') or '').strip()}`, e a `nota` "
                    "está vazia. Divergir das duas colunas é dizer que o "
                    "`resultado` fala do SUSPEITO — e isso se escreve no "
                    "caderno, na mesma linha, ou não vale",
                )
            )
    return achados


def _regra_do_caderno(
    grau: str,
    ensaios: list[dict],
    numero: int,
    ident: str,
    lado: str,
    resumo: Resumo,
) -> list[Achado]:
    """Regras 6, 9, 10 e 12 — o grau forte contra o caderno de bancada.

    `ensaios` já chega casado por (`linha_id`, transporte): quem casou foi o
    `eliminacao.carrega_por_lado`, e o transporte importa tanto quanto o `id`.
    Ensaio de rádio não sustenta afirmação de cabo — a assimetria entre os dois
    é a regressão que este mapa inteiro existe para pegar, e aceitar um lado
    pelo outro seria justamente apagá-la.

    Quem responde "a feature obedeceu?" é `veredicto_da_feature`, não a coluna
    `resultado` crua: ver a seção "A coluna que a casa já tinha encomendado" no
    cabeçalho deste arquivo.
    """
    rotulo = ROTULO_DO_LADO[lado]
    if not ensaios:
        resumo.graus_fortes_sem_ensaio += 1
        return [
            Achado(
                FALHA,
                "grau-sem-ensaio",
                numero,
                ident,
                lado,
                f"declara `{lado}_grau = {grau}` e não há UM ensaio de {rotulo} "
                f"para `{ident}` em {ENSAIOS_RELATIVO}. Registre o ensaio que "
                "você fez (uma linha: `linha_id`, `transporte`, `suspeito`, "
                f"`presente`, `resultado`, `observado_por`) ou baixe o grau para "
                f"`{GRAU_MONTOU}`, que é o que a suíte sozinha sustenta",
            )
        ]

    guarda = _regra_do_veredicto_da_feature(ensaios, numero, ident, lado)

    if grau != GRAU_OBEDECEU:
        return guarda

    sustentam = [
        ensaio
        for ensaio in ensaios
        if veredicto_da_feature(ensaio) in RESULTADOS_QUE_SUSTENTAM
    ]
    if not sustentam:
        vistos = sorted({veredicto_da_feature(e) for e in ensaios})
        return [
            *guarda,
            Achado(
                FALHA if RESULTADO_REPROVA else AVISO,
                "grau-sem-ensaio-que-obedeca",
                numero,
                ident,
                lado,
                f"declara `{lado}_grau = {GRAU_OBEDECEU}` e os {len(ensaios)} "
                f"ensaio(s) de {rotulo} desta linha dizem {vistos}. Ou o degrau "
                f"está alto demais, ou o ensaio foi gravado com o `resultado` do "
                "SUSPEITO em vez do que a FEATURE fez — se for o segundo, "
                f"`{COLUNA_DO_VEREDICTO_DA_FEATURE}` é a coluna onde se diz o "
                "que a feature fez, e a `nota` do ensaio é onde se explica por "
                "que as duas divergem",
            )
        ]

    if not any(
        (e.get("observado_por") or "").strip() == OBSERVADOR_QUE_SUSTENTA for e in sustentam
    ):
        observadores = sorted({(e.get("observado_por") or "").strip() for e in sustentam})
        return [
            *guarda,
            Achado(
                FALHA if OLHO_DELA_REPROVA else AVISO,
                "grau-sem-olho-dela",
                numero,
                ident,
                lado,
                f"o ensaio que sustenta `{GRAU_OBEDECEU}` no {rotulo} foi "
                f"observado por {observadores}, e o METODO-DE-ISOLAMENTO diz que "
                f"só `{OBSERVADOR_QUE_SUSTENTA}` sustenta esse degrau: peça o "
                "olho dela, ou desça para `SAIU NO FIO`",
            )
        ]
    return guarda


def _regra_da_mordida_nao_provada(
    linha: dict[str, str], numero: int, ident: str
) -> list[Achado]:
    """Regra 11 — a coluna que existia e ninguém lia.

    Só cobra onde a promessa é máxima (grau forte) E há teste apontado: cobrar
    das 293 linhas seria enterrar o relatório em aviso, e a regra da casa é
    "teste tem de MORDER" — o lugar onde não ter arrancado a cura custa mais
    caro é justamente embaixo do degrau mais alto.
    """
    if not (linha.get("teste_que_morde") or "").strip():
        return []
    if (linha.get("mordida_provada_em") or "").strip():
        return []
    return [
        Achado(
            AVISO,
            "mordida-nao-provada",
            numero,
            ident,
            "",
            "tem grau forte e `teste_que_morde`, mas `mordida_provada_em` está "
            "vazia: ninguém registrou ter arrancado a cura e visto reprovar. "
            "Arranque, veja reprovar, devolva — e ponha a data aqui",
        )
    ]


def imprime_resumo(resumo: Resumo, desligadas: list[str]) -> None:
    """O quadro que ela lê para saber ONDE o mapa está cego."""
    print("")
    print("Resumo do censo (nenhum destes números é limiar — são o retrato de hoje):")
    linhas = [
        ("linhas do mapa", resumo.linhas),
        (
            "células de transporte ("
            + " + ".join(ROTULO_DO_LADO[lado] for lado in LADOS)
            + ")",
            resumo.celulas,
        ),
        ("células mudas (ninguém respondeu se aciona)", resumo.celulas_mudas),
        ("linhas mudas nos DOIS lados", resumo.linhas_mudas_dos_dois_lados),
        ("células que afirmam acionar (sim ou parcial)", resumo.celulas_que_afirmam),
        (f"células com confiança `{CONFIANCA_FORTE}`", resumo.celulas_medidas),
        (
            f"afirmações fortes (`{ACIONA_FORTE}` + `{CONFIANCA_FORTE}`)",
            resumo.afirmacoes_fortes,
        ),
        ("     dessas, SEM teste que morda", resumo.afirmacoes_fortes_sem_rede),
        ("linhas com teste que morde", resumo.linhas_com_mordida),
        ("alvos de pytest apontados pelo mapa", resumo.alvos_de_teste),
        ("assimetrias não declaradas", resumo.assimetrias_nao_declaradas),
        (
            f"graus fortes (`{GRAU_SAIU_NO_FIO}` ou `{GRAU_OBEDECEU}`)",
            resumo.graus_fortes,
        ),
        ("     desses, SEM ensaio no caderno", resumo.graus_fortes_sem_ensaio),
        ("ensaios lidos do caderno de bancada", resumo.ensaios_no_caderno),
    ]
    largura = max(len(rotulo) for rotulo, _ in linhas)
    for rotulo, valor in linhas:
        print(f"  {rotulo.ljust(largura, '.')} {valor}")
    for regra in desligadas:
        print(f"  regra DESLIGADA neste ambiente: {regra}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Censo do mapa de canais: reprova afirmação forte sem teste."
    )
    parser.add_argument(
        "--raiz",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="raiz do repositório (padrão: a deste script)",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help=f"o mapa a censurar (padrão: <raiz>/{CSV_RELATIVO})",
    )
    parser.add_argument(
        "--hoje",
        type=str,
        default=None,
        help="data de referência AAAA-MM-DD (só para teste do prazo de validade)",
    )
    args = parser.parse_args(argv)

    raiz = args.raiz.resolve()
    if not raiz.is_dir():
        print(f"ERRO: raiz inexistente: {raiz}")
        return 2

    caminho_csv = args.csv.resolve() if args.csv else raiz / CSV_RELATIVO
    if not caminho_csv.is_file():
        print(f"ERRO: mapa inexistente: {caminho_csv}")
        return 2

    hoje = date.today()
    if args.hoje:
        lida = le_data(args.hoje)
        if lida is None:
            print(f"ERRO: --hoje ilegível: {args.hoje!r}")
            return 2
        hoje = lida

    achados, resumo, desligadas = censo(caminho_csv, raiz, hoje)
    falhas = [achado for achado in achados if achado.nivel == FALHA]
    avisos = [achado for achado in achados if achado.nivel == AVISO]

    if avisos:
        print(f"{len(avisos)} aviso(s) — não derrubam este portão hoje:")
        for achado in avisos:
            print(str(achado))
        print("")

    if falhas:
        print(f"FALHA: {len(falhas)} reprovação(ões) em {caminho_csv.name}:")
        for achado in falhas:
            print(str(achado))
        imprime_resumo(resumo, desligadas)
        print("")
        print("Cada linha acima é uma afirmação do mapa sem rede que a sustente.")
        print("Preencha `teste_que_morde` com o id do nó do pytest que reprova")
        print("quando aquela feature quebrar NAQUELE transporte, ou baixe a")
        print("confiança da célula para o que ela de fato é. Vazio é pergunta")
        print("aberta e não reprova; `medido` sem teste, sim.")
        print("")
        print(f"E o grau é a MESMA conta na bancada: `{GRAU_SAIU_NO_FIO}` e")
        print(f"`{GRAU_OBEDECEU}` pedem ensaio do MESMO transporte em")
        print(f"{ENSAIOS_RELATIVO}. Sem ensaio, o degrau honesto é")
        print(f"`{GRAU_MONTOU}` — que já é o que a suíte prova sem aparelho.")
        return 1

    print(f"OK: nenhuma afirmação forte sem rede em {caminho_csv.name}.")
    imprime_resumo(resumo, desligadas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
