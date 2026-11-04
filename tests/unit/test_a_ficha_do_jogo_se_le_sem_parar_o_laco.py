"""A ficha do jogo se lê sem parar o laço (A-FICHA-DO-JOGO-SE-LE-SEM-PARAR-O-LACO-01).

Medido em 02/11/2026: o `mmap.find` de `_ler_o_arquivo` prende o GIL pelo arquivo inteiro, e o
laço do daemon parou de 11 a 16 s depois de cada install, com o cache da roupa zerado. A leitura
agora vai em blocos que soltam o GIL, e o cache sobrevive ao reinício em disco.
"""
from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import a_roupa_do_jogo as rj
from hefesto_dualsense4unix.integrations import ficha_declarada as fd

_GRANDE = 512 << 20
_TICK = 0.01
_TETO_DO_ATRASO = 0.05
_UMA_HORA_ATRAS = time.time_ns() - 3600 * 10**9
_METADATA = "Jogo_Data/il2cpp_data/Metadata/global-metadata.dat"


def _o_reinicio() -> None:
    """O daemon que reinicia (o install): toda memória dos dois caches some."""
    rj._CACHE.clear()
    rj._LIDO_EM.clear()
    rj._AQUECENDO.clear()
    fd._POR_ARQUIVO.clear()
    fd._LIDO_DO_DISCO.clear()


@pytest.fixture(autouse=True)
def _cache_limpo() -> Iterator[None]:
    _o_reinicio()
    yield
    _o_reinicio()


def _esparso(caminho: Path, agulha: bytes, onde: int, tamanho: int = _GRANDE) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("wb") as fh:
        fh.truncate(tamanho)
        fh.seek(onde)
        fh.write(agulha)
    return caminho


def _o_maior_atraso(ler: Callable[[], Any]) -> tuple[Any, float]:
    """O que `ler` devolve e o maior atraso de um fio que dorme `_TICK` durante a leitura."""
    parar = threading.Event()
    maior = [0.0]

    def _fio() -> None:
        while not parar.is_set():
            antes = time.perf_counter()
            time.sleep(_TICK)
            maior[0] = max(maior[0], time.perf_counter() - antes - _TICK)

    fio = threading.Thread(target=_fio, daemon=True)
    fio.start()
    time.sleep(5 * _TICK)
    maior[0] = 0.0
    try:
        resposta = ler()
    finally:
        parar.set()
        fio.join()
    return resposta, maior[0]


def test_o_fio_de_10_ms_nao_para_enquanto_o_executavel_se_le(tmp_path: Path) -> None:
    """MORDIDA: devolver o `mmap.find` inteiro por agulha prende o GIL por centenas de ms."""
    exe = _esparso(tmp_path / "Jogo.exe", b"libScePad\x4c\x05\xe6\x0c", _GRANDE // 2)

    (sony, pids), atraso = _o_maior_atraso(lambda: fd._ler_o_arquivo(exe))

    assert sony == {"libScePad", "scePad"} and pids == {"0ce6"}
    assert atraso < _TETO_DO_ATRASO, f"o fio parou {atraso * 1000:.0f} ms"


@pytest.mark.parametrize(
    ("nome", "agulha", "rewired", "esperado"),
    [
        ("SDL2.dll", b"DualSense Wireless Controller", False, (False, True)),
        ("incontrol.dll", b"\0PlayStation5EdgeUSBWindowsNativeProfile\0", False, (True, False)),
        ("sharedassets0.assets", b"Sony DualSense Edge\0", True, (True, False)),
    ],
)
def test_o_fio_de_10_ms_nao_para_enquanto_a_roupa_se_le(
    tmp_path: Path, nome: str, agulha: bytes, rewired: bool, esperado: tuple[bool, bool]
) -> None:
    arquivo = _esparso(tmp_path / nome, agulha, _GRANDE // 2)

    marcas, atraso = _o_maior_atraso(lambda: rj._sinais_do_arquivo(arquivo, rewired=rewired))

    assert marcas == esperado
    assert atraso < _TETO_DO_ATRASO, f"o fio parou {atraso * 1000:.0f} ms"


_EMENDA = fd._SOBRA + fd._BLOCO


@pytest.mark.parametrize("recuo", [1, 3, 5, 9])
def test_a_agulha_na_emenda_de_dois_blocos_e_achada(tmp_path: Path, recuo: int) -> None:
    """A agulha que começa `recuo` bytes antes do fim do primeiro bloco cruza o corte."""
    exe = _esparso(tmp_path / "Jogo.exe", b"WinDualSense", _EMENDA - recuo, 3 * fd._BLOCO)
    pid = _esparso(tmp_path / "Pid.exe", b"\x4c\x05\0\0\xf2\x0d", _EMENDA - recuo, 3 * fd._BLOCO)
    sdl = _esparso(tmp_path / "SDL3.dll", b"DualSense Edge", _EMENDA - recuo, 3 * fd._BLOCO)
    perfil = _esparso(
        tmp_path / "global-metadata.dat", b"\0DualSenseWindowsProfile\0",
        _EMENDA - recuo, 3 * fd._BLOCO,
    )

    assert fd._ler_o_arquivo(exe)[0] == {"WinDualSense"}
    assert fd._ler_o_arquivo(pid)[1] == {"0df2"}
    assert rj._sinais_do_arquivo(sdl, rewired=False) == (True, False)
    assert rj._sinais_do_arquivo(perfil, rewired=False) == (False, True)


def test_o_nome_que_acaba_na_emenda_ve_o_edge_do_outro_lado(tmp_path: Path) -> None:
    """`Sony DualSense` acaba no fim do bloco e o ` Edge` vem no seguinte: é o Edge, não o comum.

    MORDIDA: julgar o nome sem esperar a janela seguinte devolve o comum.
    """
    agulha = b"Sony DualSense"
    assets = _esparso(
        tmp_path / "sharedassets0.assets", agulha + b" Edge\0",
        _EMENDA - len(agulha), 3 * fd._BLOCO,
    )
    perfil = _esparso(
        tmp_path / "incontrol.dll", b"\0PlayStation5EdgeProfile\0",
        _EMENDA - len(b"\0PlayStation5"), 3 * fd._BLOCO,
    )

    assert rj._sinais_do_arquivo(assets, rewired=True) == (True, False)
    assert rj._sinais_do_arquivo(perfil, rewired=False) == (True, False)


def test_o_perfil_que_segue_depois_da_emenda_nao_se_julga_cortado(tmp_path: Path) -> None:
    """`…Profile` acaba no fim do bloco, mas o nome segue no seguinte e não termina em `Profile`.

    MORDIDA: julgar o nome que encosta no fim de uma janela que não é a última devolve o comum.
    """
    antes = b"\0DualSenseWindowsProfile"
    perfil = _esparso(
        tmp_path / "global-metadata.dat", antes + b"Ajudante\0",
        _EMENDA - len(antes), 3 * fd._BLOCO,
    )

    assert rj._sinais_do_arquivo(perfil, rewired=False) == (False, False)


@pytest.mark.parametrize("recuo", [1, 3, 4, 5])
def test_o_hori_cortado_no_comeco_da_janela_nao_vira_o_comum(tmp_path: Path, recuo: int) -> None:
    """O `Hori…Profile` que atravessa o começo da segunda janela segue fora, como inteiro.

    MORDIDA: julgar o nome que encosta no começo de uma janela que não é a primeira devolve o comum,
    porque o corte come o `Hori` do começo.
    """
    perfil = _esparso(
        tmp_path / "global-metadata.dat", b"\0HoriDualSenseWindowsProfile\0",
        fd._BLOCO - recuo, 3 * fd._BLOCO,
    )

    assert rj._sinais_do_arquivo(perfil, rewired=False) == (False, False)


def _datar(raiz: Path, ns: int = _UMA_HORA_ATRAS) -> None:
    for caminho in [raiz, *raiz.rglob("*")]:
        os.utime(caminho, ns=(ns, ns))


def _jogo(raiz: Path, arquivos: dict[str, bytes]) -> Path:
    for relativo, texto in arquivos.items():
        (raiz / relativo).parent.mkdir(parents=True, exist_ok=True)
        (raiz / relativo).write_bytes(texto)
    _datar(raiz)
    return raiz


def _conta(monkeypatch: pytest.MonkeyPatch, modulo: Any, nome: str) -> list[Path]:
    chamadas: list[Path] = []
    real = getattr(modulo, nome)

    def _contando(caminho: Path, *args: Any, **kw: Any) -> Any:
        chamadas.append(caminho)
        return real(caminho, *args, **kw)

    monkeypatch.setattr(modulo, nome, _contando)
    return chamadas


@pytest.fixture
def dois_jogos(tmp_path: Path) -> tuple[Path, Path]:
    edge = _jogo(tmp_path / "Edge", {
        _METADATA: b"\0PlayStation5EdgeUSBWindowsNativeProfile\0", "Jogo.exe": b"MZ",
    })
    comum = _jogo(tmp_path / "Comum", {
        "Jogo_Data/Plugins/SDL2.dll": b"DualSense Wireless Controller",
        "Jogo.exe": b"MZ\x4c\x05\xe6\x0c",
    })
    return edge, comum


def test_depois_do_reinicio_nenhum_jogo_se_rele(
    monkeypatch: pytest.MonkeyPatch, dois_jogos: tuple[Path, Path]
) -> None:
    """MORDIDA: não gravar o cache em disco relê os dois jogos depois do reinício."""
    edge, comum = dois_jogos
    antes = {raiz: rj.roupa_do_jogo(raiz) for raiz in dois_jogos}
    assert antes[edge][0] == "0df2" and antes[comum][0] == "0ce6", antes

    _o_reinicio()
    lidas = _conta(monkeypatch, rj, "_ler_o_disco")
    varridos = _conta(monkeypatch, fd, "_varrer_o_arquivo")

    assert {raiz: rj.roupa_do_jogo(raiz) for raiz in dois_jogos} == antes
    assert lidas == [] and varridos == []


def test_o_fio_escrevente_le_o_disco_e_grava_uma_vez(
    monkeypatch: pytest.MonkeyPatch, dois_jogos: tuple[Path, Path]
) -> None:
    """`roupas_dos_jogos` fora do laço, depois do reinício: só `stat`, e o lote grava no fim."""
    from hefesto_dualsense4unix.integrations import prontuario_dos_jogos

    edge, comum = dois_jogos
    monkeypatch.setattr(prontuario_dos_jogos, "jogos_instalados",
                        lambda _home=None: [("1", "Edge", edge), ("2", "Comum", comum)])
    monkeypatch.setattr(rj, "_opcoes_de_lancamento", lambda _home: {})
    gravacoes = _conta(monkeypatch, fd, "_escrever_no_disco")
    antes = rj.roupas_dos_jogos()
    assert [str(g) for g in gravacoes].count(rj._NOME_NO_DISCO) == 1, gravacoes

    _o_reinicio()
    lidas = _conta(monkeypatch, rj, "_ler_o_disco")
    assert rj.roupas_dos_jogos() == antes
    assert lidas == []


@pytest.mark.parametrize("mudanca", ["arquivo", "subpasta", "tamanho"])
def test_o_que_mudou_se_rele_e_so_ele(
    monkeypatch: pytest.MonkeyPatch, dois_jogos: tuple[Path, Path], mudanca: str
) -> None:
    edge, comum = dois_jogos
    for raiz in dois_jogos:
        rj.roupa_do_jogo(raiz)
    _o_reinicio()
    lidas = _conta(monkeypatch, rj, "_ler_o_disco")
    sdl = comum / "Jogo_Data/Plugins/SDL2.dll"
    if mudanca == "arquivo":
        os.utime(sdl, ns=(_UMA_HORA_ATRAS + 10**9, _UMA_HORA_ATRAS + 10**9))
    elif mudanca == "subpasta":
        (comum / "Jogo_Data/Plugins/novo.txt").write_bytes(b"")
    else:
        sdl.write_bytes(b"DualSense Wireless Controller DualSense Edge")
        os.utime(sdl, ns=(_UMA_HORA_ATRAS, _UMA_HORA_ATRAS))

    rj.roupa_do_jogo(edge)
    rj.roupa_do_jogo(comum)

    assert lidas == [comum]


@pytest.mark.parametrize(
    "texto",
    ["{ isto não é json", json.dumps({"versão": 999, "entradas": {}}), json.dumps([1, 2])],
)
def test_o_cache_corrompido_ou_de_outra_versao_vale_vazio(
    monkeypatch: pytest.MonkeyPatch, dois_jogos: tuple[Path, Path], texto: str
) -> None:
    edge, _comum = dois_jogos
    antes = rj.roupa_do_jogo(edge)
    from hefesto_dualsense4unix.utils.xdg_paths import cache_dir

    (cache_dir() / rj._NOME_NO_DISCO).write_text(texto, encoding="utf-8")
    (cache_dir() / fd._NOME_DOS_SINAIS).write_text(texto, encoding="utf-8")
    _o_reinicio()
    lidas = _conta(monkeypatch, rj, "_ler_o_disco")

    assert rj.roupa_do_jogo(edge) == antes
    assert lidas == [edge]


def test_o_laco_do_servico_nao_le_nem_grava_o_disco(
    monkeypatch: pytest.MonkeyPatch, dois_jogos: tuple[Path, Path]
) -> None:
    """Com `so_o_cache`, depois do reinício, o laço não abre o JSON: quem abre é o aquecimento."""
    from hefesto_dualsense4unix.integrations import prontuario_dos_jogos

    edge, comum = dois_jogos
    for raiz in dois_jogos:
        rj.roupa_do_jogo(raiz)
    _o_reinicio()
    monkeypatch.setattr(prontuario_dos_jogos, "jogos_instalados",
                        lambda _home=None: [("1", "Edge", edge), ("2", "Comum", comum)])
    monkeypatch.setattr(rj, "_opcoes_de_lancamento", lambda _home: {})
    no_laco: list[str] = []
    real = fd._guardado_no_disco

    def _quem_le(nome: str) -> Any:
        no_laco.append(threading.current_thread().name)
        return real(nome)

    monkeypatch.setattr(rj, "_guardado_no_disco", _quem_le)
    lidas = _conta(monkeypatch, rj, "_ler_o_disco")
    aqueceu = threading.Event()

    assert rj.roupas_dos_jogos(so_o_cache=True, ao_aquecer=aqueceu.set) == {}
    assert aqueceu.wait(10)
    assert set(no_laco) == {"hefesto-roupa"}, no_laco
    assert lidas == []
    assert set(rj.roupas_dos_jogos(so_o_cache=True)) == {"1", "2"}


def test_o_prontuario_usa_o_mesmo_leitor_e_guarda_por_arquivo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """MORDIDA: `examinar_o_binario` sem o cache por arquivo relê o executável a cada reinício."""
    pasta = _jogo(tmp_path / "Jogo", {"Jogo.exe": b"MZ scePad \x4c\x05\xf2\x0d"})
    antes = fd.examinar_o_binario(pasta)
    assert antes.sony == ("scePad",) and antes.pids == ("0df2",)

    _o_reinicio()
    varridos = _conta(monkeypatch, fd, "_varrer_o_arquivo")

    assert fd.examinar_o_binario(pasta) == antes
    assert varridos == []


def test_o_arquivo_recem_mudado_nao_se_guarda_por_arquivo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O `mtime` dentro da margem não entra no cache por arquivo: o disco de tempo grosso mente."""
    pasta = tmp_path / "Jogo"
    pasta.mkdir()
    (pasta / "Jogo.exe").write_bytes(b"MZ")
    fd.examinar_o_binario(pasta)
    varridos = _conta(monkeypatch, fd, "_varrer_o_arquivo")

    fd.examinar_o_binario(pasta)

    assert varridos == [pasta / "Jogo.exe"]
