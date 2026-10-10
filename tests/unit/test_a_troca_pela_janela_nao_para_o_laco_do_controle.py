"""A troca pela janela não para o laço do controle.

A-TROCA-PELA-JANELA-NAO-PARA-O-LACO-DO-CONTROLE-01 (09/10/2026). A troca automática roda no laço
asyncio do serviço, o mesmo que leva o pad virtual de P1 a P4 a 60 Hz. Ela lia a janela ali
(``wlrctl`` é um processo por leitura), copiava fundo cada perfil a cada tique para só ler o
``match`` e a ``priority``, e disparava a semeadura dos jogos no mesmo fio. A cura: a leitura da
janela, a semeadura e a leitura dos perfis mudados vão a um executor de uma vaga do
``AutoSwitcher``; a escolha lê os perfis sem cópia e copia só o escolhido.

TUDO É DE MENTIRA: perfis no lar isolado do conftest, ``FakeController``, leitor de janela que só
dorme; o dono do evento é dado como armado por ``monkeypatch``, sem inotify nenhum.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core import o_dono_do_evento as _ode
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import Profile
from hefesto_dualsense4unix.testing.fake_controller import FakeController
from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

JANELA = {"wm_class": "jogo07_class", "wm_name": "O jogo", "exe_basename": "jogo07"}
QUADRO_S = 1 / 60


def _gerente() -> ProfileManager:
    fc = FakeController()
    fc.connect()
    return ProfileManager(controller=fc, store=StateStore())


def _quarenta_perfis_parados() -> None:
    """40 perfis, um por jogo, com o arquivo de uma hora atrás (fora do recém-gravado)."""
    pasta = profiles_dir(ensure=True)
    uma_hora_atras = time.time() - 3600
    for n in range(40):
        caminho = pasta / f"jogo{n:02d}.json"
        caminho.write_text(json.dumps({
            "name": f"jogo{n:02d}", "version": 1, "priority": 10,
            "match": {"type": "criteria", "window_class": [f"jogo{n:02d}_class"]},
        }), encoding="utf-8")
        os.utime(caminho, (uma_hora_atras, uma_hora_atras))


@pytest.fixture
def dono_armado(monkeypatch: pytest.MonkeyPatch):
    """O serviço: o dono do evento armado, e a leitura pela assinatura limpa nos dois lados."""
    monkeypatch.setattr(_ode, "armado", lambda: True)
    loader._PERFIS_PELA_ASSINATURA.esquecer()
    yield
    loader._PERFIS_PELA_ASSINATURA.esquecer()


def test_o_leitor_lento_nao_para_o_relogio_de_60_hz(dono_armado: None) -> None:
    """Leitor de 200 ms, 40 perfis e um relógio a 60 Hz no mesmo laço: nenhum quadro passa de 40 ms.

    Os perfis entram frios: a primeira leitura decodifica os 40, e ela também anda fora do laço.
    """
    _quarenta_perfis_parados()

    def leitor_lento() -> dict[str, Any]:
        time.sleep(0.2)
        return dict(JANELA)

    sw = AutoSwitcher(manager=_gerente(), window_reader=leitor_lento, poll_interval_sec=0.05)
    intervalos: list[float] = []

    async def cena() -> None:
        tarefa = sw.start()
        loop = asyncio.get_running_loop()
        antes = loop.time()
        fim = antes + 3.0
        while loop.time() < fim:
            await asyncio.sleep(QUADRO_S)
            agora = loop.time()
            intervalos.append(agora - antes)
            antes = agora
        sw.stop()
        await asyncio.wait_for(tarefa, timeout=5.0)

    asyncio.run(cena())

    assert len(intervalos) > 60
    assert max(intervalos) < 0.040, f"o maior quadro levou {max(intervalos) * 1000:.0f} ms"


def test_a_escolha_copia_so_o_perfil_escolhido(
    dono_armado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """40 perfis parados, 10 tiques: no máximo uma cópia profunda por tique, nunca 400."""
    _quarenta_perfis_parados()
    copias: list[str] = []
    copiar_de_verdade = Profile.model_copy

    def _contar(self: Profile, *a: Any, **kw: Any) -> Profile:
        copias.append(self.name)
        return copiar_de_verdade(self, *a, **kw)

    sw = AutoSwitcher(manager=_gerente(), window_reader=lambda: dict(JANELA), debounce_sec=1e9)
    sw._tick(dict(JANELA), 0.0)  # a primeira leitura decodifica e guarda
    monkeypatch.setattr(Profile, "model_copy", _contar)

    for tique in range(10):
        sw._tick(dict(JANELA), 1.0 + tique * 0.5)

    assert len(copias) <= 10, f"{len(copias)} cópias em 10 tiques"
    assert set(copias) <= {"jogo07"}


def test_o_perfil_escolhido_e_uma_copia_e_quem_o_edita_nao_mexe_no_guardado(
    dono_armado: None,
) -> None:
    _quarenta_perfis_parados()
    gerente = _gerente()
    perfil, _ = gerente.select_for_window_ex(dict(JANELA))
    assert perfil is not None and perfil.name == "jogo07"
    perfil.priority = 99
    de_novo, _ = gerente.select_for_window_ex(dict(JANELA))
    assert de_novo is not None and de_novo.priority == 10
    assert all(p.priority == 10 for p in loader.load_all_profiles())


@pytest.fixture
def biblioteca_mudada(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """A semeadura ligada, a biblioteca com assinatura nova, e um espião na semeadura."""
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores, jogos_locais

    monkeypatch.delenv(loader.SEED_SKIP_ENV_VAR, raising=False)
    monkeypatch.setattr(loader, "_seed_attempted", True)
    monkeypatch.setattr(loader, "_ultima_varredura_de_jogos", None)
    monkeypatch.setattr(loader, "_assinatura_da_biblioteca_vista", None)
    monkeypatch.setattr(jogos_locais, "assinatura_da_biblioteca", lambda: ("nova",))
    monkeypatch.setattr(jogos_locais, "assinatura_das_janelas", lambda: ("nova",))
    monkeypatch.setattr(censo_dos_lancadores, "assinatura_das_bibliotecas", lambda: ("nova",))
    semeou: list[str] = []
    monkeypatch.setattr(loader, "semear_perfis_dos_jogos", lambda *a, **k: semeou.append("s"))
    monkeypatch.setattr(loader, "reapontar_perfis_com_chave_de_executavel", lambda *a, **k: None)
    return semeou


def test_o_tique_no_laco_nao_semeia_e_o_passo_fora_do_laco_semeia(
    dono_armado: None, biblioteca_mudada: list[str]
) -> None:
    sw = AutoSwitcher(manager=_gerente(), window_reader=lambda: dict(JANELA), debounce_sec=1e9)

    async def tique_no_laco() -> None:
        sw._tick(dict(JANELA), 0.0)

    asyncio.run(tique_no_laco())
    assert biblioteca_mudada == [], "o tique no laço semeou"

    async def passo_fora_do_laco() -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, sw._ler_fora_do_laco)

    assert asyncio.run(passo_fora_do_laco()) == JANELA
    assert biblioteca_mudada == ["s"]


def test_fora_do_servico_a_leitura_segue_semeando(biblioteca_mudada: list[str]) -> None:
    """A interface e a linha de comando, sem o dono do evento: o gatilho preguiçoso fica."""
    loader.load_all_profiles()
    assert biblioteca_mudada == ["s"]


def test_a_carga_fora_do_laco_no_servico_segue_semeando(
    dono_armado: None, biblioteca_mudada: list[str]
) -> None:
    """No serviço, só a leitura feita DENTRO do laço deixa de semear."""
    loader.load_all_profiles()
    assert biblioteca_mudada == ["s"]


def test_o_guardado_por_assinatura_e_um_dono_so(dono_armado: None) -> None:
    """A escolha e o `load_all_profiles` leem a mesma leitura pela assinatura."""
    _quarenta_perfis_parados()
    gerente = _gerente()
    gerente.select_for_window_ex(dict(JANELA))
    guardados = loader._PERFIS_PELA_ASSINATURA._guardados
    assert len(guardados) == 40
    assert Path(next(iter(guardados))).parent == profiles_dir()
