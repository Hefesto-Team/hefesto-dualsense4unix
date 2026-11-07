"""A guarda da Steam não dispara em rajada (07/11/2026).

Medido no diário: 14 partidas em 24 s às 13:10, e as 111 voltas do dia deram `em_dia` no
`caminhos.conf`, parado desde 22/10. Quem dispara é a Steam regravando os `appmanifest` do
`steamapps`. Cada escrita é um `PathChanged`, e o `.path` não vigia enquanto a unidade `oneshot`
sobe: segurar a subida até a calma faz da rajada uma volta só. Medido no systemd 255 com a unidade
e a sentinela de verdade: 14 escritas, 14 partidas sem a espera e 1 com a espera.

`UnidadeDeMentira` é esse `.path` com o `oneshot`, sobre escritas de verdade em disco e a espera
real do produto.

MORDIDA: tirar a linha da unidade, a espera, o olhar dentro do `steamapps`, o teto, a comparação
do `garantir` ou a opção da sentinela reprova.

Faixa sintética da casa: os appid daqui não existem na Steam.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sdw
from hefesto_dualsense4unix.integrations import vigia_do_jogo_novo as vigia
from tests.unit.test_as_configuracoes_chegam_ao_jogo_novo import NOVO, _Casa, _manifesto

RAIZ = Path(__file__).resolve().parents[2]
UNIDADE = RAIZ / "assets" / "hefesto-steam-input-guard.service"
SENTINELA = Path(sdw.__file__)
CALMA_S = 0.6
TETO_S = 5.0
PASSO_S = 0.02


class UnidadeDeMentira:
    """Um `.path` com um `oneshot`: o gatilho com a unidade subindo não faz outra partida."""

    def __init__(self, espera: Callable[[], object]) -> None:
        self.espera = espera
        self.voltas = 0
        self.fundidos = 0
        self._tranca = threading.Lock()
        self._subindo: threading.Thread | None = None

    def gatilho(self) -> None:
        with self._tranca:
            if self._subindo is not None:
                self.fundidos += 1
                return
            self._subindo = threading.Thread(target=self._partida, daemon=True)
            self._subindo.start()

    def _partida(self) -> None:
        self.espera()
        with self._tranca:
            self.voltas += 1
            self._subindo = None

    def esperar_o_fim(self) -> None:
        fio = self._subindo
        if fio is not None:
            fio.join(TETO_S * 2)
        assert self._subindo is None, "a unidade não terminou"


@pytest.fixture
def casa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Casa:
    c = _Casa(tmp_path)
    monkeypatch.setenv("HOME", str(c.home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(c.config))
    monkeypatch.setattr(vigia, "_recarregar_o_systemd", lambda: True)
    return c


def _esperar(casa: _Casa) -> bool:
    return vigia.esperar_a_calma(casa.home, calma_s=CALMA_S, teto_s=TETO_S, passo_s=PASSO_S)


def _regravar(pasta: Path) -> None:
    (pasta / "appmanifest_1.acf").write_text(f'"AppState" {{ "t" "{time.time()}" }}\n',
                                             encoding="utf-8")


def _rajada(unidade: UnidadeDeMentira, pasta: Path, escritas: int) -> None:
    for _ in range(escritas):
        _regravar(pasta)
        unidade.gatilho()
        time.sleep(CALMA_S / 5)
    unidade.esperar_o_fim()


@pytest.fixture
def pasta_de_cada_biblioteca(casa: _Casa, request: pytest.FixtureRequest) -> Path:
    return casa.steam / "steamapps" if request.param == "principal" else (
        casa.biblioteca / "steamapps")


@pytest.mark.parametrize("pasta_de_cada_biblioteca", ["principal", "outra"], indirect=True)
def test_a_rajada_inteira_vira_uma_volta_depois_da_ultima_escrita(
    casa: _Casa, pasta_de_cada_biblioteca: Path
) -> None:
    unidade = UnidadeDeMentira(lambda: _esperar(casa))
    _rajada(unidade, pasta_de_cada_biblioteca, 14)
    assert unidade.voltas == 1
    assert unidade.fundidos == 13


def test_sem_a_espera_a_mesma_rajada_faz_uma_volta_por_escrita(casa: _Casa) -> None:
    """A régua do dublê: é ele que mostra a rajada medida quando a subida não segura nada."""
    unidade = UnidadeDeMentira(lambda: None)
    pasta = casa.steam / "steamapps"
    for _ in range(14):
        _regravar(pasta)
        unidade.gatilho()
        unidade.esperar_o_fim()
    assert unidade.voltas == 14


def test_a_escrita_que_para_antes_da_calma_ainda_conta(casa: _Casa) -> None:
    """A volta sai DEPOIS da última escrita, e por isso enxerga a Steam já fechada."""
    pasta = casa.steam / "steamapps"
    _regravar(pasta)
    comeco = time.monotonic()
    fio = threading.Thread(target=_regravar_depois, args=(pasta, CALMA_S / 2))
    fio.start()
    assert _esperar(casa)
    fio.join()
    assert time.monotonic() - comeco >= CALMA_S * 1.4


def _regravar_depois(pasta: Path, atraso: float) -> None:
    time.sleep(atraso)
    _regravar(pasta)


def test_sem_escrita_recente_a_volta_nao_espera_nada(casa: _Casa) -> None:
    antigo = time.time() - 3600
    for caminho in vigia.caminhos_a_vigiar(casa.home):
        for item in [caminho, *(caminho.iterdir() if caminho.is_dir() else ())]:
            if item.exists():
                os.utime(item, (antigo, antigo))
    comeco = time.monotonic()
    assert vigia.esperar_a_calma(casa.home, calma_s=30.0, teto_s=30.0, passo_s=1.0)
    assert time.monotonic() - comeco < 1.0


def test_a_data_no_futuro_nao_segura_a_volta(casa: _Casa) -> None:
    """Um arquivo com o relógio de outra máquina não vira escrita de agora em toda volta."""
    antigo = time.time() - 3600
    for caminho in vigia.caminhos_a_vigiar(casa.home):
        for item in [caminho, *(caminho.iterdir() if caminho.is_dir() else ())]:
            if item.exists():
                os.utime(item, (antigo, antigo))
    futuro = time.time() + 3600
    os.utime(casa.steam / "steamapps" / "libraryfolders.vdf", (futuro, futuro))
    comeco = time.monotonic()
    assert vigia.esperar_a_calma(casa.home, calma_s=30.0, teto_s=30.0, passo_s=1.0)
    assert time.monotonic() - comeco < 1.0


def test_a_escrita_durante_a_varredura_nao_some_da_conta(
    casa: _Casa, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A régua da hora vem depois de olhar os arquivos: o que foi escrito enquanto se olhava é de
    agora, não do futuro."""
    antigo = time.time() - 3600
    for caminho in vigia.caminhos_a_vigiar(casa.home):
        for item in [caminho, *(caminho.iterdir() if caminho.is_dir() else ())]:
            if item.exists():
                os.utime(item, (antigo, antigo))
    instantes = vigia._instantes_de_escrita

    def escrevendo(caminho: Path) -> Iterator[float]:
        time.sleep(PASSO_S)
        _regravar(casa.steam / "steamapps")
        return instantes(caminho)

    monkeypatch.setattr(vigia, "_instantes_de_escrita", escrevendo)
    assert vigia._ultima_mudanca(vigia.caminhos_a_vigiar(casa.home)) > antigo + 1800


def test_a_data_no_futuro_nao_esconde_a_escrita_de_agora(casa: _Casa) -> None:
    pasta = casa.steam / "steamapps"
    futuro = time.time() + 3600
    os.utime(pasta / "libraryfolders.vdf", (futuro, futuro))
    _regravar(pasta)
    assert vigia._ultima_mudanca(vigia.caminhos_a_vigiar(casa.home)) > time.time() - 5


def test_o_download_sem_fim_nao_segura_a_volta_para_sempre(casa: _Casa) -> None:
    pasta = casa.steam / "steamapps"
    parar = threading.Event()

    def baixando() -> None:
        while not parar.wait(PASSO_S):
            _regravar(pasta)

    respostas: list[bool] = []

    def segurando() -> None:
        respostas.append(vigia.esperar_a_calma(casa.home, calma_s=TETO_S, teto_s=0.3,
                                               passo_s=PASSO_S))

    fios = [threading.Thread(target=alvo, daemon=True) for alvo in (baixando, segurando)]
    for fio in fios:
        fio.start()
    fios[1].join(TETO_S)
    terminou = not fios[1].is_alive()
    parar.set()
    fios[0].join(TETO_S)
    assert terminou, "o teto não soltou a volta com a Steam escrevendo sem parar"
    assert respostas == [False]


def test_a_conta_e_o_vdf_tambem_seguram_a_volta(casa: _Casa) -> None:
    vdf = vigia.caminhos_a_vigiar(casa.home)[0]
    assert vdf.name == "localconfig.vdf"
    antigo = time.time() - 3600
    for caminho in vigia.caminhos_a_vigiar(casa.home):
        os.utime(caminho, (antigo, antigo))
        if caminho.is_dir():
            for item in caminho.iterdir():
                os.utime(item, (antigo, antigo))
    assert vigia._ultima_mudanca(vigia.caminhos_a_vigiar(casa.home)) <= antigo + 1
    vdf.write_text(vdf.read_text(encoding="utf-8"), encoding="utf-8")
    assert vigia._ultima_mudanca(vigia.caminhos_a_vigiar(casa.home)) > antigo + 1


def test_a_rajada_nao_grava_nem_recarrega_sem_mudanca(casa: _Casa) -> None:
    recargas: list[int] = []

    def recarregar() -> bool:
        recargas.append(1)
        return True

    assert vigia.garantir(casa.home, config_home=casa.config,
                          recarregar=recarregar) == vigia.ESCRITO
    caminhos = casa.unidades / "hefesto-steam-input-guard.path.d" / "caminhos.conf"
    antes = caminhos.stat().st_mtime_ns
    for _ in range(14):
        _regravar(casa.steam / "steamapps")
        assert vigia.garantir(casa.home, config_home=casa.config,
                              recarregar=recarregar) == vigia.EM_DIA
    assert caminhos.stat().st_mtime_ns == antes
    assert recargas == [1]


def test_o_jogo_novo_em_qualquer_biblioteca_segue_entrando(casa: _Casa) -> None:
    vigia.garantir(casa.home, config_home=casa.config)
    unidade = UnidadeDeMentira(lambda: _esperar(casa))
    casa.instala_o_jogo_novo()
    unidade.gatilho()
    unidade.esperar_o_fim()
    assert unidade.voltas == 1
    assert vigia.jogos_novos_a_receber(casa.home, config_home=casa.config).count(NOVO) == 1
    assert casa.biblioteca / "steamapps" in vigia.caminhos_a_vigiar(casa.home)


def test_biblioteca_nova_entra_no_vigia_e_so_a_mudanca_regrava(casa: _Casa) -> None:
    vigia.garantir(casa.home, config_home=casa.config)
    nova = casa.home / "SSD" / "steamapps"
    nova.mkdir(parents=True)
    _manifesto(nova, "3333", "Outro Jogo")
    vdf = casa.steam / "steamapps" / "libraryfolders.vdf"
    vdf.write_text(vdf.read_text(encoding="utf-8").rstrip()[:-1]
                   + f'\t"2"\n\t{{\n\t\t"path"\t\t"{nova.parent}"\n\t}}\n}}\n', encoding="utf-8")
    assert vigia.garantir(casa.home, config_home=casa.config) == vigia.ESCRITO
    assert "PathChanged=%h/SSD/steamapps\n" in casa.dropin()


def test_a_unidade_segura_a_subida_antes_de_todo_passo() -> None:
    linhas = UNIDADE.read_text(encoding="utf-8").splitlines()
    execucoes = [ln for ln in linhas if re.match(r"Exec[A-Za-z]*=", ln)]
    assert execucoes[0] == "ExecStartPre=-/usr/bin/env python3 __SENTINELA__ --esperar-a-calma"
    assert all(ln.startswith("ExecStart=") for ln in execucoes[1:])


def test_a_opcao_da_unidade_chega_ao_vigia_e_nao_escreve_nada(
    casa: _Casa, monkeypatch: pytest.MonkeyPatch
) -> None:
    chamadas: list[int] = []
    monkeypatch.setattr(sdw, "esperar_a_calma", lambda: chamadas.append(1))
    monkeypatch.setattr(sdw, "garantir_o_vigia", lambda **_k: pytest.fail("a espera não grava"))
    assert sdw.main(["--esperar-a-calma"]) == 0
    assert chamadas == [1]


def test_a_sentinela_roda_a_espera_como_a_unidade_roda(casa: _Casa, tmp_path: Path) -> None:
    """A unidade chama o arquivo solto, com o `python3` do sistema, sem o pacote no caminho."""
    antigo = time.time() - 3600
    for caminho in vigia.caminhos_a_vigiar(casa.home):
        os.utime(caminho, (antigo, antigo))
        if caminho.is_dir():
            for item in caminho.iterdir():
                os.utime(item, (antigo, antigo))
    ambiente = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    ambiente.update(HOME=str(casa.home), XDG_CONFIG_HOME=str(casa.config))
    saida = subprocess.run([sys.executable, str(SENTINELA), "--esperar-a-calma"],
                           capture_output=True, text=True, timeout=30, check=False, env=ambiente,
                           cwd=tmp_path)
    assert saida.returncode == 0, saida.stderr
