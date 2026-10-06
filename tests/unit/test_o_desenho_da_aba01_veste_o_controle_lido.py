#!/usr/bin/env python3
"""O DESENHO DA ABA 01 VESTE O CONTROLE LIDO — os 28 modelos dela, não os 4 do mockup."""
from __future__ import annotations

import json
import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

for _p in (str(RAIZ / "src"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import a01_jogar

import monta

BANCADA = RAIZ / "mockup/01-jogar.html"

CRU = re.compile(r'<g id="jg-p1-corpo" class="z-casca"[^>]*>\s*(?:<title>[^<]*</title>\s*)?'
                 r'<path[^>]*fill="(#[0-9a-fA-F]{6})"')

ENDERECO = ('data-campo="desenho" data-hef-alvo="atributo"'
            ' data-hef-atributo="data-colorway"')


def _pagina() -> str:
    if not BANCADA.is_file():
        pytest.skip(f"a bancada não tem {BANCADA.name} — rode aba01.py")
    return BANCADA.read_text(encoding="utf-8")


def _fileira_de_cartoes(doc: str) -> str:
    """Só a fileira dos quatro cartões — dono único do corte, nas duas réguas."""
    i = doc.index('data-lista="cartoes"')
    fileira = doc[i:doc.index('<div class="faixa-final', i)]
    assert len(fileira) > 2000, "a régua não achou a fileira de cartões"
    return fileira


def _colorways_da_folha(css: str) -> set[str]:
    """Os modelos que uma folha declara. A mesma leitura dos dois lados."""
    return set(re.findall(r'svg\[data-colorway="([^"]+)"\]', css))


def test_os_quatro_desenhos_tem_endereco_com_o_alvo_de_atributo() -> None:
    doc = _pagina()
    achei = doc.count(ENDERECO)
    assert achei == len(monta.MESA), (
        f"esperava {len(monta.MESA)} desenhos endereçados e achei {achei}. "
        "Sem os TRÊS atributos juntos o piloto cai no ramo padrão e escreve o "
        "valor como TEXTO por cima do controle.")
    assert doc.count(f"<svg {ENDERECO}") == len(monta.MESA), (
        "o endereço saiu de cima do `<svg>` — a folha das cores casa pelo "
        "seletor `svg[data-colorway=…]`, e num `<div>` ele não vale")


def test_o_desenho_nao_diz_ser_o_dono_da_coluna() -> None:
    """O `data-controle="dualsense"` do arquivo sai dos quatro desenhos."""
    doc = _pagina()
    fileira = _fileira_de_cartoes(doc)
    assert 'data-controle="dualsense"' not in fileira


def test_a_folha_das_cores_e_publicada_uma_vez_com_os_vinte_e_oito() -> None:
    doc = _pagina()
    assert doc.count('<style id="cores-do-dualsense-folha">') == 1, (
        "a tabela das cores tem de estar publicada exatamente uma vez: quatro "
        "cópias podadas são quatro escolhas cravadas, e quatro cópias inteiras "
        "são 180 KB de CSS repetido")
    dela = _colorways_da_folha(monta.DS)
    assert len(dela) >= 28, "o `ds_limpo.svg` perdeu modelos — não há o que medir"
    assert _colorways_da_folha(doc) == dela


def test_nenhum_desenho_carrega_a_propria_folha_podada() -> None:
    doc = _pagina()
    fileira = _fileira_de_cartoes(doc)
    assert "cores-do-dualsense-folha" not in fileira, (
        "um desenho voltou a carregar a folha podada — com ela, escrever "
        "outro colorway não casa regra nenhuma e o chassi cai no cinza cru")


def test_o_pacote_promete_o_desenho_entre_os_campos_do_cartao() -> None:
    assert "desenho" in a01_jogar.POR_CARTAO, (
        "sem o nome em `POR_CARTAO` a cobertura conta menos do que o pacote "
        "emite — e ela é O instrumento com que esta casa prova um endereço")


def test_o_pacote_emite_o_colorway_do_controle_e_nao_o_do_desenho() -> None:
    """Com um controle Nova Pink na mesa, o pacote emite `nova-pink`."""
    uniq = "aa:bb:cc:00:00:01"
    ctx = Contexto(
        state={},
        mesa=[{"uniq": uniq, "pref": "p1", "cor": "nova-pink",
               "nome": "Nova Pink", "via": "USB"}],
        conectados=[{"uniq": uniq, "connected": True, "player_slot": 1,
                     "battery_pct": 80, "transport": "usb"}],
    )
    cartao = a01_jogar.pacote(ctx)["cartoes"][uniq]
    assert cartao["desenho"] == "nova-pink"
    assert cartao["plastico"] == monta.cor_da_zona("nova-pink")


def test_sem_cor_lida_o_desenho_nao_afirma_modelo_nenhum() -> None:
    """Vazio e desconhecido calam — a regra de produto, campo sem informação não mostra nada."""
    assert a01_jogar._colorway_do_desenho("") == ""
    assert a01_jogar._colorway_do_desenho("modelo-que-nao-existe") == ""
    for slug in ("", "modelo-que-nao-existe"):
        assert bool(a01_jogar._colorway_do_desenho(slug)) == \
            bool(a01_jogar._cor_do_plastico(slug))


ROTEIRO = """
(function(){
  const svg = document.querySelector('[data-controle="p1"] svg[data-campo="desenho"]');
  if(!svg) return JSON.stringify({erro: 'não achei o desenho do p1'});
  const casca = svg.querySelector('.z-casca path:not([fill="none"])');
  if(!casca) return JSON.stringify({erro: 'não achei o chassi do desenho'});
  const fora = {pintou: {}};
  for(const c of MODELOS){
    svg.setAttribute('data-colorway', c);
    fora.pintou[c] = getComputedStyle(casca).fill;
  }
  svg.removeAttribute('data-colorway');
  fora.apagado = getComputedStyle(casca).fill;
  return JSON.stringify(fora);
})()
"""


def _no_webkit(roteiro: str) -> dict:
    """Abre a bancada num WebKit offscreen e devolve o que o roteiro mediu."""
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

    def guardou(v: object, res: object) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:  # pragma: no cover — só quando o roteiro quebra
            saiu.append(f"ERRO {e}")
        Gtk.main_quit()

    def carregou(v: object, evento: object) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(roteiro, -1, None, None, None, guardou)

    view.connect("load-changed", carregou)
    view.load_uri(BANCADA.as_uri())
    guarda = GLib.timeout_add(20000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert saiu, "o WebKit não respondeu em 20 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    return dict(json.loads(saiu[0]))


def _rgb(hexa: str) -> str:
    """`#ae335a` → `rgb(174, 51, 90)`, a forma em que o WebKit devolve o `fill`."""
    h = hexa.lstrip("#")
    return f"rgb({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)})"


def _como_o_motor_diz(valor: str) -> str:
    """O que o WebKit devolve para o valor que a folha dela escreveu."""
    if valor.startswith("#"):
        return _rgb(valor)
    return valor.replace("url(#", 'url("#').replace(")", '")')


def test_os_vinte_e_oito_modelos_dela_pintam_no_motor() -> None:
    """Cada modelo do mapa dela pinta o chassi com a cor que ela mapeou."""
    doc = _pagina()
    achou = CRU.search(doc)
    assert achou, "o chassi do desenho do P1 mudou de forma — não há neutro a medir"
    cru = _rgb(achou.group(1))

    modelos = sorted(_colorways_da_folha(monta.DS))
    medido = _no_webkit(ROTEIRO.replace("MODELOS", json.dumps(modelos)))
    assert "erro" not in medido, medido.get("erro")

    cinzas = [c for c in modelos if medido["pintou"][c] == cru]
    assert not cinzas, (
        f"{len(cinzas)} dos {len(modelos)} modelos dela caíram no cinza cru "
        f"({cru}) — a folha da página não os traz: {cinzas[:6]}")
    erradas = {c: (medido["pintou"][c], monta.cor_da_zona(c, "casca"))
               for c in modelos
               if medido["pintou"][c] != _como_o_motor_diz(monta.cor_da_zona(c, "casca"))}
    assert not erradas, f"o chassi não vestiu a cor do mapa dela: {erradas}"


def test_sem_colorway_o_desenho_volta_ao_neutro_e_nao_ao_mockup() -> None:
    """Apagar o atributo devolve o desenho ao cinza cru — não ao Cosmic Red."""
    doc = _pagina()
    achou = CRU.search(doc)
    assert achou, "o chassi do desenho do P1 mudou de forma"
    medido = _no_webkit(ROTEIRO.replace("MODELOS", "[]"))
    assert "erro" not in medido, medido.get("erro")
    assert medido["apagado"] == _rgb(achou.group(1))
