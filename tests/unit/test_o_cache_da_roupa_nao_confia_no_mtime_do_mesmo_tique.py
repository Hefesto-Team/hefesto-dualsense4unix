"""O cache da roupa do jogo não confia no arquivo que mudou no mesmo tique.

O-CACHE-DA-ROUPA-NAO-CONFIA-NO-MTIME-DO-MESMO-TIQUE-01. A chave do cache é o
`(caminho, tamanho, mtime)` da raiz, das subpastas e dos arquivos lidos. Num disco de tempo
grosso (FAT guarda 2 s, exFAT 10 ms), o arquivo que nasce no MESMO tique do `mtime` que a
leitura anterior viu deixa a pasta igual, e o cache devolvia a roupa velha até o daemon
reiniciar. A cura é a do índice do git: a leitura leva o instante em que COMEÇOU, e o que
mudou a menos de uma margem dele é suspeito. O suspeito serve a roupa guardada (o laço do
serviço nunca perde um jogo por isso) e ganha UMA releitura fora do laço, passada a margem.

Tudo em pasta de mentira (`tmp_path`), com o relógio do módulo trocado por um de mentira (nada
dorme) e o tamanho do diretório fixo, como num disco de tempo grosso: só o relógio e o disco são
dublados, o resto é o código real.
"""
from __future__ import annotations

import os
import stat as _stat
import threading
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import a_roupa_do_jogo as rj

_PASTA_DO_PERFIL = "Jogo_Data/il2cpp_data/Metadata"
_METADATA = f"{_PASTA_DO_PERFIL}/global-metadata.dat"
_PERFIL_DO_COMUM = b"\0PlayStation5USBWindowsNativeProfile\0"
_T0 = 1_700_000_000 * 10**9
_SEGUNDO = 10**9


class _Relogio:
    """O relógio de parede do módulo, em ns, que só anda quando o teste manda."""

    def __init__(self) -> None:
        self.ns = _T0

    def __call__(self) -> int:
        return self.ns

    def avanca(self, segundos: float) -> None:
        self.ns += int(segundos * _SEGUNDO)


@pytest.fixture(autouse=True)
def _cache_limpo() -> Iterator[None]:
    rj._CACHE.clear()
    rj._LIDO_EM.clear()
    rj._AQUECENDO.clear()
    yield
    rj._CACHE.clear()
    rj._LIDO_EM.clear()
    rj._AQUECENDO.clear()


@pytest.fixture
def relogio(monkeypatch: pytest.MonkeyPatch) -> _Relogio:
    falso = _Relogio()
    monkeypatch.setattr(rj, "_agora_ns", falso)
    return falso


@pytest.fixture(autouse=True)
def _disco_de_tempo_grosso(monkeypatch: pytest.MonkeyPatch) -> None:
    """O diretório não muda de tamanho quando ganha um arquivo (ext4, exFAT): só o `mtime` o diz."""
    os_real = rj.os

    class _OsGrosso:
        def __getattr__(self, nome: str) -> Any:
            return getattr(os_real, nome)

        @staticmethod
        def stat(caminho: Any, *args: Any, **kw: Any) -> Any:
            st = os_real.stat(caminho, *args, **kw)
            if _stat.S_ISDIR(st.st_mode):
                return SimpleNamespace(st_size=0, st_mtime_ns=st.st_mtime_ns)
            return st

    monkeypatch.setattr(rj, "os", _OsGrosso())


def _datar(raiz: Path, ns: int) -> None:
    """Põe a mesma data na raiz, nas subpastas e nos arquivos: o relógio grosso que não andou."""
    for caminho in [raiz, *raiz.rglob("*")]:
        os.utime(caminho, ns=(ns, ns))


def _jogo(raiz: Path, ns: int) -> Path:
    """Um jogo que não nomeia controle nenhum, recém-instalado: tudo datado em `ns`."""
    (raiz / _PASTA_DO_PERFIL).mkdir(parents=True)
    (raiz / "Jogo.exe").write_bytes(b"MZ")
    _datar(raiz, ns)
    return raiz


def _chega_o_perfil_no_mesmo_tique(raiz: Path, ns: int) -> None:
    """O arquivo que declara o `0ce6` nasce e o disco devolve a data de antes a tudo."""
    (raiz / _METADATA).write_bytes(_PERFIL_DO_COMUM)
    _datar(raiz, ns)


def _conta_as_leituras(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    lidas: list[Path] = []
    real = rj._ler_o_disco

    def _contando(raiz: Path) -> Any:
        lidas.append(raiz)
        return real(raiz)

    monkeypatch.setattr(rj, "_ler_o_disco", _contando)
    return lidas


def _o_laco_do_servico(
    monkeypatch: pytest.MonkeyPatch, raiz: Path
) -> tuple[Any, threading.Event]:
    """`roupas_dos_jogos` com um jogo só (appid `1`), sem Steam, e o aviso do aquecimento."""
    from hefesto_dualsense4unix.integrations import prontuario_dos_jogos

    monkeypatch.setattr(
        prontuario_dos_jogos, "jogos_instalados", lambda _home=None: [("1", "Jogo", raiz)]
    )
    monkeypatch.setattr(rj, "_opcoes_de_lancamento", lambda _home: {})
    aqueceu = threading.Event()

    def _laco() -> dict[str, tuple[str, str]]:
        return rj.roupas_dos_jogos(so_o_cache=True, ao_aquecer=aqueceu.set)

    return _laco, aqueceu


def test_o_arquivo_do_mesmo_tique_aparece_passada_a_margem(
    tmp_path: Path, relogio: _Relogio
) -> None:
    """Chave igual, leitura recém-feita: passada a margem, a roupa muda sem reiniciar nada.

    MORDIDA: tirar a regra do suspeito (`_a_releitura_venceu` sempre falso), ou zerar a margem,
    devolve `0df2` na consulta de depois da margem.
    """
    t_arquivos = _T0 - _SEGUNDO // 2
    raiz = _jogo(tmp_path / "Jogo", t_arquivos)

    assert rj.roupa_do_jogo(raiz)[0] == "0df2"
    chave_antes = rj._CACHE[str(raiz)][0]

    _chega_o_perfil_no_mesmo_tique(raiz, t_arquivos)
    assert rj._chave(raiz, [Path(c) for c, _t, _m in chave_antes[1:]]) == chave_antes, (
        "o disco de tempo grosso: a chave não viu o arquivo novo"
    )

    relogio.avanca(1)  # dentro da margem: a roupa guardada serve
    assert rj.roupa_do_jogo(raiz)[0] == "0df2"

    relogio.avanca(2)  # passada: o mtime mais novo + a margem ficou para trás
    roupa, fonte = rj.roupa_do_jogo(raiz)
    assert roupa == "0ce6", fonte
    assert fonte == f"{_METADATA} declara só o DualSense comum"


def test_dentro_da_margem_o_laco_serve_a_roupa_guardada_e_o_jogo_nao_sai_de_roupas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relogio: _Relogio
) -> None:
    """O suspeito AINDA SERVE a leitura guardada: sem ela o jogo sairia de `roupas`.

    MORDIDA: o suspeito devolver `None` tira o jogo de `roupas` na consulta do laço.
    """
    raiz = _jogo(tmp_path / "Jogo", _T0 - _SEGUNDO // 2)
    laco, aqueceu = _o_laco_do_servico(monkeypatch, raiz)
    rj.roupa_do_jogo(raiz)  # a leitura recém-feita e suspeita
    lidas = _conta_as_leituras(monkeypatch)

    relogio.avanca(1)
    assert set(laco()) == {"1"}
    assert laco()["1"][0] == "0df2"
    assert not aqueceu.is_set(), "dentro da margem não há releitura"
    assert not rj._AQUECENDO.is_set()
    assert lidas == []

    _chega_o_perfil_no_mesmo_tique(raiz, _T0 - _SEGUNDO // 2)
    relogio.avanca(2)  # passada a margem: o laço segue servindo o guardado e pede UM aquecimento
    assert laco()["1"][0] == "0df2"
    assert aqueceu.wait(5), "o aquecimento relê fora do laço e avisa"
    assert lidas == [raiz]
    assert laco()["1"][0] == "0ce6"


def test_o_arquivo_que_chega_durante_a_leitura_tambem_e_visto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relogio: _Relogio
) -> None:
    """A chave sai DEPOIS da leitura: o arquivo que chega no meio entra nela sem entrar na leitura.

    O instante em que a leitura COMEÇOU, tirado antes dela, fecha o vão: a pasta dele é mais nova
    que o começo, logo a leitura é suspeita, e a consulta seguinte (a leitura lenta já passou da
    margem) a refaz. MORDIDA: tirar o instante DEPOIS da leitura deixa o `0df2` para sempre.
    """
    raiz = _jogo(tmp_path / "Jogo", _T0 - _SEGUNDO)
    real = rj._ler_o_disco

    def _lenta_com_chegada(pasta: Path) -> Any:
        lido = real(pasta)
        _chega_o_perfil_no_mesmo_tique(pasta, _T0 + _SEGUNDO // 10)  # depois do começo
        relogio.avanca(5)  # a instalação em andamento: a leitura demorou
        return lido

    monkeypatch.setattr(rj, "_ler_o_disco", _lenta_com_chegada)
    assert rj.roupa_do_jogo(raiz)[0] == "0df2", "a leitura não viu o arquivo que chegou depois dela"
    monkeypatch.setattr(rj, "_ler_o_disco", real)

    assert rj.roupa_do_jogo(raiz)[0] == "0ce6"


def test_datas_velhas_nao_relem_e_o_suspeito_se_le_uma_vez_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relogio: _Relogio
) -> None:
    """O cache segue sendo cache: nada de reler a cada consulta.

    MORDIDA: reler a cada consulta (ou desligar o cache) reprova as duas contagens.
    """
    lidas = _conta_as_leituras(monkeypatch)
    velho = _jogo(tmp_path / "Velho", _T0 - 3600 * _SEGUNDO)
    for _ in range(3):
        assert rj.roupa_do_jogo(velho)[0] == "0df2"
    assert lidas == [velho], "as datas mais velhas que a margem: uma leitura só"

    lidas.clear()
    novo = _jogo(tmp_path / "Novo", _T0 - _SEGUNDO // 2)
    for _ in range(3):
        assert rj.roupa_do_jogo(novo)[0] == "0df2"
    assert lidas == [novo], "dentro da margem a consulta não relê"

    relogio.avanca(3)
    for _ in range(3):
        assert rj.roupa_do_jogo(novo)[0] == "0df2"
    assert lidas == [novo, novo], "passada a margem, UMA releitura, e a seguinte já não é suspeita"


def test_a_chave_diferente_segue_o_caminho_de_sempre(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relogio: _Relogio
) -> None:
    """Quem escreve na própria pasta o tempo todo muda a chave e é lido na hora, sem margem."""
    raiz = _jogo(tmp_path / "Jogo", _T0 - _SEGUNDO // 2)
    assert rj.roupa_do_jogo(raiz)[0] == "0df2"
    lidas = _conta_as_leituras(monkeypatch)

    (raiz / _METADATA).write_bytes(_PERFIL_DO_COMUM)
    _datar(raiz, _T0 + _SEGUNDO // 4)  # a data MUDOU: a chave vê

    assert rj.roupa_do_jogo(raiz)[0] == "0ce6"
    assert lidas == [raiz]
