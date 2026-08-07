"""O portão da frase que a medição dela derrubou pela metade.

*"O Hefesto sai da frente"* — e as irmãs *"sai de cena"*, *"sai do caminho"*,
*"se cala"* — era como a casa inteira descrevia o que acontece quando um jogo
entra na allowlist do Steam Input. Em 06/08/2026, das 19:34 às 19:56, com um
DualSense físico e três jogos abertos, **ela** mediu o contrário da metade que
importa — a sprint `CONTROLE-SONY-MEDIDO-01`, em `docs/process/sprints/`,
seção *A INVERSÃO*, **grau MEDIDO**:

- o Hefesto **entrega a ENTRADA** — solta o grab, desfaz o esconde-esconde do
  hidraw e recolhe o gamepad virtual, que é o que acaba com o controle dobrado;
- e **mantém a SAÍDA inteira** — com o Mullet Mad Jack aberto, os gatilhos que
  ela aplicou seguraram **duros** e o vermelho **dela** ficou na lightbar.

O mecanismo é estrutural, não sorte: os oito chamadores de
`steam_input_excecao_ativa` estão todos em `daemon/subsystems/gamepad.py`, e
**nenhum** em `core/` — não existe portão da exceção no caminho de saída.

Por que isso precisa de um portão, e não só de uma varredura
------------------------------------------------------------

Porque a frase **faz a pessoa agir errado**, e no sentido pior: quem lê "o
Hefesto sai da frente" conclui que vai perder cor e gatilho no jogo marcado —
que é exatamente o que acontece **fora** da lista, não dentro (a INVERSÃO). Uma
varredura de hoje conserta as ocorrências de hoje; o portão é o que impede a
frase de voltar amanhã, escrita de boa-fé por quem não leu a sprint.

O CRITÉRIO, e por que não é "procurar a string"
-----------------------------------------------

Um portão que procurasse ``"sai da frente"`` viraria ruído no primeiro
documento honesto — a própria sprint que a refuta precisa **citá-la** para
contá-la, e este arquivo também. Pior: o repositório usa as mesmas palavras
para outros sujeitos, e todos esses usos estão **certos**:

- *"o **co-op** sai de cena sozinho nos jogos com Steam Input"* (`cmd_coop.py`)
  — verdade medida: os vpads dos secundários são recolhidos;
- *"o **gamepad virtual** sai de cena enquanto o jogo estiver em sessão"*
  (`launch_env.py`) — é a definição do mecanismo;
- *"o sinal tem de apagar assim que **o jogo** sai da frente"* — outro sujeito;
- *"a **Steam** está garantidamente fora do caminho"*, *"fora do caminho
  quente"* — assunto completamente diferente.

Logo o portão cobra **duas marcas juntas**, e uma escapatória:

1. **o SUJEITO** — `Hefesto` ou `emulação`. É o produto inteiro que a frase
   afasta, e é isso que a torna falsa: o que sai é o dispositivo de entrada,
   não o produto;
2. **o AFASTAMENTO** — sair da frente / de cena / do caminho, ficar fora de,
   calar-se, parar de atuar;
3. **a escapatória: a marca da refutação por perto** (±8 linhas) — uma citação
   da sprint que mediu, ou as palavras `refut` / `meia verdade` / `caduc`.
   Traduzindo: **a frase só pode aparecer ao lado da medição que a derruba.**
   É o que deixa `profiles_actions.py` escrever *"aqui não se escreve 'o
   Hefesto sai da frente'"* sem o portão reclamar, e o que faria um texto novo
   reclamar imediatamente.

E o portão cobra isso **onde a frase faz estrago**: o produto (`src/`,
`scripts/`, `assets/`) e as páginas que ENSINAM (`README`, `docs/usage`,
`docs/adr`, `docs/protocol`). `docs/process/` e o `CHANGELOG` ficam de fora por
escrito, pelo mesmo motivo de `scripts/validar-referencias-docs.py`: sprint é
**registro**, e registrar uma frase derrubada exige transcrevê-la.

A MORDIDA (verificada em 07/08/2026)
------------------------------------

Arranquei a cura em três lugares, um de cada natureza, e o portão reprovou nos
três, apontando arquivo e linha:

- ``"o Hefesto já sai da frente dele"`` de volta ao toast de
  `format_game_broken_result` -> `daemon_actions.py:558`;
- ``"o Hefesto saiu da frente dele"`` de volta ao tooltip do badge de co-op ->
  `status_actions.py:254`;
- ``"os jogos em que o Hefesto sai da frente"`` de volta ao `--help` do
  `gamepad steam-input` -> `cmd_steam.py:67`.

**A quarta arrancada é a que valeu mais**, e ela reprovou o portão antes de
reprovar o código: arranquei a **escapatória** (apaguei a citação da sprint da
NOTA DATADA de `daemon_actions.py`) e o portão **passou** — porque a marca
``"A INVERSÃO"``, comparada sem caixa, casava com o ``"da inversão"`` que a
paráfrase deixou para trás. A marca frouxa saiu da lista, a arrancada foi
refeita e aí sim o portão reprovou a nota que explica o defeito
(`daemon_actions.py:509`). É a metade condicional funcionando: a nota datada só
vale enquanto **citar** a medição, e não enquanto apenas falar dela.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

#: Onde a frase faz estrago: o produto e as páginas que ENSINAM. `docs/process/`
#: e o `CHANGELOG` ficam de fora por escrito — são registro, e registrar uma
#: frase derrubada exige transcrevê-la.
ALVOS_COBRADOS = (
    "src",
    "scripts",
    "assets",
    "README.md",
    ".github/CONTRIBUTING.md",
    "docs/usage",
    "docs/adr",
    "docs/protocol",
)

#: Arquivos de texto que uma pessoa lê (ou que viram tela). Binário e imagem
#: ficam de fora sozinhos.
SUFIXOS = (".py", ".md", ".sh", ".glade", ".txt", ".desktop", ".in")

#: Marca 1 — o sujeito. É o produto inteiro que a frase afasta, e é aí que ela
#: mente: quem sai é o dispositivo de ENTRADA.
_SUJEITO = r"(?:Hefesto|emula[çc][ãa]o)"

#: Marca 2 — o afastamento, em todas as formas que a casa já escreveu.
_AFASTAMENTO = (
    r"(?:sai|sair|saiu|saem|sa[íi]ram|sair[áa]|sairia|saindo)\s+"
    r"d[aeo]s?\s+(?:frente|cena|caminho)"
    # "fora do caminho" sozinho é ambíguo: o repositório o usa para caminho
    # QUENTE, de criação e de execução — assunto que nada tem a ver com a
    # allowlist. Estes três ficam de fora por nome, e só eles.
    r"|fora\s+d[ao]\s+(?:frente|cena)\b"
    r"|fora\s+d[ao]\s+caminho"
    r"(?!\s+(?:quente|cr[íi]tico|de\s+cria|de\s+execu|de\s+leitura))"
    r"|se\s+cal(?:a|ar|ou|am|aria)\b"
    r"|(?:para|parar|deixa|deixar)\s+de\s+(?:atuar|agir|entregar)"
    r"|n[ãa]o\s+atua\b"
)

#: A regra: sujeito e afastamento na MESMA vizinhança. 80 caracteres é o que
#: cabe entre "o Hefesto" e o verbo numa frase de tela ou num comentário
#: quebrado em duas linhas.
_REGRA = re.compile(
    rf"{_SUJEITO}\b.{{0,80}}?(?:{_AFASTAMENTO})",
    re.IGNORECASE | re.DOTALL,
)

#: A escapatória: a frase só pode aparecer ao lado da medição que a derruba.
#:
#: *"A INVERSÃO"* — o nome da seção — foi tentado aqui e **reprovado na
#: mordida**: comparado sem caixa, ele casa com qualquer *"da inversão"*, e uma
#: das arrancadas passou por isso. Ficaram só marcas que ninguém escreve por
#: acidente ao afirmar a frase.
_MARCAS_DE_REFUTACAO = (
    "controle-sony-medido-01",
    "refut",
    "meia verdade",
    "caduc",
)

#: Quantas linhas de contexto valem como "ao lado".
_RAIO_DA_MARCA = 8


def _arquivos_cobrados() -> list[Path]:
    """Os arquivos do produto e das páginas que ensinam, sem `docs/process/`."""
    achados: list[Path] = []
    for alvo in ALVOS_COBRADOS:
        caminho = RAIZ / alvo
        if caminho.is_dir():
            achados.extend(
                p
                for p in sorted(caminho.rglob("*"))
                if p.is_file() and p.suffix in SUFIXOS
            )
        elif caminho.is_file():
            achados.append(caminho)
    return achados


def _tem_marca_de_refutacao(linhas: list[str], indice: int) -> bool:
    """A vizinhança carrega a citação da medição que derruba a frase?"""
    inicio = max(0, indice - _RAIO_DA_MARCA)
    fim = min(len(linhas), indice + _RAIO_DA_MARCA + 1)
    vizinhanca = " ".join(linhas[inicio:fim]).lower()
    return any(marca in vizinhanca for marca in _MARCAS_DE_REFUTACAO)


def frases_refutadas_em(texto: str) -> list[tuple[int, str]]:
    """As linhas que afirmam a frase refutada, com o trecho de cada uma.

    A janela é de duas linhas porque o produto quebra frase em duas: o sujeito
    fica no fim de uma e o verbo no começo da seguinte, e um portão de uma
    linha só passaria por cima da metade dos casos que ele existe para pegar.
    """
    linhas = texto.splitlines()
    achados: list[tuple[int, str]] = []
    for indice in range(len(linhas)):
        janela = " ".join(linhas[indice : indice + 2])
        janela = re.sub(r"\s+", " ", janela)
        achado = _REGRA.search(janela)
        if achado is None:
            continue
        if _tem_marca_de_refutacao(linhas, indice):
            continue
        achados.append((indice + 1, achado.group(0).strip()))
    return achados


# ---------------------------------------------------------------------------
# O portão
# ---------------------------------------------------------------------------
def test_nenhum_arquivo_do_produto_afirma_que_o_hefesto_sai_da_frente() -> None:
    """A varredura inteira, num teste só — o relatório aponta arquivo e linha."""
    culpados: list[str] = []
    for arquivo in _arquivos_cobrados():
        try:
            texto = arquivo.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for numero, trecho in frases_refutadas_em(texto):
            rel = arquivo.relative_to(RAIZ)
            culpados.append(f"{rel}:{numero}: {trecho!r}")
    assert not culpados, (
        "a frase que ela refutou em 06/08/2026 voltou ao produto. Na allowlist "
        "o Hefesto entrega a ENTRADA e MANTÉM A SAÍDA — os gatilhos dela "
        "seguraram e a cor dela ficou (CONTROLE-SONY-MEDIDO-01, seção A "
        "INVERSÃO). Diga o que de fato acontece, ou cite a medição ao lado:\n  "
        + "\n  ".join(culpados)
    )


# ---------------------------------------------------------------------------
# O critério, provado nos dois sentidos — sem isto o portão acima é uma crença
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "frase",
    [
        "o Hefesto sai da frente dele",
        "o Hefesto já sai da frente deste jogo",
        "o Hefesto saiu da frente dele, e por isso P2 saiu do co-op",
        "os jogos em que o Hefesto sai da frente",
        "a allowlist é opt-in de 'o Hefesto sai de cena neste jogo'",
        "nos dois jogos dela o Hefesto sai de cena de propósito",
        "o Hefesto sai do caminho inclusive retirando o gamepad virtual",
        "o jogo da allowlist rodando com o Hefesto fora do caminho",
        "é a lista dos jogos em que o Hefesto se cala",
        "neste jogo o Hefesto para de atuar",
        "a emulação não foi desligada, ela SAIU DA FRENTE deste jogo",
    ],
)
def test_o_portao_pega_a_frase_em_todas_as_formas_que_a_casa_escreveu(
    frase: str,
) -> None:
    """Cada uma destas esteve viva na árvore antes de 07/08/2026."""
    assert frases_refutadas_em(frase), f"passou batido: {frase!r}"


@pytest.mark.parametrize(
    "frase",
    [
        # Outro sujeito — e todos MEDIDOS como verdadeiros.
        "O co-op sai de cena sozinho nos jogos com Steam Input, e volta depois",
        "o gamepad virtual sai de cena enquanto o jogo da allowlist rodar",
        "o sinal tem de apagar assim que o jogo sai da frente, não 30 s depois",
        "as edições acontecem no intervalo em que a Steam está fora do caminho",
        "o revert restauraria o número e o co-op nunca mais sairia de cena",
        # Assunto completamente diferente.
        "chamado uma vez na fiação do daemon, fora do caminho quente",
        "Fora do caminho de criação desde VPAD-03: o vpad usa o blueprint",
        # O que o produto passou a dizer em 07/08 — a frase certa.
        "Marquei o jogo: ele passa a ver o controle de verdade, sem o dobrado, "
        "e a sua cor e os seus gatilhos continuam valendo",
        "Neste jogo quem entrega o controle é a Steam: os controles virtuais "
        "foram recolhidos, e por isso P2 saiu do co-op",
    ],
)
def test_o_portao_nao_reclama_do_que_esta_certo(frase: str) -> None:
    """Um portão que reprovasse isto seria ruído, e ruído se desliga."""
    assert not frases_refutadas_em(frase), f"falso positivo: {frase!r}"


def test_a_escapatoria_existe_e_e_a_citacao_da_medicao() -> None:
    """Citar a frase para contá-la é permitido; afirmá-la, não.

    É a metade condicional do portão. Sem ela, esta casa não conseguiria
    escrever a nota datada que a regra "não se apaga decisão medida" exige.
    """
    afirmacao = ["    O jogo assumiu o controle: o Hefesto saiu da frente dele."]
    assert frases_refutadas_em("\n".join(afirmacao))

    com_citacao = [
        "    NOTA DATADA — 07/08/2026. Este texto dizia que o Hefesto saiu da",
        "    frente do jogo, e a medição de 06/08 refutou a metade da saída",
        "    (CONTROLE-SONY-MEDIDO-01, seção A INVERSÃO).",
    ]
    assert not frases_refutadas_em("\n".join(com_citacao))


def test_a_escapatoria_nao_alcanca_o_documento_inteiro() -> None:
    """A marca vale por vizinhança, não por arquivo — senão vira anistia.

    Uma citação da sprint no topo de um módulo de mil linhas não pode
    autorizar a frase na linha 900.
    """
    texto = "\n".join(
        ["ver CONTROLE-SONY-MEDIDO-01, seção A INVERSÃO"]
        + ["conteúdo qualquer"] * (_RAIO_DA_MARCA + 4)
        + ["e por isso o Hefesto sai da frente do jogo"]
    )
    assert frases_refutadas_em(texto)


def test_o_escopo_cobra_o_produto_e_poupa_o_registro() -> None:
    """`docs/process/` fora, `src/` dentro — a decisão de escopo é medida.

    A sprint que refuta a frase a cita **doze** vezes; se o portão a cobrasse,
    o primeiro documento honesto o desligaria.
    """
    cobrados = {p.relative_to(RAIZ).as_posix() for p in _arquivos_cobrados()}
    assert any(c.startswith("src/") for c in cobrados)
    assert any(c.startswith("docs/usage/") for c in cobrados)
    assert not any(c.startswith("docs/process/") for c in cobrados)
    assert "CHANGELOG.md" not in cobrados

    sprint = (
        RAIZ
        / "docs/process/sprints"
        / "2026-08-06-CONTROLE-SONY-MEDIDO-01-o-experimento-que-decide-"
        "metade-da-doutrina.md"
    )
    assert sprint.is_file(), "a sprint que mede mudou de nome; o portão perdeu a âncora"
    assert frases_refutadas_em(sprint.read_text(encoding="utf-8")), (
        "a sprint deixou de citar a frase que ela derruba — ou o portão parou "
        "de reconhecê-la, e nesse caso ele não está cobrando nada"
    )
