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


_JS_DO_PRODUTO = r"""
(function(){
  const dado = CENSO_NO_JS, r = {}, enviados = [];
  dado.declarado = { "1": {}, "16": {} };
  window.hefestoArranjo(dado, false);
  document.addEventListener('change', ev => {
    const a = ev.target.closest('[data-gesto]');
    if (a) enviados.push({ gesto: a.dataset.gesto, entrada: a.dataset.entrada, valor: a.value });
  }, true);
  const abre = n => {
    for (let i = 0; i < 2 && !document.querySelector('#edita [data-entrada="' + n + '"]'); i++) {
      document.querySelector('.plug[data-porta="' + n + '"]').click();
    }
  };
  const sel = (n, classe) =>
    document.querySelector('#edita select.' + classe + '[data-entrada="' + n + '"]');
  const rotulo = n =>
    document.querySelector('.plug[data-porta="' + n + '"]').getAttribute('aria-label');

  abre('16');
  const lugar = sel('16', 'lugar-da-entrada');
  r.lugar = !!lugar;
  if (lugar) {
    lugar.selectedIndex = 1;
    lugar.dispatchEvent(new Event('change', { bubbles: true }));
  }
  abre('1');
  const mover = sel('1', 'mover-para');
  r.valores = mover ? Array.from(mover.options).map(o => o.value) : null;
  const antes = rotulo('1');
  if (mover) {
    mover.value = '16';
    mover.dispatchEvent(new Event('change', { bubbles: true }));
  }
  r.ficouAte = rotulo('1') === antes;
  abre('5');
  r.foraLugar = !!sel('5', 'lugar-da-entrada');
  r.foraMover = !!sel('5', 'mover-para');
  r.enviados = enviados;
  dado.declarado = { "4": {} };
  dado.mapa["16"] = dado.mapa["1"];
  delete dado.mapa["1"];
  window.hefestoArranjo(dado, false);
  document.querySelector('.plug[data-porta="16"]').click();
  r.abriuSemDono = !document.getElementById('edita').hidden;
  r.semDono = !!sel('16', 'lugar-da-entrada') || !!sel('16', 'mover-para');
  return JSON.stringify(r);
})()
"""


def test_no_produto_os_dois_mandam_o_gesto_ao_dono_e_so_onde_ele_grava(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """D-2511-O-PAINEL-DA-ENTRADA-DIZ-O-LUGAR-E-MOVE-SEM-ARRASTO: no produto, quem grava é o dono.

    Com o arranjo desta máquina, o «Lugar» da entrada sem lugar e o «Mover para…» mandam o gesto
    com a entrada e o valor que o dono grava, a página não troca nada sozinha, e a entrada que o
    dono não grava não ganha nenhum dos dois.
    """
    import json

    from hefesto_dualsense4unix.integrations.entrada_a_entrada import LUGARES_DA_PORTA

    roteiro = _JS_DO_PRODUTO.replace("CENSO_NO_JS", json.dumps(gerador.CENSO_DE_EXEMPLO))
    lido = _no_webkit(str(gerador.pagina()), tmp_path_factory.mktemp("produto"), roteiro)
    assert "erro" not in lido, lido
    assert lido["lugar"] and lido["valores"] == ["", "16"], lido
    assert lido["enviados"] == [
        {"gesto": "entrada-lugar", "entrada": "16", "valor": LUGARES_DA_PORTA[0]},
        {"gesto": "entrada-trocar", "entrada": "1", "valor": "16"},
    ], lido
    assert lido["ficouAte"], "a página trocou as entradas sem o dono gravar"
    assert not lido["foraLugar"] and not lido["foraMover"], lido
    assert lido["abriuSemDono"] and not lido["semDono"], lido
