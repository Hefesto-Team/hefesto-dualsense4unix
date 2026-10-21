"""A-JOGAR-SEM-EXTERNO-NAO-DEIXA-FAIXA-VAZIA-01 (21/10/2026), medida no WebKit (`WebKit2`).

Sob os cartões da Jogar sobrava uma faixa vazia com uma linha: era a `.faixa-final` da pendência,
que sem `.ha` escondia só a frase (`visibility`) e guardava a divisória e 37 px. O marcador dos
externos (`.ext-vaga > .nada`) já tinha altura zero. A página é a do desenho (`mockup/`),
pintada com o que o pacote da aba entrega; nada fala com daemon.

A MORDIDA: devolva `.faixa-final:not(.ha) .pendente{visibility:hidden}` no lugar da regra nova
(`aba01.py`), regere o desenho, e as duas larguras reprovam com a faixa de pé.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("abre a página num WebKit")

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from pacotes import Contexto
from pacotes import a01_jogar as jogar

from hefesto_dualsense4unix.interface import onde
from tests.unit.test_as_telas_de_16_10_no_webkit import _no_webkit

TAMANHOS = [(1212, 809), (1920, 1080)]

VIVO: dict[str, Any] = {"connected": True, "native_mode": False, "paused": False,
                        "gamepad_emulation": {"enabled": True, "flavor": "dualsense"}}

#: Um externo de faixa forjada, com o número 3 do co-op (dois DualSense na mesa).
UM_EXTERNO: dict[str, Any] = {"name": "8BitDo Pro 2", "vid": "2dc8", "pid": "6003",
                              "bus": "usb", "uniq": "aa:bb:cc:00:00:e1",
                              "driver": "hid-generic", "player_slot": 3}

#: Pinta como o piloto (frase, classe `ha`, o HTML dos externos) e lê o que fica sob os cartões.
MEDIR = r"""
(function(){
  const A = __A__;
  const faixa = document.querySelector('.faixa-final');
  document.querySelector('[data-campo="pendente"]').textContent = A.frase || '—';
  faixa.classList.toggle('ha', !!A.frase);
  document.querySelector('.ext-vaga').innerHTML = A.externos;
  const vis = el => { const cs = getComputedStyle(el), r = el.getBoundingClientRect();
    return cs.display !== 'none' && cs.visibility !== 'hidden' && r.width > 0 && r.height > 0; };
  const pecas = document.querySelector('.pecas[data-lista="cartoes"]');
  const quadro = pecas.closest('.quadro') || pecas.parentElement.parentElement;
  const cartoes = [...pecas.querySelectorAll('.cartao[data-controle], .ext-cartao')].filter(vis);
  const fundo = Math.max(...cartoes.map(c => c.getBoundingClientRect().bottom));
  const qr = quadro.getBoundingClientRect();
  const abaixo = [...quadro.querySelectorAll('*')].filter(el => {
    if (!vis(el) || el.closest('.cartao[data-controle], .ext-cartao')) return false;
    const r = el.getBoundingClientRect();
    return r.top >= fundo - 0.5 && r.top < qr.bottom;
  }).map(el => el.className || el.tagName);
  const ext = [...pecas.querySelectorAll('.ext-cartao')].filter(vis);
  return JSON.stringify({
    cartoes: cartoes.length, abaixo: abaixo,
    faixa_visivel: vis(faixa), faixa_borda: getComputedStyle(faixa).borderTopWidth,
    externos: ext.map(e => (e.innerText || '').replace(/\s+/g, ' ').trim()),
  });
})()
"""


def _externos(*externos: dict[str, Any]) -> str:
    ctx = Contexto(state=dict(VIVO), mesa=[], conectados=[], externos=list(externos))
    return str(jogar.pacote(ctx)["externos"])


def _medir(tamanho: tuple[int, int], frase: str, externos: str) -> dict[str, Any]:
    uri = onde.pagina("01-jogar.html", publicado=False).as_uri()
    js = MEDIR.replace("__A__", json.dumps({"frase": frase, "externos": externos}))
    lido: dict[str, Any] = _no_webkit(uri, tamanho, [js])[0]
    return lido


@pytest.mark.parametrize("tamanho", TAMANHOS, ids=lambda t: f"{t[0]}x{t[1]}")
def test_sem_externo_e_sem_pendencia_nada_fica_sob_os_cartoes(tamanho: tuple[int, int]) -> None:
    """A prova da D-2110-A-FAIXA-SEM-PENDENCIA-SAI-INTEIRA."""
    lido = _medir(tamanho, "", _externos())
    assert lido["cartoes"] >= 1, lido
    assert not lido["faixa_visivel"] and lido["abaixo"] == [], (
        f"sob os cartões ficou uma faixa vazia: {lido['abaixo']}")


@pytest.mark.parametrize("tamanho", TAMANHOS[:1], ids=lambda t: f"{t[0]}x{t[1]}")
def test_o_externo_numerado_aparece_e_nada_fica_sob_ele(tamanho: tuple[int, int]) -> None:
    lido = _medir(tamanho, "", _externos(UM_EXTERNO))
    assert lido["externos"] and lido["externos"][0].startswith("Controle 3"), lido
    assert lido["abaixo"] == [], lido


@pytest.mark.parametrize("tamanho", TAMANHOS[:1], ids=lambda t: f"{t[0]}x{t[1]}")
def test_a_pendencia_ainda_acende_a_faixa_com_a_linha(tamanho: tuple[int, int]) -> None:
    from hefesto_dualsense4unix.app.actions.relancar import texto_do_pendente

    lido = _medir(tamanho, texto_do_pendente(mascara="Xbox"), _externos())
    assert lido["faixa_visivel"] and lido["faixa_borda"] == "1px", lido
