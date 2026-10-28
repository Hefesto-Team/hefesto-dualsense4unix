"""A-JOGAR-SEM-EXTERNO-NAO-DEIXA-FAIXA-VAZIA-01 (21/10/2026), medida no WebKit (`WebKit2`).

Sob os cartões da Jogar sobrava uma faixa vazia com uma linha: era a `.faixa-final` da pendência,
que saiu da Jogar com o cartão velho em 28/10. O externo virou mais uma linha da seção Controles
(D-2810-O-EXTERNO-ENTRA-NA-SECAO-CONTROLES-DA-JOGAR), depois dos assentos, e o marcador vazio dele
(`.ext-vaga > .nada`) não pode deixar nada sob as linhas. A página é a do desenho (`mockup/`), que
o `--publicar 01` copia byte a byte, pintada com o que o pacote da aba entrega; sem daemon.

A MORDIDA: tire `.quadro.estica .ext-vaga > .nada{display:none}` do CSS da `aba01.py`, regere o
desenho, e o marcador vira um item da coluna das linhas (mais um vão de 6 px sob os assentos).
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

CHEIA = (1920, 1080)

VIVO: dict[str, Any] = {"connected": True, "native_mode": False, "paused": False,
                        "gamepad_emulation": {"enabled": True, "flavor": "dualsense"}}

UM_EXTERNO: dict[str, Any] = {"name": "8BitDo Pro 2", "vid": "2dc8", "pid": "6003",
                              "bus": "usb", "uniq": "aa:bb:cc:00:00:e1",
                              "driver": "hid-generic", "player_slot": 3}

MEDIR = r"""
(function(){
  const A = __A__;
  document.querySelector('.ext-vaga').innerHTML = A.externos;
  const vis = el => { const cs = getComputedStyle(el), r = el.getBoundingClientRect();
    return cs.display !== 'none' && cs.visibility !== 'hidden' && r.width > 0 && r.height > 0; };
  const corpo = document.querySelector('.quadro.estica > .quadro-corpo');
  const linhas = [...corpo.querySelectorAll('.ctl[data-controle], .ext-cartao')].filter(vis);
  const fundo = Math.max(...linhas.map(c => c.getBoundingClientRect().bottom));
  const qr = corpo.getBoundingClientRect();
  const abaixo = [...corpo.querySelectorAll('*')].filter(el => {
    if (!vis(el) || el.closest('.ctl[data-controle], .ext-cartao')) return false;
    const r = el.getBoundingClientRect();
    return r.top >= fundo - 0.5 && r.top < qr.bottom;
  }).map(el => el.className || el.tagName);
  const ext = [...corpo.querySelectorAll('.ext-cartao')].filter(vis);
  const derradeira = linhas[linhas.length - 1];
  return JSON.stringify({
    linhas: linhas.length, abaixo: abaixo,
    a_ultima_e_o_externo: !!derradeira && derradeira.classList.contains('ext-cartao'),
    altura_do_externo: ext.length ? ext[0].getBoundingClientRect().height : 0,
    altura_da_vaga: corpo.querySelector('.ctl.off')
      ? corpo.querySelector('.ctl.off').getBoundingClientRect().height : 0,
    rolagem: corpo.scrollHeight - corpo.clientHeight,
    externos: ext.map(e => (e.innerText || '').replace(/\s+/g, ' ').trim()),
    pendente: !!document.querySelector('[data-campo="pendente"], .faixa-final'),
    itens_da_vaga: [...document.querySelectorAll('.ext-vaga > :not(.ext-cartao)')]
      .filter(el => getComputedStyle(el).display !== 'none').map(el => el.tagName),
  });
})()
"""


def _externos(*externos: dict[str, Any]) -> str:
    ctx = Contexto(state=dict(VIVO), mesa=[], conectados=[], externos=list(externos))
    return str(jogar.pacote(ctx)["externos"])


def _medir(tamanho: tuple[int, int], externos: str) -> dict[str, Any]:
    uri = onde.pagina("01-jogar.html").as_uri()
    js = MEDIR.replace("__A__", json.dumps({"externos": externos}))
    lido: dict[str, Any] = _no_webkit(uri, tamanho, [js])[0]
    return lido


@pytest.mark.parametrize("tamanho", TAMANHOS, ids=lambda t: f"{t[0]}x{t[1]}")
def test_sem_externo_nada_fica_sob_as_linhas_dos_controles(tamanho: tuple[int, int]) -> None:
    """A prova da D-2110-A-FAIXA-SEM-PENDENCIA-SAI-INTEIRA, na seção Controles."""
    lido = _medir(tamanho, _externos())
    assert lido["linhas"] >= 1, lido
    assert lido["abaixo"] == [], f"sob as linhas ficou algo: {lido['abaixo']}"
    assert not lido["externos"] and not lido["pendente"], lido
    assert lido["itens_da_vaga"] == [], (
        f"a vaga vazia pôs {lido['itens_da_vaga']} na coluna das linhas: cada item soma um vão")
    if tamanho == CHEIA:
        assert lido["rolagem"] <= 0, f"a seção rolou {lido['rolagem']} px sem externo"


@pytest.mark.parametrize("tamanho", TAMANHOS, ids=lambda t: f"{t[0]}x{t[1]}")
def test_o_externo_e_a_ultima_linha_e_nada_fica_sob_ele(tamanho: tuple[int, int]) -> None:
    """O externo vem depois dos assentos, na altura da linha fechada, sem rolagem na seção."""
    lido = _medir(tamanho, _externos(UM_EXTERNO))
    assert lido["externos"] and lido["externos"][0].startswith("Controle 3"), lido
    assert lido["a_ultima_e_o_externo"], lido
    assert lido["altura_do_externo"] == lido["altura_da_vaga"], lido
    assert lido["abaixo"] == [], lido
    if tamanho == CHEIA:
        assert lido["rolagem"] <= 0, f"a seção rolou {lido['rolagem']} px com o externo"
