"""O backend montado sem leitor não procura nem abre nó em /dev/input nem em /dev/hidraw.

`PyDualSenseController()` sem leitor monta um `EvdevReader()`, e o construtor dele procurava o
controle: percorria `/dev/input` e abria cada nó de gamepad que o sysfs não classificava. Na
suíte, eram 21 nós reais da máquina abertos por backend montado. A procura é do
`refresh_device()`, que o backend chama ao conectar; montar não toca aparelho nenhum.

A régua conta, por um gancho de auditoria num processo filho, toda abertura e toda listagem sob
`/dev/input` e `/dev/hidraw`: na montagem pura e numa amostra dos testes que montam o backend.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from hefesto_dualsense4unix.core import evdev_reader as er
from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

RAIZ = Path(__file__).resolve().parents[2]

_GANCHO = '''
import json
import os
import sys

_TOQUES = []
_DONO = ["(montagem)"]
_EVENTOS = ("open", "os.scandir", "os.listdir", "glob.glob")


def _gancho(evento, args):
    if evento not in _EVENTOS or not args:
        return
    try:
        caminho = os.fsdecode(args[0])
    except Exception:
        return
    if caminho.startswith(("/dev/input", "/dev/hidraw")):
        _TOQUES.append([_DONO[0], evento, caminho])


sys.addaudithook(_gancho)


def pytest_runtest_setup(item):
    _DONO[0] = item.nodeid


def pytest_sessionfinish(session, exitstatus):
    with open(os.environ["TOQUES_SAIDA"], "w", encoding="utf-8") as saida:
        json.dump(_TOQUES, saida)
'''

_MONTAGEM = '''
import gancho_dos_nos as g
from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

for _ in range(3):
    backend = PyDualSenseController()
    backend.read_state()
    backend.disconnect()
g.pytest_sessionfinish(None, 0)
'''

_AMOSTRA = (
    "tests/unit/test_backend_keepalive_neutro.py",
    "tests/unit/test_led_set_broadcast.py",
)


def _ambiente(tmp_path: Path) -> tuple[dict[str, str], Path]:
    (tmp_path / "gancho_dos_nos.py").write_text(_GANCHO, encoding="utf-8")
    saida = tmp_path / "toques.json"
    ambiente = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    ambiente["PYTHONPATH"] = os.pathsep.join([str(tmp_path), str(RAIZ / "src"), str(RAIZ)])
    ambiente["TOQUES_SAIDA"] = str(saida)
    return ambiente, saida


def _toques(saida: Path, texto: str) -> list[list[str]]:
    assert saida.exists(), f"o gancho não escreveu os toques:\n{texto[-1500:]}"
    toques: list[list[str]] = json.loads(saida.read_text(encoding="utf-8"))
    return toques


def test_montar_o_backend_sem_leitor_nao_toca_dev_input(tmp_path: Path) -> None:
    ambiente, saida = _ambiente(tmp_path)
    r = subprocess.run(
        [sys.executable, "-c", _MONTAGEM],
        capture_output=True, text=True, cwd=tmp_path, env=ambiente, timeout=120,
    )
    texto = r.stdout + r.stderr
    assert r.returncode == 0, texto[-1500:]
    toques = _toques(saida, texto)
    assert not toques, f"montar o backend tocou nós da máquina: {toques[:10]}"


def test_a_amostra_que_monta_o_backend_nao_toca_dev_input(tmp_path: Path) -> None:
    ambiente, saida = _ambiente(tmp_path)
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         "-p", "gancho_dos_nos", *_AMOSTRA],
        capture_output=True, text=True, cwd=RAIZ, env=ambiente, timeout=600,
    )
    texto = r.stdout + r.stderr
    verde = re.search(r"\d+ passed", texto) and not re.search(r"\d+ (failed|error)", texto)
    assert verde, texto[-1500:]
    toques = _toques(saida, texto)
    por_arquivo: dict[str, int] = {}
    for dono, _evento, _caminho in toques:
        arquivo = dono.split("::", 1)[0]
        por_arquivo[arquivo] = por_arquivo.get(arquivo, 0) + 1
    assert not por_arquivo, f"testes que tocaram nós da máquina: {por_arquivo}"


def test_montar_nao_procura_mesmo_sem_dev_input_na_maquina(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    procuras: list[str] = []

    def _anota(nome: str) -> Callable[..., None]:
        def _procura(*_a: object, **_k: object) -> None:
            procuras.append(nome)
            return None
        return _procura

    for nome in ("find_dualsense_evdev", "localizar_node_por_identidade", "discover_gamepads"):
        monkeypatch.setattr(er, nome, _anota(nome))
    backend = PyDualSenseController()
    try:
        assert procuras == [], f"montar o backend procurou o controle: {procuras}"
        assert not backend._evdev.is_available()
    finally:
        backend.disconnect()


def test_o_leitor_procura_quando_o_backend_conecta(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    no = tmp_path / "event7"
    alvos: list[str | None] = []

    def _localiza(identidade: str) -> Path:
        alvos.append(identidade)
        return no

    monkeypatch.setattr(er, "find_dualsense_evdev", lambda: no)
    monkeypatch.setattr(er, "localizar_node_por_identidade", _localiza)
    leitor = er.EvdevReader()
    reaberturas: list[str] = []
    monkeypatch.setattr(leitor, "request_reopen", lambda reason="": reaberturas.append(reason))
    try:
        assert not leitor.is_available()
        leitor.retarget("02:fe:00:00:00:07")
        assert leitor.refresh_device()
        assert leitor._device_path == no
        assert alvos == ["02fe00000007"]
        assert reaberturas == [], "o leitor sem nó aberto não tem o que reabrir"
    finally:
        leitor.stop()
