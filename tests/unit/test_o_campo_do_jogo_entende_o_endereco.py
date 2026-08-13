"""JOGO-QUE-SE-DIZ-01 — o campo "Nome do jogo:" entende o endereço da loja.

Pedido dela, 13/08/2026: *"ou aplicamos um regex automático só de colar o link
da loja do jogo e ele pega o id"*. O campo exigia o appid CRU — o único dado
que ninguém tem em mãos — e a foto do editor dela mostrava `851100` digitado à
mão.

Este arquivo é a tabela de formas, com as que TÊM de falhar juntas. Puro: nada
de GTK, nada de disco, nada da biblioteca dela.

A mordida: apagar `_LOJA_STEAM_RE` da lista de tentativas em
`steam_app.steam_appid_de_texto` faz os quatro casos de endereço reprovarem, e
`normalize_appid` junto — que é o que prova que o Salvar aceita o endereço mesmo
sem a janela reescrever o campo.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.profiles.simple_match import (
    MSG_STEAM_APPID_INVALIDO,
    from_simple_choice,
    normalize_appid,
)
from hefesto_dualsense4unix.profiles.schema import MatchCriteria
from hefesto_dualsense4unix.profiles.steam_app import (
    parece_endereco,
    steam_appid_de_texto,
)

#: O appid que ela digitou à mão na foto do editor, em 13/08/2026.
APPID = 851100

#: As formas que TÊM de virar `851100`, uma a uma, do pedido dela.
FORMAS_QUE_VIRAM_APPID: list[tuple[str, str]] = [
    (
        "endereço da loja com o nome do jogo no caminho",
        "https://store.steampowered.com/app/851100/Sea_of_Stars/",
    ),
    (
        "endereço da loja sem barra no fim",
        "https://store.steampowered.com/app/851100",
    ),
    (
        "endereço colado sem esquema, com o `snr=` que a Steam gruda",
        "store.steampowered.com/app/851100/?snr=1_7_7_230_150_1",
    ),
    ("o protocolo `steam://` dos atalhos", "steam://rungameid/851100"),
    ("o número cru, que sempre valeu", "851100"),
    ("a wm_class colada de um journal, que sempre valeu", "steam_app_851100"),
    ("espaço em volta do que ela colou", "  https://store.steampowered.com/app/851100  "),
    ("a página de aviso de idade, que é a que a loja abre em jogo adulto",
     "https://store.steampowered.com/agecheck/app/851100/"),
]

#: O que NÃO pode virar appid nenhum. O campo não adivinha.
FORMAS_QUE_NAO_VIRAM_NADA: list[tuple[str, str]] = [
    ("link de outra loja", "https://www.gog.com/game/sea_of_stars"),
    ("link da Steam que não é da página do jogo (perfil)",
     "https://steamcommunity.com/id/alguem/"),
    ("link da Steam que não é da página do jogo (workshop)",
     "https://steamcommunity.com/sharedfiles/filedetails/?id=851100"),
    ("página da loja que não é de jogo (pacote)",
     "https://store.steampowered.com/bundle/851100/"),
    ("um \"id\" com letra não é appid", "https://store.steampowered.com/app/sea_of_stars/"),
    ("host que só PARECE o da loja",
     "https://store.steampowered.com.exemplo.invalido/app/851100"),
    ("texto qualquer", "Sea of Stars"),
    ("nome de programa, que é o outro significado do campo", "eldenring"),
    ("vazio", ""),
    ("só espaço", "   "),
]


class TestOQueViraNumero:
    @pytest.mark.parametrize(
        "texto", [t for _motivo, t in FORMAS_QUE_VIRAM_APPID], ids=[
            m for m, _t in FORMAS_QUE_VIRAM_APPID
        ]
    )
    def test_a_forma_vira_o_appid(self, texto: str) -> None:
        assert steam_appid_de_texto(texto) == APPID

    def test_com_barra_no_fim_e_sem_barra_dao_o_mesmo(self) -> None:
        """`/app/851100/` e `/app/851100` são o mesmo jogo — pedido dela."""
        com = steam_appid_de_texto("https://store.steampowered.com/app/851100/")
        sem = steam_appid_de_texto("https://store.steampowered.com/app/851100")
        assert com == sem == APPID

    def test_o_snr_nao_entra_no_numero(self) -> None:
        """O `?snr=1_7_7_230_150_1` tem dígitos e NENHUM deles é do appid."""
        assert (
            steam_appid_de_texto(
                "store.steampowered.com/app/851100/?snr=1_7_7_230_150_1"
            )
            == APPID
        )


class TestOQueNaoViraNumero:
    @pytest.mark.parametrize(
        "texto", [t for _motivo, t in FORMAS_QUE_NAO_VIRAM_NADA], ids=[
            m for m, _t in FORMAS_QUE_NAO_VIRAM_NADA
        ]
    )
    def test_a_forma_nao_vira_appid_nenhum(self, texto: str) -> None:
        assert steam_appid_de_texto(texto) is None


class TestOCaminhoDoSalvar:
    """A janela pode nem ter reescrito o campo — o Salvar tem de aceitar igual."""

    def test_normalize_appid_aceita_o_endereco(self) -> None:
        assert normalize_appid(
            "https://store.steampowered.com/app/851100/Sea_of_Stars/"
        ) == "851100"

    def test_from_simple_choice_grava_a_regra_do_jogo_a_partir_do_endereco(self) -> None:
        regra = from_simple_choice(
            choice="steam_game",
            custom_name="store.steampowered.com/app/851100/?snr=1_7_7_230_150_1",
        )
        assert isinstance(regra, MatchCriteria)
        assert regra.window_class == ["steam_app_851100"]

    def test_endereco_de_outra_loja_e_recusado_com_frase_de_gente(self) -> None:
        with pytest.raises(ValueError) as erro:
            from_simple_choice(
                choice="steam_game",
                custom_name="https://www.gog.com/game/sea_of_stars",
            )
        assert str(erro.value) == MSG_STEAM_APPID_INVALIDO


class TestQuandoAJanelaReclama:
    """`parece_endereco` é o gatilho da frase "não reconheci" — e é estreito."""

    @pytest.mark.parametrize(
        "colado",
        [
            "https://www.gog.com/game/sea_of_stars",
            "https://steamcommunity.com/id/alguem/",
            "store.steampowered.com/bundle/851100/",
        ],
    )
    def test_endereco_colado_merece_a_frase(self, colado: str) -> None:
        assert parece_endereco(colado)

    @pytest.mark.parametrize("digitando", ["S", "Sea", "Sea of St", "eldenring", ""])
    def test_nome_sendo_digitado_nao_merece_alerta_nenhum(self, digitando: str) -> None:
        """Alerta piscando a cada tecla é pior que silêncio."""
        assert not parece_endereco(digitando)
