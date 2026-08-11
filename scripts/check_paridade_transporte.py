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
                          publicado. Ver a nota sobre o mtime, logo abaixo.

AVISO (não derruba o CI hoje)
  6. `assimetria-nao-declarada` — `cabo_aciona` e `radio_aciona` divergem (ou um
                          dos dois nem foi respondido) e `assimetria_declarada`
                          está vazia. Começa como AVISO PORQUE O CSV AINDA ESTÁ
                          SENDO PREENCHIDO: hoje a divergência mais comum é
                          "ninguém respondeu esse lado", que é buraco de censo,
                          não mentira do mapa. Promover para FALHA é trocar
                          `ASSIMETRIA_REPROVA` para True — uma linha, no topo
                          deste arquivo — quando as colunas estiverem fechadas.
  7. `validade-sem-data` — `validade_dias` preenchido com `provado_em` vazio:
                          prazo que não se consegue contar.

Por que a regra 5 existe, se `gerar-mapa.py --check` já compara datas
---------------------------------------------------------------------
Porque aquele `--check` compara MTIME, e mtime no CI é ordem de checkout, não
histórico de edição: o `actions/checkout` escreve os arquivos em ordem de
caminho, e `specs.html` (raiz, "sp") sai depois de `docs/` e de `scripts/` —
então ele nasce sempre "mais novo" que as fontes e o `--check` passa SEMPRE,
independente do conteúdo. Ele continua valendo, e vale muito, no caminho onde
mtime é informação de verdade: a máquina de quem edita (por isso ele entrou
também no `.pre-commit-config.yaml`). No CI quem morde de fato é esta regra 5,
que compara CONTEÚDO: todo `id` do CSV tem de estar dentro do `specs.html`.

Limite honesto da regra 5: ela pega a linha NOVA que ninguém publicou. Linha
REMOVIDA do CSV e ainda publicada no HTML ela não vê — para isso o mtime local
continua sendo a rede.

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

#: PROMOÇÃO DA REGRA 6. Trocar para True faz a assimetria não declarada
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

CSV_RELATIVO = "docs/data/mapa-controles.csv"
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
SUFIXOS_EXIGIDOS = ("aciona", "confianca", "canal")

#: Domínio de cada coluna. Vazio é SEMPRE aceito, e isso é decisão de desenho:
#: o próprio `specs.html` declara no rodapé que "vazio aqui é pergunta aberta,
#: nunca não". Valor novo que não estiver nesta tabela reprova — de propósito.
#: Acrescentar um valor ao mapa é acrescentá-lo aqui, no mesmo gesto, senão a
#: régua passa a aprovar o que não sabe ler.
#:
#: `aciona`/`aceita` entram aqui embora o pedido só citasse canal/confiança/
#: existe: a regra 1 e a 6 leem `aciona`, e um valor novo ali (um "sim?" com
#: interrogação, por exemplo) desligaria as duas EM SILÊNCIO.
DOMINIO_POR_SUFIXO = {
    "aciona": frozenset({"", "sim", "não", "parcial", "desconhecido"}),
    "aceita": frozenset({"", "sim", "não", "parcial", "desconhecido"}),
    "canal": frozenset(
        {"", "hidraw", "uhid", "evdev", "sysfs", "dbus", "alsa-pipewire", "outro"}
    ),
    "confianca": frozenset(
        {"", "medido", "inferido-do-codigo", "afirmado-no-doc", "incerto"}
    ),
}
DOMINIO_EXISTE = frozenset({"", "tem", "nao-tem", "parcial", "desconhecido"})

#: O que conta como "afirmação forte": o produto ACIONA aquilo, e alguém MEDIU.
#: `parcial` fica de fora de propósito — é uma afirmação com ressalva, e a
#: sprint quer a rede primeiro onde a promessa é inteira.
ACIONA_FORTE = "sim"
CONFIANCA_FORTE = "medido"

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

        if mudas_nesta_linha == len(LADOS):
            resumo.linhas_mudas_dos_dois_lados += 1

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
    """Regra 3 e regra 7. Silenciosa quando as duas colunas estão vazias."""
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
    """Regra 6 — o caso que ela descreveu: consolidado no cabo, morto no rádio."""
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
        return 1

    print(f"OK: nenhuma afirmação forte sem rede em {caminho_csv.name}.")
    imprime_resumo(resumo, desligadas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
