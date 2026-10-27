#!/usr/bin/env python3
"""Gera a aba JOGAR — `src/hefesto_dualsense4unix/interface/paginas/01-jogar.html`."""
import collections
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import onde
import monta
import aba02
from monta import MASCARAS, MESA, glifo, monta as montar, svg

from hefesto_dualsense4unix.interface.frases_que_ela_baniu import (
    FRASES_BANIDAS,
)
from hefesto_dualsense4unix.interface.pacotes.a01_jogar import (
    CADEADO_CEGO,
    CADEADO_DICA,
    CADEADO_ROTULO,
    CHIP_DO_NATIVO,
    ESPERA_DICA,
    MARCA_DO_PRIMARIO,
    PRIMARIO_DICA,
    ROTULO_DO_NATIVO,
    mascaras_montaveis,
)

BATERIA = {"p1": 100, "p2": 64, "p3": 41, "p4": 87}


NATIVO_E_OS_JOGADORES = "quem conta os jogadores passa a ser o jogo."

INTERRUPTOR = [
    ("ligado", "gamepad", "Ligado",
     "Luz, vibração, gatilho e número do jogador pelo Hefesto"),
    ("desligado", "native", "Desligado",
     "Nenhum jogo recebe controle do Hefesto"),
]
HEFESTO_LIGADO = True
MODOS = [
    {"chave": "dualsense", "rot": "Sony DualSense", "modo": "",
     "sem_dono": False,
     "dica": "Pelo canal próprio do DualSense"},
    {"chave": "xbox", "rot": "Xbox", "modo": "",
     "sem_dono": False,
     "dica": "Pelo canal comum, igual ao controle de Xbox"},
    {"chave": "nintendo", "rot": "Nintendo Pro", "modo": "",
     "sem_dono": False,
     "dica": "Pelo canal do Pro Controller"},
]
MODO_ACESO = "dualsense"

DO_DESLIGADO = [
    {"chave": CHIP_DO_NATIVO, "rot": ROTULO_DO_NATIVO, "modo": "",
     "sem_dono": False,
     "dica": "O jogo fala direto com o controle, sem Steam"},
    {"chave": "steam", "rot": "Steam Input", "modo": "",
     "sem_dono": False,
     "dica": "A Steam traduz o controle para o jogo"},
    {"chave": "navegacao", "rot": "Navegação", "modo": "desktop",
     "sem_dono": False,
     "dica": "Vira mouse e teclado; o Hefesto segue lendo o controle"},
]
NATIVO_ACESO = CHIP_DO_NATIVO

PENDENTE = next(m["rot"] for m in MODOS if m["chave"] == MODO_ACESO)


CSS = """  .hef-rd{position:absolute;width:0;height:0;opacity:0;pointer-events:none}

  .hef-q > .quadro-topo{gap:8px}
  .hef-q > .quadro-topo > .quadro-titulo{margin-right:6px}
  .hef-pos{
    height:var(--h-acao);box-sizing:border-box;display:inline-flex;align-items:center;gap:9px;
    padding:0 18px;border-radius:7px;font-size:12.5px;
    border:1px solid var(--linha);background:var(--app-bg);color:var(--fg);
    cursor:pointer;user-select:none;
  }
  .hef-pos:hover{border-color:var(--comment);color:var(--texto-suave)}
  .hef-pos .pino{width:9px;height:9px;border-radius:50%;flex:0 0 9px;
                 border:1px solid var(--linha);background:transparent}
  .hef-q:not(:has(.hef-pos.on)) #hef-ligado:checked ~ .quadro-topo .hef-pos.ligado,
  .hef-q:not(:has(.hef-pos.on)) #hef-desligado:checked ~ .quadro-topo .hef-pos.desligado,
  .hef-pos.on{border-color:var(--purple);background:var(--sel-bg);
              color:var(--fg);font-weight:600}
  .hef-q:not(:has(.hef-pos.on)) #hef-ligado:checked ~ .quadro-topo .hef-pos.ligado .pino,
  .hef-pos.ligado.on .pino{background:var(--green);border-color:var(--green);
                           box-shadow:0 0 7px var(--green)}
  .hef-q:not(:has(.hef-pos.on)) #hef-desligado:checked ~ .quadro-topo .hef-pos.desligado .pino,
  .hef-pos.desligado.on .pino{background:var(--texto-mudo);
                              border-color:var(--texto-mudo)}

  .hef-q .so-ligado,
  .hef-q .so-desligado{display:none}
  .hef-q:not(:has(.hef-pos.on)):has(#hef-ligado:checked) .so-ligado{display:block}
  .hef-q:not(:has(.hef-pos.on)):has(#hef-desligado:checked) .so-desligado{display:block}
  .hef-q:has(.hef-pos.ligado.on) .so-ligado{display:block}
  .hef-q:has(.hef-pos.desligado.on) .so-desligado{display:block}
  .hef-q .degrau{height:var(--h-acao)}
  .hef-q ~ .quadro.estica > .quadro-corpo{gap:6px}
  .degrau .silhueta{height:20px;width:auto;flex:0 0 auto;fill:currentColor}
  .degrau .silhueta.traco{fill:none;stroke-width:3.6}
  .degrau .silhueta.contorno path{stroke:currentColor;stroke-width:2.4}

  .so-desligado .degrau.on[data-hef-quando="nativo"]{
    border-color:#f8f8f2;background:rgba(248,248,242,.12);color:#fff}
  .so-desligado .degrau.on[data-hef-quando="steam"]{
    border-color:#8be9fd;background:rgba(139,233,253,.13);color:#d4f6fe}
  .so-desligado .degrau.on[data-hef-quando="navegacao"]{
    border-color:#ffb86c;background:rgba(255,184,108,.13);color:#ffd9b0}
  .hef [data-gesto]{min-height:24px}
  .degrau.sem-dono{border-style:dashed;color:var(--fg);cursor:not-allowed}
  .degrau.sem-dono:hover{border-color:var(--linha);color:var(--fg)}
  .degrau.sem-dono i{border-style:dashed}
  .degrau i.tr{color:var(--fg);border-style:dashed}

  .quadro-topo{--w-canto:166px}
  .quadro-topo > .cadeado,.quadro-topo > .canto{
    display:inline-flex;align-items:center;justify-content:center;gap:9px;flex:0 0 auto;
    width:var(--w-canto);height:var(--h-acao);padding:0 16px 0 12px;
    box-sizing:border-box;border-radius:999px;
    font:600 13.5px/1 'Space Grotesk',system-ui,sans-serif;white-space:nowrap;cursor:pointer}
  .quadro-topo > .canto{margin-left:auto;border:1px solid var(--border-forte);background:transparent;
                        color:var(--texto-suave)}
  .quadro-topo > .canto:hover{border-color:var(--texto-suave);color:var(--fg)}
  .quadro-topo > .canto .gira{flex:0 0 auto}
  .cadeado{border:1px solid var(--border-forte);background:var(--app-bg);
           color:var(--fg)}
  .cadeado .p{width:11px;height:11px;border-radius:50%;flex:0 0 auto;
              background:var(--border-forte);box-shadow:none}
  .cadeado.ligada{border-color:var(--green);background:rgba(80,250,123,.09);
                  color:var(--green)}
  .cadeado.ligada .p{background:var(--green);box-shadow:0 0 6px var(--green)}
"""


_BATERIA_GLIFO = glifo("bateria", tam=13).replace("<title>Bateria</title>", "")


_BLOCO_DAS_CORES = re.compile(r'<defs id="[^"]*cores-do-dualsense">.*?</defs>', re.S)


def _tabela_das_cores():
    """As 28 cores dela, publicadas UMA vez — 03/09/2026, e é a lei de produto."""
    achou = _BLOCO_DAS_CORES.search(monta.DS)
    if not achou:
        raise SystemExit(
            'ERRO em 01-jogar: o <defs id="cores-do-dualsense"> sumiu do '
            "ds_limpo.svg. Sem ele os quatro desenhos ficam sem regra nenhuma "
            "e caem no cinza cru — rode scripts/gerar_cores_do_dualsense.py.")
    return achou.group(0)


TABELA_DAS_CORES = f'''    <svg class="cores-do-dualsense" aria-hidden="true" focusable="false"
         width="0" height="0" style="position:absolute">
{_tabela_das_cores()}
    </svg>
'''


def _desenho(c):
    """O desenho de um controle da MESA, pronto para o cartão."""
    x = re.sub(r"<\?xml[^>]*\?>\s*", "",
               svg(f'jg-{c["pref"]}', c["cor"], lampadas=False))
    x = _BLOCO_DAS_CORES.sub("", x, count=1)
    x = x.replace(' data-controle="dualsense"', "", 1)
    return x.replace(
        "<svg ",
        '<svg data-campo="desenho" data-hef-alvo="atributo"'
        ' data-hef-atributo="data-colorway" ', 1)


_VAZIO = "—"


def _chips_de_mascara(escolhida):
    """Os três chips de máscara de UM cartão — os mesmos nos QUATRO lugares."""
    montaveis = mascaras_montaveis()
    razao = ("Esta máscara não está disponível. As que estão: "
             + ", ".join(sorted(montaveis)) + ".")
    fora = []
    for m in MASCARAS:
        inerte = m not in montaveis
        fora.append(
            f'                  <span class="chip{" inerte" if inerte else ""}'
            f'{" on" if m == escolhida else ""}"'
            + (f' data-dica="{razao}"' if inerte else "")
            + f' data-gesto="mascara" data-mascara="{m}"'
            f' data-campo="mascara-cartao" data-hef-alvo="classe"'
            f' data-hef-quando="{m}">{m}</span>')
    return "\n".join(fora)


VISTO_NO_NATIVO = (
    '<span class="visto-fixo" data-dica="Desligado: o jogo vê o controle como ele é">'
    '<svg class="cad" viewBox="0 0 12 12" width="11" height="11" aria-hidden="true">'
    '<path d="M3.6 5.2V3.9a2.4 2.4 0 0 1 4.8 0v1.3" fill="none" stroke="currentColor" '
    'stroke-width="1.2"/><rect x="2.3" y="5.2" width="7.4" height="5.4" rx="1.1" '
    'fill="currentColor"/></svg>DualSense</span>'
    '<span class="visto-legenda">O jogo vê o próprio controle</span>')


def cartao(c, bateria=None):
    """Um cartão da fileira: desenho na cor do plástico, rótulo e as máscaras.

    `bateria` é o único argumento, e existe porque a carga é o **único dado
    inventado** desta aba (a legenda o declara desde 26/08): no mockup ela vem
    da tabela `BATERIA`, e na aba viva vem do `state_full`. Sem este argumento
    a mesa viva de cinco controles levantaria `KeyError` no `p5` — no meio da
    remontagem, com a tela do usuário na frente.


    A MÁSCARA NÃO É DIGITADA. Ela sai de `monta.MESA[...]["mascara"]`, que é a
    mesma fonte que a Controles e a Conexões leem — e foi a divergência que a
    versão à mão criou: a 01 mostrava `P2 = DualSense` e `P3 = Xbox 360` contra
    o `P2 = Xbox 360` / `P3 = DualSense` da MESA, porque a fonte única existia e
    a tela de referência ficava de fora dela.

    OS ENDEREÇOS (29/08/2026, e o vocabulário é o do `aba02.py:379`)
    ----------------------------------------------------------------
    `data-controle` é o `uniq` do aparelho quando há um (a mesa viva) e o `pref`
    quando não há (o mockup, cuja mesa é escrita à mão) — a MESMA linha do
    `aba02.py:658`, e não uma segunda regra.

    **Os três `data-campo` do rótulo existem porque o rótulo TEM FILHOS.**
    Escrever `textContent` num elemento com filho apaga os filhos e força
    layout: era a armadilha medida do piloto da Controles. Cada valor que muda
    de segundo a segundo ganha aqui a sua própria FOLHA, e a folha é um `<span>`
    inline sem estilo — que é o que permite endereçar sem mover um pixel, que é
    a promessa desta mudança.

    A PELE, E O `title` QUE SAIU (03/09/2026, IDENTIDADE-VEM-DE-CIMA-01)
    --------------------------------------------------------------------
    O cartão trazia DUAS identidades cravadas, e as duas nomeavam o controle do
    desenho enquanto a fita do topo já nomeava o dela:

        style="--plastico:#ae335a"                        → a borda Cosmic Red
        title="Sony • Player 1 • Cosmic Red • USB"        → a dica Cosmic Red

    A **borda** virou a `<i class="pele">`, que tem endereço e alvo `cor` — o
    porquê da forma está no CSS, junto da regra.

    O **`title` SAIU, e não foi substituído por outro.** Três razões, e a
    terceira é a que decide:

    1. ele REPETIA o rótulo palavra por palavra, quatro pixels ao lado —
       `rotulo(c, "completa")` é `Sony • Player 1 • Cosmic Red • USB`, e o
       rótulo visível escreve as mesmas quatro coisas em três linhas. É a mesma
       conta que tirou o `<title>Bateria</title>` do glifo, vinte linhas acima;
    2. `title` é ATRIBUTO, e o piloto **não tem alvo de pintura para atributo**
       — a razão já estava escrita na `aba04.py`, na dica que saiu de lá pelo
       mesmo motivo. Toda dica escrita aqui fica congelada no que o gerador
       soube, e o gerador só sabe o mockup;
    3. logo, mantê-lo era escolher entre uma dica que MENTE (a de 02/09, que
       sussurrava "Cosmic Red" sob o cursor com o White na mão) e um endereço
       que não pinta nada — e a segunda é pior, porque zera a régua deixando a
       tela igualmente errada.

    UMA FUNÇÃO SÓ PARA OS QUATRO LUGARES (07/09/2026, QUATRO-NA-MESA-01)
    -------------------------------------------------------------------
    **O DEFEITO, medido com os QUATRO DualSense do usuário na mesa:** o daemon
    publicava quatro controles, a carga da aba chegava com
    ``colunas = {p1, p2, p3, p4}`` e ``ocupados`` com os quatro — e a tela
    mostrava DOIS. O P3 e o P4 continuavam dizendo travessão em tudo.

    **A CAUSA era esta função ter DOIS RAMOS.** O ramo do lugar vazio devolvia
    um cartão **sem nenhum ``data-campo`` por dentro**, e o passo 2 do piloto
    (`hefesto_vivo.py`) só sabe escrever onde há endereço::

        for(const raiz of document.querySelectorAll('[data-controle="'+pref+'"]'))
          for(const el of achar(raiz, k)) escrever(el, v);

    ``achar(raiz, k)`` procura ``data-campo="k"`` DENTRO do bloco. Sem endereço
    o dado dela chegava e não tinha onde pousar — zero escrito e zero erro, que
    é o modo de falhar que esta casa persegue. Medido no publicado de hoje:
    **9 endereços no P1 e no P2, 4 no P3 e no P4** — e os 4 eram o desenho e os
    três chips de máscara, os únicos dois que já tinham sido curados um a um
    (03/09) *pelo mesmo motivo, sem que ninguém curasse os outros sete*.

    **POR QUE UMA FUNÇÃO SÓ, e não dois ramos consertados:** dois ramos que
    duplicam estrutura foi exatamente o que produziu isto — um envelheceu e o
    outro não, sete vezes seguidas. A ``pele``, o ``jogador-espera``, o
    ``jogador``, a ``identidade``, o ``degradou-cartao``, o
    ``marcador-principal`` e a ``bateria`` nasceram no ramo de cima e nenhum
    desceu. Agora ``conectado`` decide **só duas coisas** — a classe/atributo e
    o TEXTO inicial de cada campo —, e a estrutura é literalmente a mesma
    cadeia de caracteres para os quatro.

    **E A CENA QUE O USUÁRIO APROVOU NÃO MUDA UM PIXEL.** O que entra no lugar vazio
    ou nasce escondido pelo próprio CSS do ``off`` (a ``pele``, a marca
    "Sony •"), ou já é ``display:none`` em repouso nos quatro cartões (o
    ``e-primario``, sem a classe ``ha``), ou é um ``<span>`` inline sem estilo
    em volta do mesmo travessão. As duas regras que seguram isso estão no CSS,
    junto de ``.cartao.off``.

    **QUEM TIRA O ``off`` É O PILOTO**, no passo ``1c``, quando o controle
    chega — e é aí que o cartão do P3 fica idêntico ao do P1, marca e número
    inclusive. O gerador não decide nada disso: ele só garante que há onde
    escrever.
    """
    conectado = c.get("conectado", True)

    classe = ("cartao off" if not conectado
              else "cartao alvo" if c["alvo"] else "cartao")
    marca_de_conexao = "sim" if conectado else "nao"  # (noqa-acento)
    dica_do_lugar = "" if conectado else (
        '\n                   data-dica="Nenhum controle aqui"')
    jogador = f'Player {c["jogador"]}' if conectado else _VAZIO
    identidade = (f'{c["nome"]} <span class="pt">•</span> {c["via"]}'
                  if conectado else _VAZIO)
    carga = (f'{bateria if bateria is not None else BATERIA.get(c["pref"], "— ")}%'
             if conectado else _VAZIO)

    return f'''              <div class="{classe}"
                   data-controle="{c.get("uniq") or c["pref"]}" data-conectado="{marca_de_conexao}"{dica_do_lugar}>
                <i class="pele" data-campo="plastico" data-hef-alvo="cor" style="color:{monta.cor_da_zona(c["cor"])}"></i>
                <div class="peca-topo">
                {_desenho(c)}
                <span class="rotulo"><span class="fabricante">Sony <span class="pt">•</span> </span><b data-campo="jogador-espera" data-hef-alvo="classe" data-hef-classe="espera" data-dica="{ESPERA_DICA}"><span data-campo="jogador">{jogador}</span></b><br><span data-campo="identidade">{identidade}</span><span class="e-primario" data-campo="marcador-principal" data-hef-alvo="classe" data-hef-classe="ha" data-dica="{PRIMARIO_DICA}"> <span class="pt">•</span> {MARCA_DO_PRIMARIO}</span><br><span class="bat">{_BATERIA_GLIFO} <span data-campo="bateria">{carga}</span></span></span>
                </div>
                <div class="mascara">
{_chips_de_mascara(c["mascara"] if conectado else None)}
{VISTO_NO_NATIVO}
                </div>
              </div>'''


def frase_das_mascaras():
    """"P1 e P3 em DualSense, o P2 em Xbox 360 e o P4 em Nintendo Pro" — da MESA.

    A frase estava digitada na legenda e repetia o erro dos chips. Escrita aqui,
    ela não tem como discordar deles.
    """
    partes = []
    for m in MASCARAS:
        ps = [f'P{c["jogador"]}' for c in monta.CONECTADOS if c["mascara"] == m]
        if not ps:
            continue
        quem = " e ".join([", ".join(ps[:-1]), ps[-1]] if len(ps) > 2 else ps)
        partes.append(f"{quem} em {m}" if len(ps) > 1 else f"o {quem} em {m}")
    return ", ".join(partes[:-1]) + " e " + partes[-1]


CARTOES = "\n".join(cartao(c) for c in MESA)

_GIRA = (
    '<svg class="gira" viewBox="0 0 12 12" width="11" height="11" aria-hidden="true">'
    '<path d="M10 6a4 4 0 1 1-1.2-2.85" fill="none" stroke="currentColor" '
    'stroke-width="1.6" stroke-linecap="round"/>'
    '<path d="M9.4 1.2v2.4H7" fill="none" stroke="currentColor" stroke-width="1.6" '
    'stroke-linecap="round" stroke-linejoin="round"/></svg>')

_INTERRUPTOR = "\n".join(
    f'        <label class="hef-pos {lado}" for="hef-{lado}"'
    f' data-gesto="hefesto" data-modo="{modo}"\n'
    f'               data-campo="hef-posicao" data-hef-alvo="classe"'
    f' data-hef-quando="{lado}"\n'
    f'               data-dica="{dica}"><span class="pino"></span>{rot}</label>'
    for lado, modo, rot, dica in INTERRUPTOR)


CAMPO_DO_STEAM_INPUT = "steam-input-aceso"

CAMPO_DO_MODO = "modo-aceso"


def _campo_do_chip(m):
    """Por qual endereço este chip recebe o "estou aceso".

    **OS CHIPS DE CAMINHO PARTILHAM UM; O STEAM INPUT TEM O DELE** —
    STEAM-INPUT-01, 20/09/2026.

    Até aqui os quatro carregavam ``modo-aceso``, e o comentário de baixo dizia
    por quê: *"Um segundo clique não pode deixar dois acesos porque não há
    caminho em que duas chaves casem."* Isso valia enquanto os quatro eram
    exclusivos entre si — um CAMINHO (`dualsense`, `xbox`) ou um MODO
    (`navegacao`) de cada vez.

    O Steam Input não é exclusivo de nenhum deles: o degrau 4 da
    `ponte_escada.ESCADA` é ``Ponte(gamepad, dualsense, steam_input=True)`` e
    tem ``recria_vpad=False`` — ele senta EM CIMA do caminho DualSense.

    **FATO SUBSTITUÍDO — 21/09/2026.** Aqui se dizia que os dois passavam a
    poder estar acesos juntos; era o padrão da sprint enquanto a D-2 esperava a
    palavra de produto, e o usuário decidiu UM SÓ (*"dois botões ligados no modo"*). O campo
    próprio continua: é por ele que o emissor (`pacotes/a01_jogar.
    _estado_da_tela`) diz qual dos dois acende, porque o Steam Input não tem
    caminho e o laço do ``modo-aceso`` nunca o escolheria.

    **CUSTO ZERO DE PIXEL, e foi o que decidiu.** `data-campo` está em
    `scripts/check_o_desenho_aprovado.INVISIVEIS`, e a classe acesa continua
    sendo a MESMA ``on``. A alternativa — uma marca visual distinta para o Steam
    Input — exige CSS novo e `--publicar 01`, que é ato dela (§7 D-2).
    """
    return (CAMPO_DO_STEAM_INPUT if m["chave"] == "steam" else CAMPO_DO_MODO)


ARTE_DOS_CONTROLES = onde.RAIZ / "assets" / "control-svg"

SILHUETAS = {"dualsense": ("Sony-dualsense.svg", "contorno"),
             "xbox": ("xbox.svg", "traco"),
             "nintendo": ("Nintendo-pro_controller.svg", "")}


def silhueta(chave: str) -> str:
    """O desenho de linha do controle de um modo, tingido pela cor do texto do botão."""
    arquivo, estilo = SILHUETAS[chave]
    cru = (ARTE_DOS_CONTROLES / arquivo).read_text(encoding="utf-8")
    cru = re.sub(r"<\?xml[^>]*\?>", "", cru).strip()
    raiz = re.search(r"<svg[^>]*>", cru)
    tag = re.sub(r'\s(?:width|height|xmlns:bx)="[^"]*"', "", raiz.group(0))
    classe = f"silhueta {estilo}".strip()
    tag = tag.replace("<svg", f'<svg class="{classe}" aria-hidden="true" focusable="false"', 1)
    corpo = "".join(linha.strip() for linha in cru[raiz.end():].splitlines())
    return re.sub(r'"#(?:000|111)(?:000)?"', '"currentColor"', tag + corpo)


def _chip_do_modo(m, aceso=MODO_ACESO):
    """Um chip da fileira de modos: os três do Ligado ou os dois do Desligado."""
    classe = ("degrau"
              + (" on" if m["chave"] == aceso else "")
              + (" sem-dono" if m["sem_dono"] else ""))
    modo = f' data-modo="{m["modo"]}"' if m["modo"] else ""
    degrau = "" if m["chave"] == CHIP_DO_NATIVO else f' data-degrau="{m["chave"]}"'
    return (f'            <span class="{classe}"{degrau}'
            f' data-gesto="{m.get("gesto") or "modo-" + m["chave"]}"{modo}\n'
            f'                  data-campo="{_campo_do_chip(m)}"'
            f' data-hef-alvo="classe"'
            f' data-hef-quando="{m["chave"]}"\n'
            f'                  data-dica="{m["dica"]}">'
            f'{silhueta(m["chave"]) if m["chave"] in SILHUETAS else ""}{m["rot"]}</span>')


_MODOS = "\n".join(_chip_do_modo(m) for m in MODOS)

_MODOS_DO_DESLIGADO = "\n".join(_chip_do_modo(m, NATIVO_ACESO) for m in DO_DESLIGADO)


MIOLO = f'''
    <div class="quadro hef-q">
      <input type="radio" name="hefesto" id="hef-ligado" class="hef-rd"{" checked" if HEFESTO_LIGADO else ""}>
      <input type="radio" name="hefesto" id="hef-desligado" class="hef-rd"{"" if HEFESTO_LIGADO else " checked"}>
      <div class="quadro-topo">
        <span class="quadro-titulo" data-dica="Como o controle chega ao jogo. PS + R3 pula">Status</span>
{_INTERRUPTOR}
        <button class="canto" type="button" data-gesto="reconectar" data-dica="Desliga e liga de novo todos os controles">{_GIRA}Reconectar</button>
        <button class="cadeado" data-gesto="cadeado" data-campo="cadeado" data-hef-alvo="classe" data-hef-classe="ligada" data-hef-quando="LIGADO" data-dica="{CADEADO_DICA}"><span class="p"></span>{CADEADO_ROTULO}</button>
      </div>
      <div class="quadro-corpo hef">

        <div class="hef-modo so-ligado">
          <div class="escada">
{_MODOS}
          </div>
        </div>

        <div class="hef-modo so-desligado">
          <div class="escada">
{_MODOS_DO_DESLIGADO}
          </div>
        </div>

        {monta.ressalva(CADEADO_CEGO)}

      </div>
    </div>
{aba02.MIOLO}'''


LEGENDA = f'''<div class="nota">
  <h2>O que mudou, e por quê</h2>
  <ul>
    <li><b>"Trava o perfil ativo" virou <span class="marca">Modo Freestyle</span>, com letra e altura maiores</b> — sua palavra, 23/09:
      <span class="marca">"Vira Modo Freestyle o botão. E a fonte dele aumenta e a altura do botão
      aumenta também"</span>. A letra foi de 10,5 para <b>12,5 px</b>, a de todo botão desta janela;
      a altura, de 17 para <b>26 px</b>, a do botão de giroscópio no dia em que você o apontou como
      modelo. O que ele faz não mudou: ligado, o perfil que está valendo continua valendo; só o
      perfil próprio de um jogo entra por cima, como já era.</li>
    <li><b>O "Personalizado" virou <span class="marca">Freestyle</span></b> — é o perfil de fora do
      jogo, com os seus ajustes dos quatro controles; mudou só o nome. Do ligar o computador ao
      primeiro jogo <b>o topo diz Freestyle</b>, e o que você ajustar nas outras abas cai nele. O jogo
      com perfil próprio entra por cima, com o botão ligado ou não; com ele desligado, fechar o jogo
      devolve o Freestyle. O arquivo de antes fica no histórico, inteiro.</li>
    <li><b>A fileira plana virou DOIS NÍVEIS</b> — sua palavra, 31/08:
      <span class="marca">"vamos desconfundir isso que tal? Hefesto Ligado/Desligado (…) Modo
      Hefesto se Ligado Abre as seções de Modo"</span>. A pergunta que abriu isto também é sua
      — <span class="marca">"qual a diferença de nativo pra dualsense?"</span> —, e ela era
      boa: a tela punha os dois na <b>mesma</b> fileira, como alternativas do mesmo tipo. Não
      são. <b>Nativo é o Hefesto FORA do meio</b>; os outros são jeitos de ele <b>estar</b> no
      meio. Agora a tela mostra isso: em cima o interruptor, embaixo o que ele abre.</li>
    <li><b>E o interruptor SUBIU para fora do quadro</b> — sua decisão da tarde de 31/08,
      olhando a foto: ele tinha nascido <b>dentro</b> de "Quando o jogo abrir", e um quadro é um
      <b>escopo</b>. Ali ele lia como <i>"ligar o Hefesto quando um jogo abrir"</i>, e não é isso:
      <b>ligado ou desligado vale sempre</b>, com jogo aberto ou sem nenhum. O que o lançamento
      decide de verdade é o <b>modo</b>, e é só ele que fica no quadro.
      <br>A gramática é a da <b>fita</b> do topo da janela (<span class="marca">"{monta.ROTULO_DA_FITA}
      [Todos] [P1 · o plástico · USB]…"</span>): rótulo deitado, a fileira do que se escolhe, sem
      moldura, acima do que ela governa. O "Hefesto" nasce no <b>mesmo x</b> de "Quando o jogo
      abrir" e "Conectado agora" — os três títulos da aba numa coluna só.
      <br><b>E ela DEVOLVEU altura em vez de custar</b>, que era o risco: o quadro perdeu a linha
      do interruptor e a divisória que a separava dos modos (63px), e o que subiu custa 50 (a
      fileira de 36 mais o passo de 14 do miolo). Saldo <b>−13px</b>: o miolo pedia <b>514</b> de
      542 e passou a pedir <b>501</b>; a folga foi de <b>28</b> para <b>41px</b>, nas duas
      posições do interruptor.</li>
    <li><b>"Desligado" deixou de ser um estado inventado, e isso fecha a MIGRA-JOGAR-06</b> —
      sem construir nada. O quarto botão da fileira antiga não tinha leitor:
      <code>mode_transition.mode_of_state</code> é o ponto único de leitura do modo vivo e
      devolve <b>três</b> valores, nunca um quarto. Com a sua decisão, <b>Desligado = Modo
      Nativo</b> (<code>MODE_NATIVE</code>), que <b>lê</b> (o mesmo <code>mode_of_state</code>)
      e <b>escreve</b> (<code>apply_mode('native')</code>, em <code>painel.ESCRITOR_DOS_MODOS</code>).
      Parar o Hefesto inteiro continua sendo <b>"Parar o serviço"</b>, na Sistema — e o verbo
      é escolha dela de 31/08: <i>parar</i> é o que o <code>systemctl stop</code> faz e é o par
      de <i>Ligado</i>; <i>encerrar</i> sugeria fim definitivo, e o serviço volta no próximo
      login.</li>
    <li><b>O chip que se chamava "Hefesto" virou "Sony DualSense"</b> — ele sempre foi
      <code>Ponte(gamepad, dualsense)</code>, o primeiro degrau de
      <code>integrations/ponte_escada.ESCADA</code>. Era o nome do <b>produto</b> no lugar do
      nome da <b>máscara</b>, numa fileira em que os outros também são o Hefesto.</li>
    <li><b>O Xbox chegou à tela pela primeira vez</b> — <code>Ponte(gamepad, xbox)</code> é o
      <b>segundo</b> degrau que o produto tenta, e nenhum chip o nomeava. Era exatamente o que
      a conferência dos degraus denunciava: <span class="marca">"um degrau real não
      tem chip na tela"</span>. Agora tem.</li>
    <li><b>Os algarismos saíram, e é decisão dela de 31/08</b> — a tela escrevia
      <b>③ Steam Input</b>, o produto o tenta em <b>quarto</b>
      (<code>ponte_escada.indice_do_degrau + 1</code> = 4) e esta legenda prometia que o número
      ERA esse índice. Os três não podiam estar certos, e a causa é a própria decisão dela do
      mesmo dia: o terceiro degrau é o <b>Nativo</b>, que saiu da fileira para virar o
      interruptor <b>Desligado</b>. Havia três saídas — numerar <i>1 · 2 · 4</i> com o buraco do
      3, numerar pela posição na tela (e esta linha passar a mentir), ou tirar os números. Ela
      tirou. <b>A ordem não se perdeu</b>: está na dica de cada modo e na do quadro
      <b>Quando o jogo abrir</b>.</li>
    <li><b>A máscara virou POR CONTROLE</b> — decisão sua, 28/08. Três opções e
      <b>sem "Automático"</b>: DualSense · Xbox 360 · Nintendo Pro. O seletor mora dentro
      do cartão de cada controle. O que era um seletor único lá em cima
      (<span class="marca">"O jogo vê o controle como:"</span>) saiu do quadro
      <b>Quando o jogo abrir</b> — e o rótulo veio junto, no plural.</li>
    <li><b>Nenhum aviso do que se perde</b> — não há "você perde giro", "perde touchpad"
      nem "perde microfone" em máscara nenhuma. A dica diz o que muda de verdade: a máscara
      muda <b>o que o jogo vê</b>, e por isso os botões que ele desenha. O controle na sua
      mão continua o mesmo (<code>docs/usage/modos.md</code>) — a luz, o gatilho e o
      giroscópio seguem por conta do Hefesto em qualquer máscara. O microfone segue o
      <b>transporte</b>, não a máscara.</li>
    <li><b>"Automático" saiu da máscara</b> — substitui a <code>D-A-MASCARA-GANHA-O-AUTOMATICO</code>
      de 26/08, que o queria como terceira opção ligada. A heurística que o moveria
      (<code>api_de_entrada.py</code>) errou em <b>13 dos 14</b> jogos do seu censo.</li>
    <li><b>"Automático" saiu também do Modo de conexão</b> — sua palavra, 31/08:
      <span class="marca">"na aba jogar o Botão Automático não existe"</span>. E não existe
      mesmo: ele não tinha <b>leitor</b> (<code>painel.CHIPS_DA_ESCADA</code> o declarava com
      <code>ponte=None</code>, e o chip só acendia comparando pontes — nenhum
      estado do produto podia acendê-lo) nem <b>escritor</b> (não há método de IPC que fixe um
      degrau). <b>O mecanismo ficou</b>: tentar na ordem e parar quando acerta é o que o produto
      já faz sozinho, e está dito na dica.</li>
    <li><b>A fita ficou viva, e agora ela tem alvo</b> — era a contradição que esta legenda
      declarava em aberto: a fita dizia <span class="marca">"vai para o controle escolhido
      aqui"</span> numa aba em que nada era por controle. A máscara resolveu isso. O cartão
      do alvo leva o <b>mesmo realce do chip escolhido</b>, para os dois lerem como uma
      escolha só.</li>
    <li><b>O modo continua da máquina inteira</b>, e não desceu para o cartão junto com a
      máscara. Não é descuido: o modo é <b>estado do processo</b> — existe um só
      (<code>app/actions/mode_transition.py</code>), e duas peças pedindo modos diferentes
      não têm resposta. Máscara é do <b>aparelho</b>; modo é da <b>máquina</b>.</li>
    <li><b>O Point and click é do Ligado e a Navegação é do Desligado — os dois são o mesmo modo, e cada fileira tem três chips</b>
      — em 15/10 a opção A do desenho do todo substituiu a ordem de 31/08 (<i>"tira o point and
      click e deixa só o navegação"</i>): o Point and click volta, só no Ligado, e a Navegação
      passa a ser o terceiro chip do Desligado. A ordem de 17/09 segue: <i>"o modo point and click é o modo navegação e o modo que nós mesmos
      podemos usar e configurar na aba navegação. Ele ativa o modo configurado lá."</i>
      <br><b>Navegação</b> é o caso do meio, e é bom: o <b>modo</b> tem dono e funciona hoje
      (<code>apply_mode('desktop')</code>, o antigo "Controlar o PC"), e desde 17/09 ele
      <b>carrega o seu perfil</b> ao entrar — o mouse, as teclas, os botões e a função do
      teclado que você gravou na aba Navegação. O <b>PS + R3</b> para nela e entra pela mesma
      porta. O que ela não é, e por isso leva traço no lugar do algarismo, é degrau da escada
      automática: a ordem em que o Hefesto tenta sozinho não passa por ela.
      <br>Nenhum chip desta fileira entra <b>marcado</b> hoje. A marca continua desenhada —
      borda tracejada, cor explícita e cursor de "não clique", e nada de <code>opacity</code>,
      porque a lição da fita inerte é que a opacidade some com o texto e cega toda régua de
      contraste —, e ela está pronta para a próxima fileira que precisar dela.</li>
    <li><b>Quatro controles ligados, um cartão cada</b> — a lista é a <code>MESA</code> do <code>monta.py</code>: não há "quatro" escrito num laço, e o número do jogador é campo, não a posição na fila. Continua sendo só a peça, com o <b>SVG pequeno na cor do plástico</b> — o card completo é da aba Controles.</li>
    <li><b>A borda e a cor vêm do mapa</b> — a cor do plástico sai do <code>cores-do-dualsense.csv</code> pela folha que o gerador escreveu dentro do desenho. Não está digitada aqui.</li>
    <li><b>As cinco lâmpadas do jogador ficam apagadas neste cartão</b> — medido de novo hoje,
      no 1× da sua tela: cada lâmpada mede <b>1,06 × 0,36 px</b> no desenho de 62px, e acender
      as dez mudava <b>de 2 a 7 pixels de 2666</b> por cartão. Para se lerem, o cartão
      precisaria de ~460px — os quatro somariam 1840px numa fileira que tem 1163px. Quem diz
      o número aqui é o rótulo <b>Player N</b>; o padrão das luzes, desenhado grande, está na
      <b>Iluminação</b>.</li>
    <li><b>O botão do canto do bloco Modo (era "Trava o perfil ativo") mora na linha do título</b> — como o "Banco de provas" da Navegação. Embaixo dos modos ela lia como um quinto modo, e não é modo: é uma trava sobre o perfil. O rótulo é palavra dela de 11/09; o mecanismo, que era o rótulo antigo, passou para a dica no ponteiro do mouse.</li>
    <li><b>"Reconciliar jogadores" virou "Reconectar Controles"</b>.</li>
    <li><b>A área de avisos tem espaço reservado</b> e <b>conta quantos são</b>. Antes, três banners disputavam a linha e o primeiro escondia os outros. A barra vertical que a separa dos cartões agora vai até embaixo — era um toco de um terço, porque a coluna tomava a altura do único aviso.</li>
    <li><b>Nenhum ícone <b>?</b> na aba</b> — cada frase é uma dica curta, no mouse ou no foco, e os alvos de clique têm 24 px.</li>
  </ul>

  <h2>O que eu decidi por conta, e você pode derrubar</h2>
  <ul>
    <li><b>As três máscaras são chip, e não o botão de 36px do resto da janela</b>, e o preço
      está medido dos dois lados. Com o botão, as três somam 116px por cartão: o miolo pede
      <b>560px</b> e a janela oferece <b>542</b> — o quadro "Conectado agora" passava a rolar
      por dentro, com 18px do <b>Reconectar Controles</b> fora da tela. Com o chip a conta
      fecha em <b>502</b>. E não é uma altura nova: o <b>chip da fita</b>, três linhas acima,
      já é o seletor por controle desta casa, na mesma altura e com o mesmo destaque — o que
      muda é a direção, a fita deita e o cartão empilha.</li>
    <li><b>Empilhadas, e não lado a lado</b> — o cartão tem 208px e só "Nintendo Pro" pede
      ~104px; três na horizontal precisariam de ~326px. A saída seria dois cartões por
      fileira (423px cada), e o preço disso é desfazer <b>os quatro numa fileira só</b>, que é
      o que deixa todos os controles num relance. Se você preferir a horizontal, é esse o troco.</li>
    <li><b>As máscaras que aparecem escolhidas</b> — {frase_das_mascaras()}. É para você <b>ver</b> que a escolha é por controle; os seus quatro
      hoje são DualSense.</li>
    <li><b>Clicar num cartão leva a fita para ele</b> — é a mesma gramática que você fixou hoje
      para o acordeão da Controles ("clicar num card muda a fita").</li>
    <li><b>A ordem dos cinco modos não é a ordem em que você os listou</b>, e é a única coisa
      em que me afastei do seu texto. Você escreveu <span class="marca">"Steam Input, Xbox, Sony
      DualSense, Point And Click"</span>; eu pus <b>Sony DualSense · Xbox · Steam Input</b>,
      que é a ordem <b>medida</b> em que o produto tenta
      (<code>ponte_escada.ESCADA</code>): a DualSense primeiro porque <b>dez</b> linhas do
      <code>mapa-controles.csv</code> só chegam ao jogo por ela, e o Steam Input por último
      porque é o único que exige <b>fechar a Steam, reabrir a Steam e reabrir o jogo</b>. Sem os
      algarismos, <b>a ordem da fileira é a única coisa que ainda diz o que o produto tenta
      primeiro</b> — trocá-la para a sua ordem passaria a afirmar que o Hefesto começa pelo Steam
      Input, e isso é falso e caro. <b>Se você preferir a sua ordem mesmo assim</b>, é uma linha
      no <code>MODOS</code>; mas então a dica de cada modo tem de deixar de dizer "é o primeiro
      que o Hefesto tenta", ou a tela volta a se contradizer.</li>
    <li><b>O rótulo "Hefesto" ficou DEITADO, ao lado do interruptor</b>, e não em cima como as
      outras linhas desta casa. Nasceu como pagamento de altura — o miolo tinha <b>2px</b> de
      folga em 542 antes do redesenho da manhã, e um rótulo por cima custa 22px. Esse aperto
      passou (a subida devolveu 13px, e a folga hoje é de 41), mas ele <b>continua deitado</b>
      porque é a forma que você desenhou (<span class="marca">"Hefesto Ligado/Desligado"</span>,
      tudo numa linha) — e porque é a da fita do topo da janela, que é o lugar de onde ele
      agora fala.</li>
    <li><b>O "?" dos modos subiu do rótulo "Modo" para o topo do quadro</b> — é consequência de
      o interruptor ter saído: com só os cinco modos dentro, a ajuda do quadro <b>é</b> a ajuda
      dos modos, e dois "?" a três linhas um do outro diriam a mesma coisa duas vezes. Nada de
      texto se perdeu — ele está inteiro no "?" do <b>Quando o jogo abrir</b>. De quebra os
      rótulos das duas posições ficaram idênticos (texto puro dos dois lados), que é o que já
      tinha custado <b>180 contra 176</b> quando divergiram.</li>
    <li><b>O nome da seção é "Modo", e não "Modo de conexão"</b> — é a sua palavra
      (<span class="marca">"Abre as seções de Modo"</span>). O quadro continua se chamando
      <b>Quando o jogo abrir</b>, e o de baixo <b>Conectado agora</b>: os dois títulos são seus,
      de 26 e 28/08, e não os troquei sem você pedir.</li>
    <li><b>Continua sem uma linha de JavaScript, mas o combinador mudou</b> — e a troca foi
      forçada, não gosto. Com o interruptor fora do quadro, os dois <code>radio</code> deixaram
      de ser irmãos das seções que abrem, e o <code>~</code> só enxerga irmão posterior. A saída
      óbvia — pendurar os dois <code>input</code> direto no miolo — <b>reprovou numa régua real</b>:
      o <code>regua.py</code> exige que todo filho direto do miolo comece no x do miolo e tenha a
      largura inteira, e um <code>input</code> de 0×0 é filho direto com largura própria; a cura
      teria custado um erro na régua da aba que <b>é a referência das outras nove</b>. O que
      está lá é <code>:has()</code>, que não é mecanismo novo aqui: o esqueleto já abre e fecha
      as seções da <b>Conexões</b> com ele.</li>
    <li><b>A linha laranja tracejada não acende mais na tela</b> (13/09): o clique troca o modo na hora. Sem nada a aplicar, a faixa sai inteira, com a linha de cima (21/10), e o <b>Reconectar controles</b> fica no canto do quadro.</li>
    <li><b>A carga de cada bateria é o único dado inventado desta aba</b> — 100, 64, 41 e 87%. Bateria é estado do momento, e o mockup mostra um momento; todo o resto (cor, nome, transporte, jogador, desenho) sai de arquivo.</li>
    <li><b>O recibo do rodapé nomeia o perfil</b> — é onde a mudança vai cair, que era a informação que faltava e te custou semanas.</li>
  </ul>

  <h2>O que isto encomenda ao código</h2>
  <ul>
    <li><b>O interruptor tem de ler DOIS modos como "Ligado"</b>. Hoje a pintura viva acende um
      botão comparando <code>data-modo</code> com o modo do daemon, um a um — e o Hefesto ligado
      é <b>gamepad</b> <i>ou</i> <b>desktop</b> (Navegação). Sem uma leitura derivada
      (<code>ligado = modo in {{gamepad, desktop}}</code>) o interruptor fica apagado dos dois
      lados quando você escolhe a Navegação: a tela não estaria mentindo, estaria muda — e mudo
      é pior, porque parece defeito.</li>
    <li><b>O Steam Input não se fixa pela tela</b>: não há método de IPC que o ligue, e ele só
      sobrevive com a Steam fechada. <b>Sony DualSense</b> e <b>Xbox</b> se fixam — cada clique
      escolhe o caminho, com o jogo aberto, e o <b>PS + R3</b> na sua mão faz o mesmo.</li>
    <li><b>A máscara Nintendo Pro não existe hoje</b>, e entra assim mesmo — isto é mockup, e
      mockup desenha o produto que vai existir. O catálogo do produto
      (<code>integrations/uinput_gamepad.py</code>, <code>FLAVORS</code>) tem <b>duas</b>
      entradas: <code>dualsense</code> e <code>xbox</code>. A terceira nasce como
      <b>MÁSCARA-NINTENDO-01</b>, com um invariante duro: o PID <b>não</b> pode ser o
      <code>0x2009</code> do Pro físico (VPAD-04 — vpad e aparelho real com o mesmo VID/PID
      somem juntos da Steam, e o jogo fica com zero controles). Boa parte já está pronta:
      <code>mascaras_validas()</code> deriva do catálogo, então o terceiro sabor passa a valer
      no disco e no portão do IPC <b>sem uma linha de edição</b>.</li>
    <li><b>A máscara já é por aparelho no código</b> (<code>daemon/subsystems/external_mask.py</code>,
      desde 15/08) — o registro por <code>MAC</code> e a herança existem. O que falta é <b>passar a
      identidade</b> em três lugares: <code>virtual_pad.make_virtual_pad</code>,
      <code>coop.py</code> e <code>gamepad.py</code>. Hoje ninguém a passa, e por isso a
      máscara viva é uma só para todos os controles — que é exatamente o que esta tela deixa de
      mostrar.</li>
    <li><b>Um fato do specs, para a sprint não prometer o que o aparelho não tem:</b> o
      Pro Controller <b>não tem</b> microfone, alto-falante, touchpad, lightbar RGB, gatilho
      adaptativo nem gatilho analógico (ZL/ZR são digitais) — 99 linhas do
      <code>mapa-controles.csv</code>. Nada disso é aviso para esta tela: máscara não é
      adoção. A máscara Nintendo Pro faz o <b>seu DualSense</b> aparecer como um Pro para o
      jogo; ela não faz o Hefesto adotar um Pro.</li>
  </ul>

  <h2>Ainda é sua a palavra</h2>
  <ul>
    <li><b>O microfone quando a máscara é Xbox 360 ou Nintendo Pro.</b> A ONDA-CONEXOES-06
      escreve que nessas máscaras o jogo não pergunta pelo microfone e por isso ele
      <b>some do jogo</b>, e cria o estado <b>Emulado</b> para tapar o buraco — uma fonte de
      captura virtual que qualquer jogo enxerga. É por isso que esta tela não escreve aviso
      nenhum. <b>Mas essa afirmação não tem medição</b>: não há uma linha de microfone ×
      máscara no <code>ensaios.csv</code>, e a régua que a provaria está escrita na própria
      sprint <b>sem dono</b>. Hoje quem entrega o mic ao jogo é a prioridade do WirePlumber,
      que é cega à máscara — o que <b>estreita</b> o buraco e ninguém sabe quanto. É uma
      sprint de bancada, e ela não está na fila.</li>
  </ul>
</div>

</body>
</html>
'''


def _dentro_da_grade_dos_assentos(corpo: str) -> str:
    """O `<div class="pecas">…</div>` INTEIRO, contado por `div` aberto e fechado."""
    marca = '<div class="pecas"'
    inicio = corpo.find(marca)
    if inicio < 0:
        return ""
    profundidade = 0
    i = inicio
    while i < len(corpo):
        abre = corpo.find("<div", i)
        fecha = corpo.find("</div>", i)
        if fecha < 0:
            return corpo[inicio:]
        if 0 <= abre < fecha:
            profundidade += 1
            i = abre + 4
            continue
        profundidade -= 1
        if profundidade == 0:
            return corpo[inicio:fecha + 6]
        i = fecha + 6
    return corpo[inicio:]


def _campos_por_lugar(fileira: str) -> dict[str, list[str]]:
    """Os `data-campo` de DENTRO de cada cartão, por `data-controle`."""
    fora: dict[str, list[str]] = {}
    marca = '<div class="cartao'
    i = fileira.find(marca)
    while i >= 0:
        profundidade = 0
        j = i
        while j < len(fileira):
            abre = fileira.find("<div", j)
            fecha = fileira.find("</div>", j)
            if fecha < 0:
                j = len(fileira)
                break
            if 0 <= abre < fecha:
                profundidade += 1
                j = abre + 4
                continue
            profundidade -= 1
            j = fecha + 6
            if profundidade == 0:
                break
        bloco = fileira[i:j]
        dono = re.search(r'data-controle="([^"]*)"', bloco)
        if dono:
            fora[dono.group(1)] = re.findall(r'data-campo="([^"]*)"', bloco)
        i = fileira.find(marca, j)
    return fora


_SEM_FECHO = frozenset((
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
))


def _ancestrais(html: str, classe: str) -> set[str] | None:
    """Todas as classes dos ELEMENTOS QUE CONTÊM o primeiro `.classe`.

    POR QUE UM ANALISADOR, e não um `split` no texto: a pergunta *"esta caixa
    está DENTRO daquela seção?"* é sobre aninhamento, e aninhamento não se lê
    contando `</div>`. A régua que este helper substituiu media a ORDEM no  (noqa-acento: verbo medir)
    arquivo (*"o cadeado vem depois de `so-desligado`"*) e por isso reprovou uma
    mudança de posição pedida pelo usuário como se fosse defeito — o instrumento
    respondia sobre a ordem do fonte, não sobre a árvore que o navegador monta.

    Devolve `None` quando a classe não está lá; um conjunto VAZIO é resposta
    legítima e diferente (o elemento existe e não tem ancestral com classe).

    O `html.parser` da biblioteca padrão basta e não custa dependência. **Duas
    armadilhas dele estão tratadas aqui, e as duas empilhariam errado em
    silêncio:**

    * **as tags SEM FECHO** (`<input>`, `<br>`, `<img>`) — quem as empilha nunca
      as desempilha, e a partir da primeira toda profundidade fica alta demais.
      A lista é a mesma de `frases_que_ela_baniu._SEM_FECHO`, e a razão também.
    * **as tags AUTOFECHADAS** (`<path/>`, `<circle/>`) — esta página embute os
      SVGs dos quatro controles, e são centenas. O `HTMLParser` chama
      `handle_startendtag`, cujo padrão dispara `handle_starttag` **e**
      `handle_endtag`: com a `<path/>` fora da lista de vazias, isso EMPILHA uma
      vez e DESEMPILHA uma vez — mas com ela dentro, só desempilha, e a pilha
      desce abaixo do zero. Por isso ele é sobrescrito: uma tag que abre e fecha
      no mesmo ponto não é ancestral de ninguém.
    """
    from html.parser import HTMLParser

    class Cadeia(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.pilha: list[set[str]] = []
            self.achado: set[str] | None = None

        def _classes(self, atributos) -> set[str]:
            for k, v in atributos:
                if k == "class" and v:
                    return set(v.split())
            return set()

        def _olhar(self, atributos) -> None:
            if self.achado is None and classe in self._classes(atributos):
                self.achado = {c for nivel in self.pilha for c in nivel}

        def handle_starttag(self, tag, atributos):
            self._olhar(atributos)
            if tag.lower() not in _SEM_FECHO:
                self.pilha.append(self._classes(atributos))

        def handle_startendtag(self, _tag, atributos):
            self._olhar(atributos)

        def handle_endtag(self, tag):
            if tag.lower() not in _SEM_FECHO and self.pilha:
                self.pilha.pop()

    cadeia = Cadeia()
    cadeia.feed(html)
    return cadeia.achado


def _conferir(doc):
    """As decisões da aba, conferidas NA SAÍDA. O gerador para se caírem."""
    corpo = doc.split('<div class="miolo">', 1)[-1].split('<div class="nota">', 1)[0]
    corpo = re.sub(r"<!--.*?-->", "", corpo, flags=re.S)
    if len(corpo) < 2000:
        raise SystemExit("ERRO: a régua não achou o miolo — o recorte mudou de forma. "
                         "Uma régua que mede 0 caractere passa com qualquer desenho.")
    status = corpo.split('<div class="quadro hef-q">', 1)[-1].split('<div class="quadro estica">', 1)[0]

    falhas = []

    def exigir(cond, oquê):
        if not cond:
            falhas.append(oquê)

    exigir(corpo.count('<div class="quadro hef-q">') == 1 and len(status) > 1000,
           "o quadro do Status sumiu, ou nasceu duas vezes")
    for lado, esperados in (("so-ligado", [m["rot"] for m in MODOS]),
                            ("so-desligado", [m["rot"] for m in DO_DESLIGADO])):
        secao = status.split(f'class="hef-modo {lado}"', 1)[-1].split("</div>\n        </div>", 1)[0]
        achados = re.findall(r'<span class="degrau[^"]*"[^>]*>(?:<svg.*?</svg>)?([^<]+)</span>',
                             secao, re.S)
        exigir(achados == esperados,
               f"a fileira do {lado} saiu diferente do desenho: esperava {esperados}, achei {achados}")
        for rotulo in re.findall(r'<span class="degrau[^"]*"([^>]*)>', secao):
            exigir('data-dica="' in rotulo, f"um chip do {lado} ficou sem a dica curta")
    exigir([m["rot"] for m in MODOS] == ["Sony DualSense", "Xbox", "Nintendo Pro"],
           "os modos do Ligado não são Sony DualSense · Xbox · Nintendo Pro")
    ligado = status.split('class="hef-modo so-ligado"', 1)[-1].split('class="hef-modo so-desligado"', 1)[0]
    exigir(ligado.count('<svg class="silhueta') == len(MODOS),
           "um modo do Ligado ficou sem o desenho do controle dentro do botão")
    exigir("point-and-click" not in corpo and "Point and click" not in corpo,
           "o Point and click voltou ao modo: ele mora no estilo de jogo")
    exigir(corpo.count('data-gesto="modo-navegacao" data-modo="desktop"') == 1,
           "a Navegação não é o modo `desktop` do Desligado")
    exigir(len(re.findall(r'<span class="degrau', status)) == len(MODOS) + len(DO_DESLIGADO),
           "a fileira não tem os seis chips (três em cada lado)")
    exigir('class="' 'ajuda"' not in corpo and ">?<" not in corpo,
           "voltou um «?» à aba — as ajudas são dica no mouse (`data-dica`)")
    exigir(' title="' not in re.sub(r"<svg.*?</svg>", "", status, flags=re.S),
           "voltou um `title` ao Status — a dica é `data-dica`")

    for frase in ("sem giroscópio", "só chegam ao jogo por aqui",
                  "só chegam ao jogo pelo", "sem touchpad para o jogo"):
        exigir(frase not in corpo, f"um tooltip voltou a negar feature: {frase!r}")

    exigir('<span class="quadro-titulo" data-dica="Como o controle chega ao jogo. PS + R3 pula">Status</span>'
           in status, "o título do quadro de cima não é o Status")
    exigir(">Modo</span>" not in corpo and 'class="linha-rot">Status' not in corpo,
           "o quadro «Modo» ou a fileira solta do Status voltou")
    exigir("O controle é visto como" not in corpo and 'data-lista="cartoes"' not in corpo
           and 'data-gesto="mascara"' not in corpo,
           "o quadro «O controle é visto como:» voltou: o modo vale para todos os controles")
    exigir(corpo.count(">Dispositivos conectados</span>") == 1,
           "a estrutura da Controles não está na Jogar")

    tira = doc.split('<div class="tira">', 1)[-1].split("</div>", 1)[0]
    exigir('href="02-controles.html"' not in tira and ">Controles<" not in tira,
           "a Controles voltou à fita das abas: ela mora na Jogar")
    exigir(len(re.findall(r'class="aba[ "]', tira)) == len(monta.ABAS) == 9,
           "a fita das abas não tem as nove")
    exigir('class="conectado"' not in doc and 'data-campo="conta-b"' not in doc,
           "o contador «● N USB · N BT» voltou ao cabeçalho")
    exigir(f"{len(monta.CONECTADOS)} controles:" not in doc,
           "o «N controles:» voltou ao cabeçalho — ela o tirou em 22/09")

    for frase in FRASES_BANIDAS:
        exigir(frase not in corpo, f"um texto voltou a alarmar sem medição: {frase!r}")

    _por_campo = collections.Counter(_campo_do_chip(m) for m in MODOS + DO_DESLIGADO)
    exigir("steam" not in {m["chave"] for m in MODOS},
           "o Steam Input voltou a ser modo do Ligado — ela o tirou de lá em "
           "08/10/2026 («Steam Input sai de Ligado»)")
    exigir(_por_campo[CAMPO_DO_STEAM_INPUT] == 1,
           f"o chip do Steam Input não tem campo próprio: esperava 1 chip em "
           f"`{CAMPO_DO_STEAM_INPUT}`, a tabela dá {_por_campo[CAMPO_DO_STEAM_INPUT]}")
    for campo, quantos, oque in (
        ("hef-posicao", len(INTERRUPTOR), "as posições do interruptor"),
        (CAMPO_DO_MODO, _por_campo[CAMPO_DO_MODO], "os chips de CAMINHO da fileira de modos"),
        (CAMPO_DO_STEAM_INPUT, _por_campo[CAMPO_DO_STEAM_INPUT],
         "o chip do Steam Input, que tem campo próprio"),
    ):
        achei = status.count(f'data-campo="{campo}" data-hef-alvo="classe"')
        exigir(achei == quantos,
               f"{oque}: esperava {quantos} endereços `{campo}` com alvo "
               f"`classe`, achei {achei}")

    topo = status.split('<div class="quadro-topo">', 1)[-1].split('<div class="quadro-corpo hef">', 1)[0]
    ordem = [topo.find(marca) for marca in ('>Status</span>', 'class="hef-pos ligado"',
                                            'class="hef-pos desligado"', 'data-gesto="reconectar"',
                                            'data-gesto="cadeado"')]
    exigir(-1 not in ordem and ordem == sorted(ordem),
           "a linha do Status não é Status · Ligado · Desligado · Reconectar · Modo Freestyle, "
           "nesta ordem")
    exigir(corpo.count('data-gesto="reconectar"') == 1, "o Reconectar sumiu ou dobrou")
    folha = "".join(re.findall(r"<style[^>]*>(.*?)</style>", doc, re.S))
    exigir(".hef-pos{\n    height:var(--h-acao)" in folha
           and "width:var(--w-canto);height:var(--h-acao)" in folha,
           "os quatro botões da linha do Status deixaram de ter a mesma altura (`--h-acao`)")

    exigir(corpo.count('data-campo="cadeado" data-hef-alvo="classe"') == 1,
           "o cadeado perdeu o endereço de pintura (`cadeado` com alvo `classe`)")
    exigir(corpo.count('data-hef-classe="ligada" data-hef-quando="LIGADO"') == 1,
           "a pílula da trava perdeu a polaridade (`ligada` no `LIGADO`)")
    exigir(corpo.count('data-gesto="cadeado"') == 1, "o cadeado perdeu o endereço do clique")
    exigir(CADEADO_ROTULO in corpo, "o rótulo do cadeado sumiu da tela")
    exigir(CADEADO_DICA in corpo, "o cadeado ficou sem a razão na dica")
    for classe in ("cadeado", "canto"):
        familia = _ancestrais(corpo, classe)
        exigir(familia is not None and "quadro-topo" in familia
               and "so-ligado" not in familia and "so-desligado" not in familia,
               f"o `{classe}` saiu da linha do título do Status")

    folhas = re.sub(r"/\*.*?\*/", "", folha, flags=re.S)
    exigir(".degradou" not in folhas and "[title" not in folhas,
           "voltou regra de pintura que decide por `[title]` (ou a `.degradou`)")

    if falhas:
        raise SystemExit("ERRO em 01-jogar — decisão dela desfeita:\n  "
                         + "\n  ".join(f"- {f}" for f in falhas))
    aba02._conferir(doc, "01-jogar")


if __name__ == "__main__":
    import os
    import shutil
    import tempfile

    _real = onde.saida()
    _prova = pathlib.Path(tempfile.mkdtemp(prefix="hefesto-prova-01-"))
    for _vizinha in _real.glob("*.html"):
        shutil.copy2(_vizinha, _prova / _vizinha.name)
    os.environ[onde._DESVIO] = str(_prova)
    n = montar("01-jogar", "Jogar", MIOLO, aba02.CSS + CSS)
    _saida = onde.pagina("01-jogar.html")
    _saida.write_text(aba02.com_o_piso("02-controles", aba02.cor_do_plastico_por_regra(
        aba02.fita_clicavel(_saida.read_text()))))
    _conferir(_saida.read_text())
    shutil.copyfile(_prova / "01-jogar.html", _real / "01-jogar.html")
    shutil.rmtree(_prova)
    print(f"01-jogar: OK, {n} divs · mesa de {len(monta.CONECTADOS)} conectado(s) "
          f"+ {len(MESA) - len(monta.CONECTADOS)} lugar(es) vazio(s)")
