#!/usr/bin/env python3
"""A janela Calibrar giroscópio — `mockup/calibrar-sensores.html`.

PEDIDO, 31/08/2026, e é o segundo botão que o usuário mandou nascer na Controles:

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
conectados — hoje dois, pela decisão de produto do mesmo dia de deixar dois fora.

POR QUE O PROCEDIMENTO DA STEAM: é o que o usuário nomeou, e ele é o mínimo honesto —
o giroscópio zera medindo o repouso, então a única coisa que a pessoa precisa
fazer é **não mexer**. Toda instrução a mais é ruído.

A PALETA E O ESQUELETO SÃO OS DO `mapa.py`, copiados de propósito: as duas são
páginas que abrem POR FORA das dez abas, e uma segunda gramática de página
avulsa na mesma janela seria uma a mais.

**A CAIXA É A DA JANELA DAS ABAS** desde 23/09/2026
(A-CALIBRACAO-TEM-O-TAMANHO-DO-PROGRAMA-01), lida do `topo.html`, porque o usuário
pediu a Calibrar do tamanho do programa. Em 24/09/2026 o usuário decidiu que o «Mapa
do controle» e o mapa das portas seguem a mesma caixa, e as três avulsas
passaram a pedi-la ao mesmo dono, `caixa_da_janela.py`
(AS-PAGINAS-AVULSAS-TEM-A-CAIXA-DA-JANELA-01).

OS CONTROLES SÃO DE QUEM ABRE A PÁGINA — 11/09/2026, F3-CALIBRAR
-----------------------------------------------------------------

Até hoje esta página desenhava `monta.CONECTADOS` (o desenho, sempre dois) com
números de uma constante deste arquivo (`REPOUSO`, seis por controle). Medido no
daemon do usuário em 11/09, com os dois DualSense na bancada:

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
import onde
import monta
import caixa_da_janela

from hefesto_dualsense4unix.core.roteador_de_movimento import (
    SEGUNDOS_DO_ZERO,
)

SEGUNDOS = f"{SEGUNDOS_DO_ZERO:g}"

ZERO_PARADO = "parado"
ZERO_MEDINDO = "medindo"
ZERO_PRONTO = "pronto"
ZERO_MEXEU = "mexeu"
ESTADOS_DO_ZERO = (ZERO_PARADO, ZERO_MEDINDO, ZERO_PRONTO, ZERO_MEXEU)

SEM_LEITURA = "—"

FAMILIAS = (("giro", "Giroscópio"), ("accel", "Acelerômetro"))

SEM_CONTROLE = ("Nenhum controle conectado. Ligue um pelo cabo ou pelo rádio "
                "e ele aparece aqui.")

TITULO = "Calibrar giroscópio"
ROTULO_SENSIBILIDADE = "O quanto um gesto anda"
ROTULO_TREMOR = "Ignorar tremor até"
UNIDADE_DO_TREMOR = "graus/s"
SENSIBILIDADE = (1, 12, 6)
TREMOR = (1, 60, 3)

AJUDA_DA_PAGINA = "Mede o zero de cada controle parado"
PASSOS = (
    ("e-parado", "Deixe parados", "Numa superfície plana, sem tocar"),
    ("e-medindo", f"Medindo {SEGUNDOS} s", "Encostar recomeça a conta"),
    ("e-pronto", "Pronto", "O zero fica guardado e vale em todo jogo"),
)
LUGARES = 4

from hefesto_dualsense4unix.core.remapeamento_de_botao import (  # noqa: E402
    REMAPEAVEIS,
)

ROTULO_SEGURAR = "Só enquanto eu segurar"
ROTULO_SEMPRE = "Sempre"
SEMPRE = "sempre"
ROTULO_MESMO_PARADO = "Mesmo parado"
MESMO_PARADO = "mesmo_parado"
ROTULO_INVERTER = "Inverter"
INVERTER = (
    ("lado", "Esquerda e direita", "inverter_horizontal"),
    ("cima-baixo", "Cima e baixo", "inverter_vertical"),
)

_PECA_DO_BOTAO = {"l3": "stick_l", "r3": "stick_r", "create": "share"}


def _pecas() -> dict:
    """O mapa das peças (`docs/data/pecas-do-dualsense.csv`), por id."""
    import csv

    linhas = [x for x in (monta.DADOS_DO_REPO / "pecas-do-dualsense.csv")
              .read_text(encoding="utf-8").splitlines() if x and not x.startswith("#")]
    return {p["id"]: p for p in csv.DictReader(linhas)}


def nome_do_botao(botao, pecas=None):
    """O nome curto do botão na tela, LIDO do mapa das peças."""
    p = (pecas or _pecas())[_PECA_DO_BOTAO.get(botao, botao)]
    if len(p["nome"]) <= 8:
        return p["nome"]
    for a in p["apelidos"].split("|"):
        if a.isalnum() and len(a) <= 3:
            return a
    return p["nome"]


def _opcoes_do_segurar():
    """`(valor, rótulo)` de cada opção da lista, «Sempre» e «Mesmo parado» primeiro."""
    pecas = _pecas()
    return [(SEMPRE, ROTULO_SEMPRE), (MESMO_PARADO, ROTULO_MESMO_PARADO)] + [
        (b, nome_do_botao(b, pecas)) for b in REMAPEAVEIS]


def plural(quantos: int, um: str, muitos: str) -> str:
    """Uma das duas palavras, pela contagem. ``0`` usa o plural, como em português.

    POR QUE ELE EXISTE, e o defeito é medido: esta página escrevia
    ``dos {n} controles`` e caía em *"dos 1 controles"* com um controle só
    (em `calibrar.py`, antes de 11/09). **O plural dito com um «s» entre
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
    """`Nenhum controle conectado` · `1 controle conectado` · `4 controles conectados`."""
    if quantos <= 0:
        return ""
    return f"{quantos} {plural(quantos, 'controle conectado', 'controles conectados')}"


CSS = """
  :root{
    --app-bg:#21222c; --panel:#282a36; --elevated:#2b2d3a;
    --fundo-da-pagina:#11121a;
    --border-sutil:#343746; --border-forte:#44475a; --linha:#53576f;
    --fg:#f8f8f2; --texto-suave:#c8ccda; --texto-mudo:#9a9eb8; --comment:#8896c4;
    --cyan:#8be9fd; --green:#50fa7b; --orange:#ffb86c;
    --pink:#ff79c6; --purple:#bd93f9; --red:#ff5555;
    --sel-bg:rgba(189,147,249,.16);
    --f:'Space Grotesk',system-ui,sans-serif;
    --m:'JetBrains Mono',ui-monospace,monospace;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--fundo-da-pagina);color:var(--fg);font-family:var(--f);
       display:flex;flex-direction:column;align-items:center;gap:16px}
  .mono{font-family:var(--m)}
  .cx{background:var(--app-bg);border-radius:11px;
      border:1px solid var(--border-sutil);overflow:hidden;
      display:flex;flex-direction:column}
  .topo{padding:15px 20px;border-bottom:1px solid var(--border-sutil);
        position:relative;padding-left:132px;flex:0 0 auto}
  h1{font-size:18px;font-weight:700;display:flex;align-items:center;gap:9px}
  h1 .p{color:var(--pink)}
  .perfil-ativo{position:absolute;right:20px;top:17px;display:flex;align-items:center;gap:7px;
                padding:5px 11px;border-radius:7px;border:1px solid var(--linha);
                background:var(--panel)}
  .pa-rot{font-size:12.5px;color:var(--fg);white-space:nowrap}
  .pa-nome{font-size:12.5px;color:var(--pink);font-weight:600;white-space:nowrap;max-width:360px;
           overflow:hidden;text-overflow:ellipsis}
  .voltar{position:absolute;left:20px;top:17px;display:inline-flex;align-items:center;
          gap:6px;padding:5px 11px;border-radius:7px;text-decoration:none;
          border:1px solid var(--border-forte);background:var(--panel);
          color:var(--texto-suave);font-size:12px}
  .voltar:hover{border-color:var(--comment);color:var(--fg)}

  .corpo{padding:18px 20px 20px;display:flex;flex-direction:column;gap:14px;
         flex:1;min-height:0;overflow-y:auto}

  .et{position:absolute;width:0;height:0;opacity:0;pointer-events:none}

  .passos{display:flex;gap:9px}
  .passo{flex:1;display:flex;gap:9px;align-items:center;height:32px;
         padding:0 12px;border-radius:8px;border:1px solid var(--border-sutil);
         background:var(--panel);cursor:pointer}
  .passo .n{flex:0 0 20px;height:20px;border-radius:50%;display:flex;
            align-items:center;justify-content:center;font-family:var(--m);
            font-size:11px;border:1px solid var(--border-forte);color:var(--fg)}
  .passo b{font-size:12.5px;font-weight:600}
  #e-parado:checked  ~ .passos .passo:nth-child(1),
  #e-medindo:checked ~ .passos .passo:nth-child(2),
  #e-pronto:checked  ~ .passos .passo:nth-child(3){
    border-color:var(--purple);background:var(--sel-bg)}
  #e-parado:checked  ~ .passos .passo:nth-child(1) .n,
  #e-medindo:checked ~ .passos .passo:nth-child(2) .n,
  #e-pronto:checked  ~ .passos .passo:nth-child(3) .n{
    border-color:var(--purple);color:var(--fg)}

  .grade{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));column-gap:11px;
         grid-template-rows:auto minmax(0,1fr);flex:1 0 auto}
  .controles,.mira-cx{display:contents}
  .lugar{grid-row:span 2;border:1px dashed var(--border-forte);border-radius:9px;
         display:flex;align-items:center;justify-content:center;
         font-family:var(--m);font-size:22px;color:var(--border-forte)}
  .vazio{grid-column:1 / -1;padding:22px 14px;text-align:center;border-radius:9px;
         border:1px dashed var(--border-forte);background:var(--panel);
         color:var(--fg);font-size:13px;line-height:19px}
  .ctr{border:2px solid var(--plastico,var(--border-forte));border-bottom:0;
       border-radius:9px 9px 0 0;
       background:var(--panel);padding:11px 12px 10px;display:flex;
       flex-direction:column;gap:8px;min-width:0}
  .ctr-topo{display:flex;align-items:center;gap:9px;min-width:0}
  .ctr .nome{font-size:12.5px;color:var(--fg);line-height:15px;white-space:nowrap;
             overflow:hidden;text-overflow:ellipsis;flex:1 1 auto;min-width:0}
  .ctr .nome .l1{display:flex;align-items:center;gap:6px;min-width:0;margin-bottom:2px}
  .ctr .nome .l1 b{flex:0 1 auto;min-width:0}
  .ctr .nome b{color:var(--fg);font-weight:600;display:inline-flex;max-width:100%;
               vertical-align:top}
  .ctr .nome .quem-nome{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .ctr .nome .quem-num{white-space:pre}
  .ds-svg{width:60px;height:auto;flex:0 0 60px}
  .selo{margin-left:auto;flex:0 0 auto;font-size:11px;line-height:13px;padding:2px 8px;border-radius:6px;
        border:1px solid var(--border-forte);color:var(--fg);white-space:nowrap}
  #e-medindo:checked ~ .grade .selo:not([data-zero]),
  .selo[data-zero="medindo"]{border-color:var(--orange);color:var(--orange)}
  #e-pronto:checked  ~ .grade .selo:not([data-zero]),
  .selo[data-zero="pronto"]{border-color:var(--green);color:var(--green)}
  .selo[data-zero="mexeu"]{border-color:var(--fg);color:var(--fg)}
  .selo .t2,.selo .t3,.selo .t4{display:none}
  #e-medindo:checked ~ .grade .selo:not([data-zero]) .t1,
  #e-medindo:checked ~ .grade .selo:not([data-zero]) .t3,
  #e-pronto:checked  ~ .grade .selo:not([data-zero]) .t1,
  #e-pronto:checked  ~ .grade .selo:not([data-zero]) .t2,
  .selo[data-zero]:not([data-zero="parado"]) .t1{display:none}
  #e-medindo:checked ~ .grade .selo:not([data-zero]) .t2,
  #e-pronto:checked  ~ .grade .selo:not([data-zero]) .t3,
  .selo[data-zero="medindo"] .t2,
  .selo[data-zero="pronto"] .t3,
  .selo[data-zero="mexeu"] .t4{display:inline}

  .leitura{border-top:1px solid var(--border-sutil);padding-top:9px;
           display:flex;flex-direction:column;gap:8px}
  .lin{display:flex;align-items:center;gap:7px;font-family:var(--m);font-size:11px}
  .lin > .r{flex:0 0 82px;color:var(--fg)}
  .lin > .v{flex:0 0 52px;text-align:right;color:var(--texto-suave)}
  .lin > .g{flex:1;height:4px;border-radius:2px;background:var(--border-sutil);
            position:relative;overflow:hidden;color:var(--border-forte)}
  .lin > .g::after{content:"";position:absolute;top:0;bottom:0;left:50%;width:2px;
                   background:var(--comment);transform:translateX(-1px);z-index:1}
  .lin > .g > i{position:absolute;top:0;bottom:0;border-radius:2px;
                background:currentColor}
  .lin > .g > i.neg{right:50%}
  .lin > .g > i.pos{left:50%}
  #e-pronto:checked ~ .grade .lin > .g::after{background:var(--green)}

  .barra{height:6px;border-radius:3px;background:var(--border-sutil);overflow:hidden}
  .barra > i{display:block;height:100%;width:0;background:var(--purple)}
  #e-medindo:checked ~ .rodape .barra > i{width:58%}
  #e-pronto:checked  ~ .rodape .barra > i{width:100%;background:var(--green)}

  .rodape{display:flex;align-items:center;gap:13px;margin-top:auto}
  .rodape .acoes{display:flex;gap:9px}
  .rodape .barra{flex:1}
  .quantos{font-size:12px;color:var(--fg);white-space:nowrap}
  .btn{height:34px;width:150px;padding:0 15px;border-radius:8px;font-size:13px;cursor:pointer;
       border:1px solid var(--border-forte);background:var(--panel);color:var(--texto-suave);
       display:inline-flex;align-items:center;justify-content:center;text-decoration:none;
       white-space:nowrap;font-family:inherit}
  .btn:hover{border-color:var(--comment);color:var(--fg)}
  .btn.fazer{border-color:var(--green);background:var(--green);color:var(--app-bg);
             font-weight:600}
  .btn.fazer:hover{color:var(--app-bg);filter:brightness(1.08)}
  .btn .t2,.btn .t3{display:none}
  #e-medindo:checked ~ .rodape .btn.fazer .t1,
  #e-medindo:checked ~ .rodape .btn.fazer .t3,
  #e-pronto:checked  ~ .rodape .btn.fazer .t1,
  #e-pronto:checked  ~ .rodape .btn.fazer .t2{display:none}
  #e-medindo:checked ~ .rodape .btn.fazer .t2,
  #e-pronto:checked  ~ .rodape .btn.fazer .t3{display:inline}
  #e-medindo:checked ~ .rodape .btn.fazer{border-color:var(--orange);background:var(--orange)}

  .mira{min-width:0;display:flex;flex-direction:column;gap:13px;
        padding:9px 12px 12px;border-radius:0 0 9px 9px;
        border:2px solid var(--plastico,var(--border-forte));border-top:0;
        background:var(--panel);position:relative}
  .mira::before{content:"";position:absolute;left:12px;right:12px;top:0;
                border-top:1px solid var(--border-sutil)}
  .desl{display:grid;grid-template-columns:1fr auto;align-items:center;
        column-gap:8px;row-gap:3px;font-size:12px}
  .desl .r{color:var(--texto-suave);white-space:nowrap;overflow:hidden;
           text-overflow:ellipsis;min-width:0}
  .desl .n{grid-row:1;grid-column:2;font-family:var(--m);font-size:11px;
           color:var(--fg);white-space:nowrap}
  .desl .un{color:var(--fg)}
  .desl .trilho{grid-row:2;grid-column:1 / -1;width:100%;margin:0;
                accent-color:var(--purple)}
  .desl .lista,.desl .inverter{grid-row:2;grid-column:1 / -1}
  .desl .lista{width:100%;height:24px;padding:0 8px;border-radius:6px;
               border:1px solid var(--border-forte);background:var(--app-bg);
               color:var(--fg);font-family:inherit;font-size:12px;cursor:pointer}
  .desl .lista:hover{border-color:var(--comment)}
  .desl .lista option{background:var(--panel);color:var(--fg)}
  .inverter{display:grid;grid-template-columns:1fr;gap:6px}
  .inverter .sw{justify-content:center}
  .inverter .sw{height:24px;border-radius:6px;font-size:10.5px;font-family:inherit;
    cursor:pointer;border:1px solid var(--green);background:rgba(80,250,123,.09);
    color:var(--green);display:inline-flex;align-items:center;gap:6px;padding:0 10px;
    white-space:nowrap}
  .inverter .sw .p{width:6px;height:6px;border-radius:50%;background:var(--green);
    box-shadow:0 0 6px var(--green)}
  .inverter .sw.off{border-color:var(--border-forte);background:var(--app-bg);
    color:var(--fg)}
  .inverter .sw.off .p{background:var(--border-forte);box-shadow:none}
  [data-gesto]{min-height:24px}
"""


moldura = caixa_da_janela.moldura


def _svg(c):
    """O desenho do controle, na cor do plástico dele, sem as lâmpadas."""
    cor = str(c.get("cor") or "")
    if cor and not monta.o_desenho_conhece(cor):
        cor = ""
    return re.sub(r"<\?xml[^>]*\?>\s*", "",
                  monta.svg(f'cal-{c.get("pref") or "px"}', cor, lampadas=False))


def _eixos():
    """As seis linhas de leitura de um controle: três de giro, três de aceleração."""
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
    """A cor do plástico daquele controle, ou a borda neutra do tema."""
    cor = str(c.get("cor") or "")
    if cor and monta.o_desenho_conhece(cor):
        return monta.cor_da_zona(cor)
    return "var(--border-forte)"


def _quem(c):
    """Quem joga com o controle: o que o pacote trouxe (`<nome> • P<n>`), ou o «P<n>» da cena."""
    if c.get("quem"):
        return c["quem"]
    if c.get("jogador"):
        return f"P{monta.numero_do_jogador(c['jogador'])}"
    return SEM_LEITURA


def controle(c):
    """O cartão de UM controle — o desenho, a identidade e as seis linhas vazias.

    A PRIMEIRA LINHA DIZ QUEM JOGA (07/10/2026, a resposta [45]): o nome que o usuário deu ao controle e o
    número, ou só o número sem nome. A Calibrar não tem lâmpadas, por isso leva os dois. «Player N»
    e o «Sony •» saíram para a gramática da casa (`P<n>`).
    """
    nome = c.get("nome") or SEM_LEITURA
    via = c.get("via") or SEM_LEITURA
    return f'''          <div class="ctr" style="--plastico:{_plastico(c)}"
               data-controle="{c.get("pref") or ""}">
            <div class="ctr-topo">
              {_svg(c)}
              <span class="nome"><span class="l1"><b data-campo="quem-joga" data-hef-alvo="html">{_quem(c)}</b><span class="selo" data-campo="zero-estado" data-hef-alvo="atributo" data-hef-atributo="data-zero"><span class="t1">Parado</span><span class="t2">Medindo…</span><span class="t3">Calibrado</span><span class="t4">Mexeu</span></span></span>{nome} <span class="pt">•</span> {via}</span>
            </div>
            <div class="leitura">
{_eixos()}
            </div>
          </div>'''


def lugares_vazios(quem):
    """Os números dos lugares sem controle, até o P4, em ordem."""
    tomados = {_numero(c) for c in quem}
    livres = [n for n in range(1, LUGARES + 1) if n not in tomados]
    return livres[:max(0, LUGARES - len(quem))]


def lugar(n):
    """O lugar vazio de um jogador: o número, e nada mais, como nas abas."""
    return f'          <div class="lugar" aria-label="Lugar vazio do P{n}">P{n}</div>'


def _numero(c):
    """O número do jogador, ou `None` quando a bancada não o leu (`mesa_viva` o dá inteiro)."""
    n = c.get("jogador")
    return n if isinstance(n, int) else None


def controles(quem):
    """O miolo do bloco `[data-bloco="controles"]`: os cartões e os lugares vazios, ou a frase.

    O LUGAR VAZIO ENTRA NA POSIÇÃO DO NÚMERO DELE. Com o P2 fora e o P1 e o P3
    conectados, a fila é P1, P2 vazio, P3, P4 vazio, como nas abas. Os cartões
    não mudam de ordem (a das miras é a mesma, e a grade põe cada mira embaixo do
    cartão do mesmo controle); só os lugares se intercalam.
    """
    if not quem:
        return f'          <p class="vazio">{SEM_CONTROLE}</p>'
    livres = lugares_vazios(quem)
    partes = []
    for c in quem:
        n = _numero(c)
        while livres and n is not None and livres[0] < n:
            partes.append(lugar(livres.pop(0)))
        partes.append(controle(c))
    return "\n".join(partes + [lugar(n) for n in livres])


def _deslizante(gesto, rotulo, faixa, campo, unidade=""):
    """Uma linha de deslizante da mira: o rótulo, o trilho e o número."""
    minimo, maximo, nasce = faixa
    un = f' <span class="un">{unidade}</span>' if unidade else ""
    return (f'              <label class="desl"><span class="r">{rotulo}</span>'
            f'<input class="trilho" type="range" min="{minimo}" max="{maximo}"'
            f' step="1" value="{nasce}" data-gesto="{gesto}"'
            f' data-campo="{campo}" data-hef-alvo="valor" aria-label="{rotulo}">'
            f'<span class="n"><span data-campo="{campo}-num">{nasce}</span>{un}'
            f'</span></label>')


def _segurar():
    """A linha do «Só enquanto eu segurar»: o rótulo e a lista, nascendo «Sempre»."""
    opcoes = "".join(
        f'<option value="{v}"{" selected" if v == SEMPRE else ""}>{r}</option>'
        for v, r in _opcoes_do_segurar())
    return (f'              <label class="desl"><span class="r">{ROTULO_SEGURAR}</span>'
            f'<select class="lista" data-gesto="mira-segurar" data-campo="mira-segurar"'
            f' data-hef-alvo="valor" aria-label="{ROTULO_SEGURAR}">{opcoes}</select>'
            f'</label>')


def _inverter():
    """A linha do «Inverter»: o rótulo e os dois botões, cada lado por si."""
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
    """A coluna da mira de UM controle — os dois deslizantes, o «Só enquanto eu"""
    return (f'          <div class="mira" style="--plastico:{_plastico(c)}"'
            f' data-controle="{c.get("pref") or ""}">\n'
            f'            <span class="quem" data-campo="quem-joga" data-hef-alvo="html">{_quem(c)}</span>\n'
            f'{_deslizante("mira-sensibilidade", ROTULO_SENSIBILIDADE, SENSIBILIDADE, "mira-sensibilidade")}\n'
            f'{_deslizante("mira-tremor", ROTULO_TREMOR, TREMOR, "mira-tremor", UNIDADE_DO_TREMOR)}\n'
            f'{_segurar()}\n'
            f'{_inverter()}\n'
            f'          </div>')


def miras(quem):
    """O miolo do bloco `[data-bloco="miras"]`: o título e uma coluna por controle."""
    if not quem:
        return ""
    colunas = "\n".join(mira(c) for c in quem)
    return f'\n{colunas}\n    '


def _passos():
    """A fita dos três passos: o número e o nome, com a frase curta em `data-dica`."""
    return "\n".join(
        f'      <label class="passo" for="{rid}" data-dica="{dica}">'
        f'<span class="n">{n}</span><b>{rot}</b></label>'
        for n, (rid, rot, dica) in enumerate(PASSOS, 1))


ABA_DO_CALIBRAR = "01-jogar.html"


def documento(quem):
    """A página inteira, com os cartões de ``quem``, pronta para gravar."""
    html = f'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Hefesto — calibrar giroscópio</title>
<style>{caixa_da_janela.letra_da_casa()}{CSS}{moldura()}</style>
</head>
<body>

<div class="cx">
  <div class="topo">
    {caixa_da_janela.voltar(ABA_DO_CALIBRAR)}
    <h1><span class="p" data-dica="{AJUDA_DA_PAGINA}">{TITULO}</span></h1>
    <div class="perfil-ativo"><span class="pa-rot">Perfil ativo</span><span class="pa-nome" data-campo="perfil">—</span></div>
  </div>

  <div class="corpo">

    <input class="et" type="radio" name="etapa" id="e-parado" data-campo="passo-parado" data-hef-alvo="marcado" checked>
    <input class="et" type="radio" name="etapa" id="e-medindo" data-campo="passo-medindo" data-hef-alvo="marcado">
    <input class="et" type="radio" name="etapa" id="e-pronto" data-campo="passo-pronto" data-hef-alvo="marcado">

    <div class="passos">
{_passos()}
    </div>

    <div class="grade">
    <div class="controles" data-bloco="controles">
{controles(quem)}
    </div>

    <div class="mira-cx" data-bloco="miras">{miras(quem)}</div>
    </div>

    <div class="rodape">
      <div class="barra"><i></i></div>
      <span class="quantos" data-campo="quantos" data-hef-alvo="html">{contagem(len(quem))}</span>
      <span class="acoes">
        <button class="btn fazer" data-gesto="calibrar-comecar"><span class="t1">Começar</span><span class="t2">Medindo…</span><span class="t3">Calibrar de novo</span></button>
        <a class="btn" href="{ABA_DO_CALIBRAR}">Fechar</a>
      </span>
    </div>

  </div>
</div>

</body>
</html>
'''
    return monta.com_a_base("\n".join(l.rstrip() for l in html.split("\n")))


def main():
    if ABA_DO_CALIBRAR.removesuffix(".html") not in {a for _, a in monta.ABAS}:
        raise SystemExit(f"ERRO em calibrar-sensores: o «Fechar» leva a {ABA_DO_CALIBRAR}, "
                         "que não está na tira de abas.")
    quem = monta.CONECTADOS
    onde.pagina("calibrar-sensores.html").write_text(documento(quem))
    print(f"calibrar-sensores.html: {contagem(len(quem))} no desenho · "
          f"3 estados clicáveis")


if __name__ == "__main__":
    main()
