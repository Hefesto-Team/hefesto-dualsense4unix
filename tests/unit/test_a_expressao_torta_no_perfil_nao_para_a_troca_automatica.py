"""Uma expressão inválida no título da janela não para a troca automática.

A expressão se confere ao gravar (o schema, para todo chamador); o arquivo antigo que ainda a traz
não casa com janela nenhuma e não derruba o que lê a lista; e o laço do autoswitch segue vivo quando
um tique falha, com a morte da tarefa registrada. A pasta de perfis é de mentira em todo teste.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli.app import app
from hefesto_dualsense4unix.profiles import autoswitch as autoswitch_mod
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
from hefesto_dualsense4unix.profiles.loader import load_all_profiles, save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)
from hefesto_dualsense4unix.testing import FakeController

runner = CliRunner()

EXPRESSAO_TORTA = "[abc"


@pytest.fixture
def pasta_de_mentira(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)

    from hefesto_dualsense4unix.utils import session, xdg_paths

    cfg = tmp_path / "config"
    cfg.mkdir()

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            cfg.mkdir(parents=True, exist_ok=True)
        return cfg

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    monkeypatch.setattr(session, "config_dir", fake_config_dir)
    return alvo


def _perfil(nome: str, classe: str) -> Profile:
    return Profile(
        name=nome,
        match=MatchCriteria(window_class=[classe]),
        priority=10,
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Rigid", params=[0, 100]),
        ),
        leds=LedsConfig(lightbar=(10, 20, 30)),
    )


def _json_torto(nome: str) -> dict[str, Any]:
    bom = _perfil(nome, "x").model_dump(mode="json")
    bom["match"] = {"type": "criteria", "window_title_regex": EXPRESSAO_TORTA}
    return bom


def test_o_comando_recusa_a_expressao_torta_e_nao_cria_arquivo(pasta_de_mentira: Path) -> None:
    resultado = runner.invoke(
        app, ["profile", "create", "ruim", "--match-regex", EXPRESSAO_TORTA]
    )
    assert resultado.exit_code != 0
    assert not list(pasta_de_mentira.glob("*.json"))
    assert "expressão" in resultado.output
    assert "Traceback" not in resultado.output


def test_o_schema_recusa_a_expressao_torta_para_todo_chamador() -> None:
    with pytest.raises(ValidationError):
        MatchCriteria(window_title_regex=EXPRESSAO_TORTA)
    com_lixo = MatchCriteria(window_title_regex=r"(?<!\w)9912410(?!\w)")
    assert com_lixo.matches({"wm_name": "Minecraft Dungeons II 9912410"})


def test_a_expressao_boa_segue_casando_sem_caixa() -> None:
    criterio = MatchCriteria(window_title_regex="dungeons")
    assert criterio.matches({"wm_name": "Minecraft DUNGEONS"})
    assert not criterio.matches({"wm_name": "Navegador"})
    assert not criterio.matches({})


def test_o_arquivo_antigo_com_expressao_torta_nao_derruba_a_leitura(
    pasta_de_mentira: Path,
) -> None:
    save_profile(_perfil("jogo", "JogoBom"))
    (pasta_de_mentira / "ruim.json").write_text(
        json.dumps(_json_torto("ruim")), encoding="utf-8"
    )
    nomes = [p.name for p in load_all_profiles()]
    assert "jogo" in nomes
    assert "ruim" not in nomes


def test_o_criterio_ja_construido_com_expressao_torta_nao_casa_e_nao_levanta() -> None:
    criterio = MatchCriteria.model_construct(
        type="criteria", window_class=[], window_title_regex=EXPRESSAO_TORTA, process_name=[]
    )
    assert criterio.matches({"wm_name": "abc"}) is False


@pytest.mark.asyncio
async def test_a_troca_segue_viva_com_o_criterio_torto_na_lista(
    pasta_de_mentira: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bom = _perfil("jogo", "JogoBom")
    save_profile(bom)
    torto = _perfil("ruim", "x")
    torto.match = MatchCriteria.model_construct(
        type="criteria", window_class=[], window_title_regex=EXPRESSAO_TORTA, process_name=[]
    )
    monkeypatch.setattr(
        loader_module, "_ler_todos_os_perfis", lambda *, copiar: [torto, bom]
    )
    monkeypatch.setattr(loader_module, "_maybe_seed_presets", lambda: None)
    monkeypatch.setattr(loader_module, "_talvez_semear_jogos", lambda: None)

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    comp = AutoSwitcher(
        manager=manager,
        window_reader=lambda: {"wm_class": "JogoBom", "wm_name": "abc"},
        poll_interval_sec=0.02,
        debounce_sec=0.02,
    )
    tarefa = comp.start()
    await asyncio.sleep(0.3)
    assert not tarefa.done()
    comp.stop()
    await tarefa
    assert comp._current_profile == "jogo"


@pytest.mark.asyncio
async def test_o_tique_que_falha_nao_mata_a_tarefa(
    pasta_de_mentira: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    save_profile(_perfil("jogo", "JogoBom"))
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    comp = AutoSwitcher(
        manager=manager,
        window_reader=lambda: {"wm_class": "JogoBom"},
        poll_interval_sec=0.02,
        debounce_sec=0.02,
    )
    original = comp._decidir
    falhas = {"n": 0}

    def decidir_que_falha_tres_vezes(info: dict[str, Any], now: float) -> None:
        if falhas["n"] < 3:
            falhas["n"] += 1
            raise RuntimeError("tique torto")
        original(info, now)

    monkeypatch.setattr(comp, "_decidir", decidir_que_falha_tres_vezes)
    tarefa = comp.start()
    await asyncio.sleep(0.4)
    assert falhas["n"] == 3
    assert not tarefa.done()
    comp.stop()
    await tarefa
    assert comp._current_profile == "jogo"


@pytest.mark.asyncio
async def test_a_morte_da_tarefa_fica_registrada(monkeypatch: pytest.MonkeyPatch) -> None:
    registro: list[tuple[str, dict[str, Any]]] = []

    class _Log:
        def __getattr__(self, nivel: str) -> Any:
            return lambda evento, **kw: registro.append((evento, kw))

    monkeypatch.setattr(autoswitch_mod, "logger", _Log())
    comp = AutoSwitcher(manager=ProfileManager(controller=FakeController()),
                        window_reader=lambda: {})

    async def morre() -> None:
        raise RuntimeError("laço morreu")

    monkeypatch.setattr(comp, "run", morre)
    tarefa = comp.start()
    with pytest.raises(RuntimeError):
        await tarefa
    await asyncio.sleep(0)
    assert any(evento == "autoswitch_task_morreu" for evento, _ in registro)
