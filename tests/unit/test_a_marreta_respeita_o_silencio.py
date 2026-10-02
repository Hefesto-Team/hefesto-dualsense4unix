"""A marreta do Hefesto respeita quem desligou animação — e nunca é a notícia."""
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


def test_com_animacao_desligada_zero_quadros() -> None:
    """``gtk-enable-animations=False`` e a marreta não bate quadro nenhum."""
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
    """A cadência carimbada por ela: uma batida, 0,82 s."""
    quadros = _quadros_da_marreta(_animacao_ligada(AjustesDoGtk(animar=True)))
    assert len(quadros) > 0
    assert MARRETA_DURACAO_S == 0.82


def test_a_marreta_nao_pisca_acima_de_tres_hertz() -> None:
    """R36 — e o que se mede é a frequência do SINAL, não a taxa de quadros."""
    assert _marreta_hz() < 3.0, (
        f"a marreta pisca a {_marreta_hz():.2f} Hz, acima do teto de 3 Hz"
    )


def test_o_ajuste_ausente_nao_desliga_a_tela() -> None:
    """GTK que não conhece a chave = animação LIGADA, que é o default do GTK."""
    assert _animacao_ligada(AjustesSemAChave()) is True
    assert _animacao_ligada(None) is True


def test_a_noticia_nao_depende_de_quadro_nenhum() -> None:
    """R14 — o martelo é enfeite, e o nome acessível é o portador."""
    frase = _nome_acessivel_do_cartao("7", FACE_FRENTE)
    assert "7" in frase, "o nome acessível não diz de que entrada se trata"
    assert FACE_FRENTE in frase
    assert "Entrada" in frase, (
        "a palavra é 'entrada', nunca 'porta' (D-A-PALAVRA-ENTRADA)"
    )
    assert "porta" not in frase.lower()


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
    """R1, no caminho REAL: o payload vivo chega à janela e ela avança."""
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
    """R12 — ``Gtk.Label`` nasce ``can_focus=False``, e isso foi MEDIDO."""
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
    """R33 — os números reais na tela, e **nenhum** teto de 8 s."""
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
