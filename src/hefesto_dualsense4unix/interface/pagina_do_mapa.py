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

from hefesto_dualsense4unix.interface import caixa_da_janela, onde

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

  function aplicarArranjo(f) {
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
    editando = null;
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

  window.hefestoArranjo = function (dado) {
    var falta = CAMPOS_DO_ARRANJO.filter(function (c) { return !dado || !dado[c]; });
    if (falta.length) {
      /* RECUSAR É METADE DO TRABALHO: meio arranjo desenharia um gabinete sem
         entradas, e isso se lê como "não tenho nada ligado". */
      throw new Error("arranjo incompleto, falta: " + falta.join(", "));
    }
    aplicarArranjo(dado);
    dizerDeQuando();
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
            "              + \"<b>GUIA-RADIO-DA-SALA</b>, §6.3 — e o controle precisa "
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
            '              + "<b>GUIA-RADIO-DA-SALA</b>, §6.3 — e o controle '
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
#: edições continuarem aqui. Vazia desde 26/09/2026: as doze do mapa das
#: conexões foram publicadas pela O-MAPA-DAS-CONEXOES-NO-PRODUTO-01.
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
