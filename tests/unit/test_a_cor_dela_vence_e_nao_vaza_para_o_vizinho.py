"""Duas curas da seção "Os controles" que o censo achou arrancáveis sem vermelho."""
from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("a cor do card")

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config import secao_controles as secao
from hefesto_dualsense4unix.app.actions.external_controllers import (
    ID_DE_OUTRA_COR,
)
from hefesto_dualsense4unix.integrations.cor_do_plastico import (
    NOMES_DE_FABRICA,
    TONS,
    CorDoPlastico,
    tom_para_a_borda,
)

DECLARADA = NOMES_DE_FABRICA["02"]

LIDA = CorDoPlastico(codigo="05", nome=NOMES_DE_FABRICA["05"], tom=TONS["05"])

#: O endereço do DualSense da mesa de teste. Máscara da casa: octetos 4 e 5
UNIQ_ADOTADO = "aa:bb:cc:00:00:7e"

UNIQ_FORJADO = "02:fe:00:9d:41:6b"


class _Hospedeiro:
    """O mínimo que a seção pede do `HefestoApp`, e nada do daemon vivo."""

    def __init__(self, payload: dict[str, Any], pendente: Any = None) -> None:
        self._controles_leitor = lambda: payload
        self._mesa_leitor = lambda: None
        self._cor_do_plastico_leitor = lambda _uniq: None
        self._maquina_pendente = pendente
        self._edit_target_uniq = None


def _montar(payload: dict[str, Any], pendente: Any = None) -> Any:
    """Monta a seção numa caixa solta e devolve o painel."""
    painel = secao._PainelDosControles(_Hospedeiro(payload, pendente))
    fora = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    painel.montar(fora)
    painel._caixa_de_fora = fora
    return painel


def _cards_na_grade(painel: Any) -> list[Any]:
    """Os cards que estão na tela, na ordem em que a grade os recebeu."""
    for filho in painel._caixa.get_children():
        if isinstance(filho, Gtk.Grid):
            return sorted(filho.get_children(), key=lambda card: card.dados.titulo)
    return []


class TestAEscolhaDelaVenceALeitura:
    def test_o_tom_da_borda_e_o_da_cor_declarada(self) -> None:
        """A decisão dela de 21/08: a escolha vence a tabela."""
        assert secao._tom_da_cor(DECLARADA, LIDA) == tom_para_a_borda(TONS["02"])
        assert secao._tom_da_cor(DECLARADA, LIDA) != tom_para_a_borda(LIDA.tom)

    def test_sem_declaracao_a_borda_e_a_da_leitura(self) -> None:
        """O outro lado da precedência: sem escolha dela, o aparelho fala."""
        assert secao._tom_da_cor(None, LIDA) == tom_para_a_borda(LIDA.tom)

    def test_nome_que_a_casa_nao_conhece_nao_herda_o_tom_lido(self) -> None:
        """Ela digitou uma cor de coleção: borda neutra, nunca a cor lida."""
        assert secao._tom_da_cor("Verde-abacate", LIDA) == ""

    def test_a_lista_marca_o_botao_que_ela_escolheu(self) -> None:
        conhecida = secao._cor_na_tela(DECLARADA, LIDA)
        assert conhecida == ("02", "", DECLARADA)

    def test_nome_de_fora_da_lista_vai_para_outra_com_o_texto_dela(self) -> None:
        assert secao._cor_na_tela("Verde-abacate", LIDA) == (
            ID_DE_OUTRA_COR,
            "Verde-abacate",
            "Verde-abacate",
        )

    def test_sem_declaracao_a_lista_nasce_sem_marca_e_mostra_o_lido(self) -> None:
        assert secao._cor_na_tela(None, LIDA) == ("", "", LIDA.nome)

    def test_o_card_montado_nasce_com_a_borda_da_cor_declarada(self) -> None:
        """A costura inteira: declaração pendente mais leitura, na tela."""
        endereco = UNIQ_ADOTADO.replace(":", "")
        painel = _montar(
            {
                "controllers": [
                    {
                        "uniq": UNIQ_ADOTADO,
                        "connected": True,
                        "transport": "bluetooth",
                        "player_slot": 1,
                    }
                ],
                "external": [],
            },
            pendente={"controles": {endereco: {"cor": DECLARADA}}},
        )
        painel._cores[UNIQ_ADOTADO] = LIDA
        painel.reexaminar()

        (card,) = _cards_na_grade(painel)
        assert card.dados.tom == tom_para_a_borda(TONS["02"])
        assert card.dados.cor_id == "02"
        assert card.dados.cor_lida == ""


def _mesa_de_dois_clones() -> dict[str, Any]:
    """Dois Nintendo-class no cabo, com o MESMO ``uniq`` sintetizado."""
    clone = {
        "name": "Nintendo Switch Pro Controller",
        "uniq": UNIQ_FORJADO,
        "bus": "usb",
        "vendor_id": "057e",
        "product_id": "2009",
    }
    return {
        "controllers": [],
        "external": [
            {**clone, "player_slot": 1, "evdev_path": "/dev/input/event20"},
            {**clone, "player_slot": 2, "evdev_path": "/dev/input/event21"},
        ],
    }


class TestChaveRepetidaNaoVazaParaOVizinho:
    def test_dois_clones_nao_dividem_a_chave_do_card(self) -> None:
        painel = _montar(_mesa_de_dois_clones())
        primeiro, segundo = _cards_na_grade(painel)

        assert primeiro.dados.chave != segundo.dados.chave, (
            "os dois clones responderam pela mesma chave — declarar a cor de um "
            "repinta o outro"
        )

    def test_declarar_a_cor_de_um_clone_nao_pinta_a_borda_do_outro(self) -> None:
        """O defeito de tela que a cura existe para impedir."""
        painel = _montar(_mesa_de_dois_clones())
        jogador_1, jogador_2 = _cards_na_grade(painel)
        assert jogador_1.dados.titulo == "Jogador 1"
        assert jogador_2.dados.titulo == "Jogador 2"

        painel._ao_declarar(jogador_1.dados.chave, "cor", DECLARADA)

        assert jogador_1.dados.tom == tom_para_a_borda(TONS["02"]), (
            "a borda do card em que ela declarou não acendeu"
        )
        assert jogador_2.dados.tom == "", (
            "a cor declarada no Jogador 1 vazou para a borda do Jogador 2 — "
            "CLONE-01 pela porta dos fundos"
        )

    def test_o_clone_nao_persiste_declaracao_nenhuma(self) -> None:
        """O endereço forjado começa em ``02`` e o schema o recusa."""
        painel = _montar(_mesa_de_dois_clones())
        jogador_1, _jogador_2 = _cards_na_grade(painel)

        painel._ao_declarar(jogador_1.dados.chave, "cor", DECLARADA)

        assert painel._host._maquina_pendente is None
