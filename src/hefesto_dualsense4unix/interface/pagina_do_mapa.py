#!/usr/bin/env python3
"""O gerador do `mapa-das-portas.html` — e por que ele nasce da origem congelada.

O DEFEITO QUE ELE FECHA, 11/09/2026
------------------------------------

A página dizia **"o arranjo de agora"** sobre um censo de **24/08/2026 cravado
em JavaScript**: oito aparelhos, três faces, um mapa e duas leituras digitados à
mão dentro do HTML, todos de UMA máquina. Quem abrisse o produto noutro
computador lia o gabinete de outra pessoa — e a ordem dela de 11/09/2026 é
justamente a contrária:

    "a ideia é que todas as features mesmo do app funcionem nao so pra  (noqa-acento)
     mim mas pra qualquer outro user"   — citação literal dela, 11/09/2026

E a página não tinha gerador: era o único HTML desta casa escrito à mão, e já
tinha divergido da origem congelada em treze pedaços sem ninguém ver.

DE ONDE ELA NASCE, e a escolha é o ponto inteiro
-------------------------------------------------

Este gerador **não escreve a página do zero**: ele LÊ a origem congelada
(:data:`ORIGEM`) e aplica as :data:`EDICOES`, uma a uma, cada uma com data e
motivo. A razão é que aquela origem não é um rascunho velho — é a
**especificação executável do motor**: `tests/fixtures/motor_do_arranjo_do_mockup.js`
extrai o `<script>` dela, roda 120 cenários em `node`, e o JSON que sai é o ouro
contra o qual o porte em Python é medido
(`tests/unit/test_arranjo_da_mesa_bate_com_o_mockup.py`).

Derivar dali torna a equivalência do motor **estrutural** em vez de declarada:
o que o produto renderiza É o motor da origem mais um conjunto de mudanças
nomeadas. Não há como as duas casas divergirem em silêncio, porque só existe
uma — a outra é calculada.

QUEM ESCREVE ONDE
------------------

    mockup/congelados/2026-08-24-mapa-das-portas.html
              │   congelada: o motor de 24/08, que produz o ouro
              │   `pagina_do_mapa.py`
    mockup/mapa-das-portas.html            ← a BANCADA, o que ela olha
              │   `check_o_desenho_aprovado.py --publicar mapa-das-portas.html`
    src/.../interface/paginas/mapa-das-portas.html   ← o que o produto renderiza

Uso::

    python3 -m hefesto_dualsense4unix.interface.pagina_do_mapa
"""

from __future__ import annotations

import json
import sys
from typing import Any, NamedTuple

from hefesto_dualsense4unix.integrations.entrada_a_entrada import LUGARES_DA_PORTA
from hefesto_dualsense4unix.interface import caixa_da_janela, onde
from hefesto_dualsense4unix.utils.rotulo_da_entrada import (
    FACE_DO_HUB_DECLARADO,
    MAXIMO_DO_NOME_DA_ENTRADA,
    PALAVRA_DA_ENTRADA,
    PALAVRA_NA_FRASE,
)

#: A ESPECIFICAÇÃO EXECUTÁVEL. Congelada por decisão: reescrevê-la reescreveria
#: o ouro de 120 cenários, e apagaria o registro de como o motor falava em
#: 24/08/2026 — que é o que aquela pasta datada é.
ORIGEM = (onde.RAIZ / "mockup" / "congelados" / "2026-08-24-mapa-das-portas.html")

#: Onde o gerador escreve. A BANCADA, nunca o publicado — o produto só recebe
#: pelo `--publicar`, que é ato dela (`interface/onde.py`).
DESTINO = onde.BANCADA / "mapa-das-portas.html"


class Edicao(NamedTuple):
    """Um pedaço em que a página do produto difere da origem congelada.

    ``antes`` tem de aparecer **exatamente uma vez** na origem: zero é edição
    que envelheceu (a frase mudou de lado e a declaração ficou apontando para o
    que não há), e duas é edição ambígua — as duas reprovam em voz alta, porque
    uma troca que erra o alvo calada é o defeito que este arquivo existe para
    matar.
    """

    antes: str
    depois: str
    porque: str


# ═══ O CENSO DE EXEMPLO ═══════════════════════════════════════════════════
#
# ELE SAIU DO JAVASCRIPT E VEIO PARA CÁ, e a mudança não é de arrumação: aqui
# ele tem UM dono, e a página passa a poder trocá-lo pelo censo de quem a abre
# (ver `ABRE_A_PORTA`, mais abaixo). Enquanto ninguém entrega leitura nenhuma, é
# este arranjo que a página desenha — e o cabeçalho diz que é exemplo, com a
# data, numa classe que a folha do produto não esconde.
#
# OS VALORES SÃO OS DA ORIGEM CONGELADA, byte a byte. Trocá-los por outros
# inventados custaria a comparação a olho entre esta página e o ouro, que é o
# que deixa qualquer pessoa conferir o motor sem rodar nada.

#: O rótulo do cabeçalho quando ninguém entregou leitura. Ele é DADO da página,
#: não bilhete de projeto — ver a edição `A_DATA_SOBREVIVE`.
QUANDO_DO_EXEMPLO = "leitura de exemplo · 24/08/2026"

CENSO_DE_EXEMPLO: dict[str, Any] = {
    "quando": QUANDO_DO_EXEMPLO,
    "aparelhos": [
        {"id": "bt-a", "tipo": "Bluetooth", "nome": "TP-Link UB500",
         "sementeDoCaminho": "3-1.2", "cor": "#bd93f9", "classe": "bt", "usb": 2, "mA": 500},
        {"id": "bt-b", "tipo": "Bluetooth", "nome": "TP-Link UB500",
         "sementeDoCaminho": "3-1.1.4", "cor": "#bd93f9", "classe": "bt", "usb": 2, "mA": 500},
        {"id": "bt-c", "tipo": "Bluetooth", "nome": "TP-Link UB500",
         "sementeDoCaminho": "3-3", "cor": "#bd93f9", "classe": "bt", "usb": 2, "mA": 500},
        {"id": "wifi", "tipo": "Wi-Fi", "nome": "Archer T3U",
         "sementeDoCaminho": "4-1.1.2", "cor": "#ff5555", "classe": "wifi", "usb": 3, "mA": 504},
        {"id": "webcam", "tipo": "Webcam", "nome": "Logitech C920",
         "sementeDoCaminho": "3-4", "cor": "#8be9fd", "classe": "webcam", "usb": 2, "mA": 500},
        {"id": "teclado", "tipo": "Teclado", "nome": "Receptor 2,4 GHz",
         "sementeDoCaminho": "3-1.4", "cor": "#ffb86c", "classe": "teclado", "usb": 2, "mA": 100},
        {"id": "mouse", "tipo": "Mouse", "nome": "Receptor 2,4 GHz",
         "sementeDoCaminho": "1-3", "cor": "#f1fa8c", "classe": "mouse", "usb": 2, "mA": 98},
        {"id": "hub", "tipo": "Hub", "nome": "TP-Link UH700",
         "sementeDoCaminho": "3-1", "cor": "#6272a4", "classe": "hub", "usb": 3, "mA": 100},
    ],
    "faces": [
        {"nome": "Frente do gabinete", "forma": "coluna", "perto": True, "regiao": "pc",
         "portas": [{"n": "1", "usb": 2, "onde": "pc", "par": "2"},
                    {"n": "2", "usb": 2, "onde": "pc", "par": "1"}]},
        {"nome": "Traseira", "forma": "grade-tras", "regiao": "pc", "donaDaFaixaPc": True,
         "portas": [{"n": "3", "usb": 3, "onde": "pc", "par": "4"},
                    {"n": "4", "usb": 3, "onde": "pc", "par": "3"},
                    {"n": "5", "usb": 3, "onde": "pc", "par": "6"},
                    {"n": "6", "usb": 3, "onde": "pc", "par": "5"},
                    {"n": "7", "usb": 2, "onde": "pc", "par": "8"},
                    {"n": "8", "usb": 2, "onde": "pc", "par": "7"}]},
        {"nome": "Hub, no alto do rack", "forma": "fileira", "alto": True, "regiao": "hub",
         "portas": [{"n": "9", "usb": 3, "onde": "hub", "pos": 1, "par": "10"},
                    {"n": "10", "usb": 3, "onde": "hub", "pos": 2, "par": "9"},
                    {"n": "11", "usb": 3, "onde": "hub", "pos": 3, "par": "12"},
                    {"n": "12", "usb": 3, "onde": "hub", "pos": 4, "par": "11"},
                    {"n": "13", "usb": 3, "onde": "hub", "pos": 5, "par": "14"},
                    {"n": "14", "usb": 3, "onde": "hub", "pos": 6, "par": "13"},
                    {"n": "15", "usb": 3, "onde": "hub", "pos": 7,
                     "filho": {"n": "15a", "usb": 3, "onde": "hub", "pos": 9,
                               "esticada": True,
                               "cabo": "extensor de 1 m, declarado por você"}}]},
    ],
    "mapa": {"1": "1-3", "4": "3-1", "5": "3-3", "6": "3-4",
             "9": "3-1.2", "11": "4-1.1.2", "13": "3-1.4", "15a": "3-1.1.4"},
    "leituras": {
        "antes": {"rotulo": "20h15 — antes de você mexer",
                  "caminho": {"mouse": "1-3", "hub": "3-1", "bt-c": "3-3", "webcam": "3-4",
                              "bt-a": "3-1.2", "wifi": "4-1.1.2", "teclado": "3-1.4",
                              "bt-b": "3-1.1.4"}},
        "agora": {"rotulo": "22h50 — depois dos seus movimentos",
                  "caminho": {"teclado": "1-3", "webcam": "1-4", "mouse": "1-6", "hub": "3-1",
                              "bt-c": "3-1.1.1", "bt-b": "3-1.1.4", "bt-a": "3-1.2",
                              "wifi": "4-2"}},
    },
    #: A FILEIRA DE CONTROLES É SIMULADOR, não leitura: os botões `1 2 3 4` ao
    #: lado dela existem para a pessoa perguntar *"e se fossem quatro?"*. Por
    #: isso ela NÃO vem no censo vivo — vem daqui, e o `controlesSobre` a
    #: espalha pelos adaptadores que a máquina de quem abre tiver.
    "controles": [
        {"nome": "Jogador 1", "mic": True, "onde": "bt-a"},
        {"nome": "Jogador 2", "mic": True, "onde": "bt-a"},
        {"nome": "Jogador 3", "mic": True, "onde": "bt-b"},
        {"nome": "Jogador 4", "mic": True, "onde": "bt-b"},
    ],
}

#: A COR DE CADA ESPÉCIE, DERIVADA DO EXEMPLO — nunca uma segunda tabela.
#:
#: O desenho pinta o chip de cada aparelho com `ap.cor`, e o arranjo vivo
#: precisa da mesma cor para o roxo do Bluetooth não virar dois roxos. Ela é
#: LIDA do censo acima em vez de digitada aqui: duas tabelas de cor divergem no
#: dia em que alguém trocar uma delas, e é a classe de defeito que esta casa
#: chama de segunda verdade.
CORES_POR_CLASSE: dict[str, str] = {
    str(a["classe"]): str(a["cor"]) for a in CENSO_DE_EXEMPLO["aparelhos"]
}

#: A COR DO TIPO QUE ELA DECLAROU (O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01): o tipo decide a cor
#: em todo o app, e as de teclado, mouse, Wi-Fi e caixa de som são as da régua da aba 08
#: (``aba08`` ``--c-<tipo>``). A webcam leva a da classe.
COR_POR_TIPO_DECLARADO: dict[str, str] = {
    "teclado": "#ffb86c", "mouse": "#f1fa8c", "wifi": "#c3e88d",
    "caixa_de_som": "#bd93f9", "outro": "#9a9eb8",
}

#: A cor de quem não tem espécie, e ela não é enfeite: o Archer T3U desta
#: bancada declina de se classificar (`ff/ff/ff`), e `mesa_do_motor` o entrega
#: com `classe` vazia. O tom do hub é o mais apagado da paleta — dizer "não sei
#: o que é isto" com a cor de um Bluetooth seria a tela afirmando o que ninguém
#: mediu.
COR_SEM_CLASSE = CORES_POR_CLASSE["hub"]

#: OS CAMPOS QUE UMA LEITURA VIVA TEM DE TRAZER. Quem entrega menos que isto
#: está entregando um arranjo pela metade, e a página o RECUSA em voz alta em
#: vez de desenhar metade de um gabinete — ver `ABRE_A_PORTA`.
CAMPOS_DO_ARRANJO = ("quando", "aparelhos", "faces", "mapa", "leituras")

#: DE ONDE VEIO A VELOCIDADE DA ENTRADA, na linha de baixo de «Velocidade» —
#: O-MAPA-QUE-ELA-CORRIGE-01 (D-2609-A-VELOCIDADE-DELA-VENCE-A-PLACA). As
#: chaves são as de ``mapa_das_portas`` (``USB_PELO_APARELHO``,
#: ``USB_DECLARADA``, ``USB_PELA_PLACA``; ``""`` é «não se sabe»), e a régua
#: confere as duas pontas.
FRASES_DA_ORIGEM_DA_VELOCIDADE = {
    "placa": "É o que a placa-mãe diz.",
    "declarada": "É o que você disse.",
    "aparelho": "Um aparelho está nela a 5 Gbps.",
    "": "A placa-mãe não diz. Diga você.",
}


def _exemplo_em_js(recuo: str = "  ") -> str:
    """O censo de exemplo como um literal JavaScript legível.

    `json.dumps(indent=2)` quebrava cada aparelho em nove linhas e o bloco
    passava de 250 — ilegível exatamente onde o mockup era legível. Aqui cada
    aparelho, cada face e cada controle ocupa UMA linha, que é a forma em que o
    censo sempre esteve escrito nesta página.
    """
    def compacto(valor: Any) -> str:
        return json.dumps(valor, ensure_ascii=False, separators=(", ", ": "))

    linhas = ["{"]
    for chave, valor in CENSO_DE_EXEMPLO.items():
        if isinstance(valor, list):
            linhas.append(f"{recuo}  {json.dumps(chave, ensure_ascii=False)}: [")
            for item in valor:
                linhas.append(f"{recuo}    {compacto(item)},")
            linhas[-1] = linhas[-1][:-1]  # a última não leva vírgula
            linhas.append(f"{recuo}  ],")
        else:
            linhas.append(
                f"{recuo}  {json.dumps(chave, ensure_ascii=False)}: {compacto(valor)},")
    linhas[-1] = linhas[-1][:-1]
    linhas.append(f"{recuo}}}")
    return "\n".join(linhas)


def _bloco_do_censo(nome: str) -> str:
    """A declaração `var NOME = …;` inteira, como ela está na origem.

    Ela é LIDA da origem, nunca digitada aqui: uma segunda cópia do literal
    envelheceria no dia em que alguém mexesse num byte do mockup congelado, e a
    troca passaria a errar o alvo — calada, porque `str.replace` de um pedaço
    que não existe não levanta nada. É esta função que transforma o silêncio em
    `SystemExit`.
    """
    texto = ORIGEM.read_text(encoding="utf-8")
    abre = f"  var {nome} = "
    linhas = texto.split("\n")
    try:
        inicio = next(i for i, linha in enumerate(linhas) if linha.startswith(abre))
    except StopIteration:
        raise SystemExit(
            f"ERRO: `var {nome} = …` não está na origem congelada ({ORIGEM.name}). "
            "Ou o nome mudou, ou a origem mudou — e nos dois casos a edição "
            "deste gerador está apontando para o que não há.") from None
    for fim in range(inicio, len(linhas)):
        if linhas[fim] in ("  ];", "  };"):
            return "\n".join(linhas[inicio:fim + 1]) + "\n"
    raise SystemExit(
        f"ERRO: achei `var {nome} = …` na origem e não achei o fecho dele. "
        "A forma do bloco mudou; esta leitura tem de mudar junto.")


#: ══ A PORTA PARA O CENSO DE QUEM ABRE ═════════════════════════════════════
#:
#: `window.hefestoArranjo(dado)` é como o produto entrega a leitura DESTA
#: máquina. Quem a chama é `hefesto_vivo.Piloto._entregar_o_arranjo`, com o que
#: `interface/arranjo_desta_maquina.arranjo()` leu do `/sys` mais o mapa que a
#: pessoa declarou. Sem ninguém do lado de fora — a página aberta a dedo no
#: navegador, por exemplo — o que se vê é o exemplo, e o cabeçalho diz isso.
#:
#: ELA RECUSA O QUE NÃO ENTENDE. Um arranjo sem `faces` desenharia um gabinete
#: sem entrada nenhuma e a pessoa leria isso como *"não tenho nada ligado"* —
#: o vazio mais convincente que existe. Aqui a recusa é barulhenta e a página
#: fica com o exemplo, que ao menos se declara exemplo.
ABRE_A_PORTA = """\
  /* ══ A PORTA PARA O CENSO DE QUEM ABRE — 11/09/2026 ══════════════════
     Até aqui esta página só sabia desenhar UM gabinete: o que estava digitado
     no JavaScript dela. `hefestoArranjo` é por onde o produto entrega a
     leitura da máquina de quem abriu, e a página se repinta inteira com ela.
     Ver `interface/pagina_do_mapa.py` e `interface/arranjo_desta_maquina.py`. */
  function controlesSobre(aparelhos, base) {
    /* A fileira de controles é SIMULADOR — os botões 1..4 ao lado dela são a
       pergunta "e se fossem quatro?". O censo vivo não a traz; ela se espalha
       pelos adaptadores que a máquina de quem abre tiver. */
    var bts = aparelhos.filter(function (a) { return a.classe === "bt"; });
    return base.map(function (c, i) {
      return { nome: c.nome, mic: c.mic, onde: bts.length ? bts[i % bts.length].id : null };
    });
  }

  function aplicarArranjo(f, manterOEditor) {
    fonte = f;
    APARELHOS = f.aparelhos;
    FACES = f.faces;
    MAPA = f.mapa;
    /* O "Voltar" do reexame restaura ESTE mapa. Deixá-lo com o do exemplo
       devolveria a pessoa a um gabinete que não é o dela, com um clique. */
    MAPA_ORIGINAL = Object.assign({}, MAPA);
    LEITURAS = f.leituras;
    leituraAtual = "agora";
    leituraAnterior = "antes";
    CONTROLES = f.controles || controlesSobre(APARELHOS, EXEMPLO.controles);
    quantos = CONTROLES.length;
    /* O QUE ELA DECLAROU EM CADA ENTRADA — 26/09/2026, o editor da entrada.
       Toda entrada do mapa dela vem, com {} quando ela não disse nada, e as
       chaves são as que o editor GRAVA no disco. A que o desenho monta do que
       ela declarou (as do hub, a ponta do extensor) não vem: ali, e no
       exemplo, o editor fica só na tela. */
    DECLARADO = JSON.parse(JSON.stringify(f.declarado || {}));
    GRAVA = Object.keys(DECLARADO);
    /* O NOME DE CADA ENTRADA, composto pelo dono (O-MAPA-QUE-ELA-CORRIGE-01):
       `entrada_a_entrada.rotulos_das_entradas`. */
    ROTULOS = f.rotulos || {};
    /* AS ENTRADAS EM QUE O COMPUTADOR LÊ UM HUB (D-2609-O-HUB-PENDE-DA-
       ENTRADA): o editor delas nasce com «Hub», e o plugue ganha a marca. */
    HUB_LIDO = f.hubLido || {};
    /* DE ONDE VEIO A VELOCIDADE de cada entrada: a mesma precedência que
       pintou o plugue (aparelho, depois o que ela disse, depois a placa). */
    USB_DE = f.usbDe || {};
    /* A VOLTA DE UMA GRAVAÇÃO NÃO FECHA O EDITOR — 26/09/2026,
       O-MAPA-QUE-ELA-CORRIGE-01: ela clicou numa entrada, e a entrada
       continua aberta com o que o disco diz agora. */
    if (!manterOEditor) editando = null;
  }

  function dizerDeQuando() {
    /* O cabeçalho nasce dizendo o exemplo, no HTML, para a página ser honesta
       mesmo sem JavaScript nenhum. FATO SUBSTITUÍDO em 26/09/2026: aqui ele
       passava a dizer de quando era a leitura desta máquina, e ela pediu que
       isso saísse («essa info some»). A linha existe só para o exemplo se
       dizer exemplo; com a leitura de quem abre, ela sai da página. */
    var el = document.getElementById("de-quando");
    if (el && fonte.quando !== EXEMPLO.quando) el.remove();
  }

  /* O «EXAMINAR» NO PRODUTO — 26/09/2026, O-MAPA-DAS-CONEXOES-NO-PRODUTO-02.
     Com a leitura desta máquina na tela, quem relê é o produto: o botão leva
     o gesto `reexaminar`, a leitura nova sai fora do fio da janela e volta por
     `hefestoArranjo(dado, true)`, com a que a página tinha como «antes». No
     exemplo não há o que reler, e o reexame é o das duas leituras dele. */
  function doProduto() { return fonte !== EXEMPLO; }
  function examinaNoProduto() { return doProduto() ? ' data-gesto="reexaminar"' : ""; }
  function marcarOExaminar() {
    var ex = document.querySelector(".topo #reexaminar");
    if (ex && doProduto()) ex.setAttribute("data-gesto", "reexaminar");
  }

  window.hefestoArranjo = function (dado, como) {
    /* COMO ELE CHEGA — 26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01: `false` é a
       abertura, `true` é o «Examinar», e "gravou" é a volta
       de uma gravação do editor (`arranjo_desta_maquina.CHAVE_DEPOIS_DE_GRAVAR`):
       a página repinta pelo disco sem mudar de modo nem fechar o editor. */
    var comoReexame = como === true;
    var gravou = como === "gravou";
    var falta = CAMPOS_DO_ARRANJO.filter(function (c) { return !dado || !dado[c]; });
    if (falta.length) {
      /* RECUSAR É METADE DO TRABALHO: meio arranjo desenharia um gabinete sem
         entradas, e isso se lê como "não tenho nada ligado". */
      throw new Error("arranjo incompleto, falta: " + falta.join(", "));
    }
    /* O REEXAME RELÊ O QUE ELA ENSINOU, porque o ensinar grava no disco
       (O-MAPA-QUE-ELA-CORRIGE-01, D-2609-ENSINAR-GRAVA-O-NO). Até aqui o
       mapa da tela era guardado por cima da releitura: o que ela ensinava
       só vivia na memória, e a releitura o desfazia. */
    /* a leitura anterior da tela fica: gravar não é reexaminar */
    var antesDaTela = gravou && LEITURAS ? LEITURAS.antes : null;
    aplicarArranjo(dado, gravou);
    if (antesDaTela) LEITURAS = { agora: dado.leituras.agora, antes: antesDaTela };
    if (comoReexame) {
      modo = "reexame"; segurando = null; naMao = null;
    }
    /* o aparelho que estava na mão foi ensinado: ele sai da mão */
    if (gravou && segurando) { segurando = null; naMao = null; modo = "mesa"; }
    dizerDeQuando();
    marcarOExaminar();
    pintar();
    return "ok";
  };

"""


#: ══ A CAIXA DA JANELA — 24/09/2026 ═════════════════════════════════════════
#:
#: A palavra dela, na página da sessão dos desenhos: *«Vira caixa da janela,
#: rolando por dentro»*. Até aqui esta era uma página de DOCUMENTO — a
#: `.pagina` com `max-width:1180px` (a largura das abas antes de 08/09) e a
#: página inteira rolando: na TV dela, 1180 x 2195 ao lado de uma janela de
#: 1600 x 808. O recuo e o tamanho vêm do dono comum das três páginas avulsas
#: (`caixa_da_janela.moldura`), lidos do esqueleto das abas.
#:
#: O CABEÇALHO FICA E O RESTO ROLA, como na Calibrar e no «Mapa do controle».
#: O `.corpo` vai até a borda da caixa — a barra de rolagem com ele — e o
#: recuo do texto volta pelo `padding`, para nada mudar de lugar lá dentro.
#: O fundo de dentro continua o `--color-paper` desta página: os painéis
#: dela são `--color-paper-2`, e no fundo das abas eles sumiriam.
CAIXA_DA_JANELA = (
    "  /* A CAIXA DA JANELA — 24/09/2026, decisão dela: «vira caixa da janela,\n"
    "     rolando por dentro». O recuo e o tamanho são os das abas (as três\n"
    "     linhas no fim deste bloco); o cabeçalho fica e o `.corpo` rola. */\n"
    "  body {\n"
    "    margin: 0; background: #11121a; color: var(--color-ink);\n"
    "    font-family: var(--font-corpo); font-size: var(--text-base); line-height: 1.55;\n"
    "    -webkit-font-smoothing: antialiased;\n"
    "    display: flex; flex-direction: column; align-items: center;\n"
    "  }\n"
    "  .pagina { background: var(--color-paper); border: 1px solid var(--color-paper-3);\n"
    "            border-radius: 11px; overflow: hidden; display: flex; flex-direction: column;\n"
    "            padding: var(--space-md) var(--space-sm) 0; }\n"
    "  .pagina > .topo { flex: 0 0 auto; }\n"
    "  .pagina > .corpo { flex: 1; min-height: 0; overflow-y: auto;\n"
    "                     margin: 0 calc(-1 * var(--space-sm));\n"
    "                     padding: 0 var(--space-sm) var(--space-lg); }\n"
    + caixa_da_janela.moldura(caixa=".pagina")
)


#: OS DADOS QUE O PAINEL DO APARELHO LÊ, escritos na página pelo gerador: os tipos que ela
#: pode dizer (a régua confere os ids com o dono, `entrada_a_entrada`), a cor de cada um e os
#: lugares do gabinete que o Mapear já oferece.
TIPOS_DO_APARELHO_NA_PAGINA: tuple[tuple[str, str], ...] = (
    ("teclado", "Teclado"), ("mouse", "Mouse"), ("wifi", "Wi-Fi"), ("webcam", "Webcam"),
    ("caixa_de_som", "Caixa de som"), ("outro", "Outro"),
)


def _com_os_dados(js: str) -> str:
    """O JavaScript do painel com os tipos, as cores e os lugares do dono no lugar."""
    cores = {**CORES_POR_CLASSE, **COR_POR_TIPO_DECLARADO}
    dados = {
        "__TIPOS_DO_APARELHO__": json.dumps(TIPOS_DO_APARELHO_NA_PAGINA, ensure_ascii=False),
        "__COR_DO_TIPO__": json.dumps(
            {t: cores.get(t, COR_SEM_CLASSE) for t, _ in TIPOS_DO_APARELHO_NA_PAGINA}),
        "__LUGARES_DA_ENTRADA__": json.dumps(list(LUGARES_DA_PORTA), ensure_ascii=False),
    }
    for chave, valor in dados.items():
        js = js.replace(chave, valor)
    return js


EDICOES: tuple[Edicao, ...] = (
    Edicao(
        antes="<title>Onde eu ponho isto?</title>",
        depois="<title>Hefesto — o mapa das entradas</title>",
        porque=(
            "31/08/2026 — o título da aba do navegador é o que a barra da janela "
            "mostra, e «Onde eu ponho isto?» não diz de que programa é a tela."
        ),
    ),
    Edicao(
        antes=(
            "  .topo .nota { color: var(--color-ink-faint); font-size: var(--text-sm); "
            "margin-left: auto; }\n"
        ),
        depois=(
            "  .topo .nota { color: var(--color-ink-faint); font-size: var(--text-sm); "
            "margin-left: auto; }\n"
            "  /* A DATA NÃO PODE SER `.nota` — 11/09/2026. A folha do produto apaga toda\n"
            "     `.nota` (bilhete de projeto), e aqui isso deixava a página afirmando\n"
            "     «o arranjo de agora» sobre uma leitura congelada. A data é DADO da\n"
            "     página, então tem classe própria, que a folha do produto não esconde. */\n"
            "  .topo .quando { color: var(--color-ink-faint); font-size: var(--text-sm); "
            "margin-left: auto;\n"
            "                  font-family: var(--font-dado); }\n"
        ),
        porque=(
            "11/09/2026 — `folha_da_casa.FOLHA_DA_CASA` abre com "
            "`.nota{display:none !important}`. No Chrome o aviso aparecia; na tela "
            "dela, não — e a página ficava afirmando «o arranjo de agora» sobre uma "
            "leitura congelada, sem a única defesa que tinha."
        ),
    ),
    Edicao(
        antes=(
            '  <header class="topo">\n'
            "    <h1><em>Conexões</em> — o mapa da sua mesa</h1>\n"
            '    <p class="nota">mockup · 24/08/2026 · medido na MeowSystem</p>\n'
        ),
        depois=(
            '  <header class="topo" style="position:relative;padding-left:132px">\n'
            "    <!-- O BOTÃO DE VOLTAR — 30/08/2026, pergunta dela: \"ok temos um botão pra vir\n"
            "         pra cá. Mas e o botão pra voltar?\". Não havia nenhum href de saída nesta\n"
            "         página. O destino não é chute: `grep -l mapa-das-portas.html` devolve UMA\n"
            "         aba, a Conexões — e ela existe ao lado desta cópia, não ao lado da\n"
            "         origem congelada, que tem três arquivos e nenhuma aba. -->\n"
            '    <a href="08-conexoes.html" title="Volta para a aba Conexões, que é de onde '
            'este mapa se abre."\n'
            '       style="position:absolute;left:0;top:2px;display:inline-flex;'
            "align-items:center;gap:6px;\n"
            "              padding:5px 11px;border-radius:7px;text-decoration:none;\n"
            "              border:1px solid var(--border-forte);background:var(--panel);\n"
            '              color:var(--texto-suave);font-size:12px">← Voltar</a>\n'
            "    <h1><em>Conexões</em> — o mapa dos seus objetos</h1>\n"
            f'    <p class="quando" id="de-quando">{QUANDO_DO_EXEMPLO}</p>\n'
        ),
        porque=(
            "TRÊS COISAS NO MESMO CABEÇALHO, e as três têm de sair juntas porque são "
            "as mesmas três linhas. (1) o botão de voltar, 30/08/2026, pedido dela; "
            "ele NÃO pode ir para a origem congelada, cuja pasta não tem "
            "`08-conexoes.html` — seria um botão que não vai a lugar nenhum. "
            "(2) a palavra «mesa» saiu da tela em 05/09/2026, ordem dela. "
            "(3) a linha da data virou `.quando` com `id`, 11/09/2026: a folha do "
            "produto apaga `.nota`, e o `id` é por onde o censo vivo reescreve o "
            "rótulo quando o produto entrega a leitura desta máquina."
        ),
    ),
    Edicao(
        antes=(
            '    <p class="sub">Bluetooth tem 1600 vezes de falar por segundo, '
            "<b>por adaptador</b>, e todos os controles daquele adaptador dividem isso. "
            "Não falta banda: falta vez. É esta conta que decide se a mesa cheia "
            "funciona com tudo ligado.</p>"
        ),
        depois=(
            '    <p class="sub">Cada adaptador Bluetooth atende 1600 envios por segundo, '
            "divididos entre os controles ligados nele. É esta conta que decide se "
            "todos funcionam ao mesmo tempo.</p>"
        ),
        porque=(
            "11/09/2026, `PAGINAS-ESPECIAIS-B1`, por aprovação dela: a frase encolheu "
            "e a palavra «mesa» saiu junto."
        ),
    ),
    Edicao(
        antes=(
            '        <span><code style="font-family:var(--font-dado)">'
            "integrations/dualsense_bt_audio.py</code>, A/B de 25/07/2026</span>"
        ),
        depois="        <span>medido aqui em 25/07/2026</span>",
        porque=(
            "11/09/2026, `PAGINAS-ESPECIAIS-B1`, por aprovação dela: o caminho de um "
            "arquivo do nosso código não é recado de tela. Onde o A/B foi medido "
            "continua escrito no comentário do motor, que é onde quem for conferir "
            "procura."
        ),
    ),
    Edicao(
        antes='porque: "entrada direta, mas na altura da mesa" };',
        depois='porque: "entrada direta, mas na altura da escrivaninha" };',
        porque="05/09/2026 — a palavra «mesa» saiu da tela, ordem dela.",
    ),
    Edicao(
        antes=(
            "      desc: \"Aceita um lugar pior para você mexer em menos coisas. "
            'Bom quando desmontar a mesa custa caro." },'
        ),
        depois=(
            "      desc: \"Aceita um lugar pior para você mexer em menos coisas. "
            'Bom quando desmontar o arranjo custa caro." },'
        ),
        porque="05/09/2026 — a palavra «mesa» saiu da tela, ordem dela.",
    ),
    Edicao(
        antes=(
            '    if (bts.length && noAlto === 0) out.push("os dongles ficam na altura '
            'da mesa, não no alto do rack");'
        ),
        depois=(
            '    if (bts.length && noAlto === 0) out.push("os dongles ficam na altura '
            'da escrivaninha, não no alto do rack");'
        ),
        porque="05/09/2026 — a palavra «mesa» saiu da tela, ordem dela.",
    ),
    Edicao(
        antes=(
            '        \'<button class="modo" data-modo="mesa" aria-pressed="\' + '
            '(modo === "mesa") + \'">Como está a minha mesa</button>\'\n'
            '      + \'<button class="modo destaque" data-modo="ideal" aria-pressed="\' + '
            '(modo === "ideal") + \'">Me mostre os arranjos</button>\'\n'
            '      + \'<button class="modo" data-modo="mao" aria-pressed="\' + '
            '(modo === "mao") + \'">Estou com algo na mão</button>\'\n'  # (noqa-acento: data-modo)
            '      + \'<button class="modo" id="reexaminar" aria-pressed="false" '
            'style="margin-left:auto">Reexaminar a mesa</button>\';'
        ),
        depois=(
            '        \'<button class="modo" data-modo="mesa" aria-pressed="\' + '
            '(modo === "mesa") + \'">Como está hoje</button>\'\n'
            '      + \'<button class="modo destaque" data-modo="ideal" aria-pressed="\' + '
            '(modo === "ideal") + \'">O que mudar</button>\'\n'
            '      + \'<button class="modo" data-modo="mao" aria-pressed="\' + '
            '(modo === "mao") + \'">Tenho algo na mão</button>\'\n'  # (noqa-acento: data-modo)
            '      + \'<button class="modo" id="reexaminar" aria-pressed="false" '
            'style="margin-left:auto">Examinar de novo</button>\';'
        ),
        porque=(
            "11/09/2026, `PAGINAS-ESPECIAIS-B1`, por aprovação dela: os quatro "
            "botões dizem o que fazem em duas ou três palavras, e a palavra «mesa» "
            "sai dos dois que a carregavam. O `data-modo` NÃO muda: "
            "\"mao\" é endereço, e trocá-lo quebra o "  # (noqa-acento): valor
            "`julgar`, que o casa por igualdade de string."
        ),
    ),
    Edicao(
        antes=(
            "      html += '<p class=\"chamada\">Quatro arranjos possíveis. O melhor "
            "no papel pode não caber na sua mesa — escolha o que cabe.</p>'"
        ),
        depois=(
            "      html += '<p class=\"chamada\">Quatro arranjos possíveis. O melhor "
            "no papel pode não caber na sua escrivaninha — escolha o que cabe.</p>'"
        ),
        porque="05/09/2026 — a palavra «mesa» saiu da tela, ordem dela.",
    ),
    Edicao(
        antes=(
            '        html += \'<p class="chamada"><span class="grande">\' + reais.length + '
            '" movimento" + (reais.length > 1 ? "s" : "") + "</span> e a sua mesa fica '
            'no melhor arranjo que este hardware permite.</p>"'
        ),
        depois=(
            '        html += \'<p class="chamada"><span class="grande">\' + reais.length + '
            '" movimento" + (reais.length > 1 ? "s" : "") + "</span> e o seu arranjo fica '
            'no melhor que este hardware permite.</p>"'
        ),
        porque="05/09/2026 — a palavra «mesa» saiu da tela, ordem dela.",
    ),
    Edicao(
        antes=(
            '        + \'<button class="btn" id="ver-antes">Ver como a mesa estava \' + '
            '(leituraAtual === "agora" ? "antes" : "agora") + "</button></div>";'
        ),
        depois=(
            '        + \'<button class="btn" id="ver-antes">Ver como o arranjo estava \' + '
            '(leituraAtual === "agora" ? "antes" : "agora") + "</button></div>";'
        ),
        porque="05/09/2026 — a palavra «mesa» saiu da tela, ordem dela.",
    ),
    Edicao(
        antes=(
            '        ? "Encontrei <span class=\\"grande\\">" + pend + "</span> coisa" + '
            '(pend > 1 ? "s" : "") + " que vale mudar de lugar."\n'
            '        : "Esta mesa está no melhor arranjo que eu conheço.") + "</p>"'
        ),
        depois=(
            '        ? "<span class=\\"grande\\">" + pend + "</span> coisa" + '
            '(pend > 1 ? "s" : "") + " para mudar de lugar."\n'
            '        : "Este arranjo é o melhor que eu conheço.") + "</p>"'
        ),
        porque=(
            "11/09/2026, `PAGINAS-ESPECIAIS-B1`, por aprovação dela, e a palavra "
            "«mesa» sai junto (05/09/2026)."
        ),
    ),
    Edicao(
        antes=(
            "        + (pend ? 'Clique em <b style=\"color:var(--color-ok)\">Me mostre "
            "os arranjos</b> para ver o que mover, na ordem, e por quê.'"
        ),
        depois=(
            "        + (pend ? 'Clique em <b style=\"color:var(--color-ok)\">O que "
            "mudar</b> para ver o que mover, na ordem, e por quê.'"
        ),
        porque=(
            "11/09/2026 — o botão mudou de nome na edição acima, e a frase que manda "
            "clicar nele tem de mudar junto. Um recado que nomeia um botão que não "
            "existe mais é pior do que nenhum."
        ),
    ),
    Edicao(
        antes=(
            '        + (leituraAtual === "agora" ? "Esta é a mesa de agora — " : '
            "'<b style=\"color:var(--color-lacuna)\">Você está vendo uma leitura "
            "ANTIGA</b> — ')"
        ),
        depois=(
            '        + (leituraAtual === "agora" ? "Este é o arranjo de agora — " : '
            "'<b style=\"color:var(--color-lacuna)\">Você está vendo uma leitura "
            "ANTIGA</b> — ')"
        ),
        porque="05/09/2026 — a palavra «mesa» saiu da tela, ordem dela.",
    ),
    Edicao(
        antes=(
            '      + \'<span class="ctl-rot" style="margin-left:auto">Controles na '
            "mesa:</span>'"
        ),
        depois=(
            '      + \'<span class="ctl-rot" style="margin-left:auto">Controles '
            "ligados:</span>'"
        ),
        porque="05/09/2026 — a palavra «mesa» saiu da tela, ordem dela.",
    ),
    Edicao(
        antes=(
            "      + ' <b>Nenhum deles muda a conta do rádio</b> — gatilho, vibração, "
            "barra de luz, giroscópio e touchpad andam no mesmo canal e não somam "
            "pacote. O que eles mudam é a <b>bateria</b>, e o preço disso "
            '<span class="selo derivado">não medido</span> nesta casa: nenhum dos 178 '
            "ensaios cronometrou consumo por feature.</p>'"
        ),
        depois=(
            "      + ' <b>Nenhum deles muda a conta do rádio</b> — gatilho, vibração, "
            "barra de luz, giroscópio e touchpad andam no mesmo canal e não somam "
            "pacote. O que eles gastam é bateria.</p>'"
        ),
        porque=(
            "11/09/2026, `PAGINAS-ESPECIAIS-B1`, por aprovação dela — e é também a "
            "regra de 07/09: a tela nunca confessa dívida nossa. Quantos ensaios esta "
            "casa cronometrou é assunto do mapa, não da tela de quem usa."
        ),
    ),
    Edicao(
        antes=(
            "      + '<span class=\"mic-porque\">Uma caixinha por controle <b>que está "
            "na mesa</b> — controle que nunca esteve aqui não tem onde ser gravado, e "
            "marcar algo que o produto esquece é a definição do defeito que esta leva "
            "mata. Fica fora do perfil de propósito: o microfone é o único que "
            "<b>capta a sala</b>, e o único que muda a conta do rádio — <b>276,7</b> "
            "em vez de 260,4 vezes de falar por segundo. Nasce desligado, e só você o "
            "liga.</span>'"
        ),
        depois=(
            "      + '<span class=\"mic-porque\">Uma caixinha por controle ligado. O "
            "microfone é o único que capta a sala e o único que pesa no rádio — 276,7 "
            "envios por segundo em vez de 260,4. Nasce desligado; só você o liga.</span>'"
        ),
        porque=(
            "11/09/2026, `PAGINAS-ESPECIAIS-B1`, por aprovação dela — e a regra de "
            "07/09: a tela nunca confessa dívida nossa."
        ),
    ),
    Edicao(
        antes=(
            "      + '<br><span class=\"selo derivado\">derivado</span> A conta vem de "
            "uma medição de <b>um</b> controle. '\n"
            '      + "Quatro no rádio ao mesmo tempo <b>nunca foi medido nesta casa</b> '
            '— o maior ensaio já feito foi de dois."'
        ),
        depois=(
            "      + '<br><span class=\"selo derivado\">derivado</span> A conta vale "
            "por controle. Com quatro no rádio, o número é estimado.'"
        ),
        porque=(
            "11/09/2026, `PAGINAS-ESPECIAIS-B1`, por aprovação dela — e a regra de "
            "07/09: a tela nunca confessa dívida nossa. O selo «derivado» fica: ele "
            "diz à pessoa o que o número é, sem contar o que falta à casa."
        ),
    ),
    # ═══ O CENSO SAI DO JAVASCRIPT CRAVADO — as cinco trocas de bloco ═══════
    Edicao(
        antes=(
            "  /* ══ 1. O QUE O BARRAMENTO ENTREGOU — medido em 24/08/2026 ═══════════ */\n"
            + _bloco_do_censo("APARELHOS")
        ),
        depois=(
            "  /* ══ 1. O ARRANJO QUE ESTA PÁGINA DESENHA ════════════════════════════\n"
            "     O exemplo abaixo é a leitura de 24/08/2026 de um gabinete só, e é o\n"
            "     que se vê enquanto ninguém entregar outra. O produto entrega a desta\n"
            "     máquina por `window.hefestoArranjo`, lá embaixo, e o cabeçalho diz\n"
            "     qual das duas está na tela. Quem escreve este bloco é\n"
            "     `interface/pagina_do_mapa.CENSO_DE_EXEMPLO`.                        */\n"
            "  var EXEMPLO = " + _exemplo_em_js() + ";\n"
            "\n"
            "  /* `fonte` é o arranjo em cena: nasce no exemplo acima e é trocado\n"
            "     inteiro por `window.hefestoArranjo(dado)`. `CAMPOS_DO_ARRANJO` é o\n"
            "     que uma entrega tem de trazer para ser aceita. */\n"
            "  var CAMPOS_DO_ARRANJO = "
            + json.dumps(list(CAMPOS_DO_ARRANJO), ensure_ascii=False) + ";\n"
            "  var fonte = EXEMPLO;\n"
            "  var APARELHOS = fonte.aparelhos;\n"
        ),
        porque=(
            "11/09/2026 — o censo sai do JavaScript cravado e ganha dono em "
            "`pagina_do_mapa.CENSO_DE_EXEMPLO`. Oito aparelhos digitados dentro do "
            "HTML de UMA máquina eram apresentados como «o arranjo de agora»: quem "
            "abrisse noutro computador lia o gabinete de outra pessoa."
        ),
    ),
    Edicao(
        antes=(
            "  /* ══ 2. AS FACES — declaradas por ela, na foto numerada ══════════════ */\n"
            + _bloco_do_censo("FACES")
        ),
        depois=(
            "  /* ══ 2. AS FACES — quantas entradas cada face do gabinete tem ════════\n"
            "     Isto não se mede: nenhuma leitura de `/sys` sabe em que face do metal\n"
            "     o buraco fica. Quem declara é quem olha o gabinete. Ver o rodapé.   */\n"
            "  var FACES = fonte.faces;\n"
        ),
        porque=(
            "11/09/2026 — o censo sai do JavaScript cravado (ver `APARELHOS`), e o "
            "comentário para de descrever a foto de uma pessoa."
        ),
    ),
    Edicao(
        antes=_bloco_do_censo("MAPA"),
        depois="  var MAPA = fonte.mapa;\n",
        porque="11/09/2026 — o censo sai do JavaScript cravado (ver `APARELHOS`).",
    ),
    Edicao(
        antes=(
            "  /* ══ 2.2 AS DUAS LEITURAS, medidas na MeowSystem em 24/08/2026 ═══════\n"
            "     A de 20h15 e a de 22h50, depois de ela fazer os movimentos. São dado\n"
            "     real: é a mesma comparação que o produto faria com duas leituras de\n"
            "     sysfs separadas por um \"Reexaminar\".                                   */\n"
            + _bloco_do_censo("LEITURAS")
        ),
        depois=(
            "  /* ══ 2.2 AS DUAS LEITURAS ════════════════════════════════════════════\n"
            "     Duas leituras de `/sys` separadas por um \"Reexaminar\": é assim que o\n"
            "     produto sabe quem mudou de lugar. No exemplo são as de 20h15 e 22h50\n"
            "     de 24/08/2026; com o censo vivo são as que a máquina de quem abriu\n"
            "     entregou.                                                           */\n"
            "  var LEITURAS = fonte.leituras;\n"
        ),
        porque=(
            "11/09/2026 — o censo sai do JavaScript cravado (ver `APARELHOS`), e o "
            "comentário para de nomear a máquina de uma pessoa só."
        ),
    ),
    Edicao(
        antes=_bloco_do_censo("CONTROLES") + "  var quantos = 4;\n",
        depois=(
            "  var CONTROLES = fonte.controles;\n"
            "  var quantos = CONTROLES.length;\n"
        ),
        porque="11/09/2026 — o censo sai do JavaScript cravado (ver `APARELHOS`).",
    ),
    Edicao(
        antes="  pintar();\n})();\n",
        depois=ABRE_A_PORTA + "  pintar();\n})();\n",
        porque=(
            "11/09/2026 — a porta pela qual o produto entrega o arranjo de quem abre. "
            "Ela fica no fim porque chama `pintar`, que só existe depois de o motor "
            "inteiro estar declarado."
        ),
    ),
    # ═══ O RODAPÉ PARA DE DESCREVER UM GABINETE SÓ ═════════════════════════
    Edicao(
        antes=(
            "    <p><b>O que é medição e o que é declaração.</b> Medido nesta máquina "
            "em 24/08/2026: os três adaptadores e\n"
            "      seus caminhos de barramento (<code>3-1.2</code>, <code>3-1.1.4</code>, "
            "<code>3-3</code>); que os dois\n"
            "      chips do hub (<code>4-1</code>, <code>4-1.1</code>) enumeram a "
            "<b>5000M</b> — o enlace SuperSpeed fica\n"
            "      treinado com ou sem o Wi-Fi; o consumo de cada entrada; e que "
            "<code>physical_location</code> só responde\n"
            "      em <code>1-3</code>, então nas outras dez o kernel não sabe onde a "
            "entrada fica no gabinete. Declarado por\n"
            "      você, na foto numerada: quantas entradas cada face tem, e o que está "
            "em cada uma.</p>\n"
            "    <p><b>Qual UB500 está na 9 e qual na 15 é declaração sua</b>, não "
            "medição: os dois são idênticos e o\n"
            "      barramento não distingue posição. O que ele distingue é o serial, e é "
            "por ele que o pareamento fica\n"
            "      preso ao adaptador certo — <code>hciN</code> troca de aparelho entre "
            "sessões e não serve de identidade.</p>"
        ),
        depois=(
            "    <p><b>O que é medição e o que é declaração.</b> Medido no seu "
            "computador: cada aparelho ligado e o\n"
            "      caminho de barramento dele, a velocidade de cada hub e o consumo de "
            "cada entrada. Declarado por você:\n"
            "      quantas entradas cada face do gabinete tem, o número que você "
            "escreveu em cada uma, e qual entrada é\n"
            "      qual caminho. O kernel raramente sabe onde a entrada fica no metal — "
            "por isso quem diz é você.</p>\n"
            "    <p><b>Dois adaptadores iguais o barramento não distingue</b>: qual "
            "deles está em cada entrada é\n"
            "      declaração sua, não medição. O que o barramento distingue é o serial, "
            "e é por ele que o pareamento\n"
            "      fica preso ao adaptador certo — <code>hciN</code> troca de aparelho "
            "entre sessões e não serve de\n"
            "      identidade.</p>"
        ),
        porque=(
            "11/09/2026, ordem dela: *\"a ideia é que todas as features mesmo "
            "do app funcionem nao so pra mim mas "  # (noqa-acento: citação dela)
            "pra qualquer outro user\"*. O rodapé listava "
            "os caminhos de barramento de UM gabinete — `3-1.2`, `4-1`, `1-3` — como "
            "se fossem os de quem abre. O que ele explica (o que se mede e o que se "
            "declara) vale para qualquer máquina; os números não."
        ),
    ),
    Edicao(
        antes=(
            "    <p><b>O extensor não aparece sozinho.</b> Cabo passivo não tem "
            "identidade USB: o dongle na ponta enumera\n"
            "      como se estivesse na porta do hub. Por isso a 15 ganha uma "
            "entrada-filha declarada — para o desenho\n"
            "      mostrar onde a antena está de verdade.</p>"
        ),
        depois=(
            "    <p><b>O extensor não aparece sozinho.</b> Cabo passivo não tem "
            "identidade USB: o aparelho na ponta\n"
            "      enumera como se estivesse na entrada do hub. Por isso uma entrada com "
            "extensor ganha uma\n"
            "      entrada-filha declarada — para o desenho mostrar onde a antena está de "
            "verdade.</p>"
        ),
        porque=(
            "11/09/2026 — mesma ordem dela: «a 15» é uma entrada de um gabinete só. "
            "O fato do cabo passivo vale para qualquer um."
        ),
    ),
    Edicao(
        antes=(
            "              + '<br><span class=\"passo\">o Hefesto desfaz o pareamento "
            "antigo, limpa o que ficou para trás e '\n"
            "              + \"pareia de novo no adaptador certo — sem terminal, com o "
            "controle na mão.</span></li>\";"
        ),
        depois=(
            "              + '<br><span class=\"passo\">hoje isto é gesto de terminal: "
            "o passo a passo está no '\n"
            "              + \"<b>bluetooth-varios-adaptadores</b>, §3.3 — e o controle precisa "
            "estar na sua mão, em PS + Create.</span></li>\";"
        ),
        porque=(
            "A-TELA-PROMETE-PAREAR-01, 19/09/2026. A frase oferecia um gesto que o "
            "produto NÃO faz: os 18 gestos da aba Conexões não tocam em pareamento. "
            "O transporte inteiro existe (os verbos `esquecer`, `descobrir` e "
            "`parear`, o script instalado como root, o sudoers com NOPASSWD, o agente "
            "ativo); o que falta é o último palmo, e é a PONTE-SEM-CHAMADOR-01. "
            "Enquanto o botão não existir, a frase é o produto afirmando uma "
            "capacidade que não tem — e nesta casa fato errado se SUBSTITUI, não se "
            "guarda ao lado. O texto novo diz o que há hoje e aponta o caminho, em "
            "vez de prometer.\n"
            "FATO ERRADO, SUBSTITUÍDO (20/09/2026): esta razão dizia que "
            "`grep -rn bt_ponte_privilegiada src/` devolvia ZERO. Não devolve mais, "
            "e já não devolvia quando foi escrita — `integrations/conexao_zumbi.py` "
            "chama o verbo `desconectar` desde 18/09, e "
            "`integrations/gesto_de_pareamento.py` chama `descobrir` e `parear` desde "
            "20/09. O QUE NÃO MUDOU, e é o que sustenta esta edição: nenhum BOTÃO da "
            "tela pareia, porque a PONTE-SEM-CHAMADOR-01 deixou os dois botões para "
            "depois do OK dela — parear escreve no rádio dela com quatro controles "
            "vivos em cima."
        ),
    ),
    # ═══ A CAIXA DA JANELA — 24/09/2026, publicada no mesmo dia (ver `CAIXA_DA_JANELA`) ═══
    Edicao(
        antes=(
            "  body {\n"
            "    margin: 0; background: var(--color-paper); color: var(--color-ink);\n"
            "    font-family: var(--font-corpo); font-size: var(--text-base); "
            "line-height: 1.55;\n"
            "    -webkit-font-smoothing: antialiased;\n"
            "  }\n"
            "  .pagina { max-width: 1180px; margin: 0 auto; padding: var(--space-md) "
            "var(--space-sm) var(--space-lg); }\n"
        ),
        depois=CAIXA_DA_JANELA,
        porque=(
            "AS-PAGINAS-AVULSAS-TEM-A-CAIXA-DA-JANELA-01, 24/09/2026, a palavra "
            "dela: «Vira caixa da janela, rolando por dentro». A página tinha a "
            "largura das abas de antes de 08/09 e rolava inteira (1180 x 2195 na "
            "TV dela, contra a janela de 1600 x 808)."
        ),
    ),
    Edicao(
        antes='  </header>\n\n  <div class="modos" id="modos"></div>\n',
        depois='  </header>\n\n  <div class="corpo">\n  <div class="modos" id="modos"></div>\n',
        porque=(
            "24/09/2026 — o `.corpo` que rola por dentro da caixa abre logo depois "
            "do cabeçalho, que fica."
        ),
    ),
    Edicao(
        antes="  </footer>\n</div>\n\n<script>\n",
        depois="  </footer>\n  </div>\n</div>\n\n<script>\n",
        porque="24/09/2026 — e fecha depois do rodapé, que rola junto com o resto.",
    ),
    # ═══ O MAPA DAS CONEXÕES — 26/09/2026, o que ela pediu olhando a página ═══
    # Publicadas em 26/09/2026 pela O-MAPA-DAS-CONEXOES-NO-PRODUTO-01, por
    # delegação dela («quem implementa publica»). Várias editam o que uma edição
    # de antes escreveu (o cabeçalho e os modos de 11/09): o gerador as aplica
    # em ordem, e a régua cobra cada `antes` no texto da vez dela.
    Edicao(
        antes=(
            '</head>'
        ),
        depois=(
            '<style>\n'
            '  /* O MAPA DAS CONEXÕES — 26/09/2026, os pedidos dela olhando a'
            ' página. */\n'
            '  /* «a cor de fonte de qualquer cinza que tem na página muda pr'
            'a branco» */\n'
            '  :root { --color-ink-quiet: #f8f8f2; --color-ink-faint: #f8f8f2'
            '; }\n'
            '  .pagina { --texto-suave: #f8f8f2; --texto-mudo: #f8f8f2; }\n'
            '  /* as bordas que usavam o cinza continuam cinza: só a LETRA fi'
            'cou branca */\n'
            '  .plug[data-v="serve"], .plug[data-v="fica"] { box-shadow: 0 0 '
            '0 2px #6272a4; }\n'
            '  .chip:hover { border-color: #6272a4; }\n'
            '  /* o cartão que já tem entrada não se apaga mais: o número diz'
            ' que ele tem lugar */\n'
            '  .chip[data-alocado="1"] { opacity: 1; }\n'
            '  /* «Examinar» mora no cabeçalho, onde estava a data da leitura'
            ' */\n'
            '  .topo .examinar { margin-left: auto; align-self: center; displ'
            'ay: inline-flex;\n'
            '                    align-items: center; gap: .4rem; }\n'
            '  .topo .examinar span { pointer-events: none; }\n'
            '  .painel .fina { margin: .35rem 0 0; font-size: var(--text-sm);'
            ' }\n'
            '  /* o editor da entrada: o que tem nela e a velocidade dela */\n'
            '  .palco { position: relative; }\n'
            '  .rotulo .decl { display: inline-block; margin: .15rem 0 0 .4re'
            'm; padding: 0 .4rem;\n'
            '                  border: 1px solid var(--color-accent); border-'
            'radius: var(--radius-sm);\n'
            '                  color: var(--color-accent); font-size: .6875re'
            'm; }\n'
            '  .edita { position: absolute; z-index: 5; width: 300px; display'
            ': flex; flex-direction: column;\n'
            '           gap: .6rem; padding: .7rem .8rem; background: var(--c'
            'olor-paper-2);\n'
            '           border: 1px solid var(--color-accent); border-radius:'
            ' var(--radius-md);\n'
            '           box-shadow: 0 8px 24px rgba(0,0,0,.45); }\n'
            '  .edita[hidden] { display: none; }\n'
            '  .edita-cab { display: flex; align-items: center; gap: .5rem; }'
            '\n'
            '  .edita-cab b { font-size: var(--text-base); }\n'
            '  .edita-cab span { font-size: var(--text-xs); }\n'
            '  .edita-cab .fecha { margin-left: auto; min-width: 0; width: 1.'
            '8rem; height: 1.8rem;\n'
            '                      padding: 0; display: inline-flex; align-it'
            'ems: center; justify-content: center; }\n'
            '  .edita-linha { display: flex; flex-direction: column; gap: .3r'
            'em; }\n'
            '  .edita-linha > span { font-size: var(--text-xs); font-weight: '
            '600; }\n'
            '  .edita .seg { display: grid; grid-template-columns: repeat(3, '
            'minmax(0, 1fr)); gap: .3rem; }\n'
            '  .edita .seg.dois { grid-template-columns: repeat(2, minmax(0, '
            '1fr)); }\n'
            '  .edita .seg .escolha { justify-content: center; text-align: ce'
            'nter; }\n'
            '  /* «Arruma o alinhamento dos blocos» — 26/09/2026. O «Voltar» '
            'entra na linha\n'
            '     do título, os três modos têm a mesma largura, as colunas de'
            ' entradas têm a\n'
            '     mesma largura em todas as chapas, e a bandeja começa na alt'
            'ura da primeira\n'
            '     chapa e acompanha a rolagem. */\n'
            '  .topo { padding-left: 0 !important; align-items: center; }\n'
            '  .topo > a[href="08-conexoes.html"] { position: static !importa'
            'nt; }\n'
            '  .modos { display: grid; grid-template-columns: repeat(3, 8.5re'
            'm); }\n'
            '  .modos .modo { justify-content: center; text-align: center; }\n'
            '  .chapa.grade-tras { grid-template-columns: repeat(2, 17rem); }'
            '\n'
            '  .chapa.fileira { grid-template-columns: repeat(3, 17rem); }\n'
            '  .palco > .bandeja { margin-top: 29px; position: sticky; top: .'
            '5rem; }\n'
            '  @media (max-width: 640px) {\n'
            '    .chapa.fileira, .chapa.grade-tras { grid-template-columns: m'
            'inmax(0, 1fr); }\n'
            '    .modos { grid-template-columns: repeat(3, minmax(0, 1fr)); }'
            '\n'
            '    .palco > .bandeja { margin-top: 0; position: static; }\n'
            '  }\n'
            '</style>\n'
            '</head>'
        ),
        porque=(
            '26/09/2026 — a folha do mapa das conexões: o cinza da letra vira'
            ' branco, o «Examinar» no cabeçalho e o editor da entrada.'
        ),
    ),
    Edicao(
        antes=(
            '<h1><em>Conexões</em> — o mapa dos seus objetos</h1>\n'
            '    <p class="quando" id="de-quando">leitura de exemplo · 24/08/'
            '2026</p>\n'
        ),
        depois=(
            '<h1>Mapa das <em>Conexões</em></h1>\n'
            '    <button class="btn examinar" id="reexaminar" title="Lê o com'
            'putador de novo e mostra o que mudou de lugar"><span aria-hidden'
            '="true">⟳</span> Examinar</button>\n'
        ),
        porque=(
            '26/09/2026, pedidos dela: *«Mapa das Entradas Muda pra Mapa das '
            'Conexões»*, *«leitura deste computador · 26/09/2026 03h13 essa i'
            'nfo some»* e *«botão examinar de novo tá desconexo do resto dos '
            'elementos»*. O «Examinar» ocupa o lugar da data, com o ícone, e '
            'sai da fileira dos modos, onde parecia um quarto modo. O `dizerD'
            'eQuando` já aceita a data ausente.'
        ),
    ),
    Edicao(
        antes=(
            '  <div class="palco">\n'
            '    <div class="faces" id="faces"></div>'
        ),
        depois=(
            '  <div class="palco">\n'
            '    <div class="edita" id="edita" hidden></div>\n'
            '    <div class="faces" id="faces"></div>'
        ),
        porque=(
            '26/09/2026 — o editor da entrada mora no palco, por cima das fac'
            'es.'
        ),
    ),
    Edicao(
        antes=(
            '  <section class="secao">\n'
            '    <h2>Os controles — onde cada um rende 100%</h2>\n'
            '    <p class="sub">Cada adaptador Bluetooth atende 1600 envios p'
            'or segundo, divididos entre os controles ligados nele. É esta co'
            'nta que decide se todos funcionam ao mesmo tempo.</p>\n'
            '    <div class="moldura">\n'
            '      <div class="adaptadores" id="adaptadores"></div>\n'
            '      <div class="legenda" style="margin-top:1rem">\n'
            '        <span>Controle com microfone: <b style="color:var(--colo'
            'r-ink)">276,7</b>/s</span>\n'
            '        <span>sem microfone: <b style="color:var(--color-ink)">2'
            '60,4</b>/s</span>\n'
            '        <span class="selo medido">medido</span>\n'
            '        <span>medido aqui em 25/07/2026</span>\n'
            '      </div>\n'
            '    </div>\n'
            '  </section>\n'
            '\n'
            '  <footer class="rodape">\n'
            '    <p><b>O que é medição e o que é declaração.</b> Medido no se'
            'u computador: cada aparelho ligado e o\n'
            '      caminho de barramento dele, a velocidade de cada hub e o c'
            'onsumo de cada entrada. Declarado por você:\n'
            '      quantas entradas cada face do gabinete tem, o número que v'
            'ocê escreveu em cada uma, e qual entrada é\n'
            '      qual caminho. O kernel raramente sabe onde a entrada fica '
            'no metal — por isso quem diz é você.</p>\n'
            '    <p><b>Dois adaptadores iguais o barramento não distingue</b>'
            ': qual deles está em cada entrada é\n'
            '      declaração sua, não medição. O que o barramento distingue '
            'é o serial, e é por ele que o pareamento\n'
            '      fica preso ao adaptador certo — <code>hciN</code> troca de'
            ' aparelho entre sessões e não serve de\n'
            '      identidade.</p>\n'
            '    <p><b>O extensor não aparece sozinho.</b> Cabo passivo não t'
            'em identidade USB: o aparelho na ponta\n'
            '      enumera como se estivesse na entrada do hub. Por isso uma '
            'entrada com extensor ganha uma\n'
            '      entrada-filha declarada — para o desenho mostrar onde a an'
            'tena está de verdade.</p>\n'
            '  </footer>\n'
        ),
        depois="",
        porque=(
            '26/09/2026, pedido dela: *«tudo do Os controles — onde cada um r'
            'ende 100% deixa de existir tudo isso aí até O extensor não apare'
            'ce sozinho»*. O Perfil de Desempenho desceu para cada cartão da '
            'aba (*«deveria aparecer por controle»*), os controles ligados e '
            'o microfone saíram (*«Controles Ligados por default no software '
            'é 4, isso não deve aparecer pro user. Quem usa o microfone també'
            'm não»*), e os controles no adaptador errado viraram a Sugestão '
            'de Conexão da aba. O rodapé saiu junto.'
        ),
    ),
    Edicao(
        antes=(
            '        \'<button class="modo" data-modo="mesa" aria-pressed="\' +'
            ' (modo === "mesa") + \'">Como está hoje</button>\'\n'
            '      + \'<button class="modo destaque" data-modo="ideal" aria-pr'
            'essed="\' + (modo === "ideal") + \'">O que mudar</button>\'\n'
            '      + \'<button class="modo" data-modo="mao" aria-pressed="\' + '
            '(modo === "mao") + \'">Tenho algo na mão</button>\'\n'  # (noqa-acento: JS)
            '      + \'<button class="modo" id="reexaminar" aria-pressed="fals'
            'e" style="margin-left:auto">Examinar de novo</button>\';\n'
        ),
        depois=(
            '        \'<button class="modo" data-modo="mesa" aria-pressed="\' +'
            ' (modo === "mesa") + \'">Atual</button>\'\n'
            '      + \'<button class="modo destaque" data-modo="ideal" aria-pr'
            'essed="\' + (modo === "ideal") + \'">Sugestões</button>\'\n'
            '      + \'<button class="modo" data-modo="mao" aria-pressed="\' + '
            '(modo === "mao") + \'">Adicionar</button>\';\n'  # (noqa-acento: JS)
        ),
        porque=(
            '26/09/2026, pedido dela: *«muda os nomes dos botões pra algo fác'
            'il de entender. No máximo 1 palavra.»* Os nomes são dela: *«Atua'
            'l, Sugestões, Adicionar»*. O `data-modo` não muda: é endereço.'
        ),
    ),
    Edicao(
        antes=(
            '    } else {\n'
            '      var pend = receita(op).filter(function (m) { return !m.sem'
            'Numero; }).length;\n'
            '      var sem = semEntrada();\n'
            '      html = \'<p class="chamada">\' + (pend\n'
            '        ? "<span class=\\"grande\\">" + pend + "</span> coisa" + ('
            'pend > 1 ? "s" : "") + " para mudar de lugar."\n'
            '        : "Este arranjo é o melhor que eu conheço.") + "</p>"\n'
            '        + \'<p style="margin:0;font-size:var(--text-sm);color:var'
            '(--color-ink-quiet)">\'\n'
            '        + (pend ? \'Clique em <b style="color:var(--color-ok)">O '
            "que mudar</b> para ver o que mover, na ordem, e por quê.'\n"
            '                : "Se o controle ainda engasgar, a causa não é a'
            ' disposição — olhe a conta de vezes de falar, abaixo.")\n'
            '        + "</p>"\n'
            '        + \'<p style="margin:.5rem 0 0;font-size:var(--text-xs);c'
            'olor:var(--color-ink-faint)">\'\n'
            '        + (leituraAtual === "agora" ? "Este é o arranjo de agora'
            ' — " : \'<b style="color:var(--color-lacuna)">Você está vendo uma'
            " leitura ANTIGA</b> — ')\n"
            '        + LEITURAS[leituraAtual].rotulo + " · você declarou <b s'
            'tyle=\\"color:var(--color-ink-quiet)\\">"\n'
            '        + Object.keys(MAPA).length + " de " + todasPortas().leng'
            'th + "</b> entradas."\n'
            '        + (sem.length ? \' <b style="color:var(--color-lacuna)">\''
            ' + sem.length\n'
            '            + " aparelho" + (sem.length > 1 ? "s estão" : " está'
            '") + " numa entrada que você não declarou.</b>" : "")\n'
            '        + "</p>";\n'
            '    }\n'
        ),
        depois=(
            '    } else {\n'
            '      var pend = receita(op).filter(function (m) { return !m.sem'
            'Numero; }).length;\n'
            '      var sem = semEntrada();\n'
            '      html = \'<p class="chamada">\' + (pend\n'
            '        ? \'<span class="grande">\' + pend + "</span> coisa" + (pe'
            'nd > 1 ? "s" : "") + " para mudar de lugar"\n'
            '        : "Nada a mudar de lugar") + "</p>"\n'
            '        + \'<p class="fina">\'\n'
            '        + (leituraAtual === "agora" ? "" : \'<b style="color:var('
            '--color-lacuna)">leitura antiga</b> · \')\n'
            '        + Object.keys(MAPA).length + " de " + todasPortas().leng'
            'th + " entradas mapeadas"\n'
            '        + (sem.length ? \' · <b style="color:var(--color-lacuna)"'
            '>\' + sem.length + " aparelho"\n'
            '            + (sem.length > 1 ? "s" : "") + " fora do mapa</b>" '
            ': "")\n'
            '        + (pend ? \' · clique em <b style="color:var(--color-ok)"'
            '>Sugestões</b>\' : "")\n'
            '        + "</p>";\n'
            '    }\n'
        ),
        porque=(
            '26/09/2026 — o painel do «Atual» diz o que há para mudar e quant'
            'as entradas estão mapeadas, e mais nada. A frase que mandava olh'
            'ar a conta dos controles abaixo saiu com a seção.'
        ),
    ),
    Edicao(
        antes=(
            '    h += "</span></div>";\n'
            '    if (porta.filho) h +='
        ),
        depois=(
            '    if (DECLARADO[porta.n] && DECLARADO[porta.n].liga === "hub")'
            ' h += \'<span class="decl">hub</span>\';\n'
            '    h += "</span></div>";\n'
            '    if (porta.filho) h +='
        ),
        porque=(
            '26/09/2026 — a entrada em que ela declarou um hub mostra o selo.'
        ),
    ),
    Edicao(
        antes=(
            '    /* ── os controles: onde cada um deve ficar ────────────────'
            '────── */\n'
            '    var alvo = document.getElementById("adaptadores");\n'
            '    var pc = planoDosControles();\n'
            '    var pa = perfilAtual();\n'
            '    var micLigado = CONTROLES.slice(0, quantos).some(function (c'
            ') { return c.mic; });\n'
            '    var h2 = \'<div class="linha-perfil"><span class="ctl-rot">Pe'
            "rfil de desempenho:</span>'\n"
            '      + PERFIS.map(function (v) {\n'
            '          return \'<button class="escolha" data-perfil="\' + v.id '
            '+ \'" aria-pressed="\' + (perfil === v.id) + \'">\' + v.rotulo + "</'
            'button>";\n'
            '        }).join("")\n'
            '      + \'<span class="ctl-rot" style="margin-left:auto">Controle'
            "s ligados:</span>'\n"
            '      + [1,2,3,4].map(function (n) {\n'
            '          return \'<button class="escolha" data-quantos="\' + n + '
            '\'" aria-pressed="\' + (quantos === n) + \'">\' + n + "</button>";\n'
            '        }).join("")\n'
            '      + "</div>"\n'
            '      + \'<p class="ctl-nota">\' + pa.resumo\n'
            "      + ' <b>Nenhum deles muda a conta do rádio</b> — gatilho, v"
            'ibração, barra de luz, giroscópio e touchpad andam no mesmo cana'
            "l e não somam pacote. O que eles gastam é bateria.</p>'\n"
            '      + \'<div class="linha-mic"><b>Quem usa microfone</b>\'\n'
            '      + CONTROLES.slice(0, quantos).map(function (c) {\n'
            '          return \'<button class="escolha" data-mic-de="\' + c.nom'
            'e + \'" aria-pressed="\' + c.mic + \'">\'\n'
            '            + (c.mic ? "\\u2611 " : "\\u2610 ") + c.nome + "</butt'
            'on>";\n'
            '        }).join("")\n'
            '      + \'<span class="mic-porque">Uma caixinha por controle liga'
            'do. O microfone é o único que capta a sala e o único que pesa no'
            ' rádio — 276,7 envios por segundo em vez de 260,4. Nasce desliga'
            "do; só você o liga.</span>'\n"
            '      + "</div>";\n'
            '\n'
            '    pc.ads.forEach(function (a) {\n'
            '      var meus = CONTROLES.slice(0, quantos).filter(function (c)'
            ' { return pc.destino[c.nome] === a.id; });\n'
            '      var usado = pc.carga[a.id] || 0;\n'
            '      var pct = Math.min(100, Math.round(usado / SLOTS * 100));\n'
            '      var fx = faixa(usado);\n'
            '      h2 += \'<div class="adap"><div class="quem"><b>Adaptador · '
            '\' + a.rotulo + "</b><span>"\n'
            '        + (meus.length ? meus.map(function (c) { return c.nome.r'
            'eplace("Jogador ", "P") + (c.mic ? " com mic" : ""); }).join(" ·'
            ' ") : "nenhum controle")\n'
            '        + \'</span></div><div class="barra"><i class="\' + fx.clas'
            'se + \'" style="width:\' + pct + \'%"></i></div>\'\n'
            '        + \'<div class="conta">\' + fatias(usado) + " / " + SLOTS '
            '+ " · " + pct + \'% · <em class="\' + fx.classe + \'">\'\n'
            '        + (usado === 0 ? "livre" : fx.nome) + "</em></div></div>'
            '";\n'
            '    });\n'
            '\n'
            '    var fxPico = faixa(Math.max.apply(null, pc.ads.map(function '
            '(a) { return pc.carga[a.id] || 0; })));\n'
            '    h2 += \'<div class="veredito-mesa \' + (fxPico.classe === "che'
            'ia" ? "ruim" : fxPico.classe === "apertada" ? "aviso" : "bom") +'
            ' \'">\'\n'
            '      + (function () {\n'
            '          var pico = Math.max.apply(null, pc.ads.map(function (a'
            ') { return pc.carga[a.id] || 0; }));\n'
            '          var fx = faixa(pico);\n'
            '          if (fx.classe === "cheia") {\n'
            '            return "<b>Não cabe.</b> O adaptador mais cheio cheg'
            'a a " + fatias(pico) + " das " + SLOTS\n'
            '              + " vezes de falar por segundo (" + Math.round(pic'
            'o / SLOTS * 100) + "%), e aí o controle engasga.";\n'
            '          }\n'
            '          if (fx.classe === "apertada") {\n'
            '            return "<b>Cabe, mas apertado.</b> O adaptador mais '
            'cheio fica em " + fatias(pico) + " de " + SLOTS\n'
            '              + " (" + Math.round(pico / SLOTS * 100) + "%). Fun'
            'ciona — e é o degrau em que um dongle a mais"\n'
            '              + " deixa de ser luxo."\n'
            '              + (pc.sobra > 0 ? " Ainda caberiam <b>mais " + pc.'
            'sobra + "</b> com microfone." : "");\n'
            '          }\n'
            '          return "<b>Cabe, com folga.</b> O adaptador mais cheio'
            ' fica em " + fatias(pico) + " de " + SLOTS\n'
            '            + " (" + Math.round(pico / SLOTS * 100) + "%)."\n'
            '            + (pc.sobra > 0 ? " Ainda caberiam <b>mais " + pc.so'
            'bra + "</b> com microfone." : "");\n'
            '        })()\n'
            '      + \'<br><span class="selo derivado">derivado</span> A conta'
            " vale por controle. Com quatro no rádio, o número é estimado.'\n"
            '      + "</div>";\n'
            '\n'
            '    /* o que ela precisa MOVER de adaptador, e como */\n'
            '    var mudancas = CONTROLES.slice(0, quantos).filter(function ('
            'c) { return pc.destino[c.nome] !== c.onde; });\n'
            '    if (mudancas.length) {\n'
            '      h2 += \'<div class="veredito-mesa aviso"><b>\' + mudancas.le'
            'ngth + " controle" + (mudancas.length > 1 ? "s estão" : " está")'
            '\n'
            '        + " no adaptador errado.</b> O pareamento fica preso ao '
            'adaptador onde nasceu — plugar outro dongle não move ninguém.<ul'
            ' class=\\"mudar\\">"\n'
            '        + mudancas.map(function (c) {\n'
            '            var de = adaptadores().filter(function (a) { return '
            'a.id === c.onde; })[0];\n'
            '            var para = adaptadores().filter(function (a) { retur'
            'n a.id === pc.destino[c.nome]; })[0];\n'
            '            return "<li><b>" + c.nome + "</b>: " + (de ? de.rotu'
            'lo : "adaptador atual") + " → " + (para ? para.rotulo : "?")\n'
            '              + \'<br><span class="passo">hoje isto é gesto de te'
            "rminal: o passo a passo está no '\n"
            '              + "<b>bluetooth-varios-adaptadores</b>, §3.3 — e o controle '
            'precisa estar na sua mão, em PS + Create.</span></li>";\n'
            '          }).join("")\n'
            '        + "</ul></div>";\n'
            '    }\n'
            '    alvo.innerHTML = h2;\n'
        ),
        depois=(
            '    mostrarEditor();\n'
            '    emTitulo(document.querySelector(".pagina"));\n'
        ),
        porque=(
            '26/09/2026 — a pintura dos controles saiu com a seção; no fim da'
            ' pintura entram o editor da entrada e a maiúscula de cada palavr'
            'a.'
        ),
    ),
    Edicao(
        antes=(
            'document.addEventListener("click", function (ev) {\n'
        ),
        depois=(
            'document.addEventListener("click", function (ev) {\n'
            '    /* O EDITOR DA ENTRADA — 26/09/2026. Os gestos dele vêm ante'
            's de todos:\n'
            '       um botão dentro do editor não pode cair no clique do plug'
            'ue embaixo. */\n'
            '    if (ev.target.closest(".modo[data-modo]")) editando = null;\n'
            '    if (ev.target.id === "edita-fecha") { editando = null; pinta'
            'r(); return; }\n'
            '    var lg = ev.target.closest("#edita [data-liga]");\n'
            '    if (lg) { declarar(editando, "liga", lg.getAttribute("data-l'
            'iga")); pintar(); return; }\n'
            '    var ub = ev.target.closest("#edita [data-usb]");\n'
            '    if (ub) { declarar(editando, "usb", parseInt(ub.getAttribute'
            '("data-usb"), 10)); pintar(); return; }\n'
            '    var tb = ev.target.closest("#edita [data-tirar]");\n'
            '    if (tb) {\n'
            '      /* «Mudar de Entrada» é o que o clique no plugue ocupado f'
            'azia antes:\n'
            '         a entrada deixa de ser dele, e ele fica na mão até ela '
            'dizer onde está. */\n'
            '      var nt = tb.getAttribute("data-tirar"), quemT = acha(aloca'
            'cao[nt]);\n'
            '      delete MAPA[nt]; editando = null;\n'
            '      segurando = quemT.id; modo = "mao";\n'  # (noqa-acento: JS)
            '      naMao = ({ bt: "bt", wifi: "wifi", teclado: "teclado", mou'
            'se: "mouse", webcam: "webcam" })[quemT.classe] || null;\n'
            '      pintar(); return;\n'
            '    }\n'
            '    if (editando && !ev.target.closest("#edita") && !ev.target.c'
            'losest(".plug[data-porta]")) {\n'
            '      editando = null; pintar();\n'
            '    }\n'
        ),
        porque=(
            '26/09/2026 — os cliques do editor da entrada.'
        ),
    ),
    Edicao(
        antes=(
            '      } else if (alocacao[n]) {\n'  # (noqa-acento: JS)
            '        var quem = acha(alocacao[n]);\n'  # (noqa-acento: JS)
            '        delete MAPA[n];                 /* desdeclara: ela vai d'
            'izer onde é */\n'
            '        segurando = quem.id; modo = "mao";\n'  # (noqa-acento: JS)
            '        naMao = ({ bt: "bt", wifi: "wifi", teclado: "teclado", m'
            'ouse: "mouse", webcam: "webcam" })[quem.classe] || null;\n'
            '      }\n'
        ),
        depois=(
            '      } else {\n'
            '        /* o plugue abre o editor dela: o que tem nesta entrada,'
            ' e a velocidade */\n'
            '        editando = n;\n'
            '      }\n'
        ),
        porque=(
            '26/09/2026 — o clique no plugue abre o editor; o «Mudar de entra'
            'da» dele é o que o clique no plugue ocupado fazia antes.'
        ),
    ),
    Edicao(
        antes=(
            '  function pintar() {'
        ),
        depois=(
            '  /* ══ O EDITOR DA ENTRADA — 26/09/2026 ═══════════════════════'
            '═══════════\n'
            '     Pedido dela: «ao clicar em um desses usb mapeados eu pudess'
            'e setar que tem\n'
            '     tal coisa lá. no caso o hub ou afins». E a velocidade é a o'
            'utra metade: o\n'
            '     kernel só sabe se a entrada é USB 3.0 pelo par que a placa-'
            'mãe declara, e\n'
            '     ela pode corrigir o que o firmware diz. `DECLARADO` é o que'
            ' ela disse nesta\n'
            '     página; gravar no `maquina.json` é do produto. */\n'
            '  var DECLARADO = {};\n'
            '  var editando = null;\n'
            '\n'
            '  function declarar(n, campo, valor) {\n'
            '    var p = porNum(n);\n'
            '    if (!p) return;\n'
            '    var d = DECLARADO[n] || (DECLARADO[n] = {});\n'
            '    d[campo] = valor;\n'
            '    if (campo === "usb") p.usb = valor;\n'
            '    if (campo !== "liga") return;\n'
            '    FACES = FACES.filter(function (f) { return f.daEntrada !== S'
            'tring(n); });\n'
            '    delete p.filho;\n'
            '    if (valor === "hub") {\n'
            '      FACES.push({ nome: "Hub na Entrada " + n, forma: "fileira"'
            ', regiao: "hub", daEntrada: String(n),\n'
            '        portas: [1, 2, 3, 4].map(function (i) { return { n: n + '
            '"." + i, usb: p.usb, onde: "hub", pos: i }; }) });\n'
            '    } else if (valor === "extensor") {\n'
            '      p.filho = { n: n + "a", usb: p.usb, onde: p.onde, esticada'
            ': true, cabo: "Extensor, declarado por você" };\n'
            '    }\n'
            '  }\n'
            '\n'
            '  function mostrarEditor() {\n'
            '    var ed = document.getElementById("edita");\n'
            '    if (!ed) return;\n'
            '    var p = editando && porNum(editando);\n'
            '    var plug = p && document.querySelector(\'.plug[data-porta="\' '
            '+ editando + \'"]\');\n'
            '    if (!p || !plug || modo === "ideal" || segurando) { ed.hidde'
            'n = true; return; }\n'
            '    var liga = (DECLARADO[editando] || {}).liga || "direto";\n'
            '    var face = FACES.filter(function (f) {\n'
            '      return f.portas.some(function (x) { return x === p || x.fi'
            'lho === p; });\n'
            '    })[0];\n'
            '    var quem = alocacao[editando] ? acha(alocacao[editando]) : n'  # (noqa-acento: JS)
            'ull;\n'
            '    ed.innerHTML = \'<div class="edita-cab"><b>Entrada \' + editan'
            'do + "</b><span>" + (face ? face.nome : "") + "</span>"\n'
            '      + \'<button class="btn fecha" id="edita-fecha" aria-label="'
            'Fechar">&times;</button></div>\'\n'
            '      + \'<div class="edita-linha"><span>O que tem aqui</span><di'
            'v class="seg">\'\n'
            '      + [["direto", "Direto"], ["hub", "Hub"], ["extensor", "Ext'
            'ensor"]].map(function (o) {\n'
            '          return \'<button class="escolha" data-liga="\' + o[0] + '
            '\'" aria-pressed="\' + (liga === o[0]) + \'">\' + o[1] + "</button>"'
            ';\n'
            '        }).join("")\n'
            '      + "</div></div>"\n'
            '      + \'<div class="edita-linha"><span>Velocidade</span><div cl'
            'ass="seg dois">\'\n'
            '      + [[3, "USB 3.0"], [2, "USB 2.0"]].map(function (o) {\n'
            '          return \'<button class="escolha" data-usb="\' + o[0] + \''
            '" aria-pressed="\' + (p.usb === o[0]) + \'">\' + o[1] + "</button>"'
            ';\n'
            '        }).join("")\n'
            '      + "</div></div>"\n'
            '      + (quem ? \'<div class="edita-linha"><span>\' + quem.tipo + '
            "' está aqui</span>'\n"
            '          + \'<button class="btn" data-tirar="\' + editando + \'">M'
            'udar de entrada</button></div>\' : "");\n'
            '    ed.hidden = false;\n'
            '    var palco = ed.parentElement.getBoundingClientRect(), r = pl'
            'ug.getBoundingClientRect();\n'
            '    ed.style.left = Math.max(0, Math.min(r.left - palco.left, pa'
            'lco.width - 310)) + "px";\n'
            '    ed.style.top = (r.bottom - palco.top + 8) + "px";\n'
            '  }\n'
            '\n'
            '  document.addEventListener("keydown", function (ev) {\n'
            '    if (ev.key === "Escape" && editando) { editando = null; pint'
            'ar(); }\n'
            '  });\n'
            '\n'
            '  /* ══ TODA PALAVRA COM MAIÚSCULA — 26/09/2026 ════════════════'
            '════════════\n'
            '     Pedido dela: «Todas as palavras Iniciam com a letra maiúscu'
            'la». Os\n'
            '     conectivos ficam minúsculos no meio da frase, que é como el'
            'a mesma escreve\n'
            '     («Gestão de Controles», «Perfil de Desempenho»). Caminho d'
            'e barramento,\n'
            '     número e código não mudam. Roda no fim de cada pintura, sob'
            're a página\n'
            '     inteira, e é idempotente. */\n'
            '  var MINUSCULAS = ["a", "o", "as", "os", "e", "de", "da", "das"'
            ', "do", "dos", "em", "no", "na",\n'
            '    "nos", "nas", "num", "numa", "um", "uma", "para", "pra", "po'
            'r", "com", "ao", "à", "se", "ou"];\n'
            '  function emTitulo(raiz) {\n'
            '    if (!raiz) return;\n'
            '    var andar = document.createTreeWalker(raiz, NodeFilter.SHOW_'
            'TEXT, null), nos = [];\n'
            '    while (andar.nextNode()) nos.push(andar.currentNode);\n'
            '    nos.forEach(function (no) {\n'
            '      var pai = no.parentElement;\n'
            '      if (!pai || pai.closest("code, script, style, .caminho, .c'
            'hip .txt span")) return;\n'
            '      var abre = !no.previousSibling;\n'
            '      var novo = no.nodeValue.replace(/[^\\s—·,.;:()«»"→↳]+/g, fu'
            'nction (w, pos) {\n'
            '        if (!/^[A-Za-zÀ-ÿ]/.test(w)) return w;\n'
            '        /* começo de frase conta como primeira palavra: «Possíve'
            'is. O Melhor» */\n'
            '        var antes = no.nodeValue.slice(0, pos).trim();\n'
            '        var primeira = (abre && antes === "") || /[.!?]$/.test(a'
            'ntes);\n'
            '        if (!primeira && MINUSCULAS.indexOf(w.toLowerCase()) !=='
            ' -1) return w.toLowerCase();\n'
            '        /* cada pedaço de um nome com hífen: «Wi-Fi», «Entrada-F'
            'ilha» */\n'
            '        return w.split("-").map(function (s) { return s.charAt(0'
            ').toUpperCase() + s.slice(1); }).join("-");\n'
            '      });\n'
            '      if (novo !== no.nodeValue) no.nodeValue = novo;\n'
            '    });\n'
            '  }\n'
            '\n'
            '  function pintar() {\n'
            '    /* o hub nasce com o cinza da paleta (#6272a4), e o cinza da'
            ' letra saiu */\n'
            '    APARELHOS.forEach(function (a) { if (a.cor === "#6272a4") a.'
            'cor = "#f8f8f2"; });'
        ),
        porque=(
            '26/09/2026, pedidos dela: *«ao clicar em um desses usb mapeados '
            'eu pudesse setar que tem tal coisa lá»* e *«Todas as palavras In'
            'iciam com a letra maíscula»*.'
        ),
    ),
    Edicao(
        antes=(
            '[{"n": "1", "usb": 2, "onde": "pc", "par": "2"}, {"n": "2", "usb'
            '": 2, "onde": "pc", "par": "1"}]'
        ),
        depois=(
            '[{"n": "1", "usb": 3, "onde": "pc", "par": "2"}, {"n": "2", "usb'
            '": 3, "onde": "pc", "par": "1"}]'
        ),
        porque=(
            '26/09/2026, resposta dela: as duas entradas da frente são AZUIS '
            '(USB 3.0), e as 7 e 8 da traseira são pretas ou brancas (USB 2.0'
            '). O firmware dizia o contrário da frente; o desenho mostra o qu'
            'e ela declarou.'
        ),
    ),
    # ═══ O EDITOR GRAVA — 26/09/2026, O-MAPA-DAS-CONEXOES-NO-PRODUTO-01 ═══
    Edicao(
        antes=(
            '  var DECLARADO = {};\n'
            '  var editando = null;\n'
        ),
        depois=(
            '  var DECLARADO = {};\n'
            '  var editando = null;\n'
            '  /* O EDITOR GRAVA — 26/09/2026. `GRAVA` são as entradas do mapa de'
            ' quem abre,\n'
            '     entregues pelo produto em `hefestoArranjo`; só nelas o botão l'
            'eva o gesto\n'
            '     ao disco. No exemplo e nas entradas que o desenho monta do que'
            ' ela\n'
            '     declarou (as do hub, a ponta do extensor), o editor fica só na'
            ' tela. */\n'
            '  var GRAVA = [];\n'
            '  function gravaNaEntrada(n, gesto) {\n'
            '    if (GRAVA.indexOf(String(n)) === -1) return "";\n'
            '    return \' data-gesto="\' + gesto + \'" data-entrada="\' + n + \'"\';\n'
            '  }\n'
        ),
        porque=(
            '26/09/2026 — o que ela declara numa entrada do mapa dela vai ao `m'
            'aquina.json` (`pacotes/a12_mapa_das_portas.py`), e volta na próxi'
            'ma leitura pelo `f.declarado`.'
        ),
    ),
    Edicao(
        antes='data-liga="\' + o[0] + \'" aria-pressed="',
        depois=(
            'data-liga="\' + o[0] + \'"\' + gravaNaEntrada(editando, "entrada-o-que-tem")'
            ' + \' aria-pressed="'
        ),
        porque='26/09/2026 — «O que tem aqui» grava: o gesto `entrada-o-que-tem`.',
    ),
    Edicao(
        antes='data-usb="\' + o[0] + \'" aria-pressed="',
        depois=(
            'data-usb="\' + o[0] + \'"\' + gravaNaEntrada(editando, "entrada-velocidade")'
            ' + \' aria-pressed="'
        ),
        porque='26/09/2026 — «Velocidade» grava: o gesto `entrada-velocidade`.',
    ),
    # ═══ O EXEMPLO CONTINUA DIZENDO QUE É EXEMPLO — 26/09/2026 ═══
    # A conferência da O-MAPA-DAS-CONEXOES-NO-PRODUTO-01. O pedido dela
    # (*«leitura deste computador · 26/09/2026 03h13 essa info some»*) é sobre
    # a leitura DA MÁQUINA DELA, e a edição do cabeçalho tirou junto a única
    # defesa de 11/09: quem ainda não mapeou nada via o gabinete de exemplo
    # (os aparelhos de outra pessoa, «4 Coisas para Mudar de Lugar») sem nada
    # dizendo que não é o dele. A linha volta SÓ no exemplo: quando o produto
    # entrega a leitura desta máquina, ela sai da página.
    Edicao(
        antes=(
            '<h1>Mapa das <em>Conexões</em></h1>\n'
            '    <button class="btn examinar"'
        ),
        depois=(
            '<h1>Mapa das <em>Conexões</em></h1>\n'
            f'    <p class="quando" id="de-quando">{QUANDO_DO_EXEMPLO}</p>\n'
            '    <button class="btn examinar"'
        ),
        porque=(
            '26/09/2026 — o exemplo se diz exemplo no cabeçalho (a defesa de '
            '11/09), ao lado do «Examinar»; a leitura desta máquina não mostra '
            'a linha, que é o pedido dela.'
        ),
    ),
    Edicao(
        antes='  .topo .examinar span { pointer-events: none; }\n',
        depois=(
            '  .topo .examinar span { pointer-events: none; }\n'
            '  /* a linha do exemplo já empurra o «Examinar» para a direita */\n'
            '  .topo .quando + .examinar { margin-left: 0; }\n'
        ),
        porque='26/09/2026 — a linha do exemplo e o «Examinar» ficam juntos, à direita.',
    ),
    # ═══ O QUE A 01 DEIXOU — 26/09/2026, O-MAPA-DAS-CONEXOES-NO-PRODUTO-02 ═══
    # Os três buracos que a conferência da 01 mediu: o «Examinar» que dizia
    # sempre «Nada Mudou de Lugar», o hub oferecido onde há um aparelho direto
    # que não é hub (e a Sugestão mandando o dongle para dentro de um hub
    # desenhado), e as entradas desenhadas que editavam sem gravar.
    Edicao(
        antes=(
            '    if (ev.target.id === "reexaminar") {\n'
            '      /* relata a diferença; NÃO troca o que o mapa mostra */\n'
            '      modo = "reexame"; segurando = null; naMao = null; pintar(); return;\n'
            '    }\n'
        ),
        depois=(
            '    if (ev.target.id === "reexaminar") {\n'
            '      /* relata a diferença; NÃO troca o que o mapa mostra. No produto quem\n'
            '         abre o reexame é a leitura nova, que chega pelo `hefestoArranjo`. */\n'
            '      if (doProduto()) return;\n'
            '      modo = "reexame"; segurando = null; naMao = null; pintar(); return;\n'
            '    }\n'
        ),
        porque=(
            '26/09/2026 — o «Examinar» do produto espera a leitura nova: pintar o '
            'reexame no clique compararia a leitura da tela com ela mesma, e diria '
            '«Nada Mudou de Lugar» de quem mudou.'
        ),
    ),
    Edicao(
        antes=(
            '\'<div class="acoes"><button class="btn forte" id="reexaminar">Já movi — '
            'veja o que mudou</button>\''
        ),
        depois=(
            '\'<div class="acoes"><button class="btn forte" id="reexaminar"\' + '
            'examinaNoProduto() + \'>Já movi — veja o que mudou</button>\''
        ),
        porque=(
            '26/09/2026 — o «Já movi» das Sugestões é o mesmo «Examinar», e no '
            'produto leva o mesmo gesto.'
        ),
    ),
    Edicao(
        antes=(
            '                + \'<li><span class="selo medido">medido</span>'
            '<span>Estava em <code>\' '
            '+ m.antes + "</code>"\n'
            '                + (m.entradaAntes ? " (entrada <b>" + m.entradaAntes + "</b>)" : "")\n'
            '                + ", agora está em <code>" + m.agora + "</code>"\n'
        ),
        depois=(
            '                + \'<li><span class="selo medido">medido</span><span>\'\n'
            '                + (m.antes ? "Estava em <code>" + m.antes + "</code>"\n'
            '                    + (m.entradaAntes ? " (entrada <b>" '
            '+ m.entradaAntes + "</b>)" : "")\n'
            '                    + ", agora está em " : "Agora está em ")\n'
            '                + "<code>" + m.agora + "</code>"\n'
        ),
        porque=(
            '26/09/2026 — o aparelho que chegou depois da leitura anterior não '
            '«estava» em lugar nenhum: a frase dizia «Estava em undefined».'
        ),
    ),
    Edicao(
        antes=(
            '  function regiaoDoCaminho(c) {\n'
            '    var h = leitura()["hub"];\n'
            '    if (!h || !c) return null;\n'
            '    if (c.indexOf(h + ".") === 0) return "hub";\n'
            '    var mh = h.match(/^(\\d+)-(.+)$/), mc = c.match(/^(\\d+)-(.+)$/);\n'
            '    if (mh && mc && mc[1] !== mh[1] '
            '&& mc[2].indexOf(mh[2] + ".") === 0) return "hub";\n'
            '    return "pc";\n'
            '  }\n'
        ),
        depois=(
            '  function regiaoDoCaminho(c) {\n'
            '    /* O HUB É QUEM TEM A CLASSE DE HUB — 26/09/2026. Aqui se perguntava\n'
            '       pelo aparelho de id "hub", que só o exemplo tem: no produto a\n'
            '       resposta era sempre «não sei», e o reexame dizia «está direto no\n'
            '       gabinete» de quem estava no hub. */\n'
            '    var cam = leitura();\n'
            '    var hubs = APARELHOS.filter(function (a) { '
            'return a.classe === "hub" && cam[a.id]; })\n'
            '      .map(function (a) { return cam[a.id]; });\n'
            '    if (!hubs.length || !c) return null;\n'
            '    return hubs.some(function (h) {\n'
            '      if (c.indexOf(h + ".") === 0) return true;\n'
            '      var mh = h.match(/^(\\d+)-(.+)$/), mc = c.match(/^(\\d+)-(.+)$/);\n'
            '      return !!(mh && mc && mc[1] !== mh[1] && mc[2].indexOf(mh[2] + ".") === 0);\n'
            '    }) ? "hub" : "pc";\n'
            '  }\n'
        ),
        porque=(
            '26/09/2026 — o id do aparelho no produto não é "hub" (é a identidade '
            'estável, `arranjo_desta_maquina.identidades`): o hub se acha pela '
            'classe, e o exemplo, que tem um hub só, responde como antes.'
        ),
    ),
    Edicao(
        antes='  function planejar(op) {\n',
        depois=(
            '  /* O HUB DESENHADO — 26/09/2026. A face que o desenho monta de um hub\n'
            '     declarado (`daEntrada`) tem entradas que ninguém leu: o número e a\n'
            '     quantidade são do desenho. A Sugestão nunca manda um aparelho para\n'
            '     dentro delas. Medido: com o dongle direto na 5 e o hub declarado\n'
            '     na 5, ela mandava o dongle «da Entrada 5 para a 5.1». */\n'
            '  function doHubDesenhado(p) {\n'
            '    return FACES.some(function (f) {\n'
            '      return !!f.daEntrada && f.portas.some(function (x) { '
            'return x === p || x.filho === p; });\n'
            '    });\n'
            '  }\n'
            '\n'
            '  function planejar(op) {\n'
        ),
        porque='26/09/2026 — quem responde se uma entrada é do hub desenhado.',
    ),
    Edicao(
        antes=(
            '    var portas = todasPortas().filter(function (p) { return !proibida(p); });\n'
        ),
        depois=(
            '    var portas = todasPortas().filter(function (p) { return !proibida(p) && '
            '!doHubDesenhado(p); });\n'
        ),
        porque=(
            '26/09/2026 — a Sugestão nunca manda mover um aparelho para dentro de '
            'um hub desenhado.'
        ),
    ),
    Edicao(
        antes=(
            '  .edita .seg .escolha { justify-content: center; text-align: center; }\n'
        ),
        depois=(
            '  .edita .seg .escolha { justify-content: center; text-align: center; }\n'
            '  /* a escolha que não cabe: cinza, com a razão na dica, e responde (D-03) */\n'
            '  .edita .seg .escolha.apagado { opacity: .45; cursor: not-allowed; }\n'
            '  .edita .seg .escolha.apagado:hover { background: var(--color-paper-3); }\n'
        ),
        porque='26/09/2026 — a cara do «Hub» que não cabe na entrada.',
    ),
    Edicao(
        antes=(
            '          return \'<button class="escolha" data-liga="\' + o[0] + \'"\' + '
            'gravaNaEntrada(editando, "entrada-o-que-tem") + \' aria-pressed="\' + '
            '(liga === o[0]) + \'">\' + o[1] + "</button>";\n'
        ),
        depois=(
            '          /* O HUB NÃO CABE ONDE HÁ UM APARELHO DIRETO QUE NÃO É HUB: cinza,\n'
            '             com a razão na dica (a D-03 dela), e o clique não declara. */\n'
            '          if (o[0] === "hub" && quem && quem.classe !== "hub") {\n'
            '            return \'<button class="escolha apagado" data-liga="hub" '
            'aria-disabled="true" aria-pressed="\' + (liga === "hub")\n'
            '              + \'" title="\' + quem.tipo + \' Está Direto Nesta Entrada">\' + '
            'o[1] + "</button>";\n'
            '          }\n'
            '          return \'<button class="escolha" data-liga="\' + o[0] + \'"\' + '
            'gravaNaEntrada(editando, "entrada-o-que-tem") + \' aria-pressed="\' + '
            '(liga === o[0]) + \'">\' + o[1] + "</button>";\n'
        ),
        porque=(
            '26/09/2026 — medido: o dongle Bluetooth direto na 5, ela declara Hub '
            'na 5, e a página desenha um hub que não pode estar ali.'
        ),
    ),
    Edicao(
        antes=(
            '    if (lg) { declarar(editando, "liga", lg.getAttribute("data-liga")); '
            'pintar(); return; }\n'
        ),
        depois=(
            '    if (lg) {\n'
            '      /* o apagado responde e não declara: a razão está na dica */\n'
            '      if (lg.getAttribute("aria-disabled") !== "true") '
            'declarar(editando, "liga", lg.getAttribute("data-liga"));\n'
            '      pintar(); return;\n'
            '    }\n'
        ),
        porque='26/09/2026 — o clique no «Hub» cinza não declara um hub que não cabe.',
    ),
    Edicao(
        antes=(
            '  function gravaNaEntrada(n, gesto) {\n'
            '    if (GRAVA.indexOf(String(n)) === -1) return "";\n'
        ),
        depois=(
            '  /* A PONTA DO EXTENSOR GRAVA — 26/09/2026. A ponta de um extensor\n'
            '     declarado numa entrada que grava é a entrada-filha dele no disco\n'
            '     (`entrada_a_entrada.ponta_do_extensor`): o número puro mais «a». As\n'
            '     do hub desenhado (`5.1`…) não cabem no disco, e não gravam. */\n'
            '  function podeGravar(n) {\n'
            '    n = String(n);\n'
            '    if (GRAVA.indexOf(n) !== -1) return true;\n'
            '    var mae = maeDe(n);\n'
            '    return !!mae && /^[0-9]{1,3}$/.test(mae.n) && n === mae.n + "a"\n'
            '      && GRAVA.indexOf(mae.n) !== -1 && (DECLARADO[mae.n] || {}).liga '
            '=== "extensor";\n'
            '  }\n'
            '  function gravaNaEntrada(n, gesto) {\n'
            '    if (!podeGravar(n)) return "";\n'
        ),
        porque=(
            '26/09/2026 — o que ela declara na ponta do extensor vai ao disco, e '
            'volta ao reler.'
        ),
    ),
    Edicao(
        antes=(
            '    var quem = alocacao[editando] ? '  # (noqa-acento: JS)
            'acha(alocacao[editando]) : null;\n'  # (noqa-acento: JS)
            '    ed.innerHTML = \'<div class="edita-cab"><b>Entrada \' + editando + '
            '"</b><span>" + (face ? face.nome : "") + "</span>"\n'
            '      + \'<button class="btn fecha" id="edita-fecha" aria-label="Fechar">'
            '&times;</button></div>\'\n'
            '      + \'<div class="edita-linha"><span>O que tem aqui</span><div class="seg">\'\n'
        ),
        depois=(
            '    var quem = alocacao[editando] ? '  # (noqa-acento: JS)
            'acha(alocacao[editando]) : null;\n'  # (noqa-acento: JS)
            '    /* A ENTRADA QUE SÓ EXISTE NO DESENHO — 26/09/2026. No produto, o que\n'
            '       ela declarasse numa entrada que não grava (as do hub desenhado)\n'
            '       sumiria ao reler, sem aviso: ali o editor só mostra quem está\n'
            '       nela, e sem ninguém ele não abre. No exemplo, tudo é só tela. */\n'
            '    var soNaTela = doProduto() && !podeGravar(editando);\n'
            '    if (soNaTela && !quem) { ed.hidden = true; ed.innerHTML = ""; return; }\n'
            '    ed.innerHTML = \'<div class="edita-cab"><b>Entrada \' + editando + '
            '"</b><span>" + (face ? face.nome : "") + "</span>"\n'
            '      + \'<button class="btn fecha" id="edita-fecha" aria-label="Fechar">'
            '&times;</button></div>\'\n'
            '      + (soNaTela ? "" : \'<div class="edita-linha"><span>O que tem aqui'
            '</span><div class="seg">\'\n'
        ),
        porque=(
            '26/09/2026 — as entradas desenhadas editavam sem gravar: o que ela '
            'declarava ali sumia ao reabrir.'
        ),
    ),
    Edicao(
        antes=(
            '    if (!p || !plug || modo === "ideal" || segurando) { ed.hidden = true; return; }\n'
        ),
        depois=(
            '    /* o editor escondido não guarda os botões da entrada de antes: um\n'
            '       clique neles levaria ao disco o gesto de outra entrada */\n'
            '    if (!p || !plug || modo === "ideal" || segurando) { ed.hidden = true; '
            'ed.innerHTML = ""; return; }\n'
        ),
        porque=(
            '26/09/2026 — medido na régua que clica: com o editor escondido, o '
            'botão da entrada 5 continuava no DOM com o `data-entrada` dela.'
        ),
    ),
    Edicao(
        antes=(
            '      + "</div></div>"\n'
            '      + (quem ? \'<div class="edita-linha"><span>\''
        ),
        depois=(
            '      + "</div></div>")\n'
            '      + (quem ? \'<div class="edita-linha"><span>\''
        ),
        porque='26/09/2026 — fecha o `soNaTela` das duas linhas do editor.',
    ),
    Edicao(
        antes=(
            '+ \'<b style="color:var(--color-lacuna)">Por que \' + novos.length + '
            '" ficaram sem entrada</b>"'
        ),
        depois=(
            '+ \'<b style="color:var(--color-lacuna)">Por que \' + novos.length\n'
            '            + (novos.length > 1 ? " ficaram" : " ficou") + " sem entrada</b>"'
        ),
        porque=(
            '26/09/2026 — o reexame chega ao produto, e com um aparelho só a frase '
            'dizia «Por Que 1 Ficaram Sem Entrada».'
        ),
    ),
    # ══ O-MAPA-QUE-ELA-CORRIGE-01, 26/09/2026 ══════════════════════════════
    # Os pedidos dela, com o mapa aberto: renomear a entrada, trocar duas de
    # lugar, dizer onde fica o hub e corrigir a velocidade. As edições daqui
    # para baixo são desta sprint; o `porque` de cada uma diz o passo.
    Edicao(
        antes=(
            "    var lg = ev.target.closest(\"#edita [data-liga]\");\n"
            "    if (lg) {\n"
        ),
        depois=(
            "    var lg = ev.target.closest(\"#edita [data-liga]\");\n"
            "    /* A TELA ESPERA O DISCO — 26/09/2026, D-2609-A-TELA-DO-MAPA-ESPERA-O-DISCO.\n"
            "       O botão que leva o gesto ao disco não pinta nada aqui: ele fica\n"
            "       «em voo» (o carimbo do piloto), o produto grava e devolve o\n"
            "       arranjo relido, e a página repinta pelo que o disco diz. Uma\n"
            "       recusa não repinta, e a piscada acha o botão clicado. No\n"
            "       exemplo, sem produto, a pintura continua local. */\n"
            "    if (lg && lg.hasAttribute(\"data-gesto\")) return;\n"
            "    if (lg) {\n"
        ),
        porque='26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 0) — «O que tem aqui» espera o disco.',
    ),
    Edicao(
        antes="    var ub = ev.target.closest(\"#edita [data-usb]\");\n",
        depois=(
            "    var ub = ev.target.closest(\"#edita [data-usb]\");\n"
            "    if (ub && ub.hasAttribute(\"data-gesto\")) return;\n"
        ),
        porque='26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 0) — «Velocidade» espera o disco.',
    ),
    Edicao(
        antes=(
            "    var soltos = APARELHOS.filter(function (a) { return !portaDe(a.id); }).length;\n"
            "    document.getElementById(\"ajuda-bandeja\").textContent = segurando\n"
            "      ? \"Na mão: \" + acha(segurando).tipo + \". Clique a entrada em que ele vai.\"\n"
            "      : (soltos ? soltos + \" ainda sem lugar no mapa.\""
            " : \"O número é a entrada em que cada um está.\");\n"
        ),
        depois=(
            "    /* A DICA DIZ QUE A ENTRADA ABRE UM EDITOR — 26/09/2026: nada na tela\n"
            "       dizia, e ela nunca o achou. Quantos estão sem lugar já está no\n"
            "       painel («fora do mapa»). */\n"
            "    document.getElementById(\"ajuda-bandeja\").textContent = segurando\n"
            "      ? \"Na mão: \" + acha(segurando).tipo + \". Clique a entrada em que ele vai.\"\n"
            "      : \"Clique numa entrada para dar nome, corrigir ou trocar.\";\n"
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 0) — medido no diário '
            'dela: dois cliques no plugue e nenhuma escolha; a dica não dizia que '
            'ali há um editor.'
        ),
    ),
    # ══ O-MAPA-QUE-ELA-CORRIGE-01 (passo 2), 26/09/2026: o nome da entrada ══
    Edicao(
        antes="  var DECLARADO = {};\n  var editando = null;\n",
        depois=(
            "  var DECLARADO = {};\n"
            "  var editando = null;\n"
            "  /* O NOME DA ENTRADA — 26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (D1). Pedido\n"
            "     dela: «me referi as portas renomear». O nome é da POSIÇÃO, e quem o\n"
            "     compõe é o Python (`utils/rotulo_da_entrada`): o produto entrega os\n"
            "     `rotulos` no arranjo. A palavra de reserva é a do dono, que o gerador\n"
            "     escreve aqui; no exemplo, o nome é o que se digitou nesta tela. */\n"  # noqa-acento: citação literal dela
            "  var PALAVRA_DA_ENTRADA = "
            + json.dumps(PALAVRA_DA_ENTRADA, ensure_ascii=False) + ";\n"
            "  var PALAVRA_NA_FRASE = "
            + json.dumps(PALAVRA_NA_FRASE, ensure_ascii=False) + ";\n"
            "  var MAXIMO_DO_NOME = " + str(MAXIMO_DO_NOME_DA_ENTRADA) + ";\n"
            "  /* o nome da face de um hub declarado, no disco: o do dono */\n"
            "  var FACE_DO_HUB = "
            + json.dumps(FACE_DO_HUB_DECLARADO, ensure_ascii=False) + ";\n"
            "  var ROTULOS = {};\n"
            "  var HUB_LIDO = {};\n"
            "  var USB_DE = {};\n"
            "  var FRASES_DA_ORIGEM = "
            + json.dumps(FRASES_DA_ORIGEM_DA_VELOCIDADE, ensure_ascii=False) + ";\n"
            "  /* a origem só se diz no produto: no exemplo ninguém mediu nada */\n"
            "  function origemDaVelocidade(n) {\n"
            "    if (!doProduto() || !podeGravar(n)) return \"\";\n"
            "    var frase = FRASES_DA_ORIGEM[USB_DE[String(n)] || \"\"];\n"
            "    return frase ? '<span class=\"origem\">' + frase + \"</span>\" : \"\";\n"
            "  }\n"
            "  function rotuloDe(n) {\n"
            "    var r = ROTULOS[String(n)];\n"
            "    if (r) return r.rotulo;\n"
            "    return nomeDe(n) || PALAVRA_DA_ENTRADA + \" \" + n;\n"
            "  }\n"
            "  function nomeDe(n) { return (DECLARADO[n] || {}).nome || \"\"; }\n"
            "  /* o sintagma sem artigo, para o meio da frase: «Entrada 3», «entrada Meio» */\n"
            "  function naFraseDe(n) {\n"
            "    var r = ROTULOS[String(n)];\n"
            "    if (r) return r.naFrase;\n"
            "    var nome = nomeDe(n);\n"
            "    return nome ? PALAVRA_NA_FRASE + \" \" + nome : PALAVRA_DA_ENTRADA + \" \" + n;\n"
            "  }\n"
            "  function emAtributo(t) {\n"
            "    return String(t).replace(/&/g, \"&amp;\").replace(/\"/g, \"&quot;\")"
            ".replace(/</g, \"&lt;\");\n"
            "  }\n"
            "  function linhaDoNome(n) {\n"
            "    return '<div class=\"edita-linha\"><span>Nome</span>"
            "<input class=\"campo-nome\" type=\"text\"'\n"
            "      + ' data-nome=\"' + n + '\"' + gravaNaEntrada(n, \"entrada-nome\")\n"
            "      + ' maxlength=\"' + MAXIMO_DO_NOME + '\" value=\"'"
            " + emAtributo(nomeDe(n)) + '\"'\n"
            "      + ' placeholder=\"' + emAtributo(PALAVRA_DA_ENTRADA + \" \" + n)"
            " + '\" aria-label=\"Nome\"></div>';\n"
            "  }\n"
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 2) — o nome da entrada '
            'vem do dono, e o editor ganha o campo «Nome».'
        ),
    ),
    Edicao(
        antes=(
            "    ed.innerHTML = '<div class=\"edita-cab\"><b>Entrada ' + editando"
            " + \"</b><span>\" + (face ? face.nome : \"\") + \"</span>\"\n"
            "      + '<button class=\"btn fecha\" id=\"edita-fecha\" aria-label=\"Fechar\">"
            "&times;</button></div>'\n"
            "      + (soNaTela ? \"\" : '<div class=\"edita-linha\"><span>O que tem aqui"
            "</span><div class=\"seg\">'\n"
        ),
        depois=(
            "    ed.innerHTML = '<div class=\"edita-cab\"><b>' + emAtributo(rotuloDe(editando))"
            " + \"</b><span>\" + (face ? face.nome : \"\") + \"</span>\"\n"
            "      + '<button class=\"btn fecha\" id=\"edita-fecha\" aria-label=\"Fechar\">"
            "&times;</button></div>'\n"
            "      + (soNaTela ? \"\" : linhaDoNome(editando))\n"
            "      + (soNaTela ? \"\" : '<div class=\"edita-linha\"><span>O que tem aqui"
            "</span><div class=\"seg\">'\n"
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 2) — o cabeçalho do '
            'editor diz o nome dela, e o campo «Nome» vem antes do resto.'
        ),
    ),
    Edicao(
        antes=(
            "  document.addEventListener(\"keydown\", function (ev) {\n"
            "    if (ev.key === \"Escape\" && editando) { editando = null; pintar(); }\n"
            "  });\n"
        ),
        depois=(
            "  document.addEventListener(\"keydown\", function (ev) {\n"
            "    if (ev.key === \"Escape\" && editando) { editando = null; pintar(); }\n"
            "  });\n"
            "  /* O NOME, NO EXEMPLO — 26/09/2026. No produto o campo leva o gesto\n"
            "     `entrada-nome`, e a página espera o disco; aqui, sem produto, o nome\n"
            "     fica só na tela. */\n"
            "  document.addEventListener(\"change\", function (ev) {\n"
            "    var campo = ev.target.closest && ev.target.closest(\"#edita [data-nome]\");\n"
            "    if (!campo || campo.hasAttribute(\"data-gesto\")) return;\n"
            "    declarar(campo.getAttribute(\"data-nome\"), \"nome\","
            " campo.value.trim().slice(0, MAXIMO_DO_NOME));\n"
            "    pintar();\n"
            "  });\n"
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 2) — o nome no exemplo '
            'é só da tela.'
        ),
    ),
    Edicao(
        antes="  .edita .seg .escolha.apagado:hover { background: var(--color-paper-3); }\n",
        depois=(
            "  .edita .seg .escolha.apagado:hover { background: var(--color-paper-3); }\n"
            "  /* o nome da entrada: o campo tem fundo, cor e borda próprios — no\n"
            "     WebKitGTK o campo sem eles nasce com as cores do sistema */\n"
            "  .edita .campo-nome { font: inherit; font-size: var(--text-sm); width: 100%;\n"
            "                         box-sizing: border-box; padding: .35rem .5rem;\n"
            "                         background: var(--color-paper); color: var(--color-ink);\n"
            "                         border: 1px solid var(--color-rule);"
            " border-radius: var(--radius-sm); }\n"
            "  .edita .campo-nome:focus { outline: none; border-color: var(--color-accent); }\n"
        ),
        porque='26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 2) — o campo «Nome».',
    ),
    # ══ O-MAPA-QUE-ELA-CORRIGE-01 (passo 3), 26/09/2026: a entrada pelo dono ══
    Edicao(
        antes=(
            '          txt: "a entrada " + atual + " passou a ser do " + '
            '(acha(plano[atual]) || {}).tipo + ", entao este precisa de o'
            'utro lugar" });\n'
            '        motivo[ap.id] = {'
        ),
        depois=(
            '          txt: "a " + naFraseDe(atual) + " passou a ser do "'
            ' + (acha(plano[atual]) || {}).tipo + ", entao este precisa d'
            'e outro lugar" });\n'
            '        motivo[ap.id] = {'
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 3) — a razão da'
            ' entrada tomada diz o nome dela.'
        ),
    ),
    Edicao(
        antes=(
            '          txt: "a entrada " + atual + " passou a ser do " + '
            '(acha(plano[atual]) || {}).tipo + ", entao este precisa de o'
            'utro lugar" });\n'
            '        motivo[a.id] = {'
        ),
        depois=(
            '          txt: "a " + naFraseDe(atual) + " passou a ser do "'
            ' + (acha(plano[atual]) || {}).tipo + ", entao este precisa d'
            'e outro lugar" });\n'
            '        motivo[a.id] = {'
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 3) — a razão da'
            ' entrada tomada diz o nome dela (a variante).'
        ),
    ),
    Edicao(
        antes=(
            '        txt: "a entrada " + de + " passou a ser do " + (acha'
            '(plano[de]) || {}).tipo + ", entao este precisa de outro lug'
            'ar" });\n'
        ),
        depois=(
            '        txt: "a " + naFraseDe(de) + " passou a ser do " + (a'
            'cha(plano[de]) || {}).tipo + ", entao este precisa de outro '
            'lugar" });\n'
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 3) — a razão da'
            ' entrada tomada diz o nome dela (a receita).'
        ),
    ),
    Edicao(
        antes=(
            '        titulo: (function (r) { return de ? "Mova " + r.g + '
            '" " + r.n + " da entrada " + de + " para a " + para\n'
            '                                     : "Ponha " + r.g + " " '
            '+ r.n + " na entrada " + para; })(rot(a))\n'
        ),
        depois=(
            '        titulo: (function (r) { return de ? "Mova " + r.g + '
            '" " + r.n + " da " + naFraseDe(de) + " para a " + naFraseDe('
            'para)\n'
            '                                     : "Ponha " + r.g + " " '
            '+ r.n + " na " + naFraseDe(para); })(rot(a))\n'
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 3) — o moviment'
            'o diz as duas entradas pelo nome.'
        ),
    ),
    Edicao(
        antes=(
            '      if (vzRadio) return { v: "evite", txt: "vale evitar", '
            'porque: "colada no " + vz.tipo + ", na entrada " + porta.par'
            ' };\n'
            '      if (porta.esticada) return { v: "melhor"'
        ),
        depois=(
            '      if (vzRadio) return { v: "evite", txt: "vale evitar", '
            'porque: "colada no " + vz.tipo + ", na " + naFraseDe(porta.p'
            'ar) };\n'
            '      if (porta.esticada) return { v: "melhor"'
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 3) — a vizinha '
            'colada diz o nome da entrada (o adaptador).'
        ),
    ),
    Edicao(
        antes=(
            '      if (vzRadio) return { v: "evite", txt: "vale evitar", '
            'porque: "colada no " + vz.tipo + ", na entrada " + porta.par'
            ' };\n'
            '      return { v: "melhor", txt: "melhor lugar", porque: "az'
            'ul,'
        ),
        depois=(
            '      if (vzRadio) return { v: "evite", txt: "vale evitar", '
            'porque: "colada no " + vz.tipo + ", na " + naFraseDe(porta.p'
            'ar) };\n'
            '      return { v: "melhor", txt: "melhor lugar", porque: "az'
            'ul,'
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 3) — a vizinha '
            'colada diz o nome da entrada (o Wi-Fi).'
        ),
    ),
    Edicao(
        antes=(
            '      if (vzRadio) return { v: "evite", txt: "vale evitar", '
            'porque: "colada no " + vz.tipo + ", na entrada " + porta.par'
            ' };\n'
            '      return { v: "melhor", txt: "melhor lugar", porque: "di'
            'reta do PC'
        ),
        depois=(
            '      if (vzRadio) return { v: "evite", txt: "vale evitar", '
            'porque: "colada no " + vz.tipo + ", na " + naFraseDe(porta.p'
            'ar) };\n'
            '      return { v: "melhor", txt: "melhor lugar", porque: "di'
            'reta do PC'
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 3) — a vizinha '
            'colada diz o nome da entrada (o teclado).'
        ),
    ),
    Edicao(
        antes=(
            '      if (vzRadio) return { v: "evite", txt: "vale evitar", '
            'porque: "colada no " + vz.tipo + ", na entrada " + porta.par'
            ' };\n'
            '      if (noHub && superspeedNoHub()) return { v: "evite", t'
            'xt: "vale evitar", porque: "hub com'
        ),
        depois=(
            '      if (vzRadio) return { v: "evite", txt: "vale evitar", '
            'porque: "colada no " + vz.tipo + ", na " + naFraseDe(porta.p'
            'ar) };\n'
            '      if (noHub && superspeedNoHub()) return { v: "evite", t'
            'xt: "vale evitar", porque: "hub com'
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 3) — a vizinha '
            'colada diz o nome da entrada (o mouse).'
        ),
    ),
    Edicao(
        antes=(
            '        return { id: a.id, entrada: p, rotulo: p ? "entrada '
            '" + p : "entrada por confirmar" };\n'
        ),
        depois=(
            '        return { id: a.id, entrada: p, rotulo: p ? naFraseDe'
            '(p) : "entrada por confirmar" };\n'
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 3) — o adaptado'
            'r diz a entrada em que está pelo nome.'
        ),
    ),
    Edicao(
        antes='        porque = de ? "estava na entrada " + de : "ainda sem lugar";\n',
        depois='        porque = de ? "estava na " + naFraseDe(de) : "ainda sem lugar";\n',
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 3) — o plano di'
            'z de onde veio pelo nome.'
        ),
    ),
    Edicao(
        antes='        porque = "vai para a entrada " + portaDeEm(ctx.plano, idAgora);\n',
        depois='        porque = "vai para a " + naFraseDe(portaDeEm(ctx.plano, idAgora));\n',
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 3) — o plano di'
            'z para onde vai pelo nome.'
        ),
    ),
    Edicao(
        antes=(
            '    var titulo = ap ? ap.tipo + " — " + ap.nome : "entrada "'
            ' + porta.n + ", vazia";\n'
        ),
        depois='    var titulo = ap ? ap.tipo + " — " + ap.nome : rotuloDe(porta.n) + ", vazia";\n',
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 3) — a dica do '
            'plugue vazio diz o nome da entrada.'
        ),
    ),
    Edicao(
        antes=(
            '    if (ap) {\n'
            '      h += \'<b class="nome" style="color:\' + ap.cor + \'">\' +'
            ' ap.tipo'
        ),
        depois=(
            '    /* O NOME QUE ELA DEU, na primeira linha do rótulo — cor'
            'tado com\n'
            '       reticências, e inteiro na dica. O selo `.num` continu'
            'a o número:\n'
            '       é o do metal. */\n'
            '    var batismo = nomeDe(porta.n);\n'
            '    if (batismo) h += \'<span class="nomeada" title="\' + emAt'
            'ributo(batismo) + \'">\'\n'
            "      + emAtributo(batismo) + '</span>';\n"
            '    if (ap) {\n'
            '      h += \'<b class="nome" style="color:\' + ap.cor + \'">\' +'
            ' ap.tipo'
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 3) — o plugue m'
            'ostra o nome que ela deu à entrada.'
        ),
    ),
    Edicao(
        antes='  .rotulo .vazio { color: var(--color-ink-faint); font-style: italic; }\n',
        depois=(
            '  .rotulo .vazio { color: var(--color-ink-faint); font-style'
            ': italic; }\n'
            '  /* o nome que ela deu à entrada: uma linha só, com reticên'
            'cias */\n'
            '  .rotulo .nomeada { display: block; font-weight: 700; white'
            '-space: nowrap;\n'
            '                     overflow: hidden; text-overflow: ellips'
            'is; }\n'
        ),
        porque='26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 3) — a linha do nome no plugue.',
    ),
    Edicao(
        antes='      FACES.push({ nome: "Hub na Entrada " + n,',
        depois='      FACES.push({ nome: FACE_DO_HUB.replace("{numero}", n),',
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 3) — o nome da face do '
            'hub é o do dono (`FACE_DO_HUB_DECLARADO`), e a página não compõe a '
            'palavra.'
        ),
    ),
    # ══ O-MAPA-QUE-ELA-CORRIGE-01 (passo 4), 26/09/2026: «Trocar com…» ══
    Edicao(
        antes=(
            '      + (quem ? \'<div class="edita-linha"><span>\' + quem.tipo + \' '
            "está aqui</span>'\n"
            '          + \'<button class="btn" data-tirar="\' + editando + \'">Mud'
            'ar de entrada</button></div>\' : "");\n'
        ),
        depois=(
            '      + (quem ? \'<div class="edita-linha"><span>\' + quem.tipo + \' '
            'está aqui</span></div>\' : "")\n'
            '      + (soNaTela ? "" : linhaDaTroca(editando));\n'
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 4) — «Mudar de Entrad'
            'a» sai: o ato dele é o «Trocar com…», que grava.'
        ),
    ),
    Edicao(
        antes=(
            '    var tb = ev.target.closest("#edita [data-tirar]");\n'
            '    if (tb) {\n'
            '      /* «Mudar de Entrada» é o que o clique no plugue ocupado faz'
            'ia antes:\n'
            '         a entrada deixa de ser dele, e ele fica na mão até ela di'
            'zer onde está. */\n'
            '      var nt = tb.getAttribute("data-tirar"), quemT = acha(alocaca'
            'o[nt]);\n'
            '      delete MAPA[nt]; editando = null;\n'
            '      segurando = quemT.id; modo = "mao";\n'  # (noqa-acento: JS)
            '      naMao = ({ bt: "bt", wifi: "wifi", teclado: "teclado", mouse'
            ': "mouse", webcam: "webcam" })[quemT.classe] || null;\n'
            '      pintar(); return;\n'
            '    }\n'
        ),
        depois="",
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 4) — o botão «Mudar d'
            'e Entrada» saiu, e o ouvinte dele junto.'
        ),
    ),
    Edicao(
        antes=(
            '  function linhaDoNome(n) {\n'
        ),
        depois=(
            '  /* «TROCAR COM…» — 26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (D-2609'
            '-TROCAR-MOVE-\n'
            '     O-BURACO). Pedido dela: «trocar elas de lugar no mapeamento».'
            ' Só nas\n'
            '     entradas que gravam, sem as pontas; cada opção diz o nome, a '
            'face e o que\n'
            '     está nela. O produto troca o buraco das duas, e a página repi'
            'nta pelo\n'
            '     disco. */\n'
            '  function faceDe(m) {\n'
            '    var f = FACES.filter(function (x) {\n'
            '      return x.portas.some(function (q) { return q.n === m || (q.f'
            'ilho && q.filho.n === m); });\n'
            '    })[0];\n'
            '    return f ? f.nome : "";\n'
            '  }\n'
            '  function linhaDaTroca(n) {\n'
            '    if (GRAVA.indexOf(String(n)) === -1 || !/^[0-9]{1,3}$/.test(St'
            'ring(n))) return "";\n'
            '    var outras = GRAVA.filter(function (m) { return m !== String(n'
            ') && /^[0-9]{1,3}$/.test(m); });\n'
            '    if (!outras.length) return "";\n'
            '    return \'<div class="edita-linha"><span>Trocar de lugar</span>\''
            '\n'
            '      + \'<select class="troca" data-gesto="entrada-trocar" data-en'
            'trada="\' + n + \'">\'\n'
            '      + \'<option value="">Trocar com…</option>\'\n'
            '      + outras.map(function (m) {\n'
            '          var ali = alocacao[m] ? acha(alocacao[m]) : null;\n'  # (noqa-acento: JS)
            '          var partes = [rotuloDe(m), faceDe(m), ali ? ali.tipo : "'
            'vazia"].filter(Boolean);\n'
            '          return \'<option value="\' + m + \'">\' + emAtributo(partes.'
            'join(" · ")) + "</option>";\n'
            '        }).join("")\n'
            '      + "</select></div>";\n'
            '  }\n'
            '  function linhaDoNome(n) {\n'
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 4) — a linha «Trocar '
            'de lugar» do editor.'
        ),
    ),
    Edicao(
        antes=(
            '    var chip = ev.target.closest(".chip[data-ap]");\n'
            '    if (chip) {\n'
            '      modo = "mao";\n'  # (noqa-acento: JS)
        ),
        depois=(
            '    var chip = ev.target.closest(".chip[data-ap]");\n'
            '    /* NO PRODUTO, O APARELHO QUE JÁ ESTÁ NUMA ENTRADA abre o edit'
            'or dela: quem\n'
            '       corrige ali é o «Trocar com…» (um ato por porta). O que não'
            ' está em\n'
            '       entrada nenhuma continua indo para a mão, para ser ensinado'
            '. */\n'
            '    if (chip && doProduto() && portaDe(chip.getAttribute("data-ap"'
            '))) {\n'
            '      editando = portaDe(chip.getAttribute("data-ap")); modo = "me'
            'sa";\n'
            '      segurando = null; naMao = null; pintar(); return;\n'
            '    }\n'
            '    if (chip) {\n'
            '      modo = "mao";\n'  # (noqa-acento: JS)
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 4) — o chip do aparel'
            'ho que já está numa entrada abre o editor dela.'
        ),
    ),
    Edicao(
        antes=(
            '  .edita .campo-nome:focus { outline: none; border-color: var(--co'
            'lor-accent); }\n'
        ),
        depois=(
            '  .edita .campo-nome:focus { outline: none; border-color: var(--co'
            'lor-accent); }\n'
            '  /* a lista da troca: fundo, cor e borda próprios (no WebKitGTK o'
            ' que não\n'
            '     os tem nasce cinza) */\n'
            '  .edita .troca { font: inherit; font-size: var(--text-sm); width:'
            ' 100%;\n'
            '                  box-sizing: border-box; padding: .3rem .4rem;\n'
            '                  background: var(--color-paper); color: var(--col'
            'or-ink);\n'
            '                  border: 1px solid var(--color-rule); border-radi'
            'us: var(--radius-sm); }\n'
            '  .edita .troca option { background: var(--color-paper); color: va'
            'r(--color-ink); }\n'
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 4) — a lista «Trocar '
            'com…».'
        ),
    ),
    Edicao(
        antes=(
            '  .edita .troca option { background: var(--color-paper); color: va'
            'r(--color-ink); }\n'
        ),
        depois=(
            '  .edita .troca option { background: var(--color-paper); color: va'
            'r(--color-ink); }\n'
            '  /* O NOME COMPRIDO NO CABEÇALHO — 26/09/2026: a face desce inteira'
            ' para a\n'
            '     linha de baixo quando não cabe ao lado do nome, e o «Fechar» fica no'
            ' canto. */\n'
            '  .edita-cab { flex-wrap: wrap; position: relative; padding-right: '
            '2.2rem; row-gap: .1rem; }\n'
            '  .edita-cab span { white-space: nowrap; }\n'
            '  .edita-cab .fecha { position: absolute; top: 0; right: 0; }\n'
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (a conferência) — com um nome'
            ' de 24 letras o nome e a face quebravam cada um em duas linhas, lado'
            ' a lado; a sprint pede que a face desça para uma linha própria.'
        ),
    ),
    Edicao(
        antes='no.nodeValue.replace(/[^\\s—·,.;:()«»"→↳]+/g',
        depois='no.nodeValue.replace(/[^\\s—·,.;:()«»"→↳…]+/g',
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 4) — as reticências '
            'separam a palavra: «Trocar com…» não vira «Trocar Com…».'
        ),
    ),
    # ══ O-MAPA-QUE-ELA-CORRIGE-01 (passo 5), 26/09/2026: onde fica o hub ══
    Edicao(
        antes=(
            '      return \'<div><div class="face-cab"><h3>\' + f.nome + \'</h3><s'
            'pan class="quantas">\' + cheias + " de " + total + " ocupadas</span'
            '></div>"\n'
        ),
        depois=(
            '      /* A FACE DIZ DE QUAL ENTRADA PENDE (D-2609-O-HUB-PENDE-DA-E'
            'NTRADA): o\n'
            '         título é do dono («Hub na Entrada 3»), e a divergência é '
            'uma linha\n'
            '         a mais, sem culpa. */\n'
            '      return \'<div><div class="face-cab"><h3>\' + (f.titulo || f.no'
            'me) + \'</h3><span class="quantas">\' + cheias + " de " + total + " '
            'ocupadas</span></div>"\n'
            '        + (f.diverge ? \'<p class="diverge">\' + f.diverge + "</p>" : "")\n'
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 5) — a face do hub di'
            'z de qual entrada pende.'
        ),
    ),
    Edicao(
        antes=(
            '    if (DECLARADO[porta.n] && DECLARADO[porta.n].liga === "hub") h'
            ' += \'<span class="decl">hub</span>\';\n'
        ),
        depois=(
            '    if ((DECLARADO[porta.n] && DECLARADO[porta.n].liga === "hub") '
            '|| HUB_LIDO[porta.n]) h += \'<span class="decl">hub</span>\';\n'
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 5) — o plugue da entr'
            'ada em que o computador lê um hub ganha a marca.'
        ),
    ),
    Edicao(
        antes=(
            '    FACES = FACES.filter(function (f) { return f.daEntrada !== Str'
            'ing(n); });\n'
            '    delete p.filho;\n'
            '    if (valor === "hub") {\n'
            '      FACES.push({ nome: FACE_DO_HUB.replace("{numero}", n), forma'
            ': "fileira", regiao: "hub", daEntrada: String(n),\n'
        ),
        depois=(
            '    /* A DEDUPLICAÇÃO É PELA LIGAÇÃO (D-2609-O-HUB-PENDE-DA-ENTRAD'
            'A): só a face\n'
            '       de quatro buracos que ESTA tela desenhou sai; a face ligada'
            ' à entrada\n'
            '       fica, e o hub dela não ganha uma segunda. */\n'
            '    FACES = FACES.filter(function (f) { return !(f.fantasma && f.d'
            'aEntrada === String(n)); });\n'
            '    delete p.filho;\n'
            '    var ligada = FACES.some(function (f) { return f.daEntrada === '
            'String(n); });\n'
            '    if (valor === "hub" && !ligada) {\n'
            '      FACES.push({ nome: FACE_DO_HUB.replace("{numero}", n), titul'
            'o: "Hub na " + naFraseDe(n),\n'
            '        fantasma: true, forma: "fileira", regiao: "hub", daEntrada'
            ': String(n),\n'
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 5) — o hub declarado '
            'na tela não duplica a face ligada.'
        ),
    ),
    Edicao(
        antes=(
            '    var liga = (DECLARADO[editando] || {}).liga || "direto";\n'
        ),
        depois=(
            '    /* O COMPUTADOR LÊ UM HUB NESTA ENTRADA: «Hub» nasce apertado,'
            ' e «Direto»\n'
            '       fica apagado com a razão na dica (o espelho da D-03). */\n'
            '    var lido = !!HUB_LIDO[editando];\n'
            '    var liga = (DECLARADO[editando] || {}).liga || (lido ? "hub" :'
            ' "direto");\n'
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 5) — o editor da entr'
            'ada em que o computador lê um hub.'
        ),
    ),
    Edicao(
        antes=(
            '          if (o[0] === "hub" && quem && quem.classe !== "hub") {\n'
        ),
        depois=(
            '          if (o[0] === "direto" && lido) {\n'
            '            return \'<button class="escolha apagado" data-liga="dir'
            'eto" aria-disabled="true" aria-pressed="false"\'\n'
            '              + \' title="O computador lê um hub nesta entrada">\' +'
            ' o[1] + "</button>";\n'
            '          }\n'
            '          if (o[0] === "hub" && quem && quem.classe !== "hub" && !'
            'lido) {\n'
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 5) — «Direto» apagado'
            ' onde o computador lê um hub.'
        ),
    ),
    Edicao(
        antes=(
            '        }).join("")\n'
            '      + "</div></div>"\n'
            '      + \'<div class="edita-linha"><span>Velocidade</span>'
        ),
        depois=(
            '        }).join("")\n'
            '      + "</div>" + (lido ? \'<span class="lido">O computador lê um '
            'hub nela.</span>\' : "") + "</div>"\n'
            '      + \'<div class="edita-linha"><span>Velocidade</span>'
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 5) — a linha que diz '
            'por que «Hub» nasce apertado.'
        ),
    ),
    Edicao(
        antes=(
            '  .face-cab .quantas { font-size: var(--text-xs); color: var(--col'
            'or-ink-faint); font-family: var(--font-dado); }\n'
        ),
        depois=(
            '  .face-cab .quantas { font-size: var(--text-xs); color: var(--col'
            'or-ink-faint); font-family: var(--font-dado); }\n'
            '  /* a divergência do hub: uma linha a mais, sem culpa */\n'
            '  .diverge { margin: 0 0 var(--space-2xs); font-size: var(--te'
            'xt-xs); color: var(--color-lacuna); }\n'
            '  .edita .lido { font-size: var(--text-xs); color: var(--color-ink'
            '-quiet); }\n'
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 5) — a linha da diver'
            'gência e a do editor.'
        ),
    ),
    # ══ O-MAPA-QUE-ELA-CORRIGE-01 (passo 6), 26/09/2026: de onde veio a velocidade ══
    Edicao(
        antes=(
            'gravaNaEntrada(editando, "entrada-velocidade") + \' aria-pressed="\''
            ' + (p.usb === o[0]) + \'">\' + o[1] + "</button>";\n'
            '        }).join("")\n'
            '      + "</div></div>")\n'
        ),
        depois=(
            'gravaNaEntrada(editando, "entrada-velocidade") + \' aria-pressed="\''
            ' + (p.usb === o[0]) + \'">\' + o[1] + "</button>";\n'
            '        }).join("")\n'
            '      + "</div>" + origemDaVelocidade(editando) + "</div>")\n'
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 6) — a linha de baixo'
            ' de «Velocidade» diz de onde ela veio.'
        ),
    ),
    Edicao(
        antes=(
            '  .edita .lido { font-size: var(--text-xs); color: var(--color-ink'
            '-quiet); }\n'
        ),
        depois=(
            '  .edita .lido { font-size: var(--text-xs); color: var(--color-ink'
            '-quiet); }\n'
            '  .edita .origem { font-size: var(--text-xs); color: var(--color-i'
            'nk-quiet); }\n'
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 6) — a linha da orige'
            'm.'
        ),
    ),
    # ══ O-MAPA-QUE-ELA-CORRIGE-01 (passo 7), 26/09/2026: ensinar grava o nó ══
    Edicao(
        antes=(
            '  function gravaNaEntrada(n, gesto) {\n'
            '    if (!podeGravar(n)) return "";\n'
            '    return \' data-gesto="\' + gesto + \'" data-entrada="\' + n + \'"\';'
            '\n'
            '  }\n'
        ),
        depois=(
            '  function gravaNaEntrada(n, gesto) {\n'
            '    if (!podeGravar(n)) return "";\n'
            '    return \' data-gesto="\' + gesto + \'" data-entrada="\' + n + \'"\';'
            '\n'
            '  }\n'
            '  /* O PLUGUE QUE APRENDE — 26/09/2026, D-2609-ENSINAR-GRAVA-O-NO.'
            ' Com um\n'
            '     aparelho fora do mapa na mão, a entrada livre do mapa dela le'
            'va o\n'
            '     gesto `entrada-ensinar` e o caminho em que a página lê o apar'
            'elho\n'
            '     agora; o produto grava o nó dele na entrada. Só as do disco\n'
            '     (`GRAVA`): a ponta e o hub desenhado não têm nó a gravar. E só\n'
            '     as que acendem: a ocupada e a de «outra região» (o aparelho\n'
            '     direto no PC não está num buraco do hub) ficam sem o gesto. */\n'
            '  function ensinaNaEntrada(porta) {\n'
            '    if (!segurando || !doProduto() || GRAVA.indexOf(String(porta.n'
            ')) === -1) return "";\n'
            '    var c = leitura()[segurando], j = julgar(porta);\n'
            '    if (!c || (j && (j.v === "cheia" || j.v === "fora"))) return "";\n'
            '    return \' data-gesto="entrada-ensinar" data-entrada="\' + porta.'
            'n\n'
            '      + \'" data-caminho="\' + emAtributo(c) + \'"\';\n'
            '  }\n'
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 7) — o plugue candida'
            'to leva o gesto de ensinar.'
        ),
    ),
    Edicao(
        antes=(
            '      + \' aria-label="\' + titulo + \'" title="\' + titulo + \'"></but'
            'ton><span class="rotulo">\';\n'
        ),
        depois=(
            '      + ensinaNaEntrada(porta)\n'
            '      + \' aria-label="\' + titulo + \'" title="\' + titulo + \'"></but'
            'ton><span class="rotulo">\';\n'
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 7) — o plugue do soqu'
            'ete diz o gesto.'
        ),
    ),
    Edicao(
        antes=(
            '      if (segurando) {\n'
            '        if (ocupada(alocacao, p)) return;\n'  # (noqa-acento: JS)
        ),
        depois=(
            '      if (segurando) {\n'
            '        /* NO PRODUTO A PÁGINA ESPERA O DISCO (D-2609-ENSINAR-GRAV'
            'A-O-NO): o\n'
            '           plugue candidato levou o gesto, e o arranjo relido tira'
            ' o\n'
            '           aparelho da mão. A entrada que não grava não aprende: o'
            ' que\n'
            '           ficava só na memória a releitura desfazia. */\n'
            '        if (doProduto()) return;\n'
            '        if (ocupada(alocacao, p)) return;\n'  # (noqa-acento: JS)
        ),
        porque=(
            '26/09/2026, O-MAPA-QUE-ELA-CORRIGE-01 (passo 7) — no produto o cli'
            'que não ensina na memória.'
        ),
    ),
    Edicao(
        antes=(
            '        : "Nada a mudar de lugar") + "</p>"\n'
            '        + \'<p class="fina">\'\n'
            '        + (leituraAtual === "agora" ? "" : \'<b style="color:var(--color-'
            'lacuna)">leitura antiga</b> · \')\n'
            '        + Object.keys(MAPA).length + " de " + todasPortas().length + " e'
            'ntradas mapeadas"\n'
            '        + (sem.length ? \' · <b style="color:var(--color-lacuna)">\' + sem'
            '.length + " aparelho"\n'
            '            + (sem.length > 1 ? "s" : "") + " fora do mapa</b>" : "")\n'
            '        + (pend ? \' · clique em <b style="color:var(--color-ok)">Sugestõ'
            'es</b>\' : "")\n'
            '        + "</p>";\n'
        ),
        depois=(
            '        : "Nada a mudar de lugar")\n'
            '        + \' <span class="fina">\'\n'
            '        + (leituraAtual === "agora" ? "" : \'<b style="color:var(--color-'
            'lacuna)">leitura antiga</b> · \')\n'
            '        + Object.keys(MAPA).length + " de " + todasPortas().length + " e'
            'ntradas mapeadas"\n'
            '        + (sem.length ? \' · <b style="color:var(--color-lacuna)">\' + sem'
            '.length + " aparelho"\n'
            '            + (sem.length > 1 ? "s" : "") + " fora do mapa</b>" : "")\n'
            '        + (pend ? \' · clique em <b style="color:var(--color-ok)">Sugestõ'
            'es</b>\' : "")\n'
            '        + "</span></p>";\n'
        ),
        porque=(
            '01/10/2026, O-MAPA-DAS-CONEXOES-CABE-NA-ABA-E-FALA-MENOS-01 — o resumo d'
            'o Atual numa linha: o «N de M entradas mapeadas» entra no mesmo parágraf'
            'o da chamada, num `span.fina` (pedido c).'
        ),
    ),
    Edicao(
        antes=(
            '  .painel .fina { margin: .35rem 0 0; font-size: var(--text-sm); }\n'
        ),
        depois=(
            '  .painel span.fina { margin-left: .8rem; font-weight: 400; font-size: v'
            'ar(--text-sm); }\n'
        ),
        porque=(
            '01/10/2026, O-MAPA-DAS-CONEXOES-CABE-NA-ABA-E-FALA-MENOS-01 — a folha do'
            ' resumo em uma linha (pedido c).'
        ),
    ),
    Edicao(
        antes=(
            '  .chapa.grade-tras { grid-template-columns: repeat(2, 17rem); }\n'
            '  .chapa.fileira { grid-template-columns: repeat(3, 17rem); }\n'
            '  .palco > .bandeja { margin-top: 29px; position: sticky; top: .5rem; }\n'
            '  @media (max-width: 640px) {\n'
            '    .chapa.fileira, .chapa.grade-tras { grid-template-columns: minmax(0,'
            ' 1fr); }\n'
            '    .modos { grid-template-columns: repeat(3, minmax(0, 1fr)); }\n'
            '    .palco > .bandeja { margin-top: 0; position: static; }\n'
            '  }\n'
            '</style>\n'
        ),
        depois=(
            '  /* AS ENTRADAS SE ARRUMAM SOZINHAS — 01/10/2026 (pedido d): quantas co'
            'lunas de\n'
            '     17rem couberem, nas três formas; a Frente vira uma linha, e o hub, '
            'duas. */\n'
            '  .chapa.coluna, .chapa.grade-tras, .chapa.fileira {\n'
            '    display: grid; grid-template-columns: repeat(auto-fill, 17rem); gap:'
            ' .55rem var(--space-md); }\n'
            '  /* A LEGENDA SOBE para a linha dos modos, à direita (pedido e) */\n'
            '  .pagina > .corpo { display: grid; grid-template-columns: auto minmax(0'
            ', 1fr);\n'
            '                     column-gap: var(--space-md); align-content: start; '
            '}\n'
            '  .pagina > .corpo > * { grid-column: 1 / -1; }\n'
            '  .pagina > .corpo > .modos { grid-column: 1; grid-row: 1; }\n'
            '  .pagina > .corpo > .legenda { grid-column: 2; grid-row: 1; justify-sel'
            'f: end;\n'
            '                                align-self: center; margin-top: 0; }\n'
            '  .palco > .bandeja { margin-top: 29px; position: sticky; top: .5rem; }\n'
            '  /* «ATUALMENTE CONECTADO» ROLA POR DENTRO e acaba no fim da última fac'
            'e (pedido a).\n'
            '     Só com o palco em duas colunas: numa coluna só a bandeja tem linha '
            'própria,\n'
            '     e a altura da linha seria zero. */\n'
            '  @media (min-width: 901px) {\n'
            '    .palco > .bandeja { position: static; align-self: stretch; height: 0'
            ';\n'
            '                        min-height: calc(100% - 29px); box-sizing: borde'
            'r-box;\n'
            '                        display: flex; flex-direction: column; }\n'
            '    .palco > .bandeja .lista { flex: 1 1 0; min-height: 0; overflow-y: a'
            'uto; }\n'
            '  }\n'
            '  @media (max-width: 900px) {\n'
            '    .palco > .bandeja .lista { max-height: 22rem; overflow-y: auto; }\n'
            '  }\n'
            '  /* O ADICIONAR NUMA LINHA: a pergunta e as escolhas lado a lado (pedid'
            'o g) */\n'
            '  .painel > #chamada-mao { display: inline-block; margin: 0 var(--space-'
            'sm) 0 0;\n'
            '                           vertical-align: middle; }\n'
            '  .painel > #chamada-mao + .escolhas { display: inline-flex; vertical-al'
            'ign: middle; }\n'
            '  /* O «?» DA CASA: a razão de cada movimento das Sugestões mora nele (p'
            'edido f).\n'
            '     O `p.ajuda` da bandeja é outra peça: a regra mora só dentro da rece'
            'ita. */\n'
            '  .receita .ajuda { display: inline-grid; place-items: center; width: 17'
            'px; height: 17px;\n'
            '                    margin-left: .45rem; border-radius: 50%; border: 1px'
            ' solid var(--color-rule);\n'
            '                    color: var(--color-ink-quiet); font-size: 11px; font'
            '-weight: 400;\n'
            '                    line-height: 1; cursor: help; position: relative; ve'
            'rtical-align: middle; }\n'
            '  .receita .ajuda:hover, .receita .ajuda:focus { border-color: var(--col'
            'or-frio);\n'
            '                                                 color: var(--color-frio'
            '); outline: none; }\n'
            '  .receita .ajuda .dica { display: none; position: absolute; left: 22px;'
            ' top: -4px;\n'
            '                          width: 26rem; z-index: 40; flex-direction: col'
            'umn; gap: .3rem;\n'
            '                          padding: .55rem .7rem; background: var(--color'
            '-paper-2);\n'
            '                          border: 1px solid var(--color-rule); border-ra'
            'dius: var(--radius-md);\n'
            '                          font-size: var(--text-xs); line-height: 1.5;\n'
            '                          color: var(--color-ink); text-align: left; }\n'
            '  .receita .ajuda:hover .dica, .receita .ajuda:focus .dica,\n'
            '  .receita .ajuda:focus-within .dica { display: flex; }\n'
            '  .receita .ajuda .dica > span { display: flex; gap: .4rem; align-items:'
            ' baseline; }\n'
            '  .painel > p.ganho { margin: .5rem 0 0; display: flex; gap: .4rem; alig'
            'n-items: baseline;\n'
            '                      font-size: var(--text-sm); }\n'
            '  @media (max-width: 640px) {\n'
            '    .chapa.coluna, .chapa.fileira, .chapa.grade-tras { grid-template-col'
            'umns: minmax(0, 1fr); }\n'
            '    .modos { grid-template-columns: repeat(3, minmax(0, 1fr)); }\n'
            '    .palco > .bandeja { margin-top: 0; position: static; }\n'
            '    .pagina > .corpo > .legenda { grid-column: 1 / -1; grid-row: auto; j'
            'ustify-self: start; }\n'
            '  }\n'
            '</style>\n'
        ),
        porque=(
            '01/10/2026, O-MAPA-DAS-CONEXOES-CABE-NA-ABA-E-FALA-MENOS-01 — a folha qu'
            'e faz a página caber na aba: as entradas se arrumam sozinhas (d), a lege'
            'nda na linha dos modos (e), «Atualmente conectado» rolando até o fim da '
            'última face (a), o Adicionar numa linha (g) e o «?» das razões (f).'
        ),
    ),
    Edicao(
        antes=(
            '      <h3>O que está plugado</h3>\n'
        ),
        depois=(
            '      <h3>Atualmente conectado</h3>\n'
        ),
        porque=(
            '01/10/2026, O-MAPA-DAS-CONEXOES-CABE-NA-ABA-E-FALA-MENOS-01 — o título d'
            'a bandeja é o que ela pediu (pedido a).'
        ),
    ),
    Edicao(
        antes=(
            '<p class="chamada" id="chamada-mao">O que você tem na mão agora?</p>'
        ),
        depois=(
            '<p class="chamada" id="chamada-mao">O que você pretende conectar?</p>'
        ),
        porque=(
            '01/10/2026, O-MAPA-DAS-CONEXOES-CABE-NA-ABA-E-FALA-MENOS-01 — a pergunta'
            ' do Adicionar é a que ela ditou (pedido g).'
        ),
    ),
    Edicao(
        antes=(
            '        if (tomada) razoes.unshift({ selo: "derivado",\n'
            '          txt: "a " + naFraseDe(atual) + " passou a ser do " + (acha(pla'
            'no[atual]) || {}).tipo + ", entao este precisa de outro lugar" });\n'
        ),
        depois=(
            '        if (tomada) razoes.unshift({ selo: "derivado",\n'
            '          txt: "a " + naFraseDe(atual) + " passou a ser do " + (acha(pla'
            'no[atual]) || {}).tipo + ", então este precisa de outro lugar" });\n'
        ),
        porque=(
            '01/10/2026, O-MAPA-DAS-CONEXOES-CABE-NA-ABA-E-FALA-MENOS-01 — o acento q'
            'ue o Title Case punha em maiúscula na tela (item 3).'
        ),
    ),
    Edicao(
        antes=(
            '        if (tomada2) rz.unshift({ selo: "derivado",\n'
            '          txt: "a " + naFraseDe(atual) + " passou a ser do " + (acha(pla'
            'no[atual]) || {}).tipo + ", entao este precisa de outro lugar" });\n'
        ),
        depois=(
            '        if (tomada2) rz.unshift({ selo: "derivado",\n'
            '          txt: "a " + naFraseDe(atual) + " passou a ser do " + (acha(pla'
            'no[atual]) || {}).tipo + ", então este precisa de outro lugar" });\n'
        ),
        porque=(
            '01/10/2026, O-MAPA-DAS-CONEXOES-CABE-NA-ABA-E-FALA-MENOS-01 — o acento q'
            'ue o Title Case punha em maiúscula na tela (item 3).'
        ),
    ),
    Edicao(
        antes=(
            '        txt: "a " + naFraseDe(de) + " passou a ser do " + (acha(plano[de'
            ']) || {}).tipo + ", entao este precisa de outro lugar" });\n'
        ),
        depois=(
            '        txt: "a " + naFraseDe(de) + " passou a ser do " + (acha(plano[de'
            ']) || {}).tipo + ", então este precisa de outro lugar" });\n'
        ),
        porque=(
            '01/10/2026, O-MAPA-DAS-CONEXOES-CABE-NA-ABA-E-FALA-MENOS-01 — o acento q'
            'ue o Title Case punha em maiúscula na tela (item 3).'
        ),
    ),
    Edicao(
        antes=(
            '      html += \'<p class="chamada">Quatro arranjos possíveis. O melhor no'
            " papel pode não caber na sua escrivaninha — escolha o que cabe.</p>'\n"
            '        + \'<div class="escolhas" style="margin-bottom:.9rem">\'\n'
            '        + VARIANTES.map(function (v) {\n'
            '            var n = receita(v.op).filter(function (m) { return !m.semNum'
            'ero; }).length;\n'
            '            var c = consequencias(v.op), base = consequencias({});\n'
            '            var novas = c.filter(function (x) { return base.indexOf(x) ='
            '== -1; });\n'
            '            return \'<button class="escolha" data-var="\' + v.id + \'" aria'
            '-pressed="\' + (variante === v.id) + \'">\'\n'
            '              + "<span><b>" + v.rotulo + "</b><br><span style=\\"font-siz'
            'e:.6875rem;color:var(--color-ink-faint)\\">"\n'
            '              + n + " movimento" + (n === 1 ? "" : "s")\n'
            '              + (novas.length ? " · " + novas[0] : (v.id === "melhor" ? '
            '" · a referência" : " · sem perda"))\n'
            '              + "</span></span></button>";\n'
            '          }).join("")\n'
            '        + "</div>"\n'
            '        + \'<p style="margin:-.4rem 0 .9rem;font-size:var(--text-sm);colo'
            'r:var(--color-ink-quiet)">\'\n'
            '        + VARIANTES.filter(function (v) { return v.id === variante; })[0'
            '].desc\n'
            '        + (function () {\n'
            '            var c = consequencias(op), base = consequencias({});\n'
            '            var novas = c.filter(function (x) { return base.indexOf(x) ='
            '== -1; });\n'
            '            return novas.length ? \'<br><b style="color:var(--color-lacun'
            'a)">O que se perde:</b> \' + novas.join("; ") + "." : "";\n'
            '          })()\n'
            '        + "</p>";\n'
            '      var movs = receita(op);\n'
            '      var reais = movs.filter(function (m) { return !m.semNumero; });\n'
            '      if (!reais.length) {\n'
            '        html += \'<div class="nada-a-fazer"><b>Nada a mover.</b> Cada apa'
            "relho já está na entrada que eu escolheria: '\n"
            '             + "o teclado numa entrada direta, o Wi-Fi longe dos dongles'
            ', e os três dongles no alto e separados.</div>";\n'
            '      } else {\n'
            '        html += \'<p class="chamada"><span class="grande">\' + reais.lengt'
            'h + " movimento" + (reais.length > 1 ? "s" : "") + "</span> e o seu arra'
            'njo fica no melhor que este hardware permite.</p>"\n'
            '             + \'<ol class="receita">\'\n'
            '             + reais.map(function (m) {\n'
            '                 return "<li><div><h4>" + m.titulo + "</h4><ul>"\n'
            "                   + m.linhas.map(function (l) { return '<li><span class"
            '="selo \' + l.s + \'">\' + (l.s === "espec" ? "especificação" : l.s) + "</s'
            'pan><span>" + l.t + "</span></li>"; }).join("")\n'
            '                   + "</ul></div></li>";\n'
            '               }).join("")\n'
            '             + "</ol>";\n'
            '        var fim = movs.filter(function (m) { return m.semNumero; })[0];\n'
            '        if (fim) html += \'<div class="nada-a-fazer" style="margin-top:.5'
            'rem"><b>\' + fim.titulo + "</b><ul style=\\"list-style:none;margin:.3rem 0'
            ' 0;padding:0;display:flex;flex-direction:column;gap:.2rem\\">"\n'
            '          + fim.linhas.map(function (l) { return \'<li style="display:fle'
            'x;gap:.4rem;align-items:baseline;font-size:var(--text-sm);color:var(--co'
            'lor-ink-quiet)"><span class="selo \' + l.s + \'">\' + l.s + "</span><span>"'
            ' + l.t + "</span></li>"; }).join("") + "</ul></div>";\n'
            '        html += \'<div class="acoes"><button class="btn forte" id="reexam'
            'inar"\' + examinaNoProduto() + \'>Já movi — veja o que mudou</button>\'\n'
            '             +  \'<button class="btn" id="voltar">Desfazer o que eu decla'
            "rei</button></div>'\n"
            '             +  \'<p style="margin:.5rem 0 0;font-size:var(--text-xs);col'
            'or:var(--color-ink-faint)">\'\n'
            "             +  'Eu <b>não presumo</b> que você seguiu a ordem à risca: "
            "leio o sistema de novo, vejo quem mudou de lugar '\n"
            "             +  'e pergunto em qual entrada cada um foi parar. Mapa que "
            "adivinha vira mapa que mente.</p>';\n"
        ),
        depois=(
            '      /* O SUGESTÕES FALA MENOS — 01/10/2026 (pedido f): os botões dizem'
            ' só o\n'
            '         arranjo, cada movimento é uma linha com as razões no «?», e da '
            'conta do\n'
            '         fim fica a linha do ganho não medido (D-LINHA-DO-GANHO-NAO-MEDI'
            'DO). */\n'
            '      html += \'<div class="escolhas" style="margin-bottom:.9rem">\'\n'
            '        + VARIANTES.map(function (v) {\n'
            '            return \'<button class="escolha" data-var="\' + v.id + \'" aria'
            '-pressed="\' + (variante === v.id) + \'">\'\n'
            '              + "<b>" + v.rotulo + "</b></button>";\n'
            '          }).join("")\n'
            '        + "</div>"\n'
            '        + (function () {\n'
            '            var c = consequencias(op), base = consequencias({});\n'
            '            var novas = c.filter(function (x) { return base.indexOf(x) ='
            '== -1; });\n'
            '            return novas.length ? \'<p style="margin:-.4rem 0 .9rem;font-'
            'size:var(--text-sm);color:var(--color-ink-quiet)">\'\n'
            '              + \'<b style="color:var(--color-lacuna)">O que se perde:</b'
            '> \' + novas.join("; ") + ".</p>" : "";\n'
            '          })();\n'
            '      var movs = receita(op);\n'
            '      var reais = movs.filter(function (m) { return !m.semNumero; });\n'
            '      if (!reais.length) {\n'
            '        html += \'<div class="nada-a-fazer"><b>Nada a mover.</b> Cada apa'
            "relho já está na entrada que eu escolheria: '\n"
            '             + "o teclado numa entrada direta, o Wi-Fi longe dos dongles'
            ', e os três dongles no alto e separados.</div>";\n'
            '      } else {\n'
            '        html += \'<p class="chamada"><span class="grande">\' + reais.lengt'
            'h + " movimento" + (reais.length > 1 ? "s" : "") + "</span></p>"\n'
            '             + \'<ol class="receita">\'\n'
            '             + reais.map(function (m) {\n'
            '                 return "<li><div><h4>" + m.titulo + \'<span class="ajuda'
            '" tabindex="0">?<span class="dica">\'\n'
            "                   + m.linhas.map(function (l) { return '<span><span cla"
            'ss="selo \' + l.s + \'">\' + (l.s === "espec" ? "especificação" : l.s) + "<'
            '/span><span>" + l.t + "</span></span>"; }).join("")\n'
            '                   + "</span></span></h4></div></li>";\n'
            '               }).join("")\n'
            '             + "</ol>";\n'
            '        var fim = movs.filter(function (m) { return m.semNumero; })[0];\n'
            '        var ganho = fim ? fim.linhas.filter(function (l) { return /^<b>/'
            '.test(l.t); })[0] : null;\n'
            '        if (ganho) html += \'<p class="ganho"><span class="selo \' + ganho'
            '.s + \'">\' + ganho.s + "</span><span>"\n'
            '          + ganho.t.replace(/<\\/b>[\\s\\S]*$/, "</b>") + "</span></p>";\n'
            '        html += \'<div class="acoes"><button class="btn forte ja-movi"\' +'
            " examinaNoProduto() + '>Já movi — veja o que mudou</button>'\n"
            '             +  \'<button class="btn" id="voltar">Desfazer o que eu decla'
            "rei</button></div>';\n"
        ),
        porque=(
            '01/10/2026, O-MAPA-DAS-CONEXOES-CABE-NA-ABA-E-FALA-MENOS-01 — o Sugestõe'
            's fala menos: sem a chamada, a descrição e os subtítulos das variantes, '
            'cada movimento numa linha com as razões no «?», a linha do ganho não med'
            'ido curta e sem o parágrafo do «Já movi», que deixa de repetir o id do «'
            'Examinar» (pedido f e item 4).'
        ),
    ),
    Edicao(
        antes=(
            '    if (ev.target.id === "reexaminar") {\n'
        ),
        depois=(
            '    if (ev.target.id === "reexaminar" || ev.target.classList.contains("j'
            'a-movi")) {\n'
        ),
        porque=(
            '01/10/2026, O-MAPA-DAS-CONEXOES-CABE-NA-ABA-E-FALA-MENOS-01 — o «Já movi'
            '» das Sugestões responde pela classe, e o `#reexaminar` é só o do cabeça'
            'lho (item 4).'
        ),
    ),
    Edicao(
        antes=(
            '        estado = "chega"; vered = "vem para cá";\n'
            '        var de = portaDe(idPlano);\n'
            '        porque = de ? "estava na " + naFraseDe(de) : "ainda sem lugar";\n'
            '      } else if (!idPlano && idAgora) {\n'
            '        ap = acha(idAgora); estado = "sai"; vered = "sai daqui";\n'
            '        porque = "vai para a " + naFraseDe(portaDeEm(ctx.plano, idAgora)'
            ');\n'
            '      } else if (idPlano) { estado = "fica"; vered = "fica"; porque = "j'
            'á está certa"; }\n'
        ),
        depois=(
            '        /* SÓ O VEREDITO — 01/10/2026 (pedido f): de onde e para onde já'
            ' estão\n'
            '           na lista de cima. */\n'
            '        estado = "chega"; vered = "vem para cá";\n'
            '      } else if (!idPlano && idAgora) {\n'
            '        ap = acha(idAgora); estado = "sai"; vered = "sai daqui";\n'
            '      } else if (idPlano) { estado = "fica"; vered = "fica"; }\n'
        ),
        porque=(
            '01/10/2026, O-MAPA-DAS-CONEXOES-CABE-NA-ABA-E-FALA-MENOS-01 — no mapa do'
            ' Sugestões cada entrada diz só o veredito (pedido f).'
        ),
    ),
    Edicao(
        antes=(
            '  .edita-cab .fecha { position: absolute; top: 0; right: 0'
            '; }\n'
        ),
        depois=(
            '  .edita-cab .fecha { position: absolute; top: 0; right: 0'
            '; }\n'
            '  /* O PAINEL DO APARELHO — 04/10/2026, O-APARELHO-SE-CORR'
            'IGE-ONDE-SE-CLICA-01 */\n'
            '  .rotulo .ap-btn { display: inline-block; max-width: 100%'
            '; margin: 0; padding: .12rem .45rem;\n'
            '                    font: inherit; font-weight: 600; text-'
            'align: left; cursor: pointer;\n'
            '                    background: var(--color-paper-3); bord'
            'er: 1px solid var(--color-rule);\n'
            '                    border-radius: var(--radius-sm); }\n'
            '  .rotulo .ap-btn:hover { border-color: #6272a4; }\n'
            '  .rotulo .ap-btn:focus-visible { outline: 2px solid var(-'
            '-color-accent); outline-offset: 2px; }\n'
            '  .rotulo .ap-btn[draggable="true"] { cursor: grab; }\n'
            '  .edita .acoes-do-aparelho a.btn { display: inline-block; text-decoration: none; }\n'
            '  .soquete.alvo-do-arrasto { outline: 2px dashed var(--col'
            'or-ok); outline-offset: 3px; border-radius: var(--radius-s'
            'm); }\n'
            '  body.arrastando .soquete[data-soquete] { cursor: copy; }'
            '\n'
            '  .edita .ap-cab { padding-right: 2.2rem; }\n'
            '  .edita .campo-nome.titulo { font-weight: 700; font-size:'
            ' var(--text-base); background: transparent;\n'
            '                              border: 0; border-bottom: 1p'
            'x dashed var(--color-rule); border-radius: 0;\n'
            '                              padding: .15rem 0; }\n'
            '  .edita .tipos, .edita .etqs { display: flex; flex-wrap: '
            'wrap; gap: .3rem; }\n'
            '  .edita .tipos .escolha { display: inline-flex; align-ite'
            'ms: center; gap: .3rem; padding: .2rem .5rem; }\n'
            '  .edita .tipos .escolha i { width: .55rem; height: .55rem'
            '; border-radius: 50%; display: inline-block; }\n'
            '  .edita .tipos .escolha[aria-pressed="true"] { border-col'
            'or: var(--color-accent);\n'
            '                    background: color-mix(in srgb, var(--c'
            'olor-accent) 18%, var(--color-paper-3)); }\n'
            '  .edita .etq { padding: .12rem .45rem; font-family: var(-'
            '-font-dado); font-size: .6875rem;\n'
            '                border: 1px solid var(--color-rule); borde'
            'r-radius: var(--radius-sm); }\n'
            '  .edita .etq.medida { border-style: dashed; }\n'
            '  /* A FAIXA DELE (desenho 2): pintado é o canal bom; vazio, com a'
            ' marca de quem o tomou */\n'
            '  .edita .faixa-dele { display: grid; grid-template-columns: repea'
            't(79, 1fr); gap: 1px;\n'
            '                       height: .75rem; }\n'
            '  .edita .faixa-dele i { display: block; border-radius: 1px; backg'
            'round: transparent;\n'
            '    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--color-rul'
            'e) 60%, transparent); }\n'
            '  .edita .faixa-dele i.b, .edita .faixa-dele i.o {\n'
            '    background: var(--cor-faixa, var(--color-ink)); box-shadow: no'
            'ne; }\n'
            '  .edita .faixa-dele i.p { box-shadow: inset 0 -3px 0 var(--marca,'
            ' var(--color-rule)); }\n'
            '  .edita .faixa-dele i.o { box-shadow: inset 0 -3px 0 var(--marca,'
            ' transparent); }\n'
            '  .edita .faixa-dele-txt { display: block; margin-top: .25rem; fon'
            't-family: var(--font-dado);\n'
            '                           font-size: .6875rem; text-transform: none; }\n'
            '  .edita .faixa-dele-txt .marca-txt { display: inline-block; width: .5rem;'
            ' height: .5rem;\n'
            '    margin-right: .25rem; border-radius: 1px; background: var(--marca); }\n'
            '  .edita .onde { display: flex; align-items: center; justi'
            'fy-content: space-between; gap: .5rem;\n'
            '                 font-size: var(--text-sm); }\n'
            '  .edita .chave { display: inline-flex; align-items: cente'
            'r; gap: .4rem; font: inherit;\n'
            '                  font-size: var(--text-xs); color: var(--'
            'color-ink); cursor: pointer;\n'
            '                  background: transparent; border: 0; padd'
            'ing: .1rem; }\n'
            '  .edita .chave i { position: relative; width: 2rem; heigh'
            't: 1.1rem; border-radius: 1rem;\n'
            '                    background: var(--color-paper-3); bord'
            'er: 1px solid var(--color-rule); }\n'
            '  .edita .chave i::after { content: ""; position: absolute'
            '; top: 1px; left: 1px; width: .85rem; height: .85rem;\n'
            '                           border-radius: 50%; background:'
            ' var(--color-ink); transition: transform .15s; }\n'
            '  .edita .chave[aria-checked="true"] i { background: var(-'
            '-color-accent); border-color: var(--color-accent); }\n'
            '  .edita .chave[aria-checked="true"] i::after { transform:'
            ' translateX(.9rem); }\n'
            '  .edita .chave:focus-visible { outline: 2px solid var(--c'
            'olor-accent); outline-offset: 2px; }\n'
            '  .edita .faz { display: flex; align-items: center; justif'
            'y-content: space-between; gap: .5rem;\n'
            '                padding: .45rem .55rem; border: 1px solid '
            'color-mix(in srgb, var(--color-ok) 45%, transparent);\n'
            '                border-radius: var(--radius-sm); font-size'
            ': var(--text-sm);\n'
            '                background: color-mix(in srgb, var(--color'
            '-ok) 8%, var(--color-paper-2)); }\n'
            '  .edita .acoes-do-aparelho { flex-direction: row; flex-wr'
            'ap: wrap; gap: .4rem; }\n'
            '  .edita .dica-id { margin: 0; font-size: var(--text-xs); '
            '}\n'
            '  .edita .mais summary { cursor: pointer; font-size: var(-'
            '-text-xs); font-weight: 600; }\n'
            '  .edita .mais[open] { display: flex; flex-direction: colu'
            'mn; gap: .6rem; }\n'
            '  .plug[data-achado="1"] { box-shadow: 0 0 0 3px var(--col'
            'or-accent), 0 0 18px 3px rgba(189,147,249,.55); }\n'
            '  .aviso-uma-linha { display: flex; align-items: center; g'
            'ap: .6rem; margin: 0;\n'
            '                     padding: .45rem .7rem; border: 1px so'
            'lid color-mix(in srgb, var(--color-ok) 55%, transparent);\n'
            '                     border-radius: var(--radius-sm); font'
            '-size: var(--text-sm);\n'
            '                     background: color-mix(in srgb, var(--'
            'color-ok) 10%, var(--color-paper-2)); }\n'
            '  .aviso-uma-linha .ok { color: var(--color-ok); font-weig'
            'ht: 700; }\n'
            '  .aviso-uma-linha .btn.pequeno { padding: .1rem .5rem; fo'
            'nt-size: var(--text-xs); }\n'
            '  .aviso-uma-linha .aviso-fecha { margin-left: auto; min-w'
            'idth: 0; width: 1.8rem; height: 1.8rem; padding: 0; }\n'
            '  .aviso-detalhe { margin-top: .6rem; }\n'
            '  .leitura-da-maquina { margin: .5rem 0 0; font-size: var('
            '--text-xs); line-height: 1.5; }\n'
        ),
        porque=(
            '04/10/2026, O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 — o est'
            'ilo do painel do aparelho, da chave do extensor, do aviso '
            'de uma linha e da leitura da máquina.'
        ),
    ),
    Edicao(
        antes=(
            '      : "Clique numa entrada para dar nome, corrigir ou tr'
            'ocar.";'
        ),
        depois=(
            '      : "";'
        ),
        porque=(
            '04/10/2026, O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 — sai o'
            ' «Clique numa Entrada…»: o clique se mostra pela forma (o '
            'aparelho tem cara de botão), não por instrução (decisão 10'
            ' dela).'
        ),
    ),
    Edicao(
        antes=(
            '      h += \'<b class="nome" style="color:\' + ap.cor + \'">\''
            ' + ap.tipo + \'</b><span class="caminho">\' + (caminhoDe(ap.'
            'id) || "—") + "</span>";'
        ),
        depois=(
            '      h += \'<button class="ap-btn nome" data-ap-abre="\' + '
            'porta.n + \'"\'\n'
            '        + ((doProduto() ? GRAVA.indexOf(String(porta.n)) !'
            '== -1 : true) ? \' draggable="true"\' : "")\n'
            '        + \' style="color:\' + ap.cor + \'" title="Abrir o pa'
            "inel de ' + emAtributo(rotuloDoAparelho(ap))\n"
            '        + \'">\' + emAtributo(rotuloDoAparelho(ap)) + \'</but'
            'ton><span class="caminho">\' + (caminhoDe(ap.id) || "—") + '
            '"</span>";'
        ),
        porque=(
            '04/10/2026, O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 — o apa'
            'relho no mapa é um botão: clicar abre o painel dele, e arr'
            'astar leva para outra entrada.'
        ),
    ),
    Edicao(
        antes=(
            '    h += \'<div class="soquete"><span class="num">\' + porta'
            '.n + "</span>"'
        ),
        depois=(
            '    h += \'<div class="soquete" data-soquete="\' + porta.n +'
            ' \'"><span class="num">\' + porta.n + "</span>"'
        ),
        porque=(
            '04/10/2026, O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 — a ent'
            'rada é o alvo do arrastar.'
        ),
    ),
    Edicao(
        antes=(
            '        + \'<span class="txt"><b>\' + a.tipo + "</b><span>" '
            '+ a.nome + " · " + (caminhoDe(a.id) || "não está plugado")'
            ' + "</span></span>"'
        ),
        depois=(
            '        + \'<span class="txt"><b>\' + emAtributo(rotuloDoApa'
            'relho(a)) + "</b><span>" + a.nome + " · " + (caminhoDe(a.i'
            'd) || "não está plugado") + "</span></span>"'
        ),
        porque=(
            '04/10/2026, O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 — o car'
            'tão da lista diz o nome que ela deu (ou o tipo que ela dis'
            'se) antes do que a máquina leu.'
        ),
    ),
    Edicao(
        antes=(
            '    if (chip && doProduto() && portaDe(chip.getAttribute("'
            'data-ap"))) {\n'
            '      editando = portaDe(chip.getAttribute("data-ap")); mo'
            'do = "mesa";'
        ),
        depois=(
            '    if (chip && portaDe(chip.getAttribute("data-ap"))) {\n'
            '      achado = null; editandoDe = "lista";\n'
            '      editando = portaDe(chip.getAttribute("data-ap")); mo'
            'do = "mesa";'
        ),
        porque=(
            '04/10/2026, O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 — clica'
            'r em qualquer aparelho da lista abre o painel dele, ao lad'
            'o do cartão, no exemplo e no produto.'
        ),
    ),
    Edicao(
        antes=(
            '    var ub = ev.target.closest("#edita [data-usb]");'
        ),
        depois=(
            '    /* O PAINEL DO APARELHO — 04/10/2026. O que leva `data'
            '-gesto` o produto grava e a página\n'
            '       espera o disco; o que não leva (o exemplo) muda só '
            'na tela. */\n'
            '    var abre = ev.target.closest("[data-ap-abre]");\n'
            '    if (abre) {\n'
            '      achado = null; editandoDe = "mapa";\n'
            '      editando = abre.getAttribute("data-ap-abre"); if (mo'
            'do === "ideal") modo = "mesa";\n'
            '      pintar(); return;\n'
            '    }\n'
            '    var ext = ev.target.closest("#edita [data-extensor]");'
            '\n'
            '    if (ext && ext.hasAttribute("data-gesto")) return;\n'
            '    if (ext) {\n'
            '      var liga = ext.getAttribute("data-ligado") === "true'
            '", pe = porNum(editando);\n'
            '      declarar(editando, "extensor", liga); if (pe) pe.est'
            'icada = liga;\n'
            '      pintar(); return;\n'
            '    }\n'
            '    var tp = ev.target.closest("#edita [data-tipodito]");\n'
            '    if (tp && (tp.hasAttribute("data-gesto") || tp.disable'
            'd)) return;\n'
            '    if (tp) {\n'
            '      var ap0 = aparelhoDaEntrada(editando);\n'
            '      if (ap0) {\n'
            '        ap0.tipoDeclarado = tp.getAttribute("data-tipodito'
            '");\n'
            '        ap0.cor = COR_DO_TIPO[ap0.tipoDeclarado] || ap0.co'
            'r;\n'
            '      }\n'
            '      pintar(); return;\n'
            '    }\n'
            '    var vauto = ev.target.closest("#edita #voltar-ao-autom'
            'atico");\n'
            '    if (vauto && (vauto.hasAttribute("data-gesto") || vaut'
            'o.disabled)) return;\n'
            '    if (vauto) {\n'
            '      var ap1 = aparelhoDaEntrada(editando);\n'
            '      if (ap1) { delete ap1.tipoDeclarado; delete ap1.nome'
            'Declarado; ap1.cor = ap1.corDaMaquina || ap1.cor; }\n'
            '      if (DECLARADO[editando]) delete DECLARADO[editando].'
            'extensor;\n'
            '      var pv = porNum(editando); if (pv) pv.esticada = fal'
            'se;\n'
            '      pintar(); return;\n'
            '    }\n'
            '    if (ev.target.closest("#edita #identificar")) {\n'
            '      identificando = alocacao[editando] || null; pintar()'  # (noqa-acento: JS)
            '; return;\n'
            '    }\n'
            '    if (ev.target.id === "ver-a-sugestao") { editando = nu'
            'll; modo = "ideal"; pintar(); return; }\n'
            '    if (ev.target.id === "aviso-ver") { avisoAberto = true'
            '; pintar(); return; }\n'
            '    if (ev.target.id === "aviso-fecha") { modo = "mesa"; p'
            'intar(); return; }\n'
            '    var ub = ev.target.closest("#edita [data-usb]");'
        ),
        porque=(
            '04/10/2026, O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 — os ge'
            'stos do painel: a chave do extensor, o tipo, «Voltar ao au'
            'tomático», «Identificar», «Mostrar a entrada boa» e o avis'
            'o de uma linha.'
        ),
    ),
    Edicao(
        antes=(
            '  function mostrarEditor() {\n'
            '    var ed = document.getElementById("edita");\n'
            '    if (!ed) return;\n'
        ),
        depois=_com_os_dados(
            '  /* ══ O PAINEL DO APARELHO — 04/10/2026, O-APARELHO-SE-C'
            'ORRIGE-ONDE-SE-CLICA-01 ═══════\n'
            '     Pedido dela: «clicar num dispositivo não oferece modi'
            'ficá-lo ou identificá-lo, nem no\n'
            '     mapa nem em Atualmente Conectado». Clicar em QUALQUER'
            ' aparelho (o botão com o nome dele\n'
            '     no mapa, ou o cartão da lista) abre este painel, flut'
            'uando ao lado dele. Em cima, o que\n'
            '     ela corrige: o nome, o tipo (o tipo decide a cor em t'
            'odo o app) e a chave «Extensor».\n'
            '     No meio, o que a máquina vê, em etiquetas sem botão. '
            'Embaixo, uma linha só: o que fazer.\n'
            '     QUEM VENCE: a máquina no que mede (o chip, a velocida'
            'de, os hubs: etiquetas sem botão), a\n'
            '     pessoa no resto (o nome, o tipo, o extensor). O tipo '
            'que ela diz decide a cor e o nome em\n'
            '     todo o app; no motor ele só pesa quando a máquina não'
            ' leu a classe do aparelho. */\n'
            '  var TIPOS_DO_APARELHO = __TIPOS_DO_APARELHO__;\n'
            '  var COR_DO_TIPO = __COR_DO_TIPO__;\n'
            '  var LUGARES_DA_ENTRADA = __LUGARES_DA_ENTRADA__;\n'
            '  var TIPO_DA_CLASSE = { teclado: "teclado", mouse: "mouse'
            '", wifi: "wifi", webcam: "webcam" };\n'
            '  var AVISO_SOME_EM_MS = 10000;\n'
            '  var editandoDe = "mapa", identificando = null, achado = '
            'null;\n'
            '  var avisoTimer = null, avisoAberto = false, arrastando ='
            ' null;\n'
            '\n'
            '  function aparelhoDaEntrada(n) { return alocacao[n] ? ach'  # (noqa-acento: JS)
            'a(alocacao[n]) : null; }\n'  # (noqa-acento: JS)
            '  function rotuloDoTipo(t) {\n'
            '    for (var i = 0; i < TIPOS_DO_APARELHO.length; i++) if '
            '(TIPOS_DO_APARELHO[i][0] === t) return TIPOS_DO_APARELHO[i'
            '][1];\n'
            '    return t;\n'
            '  }\n'
            '  /* o nome que ela deu vence; depois o tipo que ela disse'
            '; depois o que a máquina leu */\n'
            '  function rotuloDoAparelho(a) {\n'
            '    return a.nomeDeclarado || (a.tipoDeclarado ? rotuloDoT'
            'ipo(a.tipoDeclarado) : a.tipo);\n'
            '  }\n'
            '  function editavelNoProduto(quem) { return !doProduto() |'
            '| !!quem.modelo; }\n'
            '\n'
            '  /* A CHAVE «EXTENSOR» — é da porta, separada do que está'
            ' ligado nela (hub, aparelho): ligada,\n'
            '     o aparelho continua dito na entrada e o motor lê a en'
            'trada como esticada. */\n'
            '  function chaveDoExtensor(n) {\n'
            '    var soNaTela = doProduto() && !podeGravar(n);\n'
            '    if (soNaTela) return "";\n'
            '    var ligado = !!(DECLARADO[n] || {}).extensor;\n'
            '    return \'<button class="chave" role="switch" aria-check'
            'ed="\' + ligado + \'" data-extensor="\' + n + \'"\'\n'
            '      + \' data-ligado="\' + (!ligado) + \'"\' + gravaNaEntrad'
            'a(n, "entrada-extensor")\n'
            '      + \' title="Há um cabo de extensão entre esta entrada'
            ' e o aparelho"><i></i><span>Extensor</span></button>\';\n'
            '  }\n'
            '  function linhaDoExtensor(n) {\n'
            '    var c = chaveDoExtensor(n);\n'
            '    return c ? \'<div class="edita-linha"><span>Extensor</s'
            'pan><div class="onde">\'\n'
            "      + '<span>Tem um cabo de extensão nesta entrada?</spa"
            'n>\' + c + "</div></div>" : "";\n'
            '  }\n'
            '  /* O «LUGAR» — a face do gabinete (o campo do Mapear, no'
            ' mesmo dono). Só no produto, onde a\n'
            '     entrada grava: no exemplo ninguém guarda nada. */\n'
            '  function linhaDoLugar(n) {\n'
            '    if (!doProduto() || !podeGravar(n) || !/^[0-9]{1,3}$/.'
            'test(String(n))) return "";\n'
            '    var atual = faceDe(n), nomes = LUGARES_DA_ENTRADA.slic'
            'e();\n'
            '    FACES.forEach(function (f) { if (!f.semLugar && !f.daE'
            'ntrada && nomes.indexOf(f.nome) === -1) nomes.push(f.nome)'
            '; });\n'
            '    return \'<div class="edita-linha"><span>Lugar</span><se'
            'lect class="troca" data-gesto="entrada-lugar"\'\n'
            '      + \' data-entrada="\' + n + \'" aria-label="Lugar">\'\n'
            '      + (atual && nomes.indexOf(atual) !== -1 ? "" : \'<opt'
            'ion value="" selected>Sem lugar</option>\')\n'
            '      + nomes.map(function (nome) {\n'
            '          return \'<option value="\' + emAtributo(nome) + \'"'
            '\' + (nome === atual ? " selected" : "") + ">"\n'
            '            + emAtributo(nome) + "</option>";\n'
            '        }).join("")\n'
            '      + "</select></div>";\n'
            '  }\n'
            '  function semLugar(p) {\n'
            '    return FACES.some(function (f) { return !!f.semLugar &'
            '& f.portas.indexOf(p) !== -1; });\n'
            '  }\n'
            '  function aparelhoSemLugar(id) {\n'
            '    var p = portaDe(id), pp = p && porNum(p);\n'
            '    return !!(pp && semLugar(pp));\n'
            '  }\n'
            '\n'
            '  /* «O QUE FAZER»: uma linha, no máximo um botão. Fala o '
            'que o motor já diz (o plano). */\n'
            '  function oQueFazer(n, quem) {\n'
            '    if (!quem.classe && !quem.tipoDeclarado) {\n'
            '      return \'<div class="faz"><span>Sem saber o que é, eu'
            " não sugiro lugar. Diga o tipo acima.</span></div>';\n"
            '    }\n'
            '    if (aparelhoSemLugar(quem.id)) {\n'
            '      return \'<div class="faz"><span>Esta entrada está sem'
            ' lugar no gabinete: diga o lugar dela para eu julgar.</spa'
            "n></div>';\n"
            '    }\n'
            '    var r = planejar({}), para = portaDeEm(r.plano, quem.i'
            'd);\n'
            '    var m = r.motivo[quem.id] || { razoes: [], essencial: '
            'false, ganho: 0 };\n'
            '    if (receitaManda(n, para, m)) {\n'
            '      var razao = m.razoes.length ? m.razoes[0].txt : "";\n'
            '      return \'<div class="faz"><span>Melhor na \' + emAtrib'
            'uto(naFraseDe(para))\n'
            '        + (razao ? ": " + emAtributo(razao) : "") + \'.</sp'
            "an>'\n"
            '        + \'<button class="btn forte" id="ver-a-sugestao">M'
            "ostrar a entrada boa</button></div>';\n"
            '    }\n'
            '    return \'<div class="faz bem"><span>✓ Está numa boa ent'
            "rada.</span></div>';\n"
            '  }\n'
            '  /* no exemplo ninguém mediu nada: as etiquetas saem do q'
            'ue o desenho já diz */\n'
            '  function etiquetasDoExemplo(quem, p) {\n'
            '    var e = [];\n'
            '    if (quem.tipo) e.push(quem.tipo);\n'
            '    if (p) e.push(p.usb === 3 ? "USB 3.0" : "USB 2.0");\n'
            '    if (p && p.onde === "hub") e.push("atrás de 1 hub");\n'
            '    return e;\n'
            '  }\n'
            '  function identificavel(quem) { return !/^054c:/.test(que'
            'm.modelo || ""); }\n'
            '\n'
            '  function htmlDoPainelDoAparelho(n, quem, p, face) {\n'
            '    var edita = editavelNoProduto(quem);\n'
            '    var g = function (gesto) {\n'
            '      return quem.modelo ? \' data-gesto="\' + gesto + \'" da'
            'ta-modelo="\' + quem.modelo + \'"\' : "";\n'
            '    };\n'
            '    var h = \'<div class="edita-cab ap-cab"><input class="c'
            'ampo-nome titulo" type="text"\'\n'
            '      + \' data-nome-do-aparelho="\' + emAtributo(quem.id) +'
            ' \'"\' + g("aparelho-nome")\n'
            '      + (edita ? "" : " disabled") + \' maxlength="\' + MAXI'
            'MO_DO_NOME + \'"\'\n'
            '      + \' value="\' + emAtributo(quem.nomeDeclarado || "") '
            '+ \'"\'\n'
            '      + \' placeholder="\' + emAtributo(rotuloDoAparelho(que'
            'm)) + \'" aria-label="Nome do aparelho">\'\n'
            '      + \'<button class="btn fecha" id="edita-fecha" aria-l'
            'abel="Fechar">&times;</button></div>\';\n'
            '\n'
            '    h += \'<div class="edita-linha"><span>O que é</span><di'
            'v class="tipos">\';\n'
            '    var tipoAgora = quem.tipoDeclarado || TIPO_DA_CLASSE[q'
            'uem.classe] || "";\n'
            '    h += TIPOS_DO_APARELHO.map(function (t) {\n'
            '      return \'<button class="escolha tipo-do-aparelho" dat'
            'a-tipodito="\' + t[0] + \'"\' + g("aparelho-tipo")\n'
            '        + (edita ? "" : " disabled") + \' aria-pressed="\' +'
            ' (tipoAgora === t[0]) + \'">\'\n'
            '        + \'<i style="background:\' + (COR_DO_TIPO[t[0]] || '
            '"#9a9eb8") + \'"></i>\' + t[1] + "</button>";\n'
            '    }).join("");\n'
            '    h += "</div></div>";\n'
            '\n'
            '    h += \'<div class="edita-linha"><span>Onde está</span><'
            'div class="onde"><span>\'\n'
            '      + emAtributo(rotuloDe(n) + (face ? " · " + (face.tit'
            'ulo || face.nome) : "")) + "</span>"\n'
            '      + chaveDoExtensor(n) + "</div></div>";\n'
            '\n'
            '    var et = quem.etiquetas || etiquetasDoExemplo(quem, p)'
            ';\n'
            '    if (et.length) {\n'
            '      h += \'<div class="edita-linha"><span>O que a máquina'
            ' vê</span><div class="etqs">\'\n'
            '        + et.map(function (e) { return \'<span class="etq">'
            '\' + emAtributo(e) + "</span>"; }).join("") + "</div></div>'
            '";\n'
            '    }\n'
            '    /* A FAIXA DELE: a mesma conta da aba Conexões; sem leitura nã'
            'o há linha */\n'
            '    var fx = quem.faixa;\n'
            '    if (fx && fx.celulas && fx.celulas.length) {\n'
            '      h += \'<div class="edita-linha"><span>A faixa dele</span><div'
            ">'\n"
            '        + \'<div class="faixa-dele" role="img" aria-label="\' + emAt'
            'ributo(fx.texto || "A faixa dele") + \'"\'\n'
            '        + \' style="--cor-faixa:\' + emAtributo(fx.cor || "") + \'">\''
            '\n'
            '        + fx.celulas.map(function (c, k) {\n'
            '            var onde = "Canal " + k + " · " + (2402 + k) + " MHz";'
            '\n'
            '            var dito = c[0] === "p" ? " · perdido para " + c[2]\n'
            '              : c[0] === "o" ? " · ocupado" + (c[2] ? ", perde " +'
            ' c[2] : "")\n'
            '              : c[0] === "b" ? " · bom" : "";\n'
            '            return \'<i class="\' + c[0] + \'"\' + (c[1] ? \' style="--'
            'marca:\' + emAtributo(c[1]) + \'"\' : "")\n'
            '              + \' title="\' + emAtributo(onde + dito) + \'"></i>\';\n'
            '          }).join("") + "</div>"\n'
            '        + (fx.texto ? \'<span class="faixa-dele-txt">\'\n'
            '          + (fx.partes || [[fx.texto, ""]]).map(function (pt) {\n'
            '              return (pt[1] ? \'<i class="marca-txt" aria-hidden="true"\''
            ' + \' style="--marca:\'\n'
            '                + emAtributo(pt[1]) + \'"></i>\' : "") + emAtributo(pt[0]);\n'
            '            }).join("") + "</span>" : "")\n'
            '        + "</div></div>";\n'
            '    }\n'
            '    h += oQueFazer(n, quem);\n'
            '\n'
            '    var gVolta = \' data-gesto="voltar-ao-automatico"\' + (q'
            'uem.modelo ? \' data-modelo="\' + quem.modelo + \'"\' : "")\n'
            '      + (podeGravar(n) ? \' data-entrada="\' + n + \'"\' : "")'
            ';\n'
            '    h += \'<div class="edita-linha acoes-do-aparelho">\'\n'
            '      + (quem.receptor ? \'<a class="btn" id="descobrir-a-faixa" '
            'href="08-conexoes.html">Descobrir a faixa</a>\' : "")\n'
            '      + (identificavel(quem) ? \'<button class="btn" id="id'
            'entificar">Identificar</button>\' : "")\n'
            '      + \'<button class="btn" id="voltar-ao-automatico"\' + '
            '(doProduto() ? gVolta : "") + (edita ? "" : " disabled")\n'
            '      + ">Voltar ao automático</button></div>";\n'
            '    if (identificando === quem.id) {\n'
            '      h += \'<p class="dica-id">Tire o aparelho e ponha de '
            'novo, depois clique «Examinar»: eu acendo a entrada em que'
            " ele estava.</p>';\n"
            '    }\n'
            '    var soNaTela = doProduto() && !podeGravar(n);\n'
            '    if (!soNaTela) {\n'
            '      h += \'<details class="mais"><summary>Mais desta entr'
            "ada</summary>' + linhaDoNome(n)\n"
            '        + linhaDoLugar(n) + linhaDaTroca(n) + "</details>"'
            ';\n'
            '    }\n'
            '    return h;\n'
            '  }\n'
            '\n'
            '  function mostrarOPainelDoAparelho(ed, quem) {\n'
            '    var n = editando, p = porNum(n);\n'
            '    var plug = document.querySelector(\'.plug[data-porta="\''
            ' + n + \'"]\');\n'
            '    var face = FACES.filter(function (f) {\n'
            '      return f.portas.some(function (x) { return x === p |'
            '| x.filho === p; });\n'
            '    })[0];\n'
            '    ed.innerHTML = htmlDoPainelDoAparelho(n, quem, p, face'
            ');\n'
            '    ed.hidden = false;\n'
            '    var palco = ed.parentElement.getBoundingClientRect();\n'
            '    var chip = editandoDe === "lista" ? document.querySele'
            'ctor(\'.chip[data-ap="\' + quem.id + \'"]\') : null;\n'
            '    if (chip) {\n'
            '      var c = chip.getBoundingClientRect();\n'
            '      ed.style.left = Math.max(0, c.left - palco.left - 30'
            '8) + "px";\n'
            '      ed.style.top = Math.max(0, c.top - palco.top) + "px"'
            ';\n'
            '    } else {\n'
            '      var r = plug.getBoundingClientRect();\n'
            '      ed.style.left = Math.max(0, Math.min(r.left - palco.'
            'left, palco.width - 310)) + "px";\n'
            '      ed.style.top = (r.bottom - palco.top + 8) + "px";\n'
            '    }\n'
            '  }\n'
            '\n'
            '  function mostrarEditor() {\n'
            '    var ed = document.getElementById("edita");\n'
            '    if (!ed) return;\n'
            '    var quem = editando && modo !== "ideal" && !segurando '
            '? aparelhoDaEntrada(editando) : null;\n'
            "    var plug = editando && document.querySelector('.plug[d"
            'ata-porta="\' + editando + \'"]\');\n'
            '    if (quem && plug && porNum(editando)) mostrarOPainelDo'
            'Aparelho(ed, quem);\n'
            '    else mostrarEditorDaEntrada();\n'
            '  }\n'
            '\n'
            '  /* TROCAR DE LUGAR É ARRASTAR para a outra entrada, com '
            '«Mover para…» no painel para quem usa\n'
            '     teclado ou leitor de tela. No produto o gesto é o `en'
            'trada-trocar` (o mesmo do «Mover\n'
            '     para…»); no exemplo a troca é só na tela. */\n'
            '  function podeMover(de, para) {\n'
            '    if (de === para) return false;\n'
            '    if (doProduto()) return GRAVA.indexOf(String(de)) !== '
            '-1 && GRAVA.indexOf(String(para)) !== -1\n'
            '      && /^[0-9]{1,3}$/.test(String(de)) && /^[0-9]{1,3}$/'
            '.test(String(para));\n'
            '    return !!porNum(de) && !!porNum(para);\n'
            '  }\n'
            '  function moverPara(de, para) {\n'
            '    if (!podeMover(de, para)) return;\n'
            '    if (doProduto()) {\n'
            '      var sel = document.createElement("select");\n'
            '      sel.hidden = true;\n'
            '      sel.setAttribute("data-gesto", "entrada-trocar");\n'
            '      sel.setAttribute("data-entrada", de);\n'
            '      sel.innerHTML = \'<option value="\' + para + \'" select'
            'ed>\' + para + "</option>";\n'
            '      document.body.appendChild(sel);\n'
            '      sel.dispatchEvent(new Event("change", { bubbles: tru'
            'e }));\n'
            '      document.body.removeChild(sel);\n'
            '      return;\n'
            '    }\n'
            '    var cd = MAPA[de], cp = MAPA[para];\n'
            '    if (cd) MAPA[para] = cd; else delete MAPA[para];\n'
            '    if (cp) MAPA[de] = cp; else delete MAPA[de];\n'
            '    editando = null;\n'
            '    pintar();\n'
            '  }\n'
            '  document.addEventListener("dragstart", function (ev) {\n'
            '    var b = ev.target.closest && ev.target.closest(".ap-bt'
            'n[data-ap-abre]");\n'
            '    if (!b || !ev.dataTransfer) return;\n'
            '    arrastando = b.getAttribute("data-ap-abre");\n'
            '    ev.dataTransfer.setData("text/plain", arrastando);\n'
            '    ev.dataTransfer.effectAllowed = "move";\n'
            '    document.body.classList.add("arrastando");\n'
            '  });\n'
            '  function limparOsAlvos() {\n'
            '    var alvos = document.querySelectorAll(".soquete.alvo-d'
            'o-arrasto");\n'
            '    for (var i = 0; i < alvos.length; i++) alvos[i].classL'
            'ist.remove("alvo-do-arrasto");\n'
            '  }\n'
            '  document.addEventListener("dragend", function () {\n'
            '    arrastando = null; document.body.classList.remove("arr'
            'astando"); limparOsAlvos();\n'
            '  });\n'
            '  document.addEventListener("dragover", function (ev) {\n'
            '    var s = arrastando && ev.target.closest && ev.target.c'
            'losest(".soquete[data-soquete]");\n'
            '    if (!s || !podeMover(arrastando, s.getAttribute("data-'
            'soquete"))) return;\n'
            '    ev.preventDefault();\n'
            '    limparOsAlvos();\n'
            '    s.classList.add("alvo-do-arrasto");\n'
            '  });\n'
            '  document.addEventListener("drop", function (ev) {\n'
            '    var s = arrastando && ev.target.closest && ev.target.c'
            'losest(".soquete[data-soquete]");\n'
            '    if (!s) return;\n'
            '    ev.preventDefault();\n'
            '    var de = arrastando;\n'
            '    arrastando = null; document.body.classList.remove("arr'
            'astando"); limparOsAlvos();\n'
            '    moverPara(de, s.getAttribute("data-soquete"));\n'
            '  });\n'
            '\n'
            '  /* O AVISO DE «MUDOU DE LUGAR» é uma linha com ✓ que som'
            'e sozinha em 10 s: «Ver» abre o\n'
            '     detalhe (e o segura até ela fechar) e o ✕ fecha na ho'
            'ra. */\n'
            '  function oAvisoDeUmaLinha(mudou, detalhe) {\n'
            '    var frase, sab = mudou.filter(function (m) { return m.'
            'entradaAgora; }).length;\n'
            '    if (!mudou.length) frase = "Nada mudou de lugar.";\n'
            '    else if (mudou.length === 1) {\n'
            '      var m = mudou[0], nome = String(m.ap.tipo || "aparel'
            'ho").toLowerCase();\n'
            '      frase = m.entradaAgora\n'
            '        ? "O " + nome + " mudou para a " + naFraseDe(m.ent'
            'radaAgora) + ", e eu já sei onde ele está."\n'
            '        : "O " + nome + " mudou de lugar, e eu ainda não s'
            'ei em qual entrada ele está.";\n'
            '    } else {\n'
            '      frase = mudou.length + " aparelhos mudaram de lugar"'
            '\n'
            '        + (sab === mudou.length ? ", e eu já sei onde estã'
            'o."\n'
            '           : sab ? ", e eu sei onde " + sab + " estão." : '
            '", e eu ainda não sei em quais entradas.");\n'
            '    }\n'
            '    return \'<p class="aviso-uma-linha" role="status"><span'
            ' class="ok" aria-hidden="true">✓</span>\'\n'
            '      + "<span>" + emAtributo(frase) + "</span>"\n'
            '      + (mudou.length ? \'<button class="btn pequeno" id="a'
            'viso-ver" aria-expanded="\' + avisoAberto + \'">Ver</button>'
            '\' : "")\n'
            '      + \'<button class="btn aviso-fecha" id="aviso-fecha" '
            'aria-label="Fechar o aviso">&times;</button></p>\'\n'
            '      + (avisoAberto ? \'<div class="aviso-detalhe">\' + det'
            'alhe + "</div>" : "");\n'
            '  }\n'
            '  var avisoLeituras = null;\n'
            '  function acharOIdentificado() {\n'
            '    if (!identificando) return;\n'
            '    if (reexame(leituraAnterior, leituraAtual).some(functi'
            'on (m) { return m.ap.id === identificando; })) {\n'
            '      achado = identificando;\n'
            '    }\n'
            '    identificando = null;\n'
            '  }\n'
            '  function cuidarDoAviso() {\n'
            '    if (modo !== "reexame") {\n'
            '      if (avisoTimer) { clearTimeout(avisoTimer); avisoTim'
            'er = null; }\n'
            '      avisoAberto = false; avisoLeituras = null;\n'
            '      return;\n'
            '    }\n'
            '    /* uma leitura nova (outro `Examinar`) recomeça os 10 '
            's */\n'
            '    if (avisoLeituras !== LEITURAS) {\n'
            '      recomecarOAviso(); avisoLeituras = LEITURAS; acharOI'
            'dentificado();\n'
            '    }\n'
            '    if (avisoTimer || avisoAberto) return;\n'
            '    avisoTimer = setTimeout(function () {\n'
            '      avisoTimer = null;\n'
            '      if (modo === "reexame" && !avisoAberto) { modo = "me'
            'sa"; pintar(); }\n'
            '    }, AVISO_SOME_EM_MS);\n'
            '  }\n'
            '  function recomecarOAviso() {\n'
            '    if (avisoTimer) { clearTimeout(avisoTimer); avisoTimer'
            ' = null; }\n'
            '    avisoAberto = false; avisoLeituras = null;\n'
            '  }\n'
            '\n'
            '  function mostrarEditorDaEntrada() {\n'
            '    var ed = document.getElementById("edita");\n'
            '    if (!ed) return;\n'
        ),
        porque=(
            '04/10/2026, O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 — o pai'
            'nel do aparelho e o arrastar; o editor antigo vira o da EN'
            'TRADA VAZIA e o `mostrarEditor` escolhe um dos dois.'
        ),
    ),
    Edicao(
        antes=(
            '[["direto", "Direto"], ["hub", "Hub"], ["extensor", "Exten'
            'sor"]].map'
        ),
        depois=(
            '[["direto", "Direto"], ["hub", "Hub"]].map'
        ),
        porque=(
            '04/10/2026, O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 — o ext'
            'ensor deixa de ser «o que tem aqui»: é a chave da porta, s'
            'eparada do que está ligado nela.'
        ),
    ),
    Edicao(
        antes=(
            '<div class="edita-linha"><span>O que tem aqui</span><div c'
            'lass="seg">\''
        ),
        depois=(
            '<div class="edita-linha"><span>O que tem aqui</span><div c'
            'lass="seg dois">\''
        ),
        porque=(
            '04/10/2026, O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 — duas '
            'respostas, duas colunas.'
        ),
    ),
    Edicao(
        antes=(
            '      + "</div>" + (lido ? \'<span class="lido">O computado'
            'r lê um hub nela.</span>\' : "") + "</div>"'
        ),
        depois=(
            '      + "</div>" + (lido ? \'<span class="lido">O computado'
            'r lê um hub nela.</span>\' : "") + "</div>"\n'
            '      + linhaDoExtensor(editando)'
        ),
        porque=(
            '04/10/2026, O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 — a cha'
            've «Extensor» na entrada vazia.'
        ),
    ),
    Edicao(
        antes=(
            '      + (soNaTela ? "" : linhaDaTroca(editando));'
        ),
        depois=(
            '      + (soNaTela ? "" : linhaDoLugar(editando) + linhaDaT'
            'roca(editando));'
        ),
        porque=(
            '04/10/2026, O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 — o cam'
            'po «Lugar» (absorvido da A-ENTRADA-SEM-LUGAR-APARECE-NO-MA'
            'PA-01) no editor da entrada.'
        ),
    ),
    Edicao(
        antes=(
            '    return \'<div class="edita-linha"><span>Trocar de lugar'
            "</span>'"
        ),
        depois=(
            '    return \'<div class="edita-linha"><span>Mover para…</sp'
            "an>'"
        ),
        porque=(
            '04/10/2026, O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 — «Move'
            'r para…», o nome do botão para quem usa teclado ou leitor '
            'de tela.'
        ),
    ),
    Edicao(
        antes=(
            '      + \'<option value="">Trocar com…</option>\''
        ),
        depois=(
            '      + \'<option value="">Mover para…</option>\''
        ),
        porque=(
            '04/10/2026, O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 — a pri'
            'meira opção diz o mesmo que o rótulo.'
        ),
    ),
    Edicao(
        antes=(
            '    return \'<div class="edita-linha"><span>Nome</span><inp'
            'ut class="campo-nome" type="text"'
        ),
        depois=(
            '    return \'<div class="edita-linha"><span>Nome da entrada'
            '</span><input class="campo-nome" type="text"'
        ),
        porque=(
            '04/10/2026, O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 — com o'
            ' nome do aparelho no painel, o campo da entrada diz de que'
            'm é o nome.'
        ),
    ),
    Edicao(
        antes=(
            '    var plano = {}, motivo = {};\n'
            '    var portas = todasPortas()'
        ),
        depois=(
            '    var plano = {}, motivo = {};\n'
            '    /* A FILEIRA «SEM LUGAR» NÃO ENTRA NO PLANO — 04/10/20'
            '26: sem o lugar (a face) o motor não\n'
            '       tem o que julgar, então quem está nela fica onde es'
            'tá e ninguém é mandado para lá. */\n'
            '    APARELHOS.forEach(function (a) { if (aparelhoSemLugar('
            'a.id)) plano[portaDe(a.id)] = a.id; });\n'
            '    var portas = todasPortas()'
        ),
        porque=(
            '04/10/2026, O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 — quem '
            'mora na fileira «Sem Lugar» fica onde está no plano.'
        ),
    ),
    Edicao(
        antes=(
            '      APARELHOS.filter(function (a) { return a.classe === '
            'cl; }).forEach(function (ap) {'
        ),
        depois=(
            '      APARELHOS.filter(function (a) { return a.classe === '
            'cl && !aparelhoSemLugar(a.id); }).forEach(function (ap) {'
        ),
        porque=(
            '04/10/2026, O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 — o pla'
            'no não reescolhe quem está sem lugar.'
        ),
    ),
    Edicao(
        antes=(
            '    var portas = todasPortas().filter(function (p) { retur'
            'n !proibida(p) && !doHubDesenhado(p); });'
        ),
        depois=(
            '    var portas = todasPortas().filter(function (p) { retur'
            'n !proibida(p) && !doHubDesenhado(p) && !semLugar(p); });'
        ),
        porque=(
            '04/10/2026, O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 — ningu'
            'ém é mandado para a fileira «Sem Lugar».'
        ),
    ),
    Edicao(
        antes=(
            '    if (ctx.modo === "ideal") {\n'
            '      var idPlano'
        ),
        depois=(
            '    if (ctx.modo === "ideal" && !semLugar(porta)) {\n'
            '      var idPlano'
        ),
        porque=(
            '04/10/2026, O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 — no «S'
            'ugestões» a fileira «Sem Lugar» segue como está: sem vered'
            'ito.'
        ),
    ),
    Edicao(
        antes=(
            '      var j = julgar(porta);\n'
            '      if (ap) {'
        ),
        depois=(
            '      var j = semLugar(porta) ? null : julgar(porta);\n'
            '      if (ap) {'
        ),
        porque=(
            '04/10/2026, O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 — a ent'
            'rada sem lugar não leva veredito de lugar.'
        ),
    ),
    Edicao(
        antes=(
            '      + ensinaNaEntrada(porta)\n'
        ),
        depois=(
            '      + ensinaNaEntrada(porta)\n'
            "      + (achado && alocacao[porta.n] === achado ? ' data-a"  # (noqa-acento: JS)
            'chado="1"\' : "")\n'
        ),
        porque=(
            '04/10/2026, O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 — «Iden'
            'tificar» (tire e ponha): depois do «Examinar» a entrada em'
            ' que o aparelho estava acende.'
        ),
    ),
    Edicao(
        antes=(
            '        + faixa + "</div>";\n'
            '    }).join("");'
        ),
        depois=(
            '        + (f.leitura && modo !== "ideal"\n'
            '            ? \'<p class="leitura-da-maquina">\' + f.leitura'
            '.map(emAtributo).join(" · ") + "</p>" : "")\n'
            '        + faixa + "</div>";\n'
            '    }).join("");'
        ),
        porque=(
            '04/10/2026, O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 — a lei'
            'tura da máquina em palavras curtas, embaixo do hub.'
        ),
    ),
    Edicao(
        antes=(
            '        + \'<button class="btn" id="ver-antes">Ver como o a'
            'rranjo estava \' + (leituraAtual === "agora" ? "antes" : "a'
            'gora") + "</button></div>";\n'
            '    } else if (modo === "mao") {'  # (noqa-acento: JS)
        ),
        depois=(
            '        + \'<button class="btn" id="ver-antes">Ver como o a'
            'rranjo estava \' + (leituraAtual === "agora" ? "antes" : "a'
            'gora") + "</button></div>";\n'
            '      html = oAvisoDeUmaLinha(mudou, html);\n'
            '    } else if (modo === "mao") {'  # (noqa-acento: JS)
        ),
        porque=(
            '04/10/2026, O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 — o avi'
            'so de «mudou de lugar» vira uma linha com ✓, «Ver» e ✕; o '
            'detalhe de antes só abre no «Ver».'
        ),
    ),
    Edicao(
        antes=(
            '    painel.innerHTML = html;\n'
        ),
        depois=(
            '    painel.innerHTML = html;\n'
            '    cuidarDoAviso();\n'
        ),
        porque=(
            '04/10/2026, O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 — o avi'
            'so some sozinho em 10 s.'
        ),
    ),
    Edicao(
        antes=(
            '      modo = "reexame"; segurando = null; naMao = null; pi'
            'ntar(); return;'
        ),
        depois=(
            '      recomecarOAviso(); modo = "reexame"; segurando = nul'
            'l; naMao = null; pintar(); return;'
        ),
        porque=(
            '04/10/2026, O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 — cada '
            '«Examinar» recomeça os 10 s do aviso.'
        ),
    ),
    Edicao(
        antes=(
            '      if (!pai || pai.closest("code, script, style, .camin'
            'ho, .chip .txt span")) return;'
        ),
        depois=(
            '      if (!pai || pai.closest("code, script, style, .camin'
            'ho, .chip .txt span, .aviso-uma-linha, .leitura-da-maquina'
            ', .faz, .dica-id, .etq, .faixa-dele-txt")) return;'
        ),
        porque=(
            '04/10/2026, O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 — as fr'
            'ases do aviso, da leitura, do «o que fazer» e da faixa del'
            'e ficam como frases.'
        ),
    ),
    Edicao(
        antes=(
            '    var ordem = ["hub", "teclado", "wifi", "bt", "mouse"'
            ', "webcam"];\n'
            '    var jaPostos = [];\n'
        ),
        depois=(
            '    var ordem = ["hub", "teclado", "wifi", "bt", "mouse"'
            ', "webcam"];\n'
            '    var jaPostos = [];\n'
            '    /* O APARELHO QUE O PLANO NÃO SABE ARRUMAR FICA ONDE'
            ' ESTÁ — 04/10/2026,\n'
            '       AS-DICAS-SAO-CARTOES-COM-UM-GESTO-01. Um aparelho'
            ' de classe fora da\n'
            '       ordem de decisão (um pendrive, uma placa que ning'
            'uém classificou) nunca\n'
            '       entra no plano; sem esta reserva a entrada dele v'  # (noqa-acento: JS)
            'alia como livre, outro\n'
            '       aparelho a recebia e o mapa dizia «sai daqui» sem'
            ' destino. A entrada\n'
            '       fica com ele, com o motivo «fica». É a gêmea de\n'
            '       `arranjo_da_mesa._o_que_o_plano_nao_sabe_arrumar_'
            'fica`. */\n'
            '    APARELHOS.forEach(function (a) {\n'
            '      if (ordem.indexOf(a.classe) !== -1) return;\n'
            '      var hoje = portaDe(a.id);\n'
            '      if (!hoje || plano[hoje]) return;\n'
            '      plano[hoje] = a.id;\n'
            '      motivo[a.id] = { razoes: [], peso: "melhora", ganh'
            'o: 0, forcado: false, essencial: false };\n'
            '    });\n'
        ),
        porque=(
            '04/10/2026, AS-DICAS-SAO-CARTOES-COM-UM-GESTO-01 — o apa'
            'relho que o plano não sabe arrumar fica onde está (a gêm'
            'ea JS do arranjo_da_mesa).'
        ),
    ),
)



#: ══ AS EDIÇÕES QUE ESPERAM A SESSÃO DOS DESENHOS — 24/09/2026 ════════════
#:
#: A tela para no mockup até o OK dela (ordem de 23/09), e esta página tem DUAS
#: casas que o gerador responde: a bancada, que o `main()` grava, e a cópia do
#: produto, que só muda pelo `--publicar`. As edições daqui entram na bancada e
#: ficam FORA da conta da cópia do produto (o `com_as_que_esperam=False`)
#: — é isso que deixa a régua da igualdade (`test_arranjo_invariantes`) verde
#: enquanto o desenho espera por ela.
#:
#: QUEM PUBLICAR, no mesmo commit do `--publicar mapa-das-portas.html`, junta
#: as edições daqui ao fim de `EDICOES` e deixa esta tupla vazia. A régua da
#: igualdade reprova dizendo isto se a cópia do produto receber o desenho e as
#: edições continuarem aqui. Vazia desde 26/09/2026 e de novo em 03/10 e 05/10: as do
#: O-MAPA-DAS-CONEXOES-CABE-NA-ABA-E-FALA-MENOS-01 e as do conjunto «Conexões 2»
#: foram publicadas e entraram no fim de `EDICOES`.
EDICOES_ESPERANDO_A_SESSAO_DELA: tuple[Edicao, ...] = ()


def pagina(com_as_que_esperam: bool = True) -> str:
    """A página: a origem congelada mais as :data:`EDICOES`.

    Com ``com_as_que_esperam`` (o padrão, e é a BANCADA), vêm também as
    :data:`EDICOES_ESPERANDO_A_SESSAO_DELA`; sem ele, sai a cópia que o produto
    tem hoje.

    Cada troca é cobrada: `antes` tem de aparecer uma vez e só uma. É o que
    impede uma edição de envelhecer calada — `str.replace` de um pedaço que não
    existe devolve o texto intacto e não levanta nada, e foi assim que as duas
    casas divergiram em treze pedaços sem ninguém ver.
    """
    texto = ORIGEM.read_text(encoding="utf-8")
    edicoes = EDICOES + (EDICOES_ESPERANDO_A_SESSAO_DELA if com_as_que_esperam else ())
    for numero, edicao in enumerate(edicoes, 1):
        quantas = texto.count(edicao.antes)
        if quantas != 1:
            raise SystemExit(
                f"ERRO na edição {numero}: o pedaço aparece {quantas} vez(es) na "
                f"origem, e tem de aparecer UMA.\n"
                f"  motivo declarado: {edicao.porque}\n"
                f"  pedaço: {edicao.antes[:120]!r}")
        texto = texto.replace(edicao.antes, edicao.depois, 1)
    return texto


def main(argv: list[str] | None = None) -> int:
    _ = argv
    novo = pagina()
    antes = DESTINO.read_text(encoding="utf-8") if DESTINO.exists() else ""
    DESTINO.write_text(novo, encoding="utf-8")
    print(f"mapa-das-portas: {len(EDICOES)} edições sobre a origem congelada"
          f" + {len(EDICOES_ESPERANDO_A_SESSAO_DELA)} esperando a sessão dela · "
          f"{len(novo.splitlines())} linhas · "
          f"{'mudou' if novo != antes else 'já estava igual'}")
    print(f"  escrito em {DESTINO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
