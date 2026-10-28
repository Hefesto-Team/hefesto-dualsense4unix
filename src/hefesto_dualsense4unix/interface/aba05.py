"""Aba 05 · Vibração — a mesa de QUATRO controles."""
import csv
import math
import pathlib
import re
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
import onde
import monta as monta_
from monta import CONECTADOS, DADOS_DO_REPO

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from monta import (
    MESA, cor_da_zona, glifo, monta, svg, trava_do_nativo,
)

from hefesto_dualsense4unix.daemon.subsystems import padroes_de_vibracao as padroes
from hefesto_dualsense4unix.daemon.subsystems.rumble import (
    RUMBLE_POLICY_MULT,
)
from hefesto_dualsense4unix.interface.pacotes.a05_vibracao import (
    CAMPO_DA_DICA_DA_IMERSAO,
    CAMPO_DA_DICA_DO_HAPTICO,
    CAMPO_DO_EFEITO_HAPTICO,
    CAMPO_DO_EFEITO_IMERSAO,
    GESTO_DO_EFEITO_HAPTICO,
    GESTO_DO_EFEITO_IMERSAO,
    GESTO_DO_MODO,
)
from hefesto_dualsense4unix.interface.mapa import glifo_do_controle

from hefesto_dualsense4unix.profiles import formas_de_haptica as formas
from hefesto_dualsense4unix.profiles.schema import (
    MOTOR_PCT_MAX,
    MOTOR_PCT_PADRAO,
    RUMBLE_CUSTOM_MULT_MAX,
)

from hefesto_dualsense4unix.app.telas.vibracao import (
    DICA_DO_TETO_DA_MESA,
    DICA_DOS_VALORES_QUE_PASSAM,
    degraus_da_forca,
    html_do_estado,
    textos_do_estado,
)

CENA_DO_ESTADO = {"rumble_policy": "economia",
                  "rumble_ff": {"plays": 0, "nao_nulos": 0, "vpads": 1}}

_LINHAS = [
    l for l in csv.DictReader(
        x for x in (DADOS_DO_REPO / "pecas-do-dualsense.csv").read_text().splitlines()
         if not x.startswith("#"))
    if l["regiao"] == "vibracao" and l["no_svg"] != "falta"
]
if len(_LINHAS) != 2:
    raise SystemExit(f"ERRO: o mapa tem {len(_LINHAS)} peça(s) de vibração, e a aba "
                     f"desenha duas. Confira docs/data/pecas-do-dualsense.csv")

MOTORES = [
    {
        "id": l["no_svg"],
        "glifo": l["glifo"],
        "rot": f'{l["nome"].split()[0]} {l["nome"].split()[-1]}',
        "nome": l["nome"],
        "nota": l["nota"],
        "apelido": l["apelidos"],
    }
    for l in sorted(_LINHAS, key=lambda l: float(l["x1"]))
]
ESQ, DIR = MOTORES

FORCA = [("Economia", "economia"), ("Padrão", "balanceado"),
         ("Máximo", "max")]

if tuple(chave for _, chave in FORCA) != degraus_da_forca():
    raise SystemExit(
        f"ERRO: os degraus desta aba são {[c for _, c in FORCA]} e o "
        f"produto tem {list(degraus_da_forca())} (app/telas/vibracao."
        "degraus_da_forca). O `data-forca` é o endereço por onde a pintura acha "
        "o botão — divergir aqui faz a tela acender o degrau errado, em silêncio.")

TETO = round(RUMBLE_CUSTOM_MULT_MAX * 100)

PASSO = math.gcd(*(round(m * 100) for m in RUMBLE_POLICY_MULT.values()), TETO)

TETO_DA_FORCA = TETO
PASSO_DA_FORCA = 5

TETO_DO_MOTOR = MOTOR_PCT_MAX

TETO_DA_HAPTICA = MOTOR_PCT_MAX

PASSO_DO_MOTOR = 1

BARRA_DO_MOTOR_PADRAO = MOTOR_PCT_PADRAO

SEM_A_FAIXA_DE_ESTADO = True

ESTADO = {
    "p1": {"pct": 120,
           "esq": (True, 50),   "dir": (True, 100),
           "hap": (True, TETO_DA_HAPTICA)},
    "p2": {"pct": 70,
           "esq": (False, 0),   "dir": (True, 100),
           "hap": (True, 80)},
    "p3": {"pct": 30,
           "esq": (True, 100),  "dir": (True, 100),
           "hap": (True, TETO_DA_HAPTICA)},
    "p4": {"pct": 100,
           "esq": (True, 100),  "dir": (False, 0),
           "hap": (False, 0)},
}

GOVERNA = ".vib .ctrl > :is(.forca,.motor)"
DICA_DO_AUTOMATICO = "O jogo decide a força; o estilo do perfil ajusta"

GLIFO_DO_CONTROLE = glifo_do_controle()
DICA_DA_FORCA = ("Abaixo de 100% a vibração fica mais fraca; acima, a fraca é reforçada, "
               "até o máximo do motor")
BOTAO_DA_FORCA = ('<span class="lado glifo-forca on" role="img" aria-label="O controle inteiro" '
                  'data-dica="Os dois motores e a háptica: tudo o que vibra">' + GLIFO_DO_CONTROLE + '</span>')

CSS = """  .vib{
    display:grid;
    grid-template-columns:calc(var(--larg-rot) + var(--gap-col)) repeat(4,minmax(0,1fr));
    column-gap:0;margin-right:-14px;
    flex:1 1 auto;min-height:0;grid-template-rows:minmax(0,1fr);
    --r-des:72px;--r-nome:30px;--r-forca:36px;--r-barra:36px;--r-motor:36px;
    --r-efeito:38px;--r-acoes:34px;
    --r-ar:2px;--r-passo:calc(var(--r-ar) * 2);
  }
  .miolo > .quadro.vib-quadro{flex:1 1 auto;min-height:0;display:flex;flex-direction:column}
  .miolo > .quadro.vib-quadro > .quadro-corpo{flex:1 1 auto;min-height:0;display:flex;flex-direction:column}
  .vib > .rotulos{padding-right:var(--gap-col)}
  .vib > div{
    display:grid;row-gap:var(--r-passo);
    grid-template-rows:minmax(var(--r-des),3fr) var(--r-nome) minmax(var(--r-forca),1fr)
                       minmax(var(--r-motor),1fr) minmax(var(--r-efeito),1fr)
                       minmax(var(--r-motor),1fr) minmax(var(--r-motor),1fr)
                       minmax(var(--r-efeito),1fr) minmax(var(--r-acoes),1fr);
  }
  .efeito-lista{display:flex;flex-direction:column;justify-content:center;gap:0;min-width:0}
  .vib-efeito{flex:0 0 26px;width:100%;min-width:0;height:26px;padding:0 9px;border-radius:7px;
    border:1px solid var(--border-forte);background:var(--app-bg,var(--panel));color:var(--fg);
    font:500 12.5px 'Space Grotesk',system-ui,sans-serif;cursor:pointer}
  .vib-efeito:hover{border-color:var(--comment)}
  .vib-efeito-dica{display:contents}
  .vib .acoes-col{align-content:center}
  .vib .acoes-col{align-items:center}
  .quadro-topo .modo-auto{margin-left:auto}
  .vib .forca > .motor{position:relative}
  .vib .forca{display:flex;flex-direction:column;justify-content:center;gap:7px}
  .vib .forca > .motor{height:var(--r-barra);flex:none}
  .vib .forca .trilho.arrasta{height:9px;border-radius:5px;background:var(--sel-bg)}
  .vib .forca .trilho.arrasta::-webkit-slider-runnable-track{height:9px;border-radius:5px}
  .vib .forca .trilho.arrasta::-webkit-slider-thumb{width:17px;height:17px;background:var(--pink);margin-top:-4px}
  .vib .forca .motor > .num{font-weight:700;color:var(--pink)}
  .motor.haptica .teto.no-ar.on::after{content:'';display:inline-block;width:6px;
    height:6px;border-radius:50%;background:var(--green);margin-left:3px;
    vertical-align:1px}
  .vib .forca ~ .motor .trilho.travada{display:none}
  .vib .forca.padrao ~ .motor .trilho.arrasta{display:none}
  .vib .forca.padrao ~ .motor .trilho.travada{display:block;background:var(--green);
    opacity:.85;cursor:not-allowed}
  .vib .forca.padrao ~ .motor .lado{pointer-events:none}
  .vib .forca ~ .motor .teto{grid-column:4;grid-row:1}
  .vib .forca ~ .motor .num{grid-row:1;grid-column:3;display:flex;
    justify-content:flex-end;white-space:nowrap}
  .vib .forca ~ .motor .lado:not(.on) ~ .num{grid-column:3 / span 2;
    font-size:10.5px;font-weight:600;font-family:inherit;color:var(--fg)}
  .vib .forca ~ .motor .lado:not(.on) ~ .teto{font-size:0}
  .vib .forca.padrao ~ .motor .lado ~ .num{grid-column:3 / span 2;
    font-size:10.5px;font-weight:600;font-family:inherit;color:var(--green)}
  .vib .forca.padrao ~ .motor .lado ~ .teto{font-size:0}
  .vib .ctrl[data-conectado="nao"] .forca.padrao ~ .motor .trilho.travada{display:none}
  .motor.haptica.fora{opacity:.45}
  .motor.haptica.fora .trilho.arrasta,.motor.haptica.fora .lado{pointer-events:none}
  .vib .ctrl{border-left:1px solid var(--linha);padding:0 14px 0 13px}

  .vib .ctrl[data-conectado="nao"]{border-color:var(--border-forte)}
  .vib .ctrl[data-conectado="nao"] .motor > *,
  .vib .ctrl[data-conectado="nao"] .efeito-lista > *,
  .vib .ctrl[data-conectado="nao"] .acoes-col > *{display:none}
  .vib .ctrl[data-conectado="nao"] .motor::after,
  .vib .ctrl[data-conectado="nao"] .acoes-col::after{
    content:"—";color:var(--linha);display:flex;align-items:center;
    justify-content:center;grid-column:1/-1;width:100%;height:100%}
  .vib .ctrl[data-conectado="nao"] .moldura{border-color:var(--border-forte)}
  .vib .ctrl[data-conectado="nao"] .rot-ctrl{color:var(--fg)}

  .vib > div > *{position:relative}
  .vib > div > *::before{content:'';position:absolute;top:calc(var(--r-ar) * -1);height:0;
    left:-13px;right:-14px;border-top:1px solid var(--rot-linha)}
  .vib > div:not(:last-child) > *::before{right:-14px}
  .vib > div:last-child > *::before{right:0}
  .vib > .rotulos > *::before{left:0;right:calc(var(--gap-col) * -1)}
  .vib > div > *:first-child::before{display:none}
  .vib > div > *:nth-child(3)::before{display:none}
  .vib > .rotulos > *:nth-child(3)::before{display:block}
  .vib > .ctrl > .acoes-col::before{display:none}

  .vib .rotulos > *{display:flex;flex-direction:column;justify-content:center;gap:5px}
  .vib .rotulos > *{align-items:flex-start;text-align:left}
  .vib .rotulos .sec-rot{justify-content:flex-start}
  .vib .rotulos > :not(.cel-des) > .sec-rot{flex:1}
  .sec-rot{font-size:12px;font-weight:600;color:var(--rot-campo);
           display:flex;align-items:center;gap:6px}
  .vib .rotulos .dica{text-transform:none;letter-spacing:0;top:auto;bottom:-4px}
  .vib .rotulos .cel-des{gap:8px}

  .vib .moldura{
    border:1px solid var(--plastico, var(--border-forte));border-radius:8px;
    background:var(--app-bg);
    display:flex;align-items:center;justify-content:center;padding:5px;
  }
  .vib .moldura .ds-svg{height:100%;width:auto;max-width:100%}
  .rot-ctrl{font-size:11px;color:var(--fg);text-align:center;
            display:flex;align-items:center;justify-content:center}
  .vib .rot-ctrl{height:30px;box-sizing:border-box;border:1px solid var(--linha);border-radius:7px;
    font:600 12px 'Space Grotesk',system-ui,sans-serif;color:var(--fg);white-space:nowrap;
    overflow:hidden;text-overflow:ellipsis;align-self:center;width:100%;display:block;
    line-height:28px;padding:0 4px}
  .vib .rot-ctrl .pt{margin:0 6px}
  .vib .ctrl[data-conectado="nao"] .rot-ctrl{color:var(--fg);border:1px dashed var(--border-sutil);
    background:transparent}

  .motor{display:grid;grid-template-columns:36px minmax(0,1fr) 44px 8px;align-items:center;
         gap:8px;height:100%}
  .motor .trilho{height:5px;border-radius:3px;background:var(--border-forte);position:relative}
  .motor .cheio{position:absolute;left:0;top:0;bottom:0;border-radius:3px;background:var(--purple)}
  .motor .cheio::after{content:'';position:absolute;right:-5px;top:-4px;width:12px;height:12px;
    border-radius:50%;background:var(--purple);border:2px solid var(--panel)}
  .motor .num{text-align:right;font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--fg)}
  .motor .teto{font-size:10.5px;color:var(--fg);font-family:'JetBrains Mono',monospace;
    text-align:right;justify-self:end;white-space:nowrap}
  .glifo-forca{cursor:default;display:inline-flex;align-items:center;justify-content:center}
  .motor.off .cheio{background:var(--border-forte)}
  .motor.off .num{color:var(--fg)}
  .motor .trilho.arrasta{appearance:none;-webkit-appearance:none;
    width:100%;padding:0;margin:0;border:0;background:var(--border-forte);
    cursor:grab}
  .motor .trilho.arrasta:active{cursor:grabbing}
  .motor .trilho.arrasta::-webkit-slider-runnable-track{
    height:5px;border-radius:3px;background:transparent}
  .motor .trilho.arrasta::-webkit-slider-thumb{appearance:none;
    -webkit-appearance:none;width:12px;height:12px;border-radius:50%;
    background:var(--purple);border:2px solid var(--panel);margin-top:-4px}
  .motor .trilho.arrasta:focus-visible{outline:2px solid var(--purple);
    outline-offset:3px}

  .lado{
    height:var(--h-escolha);width:36px;border-radius:7px;font-family:inherit;
    border:1px solid var(--linha);background:var(--app-bg);color:var(--fg);
    cursor:pointer;display:flex;align-items:center;justify-content:center;padding:0;
  }
  .lado.on{border-color:var(--orange);background:rgba(255,184,108,.1);color:var(--orange)}
  .lado:hover:not(.on){border-color:var(--comment);color:var(--texto-suave)}

  .acoes-col{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}
  .acoes-col .btn{width:100%;min-width:0;justify-content:center;padding:0 4px;font-size:11.5px}
  .acoes-col .btn.vermelho,.acoes-col .btn.vermelho:hover{
    background:#c62828;border-color:#c62828;color:#fff;font-weight:600}
  .acoes-col .btn.on{border-color:var(--orange);background:rgba(255,184,108,.1);color:var(--orange)}

  .vib .ds-svg [id$="-feat-rumble-esquerdo"] .peca,
  .vib .ds-svg [id$="-feat-rumble-direito"] .peca{stroke:var(--orange);stroke-width:1}
  .vib .ds-svg .oculta{opacity:0 !important}
  .vib .ds-svg .oculta.acesa{opacity:.95 !important;
                             filter:drop-shadow(0 0 1.8px var(--plastico, var(--border-forte)))}

  .vib-estado{margin:0 4px 0;display:flex;flex-direction:column;gap:2px}
  .vib-estado:empty{display:none}
  .vib-estado .est{display:flex;gap:8px;align-items:flex-start;
                   font-size:12px;line-height:1.4}
  .vib-estado .est .sinal{flex:0 0 auto;font-size:9px;line-height:1.9}
  .vib-estado .est.alerta{color:var(--orange)}
  .vib-estado .est.alerta .sinal{color:var(--orange)}
  .vib-estado .est.info{color:var(--cyan)}
  .vib-estado .est.info .sinal{color:var(--cyan)}
  .vib-estado .est.recibo{color:var(--green)}
  .vib-estado .est.recibo .sinal{color:var(--green)}
"""

PAPEIS_QUE_SAO_GESTO = ("testar", "parar",
                        "intensidade", "motor", "haptica", "testar-haptica")


def _endereco_de_pintura(nome, extra=""):
    """`data-papel` quando o nome é gesto desta aba; `data-hef` quando não é."""
    atributo = "data-papel" if nome in PAPEIS_QUE_SAO_GESTO else "data-hef"
    return f' {atributo}="{nome}"' + extra


def _trilho_arrastavel(valor, teto, campo):
    """O trilho da Força como `<input type=range>`: o `value` dele é o que o piloto lê no `change`.

    Vai de 0 a :data:`TETO_DA_FORCA`, de 5 em 5 (:data:`PASSO_DA_FORCA`, desenho de 18/10/2026). O
    alvo de pintura é `valor`, e não `largura`: pintar `style.width` num `<input>` esticaria o
    controle em vez de mover o polegar.
    """
    return _trilho(valor, teto, PASSO_DA_FORCA, campo, "intensidade",
                   DICA_DA_FORCA)


def _trilho(valor, teto, passo, campo, papel, titulo, extra=""):
    """O `<input type=range>` das TRÊS barras que se arrastam nesta coluna."""
    return (f'<input class="trilho arrasta" type="range" min="0"'
            f' max="{teto}" step="{passo}" value="{valor}"'
            f' data-papel="{papel}" data-campo="{campo}"'
            f' data-hef-alvo="valor"{extra}'
            f' title="{titulo}">')


def _linha_da_forca(pct, vazio=False):
    """A linha «Força da vibração»: o controle inteiro · trilho de 0 a 200 · número · `%`.

    Sem os três botões (r3b-05-12): só o trilho, com a porcentagem. `vazio` troca só o texto do
    número pelo travessão; a estrutura e os endereços são os mesmos nos quatro lugares.
    """
    trilho = _trilho_arrastavel(pct, TETO_DA_FORCA, "mult-pos")
    return (f'<div class="motor mult">{BOTAO_DA_FORCA}{trilho}'
            f'<span class="num" data-campo="mult">{VAZIO if vazio else pct}</span>'
            f'<span class="teto">%</span></div>')


def _trilho_travado():
    """A barra travada do Padrão: inteira verde, sem arrasto e sem teclado.

    Vive ao lado do `<input>`, e a folha mostra um ou o outro (`.forca.padrao ~
    .motor`): travar é trocar de elemento, porque um `<input>` escondido não
    recebe seta nem foco, e um desabilitado cinza o que devia ficar verde.
    """
    return ('<span class="trilho travada" role="img" aria-disabled="true"'
            ' aria-label="Padrão: o sinal do jogo, sem ajuste"></span>')


def _barra_de_motor(valor, sigla, m, ligado, botao, vazio=False):
    """A linha de UM motor: interruptor · barra que arrasta · número · `%`.

    `vazio` é o lugar SEM CONTROLE, e ele troca só o TEXTO do número pelo
    travessão — a mesma regra do irmão :func:`_barra`, e a razão inteira está
    lá. O `<input>` continua com `value="0"` porque um `type=range` não guarda
    travessão; ele é `display:none` num lugar vazio, e o que a tela mostra é o
    `—` que a folha põe por cima (`.ctrl[data-conectado="nao"] .motor::after`).

    **É A METADE DE DESENHO QUE A ONDA1-D2 DEIXOU COM ENDEREÇO**, e a decisão
    é de produto, de 04/09/2026, dita fora das três opções que estavam postas:

        "os slcers do botão esquerdo e direito (forte e  # noqa-acento: citação
         fraco) se multiplicam (interagem com os botões economia, moderado,
         máximo, se eu tiver 150% do perfil de vibração e as duas linhas
         estiverem 100 entao a vibração dos 2 será 150%, mas se so a do motor
         fraco tiver 100 e a outrqa 50% então será 150 em um e 75% no outro
         entende?"

    `efetivo(motor) = degrau(coluna) x barra(motor)`, e a conta mora num lugar
    só, do lado do daemon (`gamepad._mults_por_motor`). Esta linha é o primeiro
    fator visível ao lado do segundo: os quatro degraus logo acima, a barra
    aqui.

    **O QUE A LINHA DEIXOU DE MOSTRAR, e onde ele foi parar.** Até 04/09 o
    número desta linha era o par `weak`/`strong` que o JOGO pediu, de 0 a 255 —
    LEITURA. Ele não cabe mais no mesmo pixel que o ajuste (duas escalas na
    mesma barra é a contradição que esta aba mais persegue), e não se perdeu:

    * o **punho que treme** no desenho já sai do mesmo dado (`treme-e`/`treme-d`,
      `_endereca_o_tremor`), e é ele que responde *"chegou força agora?"*;
    * o número exato vira o `title` DESTA linha, pintado pelo alvo `atributo`
      (`motor-{sigla}-pedido`) — e quando não há o que dizer o pintor **APAGA o
      atributo** (`hefesto_vivo.escrever`, ramo `atributo`), de modo que não
      sobra dica afirmando um pedido que ninguém mediu.

    **O `data-papel` VAI NO `<input>`, NUNCA NO `<div>` DE FORA** — a lição já
    paga pela linha "Personalizado": o ouvinte manda `valor: alvo.value ?? ''`,
    e um `<div>` não tem `value`, então o clique chegaria ao pacote sem
    quantidade nenhuma. O `data-lado` viaja junto no MESMO elemento, porque é
    ele que diz ao gesto qual das duas barras foi arrastada
    (`hefesto_vivo.manda_do_alvo`: `lado: d.lado || ''`).

    **O ENDEREÇO DE PINTURA É NOVO DE PROPÓSITO** (`barra-e`/`barra-e-pct`), e
    os velhos (`motor-e`, `motor-e-pct`) continuam sendo emitidos pelo pacote.
    É a PONTE DE PUBLICAÇÃO, e a razão é a mesma do `forca-pct`: a página que
    ela ABRE hoje ainda tem a linha de leitura, e publicar é ato dela. Reusar o
    nome velho para o significado novo faria o produto pintar um multiplicador
    dentro de uma barra de 0 a 255 — a mentira que esta aba mais persegue.

    `off` SEGUE A BARRA, e não o interruptor: com a barra em 0 aquele motor não
    treme neste perfil, e é o que o trilho apagado diz. O interruptor de punho
    continua sem fonte no produto (`app/telas/vibracao.SEM_FONTE['lado:ligado']`)
    e continua sendo desenho — mas agora o desenho não se contradiz, porque a
    cena põe os dois de acordo.
    """
    campo = f"barra-{sigla}"
    titulo = (f'Quanto da vibração chega a este punho — 0 a {TETO_DO_MOTOR}% do'
              f' degrau da coluna. Em 0, este motor fica mudo. Grava na hora, só'
              f' para este controle.')
    trilho = _trilho(valor, TETO_DO_MOTOR, PASSO_DO_MOTOR, campo, "motor",
                     titulo, extra=f' data-lado="{sigla}"')
    return (f'<div class="motor mult{"" if ligado else " off"}"'
            f' data-campo="motor-{sigla}-pedido" data-hef-alvo="atributo"'
            f' data-hef-atributo="title">'
            f'{botao}{trilho}{_trilho_travado()}'
            f'<span class="num" data-campo="{campo}-pct">'
            f'{VAZIO if vazio else valor}</span>'
            f'<span class="teto">%</span></div>')


def _linha_da_haptica(valor, ligado, vazio=False):
    """A linha «Sensor háptico»: interruptor · trilho de 0 a 100 · número · `%` e a luz.

    Desde 02/10/2026 ela mora na faixa que era do Personalizado, logo abaixo da
    Força (A-ABA-VIBRACAO-TEM-O-SENSOR-HAPTICO-E-DOIS-TESTES-01); o nome é o
    dela, «Sensor háptico». A luz «no ar» é a bolinha depois do `%`, acesa pelo
    `haptica_no_ar` do `state_full`.

    O mesmo desenho das linhas dos motores, com gesto próprio (`haptica`,
    porque o teto é outro), e o mesmo par: o
    interruptor é a barra acima de zero (desligar grava 0, ligar devolve o
    padrão do dono), sem campo booleano à parte. O teto é lido do esquema
    (:data:`TETO_DA_HAPTICA`). Onde o Hefesto não está no caminho do controle
    (o Nativo pelo rádio sem a ponte), o pacote acende `fora` e a linha fica
    cinza — e o porquê fica no `?` do rótulo, e não na tela aberta.
    """
    botao = (f'<button class="haptica-lado lado{" on" if ligado else ""}" '
             f'data-gesto="haptica" '
             f'data-campo="lado-h" data-hef-alvo="classe" '
             f'data-hef-quando="1" '
             f'title="Háptica por áudio — a vibração fina que o jogo manda como som.">'
             f'{glifo("haptica", ativo=ligado, tam=18)}</button>')
    titulo = (f'A força da háptica por áudio neste controle — 0 a {TETO_DA_HAPTICA}%.'
              f' 50% é o jogo como ele mandou. Grava na hora, só para ele.')
    trilho = _trilho(valor, TETO_DA_HAPTICA, PASSO_DO_MOTOR, "barra-h", "haptica",
                     titulo)
    return (f'<div class="motor mult haptica"'
            f' data-campo="haptica-fora" data-hef-alvo="classe"'
            f' data-hef-classe="fora">'
            f'{botao}{trilho}{_trilho_travado()}'
            f'<span class="num" data-campo="barra-h-pct">'
            f'{VAZIO if vazio else valor}</span>'
            f'<span class="teto no-ar" data-campo="haptica-no-ar"'
            f' data-hef-alvo="classe"'
            f' title="Aceso: há háptica chegando a este controle agora.">%</span></div>')


_ROTULOS_DA_IMERSAO = {
    padroes.DO_ESTILO: "Do estilo", padroes.SEM_EFEITO: "Sem efeito", **padroes.ROTULOS}


def _lista_do_efeito(gesto, campo, campo_dica, nome, escolhas, rotulos, dicas):
    """Uma lista suspensa do controle: «Do estilo» primeiro, «Sem efeito» depois, as formas em seguida.

    O gesto do `<select>` e o campo que a pintura escreve nele têm nomes distintos: o pintor
    acha o valor por `data-campo`, e o clique, por `data-gesto`. A frase da opção escolhida é a
    dica da caixa em volta da lista (16/10/2026), escrita pelo campo da dica a cada tique.
    """
    opcoes = "".join(
        f'<option value="{chave}"{" selected" if i == 0 else ""}>{rotulos[chave]}</option>'
        for i, chave in enumerate(escolhas))
    return (f'<div class="efeito-lista">'
            f'<span class="vib-efeito-dica" data-campo="{campo_dica}" data-hef-alvo="atributo" '
            f'data-hef-atributo="data-dica" data-dica="{dicas[escolhas[0]]}">'
            f'<select class="vib-efeito" data-gesto="{gesto}" aria-label="{nome}" '
            f'data-campo="{campo}" data-hef-alvo="valor">'
            f'{opcoes}</select></span></div>')


LADOS = (("e", ESQ, "esq"), ("d", DIR, "dir"))


VAZIO = "—"


def _endereca_o_tremor(desenho, pref):
    """Dá endereço de pintura aos dois grupos de motor do SVG — 03/09/2026."""
    for sigla, m, _k in LADOS:
        ancora = f'id="{pref}-{m["id"]}"'
        if ancora not in desenho:
            raise SystemExit(
                f"ERRO em _endereca_o_tremor({pref!r}): o desenho não tem "
                f"{ancora} — o motor {sigla!r} sai do mapa "
                f"(docs/data/pecas-do-dualsense.csv, coluna `no_svg`), e sem a "
                f"âncora o punho que treme volta a ser o da cena, calado.")
        desenho = desenho.replace(
            ancora,
            f'{ancora} data-campo="treme-{sigla}"'
            f' data-hef-alvo="classe" data-hef-classe="acesa"', 1)
    return desenho



FOLHA_DOS_28 = re.sub(r"</?style[^>]*>", "", monta_.folha_das_cores())

_ABRE_A_TINTA = '<defs id="cores-do-dualsense">'
if _ABRE_A_TINTA not in monta_.DS:
    raise SystemExit(
        "ERRO em aba05: o desenho não tem mais o `<defs id=\"cores-do-"
        "dualsense\">` — os doze modelos que pintam por `url(#…)` ficariam sem "
        "tinta na página.")
TINTA_DOS_28 = (
    monta_.DS[monta_.DS.index(_ABRE_A_TINTA):
              monta_.DS.index('<style id="cores-do-dualsense-folha">')]
    + "</defs>")

BLOCO_DA_TINTA = (
    f'          <svg width="0" height="0" aria-hidden="true"\n'
    f'               style="position:absolute;overflow:hidden">'
    f'{TINTA_DOS_28}</svg>\n')

ENDERECO_DA_COR = ('data-campo="colorway" data-hef-alvo="atributo"'
                   ' data-hef-atributo="data-colorway"')

_FOLHA_PODADA = re.compile(
    r'\s*<style id="[^"]*cores-do-dualsense-folha">.*?</style>', re.S)


def _endereca_a_cor(desenho, pref, cor, com_dono=True):
    """Dá ao `<svg>` o endereço da COR e tira dele a folha de um modelo só.

    `com_dono=False` é o LUGAR VAZIO da mesa, e ele sai daqui **sem**
    `data-colorway`. Não é economia: é a regra de produto — campo sem informação não
    mostra nada. Um lugar sem controle não tem modelo, e afirmar "Galactic
    Purple" ali seria o desenho falando por um aparelho que não existe. Sem o
    atributo, nenhuma regra da folha casa e o desenho cai no cinza neutro, que é
    o que o `.ctrl[data-conectado="nao"]` já pinta por cima com `var(--linha)` — a tela não muda
    um pixel, e o arquivo deixa de afirmar o que não sabe.

    O ENDEREÇO FICA NOS QUATRO, inclusive nos vazios: no dia em que um terceiro
    controle entrar na mesa, o pintor tem onde escrever o modelo dele.

    RECUSA QUANDO A ÂNCORA SOME, pelas duas vias — `monta.troca` para o `<svg>`
    e a contagem para a folha. É a lição do `str.replace` que não casava: um
    endereço que não entra no HTML é uma pintura que não acontece, e ela é
    silenciosa dos dois lados.
    """
    quem = f"aba05 · _endereca_a_cor({pref!r})"
    desenho = monta_.troca(
        desenho, quem, f'<svg data-colorway="{cor}" ',
        f'<svg {ENDERECO_DA_COR} data-colorway="{cor}" ' if com_dono
        else f'<svg {ENDERECO_DA_COR} ')
    achadas = _FOLHA_PODADA.findall(desenho)
    if len(achadas) != 1:
        raise SystemExit(
            f"ERRO em {quem}: esperava UMA folha podada dentro do desenho e "
            f"achei {len(achadas)}. A página publica as 28 de uma vez; deixar "
            f"a podada aqui dentro devolveria a este controle uma cor só.")
    return _FOLHA_PODADA.sub("", desenho, count=1)


ESTADO_DO_LUGAR_VAZIO = {"pct": 0,
                         "esq": (False, 0), "dir": (False, 0), "hap": (False, 0)}


def _coluna(c, e=None, conectado=None):
    """Uma coluna da mesa: o desenho, o nome, a força, os dois motores, as ações.

    `e` é o estado daquela coluna. Sem ele vale a CENA do mockup
    (:data:`ESTADO`, chaveada pelo `pref`) para quem está na mesa, e o
    :data:`ESTADO_DO_LUGAR_VAZIO` para quem não está; com ele a coluna é montada
    com o que o daemon respondeu. O parâmetro existe para que a tela viva saia do
    MESMO gerador que a tela aprovada: um segundo emissor de HTML seria o segundo
    dono do desenho.

    **UMA FUNÇÃO SÓ PARA OS QUATRO LUGARES — 07/09/2026, e é cura de defeito
    MEDIDO com os quatro DualSense do usuário na mesa.** Havia um `_coluna_vazia()` à
    parte que devolvia um cartão **sem um único `data-campo` por dentro**:

        <div class="ctrl vazia" …><div class="seg"><span class="nada">—</span></div>…

    O daemon publicava os quatro controles, o pacote mandava as quatro colunas
    (`a05_vibracao` emite para os QUATRO lugares de propósito) e o piloto fazia
    `raiz.querySelectorAll('[data-campo="…"]')` dentro do bloco daquele
    `data-controle` (`hefesto_vivo._pintar`, passo 2). **Sem endereço, o dado
    dela chegava e não tinha onde pousar**: o P3 e o P4 continuavam dizendo
    `P3 • Desconectado` com travessão em tudo, com os aparelhos ligados.

    Medido na página publicada de 06/09, contando `data-campo` por
    `[data-controle="pN"]`: **P1 e P2 com 14 endereços distintos, P3 e P4 com
    UM** (o `colorway` do `<svg>`, que só existia por acidente do
    `_endereca_a_cor`).

    **A CAUSA DE FUNDO ERAM OS DOIS RAMOS**, e é por isso que a cura é fundi-los:
    o lugar cheio ganhou o degrau endereçado (03/09), o punho que treme (03/09),
    a cor do plástico (03/09) e as duas barras de motor (04/09) — e nenhuma
    dessas quatro passou pelo lugar vazio, porque ele era outro texto. **Um dos
    dois ramos envelheceu sem o outro**, quatro vezes em dois dias, sem uma
    linha de erro.

    `conectado` DECIDE DUAS COISAS, e só elas:

    a) **a marca do cartão** — `class="ctrl off"`, `data-conectado="nao"` e o
       `title`. São as MESMAS marcas que o piloto põe num lugar que esvazia ao
       vivo (`_pintar`, passo 1b) e TIRA quando o controle chega (passo 1c). É o
       que faz o lugar reabrir sozinho, sem regerar nada. A classe `vazia`
       morreu com esta fusão justamente por isso: **o piloto não a conhece**, e
       um cartão que nascesse com ela ficaria cinza para sempre, agora com o
       dado dela chegando por baixo.
    b) **o valor INICIAL de cada campo** — o travessão nos números, nenhum
       degrau aceso, nenhum punho tremendo e nenhum `data-colorway`. Quem some
       da tela são os WIDGETS, e quem os some é a folha
       (`.ctrl[data-conectado="nao"] .seg > *{{display:none}}` e os irmãos), que
       é a mesma cura de 05/09 para a coluna que perde o dono ao vivo. Nada de
       clicável sobrevive num lugar vazio: `display:none` não recebe clique.

    A ordem de 31/08/2026 continua inteira — *"Deixa os outros espaços dos
    4 controles a mostra ainda mas cinza igual vc fez na aba jogar."* A coluna
    continua na tela, com as sete linhas na mesma altura, o nome dizendo a
    POSIÇÃO e o ESTADO (nunca o do plástico) e o travessão no lugar do ajuste.
    O que mudou é que agora ela tem ONDE receber o controle que chega.
    """
    if conectado is None:
        conectado = c.get("conectado", True)
    e = e or (ESTADO[c["pref"]] if conectado else ESTADO_DO_LUGAR_VAZIO)
    plastico = cor_da_zona(c["cor"])
    acesos = tuple(m["id"] for m, k in ((ESQ, "esq"), (DIR, "dir")) if e[k][0])
    desenho = _endereca_a_cor(
        _endereca_o_tremor(
            svg(f'vb-{c["pref"]}', c["cor"], acesos=acesos, lampadas=False),
            f'vb-{c["pref"]}'),
        f'vb-{c["pref"]}', c["cor"], com_dono=conectado)

    linhas = []
    for sigla, m, k in LADOS:
        ligado, valor = e[k]
        botao = (f'<button class="lado{" on" if ligado else ""}" '
                 f'data-gesto="lado" data-lado="{sigla}" '
                 f'data-campo="lado-{sigla}" data-hef-alvo="classe" '
                 f'data-hef-quando="1" '
                 f'title="{m["nome"]} — {m["nota"]}">'
                 f'{glifo(m["glifo"], ativo=ligado, tam=18)}</button>')
        linhas.append(_barra_de_motor(valor, sigla, m, ligado, botao,
                                      vazio=not conectado))

    classe = "ctrl" if conectado else "ctrl off"
    marca = ("" if conectado else
             ' data-conectado="nao" title="Nenhum controle neste lugar."')
    tinta = f' style="--plastico:{plastico}"' if conectado else ""
    if conectado:
        rotulo = monta_.rotulo(c, "modelo")
    else:
        rotulo = f'P{c["jogador"]} <span class="pt">•</span> Desconectado'
    return f'''
          <div class="{classe}" data-controle="{c["pref"]}" data-uniq="{c.get("uniq", "")}"{marca}>
            <div class="moldura" data-hef="desenho" data-campo="plastico"
                 data-hef-alvo="plastico"{tinta}>{desenho}</div>
            <div class="rot-ctrl" data-campo="identidade-titulo" data-hef-alvo="atributo"
                 data-hef-atributo="title" title="{re.sub(r"<[^>]+>", "", rotulo)}"><span data-hef="identidade">{rotulo}</span></div>
            <div class="forca" data-campo="padrao" data-hef-alvo="classe"
                 data-hef-classe="padrao">
              {_linha_da_forca(e["pct"], vazio=not conectado)}
            </div>
            {_linha_da_haptica(e["hap"][1], e["hap"][0], vazio=not conectado)}
            {_lista_do_efeito(GESTO_DO_EFEITO_HAPTICO, CAMPO_DO_EFEITO_HAPTICO,
                              CAMPO_DA_DICA_DO_HAPTICO, "Efeito háptico", formas.ESCOLHAS,
                              formas.ROTULOS, formas.DICAS)}
            {linhas[0]}
            {linhas[1]}
            {_lista_do_efeito(GESTO_DO_EFEITO_IMERSAO, CAMPO_DO_EFEITO_IMERSAO,
                              CAMPO_DA_DICA_DA_IMERSAO, "Padrão dos motores", padroes.ESCOLHAS,
                              _ROTULOS_DA_IMERSAO, padroes.DICAS)}
            <div class="acoes-col">
              <button class="btn" data-papel="testar" data-campo="em-teste"
                      data-hef-alvo="classe" data-hef-atributo="aria-pressed"
                      aria-pressed="false">Vibração</button>
              <button class="btn" data-papel="testar-haptica" data-campo="em-teste-h"
                      data-hef-alvo="classe" data-hef-atributo="aria-pressed"
                      aria-pressed="false">Háptica</button>
              <button class="btn vermelho" data-papel="parar"
                      data-hef-rotulo="o texto do botão">Parar</button>
            </div>
          </div>'''


MIOLO = f'''
{BLOCO_DA_TINTA}
    <div class="quadro vib-quadro" data-modo-da-aba="{monta_.MODO_PERSONALIZADO}" data-campo="{GESTO_DO_MODO}"
         data-hef-alvo="atributo" data-hef-atributo="data-modo-da-aba">
      <div class="quadro-topo">
        <span class="quadro-titulo" data-dica="Quanto do que o jogo pede chega a cada controle. A fita do topo não escolhe nada aqui">Vibração</span>
        {trava_do_nativo("na vibração")}
        {monta_.modo_auto(GESTO_DO_MODO, governa=GOVERNA, dica=DICA_DO_AUTOMATICO)}
      </div>
      <div class="quadro-corpo">
        <div class="vib">

          <div class="rotulos">
            <div class="cel-des">
              <span class="sec-rot" data-dica="O lado que treme acende em laranja; o contorno na cor do plástico diz de quem é o controle. Apagado é lado desligado">Controle</span>
            </div>
            <div><span class="sec-rot">Modelo</span></div>
            <div><span class="sec-rot" data-dica="{DICA_DA_FORCA}. {DICA_DO_TETO_DA_MESA}">Força da vibração</span></div>
            <div><span class="sec-rot" data-dica="A vibração fina que o jogo manda como som, no cabo e no BT. O risco no meio é 50%: o jogo como ele mandou. {DICA_DO_TETO_DA_MESA} Cinza quando o jogo fala direto com o controle, sem passar pelo Hefesto">Sensor háptico</span></div>
            <div><span class="sec-rot" data-dica="A forma do toque háptico deste controle. Do estilo segue o estilo e Sem efeito cala o toque; a força é a do Sensor háptico">Efeito háptico</span></div>
            <div><span class="sec-rot" data-dica="Motor do punho esquerdo: contrapeso maior, som grosso. Desligue um lado e aquele punho para de tremer">{ESQ["rot"]}</span></div>
            <div><span class="sec-rot" data-dica="Motor do punho direito: contrapeso menor, som fino">{DIR["rot"]}</span></div>
            <div><span class="sec-rot" data-dica="O padrão dos motores deste controle. Do estilo segue o estilo e Sem efeito cala os motores; o Testar toca o padrão escolhido">Padrão dos motores</span></div>
            <div><span class="sec-rot" data-dica="Vibração treme os motores deste controle até o Parar, seguindo ao vivo as barras da coluna. Háptica toca a vibração fina pelo som, com a força do Sensor háptico. No mesmo controle ligar um desliga o outro, e cada controle tem o seu teste. Parar corta os dois deste controle e devolve a vibração dele ao jogo. {DICA_DOS_VALORES_QUE_PASSAM}">Testar agora</span></div>
          </div>
{"".join(_coluna(c) for c in MESA)}

        </div>
        <div class="vib-estado" id="vib-estado">{html_do_estado(textos_do_estado(CENA_DO_ESTADO))}</div>
      </div>
    </div>
'''

LEGENDA = f'''<div class="nota">
  <h2>O que você pediu, e está aqui</h2>
  <ul>
    <li><b>A Força da vibração é só o trilho</b> (18/10): saíram os botões de degrau, e ficou o trilho de 0 a 200% com a porcentagem e o ícone do DualSense. Abaixo de 100% abaixa a vibração; acima, reforça a fraca, até o máximo do motor. A linha ficou mais baixa e o desenho do controle ganhou o espaço. A <b>Sensor háptico</b> tem a bolinha verde acesa quando a háptica está chegando ao controle, e o <b>Testar agora</b> tem <b>Vibração</b>, <b>Háptica</b> e <b>Parar</b> numa linha só.</li>
    <li><b>Os quatro controles, um por coluna, sempre à vista</b> — na mesma ordem da fita do topo, cada um com a sua cor de plástico na borda do desenho.</li>
    <li><b>A força tem endereço, e o endereço é a coluna</b> — cada uma tem a sua barra de Força. Como os quatro estão à vista, <b>a fita do topo não escolhe nada aqui</b> e nasce esmaecida (28/08). Também saiu o destaque que a coluna do P1 tinha: com a fita inerte, ele afirmaria na tela uma coisa que a fita já não faz.</li>
    <li><b>As cinco lâmpadas do jogador saíram do desenho</b> (28/08). Medidas neste navegador, nesta aba: <b>2,79 × 0,93 px</b> cada uma. Não é pouco contraste, é pouco pixel — menos de um pixel de altura não diz nada, aceso ou apagado. Quem diz o jogador aqui é o rótulo embaixo da coluna, que se lê. Elas continuam desenhadas na <b>Iluminação</b>, onde o controle é grande.</li>
    <li><b>Um bloco só</b> — as duas áreas viraram uma tabela do mesmo quadro.</li>
    <li><b>Motor esquerdo e direito são o que ATIVA o lado durante o jogo</b> — o interruptor de cada lado, e o desenho mostra qual punho treme.</li>
    <li><b>A barra de Força vai de 0 a {TETO_DA_FORCA}%</b>, de 5 em 5 — o controle não tem nível de 150%, e os {TETO_DA_FORCA}% do trilho já existiam.</li>
  </ul>

  <h2>O que passou a vir do mapa, e deixou de ser digitado</h2>
  <ul>
    <li><b>Os quatro controles</b> saem de <code>monta.MESA</code> — nome, jogador, plástico e transporte. A aba não sabe contar até quatro: ela percorre a lista.</li>
    <li><b>As cores</b> saem de <code>cor_da_zona()</code>, que lê o <code>&lt;style&gt;</code> gerado por <code>gerar_cores_do_dualsense.py</code> a partir de <code>docs/data/cores-do-dualsense.csv</code>. Não há um hexadecimal de plástico escrito nesta aba.</li>
    <li><b>Os dois motores</b> saem de <code>docs/data/pecas-do-dualsense.csv</code>: o id no desenho (<code>{ESQ["id"]}</code> e <code>{DIR["id"]}</code>), o glifo de cada um, o nome e a nota que vira dica.</li>
    <li><b>O padrão das lâmpadas</b> continua vindo do produto (<code>core/led_control.py</code>): P1 é a do meio e o P3 é <code>135</code> — não <code>234</code>, que era o que estava digitado no mockup. Ele não é desenhado nesta aba (elas saíram, por tamanho), e segue desenhado na Iluminação.</li>
  </ul>

  <h2>A sua dúvida sobre os motores, respondida</h2>
  <p style="margin:5px 0 10px">Você desconfiou certo do nome. <b>Não existe "leve" e "forte" para cada motor</b> — existem <b>dois motores</b>, um em cada punho, e cada um recebe <b>um</b> valor de 0 a 255. O da esquerda tem <b>contrapeso maior</b>, por isso soa grosso; o da direita, menor, soa fino. "Leve" e "forte" são apelidos dos <b>lados</b>.</p>
  <p style="margin:0 0 10px">Medido nesta casa, e está na canônica (<code>dualsense-referencia-canonica.md:303</code>): com o daemon parado, um <code>EV_FF</code> ligou o esquerdo e o report seguinte pediu <code>common[2]=200</code> (direito) e <code>common[3]=0</code> (esquerdo) — <b>o tremor trocou de lado</b>. Palavra sua, na medição: <i>"esquerda e senti que foi pra direita e lá morreu"</i>. São dois bytes independentes. No código do produto o par é <code>weak</code>/<code>strong</code> = direito/esquerdo.</p>

  <h2>Ainda aberto — precisa da sua palavra</h2>
  <ul>
    <li><b>A cor do lado que treme — e o rótulo que a contradizia.</b> Você decidiu "cor do plástico" (D-O-SVG-VIBRA-POR-LADO), e o rótulo da coluna prometia isso com estas palavras: <i>"acende na cor do plástico daquele controle"</i>. O que está desenhado é <b>laranja</b>, e a tela se contradizia sozinha. A frase passou a descrever o desenho, porque o laranja tem motivo medido: o contorno do controle <i>já é</i> a cor do plástico, então um traço de plástico sobre ele <b>apagaria</b> o lado em vez de mostrá-lo, e o laranja é o que diz o LADO de longe — a cor do plástico não distingue os dois punhos do mesmo controle. Quem diz de quem é o tremor é o contorno e a borda da moldura, que são o plástico.<br>
        <b>Se você quiser o contrário, é uma linha:</b> o traço vira <code>var(--plastico)</code> e a frase volta ao que era — mas então os dois lados acesos de um controle ficam da mesma cor do corpo dele, e o "qual punho treme" passa a depender só da espessura do traço.</li>
    <li><b>Respondida em 28/08, e por isso saiu daqui:</b> "com a fita em Todos, as quatro colunas mexem juntas?". Não há mais o que a fita mexa nesta aba — os quatro ficam lado a lado e cada coluna se ajusta sozinha. A fita esmaecida é a tela dizendo isso.</li>
    <li><b>O "Auto" mostra 70% no P3</b> porque a bateria dele está no meio. Esse número muda sozinho na tela enquanto joga, ou só quando você entra na aba?</li>
  </ul>
</div>

</body>
</html>
'''

CSS_DAS_MEDIDAS = f"""
  .vib{{
    --larg-rot:{monta_.larg_rotulos('05-vibracao')}px;
    --gap-col:{monta_.GAP_DAS_COLUNAS}px;
  }}
"""

def _colunas_do_corpo(corpo):
    """O HTML de cada `[data-controle="pN"]`, na língua em que o PILOTO o lê."""
    import re as _re
    ate_a_faixa = corpo.split('class="vib-estado"', 1)[0]
    achados = {}
    for pedaco in ate_a_faixa.split('<div class="ctrl')[1:]:
        abre = pedaco.split(">", 1)[0]
        quem = _re.search(r'data-controle="(p\d+)"', abre)
        if quem:
            achados[quem.group(1)] = pedaco
    return achados


def _conferir(doc):
    """As decisões de produto nesta aba, conferidas NA SAÍDA. Só o miolo, sem"""
    import re as _re
    corpo = doc.split('<div class="miolo">', 1)[-1].split('<div class="nota">', 1)[0]
    corpo = _re.sub(r"<!--.*?-->", "", corpo, flags=_re.S)
    corpo = _re.sub(r"<style[^>]*>.*?</style>", "", corpo, flags=_re.S)
    if len(corpo) < 2000:
        raise SystemExit("ERRO: a régua não achou o miolo desta aba.")
    falhas = []

    def exigir(cond, oque):
        if not cond:
            falhas.append(oque)

    vazios = [c for c in MESA if not c.get("conectado", True)]
    blocos = _colunas_do_corpo(corpo)
    exigir(corpo.count('class="ctrl off"') == len(vazios),
           f"os lugares vazios marcados `ctrl off` não são {len(vazios)}")
    exigir(corpo.count('data-conectado="nao"') == len(vazios),
           f"os lugares vazios marcados `data-conectado=\"nao\"` não são "  # (noqa-acento)
           f"{len(vazios)}")
    exigir("ctrl vazia" not in corpo,
           "a classe `vazia` voltou ao cartão — o piloto tira a `off` e o "
           "`data-conectado`, e não conhece a `vazia`: o lugar ficaria cinza "
           "para sempre com o dado dela chegando por baixo")
    exigir(len(blocos) == len(MESA),
           f"a régua não achou as {len(MESA)} colunas: {sorted(blocos)}")
    for c in vazios:
        exigir(f'P{c["jogador"]} <span class="pt">•</span> Desconectado' in corpo,
               f"a coluna do P{c['jogador']} não diz Desconectado")
        exigir(c["nome"] not in corpo,
               f"o nome do plástico {c['nome']!r} voltou a uma coluna vazia")
        bloco = blocos.get(c["pref"], "")
        exigir("data-colorway=" not in bloco,
               f"o lugar vazio {c['pref']} afirma um modelo de controle — o "
               f"ENDEREÇO da cor vai nos quatro, o VALOR só em quem tem "
               f"aparelho")
        exigir("--plastico:" not in bloco,
               f"o lugar vazio {c['pref']} afirma uma cor de plástico — mesma "
               f"regra do `data-colorway` logo acima")
    for alvo in (".motor > *", ".efeito-lista > *", ".acoes-col > *"):
        exigir(f'.vib .ctrl[data-conectado="nao"] {alvo}' in doc,
               f"a folha deixou de esconder `{alvo}` num lugar sem controle — "
               f"os trilhos e o `Testar` voltam a ficar clicáveis "
               f"para um aparelho que não está na mesa")
    exigir('.vib .ctrl[data-conectado="nao"]:not(' not in doc,
           "voltou uma exceção ao `[data-conectado=\"nao\"]` na folha desta "  # (noqa-acento)
           "aba — ela separa o lugar que NASCE vazio do que esvazia ao vivo, e "
           "duas caras para o mesmo estado na mesma tela é o que esta aba mais "
           "persegue")
    exigir(corpo.count('class="trilho arrasta"') == len(MESA) * (1 + len(LADOS) + 1),
           "os trilhos arrastáveis não são os mesmos nos quatro lugares")
    exigir("--r-passo:calc(var(--r-ar) * 2)" in doc, "o passo deixou de ser o dobro do ar")
    exigir("top:calc(var(--r-ar) * -1)" in doc or "top:-var(--r-ar)" in doc
           or "top: calc(var(--r-ar) * -1)" in doc,
           "a divisória saiu do meio do vão")
    exigir(".rotulos > *{align-items:flex-start;text-align:left}" in doc,
           "os rótulos voltaram a alinhar à direita")
    campos = set(_re.findall(r'data-campo="([^"]+)"', corpo))
    papeis = set(_re.findall(r'data-papel="([^"]+)"', corpo))
    exigir(not (campos & papeis),
           f"nome que é valor E clique ao mesmo tempo: {sorted(campos & papeis)} — "
           f"a pintura escreve o valor dentro do botão")
    for c in MESA:
        exigir(f'data-controle="{c["pref"]}"' in corpo,
               f'a coluna do {c["pref"]} não tem data-controle')
    exigir(corpo.count('data-controle="p') == len(MESA),
           f'as colunas endereçadas não são {len(MESA)}')
    exigir('id="vib-estado"' in corpo, "a faixa de estado sumiu da aba")
    cena = textos_do_estado(CENA_DO_ESTADO)
    exigir(cena == [],
           f"a cena do estado voltou a acender linha permanente: {cena} — a "
           f"decisão dela de 07/09/2026 é que, com a mesa quieta, não há texto "
           f"nenhum sob a grade")
    exigir('id="vib-estado"></div>' in corpo,
           "a faixa de estado não nasce vazia no desenho — com a mesa quieta "
           "ela não tem o que dizer, e o que estiver ali é prosa cravada")
    exigir(".vib-estado:empty{display:none}" in doc,
           "sumiu a regra que esconde a faixa vazia: sem ela a faixa vira uma "
           "tira de nada debaixo da grade")
    _com_pedidos = {"rumble_policy": "economia",
                    "rumble_ff": {"plays": 12, "nao_nulos": 12, "vpads": 1}}
    exigir(textos_do_estado(_com_pedidos) == [],
           f"a faixa voltou a falar sobre o que o JOGO pediu: "
           f"{textos_do_estado(_com_pedidos)} — ela saiu por ordem dela em "
           f"07/09/2026")
    for sigla, _m, _k in LADOS:
        exigir(corpo.count(f'data-campo="treme-{sigla}"') == len(MESA),
               f"o motor {sigla!r} não tem endereço em cada uma das "
               f"{len(MESA)} colunas — sem ele o tremor do controle que chegar "
               f"naquele lugar não tem onde pousar")
    exigir(corpo.count('data-hef-classe="acesa"') == len(LADOS) * len(MESA),
           "a classe do tremor não é a `acesa` do desenho compartilhado")
    for c in vazios:
        exigir(' acesa' not in blocos.get(c["pref"], ""),
               f"o lugar vazio {c['pref']} nasceu com um punho ACESO — o "
               f"endereço vai nos quatro, a classe só em quem tremeu de verdade")
    for frase, nome in ((DICA_DO_TETO_DA_MESA, "o teto da mesa"),
                        (DICA_DOS_VALORES_QUE_PASSAM, "os valores que passam pela intensidade")):
        exigir(frase in corpo, f"a dica perdeu a frase da janela estável: {nome}")
    _achou = _re.search(r'data-dica="([^"]*)">Sensor háptico</span>', corpo)
    _haptica = _achou.group(1) if _achou else ""
    exigir(_haptica and DICA_DO_TETO_DA_MESA in _haptica
           and _haptica.index("O risco no meio é 50%")
           < _haptica.index(DICA_DO_TETO_DA_MESA) < _haptica.index("Cinza quando"),
           "o «?» da sensor háptico perdeu a frase do teto do perfil de bateria (logo depois do 50%)")
    sobrando = papeis - set(PAPEIS_QUE_SAO_GESTO)
    exigir(not sobrando,
           f"`data-papel` sem gesto que atenda: {sorted(sobrando)} — o ouvinte "
           f"do piloto lê todo `data-papel` como nome de gesto, e um nome que "
           f"nenhum pacote registra vira clique que não responde. Use "
           f"`data-hef` para endereço que é só pintura")

    arrastaveis = _re.findall(r'<input class="trilho arrasta"[^>]*>', corpo)
    por_papel = {}
    for tag in arrastaveis:
        achado = _re.search(r'data-papel="([^"]+)"', tag)
        por_papel.setdefault(achado.group(1) if achado else "", []).append(tag)
    exigir(len(por_papel.get("intensidade", [])) == len(MESA),
           f"as barras 'Personalizado' arrastáveis não são {len(MESA)} "
           f"(achei {len(por_papel.get('intensidade', []))}) — a de cada lugar "
           f"tem de ser um `<input type=range>`, senão o clique dela chega "
           f"ao pacote sem número")
    for tag in por_papel.get("intensidade", []):
        exigir(f'max="{TETO_DA_FORCA}"' in tag,
               f"a barra da Força não vai até {TETO_DA_FORCA}% — o desenho de "
               f"18/10 é o trilho de 0 a 200 (o corte em 100% estava errado)")
        exigir(f'step="{PASSO_DA_FORCA}"' in tag,
               f"o passo da Força não é {PASSO_DA_FORCA} — o desenho de 18/10 "
               f"anda de 5 em 5")
    da_haptica = por_papel.get("haptica", [])
    de_motor = por_papel.get("motor", [])
    exigir(len(da_haptica) == len(MESA),
           f"a barra da háptica por áudio não está nos {len(MESA)} lugares "
           f"(achei {len(da_haptica)})")
    for tag in da_haptica:
        exigir(f'max="{TETO_DA_HAPTICA}"' in tag and 'data-campo="barra-h"' in tag,
               f"a barra da háptica não para em {TETO_DA_HAPTICA}% ou perdeu o "
               f"endereço `barra-h` — o teto é o dos motores")
    exigir(TETO_DA_HAPTICA == TETO_DO_MOTOR,
           f"o «Sensor háptico» para em {TETO_DA_HAPTICA}% e os motores em {TETO_DO_MOTOR}%")
    exigir('class="quadro criar' not in corpo and "Criar efeitos novos" not in corpo,
           "o «Criar efeitos novos» voltou à Vibração: ele não criava nada que se usasse")
    exigir(".vib > .rotulos > *:nth-child(3)::before{display:block}" in doc
           and ".vib > .ctrl > .acoes-col::before{display:none}" in doc,
           "a linha entre «Modelo» e «Força» saiu dos rótulos, ou a de «Testar agora» voltou às colunas")
    exigir(".vib .forca .trilho.arrasta{height:9px" in doc,
           "a «Força da vibração» perdeu o trilho largo que a separa das outras três barras")
    exigir(len(de_motor) == len(LADOS) * len(MESA),
           f"as barras de motor arrastáveis não são {len(LADOS) * len(MESA)} "
           f"(achei {len(de_motor)}) — cada LUGAR tem UMA por punho, e é "
           f"o que fecha a `SEM_DONO['barra:motor']`")
    for sigla, _m, _k in LADOS:
        do_lado = [t for t in de_motor if f'data-lado="{sigla}"' in t]
        exigir(len(do_lado) == len(MESA),
               f"a barra do motor {sigla!r} não tem `data-lado` em cada um dos "
               f"{len(MESA)} lugares — sem ele o gesto não sabe qual das duas "
               f"foi arrastada")
        for tag in do_lado:
            exigir(f'data-campo="barra-{sigla}"' in tag,
                   f"a barra do motor {sigla!r} não usa o endereço novo "
                   f"`barra-{sigla}` — `motor-{sigla}-pct` é a LEITURA de 0 a "
                   f"255 da página publicada, e escrever nela um multiplicador "
                   f"põe o cursor no lugar errado")
    for tag in de_motor:
        exigir(f'max="{TETO_DO_MOTOR}"' in tag,
               f"a barra de motor não para em {TETO_DO_MOTOR}% — o teto é o "
               f"`MOTOR_PCT_MAX` do esquema, e passar dele daria à mesma peça "
               f"duas portas para o mesmo estouro")
        exigir(f'step="{PASSO_DO_MOTOR}"' in tag,
               f"o passo da barra de motor não é {PASSO_DO_MOTOR} — a borda "
               f"aceita todo inteiro de 0 a {TETO_DO_MOTOR}, e um passo maior "
               f"esconderia valores que o produto grava sem reclamar")
    for morto in ('data-campo="trava"', '<span class="sec-rot">Estado'):
        exigir(morto not in corpo,
               f"{morto!r} voltou à aba 05 — a faixa de estado saiu em "
               f"05/09/2026 por decisão dela: *'remove ela não faz sentido'*")
    exigir("--r-estado" not in doc,
           "`--r-estado` voltou à folha da aba 05 — a faixa cuja altura ele "
           "reservava saiu em 05/09/2026, e altura guardada para linha que não "
           "existe é rolagem paga por nada")
    exigir(doc.count("minmax(var(--r-efeito),1fr) minmax(var(--r-acoes),1fr);") == 1,
           "a grade da aba 05 deixou de terminar no `--r-acoes` em fração, depois da faixa do "
           "efeito imersão — a oitava faixa saiu em 05/09/2026 e as duas listas entraram em "
           "15/10/2026")
    _ordem = _re.findall(r'<span class="sec-rot"[^>]*>([^<]+)</span>',
                         corpo.split('<div class="rotulos">', 1)[-1].split('<div class="ctrl', 1)[0])
    exigir(_ordem == ["Controle", "Modelo", "Força da vibração", "Sensor háptico", "Efeito háptico",
                      ESQ["rot"], DIR["rot"], "Padrão dos motores", "Testar agora"],
           f"as faixas da aba 05 saíram da ordem do desenho A: {_ordem}")
    for gesto, rotulos, escolhas in (
            (GESTO_DO_EFEITO_HAPTICO, formas.ROTULOS, formas.ESCOLHAS),
            (GESTO_DO_EFEITO_IMERSAO, _ROTULOS_DA_IMERSAO, padroes.ESCOLHAS)):
        _listas = _re.findall(
            r'<select class="vib-efeito" data-gesto="' + gesto + r'"[^>]*>(.*?)</select>',
            corpo, flags=_re.S)
        exigir(len(_listas) == len(MESA),
               f"a lista {gesto!r} não está nas {len(MESA)} colunas (achei {len(_listas)})")
        for opcoes in _listas:
            _valores = _re.findall(r'<option value="([^"]+)"[^>]*>([^<]+)</option>', opcoes)
            exigir(tuple(v for v, _r in _valores) == tuple(escolhas)
                   and [r for _v, r in _valores] == [rotulos[c] for c in escolhas],
                   f"as opções de {gesto!r} não são as da lista do produto, na ordem dela")
            exigir(_valores[:2] == [("do_estilo", "Do estilo"), ("sem_efeito", "Sem efeito")],
                   f"a lista {gesto!r} não abre com «Do estilo» e «Sem efeito»")
    exigir("grid-template-rows:minmax(var(--r-des),3fr) var(--r-nome) minmax(var(--r-forca),1fr)" in doc
           and "grid-template-rows:minmax(0,1fr)" in doc,
           "as faixas da grade da aba 05 voltaram a ter altura fixa: a coluna deixa de encher o quadro")
    _testar = _re.search(r'data-dica="([^"]*)">Testar agora</span>', corpo)
    exigir(_testar is not None,
           'o rótulo "Testar agora" saiu da coluna de rótulos — sem ele não há '
           "onde a dica morar")
    exigir(_testar is not None and DICA_DOS_VALORES_QUE_PASSAM in _testar.group(1),
           'a nota do Testar não está na dica do "Testar agora" — a 05-Q2 dela é '
           '*"As duas na dica"*')
    exigir(corpo.count(DICA_DOS_VALORES_QUE_PASSAM) == 1,
           "a nota do Testar aparece mais de uma vez na mesma tela")
    exigir('class="seg"' not in corpo and "data-forca=" not in corpo,
           "os botões da Força voltaram à tela — o desenho de 18/10 (r3b-05-12) "
           "os tirou: a Força é só o trilho com a porcentagem")

    _faixa = corpo.split('class="vib-estado"', 1)[-1].split(">", 1)[0]
    exigir("data-hef-recado" not in _faixa,
           "a faixa voltou a declarar lugar de recado — o piloto não põe mais "
           "frase na tela, e um endereço que ninguém lê é dado morto")
    exigir(".vib-estado .est.recibo{color:var(--green)}" in doc
           and ".vib-estado .est.recibo .sinal{color:var(--green)}" in doc,
           "o tom `recibo` da faixa não é verde — e verde é a cor que esta "
           "casa usa para o que deu certo em todas as dez abas")
    exigir("--orange" not in doc.split(".vib-estado .est.recibo", 1)[-1]
           .split("}", 2)[0],
           "o recibo da faixa ficou laranja — laranja é o `alerta`, e alerta "
           "sobre um clique que gravou ensina que o botão falha")

    _marcas = _re.compile(
        r'data-campo="([^"]+)"'
        r'|data-hef-alvo="([^"]+)"'
        r'|data-hef-classe="([^"]+)"'
        r'|data-hef-quando="([^"]+)"'
        r'|data-hef-atributo="([^"]+)"')

    def _enderecos(html):
        achados = set()
        for grupo in _marcas.findall(html):
            achados.add(next(x for x in grupo if x))
        return achados

    if len(blocos) == len(MESA):
        _por_lugar = {pref: _enderecos(html) for pref, html in blocos.items()}
        _padrao = _por_lugar[MESA[0]["pref"]]
        for c in MESA[1:]:
            _dele = _por_lugar[c["pref"]]
            exigir(_dele == _padrao,
                   f"o lugar {c['pref']} não tem os mesmos endereços do "
                   f"{MESA[0]['pref']} — faltam {sorted(_padrao - _dele)} e "
                   f"sobram {sorted(_dele - _padrao)}. O piloto pinta dentro do "
                   f"bloco daquele `data-controle`: um endereço a menos é dado "
                   f"dela chegando sem ter onde pousar; um a mais é pintura que "
                   f"nunca acontece")
        exigir(len(_padrao) >= 14,
               f"a régua dos quatro lugares mede {len(_padrao)} endereços e "
               f"eram 14 em 06/09 — ela ficou verde por VACUIDADE, que é o "
               f"jeito de esta guarda deixar de guardar")

    if falhas:
        raise SystemExit("ERRO em 05-vibracao — decisão dela desfeita:\n  "
                         + "\n  ".join(f"- {f}" for f in falhas))


if __name__ == "__main__":
    import os
    import shutil
    import tempfile

    _real = onde.saida()
    _prova = pathlib.Path(tempfile.mkdtemp(prefix="hefesto-prova-05-"))
    for _vizinha in _real.glob("*.html"):
        shutil.copy2(_vizinha, _prova / _vizinha.name)
    os.environ[onde._DESVIO] = str(_prova)
    n = monta("05-vibracao", "Vibração", MIOLO,
              CSS + CSS_DAS_MEDIDAS + FOLHA_DOS_28)
    _conferir(onde.pagina("05-vibracao.html").read_text())
    shutil.copyfile(_prova / "05-vibracao.html", _real / "05-vibracao.html")
    shutil.rmtree(_prova)
    print(f"05-vibracao: OK, {n} divs · {len(CONECTADOS)} conectado(s) "
          f"+ {len(MESA) - len(CONECTADOS)} lugar(es) vazio(s) · motores do mapa: "
          f'{ESQ["id"]} / {DIR["id"]}')
