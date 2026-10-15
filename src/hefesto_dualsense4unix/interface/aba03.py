import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import re  # noqa: E402
import onde  # noqa: E402
import monta as monta_  # noqa: E402  o MÓDULO, para ler CONECTADOS
from monta import CSS_GLIFO, MESA, R, cor_da_zona, glifo, monta, trava_do_nativo  # noqa: E402

sys.path.insert(0, str(R / "src"))
from hefesto_dualsense4unix.app.actions.trigger_specs import PRESETS  # noqa: E402

from hefesto_dualsense4unix.interface.pacotes.a03_gatilhos import (  # noqa: E402
    ALVO_DO_PLASTICO,
    CAMPO_DO_CHIP,
    CAMPO_DO_ESTILO,
    CAMPO_DO_PLASTICO,
    CLASSE_DO_CHIP,
    DICA_DO_MODO,
    PREFIXO_DA_DICA_DA_IMERSAO,
    PREFIXO_DA_DICA_DO_MODO,
    ROTULO_DO_JOGO_DECIDE,
    SEM_APARELHO_AQUI,
    SEM_IMERSAO,
    SEUS_EFEITOS,
    SEPARADOR_DOS_MEUS,
    TRAVESSAO,
    _cabeca_do_controle,
    _escapar,
    dica_da_imersao,
    descricao_do_modo,
    html_das_opcoes_de_imersao,
    sem_comentarios_de_css,
)
from hefesto_dualsense4unix.interface.pacotes.meus_efeitos import (  # noqa: E402
    PREFIXO_DO_MEU,
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

#: O «Desligado» do produto é, nesta tela, «Sem efeito» (ver `ROTULO_DO_JOGO_DECIDE`).
_ROTULO_DA_TELA = {p.name: ROTULO_DO_JOGO_DECIDE if p.name == "Off" else p.label
                   for p in PRESETS}

#: O «Montar do zero» (`Custom`) não é efeito de acionamento nesta tela: os ajustes saíram dela.
SEM_NA_LISTA = ("Custom",)
MODOS = [(_ROTULO_DA_TELA[p.name], DICA_DO_MODO[p.name]) for p in PRESETS
         if p.name not in SEM_NA_LISTA]
CHAVE_DO_MODO = {_ROTULO_DA_TELA[p.name]: p.name for p in PRESETS}

#: o gesto do botão do Modo automático; o pintor (`data-modo-da-aba` do quadro) é do pacote
GESTO_DO_MODO = "modo-dos-gatilhos"

#: o quadro que governa o botão: a grade, menos o DualSense, o «Controle» e os chips
GOVERNA = ".g2-grade > :is(.g2-gl:not(.g2-ds),.g2-rot,.g2-cel,.g2-sep:not(.g2-sep-cab))"
DICA_DO_AUTOMATICO = "O jogo manda; o estilo do perfil ajusta"

#: o que a cena do desenho mostra: (acionamento, imersão) por gatilho de cada controle
CENA = {
    "p1": {"e": ("Machine", "rajada-que-sobe-sozinha"),
           "d": ("Bow", "corda-que-treme-no-fim")},
    "p2": {"e": ("SemiAutoGun", "ferrolho-que-volta"),
           "d": ("Rigid", SEM_IMERSAO)},
    "p3": {"e": None, "d": None},
    "p4": {"e": None, "d": None},
}
ESTILO_DA_CENA = "FPS"
MEU_ACIONAMENTO = "Freio tardio"
MEU_IMERSAO = "Recuo do MK"

#: as barras da área de criar: (chave, rótulo, mínimo, máximo, valor, unidade)
BARRAS = [("inicio", "Início", 0, 9, 2, ""), ("fim", "Fim", 0, 9, 9, ""),
          ("forca", "Força", 0, 8, 4, ""), ("freq", "Frequência", 0, 255, 40, "Hz")]

GLIFO_DO_DUALSENSE = (
    '<svg class="gl" width="36" height="36" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    '<title>DualSense</title><g transform="translate(16 16.5) scale(.82) translate(-16 -16.8)" '
    'fill="none" stroke="currentColor"><path d="M8.5 7H23.5C26.6 7 28.4 8.9 29.1 12.2L30.6 22.6'
    'C31.1 26.6 27.9 28.6 25.6 26.6L21.4 21.9Q16 19.6 10.6 21.9L6.4 26.6C4.1 28.6 0.9 26.6 1.4 22.6'
    'L2.9 12.2C3.6 8.9 5.4 7 8.5 7Z" stroke-width="2.44" stroke-linejoin="round"/>'
    '<rect x="10.2" y="7" width="11.6" height="6.4" rx="1" stroke-width="1.9"/>'
    '<circle cx="12.4" cy="17" r="1.7" stroke-width="1.8"/><circle cx="19.6" cy="17" r="1.7" '
    'stroke-width="1.8"/><path d="M6.6 11.4V15.4M4.6 13.4H8.6" stroke-width="1.8" '
    'stroke-linecap="round"/><g fill="currentColor" stroke="none"><circle cx="25.4" cy="11.9" r="1"/>'
    '<circle cx="25.4" cy="14.9" r="1"/><circle cx="23.9" cy="13.4" r="1"/>'
    '<circle cx="26.9" cy="13.4" r="1"/></g></g></svg>')

CSS = CSS_GLIFO + """
  /* ---------- Gatilhos · a grade do todo ----------
     Uma coluna de glifos (L2, R2), uma de rótulos e UMA COLUNA POR CONTROLE da `MESA`.
     Cada célula leva o `data-controle` do seu lugar: o piloto pinta todas as que casam, e o
     clique chega ao pacote com o controle certo. `minmax(0,1fr)` e não `1fr`: o mínimo
     `auto` empurraria a coluna com o conteúdo mais largo. */
  .g2-grade{display:grid;grid-template-columns:44px 132px repeat(N_COLS,minmax(0,1fr));
    column-gap:14px;row-gap:16px;align-items:center;padding:8px 4px 6px}
  .g2-cab{display:flex;justify-content:center;min-height:36px}
  /* o chip do controle tem a largura, a altura e a fonte dos campos de baixo */
  .g2-cab > .cabeca,.g2-cab > .cabeca > span{display:flex;width:100%}
  .g2-cab .chip{width:100%;height:36px;box-sizing:border-box;display:flex;align-items:center;
    justify-content:center;border-radius:7px;font:600 12.5px 'Space Grotesk',system-ui,sans-serif;
    padding:0 11px;white-space:nowrap}
  .g2-cab .chip .pt{margin:0 6px}
  /* o lugar vazio mostra «Px · Desconectado», apagado, como no desenho do todo */
  .g2-cab[data-conectado="nao"] .chip{color:var(--comment);border:1px solid var(--border-sutil)}
  .g2-gl{grid-row:span 2;display:flex;align-items:center;justify-content:center;color:var(--fg);
    align-self:stretch;border-right:1px solid var(--border-sutil)}
  .g2-grade > .g2-gl.g2-ds{grid-column:1;grid-row:auto}
  .g2-grade .g2-gl.g2-r2{margin-top:6px}
  .sec-rot{font-size:12px;font-weight:600;color:var(--rot-campo);gap:7px}
  .g2-rot{display:flex;align-items:center;min-height:36px}
  .g2-rot .sec-rot{white-space:nowrap}
  .g2-cel{min-height:36px;display:flex;align-items:center;min-width:0}
  .g2-cel[data-conectado="nao"]{border-radius:7px;border:1px dashed var(--border-sutil);height:36px;
    box-sizing:border-box}
  .g2-cel[data-conectado="nao"] select{visibility:hidden;pointer-events:none}
  .g2-env{display:block;width:100%;min-width:0}
  .g2-acion,.g2-imersao,.g2-partir{width:100%;height:36px;padding:0 11px;border-radius:7px;
    font:500 12.5px 'Space Grotesk',system-ui,sans-serif;border:1px solid var(--linha);
    background:var(--app-bg);color:var(--texto-suave);cursor:pointer}
  .g2-acion{color:var(--fg);font-weight:600;border-color:var(--purple);background:var(--sel-bg)}
  .g2-imersao{border-color:rgba(255,121,198,.55);color:var(--fg)}
  .g2-acion:hover,.g2-imersao:hover,.g2-partir:hover{border-color:var(--comment)}
  .g2-sep{grid-column:1 / -1;height:1px;background:var(--border-sutil);margin:2px 0}
  /* a célula à esquerda dos chips: «Controle» e, abaixo, o estilo de jogo do perfil (só leitura) */
  .g2-grade > .g2-canto{grid-column:2;display:flex;flex-direction:column;align-items:flex-start;
    justify-content:center;gap:3px;height:auto;min-width:0;align-self:stretch}
  .g2-canto .g2-canto-rot{line-height:16px}
  .g2-canto .g2-estilo{display:flex;flex-wrap:wrap;justify-content:space-between;column-gap:8px;
    width:100%;font:500 12px/16px 'Space Grotesk',system-ui,sans-serif;color:var(--fg);cursor:help}
  .g2-canto .g2-estilo > span{white-space:nowrap}
  .g2-canto .g2-estilo-nome{color:var(--purple);font-weight:600;margin-left:auto}
  .g2-canto .g2-estilo-nome::after{content:attr(data-estilo)}
  /* sem estilo no perfil o pacote apaga o atributo (o piloto não escreve vazio num texto) */
  .g2-canto .g2-estilo:not(:has(.g2-estilo-nome[data-estilo])){display:none}
  @media (max-height:780px){.quadro .g2-grade{row-gap:8px;padding-top:4px}}
  /* criar efeitos novos */
  .g2-criar{margin-top:6px;flex:0 0 auto}
  .criar .criar-linha{display:flex;align-items:center;gap:12px;padding:12px 16px;flex-wrap:wrap;min-width:0}
  .criar .quadro-titulo{flex:0 0 auto;margin-right:4px}
  .criar .seg-criar{display:inline-flex;gap:4px;flex:0 0 auto}
  .criar .seg-criar label,.criar .meu{height:30px;padding:0 12px;border-radius:999px;
    font:500 12.5px/1 'Space Grotesk',system-ui,sans-serif;border:1px solid var(--linha);
    background:var(--app-bg);color:var(--texto-mudo);cursor:pointer;white-space:nowrap;
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
  .criar .nome-criar::placeholder{color:var(--texto-mudo)}
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
"""
CSS = CSS.replace("repeat(N_COLS,", f"repeat({len(MESA)},")


def _op_vazio(escolhido):
    """O `—` do lugar vazio: oferecido ao `escrever()` do piloto, e NÃO à lista.

    `hidden` o tira do menu que ela abre. Ele fica no `<select>` porque o piloto só escreve `—`
    onde ele existe: sem ele o lugar que esvazia guarda o efeito de quem saiu.
    """
    return (f'<option value="{TRAVESSAO}"'
            f'{" selected" if escolhido == TRAVESSAO else ""} disabled hidden>{TRAVESSAO}</option>')


def _grupo_dos_seus(nome, escolhido=""):
    valor = PREFIXO_DO_MEU + nome
    marca = " selected" if escolhido == valor else ""
    return (f'<optgroup label="{SEUS_EFEITOS}"><option value="{_escapar(valor)}"{marca}>'
            f'{_escapar(nome)}</option></optgroup>')


def opcoes_modo(escolhido):
    """As opções do acionamento: o `—`, os modos do produto e «Seus efeitos»."""
    modos = "".join(
        f'<option value="{CHAVE_DO_MODO[n]}"'
        f'{" selected" if CHAVE_DO_MODO[n] == escolhido else ""} title="{_escapar(d)}">{n}</option>'
        for n, d in MODOS)
    return _op_vazio(escolhido) + modos + _grupo_dos_seus(MEU_ACIONAMENTO, escolhido)


def opcoes_imersao(modo, escolhida):
    """As opções da imersão: as mesmas que o pacote monta, com a escolhida marcada.

    O `—` e «Seus efeitos» são os do desenho, não os do disco de quem gera a página.
    """
    cru = html_das_opcoes_de_imersao(modo)
    cru = re.sub(r"^<option value=\"" + TRAVESSAO + r"\"[^>]*>[^<]*</option>", "", cru)
    cru = re.sub(r'<optgroup label="' + SEUS_EFEITOS + r'">.*?</optgroup>', "", cru)
    alvo = f'<option value="{_escapar(escolhida)}"'
    if alvo in cru:
        cru = cru.replace(alvo, alvo + " selected", 1)
    return _op_vazio(escolhida) + cru + _grupo_dos_seus(MEU_IMERSAO)


def _celula_do_acionamento(pref, sig, vazio):
    """A célula do acionamento de um gatilho num controle: o campo com a dica que muda com ele."""
    modo = CENA[pref][sig][0] if not vazio else TRAVESSAO
    dica = SEM_APARELHO_AQUI if vazio else descricao_do_modo(modo)
    return (f'<div class="g2-cel" id="acion-{pref}-{sig}" data-controle="{pref}"{_marca(vazio)}>'
            f'<span class="g2-env" data-campo="{PREFIXO_DA_DICA_DO_MODO}{sig}" data-hef-alvo="atributo" '
            f'data-hef-atributo="data-dica" data-dica="{_escapar(dica)}">'
            f'<select class="g2-acion" data-gesto="modo" data-campo="modo-chave-{sig}" '
            f'data-hef-alvo="valor" data-lado="{sig}" aria-label="Efeito de acionamento">'
            f'{opcoes_modo(modo)}</select></span></div>')


def _celula_da_imersao(pref, sig, vazio):
    """A célula da imersão: a escolha é do acionamento da coluna, que o clique leva junto."""
    modo, imersao = CENA[pref][sig] if not vazio else (TRAVESSAO, TRAVESSAO)
    dica = SEM_APARELHO_AQUI if vazio else dica_da_imersao(imersao)
    return (f'<div class="g2-cel" data-controle="{pref}"{_marca(vazio)}>'
            f'<span class="g2-env" data-campo="{PREFIXO_DA_DICA_DA_IMERSAO}{sig}" data-hef-alvo="atributo" '
            f'data-hef-atributo="data-dica" data-dica="{_escapar(dica)}">'
            f'<select class="g2-imersao" data-gesto="imersao" data-campo="imersao-{sig}" '
            f'data-hef-alvo="valor" data-lado="{sig}" data-hef-forma="acion-{pref}-{sig}" '
            f'aria-label="Efeito de imersão">{opcoes_imersao(modo, imersao)}</select></span></div>')


def _marca(vazio):
    return ' data-conectado="nao"' if vazio else ""  # (noqa-acento) valor


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
        f'          <div class="g2-cab" data-controle="{c["pref"]}"{_marca(not c.get("conectado", True))}>'
        f'{_chip(c)}</div>' for c in MESA)


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
    acion = _linha("", classe, "Efeito de acionamento", "Como o gatilho resiste ao dedo",
                   _celula_do_acionamento, sig)
    imer = _linha("", classe, "Efeito de imersão", "O realismo que o acionamento ganha",
                  _celula_da_imersao, sig)
    return "\n".join([_glifo_do_gatilho(nome, classe), acion[1], acion[2], imer[1], imer[2]])


def _meus():
    return (f'<span class="meu" data-dica="Efeito de acionamento"><i style="--cor:var(--purple)"></i>'
            f'{_escapar(MEU_ACIONAMENTO)}</span>'
            f'<span class="meu" data-dica="Efeito de imersão"><i style="--cor:var(--pink)"></i>'
            f'{_escapar(MEU_IMERSAO)}</span>')


def _barra(chave, rotulo, de, ate, valor, unidade):
    uni = f' data-unidade="{unidade}"' if unidade else ""
    mostra = f"{valor} {unidade}".strip()
    return (f'<label class="g2-barra"><span class="g2-bn">{rotulo}</span>'
            f'<input type="range" data-linha="{chave}" min="{de}" max="{ate}" value="{valor}"{uni}>'
            f'<b>{mostra}</b></label>')


def _partir():
    ops = "".join(
        f'<option value="{p.name}"{" selected" if p.name == "Rigid" else ""}>'
        f'{p.label}</option>'
        for p in PRESETS if p.name not in ("Off", *SEM_NA_LISTA))
    return ('<select class="g2-partir" data-linha="partir" aria-label="Partir de" '
            f'data-dica="O ponto de partida">{ops}</select>')


ROTEIRO_DAS_BARRAS = (
    "<script>document.addEventListener('input',function(ev){var r=ev.target;"
    "if(!r||r.type!=='range'||!r.closest||!r.closest('.g2-barra'))return;var b=r.nextElementSibling;"
    "if(b)b.textContent=r.value+(r.dataset.unidade?' '+r.dataset.unidade:'');});</script>")

MIOLO = f'''
    <div class="quadro" data-modo-da-aba="{monta_.MODO_PERSONALIZADO}" data-campo="{GESTO_DO_MODO}"
         data-hef-alvo="atributo" data-hef-atributo="data-modo-da-aba">
      <div class="quadro-topo">
        <span class="quadro-titulo" data-dica="Uma coluna por controle; vale na hora">Gatilhos</span>
        {trava_do_nativo("nos gatilhos")}
        {monta_.modo_auto(GESTO_DO_MODO, governa=GOVERNA, dica=DICA_DO_AUTOMATICO)}
      </div>
      <div class="quadro-corpo">
        <div class="g2-grade">
          <div class="g2-gl g2-ds" aria-label="DualSense">{GLIFO_DO_DUALSENSE}</div>
          <div class="g2-canto" aria-label="Controle e estilo de jogo"><span class="sec-rot g2-canto-rot">Controle</span><span class="g2-estilo" data-dica="O estilo escolhido em Perfis. Só leitura"><span class="g2-estilo-rot">Estilo de jogo</span><span class="g2-estilo-nome" data-campo="{CAMPO_DO_ESTILO}" data-hef-alvo="atributo" data-hef-atributo="data-estilo" data-estilo="{ESTILO_DA_CENA}"></span></span></div>
{_chips()}
          <div class="g2-sep g2-sep-cab"></div>
{_bloco_do_gatilho("l2", "g2-l2", "e")}
          <div class="g2-sep"></div>
{_bloco_do_gatilho("r2", "g2-r2", "d")}
        </div>
      </div>
    </div>
    <div class="quadro criar g2-criar" id="criar-gatilhos">
      <div class="criar-linha">
        <span class="quadro-titulo" data-dica="O que você criar entra nas listas de cima">Criar efeitos novos</span>
        <span class="seg-criar" role="group" aria-label="Tipo"><label data-dica="Como o gatilho resiste"><input type="radio" name="tipo-criar" value="acionamento" data-linha="tipo" checked><span>Acionamento</span></label><label data-dica="O realismo por cima"><input type="radio" name="tipo-criar" value="imersao" data-linha="tipo"><span>Imersão</span></label></span>
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
    for g in ("modo", "imersao", "criar-efeito", "sentir", GESTO_DO_MODO):
        exigir(f'data-gesto="{g}"' in corpo,
               f"o endereço do gesto {g!r} sumiu do desenho — o clique some calado")
    exigir(corpo.count('data-gesto="modo"') == 2 * n and corpo.count('data-gesto="imersao"') == 2 * n,
           f"não há dois campos de acionamento e dois de imersão por controle ({n})")
    exigir(corpo.count('id="criar-gatilhos"') == 1
           and corpo.count('data-hef-forma="criar-gatilhos"') == 2,
           "o Criar e o Sentir não apontam para o quadro de criar: o gesto não leria as barras")
    exigir(corpo.count('data-hef-alvo="valor"') == 4 * n,
           "um campo de escolha do desenho não pinta por valor")

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
        exigir(f'data-controle="{pref}" data-conectado="nao"' in corpo,  # (noqa-acento) valor
               f"o lugar {pref.upper()} deixou de se dar por vazio")
        exigir(c["nome"] not in corpo, f"o nome do plástico {c['nome']!r} voltou a um lugar vazio")
        exigir(corpo.count(f'<option value="{TRAVESSAO}" selected disabled hidden>')
               == 4 * len(vazios), "um campo do lugar vazio não mostra o travessão")
    exigir(f'<option value="{TRAVESSAO}"' in corpo
           and len(re.findall(rf'<option value="{TRAVESSAO}"[^>]*\bdisabled\b', corpo))
           == corpo.count('<select class="g2-a') + corpo.count('<select class="g2-i'),
           "um campo de escolha não oferece `—` ao piloto")
    exigir('[data-conectado="nao"] select' in doc,  # (noqa-acento) valor
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
        exigir(corpo.count(f'data-campo="{PREFIXO_DA_DICA_DO_MODO}{_sig}"') == n
               and corpo.count(f'data-campo="{PREFIXO_DA_DICA_DA_IMERSAO}{_sig}"') == n,
               f"os embrulhos da dica do gatilho {_sig} não estão em todos os lugares")
        exigir(corpo.count('id="acion-') == 2 * n, "a célula do acionamento perdeu o `id` que a imersão leva")
    for _spec in PRESETS:
        if _spec.name not in SEM_NA_LISTA:
            exigir(f'<option value="{_spec.name}"' in corpo,
                   f"o modo {_spec.name} perdeu o `value` — o clique iria sem contrato")
    exigir('value="Custom"' not in corpo, "o «Montar do zero» voltou à lista do acionamento")
    exigir(f'data-campo="{CAMPO_DO_ESTILO}"' in corpo, "o estilo do perfil perdeu o endereço")

    for chave in ("tipo", "partir", "nome", "inicio", "fim", "forca", "freq"):
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
          f"+ {len(MESA) - len(monta_.CONECTADOS)} lugar(es) vazio(s) · {len(MODOS)} modos")
