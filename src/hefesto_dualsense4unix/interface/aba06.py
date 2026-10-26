"""A aba Navegação do todo: cada botão do controle com o que faz no computador."""
import csv
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import onde
from hefesto_dualsense4unix.core import acoes_do_gesto as _acoes_do_gesto
from hefesto_dualsense4unix.core.acoes_de_botao import (
    EIXO_DIREITO,
    EIXO_ESQUERDO,
    por_grupo,
)
from hefesto_dualsense4unix.core.acoes_de_botao import (
    padrao as _padrao_dos_botoes,
)
from hefesto_dualsense4unix.core.acoes_de_botao import (
    rotulo as rotulo_da_acao,
)
from hefesto_dualsense4unix.integrations.uinput_mouse import (
    DEFAULT_MOUSE_SPEED,
    DEFAULT_SCROLL_SPEED,
    MOUSE_SPEED_MAX,
    MOUSE_SPEED_MIN,
    SCROLL_SPEED_MAX,
    SCROLL_SPEED_MIN,
)
from hefesto_dualsense4unix.profiles.loader import MOLDES_DE_PERFIL
from monta import CONECTADOS, CSS_GLIFO, DADOS_DO_REPO, FIM_DA_ABA, MESA, glifo, monta
from pacotes.a06_navegacao import (
    DO_PERMITIR,
    PERMITIR,
    PERMITIR_INTERNA,
    PREFIXO_DA_LIBERDADE,
    PREFIXO_DA_VALIDADE,
    PREFIXO_DO_GESTO,
    PREFIXO_DO_SCRIPT,
    chips_da_fita,
    chips_de_quem_navega,
)

BLOCO_PARA_QUEM = "para-quem"
BLOCO_DOS_MEUS_PERFIS = "meus-perfis"

MESA_DA_FITA = CONECTADOS

PECAS = {p["id"]: p for p in csv.DictReader(
    [ln for ln in (DADOS_DO_REPO / "pecas-do-dualsense.csv").read_text().splitlines()
     if ln and not ln.startswith("#")])}

LINHA_DE_BOTAO = "linha-de-botao"

OPCOES_TECLADO = [
    "Só dentro do jogo",
    "Só fora do jogo",
    "Sempre",
    "Desativado",
]
TECLADO_PADRAO = OPCOES_TECLADO[1]

_CLIQUES_DO_TOUCHPAD = {
    "touchpad_left_press": "esquerda",
    "touchpad_middle_press": "meio",
    "touchpad_right_press": "direita",
}

PADRAO_DO_PONTE = f"molde:{MOLDES_DE_PERFIL[0].chave}"


def gl_de(pid):
    """O arquivo de glifo daquela peça, pela coluna `glifo` do mapa."""
    g = PECAS[pid]["glifo"]
    if g == "-":
        raise SystemExit(f"ERRO: a peça '{pid}' não tem glifo em pecas-do-dualsense.csv")
    return g


def nome_de(pid):
    """O nome curto da peça, lido do mapa."""
    p = PECAS[pid]
    if len(p["nome"]) <= 8:
        return p["nome"]
    for a in p["apelidos"].split("|"):
        if a.isalnum() and len(a) <= 3:
            return a
    return p["nome"]


def dir_de(pid):
    """A direção do d-pad, do `nome` do mapa: «D-pad cima» vira «cima»."""
    return PECAS[pid]["nome"].split()[-1].lower()


_nota = re.search(r"Clique ([^.]+)\.", PECAS["touchpad"]["nota"])
if not _nota or not all(p in _nota.group(1) for p in ("esquerd", "direit", "central")):
    raise SystemExit("ERRO: a nota do touchpad não declara mais os três cliques — "
                     "veja docs/data/pecas-do-dualsense.csv")


def _rot(txt):
    """O qualificador ao lado do glifo, como o desenho o escreve."""
    return f'<span class="rot-gl">{txt[:1].upper()}{txt[1:]}</span>'


def _um(pid, rot=None, nm=None, tam=18):
    """Um glifo do mapa, com o nome ao lado quando ele não se lê sozinho."""
    g = glifo(gl_de(pid), tam=tam)
    if nm is None:
        nm = PECAS[pid]["regiao"] not in ("face", "direcional")
    if nm:
        g += f'<span class="nm">{nome_de(pid)}</span>'
    if rot:
        g += _rot(rot)
    return g


ACOES_DO_PS = por_grupo("ps")
ACOES_GESTO = _acoes_do_gesto.por_grupo()
_PADRAO_DOS_BOTOES = {b: rotulo_da_acao(a) for b, a in _padrao_dos_botoes().items()}


def drop(grupos, escolhido, gesto="", linha="", campo="", classe="campo-linha"):
    """Um `<select>` de grupos; o `campo` é o endereço que o piloto pinta."""
    partes = []
    for rot, ops in grupos:
        op = "".join(f'<option{" selected" if o == escolhido else ""}>{o}</option>' for o in ops)
        partes.append(f'<optgroup label="{rot}">{op}</optgroup>' if rot else op)
    g = f' data-gesto="{gesto}"' if gesto else ""
    ln = f' data-linha="{linha}"' if linha else ""
    c = f' data-campo="{campo}" data-hef-alvo="valor"' if campo else ""
    return f'<select class="{classe}"{g}{ln}{c}>{"".join(partes)}</select>'


def simples(ops, escolhido, gesto, campo, dica):
    """Um `<select>` de opções planas, com gesto e endereço de pintura."""
    op = "".join(f'<option{" selected" if o == escolhido else ""}>{o}</option>' for o in ops)
    return (f'<select class="campo-linha" data-gesto="{gesto}" data-campo="{campo}"'
            f' data-hef-alvo="valor" data-dica="{dica}">{op}</select>')


def trilho(valor, minimo, maximo, gesto, dica):
    """Uma velocidade como barra arrastável, com o número ao lado (um endereço só)."""
    return (f'<div class="campo-num" data-dica="{dica}">'
            f'<input class="trilho" type="range" min="{minimo}" max="{maximo}" step="1"'
            f' value="{valor}" data-gesto="{gesto}" data-campo="{gesto}" data-hef-alvo="valor">'
            f'<span class="num" data-campo="{gesto}">{valor}</span></div>')


COLUNA_1 = [
    ("cross", "cross", True, None),
    ("circle", "circle", True, None),
    ("square", "square", True, None),
    ("triangle", "triangle", True, None),
    ("dpad_up", "dpad_up", False, dir_de("dpad_up")),
    ("dpad_down", "dpad_down", False, dir_de("dpad_down")),
    ("dpad_left", "dpad_left", False, dir_de("dpad_left")),
    ("dpad_right", "dpad_right", False, dir_de("dpad_right")),
    ("options", "options", True, None),
    ("share", "create", True, None),
    ("ps", "ps", True, None),
]
COLUNA_2 = [
    ("l1", "l1", True, None),
    ("r1", "r1", True, None),
    ("l2", "l2", True, None),
    ("r2", "r2", True, None),
    ("stick_l", "l3", True, "clique"),
    ("stick_l", EIXO_ESQUERDO, True, "direção"),
    ("stick_r", "r3", True, "clique"),
    ("stick_r", EIXO_DIREITO, True, "direção"),
    ("touchpad", "touchpad_left_press", False, _CLIQUES_DO_TOUCHPAD["touchpad_left_press"]),
    ("touchpad", "touchpad_middle_press", False, _CLIQUES_DO_TOUCHPAD["touchpad_middle_press"]),
    ("touchpad", "touchpad_right_press", False, _CLIQUES_DO_TOUCHPAD["touchpad_right_press"]),
]
LINHAS = [linha for _, linha, _, _ in COLUNA_1 + COLUNA_2]

DICA_DO_TOQUE = "O toque no touchpad move o cursor"
TOQUE_DO_TOUCHPAD = (f'<select class="campo-linha" disabled data-dica="{DICA_DO_TOQUE}"'
                     ' data-linha="touchpad_toque">'
                     f'<option selected>{rotulo_da_acao("__CURSOR__")}</option></select>')


def _grupos_do_ps():
    """A lista da linha PS, o dono único do PS sozinho (N8, 16/10/2026).

    O ato do computador (o que a linha «PS» dos gestos fazia) e o que o PS digita numa lista só:
    os grupos do gesto primeiro, as teclas depois, e um «— Nada —» no fim, que cala os dois.
    """
    juntos = []
    for grupo, ops in [*ACOES_GESTO, *ACOES_DO_PS]:
        if not grupo:
            continue
        igual = next((x for x in juntos if x[0] == grupo), None)
        if igual is None:
            juntos.append((grupo, list(ops)))
        else:
            igual[1].extend(ops)
    return juntos + [(g, ops) for g, ops in ACOES_GESTO if not g]


def _celula_da_acao(linha):
    if linha == "ps":
        lista = drop(_grupos_do_ps(), _acoes_do_gesto.rotulo(_acoes_do_gesto.PADRAO["ps"]),
                     gesto=LINHA_DE_BOTAO, linha=linha, campo=f"acao-{linha}")
        rotulo = _acoes_do_gesto.rotulo(_acoes_do_gesto.SCRIPT)
        return lista.replace(f"<option>{rotulo}</option>",
                             f'<option data-campo="{PREFIXO_DO_SCRIPT}ps">{rotulo}</option>')
    return drop(por_grupo(linha), _PADRAO_DOS_BOTOES[linha], gesto=LINHA_DE_BOTAO, linha=linha,
                campo=f"acao-{linha}")


def _linha_de_botao(pid, linha, nm, rot):
    glifos = f'<span class="gls">{_um(pid, rot=rot, nm=nm)}</span>'
    return f'<tr data-linha="{linha}"><td class="b">{glifos}</td><td>{_celula_da_acao(linha)}</td></tr>'


def _tabela(coluna):
    return ('<table class="tab bt2">\n'
            + "\n".join(_linha_de_botao(*x) for x in coluna) + '\n</table>')


COMBOS = [(g.numero, g.pecas, _acoes_do_gesto.rotulo(_acoes_do_gesto.PADRAO.get(
    g.chave, _acoes_do_gesto.NADA))) for g in _acoes_do_gesto.TODOS_OS_GESTOS.values()
    if g.chave != _acoes_do_gesto.GESTO_DO_PS]
_GESTO_DA_LINHA = {g.numero: g.chave for g in _acoes_do_gesto.TODOS_OS_GESTOS.values()}
_PECA_DA_ESCOLHA = {"create": "share", "l3": "stick_l", "r3": "stick_r"}


def drop_do_gesto(chave, faz):
    """A lista de UM gesto, com o endereço de leitura e o de pintura."""
    lista = drop(ACOES_GESTO, faz, gesto="acao-do-gesto", linha=chave,
                 campo=PREFIXO_DO_GESTO + chave)
    rotulo = _acoes_do_gesto.rotulo(_acoes_do_gesto.SCRIPT)
    return lista.replace(f"<option>{rotulo}</option>",
                         f'<option data-campo="{PREFIXO_DO_SCRIPT}{chave}">{rotulo}</option>')


def linha_combo(n, pecas, faz):
    chave = _GESTO_DA_LINHA[n]
    vale = "nao" if chave in _acoes_do_gesto.GESTOS_NOVOS else "sim"  # (noqa-acento)
    nomes = [glifo(gl_de(p), tam=18) if p == "ps" else _um(p) for p in pecas]
    combo = ' <span class="mais">+</span> '.join(nomes)
    return (f'<tr class="g g{n}" data-vale="{vale}" data-campo="{PREFIXO_DA_VALIDADE}{chave}"'
            f' data-hef-alvo="atributo" data-hef-atributo="data-vale">'
            f'<td class="b"><span class="gls">{combo}</span></td>'
            f'<td>{drop_do_gesto(chave, faz)}</td>'
            f'<td class="x"><button class="tira-gesto" type="button" data-gesto="remover-gesto"'
            f' data-linha="{chave}" aria-label="Remover o gesto" data-dica="Remover o gesto">'
            f'×</button></td></tr>')


def _escolha_do_gesto():
    """«+ Gesto»: um botão por candidato, só com o glifo; o usado e o proibido ficam indisponíveis.

    O nome da peça vai para a dica: ao lado do glifo, numa casa de 34 px, ele vazava sobre os
    vizinhos e para fora da caixa (o «Share» por cima do «Options», o «R1» fora dela).
    """
    botoes = []
    for b in _acoes_do_gesto.BOTOES_DA_ESCOLHA:
        livre = "sim" if b in _acoes_do_gesto.BOTOES_DO_GESTO_NOVO else "nao"  # (noqa-acento)
        peca = _PECA_DA_ESCOLHA.get(b, b)
        endereco = ("" if b in _acoes_do_gesto.BOTOES_PROIBIDOS else
                    f' data-campo="{PREFIXO_DA_LIBERDADE}{b}" data-hef-alvo="atributo"'
                    ' data-hef-atributo="data-livre"')
        botoes.append(
            f'<button type="button" class="b-gesto" data-gesto="novo-gesto" data-b="{b}"'
            f' data-livre="{livre}"{endereco} aria-label="PS + {PECAS[peca]["nome"]}"'
            f' data-dica="{PECAS[peca]["nome"]}">{_um(peca, nm=False)}</button>')
    return ('<details class="novo-gesto"><summary class="btn roxo mais-gesto"'
            ' data-dica="Acrescenta um gesto do PS com outro botão">+ Gesto</summary>'
            f'<div class="escolha-gesto">{"".join(botoes)}</div></details>')


def _seg(gesto, campo, aria, itens, ligado, classe=""):
    """Um seletor de botões: o clique manda o `value`, a pintura acende o que vale."""
    botoes = []
    for valor, rotulo, dica in itens:
        aceso = valor == ligado
        marca = ' class="on"' if aceso else ""
        ponta = f' data-dica="{dica}"' if dica else ""
        botoes.append(
            f'<button{marca} type="button" role="radio" aria-checked="{str(aceso).lower()}"'
            f' value="{valor}" data-gesto="{gesto}" data-campo="{campo}" data-hef-alvo="classe"'
            f' data-hef-quando="{valor}" data-hef-atributo="aria-checked"{ponta}>{rotulo}</button>')
    return (f'<div class="seg mini{classe}" role="radiogroup" aria-label="{aria}">'
            + "".join(botoes) + '</div>')


def _op(rotulo, corpo, classe=""):
    return f'<div class="op2{classe}"><span class="op2-rot">{rotulo}</span>{corpo}</div>'


def _perfil_de_ponto():
    moldes = []
    for m in MOLDES_DE_PERFIL:
        chave = f"molde:{m.chave}"
        marca = " selected" if chave == PADRAO_DO_PONTE else ""
        moldes.append(f'<option value="{chave}"{marca}>{m.nome}</option>')
    return ('<select class="campo-linha" data-gesto="point-and-click-perfil"'
            ' data-campo="point-and-click-perfil" data-hef-alvo="valor"'
            ' data-dica="O perfil que o point and click usa">'
            f'<optgroup label="Moldes">{"".join(moldes)}</optgroup>'
            f'<optgroup label="Meus perfis" data-bloco="{BLOCO_DOS_MEUS_PERFIS}"></optgroup>'
            '</select>')


OPCOES = "\n".join([
    _op("Permitir navegação", _seg(
        PERMITIR, PERMITIR, "Permitir navegação",
        [(valor, rotulo, dica) for valor, (rotulo, dica) in DO_PERMITIR.items()],
        PERMITIR_INTERNA, " quem")),
    _op("Na Steam", _seg(
        "na-steam", "na-steam", "Na Steam",
        [("big-picture", "Big Picture", ""),
         ("padrao", "Steam padrão", "")],  # (noqa-acento)
        "big-picture"),
        " so-steam"),
    _op("Perfil jogo - navegação", _perfil_de_ponto(), " do-hefesto"),
    _op("Touchpad", TOQUE_DO_TOUCHPAD, " do-hefesto"),
    _op("Função do teclado", simples(
        OPCOES_TECLADO, TECLADO_PADRAO, "teclado", "teclado-estado",
        "Quando o controle digita"), " do-hefesto"),
    _op("Velocidade do cursor", trilho(
        DEFAULT_MOUSE_SPEED, MOUSE_SPEED_MIN, MOUSE_SPEED_MAX, "vel-cursor",
        "Analógico esquerdo, touchpad e point and click"), " do-hefesto"),
    _op("Velocidade da rolagem", trilho(
        DEFAULT_SCROLL_SPEED, SCROLL_SPEED_MIN, SCROLL_SPEED_MAX, "vel-rolagem",
        "Analógico direito"), " do-hefesto"),
])

GESTOS_DO_PS = (
    '<div class="sec2 sec2-gestos"><span data-dica="Segure o PS e o outro juntos; vale em todo'
    ' controle">Gestos do PS</span>' + _escolha_do_gesto() + '</div>\n<table class="tab ges2">\n'
    + "\n".join(linha_combo(n, p, f) for n, p, f in COMBOS) + "\n</table>")

FILA = '''
        <div class="fila2">
          <a class="btn roxo" href="mapa-do-controle.html#trocar" data-dica="O Cruz pode virar Quadrado no jogo">Trocar os botões</a>
          <a class="btn roxo" href="mapa-do-controle.html#point-and-click" data-dica="Os botões do perfil de point and click">Point and click</a>
          <a class="btn roxo" href="#acessibilidade">Acessibilidade</a>
          <span class="padrao2">
            <input type="checkbox" id="conf-padrao" class="abre-conf">
            <label for="conf-padrao" class="btn amarelo-padrao">Voltar ao padrão</label>
            <label for="conf-padrao" class="veu"></label>
            <span class="confirma"><span>Voltar ao padrão os botões, as velocidades e os gestos?</span>
              <label for="conf-padrao" class="btn-conf vermelho" data-gesto="padrao-da-aba">Confirmar</label>
              <label for="conf-padrao" class="btn-conf">Cancelar</label></span>
          </span>
        </div>'''

MIOLO = f'''
    <div class="quadro estica nav2" data-quem="hefesto" data-campo="quem-navega"
         data-hef-alvo="atributo" data-hef-atributo="data-quem">
      <div class="nav-topo">
        <span class="quadro-titulo" tabindex="0" data-dica="O controle vira mouse e teclado do computador. Em «Permitir navegação», você escolhe quem traduz.">Navegação</span>
      </div>
      <div class="quadro-corpo">
        <div class="nav2-grade">
          <section class="nav2-botoes">
            <div class="sec2"><span class="so-hefesto">Os botões no computador</span><span class="so-steam">Os botões seguem a Steam</span></div>
            <div class="nav2-duas">
{_tabela(COLUNA_1)}
{_tabela(COLUNA_2)}
            </div>
          </section>
          <section class="nav2-opcoes">
            <div class="sec2">Opções</div>
            <div class="nav2-ops">
{OPCOES}
            </div>
            <div class="nav2-gestos">
{GESTOS_DO_PS}
            </div>
          </section>
        </div>
{FILA}
      </div>
    </div>
'''

SCRIPT = """<script>
(() => {
  const nav = document.querySelector('.nav2');
  const quem = nav.querySelector('.seg.quem');
  const acende = (grupo, botao) => grupo.querySelectorAll('button').forEach(b => {
    const on = b === botao;
    b.classList.toggle('on', on);
    b.setAttribute('aria-checked', String(on));
  });
  quem.addEventListener('click', e => {
    const b = e.target.closest('button');
    if (!b) return;
    nav.dataset.quem = b.value === 'steam' ? 'steam' : 'hefesto';
    acende(quem, b);
  });
  const escolha = nav.querySelector('.novo-gesto');
  const trava = () => escolha.querySelectorAll('.b-gesto').forEach(b => {
    b.disabled = b.dataset.livre !== 'sim';
  });
  new MutationObserver(trava).observe(escolha, {subtree: true, attributes: true, attributeFilter: ['data-livre']});
  trava();
  escolha.addEventListener('click', e => {
    if (e.target.closest('.b-gesto:not([disabled])')) setTimeout(() => { escolha.open = false; }, 0);
  });
  document.querySelectorAll('.seg.mini:not(.quem)').forEach(g => g.addEventListener('click', e => {
    const b = e.target.closest('button:not([disabled])');
    if (b) acende(g, b);
  }));
  document.documentElement.classList.add('alvos-24');
  const piso = () => document.querySelectorAll('body *').forEach(e => {
    if (e.closest('svg, .fita') || ['SCRIPT', 'STYLE'].includes(e.tagName)) return;
    const texto = ['INPUT', 'SELECT', 'TEXTAREA'].includes(e.tagName)
      || [...e.childNodes].some(n => n.nodeType === 3 && n.nodeValue.trim());
    if (texto && parseFloat(getComputedStyle(e).fontSize) < 12) e.style.setProperty('font-size', '12px', 'important');
  });
  const titulos = () => document.querySelectorAll('select').forEach(s => {
    const o = s.options[s.selectedIndex];
    if (o && s.title !== o.textContent.trim()) s.title = o.textContent.trim();
  });
  document.addEventListener('change', titulos);
  window.addEventListener('load', () => { piso(); titulos(); setTimeout(piso, 400); setInterval(titulos, 500); });
  if (location.hash === '#steam') quem.querySelector('[value="steam"]').click();
})();
</script>"""


def _ac(rotulo, controle, dica=""):
    d = f' data-dica="{dica}"' if dica else ""
    return (f'<div class="ac2"><span class="ac2-rot"{d}>{rotulo}</span>'
            f'<span class="ac2-ctl" inert>{controle}</span></div>')


def _ac_seg(itens, ligado):
    botoes = []
    for item in itens:
        marca = ' class="on"' if item == ligado else ""
        botoes.append(f'<button type="button" disabled{marca}>{item}</button>')
    return '<div class="seg mini">' + "".join(botoes) + '</div>'


def _ac_chips(itens, ligados):
    return ('<div class="ac-chips">' + "".join(
        f'<span class="chip{" on" if i in ligados else ""}">{i}</span>' for i in itens) + '</div>')


def _ac_num(valor, unidade):
    return ('<div class="campo-num mini"><span class="par"><span class="bignum">'
            f'<button class="passo" type="button" disabled>−</button><b>{valor}</b>'
            f'<button class="passo" type="button" disabled>+</button></span>'
            f'<span class="un">{unidade}</span></span></div>')


def _ac_lista(opcoes, escolhida):
    op = "".join(f'<option{" selected" if o == escolhida else ""}>{o}</option>' for o in opcoes)
    return f'<select class="campo-linha" disabled>{op}</select>'


def _ac_tog(texto):
    return f'<span class="nj-tog"><span class="pino"></span><span class="txt">{texto}</span></span>'


def _grade_da_acessibilidade():
    col1 = [
        _ac("Uma mão", _ac_seg(["Desligada", "Esquerda", "Direita"], "Desligada"),
            "Segurar o botão leva o lado ao outro"),
        _ac("Trocar de lado com",
            _ac_lista(["Segurar L1", "Segurar L2", "Tocar no touchpad"], "Segurar L1")),
        _ac("Alternar em vez de segurar",
            _ac_chips(["L1", "L2", "R1", "R2", "Cruz", "Círculo"], ()), "Um toque prende; outro solta"),
        _ac("Segurar conta após", _ac_num("0,8", "s")),
        _ac("Toque duplo em até", _ac_num("0,3", "s")),
        _ac("Repetir ao segurar", _ac_chips(["Direcional", "Cruz", "Círculo"], ()),
            "Segurar repete, como uma tecla"),
        _ac("Repete após", _ac_num("0,5", "s")),
        _ac("Ritmo da repetição", _ac_num("6", "Hz")),
    ]
    col2 = [
        _ac("Ignorar tremor abaixo de", _ac_num("120", "ms")),
        _ac("Aperto mínimo", _ac_num("50", "ms")),
        _ac("Botão que trava", _ac_chips(["L1", "R1", "L2", "R2"], ()),
            "Fica preso até o próximo botão"),
        _ac("Gestos sem apertar junto", _ac_tog("Desligado"), "Toque no PS e depois no outro"),
        _ac("Zona morta", _ac_num("10", "%")),
        _ac("Curva", _ac_seg(["Linear", "Precisa", "Estável", "Digital"], "Linear")),
        _ac("Sensibilidade", _ac_num("100", "%")),
        _ac("Inverter", _ac_chips(["Eixo Y", "Eixo X", "Trocar os lados"], ())),
        _ac("Giroscópio como analógico",
            _ac_lista(["Desligado", "Analógico direito", "Analógico esquerdo"], "Desligado")
            + _ac_lista(["Sempre", "Segurando L2"], "Segurando L2"),
            "Mexer o controle move o analógico"),
    ]
    return ('<div class="ac2-grade">'
            f'<div class="ac2-col">{"".join(col1)}</div>'
            f'<div class="ac2-col">{"".join(col2)}</div></div>')


def _tela_da_acessibilidade():
    return f'''
<div class="tela-nova" id="acessibilidade">
  <div class="tn-cx ac2-cx" role="dialog" aria-modal="true" aria-label="Acessibilidade">
    <div class="tn-topo">
      <span class="tn-tit" data-dica="Para pouca força, pouco alcance ou uma mão só">Acessibilidade</span>
      <span class="pc-para"><span class="ext-rot">Para</span><span data-bloco="{BLOCO_PARA_QUEM}">{chips_de_quem_navega(MESA_DA_FITA, so_o_primeiro=True)}</span></span>
      <span class="chave-jogo ac-chave" data-dica="A necessidade é de quem joga, não do jogo"><span class="nj-tog ligado" inert><span class="pino"></span><span class="txt">Sim</span></span><span class="chave-rot">Em todo perfil</span></span>
      <a class="tn-x" href="#" aria-label="Fechar">×</a>
    </div>
    <div class="tn-corpo">
      {_grade_da_acessibilidade()}
    </div>
    <div class="tn-rod">
      <a class="btn" href="#">Cancelar</a>
      <span class="btn amarelo-padrao apagado" aria-disabled="true" data-dica="Volta estes ajustes ao de fábrica">Voltar ao padrão</span>
      <span class="btn roxo apagado" aria-disabled="true" data-dica="Guarda estes ajustes para quem joga">Guardar</span>
    </div>
  </div>
</div>
'''


TELA_ACESSIBILIDADE = _tela_da_acessibilidade()

CSS = CSS_GLIFO + """
.rodape button { height:var(--h-acao);padding-top:0;padding-bottom:0;min-width:104px;text-align:center;justify-content:center }
.tela-nova { display:none;position:fixed;inset:0;z-index:60; background:rgba(9,10,15,.72);align-items:center;justify-content:center }
.tela-nova:target { display:flex }
.tn-cx { width:660px;max-width:94vw;background:var(--panel);border-radius:11px; border:1px solid var(--border-forte);box-shadow:0 26px 70px rgba(0,0,0,.62); display:flex;flex-direction:column;max-height:min(717px,calc(100vh - 40px)) }
.tn-topo { display:flex;align-items:center;gap:9px;padding:14px 18px 0;flex:none }
.tn-tit { font-size:14.5px;font-weight:600;color:var(--purple) }
.tn-x { margin-left:auto;width:26px;height:26px;border-radius:6px;text-decoration:none; border:1px solid var(--border-forte);color:var(--fg);font-size:14px; display:flex;align-items:center;justify-content:center }
.tn-x:hover { border-color:var(--red);color:var(--red) }
.tn-corpo { padding:11px 18px 16px;display:flex;flex-direction:column;min-height:0 }
.tn-corpo > .moldura { overflow-y:auto;min-height:0;scrollbar-gutter:stable }
.tn-corpo > .moldura { scrollbar-width:thin; scrollbar-color:var(--border-forte) var(--panel-2, #21222c) }
.tn-rod { display:flex;gap:var(--gap);padding:0 18px 16px;flex:none }
.tn-rod .btn { flex:1;text-decoration:none }
.tn-rod .confirma { left:18px;right:18px }
.tn-cx .tab td { height:23px }
.tn-cx .campo-linha { height:22px }
.tn-cx .dica { left:auto;right:22px }
.miolo > .quadro + .quadro > .quadro-topo { padding:6px 14px 0 }
.miolo > .quadro + .quadro > .quadro-corpo { padding:4px 14px 2px }
.miolo > .quadro:first-child > .quadro-corpo { padding-bottom:6px }
.at-linha:has(.btn) { height:var(--h-acao) }
.campo-num { display:flex;align-items:center;height:var(--h-escolha);padding:0 11px; border:1px solid var(--border-forte);border-radius:7px;background:var(--app-bg) }
.campo-num .par { display:flex;align-items:center;gap:9px;flex:0 1 auto;min-width:0 }
.campo-num .par:last-child { flex:1 1 auto }
.campo-num .par:not(:first-child):last-child .bignum { margin-left:auto }
.campo-num .sub { font-size:10.5px;color:var(--fg);white-space:nowrap; overflow:hidden;text-overflow:ellipsis }
.campo-num .risco { width:1px;height:18px;background:var(--border-forte);margin:0 4px 0 5px }
.bignum { display:inline-flex;align-items:center;flex:none }
.bignum b { font-family:'JetBrains Mono',monospace;font-size:15px;color:var(--fg); font-weight:600;min-width:22px;text-align:center }
.passo { width:22px;height:24px;border:1px solid var(--border-forte);border-radius:5px; background:transparent;color:var(--fg);font-size:14px;font-family:inherit; cursor:pointer;line-height:1;padding:0 }
.passo:hover { border-color:var(--purple);color:var(--purple) }
.campo-num .trilho { appearance:none;-webkit-appearance:none;flex:1 1 auto; min-width:0;height:5px;padding:0;margin:0;border:0;border-radius:3px; background:var(--border-forte);cursor:grab }
.campo-num .trilho:active { cursor:grabbing }
.campo-num .trilho::-webkit-slider-runnable-track { height:5px;border-radius:3px;background:transparent }
.campo-num .trilho::-webkit-slider-thumb { appearance:none;-webkit-appearance:none; width:12px;height:12px;border-radius:50%;background:var(--purple); border:2px solid var(--panel);margin-top:-4px }
.campo-num .trilho:focus-visible { outline:2px solid var(--purple);outline-offset:3px }
.campo-num .num { font-family:'JetBrains Mono',monospace;font-size:15px; color:var(--fg);font-weight:600;min-width:22px;text-align:right;flex:none; margin-left:11px }
.tab { width:100%;border-collapse:collapse;font-size:11.5px;table-layout:fixed }
.tab th { color:var(--fg);font-weight:700;text-align:left;font-size:10px; padding:0 8px 4px 0; border-bottom:1px solid var(--border-forte) }
.tab td { padding:0 8px 0 0;height:var(--h-escolha);color:var(--texto-suave); border-bottom:1px solid var(--border-sutil);vertical-align:middle }
.tab tr:last-child td { border-bottom:none }
.tab th:first-child,.tab td.b { width:176px }
.tab td.b { white-space:nowrap;overflow:hidden }
.tab tr.disputa td.b { color:var(--orange) }
.tab tr.g:hover td { background:rgba(189,147,249,.07) }
.campo-linha { width:100%;height:var(--h-escolha);border-radius:6px;font-size:11.5px;font-family:inherit; padding:0 8px;border:1px solid var(--border-forte);background:var(--panel); color:var(--fg);cursor:pointer }
.campo-linha:hover { border-color:var(--purple) }
.disputa .campo-linha { border-color:var(--orange);color:var(--orange) }
.campo-linha:disabled { border-color:var(--border-sutil);color:var(--fg); cursor:not-allowed }
.campo-linha:disabled:hover { border-color:var(--border-sutil) }
.nm { font-family:'JetBrains Mono',monospace;font-size:10.5px;color:var(--texto-suave);margin-left:3px }
.rot-gl { font-size:10.5px;color:var(--fg);margin-left:3px }
.acoes a.btn { text-decoration:none }
.confirma { display:none;position:absolute;bottom:calc(100% + 8px);left:0;right:0;z-index:6; align-items:center;gap:8px;background:var(--elevated);border:1px solid var(--orange); border-radius:7px;padding:8px 10px;font-size:11.5px;color:var(--texto-suave) }
.confirma span { flex:1 }
.btn-conf { height:var(--h-acao);padding:0 13px;border-radius:7px;font-size:12.5px; font-family:inherit;cursor:pointer;border:1px solid var(--comment); background:transparent;color:var(--texto-suave); display:inline-flex;align-items:center;justify-content:center }
.btn-conf.vermelho { border-color:var(--red);color:var(--red) }
.abre-conf { position:absolute;width:0;height:0;opacity:0;pointer-events:none }
.veu { display:none;position:fixed;inset:0;z-index:5;cursor:default }
.abre-conf:checked ~ .veu { display:block }
.abre-conf:checked ~ .confirma { display:flex }
.chave-rot { font-size:11.5px;color:var(--texto-suave) }
.nj-tog { display:inline-flex;align-items:center;gap:6px;height:22px;padding:0 9px; border:1px solid var(--border-forte);border-radius:6px;font-size:11px; color:var(--fg);cursor:pointer;user-select:none }
.nj-tog .pino { width:7px;height:7px;border-radius:50%;background:var(--border-forte) }
.nj-tog.ligado { border-color:var(--green);background:rgba(80,250,123,.1);color:var(--green) }
.nj-tog.ligado .pino { background:var(--green);box-shadow:0 0 6px var(--green) }
.tn-cx .tab th:first-child,.tn-cx .tab td.b { width:250px }
.gestos:has(.g1:hover) :is(#p1-glifo-ps,#p1-glifo-ps *,#p1-options > .peca,#p1-glifo-options,#p1-glifo-options *) { fill:var(--pink)!important;stroke:var(--pink)!important;color:var(--pink) }
.gestos:has(.g2:hover) :is(#p1-glifo-ps,#p1-glifo-ps *,#p1-dpad_up > .peca,#p1-glifo-dpad_up,#p1-glifo-dpad_up *) { fill:var(--pink)!important;stroke:var(--pink)!important;color:var(--pink) }
.gestos:has(.g3:hover) :is(#p1-glifo-ps,#p1-glifo-ps *,#p1-dpad_down > .peca,#p1-glifo-dpad_down,#p1-glifo-dpad_down *) { fill:var(--pink)!important;stroke:var(--pink)!important;color:var(--pink) }
.gestos:has(.g4:hover) :is(#p1-glifo-ps,#p1-glifo-ps *,#p1-stick_r > .peca,#p1-glifo-stick_r,#p1-glifo-stick_r *) { fill:var(--pink)!important;stroke:var(--pink)!important;color:var(--pink) }
.gestos:has(.g5:hover) :is(#p1-glifo-ps,#p1-glifo-ps *,#p1-stick_l > .peca,#p1-glifo-stick_l,#p1-glifo-stick_l *) { fill:var(--pink)!important;stroke:var(--pink)!important;color:var(--pink) }
.gestos:has(.g6:hover) :is(#p1-glifo-ps,#p1-glifo-ps *) { fill:var(--pink)!important;stroke:var(--pink)!important;color:var(--pink) }
.tn-cx.larga { width:1000px }
.tn-cx.ac-cx { width:860px }
.pc-para { margin-left:auto;font-size:11.5px;color:var(--texto-suave);display:inline-flex;align-items:center;gap:6px;white-space:nowrap }
.tn-topo .pc-para { margin-left:auto }
.tn-topo .pc-para + .ac-chave { margin-left:14px }
.tn-topo .ac-chave + .tn-x { margin-left:12px }
.ext-rot { font-size:10.5px;color:var(--rot-campo) }
.seg.mini { gap:6px;flex-wrap:nowrap }
.seg.mini button { min-width:0;flex:0 0 auto;padding:5px 11px;font-size:11.5px }
.pc-linha .seg.mini button { height:28px;padding:0 11px }
.campo-num.mini { height:28px;padding:0 9px }
.campo-num.mini .bignum b { font-size:13px;min-width:34px }
.campo-num .un { font-size:10.5px;color:var(--fg);white-space:nowrap }
.tab.pc-tab { table-layout:fixed }
.tab.pc-tab td { height:30px;padding:0 6px 0 0;border-bottom:1px solid var(--border-sutil) }
.tab.pc-tab tr:last-child td { border-bottom:0 }
.tab.pc-tab th:first-child { width:auto }
.tab.pc-tab td.o { color:var(--texto-suave);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:11.5px }
.tab.pc-tab .campo-linha { height:24px }
.pc-bt .gl { flex:0 0 16px }
.ac-topo .nj-tog { margin-left:auto }
.ac-linha .campo-linha { width:auto;min-width:150px;height:28px }
.ac-chips { display:flex;flex-wrap:wrap;gap:6px }
.ac-chips .chip { padding:3px 10px;font-size:11.5px;cursor:pointer }
.ac-chave { margin-left:0 }
.tela-nova:target ~ .todo-menu { display:none }
.campo-num .trilho[data-gesto] { height:24px;padding:9.5px 0;box-sizing:border-box;background-clip:content-box }
.tn-cx.ac-cx { width:980px }
.ac-chips .chip { display:inline-flex;align-items:center;min-height:24px }
.at-pc .seg.mini button { height:28px;padding:0 14px }
.at-pc .btn.configurar { flex:0 0 auto;height:28px;display:inline-flex;align-items:center;padding:0 14px;font-size:11.5px;margin-left:auto;text-decoration:none }
.tab tr.dois td { height:34px }
.nav2 { position:relative }
.nav-topo { display:flex;align-items:center;gap:12px;padding:12px 16px 0;position:relative;min-height:36px }
.nav-topo .quadro-titulo:focus-visible { outline:2px solid var(--cyan,#8be9fd);outline-offset:3px;border-radius:4px }
.miolo { overflow:hidden }
.nav2 > .quadro-corpo { padding:14px 16px 14px;gap:14px }
.nav2-grade { flex:1;min-height:0;display:grid;grid-template-columns:minmax(0,1.62fr) minmax(0,1fr);gap:18px }
.nav2-botoes,.nav2-opcoes { background:var(--app-bg);border:1px solid var(--border-sutil);border-radius:9px;padding:12px 16px;min-width:0 }
.sec2 { font-size:12px;font-weight:600;color:var(--rot-campo);margin:0 0 8px }
.nav2-duas { display:grid;grid-template-columns:1fr 1fr;gap:22px;transition:opacity .15s }
.tab.bt2 { width:100%;border-collapse:collapse }
.tab.bt2 td { height:36px }
.tab.bt2 td.b { width:104px }
.tab.bt2 .campo-linha { height:30px }
.tab.bt2 .gls { display:inline-flex;align-items:center;gap:6px }
.op2 { display:grid;grid-template-columns:140px minmax(0,1fr);align-items:center;gap:12px;height:37px }
.op2-rot { font-size:12px;color:var(--texto-suave) }
.op2 .campo-linha { height:30px }
.op2 .seg.mini button { flex:1;height:30px }
.op2 .campo-num { height:30px }
.sec2-gestos { margin-top:8px;cursor:help }
.tab.ges2 { width:100%;border-collapse:collapse }
.tab.ges2 td { height:29px }
.tab.ges2 td.b { width:112px }
.tab.ges2 .campo-linha { height:26px }
.nav2[data-quem="hefesto"] .so-steam,.nav2[data-quem="steam"] .so-hefesto { display:none }
.nav2[data-quem="steam"] .nav2-duas,.nav2[data-quem="steam"] .do-hefesto { opacity:.35;pointer-events:none }
.fila2 { display:grid;grid-template-columns:repeat(4,1fr);gap:14px;padding:12px 16px;background:var(--app-bg); border:1px solid var(--border-sutil);border-radius:9px;flex:none }
.fila2 > .btn,.fila2 .amarelo-padrao { height:38px;width:100%;text-decoration:none;white-space:nowrap }
.padrao2 { position:relative;display:block }
.btn.apagado,.btn.apagado:hover { opacity:.4;cursor:not-allowed;background:none }
.padrao2 .confirma { left:auto;right:0;width:420px }
.tn-cx.ac2-cx { width:1060px }
.ac2-grade { display:grid;grid-template-columns:1fr 1fr;gap:0 30px }
.ac2 { display:grid;grid-template-columns:204px minmax(0,1fr);align-items:center;gap:12px;height:44px; border-bottom:1px solid var(--border-sutil) }
.ac2-col .ac2:last-child { border-bottom:0 }
.ac2-rot { font-size:12px;color:var(--texto-suave) }
.ac2-rot[data-dica] { cursor:help }
.ac2-ctl { display:flex;align-items:center;gap:8px;min-width:0 }
.ac2-ctl .campo-linha { height:28px;width:auto;min-width:0;flex:1 }
.ac2-ctl .seg.mini { flex-wrap:nowrap }
.ac2-ctl .seg.mini button { height:28px }
.ac2-ctl .ac-chips { display:flex;gap:6px;flex-wrap:nowrap }
.ac2-ctl .campo-num.mini { flex:none }
.tab.bt2 td:last-child,.tab.ges2 td:last-child { padding-right:0 }
.tab.bt2 .nm,.tab.bt2 .rot-gl,.tab.ges2 .nm { font-family:inherit;font-size:12px;color:var(--texto-suave);margin-left:4px }
.nav2-duas { align-items:start }
.tn-rod { padding-top:6px }
.nav2-opcoes { --rot2:140px }
.op2 { grid-template-columns:var(--rot2) minmax(0,1fr) }
.tab.ges2 td.b { width:calc(var(--rot2) + 12px) }
.ac2 { grid-template-columns:184px minmax(0,1fr) }
.ac2-ctl > * { flex:1 1 0;min-width:0 }
.ac2-ctl .campo-num.mini { flex:1 1 0 }
.ac2-ctl .seg.mini,.ac2-ctl .ac-chips { display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:6px }
.ac2-ctl .seg.mini button,.ac2-ctl .ac-chips .chip { justify-content:center;text-align:center;padding-left:8px;padding-right:8px;white-space:nowrap }
.ac2-ctl .campo-num.mini .par { flex:1 1 auto }
.ac2-ctl .campo-num.mini .bignum { flex:1 1 auto;justify-content:space-between }
.ac2-ctl .nj-tog { height:28px;border-radius:7px }
@media (max-height:860px){.nav2 .tab.bt2 td{height:30px!important} .nav2 .tab.bt2 select{height:26px} .nav2 .op2{height:31px} .nav2 .op2 :is(.campo-linha,.campo-num,.seg.mini button){height:26px} .nav2 .tab.ges2 td{height:25px!important} .nav2 .tab.ges2 select{height:23px}}
@media (max-height:780px){.nav2 .tab.bt2 td{height:26px!important} .nav2 .tab.bt2 select{height:23px} .nav2 .op2{height:27px} .nav2 .op2 :is(.campo-linha,.campo-num,.seg.mini button){height:23px} .nav2 .tab.ges2 td{height:22px!important} .nav2 .tab.ges2 select{height:20px} .nav2-botoes,.nav2-opcoes{padding-block:8px} .nav2 > .quadro-corpo{padding-block:10px}}
.nav2-botoes,.nav2-opcoes { display:flex;flex-direction:column;min-height:0 }
.nav2-duas { flex:1 1 auto;min-height:0;align-items:stretch }
.nav2-duas > .tab.bt2 { height:100% }
.nav2-ops { flex:1 1 auto;min-height:0;display:flex;flex-direction:column;justify-content:space-evenly }
.nav2-gestos { flex:none }
.op2 .seg.mini button { white-space:nowrap;padding:0 6px;min-width:0 }
.sec2-gestos { display:flex;align-items:center;justify-content:space-between;cursor:default }
.sec2-gestos > span[data-dica] { cursor:help }
.tab.ges2 td.x { width:32px;text-align:right }
.tab.ges2 tr[data-vale="nao"] { display:none }
.tira-gesto { width:26px;height:26px;border-radius:6px;border:1px solid var(--border-forte);background:transparent;color:var(--fg);font-size:14px;line-height:1;cursor:pointer;padding:0 }
.tira-gesto:hover { border-color:var(--red);color:var(--red) }
.novo-gesto { position:relative }
.novo-gesto > summary { list-style:none;height:26px;padding:0 12px;font-size:12px;display:inline-flex;align-items:center;cursor:pointer }
.novo-gesto > summary::-webkit-details-marker { display:none }
.escolha-gesto { position:absolute;right:0;bottom:calc(100% + 6px);z-index:8;display:grid;grid-template-columns:repeat(4,34px);gap:6px;padding:10px;background:var(--elevated);border:1px solid var(--border-forte);border-radius:8px;box-shadow:0 12px 30px rgba(0,0,0,.5) }
.b-gesto { width:34px;height:30px;padding:0;justify-content:center;border-radius:6px;border:1px solid var(--border-forte);background:var(--panel);color:var(--fg);display:inline-flex;align-items:center;gap:4px;cursor:pointer;white-space:nowrap }
.b-gesto:hover:not([disabled]) { border-color:var(--purple) }
.b-gesto[disabled] { opacity:.3;cursor:not-allowed }
.nav2-opcoes .sec2-gestos { margin:8px 0 6px }
html.alvos-24 :is(button,select,input:not([type=checkbox]):not([type=radio]):not([type=hidden]),textarea,summary,[role=button],.nj-tog,.sw,.passo,label.faixa,.nav-i,.mudo-i,.padrao-i){min-height:24px;box-sizing:border-box}
html.alvos-24 :is(button,[role=button],.nj-tog,.passo,.nav-i,.mudo-i,.padrao-i){min-width:24px}
html.alvos-24 :is(input[type=checkbox],input[type=radio]):not(.radio-mesa){min-width:24px;min-height:24px}
html.alvos-24 input[type=range]{height:24px}
"""


def _conferir(doc):
    """O gerador confere o que a tela promete antes de escrever."""
    falhas = []

    def exigir(cond, msg):
        if not cond:
            falhas.append(msg)

    corpo = doc
    exigir(not re.search(r'class="[^"]*\bajuda\b', corpo), "o «?» voltou: a explicação mora no `data-dica`")
    for velha in ("definicoes-mouse", "teclas-do-teclado", 'id="remapeamento"', 'id="point-and-click"'):
        exigir(velha not in corpo, f"a janela {velha!r} voltou")
    achadas = re.findall(r'<tr data-linha="([a-z0-9_]+)"', corpo)
    exigir(achadas == LINHAS, f"as linhas da tela divergem das do desenho: {achadas}")
    exigir(corpo.count(f'data-gesto="{LINHA_DE_BOTAO}"') == len(LINHAS),
           "uma linha de botão ficou sem gesto")
    exigir(len(COLUNA_1) == len(COLUNA_2), "as duas colunas de «Os botões» não têm o mesmo tamanho")
    opcoes = corpo.split('<section class="nav2-opcoes">')[1].split("</section>")[0]
    exigir(opcoes.lstrip().startswith('<div class="sec2">Opções</div>'),
           "o quadrante da direita perdeu o título «Opções»")
    exigir(DICA_DO_TOQUE in opcoes and DICA_DO_TOQUE not in corpo.split(
        '<section class="nav2-opcoes">')[0], "o toque do touchpad não mora em «Opções»")
    exigir(f'data-gesto="{PERMITIR}"' in opcoes
           and all(f'value="{v}"' in opcoes for v in DO_PERMITIR),
           "«Permitir navegação» perdeu um dos três botões")
    for velha in ("Quem navega", "Tipo de navegação", "Navega com", "navegacao-tipo",
                  "Perfil de point and click"):
        exigir(velha not in corpo, f"{velha!r} voltou à Navegação")
    exigir('data-gesto="novo-gesto"' in opcoes and 'data-gesto="remover-gesto"' in opcoes,
           "os gestos do PS perderam o «+ Gesto» ou o «×»")
    exigir('data-linha="ps"' not in opcoes, "a linha do PS sozinho voltou aos gestos")
    exigir(len(re.findall(r'<a class="btn roxo" href="[^"]+"', corpo.split('class="fila2"')[1]
                          .split("</div>")[0])) == 3, "a fila de baixo perdeu um botão")
    exigir('href="mapa-do-controle.html#trocar"' in corpo
           and 'href="mapa-do-controle.html#point-and-click"' in corpo,
           "a fila de baixo não aponta para o mapa do controle")
    exigir('id="acessibilidade"' in corpo and "Giroscópio como analógico" in corpo,
           "a janela Acessibilidade perdeu o giroscópio")
    exigir(corpo.count('class="g g') == len(COMBOS), "os gestos do PS não são os do produto")
    exigir(all(f">{m.nome}</option>" in corpo for m in MOLDES_DE_PERFIL),
           "a lista de point and click não traz os moldes do produto")
    exigir(all(f"{o}</option>" in corpo for o in OPCOES_TECLADO),
           "a Função do teclado perdeu uma das quatro opções")
    if falhas:
        raise SystemExit("ERRO em 06-navegacao:\n  " + "\n  ".join(f"- {f}" for f in falhas))


def _gerar() -> None:
    n = monta("06-navegacao", "Navegação", MIOLO + SCRIPT, CSS)

    p = onde.pagina("06-navegacao.html")
    s = p.read_text()
    fita_re = re.compile(r'(<div class="fita inerte"[^>]*)(>)(.*?)(</div>)', re.S)
    if not fita_re.search(s):
        raise SystemExit("ERRO: a fita inerte mudou de forma — refaça o endereço")
    s = fita_re.sub(
        lambda m: (m.group(1) + ' data-campo="fita-chips" data-hef-alvo="html"'
                   + m.group(2) + chips_da_fita(MESA_DA_FITA) + m.group(4)),
        s, count=1)

    marca = FIM_DA_ABA
    if marca not in s:
        raise SystemExit("ERRO: a marca da legenda mudou no fim.html")
    s = s.replace(marca, TELA_ACESSIBILIDADE.strip() + "\n\n" + marca, 1)
    onde.gravar("06-navegacao.html", s)

    _conferir(onde.pagina("06-navegacao.html").read_text())
    print(f"06-navegacao: OK, {n} divs · {len(CONECTADOS)} conectado(s) "
          f"+ {len(MESA) - len(CONECTADOS)} lugar(es) vazio(s) · {len(LINHAS)} botões")


if __name__ == "__main__":
    import os
    import shutil
    import tempfile

    _real = onde.saida()
    _prova = pathlib.Path(tempfile.mkdtemp(prefix="hefesto-prova-06-"))
    for _vizinha in _real.glob("*.html"):
        shutil.copy2(_vizinha, _prova / _vizinha.name)
    os.environ[onde._DESVIO] = str(_prova)
    _gerar()
    shutil.copyfile(_prova / "06-navegacao.html", _real / "06-navegacao.html")
    shutil.rmtree(_prova)
