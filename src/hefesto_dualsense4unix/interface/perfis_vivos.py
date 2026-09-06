#!/usr/bin/env python3
"""perfis_vivos.py — a aba Perfis VIVA: o desenho dela com os perfis do disco.

O mockup aprovado rodando num `WebKit2.WebView` dentro de uma janela GTK3
(`D-A-INTERFACE-NOVA-E-O-MOCKUP-DENTRO-DE-UMA-JANELA-GTK`), com os perfis vindo
do DISCO e o perfil ativo vindo do daemon. **Esta é a aba menos dependente do
daemon das dez**: o que ela pinta sai de `profiles/loader.load_all_profiles`, e
só o nome do perfil ativo e a mesa de controles precisam do IPC.

    perfis_vivos.py                        # a janela, na tela
    perfis_vivos.py --oculta               # Gtk.OffscreenWindow: nada aparece
    perfis_vivos.py --oculta --segundos 4 --foto a.png

AS DUAS MORDIDAS, as mesmas do piloto da aba Controles:

    --sem-ponte           desliga a ponte: a tela tem de ficar na cena FIXA do
                          mockup (14 perfis, "Mortal Kombat" ativo, quatro
                          controles). Se ela mostrar os perfis dela, o dado não
                          está vindo do Python.
    --arranca-enderecos   apaga os `data-hef` que o `aba10.py` escreve: a
                          pintura tem de DESABAR. Se não desabar, os endereços
                          não estavam sendo usados.

E o resto:

    --duble a.json        os perfis e o estado vêm de um roteiro, não do disco
                          nem do daemon. É o PADRÃO, e é de propósito: os perfis
                          dela têm nome de jogo, e uma foto versionada com eles
                          seria a biblioteca dela num PNG (a mesma razão do
                          `retratar_abas._PERFIS_DA_FOTO`).
    --do-disco            lê os perfis DELA de verdade (`load_all_profiles`).
                          Não fotografe com isto ligado.
    --prova-gesto         cliques sintéticos, para provar tela → Python → eco

ESTA LEVA NÃO ESCREVE NADA. Nenhum método de escrita é pronunciado: o único IPC
é `daemon.state_full` (via `mesa_viva.METODO`) e o único acesso a disco é de
LEITURA. Os gestos chegam ao Python, são registrados com o DONO REAL declarado
em `perfis_web.DONOS_DOS_GESTOS` e ecoam de volta. Nenhum perfil dela é tocado.

A JANELA, AS DUAS PONTES E A GUARDA DE CARGA são da biblioteca
(`hefesto_dualsense4unix.gui.ponte_da_tela`), e o que decide o que a tela recebe
é `hefesto_dualsense4unix.app.actions.perfis_web` — os dois versionados. O que
sobra aqui é a costura: quem lê o disco, quem lê o daemon, e o JavaScript da
página.

A ARMADILHA QUE É DESTE ARQUIVO, e não da ponte: **nome de perfil é DADO DELA
dentro de uma PÁGINA.** Num `Gtk.TreeView` um perfil chamado `<b>x</b>` é o
texto `<b>x</b>`; numa página, é markup. Por isso nenhuma linha desta tela é
montada por concatenação de HTML: o ajudante CLONA o `<tr>` que o `aba10.py`
escreveu e preenche cada endereço por `textContent`. O desenho continua com um
dono só, e nenhum caractere dela atravessa a fronteira como marcação.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from typing import Any

# A JANELA, AS DUAS PONTES E A GUARDA DE CARGA VÊM DA BIBLIOTECA, e é ela que
# crava os quatro pinos de `gi.require_version` (com o Gdk DEPOIS do Gtk).
# Importá-la ANTES de `gi.repository` é o que garante a ordem.
from hefesto_dualsense4unix.gui.ponte_da_tela import JanelaDaAba  # noqa: E402  isort:skip

from gi.repository import GLib, Gtk  # noqa: E402

from hefesto_dualsense4unix.app.actions import perfis_web  # noqa: E402

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import mesa_viva  # noqa: E402
import monta  # noqa: E402  (o gerador do mockup, usado como BIBLIOTECA)
import onde  # noqa: E402  (o dono das duas pastas: bancada e publicado)

import aba10  # noqa: E402  isort:skip

# O DONO DA PASTA RESPONDE, e o caminho não se soletra — 06/09/2026, costura da
# ONDA C. Aqui estava `AQUI.parent / "10-perfis.html"`, que era certo enquanto
# esta bancada morava em `layout/_ferramentas/` e apontava para
# `hefesto_dualsense4unix/10-perfis.html` desde a mudança para `src/`: um
# arquivo que não existe. É o gêmeo do defeito que a `ONDA5-07-03` achou na
# `jogar_vivo.py`, e as duas apagavam o mesmo jeito — "ERRO DE CARGA",
# `voltas: 0` e `rc=0`.
PAGINA = onde.PUBLICADO / "10-perfis.html"
TITULO_ESPERADO = "Hefesto — aba PERFIS"

#: O tique desta aba. A Controles lê o `state_full` a 10 Hz porque desenha
#: analógico e giroscópio; aqui o dado é perfil em DISCO — ele não muda dez
#: vezes por segundo, e reler o disco nessa cadência seria pagar I/O por nada.
#: 500 ms é o mesmo período da faixa "devagar" do produto
#: (`app/constants.SLOW_POLL_INTERVAL_MS`), e é ele que entra na conta de
#: orçamento do relato.
TIQUE_MS = 500

#: O tique RÁPIDO, o mesmo da janela de hoje: é ele que traz o perfil ativo e a
#: mesa. Quem muda depressa nesta aba é o que vem do daemon, não o disco.
TIQUE_RAPIDO_MS = 100

#: A cor do plástico quando o aparelho não a respondeu. Mesma saída do piloto da
#: Controles: a borda neutra do tema é o "não sei" desta linha.
PLASTICO_DESCONHECIDO = "var(--border-forte)"

_cor_da_zona_real = aba10.cor_da_zona


def _cor_da_zona_tolerante(colorway: str, zona: str = "casca-solida") -> str:
    """`monta.cor_da_zona` PARA a geração quando o colorway não existe — e está
    certo para o mockup, onde a mesa é escrita à mão. Aqui a mesa vem do
    aparelho, e "não sei a cor" é resposta legítima."""
    if not colorway:
        return PLASTICO_DESCONHECIDO
    try:
        return _cor_da_zona_real(colorway, zona)
    except SystemExit:
        return PLASTICO_DESCONHECIDO


aba10.cor_da_zona = _cor_da_zona_tolerante
monta.cor_da_zona = _cor_da_zona_tolerante


# ---------------------------------------------------------------------------
# O JavaScript da ponte — clona o desenho, escreve por TIPO, e conta o que
# escreveu. Nenhuma linha desta tela é HTML vindo do Python.
# ---------------------------------------------------------------------------
BOOTSTRAP = r"""
window.HEF = (function(){
  const qa = (s,r)=>Array.from((r||document).querySelectorAll(s));
  const q  = (s,r)=>(r||document).querySelector(s);

  // AS ESCRITAS DEVOLVEM QUANTOS VALORES ESCREVERAM — 0 quando o endereço não
  // existe. É o que faz a conta do fim ser uma RÉGUA e não um enfeite: com
  // `n++` cego, apagar um endereço não mudaria o número e a régua aprovaria uma
  // pintura que não pinta nada.
  function txt(el,v){ if(!el) return 0; if(el.textContent !== v) el.textContent = v; return 1; }
  function val(el,v){ if(!el) return 0; if(el.value !== v) el.value = v; return 1; }
  function est(el,o){ if(!el) return 0; for(const k in o){ if(el.style[k]!==o[k]) el.style[k]=o[k]; } return 1; }
  function cls(el,c,on){ if(!el) return 0; el.classList.toggle(c, !!on); return 1; }
  function dica(el,v){ if(!el) return 0; if(el.getAttribute('title')!==v) el.setAttribute('title', v); return 1; }
  // TRAVAR É ESCRITA, e por isso conta. Um botão que a tela oferece e o produto
  // recusa é mentira: o `disabled` é o "não dá" dito no lugar certo.
  function trava(el,off){ if(!el) return 0; if(el.disabled!==!!off) el.disabled=!!off; return 1; }
  function prop(el,nome,v){ if(!el) return 0; if(el.style.getPropertyValue(nome)!==v) el.style.setProperty(nome, v); return 1; }

  // OS DOIS MOLDES, TIRADOS DA PRÓPRIA PÁGINA. É isto que faz o desenho ter UM
  // dono: a linha que a tela usa é a que o `aba10.py` escreveu, clonada — nunca
  // uma segunda cópia escrita aqui. E é também o que impede injeção: nada de
  // `innerHTML` com texto dela em lugar nenhum.
  const moldeDoPerfil  = (q('[data-hef="perfis.lista"] tr')  || {cloneNode:()=>null}).cloneNode(true);
  const moldeDaGuarda  = (q('[data-hef="guarda.linhas"] tr') || {cloneNode:()=>null}).cloneNode(true);
  const corpoDaLista   = q('[data-hef="perfis.lista"]');
  const corpoDaGuarda  = q('[data-hef="guarda.linhas"]');
  const tabelaDaLista  = corpoDaLista ? corpoDaLista.closest('table') : null;
  const tabelaDaGuarda = corpoDaGuarda ? corpoDaGuarda.closest('table') : null;

  function manda(o){ window.webkit.messageHandlers.hefesto.postMessage(JSON.stringify(o)); }

  function frase(depois, texto, marca){
    // O ESTADO VAZIO É TEXTO, e vem do Python. Ele nasce e morre por aqui para
    // a tabela nunca ficar como cabeçalho sozinho — que é a "tabela vazia" que
    // esta casa recusa.
    let d = q('.'+marca);
    if(!texto){ if(d) d.remove(); return 0; }
    if(!d){
      d = document.createElement('div');
      d.className = marca;
      d.style.cssText = 'padding:18px 6px;color:var(--comment);font-size:12px;line-height:1.7';
      depois.parentNode.insertBefore(d, depois.nextSibling);
    }
    d.textContent = texto;
    return 1;
  }

  function remonta(m){
    if(!corpoDaLista || !moldeDoPerfil) return 'sem-molde';
    corpoDaLista.innerHTML = '';
    for(const linha of m.lista){
      const tr = moldeDoPerfil.cloneNode(true);
      tr.setAttribute('data-hef-perfil', linha.perfil);
      corpoDaLista.appendChild(tr);
    }
    if(tabelaDaLista) tabelaDaLista.style.display = m.lista.length ? '' : 'none';
    frase(tabelaDaLista, m.lista_vazia, 'vazio-da-lista');
    ligarGestos();
    return 'ok';
  }

  function remontaGuarda(m){
    if(!corpoDaGuarda || !moldeDaGuarda) return 'sem-molde';
    corpoDaGuarda.innerHTML = '';
    for(const linha of m.guarda){
      const tr = moldeDaGuarda.cloneNode(true);
      tr.setAttribute('data-hef-uniq', linha.uniq);
      corpoDaGuarda.appendChild(tr);
    }
    if(tabelaDaGuarda) tabelaDaGuarda.style.display = m.guarda.length ? '' : 'none';
    frase(tabelaDaGuarda, m.guarda_vazia, 'vazio-da-guarda');
    return 'ok';
  }

  function pintaLinha(linha){
    const tr = q('[data-hef-perfil="'+CSS.escape(linha.perfil)+'"]'); if(!tr) return 0;
    let n = 0;
    n += txt(q('[data-hef="perfis.linha.nome"]', tr), linha.nome);
    n += txt(q('[data-hef="perfis.linha.prioridade"]', tr), linha.prioridade);
    n += txt(q('[data-hef="perfis.linha.quando"]', tr), linha.quando);
    n += cls(tr, 'ativo', linha.ativo);
    n += dica(tr, linha.dica);
    return n;
  }

  function pintaGuarda(linha){
    const tr = q('[data-hef-uniq="'+CSS.escape(linha.uniq)+'"]'); if(!tr) return 0;
    let n = 0;
    n += txt(q('[data-hef="guarda.nome"]', tr), linha.nome);
    n += txt(q('[data-hef="guarda.id"]', tr), linha.id);
    n += prop(tr, '--plastico', linha.plastico);
    n += dica(tr, linha.dica);
    for(const g of qa('[data-hef="guarda.secao"]', tr))
      n += cls(g, 'on', !!linha.secoes[g.dataset.hefSecao]);
    return n;
  }

  function pintaEditor(e){
    if(!e) return 0;
    let n = 0;
    n += val(q('[data-hef="editor.nome"]'), e.nome);
    n += est(q('[data-hef="editor.prioridade"]'), {width:e.prioridade});
    n += txt(q('[data-hef="editor.prioridade.n"]'), e.prioridade_n);
    n += dica(q('[data-hef="editor.prioridade.dica"]'), e.prioridade_dica);
    const amb = q('[data-hef="editor.ambiente"]');
    // O TERCEIRO ESTADO DO SELETOR. Perfil que a tela não sabe mostrar não abre
    // dizendo "Todos": o seletor vai TRAVADO com a frase. Abrir mentindo é o
    // defeito R-12 pelo avesso, e o estrago dele já aconteceu nesta casa.
    if(e.ambiente !== null) n += val(amb, e.ambiente);
    n += trava(amb, e.ambiente_travado);
    n += dica(amb, e.ambiente_recado);
    n += val(q('[data-hef="editor.jogo"]'), e.jogo);
    const est_ = q('[data-hef="editor.estilo"]');
    n += trava(est_, e.estilo_travado);
    n += dica(est_, e.estilo_recado);
    return n;
  }

  function pinta(p){
    const t0 = performance.now(); let n = 0;
    n += txt(q('[data-hef="perfis.conta"]'), p.conta);
    n += txt(q('[data-hef="perfis.com-ajuste"]'), p.com_ajuste);
    for(const linha of p.lista)  n += pintaLinha(linha);
    for(const linha of p.guarda) n += pintaGuarda(linha);
    n += pintaEditor(p.editor);
    // OS TRÊS DESLIGADOS. Botão que aceita clique e não faz nada consome a
    // confiança de quem clicou; travar é a resposta honesta, e o `title` diz
    // por quê.
    for(const chave in p.travados){
      const b = q('[data-hef-gesto="'+chave+'"]');
      n += trava(b, true); n += dica(b, p.travados[chave]);
    }
    if(n !== window.__hefN){ window.__hefN = n;
      manda({gesto:'pintou', valores:n, ms: Math.round((performance.now()-t0)*100)/100}); }
    return n;
  }

  function ligarGestos(){
    for(const b of qa('[data-hef-gesto]')){
      if(b.dataset.ligado) continue; b.dataset.ligado='1';
      const evento = (b.tagName === 'SELECT' || b.tagName === 'INPUT') ? 'change' : 'click';
      b.addEventListener(evento, ev=>{
        if(evento === 'click'){ ev.preventDefault(); ev.stopPropagation(); }
        if(b.disabled) return;
        manda({gesto:'botao', qual:b.dataset.hefGesto,
               valor:(b.value !== undefined ? String(b.value) : '')});
      });
    }
    for(const tr of qa('[data-hef-perfil]')){
      if(tr.dataset.ligado) continue; tr.dataset.ligado='1';
      tr.addEventListener('click', ()=>{
        manda({gesto:'linha', perfil:tr.getAttribute('data-hef-perfil')});
      });
    }
  }

  function eco(o){
    // O ECO MORA NA TELA por um tique só: quem decide o que fica é o Python, e
    // o tique seguinte repinta. Aqui o eco existe para o clique dela não sumir
    // meio segundo depois — a mesma razão do piloto da Controles.
    if(o.gesto==='linha'){
      for(const tr of qa('[data-hef-perfil]'))
        tr.classList.toggle('escolhida', tr.getAttribute('data-hef-perfil')===o.perfil);
    }
  }

  ligarGestos();
  return {pinta:pinta, remonta:remonta, remontaGuarda:remontaGuarda, eco:eco,
          quem:function(){ return document.title + '|' + qa('[data-hef-perfil]').length; }};
})();
'HEF-PRONTO'
"""


# ---------------------------------------------------------------------------
# De onde vem o dado
# ---------------------------------------------------------------------------
def perfis_do_disco() -> list[Any]:
    """Os perfis DELA, em LEITURA. `load_all_profiles` e nada mais."""
    from hefesto_dualsense4unix.profiles.loader import load_all_profiles

    return list(load_all_profiles())


def perfis_do_duble(bruto: list[dict[str, Any]]) -> list[Any]:
    """Perfis inventados, validados pelo MESMO esquema do produto.

    Passar pelo `Profile` do pydantic em vez de por um objeto de mentira é o que
    garante que o dublê não possa exprimir um perfil que o disco não poderia
    ter — inclusive na chave de `controllers`, que o esquema canoniza.
    """
    from hefesto_dualsense4unix.profiles.schema import Profile

    return [Profile.model_validate(p) for p in bruto]


def mesa_de_agora(state: dict[str, Any] | None) -> list[dict[str, Any]]:
    """A mesa no formato que o `perfis_web` espera, pelo gerador do mockup.

    `rotulo` e `plastico` saem de `monta.rotulo` e `aba10.cor_da_zona` — os
    mesmos que desenham o mockup —, e não de texto escrito aqui. É o que faz o
    desenho ACOMPANHAR a mudança: quando ela mudar a gramática do rótulo, esta
    aba muda junto, sem ninguém reescrever nada.
    """
    if not state:
        return []
    mesa = mesa_viva.mesa_do_estado(state, {})
    for controle in mesa:
        controle["rotulo"] = monta.rotulo(controle, "curta")
        controle["plastico"] = _cor_da_zona_tolerante(str(controle.get("cor") or ""))
    return mesa


# ---------------------------------------------------------------------------
# A janela
# ---------------------------------------------------------------------------
class Janela:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.pronto = False
        self.chaves: tuple = ()
        self.chaves_da_guarda: tuple = ()
        self.custos: list[float] = []
        self.custos_disco: list[float] = []
        self.custos_tela: list[float] = []
        self.voltas = 0
        self.remontagens = 0
        self.rss: list[int] = []
        self.gestos: list[dict[str, Any]] = []
        self.valores: list[int] = []
        #: O que ela escolheu na lista. Mora SÓ AQUI, na memória desta janela —
        #: nunca no perfil dela — e some quando a janela fecha.
        self.escolhido: str | None = None
        self.perfis: list[Any] = []
        self.ativo: str | None = None
        self.mesa: list[dict[str, Any]] = []
        self.daemon_vivo = True
        self._duble: dict[str, Any] | None = None

        self.tela = JanelaDaAba(
            arquivo=PAGINA,
            titulo_esperado=TITULO_ESPERADO,
            ao_carregar=self._instalar,
            ao_receber=self._gesto,
            ao_sair_da_aba=self._saiu_da_aba,
            oculta=args.oculta,
            subtitulo="Perfis — os do disco",
        )
        self.view = self.tela.view
        self.ponte = self.tela.ponte
        self.janela = self.tela.janela

    # -- carga -------------------------------------------------------------
    def _saiu_da_aba(self, titulo: str) -> None:
        self.pronto = False
        print(f"[fora da Perfis] {titulo} — o mockup estático; a pintura pausou.")

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
            self._tique()
            GLib.timeout_add(TIQUE_MS, self._tique)
            if self.args.prova_gesto:
                self._marcar_gestos_de_mentira()
            if self.args.arranca_enderecos:
                # A MORDIDA DO ENDEREÇO: arranca os `data-hef` e vê a pintura
                # DESABAR. Um endereço a menos não levanta erro nenhum no
                # WebKit — o `querySelector` devolve `null` e o valor
                # simplesmente não é escrito. `data-hef-perfil` e
                # `data-hef-uniq` ficam de fora de propósito: arrancá-los
                # derruba a pintura inteira de uma vez, e a queda deixaria de
                # dizer QUAL endereço morreu.
                GLib.timeout_add(
                    1500,
                    lambda: (
                        self._js(
                            "for(const e of document.querySelectorAll("
                            "'[data-hef],[data-hef-secao],[data-hef-gesto]'))"
                            "{for(const a of ['hef','hefSecao','hefGesto'])"
                            " delete e.dataset[a];} window.__hefN=-1;"
                        ),
                        False,
                    )[1],
                )
            self._agendar_saida()

        self.ponte.perguntar(BOOTSTRAP, pronto)

    def _marcar_gestos_de_mentira(self) -> None:
        """Cliques SINTÉTICOS, para provar o caminho tela → Python → eco.

        `el.click()` percorre o MESMO caminho de eventos do clique do rato: o
        `addEventListener` do bootstrap é o que responde. Clicar por coordenada
        é a armadilha que esta casa já pagou duas vezes.

        A ORDEM É A MORDIDA. O "Detectar" e o "Voltar à de ontem" são clicados
        junto dos que funcionam, e têm de produzir ZERO gestos — eles nascem
        travados porque não têm motor. Uma régua que só clicasse os vivos não
        distinguiria "travado" de "sem ouvinte", que é o defeito de origem dos
        três botões de som da aba Controles.
        """
        roteiro = [
            (1200, "document.querySelectorAll('[data-hef-perfil]')[1].click()"),
            (1500, "document.querySelector('[data-hef-gesto=\"ativar\"]').click()"),
            (1800, "document.querySelector('[data-hef-gesto=\"detectar\"]').click()"),
            (2100, "document.querySelector('[data-hef-gesto=\"voltar-a-de-ontem\"]').click()"),
            (2400, "document.querySelector('[data-hef-gesto=\"recarregar\"]').click()"),
        ]
        for ms, script in roteiro:
            GLib.timeout_add(ms, lambda s=script: (self._js(s), False)[1])

    def _agendar_saida(self) -> None:
        foto = self.args.foto
        self.tela.agendar_saida(
            self.args.segundos or 0.0,
            antes=(lambda: self.tela.fotografar(foto)) if foto else None,
        )

    # -- as fontes ---------------------------------------------------------
    def _carregar_duble(self) -> dict[str, Any]:
        if self._duble is None:
            self._duble = json.loads(pathlib.Path(self.args.duble).read_text(encoding="utf-8"))
        return self._duble

    def _ler(self) -> None:
        """Os perfis, o ativo e a mesa — cada um da sua fonte, e nenhum inventado."""
        if self.args.do_disco:
            self.perfis = perfis_do_disco()
        else:
            self.perfis = perfis_do_duble(self._carregar_duble().get("perfis", []))

        state: dict[str, Any] | None = None
        if self.args.duble and not self.args.do_daemon:
            state = self._carregar_duble().get("state")
            self.daemon_vivo = state is not None
        else:
            try:
                state = mesa_viva.estado_do_daemon()
                self.daemon_vivo = True
            except mesa_viva.DaemonMudo as erro:
                state = None
                self.daemon_vivo = False
                if self.voltas == 0:
                    print(f"[daemon mudo] {erro}")
        self.ativo = str(state.get("active_profile") or "") or None if state else None
        self.mesa = mesa_de_agora(state)

    # -- o tique -----------------------------------------------------------
    def _tique(self) -> bool:
        if not self.pronto:
            return True
        t0 = time.perf_counter()
        self._ler()
        t_disco = (time.perf_counter() - t0) * 1000

        pacote = perfis_web.pacote_da_aba(
            self.perfis,
            ativo=self.ativo,
            mesa=self.mesa if self.daemon_vivo else None,
            daemon_vivo=self.daemon_vivo,
            editado=self._perfil_editado(),
        )

        t1 = time.perf_counter()
        chaves = tuple(linha["perfil"] for linha in pacote["lista"])
        if chaves != self.chaves:
            self.remontagens += 1
            self.ponte.dizer("HEF.remonta", pacote)
            self.chaves = chaves
            print(f"[remonta #{self.remontagens}] {len(chaves)} perfil(is) na lista")
        chaves_guarda = tuple(linha["uniq"] for linha in pacote["guarda"])
        if chaves_guarda != self.chaves_da_guarda:
            self.ponte.dizer("HEF.remontaGuarda", pacote)
            self.chaves_da_guarda = chaves_guarda
            print(f"[remonta guarda] {len(chaves_guarda)} controle(s) na mesa")
        self.ponte.dizer("HEF.pinta", pacote)
        t_tela = (time.perf_counter() - t1) * 1000

        self.custos_disco.append(t_disco)
        self.custos_tela.append(t_tela)
        self.custos.append(t_disco + t_tela)
        self.voltas += 1
        # UM VAZAMENTO NÃO APARECE NO RELÓGIO — aparece na memória. A remontagem
        # troca o `innerHTML` do corpo, e um listener não removido por
        # remontagem seria invisível numa régua de tempo.
        if self.voltas % 20 == 0:
            try:
                with open("/proc/self/status", encoding="utf-8") as arq:
                    for linha in arq:
                        if linha.startswith("VmRSS:"):
                            self.rss.append(int(linha.split()[1]))
                            break
            except OSError:
                pass
        return True

    def _perfil_editado(self) -> Any:
        if not self.escolhido:
            return None
        return next(
            (p for p in self.perfis if str(getattr(p, "name", "")) == self.escolhido), None
        )

    # -- a ponte -----------------------------------------------------------
    def _js(self, script: str) -> None:
        self.ponte.rodar(script)

    def _gesto(self, o: dict) -> None:
        """tela → Python, já em JSON. Quem recusa o que não for objeto JSON é a
        `PonteDaTela`; o que chega aqui é gesto de verdade."""
        self.gestos.append(o)
        gesto = o.get("gesto")
        if gesto == "pintou":
            self.valores.append(int(o.get("valores") or 0))
            print(f'[pintura] {o.get("valores")} valores escritos · {o.get("ms")} ms na página')
            return
        if gesto == "linha":
            self.escolhido = str(o.get("perfil") or "") or None
            print(f'[gesto] linha → escolhido (ECO, não grava · {len(self.escolhido or "")} car.)')
            print(f'         dono real: {perfis_web.DONOS_DOS_GESTOS["linha"]}')
            self.ponte.dizer("HEF.eco", o)
            return
        if gesto == "botao":
            qual = str(o.get("qual") or "")
            dono = perfis_web.DONOS_DOS_GESTOS.get(qual, perfis_web.SEM_DONO)
            print(f"[gesto] {qual} (ECO, não grava)")
            print(f"         dono real: {dono}")
            return

    # -- relato ------------------------------------------------------------
    def relato(self) -> str:
        def resumo(nome: str, v: list[float]) -> str:
            if not v:
                return f"{nome}: sem amostra"
            s = sorted(v)
            return (
                f"{nome}: mediana {s[len(s)//2]:.2f} ms · p95 {s[int(len(s)*.95)]:.2f} "
                f"· max {s[-1]:.2f}"
            )

        linhas = [
            f"voltas: {self.voltas} · remontagens: {self.remontagens} · "
            f"gestos: {len([g for g in self.gestos if g.get('gesto') != 'pintou'])}",
            f"valores escritos por pintura: {sorted(set(self.valores)) or 'NENHUM'}",
            resumo("fonte", self.custos_disco),
            resumo("tela ", self.custos_tela),
            resumo("volta", self.custos),
        ]
        if self.custos:
            s = sorted(self.custos)
            med = s[len(s) // 2]
            linhas.append(
                f"orçamento: {med / TIQUE_MS * 100:.1f}% dos {TIQUE_MS} ms do tique desta aba · "
                f"{med / TIQUE_RAPIDO_MS * 100:.1f}% dos {TIQUE_RAPIDO_MS} ms do tique rápido"
            )
        # A RÉGUA POR BLOCO, e ela é o que uma volta só esconde: uma régua de
        # 29/08 rodou o tique UMA VEZ e não viu uma regressão que só aparecia em
        # 181 segundos.
        if len(self.custos) >= 60:
            passo = 30
            blocos = []
            for i in range(0, len(self.custos) - passo + 1, passo):
                fatia = sorted(self.custos[i : i + passo])
                blocos.append(f"{i//passo}:{fatia[len(fatia)//2]:.2f}")
            linhas.append(f"mediana por bloco de {passo} voltas → " + " · ".join(blocos))
        if self.rss:
            linhas.append(
                f"memória RSS: {self.rss[0]/1024:.1f} MB no começo → "
                f"{self.rss[-1]/1024:.1f} MB no fim ({len(self.rss)} amostras)"
            )
        return "\n".join(linhas)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--oculta", action="store_true", help="Gtk.OffscreenWindow")
    p.add_argument("--foto", help="salva um PNG e sai (pede --oculta)")
    p.add_argument("--segundos", type=float, default=0.0, help="sai depois de N s")
    p.add_argument("--sem-ponte", action="store_true", help="a MORDIDA")
    p.add_argument("--arranca-enderecos", action="store_true",
                   help="MORDIDA: apaga os data-hef e prova que a pintura desaba")
    p.add_argument("--prova-gesto", action="store_true",
                   help="dispara cliques sintéticos e prova o eco")
    p.add_argument("--duble", default=str(AQUI / "perfis-duble.json"),
                   help="JSON com {perfis, state} — o PADRÃO, para a foto não "
                        "levar a biblioteca dela")
    p.add_argument("--do-disco", action="store_true",
                   help="lê os perfis DELA de verdade (load_all_profiles). "
                        "Não fotografe com isto ligado")
    p.add_argument("--do-daemon", action="store_true",
                   help="pergunta o perfil ativo e a mesa ao daemon mesmo com --duble")
    args = p.parse_args()

    if not PAGINA.exists():
        print(f"ERRO: a página desta aba não está em {PAGINA}", file=sys.stderr)
        return 2

    j = Janela(args)
    Gtk.main()
    print("\n" + j.relato())

    # UMA BANCADA QUE NÃO DEU UMA VOLTA NÃO MEDIU NADA, E NÃO SAI VERDE — a
    # mesma guarda que a `jogar_vivo.main` ganhou na `ONDA5-07-03`, pelo mesmo
    # defeito. O `--sem-ponte` é a exceção e é a MORDIDA: ele desliga a pintura
    # de propósito, e zero volta ali é o resultado esperado.
    if j.voltas == 0 and not args.sem_ponte:
        print("ERRO: a bancada não deu uma volta — nada foi medido.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
