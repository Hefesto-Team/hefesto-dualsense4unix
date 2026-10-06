"""A release sai sozinha: um dono da versão, o CHANGELOG do fechado, e o que se baixa se confere.

Cada bloco prova uma peça de `scripts/release/` num repositório de brinquedo (git de verdade, tags e
commits de cada tipo, cópias dos alvos de versão do repositório real) e o `release.yml` contra o
`gh` de mentira de `tests/fixtures/github/gh_de_mentira.py`, que recusa o que o GitHub recusa (a
release imutável, o ruleset com a exceção de administrador). Nada daqui fala com o GitHub nem com o
PyPI.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

yaml = pytest.importorskip("yaml")

RAIZ = Path(__file__).resolve().parents[2]
RELEASE = RAIZ / "scripts" / "release"
VERSAO = RELEASE / "versao.py"
CHANGELOG = RELEASE / "changelog.py"
SUMS = RELEASE / "sums.py"
PUBLICAR = RELEASE / "publicar.py"
PACOTES = RELEASE / "pacotes.py"
PUBLICO = RELEASE / "publico.py"
RELEASE_YML = RAIZ / ".github" / "workflows" / "release.yml"
NOTAS_YML = RAIZ / ".github" / "release.yml"
REPOSITORIO_YML = RAIZ / ".github" / "repositorio.yml"
GH_DE_MENTIRA = RAIZ / "tests" / "fixtures" / "github" / "gh_de_mentira.py"
APLICAR = RAIZ / "scripts" / "github" / "aplicar.py"

# O que o `check_version_consistency.py` confere, copiado do repositório real para o brinquedo.
ALVOS_DE_VERSAO = (
    "pyproject.toml",
    "README.md",
    "src/hefesto_dualsense4unix/__init__.py",
    "packaging/arch/PKGBUILD",
    "packaging/fedora/hefesto-dualsense4unix.spec",
    "packaging/nix/package.nix",
    "packaging/debian/control",
    "assets/appimage/entrypoint.sh",
    "flatpak/io.github.hefesto_team.hefesto_dualsense4unix.metainfo.xml",
    "packaging/cosmic-applet/Cargo.toml",
    "packaging/cosmic-applet/Cargo.lock",
    "scripts/check_version_consistency.py",
    "scripts/check_texto_publico.py",
)

CHANGELOG_DO_BRINQUEDO = """# Changelog

## [Unreleased]

### Corrigido

- Item escrito à mão.

## [0.9.4.5] — 2026-08-20

### Adicionado

- Item antigo.
"""

REPOSITORIO_DO_BRINQUEDO = """versão: 1
release:
  serie: "{serie}"
rotulos:
  lista:
    - {{nome: "bug", cor: "d73a4a", descrição: "x"}}
    - {{nome: "área: tela", cor: "c5def5", descrição: "x"}}
    - {{nome: "área: som", cor: "c5def5", descrição: "x"}}
"""


def _env_git(data: str | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        GIT_AUTHOR_NAME="Pessoa Teste",
        GIT_AUTHOR_EMAIL="pessoa@exemplo.org",
        GIT_COMMITTER_NAME="Pessoa Teste",
        GIT_COMMITTER_EMAIL="pessoa@exemplo.org",
        GIT_CONFIG_GLOBAL="/dev/null",
        GIT_CONFIG_SYSTEM="/dev/null",
    )
    if data:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = f"{data}T12:00:00+00:00"
    return env


def git(raiz: Path, *args: str, data: str | None = None) -> str:
    r = subprocess.run(
        ["git", "-C", str(raiz), *args],
        capture_output=True,
        text=True,
        env=_env_git(data),
        check=False,
    )
    assert r.returncode == 0, f"git {args}: {r.stderr}"
    return r.stdout


def commitar(raiz: Path, assunto: str, data: str | None = None) -> None:
    git(raiz, "commit", "--allow-empty", "--no-verify", "-q", "-m", assunto, data=data)


def rodar(
    script: Path,
    *args: str,
    raiz: Path | None = None,
    entrada: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(script)]
    if raiz is not None and script.name in ("versao.py", "changelog.py", "pacotes.py"):
        cmd += ["--raiz", str(raiz)]
    return subprocess.run(
        cmd + list(args),
        capture_output=True,
        text=True,
        input=entrada,
        check=False,
        env=env or dict(os.environ),
    )


def primeira_linha(r: subprocess.CompletedProcess[str]) -> str:
    return (r.stdout.strip().splitlines() or [""])[0]


@pytest.fixture
def brinquedo(tmp_path: Path) -> Path:
    """Um brinquedo na série 0.9: a tag v0.9.4.5, a v4.0.0 (outra série) e os alvos de versão."""
    raiz = tmp_path / "brinquedo"
    raiz.mkdir()
    git(raiz, "init", "-q", "-b", "dev")
    for rel in ALVOS_DE_VERSAO:
        destino = raiz / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(RAIZ / rel, destino)
    # o README real é grande e traz a versão em duas linhas: o que importa aqui são elas
    (raiz / "CHANGELOG.md").write_text(CHANGELOG_DO_BRINQUEDO, encoding="utf-8")
    (raiz / ".github").mkdir()
    (raiz / ".github" / "repositorio.yml").write_text(
        REPOSITORIO_DO_BRINQUEDO.format(serie="0.9"), encoding="utf-8"
    )
    git(raiz, "add", "-A")
    commitar(raiz, "chore: base do brinquedo", data="2026-08-20")
    git(raiz, "tag", "v0.9.4.5")
    git(
        raiz, "tag", "v4.0.0"
    )  # outra numeração, mais alta: a série 0.9 não pode tomá-la por «última»
    return raiz


# ---------------------------------------------------------------------------
# 1. O dono da versão
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("commits", "esperada"),
    [
        (["feat(tela): uma aba nova"], "0.9.5"),
        (["fix(som): o microfone calava"], "0.9.4.6"),
        (["fix: um", "feat: dois", "docs: três"], "0.9.5"),
        (["perf(radio): menos pacotes"], "0.9.4.6"),
        (["feat!: troca o formato do perfil"], "0.9.5"),
        (["fix: corrige\n\nBREAKING CHANGE: o perfil muda"], "0.9.5"),
    ],
)
def test_a_proxima_versao_sai_do_tipo_dos_commits(
    brinquedo: Path, commits: list[str], esperada: str
) -> None:
    for c in commits:
        commitar(brinquedo, c)
    r = rodar(VERSAO, "seguinte", "--so-o-numero", raiz=brinquedo)
    assert r.returncode == 0 and r.stdout.splitlines()[-1] == esperada, r.stdout


def test_commit_que_nao_lanca_nada_nao_propoe_versao(brinquedo: Path) -> None:
    for c in ("docs: um texto", "test: um teste", "chore: faxina", "refactor: arruma"):
        commitar(brinquedo, c)
    r = rodar(VERSAO, "seguinte", raiz=brinquedo)
    assert r.returncode == 0 and "nada a lançar" in r.stdout


def test_a_ultima_tag_e_a_mais_alta_da_serie_e_a_proxima_parte_dela(brinquedo: Path) -> None:
    commitar(brinquedo, "feat: um")
    git(brinquedo, "tag", "v0.9.5")
    commitar(brinquedo, "fix: dois")
    r = rodar(VERSAO, "seguinte", "--so-o-numero", raiz=brinquedo)
    assert r.stdout.splitlines()[-1] == "0.9.5.1", "um fix depois da 0.9.5 sobe a quarta casa"
    commitar(brinquedo, "feat: três")
    assert (
        rodar(VERSAO, "seguinte", "--so-o-numero", raiz=brinquedo).stdout.splitlines()[-1]
        == "0.9.6"
    )


def test_trocar_a_serie_e_trocar_a_linha_do_arquivo(brinquedo: Path) -> None:
    (brinquedo / ".github" / "repositorio.yml").write_text(
        REPOSITORIO_DO_BRINQUEDO.format(serie="4"), encoding="utf-8"
    )
    commitar(brinquedo, "feat: um")
    assert (
        rodar(VERSAO, "seguinte", "--so-o-numero", raiz=brinquedo).stdout.splitlines()[-1]
        == "4.1.0"
    )
    commitar(brinquedo, "fix: dois")
    # feat e fix juntos: o feat manda
    assert (
        rodar(VERSAO, "seguinte", "--so-o-numero", raiz=brinquedo).stdout.splitlines()[-1]
        == "4.1.0"
    )


def test_a_proposta_e_idempotente(brinquedo: Path) -> None:
    commitar(brinquedo, "feat: um")
    a = rodar(VERSAO, "seguinte", raiz=brinquedo).stdout
    b = rodar(VERSAO, "seguinte", raiz=brinquedo).stdout
    assert a == b


def _conferencia(raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(raiz / "scripts" / "check_version_consistency.py")],
        capture_output=True,
        text=True,
        check=False,
    )


def _texto_dos_alvos(raiz: Path) -> dict[str, str]:
    return {
        rel: (raiz / rel).read_text(encoding="utf-8")
        for rel in ALVOS_DE_VERSAO
        if rel != "scripts/check_version_consistency.py"
    }


def test_gravar_poe_a_mesma_versao_em_todos_os_alvos_e_a_regua_do_repositorio_concorda(
    brinquedo: Path,
) -> None:
    # o brinquedo parte de um repositório em que a régua JÁ passava
    assert _conferencia(brinquedo).returncode == 0
    # a seção do CHANGELOG primeiro: o AppStream resume a release a partir dela
    assert (
        rodar(CHANGELOG, "montar", "0.9.5", "--data", "2026-10-07", raiz=brinquedo).returncode == 0
    )
    r = rodar(VERSAO, "gravar", "0.9.5", "--data", "2026-10-07", raiz=brinquedo)
    assert r.returncode == 0, r.stdout
    assert "gravada em" in primeira_linha(r)
    depois = _conferencia(brinquedo)
    assert depois.returncode == 0, depois.stdout
    textos = _texto_dos_alvos(brinquedo)
    assert 'version = "0.9.5"' in textos["pyproject.toml"]
    assert "pkgver=0.9.5" in textos["packaging/arch/PKGBUILD"]
    assert re.search(r"^Version:\s*0\.9\.5\s*$", textos["packaging/debian/control"], re.M)
    assert (
        'name = "hefesto-dualsense4unix-applet"\nversion = "0.9.5"'
        in textos["packaging/cosmic-applet/Cargo.lock"]
    )
    metainfo = textos["flatpak/io.github.hefesto_team.hefesto_dualsense4unix.metainfo.xml"]
    assert re.search(
        r'<releases>\s*<release version="0\.9\.5" date="2026-10-07">'
        r"\s*<description>\s*<p>Item escrito à mão\.",
        metainfo,
    )
    assert '<release version="0.9.4.5"' in metainfo, "a release anterior fica onde estava"


def test_gravar_sem_a_secao_do_changelog_a_regua_do_repositorio_acusa(brinquedo: Path) -> None:
    """A data do AppStream tem de ser a da seção do CHANGELOG: sem a seção, a régua acusa."""
    assert rodar(VERSAO, "gravar", "0.9.5", "--data", "2026-10-07", raiz=brinquedo).returncode == 0
    r = _conferencia(brinquedo)
    assert r.returncode == 1 and "metainfo x CHANGELOG" in r.stdout
    assert (
        rodar(CHANGELOG, "montar", "0.9.5", "--data", "2026-10-07", raiz=brinquedo).returncode == 0
    )
    assert _conferencia(brinquedo).returncode == 0


def test_gravar_de_novo_nao_muda_nada_e_o_conferir_diz_o_que_faria(brinquedo: Path) -> None:
    antes = _texto_dos_alvos(brinquedo)
    c = rodar(VERSAO, "gravar", "0.9.5", "--data", "2026-10-07", "--conferir", raiz=brinquedo)
    assert c.returncode == 1 and "mudaria" in primeira_linha(c)
    assert _texto_dos_alvos(brinquedo) == antes, "o --conferir não escreve"
    assert rodar(VERSAO, "gravar", "0.9.5", "--data", "2026-10-07", raiz=brinquedo).returncode == 0
    depois = _texto_dos_alvos(brinquedo)
    segunda = rodar(VERSAO, "gravar", "0.9.5", "--data", "2026-10-07", raiz=brinquedo)
    assert segunda.returncode == 0 and "já está em todos os alvos" in primeira_linha(segunda)
    assert _texto_dos_alvos(brinquedo) == depois
    assert rodar(VERSAO, "gravar", "0.9.5", "--conferir", raiz=brinquedo).returncode == 0


def test_gravar_sem_versao_grava_a_proposta(brinquedo: Path) -> None:
    commitar(brinquedo, "feat: um")
    r = rodar(VERSAO, "gravar", "--data", "2026-10-07", raiz=brinquedo)
    assert r.returncode == 0 and "0.9.5 gravada" in primeira_linha(r)
    assert 'version = "0.9.5"' in (brinquedo / "pyproject.toml").read_text(encoding="utf-8")


def test_gravar_recusa_versao_fora_da_serie(brinquedo: Path) -> None:
    r = rodar(VERSAO, "gravar", "4.1.0", raiz=brinquedo)
    assert r.returncode == 2 and "não é da série 0.9" in r.stdout
    assert 'version = "0.9.4.5"' in (brinquedo / "pyproject.toml").read_text(encoding="utf-8")


def test_mordida_um_alvo_com_versao_diferente_reprova_e_o_dono_o_acha(brinquedo: Path) -> None:
    # alguém mexeu num alvo à mão: a régua reprova, e o dono, no --conferir, aponta o arquivo
    pkg = brinquedo / "packaging" / "arch" / "PKGBUILD"
    pkg.write_text(
        pkg.read_text(encoding="utf-8").replace("pkgver=0.9.4.5", "pkgver=0.9.4.4"),
        encoding="utf-8",
    )
    assert _conferencia(brinquedo).returncode == 1
    r = rodar(VERSAO, "gravar", "0.9.4.5", "--conferir", raiz=brinquedo)
    assert r.returncode == 1 and "packaging/arch/PKGBUILD" in r.stdout
    assert rodar(VERSAO, "gravar", "0.9.4.5", raiz=brinquedo).returncode == 0
    assert _conferencia(brinquedo).returncode == 0


def test_a_tag_tem_de_dizer_a_versao_do_pacote(brinquedo: Path) -> None:
    assert rodar(VERSAO, "conferir-tag", "v0.9.4.5", raiz=brinquedo).returncode == 0
    assert rodar(VERSAO, "conferir-tag", "refs/tags/v0.9.4.5", raiz=brinquedo).returncode == 0
    r = rodar(VERSAO, "conferir-tag", "v0.9.5", raiz=brinquedo)
    assert r.returncode == 1 and "a tag diz 0.9.5 e o pacote tem 0.9.4.5" in r.stdout
    assert rodar(VERSAO, "conferir-tag", "main", raiz=brinquedo).returncode == 1


def test_o_hash_do_tarball_entra_no_pkgbuild_uma_vez(brinquedo: Path, tmp_path: Path) -> None:
    tarball = tmp_path / "fonte.tar.gz"
    tarball.write_bytes(b"o tarball da tag")
    esperado = hashlib.sha256(b"o tarball da tag").hexdigest()
    r = rodar(VERSAO, "hash", str(tarball), raiz=brinquedo)
    assert r.returncode == 0 and esperado[:12] in r.stdout
    assert f"sha256sums=('{esperado}')" in (brinquedo / "packaging/arch/PKGBUILD").read_text(
        encoding="utf-8"
    )
    assert rodar(VERSAO, "hash", str(tarball), "--conferir", raiz=brinquedo).returncode == 0
    assert "já tem" in primeira_linha(rodar(VERSAO, "hash", str(tarball), raiz=brinquedo))


def test_a_serie_do_repositorio_real_existe_e_a_proposta_roda_nele() -> None:
    """O arquivo de verdade declara a série, e o dono lê a mesma linha que o aplicador valida."""
    dados = yaml.safe_load(REPOSITORIO_YML.read_text(encoding="utf-8"))
    assert re.fullmatch(r"\d+(\.\d+){0,2}", dados["release"]["serie"])
    r = rodar(VERSAO, "seguinte", raiz=RAIZ)
    assert r.returncode == 0, r.stdout


# ---------------------------------------------------------------------------
# 2. O bloco `publico` e o CHANGELOG que nasce do que foi fechado
# ---------------------------------------------------------------------------


def sprint(
    raiz: Path,
    ident: str,
    estado: str = "feita",
    fechada: str | None = "07/10/2026",
    muda: str | None = "O botão do microfone liga só o microfone daquele controle.",
    tipo: str = "adicionado",
    extra: str = "",
) -> Path:
    pasta = raiz / "docs" / "process" / "sprints"
    pasta.mkdir(parents=True, exist_ok=True)
    cab = f"---\nsprint: {ident}\nestado: {estado}\n"
    if fechada:
        cab += f"# fechada {fechada}: 3 commits\n"
    cab += (
        "bancada: false\ndepois_de: []\nposse:\n  X:\n    - a.py\ncria: []\nnao_toca: []\n---\n\n"
    )
    corpo = f"# {ident}\n\nTexto da sprint, com «mesa» e «agente» à vontade: só o bloco sai.\n\n"
    if muda is not None:
        corpo += (
            "```publico\ntitulo: O microfone de cada controle\n"
            f"tipo: {tipo}\narea: som\nmuda: {muda}\n"
            f"pronto: Ao apertar o botão, só aquele microfone muda.\n{extra}```\n"
        )
    arq = pasta / f"2026-10-07-{ident}.md"
    arq.write_text(cab + corpo, encoding="utf-8")
    return arq


def test_o_bloco_publico_e_lido_e_o_resto_da_sprint_fica_em_casa() -> None:
    spec = importlib.util.spec_from_file_location("publico_do_teste", PUBLICO)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(RELEASE))
    spec.loader.exec_module(modulo)
    texto = (
        "# Sprint\n\nblá «mesa»\n\n```publico\ntitulo: Um\ntipo: mudado\n"
        "muda: Primeira linha\n  e a segunda.\npronto: Feito.\n```\n"
    )
    bloco = modulo.extrair(texto)
    assert bloco == {
        "titulo": "Um",
        "tipo": "mudado",
        "muda": "Primeira linha e a segunda.",
        "pronto": "Feito.",
    }
    assert modulo.extrair("# sem bloco\n") is None


@pytest.mark.parametrize(
    ("campo", "valor", "trecho"),
    [
        ("muda", "A mesa mostra o resultado.", "palavra da casa"),
        ("muda", "O agente corrige o perfil.", "palavra da casa"),
        ("muda", "Depois da leva de hoje o botão liga.", "palavra da casa"),
        ("muda", "A sprint de hoje fecha.", "palavra da casa"),
        ("tipo", "novidade", "`tipo` é um destes"),
        ("area", "inexistente", "`area` é uma destas"),
        ("titulo", "x" * 81, "passa de 80"),
    ],
)
def test_a_regua_do_publico_reprova_palavra_da_casa_e_campo_torto(
    brinquedo: Path, campo: str, valor: str, trecho: str
) -> None:
    sys.path.insert(0, str(RELEASE))
    import publico as modulo

    bloco = {
        "titulo": "Um título",
        "tipo": "adicionado",
        "area": "som",
        "muda": "O botão liga.",
        "pronto": "Liga.",
    }
    assert modulo.validar(bloco, brinquedo) == [], "o bloco de partida é válido"
    bloco[campo] = valor
    erros = modulo.validar(bloco, brinquedo)
    assert any(trecho in e for e in erros), erros


def test_o_publico_passa_pela_regua_de_autoria_quando_ela_existe(brinquedo: Path) -> None:
    """A régua é o `check_autoria.py texto` da árvore: se ela recusa, o bloco não vai a quem usa."""
    sys.path.insert(0, str(RELEASE))
    import publico as modulo

    (brinquedo / "scripts" / "check_autoria.py").write_text(
        "import sys\ntexto = sys.stdin.read()\n"
        "print('autoria: REPROVADO: texto' if 'proibida' in texto else 'autoria: OK: texto.')\n"
        "sys.exit(1 if 'proibida' in texto else 0)\n",
        encoding="utf-8",
    )
    bom = {"titulo": "Um", "tipo": "adicionado", "muda": "O botão liga.", "pronto": "Liga."}
    assert modulo.validar(bom, brinquedo) == []
    ruim = dict(bom, muda="O botão liga a palavra proibida.")
    assert any("autoria" in e for e in modulo.validar(ruim, brinquedo))
    assert modulo.validar(ruim, brinquedo, autoria=False) == []


def test_o_changelog_nasce_do_que_estava_escrito_das_sprints_fechadas_e_dos_prs(
    brinquedo: Path,
) -> None:
    sprint(brinquedo, "UMA-SPRINT-01")
    sprint(
        brinquedo,
        "OUTRA-SPRINT-01",
        tipo="corrigido",
        muda="Um controle no cabo volta sozinho depois do erro de USB.",
    )
    commitar(brinquedo, "feat(tela): a aba nova abre mais rápido (#12)", data="2026-10-06")
    commitar(brinquedo, "fix(som): o microfone voltava mudo (#13)", data="2026-10-06")
    commitar(brinquedo, "feat: sem número de PR não entra na lista de PRs")
    r = rodar(CHANGELOG, "montar", "0.9.5", "--data", "2026-10-07", raiz=brinquedo)
    assert r.returncode == 0, r.stdout
    texto = (brinquedo / "CHANGELOG.md").read_text(encoding="utf-8")
    secao = texto.split("## [0.9.5] — 2026-10-07")[1].split("## [0.9.4.5]")[0]
    assert "- Item escrito à mão." in secao, "o que estava em Unreleased entra"
    assert "- O botão do microfone liga só o microfone daquele controle." in secao
    assert "- Um controle no cabo volta sozinho depois do erro de USB." in secao
    assert "- A aba nova abre mais rápido" in secao and "- O microfone voltava mudo" in secao
    assert "sem número de PR" not in secao
    assert secao.index("### Adicionado") < secao.index("### Corrigido"), (
        "a ordem é a do Keep a Changelog"
    )
    # Unreleased fica vazio e a versão anterior não se mexe
    assert texto.split("## [Unreleased]")[1].split("## [0.9.5]")[0].strip() == ""
    assert "## [0.9.4.5] — 2026-08-20\n\n### Adicionado\n\n- Item antigo." in texto


def test_o_changelog_e_idempotente_e_o_conferir_nao_escreve(brinquedo: Path) -> None:
    sprint(brinquedo, "UMA-SPRINT-01")
    antes = (brinquedo / "CHANGELOG.md").read_text(encoding="utf-8")
    c = rodar(CHANGELOG, "montar", "0.9.5", "--data", "2026-10-07", "--conferir", raiz=brinquedo)
    assert c.returncode == 1 and (brinquedo / "CHANGELOG.md").read_text(encoding="utf-8") == antes
    assert (
        rodar(CHANGELOG, "montar", "0.9.5", "--data", "2026-10-07", raiz=brinquedo).returncode == 0
    )
    feito = (brinquedo / "CHANGELOG.md").read_text(encoding="utf-8")
    segunda = rodar(CHANGELOG, "montar", "0.9.5", "--data", "2026-10-07", raiz=brinquedo)
    assert segunda.returncode == 0 and "já está completa" in primeira_linha(segunda)
    assert (brinquedo / "CHANGELOG.md").read_text(encoding="utf-8") == feito
    assert (
        rodar(
            CHANGELOG, "montar", "0.9.5", "--data", "2026-10-07", "--conferir", raiz=brinquedo
        ).returncode
        == 0
    )


def test_sprint_fechada_sem_publico_nao_entra_e_e_avisada(brinquedo: Path, tmp_path: Path) -> None:
    sprint(brinquedo, "SEM-BLOCO-01", muda=None)
    detalhe = tmp_path / "detalhe.txt"
    r = rodar(
        CHANGELOG,
        "montar",
        "0.9.5",
        "--data",
        "2026-10-07",
        "--detalhe",
        str(detalhe),
        raiz=brinquedo,
    )
    assert r.returncode == 0
    texto = (brinquedo / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "SEM-BLOCO" not in texto
    assert "aviso: SEM-BLOCO-01 fechou em 07/10/2026 sem bloco `publico`" in detalhe.read_text(
        encoding="utf-8"
    )


def test_so_entra_sprint_fechada_depois_da_ultima_tag(brinquedo: Path) -> None:
    sprint(brinquedo, "ANTIGA-01", fechada="01/08/2026", muda="Isto saiu na versão anterior.")
    sprint(
        brinquedo, "ABERTA-01", estado="aberta", fechada=None, muda="Isto ainda não está pronto."
    )
    sprint(
        brinquedo, "SEM-DATA-01", fechada=None, muda="Sem data de fecho não se sabe de quando é."
    )
    sprint(brinquedo, "NOVA-01", muda="Isto saiu agora.")
    rodar(CHANGELOG, "montar", "0.9.5", "--data", "2026-10-07", raiz=brinquedo)
    texto = (brinquedo / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "Isto saiu agora." in texto
    for fora in (
        "Isto saiu na versão anterior.",
        "Isto ainda não está pronto.",
        "Sem data de fecho",
    ):
        assert fora not in texto, fora


def test_bloco_com_palavra_da_casa_nao_entra_no_changelog(brinquedo: Path, tmp_path: Path) -> None:
    sprint(brinquedo, "CASEIRA-01", muda="A mesa dela mostra o resultado do agente.")
    detalhe = tmp_path / "detalhe.txt"
    rodar(
        CHANGELOG,
        "montar",
        "0.9.5",
        "--data",
        "2026-10-07",
        "--detalhe",
        str(detalhe),
        raiz=brinquedo,
    )
    assert "mesa" not in (brinquedo / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "o bloco `publico` de CASEIRA-01 não entra" in detalhe.read_text(encoding="utf-8")


def test_linha_que_uma_versao_anterior_ja_tem_nao_se_repete(brinquedo: Path) -> None:
    sprint(brinquedo, "REPETIDA-01", muda="Item antigo.")
    rodar(CHANGELOG, "montar", "0.9.5", "--data", "2026-10-07", raiz=brinquedo)
    assert (brinquedo / "CHANGELOG.md").read_text(encoding="utf-8").count("- Item antigo.") == 1


def test_sem_nada_a_dizer_a_secao_nao_nasce_vazia(brinquedo: Path) -> None:
    texto = (
        (brinquedo / "CHANGELOG.md")
        .read_text(encoding="utf-8")
        .replace("### Corrigido\n\n- Item escrito à mão.\n", "")
    )
    (brinquedo / "CHANGELOG.md").write_text(texto, encoding="utf-8")
    r = rodar(CHANGELOG, "montar", "0.9.5", raiz=brinquedo)
    assert r.returncode == 4 and "nada a dizer" in primeira_linha(r)
    assert "## [0.9.5]" not in (brinquedo / "CHANGELOG.md").read_text(encoding="utf-8")


def test_as_notas_trazem_a_secao_e_como_conferir_o_que_se_baixa(brinquedo: Path) -> None:
    rodar(CHANGELOG, "montar", "0.9.5", "--data", "2026-10-07", raiz=brinquedo)
    r = rodar(
        CHANGELOG, "notas", "0.9.5", "--repo", "Hefesto-Team/hefesto-dualsense4unix", raiz=brinquedo
    )
    assert r.returncode == 0
    assert "- Item escrito à mão." in r.stdout and not r.stdout.startswith("## [")
    assert "sha256sum -c SHA256SUMS --ignore-missing" in r.stdout
    assert (
        "gh attestation verify NOME-DO-ARQUIVO --repo Hefesto-Team/hefesto-dualsense4unix"
        in r.stdout
    )
    assert rodar(CHANGELOG, "notas", "9.9.9", raiz=brinquedo).returncode == 3


# ---------------------------------------------------------------------------
# 3. O que se baixa se confere: o SHA256SUMS
# ---------------------------------------------------------------------------


def _pasta_de_artefatos(tmp_path: Path) -> Path:
    pasta = tmp_path / "dist"
    pasta.mkdir()
    for nome in (
        "hefesto-0.9.5-py3-none-any.whl",
        "hefesto-0.9.5.tar.gz",
        "Hefesto-0.9.5-x86_64.AppImage",
        "hefesto_0.9.5_amd64_ubuntu22.deb",
        "Hefesto-0.9.5-x86_64.flatpak",
    ):
        (pasta / nome).write_bytes(f"conteúdo de {nome}".encode())
    return pasta


EXIGIDOS = ["*.whl", "*.tar.gz", "*.AppImage", "*.deb", "*.flatpak"]


def test_o_sha256sums_tem_o_formato_do_sha256sum_e_bate(tmp_path: Path) -> None:
    pasta = _pasta_de_artefatos(tmp_path)
    assert rodar(SUMS, "gerar", str(pasta)).returncode == 0
    linhas = (pasta / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 5 and all(re.fullmatch(r"[0-9a-f]{64}  \S+", ln) for ln in linhas)
    assert linhas == sorted(linhas, key=lambda ln: ln.split("  ")[1])
    sistema = subprocess.run(
        ["sha256sum", "--check", "SHA256SUMS"],
        cwd=pasta,
        capture_output=True,
        text=True,
        check=False,
    )
    assert sistema.returncode == 0, sistema.stdout
    r = rodar(SUMS, "conferir", str(pasta), "--exigir", *EXIGIDOS)
    assert r.returncode == 0 and "5 arquivo(s) batem" in primeira_linha(r)


def test_o_sha256sums_e_idempotente(tmp_path: Path) -> None:
    pasta = _pasta_de_artefatos(tmp_path)
    assert rodar(SUMS, "gerar", str(pasta), "--conferir").returncode == 1
    rodar(SUMS, "gerar", str(pasta))
    feito = (pasta / "SHA256SUMS").read_bytes()
    segunda = rodar(SUMS, "gerar", str(pasta))
    assert segunda.returncode == 0 and "já tem" in primeira_linha(segunda)
    assert (pasta / "SHA256SUMS").read_bytes() == feito
    assert rodar(SUMS, "gerar", str(pasta), "--conferir").returncode == 0


def test_mordida_artefato_fora_do_sha256sums_reprova(tmp_path: Path) -> None:
    pasta = _pasta_de_artefatos(tmp_path)
    rodar(SUMS, "gerar", str(pasta))
    (pasta / "extra.deb").write_bytes(b"ninguem listou")
    r = rodar(SUMS, "conferir", str(pasta))
    assert r.returncode == 1 and "fora do SHA256SUMS: extra.deb" in r.stdout


def test_mordida_artefato_trocado_no_caminho_reprova(tmp_path: Path) -> None:
    pasta = _pasta_de_artefatos(tmp_path)
    rodar(SUMS, "gerar", str(pasta))
    (pasta / "hefesto-0.9.5.tar.gz").write_bytes(b"outro texto")
    r = rodar(SUMS, "conferir", str(pasta))
    assert r.returncode == 1 and "hash diferente: hefesto-0.9.5.tar.gz" in r.stdout


def test_mordida_linha_sem_arquivo_e_tipo_que_falta_reprovam(tmp_path: Path) -> None:
    pasta = _pasta_de_artefatos(tmp_path)
    rodar(SUMS, "gerar", str(pasta))
    (pasta / "Hefesto-0.9.5-x86_64.flatpak").unlink()
    r = rodar(SUMS, "conferir", str(pasta), "--exigir", *EXIGIDOS)
    assert r.returncode == 1
    assert "no SHA256SUMS e sem arquivo: Hefesto-0.9.5-x86_64.flatpak" in r.stdout
    assert "falta um arquivo *.flatpak" in r.stdout


def test_pasta_vazia_nao_gera_sums(tmp_path: Path) -> None:
    (tmp_path / "vazia").mkdir()
    assert rodar(SUMS, "gerar", str(tmp_path / "vazia")).returncode == 2


# ---------------------------------------------------------------------------
# 4. A publicação: rascunho, arquivos, publicação, contra o `gh` de mentira
# ---------------------------------------------------------------------------

SLUG = "Hefesto-Team/ensaio"
# a conta da casa vai por partes: o higienizador do commit apaga o nome inteiro
CONTA = "vitoria" + "mariadb"


ESTADO_INICIAL: dict[str, Any] = {
    "user": CONTA,
    "slug": SLUG,
    "privado": False,
    "repo": {
        "node_id": "R_kgDOabc",
        "description": None,
        "homepage": "https://patreon.com/exemplo",
        "has_issues": True,
        "has_wiki": True,
        "has_projects": True,
        "has_discussions": False,
    },
    "topics": [],
    "repos_extras": {"Hefesto-Team/hefesto-dualsense4unix": "R_h", "Hefesto-Team/Forja": "R_f"},
    "alertas": False,
    "fixes": False,
    "relato": False,
    "pages": False,
    "sponsor": True,
    "análise": {"secret_scanning": "disabled", "secret_scanning_push_protection": "disabled"},
    "colaboradores": {CONTA: "admin", "visitante": "write"},
    "rulesets": [],
    "prox": 0,
    "negar": {},
}


class Mentira:
    def __init__(self, pasta: Path) -> None:
        self.estado_arq = pasta / "estado.json"
        self.log = pasta / "chamadas.jsonl"
        self.log.write_text("")
        self.estado_arq.write_text(json.dumps(ESTADO_INICIAL))

    @property
    def estado(self) -> dict[str, Any]:
        return json.loads(self.estado_arq.read_text())  # type: ignore[no-any-return]

    def mudar(self, **campos: Any) -> None:
        e = self.estado
        e.update(campos)
        self.estado_arq.write_text(json.dumps(e))

    def chamadas(self) -> list[dict[str, Any]]:
        return [json.loads(x) for x in self.log.read_text().splitlines()]

    def escritas(self) -> list[str]:
        return [f"{c['m']} {c['p']}" for c in self.chamadas() if c["escrita"]]


@pytest.fixture
def gh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Mentira:
    pasta = tmp_path / "mentira"
    (pasta / "bin").mkdir(parents=True)
    exe = pasta / "bin" / "gh"
    corpo = GH_DE_MENTIRA.read_text(encoding="utf-8").split("\n", 1)[1]
    exe.write_text(f"#!{sys.executable}\n{corpo}", encoding="utf-8")
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    m = Mentira(pasta)
    monkeypatch.setenv("PATH", f"{pasta / 'bin'}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("GH_MENTIRA_ESTADO", str(m.estado_arq))
    monkeypatch.setenv("GH_MENTIRA_LOG", str(m.log))
    return m


def _pronta_para_publicar(tmp_path: Path) -> tuple[Path, Path]:
    pasta = _pasta_de_artefatos(tmp_path)
    rodar(SUMS, "gerar", str(pasta))
    notas = tmp_path / "notas.md"
    notas.write_text("- Item.\n", encoding="utf-8")
    return pasta, notas


def publicar(
    pasta: Path, notas: Path, *extra: str, tag: str = "v0.9.5"
) -> subprocess.CompletedProcess[str]:
    return rodar(
        PUBLICAR, tag, "--repo", SLUG, "--pasta", str(pasta), "--notas", str(notas), *extra
    )


def test_a_release_nasce_rascunho_recebe_os_arquivos_e_so_entao_e_publicada(
    gh: Mentira, tmp_path: Path
) -> None:
    gh.mudar(imutaveis=True)
    pasta, notas = _pronta_para_publicar(tmp_path)
    r = publicar(pasta, notas)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "publicada com 6 arquivo(s) e o SHA256SUMS" in r.stdout
    verbos = [c["m"] for c in gh.chamadas() if c["escrita"]]
    assert verbos == ["release create", "release upload", "release edit"], (
        "rascunho, arquivos, publicação, nesta ordem"
    )
    criar = next(c for c in gh.chamadas() if c["m"] == "release create")
    assert (
        "--draft" in criar["b"]["flags"]
        and "--verify-tag" in criar["b"]["flags"]
        and "--generate-notes" in criar["b"]["flags"]
    )
    subir = next(c for c in gh.chamadas() if c["m"] == "release upload")
    assert "--clobber" in subir["b"]["flags"]
    final = gh.estado["releases"]["v0.9.5"]
    assert final["draft"] is False and final["travada"] is True, (
        "publicada com a imutável ligada: travou"
    )
    assert "SHA256SUMS" in final["assets"] and len(final["assets"]) == 6
    assert "delete" not in " ".join(verbos)


def test_rodar_de_novo_na_versao_publicada_com_os_mesmos_arquivos_nao_escreve(
    gh: Mentira, tmp_path: Path
) -> None:
    gh.mudar(imutaveis=True)
    pasta, notas = _pronta_para_publicar(tmp_path)
    assert publicar(pasta, notas).returncode == 0
    antes = gh.estado
    gh.log.write_text("")
    r = publicar(pasta, notas)
    assert r.returncode == 0 and "já está publicada com os mesmos 6 arquivo(s)" in r.stdout
    assert gh.escritas() == [] and gh.estado == antes


def test_versao_publicada_com_outros_arquivos_e_recusada_e_nada_muda(
    gh: Mentira, tmp_path: Path
) -> None:
    gh.mudar(imutaveis=True)
    pasta, notas = _pronta_para_publicar(tmp_path)
    assert publicar(pasta, notas).returncode == 0
    # uma reconstrução que não é byte a byte a mesma (o wheel e o AppImage não são reproduzíveis)
    (pasta / "hefesto-0.9.5.tar.gz").write_bytes(b"reconstruido")
    rodar(SUMS, "gerar", str(pasta))
    antes = gh.estado
    gh.log.write_text("")
    r = publicar(pasta, notas)
    assert r.returncode == 1 and "já está publicada com outros arquivos" in r.stdout
    assert "a correção é a versão seguinte" in r.stdout
    assert gh.escritas() == [] and gh.estado == antes


def test_o_rascunho_interrompido_e_retomado_sem_recriar(gh: Mentira, tmp_path: Path) -> None:
    gh.mudar(imutaveis=True)
    pasta, notas = _pronta_para_publicar(tmp_path)
    # a primeira corrida morreu depois de criar o rascunho e subir só um arquivo
    gh.mudar(
        releases={
            "v0.9.5": {
                "draft": True,
                "travada": False,
                "title": "x",
                "notes": "",
                "assets": {"hefesto-0.9.5.tar.gz": "sha256:velho"},
            }
        }
    )
    r = publicar(pasta, notas)
    assert r.returncode == 0, r.stdout + r.stderr
    verbos = [c["m"] for c in gh.chamadas() if c["escrita"]]
    assert verbos == ["release upload", "release edit"], "não recria: só sobe o que falta e publica"
    final = gh.estado["releases"]["v0.9.5"]
    assert (
        final["assets"]["hefesto-0.9.5.tar.gz"]
        == "sha256:" + hashlib.sha256(b"conte\xc3\xbado de hefesto-0.9.5.tar.gz").hexdigest()
    ), "o arquivo velho do rascunho foi trocado (--clobber)"


def test_a_pasta_que_nao_confere_nao_publica_nada(gh: Mentira, tmp_path: Path) -> None:
    pasta, notas = _pronta_para_publicar(tmp_path)
    (pasta / "hefesto-0.9.5.tar.gz").write_bytes(b"trocado depois do SHA256SUMS")
    r = publicar(pasta, notas)
    assert r.returncode == 1 and "nada foi publicado" in r.stdout
    assert gh.chamadas() == [], "nem uma chamada ao servidor"
    (pasta / "hefesto-0.9.5.tar.gz").write_bytes(b"conte\xc3\xbado de hefesto-0.9.5.tar.gz")
    (pasta / "Hefesto-0.9.5-x86_64.flatpak").unlink()
    rodar(SUMS, "gerar", str(pasta))
    r = publicar(pasta, notas)
    assert r.returncode == 1 and gh.chamadas() == [], (
        "falta um tipo de arquivo da release: não publica"
    )


def test_o_conferir_diz_o_que_faria_sem_escrever(gh: Mentira, tmp_path: Path) -> None:
    pasta, notas = _pronta_para_publicar(tmp_path)
    r = publicar(pasta, notas, "--conferir")
    assert r.returncode == 1 and "criaria o rascunho" in r.stdout
    assert gh.escritas() == []


def test_a_causa_o_fluxo_antigo_apagar_e_recriar_a_imutavel_recusa(
    gh: Mentira, tmp_path: Path
) -> None:
    """O que o `release.yml` fazia (`gh release delete` e `create` com arquivos) não passa no
    servidor com a release imutável: é por isso que o fluxo virou rascunho."""
    gh.mudar(imutaveis=True)
    pasta = _pasta_de_artefatos(tmp_path)
    arquivos = [str(p) for p in sorted(pasta.iterdir())]
    base = ["--repo", SLUG, "--yes"]

    def g(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["gh", *args], capture_output=True, text=True, check=False)

    # 1. o `create` com arquivos, sem rascunho: nasce pública e travada, e o arquivo não sobe
    criar = g("release", "create", "v0.9.5", "--repo", SLUG, "--title", "t", *arquivos)
    assert criar.returncode == 1 and "immutable" in criar.stderr
    # 2. a versão existe publicada: o fluxo antigo a apagava e recriava
    assert g("release", "delete", "v0.9.5", *base).returncode == 0
    nova = g("release", "create", "v0.9.5", "--repo", SLUG, "--title", "t", "--draft")
    assert nova.returncode == 1 and "used by an immutable release" in nova.stderr, (
        "a tag não volta nunca"
    )


def test_sem_a_imutavel_o_fluxo_antigo_passava_e_o_duble_nao_e_mais_duro_que_o_servidor(
    gh: Mentira, tmp_path: Path
) -> None:
    """O dublê só vale se aceita o que a API aceita: sem a imutável, apagar e recriar passa."""
    pasta = _pasta_de_artefatos(tmp_path)
    arquivos = [str(p) for p in sorted(pasta.iterdir())]
    criar = subprocess.run(
        ["gh", "release", "create", "v0.9.5", "--repo", SLUG, "--title", "t", *arquivos],
        capture_output=True,
        text=True,
        check=False,
    )
    assert criar.returncode == 0
    assert (
        subprocess.run(
            ["gh", "release", "delete", "v0.9.5", "--repo", SLUG, "--yes"], check=False
        ).returncode
        == 0
    )
    assert (
        subprocess.run(
            ["gh", "release", "create", "v0.9.5", "--repo", SLUG, "--title", "t", "--draft"],
            check=False,
        ).returncode
        == 0
    )


def test_a_release_publicada_imutavel_recusa_arquivo_novo_e_edicao(
    gh: Mentira, tmp_path: Path
) -> None:
    gh.mudar(imutaveis=True)
    pasta, notas = _pronta_para_publicar(tmp_path)
    assert publicar(pasta, notas).returncode == 0
    extra = tmp_path / "extra.txt"
    extra.write_text("x")
    sobe = subprocess.run(
        ["gh", "release", "upload", "v0.9.5", "--repo", SLUG, "--clobber", str(extra)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert sobe.returncode == 1 and "immutable" in sobe.stderr
    edita = subprocess.run(
        ["gh", "release", "edit", "v0.9.5", "--repo", SLUG, "--draft=true"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert edita.returncode == 1 and "immutable" in edita.stderr


# ---------------------------------------------------------------------------
# 5. O `release.yml`
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def wf() -> dict[str, Any]:
    dados = yaml.safe_load(RELEASE_YML.read_text(encoding="utf-8"))
    assert isinstance(dados, dict)
    return dados


def _shell(wf: dict[str, Any], job: str) -> str:
    return "\n".join(str(p.get("run", "")) for p in wf["jobs"][job]["steps"])


def _needs(wf: dict[str, Any], job: str) -> list[str]:
    n = wf["jobs"][job].get("needs", [])
    return [n] if isinstance(n, str) else list(n)


def test_o_release_yml_nao_apaga_nem_recria_a_versao(wf: dict[str, Any]) -> None:
    texto = RELEASE_YML.read_text(encoding="utf-8")
    assert "gh release delete" not in texto and "gh release create" not in texto
    assert "scripts/release/publicar.py" in _shell(wf, "github-release")


def test_o_job_que_publica_usa_o_ambiente_release_e_so_ele_escreve_no_repositorio(
    wf: dict[str, Any],
) -> None:
    assert wf["jobs"]["github-release"]["environment"] == "release"
    assert wf["jobs"]["github-release"]["permissions"] == {"contents": "write"}
    assert wf["permissions"] == {"contents": "read"}, "o fluxo lê; quem precisa de mais pede no job"
    escrevem = {
        n for n, j in wf["jobs"].items() if (j.get("permissions") or {}).get("contents") == "write"
    }
    assert escrevem == {"github-release"}, escrevem
    assert wf["jobs"]["pypi"]["permissions"] == {"id-token": "write"}


def test_o_ambiente_release_existe_no_arquivo_do_repositorio() -> None:
    dados = yaml.safe_load(REPOSITORIO_YML.read_text(encoding="utf-8"))
    ambientes = {a["nome"]: a for a in dados["ambientes"]}
    assert {"pypi", "release"} <= set(ambientes) and ambientes["release"]["tags"] == ["v*"]
    assert ambientes["release"]["revisores"], "a publicação espera a aprovação de quem mantém"


def test_a_integridade_gera_o_sums_e_pede_o_atestado_de_tudo(wf: dict[str, Any]) -> None:
    passos = wf["jobs"]["integridade"]["steps"]
    shell = _shell(wf, "integridade")
    assert "sums.py gerar" in shell and "sums.py conferir" in shell and "sha256sum --check" in shell
    atesta = [p for p in passos if "attest-build-provenance" in str(p.get("uses", ""))]
    assert len(atesta) == 1
    assert atesta[0]["with"]["subject-checksums"] == "dist/tudo/SHA256SUMS", (
        "o atestado cobre cada arquivo do SHA256SUMS"
    )
    assert wf["jobs"]["integridade"]["permissions"] == {
        "contents": "read",
        "id-token": "write",
        "attestations": "write",
    }
    # o `act` não tem o token OIDC: só esse passo é pulado, e o resto roda de verdade
    assert atesta[0]["if"] == "${{ !env.ACT }}"
    assert [p["name"] for p in passos if "if" in p] == [atesta[0]["name"]]


def test_a_integridade_espera_todos_os_arquivos_e_quem_publica_espera_a_integridade(
    wf: dict[str, Any],
) -> None:
    assert {"build", "appimage", "deb", "flatpak"} <= set(_needs(wf, "integridade"))
    assert "integridade" in _needs(wf, "github-release") and "integridade" in _needs(wf, "pypi")
    for antigo in ("deb-install-smoke", "guarda-ci"):
        assert antigo in _needs(wf, "github-release"), f"{antigo} continua barrando a publicação"


def test_quem_publica_confere_o_sums_antes_e_leva_o_sha256sums_para_a_release(
    wf: dict[str, Any],
) -> None:
    shell = _shell(wf, "github-release")
    assert shell.index("sums.py conferir") < shell.index("publicar.py")
    for padrao in ("*.whl", "*.tar.gz", "*.AppImage", "*.deb", "*.flatpak"):
        assert padrao in shell, f"a release sem um {padrao} não publica"
    assert "changelog.py notas" in shell
    baixa = [
        p
        for p in wf["jobs"]["github-release"]["steps"]
        if str(p.get("uses", "")).startswith("actions/download-artifact")
    ]
    assert baixa and baixa[0]["with"]["merge-multiple"] is True


def test_a_tag_diz_a_versao_do_pacote_antes_de_qualquer_build(wf: dict[str, Any]) -> None:
    nomes = [p.get("name", "") for p in wf["jobs"]["build"]["steps"]]
    assert "A tag diz a versão do pacote" in nomes
    assert nomes.index("A tag diz a versão do pacote") < nomes.index("Build wheel + sdist")
    assert "versao.py conferir-tag" in _shell(wf, "build")


def test_os_pacotes_de_distro_seguem_a_versao_depois_da_publicacao(wf: dict[str, Any]) -> None:
    assert "github-release" in _needs(wf, "pacotes")
    shell = _shell(wf, "pacotes")
    assert "pacotes.py preparar" in shell and "pacotes.py abrir-pr" in shell
    abrir = next(p for p in wf["jobs"]["pacotes"]["steps"] if "abrir-pr" in str(p.get("run", "")))
    assert abrir["if"] == "${{ vars.PACOTES_REPOS != '' }}", (
        "sem repositório de pacote declarado, só prepara"
    )


def test_todo_job_do_release_tem_decisao_no_ci_de_casa(wf: dict[str, Any]) -> None:
    decididos = {
        ln.split("|")[1]
        for ln in (RAIZ / "scripts/ci-local/jobs.txt").read_text(encoding="utf-8").splitlines()
        if ln.split("|")[0] in ("ROLA", "FORA-DE-CASA")
    }
    assert {"integridade", "pacotes", "github-release"} <= decididos


# ---------------------------------------------------------------------------
# 6. As notas automáticas do GitHub e o arquivo do repositório
# ---------------------------------------------------------------------------


def _rotulos_do_repositorio() -> list[str]:
    dados = yaml.safe_load(REPOSITORIO_YML.read_text(encoding="utf-8"))
    return [r["nome"] for r in dados["rotulos"]["lista"]]


def test_as_notas_automaticas_agrupam_pelos_rotulos_de_area_do_repositorio() -> None:
    notas = yaml.safe_load(NOTAS_YML.read_text(encoding="utf-8"))["changelog"]
    usados = [rotulo for c in notas["categories"] for rotulo in c["labels"] if rotulo != "*"]
    existentes = _rotulos_do_repositorio()
    assert [r for r in usados if r not in existentes] == [], "rótulo que não existe no repositório"
    areas = [r for r in existentes if r.startswith("área: ")]
    assert sorted(a for a in usados if a.startswith("área: ")) == sorted(areas), (
        "uma categoria por área, e só elas"
    )
    assert notas["categories"][-1]["labels"] == ["*"], "o que não casa cai na última"
    assert all(r in existentes for r in notas["exclude"]["labels"])
    # a mesma frase que o resto do texto público: nada da casa
    saida = subprocess.run(
        [sys.executable, str(RAIZ / "scripts/check_texto_publico.py")],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        check=False,
    )
    assert saida.returncode == 0, saida.stdout[-400:]


def test_a_serie_e_o_bloco_release_do_arquivo_do_repositorio() -> None:
    dados = yaml.safe_load(REPOSITORIO_YML.read_text(encoding="utf-8"))
    assert dados["release"] == {"serie": "0.9"}
    assert dados["seguranca"]["releases_imutaveis"] == {"ligada": True}


# ---------------------------------------------------------------------------
# 7. O main avança na release: a assinatura com a exceção de quem administra
# ---------------------------------------------------------------------------


def _aplicar_modulo() -> Any:
    spec = importlib.util.spec_from_file_location("aplicar_da_release", APLICAR)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["aplicar_da_release"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _historia(gh: Mentira, assinados: bool) -> None:
    """Um `dev` e um `main` atrás dele, com commits que o main não tem (sem assinatura)."""
    gh.mudar(
        ramos={"dev": "c3", "main": "c0"},
        commits={
            "c0": {"pai": None, "assinado": False},
            "c1": {"pai": "c0", "assinado": assinados},
            "c2": {"pai": "c1", "assinado": assinados},
            "c3": {"pai": "c2", "assinado": assinados},
        },
    )


def _avancar(ramo: str, sha: str, *, force: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", "api", "-i", "-X", "PATCH", f"repos/{SLUG}/git/refs/heads/{ramo}", "--input", "-"],
        input=json.dumps({"sha": sha, "force": force}),
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def repositorio_aplicado(gh: Mentira) -> Mentira:
    aplicar = _aplicar_modulo()
    assert (
        aplicar.principal(
            ["--repo", SLUG, "--arquivo", str(REPOSITORIO_YML), "--aplicar", "--so", "rulesets"]
        )
        == 0
    )
    assert next(r["name"] for r in gh.estado["rulesets"]).startswith("A história do dev")
    return gh


def test_o_main_avanca_por_quem_administra_e_e_recusado_para_quem_nao_administra(
    repositorio_aplicado: Mentira,
) -> None:
    gh = repositorio_aplicado
    _historia(gh, assinados=False)
    r = _avancar("main", "c3")
    assert r.stdout.startswith("HTTP/2.0 200"), r.stdout + r.stderr
    assert gh.estado["ramos"]["main"] == "c3"
    # quem não administra: o mesmo avanço, o mesmo ruleset, e o servidor recusa
    _historia(gh, assinados=False)
    gh.mudar(user="visitante")
    recusado = _avancar("main", "c3")
    assert (
        "HTTP/2.0 422" in recusado.stdout
        and "Commits must have verified signatures" in recusado.stdout
    )
    assert gh.estado["ramos"]["main"] == "c0"


def test_no_dev_nem_quem_administra_empurra_commit_sem_assinatura(
    repositorio_aplicado: Mentira,
) -> None:
    gh = repositorio_aplicado
    _historia(gh, assinados=False)
    gh.mudar(ramos={"dev": "c0", "main": "c0"})
    r = _avancar("dev", "c3")
    mensagem = json.loads(r.stdout.split("\n\n", 1)[1])["message"]
    assert (
        "HTTP/2.0 422" in r.stdout
        and "A história do dev" in mensagem
        and "verified signatures" in mensagem
    )
    # com os commits assinados o dev avança: a regra barra o que não está assinado, e só isso
    _historia(gh, assinados=True)
    gh.mudar(ramos={"dev": "c0", "main": "c0"})
    assert _avancar("dev", "c3").stdout.startswith("HTTP/2.0 200")


def test_mordida_sem_a_excecao_no_ruleset_do_main_o_administrador_e_recusado(
    gh: Mentira, tmp_path: Path
) -> None:
    """Sem a exceção do `main`, o avanço da release volta a ser recusado pelos commits antigos."""
    dados = yaml.safe_load(REPOSITORIO_YML.read_text(encoding="utf-8"))
    do_main = next(r for r in dados["rulesets"] if r.get("assinatura") and r["ramos"] == ["main"])
    do_main.pop("excecao")
    arq = tmp_path / "sem-excecao.yml"
    arq.write_text(yaml.safe_dump(dados, allow_unicode=True, sort_keys=False), encoding="utf-8")
    aplicar = _aplicar_modulo()
    assert (
        aplicar.principal(["--repo", SLUG, "--arquivo", str(arq), "--aplicar", "--so", "rulesets"])
        == 0
    )
    _historia(gh, assinados=False)
    r = _avancar("main", "c3")
    assert "HTTP/2.0 422" in r.stdout and "verified signatures" in r.stdout


def test_o_ruleset_do_main_chega_ao_servidor_com_a_excecao_de_administrador(
    repositorio_aplicado: Mentira,
) -> None:
    gh = repositorio_aplicado
    do_main = next(
        r
        for r in gh.estado["rulesets"]
        if r["conditions"]["ref_name"]["include"] == ["refs/heads/main"]
        and any(x["type"] == "required_signatures" for x in r["rules"])
    )
    assert do_main["bypass_actors"] == [
        {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}
    ]
    do_dev = next(
        r
        for r in gh.estado["rulesets"]
        if r["conditions"]["ref_name"]["include"] == ["refs/heads/dev"]
        and any(x["type"] == "required_signatures" for x in r["rules"])
    )
    assert do_dev["bypass_actors"] == []
    versoes = next(r for r in gh.estado["rulesets"] if r["target"] == "tag")
    assert versoes["bypass_actors"] == [], "as versões publicadas não têm exceção para ninguém"


# ---------------------------------------------------------------------------
# 8. O gesto do PyPI fica escrito: o `aplicar.py --conferir` avisa
# ---------------------------------------------------------------------------


def test_o_conferir_avisa_enquanto_o_publicador_de_confianca_do_pypi_nao_foi_registrado(
    gh: Mentira, tmp_path: Path
) -> None:
    aplicar = _aplicar_modulo()
    detalhe = tmp_path / "detalhe.txt"
    aplicar.principal(
        [
            "--repo",
            SLUG,
            "--arquivo",
            str(REPOSITORIO_YML),
            "--conferir",
            "--so",
            "",
            "--detalhe",
            str(detalhe),
        ]
    )
    texto = detalhe.read_text(encoding="utf-8")
    assert "aviso: release: o publicador de confiança do PyPI não está registrado" in texto
    assert (
        "https://pypi.org/manage/account/publishing/" in texto
        and "release.yml" in texto
        and "pypi" in texto
    )
    # feito o gesto, a variável diz «true» e o aviso some
    gh.mudar(variaveis={"PYPI_PUBLISH": "true"})
    aplicar.principal(
        ["--repo", SLUG, "--arquivo", str(REPOSITORIO_YML), "--conferir", "--detalhe", str(detalhe)]
    )
    assert "aviso: release" not in detalhe.read_text(encoding="utf-8")


def test_o_aviso_do_pypi_nao_muda_o_codigo_de_saida(gh: Mentira) -> None:
    aplicar = _aplicar_modulo()
    gh.mudar(variaveis={"PYPI_PUBLISH": "true"})
    com = aplicar.principal(["--repo", SLUG, "--arquivo", str(REPOSITORIO_YML), "--conferir"])
    gh.mudar(variaveis={})
    sem = aplicar.principal(["--repo", SLUG, "--arquivo", str(REPOSITORIO_YML), "--conferir"])
    assert com == sem, (
        "o aviso é só aviso: o que falta é um gesto de quem mantém, não uma diferença do arquivo"
    )


def test_o_arquivo_recusa_serie_torta() -> None:
    aplicar = _aplicar_modulo()
    dados = yaml.safe_load(REPOSITORIO_YML.read_text(encoding="utf-8"))
    assert not [e for e in aplicar.validar(dados) if e.startswith("release")]
    for torta in ("", "v0.9", "0.9.x", None, 0.9):
        dados["release"]["serie"] = torta
        assert any(e.startswith("release.serie") for e in aplicar.validar(dados)), torta
    del dados["release"]["serie"]
    assert any(e.startswith("release.serie") for e in aplicar.validar(dados))


# ---------------------------------------------------------------------------
# 9. Os arquivos de pacote seguem a versão
# ---------------------------------------------------------------------------


def _brinquedo_na_versao(brinquedo: Path, numero: str = "0.9.5") -> None:
    assert rodar(VERSAO, "gravar", numero, "--data", "2026-10-07", raiz=brinquedo).returncode == 0


def test_os_pacotes_saem_na_versao_da_tag_com_o_hash_do_tarball(
    brinquedo: Path, tmp_path: Path
) -> None:
    _brinquedo_na_versao(brinquedo)
    tarball = tmp_path / "fonte.tar.gz"
    tarball.write_bytes(b"o tarball da tag v0.9.5")
    saida = tmp_path / "pacotes"
    r = rodar(
        PACOTES,
        "preparar",
        "--numero",
        "0.9.5",
        "--tarball",
        str(tarball),
        "--saida",
        str(saida),
        raiz=brinquedo,
    )
    assert r.returncode == 0, r.stdout
    esperado = hashlib.sha256(b"o tarball da tag v0.9.5").hexdigest()
    assert f"sha256sums=('{esperado}')" in (saida / "arch" / "PKGBUILD").read_text(encoding="utf-8")
    assert "pkgver=0.9.5" in (saida / "arch" / "PKGBUILD").read_text(encoding="utf-8")
    assert re.search(
        r"^Version:\s*0\.9\.5$",
        (saida / "fedora" / "hefesto-dualsense4unix.spec").read_text(encoding="utf-8"),
        re.M,
    )
    assert re.search(
        r"^Version:\s*0\.9\.5$", (saida / "debian" / "control").read_text(encoding="utf-8"), re.M
    )
    assert 'version = "0.9.5";' in (saida / "nix" / "package.nix").read_text(encoding="utf-8")
    # o PKGBUILD do repositório fica com SKIP: o hash só existe depois da tag
    assert "sha256sums=('SKIP')" in (brinquedo / "packaging/arch/PKGBUILD").read_text(
        encoding="utf-8"
    )
    segunda = rodar(
        PACOTES,
        "preparar",
        "--numero",
        "0.9.5",
        "--tarball",
        str(tarball),
        "--saida",
        str(saida),
        raiz=brinquedo,
    )
    assert segunda.returncode == 0 and "já tem os arquivos" in primeira_linha(segunda)
    assert (
        rodar(
            PACOTES,
            "preparar",
            "--numero",
            "0.9.5",
            "--tarball",
            str(tarball),
            "--saida",
            str(saida),
            "--conferir",
            raiz=brinquedo,
        ).returncode
        == 0
    )


def test_mordida_arquivo_de_pacote_numa_versao_que_nao_e_a_da_tag_reprova(
    brinquedo: Path, tmp_path: Path
) -> None:
    _brinquedo_na_versao(brinquedo)
    spec = brinquedo / "packaging/fedora/hefesto-dualsense4unix.spec"
    spec.write_text(
        spec.read_text(encoding="utf-8").replace(
            "Version:        0.9.5", "Version:        0.9.4.5"
        ),
        encoding="utf-8",
    )
    tarball = tmp_path / "fonte.tar.gz"
    tarball.write_bytes(b"x")
    r = rodar(
        PACOTES,
        "preparar",
        "--numero",
        "0.9.5",
        "--tarball",
        str(tarball),
        "--saida",
        str(tmp_path / "p"),
        raiz=brinquedo,
    )
    assert (
        r.returncode == 1
        and "packaging/fedora/hefesto-dualsense4unix.spec: diz 0.9.4.5 e a tag é 0.9.5" in r.stdout
    )
    assert not (tmp_path / "p").exists(), "nada sai com um arquivo fora da versão"


def test_o_pr_de_atualizacao_abre_no_repositorio_de_pacote_com_o_autor_do_commit_da_tag(
    brinquedo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _brinquedo_na_versao(brinquedo)
    git(brinquedo, "add", "-A")
    commitar(brinquedo, "chore(release): 0.9.5")
    tarball = tmp_path / "fonte.tar.gz"
    tarball.write_bytes(b"fonte")
    saida = tmp_path / "pacotes"
    assert (
        rodar(
            PACOTES,
            "preparar",
            "--numero",
            "0.9.5",
            "--tarball",
            str(tarball),
            "--saida",
            str(saida),
            raiz=brinquedo,
        ).returncode
        == 0
    )
    # o repositório de pacote: um bare local; o `gh` de fachada clona dele e grava o PR que abriria
    remoto = tmp_path / "pacote.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remoto))
    semente = tmp_path / "semente"
    git(tmp_path, "clone", "-q", str(remoto), str(semente))
    (semente / "PKGBUILD").write_text("pkgver=0.9.4.5\n", encoding="utf-8")
    git(semente, "add", "-A")
    git(semente, "checkout", "-q", "-b", "main")
    commitar(semente, "base do pacote")
    git(semente, "push", "-q", "origin", "main")
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    prs = tmp_path / "prs.jsonl"
    fachada = bin_ / "gh"
    fachada.write_text(
        "#!/bin/sh\n"
        'if [ "$1 $2" = "repo clone" ]; then exec git clone -q ' + str(remoto) + ' "$4"; fi\n'
        'if [ "$1 $2" = "pr create" ]; then echo "$@" >> ' + str(prs) + "; exit 0; fi\n"
        "exit 2\n",
        encoding="utf-8",
    )
    fachada.chmod(0o755)
    env = dict(
        os.environ,
        PATH=f"{bin_}{os.pathsep}{os.environ['PATH']}",
        **{k: v for k, v in _env_git().items() if k.startswith("GIT_")},
    )
    r = rodar(
        PACOTES,
        "abrir-pr",
        "--numero",
        "0.9.5",
        "--pasta",
        str(saida),
        "--repos",
        "Hefesto-Team/pacote-arch:arch",
        raiz=brinquedo,
        env=env,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "atualiza-0.9.5" in git(remoto, "branch", "--list")
    assert "Pessoa Teste" in git(remoto, "log", "-1", "--format=%an", "atualiza-0.9.5")
    conteúdo = git(remoto, "show", "atualiza-0.9.5:PKGBUILD")
    assert "pkgver=0.9.5" in conteúdo and "sha256sums=('" in conteúdo
    pedido = prs.read_text(encoding="utf-8")
    assert "--repo Hefesto-Team/pacote-arch" in pedido and "--head atualiza-0.9.5" in pedido
    # distro que o artefato não tem: recusa antes de clonar
    ruim = rodar(
        PACOTES,
        "abrir-pr",
        "--numero",
        "0.9.5",
        "--pasta",
        str(saida),
        "--repos",
        "Hefesto-Team/x:gentoo",
        raiz=brinquedo,
        env=env,
    )
    assert ruim.returncode == 2


def test_o_publicar_nao_importa_o_que_nao_usa() -> None:
    """Os scripts de `scripts/release/` rodam no `python3` pelado do runner: só a stdlib."""
    permitidos = set(sys.stdlib_module_names) | {
        "_comum",
        "numero",
        "changelog",
        "sums",
        "publico",
        "publicar",
        "pacotes",
    }
    for arq in RELEASE.glob("*.py"):
        for ln in arq.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)", ln)
            if m:
                assert m.group(1) in permitidos, f"{arq.name}: {ln.strip()}"


# ---------------------------------------------------------------------------
# 10. A triagem da issue aceita: o outro lado do ciclo da sprint
# ---------------------------------------------------------------------------

TRIAGEM_YML = RAIZ / ".github" / "workflows" / "triagem.yml"
ROTULOS_YML = RAIZ / ".github" / "workflows" / "rotulos.yml"


def _eventos(arquivo: Path) -> set[tuple[str, str]]:
    dados = yaml.safe_load(arquivo.read_text(encoding="utf-8"))
    gatilho = dados.get("on", dados.get(True))  # o YAML 1.1 lê `on` como verdadeiro
    return {
        (evento, tipo)
        for evento, cfg in gatilho.items()
        for tipo in (cfg or {}).get("types", ["*"])
    }


def test_a_triagem_ouve_so_o_rotulo_aceito_e_o_rotulos_yml_ouve_outros_eventos() -> None:
    triagem = _eventos(TRIAGEM_YML)
    assert triagem == {("issues", "labeled")}
    # o dono de cada coisa: o que acontece quando a issue ABRE ou é EDITADA é do `rotulos.yml`, e o que
    # acontece quando ela é ACEITA é da triagem; nenhum evento é dos dois
    assert triagem.isdisjoint(_eventos(ROTULOS_YML))
    job = yaml.safe_load(TRIAGEM_YML.read_text(encoding="utf-8"))["jobs"]["aceita"]
    assert job["if"] == "github.event.label.name == 'aceito'"
    assert job["permissions"] == {"contents": "read", "issues": "write"}


def test_a_triagem_nao_refaz_o_que_o_rotulos_yml_ja_faz() -> None:
    texto = TRIAGEM_YML.read_text(encoding="utf-8")
    for dele in ("add-to-project", "actions/labeler", "triagem.py", "precisa do doctor"):
        assert dele not in texto, f"«{dele}» é do rotulos.yml: dois donos para a mesma coisa"
    assert "add-to-project" in ROTULOS_YML.read_text(encoding="utf-8")


def test_o_rotulo_aceito_e_um_dos_do_arquivo_do_repositorio_e_a_lista_e_uma_so() -> None:
    assert "aceito" in _rotulos_do_repositorio()
    # nenhum fluxo cria rótulo: `gh issue create --label` de nome que não existe o cria calado
    for fluxo in (TRIAGEM_YML, ROTULOS_YML):
        assert "gh label create" not in fluxo.read_text(encoding="utf-8")


def test_a_triagem_avisa_uma_vez_e_nenhum_dado_do_evento_entra_no_shell() -> None:
    dados = yaml.safe_load(TRIAGEM_YML.read_text(encoding="utf-8"))
    passo = dados["jobs"]["aceita"]["steps"][0]
    assert "${{" not in passo["run"], "o dado do evento chega pelo env, nunca dentro do script"
    assert set(passo["env"]) == {"GH_TOKEN", "NUMERO", "REPO"}
    assert "grep -qF '<!-- aceito -->'" in passo["run"] and "exit 0" in passo["run"]
    corpo = passo["run"].split("<<'AVISO'")[1]
    assert corpo.lstrip().startswith("<!-- aceito -->"), (
        "o aviso carrega a marca que a conferência procura"
    )
