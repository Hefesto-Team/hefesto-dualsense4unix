"""Os testes fecham os descritores que abrem, e a suíte num processo só não passa de 1024.

O build da release rodava `pytest tests/unit` num processo só, e 42 testes caíram com
`ValueError: filedescriptor out of range in select()`. A origem era o self-pipe dos leitores,
aberto no construtor: cada leitor construído e nunca iniciado prendia dois descritores até o
fim do processo. A régua conta, num processo filho, os descritores que cada teste abre e que
ainda estão abertos no fim da sessão; um arquivo em que dois testes deixam sobra vaza.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.evdev_reader import (
    EvdevReader,
    MotionSensorReader,
    TouchpadReader,
)
from hefesto_dualsense4unix.core.physical_report_reader import PhysicalReportReader

RAIZ = Path(__file__).resolve().parents[2]

_CONTADOR = '''
import gc
import json
import os

import pytest

_NOVOS: dict = {}


def _abertos():
    vistos = {}
    for nome in os.listdir("/proc/self/fd"):
        try:
            vistos[int(nome)] = os.readlink(f"/proc/self/fd/{nome}")
        except OSError:
            pass
    return vistos


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    antes = _abertos()
    yield
    depois = _abertos()
    _NOVOS[item.nodeid] = {fd: alvo for fd, alvo in depois.items() if antes.get(fd) != alvo}


def pytest_sessionfinish(session, exitstatus):
    gc.collect()
    agora = _abertos()
    sobra = {}
    for nodeid, novos in _NOVOS.items():
        presos = sorted(alvo for fd, alvo in novos.items() if agora.get(fd) == alvo)
        if presos:
            sobra[nodeid] = presos
    with open(os.environ["CONTAR_DESCRITORES_SAIDA"], "w", encoding="utf-8") as saida:
        json.dump(sobra, saida)
'''

_VAZA = '''
import os


def test_um():
    os.pipe()


def test_dois():
    os.pipe()


def test_fecha():
    r, w = os.pipe()
    os.close(r)
    os.close(w)
'''

_OS_QUE_VAZAVAM = (
    "tests/unit/test_a_barra_nao_escurece_ao_reaplicar.py",
    "tests/unit/test_a_marca_da_cor_nao_some.py",
    "tests/unit/test_backend_multi_controller.py",
)

_SEM_TETO = ("tests", "scripts/ensaios/cor_do_plastico.py")

_PROVA_DO_TETO = "tests/unit/test_a_espera_passa_do_descritor_1023.py"


def _sobra_por_arquivo(tmp_path: Path, alvos: list[str], *, cwd: Path) -> dict[str, list[str]]:
    (tmp_path / "contar_descritores.py").write_text(_CONTADOR, encoding="utf-8")
    saida = tmp_path / "sobra.json"
    ambiente = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    ambiente["PYTHONPATH"] = os.pathsep.join([str(tmp_path), str(RAIZ / "src"), str(RAIZ)])
    ambiente["CONTAR_DESCRITORES_SAIDA"] = str(saida)
    r = subprocess.run(
        [
            sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
            "-p", "contar_descritores", *alvos,
        ],
        capture_output=True, text=True, cwd=cwd, env=ambiente, timeout=600,
    )
    texto = r.stdout + r.stderr
    assert saida.exists(), f"o contador não escreveu a sobra:\n{texto[-1500:]}"
    verde = re.search(r"\d+ passed", texto) and not re.search(r"\d+ (failed|error)", texto)
    assert verde, texto[-1500:]
    por_arquivo: dict[str, list[str]] = {}
    for nodeid in json.loads(saida.read_text(encoding="utf-8")):
        por_arquivo.setdefault(nodeid.split("::", 1)[0], []).append(nodeid)
    return por_arquivo


def _vazam(por_arquivo: dict[str, list[str]]) -> dict[str, list[str]]:
    return {arquivo: testes for arquivo, testes in por_arquivo.items() if len(testes) >= 2}


def test_a_regua_reprova_o_pipe_plantado_sem_close(tmp_path: Path) -> None:
    quintal = tmp_path / "quintal"
    quintal.mkdir()
    (quintal / "test_planta.py").write_text(_VAZA, encoding="utf-8")
    vazam = _vazam(_sobra_por_arquivo(tmp_path, ["test_planta.py"], cwd=quintal))
    assert sorted(vazam.get("test_planta.py", [])) == [
        "test_planta.py::test_dois", "test_planta.py::test_um",
    ], vazam


def test_a_regua_nao_acusa_quem_fecha(tmp_path: Path) -> None:
    quintal = tmp_path / "quintal"
    quintal.mkdir()
    fecha = _VAZA.replace("    os.pipe()\n", "    list(map(os.close, os.pipe()))\n")
    (quintal / "test_planta.py").write_text(fecha, encoding="utf-8")
    assert _sobra_por_arquivo(tmp_path, ["test_planta.py"], cwd=quintal) == {}


def test_os_arquivos_que_vazavam_nao_deixam_sobra(tmp_path: Path) -> None:
    vazam = _vazam(_sobra_por_arquivo(tmp_path, list(_OS_QUE_VAZAVAM), cwd=RAIZ))
    assert not vazam, f"testes que deixam descritor aberto: {vazam}"


def _abertos() -> int:
    return len(os.listdir("/proc/self/fd"))


_LEITORES: dict[str, Callable[[Path], Any]] = {
    "evdev": lambda no: EvdevReader(device_path=no),
    "touchpad": lambda no: TouchpadReader(device_path=no),
    "movimento": lambda no: MotionSensorReader(device_path=no),
    "hidraw": lambda no: PhysicalReportReader(lambda: None, object()),
}


@pytest.mark.parametrize("leitor", sorted(_LEITORES))
def test_o_leitor_construido_sem_start_nao_prende_descritor(tmp_path: Path, leitor: str) -> None:
    fabrica = _LEITORES[leitor]
    antes = _abertos()
    vivos = [fabrica(tmp_path / f"event{i}") for i in range(40)]
    assert _abertos() == antes, f"40 leitores {leitor} sem start prendem descritor"
    for vivo in vivos:
        vivo.stop()
    assert _abertos() == antes


def test_nenhum_teste_espera_pelo_select_com_teto() -> None:
    achados = []
    for raiz in _SEM_TETO:
        caminho = RAIZ / raiz
        arquivos = sorted(caminho.rglob("*.py")) if caminho.is_dir() else [caminho]
        for arquivo in arquivos:
            relativo = arquivo.relative_to(RAIZ).as_posix()
            if relativo in (_PROVA_DO_TETO, Path(__file__).relative_to(RAIZ).as_posix()):
                continue
            texto = arquivo.read_text(encoding="utf-8", errors="replace")
            for numero, linha in enumerate(texto.splitlines(), 1):
                if re.search(r"\bselect\.select\(", linha):
                    achados.append(f"{relativo}:{numero}")
    assert not achados, f"`select.select` tem teto de 1024 descritores: {achados}"
