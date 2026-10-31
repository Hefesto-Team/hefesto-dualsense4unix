"""O-TIQUE-VIVO-NAO-MUDA-A-ALTURA-DO-CARTAO-01 — o cartão aberto da Jogar não muda com o tique.

Medido em 31/10/2026 no piloto em lar de mentira (1222 px): o cartão ia de 264,27 a 260,07 px no
primeiro tique vivo e voltava a 264,27 no seguinte. O selo do canal do alto-falante nasce vazio
(o canal ainda não foi lido), e o rótulo «Alto-falante», sem altura própria, encolhia com ele;
o piso de 12 px da folha da casa (a56c29515) fez o selo passar da linha do texto.

A RÉGUA: no WebKit, com o BOOTSTRAP do piloto, o tique pinta em sequência os estados que o
rótulo pode mostrar (sem leitura, ATIVO, DESLIGADO com «Saída muda», o traço) nos dois
transportes, e a altura do cartão e a de cada `.rot-linha` não mudam, e o conteúdo cabe na
linha, em três larguras: a menor é a vista do desenho, que `tamanho_que_cabe` garante em pixels
de CSS. A folha do piso da página aberta é trocada pela de `folha_da_casa.py` de agora, para a
régua medir a origem e não a cópia gerada no mockup.
"""
from __future__ import annotations

import copy
import json
import os
import pathlib
import re
import sys
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import pacotes  # isort:skip
from hefesto_dualsense4unix.interface import hefesto_vivo, mesa_viva, onde
from hefesto_dualsense4unix.interface.folha_da_casa import (
    ALVO_MINIMO_PX,
    ID_DA_FOLHA_DO_PISO,
    PISO_POR_PAGINA,
    VISTA_DO_DESENHO,
)
from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

from tests.conftest import skip_sem_gi_real

RAIZ = pathlib.Path(__file__).resolve().parents[2]

JOGAR = onde.ENSAIO / "01-jogar.html"

LARGURAS = (VISTA_DO_DESENHO[0], 1500, 1918)

MEDIR = r"""
(function(){
  var c = document.querySelector('.quadro-corpo > .ctl:has(> input:checked)');
  var linhas = [].map.call(c.querySelectorAll('.rot-linha'), function(r){
    var b = r.getBoundingClientRect(), sobra = 0;
    r.querySelectorAll('*').forEach(function(e){
      var q = e.getBoundingClientRect();
      if (q.height > 0) sobra = Math.max(sobra, q.bottom - b.bottom, b.top - q.top);
    });
    return [r.firstChild.textContent.trim(), b.height, sobra];
  });
  return JSON.stringify({alto: c.getBoundingClientRect().height, linhas: linhas});
})()
"""


def _bootstrap() -> str:
    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py").read_text(
        encoding="utf-8")
    m = re.search(r'BOOTSTRAP = r"""(.*?)"""', fonte, re.S)
    assert m, "não achei o BOOTSTRAP no piloto"
    return m.group(1)


def _controle(transporte: str) -> dict[str, Any]:
    return {"uniq": "aa:bb:cc:00:00:01", "connected": True, "player_slot": 1,
            "transport": transporte, "battery_pct": 80,
            "inputs": {"lx": 128, "ly": 128, "rx": 128, "ry": 128, "l2_raw": 0, "r2_raw": 0,
                       "buttons": []},
            "audio": {"mic_mudo": False}, "speaker": {"volume": 102, "muted": False, "rota": 0}}


def _carga(transporte: str) -> dict[str, Any]:
    c = _controle(transporte)
    estado = {"connected": True, "controllers": [c]}
    mesa = mesa_viva.mesa_do_estado(estado, {})
    ctx = pacotes.Contexto(state=estado, mesa=mesa, conectados=[c], estados={})
    carga = pacotes.normalizar(pacotes.pacote_da_pagina(JOGAR.name, ctx) or {},
                               {str(m.get("uniq") or ""): m["pref"] for m in mesa})
    pacotes.apagar_os_lugares_sem_dono(carga, hefesto_vivo._com_dono(ctx), pagina=JOGAR.name)
    carga["alvo"] = "p1"
    return carga


ROTULOS_DO_TIQUE = (
    {"alto-canal": a02.NADA_A_DIZER, "alto-selo": a02.NADA_A_DIZER, "mic-selo": "—"},
    {"alto-canal": mesa_viva.selo_do_alto_falante(False, True), "alto-selo": a02.NADA_A_DIZER},
    {"alto-canal": mesa_viva.selo_do_alto_falante(True, True), "alto-selo": a02.selo_do_som(True)},
    {"alto-canal": mesa_viva.selo_do_alto_falante(False, False), "alto-selo": a02.NADA_A_DIZER},
    {"alto-canal": a02.NADA_A_DIZER, "alto-selo": a02.selo_do_som(True)},
)


@pytest.fixture(scope="module", params=LARGURAS, ids=[f"{w}px" for w in LARGURAS])
def tela(request: pytest.FixtureRequest) -> Any:
    """O mockup da Jogar num WebView oculto, com o BOOTSTRAP do produto, na largura do parâmetro."""
    if not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
        pytest.skip("sem servidor gráfico: rode sob `xvfb-run -a` (pulo não é verde)")
    sys.path.insert(0, str(RAIZ / "scripts"))
    import regua_de_tela

    t = regua_de_tela.Tela(JOGAR, titulo_esperado="Hefesto", largura=request.param, altura=809)
    t.executar(_bootstrap() + ";'ok'")
    trocada = t.executar(
        f"(function(){{var s=document.getElementById({json.dumps(ID_DA_FOLHA_DO_PISO)});"
        f"if(!s)return 'sem';s.textContent={json.dumps(PISO_POR_PAGINA['02-controles'])};"
        "return 'ok';})()")
    assert trocada == "ok", "a página da Jogar perdeu a folha do piso"
    yield t
    t.fechar()


@skip_sem_gi_real
@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_o_cartao_tem_a_mesma_altura_em_todo_tique(tela: Any, transporte: str) -> None:
    """Os rótulos dos quadros mudam a cada tique, e o cartão e as linhas dos rótulos ficam parados.

    Duas voltas pela sequência, com o tempo andando entre os tiques: uma medida de um instante só
    não pega o primeiro tique, que é onde o selo do canal nasce vazio.
    """
    base = _carga(transporte)
    medidas = []
    for volta in range(2):
        for i, rotulos in enumerate(ROTULOS_DO_TIQUE):
            carga = copy.deepcopy(base)
            carga["colunas"]["p1"].update(rotulos)
            tela.executar(
                f"(function(){{window.__hef.pintar({json.dumps(carga)});return 'ok';}})()")
            tela.avancar(0.2)
            medidas.append((volta, i, json.loads(tela.executar(MEDIR))))
    alturas = {round(m["alto"], 2) for _v, _i, m in medidas}
    assert len(alturas) == 1, (
        "o cartão mudou de altura com o tique: "
        + ", ".join(f"volta {v} tique {i}: {m['alto']:.2f}" for v, i, m in medidas))
    for volta, i, m in medidas:
        assert m["linhas"], "o cartão aberto perdeu as linhas dos rótulos"
        for nome, alto, sobra in m["linhas"]:
            assert round(alto, 2) == ALVO_MINIMO_PX, (
                f"volta {volta} tique {i}: a linha «{nome}» tem {alto:.2f} px, "
                f"e a altura fixa é {ALVO_MINIMO_PX}")
            assert sobra <= 0.5, (
                f"volta {volta} tique {i}: o conteúdo da linha «{nome}» passa {sobra:.2f} px "
                "da altura fixa")
