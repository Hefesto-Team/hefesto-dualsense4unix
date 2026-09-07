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
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[1]

# O `monta` mora dentro do pacote e é importado POR CAMINHO, como as dez abas
# fazem (`aba01.py:60-62`). Ele puxa `onde` como módulo solto do mesmo
# diretório, então acrescentar a pasta ao `sys.path` é o contrato dele, não um
# atalho meu.
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))
sys.path.insert(0, str(RAIZ / "src"))
import monta  # noqa: E402

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
    ("obedeceu", "obedeceu"),
    ("nada", "nada aconteceu"),
    ("nao-vi", "não consegui ver"),
    ("outra-coisa", "aconteceu outra coisa"),
)

#: Os papéis do desenho, e eles TÊM de ser distintos: um teste em que os quatro
#: brilham igual não diz nada.
PAPEL_REAGE = "reage"
PAPEL_CALADO = "calado"
PAPEL_OBSERVA = "observa"


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


def linhas_do_roteiro() -> list[tuple[str, str, str, str]]:
    """As 21 linhas da §2 da sprint, lidas da tabela markdown.

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
        if len(celulas) == 4 and celulas[0].isdigit():
            fora.append((celulas[0], celulas[1], celulas[2], celulas[3]))
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


def testes_do_roteiro(vocab: dict[str, set[str]]) -> list[Teste]:
    """As 21 linhas da aceitação, uma por teste.

    **As linhas 13-21 são a ACEITAÇÃO DO PRODUTO** — a definição de pronto dela,
    dita em gestos. Elas vêm primeiro na página por isso.
    """
    fora = []
    fonte = f"{arquivo_do_roteiro().relative_to(RAIZ)} §2"
    for numero, gesto, passa, sprints in linhas_do_roteiro():
        limpo = re.sub(r"[*`]", " ", f"{gesto} {passa}")
        nomeados = postos_citados(limpo)
        papeis = {
            p: (PAPEL_REAGE if p in nomeados else PAPEL_CALADO) if nomeados
            else PAPEL_OBSERVA
            for p in POSTOS
        }
        fora.append(Teste(
            id=f"roteiro-{int(numero):02d}",
            secao="O roteiro — a aceitação do produto",
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
            if not (nao_medido or (fraco and afirma)):
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
    try:
        estado = _pergunta_ao_daemon("daemon.state_full")
    except FileNotFoundError:
        fora["daemon"] = (
            "daemon offline — o socket não existe. Os quatro cartões ficam no "
            "travessão, e o registro grava a ausência como ela é. Ninguém "
            "reinicia o daemon dela por causa desta página.")
        return fora
    except Exception as erro:  # o canal caiu; a página continua servindo
        fora["daemon"] = f"daemon não respondeu: {erro}"
        return fora

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
            raise ValueError(
                "sem o COMO não se grava: diga o gesto exato que foi aplicado "
                "(o comando, o report, o byte, o arquivo:linha de quem o "
                "executou). É isto que se perdia quando a sessão morria.")
        linha = {
            "quando": _agora(),
            "teste": item.get("teste"),
            "secao": item.get("secao"),
            "titulo": item.get("titulo"),
            "celula": item.get("celula"),
            "respostas": item.get("respostas") or {},
            "o_que_eu_vi": item.get("o_que_eu_vi") or "",
            "gesto": gesto,
            "como_do_arquivo": item.get("como_do_arquivo") or [],
            "mesa": _mesa_mascarada(item.get("mesa") or {}),
            "veredito": item.get("veredito") or "",
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
    """
    valores = [v for v in respostas.values() if v]
    if not valores:
        return "não feito"
    if any(v == "outra-coisa" for v in valores):
        return "parcial"
    if all(v in ("obedeceu", "nada") for v in valores):
        return "obedeceu"
    if all(v == "nao-vi" for v in valores):
        return "não feito"
    return "parcial"


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


_CSS = """
:root{
  --fundo:#f6f5f3; --papel:#fff; --tinta:#1c1c1e; --fraca:#6b6b70;
  --regua:#dedcd8; --ok:#2f7d52; --falha:#b3352f; --parcial:#a9761c;
  --reage:#ff79c6; --calado:#7c8598; --observa:#5b8dd6;
}
@media (prefers-color-scheme:dark){:root:not([data-tema="claro"]){
  --fundo:#141416; --papel:#1d1d20; --tinta:#eceaea; --fraca:#9a9aa0;
  --regua:#2e2e33; --ok:#5fd18f; --falha:#ff7b72; --parcial:#e0b352;}}
*{box-sizing:border-box}
body{margin:0;background:var(--fundo);color:var(--tinta);
  font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
header{position:sticky;top:0;z-index:9;background:var(--papel);
  border-bottom:1px solid var(--regua);padding:.7rem 1rem;
  display:flex;gap:1rem;align-items:baseline;flex-wrap:wrap}
header b{font-size:1.05rem}
.cinza{color:var(--fraca);font-size:.85rem}
main{max-width:1180px;margin:0 auto;padding:1rem}
.cartao{background:var(--papel);border:1px solid var(--regua);
  border-radius:10px;padding:1rem 1.15rem;margin:0 0 1rem}
h2{margin:.1rem 0 .5rem;font-size:1.15rem}
h3{margin:1.1rem 0 .4rem;font-size:.78rem;letter-spacing:.09em;
  text-transform:uppercase;color:var(--fraca)}
.linha-obs{display:grid;grid-template-columns:4.2rem 1fr;gap:.35rem .7rem;
  padding:.15rem 0;border-bottom:1px dotted var(--regua)}
.papel-tag{font-size:.72rem;font-weight:700;letter-spacing:.05em}
.t-reage{color:var(--reage)} .t-calado{color:var(--calado)} .t-observa{color:var(--observa)}
.quatro{display:grid;grid-template-columns:repeat(4,1fr);gap:.8rem}
@media (max-width:820px){.quatro{grid-template-columns:repeat(2,1fr)}}
.ctl{border:2px solid var(--regua);border-radius:10px;padding:.6rem;
  background:var(--papel)}
.ctl.papel-reage{border-color:var(--reage);--realce:var(--reage);
  box-shadow:0 0 0 3px color-mix(in srgb,var(--reage) 22%,transparent)}
.ctl.papel-calado{border-style:dashed;border-color:var(--calado);--realce:var(--calado);opacity:.72}
.ctl.papel-observa{border-color:var(--observa);--realce:var(--observa)}
.ctl svg{width:100%;height:auto;display:block}
.ctl .nome{font-weight:700;font-size:.9rem;margin-top:.35rem}
.ctl .meta{font-size:.75rem;color:var(--fraca);font-variant-numeric:tabular-nums}
.ctl .rotulo-papel{font-size:.68rem;font-weight:700;letter-spacing:.06em;
  text-transform:uppercase}
.resp{margin:.5rem 0 0;font-size:.82rem}
.resp label{display:block;padding:.1rem 0;cursor:pointer}
textarea,input[type=text]{width:100%;font:inherit;padding:.45rem .55rem;
  border:1px solid var(--regua);border-radius:6px;background:var(--fundo);
  color:var(--tinta)}
button{font:inherit;padding:.5rem .95rem;border-radius:7px;cursor:pointer;
  border:1px solid var(--regua);background:var(--papel);color:var(--tinta)}
button.forte{background:var(--tinta);color:var(--papel);border-color:var(--tinta);
  font-weight:600}
button:disabled{opacity:.45;cursor:not-allowed}
.rodape{display:flex;gap:.6rem;justify-content:flex-end;margin-top:.9rem;
  flex-wrap:wrap}
.timer{font:700 3.2rem/1 ui-monospace,monospace;text-align:center;
  padding:1.6rem 0;font-variant-numeric:tabular-nums}
.como{font:12.5px/1.5 ui-monospace,SFMono-Regular,monospace;
  background:var(--fundo);border:1px solid var(--regua);border-radius:6px;
  padding:.5rem .6rem;white-space:pre-wrap;word-break:break-word}
.como b{color:var(--fraca);font-weight:600}
table.indice{width:100%;border-collapse:collapse;font-size:.85rem}
table.indice td,table.indice th{border-bottom:1px solid var(--regua);
  padding:.3rem .45rem;text-align:left;vertical-align:top}
td.n{width:3rem;font-variant-numeric:tabular-nums;color:var(--fraca)}
.e-obedeceu{color:var(--ok);font-weight:600}
.e-falhou{color:var(--falha);font-weight:600}
.e-parcial{color:var(--parcial);font-weight:600}
.e-nao{color:var(--fraca)}
a{color:inherit}
.envelope{overflow-x:auto}
"""

_JS = r"""
const TESTES = window.__TESTES__;
let atual = 0, tempo = 1, tique = null, gravado = window.__GRAVADO__ || {};

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
  if (trocou) { limpar(); }
  location.hash = TESTES[atual].id;
  pintar();
}

function limpar() {
  $('#o-que-eu-vi').value = '';
  $('#gesto').value = '';
  $('#aviso').textContent = '';
}

async function desenhar() {
  const alvo = $('#desenhos');
  alvo.innerHTML = '<p class="cinza">montando os quatro desenhos…</p>';
  const r = await fetch('/desenhos?teste=' + encodeURIComponent(TESTES[atual].id));
  alvo.innerHTML = await r.text();
  const salvo = gravado[TESTES[atual].id];
  // OS CAMPOS SÃO SEMPRE REESCRITOS, inclusive para o vazio. Defeito medido
  // pela régua nesta leva: eles só eram preenchidos QUANDO havia registro, e o
  // texto do teste anterior ficava na tela — ela avançaria e salvaria o gesto
  // do teste passado como se fosse deste. Um campo que herda o valor do
  // anterior é pior que um campo em branco: ele afirma.
  $('#o-que-eu-vi').value = (salvo && salvo.o_que_eu_vi) || '';
  $('#gesto').value = (salvo && salvo.gesto) || '';
  $('#aviso').textContent = '';
  if (salvo && salvo.respostas) {
    for (const [p, v] of Object.entries(salvo.respostas)) {
      const el = $(`input[name="r-${p}"][value="${v}"]`);
      if (el) el.checked = true;
    }
  }
}

function pintar() {
  const t = TESTES[atual];
  $('#contador').textContent = `teste ${atual + 1} de ${TESTES.length}`;
  $('#secao').textContent = t.secao;
  $('#titulo').textContent = t.titulo;
  $('#antes').hidden = tempo !== 1;
  $('#contagem').hidden = tempo !== 2;
  $('#depois').hidden = tempo !== 3;

  if (tempo === 1) {
    $('#vai-acontecer').innerHTML = esc(t.vai_acontecer);
    $('#passa-quando').innerHTML = esc(t.passa_quando);
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
  if (tempo === 3) desenhar();
  indice();
}

function iniciar() {
  const t = TESTES[atual];
  tempo = 2;
  pintar();
  let resta = t.segundos;
  const mostra = () => {
    const m = Math.floor(resta / 60), s = resta % 60;
    $('#relogio').textContent = m > 0 ? `${m}:${String(s).padStart(2, '0')}` : String(s);
  };
  mostra();
  tique = setInterval(() => {
    resta -= 1;
    mostra();
    if (resta <= 0) { clearInterval(tique); tique = null; ir(atual, 3); }
  }, 1000);
}

async function salvar(avanca) {
  const t = TESTES[atual];
  const respostas = {};
  for (const p of ['P1', 'P2', 'P3', 'P4']) {
    const el = $(`input[name="r-${p}"]:checked`);
    if (el) respostas[p] = el.value;
  }
  const gesto = $('#gesto').value.trim();
  if (!gesto) {
    $('#aviso').textContent = 'O COMO é obrigatório: escreva o gesto exato que foi aplicado. É isto que se perdia quando a sessão morria.';
    $('#gesto').focus();
    return;
  }
  $('#aviso').textContent = '';
  const mesa = await (await fetch('/mesa')).json();
  const r = await fetch('/registro', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      teste: t.id, secao: t.secao, titulo: t.titulo, celula: t.celula,
      respostas, o_que_eu_vi: $('#o-que-eu-vi').value, gesto,
      como_do_arquivo: t.como, mesa,
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

window.addEventListener('DOMContentLoaded', () => {
  $('#iniciar').onclick = iniciar;
  $('#pular-timer').onclick = () => { if (tique) clearInterval(tique); tique = null; ir(atual, 3); };
  $('#voltar').onclick = () => ir(atual, 1);
  $('#anterior').onclick = () => ir(atual - 1, 1);
  $('#salvar').onclick = () => salvar(true);
  $('#so-salvar').onclick = () => salvar(false);
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
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>A mesa de medição — os quatro DualSense</title>
<style>{_CSS}</style>
{monta.folha_das_cores()}
<style>{monta.folha_de_realce()}</style>
</head><body>
<header>
  <b>A mesa de medição</b>
  <span class="cinza" id="contador"></span>
  <span class="cinza" id="daemon">lendo o daemon…</span>
  <span class="cinza">o registro vai para {_e(pasta_do_registro())}</span>
</header>
<main>
  <div class="cartao">
    <div class="cinza" id="secao"></div>
    <h2 id="titulo"></h2>

    <section id="antes" hidden>
      <h3>O que vai acontecer</h3>
      <p id="vai-acontecer"></p>
      <h3>Passa quando</h3>
      <p id="passa-quando"></p>
      <h3>O que observar em cada um</h3>
      <div id="observar"></div>
      <h3>A célula que isto fecha</h3>
      <p><code id="celula"></code><br><span class="cinza" id="hoje"></span></p>
      <h3>A peça que vai acender</h3>
      <p id="pecas"></p>
      <h3>O COMO que o arquivo já publica</h3>
      <div class="como" id="como-do-arquivo"></div>
      <div class="rodape">
        <button id="anterior">&larr; anterior</button>
        <button id="iniciar" class="forte">&#9654; INICIAR
          (<span id="segundos-alvo"></span>s de timer antes)</button>
      </div>
    </section>

    <section id="contagem" hidden>
      <h3>Tire os olhos da tela e ponha nos controles</h3>
      <div class="timer" id="relogio">—</div>
      <div class="rodape"><button id="pular-timer">já passou &rarr;</button></div>
    </section>

    <section id="depois" hidden>
      <h3>Os quatro, agora</h3>
      <div id="desenhos"></div>
      <h3>O que eu vi</h3>
      <textarea id="o-que-eu-vi" rows="2"
        placeholder="acendeu na hora, cor certa…"></textarea>
      <h3>O COMO — o gesto exato que foi aplicado (obrigatório)</h3>
      <textarea id="gesto" rows="3"
        placeholder="o comando, o report, o byte, o arquivo:linha de quem executou"></textarea>
      <p class="cinza" id="aviso"></p>
      <div class="rodape">
        <button id="voltar">&larr; voltar</button>
        <button id="so-salvar">salvar e ficar</button>
        <button id="salvar" class="forte">salvar e avançar &rarr;</button>
      </div>
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
</script>
<script>{_JS}</script>
</body></html>"""


def cartoes(teste: Teste, mesa: dict[str, Any]) -> str:
    """Os quatro cartões do TEMPO 3: desenho, identidade e as quatro respostas.

    A LUZ DE JOGADOR ENTRA NA IDENTIFICAÇÃO — pedido dela: *"lá tem o led do
    player, o led que fica aceso também e afins"*. O desenho mostra qual lâmpada
    está acesa em cada um, e é assim que ela casa o cartão da tela com o
    plástico na mesa.
    """
    svgs = desenhos(teste, mesa)
    postos = (mesa or {}).get("postos") or {}
    blocos = []
    for posto in POSTOS:
        vivo = postos.get(posto) or {}
        papel = teste.papeis.get(posto, PAPEL_OBSERVA)
        diz = {
            PAPEL_REAGE: "deve reagir",
            PAPEL_CALADO: "não pode reagir",
            PAPEL_OBSERVA: "observe",
        }[papel]
        bateria = vivo.get("bateria")
        meta = " · ".join(x for x in (
            vivo.get("transporte") or "sem transporte",
            f'{bateria}%' if isinstance(bateria, (int, float)) else "bateria —",
            vivo.get("estado_da_bateria") or "",
            f'lâmpada {vivo["lampada"]}' if vivo.get("lampada") else "lâmpada —",
        ) if x)
        respostas = "".join(
            f'<label><input type="radio" name="r-{posto}" value="{v}"> {_e(rot)}</label>'
            for v, rot in RESPOSTAS
        )
        blocos.append(
            f'<div class="ctl papel-{papel}" data-posto="{posto}">'
            f'{svgs[posto]}'
            f'<div class="rotulo-papel t-{papel}">{_e(posto)} · {_e(diz)}</div>'
            f'<div class="nome">{_e(vivo.get("nome") or "—")}</div>'
            f'<div class="meta">{_e(meta)}</div>'
            f'<div class="meta">{_e(vivo.get("modelo") or "sem modelo publicado")}'
            f' · {_e(vivo.get("uniq") or "sem endereço")}</div>'
            f'<div class="resp">{respostas}</div>'
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

    def do_GET(self) -> None:  # noqa: N802 (a forma é da biblioteca padrão)
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
            self._responder("não existe".encode("utf-8"),
                            "text/plain; charset=utf-8", 404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] != "/registro":
            self._responder("não existe".encode("utf-8"),
                            "text/plain; charset=utf-8", 404)
            return
        tamanho = int(self.headers.get("Content-Length") or 0)
        try:
            item = json.loads(self.rfile.read(tamanho).decode("utf-8"))
        except ValueError as erro:
            self._responder(str(erro).encode("utf-8"),
                            "text/plain; charset=utf-8", 400)
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
