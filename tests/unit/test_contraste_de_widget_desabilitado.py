"""BUG-GUI-SWITCH-APAGADO-INVISIVEL-01 — o interruptor que não mostrava estado.

O que ela via: o interruptor **"Pelo rádio"** do card do controle (o que nasceu
em 07/08, `controller_card.py`) fica INSENSÍVEL enquanto o controle está no
cabo — e desenhava com o miolo no mesmo branco `@fg` de um interruptor vivo. O
rótulo ao lado dele mudava de cor (`label:disabled` existe desde sempre); o
interruptor, não. Ela ganhou um controle novo no mesmo dia em que perdeu a
capacidade de ver se ele estava ligado.

**A causa é do projeto, e isso é o que este arquivo ancora.** O `theme.css`
tinha `:disabled` para `button` e para `label`, e o `switch` ficou de fora: as
regras `switch`/`switch:checked`/`switch slider` pintam cor CHAPADA sobre
qualquer estado, e cor chapada sobrepõe o rebaixamento que o tema do sistema
aplicaria sozinho. Medido em 07/08 (GTK 3.24.41), o mesmo `Gtk.Switch` sensível
contra insensível:

    tema                 a 0%      acima de 3%    miolo (aceso -> apagado)
    casa, ANTES         377 px           1 px     #F8F8F2 -> #F8F8F2
    GTK stock          1264 px        1264 px     #D2D2D2 -> #787878
    casa, DEPOIS       1178 px        1047 px     #F8F8F2 -> #8B8FA8

A coluna do meio é a acusação inteira: ANTES havia 377 pixels de diferença a 0%
de tolerância, e **um** deles sobrevivia a 3%. Era a franja de antisserrilhado
de uma borda, não um sinal. O tema da casa tinha APAGADO a distinção que o GTK
entregava de graça.

## O critério, e de onde ele vem

É o do **GTK stock**, medido nesta mesma máquina e com este mesmo instrumento —
não um número escolhido para caber na cura:

1. **a diferença tem de sobreviver ao antisserrilhado.** Contar pixels a 0% de
   tolerância aprova qualquer coisa: duas bordas com meio tom de diferença já
   dão centenas. O piso é sobre a contagem ACIMA DE 3%, que é onde o ANTES
   morre (1 px) e onde o stock continua de pé (1264 px);
2. **o MIOLO tem de escurecer.** É o que o olho procura num interruptor, e é a
   diferença qualitativa entre o stock (#D2D2D2 -> #787878) e o ANTES da casa
   (#F8F8F2 -> #F8F8F2, razão 1,0:1 — a mesma cor). O piso de 1,8:1 fica abaixo
   dos ~3,0:1 que stock e cura entregam, e MUITO acima do 1,0:1 do defeito.

## Este arquivo é o primeiro teste de contraste de WIDGET da casa

O que havia antes lia TEXTO: `test_contraste_css.py` monta pares texto x fundo
lendo o CSS, e `test_color_contrast.py` afere um auxiliar de runtime. Nenhum dos
dois renderiza widget nenhum — e o defeito daqui é invisível para os dois,
porque as duas cores envolvidas (`@fg` e `@text_muted`) são da paleta e cada uma
passa em qualquer par de texto que se monte com elas.

`distancia_ao_desabilitar` é a ferramenta, e ela recebe uma FÁBRICA de widget:
`ADORMECIDOS` é a lista dos widgets cobertos, e cobrir o próximo é acrescentar
uma linha lá. O `button` está na lista de propósito — ele já tinha `:disabled`
e serve de controle: se o instrumento reprovasse o botão, o instrumento estaria
errado, não o tema.

**Este arquivo mede PIXEL, não texto.** Procurar a string `switch:disabled` no
CSS passaria com a regra escrita num seletor que não casa com nada — que foi um
dos caminhos falsos da investigação irmã (`test_switch_sem_icone_quebrado.py`).

## Os dois eixos, porque curar um pode quebrar o outro

Um interruptor tem de responder DUAS perguntas ao mesmo tempo, e elas puxam para
lados opostos:

1. **posso mexer nisto?** — o rebaixamento. Quanto mais o indisponível se afasta
   do disponível, melhor;
2. **está ligado?** — a marca. Rebaixar demais apaga a marca, e ela troca "não
   sei se posso mexer" por "não sei se está ligado".

A cura separa os dois portadores: o **miolo** carrega o eixo 1 (vai a
@text_muted nos dois estados) e o **anel** carrega o eixo 2 (fica @purple
quando ligado). Foi medindo o eixo 2 no lugar errado — no trilho, onde dá
1,48:1, em vez do anel, onde dá 4,89:1 — que a primeira versão desta régua quase
condenou a cura certa e mandou trocá-la por uma que reintroduzia AZUL na
interface, exatamente o que o BUG-GUI-ACENTO-AZUL-VAZANDO-01 tinha removido.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito. Este
# arquivo RENDERIZA um widget e conta pixels; contra `Gtk.Box = object` ele
# passaria sem medir nada.
exigir_gi_real("contraste de widget desabilitado")

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

import pytest

pytest.importorskip("cairo")

from gi.repository import Gdk, Gtk

from hefesto_dualsense4unix.utils.color_contrast import razao_contraste

CSS = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "hefesto_dualsense4unix"
    / "gui"
    / "theme.css"
)

#: Tolerância, em % de 255, acima da qual um pixel conta como DIFERENTE.
#:
#: Um limiar de 0% conta a franja de antisserrilhado de qualquer borda e aprova
#: um tema que não mudou nada. 3% (~7,6 de 255) é o degrau que separa "a mesma
#: cor com ruído de traçado" de "outra cor": no defeito, 377 px caíam para 1.
TOLERANCIA_PCT = 3

#: Fração MÍNIMA do render que precisa mudar ao desabilitar o widget.
#:
#: Calibrado contra o GTK stock desta máquina, que é o teto honesto: o pior dos
#: estados dele entrega 680 px de 2904 = 23,4%. O piso fica em 10% para tolerar
#: deriva de geometria entre versões do GTK sem chegar perto do defeito, que
#: entregava 0,04% (1 px de 2816).
PISO_FRACAO_DIFERENTE = 0.10

#: Razão de contraste mínima entre o MIOLO aceso e o miolo apagado.
#:
#: O stock entrega 2,90:1 (#D2D2D2 -> #787878) e a cura 3,01:1
#: (#F8F8F2 -> #8B8FA8). O defeito entregava 1,00:1 — a mesma cor, exatamente.
PISO_RAZAO_DO_MIOLO = 1.8

#: Razão mínima entre a MARCA de ligado e a de desligado, ambos indisponíveis.
#:
#: 3,0:1 é o piso do WCAG 1.4.11 para elemento não-textual, e é o que o GTK
#: stock entrega no trilho (3,07:1). A cura entrega 4,89:1 no anel @purple.
PISO_RAZAO_DA_MARCA = 3.0


def _drenar() -> None:
    """Assenta o laço. Widget sem alocação mede 1x1 e aprova qualquer desenho."""
    for _ in range(6):
        while Gtk.events_pending():
            Gtk.main_iteration()


def _render(fabrica: Callable[[], Gtk.Widget], *, sensivel: bool, com_o_css: bool):
    """Um widget desenhado numa `Gtk.OffscreenWindow`, devolvido como pixbuf.

    `Gtk.OffscreenWindow` e não `Gtk.Window`: sob Xvfb não há gerenciador de
    janelas, a janela nunca é mapeada e o filho fica 1x1 para sempre.

    A janela leva a classe `.hefesto-dualsense4unix-window` porque as regras do
    tema são escopadas nela — um render sem a classe mediria o tema do sistema e
    passaria com a cura arrancada.
    """
    janela = Gtk.OffscreenWindow()
    janela.get_style_context().add_class("hefesto-dualsense4unix-window")

    widget = fabrica()
    widget.set_sensitive(sensivel)
    widget.set_halign(Gtk.Align.CENTER)
    widget.set_valign(Gtk.Align.CENTER)
    # Margem para o pixbuf não sair recortado rente à borda do widget.
    for lado in ("start", "end", "top", "bottom"):
        getattr(widget, f"set_margin_{lado}")(8)
    janela.add(widget)

    provedor = None
    if com_o_css:
        provedor = Gtk.CssProvider()
        provedor.load_from_path(str(CSS))
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provedor, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    janela.show_all()
    _drenar()
    pixbuf = janela.get_pixbuf()

    if provedor is not None:
        Gtk.StyleContext.remove_provider_for_screen(Gdk.Screen.get_default(), provedor)
    janela.destroy()
    return pixbuf


def _celulas(pixbuf) -> tuple[list[tuple[int, int, int]], int, int]:
    """O pixbuf como lista de (r, g, b), na ordem de leitura, mais as medidas."""
    dados = pixbuf.get_pixels()
    canais = pixbuf.get_n_channels()
    passo = pixbuf.get_rowstride()
    largura, altura = pixbuf.get_width(), pixbuf.get_height()
    saida: list[tuple[int, int, int]] = []
    for y in range(altura):
        base = y * passo
        for x in range(largura):
            i = base + x * canais
            saida.append((dados[i], dados[i + 1], dados[i + 2]))
    return saida, largura, altura


def distancia_ao_desabilitar(
    fabrica: Callable[[], Gtk.Widget],
    *,
    com_o_css: bool = True,
    tolerancia_pct: int = TOLERANCIA_PCT,
) -> tuple[int, int, float]:
    """Quanto o desenho de um widget MUDA quando ele fica insensível.

    Devolve ``(diferentes, total, fracao)`` — a contagem de pixels que mudam
    acima de ``tolerancia_pct``% de 255, o tamanho do render e a razão entre os
    dois. É a ferramenta que os próximos widgets herdam: passe outra fábrica.
    """
    aceso = _render(fabrica, sensivel=True, com_o_css=com_o_css)
    apagado = _render(fabrica, sensivel=False, com_o_css=com_o_css)

    a, largura, altura = _celulas(aceso)
    b, _, _ = _celulas(apagado)
    total = largura * altura
    corte = tolerancia_pct * 255 / 100.0
    # `strict` não é formalidade: os dois renders TÊM de ter o mesmo tamanho.
    # Se um deles vier 1x1 (widget medido antes de o laço assentar) o zip curto
    # compararia um pixel e a contagem sairia zero — reprovando por motivo errado.
    diferentes = sum(
        1
        for pa, pb in zip(a, b, strict=True)
        if max(abs(pa[0] - pb[0]), abs(pa[1] - pb[1]), abs(pa[2] - pb[2])) > corte
    )
    return diferentes, total, diferentes / total


def _cor_do_miolo(pixbuf, ligado: bool) -> tuple[int, int, int]:
    """Cor no centro do SLIDER — o miolo que anda, não o trilho.

    O slider ocupa a metade esquerda do trilho quando desligado e a direita
    quando ligado; 28% / 72% da largura caem no meio dele nas duas geometrias
    (a do tema e a do stock) sem encostar na borda arredondada.
    """
    celulas, largura, altura = _celulas(pixbuf)
    x = int(largura * (0.72 if ligado else 0.28))
    return celulas[(altura // 2) * largura + x]


def _cor_da_borda(pixbuf) -> tuple[int, int, int]:
    """Cor da BORDA no topo do widget, descendo pela coluna central.

    É onde mora a marca de LIGADO de um interruptor indisponível: o trilho fica
    rebaixado (@sel_bg), e quem continua dizendo "isto está ligado" é o anel
    @purple — o mesmo par que o `button:checked:disabled` já usava.

    Procura o primeiro pixel que se afasta do fundo em mais de 12/255 (folga
    para o antisserrilhado do canto arredondado não ser confundido com a borda).
    """
    celulas, largura, altura = _celulas(pixbuf)
    x = largura // 2
    fundo = celulas[x]
    for y in range(altura):
        p = celulas[y * largura + x]
        if max(abs(p[i] - fundo[i]) for i in range(3)) > 12:
            return p
    return fundo


def _interruptor(ligado: bool) -> Callable[[], Gtk.Widget]:
    def fabrica() -> Gtk.Widget:
        sw = Gtk.Switch()
        sw.set_active(ligado)
        sw.set_state(ligado)
        return sw

    return fabrica


def _botao() -> Gtk.Widget:
    return Gtk.Button(label="Aplicar")


#: Os widgets cobertos. Acrescentar uma linha aqui é cobrir o próximo.
ADORMECIDOS: list[tuple[str, Callable[[], Gtk.Widget]]] = [
    ("switch desligado", _interruptor(False)),
    ("switch ligado", _interruptor(True)),
    ("button", _botao),
]


@pytest.mark.parametrize("nome,fabrica", ADORMECIDOS, ids=[n for n, _ in ADORMECIDOS])
def test_widget_insensivel_desenha_diferente_de_um_sensivel(
    nome: str, fabrica: Callable[[], Gtk.Widget]
) -> None:
    """A mordida: sem `switch:disabled` no theme.css, os dois `switch` reprovam.

    O `button` na lista é o CONTROLE do instrumento: ele já tinha `:disabled`
    antes deste arquivo existir, e reprovar nele significaria que a régua está
    errada — não o tema.
    """
    diferentes, total, fracao = distancia_ao_desabilitar(fabrica)

    assert fracao >= PISO_FRACAO_DIFERENTE, (
        f"`{nome}` insensível desenha praticamente igual ao sensível: só "
        f"{diferentes} de {total} px ({fracao:.2%}) mudam acima de "
        f"{TOLERANCIA_PCT}% de tolerância, e o piso é {PISO_FRACAO_DIFERENTE:.0%}. "
        "Ela não consegue ver que o controle está indisponível. Falta variante "
        "`:disabled` no theme.css para este widget, ou ela deixou de casar."
    )


@pytest.mark.parametrize("ligado", [False, True], ids=["desligado", "ligado"])
def test_o_miolo_do_interruptor_escurece_ao_ficar_indisponivel(ligado: bool) -> None:
    """O critério qualitativo: o botão que anda tem de APAGAR, não só a moldura.

    Separado do teste de área porque uma cura que mudasse só o TRILHO passaria
    lá e falharia aqui — e o miolo é o que o olho segue num interruptor. Era
    exatamente o buraco do defeito: o trilho já mudava um pouco (o tema do
    sistema mexia nele), e o miolo ficava em #F8F8F2 nos dois estados.
    """
    aceso = _cor_do_miolo(_render(_interruptor(ligado), sensivel=True, com_o_css=True), ligado)
    apagado = _cor_do_miolo(
        _render(_interruptor(ligado), sensivel=False, com_o_css=True), ligado
    )

    razao = razao_contraste(aceso, apagado)

    assert razao >= PISO_RAZAO_DO_MIOLO, (
        f"o miolo do interruptor (ligado={ligado}) vai de "
        f"#{aceso[0]:02X}{aceso[1]:02X}{aceso[2]:02X} para "
        f"#{apagado[0]:02X}{apagado[1]:02X}{apagado[2]:02X} ao ficar insensível "
        f"— razão de {razao:.2f}:1, abaixo do piso de {PISO_RAZAO_DO_MIOLO}:1. "
        "Falta `switch:disabled slider` (e o `:checked:disabled slider`) no "
        "theme.css. O GTK stock entrega 2,90:1 de graça nesta mesma máquina."
    )


def test_o_gtk_stock_ja_entregava_a_distincao_que_o_tema_apagou() -> None:
    """Ancora a premissa: a régua é possível, e o defeito era NOSSO.

    Sem esta âncora, os pisos acima passariam por serem baixos, e ninguém
    saberia que o tema da casa estava por baixo do que o GTK dá sem pedir. Ela
    também protege o número do outro lado: no dia em que o GTK parar de rebaixar
    widget insensível sozinho, é aqui que se descobre — e não com um conselho
    errado dado com confiança sobre o `theme.css`.

    Ela PULA em vez de reprovar quando o ambiente não tem tema GTK que rebaixe:
    o tema do sistema é da máquina, não do projeto, e o CI roda com outro. O
    teste que garante a CURA não depende disto e roda nos dois ambientes — é o
    mesmo desenho de `test_switch_sem_icone_quebrado.py`, pela mesma razão, que
    já segurou uma release inteira.
    """
    _, _, fracao = distancia_ao_desabilitar(_interruptor(False), com_o_css=False)

    if fracao < PISO_FRACAO_DIFERENTE:
        pytest.skip(
            "o tema GTK deste ambiente não rebaixa `switch` insensível sozinho "
            f"(só {fracao:.2%} do render muda): não há o que ancorar aqui. A "
            "cura continua coberta pelos testes que carregam o theme.css."
        )

    assert fracao >= PISO_FRACAO_DIFERENTE


def test_o_interruptor_indisponivel_continua_dizendo_se_esta_ligado() -> None:
    """O SEGUNDO eixo: rebaixar não pode custar a leitura de LIGADO x desligado.

    "Ela ganhou um interruptor hoje e não consegue ver se ele está ligado" tem
    duas metades, e curar uma pode quebrar a outra: um `:disabled` que apagasse
    o interruptor inteiro deixaria os dois estados iguais entre SI, e ela
    trocaria "não sei se posso mexer" por "não sei se está ligado".

    A marca de ligado de um interruptor indisponível é o ANEL @purple, não o
    trilho — é aí que este teste mede, e foi medindo o lugar errado (o trilho)
    que a primeira versão desta régua quase condenou a cura certa:

        onde se mede            ON x OFF, ambos apagados
        trilho (fill)                        1,48:1
        borda (o anel)                       4,89:1
        GTK stock, no trilho                 3,07:1

    O piso de 3,0:1 é o do WCAG 1.4.11 para elemento NÃO-textual, e é também o
    que o stock entrega — mesmo ele estando formalmente isento (1.4.11 dispensa
    componente inativo). Vale a régua mais dura porque a informação é justamente
    o que ela precisa ler.

    **Este teste é o que morde a remoção do `switch:checked:disabled`.** MEDIDO
    em 07/08: arrancando aquele bloco, o `:disabled` genérico assume, o anel cai
    para @border_soft nos dois estados e a razão vai a 1,00:1 — enquanto os
    testes de área acima continuam passando (43,11%), porque o slider muda de
    lado e isso sozinho move pixels de sobra. Sem esta asserção, aquele bloco
    pareceria redundante e sairia na primeira limpeza.
    """
    borda_ligado = _cor_da_borda(_render(_interruptor(True), sensivel=False, com_o_css=True))
    borda_desligado = _cor_da_borda(
        _render(_interruptor(False), sensivel=False, com_o_css=True)
    )

    razao = razao_contraste(borda_ligado, borda_desligado)

    assert razao >= PISO_RAZAO_DA_MARCA, (
        "um interruptor INDISPONÍVEL não diz mais se está ligado: o anel do "
        f"ligado é #{borda_ligado[0]:02X}{borda_ligado[1]:02X}{borda_ligado[2]:02X} "
        f"e o do desligado é "
        f"#{borda_desligado[0]:02X}{borda_desligado[1]:02X}{borda_desligado[2]:02X} "
        f"— razão de {razao:.2f}:1, abaixo do piso de {PISO_RAZAO_DA_MARCA}:1. "
        "Provavelmente saiu o bloco `switch:checked:disabled` do theme.css, e o "
        "`switch:disabled` genérico passou a pintar o anel dos dois estados de "
        "@border_soft."
    )
