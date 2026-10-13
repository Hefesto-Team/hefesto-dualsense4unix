"""O gatilho que o controle não aceita não derruba o perfil.

O-GATILHO-QUE-O-CONTROLE-NAO-ACEITA-NAO-DERRUBA-O-PERFIL-01 (09/10/2026). O ``TriggerConfig``
conferia o nome do modo e o tipo dos parâmetros, mas não a aridade nem a faixa, que só o
``build_from_name`` conhece. Um perfil escrito à mão, de outra versão ou importado passava pelo
esquema e explodia na ativação: a luz, o som, o teclado e o modo também não chegavam, e o
autoswitch repetia a tentativa a cada ``poll`` com a janela do jogo em foco.

A cura mora no ``TriggerConfig``: o lado que o ``build_from_name`` não monta carrega como
``Off``, o motivo fica num atributo privado (não vai ao disco), e a ativação o leva ao relatório.

TUDO É DE MENTIRA: perfis num diretório de ``tmp_path``, ``FakeController``; nada chega a daemon
nem ao aparelho.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core.controller import OutputSpec
from hefesto_dualsense4unix.core.trigger_effects import build_from_name
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import autoswitch as autoswitch_mod
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
from hefesto_dualsense4unix.profiles.loader import load_all_profiles
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import TriggerConfig
from hefesto_dualsense4unix.testing.fake_controller import FakeController

#: Os três perfis medidos em 09/10: o lado esquerdo que o controle não aceita.
RECUSADOS: dict[str, dict[str, Any]] = {
    "RigidoUm": {"mode": "Rigid", "params": [5]},
    "RigidoAlto": {"mode": "Rigid", "params": [300, 300]},
    "Pulso": {"mode": "Pulse", "params": [999]},
}
BOM = {"mode": "Rigid", "params": [5, 200]}
COR = [10, 20, 30]
#: A forma que o perfil e o daemon usam por dentro (o esquema tira os `:`); faixa forjada.
P1 = "aabbcc000001"


class ControleQueGuardaACamada(FakeController):
    """O ``FakeController`` que lembra o que a camada por controle recebeu."""

    def __init__(self) -> None:
        super().__init__()
        self.por_controle: dict[str, OutputSpec] = {}

    def apply_output_for(self, uniq: str, spec: OutputSpec) -> Any:
        self.por_controle[uniq] = spec
        return "registrado"


@pytest.fixture
def perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _dir(ensure: bool = False) -> Path:
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", _dir)
    return alvo


def _escrever(pasta: Path, nome: str, esquerdo: dict[str, Any], *, por_controle: bool) -> None:
    """O perfil escrito à mão, direto no disco: não passa pelo esquema ao ser gravado."""
    gatilhos = {"left": esquerdo, "right": BOM}
    cru: dict[str, Any] = {
        "name": nome,
        "version": 1,
        "match": {"type": "criteria", "window_class": [f"{nome}_class"]},
        "priority": 10,
        "leds": {"lightbar": COR},
    }
    if por_controle:
        cru["controllers"] = {P1: {"triggers": gatilhos}}
    else:
        cru["triggers"] = gatilhos
    (pasta / f"{nome.lower()}.json").write_text(json.dumps(cru), encoding="utf-8")


def _gatilhos_do_global(fc: FakeController) -> dict[str, Any]:
    return {
        c.payload[0]: c.payload[1] for c in fc.commands if c.kind == "set_trigger"
    }


@pytest.mark.parametrize("nome", sorted(RECUSADOS))
def test_o_esquema_carrega_o_lado_que_nao_monta_como_off(nome: str) -> None:
    tc = TriggerConfig.model_validate(RECUSADOS[nome])
    assert (tc.mode, tc.params) == ("Off", [])
    build_from_name(tc.mode, tc.params)
    assert tc.motivo_da_recusa is not None
    assert RECUSADOS[nome]["mode"] in tc.motivo_da_recusa


def test_o_motivo_nao_vai_ao_disco() -> None:
    tc = TriggerConfig.model_validate(RECUSADOS["RigidoUm"])
    assert tc.model_dump() == {"mode": "Off", "params": []}
    assert "motivo" not in tc.model_dump_json()


def test_o_gatilho_que_monta_fica_como_esta() -> None:
    tc = TriggerConfig.model_validate(BOM)
    assert (tc.mode, tc.params) == ("Rigid", [5, 200])
    assert tc.motivo_da_recusa is None


@pytest.mark.parametrize("nome", sorted(RECUSADOS))
def test_o_perfil_global_ativa_com_o_lado_recusado_desligado(perfis: Path, nome: str) -> None:
    _escrever(perfis, nome, RECUSADOS[nome], por_controle=False)
    assert nome in {p.name for p in load_all_profiles()}
    fc = FakeController()
    fc.connect()
    store = StateStore()
    gerente = ProfileManager(controller=fc, store=store)
    relatorio: dict[str, str] = {}

    gerente.activate(nome, relatorio=relatorio)

    assert store.active_profile == nome
    lados = _gatilhos_do_global(fc)
    assert lados["left"] == build_from_name("Off", [])
    assert lados["right"] == build_from_name(BOM["mode"], BOM["params"])
    assert fc.last_led is not None and fc.last_led.color == tuple(COR)
    assert relatorio["trigger"].startswith("recusado")
    assert "esquerdo" in relatorio["trigger"]
    assert RECUSADOS[nome]["mode"] in relatorio["trigger"]


@pytest.mark.parametrize("nome", sorted(RECUSADOS))
def test_o_perfil_por_controle_ativa_com_o_lado_recusado_desligado(
    perfis: Path, nome: str
) -> None:
    _escrever(perfis, nome, RECUSADOS[nome], por_controle=True)
    fc = ControleQueGuardaACamada()
    fc.connect()
    store = StateStore()
    gerente = ProfileManager(controller=fc, store=store)
    relatorio: dict[str, str] = {}

    gerente.activate(nome, relatorio=relatorio)

    assert store.active_profile == nome
    spec = fc.por_controle[P1]
    assert spec.trigger_left == build_from_name("Off", [])
    assert spec.trigger_right == build_from_name(BOM["mode"], BOM["params"])
    assert fc.last_led is not None and fc.last_led.color == tuple(COR)
    assert relatorio["trigger"].startswith("recusado")
    assert P1 in relatorio["trigger"]
    assert RECUSADOS[nome]["mode"] in relatorio["trigger"]


def test_o_perfil_bom_nao_relata_recusa(perfis: Path) -> None:
    _escrever(perfis, "Bom", BOM, por_controle=False)
    fc = FakeController()
    fc.connect()
    relatorio: dict[str, str] = {}
    ProfileManager(controller=fc, store=StateStore()).activate("Bom", relatorio=relatorio)
    assert not relatorio["trigger"].startswith("recusado")


def test_o_autoswitch_ativa_uma_vez_com_a_janela_parada(
    perfis: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cinco tiques com a janela do jogo em foco: uma ativação, nenhuma falha."""
    _escrever(perfis, "RigidoUm", RECUSADOS["RigidoUm"], por_controle=False)
    log = MagicMock()
    monkeypatch.setattr(autoswitch_mod, "logger", log)
    fc = FakeController()
    fc.connect()
    store = StateStore()
    gerente = ProfileManager(controller=fc, store=store)
    ativacoes: list[str] = []
    ativar_de_verdade = gerente.activate

    def _contar(nome: str, **kw: Any) -> Any:
        ativacoes.append(nome)
        return ativar_de_verdade(nome, **kw)

    monkeypatch.setattr(gerente, "activate", _contar)
    janela = {"wm_class": "RigidoUm_class", "wm_name": "O jogo", "exe_basename": "jogo"}
    sw = AutoSwitcher(
        manager=gerente, window_reader=lambda: dict(janela), store=store, debounce_sec=0.0
    )
    for tique in range(5):
        sw._tick(dict(janela), 10.0 + tique * 0.5)

    assert ativacoes == ["RigidoUm"]
    falhas = [c for c in log.warning.call_args_list if c[0][0] == "autoswitch_activate_failed"]
    assert falhas == []
    assert store.active_profile == "RigidoUm"


@pytest.mark.parametrize("por_controle", [False, True], ids=["global", "por-controle"])
def test_com_o_padrao_do_computador_o_relatorio_ainda_nomeia_o_recusado(
    perfis: Path, por_controle: bool
) -> None:
    """Com o padrão do computador declarado, a vista é revalidada e perde o motivo privado.

    A ativação colhe os recusados do perfil carregado, não da vista: sem isso, quem tem um
    padrão do computador (o caso comum) veria «gatilhos» aplicados com o lado desligado.
    """
    from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc
    from hefesto_dualsense4unix.profiles.loader import load_profile
    from hefesto_dualsense4unix.utils import maquina

    assert maquina.gravar_o_computador({"global": {"mouse": {"speed": 9}}})
    _escrever(perfis, "RigidoUm", RECUSADOS["RigidoUm"], por_controle=por_controle)
    vista = opc.o_que_vale(load_profile("RigidoUm"))
    lado = (vista.controllers[P1].triggers if por_controle else vista.triggers).left
    assert lado.mode == "Off" and lado.motivo_da_recusa is None, "a vista não foi revalidada"

    fc = ControleQueGuardaACamada() if por_controle else FakeController()
    fc.connect()
    store = StateStore()
    relatorio: dict[str, str] = {}
    ProfileManager(controller=fc, store=store).activate("RigidoUm", relatorio=relatorio)

    assert store.active_profile == "RigidoUm"
    assert relatorio["trigger"].startswith("recusado")
    assert "Rigid" in relatorio["trigger"]
