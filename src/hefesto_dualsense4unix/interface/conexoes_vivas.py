#!/usr/bin/env python3
"""conexoes_vivas — a aba 08 (Conexões) viva, pelo molde da Controles.

A página publicada `08-conexoes.html` num `WebKit2.WebView` dentro de uma janela
GTK3, com o Python OUVINDO. **Este arquivo é fino de propósito**: a janela, as
duas pontes e a guarda de carga são de `gui/ponte_da_tela.py`, e quem PINTA a
aba é o pacote `interface/pacotes/a08_conexoes.py`, pelo piloto das dez abas
(`hefesto_vivo.py`). O que sobra aqui é o que só esta bancada tem: a prova do
gesto, a foto e a régua de custo da leitura do estado.

    ./conexoes_vivas.py --oculta --duble estado.json --segundos 20 --foto <pasta>/a.png

A PINTURA DESTA BANCADA SAIU EM 28/09/2026. Ela pintava na gramática
`data-v`/`data-g` de 26/08 (`gui/aba_conexoes.pintura`), que a página aprovada
não fala mais: nenhum endereço dela existia na página, e a remontagem trocava o
`innerHTML` do acordeão e das colunas do exame pelo HTML velho. A tela pintada
se olha pelo piloto — `hefesto_vivo.py --oculta --abre 08-conexoes.html` —,
sempre no lar de mentira.

O DAEMON PODE ESTAR DESLIGADO, E ISSO NÃO IMPEDE NADA
-----------------------------------------------------
`--duble` lê um `state_full` de arquivo em vez de perguntar ao daemon: nenhum
byte vai ao aparelho, nenhum `/sys` é lido, e nenhum perfil dela é escrito.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from typing import Any

RAIZ_DEV = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ_DEV / "src"))

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("WebKit2", "4.1")

from gi.repository import GLib, Gtk  # noqa: E402

from hefesto_dualsense4unix.gui.ponte_da_tela import JanelaDaAba  # noqa: E402

PAGINA = RAIZ_DEV / "src" / "hefesto_dualsense4unix" / "interface" / "paginas" / "08-conexoes.html"  # noqa-acento (`paginas` e o nome da PASTA; caminho nao leva acento)
TITULO_ESPERADO = "aba CONEXÕES"
TIQUE_MS = 100

OUVINTE = r"""
(function(){
  if(window.__hefOuvinte) return;
  window.__hefOuvinte = true;
  window.__hefErros = [];
  function manda(o){
    try { window.webkit.messageHandlers.hefesto.postMessage(JSON.stringify(o)); }
    catch(e){}
  }
  // O ERRO DE JS É CONTADO, não só impresso: a prova sai com a conta dele.
  window.addEventListener('error', ev => {
    window.__hefErros.push(String(ev.message||ev));
    manda({gesto:'erro-js', texto:String(ev.message||ev).slice(0,200)});
  });
  // Campo de texto e lista falam no `change`; o resto, no clique.
  const DE_ESCREVER = el => el.matches('select,textarea,input:not([type=button]):not([type=submit]):not([type=checkbox]):not([type=radio])');
  function dados(el, extra){
    const o = Object.assign({}, el.dataset, extra||{});
    o.texto = (el.textContent||'').trim().slice(0,80);
    return o;
  }
  // UM OUVINTE SÓ, NO DOCUMENTO. Delegação em vez de um listener por elemento:
  // a remontagem troca o innerHTML e levaria junto todo listener pendurado nos
  // filhos — o botão ficaria desenhado, com cursor:pointer, e MUDO. É o defeito
  // dos três botões de som da aba Controles, e aqui ele não pode nascer.
  document.addEventListener('click', ev => {
    const el = ev.target.closest('[data-gesto]');
    if(!el || el.disabled || DE_ESCREVER(el)) return;
    manda(dados(el, {evento:'click'}));
  }, true);
  document.addEventListener('change', ev => {
    const el = ev.target.closest('[data-gesto]');
    if(!el || !DE_ESCREVER(el)) return;
    manda(dados(el, {evento:'change', valor: el.value}));
  }, true);
})();
"""

PROVA_DO_GESTO = r"""
(function(){
  const marco = document.getElementById('cx8-3');
  const raiz = (marco && marco.closest('.quadro')) || document;
  const nomes = [], cinzas = [];
  const vistos = new Set();
  for(const el of raiz.querySelectorAll('[data-gesto]')){
    const n = el.dataset.gesto;
    if(vistos.has(n)) continue;
    const vivo = Array.from(raiz.querySelectorAll('[data-gesto="'+n+'"]')).find(e => !e.disabled);
    vistos.add(n);
    if(!vivo){ cinzas.push(n); continue; }
    nomes.push(n);
  }
  // OS GESTOS DOS MOLDES — a pergunta, os painéis e o balão nascem em
  // `<template>` e só entram no DOM quando a página os abre. A prova não os
  // clica (abrir cada um é o roteiro da página), mas COBRA o dono de cada nome:
  // um gesto de molde sem dono é um botão que a tela oferece e ninguém atende.
  const moldes = [];
  for(const t of raiz.querySelectorAll('template')){
    for(const el of t.content.querySelectorAll('[data-gesto]')){
      const n = el.dataset.gesto;
      if(!vistos.has(n) && moldes.indexOf(n) < 0) moldes.push(n);
    }
  }
  window.webkit.messageHandlers.hefesto.postMessage(JSON.stringify(
    {gesto:'prova-lista', nomes:nomes, cinzas:cinzas, moldes:moldes}));
  nomes.forEach((n, i) => setTimeout(() => {
    const el = Array.from(raiz.querySelectorAll('[data-gesto="'+n+'"]')).find(e => !e.disabled);
    if(!el) return;
    if(el.matches('select,textarea,input:not([type=button]):not([type=submit]):not([type=checkbox]):not([type=radio])')){
      if(el.tagName === 'SELECT' && el.options.length > 1) el.selectedIndex = 1;
      else if(el.tagName !== 'SELECT') el.value = (el.value || '') + ' ';
      el.dispatchEvent(new Event('change', {bubbles:true}));
    } else {
      el.click();
    }
  }, 120 * i));
})()
"""

BOOTSTRAP = OUVINTE + "\n'HEF-PRONTO'\n"


def _ler_json(caminho: str | None) -> Any:
    if not caminho:
        return None
    return json.loads(pathlib.Path(caminho).read_text(encoding="utf-8"))


def _dono_do_gesto(nome: str) -> str | None:
    """Quem atende este gesto na aba 08 — o registro das dez abas, não uma lista.

    ``"handler"`` quando há um ``@gesto`` para ele; ``"SEM_GESTO"`` quando o
    pacote declara que ele ainda não tem dono, com a razão; ``None`` quando
    ninguém sabe dele — e esse é o caso que a prova reprova.
    """
    from hefesto_dualsense4unix.interface import pacotes
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    if pacotes.gesto_da_pagina(PAGINA.name, nome) is not None:
        return "handler"
    if nome in a08_conexoes.SEM_GESTO:
        return "SEM_GESTO"
    return None


class Janela:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.pronto = False
        self.voltas = 0
        self.custos: list[float] = []
        self.gestos: list[dict[str, Any]] = []
        self.sem_dono: list[str] = []
        self.erros_js: list[str] = []
        self.prova_nomes: list[str] = []
        self.prova_cinzas: list[str] = []
        self.prova_moldes: list[str] = []
        self.rss: list[int] = []
        self._t0 = 0.0

        self.tela = JanelaDaAba(
            arquivo=PAGINA,
            titulo_esperado=TITULO_ESPERADO,
            ao_carregar=self._instalar,
            ao_receber=self._gesto,
            ao_sair_da_aba=self._saiu_da_aba,
            oculta=args.oculta,
            subtitulo="Conexões — o que o aparelho diz",
        )
        self.ponte = self.tela.ponte
        self.janela = self.tela.janela

    def _saiu_da_aba(self, titulo: str) -> None:
        self.pronto = False
        print(f"[fora da Conexões] {titulo} — o mockup estático; o tique pausou.")

    def _instalar(self) -> None:
        if self.args.secao:
            self.ponte.rodar(
                f"(function(e){{if(e)e.checked=true;}})"
                f"(document.getElementById({json.dumps(self.args.secao)}))"
            )
        if self.args.sem_ponte:
            print("MORDIDA: a ponte está DESLIGADA — a tela fica na cena fixa do mockup.")
            self.pronto = True
            if self.args.prova_gesto:
                self.ponte.rodar(OUVINTE)
                self._marcar_gestos_de_mentira()
            self._agendar_saida()
            return

        def pronto(_valor: str | None, erro: Exception | None) -> None:
            if erro is not None:
                print(f"ERRO DE CARGA: o bootstrap não instalou: {erro}", file=sys.stderr)
                Gtk.main_quit()
                return
            self.pronto = True
            self._t0 = time.monotonic()
            self._tique()
            GLib.timeout_add(TIQUE_MS, self._tique)
            if self.args.prova_gesto:
                self._marcar_gestos_de_mentira()
            self._agendar_saida()

        self.ponte.perguntar(BOOTSTRAP, pronto)

    def _marcar_gestos_de_mentira(self) -> None:
        """Cliques SINTÉTICOS: provam o caminho tela → Python, não o desenho."""
        GLib.timeout_add(1200, lambda: (self.ponte.rodar(PROVA_DO_GESTO), False)[1])

    def _agendar_saida(self) -> None:
        foto = self.args.foto
        self.tela.agendar_saida(
            self.args.segundos or 0.0,
            antes=(lambda: self.tela.fotografar(foto)) if foto else None,
        )

    def _estado(self) -> dict[str, Any] | None:
        if self.args.duble:
            bruto = _ler_json(self.args.duble)
            return bruto if isinstance(bruto, dict) else None
        try:
            sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
            import mesa_viva

            return mesa_viva.estado_do_daemon()
        except Exception as erro:
            if self.voltas == 0:
                print(f"daemon calado ({erro}) — a mesa fica vazia, e é uma resposta.")
            return None

    def _tique(self) -> bool:
        """Uma volta: a leitura do estado, com o custo dela."""
        if not self.pronto:
            return True
        t0 = time.perf_counter()
        self._estado()
        t_ipc = (time.perf_counter() - t0) * 1000
        self.custos.append(t_ipc)
        self.voltas += 1
        if self.voltas % 50 == 0:
            self._medir_memoria()
        return True

    def _medir_memoria(self) -> None:
        """Um vazamento não aparece no relógio — aparece na memória."""
        try:
            with open("/proc/self/status", encoding="utf-8") as arq:
                for linha in arq:
                    if linha.startswith("VmRSS:"):
                        self.rss.append(int(linha.split()[1]))
                        return
        except OSError:
            pass

    def _gesto(self, objeto: dict[str, Any]) -> None:
        nome = str(objeto.get("gesto") or "")
        if nome == "erro-js":
            self.erros_js.append(str(objeto.get("texto") or ""))
            print(f"ERRO DE JS: {objeto.get('texto')}", file=sys.stderr)
            return
        if nome == "prova-lista":
            self.prova_nomes = [str(n) for n in objeto.get("nomes") or []]
            self.prova_cinzas = [str(n) for n in objeto.get("cinzas") or []]
            self.prova_moldes = [str(n) for n in objeto.get("moldes") or []]
            return
        dono = _dono_do_gesto(nome)
        if dono is None:
            self.sem_dono.append(nome)
            print(f"gesto SEM DONO, recusado: {objeto!r}", file=sys.stderr)
            return
        self.gestos.append(objeto)
        alvo = objeto.get("alvo") or "—"
        valor = objeto.get("valor") or objeto.get("texto") or ""
        print(f"gesto: {nome} · {dono} · alvo {alvo} · {str(valor)[:40]}")

    def relato_da_prova(self) -> tuple[bool, str]:
        """``(passou, texto)`` — cada gesto da seção clicado chegou e tem dono."""
        chegaram = {str(o.get("gesto")) for o in self.gestos}
        faltam = [n for n in self.prova_nomes if n not in chegaram]
        linhas = [
            f"prova do gesto: {len(self.prova_nomes)} nomes clicados · "
            f"{len(chegaram & set(self.prova_nomes))} chegaram com dono · "
            f"{len(set(self.sem_dono))} sem dono · {len(self.erros_js)} erro(s) de JS",
        ]
        if self.prova_cinzas:
            linhas.append(f"  cinzas (não se clica): {', '.join(self.prova_cinzas)}")
        orfaos = [n for n in self.prova_moldes if _dono_do_gesto(n) is None]
        if self.prova_moldes:
            linhas.append(f"  nos moldes (dono conferido, sem clique): "
                          f"{', '.join(self.prova_moldes)}")
        if orfaos:
            linhas.append(f"  MOLDE SEM DONO: {', '.join(orfaos)}")
        if faltam:
            linhas.append(f"  NÃO CHEGARAM: {', '.join(faltam)}")
        if self.sem_dono:
            linhas.append(f"  SEM DONO: {', '.join(sorted(set(self.sem_dono)))}")
        passou = (bool(self.prova_nomes) and not faltam and not self.sem_dono
                  and not self.erros_js and not orfaos)
        return passou, "\n".join(linhas)

    def relato(self) -> str:
        def resumo(nome: str, v: list[float]) -> str:
            if not v:
                return f"{nome}: sem amostra"
            s = sorted(v)
            return (
                f"{nome}: mediana {s[len(s) // 2]:.2f} ms · "
                f"p95 {s[int(len(s) * 0.95)]:.2f} · max {s[-1]:.2f}"
            )

        linhas = [
            f"voltas: {self.voltas} · gestos: {len(self.gestos)}",
            resumo("IPC ", self.custos),
        ]
        if self.custos:
            s = sorted(self.custos)
            med = s[len(s) // 2]
            linhas.append(
                f"orçamento: {med / TIQUE_MS * 100:.1f}% dos {TIQUE_MS} ms do tique"
            )
        if len(self.custos) >= 600:
            blocos = [
                f"{i // 300}:{sorted(self.custos[i:i + 300])[150]:.2f}"
                for i in range(0, len(self.custos) - 299, 300)
            ]
            linhas.append("mediana por bloco de 300 voltas → " + " · ".join(blocos))
        if self.rss:
            linhas.append(
                f"memória RSS: {self.rss[0] / 1024:.1f} MB → "
                f"{self.rss[-1] / 1024:.1f} MB ({len(self.rss)} amostras)"
            )
        if self.ponte.recusas:
            linhas.append(f"gestos RECUSADOS pela ponte: {len(self.ponte.recusas)}")
        return "\n".join(linhas)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--oculta", action="store_true", help="Gtk.OffscreenWindow")
    p.add_argument("--foto", help="salva um PNG e sai (pede --oculta)")
    p.add_argument("--segundos", type=float, default=0.0, help="sai depois de N s")
    p.add_argument("--sem-ponte", action="store_true", help="a MORDIDA: sem o tique")
    p.add_argument("--prova-gesto", action="store_true",
                   help="cliques sintéticos, e prova que o gesto chega ao Python")
    p.add_argument("--secao", help="abre esta seção antes da foto (ex.: cx8-3)")
    p.add_argument("--duble", help="JSON com um state_full — em vez do daemon")
    args = p.parse_args()

    if not PAGINA.exists():
        print(f"ERRO: a página desta aba não está em {PAGINA}", file=sys.stderr)
        return 2

    j = Janela(args)
    Gtk.main()
    print("\n" + j.relato())
    if args.prova_gesto:
        passou, texto = j.relato_da_prova()
        print(texto)
        if not passou:
            print("ERRO: a prova do gesto não fechou.", file=sys.stderr)
            return 1

    if j.voltas == 0 and not args.sem_ponte:
        print("ERRO: a bancada não deu uma volta — nada foi medido.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
