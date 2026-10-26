"""A-JANELA-ESPERA-A-TRAVA-E-DIZ-A-CAUSA-01 — as réguas.

A trava da lista de exclusão que não veio no prazo é uma resposta, e quem chama
a recebe com a causa: a carona diz «a trava não veio» (não «não havia
lançador»), a janela espera o prazo dela, e a lista devolve `"ocupada"` e
`"ilegivel"` em vez de um `"erro"` só. Outro processo segura a trava de verdade.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.integrations import cura_por_estrada as cpe
from hefesto_dualsense4unix.integrations import lista_de_exclusao as lx
from tests.unit.test_a_exclusao_mora_na_camada_do_jogo import _PONTE
from tests.unit.test_a_lista_de_exclusao_tem_um_escritor_por_vez import (
    _SEGURA_A_TRAVA,
    _ambiente,
    _esperar_o_arquivo,
)


from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07
from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

_CHAVE = "steam_app_1088850"
_CAIXA = "processo:regua"


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
    heroic = lar / ".config" / "heroic"
    heroic.mkdir(parents=True)
    (heroic / "config.json").write_text('{"defaultSettings": {}}')
    a09._ARMADO.clear()
    a09._PAINEL[0] = None
    a07._ESCOLHA.limpar()
    yield lar
    a09._ARMADO.clear()
    a09._PAINEL[0] = None
    a07._ESCOLHA.limpar()


_SEGURA_POR_UM_TEMPO = """
import fcntl, os, sys, time
from pathlib import Path
trava, pronto, segundos = Path(sys.argv[1]), Path(sys.argv[2]), float(sys.argv[3])
trava.parent.mkdir(parents=True, exist_ok=True)
fd = os.open(trava, os.O_RDWR | os.O_CREAT, 0o600)
fcntl.flock(fd, fcntl.LOCK_EX)
pronto.touch()
time.sleep(segundos)
"""


def _prender(tmp_path: Path, lar: Path, *, segundos: float) -> subprocess.Popen[str]:
    """Outro processo com a trava na mão por `segundos` (ou até `fim`, se negativo)."""
    pronto = tmp_path / f"pronto-{time.monotonic_ns()}"
    outro = subprocess.Popen(
        [sys.executable, "-c", _SEGURA_POR_UM_TEMPO,
         str(lx.caminho().parent / cpe.NOME_DA_TRAVA), str(pronto), str(segundos)],
        env=_ambiente(lar), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _esperar_o_arquivo(pronto, outro)
    return outro


@pytest.fixture
def _trava_presa(tmp_path: Path, _lar: Path) -> Iterator[subprocess.Popen[str]]:
    """Outro escritor com a trava na mão até o teste terminar."""
    pronto, fim = tmp_path / "pronto", tmp_path / "fim"
    outro = subprocess.Popen(
        [sys.executable, "-c", _SEGURA_A_TRAVA,
         str(lx.caminho().parent / cpe.NOME_DA_TRAVA), str(pronto), str(fim)],
        env=_ambiente(_lar), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        _esperar_o_arquivo(pronto, outro)
        yield outro
    finally:
        fim.touch()
        outro.communicate(timeout=30)


class _Ctx:
    state: dict[str, Any] | None = None


_CTX: Any = _Ctx()


def _so_as_estradas(monkeypatch: pytest.MonkeyPatch) -> None:
    """O duplo clique das correções mudo, menos os outros lançadores."""
    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

    monkeypatch.setattr(a09._daemon, "medir_jogos_com_steam_input", lambda: [])
    monkeypatch.setattr(a09, "_rodar_os_consertos", lambda jogos: {
        "ran": 0, "missing": 0, "steam_input": None, "steam_input_jogos": jogos})
    monkeypatch.setattr(a09._daemon, "format_fix_safe_result", lambda _r: "")
    monkeypatch.setattr(cv, "gravar_camadas_da_steam_fora", lambda _ligar: None)
    monkeypatch.setattr(cv, "frase_do_ato", lambda _ligar: "")
    monkeypatch.setattr(a09, "_o_pino", lambda: (None, lambda **_k: {"status": "noop"}))
    monkeypatch.setattr(a09, "_porque_o_proton_nao_trava", lambda *_a: None)
    monkeypatch.setattr(a09, "proton_fixado", lambda: True)
    monkeypatch.setattr(a09, "_versoes_que_sobram", lambda: [])


def _o_duplo_clique() -> None:
    """O que o duplo clique faz: reaplica e deixa o recibo no diário."""
    a09._relatar_o_recibo(a09.CAMPO_DAS_CORRECOES, a09._reaplicar_as_correcoes())


def test_o_duplo_clique_espera_a_trava_e_diz_heroic(
        tmp_path: Path, _lar: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    """Trava presa além do prazo do serviço e dentro do da janela: o recibo diz «Heroic».

    A janela espera 5 s, o serviço 1 s (D-0810-A-LISTA-OCUPADA-DIZ-A-CAUSA).
    """
    monkeypatch.setattr(cpe, "ESPERA_DO_SERVICO_S", 0.3)
    _so_as_estradas(monkeypatch)
    outro = _prender(tmp_path, _lar, segundos=1.5)
    try:
        antes = time.monotonic()
        _o_duplo_clique()
        gasto = time.monotonic() - antes
    finally:
        outro.communicate(timeout=30)
    recibo = capsys.readouterr().err
    assert "O ambiente do Hefesto está em: Heroic." in recibo, (
        f"a janela desistiu no prazo do serviço (esperou {gasto:.1f} s):\n{recibo}")
    assert gasto > 1.0, f"a janela não esperou a trava ({gasto:.2f} s)"
    assert "Nenhum outro lançador recebeu" not in recibo


def test_o_duplo_clique_com_a_trava_presa_alem_do_prazo_nao_diz_que_nao_havia_lancador(
        _lar: Path, _trava_presa: subprocess.Popen[str], monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    """Passar o prazo da janela não basta: o `()` de «a trava não veio» tem a frase própria."""
    monkeypatch.setattr(cpe, "ESPERA_DA_JANELA_S", 0.4)
    _so_as_estradas(monkeypatch)
    with structlog.testing.capture_logs() as diario:
        _o_duplo_clique()
    recibo = capsys.readouterr().err
    assert cpe.FRASE_DA_TRAVA_QUE_NAO_VEIO in recibo, recibo
    assert "Nenhum outro lançador recebeu" not in recibo, recibo
    assert "Heroic" not in recibo
    assert "{\"defaultSettings\": {}}" in (_lar / ".config/heroic/config.json").read_text(), (
        "a carona escreveu sem a trava")
    esperou = [x for x in diario if x.get("event") == "carona_esperou_a_janela"]
    assert [x.get("quem") for x in esperou] == [cpe.QUEM_JANELA], esperou


def test_a_carona_sem_a_trava_diz_que_ela_nao_veio(
        _lar: Path, _trava_presa: subprocess.Popen[str]) -> None:
    escritos = cpe.curar_todas_as_estradas(espera=0.4)
    assert escritos == ()
    assert escritos.sem_a_trava is True
    frase = cpe.frase_das_estradas(escritos)
    assert frase == cpe.FRASE_DA_TRAVA_QUE_NAO_VEIO
    assert "Nenhum outro lançador" not in frase


def test_a_carona_sem_lancador_nao_diz_que_a_trava_nao_veio(_lar: Path) -> None:
    """O outro vazio: a trava veio e não havia lançador — a frase de sempre."""
    shutil.rmtree(_lar / ".config/heroic")
    escritos = cpe.curar_todas_as_estradas()
    assert escritos == ()
    assert escritos.sem_a_trava is False
    assert cpe.frase_das_estradas(escritos).startswith("Nenhum outro lançador recebeu")


def test_a_carona_com_a_trava_escreve_e_diz_onde(_lar: Path) -> None:
    escritos = cpe.curar_todas_as_estradas()
    assert list(escritos) == ["heroic"]
    assert escritos.sem_a_trava is False
    assert cpe.frase_das_estradas(escritos) == "O ambiente do Hefesto está em: Heroic."


def test_o_servico_le_a_carona_como_sequencia(
        _lar: Path, _trava_presa: subprocess.Popen[str]) -> None:
    """O `list(estradas)` do diário do serviço segue valendo, com a trava e sem ela."""
    assert isinstance(cpe.curar_todas_as_estradas(espera=0.2), tuple)
    assert list(cpe.curar_todas_as_estradas()) == []


def test_o_servico_com_a_trava_livre_devolve_a_lista_de_antes(
        _lar: Path) -> None:
    assert list(cpe.curar_todas_as_estradas()) == ["heroic"]


def test_o_servico_segue_com_o_prazo_dele_e_o_diario_diz_quem(
        _lar: Path, _trava_presa: subprocess.Popen[str]) -> None:
    antes = time.monotonic()
    with structlog.testing.capture_logs() as diario:
        cpe.curar_todas_as_estradas()
    assert time.monotonic() - antes < cpe.ESPERA_DO_SERVICO_S + 1.0
    esperou = [x for x in diario if x.get("event") == "carona_esperou_a_janela"]
    assert [(x.get("quem"), x.get("espera_s")) for x in esperou] == [
        (cpe.QUEM_SERVICO, cpe.ESPERA_DO_SERVICO_S)], esperou


def test_o_anotar_sem_a_trava_diz_ocupada(
        tmp_path: Path, _lar: Path, _trava_presa: subprocess.Popen[str],
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cpe, "ESPERA_DA_JANELA_S", 0.3)
    yml = cpe.YmlDoJogo(str(tmp_path / "g.yml"), "x", "0")
    assert lx.anotar_os_ymls([yml]) == "ocupada"


def test_as_frases_da_tela_passam_pela_lingua_da_casa() -> None:
    """Sem «mesa», sem vermelho: a frase da trava que não veio fala a língua da casa."""
    frase = cpe.FRASE_DA_TRAVA_QUE_NAO_VEIO
    assert frase[0].isupper() and frase.endswith("."), frase
    assert "mesa" not in frase.casefold()
