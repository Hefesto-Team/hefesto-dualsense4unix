"""O PORTÃO DA COLISÃO DE SPRINTS — e ele tem de acusar o que a MÃO achou."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import exigir_insumo_fora_do_git

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "check_colisao_de_sprints.py"
SPRINTS = RAIZ / "docs" / "process" / "sprints"

exigir_insumo_fora_do_git(
    "scripts/check_colisao_de_sprints.py",
    "docs/process/sprints",
)

_spec = importlib.util.spec_from_file_location("_colisao", SCRIPT)
assert _spec and _spec.loader
colisao = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(colisao)


def _sprint(nome: str, *, posse=None, cria=None, depois_de=None, nao_toca=None) -> str:
    linhas = ["---", f"sprint: {nome}", "posse:"]
    for agente, arquivos in (posse or {}).items():
        linhas.append(f"  {agente}:")
        linhas += [f"    - {a}" for a in arquivos]
    linhas.append("cria:")
    linhas += [f"  - {a}" for a in (cria or [])]
    linhas.append("bancada: false")
    linhas.append("depois_de:")
    linhas += [f"  - {a}" for a in (depois_de or [])]
    linhas.append("nao_toca:")
    linhas += [f"  - {a}" for a in (nao_toca or [])]
    linhas += ["---", "", "# o corpo, que a régua NUNCA lê", ""]
    return "\n".join(linhas)


def _confere(**sprints: str) -> list[str]:
    anotadas = {}
    for nome, texto in sprints.items():
        dados = colisao.le_frontmatter(texto, nome)
        assert dados is not None, f"o dublê {nome} não foi lido como frontmatter"
        anotadas[Path(nome)] = dados
    return colisao.confere(anotadas)


def test_sprint_sem_frontmatter_nao_e_erro_e_vira_divida() -> None:
    assert colisao.le_frontmatter("# uma sprint qualquer\n", "x.md") is None


def test_campo_desconhecido_e_recusado_dizendo_a_linha() -> None:
    texto = "---\nsprint: X\npossse:\n  A:\n---\n"
    with pytest.raises(colisao.FormatoInvalido) as exc:
        colisao.le_frontmatter(texto, "x.md")
    assert "possse" in str(exc.value) and "x.md:3" in str(exc.value)


def test_frontmatter_que_nunca_fecha_e_recusado() -> None:
    with pytest.raises(colisao.FormatoInvalido):
        colisao.le_frontmatter("---\nsprint: X\n", "x.md")


def _com_estado(texto: str, estado: str) -> str:
    return texto.replace("sprint: ", f"estado: {estado}\nsprint: ", 1)


def test_estado_desconhecido_e_recusado() -> None:
    with pytest.raises(colisao.FormatoInvalido) as exc:
        colisao.le_frontmatter(_com_estado(_sprint("X"), "pronta"), "x.md")
    assert "pronta" in str(exc.value) and "aberta" in str(exc.value)


def test_sem_estado_e_aberta_por_padrao() -> None:
    dados = colisao.le_frontmatter(_sprint("X"), "x.md")
    assert dados is not None and dados["estado"] == "aberta" and colisao.aberta(dados)


def test_sprint_feita_nao_disputa_posse() -> None:
    """Duas sprints no mesmo arquivo: com as duas abertas o portão grita; com"""
    abertas = _confere(
        a=_sprint("A-01", posse={"A": ["src/x.py"]}),
        b=_sprint("B-01", posse={"B": ["src/x.py"]}),
    )
    assert abertas, "a mordida: com as duas abertas tem de gritar"
    uma_feita = _confere(
        a=_com_estado(_sprint("A-01", posse={"A": ["src/x.py"]}), "feita"),
        b=_sprint("B-01", posse={"B": ["src/x.py"]}),
    )
    assert uma_feita == []


def test_espera_ela_nao_se_despacha_e_nao_disputa(tmp_path) -> None:
    """`espera-ela`: o código fechou, o gesto dela não — e a fila tem de dizer isso."""
    (tmp_path / "2026-09-21-ESPERA-01.md").write_text(
        _com_estado(_sprint("ESPERA-01", posse={"A": ["src/x.py"]}), "espera-ela"),
        encoding="utf-8",
    )
    (tmp_path / "2026-09-21-VIVA-01.md").write_text(
        _sprint("VIVA-01", posse={"B": ["src/x.py"]}), encoding="utf-8"
    )
    base = [sys.executable, str(SCRIPT), "--pasta", str(tmp_path)]

    r = subprocess.run([*base, "--exigir", "ESPERA-01"], capture_output=True, text=True)
    assert r.returncode == 1 and "espera-ela" in r.stderr, (
        "sprint que espera a mão dela não se despacha para agente"
    )
    r = subprocess.run([*base, "--abertas"], capture_output=True, text=True)
    assert "ESPERA-01" not in r.stdout and "VIVA-01" in r.stdout
    r = subprocess.run([*base, "--espera-ela"], capture_output=True, text=True)
    assert "ESPERA-01" in r.stdout and "VIVA-01" not in r.stdout

    sem_disputa = _confere(
        a=_com_estado(_sprint("A-01", posse={"A": ["src/x.py"]}), "espera-ela"),
        b=_sprint("B-01", posse={"B": ["src/x.py"]}),
    )
    assert sem_disputa == []


def test_espera_ela_nao_desce_para_arquivados() -> None:
    """Ela fica na pasta viva: é lá que a pauta da sessão com ela se lê."""
    movedor = SCRIPT.parent / "mover-sprints-fechadas.py"
    fonte = movedor.read_text(encoding="utf-8")
    linha = next(ln for ln in fonte.splitlines() if ln.startswith("FECHADOS"))
    assert "espera-ela" not in linha, (
        "`espera-ela` entrou na lista dos que descem para `arquivados/` — a "
        "sprint que espera a mão dela tem de ficar na pasta viva"
    )


def test_exigir_recusa_sprint_que_nao_esta_aberta(tmp_path) -> None:
    (tmp_path / "2026-09-06-FEITA-01.md").write_text(
        _com_estado(_sprint("FEITA-01", posse={"A": ["src/x.py"]}), "feita"),
        encoding="utf-8",
    )
    (tmp_path / "2026-09-06-VIVA-01.md").write_text(
        _sprint("VIVA-01", posse={"A": ["src/y.py"]}), encoding="utf-8"
    )
    base = [sys.executable, str(SCRIPT), "--pasta", str(tmp_path)]
    r = subprocess.run([*base, "--exigir", "FEITA-01"], capture_output=True, text=True)
    assert r.returncode == 1 and "estado: feita" in r.stderr
    r = subprocess.run([*base, "--exigir", "VIVA-01"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    r = subprocess.run([*base, "--abertas"], capture_output=True, text=True)
    assert "VIVA-01" in r.stdout and "FEITA-01" not in r.stdout


def test_nasce_reprovando_zero_na_arvore_de_verdade() -> None:
    r = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=RAIZ, capture_output=True, text=True
    )
    assert r.returncode == 0, (
        "o portão nasceu reprovando, e ele foi desenhado para nascer verde — "
        "sprint sem frontmatter é DÍVIDA, não reprovação:\n" + r.stdout + r.stderr
    )
    assert "DÍVIDA" in r.stdout, "a lista de dívida sumiu da saída:\n" + r.stdout


def test_exigir_recusa_sprint_sem_frontmatter_e_aceita_a_que_tem(tmp_path) -> None:
    """É o que o despachante chama para não deixar agente nascer sem posse."""
    (tmp_path / "2026-09-06-COM-POSSE-01.md").write_text(
        _sprint("COM-POSSE-01", posse={"A": ["src/x.py"]}), encoding="utf-8"
    )
    (tmp_path / "2026-09-06-SEM-FRONTMATTER-01.md").write_text(
        "# uma sprint sem posse\n", encoding="utf-8"
    )
    base = [sys.executable, str(SCRIPT), "--pasta", str(tmp_path)]
    r = subprocess.run([*base, "--exigir", "COM-POSSE-01"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr

    r = subprocess.run(
        [*base, "--exigir", "SEM-FRONTMATTER-01"], capture_output=True, text=True
    )
    assert r.returncode == 1 and "SEM-FRONTMATTER-01" in r.stderr

    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--exigir", "SPRINT-QUE-NAO-EXISTE"],
        cwd=RAIZ, capture_output=True, text=True,
    )
    assert r.returncode == 1
    assert "SPRINT-QUE-NAO-EXISTE" in r.stderr


def test_o_comentario_inline_nao_gruda_no_caminho() -> None:
    """Um `# dona: A` no fim da linha cegava o portão INTEIRO."""
    dados = colisao.le_frontmatter(
        _sprint(
            "COM-COMENTARIO",
            posse={"A1": ["src/alvo.py       # dona: outra frente", "src/limpo.py"]},
        ),
        "COM-COMENTARIO",
    )
    assert dados is not None
    assert dados["posse"]["A1"] == ["src/alvo.py", "src/limpo.py"], (
        "o comentário inline entrou no caminho. Enquanto ele estiver ali, este "
        f"caminho não casa com nenhum outro e a colisão fica invisível: "
        f"{dados['posse']['A1']!r}"
    )


def test_a_colisao_com_comentario_inline_e_acusada() -> None:
    """A prova de ponta a ponta: duas sprints, uma anotando o caminho."""
    achados = _confere(
        UMA=_sprint("UMA", posse={"A1": ["src/disputado.py"]}),
        OUTRA=_sprint(
            "OUTRA", posse={"B1": ["src/disputado.py   # cedo, mas edito"]}
        ),
    )
    assert any("src/disputado.py" in a for a in achados), (
        "as duas reivindicam o mesmo arquivo e uma o anotou — a colisão tem de "
        f"ser acusada mesmo assim. Achados: {achados!r}"
    )


def test_o_hash_colado_no_caminho_sobrevive() -> None:
    """A cura não pode ter começado a cortar caminho legítimo."""
    dados = colisao.le_frontmatter(
        _sprint("HASH", posse={"A1": ["src/rel#1.py"]}), "HASH"
    )
    assert dados is not None
    assert dados["posse"]["A1"] == ["src/rel#1.py"]
