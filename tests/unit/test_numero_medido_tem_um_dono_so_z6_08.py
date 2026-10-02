"""Z6-08 — o número medido tem um dono só."""
from __future__ import annotations

import csv
import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

RAIZ_REAL = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ_REAL / "scripts" / "validar-fala-de-tela.py"
FALA_DO_MAPA_REAL = RAIZ_REAL / "src" / "hefesto_dualsense4unix" / "app" / "fala_do_mapa.py"

RADIO_DA_MESA_MENTIROSA = '''\
"""radio_da_mesa.py de MENTIRA — só para teste."""
from __future__ import annotations

from hefesto_dualsense4unix.app.fala_do_mapa import Numero

HZ_INPUT_SEM_MIC = {sem_mic}
HZ_INPUT_COM_MIC = 170.5
HZ_AUDIO_COM_MIC = 106.2

NUMEROS_MEDIDOS_NO_MAPA: tuple[Numero, ...] = (
    Numero(constante="HZ_INPUT_SEM_MIC", valor=HZ_INPUT_SEM_MIC,
           chave="audio.microfone@dualsense", coluna="radio_ressalva"),
    Numero(constante="HZ_INPUT_COM_MIC", valor=HZ_INPUT_COM_MIC,
           chave="audio.microfone@dualsense", coluna="radio_ressalva"),
    Numero(constante="HZ_AUDIO_COM_MIC", valor=HZ_AUDIO_COM_MIC,
           chave="audio.microfone@dualsense", coluna="radio_ressalva"),
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


def _portao() -> Any:
    """O `validar-fala-de-tela.py`, carregado pelo caminho (o nome tem hífen)."""
    spec = importlib.util.spec_from_file_location("portao_da_fala_z6_08", SCRIPT)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["portao_da_fala_z6_08"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _so_o_radio(tmp_path: Path, fonte: str) -> Path:
    integracoes = tmp_path / "src" / "hefesto_dualsense4unix" / "integrations"
    integracoes.mkdir(parents=True, exist_ok=True)
    (integracoes / "radio_da_mesa.py").write_text(fonte, encoding="utf-8")
    return tmp_path


def test_a_forma_do_produto_da_os_tres_numeros(tmp_path: Path) -> None:
    raiz = _so_o_radio(tmp_path, RADIO_DA_MESA_MENTIROSA.format(sem_mic=260.4))
    achados = _portao().descobre_numeros(raiz)
    assert [(n.constante, n.valor, n.chave, n.coluna) for n in achados] == [
        ("HZ_INPUT_SEM_MIC", 260.4, "audio.microfone@dualsense", "radio_ressalva"),
        ("HZ_INPUT_COM_MIC", 170.5, "audio.microfone@dualsense", "radio_ressalva"),
        ("HZ_AUDIO_COM_MIC", 106.2, "audio.microfone@dualsense", "radio_ressalva"),
    ]


def test_a_tupla_crua_nao_conta_mais(tmp_path: Path) -> None:
    """A forma de antes some da régua, e no produto o piso de 3 reprova."""
    crua = (
        "HZ_INPUT_SEM_MIC = 260.4\n"
        "NUMEROS_MEDIDOS_NO_MAPA = (\n"
        '    ("HZ_INPUT_SEM_MIC", HZ_INPUT_SEM_MIC, "audio.microfone@dualsense",'
        ' "radio_ressalva"),\n'
        ")\n"
    )
    assert _portao().descobre_numeros(_so_o_radio(tmp_path, crua)) == []


def test_o_numero_por_posicao_tambem_conta(tmp_path: Path) -> None:
    fonte = (
        "HZ_INPUT_SEM_MIC = 260.4\n"
        "NUMEROS_MEDIDOS_NO_MAPA = (\n"
        '    Numero("HZ_INPUT_SEM_MIC", HZ_INPUT_SEM_MIC, "audio.microfone@dualsense",'
        ' coluna="radio_ressalva"),\n'
        ")\n"
    )
    achados = _portao().descobre_numeros(_so_o_radio(tmp_path, fonte))
    assert [(n.constante, n.valor, n.coluna) for n in achados] == [
        ("HZ_INPUT_SEM_MIC", 260.4, "radio_ressalva")]


def test_o_numero_sem_um_campo_nao_conta(tmp_path: Path) -> None:
    """O construtor recusaria o mesmo item ao importar: a régua não o conta."""
    fonte = (
        "HZ_INPUT_SEM_MIC = 260.4\n"
        "NUMEROS_MEDIDOS_NO_MAPA = (\n"
        '    Numero(constante="HZ_INPUT_SEM_MIC", valor=HZ_INPUT_SEM_MIC,'
        ' chave="audio.microfone@dualsense"),\n'
        '    Numero(constante="HZ_INPUT_SEM_MIC", valor=HZ_INPUT_SEM_MIC,'
        ' chave="a@b", coluna="c", sobra=1),\n'
        ")\n"
    )
    assert _portao().descobre_numeros(_so_o_radio(tmp_path, fonte)) == []


def test_o_produto_publica_numero_e_o_construtor_roda() -> None:
    """O fio: o `Numero` tem chamador de produção, e é a tupla do rádio."""
    from hefesto_dualsense4unix.app.fala_do_mapa import Numero
    from hefesto_dualsense4unix.integrations import radio_da_mesa

    tupla = radio_da_mesa.NUMEROS_MEDIDOS_NO_MAPA
    assert tupla and all(isinstance(n, Numero) for n in tupla), tupla
    assert {n.constante for n in tupla} == {
        "HZ_INPUT_SEM_MIC", "HZ_INPUT_COM_MIC", "HZ_AUDIO_COM_MIC"}
    for n in tupla:
        assert n.valor == getattr(radio_da_mesa, n.constante), n
    achados = _portao().descobre_numeros(RAIZ_REAL)
    assert len(achados) == len(tupla), achados
