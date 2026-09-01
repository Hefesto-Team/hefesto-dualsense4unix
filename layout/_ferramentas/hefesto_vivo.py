#!/usr/bin/env python3
"""O PILOTO ÚNICO: uma janela, as dez abas, tudo pintado pelo despachante.

DECISÃO DELA, 01/09/2026: *"melhor assim mesmo. aba a aba. igual vc falou. mas
já usando o trabalho do specs pra fazermos tudo de uma vez. já o trampo final."*
E depois: *"a única que não faremos, só deixamos o botão levando pra ela, é a de
lançadores."*

O QUE ELE SUBSTITUI, e é o motivo de existir: até aqui havia CINCO pilotos, um
por aba — `controles_vivos`, `jogar_vivo`, `conexoes_vivas`, `perfis_vivos`,
`sistema_viva`. Cada um abre a sua página e morre nela; clicar na tira levava a
uma página ESTÁTICA, o mockup sem dado. O produto que ela pediu é uma janela em
que as dez abas estão vivas e a navegação entre elas funciona.

COMO ELE SABE O QUE PINTAR: pelo nome do arquivo à vista. O `load-changed` do
WebView chega em toda carga, e o `pacotes.pacote_da_pagina()` devolve o pacote
daquela página — ou `None`, que quer dizer "esta aba ainda não tem quem a pinte"
e é diferente de um pacote vazio.

AS DUAS LÍNGUAS, e a tradução mora AQUI de propósito:

    o daemon fala `uniq`   — `d4:2f:…`, o endereço do aparelho
    o desenho fala `pref`  — `p1`, `p2`, que é o que o `data-controle` traz

As funções de pacote falam a língua do daemon, porque é dele que leem. A tela
fala a língua do desenho, porque é o mockup dela. Traduzir no pacote misturaria
as duas e faria cada aba carregar a mesa; traduzir no JS espalharia a regra por
dez páginas. Fica no piloto, que é quem já tem a mesa na mão.
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import threading
import time

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
for _p in (str(AQUI), str(RAIZ / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
import mesa_viva  # noqa: E402
import onde  # noqa: E402
import pacotes  # noqa: E402
from gi.repository import GLib, Gtk  # noqa: E402

from hefesto_dualsense4unix.gui.ponte_da_tela import JanelaDaAba  # noqa: E402

#: A PRIMEIRA PÁGINA é a Jogar, que é a primeira da tira. Não é escolha de
#: gosto: é a aba que o `.desktop` dela abre.
PRIMEIRA = "01-jogar.html"

#: O tique da pintura. 500 ms é o mesmo do `controles_vivos`, medido lá: o custo
#: por volta ficou em 0,9% do orçamento, com IPC de mediana 0,8 ms.
TIQUE_MS = 500

#: A aba que NÃO tem pacote, por decisão dela — só o botão que leva a ela.
SEM_PACOTE = {"07-lancadores.html"}

#: O QUE A GUARDA DE CARGA ACEITA. Os pilotos de uma aba só passavam o nome
#: dela — `"Controles"` — e a guarda matava a janela em qualquer outra página.
#: Aqui as DEZ são legítimas, então o esperado é o que as dez compartilham:
#:
#:     Hefesto — aba JOGAR (mockup 26/08/2026)
#:     Hefesto — aba GATILHOS (mockup 26/08/2026)
#:
#: A guarda casa por SUBSTRING, e `"Jogar"` não casa com `"aba JOGAR"` — foi o
#: que matou a primeira execução deste piloto. Continua servindo para o que ela
#: existe: uma página que NÃO é do mockup (um erro de carga, um `about:blank`)
#: não tem este título e a guarda a pega.
TITULO_DE_QUALQUER_ABA = "Hefesto — aba "

#: O BOOTSTRAP: uma função de pintura, genérica, para as dez.
#:
#: Ela NÃO sabe nada de nenhuma aba — recebe endereço e valor e escreve. Toda a
#: inteligência está do lado Python, nos pacotes, que são puros e testáveis sem
#: abrir janela. Foi assim que 143 valores puderam ser medidos antes de existir
#: esta janela.
#:
#: O CONTADOR É O QUE IMPEDE O VERDE SOBRE NADA. `pintar()` devolve quantos
#: valores escreveu, e o piloto imprime. Uma aba que devolve 0 com pacote não
#: vazio é endereço que não existe na página — e é o defeito que fez a
#: `06-navegacao` publicar zero endereços em 01/09 sem ninguém ver.
BOOTSTRAP = r"""
(function(){
  window.__hef = window.__hef || {};
  function escrever(el, v){
    if(!el) return 0;
    const t = (v === null || v === undefined || v === '') ? '—' : String(v);
    // O ALVO PADRÃO É O TEXTO. `data-hef-alvo` desvia para um atributo quando a
    // tela precisa de outra coisa — a largura de uma barra, o `value` de um
    // campo. Sem isso, pintar uma barra escreveria o número DENTRO dela.
    const alvo = el.dataset.hefAlvo || 'texto';
    if(alvo === 'largura'){
      if(el.style.width !== t + '%'){ el.style.width = t + '%'; return 1; }
      return 0;
    }
    if(alvo === 'fundo'){
      if(el.style.background !== t){ el.style.background = t; return 1; }
      return 0;
    }
    if(alvo === 'valor'){ if(el.value !== t){ el.value = t; return 1; } return 0; }
    if(el.textContent !== t){ el.textContent = t; return 1; }
    return 0;
  }
  // OS TRÊS VOCABULÁRIOS DE ENDEREÇO, e nenhum se aposenta. Medido em
  // 01/09/2026, nas dez páginas publicadas:
  //
  //     data-campo   oito abas          o mais novo, e o do piloto único
  //     data-papel   só a Vibração (28) um PAR com `data-lado`
  //     data-hef     só a Perfis (77)   nomes com ponto: `perfis.linha.nome`
  //
  // Cada um nasceu com o piloto da sua aba, e os pilotos ainda os usam. Trocar
  // tudo por um só renomearia 105 endereços e quebraria cinco pilotos vivos
  // para ganhar consistência de nome — o piloto único aceita os três, que é o
  // que custa uma linha aqui.
  function achar(raiz, chave){
    const esc = chave.replace(/"/g, '\\"');
    return raiz.querySelectorAll(
      '[data-campo="' + esc + '"],[data-papel="' + esc + '"],[data-hef="' + esc + '"]');
  }
  window.__hef.pintar = function(p){
    let n = 0;
    // A FITA SE TROCA INTEIRA, e não campo a campo: o número de chips muda com
    // a mesa, e não há endereço para um chip que ainda não existe.
    if(p.fita){
      const f = document.querySelector('.fita');
      if(f && f.outerHTML !== p.fita){ f.outerHTML = p.fita; n += 1; }
    }
    // 1. OS CAMPOS DA MESA — soltos no documento, valem para a página toda.
    for(const [k, v] of Object.entries(p.mesa || {})){
      const alvos = achar(document, k);
      // UMA LISTA SE DISTRIBUI pelos elementos de mesmo endereço, na ordem.
      // É como a aba Conexões mostra os achados do exame e a Perfis a lista de
      // perfis: N blocos iguais, um por item, todos com o mesmo `data-campo`.
      // Sem isto o pacote teria de emitir `achado-0`, `achado-1`… e o gerador
      // teria de saber de antemão QUANTOS itens o exame acha.
      if(Array.isArray(v)){
        alvos.forEach(function(el, i){ n += escrever(el, i < v.length ? v[i] : ''); });
        continue;
      }
      if(v !== null && typeof v === 'object') continue;
      for(const el of alvos) n += escrever(el, v);
    }
    // 2. OS CAMPOS POR CONTROLE — dentro do bloco daquele `data-controle`.
    for(const [pref, campos] of Object.entries(p.colunas || {})){
      for(const raiz of document.querySelectorAll('[data-controle="' + pref + '"]')){
        for(const [k, v] of Object.entries(campos)){
          if(v !== null && typeof v === 'object') continue;
          for(const el of achar(raiz, k)) n += escrever(el, v);
        }
      }
    }
    return n;
  };
  return 'ok';
})();
"""


def _fita(mesa: list[dict]) -> str:
    """A fita de chips com a mesa VIVA, pelo mesmo gerador do desenho.

    `monta.fita()` é o dono dela nas dez páginas. Passar `mesa` é obrigatório:
    sem o argumento ele cai nos `CONECTADOS` do mockup, que são derivados no
    IMPORT e nunca recalculados — trocar `monta.MESA` de fora não alcança.
    """
    if not mesa or any(not c.get("cor") for c in mesa):
        # A COR AINDA NÃO CHEGOU. O leitor do plástico é perguntado em thread e
        # a mesa nasce sem cor — `monta.fita` levanta `SystemExit: colorway ''
        # não existe` nesse instante. Devolver "" deixa a fita como está e o
        # tique seguinte a pinta; erguer aqui derrubaria a aba inteira por meio
        # segundo de espera.
        #
        # `SystemExit` NÃO é `Exception` — herda de `BaseException`, e um
        # `except Exception` passa ao lado. Foi o que aconteceu na primeira
        # execução: o piloto morreu com a mensagem do portão de cores, que é um
        # portão e está certo em erguer.
        return ""
    try:
        import monta

        return monta.fita(ativo=(mesa[0]["pref"] if mesa else "todos"), mesa=mesa)
    except (Exception, SystemExit):
        return ""


def _pagina_da_uri(uri: str | None) -> str:
    """O nome do arquivo à vista, ou `""`.

    É o que o despachante usa de chave, e é o que o `load-changed` entrega. Sai
    da URI e não de um estado que o piloto guarde: guardar seria uma segunda
    fonte da verdade sobre em que aba a janela está, e as duas divergiriam na
    primeira navegação que falhasse no meio.
    """
    if not uri:
        return ""
    return uri.rstrip("/").split("/")[-1].split("?")[0].split("#")[0]


class Piloto:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.pronto = False
        self.agendado = False
        self.relatou = False
        self.pagina = PRIMEIRA
        self.voltas = 0
        #: Quantos valores cada aba pintou, na ordem em que foram visitadas. É o
        #: relato do fim, e é o que distingue "a aba não tem dado" de "a aba tem
        #: pacote e nenhum endereço casou".
        self.pinturas: dict[str, list[int]] = {}
        self.visitadas: list[str] = []
        self.custos: list[float] = []
        self.leitor = mesa_viva.LeitorDeCor(ligado=not args.sem_cor)
        #: Os `uniq` já perguntados ao leitor de cor. Sem esta trava, cada tique
        #: abriria uma thread nova para o mesmo controle — 2 por segundo.
        self.perguntados: set[str] = set()

        self.tela = JanelaDaAba(
            arquivo=onde.pagina(PRIMEIRA, publicado=True),
            titulo_esperado=TITULO_DE_QUALQUER_ABA,
            ao_carregar=self._instalar,
            ao_sair_da_aba=self._navegou,
            oculta=args.oculta,
            subtitulo="as dez abas, vivas",
        )
        self.view = self.tela.view
        self.ponte = self.tela.ponte
        # O SEGUNDO OUVINTE, e ele precisa ser próprio: o `ao_sair_da_aba` da
        # biblioteca dispara UMA vez, na saída da aba desta janela. Daqui em
        # diante toda página é "fora da aba" e o callback não volta. Sem este
        # `connect`, Jogar → Gatilhos → Jogar não produziria evento nenhum e o
        # piloto ficaria pintando a página errada. É a mesma nota que o
        # `controles_vivos` carrega, e a razão é a mesma.
        self.view.connect("load-changed", self._carregou)

    # -- navegação ---------------------------------------------------------
    def _navegou(self, titulo: str) -> None:
        """Ela clicou na tira. Aqui isso não pausa nada — é o ponto do piloto."""
        print(f"[navegou] {titulo}")

    def _carregou(self, _view, evento) -> None:
        from gi.repository import WebKit2

        if evento != WebKit2.LoadEvent.FINISHED:
            return
        nova = _pagina_da_uri(self.view.get_uri())
        if not nova or (nova == self.pagina and self.pronto):
            return
        self.pagina = nova
        if nova not in self.visitadas:
            self.visitadas.append(nova)
        # A PONTE MORRE A CADA CARGA — o `window.__hef` é do documento antigo.
        # Reinstalar é obrigatório, e esquecer isso é como uma aba nova nasce
        # muda sem uma linha de erro.
        self.pronto = False
        self.ponte.perguntar(BOOTSTRAP, self._instalado)

    def _instalar(self) -> None:
        self.ponte.perguntar(BOOTSTRAP, self._instalado)

    def _instalado(self, _valor, erro) -> None:
        if erro is not None:
            print(f"ERRO: o bootstrap não instalou em {self.pagina}: {erro}", file=sys.stderr)
            return
        self.pronto = True
        # O TIMER E A SAÍDA SÓ UMA VEZ, e a flag é própria. Testar `voltas == 0`
        # aqui não funciona: `_tique()` roda logo acima e já a incrementa, então
        # a condição era sempre falsa — a janela ficava viva para sempre, sem
        # tique periódico e sem relato. Medido na primeira execução deste piloto.
        self._tique()
        if not self.agendado:
            self.agendado = True
            GLib.timeout_add(TIQUE_MS, self._tique)
            self._agendar()

    # -- a pintura ---------------------------------------------------------
    def _contexto(self, st: dict) -> tuple[pacotes.Contexto, dict[str, str]]:
        """O contexto do tique, e o dicionário `uniq → pref` para traduzir."""
        ctx_conectados = [c for c in (st.get("controllers") or [])
                          if c.get("connected", True)]
        # A COR DO PLÁSTICO vem do leitor, que responde `{}` até a primeira
        # pergunta voltar — por isso a mesa nasce "Não sei" e vira "Starlight
        # Blue" na segunda remontagem. Perguntar é BLOQUEANTE (fala com o
        # aparelho), então vai em thread: no tique ela travaria a janela.
        for c in ctx_conectados:
            uniq = str(c.get("uniq") or "")
            if uniq and uniq not in self.perguntados:
                self.perguntados.add(uniq)
                threading.Thread(
                    target=self.leitor.perguntar, args=(uniq,), daemon=True
                ).start()
        conectados = ctx_conectados
        mesa = mesa_viva.mesa_do_estado(st, self.leitor.conhecidos())
        para_pref = {str(c.get("uniq") or ""): c["pref"] for c in mesa}
        ctx = pacotes.Contexto(state=st, mesa=mesa, conectados=conectados, estados={})
        return ctx, para_pref

    def _tique(self) -> bool:
        if not self.pronto:
            return True
        t0 = time.perf_counter()
        try:
            st = mesa_viva.estado_do_daemon()
        except Exception as e:
            print(f"[daemon mudo] {e}", file=sys.stderr)
            return True

        try:
            ctx, para_pref = self._contexto(st)
        except Exception as e:
            print(f"[mesa] não montou: {e}", file=sys.stderr)
            return True
        try:
            pacote = pacotes.pacote_da_pagina(self.pagina, ctx)
        except Exception as e:
            # UMA ABA QUE LEVANTA NÃO DERRUBA A JANELA. Ela para de pintar e o
            # motivo sai no relato — que é diferente de a tela congelar sem
            # dizer por quê, e é o estado que o `Contexto.por_uniq` já protege.
            print(f"[{self.pagina}] o pacote levantou: {e}", file=sys.stderr)
            return True
        if pacote is None:
            return True

        # A FORMA CANÔNICA E A TRADUÇÃO `uniq → pref`, as duas no despachante.
        # Ele é quem conhece as três palavras que as abas usam para a mesma
        # coisa (`colunas`, `cartoes`, `cards`) e o que cada uma deixa solto na
        # raiz. Repetir isso aqui seria um segundo dono da mesma regra.
        carga = pacotes.normalizar(pacote, para_pref)
        # O CABEÇALHO É DE TODAS AS ABAS, e não de nenhum pacote: a contagem e o
        # perfil ativo moram no `topo.html`, que é um só para as dez. Sem esta
        # linha os três campos ficavam vazios em TODA aba — cada pacote cuidava
        # da sua e ninguém cuidava do que era de todas.
        for chave, valor in pacotes.topo(ctx).items():
            carga["mesa"].setdefault(chave, valor)

        # A FITA É DE TODAS AS ABAS, e ela MENTE se não for repintada: o HTML
        # publicado traz os dois chips do mockup ("P1 · Cosmic Red · USB",
        # "P2 · Starlight Blue · BT"), e com UM controle no cabo a tela dizia
        # que havia dois, um deles no rádio. É a quinta reincidência do mesmo
        # defeito nesta casa — *uma frase que nomeia um controle fora da mesa* —
        # e a foto da aba Perfis o mostrou de novo em 01/09/2026, já com o topo
        # e a tabela corretos ao lado.
        carga["fita"] = _fita(ctx.mesa)

        def contou(valor, erro) -> None:
            if erro is not None:
                print(f"[{self.pagina}] a pintura falhou: {erro}", file=sys.stderr)
                return
            try:
                n = int(str(valor))
            except (TypeError, ValueError):
                n = -1
            # O `-1` (página trocada no meio) NÃO entra na conta: contá-lo
            # como zero faria uma aba viva parecer muda na travessia.
            if n >= 0:
                self.pinturas.setdefault(self.pagina, []).append(n)

        # A GUARDA `window.__hef &&` NÃO É ZELO: entre o tique começar e o JS
        # rodar, a página pode ter trocado — e o `__hef` é do DOCUMENTO, morre
        # com ele. Medido em 01/09/2026, passeando pelas dez: duas abas
        # devolviam `TypeError: undefined is not an object` a cada travessia.
        # O `-1` diz "a página trocou no meio", que é diferente de "pintei
        # nada" — e o relato conta os dois separados.
        self.ponte.perguntar(
            f"(window.__hef && window.__hef.pintar({_json(carga)})) || -1", contou)
        self.voltas += 1
        self.custos.append((time.perf_counter() - t0) * 1000)
        return True

    # -- o roteiro e o relato ---------------------------------------------
    def _agendar(self) -> None:
        if self.args.passear:
            # O PASSEIO: clica a tira aba por aba, para provar que as dez
            # pintam. Sem ele o relato só teria a primeira — e "a aba abre" não
            # é o mesmo que "a aba pinta", que é a distinção inteira desta leva.
            for i, alvo in enumerate(sorted(pacotes.PACOTES)):
                GLib.timeout_add(
                    1200 + i * self.args.parada,
                    lambda a=alvo: (self._ir(a), False)[1],
                )
            total = 1600 + len(pacotes.PACOTES) * self.args.parada
        else:
            total = int(self.args.segundos * 1000)
        GLib.timeout_add(total, lambda: (self._relatar(), Gtk.main_quit(), False)[2])

    def _ir(self, pagina: str) -> None:
        self.view.load_uri(onde.pagina(pagina, publicado=True).as_uri())

    def _relatar(self) -> None:
        # UMA VEZ SÓ. O `_agendar` roda no `_instalado`, que dispara a cada
        # carga de página; sem esta trava o passeio agendava dez saídas e o
        # relato saía repetido — dois "foto:" no log de 01/09.
        if self.relatou:
            return
        self.relatou = True
        if self.args.foto:
            self.tela.fotografar(self.args.foto)
            print(f"foto: {self.args.foto}")
        print(f"\nvoltas: {self.voltas} · abas visitadas: {len(self.visitadas)}")
        print(f"{'aba':22s} {'pinturas':>8s} {'valores':>8s}")
        mudas = []
        for pagina in sorted(pacotes.PACOTES):
            conta = self.pinturas.get(pagina) or []
            pico = max(conta) if conta else 0
            print(f"{pagina:22s} {len(conta):8d} {pico:8d}")
            if conta and pico == 0:
                mudas.append(pagina)
        if self.custos:
            ordenado = sorted(self.custos)
            print(f"custo do tique: mediana {ordenado[len(ordenado)//2]:.2f} ms · "
                  f"max {ordenado[-1]:.2f} ms")
        if mudas:
            # ZERO É ERRO, NÃO SILÊNCIO. Uma aba que foi visitada, tem pacote e
            # escreveu zero valores é endereço que não casou — e essa é a forma
            # exata do defeito que deixou a `06-navegacao` publicar sem
            # endereço nenhum.
            print(f"\nABAS MUDAS (pacote sem endereço que case): {', '.join(mudas)}")
            raise SystemExit(1)


def _json(obj) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, default=str)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--oculta", action="store_true",
                   help="Gtk.OffscreenWindow — nada aparece na tela dela. "
                        "Ela tem UMA tela; é o padrão de toda régua desta casa.")
    p.add_argument("--segundos", type=float, default=6.0)
    p.add_argument("--passear", action="store_true",
                   help="visita as dez abas e mede a pintura de cada uma")
    p.add_argument("--parada", type=int, default=900,
                   help="ms em cada aba durante o passeio")
    p.add_argument("--foto", default="")
    p.add_argument("--abre", default="", help="abrir direto numa aba")
    p.add_argument("--sem-cor", action="store_true",
                   help="MORDIDA: sem o leitor de cor do plástico")
    args = p.parse_args()

    piloto = Piloto(args)
    if args.abre:
        GLib.timeout_add(400, lambda: (piloto._ir(args.abre), False)[1])
    Gtk.main()


if __name__ == "__main__":
    main()
