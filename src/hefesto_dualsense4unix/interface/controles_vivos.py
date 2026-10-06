#!/usr/bin/env python3
"""controles_vivos.py — a aba Controles VIVA: o desenho dela com a bancada.

O mockup aprovado rodando num `WebKit2.WebView` dentro de uma janela GTK3
(`D-A-INTERFACE-NOVA-E-O-MOCKUP-DENTRO-DE-UMA-JANELA-GTK`), e o `daemon.state_full`
pintando-o dez vezes por segundo. Um cartão por controle PRESENTE, na ordem dos
jogadores, com a cor do plástico de cada um — e a mesa muda sozinha quando ela
pluga ou tira um controle, **sem recarregar a página**.

    controles_vivos.py                     # a janela, na tela
    controles_vivos.py --oculta            # Gtk.OffscreenWindow: nada aparece
    controles_vivos.py --oculta --segundos 4 --foto a.png

AS DUAS MORDIDAS, e as duas foram medidas:

    --sem-ponte           desliga a ponte: a tela tem de ficar na cena FIXA do
                          mockup (quatro controles, Mortal Kombat, o P1 com o
                          gatilho em 200/255). Se ela mostrar a bancada, o
                          dado não está vindo do daemon.
    --arranca-enderecos   apaga os `data-*` que o `aba02.py` escreve: a pintura
                          tem de DESABAR. Se não desabar, os endereços não
                          estavam sendo usados.

E o resto:

    --duble a.json        a mesa vem de um roteiro, não do daemon (chegada,
                          saída, mesa vazia, mesa de cinco, daemon calado)
    --abre <uniq>         qual card nasce aberto
    --prova-gesto         cliques sintéticos, para provar tela → Python → eco
    --prova-interruptor   navega até a aba Jogar e LIGA e DESLIGA de verdade,
                          mostrando o `gamepad_disabled.flag` sumir e voltar
    --sem-interruptor     a MORDIDA do interruptor: não instala a ponte na aba
                          Jogar, e a `--prova-interruptor` tem de REPROVAR
    --cor-duble 02,05     a cor do plástico vem de um dublê, sem mandar um byte
                          ao aparelho
    --sem-cor  --sem-mic  --sem-pactl      desliga cada leitor, um a um

O QUE ESTE PROGRAMA ESCREVE, e é UMA COISA SÓ (31/08/2026)
----------------------------------------------------------
Até 30/08 este arquivo não escrevia nada. Mudou por pedido, literal:  e **.

O único gesto que APLICA é a **fileira de modos da aba Jogar** — os botões
`[data-modo]` de "O que o controle faz agora". Ele sai daqui por
`app/actions/mode_transition.apply_mode`, que é o dono declarado da sequência
desde o HARM-01, e o que ele grava no disco é o `gamepad_disabled.flag` do
próprio produto (`utils/session.save_gamepad_emulation`) — **não há um segundo
lugar de verdade**, e este arquivo não abre nenhum.

Todo o resto continua ECO: os dois interruptores de sensor, os dois botões de
rota e os três botões de som (o 🎙, o ♪ e o Liberar do microfone) chegam ao
Python, são registrados e voltam para a tela sem tocar em perfil nenhum. O dono
real de cada gesto está declarado em :data:`DONOS_DOS_GESTOS`, num lugar só — e
os do modo **não são digitados lá**: saem de `painel.escritor_do_modo`, que é o
dono da resposta.

POR QUE O INTERRUPTOR MORA NESTE ARQUIVO, e não no piloto da aba Jogar
----------------------------------------------------------------------
Porque é **este** que ela abre: `./interface` → `scripts/abrir_interface.py` →
este piloto. A tira de cima navega de verdade (`<a href="01-jogar.html">`), e a
ponte da janela sobrevive à navegação — o que não sobrevivia era a PONTE DE
GESTO, que só existia na página da aba Controles.

MEDIDO em 31/08, antes de uma linha ser escrita: com o `./interface` aberto e a
tira navegada até a Jogar, `[data-modo="gamepad"]` aparecia **ACESO**,
`listeners=0` nos quatro botões, o clique sintético produziu **zero gestos** e o
`gamepad_disabled.flag` não se moveu — enquanto o `mode_of_state` do daemon dizia
`desktop`. A tela afirmava o estado do DESENHO, que é o F7 desta casa.

Quando a MIGRA-JOGAR enxertar o `jogar_vivo.py` no lugar do mockup estático, o
interruptor sai daqui **sem reescrever regra nenhuma**: a regra já está em
`app/actions/jogar/painel` (leitor, escritor, trava e lembrança) e em
`mode_transition` (a sequência). O que fica aqui é DOM.

A JANELA, AS DUAS PONTES E A GUARDA DE CARGA SAÍRAM DAQUI em 29/08/2026: elas
são de todas as abas, não desta, e agora moram em
`hefesto_dualsense4unix.interface.janela` — com **as quatro armadilhas do
WebKit2 4.1** que este arquivo pagou, escritas lá em
:data:`~hefesto_dualsense4unix.interface.janela.AS_QUATRO_ARMADILHAS`. O que
sobrou aqui é a ABA: a mesa, a pintura e os gestos.

A armadilha que continua sendo deste arquivo, porque é da PINTURA e não da
ponte: `textContent` num elemento que TEM filho apaga os filhos e força layout —
a pintura escreve por TIPO (`txt`/`est`/`cls`), nunca "escreva isto aí".
"""
from __future__ import annotations

import contextlib
import argparse
import inspect
import json
import pathlib
import sys
import threading
import time
from collections import deque
from typing import Any

from hefesto_dualsense4unix.interface.janela import JanelaDaAba  # noqa: E402  isort:skip

from gi.repository import GLib, Gtk, WebKit2  # noqa: E402

from hefesto_dualsense4unix.app.actions import mode_transition
from hefesto_dualsense4unix.app.actions.jogar import painel

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
RAIZ = AQUI.parents[2]

import mesa_viva  # noqa: E402
import monta  # noqa: E402  (o gerador do mockup, usado como BIBLIOTECA)


def _a01():  # noqa: ANN202
    """O pacote da aba 01, importado TARDE — ele puxa o produto inteiro."""
    from pacotes import a01_jogar

    return a01_jogar


import aba02  # noqa: E402  isort:skip

PAGINA = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "paginas" / "02-controles.html"  # noqa-acento (`paginas` e o nome da PASTA; caminho nao leva acento)
TITULO_ESPERADO = "Hefesto — aba CONTROLES"

TIQUE_MS = 100
TIQUE_LENTO_MS = 2000

#: `state_full` (a mesma leitura do tique rápido) e pinta quatro botões — a 10 Hz
TIQUE_DO_INTERRUPTOR_MS = 500

PRAZO_DO_MODO_S = 4.0

ROTEIRO_DA_PROVA_DE_GESTO: tuple[tuple[int, str] | tuple[int, str, str], ...] = (
    (1500, ".faixa"),
    (2000, '.sw[data-sensor="giroscopio"]'),
    (2500, '.rota button[data-rota="nada"]'),
    (2800, '.rota button[data-rota="junto"]'),
    (2950, '.rota button[data-rota="pc"]'),
    (3100, '.rota button[data-rota="jogo"]'),
    (3400, '[data-mudo="alto-falante"]'),
    (3700, '[data-gesto="mic-retorno"]', "so-existe"),
)


def _clique_que_confessa(card: str, seletor: str, so_existe: bool = False) -> str:
    """O clique sintético que AVISA quando o alvo não está lá.

    Um `.click()` cru sobre `querySelector` que devolveu `null` levanta dentro
    do WebKit, e o `_js` não lê retorno nem erro — o passo some sem uma linha
    vermelha. Aqui o passo manda o resultado de volta pelo mesmo canal que a
    página já usa (`webkit.messageHandlers.hefesto`), e o relato final conta.

    É a regra desta casa aplicada a si mesma: *instrumento que sabe do próprio
    risco RESOLVE, não avisa.*
    """
    import json as _json

    sel = _json.dumps(seletor)
    clique = "" if so_existe else "if(e){e.click();}"
    return (
        "(function(){var c=" + card + ";"
        "var e=c?c.querySelector(" + sel + "):null;"
        "window.webkit.messageHandlers.hefesto.postMessage(JSON.stringify("
        "{gesto:'roteiro',alvo:" + sel + ",achou:!!e}));"
        + clique + "})()"
    )


DONOS_DOS_GESTOS = {
    **{
        f"modo:{modo.chave}": painel.escritor_do_modo(modo.chave)
        for modo in painel.MODOS_DA_TELA
    },
    "sensor:giroscopio": "NÃO TEM DONO. Não há campo de sensor em "
    "profiles/schema.py nem método de sensor em daemon/ipc_server.py. "
    "A decisão dela de 18/08 (guardar giro e acelerômetro no perfil) "
    "está registrada e não foi construída.",
    "sensor:acelerometro": "NÃO TEM DONO, e o dado também não existe: "
    "daemon/sensor_hub.leitura() publica gyro e touchpad, e o mapa de canais "
    "dá movimento.acelerometro como não/não, os dois MEDIDOS.",
    "rota:jogo": "pacotes/a02_controles.rota (grava=save_profile) — byte "
    "`OUTPUT_PATH_SEL`=2 pelo `speaker.set`, mais `app/audio_saida.RotaDeSaida`"
    " devolvendo a saída padrão do sistema (camada 1).",
    "rota:junto": "pacotes/a02_controles.rota — o MESMO dono, com "
    "`speaker.fonte='mix'`: o monitor da saída padrão cai TAMBÉM no sink do "
    "controle, e a TV continua tocando. Não é uma terceira camada.",
    "rota:nada": "pacotes/a02_controles.rota — o MESMO dono: rota 0 (o "
    "alto-falante fora do caminho) mais a saída padrão devolvida ao sistema. "
    "É o ato que ela decidiu em 20/09, com o nome que ela já tinha escrito.",
    "rota:pc": "pacotes/a02_controles.rota — continua rota válida pelo perfil, "
    "pelo IPC e pela CLI, mas SAIU DA FILEIRA em 20/09; por ser global, dois "
    "controles com rotas diferentes é pergunta que o produto ainda não responde.",
    "alvo": "app/alvo_de_edicao.definir_alvo (janela) + controller.target.set "
    "(daemon). Nesta leva o acordeão só RELATA quem está aberto.",
    "mudo:microfone": "mic.set {muted: bool} (daemon/ipc_handlers.py) pela ponte "
    "app/ipc_bridge.mic_set — é o botão de três caras do "
    "interface/cartao_do_controle.py. Clicar faz o Hefesto ASSUMIR o registrador "
    "do mudo, e o botão físico do controle para de valer até o Liberar.",
    "mudo:mic-liberar": "mic.set {muted: null} — a MESMA chamada com `null`, que "
    "devolve a posse ao kernel (hid_playstation). É o TEXTO_BOTAO_MIC_DEVOLVER "
    "do produto, e ele nasce insensível porque sem posse não há o que devolver.",
    "mudo:alto-falante": "speaker.set {muted: bool} (daemon/ipc_handlers.py) pela "
    "ponte app/ipc_bridge.speaker_set. O daemon RECUSA sem volume conhecido — "
    "por isso o ícone nasce travado enquanto o volume for desconhecido.",
}

SEM_DONO = ("SEM LINHA na tabela de donos — este gesto chegou de um endereço que "
            "o gerador não escreve. Nada foi aplicado.")


#: para `--plastico`; a borda neutra do tema é o "não sei" desta linha, e é a
PLASTICO_DESCONHECIDO = "var(--border-forte)"

_cor_da_zona_real = aba02.cor_da_zona


def _cor_da_zona_tolerante(colorway: str, zona: str = "casca-solida") -> str:
    """`monta.cor_da_zona` PARA a geração quando o colorway não existe — e está"""
    if not colorway:
        return PLASTICO_DESCONHECIDO
    try:
        return _cor_da_zona_real(colorway, zona)
    except SystemExit:
        return PLASTICO_DESCONHECIDO


aba02.cor_da_zona = _cor_da_zona_tolerante
monta.cor_da_zona = _cor_da_zona_tolerante

_luz_real = aba02.luz_do_jogador


def _luz_tolerante(c: dict[str, Any]) -> str:
    """A tabela de cor por jogador só tem cinco entradas; a mesa pode ter mais."""
    try:
        return _luz_real(c)
    except Exception:
        return "#44475a"


aba02.luz_do_jogador = _luz_tolerante


CAMPOS_DO_BLOCO = frozenset(inspect.signature(aba02.bloco).parameters) - {"c"}


def html_da_mesa(mesa: list[dict[str, Any]], estados: dict[str, dict[str, Any]]) -> str:
    """As caixas de controle, pelo gerador do mockup — nunca por HTML meu."""
    return "\n".join(
        aba02.bloco(c, **{k: v for k, v in estados[c["uniq"]].items() if k in CAMPOS_DO_BLOCO})
        for c in mesa
    )


def html_da_fita(mesa: list[dict[str, Any]]) -> str:
    """A fita de chips, também pelo gerador — e clicável, como nesta aba."""
    antes_monta, antes_aba = monta.MESA, aba02.MESA
    monta.MESA, aba02.MESA = mesa, mesa
    try:
        bruta = monta.fita(
            ativo=(mesa[0]["pref"] if mesa else "todos"), mesa=mesa,
            inerte=not monta.a_fita_escolhe("02-controles.html"))
        return aba02.fita_clicavel(bruta, mesa=mesa)
    finally:
        monta.MESA, aba02.MESA = antes_monta, antes_aba


def css_dos_chips(mesa: list[dict[str, Any]]) -> str:
    """A regra que acende o chip do controle aberto, para os prefs VIVOS."""
    ids = ["c-todos"] + [f'c-{c["pref"]}' for c in mesa]
    alvo = ",\n  ".join(f'body:has(#{r}:checked) .chip[for="{r}"]' for r in ids)
    return f"{alvo}{{background:var(--sel-bg);color:var(--fg);font-weight:600}}"


def conta_da_altura(n: int) -> tuple[int, int]:
    """`(px para o card aberto, px de rolagem)` para uma mesa de N."""
    if n <= 0:
        return (aba02.VISIVEL - aba02.PAD_DO_CORPO, 0)
    para_o_card = (
        aba02.VISIVEL - aba02.PAD_DO_CORPO - (n - 1) * aba02.ALTURA_FECHADA
        - (n - 1) * aba02.GAP_ENTRE
    )
    if para_o_card >= aba02.ALTURA_DO_CARD:
        return (para_o_card, 0)
    falta = aba02.ALTURA_DO_CARD - para_o_card
    return (aba02.ALTURA_DO_CARD, falta)


BOOTSTRAP = r"""
window.HEF = (function(){
  const qa = (s,r)=>Array.from((r||document).querySelectorAll(s));
  const q  = (s,r)=>(r||document).querySelector(s);
  // Escreve TEXTO. Só em folha sem filho — a régua que mediu 43 ms contra
  // 0,66 estava escrevendo textContent num container, e isso APAGA os filhos.
  // AS TRÊS ESCRITAS DEVOLVEM QUANTOS VALORES ESCREVERAM — 0 quando o endereço
  // não existe. É o que faz a conta do fim ser uma RÉGUA e não um enfeite: com
  // `n++` cego, apagar um endereço não mudava o número e a régua aprovava uma
  // pintura que não pintava nada.
  function txt(el,v){ if(!el) return 0; if(el.textContent !== v) el.textContent = v; return 1; }
  function est(el,o){ if(!el) return 0; for(const k in o){ if(el.style[k]!==o[k]) el.style[k]=o[k]; } return 1; }
  function cls(el,c,on){ if(!el) return 0; el.classList.toggle(c, !!on); return 1; }
  // TRAVAR É ESCRITA, e por isso conta na régua. Um botão que a tela oferece e
  // o produto recusa é mentira: o `disabled` é o "não dá" dito no lugar certo.
  function trava(el,off){ if(!el) return 0; if(el.disabled!==!!off) el.disabled=!!off; return 1; }
  function onda(el, vals){
    if(!el) return 0; const barras = el.children; let k=0;
    for(let i=0;i<barras.length && i<vals.length;i++){
      const h = vals[i]+'%'; if(barras[i].style.height!==h) barras[i].style.height=h; k++;
    }
    return k ? 1 : 0;
  }
  function card(uniq){ return q('.ctl[data-controle="'+uniq+'"]'); }

  function pintaCard(uniq, d){
    const c = card(uniq); if(!c) return 0; let n=0;
    n += txt(q('[data-campo="mascara"]', c), d.mascara);
    n += est(q('.bat .cheio', c), {width:d.bat.w}) + txt(q('.bat .n', c), d.bat.n);
    n += est(q('.touch .ponto', c),
             {left:d.touch.left, top:d.touch.top, opacity:d.touch.vis?'1':'0'});
    n += txt(q('[data-campo="touch-estado"]', c), d.touch.estado);
    for(const lado of ['l','r']){
      const s = d.sticks[lado];
      n += est(q('.stick[data-stick="'+lado+'"] .p', c), {left:s.left, top:s.top});
      const xy = q('.xy[data-xy="'+lado+'"]', c);
      if(xy){ if(xy.innerHTML !== s.xy) xy.innerHTML = s.xy; n++; }
      n += est(q('.stick[data-stick="'+lado+'"] .rotl', c), {color:s.on?'var(--plastico)':''});
    }
    const acesos = new Set(d.glifos);
    for(const g of qa('.gb[data-glifo]', c)) n += cls(g,'on', acesos.has(g.dataset.glifo));
    for(const k of ['l2','r2']){
      const linha = q('.gat-linha[data-gatilho="'+k+'"]', c);
      n += est(q('.cheio', linha||document.createElement('i')), {width:d.gat[k].w});
      n += txt(linha ? q('.n', linha) : null, d.gat[k].n);
    }
    for(const e in d.eixos){
      const el = q('.eixo[data-eixo="'+e+'"]', c); if(!el) continue;
      n += txt(el.children[1], d.eixos[e].n) + est(q('.v', el), d.eixos[e].v);
    }
    n += est(q('.barra-luz', c), {background:d.luz.bg});
    // POR ENDEREÇO, NÃO POR CLASSE. O `.de-quem` deixou de ser único no card
    // quando o touchpad ganhou o dele, e um `querySelector` por classe pegava o
    // PRIMEIRO — o hexadecimal da barra de luz foi parar no título do Touchpad,
    // que é a cara do defeito que os `data-campo` existem para não deixar
    // acontecer. Foi visto na foto, não deduzido.
    const dq = q('[data-campo="luz-hex"]', c);
    n += txt(dq, d.luz.hex); if(dq) dq.title = d.luz.title || '';
    for(const s of qa('[data-campo="mic-selo"]', c)){ n += txt(s, d.mic.selo); n += cls(s,'off', d.mic.off); }
    const bm = q('[data-bloco="microfone"]', c);
    if(bm){
      n += onda(q('.onda', bm), d.mic.onda);
      n += est(q('.vol .cheio', bm), {width:d.mic.vol_w}) + txt(q('.vol .n', bm), d.mic.vol_n);
      // O ECO DO MUDO SAIU COM O ATO — 20/09/2026. Esta linha acendia o 🎙
      // quando o microfone estava MUDO, e o 🎙 não cala mais. O botão tem dono
      // novo (`data-mic-luz`, alvo `atributo`) e quem o pinta é o `achar()`
      // genérico. Deixar as duas escritas vivas faria o eco do tique apagar a
      // luz no meio dela — dois donos para o mesmo elemento, que é o defeito
      // que os `data-campo` existem para não deixar acontecer.
      // O CAMPO QUE VESTE O 🎙 MUDOU EM 21/09/2026: é o `mic-retorno` (o que o
      // botão CAUSA), não o `mic-botao-estado` (a luz do plástico, que tem dono
      // no daemon e aparece no selo ao lado). A disciplina é a mesma.
      n += trava(q('[data-mudo="mic-liberar"]', bm), !d.mic.posse);
    }
    const ba = q('[data-bloco="alto-falante"]', c);
    if(ba){
      n += txt(q('[data-campo="alto-estado"]', ba), d.alto.estado);
      n += onda(q('.onda', ba), d.alto.onda);
      n += est(q('.vol .cheio', ba), {width:d.alto.vol_w}) + txt(q('.vol .n', ba), d.alto.vol_n);
      // O ♪ NÃO TINHA UMA LINHA AQUI. O daemon publica `speaker.muted` desde
      // sempre e a tela não o lia: o ícone não tinha como acender nem com o
      // alto-falante mudo. O eco do clique entra por cima, como o da rota.
      n += cls(q('[data-mudo="alto-falante"]', ba), 'on', d.alto.mudo);
      n += trava(q('[data-mudo="alto-falante"]', ba), !d.alto.pode);
      for(const b of qa('.rota button[data-rota]', ba)) n += cls(b,'on', b.dataset.rota===d.alto.rota);
    }
    for(const b of qa('.sw[data-sensor]', c)) n += cls(b,'off', d.sw[b.dataset.sensor]==='off');
    return n;
  }

  function pinta(p){
    const t0 = performance.now(); let n = 0;
    const conta = q('.conectado');
    if(conta){
      for(const no of conta.childNodes) if(no.nodeType===3){ if(no.nodeValue!==p.conta) no.nodeValue=p.conta; break; }
      txt(q('b', conta), p.conta_b);
      est(conta, {color:p.conta_cor});
      txt(q('.bolinha', conta), p.bolinha); n+=3;
    }
    txt(q('.pa-nome'), p.perfil); n++;
    // O rodapé diz o MESMO perfil ("Salvar Perfil grava no …") e é literal no
    // esqueleto (`_ferramentas/fim.html`, que não é o gerador desta aba). Sem
    // isto a tela mostrava dois perfis diferentes ao mesmo tempo — o vivo em
    // cima e "Mortal Kombat" embaixo.
    const rec = qa('.recibo b'); if(rec.length) { txt(rec[rec.length-1], p.perfil); n++; }
    for(const u in p.cards) n += pintaCard(u, p.cards[u]);
    // QUANTOS VALORES A PINTURA ESCREVEU, de volta ao Python. Sem isto uma
    // pintura que não acha NADA (um endereço que sumiu do gerador) passaria
    // calada — que é como a fita viva morreu em 27/08.
    if(n !== window.__hefN){ window.__hefN = n;
      manda({gesto:'pintou', valores:n, ms: Math.round((performance.now()-t0)*100)/100}); }
    return n;
  }

  function remonta(m){
    const corpo = q('.quadro-corpo'); if(!corpo) return 'sem-corpo';
    // O rádio do "Todos" mora no corpo e não é card: ele é preservado, senão o
    // chip "Todos" para de abrir a mesa inteira.
    const todos = q('#c-todos');
    corpo.innerHTML = '';
    if(todos) corpo.appendChild(todos);
    corpo.insertAdjacentHTML('beforeend', m.corpo);
    const fita = q('.fita');
    if(fita && m.fita) fita.outerHTML = m.fita;
    let folha = q('#hef-css');
    if(!folha){ folha = document.createElement('style'); folha.id='hef-css'; document.head.appendChild(folha); }
    folha.textContent = m.css;
    if(m.checado){ const r = document.getElementById(m.checado); if(r) r.checked = true; }
    ligarGestos();
    return 'ok';
  }

  function manda(o){ window.webkit.messageHandlers.hefesto.postMessage(JSON.stringify(o)); }

  function ligarGestos(){
    for(const b of qa('.sw[data-sensor]')){
      if(b.dataset.ligado) continue; b.dataset.ligado='1';
      b.addEventListener('click', ev=>{
        ev.preventDefault(); ev.stopPropagation();
        manda({gesto:'sensor', sensor:b.dataset.sensor,
               controle:b.closest('.ctl').dataset.controle,
               estava: b.classList.contains('off') ? 'off' : 'on'});
      });
    }
    for(const b of qa('.rota button[data-rota]')){
      if(b.dataset.ligado) continue; b.dataset.ligado='1';
      b.addEventListener('click', ev=>{
        ev.preventDefault(); ev.stopPropagation();
        manda({gesto:'rota', rota:b.dataset.rota,
               controle:b.closest('.ctl').dataset.controle});
      });
    }
    // OS TRÊS BOTÕES DE SOM — o 🎙, o ♪ e o Liberar. Eles NÃO estavam aqui, e
    // era esse o defeito: o CSS lhes dava `cursor:pointer`, a pintura tocava um
    // deles, e nenhum tinha ouvinte. Medido com cliques sintéticos: dois
    // cliques nos ícones produziram ZERO gestos, enquanto os de rota, ao lado,
    // ecoavam. `disabled` não precisa de guarda — o navegador não dispara
    // `click` num botão desabilitado —, mas a guarda fica porque o `disabled`
    // pode sair da tela por pintura e o significado não muda.
    for(const b of qa('[data-mudo]')){
      if(b.dataset.ligado) continue; b.dataset.ligado='1';
      b.addEventListener('click', ev=>{
        ev.preventDefault(); ev.stopPropagation();
        if(b.disabled) return;
        manda({gesto:'mudo', bloco:b.dataset.mudo,
               controle:b.closest('.ctl').dataset.controle,
               estava: b.classList.contains('on') ? 'on' : 'off'});
      });
    }
    for(const r of qa('.radio-mesa')){
      if(r.dataset.ligado) continue; r.dataset.ligado='1';
      r.addEventListener('change', ()=>{
        if(!r.checked) return;
        const c = r.closest('.ctl');
        manda({gesto:'alvo', radio:r.id, controle: c ? c.dataset.controle : ''});
      });
    }
  }

  function eco(o){
    if(o.gesto==='sensor'){
      const c = card(o.controle); if(!c) return;
      const b = q('.sw[data-sensor="'+o.sensor+'"]', c);
      if(b) b.classList.toggle('off', o.estado==='off');
    }
    if(o.gesto==='rota'){
      const c = card(o.controle); if(!c) return;
      for(const b of qa('.rota button', c)) b.classList.toggle('on', b.dataset.rota===o.rota);
    }
    if(o.gesto==='mudo'){
      const c = card(o.controle); if(!c) return;
      const b = q('[data-mudo="'+o.bloco+'"]', c);
      if(b && o.estado!==undefined) b.classList.toggle('on', o.estado==='on');
      // O "Liberar" acompanha o 🎙: assumir o mudo é o que CRIA o que devolver.
      const lib = q('[data-mudo="mic-liberar"]', c);
      if(lib && o.posse!==undefined) lib.disabled = !o.posse;
    }
  }

  function vazio(m){
    const corpo = q('.quadro-corpo'); if(!corpo) return;
    const todos = q('#c-todos');
    corpo.innerHTML = '';
    if(todos) corpo.appendChild(todos);
    const d = document.createElement('div');
    d.className = 'vazio-da-mesa';
    d.style.cssText = 'padding:26px;color:var(--texto-mudo);font-size:13px;line-height:1.7;max-width:720px';
    d.textContent = m.texto;
    corpo.appendChild(d);
    // A FITA TAMBÉM ESVAZIA. Deixá-la com os chips de quem já saiu é a mentira
    // confortável desta tela: a mesa está vazia e a fita continuaria oferecendo
    // "P1 · Cosmic Red · USB" para escolher.
    const fita = q('.fita');
    if(fita && m.fita) fita.outerHTML = m.fita;
  }

  ligarGestos();
  return {pinta:pinta, remonta:remonta, eco:eco, vazio:vazio,
          quem:function(){ return document.title + '|' + qa('.ctl').length; }};
})();
'HEF-PRONTO'
"""

INTERRUPTOR = r"""
window.HEFSW = (function(){
  const qa = s => Array.from(document.querySelectorAll(s));
  function manda(o){ window.webkit.messageHandlers.hefesto.postMessage(JSON.stringify(o)); }

  // AS ESCRITAS DEVOLVEM QUANTAS ESCREVERAM — 0 quando o endereço não existe.
  // Com `n++` cego, arrancar os `data-modo` não mudaria o número e a régua
  // aprovaria uma pintura que não pinta nada.
  function cls(el,c,on){ if(!el) return 0; el.classList.toggle(c, !!on); return 1; }
  function trava(el,off){ if(!el) return 0; if(el.disabled!==!!off) el.disabled=!!off; return 1; }
  function dica(el,v){ if(!el) return 0; if(el.title!==v) el.title=v; return 1; }

  // A POSIÇÃO DO INTERRUPTOR — E ELA SEGUE O DAEMON, NÃO O CLIQUE (31/08/2026).
  //
  // O QUE QUEBROU: o mockup deixou de usar `<button>` na fileira de modos e
  // passou a usar `<label>` sobre um `radio` escondido, que é como as dez abas
  // abrem seção sem uma linha de JavaScript. O `ev.preventDefault()` do ouvinte
  // abaixo era inofensivo num `<button>`; num `<label>` ele IMPEDE o rádio de
  // mudar, e a seção não abriria nem fecharia.
  //
  // A CURA NÃO É TIRAR O `preventDefault`. Se o clique movesse o rádio sozinho,
  // a tela abriria a seção do Modo Nativo enquanto o daemon continuasse em
  // `gamepad` — o F7 desta casa, estado velho como padrão, na pergunta em que
  // ele mais dói. A seção segue o DAEMON: quem move o rádio é a pintura.
  //
  // O ID DO RÁDIO NÃO É DIGITADO AQUI: ele sai do `for` do próprio rótulo
  // (`htmlFor`), que é o que o gerador escreve. Escrevê-lo seria digitar o que
  // se pode LER — a forma exata dos onze instrumentos falsos de 26/08 — e a
  // régua da suíte confere justamente isso, então nem em comentário ele entra.
  // E a REGRA de quais modos são "Ligado" não mora aqui: ela chega pronta em
  // `p.hefesto_ligado`, de `painel.hefesto_ligado`.
  function radioDoLado(qual){
    const rot = document.querySelector('.hef-pos.' + qual);
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
  // se PEDIU. Relatar a intenção é como uma régua dá verde sobre uma pintura
  // que não pintou: aqui a mordida (arrancar o `lado`) tem de aparecer como o
  // rádio parado no lado errado, e só a leitura de volta mostra isso.
  function ladoNaTela(){
    const l = radioDoLado('ligado'), d = radioDoLado('desligado');
    if(l && l.checked) return 'Ligado';
    if(d && d.checked) return 'Desligado';
    return 'SEM INTERRUPTOR';
  }

  function pinta(p){
    let n = 0;
    for(const b of qa('[data-modo]')){
      const chave = b.dataset.modo;
      const motivo = p.travados[chave] || '';
      n += cls(b, 'on', chave === p.modo);
      n += trava(b, !!motivo);
      n += dica(b, motivo || (p.dicas[chave] || ''));
    }
    n += lado(p);
    // A CHAVE DO RELATO CARREGA O MODO, e não só a contagem: com `n` sozinho o
    // Python só ouviria a PRIMEIRA pintura, e uma troca de modo passaria calada.
    // O LADO ENTRA NA CHAVE pelo mesmo motivo: o rádio só é escrito quando MUDA,
    // então `n` volta ao valor de antes no tique seguinte, e sem o lado a virada
    // do interruptor passaria calada — que é como a fita viva morreu em 27/08.
    const marca = n + ':' + (p.modo || '') + ':' + Object.keys(p.travados).length
                + ':' + p.hefesto_ligado;
    if(marca !== window.__hefSW){ window.__hefSW = marca;
      manda({gesto:'interruptor-pintou', valores:n, modo:p.modo||'',
             hefesto_ligado:p.hefesto_ligado, lado:ladoNaTela()}); }
    return n;
  }

  function ligar(){
    let quantos = 0;
    for(const b of qa('[data-modo]')){
      if(b.dataset.ligado) continue; b.dataset.ligado='1'; quantos++;
      b.addEventListener('click', ev=>{
        ev.preventDefault(); ev.stopPropagation();
        // `disabled` já impede o evento no navegador; a guarda fica porque o
        // `disabled` pode sair da tela por pintura e o significado não muda.
        if(b.disabled) return;
        manda({gesto:'modo', modo:b.dataset.modo});
      });
    }
    return quantos;
  }

  const ligados = ligar();
  return {pinta:pinta, ligar:ligar,
          quem:function(){ return qa('[data-modo]').length + '|' + ligados; }};
})();
'SW-PRONTO'
"""


def _unidade_do_hefesto() -> str:
    """O nome da unidade, LIDO do produto — nunca digitado."""
    from hefesto_dualsense4unix.daemon.service_install import SERVICE_NORMAL

    return str(SERVICE_NORMAL)


def _leitor_duble(codigos: str | None) -> Any:
    """Um `ler_identidade_pelo_cabo` de mentira, que responde os códigos pedidos.

    Existe para PROVAR a junta `código de fábrica → colorway do desenho →
    --plastico` sem mandar um byte ao aparelho do usuário. É o mesmo ponto de injeção
    que o próprio `cor_do_plastico.ler_pelo_cabo` já oferece (`perguntar=`) e que
    a suíte usa para não mandar comando de fábrica aos controles do usuário.
    """
    if not codigos:
        return None
    from hefesto_dualsense4unix.integrations.cor_do_plastico import (
        IdentidadeDeFabrica,
        cor_do_serial,
    )

    fila = [c.strip() for c in codigos.split(",") if c.strip()]
    entregues: dict[str, Any] = {}

    def leitor(uniq: str) -> Any:
        if uniq not in entregues:
            codigo = fila[len(entregues) % len(fila)][:2].rjust(2, "0")
            serial = f"DUBL{codigo}".ljust(17, "0")
            entregues[uniq] = IdentidadeDeFabrica(serial=serial, cor=cor_do_serial(serial))
        return entregues[uniq]

    return leitor


class Janela:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.alvo: str | None = args.abre or None
        self.chaves: tuple = ()
        self.uniqs: tuple[str, ...] = ()
        self.pronto = False
        self.custos: list[float] = []
        self.custos_ipc: list[float] = []
        self.custos_tela: list[float] = []
        self.voltas = 0
        self.rss: list[int] = []
        self.remontagens = 0
        self.gestos: list[dict[str, Any]] = []
        self.valores: list[int] = []
        self.eco_sensor: dict[str, dict[str, str]] = {}
        self.eco_rota: dict[str, str] = {}
        #: O eco dos três botões de som, por controle. Ele é o que sobrevive à
        self.eco_mudo: dict[str, dict[str, Any]] = {}
        self.ondas: dict[str, deque] = {}
        self.lento: dict[str, dict[str, Any]] = {}
        self.leitor_de_cor = mesa_viva.LeitorDeCor(
            ligado=not args.sem_cor, leitor=_leitor_duble(args.cor_duble)
        )
        self.mic = None
        self._roteiro: list[dict[str, Any]] | None = None
        self._t0 = 0.0
        self.interruptor_ligado = False
        self.eco_modo: str | None = None
        self.eco_ate = 0.0
        self.aplicados: list[str] = []
        self.lembrancas: list[tuple[str, bool | None]] = []
        self.pinturas_do_interruptor = 0
        self.lados_do_interruptor: list[str] = []
        self.recusas_de_modo: list[str] = []
        #: verde sobre dois botões mortos em 29/08.
        self.cliques_do_roteiro = 0
        self.alvos_mortos_do_roteiro: list[str] = []
        self.alvos_vivos_do_roteiro = 0


        self.tela = JanelaDaAba(
            arquivo=PAGINA,
            titulo_esperado=TITULO_ESPERADO,
            ao_carregar=self._instalar,
            ao_receber=self._gesto,
            ao_sair_da_aba=self._saiu_da_aba,
            oculta=args.oculta,
            subtitulo="Controles — o que o aparelho diz",
        )
        self.view = self.tela.view
        self.ponte = self.tela.ponte
        self.janela = self.tela.janela

        self.view.connect("load-changed", self._pagina_mudou)
        if not args.sem_interruptor:
            GLib.timeout_add(TIQUE_DO_INTERRUPTOR_MS, self._tique_do_interruptor)

    def _saiu_da_aba(self, titulo: str) -> None:
        """O usuário clicou na tira. Sair da Controles só DESLIGA a pintura."""
        self.pronto = False
        print(f"[fora da Controles] {titulo} — o mockup estático; a pintura pausou.")

    def _pagina_mudou(self, _view: Any, evento: Any) -> None:
        """Uma página TERMINOU de carregar — qualquer uma, inclusive a de volta."""
        if evento != WebKit2.LoadEvent.FINISHED:
            return
        self.interruptor_ligado = False
        if self.args.sem_interruptor:
            return
        GLib.timeout_add(80, self._talvez_ligar_o_interruptor)

    def _talvez_ligar_o_interruptor(self) -> bool:
        """A página à vista tem a fileira de modos? Então ela ganha a ponte."""

        def respondeu(valor: str | None, erro: Exception | None) -> None:
            if erro is not None:
                return
            if valor == "ja":
                self.interruptor_ligado = True
                self._pintar_o_interruptor()
                return
            if valor == "sim":
                self._ligar_o_interruptor()

        self.ponte.perguntar(
            "document.querySelector('[data-modo]')"
            " ? (window.HEFSW ? 'ja' : 'sim') : 'nao'",  # (noqa-acento): sentinela comparada no JS
            respondeu,
        )
        return False

    def _ligar_o_interruptor(self) -> None:
        def pronto(valor: str | None, erro: Exception | None) -> None:
            if erro is not None:
                print(f"interruptor: não instalou ({erro})", file=sys.stderr)
                return
            self.interruptor_ligado = True
            lembra = painel.modo_lembrado()
            self.lembrancas.append(("ao chegar na fileira", lembra.ligado))
            print("[interruptor] a fileira de modos está VIVA — "
                  f"{valor or 'sem resposta'}")
            print(f"[interruptor] o disco diz: {lembra.frase}")
            self._pintar_o_interruptor()

        self.ponte.perguntar(INTERRUPTOR + ";window.HEFSW.quem()", pronto)

    def _tique_do_interruptor(self) -> bool:
        if self.interruptor_ligado:
            self._pintar_o_interruptor()
        return True

    def _pintar_o_interruptor(self) -> None:
        """O que a fileira mostra AGORA — a verdade do daemon, com prazo do eco."""
        state, _erro = self._estado()
        vivo = painel.modo_vivo(state)
        if self.eco_modo is not None:
            if vivo == self.eco_modo:
                print(f"[interruptor] o daemon alcançou “{self.eco_modo}”.")
                self.eco_modo = None
            elif time.monotonic() > self.eco_ate:
                print(f"[interruptor] PRAZO ESTOURADO: pedi “{self.eco_modo}” e "
                      f"o daemon continua em “{vivo}”. A tela volta à verdade.")
                self.eco_modo = None
        lembra = painel.modo_lembrado()
        self.ponte.dizer(
            "HEFSW.pinta",
            {
                "modo": self.eco_modo or vivo or "",
                "travados": {
                    m.chave: painel.porque_nao_aplica(m.chave)
                    for m in painel.MODOS_DA_TELA
                    if painel.porque_nao_aplica(m.chave)
                },
                "dicas": {mode_transition.MODE_GAMEPAD: lembra.frase},
                "hefesto_ligado": painel.hefesto_ligado(state),
            },
        )

    def _aplicar_o_modo(self, chave: str) -> None:
        """O clique do usuário virando pedido — pelo dono, e só por ele."""
        motivo = painel.porque_nao_aplica(chave)
        if motivo:
            self.recusas_de_modo.append(chave)
            print(f"[interruptor] RECUSADO — {motivo}")
            return
        antes = painel.modo_lembrado()
        self.lembrancas.append((f"antes de aplicar {chave}", antes.ligado))
        self.eco_modo = chave
        self.eco_ate = time.monotonic() + PRAZO_DO_MODO_S
        self.aplicados.append(chave)
        plano = painel.plano_do_modo(chave) or []
        print(f"[interruptor] APLICANDO “{chave}” — "
              + " · ".join(metodo for metodo, _ in plano))

        def deu(resultado: Any) -> bool:
            depois = painel.modo_lembrado()
            self.lembrancas.append((f"depois de aplicar {chave}", depois.ligado))
            print(f"[interruptor] o daemon respondeu: {resultado}")
            print(f"[interruptor] o disco agora diz: {depois.frase}")
            return False

        def falhou(erro: Exception) -> bool:
            print(f"[interruptor] o daemon RECUSOU “{chave}”: {erro}",
                  file=sys.stderr)
            self.eco_modo = None
            return False

        mode_transition.apply_mode(chave, on_done=deu, on_fail=falhou)

    def _marcar_o_interruptor_de_mentira(self) -> None:
        """Cliques SINTÉTICOS na fileira de modos — os TRÊS, e todos aplicam."""
        jogar = (PAGINA.parent / "01-jogar.html").as_uri()
        roteiro: list[tuple[int, Any]] = [
            (1200, lambda: self.view.load_uri(jogar)),
            (2600, lambda: self._js(
                "document.querySelector('[data-modo=\"native\"]').click()")),
            (3400, lambda: self._js(
                "document.querySelector('[data-modo=\"gamepad\"]').click()")),
            (7000, lambda: self._js(
                "document.querySelector('[data-modo=\"desktop\"]').click()")),
        ]
        for ms, passo in roteiro:
            GLib.timeout_add(ms, lambda p=passo: (p(), False)[1])
        self.cliques_do_roteiro = len(roteiro) - 1

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
            if not self.args.sem_mic:
                self._ligar_o_microfone()
            self._tique()
            GLib.timeout_add(TIQUE_MS, self._tique)
            if self.args.prova_gesto:
                self._marcar_gestos_de_mentira()
            if self.args.prova_interruptor:
                self._marcar_o_interruptor_de_mentira()
            if self.args.arranca_enderecos:
                GLib.timeout_add(
                    2000,
                    lambda: (
                        self._js(
                            "for(const e of document.querySelectorAll('[data-glifo],"
                            "[data-eixo],[data-bloco],[data-gatilho],[data-stick],"
                            "[data-xy],[data-campo],[data-mudo]'))"
                            "{for(const a of ['glifo','eixo','bloco','gatilho','stick',"
                            "'xy','campo','mudo'])"
                            " delete e.dataset[a];} window.__hefN=-1;"
                        ),
                        False,
                    )[1],
                )
            GLib.timeout_add(TIQUE_LENTO_MS, self._tique_lento)
            self._agendar_saida()

        self.ponte.perguntar(BOOTSTRAP, pronto)

    def _marcar_gestos_de_mentira(self) -> None:
        """Cliques SINTÉTICOS, para provar o caminho tela → Python → eco."""
        um = "document.querySelectorAll('.ctl')[document.querySelectorAll('.ctl').length-1]"
        for passo in ROTEIRO_DA_PROVA_DE_GESTO:
            ms, seletor = passo[0], passo[1]
            so_existe = len(passo) > 2 and passo[2] == "so-existe"
            GLib.timeout_add(
                ms,
                lambda s=seletor, e=so_existe: (
                    self._js(_clique_que_confessa(um, s, e)), False)[1],
            )

    def _agendar_saida(self) -> None:
        foto = self.args.foto
        self.tela.agendar_saida(
            self.args.segundos or 0.0,
            antes=(lambda: self.tela.fotografar(foto)) if foto else None,
        )

    def _ligar_o_microfone(self) -> None:
        """O microfone é o ÚNICO item desta aba que NÃO vem do IPC."""
        try:
            from hefesto_dualsense4unix.app.mic_monitor import MicMonitor

            self.mic = MicMonitor()
            self.mic.set_ativo(True)
        except Exception as erro:  # pragma: no cover
            print(f"aviso: sem medidor de microfone ({erro})", file=sys.stderr)

    def _estado(self) -> tuple[dict | None, str]:
        """O `state_full` de agora — do daemon do usuário, ou do dublê.

        O DUBLÊ ACEITA UM ROTEIRO, e é assim que a chegada e a saída de controle
        se provam sem plugar nada na bancada: uma lista de
        ``{"aos": segundos, "state": …}`` (``state: null`` = daemon calado), e o
        tique escolhe a cena pelo relógio. Sem roteiro, o arquivo é um
        `state_full` só.
        """
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
                "O Hefesto não respondeu. Ele é um serviço do sistema: se estiver "
                "desligado, quem o liga de volta é o systemd — no terminal, "
                f"`systemctl --user start {_unidade_do_hefesto()}`. ({erro})",
                bolinha="○",
                cor="var(--red)",
                conta=" 0 controles: ",
            )
            self.custos_ipc.append(t_ipc)
            self.voltas += 1
            return True

        conectados = mesa_viva.controles_conectados(state)
        vivos = {str(c.get("uniq") or "") for c in conectados}
        self.leitor_de_cor.esquecer_ausentes(vivos)
        self.leitor_de_cor.disparar(conectados)

        mesa = mesa_viva.mesa_do_estado(state, self.leitor_de_cor.conhecidos(), alvo=self.alvo)
        if not mesa:
            self._mesa_ausente(
                _a01().MESA_VAZIA,
                bolinha="○",
                cor="var(--orange)",
                conta=" 0 controles: ",
            )
            self.custos_ipc.append(t_ipc)
            self.voltas += 1
            return True

        if self.mic is not None:
            with contextlib.suppress(Exception):
                self.mic.set_controles(tuple(c["uniq"] for c in mesa))

        estados = {}
        for c in mesa:
            entrada = next(e for e in conectados if str(e.get("uniq") or "") == c["uniq"])
            estados[c["uniq"]] = mesa_viva.estado_do_card(
                entrada,
                mic_vol=self.lento.get(c["uniq"], {}).get("mic_vol"),
                rota_nada=self.lento.get(c["uniq"], {}).get("rota_nada"),
                onda_mic=self._onda(c["uniq"]),
            )

        chaves = tuple(
            (c["uniq"], c["cor"], c["nome"], c["via"], c["jogador"], c["mascara"])
            for c in mesa
        )
        t1 = time.perf_counter()
        if chaves != self.chaves:
            self._remontar(mesa, estados)
            self.chaves = chaves
        self.uniqs = tuple(c["uniq"] for c in mesa)
        self._pintar(state, mesa, conectados, estados)
        t_tela = (time.perf_counter() - t1) * 1000

        self.custos_ipc.append(t_ipc)
        self.custos_tela.append(t_tela)
        self.custos.append(t_ipc + t_tela)
        self.voltas += 1
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

    def _onda(self, uniq: str) -> list[int]:
        """As 14 barras do microfone — histórico deslizante, como o produto."""
        fila = self.ondas.setdefault(uniq, deque([mesa_viva.PISO_DA_ONDA] * 14, maxlen=14))
        nivel = None
        if self.mic is not None:
            try:
                leitura = self.mic.leitura(uniq)
                nivel = getattr(leitura, "nivel", None) if leitura else None
            except Exception:
                nivel = None
        fila.append(mesa_viva.PISO_DA_ONDA if nivel is None else round(nivel * 100))
        return list(fila)

    def _remontar(self, mesa: list[dict[str, Any]], estados: dict) -> None:
        self.remontagens += 1
        para_o_card, rola = conta_da_altura(len(mesa))
        aberto = next((c for c in mesa if c["alvo"]), mesa[0])
        pacote = {
            "corpo": html_da_mesa(mesa, estados),
            "fita": html_da_fita(mesa),
            "css": css_dos_chips(mesa),
            "checado": f'c-{aberto["pref"]}',
        }
        self.ponte.dizer("HEF.remonta", pacote)
        print(
            f"[remonta #{self.remontagens}] {len(mesa)} controle(s): "
            + " · ".join(f'P{c["jogador"]} {c["nome"]} {c["via"]}' for c in mesa)
            + f" — card aberto {para_o_card}px"
            + (f", a caixa ROLA {rola}px" if rola else ", sem rolar")
        )

    def _mesa_ausente(self, texto: str, *, bolinha: str, cor: str, conta: str) -> None:
        if self.chaves != ("vazio", texto):
            self.ponte.dizer("HEF.vazio", {"texto": texto, "fita": html_da_fita([])})
            self.chaves = ("vazio", texto)
            self.uniqs = ()
            print(f"[mesa vazia] {texto}")
        self.ponte.dizer(
            "HEF.pinta",
            {
                "conta": conta,
                "conta_b": "—",
                "conta_cor": cor,
                "bolinha": bolinha,
                "perfil": "—",
                "cards": {},
            },
        )

    def _pintar(self, state: dict, mesa: list[dict[str, Any]], conectados: list[dict[str, Any]], estados: dict) -> None:
        self.ondas.pop("__vazio__", None)
        conta, conta_b = mesa_viva.texto_da_contagem(mesa)
        cards = {}
        for c in mesa:
            entrada = next(e for e in conectados if str(e.get("uniq") or "") == c["uniq"])
            cards[c["uniq"]] = self._pacote_do_card(c, entrada, estados[c["uniq"]])
        pacote = {
            "conta": conta[1:],
            "conta_b": conta_b,
            "conta_cor": "var(--green)",
            "bolinha": "●",
            "perfil": str(state.get("active_profile") or "—"),
            "cards": cards,
        }
        self.ponte.dizer("HEF.pinta", pacote)

    def _pacote_do_card(self, c: dict, entrada: dict, e: dict) -> dict:
        inputs = entrada.get("inputs") or {}
        bat = entrada.get("battery_pct")
        lx, ly, rx, ry = e["sticks"]
        botoes = set(inputs.get("buttons") or [])
        luz = entrada.get("lightbar_rgb") or []
        hexa = "#%02X%02X%02X" % tuple(luz[:3]) if len(luz) >= 3 else "—"
        recado = ""
        if entrada.get("lightbar_disputada"):
            recado = (
                "A Steam tem este controle aberto: a cor publicada é a PEDIDA, "
                "e pode não ser a acesa."
            )
        alto_pct = e["alto_pct"]
        eco = self.eco_mudo.get(c["uniq"], {})
        eco_mic_mudo = (eco["microfone"] == "on") if "microfone" in eco else e["mic_mudo"]
        # `mic_sabemos` é falso quando o `state_full` não trouxe a chave `audio`
        mic_sabemos = ("microfone" in eco) or e.get("mic_sabemos", False)
        eco_alto_mudo = (eco["alto-falante"] == "on") if "alto-falante" in eco else e["alto_mudo"]
        eixos = {}
        for eixo, texto, estilo in e["giro"]:
            estilo_d = dict(p.split(":", 1) for p in estilo.split(";") if p)
            eixos[f"giro-{eixo.lower()}"] = {"n": texto, "v": estilo_d}
        return {
            "mascara": c["mascara"],
            "bat": {
                "w": f"{bat}%" if isinstance(bat, int) else "0%",
                "n": f"{bat}%" if isinstance(bat, int) else "— %",
            },
            "touch": {
                "left": f'{e["touch"][0]}%',
                "top": f'{e["touch"][1]}%',
                "vis": e["tocando"],
                "estado": aba02.texto_toques(1 if e["tocando"] else 0),
            },
            "sticks": {
                "l": {
                    "left": f"{aba02.pos(lx)}%",
                    "top": f"{aba02.pos(ly)}%",
                    "xy": f"X: {lx:>3}<br>Y: {ly:>3}",
                    "on": "l3" in botoes,
                },
                "r": {
                    "left": f"{aba02.pos(rx)}%",
                    "top": f"{aba02.pos(ry)}%",
                    "xy": f"X: {rx:>3}<br>Y: {ry:>3}",
                    "on": "r3" in botoes,
                },
            },
            "glifos": sorted(e["glifos_on"]),
            "gat": {
                "l2": {"w": f'{e["l2"] * 100 // 255}%', "n": f'{e["l2"]} / 255'},
                "r2": {"w": f'{e["r2"] * 100 // 255}%', "n": f'{e["r2"]} / 255'},
            },
            "eixos": eixos,
            "luz": {
                "bg": hexa if hexa != "—" else "var(--border-forte)",
                "hex": hexa,
                "title": recado,
            },
            "mic": {
                "selo": mesa_viva.selo_do_mic(eco_mic_mudo, mic_sabemos),
                "off": eco_mic_mudo and mic_sabemos,
                "onda": e["mic_v"],
                "vol_w": f'{e["mic_vol"]}%',
                "vol_n": str(e["mic_vol"]),
                "posse": bool(eco.get("mic_posse", e["mic_posse"])),
            },
            "alto": {
                "estado": "· Não ajustado" if alto_pct is None else f"· {alto_pct} %",
                "onda": [mesa_viva.PISO_DA_ONDA] * 14,
                "vol_w": "0%" if alto_pct is None else f"{alto_pct}%",
                "vol_n": "—" if alto_pct is None else str(alto_pct),
                "mudo": eco_alto_mudo,
                "pode": e["alto_pode"],
                "rota": self.eco_rota.get(
                    c["uniq"], "nada" if e["rota_nada"] else "jogo"),
            },
            "sw": self.eco_sensor.get(
                c["uniq"], {"giroscopio": "off", "acelerometro": "off"}
            ),
        }

    def _tique_lento(self) -> bool:
        if self.args.sem_pactl:
            return True
        alvos = list(self.uniqs)
        if not alvos:
            return True
        threading.Thread(target=self._ler_pactl, args=(alvos,), daemon=True).start()
        return True

    def _ler_pactl(self, alvos: list[str]) -> None:
        try:
            from hefesto_dualsense4unix.integrations.audio_control import volume_da_captura

            novo: dict[str, dict[str, Any]] = {}
            for uniq in alvos:
                fonte = ""
                if self.mic is not None:
                    leitura = self.mic.leitura(uniq)
                    fonte = getattr(leitura, "fonte", "") if leitura else ""
                novo[uniq] = {
                    "rota_nada": False,
                    "mic_vol": volume_da_captura(fonte=fonte) if fonte else None,
                }
            GLib.idle_add(self._guardar_lento, novo)
        except Exception as erro:  # pragma: no cover
            print(f"aviso: faixa lenta falhou ({erro})", file=sys.stderr)

    def _guardar_lento(self, novo: dict) -> bool:
        self.lento.update(novo)
        return False

    def _js(self, script: str) -> None:
        """JavaScript solto — as mordidas e os cliques sintéticos. Para chamar"""
        self.ponte.rodar(script)

    def _gesto(self, o: dict) -> None:
        """tela → Python, já em JSON. Quem lê a mensagem e RECUSA o que não for"""
        gesto = o.get("gesto")
        if gesto == "roteiro":
            alvo = str(o.get("alvo") or "?")
            if o.get("achou"):
                self.alvos_vivos_do_roteiro += 1
            else:
                self.alvos_mortos_do_roteiro.append(alvo)
                print(f"[roteiro] ALVO MORTO: {alvo} não existe na página",
                      file=sys.stderr)
            return
        self.gestos.append(o)
        if gesto == "pintou":
            self.valores.append(int(o.get("valores") or 0))
            print(f'[pintura] {o.get("valores")} valores escritos · {o.get("ms")} ms na página')
            return
        if gesto == "interruptor-pintou":
            self.pinturas_do_interruptor += 1
            lado = str(o.get("lado") or "?")
            if not self.lados_do_interruptor or lado != self.lados_do_interruptor[-1]:
                self.lados_do_interruptor.append(lado)
            print(f'[interruptor] {o.get("valores")} valores escritos · '
                  f'aceso: {o.get("modo") or "NENHUM"} · '
                  f'a tela mostra: {lado}')
            return
        if gesto == "modo":
            chave = str(o.get("modo") or "")
            print(f"[gesto] modo → {chave}")
            print(f"         dono real: "
                  f"{DONOS_DOS_GESTOS.get(f'modo:{chave}', SEM_DONO)}")
            self._aplicar_o_modo(chave)
            return
        if gesto == "alvo":
            self.alvo = o.get("controle") or None
            print(f'[gesto] alvo → {o.get("radio")} ({self.alvo or "Todos"}) · '
                  f'dono real: {DONOS_DOS_GESTOS["alvo"]}')
            return
        if gesto == "sensor":
            chave = f'sensor:{o.get("sensor")}'
            novo = "on" if o.get("estava") == "off" else "off"
            uniq = str(o.get("controle") or "")
            estado = self.eco_sensor.setdefault(
                uniq, {"giroscopio": "off", "acelerometro": "off"}
            )
            estado[str(o.get("sensor"))] = novo
            print(f'[gesto] {chave} no controle {uniq} → {novo} (ECO, não grava)')
            print(f"         dono real: {DONOS_DOS_GESTOS.get(chave, SEM_DONO)}")
            self.ponte.dizer("HEF.eco", {**o, "estado": novo})
            return
        if gesto == "rota":
            chave = f'rota:{o.get("rota")}'
            self.eco_rota[str(o.get("controle") or "")] = str(o.get("rota"))
            print(f'[gesto] {chave} no controle {o.get("controle")} (ECO, não aplica)')
            print(f"         dono real: {DONOS_DOS_GESTOS.get(chave, SEM_DONO)}")
            self.ponte.dizer("HEF.eco", o)
            return
        if gesto == "mudo":
            chave = f'mudo:{o.get("bloco")}'
            uniq = str(o.get("controle") or "")
            estado = self.eco_mudo.setdefault(uniq, {})
            if o.get("bloco") == "mic-liberar":
                estado.pop("microfone", None)
                estado["mic_posse"] = False
                resposta = {**o, "bloco": "microfone", "estado": "off", "posse": False}
            else:
                novo = "off" if o.get("estava") == "on" else "on"
                estado[str(o.get("bloco"))] = novo
                if o.get("bloco") == "microfone":
                    estado["mic_posse"] = True
                resposta = {**o, "estado": novo,
                            "posse": bool(estado.get("mic_posse"))}
            print(f'[gesto] {chave} no controle {uniq} → '
                  f'{resposta["estado"]} (ECO, não manda um byte)')
            print(f"         dono real: {DONOS_DOS_GESTOS.get(chave, SEM_DONO)}")
            self.ponte.dizer("HEF.eco", resposta)
            return

    def relato(self) -> str:
        def resumo(nome: str, v: list[float]) -> str:
            if not v:
                return f"{nome}: sem amostra"
            s = sorted(v)
            return (
                f"{nome}: mediana {s[len(s)//2]:.2f} ms · p95 {s[int(len(s)*.95)]:.2f} "
                f"· max {s[-1]:.2f}"
            )

        def flag(v: bool | None) -> str:
            return {True: "LIGADO", False: "DESLIGADO de propósito"}.get(
                v, "nunca decidiu"
            )

        linhas = [
            f"voltas: {self.voltas} · remontagens: {self.remontagens} · "
            f"gestos: {len([g for g in self.gestos if g.get('gesto') != 'pintou'])}",
            f"roteiro: {self.alvos_vivos_do_roteiro} alvo(s) clicado(s) de "
            f"{len(ROTEIRO_DA_PROVA_DE_GESTO)}"
            + (f" · ALVOS MORTOS: {', '.join(self.alvos_mortos_do_roteiro)}"
               if self.alvos_mortos_do_roteiro
               else " · nenhum alvo morto"),
            f"valores escritos por pintura: {sorted(set(self.valores)) or 'NENHUM'}",
            f"interruptor: {self.pinturas_do_interruptor} pintura(s) · "
            f"{self.cliques_do_roteiro} clique(s) sintético(s) → "
            f"{len([g for g in self.gestos if g.get('gesto') == 'modo'])} gesto(s) "
            f"de modo — desde 31/08 a fileira não tem botão travado, então os "
            f"dois números TÊM de bater; a diferença seria botão sem ouvinte",
            f"aplicados: {self.aplicados or 'NENHUM'} · "
            f"recusados por falta de dono: {self.recusas_de_modo or 'nenhum'}",
            "o interruptor, LIDO DA TELA, na ordem: "
            + (" → ".join(self.lados_do_interruptor) or "NUNCA PINTADO"),
            "o disco (gamepad_disabled.flag), na ordem: "
            + (" → ".join(f"{quando}: {flag(v)}" for quando, v in self.lembrancas)
               or "NUNCA LIDO"),
            resumo("IPC ", self.custos_ipc),
            resumo("tela", self.custos_tela),
            resumo("volta", self.custos),
        ]
        if self.custos:
            s = sorted(self.custos)
            med = s[len(s) // 2]
            linhas.append(
                f"orçamento: {med / TIQUE_MS * 100:.1f}% dos {TIQUE_MS} ms do tique rápido · "
                f"{med / 500 * 100:.1f}% dos 500 ms"
            )
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
    p.add_argument("--sem-mic", action="store_true", help="não abre captura de microfone")
    p.add_argument("--sem-pactl", action="store_true", help="sem a faixa lenta")
    p.add_argument(
        "--cor-duble",
        help="códigos de fábrica separados por vírgula (ex.: 02,05) — a cor "
        "vem de um dublê em vez do aparelho, para provar a junta sem mandar "
        "byte nenhum ao controle",
    )
    p.add_argument("--arranca-enderecos", action="store_true",
                   help="MORDIDA: apaga os data-* e prova que a pintura desaba")
    p.add_argument("--prova-gesto", action="store_true",
                   help="dispara cliques sintéticos e prova o eco")
    p.add_argument("--prova-interruptor", action="store_true",
                   help="navega até a aba Jogar e LIGA e DESLIGA de verdade, "
                        "mostrando o gamepad_disabled.flag sumir e voltar")
    p.add_argument("--sem-interruptor", action="store_true",
                   help="MORDIDA: não instala a ponte na fileira de modos — a "
                        "--prova-interruptor tem de REPROVAR")
    p.add_argument("--abre", help="uniq do controle que nasce aberto (prova)")
    p.add_argument("--duble", help="JSON com um state_full — em vez do daemon")
    args = p.parse_args()

    if not PAGINA.exists():
        print(f"ERRO: a página desta aba não está em {PAGINA}", file=sys.stderr)
        return 2

    j = Janela(args)
    Gtk.main()
    if j.mic is not None:
        j.mic.stop()
    print("\n" + j.relato())

    if j.voltas == 0 and not args.sem_ponte:
        print("ERRO: a bancada não deu uma volta — nada foi medido.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
