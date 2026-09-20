"""O carimbo da casa não muda de TAMANHO com o estado da árvore de quem gerou.

Sprint `O-TAMANHO-QUE-DEPENDE-DA-ARVORE-01` (20/09/2026).

O DEFEITO QUE ESTA RÉGUA EXISTE PARA PEGAR
------------------------------------------
De 25/08 a 20/09/2026 o rodapé dos quatro instrumentos HTML trazia
`· árvore com N mudança(s) não commitada(s)`. Essa frase **muda de comprimento
com N** — «2» e «13» não ocupam o mesmo espaço — e **some inteira** quando a
árvore está limpa. O `git status` de quem gerou virava bytes do produto.

O sintoma chegou como um vermelho que se lia como outra coisa:

    FALHA numero-caduco: `bytes:html/specs.html` publica 2.280.044
                         e a medição de agora diz 2.280.091

Os 47 bytes de diferença são exatamente o carimbo de uma árvore suja menos o de
uma limpa. Rodar a cura que o próprio erro imprime gravava um TERCEIRO número,
porque a árvore mudava de estado entre as corridas — três números para o mesmo
arquivo, no mesmo minuto, sem que uma vírgula do dado tivesse mudado.

O QUE A MORDIDA ARRANCA
-----------------------
Devolver a `procedencia()` a chave `sujos` e ao `carimbo()` o trecho
`· árvore com {sujos} mudança(s) não commitada(s)` (arrancado em 20/09/2026,
`scripts/carimbo_da_casa.py`). Com a cura arrancada, medido:

    test_o_carimbo_nao_muda_com_a_sujeira_da_arvore .... 223 / 270 / 271 bytes
    test_o_carimbo_nao_pergunta_o_estado_da_arvore ..... `git status --porcelain`
    test_a_procedencia_declara_so_a_fonte ............. chave `sujos` de volta
    test_a_pagina_publicada_...(as quatro páginas) .... 5 campos onde cabem 4

Devolvida a cura, as oito passam. Cada teste diz, no próprio docstring, a
mutação que o faz reprovar e o número que ela produziu.

O QUE ESTA RÉGUA NÃO COBRE, E ESTÁ DECLARADO
--------------------------------------------
1. `scripts/gerar-painel.py` escreve, no CORPO do painel, um parágrafo próprio
   «Árvore: N arquivo(s) com mudança não commitada em <commit>». Ele NÃO é o
   carimbo: é um cartão de um painel que existe para relatar o estado do
   projeto, ele já sai do `--check` por `_recorta_selo`, e nenhum número
   publicado mede `html/painel.html`. Fica de fora por decisão, não por
   esquecimento.
2. O NOME DA BRANCH também tem comprimento variável, e a sprint decidiu que
   commit e branch FICAM. Medido em 20/09/2026: gerar em `dev` e gerar numa
   worktree de agente (`worktree-wf_7917c453-7ab-2`) dá uma diferença de 23
   bytes na página. Quem regerar as páginas numa branch e publicar o tamanho
   noutra vai ver `test_o_documento_confere_com_a_medicao_de_agora`
   (`tests/unit/test_leia_primeiro_nao_digita_numero_a_mao.py`) reprovar — e a
   causa é essa, não a sujeira da árvore.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PASTA = RAIZ / "html"

sys.path.insert(0, str(RAIZ / "scripts"))
import carimbo_da_casa  # depende da linha acima: `scripts/` não é pacote

#: A marca da linha do carimbo, escrita À MÃO de propósito: importá-la do módulo
#: faria esta régua concordar com ele por construção, que é a tautologia de que
#: esta casa já morreu uma vez.
MARCA = "data-carimbo"

#: QUANTOS CAMPOS a linha tem, separados por `·`. Escritos à mão pela mesma
#: razão. Hoje: «gerado em …», «commit … na branch …», «por …» e, nas três que
#: não são o índice, «índice dos instrumentos». Um campo a mais é um dado a mais
#: viajando dentro do produto — foi assim que a sujeira da árvore entrou.
CAMPOS_ESPERADOS = {
    "index.html": 3,
    "specs.html": 4,
    "painel.html": 4,
    "frases-de-tela.html": 4,
}

#: As palavras com que um "estado da árvore" chega a uma linha de rodapé. Elas
#: NÃO são a régua — a régua é a contagem de campos, que pega qualquer
#: redação. Elas existem para a mensagem de erro NOMEAR o que voltou.
PALAVRAS_DE_ESTADO = ("commitada", "commitado", "sujo", "staged", "modificad")


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


def _sujar(raiz: Path, quantos: int) -> None:
    for i in range(quantos):
        (raiz / f"sujo{i}.txt").write_text("x\n", encoding="utf-8")


def _limpar(raiz: Path, quantos: int) -> None:
    for i in range(quantos):
        (raiz / f"sujo{i}.txt").unlink()


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
    """Zero, dois e treze arquivos sujos dão o MESMO carimbo, byte a byte.

    Os três números são a mordida inteira da sprint: 0 porque a frase sumia
    quando a árvore estava limpa, 2 e 13 porque o número de DÍGITOS de N também
    conta — «2» e «13» não ocupam o mesmo espaço.

    MORDIDA: devolver `sujeira` ao `carimbo()` dá 223, 270 e 271 bytes.
    """
    colhido: dict[int, str] = {}
    for quantos in (0, 2, 13):
        _sujar(brinquedo, quantos)
        colhido[quantos] = carimbo_da_casa.carimbo(
            "scripts/gerar-mapa.py", raiz=brinquedo
        )
        _limpar(brinquedo, quantos)

    tamanhos = {n: len(linha.encode("utf-8")) for n, linha in colhido.items()}
    assert len(set(colhido.values())) == 1, (
        "o carimbo muda com o estado da árvore de quem gerou — "
        f"tamanhos em bytes por número de arquivos sujos: {tamanhos}.\n"
        "O produto passa a carregar o `git status` de quem apertou o botão, e o "
        "tamanho publicado em `docs/data/LEIA-PRIMEIRO.md` caduca sem que o dado "
        "tenha mudado.\n"
        "As linhas colhidas:\n  "
        + "\n  ".join(f"{n:>2} sujos: {linha}" for n, linha in colhido.items())
    )


def test_o_carimbo_nao_pergunta_o_estado_da_arvore(
    brinquedo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Montar o carimbo não roda um só comando que leia o estado da árvore.

    Esta é a régua da RAIZ: a de cima pega o efeito (bytes a mais), esta pega a
    causa (perguntar ao `git` como está a mesa). Ela alcança um `git diff`, um
    `git ls-files -m` ou um `git describe --dirty` que voltassem com outra
    redação — e NOMEIA o comando na mensagem.

    MORDIDA, as duas medidas em 20/09/2026: devolver a linha
    `_git("status", "--porcelain", …)` a `procedencia()` reprova com
    *"git status --porcelain"* no erro; trocar `rev-parse --short HEAD` por
    `describe --always --dirty` reprova com *"git describe --always --dirty"* —
    e essa segunda passa por baixo das outras réguas, porque `--dirty` marca o
    estado da árvore sem mudar o número de campos da linha.
    """
    perguntas: list[list[str]] = []
    original = subprocess.run

    def espiao(args, *resto, **chaves):  # type: ignore[no-untyped-def]
        if isinstance(args, (list, tuple)):
            perguntas.append([str(a) for a in args])
        return original(args, *resto, **chaves)

    monkeypatch.setattr(carimbo_da_casa.subprocess, "run", espiao)
    _sujar(brinquedo, 3)
    carimbo_da_casa.carimbo("scripts/gerar-mapa.py", raiz=brinquedo)

    proibidos = ("status", "diff", "describe", "stash")
    achados = [
        " ".join(p) for p in perguntas
        if any(termo in p for termo in proibidos)
        or ("ls-files" in p and "-m" in p)
    ]
    assert not achados, (
        "o carimbo pergunta ao `git` como está a árvore de quem gerou: "
        + "; ".join(achados)
        + ".\nO que essa resposta vira é texto dentro do arquivo publicado, e "
        "texto de comprimento variável muda o TAMANHO do produto. Procedência é "
        "de onde a página SAIU (commit, branch), não como estava a mesa."
    )


def test_a_procedencia_declara_so_a_fonte(brinquedo: Path) -> None:
    """`procedencia()` devolve commit e branch — e nada sobre a mesa.

    MORDIDA: devolver a chave `sujos` faz reprovar nomeando a chave.
    """
    _sujar(brinquedo, 4)
    p = carimbo_da_casa.procedencia(raiz=brinquedo)
    assert set(p) == {"commit", "branch"}, (
        f"`procedencia()` devolve {sorted(p)}; esperado ['branch', 'commit'].\n"
        "Toda chave a mais aqui vira texto no rodapé das quatro páginas. Se ela "
        "descrever o ESTADO da árvore, o tamanho do arquivo passa a depender de "
        "quem gerou (ver o docstring de `procedencia()`)."
    )
    assert p["branch"] == "dev", (
        f"o brinquedo nasceu em `dev` e `procedencia()` leu {p['branch']!r} — "
        "a régua não está falando com o repositório que ela montou."
    )


def test_trocar_o_commit_nao_muda_o_tamanho_do_carimbo(brinquedo: Path) -> None:
    """O commit FICA no carimbo, e pode: o hash curto tem largura fixa.

    A sprint manteve commit e branch justamente por isso. Esta régua é o que
    sustenta a afirmação — ela reprova se alguém trocar o hash curto por algo de
    largura variável, como `git describe`.

    MORDIDA, medida em 20/09/2026: pendurar no carimbo o ASSUNTO do commit —
    `_git("log", "-1", "--format=%s")`, que é o que o `scripts/gerar-painel.py`
    já faz no corpo do painel — faz o carimbo ir de 274 a 253 bytes entre dois
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


# --------------------------------------------------------------------------
# O produto: as quatro páginas publicadas
# --------------------------------------------------------------------------
@pytest.mark.parametrize("nome", sorted(CAMPOS_ESPERADOS))
def test_a_pagina_publicada_nao_carrega_a_sujeira_de_quem_gerou(nome: str) -> None:
    """O carimbo de cada página publicada tem os campos de hoje, e só eles.

    A contagem de campos é a régua, e não a busca pela frase: ela pega a
    sujeira de volta com QUALQUER redação. As palavras só entram na mensagem,
    para nomear o que voltou.

    MORDIDA: o `html/specs.html` como estava antes desta leva trazia
    «árvore com 5 mudança(s) não commitada(s)» — 5 campos onde cabem 4.
    """
    caminho = PASTA / nome
    if not caminho.is_file():
        pytest.fail(
            f"html/{nome} não está no disco — regere as quatro:\n"
            "  python3 scripts/gerar-mapa.py && python3 scripts/gerar-painel.py "
            "&& python3 scripts/gerar-frases-de-tela.py "
            "&& python3 scripts/gerar-indice-html.py"
        )
    linhas = [
        ln for ln in caminho.read_text(encoding="utf-8", errors="replace").splitlines()
        if MARCA in ln
    ]
    assert len(linhas) == 1, (
        f"html/{nome} tem {len(linhas)} linha(s) com `{MARCA}`; esperado 1."
    )
    linha = linhas[0]

    miolo = re.sub(r"<[^>]+>", "", linha)
    campos = [pedaco.strip() for pedaco in miolo.split("·") if pedaco.strip()]
    nomeadas = [p for p in PALAVRAS_DE_ESTADO if p in linha.lower()]
    assert len(campos) == CAMPOS_ESPERADOS[nome], (
        f"o carimbo de html/{nome} tem {len(campos)} campo(s); esperado "
        f"{CAMPOS_ESPERADOS[nome]}.\n  {linha}\n"
        + (
            f"As palavras {nomeadas} dizem o que voltou: o ESTADO da árvore de "
            "quem gerou. Ele muda de comprimento e muda o tamanho do arquivo "
            "publicado.\n"
            if nomeadas else ""
        )
        + "Regere a página depois de curar o `scripts/carimbo_da_casa.py`."
    )
