#!/usr/bin/env python3
"""controles_vivos.py — a aba Controles VIVA: o desenho dela com a mesa dela.

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
                          gatilho em 200/255). Se ela mostrar a mesa dela, o
                          dado não está vindo do daemon.
    --arranca-enderecos   apaga os `data-*` que o `aba02.py` escreve: a pintura
                          tem de DESABAR. Se não desabar, os endereços não
                          estavam sendo usados.

E o resto:

    --duble a.json        a mesa vem de um roteiro, não do daemon (chegada,
                          saída, mesa vazia, mesa de cinco, daemon calado)
    --abre <uniq>         qual card nasce aberto
    --prova-gesto         cliques sintéticos, para provar tela → Python → eco
    --cor-duble 02,05     a cor do plástico vem de um dublê, sem mandar um byte
                          ao aparelho
    --sem-cor  --sem-mic  --sem-pactl      desliga cada leitor, um a um

ESTA LEVA NÃO ESCREVE NADA. O único método de IPC que este programa pronuncia é
`daemon.state_full` (ver `mesa_viva.METODO`); os gestos da tela — os dois
interruptores de sensor, os dois botões de rota e os três botões de som (o 🎙,
o ♪ e o Liberar do microfone) — chegam ao Python, são registrados e **ecoam de
volta**. Nenhum perfil dela é tocado; o dono real de cada gesto está declarado
em :data:`DONOS_DOS_GESTOS`, num lugar só.

A JANELA, AS DUAS PONTES E A GUARDA DE CARGA SAÍRAM DAQUI em 29/08/2026: elas
são de todas as abas, não desta, e agora moram em
`hefesto_dualsense4unix.gui.ponte_da_tela` — com **as quatro armadilhas do
WebKit2 4.1** que este arquivo pagou, escritas lá em
:data:`~hefesto_dualsense4unix.gui.ponte_da_tela.AS_QUATRO_ARMADILHAS`. O que
sobrou aqui é a ABA: a mesa, a pintura e os gestos.

A armadilha que continua sendo deste arquivo, porque é da PINTURA e não da
ponte: `textContent` num elemento que TEM filho apaga os filhos e força layout —
a pintura escreve por TIPO (`txt`/`est`/`cls`), nunca "escreva isto aí".
"""
from __future__ import annotations

import argparse
import inspect
import json
import pathlib
import sys
import threading
import time
from collections import deque
from typing import Any

# A JANELA, AS DUAS PONTES E A GUARDA DE CARGA VÊM DA BIBLIOTECA, e é ela que
# crava os quatro pinos de `gi.require_version` (com o Gdk DEPOIS do Gtk).
# Importá-la ANTES de `gi.repository` é o que garante a ordem — não é import
# decorativo, é a ordem de inicialização do gi.
from hefesto_dualsense4unix.gui.ponte_da_tela import JanelaDaAba  # noqa: E402  isort:skip

from gi.repository import GLib, Gtk  # noqa: E402

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
RAIZ = pathlib.Path("/mnt/Apate/Desenvolvimento/hefesto-dualsense4unix")
sys.path.insert(0, str(RAIZ / "novo-layout" / "_ferramentas"))

import mesa_viva  # noqa: E402
import monta  # noqa: E402  (o gerador do mockup, usado como BIBLIOTECA)

import aba02  # noqa: E402  isort:skip

PAGINA = RAIZ / "novo-layout" / "02-controles.html"
TITULO_ESPERADO = "Hefesto — aba CONTROLES"

#: O tique rápido: o mesmo período da janela de hoje
#: (`app/constants.LIVE_POLL_INTERVAL_MS`). Ele lê SÓ o IPC.
TIQUE_MS = 100
#: A faixa lenta: o que sai de `pactl` (rota do som, alto-falante acordado,
#: volume do microfone). São subprocessos — a 10 Hz seriam trinta por segundo,
#: que é o custo que a carona de 0,5 Hz do produto existe para não pagar.
TIQUE_LENTO_MS = 2000

#: O DONO REAL DE CADA GESTO, DECLARADO NUM LUGAR SÓ. Nesta leva nenhum deles é
#: chamado — a aba é para ela AVALIAR, e um gesto que grave sem ela mandar é
#: dano. O que o clique faz hoje é chegar aqui, ser registrado e ecoar.
DONOS_DOS_GESTOS = {
    "sensor:giroscopio": "NÃO TEM DONO. Não há campo de sensor em "
    "profiles/schema.py nem método de sensor em daemon/ipc_server.py. "
    "A decisão dela de 18/08 (guardar giro e acelerômetro no perfil) "
    "está registrada e não foi construída.",
    "sensor:acelerometro": "NÃO TEM DONO, e o dado também não existe: "
    "daemon/sensor_hub.leitura() publica gyro e touchpad, e o mapa de canais "
    "dá movimento.acelerometro como não/não, os dois MEDIDOS.",
    "rota:jogo": "app/audio_saida.RotaDeSaida + status_actions."
    "_aplicar_rota_do_sistema — troca o default sink do SISTEMA, que é global.",
    "rota:pc": "app/audio_saida.RotaDeSaida (o mesmo dono) — e por ser global, "
    "dois controles com rotas diferentes é pergunta que o desenho faz e o "
    "produto ainda não responde.",
    "alvo": "app/alvo_de_edicao.definir_alvo (janela) + controller.target.set "
    "(daemon). Nesta leva o acordeão só RELATA quem está aberto.",
    # OS TRÊS DE SOM TÊM DONO — e é a diferença que importa em relação aos dois
    # interruptores de sensor acima: estes três JÁ SÃO produto que funciona na
    # janela de hoje. O que faltava era a tela nova ter onde ligá-los.
    "mudo:microfone": "mic.set {muted: bool} (daemon/ipc_handlers.py) pela ponte "
    "app/ipc_bridge.mic_set — é o botão de três caras do "
    "app/widgets/controller_card.py. Clicar faz o Hefesto ASSUMIR o registrador "
    "do mudo, e o botão físico do controle para de valer até o Liberar.",
    "mudo:mic-liberar": "mic.set {muted: null} — a MESMA chamada com `null`, que "
    "devolve a posse ao kernel (hid_playstation). É o TEXTO_BOTAO_MIC_DEVOLVER "
    "do produto, e ele nasce insensível porque sem posse não há o que devolver.",
    "mudo:alto-falante": "speaker.set {muted: bool} (daemon/ipc_handlers.py) pela "
    "ponte app/ipc_bridge.speaker_set. O daemon RECUSA sem volume conhecido — "
    "por isso o ícone nasce travado enquanto o volume for desconhecido.",
}

#: O que se diz de um gesto SEM linha na tabela acima. Era um `KeyError` cru:
#: `DONOS_DOS_GESTOS[chave]` derrubava a janela inteira quando a chave não
#: existia — e derrubar a tela dela para relatar um dono desconhecido é o pior
#: dos dois males. O gerador só emite chaves conhecidas, mas quem lê a tabela
#: não é só o gerador: é qualquer DOM, inclusive um adulterado por régua.
SEM_DONO = ("SEM LINHA na tabela de donos — este gesto chegou de um endereço que "
            "o gerador não escreve. Nada foi aplicado.")


# ---------------------------------------------------------------------------
# O gerador do mockup, usado como biblioteca
# ---------------------------------------------------------------------------
#: A cor do plástico quando o aparelho não a respondeu. O desenho pede um valor
#: para `--plastico`; a borda neutra do tema é o "não sei" desta linha, e é a
#: mesma saída que `cor_do_plastico.tom_para_a_borda` dá para tom vazio.
PLASTICO_DESCONHECIDO = "var(--border-forte)"

_cor_da_zona_real = aba02.cor_da_zona


def _cor_da_zona_tolerante(colorway: str, zona: str = "casca-solida") -> str:
    """`monta.cor_da_zona` PARA a geração quando o colorway não existe — e está
    certo para o mockup, onde a mesa é escrita à mão. Aqui a mesa vem do
    aparelho, e "não sei a cor" é resposta legítima: vira a borda neutra."""
    if not colorway:
        return PLASTICO_DESCONHECIDO
    try:
        return _cor_da_zona_real(colorway, zona)
    except SystemExit:
        return PLASTICO_DESCONHECIDO


#: Os DOIS nomes, porque são dois: `aba02` importou `cor_da_zona` de `monta`,
#: e quem desenha o chip da fita é o `monta.fita()`. Trocar um só deixava o card
#: com a borda neutra e a fita PARANDO a montagem — que foi o primeiro erro
#: desta leva, e é a cara do defeito de "corrigir pela metade".
aba02.cor_da_zona = _cor_da_zona_tolerante
monta.cor_da_zona = _cor_da_zona_tolerante

_luz_real = aba02.luz_do_jogador


def _luz_tolerante(c: dict[str, Any]) -> str:
    """A tabela de cor por jogador só tem cinco entradas; a mesa pode ter mais.

    E o valor é provisório de qualquer jeito: o tique o substitui pela cor VIVA
    que o daemon leu do sysfs, que é dado melhor do que a tabela.
    """
    try:
        return _luz_real(c)
    except Exception:
        return "#44475a"


aba02.luz_do_jogador = _luz_tolerante


#: Os kwargs que `aba02.bloco` aceita, LIDOS DA ASSINATURA DELE. O estado que a
#: mesa viva monta traz mais campos do que o desenho desenha (`alto_pct`, que é
#: o "não sei" do volume) — e o dia em que ela acrescentar um argumento ao
#: `bloco`, esta lista acompanha sozinha, em vez de o gerador levantar
#: `TypeError` no meio da execução do produto.
CAMPOS_DO_BLOCO = frozenset(inspect.signature(aba02.bloco).parameters) - {"c"}


def html_da_mesa(mesa: list[dict], estados: dict[str, dict]) -> str:
    """As caixas de controle, pelo gerador do mockup — nunca por HTML meu.

    É o que faz o desenho ACOMPANHAR a mudança por construção: quando ela mudar
    uma linha do `aba02.py`, esta aba muda junto, sem ninguém reescrever nada.
    """
    return "\n".join(
        aba02.bloco(c, **{k: v for k, v in estados[c["uniq"]].items() if k in CAMPOS_DO_BLOCO})
        for c in mesa
    )


def html_da_fita(mesa: list[dict]) -> str:
    """A fita de chips, também pelo gerador — e clicável, como nesta aba."""
    antes_monta, antes_aba = monta.MESA, aba02.MESA
    monta.MESA, aba02.MESA = mesa, mesa
    try:
        bruta = monta.fita(ativo=(mesa[0]["pref"] if mesa else "todos"))
        return aba02.fita_clicavel(bruta)
    finally:
        monta.MESA, aba02.MESA = antes_monta, antes_aba


def css_dos_chips(mesa: list[dict]) -> str:
    """A regra que acende o chip do controle aberto, para os prefs VIVOS.

    O `aba02.CHIP_ACESO` é gerado da mesa fixa de quatro; com cinco na mesa o
    quinto chip nunca acenderia, calado.
    """
    ids = ["c-todos"] + [f'c-{c["pref"]}' for c in mesa]
    alvo = ",\n  ".join(f'body:has(#{r}:checked) .chip[for="{r}"]' for r in ids)
    return f"{alvo}{{background:var(--sel-bg);color:var(--fg);font-weight:600}}"


def conta_da_altura(n: int) -> tuple[int, int]:
    """`(px para o card aberto, px de rolagem)` para uma mesa de N.

    A conta é a MESMA do `aba02.py` — mas lá ela roda em tempo de GERAÇÃO, com
    `len(MESA)` fixo em quatro, e aqui o número de controles é de tempo de
    EXECUÇÃO. Era a costura central deste piloto.

    Com N ≥ 5 o card aberto não cabe (o `assert` do gerador PARA aí, e está
    certo em parar: melhor recusar do que esconder um controle calado). Aqui a
    tela não pode parar — ela é o produto —, então a caixa ROLA, que é o mesmo
    recurso que o chip "Todos" já usa, e o número de pixels vai para o relato.
    """
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


# ---------------------------------------------------------------------------
# O JavaScript da ponte — escreve por TIPO, nunca "ponha isto aí"
# ---------------------------------------------------------------------------
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
      n += cls(q('[data-mudo="microfone"]', bm), 'on', d.mic.off);
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


def _leitor_duble(codigos: str | None) -> Any:
    """Um `ler_pelo_cabo` de mentira, que responde os códigos que se pedir.

    Existe para PROVAR a junta `código de fábrica → colorway do desenho →
    --plastico` sem mandar um byte ao aparelho dela. É o mesmo ponto de injeção
    que o próprio `cor_do_plastico.ler_pelo_cabo` já oferece (`perguntar=`) e que
    a suíte usa para não mandar comando de fábrica aos controles dela.
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
        self.alvo: str | None = args.abre or None
        self.chaves: tuple = ()
        #: os `uniq` da mesa de agora — a faixa lenta pergunta por eles
        self.uniqs: tuple[str, ...] = ()
        self.pronto = False
        self.custos: list[float] = []
        self.custos_ipc: list[float] = []
        self.custos_tela: list[float] = []
        self.voltas = 0
        self.rss: list[int] = []
        self.remontagens = 0
        self.gestos: list[dict] = []
        self.valores: list[int] = []
        #: O ECO, e ele mora SÓ AQUI — na memória desta janela, nunca no perfil
        #: dela. É o que faz o clique continuar valendo no tique seguinte em vez
        #: de o desenho voltar sozinho meio décimo depois; e é o que some quando
        #: a janela fecha, que é o contrato desta leva.
        self.eco_sensor: dict[str, dict[str, str]] = {}
        self.eco_rota: dict[str, str] = {}
        #: O eco dos três botões de som, por controle. Ele é o que sobrevive à
        #: pintura: sem isto o tique seguinte devolveria o estado do daemon e o
        #: clique dela sumiria em 100 ms — que é o que já acontecia com a rota.
        self.eco_mudo: dict[str, dict[str, Any]] = {}
        self.ondas: dict[str, deque] = {}
        self.lento: dict[str, dict] = {}
        self.leitor_de_cor = mesa_viva.LeitorDeCor(
            ligado=not args.sem_cor, leitor=_leitor_duble(args.cor_duble)
        )
        self.perguntando: set[str] = set()
        self.mic = None
        self._roteiro: list[dict] | None = None
        self._t0 = 0.0


        # A JANELA, A PONTE E A GUARDA SÃO DA BIBLIOTECA. O que sobra aqui é a
        # aba: a mesa, a pintura e os gestos. Antes desta leva estas 45 linhas
        # eram do piloto, e nove cópias delas seriam nove donos do mesmo valor.
        self.tela = JanelaDaAba(
            arquivo=PAGINA,
            titulo_esperado=TITULO_ESPERADO,
            ao_carregar=self._instalar,
            ao_receber=self._gesto,
            ao_sair_da_aba=self._saiu_da_aba,
            oculta=args.oculta,
            subtitulo="Controles — a mesa de verdade",
        )
        self.view = self.tela.view
        self.ponte = self.tela.ponte
        self.janela = self.tela.janela

    # -- carga -------------------------------------------------------------
    def _saiu_da_aba(self, titulo: str) -> None:
        """Ela clicou na tira. Sair da Controles só DESLIGA a pintura.

        As outras nove abas ainda são o mockup estático, e é exatamente o que
        elas devem parecer até a ordem de migração alcançá-las. Quem garante que
        isso não mata a janela é a guarda da biblioteca; o que é da aba — parar
        de pintar — é esta linha.
        """
        self.pronto = False
        print(f"[fora da Controles] {titulo} — o mockup estático; a pintura pausou.")

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
            if self.args.arranca_enderecos:
                # A MORDIDA DO ENDEREÇO: arranca os `data-*` que o `aba02.py`
                # passou a escrever e vê a pintura DESABAR. Um endereço a menos
                # não levanta erro nenhum no WebKit — o `querySelector` devolve
                # `null` e o valor simplesmente não é escrito. Se a conta não
                # cair, os endereços não estavam sendo usados.
                #
                # `campo` E `mudo` ENTRARAM EM 29/08, e a falta deles era o
                # mesmo buraco do `--prova-gesto` que nunca clicava o ♪: uma
                # régua que não toca um endereço não pode reprovar quem o
                # quebrar. `data-controle` fica de fora de propósito — arrancá-lo
                # derruba a pintura inteira de uma vez e a queda deixaria de
                # dizer QUAL endereço morreu.
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
        """Cliques SINTÉTICOS, para provar o caminho tela → Python → eco.

        Um clique de verdade não cabe numa prova automática (a janela é
        Offscreen), e clicar por coordenada é a armadilha que esta casa já pagou
        duas vezes. `el.click()` percorre o MESMO caminho de eventos do clique
        do rato: o `addEventListener` do bootstrap é o que responde.
        """
        # OS TRÊS BOTÕES DE SOM ENTRARAM NO ROTEIRO EM 29/08, e a ausência deles
        # era o motivo de o defeito ter atravessado: a régua clicava a faixa, um
        # interruptor de sensor e um botão de rota, e NUNCA o 🎙 nem o ♪ — dava
        # verde sobre dois botões mortos porque não os tocava.
        #
        # A ORDEM É A MORDIDA. O "Liberar" é clicado ANTES do 🎙, com a posse
        # ainda do kernel: ele está travado e tem de produzir ZERO gestos. Depois
        # o 🎙 assume a posse, e só então o Liberar responde e volta a travar.
        # Uma régua que só clicasse os três em qualquer ordem não distinguiria
        # "travado" de "sem ouvinte" — que é exatamente o defeito de origem.
        um = "document.querySelectorAll('.ctl')[1]"
        roteiro = [
            (1500, f"{um}.querySelector('.faixa').click()"),
            (2000, f"{um}.querySelector('.sw[data-sensor=\"giroscopio\"]').click()"),
            (2500, f"{um}.querySelector('.rota button[data-rota=\"pc\"]').click()"),
            (2800, f"{um}.querySelector('[data-mudo=\"mic-liberar\"]').click()"),
            (3100, f"{um}.querySelector('[data-mudo=\"microfone\"]').click()"),
            (3400, f"{um}.querySelector('[data-mudo=\"mic-liberar\"]').click()"),
            (3700, f"{um}.querySelector('[data-mudo=\"alto-falante\"]').click()"),
        ]
        for ms, script in roteiro:
            GLib.timeout_add(ms, lambda s=script: (self._js(s), False)[1])

    def _agendar_saida(self) -> None:
        foto = self.args.foto
        self.tela.agendar_saida(
            self.args.segundos or 0.0,
            antes=(lambda: self.tela.fotografar(foto)) if foto else None,
        )

    # -- microfone ---------------------------------------------------------
    def _ligar_o_microfone(self) -> None:
        """O microfone é o ÚNICO item desta aba que NÃO vem do IPC.

        Quem captura é a própria janela (`app/mic_monitor.MicMonitor`), e só
        enquanto a aba está à vista — sem isso um `parec` por controle ficaria
        gravando o microfone dela a sessão inteira.
        """
        try:
            from hefesto_dualsense4unix.app.mic_monitor import MicMonitor

            self.mic = MicMonitor()
            self.mic.set_ativo(True)
        except Exception as erro:  # pragma: no cover
            print(f"aviso: sem medidor de microfone ({erro})", file=sys.stderr)

    # -- os tiques ---------------------------------------------------------
    def _estado(self) -> tuple[dict | None, str]:
        """O `state_full` de agora — do daemon dela, ou do dublê.

        O DUBLÊ ACEITA UM ROTEIRO, e é assim que a chegada e a saída de controle
        se provam sem plugar nada na mesa dela: uma lista de
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
                "Hefesto desligado — abra a aba Sistema e clique em "
                f'"Ligar o Hefesto". ({erro})',
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
        for uniq in self.leitor_de_cor.pendentes(conectados):
            if uniq not in self.perguntando:
                self.perguntando.add(uniq)
                threading.Thread(
                    target=self.leitor_de_cor.perguntar, args=(uniq,), daemon=True
                ).start()

        mesa = mesa_viva.mesa_do_estado(state, self.leitor_de_cor.conhecidos(), alvo=self.alvo)
        if not mesa:
            self._mesa_ausente(
                "Nenhum controle na mesa agora. Conecte um pelo cabo ou pelo "
                "rádio — a mesa aparece sozinha, sem recarregar esta tela.",
                bolinha="○",
                cor="var(--orange)",
                conta=" 0 controles: ",
            )
            self.custos_ipc.append(t_ipc)
            self.voltas += 1
            return True

        if self.mic is not None:
            try:
                self.mic.set_controles(tuple(c["uniq"] for c in mesa))
            except Exception:
                pass

        estados = {}
        for c in mesa:
            entrada = next(e for e in conectados if str(e.get("uniq") or "") == c["uniq"])
            estados[c["uniq"]] = mesa_viva.estado_do_card(
                entrada,
                mic_vol=self.lento.get(c["uniq"], {}).get("mic_vol"),
                canal=self.lento.get(c["uniq"], {}).get("canal", ""),
                rota_pc=self.lento.get(c["uniq"], {}).get("rota_pc"),
                onda_mic=self._onda(c["uniq"]),
            )

        # A CHAVE DA REMONTAGEM É O QUE O GERADOR ESCREVE NO HTML, e não só quem
        # está na mesa. O produto reconstrói os cards quando o conjunto
        # `(index, uniq)` muda (`status_actions._status_card_keys_for`) e faz
        # diff no resto — a mesma disciplina. Aqui entram também a cor, o nome,
        # o transporte e o número do jogador, porque os quatro estão ASSADOS no
        # HTML da linha de identidade: sem eles, a cor que chega três segundos
        # depois (é uma pergunta ao aparelho, em thread) nunca apareceria.
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
        # UM VAZAMENTO NÃO APARECE NO RELÓGIO — aparece na memória. O `remonta`
        # troca o `innerHTML` do corpo inteiro, e um listener não removido por
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

    def _onda(self, uniq: str) -> list[int]:
        """As 14 barras do microfone — histórico deslizante, como o produto.

        Sem captura (`nivel is None`) a onda fica no PISO: uma linha baixa e
        chata, que é "não está entrando nada". Nunca uma onda animada com o
        último valor, que leria como som vivo.
        """
        fila = self.ondas.setdefault(uniq, deque([mesa_viva.PISO_DA_ONDA] * 14, maxlen=14))
        nivel = None
        if self.mic is not None:
            try:
                leitura = self.mic.leitura(uniq)
                nivel = getattr(leitura, "nivel", None) if leitura else None
            except Exception:
                nivel = None
        fila.append(mesa_viva.PISO_DA_ONDA if nivel is None else int(round(nivel * 100)))
        return list(fila)

    def _remontar(self, mesa: list[dict], estados: dict) -> None:
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
        # O texto do vazio é a CHAVE do estado vazio: trocar de "daemon calado"
        # para "mesa vazia com daemon vivo" é uma mudança de tela e tem de
        # repintar. Os dois são estados diferentes, e o produto já os separa.
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

    def _pintar(self, state: dict, mesa: list[dict], conectados: list[dict], estados: dict) -> None:
        self.ondas.pop("__vazio__", None)
        conta, conta_b = mesa_viva.texto_da_contagem(mesa)
        cards = {}
        for c in mesa:
            entrada = next(e for e in conectados if str(e.get("uniq") or "") == c["uniq"])
            cards[c["uniq"]] = self._pacote_do_card(c, entrada, estados[c["uniq"]])
        pacote = {
            "conta": conta[1:],  # o "●" é o `.bolinha`, elemento próprio
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
        # O ECO DOS TRÊS BOTÕES DE SOM, lido UMA vez: o que ela clicou vence a
        # leitura do daemon nesta tela, porque esta leva não manda um byte e a
        # leitura devolveria o estado de antes do clique a cada 100 ms.
        eco = self.eco_mudo.get(c["uniq"], {})
        eco_mic_mudo = (eco["microfone"] == "on") if "microfone" in eco else e["mic_mudo"]
        eco_alto_mudo = (eco["alto-falante"] == "on") if "alto-falante" in eco else e["alto_mudo"]
        eixos = {}
        # SÓ O GIROSCÓPIO. O laço percorria também `("acel", e["acel"])` e
        # endereçava `.eixo[data-eixo="acel-x"]`, que não existe mais na tela —
        # três buscas por card devolvendo nulo, caladas, a dez vezes por segundo.
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
                "estado": aba02.COM_TOQUE if e["tocando"] else aba02.SEM_TOQUE,
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
            # O ECO DOS BOTÕES DE SOM ENTRA POR CIMA DA LEITURA, do mesmo jeito
            # que o da rota já entrava: sem isto o tique seguinte devolveria o
            # estado do daemon e o clique dela sumiria em 100 ms.
            "mic": {
                "selo": "MUDO" if eco_mic_mudo else "ATIVO",
                "off": eco_mic_mudo,
                "onda": e["mic_v"],
                "vol_w": f'{e["mic_vol"]}%',
                "vol_n": str(e["mic_vol"]),
                "posse": bool(eco.get("mic_posse", e["mic_posse"])),
            },
            "alto": {
                "estado": (
                    "· Não ajustado"
                    if alto_pct is None
                    else (
                        f'· {alto_pct} % · {e["estado_alto"]}'
                        if e["estado_alto"]
                        else f"· {alto_pct} %"
                    )
                ),
                # A ONDA DO ALTO-FALANTE NÃO TEM FONTE, e não é omissão: o
                # produto desenha uma barra de VOLUME (`sensor_widgets.SpeakerBar`),
                # e nível de saída ninguém lê — o mapa dá `audio.alto_falante`
                # como "o Hefesto NÃO envia PCM". Fica no piso: uma linha baixa e
                # chata, que é "não estou medindo nada", e nunca uma onda animada.
                "onda": [mesa_viva.PISO_DA_ONDA] * 14,
                "vol_w": "0%" if alto_pct is None else f"{alto_pct}%",
                "vol_n": "—" if alto_pct is None else str(alto_pct),
                "mudo": eco_alto_mudo,
                "pode": e["alto_pode"],
                "rota": self.eco_rota.get(c["uniq"], "pc" if e["rota_pc"] else "jogo"),
            },
            # OS DOIS INTERRUPTORES NASCEM DESLIGADOS, e é a resposta honesta:
            # não há campo no perfil, método no IPC nem gate no daemon — grep de
            # `gyro_enab|motion_enab|sensor_enab` em `src/` devolve ZERO. Dizê-los
            # LIGADOS (como o mockup faz nos oito) seria a tela afirmando um
            # estado que ninguém guarda. O que o clique muda é o eco.
            "sw": self.eco_sensor.get(
                c["uniq"], {"giroscopio": "off", "acelerometro": "off"}
            ),
        }

    # -- a faixa lenta (pactl) --------------------------------------------
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
            from hefesto_dualsense4unix.app import audio_saida
            from hefesto_dualsense4unix.integrations.audio_control import volume_da_captura

            lista = audio_saida.rodar_leitura(["pactl", "list", "sinks", "short"])
            padrao = audio_saida.sink_padrao_da_saida(
                audio_saida.rodar_leitura(["pactl", "info"])
            )
            novo: dict[str, dict] = {}
            for uniq in alvos:
                sink = self.mic.sink_de(uniq) if self.mic is not None else ""
                canal = audio_saida.estado_do_canal(lista, sink) if sink else ""
                fonte = ""
                if self.mic is not None:
                    leitura = self.mic.leitura(uniq)
                    fonte = getattr(leitura, "fonte", "") if leitura else ""
                novo[uniq] = {
                    "canal": {"acordado": "Acordado", "dormindo": "Dormindo"}.get(canal, ""),
                    "rota_pc": bool(sink) and padrao == sink,
                    "mic_vol": volume_da_captura(fonte=fonte) if fonte else None,
                }
            GLib.idle_add(self._guardar_lento, novo)
        except Exception as erro:  # pragma: no cover
            print(f"aviso: faixa lenta falhou ({erro})", file=sys.stderr)

    def _guardar_lento(self, novo: dict) -> bool:
        self.lento.update(novo)
        return False

    # -- a ponte -----------------------------------------------------------
    def _js(self, script: str) -> None:
        """JavaScript solto — as mordidas e os cliques sintéticos. Para chamar
        uma função da página com dado, `self.ponte.dizer`, que serializa."""
        self.ponte.rodar(script)

    def _gesto(self, o: dict) -> None:
        """tela → Python, já em JSON. Quem lê a mensagem e RECUSA o que não for
        objeto JSON é a `PonteDaTela`; o que chega aqui é gesto de verdade."""
        self.gestos.append(o)
        gesto = o.get("gesto")
        if gesto == "pintou":
            self.valores.append(int(o.get("valores") or 0))
            print(f'[pintura] {o.get("valores")} valores escritos · {o.get("ms")} ms na página')
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
                # Liberar DEVOLVE a posse: o eco apaga o que o 🎙 tinha assumido,
                # e o próprio botão volta a ficar travado. É o único dos três que
                # muda o estado de OUTRO botão, e por isso ecoa os dois.
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
        # A RÉGUA POR BLOCO, e ela é o que uma volta só esconde: uma régua de
        # ontem rodou o tique UMA VEZ e não viu uma regressão que só aparecia em
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
    p.add_argument("--abre", help="uniq do controle que nasce aberto (prova)")
    p.add_argument("--duble", help="JSON com um state_full — em vez do daemon")
    args = p.parse_args()

    j = Janela(args)
    Gtk.main()
    if j.mic is not None:
        j.mic.stop()
    print("\n" + j.relato())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
