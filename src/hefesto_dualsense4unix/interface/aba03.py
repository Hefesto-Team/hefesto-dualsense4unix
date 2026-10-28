import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import re
import onde
import mapa as _mapa
import monta as monta_
from monta import CSS_GLIFO, MESA, R, cor_da_zona, glifo, monta, trava_do_nativo

sys.path.insert(0, str(R / "src"))
from hefesto_dualsense4unix.app.actions.trigger_specs import PRESETS

from hefesto_dualsense4unix.interface.pacotes.a03_gatilhos import (
    ALVO_DO_PLASTICO,
    CAMPO_DA_FORCA,
    CAMPO_DO_CHIP,
    CAMPO_DO_ESTILO,
    CAMPO_DO_PLASTICO,
    CLASSE_DO_CHIP,
    DEGRAUS_DA_FORCA,
    DICA_DO_MODO,
    PREFIXO_DA_DICA_DA_IMERSAO,
    PREFIXO_DA_FAMILIA_DA_IMERSAO,
    PREFIXO_DO_SEU_ACIONAMENTO,
    SEM_APARELHO_AQUI,
    SEM_IMERSAO,
    SEUS_EFEITOS,
    TRAVESSAO,
    _cabeca_do_controle,
    _escapar,
    dica_da_imersao,
    familia_da_imersao,
    html_das_opcoes_de_imersao,
    nivel_da_forca,
    sem_comentarios_de_css,
)
from hefesto_dualsense4unix.profiles.efeitos_de_imersao import FAMILIAS_DA_PAGINA
from hefesto_dualsense4unix.interface.mapa import glifo_do_controle
from hefesto_dualsense4unix.profiles.schema import RUMBLE_CUSTOM_MULT_MAX
from hefesto_dualsense4unix.interface.pacotes.meus_efeitos import (
    PREFIXO_DO_MEU,
    SEPARADOR_DOS_MEUS,
    TETO_DO_NOME,
)

GL = monta_.GLIFO_DA_SECAO

_SEM_DICA = [p.name for p in PRESETS if p.name not in DICA_DO_MODO]
_DICA_ORFA = [n for n in DICA_DO_MODO if n not in {p.name for p in PRESETS}]
if _SEM_DICA or _DICA_ORFA:
    raise SystemExit(
        f"ERRO: `DICA_DO_MODO` e `app/actions/trigger_specs.PRESETS` não falam dos\n"
        f"mesmos modos. Sem dica: {_SEM_DICA or 'nenhum'} · dica órfã: "
        f"{_DICA_ORFA or 'nenhuma'}.\n"
        f"Um modo novo no produto precisa da frase que ESTA tela mostra; uma dica\n"
        f"órfã é texto de um modo que o produto não tem mais.")

ROT = {p.name: p.label for p in PRESETS}

SEM_NA_LISTA = ("Custom",)

GESTO_DO_MODO = "modo-dos-gatilhos"

GOVERNA = ".g2-grade > :is(.g2-gl:not(.g2-ds),.g2-rot,.g2-cel,.g2-sep:not(.g2-sep-cab))"
DICA_DO_AUTOMATICO = "O jogo manda; o estilo do perfil ajusta"

CENA = {
    "p1": {"e": ("Machine", "rajada-que-sobe-sozinha"),
           "d": ("Bow", "corda-que-estica")},
    "p2": {"e": ("Weapon", "ferrolho-que-volta"),
           "d": ("Off", SEM_IMERSAO)},
    "p3": {"e": None, "d": None},
    "p4": {"e": None, "d": None},
}
ESTILO_DA_CENA = "FPS"
MEU_ACIONAMENTO = "Freio tardio"
MEU_IMERSAO = "Recuo do MK"

BARRAS = [("inicio", "Início", 0, 9, 2, ""), ("fim", "Fim", 0, 9, 9, ""),
          ("forca", "Força", 0, 8, 4, ""), ("freq", "Frequência", 0, 255, 40, "Hz")]

BASE_DO_CRIADOR = "Machine"
PARAMETROS_DA_BARRA = {"inicio": {"start", "position"}, "fim": {"end"},
                       "forca": {"force", "strength", "amplitude"}, "freq": {"frequency"}}


def _barras_que_a_base_usa():
    """A regra que esconde a barra que a base escolhida em «Partir de» não manda ao gatilho."""
    regras = []
    for p in PRESETS:
        if p.name in ("Off", *SEM_NA_LISTA):
            continue
        nomes = {getattr(c, "name", c) for c in p.params}
        for chave, aceitos in PARAMETROS_DA_BARRA.items():
            if not nomes & aceitos:
                regras.append(f'  .g2-criar:has(.g2-partir option[value="{p.name}"]:checked) '
                              f'.g2-barra:has([data-linha="{chave}"]){{display:none}}\n')
    return "".join(regras)


GLIFO_DO_DUALSENSE = _mapa.silhueta_do_dualsense(40)

from hefesto_dualsense4unix.interface.pacotes.a03_gatilhos import DO_ESTILO  # noqa: E402

TETO_DA_INTENSIDADE = round(RUMBLE_CUSTOM_MULT_MAX * 100)
PASSO_DA_INTENSIDADE = 5
ROTULO_DA_INTENSIDADE = "Intensidade do gatilho"
DICA_DA_INTENSIDADE = ("Abaixo de 100% o efeito do gatilho fica mais fraco; acima, o fraco é reforçado, "
                       "até o máximo do gatilho")
CAMPO_DA_INTENSIDADE = "intensidade-do-gatilho"
INTENSIDADE_DA_CENA = {"p1": 120, "p2": 70}
GESTO_DA_INTENSIDADE = "intensidade-do-gatilho"
ONDE_ENTRA_A_INTENSIDADE = "acima"
GLIFO_DA_INTENSIDADE = glifo_do_controle()

FORCA_DA_CENA = {"p1": {"l2": 96, "r2": 200}, "p2": {"l2": 0, "r2": 0}}

CSS = CSS_GLIFO + """  .g2-grade{display:grid;grid-template-columns:44px 132px repeat(N_COLS,minmax(0,1fr));
    column-gap:14px;row-gap:16px;align-items:center;padding:8px 4px 6px}
  .g2-cab{display:flex;justify-content:center;min-height:36px}
  .g2-forca{display:flex;justify-content:center;align-items:flex-end;gap:22px;height:58px;
    box-sizing:border-box;padding:4px 0 2px;border-radius:7px;border:1px solid var(--border-forte)}
  .g2-forca .escada{display:flex;flex-direction:column;align-items:center;gap:3px}
  .g2-forca .degraus{display:flex;align-items:flex-end;gap:3px;height:36px}
  .g2-forca .degraus i{display:block;width:6px;border-radius:2px;background:var(--border-forte)}
  .g2-forca .escada b{font:600 11px/13px 'Space Grotesk',system-ui,sans-serif;color:var(--fg)}
  .g2-forca[data-conectado="nao"]{border:1px dashed var(--border-sutil)}
  .g2-forca[data-conectado="nao"] .degraus i{background:var(--border-sutil)}
  .g2-cab > .cabeca,.g2-cab > .cabeca > span{display:flex;width:100%}
  .g2-cab .chip{width:100%;height:36px;box-sizing:border-box;display:flex;align-items:center;
    justify-content:center;border-radius:7px;font:600 12.5px 'Space Grotesk',system-ui,sans-serif;
    padding:0 11px;white-space:nowrap}
  .g2-cab .chip .pt{margin:0 6px}
  .g2-cab[data-conectado="nao"] .chip{color:var(--fg);border:1px solid var(--border-sutil)}
  .g2-gl{grid-row:span 1;display:flex;align-items:center;justify-content:center;color:var(--fg);
    align-self:stretch;border-right:1px solid var(--border-sutil)}
  .g2-grade > .g2-gl.g2-ds{grid-column:1;grid-row:span 1;border-right:0}
  .g2-grade > .g2-rot-forca{grid-column:2}
  .g2-grade .g2-gl.g2-r2{margin-top:6px}
  .sec-rot{font-size:12px;font-weight:600;color:var(--rot-campo);gap:7px}
  .g2-rot{display:flex;align-items:center;min-height:36px}
  .g2-rot .sec-rot{white-space:nowrap}
  .g2-cel{min-height:36px;display:flex;align-items:center;min-width:0}
  .g2-cel[data-conectado="nao"]{border-radius:7px;border:1px dashed var(--border-sutil);height:36px;
    box-sizing:border-box}
  .g2-cel[data-conectado="nao"] select{visibility:hidden;pointer-events:none}
  .g2-env{display:block;width:100%;min-width:0}
  .g2-imersao,.g2-partir{width:100%;height:36px;padding:0 11px;border-radius:7px;
    font:500 12.5px 'Space Grotesk',system-ui,sans-serif;border:1px solid var(--linha);
    background:var(--app-bg);color:var(--texto-suave);cursor:pointer}
  .g2-imersao{border-color:rgba(255,121,198,.55);color:var(--fg)}
  .g2-imersao:hover,.g2-partir:hover{border-color:var(--comment)}
  .g2-sep{grid-column:1 / -1;height:1px;background:var(--border-sutil);margin:2px 0}
  .g2-grade > .g2-canto{grid-column:2;display:flex;flex-direction:column;align-items:flex-start;
    justify-content:center;gap:3px;height:auto;min-width:0;align-self:stretch}
  .g2-canto .g2-estilo{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;column-gap:8px;
    width:100%;font:500 12px/16px 'Space Grotesk',system-ui,sans-serif;color:var(--fg);cursor:help}
  .g2-canto .g2-estilo > span{white-space:nowrap}
  .g2-canto .g2-estilo-nome{color:var(--purple);font-weight:600;margin-left:auto}
  .g2-canto .g2-estilo-nome::after{content:attr(data-estilo)}
  .g2-gl.g2-int-gl{grid-row:auto;border-right:0}
  .g2-int{display:grid;grid-template-columns:36px minmax(0,1fr) 44px 8px;align-items:center;gap:8px;
    height:36px;min-width:0}
  .g2-int .lado{height:36px;width:36px;box-sizing:border-box;border-radius:7px;display:flex;
    align-items:center;justify-content:center;padding:0;border:1px solid var(--orange);
    background:rgba(255,184,108,.1);color:var(--orange);cursor:default}
  .g2-int .num{text-align:right;font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--fg)}
  .g2-int .teto{font-size:10.5px;color:var(--fg);font-family:'JetBrains Mono',monospace;
    text-align:right;justify-self:end;white-space:nowrap}
  .g2-int .trilho.arrasta{appearance:none;-webkit-appearance:none;width:100%;height:5px;padding:0;
    margin:0;border:0;border-radius:3px;background:var(--border-forte);cursor:grab}
  .g2-int .trilho.arrasta:active{cursor:grabbing}
  .g2-int .trilho.arrasta::-webkit-slider-runnable-track{height:5px;border-radius:3px;
    background:transparent}
  .g2-int .trilho.arrasta::-webkit-slider-thumb{appearance:none;-webkit-appearance:none;width:12px;
    height:12px;border-radius:50%;background:var(--purple);border:2px solid var(--panel);margin-top:-4px}
  .g2-int .trilho.arrasta:focus-visible{outline:2px solid var(--purple);outline-offset:3px}
  .g2-int .trilho.arrasta{height:9px;border-radius:5px;background:var(--sel-bg)}
  .g2-int .trilho.arrasta::-webkit-slider-runnable-track{height:9px;border-radius:5px}
  .g2-int .trilho.arrasta::-webkit-slider-thumb{width:17px;height:17px;background:var(--pink);margin-top:-4px}
  .g2-int .num{font-weight:700;color:var(--pink)}
  .g2-int[data-conectado="nao"] > *{display:none}
  .g2-int[data-conectado="nao"]::after{content:"—";color:var(--linha);display:flex;
    align-items:center;justify-content:center;grid-column:1/-1;width:100%;height:100%}
  @media (max-height:830px){.quadro .g2-grade{row-gap:8px;padding-top:4px}}
  .g2-criar{margin-top:6px;flex:0 0 auto}
  .criar .criar-linha{display:flex;align-items:center;gap:12px;padding:12px 16px;flex-wrap:wrap;min-width:0}
  .criar .quadro-titulo{flex:0 0 auto;margin-right:4px}
  .criar .seg-criar{display:inline-flex;gap:4px;flex:0 0 auto}
  .criar .seg-criar label,.criar .meu{height:30px;padding:0 12px;border-radius:999px;
    font:500 12.5px/1 'Space Grotesk',system-ui,sans-serif;border:1px solid var(--linha);
    background:var(--app-bg);color:var(--fg);cursor:pointer;white-space:nowrap;
    display:inline-flex;align-items:center;gap:7px;box-sizing:border-box}
  .criar .seg-criar input{position:absolute;opacity:0;pointer-events:none;width:1px;height:1px}
  .criar .seg-criar label:has(input:checked){border-color:var(--purple);background:var(--sel-bg);
    color:var(--fg);font-weight:600}
  .criar .seg-criar label:hover:not(:has(input:checked)),.criar .meu:hover{border-color:var(--comment);
    color:var(--texto-suave)}
  .criar .seg-criar label:has(input:focus-visible){outline:2px solid var(--cyan,#8be9fd);outline-offset:2px}
  .g2-criar .g2-partir{width:190px;flex:0 0 auto;height:30px}
  .criar .nome-criar{height:30px;width:150px;flex:0 0 auto;padding:0 11px;border-radius:7px;
    border:1px solid var(--linha);background:var(--app-bg);color:var(--fg);
    font:500 12.5px 'Space Grotesk',system-ui,sans-serif}
  .criar .nome-criar::placeholder{color:var(--fg)}
  .criar .btn-criar{height:30px;padding:0 14px;border-radius:7px;border:1px solid var(--purple);
    background:rgba(189,147,249,.12);color:var(--purple);font:600 12.5px/1 'Space Grotesk',system-ui,sans-serif;
    cursor:pointer;flex:0 0 auto}
  .criar .btn-criar:hover{background:rgba(189,147,249,.22)}
  .criar .meus{display:flex;gap:6px;margin-left:auto;align-items:center;min-width:0;flex-wrap:wrap}
  .criar .meu{color:var(--texto-suave);cursor:help}
  .criar .meu i{width:7px;height:7px;border-radius:50%;background:var(--cor,var(--purple));flex:0 0 auto}
  .g2-barras{display:flex;align-items:center;gap:26px;padding:4px 16px 14px}
  .g2-barra{display:flex;align-items:center;gap:10px;flex:1 1 0;min-width:0}
  .g2-barra .g2-bn{font-size:12px;font-weight:600;color:var(--rot-campo);white-space:nowrap}
  .g2-barra input{flex:1;min-width:60px;accent-color:var(--purple);height:24px}
  .g2-barra b{font:700 12px 'JetBrains Mono',monospace;color:var(--fg);min-width:40px;text-align:left}
  .g2-sentir{height:30px;padding:0 14px;border-radius:7px;border:1px solid var(--pink);
    background:rgba(255,121,198,.1);color:var(--pink);font:600 12.5px/1 'Space Grotesk',system-ui,sans-serif;
    cursor:pointer;flex:0 0 auto}
  .g2-sentir:hover{background:rgba(255,121,198,.2)}
  .quadro-topo .modo-auto{margin-left:auto}
  .g2-env{position:relative}
  .g2-fam{position:absolute;left:11px;top:0;height:36px;display:flex;align-items:center;
    font:600 11px/1 'Space Grotesk',system-ui,sans-serif;color:var(--purple);pointer-events:none}
  .g2-fam:not([data-fam]){display:none}
  .g2-fam::before{content:attr(data-fam)}
  .g2-fam::after{content:"";width:1px;height:14px;background:var(--border-sutil);margin-left:7px}
  @media (max-height:830px){.criar .criar-linha{padding:8px 16px;row-gap:6px}.g2-barras{padding-bottom:8px}}
"""
CSS = CSS.replace("repeat(N_COLS,", f"repeat({len(MESA)},")
CSS += "".join(
    f'\n  .g2-fam[data-fam="{f}"] + .g2-imersao{{padding-left:{29 + round(len(f) * 6.6)}px}}'
    for f in FAMILIAS_DA_PAGINA)
CSS += "".join(
    f"\n  .g2-forca .degraus i:nth-child({n}){{height:{round(36 * n / DEGRAUS_DA_FORCA)}px}}"
    for n in range(1, DEGRAUS_DA_FORCA + 1))
CSS += "".join(
    f'\n  .g2-forca:not([data-conectado="nao"]) .escada[data-nivel="{n}"] '
    f"i:nth-child(-n+{n}){{background:var(--purple)}}"
    for n in range(1, DEGRAUS_DA_FORCA + 1)) + "\n"
CSS += _barras_que_a_base_usa()


def _op_vazio(escolhido):
    """O `—` do lugar vazio: oferecido ao `escrever()` do piloto, e NÃO à lista.

    `hidden` o tira do menu que ela abre. Ele fica no `<select>` porque o piloto só escreve `—`
    onde ele existe: sem ele o lugar que esvazia guarda o efeito de quem saiu.
    """
    return (f'<option value="{TRAVESSAO}"'
            f'{" selected" if escolhido == TRAVESSAO else ""} disabled hidden>{TRAVESSAO}</option>')


def _grupo_dos_seus(itens):
    """O grupo «Seus efeitos» do desenho: o que ela criou e o acionamento que ela guardou antes."""
    dentro = "".join(f'<option value="{_escapar(valor)}">{_escapar(nome)}</option>'
                     for valor, nome in itens)
    return f'<optgroup label="{SEUS_EFEITOS}">{dentro}</optgroup>'


def opcoes_imersao(escolhida):
    """As opções do efeito do gatilho: as mesmas que o pacote monta, com a escolhida marcada.

    O `—` e «Seus efeitos» são os do desenho, não os do disco de quem gera a página. O grupo leva
    os dois que o desenho guarda: o acionamento de antes e a imersão nova, na mesma lista.
    """
    cru = html_das_opcoes_de_imersao()
    cru = re.sub(r"^<option value=\"" + TRAVESSAO + r"\"[^>]*>[^<]*</option>", "", cru)
    cru = re.sub(r'<optgroup label="' + SEUS_EFEITOS + r'">.*?</optgroup>', "", cru)
    alvo = f'<option value="{_escapar(escolhida)}"'
    if alvo in cru:
        cru = cru.replace(alvo, alvo + " selected", 1)
    return _op_vazio(escolhida) + cru + _grupo_dos_seus(
        [(PREFIXO_DO_SEU_ACIONAMENTO + MEU_ACIONAMENTO, MEU_ACIONAMENTO),
         (PREFIXO_DO_MEU + MEU_IMERSAO, MEU_IMERSAO)])


def _celula_da_imersao(pref, sig, vazio):
    """A célula do efeito do gatilho: a única do gatilho, e o acionamento vem dentro do efeito.

    A família é a etiqueta à esquerda da caixa (`data-fam`, que o piloto pinta e apaga); a frase
    do efeito mora SÓ na dica da caixa e no `title` de cada opção.
    """
    imersao = CENA[pref][sig][1] if not vazio else TRAVESSAO
    dica = SEM_APARELHO_AQUI if vazio else dica_da_imersao(imersao)
    fam = "" if vazio else familia_da_imersao(imersao)
    atr_fam = f' data-fam="{_escapar(fam)}"' if fam else ""
    return (f'<div class="g2-cel{_off(vazio)}" data-controle="{pref}"{_marca(vazio)}>'
            f'<span class="g2-env" data-campo="{PREFIXO_DA_DICA_DA_IMERSAO}{sig}" data-hef-alvo="atributo" '
            f'data-hef-atributo="data-dica" data-dica="{_escapar(dica)}">'
            f'<i class="g2-fam" aria-hidden="true" data-campo="{PREFIXO_DA_FAMILIA_DA_IMERSAO}{sig}" '
            f'data-hef-alvo="atributo" data-hef-atributo="data-fam"{atr_fam}></i>'
            f'<select class="g2-imersao" data-gesto="imersao" data-campo="imersao-{sig}" '
            f'data-hef-alvo="valor" data-lado="{sig}" '
            f'aria-label="Efeito do gatilho">{opcoes_imersao(imersao)}</select></span></div>')


def _marca(vazio):
    return ' data-conectado="nao"' if vazio else ""


def _off(vazio):
    """A classe que o piloto põe no lugar que esvazia (passo `1b`): nascer com ela deixa o P2 que sai
    e o P3 que nasce vazio com a mesma classe. A folha lê só o `data-conectado`."""
    return " off" if vazio else ""


def _chip(c):
    """O cabeçalho da coluna. A borda de cor só sai para quem está na mesa.

    A marcação tem um dono só, o pacote: o produto escreve nos dois endereços que ela deixa.
    A cor se resolve aqui, com a régua estrita: `cor_da_zona` levanta num colorway que o
    desenho não tem. Num lugar vazio o chip diz «Px · Desconectado», apagado.
    """
    vivo = c.get("conectado", True)
    return _cabeca_do_controle(
        c["jogador"], c["nome"] if vivo else "", c["via"] if vivo else "",
        cor_da_zona(c["cor"]) if vivo else "", conectado=bool(vivo))


def _chips():
    return "\n".join(
        f'          <div class="g2-cab{_off(not c.get("conectado", True))}" data-controle="{c["pref"]}"{_marca(not c.get("conectado", True))}>'
        f'{_chip(c)}</div>' for c in MESA)


def _escada(c, gatilho):
    """Os degraus de UM gatilho: o nível nasce da cena, e o pacote o reescreve a cada tique."""
    vivo = c.get("conectado", True)
    nivel = nivel_da_forca(FORCA_DA_CENA.get(c["pref"], {}).get(gatilho, 0)) if vivo else 0
    degraus = "<i></i>" * DEGRAUS_DA_FORCA
    return (f'<span class="escada" data-campo="{CAMPO_DA_FORCA[gatilho]}" data-hef-alvo="atributo" '
            f'data-hef-atributo="data-nivel" data-nivel="{nivel}">'
            f'<span class="degraus">{degraus}</span><b>{gatilho.upper()}</b></span>')


def _forcas():
    """A linha da força do aperto: o L2 e o R2 de cada lugar da `MESA`."""
    celulas = "\n".join(
        f'          <div class="g2-forca{_off(not c.get("conectado", True))}" data-controle="{c["pref"]}"'
        f'{_marca(not c.get("conectado", True))}>{_escada(c, "l2")}{_escada(c, "r2")}</div>'
        for c in MESA)
    return ('          <div class="g2-rot g2-rot-forca"><span class="sec-rot" data-dica="O quanto cada gatilho '
            'está apertado agora">Força do aperto</span></div>\n' + celulas)


def _celula_da_intensidade(c):
    """A linha de UM controle: o ícone, o trilho de 0 a 200, o número e o `%`.

    O trilho é um `<input type=range>` como o da 05, e o `value` dele é o que o piloto lê no
    `change` e manda ao gesto :data:`GESTO_DA_INTENSIDADE`. O lugar vazio tem a mesma estrutura e
    o travessão no número: o que ele não pode ter é um número afirmado.
    """
    vivo = c.get("conectado", True)
    pct = INTENSIDADE_DA_CENA.get(c["pref"], 100) if vivo else 0
    return (f'<div class="g2-int{_off(not vivo)}" data-controle="{c["pref"]}"{_marca(not vivo)}>'
            f'<span class="lado on" role="img" aria-label="Os dois gatilhos" '
            f'data-dica="O L2 e o R2 deste controle">{GLIFO_DA_INTENSIDADE}</span>'
            f'<input class="trilho arrasta" type="range" min="0" max="{TETO_DA_INTENSIDADE}" '
            f'step="{PASSO_DA_INTENSIDADE}" value="{pct}" '
            f'data-papel="{GESTO_DA_INTENSIDADE}" data-campo="{CAMPO_DA_INTENSIDADE}" '
            f'data-hef-alvo="valor" title="{DICA_DA_INTENSIDADE}">'
            f'<span class="num" data-campo="{CAMPO_DA_INTENSIDADE}-pct">{TRAVESSAO if not vivo else pct}</span>'
            f'<span class="teto">%</span></div>')


def _intensidades():
    """A linha «Intensidade do gatilho»: o ícone vazio da coluna 1, o rótulo e uma célula por lugar."""
    celulas = "\n".join("          " + _celula_da_intensidade(c) for c in MESA)
    return ('          <div class="g2-gl g2-int-gl" aria-hidden="true"></div>\n'
            f'          <div class="g2-rot"><span class="sec-rot" data-dica="{DICA_DA_INTENSIDADE}">'
            f'{ROTULO_DA_INTENSIDADE}</span></div>\n' + celulas)


def _linha(glifo_html, classe, rotulo, dica, fabrica, lado):
    """Um rótulo e uma célula por controle da `MESA`."""
    rot = (f'          <div class="g2-rot"><span class="sec-rot" data-dica="{dica}">{rotulo}</span></div>')
    celulas = "\n".join(
        "          " + fabrica(c["pref"], lado, not c.get("conectado", True)) for c in MESA)
    return (glifo_html, rot, celulas)


def _glifo_do_gatilho(nome, classe):
    return (f'          <div class="g2-gl {classe}" aria-label="{nome.upper()}">'
            f'{glifo(nome, tam=GL)}</div>')


def _bloco_do_gatilho(nome, classe, sig):
    imer = _linha("", classe, "Efeito do gatilho", "O que o gatilho faz no jogo, pelo nome do que acontece",
                  _celula_da_imersao, sig)
    return "\n".join([_glifo_do_gatilho(nome, classe), imer[1], imer[2]])


def _meus():
    return (f'<span class="meu" data-dica="Efeito do gatilho"><i style="--cor:var(--pink)"></i>'
            f'{_escapar(MEU_ACIONAMENTO)}</span>'
            f'<span class="meu" data-dica="Efeito do gatilho"><i style="--cor:var(--pink)"></i>'
            f'{_escapar(MEU_IMERSAO)}</span>')


def _barra(chave, rotulo, de, ate, valor, unidade):
    uni = f' data-unidade="{unidade}"' if unidade else ""
    mostra = f"{valor} {unidade}".strip()
    return (f'<label class="g2-barra"><span class="g2-bn">{rotulo}</span>'
            f'<input type="range" data-linha="{chave}" data-gesto="sentir" data-hef-forma="criar-gatilhos" min="{de}" max="{ate}" value="{valor}"{uni}>'
            f'<b>{mostra}</b></label>')


def _partir():
    ops = "".join(
        f'<option value="{p.name}"{" selected" if p.name == BASE_DO_CRIADOR else ""}>'
        f'{p.label}</option>'
        for p in PRESETS if p.name not in ("Off", *SEM_NA_LISTA))
    return (f'<select class="g2-partir" data-linha="partir" data-gesto="sentir" data-hef-forma="criar-gatilhos" aria-label="Partir de" '
            f'data-dica="O ponto de partida">{ops}</select>')


ROTEIRO_DAS_BARRAS = (
    "<script>document.addEventListener('input',function(ev){var r=ev.target;"
    "if(!r||r.type!=='range'||!r.closest||!r.closest('.g2-barra'))return;var b=r.nextElementSibling;"
    "if(b)b.textContent=r.value+(r.dataset.unidade?' '+r.dataset.unidade:'');});</script>")

def _miolo(entra=ONDE_ENTRA_A_INTENSIDADE):
    """O miolo da aba. `entra` põe a «Intensidade do gatilho» `acima` (sob os chips) ou `abaixo` (depois do R2)."""
    assert entra in ("acima", "abaixo"), entra
    linha = _intensidades()
    sob_os_chips = linha if entra == "acima" else ""
    depois_do_r2 = ('          <div class="g2-sep"></div>\n' + linha) if entra == "abaixo" else ""
    return f'''
    <div class="quadro" data-modo-da-aba="{monta_.MODO_PERSONALIZADO}" data-campo="{GESTO_DO_MODO}"
         data-hef-alvo="atributo" data-hef-atributo="data-modo-da-aba">
      <div class="quadro-topo">
        <span class="quadro-titulo" data-dica="Uma coluna por controle; vale na hora">Gatilhos</span>
        {trava_do_nativo("nos gatilhos")}
        {monta_.modo_auto(GESTO_DO_MODO, governa=GOVERNA, dica=DICA_DO_AUTOMATICO)}
      </div>
      <div class="quadro-corpo">
        <div class="g2-grade">
{_forcas()}
          <div class="g2-gl g2-ds" aria-label="DualSense">{GLIFO_DO_DUALSENSE}</div>
          <div class="g2-canto" aria-label="Estilo de jogo"><span class="g2-estilo" data-dica="O estilo escolhido em Perfis"><span class="sec-rot g2-estilo-rot">Estilo de jogo</span><span class="g2-estilo-nome" data-campo="{CAMPO_DO_ESTILO}" data-hef-alvo="atributo" data-hef-atributo="data-estilo" data-estilo="{ESTILO_DA_CENA}"></span></span></div>
{_chips()}
{sob_os_chips}
          <div class="g2-sep g2-sep-cab"></div>
{_bloco_do_gatilho("l2", "g2-l2", "e")}
          <div class="g2-sep"></div>
{_bloco_do_gatilho("r2", "g2-r2", "d")}
{depois_do_r2}
        </div>
      </div>
    </div>
    <div class="quadro criar g2-criar" id="criar-gatilhos">
      <div class="criar-linha">
        <span class="quadro-titulo" data-dica="O que você criar entra na lista «Efeito do gatilho»">Criar efeitos novos</span>
        {_partir()}
        <input class="nome-criar" type="text" data-linha="nome" maxlength="{TETO_DO_NOME}" placeholder="Nome do efeito" aria-label="Nome do efeito">
        <button class="btn-criar" type="button" data-gesto="criar-efeito" data-hef-forma="criar-gatilhos" data-dica="Guarda e põe nas listas">Criar</button>
        <span class="meus" aria-label="Seus efeitos">{_meus()}</span>
      </div>
      <div class="g2-barras">
        {"".join(_barra(*b) for b in BARRAS)}
        <button class="g2-sentir" type="button" data-gesto="sentir" data-hef-forma="criar-gatilhos" data-dica="Toca o efeito no controle escolhido">Sentir</button>
      </div>
    </div>
    {ROTEIRO_DAS_BARRAS}
'''

MIOLO = _miolo()

_INICIO_DO_LUGAR = re.compile(r'<div\b[^>]*?\bdata-controle="(p\d+)"')

_TAG = re.compile(r"<[a-z]+\b[^>]*>")
_ATRIBUTO = re.compile(r'([a-z-]+)="([^"]*)"')


def _fim_do_bloco(corpo, ini):
    """Onde fecha o `<div>` que começa em `ini`."""
    fundo = 0
    for m in re.finditer(r"<div\b|</div>", corpo[ini:]):
        fundo += -1 if m.group(0) == "</div>" else 1
        if fundo == 0:
            return ini + m.end()
    raise SystemExit("ERRO: um bloco da aba 03 não fecha — o HTML saiu torto.")


def _enderecos_de_cada_lugar(corpo):
    """`pref` → {`data-campo`: o alvo, o atributo e a classe dele}, somando as células do lugar."""
    saida = {}
    for m in _INICIO_DO_LUGAR.finditer(corpo):
        trecho = corpo[m.start():_fim_do_bloco(corpo, m.start())]
        campos = saida.setdefault(m.group(1), {})
        for tag in _TAG.finditer(trecho):
            atr = dict(_ATRIBUTO.findall(tag.group(0)))
            if "data-campo" in atr:
                campos[atr["data-campo"]] = (atr.get("data-hef-alvo", ""),
                                             atr.get("data-hef-atributo", ""),
                                             atr.get("data-hef-classe", ""))
    return saida


def _conferir(doc):
    """As decisões do desenho do todo, conferidas NA SAÍDA."""
    corpo = doc.split('<div class="miolo">', 1)[-1].split('<div class="nota">', 1)[0]
    corpo = re.sub(r"<!--.*?-->", "", corpo, flags=re.S)
    if len(corpo) < 2000:
        raise SystemExit("ERRO: a régua não achou o miolo desta aba.")
    falhas = []

    def exigir(cond, oque):
        if not cond:
            falhas.append(oque)

    vazios = [c for c in MESA if not c.get("conectado", True)]
    n = len(MESA)
    for g in ("guardar", "em-todos", "pronto", "ajuste", "reenviar"):
        exigir(f'data-gesto="{g}"' not in corpo, f"o gesto {g!r} voltou ao desenho do todo")
    exigir('class="ajuda' not in corpo and 'class="ajustes' not in corpo,
           "o «?» ou a caixa de ajustes voltou ao desenho do todo")
    for g in ("imersao", "criar-efeito", "sentir", GESTO_DO_MODO):
        exigir(f'data-gesto="{g}"' in corpo,
               f"o endereço do gesto {g!r} sumiu do desenho — o clique some calado")
    exigir(corpo.count('data-gesto="imersao"') == 2 * n,
           f"não há dois campos de efeito por controle ({n}): um por gatilho")
    exigir('data-gesto="modo"' not in corpo and "acion-" not in corpo and 'g2-acion' not in doc,
           "o acionamento voltou ao desenho: o gatilho só tem o efeito")
    exigir(corpo.count('id="criar-gatilhos"') == 1
           and corpo.count('data-hef-forma="criar-gatilhos"') == 7,
           "o Criar, o Sentir e as barras não apontam para o quadro de criar: o gesto não leria as barras")
    exigir(corpo.count('data-hef-alvo="valor"') == 2 * n + n,
           "um campo de escolha, ou o trilho da intensidade, do desenho não pinta por valor")

    exigir(corpo.count(f'data-campo="{CAMPO_DO_CHIP}"') == n
           and corpo.count(f'data-campo="{CAMPO_DO_PLASTICO}"') == n,
           f"os {n} cabeçalhos não têm os dois endereços (chip e cor)")
    exigir(corpo.count(f'data-hef-alvo="{ALVO_DO_PLASTICO}"') == n,
           "o alvo que alcança a cor não está nos cabeçalhos")
    exigir(corpo.count(f'<div class="{CLASSE_DO_CHIP}" ') == n,
           f"o embrulho `.{CLASSE_DO_CHIP}` sumiu de algum cabeçalho")
    exigir(corpo.count("--plastico:") == n - len(vazios),
           "há cor de plástico cravada fora dos chips de quem está na mesa")
    exigir(not re.search(r'<span class="chip[^>]*--plastico', corpo),
           "o `<span>` do chip voltou a carregar a cor")
    exigir(corpo.count('class="chip plastico"') == n - len(vazios)
           and corpo.count('class="chip vazio"') == len(vazios),
           "a borda de cor saiu de quem está na mesa, ou ficou em quem não está")

    for c in vazios:
        pref = c["pref"]
        exigir(f'data-controle="{pref}" data-conectado="nao"' in corpo,
               f"o lugar {pref.upper()} deixou de se dar por vazio")
        exigir(c["nome"] not in corpo, f"o nome do plástico {c['nome']!r} voltou a um lugar vazio")
        exigir(corpo.count(f'<option value="{TRAVESSAO}" selected disabled hidden>')
               == 2 * len(vazios), "um campo do lugar vazio não mostra o travessão")
    exigir(f'<option value="{TRAVESSAO}"' in corpo
           and len(re.findall(rf'<option value="{TRAVESSAO}"[^>]*\bdisabled\b', corpo))
           == corpo.count('<select class="g2-i'),
           "um campo de escolha não oferece `—` ao piloto")
    exigir('[data-conectado="nao"] select' in doc,
           "a trava do lugar vazio sumiu do CSS")

    _por_lugar = _enderecos_de_cada_lugar(corpo)
    exigir(len(_por_lugar) == n, f"a régua achou {len(_por_lugar)} lugares e a `MESA` tem {n}")
    _todos = set().union(*_por_lugar.values()) if _por_lugar else set()
    for _pref in sorted(_por_lugar):
        _faltam = sorted(_todos - set(_por_lugar[_pref]))
        exigir(not _faltam, f"o lugar {_pref.upper()} não tem onde receber {_faltam}")
    for _campo in sorted(_todos):
        _assin = {c[_campo] for c in _por_lugar.values() if _campo in c}
        exigir(len(_assin) == 1, f"o endereço {_campo!r} tem alvos diferentes entre os lugares")

    for _sig in ("e", "d"):
        exigir(corpo.count(f'data-campo="{PREFIXO_DA_DICA_DA_IMERSAO}{_sig}"') == n,
               f"os embrulhos da dica do gatilho {_sig} não estão em todos os lugares")
    for _spec in PRESETS:
        if _spec.name not in (*SEM_NA_LISTA, "Off"):
            exigir(f'<option value="{_spec.name}"' in corpo,
                   f"o ponto de partida {_spec.name} perdeu o `value` — o Criar iria sem contrato")
    exigir('value="Custom"' not in corpo, "o «Montar do zero» voltou à lista de partida")
    exigir(f'data-campo="{CAMPO_DO_ESTILO}"' in corpo, "o estilo do perfil perdeu o endereço")
    for _sig in ("e", "d"):
        exigir(corpo.count(f'data-campo="{PREFIXO_DA_FAMILIA_DA_IMERSAO}{_sig}"') == n,
               f"a etiqueta de família do gatilho {_sig} não está em todos os lugares")
    exigir("g2-frase" not in corpo and "g2-frase" not in doc,
           "a frase do efeito voltou a ser texto embaixo da caixa: ela mora só na dica")
    exigir(corpo.count('<optgroup label="Golpe">') == 2 * n,
           "a lista do efeito do gatilho não abre em grupos por família")
    for _lista in re.findall(r'<select class="g2-imersao".*?</select>', corpo, re.S):
        exigir(re.search(r'^<select[^>]*>(?:<option[^>]*hidden>[^<]*</option>)?'
                         rf'<option value="{DO_ESTILO}"', _lista) is not None,
               "a lista do efeito do gatilho não abre com «Do estilo»")
        _sos = [g for g, d in re.findall(r'<optgroup label="([^"]+)">(.*?)</optgroup>', _lista, re.S)
                if g != SEUS_EFEITOS and d.count("<option") == 1]
        exigir(not _sos, f"grupo de um efeito só na lista do efeito do gatilho: {_sos}")
        _grupos = [g for g in re.findall(r'<optgroup label="([^"]+)">', _lista) if g != SEUS_EFEITOS]
        exigir(_grupos == list(FAMILIAS_DA_PAGINA),
               f"a lista do efeito do gatilho não tem os grupos do produto, na ordem: {_grupos}")
        for _grupo, _dentro in re.findall(r'<optgroup label="([^"]+)">(.*?)</optgroup>', _lista,
                                          re.S):
            if _grupo == SEUS_EFEITOS:
                continue
            for _valor in re.findall(r'<option value="([^"]+)"', _dentro):
                exigir(familia_da_imersao(_valor) == _grupo,
                       f"o efeito {_valor!r} está no grupo {_grupo!r} e a etiqueta dele diz "
                       f"{familia_da_imersao(_valor)!r}")
    for _fam, _sel in re.findall(r'<i class="g2-fam"[^>]*?(?:data-fam="([^"]*)")?></i>'
                                 r'<select class="g2-imersao"[^>]*>(.*?)</select>', corpo, re.S):
        _marcada = re.search(r'<option value="([^"]*)" selected', _sel)
        exigir(_marcada is None or _fam == familia_da_imersao(_marcada.group(1)),
               f"a etiqueta {_fam!r} ao lado da lista não é o grupo do efeito marcado")
        exigir(_marcada is None or _marcada.group(1) != DO_ESTILO or not _fam,
               "a etiqueta de família apareceu ao lado do «Do estilo»")
    exigir(re.search(r'class="g2-gl g2-ds"[^>]*>.*?</div>\s*<div class="g2-canto"', corpo, re.S)
           is not None and "g2-canto-rot" not in corpo,
           "o desenho do controle saiu do lado do «Estilo de jogo», ou o rótulo «Controle» voltou")
    exigir(f'value="{BASE_DO_CRIADOR}" selected' in corpo,
           "o criador do gatilho deixou de partir da Metralhadora")
    exigir(_barras_que_a_base_usa().strip() in doc and 'option[value="Resistance"]:checked) .g2-barra:has([data-linha="freq"])' in doc,
           "o criador mostra barra que a base escolhida não manda ao gatilho")
    exigir("g2-avtog" not in corpo and "g2-avtog" not in doc and "Avançado" not in corpo
           and "hef-gatilhos-avancado" not in doc,
           "a chave «Avançado» voltou ao título do quadro: o gatilho só tem o efeito")
    exigir("Como o gatilho faz" not in corpo and "g2-av" not in corpo,
           "a linha «Como o gatilho faz» voltou: o acionamento vem dentro do efeito")
    exigir("tipo-criar" not in corpo and 'data-linha="tipo"' not in corpo,
           "o tipo Acionamento voltou ao «Criar efeitos novos»: tudo o que ela cria é um efeito")
    exigir(f'value="{PREFIXO_DO_SEU_ACIONAMENTO}{MEU_ACIONAMENTO}"' in corpo
           and corpo.count('<optgroup label="Seus efeitos">') == 2 * n,
           "o acionamento que ela guardou saiu do grupo «Seus efeitos» da lista do efeito")
    for _campo in CAMPO_DA_FORCA.values():
        exigir(corpo.count(f'data-campo="{_campo}"') == n,
               f"a escada {_campo!r} não está em todos os {n} lugares")
    exigir(len(re.findall(r'class="g2-forca(?: off)?"', corpo)) == n,
           "a linha da força do aperto perdeu um lugar")
    for classe in ("g2-cab", "g2-cel", "g2-forca", "g2-int"):
        marcas = re.findall(rf'class="{classe}( off)?"[^>]*?(data-conectado="nao")?>', corpo)
        exigir(bool(vazios) and all(bool(off) == bool(vazio) for off, vazio in marcas),
               f"o `{classe}` vazio não tem a classe `off` que o piloto escreve, ou o cheio tem")
    exigir(corpo.index('class="g2-forca') < corpo.index('class="g2-cab'),
           "a força do aperto deixou de ficar acima de «Controle»")
    exigir(' id="' not in GLIFO_DO_DUALSENSE and "<title>" not in GLIFO_DO_DUALSENSE,
           "o ícone do DualSense voltou a ter `id` e colidiria com outro desenho")

    trilhos = re.findall(rf'<input class="trilho arrasta"[^>]*data-campo="{CAMPO_DA_INTENSIDADE}"[^>]*>', corpo)
    exigir(len(trilhos) == n, f"a intensidade não tem um trilho por lugar ({n}): há {len(trilhos)}")
    for t in trilhos:
        exigir('min="0"' in t and f'max="{TETO_DA_INTENSIDADE}"' in t and f'step="{PASSO_DA_INTENSIDADE}"' in t,
               f"o trilho da intensidade não vai de 0 a {TETO_DA_INTENSIDADE}, de {PASSO_DA_INTENSIDADE} em "
               f"{PASSO_DA_INTENSIDADE}: {t}")
        exigir(f'title="{DICA_DA_INTENSIDADE}"' in t, "o trilho da intensidade perdeu a dica de uma frase")
    exigir(all(f'data-papel="{GESTO_DA_INTENSIDADE}"' in t and "data-hef=" not in t for t in trilhos),
           "o trilho da intensidade não manda o gesto: sem `data-papel` ele só pinta e não grava")
    exigir(corpo.count(f">{ROTULO_DA_INTENSIDADE}<") == 1, "o rótulo da intensidade não aparece uma vez só")
    exigir(len(re.findall(r'class="g2-int(?: off)?"', corpo)) == n, "a linha da intensidade perdeu um lugar")
    exigir(corpo.count(f'data-campo="{CAMPO_DA_INTENSIDADE}-pct">{TRAVESSAO}<') == len(vazios),
           "o número da intensidade de um lugar vazio não é o travessão")
    _ordem = (corpo.index('class="g2-cab'), corpo.index('class="g2-int'),
              corpo.index('data-gesto="imersao"'))
    exigir((_ordem[0] < _ordem[1] < _ordem[2]) if ONDE_ENTRA_A_INTENSIDADE == "acima"
           else (_ordem[0] < _ordem[2] < _ordem[1]),
           f"a intensidade não está onde `ONDE_ENTRA_A_INTENSIDADE` ({ONDE_ENTRA_A_INTENSIDADE}) manda")

    for chave in ("partir", "nome", "inicio", "fim", "forca", "freq"):
        exigir(f'data-linha="{chave}"' in corpo, f"a área de criar perdeu o campo {chave!r}")
    exigir('id="criar-gatilhos"' in corpo and 'data-hef-forma="criar-gatilhos"' in corpo,
           "o botão Criar deixou de apontar para a área de criar")
    exigir('class="meus"' in corpo, "a área de criar perdeu onde pousam os efeitos criados")
    exigir(f"maxlength=\"{TETO_DO_NOME}\"" in corpo, "o nome do efeito perdeu o teto do dono")

    for _lado in CENA.values():
        for _par in _lado.values():
            if _par and _par[1] != SEM_IMERSAO:
                exigir(f'value="{_par[1]}" selected' in corpo,
                       f"a imersão {_par[1]!r} da cena não está marcada")

    _css = sem_comentarios_de_css(doc)
    exigir("minmax(0,1fr)" in _css, "a grade deixou de usar `minmax(0,1fr)`")
    for _chave in ("partir", "inicio", "fim", "forca", "freq"):
        _campo = re.search(rf'<(?:input|select)\b[^>]*data-linha="{_chave}"[^>]*>', corpo)
        exigir(_campo is not None and 'data-gesto="sentir" data-hef-forma="criar-gatilhos"'
               in _campo.group(0), f"o campo {_chave!r} do criador não toca o gatilho ao soltar")
    _controles = sorted({hex(ord(ch)) for ch in doc if ord(ch) < 32 and ch not in "\n\t"})
    exigir(not _controles, f"há caractere de controle no documento ({', '.join(_controles)})")
    exigir(SEPARADOR_DOS_MEUS not in corpo, "o separador antigo da lista de «Meus efeitos» voltou")

    if falhas:
        raise SystemExit("ERRO em 03-gatilhos — decisão dela desfeita:\n  "
                         + "\n  ".join(f"- {f}" for f in falhas if f))


if __name__ == "__main__":
    import os
    import shutil
    import tempfile

    _real = onde.saida()
    _prova = pathlib.Path(tempfile.mkdtemp(prefix="hefesto-prova-03-"))
    for _vizinha in _real.glob("*.html"):
        shutil.copy2(_vizinha, _prova / _vizinha.name)
    os.environ[onde._DESVIO] = str(_prova)
    n = monta("03-gatilhos", "Gatilhos", MIOLO, CSS)
    _conferir(onde.pagina("03-gatilhos.html").read_text())
    shutil.copyfile(_prova / "03-gatilhos.html", _real / "03-gatilhos.html")
    shutil.rmtree(_prova)
    print(f"03-gatilhos: OK, {n} divs · {len(monta_.CONECTADOS)} conectado(s) "
          f"+ {len(MESA) - len(monta_.CONECTADOS)} lugar(es) vazio(s)")
