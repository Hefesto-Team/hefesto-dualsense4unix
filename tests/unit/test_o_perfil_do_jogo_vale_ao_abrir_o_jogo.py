"""O perfil do jogo vale ao abrir o jogo (O-PERFIL-DO-JOGO-VALE-AO-ABRIR-O-JOGO-01, 14/11/2026).

Duas causas medidas no diário do serviço, e uma régua para cada uma:

* abrir outro jogo e ver o perfil do jogo de antes voltar: o leitor do jogo em cena do autoswitch
  lia o `appid_em_cena` do sinal, que só vê o lançamento novo no tique seguinte do sinal (até
  2 s); nesse intervalo o autoswitch ativava de novo o perfil do jogo de antes (14/11, 04h35, 0,4 s
  depois do `origin=launch`). O jogo do lançamento que trava o pad vale primeiro;
* o controle virar Navegação no meio do jogo: o `jogo.fechou` do jogo armado devolvia o modo do
  computador com outro jogo em cena, o que entrou pela janela sem arme (13/11, 03h39 a 03h44,
  com a autoridade em `game` o tempo todo). A volta espera o jogo em cena sair.

AS MORDIDAS (executadas na implementação, com o md5 conferido na volta):

* o leitor sem a trava do lançamento →
  `test_abrir_a_aplica_a_abrir_b_aplica_b_e_fechar_volta` reprova no B;
* a volta sem a espera do jogo em cena →
  `test_o_jogo_em_cena_segura_o_modo_do_jogo_e_a_volta_vem_quando_ele_sai` reprova nos dois
  modos do computador.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.core.events import EventTopic
from hefesto_dualsense4unix.daemon import launch_env as le
from hefesto_dualsense4unix.daemon import lifecycle
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import autoswitch as sub
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    Profile,
    ProfileModeConfig,
)
from hefesto_dualsense4unix.testing import FakeController
from tests.unit.test_a_mascara_do_cartao_vale_com_o_vpad_de_pe import PERFIL, _ensaio
from tests.unit.test_o_default_env_e_o_modo_do_computador import (
    _armar,
    _NaNavegacao,
    _o_jogo_em_xbox,
    _todos,
)
from tests.unit.test_o_jogo_so_nasce_com_o_ambiente_do_proprio_arme import APPID

__all__ = ["_ensaio"]

JOGO_A, JOGO_B = 9951101, 9951202
NAVEGACAO = "Navegação"


@pytest.fixture
def perfis_isolados(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    alvo = tmp_path / "profiles"
    alvo.mkdir()
    monkeypatch.setattr(loader_module, "profiles_dir", lambda ensure=False: alvo)
    return alvo


def _do_jogo(nome: str, appid: int, flavor: str) -> Profile:
    return Profile(
        name=nome, match=MatchCriteria(window_class=[f"steam_app_{appid}"]), priority=80,
        mode=ProfileModeConfig(kind="gamepad", gamepad_flavor=flavor),
    )


def _a_mesa() -> tuple[ProfileManager, StateStore]:
    for perfil in (
        _do_jogo("Jogo A", JOGO_A, "dualsense"),
        _do_jogo("Jogo B", JOGO_B, "xbox"),
        Profile(name=NAVEGACAO, match=MatchCriteria(window_class=["firefox"]), priority=50,
                mode=ProfileModeConfig(kind="desktop")),
        Profile(name="geral", match=MatchAny(), priority=0),
    ):
        save_profile(perfil)
    fc = FakeController()
    fc.connect()
    store = StateStore()
    return ProfileManager(controller=fc, store=store), store


class _Tique:
    def __init__(self, sw: AutoSwitcher) -> None:
        self.sw, self.t = sw, 0.0

    def ate(self, segundos: float, info: dict[str, Any]) -> None:
        fim = self.t + segundos
        while self.t <= fim:
            self.sw._tick(dict(info), self.t)
            self.t += 0.5


def _abre(manager: ProfileManager, servico: Any, nome: str, appid: int) -> None:
    """O arme do lançamento: ativa o perfil do jogo e trava o pad; o sinal só vê depois."""
    manager.activate(nome, origin="launch")
    servico._pad_travado_pelo_lancamento = (appid, 1)


def test_abrir_a_aplica_a_abrir_b_aplica_b_e_fechar_volta(perfis_isolados: Path) -> None:
    """Dois jogos de mentira e a Navegação, com o leitor do serviço de verdade.

    Entre o arme e o tique seguinte do sinal, o `appid_em_cena` ainda é o do jogo de antes, e a
    janela do jogo novo ainda não se lê: o perfil do jogo novo fica.
    """
    manager, store = _a_mesa()
    servico = SimpleNamespace(appid_em_cena=None, _pad_travado_pelo_lancamento=None)
    sw = AutoSwitcher(
        manager=manager, window_reader=dict, store=store,
        jogo_em_cena_reader=sub._o_jogo_em_cena_do_servico(servico),
        jogo_vivo_reader=lambda: None,
    )
    relogio = _Tique(sw)
    relogio.ate(2.0, {"wm_class": "firefox"})
    assert store.active_profile == NAVEGACAO, "premissa: fora do jogo, a Navegação"

    _abre(manager, servico, "Jogo A", JOGO_A)
    relogio.ate(1.5, {})
    assert store.active_profile == "Jogo A", "abrir A não aplicou A"
    servico.appid_em_cena = JOGO_A
    relogio.ate(3.0, {"wm_class": f"steam_app_{JOGO_A}"})
    relogio.ate(3.0, {})
    assert store.active_profile == "Jogo A"

    _abre(manager, servico, "Jogo B", JOGO_B)
    relogio.ate(1.5, {})
    assert store.active_profile == "Jogo B", (
        "abrir B devolveu o perfil de A: o leitor leu o jogo de antes no sinal atrasado")
    servico.appid_em_cena = JOGO_B
    relogio.ate(3.0, {"wm_class": f"steam_app_{JOGO_B}"})
    assert store.active_profile == "Jogo B"

    servico._pad_travado_pelo_lancamento = None
    servico.appid_em_cena = None
    relogio.ate(15.0, {"wm_class": "firefox"})
    assert store.active_profile == NAVEGACAO, "fechar o jogo não voltou ao perfil de fora"


def test_o_leitor_do_servico_le_a_trava_antes_do_sinal() -> None:
    servico = SimpleNamespace(appid_em_cena=JOGO_A, _pad_travado_pelo_lancamento=(JOGO_B, 7))
    leitor = sub._o_jogo_em_cena_do_servico(servico)
    assert leitor() == JOGO_B
    servico._pad_travado_pelo_lancamento = None
    assert leitor() == JOGO_A
    servico._pad_travado_pelo_lancamento = (True, 7)
    assert leitor() == JOGO_A
    servico.appid_em_cena = None
    servico._pad_travado_pelo_lancamento = ()
    assert leitor() is None


def _na_navegacao(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """O computador na Navegação, P1 a P3 na mesa, o jogo armado em Xbox e aberto."""
    loader_module.save_profile(Profile(name=PERFIL, match=MatchAny()), origem="teste")
    d = _NaNavegacao()
    d.store = SimpleNamespace(active_profile=PERFIL)
    d._coop_manager = CoopManager(d)  # type: ignore[arg-type]
    _armar(tmp_path, monkeypatch, d, "xbox")
    d.display_authority = "game"
    assert d._gamepad_device is not None and d._mouse_device is None, "premissa"
    return d


_COMPUTADORES = {
    "navegacao": (_na_navegacao, lambda d: d._gamepad_device is None
                  and d._mouse_device is not None),
    "dualsense": (_o_jogo_em_xbox, lambda d: [m for m, _ in _todos(d)] == ["dualsense"] * 3),
}


@pytest.mark.parametrize("computador", sorted(_COMPUTADORES))
def test_o_jogo_em_cena_segura_o_modo_do_jogo_e_a_volta_vem_quando_ele_sai(
    computador: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O jogo armado sai de cena para outro jogo, que entrou pela janela: o modo do jogo fica.

    O anunciador do serviço é o de verdade, e é ele quem diz `jogo.fechou`. Quando o jogo em cena
    sai, o modo do computador volta, uma vez, nos três controles.
    """
    montar, voltou = _COMPUTADORES[computador]
    d = montar(tmp_path, monkeypatch)
    no_jogo = [m for m, _ in _todos(d)] if computador == "dualsense" else None
    anunciador = sub.AnunciadorDoJogo(d.bus, d.store, d)
    fechados = d.bus.subscribe(EventTopic.JOGO_FECHOU)
    d.appid_em_cena = APPID
    anunciador.ver()
    lifecycle._soltar_o_pad_do_lancamento(d, lifecycle.MOTIVO_DA_AUTORIDADE)  # type: ignore[arg-type]
    with structlog.testing.capture_logs() as registros:
        d.appid_em_cena = JOGO_B
        anunciador.ver()
        assert fechados.get_nowait()["appid"] == APPID, "premissa: o jogo armado saiu de cena"
        for _ in range(3):
            assert le.o_fim_do_jogo_devolve_o_modo(d) is None
        assert d._gamepad_device is not None, "o modo do computador entrou com outro jogo em cena"
        if no_jogo is not None:
            assert [m for m, _ in _todos(d)] == no_jogo
        assert not [r for r in registros if r["event"] == "modo_do_computador_devolvido"]

        d.appid_em_cena = None
        d.display_authority = "daemon"
        anunciador.ver()
        for _ in range(3):
            le.o_fim_do_jogo_devolve_o_modo(d)
    assert voltou(d), "o jogo em cena saiu e o modo do computador não voltou"
    voltas = [r for r in registros if r["event"] == "modo_do_computador_devolvido"]
    assert len(voltas) == 1, voltas


def test_a_volta_segue_quando_o_jogo_em_cena_e_o_que_fechou(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O appid em cena que é o do próprio jogo que fechou não segura a volta."""
    d = _na_navegacao(tmp_path, monkeypatch)
    lifecycle._soltar_o_pad_do_lancamento(d, lifecycle.MOTIVO_DA_AUTORIDADE)  # type: ignore[arg-type]
    d.display_authority = "daemon"
    d.appid_em_cena = APPID
    d.bus.publish(EventTopic.JOGO_FECHOU, {"appid": APPID, "t": 0.0})
    assert le.o_fim_do_jogo_devolve_o_modo(d) is not None
    assert d._gamepad_device is None and d._mouse_device is not None
