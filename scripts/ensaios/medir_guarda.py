"""Lê do DOM VIVO o estado das células 'Ajuste próprio' das quatro linhas."""
import pathlib, sys
sys.path.insert(0, "/mnt/Apate/Desenvolvimento/hefesto-dualsense4unix/src/hefesto_dualsense4unix/interface")
import sys
# A janela deste instrumento NÃO nasce na tela dela (TELA-DELA-02).
# Ela pediu duas vezes em 04/09/2026; o `park` do workspace chega tarde,
# porque move a janela DEPOIS de ela existir. Escape: HEFESTO_NA_TELA=1.
_RAIZ_TELA = str(pathlib.Path(__file__).resolve().parents[2] / 'src')
if _RAIZ_TELA not in sys.path:
    sys.path.insert(0, _RAIZ_TELA)
from hefesto_dualsense4unix.utils.tela_de_mentira import (
    garantir_tela_de_mentira,
)

garantir_tela_de_mentira()

import gi
gi.require_version("Gtk", "3.0"); gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, Gtk
from hefesto_dualsense4unix.gui.ponte_da_tela import JanelaDaAba
from hefesto_dualsense4unix.interface import onde

JS = """(function(){
  const out = [];
  document.querySelectorAll('.tab tbody tr').forEach((tr, i) => {
    const nome = (tr.querySelector('[data-hef="guarda.nome"]')||{}).textContent;
    const cels = [...tr.querySelectorAll('[data-hef="guarda.secao"]')]
                   .map(e => e.classList.contains('on') ? 'ACESA' : 'apagada');
    if (cels.length) out.push({linha:i, nome:(nome||'').trim(), cels});
  });
  return JSON.stringify(out);
})()"""

def _pronto(*_a):
    GLib.timeout_add(3000, ler)

j = JanelaDaAba(arquivo=onde.pagina("10-perfis.html", publicado=True),
                titulo_esperado="Hefesto — aba PERFIS", oculta=True,
                ao_carregar=_pronto)

def ler():
    def volta(v, e):
        print("ERRO:", e) if e else print(v)
        Gtk.main_quit()
    j.ponte.perguntar(JS, volta)
    return False
GLib.timeout_add(15000, Gtk.main_quit)
Gtk.main()
