"""MORDIDA do recado na coluna-grade: injeta a recusa NO PILOTO REAL e mede.

Sobe o piloto do produto (`--oculta`), deixa a pintura correr, deposita uma
recusa pelo caminho de verdade (`_recusou_dizendo`) e mede se o desenho do
controle SAIU DO LUGAR. O defeito que isto cobra foi fotografado em 04/09/2026:
o recado ocupava uma célula do grid e a coluna inteira descia uma casa.
"""
import sys
import pathlib

# A RAIZ SAI DE `__file__`, NUNCA CRAVADA — a armadilha que oito arquivos desta
# casa já pagaram quando a pasta mudou de nome.
_RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_RAIZ / "src" / "hefesto_dualsense4unix" / "interface"))
sys.path.insert(0, str(_RAIZ / "src"))
import argparse
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk
import hefesto_vivo as hv

MEDIR = """(function(){
  const c = document.querySelector('[data-controle="p1"]');
  if(!c) return JSON.stringify({erro:'SEM CARTAO p1'});
  const svg = c.querySelector('.ds-svg');
  const r = svg ? svg.getBoundingClientRect() : null;
  const rec = c.querySelector('.hef-recado');
  const pai = rec ? rec.parentNode : c;
  return JSON.stringify({
    topo: r ? Math.round(r.top) : null,
    recado: rec ? getComputedStyle(rec).position : 'NAO EXISTE',
    display_do_pai: getComputedStyle(pai).display,
    pai_e_o_cartao: pai === c,
    tag_do_pai: pai.tagName + '.' + (pai.className||'')});
})()"""

a = argparse.Namespace(oculta=True, segundos=0.0, passear=False, parada=900, foto="",
                       abre="05-vibracao.html", prova_no_aparelho=False, entre=2500,
                       espera=1200, incluir_perigosos=False, prova_clique="",
                       sem_cor=False, prova_de_mockup=False, voltas_por_aba=8,
                       teto_de_mockup=-1, sem_cravado=False, sem_selo=False)
piloto = hv.Piloto(a)
estado = {}

def medir(rotulo, depois):
    def volta(v, e):
        estado[rotulo] = v or f"ERRO {e}"
        depois()
    piloto.ponte.perguntar(MEDIR, volta)

def passo_a():
    medir("antes", lambda: GLib.timeout_add(200, passo_b))
    return False

def passo_b():
    # a recusa pelo caminho do produto — o mesmo que um RuntimeError faz
    mesa = piloto._mesa_de_agora or {}
    primeiro = next(iter(mesa), None) or {}
    uniq = primeiro.get("uniq") if isinstance(primeiro, dict) else str(primeiro)
    piloto._recusou_dizendo("05-vibracao.html", "testar", str(uniq),
                            RuntimeError("Este controle não está na mesa. "
                                         "Reconecte-o e tente de novo."))
    GLib.timeout_add(900, passo_c)
    return False

def passo_c():
    medir("depois", fim)
    return False

def fim():
    import json as _json
    print("ANTES :", estado.get("antes"))
    print("DEPOIS:", estado.get("depois"))
    try:
        a = _json.loads(estado.get("antes") or "{}")
        d = _json.loads(estado.get("depois") or "{}")
    except ValueError:
        print("VEREDITO: não deu para ler a medição"); Gtk.main_quit(); return
    if d.get("recado") == "NAO EXISTE":
        print("VEREDITO: INCONCLUSIVO — o recado não chegou ao cartão")
    elif a.get("topo") != d.get("topo"):
        print(f"VEREDITO: VERMELHO — o recado deslocou o desenho "
              f"{a.get('topo')} -> {d.get('topo')} px")
    else:
        print(f"VEREDITO: VERDE — o desenho ficou em {d.get('topo')} px, "
              f"e o recado é `{d.get('recado')}`")
    Gtk.main_quit()

GLib.timeout_add(4000, passo_a)
GLib.timeout_add(25000, Gtk.main_quit)
Gtk.main()
