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

    docs/process/sprints/2026-08-24-ABA-CONEXOES/mockup/mapa-das-portas.html
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

from hefesto_dualsense4unix.interface import onde

#: A ESPECIFICAÇÃO EXECUTÁVEL. Congelada por decisão: reescrevê-la reescreveria
#: o ouro de 120 cenários, e apagaria o registro de como o motor falava em
#: 24/08/2026 — que é o que aquela pasta datada é.
ORIGEM = (onde.RAIZ / "docs" / "process" / "sprints" / "2026-08-24-ABA-CONEXOES"
          / "mockup" / "mapa-das-portas.html")

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
  }

  function dizerDeQuando() {
    /* O cabeçalho nasce dizendo o exemplo, no HTML, para a página ser honesta
       mesmo sem JavaScript nenhum. Aqui ele passa a dizer de quando é o que
       está na tela. */
    var el = document.getElementById("de-quando");
    if (el) el.textContent = fonte.quando;
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
            "sai dos dois que a carregavam. O `data-modo` NÃO muda: "  # (noqa-acento)
            "\"mao\" é endereço, e trocá-lo quebra o `julgar` que o lê."  # (noqa-acento)
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
)


def pagina() -> str:
    """A página do produto: a origem congelada mais as :data:`EDICOES`.

    Cada troca é cobrada: `antes` tem de aparecer uma vez e só uma. É o que
    impede uma edição de envelhecer calada — `str.replace` de um pedaço que não
    existe devolve o texto intacto e não levanta nada, e foi assim que as duas
    casas divergiram em treze pedaços sem ninguém ver.
    """
    texto = ORIGEM.read_text(encoding="utf-8")
    for numero, edicao in enumerate(EDICOES, 1):
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
    print(f"mapa-das-portas: {len(EDICOES)} edições sobre a origem congelada · "
          f"{len(novo.splitlines())} linhas · "
          f"{'mudou' if novo != antes else 'já estava igual'}")
    print(f"  escrito em {DESTINO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
