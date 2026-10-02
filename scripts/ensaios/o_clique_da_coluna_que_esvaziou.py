#!/usr/bin/env python3
"""O clique numa coluna cujo controle não está na mesa NÃO acusa quem clicou."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.utils.tela_de_mentira import (
    garantir_tela_de_mentira,
)

garantir_tela_de_mentira()

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.interface import hefesto_vivo
from hefesto_dualsense4unix.interface.pacotes.a05_vibracao import (
    FRASE_DO_CONTROLE_QUE_SAIU,
)

ABA = "05-vibracao.html"

PEDACO_CERTO = FRASE_DO_CONTROLE_QUE_SAIU.split(".")[0]

PEDACO_ERRADO = "não disse em qual controle"

LER_ASSENTOS = r"""
(function(gesto){
  const fora = [];
  for(const bloco of document.querySelectorAll('[data-controle]')){
    const pref = bloco.getAttribute('data-controle') || '';
    // O `data-controle` do desenho compartilhado carrega o MODELO
    // ("dualsense"), não o assento — dois significados no mesmo atributo, e o
    // relato da sprint o registra. Aqui só interessam os assentos.
    if(!/^p[0-9]+$/.test(pref)) continue;
    const sel = '[data-gesto="' + gesto + '"],[data-hef-gesto="' + gesto + '"],'
              + '[data-papel="' + gesto + '"]';
    fora.push({pref: pref,
               conectado: bloco.getAttribute('data-conectado') || '',
               tem_botao: !!bloco.querySelector(sel)});
  }
  return JSON.stringify({assentos: fora,
                         url: location.pathname.split('/').pop()});
})(%s)
"""

CLICAR = r"""
(function(pref, gesto){
  const bloco = document.querySelector('[data-controle="' + pref + '"]');
  if(!bloco) return 'SEM BLOCO ' + pref;
  const sel = '[data-gesto="' + gesto + '"],[data-hef-gesto="' + gesto + '"],'
            + '[data-papel="' + gesto + '"]';
  const el = bloco.querySelector(sel);
  if(!el) return 'SEM BOTAO ' + gesto + ' em ' + pref;
  el.click();
  return 'cliquei ' + gesto + ' em ' + pref;
})(%s, %s)
"""

LER_RECADOS = r"""
(function(){
  const fora = [];
  for(const el of document.querySelectorAll('.hef-recado')){
    fora.push({chave: el.getAttribute('data-hef-recado') || '',
               texto: (el.textContent || '').trim().replace(/\s+/g, ' ')});
  }
  return JSON.stringify(fora);
})()
"""

BANDEIRAS = dict(oculta=True, foto="", segundos=0.0, passear=False, parada=900,
                 espera=1200, incluir_perigosos=False, prova_clique="",
                 prova_de_mockup=False, sem_cravado=False, sem_selo=False,
                 teto_de_mockup=-1, voltas_por_aba=8, sem_cor=False,
                 sem_ondas=True, prova_no_aparelho=False, entre=2500)


class Ensaio:
    """O laço do GTK, escrito como uma fila de passos — um por tique."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.piloto = hefesto_vivo.Piloto(
            argparse.Namespace(**BANDEIRAS, abre=ABA))
        self.pagina = ""
        self.assentos: list[dict] = []
        self.assento = ""
        self.cliques: list[str] = []
        self.recados: list[dict] = []
        self.mesa: list[str] = []
        self.erro = ""

    def _perguntar(self, script: str, seguinte) -> None:
        def respondeu(texto: str | None, erro: Exception | None) -> None:
            if erro or not texto:
                self.erro = f"a ponte não respondeu: {erro}"
                Gtk.main_quit()
                return
            seguinte(texto)

        self.piloto.ponte.perguntar(script, respondeu)

    def ir(self) -> bool:
        if not self.piloto.pronto:
            return True
        self.piloto._ir(ABA)
        GLib.timeout_add(2500, self.olhar_os_assentos)
        return False

    def olhar_os_assentos(self) -> bool:
        def leu(texto: str) -> None:
            bruto = json.loads(texto)
            self.pagina = str(bruto["url"])
            self.assentos = bruto["assentos"]
            self.mesa = [str(c.get("pref") or "")
                         for c in self.piloto._mesa_de_agora]
            if self.args.foto_antes:
                self.piloto.tela.fotografar(self.args.foto_antes)
            self.escolher_e_clicar()

        self._perguntar(LER_ASSENTOS % json.dumps(self.args.gesto), leu)
        return False

    def escolher_e_clicar(self) -> None:
        vazios = [a["pref"] for a in self.assentos
                  if a["pref"] not in self.mesa and a["tem_botao"]]
        if self.args.assento:
            self.assento = self.args.assento
        elif vazios:
            self.assento = vazios[0]
        else:
            self.erro = ("nenhum assento desta página está fora da mesa — não "
                         "há coluna esvaziada a medir agora")
            Gtk.main_quit()
            return
        for i in range(self.args.vezes):
            GLib.timeout_add(400 + i * self.args.entre_cliques,
                             self.clicar_uma_vez)
        GLib.timeout_add(400 + self.args.vezes * self.args.entre_cliques + 2000,
                         self.ler_o_que_pousou)

    def clicar_uma_vez(self) -> bool:
        def clicou(texto: str) -> None:
            self.cliques.append(json.loads(texto) if texto.startswith('"')
                                else texto.strip('"'))

        self._perguntar(
            CLICAR % (json.dumps(self.assento), json.dumps(self.args.gesto)),
            clicou)
        return False

    def ler_o_que_pousou(self) -> bool:
        def leu(texto: str) -> None:
            self.recados = json.loads(texto)
            if self.args.foto_depois:
                self.piloto.tela.fotografar(self.args.foto_depois)
            Gtk.main_quit()

        self._perguntar(LER_RECADOS, leu)
        return False


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--gesto", default="testar",
                   help="qual botão da coluna clicar (padrão: testar)")
    p.add_argument("--assento", default="",
                   help="forçar o assento (`p3`). Vazio = o primeiro que a "
                        "página publica e a mesa não conhece")
    p.add_argument("--vezes", type=int, default=5,
                   help="quantos cliques — é o denominador de 'aplica de "
                        "primeira'")
    p.add_argument("--entre-cliques", type=int, default=700,
                   help="ms entre um clique e o próximo")
    p.add_argument("--foto-antes", default="",
                   help="PNG da aba ANTES de qualquer clique")
    p.add_argument("--foto-depois", default="",
                   help="PNG da aba DEPOIS, com a frase na tela")
    args = p.parse_args()

    ensaio = Ensaio(args)

    GLib.timeout_add(600, ensaio.ir)
    GLib.timeout_add(60000, Gtk.main_quit)
    Gtk.main()

    if ensaio.erro:
        print(f"REPROVA: {ensaio.erro}")
        return 1
    if ensaio.pagina != ABA:
        print(f"REPROVA: li a página {ensaio.pagina!r}, e este ensaio é da {ABA!r}.")
        return 1

    print(f"mesa de agora: {ensaio.mesa or '(vazia)'}")
    print(f"assentos na página: "
          f"{[(a['pref'], a['conectado'] or '?') for a in ensaio.assentos]}")
    print(f"assento clicado: {ensaio.assento} · gesto: {args.gesto}")
    print()
    for linha in ensaio.cliques:
        print(f"  [clique] {linha}")
    chegaram = len(ensaio.piloto.gestos)
    print(f"\ncliques mandados: {args.vezes} · chegaram ao Python: {chegaram}")
    for chave, (desfecho, frase) in sorted(ensaio.piloto.desfechos.items()):
        print(f"  [desfecho] {chave}: {desfecho} · {frase}")
    for r in ensaio.recados:
        print(f"  [na tela] chave={r['chave']!r} · {r['texto']}")

    print()
    culpados = []
    if chegaram < args.vezes:
        culpados.append(
            f"dos {args.vezes} cliques só {chegaram} chegaram ao Python — o nó "
            f"sumiu entre a leitura e o clique (ver A-TELA-SAMBA-01)")
    na_tela = " ".join(r["texto"] for r in ensaio.recados)
    if PEDACO_ERRADO in na_tela:
        culpados.append(
            f"a tela acusa o clique dela: {na_tela!r}. O clique DISSE — veio "
            f"com controle={ensaio.assento!r}, e a coluna existe na tela")
    if PEDACO_CERTO not in na_tela:
        culpados.append(
            f"a frase do fato não chegou à tela. O que está lá: {na_tela!r}")
    aplicados = [a for a in ensaio.piloto.aplicados if a.startswith(ABA)]
    if aplicados:
        culpados.append(
            f"o gesto foi adiante e disse 'aplicado' ({aplicados}) — sem alvo, "
            f"`rumble.set` é BROADCAST e a mesa inteira treme")

    if culpados:
        print(f"REPROVA: {len(culpados)} coisa(s):")
        for c in culpados:
            print(f"  {c}")
        return 1
    print(f"OK: {chegaram}/{args.vezes} cliques chegaram, e a tela diz o FATO "
          f"— não a culpa de quem clicou.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
