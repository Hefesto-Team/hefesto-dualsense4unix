#!/usr/bin/env python3
"""conexoes_vivas — a aba 08 (Conexões) viva, pelo molde da Controles.

O mockup `08-conexoes.html` num `WebKit2.WebView` dentro de uma janela GTK3, com
o Python pintando e ouvindo. **Este arquivo é fino de propósito**: a janela, as
duas pontes e a guarda de carga são de `gui/ponte_da_tela.py`, e os valores e os
endereços são de `gui/aba_conexoes.py`. O que sobra aqui é o que só o piloto tem:
o laço do tique, o dublê e a régua de custo.

    ./conexoes_vivas.py --oculta --duble mesa.json --segundos 20 --foto /tmp/a.png

POR QUE ELE MORA EM `src/hefesto_dualsense4unix/interface/` E NÃO É ENTREGÁVEL
------------------------------------------------------------------
`layout/` é `.gitignore:108`. Este arquivo NÃO viaja em worktree e NÃO é
commitável — é o mesmo estatuto do `controles_vivos.py`, e é por isso que tudo
que vale para as dez abas saiu daqui para `src/`. Quem quiser rodá-lo na árvore
dela copia-o para lá; quem quiser MEDIR o que ele faz não precisa dele: a régua
(`tests/unit/test_regua_de_tela_a_aba_conexoes.py`) chama `gui/aba_conexoes.py`
direto, que é onde mora o que se prova.

O DAEMON PODE ESTAR DESLIGADO, E ISSO NÃO IMPEDE NADA
-----------------------------------------------------
`--duble` lê um `state_full` de arquivo e `--mesa-duble` lê a mesa de rádio (os
adaptadores, os vizinhos, o exame) de outro. Foi assim que esta aba se ligou
inteira com o `hefesto-chave estavel` desligado: nenhum byte foi ao aparelho,
nenhum `/sys` foi lido, e nenhum perfil dela foi escrito.
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

from hefesto_dualsense4unix.gui import aba_conexoes  # noqa: E402
from hefesto_dualsense4unix.gui.ponte_da_tela import JanelaDaAba  # noqa: E402

PAGINA = RAIZ_DEV / "src" / "hefesto_dualsense4unix" / "interface" / "paginas" / "08-conexoes.html"  # noqa-acento (`paginas` e o nome da PASTA; caminho nao leva acento)
TITULO_ESPERADO = "aba CONEXÕES"
TIQUE_MS = 100

#: O bootstrap da aba. As três escritas DEVOLVEM quantos valores escreveram — 0
#: quando o endereço não existe —, e é isso que faz a conta do fim ser uma RÉGUA
#: e não um enfeite: com `n++` cego, arrancar um endereço não mudava o número e a
#: régua aprovava uma pintura que não pintava nada.
BOOTSTRAP = r"""
window.HEF = (function(){
  const qa = (s,r)=>Array.from((r||document).querySelectorAll(s));
  const q  = (s,r)=>(r||document).querySelector(s);
  function manda(o){
    try { window.webkit.messageHandlers.hefesto.postMessage(JSON.stringify(o)); }
    catch(e){}
  }

  // Escreve TEXTO, e só em folha. Escrever textContent num container APAGA os
  // filhos — foi assim que uma régua desta casa mediu 43 ms contra 0,66.
  function txt(el, valor){
    if(!el) return 0;
    if(el.textContent !== valor) el.textContent = valor;
    return 1;
  }
  // TRAVAR É ESCRITA, e conta na régua: um botão que a tela oferece e o produto
  // recusa é mentira. O `disabled` é o "não dá" dito no lugar certo.
  function trava(el, off){
    if(!el) return 0;
    if(el.disabled !== !!off) el.disabled = !!off;
    return 1;
  }

  // ONDE CADA BLOCO MORA. O Python manda NOMES; os seletores da folha dela
  // ficam deste lado, num lugar só.
  // CADA REMONTA DEVOLVE QUANTOS ENDEREÇOS INSTALOU, não 1. Devolver 1 por
  // bloco era a régua mentindo por baixo: a primeira versão desta aba relatou
  // "26 valores" enquanto escrevia 60, e uma pintura que perdesse metade dos
  // endereços continuaria devolvendo 6. Conta-se o que ficou no DOM.
  const contar = el => el ? qa('[data-v]', el).length : 0;
  const dentro = (sel, html) => {
    const c = q(sel); if(!c) return 0;
    c.innerHTML = html; return contar(c);
  };
  const ONDE = {
    controles:   html => dentro('.gc', html),
    exame:       html => dentro('.col-exame', html),
    ordem:       html => dentro('.col-ordem', html),
    vizinhos:    html => dentro('.vizinhos', html),
    // A TABELA GUARDA O CABEÇALHO. Trocar o innerHTML da <table> levaria o
    // <tr><th> junto, e a coluna perderia o nome — o navegador ainda insere um
    // <tbody> que ninguém escreveu, então mexer por tbody também não serve.
    adaptadores: html => {
      const tab = q('table.tab'); if(!tab) return 0;
      for(const tr of qa('tr', tab)) if(!q('th', tr)) tr.remove();
      const cab = q('tr', tab); if(!cab) return 0;
      cab.insertAdjacentHTML('afterend', html);
      return contar(tab);
    },
    // AS PISTAS ENTRAM ANTES DO EIXO, sem embrulho novo: `.sub-secao` é bloco
    // simples e um <div> a mais mudaria o desenho dela para não mudar nada que
    // se veja.
    pistas: html => {
      const sub = q('.sub-secao'); if(!sub) return 0;
      const eixo = q('.eixo', sub); if(!eixo) return 0;
      for(const p of qa('.pista', sub)) p.remove();
      eixo.insertAdjacentHTML('beforebegin', html);
      return qa('.pista [data-v]', sub).length;
    }
  };

  function pinta(pacote){
    let n = 0;
    for(const nome in (pacote.remonta||{})){
      const por = ONDE[nome];
      n += por ? por(pacote.remonta[nome]) : 0;
    }
    for(const end in (pacote.valores||{})){
      n += txt(q('[data-v="'+end+'"]'), pacote.valores[end]);
    }
    // A TRAVA TEM ENDEREÇO PRÓPRIO (`data-trava`), como o valor tem o dele.
    // Achá-la por classe + alvo era um seletor que a folha DELA podia quebrar
    // sem ninguém notar: o botão continuaria desenhado e a trava sumiria.
    for(const end in (pacote.travas||{})){
      n += trava(q('[data-trava="'+end+'"]'), pacote.travas[end]);
    }
    if(n !== window.__hefN){ window.__hefN = n; manda({gesto:'pintou', n:n}); }
    return n;
  }

  // UM OUVINTE SÓ, NO DOCUMENTO. Delegação em vez de um listener por elemento:
  // a remontagem troca o innerHTML e levaria junto todo listener pendurado nos
  // filhos — o botão ficaria desenhado, com cursor:pointer, e MUDO. É o defeito
  // dos três botões de som da aba Controles, e aqui ele não pode nascer.
  function ligarGestos(){
    document.addEventListener('click', ev => {
      const el = ev.target.closest('[data-g]');
      if(!el || el.disabled) return;
      if(el.tagName === 'SELECT') return;
      manda({gesto: el.dataset.g, alvo: el.dataset.alvo || '',
             texto: (el.textContent||'').trim().slice(0,80)});
    }, true);
    document.addEventListener('change', ev => {
      const el = ev.target.closest('[data-g]');
      if(!el || el.tagName !== 'SELECT') return;
      manda({gesto: el.dataset.g, alvo: el.dataset.alvo || '', valor: el.value});
    }, true);
  }

  ligarGestos();
  window.__hefN = -1;
  return {pinta: pinta,
          quem: function(){ return document.title + '|' + qa('.gc-item').length; }};
})();
'HEF-PRONTO'
"""


def _ler_json(caminho: str | None) -> Any:
    if not caminho:
        return None
    return json.loads(pathlib.Path(caminho).read_text(encoding="utf-8"))


class _Anonimo:
    """Um objeto de atributos a partir de um dicionário — o dublê da mesa.

    Os `Adaptador`/`RadioUsb`/`Item`/`Ordem` do produto são dataclasses frozen; o
    dublê precisa da mesma FORMA, não da mesma classe. Construir os reais aqui
    obrigaria o piloto a importar cinco módulos para inventar dado de mentira.
    """

    def __init__(self, bruto: dict[str, Any]) -> None:
        for chave, valor in bruto.items():
            setattr(self, chave, _Anonimo(valor) if isinstance(valor, dict) else valor)

    def __getattr__(self, _nome: str) -> Any:
        return ""


class Janela:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.pronto = False
        self.voltas = 0
        self.custos: list[float] = []
        self.custos_ipc: list[float] = []
        self.custos_tela: list[float] = []
        self.valores: list[int] = []
        self.gestos: list[dict[str, Any]] = []
        self.remontagens = 0
        self.chave: tuple[Any, ...] = ()
        self.rss: list[int] = []
        self._t0 = 0.0

        mesa = _ler_json(args.mesa_duble) or {}
        self.adaptadores = [_Anonimo(a) for a in mesa.get("adaptadores", [])]
        self.radios = [_Anonimo(r) for r in mesa.get("radios", [])]
        self.itens = [_Anonimo(i) for i in mesa.get("exame", [])]
        self.ordem = _Anonimo(mesa["ordem"]) if mesa.get("ordem") else None
        self.ocupacoes = {c: _Anonimo(o) for c, o in (mesa.get("ocupacoes") or {}).items()}
        self.apelidos = mesa.get("apelidos") or {}
        self.declarados = mesa.get("declarados") or {}

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

    # -- carga -------------------------------------------------------------
    def _saiu_da_aba(self, titulo: str) -> None:
        self.pronto = False
        print(f"[fora da Conexões] {titulo} — o mockup estático; a pintura pausou.")

    def _instalar(self) -> None:
        if self.args.sem_ponte:
            print("MORDIDA: a ponte está DESLIGADA — a tela fica na cena fixa do mockup.")
            self.pronto = True
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
            if self.args.arranca_enderecos:
                # A MORDIDA DO ENDEREÇO: arranca os `data-v` e vê a pintura
                # DESABAR. Um endereço a menos não levanta erro nenhum no
                # WebKit — o `querySelector` devolve `null` e o valor
                # simplesmente não é escrito. Se a conta não cair, os endereços
                # não estavam sendo usados.
                GLib.timeout_add(
                    2000,
                    lambda: (
                        self.ponte.rodar(
                            "for(const e of document.querySelectorAll('[data-v]'))"
                            " delete e.dataset.v; window.__hefN=-1;"
                        ),
                        False,
                    )[1],
                )
            if self.args.prova_gesto:
                self._marcar_gestos_de_mentira()
            self._agendar_saida()

        self.ponte.perguntar(BOOTSTRAP, pronto)

    def _marcar_gestos_de_mentira(self) -> None:
        """Cliques SINTÉTICOS: provam o caminho tela → Python, não o desenho.

        `el.click()` percorre o MESMO caminho de eventos do clique do rato — o
        ouvinte delegado do bootstrap é o que responde. Clicar por coordenada é
        a armadilha que esta casa já pagou duas vezes.
        """
        roteiro = [
            (1200, "document.querySelector('[data-g=\"exame.reexaminar\"]').click()"),
            (1500, "document.querySelector('[data-g=\"adaptador.renomear\"]').click()"),
            (1800, "document.querySelector('[data-g=\"mesa.mapear-entradas\"]').click()"),
            (2100, "document.querySelector('[data-g=\"controle.luz.nao-acende\"]').click()"),
            (
                2400,
                "(function(s){s.selectedIndex=1;"
                "s.dispatchEvent(new Event('change',{bubbles:true}));})"
                "(document.querySelector('[data-g=\"vizinho.oque\"]'))",
            ),
        ]
        for ms, script in roteiro:
            GLib.timeout_add(ms, lambda s=script: (self.ponte.rodar(s), False)[1])

    def _agendar_saida(self) -> None:
        foto = self.args.foto
        self.tela.agendar_saida(
            self.args.segundos or 0.0,
            antes=(lambda: self.tela.fotografar(foto)) if foto else None,
        )

    # -- o tique -----------------------------------------------------------
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
        if not self.pronto:
            return True
        t0 = time.perf_counter()
        estado = self._estado()
        t_ipc = (time.perf_counter() - t0) * 1000
        if estado is None:
            estado = {"controllers": []}

        controles = aba_conexoes.controles_do_estado(estado)
        chave = aba_conexoes.chave_da_mesa(controles, self.adaptadores, self.radios)
        remontar = chave != self.chave

        t1 = time.perf_counter()
        p = aba_conexoes.pintura(
            estado,
            controles=controles,
            itens_do_exame=self.itens,
            ordem=self.ordem,
            adaptadores=self.adaptadores,
            radios=self.radios,
            ocupacoes=self.ocupacoes,
            apelidos=self.apelidos,
            declarados=self.declarados,
            remontar=remontar,
        )
        self.ponte.dizer("HEF.pinta", p.como_dicionario())
        t_tela = (time.perf_counter() - t1) * 1000

        if remontar:
            self.chave = chave
            self.remontagens += 1
            sobra = aba_conexoes.sobraram(controles)
            if sobra:
                print(f"AVISO: {sobra} controle(s) ligados NÃO cabem no acordeão de 4 fatias.")
        self.custos_ipc.append(t_ipc)
        self.custos_tela.append(t_tela)
        self.custos.append(t_ipc + t_tela)
        self.voltas += 1
        if self.voltas % 50 == 0:
            self._medir_memoria()
        return True

    def _medir_memoria(self) -> None:
        """Um vazamento não aparece no relógio — aparece na memória.

        A remontagem troca o `innerHTML` de seis blocos, e um ouvinte não
        removido por remontagem seria invisível numa régua de tempo. Aqui não há
        ouvinte por elemento (a delegação é no documento), e esta conta é o que
        prova que continua assim.
        """
        try:
            with open("/proc/self/status", encoding="utf-8") as arq:
                for linha in arq:
                    if linha.startswith("VmRSS:"):
                        self.rss.append(int(linha.split()[1]))
                        return
        except OSError:
            pass

    # -- os gestos ---------------------------------------------------------
    def _gesto(self, objeto: dict[str, Any]) -> None:
        if objeto.get("gesto") == "pintou":
            self.valores.append(int(objeto.get("n") or 0))
            return
        if not aba_conexoes.gesto_valido(objeto):
            # Recusar com motivo, nunca engolir. Um gesto que a tela manda e o
            # Python não conhece é defeito de um dos dois lados, e calar
            # esconderia qual.
            print(f"gesto DESCONHECIDO, recusado: {objeto!r}", file=sys.stderr)
            return
        self.gestos.append(objeto)
        alvo = objeto.get("alvo") or "—"
        valor = objeto.get("valor") or objeto.get("texto") or ""
        print(f"gesto: {objeto['gesto']} · alvo {alvo} · {valor}")

    # -- o relato ----------------------------------------------------------
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
            f"voltas: {self.voltas} · remontagens: {self.remontagens} · "
            f"gestos: {len(self.gestos)}",
            f"valores escritos por pintura: {sorted(set(self.valores)) or 'NENHUM'}",
            resumo("IPC ", self.custos_ipc),
            resumo("tela", self.custos_tela),
            resumo("volta", self.custos),
        ]
        if self.custos:
            s = sorted(self.custos)
            med = s[len(s) // 2]
            linhas.append(
                f"orçamento: {med / TIQUE_MS * 100:.1f}% dos {TIQUE_MS} ms do tique"
            )
        # A RÉGUA POR BLOCO, e ela é o que uma volta só esconde: uma régua de
        # 29/08 rodou o tique UMA VEZ e não viu uma regressão que só aparecia
        # aos 181 segundos. Aqui a deriva aparece como a mediana subindo de
        # bloco para bloco.
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
    p.add_argument("--sem-ponte", action="store_true", help="a MORDIDA: sem pintura nenhuma")
    p.add_argument("--arranca-enderecos", action="store_true",
                   help="MORDIDA: apaga os data-v e prova que a pintura desaba")
    p.add_argument("--prova-gesto", action="store_true",
                   help="cliques sintéticos, e prova que o gesto chega ao Python")
    p.add_argument("--duble", help="JSON com um state_full — em vez do daemon")
    p.add_argument("--mesa-duble", help="JSON com a mesa de rádio, o exame e a ordem")
    args = p.parse_args()

    if not PAGINA.exists():
        print(f"ERRO: a página desta aba não está em {PAGINA}", file=sys.stderr)
        return 2

    j = Janela(args)
    Gtk.main()
    print("\n" + j.relato())

    # UMA BANCADA QUE NÃO DEU UMA VOLTA NÃO MEDIU NADA, E NÃO SAI VERDE — a
    # guarda que a `jogar_vivo.main` ganhou na `ONDA5-07-03`, estendida às cinco
    # na costura da ONDA C. O defeito que ela cobra é o de rc=0 sobre janela
    # vazia; aqui a página existe, e a guarda é o que impede o dia em que ela
    # deixar de existir de passar calado. O `--sem-ponte` é a exceção e é a
    # MORDIDA: ele desliga a pintura de propósito.
    if j.voltas == 0 and not args.sem_ponte:
        print("ERRO: a bancada não deu uma volta — nada foi medido.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
