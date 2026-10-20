"""A-LISTA-DE-EXCLUSAO-TEM-UM-ESCRITOR-POR-VEZ-01 — as réguas."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import structlog
import yaml

from hefesto_dualsense4unix.integrations import cura_por_estrada as cpe
from hefesto_dualsense4unix.integrations import lista_de_exclusao as lx
from tests.unit.test_a_exclusao_mora_na_camada_do_jogo import (
    _JANELA,
    _PONTE,
    _flatpak,
    _lutris_flatpak,
)
from tests.unit.test_o_uninstall_nao_deixa_rastro import _SO_A_BIBLIOTECA_PADRAO, SISTEMA
from tests.unit import a_exclusao_de_antes as antiga


@pytest.fixture(autouse=True)
def _as_extensoes_de_caixa_ligadas(monkeypatch: pytest.MonkeyPatch) -> None:
    """O Lutris, o RetroArch, o Dolphin e o mGBA viraram extensão: aqui elas estão ligadas."""
    from tests.unit.as_caixas_das_extensoes import ligar

    ligar(monkeypatch)

SRC = Path(cpe.__file__).resolve().parents[2]
CURA = Path(cpe.__file__).resolve()
_MGBA = "io.mgba.mGBA"


@pytest.fixture(autouse=True)
def _lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    lar = tmp_path / "lar"
    lar.mkdir()
    monkeypatch.setenv("HOME", str(lar))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(lar / ".config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(lar / ".local" / "state"))
    monkeypatch.setenv("XDG_DATA_HOME", str(lar / ".local" / "share"))
    from hefesto_dualsense4unix.utils.xdg_paths import launch_env_dir

    amb = launch_env_dir(ensure=True)
    (amb / "default.env").write_text("".join(f"{k}={v}\n" for k, v in _PONTE.items()))
    return lar


def _ambiente(lar: Path) -> dict[str, str]:
    return {**os.environ, "HOME": str(lar), "XDG_CONFIG_HOME": str(lar / ".config"),
            "XDG_STATE_HOME": str(lar / ".local/state"),
            "XDG_DATA_HOME": str(lar / ".local/share"), "PYTHONPATH": str(SRC),
            "PYTHONDONTWRITEBYTECODE": "1"}


def _esperar_o_arquivo(alvo: Path, processo: subprocess.Popen[str], teto: float = 20.0) -> None:
    prazo = time.monotonic() + teto
    while not alvo.exists():
        assert processo.poll() is None, processo.communicate()
        assert time.monotonic() < prazo, f"o outro processo não chegou a {alvo.name}"
        time.sleep(0.01)


_O_SERVICO = """
import hashlib, sys
from pathlib import Path
from hefesto_dualsense4unix.integrations import cura_por_estrada as cpe
from hefesto_dualsense4unix.integrations import lista_de_exclusao as lx
casa, yml, pronto, fim = (Path(x) for x in sys.argv[1:5])
k = 0
while not fim.exists():
    k += 1
    depois = hashlib.sha256(str(k).encode()).hexdigest()
    status = lx.anotar_os_ymls([cpe.YmlDoJogo(str(yml), "x", depois)], config_home=casa)
    assert status == "feito", status
    pronto.touch()
print(hashlib.sha256(str(k).encode()).hexdigest())
"""


_O_OUTRO_ESCRITOR = """
import fcntl, json, os, sys, time
from pathlib import Path
trava, lista, pronto = (Path(x) for x in sys.argv[1:4])
trava.parent.mkdir(parents=True, exist_ok=True)
fd = os.open(trava, os.O_RDWR | os.O_CREAT, 0o600)
fcntl.flock(fd, fcntl.LOCK_EX)
pronto.touch()
time.sleep(0.4)
lista.write_text(json.dumps({"formato": 1, "jogos": [
    {"chave": "steam_app_2", "lancador": "heroic", "nome": "o do outro", "quando": ""}]}))
time.sleep(0.2)
os.close(fd)
"""


def test_tirar_a_caixa_chama_a_carona_e_a_anotacao_sem_esperar_a_si_mesmo(_lar: Path) -> None:
    """O «Tirar da lista» do mGBA: o `tirar` chama a carona, que cobre o `.yml`"""
    yml = _lutris_flatpak(_lar)
    _flatpak(_lar, _MGBA)
    assert antiga.adicionar(_JANELA, lancador="lutris", nome="Recettear", lar=_lar) == "adicionado"
    assert antiga.adicionar("emulador:mgba", lancador="mgba", nome="mGBA — todos os jogos",
                            janelas=(_MGBA,), lar=_lar) == "adicionado"
    caixa = _lar / ".local/share/flatpak/overrides" / _MGBA
    antes = time.monotonic()
    with structlog.testing.capture_logs() as diario:
        assert lx.tirar("emulador:mgba", lar=_lar) == "removido"
    gasto = time.monotonic() - antes
    assert not [x for x in diario if x.get("event") == "carona_esperou_a_janela"], diario
    assert "SDL_GAMECONTROLLER_IGNORE_DEVICES=" in (
        caixa.read_text() if caixa.exists() else ""), (
        "fora da lista, a caixa do mGBA não recebeu o ambiente: a carona esperou o "
        "próprio «Tirar»")
    texto = yml.read_text()
    assert yaml.safe_load(texto)["system"]["env"].get("SDL_GAMECONTROLLER_IGNORE_DEVICES") == ""
    anotado = next(e for e in lx.ler() if e.chave == _JANELA).lutris[0]
    assert anotado.depois == hashlib.sha256(texto.encode()).hexdigest(), (
        "a anotação do `.yml` não chegou à lista: o `anotar_os_ymls` esperou a trava "
        "que o próprio processo segurava")
    assert gasto < cpe.ESPERA_DA_JANELA_S, f"o «Tirar» levou {gasto:.1f} s"


def test_outro_fio_do_mesmo_processo_espera(_lar: Path) -> None:
    """A reentrância é do FIO: outro fio do mesmo processo espera como outro"""
    import threading

    dentro = threading.Event()
    sair = threading.Event()
    viu: list[bool] = []

    def segura() -> None:
        with cpe.trava_da_lista() as na_mao:
            assert na_mao
            dentro.set()
            sair.wait(10)

    fio = threading.Thread(target=segura)
    fio.start()
    try:
        assert dentro.wait(10)
        with cpe.trava_da_lista(espera=0.2) as na_mao:
            viu.append(na_mao)
    finally:
        sair.set()
        fio.join(10)
    assert viu == [False], "outro fio entrou com a trava do primeiro na mão"
    with cpe.trava_da_lista(espera=0.2) as na_mao:
        assert na_mao, "a trava não se soltou quando o de fora saiu"


_SEGURA_A_TRAVA = """
import fcntl, os, sys, time
from pathlib import Path
trava, pronto, fim = (Path(x) for x in sys.argv[1:4])
trava.parent.mkdir(parents=True, exist_ok=True)
fd = os.open(trava, os.O_RDWR | os.O_CREAT, 0o600)
fcntl.flock(fd, fcntl.LOCK_EX)
pronto.touch()
prazo = time.monotonic() + 30
while not fim.exists() and time.monotonic() < prazo:
    time.sleep(0.01)
"""


@pytest.fixture
def _a_janela_segura(tmp_path: Path, _lar: Path) -> Iterator[subprocess.Popen[str]]:
    """Outro processo (a janela) com a trava na mão até o teste terminar."""
    pronto, fim = tmp_path / "pronto", tmp_path / "fim"
    janela = subprocess.Popen(
        [sys.executable, "-c", _SEGURA_A_TRAVA,
         str(lx.caminho().parent / cpe.NOME_DA_TRAVA), str(pronto), str(fim)],
        env=_ambiente(_lar), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        _esperar_o_arquivo(pronto, janela)
        yield janela
    finally:
        fim.touch()
        janela.communicate(timeout=30)


def test_a_carona_do_servico_nao_espera_a_janela(
        _lar: Path, _a_janela_segura: subprocess.Popen[str]) -> None:
    """Com a trava na janela, a carona volta em até 1 s, sem escrever, e diz."""
    _flatpak(_lar, _MGBA)
    caixa = _lar / ".local/share/flatpak/overrides" / _MGBA
    antes = time.monotonic()
    with structlog.testing.capture_logs() as diario:
        escritos = cpe.curar_todas_as_estradas(lar=_lar, raiz_sistema=_lar.parent / "sistema")
    gasto = time.monotonic() - antes
    assert escritos == ()
    assert escritos.sem_a_trava, "a carona não disse que a trava não veio"
    assert not caixa.exists(), "a carona escreveu sem a trava"
    assert gasto < cpe.ESPERA_DO_SERVICO_S + 1.0, f"a carona esperou {gasto:.1f} s"
    esperou = [x for x in diario if x.get("event") == "carona_esperou_a_janela"]
    assert esperou, diario
    assert esperou[0].get("quem") == cpe.QUEM_SERVICO, esperou


_RETOMA_A_TRAVA = """
import fcntl, os, sys, time
from pathlib import Path
trava, pronto, fim = (Path(x) for x in sys.argv[1:4])
trava.parent.mkdir(parents=True, exist_ok=True)
prazo = time.monotonic() + 60
while not fim.exists() and time.monotonic() < prazo:
    fd = os.open(trava, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    pronto.touch()
    time.sleep(0.002)
    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)
"""


def test_quem_espera_nao_perde_para_quem_retoma(tmp_path: Path, _lar: Path) -> None:
    """Outro processo retoma a trava logo depois de soltá-la: quem espera pega"""
    pronto, fim = tmp_path / "pronto", tmp_path / "fim"
    outro = subprocess.Popen(
        [sys.executable, "-c", _RETOMA_A_TRAVA, str(lx.caminho().parent / cpe.NOME_DA_TRAVA),
         str(pronto), str(fim)], env=_ambiente(_lar), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    gastos: list[float] = []
    try:
        _esperar_o_arquivo(pronto, outro)
        for _ in range(5):
            antes = time.monotonic()
            with cpe.trava_da_lista(espera=2.0) as na_mao:
                gastos.append(time.monotonic() - antes)
                assert na_mao, (
                    f"quem espera perdeu a trava para quem a retoma (esperas: {gastos})")
    finally:
        fim.touch()
        outro.communicate(timeout=30)
    assert max(gastos) < 1.0, f"a espera passou de 1 s: {gastos}"


def test_quem_desistiu_nao_fica_com_a_trava(tmp_path: Path, _lar: Path) -> None:
    """Quem desistiu no prazo deixa a espera na fila; quando o outro solta, a"""
    pronto, fim = tmp_path / "pronto", tmp_path / "fim"
    janela = subprocess.Popen(
        [sys.executable, "-c", _SEGURA_A_TRAVA,
         str(lx.caminho().parent / cpe.NOME_DA_TRAVA), str(pronto), str(fim)],
        env=_ambiente(_lar), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        _esperar_o_arquivo(pronto, janela)
        with cpe.trava_da_lista(espera=0.3) as na_mao:
            assert not na_mao
    finally:
        fim.touch()
        janela.communicate(timeout=30)
    with cpe.trava_da_lista(espera=2.0) as na_mao:
        assert na_mao, "a espera que desistiu ficou com a trava"


def test_o_desfazer_pelo_python_do_sistema_espera_a_trava(tmp_path: Path, _lar: Path) -> None:
    """O desfazer roda com o `python3` do sistema e só a biblioteca padrão; com"""
    py = shutil.which("python3", path=SISTEMA)
    if py is None:
        pytest.skip("sem python3 no sistema")
    casa = _lar / ".config/heroic"
    casa.mkdir(parents=True)
    (casa / "config.json").write_text(json.dumps({"defaultSettings": {}}))
    cpe.curar_todas_as_estradas(lar=_lar, raiz_sistema=_lar.parent / "sistema")
    assert "SDL_GAMECONTROLLER_IGNORE_DEVICES" in (casa / "config.json").read_text()
    recusa = tmp_path / "so_a_biblioteca_padrao.py"
    recusa.write_text(_SO_A_BIBLIOTECA_PADRAO, encoding="utf-8")
    from hefesto_dualsense4unix.utils.xdg_paths import launch_env_dir

    with cpe.trava_da_lista():
        desfazer = subprocess.Popen(
            [py, "-I", str(recusa), str(CURA), "--desfazer", "--lar", str(_lar),
             "--pasta-do-ambiente", str(launch_env_dir()),
             "--lista-de-exclusao", str(lx.caminho())],
            env={"HOME": str(_lar), "XDG_CONFIG_HOME": str(_lar / ".config"),
                 "PATH": SISTEMA, "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"},
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(tmp_path))
        prazo = time.monotonic() + 2.0
        mexeu = False
        while time.monotonic() < prazo and not mexeu and desfazer.poll() is None:
            time.sleep(0.05)
            mexeu = "SDL_GAMECONTROLLER_IGNORE_DEVICES" not in (casa / "config.json").read_text()
        esperava = desfazer.poll() is None
    saida, erro = desfazer.communicate(timeout=60)
    assert desfazer.returncode == 0, saida + erro
    assert esperava and not mexeu, (
        f"o desfazer não esperou a trava (terminou={not esperava}, escreveu={mexeu}):\n"
        + saida + erro)
    assert "SDL_GAMECONTROLLER_IGNORE_DEVICES" not in (casa / "config.json").read_text()
