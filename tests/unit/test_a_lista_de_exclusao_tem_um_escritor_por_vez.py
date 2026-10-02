"""A-LISTA-DE-EXCLUSAO-TEM-UM-ESCRITOR-POR-VEZ-01 — as réguas.

A lista de exclusão tem dois processos que leem, juntam e regravam: a janela
(«Excluir», «Tirar da lista», «Aplicar soluções nos lançadores») e o serviço
(a carona de cada transição, que anota os `.yml` do Lutris). Medido em
02/10/2026 num lar de mentira, com 300 «Excluir» seguidos e a anotação em laço
noutro processo: 147, 222 e 149 das 300 exclusões sumiram do arquivo.

A trava é um `flock` ao lado da lista, e o dono é o `cura_por_estrada`
(o desfazer do uninstall roda aquele arquivo sozinho, com o `python3` do
sistema). As réguas usam PROCESSOS de verdade para o outro escritor: um dublê
no mesmo processo não mediria o `flock`, que é entre processos.

TUDO NUM LAR DE MENTIRA: o `HOME` e os `XDG_*` de cada teste.
"""

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


# ---------------------------------------------------------------------------
# 1 · A corrida do estudo, com a trava
# ---------------------------------------------------------------------------
#: O serviço: anota o `.yml` do jogo do Lutris em laço, como a carona sobre um
#: jogo excluído, até a janela terminar; diz a última anotação.
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


def test_dois_processos_nao_perdem_exclusao(tmp_path: Path) -> None:
    """A janela faz N «Excluir» enquanto o serviço anota o `.yml` noutro processo.

    MORDIDA: tire a trava do `anotar_os_ymls` (ou do `adicionar`) e exclusões
    somem do arquivo — reprova pela contagem.
    """
    n = 150
    casa = tmp_path / "casa"
    yml = casa / "g.yml"
    lx._gravar(lx.caminho(casa), [lx.Entrada(
        chave="umu-lutris", lancador="lutris", nome="o do Lutris", quando="",
        lutris=(cpe.YmlDoJogo(str(yml), "x", "0"),))])
    pronto, fim = tmp_path / "pronto", tmp_path / "fim"
    servico = subprocess.Popen(
        [sys.executable, "-c", _O_SERVICO, str(casa), str(yml), str(pronto), str(fim)],
        env=_ambiente(tmp_path / "lar"), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True)
    try:
        _esperar_o_arquivo(pronto, servico)
        for i in range(n):
            assert lx.adicionar(f"umu-{i}", lancador="heroic", nome=f"jogo {i}",
                                config_home=casa, lar=tmp_path / "lar") == "adicionado"
    finally:
        fim.touch()
        saida, erro = servico.communicate(timeout=60)
    assert servico.returncode == 0, erro
    final = lx.ler(casa)
    vivas = [e.chave for e in final if e.chave.startswith("umu-") and e.chave != "umu-lutris"]
    assert len(vivas) == n, (
        f"{n - len(vivas)} das {n} exclusões sumiram do arquivo: o serviço regravou a "
        "lista por cima da janela")
    lutris = next(e for e in final if e.chave == "umu-lutris")
    assert lutris.lutris[0].depois == saida.strip(), (
        "a última anotação do `.yml` sumiu: a janela regravou a lista por cima do serviço")


# ---------------------------------------------------------------------------
# 2 · A lista se lê com a trava na mão
# ---------------------------------------------------------------------------
#: O dublê que segura a trava: pega o `flock` do arquivo do dono, escreve uma
#: exclusão na lista enquanto a segura, e só então solta.
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


def test_o_adicionar_le_a_lista_depois_de_pegar_a_trava(tmp_path: Path, _lar: Path) -> None:
    """Outro processo segura a trava e escreve na lista: o «Excluir» espera e
    junta o seu ao dele.

    MORDIDA: ler a lista antes de pegar a trava (a leitura de `:483` fora do
    `with`) — a exclusão do outro some.
    """
    destino = lx.caminho()
    lx._gravar(destino, [])
    pronto = tmp_path / "pronto"
    outro = subprocess.Popen(
        [sys.executable, "-c", _O_OUTRO_ESCRITOR, str(destino.parent / cpe.NOME_DA_TRAVA),
         str(destino), str(pronto)], env=_ambiente(_lar), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        _esperar_o_arquivo(pronto, outro)
        assert lx.adicionar("steam_app_1", lancador="heroic", nome="o meu",
                            lar=_lar) == "adicionado"
    finally:
        outro.communicate(timeout=30)
    assert {e.chave for e in lx.ler()} == {"steam_app_1", "steam_app_2"}, (
        "a exclusão do outro escritor sumiu: o «Excluir» leu a lista antes da trava")


# ---------------------------------------------------------------------------
# 3 · A trava é reentrante no mesmo processo
# ---------------------------------------------------------------------------
def test_tirar_a_caixa_chama_a_carona_e_a_anotacao_sem_esperar_a_si_mesmo(_lar: Path) -> None:
    """O «Tirar da lista» do mGBA: o `tirar` chama a carona, que cobre o `.yml`
    do jogo excluído do Lutris e chama o `anotar_os_ymls` — tudo com a trava
    na mão, num processo só.

    MORDIDA: um `flock` novo a cada tomada — a carona espera o próprio `tirar`
    e desiste, e a caixa do mGBA fica sem o ambiente; a anotação espera 5 s e
    volta «erro».
    """
    yml = _lutris_flatpak(_lar)
    _flatpak(_lar, _MGBA)
    assert lx.adicionar(_JANELA, lancador="lutris", nome="Recettear", lar=_lar) == "adicionado"
    assert lx.adicionar("emulador:mgba", lancador="mgba", nome="mGBA — todos os jogos",
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
    """A reentrância é do FIO: outro fio do mesmo processo espera como outro
    processo esperaria.

    MORDIDA: um contador só do processo, sem o `RLock` — o segundo fio entra
    com a trava do primeiro na mão.
    """
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


# ---------------------------------------------------------------------------
# 4 · O serviço não espera a janela além de 1 s
# ---------------------------------------------------------------------------
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
    """Com a trava na janela, a carona volta em até 1 s, sem escrever, e diz.

    MORDIDA: a espera sem teto (`espera=None` virando um `flock` bloqueante) —
    a régua estoura o prazo.
    """
    _flatpak(_lar, _MGBA)
    caixa = _lar / ".local/share/flatpak/overrides" / _MGBA
    antes = time.monotonic()
    with structlog.testing.capture_logs() as diario:
        escritos = cpe.curar_todas_as_estradas(lar=_lar, raiz_sistema=_lar.parent / "sistema")
    gasto = time.monotonic() - antes
    assert escritos == ()
    assert not caixa.exists(), "a carona escreveu sem a trava"
    assert gasto < cpe.ESPERA_DO_SERVICO_S + 1.0, f"a carona esperou {gasto:.1f} s"
    assert [x for x in diario if x.get("event") == "carona_esperou_a_janela"], diario


#: O escritor que retoma a trava logo depois de soltá-la (a carona em
#: sequência, a anotação em laço): segura 2 ms, solta, reabre e pede de novo.
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
    """Outro processo retoma a trava logo depois de soltá-la: quem espera pega
    a trava na vez seguinte, e não no fim do prazo.

    MORDIDA: a espera de antes, que perguntava ao `flock` a cada 20 ms (o
    `LOCK_NB` em laço no lugar de `_esperar_na_fila`) — medido em 02/10/2026,
    9 de 10 esperas passavam de 2 s, e o «Excluir» voltava «erro».
    """
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
    """Quem desistiu no prazo deixa a espera na fila; quando o outro solta, a
    trava pega e se solta sozinha, e o próximo pedido deste processo entra.

    MORDIDA: o fio que desistiu não solta (`_soltar` fora do `desistiu`) — a
    trava fica presa num descritor que ninguém mais conhece, e todo pedido
    seguinte deste processo espera até o prazo.
    """
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


def test_sem_a_trava_no_prazo_o_excluir_nao_escreve(
        _lar: Path, _a_janela_segura: subprocess.Popen[str],
        monkeypatch: pytest.MonkeyPatch) -> None:
    """O outro lado: sem a trava no prazo da janela, o «Excluir» volta «erro»
    sem escrever nada (nunca um jogo meio excluído)."""
    monkeypatch.setattr(cpe, "ESPERA_DA_JANELA_S", 0.3)
    assert lx.adicionar("steam_app_9", lancador="heroic", nome="o nove", lar=_lar) == "erro"
    assert not lx.caminho().exists()


# ---------------------------------------------------------------------------
# 5 · O desfazer do uninstall espera como a janela, só com a biblioteca padrão
# ---------------------------------------------------------------------------
def test_o_desfazer_pelo_python_do_sistema_espera_a_trava(tmp_path: Path, _lar: Path) -> None:
    """O desfazer roda com o `python3` do sistema e só a biblioteca padrão; com
    a trava na mão de outro, ele espera, e termina quando ela se solta.

    MORDIDA: um import de fora da biblioteca padrão no caminho da trava (um
    `import yaml` no `trava_da_lista`) — o desfazer cai e não diz o que fez.
    E: o desfazer sem a trava (`desfazer_as_estradas` indo direto ao
    `_desfazer_na_trava`) — ele escreve com a trava na mão de outro.
    """
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
        # Dois segundos (o prazo do desfazer é o da janela, 5 s): sem a trava,
        # o desfazer escreveria bem antes disso, e o `python3` que demora a
        # nascer numa máquina carregada não passa por «esperou».
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
