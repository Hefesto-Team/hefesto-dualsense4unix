#!/usr/bin/env python3
"""A JOGAR: o rótulo que o tique escreve no chip «Steam Input» não apaga o desenho da Steam.

Medido em 29/10/2026 no piloto, em lar de mentira: o `blocos:` do chip
(`a01_jogar._o_rotulo_do_chip`) mirava o próprio `[data-gesto="modo-steam"]`, e o piloto troca o
`innerHTML` do alvo; o desenho que o gerador põe no botão sumia no primeiro tique, só nele (o
Nativo e a Navegação não têm `blocos:`). O alvo agora é o rótulo dentro do chip. A régua aplica
o `blocos:` em repouso e o armado como o piloto aplica, no desenho e na página publicada.
A mordida: o seletor de volta ao chip inteiro apaga o desenho, e a régua reprova.
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

from hefesto_dualsense4unix.interface.pacotes import a01_jogar

CHROME = pathlib.Path("/usr/bin/google-chrome")

APLICAR = r"""
([blocos, gesto]) => {
  document.getElementById('hef-desligado').click();
  for (const [seletor, html] of Object.entries(blocos)) {
    const alvo = document.querySelector(seletor);
    if (alvo) alvo.innerHTML = html;
  }
  const chip = document.querySelector(`[data-gesto="${gesto}"]`);
  const svg = chip.querySelector('svg.silhueta');
  const r = svg ? svg.getBoundingClientRect() : null;
  return {texto: chip.textContent.trim(), desenho: r ? [r.width, r.height] : null};
}
"""


def _aplicar(arquivo: pathlib.Path, blocos: dict[str, str]) -> dict:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg, _ = chrome_sem_rede.abrir_sem_rede(
                navegador, arquivo.as_uri(), largura=1212, altura=809)
            return pg.evaluate(APLICAR, [blocos, a01_jogar.GESTO_DO_STEAM_INPUT])
        finally:
            navegador.close()


@pytest.mark.skipif(not CHROME.exists(), reason="sem o Chrome da casa")
@pytest.mark.parametrize("publicado", [False, True], ids=["desenho", "publicado"])
@pytest.mark.parametrize("rotulo", ["Steam Input", a01_jogar.STEAM_INPUT_ARMADO],
                         ids=["repouso", "armado"])
def test_o_blocos_do_chip_troca_o_rotulo_e_o_desenho_fica(publicado, rotulo, tmp_path):
    import onde

    alvo = tmp_path / "01-jogar.html"
    alvo.write_text(onde.pagina("01-jogar.html", publicado=publicado)
                    .read_text(encoding="utf-8"), encoding="utf-8")
    blocos = {a01_jogar.SELETOR_DO_ROTULO_DO_STEAM_INPUT: rotulo}
    assert a01_jogar._o_rotulo_do_chip(None).keys() == blocos.keys()
    medido = _aplicar(alvo, blocos)
    assert medido["texto"] == rotulo, medido
    assert medido["desenho"] and min(medido["desenho"]) > 0, (
        f"o rótulo do tique apagou o desenho da Steam: {medido}")
