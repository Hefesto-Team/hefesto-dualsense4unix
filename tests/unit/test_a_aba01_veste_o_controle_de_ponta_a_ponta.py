#!/usr/bin/env python3
"""A ABA 01 VESTE O CONTROLE DE PONTA A PONTA — do daemon ao pixel."""
from __future__ import annotations

import json
import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

for _p in (str(RAIZ / "src"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import a01_jogar

import hefesto_vivo
import monta

BANCADA = RAIZ / "mockup/01-jogar.html"

CRU = re.compile(r'<g id="jg-p1-corpo" class="z-casca"[^>]*>\s*'
                 r'(?:<title>[^<]*</title>\s*)?<path[^>]*fill="(#[0-9a-fA-F]{6})"')

UNIQ = "aa:bb:cc:00:00:01"


def _modelos_do_mapa() -> list[str]:
    """Os 28 do mapa dela, lidos da folha que o gerador de cores escreveu."""
    return sorted(set(re.findall(r'svg\[data-colorway="([^"]+)"\]', monta.DS)))


def _fora_do_mockup() -> list[str]:
    """Os modelos que o desenho NÃO traz — os 24 que provam a lei."""
    do_mockup = {str(c["cor"]) for c in monta.MESA}
    return [m for m in _modelos_do_mapa() if m not in do_mockup]


def _carga(slug: str) -> dict[str, Any]:
    """A carga que o piloto pintaria com ESTE modelo no cabo do P1."""
    cru = {"uniq": UNIQ, "connected": True, "player_slot": 1,
           "transport": "usb", "battery_pct": 95}
    da_mesa = {"uniq": UNIQ, "pref": "p1", "jogador": 1,
               "nome": slug, "cor": slug, "via": "USB"}
    ctx = Contexto(state={"controllers": [cru]}, mesa=[da_mesa],
                   conectados=[cru], estados={})
    carga = pacotes.normalizar(a01_jogar.pacote(ctx), {UNIQ: "p1"})
    return dict(pacotes.apagar_os_lugares_sem_dono(carga))


ROTEIRO = """
(function(){
  const svg = document.querySelector('[data-controle="p1"] svg[data-campo="desenho"]');
  if(!svg) return JSON.stringify({erro: 'não achei o desenho do p1'});
  const casca = svg.querySelector('.z-casca path:not([fill="none"])');
  if(!casca) return JSON.stringify({erro: 'não achei o chassi do desenho'});
  const pele = document.querySelector('[data-controle="p1"] [data-campo="plastico"]');
  if(!pele) return JSON.stringify({erro: 'não achei a pele do cartão do p1'});
  const fora = {chassi: {}, pele: {}, colorway: {}, pintou: {}};
  for(const [slug, carga] of CARGAS){
    fora.pintou[slug] = window.__hef.pintar(carga);
    fora.chassi[slug] = getComputedStyle(casca).fill;
    fora.pele[slug] = getComputedStyle(pele).color;
    fora.colorway[slug] = svg.getAttribute('data-colorway');
  }
  return JSON.stringify(fora);
})()
"""


def _no_webkit(roteiro: str) -> dict[str, Any]:
    """Abre a bancada num WebKit offscreen, com o BOOTSTRAP do piloto dentro."""
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

    def bootou(v: Any, res: Any) -> None:
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:  # pragma: no cover
            saiu.append(f"ERRO no BOOTSTRAP: {e}")
            Gtk.main_quit()
            return
        v.evaluate_javascript(roteiro, -1, None, None, None, guardou)

    def carregou(v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(hefesto_vivo.BOOTSTRAP, -1, None, None, None,
                                  bootou)

    view.connect("load-changed", carregou)
    view.load_uri(BANCADA.as_uri())
    guarda = GLib.timeout_add(30000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert saiu, "o WebKit não respondeu em 30 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    return dict(json.loads(saiu[0]))


def _rgb(hexa: str) -> str:
    """`#e35b8c` → `rgb(227, 91, 140)`, a forma em que o WebKit devolve a cor."""
    h = hexa.lstrip("#")
    return f"rgb({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)})"


def _como_o_motor_diz(valor: str) -> str:
    """O que o WebKit devolve para o valor que a folha dela escreveu."""
    if valor.startswith("#"):
        return _rgb(valor)
    return valor.replace("url(#", 'url("#').replace(")", '")')


@pytest.fixture(scope="module")
def medido() -> dict[str, Any]:
    """Uma abertura de WebKit para as três asserções abaixo."""
    if not BANCADA.is_file():
        pytest.skip(f"a bancada não tem {BANCADA.name} — rode aba01.py")
    cargas = [[slug, _carga(slug)] for slug in _fora_do_mockup()]
    fora = _no_webkit(ROTEIRO.replace("CARGAS", json.dumps(cargas)))
    assert "erro" not in fora, fora.get("erro")
    return fora


def test_o_piloto_escreve_o_colorway_que_o_pacote_leu(medido: dict[str, Any]) -> None:
    """O elo do meio: o `escrever()` do piloto chega ao atributo do `<svg>`."""
    for slug in _fora_do_mockup():
        assert medido["colorway"][slug] == slug, (
            f"com {slug!r} na mesa o `<svg>` ficou com "
            f"{medido['colorway'][slug]!r}. O `escrever()` não chegou ao "
            f"atributo: confira `data-hef-alvo` e `data-hef-atributo` no "
            f"desenho, e `atributo_escrevivel` no piloto.")


def test_os_vinte_e_quatro_modelos_de_fora_do_mockup_pintam(
        medido: dict[str, Any]) -> None:
    """A lei de produto, no pixel: o controle DELE, não o do desenho."""
    achou = CRU.search(BANCADA.read_text(encoding="utf-8"))
    assert achou, "o chassi do desenho do P1 mudou de forma — não há neutro a medir"
    cru = _rgb(achou.group(1))
    fora = _fora_do_mockup()
    assert len(fora) == 24, (
        f"o mapa dela mudou de tamanho: {len(fora)} modelos fora do mockup. "
        f"Releia esta régua antes de mexer no número.")

    cinzas = [s for s in fora if medido["chassi"][s] == cru]
    assert not cinzas, (
        f"{len(cinzas)} de {len(fora)} modelos caíram no cinza cru ({cru}) — "
        f"o desenho ficou SEM identidade em vez de vestir o aparelho: "
        f"{cinzas[:6]}")

    do_mockup = monta.cor_da_zona(str(monta.MESA[0]["cor"]), "casca")
    presos = [s for s in fora if medido["chassi"][s] == _rgb(do_mockup)]
    assert not presos, (
        f"{len(presos)} modelos continuaram com a cor do MOCKUP ({do_mockup}) "
        f"sobre um aparelho que é outro — é o defeito que esta leva mata: "
        f"{presos[:6]}")

    erradas = {s: (medido["chassi"][s], monta.cor_da_zona(s, "casca"))
               for s in fora
               if medido["chassi"][s]
               != _como_o_motor_diz(monta.cor_da_zona(s, "casca"))}
    assert not erradas, f"o chassi não vestiu a cor do mapa dela: {erradas}"


def test_a_borda_e_o_desenho_nunca_discordam(medido: dict[str, Any]) -> None:
    """A queixa de uso era a DISTÂNCIA entre os dois, e ela tinha quatro pixels.

        **

    A borda (`--plastico`, pela pele) e o desenho (`data-colorway`) são pintados
    por alvos DIFERENTES, a partir de duas chaves diferentes do pacote. Nada os
    obrigava a concordar além de chamarem o mesmo `monta.cor_da_zona` — e é
    isso que esta régua cobra no motor, no mesmo tique.

    A comparação é com a zona `casca-solida` de propósito: é o que
    `cor_da_zona` devolve por omissão, e é o que o pacote escreve na pele. Os
    modelos que pintam com `<pattern>` saem da conta porque a pele não pode
    receber um `url(#…)` — mas o desenho pode, e a asserção acima já os cobre.
    """
    for slug in _fora_do_mockup():
        esperado = monta.cor_da_zona(slug)
        if not esperado.startswith("#"):
            continue
        assert medido["pele"][slug] == _rgb(esperado), (
            f"com {slug!r} na mesa a borda do cartão ficou "
            f"{medido['pele'][slug]} e o mapa dela diz {esperado}")


def test_a_pintura_nao_deu_verde_sobre_nada(medido: dict[str, Any]) -> None:
    """Um contador em zero é endereço que não existe — e é verde sobre nada."""
    primeiro = _fora_do_mockup()[0]
    assert medido["pintou"][primeiro] > 0, (
        "o piloto pintou ZERO valores na bancada — nenhum endereço da carga "
        "existe na página")
