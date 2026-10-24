# A PASTA, não /tmp: estas três liam um `monta` de /tmp — o de 26/08 23:50 —
import ast
import importlib.util
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import onde
from monta import acesos_da_fita as _acesos_da_fita
from monta import TOPO
from monta import (DS, MESA, CONECTADOS, CSS_GLIFO, CSS_POPUP, TRAVESSAO,
                   cor_da_zona, monta, player_slot_color,
                   ressalva as monta_ressalva, svg)

# geradores 08 e 09 pararam de RODAR por isso, calados até alguém tentar:
from onde import RAIZ as R

from hefesto_dualsense4unix.interface import conexoes as _aba_conexoes
from hefesto_dualsense4unix.integrations import entrada_a_entrada as _entrada_a_entrada

from hefesto_dualsense4unix.integrations import arranjo_da_mesa as _motor
from hefesto_dualsense4unix.integrations import dicas_da_conexao as _dicas
from hefesto_dualsense4unix.integrations import ordens_da_mesa as _ordens
from pacotes import a08_conexoes as _pacote08
from hefesto_dualsense4unix.mods import tema as _tema
import pacotes as _pacote_base

def _valor(no, ja):
    """O valor de um nó de AST, resolvendo NOME contra o que já foi lido."""
    if isinstance(no, ast.Name):
        return ja[no.id]
    if isinstance(no, ast.Attribute):
        return no.attr
    if isinstance(no, ast.Dict):
        return {_valor(k, ja): _valor(v, ja) for k, v in zip(no.keys, no.values)}
    if isinstance(no, ast.Tuple):
        return tuple(_valor(e, ja) for e in no.elts)
    if isinstance(no, ast.List):
        return [_valor(e, ja) for e in no.elts]
    return ast.literal_eval(no)


def _constantes(caminho, nomes):
    """As constantes de módulo daquele arquivo, lidas sem importar nada."""
    arvore = ast.parse(pathlib.Path(caminho).read_text())
    ja, achado = {}, {}
    for no in arvore.body:
        if isinstance(no, ast.Assign) and len(no.targets) == 1:
            alvo, valor = no.targets[0], no.value
        elif isinstance(no, ast.AnnAssign) and no.value is not None:
            alvo, valor = no.target, no.value
        else:
            continue
        if not isinstance(alvo, ast.Name):
            continue
        try:
            ja[alvo.id] = _valor(valor, ja)
        except (ValueError, TypeError, KeyError, SyntaxError):
            continue
        if alvo.id in nomes:
            achado[alvo.id] = ja[alvo.id]
    if faltam := set(nomes) - set(achado):
        raise SystemExit(f"ERRO: {caminho} não tem mais {sorted(faltam)} — "
                         f"a tela dependia deles.")
    return achado


RADIO = _constantes(
    R / "src/hefesto_dualsense4unix/integrations/radio_da_mesa.py",
    {"HZ_INPUT_SEM_MIC", "HZ_INPUT_COM_MIC", "HZ_AUDIO_COM_MIC"})

MULT = _constantes(R / "src/hefesto_dualsense4unix/daemon/subsystems/rumble.py",
                   {"RUMBLE_POLICY_MULT"})["RUMBLE_POLICY_MULT"]
_RUM = _constantes(R / "src/hefesto_dualsense4unix/core/rumble.py",
                   {"SEM_TETO"})
ORC = _constantes(R / "src/hefesto_dualsense4unix/app/actions/config/secao_orcamento.py",
                  {"PERFIS", "ROTULOS_DOS_PERFIS", "TETO_POR_PERFIL"})
ORC["SEM_TETO"] = _RUM["SEM_TETO"]

fala_do_teto = _aba_conexoes.fala_do_teto

PERFIL_DA_MESA = ORC["PERFIS"][0]
ORCAMENTO_DA_MESA = ORC["TETO_POR_PERFIL"][PERFIL_DA_MESA]
TETO_GLOBAL = fala_do_teto(ORCAMENTO_DA_MESA)

_alvo = R / "src/hefesto_dualsense4unix/app/fala_do_mapa.py"
_spec = importlib.util.spec_from_file_location("fala_do_mapa_da_tela", _alvo)
_fala = importlib.util.module_from_spec(_spec)
sys.modules["fala_do_mapa_da_tela"] = _fala
_spec.loader.exec_module(_fala)


def num(valor):
    """`1600` → `1.600`; `260.4` → `260,4`; `1106.8` → `1.106,8`."""
    inteiro, _, decimal = _fala.formata_pt_br(valor).partition(",")
    milhar = f"{int(inteiro):,}".replace(",", ".")
    return milhar if decimal == "0" and float(valor).is_integer() else f"{milhar},{decimal}"


# `DualSense` aqui sem ninguém ver.
def _estado_da_aba_controles(campos):
    arq = pathlib.Path(__file__).resolve().parent / "aba02.py"
    for no in ast.parse(arq.read_text()).body:
        if not (isinstance(no, ast.Assign) and len(no.targets) == 1
                and getattr(no.targets[0], "id", "") == "ESTADO"):
            continue
        fora = {}
        for chave, chamada in zip(no.value.keys, no.value.values):
            kw = {k.arg: k.value for k in getattr(chamada, "keywords", [])}
            if faltam := set(campos) - set(kw):
                raise SystemExit(
                    f"ERRO: o ESTADO da aba02 não tem mais {sorted(faltam)} em "
                    f"{chave.value!r}. A linha fechada desta aba mostra a máscara e a "
                    f"bateria de lá — se elas mudaram de nome, mude aqui também.")
            fora[chave.value] = {c: ast.literal_eval(kw[c]) for c in campos}
        return fora
    raise SystemExit("ERRO: `ESTADO` sumiu de aba02.py — o resumo da linha fechada "
                     "desta aba (máscara · microfone · bateria) sai de lá.")


#: divergia (a Jogar dizia que o P2 era DualSense e o P3 Xbox 360; a Controles e
DA_CONTROLES = _estado_da_aba_controles({"bat"})
if faltam := {c["pref"] for c in MESA} - set(DA_CONTROLES):
    raise SystemExit(f"ERRO: a MESA tem {sorted(faltam)} e o ESTADO da aba02 não.")

SEGUE_O_GLOBAL = _aba_conexoes.SEGUE_O_GLOBAL
BOTAO_DO_MIC = _pacote08.FALA_DO_BOTAO_DO_MIC[True]


CASA_DO_TETO_GLOBAL = _aba_conexoes.CASA_DO_TETO_GLOBAL
ABA_DO_TETO_GLOBAL = _aba_conexoes.ABA_DO_TETO_GLOBAL

SEM_NOME = _pacote08.SEM_NOME
ADAPTADORES = [
    {"nome": "Sala", "modelo": "TP-Link UB500", "onde": "Entrada 3",
     "detalhe": "traseira", "prefs": ["p2", "p3"]},
    {"nome": SEM_NOME, "modelo": "Intel AX211", "onde": "Interno",
     "detalhe": "M.2", "prefs": []},
]

RADIOS_VIZINHOS = [
    ("Intel AX211 (banda 2,4)", "Wi-Fi", False),
    ("Logitech Unifying", "Teclado", False),
    ("2.4G Wireless Rcvr", "— O que é? —", True),
    ("Unknown 0e8d:0608", "— O que é? —", True),
]

def sel(opcoes, escolhida, classe="pronto", dica="", gesto="", campo=""):
    """Um `<select>` com a opção escolhida marcada — uma forma só na tela."""
    marca = f' data-gesto="{gesto}"' if gesto else ""
    endereco = f' data-campo="{campo}" data-hef-alvo="valor"' if campo else ""
    corpo = "".join(f'<option{" selected" if o == escolhida else ""}>{o}</option>'
                    for o in opcoes)
    return f'<select class="{classe}" title="{dica}"{marca}{endereco}>{corpo}</select>'


_CRU_DA_SIGLA = {"USB": "usb", "BT": "bt"}

_PALAVRA = _constantes(
    R / "src/hefesto_dualsense4unix/app/actions/home_actions.py",
    {"_PALAVRA_DO_TRANSPORTE", "PALAVRA_DE_TRANSPORTE_DESCONHECIDO"})


def palavra_do_transporte(cru):
    """`usb` → `USB`, `bt` → `BT`. A tabela do dono, lida por AST."""
    bruto = str(cru or "").strip()
    if not bruto:
        return _PALAVRA["PALAVRA_DE_TRANSPORTE_DESCONHECIDO"]
    return _PALAVRA["_PALAVRA_DO_TRANSPORTE"].get(bruto.lower(), bruto)


def transporte_de(c):
    """`usb`/`bt` do controle da CENA — a chave CRUA, nunca a palavra da tela."""
    cru = str(c.get("transporte") or "").strip().lower()
    if cru:
        return cru
    sigla = str(c.get("via") or "")
    if sigla not in _CRU_DA_SIGLA:
        raise SystemExit(
            f"ERRO em 08-conexoes: o controle {c.get('pref')!r} diz via={sigla!r}, "
            f"que não é sigla de transporte, e a mesa do desenho não trouxe a "
            f"chave crua `transporte`. Quem pergunta transporte pergunta à chave "
            f"crua — a palavra da tela muda com o glossário.")
    return _CRU_DA_SIGLA[sigla]


def e_radio(c):
    """Este controle da cena fala por rádio? — uma comparação só para o arquivo."""
    return transporte_de(c) == "bt"


NO_CABO = [c for c in CONECTADOS if not e_radio(c)]
NO_RADIO = [c for c in CONECTADOS if e_radio(c)]

CAMPO_DAS_DICAS = "dicas"


#: o controle conhecido que pede para parear no desenho (O-CONTROLE-QUE-PEDE-PARA-PAREAR-…-01):
#: o «Roxo», ouvido pelo primeiro adaptador do desenho
PEDIDO_DO_DESENHO = {"aparelho": "AABBCC0000F7", "lugar": "L1", "nome": "Galactic Purple"}


def _dicas_da_cena():
    """As dicas da bancada, pelas MESMAS funções do produto (`a08_conexoes._html_das_dicas`).

    Os fatos são de mentira e dizem o que o desenho 4 mostra: um adaptador sufocado com o controle
    que a central manda para outro, o Wi-Fi colado nos rádios, o teclado só no hub (com o de→para)
    e uma conferência de energia, que cai em «mais 1».
    """
    frase = _ordens.Linha(texto="Ele emite ruído em cima da faixa dos controles.",
                          selo=_ordens.DERIVADO_DA_CONTA)
    fala_melhor = _ordens.Linha(
        texto="O receptor atrás de um hub perde sinal; direto no gabinete ele fala melhor.",
        selo=_ordens.DERIVADO_DA_CONTA)
    wifi = _ordens.Ordem(
        chave=_ordens.R1_RADIO_LARGO_NO_MESMO_HUB, acao="Mova o Wi-Fi", o_que_eu_vi=frase,
        por_que_importa=frase, ganho_esperado=frase)
    teclado = _ordens.Ordem(
        chave=_ordens.R4_TECLADO_SO_NO_HUB, acao="Mova o teclado", o_que_eu_vi=frase,
        por_que_importa=fala_melhor, ganho_esperado=frase, destino="9")
    painel = _dicas.montar(
        [
            _dicas.dica_do_pedido(PEDIDO_DO_DESENHO["aparelho"], PEDIDO_DO_DESENHO["nome"],
                                  "da Entrada 4", PEDIDO_DO_DESENHO["lugar"]),
            _dicas.dica_do_movimento(_dicas.Movimento(
                controle="p2", jogador=2, nome_do_controle="Starlight Blue", de_id="meio",
                de_nome="Meio", para_id="direita", para_nome="Direita", controles_no_de=3,
                bons=20, sufocado=True)),
            _dicas.dica_da_ordem(wifi, "atencao", slot=0, dica_de_ignorar=_pacote08.DICA_DO_IGNORAR),  # (noqa-acento): chave de máquina
            _dicas.dica_da_ordem(teclado, "atencao", slot=1, de="Entrada 4", para="Entrada 9",  # (noqa-acento): chave de máquina
                                 dica_de_ignorar=_pacote08.DICA_DO_IGNORAR),
            _dicas.dica_da_conferencia(
                "energia_das_portas", "Energia das entradas", "atencao",  # (noqa-acento): chave de máquina
                "A entrada 12 entrega menos corrente do que o aparelho pede."),
        ],
        ["Suporte ao controle", "Pareamentos salvos"])
    return _aba_conexoes.html_das_dicas(painel, _pacote08.icone_da_dica)


def tem_mic_pelo_radio(c):
    return e_radio(c)


#: escolhido. Pelo CABO o DualSense expõe placa USB Audio própria e o PipeWire a
#: DualSense" e "Bateria 100%". Medido em 28/08 nas quatro linhas.
def caminho_do_mic(c):
    return _pacote08.caminho_do_microfone(transporte_de(c))


# `a04_iluminacao.um_botao_de_player`.
rotulo = _pacote08.rotulo_do_controle


CSS = CSS_GLIFO + CSS_POPUP + """
  /* 6.1 · O RESPIRO DO RÓTULO QUE EXPANDE — 31/08/2026, pedido com duas
     fotos desta aba: *"o nome dos campos que expandem não tem respiro"*.

     MEDIDO no Chrome antes de mexer, e a medida acha a causa exata: o
     `.quadro-topo` do esqueleto é `padding:11px 14px 0` — **zero embaixo**. Num
     quadro comum isso não aparece, porque o conteúdo vem logo abaixo e traz o
     próprio respiro. Num acordeão FECHADO não vem nada: sobrava **1px** entre o
     texto e a borda de baixo da faixa, contra 12px em cima. O rótulo não estava
     centrado na faixa — estava encostado nela.

     A CURA DEFINITIVA É UMA VARIÁVEL NO `topo.html`, como a lista dela manda —
     e o `topo.html` está CONGELADO por decisão de produto de hoje, enquanto duas
     sessões trabalham na mesma árvore. Esta regra é local à Conexões, que é a
     única aba com acordeão de verdade (medido: `input.abre` = 3 aqui, 0 nas
     outras doze páginas). Quando o esqueleto descongelar, ela sobe para lá e
     esta some. */
  .quadro:has(> input.abre) .quadro-topo{padding-bottom:11px}
  /* A SEÇÃO ABERTA SOBE OS BLOCOS — 26/09/2026, pedido: *«tem uma linha
     abaixo do gestão de controles que não tá sendo usada. Deveriamos subir os
     blocos de seção pra ocupar ali de cima tambem»* (noqa-acento: citação literal).
     O respiro de baixo do rótulo (11px) é do acordeão FECHADO; aberto, o
     corpo vem logo embaixo e os dois respiros somavam 21px de faixa vazia. */
  .quadro:has(> input.abre:checked) .quadro-topo{padding-bottom:5px}
  .quadro:has(> input.abre:checked) > .quadro-corpo{padding-top:4px}

  /* O NOME DO ADAPTADOR É EDITÁVEL NO LUGAR — o botão `Renomear` saiu.
     `contenteditable` é o que o mockup faz sem JavaScript; o DUPLO clique que o usuário
     pediu é gesto do produto. O tracejado é o que diz que ali se escreve — sem
     ele o campo mente por omissão, parecendo texto morto. */
  .renomeia{border-bottom:1px dashed var(--linha);cursor:text}
  .renomeia:hover{border-bottom-color:var(--cyan)}
  .renomeia:focus{outline:none;border-bottom-style:solid;border-bottom-color:var(--cyan)}

  /* O LUGAR SEM CONTROLE na Gestão. A cor é a do `.vazio` da Gatilhos, que é a
     página que o usuário mandou copiar; o contraste está medido na prova de tela. A
     borda do plástico não vem — ela identifica a peça que está ali, e não há
     peça a identificar.

     A CLASSE ERA `fora` E PASSOU A SER `off` — 07/09/2026, e a troca é o que
     faz o lugar vazio VOLTAR quando o controle chega. `off` é a marca que o
     piloto conhece: ele a escreve no passo `1b` (lugar sem dono) e a TIRA no
     passo `1c` (lugar que ganhou dono). `fora` era palavra só desta aba, e
     nenhum passo do piloto a tirava — então um P3 que chegasse encontrava o
     cartão cinza, sem cursor e sem resumo, para sempre. Medido com os quatro
     DualSense do usuário na mesa em 07/09: o daemon publicava quatro, a carga
     chegava com os quatro em `ocupados`, e a tela mostrava dois.

     AS TRÊS REGRAS ABAIXO SÃO O QUE O USUÁRIO DECIDIU EM 31/08 — *"o espaço fica,
     mas o nome do canto muda"* — dito agora em CSS em vez de em estrutura. O
     cartão vazio carrega os MESMOS endereços do cheio (ver
     `linha_do_controle`), e o que ela vê continua sendo só o nome:

       · o RESUMO some. Máscara, microfone e bateria são leituras do aparelho,
         e não há aparelho; três travessões em fila diriam que a leitura
         FALHOU, e a ausência diz que o controle não está — que é a frase que
         estava escrita no ramo vazio antes de ele morrer.
       · as SETAS somem, porque não há corpo a abrir.
       · o `<label>` que envolve o nome perde o clique. Ele TEM de existir no
         HTML: o piloto escreve valores, não marcação, e um cartão que nasce
         sem gatilho não tem como ganhar um quando o controle chega. O
         comentário antigo dizia *"um lugar sem gatilho não tem como abrir"* e
         estava certo enquanto o cartão nunca seria preenchido; a partir do
         momento em que ele se enche, a garantia de estrutura vira o defeito.
         `pointer-events:none` é a mesma promessa, e ela se desfaz sozinha no
         tique em que o piloto tira o `off`. */
  .gc-item.off .gc-nome{color:var(--fg)}
  .gc-item.off{cursor:default;border-style:dashed}
  .gc-item.off .gc-cabeca{border-bottom:0}
  .gc-item.off .gc-resumo{display:none}
  .gc-item.off .gc-dono,
  .gc-item.off .gc-num{display:none}
  .gc-item.off .gc-nome b{color:var(--texto-suave);font-weight:600}
  .gc-item.off .gc-nome{font-weight:400}
  .gc-item.off .gc-nome .sep{margin:0 6px;color:var(--fg)}
  .gc-item.off .ds-mini{opacity:.3}
  .gc-item.off .gc-abre,
  .gc-item.off .gc-num{pointer-events:none;color:var(--fg)}

  /* ================= Conexões =================
     Três assuntos, três quadros, agrupados por PERGUNTA:
       1. "está tudo certo?"   — DUAS colunas: o que eu vi · o que fazer. A
          terceira ("o que só você sabe") saiu em 28/08: as duas perguntas de
          rádio passaram a morar no "Mapear Entradas", que é a janela onde
          ela já declara a sala.
       2. "Gestão de controles"   — os controles ligados, em acordeão: o da fita
          aberto, os outros na linha fechada com o resumo.
       3. "Rádio e adaptadores"— o inventário físico da mesa, e o Desempenho
          embaixo, separado, porque os turnos são POR ADAPTADOR.
     ------------------------------------------------------------------ */
  /* o "?" ao lado de um rótulo só vira bolinha se a linha for flex — solto num
     bloco ele herda `inline` e a largura/altura de 17px não valem nada */
  .linha-rot{display:flex;align-items:center;gap:8px;height:19px;margin-bottom:4px}
  /* DUAS colunas com a mesma gramática da Navegação e da Gatilhos — o nome é o
     mesmo de propósito: é a régua que confere a soma das colunas. */
  .duas-colunas{display:grid;grid-template-columns:1fr 1fr;gap:0;align-items:stretch}
  /* 17 e não 16: a barra de 1 px é `border-left` da coluna da direita e sai da
     LARGURA dela. Com 16 dos dois lados os dois botões do inventário mediam
     547,5 e 546,5 — a diferença que ela repara. O pixel volta aqui. */
  .duas-colunas > .lado-e{padding-right:17px}
  .lado-e,.lado-d{display:flex;flex-direction:column;min-width:0}
  .lado-d{padding-left:16px;border-left:1px solid var(--border-sutil)}
  .pilha{display:flex;flex-direction:column;gap:8px}

  /* ---- as dicas: cartões de poucas palavras, com UM botão ----
     AS-DICAS-SAO-CARTOES-COM-UM-GESTO-01 (04/10/2026), o desenho 4 que o usuário aprovou. Cor nunca
     sozinha: o nível tem borda E uma palavra para o leitor de tela (o nome da região), o desenho de
     cada tipo vai no ícone, e a ordem de leitura é título, de→para, botão. A fileira usa a grade
     dos cartões de baixo (vão de 10px). O ⓘ abre o porquê numa frase, e o «Ignorar» mora lá.
     05/10/2026, o desenho aprovado: até quatro, todos da MESMA altura, e o porquê abre POR CIMA
     (não estica os vizinhos); o gesto, curto, à direita. */
  .dicas{display:flex;flex-direction:column;gap:8px;margin-bottom:12px}
  .dicas-fileira{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
  @media (max-width:1180px){.dicas-fileira{grid-template-columns:repeat(2,minmax(0,1fr))}}
  .cartao-dica{position:relative;display:flex;flex-direction:column;gap:6px;min-width:0;
        height:96px;box-sizing:border-box;padding:9px 11px;
        border:1px solid var(--border-forte);border-left-width:3px;border-radius:7px;
        background:var(--app-bg)}
  .cartao-dica.nivel-grave{border-left-color:var(--red)}
  .cartao-dica.nivel-ajuste{border-left-color:var(--orange)}
  .cartao-dica.nivel-nota{border-left-color:var(--yellow)}
  .cd-cab{display:flex;align-items:center;gap:8px}
  .cd-ic{flex:0 0 auto;display:inline-flex;color:var(--texto-suave)}
  .cartao-dica .cd-ic svg.i{width:16px;height:16px;flex:0 0 16px}
  .cartao-dica h4{flex:1;min-width:0;margin:0;font-size:12.5px;font-weight:600;color:var(--fg);
           line-height:1.3}
  /* a palavra do nível mora no nome da região (`aria-label`), não num texto escondido: texto
     recortado de propósito é, para a régua da janela estreita, texto que a janela engoliu.
     O × ignora o conselho (o mesmo gesto do antigo «Ignorar»); o porquê vive no hover do título. */
  .cartao-dica .cd-x{flex:0 0 24px;width:24px;height:24px;margin:-4px 0 -4px 0;padding:0;
              border:0;border-radius:5px;background:none;color:var(--fg);font-size:16px;
              line-height:1;display:inline-flex;align-items:center;justify-content:center;
              cursor:pointer}
  .cartao-dica .cd-x:hover{background:var(--sel-bg);color:var(--fg)}
  .cd-detalhe{margin:0;font-size:11px;font-family:'JetBrains Mono',monospace;
              color:var(--fg)}
  .cartao-dica .cd-pic{display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin:0;
             font-size:10.5px;font-family:'JetBrains Mono',monospace;color:var(--fg)}
  .cartao-dica .cd-pic i{font-style:normal;color:var(--green)}
  .cd-acao{margin-top:auto;display:flex;justify-content:flex-end}
  .cartao-dica .cd-botao{display:flex;align-items:center;justify-content:center;width:auto;
              box-sizing:border-box;min-height:28px;padding:0 12px;text-align:center;
              text-decoration:none;border-color:var(--green);color:var(--green)}
  .cartao-dica .cd-botao:hover{background:rgba(80,250,123,.09)}
  /* a dica que o usuário mandou calar fica no fim, apagada: o achado esmaece, o caminho de volta não */
  .cartao-dica.calada .cd-cab,.cartao-dica.calada .cd-pic,.cartao-dica.calada .cd-detalhe{opacity:.45}
  .nada-a-mudar{display:flex;align-items:center;gap:8px;margin:0;font-size:13px;color:var(--green)}
  .nada-a-mudar i{width:9px;height:9px;border-radius:50%;background:currentColor}

  /* OS CONTROLES QUE O HEFESTO SÓ VÊ — EXTERNOS-01 (06/09/2026, linha 305 do
     CSV da paridade) e a escolha do usuário no mesmo dia: **no mesmo frame dos
     assentos**, como a janela GTK fazia. A EXTERNOS-01 os pôs numa ressalva
     debaixo do acordeão e PERGUNTOU; aqui eles são LINHAS do próprio `.gc`.

     A VAGA É `display:contents` pela mesma razão da aba 01: o piloto precisa de
     UM elemento de pé para reescrever (`data-hef-alvo="html"`), e uma caixa
     de verdade dentro de um `flex-direction:column` viraria UM item — todas as
     linhas empilhadas dentro de uma célula, com a moldura do `.gc` cortando o
     desenho ao meio. O marcador de vazio sai por `display:none`, e não pelo
     `:empty` da `.ressalva`, porque sob `display:contents` um `<i>` vazio ainda
     seria um item de flex e abriria uma linha de altura zero.

     A LINHA NÃO É UM `.gc-item`, e continua não sendo: cada `.gc-item` tem
     `data-controle="pN"`, um rádio de alvo de saída e um corpo que abre. Um
     externo não tem assento, não é alvo de saída de nada e não tem o que abrir
     — pô-lo ali daria à tela um sexto rádio apontando para um aparelho em que o
     daemon não escreve. O que se copia é a CAIXA (o fio de 1px que separa as
     linhas, os 12px de recuo, a coluna do nome), e nunca a classe.

     A ARESTA ESQUERDA É TRACEJADA, e é o segundo sinal depois da marca: os
     `.gc-item` levam ali 3px sólidos, que é onde a `.gc-cor` pinta a cor LIDA
     do plástico. Um externo não tem cor lida — a folha das 28 é dos DualSense —
     e o tracejado é o vocabulário desta casa para *"isto não é um ajuste seu"*
     (`.renomeia`, `.degrau.sem-dono` da aba 01). Nada de `opacity`.

     QUEM O DISTINGUE É A MARCA, como na janela GTK: o assento diz o nome do
     controle, o externo diz *"Controle 4 — Nintendo"*, com a palavra vinda de
     `external_controllers.brand_of`.

     O AVISO DO `hid-nintendo` VAI EM LARANJA, que é a cor que esta casa reserva
     para o que pede atenção — e ele não acusa o Hefesto: a morte é do driver
     do kernel, e a saída estável é o cabo. */
  .gc .ext-vaga{display:contents}
  /* NA GRADE DOS CARTÕES o externo ocupa DUAS das quatro colunas, embaixo: dois por fileira, como
     os assentos, e a altura da seção não cresce uma linha inteira por externo (A-LINHA-DO-EXTERNO-
     VOLTA-AOS-30-PX-01). O que traz o aviso do Nintendo pelo BT é a frase mais longa e atravessa
     as quatro (`data-larga`, posto pelo gerador). */
  .gc .ext-linha{grid-column:span 2;border:1px solid var(--border-sutil);
                 border-left:3px dashed var(--border-forte);border-radius:7px}
  .gc .ext-vaga > .nada{display:none}
  .gc .ext-linha[data-larga]{grid-column:1/-1}
  .gc .ext-linha{display:flex;align-items:center;gap:8px;
                 min-height:28px;padding:0 12px;
                 font-size:12px;color:var(--fg);
                 border-top:1px solid var(--border-sutil);
                 border-left:3px dashed var(--border-forte)}
  .gc .ext-nome{color:var(--fg);font-weight:600;white-space:nowrap;flex:0 0 auto}
  /* O quadrado do modelo tomou 42 px da linha: a 1272 px, com dois por fileira, a coluna das três
     listas vazava 28 px. O «via» é o que cede (reticências, e a frase inteira na dica). */
  .gc .ext-via{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;font-size:11.5px;
               white-space:nowrap}
  .gc .ext-aviso{color:var(--orange);font-size:11.5px;text-align:right}
  .gc .ext-botoes{font-size:11px;letter-spacing:.06em;white-space:nowrap}
  /* O QUADRADO DO MODELO (A-08-MOSTRA-O-DESENHO-DO-CONTROLE-01): o desenho do sprite
     `ext-sprite`, na cor do texto mudo, sem número de modelo na linha (ele vai na dica). O traço
     do desenho não escala com o quadrado (`non-scaling-stroke`): a 34 px, o traço de 2,6 unidades
     de uma arte de 100 viraria um fio de 0,9 px. */
  .gc .ext-desenho{flex:0 0 auto;display:inline-flex;align-items:center;justify-content:center;
                   width:34px;height:22px;color:var(--fg)}
  .gc .ext-desenho svg{width:34px;height:22px;display:block}
  .ext-sprite symbol *{vector-effect:non-scaling-stroke;stroke-width:1.3px}
  /* as três listas do externo têm largura FIXA e moram no fim da linha: de um externo
     para o outro elas caem na mesma coluna, com ou sem o aviso do Nintendo pelo BT. 26 px de
     altura + a borda de 1 px da linha = 28, e 64 px abrigam o texto mais largo de «Chave» e de
     «Botões» (40 px) com o recuo de 8 px de cada lado. */
  .gc .ext-declara{display:flex;align-items:center;gap:6px;flex:none}
  .gc .ext-declara select.pronto{height:26px;line-height:1.2;padding-top:0;padding-bottom:0;
                                 width:64px}
  .gc .ext-declara select.pronto[data-gesto="externo-cor"]{width:132px}
  /* O APARELHO DE UMA EXTENSÃO (22/10/2026, o arranjo C da janela da extensão): a linha do
     externo, com a borda cheia na cor do acessório, o ícone do transporte, a pílula do estado, a
     pilha e o «via» o nome da extensão. As peças são as da coluna «Agora» da janela dela. */
  .gc .ext-acessorio{border-left:3px solid var(--c-acessorio)}
  .gc .ext-acessorio .ic{flex:none}
  .gc .ext-acessorio .c-verde{color:var(--green)}
  .gc .ext-acessorio .c-amarelo{color:var(--yellow)}
  .gc .ext-acessorio .c-laranja{color:var(--orange)}
  .gc .ext-acessorio .c-mudo{color:var(--texto-mudo)}
  .gc .ext-acessorio .c-acessorio{color:var(--c-acessorio)}
  .gc .ext-acessorio .est{display:inline-flex;align-items:center;gap:5px;font-size:11px;
                          white-space:nowrap;flex:none}
  .gc .ext-acessorio .est i{width:8px;height:8px;border-radius:50%;display:inline-block}
  .gc .ext-acessorio .est-verde{color:var(--green)}
  .gc .ext-acessorio .est-verde i{background:var(--green);box-shadow:0 0 6px var(--green)}
  .gc .ext-acessorio .est-amarelo{color:var(--yellow)}
  .gc .ext-acessorio .est-amarelo i{background:var(--yellow)}
  .gc .ext-acessorio .est-laranja{color:var(--orange)}
  .gc .ext-acessorio .est-laranja i{background:var(--orange)}
  .gc .ext-acessorio .est-mudo{color:var(--texto-mudo)}
  .gc .ext-acessorio .est-mudo i{background:var(--border-forte)}
  .gc .ext-acessorio .bat{width:34px;height:10px;border:1px solid var(--texto-mudo);border-radius:2px;
                          padding:1px;flex:none;box-sizing:content-box;display:inline-block}
  .gc .ext-acessorio .bat i{display:block;height:100%;background:var(--green);border-radius:1px}
  .gc .ext-acessorio .ext-via{text-align:right;color:var(--texto-suave)}

  /* ---- botões: todo grupo divide a largura do bloco em partes IGUAIS ----
     A régua dela é estrita: 273/273/273/273 na Jogar, 260 nos 38 da Gatilhos,
     145×4 na Vibração, 173×6 na Perfis. Aqui eram 134/159, 157/71 e 170/192. */
  .miolo .acoes{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:8px;width:100%}
  .miolo .acoes .btn{width:100%;display:flex;align-items:center;justify-content:center;
                     padding:0 10px}

  select.pronto{border-radius:6px;font-size:11.5px;font-family:inherit;padding:0 8px;
    border:1px solid var(--border-forte);background:var(--app-bg);color:var(--texto-suave);
    cursor:pointer}
  select.pronto:hover{border-color:var(--comment)}
  /* o dropdown que ainda espera resposta chama o olho pela borda, não por faixa */
  select.pronto.pergunta{border-color:var(--cyan);color:var(--cyan)}

  /* ================= os cartões da gestão de controles =================
     A-08-O-CHECKUP-ABSORVE-A-GESTAO-01, 25/09/2026 — o desenho de quem
     coordena, depois de ela ver o acordeão com a Gestão dentro do Check-up:
     *«tá quebradíssima a 8»*. A linha que abria e fechava virou UM CARTÃO POR
     LUGAR, os quatro lado a lado — a mesa desta aba é de quatro —, e nada mais
     abre nem fecha: o que era o corpo escondido fica à vista. O rádio `gc-*`
     continua sendo o ALVO de saída (a fita e o cartão marcado), e só isso.
     A gramática é a da aba Sistema que o usuário aprovou: rótulo à esquerda, valor
     à direita, fio de 1px entre as linhas, 25,5px por linha.

     CSS PURO, ZERO JAVASCRIPT, como o acordeão era. E A CLASSE NÃO SE CHAMA
     `peca` NEM `tira` NEM `mesa`: as três já têm dono (o SVG, a fila de abas
     do esqueleto e o `topo.html`). */
  .gc-r{display:none}
  .gc{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
  /* NA JANELA ESTREITA os cartões vão dois a dois: em quatro colunas de 200px o
     nome do controle e o modo eram cortados (a régua da janela estreita, em
     940 px, mediu quatro peças engolidas). */
  @media (max-width:1180px){.gc{grid-template-columns:repeat(2,minmax(0,1fr))}}
  .gc-item{position:relative;display:flex;flex-direction:column;min-width:0;
           padding:3px 12px 8px;border:1px solid var(--border-forte);
           border-radius:9px;background:var(--app-bg);overflow:hidden}
  /* A COR LIDA DO PLÁSTICO é a faixa de 3px no alto do cartão. Ela é a TINTA
     DE UM ELEMENTO, e não uma variável de CSS: o `escrever()` do piloto não
     tem alvo de variável, e o alvo é `cor` e não `fundo` porque o CSSOM
     normaliza o hex na atribuição e o `fundo` acusaria mudança em todo tique
     (medido em 03/09/2026). Sem cor lida o pacote manda vazio, o elemento
     volta a `color:transparent` e a faixa some — campo sem informação não
     mostra nada. */
  .gc-cor{position:absolute;left:0;right:0;top:0;height:3px;display:block;
          color:transparent;background:currentColor}
  /* UMA LINHA SÓ — 26/09/2026, pedido com a janela maximizada: *«colocar
     numero do player e nome do player na mesma linha do nome do modelo e modo
     de conexão»*. O desenho à esquerda, e ao lado o «P N», o nome de quem joga e
     o modelo com o transporte; a linha de 38 px que o número tinha sozinho saiu.
     (noqa-acento: citação literal) No cartão estreito (271 px no tamanho
     do desenho) o modelo DESCE para uma segunda linha dentro dos mesmos 62 px,
     em vez de virar reticências: o `flex-wrap` só quebra quando o dono não teria
     os 70 px dele. */
  .gc-cabeca{display:flex;align-items:center;gap:10px;height:62px;
             border-bottom:1px solid var(--border-sutil)}
  .gc-quem{flex:1;min-width:0;display:flex;flex-wrap:wrap;align-items:center;
           column-gap:6px;row-gap:1px}
  .gc-num{flex:0 0 auto;font-size:13.5px;font-weight:700;color:var(--purple);
          cursor:pointer}
  /* O DONO: em repouso ele é texto; só se veste de campo com o mouse ou o
     foco. Vazio, o `placeholder` diz para que serve. */
  .gc-dono{flex:1 1 70px;min-width:70px;height:26px;padding:0 7px;
           border:1px solid transparent;border-radius:6px;background:transparent;
           color:var(--fg);font:inherit;font-size:12.5px;font-weight:600;
           text-overflow:ellipsis}
  .gc-dono::placeholder{color:var(--fg);font-weight:400}
  .gc-dono:hover{border-color:var(--border-sutil)}
  .gc-dono:focus{border-color:var(--purple);outline:none}
  /* O APARELHO: o desenho e o nome, e é ele o alvo do clique que aponta a fita
     para este controle. O `<label>` ENVOLVE o texto, não o cobre, para a dica
     de dentro continuar sendo a que aparece. */
  .gc-abre{flex:0 0 auto;display:flex;align-items:center;height:62px;
           cursor:pointer;border-radius:7px}
  .gc-cabeca:hover .gc-nome{color:var(--fg)}
  /* A PROPORÇÃO É A DO `viewBox` (116,684 × 80,472); só a largura é escolhida:
     76px dão 52 de altura, e o cartão cabe com o quadro do rádio à vista. */
  .gc-abre .ds-mini{flex:0 0 76px;width:76px;height:auto}
  .gc-nome{flex:0 1 auto;min-width:0;max-width:100%;font-size:12.5px;font-weight:600;color:var(--texto-suave);
           white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  /* OS SELOS, UM POR LINHA. O selo é do produto
     (`a08_conexoes.selo_do_estado`: o rótulo, o valor em `<b>` e o ✓ em
     `<i class="certo">`), e a linha só o arruma: o rótulo à esquerda e o que
     vier depois dele empurrado para a direita. */
  .gc-resumo{display:flex;flex-direction:column;border-top:1px solid var(--border-sutil)}
  .gc-est{display:block;border-bottom:1px solid var(--border-sutil)}
  .gc-est .est{display:flex;align-items:center;gap:6px;height:25.5px;min-width:0;
               font-size:12px;color:var(--fg);white-space:nowrap}
  .gc-est .est > b{margin-left:auto;min-width:0;overflow:hidden;text-overflow:ellipsis;
                   color:var(--fg);font-weight:600}
  .gc-est .est > .certo{margin-left:auto;font-style:normal;font-weight:700;color:var(--texto-suave)}
  .gc-est .est > b + .certo{margin-left:0}
  .gc-est .est.warn > b{color:var(--orange)}
  /* O BOTÃO «A LUZ NÃO ACENDE» SAIU EM 19/10/2026, a pedido, com a espera pelo PS e o
     gesto: o cartão termina no resumo. */
  /* REGRA DE PRODUTO: *"sempre visível mas só
     acionável quando tiver no rádio"* — botão que SOME ensina que a tela é
     instável. */
  .btn.apagado{border-color:var(--border-forte);color:var(--fg);
               opacity:.55;cursor:help}
  .btn.apagado:hover{border-color:var(--border-forte);color:var(--fg)}
  /* o SVG real ganha a barra de luz acesa, PREENCHIDA (um contorno de 1,2 numa
     forma de 2px pinta menos de um pixel). As lâmpadas de jogador saem do
     desenho pequeno por `svg(..., lampadas=False)`, decisão de 28/08. */
  .gc-item [id$="-lightbar"] .peca{fill:var(--luz,var(--border-forte))}
  /* AS FERRAMENTAS DO CHECK-UP — cinco botões de largura IGUAL, a régua dela
     para todo grupo (273×4 na Jogar, 173×6 na Perfis). O mapa das entradas
     ganhou nome: um ícone solto era o único botão da faixa sem palavra. */
  .ferramentas{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;
               margin:10px 0 0}
  .ferramentas .btn{width:100%;height:28px;display:flex;align-items:center;justify-content:center;
                    gap:7px;padding:0 10px;white-space:nowrap}
  .ferramentas .i.ds{width:21px}
  .ferramentas .i{width:14px;height:14px;flex:0 0 auto;fill:none;stroke:currentColor;
                  stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
  /* O FLUXO DO MAPEAR — a moldura da `.tela-nova` com duas colunas: à
     esquerda a entrada da vez (o que foi medido, e o nome e o lugar que ela dá),
     à direita as que já têm nome. A frase do alto diz em que passo o fluxo
     está, e o ponto pulsa enquanto o Hefesto espera o cabo chegar. */
  .mp-cx{width:760px}
  .mp{display:flex;flex-direction:column;gap:14px}
  .mp-diz{margin:0;display:flex;align-items:center;gap:9px;color:var(--fg);
          font-size:13px;font-weight:600}
  .mp-luz{flex:0 0 auto;width:8px;height:8px;border-radius:50%;background:var(--comment)}
  .mp-luz[data-estado="esperando"]{background:var(--cyan);animation:mp-pulso 1.4s ease-in-out infinite}
  .mp-luz[data-estado="porta"]{background:var(--green);box-shadow:0 0 6px var(--green)}
  @keyframes mp-pulso{0%,100%{opacity:1}50%{opacity:.25}}
  @media (prefers-reduced-motion:reduce){.mp-luz[data-estado="esperando"]{animation:none}}
  .mp-duas{display:grid;grid-template-columns:minmax(0,1.5fr) 1px minmax(0,1fr);gap:0 18px}
  .mp-duas::before{content:"";grid-column:2;grid-row:1;background:var(--border-sutil)}
  .mp-esq{grid-column:1;grid-row:1;display:flex;flex-direction:column;gap:8px;min-width:0}
  /* A LISTA ROLA, E A ALTURA É A DA ESQUERDA (29/09/2026,
     O-MAPEAR-LISTA-O-QUE-JA-FOI-MAPEADO-01): com `height:0` a coluna da direita
     não conta na altura da linha da grade, e o `min-height:100%` a estica até a
     esquerda; as 15 entradas dela rolam por dentro em vez de empurrar o diálogo. */
  .mp-dir{grid-column:3;grid-row:1;display:flex;flex-direction:column;gap:8px;min-width:0;
          height:0;min-height:100%}
  .mp-rot{font-size:12px;font-weight:600;color:var(--rot-campo)}
  .mp-porta{border:1px solid var(--border-sutil);border-radius:7px;background:var(--app-bg);
            padding:4px 12px;min-height:42px}
  .mp-porta > .nada{display:none}
  .mp-fatos{display:grid;grid-template-columns:auto minmax(0,1fr);margin:0}
  .mp-fatos dt,.mp-fatos dd{margin:0;height:25.5px;display:flex;align-items:center;font-size:12px;
                            border-bottom:1px solid var(--border-sutil)}
  .mp-fatos dt{color:var(--fg);padding-right:16px}
  .mp-fatos dd{color:var(--fg);font-weight:600;min-width:0;overflow:hidden;
               text-overflow:ellipsis;white-space:nowrap}
  .mp-fatos dt:nth-last-child(2),.mp-fatos dd:last-child{border-bottom:none}
  .mp-campos{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:10px;margin-top:4px}
  .mp-campos label{display:flex;flex-direction:column;gap:5px;min-width:0}
  .mp-campos input,.mp-campos select{width:100%;height:var(--h-escolha,34px);padding:0 9px;
                  border-radius:7px;border:1px solid var(--border-forte);background:var(--app-bg);
                  color:var(--fg);font:inherit;font-size:12.5px}
  .mp-campos input:focus,.mp-campos select:focus{border-color:var(--purple);outline:none}
  .mp-lista{list-style:none;margin:0;padding:0;border-top:1px solid var(--border-sutil);
            flex:1 1 0;min-height:0;overflow-y:auto}
  .mp-lista li{display:flex;align-items:center;gap:8px;height:25.5px;font-size:12px;
               border-bottom:1px solid var(--border-sutil);min-width:0}
  .mp-lista li b{color:var(--fg);font-weight:600;white-space:nowrap}
  .mp-lista li span{margin-left:auto;color:var(--fg);white-space:nowrap;
                    overflow:hidden;text-overflow:ellipsis}
  .mp-lista li.vazio{color:var(--fg)}
  .mp-conta{margin:0;font-size:11.5px;color:var(--fg)}
  .mp-cx .tn-rod .btn.principal{border-color:var(--green);color:var(--green)}
  .mp-cx .tn-rod .btn.principal:hover{background:rgba(80,250,123,.09)}
  .acao{font-size:10.5px;color:var(--cyan);border-bottom:1px dotted var(--cyan);cursor:pointer}

  /* ---- o inventário da mesa: DUAS tabelas, ambas com cabeçalho roxo ---- */
  .tab{width:100%;border-collapse:collapse;font-size:11.5px}
  .tab th{color:var(--rot-campo);font-weight:600;text-align:left;font-weight:600;font-size:10px;
          padding:0 8px 6px 0;
          border-bottom:1px solid var(--border-forte)}
  .tab td{padding:6px 8px 6px 0;color:var(--texto-suave);border-bottom:1px solid var(--border-sutil)}
  .tab tr:last-child td{border-bottom:none}
  .tab .mudo{color:var(--fg)}
  /* CICATRIZ, medida em três tentativas: a `<table>` NÃO estica pela altura da
     caixa. Quem estica a linha de uma tabela é a `height` da CÉLULA, e não um
     `flex` na tabela.
     OS RÁDIOS VIZINHOS: UMA FILEIRA, e não mais uma tabela de duas linhas. A
     tabela custava 108px na coluna que MANDA na altura do quadro; a fileira
     custa 53. `grid-auto-flow:column` e não `repeat(4,…)`: o número de vizinhos
     vem da lista, e uma coluna digitada aqui mentiria no dia em que ela
     crescer — é a mesma forma que `.miolo .acoes` usa para os botões. */
  .vizinhos{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(0,1fr);gap:11px}
  .vizinhos select.pronto{width:100%}
  .viz{display:flex;flex-direction:column;gap:4px;min-width:0}
  .viz .qual{font-size:10.5px;color:var(--fg);white-space:nowrap;overflow:hidden;
             text-overflow:ellipsis}
  /* A COLUNA "ONDE" — 04/09/2026, e ela é a que faltava para a linha do
     Check-up ter endereço na mesa. O exame diz "dois rádios da bancada estão em
     entradas vizinhas" e não diz QUAL; a janela estável põe o aviso ao lado do
     rádio culpado, e é isto.

     ELA NÃO CUSTA LINHA NOVA: o bloco `.viz` é uma coluna de 53px com o nome em
     cima e o `<select>` embaixo, e o "onde" entra como terceira linha de 10,5px
     — a mesma altura do nome. Quando não há aviso ele diz só o painel ("Direita",
     "Entrada 7" quando ela desenhou a mesa), e quando há, o aviso vem colado.

     O AMARELO SÓ ACENDE COM AVISO, e quem decide é o produto: o interruptor é
     um `<i>` invisível irmão, com o alvo `classe` BOOLEANO — o valor que ele
     recebe é a DICA de `_avisos_de_vizinhanca`, e o `ligado()` do piloto só
     pergunta se ela existe. Rádio que ninguém acusou recebe `""`, a classe
     apaga e a linha fica na cor de sempre. Nada aqui adivinha vizinhança.

     POR QUE UM IRMÃO E NÃO A PRÓPRIA LINHA: o vocabulário é UM `data-campo` por
     nó, e a linha já tem o dela (o texto). É o mesmo desenho dos `<i class="est">`
     das cinco linhas do exame, e do `~` que leva a cor do irmão até elas. */
  .viz .vaviso{display:none}
  .viz .onde{font-size:10.5px;color:var(--fg);white-space:nowrap;overflow:hidden;
             text-overflow:ellipsis}
  .viz .vaviso.on ~ .onde{color:var(--orange)}
  /* a sobra de altura das duas colunas do inventário cai ANTES da última fileira,
     nunca entre irmãos — `space-between` só empurra o buraco para o meio */
  .lado-e > .empurra,.lado-d > .empurra{margin-top:auto}

  /* ================= o orçamento do rádio — SAIU EM 23/09/2026 =================
     `.capa`, `.pista`, `.bloco`, `.eixo` e `.leg` eram a régua de turnos por
     adaptador. A seção virou o desenho aprovado (TRANSPLANTE-DA-SECAO-01), a
     régua saiu, e as regras saem junto: CSS de elemento que não existe mais é
     a segunda versão viva de uma decisão (a mesma conta de 28/08, acima).
     ------------------------------------------------------------------ */

  /* OS DOIS BOTÕES DA MESA VIRARAM `<a href="#…">`, e um `<a>` chega sublinhado.
     Medido em 29/08: altura e largura ficaram iguais (34×539, os mesmos do
     `<button>`), e só o sublinhado mudou — o tipo de defeito que régua de caixa
     não vê, porque não move um pixel. O `CSS_POPUP` já carrega o mesmo remédio
     para o rodapé das pop-ups; aqui ele vale para o miolo. No dia em que uma
     segunda aba trocar botão por link, a regra sobe para o `topo.html` — que é
     a mesma conta que mudou o bloco das pop-ups de lugar hoje. */
  a.btn{text-decoration:none}

  /* ================= AS DUAS POP-UPS DA MESA =================
     A anatomia (`.tela-nova` -> `.tn-cx` -> `.tn-topo`/`.tn-corpo`/`.tn-rod`) NÃO
     está aqui: ela mudou-se para `monta.CSS_POPUP` em 29/08, quando esta aba
     virou o segundo consumidor dela. Aqui fica só o que é DESTAS duas telas.
     ---------------------------------------------------------------- */
  /* a rolagem é da `.moldura` (regra do `CSS_POPUP`); o respiro é para a barra
     não pintar por cima da última coluna de quadrados. */
  .tn-cx .moldura{padding-right:6px}
  .mm-rot{font-size:10px;font-weight:600;color:var(--purple);
          }
  .mm-rot-linha{display:flex;align-items:center;gap:8px;height:19px}

  /* ---- a lista de aparelhos.
     NO PRODUTO ELA É A COLUNA DA ESQUERDA e as faces ficam à direita
     (`mapa_da_mesa._Janela.__init__`). Aqui ela é a fileira de CIMA, e a razão é
     aritmética: o quadrado do produto tem 84px de largura e a fileira tem SETE
     colunas fixas — 7×84 + 6 de vão pedem 618px, e a `.tn-cx` oferece 624 por
     dentro. Lado a lado com uma coluna de lista, o quadrado cairia para ~56px e
     as três linhas de texto dele parariam de caber. Empilhado, o 84 do produto
     é exatamente o que sobra. */
  .mm-lista{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin-bottom:12px}
  .mm-ap{height:26px;padding:0 9px;border-radius:6px;background:var(--elevated);
         border:1px solid var(--border-forte);color:var(--texto-suave);
         font:inherit;font-size:11px;cursor:pointer;display:inline-flex;
         align-items:center;gap:4px}
  .mm-ap code{font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--fg)}
  .mm-ap:hover{border-color:var(--comment);color:var(--fg)}
  /* o escolhido é um ToggleButton ATIVO — clicar nele de novo desescolhe. */
  .mm-ap.on{border-color:var(--purple);background:var(--sel-bg);color:var(--fg);font-weight:600}
  .mm-ap.on code{color:var(--purple)}

  /* ---- as faces */
  .mm-face{margin-bottom:12px}
  .mm-face-cab{display:flex;align-items:center;gap:9px;margin-bottom:6px}
  .mm-face-nome{font-size:11.5px;font-weight:600;color:var(--texto-suave)}
  /* o nome é um `Gtk.Label`, NÃO um campo: depois de criada, a face não tem
     como ser renomeada nem apagada pela interface (`mapa_da_mesa._Janela._desenhar_faces`). */
  .tn-cx .mm-face-cab .btn{height:23px;font-size:10px;padding:0 8px}
  /* SETE COLUNAS, para toda face, e o produto escreve a razão: "sete é a fileira
     do hub dela, que é a maior face desta casa" (`_COLUNAS = 7`). O `minmax` deixa
     o quadrado encolher em vez de rolar de lado quando a barra vertical aparece. */
  /* COLUNAS DE VERDADE — 31/08/2026: *"ajusta os alinhamentos e distribuições de
     tudo"*. A grade já era `repeat(7, …)`, mas a filha empilhada dentro da célula
     furava a coluna: medido, 8 x diferentes numa grade de 7, e dois quadrados de
     larguras diferentes (82 e 73). Com a filha fora, toda entrada é uma célula de
     uma coluna, e as duas faces alinham na mesma régua de x. */
  .mm-grade{display:grid;grid-template-columns:repeat(7,minmax(0,84px));
            gap:5px;align-items:start;justify-content:start}
  /* o hub carrega uma legenda embaixo, então a célula dele é mais larga */
  .mm-grade-hubs{grid-template-columns:repeat(3,minmax(0,148px))}
  .mm-hub-nome{font-size:11px;font-weight:600;color:var(--texto-suave);padding-left:2px;
               overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  /* a pergunta curta do «Acrescentar hub» — uma linha, com a altura dos botões da face */
  .hub-pergunta{display:flex;align-items:center;gap:8px;margin:0 0 8px;padding:5px 7px;
                border:1px dashed var(--border-forte);border-radius:7px}
  .hub-rot{display:flex;align-items:center;gap:7px;font-size:11.5px;color:var(--texto-suave)}
  .hub-sel{height:var(--h-acao);min-width:64px;padding:0 7px;border-radius:7px;background:var(--app-bg);
           border:1px solid var(--border-forte);color:var(--fg);font:inherit;font-size:11.5px}
  .hub-nome{flex:1 1 auto;min-width:0;width:auto}
  .hub-pergunta .btn{flex:0 0 auto}
  .mm-ligado{font-size:10px;color:var(--fg);line-height:1.4;padding-left:2px}
  .mm-ligado b{color:var(--texto-suave);font-weight:600}
  .mm-cel{display:flex;flex-direction:column;gap:4px}
  /* 84×56 é `botao.set_size_request(84, 56)`, que em GTK é MÍNIMO e não teto —
     por isso `min-height` aqui, e não `height`: "Aparelho de entrada" quebra em
     duas linhas nos dois. */
  .mm-sq{min-height:56px;width:100%;padding:4px 3px;border-radius:6px;
         background:var(--app-bg);border:1px solid var(--border-forte);
         color:var(--texto-suave);font:inherit;cursor:pointer;
         display:flex;flex-direction:column;align-items:center;justify-content:center;
         gap:1px;text-align:center;line-height:1.15;overflow:hidden}
  .mm-n{font-family:'JetBrains Mono',monospace;font-size:11.5px;font-weight:700;color:var(--fg)}
  .mm-c{font-size:9px;color:var(--texto-suave);word-break:break-word}
  .mm-c.mm-vazia{color:var(--fg);font-style:italic}
  .mm-ext{font-size:8.5px;color:var(--fg)}
  .mm-v{font-size:9px;font-weight:600}
  /* AS CINCO CORES SÃO OS CINCO ESTADOS QUE **ESTA** JANELA PRODUZ. Os três do
     modo ideal (`chega`, `sai`, `fica`) não entram: eles vêm do plano, e esta
     janela não calcula plano nenhum. */
  .mm-sq[data-v="cheia"]{opacity:.72}
  .mm-sq[data-v="cheia"] .mm-v{color:var(--fg)}
  .mm-sq[data-v="serve"]{border-color:var(--comment)}
  .mm-sq[data-v="serve"] .mm-v{color:var(--fg)}
  .mm-sq[data-v="evite"]{border-color:var(--orange)}
  .mm-sq[data-v="evite"] .mm-v{color:var(--orange)}
  .mm-sq[data-v="melhor"]{border-color:var(--green);background:rgba(80,250,123,.07)}
  .mm-sq[data-v="melhor"] .mm-v{color:var(--green)}
  /* a filha por extensão é recuada e tracejada: ela não está na fileira do metal,
     está na ponta de um cabo que só VOCÊ sabe que existe. */
  .mm-sq.mm-filha,.mm-cel .mm-sq + .mm-sq{border-style:dashed;margin-left:9px;width:calc(100% - 9px)}

  /* ---- as duas perguntas da sala, que se mudaram da aba para cá em 28/08.
     NENHUMA `.dica` MORA AQUI DENTRO, e isso é uma correção medida em 29/08.
     A primeira versão pôs um `?` no rótulo da lista, um no rótulo deste bloco e
     um em cada pergunta — quatro no total, os quatro dentro da `.moldura`. A
     régua reprovou: o envelope mediu 860,2×762,5px contra a janela de 757, e
     duas das dicas fechavam em y=810. Os dois modos de errar de uma vez: a
     `.moldura` rola, e um ancestral que rola RECORTA todo descendente absoluto;
     e um `?` a 670px de altura abre uma caixa de 141px que sai da janela pela
     base. É a mesma cicatriz que o `CSS_POPUP` já carrega escrita — "não há uma
     só dica dentro dela". A cura: um `?` por pop-up, no `.tn-topo`, e o resto
     em `title`, que é hover nativo e não tem caixa a recortar. */
  .mm-sala{margin:14px 0 12px}
  /* EMPILHADA, e não lado a lado: a pergunta mais longa tem 46 caracteres e a
     fileira das três opções mede 350px — numa caixa de 624px por dentro, lado a
     lado o enunciado caía para quatro linhas de nove caracteres. */
  /* PERGUNTA E BOTÕES NA MESMA LINHA — medido em 29/08. Empilhados, os dois
     blocos custavam 133px e a confissão nascia FORA da vista (a moldura mostra
     478 de 658). O enunciado mais longo mede ~250px e a fileira das três opções
     350px: 600 numa caixa de 624 por dentro. As perguntas continuam uma ABAIXO
     da outra — o que ficou lado a lado é o enunciado e a sua resposta, que é o
     par que se lê junto. */
  .mm-perg{display:flex;align-items:center;gap:10px;margin-top:9px}
  .mm-perg > .mm-q{flex:1;min-width:0}
  .mm-q{font-size:11.5px;color:var(--texto-suave);display:flex;align-items:center;gap:7px}
  /* o `.seg` do esqueleto dá `flex:1;min-width:150px` a cada opção, para uma
     fileira que ocupa a coluna inteira. Aqui são TRÊS opções de uma a três
     palavras numa caixa de 624px: esticadas, cada botão media 200px de fundo  (noqa-acento: verbo medir, imperfeito)
     para 20 de texto. Elas passam a caber no que dizem. */
  .tn-cx .mm-sala .seg button{flex:0 0 auto;min-width:92px;height:28px;
                              font-size:11px;padding:0 14px}

  /* ---- a confissão. Ela NUNCA é vazia depois da primeira face.
     ELA SAIU DO CORPO E VIROU DICA — decisão, 29/08/2026, e é a
     `D-TUDO-QUE-EXPLICA-VIRA-DICA` aplicada a esta pop-up. O que a comprou:
     a moldura escondia 140px, e o PRIMEIRO deles era a confissão inteira
     (o bloco de lista media 106px). Uma tela que parece completa e não está  (noqa-acento: verbo medir, imperfeito)
     é a classe de defeito que esta casa mais paga.

     O QUE FICA NO CORPO, E POR QUE FICA: uma linha só, sempre à vista, com a
     CONTA. Sumir calada é que era o defeito — a confissão é o que ensina o que
     o Hefesto não sabe. A linha nasce FORA da `.moldura` de propósito: dentro
     dela voltaria a rolar para baixo da dobra, que é justamente o que se está
     consertando.

     E O SINAL **NÃO É UM `?`** — nem podia ser, por duas contas medidas:
       · a regra desta pop-up é "um `?` por pop-up, no `.tn-topo`" (ver o
         comentário do `.mm-sala`: um `?` a 670px abre caixa de 141px que sai
         da janela pela base, e esta linha vive a ~600px);
       · e um `?` mudo não diz NADA antes do hover. A linha diz a conta —
         "três coisas" — de graça, para quem nunca passar o mouse. O rastro
         sobrevive sem interação nenhuma, que é o que a decisão exige.
     O resto é `title`: hover nativo, sem caixa nossa a recortar nem a
     transbordar. O `cursor:help` e o sublinhado pontilhado são o que anuncia
     que há mais ali. */
  .mm-conf-linha{margin:11px 0 0;font-size:11.5px;line-height:1.55;
                 color:var(--fg)}
  .mm-conf-linha b{font-weight:600;color:var(--texto-suave)}
  .mm-conf-linha span{cursor:help;border-bottom:1px dotted var(--border-forte)}
  /* A LINHA SOME QUANDO NÃO HÁ O QUE CONFESSAR — 03/09/2026, e a regra é a da
     janela do desenho: lá `confissao_do_desenho` devolve vazio e nada é
     desenhado. Quem acende esta classe é o produto, pelo `confissao-nada`; no
     arquivo aberto no navegador ela nunca está ligada, porque a cena tem
     lacuna. Sem esta regra, uma mesa sem lacuna leria "…: nada." — texto que
     ocupa a linha para não dizer nada. */
  .mm-conf-linha.sumido{display:none}

  /* ---- os gestos de baixo. `.apagado` deixou de ser só da gestão de controles:
     os dois botões de ação desta pop-up nascem apagados pela mesma regra de produto —
     botão que SOME ensina que a tela é instável. */
  /* OS DOIS GESTOS TÊM O MESMO TAMANHO — 31/08/2026, parte do *"ajusta os
     alinhamentos e distribuições de tudo"*. Eles medem o texto: `Tirar daqui`
     dava 92px e `Tem uma extensão aqui` 170, lado a lado, e dois botões do mesmo
     peso com tamanhos tão diferentes leem como hierarquia que não existe — os
     dois agem sobre a MESMA entrada que você acabou de clicar.
     O grupo de criar face continua empurrado à direita: ele não age sobre a
     entrada selecionada, e a distância é o que diz isso. */
  .mm-acoes{display:flex;align-items:center;gap:8px}
  .mm-acoes > .btn{flex:0 0 auto;min-width:172px;justify-content:center}
  .mm-nova{display:flex;align-items:center;gap:8px;margin-left:auto}
  .mm-campo{height:var(--h-acao);width:118px;padding:0 9px;border-radius:7px;
            background:var(--app-bg);border:1px solid var(--border-forte);
            color:var(--fg);font:inherit;font-size:11.5px}
  .mm-campo::placeholder{color:var(--fg)}
  .tn-rod.mm-rod{justify-content:flex-end}
  .tn-rod.mm-rod .btn{flex:0 0 auto;padding:0 22px}

  /* ================= a cerimônia de um toque por aparelho ================= */
  .ce-cartao{display:flex;flex-direction:column;gap:6px;padding:14px 15px;
             border-radius:8px;background:var(--app-bg);
             border:1px solid var(--border-sutil)}
  .ce-perg{font-size:15px;font-weight:600;color:var(--fg);line-height:1.35}
  /* TEXTO, nunca barra: os DOIS números, sempre (R26). E não há barra de
     progresso porque o total da fase em pé ENCOLHE — ela andaria para trás. */
  .ce-cont{font-family:'JetBrains Mono',monospace;font-size:10.5px;color:var(--purple)}
  .ce-quem{font-size:11.5px;color:var(--texto-suave);line-height:1.55}
  .ce-quem code{font-family:'JetBrains Mono',monospace;font-size:10.5px;color:var(--fg)}
  /* OS LUGARES CABEM NUMA LINHA SÓ — 31/08/2026, e o usuário mandou com a foto na mão:
     *"botões em duas linhas. deveria ser uma."*

     A causa era `flex-wrap:wrap` com botões do tamanho do próprio texto: some a
     largura dos quatro (`Frente do gabinete` é 40% maior que `Em cima da mesa`)
     e, no dia em que a soma passa da caixa, o último cai sozinho para a segunda
     linha. Depende da FONTE que carregou — por isso a foto dela mostrava duas
     linhas e o Chrome headless mostrava uma: com fallback mais estreito, cabia.
     Régua nenhuma pegaria isso; só o olho de quem confere, na máquina do usuário.

     `grid-auto-flow:column` com `grid-auto-columns:1fr` é a gramática que a casa
     já usa em `.miolo .acoes`: os botões dividem a largura em partes iguais,
     nunca quebram, e o alvo de clique é o mesmo para as quatro escolhas — que é
     o que quatro escolhas do mesmo peso pedem. */
  .ce-botoes{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:8px;margin-top:12px}
  .tn-cx .ce-botoes .btn{width:100%;text-decoration:none;justify-content:center;
                         padding:0 6px;min-width:0}
  /* o foco É o anúncio (R13): não há live region alcançável pelo PyGObject, então
     mover o foco é a única forma que a janela tem de dizer "o passo mudou". */
  .btn.foco{outline:2px solid var(--purple);outline-offset:2px}
"""


LARG_NOME = 220
CSS += (f"\n  .gc-cabeca,\n"
        f"  .gc .ext-linha{{--larg-nome:{LARG_NOME}px}}\n")

ESTADOS = ["todos"] + [c["pref"] for c in MESA]

_regras = [
    "  /* o destaque estático da fita perde para o do acordeão: `.fita .chip.on`",
    "     tem especificidade maior que o `.chip.on` do esqueleto, e é ele que",
    "     apaga o chip que nasceu marcado no HTML. */",
    "  .fita .chip.on{background:var(--app-bg);color:var(--fg);font-weight:400;"
    "border-color:var(--border-forte)}",
    "  .fita .chip.plastico.on{border-color:var(--plastico,var(--border-forte))}",
    "  /* O CARTÃO QUE A FITA APONTA ganha a borda roxa da escolha, a mesma do",
    "     chip. Em «Todos» nenhum cartão se destaca: todos são o alvo. */",
]
for estado in ESTADOS:
    marcado = f"body:has(#gc-{estado}:checked)"
    # QUEM ACENDE É A PERGUNTA DA FITA (O-SELECIONAR-ACENDE-QUEM-ESTA-ESCOLHIDO-01): o cartão
    # de um controle acende só o chip dele; o «Todos» acende o «Todos» e os quatro com ele.
    chips = [f'{marcado} .fita .chip[data-pref="{aceso}"]'
             for aceso in sorted(_acesos_da_fita(estado, MESA), key=ESTADOS.index)]
    if estado == "todos":
        chips.append(f'{marcado} .fita:not(:has(.chip[data-pref="todos"])) .chip[data-pref]')
    _regras.append("  " + ",".join(chips) + "{background:var(--sel-bg);"
                   "color:var(--fg);font-weight:600;border-color:var(--purple)}")
    _regras.append("  " + ",".join(f"{c}.plastico" for c in chips)
                   + "{border-color:var(--plastico,var(--border-forte))}")
    if estado == "todos":
        continue
    _regras.append(
        f"  .quadro-corpo:has(#gc-{estado}:checked) .gc-{estado}"
        "{border-color:var(--purple);box-shadow:0 0 0 1px var(--purple)}")
CSS += "\n" + "\n".join(_regras) + "\n"

CSS += """
  .porta{margin-left:auto;font-size:11px;line-height:17px;height:17px;
    color:var(--fg);text-decoration:none;white-space:nowrap}
  .porta:hover{color:var(--cyan);text-decoration:underline}
"""


VER_IGNORADAS = "Ver as ordens ignoradas"

ORDEM_IGNORADA_VOLTA = _pacote08.ORDEM_IGNORADA_VOLTA


MAPEAR_ENTRADAS = "Mapear entradas"
MAPEAR_UMA_A_UMA = "Mapear entrada a entrada"

EXAMINAR_PORTAS = "Examinar entradas"

RENOMEAR_DICA = _pacote08.RENOMEAR_DICA


#: contrato. O `validar-acentuacao.py` isenta a LINHA que traga `noqa-acento`, e
BORDA_LIDA = ("A borda é a cor do plástico que o Hefesto <b>leu do aparelho</b>: este controle "
              "está no cabo, e pelo cabo ele pergunta e o aparelho responde.")
BORDA_NEUTRA = ("A borda é <b>neutra</b> porque a cor deste controle <b>não foi lida</b>. "
                "Uma borda colorida aqui seria uma cor que ninguém leu — e o desenho "
                "continua na cor que o resto do Hefesto já conhece.")

# continua verdadeira) mais `secao_controles.frase_da_capacidade_do_mic()` (o
# `frase_da_capacidade_do_mic` foi escrita para impedir.
MIC_LIGADO_DICA = (
    "Liga o microfone deste controle. Desligado, nenhum programa o ouve — nem o jogo, nem a "
    "chamada. Por onde ele chega quem decide é o USB ou o BT; a linha ao lado diz qual.")
BOTAO_DICA = (
    "O botão físico do microfone faz o mesmo que o desta tela: liga o microfone "
    "<b>e</b> o canal dele. O que ele cala vale para o computador todo, não só "
    "para este controle.")

BOTAO_DICA_CURTA = (
    "O que o botão físico do microfone cala. É um ajuste do computador, um só "
    "para todos os controles.")

#: mirar só este controle (`controller.target.set`).
SO_ESTE_DICA = ("Escolhe só este controle: a luz, os gatilhos e a vibração "
                "passam a mirar nele.")


# `url(#hachura-sem-hex)`, uma hachura; outros dois usam gradiente
# unprefixada, apontaria para `#hachura-sem-hex` enquanto os desenhos definiriam
# `#p1-hachura-sem-hex`: oito modelos ficariam SEM TINTA, e só na máquina de
_CORES_NO_DESENHO = re.compile(
    r'\n?[ \t]*<defs id="[^"]*cores-do-dualsense">.*?</defs>', re.S)

_ABRE_O_DESENHO = '<svg data-colorway="'


def _a_tabela_dos_28() -> str:
    """As 28 cores dela, lidas do desenho — a TABELA, publicada uma vez."""
    achado = _CORES_NO_DESENHO.search(DS)
    if not achado:
        raise SystemExit(
            "ERRO em 08-conexoes: o `<defs id=\"cores-do-dualsense\">` sumiu do "
            "`ds_limpo.svg` — sem ele o desenho não tem como virar outro modelo, "
            "e o alvo de atributo escreveria um colorway que nada casa.")
    return achado.group(0).strip()


TABELA_DAS_CORES = (
    '  <svg width="0" height="0" aria-hidden="true" focusable="false"\n'
    '       style="position:absolute;width:0;height:0;overflow:hidden">\n'
    f'  {_a_tabela_dos_28()}\n'
    '  </svg>')


def desenho_do_controle(c, luz):
    """O desenho pequeno da linha, com ENDEREÇO e sem a folha podada."""
    x = svg(c["pref"], c["cor"], classes="ds-svg ds-mini", luz=luz, lampadas=False)
    if _ABRE_O_DESENHO not in x:
        raise SystemExit(
            f"ERRO em 08-conexoes: o desenho do {c['pref']} não abre com "
            f"`{_ABRE_O_DESENHO}` — sem essa âncora o endereço da cor cairia no "
            "lugar errado, que é pior que não existir.")
    x = x.replace(_ABRE_O_DESENHO,
                  '<svg data-campo="desenho" data-hef-alvo="atributo" '
                  'data-hef-atributo="data-colorway" data-colorway="', 1)
    limpo, quantas = _CORES_NO_DESENHO.subn("", x)
    if quantas != 1:
        raise SystemExit(
            f"ERRO em 08-conexoes: o desenho do {c['pref']} trouxe {quantas} "
            f"tabelas de cor onde devia trazer uma — o `<defs>` das cores mudou "
            f"de forma, e a podada ficaria na página vencendo a dos 28.")
    return limpo


#: `<span data-campo="nome" data-hef-alvo="html">` que no lugar cheio traz o
def nome_do_lugar_vazio(c):
    """O rótulo do lugar sem aparelho: «P3 • Desconectado» (conserto de 14/10/2026, q4B)."""
    return (f'<b>P{c["jogador"]}</b><span class="sep">{_pacote_base.PONTO_DO_ROTULO}</span>'
            f'{_pacote_base.SEM_NINGUEM_AQUI}')


#: 26/09/2026; a bateria foi para o nome (`nome_com_a_bateria`).
ESTADOS_DA_LINHA = ("est-mic", "est-som", "est-modo", "est-visto")
DONO_DICA = ("Escreva o nome de quem joga com este controle. O nome fica no controle: "
             "vale em qualquer entrada e adaptador. Apague para voltar a «P N».")
from types import SimpleNamespace  # noqa: E402

_DECLARACAO_DA_BANCADA = SimpleNamespace(controles={}, orcamento=SimpleNamespace(teto=None))
DICAS_DA_CENA = _dicas_da_cena()


def _estado_da_bancada(c):
    """Os quatro selos da cena, pelo MESMO dono que o produto chama a cada tique."""
    radio = e_radio(c)
    vivo = {"uniq": "", "transport": "bt" if radio else "usb",
            "battery_pct": DA_CONTROLES[c["pref"]]["bat"], "hz_movimento": 480,
            "hz_voz": 1 if radio else None, "speaker": {"volume": 100, "muted": False}}
    return _pacote08.estado_do_controle(vivo, {"mascara": c["mascara"]}, {"native_mode": False},
                                        _DECLARACAO_DA_BANCADA, _MODO_DA_CENA)


#: O «Modo de conexão» da cena: o chip «Sony DualSense», que é o aceso no
def _modo_da_cena():
    from hefesto_dualsense4unix.app.actions.jogar import painel as _painel

    return next(ch.rotulo for ch in _painel.CHIPS_DA_ESCADA if ch.chave == "dualsense")


_MODO_DA_CENA = _modo_da_cena()


def linha_do_controle(c):
    """Um controle do acordeão: a linha fechada e o corpo que ela abre.

    Nada aqui é digitado por controle: a cor da borda sai do desenho, a cor da
    luz sai do produto, o rótulo sai da ordem de produto, a máscara e a bateria saem
    da aba Controles, e o transporte decide o que a linha pode prometer.

    UMA FUNÇÃO SÓ PARA OS QUATRO LUGARES — 07/09/2026, e os dois ramos que
    havia aqui eram o defeito. O lugar VAZIO tinha marcação própria, sem um
    `data-campo` por dentro; `conectado` agora decide DUAS coisas, e só elas:

      a) a classe e o atributo do cartão (`off` + `data-conectado="nao"`);
      b) o TEXTO INICIAL de cada campo — o travessão no lugar do valor.

    A ESTRUTURA É A MESMA NOS QUATRO, e é isso que cura o defeito. Medido em
    07/09/2026 com os quatro DualSense do usuário na mesa: o daemon publicava quatro,
    a carga chegava com `colunas = ['p1','p2','p3','p4']` e os quatro em
    `ocupados`, e a tela mostrava DOIS. O passo 2 do piloto
    (`hefesto_vivo.pintar`) procura `data-campo="k"` DENTRO do bloco
    `[data-controle="pN"]`; sem endereço, o dado dela chega e não tem onde
    pousar. O `data-controle` do lugar vazio nasceu em 03/09 — decisão de produto,
    *"tem que aparecer desligado enquanto não tem nenhum controle; a partir do
    momento que tiver, ele aparece o controle devidamente conectado"* — e essa
    cura ficou pela metade: o endereço do BLOCO chegou, o dos CAMPOS não.

    E DOIS RAMOS QUE DUPLICAM ESTRUTURA ENVELHECEM SEPARADOS. Este par
    envelheceu: entre 03/09 e 06/09 o lugar cheio ganhou `luz-trava`,
    `luz-dica`, `luz-texto`, `luz-espera` e o endereço do desenho — cinco
    endereços novos, nenhum deles no ramo de baixo, e ninguém percebeu porque
    não havia como perceber.

    O QUE `conectado` NÃO DECIDE MAIS: se o cartão ABRE. Isso agora é CSS
    (`.gc-item.off`), e a razão está escrita lá — o piloto escreve valores, não
    marcação, e um cartão que nasce sem `<label>` não ganha um quando o
    controle chega.
    """
    conectado = c.get("conectado", True)

    def vale(cheio, vazio=TRAVESSAO):
        """O texto inicial deste campo: o valor lido, ou o travessão."""
        return cheio if conectado else vazio

    no_radio = e_radio(c)
    luz = "#%02x%02x%02x" % player_slot_color(c["jogador"])
    tinta = ("" if (no_radio or not conectado)
             else f' style="color:{cor_da_zona(c["cor"])}"')
    barra = f'<i class="gc-cor" data-campo="plastico" data-hef-alvo="cor"{tinta}></i>'
    estado = _estado_da_bancada(c) if conectado else {}
    marca = "" if conectado else ' off'
    diz = "" if conectado else ' data-conectado="nao"'
    # `[data-controle][data-conectado="nao"]:not(.vazia){border-color:…}`, e ela

    dica_linha = (f"{SO_ESTE_DICA} A fita do topo passa a apontar para ele."
                  if conectado else "Nenhum controle neste lugar.")
    dica_da_borda = (' title="A borda é a cor lida deste aparelho."'
                     if (conectado and not no_radio) else "")
    return f'''          <div class="gc-item gc-{c["pref"]}{marca}" data-controle="{c["pref"]}"{diz}>
            {barra}
            <div class="gc-cabeca">
              <label class="gc-abre" for="gc-{c["pref"]}" data-gesto="alvo" title="{dica_linha}">
                {desenho_do_controle(c, luz)}
              </label>
              <div class="gc-quem">
                <label class="gc-num" for="gc-{c["pref"]}" data-gesto="alvo" title="{dica_linha}">P{c["jogador"]}</label>
                <input class="gc-dono" type="text" data-gesto="dono-renomear" data-campo="dono" data-hef-alvo="valor"
                       value="" placeholder="Nome de quem joga" maxlength="24" spellcheck="false"
                       aria-label="Nome de quem joga com este controle" title="{DONO_DICA}">
                <span class="gc-nome" data-campo="nome" data-hef-alvo="html"{dica_da_borda}>{vale(_pacote08.nome_com_a_bateria(_pacote08.rotulo_curto_do_controle(c), DA_CONTROLES[c["pref"]]["bat"]), nome_do_lugar_vazio(c))}</span>
              </div>
            </div>
            <div class="gc-resumo">
{chr(10).join(f'              <span class="gc-est" data-campo="{k}" data-hef-alvo="html">{estado.get(k, TRAVESSAO)}</span>' for k in ESTADOS_DA_LINHA)}
            </div>
          </div>'''


POR_NOMEAR = [v for v in RADIOS_VIZINHOS if v[2]]
JA_NOMEADOS = [v for v in RADIOS_VIZINHOS if not v[2]]
JOGADORES_NO_CABO = " e o ".join(f"Player {c['jogador']}" for c in NO_CABO)


def _plural(n, um, muitos):
    return um if n == 1 else muitos


#   – "O que só você sabe" saiu, e ele NÃO paga nada: a coluna media 110px de  # (noqa-acento: verbo medir, imperfeito)

ALTURA = 828
VISIVEL = 542
UTIL = 508
ESCONDE = 286
ESCONDE_ANTES = 332
Q_GESTAO, Q_EXAME, Q_RADIO = 219, 204, 343
Q_GESTAO_ANTES = 265
VISIVEL_3 = 75
VISIVEL_3_ANTES = 29
TETO_DOS_DOIS = 434
DESEMPENHO = 145
INVENTARIO = 130
TODOS = 339
TODOS_ANTES = 409
ESCONDE_TODOS = 406
ESCONDE_TODOS_ANTES = 476
H_ESCOLHA = int(re.search(r"--h-escolha:(\d+)px",
                          (pathlib.Path(__file__).resolve().parent / "topo.html").read_text()).group(1))
ALT_TV = 1080
UTIL_TV = 831


MAPA = _constantes(
    R / "src/hefesto_dualsense4unix/interface/logica_do_mapa.py",
    {"EXPLICACAO", "ROTULO_APARELHOS", "ROTULO_TIRAR", "ROTULO_EXTENSAO",
     "ROTULO_NOVA_ENTRADA", "ROTULO_NOVA_FACE", "ROTULO_FECHAR", "ROTULO_VAZIA",
     "ROTULO_POR_EXTENSAO", "NOME_DA_FACE_EM_BRANCO", "ESPERA_O_APLICAR",
     "GRAVA_NO_CLIQUE", "CONFISSAO_ABERTURA", "CONFISSAO", "_COLUNAS"})

CALIB = _constantes(
    R / "src/hefesto_dualsense4unix/interface/calibracao_das_entradas.py",
    {"FACES", "PERGUNTA_SENTADA", "SEM_SAIR_DA_CADEIRA", "ROTULO_JA_CHEGA",
     "ROTULO_NAO_SEI", "ROTULO_NAO_ALCANCO", "FIM_DA_FASE_SENTADA",
     "CONVITE_EM_PE", "ROTULO_VOU_MOSTRAR", "ROTULO_DEIXAR_PARA_DEPOIS",
     "CONVITE_DO_ENCAIXE", "PROCURANDO", "SEGUNDOS_ATE_O_NO",
     "SEGUNDOS_ATE_A_VIBRACAO"})

SALA = _constantes(
    R / "src/hefesto_dualsense4unix/app/actions/config/secao_mesa.py",
    {"_PERGUNTA_DA_ALTURA", "_DICA_DA_ALTURA", "_PERGUNTA_DA_VISADA",
     "_DICA_DA_VISADA"})


def _confere_no_produto(caminho, frases):
    """Reprova quando uma frase de tela deixa de existir no fonte do produto."""
    fonte = pathlib.Path(caminho).read_text()
    faltam = [f for f in frases if f not in fonte]
    if faltam:
        raise SystemExit(f"ERRO: {pathlib.Path(caminho).name} não diz mais "
                         f"{faltam} — a pop-up copiava essa frase.")


_JULGAR = R / "src/hefesto_dualsense4unix/integrations/arranjo_da_mesa.py"
V_OCUPADA = "Ocupada"
V_SERVE = "Serve"
V_EVITAR = "Vale evitar"
V_MELHOR = "Melhor lugar"
P_TIRAR = "clique para tirar"
P_EXTENSOR = "Com o extensor"
P_SERVE = "entrada direta, mas na altura da escrivaninha"
P_MELHOR = "na ponta do extensor: a antena mais longe das outras"
_confere_no_produto(_JULGAR, [
    f'"{V_OCUPADA}", f"{{tipo}} — {P_TIRAR}"',
    f'"{P_EXTENSOR}"', f'Veredito("serve", "{V_SERVE}", "{P_SERVE}")',
    f'"{V_EVITAR}", colada', f'"{V_MELHOR}"', f'"{P_MELHOR}"',
])

#: O que o título de cada janela de mapear diz ao passar o mouse (o «?» saiu, 13/10/2026).
DICA_DO_MAPEAR = "Clique no aparelho, depois na entrada em que ele está"
DICA_DO_MAPEAR_PORTAS = "Use o mesmo DualSense em todas as entradas"


# todas as letras que o DualSense por cabo é `03/00/00` — classe de entrada sem
CENSO = [
    ("Aparelho de entrada", "1-2", "1",   f'o P{CONECTADOS[0]["jogador"]} {CONECTADOS[0]["nome"]}, no {"BT" if e_radio(CONECTADOS[0]) else "USB"}'),
    ("Mouse",               "1-3", "7",   "o receptor do mouse"),
    ("Aparelho de entrada", "1-5", "2",   f'o P{CONECTADOS[1]["jogador"]} {CONECTADOS[1]["nome"]}, no {"BT" if e_radio(CONECTADOS[1]) else "USB"}'),
    ("Bluetooth",           "3-3", "3",   f'o adaptador “{ADAPTADORES[0]["nome"]}”'
                                          f' — {ADAPTADORES[0]["modelo"]}'),
    ("Teclado",             "3-4", "4",   "o receptor do teclado que o exame desta aba cita"),
    ("Câmera",              "3-5", None,  "a webcam, plugada agora e ainda sem lugar"),
    ("Não identificado",    "4-1", "5",   "o sistema não diz o que é"),
]

ESCOLHIDO = "3-3"

FACES = [
    ("Frente do gabinete", ["1", "2"]),
    ("Traseira", ["3", "4", "5", "6", "7", "8", "9", "10"]),
]

EXTENSAO = {"10": "10a"}

ONDE_ESTA = {no: em for _, no, em, _ in CENSO if em}
QUEM_ESTA = {em: (esp, no) for esp, no, em, _ in CENSO if em}


def _irmas():
    """As entradas de duas em duas, na ordem em que ela desenhou a face."""
    par = {}
    for _, numeros in FACES:
        for i in range(0, len(numeros) - 1, 2):
            par[numeros[i]] = numeros[i + 1]
            par[numeros[i + 1]] = numeros[i]
    return par


PARES = _irmas()


def veredito(n, esticada=False):
    """O que `arranjo_da_mesa.julgar` diz desta entrada, com o Bluetooth na mão."""
    if n in QUEM_ESTA:
        return "cheia", V_OCUPADA, f"{QUEM_ESTA[n][0]} — {P_TIRAR}"
    if n in EXTENSAO:
        return "cheia", V_OCUPADA, P_EXTENSOR
    vizinho = QUEM_ESTA.get(PARES.get(n, ""))
    if vizinho and vizinho[0] in ("Bluetooth", "Teclado", "Mouse"):
        return "evite", V_EVITAR, _motor.frase_da_colada(vizinho[0], na_frase(PARES[n]))
    if esticada:
        return "melhor", V_MELHOR, P_MELHOR
    return "serve", V_SERVE, P_SERVE


#:   · `especie`   — os dois DualSense por cabo saem sem classe no motor.
LACUNAS = ["LACUNA_POSICAO", "LACUNA_VELOCIDADE", "LACUNA_ESPECIE"]


_POR_EXTENSO = _pacote08.PALAVRA_DA_CONTA
if len(LACUNAS) not in _POR_EXTENSO:
    raise SystemExit(f"ERRO: a cena tem {len(LACUNAS)} lacunas e esta tela só "
                     f"sabe dizer {sorted(_POR_EXTENSO)} por extenso.")

#:     GTK — lá a linha não é desenhada quando `confissao_do_desenho` devolve
CONFISSAO_NA_TELA = (
    f'<div class="mm-conf-linha" data-campo="confissao-nada" '
    f'data-hef-alvo="classe" data-hef-classe="sumido" data-hef-quando="sim">'
    f'<span>{_pacote08.ROTULO_DA_CONTA} '
    f'<b data-campo="confissao-conta">{_POR_EXTENSO[len(LACUNAS)]}</b>.'
    f'</span></div>')

from hefesto_dualsense4unix.interface.logica_do_mapa import (  # noqa: E402
    DICA_ENUMERA,
    DICA_EXTENSAO,
    DICA_JA_COLOCADO,
)
from hefesto_dualsense4unix.utils.rotulo_da_entrada import com_artigo, na_frase  # noqa: E402

_MAPA_PY = R / "src/hefesto_dualsense4unix/interface/logica_do_mapa.py"
_confere_no_produto(_MAPA_PY, [
    "Você já colocou este aparelho {onde}.",
    "O sistema enumera este aparelho como {c}.",
    "Foi você quem disse que há uma extensão aqui.",
])


def ap_botao(esp, no, em, quem):
    """Um aparelho da lista — o `Gtk.ToggleButton` de `_desenhar_aparelhos`."""
    # (`mapa_da_mesa._desenhar_aparelhos` só chama `set_tooltip_text` sob `if onde:`).
    dica = DICA_JA_COLOCADO.format(onde=com_artigo(na_frase(em), em=True)) if em else ""
    return (f'<button class="mm-ap{" on" if no == ESCOLHIDO else ""}" '
            f'data-gesto="escolher-aparelho" '
            f'title="{dica} · O objeto: {quem}.">{esp}'
            f'<span class="pt">·</span><code>{no}</code></button>')


def quadrado(n, esticada=False):
    """Uma entrada — o botão de 84×56 px, com as suas até quatro linhas."""
    estado, texto, porque = veredito(n, esticada)
    dentro = QUEM_ESTA.get(n)
    corpo = dentro[0] if dentro else MAPA["ROTULO_VAZIA"]
    dizeres = []
    if esticada:
        dizeres.append(DICA_EXTENSAO)
    elif dentro:
        dizeres.append(DICA_ENUMERA.format(c=dentro[1]))
    dizeres.append(porque)
    linhas = [f'<span class="mm-n">{n}</span>',
              f'<span class="mm-c{"" if dentro else " mm-vazia"}">{corpo}</span>']
    if esticada:
        linhas.append(f'<span class="mm-ext">{MAPA["ROTULO_POR_EXTENSAO"]}</span>')
    linhas.append(f'<span class="mm-v">{texto}</span>')
    return (f'<button class="mm-sq" data-v="{estado}" data-gesto="escolher-entrada" '
            f'title="{" ".join(dizeres)}">'
            + "".join(linhas) + "</button>")


def celula(n):
    """Uma entrada do gabinete, e só ela."""
    return '<div class="mm-cel">' + quadrado(n) + "</div>"


FACE_DA_ENTRADA = {n: nome for nome, numeros in FACES for n in numeros}


#: O DESENHO É DO PRODUTO desde 01/09/2026 — `interface/conexoes.html_do_mapa`.
MAPA_DESENHADO = _aba_conexoes.html_do_mapa(
    [{"nome": nome, "portas": numeros} for nome, numeros in FACES],
    quem_esta=QUEM_ESTA,
    extensoes=EXTENSAO,
    veredito_de=veredito,
    rotulos={"vazia": MAPA["ROTULO_VAZIA"],
             "por_extensao": MAPA["ROTULO_POR_EXTENSAO"],
             "nova_entrada": MAPA["ROTULO_NOVA_ENTRADA"]},
    dicas={"esticada": DICA_EXTENSAO,
           "enumera": DICA_ENUMERA,
           "nova_entrada": _aba_conexoes.DICA_NOVA_ENTRADA},
    #: A pergunta do «Acrescentar hub» nasce ABERTA no desenho: é a face que o usuário escolheu (B-hub).
    pergunta={"aberta": True, "entradas": [n for _nome, ns in FACES for n in ns]})


RESPOSTAS_DA_ALTURA = (("acima", "Sim"), ("abaixo", "Não"), ("", "Não sei"))
RESPOSTAS_DA_VISADA = (("com_gente", "Sim"), ("livre", "Não"), ("", "Não sei"))


def pergunta_da_sala(texto, dica, respostas, marcada, gesto):
    """Uma das duas perguntas que barramento nenhum responde.

    Pergunta, dica e as TRÊS opções são literais de `secao_mesa._declaracoes`.
    `Gtk.ComboBox` está proibido nesta casa (o cosmic-comp fecha o popup no
    clique, cosmic-epoch#2497) — no produto é um `SegmentedSelector`, e aqui é
    o `.seg`, que é o mesmo desenho.

    A DICA É HOVER DO RÓTULO, e não um `?`: no produto ela é
    `texto.set_tooltip_text(...)` sobre o próprio `Gtk.Label` da pergunta
    (`secao_mesa.py`). E tem de ser — ver o comentário do `.mm-sala` no CSS:
    dica dentro da `.moldura` é dica recortada.

    O QUE **NÃO** VEIO ANEXADO: o produto gruda a `moldura.QUANDO_VALE` no fim
    desta dica, porque a seção dele não tem onde mais dizê-la. A frase
    (`GRAVA_NO_CLIQUE`) tem dono em `logica_do_mapa` e não mora mais na tela do
    desenho: o título da janela leva só o hover curto do todo (13/10/2026). **NÃO É `ESPERA_O_APLICAR`**, que este docstring
    nomeava até 06/09/2026: aquela é a irmã dela, a da janela GTK que espera o
    "Aplicar", e esta tela grava no clique desde 01/09.

    O ENDEREÇO DA PINTURA CHEGOU EM 03/09/2026 (`MIGRA-08-01`), e ele cura uma
    tela que MENTIA: o `maquina.json` desta bancada diz
    `linha_de_visada='com_gente'`, e os TRÊS botões da visada estavam apagados —
    a tela dizendo que ninguém respondeu uma pergunta respondida. O "Sim" da
    ALTURA acertava por coincidência do mockup, que é pior: um acerto que não
    vem de leitura erra no primeiro clique do usuário.

    SÃO DOIS ATRIBUTOS COM DOIS VOCABULÁRIOS, e os dois são do produto —
    `data-modo` é o que o GESTO manda (onde `""` vira `None` no
    `machine_declare`), `data-hef-quando` é o que a PINTURA compara (onde `""`
    quer dizer "alvo booleano" e acenderia os três juntos). A razão inteira está
    em `pacotes.a08_conexoes._ID_NAO_SEI`, que é o dono do `"nao_sei"` daqui.
    """
    botoes = "".join(
        f'<button class="{"on" if nome == marcada else ""}" '
        f'data-gesto="{gesto}" data-modo="{ident}" '
        f'data-campo="{gesto}" data-hef-alvo="classe" '
        f'data-hef-quando="{ident or _pacote08._ID_NAO_SEI}">{nome}</button>'
        for ident, nome in respostas)
    return f'''              <div class="mm-perg">
                <span class="mm-q" title="{dica}">{texto}</span>
                <div class="seg">{botoes}</div>
              </div>'''


TELA_MAPEAR = f'''
<div class="tela-nova" id="mapear-entradas">
  <div class="tn-cx">
    <div class="tn-topo">
      <span class="tn-tit" data-dica="{DICA_DO_MAPEAR}">{MAPEAR_ENTRADAS}</span>
      <a class="tn-x" href="#" title="Fechar">×</a>
    </div>
    <div class="tn-corpo">
      <div class="moldura">
        <div class="mm-rot-linha"><span class="mm-rot" title="Tudo o que está ligado ao computador. O que já tem lugar continua na lista: clique nele para mudar de entrada.">{MAPA["ROTULO_APARELHOS"]}</span></div>
        <!-- O ENDEREÇO CHEGOU EM 03/09/2026 (`IDENTIDADE-VEM-DE-CIMA-01`). O
             pacote já trocava esta lista inteira desde 01/09, mas por SELETOR
             CSS, pela chave `blocos` — e um bloco sem `data-campo` é invisível
             para as duas réguas desta casa: os `title` do desenho ("o P1 Cosmic
             Red, no cabo") passavam por congelados sem que nada visse que o
             produto já os reescrevia. Com o endereço, a troca é a MESMA e as
             réguas a enxergam. -->
        <div class="mm-lista" data-campo="aparelhos" data-hef-alvo="html">
{chr(10).join("          " + ap_botao(*a) for a in CENSO)}
        </div>
        <!-- O RECIPIENTE DO MAPA — 01/09/2026. Ele existe para o piloto poder
             TROCAR o miolo inteiro: as faces e as entradas são as que
             o usuário declarou, e o número delas muda. Um bloco cujo número de filhos
             muda com o dado não tem como ser pintado campo a campo — é a mesma
             razão da fita, que se troca inteira desde que a mesa passou a ter
             dois lugares vazios.
             SEM CSS PRÓPRIO de propósito: é um `<div>` de bloco, e as
             `.mm-face` dentro dele empilham como empilhavam. -->
        <div class="mm-faces">
{MAPA_DESENHADO}
        </div>

        <div class="mm-sala">
          <div class="mm-rot-linha"><span class="mm-rot" title="Duas coisas que nenhuma leitura do sistema alcança. Não responder não é o mesmo que “Não sei”: “Não sei” é você dizendo que olhou.">O que só você sabe</span></div>
{pergunta_da_sala(SALA["_PERGUNTA_DA_ALTURA"], SALA["_DICA_DA_ALTURA"],
                  RESPOSTAS_DA_ALTURA, "Sim", "sala-altura")}
{pergunta_da_sala(SALA["_PERGUNTA_DA_VISADA"], SALA["_DICA_DA_VISADA"],
                  RESPOSTAS_DA_VISADA, None, "sala-visada")}
        </div>
      </div>
      {CONFISSAO_NA_TELA}

      <div class="acoes mm-acoes">
        <button class="btn apagado" data-gesto="tirar-daqui" title="Acende quando você clica numa entrada que tem aparelho. Ele escreve “sem aparelho” nessa entrada — a entrada continua no desenho, só fica vazia.">{MAPA["ROTULO_TIRAR"]}</button>
        <button class="btn apagado" data-gesto="nova-extensao" title="Acende quando você clica numa entrada cujo número é só dígito. Cria a filha dela — a 10 vira 10a, depois 10b. Não há neta.">{MAPA["ROTULO_EXTENSAO"]}</button>
        <span class="mm-nova"><input class="mm-campo" placeholder="{MAPA["NOME_DA_FACE_EM_BRANCO"]}" maxlength="16">
          <button class="btn" data-gesto="nova-face" title="Cria uma face com o nome que você escreveu, sem entrada nenhuma. Sem nome, não cria.">{MAPA["ROTULO_NOVA_FACE"]}</button></span>
      </div>
    </div>
    <div class="tn-rod mm-rod">
      <a class="btn" href="#">{MAPA["ROTULO_FECHAR"]}</a>
    </div>
  </div>
</div>
'''


_DESENHO_DO_RADIO = R / "mockup/mapa-do-radio.html"
_DESENHO_DO_RADIO_TXT = _DESENHO_DO_RADIO.read_text(encoding="utf-8")

_CLASSES_RENOMEADAS = {"fatias": "conta-da-vaga", "fatia": "pedaco"}


def _escopo(seletores: str) -> str:
    """`.a, .b:hover` → `.radio .a, .radio .b:hover` — a folha do desenho só vale na seção."""
    fora = []
    for sel in seletores.split(","):
        sel = sel.strip()
        if not sel:
            continue
        if sel in (":root", ".quadro"):
            fora.append(".radio")
        elif sel == "*":
            fora.append(".radio, .radio *")
        elif sel.startswith("#"):
            fora.append(".radio #rd-" + sel[1:])
        else:
            fora.append(".radio " + sel)
    return ", ".join(fora)


def _sem_os_tokens_da_casa(miolo: str) -> str:
    """A raiz do desenho do rádio sem as cores que ele copiou da casa.

    Copiado para `.radio{…}`, um token da casa vira valor PRÓPRIO da seção e esconde o da raiz:
    um tema de cores (O-TEMA-DE-CORES-ENTRA-PELA-FOLHA-DE-USUARIO-01) trocaria o painel da página
    inteira menos o do rádio. O mesmo valor sai daqui e a seção herda; um valor diferente fica,
    porque é do desenho e não uma cópia."""
    casa = {nome: "".join(valor.split()) for nome, valor in _tema.tokens_do_root(TOPO).items()}
    fica = []
    for declaracao in miolo.split(";"):
        nome, _, valor = declaracao.partition(":")
        nome, valor = nome.strip(), " ".join(valor.split())
        if not nome or casa.get(nome) == "".join(valor.split()).lower():
            continue
        fica.append(f"{nome}:{valor}")
    return ";".join(fica)


#: Os dois cinzas de letra da casa (`--comment` e `--texto-mudo`) como cor de TEXTO numa regra:
#: `color:` sem prefixo, logo nem `border-color` nem `background-color`.
_LETRA_CINZA = re.compile(r"(?<![\w-])color:\s*var\(--(?:texto-mudo|comment)\)")


def _letra_sem_cinza(declaracoes: str) -> str:
    """A letra cinza do desenho do rádio vira `--fg` (16/10/2026).

    *«Esse cinza some da interface se tratando de fonte. Não usamos ele»*: as dez abas trocaram os
    dois cinzas de letra por `--fg` nos geradores, mas o desenho aprovado do rádio
    (`mockup/mapa-do-radio.html`) é congelado e entra aqui pela folha dele, com 25 regras de letra
    em `--texto-mudo` e uma em `--comment`. Medido na conferência, com a seção aberta e quatro
    controles: «Dentro da máquina» e «0/2» do adaptador saíam em #9a9eb8. A troca é na entrada da
    folha, e não no arquivo do desenho; a borda e o fundo continuam com os tokens dele."""
    return _LETRA_CINZA.sub("color: var(--fg)", declaracoes)


def _css_do_radio() -> str:
    """A folha do desenho aprovado, com escopo `.radio` e sem o que é da página."""
    corpo = re.search(r"<style>(.*?)</style>", _DESENHO_DO_RADIO_TXT, re.S).group(1)
    corpo = re.sub(r"/\*.*?\*/", "", corpo, flags=re.S)
    for velho, novo in _CLASSES_RENOMEADAS.items():
        corpo = re.sub(rf"\.{velho}\b", f".{novo}", corpo)
    nomes = re.findall(r"@keyframes\s+([\w-]+)", corpo)
    for nome in nomes:
        corpo = re.sub(rf"\b{nome}\b", f"rd-{nome}", corpo)
    saida, i = [], 0
    while True:
        abre = corpo.find("{", i)
        if abre < 0:
            break
        cabeca = corpo[i:abre].strip()
        prof, j = 0, abre
        while j < len(corpo):
            if corpo[j] == "{":
                prof += 1
            elif corpo[j] == "}":
                prof -= 1
                if prof == 0:
                    break
            j += 1
        miolo = corpo[abre + 1:j]
        i = j + 1
        if cabeca.startswith("@keyframes"):
            saida.append(f"{cabeca}{{{miolo}}}")
        elif cabeca.startswith("@media"):
            dentro = []
            for sel, decl in re.findall(r"([^{}]+)\{([^{}]*)\}", miolo):
                dentro.append(f"{_escopo(sel)}{{{_letra_sem_cinza(decl.strip())}}}")
            saida.append(f"{cabeca}{{{''.join(dentro)}}}")
        elif cabeca == "body":
            continue
        elif cabeca == ".quadro":
            saida.append(".quadro.radio{position:relative;z-index:0}")
        elif cabeca == ":root":
            saida.append(f"{_escopo(cabeca)}{{{_sem_os_tokens_da_casa(miolo)}}}")
        else:
            saida.append(f"{_escopo(cabeca)}{{{_letra_sem_cinza(' '.join(miolo.split()))}}}")
    return "\n  ".join(saida)


#: A COR DE CADA TIPO É UM TOKEN DA RAIZ (O-TEMA-DE-CORES-ENTRA-PELA-FOLHA-DE-USUARIO-01): o Python
#: escreve `var(--c-<tipo>)` na régua e `var(--sala-<tipo>)` na sala, e o valor mora só aqui. Na
#: raiz, e não no escopo da seção: um valor posto em `.radio .espectro{…}` venceria o que um tema
#: põe no `:root`, e o tema não chegaria à régua. O controle leva o plástico dele, lido do aparelho;
#: o `--c-controle` é só a cor do desenho de exemplo.
CORES_NA_REGUA = {
    "controle": "#7eb8d4", "wifi": "#d4d7e0", "teclado": "#ffb86c", "mouse": "#f1fa8c",
    "celular": "#f78c6c", "relogio": "#82aaff", "ruido": "#8a8fa8", "fone": "#8be9fd",
    "caixa": "#bd93f9", "outro": "#9a9eb8", _pacote08.TIPO_ACESSORIO: "#ff79c6",
}
#: A cor calma de cada tipo na sala (o ícone e a vaga da ponte), a de antes em `COR_DO_TIPO`.
CORES_NA_SALA = {
    "teclado": "#8b8fa8", "mouse": "#6d7186", "webcam": "#a8a08c", "caixa": "#8c8299",
    "fone": "#7e9aa8", "outro": "#606062", "celular": "#a89a96", "relogio": "#8a9aa8",
    "gamepad": "#7e8fa8",
    _pacote08.TIPO_ACESSORIO: "#a8919f",
}
_RAIZ_DAS_CORES_DOS_TIPOS = ";".join(
    [f"--c-{tipo}:{cor}" for tipo, cor in CORES_NA_REGUA.items()]
    + [f"--sala-{tipo}:{cor}" for tipo, cor in CORES_NA_SALA.items()])


CSS_DA_SECAO_DO_RADIO = _css_do_radio() + """
  .radio .btn{height:auto;padding-top:7px;padding-bottom:7px}
  .radio .btn.so-icone{padding:7px}
  .radio .painel .escolha{height:auto}
  .radio .porta{margin-left:0;line-height:normal;font-size:inherit;text-decoration:none;
                white-space:normal}
  .radio .porta:hover{text-decoration:none}
  .radio .marca{color:inherit}
  .radio .quadro-topo.cab{margin-bottom:0}
  .radio .quadro-topo.cab .conta{margin-left:4px}
  .radio .lugar:not(.aberto) > .aparelhos{display:none}
  .radio .sala-vazia{color:var(--fg);font-size:12.5px;padding:10px 4px}
  .radio .moldes{display:none}
  .radio .btn.apagado{cursor:not-allowed;border-color:var(--border-sutil);color:var(--fg)}
  .radio .historico{display:flex;flex-direction:column;gap:6px}
  .radio .queda-desde{font-size:11px;color:var(--fg);padding:2px 4px}
  .radio .conectar{display:flex;flex-direction:column;gap:11px;min-height:0}
  .radio .soltar.apagado,.radio .lampada.apagado{cursor:not-allowed;opacity:.5}
  .radio .linha{grid-template-columns:36px minmax(13ch,30ch) 1fr 6ch 22px;min-height:0;height:30px;
                padding-top:0;padding-bottom:0}
  .radio .aparelhos{gap:6px;padding-top:6px;padding-bottom:8px}
  .radio .aparelhos .linha > svg{height:20px;width:auto}
  .radio .aparelhos .linha .vaga,.radio .aparelhos .linha .parte{min-height:0;height:22px}
  .radio .linha .features{display:flex;align-items:center;gap:10px}
  .radio .linha .features .ar-selo{flex:none}
  .radio .aparelhos .faixa-do-aparelho:not(:has(.hz)){width:auto !important}
  .radio .aparelhos .faixa-do-aparelho:not(:has(.hz)) .vaga{flex:0 0 auto !important;padding:0 14px}
  /* O som, a vibração e a luz de cada linha só MOSTRAM (`<span data-ligada>`): nenhum ato do produto
     os atende, e o desenho aprovado os pintava por `aria-pressed` de botão. A dica é o que eles dizem. */
  .radio span.vaga,.radio span.selo-zero{cursor:help}
  .radio span.vaga[data-ligada],.radio span.selo-zero[data-ligada]{border-style:solid}
  .radio span.vaga[data-ligada]{background:var(--panel)}
  .radio span.vaga.som[data-ligada]{border-color:var(--c-som);color:var(--c-som)}
  .radio span.vaga.haptica[data-ligada]{border-color:var(--c-haptica);color:var(--c-haptica)}
  .radio span.selo-zero[data-ligada]{border-color:var(--yellow);color:var(--yellow)}
  .radio span.vaga.vaga:not([data-ligada]):not(.fixa):hover{border-color:var(--linha);
                                                          color:var(--fg)}
  .radio .lugar{padding-top:0;padding-bottom:0;min-height:0}
  /* O NOME E O «ONDE FICA?» CABEM NA LINHA (19/10/2026, a foto da aba Conexões): o `min-height`
     de 26 px dos dois vencia a altura compacta e eles encostavam na moldura do adaptador. */
  .radio .lugar-topo{min-height:28px}
  .radio .lugar-nome,.radio .abre-lugar{height:22px;min-height:0;padding-top:0;padding-bottom:0}
  .radio .lugar-topo .ensina{min-height:0;height:20px;padding-top:0;padding-bottom:0}
  .radio .abre-lugar:disabled{opacity:.35;cursor:default}
  #rd-secao > .quadro-topo{padding-top:6px;padding-bottom:6px}
  #rd-secao .quadro-corpo{padding-top:0;padding-bottom:8px}
  #rd-secao .espectro{margin-bottom:6px}
  #rd-secao .espectro-cab{margin-bottom:0;padding-bottom:2px}
  .miolo{padding-bottom:8px;row-gap:8px}
  .radio .linha .quem{display:flex;align-items:center;min-width:0;overflow:hidden;white-space:nowrap}
  .radio .linha .quem .nome{flex:0 1 auto;min-width:4ch}
  .radio .linha .quem-resto{font-size:12.5px;color:var(--texto-suave);flex:none}
  .radio .lugar-topo[draggable="true"]{cursor:grab}
  .radio .lugar.arrastando{opacity:.45}
  /* O «⋮» com o «Esquecer» e o X que só tira o aviso (ESQUECER-E-LIMPAR-AS-CONEXOES-01):
     o mesmo lugar e o mesmo tamanho que o X de antes, e nenhum botão a mais por linha. */
  .radio .linha .xis,.radio .linha .menu-da-linha{width:22px;height:22px;padding:0;
                          display:inline-flex;align-items:center;
                          justify-content:center;border-radius:50%;border:1px solid transparent;
                          background:transparent;color:var(--fg);cursor:pointer;font-size:12px}
  .radio .linha .menu-da-linha{font-size:15px;line-height:1}
  .radio .linha .xis:hover,.radio .linha .menu-da-linha:hover{border-color:var(--orange);
                          color:var(--orange)}
  .radio .linha .xis:focus-visible,.radio .linha .menu-da-linha:focus-visible{
                          outline:2px solid var(--purple);outline-offset:2px}
  .radio .linha .nome-fixo{font-size:12.5px;color:var(--texto-suave);overflow:hidden;
                           text-overflow:ellipsis}
  .radio .linha .features .desligado{color:var(--fg);font-size:11.5px}
  .radio .linha .btn.tentar{height:22px;min-height:0;padding:0 12px;display:inline-flex;align-items:center;
                            font-size:11.5px;border-color:var(--green);color:var(--green)}
  .radio .linha.nao-conectou .features,.radio .linha.desligado .features{display:flex;
                            align-items:center}
  .radio .linha.nao-conectou,.radio .linha.desligado{cursor:default}
  .radio .linha.desligado .ds{opacity:.55}
  .radio .lugar.nao-conectou{border-color:var(--orange)}
  /* O RÓTULO DA PISTA QUE É BOTÃO NASCE COM O FUNDO DO SISTEMA — 26/09/2026, foto
     dela: *«nessa região o svg continua em branco não dá pra entender»*.
     Medido no WebKitGTK da janela: o `<button>` pintava `rgb(192,192,192)` por
     baixo do ícone cinza, e o desenho sumia. O fundo é o da faixa, o traço é
     o do texto, e todo rótulo diz uma palavra ao lado do ícone.
     (noqa-acento: citação literal) */
  .radio button.rotulo{background:transparent;color:var(--texto-suave);line-height:1.3;
                       border:1px solid transparent;border-radius:6px;cursor:pointer;
                       font:inherit;text-align:left}
  .radio button.rotulo:hover{border-color:var(--purple);color:var(--fg)}
  .radio button.rotulo:focus-visible{outline:2px solid var(--purple);outline-offset:1px}
  /* UMA FAIXA POR APARELHO (AS-FAIXAS-DIZEM-QUEM-BRIGA-COM-CADA-APARELHO-01, o desenho 1):
     os mesmos 79 canais em toda linha. Pintado é o canal bom, na cor do aparelho; o buraco é
     o canal perdido, e nele a marca (embaixo) é a cor de quem briga ali, dos dois lados.
     A cor é a IDENTIDADE; a palavra do selo é o que diz se está bom (cor nunca sozinha). */
  .radio .espectro{--vazio:#1b1c24}
  .radio .ar{display:flex;flex-direction:column;gap:7px}
  .radio .ar-grupo{display:flex;align-items:center;gap:8px;font-size:12px;
                   color:var(--fg);margin-top:6px;padding-top:6px;
                   border-top:1px dashed var(--border-sutil)}
  .radio .ar-grupo.outros{color:var(--fg)}
  .radio .ar-grupo:first-child{margin-top:0;padding-top:0;border-top:0}
  .radio .ar-grupo b{font-weight:600;color:var(--cor-do-grupo,var(--fg))}
  .radio .ar-grupo .glifo-do-grupo{color:var(--cor-do-grupo,var(--texto-suave));font-size:14px}
  /* 05/10/2026, o desenho aprovado: ícone · faixa · ponto. O nome e o estado moram no tooltip;
     mais de três aparelhos numa entrada vão em duas colunas, metade de cada lado. */
  .radio .ar-linha{display:grid;align-items:center;column-gap:12px;
                   grid-template-columns:30px minmax(0,1fr) 12px}
  .radio .ar-do{display:flex;flex-direction:column;gap:7px}
  .radio .pistas .fora-do-foco{display:none}
  .radio .ar-duas{display:grid;grid-auto-flow:column;grid-template-columns:1fr 1fr;
                  column-gap:32px;row-gap:7px}
  .radio .ar-linha{transition:opacity .15s;border-radius:6px}
  .radio .ar-linha:focus-visible{outline:2px solid var(--purple);outline-offset:2px}
  .radio .pistas[data-foco] .ar-linha{opacity:.28}
  .radio .pistas[data-foco] .ar-linha.acesa{opacity:1}
  .radio .ar-rot{display:flex;align-items:center;justify-content:center;width:30px;height:22px}
  .radio .ar-rot svg{flex:none;color:var(--cor);width:20px;height:20px}
  /* o desenho do controle é largo: na mesma altura visual dos outros, ele pede mais largura */
  .radio .ar-rot svg.ds{width:28px;height:19px}
  .radio .ar-rot button.rotulo{display:flex;align-items:center;justify-content:center;
                               padding:0;width:30px;height:22px}
  .radio .ar-faixa{display:grid;grid-template-columns:repeat(79,minmax(0,1fr));gap:1px;
                   height:14px;min-width:0}
  .radio .ar-faixa i{display:block;position:relative;background:var(--vazio);
                     border-radius:1px}
  .radio .ar-faixa i.b{background:var(--cor)}
  .radio .ar-faixa u{position:absolute;left:0;right:0;bottom:0;height:4px;
                     background:var(--m);text-decoration:none}
  /* O enlace de baixa energia (a opção 1 do usuário, 09/10/2026): os 40 canais LE, duas
     células cada, com a textura de «não medido» na cor do aparelho; o canal de anúncio leva a
     barra de cima. Nada pintado como bom ou perdido: o mapa do adaptador não é o dele. */
  .radio .ar-faixa i.n{background:repeating-linear-gradient(135deg,var(--cor) 0 1px,
                       var(--vazio) 1px 4px)}
  .radio .ar-faixa i.n.a{box-shadow:inset 0 3px 0 var(--cor)}
  /* a faixa sem leitura é o trilho vazio, igual ao dos outros; só o passo do «Descobrir» fala */
  .radio .ar-faixa.sem{display:flex;align-items:center;font-size:11px;color:var(--fg);
                       background:repeating-linear-gradient(90deg,var(--vazio) 0 9px,transparent 9px 11px)}
  /* 06/10/2026, item 1: a faixa por descobrir é o botão, à vista; o Wi-Fi em 5 GHz diz onde está */
  .radio button.ar-faixa.descobrir{justify-content:center;height:18px;padding:0;cursor:pointer;
                       background:transparent;
                       font:inherit;font-size:11.5px;color:var(--texto-suave);
                       border:1px dashed var(--comment);border-radius:5px}
  .radio button.ar-faixa.descobrir span{background:var(--panel);padding:0 8px;border-radius:4px}
  .radio button.ar-faixa.descobrir:hover,.radio button.ar-faixa.descobrir:focus-visible{
                       border-color:var(--green);color:var(--green);outline:none}
  .radio .ar-faixa.fora{display:flex;align-items:center;font-size:11px;color:var(--fg);
                       background:linear-gradient(var(--vazio),var(--vazio)) center/100% 2px no-repeat}
  .radio .ar-faixa.fora span{background:var(--panel);padding:0 8px 0 0}
  /* 06/10/2026, pergunta 1 (A): quando a seção não cabe, a linha de quem está fora da faixa
     (o Wi-Fi em 5 GHz) sobe para o título do grupo como selo, e a tela não rola por ela */
  .radio .ar-no-titulo{display:none;align-items:center;gap:6px;margin-left:10px;font-size:11px;
                       color:var(--fg)}
  .radio .pistas[data-fora-no-titulo] .ar-no-titulo{display:inline-flex}
  .radio .pistas[data-fora-no-titulo] .ar-linha[data-fora-da-faixa]{display:none}
  .radio .ar-estado{display:flex;align-items:center;justify-content:center;width:12px}
  /* o estado é um ponto: verde = bom, vermelho = problema, vazado = sem leitura */
  .radio .ar-selo{display:inline-block;box-sizing:border-box;width:10px;height:10px;padding:0;
                  border-radius:50%;border:0;background:var(--orange);box-shadow:0 0 0 3px rgba(255,184,108,.2)}
  .radio .ar-selo.sofrendo{background:var(--red);box-shadow:0 0 0 3px rgba(255,85,85,.2)}
  .radio .ar-selo.boa{background:var(--green);box-shadow:none}
  .radio .ar-selo.sem{background:transparent;box-shadow:none;border:2px solid var(--comment)}
  /* o sinal medido de quem não se julga pelo controle: o ponto cheio, na cor do aparelho */
  .radio .ar-selo.sinal{background:var(--cor,var(--texto-suave));box-shadow:none}
  /* o controle conhecido que pede para parear: o ponto verde que pulsa (05/10/2026) */
  .cd-pulso,.radio .ar-pulso{display:inline-block;width:10px;height:10px;border-radius:50%;
             background:var(--green);box-shadow:0 0 0 0 rgba(80,250,123,.55);
             animation:pulso-pede 1.4s infinite}
  .radio .ar-pulso{margin-left:7px;vertical-align:middle}
  @keyframes pulso-pede{70%{box-shadow:0 0 0 8px rgba(80,250,123,0)}
                        100%{box-shadow:0 0 0 0 rgba(80,250,123,0)}}
  @media (prefers-reduced-motion:reduce){.cd-pulso,.radio .ar-pulso{animation:none}}
  .radio .ar-legenda{margin-left:auto;display:flex;gap:6px;flex-wrap:wrap}
  .radio .ar-legenda button{display:flex;align-items:center;gap:5px;font-size:12px;font-family:inherit;
                    background:var(--panel);border:1px solid var(--border-forte);
                    color:var(--texto-suave);border-radius:7px;padding:3px 7px;cursor:pointer}
  .radio .ar-legenda button i{width:10px;height:10px;border-radius:3px;display:inline-block}
  .radio .ar-legenda button[aria-pressed="true"]{border-color:var(--fg);color:var(--fg)}
  .radio .ar-legenda button:focus-visible{outline:2px solid var(--purple);outline-offset:1px}

  /* O «Procurar» é do painel do «Conectar» e de mais nenhum: o do «⋮» tem o nome, uma
     frase e o botão. */
  .radio .painel:not([data-tipo="conectar"]) .cadeado{display:none}
  .radio .painel .explica{margin:0 0 10px;font-size:12.5px;color:var(--texto-suave);
                          line-height:1.4}
  /* A gaveta do «⋮» (cura 4 da O-CONTROLE-NOVO-SE-CONECTA-E-SE-TIRA-PELA-CONEXOES-01): o
     tamanho do que mostra, ao lado da linha, com o estado do aparelho embaixo do nome e os
     botões do mesmo grupo com a mesma largura; o que apaga é vermelho com letra branca. */
  .radio .painel[data-tipo="menu"]{bottom:auto;width:auto;min-width:250px;max-width:340px;
    border:1px solid var(--border-forte);border-radius:9px;box-shadow:0 10px 28px rgba(0,0,0,.5);
    padding:11px 12px 12px;gap:8px;overflow:visible}
  .radio .painel[data-tipo="menu"] .painel-cab h2{color:var(--fg)}
  .radio .painel[data-tipo="menu"] .estado{margin:-4px 0 0;font-size:12.5px;color:var(--texto-suave)}
  .radio .painel[data-tipo="menu"] .explica{margin:0}
  .radio .painel[data-tipo="menu"] .escolha{display:grid;grid-auto-flow:column;
    grid-auto-columns:1fr;gap:7px}
  .radio .painel[data-tipo="menu"] .escolha .btn{justify-content:center}
  .radio .painel .btn.apaga{background:var(--red);border-color:var(--red);color:#fff}
  .radio .painel .btn.apaga:hover{background:#ff6e6e;border-color:#ff6e6e;color:#fff}
  .radio .painel .btn.apaga svg{color:#fff}
  .radio .painel[data-solto]:not([data-tipo="menu"]){border:1px solid var(--linha);border-radius:9px}
  .radio .lugar-nome[class*="cor-"]:not(:focus){border-color:var(--cor-do-grupo)}
  .radio .porta svg[class*="cor-"]{color:var(--cor-do-grupo)}
  .radio .cor-cyan{--cor-do-grupo:var(--cyan)}
  .radio .cor-purple{--cor-do-grupo:var(--purple)}
  .radio .cor-pink{--cor-do-grupo:var(--pink)}
  .radio .cor-yellow{--cor-do-grupo:var(--yellow)}
  .radio .cor-orange{--cor-do-grupo:var(--orange)}
  .radio .cor-comment{--cor-do-grupo:var(--comment)}
  /* A VARREDURA E A BUSCA MORAM SEMPRE NO CABEÇALHO DA CAIXA, e as listas
     `radio-varrendo` e `radio-conectando` as acendem — sem refazer a sala
     (O-CONECTAR-ABRE-INTEIRO-TODA-VEZ-01, cura 2). A borda da busca é a da
     espera do desenho aprovado (`.lugar.esperando`). */
  .radio .marca.varrendo:not(.aceso){display:none}
  .radio .lugar:not(.buscando) .espera.busca{display:none}
  .radio .lugar.buscando{border-color:rgba(80,250,123,.6)}
  /* O chip que a central não aceita agora: apagado, com a dica, e sem tremer. */
  .radio .op[aria-disabled="true"]{cursor:not-allowed;opacity:.5}
  /* O arrasto com um movimento esperando treme a linha, como o botão (R8). */
  .radio .linha.recusa{animation:rd-recusa 420ms var(--ease) 1}
  @media (prefers-reduced-motion: reduce){.radio .linha.recusa{animation:none}}
  /* O «PROCURAR» (O-CONECTAR-E-UM-INTERRUPTOR-01): a pílula do «Modo
     Freestyle» da aba Jogar, com os valores DO USUÁRIO (`aba01.py`, a folha
     `.cadeado`), copiados e presos pela régua do interruptor — sem importar
     de outra aba. No painel, ela fica à direita do título. */
  .radio .cadeado{display:inline-flex;align-items:center;justify-content:center;gap:7px;
           margin-left:auto;height:26px;flex:0 0 auto;white-space:nowrap;
           border-radius:7px;padding:0 12px;font-size:12.5px;font-family:inherit;
           cursor:pointer;
           border:1px solid var(--border-forte);background:var(--app-bg);
           color:var(--fg)}
  .radio .cadeado .p{width:7px;height:7px;border-radius:50%;flex:0 0 auto;
              background:var(--border-forte);box-shadow:none}
  .radio .cadeado.ligada{border-color:var(--green);background:rgba(80,250,123,.09);
                  color:var(--green)}
  .radio .cadeado.ligada .p{background:var(--green);box-shadow:0 0 6px var(--green)}
  /* O DESENHO DO TODO (13/10/2026, mudanças 9 e 10): a Rádio aberta cabe sem rolagem (as
     faixas e os vãos encolhem 2 px, o desenho é o mesmo), e as barras dos adaptadores começam
     e acabam na mesma reta, qualquer que seja o nome ou a conta do adaptador. */
  .radio .ar,.radio .ar-do{gap:5px}
  .radio .ar-duas{row-gap:5px}
  .radio .ar-grupo{margin-top:3px}
  .radio .ar-rot,.radio .ar-rot button.rotulo{height:20px}
  .radio .sala{gap:5px}
  .radio .lugar-topo{display:grid;grid-template-columns:24px auto 116px 26px minmax(110px,1fr) auto;
                     column-gap:8px;align-items:center}
  .radio .lugar-topo > .abre-lugar{grid-column:1}
  .radio .lugar-topo > .lugar-nome{grid-column:2}
  .radio .lugar-topo > .onde{grid-column:3;min-width:0}
  .radio .lugar-topo > .sino{grid-column:4}
  .radio .lugar-topo > .barra-do-lugar{grid-column:5;min-width:0}
  .radio .lugar-topo > .lugar-conta{grid-column:6;margin-left:0;display:grid;
                                    grid-template-columns:auto auto 48px;column-gap:8px;
                                    justify-content:end}
  .radio .lugar-topo > .lugar-conta > .sobra{justify-self:start}
  /* O APARELHO SEM TIPO (desenho do todo, 13/10/2026): o «?» tracejado no lugar do ícone e a grade
     «O que é este aparelho?» com nove ícones grandes. */
  .radio .linha .tipo-qual{width:20px;height:20px;border-radius:50%;border:1px dashed var(--orange);
    color:var(--orange);display:inline-flex;align-items:center;justify-content:center;
    font-size:12px;font-weight:600;text-decoration:none;flex:none}
  .radio .linha .tipo-qual:hover{background:rgba(255,184,108,.12)}
  .tipo-cx{width:min(620px,92vw)}
  .tipo-grade{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
  .tipo-op{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;
    height:104px;border-radius:10px;border:1px solid var(--border-sutil);background:var(--app-bg);
    color:var(--texto-suave);font-family:inherit;font-size:13px;cursor:pointer}
  .tipo-op .i{width:40px;height:40px;display:block;fill:none;stroke:currentColor;
    stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round}
  .tipo-op .i.ds{width:58px;height:40px;color:var(--cyan)}
  .tipo-op:hover{border-color:var(--purple);color:var(--fg)}
  /* O ACIONADOR (desenho r3-08-14, com o ajuste da rodada 3 de 14/10): «Usar como botões de…»
     a 150 x 24 na coluna da ação, e a janela das teclas ao lado do desenho real do controle. */
  .radio .linha .btn.usar-como{text-decoration:none;white-space:nowrap}
  .radio .linha[data-r3="14"] .features{display:grid;grid-template-columns:204px 150px;
    align-items:center;column-gap:0}
  .radio .linha[data-r3="14"] .sem-radio{margin-right:0}
  .radio .linha[data-r3="14"] .btn.usar-como{width:150px;height:24px;min-height:24px;margin-left:0;
    padding:0;box-sizing:border-box;display:inline-flex;align-items:center;justify-content:center;
    font-size:12px}
  .ac-cx{width:min(960px,94vw)}
  .ac-corpo{flex-direction:row !important;gap:22px;align-items:stretch}
  .ac-lista{flex:0 0 300px;display:flex;flex-direction:column;gap:10px}
  .ac-teclas{display:flex;flex-direction:column;gap:10px}
  .ac-dica{font-size:12.5px;color:var(--texto-suave);line-height:1.5;margin-bottom:6px}
  .ac-tecla{display:flex;align-items:center;gap:8px;min-height:40px;padding:0 14px;
    box-sizing:border-box;border:1px solid var(--border-sutil);border-radius:8px;cursor:pointer;
    font-size:13px}
  .ac-tecla input{display:none}
  .ac-tecla.sel,.ac-tecla:has(input:checked){border-color:var(--purple);background:var(--sel-bg)}
  .ac-de{color:var(--fg)}
  .ac-seta{color:var(--texto-mudo)}
  .ac-para{margin-left:auto;color:var(--cyan);font-weight:600}
  .ac-mais{margin-top:auto;height:34px;font-size:12.5px}
  .ac-quem{margin-left:10px;height:28px;padding:0 8px;border-radius:6px;border:1px solid var(--linha);
    background:var(--app-bg);color:var(--fg);font-family:inherit;font-size:12.5px}
  .ac-desenho{flex:1;min-width:0;display:flex;align-items:center;justify-content:center;
    background:var(--app-bg);border-radius:9px;padding:8px}
  .ac-svg{width:100%;height:auto;max-height:52vh}
  #acionador .tn-rod .btn{height:34px}
""" + f"  :root{{{_RAIZ_DAS_CORES_DOS_TIPOS}}}\n"


#: Os tipos que a régua ganhou e o desenho do rádio não tinha: o celular, o relógio e o
#: acessório (o aparelho de baixa energia que não diz o tipo).
SIMBOLOS_DAS_FAIXAS = (
    '  <symbol id="rd-celular" viewBox="0 0 24 24"><rect x="7" y="2" width="10" height="20" '
    'rx="2"/><path d="M11 18h2"/></symbol>\n'
    '  <symbol id="rd-relogio" viewBox="0 0 24 24"><rect x="7" y="7" width="10" height="10" '
    'rx="3"/><path d="M9 7l1-5h4l1 5M9 17l1 5h4l1-5"/></symbol>\n'
    f'  <symbol id="rd-{_pacote08.CATEGORIA_ACESSORIO["glifo"]}" viewBox="0 0 24 24">'
    '<rect x="3" y="8" width="11" height="8" rx="4"/>'
    '<path d="M17.5 9.5a3.5 3.5 0 0 1 0 5M20 7a7 7 0 0 1 0 10"/></symbol>')


def _sprite_do_radio() -> str:
    """O sprite do desenho, com os ids em `rd-` e a silhueta sem os ids de dentro.

    A silhueta do DualSense vem do `ds_limpo.svg` com os ids das peças (`corpo`
    duas vezes, `r1`, `touchpad`…) e os `data-*` do mapa do controle. Numa
    página que já tem desenhos do controle, um `id="corpo"` a mais é um
    `url(#…)` que passa a apontar para o lugar errado — e os `data-entrada`
    fariam as réguas do mapa contarem peças que não são deste controle.
    """
    bloco = re.search(r'(<svg width="0" height="0"[^>]*>)(.*?)(</svg>)\s*\n',
                      _DESENHO_DO_RADIO_TXT, re.S)
    abre, corpo, fecha = bloco.groups()
    corpo = re.sub(r"<!--.*?-->", "", corpo, flags=re.S)

    def limpa_o_ds(m: re.Match) -> str:
        dentro = m.group(2)
        dentro = re.sub(r'\s(?:id|class|data-[\w-]+)="[^"]*"', "", dentro)
        dentro = re.sub(r'\sstyle="[^"]*filter[^"]*"', "", dentro)
        return m.group(1) + dentro + m.group(3)

    corpo = re.sub(r'(<symbol id="i-ds"[^>]*>)(.*?)(</symbol>)', limpa_o_ds, corpo, flags=re.S)
    corpo = re.sub(r'<symbol id="i-', '<symbol id="rd-', corpo)
    corpo = "\n".join(linha for linha in corpo.splitlines() if linha.strip())
    return abre + "\n" + corpo + "\n" + SIMBOLOS_DAS_FAIXAS + "\n" + fecha


def _csv_do_desenho(ident: str) -> list[dict[str, str]]:
    cru = re.search(rf'<script type="text/csv" id="{ident}">(.*?)</script>',
                    _DESENHO_DO_RADIO_TXT, re.S).group(1).strip().splitlines()
    cabeca = cru[0].split(",")
    return [dict(zip(cabeca, (c.strip() for c in linha.split(",")), strict=False))
            for linha in cru[1:] if linha.strip()]


_FACES_DO_DESENHO = ("Frente do gabinete", "Traseira", "Num hub ou extensão", "Na escrivaninha")


#: «caiu 12× em 24 min»: o que o diário do kernel contou na bancada de 04/10 (desenho 5).
QUEDAS_DO_DESENHO_5 = {"n": 12, "min": 24}


#: os controles que o «Usar como botões de» do desenho oferece, pelo plástico (r3-08-14); a chave
#: é da faixa forjada da casa, nunca um endereço de verdade.
QUEM_RECEBE_NO_DESENHO = (("aabbcc0000c1", "Cosmic Red"), ("aabbcc0000c2", "Starlight Blue"),
                          ("aabbcc0000c3", "White"), ("aabbcc0000c4", "Galactic Purple"))
COLORWAY_NO_DESENHO = dict(zip((k for k, _ in QUEM_RECEBE_NO_DESENHO),
                               ("cosmic-red", "starlight-blue", "white", "galactic-purple"),
                               strict=True))


def _desenho_do_acionador() -> str:
    """O DualSense real (`assets/control-svg/dualsense.svg`) dentro da janela do acionador.

    Os `id` ganham o prefixo ``ac-`` (o mesmo desenho vive em outras páginas, e um `id` repetido
    quebra o `url(#…)` dos padrões), o `<svg>` perde o tamanho fixo e ganha `ac-svg`, e cada
    botão que a troca conhece vira o gesto ``acionador-botao``, que leva a forma da janela.
    A tabela e a folha das cores saem: a página tem UMA (`TABELA_DAS_CORES`), e o
    `data-colorway` ganha endereço (`acionador-desenho`) para seguir o controle escolhido.
    """
    cru = (R / "assets" / "control-svg" / "dualsense.svg").read_text(encoding="utf-8")
    cru = cru[cru.index("<svg"):]
    cru, tabelas = _CORES_NO_DESENHO.subn("", cru)
    if tabelas != 1 or "cores-do-dualsense" in cru:
        raise SystemExit(
            f"ERRO em 08-conexoes: o `dualsense.svg` trouxe {tabelas} tabela(s) de cor (com a "
            "folha dentro) onde a janela do acionador espera uma — a segunda ficaria na página "
            "vencendo a dela.")
    cor = _pacote08.campos_do_acionador(CENA_DO_RADIO)["acionador-desenho"]
    cru = re.sub(r'<svg data-colorway="[^"]*"',
                 '<svg data-campo="acionador-desenho" data-hef-alvo="atributo" '
                 f'data-hef-atributo="data-colorway" data-colorway="{cor}"', cru, count=1)
    ids = set(re.findall(r'\sid="([^"]+)"', cru))
    cru = re.sub(r'(\sid=")([^"]+)"', r'\1ac-\2"', cru)
    cru = re.sub(r"url\(#([^)]+)\)",
                 lambda m: f"url(#ac-{m.group(1)})" if m.group(1) in ids else m.group(0), cru)
    cru = re.sub(r'href="#([^"]+)"',
                 lambda m: f'href="#ac-{m.group(1)}"' if m.group(1) in ids else m.group(0), cru)
    cru = re.sub(r"#([A-Za-z_][\w-]*)(?=[\s,{.:>\[)])",
                 lambda m: f"#ac-{m.group(1)}" if m.group(1) in ids else m.group(0), cru)
    cru = re.sub(r'<svg\s', '<svg class="ac-svg" ', cru, count=1)
    cru = re.sub(r'(<svg[^>]*?)\swidth="[^"]*"\sheight="[^"]*"', r"\1", cru, count=1)
    trocam = {peca for peca, _, _ in _pacote08._botoes_do_desenho()}
    return re.sub(
        r'<g ([^>]*)data-entrada="([^"]+)"',
        lambda m: (f'<g {m.group(1)}data-entrada="{m.group(2)}" data-gesto="acionador-botao" '
                   'data-hef-forma="acionador"') if m.group(2) in trocam else m.group(0),
        cru).strip()


def _cena_do_desenho() -> dict:
    """A cena do desenho aprovado, na forma que o pacote pinta.

    OS HZ SÃO A CONTA DO DESENHO, e só do desenho: a bancada não tem daemon, e o
    desenho aprovado mostra números na forma. No produto os Hz vêm do contador
    (`state_full`) e nada é estimado (R10) — o pacote nunca faz esta conta.
    """
    linhas = _csv_do_desenho("dados")
    faces = dict(zip(_FACES_DO_DESENHO, CALIB["FACES"], strict=True))
    hz_por_ponte = _pacote08.MARGINAL_DA_PONTE
    lugares, aparelhos = [], []
    for linha in (x for x in linhas if x["tabela"] == "lugar"):
        lugares.append({
            "id": linha["id"], "lugar": linha["id"], "nome": linha["nome"],
            "entrada": _entrada_a_entrada.rotulo_do_numero(linha["c"]),
            "face": faces.get(linha["d"], ""), "hub": linha["a"] == "hub",
            "varrendo": "varrendo" in linha.get("h", ""), "junto": "", "usb3": False,
            "conectando": False, "chegou": [], "quedas": [], "teto": float(linha["e"]),
        })
    for i, linha in enumerate(x for x in linhas if x["tabela"] == "aparelho"):
        ligado = linha.get("h", "")
        aparelhos.append({
            "id": linha["id"], "tipo": linha["a"], "lugar": linha["c"],
            # O controle da cena não tem nome de quem joga: a tela diz «Player N», como faz
            # com o controle de qualquer pessoa que ainda não deu nome a ele.
            "nome": "" if linha["a"] == "controle" else linha["nome"],
            "rotulo": f"Player {i + 1}" if linha["a"] == "controle" else linha["nome"],
            "cor": linha["b"], "cor_nome": linha["g"],
            "mic": "mic" in ligado, "luz": "luz" in ligado, "fixo": "fixo" in ligado,
            "ponte": ("haptica" if "vib" in ligado else "som" if "ponte" in ligado else None),
            "som": float(linha["d"] or 0), "esperando": False, "alem": False,
        })
    # O acionador do desenho r3-08-14, logo abaixo da webcam: Tecla 1 na Cruz, Tecla 2 no
    # Círculo e o pedal no L2 do Cosmic Red (`pacotes.a08_conexoes`, o bloco dos acionadores).
    webcam = next(i for i, a in enumerate(aparelhos) if a["tipo"] == "webcam")
    aparelhos.insert(webcam + 1, {
        "id": "A1", "chave": "1234:abcd:00000000", "tipo": _pacote08.TIPO_ENTRADA,
        "lugar": aparelhos[webcam]["lugar"], "nome": "Acionador USB", "rotulo": "Acionador USB",
        "controle": QUEM_RECEBE_NO_DESENHO[0][0], "fixo": True, "esperando": False,
        "mic": False, "luz": False, "ponte": None, "som": 0.0, "alem": False,
        "teclas": [(256, "Tecla 1", "cross"), (257, "Tecla 2", "circle"), (258, "Pedal", "l2")]})
    for lug in lugares:
        dentro = [a for a in aparelhos if a["lugar"] == lug["id"]]
        controles = [a for a in dentro if a["tipo"] == "controle"]
        pontes = [a for a in controles if a["ponte"]]
        for k, a in enumerate(pontes):
            a["alem"] = k >= _pacote08.PONTES_POR_ADAPTADOR
        sons = sum(a["som"] for a in dentro if a["tipo"] in ("caixa", "fone"))
        ar = max(0.0, lug["teto"] - hz_por_ponte * len(pontes) - sons)
        parte = ar / 2 / (len(controles) or 1)
        fracao_da_voz = RADIO["HZ_AUDIO_COM_MIC"] / (RADIO["HZ_AUDIO_COM_MIC"]
                                                     + RADIO["HZ_INPUT_COM_MIC"])
        for a in controles:
            voz = min(RADIO["HZ_AUDIO_COM_MIC"], parte * fracao_da_voz) if a["mic"] else 0.0
            a["hz_mov"], a["hz_voz"] = parte - voz, (voz if a["mic"] else None)
    quedas = [q for q in _csv_do_desenho("quedas")]
    for lug in lugares:
        lug["quedas"] = [{"carimbo": 0.0, "quando": q["quando"],
                          "porque": _pacote08.FRASE_DO_DIARIO["ponte subiu"]}
                         for q in quedas if q["lugar"] == lug["id"]]
        if lug["quedas"]:
            lug["quedas_desde"] = "23/09"
    evitados = [{"lugar": x["a"], "ini": int(x["b"]), "fim": int(x["c"])}
                for x in linhas if x["tabela"] == "evitado"]
    tipo_do_desenho = {"teclado": "teclado", "mouse": "mouse", "wifi": "wifi"}
    vizinhos = [{"id": x["id"], "tipo": tipo_do_desenho.get(x["a"], ""), "nome": x["nome"],
                 "sugestao": "", "no": f"/sys/usb/{x['id']}"}
                for x in linhas if x["tabela"] == "espectro"]
    # O que o CSV do desenho não tem: o L1 também evita canais (disjuntos dos outros dois), o
    # Wi-Fi do desenho está em 5 GHz e há outro, interno, em 2,4 GHz.
    evitados.append({"lugar": lugares[0]["id"], "ini": 8, "fim": 16})
    wifi = [{"no": f"/sys/usb/{x['id']}", "mhz": 5805, "largura": 80}
            for x in linhas if x["tabela"] == "espectro" and x["a"] == "wifi"]
    # O mesmo aparelho do desenho 5 na outra banda: 2,4 GHz, em USB 3.0, e as quedas que o diário
    # do kernel contou (a placa que sai do barramento e volta; a «chave» é o vid:pid dela).
    wifi.append({"no": "", "mhz": 2437, "largura": 20, "chave": "usb:2357:012d",
                 "quedas": QUEDAS_DO_DESENHO_5})
    portas = [{"id": x["id"], "caminho": x["a"], "usb": x["b"], "ocupa": x["c"],
               "grupo": re.sub(r"\bmesa\b", "escrivaninha", x["d"]), "rotulo": x["a"]}
              for x in linhas if x["tabela"] == "porta"]
    portas.append({"id": "porta-wifi-2-4", "caminho": "3-1.2", "usb": "3.0",
                   "ocupa": "wifi-usb-2357-012d", "grupo": "", "rotulo": "3-1.2"})
    cheio = max(lugares, key=lambda lg: sum(1 for a in aparelhos
                                            if a["lugar"] == lg["id"] and a["ponte"]))
    vazio = min(lugares, key=lambda lg: (sum(1 for a in aparelhos
                                             if a["lugar"] == lg["id"] and a["ponte"]),
                                         lg["varrendo"]))
    perto = [{"id": x["id"], "adaptador": vazio["id"], "nome": x["nome"], "tipo": x["tipo"],
              "forca": int(x["forca"]), "conhecido": x["conhecido"] == "sim"}
             for x in _csv_do_desenho("perto")]
    quem_sai = [a for a in aparelhos if a["lugar"] == cheio["id"] and a["ponte"]][-1]
    # desenhava um «DualSense · Não Conectou» sem aparelho — a busca que
    # de um controle de verdade, com nome e cor. <!-- noqa-acento: citação literal -->
    aparelhos.append({"id": f"nao-conectou-{cheio['id']}-P5", "aparelho": "P5",
                      "tipo": "controle", "lugar": cheio["id"], "nome": "Lia",
                      "rotulo": "DualSense", "cor": "#7eb8d4", "cor_nome": "Starlight Blue",
                      "nao_conectou": True, "esperando": False, "fixo": True,
                      "pareado_aqui": True})
    # o par que não ficou guardado: a mesma linha oferece «Tentar de Novo», e o desenho mostra as duas
    aparelhos.append({"id": f"nao-conectou-{vazio['id']}-P6", "aparelho": "P6",
                      "tipo": "controle", "lugar": vazio["id"], "nome": "Davi",
                      "rotulo": "DualSense", "cor": "#b5232e", "cor_nome": "Cosmic Red",
                      "nao_conectou": True, "esperando": False, "fixo": True,
                      "pareado_aqui": False})
    aparelhos.append({"id": "D9", "aparelho": "D9", "tipo": "controle", "lugar": cheio["id"],
                      "nome": "", "rotulo": "DualSense", "desligado": True,
                      "esperando": False, "fixo": True})
    cheio["nao_conectou"] = True
    # O aparelho do Bluetooth que nenhuma leitura nomeia, nem o enlace (O-APARELHO-DO-BLUETOOTH-SEM-
    # TIPO-SE-NOMEIA-PELA-PESSOA-01): a linha leva o «?» e a grade «O que é este aparelho?» o nomeia.
    # Ele ocupa a linha que era do celular do desenho 1 (uma linha a mais no adaptador cheio custa
    # a linha do 5 GHz a 809 px); o celular continua na grade, na legenda e na régua. O teclado que
    # o «Descobrir» já mediu (o mouse ainda não): as duas formas de um receptor.
    aparelhos.append({"id": "aa:bb:cc:00:00:e2", "tipo": "outro", "lugar": cheio["id"],
                      "nome": "", "rotulo": "", "pareado": True, "esperando": False,
                      "fixo": False})
    # O aparelho de baixa energia que não diz o tipo (O-ACESSORIO-SEM-TIPO-GANHA-CATEGORIA-E-
    # SINAL-NA-CONEXOES-01): chega «outro», como o BlueZ o dá, e a regra da cena o faz
    # «Acessório» pelo enlace LE; a faixa são os 40 canais «não medido», e o ponto, o sinal.
    # Ele ocupa a linha que era do relógio do desenho 1: uma linha a mais no adaptador cheio
    # (sete aparelhos em duas colunas) custava 29 px, e a seção aberta passava a rolar 13 px na
    # janela maximizada (1918 por 840). O relógio continua na legenda e na régua.
    acessorio = "aa:bb:cc:00:00:e1"
    aparelhos.append({"id": acessorio, "tipo": "outro", "lugar": cheio["id"],
                      "nome": "Acessório", "rotulo": "Acessório", "pareado": True,
                      "esperando": False, "fixo": False})
    enlaces = {cheio["id"]: {_pacote08._so_hex(acessorio): {
        "le": True, "canais_evitados": None, "qualidade_do_enlace": None, "rssi": -61}}}
    _pacote08._com_a_categoria_do_enlace(aparelhos, enlaces)
    for _viz in vizinhos:
        if _viz["tipo"] in ("teclado", "mouse"):
            _viz["receptor"] = True
        if _viz["tipo"] == "teclado":
            _viz["banda"] = [18, 35]
            _viz["saude"] = {"teclas_presas": 3, "buracos": 0, "janela_s": 3600, "lendo": True}
        elif _viz["tipo"] == "mouse":
            _viz["saude"] = {"teclas_presas": 0, "buracos": 0, "janela_s": 3600, "lendo": True}
    cena = {
        "lugares": lugares, "aparelhos": aparelhos, "evitados": evitados,
        "canais_medidos": {lg["id"]: True for lg in lugares}, "enlaces": enlaces,
        "vizinhos": vizinhos, "wifi": wifi, "portas": portas, "pedido": None,
        "proposta": {"controle": quem_sai["id"], "destino": vazio["id"]},
        "ocupado": False, "aberto": None, "perto": perto,
        "destino_do_conectar": vazio["id"],
        "pedindo": [dict(PEDIDO_DO_DESENHO)],
        "quem_recebe": list(QUEM_RECEBE_NO_DESENHO),
        "colorway_de": dict(COLORWAY_NO_DESENHO),
    }
    cena["procurando"] = (_pacote08.PROCURAR_LIGADO
                          if any(lg.get("conectando") for lg in lugares)
                          else _pacote08.PROCURAR_DESLIGADO)
    return cena


CENA_DO_RADIO = _cena_do_desenho()
CAMPOS_DO_RADIO = _pacote08.campos_da_secao(CENA_DO_RADIO)
SALA_DO_DESENHO = _pacote08.html_da_sala(CENA_DO_RADIO, com_hz=True)
#: pintor acende os dois. <!-- noqa-acento: citação literal -->
INTERRUPTOR_PROCURAR = (
    '<button class="cadeado'
    + (" ligada" if CAMPOS_DO_RADIO["radio-procurando"] == _pacote08.PROCURAR_LIGADO else "")
    + '" data-gesto="radio-procurar" data-campo="radio-procurando" data-hef-alvo="classe" '
    f'data-hef-classe="ligada" data-hef-quando="{_pacote08.PROCURAR_LIGADO}" '
    'title="Procura aparelhos no adaptador aberto. Desligue para parar.">'
    '<span class="p"></span>Procurar</button>')
SPRITE_DO_RADIO = _sprite_do_radio()


#: Os desenhos do modelo de cada controle de fora: o arquivo de `assets/control-svg/` e o símbolo
#: que a linha do externo usa (`pacotes.a08_conexoes.simbolo_do_externo` é o dono da escolha). Os
#: quatro são desenho nosso, só traçado: a arte que a casa já trazia (`Nintendo-pro_controller.svg`,
#: `8bitdo-sn30pro.svg`) não tem origem nem licença registradas, e o contrato da sprint só aceita
#: desenho próprio ou de licença compatível com MIT.
ARTE_DOS_EXTERNOS = {"ext-pro": "pro-controller.svg",
                     "ext-xbox": "xbox.svg",
                     "ext-8bitdo": "8bitdo.svg",
                     "ext-generico": "generico.svg"}

#: os atributos de pintura que o `<svg>` do arquivo declara e que o `<symbol>` não herda
_PINTURA = ("fill", "stroke", "stroke-width", "stroke-linejoin", "stroke-linecap")


def _simbolo_do_externo(ident: str, arquivo: str) -> str:
    """Um `<symbol>` em `currentColor`: a pintura do `<svg>` do arquivo desce para um `<g>`."""
    cru = (R / "assets" / "control-svg" / arquivo).read_text(encoding="utf-8")
    raiz = re.search(r"<svg([^>]*)>", cru).group(1)
    caixa = re.search(r'viewBox="([^"]+)"', raiz).group(1)
    dentro = re.search(r"<svg[^>]*>(.*)</svg>", cru, re.S).group(1)
    dentro = "".join(linha.strip() for linha in dentro.splitlines())
    pintura = " ".join(f'{a}="{v}"' for a in _PINTURA
                       for v in re.findall(rf'\s{a}="([^"]*)"', raiz))
    pintura = re.sub(r'="#(?:111|000)(?:000)?"', '="currentColor"', pintura)
    return f'  <symbol id="{ident}" viewBox="{caixa}"><g {pintura}>{dentro}</g></symbol>'


SPRITE_DOS_EXTERNOS = (
    '<svg class="ext-sprite" width="0" height="0" style="position:absolute" aria-hidden="true">\n'
    + "\n".join(_simbolo_do_externo(i, a) for i, a in ARTE_DOS_EXTERNOS.items())
    + "\n</svg>")

ENCAIXE_CURTO = "Encaixe o DualSense numa entrada vazia."

AJUDA_DO_AR = "Cada linha é um aparelho; passe o mouse para ver quem briga"

LEGENDA_DAS_FAIXAS = (
    '<div class="ar-legenda" role="group" aria-label="Acender por tipo">'
    + "".join(
        f'<button type="button" aria-pressed="false" data-tipo-da-legenda="{tipo}">'
        f'<i style="background:var(--c-{tipo})"></i>{rotulo}</button>'
        for tipo, rotulo in _pacote08.LEGENDA_DAS_FAIXAS)
    + "</div>")

SCRIPT_DAS_FAIXAS = r"""
  <script>
  (function(){
    'use strict';
    if(window.__hefFaixas) return;
    window.__hefFaixas = true;
    // O que a pessoa aponta (a linha sob o mouse ou com o foco) e o tipo que o usuário escolheu na
    // legenda. A linha vale mais que o tipo, e a faixa se repinta por dentro a cada tique:
    // por isso o estado mora aqui, e o observador o reaplica depois de cada repintura.
    var linhaAcesa = null, tipoAceso = null;
    function pistas(){ return document.querySelector('.radio .pistas'); }
    function aplicar(){
      var p = pistas(); if(!p) return;
      var linhas = Array.prototype.slice.call(p.querySelectorAll('.ar-linha'));
      var acesas = null;
      if(linhaAcesa){
        var la = linhas.filter(function(l){ return l.getAttribute('data-id') === linhaAcesa; })[0];
        if(la) acesas = [linhaAcesa].concat((la.getAttribute('data-briga') || '').split(' '));
      } else if(tipoAceso){
        acesas = linhas.filter(function(l){
          return l.getAttribute('data-tipo') === tipoAceso ||
            (' ' + (l.getAttribute('data-quem') || '') + ' ').indexOf(' ' + tipoAceso + ' ') >= 0;
        }).map(function(l){ return l.getAttribute('data-id'); });
      }
      linhas.forEach(function(l){
        l.classList.toggle('acesa', !!acesas && acesas.indexOf(l.getAttribute('data-id')) >= 0);
      });
      if(acesas) p.setAttribute('data-foco', '1'); else p.removeAttribute('data-foco');
    }
    function daLinha(ev){
      return ev.target && ev.target.closest ? ev.target.closest('.radio .ar-linha') : null;
    }
    function apontar(ev){
      var l = daLinha(ev);
      linhaAcesa = l ? l.getAttribute('data-id') : null;
      aplicar();
    }
    document.addEventListener('mouseover', apontar);
    document.addEventListener('focusin', apontar);
    document.addEventListener('mouseout', function(ev){
      if(daLinha(ev) && !(ev.relatedTarget && ev.relatedTarget.closest &&
                           ev.relatedTarget.closest('.radio .ar-linha'))){ apontar({target: null}); }
    });
    document.addEventListener('focusout', function(ev){
      if(daLinha(ev)) apontar({target: null});
    });
    document.addEventListener('click', function(ev){
      var b = ev.target && ev.target.closest ? ev.target.closest('.radio .ar-legenda button') : null;
      if(!b) return;
      var tipo = b.getAttribute('data-tipo-da-legenda');
      tipoAceso = tipoAceso === tipo ? null : tipo;
      Array.prototype.forEach.call(document.querySelectorAll('.radio .ar-legenda button'), function(x){
        x.setAttribute('aria-pressed', x.getAttribute('data-tipo-da-legenda') === tipoAceso ? 'true' : 'false');
      });
      aplicar();
    });
    var p0 = pistas();
    if(p0 && window.MutationObserver) new MutationObserver(aplicar).observe(p0, {childList: true});
  })();
  </script>
"""

SCRIPT_DA_SECAO_DO_RADIO = r"""
  <script>
  (function(){
    'use strict';
    if(window.__hefRadio) return;
    window.__hefRadio = true;
    function um(sel, raiz){ return (raiz || document).querySelector(sel); }
    function todos(sel, raiz){ return Array.prototype.slice.call((raiz || document).querySelectorAll(sel)); }
    function perto(ev, sel){ return ev.target && ev.target.closest ? ev.target.closest(sel) : null; }
    function aspas(v){ return String(v).replace(/["\\]/g, '\\$&'); }
    function comPiloto(){ return !!(window.__hef && window.__hef.ouvindo); }
    function abrirASecao(){ var r = document.getElementById('cx8-3'); if(r && !r.checked) r.checked = true; }
    function balancar(b){ b.classList.remove('recusa'); void b.offsetWidth; b.classList.add('recusa');
      setTimeout(function(){ b.classList.remove('recusa'); }, 500); }

    // ---- o acordeão: abrir um adaptador fecha os outros (o Python lembra) ----
    // Com UMA caixa só ela fica aberta (decisão, 25/09): o pacote nem
    // pinta a seta, e esta guarda cobre a página de antes do próximo tique.
    document.addEventListener('click', function(ev){
      var b = perto(ev, '.radio .abre-lugar');
      if(!b) return;
      if(todos('.radio .sala .lugar').length < 2) return;
      var card = b.closest('.lugar'), abrindo = !card.classList.contains('aberto');
      todos('.radio .lugar').forEach(function(l){
        l.classList.remove('aberto');
        var a = um('.abre-lugar', l); if(a) a.setAttribute('aria-expanded', 'false');
      });
      if(abrindo){ card.classList.add('aberto'); b.setAttribute('aria-expanded', 'true'); }
      focar();
    });
    // ---- a caixa aberta põe a faixa em foco nela: só os aparelhos do usuário, sem o título ----
    // (desenho aprovado de 05/10/2026). Com uma caixa só, ela vive aberta e nada se esconde.
    function focar(){
      var p = um('.radio .pistas'); if(!p) return;
      var aberta = todos('.radio .sala .lugar').length > 1 ? um('.radio .sala .lugar.aberto') : null;
      var id = aberta ? aberta.getAttribute('data-id') : '';
      todos('.ar > .ar-grupo, .ar > .ar-do', p).forEach(function(e){
        // o grupo da caixa aberta só fica quando pulsa: o controle que pede para parear ali
        var dele = (e.classList.contains('ar-do') && e.getAttribute('data-do') === id)
          || (e.getAttribute('data-grupo') === id && !!e.querySelector('.ar-pulso'));
        e.classList.toggle('fora-do-foco', !!id && !dele);
      });
    }
    (function(){
      var p = um('.radio .pistas'), sala = um('.radio .sala');
      if(window.MutationObserver){
        if(p) new MutationObserver(focar).observe(p, {childList: true});
        if(sala) new MutationObserver(focar).observe(sala, {childList: true});
      }
      focar();
    })();
    // ---- a largura do nome segue o texto ----
    document.addEventListener('input', function(ev){
      var n = perto(ev, '.radio .lugar-nome');
      if(n) n.style.width = Math.max((n.value || n.placeholder).length + 2, 10) + 'ch';
      var c = perto(ev, '.radio .quem .nome');
      if(c) c.style.width = Math.max((c.value || c.placeholder).length + 2, 6) + 'ch';
    });

    // ---- a PERGUNTA, antes de todo mover (R7) ----
    var antesDaPergunta = null;
    function moldeDe(alvo, destino){
      return um('.radio template.pergunta-molde:not([data-pedido]):not([data-esquecer])[data-alvo="'
                + aspas(alvo) + '"][data-destino="' + aspas(destino) + '"]');
    }
    // A PERGUNTA DO X (26/09/2026): o endereço é a linha E o adaptador — o mesmo
    // controle desligado mora em cada adaptador em que tem chave.
    function moldeDoX(alvo, lugar){
      return um('.radio template.pergunta-molde[data-esquecer][data-alvo="' + aspas(alvo)
                + '"][data-destino="' + aspas(lugar) + '"]');
    }
    function perguntar(m){
      if(!m) return false;
      abrirASecao();
      var caixa = document.getElementById('rd-pergunta');
      antesDaPergunta = document.activeElement;
      um('.diz', caixa).innerHTML = m.innerHTML;
      var sim = document.getElementById('rd-pergunta-sim');
      var outro = document.getElementById('rd-pergunta-outro');
      sim.textContent = m.dataset.sim || ''; sim.hidden = !m.dataset.sim;
      sim.dataset.alvo = m.dataset.alvo || ''; sim.dataset.destino = m.dataset.destino || '';
      // O «SIM» É O GESTO DO MOLDE: «Mover» por padrão, «Esquecer» no X.
      sim.dataset.gesto = m.dataset.gesto || 'confirmar-mudanca';
      outro.textContent = m.dataset.outro || ''; outro.hidden = !m.dataset.outro;
      outro.dataset.alvo = m.dataset.alvo || '';
      todos('.radio .lugar.alvo').forEach(function(l){ l.classList.remove('alvo'); });
      if(m.dataset.destino){
        var c = um('.radio .lugar[data-id="' + aspas(m.dataset.destino) + '"]');
        if(c) c.classList.add('alvo');
      }
      caixa.hidden = false;
      document.getElementById('rd-veu-pergunta').classList.add('aberto');
      (sim.hidden ? outro : sim).focus();
      return true;
    }
    function fecharAPergunta(){
      var caixa = document.getElementById('rd-pergunta');
      if(caixa.hidden) return;
      caixa.hidden = true;
      document.getElementById('rd-veu-pergunta').classList.remove('aberto');
      todos('.radio .lugar.alvo').forEach(function(l){ l.classList.remove('alvo'); });
      if(antesDaPergunta && document.contains(antesDaPergunta)) antesDaPergunta.focus();
    }
    document.addEventListener('click', function(ev){
      if(perto(ev, '#rd-pergunta .btn') || perto(ev, '#rd-veu-pergunta')) fecharAPergunta();
    });

    // ---- o PAINEL lateral: o que a página abre, o Python já pintou ----
    // O PAINEL SEGUE O MOLDE ENQUANTO ESTÁ ABERTO (25/09/2026, a lista dela,
    // passo b6: *«não apareceu na lista»*). Ele era uma CÓPIA tirada no clique:
    // o tique repintava o molde com o aparelho que a busca achou, e o
    // «Procurando» aberto continuava mostrando a lista do instante do clique.
    var quemAbriu = null, painelAberto = null;
    function moldeDoPainel(tipo, alvo){
      return um('.radio template.painel-molde[data-painel="' + tipo + '"][data-alvo="'
                + aspas(alvo || '') + '"]');
    }
    function encherOPainel(m){
      document.getElementById('rd-painel-titulo').textContent = m.dataset.titulo || '';
      document.getElementById('rd-pulso').style.display = m.dataset.pulso ? '' : 'none';
      var corpo = document.getElementById('rd-painel-corpo');
      corpo.innerHTML = ''; corpo.appendChild(m.content.cloneNode(true));
      return corpo;
    }
    function marcaDoMolde(m){
      return (m.dataset.titulo || '') + '\u0000' + (m.dataset.pulso || '') + '\u0000' + m.innerHTML;
    }
    function abrirPainel(tipo, alvo){
      var m = moldeDoPainel(tipo, alvo);
      if(!m) return false;
      abrirASecao();
      quemAbriu = document.activeElement;
      var p = document.getElementById('rd-painel');
      var corpo = encherOPainel(m);
      painelAberto = {tipo: tipo, alvo: alvo || '', marca: marcaDoMolde(m)};
      p.setAttribute('data-tipo', tipo);
      p.classList.add('aberto'); p.removeAttribute('inert'); p.setAttribute('aria-hidden', 'false');
      aGavetaNaLinha(p);
      oPainelDeixaOsMenus(p);
      aSecaoCabeOPainel();
      var primeiro = um('button, a, input', corpo) || document.getElementById('rd-fechar');
      if(primeiro) primeiro.focus();
      return true;
    }
    // O PAINEL ABERTO SE REMENDA, NÃO SE REFAZ (O-CONECTAR-ABRE-INTEIRO-TODA-VEZ-01,
    // cura 1). Ele se esvaziava e se enchia de novo a cada molde novo — e o
    // molde do «Conectar» muda a cada leitura do BlueZ (3 s), porque o sinal
    // de quem está perto mora nele: todo botão do painel era destruído e
    // recriado, o que estava debaixo do ponteiro dela também. Agora os nós
    // casam pela chave (a tag e o `data-alvo`): a linha que fica é o MESMO nó,
    // e só o que mudou nela muda (o número do sinal, o `aria-pressed` e a dica
    // do chip); a que chegou entra no lugar dela, e a que saiu sai. O título e
    // o pulso são do molde também, e mudam no lugar.
    function chaveDoNo(n){
      if(n.nodeType !== 1) return '#' + n.nodeType;
      var alvo = n.getAttribute('data-alvo');
      return n.tagName + (alvo === null ? '' : '|' + alvo);
    }
    function remendarOsAtributos(vivo, novo){
      Array.prototype.slice.call(vivo.attributes).forEach(function(a){
        if(!novo.hasAttribute(a.name)) vivo.removeAttribute(a.name);
      });
      Array.prototype.slice.call(novo.attributes).forEach(function(a){
        if(vivo.getAttribute(a.name) !== a.value) vivo.setAttribute(a.name, a.value);
      });
    }
    function remendar(vivo, novo){
      var livres = {};
      Array.prototype.slice.call(vivo.childNodes).forEach(function(n){
        var k = chaveDoNo(n); (livres[k] = livres[k] || []).push(n);
      });
      var antes = null;
      Array.prototype.slice.call(novo.childNodes).forEach(function(m){
        var lista = livres[chaveDoNo(m)], n = lista && lista.length ? lista.shift() : null;
        if(!n) n = document.importNode(m, true);
        else if(n.nodeType === 1){ remendarOsAtributos(n, m); remendar(n, m); }
        else if(n.nodeValue !== m.nodeValue) n.nodeValue = m.nodeValue;
        var lugar = antes ? antes.nextSibling : vivo.firstChild;
        if(lugar !== n) vivo.insertBefore(n, lugar);
        antes = n;
      });
      Object.keys(livres).forEach(function(k){
        livres[k].forEach(function(n){ if(n.parentNode === vivo) vivo.removeChild(n); });
      });
    }
    function seguirOPainel(){
      if(!painelAberto) return;
      var m = moldeDoPainel(painelAberto.tipo, painelAberto.alvo);
      if(!m){ fecharPainel(); return; }
      var marca = marcaDoMolde(m);
      if(marca === painelAberto.marca) return;
      var titulo = document.getElementById('rd-painel-titulo');
      if(titulo.textContent !== (m.dataset.titulo || '')) titulo.textContent = m.dataset.titulo || '';
      var pulso = document.getElementById('rd-pulso'), mostra = m.dataset.pulso ? '' : 'none';
      if(pulso.style.display !== mostra) pulso.style.display = mostra;
      remendar(document.getElementById('rd-painel-corpo'), m.content);
      painelAberto.marca = marca;
    }
    function fecharPainel(){
      var p = document.getElementById('rd-painel');
      painelAberto = null;
      if(!p.classList.contains('aberto')) return;
      if(p.contains(document.activeElement)) document.activeElement.blur();
      p.classList.remove('aberto'); p.setAttribute('inert', ''); p.setAttribute('aria-hidden', 'true');
      aSecaoCabeOPainel();
      if(quemAbriu && document.contains(quemAbriu)) quemAbriu.focus();
      quemAbriu = null;
    }
    // A SEÇÃO CABE O PAINEL (06/10/2026, item 2). O painel é absoluto e seguia a altura da seção:
    // com as entradas fechadas ela tinha 169 px e o «Conectar» pedia 488, que rolavam por dentro,
    // com o miolo vazio embaixo. Aberto, ele estica a seção até caber, no máximo até o fim do
    // miolo (a página nunca rola); fechado, a seção volta à altura dela. A conta é refeita quando
    // a lista do painel ou a seção mudam de tamanho (a procura acha aparelhos a cada leitura).
    // A GAVETA DO «⋮» MORA AO LADO DA LINHA (O-CONTROLE-NOVO-SE-CONECTA-E-SE-TIRA-PELA-CONEXOES-01,
    // cura 4). Ela era o painel da seção inteira, com o nome e um botão num retângulo vazio que
    // cobria a coluna dos «⋮» das outras linhas. Agora tem o tamanho do que mostra e abre à
    // esquerda do «⋮» que a abriu, na altura da linha: a coluna dos «⋮» fica livre.
    function aGavetaNaLinha(p){
      p.style.top = ''; p.style.right = '';
      if(p.getAttribute('data-tipo') !== 'menu' || !p.offsetParent) return;
      var alvo = (painelAberto && painelAberto.alvo || '').split('|');
      var b = um('.radio .linha .menu-da-linha[data-alvo="' + aspas(alvo[0]) + '"][data-lugar="'
                 + aspas(alvo[1] || '') + '"]');
      var r = b && b.getBoundingClientRect();
      if(!r || !r.width) return;
      var base = p.offsetParent.getBoundingClientRect();
      var topo = Math.round(r.top - base.top - 6);
      topo = Math.max(0, Math.min(topo, Math.round(base.height - p.offsetHeight - 4)));
      p.style.top = topo + 'px';
      p.style.right = Math.round(base.right - r.left + 6) + 'px';
    }
    // O PAINEL NÃO COBRE A COLUNA DOS «⋮» (a mesma cura 3): o «Conectar» aberto ocupava a borda
    // direita da seção, por cima do «⋮» de toda linha, e o clique nele caía no painel. Aberto, o
    // painel para à esquerda da coluna, e o «⋮» de qualquer linha continua ao alcance.
    function oPainelDeixaOsMenus(p){
      if(!p) return;
      p.removeAttribute('data-solto');
      if(!p.classList.contains('aberto') || p.getAttribute('data-tipo') === 'menu'
         || !p.offsetParent) return;
      p.style.right = '';
      var esquerda = Infinity;
      todos('.radio .lugar.aberto .linha .menu-da-linha').forEach(function(m){
        var q = m.getBoundingClientRect();
        if(q.width) esquerda = Math.min(esquerda, q.left);
      });
      if(esquerda === Infinity) return;
      var base = p.offsetParent.getBoundingClientRect();
      p.style.right = Math.max(0, Math.round(base.right - esquerda + 6)) + 'px';
      p.setAttribute('data-solto', '');
    }
    function aSecaoCabeOPainel(){
      var s = document.getElementById('rd-secao'), p = document.getElementById('rd-painel');
      if(!s || !p) return;
      s.style.minHeight = '';
      if(!p.classList.contains('aberto') || p.getAttribute('data-tipo') === 'menu') return;
      var cs = getComputedStyle(p), vao = parseFloat(cs.rowGap) || 0, precisa = 0, n = 0;
      Array.prototype.forEach.call(p.children, function(c){
        if(c.offsetParent === null && getComputedStyle(c).position !== 'fixed') return;
        precisa += c.scrollHeight; n += 1;
      });
      precisa += vao * Math.max(0, n - 1) + parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom)
                 + parseFloat(cs.borderTopWidth) + parseFloat(cs.borderBottomWidth) + 2;
      var miolo = s.closest('.miolo'), teto = Infinity;
      if(miolo) teto = miolo.getBoundingClientRect().bottom
                       - parseFloat(getComputedStyle(miolo).paddingBottom) - s.getBoundingClientRect().top;
      var alvo = Math.floor(Math.min(precisa, teto));
      if(alvo > s.offsetHeight) s.style.minHeight = alvo + 'px';
    }
    // O QUE ESTÁ FORA DA FAIXA CABE (06/10/2026, pergunta 1, opção A). A linha do Wi-Fi em 5 GHz
    // custa 29 px; quando com ela a seção não cabe no miolo, ela vira o selo do título «Outros
    // dispositivos sem fio». A conta tira o selo, mede e o devolve no mesmo quadro (sem piscar).
    function oQueEstaForaDaFaixaCabe(){
      var pistas = um('.radio .pistas'), miolo = pistas && pistas.closest('.miolo');
      if(!miolo) return;
      pistas.removeAttribute('data-fora-no-titulo');
      var precisa = !!um('.ar-linha[data-fora-da-faixa]', pistas) && miolo.scrollHeight > miolo.clientHeight;
      if(precisa) pistas.setAttribute('data-fora-no-titulo', '');
    }
    window.addEventListener('resize', aSecaoCabeOPainel);
    window.addEventListener('resize', function(){
      oPainelDeixaOsMenus(document.getElementById('rd-painel'));
    });
    window.addEventListener('resize', oQueEstaForaDaFaixaCabe);
    document.addEventListener('change', function(ev){
      if(ev.target && ev.target.name === 'cx8-secao') oQueEstaForaDaFaixaCabe();
    });
    // o tique repinta as linhas por dentro da faixa: a linha de fora pode chegar ou sair (a rede
    // trocou de banda), e a conta se refaz
    var pistasDoAr = um('.radio .pistas');
    if(pistasDoAr && window.MutationObserver){
      new MutationObserver(oQueEstaForaDaFaixaCabe).observe(pistasDoAr, {childList: true});
    }
    if(window.ResizeObserver){
      var olhoDoMiolo = new ResizeObserver(function(){ oQueEstaForaDaFaixaCabe(); });
      todos('.miolo > *').forEach(function(q){ olhoDoMiolo.observe(q); });
      var olhoDoPainel = new ResizeObserver(function(){
        oPainelDeixaOsMenus(document.getElementById('rd-painel')); aSecaoCabeOPainel();
      });
      var corpoDoPainel = document.getElementById('rd-painel-corpo');
      if(corpoDoPainel) olhoDoPainel.observe(corpoDoPainel);
      var corpoDaSecao = document.querySelector('#rd-secao > .quadro-corpo');
      if(corpoDaSecao) olhoDoPainel.observe(corpoDaSecao);
    }
    document.addEventListener('keydown', function(ev){
      if(ev.key === 'Escape'){ fecharAPergunta(); fecharPainel(); }
    });
    // O «CONECTAR» NÃO PRENDE A SEÇÃO (O-CONTROLE-NOVO-SE-CONECTA-E-SE-TIRA-PELA-CONEXOES-01,
    // cura 3). Um véu cobria a seção com o painel aberto, e todo clique nela só fechava o painel:
    // outra linha, outro adaptador, nada respondia. Sem o véu, as linhas respondem como sempre (o
    // «⋮» de outra linha troca a gaveta), e com a busca acesa o clique na caixa de outro adaptador
    // é a escolha do chip: o alvo muda para ela. O clique em nada fecha o painel, como o véu.
    function aCaixaEscolhe(ev){
      var caixa = perto(ev, '.radio .sala .lugar');
      if(!caixa || perto(ev, '.linha, button, input, a, [data-gesto], .balao')) return false;
      var aberto = painelAberto && painelAberto.tipo === 'conectar';
      if(!aberto && !um('.radio .sala .lugar.buscando')) return false;
      var lid = caixa.dataset.id, m = moldeDoPainel('conectar', '');
      var op = m && um('.op[data-alvo="' + aspas(lid) + '"]', m.content);
      if(!op || op.getAttribute('aria-disabled') === 'true'){ balancar(caixa); return true; }
      var chip = aberto && um('#rd-painel .op[data-alvo="' + aspas(lid) + '"]');
      if(chip){ chip.click(); return true; }
      var b = document.getElementById('rd-escolher');
      if(b && comPiloto()){ b.setAttribute('data-alvo', lid); b.click(); }
      return true;
    }
    document.addEventListener('click', function(ev){
      if(perto(ev, '#rd-fechar')){ fecharPainel(); return; }
      if(aCaixaEscolhe(ev)) return;
      var foraDoPainel = !!painelAberto && !perto(ev, '#rd-painel');
      if(foraDoPainel && !perto(ev, '.radio button, .radio input, .radio a, .radio [data-gesto]')){
        fecharPainel(); return;
      }
      // escolher dentro do painel: quem vem / para onde → a pergunta
      var ir = perto(ev, '#rd-painel [data-aparelho][data-destino]');
      if(ir){ fecharPainel(); perguntar(moldeDe(ir.dataset.aparelho, ir.dataset.destino)); return; }
      // O CHIP ACESO É O DO RÁDIO (A-CAIXA-FICA-ONDE-ELA-ABRIU-01): com o
      // piloto, o chip pede ao Python — e, com a busca de pé, à central — e o
      // painel segue o molde quando a resposta chega. Aceso no clique, o chip
      // recusado ficava aceso sobre a busca que continuava noutro adaptador.
      var chip = perto(ev, '#rd-painel .op');
      if(chip){
        // O chip apagado diz que agora não pela dica, e não treme nem acende.
        if(chip.getAttribute('aria-disabled') === 'true' || comPiloto()) return;
        todos('.op', chip.parentNode).forEach(function(o){ o.setAttribute('aria-pressed', 'false'); });
        chip.setAttribute('aria-pressed', 'true'); return;
      }
      // O «ESQUECER» DO MENU DA LINHA abre a pergunta de sempre — o par
      // (linha, adaptador), como o X abria até a ESQUECER-E-LIMPAR-AS-CONEXOES-01.
      var esquecer = perto(ev, '#rd-painel .escolha [data-gesto="esquecer-aparelho"]');
      if(esquecer){
        var mx = moldeDoX(esquecer.dataset.alvo, esquecer.dataset.lugar);
        fecharPainel();
        if(mx) perguntar(mx);
        return;
      }
      if(perto(ev, '#rd-painel .escolha [data-gesto]') || perto(ev, '#rd-painel .achado .btn')){
        fecharPainel(); return;
      }
      var b;
      if((b = perto(ev, '.radio .sino'))){ abrirPainel('sino', b.dataset.alvo); return; }
      if((b = perto(ev, '.radio .soltar'))){
        if(b.classList.contains('apagado')) balancar(b); else abrirPainel('quem-vem', b.dataset.alvo);
        return;
      }
      if((b = perto(ev, '.radio .rotulo.vizinho'))){ abrirPainel('o-que-e', b.dataset.alvo); return; }
      // O «⋮» DA LINHA (ESQUECER-E-LIMPAR-AS-CONEXOES-01): o menu dela, com o
      // «Esquecer». O molde existe sempre e o menu abre com o que se sabe; só o
      // «Esquecer» de verdade espera o rádio desocupar, e diz por quê.
      if((b = perto(ev, '.radio .linha .menu-da-linha'))){
        abrirPainel('menu', b.dataset.alvo + '|' + b.dataset.lugar);
        return;
      }
      // O X do «Não Conectou» tira o aviso, e não esquece nada: com o piloto,
      // quem tira é a central (a linha some no tique); no desenho, a página.
      if((b = perto(ev, '.radio .linha .xis'))){
        if(!comPiloto()){ var aviso = b.closest('.linha'); if(aviso) aviso.remove(); }
        return;
      }
      // «Tentar de Novo» é o «Conectar» daquele adaptador: o mesmo painel abre.
      // Quem não é controle tenta o mesmo mover, e não tem painel (`data-abre`).
      if((b = perto(ev, '.radio .linha .tentar'))){
        if(b.dataset.abre) abrirPainel(b.dataset.abre, '');
        return;
      }
      // O «+ CONECTAR» SÓ ABRE O PAINEL (O-CONECTAR-E-UM-INTERRUPTOR-01): quem
      // liga a busca é o «Procurar», e ligá-lo abre o painel também; fechar o
      // painel não o desliga. A cópia de dentro do painel não reabre nada.
      if((b = perto(ev, '#rd-b-conectar'))){ abrirPainel('conectar', ''); return; }
      if((b = perto(ev, '.radio .cadeado[data-gesto="radio-procurar"]'))){
        if(!b.classList.contains('ligada') && !b.closest('#rd-painel')) abrirPainel('conectar', '');
        return;
      }
      if((b = perto(ev, '#rd-b-equilibrar'))){
        var s = um('.radio template.balao-molde');
        if(b.classList.contains('apagado') || !s || !perguntar(moldeDe(s.dataset.controle, s.dataset.destino)))
          balancar(b);
        return;
      }
      // a lâmpada: o balão da sugestão, dentro do cartão
      if((b = perto(ev, '.radio .lampada'))){
        var card = b.closest('.lugar'), velho = um('.balao', card);
        if(velho){ velho.remove(); return; }
        var t = um('.radio template.balao-molde[data-destino="' + aspas(b.dataset.alvo) + '"]');
        if(!t || b.classList.contains('apagado')){ balancar(b); return; }
        card.appendChild(t.content.cloneNode(true));
        var ok = um('.balao .ok', card); if(ok) ok.focus();
        return;
      }
      if((b = perto(ev, '.radio .balao .ok'))){
        var bal = b.closest('.balao');
        perguntar(moldeDe(b.dataset.alvo, bal.dataset.destino));
        bal.remove(); return;
      }
    });
    // AS DICAS (AS-DICAS-SAO-CARTOES-COM-UM-GESTO-01): o botão de mover abre a MESMA pergunta de
    // todo mover (o molde é o do balão da lâmpada). O porquê vive no hover do título.
    // A GRADE «O QUE É ESTE APARELHO?» (O-APARELHO-DO-BLUETOOTH-SEM-TIPO-SE-NOMEIA-PELA-PESSOA-01):
    // a janela é uma só, o «?» da linha entrega o endereço dele aos ícones, e o ícone escolhido
    // grava o tipo para quem a abriu e fecha a janela.
    document.addEventListener('click', function(ev){
      var q = perto(ev, '.radio .linha .tipo-qual');
      if(q) todos('#tipo-do-aparelho .tipo-op').forEach(function(b){ b.dataset.alvo = q.dataset.alvo || ''; });
      if(perto(ev, '#tipo-do-aparelho .tipo-op')) location.hash = '';
    });
    document.addEventListener('click', function(ev){
      var mover = perto(ev, '.dicas .cd-botao[data-destino]');
      if(mover) perguntar(moldeDe(mover.dataset.alvo, mover.dataset.destino));
    });
    // o teclado: Enter numa linha abre «Para onde vai» — arrastar não é o único caminho
    document.addEventListener('keydown', function(ev){
      if(ev.key !== 'Enter' && ev.key !== ' ') return;
      var l = ev.target && ev.target.matches && ev.target.matches('.radio .linha[tabindex]') ? ev.target : null;
      if(!l) return;
      ev.preventDefault();
      if(ocupado()){ balancar(l); return; }
      abrirPainel('para-onde', l.dataset.id);
    });

    // ---- ARRASTAR AS CAIXAS: a ordem é de produto, e fica gravada ----
    // Decisão, 25/09/2026: ela segura a linha de cima de um adaptador e
    // arrasta para mudar a ordem (a frase de produto está no `adaptador_reordenar` do
    // pacote). A caixa anda na página enquanto ela arrasta; ao soltar, a ordem
    // nova (os `data-id`, de cima para baixo) vai ao Python pelo
    // `#rd-reordenar` — o botão escondido que o ouvinte do piloto escuta, como
    // o `#rd-comecar` da cerimônia. O tipo do arrasto é PRÓPRIO: a linha de um
    // aparelho, que também se arrasta, não se confunde com a caixa.
    var caixa = null, idDaCaixa = '', ordemAntes = '';
    function ordemDasCaixas(){
      return todos('.radio .sala .lugar').map(function(l){ return l.dataset.id; }).join(' ');
    }
    function aCaixa(){
      if(caixa && !document.contains(caixa))
        caixa = um('.radio .sala .lugar[data-id="' + aspas(idDaCaixa) + '"]');
      return caixa;
    }
    document.addEventListener('dragstart', function(ev){
      var topo = perto(ev, '.radio .lugar-topo[draggable="true"]');
      if(!topo || perto(ev, '.radio .linha') || !ev.dataTransfer) return;
      if(perto(ev, '.radio .lugar-nome')){ ev.preventDefault(); return; }
      caixa = topo.closest('.lugar'); idDaCaixa = caixa.dataset.id; ordemAntes = ordemDasCaixas();
      ev.dataTransfer.setData('application/x-hef-caixa', idDaCaixa);
      ev.dataTransfer.effectAllowed = 'move';
      caixa.classList.add('arrastando');
    });
    document.addEventListener('dragover', function(ev){
      if(!caixa) return;
      var c = perto(ev, '.radio .sala .lugar'), eu = aCaixa();
      if(!c || !eu) return;
      ev.preventDefault();
      if(ev.dataTransfer) ev.dataTransfer.dropEffect = 'move';
      if(c === eu || c.parentNode !== eu.parentNode) return;
      var r = c.getBoundingClientRect();
      c.parentNode.insertBefore(eu, ev.clientY > r.top + r.height / 2 ? c.nextSibling : c);
    });
    document.addEventListener('drop', function(ev){
      if(caixa && perto(ev, '.radio .sala')) ev.preventDefault();
    });
    document.addEventListener('dragend', function(){
      if(!caixa) return;
      var eu = aCaixa(), antes = ordemAntes;
      caixa = null; idDaCaixa = ''; ordemAntes = '';
      if(eu) eu.classList.remove('arrastando');
      var agora = ordemDasCaixas(), b = document.getElementById('rd-reordenar');
      if(b && agora && agora !== antes){ b.value = agora; b.click(); }
    });

    // ---- ARRASTAR: o destino é o adaptador inteiro, aberto ou fechado ----
    // COM UM MOVIMENTO ESPERANDO, O ARRASTO TREME (R8): a linha se arrasta
    // sempre no HTML, e quem diz «agora não» é o `radio-ocupado`, o mesmo
    // campo do «Equilibrar» — o `draggable` que seguia o «ocupado» refazia a
    // sala inteira a cada busca (O-CONECTAR-ABRE-INTEIRO-TODA-VEZ-01, cura 2).
    function ocupado(){
      var e = um('.radio [data-campo="radio-ocupado"]');
      return !!(e && e.classList.contains('apagado'));
    }
    document.addEventListener('dragstart', function(ev){
      var l = perto(ev, '.radio .linha[draggable="true"]');
      if(!l || !ev.dataTransfer) return;
      if(document.activeElement && document.activeElement.classList.contains('nome')
         && l.contains(document.activeElement)) return;
      if(ocupado()){ ev.preventDefault(); balancar(l); return; }
      ev.dataTransfer.setData('text/plain', l.dataset.id);
      ev.dataTransfer.effectAllowed = 'move';
      l.classList.add('arrastando');
    });
    document.addEventListener('dragend', function(){
      todos('.radio .linha.arrastando').forEach(function(l){ l.classList.remove('arrastando'); });
    });
    document.addEventListener('dragover', function(ev){
      if(caixa) return;
      var c = perto(ev, '.radio .lugar');
      if(!c) return;
      ev.preventDefault();
      if(ev.dataTransfer) ev.dataTransfer.dropEffect = 'move';
      todos('.radio .lugar.alvo').forEach(function(l){ if(l !== c) l.classList.remove('alvo'); });
      c.classList.add('alvo');
    });
    document.addEventListener('dragleave', function(ev){
      var c = perto(ev, '.radio .lugar');
      if(c && !c.contains(ev.relatedTarget)) c.classList.remove('alvo');
    });
    document.addEventListener('drop', function(ev){
      if(caixa) return;
      var c = perto(ev, '.radio .lugar');
      if(!c) return;
      ev.preventDefault();
      c.classList.remove('alvo');
      var quem = ev.dataTransfer ? ev.dataTransfer.getData('text/plain') : '';
      if(quem) perguntar(moldeDe(quem, c.dataset.id));
    });

    // ---- o pedido do governador vira a janela, uma vez por pedido (R3) ----
    var pedidosVistos = {};
    function olharOsPedidos(){
      todos('.radio template.pergunta-molde[data-pedido]').forEach(function(m){
        var k = m.dataset.pedido;
        if(pedidosVistos[k]) return;
        if(!document.getElementById('rd-pergunta').hidden) return;
        pedidosVistos[k] = true;
        perguntar(m);
      });
    }
    // ---- a chegada pisca o destino (R8: a confirmação é a piscada) ----
    var chegados = {};
    function olharAsChegadas(){
      todos('.radio .lugar[data-chegou]').forEach(function(c){
        (c.dataset.chegou || '').split(' ').filter(Boolean).forEach(function(q){
          var k = c.dataset.id + '|' + q;
          if(chegados[k]) return;
          chegados[k] = true;
          // quem chegou encerra a procura: o «Procurando» fecha, e a caixa
          // que recebeu pisca à vista (o controle que volta pelo pareamento
          // antigo chega por aqui também — a lista dela, passo b6)
          if(painelAberto && painelAberto.tipo === 'conectar') fecharPainel();
          c.classList.add('recebeu');
          setTimeout(function(){ c.classList.remove('recebeu'); }, 900);
        });
      });
    }

    // ---- «Examinar Entradas»: o resultado é o Check-up, e ele se abre ----
    // A lista dela, passo b8: *«não pareceu acontecer nada»*. O exame corria,
    // o botão piscava verde e o carimbo do Check-up mudava — mas o Check-up é
    // outra seção do acordeão, FECHADA enquanto ela está no rádio. Quando o
    // exame aplica (a piscada verde do piloto), a seção dele se abre. O olho
    // nasce no CLIQUE, sobre o botão clicado: guardado no carregar da página,
    // ele vigiava um nó que o piloto já trocara (medido na bancada de tela).
    document.addEventListener('click', function(ev){
      var b = perto(ev, '.radio [data-gesto="examinar-portas"]');
      if(!b || !window.MutationObserver) return;
      var olho = new MutationObserver(function(){
        if(b.classList.contains('hef-recusou')){ olho.disconnect(); return; }
        if(!b.classList.contains('hef-deu-certo')) return;
        olho.disconnect();
        var r = document.getElementById('cx8-2');
        if(r) r.checked = true;
      });
      olho.observe(b, {attributes: true, attributeFilter: ['class']});
      setTimeout(function(){ olho.disconnect(); }, 30000);
    }, true);

    // ---- a cerimônia: a âncora abre, o laço do Python diz a tela ----
    var alvoDaCerimonia = '', ultimaTela = '';
    document.addEventListener('click', function(ev){
      var a = perto(ev, '.radio a.ensina');
      if(a) alvoDaCerimonia = a.dataset.alvo || '';
      // SEM PILOTO (o desenho aberto no navegador) a resposta leva ao fim, como
      // no desenho aprovado; COM ele, quem diz a próxima tela é o laço.
      if(!comPiloto() && perto(ev, '[data-gesto="entrada-face"],[data-gesto="entrada-pular"]'))
        location.hash = 'mapear-entrada-a-entrada-fim';
    }, true);
    window.addEventListener('hashchange', function(){
      if(location.hash === '#mapear-entrada-a-entrada' && !ultimaTela){
        var b = document.getElementById('rd-comecar');
        if(b){ b.dataset.alvo = alvoDaCerimonia; b.click(); }
      }
      alvoDaCerimonia = '';
    });
    function seguirATela(){
      var el = um('[data-campo="entrada-tela"]');
      if(!el) return;
      var t = (el.getAttribute('data-tela') || '').trim();
      if(t === '\u2014') t = '';
      if(t === ultimaTela) return;
      var antes = ultimaTela; ultimaTela = t;
      if(t){ if(location.hash !== '#' + t) location.hash = t; }
      else if(antes && /^#mapear-entrada-a-entrada/.test(location.hash)) location.hash = '';
    }

    // ---- UM observador para as três leituras: o tique troca, a página olha ----
    function olhar(){ olharOsPedidos(); olharAsChegadas(); seguirATela(); seguirOPainel(); }
    var raiz = document.getElementById('rd-secao');
    if(raiz && window.MutationObserver){
      new MutationObserver(olhar).observe(raiz, {subtree: true, childList: true,
        attributes: true, attributeFilter: ['data-tela', 'data-chegou']});
    }
    olhar();
  })();
  </script>
"""




# campos_do_mapear`), e o Salvar grava pelo dono. <!-- noqa-acento: citação literal -->
from hefesto_dualsense4unix.integrations import entrada_a_entrada as _ee  # noqa: E402

#: A CENA DO DESENHO é a do meio do fluxo: o DualSense acabou de chegar à
_MP_CENA = _pacote08.campos_do_mapear({
    "estado": "porta",
    "porta": {"rotulo": "Entrada 3", "usb": "3.0", "hub": False, "storm": 0,
              "lugar_no_gabinete": "Traseira, a segunda de cima"},
    "portas": [{"nome": "Frente de cima", "numero": "1", "lugar_no_gabinete": "Frente"},
               {"nome": "", "numero": "2", "lugar_no_gabinete": "Frente"},
               {"nome": "Hub do monitor", "numero": "7", "lugar_no_gabinete": "Hub"}],
})
TELA_MAPEAR_PORTAS = f'''
<div class="tela-nova" id="mapear-portas">
  <div class="tn-cx mp-cx">
    <div class="tn-topo">
      <span class="tn-tit" data-dica="{DICA_DO_MAPEAR_PORTAS}">{MAPEAR_ENTRADAS}</span>
      <a class="tn-x" href="#" title="Fechar">×</a>
    </div>
    <div class="tn-corpo mp" id="mp-forma">
      <p class="mp-diz"><i class="mp-luz" data-campo="mapear-estado" data-hef-alvo="atributo" data-hef-atributo="data-estado" data-estado="{_MP_CENA["mapear-estado"]}"></i><span data-campo="mapear-diz">{_MP_CENA["mapear-diz"]}</span></p>
      <div class="mp-duas">
        <div class="mp-esq">
          <div class="mp-rot">O que o Hefesto mediu</div>
          <div class="mp-porta" data-campo="mapear-porta" data-hef-alvo="html">{_MP_CENA["mapear-porta"]}</div>
          <div class="mp-campos">
            <label><span class="mp-rot">Nome da entrada</span><input type="text" data-linha="nome" maxlength="32" placeholder="Ex.: Frente, a de cima"></label>
            <label><span class="mp-rot">Lugar</span><select data-linha="lugar"><option value="">Escolha o lugar</option>{"".join(f'<option>{l}</option>' for l in _ee.LUGARES_DA_PORTA)}</select></label>
          </div>
        </div>
        <div class="mp-dir">
          <div class="mp-rot">Já mapeadas</div>
          <ul class="mp-lista" data-campo="mapear-lista" data-hef-alvo="html">{_MP_CENA["mapear-lista"]}</ul>
          <p class="mp-conta" data-campo="mapear-conta">{_MP_CENA["mapear-conta"]}</p>
        </div>
      </div>
    </div>
    <div class="tn-rod">
      <a class="btn" href="#">Terminar</a>
      <button class="btn principal" data-gesto="mapear-gravar" data-hef-forma="mp-forma">Salvar e ir para a próxima</button>
      <button hidden id="mp-comecar" data-gesto="mapear-comecar"></button>
      <button hidden id="mp-parar" data-gesto="mapear-parar"></button>
    </div>
  </div>
</div>
<script>
  // A ÂNCORA ABRE, E O FLUXO COMEÇA E PARA COM ELA: o dono do mapa só olha as
  // portas enquanto a tela está aberta.
  (function(){{
    var aberto = false;
    function seguir(){{
      var agora = location.hash === '#mapear-portas';
      if(agora === aberto) return;
      aberto = agora;
      var b = document.getElementById(agora ? 'mp-comecar' : 'mp-parar');
      if(b) b.click();
    }}
    window.addEventListener('hashchange', seguir);
    seguir();
  }})();
</script>
'''

SEM_LUGAR = [(esp, no) for esp, no, em, _q in CENSO if not em]

VAGAS_NO_DESENHO = (sum(len(ns) for _n, ns in FACES) + len(EXTENSAO)
                    - len(ONDE_ESTA))
CONECTORES_QUE_NINGUEM_ALCANCA = 2
EM_PE_TOTAL = VAGAS_NO_DESENHO + CONECTORES_QUE_NINGUEM_ALCANCA

#: A frase volta à tela quando a peneira do controle (a posse tomada no `focus-in`)
#: ganhar chamador; até lá, nada a mostra.
PENEIRA_QUANDO_ELA_EXISTIR = (
    "Enquanto esta janela estiver na frente, o que você apertar no "
    "controle fica <b>aqui</b> — não chega ao jogo aberto atrás.")
PENEIRA = ""


def cerimonia(ident, pergunta, contador, quem, botoes, dica, rodape):
    """Uma das três telas do «Mapear entrada a entrada»."""
    return f'''
<div class="tela-nova" id="{ident}">
  <div class="tn-cx">
    <div class="tn-topo">
      <span class="tn-tit" data-dica="{dica}">{MAPEAR_UMA_A_UMA}</span>
      <a class="tn-x" href="#" title="Fechar" data-gesto="entrada-parar">×</a>
    </div>
    <div class="tn-corpo">
      {f'<div class="tn-frase">{PENEIRA}</div>' if PENEIRA else ""}
      <div class="moldura">
        <div class="ce-cartao">
          <span class="ce-perg">{pergunta}</span>
          <span class="ce-cont" data-campo="entrada-contador" data-hef-alvo="html">{contador}</span>
          <span class="ce-quem" data-campo="entrada-quem" data-hef-alvo="html">{quem}</span>
        </div>
        <div class="ce-botoes">{botoes}</div>
      </div>
    </div>
    <div class="tn-rod">
      {rodape}
    </div>
  </div>
</div>
'''


JA_CHEGA = (f'<a class="btn" href="#" data-gesto="entrada-parar" title="Fecha a janela na hora, '
            f'sem confirmação e sem resumo. Nada se perde: cada resposta já foi ao disco.">'
            f'{CALIB["ROTULO_JA_CHEGA"]}</a>')

TELA_SENTADA = cerimonia(
    "mapear-entrada-a-entrada",
    CALIB["PERGUNTA_SENTADA"],
    _pacote08.contador_da_cerimonia(1, len(SEM_LUGAR))
    + f' <span class="pt">·</span> {CALIB["SEM_SAIR_DA_CADEIRA"]}',
    f'{SEM_LUGAR[0][0]} <span class="pt">·</span> <code>{SEM_LUGAR[0][1]}</code>',
    "".join(
        f'<button class="btn{" foco" if i == 0 else ""}" data-gesto="entrada-face" '
        f'value="{f}" title="Cria uma entrada nesta face para este aparelho e para o que '
        f'estiver pendurado nele. Gravado na hora.">{f}</button>'
        for i, f in enumerate(CALIB["FACES"])),
    "A pergunta é sobre a entrada, não sobre o aparelho",
    f'<button class="btn" data-gesto="entrada-pular" title="Pula esta entrada, sem gravar '
    f'nada e sem perguntar de novo.">{CALIB["ROTULO_NAO_SEI"]}</button>\n      {JA_CHEGA}')

TELA_FIM = cerimonia(
    "mapear-entrada-a-entrada-fim",
    CALIB["FIM_DA_FASE_SENTADA"],
    "",
    "",
    f'<button class="btn foco" data-gesto="entrada-levantar" title="Guarda a leitura '
    f'de agora como referência e entra na fase em pé. É a única porta para ela.">'
    f'{CALIB["ROTULO_VOU_MOSTRAR"]}</button>'
    f'<a class="btn" href="#" data-gesto="entrada-parar" title="Fecha a janela. Mesmo destino do “{CALIB["ROTULO_JA_CHEGA"]}”.">'
    f'{CALIB["ROTULO_DEIXAR_PARA_DEPOIS"]}</a>',
    "Falta marcar as entradas vazias",
    JA_CHEGA)

TELA_EM_PE = cerimonia(
    "mapear-entrada-a-entrada-em-pe",
    ENCAIXE_CURTO,
    _pacote08.contador_da_cerimonia(1, EM_PE_TOTAL),
    CALIB["PROCURANDO"],
    f'<button class="btn foco" data-gesto="entrada-nao-alcanco" title="Tira esta entrada da '
    f'conta de vez: não vira dívida, não vira aviso, e o Hefesto não volta a perguntar. Ela '
    f'diminui o total do contador, não o feito.">{CALIB["ROTULO_NAO_ALCANCO"]}</button>',
    "Encaixe o DualSense com o cabo numa entrada vazia",
    JA_CHEGA)


CSS += CSS_DA_SECAO_DO_RADIO

MIOLO = f'''
    <!-- ======== A TABELA DAS CORES DO USUÁRIO, uma vez para a página inteira ========
         Os 28 modelos e as 10 zonas de `docs/data/cores-do-dualsense.csv`, com a
         hachura e os dois gradientes que oito deles usam — o
         `<defs id="cores-do-dualsense">` inteiro, lido do `ds_limpo.svg` por
         `_a_tabela_dos_28`. Ele morava DENTRO de cada desenho e vinha PODADO
         (só o modelo que o mockup escolheu), e uma tabela podada não tem como
         virar outro modelo: o alvo de atributo escreveria `white` e a casca
         continuaria caindo no cinza cru do desenho.
         O `<svg>` mede ZERO e não desenha nada — ele existe porque `<pattern>` e
         `<linearGradient>` só valem dentro de um fragmento SVG. Não muda um
         pixel do que o usuário aprovou. ======== -->
{TABELA_DAS_CORES}

    <!-- ======== 1. CHECK-UP — juízo à esquerda, conserto à direita ========
         SUBIU PARA PRIMEIRO E MUDOU DE NOME — 30/08/2026, pedido:
         *"a parte 'Está tudo certo' aparece como primeiro bloco na página e
         mudamos o nome pra Check-up"*. Faz sentido de leitura: quem abre a
         Conexões quer primeiro saber se há algo errado, e só depois a lista
         de quem está na mesa. E "Check-up" é substantivo — nomeia a seção;
         "Está tudo certo?" era pergunta, e título que pergunta faz a pessoa
         procurar a resposta em vez de ler o que está embaixo. ======== -->
    <div class="quadro">
      <!-- SÓ O CHECK-UP NASCE ABERTO — 30/08/2026, pedido: *"inicia as
           demais abas de gestão e rádio minimizadas"*. Faz sentido de uso: quem
           abre a Conexões quer primeiro saber se há algo errado; a lista da mesa
           e o inventário de rádios são consulta, não alerta. E resolve, de
           quebra, os 208px que o quadro de baixo perdia por não caber. -->
      <!-- ABRIR UMA MINIMIZA AS OUTRAS — 31/08/2026, pedido: *"abrir uma
           expansão minimiza a outra"*.

           `type="radio"` COM O MESMO `name`, e não JavaScript: é a gramática que
           esta casa já usa no interruptor da aba Jogar e nos três estados da
           página de calibração. O navegador é quem garante a exclusão — não há
           estado a sincronizar, e o mockup continua sem uma linha de script.

           O QUE ISSO TROCA, e é troca boa: com rádio não se fecha a última
           clicando nela de novo, então há SEMPRE uma seção aberta. Medido antes:
           com as três fechadas sobravam **428px** de vão até o rodapé, e com as
           três abertas a página passava **248px** do miolo e rolava. Os dois
           extremos deixam de existir.

           O CSS do esqueleto não precisou mudar: ele lê `input.abre:checked`,
           que vale igual para caixa e para rádio. -->
      <input class="abre" type="radio" name="cx8-secao" id="cx8-2" checked>
      <div class="quadro-topo">
        <label class="quadro-titulo" for="cx8-2" data-dica="Dicas em cima, um cartão por controle embaixo">Gestão de controles</label>
      </div>
      <div class="quadro-corpo">
        <!-- A LINHA DE VEREDITO SAIU — 26/09/2026, pedido com a janela
             maximizada: *«precisamos ganhar espaço vertical. vamos remover a
             linha 3 mudanças recomendadas»*. Revoga a D-16 de 04/09 («Uma
             linha de veredito no topo»): a Sugestão de Conexão ao lado já
             numera cada mudança, e a contagem repetia a caixa. -->
        <!-- AS DICAS SÃO CARTÕES COM UM GESTO — 04/10/2026, AS-DICAS-SAO-CARTOES-COM-UM-GESTO-01
             (o desenho 4 que o usuário aprovou). O exame de cinco frases e a «Sugestão de Conexão»
             saíram: no lugar dos dois, uma fileira de cartões com três a cinco palavras, o de→para
             e UM botão cada; os três que mais pesam aparecem, o resto fica em «mais N», e o que
             está certo vira uma linha no fim. É UM endereço com alvo `html`: o produto repinta a
             fileira inteira, e o desenho mostra os mesmos cartões, montados pelas mesmas funções
             (`a08_conexoes._html_das_dicas`). -->
        <div class="dicas-da-conexao" data-campo="{CAMPO_DAS_DICAS}" data-hef-alvo="html">{DICAS_DA_CENA}</div>

        <!-- OS QUATRO BOTÕES SAÍRAM — 31/08/2026, e cada um por um motivo dela.

             *"não faz sentido termos o examinar e o reexaminar"*: os dois faziam
             a MESMA coisa — refazer o exame. `Já movi — reexaminar` só prometia
             comparar o antes com o depois, e essa comparação não estava desenhada
             em lugar nenhum. Sobrou um, e ele desceu para a seção que fala das
             entradas, como o usuário mandou.

             `Ignorar` mora no ⓘ de cada cartão de dica (04/10/2026), e a ordem calada
             fica no fim, apagada, com o botão «Voltar a mostrar». E `{VER_IGNORADAS}`
             saiu com o glifo de cada linha (31/08), que era onde o gesto tinha sujeito. -->
        <!-- AS FERRAMENTAS MORAM NO CHECK-UP — 25/09/2026, pedido
             (A-08-O-CHECKUP-ABSORVE-A-GESTAO-01). O «Mapear Entradas» é UM botão
             só: a âncora abre o fluxo guiado porta a porta (`#mapear-portas`),
             que chama o dono do mapa (`entrada_a_entrada.o_mapa()`). A âncora
             não é gesto (a §P4): quem começa o fluxo é o `#mp-comecar`. -->
        <!-- QUATRO FERRAMENTAS, TODAS COM ÍCONE — 26/09/2026, pedido: *«não
             existe diferença entre o examinar entradas e atualizar»* e *«falta os
             svg ou glifos»*. O «Atualizar» entrou no «Examinar Entradas» (um clique
             refaz o exame e relê os controles), e as quatro colunas são as dos
             cartões embaixo: cada botão fica em cima de um cartão. -->
        <!-- O ACORDEÃO PASSOU A SER LIDO DE VOLTA — 06/09/2026,
             `CONEXOES-LIGAR-TUDO-01`. Os {len(MESA) + 1} rádios são o alvo de
             saída do daemon (`output_target_index`), e até hoje o `checked`
             ficava onde o desenho o pôs: ela clicava "só este" no P2, o daemon
             obedecia, e no tique seguinte a tela continuava apontando o P1.

             UM ENDEREÇO, AS DUAS METADES DA QUEIXA. O destaque da FITA do topo
             não vem do `.on` que o piloto escreve — vem das regras
             `body:has(#gc-pN:checked) .fita .chip[data-pref="pN"]` geradas
             logo acima, pelo número do jogador —, então marcar o rádio certo
             move o acordeão e a fita juntos.

             O ALVO É `marcado`, o décimo do pintor (decisão em 04/09,
             `PINTOR-MARCADO-01`): dos nove anteriores, `valor` escreve
             `el.value`, que num `<input type=radio>` é a string `"on"` e não o
             estado. A LISTA vem na ordem do DOM — `todos` primeiro, depois um
             por lugar —, que é como o piloto distribui uma lista pelos
             elementos de mesmo `data-campo`. -->
        <input type="radio" name="gc" id="gc-todos" class="gc-r"
               data-campo="alvo-aberto" data-hef-alvo="marcado">
{chr(10).join(f"""        <input type="radio" name="gc" id="gc-{c["pref"]}" class="gc-r"
               data-campo="alvo-aberto" data-hef-alvo="marcado"{" checked" if c["alvo"] else ""}>"""
              for c in MESA)}
        <!-- OS DOIS AVISOS QUE A CASA SABIA E ESTA TELA NÃO DIZIA —
             06/09/2026. Os dois têm dono no produto e zero leitor no HTML até
             hoje:

               · `status_actions.texto_de_controle_nao_adotado` — *"está ligado
                 e não chegou até aqui"*, com o que o produto tenta sozinho, em
                 quanto tempo, e a saída manual. O defeito que ele cura (dois
                 DualSense ligados e a janela mostrando um, sem uma pista do
                 porquê) voltava inteiro no HTML;
               · `home_actions.texto_native_bt_fragil` — o modo nativo com o
                 controle no rádio, COM OS NÚMEROS de quem está frágil.

             ELES SÃO LINHA DE RESSALVA (a D-02 dela) e por isso entram os dois
             sem custar altura: em repouso `.ressalva:has(.nada)` mede ZERO —
             que é o estado desta bancada e o desta máquina hoje. -->
        {monta_ressalva("sem-driver")}
        {monta_ressalva("radio-fragil")}
        <div class="gc">
{chr(10).join(linha_do_controle(c) for c in MESA)}
          <!-- OS CONTROLES QUE O HEFESTO SÓ VÊ — EXTERNOS-01, 06/09/2026, e é a
               linha 305 do `docs/data/paridade-gtk-html.csv`: *"uma aba chamada
               Conexões que não lista metade dos controles conectados"*.

               DENTRO DO `.gc`, POR ESCOLHA DO USUÁRIO — 06/09/2026, olhando as duas
               maquetes: *no mesmo frame dos assentos*, como a janela GTK fazia.
               A EXTERNOS-01 entregou a ressalva embaixo do acordeão e
               perguntou; esta é a resposta.

               A LINHA NÃO VIRA UM `.gc-item` POR ISSO, e a razão da EXTERNOS-01
               continua de pé: cada `.gc-item` tem `data-controle="pN"`, um
               rádio de alvo de saída do daemon e um corpo que abre. Um externo
               não tem assento, não é alvo de saída de nada e não tem o que
               abrir. Estar na mesma moldura é DESENHO; ser um assento é uma
               afirmação sobre o aparelho, e a tela não a faz.

               ELE NASCE VAZIO pela mesma razão da tabela dos adaptadores e do
               mapa do gabinete: quantos existem é o que a máquina responde. -->
          <div class="ext-vaga" data-campo="externos-lista" data-hef-alvo="html"><i class="nada"></i></div>
          <!-- 22/10/2026, o arranjo C da janela da extensão: as conexões e os aparelhos que cada
               extensão ligada publica (`acessorios.estado`), «via» o nome dela, na mesma moldura dos
               externos e pela mesma razão: o Hefesto os VÊ, não os adota. Nasce vazia: quantos
               existem é o que as extensões respondem. -->
          <div class="ext-vaga" data-campo="extensoes-lista" data-hef-alvo="html"><i class="nada"></i></div>
        </div>
        <!-- 05/10/2026, o desenho aprovado: as quatro ferramentas descem para baixo dos cartões. -->
        <div class="ferramentas">
          <a class="btn" href="#mapear-portas" title="{MAPEAR_ENTRADAS} — ligue o DualSense em cada entrada, uma por vez; o nome e o lugar são opcionais">
            <svg class="i" aria-hidden="true"><use href="#rd-mapa"/></svg> {MAPEAR_ENTRADAS}</a>
          <button class="btn" data-gesto="examinar-portas" title="{EXAMINAR_PORTAS} — refaz o exame das entradas, da energia e do Bluetooth, e relê o estado de cada controle">
            <svg class="i" aria-hidden="true"><use href="#rd-reexaminar"/></svg> {EXAMINAR_PORTAS}</button>
          <a class="btn" href="mapa-do-controle.html" title="O mapa do controle — abre no navegador">
            <svg class="i ds" aria-hidden="true"><use href="#rd-ds"/></svg> Mapa do controle</a>
          <a class="btn" href="mapa-das-portas.html" title="O mapa das conexões: cada entrada do computador, o que está nela e o que mudar">
            <svg class="i" aria-hidden="true"><use href="#rd-hub"/></svg> Mapa das conexões</a>
        </div>
      </div>
    </div>

    <!-- ======== 3. RÁDIO E ADAPTADORES — o `mapa-do-radio.html` aprovado ========
         TRANSPLANTE-DA-SECAO-01, 23/09/2026. A seção inteira é o desenho que
         o usuário aprovou; a folha, o sprite e a cena de exemplo são LIDOS dele
         (`_css_do_radio`, `_sprite_do_radio`, `_cena_do_desenho`). Quem pinta
         é o pacote (`a08_conexoes.campos_da_secao`); o roteiro só abre o que
         o Python já pintou.

         AS DUAS ÂNCORAS NÃO SÃO GESTOS, e é a regra da §P4: `#mapear-entradas`
         e `#mapear-entrada-a-entrada` abrem as `div.tela-nova` por `:target`.
         Quem começa o laço da cerimônia é o `#rd-comecar`, que o roteiro clica
         quando a âncora abre — um gesto de nome próprio, e não um segundo nome
         para a âncora. ======== -->
    <div class="quadro radio" id="rd-secao">
      <input class="abre" type="radio" name="cx8-secao" id="cx8-3">
      <div class="quadro-topo cab">
        <label class="quadro-titulo" for="cx8-3">Rádio e adaptadores</label>
        <div class="direita">
          {INTERRUPTOR_PROCURAR}
          <button class="btn principal" id="rd-b-conectar" data-gesto="conectar-aparelho" title="Conectar um aparelho novo">
            <svg class="i" aria-hidden="true"><use href="#rd-mais"/></svg> Conectar</button>
          <button class="btn" id="rd-b-equilibrar" data-gesto="equilibrar-radio" data-campo="radio-ocupado" data-hef-alvo="classe" data-hef-classe="apagado" title="Move um controle por vez">
            <svg class="i" aria-hidden="true"><use href="#rd-equilibrar"/></svg> Equilibrar</button>
        </div>
      </div>
      <div class="quadro-corpo">
        <div class="espectro">
          <div class="espectro-cab">
            <span data-dica="{AJUDA_DO_AR}">Dispositivos conectados</span>
            {LEGENDA_DAS_FAIXAS}
          </div>
          <div class="pistas" data-campo="espectro-canais" data-hef-alvo="html">{CAMPOS_DO_RADIO["espectro-canais"]}</div>
        </div>

        <div class="sala" data-campo="radio-sala" data-hef-alvo="html">{SALA_DO_DESENHO}</div>
        <button hidden id="rd-reordenar" data-gesto="adaptador-reordenar" value=""></button>
        <button hidden id="rd-escolher" data-gesto="escolher-adaptador" data-alvo=""></button>
        <div class="moldes" data-campo="radio-moldes" data-hef-alvo="html">{CAMPOS_DO_RADIO["radio-moldes"]}</div>

        <!-- OS BOTÕES DAS ENTRADAS SUBIRAM PARA O CHECK-UP — 25/09/2026. Ficam
             aqui só as duas peças escondidas da cerimônia antiga, que o roteiro
             desta seção ainda lê (`#rd-comecar` e `entrada-tela`). -->
        <div class="entradas" hidden>
          <button hidden id="rd-comecar" data-gesto="entrada-comecar" data-alvo=""></button>
          <i hidden data-campo="entrada-tela" data-hef-alvo="atributo" data-hef-atributo="data-tela"></i>
        </div>

        <div class="veu" id="rd-veu-pergunta"></div>
        <div class="caixa-pergunta" id="rd-pergunta" role="alertdialog" aria-modal="true" aria-labelledby="rd-pergunta-diz" hidden>
          <p class="diz" id="rd-pergunta-diz"></p>
          <div class="botoes">
            <button class="btn cancelar" id="rd-pergunta-nao" data-gesto="cancelar-mudanca">Cancelar</button>
            <button class="btn outro" id="rd-pergunta-outro" data-gesto="ligar-mesmo-assim" hidden></button>
            <button class="btn confirma" id="rd-pergunta-sim" data-gesto="confirmar-mudanca"></button>
          </div>
        </div>
        <aside class="painel" id="rd-painel" aria-hidden="true" inert role="dialog" aria-labelledby="rd-painel-titulo">
          <div class="painel-cab">
            <span class="pulso" id="rd-pulso"></span>
            <h2 id="rd-painel-titulo"></h2>
            {INTERRUPTOR_PROCURAR}
            <button class="btn so-icone fechar" id="rd-fechar" aria-label="Fechar" title="Fechar">
              <svg class="i" aria-hidden="true"><use href="#rd-sair"/></svg></button>
          </div>
          <div id="rd-painel-corpo"></div>
        </aside>
      </div>
    </div>
{SPRITE_DO_RADIO}
{SPRITE_DOS_EXTERNOS}
{SCRIPT_DA_SECAO_DO_RADIO}
{SCRIPT_DAS_FAIXAS}
'''


if __name__ == "__main__":
    import os
    import shutil
    import tempfile

    _real = onde.saida()
    _prova = pathlib.Path(tempfile.mkdtemp(prefix="hefesto-prova-08-"))
    for _vizinha in _real.glob("*.html"):
        shutil.copy2(_vizinha, _prova / _vizinha.name)
    os.environ[onde._DESVIO] = str(_prova)
    n = monta("08-conexoes", "Conexões", MIOLO, CSS)

    p = onde.pagina("08-conexoes.html")
    x = p.read_text()
    MARCA = "<!-- ===== fim da aba ===== -->"
    if MARCA not in x:
        raise SystemExit("ERRO: a marca da legenda mudou no fim.html")
    TELAS = "\n".join(t.strip() for t in (TELA_MAPEAR,
                                             _pacote08.html_do_acionador(CENA_DO_RADIO,
                                                                         _desenho_do_acionador()),
                                             _pacote08.html_da_grade_de_tipos(), TELA_SENTADA,
                                             TELA_FIM, TELA_EM_PE, TELA_MAPEAR_PORTAS))
    x = x.replace(MARCA, TELAS + "\n\n" + MARCA, 1)

    _CHIP = '<label class="chip plastico'
    _quantos = x.count(_CHIP)
    if _quantos != len(CONECTADOS):
        raise SystemExit(
            f"ERRO em 08-conexoes: a fita tem {_quantos} chips de plástico e a mesa "
            f"tem {len(CONECTADOS)} conectados. O endereço da identidade não pode "
            f"cair em cima de um chip que não existe — nem faltar num que existe.")

    onde.gravar("08-conexoes.html", x)


    _HTML = onde.pagina("08-conexoes.html").read_text()
    _falhas = []


    def _exigir(cond, queixa):
        if not cond:
            _falhas.append(queixa)


    def _dentro_do_acordeao(doc: str) -> str:
        """O `<div class="gc">…</div>` INTEIRO, contado por `div` aberto e fechado."""
        marca = '<div class="gc">'
        inicio = doc.find(marca)
        if inicio < 0:
            return ""
        profundidade = 0
        i = inicio
        while i < len(doc):
            abre = doc.find("<div", i)
            fecha = doc.find("</div>", i)
            if fecha < 0:
                return doc[inicio:]
            if 0 <= abre < fecha:
                profundidade += 1
                i = abre + 4
                continue
            profundidade -= 1
            if profundidade == 0:
                return doc[inicio:fecha + 6]
            i = fecha + 6
        return doc[inicio:]


    _ABRE = re.findall(r'<input class="abre" type="(\w+)"(?: name="([^"]*)")?', _HTML)
    _exigir(len(_ABRE) == 2, f"não são 2 seções que expandem, e sim {len(_ABRE)}")
    _exigir(all(t == "radio" for t, _ in _ABRE),
            "uma seção voltou a ser `checkbox` — duas abertas ao mesmo tempo é o que "
            "ela mandou desfazer: *abrir uma expansão minimiza a outra*")
    _exigir(len({n for _, n in _ABRE}) == 1 and _ABRE[0][1],
            "os rádios das seções não dividem o mesmo `name` — sem isso o navegador "
            "não tem como fechar a outra")

    _DICAS = _HTML.count('data-campo="dicas" data-hef-alvo="html"')
    _exigir(_DICAS == 1,
            f"as dicas têm {_DICAS} endereços e o produto repinta UM — o exame de frases e a "
            "«Sugestão de Conexão» saíram, e o cartão que ficar fora do campo nunca é pintado")
    _CARTOES = _HTML.count('<section class="cartao-dica ')
    _exigir(_CARTOES <= _dicas.CARTOES_VISIVEIS,
            f"o desenho tem {_CARTOES} cartões de dica; a fileira mostra {_dicas.CARTOES_VISIVEIS}, "
            "sem «mais N»")

    _MARCADOS = _HTML.count('data-campo="alvo-aberto" data-hef-alvo="marcado"')
    _exigir(len(MESA) + 1 == _MARCADOS,
            f"são {_MARCADOS} rádios do acordeão com endereço e a mesa tem "
            f"{len(MESA)} lugares mais o 'todos' — a lista do alvo é distribuída "
            "por POSIÇÃO, e um endereço a menos aponta o controle errado")
    _exigir(_HTML.count('data-hef-alvo="marcado" checked') <= 1,
            "mais de um rádio do acordeão nasce `checked` — o desenho não pode "
            "afirmar dois alvos de saída ao mesmo tempo")

    for _campo in ("sem-driver", "radio-fragil"):
        _exigir(_HTML.count(f'class="ressalva" data-campo="{_campo}"') == 1,
                f"a linha de ressalva `{_campo}` não está na página — o dono da "
                f"frase existe no produto e a tela volta a não ter onde escrevê-la")

    _exigir(_HTML.count('data-campo="externos-lista" data-hef-alvo="html"') == 1,
            "os controles que o Hefesto só vê ficaram sem endereço — o dono da "
            "frase existe no produto (`home_actions._format_external_title` e as "
            "duas irmãs) e a tela volta a não ter onde escrevê-la")
    #     porque cada linha de controle traz meia dúzia de `<div>` dentro — um
    _exigir('data-campo="externos-lista"' in _dentro_do_acordeao(_HTML),
            "o bloco dos externos saiu de dentro do acordeão dos controles — "
            "ela escolheu o MESMO frame em 06/09/2026, e a ressalva à parte é "
            "a maquete que ela recusou")
    _exigir(".gc .ext-vaga{display:contents}" in _HTML,
            "a vaga dos externos deixou de ser `display:contents` — as linhas "
            "voltam a empilhar dentro de um item só do acordeão")

    _exigir(_HTML.count('data-campo="extensoes-lista" data-hef-alvo="html"') == 1
            and 'data-campo="extensoes-lista"' in _dentro_do_acordeao(_HTML),
            "os aparelhos das extensões ficaram sem endereço, ou fora da moldura dos controles")
    _exigir("ext-acessorio" not in re.sub(r"<style\b.*?</style>", "", _HTML, flags=re.S),
            "um aparelho de extensão nasceu no desenho — a tela estaria afirmando um aparelho "
            "que nenhuma extensão publicou")
    _exigir('class="ext-linha"' not in _HTML,
            "uma linha de controle externo nasceu no desenho — a tela estaria "
            "afirmando um aparelho que ninguém mediu")

    _exigir(".quadro:has(> input.abre) .quadro-topo{padding-bottom:11px}" in _HTML,
            "o rótulo das seções que expandem perdeu o respiro de baixo — volta a "
            "1px contra os 12 de cima, que é o que ela viu nas duas fotos")

    _exigir("class=\"" + "ajuda" not in _HTML and "cd-" + "info" not in _HTML,
            "a aba Conexões voltou a ter um «?» ou um «i»: a dica mora no hover do título")
    _FORA = [c for c in MESA if not c.get("conectado", True)]
    _exigir(_HTML.count('<span class="sep">•</span>Desconectado</span>') == len(_FORA),
            "o lugar vazio da Gestão não diz «P N • Desconectado»: é o desenho de 14/10 (q4B)")
    for _c in _FORA:
        _exigir(rotulo(_c) not in _HTML,
                f"o rótulo de mesa do Player {_c['jogador']} continua na tela — ele não está na mesa")

    _CAMPO = re.compile(r'data-campo="([^"]*)"')


    def _campos_do_lugar(pref: str) -> set[str]:
        """Os `data-campo` DENTRO do cartão daquele lugar, por `div` balanceado."""
        marca = f'data-controle="{pref}"'
        achado = _HTML.find(marca)
        if achado < 0:
            return set()
        inicio = _HTML.rfind("<div", 0, achado)
        profundidade, i = 0, inicio
        while i < len(_HTML):
            abre, fecha = _HTML.find("<div", i), _HTML.find("</div>", i)
            if fecha < 0:
                break
            if 0 <= abre < fecha:
                profundidade += 1
                i = abre + 4
                continue
            profundidade -= 1
            if profundidade == 0:
                return set(_CAMPO.findall(_HTML[inicio:fecha + 6]))
            i = fecha + 6
        return set()


    _LUGARES = [c["pref"] for c in MESA]
    _CAMPOS_POR_LUGAR = {p: _campos_do_lugar(p) for p in _LUGARES}
    for _p, _campos in _CAMPOS_POR_LUGAR.items():
        _exigir(bool(_campos),
                f"o cartão do {_p} não tem `data-campo` nenhum — ou ele sumiu da "
                "página, ou o `data-controle` dele saiu do `<div>` que a régua "
                "abre. Nos dois casos o produto não tem por onde escrever nele")
    _REFERENCIA = _CAMPOS_POR_LUGAR[_LUGARES[0]]
    for _p in _LUGARES[1:]:
        _falta = sorted(_REFERENCIA - _CAMPOS_POR_LUGAR[_p])
        _sobra = sorted(_CAMPOS_POR_LUGAR[_p] - _REFERENCIA)
        _exigir(not _falta,
                f"o cartão do {_p} não tem os campos {', '.join(_falta)} que o "
                f"{_LUGARES[0]} tem. Quando esse controle chegar, o piloto vai "
                "escrever no vazio — foi o que ela viu em 07/09 com quatro "
                "DualSense na mesa e dois na tela")
        _exigir(not _sobra,
                f"o cartão do {_p} tem os campos {', '.join(_sobra)} que o "
                f"{_LUGARES[0]} não tem. O conjunto é IGUAL, não maior: um campo "
                "só num lugar é a segunda grafia do mesmo fato")

    _inicio_da_gestao = _HTML.index('id="cx8-2"')
    _topo_da_gestao = _HTML[_inicio_da_gestao:_HTML.index('class="quadro-corpo"', _inicio_da_gestao)]
    _exigir('class="conta"' not in _topo_da_gestao,
            "o cabeçalho da Gestão voltou a ter o carimbo ou a contagem no canto")

    _SECAO = _HTML[_HTML.index('id="rd-secao"'):_HTML.index("window.__hefRadio")]
    _EMITIDOS = set(_pacote08.campos_da_secao(CENA_DO_RADIO)) | {
        "entrada-tela", "entrada-contador", "entrada-quem"}
    _NA_PAGINA = set(re.findall(r'data-campo="([^"]+)"', _HTML))
    for _campo in sorted(_EMITIDOS - _NA_PAGINA):
        _exigir(False, f"o pacote emite `{_campo}` e a página não tem onde pintá-lo")
    _DA_SECAO = set(re.findall(r'data-campo="([^"]+)"', _SECAO))
    for _campo in sorted(_DA_SECAO - _EMITIDOS - {"hz-movimento", "hz-voz", "hz-nivel",
                                                  "hz-dica"}):
        _exigir(False, f"a seção tem o endereço `{_campo}` e o pacote não o emite")
    _ANCORAS = re.findall(r'<a [^>]*href="#(mapear-[\w-]+)"[^>]*>', _HTML)
    for _a in re.findall(r'<a [^>]*href="#mapear-entrada(?:s|-a-entrada)"[^>]*>', _HTML):
        _exigir("data-gesto" not in _a, f"uma âncora das telas ganhou gesto: {_a[:90]}")
    _GESTOS = set(re.findall(r'data-gesto="([^"]+)"', _HTML))
    for _g in sorted(_GESTOS & set(_ANCORAS)):
        _exigir(False, f"o gesto `{_g}` tem o nome de uma âncora — dois nomes para um ato")
    _exigir("fatia" not in _SECAO.lower(), "a palavra «fatia» chegou à seção do rádio")
    _exigir(_HTML.count('id="rd-secao"') == 1 and _HTML.count('<symbol id="rd-ds"') == 1,
            "a seção ou o sprite do rádio saiu repetido")

    if _falhas:
        raise SystemExit("ERRO em 08-conexoes — decisão dela desfeita:\n  "
                         + "\n  ".join(f"- {f}" for f in _falhas))

    print(f"08-conexoes: OK, {n} divs · 5 telas novas "
          f"(1 do desenho + {3} da cerimônia + o Mapear) · 2 seções exclusivas · "
          f"{len(CONECTADOS)} na mesa + {len(_FORA)} desconectado(s)")
    shutil.copyfile(_prova / "08-conexoes.html", _real / "08-conexoes.html")
    shutil.rmtree(_prova)
