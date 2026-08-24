"""Z6-08 — o número medido tem um dono só.

A mordida da sprint (o segundo item do aceite): "Trocar `HZ_INPUT_SEM_MIC`
para outro valor **sem** atualizar a `radio_ressalva` → reprova nomeando a
constante, o arquivo, a linha do CSV e os dois valores. Arrancar a
comparação → o teste que a prova reprova."

Roda contra uma árvore de mentira (um `integrations/radio_da_mesa.py` e um
`mapa-controles.csv` sintéticos) — nunca a árvore real, para o teste não
precisar acompanhar o dia em que a bancada remedir os três números.
"""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

RAIZ_REAL = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ_REAL / "scripts" / "validar-fala-de-tela.py"
FALA_DO_MAPA_REAL = RAIZ_REAL / "src" / "hefesto_dualsense4unix" / "app" / "fala_do_mapa.py"

RADIO_DA_MESA_MENTIROSA = '''\
"""radio_da_mesa.py de MENTIRA — só para teste."""
from __future__ import annotations

HZ_INPUT_SEM_MIC = {sem_mic}
HZ_INPUT_COM_MIC = 170.5
HZ_AUDIO_COM_MIC = 106.2

NUMEROS_MEDIDOS_NO_MAPA: tuple[tuple[str, float, str, str], ...] = (
    ("HZ_INPUT_SEM_MIC", HZ_INPUT_SEM_MIC, "audio.microfone@dualsense", "radio_ressalva"),
    ("HZ_INPUT_COM_MIC", HZ_INPUT_COM_MIC, "audio.microfone@dualsense", "radio_ressalva"),
    ("HZ_AUDIO_COM_MIC", HZ_AUDIO_COM_MIC, "audio.microfone@dualsense", "radio_ressalva"),
)
'''

CABECALHO = ["id", "radio_ressalva"]


def monta_arvore(tmp_path: Path, sem_mic: float, ressalva: str) -> Path:
    app = tmp_path / "src" / "hefesto_dualsense4unix" / "app"
    integracoes = tmp_path / "src" / "hefesto_dualsense4unix" / "integrations"
    app.mkdir(parents=True, exist_ok=True)
    integracoes.mkdir(parents=True, exist_ok=True)
    (app / "fala_do_mapa.py").write_text(
        FALA_DO_MAPA_REAL.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (app / "fatos_do_mapa.py").write_text(
        '"""de mentira."""\nfrom __future__ import annotations\n'
        "from typing import Final\nFATOS: Final[dict] = {}\n",
        encoding="utf-8",
    )
    (integracoes / "radio_da_mesa.py").write_text(
        RADIO_DA_MESA_MENTIROSA.format(sem_mic=sem_mic), encoding="utf-8"
    )
    dados = tmp_path / "docs" / "data"
    dados.mkdir(parents=True, exist_ok=True)
    with (dados / "mapa-controles.csv").open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=CABECALHO)
        escritor.writeheader()
        escritor.writerow({"id": "audio.microfone@dualsense", "radio_ressalva": ressalva})
    return tmp_path


def rodar(raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--raiz", str(raiz), "--all"],
        capture_output=True,
        text=True,
        check=False,
    )


def test_constante_e_celula_batendo_passa(tmp_path: Path) -> None:
    raiz = monta_arvore(
        tmp_path,
        260.4,
        "mic desligado 260,4 Hz de input; ligado 170,5 Hz de input + 106,2 Hz de áudio",
    )
    processo = rodar(raiz)
    assert processo.returncode == 0, processo.stdout


def test_constante_trocada_sem_atualizar_celula_reprova(tmp_path: Path) -> None:
    """MORDIDA de Z6-08 — o segundo item do aceite."""
    raiz = monta_arvore(
        tmp_path,
        275.0,
        "mic desligado 260,4 Hz de input; ligado 170,5 Hz de input + 106,2 Hz de áudio",
    )
    processo = rodar(raiz)
    assert processo.returncode == 1
    assert "HZ_INPUT_SEM_MIC" in processo.stdout
    assert "radio_da_mesa.py" in processo.stdout
    assert "275" in processo.stdout
    assert "radio_ressalva" in processo.stdout
    assert "audio.microfone@dualsense" in processo.stdout


def test_celula_sem_nenhum_dos_tres_numeros_reprova(tmp_path: Path) -> None:
    raiz = monta_arvore(tmp_path, 260.4, "sem número nenhum aqui")
    processo = rodar(raiz)
    assert processo.returncode == 1
    assert "HZ_INPUT_SEM_MIC" in processo.stdout
