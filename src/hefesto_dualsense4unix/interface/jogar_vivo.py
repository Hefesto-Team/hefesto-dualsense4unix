#!/usr/bin/env python3
"""jogar_vivo.py — a aba JOGAR VIVA: o desenho dela com a mesa dela.

A segunda das dez, e a primeira depois do piloto. O mockup aprovado
(`src/hefesto_dualsense4unix/interface/paginas/01-jogar.html`) num `WebKit2.WebView` dentro de uma janela GTK3
(`D-A-INTERFACE-NOVA-E-O-MOCKUP-DENTRO-DE-UMA-JANELA-GTK`), com o
`daemon.state_full` pintando-o dez vezes por segundo.

    jogar_vivo.py                          # a janela, na tela
    jogar_vivo.py --oculta                 # Gtk.OffscreenWindow: nada aparece
    jogar_vivo.py --oculta --segundos 4 --foto a.png

AS DUAS MORDIDAS, as mesmas do piloto e pelo mesmo motivo:

    --sem-ponte           desliga a ponte: a tela tem de ficar na cena FIXA do
                          mockup (quatro controles, "Jogar pelo Hefesto",
                          "1 aviso"). Se ela mostrar a mesa dela, o dado não
                          está vindo do daemon.
    --arranca-enderecos   apaga os `data-*` que o `aba01.py` escreve: a pintura
                          tem de DESABAR.

O QUE ESTE ARQUIVO NÃO REESCREVE, e é a metade do trabalho
==========================================================

* **A janela, as duas pontes e a guarda de carga** são de
  `hefesto_dualsense4unix.gui.ponte_da_tela` — de todas as dez abas, com as
  quatro armadilhas do WebKit2 4.1 pagas lá.
* **A mesa** (um item por controle, com cor, transporte, jogador e máscara) é de
  `mesa_viva.mesa_do_estado`, que já é o dono dela para a Controles e para a
  fita.
* **O HTML de cartão, de chip de fita e de linha de aviso** é do gerador do
  mockup (`aba01.cartao`, `monta.fita`, `aba01.aviso`) — nunca de HTML escrito
  aqui. É o que faz esta aba ACOMPANHAR o desenho por construção.
* **O que o produto sabe responder, e o que não sabe**, é de
  `hefesto_dualsense4unix.app.actions.jogar.painel` — que viaja em worktree,
  passa por `ruff` e por `mypy`, e é onde os três buracos desta aba estão
  escritos em vez de comentados aqui.

ESTA LEVA NÃO ESCREVE NADA. O único método de IPC pronunciado é
`daemon.state_full` (`mesa_viva.METODO`). Todo gesto da tela chega ao Python, é
registrado com o **dono real** (:data:`DONOS_DOS_GESTOS`) e **ecoa de volta** —
nenhum perfil dela é tocado, nenhum byte vai ao aparelho.

A ARMADILHA DA PINTURA, que é desta camada e não da ponte: `textContent` num
elemento que TEM filho apaga os filhos e força layout. Por isso o `aba01.cartao`
ganhou três `data-campo` FOLHA (jogador, identidade, bateria) em 29/08 — e por
isso a pintura escreve por TIPO (`txt`/`cls`/`trava`), nunca "escreva isto aí".
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import threading
import time
from typing import Any

# A BIBLIOTECA VEM ANTES DO `gi.repository`, e não é import decorativo: é ela
# que crava os quatro pinos de `gi.require_version` com o Gdk DEPOIS do Gtk.
#
# O `isort:skip` NÃO É ENFEITE, e um `ruff --fix` cego o removeu em 01/09/2026,
# reordenando estas três linhas: o `gi.repository` subiu para antes da
# biblioteca, e a ordem que este comentário protege se perdeu. Ferramenta de
# formatação não lê comentário — a marca é o que ela lê.
from hefesto_dualsense4unix.gui.ponte_da_tela import JanelaDaAba  # noqa: E402  isort:skip

from gi.repository import GLib, Gtk  # noqa: E402

from hefesto_dualsense4unix.app.actions.jogar import painel  # noqa: E402

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import mesa_viva  # noqa: E402


def _a01():  # noqa: ANN202
    """O pacote da aba 01, importado TARDE — ele puxa o produto inteiro."""
    from pacotes import a01_jogar

    return a01_jogar
import monta  # noqa: E402  (o gerador do mockup, usado como BIBLIOTECA)
import onde  # noqa: E402  (o DONO do caminho das páginas publicadas)

import aba01  # noqa: E402  isort:skip

#: A PASTA TEM UM DONO, E É O `onde.PUBLICADO` — nunca um caminho absoluto (o
#: instrumento mediria a árvore errada, o defeito que a
#: `regua_de_tela.raizes_candidatas` documenta por extenso) e nunca uma segunda
#: montagem do mesmo caminho, que é como esta linha morreu da primeira vez.
#:
#: **ESTA BANCADA MEDIU O VAZIO — 06/09/2026, ONDA5-07-03.** A linha dizia
#: ``AQUI.parent / "01-jogar.html"``, que era certo quando este arquivo morava
#: em ``layout/_ferramentas/`` e a página em ``layout/``. A mudança para
#: ``src/…/interface/`` levou as páginas para ``interface/paginas/`` e esta
#: linha ficou: ``AQUI.parent`` passou a apontar para
#: ``src/hefesto_dualsense4unix/01-jogar.html``, **que não existe**. Medido: a
#: bancada imprimia *"ERRO DE CARGA: carregou OUTRA página"*, ficava em
#: ``voltas: 0`` e **saía com rc=0** — verde sobre nada, que é a família de
#: instrumento falso que esta casa mais paga. Três das cinco abas vivas foram
#: corrigidas em 05/09 e duas ficaram para trás; a outra é `perfis_vivos.py:78`,
#: com o mesmo defeito e fora desta posse.
PAGINA = onde.PUBLICADO / "01-jogar.html"

#: A BANCADA — o desenho de HOJE, que é o que os geradores escrevem
#: (`onde.BANCADA`). Ela existe por `--bancada`, e não por padrão: o padrão
#: continua sendo o PUBLICADO, que é o que ela abre.
#:
#: **POR QUE ELE PRECISOU EXISTIR — 06/09/2026, JOGAR-O-QUE-FALTA-01.** Publicar
#: é ato dela, e uma sprint que acrescenta endereço ao desenho fica, até o OK, com
#: a bancada à frente do produto. Sem esta bandeira não há como CLICAR e
#: FOTOGRAFAR o que se acabou de construir: o piloto e esta bancada abrem o
#: publicado, e a régua daria verde sobre a página de ontem — que é a armadilha
#: que o `COMO-OLHAR-A-TELA` chama de *"régua que pergunta no lugar errado"*.
#: A frente da `PERFIL-MODO-01` pagou esse preço em 06/09 escrevendo um ensaio
#: próprio (`scripts/ensaios/o_quadro_do_modo_grava_pelo_webkit.py`) para medir
#: exatamente isto.
#:
#: **ELE NÃO PUBLICA NADA.** É só de onde o `WebKit2.WebView` lê; a direção
#: `mockup/` → `interface/paginas/` continua sendo do
#: `scripts/check_o_desenho_aprovado.py --publicar NN`, e continua sendo dela.
BANCADA = onde.BANCADA / "01-jogar.html"


def pagina_de(args: Any) -> pathlib.Path:
    """De onde esta bancada lê a página: o publicado, ou o desenho de hoje."""
    return BANCADA if getattr(args, "bancada", False) else PAGINA


TITULO_ESPERADO = "Hefesto — aba JOGAR"

#: O tique rápido: o mesmo período da janela de hoje
#: (`app/constants.LIVE_POLL_INTERVAL_MS`).
TIQUE_MS = 100

#: O DONO REAL DE CADA GESTO, DECLARADO NUM LUGAR SÓ. Nenhum deles é chamado
#: nesta leva — a aba é para ela AVALIAR, e um gesto que aplique sem ela mandar
#: é dano. O que o clique faz hoje é chegar aqui, ser registrado e ecoar.
DONOS_DOS_GESTOS = {
    "modo": "app/actions/mode_transition.apply_mode — o gesto de modo tem dono "
    "e funciona na janela de hoje, nos TRÊS: `gamepad` (a posição Ligado do "
    "interruptor), `native` (a posição Desligado) e `desktop` (o chip "
    "Navegação). Desde 31/08 a fileira desta tela e o `mode_transition.MODES` "
    "são o mesmo conjunto — não sobra botão sem dono nem modo sem lugar.",
    "degrau": "integrations/ponte_escada + ponte_tentativa — a escada existe e "
    "SOBE sozinha, mas ninguém a fixa pela tela: não há método de IPC que diga "
    "'use este degrau'. Dos cinco chips, um não tem dono NENHUM (Point And "
    "Click, `painel.chips_sem_dono`) e a Navegação tem escritor sem ser degrau "
    "(`painel.chips_sem_degrau`). MIGRA-JOGAR-07, pergunta dela.",
    "mascara": "gamepad.emulation.set (daemon/ipc_handlers.py) pela ponte "
    "app/ipc_bridge — MAS ele NÃO aceita `uniq`: a máscara viva é uma só para a "
    "mesa toda, e esta tela mostra três chips POR CONTROLE. E 'Nintendo Pro' "
    "não existe no catálogo (integrations/uinput_gamepad.FLAVORS tem duas "
    "entradas). MIGRA-JOGAR-10 e -11.",
    "alvo": "app/alvo_de_edicao.definir_alvo (janela) + controller.target.set "
    "(daemon). Nesta leva o clique no cartão só MOVE a fita, na memória desta "
    "janela.",
    "reconectar": "app/actions/home_actions.RECONCILIAR_LABEL + o gesto de "
    "reconciliação de jogadores, que JÁ é produto que funciona na janela de "
    "hoje. O que faltava era a tela nova ter onde ligá-lo.",
    # FATO ERRADO, SUBSTITUÍDO (01/09/2026). Aqui estava escrito que "os quatro
    # têm dono no produto (app/actions/profiles_actions.py)". São TRÊS.
    # Medido: `footer_actions.py` tem `on_apply_draft`, `on_save_profile` e
    # `on_import_profile`; `profiles_actions.py` tem new/duplicate/remove/
    # activate/reload/save; e o `main.glade` traz `btn_footer_apply`,
    # `btn_footer_import` e `btn_footer_save_profile` — **e nenhum botão de
    # exportar**. Não há handler de exportação em lugar nenhum do `src/`.
    #
    # "Exportar" é um botão que o DESENHO criou e o produto nunca teve. É
    # feature nova — barata, porque o perfil já é JSON no disco — mas não é
    # ligação, e chamá-la de ligação esconderia trabalho.
    "rodape": "Aplicar/Salvar/Importar têm dono (app/actions/footer_actions.py: "
    "on_apply_draft, on_save_profile, on_import_profile). EXPORTAR NÃO TEM — "
    "não existe handler no src/ nem botão no main.glade. Nesta leva nenhum é "
    "chamado: 'Salvar Perfil' GRAVA NO DISCO DELA, e esta leva não escreve.",
}

#: O que se diz de um gesto SEM linha na tabela acima. Era um `KeyError` cru no
#: piloto, e derrubar a tela dela para relatar um dono desconhecido é o pior dos
#: dois males.
SEM_DONO = ("SEM LINHA na tabela de donos — este gesto chegou de um endereço "
            "que o gerador não escreve. Nada foi aplicado.")

#: A cor do plástico quando o aparelho não a respondeu — a mesma saída que o
#: piloto da Controles dá, e a mesma que `cor_do_plastico.tom_para_a_borda` dá
#: para tom vazio.
PLASTICO_DESCONHECIDO = "var(--border-forte)"

_cor_da_zona_real = monta.cor_da_zona


def _cor_da_zona_tolerante(colorway: str, zona: str = "casca-solida") -> str:
    """`monta.cor_da_zona` PARA a geração quando o colorway não existe.

    Está certo para o mockup, onde a mesa é escrita à mão; aqui a mesa vem do
    aparelho, e "não sei a cor" é resposta legítima — vira a borda neutra.
    """
    if not colorway:
        return PLASTICO_DESCONHECIDO
    try:
        return _cor_da_zona_real(colorway, zona)
    except SystemExit:
        return PLASTICO_DESCONHECIDO


# OS DOIS NOMES, porque são dois: o `aba01` importou `cor_da_zona` de `monta`
# por `from monta import ...`, e quem desenha o chip da fita é `monta.fita`.
# Trocar um só deixava o cartão com a borda neutra e a fita PARANDO a montagem —
# é a cicatriz que o piloto da Controles já carrega por extenso.
monta.cor_da_zona = _cor_da_zona_tolerante
aba01.monta.cor_da_zona = _cor_da_zona_tolerante


# ---------------------------------------------------------------------------
# O gerador do mockup, usado como biblioteca
# ---------------------------------------------------------------------------
def html_dos_cartoes(mesa: list[dict[str, Any]], baterias: dict[str, Any]) -> str:
    """Um cartão por controle PRESENTE, pelo gerador — nunca por HTML meu.

    Zero, um, dois ou N: o desenho tem quatro porque a cena tem quatro, e o
    número aqui é o `len` da mesa. Não há um `range(4)` nesta função, e é
    exatamente o defeito que a MIGRA-JOGAR-04 nomeia.
    """
    return "\n".join(aba01.cartao(c, bateria=baterias.get(c["uniq"])) for c in mesa)


def html_da_fita(mesa: list[dict[str, Any]], alvo: str | None) -> str:
    """A fita de chips, também pelo gerador, com a mesa VIVA."""
    antes = monta.MESA
    monta.MESA = mesa
    try:
        escolhido = next((c["pref"] for c in mesa if c["uniq"] == alvo), "todos")
        # A mesa como ARGUMENTO — `monta.MESA` acima não alcança a fita,
        # porque `monta.CONECTADOS` é derivado no import. Ver a nota gêmea em
        # `controles_vivos.html_da_fita`.
        # O `inerte` VAI EXPLÍCITO, e não pelo padrão — 05/09/2026. Esta bancada
        # serve a aba 01, que ESCOLHE controle, então o padrão `False` acerta
        # hoje. Mas foi contando com esse padrão que o piloto acendeu a fita das
        # sete abas de leitura e lhes deu o `title` de quem escolhe. Quem responde
        # é `monta.a_fita_escolhe`, e passar a resposta aqui faz a bancada seguir
        # a aba no dia em que ela mudar, em vez de repetir o defeito adormecido.
        return monta.fita(ativo=escolhido, mesa=mesa,
                          inerte=not monta.a_fita_escolhe("01-jogar.html"))
    finally:
        monta.MESA = antes


def html_dos_avisos(avisos: list[dict[str, str]]) -> str:
    """A coluna Atenção: de ZERO a N, pela mesma função que o mockup usa.

    Zero avisos é o estado normal de uma máquina saudável, e o desenho não o
    tem — ele mostra um. Quem diz a palavra do zero é
    `painel.texto_da_conta`, e a coluna simplesmente fica sem linhas.
    """
    return "\n".join(aba01.aviso(a["selo"], a["texto"]) for a in avisos)


# ---------------------------------------------------------------------------
# O JavaScript da ponte — escreve por TIPO, nunca "ponha isto aí"
# ---------------------------------------------------------------------------
BOOTSTRAP = r"""
window.HEF = (function(){
  const qa = (s,r)=>Array.from((r||document).querySelectorAll(s));
  const q  = (s,r)=>(r||document).querySelector(s);
  // AS ESCRITAS DEVOLVEM QUANTOS VALORES ESCREVERAM — 0 quando o endereço não
  // existe. É o que faz a conta do fim ser uma RÉGUA e não um enfeite: com um
  // `n++` cego, apagar um endereço não mudaria o número e a régua aprovaria uma
  // pintura que não pinta nada.
  function txt(el,v){ if(!el) return 0; if(el.textContent !== v) el.textContent = v; return 1; }
  function est(el,o){ if(!el) return 0; for(const k in o){ if(el.style[k]!==o[k]) el.style[k]=o[k]; } return 1; }
  // A COR DO PLÁSTICO É UMA CUSTOM PROPERTY, e `el.style['--plastico']` NÃO
  // ESCREVE NADA: o CSSOM só aceita `setProperty` para nomes com `--`. Escrito
  // do jeito errado a atribuição é aceita calada, `n` conta 1, e a borda do
  // cartão nunca muda de cor — a régua aprovaria uma pintura que não pinta.
  function varia(el,nome,v){
    if(!el) return 0;
    if(el.style.getPropertyValue(nome)!==v) el.style.setProperty(nome, v);
    return 1;
  }
  function cls(el,c,on){ if(!el) return 0; el.classList.toggle(c, !!on); return 1; }
  // TRAVAR É ESCRITA, e por isso conta. Um botão que a tela oferece e o produto
  // não sabe cumprir é mentira: o `disabled` é o "não dá" dito no lugar certo.
  function trava(el,off,porque){
    if(!el) return 0;
    if(el.disabled!==!!off) el.disabled=!!off;
    if(off && porque && el.title!==porque) el.title=porque;
    return 1;
  }
  // O CHIP DA ESCADA É UM <span>, e `<span>.disabled` NÃO EXISTE: escrever nele
  // é criar uma propriedade que nada lê, e a tela continuaria oferecendo o
  // clique. Para eles o "não dá" é uma CLASSE, e o ouvinte a respeita.
  function inerte(el,off,porque){
    if(!el) return 0;
    el.classList.toggle('sem-dono', !!off);
    if(off && porque && el.title!==porque) el.title=porque;
    return 1;
  }
  function cartao(uniq){ return q('.cartao[data-controle="'+uniq+'"]'); }

  // A POSIÇÃO DO INTERRUPTOR — E ELA SEGUE O DAEMON, NÃO O CLIQUE (31/08/2026).
  //
  // O mockup deixou de usar `<button>` na fileira de modos: agora são dois
  // `radio` escondidos com `<label>` por cima, que é como as dez abas abrem
  // seção sem uma linha de JavaScript. O `ev.preventDefault()` do `ligarGestos`
  // era inofensivo num `<button>`; num `<label>` ele IMPEDE o rádio de mudar.
  //
  // A CURA NÃO É TIRAR O `preventDefault`, e nesta aba menos ainda: ela não
  // aplica NADA (o cabeçalho o diz — o único método pronunciado é
  // `daemon.state_full`). Se o clique abrisse a seção sozinho, a tela mostraria
  // "Modo Nativo" com o daemon em `gamepad` — o F7 desta casa. Quem move o
  // rádio é a pintura, e a pintura fala pelo daemon.
  //
  // O ID DO RÁDIO NÃO É DIGITADO AQUI: sai do `for` do próprio rótulo
  // (`htmlFor`), que é o que o gerador escreve — nem em comentário ele entra, e
  // há régua na suíte conferindo. E a REGRA de quais modos são "Ligado" também
  // não mora aqui: chega pronta em `p.hefesto_ligado`, de
  // `painel.hefesto_ligado`, porque o Hefesto ligado é `gamepad` OU `desktop`.
  function radioDoLado(qual){
    const rot = q('.hef-pos.' + qual);
    return rot ? document.getElementById(rot.htmlFor) : null;
  }
  function lado(p){
    // `null` = o daemon não respondeu. Empurrar o rádio para "desligado" aí
    // seria a tela responder "Desligado" sem ter perguntado a ninguém.
    if(p.hefesto_ligado !== true && p.hefesto_ligado !== false) return 0;
    const rd = radioDoLado(p.hefesto_ligado ? 'ligado' : 'desligado');
    if(!rd || rd.checked) return 0;
    rd.checked = true;
    return 1;
  }
  // O QUE A TELA FICOU MOSTRANDO — lido do DOM DEPOIS de escrever, e não o que
  // se PEDIU. Relatar a intenção é como uma régua dá verde sobre uma pintura que
  // não pintou: a mordida (arrancar o `lado`) só aparece na leitura de volta,
  // como o rádio parado onde o mockup nasceu.
  function ladoNaTela(){
    const l = radioDoLado('ligado'), d = radioDoLado('desligado');
    if(l && l.checked) return 'Ligado';
    if(d && d.checked) return 'Desligado';
    return 'SEM INTERRUPTOR';
  }

  function pintaCartao(uniq, d){
    const c = cartao(uniq); if(!c) return 0; let n=0;
    n += txt(q('[data-campo="jogador"]', c), d.jogador);
    n += txt(q('[data-campo="identidade"]', c), d.identidade);
    n += txt(q('[data-campo="bateria"]', c), d.bateria);
    n += varia(c, '--plastico', d.plastico);
    n += cls(c, 'alvo', d.alvo);
    for(const chip of qa('[data-mascara]', c)) n += cls(chip,'on', chip.dataset.mascara===d.mascara);
    return n;
  }

  function pinta(p){
    const t0 = performance.now(); let n = 0;
    // O CABEÇALHO tem um nó de TEXTO e um <b> irmão — escrever `textContent` no
    // `.conectado` apagaria o <b> e a bolinha. Por nó, então.
    const conta = q('.conectado');
    if(conta){
      for(const no of conta.childNodes) if(no.nodeType===3){ if(no.nodeValue!==p.conta) no.nodeValue=p.conta; break; }
      txt(q('b', conta), p.conta_b);
      est(conta, {color:p.conta_cor});
      txt(q('.bolinha', conta), p.bolinha); n+=3;
    }
    n += txt(q('.pa-nome'), p.perfil);
    // O RODAPÉ DIZ O MESMO PERFIL ("Salvar Perfil grava no …"), e ele é literal
    // no esqueleto (`_ferramentas/fim.html`, que não é o gerador desta aba).
    // Sem isto a tela mostrava dois perfis ao mesmo tempo — o vivo em cima e
    // "Mortal Kombat" embaixo. É a MESMA cura que o piloto da Controles fez.
    const rec = qa('.recibo b'); if(rec.length) n += txt(rec[rec.length-1], p.perfil);

    for(const b of qa('[data-modo]')){
      n += cls(b,'on', b.dataset.modo===p.modo);
      n += trava(b, !!p.modos_travados[b.dataset.modo], p.modos_travados[b.dataset.modo]);
    }
    n += lado(p);
    for(const s of qa('[data-degrau]')){
      n += cls(s,'on', s.dataset.degrau===p.degrau);
      n += inerte(s, !!p.degraus_travados[s.dataset.degrau], p.degraus_travados[s.dataset.degrau]);
    }
    n += txt(q('[data-campo="atencao-conta"]'), p.atencao_conta);
    // A PENDÊNCIA. O espaço dela é RESERVADO no desenho (a legenda o diz), então
    // o que muda é a visibilidade, nunca o `display` — tirá-la do fluxo faria a
    // tela pular, que é o defeito que o espaço reservado existe para não ter.
    const pend = q('[data-campo="pendente"]');
    if(pend){ n += est(pend, {visibility: p.pendente ? 'visible' : 'hidden'});
              n += txt(q('[data-campo="pendente-alvo"]', pend), p.pendente || '—'); }
    for(const u in p.cartoes) n += pintaCartao(u, p.cartoes[u]);
    // QUANTOS VALORES A PINTURA ESCREVEU, de volta ao Python. Sem isto uma
    // pintura que não acha NADA passaria calada — que é como a fita viva morreu
    // em 27/08.
    // A CHAVE CARREGA O LADO DO INTERRUPTOR, e não só a contagem: o rádio só é
    // escrito quando MUDA, então `n` volta ao valor de antes no tique seguinte —
    // e com `n` sozinho a virada do interruptor passaria calada, que é como a
    // fita viva morreu em 27/08.
    const marca = n + ':' + p.hefesto_ligado;
    if(marca !== window.__hefN){ window.__hefN = marca;
      manda({gesto:'pintou', valores:n, lado:ladoNaTela(),
             ms: Math.round((performance.now()-t0)*100)/100}); }
    return n;
  }

  function remonta(m){
    const pecas = q('[data-lista="cartoes"]');
    if(pecas) pecas.innerHTML = m.cartoes;
    const col = q('[data-lista="avisos"]');
    if(col){
      // O CABEÇALHO DA COLUNA FICA. Trocar o `innerHTML` inteiro levaria junto o
      // "Atenção" e a contagem, e a pintura seguinte não teria onde escrever —
      // um endereço que some não levanta erro nenhum no WebKit.
      for(const velho of qa('[data-aviso]', col)) velho.remove();
      col.insertAdjacentHTML('beforeend', m.avisos);
    }
    const fita = q('.fita');
    if(fita && m.fita) fita.outerHTML = m.fita;
    ligarGestos();
    return 'ok';
  }

  function vazio(m){
    const pecas = q('[data-lista="cartoes"]');
    if(pecas){
      pecas.innerHTML = '';
      const d = document.createElement('div');
      d.className = 'vazio-da-mesa';
      d.setAttribute('data-campo','vazio');
      d.style.cssText = 'padding:14px 2px;color:var(--texto-mudo);font-size:12px;'
                      + 'line-height:1.7;grid-column:1/-1';
      d.textContent = m.texto;
      pecas.appendChild(d);
    }
    // A FITA TAMBÉM ESVAZIA. Deixá-la com os chips de quem já saiu é a mentira
    // confortável desta tela: a mesa está vazia e a fita continuaria oferecendo
    // "P1 · Cosmic Red · USB" para escolher.
    const fita = q('.fita');
    if(fita && m.fita) fita.outerHTML = m.fita;
  }

  function manda(o){ window.webkit.messageHandlers.hefesto.postMessage(JSON.stringify(o)); }

  function ligarGestos(){
    for(const b of qa('[data-modo]')){
      if(b.dataset.ligado) continue; b.dataset.ligado='1';
      b.addEventListener('click', ev=>{
        ev.preventDefault(); ev.stopPropagation();
        if(b.disabled) return;
        manda({gesto:'modo', modo:b.dataset.modo});
      });
    }
    // A NAVEGAÇÃO TEM OS DOIS ENDEREÇOS — `data-degrau="navegacao"` E
    // `data-modo="desktop"` —, e é o `data-ligado` acima que decide qual ouvinte
    // ela ganha: o laço dos modos passa primeiro e a marca, e este `continue` a
    // deixa de fora. MEDIDO em 31/08: clicar nela produz UM gesto, `modo:
    // desktop`, que é o dono real dela (`apply_mode('desktop')`) — e não um
    // segundo gesto `degrau` que ninguém atende (não há IPC que fixe degrau).
    // O desfecho está certo; a razão é frágil. Se alguém trocar a marca por uma
    // por laço, a Navegação passa a mandar dois gestos, e o segundo é órfão.
    for(const s of qa('[data-degrau]')){
      if(s.dataset.ligado) continue; s.dataset.ligado='1';
      s.addEventListener('click', ev=>{
        ev.preventDefault(); ev.stopPropagation();
        // O `sem-dono` é o `disabled` dos <span>: sem esta guarda o chip que a
        // pintura marcou como inerte continuaria mandando gesto, e a tela
        // estaria dizendo "não dá" com a mão esquerda e "pode" com a direita.
        if(s.classList.contains('sem-dono')) return;
        manda({gesto:'degrau', degrau:s.dataset.degrau});
      });
    }
    for(const chip of qa('.mascara [data-mascara]')){
      if(chip.dataset.ligado) continue; chip.dataset.ligado='1';
      chip.addEventListener('click', ev=>{
        ev.preventDefault(); ev.stopPropagation();
        manda({gesto:'mascara', mascara:chip.dataset.mascara,
               controle: chip.closest('.cartao').dataset.controle});
      });
    }
    for(const c of qa('.cartao[data-controle]')){
      if(c.dataset.ligado) continue; c.dataset.ligado='1';
      c.addEventListener('click', ()=>{
        // SEM `stopPropagation` NO CHIP NÃO HAVERIA DOIS GESTOS, HAVERIA UM
        // ERRADO: o chip de máscara mora DENTRO do cartão, e o clique nele
        // subiria até aqui e moveria a fita junto. Os dois ouvintes existem, e
        // é o `stopPropagation` do de cima que os mantém distintos.
        manda({gesto:'alvo', controle:c.dataset.controle});
      });
    }
    for(const b of qa('[data-gesto]')){
      if(b.dataset.ligado) continue; b.dataset.ligado='1';
      b.addEventListener('click', ev=>{
        ev.preventDefault(); ev.stopPropagation();
        manda({gesto:b.dataset.gesto});
      });
    }
    // O RODAPÉ É DO ESQUELETO (`fim.html`), compartilhado pelas dez abas: ele
    // não tem `data-gesto` e não pode ganhar um sem mudar as outras nove. A
    // classe é o endereço dele, e está declarada aqui num lugar só.
    for(const [classe, qual] of [['.r-aplicar','aplicar'],['.r-salvar','salvar'],
                                 ['.r-importar','importar'],['.r-exportar','exportar']]){
      const b = q(classe); if(!b || b.dataset.ligado) continue; b.dataset.ligado='1';
      b.addEventListener('click', ev=>{
        ev.preventDefault(); ev.stopPropagation();
        manda({gesto:'rodape', qual:qual});
      });
    }
  }

  function eco(o){
    if(o.gesto==='alvo'){
      for(const c of qa('.cartao[data-controle]')) c.classList.toggle('alvo', c.dataset.controle===o.controle);
      const chips = qa('.fita .chip');
      for(let i=0;i<chips.length;i++) chips[i].classList.toggle('on', i===o.indice_na_fita);
    }
    if(o.gesto==='mascara'){
      const c = cartao(o.controle); if(!c) return;
      for(const chip of qa('[data-mascara]', c)) chip.classList.toggle('on', chip.dataset.mascara===o.mascara);
    }
    if(o.gesto==='modo'){
      for(const b of qa('[data-modo]')) b.classList.toggle('on', b.dataset.modo===o.modo);
    }
    if(o.gesto==='degrau'){
      for(const s of qa('[data-degrau]')) s.classList.toggle('on', s.dataset.degrau===o.degrau);
    }
  }

  ligarGestos();
  return {pinta:pinta, remonta:remonta, eco:eco, vazio:vazio,
          quem:function(){ return document.title + '|' + qa('.cartao[data-controle]').length; }};
})();
'HEF-PRONTO'
"""

# ---------------------------------------------------------------------------
# LÁPIDE — a FOLHA_DO_SEM_DONO, injetada de 29/08 a 31/08/2026
# ---------------------------------------------------------------------------
# ELA EXISTIA PORQUE O MOCKUP NÃO TINHA O ESTADO "este chip não tem dono": era
# consequência de a escada ter quatro degraus e a tela cinco, e desenhá-lo é
# palavra dela (PROVA-DE-TELA-01). Enquanto ela não via, esta aba injetava
#
#     .degrau.sem-dono{opacity:.45;cursor:not-allowed}
#     .seg button:disabled{opacity:.45;cursor:not-allowed}
#
# 31/08/2026 ELA VIU, E DESENHOU — e o desenho é melhor que a injeção, de um
# jeito MEDIDO: `.degrau.sem-dono` agora é borda tracejada e cor explícita, e
# `.seg button:disabled` (no `topo.html`, das dez abas) é borda e cor, os dois
# **sem `opacity`**. É a lição da `.fita.inerte`: a opacidade mora no ANCESTRAL,
# o texto cai para perto de 2:1, e toda régua de contraste que lê `color` fica
# cega a isso.
#
# CONTINUAR INJETANDO SERIA DESFAZER A CURA: a regra desta folha chega DEPOIS
# das do documento e vence no desempate, então o `opacity:.45` voltaria por cima
# do desenho — e a régua de contraste voltaria a dar verde sobre texto ilegível.
# Fora que `.seg` não tem uma única marcação na aba Jogar (`grep -c 'class="seg"'
# src/hefesto_dualsense4unix/interface/paginas/01-jogar.html` → 0): a segunda linha já não pintava nada.
#
# NÃO REINTRODUZA ESTA FOLHA. Se um estado de tela faltar, ele se DESENHA no
# gerador, que é onde ela o vê.


def _leitor_duble(codigos: str | None) -> Any:
    """Um `ler_pelo_cabo` de mentira, que responde os códigos que se pedir.

    Existe para PROVAR a junta `código de fábrica → colorway → --plastico` sem
    mandar um byte ao aparelho dela. É o mesmo ponto de injeção que o próprio
    `cor_do_plastico.ler_pelo_cabo` já oferece (`perguntar=`).
    """
    if not codigos:
        return None
    from hefesto_dualsense4unix.integrations.cor_do_plastico import cor_do_codigo

    fila = [c.strip() for c in codigos.split(",") if c.strip()]
    entregues: dict[str, Any] = {}

    def leitor(uniq: str) -> Any:
        if uniq not in entregues:
            entregues[uniq] = cor_do_codigo(fila[len(entregues) % len(fila)])
        return entregues[uniq]

    return leitor


# ---------------------------------------------------------------------------
# A janela
# ---------------------------------------------------------------------------
class Janela:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.alvo: str | None = None
        self.chaves: tuple = ()
        self.pronto = False
        self.custos: list[float] = []
        self.custos_ipc: list[float] = []
        self.custos_tela: list[float] = []
        self.voltas = 0
        self.rss: list[int] = []
        self.remontagens = 0
        self.gestos: list[dict[str, Any]] = []
        self.valores: list[int] = []
        #: Os lados que a TELA mostrou, na ordem, lidos do DOM. É a régua da
        #: cura de 31/08: com o `hefesto_ligado` arrancado esta lista trava num
        #: lado só, porque o rádio fica onde o mockup nasceu.
        self.lados_do_interruptor: list[str] = []
        #: O ECO, e ele mora SÓ AQUI — na memória desta janela, nunca no perfil
        #: dela. É o que faz o clique continuar valendo no tique seguinte em vez
        #: de o desenho voltar sozinho meio décimo depois.
        self.eco_modo: str | None = None
        self.eco_degrau: str | None = None
        self.eco_mascara: dict[str, str] = {}
        #: A PENDÊNCIA É O ECO DO MODO, e é honesta: enquanto o gesto não for
        #: aplicado, a tela deve dizer que ainda deve. Ela some no instante em
        #: que o modo vivo alcança o escolhido.
        self.pendente: str | None = None
        self.leitor_de_cor = mesa_viva.LeitorDeCor(
            ligado=not args.sem_cor, leitor=_leitor_duble(args.cor_duble)
        )
        self.perguntando: set[str] = set()
        self._roteiro: list[dict[str, Any]] | None = None
        self._t0 = 0.0

        self.tela = JanelaDaAba(
            arquivo=pagina_de(args),
            titulo_esperado=TITULO_ESPERADO,
            ao_carregar=self._instalar,
            ao_receber=self._gesto,
            ao_sair_da_aba=self._saiu_da_aba,
            oculta=args.oculta,
            subtitulo="Jogar — a mesa de verdade",
        )
        self.view = self.tela.view
        self.ponte = self.tela.ponte
        self.janela = self.tela.janela

    # -- carga -------------------------------------------------------------
    def _saiu_da_aba(self, titulo: str) -> None:
        """Ela clicou na tira. Sair da Jogar só DESLIGA a pintura."""
        self.pronto = False
        print(f"[fora da Jogar] {titulo} — o mockup estático; a pintura pausou.")

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
                # A MORDIDA DO ENDEREÇO: arranca os `data-*` que o `aba01.py`
                # escreve e vê a pintura DESABAR. Um endereço a menos não
                # levanta erro nenhum no WebKit — o `querySelector` devolve
                # `null` e o valor simplesmente não é escrito.
                #
                # `data-controle` fica de fora de propósito: arrancá-lo derruba
                # a pintura dos cartões inteira de uma vez, e a queda deixaria
                # de dizer QUAL endereço morreu.
                GLib.timeout_add(
                    2000,
                    lambda: (
                        self.ponte.rodar(
                            "for(const e of document.querySelectorAll("
                            "'[data-campo],[data-modo],[data-degrau],[data-mascara]'))"
                            "{for(const a of ['campo','modo','degrau','mascara'])"
                            " delete e.dataset[a];} window.__hefN=-1;"
                        ),
                        False,
                    )[1],
                )
            self._agendar_saida()

        self.ponte.perguntar(BOOTSTRAP, pronto)

    def _marcar_gestos_de_mentira(self) -> None:
        """Cliques SINTÉTICOS, para provar o caminho tela → Python → eco.

        `el.click()` percorre o MESMO caminho de eventos do clique do rato —
        clicar por coordenada é a armadilha que esta casa já pagou duas vezes.

        A ORDEM É A MORDIDA. O **Point And Click** é clicado PRIMEIRO, e ele tem
        de produzir ZERO gestos: é o único chip que não tem dono nenhum
        (`painel.chips_sem_dono`), e a pintura o marcou inerte. Uma régua que só
        clicasse os cinco em qualquer ordem não distinguiria "sem dono" de "sem
        ouvinte" — que é o defeito que deu verde sobre dois botões mortos em
        29/08.

        OS DOIS ENDEREÇOS QUE ESTE ROTEIRO PERDEU, e por quê: `[data-degrau=
        "desktop"]` e `[data-modo="desligado"]` deixaram de existir no desenho
        de 31/08 — o primeiro virou `navegacao`, o segundo virou a posição
        Desligado do interruptor (`native`). Clicar num `null` levanta
        `TypeError` dentro do WebKit e a régua morre calada; há régua na suíte
        conferindo cada endereço daqui contra o `src/hefesto_dualsense4unix/interface/paginas/01-jogar.html`.
        """
        roteiro = [
            # O `pointclick` SAIU DO DESENHO — decisão dela em 31/08/2026, quando
            # o Point And Click deixou de ser um degrau da escada de conexão. O
            # roteiro ficou com a referência velha, e `.click()` sobre `null`
            # levanta `TypeError` dentro do WebKit: a régua morreria no meio,
            # CALADA, e as três provas seguintes nunca rodariam.
            #
            # A régua que pegou isto está na suíte
            # (`test_o_botao_de_ligar_funciona_e_se_lembra`), e ela confere cada
            # endereço deste roteiro contra o `src/hefesto_dualsense4unix/interface/paginas/01-jogar.html`. É o tipo de
            # defeito que só a suíte inteira acha: os portões rápidos não a rodam.
            (1200, "document.querySelector('[data-degrau=\"dualsense\"]').click()"),
            (1500, "document.querySelector('[data-modo=\"native\"]').click()"),
            (1800, "document.querySelector('[data-degrau=\"steam\"]').click()"),
            # O ÚLTIMO CARTÃO, E NÃO O `[1]`. O mockup tem quatro cartões, mas a
            # remonta os troca pela MESA DELA: com um controle só na mesa o
            # `[1]` é `undefined`, e `.click()` nele levanta `TypeError` — a
            # régua morre calada no meio do roteiro, e o que vem depois nunca é
            # clicado. `length-1` é o último, que existe sempre que há mesa.
            (2100, "(function(c){c[c.length-1].click()})"
                   "(document.querySelectorAll('.cartao[data-controle]'))"),
            (2400, "(function(c){c[c.length-1]"
                   ".querySelector('[data-mascara=\"Xbox 360\"]').click()})"
                   "(document.querySelectorAll('.cartao[data-controle]'))"),
            (2700, "document.querySelector('[data-gesto=\"reconectar\"]').click()"),
            (3000, "document.querySelector('.r-aplicar').click()"),
            # E O INTERRUPTOR VOLTA. Sem este passo a prova mostraria o clique
            # de ida e nada do retorno — e "vai e não volta" é indistinguível de
            # "travou lá".
            (3300, "document.querySelector('[data-modo=\"gamepad\"]').click()"),
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
    def _estado(self) -> tuple[dict | None, str]:
        """O `state_full` de agora — do daemon dela, ou do dublê."""
        if self.args.duble:
            if self._roteiro is None:
                bruto = json.loads(pathlib.Path(self.args.duble).read_text())
                self._roteiro = bruto if isinstance(bruto, list) else [{"aos": 0, "state": bruto}]
                self._t0 = time.monotonic()
            agora = time.monotonic() - self._t0
            cena = None
            for c in self._roteiro:
                if agora >= float(c.get("aos", 0)):
                    cena = c
            if cena is None or cena.get("state") is None:
                return (None, "dublê: daemon calado")
            return (cena["state"], "")
        try:
            return (mesa_viva.estado_do_daemon(), "")
        except mesa_viva.DaemonMudo as erro:
            return (None, str(erro))

    def _tique(self) -> bool:
        if not self.pronto:
            return True
        t0 = time.perf_counter()
        state, erro = self._estado()
        t_ipc = (time.perf_counter() - t0) * 1000
        if state is None:
            self._mesa_ausente(
                "Hefesto desligado — abra a aba Sistema e clique em "
                f'"Ligar o Hefesto". ({erro})',
                bolinha="○",
                cor="var(--red)",
            )
            self.custos_ipc.append(t_ipc)
            self.voltas += 1
            return True

        conectados = mesa_viva.controles_conectados(state)
        vivos = {str(c.get("uniq") or "") for c in conectados}
        self.leitor_de_cor.esquecer_ausentes(vivos)
        for uniq in self.leitor_de_cor.pendentes(conectados):
            if uniq not in self.perguntando:
                self.perguntando.add(uniq)
                threading.Thread(
                    target=self.leitor_de_cor.perguntar, args=(uniq,), daemon=True
                ).start()

        mesa = mesa_viva.mesa_do_estado(state, self.leitor_de_cor.conhecidos(), alvo=self.alvo)
        if not mesa:
            self._mesa_ausente(
                # A FRASE TEM UM DONO SÓ — `a01_jogar.MESA_VAZIA`. Ela vivia
                # digitada aqui E lá, e duas cópias da mesma frase concordam até
                # o dia em que uma muda. Fechado em 04/09/2026, com a régua
                # (`test_a01_a_mesa_vazia_fala.py`) já cobrando as duas.
                _a01().MESA_VAZIA,
                bolinha="○",
                cor="var(--orange)",
            )
            self.custos_ipc.append(t_ipc)
            self.voltas += 1
            return True

        # A CHAVE DA REMONTAGEM é o que está ASSADO no HTML do cartão: sem a cor
        # aqui, a que chega três segundos depois (é uma pergunta ao aparelho, em
        # thread) nunca apareceria. É a mesma disciplina de
        # `status_actions._status_card_keys_for`, que reconstrói quando o
        # conjunto muda e faz diff no resto.
        #
        # A BANCADA MEDE COM O SILÊNCIO DELA, e não por lembrança — ONDA5-07-03,
        # 06/09/2026. As duas recusas («Não perguntar para este jogo» e «Tirar
        # daqui») calam o aviso do selo `JOGO`, e a conta mora DENTRO da função
        # dona (`home_actions.aviso_do_wrapper`), não num parâmetro que quem
        # chama tenha de passar. Por isso estes DOIS pontos — aqui e o
        # `_pacote` — medem exatamente o que a aba publicada mostra. Um
        # parâmetro seria a mesma família de defeito do dublê mais frouxo que a
        # função real, que envenenou outro arquivo por ordem de teste em 04/09.
        avisos = painel.avisos_do_estado(state)
        chaves = (
            tuple((c["uniq"], c["cor"], c["nome"], c["via"], c["jogador"]) for c in mesa),
            tuple(a["texto"] for a in avisos),
        )
        t1 = time.perf_counter()
        if chaves != self.chaves:
            self._remontar(mesa, avisos, conectados)
            self.chaves = chaves
        self._pintar(state, mesa, conectados, avisos)
        t_tela = (time.perf_counter() - t1) * 1000

        self.custos_ipc.append(t_ipc)
        self.custos_tela.append(t_tela)
        self.custos.append(t_ipc + t_tela)
        self.voltas += 1
        # UM VAZAMENTO NÃO APARECE NO RELÓGIO — aparece na memória. A remontagem
        # troca o `innerHTML` da grade, e um listener não removido por
        # remontagem seria invisível numa régua de tempo.
        if self.voltas % 50 == 0:
            try:
                with open("/proc/self/status", encoding="utf-8") as arq:
                    for linha in arq:
                        if linha.startswith("VmRSS:"):
                            self.rss.append(int(linha.split()[1]))
                            break
            except OSError:
                pass
        return True

    def _baterias(self, conectados: list[dict[str, Any]]) -> dict[str, Any]:
        """`{uniq: carga}` — e a carga que o daemon não deu vira `"— "`.

        No mockup a bateria é o ÚNICO dado inventado (a legenda o declara). Aqui
        ela vem do `state_full`, e quando não vem, é traço: um "0%" seria a tela
        afirmando bateria vazia num controle recém-plugado, que é o defeito que
        `_format_controller_subtitle` já evita no card antigo.
        """
        fora: dict[str, Any] = {}
        for entrada in conectados:
            bat = entrada.get("battery_pct")
            uniq = str(entrada.get("uniq") or "")
            fora[uniq] = bat if isinstance(bat, int) and not isinstance(bat, bool) else "— "
        return fora

    def _remontar(self, mesa: list[dict[str, Any]], avisos: list[dict[str, Any]], conectados: list[dict[str, Any]]) -> None:
        self.remontagens += 1
        self.ponte.dizer(
            "HEF.remonta",
            {
                "cartoes": html_dos_cartoes(mesa, self._baterias(conectados)),
                "avisos": html_dos_avisos(avisos),
                "fita": html_da_fita(mesa, self.alvo),
            },
        )
        print(
            f"[remonta #{self.remontagens}] {len(mesa)} controle(s): "
            + " · ".join(f'P{c["jogador"]} {c["nome"]} {c["via"]}' for c in mesa)
            + f" — {len(avisos)} aviso(s)"
        )

    def _mesa_ausente(self, texto: str, *, bolinha: str, cor: str) -> None:
        if self.chaves != ("vazio", texto):
            self.ponte.dizer("HEF.vazio", {"texto": texto, "fita": html_da_fita([], None)})
            self.chaves = ("vazio", texto)
            print(f"[mesa vazia] {texto}")
        self.ponte.dizer("HEF.pinta", self._pacote(None, [], []))

    def _pacote(
        self, state: dict | None, mesa: list[dict[str, Any]], conectados: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """O que a página recebe numa pintura. UMA chamada, sempre."""
        conta, conta_b = mesa_viva.texto_da_contagem(mesa)
        modo = self.eco_modo or painel.modo_vivo(state)
        avisos = painel.avisos_do_estado(state) if state is not None else []
        baterias = self._baterias(conectados)
        cartoes = {}
        for c in mesa:
            cartoes[c["uniq"]] = {
                "jogador": f'Player {c["jogador"]}',
                "identidade": f'{c["nome"]} • {c["via"]}',
                "bateria": f'{baterias.get(c["uniq"], "— ")}%',
                "plastico": _cor_da_zona_tolerante(c["cor"]),
                "mascara": self.eco_mascara.get(c["uniq"], c["mascara"]),
                "alvo": c["alvo"],
            }
        return {
            "conta": conta[1:],  # o "●" é o `.bolinha`, elemento próprio
            "conta_b": conta_b if mesa else "—",
            "conta_cor": "var(--green)" if mesa else "var(--orange)",
            "bolinha": "●" if mesa else "○",
            "perfil": painel.nome_do_perfil(state),
            "modo": modo or "",
            # OS TRAVADOS SÃO CALCULADOS, NÃO DIGITADOS: `painel` deriva os dois
            # conjuntos do próprio produto (`mode_transition.MODES` e
            # `ponte_escada.ESCADA`). No dia em que a escada ganhar o degrau de
            # desktop, o chip destrava sozinho.
            "modos_travados": {m.chave: m.porque_nao for m in painel.MODOS_DA_TELA
                               if not m.tem_leitor},
            # O SEM DONO NÃO É O SEM DEGRAU, e pintar um pelo outro mente na
            # tela. `chips_sem_degrau()` devolve a **Navegação**, que TEM
            # escritor (`apply_mode('desktop')`) e funciona hoje — marcá-la
            # inerte seria a tela dizendo "não dá" sobre um botão que dá. Quem
            # responde pela marca é `chips_sem_dono()`: sem degrau na ESCADA E
            # sem modo no produto. Hoje devolve um só, o Point And Click.
            "degraus_travados": {
                c.chave: (
                    f"“{c.rotulo}” ainda não tem quem o atenda no Hefesto: não é "
                    "degrau da escada (integrations/ponte_escada.ESCADA) nem modo "
                    "do produto (mode_transition.MODES). Está na tela por decisão "
                    "dela, de 31/08, e marcado por isto."
                )
                for c in painel.chips_sem_dono()
            },
            # A POSIÇÃO DO INTERRUPTOR, DERIVADA — nunca a comparação de um botão
            # só. O Hefesto ligado é `gamepad` OU `desktop` (a Navegação); um a
            # um, com o modo vivo em `desktop` as duas posições ficam apagadas e
            # a tela fica MUDA, que parece defeito. Vem do `state` e não do eco:
            # esta aba não aplica nada, e a seção que abre é a do daemon.
            "hefesto_ligado": painel.hefesto_ligado(state),
            "degrau": self.eco_degrau or painel.degrau_vivo(state, None) or "",
            "atencao_conta": painel.texto_da_conta(len(avisos)),
            "pendente": self.pendente,
            "cartoes": cartoes,
        }

    def _pintar(
        self, state: dict, mesa: list[dict[str, Any]], conectados: list[dict[str, Any]], avisos: list[dict[str, Any]]
    ) -> None:
        self.ponte.dizer("HEF.pinta", self._pacote(state, mesa, conectados))

    # -- a ponte -----------------------------------------------------------
    def _gesto(self, o: dict) -> None:
        """tela → Python, já em JSON. Quem RECUSA o que não for objeto JSON é a
        `PonteDaTela`; o que chega aqui é gesto de verdade."""
        self.gestos.append(o)
        gesto = str(o.get("gesto") or "")
        if gesto == "pintou":
            self.valores.append(int(o.get("valores") or 0))
            # O LADO É LIDO DO DOM, e é a régua da cura de 31/08: sem
            # `painel.hefesto_ligado` o rádio fica onde o mockup nasceu e a tela
            # abre a seção errada — "Modo Nativo" com o daemon em `gamepad`, ou o
            # contrário. Sem esta leitura de volta a mordida não teria como
            # aparecer no relato.
            lado = str(o.get("lado") or "?")
            # A LISTA GUARDA AS VIRADAS, não os valores distintos: com um `set`
            # de dois elementos "foi e voltou" e "foi e ficou" contam igual, e é
            # a volta que prova que a tela SEGUE o daemon em vez de travar.
            if not self.lados_do_interruptor or lado != self.lados_do_interruptor[-1]:
                self.lados_do_interruptor.append(lado)
            print(f'[pintura] {o.get("valores")} valores escritos · '
                  f'{o.get("ms")} ms na página · o interruptor mostra: {lado}')
            return
        print(f"[gesto] {gesto} {json.dumps({k: v for k, v in o.items() if k != 'gesto'})}")
        print(f"         dono real: {DONOS_DOS_GESTOS.get(gesto, SEM_DONO)}")
        if gesto == "modo":
            self.eco_modo = str(o.get("modo") or "")
            rotulo = next(
                (m.rotulo for m in painel.MODOS_DA_TELA if m.chave == self.eco_modo), ""
            )
            self.pendente = rotulo
            self.ponte.dizer("HEF.eco", o)
            return
        if gesto == "degrau":
            self.eco_degrau = str(o.get("degrau") or "")
            self.ponte.dizer("HEF.eco", o)
            return
        if gesto == "mascara":
            self.eco_mascara[str(o.get("controle") or "")] = str(o.get("mascara") or "")
            self.ponte.dizer("HEF.eco", o)
            return
        if gesto == "alvo":
            self.alvo = str(o.get("controle") or "") or None
            # O ÍNDICE NA FITA sai do Python porque é ele que conhece a ordem da
            # mesa; a página não pode deduzi-lo do DOM sem repetir a regra de
            # ordenação de `mesa_viva._por_numero_de_identidade`.
            self.ponte.dizer("HEF.eco", {**o, "indice_na_fita": self._indice_na_fita()})
            return

    def _indice_na_fita(self) -> int:
        """A posição do alvo entre os chips — o "Todos", quando existe, é o zero.

        E ELE NEM SEMPRE EXISTE — decisão dela, 04/09/2026: com um controle só na
        mesa, `monta.fita()` não emite o `Todos`, e o primeiro chip passa a ser o
        do controle. Contar sempre a partir de 1 acenderia `chips[1]` numa fita
        de um chip — ninguém aceso, e a régua desta bancada dizendo "clicou".
        Quem responde se o chip existe é `monta.cabe_o_todos`, o mesmo dos três
        emissores.
        """
        controles = self.chaves[0] if self.chaves else ()
        # `cabe_o_todos` só conta, e as chaves são uma por controle da mesa.
        comeco = 1 if monta.cabe_o_todos(controles) else 0
        if self.alvo is None:
            # SEM ALVO É "Todos", e sem o chip `Todos` é o único que sobrou —
            # que está no zero nos dois casos.
            return 0
        for i, c in enumerate(controles, start=comeco):
            if c[0] == self.alvo:
                return i
        return 0

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
            "o interruptor, LIDO DA TELA, na ordem: "
            + (" → ".join(self.lados_do_interruptor) or "NUNCA PINTADO"),
            resumo("IPC ", self.custos_ipc),
            resumo("tela", self.custos_tela),
            resumo("volta", self.custos),
        ]
        if self.custos:
            s = sorted(self.custos)
            med = s[len(s) // 2]
            linhas.append(
                f"orçamento: {med / TIQUE_MS * 100:.1f}% dos {TIQUE_MS} ms do tique rápido"
            )
        # A RÉGUA POR BLOCO, e ela é o que uma volta só esconde: uma régua de
        # 29/08 rodou o tique UMA VEZ e não viu uma regressão que só aparecia em
        # 181 segundos. Aqui o custo é cortado em blocos de 300 voltas, e uma
        # deriva aparece como a mediana subindo de bloco para bloco.
        if len(self.custos) >= 600:
            passo = 300
            blocos = []
            for i in range(0, len(self.custos) - passo + 1, passo):
                fatia = sorted(self.custos[i : i + passo])
                blocos.append(f"{i//passo}:{fatia[len(fatia)//2]:.2f}")
            linhas.append("mediana por bloco de 300 voltas → " + " · ".join(blocos))
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
    p.add_argument("--sem-cor", action="store_true", help="não pergunta a cor ao aparelho")
    p.add_argument(
        "--cor-duble",
        help="códigos de fábrica separados por vírgula (ex.: 02,05) — a cor vem "
        "de um dublê em vez do aparelho, para provar a junta sem mandar byte "
        "nenhum ao controle",
    )
    p.add_argument("--arranca-enderecos", action="store_true",
                   help="MORDIDA: apaga os data-* e prova que a pintura desaba")
    p.add_argument("--prova-gesto", action="store_true",
                   help="dispara cliques sintéticos e prova o eco")
    p.add_argument("--duble", help="JSON com um state_full — em vez do daemon")
    p.add_argument("--bancada", action="store_true",
                   help="lê o desenho de HOJE (`mockup/01-jogar.html`) em vez da "
                        "página publicada — para clicar e fotografar o que ainda "
                        "espera o OK dela. NÃO publica nada.")
    args = p.parse_args()

    alvo = pagina_de(args)
    if not alvo.exists():
        print(f"ERRO: a página desta aba não está em {alvo}", file=sys.stderr)
        return 2

    j = Janela(args)
    Gtk.main()
    print("\n" + j.relato())

    # UMA BANCADA QUE NÃO DEU UMA VOLTA NÃO MEDIU NADA, E NÃO SAI VERDE —
    # 06/09/2026, ONDA5-07-03. Com a página apontada para um arquivo que não
    # existia, este comando imprimia "ERRO DE CARGA", ficava em `voltas: 0` e
    # devolvia `rc=0`; quem o rodasse num laço ou num portão leria sucesso. A
    # regra desta casa é a de 04/09: *instrumento que sabe do próprio risco
    # RESOLVE, não avisa* — aviso no meio de um comando que termina verde
    # ninguém lê.
    #
    # O `--sem-ponte` é a exceção, e é a MORDIDA: ele desliga a pintura de
    # propósito para provar que a tela desaba sem ela, então zero volta ali é o
    # resultado esperado, não a falha.
    if j.voltas == 0 and not args.sem_ponte:
        print("ERRO: a bancada não deu uma volta — nada foi medido.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
