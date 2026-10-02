"""A régua da grafia do nome MORDE — e recusa morder o identificador técnico."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts" / "check_a_grafia_do_nome.py"
CURA = RAIZ / "scripts" / "aplicar_a_grafia_do_nome.sh"

OS_TECNICOS = (
    'wm_class="Hefesto-Dualsense4Unix",',
    "StartupWMClass=Hefesto-Dualsense4Unix",
    "com.vitoriamaria.HefestoDualsense4Unix.desktop",
    'XBOX360_NAME = "Microsoft X-Box 360 pad (Hefesto - Dualsense4Unix virtual)"',
    'DEVICE_NAME = "Hefesto - Dualsense4Unix Virtual Keyboard"',
    'DEVICE_NAME = "Hefesto - Dualsense4Unix Virtual Mouse+Keyboard"',
)

_MOLDURA_LIMPA = (
    "src/hefesto_dualsense4unix/interface/janela.py",
    "src/hefesto_dualsense4unix/interface/ver.py",
)


def _carregar(raiz: Path):
    """O portão, com a raiz apontada para o repositório de brinquedo."""
    spec = importlib.util.spec_from_file_location("_grafia_sob_teste", PORTAO)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.RAIZ = raiz
    mod.ISENTOS = {}
    mod._MOLDURA = _MOLDURA_LIMPA
    return mod


@pytest.fixture()
def casa(tmp_path: Path) -> Path:
    """Um repositório de brinquedo com a moldura JÁ CURADA."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    for rel in _MOLDURA_LIMPA:
        alvo = tmp_path / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(
            "from hefesto_dualsense4unix.utils import identidade\n"
            "barra.set_title(identidade.atual().nome_longo)\n",
            encoding="utf-8",
        )
    (tmp_path / "README.md").write_text(
        "# Hefesto — DualSense4Unix\n", encoding="utf-8"
    )
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    return tmp_path


def test_a_arvore_curada_passa(casa: Path) -> None:
    mod = _carregar(casa)
    assert mod.a_grafia() == []
    assert mod.o_dono() == []


def test_a_grafia_errada_reprova(casa: Path) -> None:
    """PENEIRA 1 — a cura arrancada do texto."""
    (casa / "README.md").write_text("# Hefesto — Dualsense4Unix\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=casa, check=True)
    achados = _carregar(casa).a_grafia()
    assert [a[0] for a in achados] == ["README.md"], achados


def test_arquivo_novo_e_visto_sem_git_add(casa: Path) -> None:
    """Portão é cego a arquivo novo por padrão — este não é."""
    (casa / "NOVO.md").write_text("o Dualsense4Unix de ontem\n", encoding="utf-8")
    achados = _carregar(casa).a_grafia()
    assert [a[0] for a in achados] == ["NOVO.md"], achados


def test_o_identificador_tecnico_nao_reprova(casa: Path) -> None:
    """A METADE QUE UMA RÉGUA BARULHENTA ERRARIA."""
    (casa / "tecnicos.txt").write_text("\n".join(OS_TECNICOS) + "\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=casa, check=True)
    assert _carregar(casa).a_grafia() == []


def test_a_moldura_que_digita_o_nome_reprova(casa: Path) -> None:
    """PENEIRA 2 — a cura arrancada do DONO, com a grafia CERTA."""
    (casa / _MOLDURA_LIMPA[1]).write_text(
        'barra.set_title("Hefesto — DualSense4Unix")\n', encoding="utf-8"
    )
    subprocess.run(["git", "add", "-A"], cwd=casa, check=True)
    mod = _carregar(casa)
    assert mod.a_grafia() == []
    achados = mod.o_dono()
    assert [a[0] for a in achados] == [_MOLDURA_LIMPA[1], _MOLDURA_LIMPA[1]], achados


def test_a_moldura_que_some_reprova(casa: Path) -> None:
    """Régua que mede arquivo inexistente mede o mundo de ontem."""
    (casa / _MOLDURA_LIMPA[0]).unlink()
    achados = _carregar(casa).o_dono()
    assert achados and achados[0][0] == _MOLDURA_LIMPA[0]


def test_a_arvore_de_verdade_esta_verde() -> None:
    """O portão, rodado como o `portoes.sh` o roda."""
    r = subprocess.run(
        ["python3", str(PORTAO)], cwd=RAIZ, capture_output=True, text=True
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_cura_e_idempotente() -> None:
    """Rodar a cura numa árvore já curada não muda byte nenhum."""
    assert CURA.is_file(), f"{CURA} sumiu — a régua ficou sem cura a apontar"
    antes = subprocess.run(
        ["git", "status", "--porcelain"], cwd=RAIZ, capture_output=True, text=True
    ).stdout
    subprocess.run(["bash", str(CURA)], cwd=RAIZ, capture_output=True, text=True, check=True)
    depois = subprocess.run(
        ["git", "status", "--porcelain"], cwd=RAIZ, capture_output=True, text=True
    ).stdout
    assert antes == depois
