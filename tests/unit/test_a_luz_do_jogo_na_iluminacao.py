#!/usr/bin/env python3
"""A aba Iluminação diz de quem é a luz agora: «o jogo pinta por cima; sem jogo, a sua cor».

O-DESLIGADO-DEIXA-O-JOGO-DECIDIR-01, item 3 (decisão dela de 04/10/2026): a regra já valia no
produto, e a tela só não a dizia. Uma linha curta embaixo das cores, sem botão novo; com o jogo
pintando a barra de algum controle, a linha ganha «Agora: a cor do jogo» (e «no P2» se for só
parte dos controles). O sinal vem do daemon (`luz_do_jogo` no `state_full`), nunca da cor lida.

AS RÉGUAS: o backend só diz «sim» com a cor do jogo na camada (e deixa de dizer no fim da
sessão); o IPC publica sempre o campo; o pacote escreve a frase certa para cada situação e só a
emite quando a página publicada tem onde pousar; o desenho tem a linha, fora da régua das colunas.
"""
from __future__ import annotations

import pathlib
import sys
from types import SimpleNamespace

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(RAIZ / "src"), str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

MAC_1 = "AA:BB:CC:00:00:01"


def _backend() -> bp.PyDualSenseController:
    ctl = bp.PyDualSenseController()
    ctl._handles = {MAC_1: SimpleNamespace()}
    return ctl


class TestOBackendDiz:
    def test_sem_a_camada_do_jogo_a_luz_e_do_perfil(self) -> None:
        assert _backend().luz_do_jogo_para(MAC_1) is False

    def test_com_a_cor_do_jogo_na_camada_a_luz_e_do_jogo(self) -> None:
        ctl = _backend()
        ctl._game_output_by_uniq["aabbcc000001"] = bp._DesiredOutput(led=(0, 255, 0))
        assert ctl.luz_do_jogo_para(MAC_1) is True

    def test_camada_so_com_o_numero_nao_e_luz_do_jogo(self) -> None:
        ctl = _backend()
        ctl._game_output_by_uniq["aabbcc000001"] = bp._DesiredOutput(
            player_leds=(True, False, False, False, False))
        assert ctl.luz_do_jogo_para(MAC_1) is False

    def test_controle_desconhecido_nao_e_luz_do_jogo(self) -> None:
        assert _backend().luz_do_jogo_para("AA:BB:CC:00:00:09") is False


class TestOIpcPublica:
    @staticmethod
    def _leitura(controller: object, uniq: str | None) -> bool:
        return IpcHandlersMixin._luz_do_jogo(SimpleNamespace(controller=controller), uniq)

    def test_so_o_true_exato_vale(self) -> None:
        sim = SimpleNamespace(luz_do_jogo_para=lambda _u: True)
        talvez = SimpleNamespace(luz_do_jogo_para=lambda _u: "sim")
        assert self._leitura(sim, "x") is True
        assert self._leitura(talvez, "x") is False

    def test_backend_sem_a_leitura_ou_que_quebra_diz_nao(self) -> None:
        def quebra(_u: str) -> bool:
            raise RuntimeError("sem aparelho")

        assert self._leitura(SimpleNamespace(), "x") is False
        assert self._leitura(SimpleNamespace(luz_do_jogo_para=quebra), "x") is False
        assert self._leitura(SimpleNamespace(luz_do_jogo_para=lambda _u: True), None) is False


MESA = [
    {"pref": "p1", "uniq": "aa:bb:cc:00:00:01", "jogador": 1, "cor": "cosmic-red",
     "nome": "Cosmic Red", "via": "BT", "transporte": "bt"},
    {"pref": "p2", "uniq": "aa:bb:cc:00:00:02", "jogador": 2, "cor": "starlight-blue",
     "nome": "Starlight Blue", "via": "USB", "transporte": "usb"},
]


def _ctl(n: int, jogo: bool) -> dict:
    return {"uniq": f"aa:bb:cc:00:00:0{n}", "transport": "bt", "connected": True,
            "player": n, "player_slot": n, "is_primary": n == 1,
            "lightbar_rgb": [0, 0, 255], "lightbar_on": True,
            "lightbar_source": "sysfs", "battery_pct": 85, "luz_do_jogo": jogo}


@pytest.fixture
def com_a_linha_na_pagina(monkeypatch: pytest.MonkeyPatch):
    from pacotes import a04_iluminacao as a04

    monkeypatch.setattr(a04, "_TEM_A_LINHA_DA_LUZ", True)
    return a04


def _topo(conectados: list[dict]) -> dict:
    import pacotes

    ctx = pacotes.Contexto(state={"active_profile": ""}, mesa=MESA, conectados=conectados,
                           estados={})
    return pacotes.pacote_da_pagina("04-iluminacao.html", ctx)


class TestAFraseDaLinha:
    def test_ninguem_pintando_so_a_regra(self, com_a_linha_na_pagina) -> None:
        topo = _topo([_ctl(1, False), _ctl(2, False)])
        frase = topo[com_a_linha_na_pagina.ENDERECO_DA_LUZ_DO_JOGO]
        assert frase == "O jogo pinta por cima; sem jogo, a sua cor."

    def test_todos_pintando_diz_agora_a_cor_do_jogo(self, com_a_linha_na_pagina) -> None:
        topo = _topo([_ctl(1, True), _ctl(2, True)])
        frase = topo[com_a_linha_na_pagina.ENDERECO_DA_LUZ_DO_JOGO]
        assert "Agora: a cor do jogo" in frase and " no " not in frase.split("Agora")[1]

    def test_so_um_pintando_diz_qual(self, com_a_linha_na_pagina) -> None:
        topo = _topo([_ctl(1, False), _ctl(2, True)])
        frase = topo[com_a_linha_na_pagina.ENDERECO_DA_LUZ_DO_JOGO]
        assert frase.endswith("<b>Agora: a cor do jogo no P2</b>"), frase

    def test_a_frase_nunca_e_vermelha_nem_pede_clique(self, com_a_linha_na_pagina) -> None:
        for estado in (False, True):
            frase = _topo([_ctl(1, estado)])[com_a_linha_na_pagina.ENDERECO_DA_LUZ_DO_JOGO]
            assert "button" not in frase and "color" not in frase

    def test_antes_do_publicar_o_campo_nao_sai(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from pacotes import a04_iluminacao as a04

        monkeypatch.setattr(a04, "_TEM_A_LINHA_DA_LUZ", False)
        assert a04.ENDERECO_DA_LUZ_DO_JOGO not in _topo([_ctl(1, True)])


class TestODesenho:
    def test_o_desenho_tem_a_linha_uma_vez_e_fora_das_colunas(self) -> None:
        html = (RAIZ / "mockup" / "04-iluminacao.html").read_text(encoding="utf-8")
        assert html.count('data-campo="luz-do-jogo"') == 1
        assert "O jogo pinta por cima; sem jogo, a sua cor." in html
        grade, resto = html.split('<div class="luz-do-jogo"', 1)
        assert "luz-grade" in grade and grade.rstrip().endswith("-->")
        assert "<button" not in resto.split("</div>", 1)[0]


class TestATelaPintaAFrase:
    """No WebKit de verdade: o piloto escreve a frase no lugar dela, e o «Agora» aparece."""

    def test_o_pintor_escreve_a_regra_e_depois_o_agora(self, monkeypatch) -> None:
        import json

        from pacotes import a04_iluminacao as a04
        from tests.unit import test_o_padrao_trava_as_barras_da_vibracao as base

        monkeypatch.setattr(base, "PAGINA", "04-iluminacao.html")
        ler = ("JSON.stringify({t: document.querySelector('[data-campo=\"luz-do-jogo\"]')"
               ".textContent.trim(), b: document.querySelectorAll("
               "'[data-campo=\"luz-do-jogo\"] b').length})")

        def pintar(frase: str) -> str:
            return "window.__hef.pintar(" + json.dumps(
                {"colunas": {}, "mesa": {a04.ENDERECO_DA_LUZ_DO_JOGO: frase}}) + ")"

        a_regra = a04.frase_da_luz_do_jogo([], 2)
        agora = a04.frase_da_luz_do_jogo([2], 2)
        r = base._na_pagina([ler, pintar(agora), ler, pintar(a_regra), ler])
        assert r[0] == {"t": a04.FRASE_DA_LUZ_DO_JOGO, "b": 0}
        assert r[2]["t"].endswith("Agora: a cor do jogo no P2")
        assert r[2]["b"] == 1
        assert r[4] == {"t": a04.FRASE_DA_LUZ_DO_JOGO, "b": 0}
