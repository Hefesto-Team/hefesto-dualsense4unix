"""As seis regras de topologia — o que cada uma acusa, e o que ela CALA."""
from __future__ import annotations


from hefesto_dualsense4unix.integrations import ordens_da_mesa as ordens


def chaves(catalogo: tuple[ordens.Ordem, ...]) -> tuple[str, ...]:
    return tuple(ordem.chave for ordem in catalogo)


def test_r3_diz_uma_frase_de_portugues_inteira() -> None:
    """A frase MONTADA, palavra por palavra — e ela nasceu de um defeito meu."""
    for quantos, esperada in (
        (3, "2 de 3 adaptadores BT passam por um hub."),
        (1, "1 de 1 adaptador BT passa por um hub."),
    ):
        frase = (
            f"{quantos - 1 or 1} de {quantos} "
            + ordens._plural(quantos, "adaptador BT passa",
                             "adaptadores BT passam")
            + " por um hub."
        )
        assert frase == esperada, (
            f"a frase do R3 saiu {frase!r} e devia ser {esperada!r}. O verbo "
            f"mora num lugar só — o `_plural` conjuga e o sufixo começa na "
            f"preposição. Foi assim que «chegam passam» chegou à tela dela.")


def test_nao_medi_e_nao_declarado_sao_frases_diferentes() -> None:
    """F7: "olhei e não sei" não é "só você sabe, e você não me disse"."""
    assert ordens.NAO_MEDI != ordens.NAO_DECLARADO
    assert ordens.NAO_MEDI not in ordens.NAO_DECLARADO
    assert ordens.NAO_DECLARADO not in ordens.NAO_MEDI


