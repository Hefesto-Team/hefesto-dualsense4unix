"""Monta uma aba a partir do esqueleto VALIDADO da Jogar + o miolo dado.

ONDE ELE ESCREVE, e mudou em 31/08/2026 por decisão dela: na **BANCADA**
(`mockup/`), nunca no publicado. O caminho tem dono único — `onde.py` —, e o
porquê está escrito lá: até 31/08 `monta()` gravava em `layout/`, que é o que
o piloto abre no WebView, então gerar uma aba **já trocava o produto** sem
passar pelo olho dela.
"""
import csv, html, pathlib, re, sys
from typing import Any

import onde

# A RAIZ SAI DE `__file__`, NUNCA CRAVADA. Medido em 28/08/2026: oito
# arquivos desta casa cravavam o caminho absoluto da árvore DELA, e por isso
# rodar uma CÓPIA do gerador REESCREVIA o mockup dela. Aconteceu numa prova:
# o `05-vibracao.html` dela ficou com `--r-motor:56px` porque um agente rodou
# uma cópia noutro diretório. É o mesmo estrago de 25/08, quando o mockup que
# ela ia abrir sumiu do disco na frente dela — e é o que impediria qualquer
# segunda árvore de trabalhar sem tocar na primeira.
#: A PASTA DESTE MÓDULO. Era `parents[2]` (a raiz do repositório) quando este
#: arquivo vivia em `layout/_ferramentas/`; agora ele mora DENTRO do pacote, e o
#: que ele lê — a logo, os assets — mora ao lado. Sair até a raiz aqui faria a
#: logo sumir em toda instalação por `pip`, onde raiz de repositório não existe.
R = pathlib.Path(__file__).resolve().parent

#: A RAIZ DO REPOSITÓRIO, para o que vive em `docs/data/` — o CSV das peças, o
#: das cores. Ela NÃO EXISTE numa instalação por `pip`: o pacote é copiado para
#: dentro do `site-packages`, e não há repositório acima dele.
#:
#: Por isso quem lê daqui tem de TOLERAR a ausência. Um `read_text()` cru
#: derrubaria o import do módulo — e com ele a interface inteira — na primeira
#: máquina que instalasse o Hefesto sem clonar o repositório.
RAIZ_DO_REPO = pathlib.Path(__file__).resolve().parents[3]


def _do_repo(relativo: str) -> str:
    """O conteúdo de um arquivo de `docs/`, ou vazio quando não há repositório.

    Vazio NÃO é silêncio aqui: quem chama recebe uma lista vazia e a tela mostra
    o nome cru da peça em vez do rótulo bonito. É degradação visível, e é melhor
    que um `FileNotFoundError` no import.
    """
    alvo = RAIZ_DO_REPO / relativo
    return alvo.read_text(encoding="utf-8") if alvo.exists() else ""
# A FONTE É A PASTA, não /tmp. As três viviam em /tmp, que é volátil e é uma
# CÓPIA — o `importar.py` a atualiza depois de gravar o original aqui. Quem
# gerasse uma aba entre as duas escritas pegava o desenho velho sem aviso.
_F = pathlib.Path(__file__).resolve().parent
TOPO = (_F / "topo.html").read_text()
# O RECIBO DO RODAPÉ MORA NO `fim.html`, E ELE É O DONO ÚNICO: um arquivo, dez
# abas. (A `01-jogar.html` é mantida à mão e carrega a própria cópia — foi dela
# que este esqueleto saiu; as duas se mantêm iguais na mão.)
#
# ELE ENCURTOU, E NÃO SAIU — `D-O-RECIBO-DO-RODAPE-ENCURTA-NAO-SAI`. Ela escreveu
# "Remover do rodapé de cada página"; perguntada se saía do mockup, do produto ou
# dos dois, respondeu: "deixa ela encurtada tanto lá quanto no mockup". O pedido
# literal dizia remover; a intenção era o tamanho. 96 caracteres viraram 57.
#
# O QUE FICA É O QUE ENSINA: a diferença entre APLICAR (vale agora) e SALVAR
# (grava no perfil), e o NOME do perfil — que é onde a mudança vai cair, a
# informação que faltava e lhe custou semanas. Sai "Anotado." e "Clique em", que
# não ensinam nada. O nome do perfil é requisito, não enfeite: há teste no produto
# que morde exigindo-o na frase.
FIM  = (_F / "fim.html").read_text()
DS   = (_F / "ds_limpo.svg").read_text()

# ---------------------------------------------------------------------------
# A LOGO É LIDA, NUNCA COLADA — 30/08/2026.
#
# Ela estava DIGITADA no `topo.html`, e por isso estava velha: ela redesenhou o
# logotipo (`layout/assets/hefesto-logo.svg`) e as dez páginas continuaram
# com o desenho de antes. Medido no dia: TRÊS desenhos vivos ao mesmo tempo — o
# dela com 6.039 bytes, os 3.466 do `topo.html` em oito páginas, e 2.566 na 02 e
# na 04, paradas há mais tempo. Ela apontou o sintoma sem saber a causa: *"tá as
# duas logos erradas. A da dock e a da interface."*
#
# É a mesma cura que a fita, as cores do plástico e o padrão das lâmpadas já
# receberam: o que tem dono não se digita. O arquivo dela é o dono; aqui só se lê.
#
# A FONTE É O `.svg` DELA, E ESTE ARQUIVO NUNCA O ESCREVE. Há quatro cópias
# idênticas na árvore (`assets/hefesto-logo.svg`, `assets/hefesto-dev-logo.svg`,
# `layout/uploads/` e esta); a que o mockup lê é a de `layout/assets/`,
# que é onde ela salva. Sobrescrever qualquer uma delas é destruir desenho dela —
# já aconteceu uma vez, e ela teve de refazer do zero.
LOGO = (R / "assets/hefesto-logo.svg").read_text()

#: A âncora da logo no esqueleto. É um comentário HTML de propósito: assim o
#: `topo.html` continua abrindo sozinho no navegador sem um SVG fantasma, e a
#: âncora não pode ser confundida com conteúdo.
MARCA_DA_LOGO = '<div class="logo"><!--LOGO--></div>'


def _logo_em_linha(x: str) -> str:
    """O SVG dela, pronto para viver dentro do HTML.

    Duas mudanças, e nenhuma toca o desenho: sai a declaração `<?xml?>` (que
    dentro de HTML não é prólogo, é lixo), e o tamanho da tag vira 40×40. O
    arquivo nasce 512×512 porque é o que o rasterizador do ícone da dock usa;
    quem manda no tamanho final é o `.logo svg` do CSS, mas a tag grande faz o
    logotipo aparecer gigante no instante entre o HTML e a folha de estilo.
    """
    x = re.sub(r"<\?xml[^>]*\?>\s*", "", x).strip()
    return re.sub(r'<svg width="\d+" height="\d+"', '<svg width="40" height="40"',
                  x, count=1)


# A ÂNCORA TEM DE APARECER **UMA VEZ SÓ**, e o `!= 1` é a metade que custou uma
# volta inteira em 30/08/2026.
#
# A ausência já era conhecida: `str.replace` que não casa devolve o texto intacto
# e não avisa — a cicatriz da fita que morreu em silêncio. O que faltava era o
# outro lado. A primeira versão desta cura escreveu a âncora, LITERAL, dentro de
# um comentário do `<style>` do `topo.html` ("a logo é injetada em
# `<div class=…>`"). O `replace(…, 1)` casou com a CITAÇÃO, que vem antes: o
# logotipo dela inteiro foi injetado dentro de um comentário de CSS, e o
# cabeçalho ficou com um `<div>` vazio. As dez páginas geraram sem erro, a
# contagem de `<div>` fechou, e a conferência que procurava `<svg` depois de
# `class="logo"` achou a cópia errada e deu VERDE em dez de dez. Quem viu foi a
# FOTO — o cabeçalho sem logotipo nenhum.
if TOPO.count(MARCA_DA_LOGO) != 1:
    raise SystemExit(f"ERRO: a âncora da logo aparece {TOPO.count(MARCA_DA_LOGO)}× "
                     f"no topo.html (tem de ser 1) —\n  {MARCA_DA_LOGO}")
TOPO = TOPO.replace(MARCA_DA_LOGO,
                    f'<div class="logo">{_logo_em_linha(LOGO)}</div>', 1)

# A ORDEM DA TIRA, e o número do arquivo é a posição. Ela, 28/08/2026: "ABA DE
# SISTEMA TROCA DE LUGAR COM LANÇADORES", e depois, com o preço na mesa,
# "confirma — renumera".
#
# FATO ERRADO, SUBSTITUÍDO no mesmo dia: eu disse a ela que renumerar custaria
# "as 90 sprints renomeadas". **Custou 2 HTML, 2 geradores e 30 citações.** As
# sprints são numeradas POR ONDA (`ONDA-SISTEMA-01`), não por aba — nenhuma
# precisou mudar de nome. Ela decidiu com um preço errado, e o preço certo era a
# favor da decisão dela.
ABAS = [("Jogar","01-jogar"),("Controles","02-controles"),("Gatilhos","03-gatilhos"),
        ("Iluminação","04-iluminacao"),("Vibração","05-vibracao"),("Navegação","06-navegacao"),
        ("Lançadores","07-lancadores"),("Conexões","08-conexoes"),("Sistema","09-sistema"),
        ("Perfis","10-perfis")]

# O PADRÃO das cinco lâmpadas por jogador. É o PADRÃO que diz o número, não uma
# lâmpada individual — e as cinco não são igualmente espaçadas (1 | vão | 3 | vão | 1).
#
# FATO ERRADO, SUBSTITUÍDO (27/08/2026). Esta tabela era digitada aqui e o
# jogador 3 estava escrito `"234"`. O padrão canônico é `"135"` — as duas pontas
# e o centro —, e quem o diz é o produto, em
# `core/led_control.py::player_led_pattern`. Ninguém tinha visto porque os
# mockups só usam os jogadores 1 e 2. A cura não é corrigir o literal: é DEIXAR
# DE TER UM. A tabela agora vem do produto, e diverge no dia em que o produto
# divergir — que é o único jeito de ela não mentir de novo.
# O `src/` É DA RAIZ DO REPOSITÓRIO, não desta pasta. Era `R / "src"` — que
# apontava para `interface/src`, inexistente — desde que este módulo se mudou
# para dentro do pacote em 01/09/2026. O import abaixo só continuava
# funcionando porque o `.envrc-voo` já punha `src/` no `PYTHONPATH`: a
# quebra estava calada, à espera de quem rodasse um gerador sem ele.
# Instalado por `pip` não há repositório, e aí o pacote já está importável.
sys.path.insert(0, str(RAIZ_DO_REPO / "src"))
from hefesto_dualsense4unix.core.led_control import (  # noqa: E402
    player_led_pattern,
)

# `player_slot_color` É REEXPORTADA, e a linha leva `noqa: F401` porque este
# módulo NÃO a usa — quem a usa são QUATRO geradores, que a importam DAQUI:
# `aba02`, `aba04`, `aba06` e `aba08`.
#
# FOI ASSIM QUE OS QUATRO QUEBRARAM, e a causa é mecânica: sem o `noqa`, o
# `ruff --fix` a apaga como *imported but unused*, e os quatro passam a morrer
# em `ImportError: cannot import name 'player_slot_color' from 'monta'`.
# Aconteceu na mudança da interface para dentro do `src/` (`6f7e0119`, cuja
# mensagem diz *"a árvore inteira passa no lint"*) — e aconteceu DE NOVO em
# 01/09/2026, minutos depois de eu a devolver, no `ruff --fix` seguinte.
#
# Da primeira vez ninguém viu, porque a bancada não tinha quem a rodasse. Agora
# tem: `tests/unit/test_os_dez_geradores_rodam.py` acusou os quatro na hora.
from hefesto_dualsense4unix.core.led_control import (  # noqa: E402, F401
    player_slot_color,
)

PADRAO_JOGADOR = {
    n: "".join(str(i + 1) for i, on in enumerate(player_led_pattern(n)) if on)
    for n in range(1, 9)
}

#: AS 54 PEÇAS DE GLIFO, e elas moram na RAIZ do repositório — não ao lado da
#: logo. `R / "assets/glyphs"` (a pasta deste módulo) não existe, e foi o que
#: derrubou os geradores 08 e 09 com `FileNotFoundError` depois da mudança
#: para dentro do pacote.
#:
#: ELAS NÃO PRECISAM ENTRAR NO WHEEL: o glifo é INLINE no HTML gerado, então
#: quem instala por `pip` recebe o desenho dentro da página. Esta pasta é de
#: quem GERA, e gerar exige o repositório.
GLIFOS = RAIZ_DO_REPO / "assets/glyphs"

#: O `docs/data/` DO REPOSITÓRIO, e ele NÃO é `R / "docs/data"`. Seis
#: geradores da bancada montavam esse caminho a partir do `R` — que, desde a
#: mudança para dentro do pacote, é a PASTA DESTE MÓDULO. Eles morriam em
#: `FileNotFoundError: .../interface/docs/data/pecas-do-dualsense.csv`, e
#: ninguém tinha visto porque ninguém os rodou desde a mudança.
DADOS_DO_REPO = RAIZ_DO_REPO / "docs/data"

# O NOME DE CADA PEÇA, EM PORTUGUÊS — e ele é LIDO, não digitado.
#
# Os tooltips dos glifos diziam `cross`, `dpad_up`, `touchpad`, `share`: inglês e
# minúscula, num produto que esta casa escreve em português (há portão que
# reprova), e num dia em que ela mandou caçar exatamente as minúsculas.
#
# O léxico certo já existe e é DO PRODUTO: `docs/data/pecas-do-dualsense.csv`, o
# dono das peças — "mudou aqui, muda em todos". A coluna `glifo` é o nome do
# arquivo em `assets/glyphs/`; a coluna `nome` é como a peça se chama na tela.
# Nada aqui é inventado: Cruz, Círculo, D-pad Cima, Analógico Esquerdo saem de lá,
# e Share, Options, L1 e PS ficam como estão porque é o que está impresso no
# plástico.
#
# POR QUE DERIVADO, E NÃO ESCRITO À MÃO: a mesma razão que o `regerar.py`
# documenta — lista digitada diverge da fonte no primeiro item que entrar ou sair.
# A derivação fecha EXATA hoje: 27 arquivos em `assets/glyphs/` e 27 linhas com
# glifo no CSV, sem sobra de nenhum dos dois lados. Glifo sem linha no CSV PARA a
# geração em `nome_do_glifo()`, em vez de deixar a aba inventar um nome.
def _nomes_das_pecas() -> dict[str, str]:
    linhas = [x for x in _do_repo("docs/data/pecas-do-dualsense.csv").splitlines()
              if not x.startswith("#")]
    return {p["glifo"]: p["nome"] for p in csv.DictReader(linhas) if p["glifo"] != "-"}


NOME_DA_PECA = _nomes_das_pecas()


def nome_do_glifo(nome: str) -> str:
    """Como a peça se chama na tela, e RECUSA o glifo que o CSV não conhece.

    A ausência PARA a geração — é a regra desta casa para âncora que sumiu. Um
    `dict.get(nome, nome)` devolveria o `cross` em inglês de volta, em silêncio,
    que é o defeito que esta tabela existe para matar.
    """
    if nome not in NOME_DA_PECA:
        raise SystemExit(
            f"ERRO em glifo({nome!r}): a peça não tem linha em "
            f"docs/data/pecas-do-dualsense.csv — o nome em português dela não se "
            f"inventa aqui, escreva a linha lá")
    return NOME_DA_PECA[nome]

# ---------------------------------------------------------------------------
# A MESA DE QUATRO. Pedido dela, 27/08/2026: "precisamos que cada aba dessa do
# nosso mockup seja reescrita pra 4 controles conectados (…) seja reescrita
# considerando o nosso mapa. e o sistema de fitas."
#
# Os quatro são os DELA — os que estão nesta bancada, com os códigos que o
# aparelho respondeu (`docs/data/cores-do-dualsense.csv`). Um mockup que mostra
# uma mesa inventada ensina uma mesa que não existe; este mostra a dela.
#
# O NÚMERO DO JOGADOR NÃO É A ORDEM DA LISTA. Ela, 26/08: "o meu controle azul é
# o player 2 — e antes de irmos pro jogo ele tem que ser o player 1"
# (`D-O-NUMERO-DO-JOGADOR-SUBSTITUI-O-DESENHO-DAS-LUZES`). Por isso `jogador` é
# campo, e não índice.
#
# `transporte` é o que decide o que a aba pode prometer: o mapa de canais
# (`docs/data/mapa-controles.csv`) responde por transporte, não por controle.
#: `mascara` é o que o JOGO vê — **não** é o modo, que é como o Hefesto conversa
#: com o controle. A distinção é dela, 28/08: "como vamos integrar o microfone
#: mesmo em outro modo ou máscara (isso é distinção importante)". As três, sem
#: "Automático" (decisão dela): DualSense · Xbox 360 · Nintendo Pro.
#:
#: ELA ESTAVA EM TRÊS LUGARES E DIVERGIA. Medido em 28/08: a Jogar dizia que o P2
#: era DualSense e o P3 Xbox 360; a Controles e a Conexões diziam o contrário, na
#: mesma sessão. A Jogar é literal e ninguém a lê. Aqui há um lugar só.
MASCARAS = ("DualSense", "Xbox 360", "Nintendo Pro")

#: `conectado` — DOIS NA MESA, DOIS FORA. Decisão dela, 31/08/2026:
#:
#:     "Vamos deixar os outros dois controles desconectados, só colocamos algo
#:      como `-` nos campos que deveriam ter algo e escurecemos tudo. Todas as
#:      abas tem que ter só dois controles conectados no momento, o resto fica off."
#:
#: O LUGAR VAZIO CONTINUA NA TELA, e é isso que o campo compra: um controle que
#: some não ensina nada; um que fica apagado, com `-` no lugar do dado, ensina
#: que ali cabe um e que ele não está. É a mesma escolha que a fita do topo já
#: fazia com `.fita.inerte` — o desenho permanece, a informação sai.
#:
#: A ORDEM É A DA MESA, e o desconectado vai para o fim: quem está lá em cima é
#: quem está jogando.
MESA = [
    {"pref": "p1", "jogador": 1, "cor": "cosmic-red",     "nome": "Cosmic Red",
     "via": "USB", "alvo": True,  "mascara": "DualSense",    "conectado": True},
    {"pref": "p2", "jogador": 2, "cor": "starlight-blue", "nome": "Starlight Blue",
     "via": "BT",  "alvo": False, "mascara": "Xbox 360",     "conectado": True},
    {"pref": "p3", "jogador": 3, "cor": "galactic-purple", "nome": "Galactic Purple",
     "via": "BT",  "alvo": False, "mascara": "DualSense",    "conectado": False},
    {"pref": "p4", "jogador": 4, "cor": "white",          "nome": "White",
     "via": "USB", "alvo": False, "mascara": "Nintendo Pro", "conectado": False},
]

#: Os que estão de fato na mesa. Quem conta controle conta ESTES — o cabeçalho, a
#: fita e toda frase que diz "N controles".
#:
#: POR QUE UMA LISTA À PARTE, e não um `MESA` de dois: o desenho precisa dos
#: quatro para pintar os dois lugares vazios. Filtrar na fonte apagaria o lugar,
#: que é justamente o que ela mandou mostrar.
CONECTADOS = [c for c in MESA if c.get("conectado", True)]


#: O separador dos rótulos, num lugar só — ele era um literal dentro de
#: `rotulo()` e passou a ter um segundo leitor quando o número do jogador virou
#: um pedaço à parte, escondível, no título do card da Controles.
SEPARADOR = ' <span class="pt">•</span> '


def rotulo(c: dict[str, Any], forma: str = "completa") -> str:
    """O rótulo de um controle, e ele tem UMA ordem só.

    Decisão dela, 26/08: **marca • player • plástico • transporte**.

    ESTAVA EM CINCO GRAMÁTICAS NA MESMA JANELA, medido em 28/08:
    `Sony • Player 1` em duas linhas (01), `SONY • PLAYER 1 • …` em caixa alta
    (02), a completa em uma linha (08), a curta `P1 • Cosmic Red • USB` (seis
    abas e os chips), e `P1 • Cosmic Red` + `USB • navega o PC` (06). Cinco jeitos
    de dizer a mesma coisa é o que faz a janela parecer montada por pessoas
    diferentes — a mesma cicatriz das quatro alturas de botão.

    `completa` onde há espaço; `curta` nos chips e onde aperta. A caixa é decisão
    de CSS (`text-transform`), nunca do texto: quem escreve em maiúscula no HTML
    tira da pessoa a chance de copiar o nome do plástico.
    """
    if forma == "curta":
        return SEPARADOR.join([f'P{c["jogador"]}', c["nome"], c["via"]])
    if forma == "peca":
        # A `curta` SEM o número do jogador. Ela existe porque o card aberto da
        # Controles deixou de dizer o número no título — decisão dela, 29/08:
        # *"Tirar o número do jogador do título do card"* —, e quem o diz ali
        # agora são as cinco lâmpadas do LED do jogador, dentro do card. A linha
        # FECHADA continua com o número, e tem de continuar: ela não tem lâmpada
        # nenhuma, e sem o número não sobraria quem aquele controle é.
        return SEPARADOR.join([c["nome"], c["via"]])
    return SEPARADOR.join(["Sony", f'Player {c["jogador"]}', c["nome"], c["via"]])


#: AS OITO CORES DE JOGADOR, NO TOM DA CASA — 30/08/2026.
#:
#: Ela: *"essas cores de seleção do lightbar seguem me incomodando profundamente,
#: pq destoam demais do resto do layout (…) pode ser as mesmas cores mas num tom
#: que fiquem em harmonia"*. `core/led_control.player_slot_color` devolve
#: primárias cruas (#0000FF, #FF0000, #00FF00…) — cor de monitor de teste ao lado
#: de uma interface inteira construída na paleta Dracula.
#:
#: MORA AQUI, E NÃO NA `aba04`, porque tem DOIS donos: a guia de cores da
#: Iluminação e a barra de luz da Controles. A primeira volta desta cura ficou só
#: na 04, e o cético mediu o resultado: a 02 continuou pintando #0000FF na barra
#: e escrevendo o hex cru na tela. Uma cura pela metade deixa as duas versões
#: vivas, que é o defeito que a regra da casa existe para matar.
#:
#: O AZUL É O `--starlight-blue` (#7EB8D4) e não o `--cyan`: a paleta Dracula não
#: tem azul próprio, e mapear o azul do player 1 para o ciano fazia DUAS casas da
#: guia caírem na mesma cor — oito casas, sete cores. O cético contou.
TOM_DA_CASA = {
    "#0000FF": "#7EB8D4",   # azul     -> o azul da casa (plástico Starlight Blue)
    "#FF0000": "#FF5555",   # vermelho -> --red
    "#00FF00": "#50FA7B",   # verde    -> --green
    "#FF0080": "#FF79C6",   # rosa     -> --pink
    "#FFFF00": "#F1FA8C",   # amarelo  -> --yellow
    "#00FFFF": "#8BE9FD",   # ciano    -> --cyan
    "#FF8000": "#FFB86C",   # laranja  -> --orange
    "#8000FF": "#BD93F9",   # roxo     -> --purple
}


def tom_da_casa(hexa: str) -> str:
    """O hex cru do produto, no tom da casa. Desconhecido volta como veio."""
    return TOM_DA_CASA.get(hexa.upper(), hexa)


def cor_da_zona(colorway: str, zona: str = "casca-solida") -> str:
    """A cor de uma zona daquele modelo, LIDA do que o gerador escreveu no SVG.

    Não é uma tabela nova: é a mesma folha que pinta o desenho
    (`scripts/gerar_cores_do_dualsense.py`), lida de volta. Digitar o hex aqui
    seria a segunda verdade que o portão `check_cores_do_dualsense.py` existe
    para matar — e foi assim que o Cosmic Red do mockup ficou `#b11f54` enquanto
    a amostragem dizia `#A51C48`.
    """
    m = re.search(rf'svg\[data-colorway="{re.escape(colorway)}"\]\{{([^}}]*)\}}', DS)
    if not m:
        raise SystemExit(f"ERRO: colorway '{colorway}' não existe no SVG gerado. "
                         f"Rode scripts/gerar_cores_do_dualsense.py")
    for par in m.group(1).split(";"):
        k, _, v = par.partition(":")
        if k.strip() == f"--z-{zona}":
            return v.strip()
    raise SystemExit(f"ERRO: zona '{zona}' não existe em '{colorway}'")


# ---------------------------------------------------------------------------
# AS MEDIDAS QUE VALEM EM MAIS DE UMA ABA — vieram do `medidas.py`, que nasceu
# em 31/08 só porque este arquivo estava CONGELADO (dois agentes na mesma
# árvore). Descongelado, elas voltam para o dono natural: o mesmo lugar de onde
# saem a MESA, a fita, o padrão das lâmpadas e as cores do plástico.
# ---------------------------------------------------------------------------
#: O MAIOR RÓTULO DE CADA ABA, medido no Chrome em 31/08/2026. É por ABA, e não
#: um número só para as três — e isso foi ela quem corrigiu, olhando a foto:
#:
#:     "diminui a largura da primeira coluna" (a da Iluminação, apontada em
#:      verde na tela: *"primeira coluna que tem controle, modelo..."*)
#:
#: EU TINHA FEITO UMA LARGURA ÚNICA PARA AS TRÊS, e ela estava errada pela
#: metade. O pedido original era outro — *"tem algo que deixa estranho essa área
#: da primeira coluna"* — e a causa era o RESPIRO ir de 3 a 61px entre abas. Uma
#: largura única igualou o respiro, mas ao preço de dar a TODAS a largura da mais
#: exigente: a Iluminação, cujo maior rótulo tem 73px, ficou com uma coluna de
#: 138 e **65px de vão inútil**. Trocar um estranho por outro não é curar.
#:
#: O QUE É UNIVERSAL É O RESPIRO, e só ele. A largura é conteúdo, e conteúdo é
#: de cada aba. As três continuam lendo como a mesma casa porque o ar entre o
#: fim do texto e a divisa é o mesmo nas três; o que muda é onde o texto começa,
#: e isso ninguém compara entre telas que não estão lado a lado.
#:
#: O comando que mede, e ele não envelhece:
#:     [...document.querySelectorAll('.miolo .rotulos .sec-rot')]
#:       .map(e => e.getBoundingClientRect().width)
MAIOR_ROTULO = {
    "03-gatilhos": 77,      # "Efeito pronto"
    "04-iluminacao": 73,    # "Controle"
    "05-vibracao": 126,     # "Força da vibração"
}

#: O respiro entre o fim do rótulo e a divisa da coluna. É o único número
#: ESCOLHIDO aqui, e o único que vale nas três: ele é o mesmo `--r-passo` que a
#: Gatilhos usa entre linhas, e o ar horizontal e o vertical serem iguais é o
#: que faz a coluna ler como uma caixa em vez de duas medidas que por acaso
#: ficaram perto.
RESPIRO_DO_ROTULO = 12


def larg_rotulos(aba: str, com_glifo: bool = False) -> int:
    """A largura da coluna de rótulos daquela aba.

    `com_glifo=True` só na Gatilhos, onde o L2/R2 ocupa uma trilha própria à
    esquerda do rótulo (decisão dela de 31/08: *"o L2 e o R2 deveriam controlar
    a seção"*). Os três — glifo, vão e rótulo — cabem na conta.
    """
    if aba not in MAIOR_ROTULO:
        raise SystemExit(f"ERRO: não sei o maior rótulo de {aba!r}. Meça antes de "
                         f"usar: um número chutado aqui corta ou quebra a palavra.")
    extra = (GLIFO_DA_SECAO + VAO_DO_GLIFO) if com_glifo else 0
    return extra + MAIOR_ROTULO[aba] + RESPIRO_DO_ROTULO


#: O VÃO ENTRE A COLUNA DE RÓTULOS E A PRIMEIRA COLUNA DE CONTROLE. Ele estava
#: em 12 na Gatilhos e 16 nas outras duas. Este SIM é universal: ele é o mesmo
#: vão que separa duas colunas de controle, e ter dois vãos diferentes na mesma
#: fileira é o que fazia a primeira coluna ler como se fosse de outra tabela.
GAP_DAS_COLUNAS = 16

#: O GLIFO QUE TITULA A SEÇÃO na aba Gatilhos (o L2 e o R2), e o vão dele até o
#: rótulo. Moram aqui porque entram na conta da largura acima: na Gatilhos a
#: coluna é [glifo][vão][rótulo], e os três têm de caber nos mesmos px que as
#: outras duas gastam só com o rótulo.
GLIFO_DA_SECAO = 36
VAO_DO_GLIFO = 10


#: O RÓTULO DA FITA É "Selecionar:" — decisão dela, 31/08/2026:
#: *"Ajustes vão para: aqui pode alterar pra colocar o **Selecionar:** em todas
#: as abas."*
#:
#: ELE MORA AQUI E NÃO NO `topo.html` porque é `monta.fita()` que emite a fita
#: inteira desde 27/08 — o esqueleto guarda só a ÂNCORA. Escrito nos dois, os
#: dois divergem no dia em que alguém mudar um: foi assim que a fita viva morreu
#: sem sintoma, quando o texto do chip mudou e o remendo deixou de casar.
#:
#: "AJUSTES VÃO PARA:" DIZIA DEMAIS E DE MENOS. Demais, porque a fita não governa
#: só ajuste — em seis das dez abas ela é leitura, e ali a frase prometia uma
#: escrita que não acontece. De menos, porque não dizia o VERBO do gesto: o que
#: se faz ali é escolher. `Selecionar:` diz o gesto e cala sobre o efeito, que
#: muda de aba para aba.
ROTULO_DA_FITA = "Selecionar:"


def fita(ativo: str = "todos", inerte: bool = False, titulo: str | None = None,
         mesa: list[dict[str, Any]] | None = None) -> str:
    """Os chips da fita, um por controle da mesa, gerados.

    ANTES ELES ERAM DOIS, DIGITADOS NO `topo.html` — dois `<span>` com o texto e
    a cor escritos à mão (`c-red`, `c-blue`), e uma classe de cor por modelo. Com
    quatro na mesa isso vira quatro classes; com os 28 do CSV, vinte e oito. A
    cor sai do desenho, e o chip sai da mesa.

    `ativo`: "todos" ou o `pref` de um controle. `inerte`: a aba não ajusta por
    controle, e a fita fica esmaecida — é o que o `title` explica.

    `mesa`: OS CONTROLES DE VERDADE, quando quem chama os tem. O padrão `None`
    usa os `CONECTADOS` do mockup, e é por isso que as dez páginas geradas saem
    byte a byte iguais ao que ela aprovou — o desenho não mudou.

    ELE PRECISOU EXISTIR, e o defeito estava na tela em 01/09/2026: com UM
    controle no cabo, o piloto pintava o card certo (`Starlight Blue · USB`) e o
    topo certo (`1 controle: 1 USB · 0 BT`), mas a fita continuava mostrando
    `P1 · Cosmic Red · USB` e `P2 · Starlight Blue · BT` — os dois do mockup. O
    controle dela aparecia na fita como P2 NO RÁDIO enquanto estava no cabo.

    É a quarta vez que este defeito aparece nesta casa, e sempre com a mesma
    forma: **uma frase que nomeia um controle que não está na mesa**. As outras
    três foram o botão de jogador da Iluminação, o primário da Navegação e o
    censo da Conexões.
    """
    t = titulo or ("Esta aba não usa o controle escolhido aqui — os cards são leitura."
                   if inerte else "O que você mudar nesta aba vai para o controle escolhido aqui.")
    # A FITA SÓ MOSTRA QUEM ESTÁ NA MESA — 31/08/2026, decisão dela de deixar dois
    # fora. Um controle desconectado não se escolhe: pôr o chip dele aqui seria
    # oferecer um destino que não existe, e é o oposto do que ela pediu na lista
    # ("ele só fica ativo se surgir controle naquela área").
    chips = [f'<span class="chip{" on" if ativo == "todos" else ""}">Todos</span>']
    for c in (CONECTADOS if mesa is None else mesa):
        on = " on" if ativo == c["pref"] else ""
        # `data-campo` NO CHIP — 03/09/2026, e ele não é enfeite de régua. A
        # identidade do controle vem da FITA, e a fita é escrita pelo produto
        # (`hefesto_vivo._fita`, que troca o `.fita` inteiro a cada tique). Sem
        # um endereço aqui, um leitor não tinha como distinguir este chip de um
        # nome de cor CONGELADO no desenho: o `check_identidade_vem_de_cima`
        # acusava os três valores de cada chip nas dez páginas — 60 dos 134 da
        # bancada. O endereço diz o que é verdade: aqui não mora desenho.
        #
        # SEM COR LIDA, SEM COR NA TELA. `cor_da_zona("")` levanta, e cair fora
        # da fita inteira era o que deixava o mockup na tela pelo rádio (ver a
        # guarda de `hefesto_vivo._fita`). O chip nasce sem `--plastico` e o
        # `.chip.plastico{border-color:var(--plastico, var(--border-forte))}` do
        # esqueleto já tem o recurso neutro — regra dela: campo sem informação
        # não mostra nada.
        slug = str(c.get("cor") or "")
        estilo = f' style="--plastico:{cor_da_zona(slug)}"' if slug else ""
        chips.append(
            f'<span class="chip plastico{on}" data-campo="fita-chip"{estilo}'
            f' title="{c["nome"]} — a borda é a cor do plástico">'
            f'P{c["jogador"]} <span class="pt">•</span> {c["nome"]}'
            f' <span class="pt">•</span> {c["via"]}</span>')
    return (f'    <div class="fita{" inerte" if inerte else ""}" title="{t}">\n'
            f'      <span>{ROTULO_DA_FITA}</span>\n      ' + "\n      ".join(chips)
            + "\n    </div>")

def glifo(nome: str, ativo: bool = False, tam: int = 24) -> str:
    """Os mesmos SVGs de glifo que a aba Status usa — 27 peças, com versão acesa.

    FATO ERRADO, SUBSTITUÍDO (28/08/2026): dizia "19 peças", aqui e no `CSS_GLIFO`.
    Contado: `assets/glyphs/` tem 54 arquivos, que são 27 peças com o par `_active`
    de cada — e as 27 batem uma a uma com as linhas de glifo do
    `docs/data/pecas-do-dualsense.csv`.

    O traço vira `currentColor` para o glifo herdar a cor da linha: numa linha em
    disputa (laranja) o botão fica laranja junto, sem uma segunda cópia do arquivo.

    O NOME DA PEÇA VIAJA COM O GLIFO, em português, no `<title>` do SVG — que é
    como um SVG diz o nome dele. **O atributo `title=` não serve num `<svg>`**: em
    SVG o tooltip é um elemento filho, não um atributo, e quem escreve
    `<svg title="…">` não vê tooltip nenhum.

    POR QUE AQUI, e não em cada aba: o nome do arquivo era a única dica que
    sobrava a quem monta uma aba, e o resultado é o `title="cross"` que a
    `02-controles` mostra 64 vezes. Com o nome saindo daqui, toda aba que use um
    glifo ganha o nome certo sem digitar nada — e nenhuma pode digitar um
    diferente.
    """
    # O NOME PRIMEIRO, e de propósito: o glifo que EXISTE em `assets/glyphs/` mas
    # não tem linha no CSV é o caso que precisa de mensagem própria. Se a leitura
    # do arquivo viesse antes, esse caso passaria e só falharia no fim.
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
    # O `<title>` é o PRIMEIRO filho de propósito: é onde o navegador o procura.
    i = x.index(">", x.index("<svg "))
    return f'{x[:i + 1]}<title>{html.escape(titulo)}</title>{x[i + 1:]}'

CSS_GLIFO = """
  /* Os glifos são os MESMOS SVGs da aba Status (assets/glyphs, 27 peças).
     `currentColor` faz cada um herdar a cor da linha em que está. */
  .gl{display:inline-block;vertical-align:-6px;flex:0 0 auto}
  .gls{display:inline-flex;align-items:center;gap:5px}
  .gls .mais{color:var(--comment);font-size:11px;margin:0 1px}
"""

# ---------------------------------------------------------------------------
# AS CINCO LÂMPADAS DO JOGADOR — e elas mudaram de casa em 29/08/2026, pelo
# mesmo motivo que o `CSS_POPUP` logo abaixo: ganharam um SEGUNDO dono.
#
# Nasceram no `aba04.py`, quando a Iluminação era a única aba que as desenhava.
# Em 29/08 a Controles passou a mostrá-las dentro do card — decisão dela:
# *"Trazer o LED do jogador para ocupar a área faltante"* —, e copiar a função
# e as quatro linhas de CSS para o segundo gerador criaria a segunda verdade
# que esta casa mata: a primeira correção de tamanho, de vão ou de padrão
# valeria numa aba e não na outra, calada.
#
# O PADRÃO JÁ VINHA DE UM LUGAR SÓ (`PADRAO_JOGADOR` ← `core/led_control.py::
# player_led_pattern`); o que estava em dois lugares seria o DESENHO dele.
# ---------------------------------------------------------------------------
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
    """As cinco lâmpadas do indicador, no padrão CANÔNICO do produto.

    `1 | vão | 3 | vão | 1` — as cinco não são igualmente espaçadas, e o
    jogador 1 é a do MEIO. O padrão vem de :data:`PADRAO_JOGADOR`, que sai de
    `core/led_control.py::player_led_pattern`.
    """
    acesas = PADRAO_JOGADOR[jogador]
    saida = []
    for n in "12345":
        if n in "25":
            saida.append('<span class="vao"></span>')
        saida.append('<i class="on"></i>' if n in acesas else "<i></i>")
    return f'<span class="luzinhas{extra}">' + "".join(saida) + "</span>"


# ---------------------------------------------------------------------------
# O CSS DAS POP-UPS — a `.tela-nova`, e ela mora AQUI porque tem DOIS donos.
#
# Ele nasceu dentro do `aba06.py`, quando a Navegação era a única aba com
# pop-up. Em 29/08 a Conexões ganhou as duas dela ("Mapear Entradas" e "Mapear
# Entrada a Entrada"), e copiar as 49 linhas para o segundo gerador criaria
# exatamente a segunda verdade que esta casa mata: a primeira correção de
# altura, de teto ou de rolagem valeria numa aba e não na outra, sem uma linha
# de aviso. Mover custou nada com um consumidor; com dois já seria migração.
#
# Fica ao lado do `CSS_GLIFO` e pela mesma razão que ele: o que vale para mais
# de uma aba não pode ser digitado em cada uma.
#
# O QUE **NÃO** VEIO JUNTO: `.tn-vel` (as duas velocidades do Point-and-click)
# continua no `aba06.py`. Ela é de uma tela só, e CSS de uma tela só num
# arquivo comum é a mesma doença pelo avesso.
# ---------------------------------------------------------------------------
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
     mais paga. O número está na mesa; encolher o conteúdo é decisão dela. */
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


def _so_o_colorway(x: str, colorway: str) -> str:
    """Do `<style>` gerado, guarda só as regras DESTE modelo.

    O SVG traz os 28 — é o que faz o arquivo abrir colorido sozinho e o que o
    banco de provas do mapa usa. Mas uma aba com QUATRO controles carregaria
    quatro cópias dos 28, e o HTML da aba passaria de 300 KB de CSS que ninguém
    lê. Aqui cada cópia fica com o seu, e as cinco linhas do modelo pedido.
    """
    def _corta(m: Any) -> str:
        dentro = m.group(1)
        fica = [l for l in dentro.splitlines()
                if f'data-colorway="{colorway}"' in l or "/*" in l or "*/" in l
                or not l.strip().startswith("svg[")]
        return str(m.group(0)).replace(dentro, "\n".join(fica))
    return re.sub(r'<style id="cores-do-dualsense-folha">(.*?)</style>', _corta, x, flags=re.S)


def _tira_grupo(x: str, gid: str, quem: str) -> str:
    """Arranca o `<g id="{gid}">…</g>` inteiro, e RECUSA se a âncora sumiu.

    Conta o aninhamento em vez de parar no primeiro `</g>`: hoje o grupo das
    lâmpadas não tem `<g>` dentro, mas o `ds_limpo.svg` é redesenhado o tempo
    todo, e uma regex que assume "sem filhos" devolveria meio grupo no dia em
    que ele ganhar um. E `str.replace` que não casa devolve o texto intacto sem
    avisar — a cicatriz da fita que morreu em silêncio. Aqui a ausência PARA a
    geração.
    """
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
        lampadas: bool = True) -> str:
    """O DualSense, na cor pedida.

    `lampadas=False` arranca as cinco lâmpadas do jogador do desenho.

    POR QUE ISSO É UM PARÂMETRO, e não uma regra de CSS. Decisão dela, 28/08:
    **as lâmpadas do jogador SOMEM dos desenhos pequenos; ficam só nos grandes,
    da Iluminação.** Elas medem 1,15 de 60 unidades do desenho — num cartão de
    62px isso dá **1,06 × 0,36 px**, e na Navegação, com 111px, **1,90 × 0,64 px**.
    Abaixo de um pixel de altura não há contraste que resolva: não é lâmpada
    apagada, é lâmpada que não cabe.

    E APAGAR NÃO ERA TIRAR. Foi o que a volta anterior fez na Jogar — deixou as
    vinte no DOM, pintadas de `--border-forte`, e escreveu que "continuam
    apagadas, e eu remedi", citando o 1,064 × 0,356 dela como razão para ficar.
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
    x = _so_o_colorway(DS, colorway)
    for i in sorted(set(re.findall(r'id="([^"]+)"', x)), key=len, reverse=True):
        x = x.replace(f'id="{i}"', f'id="{pref}-{i}"').replace(f'url(#{i})', f'url(#{pref}-{i})').replace(f'#{i} ', f'#{pref}-{i} ')
    # O `data-colorway` JÁ VEM do arquivo (o gerador de cores o escreve, para o
    # SVG abrir colorido sozinho). Dois atributos iguais na mesma tag e o
    # navegador ignora o segundo, em silêncio — a aba pintaria sempre a mesma cor.
    x = re.sub(r'<svg ([^>]*?)data-colorway="[^"]*"', r'<svg \1', x, count=1)
    x = x.replace('<svg ', f'<svg data-colorway="{colorway}" class="{classes}" ', 1)
    if not lampadas:
        x = _tira_grupo(x, f"{pref}-led-jogador", f"svg({pref!r})")
    for a in acesos:
        x = x.replace(f'id="{pref}-{a}" class="oculta"', f'id="{pref}-{a}" class="oculta acesa"')
    if jogador:
        # FUNDE A CLASSE NA TAG, pelo ID, e RECUSA se o id não existir.
        #
        # DEFEITO CURADO em 27/08/2026 (à noite), e ele estava vivo em TODAS as
        # abas: a troca era `str.replace` de `id="…" fill="#c9ced8"` **coladinhos**,
        # e no desenho de hoje vêm SEIS atributos entre os dois (x, y, width,
        # height, rx, style). A `str.replace` não casava, devolvia o texto intacto
        # e **não avisava** — `svg(jogador=N)` nunca acendeu uma lâmpada em aba
        # nenhuma. Cinco agentes o acharam por conta própria no mesmo dia; duas
        # abas mostravam os cinco pontinhos apagados na tela.
        #
        # É a MESMA forma da fita que morreu em silêncio, e por isso a cura tem
        # duas metades: casar só pelo **id** (que é estável) e **reprovar** quando
        # a âncora some. `str.replace` que não casa é o defeito, não a régua.
        for n in PADRAO_JOGADOR[jogador]:
            alvo = f'id="{pref}-led-jogador-{n}"'
            if alvo not in x:
                raise SystemExit(f"ERRO em svg({pref!r}): a lâmpada {n} sumiu do "
                                 f"desenho — âncora {alvo}")
            i = x.index(alvo)
            fim = x.index(">", i)
            ini = x.rindex("<", 0, i)
            tag = x[ini:fim]
            # FUNDE NA CLASSE QUE JÁ ESTÁ LÁ. A lâmpada nasce com `class="peca"`;
            # acrescentar um SEGUNDO atributo `class` faz o navegador ignorar o
            # segundo, sem erro e sem aviso — e foi o que a primeira versão desta
            # cura fez, trocando um defeito silencioso por outro. Medido: `led-on`
            # no HTML e ZERO no `classList` do Chrome.
            m = re.search(r'\sclass="([^"]*)"', tag)
            nova = (tag.replace(m.group(0), f' class="{m.group(1)} led-on"', 1)
                    if m else tag.replace(alvo, f'{alvo} class="led-on"', 1))
            x = x[:ini] + nova + x[fim:]
    for a in apertados:
        x = x.replace(f'<g id="{pref}-{a}"', f'<g class="marcada" id="{pref}-{a}"', 1)
    if luz:
        x = x.replace(f'<g id="{pref}-lightbar"', f'<g id="{pref}-lightbar" style="--luz:{luz}"', 1)
    return x

def troca(t: str, arq: str, de: str, para: str) -> str:
    """Substitui UMA vez e reprova se a âncora não existir mais.

    Uma `str.replace` que não casa devolve o texto intacto e não avisa. Foi
    assim que a fita viva morreu sem sintoma. Toda troca que decide COMPORTAMENTO
    passa por aqui.
    """
    if de not in t:
        raise SystemExit(f"ERRO em {arq}: a âncora sumiu do topo.html —\n  {de}")
    return t.replace(de, para, 1)

#: As variáveis de plástico que o esqueleto declara, e o modelo de cada uma.
#: Só o NOME é desta casa; o valor vem do desenho.
PLASTICOS_DO_ESQUELETO = {
    "cosmic-red": "cosmic-red",
    "nova-pink": "nova-pink",
    "starlight-blue": "starlight-blue",
    "galactic-purple": "galactic-purple",
    "midnight-black": "midnight-black",
}

#: A âncora da fita no esqueleto. É a CLASSE, nunca o texto do chip — a troca
#: antiga procurava o rótulo, e quando ele mudou ela passou a não fazer nada, em
#: silêncio, com a régua verde.
MARCA_DA_FITA = '    <div class="fita'


def monta(arq: str, titulo_aba: str, miolo: str, css_extra: str = "",
          fita_viva: bool = False, legenda: str = "") -> int:
    t = TOPO
    t = t.replace("<title>Hefesto — aba JOGAR (mockup 26/08/2026)</title>",
                  f"<title>Hefesto — aba {titulo_aba.upper()} (mockup 26/08/2026)</title>")
    if css_extra:
        t = t.replace("</style>", css_extra + "\n</style>", 1)
    # a fita: viva quando a aba ajusta por controle
    #
    # AS ÂNCORAS SÃO AS CLASSES, NÃO O TEXTO DO CHIP. A troca antiga procurava
    # `Sony 1 · USB`, que era o rótulo do chip em algum momento de 26/08; quando
    # ele virou `P1 • Cosmic Red • USB` a troca deixou de casar e passou a NÃO
    # FAZER NADA — em silêncio, com a régua verde. As seis abas que ajustam por
    # controle ficaram com o destaque em "Todos" sem ninguém ver. Achado em
    # 27/08; a linha do chip vai mudar de novo, e a classe não.
    # AS VARIÁVEIS DE PLÁSTICO DO ESQUELETO SAEM DO DESENHO. Elas eram cinco
    # hexadecimais digitados no `:root` do `topo.html` — `--cosmic-red:#b11f54` e
    # companhia —, e o primeiro deles estava ERRADO: a amostragem de 27/08
    # devolveu `#A51C48`, distância 17. Quem usa `var(--cosmic-red)` numa aba
    # herdava o hex velho sem saber. Os nomes ficam (há aba que os usa); o VALOR
    # passa a vir do `<style>` que o gerador escreveu no SVG, que é o mesmo lugar
    # de onde a fita e o desenho tiram a cor.
    for nome, colorway in PLASTICOS_DO_ESQUELETO.items():
        t = re.sub(rf"--{nome}:#[0-9a-fA-F]{{6}}",
                   f"--{nome}:{cor_da_zona(colorway)}", t, count=1)

    # A CONTAGEM DO CABEÇALHO SAI DA MESA. Ela estava digitada no esqueleto
    # ("2 controles: 1 USB · 1 BT") e divergiria da fita no primeiro controle a
    # mais — que é exatamente o que aconteceu quando a mesa virou quatro.
    # QUEM CONTA É `CONECTADOS`, não `MESA` — 31/08/2026, decisão dela de deixar
    # dois fora. O cabeçalho promete o que está na mesa AGORA; contar os quatro
    # aqui faria a janela anunciar quatro e desenhar dois acesos, que é a mesma
    # divergência que esta linha nasceu para matar.
    usb = sum(1 for c in CONECTADOS if c["via"] == "USB")
    bt = sum(1 for c in CONECTADOS if c["via"] == "BT")
    # OS DOIS `data-campo` SÃO O ENDEREÇO DA PINTURA, e eles valem para as DEZ
    # páginas porque o cabeçalho é um só. Sem eles o piloto tinha onde buscar o
    # número e nenhum lugar onde escrevê-lo: medido em 01/09/2026, a aba Jogar
    # emitia `conta` e `conta_b` e a página não tinha nem um dos dois — a
    # pintura escrevia zero, calada.
    #
    # Eles não mudam UMA LINHA do que se vê. O portão do desenho aprovado
    # ignora os atributos invisíveis de propósito, e foi por isto que ela pediu
    # o ajuste: *"a ideia do mockup é o desenho ser possível de ser comparado
    # ao produto final"* — comparar o que se VÊ, não o andaime.
    t = re.sub(r'(<div class="conectado"><span class="bolinha">●</span> )[^<]*<b>[^<]*</b>',
               rf'\g<1><span data-campo="conta">{len(CONECTADOS)} controles:</span> '
               rf'<b data-campo="conta-b">{usb} USB · {bt} BT</b>', t, count=1)

    # O PERFIL ATIVO, mesma razão: o nome vem do daemon (`active_profile`) e a
    # página tinha o texto do mockup ("Mortal Kombat") sem endereço nenhum.
    t = t.replace('<span class="pa-nome">',
                  '<span class="pa-nome" data-campo="perfil">', 1)

    # A FITA É GERADA, e não mais remendada. Ela era dois `<span>` fixos no
    # `topo.html`, e `monta()` os remendava com três `str.replace` encadeados —
    # foi assim que a fita viva morreu sem sintoma quando o texto do chip mudou.
    # Com QUATRO controles na mesa (pedido dela, 27/08) o remendo não escala:
    # a fita inteira sai de `fita()`, que lê a `MESA` e a cor do desenho.
    i = t.index(MARCA_DA_FITA)
    j = t.index("</div>", t.index('class="fita', i)) + len("</div>")
    t = t[:i] + fita(ativo=("p1" if fita_viva else "todos"), inerte=not fita_viva) + t[j:]
    # a tira: marca a aba ativa
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
        k = fim.index('<div class="nota">')
        fim = fim[:k] + legenda
    doc = t + '  <div class="miolo">\n' + miolo + '\n  </div>\n\n' + fim
    # NOMES PRÓPRIOS, e não `a`/`b`: `a` já era um `str` neste escopo, e
    # reusá-lo para uma contagem fazia o `mypy` acusar dois erros de tipo
    # sobre a mesma linha. Duas coisas diferentes com o mesmo nome é o defeito
    # que esta casa persegue em prosa; em código também vale.
    abertas, fechadas = doc.count("<div"), doc.count("</div>")
    if abertas != fechadas:
        raise SystemExit(
            f"ERRO em {arq}: <div>={abertas} </div>={fechadas} — desbalanceado")
    onde.gravar(f"{arq}.html", doc)
    # A CONTAGEM DE `<div>`, que os dez geradores imprimem como prova de que a
    # página fechou. Era `return a` — e `a` era, no mesmo escopo, o nome de um
    # `str` da tira de abas. A anotação `-> str` que eu escrevi passava por
    # causa dessa colisão, e o `aba09` chegou a imprimir `OK, 10-perfis divs`.
    return abertas
