"""A marreta do Hefesto respeita quem desligou animação — e nunca é a notícia.

``CALIBRAR-AS-ENTRADAS-01``, tarefa ``CAL-6`` (26/08/2026).

A ANIMAÇÃO QUE ELA PEDIU, E O QUE ELA CUSTA
---------------------------------------------

Palavra dela, 25/08 de madrugada: *"animação do martelo do Hefesto batendo e
dando o sinal de ok"*. Ela viu o mockup às ~03h55 e carimbou a cadência: **uma
batida, em 0,82 s**.

Esta seria a **primeira animação do produto** — ``transition|animation|
@keyframes`` no ``theme.css`` dá zero até hoje. Duas coisas vêm junto:

* **R35** — ``gtk-enable-animations`` é o equivalente de
  ``prefers-reduced-motion``, existe no GTK 3 e o produto **nunca o leu**
  (``grep`` em ``src/`` = 0). Quem desligou animação por enxaqueca, por
  vestibular ou por máquina lenta desligou por uma razão;
* **R36/R14** — a marreta não pisca acima de 3 Hz e **não é o único portador de
  notícia nenhuma**. Com ela parada, o cartão continua igualmente legível,
  porque a notícia mora no nome acessível.
"""
from __future__ import annotations

from hefesto_dualsense4unix.app.widgets.calibrar_entradas import (
    FACE_FRENTE,
    MARRETA_DURACAO_S,
    _animacao_ligada,
    _marreta_hz,
    _nome_acessivel_do_cartao,
    _quadros_da_marreta,
)


class AjustesDoGtk:
    """O ``Gtk.Settings`` de mentira — só a chave que interessa."""

    def __init__(self, animar: bool) -> None:
        self.animar = animar
        self.perguntados: list[str] = []

    def get_property(self, nome: str) -> bool:
        self.perguntados.append(nome)
        if nome != "gtk-enable-animations":
            raise TypeError(f"ajuste desconhecido: {nome}")
        return self.animar


class AjustesSemAChave:
    """Uma versão do GTK que não conhece a chave. Ausência não desliga a tela."""

    def get_property(self, nome: str) -> bool:
        raise TypeError(f"ajuste desconhecido: {nome}")


# ---------------------------------------------------------------------------
# A mordida
# ---------------------------------------------------------------------------


def test_com_animacao_desligada_zero_quadros() -> None:
    """``gtk-enable-animations=False`` e a marreta não bate quadro nenhum.

    MORDIDA: fazer ``quadros_da_marreta`` ignorar o argumento e devolver
    sempre a sequência (animar sempre), que é o que toda animação desta casa
    faria hoje, porque nenhuma lê a chave. A contagem passa de 0 e o teste
    reprova.
    """
    ajustes = AjustesDoGtk(animar=False)
    assert _animacao_ligada(ajustes) is False
    assert ajustes.perguntados == ["gtk-enable-animations"], (
        "a janela decidiu animar sem perguntar ao GTK"
    )

    quadros = _quadros_da_marreta(_animacao_ligada(ajustes))
    assert len(quadros) == 0, (
        f"a marreta bateu {len(quadros)} quadro(s) com a animação desligada"
    )


def test_com_animacao_ligada_a_marreta_bate_uma_vez_em_082_s() -> None:
    """A cadência carimbada por ela: uma batida, 0,82 s.

    O outro lado da mesma régua — uma que só soubesse recusar não seria régua.
    """
    quadros = _quadros_da_marreta(_animacao_ligada(AjustesDoGtk(animar=True)))
    assert len(quadros) > 0
    assert MARRETA_DURACAO_S == 0.82


def test_a_marreta_nao_pisca_acima_de_tres_hertz() -> None:
    """R36 — e o que se mede é a frequência do SINAL, não a taxa de quadros.

    Uma batida por 0,82 s é 1,22 Hz. O limite de 3 Hz existe porque acima dele
    o piscar entra na faixa que dispara crise fotossensível.
    """
    assert _marreta_hz() < 3.0, (
        f"a marreta pisca a {_marreta_hz():.2f} Hz, acima do teto de 3 Hz"
    )


def test_o_ajuste_ausente_nao_desliga_a_tela() -> None:
    """GTK que não conhece a chave = animação LIGADA, que é o default do GTK.

    Tratar a ausência como "desligado" faria a marreta sumir em todo ambiente
    que não publica a chave — e a ausência de resposta viraria uma decisão que
    ninguém tomou.
    """
    assert _animacao_ligada(AjustesSemAChave()) is True
    assert _animacao_ligada(None) is True


def test_a_noticia_nao_depende_de_quadro_nenhum() -> None:
    """R14 — o martelo é enfeite, e o nome acessível é o portador.

    Com a animação desligada, a frase de confirmação continua completa: contém
    a palavra "Entrada", o NÚMERO da entrada e a face. É o que o leitor de tela
    pronuncia, e é o que faz a cerimônia funcionar sem olhar.
    """
    frase = _nome_acessivel_do_cartao("7", FACE_FRENTE)
    assert "7" in frase, "o nome acessível não diz de que entrada se trata"
    assert FACE_FRENTE in frase
    assert "Entrada" in frase, (
        "a palavra é 'entrada', nunca 'porta' (D-A-PALAVRA-ENTRADA)"
    )
    assert "porta" not in frase.lower()


# ---------------------------------------------------------------------------
# A janela de verdade — R12, R19 e a marreta pelo caminho real
# ---------------------------------------------------------------------------
#
# Estes exercitam a `JanelaDeCalibrarEntradas` com o GTK REAL. Não há
# `Gtk.Window` MOSTRADA em lugar nenhum: sob Xvfb não existe gerenciador de
# janelas e uma janela mostrada fica 1x1 para sempre (`COMO-OLHAR-A-TELA.md`).
# O que se mede aqui é o gesto e a árvore de widgets, e nenhum dos dois precisa
# de tela.
#
# A guarda `exigir_gi_real` é chamada DENTRO de cada teste, e não no topo do
# módulo: as réguas puras deste arquivo (a chave de animação, a cadência, o
# nome acessível) têm de rodar mesmo onde o PyGObject não existe. Um guard de
# módulo levaria as cinco junto.


def _janela(**kwargs):
    """A janela sobre uma mesa de mentira, sem `show`."""
    from hefesto_dualsense4unix.app.widgets.calibrar_entradas import (
        JanelaDeCalibrarEntradas,
    )
    from hefesto_dualsense4unix.utils.maquina import MapaDaMesa
    from tests.unit.test_a_fase_sentada_resolve_o_hub import (
        GravadorDeMentira,
        mesa_com_hub_e_tres_aparelhos,
    )

    return JanelaDeCalibrarEntradas(
        object(),
        MapaDaMesa(),
        mesa_com_hub_e_tres_aparelhos(),
        (),
        gravar=kwargs.get("gravar") or GravadorDeMentira(),
    )


def test_a_janela_confirma_pelo_payload_do_controle() -> None:
    """R1, no caminho REAL: o payload vivo chega à janela e ela avança.

    MORDIDA: arrancar o ramo do ``cross`` de ``NavegacaoPorControle.passo``.
    A janela não sai do primeiro passo, e o teste reprova — que é a cerimônia
    voltando a exigir mouse de quem está atrás do gabinete.
    """
    from tests.conftest import exigir_gi_real

    exigir_gi_real("a janela de calibração")
    janela = _janela()
    assert janela.botoes_de_face, "a janela nasceu sem os botões das faces"

    janela.ao_payload_do_controle({"buttons": ["cross"]})

    assert janela.logica.portas, (
        "o botão do controle não confirmou nada: a janela ficou no primeiro "
        "passo e a cerimônia voltou a exigir mouse"
    )


def test_nenhum_rotulo_da_janela_pode_receber_foco() -> None:
    """R12 — ``Gtk.Label`` nasce ``can_focus=False``, e isso foi MEDIDO.

    Linha que precisa ser lida não pode ser só rótulo: quem lê por leitor de
    tela alcança o que tem foco. Por isso a notícia mora no nome acessível do
    botão do passo, e os rótulos são reforço visual.
    """
    from tests.conftest import exigir_gi_real

    exigir_gi_real("a janela de calibração")
    janela = _janela()
    for nome in ("rotulo_pergunta", "rotulo_contador", "rotulo_quem"):
        rotulo = getattr(janela, nome)
        assert rotulo.get_can_focus() is False, f"{nome} pode receber foco"


def test_os_alvos_clicaveis_tem_trinta_pixels_de_altura() -> None:
    """R19 — 30 px é o piso, e ele existe para quem tem tremor ou pressa."""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("a janela de calibração")
    janela = _janela()
    for face, botao in janela.botoes_de_face.items():
        _largura, altura = botao.get_size_request()
        assert altura >= 30, f"o botão {face!r} tem alvo de {altura} px"


def test_a_janela_diz_os_dois_relogios_e_nao_promete_teto_nenhum() -> None:
    """R33 — os números reais na tela, e **nenhum** teto de 8 s.

    Qualquer teto de 8 s declararia falha no caso MEDIANO (10,3 s), e a pessoa
    concluiria que quebrou o cabo dela. A tela assume a culpa: a demora é do
    ``usbcore.quirks`` que o próprio Hefesto instala.
    """
    from hefesto_dualsense4unix.app.widgets.calibrar_entradas import OS_DOIS_RELOGIOS
    from tests.conftest import exigir_gi_real

    exigir_gi_real("a janela de calibração")
    janela = _janela()
    texto = janela.rotulo_relogios.get_text()

    assert "3,4" in texto and "10,3" in texto and "15,6" in texto, texto
    assert "8 s" not in OS_DOIS_RELOGIOS, (
        "apareceu um teto de 8 s, que declararia falha no caso mediano"
    )
    assert "uns quatro segundos" not in texto.lower()
