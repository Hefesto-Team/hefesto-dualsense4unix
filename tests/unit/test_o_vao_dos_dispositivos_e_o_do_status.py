#!/usr/bin/env python3
"""A JOGAR: o vão entre o topo de «Dispositivos conectados» e as abas é o do Status.

Pedido, 29/10/2026: a distância entre o título «Dispositivos conectados» e a lista
é a mesma entre a linha do Status e os botões de modo. Medido no Chrome, a 1212x809, com
a mesa cheia, com o Hefesto desligado e com os quatro lugares vazios, no desenho e na
página publicada. A mordida: o `padding-top` de `.miolo > .quadro.estica > .quadro-corpo`
em `aba01.CSS_DAS_ABAS` de volta a 6px reprova os três estados.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE), str(RAIZ / "scripts")):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import chrome_sem_rede

CHROME = pathlib.Path("/usr/bin/google-chrome")

MEDIR = r"""
(estado) => {
  if (estado === 'desligado') document.getElementById('hef-desligado').click();
  if (estado === 'vazio') {
    document.querySelectorAll('[data-controle]').forEach(e => {
      e.dataset.conectado = 'nao'; e.classList.add('off'); });
  }
  const vis = (e) => e.getClientRects().length && getComputedStyle(e).display !== 'none'
    && getComputedStyle(e).visibility !== 'hidden';
  const q1 = document.querySelector('.quadro.hef-q');
  const topo1 = q1.querySelector('.quadro-topo').getBoundingClientRect().bottom;
  const modos = [...q1.querySelectorAll('.degrau')].filter(vis)
    .map(e => e.getBoundingClientRect().top);
  const q2 = document.querySelector('.quadro.estica');
  const topo2 = q2.querySelector('.quadro-topo').getBoundingClientRect().bottom;
  const abas = [...q2.querySelectorAll('.aba-ctl')].filter(vis)
    .map(e => e.getBoundingClientRect().top);
  return {status: modos.length ? Math.min(...modos) - topo1 : null,
          dispositivos: abas.length ? Math.min(...abas) - topo2 : null,
          abas: abas.length};
}
"""


def _medir(arquivo: pathlib.Path) -> dict:
    from playwright.sync_api import sync_playwright

    saida = {}
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            for estado in ("ligado", "desligado", "vazio"):
                pg, _ = chrome_sem_rede.abrir_sem_rede(
                    navegador, arquivo.as_uri(), largura=1212, altura=809)
                saida[estado] = pg.evaluate(MEDIR, estado)
                pg.close()
        finally:
            navegador.close()
    return saida


@pytest.mark.skipif(not CHROME.exists(), reason="sem o Chrome da casa")
@pytest.mark.parametrize("publicado", [False, True], ids=["desenho", "publicado"])
def test_o_vao_ate_as_abas_e_o_vao_ate_os_modos(publicado, tmp_path):
    import onde

    alvo = tmp_path / "01-jogar.html"
    alvo.write_text(onde.pagina("01-jogar.html", publicado=publicado)
                    .read_text(encoding="utf-8"), encoding="utf-8")
    medido = _medir(alvo)
    for estado, vaos in medido.items():
        assert vaos["abas"] >= 4, (estado, vaos)
        assert vaos["status"] is not None and vaos["status"] > 0, (estado, vaos)
        assert vaos["dispositivos"] == vaos["status"], (estado, vaos)
