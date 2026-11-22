"""O tato só ouve o jogo quando há jogo aberto.

O-TATO-SO-OUVE-O-JOGO-QUANDO-HA-JOGO-ABERTO-01. O ``ouvido_quer`` tomava emprestado o ``ha_jogo``,
que diz «sim» também para a janela do cliente da Steam sem jogo nenhum (D-1510 e D-2010: o toque e
o acionador a contam de propósito); o ouvido gravava o som de um jogo que não existia, ficava
surdo e, aos 30 s, o diário dizia ``tato_ouvido_surdo``. TUDO É DE MENTIRA: o daemon é um dublê com
o ``_janela_de_jogo_em_foco`` de verdade, o ouvido é o real sem a volta em fio e sem gravador, e o
relógio é simulado.

AS MORDIDAS (feitas na sprint, com a cura devolvida e o md5 conferido): o ``ouvido_quer`` com o
``ha_jogo`` de volta reprova o caso da Steam em foco pela frase «a Steam em foco sem jogo ligou o
ouvido do tato»; o ``jogo_do_ouvido`` que aceita o cliente da Steam reprova o mesmo caso e o do
navegador; o ``jogo_por`` fora da linha do aviso reprova o caso da autoridade.
"""
from __future__ import annotations

import types
from types import SimpleNamespace
from typing import Any

import pytest
import structlog.testing

from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.subsystems import diario_do_corpo as dc
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.integrations import jogos_locais
from hefesto_dualsense4unix.integrations import transiente_do_jogo as tj


class _Relogio:
    def __init__(self) -> None:
        self.agora = 100.0

    def __call__(self) -> float:
        return self.agora


class _OuvidoSemVolta(tj.OuvidoDoJogo):
    def comecar(self) -> None:
        return None


class _Mesa:
    def __init__(self, classe: str = "", autoridade: str = "daemon",
                 appid: int | None = None) -> None:
        self.bus = EventBus()
        self.relogio = _Relogio()
        self.daemon: Any = SimpleNamespace(
            bus=self.bus, display_authority=autoridade, appid_em_cena=appid,
            store=SimpleNamespace(active_profile=None, window_detect_current_class=classe),
            controller=None)
        self.daemon._janela_de_jogo_em_foco = types.MethodType(
            Daemon._janela_de_jogo_em_foco, self.daemon)
        self.motor = tv.TatoVivo([])
        self.passo = tv.Passo(self.daemon, self.motor)
        self.ouvido = _OuvidoSemVolta(
            self.passo.ouvido_quer, achar_o_fluxo=lambda: None, relogio=self.relogio)
        self.motor.ouvido = self.ouvido
        self.bus.subscribe(EventTopic.JOGO_SOM)
        self.passo(self.relogio.agora)

    def quarenta_segundos(self) -> list[Any]:
        with structlog.testing.capture_logs() as linhas:
            self.ouvido.uma_volta()
            self.relogio.agora += 40.0
            self.passo(self.relogio.agora)
            self.passo.andar_o_diario(self.relogio.agora)
        return [x for x in linhas if x["event"] == "tato_ouvido_surdo"]


def test_a_steam_em_foco_sem_jogo_nao_liga_o_ouvido_e_o_toque_segue_contando_o_jogo() -> None:
    """D-2211-O-OUVIDO-DO-TATO-SO-LIGA-COM-JOGO-ABERTO."""
    mesa = _Mesa("steam")
    assert tv.ha_jogo(mesa.daemon), "a D-1510 muda: a Steam em foco deixou de contar para o toque"
    assert not mesa.passo.ouvido_quer(), "a Steam em foco sem jogo ligou o ouvido do tato"
    assert mesa.quarenta_segundos() == []
    assert mesa.ouvido.surdo_ha_s() == 0.0


def test_o_cliente_da_steam_pelo_assistente_da_loja_tambem_nao_liga_o_ouvido() -> None:
    mesa = _Mesa("steamwebhelper")
    assert tv.ha_jogo(mesa.daemon)
    assert not mesa.passo.ouvido_quer(), "a Steam em foco sem jogo ligou o ouvido do tato"


def test_o_navegador_em_foco_nao_liga_o_ouvido() -> None:
    mesa = _Mesa("firefox")
    assert not tv.ha_jogo(mesa.daemon)
    assert not mesa.passo.ouvido_quer(), "o navegador em foco ligou o ouvido do tato"


def test_a_janela_do_jogo_da_steam_liga_o_ouvido_com_o_tato_pedindo_o_som() -> None:
    mesa = _Mesa("steam_app_1599660")
    assert mesa.passo.ouvido_quer()
    assert mesa.passo.jogo_por == "janela:steam_app_1599660"


def test_o_jogo_local_do_catalogo_com_a_janela_de_pe_liga_o_ouvido(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(jogos_locais, "jogos_de_janela",
                        lambda *_a, **_k: [SimpleNamespace(chave="Jogo-Local")])
    mesa = _Mesa("jogo-local")
    assert mesa.passo.ouvido_quer()
    assert mesa.passo.jogo_por == "janela:jogo-local"
    fora = _Mesa("outra-janela")
    assert not fora.passo.ouvido_quer()


def test_o_appid_em_cena_liga_o_ouvido() -> None:
    mesa = _Mesa("steam", appid=1599660)
    assert mesa.passo.ouvido_quer()
    assert mesa.passo.jogo_por == "appid"


def test_a_autoridade_game_liga_o_ouvido_e_o_aviso_de_surdez_diz_o_porque() -> None:
    mesa = _Mesa("steam", autoridade="game")
    assert mesa.passo.ouvido_quer()
    surdos = mesa.quarenta_segundos()
    assert len(surdos) == 1 and surdos[0]["log_level"] == "warning"
    assert surdos[0]["jogo_por"] == "autoridade"
    assert surdos[0]["ha_s"] >= dc.PRAZO_DO_SURDO_S


def test_o_jogo_que_fecha_desliga_o_ouvido_no_passo_seguinte() -> None:
    mesa = _Mesa("steam_app_1599660")
    assert mesa.passo.ouvido_quer()
    mesa.daemon.store.window_detect_current_class = "steam"
    mesa.passo(mesa.relogio.agora + 1)
    assert not mesa.passo.ouvido_quer(), "a Steam em foco sem jogo ligou o ouvido do tato"
    assert mesa.passo.jogo_por == ""


def test_o_ouvido_do_jogo_nao_pergunta_a_guarda_do_modo() -> None:
    mesa = _Mesa("steam")

    def nunca() -> bool:
        raise AssertionError("o ouvido perguntou à guarda do modo")

    mesa.daemon._janela_de_jogo_em_foco = nunca
    assert tv.jogo_do_ouvido(mesa.daemon) == ""
