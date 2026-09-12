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
    --prova-interruptor   navega até a aba Jogar e LIGA e DESLIGA de verdade,
                          mostrando o `gamepad_disabled.flag` sumir e voltar
    --sem-interruptor     a MORDIDA do interruptor: não instala a ponte na aba
                          Jogar, e a `--prova-interruptor` tem de REPROVAR
    --cor-duble 02,05     a cor do plástico vem de um dublê, sem mandar um byte
                          ao aparelho
    --sem-cor  --sem-mic  --sem-pactl      desliga cada leitor, um a um

O QUE ESTE PROGRAMA ESCREVE, e é UMA COISA SÓ (31/08/2026)
----------------------------------------------------------
Até 30/08 este arquivo não escrevia nada. Mudou por pedido dela, literal: *"Não
sei se o botão de ativar ele na interface tá funcionando viu. não sei se segue
desativado."* e *"eu quero é que **ele funcione na interface e se lembre**"*.

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
`hefesto_dualsense4unix.gui.ponte_da_tela` — com **as quatro armadilhas do
WebKit2 4.1** que este arquivo pagou, escritas lá em
:data:`~hefesto_dualsense4unix.gui.ponte_da_tela.AS_QUATRO_ARMADILHAS`. O que
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

# A JANELA, AS DUAS PONTES E A GUARDA DE CARGA VÊM DA BIBLIOTECA, e é ela que
# crava os quatro pinos de `gi.require_version` (com o Gdk DEPOIS do Gtk).
# Importá-la ANTES de `gi.repository` é o que garante a ordem — não é import
# decorativo, é a ordem de inicialização do gi.
from hefesto_dualsense4unix.gui.ponte_da_tela import JanelaDaAba  # noqa: E402  isort:skip

from gi.repository import GLib, Gtk, WebKit2  # noqa: E402

# O INTERRUPTOR É PRODUTO, e vem de `src/` inteiro: `painel` responde qual botão
# acende, quem o aplica, por que um deles não tem quem o atenda e o que está
# GRAVADO no disco; `mode_transition` é o dono da sequência de IPC. Nada disso é
# reescrito aqui — o que sobra para este arquivo é o DOM.
from hefesto_dualsense4unix.app.actions import mode_transition
from hefesto_dualsense4unix.app.actions.jogar import painel

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
#: A raiz é a DESTE arquivo, e é assim que `sistema_viva.py` já fazia.
#:
#: FATO ERRADO, SUBSTITUÍDO (30/08/2026). Estava cravado::
#:
#:     RAIZ = pathlib.Path("/mnt/Apate/Desenvolvimento/hefesto-dualsense4unix")
#:     sys.path.insert(0, str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface"))
#:
#: — a ÁRVORE DELA, escrita à mão e inserida no `sys.path` DEPOIS do `AQUI`,
#: logo NA FRENTE dele. O efeito: rodar este piloto de uma árvore de agente
#: carregava o `mesa_viva`, o `monta`, o `aba02` e o `02-controles.html` **da
#: árvore dela**, não os da árvore de quem rodava. A edição do agente não valia
#: nada e ele via o comportamento antigo — calado, sem erro nenhum.
#:
#: MEDIDO em 30/08 às 00:31: curei o socket da variante no `mesa_viva` desta
#: árvore, rodei o piloto daqui, e ele continuou dizendo "Conexão recusada" —
#: porque o `mesa_viva.__file__` que ele importou era
#: `/mnt/Apate/.../hefesto-dualsense4unix/src/hefesto_dualsense4unix/interface/mesa_viva.py`.
#:
#: E é a mesma cicatriz que a regra da casa "A ÁRVORE DELA FICA EM `dev`" existe
#: para proteger, pelo outro lado: lá o perigo é o agente ESCREVER na mesa dela;
#: aqui era o agente LER dela sem saber.
# A RAIZ É `parents[2]` — ver a nota em `hefesto_vivo.py`, medida em
# 04/09/2026: com `[1]` o `RAIZ / "src"` virava `src/src`, que não existe.
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

#: O tique rápido: o mesmo período da janela de hoje
#: (`app/constants.LIVE_POLL_INTERVAL_MS`). Ele lê SÓ o IPC.
TIQUE_MS = 100
#: A faixa lenta: o que sai de `pactl` (rota do som, alto-falante acordado,
#: volume do microfone). São subprocessos — a 10 Hz seriam trinta por segundo,
#: que é o custo que a carona de 0,5 Hz do produto existe para não pagar.
TIQUE_LENTO_MS = 2000

#: O tique do INTERRUPTOR, quando a tela está fora da aba Controles. Ele lê só o
#: `state_full` (a mesma leitura do tique rápido) e pinta quatro botões — a 10 Hz
#: seria pagar o preço do card inteiro para desenhar uma fileira que muda uma vez
#: por sessão. Meio segundo é o piso do que se percebe numa fileira de modos.
TIQUE_DO_INTERRUPTOR_MS = 500

#: Quanto o clique dela continua valendo na tela enquanto o daemon não alcança.
#: Trocar de modo cria uinput e faz grab — o `MODE_IPC_TIMEOUT_S` do produto é
#: 2,0 s para a chamada, e o efeito ainda leva um tique de estado para aparecer.
#:
#: **O prazo é o que impede o F7 desta casa.** Sem ele o botão clicado ficaria
#: aceso para sempre, e a tela passaria a afirmar um estado que o daemon recusou
#: — que é exatamente o defeito que este interruptor nasceu para curar. Passado o
#: prazo, a verdade do daemon vence e o piloto DIZ, em voz alta, que o modo
#: pedido não foi alcançado.
PRAZO_DO_MODO_S = 4.0

#: O ROTEIRO DA `--prova-gesto`: `(ms, seletor CSS dentro do card)`.
#:
#: **ELE VIROU DADO EM 08/09/2026, e a razão é um instrumento que mentia.** Dois
#: dos sete passos clicavam `[data-mudo="mic-liberar"]` — botão que ela mandou
#: tirar em 30/08 e que aparece **zero vez** em `interface/paginas/02-controles.html`
#: e no `mockup/`. `querySelector` devolvia `null`, o `.click()` levantava
#: `TypeError` dentro do WebKit, e `_js` não lê retorno nem erro: **dois dos sete
#: passos batiam em nada e ninguém ficava sabendo.** É a mesma família que o
#: comentário abaixo já nomeia ao contrário — só que aqui a régua cobria um botão
#: que não existe mais, em vez de não cobrir um que existe.
#:
#: Como dado, ele ganha DOIS guardas que a lista embutida não podia ter: o portão
#: de suíte `tests/unit/test_a_prova_de_gesto_nao_clica_no_vazio.py`, que confere
#: cada seletor contra a página PUBLICADA sem abrir janela nenhuma; e, em tempo de
#: execução, o :func:`_clique_que_confessa`, que faz cada passo dizer se achou o
#: alvo em vez de estourar calado.
ROTEIRO_DA_PROVA_DE_GESTO: tuple[tuple[int, str], ...] = (
    (1500, ".faixa"),
    (2000, '.sw[data-sensor="giroscopio"]'),
    (2500, '.rota button[data-rota="pc"]'),
    (2800, '[data-mudo="microfone"]'),
    (3100, '[data-mudo="microfone"]'),
    (3400, '[data-mudo="alto-falante"]'),
)


def _clique_que_confessa(card: str, seletor: str) -> str:
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
    return (
        "(function(){var c=" + card + ";"
        "var e=c?c.querySelector(" + sel + "):null;"
        "window.webkit.messageHandlers.hefesto.postMessage(JSON.stringify("
        "{gesto:'roteiro',alvo:" + sel + ",achou:!!e}));"
        "if(e){e.click();}})()"
    )


#: O DONO REAL DE CADA GESTO, DECLARADO NUM LUGAR SÓ. Dos onze, **só os quatro
#: do modo aplicam** (e um dos quatro nem isso: o "Desligado" não tem escritor).
#: Os outros sete continuam eco — a aba é para ela AVALIAR, e um gesto que grave
#: sem ela mandar é dano.
#:
#: As linhas do modo NÃO SÃO DIGITADAS AQUI: são lidas de
#: `painel.escritor_do_modo`, que é o dono da resposta. Digitá-las seria a
#: segunda cópia — e é assim que onze réguas desta casa reprovaram a melhora em
#: vez do defeito, em 26/08: digitavam o que deviam LER.
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


def html_da_mesa(mesa: list[dict[str, Any]], estados: dict[str, dict[str, Any]]) -> str:
    """As caixas de controle, pelo gerador do mockup — nunca por HTML meu.

    É o que faz o desenho ACOMPANHAR a mudança por construção: quando ela mudar
    uma linha do `aba02.py`, esta aba muda junto, sem ninguém reescrever nada.
    """
    return "\n".join(
        aba02.bloco(c, **{k: v for k, v in estados[c["uniq"]].items() if k in CAMPOS_DO_BLOCO})
        for c in mesa
    )


def html_da_fita(mesa: list[dict[str, Any]]) -> str:
    """A fita de chips, também pelo gerador — e clicável, como nesta aba."""
    antes_monta, antes_aba = monta.MESA, aba02.MESA
    monta.MESA, aba02.MESA = mesa, mesa
    try:
        # A MESA VAI COMO ARGUMENTO, e não pelo `monta.MESA` acima. A troca
        # de `monta.MESA` NÃO alcança a fita: `monta.CONECTADOS` é derivado de
        # `MESA` no IMPORT (`[c for c in MESA if c.get("conectado", True)]`) e
        # nunca recalculado, e é sobre ele que `fita()` itera.
        #
        # MEDIDO NA TELA em 01/09/2026, com UM controle no cabo: o card dizia
        # `Starlight Blue · USB` e o topo `1 controle: 1 USB · 0 BT`, enquanto a
        # fita mostrava `P1 · Cosmic Red · USB` e `P2 · Starlight Blue · BT` —
        # o controle dela aparecendo no RÁDIO como P2 enquanto estava no cabo.
        # O `inerte` VAI EXPLÍCITO, e não pelo padrão — 05/09/2026. Esta bancada
        # serve a aba 02, que ESCOLHE controle, então o padrão `False` acerta
        # hoje. Mas foi contando com esse padrão que o piloto acendeu a fita das
        # sete abas de leitura e lhes deu o `title` de quem escolhe. Quem responde
        # é `monta.a_fita_escolhe`, e passar a resposta aqui faz a bancada seguir
        # a aba no dia em que ela mudar, em vez de repetir o defeito adormecido.
        bruta = monta.fita(
            ativo=(mesa[0]["pref"] if mesa else "todos"), mesa=mesa,
            inerte=not monta.a_fita_escolhe("02-controles.html"))
        return aba02.fita_clicavel(bruta, mesa=mesa)
    finally:
        monta.MESA, aba02.MESA = antes_monta, antes_aba


def css_dos_chips(mesa: list[dict[str, Any]]) -> str:
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

#: O INTERRUPTOR — a fileira `[data-modo]` de QUALQUER página que a tenha.
#:
#: Ele é separado do :data:`BOOTSTRAP` de propósito: aquele é da aba Controles e
#: endereça cards; este é da fileira de modos e endereça `[data-modo]`. A tira
#: navega, e o que segue com ela é a fileira — não o card.
#:
#: **Ele não decide nada.** Qual botão acende, qual está travado e o que o
#: `title` diz chegam prontos do Python, que os pergunta ao `painel`. Escrever
#: aqui um `if modo === 'gamepad'` seria o segundo dono da regra, na linguagem
#: em que ninguém a mede.
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
    """O nome da unidade, LIDO do produto — nunca digitado.

    A variante muda o nome inteiro (`hefesto-dev-dualsense4unix.service` com
    `HEFESTO_VARIANTE=dev`), e um literal nesta tela mandaria quem lê acordar o
    daemon da OUTRA casa.
    """
    from hefesto_dualsense4unix.daemon.service_install import SERVICE_NORMAL

    return str(SERVICE_NORMAL)


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
        self.gestos: list[dict[str, Any]] = []
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
        self.lento: dict[str, dict[str, Any]] = {}
        self.leitor_de_cor = mesa_viva.LeitorDeCor(
            ligado=not args.sem_cor, leitor=_leitor_duble(args.cor_duble)
        )
        self.perguntando: set[str] = set()
        self.mic = None
        self._roteiro: list[dict[str, Any]] | None = None
        self._t0 = 0.0
        #: O INTERRUPTOR: se a página à vista AGORA tem a fileira de modos ligada.
        self.interruptor_ligado = False
        #: O clique dela, valendo até o daemon alcançar — ou até o prazo estourar.
        #: `None` = a tela mostra o modo VIVO, que é o padrão e o estado honesto.
        self.eco_modo: str | None = None
        self.eco_ate = 0.0
        #: O que ESTE processo aplicou de verdade, na ordem — a régua do relato.
        self.aplicados: list[str] = []
        #: `(quando, o que o disco dizia)` a cada leitura do opt-out. É o que
        #: prova o "se lembre": o flag sumindo e voltando, medido daqui.
        self.lembrancas: list[tuple[str, bool | None]] = []
        self.pinturas_do_interruptor = 0
        #: Os lados que a TELA mostrou, na ordem, lidos do DOM. É a régua da
        #: cura de 31/08: com o `hefesto_ligado` arrancado esta lista trava num
        #: lado só, porque o rádio fica onde o mockup nasceu.
        self.lados_do_interruptor: list[str] = []
        self.recusas_de_modo: list[str] = []
        #: Quantos cliques SINTÉTICOS a `--prova-interruptor` mandou. Sem este
        #: número o relato não distingue "o botão estava TRAVADO" de "o botão
        #: nem foi clicado" — que é o buraco pelo qual o `--prova-gesto` deu
        #: verde sobre dois botões mortos em 29/08.
        self.cliques_do_roteiro = 0
        #: Os seletores da `--prova-gesto` que NÃO acharam alvo na página. Sem
        #: esta lista, um passo que bate em `null` some sem uma linha vermelha —
        #: foi assim que dois dos sete passos ficaram mortos de 30/08 a 08/09.
        self.alvos_mortos_do_roteiro: list[str] = []
        #: Os que acharam. Os dois números juntos é que separam "o botão estava
        #: travado" de "o botão nem existe".
        self.alvos_vivos_do_roteiro = 0


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
            subtitulo="Controles — o que o aparelho diz",
        )
        self.view = self.tela.view
        self.ponte = self.tela.ponte
        self.janela = self.tela.janela

        # O SEGUNDO OUVINTE DE CARGA, e ele precisa ser próprio. O
        # `ao_sair_da_aba` da biblioteca dispara UMA vez — na saída da aba desta
        # janela — porque a guarda dela só existe para não matar a janela numa
        # navegação legítima. Daqui em diante toda página é "fora da aba", e o
        # callback não volta a ser chamado: Jogar → Gatilhos → Jogar não
        # produziria evento nenhum, e o interruptor ficaria acreditando que ainda
        # está na página onde nasceu. `load-changed` é do WebView e chega em
        # TODAS as cargas; conectar um segundo handler é aditivo no GObject e não
        # toca numa linha de `ponte_da_tela`, que é de todas as dez abas.
        self.view.connect("load-changed", self._pagina_mudou)
        if not args.sem_interruptor:
            GLib.timeout_add(TIQUE_DO_INTERRUPTOR_MS, self._tique_do_interruptor)

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

    # -- o interruptor -----------------------------------------------------
    def _pagina_mudou(self, _view: Any, evento: Any) -> None:
        """Uma página TERMINOU de carregar — qualquer uma, inclusive a de volta.

        A ponte de gesto vive no `window` da PÁGINA: navegar a destrói junto com
        o `window` antigo. Por isso o estado do interruptor cai para desligado
        aqui, sempre, e é reinstalado só depois de a página nova responder que
        tem a fileira.
        """
        if evento != WebKit2.LoadEvent.FINISHED:
            return
        self.interruptor_ligado = False
        if self.args.sem_interruptor:
            return
        # Um tique de folga: o `FINISHED` chega antes de o `document` da página
        # nova estar pronto para responder `querySelector`. É o mesmo motivo pelo
        # qual a guarda de carga da biblioteca PERGUNTA à página em vez de
        # acreditar no evento.
        GLib.timeout_add(80, self._talvez_ligar_o_interruptor)

    def _talvez_ligar_o_interruptor(self) -> bool:
        """A página à vista tem a fileira de modos? Então ela ganha a ponte.

        A pergunta é feita ao DOM, nunca ao título: o endereço é `[data-modo]`,
        que é o que o gerador escreve. Casar por título seria digitar o que se
        pode LER — e o título do mockup carrega uma DATA ("mockup 26/08/2026"),
        que envelhece sozinha e desligaria o interruptor calado.

        A RESPOSTA TEM TRÊS VALORES, e o do meio é a ARMADILHA 1 do WebKit2
        (`ponte_da_tela.AS_QUATRO_ARMADILHAS`): o `FINISHED` chega mais de uma
        vez para a mesma página. MEDIDO em 31/08: a fileira era instalada DUAS
        vezes na mesma carga — a segunda respondia `4|0` (nenhum ouvinte novo,
        porque o `data-ligado` do JS já guardava), mas entre uma e outra o
        `interruptor_ligado` caía para falso e a pintura parava. Perguntar se a
        página JÁ tem o `window.HEFSW` separa "página nova" de "mesmo
        `FINISHED` de novo" sem confiar no evento — que é a mesma disciplina da
        guarda de carga da biblioteca.
        """

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
        """O que a fileira mostra AGORA — a verdade do daemon, com prazo do eco.

        O modo VIVO vence sempre, e o clique dela só o cobre enquanto o daemon
        não teve tempo de alcançá-lo. Passado :data:`PRAZO_DO_MODO_S` o eco cai
        **em voz alta**: um botão que continuasse aceso sozinho seria a tela
        afirmando um estado que o daemon recusou.
        """
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
                # OS TRAVADOS SÃO CALCULADOS, NÃO DIGITADOS: quem responde é o
                # `painel`, e o dia em que o "Desligado" ganhar escritor o botão
                # destrava sozinho.
                "travados": {
                    m.chave: painel.porque_nao_aplica(m.chave)
                    for m in painel.MODOS_DA_TELA
                    if painel.porque_nao_aplica(m.chave)
                },
                # A DICA DO "JOGAR PELO HEFESTO" É A RESPOSTA À PERGUNTA DELA.
                # *"não sei se segue desativado"* se responde com o que está
                # GRAVADO, não com o que está acontecendo: o daemon pode ter
                # acabado de subir, e o disco é quem diz o que ela decidiu.
                "dicas": {mode_transition.MODE_GAMEPAD: lembra.frase},
                # A POSIÇÃO DO INTERRUPTOR, e ela é DERIVADA — nunca a
                # comparação de um botão só. O Hefesto ligado é `gamepad` OU
                # `desktop` (a Navegação); comparando `data-modo` um a um, com o
                # modo vivo em `desktop` as duas posições ficam apagadas e a tela
                # fica MUDA, que parece defeito. Vem do `state`, e não do eco: a
                # seção que abre é a verdade do daemon, não o clique dela.
                "hefesto_ligado": painel.hefesto_ligado(state),
            },
        )

    def _aplicar_o_modo(self, chave: str) -> None:
        """O clique dela virando pedido — pelo dono, e só por ele."""
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
        """Cliques SINTÉTICOS na fileira de modos — os TRÊS, e todos aplicam.

        O ENDEREÇO QUE ESTE ROTEIRO PERDEU: até 30/08 ele começava clicando o
        `data-modo` do botão "Desligado", que era o botão sem dono, e a mordida
        era a ORDEM — o travado primeiro, com zero gestos. (O endereço não é
        escrito por extenso aqui de propósito: há régua que colhe os
        `querySelector` deste arquivo e os confere contra o HTML, e um exemplo
        citado dentro de um comentário entraria na conta como se fosse clique —
        é a mesma armadilha que o `01-jogar.html` declara no CSS do interruptor.) **Em 31/08 esse botão saiu
        do desenho** (ver a lápide `painel.MODO_DESLIGADO`), e `.click()` sobre
        um `null` levanta `TypeError` dentro do WebKit: a régua morreria calada
        no primeiro passo. Hoje a fileira não tem nenhum botão travado — os três
        modos têm leitor e escritor —, então cliques e gestos TÊM de bater, e a
        régua do "sem ouvinte" mudou de forma: é essa igualdade.

        A ORDEM CONTINUA SENDO MEDIDA: DESLIGA (Modo Nativo), LIGA (Jogar pelo
        Hefesto) e termina em `desktop` — que é onde a mesa dela estava quando
        esta prova começou. Deixar a máquina dela noutro modo porque uma régua
        rodou seria a régua mudando o produto pelas costas.
        """
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
        self.cliques_do_roteiro = len(roteiro) - 1  # o primeiro passo é a navegação

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
        # O "LIBERAR" SAIU DO ROTEIRO EM 08/09/2026, e a razão é que ele já
        # tinha saído da TELA em 30/08, por ordem dela. Dois dos sete passos
        # clicavam `[data-mudo="mic-liberar"]`, que aparece zero vez na página
        # publicada e no mockup: `querySelector` devolvia `null`, o `.click()`
        # levantava dentro do WebKit, e ninguém ficava sabendo. O comentário
        # aqui descrevia a ordem daquele roteiro — prosa medindo o mundo de
        # ontem, que é a mesma família do defeito. Ficam SEIS passos, todos com
        # alvo vivo, e o 🎙 clicado DUAS vezes (liga e volta), que é o que
        # sobrou da mordida da ordem depois de o "Liberar" sair.
        # A RÉGUA CLICA O ÚLTIMO CARD, E NÃO O SEGUNDO. FATO ERRADO,
        # SUBSTITUÍDO (30/08/2026): estava `document.querySelectorAll('.ctl')[1]`
        # — o SEGUNDO card, escrito quando ela tinha DOIS controles no cabo.
        #
        # MEDIDO em 30/08 às 00:37, com o controle dela de hoje: mesa de UM
        # controle → `.ctl[1]` é `undefined`, os cliques batem em `null`, e
        # a prova inteira produz **zero gestos** — sem uma linha vermelha. Mesa
        # de dois → sete cliques, seis gestos, tudo verde. O instrumento
        # desligava exatamente na mesa dela, e desligava CALADO: é "o
        # instrumento mente mais que o produto", de novo, e é a mesma forma dos
        # onze da leva de 26/08 — a régua desliga quando o alvo não está lá.
        #
        # `length-1` existe para toda mesa com pelo menos um card, então a prova
        # vale na mesa de um e continua valendo na de dois.
        um = "document.querySelectorAll('.ctl')[document.querySelectorAll('.ctl').length-1]"
        for ms, seletor in ROTEIRO_DA_PROVA_DE_GESTO:
            GLib.timeout_add(
                ms, lambda s=seletor: (self._js(_clique_que_confessa(um, s)), False)[1]
            )

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
            # O TEXTO MANDAVA PARA UM BOTÃO QUE NÃO EXISTE. Dizia *"abra a aba
            # Sistema e clique em 'Ligar o Hefesto'"*, e `grep -rn "Ligar o
            # Hefesto" layout/*.html` devolve ZERO: a aba Sistema tem "Retomar",
            # "Reiniciar o Hefesto", "Atualizar" e "Desligar o Hefesto" — o
            # caminho de volta não está desenhado lá. Mandar alguém para um botão
            # inexistente é a tela afirmando uma saída que ela não tem.
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
        for uniq in self.leitor_de_cor.pendentes(conectados):
            if uniq not in self.perguntando:
                self.perguntando.add(uniq)
                threading.Thread(
                    target=self.leitor_de_cor.perguntar, args=(uniq,), daemon=True
                ).start()

        mesa = mesa_viva.mesa_do_estado(state, self.leitor_de_cor.conhecidos(), alvo=self.alvo)
        if not mesa:
            self._mesa_ausente(
                # A FRASE TEM UM DONO SÓ — `a01_jogar.MESA_VAZIA`. Esta era a
                # TERCEIRA cópia digitada dela, e ela sobreviveu ao fecho de
                # 04/09 porque a régua (`test_a01_a_mesa_vazia_fala.py`) só
                # olhava o `jogar_vivo`. Achada em 11/09 ao aplicar a A3-017,
                # que encurtou a frase: a cópia ficaria falando sozinha.
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

    def _pintar(self, state: dict, mesa: list[dict[str, Any]], conectados: list[dict[str, Any]], estados: dict) -> None:
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
        # A AUSÊNCIA DE LEITURA NÃO VIRA "ATIVO" (MIC-DA-MESA-ELEICAO-01).
        # `mic_sabemos` é falso quando o `state_full` não trouxe a chave `audio`
        # — o que acontece no instante seguinte a um hotplug-out, porque o byte
        # é atributo de INSTÂNCIA do handle e o handle novo ainda não leu nada.
        # Num contrato em que aceso = está no ar, pintar ATIVO ali seria o
        # controle que acabou de cair anunciando que está capturando.
        # O eco do clique dela vence, porque aí houve leitura de verdade.
        # O DEFAULT SEGURO DE "NÃO SEI" É NÃO SEI (auditoria 02/09/2026). Aqui
        # se lia `e.get("mic_sabemos", True)`: no dia em que o `estado_do_card`
        # deixasse de emitir a chave, o card voltaria a mentir CALADO — que é o
        # mesmo `bool(None)` que esta onda foi curar, com outro nome.
        mic_sabemos = ("microfone" in eco) or e.get("mic_sabemos", False)
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
                # A PALAVRA DO TOUCHPAD MUDOU DE DONO em 02/09/2026, por decisão
                # dela (item 15): era `aba02.COM_TOQUE`/`SEM_TOQUE`, duas
                # constantes do pacote, e passou a ser `sensor_widgets.texto_toques`
                # — a mesma conta que a GTK faz (`controller_card.py:5079`). Lida
                # do `aba02`, como `pos` e `cor_da_zona` logo abaixo: este piloto
                # já lê tudo o mais de lá.
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
            # O ECO DOS BOTÕES DE SOM ENTRA POR CIMA DA LEITURA, do mesmo jeito
            # que o da rota já entrava: sem isto o tique seguinte devolveria o
            # estado do daemon e o clique dela sumiria em 100 ms.
            "mic": {
                # UM DONO SÓ para o selo, nos dois pintores (auditoria
                # 02/09/2026): `mesa_viva.selo_do_mic`.
                "selo": mesa_viva.selo_do_mic(eco_mic_mudo, mic_sabemos),
                "off": eco_mic_mudo and mic_sabemos,
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
            novo: dict[str, dict[str, Any]] = {}
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
        gesto = o.get("gesto")
        if gesto == "roteiro":
            # O PASSO CONFESSANDO — e ele NÃO entra em `self.gestos`: ele é o
            # instrumento falando de si, não gesto da tela. Contá-lo como gesto
            # inflaria justamente o número que a prova existe para medir.
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
            # O LADO É LIDO DO DOM, e é a régua da cura de 31/08: sem
            # `painel.hefesto_ligado` o rádio fica onde o mockup nasceu e a tela
            # abre a seção errada. `aceso` é o `.on` da fileira; `lado` é o
            # interruptor de verdade.
            lado = str(o.get("lado") or "?")
            # A LISTA GUARDA AS VIRADAS, não os valores distintos: com um `set`
            # de dois elementos "foi e voltou" e "foi e ficou" contam igual, e é
            # a volta que prova que a tela SEGUE o daemon em vez de travar.
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

        def flag(v: bool | None) -> str:
            return {True: "LIGADO", False: "DESLIGADO de propósito"}.get(
                v, "nunca decidiu"
            )

        linhas = [
            f"voltas: {self.voltas} · remontagens: {self.remontagens} · "
            f"gestos: {len([g for g in self.gestos if g.get('gesto') != 'pintou'])}",
            # O ROTEIRO CONFESSA, e esta linha é a cura do achado de 08/09: até
            # aqui um passo que batia em `null` sumia sem uma palavra, e a prova
            # dava verde sobre dois botões que ela mandou tirar em 30/08.
            f"roteiro: {self.alvos_vivos_do_roteiro} alvo(s) clicado(s) de "
            f"{len(ROTEIRO_DA_PROVA_DE_GESTO)}"
            + (f" · ALVOS MORTOS: {', '.join(self.alvos_mortos_do_roteiro)}"
               if self.alvos_mortos_do_roteiro
               else " · nenhum alvo morto"),
            f"valores escritos por pintura: {sorted(set(self.valores)) or 'NENHUM'}",
            # O INTERRUPTOR TEM RELATO PRÓPRIO, e ele é a régua desta leva. Uma
            # prova que só contasse "gestos" não distinguiria o clique que chegou
            # do clique que APLICOU — e é essa a diferença que ela pediu.
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
