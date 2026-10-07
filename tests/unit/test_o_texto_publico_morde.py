"""O portão do texto público MORDE, e não morde o verbo."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts" / "check_texto_publico.py"


def _rodar(raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PORTAO), "--raiz", str(raiz)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _pagina(raiz: Path, texto: str, relativo: str = "docs/usage/pagina.md") -> Path:
    caminho = raiz / relativo
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(f"# Uma página\n\n{texto}\n", encoding="utf-8")
    return caminho


@pytest.mark.parametrize(
    ("frase", "reprova"),
    [
        ("Isto mudou por causa da decisão dela.", True),
        ("Clicar num cartão leva a fita para ele.", False),
        ("O defeito foi curado na FOO-BAR-01.", True),
        ("Veja docs/process/qualquer-coisa.md.", True),
        ("A régua da casa conferiu.", True),
        ("O portão do CI passou.", True),
        ("Medido na bancada.", True),
        ("Esta sprint entregou o botão.", True),
        ("O que esta casa aceita.", False),
        ("O que desta casa sai.", True),
        ("A decisão está no ADR-009, e o hash é SHA-256.", False),
        # nome de algoritmo com o número de bits NÃO é ID de sprint (a exceção é por forma) ...
        ("Os 4 últimos bytes são CRC-32, e o texto vem em UTF-16.", False),
        ("O CRC-64 e o CRC-16 também passam.", False),
        # ... e o ID real, mesmo com número que lembra bits, continua reprovando
        ("Curado na HARM-16.", True),
        ("Veja a SOM-02 e a CRC-32-01.", True),
        ("O CRC-32 passa, mas a MIC-USB-01 não.", True),
    ],
)
def test_a_frase(tmp_path: Path, frase: str, reprova: bool) -> None:
    _pagina(tmp_path, frase)
    r = _rodar(tmp_path)
    assert (r.returncode == 1) is reprova, (frase, r.returncode, r.stdout)
    if reprova:
        assert "docs/usage/pagina.md:3:" in r.stdout, r.stdout


def test_os_recibos_das_fotos_ficam_de_fora(tmp_path: Path) -> None:
    _pagina(tmp_path, "Nada aqui.")
    for recibo in (
        "docs/usage/assets/CONFERIDO-EM.txt",
        "docs/usage/assets/PROVA-DA-FOTO.txt",
        "docs/usage/assets/maximizada/PROVA-DA-FOTO.txt",
    ):
        _pagina(tmp_path, "conferido na bancada dela, FOO-BAR-01", recibo)
    r = _rodar(tmp_path)
    assert r.returncode == 0, r.stdout


def test_os_workflows_ficam_de_fora_e_o_resto_do_github_entra(tmp_path: Path) -> None:
    _pagina(tmp_path, "run: pytest  # FOO-BAR-01", ".github/workflows/ci.yml")
    assert _rodar(tmp_path).returncode == 0
    _pagina(tmp_path, "- [ ] a sprint", ".github/ISSUE_TEMPLATE/bug.md")
    r = _rodar(tmp_path)
    assert r.returncode == 1 and ".github/ISSUE_TEMPLATE/bug.md" in r.stdout, r.stdout


def test_o_readme_e_o_metainfo_entram(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("A escolha dela.\n", encoding="utf-8")
    meta = tmp_path / "flatpak" / "io.github.hefesto_team.hefesto_dualsense4unix.metainfo.xml"
    meta.parent.mkdir(parents=True)
    meta.write_text("<p>Veja a FOO-BAR-01.</p>\n", encoding="utf-8")
    r = _rodar(tmp_path)
    assert r.returncode == 1
    assert "README.md:1:" in r.stdout and "metainfo.xml:1:" in r.stdout, r.stdout


def _modulo():
    spec = importlib.util.spec_from_file_location("check_texto_publico", PORTAO)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def test_a_declaracao_isenta_so_a_linha_dela_e_a_velha_reprova(tmp_path: Path) -> None:
    modulo = _modulo()
    _pagina(tmp_path, "A Steam guarda a opção dela.")
    chave = ("docs/usage/pagina.md", "A Steam guarda a opção dela.")
    achados, velhas = modulo.medir(tmp_path, {chave: "o pronome é da Steam"})
    assert achados == [] and velhas == []
    _pagina(tmp_path, "A Steam guarda a própria opção.")
    achados, velhas = modulo.medir(tmp_path, {chave: "o pronome é da Steam"})
    assert achados == [] and velhas == [chave]


def test_a_arvore_de_hoje_passa() -> None:
    r = _rodar(RAIZ)
    assert r.returncode == 0, r.stdout


def test_as_paginas_do_protocolo_da_wiki_nao_trazem_o_vocabulario_de_dentro() -> None:
    """A Wiki do protocolo sai de `docs/protocol/`: a página que volta a dizer «régua»,
    «bancada» ou um código de tarefa fica segurada lá, calada. A do Proton fica de fora."""
    modulo = _modulo()
    achados = []
    for pagina in sorted((RAIZ / "docs" / "protocol").glob("*.md")):
        if pagina.name.startswith("proton-"):
            continue
        for numero, linha in enumerate(pagina.read_text(encoding="utf-8").splitlines(), 1):
            for nome, rx in modulo.EXPRESSOES:
                if rx.search(linha):
                    achados.append(f"{pagina.name}:{numero}: [{nome}]")
    assert achados == []


def test_o_que_a_lista_promete_varrer_existe(tmp_path: Path) -> None:
    """Um arquivo da lista que muda de nome não sai da varredura calado."""
    modulo = _modulo()
    assert sorted(modulo.ausentes(tmp_path)) == sorted(
        [
            "README.md",
            "NOTICE",
            "CHANGELOG.md",
            "flatpak/io.github.hefesto_team.hefesto_dualsense4unix.metainfo.xml",
            "docs/usage",
            ".github",
        ]
    )
    assert modulo.ausentes(RAIZ) == []


def test_um_nome_da_lista_que_sumiu_reprova_na_arvore_do_projeto(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    modulo = _modulo()
    monkeypatch.setattr(modulo, "ARQUIVOS", (*modulo.ARQUIVOS, "NAO-EXISTE.md"))
    assert modulo.main([]) == 1
    assert "NAO-EXISTE.md: está na lista do que se varre e não existe" in capsys.readouterr().out
