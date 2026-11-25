"""Z6-04 — o portão `validar-fala-de-tela.py` mede o número de tela, ou sai."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

RAIZ_REAL = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ_REAL / "scripts" / "validar-fala-de-tela.py"
FALA_DO_MAPA_REAL = RAIZ_REAL / "src" / "hefesto_dualsense4unix" / "app" / "fala_do_mapa.py"
RADIO_REAL = RAIZ_REAL / "src" / "hefesto_dualsense4unix" / "integrations" / "radio_da_mesa.py"
MAPA_REAL = RAIZ_REAL / "docs" / "data" / "mapa-controles.csv"

_UM_DOS_TRES = (
    '    Numero(constante="HZ_AUDIO_COM_MIC", valor=HZ_AUDIO_COM_MIC,\n'
    '           chave="audio.microfone@dualsense", coluna="radio_ressalva"),\n'
)


def monta_produto(tmp_path: Path, *, radio: str | None = None) -> Path:
    """O produto com a pasta da tela e os três arquivos REAIS que o portão lê."""
    pacote = tmp_path / "src" / "hefesto_dualsense4unix"
    for pasta in ("app", "interface", "integrations"):
        (pacote / pasta).mkdir(parents=True)
    shutil.copy(FALA_DO_MAPA_REAL, pacote / "app" / "fala_do_mapa.py")
    (pacote / "integrations" / "radio_da_mesa.py").write_text(
        radio if radio is not None else RADIO_REAL.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / "docs" / "data").mkdir(parents=True)
    shutil.copy(MAPA_REAL, tmp_path / "docs" / "data" / "mapa-controles.csv")
    return tmp_path


def rodar(raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--raiz", str(raiz), "--all"],
        capture_output=True,
        text=True,
        check=False,
    )


def test_o_produto_passa_e_diz_o_que_mediu(tmp_path: Path) -> None:
    processo = rodar(monta_produto(tmp_path))
    assert processo.returncode == 0, processo.stdout
    ultima = processo.stdout.strip().splitlines()[-1]
    assert ultima.startswith("OK: 3 número(s) de tela"), ultima
    assert "QUASE NÃO MEDIU" not in processo.stdout, processo.stdout
    assert ultima.endswith("Piso: numeros≥3."), ultima


def test_apagar_um_numero_de_tela_reprova_pelo_piso(tmp_path: Path) -> None:
    """D-2511-A-REGUA-DA-FALA-DE-TELA-SO-MEDE-O-QUE-A-TELA-MOSTRA — dois números: `rc=1`."""
    fonte = RADIO_REAL.read_text(encoding="utf-8")
    assert fonte.count(_UM_DOS_TRES) == 1, (
        "o terceiro `Numero` mudou de forma em `radio_da_mesa.py`: sem a linha esta mordida "
        "rodaria sem apagar nada e passaria sempre"
    )
    raiz = monta_produto(tmp_path, radio=fonte.replace(_UM_DOS_TRES, ""))
    processo = rodar(raiz)
    assert processo.returncode == 1, processo.stdout
    assert "numeros: a régua mede 2 e o piso é 3" in processo.stdout, processo.stdout


def test_o_registro_nao_tem_dependencia_pesada() -> None:
    """`import gi`/`Gtk` em `fala_do_mapa.py` faria este portão sair com ImportError."""
    fonte = FALA_DO_MAPA_REAL.read_text(encoding="utf-8")
    for termo in ("import gi", "from gi", "Gtk", "gi.repository"):
        assert termo not in fonte, f"{termo!r} em fala_do_mapa.py — dependência pesada"


def test_o_piso_so_conta_o_que_a_regua_le(tmp_path: Path) -> None:
    """D-2511-A-REGUA-DA-FALA-DE-TELA-SO-MEDE-O-QUE-A-TELA-MOSTRA — o piso é só dos números.

    Uma chave do piso que conta uma constante do próprio roteiro (as raízes de tela, que nada
    varre desde que a `Fala` saiu) daria verde sobre régua nenhuma.
    """
    processo = rodar(monta_produto(tmp_path))
    assert processo.returncode == 0, processo.stdout
    assert "raiz" not in processo.stdout, processo.stdout


def test_arvore_sem_a_tela_nao_e_o_produto(tmp_path: Path) -> None:
    """O piso vale para o produto, e a árvore sem a pasta da tela diz que não o aplicou."""
    raiz = monta_produto(tmp_path)
    (raiz / "src" / "hefesto_dualsense4unix" / "interface").rmdir()
    processo = rodar(raiz)
    assert processo.returncode == 0, processo.stdout
    assert "PISO NÃO APLICADO" in processo.stdout, processo.stdout


def test_o_produto_de_verdade_aplica_o_piso() -> None:
    """Na árvore real o piso vale: o portão nunca fica verde com o piso desligado."""
    processo = subprocess.run(
        [sys.executable, str(SCRIPT), "--all"], cwd=RAIZ_REAL,
        capture_output=True, text=True, check=False,
    )
    assert processo.returncode == 0, processo.stdout + processo.stderr
    assert "PISO NÃO APLICADO" not in processo.stdout, processo.stdout
