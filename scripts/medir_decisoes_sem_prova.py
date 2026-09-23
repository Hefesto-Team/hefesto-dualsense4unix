#!/usr/bin/env python3
"""AS TRÊS MEDIÇÕES DA `DECISAO-SEM-DONO-01` — decidida não é feita.

**O defeito, na palavra dela, 17/09/2026:**

    "segue por default mudo. eu preciso lembrar de clicar no icon do mic pra
     ativar e ele ser reconhecido. isso deveria tá ativado por padrão"
    (noqa-acento: citação literal dela, palavra por palavra)

Isso já era decisão dela desde **25/08/2026**, registrada em
``docs/data/decisoes-dela.csv`` como ``D-AUDIO-E-GIRO-NASCEM-LIGADOS``,
``estado: decidida``. Ela pediu a mesma coisa três vezes em 23 dias porque o
ciclo de vida do registro termina em `decidida` — **não existe o degrau que diz
que a decisão virou código**, e nenhum portão cobra.

ESTE ARQUIVO NÃO É O PORTÃO
===========================

A sprint é explícita: *"Não escreve o portão, não mexe no CSV, não implementa
decisão nenhuma. É o censo, o desenho e as três medições que vêm antes."*
Este é o instrumento das três medições — e o `--check` dele guarda a MEDIÇÃO,
nunca as decisões. Ele nunca reprova porque ela registrou uma decisão nova;
reprova quando uma decisão que TINHA régua a perdeu, quando o CSV muda de
forma por baixo da medição, ou quando o classificador de processo começa a
engolir decisão que comprovadamente é de produto.

O portão que a sprint desenha — o que exige o campo ``prova:`` e RODA a régua
apontada — depende de duas coisas que são dela: o nome do degrau novo
(`implementada`? `feita`? `no ar`?) e o que fazer com as decisões de processo.
As três medições abaixo existem para que esse portão não nasça em cima de um
sinal falso, e a segunda delas diz que ele **não pode** classificar sozinho.

MEDIÇÃO 1 — O PISO REAL, e ele é menor do que o texto sugere
-------------------------------------------------------------

*"Quantas das 237 já têm régua, mesmo sem o campo. A casa escreve régua com o
nome da decisão no título. Casar por texto dá o piso real — e se ele for alto,
esta sprint é pequena."*

Casando por texto, medido em 20/09/2026 nesta árvore:

============================================================  ====
decisões com ``estado: decidida``                              237
citadas em qualquer lugar (``tests/`` + ``scripts/`` + ``src/``)    62
citadas em ``tests/``                                           39
**citadas DENTRO de uma função ``test_*``**                     29
dessas, no CORPO da função (fora da docstring dela)             27
============================================================  ====

**O piso real é 29, não 62.** As 33 de diferença são citação em
comentário de ``src/`` — o código diz de que decisão ele nasceu, o que é bom e
não mede nada. E das 39 de ``tests/``, **dez citam só no cabeçalho do módulo**:
o id está na docstring que explica de onde o arquivo veio, e nenhuma função de
teste o menciona. Um portão que casasse por texto contaria as dez como
provadas. Elas estão nomeadas na saída.

A sprint pergunta se o piso é alto o bastante para a sprint ser pequena. **Não
é:** 29 de 237 é 12%. Sobram 208 decisões sem nada apontando para elas.

**E O INSTRUMENTO QUASE INFLOU O PRÓPRIO PISO.** A régua deste arquivo cita
``D-COSTURA-BLUEZ`` e ``D-GESTO-DO-MAPA`` dentro de funções ``test_*``, porque
confere que as duas saem nomeadas no laudo. Bastou ela existir: o piso subiu
para 31 e as citadas-só-no-cabeçalho caíram de 10 para 8, sem que uma linha do
produto mudasse. Curado em :func:`_e_o_proprio_instrumento`, por derivação — o
arquivo que menciona o nome deste módulo é régua DELE, não das decisões.

MEDIÇÃO 2 — «quantas são de processo» NÃO TEM RESPOSTA MECÂNICA
-----------------------------------------------------------------

*"Quantas são de processo e saem do escopo. Sem isso o portão nasce reprovando
coisa que não tem como provar."*

Duas tentativas de derivar a resposta do próprio CSV, e as duas caíram:

1. **Por território** — «a decisão nomeia caminho de código?». Cai porque
   ``onde_mora`` guarda **onde a decisão foi registrada**, não onde ela vive no
   produto: **115 das 237** têm um ``onde_mora`` que cita ``docs/`` e nenhum
   de ``src/``, ``tests/`` ou ``scripts/`` — e entre elas está a própria
   ``D-AUDIO-E-GIRO-NASCEM-LIGADOS``, que é a decisão mais de produto do
   arquivo. Território não separa nada.

   (NÚMERO SUBSTITUÍDO NA CONFERÊNCIA DE 20/09/2026: dizia 98, e nenhuma
   leitura do CSV devolve 98. Vale a regra da casa — número que ninguém
   consegue re-derivar sai, e o que fica vem com a derivação ao lado.)
2. **Por vocabulário** — duas listas de palavras, uma de processo (sprint,
   onda, release, agente, commit…) e uma de produto (aba, botão, daemon,
   microfone…). Medido: 102 só-produto, 11 só-processo, 4 com nenhum dos dois
   e **120 com os dois** — 50,6% indecidíveis, e o maior balde do arquivo.
3. **A escrituração envenena o assunto.** A primeira versão desta lista trazia
   `delegação` e `prioridade`. Elas não falam do que a decisão É: **86 linhas**
   do CSV trazem «POR DELEGAÇÃO» no campo ``escolha``, que é quem decidiu e não
   sobre o quê. O estrago tem tamanho medido: com as duas palavras dentro,
   **16 decisões** caíam no balde «processo» sem que nenhuma outra palavra de
   processo aparecesse nelas — a escrituração era o único motivo. Entre elas, a
   redação de duas perguntas da aba Configurações. As palavras saíram — a raiz,
   não o caso.

   (NÚMERO SUBSTITUÍDO NA CONFERÊNCIA DE 20/09/2026: dizia «36 linhas», e a
   leitura do CSV devolve 86. E o número que decide não era esse: é o 16.)

E, com as três quedas contadas, **o classificador ainda erra 2 em 29** contra
o único chão firme que existe: as decisões que têm régua dentro de um
``test_*`` são de produto por construção, e ele chama duas delas de processo
(``D-0609-GTK-LEVA-INTEIRA`` e ``D-REDACAO-DAS-DUAS-PERGUNTAS-DE-RADIO``).
Nos dois casos a palavra de processo está na escrituração e as palavras da
decisão não estão em vocabulário nenhum. Alargar o vocabulário para caber
nelas seria ajustar a régua ao caso; as duas ficam declaradas.

**A conclusão que o portão precisa ouvir: ele não pode classificar sozinho.**
A triagem das 237 é declarada uma a uma, do jeito que as 56 do ``casa-sabe``
foram — e o CSV não tem hoje nenhuma coluna onde essa marca caiba. É a segunda
coisa que a sprint já dizia ser dela.

O classificador fica aqui porque ele é útil como TRIAGEM (ele diz por onde
começar), e porque é ele que o ``--check`` vigia: se alguém alargar o
vocabulário de processo e ele passar a engolir decisão que tem régua, o
instrumento reprova nomeando. As colisões conhecidas estão em
:data:`COLISOES_DECLARADAS`, com a razão de cada uma.

MEDIÇÃO 3 — O FURO DO PRÓPRIO PORTÃO, com data
------------------------------------------------

*"Uma decisão pode ter régua que passa e mesmo assim não estar no produto — se
a régua mede o método e não o caminho. O portão mede a EXISTÊNCIA da prova,
não a qualidade dela; diga isso em voz alta no script, para ninguém confundir
verde com feito."*

Dito em voz alta, e medido no caso que a sprint escolheu. ``git log -S`` sobre
``D-AUDIO-E-GIRO-NASCEM-LIGADOS`` em ``tests/``:

===========  =======================================================
2026-09-04   ``1a5a8bb3e`` o giroscópio e o acelerômetro desligam de verdade
2026-09-05   ``862447a34`` o rascunho aprende as duas seções que faltavam
2026-09-05   ``b6dc0e1e2`` o rodapé passa a ler as cinco coisas
2026-09-06   ``2adf76655`` a lista de omissão vira regra derivada
2026-09-06   ``de6babe00`` o censo das nove features por controle vira portão
2026-09-17   ``3da234646`` o microfone nasce NO AR na chegada do controle
===========  =======================================================

**A decisão tinha citação dentro de ``tests/`` desde 04/09 — treze dias antes
de ela abrir o produto em 17/09 e achar o microfone mudo.** Um portão que
casasse por texto estaria VERDE sobre essa decisão durante os treze dias, e o
defeito que ela reportou três vezes continuaria lá.

Por isso o vocabulário de baldes deste instrumento **não tem a palavra
«implementada»**: ele responde ``citada dentro de um teste``, ``citada só no
cabeçalho`` e ``sem citação``, que é o que ele sabe. Há régua cobrando isso
(``test_o_balde_nunca_diz_implementada``).

O CUSTO DE CADA DEGRAU
----------------------

Com o piso em 29, o que falta para cada degrau da triagem da sprint:

- **do texto à prova**: 208 decisões sem nenhuma função de teste que as
  mencione. Escrever uma régua por decisão é o custo cheio;
- **da citação à medição**: 10 decisões já citadas em ``tests/`` a que falta
  só mover o id para dentro da função que já mede — é o degrau barato, e o
  único que o texto sozinho já identifica nominalmente;
- **da triagem**: 120 decisões que nenhum classificador separa. O custo aqui
  não é de código: é de leitura, uma a uma, e a marca não tem coluna onde
  morar.

Uso::

    scripts/medir_decisoes_sem_prova.py            o laudo das três medições
    scripts/medir_decisoes_sem_prova.py --nominal  com as listas inteiras
    scripts/medir_decisoes_sem_prova.py --json     para quem escrever o portão
    scripts/medir_decisoes_sem_prova.py --check    rc=1 se a MEDIÇÃO envelheceu
"""
from __future__ import annotations

import argparse
import ast
import csv
import json
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
CSV_DAS_DECISOES = RAIZ / "docs" / "data" / "decisoes-dela.csv"

# As colunas que ESTA medição lê. Se uma sumir, a medição passa a medir outra
# coisa em silêncio — e é por isso que o `--check` confere a forma antes de
# qualquer número.
COLUNAS_QUE_A_MEDICAO_LE = ("id", "titulo", "estado", "decidida_em", "onde_mora")

# O vocabulário de `estado` do CSV, medido em 20/09/2026. A sprint propõe um
# quarto valor (o degrau que falta) e o nome dele é DELA — quando ele chegar,
# esta tupla cresce junto, de propósito: um valor novo que ninguém declarou faz
# a medição contar errado sem avisar.
ESTADOS_CONHECIDOS = ("aberta", "decidida", "caduca")

# Os baldes. NENHUM deles diz «implementada», e isso é a medição 3 virada em
# regra: este instrumento sabe onde o id APARECE, não se a decisão está no
# produto.
BALDE_DENTRO = "citada dentro de um teste"
BALDE_CABECALHO = "citada só no cabeçalho"
BALDE_SEM = "sem citação"

# ---------------------------------------------------------------------------
# O PISO — a catraca, e ela só pega REGRESSÃO.
#
# Estas são as decisões que, em 20/09/2026, tinham o id DENTRO de uma função
# `test_*`. O `--check` reprova quando uma delas perde a régua: teste apagado,
# renomeado, ou id que escorregou da função para o cabeçalho.
#
# Ele NÃO reprova quando ela registra uma decisão nova sem régua. Isso seria o
# portão da sprint, e o portão da sprint espera duas palavras dela.
# ---------------------------------------------------------------------------
COM_REGUA_EM_20260920 = (
    "D-0609-A-FRASE-DO-CONTROLE-SEM-CRACHA",
    "D-0609-A-FRASE-DO-TECLADO-NA-TELA",
    "D-0609-GTK-LEVA-INTEIRA",
    "D-0609-O-MAPA-INFORMA-NUNCA-VETA",
    "D-0609-STEAM-DIVIDIDO",
    "D-0809-NO-CABO-O-PADRAO-DO-SOM-E-SFX",
    "D-0809-O-NO-DE-SOM-POR-CONTROLE-VIVE-SEMPRE",
    "D-0909-A-COR-DE-OUTRO-CONTROLE-SE-RECUSA-COM-X",
    "D-1409-A-TRAVA-MANUAL-SAI-O-PERFIL-APLICA-TUDO",
    "D-1409-FORA-DO-NATIVO-O-JOGO-VE-SO-O-VIRTUAL",
    "D-A-BORDA-E-A-IDENTIDADE-DA-PECA",
    "D-A-MASCARA-POR-CONTROLE-VALE-NO-APLICAR",
    "D-A-PALAVRA-ENTRADA",
    "D-AUDIO-E-GIRO-NASCEM-LIGADOS",
    "D-HCI1-BLOQUEADO",
    "D-LINHA-DO-GANHO-NAO-MEDIDO",
    "D-MAPA-SEM-RECEITA",
    "D-O-MIC-LIGADO-VALE-NO-RADIO",
    "D-O-PAR-DE-ENTRADAS-VEM-DO-SYSFS",
    "D-O-QUE-O-PRODUTO-DIZ-SEM-SABER",
    "D-ORDEM-DE-SERVICO",
    "D-ORDEM-IGNORADA-VOLTA",
    "D-OS-NUMEROS-DO-RADIO-TEM-UM-DONO-SO",
    "D-OS-PLUGINS-APARECEM-ONDE-AGEM",
    "D-PERFIL-DE-DESEMPENHO",
    "D-QUAL-REGUA-MANDA-NO-ARRANJO",
    "D-REDACAO-DAS-DUAS-PERGUNTAS-DE-RADIO",
    "D-STEAM-SAI-DA-NAVEGACAO",
    "D-TROCA-DE-PERFIL-CEGA",
)

# ---------------------------------------------------------------------------
# O CLASSIFICADOR DA MEDIÇÃO 2, e ele é TRIAGEM, nunca veredito.
# ---------------------------------------------------------------------------
#
# AS PALAVRAS QUE SAÍRAM, e elas são a TERCEIRA queda da medição 2:
# `delegação` e `prioridade` estavam aqui e envenenavam a triagem. Elas não
# falam do ASSUNTO da decisão — falam da ESCRITURAÇÃO dela. O campo `escolha`
# de 36 linhas começa com «DECIDIDA POR DELEGAÇÃO (25/08, madrugada, …)», que
# é quem decidiu, não sobre o quê. Com elas dentro, a
# `D-REDACAO-DAS-DUAS-PERGUNTAS-DE-RADIO` — a redação de duas perguntas da aba
# Configurações — era classificada de PROCESSO. Curado na raiz: as palavras
# saem, e não só o caso.
PALAVRA_DE_PROCESSO = re.compile(
    r"\b(?:sprint|sprints|onda|ondas|leva|levas|release|releases|vers[ãa]o|"
    r"SPRINT_ORDER|backlog|agente|agentes|commit|commits|branch|worktree|"
    r"arquivad\w*|arquivar|caduc\w*|CHANGELOG|roadmap)\b",
    re.IGNORECASE,
)
PALAVRA_DE_PRODUTO = re.compile(
    r"\b(?:aba|abas|tela|cart[ãa]o|cards?|bot[ãa]o|bot[õo]es|chip|selo|fita|"
    r"tira|daemon|perfil|perfis|jogo|jogos|controle|controles|DualSense|"
    r"microfone|mic|alto-falante|girosc[óo]pio|sensor|sensores|vibra[çc][ãa]o|"
    r"gatilho|gatilhos|touchpad|barra de luz|LED|anal[óo]gico|volume|som|"
    r"[áa]udio|r[áa]dio|bluetooth|cabo|USB|m[áa]scara|atalho|gesto|dica|"
    r"coluna|usu[áa]ri\w*|clic\w*|salvar|aplicar)\b",
    re.IGNORECASE,
)
CAMPOS_DA_TRIAGEM = ("titulo", "a_pergunta", "escolha", "onde_mora",
                     "recomendacao", "caminhos")

# O ORÁCULO da medição 2: uma decisão com régua DENTRO de um `test_*` é de
# produto por construção — alguém conseguiu apontar uma medição para ela. Toda
# vez que o classificador chamar uma dessas de «processo», é o classificador
# que está errado, e a colisão tem de estar declarada COM A RAZÃO.
COLISOES_DECLARADAS = {
    "D-0609-GTK-LEVA-INTEIRA": (
        "É de PRODUTO: a decisão tira a janela GTK inteira do disco, e quinze "
        "funções de teste medem o que sobrou — entre elas "
        "`test_modo_que_nao_controla_01.py::"
        "test_a_descricao_do_desktop_aponta_para_uma_aba_que_existe`. A "
        "triagem a chama de processo porque a palavra «leva» está no id e na "
        "escolha, e nenhuma palavra de produto aparece: a decisão fala de "
        "ARQUIVOS, e o vocabulário de produto é de TELA e de APARELHO. Esta "
        "colisão fica porque é a prova do limite do classificador — ele lê "
        "palavra, não assunto."
    ),
    "D-REDACAO-DAS-DUAS-PERGUNTAS-DE-RADIO": (
        "É de PRODUTO: a decisão é a redação de duas perguntas da aba "
        "Configurações, e `test_o_lexico_da_aba_configuracoes.py::"
        "test_as_duas_perguntas_de_radio_nao_falam_antena_nem_visada` mede as "
        "duas frases na tela. A triagem a chama de processo porque a `escolha` "
        "menciona «sprints» ao registrar de onde a redação veio, e as palavras "
        "da própria decisão — «Altura da antena», «Linha de visada» — não "
        "estão em vocabulário nenhum. Alargar o de produto para caber nelas "
        "seria ajustar a régua ao caso; a colisão fica declarada porque é o "
        "segundo caso a mostrar que o classificador não tem como decidir."
    ),
    "D-COSTURA-BLUEZ": (
        "É de PRODUTO desde 23/09/2026: a decisão diz quem escreve o `Alias` "
        "do adaptador, e `test_entrada_a_entrada_02_as_telas_aprovadas.py::"
        "test_o_motor_nao_escreve_no_bluez` mede que o motor das portas não "
        "importa escritor de BlueZ. A triagem a chama de processo porque a "
        "`escolha` fala de «script» e de «dono», e o vocabulário de produto "
        "não tem palavra de rádio. Até a ENTRADA-A-ENTRADA-02 ela era citada "
        "só no cabeçalho; ganhou régua de verdade, e a colisão é a prova."
    ),
}


def _linhas(caminho: pathlib.Path | None = None):
    # Resolvidos na CHAMADA, nunca no `def`: um default amarrado à importação
    # não se deixa apontar para outra árvore, e as mordidas precisam montar um
    # CSV e um `tests/` de mentira para provar que a medição enxerga o defeito.
    with (caminho or CSV_DAS_DECISOES).open(encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def problemas_de_forma(linhas) -> list[str]:
    """A medição conferindo o chão em que pisa, ANTES de contar qualquer coisa.

    Coluna que some faz a contagem devolver zero em silêncio, e zero lê-se como
    «nenhuma decisão sem prova» — o contrário do que aconteceu.
    """
    ruins: list[str] = []
    if not linhas:
        return [f"{CSV_DAS_DECISOES} não tem uma linha sequer"]
    faltando = [c for c in COLUNAS_QUE_A_MEDICAO_LE
                if c not in (linhas[0].keys() or ())]
    if faltando:
        ruins.append("coluna(s) que esta medição lê e o CSV não tem mais: "
                     + ", ".join(faltando))
    novos = sorted({linha.get("estado", "") for linha in linhas}
                   - set(ESTADOS_CONHECIDOS))
    if novos:
        ruins.append(
            "estado(s) fora do vocabulário declarado: " + ", ".join(novos)
            + " — se é o degrau novo que a sprint pede, o nome é dela e entra "
              "em ESTADOS_CONHECIDOS junto com a régua que o cobra")
    return ruins


def _e_o_proprio_instrumento(fonte: str) -> bool:
    """O arquivo que carrega ESTE instrumento não é régua de decisão nenhuma.

    MEDIDO EM 20/09/2026, e o defeito foi meu: a régua deste instrumento cita
    ``D-COSTURA-BLUEZ`` e ``D-GESTO-DO-MAPA`` dentro de funções ``test_*`` —
    porque ela confere que as duas saem NOMEADAS no laudo. Bastou existir para
    o piso subir de 29 para 31 e as «citadas só no cabeçalho» caírem de 10 para
    8. **O instrumento estava comprando a própria régua como prova**, que é a
    forma de dívida que esta casa já nomeou duas vezes: *a trava medida contra
    a própria saída*.

    A exclusão é DERIVADA, nunca uma lista de nomes: o arquivo que menciona o
    nome deste módulo é régua DELE, não das decisões. Um arquivo novo que meça
    o instrumento nasce coberto; e o dia em que esta função sumir, o piso sobe
    sozinho e as réguas de baixo reprovam.
    """
    return pathlib.Path(__file__).stem in fonte


def _regex_dos_ids(ids):
    """Uma alternação só, com os ids longos primeiro.

    Os limites existem porque DOIS ids desta casa são prefixo de outro
    (`D-A-ABA-LANCADORES` dentro de `D-A-ABA-LANCADORES-NASCE-PLACEHOLDER`).
    Sem eles a decisão curta herdaria a régua da longa.
    """
    alt = "|".join(re.escape(i) for i in sorted(ids, key=len, reverse=True))
    return re.compile(r"(?<![A-Za-z0-9_-])(" + alt + r")(?![A-Za-z0-9_-])")


def onde_cada_id_aparece(ids, raiz: pathlib.Path) -> tuple[dict, dict, dict]:
    """Devolve (dentro_de_teste, no_arquivo, no_corpo), varrendo ``tests/``.

    A diferença entre os dois primeiros é a MEDIÇÃO 3: casar por texto no
    arquivo conta a docstring do MÓDULO, que explica de onde o arquivo veio e
    não mede nada. Só a segunda pergunta — *o id está dentro de uma função de
    teste?* — separa a régua da nota de rodapé.

    O terceiro é o degrau mais fino, e entra porque o furo tem gradação: o id
    dentro do CORPO da função (fora da docstring dela) é o único caso em que a
    decisão participa do que a função executa. Nesta casa a docstring do teste
    é contrato — *"escreva no docstring o que a mordida arranca"* —, então o
    piso fica na função inteira; o corpo é medido ao lado, para dizer de quanto
    é a folga.
    """
    padrao = _regex_dos_ids(ids)
    dentro: dict[str, list[str]] = {}
    no_arquivo: dict[str, list[str]] = {}
    no_corpo: dict[str, list[str]] = {}
    pasta = raiz / "tests"
    if not pasta.is_dir():
        return dentro, no_arquivo, no_corpo
    for caminho in sorted(pasta.rglob("*.py")):
        try:
            fonte = caminho.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _e_o_proprio_instrumento(fonte):
            continue
        achados = set(padrao.findall(fonte))
        if not achados:
            continue
        rel = str(caminho.relative_to(raiz))
        for ident in achados:
            no_arquivo.setdefault(ident, []).append(rel)
        try:
            arvore = ast.parse(fonte)
        except SyntaxError:
            continue
        for no in ast.walk(arvore):
            if not isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not no.name.startswith("test"):
                continue
            trecho = ast.get_source_segment(fonte, no) or ""
            for ident in set(padrao.findall(no.name + "\n" + trecho)):
                dentro.setdefault(ident, []).append(f"{rel}::{no.name}")
            doc = ast.get_docstring(no) or ""
            corpo = trecho.replace(doc, " ") if doc else trecho
            for ident in set(padrao.findall(no.name + "\n" + corpo)):
                no_corpo.setdefault(ident, []).append(f"{rel}::{no.name}")
    return dentro, no_arquivo, no_corpo


def citadas_fora_de_tests(ids, raiz: pathlib.Path) -> dict[str, list[str]]:
    """Onde mais o id aparece: ``scripts/`` e ``src/``.

    Entra no laudo para mostrar a distância entre os 62 do texto e os 29 da
    medição — o grosso da diferença é comentário de ``src/`` dizendo de que
    decisão o código nasceu. Isso é bom e não é régua.
    """
    padrao = _regex_dos_ids(ids)
    achado: dict[str, list[str]] = {}
    for sub in ("scripts", "src"):
        pasta = raiz / sub
        if not pasta.is_dir():
            continue
        for caminho in sorted(pasta.rglob("*")):
            if caminho.suffix not in (".py", ".sh") or not caminho.is_file():
                continue
            try:
                fonte = caminho.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if _e_o_proprio_instrumento(fonte):
                continue
            rel = str(caminho.relative_to(raiz))
            for ident in set(padrao.findall(fonte)):
                achado.setdefault(ident, []).append(rel)
    return achado


def triagem(linha) -> str:
    """A triagem da MEDIÇÃO 2 — e ela devolve «indecidível» de propósito."""
    texto = " \n ".join(linha.get(c, "") for c in CAMPOS_DA_TRIAGEM)
    processo = bool(PALAVRA_DE_PROCESSO.search(texto))
    produto = bool(PALAVRA_DE_PRODUTO.search(texto))
    if processo and produto:
        return "indecidível"
    if processo:
        return "processo"
    if produto:
        return "produto"
    return "sem vocabulário"


def medir(raiz: pathlib.Path | None = None,
          csv_path: pathlib.Path | None = None) -> dict:
    raiz = raiz or RAIZ
    linhas = _linhas(csv_path)
    forma = problemas_de_forma(linhas)
    decididas = [ln for ln in linhas if ln.get("estado") == "decidida"]
    ids = [ln["id"] for ln in decididas]

    dentro, no_arquivo, no_corpo = onde_cada_id_aparece(ids, raiz)
    fora = citadas_fora_de_tests(ids, raiz)

    so_cabecalho = sorted(set(no_arquivo) - set(dentro))
    sem_citacao_nenhuma = sorted(
        i for i in ids if i not in no_arquivo and i not in fora)

    baldes = {}
    for ident in ids:
        if ident in dentro:
            baldes[ident] = BALDE_DENTRO
        elif ident in no_arquivo:
            baldes[ident] = BALDE_CABECALHO
        else:
            baldes[ident] = BALDE_SEM

    por_triagem: dict[str, list[str]] = {}
    for linha in decididas:
        por_triagem.setdefault(triagem(linha), []).append(linha["id"])

    oraculo = set(dentro)
    colisoes = sorted(oraculo & set(por_triagem.get("processo", [])))

    # As duas checagens do piso são DISJUNTAS de propósito, e a separação é uma
    # cura de 20/09/2026: `regua_perdida` só olha decisão que AINDA está
    # decidida. Sem o filtro, uma decisão que caduca aparecia nas duas listas
    # pela mesma causa — a régua não «se perdeu», a decisão é que saiu —, e a
    # mordida da segunda passava com a cura arrancada, porque a primeira
    # reprovava no lugar dela.
    vivas = set(ids)
    sumidas = sorted(i for i in COM_REGUA_EM_20260920 if i not in vivas)
    perdidas = sorted(i for i in COM_REGUA_EM_20260920
                      if i in vivas and i not in dentro)

    return {
        "problemas_de_forma": forma,
        "linhas": len(linhas),
        "decididas": len(decididas),
        "com_regua_dentro_de_teste": sorted(dentro),
        "com_regua_no_corpo_da_funcao": sorted(no_corpo),
        "citadas_so_no_cabecalho": so_cabecalho,
        "citadas_em_tests": sorted(no_arquivo),
        "citadas_fora_de_tests": sorted(fora),
        "sem_citacao_nenhuma": sem_citacao_nenhuma,
        "baldes": baldes,
        "triagem": {k: sorted(v) for k, v in por_triagem.items()},
        "oraculo": sorted(oraculo),
        "colisoes": colisoes,
        "colisoes_nao_declaradas": [c for c in colisoes
                                    if c not in COLISOES_DECLARADAS],
        "declaracoes_orfas": sorted(set(COLISOES_DECLARADAS) - set(colisoes)),
        "regua_perdida": perdidas,
        "piso_que_sumiu_do_csv": sumidas,
        "onde": {i: sorted(v) for i, v in dentro.items()},
    }


def _laudo(m: dict, nominal: bool) -> None:
    dec = m["decididas"]
    dentro = len(m["com_regua_dentro_de_teste"])
    cab = len(m["citadas_so_no_cabecalho"])
    print("AS TRÊS MEDIÇÕES DA DECISAO-SEM-DONO-01")
    print("=" * 72)
    print(f"{m['linhas']} decisões no CSV · {dec} com estado «decidida»")
    print()
    print("MEDIÇÃO 1 — o piso real, casando por texto")
    print(f"  citadas em tests/ + scripts/ + src/ : "
          f"{len(set(m['citadas_em_tests']) | set(m['citadas_fora_de_tests']))}")
    print(f"  citadas em tests/                   : {len(m['citadas_em_tests'])}")
    print(f"  DENTRO de uma função test_*         : {dentro}   <- o piso")
    print(f"    dessas, no CORPO (fora da docstring): "
          f"{len(m['com_regua_no_corpo_da_funcao'])}")
    print(f"  sem citação em lugar nenhum         : "
          f"{len(m['sem_citacao_nenhuma'])}")
    print(f"  faltam para as {dec}                 : {dec - dentro}"
          f"  ({100 * (dec - dentro) // dec}%)")
    print()
    print("MEDIÇÃO 2 — processo x produto: a triagem NÃO decide sozinha")
    for balde in ("produto", "processo", "indecidível", "sem vocabulário"):
        print(f"  {balde:16s}: {len(m['triagem'].get(balde, []))}")
    print(f"  oráculo (têm régua, logo são de produto): {len(m['oraculo'])}")
    print(f"  colisões oráculo x triagem              : {len(m['colisoes'])}"
          f"  (declaradas: {len(COLISOES_DECLARADAS)})")
    indec = len(m["triagem"].get("indecidível", []))
    print(f"  {100 * indec / dec:.1f}% das decididas caem em «indecidível». O "
          f"portão não pode")
    print("  classificar sozinho: a marca de processo é declarada uma a uma.")
    print()
    print("MEDIÇÃO 3 — o furo: citação NÃO é prova")
    print(f"  citadas em tests/ mas SÓ no cabeçalho: {cab}")
    for ident in m["citadas_so_no_cabecalho"]:
        print(f"    {ident}")
    print("  e o furo maior, medido no caso que a sprint escolheu:")
    print("    D-AUDIO-E-GIRO-NASCEM-LIGADOS tinha citação dentro de tests/")
    print("    desde 2026-09-04 (1a5a8bb3e) — e em 2026-09-17 ela abriu o")
    print("    produto e o microfone estava mudo. Treze dias de verde sobre")
    print("    um defeito que ela já tinha pedido três vezes.")
    print(f"  por isso os baldes são «{BALDE_DENTRO}», «{BALDE_CABECALHO}» e")
    print(f"  «{BALDE_SEM}». Nenhum deles diz «implementada».")
    print()
    print("O CUSTO DE CADA DEGRAU")
    print(f"  do texto à prova : {dec - dentro} decisões sem função de teste "
          f"que as mencione")
    print(f"  da citação à medição: {cab} já em tests/, falta mover o id para "
          f"dentro da função")
    print(f"  da triagem       : {len(m['triagem'].get('indecidível', []))} "
          f"que nenhum classificador separa")
    if nominal:
        print()
        print("AS SEM CITAÇÃO NENHUMA")
        for ident in m["sem_citacao_nenhuma"]:
            print(f"  {ident}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--nominal", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    m = medir()

    if args.json:
        print(json.dumps(m, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    # A FORMA SE CONFERE ANTES DE QUALQUER SAÍDA, e não só no `--check`.
    # ACHADO EM 20/09/2026, pela conferência: o laudo sem bandeira nenhuma —
    # o comando que uma pessoa roda PRIMEIRO — estourava `ZeroDivisionError`
    # num CSV sem a coluna `estado`, que é exatamente o caso de que esta
    # seção fala. Traceback não é resposta: a resposta é dizer que a contagem
    # não foi feita, e por quê.
    if m["problemas_de_forma"]:
        print("VERMELHO: o CSV mudou de forma por baixo da medição:")
        for p in m["problemas_de_forma"]:
            print(f"  {p}")
        print()
        print("A contagem não foi feita. Uma coluna que some faz esta medição "
              "devolver zero em silêncio, e zero lê-se como «nenhuma decisão "
              "sem prova» — o contrário do que esta sprint mediu.")
        return 1

    if not args.check:
        _laudo(m, args.nominal)
        return 0

    if m["piso_que_sumiu_do_csv"]:
        print(f"VERMELHO: {len(m['piso_que_sumiu_do_csv'])} decisão(ões) do "
              f"piso não estão mais «decidida» no CSV:")
        for ident in m["piso_que_sumiu_do_csv"]:
            print(f"  {ident}")
        print()
        print("Se a decisão caducou, tire-a de COM_REGUA_EM_20260920 no mesmo "
              "commit e diga por quê. Piso que aponta para linha que não "
              "existe deixa de ser catraca.")
        return 1

    if m["regua_perdida"]:
        print(f"VERMELHO: {len(m['regua_perdida'])} decisão(ões) do piso "
              f"perderam a régua que apontava para elas:")
        for ident in m["regua_perdida"]:
            print(f"  {ident}")
        print()
        print("O id saiu de dentro de toda função test_*: teste apagado, "
              "renomeado, ou id que escorregou para o cabeçalho. Isto é "
              "REGRESSÃO — o piso só desce quando uma decisão GANHA régua.")
        return 1

    if m["colisoes_nao_declaradas"]:
        print(f"VERMELHO: {len(m['colisoes_nao_declaradas'])} decisão(ões) "
              f"que a triagem chama de «processo» e que TÊM régua:")
        for ident in m["colisoes_nao_declaradas"]:
            print(f"  {ident} -> {m['onde'].get(ident, [])[:2]}")
        print()
        print("Régua apontada para ela é prova de que é de PRODUTO. Ou o "
              "vocabulário de processo está largo demais, ou a colisão entra "
              "em COLISOES_DECLARADAS com a razão escrita.")
        return 1

    if m["declaracoes_orfas"]:
        print(f"VERMELHO: {len(m['declaracoes_orfas'])} colisão(ões) "
              f"declarada(s) que já não acontecem:")
        for ident in m["declaracoes_orfas"]:
            print(f"  {ident} — tire a linha de COLISOES_DECLARADAS")
        print()
        print("Declaração que sobrevive ao próprio caso vira propaganda: ela "
              "isenta uma colisão futura que ninguém olhou.")
        return 1

    print(f"VERDE: {m['decididas']} decisões decididas · "
          f"{len(m['com_regua_dentro_de_teste'])} com régua dentro de um "
          f"test_* · {len(m['citadas_so_no_cabecalho'])} citadas só no "
          f"cabeçalho · {len(m['triagem'].get('indecidível', []))} que a "
          f"triagem não separa")
    print()
    print("E VERDE AQUI NÃO QUER DIZER FEITO. Este instrumento mede onde o id "
          "APARECE. A medição 3 tem a data: D-AUDIO-E-GIRO-NASCEM-LIGADOS "
          "esteve citada em tests/ por treze dias com o microfone mudo no "
          "produto dela.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
