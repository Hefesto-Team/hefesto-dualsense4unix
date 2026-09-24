#!/usr/bin/env python3
"""A página de calibração dos sensores de movimento — `mockup/calibrar-sensores.html`.

PEDIDO DELA, 31/08/2026, e é o segundo botão que ela mandou nascer na Controles:

    "Preciso que crie uma nova página que abre e mostra os svgs dos controles
     conectados e o procedimento igual o da steam pra calibrar os controles.
     São os 4 ao mesmo tempo."

OS TRÊS ESTADOS SÃO CLICÁVEIS, e isso é decisão de instrumento. Um mockup é
estático: ele desenha UM estado. Um procedimento tem TRÊS (parado, medindo,
pronto), e desenhar só um esconde dois terços do que ela precisa julgar. A saída
é a mesma gramática que a Jogar já usa no interruptor e a Controles no cartão que
abre — `<input type=radio>` escondido mais `:checked` no CSS. Ela clica e vê o
procedimento inteiro, sem uma linha de JavaScript.

O QUE "OS 4 AO MESMO TEMPO" QUER DIZER, e vale escrever porque é o ponto do
pedido: a calibração é de TODOS de uma vez, não um controle por vez. Quem tem
quatro na mesa não repete o gesto quatro vezes. A tela mostra os que estão
conectados — hoje dois, pela decisão dela do mesmo dia de deixar dois fora.

POR QUE O PROCEDIMENTO DA STEAM: é o que ela nomeou, e ele é o mínimo honesto —
o giroscópio zera medindo o repouso, então a única coisa que a pessoa precisa
fazer é **não mexer**. Toda instrução a mais é ruído.

A PALETA E O ESQUELETO SÃO OS DO `mapa.py`, copiados de propósito: as duas são
páginas que abrem POR FORA das dez abas, e uma segunda gramática de página
avulsa na mesma janela seria uma a mais.

**A CAIXA É A DA JANELA DAS ABAS** desde 23/09/2026
(A-CALIBRACAO-TEM-O-TAMANHO-DO-PROGRAMA-01), lida do `topo.html`, porque ela
pediu a Calibrar do tamanho do programa. Em 24/09/2026 ela decidiu que o «Mapa
do controle» e o mapa das portas seguem a mesma caixa, e as três avulsas
passaram a pedi-la ao mesmo dono, `caixa_da_janela.py`
(AS-PAGINAS-AVULSAS-TEM-A-CAIXA-DA-JANELA-01).

OS CONTROLES SÃO DE QUEM ABRE A PÁGINA — 11/09/2026, F3-CALIBRAR
-----------------------------------------------------------------

Até hoje esta página desenhava `monta.CONECTADOS` (o desenho, sempre dois) com
números de uma constante deste arquivo (`REPOUSO`, seis por controle). Medido no
daemon dela em 11/09, com os dois DualSense na bancada:

    a tela dizia            o aparelho respondia
    P1 · Cosmic Red · USB   P1 · Starlight Blue · USB
    P2 · Starlight Blue·BT  P2 · Cosmic Red · BT
    giro +0.2 -0.1 +0.0     `inputs` sem chave `gyro` nenhuma

Ou seja: **os dois controles trocados e as doze leituras inventadas** — e com
quatro na bancada ela veria dois. `REPOUSO` MORREU: os seis eixos de cada
controle nascem no travessão, que é como esta casa escreve *"ninguém leu"*
(`mesa_viva.SEM_LEITOR`), e quem os preenche é o tique, por
`pacotes/a11_calibrar_sensores.py`.

**POR QUE O TRAVESSÃO E NÃO UM NÚMERO DE EXEMPLO**, que é o que a aba Controles
faz na cena fixa dela: aquela página tem pacote desde 01/09 e o número do
desenho vive um tique. Esta ficou eloquente por ONZE DIAS sem ninguém a pintar,
e o que estava na tela era afirmação. Um arquivo que nasce com número é um
arquivo que mente quando o tique não vem.
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import onde  # noqa: E402
import monta  # noqa: E402
import caixa_da_janela  # noqa: E402

#: Quanto tempo a medição leva. NÃO é chute: é o que o `--calibrate` do
#: `hefesto-dualsense4unix` já usa como janela de repouso. Escrito aqui uma vez,
#: e lido pelos dois lugares da página que o citam.
SEGUNDOS = 5

#: O QUE A TELA MOSTRA ONDE NÃO HÁ LEITURA. É o mesmo caractere e o mesmo
#: sentido de `mesa_viva.SEM_LEITOR` — nunca zero fingindo repouso, nunca o
#: último valor como se fosse de agora. Repetido aqui como literal porque este
#: gerador roda sem o pacote instalado (`python3 calibrar.py`), e a régua
#: `test_a_calibracao_mostra_quem_esta_na_mao.py` confere que os dois são o
#: MESMO caractere.
SEM_LEITURA = "—"

#: AS DUAS FAMÍLIAS DE EIXO, na ordem em que a tela as mostra. O rótulo sai só
#: na primeira das três linhas de cada família — é o desenho aprovado.
FAMILIAS = (("giro", "Giroscópio"), ("accel", "Acelerômetro"))

#: O QUE A PÁGINA DIZ SEM CONTROLE NENHUM, e zero é estado legítimo: ela pode
#: abrir a calibração com tudo desligado. A frase diz **o que falta e o que
#: fazer**, nas palavras do glossário (`cabo` · `rádio`, §1) — nunca um cartão
#: fantasma com travessão, que anunciaria um controle que não está aqui.
SEM_CONTROLE = ("Nenhum controle conectado. Ligue um pelo cabo ou pelo rádio "
                "e ele aparece aqui.")

# ---------------------------------------------------------------------------
# A MIRA VIRTUAL — 24/09/2026, A-MIRA-POR-MOVIMENTO-NA-TELA-01
# ---------------------------------------------------------------------------
# Palavra dela, 23/09: o chip «Mira Virtual» mora no cartão de cada controle, na
# aba Controles, e *"a sensibilidade e o «Ignorar tremor até» ficam na tela
# Calibrar sensores"*. São dois deslizantes POR CONTROLE, numa coluna embaixo do
# cartão daquele controle.
#
# UM BLOCO PRÓPRIO, E NÃO DENTRO DO CARTÃO — e a razão é o produto: o
# `pacotes/a11_calibrar_sensores` REMONTA o bloco dos cartões a cada mudança de
# bancada, pelo `controle()` deste arquivo. Um deslizante dentro do cartão
# chegaria à janela dela no primeiro tique, antes de ela aprovar o desenho.
#
# OS NÚMEROS SÃO DO ESQUEMA (`profiles/schema.ProfileMovimentoConfig`), e estão
# escritos aqui porque este gerador roda sem o pacote instalado — a régua
# `test_a_mira_por_movimento_na_tela.py` confere que são os mesmos. O mínimo do
# tremor é 1, e não o 0 que o esquema aceita: é a faixa da sprint, e o 0 não
# ignora tremor nenhum.
#
# O RÓTULO DO TREMOR NÃO DIZ «zona morta»: a palavra técnica esconde para que
# o campo serve, e ele é o campo de acessibilidade desta tela (§3 da sprint).
ROTULO_DA_MIRA = "Mira Virtual"
ROTULO_SENSIBILIDADE = "O quanto um gesto anda"
ROTULO_TREMOR = "Ignorar tremor até"
UNIDADE_DO_TREMOR = "graus/s"
SENSIBILIDADE = (1, 12, 6)   # mínimo, máximo, o de nascença
TREMOR = (1, 60, 3)          # idem, em graus/s
#: A linha que liga os deslizantes ao chip. Sem ela os dois números flutuam na
#: página de calibração sem dizer a que servem.
DE_ONDE_VEM_A_MIRA = ("Valem para o controle com a Mira Virtual acesa, na aba "
                      "Controles.")

# ---------------------------------------------------------------------------
# «SÓ ENQUANTO EU SEGURAR» E «INVERTER» — 24/09/2026, A-MIRA-POR-MOVIMENTO-NA-TELA-02
# ---------------------------------------------------------------------------
# Palavra dela na página da sessão dos desenhos
# (`D-2409-SEGURAR-E-INVERTER-ENTRAM-NA-TELA`): «entram as duas». Os dois já
# estavam no esquema e no motor (`ProfileMovimentoConfig.gatilho`,
# `inverter_horizontal`, `inverter_vertical`); faltava a tela. Moram na coluna
# de cada controle, embaixo dos dois deslizantes, e nascem DESLIGADOS: a mira
# anda sempre, e nada inverte.
#
# OS BOTÕES DA LISTA SÃO OS DO ESQUEMA, e não uma lista escrita aqui: é
# `remapeamento_de_botao.REMAPEAVEIS`, a mesma de que o esquema recusa o que
# não está nela — o PS fica fora porque é a saída de emergência dela. (O
# `monta`, que este gerador importa, já puxa o pacote; a nota do topo sobre
# rodar sem ele caducou para os geradores que o importam.)
from hefesto_dualsense4unix.core.remapeamento_de_botao import (  # noqa: E402
    REMAPEAVEIS,
)

ROTULO_SEGURAR = "Só enquanto eu segurar"
#: A opção de nascença da lista: a mira anda sem botão nenhum. O VALOR não é o
#: vazio porque o alvo `valor` do piloto troca o vazio pelo travessão, e um
#: `<select>` não aceita o que não oferece — a lista nunca voltaria a «Sempre».
ROTULO_SEMPRE = "Sempre"
SEMPRE = "sempre"
ROTULO_INVERTER = "Inverter"
#: Os dois lados do «Inverter», cada um por si: `(o valor do `data-inverter`,
#: o rótulo do botão, o campo do esquema)`.
INVERTER = (
    ("lado", "Esquerda e direita", "inverter_horizontal"),
    ("cima-baixo", "Cima e baixo", "inverter_vertical"),
)

#: OS TRÊS BOTÕES CUJO ID DO JOGO NÃO É O ID DA PEÇA no mapa das peças: o clique
#: dos dois analógicos e o Create, que o mapa chama pelo nome do plástico antigo.
_PECA_DO_BOTAO = {"l3": "stick_l", "r3": "stick_r", "create": "share"}


def _pecas() -> dict:
    """O mapa das peças (`docs/data/pecas-do-dualsense.csv`), por id."""
    import csv

    linhas = [x for x in (monta.DADOS_DO_REPO / "pecas-do-dualsense.csv")
              .read_text(encoding="utf-8").splitlines() if x and not x.startswith("#")]
    return {p["id"]: p for p in csv.DictReader(linhas)}


def nome_do_botao(botao, pecas=None):
    """O nome curto do botão na tela, LIDO do mapa das peças.

    A MESMA REGRA da troca de botões da aba Navegação (`aba06.nome_de`): o
    `nome` quando ele é curto, e o apelido curto quando não é — é de lá que
    saem o L3 e o R3. Uma segunda regra aqui faria a mesma peça ter dois nomes
    na mesma janela.
    """
    p = (pecas or _pecas())[_PECA_DO_BOTAO.get(botao, botao)]
    if len(p["nome"]) <= 8:
        return p["nome"]
    for a in p["apelidos"].split("|"):
        if a.isalnum() and len(a) <= 3:
            return a
    return p["nome"]


def _opcoes_do_segurar():
    """`(valor, rótulo)` de cada opção da lista, «Sempre» primeiro."""
    pecas = _pecas()
    return [(SEMPRE, ROTULO_SEMPRE)] + [(b, nome_do_botao(b, pecas)) for b in REMAPEAVEIS]


def plural(quantos: int, um: str, muitos: str) -> str:
    """Uma das duas palavras, pela contagem. ``0`` usa o plural, como em português.

    POR QUE ELE EXISTE, e o defeito é medido: esta página escrevia
    ``dos {n} controles`` e caía em *"dos 1 controles"* com um controle só
    (`calibrar.py:219`, antes de 11/09). **O plural dito com um «s» entre
    parênteses não existe em língua nenhuma além da nossa** e não tem como ser
    traduzido: em inglês são duas formas, em russo são três.

    A PROIBIÇÃO NÃO SE ESCREVE COM O PADRÃO PROIBIDO, e a armadilha é desta
    casa: um comentário que CITA a forma banida vira a primeira ocorrência dela
    — aconteceu três vezes em três dias, e aconteceu aqui, no primeiro rascunho
    desta docstring.

    ELE É O DONO DA CONCORDÂNCIA DESTA PÁGINA, e os dois lados a leem daqui: o
    gerador, para o texto que o arquivo carrega, e `a11_calibrar_sensores`, para
    o que o tique escreve por cima. Um número com dono, redigitado, é um número
    esperando para divergir.

    A CASA TEM QUATRO IRMÃOS DESTE — `a09_sistema._plural` (11/09),
    `desenho_dos_lancadores._plural`, `aba08._plural` e
    `integrations.ordens_da_mesa._plural` —, e nenhum deles é importável daqui
    sem acoplar esta página avulsa a uma aba ou ao motor. **Promovê-los a um
    dono só é trabalho declarado e de outra posse**: são quatro arquivos, três
    deles de território alheio nesta leva.
    """
    return um if quantos == 1 else muitos


def contagem(quantos: int) -> str:
    """`Nenhum controle conectado` · `1 controle conectado` · `4 controles conectados`.

    É a linha do rodapé que diz **de quem** são os números da tela, antes de ela
    apertar «Começar». Com zero ela fica vazia de propósito: o lugar dos cartões
    já traz a frase inteira (:data:`SEM_CONTROLE`), e repetir a ausência em dois
    lugares é a pergunta 4 da vistoria de língua — *repete o que a tela já diz
    por outro meio?*
    """
    if quantos <= 0:
        return ""
    return f"{quantos} {plural(quantos, 'controle conectado', 'controles conectados')}"


CSS = """
  :root{
    --app-bg:#21222c; --panel:#282a36; --elevated:#2b2d3a;
    --border-sutil:#343746; --border-forte:#44475a; --linha:#53576f;
    --fg:#f8f8f2; --texto-suave:#c8ccda; --texto-mudo:#9a9eb8; --comment:#8896c4;
    --cyan:#8be9fd; --green:#50fa7b; --orange:#ffb86c;
    --pink:#ff79c6; --purple:#bd93f9; --red:#ff5555;
    --sel-bg:rgba(189,147,249,.16);
    --f:ui-sans-serif,system-ui,"Cantarell","Segoe UI",Roboto,sans-serif;
    --m:ui-monospace,"JetBrains Mono","Fira Mono","DejaVu Sans Mono",monospace;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  /* O RECUO DO `body` E O TAMANHO DA `.cx` NÃO MORAM AQUI — 23/09/2026: vêm
     da `moldura()`, lidos do `topo.html`. A razão está acima de `calibrar.moldura`. */
  body{background:#11121a;color:var(--fg);font-family:var(--f);
       display:flex;flex-direction:column;align-items:center;gap:16px}
  .mono{font-family:var(--m)}
  /* COLUNA COMO A `.janela`: o cabeçalho fica, o `.corpo` rola por dentro
     quando a vista encolhe, e a caixa nunca passa da tela. */
  .cx{background:var(--app-bg);border-radius:11px;
      border:1px solid var(--border-sutil);overflow:hidden;
      display:flex;flex-direction:column}
  .topo{padding:15px 20px;border-bottom:1px solid var(--border-sutil);
        position:relative;padding-left:132px;flex:0 0 auto}
  h1{font-size:18px;font-weight:700}
  h1 .p{color:var(--pink)}
  .sub{font-size:12.5px;color:var(--texto-mudo);margin-top:3px}
  .voltar{position:absolute;left:20px;top:17px;display:inline-flex;align-items:center;
          gap:6px;padding:5px 11px;border-radius:7px;text-decoration:none;
          border:1px solid var(--border-forte);background:var(--panel);
          color:var(--texto-suave);font-size:12px}
  .voltar:hover{border-color:var(--comment);color:var(--fg)}

  .corpo{padding:18px 20px 20px;display:flex;flex-direction:column;gap:14px;
         flex:1;min-height:0;overflow-y:auto}

  /* ---------- OS TRÊS ESTADOS ----------
     Os rádios vêm ANTES de tudo o que reage a eles: o `~` do CSS só enxerga
     irmão POSTERIOR. É a mesma armadilha que o interruptor da aba Jogar
     documenta, e a mesma cura. */
  .et{position:absolute;width:0;height:0;opacity:0;pointer-events:none}

  .passos{display:flex;gap:9px}
  .passo{flex:1;display:flex;gap:10px;align-items:flex-start;
         padding:11px 13px;border-radius:9px;border:1px solid var(--border-sutil);
         background:var(--panel);cursor:pointer}
  .passo .n{flex:0 0 22px;height:22px;border-radius:50%;display:flex;
            align-items:center;justify-content:center;font-family:var(--m);
            font-size:11px;border:1px solid var(--border-forte);color:var(--texto-mudo)}
  .passo b{display:block;font-size:13px;font-weight:600;margin-bottom:2px}
  .passo span.d{font-size:12px;color:var(--texto-mudo);line-height:16px}
  /* O PASSO EM QUE ELA ESTÁ. Cor explícita, nada de `opacity` — a lição medida
     da `.fita.inerte`: a opacidade tira contraste E peso do traço ao mesmo
     tempo, e o que sobra deixa de comunicar o que foi desenhado. */
  #e-parado:checked  ~ .passos .passo:nth-child(1),
  #e-medindo:checked ~ .passos .passo:nth-child(2),
  #e-pronto:checked  ~ .passos .passo:nth-child(3){
    border-color:var(--purple);background:var(--sel-bg)}
  #e-parado:checked  ~ .passos .passo:nth-child(1) .n,
  #e-medindo:checked ~ .passos .passo:nth-child(2) .n,
  #e-pronto:checked  ~ .passos .passo:nth-child(3) .n{
    border-color:var(--purple);color:var(--fg)}

  /* `.controles` E NÃO `.mesa` — 11/09/2026. A palavra é banida em texto de
     tela (decisão dela, 06/09) e o nome da classe não chega a lê-la, mas este
     bloco passou a ser o alvo que o produto TROCA a cada mudança de bancada, e
     o seletor vive escrito no pacote: `[data-bloco="controles"]`. Um endereço
     novo nasce na língua de hoje. */
  .controles{display:flex;gap:11px}
  /* SEM CONTROLE NENHUM não é cartão vazio: é uma frase. Ver `SEM_CONTROLE`. */
  .vazio{flex:1;padding:22px 14px;text-align:center;border-radius:9px;
         border:1px dashed var(--border-forte);background:var(--panel);
         color:var(--texto-mudo);font-size:13px;line-height:19px}
  .ctr{flex:1;border:2px solid var(--plastico,var(--border-forte));border-radius:9px;
       background:var(--panel);padding:11px 12px 12px;display:flex;
       flex-direction:column;gap:8px;min-width:0}
  .ctr-topo{display:flex;align-items:center;gap:9px;min-width:0}
  .ctr .nome{font-size:12.5px;color:var(--texto-mudo);line-height:15px;white-space:nowrap;
             overflow:hidden;text-overflow:ellipsis}
  .ctr .nome b{color:var(--fg);font-weight:600}
  /* `height:auto` NÃO É DETALHE: o SVG nasce com `width="1160" height="800"`
     nos atributos (é o tamanho que o rasterizador do ícone usa), e sem esta
     linha o `width:74px` do CSS encolhe SÓ a largura — a altura fica em 800 e
     estica o cartão inteiro. Medido: cada cartão saía com ~900px de vazio.
     As dez abas não sofrem disto porque o `topo.html` traz a regra no esqueleto
     comum; esta página tem folha própria, e por isso precisa dizê-la. */
  .ds-svg{width:74px;height:auto;flex:0 0 74px}
  .selo{margin-left:auto;flex:0 0 auto;font-size:11px;padding:2px 8px;border-radius:6px;
        border:1px solid var(--border-forte);color:var(--texto-mudo);white-space:nowrap}
  #e-medindo:checked ~ .controles .selo{border-color:var(--orange);color:var(--orange)}
  #e-pronto:checked  ~ .controles .selo{border-color:var(--green);color:var(--green)}
  .selo .t2,.selo .t3{display:none}
  #e-medindo:checked ~ .controles .selo .t1,
  #e-medindo:checked ~ .controles .selo .t3,
  #e-pronto:checked  ~ .controles .selo .t1,
  #e-pronto:checked  ~ .controles .selo .t2{display:none}
  #e-medindo:checked ~ .controles .selo .t2,
  #e-pronto:checked  ~ .controles .selo .t3{display:inline}

  .leitura{border-top:1px solid var(--border-sutil);padding-top:7px;
           display:flex;flex-direction:column;gap:5px}
  .lin{display:flex;align-items:center;gap:7px;font-family:var(--m);font-size:11px}
  .lin > .r{flex:0 0 80px;color:var(--texto-mudo)}
  .lin > .v{flex:0 0 52px;text-align:right;color:var(--texto-suave)}
  .lin > .g{flex:1;height:4px;border-radius:2px;background:var(--border-sutil);
            position:relative;overflow:hidden;color:var(--border-forte)}
  /* NO REPOUSO A BARRA É UM RISCO NO MEIO, e é isso que a tela precisa mostrar:
     o eixo parado marca o CENTRO. O risco deixou de ser um `<i>` e virou
     `::after` em 11/09/2026, e a troca é o que abriu lugar para a LEITURA: o
     `<i>` era o único filho do trilho, e pintá-lo com o valor vivo apagaria o
     centro. Pseudoelemento não disputa espaço com ninguém e o CSS continua
     sendo o dono dele.

     A BARRA BIPOLAR SÃO DUAS METADES, e a gramática é a da aba Controles
     (`aba02.py`, o bloco `.eixo .v`), pela mesma razão medida lá: o produto
     sabe escrever `width` (alvo `largura`) e `color` (alvo `cor`), e NÃO tem
     alvo de POSIÇÃO. Com um elemento só, a barra de um eixo negativo cresceria
     para o lado errado. A cor sobe para o trilho e desce por `currentColor` —
     um valor só, num elemento só. */
  .lin > .g::after{content:"";position:absolute;top:0;bottom:0;left:50%;width:2px;
                   background:var(--comment);transform:translateX(-1px);z-index:1}
  .lin > .g > i{position:absolute;top:0;bottom:0;border-radius:2px;
                background:currentColor}
  .lin > .g > i.neg{right:50%}
  .lin > .g > i.pos{left:50%}
  #e-pronto:checked ~ .controles .lin > .g::after{background:var(--green)}

  .barra{height:6px;border-radius:3px;background:var(--border-sutil);overflow:hidden}
  .barra > i{display:block;height:100%;width:0;background:var(--purple)}
  #e-medindo:checked ~ .rodape .barra > i{width:58%}
  #e-pronto:checked  ~ .rodape .barra > i{width:100%;background:var(--green)}

  /* O RODAPÉ DESCE PARA O FIM DA CAIXA, como o das abas: a altura que sobra
     vira vão ENTRE os cartões e os botões, nunca abaixo do aviso. */
  .rodape{display:flex;align-items:center;gap:13px;margin-top:auto}
  .rodape .barra{flex:1}
  /* A CONTA DE QUEM ESTÁ AQUI, e ela fica ao lado do botão de propósito: é a
     última coisa que a tela diz antes de ela apertar «Começar». Ver
     `contagem()` — com zero controles esta linha fica VAZIA, e quem fala é o
     lugar dos cartões. */
  .quantos{font-size:12px;color:var(--texto-mudo);white-space:nowrap}
  .btn{height:34px;padding:0 15px;border-radius:8px;font-size:13px;cursor:pointer;
       border:1px solid var(--border-forte);background:var(--panel);color:var(--texto-suave);
       display:inline-flex;align-items:center;text-decoration:none;white-space:nowrap}
  .btn:hover{border-color:var(--comment);color:var(--fg)}
  .btn.fazer{border-color:var(--green);color:var(--green)}
  .btn .t2,.btn .t3{display:none}
  #e-medindo:checked ~ .rodape .btn.fazer .t1,
  #e-medindo:checked ~ .rodape .btn.fazer .t3,
  #e-pronto:checked  ~ .rodape .btn.fazer .t1,
  #e-pronto:checked  ~ .rodape .btn.fazer .t2{display:none}
  #e-medindo:checked ~ .rodape .btn.fazer .t2,
  #e-pronto:checked  ~ .rodape .btn.fazer .t3{display:inline}
  #e-medindo:checked ~ .rodape .btn.fazer{border-color:var(--orange);color:var(--orange)}

  /* A MIRA VIRTUAL — 24/09/2026. As colunas repetem o `gap` e o `flex:1` dos
     cartões, e por isso cada uma cai embaixo do cartão do mesmo controle. */
  .mira-cx{border-top:1px solid var(--border-sutil);padding-top:11px;
           display:flex;flex-direction:column;gap:8px}
  .mira-cx:empty{display:none}
  .mira-topo{font-size:13px}
  .mira-topo b{font-weight:600}
  .mira-topo .d{font-size:12px;color:var(--texto-mudo);margin-left:6px}
  .miras{display:flex;gap:11px}
  .mira{flex:1;min-width:0;display:flex;flex-direction:column;gap:6px;
        padding:9px 12px;border-radius:9px;border:1px solid var(--border-sutil);
        background:var(--panel)}
  .mira .quem{font-size:11px;color:var(--texto-mudo)}
  /* O RÓTULO E O NÚMERO EM CIMA, O TRILHO EMBAIXO, na largura inteira da
     coluna. Lado a lado, com quatro controles numa janela de 1180px, sobravam
     ~23px de trilho por coluna; empilhado, o trilho é a coluna. */
  .desl{display:grid;grid-template-columns:1fr auto;align-items:center;
        column-gap:8px;row-gap:3px;font-size:12px}
  .desl .r{color:var(--texto-suave);white-space:nowrap;overflow:hidden;
           text-overflow:ellipsis;min-width:0}
  .desl .n{grid-row:1;grid-column:2;font-family:var(--m);font-size:11px;
           color:var(--fg);white-space:nowrap}
  .desl .un{color:var(--texto-mudo)}
  .desl .trilho{grid-row:2;grid-column:1 / -1;width:100%;margin:0;
                accent-color:var(--purple)}
  /* «SÓ ENQUANTO EU SEGURAR» E «INVERTER» — 24/09/2026, A-MIRA-POR-MOVIMENTO-
     NA-TELA-02. A MESMA GRAMÁTICA DOS DESLIZANTES: o rótulo em cima, o
     controle embaixo, na largura inteira da coluna — com quatro controles a
     coluna tem menos de 300px, e lado a lado a lista não caberia. */
  .desl .lista,.desl .inverter{grid-row:2;grid-column:1 / -1}
  .desl .lista{width:100%;height:24px;padding:0 8px;border-radius:6px;
               border:1px solid var(--border-forte);background:var(--app-bg);
               color:var(--fg);font-family:inherit;font-size:12px;cursor:pointer}
  .desl .lista:hover{border-color:var(--comment)}
  .desl .lista option{background:var(--panel);color:var(--fg)}
  /* OS DOIS «INVERTER» TÊM A CARA DOS CHIPS DE SENSOR da aba Controles
     (`aba02.py`, `.sensores-peca .sw`): o mesmo verde aceso, o mesmo apagado,
     a mesma pastilha de 17px. É cópia declarada — esta página tem folha
     própria, como a paleta do topo —, e um interruptor com outra cara na
     mesma janela seria um segundo vocabulário para o mesmo ato. */
  .inverter{display:flex;gap:6px;flex-wrap:wrap}
  .inverter .sw{height:17px;border-radius:6px;font-size:10.5px;font-family:inherit;
    cursor:pointer;border:1px solid var(--green);background:rgba(80,250,123,.09);
    color:var(--green);display:inline-flex;align-items:center;gap:6px;padding:0 10px;
    white-space:nowrap}
  .inverter .sw .p{width:6px;height:6px;border-radius:50%;background:var(--green);
    box-shadow:0 0 6px var(--green)}
  .inverter .sw.off{border-color:var(--border-forte);background:var(--app-bg);
    color:var(--texto-mudo)}
  .inverter .sw.off .p{background:var(--border-forte);box-shadow:none}
  .aviso{font-size:12px;color:var(--texto-mudo);line-height:17px}
  .aviso b{color:var(--texto-suave);font-weight:600}
"""


# A CAIXA TEM O TAMANHO DA JANELA DAS ABAS — 23/09/2026,
# A-CALIBRACAO-TEM-O-TAMANHO-DO-PROGRAMA-01. Ela, com a foto da tela:
#
#     "na aba de calibração ela tem altura e largura de layout inferior sendo
#      que deveria ser a mesma do programa."
#
# MEDIDO NO PILOTO ANTES DA CURA, na MESMA janela oculta, indo da Controles à
# Calibrar pelo botão dela:
#
#     vista       02-controles `.janela`   calibrar `.cx`
#     1212x809    1180 x 777               1168 x 499
#     1918x840    1600 x 808               1180 x 499   <- a TV dela
#     1212x700    1180 x 668               1168 x 499
#
# A vista era a mesma nas duas páginas, logo a janela hospeda as duas igual: a
# causa era ESTA folha — `width:1180px` (a largura das abas antes de 08/09),
# `body{padding:22px}` e a altura que o conteúdo desse.
#
# O TAMANHO TEM DONO, e é o `topo.html`: o recuo, o piso, o teto e a altura da
# vista (`--recuo-do-corpo`, `--piso-da-vista`, `--teto-da-vista`,
# `--alt-janela`) e as quatro propriedades de tamanho da `.janela`. Esta página
# os LÊ de lá a cada geração; redigitá-los aqui foi exatamente como o 1180
# ficou para trás quando as abas passaram a esticar.
#
# O LEITOR MUDOU DE CASA EM 24/09/2026 (AS-PAGINAS-AVULSAS-TEM-A-CAIXA-DA-
# JANELA-01): ele mora em `caixa_da_janela.py`, porque o «Mapa do controle» e o
# mapa das portas passaram a pedir a mesma caixa, e o mapa das portas é
# importado pelo produto por um caminho que não alcança este arquivo. O nome
# `moldura` fica aqui para quem já o chamava.
moldura = caixa_da_janela.moldura


def _svg(c):
    """O desenho do controle, na cor do plástico dele, sem as lâmpadas.

    As lâmpadas do jogador saem pelo mesmo motivo medido na aba Jogar: com 74px
    de desenho elas mediriam ~1,3 x 0,4 px. Abaixo de um pixel não é lâmpada
    apagada — é lâmpada que não cabe.

    A COR VEM POR `.get`, e não por `[...]` — 11/09/2026, e o defeito foi
    MEDIDO: o `pacotes._LUGAR_DE_MENTIRA`, com que o despachante roda a pintura
    fantasma do molde, não tem chave `cor`. O `KeyError` caía dentro do
    `except Exception` de `molde_do_lugar` e o molde saía **vazio, calado** — a
    forma exata do defeito que esta casa chama de ausência de notícia lida como
    sucesso. Modelo que o desenho não conhece cai no cinza sem identidade, que é
    o que a regra dela pede quando não há informação.
    """
    cor = str(c.get("cor") or "")
    if cor and not monta.o_desenho_conhece(cor):
        cor = ""
    return re.sub(r"<\?xml[^>]*\?>\s*", "",
                  monta.svg(f'cal-{c.get("pref") or "px"}', cor, lampadas=False))


def _eixos():
    """As seis linhas de leitura de um controle: três de giro, três de aceleração.

    TRÊS ENDEREÇOS POR EIXO, e são três porque um elemento só aceita UM alvo: o
    número é texto (`giro-x`), cada metade da barra é largura (`-neg`, `-pos`) e
    a cor sobe para o trilho (`-cor`). É a mesma repartição que a aba Controles
    documenta no `gx()` dela, e é o que faz o tique poder escrever a leitura sem
    tocar no desenho.

    NASCEM NO TRAVESSÃO E COM A BARRA A ZERO — ver o cabeçalho deste arquivo.
    """
    linhas = []
    for fam, rot in FAMILIAS:
        for i, e in enumerate("XYZ"):
            chave = f"{fam}-{e.lower()}"
            linhas.append(
                f'              <div class="lin" data-eixo="{chave}">'
                f'<span class="r">{rot if i == 0 else ""}</span>'
                f'<span class="v" data-campo="{chave}">{SEM_LEITURA}</span>'
                f'<span class="g" data-campo="{chave}-cor" data-hef-alvo="cor"'
                f' style="color:var(--border-forte)">'
                f'<i class="neg" data-campo="{chave}-neg" data-hef-alvo="largura"'
                f' style="width:0%"></i>'
                f'<i class="pos" data-campo="{chave}-pos" data-hef-alvo="largura"'
                f' style="width:0%"></i></span></div>')
    return "\n".join(linhas)


def _plastico(c):
    """A cor do plástico daquele controle, ou a borda neutra do tema.

    `monta.cor_da_zona` PARA a geração quando o modelo não existe no SVG — e
    está certo para a bancada, onde a lista é escrita à mão. Aqui a lista vem do
    APARELHO: um modelo que o desenho não conhece, ou a cor que o controle ainda
    não respondeu (`cor` vazio enquanto a primeira pergunta não volta), são
    respostas legítimas. É a mesma saída do `_cor_da_zona_tolerante` do piloto
    da aba Controles, e pela mesma razão.
    """
    cor = str(c.get("cor") or "")
    if cor and monta.o_desenho_conhece(cor):
        return monta.cor_da_zona(cor)
    return "var(--border-forte)"


def controle(c):
    """O cartão de UM controle — o desenho, a identidade e as seis linhas vazias.

    PÚBLICA PORQUE TEM DOIS CHAMADORES: o `main()`, que grava o arquivo, e
    `pacotes/a11_calibrar_sensores.py`, que o remonta a cada mudança de bancada.
    Reescrever o cartão do lado do pacote seria a segunda cópia do desenho — o
    defeito que `controles_vivos.html_da_mesa` já evitou chamando o gerador.
    """
    # TODO CAMPO POR `.get`, E COM O TRAVESSÃO NO LUGAR DO VAZIO. A lista vem do
    # APARELHO: um controle que o daemon publicou antes de resolver o número de
    # jogador, o modelo ou o transporte chega aqui com `None` — e `f"{None}"`
    # escreve a palavra `None` na tela dela. Ver a nota do `_svg`.
    jogador = c.get("jogador") or SEM_LEITURA
    nome = c.get("nome") or SEM_LEITURA
    via = c.get("via") or SEM_LEITURA
    return f'''          <div class="ctr" style="--plastico:{_plastico(c)}"
               data-controle="{c.get("pref") or ""}">
            <div class="ctr-topo">
              {_svg(c)}
              <span class="nome">Sony <span class="pt">•</span> <b>Player {jogador}</b><br>{nome} <span class="pt">•</span> {via}</span>
              <span class="selo"><span class="t1">Parado</span><span class="t2">Medindo…</span><span class="t3">Calibrado</span></span>
            </div>
            <div class="leitura">
{_eixos()}
            </div>
          </div>'''


def controles(quem):
    """O miolo do bloco `[data-bloco="controles"]`: os cartões, ou a frase.

    LISTA VAZIA É UMA RESPOSTA, não a ausência de uma. Com zero controles esta
    função devolve :data:`SEM_CONTROLE` — nunca um cartão com travessão, que
    seria a tela afirmando um controle que não está aqui (o defeito que esta
    casa já nomeou sete vezes).
    """
    if not quem:
        return f'          <p class="vazio">{SEM_CONTROLE}</p>'
    return "\n".join(controle(c) for c in quem)


def _deslizante(gesto, rotulo, faixa, campo, unidade=""):
    """Uma linha de deslizante da mira: o rótulo, o trilho e o número.

    DOIS ENDEREÇOS, porque um elemento aceita UM alvo: o trilho recebe o
    `valor` (a posição do polegar) e o número recebe o texto. O número nasce no
    valor de nascença do esquema — é o que um perfil novo tem, e não uma
    leitura inventada: ninguém mediu nada para ele existir.
    """
    minimo, maximo, nasce = faixa
    un = f' <span class="un">{unidade}</span>' if unidade else ""
    return (f'              <label class="desl"><span class="r">{rotulo}</span>'
            f'<input class="trilho" type="range" min="{minimo}" max="{maximo}"'
            f' step="1" value="{nasce}" data-gesto="{gesto}"'
            f' data-campo="{campo}" data-hef-alvo="valor" aria-label="{rotulo}">'
            f'<span class="n"><span data-campo="{campo}-num">{nasce}</span>{un}'
            f'</span></label>')


def _segurar():
    """A linha do «Só enquanto eu segurar»: o rótulo e a lista, nascendo «Sempre».

    A lista é um `<select>` de verdade, e o endereço é o alvo `valor`: o
    produto escreve nela o botão que a peça usa (`sempre` quando não há), e a
    troca dela chega ao gesto pela porta do `change`.
    """
    opcoes = "".join(
        f'<option value="{v}"{" selected" if v == SEMPRE else ""}>{r}</option>'
        for v, r in _opcoes_do_segurar())
    return (f'              <label class="desl"><span class="r">{ROTULO_SEGURAR}</span>'
            f'<select class="lista" data-gesto="mira-segurar" data-campo="mira-segurar"'
            f' data-hef-alvo="valor" aria-label="{ROTULO_SEGURAR}">{opcoes}</select>'
            f'</label>')


def _inverter():
    """A linha do «Inverter»: o rótulo e os dois botões, cada lado por si.

    Os botões são interruptores na cara dos chips de sensor da aba Controles
    (o verde aceso, o `off` apagado), e NASCEM APAGADOS. O alvo é `classe`, na
    língua do `_selo_do_sensor`: `off` quando o produto disser `DESLIGADO`.
    O nome acessível diz o ato inteiro, porque o rótulo do botão sozinho
    («Cima e baixo») não diz que inverte.
    """
    botoes = "".join(
        f'<button class="sw off" data-gesto="mira-inverter" data-inverter="{qual}"'
        f' data-campo="mira-inverter-{qual}" data-hef-alvo="classe"'
        f' data-hef-classe="off" data-hef-quando="DESLIGADO"'
        f' aria-label="{ROTULO_INVERTER} {rotulo.lower()}">'
        f'<span class="p"></span>{rotulo}</button>'
        for qual, rotulo, _ in INVERTER)
    return (f'              <div class="desl"><span class="r">{ROTULO_INVERTER}</span>'
            f'<span class="inverter">{botoes}</span></div>')


def mira(c):
    """A coluna da mira de UM controle — os dois deslizantes, o «Só enquanto eu
    segurar» e o «Inverter» dele.

    PÚBLICA pelo mesmo motivo do `controle()`: o `pacotes/a11_calibrar_sensores`
    a remonta quando a página publicada tiver o bloco. O `data-controle` é o do
    cartão de cima, e é ele que leva o clique ao controle certo.
    """
    jogador = c.get("jogador") or SEM_LEITURA
    return (f'          <div class="mira" data-controle="{c.get("pref") or ""}">\n'
            f'            <span class="quem">Player {jogador}</span>\n'
            f'{_deslizante("mira-sensibilidade", ROTULO_SENSIBILIDADE, SENSIBILIDADE, "mira-sensibilidade")}\n'
            f'{_deslizante("mira-tremor", ROTULO_TREMOR, TREMOR, "mira-tremor", UNIDADE_DO_TREMOR)}\n'
            f'{_segurar()}\n'
            f'{_inverter()}\n'
            f'          </div>')


def miras(quem):
    """O miolo do bloco `[data-bloco="miras"]`: o título e uma coluna por controle.

    SEM CONTROLE, NADA — nem o título. A frase de quem falta já está no bloco
    dos cartões, logo acima, e dizê-la duas vezes seria a tela narrando. O
    vazio é VAZIO DE VERDADE (sem quebra de linha), porque é o `:empty` da
    folha que some com a moldura do bloco.
    """
    if not quem:
        return ""
    colunas = "\n".join(mira(c) for c in quem)
    return (f'\n      <div class="mira-topo"><b>{ROTULO_DA_MIRA}</b>'
            f' <span class="d">{DE_ONDE_VEM_A_MIRA}</span></div>\n'
            f'      <div class="miras">\n{colunas}\n      </div>\n    ')


def documento(quem):
    """A página inteira, com os cartões de ``quem``, pronta para gravar.

    PÚBLICA para a régua do tamanho medir a página com 1, 2 e 4 controles — a
    MATRIZ dela — sem gravar arquivo; o `main()` grava a da bancada do desenho.
    """
    # O PLURAL SAIU DA FRASE — 11/09/2026, aprovado por ela. A linha dizia
    # «dos dois controles» e caía em «dos 1 controles» com um controle só na
    # bancada: a contagem era do desenho, não de quem lê. «todos os controles
    # conectados» é verdade com um, com dois e com quatro, e não tem número
    # a errar. O número voltou à tela no RODAPÉ, onde ele é dado e não frase —
    # e lá a concordância tem dono (`contagem()`).
    html = f'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Hefesto — calibrar sensores de movimento</title>
<style>{CSS}{moldura()}</style>
</head>
<body>

<div class="cx">
  <div class="topo">
    <!-- O VOLTAR VOLTA PARA DE ONDE VEIO, com a Controles como fallback de quem
         abre o arquivo com duplo clique — que é como ela abre. É a mesma cura do
         `mapa.py`, e pelo mesmo motivo: uma página avulsa não sabe quem a chamou. -->
    <a class="voltar" href="02-controles.html"
       onclick="if (document.referrer) {{ history.back(); return false }}"
       title="Volta para a aba anterior.">← Voltar</a>
    <h1><span class="p">Calibrar sensores de movimento</span></h1>
    <div class="sub">O giroscópio e o acelerômetro de todos os controles conectados, de uma vez.</div>
  </div>

  <div class="corpo">

    <!-- OS TRÊS ESTADOS, CLICÁVEIS. Os rádios vêm antes de tudo o que reage a
         eles — o `~` só enxerga irmão posterior. -->
    <input class="et" type="radio" name="etapa" id="e-parado" checked>
    <input class="et" type="radio" name="etapa" id="e-medindo">
    <input class="et" type="radio" name="etapa" id="e-pronto">

    <div class="passos">
      <label class="passo" for="e-parado">
        <span class="n">1</span>
        <span><b>Deixe os controles parados</b>
          <span class="d">Numa superfície plana, com os analógicos livres. Não precisa desconectar nada.</span></span>
      </label>
      <label class="passo" for="e-medindo">
        <span class="n">2</span>
        <span><b>Não toque neles</b>
          <span class="d">São {SEGUNDOS} segundos de leitura. Encostar no controle recomeça a conta dele.</span></span>
      </label>
      <label class="passo" for="e-pronto">
        <span class="n">3</span>
        <span><b>Pronto</b>
          <span class="d">O zero de cada eixo fica gravado no controle e vale para todo jogo.</span></span>
      </label>
    </div>

    <!-- OS CONTROLES DE QUEM ABRE, e o bloco inteiro tem endereço: o tique o
         remonta a cada mudança de bancada, pelo MESMO gerador que escreveu
         isto aqui. Ver `pacotes/a11_calibrar_sensores.py`. -->
    <div class="controles" data-bloco="controles">
{controles(quem)}
    </div>

    <!-- A MIRA VIRTUAL, uma coluna por controle embaixo do cartão dele — ver o
         bloco `A MIRA VIRTUAL` no topo deste arquivo. O bloco é outro de
         propósito: o dos cartões o produto remonta a cada tique. -->
    <div class="mira-cx" data-bloco="miras">{miras(quem)}</div>

    <div class="rodape">
      <button class="btn fazer"><span class="t1">Começar</span><span class="t2">Medindo…</span><span class="t3">Calibrar de novo</span></button>
      <div class="barra"><i></i></div>
      <!-- O ALVO É `html` E NÃO O TEXTO, e a razão é medida NESTA tela: com
           zero controles a `contagem()` devolve vazio, e o alvo padrão escreve
           o TRAVESSÃO no lugar de um valor vazio — um `—` solto ao lado do
           botão, anunciando a ausência de uma frase que a página tirou de
           propósito. É o mesmo defeito que a aba Lançadores mediu em 11/09, e
           a casa já decidiu a cura: o alvo `html` trata vazio como vazio. -->
      <span class="quantos" data-campo="quantos" data-hef-alvo="html">{contagem(len(quem))}</span>
      <a class="btn" href="02-controles.html">Fechar</a>
    </div>

    <!-- O QUE ELA PRECISA SABER, E SÓ ISSO. A calibração não muda ajuste nenhum
         do perfil: ela zera a leitura de repouso do aparelho. Escrever mais que
         isto seria a mesma prosa que ela mandou cortar dos tooltips. -->
    <div class="aviso">
      A calibração <b>não muda os seus ajustes</b> — ela só ensina ao controle qual é o zero dele.
      Se o cursor anda sozinho com o controle parado, é isto que resolve.
    </div>

  </div>
</div>

</body>
</html>
'''
    return "\n".join(l.rstrip() for l in html.split("\n"))


def main():
    # O ARQUIVO NASCE COM A BANCADA DO DESENHO, e o produto a substitui no
    # primeiro tique — é o mesmo contrato das dez abas. O que mudou em 11/09 é
    # que agora HÁ quem substitua: `pacotes/a11_calibrar_sensores.py`.
    quem = monta.CONECTADOS
    onde.pagina("calibrar-sensores.html").write_text(documento(quem))
    # O «s» ENTRE PARÊNTESES SAIU DAQUI TAMBÉM — 11/09/2026. Não é texto de
    # tela, mas é a mesma concordância, e a régua que a cobra lê este arquivo
    # inteiro — inclusive esta linha, que por isso não o escreve.
    print(f"calibrar-sensores.html: {contagem(len(quem))} no desenho · "
          f"3 estados clicáveis")


if __name__ == "__main__":
    main()
