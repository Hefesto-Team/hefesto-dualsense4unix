"""Testes do portão que reprova documento citando arquivo inexistente.

Sprint PORTÃO-VIVO-01, bloco F. A exigência escrita lá é literal:

    "Prova de que morde: ele tem de reprovar HOJE, sem nenhuma alteração
     [...]. Se passar no repositório como está, está cego."

Por isso o primeiro teste é o único da suíte que roda contra a árvore REAL:
ele exige que `docs/adr/011-glyphs-vs-emojis.md` continue sendo pego enquanto
afirmar que um hook chamado guardian existe. Se alguém enfraquecer o
validador -- por exemplo parando de cobrar nome de arquivo solto, sem barra --
esse teste cai na hora, que é exatamente o ponto.

Os demais testes usam repositório falso em tmp_path e existem para provar o
outro lado da moeda: o portão precisa dar VERDE no caso legítimo. Um gate que
reprova tudo é tão inútil quanto um que não reprova nada.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

RAIZ_REAL = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ_REAL / "scripts" / "validar-referencias-docs.py"

#: O documento e a linha que a sprint nomeia como prova.
ADR_GLIFOS = "docs/adr/011-glyphs-vs-emojis.md"
LINHA_DA_PROVA = 18
NOME_FANTASMA = "guardian.py"


def rodar(*args: str) -> subprocess.CompletedProcess[str]:
    """Executa o validador e devolve o processo terminado."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=RAIZ_REAL,
        check=False,
    )


@pytest.fixture
def repo_falso(tmp_path: Path) -> Path:
    """Repositório mínimo: um arquivo real e uma pasta docs/ vazia."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "existe_de_verdade.sh").write_text(
        "#!/usr/bin/env bash\n", encoding="utf-8"
    )
    pacote = tmp_path / "src" / "pacote" / "gui"
    pacote.mkdir(parents=True)
    (pacote / "main.glade").write_text("<interface/>\n", encoding="utf-8")
    return tmp_path


def escrever_doc(raiz: Path, nome: str, texto: str) -> Path:
    caminho = raiz / "docs" / nome
    caminho.write_text(texto, encoding="utf-8")
    return caminho


# ---------------------------------------------------------------------------
# A prova da sprint: reprovar HOJE, na árvore real, sem alterar nada.
# ---------------------------------------------------------------------------


def test_hook_fantasma_citado_por_um_adr_reprova(repo_falso: Path) -> None:
    """A forma exata do defeito que fez este portão nascer.

    Até 27/07/2026 este teste apontava para o ADR-011 da árvore real, que
    afirmava que ``guardian.py`` cobria os emojis proibidos -- um arquivo que
    nunca existiu. O portão passou a existir, o ADR foi corrigido no mesmo dia
    (passou a citar ``scripts/validar-glifos.py``, que existe), e o teste
    reprovou -- porque **exigia que o defeito continuasse lá**.

    Isso é teste-muralha: ele travava o defeito e proibia a correção. Esta casa
    já tem dívida registrada dessa classe, e a lição vale mais que o caso: um
    portão que precisa de sujeira na árvore para provar que funciona deixa de
    provar no instante em que alguém limpa.

    A forma do caso original está preservada aqui, em caixa própria: nome de
    arquivo **solto**, sem barra, dentro de uma frase afirmativa.
    """
    escrever_doc(
        repo_falso,
        "adr-de-mentira.md",
        "# ADR\n"
        "\n"
        f"O hook `{NOME_FANTASMA}` cobre os proibidos.\n",
    )

    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 1, (
        "o validador ACEITOU um nome de arquivo solto inexistente -- está cego.\n"
        f"saída: {proc.stdout}{proc.stderr}"
    )
    assert NOME_FANTASMA in proc.stdout
    assert "adr-de-mentira.md:3" in proc.stdout, (
        f"a linha do defeito não apareceu no relatório.\nsaída: {proc.stdout}"
    )


def test_a_arvore_real_esta_limpa() -> None:
    """Regressão: o defeito que originou o portão não volta.

    Este é o teste que substitui a muralha. Ele trava o **zero**, não a
    sujeira -- e por isso continua fazendo sentido depois da correção.
    """
    assert not list(RAIZ_REAL.rglob(NOME_FANTASMA)), (
        f"{NOME_FANTASMA} passou a existir na árvore; a premissa mudou"
    )

    proc = rodar("--all")

    assert proc.returncode == 0, (
        "há referência morta em docs/:\n" f"{proc.stdout}{proc.stderr}"
    )


# ---------------------------------------------------------------------------
# O outro lado: o portão precisa dar verde no caso legítimo.
# ---------------------------------------------------------------------------


def test_documento_que_so_cita_arquivo_existente_passa(repo_falso: Path) -> None:
    escrever_doc(
        repo_falso,
        "ok.md",
        "O instalador roda `scripts/existe_de_verdade.sh` no fim.\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, proc.stdout


def test_caminho_encurtado_casa_por_sufixo(repo_falso: Path) -> None:
    """A casa cita `gui/main.glade` e nunca o caminho completo -- e isso vale.

    Sem a regra de sufixo, este teste vira vermelho e o gate produz dezenas de
    falsos positivos por documento.
    """
    escrever_doc(repo_falso, "curto.md", "A janela mora em `gui/main.glade`.\n")
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, proc.stdout


def test_nome_solto_de_configuracao_nao_e_cobrado(repo_falso: Path) -> None:
    """`daemon.toml` vive em ~/.config, não no repositório: não é defeito."""
    escrever_doc(
        repo_falso,
        "config.md",
        "A preferência fica em `daemon.toml`, ao lado de `controllers.json`.\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, proc.stdout


def test_comando_de_terminal_em_bloco_cercado_nao_e_cobrado(
    repo_falso: Path,
) -> None:
    """Dentro de bloco de código mora comando, não referência de repositório."""
    escrever_doc(
        repo_falso,
        "bloco.md",
        "Reproduza assim:\n\n```\nfind . -name `sumiu_faz_tempo.py`\n```\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, proc.stdout


# ---------------------------------------------------------------------------
# E o portão precisa MORDER no repositório falso também.
# ---------------------------------------------------------------------------


def test_nome_solto_inexistente_reprova(repo_falso: Path) -> None:
    escrever_doc(
        repo_falso,
        "fantasma.md",
        "O hook `guardiao_imaginario.py` cobre os casos proibidos.\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 1, proc.stdout
    assert "guardiao_imaginario.py" in proc.stdout
    assert "fantasma.md:1" in proc.stdout


def test_link_markdown_para_documento_inexistente_reprova(repo_falso: Path) -> None:
    """A sprint cita três sprints linkadas no índice que não têm arquivo."""
    escrever_doc(
        repo_falso,
        "indice.md",
        "- [SPRINT-QUE-NAO-EXISTE-01](2026-01-01-SPRINT-QUE-NAO-EXISTE-01.md)\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 1, proc.stdout
    assert "2026-01-01-SPRINT-QUE-NAO-EXISTE-01.md" in proc.stdout


def test_caminho_com_barra_inexistente_reprova(repo_falso: Path) -> None:
    escrever_doc(
        repo_falso,
        "caminho.md",
        "Ele invocava um `scripts/nunca_existiu.sh` que sumiu.\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 1, proc.stdout
    assert "scripts/nunca_existiu.sh" in proc.stdout


# ---------------------------------------------------------------------------
# Escapes -- para o portão não ser impossível de satisfazer.
# ---------------------------------------------------------------------------


def test_marcador_de_isencao_silencia_a_linha(repo_falso: Path) -> None:
    """A sprint que DOCUMENTA a ausência precisa poder citar o ausente."""
    escrever_doc(
        repo_falso,
        "isento.md",
        "O hook `guardiao_imaginario.py` nunca existiu. <!-- ref-externa -->\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, proc.stdout


def test_arquivo_de_projeto_de_fora_nao_e_cobrado(repo_falso: Path) -> None:
    """`pydualsense.py` é de terceiros; cobrar a presença dele seria errado."""
    escrever_doc(
        repo_falso,
        "externo.md",
        "O layout está confirmado em `pydualsense.py:551-567`.\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, proc.stdout


def test_caminho_absoluto_do_sistema_nao_e_cobrado(repo_falso: Path) -> None:
    """`/etc/udev/rules.d/70-x.rules` é do sistema, não deste repositório."""
    escrever_doc(
        repo_falso,
        "sistema.md",
        "A regra fica em `/etc/udev/rules.d/70-inexistente.rules` na máquina.\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, proc.stdout
