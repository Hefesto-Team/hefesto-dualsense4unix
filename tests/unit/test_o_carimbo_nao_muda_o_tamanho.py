"""O carimbo da casa não muda de TAMANHO com o estado da árvore de quem gerou."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(RAIZ / "scripts"))
import carimbo_da_casa
from check_paridade_transporte import SPECS_RELATIVO

PUBLICADA = RAIZ / SPECS_RELATIVO

MARCA = "data-carimbo"

CAMPOS_ESPERADOS = 3

PALAVRAS_DE_ESTADO = (
    "commitada", "commitado", "sujo", "suja", "staged", "modificad", "branch",
)


SUBCOMANDOS_DE_ESTADO = ("status", "describe", "stash", "diff")

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
    """Um repositório de verdade, com um commit, na branch `dev`."""
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


def test_o_carimbo_nao_muda_com_a_sujeira_da_arvore(brinquedo: Path) -> None:
    """Os CINCO estados de árvore dão o MESMO carimbo, byte a byte."""
    esperado_sujo = {e for e in ESTADOS if e != "limpa"}
    colhido: dict[str, str] = {}
    for estado in ESTADOS:
        _pondo(brinquedo, estado)
        porcelana = _rodar_git(brinquedo, "status", "--porcelain").stdout.strip()
        rastreado = _rodar_git(brinquedo, "diff-index", "--quiet", "HEAD", "--")
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
    """Montar o carimbo não roda um só comando que leia o estado da árvore."""
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
    """`procedencia()` devolve o commit — e nada sobre a mesa de quem gerou."""
    _pondo(brinquedo, "1 arquivo rastreado, modificado e no índice")
    p = carimbo_da_casa.procedencia(raiz=brinquedo)
    assert set(p) == {"commit"}, (
        f"`procedencia()` devolve {sorted(p)}; esperado ['commit'].\n"
        "Toda chave a mais aqui vira texto no rodapé das páginas geradas. Se ela "
        "descrever a MESA de quem gerou — o estado da árvore, o nome da branch "
        "— o tamanho do arquivo passa a depender de onde alguém apertou o botão "
        "(ver o docstring de `procedencia()`)."
    )
    inteiro = _rodar_git(brinquedo, "rev-parse", "HEAD").stdout.strip()
    assert inteiro.startswith(p["commit"]) and p["commit"] != "?", (
        f"`procedencia()` leu o commit {p['commit']!r}, que não é um prefixo do "
        f"HEAD do brinquedo ({inteiro!r}) — a régua não está falando com o "
        "repositório que ela montou."
    )


def test_trocar_o_commit_nao_muda_o_tamanho_do_carimbo(brinquedo: Path) -> None:
    """O commit FICA no carimbo, e pode: o hash curto tem largura fixa."""
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
    """A mesma árvore, no mesmo commit, em duas branches: o MESMO carimbo."""
    em_dev = carimbo_da_casa.carimbo("scripts/gerar-mapa.py", raiz=brinquedo)
    assert _rodar_git(
        brinquedo, "checkout", "-q", "-b", "worktree-wf_7917c453-7ab-2"
    ).returncode == 0
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
    """O carimbo do mapa publicado tem os campos de hoje, e só eles."""
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
    """O rodapé do mapa não aponta para o índice das páginas locais."""
    pagina = PUBLICADA.read_text(encoding="utf-8", errors="replace")
    achados = [ln.strip()[:200] for ln in pagina.splitlines() if "index.html" in ln]
    assert not achados, (
        f"{SPECS_RELATIVO} liga para o índice, que não viaja com ele:\n  "
        + "\n  ".join(achados)
        + "\nChame o carimbo com `indice=False` no `scripts/gerar-mapa.py` e regere."
    )
