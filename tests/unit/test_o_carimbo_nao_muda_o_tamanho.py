"""O carimbo da casa não muda de TAMANHO com o estado da árvore de quem gerou.

Sprint `O-TAMANHO-QUE-DEPENDE-DA-ARVORE-01` (20/09/2026).

O DEFEITO QUE ESTA RÉGUA EXISTE PARA PEGAR
------------------------------------------
De 25/08 a 20/09/2026 o rodapé das páginas HTML geradas trazia
`· árvore com N mudança(s) não commitada(s)`. Essa frase **muda de comprimento
com N** — «2» e «13» não ocupam o mesmo espaço — e **some inteira** quando a
árvore está limpa. O `git status` de quem gerou virava bytes do produto.

O sintoma chegou como um vermelho que se lia como outra coisa: o
`numero-caduco` do `LEIA-PRIMEIRO` dizia que o mapa de canais publicava
2.280.044 bytes e que a medição de agora dizia 2.280.091.

Os 47 bytes de diferença são exatamente o carimbo de uma árvore suja menos o de
uma limpa. Rodar a cura que o próprio erro imprime gravava um TERCEIRO número,
porque a árvore mudava de estado entre as corridas — três números para o mesmo
arquivo, no mesmo minuto, sem que uma vírgula do dado tivesse mudado.

O NOME DA BRANCH SAIU JUNTO — 20/09/2026, NA CONFERÊNCIA
--------------------------------------------------------
A sprint mandou tirar só a contagem e escreveu *"o commit e a branch FICAM:
eles dizem de que fonte o arquivo saiu, e o hash tem comprimento fixo"*. A razão
é sobre o HASH. O nome da branch não tem largura fixa, e a leva que curou a
contagem provou isso nela mesma: regerou as quatro páginas na worktree
`worktree-wf_7917c453-7ab-2` e elas ficaram +92, +46, +23 e +23 bytes contra
`dev`, e o `LEIA-PRIMEIRO` passou a publicar 2.280.067 onde `dev` mede
2.280.044 — o número que o documento já trazia CERTO.

A própria sprint fecha o argumento: *"se a casa quiser manter a contagem, então
o `LEIA-PRIMEIRO` não pode publicar o TAMANHO desse arquivo"*. A casa manteve o
tamanho publicado; logo nada de largura variável cabe no carimbo — nem a
contagem, nem a branch. A divergência entre páginas irmãs sempre se leu POR
COMMIT, e o nome da branch não fazia falta a ninguém.

O QUE A MORDIDA ARRANCA
-----------------------
Devolver a `procedencia()` a chave `sujos` e ao `carimbo()` o trecho
`· árvore com {sujos} mudança(s) não commitada(s)`, ou devolver a chave
`branch` e o trecho `na branch <code>{branch}</code>` (arrancados em
20/09/2026, `scripts/carimbo_da_casa.py`). Com a cura arrancada, medido:

    test_o_carimbo_nao_muda_com_a_sujeira_da_arvore .. 196/243/244/243/243 bytes
    test_o_carimbo_nao_pergunta_o_estado_da_arvore ... `git status --porcelain`
    test_a_procedencia_declara_so_a_fonte ........... a chave, nomeada
    test_o_carimbo_nao_muda_com_o_nome_da_branch .... 223 → 246 bytes
    test_a_pagina_publicada_... ..................... 5 campos onde cabiam 4,
                                                      e a palavra `branch`

Devolvida a cura, as sete passam. Cada teste diz, no próprio docstring, a
mutação que o faz reprovar e o número que ela produziu.

AS DUAS MUTAÇÕES QUE ESTA FOLHA DEIXAVA PASSAR, E COMO ELAS FORAM FECHADAS
--------------------------------------------------------------------------
Medidas na conferência de 20/09/2026, com as oito réguas de então VERDES:

    "commit": hash + ("-sujo" if `git diff-index --quiet HEAD --` else "")
    "branch": branch + (" (árvore suja)" if `git ls-files --modified` else "")

As duas devolvem o defeito da sprint — medidas com a folha de hoje, a primeira
dá 196/196/196/**201**/**201** bytes pelos cinco estados e a segunda
196/196/196/**211**/196 —, e as duas escapavam por DOIS buracos somados:

  - a régua do efeito só criava arquivo NÃO RASTREADO, e `diff-index` e
    `ls-files --modified` são cegos a ele. Hoje ela atravessa CINCO estados,
    dois deles rastreados (`ESTADOS`);
  - a régua da raiz casava o nome do subcomando por igualdade, então
    `diff-index` não casava com `"diff"` nem `--modified` com `-m`. Hoje o
    casamento é por FAMÍLIA (`_pergunta_o_estado`).

A página que o repositório carrega é uma só, o mapa de canais, e o caminho
dela vem do dono (`SPECS_RELATIVO`, no portão). As outras páginas geradas não
se versionam, e nenhum número publicado as mede.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(RAIZ / "scripts"))
import carimbo_da_casa  # depende da linha acima: `scripts/` não é pacote
from check_paridade_transporte import SPECS_RELATIVO  # o dono do caminho do mapa

PUBLICADA = RAIZ / SPECS_RELATIVO

#: A marca da linha do carimbo, escrita À MÃO de propósito: importá-la do módulo
#: faria esta régua concordar com ele por construção, que é a tautologia de que
#: esta casa já morreu uma vez.
MARCA = "data-carimbo"

#: QUANTOS CAMPOS a linha tem, separados por `·`. Escritos à mão pela mesma
#: razão: «gerado em …», «commit …» e «por …». O link «índice dos instrumentos»
#: não entra no mapa publicado, porque o índice não viaja com ele. Um campo a
#: mais é um dado a mais viajando dentro do produto — foi assim que a sujeira
#: da árvore entrou.
CAMPOS_ESPERADOS = 3

#: As palavras com que a MESA de quem gerou chega a uma linha de rodapé. A
#: contagem de campos acima é a régua contra um campo NOVO; esta lista é a régua
#: contra a mesma coisa COLADA num campo que já existe — «por <gerador> (árvore
#: suja)» tem os mesmos campos e carrega o estado do mesmo jeito.
#:
#: `branch` está na lista desde 20/09/2026: o nome da branch saiu do carimbo por
#: ter largura variável, e ele voltaria DENTRO do campo do commit, sem mexer na
#: contagem (medido: até 92 bytes por página entre `dev` e uma worktree de
#: agente).
PALAVRAS_DE_ESTADO = (
    "commitada", "commitado", "sujo", "suja", "staged", "modificad", "branch",
)


#: Os subcomandos do `git` que respondem "como está a MESA de quem gerou".
#: Casam por FAMÍLIA, não por nome exato: `diff` alcança `diff-index`,
#: `diff-files` e `diff-tree`.
#:
#: A LISTA ERA DE NOMES EXATOS até 20/09/2026, e o buraco foi medido na
#: conferência: `git diff-index --quiet HEAD` — que é a forma canônica de
#: perguntar isto num script — não casava com `"diff"`, e `git ls-files
#: --modified` não casava com a exceção escrita para `-m`. Uma reintrodução da
#: sujeira por qualquer um dos dois atravessava as oito réguas desta folha.
SUBCOMANDOS_DE_ESTADO = ("status", "describe", "stash", "diff")

#: As bandeiras que transformam um `ls-files` (que lista o ÍNDICE, e não é
#: estado) numa pergunta sobre a mesa. As formas curta e longa, as duas.
BANDEIRAS_DE_ESTADO = (
    "-m", "--modified", "-d", "--deleted", "-o", "--others", "-u", "--unmerged",
)


def _pergunta_o_estado(tokens: list[str]) -> bool:
    """Este comando pergunta ao `git` como está a árvore de quem gerou?"""
    for token in tokens:
        if any(
            token == base or token.startswith(f"{base}-")
            for base in SUBCOMANDOS_DE_ESTADO
        ):
            return True
        if "porcelain" in token or token == "--dirty":
            return True
    return "ls-files" in tokens and any(b in tokens for b in BANDEIRAS_DE_ESTADO)


def _git_existe() -> bool:
    return shutil.which("git") is not None


def _arvore_de_brinquedo(raiz: Path, ganchos_vazios: Path) -> None:
    """Um repositório de verdade, com um commit, na branch `dev`.

    De verdade porque quem sabe se a árvore está suja é o `git`, e montar o
    esperado com as mesmas constantes que a função lê é tautologia. `git` é o
    dono da resposta, e é a ele que esta régua pergunta.

    Os ganchos vão para uma pasta vazia: esta casa tem `core.hooksPath` global,
    e um gancho de mensagem de commit faria o brinquedo falhar por um motivo
    que não tem nada a ver com o que se mede aqui.
    """
    raiz.mkdir(parents=True, exist_ok=True)

    def git(*args: str) -> None:
        pronto = subprocess.run(
            [
                "git",
                "-c", f"core.hooksPath={ganchos_vazios}",
                "-c", "commit.gpgsign=false",
                *args,
            ],
            cwd=raiz, capture_output=True, text=True, timeout=30,
        )
        assert pronto.returncode == 0, (
            f"git {' '.join(args)} falhou no repositório de brinquedo:\n"
            f"{pronto.stdout}{pronto.stderr}"
        )

    git("init", "-q", "-b", "dev")
    git("config", "user.email", "brinquedo@exemplo.invalido")
    git("config", "user.name", "Repositório de brinquedo")
    (raiz / "a.txt").write_text("a\n", encoding="utf-8")
    git("add", "a.txt")
    git("commit", "-qm", "o commit que dá um HEAD ao brinquedo")


def _rodar_git(raiz: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Um `git` no brinquedo, com os ganchos da casa fora do caminho."""
    return subprocess.run(
        [
            "git",
            "-c", f"core.hooksPath={raiz.parent / 'sem-ganchos'}",
            "-c", "commit.gpgsign=false",
            *args,
        ],
        cwd=raiz, capture_output=True, text=True, timeout=30,
    )


#: OS CINCO ESTADOS DE ÁRVORE, e a razão de os dois últimos existirem.
#:
#: Até 20/09/2026 esta folha só criava arquivo NÃO RASTREADO — o arranjo FÁCIL.
#: `git diff-index --quiet HEAD` e `git ls-files --modified` são CEGOS a arquivo
#: não rastreado, então uma reintrodução da sujeira por qualquer um dos dois
#: passava por baixo das oito réguas daqui. Medido na conferência, com a cura
#: arrancada por `diff-index`: árvore limpa 196 bytes, arquivo RASTREADO
#: modificado 201 — e as oito de então verdes.
ESTADOS = (
    "limpa",
    "2 arquivos não rastreados",
    "13 arquivos não rastreados",
    "1 arquivo rastreado, modificado no disco",
    "1 arquivo rastreado, modificado e no índice",
)


def _pondo(raiz: Path, estado: str) -> None:
    if estado == "limpa":
        return
    if estado.endswith("não rastreados"):
        for i in range(int(estado.split()[0])):
            (raiz / f"sujo{i}.txt").write_text("x\n", encoding="utf-8")
        return
    (raiz / "a.txt").write_text("a mexido pela régua\n", encoding="utf-8")
    if "índice" in estado:
        assert _rodar_git(raiz, "add", "a.txt").returncode == 0


def _devolvendo(raiz: Path) -> None:
    for sujo in raiz.glob("sujo*.txt"):
        sujo.unlink()
    (raiz / "a.txt").write_text("a\n", encoding="utf-8")
    _rodar_git(raiz, "reset", "-q")
    assert not _rodar_git(raiz, "status", "--porcelain").stdout.strip(), (
        "o brinquedo não voltou a ficar limpo entre dois estados — as medições "
        "seguintes mediriam outra coisa."
    )


@pytest.fixture()
def brinquedo(tmp_path: Path) -> Path:
    if not _git_existe():
        pytest.skip("sem `git` nesta máquina: a sujeira da árvore não se mede")
    ganchos = tmp_path / "sem-ganchos"
    ganchos.mkdir()
    raiz = tmp_path / "arvore"
    _arvore_de_brinquedo(raiz, ganchos)
    return raiz


# --------------------------------------------------------------------------
# A régua: o carimbo é o MESMO, byte a byte, seja qual for o estado da árvore
# --------------------------------------------------------------------------
def test_o_carimbo_nao_muda_com_a_sujeira_da_arvore(brinquedo: Path) -> None:
    """Os CINCO estados de árvore dão o MESMO carimbo, byte a byte.

    Os três primeiros são a mordida da sprint: 0 porque a frase sumia quando a
    árvore estava limpa, 2 e 13 porque o número de DÍGITOS de N também conta —
    «2» e «13» não ocupam o mesmo espaço.

    OS DOIS ÚLTIMOS SÃO DA CONFERÊNCIA, e são o arranjo DIFÍCIL: arquivo
    RASTREADO, modificado no disco e modificado no índice. `git status
    --porcelain` vê os cinco, mas `git diff-index --quiet HEAD` e `git ls-files
    --modified` só veem estes dois — e era por eles que uma reintrodução da
    sujeira passava com as oito réguas verdes.

    MORDIDA, as duas medidas em 20/09/2026:
      - devolver `sujeira` ao `carimbo()` por `git status --porcelain` dá
        196 / 243 / 244 / 243 / 243 bytes;
      - pendurar `-sujo` no commit por `git diff-index --quiet HEAD` dá
        196 / 196 / 196 / **201** / **201** — e só os dois últimos estados o
        revelam.
    """
    esperado_sujo = {e for e in ESTADOS if e != "limpa"}
    colhido: dict[str, str] = {}
    for estado in ESTADOS:
        _pondo(brinquedo, estado)
        porcelana = _rodar_git(brinquedo, "status", "--porcelain").stdout.strip()
        rastreado = _rodar_git(brinquedo, "diff-index", "--quiet", "HEAD", "--")
        # O DONO DA RESPOSTA É O `git`, e é a ele que se confere o cenário: sem
        # isto, um `_pondo()` que deixasse de sujar faria as cinco medições
        # baterem por não haver nada a medir — a régua daria verde sobre nada.
        assert bool(porcelana) == (estado in esperado_sujo), (
            f"o estado {estado!r} não chegou ao brinquedo: "
            f"`git status --porcelain` devolveu {porcelana!r}."
        )
        if "rastreado," in estado:
            assert rastreado.returncode != 0, (
                f"o estado {estado!r} não sujou nada RASTREADO — "
                "`git diff-index --quiet HEAD` diz que a árvore está limpa, e "
                "este teste voltaria a medir só o arranjo fácil."
            )
        colhido[estado] = carimbo_da_casa.carimbo(
            "scripts/gerar-mapa.py", raiz=brinquedo
        )
        _devolvendo(brinquedo)

    tamanhos = {e: len(linha.encode("utf-8")) for e, linha in colhido.items()}
    assert len(set(colhido.values())) == 1, (
        "o carimbo muda com o estado da árvore de quem gerou — "
        f"tamanhos em bytes por estado: {tamanhos}.\n"
        "O produto passa a carregar o `git status` de quem apertou o botão, e o "
        "tamanho publicado em `docs/data/LEIA-PRIMEIRO.md` caduca sem que o dado "
        "tenha mudado.\n"
        "As linhas colhidas:\n  "
        + "\n  ".join(f"{e}: {linha}" for e, linha in colhido.items())
    )


def test_o_carimbo_nao_pergunta_o_estado_da_arvore(
    brinquedo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Montar o carimbo não roda um só comando que leia o estado da árvore.

    Esta é a régua da RAIZ: a de cima pega o efeito (bytes a mais), esta pega a
    causa (perguntar ao `git` como está a mesa). Ela alcança a família `diff`
    inteira, um `ls-files` com bandeira de estado e um `describe --dirty` que
    voltassem com outra redação — e NOMEIA o comando na mensagem.

    MORDIDA, as quatro medidas em 20/09/2026:
      - `_git("status", "--porcelain", …)` de volta em `procedencia()` reprova
        com *"git status --porcelain"* no erro;
      - `rev-parse --short HEAD` trocado por `describe --always --dirty` reprova
        com *"git describe --always --dirty"* — e essa passa por baixo das
        outras réguas, porque `--dirty` marca o estado sem mudar o número de
        campos da linha;
      - `git diff-index --quiet HEAD --` pendurando `-sujo` no commit (196 →
        201 bytes num arquivo RASTREADO modificado);
      - `git ls-files --modified` colado no campo do commit (196 → 211).

    AS DUAS ÚLTIMAS SÃO DA CONFERÊNCIA, e as duas atravessavam esta folha
    inteira: a lista de proibidos era de nomes EXATOS, então `diff-index` não
    casava com `"diff"` e `--modified` não casava com a exceção escrita para
    `-m`. Hoje o casamento é por FAMÍLIA (`_pergunta_o_estado`).
    """
    perguntas: list[list[str]] = []
    original = subprocess.run

    def espiao(args, *resto, **chaves):  # type: ignore[no-untyped-def]
        if isinstance(args, (list, tuple)):
            perguntas.append([str(a) for a in args])
        return original(args, *resto, **chaves)

    monkeypatch.setattr(carimbo_da_casa.subprocess, "run", espiao)
    _pondo(brinquedo, "1 arquivo rastreado, modificado no disco")
    carimbo_da_casa.carimbo("scripts/gerar-mapa.py", raiz=brinquedo)

    achados = [" ".join(p) for p in perguntas if _pergunta_o_estado(p)]
    assert not achados, (
        "o carimbo pergunta ao `git` como está a árvore de quem gerou: "
        + "; ".join(achados)
        + ".\nO que essa resposta vira é texto dentro do arquivo publicado, e "
        "texto de comprimento variável muda o TAMANHO do produto. Procedência é "
        "de onde a página SAIU (commit, branch), não como estava a mesa."
    )


def test_a_procedencia_declara_so_a_fonte(brinquedo: Path) -> None:
    """`procedencia()` devolve o commit — e nada sobre a mesa de quem gerou.

    A CHAVE `branch` SAIU EM 20/09/2026, junto com `sujos` e pelo mesmo motivo:
    largura variável dentro de um arquivo cujo TAMANHO é publicado. A sprint
    mandou mantê-la, escrevendo *"o hash tem comprimento fixo"* — razão que vale
    para o hash e não para o nome da branch. A conferência mediu: as quatro
    páginas regeradas na worktree `worktree-wf_7917c453-7ab-2` ficaram 23, 23,
    46 e 92 bytes maiores que em `dev`, e o `LEIA-PRIMEIRO` publicou 2.280.067
    onde `dev` mede 2.280.044.

    MORDIDA: devolver `sujos` ou `branch` faz reprovar NOMEANDO a chave.
    """
    _pondo(brinquedo, "1 arquivo rastreado, modificado e no índice")
    p = carimbo_da_casa.procedencia(raiz=brinquedo)
    assert set(p) == {"commit"}, (
        f"`procedencia()` devolve {sorted(p)}; esperado ['commit'].\n"
        "Toda chave a mais aqui vira texto no rodapé das páginas geradas. Se ela "
        "descrever a MESA de quem gerou — o estado da árvore, o nome da branch "
        "— o tamanho do arquivo passa a depender de onde alguém apertou o botão "
        "(ver o docstring de `procedencia()`)."
    )
    # O DONO DA RESPOSTA É O `git`, e a pergunta é OUTRA: o hash INTEIRO. Casar
    # o curto com o curto rodaria o mesmo comando que a função roda — tautologia.
    inteiro = _rodar_git(brinquedo, "rev-parse", "HEAD").stdout.strip()
    assert inteiro.startswith(p["commit"]) and p["commit"] != "?", (
        f"`procedencia()` leu o commit {p['commit']!r}, que não é um prefixo do "
        f"HEAD do brinquedo ({inteiro!r}) — a régua não está falando com o "
        "repositório que ela montou."
    )


def test_trocar_o_commit_nao_muda_o_tamanho_do_carimbo(brinquedo: Path) -> None:
    """O commit FICA no carimbo, e pode: o hash curto tem largura fixa.

    A sprint manteve commit e branch justamente por isso. Esta régua é o que
    sustenta a afirmação — ela reprova se alguém trocar o hash curto por algo de
    largura variável, como `git describe`.

    MORDIDA, medida em 20/09/2026: pendurar no carimbo o ASSUNTO do commit —
    `_git("log", "-1", "--format=%s")`, que é o que o painel local já faz no
    corpo dele — faz o carimbo ir de 274 a 253 bytes entre dois
    commits do mesmo repositório.

    Medido e ANOTADO porque engana: trocar o hash curto por
    `describe --always --dirty` NÃO faz esta régua reprovar (sem tag, o
    `describe` devolve o mesmo hash curto, de largura fixa). Quem pega essa é a
    `test_o_carimbo_nao_pergunta_o_estado_da_arvore`. Duas réguas independentes
    é o que revela; é regra desta casa.
    """
    antes = carimbo_da_casa.carimbo("scripts/gerar-mapa.py", raiz=brinquedo)
    (brinquedo / "b.txt").write_text("b\n", encoding="utf-8")
    ganchos = brinquedo.parent / "sem-ganchos"
    for args in (("add", "b.txt"), ("commit", "-qm", "o segundo commit")):
        subprocess.run(
            ["git", "-c", f"core.hooksPath={ganchos}", "-c", "commit.gpgsign=false", *args],
            cwd=brinquedo, capture_output=True, text=True, timeout=30, check=True,
        )
    depois = carimbo_da_casa.carimbo("scripts/gerar-mapa.py", raiz=brinquedo)

    assert antes != depois, (
        "o carimbo não mudou com o commit — ele deixou de dizer de que fonte a "
        "página saiu, que é a única razão de ele existir."
    )
    assert len(antes.encode("utf-8")) == len(depois.encode("utf-8")), (
        "trocar de commit mudou o TAMANHO do carimbo "
        f"({len(antes.encode())} → {len(depois.encode())} bytes).\n"
        f"  antes:  {antes}\n  depois: {depois}\n"
        "O hash curto tem largura fixa; algo de largura variável (um "
        "`git describe`, uma marca `-dirty`) devolve o defeito que a sprint "
        "`O-TAMANHO-QUE-DEPENDE-DA-ARVORE-01` fechou."
    )


def test_o_carimbo_nao_muda_com_o_nome_da_branch(brinquedo: Path) -> None:
    """A mesma árvore, no mesmo commit, em duas branches: o MESMO carimbo.

    O nome da branch não é a FONTE da página — a fonte é o commit, e a página é
    publicada em `dev`. Dizer que ela saiu de `worktree-wf_7917c453-7ab-2` é
    declarar a mesa de quem passou por ali, que é o que a sprint mandou tirar; e
    o nome tem largura variável, que é o defeito que ela fechou.

    MEDIDO NA CONFERÊNCIA, 20/09/2026, na leva que curou a contagem de sujos e
    regerou as quatro páginas numa worktree de agente:

        o índice ................ +92 bytes contra `dev`
        o painel ................ +46
        o mapa de canais ........ +23
        as frases de tela ....... +23

    e o `docs/data/LEIA-PRIMEIRO.md` passou a publicar 2.280.067 onde `dev` mede
    2.280.044 — o número que o documento já trazia CERTO antes da leva.

    MORDIDA: devolver `na branch <code>{branch}</code>` ao `carimbo()` leva os
    dois carimbos a 223 e 246 bytes.
    """
    em_dev = carimbo_da_casa.carimbo("scripts/gerar-mapa.py", raiz=brinquedo)
    assert _rodar_git(
        brinquedo, "checkout", "-q", "-b", "worktree-wf_7917c453-7ab-2"
    ).returncode == 0
    # O DONO DA RESPOSTA É O `git`: sem conferir, um `checkout` que falhasse em
    # silêncio faria os dois carimbos baterem por serem o mesmo cenário.
    agora_em = _rodar_git(brinquedo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    assert agora_em == "worktree-wf_7917c453-7ab-2", (
        f"o brinquedo não trocou de branch (está em {agora_em!r}) — esta régua "
        "estaria comparando o mesmo cenário consigo mesmo."
    )
    na_worktree = carimbo_da_casa.carimbo("scripts/gerar-mapa.py", raiz=brinquedo)

    assert em_dev == na_worktree, (
        "o carimbo muda com o NOME DA BRANCH de quem gerou "
        f"({len(em_dev.encode())} → {len(na_worktree.encode())} bytes).\n"
        f"  em `dev`:      {em_dev}\n  na worktree:   {na_worktree}\n"
        f"O tamanho de `{SPECS_RELATIVO}` é publicado em "
        "`docs/data/LEIA-PRIMEIRO.md` e tem portão: toda página regerada fora "
        "de `dev` grava um número que reprova assim que o merge acontece."
    )


# --------------------------------------------------------------------------
# O produto: o mapa de canais publicado
# --------------------------------------------------------------------------
def _linha_do_carimbo() -> str:
    if not PUBLICADA.is_file():
        pytest.fail(
            f"{SPECS_RELATIVO} não está no disco — regere:\n"
            "  python3 scripts/gerar-mapa.py"
        )
    linhas = [
        ln for ln in PUBLICADA.read_text(encoding="utf-8", errors="replace").splitlines()
        if MARCA in ln
    ]
    assert len(linhas) == 1, (
        f"{SPECS_RELATIVO} tem {len(linhas)} linha(s) com `{MARCA}`; esperado 1."
    )
    return linhas[0]


def test_a_pagina_publicada_nao_carrega_a_sujeira_de_quem_gerou() -> None:
    """O carimbo do mapa publicado tem os campos de hoje, e só eles.

    SÃO DUAS RÉGUAS INDEPENDENTES, e é de propósito. A contagem de campos pega
    um campo NOVO com qualquer redação. As PALAVRAS pegam a mesma coisa colada
    dentro de um campo que já existe — «por <gerador> (árvore suja)» tem os
    mesmos campos e carrega o estado do mesmo jeito, e foi assim que uma
    mutação da conferência atravessou esta régua quando ela era só a contagem.

    MORDIDA, as duas medidas em 20/09/2026:
      - o mapa publicado de antes da leva trazia «árvore com 5 mudança(s)
        não commitada(s)» — um campo a mais;
      - o de antes da conferência trazia «na branch
        <code>worktree-wf_7917c453-7ab-2</code>» — os mesmos campos, e a
        palavra `branch` é quem o denuncia.
    """
    linha = _linha_do_carimbo()
    miolo = re.sub(r"<[^>]+>", "", linha)
    campos = [pedaco.strip() for pedaco in miolo.split("·") if pedaco.strip()]
    nomeadas = [p for p in PALAVRAS_DE_ESTADO if p in linha.lower()]
    assert not nomeadas, (
        f"o carimbo de {SPECS_RELATIVO} carrega a MESA de quem gerou — as "
        f"palavras {nomeadas} estão na linha:\n  {linha}\n"
        "Nada de largura variável cabe aqui: o tamanho do mapa é publicado em "
        "`docs/data/LEIA-PRIMEIRO.md` e tem portão.\n"
        "Regere a página depois de curar o `scripts/carimbo_da_casa.py`."
    )
    assert len(campos) == CAMPOS_ESPERADOS, (
        f"o carimbo de {SPECS_RELATIVO} tem {len(campos)} campo(s); esperado "
        f"{CAMPOS_ESPERADOS}.\n  {linha}\n"
        "Regere a página depois de curar o `scripts/carimbo_da_casa.py`."
    )


def test_o_mapa_publicado_nao_liga_para_o_que_nao_viaja() -> None:
    """O rodapé do mapa não aponta para o índice das páginas locais.

    O `docs/specs.html` viaja no repositório; o índice mora numa pasta que não
    se versiona. Um link para ele é um link quebrado para quem clona — e o
    carimbo o emite por padrão, então quem o tira é o gerador
    (`carimbo(..., indice=False)`).

    MORDIDA, medida em 28/09/2026: devolver o `indice=False` ao padrão no
    `scripts/gerar-mapa.py` e regerar faz esta régua reprovar com o link na
    mensagem.
    """
    pagina = PUBLICADA.read_text(encoding="utf-8", errors="replace")
    achados = [ln.strip()[:200] for ln in pagina.splitlines() if "index.html" in ln]
    assert not achados, (
        f"{SPECS_RELATIVO} liga para o índice, que não viaja com ele:\n  "
        + "\n  ".join(achados)
        + "\nChame o carimbo com `indice=False` no `scripts/gerar-mapa.py` e regere."
    )
