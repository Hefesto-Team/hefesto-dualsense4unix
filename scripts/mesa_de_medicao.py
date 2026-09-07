#!/usr/bin/env python3
"""A MESA DE MEDIÇÃO — a página onde ela mede os quatro DualSense.

O DEFEITO QUE ESTA PÁGINA EXISTE PARA MATAR NÃO É DE CÓDIGO: É DE MEMÓRIA.

A queixa dela, de 06/09/2026, está transcrita palavra por palavra em
`docs/process/agentes/2026-09-06/A-VALIDACAO-DOS-QUATRO-01-entrada/
ESPEC-A-VALIDACAO.md` — aqui ela é referida, não repetida, porque a frase
nomeia o assistente e nome de assistente não entra em arquivo versionado fora
de `docs/process/` (portão `anonimato`). Em uma linha: a sessão de quem estava na bancada
acabava, e com ela ia embora não só o resultado como **o modo de chegar nele**.

A medição acontecia, o resultado aparecia na conversa, a sessão morria, e no
dia seguinte ninguém sabia nem o que deu nem **como se chegou lá**. Por isso o
registro deste módulo grava, junto de cada resposta, o **COMO**: o comando, o
report, o offset, o canal e o `arquivo:linha` que o mapa já publica para aquela
célula, mais o gesto que quem estava na mesa digitou. Um registro que diz
"passou" sem dizer como não vale nada seis horas depois.

NADA SE DIGITA AQUI. Os testes SAEM DOS ARQUIVOS, e cada arquivo é o dono de
uma coisa:

    docs/data/mapa-controles.csv    as células que faltam medir, e o COMO de cada uma
    docs/process/sprints/…MESA-DE-QUATRO-01…  as 21 linhas do roteiro, que são a aceitação
    docs/data/pecas-do-dualsense.csv          o nome e o id de cada peça do desenho
    docs/data/cores-do-dualsense.csv          28 modelos × 10 zonas, a cor do plástico
    interface/ds_limpo.svg (via `monta`)      o desenho, e o realce por peça

Mudou o CSV, mudou a mesa. Uma lista de testes copiada à mão seria a segunda
verdade que esta casa derruba todo dia.

ZERO DEPENDÊNCIA NOVA. Só biblioteca padrão, e a doutrina é do
`scripts/gerar-indice-html.py`: *"um instrumento que só funciona com rede não
serve para depurar rádio."* A dívida do `playwright`, que não está no
`pyproject.toml` e deixa toda árvore nova com dois portões vermelhos, já ensinou
o preço de acrescentar uma.

A PÁGINA NÃO ACIONA O APARELHO (decisão dela: *"ok mas é essa a ideia mesmo"*).
Ela diz o que fazer, conta o tempo, mostra os quatro desenhos e GRAVA. Quem faz
é ela, no produto.

Uso:
    scripts/mesa_de_medicao.py --servir            sobe o servidor e imprime o endereço
    scripts/mesa_de_medicao.py --porta 8765        escolhe a porta
    scripts/mesa_de_medicao.py --censo             o retrato dos testes, rc=0, sem servir
    scripts/mesa_de_medicao.py --pagina /tmp/x.html  escreve a página e sai (para a régua)

Quem sobe isto de verdade é o `validar.sh` da raiz.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import html
import io
import json
import os
import pathlib
import re
import socket
import sys
import threading
import unicodedata
from dataclasses import asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from collections.abc import Sequence
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[1]

# O `monta` mora dentro do pacote e é importado POR CAMINHO, como as dez abas
# fazem (`aba01.py:60-62`). Ele puxa `onde` como módulo solto do mesmo
# diretório, então acrescentar a pasta ao `sys.path` é o contrato dele, não um
# atalho meu.
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "scripts"))
import monta

# A PALETA É DO IRMÃO NESTA PASTA, e é o mesmo módulo de que o `specs.html`, o
# `painel.html`, o `frases-de-tela.html` e o `index.html` leem. A mesa nasceu
# com nove hex próprios, claros, e ela apontou: *"mantém o mesmo tema que vemos
# aplicando"*.
import paleta_da_casa

MAPA = RAIZ / "docs/data/mapa-controles.csv"
PECAS = RAIZ / "docs/data/pecas-do-dualsense.csv"
CORES = RAIZ / "docs/data/cores-do-dualsense.csv"
ROTEIRO = RAIZ / "docs/process/sprints"

#: O nome do arquivo do roteiro é um PADRÃO, não um caminho cravado: o índice de
#: sprints renomeia arquivo, e um caminho literal morreria calado no dia da
#: renomeação — deixando a mesa com as células do mapa e sem a aceitação.
ROTEIRO_PADRAO = "2026-09-06-MESA-DE-QUATRO-01-*.md"

#: Só DualSense nesta volta (§8 da especificação). O Nintendo Pro e o 8BitDo são
#: outra frente, e a palavra é dela: *"Quatro controles é o foco. Nenhum externo
#: entra nesta mesa."*
CONTROLE = "dualsense"

#: Os quatro postos. É o vocabulário da tela — `P1`…`P4` — e ele casa com o
#: `player_slot` que o daemon publica.
POSTOS = ("P1", "P2", "P3", "P4")

#: O grau FORTE da escada, e o dono da definição é o `LEIA-PRIMEIRO.md` §3:
#: *"Grau forte é `SAIU NO FIO` ou `O APARELHO OBEDECEU`"*. Tudo abaixo disso é
#: grau fraco, e grau fraco é o que esta mesa existe para subir.
GRAU_FORTE = ("SAIU NO FIO", "O APARELHO OBEDECEU")

#: A marca com que o mapa diz "ninguém mediu esta célula". Ela mora nas colunas
#: `cabo_por_que_nao_aciona` / `radio_por_que_nao_aciona`.
NAO_MEDIDO = "nao-medido"

#: O tempo padrão do TIMER, em segundos. Ele não é enfeite: é o que ela pediu —
#: *"mostra um timer pra antes de aplicar tal coisa"* —, e serve para ela tirar
#: os olhos da tela e pôr nos controles ANTES de qualquer coisa acontecer. Sem
#: ele a coisa acontece enquanto ela ainda lê, e a medição se perde.
SEGUNDOS_PADRAO = 5

#: O teto do que a página conta sozinha. Acima disto ela mostra o alvo e um
#: botão de "já passou": ninguém fica olhando uma barra por vinte minutos, e a
#: linha 10 do roteiro ("volta neles aos 20 min") pede exatamente isso.
SEGUNDOS_LONGO = 120

#: As quatro respostas por controle. A quarta é a que salva medição — *o
#: inesperado é o achado* —, e por isso ela abre o campo de texto.
RESPOSTAS = (
    ("obedeceu", "Obedeceu"),
    ("nada", "Nada aconteceu"),
    ("nao-vi", "Não consegui ver"),
    ("outra-coisa", "Aconteceu outra coisa"),
)

#: AS FAMÍLIAS QUE SÓ SE MEDEM DE UM EM UM, e a razão é ela: *"se algum canto
#: for sobre condições tipo vibração, ouvir, falar e afins. coisas que eu
#: precisa fazer todos separados um por vez (…) afinal podemos ter 4 controles
#: mas só tenho um par de mãos"*.
#:
#: Vibração se sente com a MÃO, som se ouve com a ORELHA, microfone se testa
#: FALANDO. Nos três, medir quatro ao mesmo tempo não é difícil — é impossível:
#: com dois tremendo juntos ninguém sabe qual tremeu. Luz e bateria não entram
#: aqui porque se leem com os OLHOS, e os olhos pegam os quatro de uma vez.
_FAMILIAS_UM_POR_VEZ = ("vibracao", "audio")

#: E as palavras que dizem a mesma coisa no roteiro, que não tem família.
_DIZ_UM_POR_VEZ = ("um de cada vez", "um por vez", "um a um", "uma por vez")


def e_um_por_vez(familia: str, texto: str) -> bool:
    """Este teste se faz num controle de cada vez?

    DUAS FONTES, nenhuma digitada por teste: a FAMÍLIA da célula do mapa
    (vibração e áudio, que se medem com a mão e a orelha) e as PALAVRAS do
    roteiro (*"um de cada vez"*, *"um a um"*), que ela mesma escreveu na
    tabela. Uma terceira fonte seria uma lista de 199 linhas a manter à mão.
    """
    if familia in _FAMILIAS_UM_POR_VEZ:
        return True
    return any(x in _dobra(texto) for x in _DIZ_UM_POR_VEZ)


#: Os papéis do desenho, e eles TÊM de ser distintos: um teste em que os quatro
#: brilham igual não diz nada.
PAPEL_REAGE = "reage"
PAPEL_CALADO = "calado"
PAPEL_OBSERVA = "observa"

#: Os três vereditos do VERIFICAR — por CONTROLE, não por teste.
BATE = "bate"
NAO_BATE = "nao-bate"
SEM_JULGAR = "sem-julgar"


def confere(papel: str, resposta: str) -> tuple[str, str]:
    """O que o VERIFICAR diz sobre UM controle: bate · não bate · sem julgar.

    PEDIDO DELA, 06/09/2026: *"após responder e clicar em verificar ele mostra
    se deu certo ou errado pra cada controle"*.

    ISTO NÃO É O :func:`veredito`, E A DIFERENÇA É O PONTO INTEIRO. Aquele
    resume o TESTE para o índice e **não olha papel de propósito** — a docstring
    de lá explica por quê: transformar em "falhou" um `obedeceu` de quem devia
    ficar calado esconderia justamente o achado. Esta função faz o oposto e pela
    mesma razão: ela olha o papel para **mostrar** a divergência na cara dela,
    com o nome do que aconteceu. O achado deixa de ser escondido em qualquer um
    dos dois lados — um o preserva no resumo, o outro o anuncia na hora.

    QUEM NÃO JULGA: `observa` não tem expectativa (o roteiro não disse o que
    esperar daquele controle), e `nao-vi` não é resposta sobre o aparelho — é
    resposta sobre a medição. Julgar qualquer um dos dois seria inventar um
    veredito que ninguém mediu.

    `outra-coisa` NUNCA bate, em papel nenhum: o inesperado é o achado, e um
    achado carimbado de "certo" é um achado perdido.
    """
    if resposta in ("", "nao-vi"):
        return SEM_JULGAR, ("sem resposta" if not resposta
                            else "não deu para ver — a medição não aconteceu")
    # O `outra-coisa` VEM ANTES DO `observa`, e a ordem é a regra: sem
    # expectativa declarada continua havendo o inesperado, e ele é achado
    # igual. Com o `observa` na frente, um controle "só de observar" que fez
    # algo estranho saía carimbado de "sem julgar" — o silêncio que esta mesa
    # existe para não produzir.
    if resposta == "outra-coisa":
        return NAO_BATE, "aconteceu outra coisa — escreva o quê, isto é achado"
    if papel == PAPEL_OBSERVA:
        return SEM_JULGAR, "o roteiro não diz o que esperar deste"
    if papel == PAPEL_REAGE:
        return ((BATE, "reagiu, como o roteiro esperava")
                if resposta == "obedeceu"
                else (NAO_BATE, "devia reagir e não reagiu"))
    return ((BATE, "ficou calado, como o roteiro esperava")
            if resposta == "nada"
            else (NAO_BATE, "reagiu, e este não podia reagir"))


#: A MESMA REGRA, servida ao navegador como DADO. O JS não a reimplementa: uma
#: segunda cópia da tabela em JavaScript divergiria no dia em que uma das duas
#: fosse corrigida, e é exatamente o defeito que esta casa caça. A função que
#: monta o HTML
#: publica isto em `window.__CONFERE__`, e o JS só consulta.
def tabela_de_conferencia() -> dict[str, dict[str, list[str]]]:
    """`{papel: {resposta: [veredito, frase]}}`, gerada por :func:`confere`."""
    return {
        papel: {resp: list(confere(papel, resp))
                for resp, _ in (*RESPOSTAS, ("", ""))}
        for papel in (PAPEL_REAGE, PAPEL_CALADO, PAPEL_OBSERVA)
    }


# ---------------------------------------------------------------------------
# Ler os donos
# ---------------------------------------------------------------------------
def _dobra(texto: str) -> str:
    """Minúsculas, sem acento. A busca por texto desta casa é sem acento — o
    `LEIA-PRIMEIRO.md` §6 já avisa que `grep 'rádio'` não acha uma linha do
    caderno."""
    return "".join(
        c for c in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(c) != "Mn"
    )


def _fichas(texto: str) -> set[str]:
    """As palavras de um texto, dobradas, sem o plural e sem as curtas.

    O `-s` final cai porque a tela escreve *"Gatilhos"* e a peça se chama
    *"gatilho adaptativo esquerdo"*: sem isto a linha 7 do roteiro não acharia
    peça nenhuma. Três letras é o piso porque `luz` é palavra dela.
    """
    return {
        t[:-1] if len(t) > 3 and t.endswith("s") else t
        for t in re.split(r"[^a-z0-9]+", _dobra(texto))
        if len(t) >= 3
    }


def _sem_comentario(caminho: pathlib.Path) -> list[str]:
    """As linhas de um CSV desta casa, sem o cabeçalho em prosa.

    O `pecas-do-dualsense.csv` e o `cores-do-dualsense.csv` abrem com dezenas de
    linhas `#` que explicam a decisão que os criou — e o `csv.DictReader` cru
    leria a primeira delas como cabeçalho.
    """
    return [
        linha for linha in caminho.read_text(encoding="utf-8").splitlines()
        if linha.strip() and not linha.lstrip().startswith("#")
    ]


def pecas() -> list[dict[str, str]]:
    """As 28 peças, do arquivo que é dono delas."""
    return list(csv.DictReader(io.StringIO("\n".join(_sem_comentario(PECAS)))))


def nomes_dos_colorways() -> dict[str, str]:
    """`{slug: nome DE FÁBRICA}` — `cosmic-red` -> `Cosmic Red`.

    IRMÃ DE `colorway_por_nome`, E NÃO A MESMA: aquela indexa pelo nome
    DOBRADO (minúsculas, sem acento), porque a busca desta casa é sem acento e
    o que ela recebe é o `modelo` que o daemon publica. Esta preserva a
    capitalização de fábrica, porque o que ela alimenta é a TELA — e um cartão
    dizendo *"cosmic red"* em vez de *"Cosmic Red"* é a página inventando uma
    grafia que a Sony não usa. As duas leem o MESMO CSV, na mesma passada.
    """
    fora: dict[str, str] = {}
    for linha in csv.DictReader(io.StringIO("\n".join(_sem_comentario(CORES)))):
        nome, slug = (linha.get("nome") or "").strip(), (linha.get("id") or "").strip()
        if nome and slug:
            fora.setdefault(slug, nome)
    return fora


def nome_do_colorway(slug: str) -> str:
    """O nome de fábrica de UM slug, ou o próprio slug se ele não estiver lá."""
    return nomes_dos_colorways().get(slug, slug) if slug else ""


def colorway_por_nome() -> dict[str, str]:
    """`{nome de fábrica dobrado: slug do desenho}`.

    O daemon publica `modelo` como NOME (*Cosmic Red*); o desenho escolhe por
    `data-colorway` (*cosmic-red*). A junta é a mesma que `mesa_viva.
    _codigo_para_colorway` faz pelo CÓDIGO — aqui é pelo nome, porque é o nome
    que o `state_full` traz, e as duas leem o MESMO CSV. Digitar a tabela aqui
    seria a segunda verdade.
    """
    fora: dict[str, str] = {}
    for linha in csv.DictReader(io.StringIO("\n".join(_sem_comentario(CORES)))):
        nome, slug = (linha.get("nome") or "").strip(), (linha.get("id") or "").strip()
        if nome and slug:
            fora.setdefault(_dobra(nome), slug)
    return fora


def linhas_do_mapa() -> list[dict[str, str]]:
    """As linhas do mapa de canais, só as do DualSense."""
    with open(MAPA, encoding="utf-8") as arq:
        return [r for r in csv.DictReader(arq) if r["controle"] == CONTROLE]


def arquivo_do_roteiro() -> pathlib.Path:
    """O arquivo da sprint MESA-DE-QUATRO-01, achado pelo padrão."""
    achados = sorted(ROTEIRO.glob(ROTEIRO_PADRAO))
    if not achados:
        raise SystemExit(
            f"ERRO: nenhuma sprint casa {ROTEIRO_PADRAO} em {ROTEIRO} — as 21 "
            f"linhas da aceitação são metade desta mesa, e sem elas ela mente "
            f"por omissão.")
    return achados[0]


def linhas_do_roteiro() -> list[tuple[str, str, str, str, str]]:
    """As 21 linhas da §2 da sprint, lidas da tabela markdown.

    CINCO CAMPOS DESDE 07/09/2026: entrou a coluna *"o que cada controle faz"*,
    a encomenda dela — cada controle é uma CONDIÇÃO do experimento, não o mesmo
    gesto repetido quatro vezes. A leitura aceita as duas larguras.

    A SEÇÃO É ACHADA PELO TÍTULO, não pelo número de linha. Um documento desta
    casa é reescrito toda semana, e um `sed -n '60,80p'` cravado envelheceria em
    silêncio — que é a família de defeito que o `citacoes-de-linha` existe para
    pegar.
    """
    texto = arquivo_do_roteiro().read_text(encoding="utf-8")
    marca = "## 2. O ROTEIRO"
    if marca not in texto:
        raise SystemExit(
            f"ERRO: `{marca}` sumiu de {arquivo_do_roteiro().name} — o roteiro "
            f"mudou de forma e esta régua leria a tabela errada.")
    corpo = texto.split(marca, 1)[1].split("\n## ", 1)[0]
    fora = []
    for linha in corpo.splitlines():
        if not linha.startswith("|"):
            continue
        celulas = [c.strip() for c in linha.strip().strip("|").split("|")]
        if not celulas or not celulas[0].isdigit():
            continue
        if len(celulas) == 5:
            fora.append((celulas[0], celulas[1], celulas[2],
                         celulas[3], celulas[4]))
        elif len(celulas) == 4:
            # A TABELA DE QUATRO COLUNAS, a de antes de 07/09/2026: continua
            # valendo, e a condição fica vazia. Uma régua que exigisse cinco
            # derrubaria a mesa inteira no dia em que alguém editasse a tabela
            # sem saber da coluna nova.
            fora.append((celulas[0], celulas[1], "", celulas[2], celulas[3]))
    if not fora:
        raise SystemExit(
            "ERRO: a §2 do roteiro não devolveu uma linha — régua que não acha "
            "nada dá verde sobre o vazio.")
    return fora


# ---------------------------------------------------------------------------
# De que peça um teste fala
# ---------------------------------------------------------------------------
def vocabulario_das_pecas() -> dict[str, set[str]]:
    """`{palavra: {ids de peça}}`, do CSV que é dono dos nomes.

    POR QUE ISTO NÃO É UMA LISTA ESCRITA À MÃO, que é o que a regra da casa
    proíbe: as palavras saem de `nome` e `apelidos` do `pecas-do-dualsense.csv`.
    *"Vibração"* acha os dois motores porque eles se chamam *Motor de vibração
    esquerdo/direito*; *"Gatilhos"* acha L2 e R2 porque o apelido deles é
    *gatilho adaptativo*. Mudou o nome da peça, muda o que a mesa acende.

    Medido em 06/09/2026: as 46 palavras que saem daqui identificam, cada uma,
    no MÁXIMO quatro peças — e as de quatro são justamente o D-pad, que é uma
    peça em quatro direções. Não há palavra genérica a filtrar.
    """
    fora: dict[str, set[str]] = {}
    for p in pecas():
        fonte = p["nome"] + " " + p["apelidos"].replace("|", " ").replace("-", " ")
        for ficha in _fichas(fonte):
            fora.setdefault(ficha, set()).add(p["id"])
    return fora


def pecas_citadas(texto: str, vocab: dict[str, set[str]]) -> list[tuple[str, str]]:
    """`[(id da peça, a palavra que a achou)]` — e a palavra vai junto de
    propósito.

    Quem olha a tela e discorda do que acendeu tem de poder ver **por qual
    palavra** a mesa decidiu. Um realce sem procedência é um realce que ninguém
    pode contestar, e esta casa já pagou caro por instrumento que não declara
    como decidiu.
    """
    achados: dict[str, str] = {}
    for ficha in sorted(_fichas(texto) & set(vocab)):
        for pid in sorted(vocab[ficha]):
            achados.setdefault(pid, ficha)
    return sorted(achados.items())


def postos_citados(texto: str) -> list[str]:
    """Os `P1`…`P4` que a frase nomeia. Vazio quer dizer *todos observam*."""
    return sorted({f"P{n}" for n in re.findall(r"\bP([1-4])\b", texto)})


def segundos_do_texto(texto: str) -> int:
    """O tempo que a linha nomeia, em segundos. Sem número, o padrão.

    O timer *conta durante* o que dura: um teste de vibração de 2 s mostra os
    2 s correndo, e a linha 10 do roteiro (*"volta neles aos 20 min"*) mostra os
    vinte minutos.
    """
    m = re.search(r"(\d+)\s*(min|minuto|s\b|seg|segundo)", _dobra(texto))
    if not m:
        return SEGUNDOS_PADRAO
    n = int(m.group(1))
    return n * 60 if m.group(2).startswith("min") else n


# ---------------------------------------------------------------------------
# O teste
# ---------------------------------------------------------------------------
@dataclass
class Teste:
    """Um teste da mesa. Tudo nele veio de um arquivo com dono."""

    id: str
    secao: str
    titulo: str
    vai_acontecer: str
    passa_quando: str
    #: `{P1: papel}` — quem DEVE reagir, quem NÃO PODE reagir, quem observa.
    papeis: dict[str, str]
    #: `[(id da peça, palavra que a achou)]`
    pecas: list[tuple[str, str]]
    celula: str
    hoje: str
    #: O COMO que o arquivo já publica: comando, report, offset, canal, código.
    como: list[tuple[str, str]]
    segundos: int
    fonte: str
    #: VAZIO quando ninguém mediu. Quando o mapa JÁ registra grau forte, traz o
    #: grau e a procedência — e a página pré-marca a resposta com isso.
    #: Nasceu de uma frase dela, 07/09/2026: *"a ideia é ficar fácil pra
    #: validarmos as teses, a grande maioria ali já foi validada uns 80%"*. A
    #: mesa só listava o que FALTAVA, então ela não tinha como confirmar de
    #: relance o que já estava de pé.
    ja_medido: str = ""
    #: `{P1: "liga PRIMEIRO, pelo cabo"}` — o que CADA controle faz neste
    #: teste. Vem da coluna *"o que cada controle faz"* da §2 do roteiro, e é a
    #: encomenda dela: cada controle é uma CONDIÇÃO do mesmo experimento.
    #: Vazio nas células do mapa, onde ela escreve na hora.
    condicoes: dict[str, str] = field(default_factory=dict)
    #: TRUE quando o teste se faz num controle de cada vez — vibração, som,
    #: microfone. A página então anda P1 → P2 → P3 → P4, com timer entre cada
    #: um, e ela só passa ao seguinte depois de responder o anterior.
    um_por_vez: bool = False
    #: A resposta que o mapa implica, para vir pré-marcada: `obedeceu` quando a
    #: célula diz que aciona, `nada` quando diz que não. Só existe com selo.
    resposta_do_mapa: str = ""

    def para_json(self) -> dict[str, Any]:
        return asdict(self)


def _como_da_celula(r: dict[str, str], lado: str) -> list[tuple[str, str]]:
    """O gesto que o MAPA já publica para aquela célula.

    É a metade do "como" que não depende de ninguém lembrar: o comando, o
    report, o offset, o canal e o `arquivo:linha` estão no CSV desde que a
    célula nasceu. A outra metade — o que a pessoa de fato fez — ela digita na
    hora, e as duas são gravadas lado a lado.
    """
    pares = [
        ("canal", r[f"{lado}_canal"]),
        ("report", r[f"{lado}_report_id"]),
        ("offset", r[f"{lado}_offset"]),
        ("comando", r[f"{lado}_comando"]),
        ("código", r[f"{lado}_codigo_ref"]),
        ("teste que morde", r["teste_que_morde"]),
    ]
    return [(k, v.strip()) for k, v in pares if v and v.strip()]


#: O QUE UMA CONDIÇÃO DIZ SOBRE O PAPEL. As duas listas são de VERBOS da
#: coluna que ela escreveu, e A ORDEM É A REGRA: o CALADO vem primeiro porque
#: as frases passivas contêm os verbos de ação. Dois casos medidos em
#: 07/09/2026, na primeira volta desta função:
#:
#:   "não pode mudar de cor"  contém `muda`   -> viraria REAGE
#:   "fica ligado, no cabo"   contém `liga`   -> viraria REAGE
#:
#: Nos dois o controle está parado e é justamente o que se observa. Por isso
#: `fica ` e `continua` entram na lista de baixo, e ela é consultada antes.
# noqa-acento: as chaves abaixo são DOBRADAS (minúsculas, sem acento), que
# é a forma com que `_dobra` compara — escrevê-las com acento as quebraria.
_CALADO_DIZ = ("ninguem toca", "nao pode", "fica fora", "fica ligado",  # noqa-acento: chaves DOBRADAS, sem acento de propósito
               "fica no", "continua", "nao e este", "e a testemunha",  # noqa-acento: chave DOBRADA, sem acento de propósito
               "de comparacao")
_REAGE_DIZ = ("e este", "liga", "poe ", "muda", "troca", "aperta", "anota",
              "desliga", "religa", "recebe", "entra", "deve", "tem de",
              "so o", "sai e volta", "pareia")


def papel_da_condicao(frase: str, posto: str, nomeados: set[str] | list[str]) -> str:
    """O papel de um controle, lido da CONDIÇÃO que ela escreveu para ele.

    É mais preciso que contar citações de posto no enunciado, que era a régua
    até 07/09/2026: a condição diz, na própria frase, se aquele controle é o
    que age (*"é ESTE que desliga"*, *"põe VERMELHO"*) ou o que fica parado
    (*"ninguém toca"*, *"não pode tremer"*). Sem a coluna, cai na regra velha.
    """
    dobrada = _dobra(frase)
    if not dobrada:
        return ((PAPEL_REAGE if posto in nomeados else PAPEL_CALADO)
                if nomeados else PAPEL_OBSERVA)
    # A EXPECTATIVA EXPLÍCITA GANHA DE TUDO. *"tem de continuar"* contém
    # `continua`, que é palavra de controle parado — mas a frase declara o que
    # se ESPERA daquele controle, e é isso que ela vai conferir. Sem esta
    # linha, as duas linhas de "os quatro têm de continuar" (fechar o jogo,
    # abrir pelo lançador) saíam com os quatro marcados "não pode reagir", que
    # é o contrário do que o roteiro pede.
    if "tem de" in dobrada or dobrada.startswith("deve"):
        return PAPEL_REAGE
    if any(x in dobrada for x in _CALADO_DIZ):
        return PAPEL_CALADO
    if any(x in dobrada for x in _REAGE_DIZ):
        return PAPEL_REAGE
    return PAPEL_OBSERVA


def secoes_do_roteiro() -> dict[str, str]:
    """`{"6": "Uma feature por controle"}` — a seção de cada linha das 21.

    AS 21 NÃO SÃO UMA FILA PLANA, e ela viu isso antes de mim: abriu o seletor
    de seções e perguntou *"cadê as seções das 21?"*. A especificação da mesa
    já as trazia desde 06/09/2026 (§4, seis seções) e a página as ignorava —
    jogava as 21 numa gaveta só chamada "O roteiro". Com seis, ela fecha uma e
    passa à seguinte, que é como a hora dela anda de verdade.

    A TABELA MORA NO ROTEIRO, não aqui: `### As seis seções das 21`, na §2 da
    sprint. Uma cópia neste arquivo seria a segunda verdade sobre o mesmo
    agrupamento, e no dia em que ela mexesse numa a outra mentiria.
    """
    texto = arquivo_do_roteiro().read_text(encoding="utf-8")
    marca = "### As seis seções das 21"
    if marca not in texto:
        return {}
    corpo = texto.split(marca, 1)[1].split("\n#", 1)[0]
    fora: dict[str, str] = {}
    for linha in corpo.splitlines():
        if not linha.startswith("| ") or linha.startswith("| ---"):
            continue
        celulas = [c.strip() for c in linha.strip().strip("|").split("|")]
        if len(celulas) != 2 or celulas[0] == "seção":
            continue
        for numero in re.findall(r"\d+", celulas[1]):
            fora[numero] = celulas[0]
    return fora


def testes_do_roteiro(vocab: dict[str, set[str]]) -> list[Teste]:
    """As 21 linhas da aceitação, uma por teste.

    **As linhas 13-21 são a ACEITAÇÃO DO PRODUTO** — a definição de pronto dela,
    dita em gestos. Elas vêm primeiro na página por isso.
    """
    fora = []
    fonte = f"{arquivo_do_roteiro().relative_to(RAIZ)} §2"
    secoes = secoes_do_roteiro()
    for numero, gesto, cond, passa, sprints in linhas_do_roteiro():
        limpo = re.sub(r"[*`]", " ", f"{gesto} {cond} {passa}")
        nomeados = postos_citados(limpo)
        # AS QUATRO CONDIÇÕES, uma por controle. A coluna as traz numa frase
        # só, separadas por `·` e prefixadas pelo posto — o formato é o que ela
        # escreveu à mão na tabela, e a régua o lê em vez de exigir uma coluna
        # por controle (que multiplicaria a tabela por quatro).
        condicoes = {}
        for pedaco in re.split(r"\s+·\s+", re.sub(r"[*`]", "", cond)):
            achado = re.match(r"\s*(P[1-4])\s*:\s*(.+)", pedaco)
            if achado:
                condicoes[achado.group(1)] = achado.group(2).strip()
        # O PAPEL SAI DA CONDIÇÃO quando ela existe, e é MUITO mais preciso
        # que contar citações de posto: a condição diz, na frase, se aquele
        # controle é o que age ("é ESTE que...", "põe VERMELHO") ou o que fica
        # parado ("ninguém toca", "não pode tremer"). Sem a coluna, cai na
        # regra velha — quem é citado reage, o resto fica calado.
        papeis = {p: papel_da_condicao(condicoes.get(p, ""), p, nomeados)
                  for p in POSTOS}
        fora.append(Teste(
            id=f"roteiro-{int(numero):02d}",
            # A SEÇÃO SAI DA TABELA DAS SEIS. Sem ela, cai no rótulo
            # antigo — uma gaveta só para as 21, que é o que ela apanhou.
            secao=(f"O roteiro · {secoes[numero]}" if numero in secoes
                   else "O roteiro — a aceitação do produto"),
            titulo=re.sub(r"[*`]", "", gesto),
            vai_acontecer=re.sub(r"[*`]", "", gesto),
            passa_quando=re.sub(r"[*`]", "", passa),
            papeis=papeis,
            pecas=pecas_citadas(limpo, vocab),
            celula=f"linha {numero} do roteiro",
            hoje=f"quem já descreveu isto: {re.sub(r'[*`]', '', sprints)}",
            como=[("linha do roteiro", numero), ("passa quando", re.sub(r"[*`]", "", passa))],
            segundos=min(segundos_do_texto(limpo), SEGUNDOS_LONGO * 20),
            fonte=fonte,
            condicoes=condicoes,
            um_por_vez=e_um_por_vez("", limpo),
        ))
    return fora


def testes_do_mapa(vocab: dict[str, set[str]]) -> list[Teste]:
    """As células que o `specs.html` ainda não sabe, uma por (linha, lado).

    A REGRA DE ENTRADA, e cada metade dela tem dono escrito:

    * a célula está marcada `nao-medido` na coluna do porquê — o mapa declarando
      que ninguém mediu —, **ou**
    * o **grau é fraco** (`ate_onde_foi` fora de `SAIU NO FIO` / `O APARELHO
      OBEDECEU`, que é como o `LEIA-PRIMEIRO.md` §3 define grau forte) **e** o
      produto AFIRMA alguma coisa ali (`aciona` em `sim`/`parcial`). Sem a
      segunda metade a mesa gastaria a hora dela com célula que o produto nem
      tenta.

    E o que `existe = nao-tem` sai fora: não há o que olhar num aparelho que não
    tem a peça, e pôr isso na fila dela seria fazê-la conferir uma ausência.
    """
    fora = []
    for r in linhas_do_mapa():
        if r["existe"] == "nao-tem":
            continue
        for lado, palavra in (("cabo", "cabo"), ("radio", "rádio")):
            nao_medido = r[f"{lado}_por_que_nao_aciona"] == NAO_MEDIDO
            fraco = r[f"{lado}_ate_onde_foi"] not in GRAU_FORTE
            afirma = r[f"{lado}_aciona"] in ("sim", "parcial")
            falta = nao_medido or (fraco and afirma)
            # AS DUAS FAMÍLIAS, e a segunda é nova em 07/09/2026. Antes só
            # entrava o que FALTAVA — e ela mediu o efeito disso: *"a ideia é
            # ficar fácil pra validarmos as teses, a grande maioria ali já foi
            # validada uns 80%"*. Uma bancada que esconde o que já está de pé
            # não deixa ela CONFIRMAR nada; deixa só descobrir.
            #
            # O SELO SAI DE `de_onde_sei`, NÃO DO DEGRAU, e a diferença é
            # medida: `ate_onde_foi` está VAZIO em 115 das 195 células desta
            # árvore, inclusive em muitas que dizem `medido` — o degrau é
            # coluna nova e quase ninguém a preencheu. `de_onde_sei = medido`
            # marca CEM células, e é o que responde à frase dela. Usar o degrau
            # daria 39, e a bancada continuaria escondendo o que ela já sabe.
            de_onde = r[f"{lado}_de_onde_sei"] or ""
            ja = "" if falta or de_onde != "medido" else (
                f'medido · {r[f"{lado}_ate_onde_foi"] or "sem degrau declarado"}')
            if not falta and not ja:
                # nem falta, nem alguém mediu: não há tese a confirmar aqui
                continue
            texto = f'{r["rotulo"]} {r["chave"]}'
            das_colunas = [(p, "coluna `peca` do mapa") for p in r["peca"].split()]
            achadas = das_colunas or pecas_citadas(texto, vocab)
            fora.append(Teste(
                id=f'mapa-{r["chave"]}-{lado}',
                secao=f'O mapa de canais — {r["familia"]}',
                titulo=f'{r["rotulo"]} · {palavra}',
                vai_acontecer=(
                    f'Exercite **{r["rotulo"]}** por {palavra} e diga o que cada '
                    f'controle fez. O produto {"afirma" if r[f"{lado}_aciona"] == "sim" else "afirma em parte"} '
                    f'que aciona isto.'),
                passa_quando=(
                    r[f"{lado}_ressalva"].strip()
                    or r[f"{lado}_detalhe"].strip()
                    or r["estado_hoje"].strip()
                    or "o aparelho faz o que a célula afirma"),
                papeis={p: PAPEL_OBSERVA for p in POSTOS},
                pecas=achadas,
                celula=f'{r["chave"]} @ {palavra}',
                hoje=(
                    f'aciona={r[f"{lado}_aciona"] or "-"} · '
                    f'de_onde_sei={r[f"{lado}_de_onde_sei"] or "-"} · '
                    f'ate_onde_foi={r[f"{lado}_ate_onde_foi"] or "(vazio)"}'
                    + (f' · {NAO_MEDIDO}' if nao_medido else "")),
                como=_como_da_celula(r, lado),
                segundos=SEGUNDOS_PADRAO,
                fonte=f'docs/data/mapa-controles.csv · {r["id"]} [{lado}]',
                ja_medido=ja,
                um_por_vez=e_um_por_vez(r["familia"], texto),
                # A RESPOSTA QUE O MAPA IMPLICA. `parcial` fica sem
                # pré-marca de propósito: metade é a que interessa, e escolher
                # uma das duas por ela seria a página respondendo no lugar dela.
                resposta_do_mapa=(
                    "obedeceu" if ja and r[f"{lado}_aciona"] == "sim"
                    else "nada" if ja and r[f"{lado}_aciona"] == "não" else ""),
            ))
    return fora


def todos_os_testes() -> list[Teste]:
    """O roteiro primeiro, o mapa depois. A ordem é dela: a hora com os quatro
    controles é a aceitação, e ela tem sessenta minutos."""
    vocab = vocabulario_das_pecas()
    return testes_do_roteiro(vocab) + testes_do_mapa(vocab)


# ---------------------------------------------------------------------------
# Quem está na mesa, ao vivo
# ---------------------------------------------------------------------------
def _mascarar(endereco: str) -> str:
    """A máscara da casa: octetos 4 e 5 zerados. Há DOIS portões que a cobram.

    É a mesma regra de `integrations.sinal_da_barra.mascarar`, e ela é aplicada
    ANTES de o endereço sair deste processo — o registro em disco pode ser lido
    e colado num documento versionado, e um MAC real ali é o defeito que os dois
    portões existem para pegar.
    """
    partes = endereco.split(":")
    if len(partes) != 6:
        return endereco
    partes[3] = partes[4] = "00"
    return ":".join(partes)


#: O DualSense por dentro do `hid_playstation`, no VID/PID que o driver casa.
#: O barramento distingue o transporte sem que ninguém escreva um byte:
#: `0003` é USB e `0005` é Bluetooth, e é o mesmo par que o `uevent` publica.
_VID_PID_DUALSENSE = ("0000054C", "00000CE6")
_BUS = {"0003": "cabo", "0005": "rádio"}


def _texto(caminho: pathlib.Path) -> str:
    """Lê um arquivo do sysfs, e devolve vazio se ele não existe ou não abre.

    O sysfs some por baixo de quem lê: o controle cai no meio da varredura e o
    caminho evapora. Um `try` largo aqui é a coisa certa — o que interessa é a
    ausência ser DITA como ausência, não virar traceback numa página que ela
    tem aberta com quatro controles na mão.
    """
    try:
        return caminho.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def pelo_sysfs() -> list[dict[str, Any]]:
    """Quem está na mesa AGORA, lido do `sysfs` — sem daemon e sem escrever.

    NASCEU DE UMA QUEIXA DELA, 07/09/2026, com quatro DualSense na mesa e o
    daemon parado: *"não estamos usando o nosso mapa? pq até agora ele não
    entendeu qual player deveria aparecer, nem qual controle (…) nem o modo de
    conexão (qual é bt e qual é cabo) se tá ou não carregando"*. Ela estava
    certa: a página só sabia perguntar ao daemon, e com ele parado punha
    travessão em tudo — como se não houvesse controle nenhum, tendo QUATRO.

    O QUE ISTO ALCANÇA, e cada um vem de um arquivo que o `hid_playstation` já
    publica, tudo leitura pura:

    ============  ===================================================
    transporte    o barramento do `HID_ID` do `uevent` (0003/0005)
    endereço      `HID_UNIQ`, mascarado antes de sair daqui
    bateria       `power_supply/*/capacity`
    carregando    `power_supply/*/status`
    lâmpada       `leds/*:white:player-N/brightness`, a que está acesa
    barra de luz  `leds/*:rgb:indicator/multi_intensity`
    ============  ===================================================

    O QUE ISTO **NÃO** ALCANÇA, e é declarado em vez de inventado: **a cor do
    plástico**. Ela mora nos caracteres 5-6 de um serial de 17 que só sai por
    `SET_FEATURE 0x80` — uma ESCRITA, da mesma família em que `[1, 1]` reseta o
    controle. A página não escreve no aparelho (decisão dela), então aqui a cor
    fica vazia e quem a preenche é o daemon, quando está vivo, ou ela, uma vez
    por controle, pelo seletor — e a escolha dela fica guardada pelo endereço.
    """
    achados = []
    for no in sorted(pathlib.Path("/sys/class/hidraw").glob("hidraw*")):
        dev = no / "device"
        campos = dict(
            linha.split("=", 1)
            for linha in _texto(dev / "uevent").splitlines() if "=" in linha)
        hid_id = campos.get("HID_ID", "")
        partes = hid_id.split(":")
        if len(partes) != 3 or (partes[1], partes[2]) != _VID_PID_DUALSENSE:
            continue
        uniq = campos.get("HID_UNIQ", "")
        bateria, estado = None, ""
        for ps in (dev / "power_supply").glob("*"):
            capacidade = _texto(ps / "capacity")
            if capacidade.isdigit():
                bateria = int(capacidade)
            estado = _texto(ps / "status").lower()
            break
        lampada, barra = None, ""
        for led in sorted((dev / "leds").glob("*:white:player-*")):
            if _texto(led / "brightness") not in ("", "0"):
                try:
                    lampada = int(led.name.rsplit("-", 1)[1])
                except ValueError:
                    lampada = None
                break
        for led in (dev / "leds").glob("*:rgb:indicator"):
            cru = _texto(led / "multi_intensity").split()
            if len(cru) == 3 and any(x != "0" for x in cru):
                barra = "#%02x%02x%02x" % tuple(int(x) & 0xFF for x in cru)
            break
        achados.append({
            "no": no.name,
            "uniq": _mascarar(uniq),
            "uniq_cru": uniq,
            "transporte": _BUS.get(partes[0], partes[0]),
            "bateria": bateria,
            "estado_da_bateria": estado,
            "lampada": lampada,
            "barra": barra,
            "nome_do_driver": campos.get("HID_NAME", ""),
        })
    return achados


#: ONDE A ESCOLHA DELA DE COR FICA. Ela nomeia o controle UMA vez, por
#: endereço, e a mesa lembra — é o que o daemon faria de graça se estivesse
#: ligado, e é ela quem sabe qual plástico está na mão dela.
def arquivo_das_cores_dela() -> pathlib.Path:
    return pasta_do_registro() / "as-cores-que-ela-disse.json"


def cores_que_ela_disse() -> dict[str, str]:
    try:
        return json.loads(arquivo_das_cores_dela().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def guardar_cor_dela(endereco: str, colorway: str) -> dict[str, str]:
    """Grava (ou apaga, com `colorway` vazio) a cor que ela disse de UM
    controle, pelo endereço já mascarado."""
    tudo = cores_que_ela_disse()
    if colorway:
        tudo[endereco] = colorway
    else:
        tudo.pop(endereco, None)
    alvo = arquivo_das_cores_dela()
    alvo.parent.mkdir(parents=True, exist_ok=True)
    tmp = alvo.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(tudo, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, alvo)
    return tudo


def ler_a_cor_no_aparelho() -> dict[str, Any]:
    """PERGUNTA A COR AOS CONTROLES, e é ATO DELA — nunca automático.

    A PÁGINA NÃO ESCREVE NO APARELHO por decisão, e esta função é a única
    exceção, aberta por ela em 07/09/2026 depois de ver os quatro cartões
    dizendo *"cor não lida"*: *"A cor exige escrita mesmo. Mas ler uma vez, sob
    seu comando, é o que o daemon faz. então por favor faz isso. é o que eu
    venho pedindo."*

    O QUE ISTO ESCREVE, e por que é seguro: um `SET_FEATURE 0x80` com o payload
    `[1, 19]`, que PEDE o serial de fábrica — o mesmo que o daemon manda uma
    vez por controle por sessão, e o mesmo que o `dualshock-tools` manda. A cor
    está nos caracteres 5-6 desse serial.

    QUEM MONTA E CONFERE O PEDIDO NÃO É ESTA FUNÇÃO: é
    `integrations.cor_do_plastico`, que tem uma função sem parâmetro para o
    payload e outra que o confere byte a byte antes de sair. A razão está
    escrita lá e vale repetir aqui: `0x80` é a família em que `[1, 1]` RESETA o
    controle e `[12, 1, …]` grava calibração na memória não-volátil. Não há
    desfazer, e ela tem quatro controles sem reposição. Uma segunda montagem
    nesta página seria uma segunda chance de escrever o byte errado.

    NÃO É AUTOMÁTICO, e é o outro lado da mesma trava: só roda quando ela
    aperta o botão. Uma leitura por tique seria uma escrita por tique.
    """
    from hefesto_dualsense4unix.integrations import cor_do_plastico

    fora: dict[str, Any] = {"lidos": {}, "erros": {}}
    slugs = colorway_por_nome()
    for visto in pelo_sysfs():
        endereco = visto["uniq"]
        try:
            cor = cor_do_plastico.ler_pelo_cabo(visto["uniq_cru"])
        except Exception as erro:  # o aparelho recusou, ou o nó sumiu
            fora["erros"][endereco] = f"{type(erro).__name__}: {erro}"
            continue
        if cor is None:
            fora["erros"][endereco] = "o controle não devolveu o serial"
            continue
        # O NOME VIRA SLUG PELO CSV DELA, que é o dono do par nome/desenho. O
        # `cor_do_plastico` devolve o nome de fábrica; o desenho escolhe por
        # `data-colorway`, e a junta é o mesmo CSV das 28 cores.
        slug = slugs.get(_dobra(cor.nome), "")
        if not slug:
            fora["erros"][endereco] = (
                f"o aparelho disse «{cor.nome}» e esse nome não está em "
                f"{CORES.name} — a cor foi lida, o desenho é que não a conhece")
            continue
        guardar_cor_dela(endereco, slug)
        fora["lidos"][endereco] = {
            "nome": cor.nome, "colorway": slug,
            # A CHAVE ABAIXO É O NOME DO CAMPO que `cor_do_plastico`
            # publica. Acentuá-la a faria divergir do atributo do dono, e a
            # página passaria a falar um nome que o dono não responde. (E este
            # comentário não pode ESCREVER a chave: escrevê-la o tornaria a
            # própria violação que ele explica — aconteceu, nesta linha.)
            "codigo": cor.codigo}  # noqa-acento: campo publicado pelo dono
    return fora


def _pergunta_ao_daemon(metodo: str, prazo: float = 1.5) -> Any:
    """Uma chamada JSON-RPC pelo socket unix, com a biblioteca padrão.

    O `cli/ipc_client.py` é o cliente da casa, e ele é assíncrono e puxa o
    pacote inteiro. Aqui basta uma linha de JSON e uma de resposta: o contrato é
    *uma mensagem por linha*, e está publicado em
    `docs/protocol/ipc-unix-socket.md`. O caminho do socket continua vindo do
    dono (`utils/xdg_paths.ipc_socket_path`) — reinventá-lo era o jeito garantido
    de medir outro daemon.
    """
    from hefesto_dualsense4unix.utils.xdg_paths import ipc_socket_path

    caminho = ipc_socket_path()
    if not caminho.exists():
        raise FileNotFoundError(str(caminho))
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(prazo)
        s.connect(str(caminho))
        pedido = {"jsonrpc": "2.0", "id": 1, "method": metodo, "params": {}}
        s.sendall(json.dumps(pedido, ensure_ascii=False).encode("utf-8") + b"\n")
        buf = b""
        while not buf.endswith(b"\n"):
            pedaco = s.recv(65536)
            if not pedaco:
                break
            buf += pedaco
    resposta = json.loads(buf.decode("utf-8"))
    if "error" in resposta:
        raise RuntimeError(str(resposta["error"]))
    return resposta.get("result")


#: A PORTA DA RÉGUA, e ela é só da régua. Um JSON com a mesma forma que
#: :func:`quem_esta_na_mesa` devolve, para o Playwright poder provar os quatro
#: desenhos com quatro MODELOS diferentes sem os quatro controles dela na mesa.
#:
#: POR QUE ISTO É UM CAMINHO DECLARADO E NÃO UM `monkeypatch` do teste: a prova
#: que interessa — *o realce vence a folha das zonas* — só existe quando há
#: colorway, e sem daemon não há. Um teste que remenda o módulo por dentro
#: prova o remendo; um que entra pela porta prova a porta. O nome tem `MENTIRA`
#: no meio de propósito, e o cabeçalho da página diz quando ela está aberta.
PORTA_DA_REGUA = "MESA_DE_MEDICAO_MESA_DE_MENTIRA"


def quem_esta_na_mesa() -> dict[str, Any]:
    """Os quatro postos, com o que o daemon publicou — ou a ausência, dita.

    A PÁGINA NÃO ESCREVE NADA NO APARELHO PARA SABER QUEM É QUEM. O degrau
    `modelo` custa um `SET_FEATURE 0x80` — a mesma família em que `[1, 1]`
    RESETA o controle —, e quem o paga é o daemon, uma vez por controle por
    sessão. Aqui só se lê o que ele já publicou.

    A PRECEDÊNCIA DO NOME TEM DONO e não se reinventa: `nome_declarado` (o nome
    que ELA deu) > `modelo` (decodificado do serial) > o transporte sozinho.
    **Sem modelo publicado, travessão — nunca um colorway escolhido**, porque
    escolher um seria a tela afirmar um aparelho que ninguém leu.
    """
    de_mentira = os.environ.get(PORTA_DA_REGUA)
    if de_mentira:
        dado = json.loads(pathlib.Path(de_mentira).read_text(encoding="utf-8"))
        dado["daemon"] = f'MESA DE MENTIRA ({PORTA_DA_REGUA}) — nenhum aparelho foi lido'
        return _mesa_mascarada(dado)

    slugs = colorway_por_nome()
    postos: dict[str, dict[str, Any]] = {
        p: {
            "posto": p, "presente": False, "nome": "—", "modelo": "",
            "colorway": "", "transporte": "", "bateria": None,
            "estado_da_bateria": "", "uniq": "", "lampada": None, "barra": "",
        }
        for p in POSTOS
    }
    fora: dict[str, Any] = {"daemon": "", "postos": postos, "quando": _agora()}
    def _pelo_kernel(motivo: str) -> dict[str, Any]:
        """A SEGUNDA FONTE, quando o daemon não responde — e ela não é
        consolo: é o kernel, que é quem o daemon também lê.

        Ela mediu isto com quatro controles na mesa e o daemon parado, e a
        página punha travessão em tudo: *"nem qual controle (…) nem o modo de
        conexão (qual é bt e qual é cabo) se tá ou não carregando"*. Tudo isso
        o `hid_playstation` publica de graça. O único campo que fica vazio é a
        COR, que exige escrita — e ela é preenchida pela escolha dela, que a
        mesa guarda por endereço.
        """
        dela = cores_que_ela_disse()
        vistos = pelo_sysfs()
        # A LÂMPADA DECIDE O POSTO, e só ela: é o número que o plástico mostra
        # na mão dela. Quando duas lâmpadas coincidem (dois controles no LED 1,
        # medido nesta bancada com o daemon parado) o desempate é a ordem do
        # nó, e o cartão DIZ que empatou em vez de fingir certeza.
        por_posto: dict[str, dict[str, Any]] = {}
        sobra = []
        for v in vistos:
            alvo = f"P{v['lampada']}" if v.get("lampada") in (1, 2, 3, 4) else ""
            if alvo and alvo not in por_posto:
                por_posto[alvo] = v
            else:
                sobra.append(v)
        for v in sobra:
            livre = next((p for p in POSTOS if p not in por_posto), "")
            if livre:
                por_posto[livre] = v
        for posto, v in por_posto.items():
            cor = dela.get(v["uniq"], "")
            postos[posto].update({
                "presente": True,
                "nome": nome_do_colorway(cor) or v["transporte"] or "—",
                "modelo": nome_do_colorway(cor),
                "colorway": cor,
                "transporte": v["transporte"],
                "bateria": v["bateria"],
                "estado_da_bateria": v["estado_da_bateria"],
                "uniq": v["uniq"],
                "lampada": v["lampada"],
                "barra": v["barra"],
                "de_onde": "kernel",
                "empatou": bool(sobra) and v in sobra,
            })
        quantos = len(por_posto)
        fora["daemon"] = (
            f"{motivo} · lendo direto do kernel: {quantos} DualSense na mesa. "
            f"Transporte, bateria, carga, lâmpada e barra vêm do `sysfs`. "
            # A COR TEM DOIS CAMINHOS desde 07/09/2026, e o texto diz os
            # dois: o botão pergunta ao aparelho (uma escrita, sob o comando
            # dela), e o seletor continua valendo para quando ela preferir
            # dizer. Antes esta frase afirmava que a página não lia — e a
            # afirmação envelheceu no mesmo dia em que o botão nasceu.
            f"A COR do plástico sai por leitura no aparelho: clique em `ler a "
            f"cor nos controles` e a mesa lembra pelo endereço. Ou diga qual é "
            f"cada um no seletor de cada cartão."
            if quantos else
            f"{motivo} · e o kernel também não vê DualSense nenhum agora.")
        return fora

    try:
        estado = _pergunta_ao_daemon("daemon.state_full")
    except FileNotFoundError:
        return _pelo_kernel("daemon offline")
    except Exception as erro:  # o canal caiu; a página continua servindo
        return _pelo_kernel(f"daemon não respondeu ({erro})")

    controles = (estado or {}).get("controllers") or (estado or {}).get("controles") or []
    if isinstance(controles, dict):
        controles = list(controles.values())
    livres = [p for p in POSTOS]
    for c in controles:
        if not isinstance(c, dict):
            continue
        slot = c.get("player_slot")
        posto = f"P{slot}" if isinstance(slot, int) and 1 <= slot <= 4 else ""
        if posto not in postos or postos[posto]["presente"]:
            posto = next((p for p in livres if not postos[p]["presente"]), "")
        if not posto:
            continue
        modelo = str(c.get("modelo") or "").strip()
        declarado = str(c.get("nome_declarado") or "").strip()
        transporte = str(c.get("transporte") or "").strip()
        postos[posto].update({
            "presente": bool(c.get("connected", True)),
            "nome": declarado or modelo or transporte or "—",
            "modelo": modelo,
            "colorway": slugs.get(_dobra(modelo), "") if modelo else "",
            "transporte": transporte,
            "bateria": c.get("battery_pct"),
            "estado_da_bateria": str(c.get("battery_state") or ""),
            "uniq": _mascarar(str(c.get("uniq") or "")),
            "lampada": slot if isinstance(slot, int) else None,
            "barra": str(c.get("lightbar_rgb") or ""),
        })
    fora["daemon"] = f"daemon vivo — {sum(1 for p in postos.values() if p['presente'])} de 4 na mesa"
    return fora


# ---------------------------------------------------------------------------
# O registro em disco — o ponto inteiro
# ---------------------------------------------------------------------------
def pasta_do_registro() -> pathlib.Path:
    """Onde o registro vive. `XDG_STATE_HOME`, pelo dono do caminho."""
    from hefesto_dualsense4unix.utils.xdg_paths import state_dir

    p = state_dir() / "mesa-de-medicao"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _agora() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


class Registro:
    """Grava CADA clique, na hora, em disco.

    DUAS ESCRITAS, e as duas são necessárias:

    * `registro-<data>.jsonl` — a fita, append-only. É o histórico, e uma
      resposta corrigida não apaga a anterior: *não se apaga decisão medida*;
    * `estado.json` — a última resposta de cada teste. É o que a página lê ao
      recarregar, e é o que faz uma medição SOBREVIVER a fechar o navegador.

    E CADA LINHA CARREGA O **COMO** — o gesto que foi aplicado, o que o mapa
    publica sobre aquela célula, e o estado dos quatro no instante. É esta parte
    que se perdia quando a sessão morria.
    """

    def __init__(self, pasta: pathlib.Path | None = None) -> None:
        self.pasta = pasta or pasta_do_registro()
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.fita = self.pasta / f"registro-{_dt.date.today().isoformat()}.jsonl"
        self.estado = self.pasta / "estado.json"
        self._tranca = threading.Lock()

    def ler(self) -> dict[str, Any]:
        if not self.estado.exists():
            return {}
        try:
            dado = json.loads(self.estado.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return {}
        return dado if isinstance(dado, dict) else {}

    def gravar(self, item: dict[str, Any]) -> dict[str, Any]:
        """Uma resposta. RECUSA a que não traz o COMO.

        A recusa é a régua morando dentro do instrumento. A queixa dela é que o
        resultado sobrevivia e o *como* não; gravar uma resposta sem o gesto
        seria reproduzir o defeito com um arquivo a mais. Quem não sabe dizer
        como fez, escreve isso — o campo aceita `"não apliquei"`, o que não
        aceita é o silêncio.
        """
        gesto = str(item.get("gesto") or "").strip()
        if not gesto:
            # O COMO NÃO É DELA — corrigido em 07/09/2026, com a frase dela:
            # *"isso aqui me quebra. isso eu espero que a página descreva"*.
            # Ela tinha razão e o defeito era de quem escreveu a recusa: o
            # COMO já existe nos arquivos (as colunas `canal`, `report_id`,
            # `offset`, `comando`, `codigo_ref` e `teste_que_morde` da célula),
            # e cobrar dela que o digitasse era pedir que ela redigitasse o
            # que o repositório já publica. A página agora o traz PRONTO e
            # ela só corrige se estiver errado.
            #
            # A RECUSA CONTINUA EXISTINDO, e continua sendo o ponto: o que não
            # se grava é uma linha SEM COMO NENHUM — nem o do arquivo, nem o
            # dela. Isso só acontece se a página deixar de preencher, e aí a
            # recusa está apanhando um defeito meu, não uma falta dela.
            raise ValueError(
                "esta linha chegou sem COMO nenhum — nem o que o arquivo "
                "publica nem um escrito à mão. O COMO é a metade que se "
                "perdia quando a sessão morria; sem ele o registro não vale. "
                "Isto é defeito da página, não dela: o campo devia ter vindo "
                "preenchido.")
        linha = {
            "quando": _agora(),
            "teste": item.get("teste"),
            "secao": item.get("secao"),
            "titulo": item.get("titulo"),
            "celula": item.get("celula"),
            "respostas": item.get("respostas") or {},
            # O QUE ELA ESCREVEU SOBRE CADA CONTROLE, separado do que ela
            # escreveu sobre o conjunto. Com quatro na mesa, "acendeu na hora"
            # sem dizer em qual é uma frase que ninguém consegue usar depois.
            "notas": item.get("notas") or {},
            # A CONDIÇÃO DE CADA CONTROLE NESTE TESTE, escrita por ela antes do
            # INICIAR: *"Controle A, não liga, o b cor azul. o c, tá conectado
            # no rosa, o y vai conectar azul"*. Sem ela gravada, a fita diria
            # que os quatro fizeram a mesma coisa — e o teste inteiro existe
            # porque eles não fizeram.
            "condicoes": item.get("condicoes") or {},
            # O PAPEL DE CADA UM NO MOMENTO DA RESPOSTA. Ele mora no roteiro e
            # o roteiro muda; sem gravá-lo aqui, uma medição de hoje relida
            # amanhã seria julgada contra a expectativa de amanhã, e o
            # `confere()` daria outro veredito sobre o mesmo fato.
            "papeis": item.get("papeis") or {},
            "o_que_eu_vi": item.get("o_que_eu_vi") or "",
            "gesto": gesto,
            "como_do_arquivo": item.get("como_do_arquivo") or [],
            "mesa": _mesa_mascarada(item.get("mesa") or {}),
            "veredito": item.get("veredito") or "",
        }
        # O LAUDO POR CONTROLE É DERIVADO, e é gravado por isso mesmo: quem
        # ler a fita daqui a um mês não precisa reexecutar a regra para saber
        # o que a mesa disse na hora. `confere()` é o dono dos dois lados.
        linha["confere"] = {
            posto: list(confere(linha["papeis"].get(posto, PAPEL_OBSERVA),
                                linha["respostas"].get(posto, "")))
            for posto in POSTOS
        }
        with self._tranca:
            with open(self.fita, "a", encoding="utf-8") as arq:
                arq.write(json.dumps(linha, ensure_ascii=False) + "\n")
            tudo = self.ler()
            tudo[str(item.get("teste"))] = linha
            tmp = self.estado.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(tudo, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self.estado)
        return linha


def _mesa_mascarada(mesa: dict[str, Any]) -> dict[str, Any]:
    """O estado dos quatro, com o endereço já na máscara da casa.

    A máscara é aplicada DE NOVO aqui, mesmo que `quem_esta_na_mesa` já a tenha
    aplicado, porque este dicionário chega pelo navegador — e o que chega de
    fora não é de confiança. Duas réguas independentes é o que revela.
    """
    postos = (mesa or {}).get("postos") or {}
    if isinstance(postos, dict):
        for p in postos.values():
            if isinstance(p, dict) and p.get("uniq"):
                p["uniq"] = _mascarar(str(p["uniq"]))
    return mesa


def veredito(respostas: dict[str, str]) -> str:
    """`obedeceu` · `falhou` · `parcial` · `não feito` — o que o índice mostra.

    O papel de cada controle NÃO entra aqui de propósito: quem julga é quem
    olhou o aparelho. Uma resposta `obedeceu` num controle que deveria ficar
    calado é um ACHADO, e transformá-la em "falhou" automaticamente esconderia
    exatamente a linha que interessa.

    DEFEITO MEDIDO E CURADO EM 06/09/2026, PELA PROVA — e ele era um verde
    sobre nada, que é a família que esta casa caça:

    * `{P1..P4: "nada"}` — **os quatro disseram que NÃO ACONTECEU NADA** —
      devolvia `obedeceu`. A regra era `all(v in ("obedeceu", "nada"))`, e um
      conjunto só de `nada` a satisfaz. O índice é o instrumento que ela lê
      para saber o que ainda falta medir: pintar de verde a linha em que o
      gesto não produziu efeito em controle NENHUM é a leitura errada que uma
      mesa de medição não pode produzir;
    * e `falhou` era **INALCANÇÁVEL**. Esta docstring nomeia quatro estados, o
      CSS tem a classe `.e-falhou` e o JS tem o ramo que a escolhe — e nenhum
      caminho desta função jamais o devolvia. Uma paleta com quatro cores para
      três estados é o instrumento afirmando uma medida que ele não faz.

    A REGRA AGORA, e ela continua sem julgar papel: `obedeceu` exige que **ao
    menos um** controle tenha obedecido. Nenhum obedeceu e ninguém viu coisa
    estranha = o gesto não pegou em lugar nenhum = `falhou`.
    """
    valores = [v for v in respostas.values() if v]
    if not valores or all(v == "nao-vi" for v in valores):
        return "não feito"
    if any(v == "outra-coisa" for v in valores):
        return "parcial"
    if not any(v == "obedeceu" for v in valores):
        # Só `nada` (e talvez algum `nao-vi`): o gesto não produziu efeito em
        # controle nenhum. Isto é o `falhou` do índice, e é o que ela precisa
        # ver para voltar à linha.
        return "falhou"
    if all(v in ("obedeceu", "nada") for v in valores):
        return "obedeceu"
    return "parcial"


#: A PÁGINA QUE É DONA DO DESENHO. O mapa do controle pinta o contorno com a
#: cor do plástico desde 27/08/2026, e é dele que esta mesa lê a regra — não
#: uma segunda cópia. Mordida: mude o `stroke-width` lá e a mesa muda junto.
_A_PAGINA_DO_MAPA = ("src/hefesto_dualsense4unix/interface/paginas/"
                     "mapa-do-controle.html")


def _regras_de_estilo(texto: str) -> list[tuple[str, str]]:
    """As regras `seletor {corpo}` dos blocos de estilo, sem os comentários."""
    fora: list[tuple[str, str]] = []
    for bloco in re.findall(r"<style[^>]*>(.*?)</style>", texto, re.S):
        limpo = re.sub(r"/\*.*?\*/", "", bloco, flags=re.S)
        for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", limpo):
            fora.append((" ".join(m.group(1).split()), m.group(2).strip()))
    return fora


def folha_do_desenho(prefixos: Sequence[str]) -> str:
    """As regras que PINTAM O DESENHO — perguntadas à página que as escreve.

    *"e cara o contorno não tá pintado"* — 07/09/2026, ela comparando com o
    mapa. E estava certa: o desenho é DE LINHA, e quem dá cor à linha é o
    `stroke`. A folha dos 28 (`monta.folha_das_cores()`) pinta as ZONAS; o
    contorno do casco, os furos e as juntas vivem numa segunda folha, que até
    hoje só existia dentro do `mapa-do-controle.html`.

    Copiá-la aqui seria a segunda cópia que diverge sem ninguém ver — o defeito
    que aposentou a pasta do mockup. Então esta função LÊ o mapa e reescreve
    só o endereço: `.ds` vira o desenho desta página, e `mp-` vira o prefixo de
    cada um dos quatro postos (sem prefixo os ids colidem e o `url(#…)` do
    segundo desenho aponta para o gradiente do primeiro).
    """
    texto = (RAIZ / _A_PAGINA_DO_MAPA).read_text(encoding="utf-8")
    # A FOLHA DO DESENHO SÃO AS REGRAS `.ds ` — o desenho, não a página. Ficam
    # de fora duas famílias, e as duas por razão medida:
    #
    # * `.ds{width:100%…}`, que é o TAMANHO no mapa. A mesa põe quatro lado a
    #   lado e tem teto próprio; herdar o de lá esticaria cada um a 74vh.
    # * as `.mapa:has(.item-X:hover)`, que são o realce DE LÁ. O gatilho delas
    #   mora na lista da direita, que aqui não existe: quem acende na mesa é
    #   `monta.folha_de_realce()`, pela classe `marcada` que `monta.svg` põe no
    #   próprio grupo. Trazer as de lá seria acender no hover do mouse — e o
    #   que manda acender aqui é o roteiro, não o ponteiro.
    #
    # O QUE ENTRA, e cada uma responde por uma queixa dela: o `fill` do grupo,
    # o `stroke` do casco (*"o contorno não tá pintado"*), o `sem-tinta` que
    # apaga o círculo do PS (*"o do PS não tem esse círculo no meio"*), a luz
    # do lightbar, os LEDs de jogador e as peças ocultas.
    regras = _regras_de_estilo(texto)
    # E OS GLIFOS ENTRAM JUNTO (`.sobre`): eles são a segunda vista da mesma
    # peça — o R do analógico, o triângulo, o losango do Options. Sem as regras
    # deles os vinte glifos caíam no preto padrão do SVG, que sobre o casco
    # escuro é peça invisível. Medido em 07/09/2026: mapa cinza-claro, mesa
    # `rgb(0,0,0)`.
    do_desenho = [(sel, corpo) for sel, corpo in regras
                  if (sel.startswith(".ds ") or sel.startswith(".sobre"))
                  and ":hover" not in sel]
    if not any("var(--z-casca-solida)" in corpo for _, corpo in do_desenho):
        raise RuntimeError(
            f"o desenho perdeu a folha do traço em {_A_PAGINA_DO_MAPA} — a mesa "
            f"lê de lá e não tem cópia própria")
    # AS VARIÁVEIS VIAJAM COM AS REGRAS, e esta linha é uma cicatriz: a
    # primeira volta trouxe `fill:var(--led-apagado)` sem trazer o
    # `--led-apagado`, e os cinco LEDs de jogador ficaram PRETOS — um valor que
    # não resolve não herda o de trás, cai no padrão. O mapa as declara no
    # `:root` dele; aqui elas moram no desenho, para não disputarem com a
    # paleta da casa.
    usadas = {m for _, corpo in do_desenho
              for m in re.findall(r"var\((--[\w-]+)", corpo)}
    da_casa = {"--z-casca-solida", "--luz", "--realce"}
    declara = {}
    for sel, corpo in regras:
        if sel not in (":root", "html", ":root,html"):
            continue
        for nome, valor in re.findall(r"(--[\w-]+)\s*:\s*([^;]+)", corpo):
            declara[nome] = valor.strip()
    faltam = {n: declara[n] for n in sorted(usadas - da_casa) if n in declara}
    linhas = []
    if faltam:
        linhas.append("svg[data-colorway]{"
                      + ";".join(f"{n}:{v}" for n, v in faltam.items()) + "}")
    for sel, corpo in do_desenho:
        for pref in prefixos:
            alvo = ", ".join(
                parte.strip().replace(".ds ", "svg[data-colorway] ")
                .replace("mp-", f"{pref}-")
                for parte in sel.split(","))
            linhas.append(f"{alvo}{{{corpo}}}")
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# Os quatro desenhos
# ---------------------------------------------------------------------------
def desenhos(teste: Teste, mesa: dict[str, Any]) -> dict[str, str]:
    """Os quatro DualSense, com a peça do teste acesa e os papéis distintos.

    O REALCE VEM DE `monta.svg(apertados=…)`, e ele é o único dono: a página não
    escreve `class="marcada"` em lugar nenhum. Trocar a coluna `peca` de uma
    linha do mapa muda o que acende — que é a mordida da especificação.

    A COR VEM DA FOLHA DOS 28, publicada UMA VEZ na página; por isso cada
    desenho nasce com `folha=False`. Uma folha podada por desenho seria uma
    escolha cravada, e é o que `check_a_cor_vem_do_aparelho.py` conta como
    dívida.

    O `pref` é o que permite quatro na mesma página: sem ele os ids colidem e o
    `url(#…)` do segundo desenho aponta para o gradiente do primeiro.
    """
    postos = (mesa or {}).get("postos") or {}
    fora = {}
    for posto in POSTOS:
        vivo = postos.get(posto) or {}
        colorway = str(vivo.get("colorway") or "")
        # A PEÇA ACENDE NOS QUATRO, e é de propósito: o que separa os papéis é
        # a TINTA (`--realce`, definida por `.papel-*` no cartão), não a
        # ausência. Acender só no que deve reagir tiraria da tela justamente a
        # pergunta que interessa — *o que NÃO PODE reagir reagiu?* — e ela só se
        # responde olhando a mesma peça nos quatro.
        acender = tuple(pid for pid, _ in teste.pecas)
        lampada = vivo.get("lampada")
        fora[posto] = monta.svg(
            pref=posto.lower(),
            colorway=colorway,
            classes=f"ds-svg papel-{teste.papeis.get(posto, PAPEL_OBSERVA)}",
            apertados=acender,
            jogador=lampada if isinstance(lampada, int) and 1 <= lampada <= 4 else None,
            luz=str(vivo.get("barra") or "") or None,
            folha=False,
        )
    return fora


# ---------------------------------------------------------------------------
# A página
# ---------------------------------------------------------------------------
def _e(texto: Any) -> str:
    return html.escape(str(texto), quote=True)


#: A PALETA TEM DONO, E NÃO É ESTA PÁGINA — `scripts/paleta_da_casa.py`, o
#: mesmo módulo de que o `specs.html`, o `painel.html`, o `frases-de-tela.html`
#: e o `index.html` leem. Pedido dela, 06/09/2026: *"mantém o mesmo tema que
#: vemos aplicando"*. A mesa nasceu com paleta clara PRÓPRIA, com nove hex
#: digitados aqui — a quinta cópia da mesma decisão, e a única fora de dia.
#: Os quatro nomes abaixo são os do papel de cada controle, e ESSES são desta
#: página: não há papel de controle em artefato nenhum dos outros quatro.
_TEMA_DA_MESA = """
:root{
  --reage:var(--color-accent);
  --calado:var(--color-ink-faint);
  --observa:var(--color-frio);
  --bate:var(--color-ok);
  --nao-bate:var(--color-alerta);
  --sem-julgar:var(--color-ink-faint);
  /* O ROSA DO FOCO, o mesmo `--pink` do mapa do controle e das dez abas. Ele
     não está em `paleta_da_casa.TOKENS` porque lá o papel dele é `--color-accent`
     (roxo); aqui ele é o "olhe para cá", e é o que ela reconhece. */
  --color-pink:#ff79c6;
}
"""

_CSS = paleta_da_casa.TOKENS + _TEMA_DA_MESA + """
*{box-sizing:border-box}
body{margin:0;background:var(--color-paper-2);color:var(--color-ink);
  font:var(--text-base)/1.55 var(--font-corpo)}
header{position:sticky;top:0;z-index:9;background:var(--color-paper);
  border-bottom:var(--rule-hair) solid var(--color-rule);
  padding:var(--space-2xs) var(--space-sm);
  display:flex;gap:var(--space-sm);align-items:baseline;flex-wrap:wrap}
header b{font-size:var(--text-lg);letter-spacing:-.01em}
.cinza{color:var(--color-ink-quiet);font-size:var(--text-sm)}
.filtro{display:inline-flex;gap:2px;border:var(--rule-hair) solid var(--color-rule);
  border-radius:var(--radius-sm);padding:2px}
.filtro button{border:0;background:transparent;font-size:var(--text-xs);
  padding:2px var(--space-2xs);border-radius:2px;color:var(--color-ink-quiet)}
.filtro button.ligado{background:var(--color-accent);color:var(--color-paper-2);
  font-weight:600}
#ler-cor{font-size:var(--text-xs);padding:2px var(--space-2xs)}
#ler-cor:disabled{opacity:.5}
#secao-filtro{font:var(--text-xs)/1.4 var(--font-corpo);
  padding:2px var(--space-2xs);border-radius:var(--radius-sm);
  border:var(--rule-hair) solid var(--color-rule);
  background:var(--color-paper-3);color:var(--color-ink);max-width:26rem}
/* O SELO DO QUE JÁ FOI MEDIDO — e ele diz DE ONDE, não só que sim. */
.selo{display:inline-flex;align-items:center;gap:var(--space-3xs);
  font-size:var(--text-xs);font-weight:600;color:var(--color-ok);
  border:var(--rule-hair) solid var(--color-ok);border-radius:var(--radius-sm);
  padding:1px var(--space-2xs)}
.selo.vazio{display:none}
.vindo-do-mapa{outline:1px dashed var(--color-ok);outline-offset:1px}
main{max-width:1240px;margin:0 auto;padding:var(--space-sm)}
.cartao{background:var(--color-paper);border:var(--rule-hair) solid var(--color-rule);
  border-radius:var(--radius-md);padding:var(--space-md);margin:0 0 var(--space-sm)}

/* ---------------------------------------------------------------------
   O TOPO EXPLICA, e é a primeira coisa da página — pedido dela:
   *"começa na parte superior explicando o que está sendo testado e afins"*.
   Antes, o título vinha sozinho e o "o que vai acontecer" ficava DEPOIS dos
   quatro desenhos: ela via os controles antes de saber para quê.
   --------------------------------------------------------------------- */
.capa{border-left:3px solid var(--color-accent);padding-left:var(--space-sm);
  margin-bottom:var(--space-md)}
.capa .fita{display:flex;gap:var(--space-2xs);align-items:baseline;
  flex-wrap:wrap;color:var(--color-ink-quiet);font-size:var(--text-xs);
  letter-spacing:.08em;text-transform:uppercase}
.capa h2{margin:var(--space-3xs) 0 var(--space-2xs);font-size:var(--text-xl);
  font-weight:600;letter-spacing:-.015em;line-height:1.25}
.capa .frase{font-size:var(--text-base);color:var(--color-ink);margin:0}
.capa .quando{margin:var(--space-2xs) 0 0;color:var(--color-ink-quiet);
  font-size:var(--text-sm)}
.capa .quando b{color:var(--color-ok);font-weight:600}

h3{margin:var(--space-md) 0 var(--space-2xs);font-size:var(--text-xs);
  letter-spacing:.09em;text-transform:uppercase;color:var(--rot-campo,var(--color-ok));
  font-weight:600}
p{margin:0 0 var(--space-2xs)}

/* ---------------------------------------------------------------------
   OS QUATRO. Cada coluna é UMA pilha: desenho, quem é, o que responder, o
   campo extra e o veredito. Pedido dela: *"coloca em baixo de cada controle
   as opções do que selecionar e um campo extra"*.
   --------------------------------------------------------------------- */
.quatro{display:grid;grid-template-columns:repeat(4,1fr);gap:var(--space-xs)}
@media (max-width:940px){.quatro{grid-template-columns:repeat(2,1fr)}}
@media (max-width:520px){.quatro{grid-template-columns:1fr}}
.ctl{border:var(--rule-hair) solid var(--color-rule);
  border-radius:var(--radius-md);padding:var(--space-2xs);
  background:var(--color-paper-2);display:flex;flex-direction:column;
  gap:var(--space-3xs)}
/* A BORDA DO CARTÃO É A COR DO PLÁSTICO DAQUELE CONTROLE — dela, 07/09/2026:
   *"a borda de cada controle deve ter a borda na cor do model"*. É o que casa
   a coluna da tela com o aparelho na mão dela sem ler uma palavra. Cai na
   régua neutra quando a cor ainda não foi lida. */
.ctl{border-color:var(--cor-do-modelo, var(--color-rule))}
.ctl[style*="--cor-do-modelo"]{border-width:4px}

/* A PEÇA EM FOCO FICA OPACA, sempre. Medido em 07/09/2026: o `mic` acendia com
   `opacity:.63` — o valor que ele traz do desenho —, e uma peça que a página
   manda olhar meio transparente é meio instrução. O mapa faz o mesmo com as
   ocultas (`.oculta.acesa{opacity:.95}`). */
svg[data-colorway] g.marcada{opacity:1 !important}

/* E A BATERIA ACENDE A BARRA DE LUZ, como no mapa do controle — decisão dela de
   27/08/2026: *"bateria pode ser usando as barras da lightbar com 100% e a
   barra cheia e 0% ela apagada"*. Apontar a bateria sem acender as duas tiras é
   apontar um medidor que não está na tela. */
svg[data-colorway]:has([id$="-feat-bateria"].marcada) [id$="-lightbar"]
  :is(path,rect,circle,ellipse,polygon){
  fill:var(--realce,var(--color-pink)) !important;
  stroke:var(--realce,var(--color-pink)) !important}

/* O FOCO É O DO MAPA DO CONTROLE — dela: *"as bordas ou coisas a serem
   observadas ficam com o foco o mesmo que temos no mapa dos controles"*. Lá a
   peça em foco acende em `--pink`, e o rosa é o que ela já associa a "olhe
   aqui" em toda a casa. A mesa usava três cores por papel, e o papel já é dito
   pela moldura, pelo rótulo e pelo texto do que observar — a peça acesa só
   precisa GRITAR, e três cores diferentes de grito é uma a mais que zero. */
.ctl{--realce:var(--color-pink)}
/* A BORDA É DO MODELO E O PAPEL É O HALO — os dois sinais convivem porque
   dizem coisas diferentes: a borda diz QUAL CONTROLE é (e ela casa isso com o
   plástico na mão), o halo diz o que se espera dele NESTE teste. A primeira
   volta pôs um `outline` roxo no papel, e ele cobria a borda do modelo: os
   quatro cartões ficavam roxos e a cor do plástico sumia da moldura. */
.ctl.papel-reage{box-shadow:0 0 0 2px color-mix(in srgb,var(--reage) 55%,transparent)}
.ctl.papel-calado{opacity:.8}
/* O DESENHO É DE LINHA, E A LINHA NÃO PODE ENCOLHER COM ELE.
   -----------------------------------------------------------------------
   *"e cara o contorno não tá pintado (…) falta a parte superior do
   touchpad"* — 07/09/2026. E o contorno ESTAVA pintado: medido, `stroke`
   `rgb(228,224,216)` nos quatro, a mesma cor do mapa. O que faltava era
   ESPESSURA.

   A conta, medida no Chrome: o `stroke-width:.42` vem em unidades do
   `viewBox`, que tem 116,68 de largura. O mapa desenha o SVG com 1160 px —
   escala de 9,9 — e o traço sai com 4,2 px de tela. A mesa desenhava com 190
   px: escala 1,6, traço de **0,68 px**. Abaixo de um pixel o navegador não
   desenha uma linha, desenha um cinza fraco — e as linhas mais finas, como a
   borda de cima do touchpad, somem inteiras no antialiasing.

   A cura tem nome no SVG: `non-scaling-stroke` tira o traço da escala do
   desenho e o mede em pixels de TELA. Assim o contorno tem a mesma presença
   nos quatro cartões, no cartão largo e no estreito, e não depende de quantos
   controles cabem na linha.

   O TETO SOBE JUNTO (190 → 250 px): com o traço resolvido, o que segurava o
   desenho pequeno deixou de existir, e o que ela precisa é ENXERGAR. */
.ctl svg{width:100%;max-width:250px;height:auto;display:block;margin:0 auto}
/* O `!important` NÃO É PREGUIÇA, é a única saída: a folha que vem do mapa
   endereça o casco por ID (`#p1-corpo .peca`), e um id vence qualquer soma de
   classes. Sem ele esta regra é escrita e ignorada — foi o que aconteceu na
   primeira volta, e a foto saiu idêntica à anterior. */
.ctl svg :is(.peca,.corpo){vector-effect:non-scaling-stroke !important}
.ctl svg [id$="-corpo"] :is(.peca,.corpo){stroke-width:1.6px !important}
.ctl svg .oculta .peca{stroke-width:1.2px !important}
.ctl .rotulo-papel{font-size:var(--text-xs);font-weight:600;letter-spacing:.07em;
  text-transform:uppercase}
.t-reage{color:var(--reage)} .t-calado{color:var(--calado)} .t-observa{color:var(--observa)}
.ctl .quem{display:flex;align-items:baseline;gap:var(--space-3xs);
  flex-wrap:wrap;margin-top:var(--space-3xs)}
.ctl .posto{font-size:var(--text-base);font-weight:700;color:var(--realce,var(--color-ink))}
.ctl .meta{font-size:var(--text-xs);color:var(--color-ink-quiet);
  font-variant-numeric:tabular-nums;line-height:1.4}
.ctl .ender{font-family:var(--font-dado);font-size:10px;color:var(--color-ink-faint)}
/* O SELETOR DE COR, igual ao do mapa do controle. Ele existe porque a cor do
   plástico NÃO se lê sem escrever no aparelho, e esta página não escreve: ela
   diz qual é, uma vez, e a mesa lembra pelo endereço. */
.ctl select.cor{width:100%;font:var(--text-xs)/1.4 var(--font-corpo);
  padding:var(--space-3xs) var(--space-2xs);
  border:var(--rule-hair) solid var(--color-rule);border-radius:var(--radius-sm);
  background:var(--color-paper);color:var(--color-ink)}
.ctl select.cor:disabled{opacity:.4}
.ctl .nome{font-weight:600;font-size:var(--text-sm);color:var(--color-ink)}
.troca-cor summary{font-size:var(--text-xs);color:var(--color-ink-faint);
  cursor:pointer;list-style:none;padding:1px 0}
.troca-cor summary::-webkit-details-marker{display:none}
.troca-cor summary:hover{color:var(--color-accent);text-decoration:underline}
/* A CONDIÇÃO — o que ESTE controle faz neste teste, escrita por ela. */
.condicao-rot{display:block;font-size:var(--text-xs);letter-spacing:.07em;
  text-transform:uppercase;color:var(--rot-campo,var(--color-ok));
  font-weight:600;margin-top:var(--space-2xs)}
input.condicao{width:100%;font:var(--text-sm)/1.4 var(--font-corpo);
  padding:var(--space-3xs) var(--space-2xs);
  border:var(--rule-hair) solid var(--color-rule);border-radius:var(--radius-sm);
  background:var(--color-paper);color:var(--color-ink)}
input.condicao::placeholder{color:var(--color-ink-faint)}
/* A QUINTA OPÇÃO mora DENTRO da lista das quatro, e não depois dela. */
.resp label.quinta{align-items:flex-start;flex-direction:column;gap:2px}
.resp .marca{display:none}

/* A RESPOSTA: uma pilha de opções, e a marcada se acende. Um `radio` cru numa
   lista de quatro, quatro vezes na tela, é ruído; a caixa inteira é o alvo. */
.resp{display:flex;flex-direction:column;gap:2px;margin-top:var(--space-3xs)}
.resp label{display:flex;align-items:center;gap:var(--space-3xs);
  font-size:var(--text-sm);padding:var(--space-3xs) var(--space-2xs);
  border:var(--rule-hair) solid transparent;border-radius:var(--radius-sm);
  cursor:pointer;transition:background var(--dur-fast) var(--ease-out)}
.resp label:hover{background:var(--color-paper-3)}
.resp label:has(input:checked){background:var(--color-paper-3);
  border-color:var(--color-rule);font-weight:600}
.resp input{accent-color:var(--realce,var(--color-accent));margin:0}
.ctl .extra{width:100%;font:var(--text-xs)/1.4 var(--font-corpo);
  padding:var(--space-3xs) var(--space-2xs);
  border:var(--rule-hair) solid var(--color-rule);border-radius:var(--radius-sm);
  background:var(--color-paper);color:var(--color-ink);resize:vertical}
.ctl .extra::placeholder{color:var(--color-ink-faint)}

/* O VEREDITO POR CONTROLE — só existe depois do VERIFICAR. */
.laudo{display:none;font-size:var(--text-xs);line-height:1.4;
  padding:var(--space-3xs) var(--space-2xs);border-radius:var(--radius-sm);
  border-left:3px solid var(--sem-julgar)}
body[data-verificado="1"] .laudo{display:block}
.laudo b{display:block;font-size:var(--text-xs);letter-spacing:.06em;
  text-transform:uppercase}
.laudo.v-bate{border-left-color:var(--bate);background:color-mix(in srgb,var(--bate) 12%,transparent)}
.laudo.v-bate b{color:var(--bate)}
.laudo.v-nao-bate{border-left-color:var(--nao-bate);background:color-mix(in srgb,var(--nao-bate) 14%,transparent)}
.laudo.v-nao-bate b{color:var(--nao-bate)}
.laudo.v-sem-julgar{background:var(--color-paper-3)}
.laudo.v-sem-julgar b{color:var(--color-ink-quiet)}

textarea,input[type=text]{width:100%;font:inherit;
  padding:var(--space-2xs) var(--space-xs);
  border:var(--rule-hair) solid var(--color-rule);border-radius:var(--radius-sm);
  background:var(--color-paper-2);color:var(--color-ink);resize:vertical}
textarea:focus,input:focus,.ctl .extra:focus{outline:2px solid var(--color-accent);
  outline-offset:1px;border-color:transparent}
button{font:inherit;padding:var(--space-2xs) var(--space-sm);
  border-radius:var(--radius-sm);cursor:pointer;
  border:var(--rule-hair) solid var(--color-rule);
  background:var(--color-paper-3);color:var(--color-ink);
  transition:background var(--dur-fast) var(--ease-out)}
button:hover:not(:disabled){background:var(--color-rule)}
button.forte{background:var(--color-accent);color:var(--color-paper-2);
  border-color:var(--color-accent);font-weight:600}
button.forte:hover:not(:disabled){filter:brightness(1.1)}
button:disabled{opacity:.4;cursor:not-allowed}
.rodape{display:flex;gap:var(--space-2xs);justify-content:flex-end;
  margin-top:var(--space-sm);flex-wrap:wrap;align-items:center}
.rodape .esquerda{margin-right:auto}
.timer{font:600 var(--text-display)/1 var(--font-dado);text-align:center;
  padding:var(--space-lg) 0;font-variant-numeric:tabular-nums;
  color:var(--color-accent)}
.como{font:var(--text-xs)/1.55 var(--font-dado);
  background:var(--color-paper-2);
  border:var(--rule-hair) solid var(--color-rule);border-radius:var(--radius-sm);
  padding:var(--space-2xs) var(--space-xs);white-space:pre-wrap;
  word-break:break-word;color:var(--color-ink-quiet)}
.como b{color:var(--color-ok);font-weight:600}
.aviso{color:var(--color-alerta);font-size:var(--text-sm);margin:var(--space-2xs) 0 0}

/* O DESENHO CHEGA NO TEMPO 1; A RESPOSTA, SÓ NO 3. As duas coisas moram no
   mesmo cartão que `/desenhos` devolve, e a encomenda dela separa as duas: o
   desenho é *"o que observar"* e tem de estar na tela ANTES (é a instrução);
   a resposta é sobre o que já aconteceu, e marcá-la antes de aplicar é gravar
   uma resposta sobre nada. Por isso o corte é aqui, por tempo, e não no que o
   servidor manda — o cartão é UM só, e montá-lo duas vezes seria dois donos. */
body[data-tempo="1"] .resp, body[data-tempo="2"] .resp{display:none}
/* E A CONDIÇÃO É O CONTRÁRIO: ela se escreve ANTES, some depois. Escrever no
   TEMPO 3 o que era para ter feito no 1 é reescrever a história do teste. */
body[data-tempo="3"] .condicao, body[data-tempo="3"] .condicao-rot{
  pointer-events:none;opacity:.75}

/* ---------------------------------------------------------------------
   UM CONTROLE DE CADA VEZ — vibração, som, microfone.

   Dela, 07/09/2026: *"coisas que eu precisa fazer todos separados um por vez.
   eu só vou pro próximo controle depois de responder o primeiro e no segundo
   coloca um timer explicando o que fazer e o que observar. afinal podemos ter
   4 controles mas só tenho um par de mãos"*.

   Os quatro CONTINUAM na tela — ela precisa ver a fila e o que já respondeu —,
   mas só o da vez recebe clique. Esconder os outros tiraria a única coisa que
   diz onde ela está na sequência.
   --------------------------------------------------------------------- */
/* O ESMAECIMENTO NÃO COME A COR DO PLÁSTICO — medido em 07/09/2026, com
   `opacity:.32` e `saturate(.35)` os quatro viravam cinza e a única coisa que
   ela usa para casar o cartão com o controle na mão sumia da tela. Agora o que
   sai é o CONTRASTE do cartão, e a cor fica. */
body[data-um-por-vez="1"] .ctl{opacity:.62}
body[data-um-por-vez="1"] .ctl[data-vez="1"]{opacity:1;
  outline:2px solid var(--color-accent);outline-offset:2px;
  background:var(--color-paper)}
body[data-um-por-vez="1"] .ctl:not([data-vez="1"]) .resp{pointer-events:none}
body[data-um-por-vez="1"] .ctl.respondido{opacity:.6;filter:none}
body[data-um-por-vez="1"] .ctl.respondido::after{content:"✓ respondido";
  display:block;font-size:var(--text-xs);color:var(--color-ok);font-weight:600}
.a-vez{border-left:3px solid var(--color-accent);padding-left:var(--space-sm);
  margin:var(--space-2xs) 0}
.a-vez b{color:var(--color-accent)}
.fila-dos-quatro{display:flex;gap:var(--space-3xs);align-items:center;
  font-size:var(--text-xs);color:var(--color-ink-quiet)}
.fila-dos-quatro span{padding:1px var(--space-2xs);border-radius:var(--radius-sm);
  border:var(--rule-hair) solid var(--color-rule)}
.fila-dos-quatro span.feito{border-color:var(--color-ok);color:var(--color-ok)}
.fila-dos-quatro span.agora{background:var(--color-accent);
  color:var(--color-paper-2);border-color:var(--color-accent);font-weight:600}

table.indice{width:100%;border-collapse:collapse;font-size:var(--text-sm)}
table.indice td,table.indice th{
  border-bottom:var(--rule-hair) solid var(--color-rule);
  padding:var(--space-3xs) var(--space-2xs);text-align:left;vertical-align:top}
table.indice tr:hover td{background:var(--color-paper-3)}
td.n{width:3rem;font-variant-numeric:tabular-nums;color:var(--color-ink-faint)}
.e-obedeceu{color:var(--color-ok);font-weight:600}
.e-falhou{color:var(--color-alerta);font-weight:600}
.e-parcial{color:var(--color-lacuna);font-weight:600}
.e-nao{color:var(--color-ink-faint)}
a{color:inherit}
.envelope{overflow-x:auto}
"""

_JS = r"""
/* TODOS os testes existem sempre; TESTES é a FATIA que o filtro mostra.
   A página abre em "o que falta" — dela: *"a ideia é ficar fácil pra validarmos
   as teses, a grande maioria ali já foi validada uns 80%"*. Com os 199 numa
   lista só, o que ninguém mediu ficava no meio dos que já estão de pé. */
const TODOS = window.__TESTES__;
const CONFERE = window.__CONFERE__;  // gerada por `confere()`; o JS não a reimplementa
let filtro = 'falta', secaoAtiva = '';
/* DE QUEM É A VEZ, nos testes de um controle de cada vez. `vez` é o índice em
   POSTOS; `respondidos` são os que já têm resposta nesta rodada. */
const POSTOS = ['P1', 'P2', 'P3', 'P4'];
let vez = 0;
let TESTES = TODOS.filter((t) => !t.ja_medido);
let atual = 0, tempo = 1, tique = null, gravado = window.__GRAVADO__ || {};
let desenhado = null;  // o id do teste cujos quatro desenhos estão no ar

const $ = (s, r) => (r || document).querySelector(s);
const esc = (t) => { const d = document.createElement('div'); d.textContent = t == null ? '' : t; return d.innerHTML; };

function ir(i, t) {
  const trocou = TESTES[Math.max(0, Math.min(TESTES.length - 1, i))].id !== (TESTES[atual] || {}).id;
  atual = Math.max(0, Math.min(TESTES.length - 1, i));
  tempo = t || 1;
  if (tique) { clearInterval(tique); tique = null; }
  // TROCOU DE TESTE: os campos do anterior saem AGORA, não só quando o TEMPO 3
  // chegar. Eles estão escondidos no TEMPO 1, e um campo escondido com o texto
  // do teste passado é uma armadilha calada — ela avançaria e salvaria o COMO
  // errado. Régua que provou isto: `test_a_pagina_dirigida_pelo_navegador`.
  if (trocou) { limpar(); vez = 0; }
  location.hash = TESTES[atual].id;
  pintar();
}

function limpar() {
  $('#gesto').value = '';
  $('#aviso').textContent = '';
  // O LAUDO DO TESTE ANTERIOR SAI JUNTO. Um veredito verde herdado do teste
  // passado é pior que nenhum: ele afirma sobre um gesto que não foi aplicado.
  esconderLaudo();
}

function esconderLaudo() {
  document.body.dataset.verificado = '0';
  $('#resumo-do-laudo').textContent = '';
}

/* O COMO QUE O ARQUIVO JÁ PUBLICA, em uma frase por linha. Ela não digita
   isto: `t.como` são os pares que `_como_da_celula()` tirou das colunas
   `canal`, `report_id`, `offset`, `comando`, `codigo_ref` e `teste_que_morde`
   da própria célula do mapa. Se um dia o mapa mudar, o texto muda junto. */
function comoDoArquivo(t) {
  if (!t.como || !t.como.length) {
    return 'o arquivo não publica gesto para esta linha — descreva aqui o que '
         + 'foi aplicado, ou escreva "não apliquei".';
  }
  return t.como.map(([k, v]) => `${k}: ${v}`).join('\n');
}

async function desenhar() {
  // `t` FALTAVA AQUI, e o defeito era mudo: `t.resposta_do_mapa` levantava
  // `ReferenceError` DENTRO de uma função `async`, que vira uma Promise
  // rejeitada e não para nada — a página seguia montada, com os desenhos no
  // lugar, e só a pré-marca sumia. Achado pela régua do "já medido vem
  // pré-marcado", em 07/09/2026.
  const t = TESTES[atual];
  const alvo = $('#desenhos');
  alvo.innerHTML = '<p class="cinza">montando os quatro desenhos…</p>';
  const r = await fetch('/desenhos?teste=' + encodeURIComponent(t.id));
  alvo.innerHTML = await r.text();
  const salvo = gravado[t.id];
  // OS CAMPOS SÃO SEMPRE REESCRITOS, inclusive para o vazio. Defeito medido
  // pela régua nesta leva: eles só eram preenchidos QUANDO havia registro, e o
  // texto do teste anterior ficava na tela — ela avançaria e salvaria o gesto
  // do teste passado como se fosse deste. Um campo que herda o valor do
  // anterior é pior que um campo em branco: ele afirma.
  // O COMO CHEGA PRONTO — e é o ponto: *"isso eu espero que a página
  // descreva"*. Ele sai das colunas da própria célula do mapa, que é onde o
  // repositório já publica o canal, o report, o byte e o arquivo:linha de quem
  // executa. Se ela já corrigiu, a correção DELA ganha — nunca se sobrescreve
  // o que ela escreveu com o texto gerado.
  // O COMO NÃO SE PREENCHE AQUI — quem o faz é o `pintar()`, e é UM só. Isto
  // aqui só devolve o que ELA escreveu e ficou gravado; o texto do arquivo é
  // o piso, e o piso tem dono. (Medido pela mordida em 07/09/2026: com os dois
  // preenchendo, arrancar um deixava a régua verde.)
  if (salvo && salvo.gesto) { $('#gesto').value = salvo.gesto; }
  $('#aviso').textContent = '';
  if (salvo && salvo.respostas) {
    for (const [p, v] of Object.entries(salvo.respostas)) {
      const el = $(`input[name="r-${p}"][value="${v}"]`);
      if (el) el.checked = true;
    }
  } else if (t.resposta_do_mapa) {
    // A RESPOSTA QUE O MAPA IMPLICA, pré-marcada nos quatro — e marcada como
    // VINDA DO MAPA (o tracejado verde), para ela não confundir o que o
    // arquivo afirma com o que ela viu. Ela confirma ou corrige; o que grava
    // é sempre o que estiver na tela quando ela salvar.
    for (const p of ['P1', 'P2', 'P3', 'P4']) {
      const el = $(`input[name="r-${p}"][value="${t.resposta_do_mapa}"]`);
      if (el) { el.checked = true; el.closest('label').classList.add('vindo-do-mapa'); }
    }
  }
  // O CAMPO POR CONTROLE VOLTA JUNTO. Ele é montado por `/desenhos`, logo
  // nasce vazio a cada troca de teste; sem esta volta, ela reabriria um teste
  // já respondido e veria a resposta marcada ao lado de um campo em branco —
  // a tela dizendo que ela não escreveu o que está no disco.
  for (const [p, txt] of Object.entries((salvo && salvo.notas) || {})) {
    const el = $(`textarea[name="n-${p}"]`);
    if (el) el.value = txt;
  }
  // A CONDIÇÃO DE CADA CONTROLE volta igual: ela a escreveu antes do INICIAR,
  // e reabrir o teste sem ela seria perder metade do que o teste era.
  for (const [p, txt] of Object.entries((salvo && salvo.condicoes) || {})) {
    const el = $(`input[name="c-${p}"]`);
    if (el) el.value = txt;
  }
  // A CONDIÇÃO DO ROTEIRO entra nos campos que ela ainda não escreveu. Nas 21
  // linhas ela veio da coluna da §2; nas 127 células do mapa não existe, e o
  // campo fica vazio para ela escrever.
  for (const [p, txt] of Object.entries(t.condicoes || {})) {
    const el = $(`input[name="c-${p}"]`);
    if (el && !el.value.trim()) el.value = txt;
  }
  // E A VEZ SE REPÕE AQUI. Os cartões chegam por `fetch`, e o `pintarAVez` que
  // rodou antes deles não achou `.ctl` nenhum: no TEMPO 1 os quatro ficavam
  // esmaecidos, inclusive o da vez, e a página não mostrava de quem era a vez.
  pintarAVez(t);
  // O SELETOR DE COR guarda na hora, por endereço — ela diz uma vez e a mesa
  // lembra em todos os 148.
  for (const sel of document.querySelectorAll('select.cor')) {
    sel.onchange = async () => {
      await fetch('/cor', {method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({endereco: sel.dataset.endereco, colorway: sel.value})});
      desenhado = null;  // repinta os quatro com a cor nova
      pintar();
    };
  }
}

/* A VEZ, a fila e o texto do que fazer AGORA — só nos testes de um por vez.
   Dela: *"eu só vou pro próximo controle depois de responder o primeiro e no
   segundo coloca um timer explicando o que fazer e o que observar"*. */
function respondeu(posto) {
  return !!$(`input[name="r-${posto}"]:checked`);
}

function pintarAVez(t) {
  const um = !!t.um_por_vez;
  document.body.dataset.umPorVez = um ? '1' : '0';
  $('#a-vez').hidden = !um;
  $('#proximo-controle').hidden = !um || tempo !== 3 || vez >= 3;
  $('#iniciar-txt').textContent = um ? `INICIAR pelo ${POSTOS[vez]}` : 'INICIAR';
  if (!um) {
    for (const c of document.querySelectorAll('.ctl')) {
      c.removeAttribute('data-vez'); c.classList.remove('respondido');
    }
    return;
  }
  const posto = POSTOS[vez];
  $('#fila').innerHTML = POSTOS.map((p, i) =>
    `<span class="${i === vez ? 'agora' : respondeu(p) ? 'feito' : ''}">${p}</span>`
  ).join('');
  const cond = (t.condicoes || {})[posto] || '';
  const papel = (t.papeis || {})[posto] || 'observa';
  const espera = papel === 'reage' ? 'ele DEVE reagir'
               : papel === 'calado' ? 'ele NÃO pode reagir'
               : 'observe e relate o que ele fizer';
  $('#a-vez-txt').innerHTML =
    `<b>Agora é a vez do ${esc(posto)}, e só dele.</b> `
    + (cond ? `O que fazer: ${esc(cond)}. ` : '')
    + `O que observar: ${esc(espera)}. `
    + `Os outros três ficam parados — você tem um par de mãos.`;
  $('#proximo-posto').textContent = POSTOS[Math.min(vez + 1, 3)];
  for (const c of document.querySelectorAll('.ctl')) {
    const p = c.dataset.posto;
    // `setAttribute('data-vez', '1')`, NÃO `toggleAttribute` — este põe o
    // atributo VAZIO (`data-vez=""`), e o CSS casa `[data-vez="1"]`. O
    // resultado, medido navegando com o Playwright em 07/09/2026: o cartão da
    // vez não recebia o realce E CAÍA NA REGRA DOS OUTROS, que tira o clique.
    // A tela mostrava "agora é a vez do P1" e o P1 era o único que ela não
    // conseguia responder. Nenhuma régua de unidade pegaria: o atributo
    // ESTAVA lá, só não com o valor que a folha procura.
    if (p === posto) { c.setAttribute('data-vez', '1'); }
    else { c.removeAttribute('data-vez'); }
    c.classList.toggle('respondido', p !== posto && respondeu(p));
  }
}

function pintar() {
  const t = TESTES[atual];
  document.body.dataset.tempo = String(tempo);
  $('#contador').textContent = `teste ${atual + 1} de ${TESTES.length}`;
  $('#antes').hidden = tempo !== 1;
  $('#contagem').hidden = tempo !== 2;
  $('#depois').hidden = tempo !== 3;

  // A CAPA É PINTADA NOS TRÊS TEMPOS, e não só no 1. Ela estava dentro do
  // `if (tempo === 1)`, então no TEMPO 3 — a hora de julgar — a tela não
  // dizia mais o que era para ter acontecido nem o que fazia o teste passar.
  $('#secao').textContent = t.secao;
  $('#contador-capa').textContent = `teste ${atual + 1} de ${TESTES.length}`;
  $('#titulo').textContent = t.titulo;
  // O "O QUE VAI ACONTECER" SOME QUANDO REPETE O TÍTULO. Nas 21 linhas do
  // roteiro os dois campos saem da MESMA frase do arquivo, e a capa mostrava a
  // mesma sentença duas vezes seguidas — ruído puro, e ruído que ensina a
  // pular a leitura. Nas 127 células do mapa eles diferem, e aí os dois valem.
  const repete = (t.vai_acontecer || '').trim() === (t.titulo || '').trim();
  $('#vai-acontecer').textContent = repete ? '' : t.vai_acontecer;
  $('#vai-acontecer').hidden = repete;
  $('#passa-quando').textContent = t.passa_quando;
  pintarAVez(t);
  // O COMO VEM PRONTO, e é pintado AQUI e não no `desenhar()`: aquele só roda
  // quando o teste muda, e este campo é reescrito a cada tempo. Medido
  // navegando com o Playwright em 07/09/2026: ele chegava VAZIO ao TEMPO 3, e
  // ela veria de novo a cobrança que a fez dizer *"isso aqui me quebra"*.
  // O que ela escreveu ganha de tudo; o do arquivo só preenche o vazio.
  if (!$('#gesto').value.trim()) { $('#gesto').value = comoDoArquivo(t); }
  $('#selo').classList.toggle('vazio', !t.ja_medido);
  $('#selo-txt').textContent = t.ja_medido || '';
  $('#contador').textContent =
    `${TESTES.length} ${filtro === 'medido' ? 'já medidos' : filtro === 'tudo' ? 'no total' : 'a medir'}`;

  if (tempo === 1) {
    $('#observar').innerHTML = ['P1', 'P2', 'P3', 'P4'].map((p) => {
      const papel = t.papeis[p];
      const diz = papel === 'reage' ? 'DEVE REAGIR' : papel === 'calado' ? 'não pode reagir' : 'observe e relate';
      return `<div class="linha-obs"><b>${p}</b><span class="papel-tag t-${papel}">${diz}</span></div>`;
    }).join('');
    $('#celula').textContent = t.celula;
    $('#hoje').textContent = t.hoje;
    $('#pecas').innerHTML = t.pecas.length
      ? t.pecas.map(([id, palavra]) => `<code>${esc(id)}</code> <span class="cinza">(pela palavra “${esc(palavra)}”)</span>`).join(' · ')
      : '<span class="cinza">esta linha não nomeia peça nenhuma nos arquivos — os quatro desenhos ficam neutros, e isso é dito em vez de inventado.</span>';
    $('#como-do-arquivo').innerHTML = t.como.length
      ? t.como.map(([k, v]) => `<b>${esc(k)}:</b> ${esc(v)}`).join('\n')
      : '<span class="cinza">o arquivo não publica gesto para esta linha — o campo do “como” é a única fonte.</span>';
    $('#segundos-alvo').textContent = t.segundos;
  }
  // O DESENHO SEGUE O TESTE, NÃO O TEMPO. Buscar de novo a cada tempo do
  // MESMO teste custaria ~200 KB por transição e faria a peça acesa PISCAR no
  // meio da leitura dela; `desenhado` é o que impede as duas coisas.
  if (desenhado !== t.id) { desenhado = t.id; desenhar(); }
  indice();
}

/* A CONTAGEM, separada do INICIAR — porque ela roda DUAS vezes: quando o teste
   começa, e de novo a cada troca de controle nos testes de um por vez. Com o
   relógio preso dentro do `iniciar()`, o segundo controle começaria sem timer,
   e o timer é justamente o que dá a ela o tempo de tirar os olhos da tela. */
function contar(segundos) {
  if (tique) { clearInterval(tique); tique = null; }
  let resta = segundos;
  const mostra = () => {
    const m = Math.floor(resta / 60), s = resta % 60;
    $('#relogio').textContent = m > 0 ? `${m}:${String(s).padStart(2, '0')}` : String(s);
  };
  mostra();
  tique = setInterval(() => {
    resta -= 1;
    mostra();
    if (resta <= 0) {
      clearInterval(tique); tique = null;
      // NÃO chama `ir()`: nos testes de um por vez isso zeraria a vez e
      // devolveria a rodada ao P1. Só o TEMPO muda.
      tempo = 3;
      pintar();
    }
  }, 1000);
}

function iniciar() {
  vez = 0;
  tempo = 2;
  pintar();
  contar(TESTES[atual].segundos);
}

/* O VERIFICAR — pedido dela: *"após responder e clicar em verificar ele mostra
   se deu certo ou errado pra cada controle"*.

   A REGRA NÃO MORA AQUI. Ela é de `confere()` em `mesa_de_medicao.py`, e chega
   como DADO em `window.__CONFERE__`. Reimplementá-la em JavaScript daria duas
   cópias da mesma decisão, e a segunda divergiria no dia em que a primeira
   fosse corrigida — que é o defeito que esta casa mais caça. */
function verificar() {
  const t = TESTES[atual];
  let bate = 0, naoBate = 0, semJulgar = 0, semResposta = 0;
  for (const p of ['P1', 'P2', 'P3', 'P4']) {
    const el = $(`input[name="r-${p}"]:checked`);
    const resposta = el ? el.value : '';
    const papel = t.papeis[p] || 'observa';
    const par = (CONFERE[papel] || {})[resposta] || ['sem-julgar', 'sem resposta'];
    // A VARIÁVEL SE CHAMA `laudo` POR CAUSA DE UMA RÉGUA, e não por gosto:
    // `test_todo_estado_que_o_indice_pinta_e_alcancavel` descobre os estados
    // do ÍNDICE varrendo o texto deste arquivo atrás da comparação que o
    // índice faz, e os três estados daqui caíam na mesma peneira. Duas
    // famílias de estado, dois nomes de variável.
    //
    // E ESTE COMENTÁRIO NÃO ESCREVE O PADRÃO QUE ELA PROCURA, de propósito:
    // a primeira versão dele o citava, virou a primeira ocorrência do arquivo
    // e a régua reprovou de novo — pelo AVISO, não pelo defeito. É a mesma
    // armadilha que o `CLAUDE.md` registra de 05/09/2026, e ela pega igual.
    const laudo = par[0], frase = par[1];
    if (!resposta) semResposta++;
    else if (laudo === 'bate') bate++;
    else if (laudo === 'nao-bate') naoBate++;
    else semJulgar++;
    const alvo = $(`#laudo-${p}`);
    if (!alvo) continue;
    alvo.className = 'laudo v-' + laudo;
    const carimbo = laudo === 'bate' ? '\u2713 bate com o esperado'
      : laudo === 'nao-bate' ? '\u2717 NÃO bate com o esperado'
      : '— sem julgar';
    alvo.innerHTML = `<b>${esc(carimbo)}</b>${esc(frase)}`;
  }
  document.body.dataset.verificado = '1';
  const partes = [];
  if (bate) partes.push(`${bate} bate${bate > 1 ? 'm' : ''}`);
  if (naoBate) partes.push(`${naoBate} NÃO bate${naoBate > 1 ? 'm' : ''}`);
  if (semJulgar) partes.push(`${semJulgar} sem julgar`);
  if (semResposta) partes.push(`${semResposta} sem resposta`);
  $('#resumo-do-laudo').textContent = partes.join(' · ');
  return {bate, naoBate, semJulgar, semResposta};
}

async function salvar(avanca) {
  const t = TESTES[atual];
  const respostas = {}, notas = {}, condicoes = {};
  for (const p of ['P1', 'P2', 'P3', 'P4']) {
    const cond = $(`input[name="c-${p}"]`);
    if (cond && cond.value.trim()) condicoes[p] = cond.value.trim();
    const el = $(`input[name="r-${p}"]:checked`);
    if (el) respostas[p] = el.value;
    // O CAMPO POR CONTROLE VAI PARA O DISCO. Um campo que a tela mostra e o
    // registro não guarda é pior que campo nenhum: ela escreve achando que
    // ficou gravado.
    const nota = $(`textarea[name="n-${p}"]`);
    if (nota && nota.value.trim()) notas[p] = nota.value.trim();
  }
  // O COMO NÃO É COBRADO DELA — 07/09/2026: *"isso aqui me quebra. isso eu
  // espero que a página descreva"*. Se o campo estiver vazio, a página põe o
  // do arquivo e segue. A recusa do servidor continua de pé para o caso em que
  // NEM o arquivo tem o que dizer — e aí é defeito da página, não falta dela.
  const gesto = $('#gesto').value.trim() || comoDoArquivo(t);
  $('#aviso').textContent = '';
  const mesa = await (await fetch('/mesa')).json();
  const r = await fetch('/registro', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      teste: t.id, secao: t.secao, titulo: t.titulo, celula: t.celula,
      respostas, notas, condicoes, o_que_eu_vi: '', gesto,
      como_do_arquivo: t.como, mesa, papeis: t.papeis,
    }),
  });
  if (!r.ok) { $('#aviso').textContent = 'não gravou: ' + (await r.text()); return; }
  gravado[t.id] = await r.json();
  if (avanca) {
    if (atual + 1 >= TESTES.length) { document.getElementById('indice').scrollIntoView(); ir(atual, 3); }
    else ir(atual + 1, 1);
  } else pintar();
}

function indice() {
  const porSecao = {};
  TESTES.forEach((t, i) => { (porSecao[t.secao] = porSecao[t.secao] || []).push([i, t]); });
  $('#indice-corpo').innerHTML = Object.entries(porSecao).map(([secao, itens]) => {
    const linhas = itens.map(([i, t]) => {
      const g = gravado[t.id];
      const v = g ? g.veredito : 'não feito';
      const cls = v === 'obedeceu' ? 'e-obedeceu' : v === 'falhou' ? 'e-falhou' : v === 'parcial' ? 'e-parcial' : 'e-nao';
      return `<tr><td class="n">${i + 1}</td><td><a href="#" data-ir="${i}">${esc(t.titulo)}</a>
        <div class="cinza">${esc(t.celula)}</div></td><td class="${cls}">${v}</td></tr>`;
    }).join('');
    const feitos = itens.filter(([, t]) => gravado[t.id]).length;
    return `<h3>${esc(secao)} — ${feitos} de ${itens.length}</h3>
      <div class="envelope"><table class="indice"><tbody>${linhas}</tbody></table></div>`;
  }).join('');
  $('#indice-corpo').querySelectorAll('[data-ir]').forEach((a) => {
    a.onclick = (e) => { e.preventDefault(); ir(Number(a.dataset.ir), 1); window.scrollTo(0, 0); };
  });
}

async function mesaViva() {
  try {
    const m = await (await fetch('/mesa')).json();
    $('#daemon').textContent = m.daemon;
  } catch (e) { $('#daemon').textContent = 'a página perdeu o servidor'; }
}

/* O FILTRO. Ele troca a FATIA e reancora no teste que estava aberto, se ele
   sobreviver ao corte — senão volta ao primeiro. Cair no teste 1 a cada clique
   faria o filtro custar mais do que resolve. */
/* AS SEÇÕES, contadas no ESTADO ATUAL do filtro. Uma lista que diz "áudio 16"
   quando o filtro já é "só o que falta" e sobram 3 mandaria ela abrir uma
   gaveta quase vazia. */
function montarSecoes() {
  const base = filtro === 'tudo' ? TODOS
             : filtro === 'medido' ? TODOS.filter((t) => t.ja_medido)
             : TODOS.filter((t) => !t.ja_medido);
  const conta = new Map();
  for (const t of base) conta.set(t.secao, (conta.get(t.secao) || 0) + 1);
  const sel = $('#secao-filtro');
  const ordem = [...conta.keys()].sort((a, b) => {
    // O ROTEIRO PRIMEIRO, sempre: ele é a aceitação do produto, e a hora dela
    // com os quatro controles vale mais que qualquer família do mapa.
    const r = (s) => (s.startsWith('O roteiro') ? 0 : 1);
    return r(a) - r(b) || a.localeCompare(b, 'pt-BR');
  });
  sel.innerHTML = `<option value="">todas as seções (${base.length})</option>`
    + ordem.map((s) => `<option value="${esc(s)}"${s === secaoAtiva ? ' selected' : ''}>`
        + `${esc(s)} (${conta.get(s)})</option>`).join('');
}

function filtrar(qual, secao) {
  const antes = (TESTES[atual] || {}).id;
  filtro = qual;
  if (secao !== undefined) secaoAtiva = secao;
  TESTES = (qual === 'tudo' ? TODOS
         : qual === 'medido' ? TODOS.filter((t) => t.ja_medido)
         : TODOS.filter((t) => !t.ja_medido))
         .filter((t) => !secaoAtiva || t.secao === secaoAtiva);
  if (!TESTES.length) {
    // NUNCA UMA FILA VAZIA: um corte que não sobra nada tira a página do ar
    // sem dizer por quê. Solta a seção primeiro, depois o estado.
    secaoAtiva = '';
    TESTES = TODOS.filter((t) => qual === 'tudo' || (qual === 'medido') === !!t.ja_medido);
    if (!TESTES.length) { TESTES = TODOS; filtro = 'tudo'; }
  }
  montarSecoes();
  for (const b of document.querySelectorAll('.filtro button')) {
    b.classList.toggle('ligado', b.id === 'f-' + filtro);
  }
  const volta = TESTES.findIndex((t) => t.id === antes);
  desenhado = null;
  ir(volta >= 0 ? volta : 0, 1);
}

window.addEventListener('DOMContentLoaded', () => {
  $('#f-falta').onclick = () => filtrar('falta');
  $('#f-medido').onclick = () => filtrar('medido');
  $('#f-tudo').onclick = () => filtrar('tudo');
  $('#secao-filtro').onchange = (e) => filtrar(filtro, e.target.value);
  /* LER A COR NOS CONTROLES. É a única coisa que esta página escreve no
     aparelho, e por isso é um clique dela e não um tique: um `SET_FEATURE
     0x80` pedindo o serial de fábrica, o mesmo que o daemon manda uma vez por
     sessão. O botão se desabilita enquanto lê — quatro pedidos seguidos ao
     mesmo aparelho por um duplo clique é o que ele não precisa receber. */
  $('#ler-cor').onclick = async () => {
    const b = $('#ler-cor'), r = $('#recado-da-cor');
    b.disabled = true;
    r.textContent = 'perguntando aos controles…';
    try {
      const resp = await fetch('/ler-cor', {method: 'POST'});
      const d = await resp.json();
      const lidos = Object.values(d.lidos || {});
      const erros = Object.entries(d.erros || {});
      r.textContent = lidos.length
        ? `${lidos.length} lido(s): ` + lidos.map((c) => c.nome).join(' · ')
          + (erros.length ? ` — ${erros.length} não respondeu` : '')
        : (erros.length ? `nenhum respondeu: ${erros[0][1]}`
                        : 'nenhum DualSense na mesa agora');
      if (lidos.length) { desenhado = null; await desenhar(); pintar(); }
    } catch (e) {
      r.textContent = 'não deu para ler: ' + e;
    } finally { b.disabled = false; }
  };
  montarSecoes();
  $('#iniciar').onclick = iniciar;
  $('#pular-timer').onclick = () => {
    if (tique) { clearInterval(tique); tique = null; }
    tempo = 3;
    pintar();
  };
  $('#voltar').onclick = () => ir(atual, 1);
  $('#anterior').onclick = () => ir(atual - 1, 1);
  $('#salvar').onclick = () => salvar(true);
  $('#so-salvar').onclick = () => salvar(false);
  $('#verificar').onclick = verificar;
  /* RESPONDER E IR AO PRÓXIMO. Ele não pula direto ao cartão seguinte: volta
     ao TIMER, que é onde a página explica o que fazer e o que observar NAQUELE
     controle. Foi o pedido dela, com todas as letras: *"no segundo coloca um
     timer explicando o que fazer e o que observar"*. */
  $('#proximo-controle').onclick = () => {
    const t = TESTES[atual];
    const posto = POSTOS[vez];
    if (!respondeu(posto)) {
      $('#aviso').textContent =
        `Responda o ${posto} antes de ir ao ${POSTOS[vez + 1]} — é ele que `
        + `está sendo medido agora.`;
      return;
    }
    $('#aviso').textContent = '';
    vez = Math.min(vez + 1, 3);
    tempo = 2;
    pintar();
    contar(t.segundos);
  };
  const alvo = TESTES.findIndex((t) => t.id === location.hash.slice(1));
  ir(alvo >= 0 ? alvo : 0, 1);
  mesaViva();
  setInterval(mesaViva, 4000);
});
"""


def pagina(testes: list[Teste], gravado: dict[str, Any]) -> str:
    """A página inteira. Ela é MONTADA A CADA `GET /`, nunca guardada em disco.

    Assim ela nunca envelhece: mudou o CSV, o próximo `F5` já mostra a mesa
    nova. Um HTML publicado seria a cópia que diverge da fonte sem ninguém ver —
    que foi o que aconteceu com a pasta do mockup, e ela mandou aposentá-la.
    """
    dados = json.dumps([t.para_json() for t in testes], ensure_ascii=False)
    salvos = json.dumps(gravado, ensure_ascii=False)
    # A REGRA DO VERIFICAR VIAJA COMO DADO, gerada por `confere()`. O JS a
    # consulta e não a reimplementa — duas cópias divergiriam.
    confere_json = json.dumps(tabela_de_conferencia(), ensure_ascii=False)
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>A mesa de medição — os quatro DualSense</title>
<style>{_CSS}</style>
{monta.folha_das_cores()}
<style>{monta.folha_de_realce()}</style>
<!-- O CONTORNO DO DESENHO, na cor do plástico, lido do mapa do controle. -->
<style>{folha_do_desenho([x.lower() for x in POSTOS])}</style>
</head><body>
<header>
  <b>A mesa de medição</b>
  <!-- O FILTRO — 07/09/2026, pedido dela: a página abre no que FALTA, e o que
       já foi medido fica a um clique, com a resposta do mapa pré-marcada. -->
  <span class="filtro">
    <button id="f-falta" class="ligado">o que falta</button>
    <button id="f-medido">já medido</button>
    <button id="f-tudo">tudo</button>
  </span>
  <!-- O SELETOR DE SEÇÃO — 07/09/2026, dela: *"o prioritários (…) faço eles e
       na sequência vou fazendo os demais"*. Uma fila de 148 não se ataca de
       uma vez; ela escolhe uma seção, fecha, e vai para a próxima. O roteiro
       vem primeiro na lista porque é a ACEITAÇÃO do produto, não uma seção
       qualquer do mapa. -->
  <select id="secao-filtro" title="a fila de uma seção por vez"></select>
  <!-- A ÚNICA ESCRITA NO APARELHO, e ela é ATO DELA — nunca automática. Ver a
       docstring de `ler_a_cor_no_aparelho`. -->
  <button id="ler-cor" title="pergunta o serial de fábrica a cada controle e
    tira a cor dele; é a única coisa que esta página escreve no aparelho">
    ler a cor nos controles</button>
  <span class="cinza" id="recado-da-cor"></span>
  <span class="cinza" id="contador"></span>
  <span class="cinza" id="daemon">lendo o daemon…</span>
  <span class="cinza">o registro vai para {_e(pasta_do_registro())}</span>
</header>
<main>
  <div class="cartao">

    <!-- O TOPO EXPLICA O QUE ESTÁ SENDO TESTADO, e vem ANTES de tudo — pedido
         dela: *"começa na parte superior explicando o que está sendo testado e
         afins"*. Até 06/09/2026 o título vinha sozinho e o "o que vai
         acontecer" ficava DEPOIS dos quatro desenhos, dentro da seção do
         TEMPO 1: ela via os controles antes de saber para quê, e no TEMPO 3 a
         explicação sumia da tela justamente quando ela ia julgar. Agora a capa
         está sempre visível, nos três tempos. -->
    <div class="capa">
      <div class="fita">
        <span id="secao"></span>
        <span>·</span>
        <span id="contador-capa"></span>
        <span class="selo vazio" id="selo">&#10003; <span id="selo-txt"></span></span>
      </div>
      <h2 id="titulo"></h2>
      <p class="frase" id="vai-acontecer"></p>
      <p class="quando"><b>passa quando</b> <span id="passa-quando"></span></p>
      <!-- A FAIXA DA VEZ — só aparece nos testes de um controle de cada vez. -->
      <div class="a-vez" id="a-vez" hidden>
        <div class="fila-dos-quatro" id="fila"></div>
        <p id="a-vez-txt"></p>
      </div>
    </div>

    <!-- OS QUATRO DESENHOS FICAM FORA DAS TRÊS SEÇÕES, e é o pedido dela:
         *"em cada controle eu devo observar algo. Faça os svgs brilharem
         mostrando o que observar de cada controle em cada rodada"*. Eles
         nasceram dentro do TEMPO 3, e ali chegavam TARDE: ela lia o que fazer,
         apertava INICIAR e ia mexer no aparelho SEM NUNCA TER VISTO onde
         olhar. O desenho é a instrução, não o recibo — por isso ele está no
         ar nos três tempos, com a mesma peça acesa do começo ao fim. -->
    <div id="desenhos"></div>

    <section id="antes" hidden>
      <div class="rodape">
        <span class="esquerda cinza" id="pecas"></span>
        <button id="anterior">&larr; anterior</button>
        <button id="iniciar" class="forte">&#9654; <span id="iniciar-txt">INICIAR</span>
          (<span id="segundos-alvo"></span>s)</button>
      </div>
      <details>
        <summary class="cinza">a célula que isto fecha, e o COMO que o arquivo já publica</summary>
        <p><code id="celula"></code><br><span class="cinza" id="hoje"></span></p>
        <div class="como" id="como-do-arquivo"></div>
      </details>
    </section>

    <section id="contagem" hidden>
      <h3>Tire os olhos da tela e ponha nos controles</h3>
      <div class="timer" id="relogio">&mdash;</div>
      <div class="rodape"><button id="pular-timer">já passou &rarr;</button></div>
    </section>

    <section id="depois" hidden>
      <!-- O CAMPO "no conjunto" SAIU — 07/09/2026, palavra dela: *"esse
           segundo campo não é eu quem deve responder. O que eu vi no conjunto
           não deve existir assim, demos 4 opções pra cada controle uma 5
           deveria ser um campo pra eu descrever por controle o que ocorreu"*.
           Ele pedia dela uma síntese dos quatro que a mesa já tem — as quatro
           respostas somadas SÃO o conjunto —, e cobrar de novo em prosa é
           trabalho dobrado. O que ela escreve fica no campo de cada controle,
           que é a quinta opção da lista de lá. -->
      <h3>O COMO — de onde este teste sai, e como se aplica</h3>
      <p class="cinza">Vem pronto dos arquivos: as colunas da própria célula do
        mapa. <b>Não é para você digitar.</b> Corrija só se estiver errado.</p>
      <textarea id="gesto" rows="3"></textarea>
      <p class="aviso" id="aviso"></p>
      <div class="rodape">
        <span class="esquerda cinza" id="resumo-do-laudo"></span>
        <button id="voltar">&larr; voltar</button>
        <button id="verificar">verificar</button>
        <button id="so-salvar">salvar e ficar</button>
        <button id="proximo-controle" class="forte" hidden>
          responder e ir ao <span id="proximo-posto"></span> &rarr;</button>
        <button id="salvar" class="forte">salvar e avançar &rarr;</button>
      </div>
      <details>
        <summary class="cinza">o que o roteiro esperava de cada um</summary>
        <div id="observar"></div>
      </details>
    </section>
  </div>

  <div class="cartao" id="indice">
    <h2>O índice, por seção</h2>
    <div id="indice-corpo"></div>
  </div>
</main>
<script>
window.__TESTES__ = {dados};
window.__GRAVADO__ = {salvos};
window.__CONFERE__ = {confere_json};
</script>
<script>{_JS}</script>
</body></html>"""


def cartoes(teste: Teste, mesa: dict[str, Any]) -> str:
    """Os quatro cartões: desenho, quem é, a CONDIÇÃO, as respostas e o campo.

    A COLUNA É UMA PILHA, na ordem em que ela olha: o desenho com a peça acesa,
    quem é o controle (com o seletor de cor), a condição que ELA escreveu para
    este controle neste teste, as quatro respostas, o campo de texto que é a
    quinta, e o laudo do VERIFICAR.

    O QUE MUDOU EM 07/09/2026, e veio dela inteiro:

    * *"cada controle sirva para testarmos variações daquilo e o esperado (…)
      Controle A, não liga, o b cor azul. o c, tá conectado no rosa, o y vai
      conectar azul"* — cada controle é uma CONDIÇÃO do mesmo experimento, não
      um papel. A condição é escrita por ela antes do INICIAR e viaja com o
      registro;
    * *"demos 4 opções pra cada controle uma 5 deveria ser um campo pra eu
      descrever por controle o que ocorreu"* — o campo de texto é a QUINTA
      opção, dentro da mesma lista, e não um apêndice;
    * *"não esquece da cor dos plasticos e dos botões e área igual a página do
      mapa do controle"* — o desenho é o mesmo `monta.svg` do mapa, com as dez
      zonas pintadas pelo CSV dela. Quando o daemon está parado a cor não se lê
      sem escrever no aparelho, então o seletor deixa ELA dizer, e a mesa
      lembra pelo endereço.

    A LUZ DE JOGADOR ENTRA NA IDENTIFICAÇÃO — pedido dela: *"lá tem o led do
    player, o led que fica aceso também e afins"*. O desenho mostra qual lâmpada
    está acesa em cada um, e é assim que ela casa o cartão da tela com o
    plástico na mesa.
    """
    svgs = desenhos(teste, mesa)
    postos = (mesa or {}).get("postos") or {}
    cores = sorted(nomes_dos_colorways().items(), key=lambda x: x[1])
    blocos = []
    for posto in POSTOS:
        vivo = postos.get(posto) or {}
        papel = teste.papeis.get(posto, PAPEL_OBSERVA)
        bateria = vivo.get("bateria")
        estado = str(vivo.get("estado_da_bateria") or "")
        carga = {"charging": "carregando", "full": "cheia",
                 "discharging": "na bateria"}.get(estado, estado)
        transporte = vivo.get("transporte") or "sem transporte"
        meta = " · ".join(x for x in (
            transporte,
            f"{bateria}%" if isinstance(bateria, (int, float)) else "bateria —",
            carga,
            f'lâmpada {vivo["lampada"]}' if vivo.get("lampada") else "lâmpada —",
        ) if x)
        atual = str(vivo.get("colorway") or "")
        opcoes = "".join(
            f'<option value="{_e(slug)}"'
            f'{" selected" if slug == atual else ""}>{_e(nome)}</option>'
            for slug, nome in cores)
        # O NOME DO PLÁSTICO É TEXTO; o seletor de 28 fica DENTRO de um
        # `<details>`. Com ele aberto o tempo todo, as 28 opções entravam no
        # texto do cartão quatro vezes e o nome do modelo — a única linha que
        # ela lê para casar a tela com o controle na mão — sumia no meio.
        nome_da_cor = nome_do_colorway(atual)
        seletor = (
            f'<div class="nome">{_e(nome_da_cor or "cor não lida")}</div>'
            f'<details class="troca-cor">'
            f'<summary>{"trocar a cor" if nome_da_cor else "dizer qual é a cor"}</summary>'
            f'<select class="cor" data-posto="{posto}" '
            f'data-endereco="{_e(vivo.get("uniq") or "")}"'
            f'{"" if vivo.get("presente") else " disabled"}>'
            f'<option value="">—</option>{opcoes}</select>'
            f'</details>')
        respostas = "".join(
            f'<label><input type="radio" name="r-{posto}" value="{v}">'
            f'<span>{_e(rot)}</span></label>'
            for v, rot in RESPOSTAS)
        # A BORDA DO CARTÃO É A COR DO PLÁSTICO — pedido dela, 07/09/2026:
        # *"a borda de cada controle deve ter a borda na cor do model"*. O hex
        # se PERGUNTA a `monta.cor_da_zona`, que é o dono do par colorway/zona
        # e lê o CSV dela; digitá-lo aqui seria a segunda tabela das 28 cores.
        # Sem cor lida, a borda fica na régua neutra e o cartão diz por quê.
        casca = monta.cor_da_zona(atual, "casca-solida") if atual else ""
        estilo = f' style="--cor-do-modelo:{casca}"' if casca else ""
        blocos.append(
            f'<div class="ctl papel-{papel}" data-posto="{posto}"{estilo}>'
            f'{svgs[posto]}'
            f'<div class="quem">'
            f'<b class="posto">{_e(posto)}</b>'
            f'<span class="meta">{_e(meta)}</span>'
            f'</div>'
            f'{seletor}'
            f'<div class="meta ender">{_e(vivo.get("uniq") or "sem endereço")}</div>'
            # A CONDIÇÃO DESTE CONTROLE NESTE TESTE — escrita por ela, e por
            # isso um campo, não um rótulo. É o que faz os quatro medirem
            # coisas DIFERENTES em vez de repetirem o mesmo gesto quatro vezes.
            f'<label class="condicao-rot" for="cond-{posto}">O que fazer neste</label>'
            f'<input class="condicao" id="cond-{posto}" name="c-{posto}" '
            f'type="text" placeholder="ex.: não liga · cor azul · já está no rosa">'
            f'<div class="resp">{respostas}'
            # A QUINTA OPÇÃO, dentro da lista: ela pediu *"uma 5 deveria ser um
            # campo pra eu descrever por controle o que ocorreu"*.
            f'<label class="quinta"><span class="marca">5</span>'
            f'<textarea class="extra" name="n-{posto}" rows="2" '
            f'placeholder="Ou descreva o que ocorreu neste"></textarea></label>'
            f'</div>'
            f'<div class="laudo" id="laudo-{posto}"></div>'
            f'</div>')
    return f'<div class="quatro">{"".join(blocos)}</div>'


# ---------------------------------------------------------------------------
# O servidor
# ---------------------------------------------------------------------------
class Mesa:
    """O estado do processo: os testes, o registro e a mesa viva."""

    def __init__(self, registro: Registro | None = None) -> None:
        self.testes = todos_os_testes()
        self.por_id = {t.id: t for t in self.testes}
        self.registro = registro or Registro()


class _Atendente(BaseHTTPRequestHandler):
    mesa: Mesa

    server_version = "MesaDeMedicao/1"

    def log_message(self, formato: str, *args: Any) -> None:
        """Silêncio no terminal DELA. Saída de comando vai para arquivo — foi
        assim que a sessão de 02/09 quebrou, e o terminal é o mesmo em que a
        conversa acontece."""

    def _responder(self, corpo: bytes, tipo: str, codigo: int = 200) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self) -> None:
        caminho = self.path.split("?", 1)[0]
        if caminho == "/":
            corpo = pagina(self.mesa.testes, self.mesa.registro.ler())
            self._responder(corpo.encode("utf-8"), "text/html; charset=utf-8")
        elif caminho == "/mesa":
            self._responder(
                json.dumps(quem_esta_na_mesa(), ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8")
        elif caminho == "/desenhos":
            pedido = self.path.split("?", 1)[1] if "?" in self.path else ""
            alvo = dict(
                p.split("=", 1) for p in pedido.split("&") if "=" in p
            ).get("teste", "")
            from urllib.parse import unquote
            teste = self.mesa.por_id.get(unquote(alvo))
            if teste is None:
                self._responder(b"teste desconhecido", "text/plain; charset=utf-8", 404)
                return
            self._responder(
                cartoes(teste, quem_esta_na_mesa()).encode("utf-8"),
                "text/html; charset=utf-8")
        elif caminho == "/estado":
            self._responder(
                json.dumps(self.mesa.registro.ler(), ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8")
        else:
            self._responder("não existe".encode(),
                            "text/plain; charset=utf-8", 404)

    def do_POST(self) -> None:
        caminho = self.path.split("?", 1)[0]
        if caminho not in ("/registro", "/cor", "/ler-cor"):
            self._responder("não existe".encode(),
                            "text/plain; charset=utf-8", 404)
            return
        tamanho = int(self.headers.get("Content-Length") or 0)
        cru = self.rfile.read(tamanho).decode("utf-8") if tamanho else ""
        # CORPO VAZIO É VÁLIDO, e `/ler-cor` é justamente assim: ele não leva
        # dado nenhum, só a ordem dela. `json.loads("")` levanta, e o erro saía
        # como texto puro num canal que o navegador lê como JSON — o recado que
        # chegava à tela era `Unexpected token 'E'`, que não diz nada a
        # ninguém. Medido clicando o botão, em 07/09/2026.
        try:
            item = json.loads(cru) if cru.strip() else {}
        except ValueError as erro:
            self._responder(
                json.dumps({"erro": str(erro)}, ensure_ascii=False).encode(),
                "application/json; charset=utf-8", 400)
            return
        if caminho == "/ler-cor":
            # A ÚNICA ESCRITA NO APARELHO QUE ESTA PÁGINA FAZ, e ela chega por
            # um POST porque é ATO DELA: um GET seria disparado por um F5.
            self._responder(
                json.dumps(ler_a_cor_no_aparelho(), ensure_ascii=False).encode(),
                "application/json; charset=utf-8")
            return
        if caminho == "/cor":
            # A COR QUE ELA DISSE, por endereço. É a única coisa que esta
            # página guarda sobre o APARELHO em vez de sobre a medição, e ela
            # existe porque a cor não se lê sem escrever no controle — o que
            # esta página não faz. O endereço chega já mascarado do navegador e
            # é mascarado de novo aqui: o que vem de fora não é de confiança.
            tudo = guardar_cor_dela(_mascarar(str(item.get("endereco") or "")),
                                    str(item.get("colorway") or ""))
            self._responder(json.dumps(tudo, ensure_ascii=False).encode("utf-8"),
                            "application/json; charset=utf-8")
            return
        item["veredito"] = veredito(item.get("respostas") or {})
        try:
            linha = self.mesa.registro.gravar(item)
        except ValueError as erro:
            self._responder(str(erro).encode("utf-8"),
                            "text/plain; charset=utf-8", 400)
            return
        self._responder(json.dumps(linha, ensure_ascii=False).encode("utf-8"),
                        "application/json; charset=utf-8")


def servir(porta: int = 0) -> tuple[ThreadingHTTPServer, str]:
    """Sobe o servidor em `127.0.0.1` e devolve o endereço.

    **`127.0.0.1`, nunca `0.0.0.0`.** Esta página mostra o endereço dos
    controles dela e o que a bancada mediu; um servidor que atende a rede
    inteira publicaria isso para quem estivesse no mesmo Wi-Fi.
    """
    _Atendente.mesa = Mesa()
    httpd = ThreadingHTTPServer(("127.0.0.1", porta), _Atendente)
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


def censo() -> str:
    """O retrato dos testes, sem servir nada. É o que a régua lê."""
    testes = todos_os_testes()
    por_secao: dict[str, int] = {}
    for t in testes:
        por_secao[t.secao] = por_secao.get(t.secao, 0) + 1
    com_peca = sum(1 for t in testes if t.pecas)
    linhas = [
        f"testes: {len(testes)}",
        f"com peça a acender: {com_peca}",
        f"seções: {len(por_secao)}",
        "",
    ]
    linhas += [f"  {n:>4}  {s}" for s, n in sorted(por_secao.items())]
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    p.add_argument("--servir", action="store_true", help="sobe o servidor")
    p.add_argument("--porta", type=int, default=0, help="a porta (0 = livre)")
    p.add_argument("--censo", action="store_true", help="o retrato, rc=0")
    p.add_argument("--pagina", metavar="ARQUIVO",
                   help="escreve a página num arquivo e sai (para a régua)")
    args = p.parse_args(argv)

    if args.censo:
        print(censo())
        return 0
    if args.pagina:
        alvo = pathlib.Path(args.pagina)
        alvo.write_text(pagina(todos_os_testes(), Registro().ler()),
                        encoding="utf-8")
        print(alvo)
        return 0
    if args.servir:
        httpd, endereco = servir(args.porta)
        print(endereco, flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            httpd.server_close()
        return 0
    print(censo())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
