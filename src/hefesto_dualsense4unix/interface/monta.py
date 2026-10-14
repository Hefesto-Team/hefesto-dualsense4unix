"""Monta uma aba a partir do esqueleto VALIDADO da Jogar + o miolo dado."""
import csv, html, pathlib, re, sys
from collections.abc import Sequence
from typing import Any

import onde

R = pathlib.Path(__file__).resolve().parent

RAIZ_DO_REPO = pathlib.Path(__file__).resolve().parents[3]


def _do_repo(relativo: str) -> str:
    """O conteúdo de um arquivo de `docs/`, ou vazio quando não há repositório."""
    alvo = RAIZ_DO_REPO / relativo
    return alvo.read_text(encoding="utf-8") if alvo.exists() else ""
_F = pathlib.Path(__file__).resolve().parent
TOPO = (_F / "topo.html").read_text()
FIM  = (_F / "fim.html").read_text()
DS   = (_F / "ds_limpo.svg").read_text()

#: A BASE COMUM DAS ABAS (13/10/2026, A-BASE-COMUM-DAS-ABAS-01): a dica no hover, o Modo
#: automático e o menu do botão direito. Dois arquivos, UMA vez por página, iguais em todas: o
#: `<style id="base-comum">` entra no fim do `<head>` e o `<script id="base-comum">` antes do
#: `</body>`. A página que não passa por `monta()` (a Calibrar) chama `com_a_base()` ela mesma.
BASE_CSS = (_F / "base-comum.css").read_text(encoding="utf-8")
BASE_JS = (_F / "base-comum.js").read_text(encoding="utf-8")


def com_a_base(doc: str) -> str:
    """O documento com a base comum posta UMA vez; levanta se ela já estiver lá ou faltar âncora."""
    if 'id="base-comum"' in doc:
        raise SystemExit("ERRO: a base comum já está nesta página; ela entra uma vez só")
    if doc.count("</head>") != 1 or doc.count("</body>") != 1:
        raise SystemExit("ERRO: a página não tem um `</head>` e um `</body>` para a base comum")
    doc = doc.replace("</head>", f'<style id="base-comum">\n{BASE_CSS}</style>\n</head>', 1)
    return doc.replace("</body>", f'<script id="base-comum">\n{BASE_JS}</script>\n</body>', 1)

LOGO = (R / "assets/hefesto-logo.svg").read_text()

MARCA_DA_LOGO = '<div class="logo"><!--LOGO--></div>'


def _logo_em_linha(x: str) -> str:
    """O SVG dela, pronto para viver dentro do HTML."""
    x = re.sub(r"<\?xml[^>]*\?>\s*", "", x).strip()
    return re.sub(r'<svg width="\d+" height="\d+"', '<svg width="40" height="40"',
                  x, count=1)


if TOPO.count(MARCA_DA_LOGO) != 1:
    raise SystemExit(f"ERRO: a âncora da logo aparece {TOPO.count(MARCA_DA_LOGO)}× "
                     f"no topo.html (tem de ser 1) —\n  {MARCA_DA_LOGO}")
TOPO = TOPO.replace(MARCA_DA_LOGO,
                    f'<div class="logo">{_logo_em_linha(LOGO)}</div>', 1)

ABAS = [("Jogar","01-jogar"),("Controles","02-controles"),("Gatilhos","03-gatilhos"),
        ("Iluminação","04-iluminacao"),("Vibração","05-vibracao"),("Navegação","06-navegacao"),
        ("Lançadores","07-lancadores"),("Conexões","08-conexoes"),("Sistema","09-sistema"),
        ("Perfis","10-perfis")]

sys.path.insert(0, str(RAIZ_DO_REPO / "src"))
from hefesto_dualsense4unix.core.led_control import (  # noqa: E402
    player_led_pattern,
)

# `player_slot_color` É REEXPORTADA, e a linha leva `noqa: F401` porque este
# FOI ASSIM QUE OS QUATRO QUEBRARAM, e a causa é mecânica: sem o `noqa`, o
# em `ImportError: cannot import name 'player_slot_color' from 'monta'`.
from hefesto_dualsense4unix.core.led_control import (  # noqa: E402, F401
    player_slot_color,
)
from hefesto_dualsense4unix.core.sysfs_leds import norm_mac  # noqa: E402

PADRAO_JOGADOR = {
    n: "".join(str(i + 1) for i, on in enumerate(player_led_pattern(n)) if on)
    for n in range(1, 9)
}

GLIFOS = RAIZ_DO_REPO / "assets/glyphs"

DADOS_DO_REPO = RAIZ_DO_REPO / "docs/data"

def _nomes_das_pecas() -> dict[str, str]:
    linhas = [x for x in _do_repo("docs/data/pecas-do-dualsense.csv").splitlines()
              if not x.startswith("#")]
    return {p["glifo"]: p["nome"] for p in csv.DictReader(linhas) if p["glifo"] != "-"}


NOME_DA_PECA = _nomes_das_pecas()


def nome_do_glifo(nome: str) -> str:
    """Como a peça se chama na tela, e RECUSA o glifo que o CSV não conhece."""
    if nome not in NOME_DA_PECA:
        raise SystemExit(
            f"ERRO em glifo({nome!r}): a peça não tem linha em "
            f"docs/data/pecas-do-dualsense.csv — o nome em português dela não se "
            f"inventa aqui, escreva a linha lá")
    return NOME_DA_PECA[nome]

#: "Automático" (decisão de produto): DualSense · Xbox 360 · Nintendo Pro.
#: era DualSense e o P3 Xbox 360; a Controles e a Conexões diziam o contrário, na
MASCARAS = ("DualSense", "Xbox 360", "Nintendo Pro")

# (`"usb"`/`"bt"`), que é a chave que `mesa_viva.mesa_do_estado` publica, e
MESA = [
    {"pref": "p1", "jogador": 1, "cor": "cosmic-red",     "nome": "Cosmic Red",
     "dono": "Vitória", "via": "USB", "transporte": "usb",
     "alvo": True,  "mascara": "DualSense",    "conectado": True},
    {"pref": "p2", "jogador": 2, "cor": "starlight-blue", "nome": "Starlight Blue",
     "via": "BT",  "transporte": "bt",
     "alvo": False, "mascara": "Xbox 360",     "conectado": True},
    {"pref": "p3", "jogador": 3, "cor": "galactic-purple", "nome": "Galactic Purple",
     "via": "BT",  "transporte": "bt",
     "alvo": False, "mascara": "DualSense",    "conectado": False},
    {"pref": "p4", "jogador": 4, "cor": "white",          "nome": "White",
     "via": "USB", "transporte": "usb",
     "alvo": False, "mascara": "Nintendo Pro", "conectado": False},
]

CONECTADOS = [c for c in MESA if c.get("conectado", True)]


SEPARADOR = ' <span class="pt">•</span> '

TRAVESSAO = "—"


def numero_do_jogador(n: Any) -> str:
    """O número do jogador COM ENDEREÇO: o `<span>` que o tique repinta com o do daemon.

    Um lugar só: a 02 (cabeçalho e tira), a 06 (`.nav-rot`) e a Calibrar o chamam, e o endereço
    não ganha uma segunda grafia. O alvo é `html` de propósito: com `texto`, o molde do lugar
    vazio cairia no travessão e a tira diria «P— • — • —».
    """
    return f'<span data-campo="jogador" data-hef-alvo="html">{n}</span>'


def dono_na_linha(nomes: dict[str, str], uniq: str, jogador: Any, *,
                  em_html: bool = False) -> str:
    """Quem joga com o controle: o nome que o usuário deu a ele, ou o «P N» quando não há nome.

    A REGRA É UMA SÓ, e mora aqui (D-2909-O-CARTAO-DIZ-QUEM-JOGA): a 08 a mostra no campo do dono,
    o cartão aberto da 02 e a Calibrar a mostram no título. `nomes` é `{endereço: nome}` do
    leitor da 08 (o `Alias` do BlueZ). Com `em_html`, o nome sai ESCAPADO (é texto dela) e o
    número leva o endereço de `numero_do_jogador`.
    """
    nome = nomes.get(str(norm_mac(str(uniq or "")) or "").upper(), "")
    if nome:
        return html.escape(nome) if em_html else nome
    if isinstance(jogador, int) and not isinstance(jogador, bool):
        return f"P{numero_do_jogador(jogador)}" if em_html else f"P{jogador}"
    return ""


def quem_joga_com_o_numero(nomes: dict[str, str], uniq: str, jogador: Any) -> str:
    """Para quem não tem lâmpadas (a Calibrar): `<nome> • P<n>`, ou só `P<n>` sem nome.

    Sai da MESMA regra de `dono_na_linha`; aqui o número fica ao lado do nome, e não no lugar dele.
    O nome e o número vão em dois `span` colados (`quem-nome` e `quem-num`): o cartão da Calibrar
    é de uma linha só, e quem ganha a reticência é o NOME, com ele inteiro no `title`; o «• P<n>»
    não encolhe. Num texto só, o corte comia o número já com «Vitória Maria» (13 letras).
    """
    quem = dono_na_linha(nomes, uniq, jogador, em_html=True)
    numero = dono_na_linha({}, uniq, jogador, em_html=True)
    if quem in ("", numero):
        return quem
    return (f'<span class="quem-nome" title="{quem}">{quem}</span>'
            f'<span class="quem-num">{SEPARADOR}{numero}</span>')


def partes_do_modelo(c: dict[str, Any]) -> list[str]:
    """As partes TEXTO da linha «Modelo» (04 e 05): `Pn`, o nome que o usuário deu, o modelo e a via.

    A ordem é UMA e mora aqui: o gerador a junta com o `SEPARADOR`, e os pacotes das duas abas a
    juntam com « • » no que o piloto pinta. Sem nome (`dono` vazio ou ausente) a parte some, e a
    linha fica como era: nunca «P1 • P1».
    """
    return [p for p in (f'P{c["jogador"]}', str(c.get("dono") or ""), c["nome"], c["via"]) if p]


def rotulo(c: dict[str, Any], forma: str = "completa") -> str:
    """O rótulo de um controle, e ele tem UMA ordem só."""
    if forma == "modelo":
        # a linha «Modelo» das abas 04 e 05 leva o nome do jogador (o `Alias` que a aba Conexões dá
        # ao controle) antes do modelo: pedido de 06/10/2026. O nome é texto DO USUÁRIO: escapado.
        return SEPARADOR.join(html.escape(p) for p in partes_do_modelo(c))
    if forma == "curta":
        return SEPARADOR.join(p for p in [f'P{c["jogador"]}', c["nome"], c["via"]] if p)
    if forma == "peca":
        corpo = SEPARADOR.join([c["nome"], c["via"]])
        quem = c.get("quem")
        # `<quem>` vai na frente e só aparece no cartão ABERTO (a tira fechada tem o «Pn •»)
        return f'<span class="so-aberto">{quem}{SEPARADOR}</span>{corpo}' if quem else corpo
    return SEPARADOR.join(["Sony", f'Player {c["jogador"]}', c["nome"], c["via"]])


#: `core/led_control.player_slot_color` devolve
#: primárias cruas (#0000FF, #FF0000, #00FF00…) — cor de monitor de teste ao lado
#: na 04, e a medição mostrou o resultado: a 02 continuou pintando #0000FF na barra
#: tem azul próprio, e mapear o azul do player 1 para o ciano fazia DUAS casas da
TOM_DA_CASA = {
    "#0000FF": "#7EB8D4",
    "#FF0000": "#FF5555",
    "#00FF00": "#50FA7B",
    "#FF0080": "#FF79C6",
    "#FFFF00": "#F1FA8C",
    "#00FFFF": "#8BE9FD",
    "#FF8000": "#FFB86C",
    "#8000FF": "#BD93F9",
    # Os oito de cima são `player_slot_color(1..8)` — a cor AUTOMÁTICA de cada
    "#80FF00": "#B8F976",
    "#00FF80": "#76F9B8",
    "#0080FF": "#76B8F9",
    "#FF00FF": "#F976F9",
    "#FFFFFF": "#F8F8F2",
    "#000000": "#44475A",
}


def tom_da_casa(hexa: str) -> str:
    """O hex cru do produto, no tom da casa. Desconhecido volta como veio."""
    return TOM_DA_CASA.get(hexa.upper(), hexa)


def cor_da_zona(colorway: str, zona: str = "casca-solida") -> str:
    """A cor de uma zona daquele modelo, LIDA do que o gerador escreveu no SVG."""
    m = re.search(rf'svg\[data-colorway="{re.escape(colorway)}"\]\{{([^}}]*)\}}', DS)
    if not m:
        raise SystemExit(f"ERRO: colorway '{colorway}' não existe no SVG gerado. "
                         f"Rode scripts/gerar_cores_do_dualsense.py")
    for par in m.group(1).split(";"):
        k, _, v = par.partition(":")
        if k.strip() == f"--z-{zona}":
            return v.strip()
    raise SystemExit(f"ERRO: zona '{zona}' não existe em '{colorway}'")


def o_desenho_conhece(colorway: str) -> bool:
    """A folha das cores tem regra para este modelo?"""
    return bool(re.search(rf'svg\[data-colorway="{re.escape(colorway)}"\]', DS))


def cor_de_css(colorway: str, zona: str = "casca-solida") -> str:
    """A cor daquele modelo QUE UM CAMPO DE COR CSS ACEITA — ou `""`.

    O DEFEITO QUE ELA CURA, achado pelos DOIS auditores da leva de 03/09/2026 e
    medido no WebKit desta máquina: **oito dos vinte e oito modelos dela**
    (Grey Camouflage, Chroma Teal, Chroma Indigo, Chroma Pearl, Ghost of Yōtei,
    Marathon, Genshin Impact e 007 First Light) não têm hexa amostrado, e
    :func:`cor_da_zona` devolve para eles ``url(#hachura-sem-hex)`` — uma
    referência a `<pattern>`, que pinta um `fill` de SVG e **não é uma cor**.

    Esse valor viajava até a PELE do cartão, onde o alvo `cor` do piloto faz
    ``el.style.color = v``. O CSSOM **recusa em silêncio** o que não é cor, e o
    que ficava na tela era o que já estava lá: o ``#ae335a`` do MOCKUP, cravado
    no HTML congelado. Resultado: com um Grey Camouflage na mesa, o desenho
    dizia `grey-camouflage` e a pele três centímetros ao lado dizia Cosmic Red.

    **É a queixa de uso literal, com os donos trocados** — *"os svgs mudam de
    acordo com o controle identificado (…) isso tá errado"* —, e é pior do que
    não pintar: não pintar é uma lacuna, pintar OUTRO MODELO é uma afirmação
    falsa. São 8 de 28, 29% do mapa dela.

    O `""` É A REGRA DE PRODUTO, e não zelo: *campo sem informação não mostra nada*. O
    alvo `cor` com valor vazio APAGA a declaração em linha, e a pele cai no
    neutro da folha — um controle sem cor de plástico, que é o honesto quando a
    amostragem não existe. O DESENHO continua certo: o `data-colorway` recebe o
    slug pelo alvo `atributo`, e o `<pattern>` pinta a hachura no SVG, que é o
    contexto em que ele VALE.

    NÃO HÁ TABELA NOVA AQUI: a lista dos oito não se digita. O discriminador é
    a FORMA do valor — quem não começa por `#` não é cor —, e por isso ele
    continua certo no dia em que ela amostrar mais um modelo ou em que nascer
    um gradiente novo.
    """
    try:
        valor = str(cor_da_zona(colorway, zona)).strip()
    except BaseException:
        return ""
    return valor if valor.startswith("#") else ""


MAIOR_ROTULO = {
    "03-gatilhos": 77,
    "04-iluminacao": 73,
    "05-vibracao": 126,
}

RESPIRO_DO_ROTULO = 12


def larg_rotulos(aba: str, com_glifo: bool = False) -> int:
    """A largura da coluna de rótulos daquela aba."""
    if aba not in MAIOR_ROTULO:
        raise SystemExit(f"ERRO: não sei o maior rótulo de {aba!r}. Meça antes de "
                         f"usar: um número chutado aqui corta ou quebra a palavra.")
    extra = (GLIFO_DA_SECAO + VAO_DO_GLIFO) if com_glifo else 0
    return extra + MAIOR_ROTULO[aba] + RESPIRO_DO_ROTULO


GAP_DAS_COLUNAS = 16

GLIFO_DA_SECAO = 36
VAO_DO_GLIFO = 10


ROTULO_DA_FITA = "Selecionar:"


# `jogar_vivo._indice_na_fita`, para quem o `Todos` é o zero). Curar só o
def cabe_o_todos(mesa: Sequence[Any] | None = None) -> bool:
    """Se o chip `Todos` entra na fita: só com MAIS DE UM controle na mesa.

    `None` cai nos `CONECTADOS` do desenho, que é o mesmo padrão de `fita()`.

    O TIPO É `Sequence`, E NÃO `list[dict]`, porque a regra é sobre a CONTAGEM e
    só sobre ela. Quem pergunta nem sempre tem itens de mesa à mão — o
    `jogar_vivo._indice_na_fita` tem as CHAVES de remontagem, uma por controle —
    e obrigá-lo a forjar dicionários vazios só para caber na anotação seria a
    régua mentindo sobre o que precisa.
    """
    return len(CONECTADOS if mesa is None else mesa) > 1


def escolha_da_fita(ativo: str,
                    mesa: list[dict[str, Any]] | None = None) -> tuple[bool, str]:
    """Se o `Todos` entra, e QUEM fica marcado. Devolve `(mostra, ativo)`."""
    lista = CONECTADOS if mesa is None else mesa
    if cabe_o_todos(lista):
        return True, ativo
    if lista:
        return False, str(lista[0]["pref"])
    return False, ativo


def acesos_da_fita(ativo: str, mesa: list[dict[str, Any]] | None = None, *,
                   escolhe: bool = True) -> frozenset[str]:
    """Os chips que acendem na fita: o `pref` de cada um, e `"todos"` quando o `Todos` acende.

    O chip aceso é quem está ESCOLHIDO (O-SELECIONAR-ACENDE-QUEM-ESTA-ESCOLHIDO-01,
    pedido de 29/09/2026): um controle escolhido acende só ele; o `Todos` escolhe
    os quatro e acende os quatro com ele; numa aba que não escolhe (`escolhe=False`),
    o ajuste vale para todos, e todos nascem acesos, qualquer que seja o `ativo` que o
    piloto mande. Com um controle só não há `Todos`, e o único acende.

    É a ÚNICA pergunta: o `fita()` e os escritores das abas 06 e 09 a fazem, e nenhum
    escreve `on` por conta própria.
    """
    lista = CONECTADOS if mesa is None else mesa
    prefs = frozenset(str(c["pref"]) for c in lista)
    mostra_todos, ativo = escolha_da_fita(ativo, lista)
    todos = frozenset({"todos"}) if mostra_todos else frozenset()
    if not escolhe or ativo == "todos":
        return prefs | todos
    return frozenset({ativo})


#   * as abas 06 e 09 perdiam `data-campo="fita-chips"`, e com ele o endereço
TAG_DO_CHIP = "label"

CAMPO_DA_FITA = "fita-chips"


ABAS_QUE_ESCOLHEM: frozenset[str] = frozenset({
    "01-jogar", "02-controles", "08-conexoes"})


def a_fita_escolhe(pagina: str) -> bool:
    """Se a fita daquela aba ESCOLHE controle, ou é só leitura."""
    nome = pagina[:-5] if pagina.endswith(".html") else pagina
    if nome not in {a for _, a in ABAS}:
        prefixo = nome.split("-", 1)[0]
        if prefixo in {a.split("-", 1)[0] for _, a in ABAS}:
            raise SystemExit(
                f"ERRO: {pagina!r} não é uma das dez abas, e o número {prefixo} "
                f"é de uma delas — isto é erro de digitação. Quem responde "
                f"'esta aba escolhe controle?' é `monta.ABAS_QUE_ESCOLHEM`, e "
                f"ele só conhece as dez de `monta.ABAS`.")
        return False
    return nome in ABAS_QUE_ESCOLHEM


GESTO_DA_FITA = "escolher-na-fita"


def _endereco_do_chip(pref: str, inerte: bool) -> str:
    """O que faz o chip CLICAR — e o vazio que o mantém honesto quando não deve."""
    if inerte:
        return ""
    return (f' data-gesto="{GESTO_DA_FITA}" data-pref="{pref}"'
            f' data-controle=""')


#: OS DOIS MODOS DE UMA ABA — pedido de 06/10/2026, nas abas Iluminação e
#: Gatilhos, que falam igual: Modo automático (o player não interage com os
#: botões da página) e Modo personalizado (que permite alterar as cores). Um par de botões na faixa do
#: título, com a mesma largura; o escolhido acende. No Automático, a folha da aba
#: deixa as colunas paradas pelo `data-modo-da-aba` do quadro (o pacote o escreve).
MODO_AUTOMATICO = "automatico"  # (noqa-acento: valor de atributo)
MODO_PERSONALIZADO = "personalizado"
ROTULO_DO_MODO = {MODO_AUTOMATICO: "Modo automático",
                  MODO_PERSONALIZADO: "Modo personalizado"}

CSS_DO_PAR_DE_MODOS = """
  .par-modo{margin-left:auto;display:inline-grid;grid-template-columns:1fr 1fr;gap:6px}
  .par-modo button{height:22px;padding:0 10px;border-radius:6px;font-family:inherit;
    font-size:11.5px;cursor:pointer;border:1px solid var(--linha);background:transparent;
    color:var(--texto-suave);white-space:nowrap}
  .par-modo button:hover:not(.on){border-color:var(--comment);color:var(--fg)}
  .par-modo button.on{border-color:var(--purple);background:var(--sel-bg);color:var(--fg);
    font-weight:600;cursor:default}
"""


def par_de_modos(gesto: str, modo: str) -> str:
    """Os dois botões do modo da aba, com o `modo` aceso (o gesto leva o `data-modo`)."""
    botoes = []
    for chave, rot in ROTULO_DO_MODO.items():
        aceso = chave == modo
        classe = ' class="on"' if aceso else ""
        botoes.append(
            f'<button{classe} data-gesto="{gesto}" data-modo="{chave}"'
            f' data-campo="{gesto}-{chave}" data-hef-alvo="classe"'
            f' data-hef-atributo="aria-pressed"'
            f' aria-pressed="{str(aceso).lower()}">{rot}</button>')
    return ('<span class="par-modo" role="group" aria-label="Modo da aba">'
            + "".join(botoes) + "</span>")


#: A dica do botão do Modo automático: o que ele faz, curto, sem nenhum número do estilo.
DICA_DO_MODO_AUTO = "O jogo manda; o estilo do perfil ajusta o resto"


def modo_auto(gesto: str, ligado: bool = False, governa: str = "",
              dica: str = DICA_DO_MODO_AUTO) -> str:
    """O Modo automático como UM botão (A-BASE-COMUM-DAS-ABAS-01, 13/10/2026).

    Ligado (`aria-pressed="true"`), o botão fica ciano e a área que o `governa` (um seletor
    CSS) esmaece e para de aceitar clique — a base comum faz isso pelo `aria-pressed`, no desenho
    e no produto. O clique alterna os dois modos no MESMO gesto de hoje (`data-modo` leva o
    que o clique PEDE, e a base o mantém no sentido contrário do estado).
    O campo é o do botão «automático» do par antigo, e o piloto o pinta pelo `aria-pressed`.
    """
    pedido = MODO_PERSONALIZADO if ligado else MODO_AUTOMATICO
    alvo = f' data-governa="{html.escape(governa, quote=True)}"' if governa else ""
    return (f'<button class="modo-auto" type="button" data-gesto="{gesto}"'
            f' data-modo="{pedido}" data-campo="{gesto}-{MODO_AUTOMATICO}"'
            f' data-hef-alvo="classe" data-hef-classe="ligado"'
            f' data-hef-atributo="aria-pressed" aria-pressed="{str(ligado).lower()}"'
            f' data-dica="{html.escape(dica, quote=True)}"{alvo}>'
            f'<span class="p"></span>{ROTULO_DO_MODO[MODO_AUTOMATICO]}</button>')


def rotulo_do_chip(c: dict[str, Any]) -> str:
    """O rótulo curto com a VIA marcada, para o chip da fita."""
    texto = rotulo(c, "curta")
    via = str(c.get("via") or "")
    if via and texto.endswith(via):
        return f'{texto[:-len(via)]}<span class="via">{via}</span>'
    return texto


# NO MODO NATIVO A FITA FICA CINZA E MUDA (DESLIGAR-O-HEFESTO-01, opção a): quem
# manda é o jogo, e a fita só mostra quem está conectado. Esta camada cobre a
# fita inteira, não aceita clique e carrega a dica; fora do Nativo nasce escondida.
DICA_DA_FITA_NO_NATIVO = (
    '<span class="so-no-nativo" title="Com o Hefesto desligado, o jogo manda: '
    'aqui só se vê quem está conectado."></span>')


def fita(ativo: str = "todos", inerte: bool = False,
         mesa: list[dict[str, Any]] | None = None) -> str:
    """Os chips da fita, um por controle da mesa, gerados.

    ANTES ELES ERAM DOIS, DIGITADOS NO `topo.html` — dois `<span>` com o texto e
    a cor escritos à mão (`c-red`, `c-blue`), e uma classe de cor por modelo. Com
    quatro na mesa isso vira quatro classes; com os 28 do CSV, vinte e oito. A
    cor sai do desenho, e o chip sai da mesa.

    `ativo`: "todos" ou o `pref` de um controle. `inerte`: a aba não ajusta por
    controle e vale para todos, então todos os chips nascem acesos e a fita não
    tem balão (`acesos_da_fita`).

    `mesa`: OS CONTROLES DE VERDADE, quando quem chama os tem. O padrão `None`
    usa os `CONECTADOS` do mockup, e é por isso que as dez páginas geradas saem
    byte a byte iguais ao que o usuário aprovou — o desenho não mudou.

    ELE PRECISOU EXISTIR, e o defeito estava na tela em 01/09/2026: com UM
    controle no cabo, o piloto pintava o card certo (`Starlight Blue · USB`) e o
    topo certo (`1 controle: 1 USB · 0 BT`), mas a fita continuava mostrando
    `P1 · Cosmic Red · USB` e `P2 · Starlight Blue · BT` — os dois do mockup. O
    controle do usuário aparecia na fita como P2 NO RÁDIO enquanto estava no cabo.

    É a quarta vez que este defeito aparece nesta casa, e sempre com a mesma
    forma: **uma frase que nomeia um controle que não está na mesa**. As outras
    três foram o botão de jogador da Iluminação, o primário da Navegação e o
    censo da Conexões.

    **E ELE VOLTOU EM 02/09/2026, por defeitos que moram AQUI.** O usuário viu e
    disse: *"o controle identificado em todas ta completamente errado"*. Medido
    com os dois controles do usuário na mesa (um `usb`, um `bt`), o daemon
    respondendo em 1 ms:

        identidade_de()  →  "White"  ·  "BT"     ← certo, e o card já mostrava
        a FITA mostrava  →  "P1 • Cosmic Red • USB"  ·  "P2 • Starlight Blue • BT"

    Os dois defeitos de CONTEÚDO, e os dois são desta função (o terceiro, que é
    de REPINTURA, está na nota do `return` lá embaixo):

    1. **O NOME VINHA DE `c["nome"]`**, que na mesa viva é o nome do PLÁSTICO
       (`mesa_viva.mesa_do_estado`) — e vale `"Não sei"` quando a cor não foi
       lida. Quem sabe nomear um controle é `pacotes.identidade_de`, e a ordem
       dele é *o que O usuário nomeou > o modelo decodificado > o transporte só*,
       NUNCA a posição. Agora é ele quem responde.
    2. **A COR NÃO LIDA DERRUBAVA A FITA INTEIRA.** `cor_da_zona("")` levanta
       `SystemExit` — e no rádio a cor do plástico NUNCA chega (o mapa diz:
       `identidade.cor_do_aparelho`, `radio_aciona = não`). Com um controle no
       BT, a fita viva morria a cada tique e a tela ficava com os dois chips do
       mockup para sempre. Sem cor lida o chip perde a borda colorida — é a
       regra de produto: *"se não tá mostrando agora, não tem info pra mostrar no
       produto"*. (O `title` que dizia por quê saiu em 13/09/2026: ver o laço.)

    O TEXTO DO CHIP SAI DE `rotulo(c, "curta")`, e não de um f-string próprio:
    a gramática do rótulo já tinha dono, e ter uma segunda cópia aqui é
    exatamente a cicatriz das *"cinco gramáticas na mesma janela"* que aquela
    função nasceu para fechar.
    """
    balao = ("" if inerte else
             ' title="O que você mudar nesta aba vai para o controle escolhido aqui."')
    lista = CONECTADOS if mesa is None else mesa
    mostra_todos, _ = escolha_da_fita(ativo, lista)
    acesos = acesos_da_fita(ativo, lista, escolhe=not inerte)
    chips: list[str] = []
    if mostra_todos:
        chips.append(f'<label class="chip{" on" if "todos" in acesos else ""}"'
                     + _endereco_do_chip("todos", inerte) + ">Todos</label>")
    for c in lista:
        on = " on" if str(c["pref"]) in acesos else ""
        nome = c["nome"] if mesa is None else identidade_do_chip(c, mesa)
        # `identidade_de` é «o transporte sozinho» — honesto num card, que só
        if mesa is not None and nome in (_degrau_do_transporte(c), c["via"],
                                         TRAVESSAO):
            nome = ""
        slug = str(c.get("cor") or "")
        pintado = f' style="--plastico:{cor_da_zona(slug)}"' if slug else ""
        porque = "a borda é a cor do plástico" if slug else ""
        dica = " — ".join(str(x) for x in (nome, porque) if x)
        com_dica = f' title="{dica}"' if dica else ""
        chips.append(
            f'<label class="chip{" plastico" if slug else ""}{on}" data-campo="fita-chip"'
            + _endereco_do_chip(str(c["pref"]), inerte)
            + f'{pintado}{com_dica}>'
            + rotulo_do_chip({**c, "nome": nome}) + "</label>")
    #
    rotulo = f"<span>{ROTULO_DA_FITA}</span>" if lista else ""
    return (f'<div class="fita{" inerte" if inerte else ""}"{balao}>\n'
            f"      {rotulo}\n      " + "\n      ".join(chips)
            + f'\n      {DICA_DA_FITA_NO_NATIVO}\n    </div>')


def identidade_do_chip(c: dict[str, Any], mesa: list[dict[str, Any]]) -> str:
    """Como este controle se chama no chip — pelo DONO, nunca por leitura nova.

    Delega a `pacotes.identidade_de`, que é o dono desde a ROTA-A (02/09/2026) e
    já acerta: *o que O usuário nomeou > o modelo decodificado > o transporte só*, e
    NUNCA a posição — a posição foi o que fez o mesmo controle mudar de nome
    quando o segundo entrou na mesa.

    **A TRADUÇÃO DE UMA CHAVE, e ela é a única lógica daqui:** `identidade_de`
    lê `transport` (o nome CRU do daemon) e o item da mesa guarda o mesmo fato
    como `transporte` (`mesa_viva.mesa_do_estado:328`). Sem esta linha o último
    degrau da ordem — «o transporte sozinho» — cai no travessão, e o controle
    do rádio aparece como `P2 • — • BT` quando podia dizer `P2 • BT • BT`.
    O certo é `identidade_de` aprender as duas grafias, ou a mesa publicar a do
    daemon; enquanto isso não acontece, a tradução mora aqui, à vista.

    O IMPORT É TARDIO de propósito: `pacotes/a04_iluminacao.py` importa `monta`,
    e um import no topo fecharia o ciclo. Ele só acontece quando há mesa VIVA —
    os dez geradores passam `mesa=None` e nunca chegam aqui.
    """
    from hefesto_dualsense4unix.interface.pacotes import identidade_de

    return identidade_de({**c, "transport": c.get("transporte", "")}, mesa)


def _degrau_do_transporte(c: dict[str, object]) -> str:
    """O último degrau de `identidade_de`: o transporte sozinho, na palavra dele.

    Existe para que a fita **pergunte** em vez de digitar. É a mesma leitura que
    `pacotes/a02_controles.py:991` faz para o cabeçalho do card.
    """
    from hefesto_dualsense4unix.interface.pacotes import identidade_de

    return str(identidade_de({"transport": c.get("transporte", "")}) or "")


def glifo(nome: str, ativo: bool = False, tam: int = 24) -> str:
    """Os mesmos SVGs de glifo que a aba Status usa — 27 peças, com versão acesa."""
    titulo = nome_do_glifo(nome)
    arq = GLIFOS / f"{nome}{'_active' if ativo else ''}.svg"
    x = arq.read_text()
    x = re.sub(r'<\?xml[^>]*\?>\s*', '', x)
    x = re.sub(r'<!--.*?-->', '', x, flags=re.S)
    x = x.replace('stroke="#f8f8f2"', 'stroke="currentColor"')
    x = x.replace('fill="#f8f8f2"', 'fill="currentColor"')
    x = x.replace('stroke="#bd93f9"', 'stroke="currentColor"')
    x = x.replace('fill="#bd93f9"', 'fill="currentColor"')
    x = x.replace('<svg ', f'<svg class="gl" width="{tam}" height="{tam}" ', 1)
    x = re.sub(r'\s+width="32"\s+height="32"', '', x).strip()
    i = x.index(">", x.index("<svg "))
    return f'{x[:i + 1]}<title>{html.escape(titulo)}</title>{x[i + 1:]}'

CSS_GLIFO = """
  /* Os glifos são os MESMOS SVGs da aba Status (assets/glyphs, 27 peças).
     `currentColor` faz cada um herdar a cor da linha em que está. */
  .gl{display:inline-block;vertical-align:-6px;flex:0 0 auto}
  .gls{display:inline-flex;align-items:center;gap:5px}
  .gls .mais{color:var(--comment);font-size:11px;margin:0 1px}
"""

CSS_LUZINHAS = """
  /* AS DUAS CORES VIAJAM COM AS LÂMPADAS, e antes não viajavam: elas eram
     declaradas em `.luzes,.troca`, dentro do CSS da Iluminação. A Controles
     escreveu a mesma classe em 29/08 e as cinco lâmpadas saíram SEM COR — o
     `var()` sem declaração não pinta e não avisa. Um bloco reusável que depende
     de um seletor da aba que o pariu não é reusável; agora ele se basta. */
  .luzinhas{--led-apagado:#4a4f5c; --led-aceso:#e8ecf5;
            display:flex;gap:3px;align-items:center}
  .luzinhas i{width:6px;height:6px;border-radius:2px;background:var(--led-apagado);display:block}
  .luzinhas i.on{background:var(--led-aceso);box-shadow:0 0 6px rgba(255,255,255,.85)}
  .luzinhas .vao{width:4px;background:none;box-shadow:none}
"""


def luzinhas(jogador: int, extra: str = "") -> str:
    """As cinco lâmpadas do indicador, no padrão CANÔNICO do produto."""
    acesas = "" if jogador == 0 else PADRAO_JOGADOR[jogador]
    saida = []
    for n in "12345":
        if n in "25":
            saida.append('<span class="vao"></span>')
        saida.append('<i class="on"></i>' if n in acesas else "<i></i>")
    return f'<span class="luzinhas{extra}">' + "".join(saida) + "</span>"


CSS_POPUP = """
  /* ---- AS TELAS NOVAS (:target, sem script) ---- */
  .tela-nova{display:none;position:fixed;inset:0;z-index:60;
             background:rgba(9,10,15,.72);align-items:center;justify-content:center}
  .tela-nova:target{display:flex}
  /* ---------------------------------------------------------------------
     A CAIXA TEM TETO, E O TETO É A JANELA DO PRODUTO (28/08/2026).
     A `.tn-cx` não tinha `max-height` nem `overflow`: se o conteúdo crescesse,
     ele saía da tela SEM barra de rolagem e SEM aviso — o defeito não aparecia
     porque régua nenhuma desta casa mede pop-up (a `.tela-nova` é
     `position:fixed`, fora do `.miolo` que as réguas varrem).
     717px = os 757px da janela do Hefesto menos 20px de respiro em cima e
     embaixo; o `min()` com `100vh` cobre quem abrir numa janela menor que isso.

     QUEM ROLA É A MOLDURA DA TABELA, e não o corpo — e isso é uma CORREÇÃO, não
     uma escolha de gosto. A primeira versão pôs `overflow-y:auto` no `.tn-corpo`
     inteiro, e o `overflow` recorta TODO descendente posicionado, role ou não:
     a dica de "Velocidade de cursor" do Point-and-click, que tem 330×123px e
     abre para fora da caixa, apareceu CORTADA em dois lados. Medido em 28/08.
     A moldura é a única parte que cresce com o número de linhas, e não há uma
     só dica dentro dela — a do título mora no `.tn-topo` e as do Point-and-click
     no `.tn-vel`, ambos fora. Assim título, frase, velocidades e o rodapé com o
     "Guardar" ficam sempre à vista, e nenhuma dica é recortada.
     --------------------------------------------------------------------- */
  .tn-cx{width:660px;max-width:94vw;background:var(--panel);border-radius:11px;
         border:1px solid var(--border-forte);box-shadow:0 26px 70px rgba(0,0,0,.62);
         display:flex;flex-direction:column;max-height:min(717px,calc(100vh - 40px))}
  .tn-topo{display:flex;align-items:center;gap:9px;padding:14px 18px 0;flex:none}
  .tn-tit{font-size:14.5px;font-weight:600;color:var(--purple)}
  .tn-x{margin-left:auto;width:26px;height:26px;border-radius:6px;text-decoration:none;
        border:1px solid var(--border-forte);color:var(--texto-mudo);font-size:14px;
        display:flex;align-items:center;justify-content:center}
  .tn-x:hover{border-color:var(--red);color:var(--red)}
  /* `min-height:0` nos dois níveis não é enfeite: sem ele um item de flex-column
     não encolhe abaixo do `min-content`, e a rolagem interna nunca chega a
     existir — o teto passaria a cortar em silêncio, que é o defeito de origem. */
  .tn-corpo{padding:11px 18px 16px;display:flex;flex-direction:column;min-height:0}
  /* `scrollbar-gutter:stable` NÃO é enfeite, e a razão foi medida em 29/08/2026:
     a moldura da `#mapear-entradas` escondia 180px — a confissão INTEIRA e a
     segunda pergunta da sala — e `offsetWidth - clientWidth` dava ZERO, porque
     no Linux a barra do Chrome é overlay e não ocupa largura. Havia rolagem e
     nada na tela dizia isso: quem abrisse a pop-up leria uma tela completa que
     não estava completa. O `.miolo` do esqueleto já resolve assim
     (`topo.html:134`); a moldura da pop-up não tinha herdado a lição. */
  .tn-corpo > .moldura{overflow-y:auto;min-height:0;scrollbar-gutter:stable}
  /* A BARRA, E O QUE O INSTRUMENTO NÃO CONSEGUE PROVAR (29/08/2026).
     O `scrollbar-gutter:stable` reserva os 9px — isso está MEDIDO
     (`offsetWidth - clientWidth == 9`). O `scrollbar-color` e as regras
     `::-webkit-scrollbar` abaixo pedem que ela seja pintada.

     **O QUE NÃO CONSEGUI PROVAR:** o Chrome headless do `olhar.py` NÃO pinta a
     barra na foto — amostrei a coluna dela pixel a pixel e só há cor de fundo,
     inclusive com `--disable-features=OverlayScrollbar`. Três tentativas.
     Logo: a rolagem existe e funciona, mas **nenhuma foto desta casa prova que
     a pessoa vê que há mais abaixo**. Quem for validar isto valida em navegador
     de verdade, ou no produto — onde quem desenha é o GTK, cuja barra é sólida.

     POR QUE ISSO IMPORTA: a `#mapear-entradas` esconde 140px, e entre eles está
     a confissão inteira ("o que eu não consegui conferir neste desenho"). Uma
     tela que parece completa e não está é a classe de defeito que esta casa
     mais paga. O número está na mesa; encolher o conteúdo é decisão de produto. */
  .tn-corpo > .moldura{scrollbar-width:thin;
                       scrollbar-color:var(--border-forte) var(--panel-2, #21222c)}
  .moldura::-webkit-scrollbar{width:9px}
  .moldura::-webkit-scrollbar-track{background:var(--panel-2, #21222c);border-radius:5px}
  .moldura::-webkit-scrollbar-thumb{background:var(--border-forte);border-radius:5px}
  .tn-frase{font-size:11.5px;color:var(--texto-mudo);line-height:1.55;margin-bottom:11px}
  .tn-rod{display:flex;gap:var(--gap);padding:0 18px 16px;flex:none}
  .tn-rod .btn{flex:1;text-decoration:none}
  /* a confirmação do rodapé segue os botões, e não a borda da caixa: o
     `left:0/right:0` do `.confirma` mira a caixa de padding do `.tn-rod`, que
     começa 18px antes do primeiro botão. */
  .tn-rod .confirma{left:18px;right:18px}
  .tn-cx .tab td{height:23px}
  .tn-cx .campo-linha{height:22px}
  /* dentro de uma pop-up a dica abre para a ESQUERDA: a caixa tem 660px e
     22+330 a partir do rótulo passava da borda direita dela. Medido na
     Point-and-click, e vale para toda `.tn-cx` pela mesma aritmética. */
  .tn-cx .dica{left:auto;right:22px}
"""

CSS_FOLHA = """
  /* ======== A FOLHA DA D-02 E DA D-03 — as duas peças das dez abas ======== */

  /* ---- S-04 · O LUGAR QUE PERDE O DONO AO VIVO NÃO OFERECE CONTROLE ----
     QUEIXA, 05/09/2026: *"temos que entender se só tem um controle
     conectado só aparece config daquele. aba cinco tá errada."*

     E ESTAVA, e não era só a cinco. Medido na tela viva com UM controle ligado:
     a 02 servia 11 widgets por coluna, a 03 servia 7 nas QUATRO, a 04 servia 16
     e a 08 servia 3 — todos clicáveis, todos para aparelhos que não estão aqui.
     A 05 mostrava até um interruptor de motor ACESO em laranja.

     POR QUE O DESENHO NÃO PODIA PREVER: o mockup assa duas colunas ligadas
     (decisão de 31/08 — *"deixa os outros espaços a mostra ainda mas
     cinza"*). Quem descobre que só há UMA é o produto, ao vivo, e a diferença
     entre "o desenho disse vazio" e "o produto descobriu vazio" era o buraco.

     O MECANISMO JÁ EXISTIA E NINGUÉM O HONRAVA: `pacotes.__init__` calcula os
     `vazios` e o piloto marca cada lugar com `data-conectado="nao"` mais a
     classe `off`. O travessão dos CAMPOS já chegava (`dict.fromkeys(chaves,
     TRAVESSAO)`). O que não chegava era o sumiço dos WIDGETS — um botão não é
     campo de texto, e nenhum `—` o apaga.

     AQUI E NÃO EM CADA ABA, pela razão desta folha inteira: uma peça que cada
     aba precisa lembrar de pedir é uma peça que alguma aba esquece. Foram
     QUATRO abas com o mesmo defeito e o mesmo remédio.

     `:not(.vazia)` NÃO É DETALHE: o piloto marca `data-conectado="nao"` também
     nas que já NASCEM vazias, e essas trazem o `<span class="nada">` por
     dentro. Sem a exclusão, esta regra esconderia o travessão delas e a coluna
     ficaria em branco — a régua trocada por outra pior.

     O CINZA É POR ESCONDER E NÃO POR `disabled`, ao contrário da S-03 logo
     abaixo, e a diferença tem razão: ali o botão EXISTE e recusa dizendo o
     porquê; aqui não há aparelho sobre o qual dizer coisa alguma. Um botão
     cinza num lugar vazio ainda promete que ali cabe uma escolha. */
  [data-controle][data-conectado="nao"]:not(.vazia) button,
  [data-controle][data-conectado="nao"]:not(.vazia) input,
  [data-controle][data-conectado="nao"]:not(.vazia) select,
  [data-controle][data-conectado="nao"]:not(.vazia) textarea,
  [data-controle][data-conectado="nao"]:not(.vazia) [contenteditable]{
    display:none !important}
  /* E O QUE SOBRA FICA APAGADO — o rótulo e os números que o travessão do
     pacote já escreveu. Sem isto o nome do plástico continuaria colorido em
     cima de uma coluna sem aparelho. */
  [data-controle][data-conectado="nao"]:not(.vazia){border-color:var(--border-forte)}

  /* O DESENHO DO CONTROLE SOME — 05/09/2026, e a palavra é de produto: *"os svgs não
     deveriam aparecer prós demais controles desconectados"*.

     A VERSÃO ANTERIOR DESTA REGRA PINTAVA o SVG de `var(--linha)` em vez de o
     tirar. Era menos do que o usuário pediu e pior do que parecia: um controle
     cinza-chumbo continua sendo um CONTROLE desenhado, e a coluna vazia
     passava a mostrar um aparelho apagado ao lado de três travessões — a tela
     desenhando o que não está aqui. Sumir é a resposta honesta, e é a mesma
     que a S-04 já dava aos botões um parágrafo acima.

     A ALTURA DA FAIXA NÃO CAI JUNTO, e é por isso que a regra é `visibility` e
     não `display`: as colunas dividem a mesma linha de grade, e um `display:
     none` faria a faixa do desenho encolher para a altura do travessão — as
     quatro colunas desalinhariam e a do controle conectado mudaria de tamanho
     conforme a mesa. `visibility:hidden` tira a tinta e guarda o lugar. */
  [data-controle][data-conectado="nao"]:not(.vazia) .ds-svg{
    visibility:hidden !important}

  /* ---- S-03 · O BOTÃO QUE VAI RECUSAR JÁ NASCE CINZA (D-03) ----
     A CARA É A DO `.seg button:disabled`, letra por letra. O que muda é o
     mecanismo: ali o botão está `disabled` de verdade e não recebe clique;
     aqui a classe é só tinta, e o botão continua respondendo — que é o que o
     PO decidiu para a aba 09, e é a única forma de dizer o porquê a quem não
     tem rato na mão. */
  .btn.apagado,.seg button.apagado{
    border-color:var(--border-sutil);color:var(--texto-mudo);cursor:not-allowed}
  .btn.apagado:hover,.seg button.apagado:hover{
    border-color:var(--border-sutil);color:var(--texto-mudo)}

  /* ---- S-02 · A RESSALVA É LINHA FIXA, E SÓ QUANDO EXISTE (D-02) ----
     No repouso ela não ocupa NADA: sem `display:none` a linha vazia continua
     cobrando a altura da fonte, que é o preço que a regra de 30/08
     (*"texto na interface é zero"*) não aceita pagar.

     A peça é o `:empty{display:none}` que a `05-vibracao` e a `06-navegacao`
     já tinham cada uma na sua folha, promovido a peça das dez — com o
     `:has(.nada)` junto, porque as duas metades são a mesma peça: `:empty`
     cobre a linha que nasce vazia e nunca é pintada; `.nada` cobre a que o
     piloto pinta a cada tique com "não há o que dizer". Faltando uma das
     duas, a linha volta a aparecer num dos dois caminhos, calada. */
  .ressalva{font-size:11.5px;line-height:1.5;color:var(--texto-mudo);margin-top:5px}
  .ressalva:empty{display:none}
  .ressalva:has(.nada){display:none}

  /* ---- S-05 · O CHIP DA FITA VIRA CONTROLE, E O CURSOR DIZ ----
     O chip passou de `<span>` a `<label>` em 05/09/2026 (`monta.fita`), e um
     `<label>` sem cursor continua parecendo texto. A regra é `:not(.inerte)`
     porque nas SETE abas em que a fita é leitura ele NÃO clica — e um dedinho
     sobre um chip morto é a mesma promessa vazia por outro meio.

     NENHUM PIXEL MUDA. `cursor` não aparece em foto, e o portão do desenho
     aprovado compara o que se VÊ; a regra existe para o rato do usuário.

     AQUI E NÃO EM CADA ABA, pela razão desta folha inteira: a fita mora no
     esqueleto das dez. A `02-controles` já tinha a sua própria linha desde que
     virou bancada clicável — a dela vira redundante, e redundante é melhor que
     divergente. */
  .fita:not(.inerte) label.chip{cursor:pointer}
"""

NADA_A_DIZER = '<i class="nada"></i>'


def botao_cinza(rotulo: str, campo: str, tom: str = "", razao: str = "",
                extra: str = "") -> str:
    """O botão que a tela JÁ SABE que vai recusar: cinza, com a razão na dica dele.

    A RAZÃO É O `data-dica` DO PRÓPRIO BOTÃO (13/10/2026, A-BASE-COMUM-DAS-ABAS-01): o «?» ao
    lado saiu das dez abas, e a dica da casa abre ao passar o mouse ou focar. O mesmo `campo` que
    acende o cinza escreve a razão (`data-hef-razao` avisa o piloto), e sem razão o botão não
    leva `data-dica` nenhum: o `title` dele volta a falar.
    """
    if not campo:
        raise SystemExit(
            f"ERRO em botao_cinza({rotulo!r}): sem `campo` não há endereço, e "
            f"sem endereço o piloto não tem onde acender o cinza nem onde "
            f"escrever a razão — o botão nasceria congelado no desenho.")
    classes = " ".join(x for x in ("btn", tom, "apagado" if razao else "") if x)
    dica = f' data-dica="{html.escape(razao, quote=True)}"' if razao else ""
    return (f'<button class="{classes}" data-campo="{campo}"'
            f' data-hef-alvo="classe" data-hef-classe="apagado"'
            f' data-hef-atributo="aria-disabled" data-hef-razao="sim"{dica}'
            f'{" " + extra if extra else ""}>{rotulo}</button>')


def ressalva(campo: str, texto: str = "") -> str:
    """A linha curta que explica um valor estranho — e só quando existe (D-02)."""
    if not campo:
        raise SystemExit(
            f"ERRO em ressalva({texto!r}): sem `campo` a linha nasce congelada "
            f"no desenho — e ressalva congelada é a que já mentiu na aba 08.")
    return (f'<div class="ressalva" data-campo="{campo}" data-hef-alvo="html">'
            f'{texto or NADA_A_DIZER}</div>')


_FOLHA = re.compile(r'<style id="cores-do-dualsense-folha">(.*?)</style>', re.S)


def folha_das_cores() -> str:
    """A folha dos **28 modelos inteira**, para quem põe mais de um desenho na"""
    m = _FOLHA.search(DS)
    if not m:
        raise SystemExit(
            "ERRO em folha_das_cores(): o `<style id=\"cores-do-dualsense-folha\">` "
            "sumiu do ds_limpo.svg — rode scripts/gerar_cores_do_dualsense.py")
    return str(m.group(0))


REALCE_PADRAO = "#ff79c6"


def folha_de_realce(var: str = "--realce", padrao: str = REALCE_PADRAO) -> str:
    """A regra CSS que faltava para `apertados=` — a peça inteira acesa."""
    alvo = ":is(path,rect,circle,ellipse,polygon,line,polyline)"
    return (
        f"svg[data-colorway] g.marcada.marcada {alvo}"
        f"{{fill:var({var},{padrao}) !important;"
        f"stroke:var({var},{padrao}) !important}}\n"
        f"svg[data-colorway] g.marcada.marcada"
        f"{{color:var({var},{padrao}) !important}}\n"
        f"svg[data-colorway] g.marcada.marcada .sem-tinta"
        f"{{fill:none !important;stroke:none !important}}"
    )


def _so_o_colorway(x: str, colorway: str) -> str:
    """Do `<style>` gerado, guarda só as regras DESTE modelo."""
    def _corta(m: Any) -> str:
        dentro = m.group(1)
        fica = [l for l in dentro.splitlines()
                if f'data-colorway="{colorway}"' in l or "/*" in l or "*/" in l
                or not l.strip().startswith("svg[")]
        return str(m.group(0)).replace(dentro, "\n".join(fica))
    return re.sub(r'<style id="cores-do-dualsense-folha">(.*?)</style>', _corta, x, flags=re.S)


def _tira_grupo(x: str, gid: str, quem: str) -> str:
    """Arranca o `<g id="{gid}">…</g>` inteiro, e RECUSA se a âncora sumiu."""
    alvo = f'<g id="{gid}"'
    if alvo not in x:
        raise SystemExit(f"ERRO em {quem}: o grupo <g id=\"{gid}\"> sumiu do "
                         f"desenho — não há o que tirar")
    i = x.index(alvo)
    n, j = 0, i
    while True:
        a = x.find("<g", j + 1)
        f = x.find("</g>", j + 1)
        if f < 0:
            raise SystemExit(f"ERRO em {quem}: <g id=\"{gid}\"> não fecha")
        if 0 <= a < f:
            n, j = n + 1, a
            continue
        if n == 0:
            return x[:i] + x[f + len("</g>"):]
        n, j = n - 1, f


def svg(pref: str, colorway: str, classes: str = "ds-svg",
        acesos: tuple[str, ...] = (), jogador: int | None = None,
        luz: str | None = None, apertados: tuple[str, ...] = (),
        lampadas: bool = True, folha: bool = True) -> str:
    """O DualSense, na cor pedida.

    `lampadas=False` arranca as cinco lâmpadas do jogador do desenho.

    `folha=False` arranca o `<style>` das cores do desenho, e é para quem já
    publicou :func:`folha_das_cores` uma vez na página — ver a docstring de lá.
    O `data-colorway` continua sendo escrito, que é o que faz a folha de cima
    alcançar este desenho.

    POR QUE ISSO É UM PARÂMETRO, e não uma regra de CSS. Decisão, 28/08:
    **as lâmpadas do jogador SOMEM dos desenhos pequenos; ficam só nos grandes,
    da Iluminação.** Elas medem 1,15 de 60 unidades do desenho — num cartão de
    62px isso dá **1,06 × 0,36 px**, e na Navegação, com 111px, **1,90 × 0,64 px**.
    Abaixo de um pixel de altura não há contraste que resolva: não é lâmpada
    apagada, é lâmpada que não cabe.

    E APAGAR NÃO ERA TIRAR. Foi o que a volta anterior fez na Jogar — deixou as
    vinte no DOM, pintadas de `--border-forte`, e escreveu que as lâmpadas
    continuavam apagadas, citando uma medição de 1,064 × 0,356 como razão para ficar.
    O número era a razão para SAIR. Quem herda um desenho com o grupo lá dentro
    volta a acendê-lo no dia em que precisar do número do jogador; o grupo fora
    é o que não volta sozinho.

    Quem PASSA `jogador=` está pedindo as lâmpadas acesas — pedir isso com
    `lampadas=False` é contradição, e ela para a geração aqui em vez de deixar
    a aba mentir.
    """
    if jogador and not lampadas:
        raise SystemExit(f"ERRO em svg({pref!r}): jogador={jogador} acende as "
                         f"lâmpadas e lampadas=False as arranca — escolha um.")
    x = _FOLHA.sub("", DS, count=1) if not folha else _so_o_colorway(DS, colorway)
    for i in sorted(set(re.findall(r'id="([^"]+)"', x)), key=len, reverse=True):
        x = x.replace(f'id="{i}"', f'id="{pref}-{i}"').replace(f'url(#{i})', f'url(#{pref}-{i})').replace(f'#{i} ', f'#{pref}-{i} ')
    x = re.sub(r'<svg ([^>]*?)data-colorway="[^"]*"', r'<svg \1', x, count=1)
    x = x.replace('<svg ', f'<svg data-colorway="{colorway}" class="{classes}" ', 1)
    if not lampadas:
        x = _tira_grupo(x, f"{pref}-led-jogador", f"svg({pref!r})")
    for a in acesos:
        x = x.replace(f'id="{pref}-{a}" class="oculta"', f'id="{pref}-{a}" class="oculta acesa"')
    if jogador:
        for n in PADRAO_JOGADOR[jogador]:
            alvo = f'id="{pref}-led-jogador-{n}"'
            if alvo not in x:
                raise SystemExit(f"ERRO em svg({pref!r}): a lâmpada {n} sumiu do "
                                 f"desenho — âncora {alvo}")
            i = x.index(alvo)
            fim = x.index(">", i)
            ini = x.rindex("<", 0, i)
            tag = x[ini:fim]
            m = re.search(r'\sclass="([^"]*)"', tag)
            nova = (tag.replace(m.group(0), f' class="{m.group(1)} led-on"', 1)
                    if m else tag.replace(alvo, f'{alvo} class="led-on"', 1))
            x = x[:ini] + nova + x[fim:]
    for a in apertados:
        alvo = f'id="{pref}-{a}"'
        i = x.find(alvo)
        if i < 0 or not x[x.rindex("<", 0, i):i].startswith("<g "):
            raise SystemExit(f"ERRO em svg({pref!r}): a peça {a!r} não é um "
                             f"<g> deste desenho — âncora <g {alvo}")
        ini, fim = x.rindex("<", 0, i), x.index(">", i)
        tag = x[ini:fim]
        m = re.search(r'\sclass="([^"]*)"', tag)
        nova = (tag.replace(m.group(0), f' class="{m.group(1)} marcada"', 1)
                if m else tag.replace(alvo, f'{alvo} class="marcada"', 1))
        x = x[:ini] + nova + x[fim:]
    if luz:
        x = x.replace(f'<g id="{pref}-lightbar"', f'<g id="{pref}-lightbar" style="--luz:{luz}"', 1)
    return x

def troca(t: str, arq: str, de: str, para: str) -> str:
    """Substitui UMA vez e reprova se a âncora não existir mais."""
    if de not in t:
        raise SystemExit(f"ERRO em {arq}: a âncora sumiu do topo.html —\n  {de}")
    return t.replace(de, para, 1)

PLASTICOS_DO_ESQUELETO = {
    "cosmic-red": "cosmic-red",
    "nova-pink": "nova-pink",
    "starlight-blue": "starlight-blue",
    "galactic-purple": "galactic-purple",
    "midnight-black": "midnight-black",
}

MARCA_DA_FITA = '    <div class="fita'

RECUO_DA_FITA = "    "


# O QUE UMA ABA POR CONTROLE FAZ NO NATIVO (DESLIGAR-O-HEFESTO-01, opção a, 09/10):
# tudo o que a aba grava vira CINZA e não aceita clique (a recusa de verdade é da
# camada, `pacotes.camada`; isto é só o rosto dela), e o que é ATO sem o que
# fazer (Aplicar, Salvar e Importar do rodapé, o `.guardar` de cada coluna) fica invisível, e o Exportar, que só grava um arquivo, segue. Ficam vivos os cinco gestos de `VIVOS_NO_NATIVO`
# (o cadeado, o liga/desliga, os dois modos e o reconectar), e o menu do botão direito
# (`.menu-hefesto`), que é da janela e não da aba. Os seletores usam o
# atributo SEM ASPAS de propósito: réguas contam o endereço com aspas, e o
# `topo.html` é compartilhado, então isto só entra nas cinco páginas.
CSS_DO_NATIVO = """
  body.nativo.por-controle :is([data-gesto],[data-modo],[data-hef-gesto],[data-papel],[data-forca],[data-player],[data-sensor],[data-rota],[data-mudo],[data-mic-modo],[data-v]):not(:is([data-gesto=cadeado],[data-gesto=hefesto],[data-gesto=modo-nativo],[data-gesto=modo-steam],[data-gesto=reconectar],.menu-hefesto *)){
    pointer-events:none;cursor:default;-webkit-appearance:none;appearance:none;
    background:transparent!important;border-color:var(--border-sutil)!important;
    color:var(--comment)!important;font-weight:400!important;box-shadow:none!important}
  body.nativo.por-controle .nativo-nao{pointer-events:none;cursor:default;
    background:transparent!important;border-color:var(--border-sutil)!important;
    color:var(--comment)!important;font-weight:400!important;box-shadow:none!important}
  body.nativo.por-controle :is([data-gesto=cadeado],[data-gesto=hefesto],[data-gesto=modo-nativo],[data-gesto=modo-steam],[data-gesto=reconectar]){pointer-events:auto}
  body.nativo.por-controle .guardar,body.nativo.por-controle .par-modo,
  body.nativo.por-controle .modo-auto,
  body.nativo.por-controle .r-aplicar,body.nativo.por-controle .r-salvar,
  body.nativo.por-controle .r-importar{visibility:hidden}
"""


# O «?» QUE AINDA MORA NAS ABAS (conferência da A-BASE-COMUM-DAS-ABAS-01, 13/10/2026). A base
# tirou a folha dele do `topo.html` e do `CSS_FOLHA`, mas os geradores das abas ainda emitem o
# span (`ISENTOS` de `test_a_base_comum_das_abas.py`, cada um com a sprint da aba como dona): sem
# esta folha, a próxima regeneração deixaria cada «?» cru, sem abrir a dica e sem sumir quando não
# há razão. Ela entra SÓ na página cujo miolo ainda tem o span, e sai daqui junto com o último.
CSS_DO_AJUDA_QUE_SAI = """
  .ajuda{width:17px;height:17px;border-radius:50%;flex:0 0 17px;border:1px solid var(--linha);
    color:var(--texto-mudo);font-size:11px;line-height:15px;text-align:center;cursor:help;position:relative}
  .ajuda:hover,.ajuda:focus{border-color:var(--cyan);color:var(--cyan);outline:none}
  .ajuda:hover .dica,.ajuda:focus .dica,.ajuda:focus-within .dica{display:block}
  .quadro-topo .par-modo + .ajuda.esq .dica{left:auto;right:22px}
  .btn:not(.apagado) + .ajuda.porque,.seg button:not(.apagado) + .ajuda.porque{display:none}
  .ajuda.porque:has(.dica:empty),.ajuda.porque:has(.nada){display:none}
  .ajuda.porque{align-self:center;margin-left:-4px}
  body.nativo.por-controle .par-modo + .ajuda{visibility:hidden}
"""
_AINDA_TEM_O_SPAN = re.compile(r'class=["\']ajuda\b')


def trava_do_nativo(o_que: str) -> str:
    """A peça «O jogo manda» do cabeçalho de um quadro, com cadeado, nascida
    escondida e mostrada por `body.nativo`. `o_que`: sobre o que o jogo manda
    («nos gatilhos», «na luz»...)."""
    return (
        '<span class="trava-nativo" title="Com o Hefesto desligado, o jogo manda '
        f'{o_que}. O que está aqui volta a valer quando ligar, na aba Jogar.">'
        '<svg class="cad" viewBox="0 0 12 12" width="11" height="11" aria-hidden="true">'
        '<path d="M3.6 5.2V3.9a2.4 2.4 0 0 1 4.8 0v1.3" fill="none" stroke="currentColor" '
        'stroke-width="1.2"/><rect x="2.3" y="5.2" width="7.4" height="5.4" rx="1.1" '
        'fill="currentColor"/></svg>O jogo manda</span>')


def corpo_da_pagina(arq: str) -> str:
    """A abertura do `<body>`. O ENDEREÇO `nativo` mora nas dez (o cabeçalho
    comum, `pacotes.topo`, o escreve), e a classe `por-controle` só nas cinco
    abas de `camada.ABAS_POR_CONTROLE` (a mesma lista que a recusa usa): é ela
    que o CSS do Nativo usa para travar o que a aba grava. Quem pinta `body.nativo` é o piloto, a cada tique."""
    # Import LAZY: `pacotes` importa este módulo (ordem própria de import).
    from hefesto_dualsense4unix.interface.pacotes.camada import ABAS_POR_CONTROLE
    classe = "por-controle" if f"{arq}.html" in ABAS_POR_CONTROLE else ""
    marca = f' class="{classe}"' if classe else ""
    return (f'<body{marca} data-campo="nativo" data-hef-alvo="classe" '
            'data-hef-classe="nativo" data-hef-quando="sim">')


def monta(arq: str, titulo_aba: str, miolo: str, css_extra: str = "",
          legenda: str = "") -> int:
    """Grava a página. A `legenda` é só o que a página precisa trazer ao fim (o
    que o produto endereça); a nota de revisão do desenho NÃO entra: a página que
    se aprova é a que o produto instala, e a nota vai para a sessão dos desenhos
    (a fonte é a constante `LEGENDA` do gerador de cada aba)."""
    t = TOPO
    t = t.replace("<title>Hefesto — aba JOGAR</title>",
                  f"<title>Hefesto — aba {titulo_aba.upper()}</title>")
    t = troca(t, arq, "</style>", CSS_FOLHA + "\n</style>")
    if css_extra:
        t = t.replace("</style>", css_extra + "\n</style>", 1)
    if '<body class="por-controle"' in corpo_da_pagina(arq):
        t = t.replace("</style>", CSS_DO_NATIVO + "</style>", 1)
    if _AINDA_TEM_O_SPAN.search(miolo):
        t = t.replace("</style>", CSS_DO_AJUDA_QUE_SAI + "</style>", 1)
    for nome, colorway in PLASTICOS_DO_ESQUELETO.items():
        t = re.sub(rf"--{nome}:#[0-9a-fA-F]{{6}}",
                   f"--{nome}:{cor_da_zona(colorway)}", t, count=1)

    # Import LAZY porque este módulo tem ordem de import própria (os `noqa:
    from hefesto_dualsense4unix.interface import mesa_viva as _mesa_viva

    usb = sum(1 for c in CONECTADOS if str(c.get("transporte") or "").lower() == "usb")
    bt = sum(1 for c in CONECTADOS if str(c.get("transporte") or "").lower() == "bt")
    t = re.sub(r'(<div class="conectado"><span class="bolinha">●</span> )[^<]*<b>[^<]*</b>',
               rf'\g<1><b data-campo="conta-b">{_mesa_viva.frase_dos_transportes(usb, bt)}</b>',
               t, count=1)

    t = t.replace('<span class="pa-nome">',
                  '<span class="pa-nome" data-campo="perfil">', 1)

    viva = a_fita_escolhe(arq)
    i = t.index(MARCA_DA_FITA)
    j = t.index("</div>", t.index('class="fita', i)) + len("</div>")
    t = (t[:i] + RECUO_DA_FITA
         + fita(ativo=("p1" if viva else "todos"), inerte=not viva) + t[j:])
    tira = ['  <div class="tira">']
    for nome, a in ABAS:
        existe = onde.pagina(f"{a}.html").exists() or a == arq
        atv = ' ativa' if a == arq else ''
        tira.append(f'    <a class="aba{atv}" href="{a}.html">{nome}</a>' if existe
                    else f'    <span class="aba falta" title="ainda não desenhada">{nome}</span>')
    tira.append('  </div>')
    i = t.index('  <div class="tira">'); j = t.index('\n', t.index('</div>', t.index('class="aba', i)))
    j = t.index('  </div>\n', i) + len('  </div>\n')
    t = t[:i] + "\n".join(tira) + "\n" + t[j:]

    fim = FIM
    if legenda:
        k = fim.index("</body>")
        fim = fim[:k] + legenda + "\n\n" + fim[k:]
    t = t.replace("<body>", corpo_da_pagina(arq), 1)
    doc = com_a_base(t + '  <div class="miolo">\n' + miolo + '\n  </div>\n\n' + fim)
    abertas, fechadas = doc.count("<div"), doc.count("</div>")
    if abertas != fechadas:
        raise SystemExit(
            f"ERRO em {arq}: <div>={abertas} </div>={fechadas} — desbalanceado")
    onde.gravar(f"{arq}.html", doc)
    return abertas
