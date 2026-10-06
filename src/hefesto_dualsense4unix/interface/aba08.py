# A PASTA, não /tmp: estas três liam um `monta` de /tmp — o de 26/08 23:50 —
import ast
import html
import importlib.util
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import onde  # noqa: E402
from monta import (DS, MESA, CONECTADOS, CSS_GLIFO, CSS_POPUP, TRAVESSAO,  # noqa: E402
                   cor_da_zona, monta, player_slot_color,
                   ressalva as monta_ressalva, svg)

# geradores 08 e 09 pararam de RODAR por isso, calados até alguém tentar:
from onde import RAIZ as R  # noqa: E402

from hefesto_dualsense4unix.interface import conexoes as _aba_conexoes  # noqa: E402
from hefesto_dualsense4unix.integrations import entrada_a_entrada as _entrada_a_entrada  # noqa: E402,E501

from hefesto_dualsense4unix.integrations import dicas_da_conexao as _dicas  # noqa: E402
from hefesto_dualsense4unix.integrations import ordens_da_mesa as _ordens  # noqa: E402
from pacotes import a08_conexoes as _pacote08  # noqa: E402

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
                   {"_ORCAMENTO_COM_TETO", "SEM_TETO"})
COM_TETO = _RUM["_ORCAMENTO_COM_TETO"]
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
TETO_DO_CONTROLE = {"p3": COM_TETO}
BOTAO_DO_MIC = _pacote08.FALA_DO_BOTAO_DO_MIC[True]


CASA_DO_TETO_GLOBAL = _aba_conexoes.CASA_DO_TETO_GLOBAL
ABA_DO_TETO_GLOBAL = _aba_conexoes.ABA_DO_TETO_GLOBAL

GLOBAL_VIVO = _constantes(R / "src/hefesto_dualsense4unix/profiles/manager.py",
                          {"_RUMBLE_POLICY_PADRAO"})["_RUMBLE_POLICY_PADRAO"]


def _vibracao_da_bancada(c):
    """As quatro pontas que a BANCADA declara para um controle do desenho."""
    return _aba_conexoes.Vibracao(
        do_controle=TETO_DO_CONTROLE.get(c["pref"]),
        do_perfil=None,
        a_viva=GLOBAL_VIVO,
        orcamento=ORCAMENTO_DA_MESA,
    )


def teto_que_vale(c):
    """(o que a tela mostra no CAMPO, a frase de quem manda neste controle)."""
    return _aba_conexoes.teto_que_vale(_vibracao_da_bancada(c))


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
POR_PREF = {c["pref"]: c for c in MESA}

CAMPO_DAS_DICAS = "dicas"


#: o controle conhecido que pede para parear no desenho (O-CONTROLE-QUE-PEDE-PARA-PAREAR-…-01):
#: o «Roxo», ouvido pelo primeiro adaptador do desenho
PEDIDO_DO_DESENHO = {"aparelho": "AABBCC0000F7", "lugar": "L1", "nome": "Roxo"}


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
                controle="p2", jogador=2, nome_do_controle="o controle", de_id="meio",
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
  /* 6.1 · O RESPIRO DO RÓTULO QUE EXPANDE — 31/08/2026, pedido dela com duas
     fotos desta aba: *"o nome dos campos que expandem não tem respiro"*.

     MEDIDO no Chrome antes de mexer, e a medida acha a causa exata: o
     `.quadro-topo` do esqueleto é `padding:11px 14px 0` — **zero embaixo**. Num
     quadro comum isso não aparece, porque o conteúdo vem logo abaixo e traz o
     próprio respiro. Num acordeão FECHADO não vem nada: sobrava **1px** entre o
     texto e a borda de baixo da faixa, contra 12px em cima. O rótulo não estava
     centrado na faixa — estava encostado nela.

     A CURA DEFINITIVA É UMA VARIÁVEL NO `topo.html`, como a lista dela manda —
     e o `topo.html` está CONGELADO por decisão dela de hoje, enquanto duas
     sessões trabalham na mesma árvore. Esta regra é local à Conexões, que é a
     única aba com acordeão de verdade (medido: `input.abre` = 3 aqui, 0 nas
     outras doze páginas). Quando o esqueleto descongelar, ela sobe para lá e
     esta some. */
  .quadro:has(> input.abre) .quadro-topo{padding-bottom:11px}
  /* A SEÇÃO ABERTA SOBE OS BLOCOS — 26/09/2026, pedido dela: *«tem uma linha
     abaixo do gestão de controles que não tá sendo usada. Deveriamos subir os
     blocos de seção pra ocupar ali de cima tambem»* (noqa-acento: citação literal).
     O respiro de baixo do rótulo (11px) é do acordeão FECHADO; aberto, o
     corpo vem logo embaixo e os dois respiros somavam 21px de faixa vazia. */
  .quadro:has(> input.abre:checked) .quadro-topo{padding-bottom:5px}
  .quadro:has(> input.abre:checked) > .quadro-corpo{padding-top:4px}

  /* O NOME DO ADAPTADOR É EDITÁVEL NO LUGAR — o botão `Renomear` saiu.
     `contenteditable` é o que o mockup faz sem JavaScript; o DUPLO clique que ela
     pediu é gesto do produto. O tracejado é o que diz que ali se escreve — sem
     ele o campo mente por omissão, parecendo texto morto. */
  .renomeia{border-bottom:1px dashed var(--linha);cursor:text}
  .renomeia:hover{border-bottom-color:var(--cyan)}
  .renomeia:focus{outline:none;border-bottom-style:solid;border-bottom-color:var(--cyan)}

  /* O LUGAR SEM CONTROLE na Gestão. A cor é a do `.vazio` da Gatilhos, que é a
     página que ela mandou copiar; o contraste está medido na prova de tela. A
     borda do plástico não vem — ela identifica a peça que está ali, e não há
     peça a identificar.

     A CLASSE ERA `fora` E PASSOU A SER `off` — 07/09/2026, e a troca é o que
     faz o lugar vazio VOLTAR quando o controle chega. `off` é a marca que o
     piloto conhece: ele a escreve no passo `1b` (lugar sem dono) e a TIRA no
     passo `1c` (lugar que ganhou dono). `fora` era palavra só desta aba, e
     nenhum passo do piloto a tirava — então um P3 que chegasse encontrava o
     cartão cinza, sem cursor e sem resumo, para sempre. Medido com os quatro
     DualSense dela na mesa em 07/09: o daemon publicava quatro, a carga
     chegava com os quatro em `ocupados`, e a tela mostrava dois.

     AS TRÊS REGRAS ABAIXO SÃO O QUE ELA DECIDIU EM 31/08 — *"o espaço fica,
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
  .gc-item.off .gc-nome{color:var(--comment)}
  .gc-item.off{cursor:default;border-style:dashed}
  .gc-item.off .gc-cabeca{border-bottom:0}
  .gc-item.off .gc-resumo,
  .gc-item.off .gc-corpo{display:none}
  .gc-item.off .gc-dono{visibility:hidden}
  .gc-item.off .ds-mini{opacity:.3}
  .gc-item.off .gc-abre,
  .gc-item.off .gc-num{pointer-events:none;color:var(--comment)}

  /* ================= Conexões =================
     Três assuntos, três quadros, agrupados por PERGUNTA:
       1. "está tudo certo?"   — DUAS colunas: o que eu vi · o que fazer. A
          terceira ("o que só você sabe") saiu em 28/08: as duas perguntas de
          rádio passaram a morar no "Mapear Entradas", que é a janela onde
          ela já declara a sala.
       2. "Gestão de Controles"   — os controles ligados, em acordeão: o da fita
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
     AS-DICAS-SAO-CARTOES-COM-UM-GESTO-01 (04/10/2026), o desenho 4 que ela aprovou. Cor nunca
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
     recortado de propósito é, para a régua da janela estreita, texto que a janela engoliu */
  .cartao-dica .cd-info{flex:0 0 18px;width:18px;height:18px;border-radius:50%;padding:0;
              border:1px solid var(--linha);background:none;color:var(--texto-mudo);
              display:inline-flex;align-items:center;justify-content:center;cursor:pointer}
  .cartao-dica .cd-info .cd-i{width:12px;height:12px;fill:none;stroke:currentColor;
              stroke-width:2.6;stroke-linecap:round}
  .cartao-dica .cd-info .cd-i circle{fill:currentColor;stroke:none}
  .cartao-dica .cd-info:hover,.cartao-dica .cd-info[aria-expanded="true"]{border-color:var(--cyan);color:var(--cyan)}
  .cd-detalhe{margin:0;font-size:11px;font-family:'JetBrains Mono',monospace;
              color:var(--texto-mudo)}
  .cartao-dica .cd-pic{display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin:0;
             font-size:10.5px;font-family:'JetBrains Mono',monospace;color:var(--texto-mudo)}
  .cartao-dica .cd-pic i{font-style:normal;color:var(--green)}
  .cd-porque{position:absolute;left:-1px;right:-1px;top:calc(100% + 4px);z-index:30;
             padding:10px 12px;border:1px solid var(--border-forte);border-radius:8px;
             background:var(--panel);box-shadow:0 8px 24px rgba(0,0,0,.6);
             font-size:11.5px;line-height:1.4;color:var(--texto-suave)}
  .cd-porque p{margin:0 0 6px}
  .cartao-dica .cd-ignora{background:none;border:0;padding:0;min-height:0;height:auto;
             font-size:11.5px;color:var(--texto-mudo);text-decoration:underline;cursor:pointer}
  .cartao-dica .cd-ignora:hover{color:var(--fg)}
  .cd-acao{margin-top:auto;display:flex;justify-content:flex-end}
  .cartao-dica .cd-botao{display:flex;align-items:center;justify-content:center;width:auto;
              box-sizing:border-box;min-height:28px;padding:0 12px;text-align:center;
              text-decoration:none;border-color:var(--green);color:var(--green)}
  .cartao-dica .cd-botao:hover{background:rgba(80,250,123,.09)}
  /* a dica que ela mandou calar fica no fim, apagada: o achado esmaece, o caminho de volta não */
  .cartao-dica.calada .cd-cab,.cartao-dica.calada .cd-pic,.cartao-dica.calada .cd-detalhe{opacity:.45}
  .nada-a-mudar{display:flex;align-items:center;gap:8px;margin:0;font-size:13px;color:var(--green)}
  .nada-a-mudar i{width:9px;height:9px;border-radius:50%;background:currentColor}

  /* OS CONTROLES QUE O HEFESTO SÓ VÊ — EXTERNOS-01 (06/09/2026, linha 305 do
     CSV da paridade) e a escolha DELA no mesmo dia: **no mesmo frame dos
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
  /* NA GRADE DOS CARTÕES o externo atravessa as quatro colunas, embaixo. */
  .gc .ext-linha{grid-column:1/-1;border:1px solid var(--border-sutil);
                 border-left:3px dashed var(--border-forte);border-radius:7px}
  .gc .ext-vaga > .nada{display:none}
  .gc .ext-linha{display:flex;align-items:center;gap:11px;
                 min-height:30px;padding:4px 12px;
                 font-size:12px;color:var(--texto-mudo);
                 border-top:1px solid var(--border-sutil);
                 border-left:3px dashed var(--border-forte)}
  .gc .ext-nome{color:var(--fg);font-weight:600;white-space:nowrap;
                flex:0 0 var(--larg-nome)}
  .gc .ext-via{flex:1;font-size:11.5px}
  .gc .ext-aviso{color:var(--orange);font-size:11.5px;text-align:right}

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

  /* ================= os cartões da Gestão de Controles =================
     A-08-O-CHECKUP-ABSORVE-A-GESTAO-01, 25/09/2026 — o desenho de quem
     coordena, depois de ela ver o acordeão com a Gestão dentro do Check-up:
     *«tá quebradíssima a 8»*. A linha que abria e fechava virou UM CARTÃO POR
     LUGAR, os quatro lado a lado — a mesa desta aba é de quatro —, e nada mais
     abre nem fecha: o que era o corpo escondido fica à vista. O rádio `gc-*`
     continua sendo o ALVO de saída (a fita e o cartão marcado), e só isso.
     A gramática é a da aba Sistema que ela aprovou: rótulo à esquerda, valor
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
  /* UMA LINHA SÓ — 26/09/2026, pedido dela com a janela maximizada: *«colocar
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
  .gc-dono::placeholder{color:var(--texto-mudo);font-weight:400}
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
  /* OS SEIS SELOS, UM POR LINHA. O selo é do produto
     (`a08_conexoes.selo_do_estado`: o rótulo, o valor em `<b>` e o ✓ em
     `<i class="certo">`), e a linha só o arruma: o rótulo à esquerda e o que
     vier depois dele empurrado para a direita. */
  .gc-resumo{display:flex;flex-direction:column;border-top:1px solid var(--border-sutil)}
  .gc-est{display:block;border-bottom:1px solid var(--border-sutil)}
  .gc-est .est{display:flex;align-items:center;gap:6px;height:25.5px;min-width:0;
               font-size:12px;color:var(--texto-mudo);white-space:nowrap}
  .gc-est .est > b{margin-left:auto;min-width:0;overflow:hidden;text-overflow:ellipsis;
                   color:var(--fg);font-weight:600}
  .gc-est .est > .certo{margin-left:auto;font-style:normal;font-weight:700;color:var(--green)}
  .gc-est .est > b + .certo{margin-left:0}
  .gc-est .est.warn > b{color:var(--orange)}
  .gc-corpo{display:flex;flex-direction:column;gap:5px;margin-top:auto;padding-top:10px}
  /* O PERFIL DE DESEMPENHO É DO CONTROLE — 26/09/2026, pedido dela: *«Modo
     Economia de Bateria Deveria Ser o Perfil de Desempenho»* e *«perfil do
     desempenho deveria aparecer por controle»*. Os três botões do mapa das
     conexões desceram para cada cartão; o aceso é o deste controle. */
  .gc-perfil{display:flex;flex-direction:column;gap:5px}
  .gc-perfil .rot{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--texto-mudo)}
  /* CADA BOTÃO COM A LARGURA DA PALAVRA DELE, E A SOBRA REPARTIDA — medido
     em 26/09/2026 (A-GESTAO-DOS-CONTROLES-NO-PRODUTO-01): com três colunas
     iguais, «Bateria Longa» e «Personalizado» perdiam 7 a 8 px no tamanho do
     desenho (1212 px) e viravam reticências. Com `flex:1 1 auto` a 11px os
     três cabem a partir de 1181 px, a menor janela com quatro cartões numa
     fileira (abaixo dela a grade vira duas e o cartão alarga). Os nomes dela
     de 26/09 («Perfil Máximo», «Perfil Econômico») pedem 246 px numa linha de
     245: o vão de 2 px, 1 px de respiro e a letra 0,2 px mais junta devolvem
     os 15 que faltavam. */
  .gc-perfil .seg{display:flex;flex-wrap:nowrap;gap:2px}
  /* `min-width:0` porque o `.btn` do esqueleto nasce com 150px, e três de 150
     não cabem num cartão de 350. */
  .gc-perfil .seg .btn{flex:1 1 auto;width:auto;min-width:0;height:26px;padding:0 1px;font-size:11px;
                       letter-spacing:-.2px;
                       white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .gc-perfil .seg .btn.on{border-color:var(--purple);background:rgba(189,147,249,.16);
                          color:var(--fg);font-weight:600}
  /* «A LUZ NÃO ACENDE» VIROU BOTÃO — 26/09/2026, pedido dela: *«A luz não
     acende isso deveria ser um botão»*. Era link pontilhado.
     O TEXTO ABAIXO É DE 25/09. «A LUZ NÃO ACENDE» ERA UM LINK DISCRETO, e não um botão do tamanho da
     economia: é o conserto de um caso raro. A trava continua IRMÃ e colada
     antes do botão (`></i><button`), porque o `~` só alcança irmãos
     posteriores — é ela que o apaga no cabo, onde o gesto não vale. */
  .gc-corpo .gc-luz{display:flex;flex-direction:column;align-items:center;gap:4px;min-width:0}
  .gc-luz .ressalva{margin-top:0;text-align:center}
  .gc-corpo .gc-luz{align-items:stretch}
  .gc-luz .btn{width:100%;height:26px;display:flex;align-items:center;justify-content:center;gap:7px}
  /* OS BOTÕES MAIS BAIXOS — 26/09/2026, com a janela maximizada: *«diminuir a
     altura dos botões»*. 26 px no perfil e na luz, 28 px nas quatro
     ferramentas (o esqueleto dá 34). */
  .gc-luz .btn .i{width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:1.8;
                  stroke-linecap:round;stroke-linejoin:round}
  .gc-corpo .ltrava{display:none}
  .gc-corpo .ltrava.on ~ .btn{opacity:.55;cursor:help}
  .gc-corpo .ltrava.on ~ .btn:hover{color:var(--texto-mudo)}
  /* REGRA DELA: *"sempre visível mas só
     acionável quando tiver no rádio"* — botão que SOME ensina que a tela é
     instável. */
  .btn.apagado{border-color:var(--border-forte);color:var(--texto-mudo);
               opacity:.55;cursor:help}
  .btn.apagado:hover{border-color:var(--border-forte);color:var(--texto-mudo)}
  /* o SVG real ganha a barra de luz acesa, PREENCHIDA (um contorno de 1,2 numa
     forma de 2px pinta menos de um pixel). As lâmpadas de jogador saem do
     desenho pequeno por `svg(..., lampadas=False)`, decisão dela de 28/08. */
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
  .mp-fatos dt{color:var(--texto-mudo);padding-right:16px}
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
  .mp-lista li span{margin-left:auto;color:var(--texto-mudo);white-space:nowrap;
                    overflow:hidden;text-overflow:ellipsis}
  .mp-lista li.vazio{color:var(--texto-mudo)}
  .mp-conta{margin:0;font-size:11.5px;color:var(--texto-mudo)}
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
  .tab .mudo{color:var(--texto-mudo)}
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
  .viz .qual{font-size:10.5px;color:var(--texto-mudo);white-space:nowrap;overflow:hidden;
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
  .viz .onde{font-size:10.5px;color:var(--texto-mudo);white-space:nowrap;overflow:hidden;
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
  .mm-ap code{font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--texto-mudo)}
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
  .mm-ligado{font-size:10px;color:var(--texto-mudo);line-height:1.4;padding-left:2px}
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
  .mm-c.mm-vazia{color:var(--texto-mudo);font-style:italic}
  .mm-ext{font-size:8.5px;color:var(--comment)}
  .mm-v{font-size:9px;font-weight:600}
  /* AS CINCO CORES SÃO OS CINCO ESTADOS QUE **ESTA** JANELA PRODUZ. Os três do
     modo ideal (`chega`, `sai`, `fica`) não entram: eles vêm do plano, e esta
     janela não calcula plano nenhum. */
  .mm-sq[data-v="cheia"]{opacity:.72}
  .mm-sq[data-v="cheia"] .mm-v{color:var(--texto-mudo)}
  .mm-sq[data-v="serve"]{border-color:var(--comment)}
  .mm-sq[data-v="serve"] .mm-v{color:var(--comment)}
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
     ELA SAIU DO CORPO E VIROU DICA — decisão dela, 29/08/2026, e é a
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
                 color:var(--texto-mudo)}
  .mm-conf-linha b{font-weight:600;color:var(--texto-suave)}
  .mm-conf-linha span{cursor:help;border-bottom:1px dotted var(--border-forte)}
  /* A LINHA SOME QUANDO NÃO HÁ O QUE CONFESSAR — 03/09/2026, e a regra é a da
     janela do desenho: lá `confissao_do_desenho` devolve vazio e nada é
     desenhado. Quem acende esta classe é o produto, pelo `confissao-nada`; no
     arquivo aberto no navegador ela nunca está ligada, porque a cena tem
     lacuna. Sem esta regra, uma mesa sem lacuna leria "…: nada." — texto que
     ocupa a linha para não dizer nada. */
  .mm-conf-linha.sumido{display:none}

  /* ---- os gestos de baixo. `.apagado` deixou de ser só da Gestão de Controles:
     os dois botões de ação desta pop-up nascem apagados pela mesma regra dela —
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
  .mm-campo::placeholder{color:var(--texto-mudo)}
  .mm-aplicar{margin:11px 0 0}
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
  .ce-quem code{font-family:'JetBrains Mono',monospace;font-size:10.5px;color:var(--texto-mudo)}
  /* OS LUGARES CABEM NUMA LINHA SÓ — 31/08/2026, e ela mandou com a foto na mão:
     *"botões em duas linhas. deveria ser uma."*

     A causa era `flex-wrap:wrap` com botões do tamanho do próprio texto: some a
     largura dos quatro (`Frente do gabinete` é 40% maior que `Em cima da mesa`)
     e, no dia em que a soma passa da caixa, o último cai sozinho para a segunda
     linha. Depende da FONTE que carregou — por isso a foto dela mostrava duas
     linhas e o Chrome headless mostrava uma: com fallback mais estreito, cabia.
     Régua nenhuma pegaria isso; só o olho dela, na máquina dela.

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
  .ce-relogios{font-size:10.5px;color:var(--texto-mudo);line-height:1.55;margin-top:13px}
"""


LARG_NOME = 220
CSS += (f"\n  .gc-cabeca,\n"
        f"  .gc .ext-linha{{--larg-nome:{LARG_NOME}px}}\n")

ESTADOS = ["todos"] + [c["pref"] for c in MESA]

_regras = [
    "  /* o destaque estático da fita perde para o do acordeão: `.fita .chip.on`",
    "     tem especificidade maior que o `.chip.on` do esqueleto, e é ele que",
    "     apaga o chip que nasceu marcado no HTML. */",
    "  .fita .chip.on{background:var(--app-bg);color:var(--texto-mudo);font-weight:400;"
    "border-color:var(--border-forte)}",
    "  .fita .chip.plastico.on{border-color:var(--plastico,var(--border-forte))}",
    "  /* O CARTÃO QUE A FITA APONTA ganha a borda roxa da escolha, a mesma do",
    "     chip. Em «Todos» nenhum cartão se destaca: todos são o alvo. */",
]
for estado in ESTADOS:
    marcado = f"body:has(#gc-{estado}:checked)"
    chips = [f'{marcado} .fita .chip[data-pref="{estado}"]']
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
    color:var(--texto-mudo);text-decoration:none;white-space:nowrap}
  .porta:hover{color:var(--cyan);text-decoration:underline}
"""


VER_IGNORADAS = "Ver as ordens ignoradas"

ORDEM_IGNORADA_VOLTA = _pacote08.ORDEM_IGNORADA_VOLTA


MAPEAR_ENTRADAS = "Mapear entradas"
MAPEAR_UMA_A_UMA = "Mapear Entrada a Entrada"

EXAMINAR_PORTAS = "Examinar entradas"

RENOMEAR_DICA = _pacote08.RENOMEAR_DICA


#: contrato. O `validar-acentuacao.py` isenta a LINHA que traga `noqa-acento`, e
BORDA_LIDA = ("A borda é a cor do plástico que o Hefesto <b>leu do aparelho</b>: este controle "
              "está no cabo, e pelo cabo ele pergunta e o aparelho responde.")
BORDA_NEUTRA = ("A borda é <b>neutra</b> porque a cor deste controle <b>não foi lida</b>. "
                "Uma borda colorida aqui seria uma cor que ninguém leu — e o desenho "
                "continua na cor que o resto do Hefesto já conhece.")

LUZ_NO_CABO = ("Só funciona com o controle no BT. Este está no USB, onde a barra de luz "
               "não depende de reconexão.")
LUZ_NO_RADIO = ("Desliga este controle do BT. Aperte PS para ele voltar, e a barra de luz "
                "volta a obedecer.")

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


def teto_dica(c):
    """A frase do `?` do teto — desenho de bancada, REPINTADA pelo pacote."""
    return _aba_conexoes.dica_do_teto(_vibracao_da_bancada(c))


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
    """O rótulo do lugar sem aparelho: nenhum (desenho aprovado de 05/10/2026, só o «P N»)."""
    return ""


#: 26/09/2026; a bateria foi para o nome (`nome_com_a_bateria`).
ESTADOS_DA_LINHA = ("est-mic", "est-som", "est-modo", "est-visto")
DONO_DA_CENA = {"p1": "Vitória"}
PERFIL_DA_CENA = {"p1": "tudo_ligado", "p2": "bateria_longa"}
from hefesto_dualsense4unix.app.actions.config import secao_orcamento as _orc  # noqa: E402

PERFIS_DO_CARTAO = tuple((p, _orc.ROTULOS_DOS_PERFIS[p], _orc.DICAS_DO_CARTAO[p])
                         for p in _orc.PERFIS)


def botao_do_perfil(pid, rotulo, dica, aceso):
    """Um dos três botões: o produto acende o do controle pelo endereço `perfil`"""
    return (f'<button class="btn{" on" if aceso else ""}" data-gesto="perfil-do-controle" '
            f'value="{pid}" role="radio" aria-checked="{"true" if aceso else "false"}" '
            f'data-campo="perfil" data-hef-alvo="classe" data-hef-classe="on" '
            f'data-hef-quando="{pid}" data-hef-atributo="aria-checked" '
            f'title="{dica}">{rotulo}</button>')
DONO_DICA = ("Escreva o nome de quem joga com este controle. O nome fica no controle: "
             "vale em qualquer entrada e adaptador. Apague para voltar a «P N».")
from types import SimpleNamespace  # noqa: E402

_DECLARACAO_DA_BANCADA = SimpleNamespace(controles={}, orcamento=SimpleNamespace(teto=None))
DICAS_DA_CENA = _dicas_da_cena()


def _estado_da_bancada(c):
    """Os seis selos da cena, pelo MESMO dono que o produto chama a cada tique."""
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
    luz sai do produto, o rótulo sai da ordem dela, a máscara e a bateria saem
    da aba Controles, e o transporte decide o que a linha pode prometer.

    UMA FUNÇÃO SÓ PARA OS QUATRO LUGARES — 07/09/2026, e os dois ramos que
    havia aqui eram o defeito. O lugar VAZIO tinha marcação própria, sem um
    `data-campo` por dentro; `conectado` agora decide DUAS coisas, e só elas:

      a) a classe e o atributo do cartão (`off` + `data-conectado="nao"`);
      b) o TEXTO INICIAL de cada campo — o travessão no lugar do valor.

    A ESTRUTURA É A MESMA NOS QUATRO, e é isso que cura o defeito. Medido em
    07/09/2026 com os quatro DualSense dela na mesa: o daemon publicava quatro,
    a carga chegava com `colunas = ['p1','p2','p3','p4']` e os quatro em
    `ocupados`, e a tela mostrava DOIS. O passo 2 do piloto
    (`hefesto_vivo.pintar`) procura `data-campo="k"` DENTRO do bloco
    `[data-controle="pN"]`; sem endereço, o dado dela chega e não tem onde
    pousar. O `data-controle` do lugar vazio nasceu em 03/09 — decisão dela,
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
    trava = (f'<i class="ltrava{"" if (no_radio or not conectado) else " on"}" '
             f'data-campo="luz-trava" '
             f'data-hef-alvo="classe" '
             f'data-hef-quando="{_pacote08.LUZ_TRAVADA}"></i>')
    dica_luz = ('data-campo="luz-dica" data-hef-alvo="atributo" '
                'data-hef-atributo="title"')
    rotulo_luz = (f'<span data-campo="luz-texto">'
                  f'{vale(_pacote08.texto_do_botao_da_luz())}</span>')
    botao = (f'<button class="btn" data-gesto="luz-nao-acende" {dica_luz} '
             f'title="{vale(LUZ_NO_RADIO if no_radio else LUZ_NO_CABO)}">'
             f'<svg class="i" aria-hidden="true"><use href="#rd-lampada"/></svg>'
             f'{rotulo_luz}</button>')
    # a COR do jogador nesta função (`player_slot_color`), e ela entra no
    bloco_da_luz = (f'<span class="gc-luz">{monta_ressalva("luz-espera")}'
                    f'{trava}{botao}</span>')
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
                       value="{vale(DONO_DA_CENA.get(c["pref"], ""), "")}" placeholder="Nome de quem joga" maxlength="24" spellcheck="false"
                       aria-label="Nome de quem joga com este controle" title="{DONO_DICA}">
                <span class="gc-nome" data-campo="nome" data-hef-alvo="html"{dica_da_borda}>{vale(_pacote08.nome_com_a_bateria(_pacote08.rotulo_curto_do_controle(c), DA_CONTROLES[c["pref"]]["bat"]), nome_do_lugar_vazio(c))}</span>
              </div>
            </div>
            <div class="gc-resumo">
{chr(10).join(f'              <span class="gc-est" data-campo="{k}" data-hef-alvo="html">{estado.get(k, TRAVESSAO)}</span>' for k in ESTADOS_DA_LINHA)}
            </div>
            <div class="gc-corpo">
              <div class="gc-perfil">
                <div class="seg" role="radiogroup" aria-label="Perfil de Desempenho">
{chr(10).join('                  ' + botao_do_perfil(pid, rotulo, dica, PERFIL_DA_CENA.get(c["pref"], "tudo_ligado") == pid) for pid, rotulo, dica in PERFIS_DO_CARTAO)}
                </div>
              </div>
              {bloco_da_luz}
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
V_OCUPADA = "ocupada"
V_INDISPONIVEL = "indisponível"
V_SERVE = "serve"
V_EVITAR = "vale evitar"
V_MELHOR = "melhor lugar"
P_TIRAR = "clique para tirar"
P_EXTENSOR = "o extensor está nela"
P_SERVE = "entrada direta, mas na altura da escrivaninha"
P_MELHOR = "na ponta do extensor: a antena mais longe das outras"
P_COLADA = "colada no {tipo}, na entrada {n}"
_confere_no_produto(_JULGAR, [
    f'"{V_OCUPADA}", f"{{tipo}} — {P_TIRAR}"', f'"{V_INDISPONIVEL}"',
    f'"{P_EXTENSOR}"', f'Veredito("serve", "{V_SERVE}", "{P_SERVE}")',
    f'"{V_EVITAR}", colada', f'"{V_MELHOR}"', f'"{P_MELHOR}"',
    'f"colada no {vizinho.tipo}, na entrada {entrada.par}"',
])

def _virgula(n):
    from hefesto_dualsense4unix.app.fala_do_mapa import formata_pt_br

    return formata_pt_br(n)


OS_DOIS_RELOGIOS = (
    f"A entrada aparece para mim em ~{_virgula(CALIB['SEGUNDOS_ATE_O_NO'])} s. "
    f"O controle só consegue vibrar por volta de "
    f"{_virgula(CALIB['SEGUNDOS_ATE_A_VIBRACAO'][0])} a "
    f"{_virgula(CALIB['SEGUNDOS_ATE_A_VIBRACAO'][1])} s — e essa demora é uma "
    "correção que o próprio Hefesto instala para ele não falhar. Não é você, e "
    "não é o seu cabo.")
_confere_no_produto(
    R / "src/hefesto_dualsense4unix/interface/calibracao_das_entradas.py",
    ["A entrada aparece para mim em ~", "Não é você, e não é o "])


def ajuda(txt, largura=""):
    st = f' style="width:{largura}"' if largura else ""
    return f'<span class="ajuda">?<span class="dica"{st}>{txt}</span></span>'


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
        return "cheia", V_INDISPONIVEL, P_EXTENSOR
    vizinho = QUEM_ESTA.get(PARES.get(n, ""))
    if vizinho and vizinho[0] in ("Bluetooth", "Teclado", "Mouse"):
        return "evite", V_EVITAR, P_COLADA.format(tipo=vizinho[0], n=PARES[n])
    if esticada:
        return "melhor", V_MELHOR, P_MELHOR
    return "serve", V_SERVE, P_SERVE


#:   · `especie`   — os dois DualSense por cabo saem sem classe no motor.
LACUNAS = ["LACUNA_POSICAO", "LACUNA_VELOCIDADE", "LACUNA_ESPECIE"]


_CONFISSAO_ITENS = [f"· {MAPA['CONFISSAO'][k]}" for k in LACUNAS]
CONFISSAO_EM_DICA = ("<b>" + html.escape(MAPA["CONFISSAO_ABERTURA"]) + "</b><br>"
                     + "<br>".join(html.escape(i) for i in _CONFISSAO_ITENS))

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


def face_dos_hubs():
    """A terceira face: o que não é buraco do gabinete."""
    if not EXTENSAO:
        return ""
    celulas = "".join(
        f'<div class="mm-cel">{quadrado(filha, esticada=True)}'
        f'<span class="mm-ligado">ligado na entrada <b>{mae}</b>'
        f' <span class="mudo">· {FACE_DA_ENTRADA[mae]}</span></span></div>'
        for mae, filha in EXTENSAO.items())
    return f'''            <div class="mm-face">
              <div class="mm-face-cab"><span class="mm-face-nome">Hubs e extensões</span>
                <button class="btn mini" data-gesto="novo-hub" title="{_aba_conexoes.DICA_NOVO_HUB}">Acrescentar hub</button></div>
              <div class="mm-grade mm-grade-hubs">{celulas}</div>
            </div>'''


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
           "nova_entrada": _aba_conexoes.DICA_NOVA_ENTRADA,
           "novo_hub": _aba_conexoes.DICA_NOVO_HUB})


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
    desta dica, porque a seção dele não tem onde mais dizê-la. Aqui a frase já
    está na tela, por extenso, no rodapé desta janelinha (`GRAVA_NO_CLIQUE`, e
    é `.mm-aplicar` no desenho) — repeti-la no hover seria a mesma frase duas
    vezes na mesma caixa. **NÃO É `ESPERA_O_APLICAR`**, que este docstring
    nomeava até 06/09/2026: aquela é a irmã dela, a da janela GTK que espera o
    "Aplicar", e esta tela grava no clique desde 01/09.

    O ENDEREÇO DA PINTURA CHEGOU EM 03/09/2026 (`MIGRA-08-01`), e ele cura uma
    tela que MENTIA: o `maquina.json` desta bancada diz
    `linha_de_visada='com_gente'`, e os TRÊS botões da visada estavam apagados —
    a tela dizendo que ninguém respondeu uma pergunta respondida. O "Sim" da
    ALTURA acertava por coincidência do mockup, que é pior: um acerto que não
    vem de leitura erra no primeiro clique dela.

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
      <span class="tn-tit">{MAPEAR_ENTRADAS}</span>
      {ajuda(
        "O gesto tem <b>dois tempos</b>: clique no aparelho, depois na entrada em que ele "
        "está. Um aparelho fica em <b>um</b> lugar — pôr onde ele não estava o tira de onde "
        "estava, no mesmo gesto.<br><br>"
        "Enquanto há um aparelho escolhido, <b>todo quadrado publica o juízo</b> para "
        "<i>ele</i>: sem sujeito a pergunta “aqui serve?” não existe, e a tela cala.<br><br>"
        "As duas perguntas do fim <b>mudaram-se da aba para cá</b> em 28/08, e aqui elas "
        "preenchem um vazio real: esta janela não guardava um único fato que só você tem. "
        "<b>Sem resposta</b> não é o mesmo que <b>“Não sei”</b>.<br><br>"
        + CONFISSAO_EM_DICA)}
      <a class="tn-x" href="#" title="Fechar">×</a>
    </div>
    <div class="tn-corpo">
      <div class="tn-frase">{MAPA["EXPLICACAO"]}</div>
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
             TROCAR o miolo inteiro: as faces e as entradas são as que ELA
             declarou, e o número delas muda. Um bloco cujo número de filhos
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
        <button class="btn apagado" data-gesto="tirar-daqui" title="Acende quando você clica numa entrada que TEM aparelho. Ele escreve “sem aparelho” nessa entrada — a entrada continua no desenho, só fica vazia.">{MAPA["ROTULO_TIRAR"]}</button>
        <button class="btn apagado" data-gesto="nova-extensao" title="Acende quando você clica numa entrada cujo número é só dígito. Cria a filha dela — a 10 vira 10a, depois 10b. Não há neta.">{MAPA["ROTULO_EXTENSAO"]}</button>
        <span class="mm-nova"><input class="mm-campo" placeholder="{MAPA["NOME_DA_FACE_EM_BRANCO"]}" maxlength="16">
          <button class="btn" data-gesto="nova-face" title="Cria uma face com o nome que você escreveu, sem entrada nenhuma. Sem nome, não cria.">{MAPA["ROTULO_NOVA_FACE"]}</button></span>
      </div>
      <div class="tn-frase mm-aplicar">{MAPA["GRAVA_NO_CLIQUE"]}</div>
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
                dentro.append(f"{_escopo(sel)}{{{decl.strip()}}}")
            saida.append(f"{cabeca}{{{''.join(dentro)}}}")
        elif cabeca == "body":
            continue
        elif cabeca == ".quadro":
            saida.append(".quadro.radio{position:relative;z-index:0}")
        else:
            saida.append(f"{_escopo(cabeca)}{{{' '.join(miolo.split())}}}")
    return "\n  ".join(saida)


CSS_DA_SECAO_DO_RADIO = _css_do_radio() + """
  .radio .btn{height:auto;padding-top:7px;padding-bottom:7px}
  .radio .btn.so-icone{padding:7px}
  .radio .painel .escolha{height:auto}
  .radio .porta{margin-left:0;line-height:normal;font-size:inherit;text-decoration:none;
                white-space:normal}
  .radio .porta:hover{text-decoration:none}
  .radio .marca{color:inherit}
  .radio .espectro-cab .ajuda{line-height:normal;text-align:center;flex:none;position:static}
  .radio .quadro-topo.cab{margin-bottom:0}
  .radio .quadro-topo.cab .conta{margin-left:4px}
  .radio .lugar:not(.aberto) > .aparelhos{display:none}
  .radio .sala-vazia{color:var(--texto-mudo);font-size:12.5px;padding:10px 4px}
  .radio .moldes{display:none}
  .radio .btn.apagado{cursor:not-allowed;border-color:var(--border-sutil);color:var(--texto-mudo)}
  .radio .historico{display:flex;flex-direction:column;gap:6px}
  .radio .queda-desde{font-size:11px;color:var(--texto-mudo);padding:2px 4px}
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
  .radio .lugar{padding-top:0;padding-bottom:0;min-height:0}
  .radio .lugar-topo{min-height:26px}
  .radio .lugar-nome,.radio .abre-lugar{height:24px;padding-top:0;padding-bottom:0}
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
                          background:transparent;color:var(--texto-mudo);cursor:pointer;font-size:12px}
  .radio .linha .menu-da-linha{font-size:15px;line-height:1}
  .radio .linha .xis:hover,.radio .linha .menu-da-linha:hover{border-color:var(--orange);
                          color:var(--orange)}
  .radio .linha .xis:focus-visible,.radio .linha .menu-da-linha:focus-visible{
                          outline:2px solid var(--purple);outline-offset:2px}
  .radio .linha .nome-fixo{font-size:12.5px;color:var(--texto-suave);overflow:hidden;
                           text-overflow:ellipsis}
  .radio .linha .features .desligado{color:var(--texto-mudo);font-size:11.5px}
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
  .radio .espectro{--c-controle:#7eb8d4;--c-wifi:#c3e88d;--c-teclado:#ffb86c;--c-mouse:#f1fa8c;
                 --c-celular:#f78c6c;--c-relogio:#82aaff;--c-ruido:#8a8fa8;--c-fone:#8be9fd;
                 --c-caixa:#bd93f9;--c-outro:#9a9eb8;--vazio:#1b1c24}
  .radio .ar{display:flex;flex-direction:column;gap:7px}
  .radio .ar-grupo{display:flex;align-items:center;gap:8px;font-size:12px;
                   color:var(--texto-mudo);margin-top:6px;padding-top:6px;
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
  /* a faixa sem leitura é o trilho vazio, igual ao dos outros; só o passo do «Descobrir» fala */
  .radio .ar-faixa.sem{display:flex;align-items:center;font-size:11px;color:var(--texto-mudo);
                       background:repeating-linear-gradient(90deg,var(--vazio) 0 9px,transparent 9px 11px)}
  .radio .ar-estado{display:flex;align-items:center;justify-content:center;width:12px}
  /* o estado é um ponto: verde = bom, vermelho = problema, vazado = faixa sem leitura */
  .radio .ar-selo{display:inline-block;box-sizing:border-box;width:10px;height:10px;padding:0;
                  border-radius:50%;border:0;background:var(--orange);box-shadow:0 0 0 3px rgba(255,184,108,.2)}
  .radio .ar-selo.sofrendo{background:var(--red);box-shadow:0 0 0 3px rgba(255,85,85,.2)}
  .radio .ar-selo.boa{background:var(--green);box-shadow:none}
  .radio .ar-selo.sem{background:transparent;box-shadow:none;border:2px solid var(--comment)}
  .radio .ar-selo.sem.apertada{border-color:var(--orange)}
  .radio .ar-selo.sofrendo.sem{border-color:var(--red)}
  /* o controle conhecido que pede para parear: o ponto verde que pulsa (05/10/2026) */
  .cd-pulso,.radio .ar-pulso{display:inline-block;width:10px;height:10px;border-radius:50%;
             background:var(--green);box-shadow:0 0 0 0 rgba(80,250,123,.55);
             animation:pulso-pede 1.4s infinite}
  .radio .ar-pulso{margin-left:7px;vertical-align:middle}
  @keyframes pulso-pede{70%{box-shadow:0 0 0 8px rgba(80,250,123,0)}
                        100%{box-shadow:0 0 0 0 rgba(80,250,123,0)}}
  @media (prefers-reduced-motion:reduce){.cd-pulso,.radio .ar-pulso{animation:none}}
  .radio button.ar-selo{cursor:pointer;min-height:0;height:10px}
  .radio button.ar-selo.sem:hover{border-color:var(--green)}
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
     Freestyle» da aba Jogar, com os valores DELA (`aba01.py`, a folha
     `.cadeado`), copiados e presos pela régua do interruptor — sem importar
     de outra aba. No painel, ela fica à direita do título. */
  .radio .cadeado{display:inline-flex;align-items:center;justify-content:center;gap:7px;
           margin-left:auto;height:26px;flex:0 0 auto;white-space:nowrap;
           border-radius:7px;padding:0 12px;font-size:12.5px;font-family:inherit;
           cursor:pointer;
           border:1px solid var(--border-forte);background:var(--app-bg);
           color:var(--texto-mudo)}
  .radio .cadeado .p{width:7px;height:7px;border-radius:50%;flex:0 0 auto;
              background:var(--border-forte);box-shadow:none}
  .radio .cadeado.ligada{border-color:var(--green);background:rgba(80,250,123,.09);
                  color:var(--green)}
  .radio .cadeado.ligada .p{background:var(--green);box-shadow:0 0 6px var(--green)}
"""


#: Os dois tipos que a régua ganhou e o desenho do rádio não tinha: o celular e o relógio.
SIMBOLOS_DAS_FAIXAS = (
    '  <symbol id="rd-celular" viewBox="0 0 24 24"><rect x="7" y="2" width="10" height="20" '
    'rx="2"/><path d="M11 18h2"/></symbol>\n'
    '  <symbol id="rd-relogio" viewBox="0 0 24 24"><rect x="7" y="7" width="10" height="10" '
    'rx="3"/><path d="M9 7l1-5h4l1 5M9 17l1 5h4l1-5"/></symbol>')


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
            "id": linha["id"], "tipo": linha["a"], "lugar": linha["c"], "nome": linha["nome"],
            "rotulo": f"Player {i + 1}" if linha["a"] == "controle" else linha["nome"],
            "cor": linha["b"], "cor_nome": linha["g"],
            "mic": "mic" in ligado, "luz": "luz" in ligado, "fixo": "fixo" in ligado,
            "ponte": ("haptica" if "vib" in ligado else "som" if "ponte" in ligado else None),
            "som": float(linha["d"] or 0), "esperando": False, "alem": False,
        })
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
    # O celular e o relógio que o BlueZ também lista no adaptador cheio (o desenho 1), e o teclado
    # que o «Descobrir» já mediu (o mouse ainda não): as duas formas de um receptor.
    aparelhos += [
        {"id": f"celular-{cheio['id']}", "tipo": "celular", "lugar": cheio["id"],
         "nome": "Celular", "rotulo": "Celular", "esperando": False, "fixo": False},
        {"id": f"relogio-{cheio['id']}", "tipo": "relogio", "lugar": cheio["id"],
         "nome": "Relógio", "rotulo": "Relógio", "esperando": False, "fixo": False}]
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
        "canais_medidos": {lg["id"]: True for lg in lugares},
        "vizinhos": vizinhos, "wifi": wifi, "portas": portas, "pedido": None,
        "proposta": {"controle": quem_sai["id"], "destino": vazio["id"]},
        "ocupado": False, "aberto": None, "perto": perto,
        "destino_do_conectar": vazio["id"],
        "pedindo": [dict(PEDIDO_DO_DESENHO)],
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

ENCAIXE_CURTO = "Encaixe o DualSense numa entrada vazia."

AJUDA_DO_AR = ("Cada linha é um aparelho, nos mesmos 79 canais. Pintado é o canal bom; o vazio "
               "é o canal perdido, e a marca embaixo é a cor de quem briga ali. Passe o mouse "
               "numa linha: acendem ela e quem briga com ela.")  # noqa-acento (texto de tela)

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
    // O que a pessoa aponta (a linha sob o mouse ou com o foco) e o tipo que ela escolheu na
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
    // Com UMA caixa só ela fica aberta (decisão dela, 25/09): o pacote nem
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
    // ---- a caixa aberta põe a faixa em foco nela: só os aparelhos dela, sem o título ----
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
      document.getElementById('rd-veu').classList.add('aberto');
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
      document.getElementById('rd-veu').classList.remove('aberto');
      if(quemAbriu && document.contains(quemAbriu)) quemAbriu.focus();
      quemAbriu = null;
    }
    document.addEventListener('keydown', function(ev){
      if(ev.key === 'Escape'){ fecharAPergunta(); fecharPainel(); }
    });
    document.addEventListener('click', function(ev){
      if(perto(ev, '#rd-fechar') || perto(ev, '#rd-veu')){ fecharPainel(); return; }
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
    // AS DICAS (AS-DICAS-SAO-CARTOES-COM-UM-GESTO-01): o ⓘ abre o porquê do cartão, e o botão
    // de mover abre a MESMA pergunta de todo mover (o molde é o do balão da lâmpada).
    document.addEventListener('click', function(ev){
      var info = perto(ev, '.dicas .cd-info');
      todos('.dicas .cd-info[aria-expanded="true"]').forEach(function(x){
        if(x === info || perto(ev, '.cd-porque')) return;
        x.setAttribute('aria-expanded', 'false');
        var p = document.getElementById(x.getAttribute('aria-controls')); if(p) p.hidden = true;
      });
      if(info){
        var aberto = info.getAttribute('aria-expanded') === 'true';
        info.setAttribute('aria-expanded', aberto ? 'false' : 'true');
        var porque = document.getElementById(info.getAttribute('aria-controls'));
        if(porque) porque.hidden = aberto;
        return;
      }
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

    // ---- ARRASTAR AS CAIXAS: a ordem é dela, e fica gravada ----
    // Decisão dela, 25/09/2026: ela segura a linha de cima de um adaptador e
    // arrasta para mudar a ordem (a frase dela está no `adaptador_reordenar` do
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
      <span class="tn-tit">{MAPEAR_ENTRADAS}</span>
      {ajuda("Use o mesmo DualSense em todas: ligue o cabo numa entrada, espere o Hefesto "
             "mostrar o que mediu dela e salve; o <b>nome</b> e o <b>lugar</b> são opcionais. "
             "Depois passe o cabo para a próxima. O nome e o lugar aparecem na "
             "<b>Gestão de Controles</b> e em <b>Rádio e Adaptadores</b>.")}
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
PROGRESSO = "entrada {feitos} de {total}"

SEM_LUGAR = [(esp, no) for esp, no, em, _q in CENSO if not em]

VAGAS_NO_DESENHO = (sum(len(ns) for _n, ns in FACES) + len(EXTENSAO)
                    - len(ONDE_ESTA))
CONECTORES_QUE_NINGUEM_ALCANCA = 2
EM_PE_TOTAL = VAGAS_NO_DESENHO + CONECTORES_QUE_NINGUEM_ALCANCA

#: `portao_a_casa_sabe_e_o_produto_nao_faz.py:1188`. A frase já está no `title`
#: e sem chamador, e a lápide do `portao_a_casa_sabe_e_o_produto_nao_faz.py:1188`
PENEIRA_QUANDO_ELA_EXISTIR = (
    "Enquanto esta janela estiver na frente, o que você apertar no "
    "controle fica <b>aqui</b> — não chega ao jogo aberto atrás.")
PENEIRA = ""


def cerimonia(ident, pergunta, contador, quem, botoes, dica, rodape):
    """Uma das três telas do «Mapear Entrada a Entrada»."""
    return f'''
<div class="tela-nova" id="{ident}">
  <div class="tn-cx">
    <div class="tn-topo">
      <span class="tn-tit">{MAPEAR_UMA_A_UMA}</span>
      {ajuda(dica)}
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
        <p class="ce-relogios">{OS_DOIS_RELOGIOS}</p>
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
    PROGRESSO.format(feitos=1, total=len(SEM_LUGAR))
    + f' <span class="pt">·</span> {CALIB["SEM_SAIR_DA_CADEIRA"]}',
    f'{SEM_LUGAR[0][0]} <span class="pt">·</span> <code>{SEM_LUGAR[0][1]}</code>',
    "".join(
        f'<button class="btn{" foco" if i == 0 else ""}" data-gesto="entrada-face" '
        f'value="{f}" title="Cria uma entrada nesta face para este aparelho e para o que '
        f'estiver pendurado nele. Gravado na hora.">{f}</button>'
        for i, f in enumerate(CALIB["FACES"])),
    "A pergunta é sobre a <b>entrada</b>, não sobre o aparelho: mesmo quando o kernel "
    "não diz o que é a coisa, você sabe em que buraco ela está.<br><br>"
    "O rótulo é <b>espécie · nome do kernel</b>. O caminho fica à vista porque é a única "
    "coisa que distingue dois aparelhos idênticos.",
    f'<button class="btn" data-gesto="entrada-pular" title="Pula esta entrada, sem gravar '
    f'nada e sem perguntar de novo.">{CALIB["ROTULO_NAO_SEI"]}</button>\n      {JA_CHEGA}')

TELA_FIM = cerimonia(
    "mapear-entrada-a-entrada-fim",
    CALIB["FIM_DA_FASE_SENTADA"],
    "",
    CALIB["CONVITE_EM_PE"],
    f'<button class="btn foco" data-gesto="entrada-levantar" title="Guarda a leitura '
    f'de agora como referência e entra na fase em pé. É a única porta para ela.">'
    f'{CALIB["ROTULO_VOU_MOSTRAR"]}</button>'
    f'<a class="btn" href="#" data-gesto="entrada-parar" title="Fecha a janela. Mesmo destino do “{CALIB["ROTULO_JA_CHEGA"]}”.">'
    f'{CALIB["ROTULO_DEIXAR_PARA_DEPOIS"]}</a>',
    "É um <b>fim de verdade</b>: sem aviso de incompletude, sem selo de pendência, sem "
    "cartaz. O contador some, porque não há mais o que contar nesta fase.<br><br>"
    "Quem já tem lugar para tudo <b>abre a janela direto aqui</b>.",
    JA_CHEGA)

TELA_EM_PE = cerimonia(
    "mapear-entrada-a-entrada-em-pe",
    ENCAIXE_CURTO,
    PROGRESSO.format(feitos=1, total=EM_PE_TOTAL),
    CALIB["PROCURANDO"],
    f'<button class="btn foco" data-gesto="entrada-nao-alcanco" title="Tira esta entrada da '
    f'conta de vez: não vira dívida, não vira aviso, e o Hefesto não volta a perguntar. Ela '
    f'diminui o TOTAL do contador, não o feito.">{CALIB["ROTULO_NAO_ALCANCO"]}</button>',
    CALIB["CONVITE_DO_ENCAIXE"] + "<br><br>"
    "Aqui a face <b>não se pergunta</b>: toda entrada aprendida de pé é gravada em "
    "<b>{}</b>. O total <b>encolhe</b> — ele é recalculado pela leitura de agora, "
    "e “{}” tira uma vaga da conta.".format(CALIB["FACES"][1], CALIB["ROTULO_NAO_ALCANCO"]),
    JA_CHEGA)


CSS += CSS_DA_SECAO_DO_RADIO

MIOLO = f'''
    <!-- ======== A TABELA DAS CORES DELA, uma vez para a página inteira ========
         Os 28 modelos e as 10 zonas de `docs/data/cores-do-dualsense.csv`, com a
         hachura e os dois gradientes que oito deles usam — o
         `<defs id="cores-do-dualsense">` inteiro, lido do `ds_limpo.svg` por
         `_a_tabela_dos_28`. Ele morava DENTRO de cada desenho e vinha PODADO
         (só o modelo que o mockup escolheu), e uma tabela podada não tem como
         virar outro modelo: o alvo de atributo escreveria `white` e a casca
         continuaria caindo no cinza cru do desenho.
         O `<svg>` mede ZERO e não desenha nada — ele existe porque `<pattern>` e
         `<linearGradient>` só valem dentro de um fragmento SVG. Não muda um
         pixel do que ela aprovou. ======== -->
{TABELA_DAS_CORES}

    <!-- ======== 1. CHECK-UP — juízo à esquerda, conserto à direita ========
         SUBIU PARA PRIMEIRO E MUDOU DE NOME — 30/08/2026, pedido dela:
         *"a parte 'Está tudo certo' aparece como primeiro bloco na página e
         mudamos o nome pra Check-up"*. Faz sentido de leitura: quem abre a
         Conexões quer primeiro saber se há algo errado, e só depois a lista
         de quem está na mesa. E "Check-up" é substantivo — nomeia a seção;
         "Está tudo certo?" era pergunta, e título que pergunta faz a pessoa
         procurar a resposta em vez de ler o que está embaixo. ======== -->
    <div class="quadro">
      <!-- SÓ O CHECK-UP NASCE ABERTO — 30/08/2026, pedido dela: *"inicia as
           demais abas de gestão e rádio minimizadas"*. Faz sentido de uso: quem
           abre a Conexões quer primeiro saber se há algo errado; a lista da mesa
           e o inventário de rádios são consulta, não alerta. E resolve, de
           quebra, os 208px que o quadro de baixo perdia por não caber. -->
      <!-- ABRIR UMA MINIMIZA AS OUTRAS — 31/08/2026, pedido dela: *"abrir uma
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
        <label class="quadro-titulo" for="cx8-2">Gestão de Controles</label>
        <span class="ajuda">?<span class="dica">
          Os seus controles e as entradas deles: as dicas em cima, cada uma com o seu botão,
          e embaixo um cartão por controle com o estado dele agora e o Perfil de Desempenho
          dele. Nada muda sozinho: a dica diz o que mover para onde, e o botão leva você até lá.
        </span></span>
      </div>
      <div class="quadro-corpo">
        <!-- A LINHA DE VEREDITO SAIU — 26/09/2026, pedido dela com a janela
             maximizada: *«precisamos ganhar espaço vertical. vamos remover a
             linha 3 mudanças recomendadas»*. Revoga a D-16 de 04/09 («Uma
             linha de veredito no topo»): a Sugestão de Conexão ao lado já
             numera cada mudança, e a contagem repetia a caixa. -->
        <!-- AS DICAS SÃO CARTÕES COM UM GESTO — 04/10/2026, AS-DICAS-SAO-CARTOES-COM-UM-GESTO-01
             (o desenho 4 que ela aprovou). O exame de cinco frases e a «Sugestão de Conexão»
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
             entradas, como ela mandou.

             `Ignorar` mora no ⓘ de cada cartão de dica (04/10/2026), e a ordem calada
             fica no fim, apagada, com o botão «Voltar a mostrar». E `{VER_IGNORADAS}`
             saiu com o glifo de cada linha (31/08), que era onde o gesto tinha sujeito. -->
        <!-- AS FERRAMENTAS MORAM NO CHECK-UP — 25/09/2026, pedido dela
             (A-08-O-CHECKUP-ABSORVE-A-GESTAO-01). O «Mapear Entradas» é UM botão
             só: a âncora abre o fluxo guiado porta a porta (`#mapear-portas`),
             que chama o dono do mapa (`entrada_a_entrada.o_mapa()`). A âncora
             não é gesto (a §P4): quem começa o fluxo é o `#mp-comecar`. -->
        <!-- QUATRO FERRAMENTAS, TODAS COM ÍCONE — 26/09/2026, pedido dela: *«não
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

             O ALVO É `marcado`, o décimo do pintor (decisão dela em 04/09,
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
               · `home_actions.texto_native_bt_fragil` — o Modo Nativo com o
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

               DENTRO DO `.gc`, POR ESCOLHA DELA — 06/09/2026, olhando as duas
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
        </div>
        <!-- 05/10/2026, o desenho aprovado: as quatro ferramentas descem para baixo dos cartões. -->
        <div class="ferramentas">
          <a class="btn" href="#mapear-portas" title="{MAPEAR_ENTRADAS} — ligue o DualSense em cada entrada, uma por vez; o nome e o lugar são opcionais">
            <svg class="i" aria-hidden="true"><use href="#rd-mapa"/></svg> {MAPEAR_ENTRADAS}</a>
          <button class="btn" data-gesto="examinar-portas" title="{EXAMINAR_PORTAS} — refaz o exame das entradas, da energia e do Bluetooth, e relê o estado de cada controle">
            <svg class="i" aria-hidden="true"><use href="#rd-reexaminar"/></svg> {EXAMINAR_PORTAS}</button>
          <a class="btn" href="mapa-do-controle.html" title="O mapa do controle — abre no navegador">
            <svg class="i ds" aria-hidden="true"><use href="#rd-ds"/></svg> Mapa do Controle</a>
          <a class="btn" href="mapa-das-portas.html" title="O mapa das conexões: cada entrada do computador, o que está nela e o que mudar">
            <svg class="i" aria-hidden="true"><use href="#rd-hub"/></svg> Mapa das Conexões</a>
        </div>
      </div>
    </div>

    <!-- ======== 3. RÁDIO E ADAPTADORES — o `mapa-do-radio.html` aprovado ========
         TRANSPLANTE-DA-SECAO-01, 23/09/2026. A seção inteira é o desenho que
         ela aprovou; a folha, o sprite e a cena de exemplo são LIDOS dele
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
        <label class="quadro-titulo" for="cx8-3">Rádio e Adaptadores</label>
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
            Dispositivos conectados
            <span class="ajuda" role="img" aria-label="{AJUDA_DO_AR}" title="{AJUDA_DO_AR}"><svg class="i" aria-hidden="true"><use href="#rd-ajuda"/></svg></span>
            {LEGENDA_DAS_FAIXAS}
          </div>
          <div class="pistas" data-campo="espectro-canais" data-hef-alvo="html">{CAMPOS_DO_RADIO["espectro-canais"]}</div>
        </div>

        <div class="sala" data-campo="radio-sala" data-hef-alvo="html">{SALA_DO_DESENHO}</div>
        <button hidden id="rd-reordenar" data-gesto="adaptador-reordenar" value=""></button>
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
        <div class="veu" id="rd-veu"></div>
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
{SCRIPT_DA_SECAO_DO_RADIO}
{SCRIPT_DAS_FAIXAS}
<script>
/* O PERFIL DE DESEMPENHO ACENDE NO CLIQUE — 26/09/2026, SÓ NA BANCADA. No
   produto (onde o piloto pôs `window.__hef`) quem acende é o tique, pelo que
   o daemon gravou: um clique recusado não pode ficar aceso. */
document.addEventListener("click", function (ev) {{
  if (window.__hef) return;
  var b = ev.target.closest(".gc-perfil .seg .btn");
  if (!b) return;
  b.parentElement.querySelectorAll(".btn").forEach(function (x) {{
    x.classList.toggle("on", x === b);
    x.setAttribute("aria-checked", x === b ? "true" : "false");
  }});
}});
</script>
'''

LEGENDA = f'''<div class="nota">
  <h2>A Gestão de Controles (25/09 e 26/09)</h2>
  <ul>
    <li><b>Uma seção só</b>: as <b>dicas</b> (um cartão por ajuste, com o botão dele; as três que mais pesam, o resto em «mais N») em cima, quatro ferramentas com ícone no meio (o «Atualizar» entrou no «{EXAMINAR_PORTAS}»; o <b>{MAPEAR_ENTRADAS}</b> abre o fluxo porta a porta) e um cartão por controle embaixo.</li>
    <li><b>O cartão diz o estado de agora</b>, no molde da aba Sistema: Mic, Som, Modo de conexão, Visto como, Conexão e Bateria, com o ✓ de «tudo certo». Nada abre nem fecha.</li>
    <li><b>O nome ao lado do «P N» é de quem joga</b>: escreva; apagado, o campo volta vazio. Embaixo, o <b>Perfil de Desempenho</b> daquele controle (Perfil Máximo, Perfil Econômico ou Personalizado), o mesmo dado da aba Sistema. O lugar sem controle fica, tracejado, só com o «P N».</li>
    <li><b>{MAPEAR_ENTRADAS}</b> abre uma tela com o que o Hefesto mediu da entrada da vez, o nome e o lugar que você dá, e a lista das que já têm nome.</li>
  </ul>
  <h2>«Rádio e Adaptadores» é o desenho que você aprovou em 23/09 — e o que ficou diferente</h2>
  <ul>
    <li><b>A seção inteira é o <code>mapa-do-radio.html</code></b>: a folha, os ícones e esta cena de exemplo são lidos dele. No produto quem pinta é o Hefesto, com os Hz medidos, as pontes «N de {_pacote08.PONTES_POR_ADAPTADOR}» e o sino de cada adaptador.</li>
    <li><b>Os vizinhos viraram selos, e não faixas.</b> O produto não lê o canal de um teclado ou de um Wi-Fi; desenhar a faixa seria estimar (R10). O hachurado — os canais que cada adaptador evita — é medido e continua.</li>
    <li><b>Caixa e fone não mostram Hz</b>: o contador mede os controles. A vaga deles fica, com a cor e o ícone.</li>
    <li><b>A fase em pé diz uma frase só</b>: «{ENCAIXE_CURTO}» (R9). A explicação longa foi para o «?».</li>
    <li><b>A tabela dos adaptadores, a régua de turnos e as linhas «hub em comum» e «contagens do gabinete» saíram</b> com a seção velha. O nome do adaptador é o campo do cartão, e ele é o nome da ENTRADA.</li>
  </ul>
  <h2>As duas janelas do gabinete entraram na tela — e o que elas NÃO fazem</h2>
  <ul>
    <li><b>Os dois botões abrem agora, e o que abre não é tela nova.</b> <b>{MAPEAR_ENTRADAS}</b> é a janela <code>mapa_da_mesa.py</code> e <b>{MAPEAR_UMA_A_UMA}</b> é a <code>calibrar_entradas.py</code>, as duas já rodando. <b>Todo texto delas sai do produto, lido por AST</b> — a mesma disciplina dos sete números do rádio. O que o AST não alcança (o veredito de cada entrada, os dois relógios, as três dicas de botão) tem portão: a geração <b>para</b> se a frase deixar de existir no fonte.</li>
    <li><b>A cena é o SEU gabinete, e é a ordem de serviço desta aba sendo cumprida.</b> O aparelho na mão é o adaptador <b>“{ADAPTADORES[0]["nome"]}”</b>, que o exame manda tirar da <b>Entrada 3</b> — e com ele escolhido cada quadrado publica o juízo <i>para ele</i>. Os cinco estados da tela são os cinco que a janela sabe produzir: <b>ocupada</b>, <b>indisponível</b>, <b>serve</b>, <b>vale evitar</b> e <b>melhor lugar</b>. Os três do modo ideal (<i>chega</i>, <i>sai</i>, <i>fica</i>) <b>não entram</b>: vêm do plano, e esta janela não calcula plano nenhum.</li>
    <li><b>Nenhum plug é azul, e a própria tela diz por quê.</b> A velocidade vem dos nós declarados, e quem os escreve é a OUTRA janela — logo toda entrada desenhada aqui sai <code>usb=2</code>. Pintar azul contradiria a confissão três blocos abaixo. <b>Mas repare a tensão</b>: o exame desta aba afirma que a Entrada 3 é <b>USB 3.0</b> e a 9 é <b>2.0</b>. As duas telas são honestas cada uma no seu canto, e o produto ainda não junta o que já sabe.</li>
    <li><b>Um nome não batia, e agora bate — no produto.</b> A confissão da velocidade mandava você a “Calibrar as entradas”, que era o título da outra janela no código; o botão desta aba chama-se <b>{MAPEAR_UMA_A_UMA}</b> desde 28/08. Até 05/09 a tela CORRIGIA a frase do produto ao gerar; agora os três lugares dizem o mesmo nome (<code>calibrar_entradas.TITULO_DA_JANELA</code>, <code>mapa_da_mesa.CONFISSAO</code> e <code>secao_mesa._BOTAO_CALIBRAR</code>) e a remenda saiu. <b>Uma tela que corrige uma frase já certa é uma segunda verdade esperando para divergir.</b></li>
    <li><b>As duas perguntas da sala chegaram, e vieram inteiras</b> — pergunta, dica e as três opções, literais de onde moravam. A da altura está respondida e a da visada não, de propósito: <b>sem resposta não é “Não sei”</b>, e a tela precisa mostrar os dois. <b>O preço, escrito:</b> elas gravam sob <code>mesa</code> e o desenho grava sob <code>mapa</code> — chaves com disciplinas diferentes (substituição num, fusão no outro). É trabalho de código, não de desenho, e a sprint que as implementar tem de saber disto.</li>
    <li><b>A cerimônia são TRÊS telas, ligadas pelos próprios botões dela</b>: a pergunta sentada, o fim da parte sem levantar, e a fase em pé. Custa só HTML e não mente sobre transição nenhuma — a webcam é o único aparelho sem lugar, então responder <i>aquela</i> pergunta leva mesmo ao fim.</li>
    <li><b>A frase do jogo aberto está amarrada ao FOCO, e ela é ESPECIFICAÇÃO.</b> A tela diz <i>“enquanto esta janela estiver na frente”</i>, e não “enquanto estiver aberta”, porque é no foco que a janela toma o controle. <b>Hoje o produto não faz isso</b>: a peneira está escrita e não tem quem a chame — é lápide viva do portão da casa. A frase depende da <code>ONDA-CONEXOES-10</code>. Por isso também <b>nenhum glifo de X/O/D-pad</b> acompanha: hoje o botão não anda na janela <i>e</i> chega ao jogo.</li>
  </ul>

  <h2>O que eu desenhei de cabeça, e por que — derrube qualquer um numa frase</h2>
  <ul>
    <li><b>A lista de aparelhos ficou EM CIMA, e no produto ela é a coluna da esquerda.</b> A conta é fria: o quadrado do produto tem <b>84&nbsp;px</b> e a fileira tem <b>sete colunas fixas</b> — 7×84 mais os vãos pedem <b>618&nbsp;px</b>, e a caixa oferece <b>624</b> por dentro. Lado a lado com uma coluna de lista, o quadrado cairia para ~56&nbsp;px e as linhas de texto dele parariam de caber. Empilhada, a fileira do produto cabe inteira.</li>
    <li><b>Os dois botões de ação nascem APAGADOS, e é o estado certo desta cena.</b> Eles só acendem com uma entrada em foco, e a janela <b>não tem realce nenhum de foco</b> — só os dois botões contam a história. Desenhá-los acesos seria desenhar um estado que ninguém consegue ver. As dicas dizem quando cada um acende. <b>Isto é defeito do produto</b>, não escolha de desenho.</li>
    <li><b>O quadrado cresce em altura quando o texto pede</b>, e “Aparelho de entrada” pede. O <code>84×56</code> do produto é <i>mínimo</i>, não teto — em GTK ele cresce igual.</li>
    <li><b>A pop-up do desenho bate no teto de 717&nbsp;px e rola por dentro</b> (mostra 478 de 658, esconde 180). É o padrão da casa, e o topo com o título e o rodapé com o <b>{MAPA["ROTULO_FECHAR"]}</b> ficam sempre à vista. <b>A janela GTK de verdade NÃO rola</b> — 720×520 num <code>Gtk.Box</code> puro, sem <code>ScrolledWindow</code> em lugar nenhum: com este conteúdo, o que sobra fica fora e ninguém avisa. É defeito a consertar, e o mockup já mostra a cura.</li>
    <li><b>“entrada 1 de 1” conta APARELHO, não entrada</b> — e a palavra é do produto. Um passo de hub coloca vários aparelhos de uma vez, e mesmo assim o contador diz “entrada”. Fica registrado; a redação é da <code>CONFIGURACOES-O-LEXICO-01</code>.</li>
    <li><b>Um aparelho aparece como “Aparelho de entrada”, e não como “DualSense”.</b> O censo classifica pela <i>interface 0</i>, e o próprio produto escreve que o DualSense por cabo é <code>03/00/00</code> — classe de entrada sem protocolo de arranque. Não inventei o rótulo: é o que a tela mostraria. E é ele que acende a terceira linha da confissão.</li>
    <li><b>A ordem da confissão é minha, e no produto ela é SORTEADA.</b> As lacunas vivem num <code>set</code>, e um <code>set</code> de textos não tem ordem estável entre execuções: as mesmas três linhas saem em ordens diferentes a cada abertura. A tela as mostra na ordem em que o produto as declara. <b>É defeito, e é de uma linha.</b></li>
  </ul>

  <h2>MODO não é MÁSCARA, e nada nesta tela diz que você perde o microfone</h2>
  <ul>
    <li><b>O microfone segue o TRANSPORTE, e a máscara não o toca.</b> Pelo cabo o DualSense expõe uma placa USB Audio própria e o PipeWire a publica sozinho (medido em 15/08/2026: duas placas ALSA, ~475.000 amostras não-zero cada). Pelo rádio não existe placa nenhuma — o aparelho não anuncia A2DP, HFP nem HSP —, e o áudio vem em Opus <i>dentro</i> do relatório HID 0x31: quem o traz é a ponte do Hefesto, que publica uma fonte de captura do PipeWire. <b>No rádio o microfone já é emulado hoje</b>, com outro nome.</li>
    <li><b>Por isso a chavinha “pelo cabo / pelo rádio” SAIU.</b> Ela oferecia uma escolha que o transporte já tinha feito — e o próprio mockup se contradizia: o gerador já derivava o caminho do transporte e desenhava a chavinha ao lado. Ponto final dela, 28/08: <i>“se tiver em modo rádio, então o mic é modo rádio”</i>. O custo do microfone virou <b>consequência</b>, e a tela o mostra em Hz na linha de cada controle, em «Rádio e Adaptadores», em vez de perguntar por ele.</li>
    <li><b>Nenhum aviso de máscara, em máscara nenhuma</b> — e o motivo é mais forte do que “o Pro só não tem microfone”. A máscara limita o que o <b>jogo</b> recebe, não o que o <b>controle</b> faz: o Hefesto continua acendendo a barra de luz, aplicando o gatilho e lendo o giro do DualSense físico em qualquer máscara. E a lacuna mais visível — o mic — tem cura: o estado <b>Emulado</b> da <code>ONDA-CONEXOES-06</code> entrega o áudio por um dispositivo que qualquer jogo enxerga, independentemente da máscara.</li>
    <li><b>Nativo e Emulado desceram de escolha para LEITURA.</b> Com o transporte explícito e a máscara explícita por controle (aba Jogar), o resultado fica determinado: cabo → a placa do próprio aparelho; rádio → a ponte. Sobraram <b>dois estados</b> — Ligado e Desligado —, e a tela <b>diz</b> o caminho em vez de perguntá-lo. O “Automático” não entra: a heurística que o moveria (<code>integrations/api_de_entrada.py</code>) errou em <b>13 de 14</b> dos jogos dela.</li>
  </ul>

  <h2>Um número desta tela estava ERRADO pelo dobro, e nenhuma régua o via</h2>
  <ul>
    <li><b>A dica do teto dizia que “Bateria longa” corta a força em 60%. O produto corta em {fala_do_teto(COM_TETO)}.</b> O degrau tem um dono só — <code>RUMBLE_POLICY_MULT["{COM_TETO}"]</code> —, e é dele que o <code>secao_orcamento</code> deriva a frase, com o cuidado escrito no próprio arquivo: <i>“escrever «30%» à mão nesta tela”</i> é o que ele existe para evitar. Aqui o 60 estava digitado. Agora é lido por AST, como os sete números do rádio já eram — <b>oito literais a menos</b>.</li>
    <li><b>A máscara e a bateria da linha fechada não são digitadas aqui, e nem no mesmo lugar.</b> A bateria vem do <code>ESTADO</code> da aba <b>Controles</b>, lido por AST — não por <code>import</code>, que <i>executaria</i> o gerador da outra aba e reescreveria o HTML dela. A máscara vem da <code>monta.MESA</code>, que virou o dono único dela em 28/08: o P2 aparece como <b>{POR_PREF["p2"]["mascara"]}</b> aqui, na Jogar e na Controles porque é o mesmo dado, não porque três listas concordam — e elas não concordavam.</li>
  </ul>

  <h2>O acordeão, em CSS puro — e o que ele não consegue</h2>
  <ul>
    <li><b>Zero JavaScript.</b> O mockup inteiro não tem uma linha de script, e o cruzamento do mapa do controle já é feito só com <code>:has()</code>. Aqui a peça é um grupo de <code>&lt;input type=radio&gt;</code> escondido: cada linha fechada é um <code>&lt;label&gt;</code> que marca o seu. Por ser rádio, <b>marcar um desmarca os outros</b> — que é, ao pé da letra, “clicar num abre e fecha os outros”.</li>
    <li><b>Clicar numa linha muda a fita, de verdade.</b> As {len(ESTADOS)} regras que repintam os chips são geradas da <code>MESA</code> e casam <b>pelo número do jogador</b> (<code>data-pref</code>) — nem pelo texto do chip, que já mudou uma vez e matou a fita viva em silêncio, nem pela posição, que com o P1 fora acendia o vizinho (<code>A-GESTAO-SEGUE-O-JOGADOR-01</code>).</li>
    <li><b>“Todos abre os {len(MESA)}” existe, e o chip da fita passou a clicar.</b> Ele era um <code>&lt;span&gt;</code> do esqueleto e virou <code>&lt;label&gt;</code> com endereço em 05/09/2026 (<code>monta.fita()</code>), nas três abas que escolhem controle — clicar nele muda o alvo desta aba. O gesto da própria linha <b>aberta</b> continua: clicar nela volta para “Todos”, com os {len(MESA)} abertos, e o <code>title</code> diz isso.</li>
    <li><b>No estado “Todos” a seta de abrir virou a palavra <code>só este</code>.</b> As {len(MESA)} linhas mostravam <b>▾</b> com a dica <i>“Abre este controle”</i> — {len(MESA)} setas de abrir sobre {len(MESA)} linhas já abertas, e a dica mentia duas vezes: a linha estava aberta, e o que o clique faz ali é <b>fechar as outras</b>. A dica do corpo da linha também mudou, e agora é a mesma nos dois estados — <i>“deixa só este controle aberto, os outros fecham”</i> é verdade tanto na linha fechada quanto nas {len(MESA)} abertas. <b>Foi preciso</b>: <code>title</code> não muda com CSS, então uma frase que só vale num estado mente no outro. A coluna da seta ficou com <b>largura fixa</b> pela mesma razão que as colunas do resumo: se ela mudasse de tamanho ao clicar, os {len(MESA)} percentuais de bateria andariam de lado juntos.</li>
  </ul>

  <h2>O que saiu, e o que cada saída pagou</h2>
  <ul>
    <li><b>“Microfone e botões” saiu do quadro e entrou nas linhas dos controles</b> — <b>86&nbsp;px</b> com a margem da sub-seção. Os dois campos que valiam para a máquina inteira agora são de cada controle, que é onde a pergunta tem resposta: o botão do mic é <i>daquele</i> aparelho.</li>
    <li><b>“Botões do controle externo” saiu da tela.</b> Nintendo e 8BitDo estão fora do escopo agora, por decisão dela — vira sprint. Nada substituiu o campo.</li>
    <li><b>“O que só você sabe” saiu, e ele não paga nada</b>: a coluna tinha <b>110&nbsp;px</b> de conteúdo contra <b>150</b> da coluna do exame, que é quem manda na altura do quadro. As duas perguntas foram para o <b>{MAPEAR_ENTRADAS}</b> — e lá elas preenchem um vazio real: hoje a janela do desenho cria face com <code>perto=False, alto=False</code> e <b>não tem um único gesto</b> que mude os dois; ela não guarda nenhum fato que só você tem.</li>
    <li><b>O dropdown de cor saiu das linhas dos controles.</b> Quem o produto lê aparece na borda; quem ele não lê fica com <b>borda neutra, e está dito</b> — no “?” do quadro e no <code>title</code> da linha. Os {len(NO_RADIO)} controles no rádio são os de borda neutra, porque o Hefesto <b>ainda não pergunta a cor pelo rádio</b> (<code>ONDA-CONEXOES-11</code>).</li>
    <li><b>A moldura dos {len(MESA)} cartões saiu, e ela pagava {Q_GESTAO_ANTES - Q_GESTAO}&nbsp;px.</b> Quatro bordas de 2&nbsp;px mais os 27 de vão entre eles somavam mais altura do que uma linha inteira de controle — e não mostravam nada. <b>A cor lida não se perdeu:</b> ela virou a barra de 3&nbsp;px na aresta esquerda de cada linha, que é a mesma promessa e agora cai numa coluna só, alinhada nas {len(MESA)} — mais fácil de comparar do que {len(MESA)} retângulos soltos.</li>
    <li><b>As lâmpadas de jogador saíram dos desenhos pequenos.</b> Neste tamanho elas medem 1,0 × 0,33&nbsp;px — tinta que ninguém vê. A barra de luz ficou, e ela é a cor do <i>jogador</i>.</li>
  </ul>

  <h2>O teto da vibração está nos dois, e a tela diz qual vale</h2>
  <ul>
    <li><b>O global vale para todos os controles, e ele MUDOU DE ABA.</b> O dropdown dos três perfis saiu daqui e foi para a <b>{ABA_DO_TETO_GLOBAL}</b>, onde se chama <b>{CASA_DO_TETO_GLOBAL}</b> — palavra dela, 28/08: <i>“Teto da Vibração, que na verdade é Perfil de Bateria”</i>. O código já lhe dava razão antes do nome: <code>secao_orcamento.py:97</code> chama a chave de <code>PERFIL_BATERIA_LONGA</code>, e a <code>D-PERFIL-DE-DESEMPENHO</code> (24/08) diz que <i>“o perfil decide o que custa BATERIA”</i>. Esta aba continua <b>lendo</b> o global — hoje <b>{ORC["ROTULOS_DOS_PERFIS"][PERFIL_DA_MESA]}</b>, que é <b>{TETO_GLOBAL}</b> —, e o que fica dela é a régua de turnos, que mede o <b>rádio</b>, não a bateria.</li>
    <li><b>O do controle sobrepõe</b>, e o campo de cada linha mostra qual é o caso: o P{POR_PREF["p3"]["jogador"]} está com a bateria em {DA_CONTROLES["p3"]["bat"]}% e sobrepõe com <b>{fala_do_teto(COM_TETO)}</b>; os outros dizem <b>{SEGUE_O_GLOBAL}</b>. A conta feita — <b>qual dos dois está valendo, de onde ele veio, e em que aba o global se muda</b> — está no <code>?</code> ao lado do campo, e não mais numa coluna de texto ao lado dele.</li>
    <li><b>Isso nasce como sprint sobre o que já existe.</b> A <code>POR-UNIDADE-01</code> (10/08) já grava política de vibração POR CONTROLE (<code>profiles/manager._controllers_to_rumble_scales</code>), relativa à global. <b>Falta uma frase sua:</b> quando o controle sobrepõe, ele vence sempre, ou o produto aplica o <code>min</code> como faz hoje entre o orçamento e a política? O <code>min</code> é o que impede um “teto” de <i>aumentar</i> a força.</li>
  </ul>

  <h2>Escolhas que precisam do seu aval</h2>
  <ul>
    <li><b>A ordem dos quadros mudou, e é a mudança que devolveu o terceiro para a tela.</b> “Gestão de Controles” passou a vir <b>primeiro</b>, e “Está tudo certo?” desceu para junto de “Rádio e adaptadores”. Duas razões: a aritmética (só quem está acima decide quanto do de baixo aparece, e não havia arranjo com o exame na frente em que o terceiro coubesse), e a leitura — o exame fala da <b>Entrada 3</b>, e a tabela que diz o que está na Entrada 3 agora é a de baixo, não a de outro lugar.</li>
    <li><b>“Vale Sem teto, do global, abaixo” SAIU — e o desempate que esta linha pedia deixou de existir.</b> Ela mandou tirar a leitura e deixar só o seletor (<code>D-O-SEM-TETO-SAI-DOS-DOIS-LUGARES</code>), e a frase saiu dos <b>dois</b> lugares em que estava: destas {len(MESA)} linhas de controle (o que ela via) e da capa do Desempenho (y=834, fora da dobra — o que casava letra por letra com o pedido, e que ela não podia ter visto). O <b>“abaixo”</b> caducou de qualquer jeito, por uma segunda razão independente: com o teto global mudando-se para a <b>{ABA_DO_TETO_GLOBAL}</b>, o endereço que a frase dava aponta para um lugar que não existe mais nesta aba. <b>A frase não se perdeu</b> — ela vive no <code>?</code> do campo, que a lê sob demanda em vez de gastar uma coluna nas {len(MESA)} linhas. E o desempate que este item pedia (“o teto global morar na mesma moldura dos {len(MESA)} tetos de controle”, por {H_ESCOLHA + 9}&nbsp;px) está <b>respondido</b>: o global saiu da aba inteira, e não custa px nenhum aqui.</li>
    <li><b>Os quatro botões viraram UMA fileira, e ela custou zero.</b> Você escreveu a ordem com todas as letras — <i>“Examinar de novo. / Já Movi - Reexaminar. / Ignorar / Ver Ordens ignoradas.”</i> — e com um par em cada coluna essa ordem não existe: a leitura de uma grade de duas colunas é esquerda→direita, e “Ignorar” (que estava à direita) teria de vir antes de “{VER_IGNORADAS}” (que estava à esquerda). <b>Medido:</b> o quadro tinha 204&nbsp;px e continua com {Q_EXAME}; a fileira nasce no mesmo y=575; os quatro botões passaram de 265,5 para <b>272&nbsp;px cada</b>, todos iguais, e a borda direita não andou um pixel.</li>
    <li><b>“Ver as ordens caladas” virou “{VER_IGNORADAS}”, e o motivo é o PAR.</b> O botão irmão chama-se <b>Ignorar</b>: quem o aperta procura depois as ordens <i>ignoradas</i>. “Caladas” era a única palavra da dupla sem par na tela. <b>Uma diferença para a sua frase:</b> você escreveu “Ver Ordens ignoradas” e a tela diz “Ver <u>as</u> ordens ignoradas” — o artigo é o que já estava lá, e só a última palavra mudou. Se você quiser a sua frase ao pé da letra, é <b>uma</b> palavra a menos.</li>
    <li><b>O gesto de voltar para “Todos” está na própria linha aberta</b>, e o chip da fita também volta: ele clica desde 05/09/2026, e o mesmo endereço vale nas três abas que escolhem controle.</li>
    <li><b>O resumo da linha fechada virou grade</b>: máscara, microfone e bateria repartem a linha em <code>126fr 272fr 76fr</code> — as três larguras <i>naturais</i> medidas, e não três números escolhidos. Assim as colunas caem no mesmo x nas {len(MESA)} linhas sozinhas, os percentuais terminam juntos, e o vão de 350&nbsp;px que sobrava entre o nome e um resumo encostado à direita desapareceu. É o mesmo remédio das quatro barras de bateria da aba Controles.</li>
    <li><b>Onde as declarações desta aba gravam?</b> Continua aberto, e agora com um caso concreto: o microfone é da <b>máquina</b> ou do <b>perfil</b>? A sua resposta de 28/08 foi <i>“nos dois: a máquina decide o padrão, o perfil sobrepõe”</i> — a tela ainda não mostra o recibo disso.</li>
    <li><b>Qual régua manda no arranjo</b> (<code>D-QUAL-REGUA-MANDA-NO-ARRANJO</code>) — a tela mostra a receita, que é o que o código tem; se o juízo por entrada vencer, o texto do imperativo muda.</li>
  </ul>
</div>

</body>
</html>
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
    TELAS = "\n".join(t.strip() for t in (TELA_MAPEAR, TELA_SENTADA, TELA_FIM, TELA_EM_PE,
                                             TELA_MAPEAR_PORTAS))
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

    _exigir('class="ext-linha"' not in _HTML,
            "uma linha de controle externo nasceu no desenho — a tela estaria "
            "afirmando um aparelho que ninguém mediu")

    _exigir(".quadro:has(> input.abre) .quadro-topo{padding-bottom:11px}" in _HTML,
            "o rótulo das seções que expandem perdeu o respiro de baixo — volta a "
            "1px contra os 12 de cima, que é o que ela viu nas duas fotos")

    _FORA = [c for c in MESA if not c.get("conectado", True)]
    _exigir("Desconectado</span>" not in _HTML,
            "o lugar vazio da Gestão voltou a dizer «Desconectado»: o desenho de 05/10 é só o «P N»")
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
