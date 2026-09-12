"""A régua da grafia do nome MORDE — e recusa morder o identificador técnico.

O portão é ``scripts/check_a_grafia_do_nome.py``. Ele tem duas peneiras, e este
arquivo arranca as duas curas para ver cada uma reprovar:

1. **a grafia** — ``Dualsense4Unix`` em texto reprova;
2. **o dono** — a moldura DIGITANDO o nome reprova, mesmo com a grafia certa.

E ele prova a metade que uma régua barulhenta erraria: os **quatro
identificadores técnicos** têm de passar. Uma régua que reprovasse o
``wm_class`` seria pior que a ausência dela — ela empurraria a próxima pessoa a
trocar a caixa de uma string que o ``StartupWMClass=`` do ``.desktop`` instalado
na máquina dela casa letra por letra, e o ícone sumiria da dock, calado.

**POR QUE UM DIRETÓRIO DE MENTIRA, e não a árvore:** arrancar a cura na árvore
viva significa reescrever 186 arquivos para depois desfazer. O portão lista por
``git ls-files`` com ``cwd`` na raiz dele, então a mordida roda o script com a
raiz apontada para um repositório de brinquedo, por ``_RAIZ`` monkeypatchado —
que é a única superfície que precisa mudar.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts" / "check_a_grafia_do_nome.py"
CURA = RAIZ / "scripts" / "aplicar_a_grafia_do_nome.sh"

#: Os quatro identificadores técnicos, escritos aqui e NÃO importados do portão.
#: Um teste que lê a constante do próprio código sob teste passa com a cura
#: arrancada — a mordida exige que a régua seja independente do que ela mede.
OS_TECNICOS = (
    'wm_class="Hefesto-Dualsense4Unix",',
    "StartupWMClass=Hefesto-Dualsense4Unix",
    "com.vitoriamaria.HefestoDualsense4Unix.desktop",
    'XBOX360_NAME = "Microsoft X-Box 360 pad (Hefesto - Dualsense4Unix virtual)"',
    'DEVICE_NAME = "Hefesto - Dualsense4Unix Virtual Keyboard"',
    'DEVICE_NAME = "Hefesto - Dualsense4Unix Virtual Mouse+Keyboard"',
)

_MOLDURA_LIMPA = (
    "src/hefesto_dualsense4unix/gui/ponte_da_tela.py",
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
    """Portão é cego a arquivo novo por padrão — este não é.

    Foi assim que quatro endereços de fixture moraram no arquivo vivo dela
    (cicatriz ANONIMATO-CEGO-A-ARQUIVO-NOVO-01). A listagem leva
    ``--others --exclude-standard``.
    """
    (casa / "NOVO.md").write_text("o Dualsense4Unix de ontem\n", encoding="utf-8")
    achados = _carregar(casa).a_grafia()
    assert [a[0] for a in achados] == ["NOVO.md"], achados


def test_o_identificador_tecnico_nao_reprova(casa: Path) -> None:
    """A METADE QUE UMA RÉGUA BARULHENTA ERRARIA.

    Os seis são `wm_class`, `StartupWMClass=`, o app-id do Flatpak e os três
    nós que o kernel publica. Nenhum é o nome do produto em texto; todos são
    casados letra por letra por alguém de fora deste repositório.
    """
    (casa / "tecnicos.txt").write_text("\n".join(OS_TECNICOS) + "\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=casa, check=True)
    assert _carregar(casa).a_grafia() == []


def test_a_moldura_que_digita_o_nome_reprova(casa: Path) -> None:
    """PENEIRA 2 — a cura arrancada do DONO, com a grafia CERTA.

    É este teste que separa esta régua de um `grep`: a grafia certa digitada
    em dois lugares é a próxima divergência esperando acontecer.
    """
    (casa / _MOLDURA_LIMPA[1]).write_text(
        'barra.set_title("Hefesto — DualSense4Unix")\n', encoding="utf-8"
    )
    subprocess.run(["git", "add", "-A"], cwd=casa, check=True)
    mod = _carregar(casa)
    assert mod.a_grafia() == []          # a grafia está certa…
    achados = mod.o_dono()               # …e mesmo assim reprova
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
    """Rodar a cura numa árvore já curada não muda byte nenhum.

    É o que a costura precisa: reaplicar por cima de outras frentes sem refazer
    a medição. Sem isso, quem costura repete o trabalho do zero.
    """
    assert CURA.is_file(), f"{CURA} sumiu — a régua ficou sem cura a apontar"
    antes = subprocess.run(
        ["git", "status", "--porcelain"], cwd=RAIZ, capture_output=True, text=True
    ).stdout
    subprocess.run(["bash", str(CURA)], cwd=RAIZ, capture_output=True, text=True, check=True)
    depois = subprocess.run(
        ["git", "status", "--porcelain"], cwd=RAIZ, capture_output=True, text=True
    ).stdout
    assert antes == depois
