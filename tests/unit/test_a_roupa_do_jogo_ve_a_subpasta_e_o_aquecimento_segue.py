"""A roupa do jogo vê o arquivo novo na subpasta, e o aquecimento segue no erro.

A-ROUPA-DO-JOGO-VE-A-SUBPASTA-E-O-AQUECIMENTO-NAO-ABORTA-01. A chave do cache da roupa
guardava o `stat` da raiz e dos arquivos lidos; um arquivo que nasce numa subpasta muda o
`mtime` da subpasta, e o cache devolvia a roupa velha até o daemon reiniciar. E uma raiz
que levantava no `_aquecer` encerrava o laço: as seguintes ficavam frias.

Tudo em pasta de mentira (`tmp_path`); só o disco do jogo é dublado, o resto é o código real.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import a_roupa_do_jogo as rj

_PASTA_DO_PERFIL = "Jogo_Data/il2cpp_data/Metadata"
_METADATA = f"{_PASTA_DO_PERFIL}/global-metadata.dat"
_PERFIL_DO_COMUM = b"PlayStation5USBWindowsNativeProfile"
_PASSADO_NS = 1_600_000_000 * 1_000_000_000


@pytest.fixture(autouse=True)
def _cache_limpo() -> Any:
    rj._CACHE.clear()
    yield
    rj._CACHE.clear()


def _jogo_sem_declaracao(raiz: Path) -> Path:
    """Um jogo que não nomeia controle nenhum, com a pasta do metadata já criada e velha."""
    pasta = raiz / _PASTA_DO_PERFIL
    pasta.mkdir(parents=True)
    (raiz / "Jogo.exe").write_bytes(b"MZ")
    for p in (pasta, pasta.parent, pasta.parent.parent):
        os.utime(p, ns=(_PASSADO_NS, _PASSADO_NS))
    return raiz


def test_o_arquivo_novo_na_subpasta_muda_a_roupa_sem_limpar_o_cache(tmp_path: Path) -> None:
    """Um jogo que ganha, numa subpasta, o arquivo que o declara `0ce6` veste o `0ce6`.

    MORDIDA: tirar as subpastas da chave (`_bibliotecas_e_manifesto` sem `pastas`, ou
    `_ler_o_disco` sem elas em `lidos`) devolve `0df2` na segunda pergunta.
    """
    raiz = _jogo_sem_declaracao(tmp_path / "Jogo")

    antes, _fonte = rj.roupa_do_jogo(raiz)
    assert antes == "0df2"
    assert str(raiz) in rj._CACHE, "a primeira pergunta guardou a leitura"

    (raiz / _METADATA).write_bytes(b"\0" + _PERFIL_DO_COMUM + b"\0")

    depois, fonte = rj.roupa_do_jogo(raiz)
    assert depois == "0ce6", fonte
    assert fonte == f"{_METADATA} declara só o DualSense comum"


def test_a_chave_guarda_as_subpastas_que_a_varredura_visitou(tmp_path: Path) -> None:
    """A chave nomeia a raiz, cada subpasta visitada e os arquivos lidos, sem repetir a raiz."""
    raiz = _jogo_sem_declaracao(tmp_path / "Jogo")

    rj.roupa_do_jogo(raiz)

    chave, _declarado = rj._CACHE[str(raiz)]
    caminhos = [c for c, _t, _m in chave]
    assert caminhos[0] == str(raiz)
    assert caminhos.count(str(raiz)) == 1
    for pasta in (
        raiz / "Jogo_Data",
        raiz / "Jogo_Data" / "il2cpp_data",
        raiz / _PASTA_DO_PERFIL,
    ):
        assert str(pasta) in caminhos, pasta
    assert str(raiz / "Jogo.exe") in caminhos


def test_o_arquivo_que_some_da_subpasta_tambem_invalida(tmp_path: Path) -> None:
    """Apagar da subpasta o arquivo que declarava o `0ce6` devolve o Edge.

    O arquivo lido já estava na chave; o caso guarda que a volta da cura segue valendo
    para o que some.
    """
    raiz = _jogo_sem_declaracao(tmp_path / "Jogo")
    (raiz / _METADATA).write_bytes(b"\0" + _PERFIL_DO_COMUM + b"\0")
    assert rj.roupa_do_jogo(raiz)[0] == "0ce6"

    (raiz / _METADATA).unlink()

    assert rj.roupa_do_jogo(raiz)[0] == "0df2"


def test_o_aquecimento_segue_quando_uma_raiz_levanta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A segunda raiz levanta e a terceira aquece; o `ao_aquecer` é chamado e a trava solta.

    MORDIDA: o `try` fora do `for` encerra o laço na segunda raiz (a terceira nunca é
    pedida).
    """
    raizes = [tmp_path / n for n in ("a", "b", "c")]
    pedidas: list[Path] = []

    def _roupa(raiz: Path, **_kw: Any) -> tuple[str, str]:
        pedidas.append(raiz)
        if raiz.name == "b":
            raise RuntimeError("jogo com disco ruim")
        return "0df2", "x"

    avisos: list[int] = []
    monkeypatch.setattr(rj, "roupa_do_jogo", _roupa)
    rj._AQUECENDO.set()

    rj._aquecer(raizes, lambda: avisos.append(1))

    assert pedidas == raizes
    assert avisos == [1]
    assert not rj._AQUECENDO.is_set()


def test_a_raiz_que_levanta_e_registrada_com_o_caminho(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A falha de UMA raiz sai no registro com o caminho dela (e só dela)."""
    ruim, boa = tmp_path / "ruim", tmp_path / "boa"

    def _roupa(raiz: Path, **_kw: Any) -> tuple[str, str]:
        if raiz == ruim:
            raise RuntimeError("disco")
        return "0df2", "x"

    monkeypatch.setattr(rj, "roupa_do_jogo", _roupa)
    with caplog.at_level("DEBUG", logger=rj.logger.name):
        rj._aquecer([ruim, boa], None)

    registros = [r.getMessage() for r in caplog.records if "não aqueceu" in r.getMessage()]
    assert registros == [f"a roupa de {ruim} não aqueceu"]
