"""A barra da janela traz TRÊS botões desta casa, e não os da decoração."""

from __future__ import annotations

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.janela`, que carrega o GTK")

from hefesto_dualsense4unix.interface import janela as ponte_da_tela


def test_sao_tres_botoes_com_gesto_dica_e_icone() -> None:
    """Cada botão da barra diz o ícone, o gesto e a dica — os três."""
    assert len(ponte_da_tela.BOTOES_DA_BARRA) == 3
    icones = {icone for icone, _, _ in ponte_da_tela.BOTOES_DA_BARRA}
    assert icones == {
        "window-close-symbolic",
        "window-maximize-symbolic",
        "window-minimize-symbolic",
    }
    gestos = [gesto for _, gesto, _ in ponte_da_tela.BOTOES_DA_BARRA]
    assert gestos == ["fechar", "maximizar", "minimizar"]
    for _, _, dica in ponte_da_tela.BOTOES_DA_BARRA:
        assert dica.strip(), "botão sem dica é botão que ninguém sabe o que faz"


def test_a_barra_nao_delega_os_botoes_a_decoracao() -> None:
    """``set_show_close_button`` é chamado com ``False``, e só com ``False``."""
    fonte = ponte_da_tela.__file__
    with open(fonte, encoding="utf-8") as arquivo:
        codigo = arquivo.read()
    chamadas = [
        linha.strip()
        for linha in codigo.splitlines()
        if "set_show_close_button(" in linha and not linha.strip().startswith("#")
    ]
    assert chamadas, "a chamada sumiu — o GTK volta ao padrão, que é True"
    for chamada in chamadas:
        assert "False" in chamada, (
            f"{chamada!r} devolve os botões à decoração do tema, "
            "que é o defeito que a BARRA-MAXIMIZADA-01 mediu"
        )


@pytest.mark.parametrize("gesto", ["fechar", "minimizar", "maximizar"])
def test_cada_gesto_chega_na_janela(gesto: str) -> None:
    """O clique no botão vira o método certo da janela, e nenhum outro."""
    chamados: list[str] = []

    class JanelaDeMentira:
        def close(self) -> None:
            chamados.append("close")

        def iconify(self) -> None:
            chamados.append("iconify")

        def is_maximized(self) -> bool:
            return False

        def maximize(self) -> None:
            chamados.append("maximize")

        def unmaximize(self) -> None:
            chamados.append("unmaximize")

    quem = object.__new__(ponte_da_tela.JanelaDaAba)
    quem.janela = JanelaDeMentira()  # type: ignore[attr-defined]
    quem._gesto_da_barra(None, gesto)
    esperado = {"fechar": "close", "minimizar": "iconify", "maximizar": "maximize"}
    assert chamados == [esperado[gesto]]


def test_o_maximizar_alterna_e_nao_so_maximiza() -> None:
    """Janela já maximizada volta ao tamanho de antes — é o que o botão promete."""
    chamados: list[str] = []

    class JanelaCheia:
        def is_maximized(self) -> bool:
            return True

        def maximize(self) -> None:
            chamados.append("maximize")

        def unmaximize(self) -> None:
            chamados.append("unmaximize")

    quem = object.__new__(ponte_da_tela.JanelaDaAba)
    quem.janela = JanelaCheia()  # type: ignore[attr-defined]
    quem._gesto_da_barra(None, "maximizar")
    assert chamados == ["unmaximize"]
