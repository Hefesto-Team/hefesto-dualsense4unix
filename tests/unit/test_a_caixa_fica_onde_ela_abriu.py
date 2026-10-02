"""A caixa fica onde ela abriu — A-CAIXA-FICA-ONDE-ELA-ABRIU-01 (item 2 da auditoria de 26/09)."""

from __future__ import annotations

import ast
import re
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import central_do_radio as cr
from tests.unit.radio_de_mentira import QUARTO, SALA, VARANDA

CHIP = re.compile(r'<button class="op" aria-pressed="(true|false)"[^>]*'
                  r'data-gesto="escolher-adaptador" data-alvo="([0-9A-F]{12})"')
TRES = (SALA, QUARTO, VARANDA)
PARES = [(busca, dela) for busca in TRES for dela in TRES if busca != dela]
TIQUES = 30


CARTAO = re.compile(r'<div class="lugar[" ]')


def _cartao(sala: str, lid: str) -> str:
    """O cartão inteiro de um adaptador no HTML da sala."""
    comecos = [m.start() for m in CARTAO.finditer(sala)]
    inicio = max(c for c in comecos if c < sala.index(f'data-id="{lid}"'))
    fim = next((c for c in comecos if c > inicio), len(sala))
    return sala[inicio:fim]


class PonteQueAceita:
    """A resposta da central que MUDA a busca de adaptador — o ``ok`` do"""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, dict[str, Any]]] = []

    def resultado(self, metodo: str, timeout: float | None = None, **params: Any) -> Any:
        self.chamadas.append((metodo, dict(params)))
        movimento = cr.Movimento(cr.CONECTANDO, str(params["destino"]), cr.ESPERANDO,
                                 cr.PASSO_PREPARANDO, quando=time.time())
        return {"status": "ok", "movimento": movimento.publicar()}


INTERFACE = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix" / "interface"


def _quem_chama(nome: str) -> set[tuple[str, str]]:
    """``(arquivo, função)`` de toda chamada a ``nome`` no pacote da interface."""
    achados: set[tuple[str, str]] = set()
    for arquivo in sorted(INTERFACE.rglob("*.py")):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for funcao in ast.walk(arvore):
            if not isinstance(funcao, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for no in ast.walk(funcao):
                if not isinstance(no, ast.Call):
                    continue
                alvo = no.func
                chamado = (alvo.attr if isinstance(alvo, ast.Attribute)
                           else alvo.id if isinstance(alvo, ast.Name) else "")
                if chamado == nome:
                    achados.add((arquivo.name, funcao.name))
    return achados


def test_so_o_x_dela_esquece_um_pareamento_pela_tela() -> None:
    """Na tela, o pareamento sai por UM caminho: o X dela («Esquecer» da"""
    assert _quem_chama("_esquecer_o_pareamento") == {("a08_conexoes.py", "confirmar_esquecer")}
    assert _quem_chama("esquecer_o_pareamento") == {("a08_conexoes.py", "_esquecer_o_pareamento")}


ROTEIRO_DO_CHIP = r"""
(function(){
  function abrir(){
    const m = document.querySelector('.radio template.painel-molde[data-painel="conectar"]');
    const corpo = document.getElementById('rd-painel-corpo');
    corpo.innerHTML = ''; corpo.appendChild(m.content.cloneNode(true));
    document.getElementById('rd-painel').classList.add('aberto');
  }
  function acesos(){
    return [...document.querySelectorAll('#rd-painel .op')]
      .filter(c => c.getAttribute('aria-pressed') === 'true').map(c => c.dataset.alvo);
  }
  function apagado(){
    return document.querySelector('#rd-painel .op[aria-pressed="false"]');
  }
  const fora = {};
  abrir();
  fora.no_molde = acesos();
  let c = apagado(); fora.clicado_sem_piloto = c.dataset.alvo; c.click();
  fora.sem_piloto = acesos();
  window.__hef = window.__hef || {}; window.__hef.ouvindo = true;
  abrir();
  c = apagado(); fora.clicado_com_piloto = c.dataset.alvo;
  try { c.click(); } catch (e) { fora.erro = String(e); }
  fora.com_piloto = acesos();
  return JSON.stringify(fora);
})()
"""


@pytest.fixture(scope="module")
def chip_no_webkit() -> dict[str, Any]:
    """A bancada da 08 num WebKit offscreen — o motor que ela usa."""
    import json

    from hefesto_dualsense4unix.interface import onde

    pagina = onde.pagina("08-conexoes.html")
    if not pagina.is_file():
        pytest.skip("a bancada da 08 não está no disco — rode o gerador")
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")
    saiu: list[str] = []
    janela = Gtk.OffscreenWindow()
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def guardou(v: Any, res: Any) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:  # pragma: no cover — só quando o roteiro quebra
            saiu.append(f"ERRO {e}")
        Gtk.main_quit()

    def carregou(v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(ROTEIRO_DO_CHIP, -1, None, None, None, guardou)

    view.connect("load-changed", carregou)
    view.load_uri(pagina.as_uri())
    guarda = GLib.timeout_add(30000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert saiu, "o WebKit não respondeu em 30 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    return dict(json.loads(saiu[0]))


def test_no_motor_com_o_piloto_o_chip_nao_acende_no_clique(chip_no_webkit: dict[str, Any]) -> None:
    """Com o piloto no ar, o chip clicado não acende na página: quem acende é o"""
    fora = chip_no_webkit
    assert len(fora["no_molde"]) == 1
    assert fora["sem_piloto"] == [fora["clicado_sem_piloto"]], "o desenho perdeu o clique"
    assert fora["com_piloto"] == fora["no_molde"], "o chip acendeu antes do rádio responder"


MOVER = [(destino, dela) for destino in (QUARTO, VARANDA) for dela in TRES if dela != destino]


