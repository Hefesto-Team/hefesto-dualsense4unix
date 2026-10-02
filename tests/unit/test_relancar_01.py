"""O diálogo só aparece quando a mudança de fato exige o jogo reabrir."""

from __future__ import annotations


from hefesto_dualsense4unix.app.actions import relancar as r


def test_o_titulo_pergunta_em_vez_de_avisar() -> None:
    """A janela PEDE, no padrão do HONESTIDADE-STEAM-01."""
    assert r.TITULO.endswith("?"), (
        "o título deixou de ser pergunta. Fechar o jogo dela é consequência "
        "pesada: o produto pede, não anuncia."
    )


def test_o_rotulo_promete_o_fim_e_nao_o_meio() -> None:
    """"Aplicar agora e reiniciar o jogo" — as palavras dela."""
    assert "Aplicar agora" in r.ROTULO_FECHAR, (
        "o rótulo voltou a descrever o meio (fechar) em vez do fim (aplicar). "
        "Quem lê o botão precisa saber o que GANHA, não só o que perde."
    )
    assert "reiniciar o jogo" in r.ROTULO_FECHAR, (
        "o rótulo não diz mais que o jogo reinicia — e reiniciar é o preço que "
        "ela aceita pagar CONSCIENTEMENTE."
    )


