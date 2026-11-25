"""D-2511-O-PAINEL-DA-ENTRADA-DIZ-O-LUGAR-E-MOVE-SEM-ARRASTO: o painel da entrada.

O gesto `entrada-lugar` vivia sem nenhum elemento que o mandasse, e a troca de duas entradas só
existia por arrasto. O painel da entrada ganha o «Lugar» (só numa entrada de «Sem Lugar») e o
«Mover para…» (toda entrada com outra a quem trocar): dois `select` nativos, que o teclado e o
controle alcançam. Esta régua roda a página que o GERADOR produz no WebKit do produto.

MORDIDAS: tirar o «Lugar» ou o «Mover» do gerador (`EDICOES_DO_PAINEL_DA_ENTRADA`) reprova o caso
que o nomeia; trocar `semLugar(p)` por `true` reprova o caso da entrada que já tem lugar.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.interface import pagina_do_mapa as gerador
from tests.unit.test_o_mapa_das_portas_nao_poe_texto_do_dom_como_html import _no_webkit

_JS = r"""
(function(){
  const r = {};
  const abre = n => {
    for (let i = 0; i < 2 && !document.querySelector('#edita [data-entrada="' + n + '"]'); i++) {
      document.querySelector('.plug[data-porta="' + n + '"]').click();
    }
  };
  const campo = (n, classe) => {
    const c = document.querySelector('#edita select.' + classe + '[data-entrada="' + n + '"]');
    if (!c) return null;
    return { tag: c.tagName, gesto: c.getAttribute('data-gesto'),
             nome: c.getAttribute('aria-label') };
  };
  const rotulo = n =>
    document.querySelector('.plug[data-porta="' + n + '"]').getAttribute('aria-label');

  abre('16');
  r.lugarSemLugar = campo('16', 'lugar-da-entrada');
  r.moverSemLugar = campo('16', 'mover-para');
  abre('1');
  r.lugarComLugar = campo('1', 'lugar-da-entrada');
  r.moverComLugar = campo('1', 'mover-para');

  const de = rotulo('1');
  r.rotulosDiferem = de !== rotulo('16');
  let arrastou = 0;
  document.addEventListener('dragstart', () => { arrastou++; }, true);
  const seletor = document.querySelector('#edita select.mover-para[data-entrada="1"]');
  seletor.value = '16';
  seletor.dispatchEvent(new Event('change', { bubbles: true }));
  r.trocou = rotulo('16') === de && rotulo('1') !== de;
  r.arrastou = arrastou;
  return JSON.stringify(r);
})()
"""


@pytest.fixture(scope="module")
def lido(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    resposta = _no_webkit(str(gerador.pagina()), tmp_path_factory.mktemp("painel"), _JS)
    assert "erro" not in resposta, resposta
    return resposta


def test_o_lugar_so_aparece_na_entrada_sem_lugar_e_o_mover_em_toda_entrada(
    lido: dict[str, Any],
) -> None:
    """D-2511-O-PAINEL-DA-ENTRADA-DIZ-O-LUGAR-E-MOVE-SEM-ARRASTO: o painel da entrada.

    Na entrada 16, de «Sem Lugar», há o seletor do gesto `entrada-lugar`; na 1, que tem lugar, não
    há; as duas trazem o «Mover para…» do gesto `entrada-trocar`, e ambos são `select` nativos.
    """
    assert lido["lugarSemLugar"] == {
        "tag": "SELECT", "gesto": "entrada-lugar", "nome": "Lugar da entrada"}, lido
    assert lido["lugarComLugar"] is None, "o «Lugar» apareceu numa entrada que já tem lugar"
    for chave in ("moverSemLugar", "moverComLugar"):
        assert lido[chave] == {
            "tag": "SELECT", "gesto": "entrada-trocar", "nome": "Mover para outra entrada"}, lido


def test_duas_entradas_trocam_pelo_mover_sem_nenhum_arrasto(lido: dict[str, Any]) -> None:
    """D-2511-O-PAINEL-DA-ENTRADA-DIZ-O-LUGAR-E-MOVE-SEM-ARRASTO: o mover sem arrasto.

    Escolher a outra entrada no «Mover para…» troca o que está em cada uma, sem `dragstart`.
    """
    assert lido["rotulosDiferem"], "as duas entradas têm o mesmo aparelho: a troca não foi medida"
    assert lido["trocou"], "o «Mover para…» não trocou as duas entradas"
    assert lido["arrastou"] == 0
