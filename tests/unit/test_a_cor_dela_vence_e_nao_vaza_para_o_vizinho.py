"""Duas curas da seção "Os controles" que o censo achou arrancáveis sem vermelho.

23/08/2026. Uma auditoria fez 50 mutações na aba Configurações; 39 morderam e
**11 passaram verdes com a cura arrancada**. Duas das quatro mais graves moram
aqui, e as duas protegem a mesma coisa: a cor que ela escolheu, no card certo.

AS DUAS CURAS
-------------

1. **A escolha dela vence a leitura** — ``_tom_da_cor`` e ``_cor_na_tela``
   (`secao_controles.py`), que executam a decisão dela de 21/08/2026: *"a
   pessoa pode escolher a cor, e a escolha dela vence a tabela"*. E há medição
   atrás disso: das vinte e uma linhas de ``TONS``, **vinte são aproximadas** —
   só a ``05`` (Starlight Blue) foi medida. Arrancar a precedência devolve a
   borda para a tabela aproximada e derruba a decisão dela em silêncio, sem uma
   linha vermelha em lugar nenhum.
2. **Chave repetida repinta o card vizinho** — ``_sem_chave_repetida``, que é o
   CLONE-01 voltando pela porta dos fundos. Dois Nintendo-class no cabo recebem
   do ``hid-nintendo`` o MESMO ``uniq`` sintetizado (``02`` + VID + PID + bus);
   sem o desempate posicional os dois cards respondem pela mesma chave, e
   ``_repintar`` acha no dicionário o card que entrou por ÚLTIMO. Declarar a cor
   do Jogador 1 pinta a borda do Jogador 2.

POR QUE A SEGUNDA PRECISA DA SEÇÃO MONTADA
------------------------------------------

``_sem_chave_repetida`` sozinha é uma função que devolve lista: medir só ela
prova que as chaves saem distintas, não que o repinte acerta o card. O defeito
que a cura existe para impedir é de TELA — a borda errada acendendo —, e por
isso o teste do vazamento monta a grade com GTK de verdade e olha a borda dos
dois cards. É o mesmo motivo pelo qual `test_config_06_cards_tem_a_mesma_altura`
mede a seção e não só o widget.

AS MORDIDAS, ARRANCADAS E CONFERIDAS EM 23/08/2026
--------------------------------------------------

==================================================================  ===========
mutação                                                             reprova
==================================================================  ===========
``_tom_da_cor`` perde o ramo ``if declarada`` (a leitura vence)      4 de 10
``_tom_da_cor`` cai na leitura quando o nome é desconhecido          1 de 10
``_cor_na_tela`` perde o ramo ``if declarada``                       3 de 10
``_cards_da_mesa`` não chama ``_sem_chave_repetida``                 2 de 10
==================================================================  ===========

A última mutação, medida com o painel na mão: declarar Cosmic Red no Jogador 1
deixou ``jogador_1.dados.tom`` vazio e acendeu ``jogador_2.dados.tom`` em
``#da244b``. A cor foi para o card errado, e nada mais na suíte reclamou.
"""
from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`. `importorskip("gi")`
# aceita o stub que outro arquivo planta em `sys.modules`; esta guarda não.
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

#: A cor que ELA declara. Código ``02`` na tabela de fábrica.
DECLARADA = NOMES_DE_FABRICA["02"]

#: A cor que o APARELHO responde. Código ``05`` — a única das vinte e uma
#: medida de verdade, e mesmo assim a declaração dela tem de vencê-la.
LIDA = CorDoPlastico(codigo="05", nome=NOMES_DE_FABRICA["05"], tom=TONS["05"])

#: O endereço do DualSense da mesa de teste. Máscara da casa: octetos 4 e 5
#: zerados, na faixa de documentação que o `check_test_data.sh` reconhece.
UNIQ_ADOTADO = "aa:bb:cc:00:00:7e"

#: O ``uniq`` que o `hid-nintendo` SINTETIZA para um clone sem endereço —
#: ``02`` + VID + PID + bus. Os dois clones recebem este mesmo valor, que é a
#: raiz do CLONE-01. Localmente administrado por construção: não existe em
#: hardware de ninguém.
UNIQ_FORJADO = "02:fe:00:9d:41:6b"


class _Hospedeiro:
    """O mínimo que a seção pede do `HefestoApp`, e nada do daemon vivo.

    ``_controles_leitor`` é o ponto de injeção da seção (irmão do
    ``_mesa_leitor`` de CONFIG-02): sem ele, montar a aba num teste conversaria
    com o daemon da máquina de quem roda a suíte.

    ``_mesa_leitor`` é a marca da bancada de retrato — é o que faz
    ``_perguntar_pela_mesa`` voltar sem sondar quem segura hidraw. E
    ``_cor_do_plastico_leitor`` fecha a última porta para o aparelho: sem ele um
    controle no cabo receberia comando da família ``0x80`` durante o teste.
    """

    def __init__(self, payload: dict[str, Any], pendente: Any = None) -> None:
        self._controles_leitor = lambda: payload
        self._mesa_leitor = lambda: None
        self._cor_do_plastico_leitor = lambda _uniq: None
        self._maquina_pendente = pendente
        self._edit_target_uniq = None


def _montar(payload: dict[str, Any], pendente: Any = None) -> Any:
    """Monta a seção numa caixa solta e devolve o painel.

    A caixa de fora fica pendurada no painel de propósito. Sem essa referência
    o Python solta o último `Gtk.Box`, o GObject é finalizado, e a finalização
    DESTRÓI os filhos — a grade some e o teste mede uma seção vazia achando que
    mede o produto. Custou uma medição falsa em 23/08/2026.
    """
    painel = secao._PainelDosControles(_Hospedeiro(payload, pendente))
    fora = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    painel.montar(fora)
    painel._caixa_de_fora = fora
    return painel


def _cards_na_grade(painel: Any) -> list[Any]:
    """Os cards que estão na tela, na ordem em que a grade os recebeu.

    Lidos da GRADE e não de ``painel._cards``: aquele dicionário é indexado pela
    chave, que é justamente o que a cura do CLONE-01 conserta — medir por ele
    seria perguntar ao defeito se ele existe.
    """
    for filho in painel._caixa.get_children():
        if isinstance(filho, Gtk.Grid):
            return sorted(filho.get_children(), key=lambda card: card.dados.titulo)
    return []


# ---------------------------------------------------------------------------
# Cura 1 — a escolha dela vence a leitura
# ---------------------------------------------------------------------------


class TestAEscolhaDelaVenceALeitura:
    def test_o_tom_da_borda_e_o_da_cor_declarada(self) -> None:
        """A decisão dela de 21/08: a escolha vence a tabela.

        As duas asserções são a mesma frase pelos dois lados — o tom É o da
        declarada, e NÃO é o da lida. Sem a segunda, a mutação que devolve a
        leitura passaria se por acaso os dois hexa coincidissem.
        """
        assert secao._tom_da_cor(DECLARADA, LIDA) == tom_para_a_borda(TONS["02"])
        assert secao._tom_da_cor(DECLARADA, LIDA) != tom_para_a_borda(LIDA.tom)

    def test_sem_declaracao_a_borda_e_a_da_leitura(self) -> None:
        """O outro lado da precedência: sem escolha dela, o aparelho fala."""
        assert secao._tom_da_cor(None, LIDA) == tom_para_a_borda(LIDA.tom)

    def test_nome_que_a_casa_nao_conhece_nao_herda_o_tom_lido(self) -> None:
        """Ela digitou uma cor de coleção: borda neutra, nunca a cor lida.

        Pintar com a leitura aqui seria mostrar na borda uma cor que ela acabou
        de dizer que NÃO é a do controle.
        """
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
        """A costura inteira: declaração pendente mais leitura, na tela.

        As duas metades chegam por caminhos diferentes — a declaração pelo
        ``_maquina_pendente`` do rodapé, a leitura pelo cache ``_cores`` que a
        resposta do aparelho preenche — e é no card que elas se encontram.
        """
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
        # A resposta do aparelho chega DEPOIS da montagem, como na vida.
        painel._cores[UNIQ_ADOTADO] = LIDA
        painel.reexaminar()

        (card,) = _cards_na_grade(painel)
        assert card.dados.tom == tom_para_a_borda(TONS["02"])
        assert card.dados.cor_id == "02"
        # A leitura não some da tela; ela só não manda na borda.
        assert card.dados.cor_lida == ""


# ---------------------------------------------------------------------------
# Cura 2 — chave repetida não repinta o card vizinho (CLONE-01)
# ---------------------------------------------------------------------------


def _mesa_de_dois_clones() -> dict[str, Any]:
    """Dois Nintendo-class no cabo, com o MESMO ``uniq`` sintetizado.

    É o caso medido do CLONE-01, e não uma invenção de teste: o `hid-nintendo`
    forja o endereço a partir de VID, PID e bus, que são iguais nos dois.
    """
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
        """O defeito de tela que a cura existe para impedir.

        Declaro no Jogador 1 e olho o Jogador 2. Com a chave repetida, o
        dicionário ``_cards`` guarda só o card que entrou por último — o Jogador
        2 —, e é a borda DELE que acende.
        """
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
        """O endereço forjado começa em ``02`` e o schema o recusa.

        Sem esta linha o teste acima poderia estar medindo um caminho que grava
        no ``maquina.json`` a FUSÃO de dois aparelhos. O ``_ao_declarar`` tem de
        cair no ramo sem endereço: a escolha vale na tela e morre com a janela.
        """
        painel = _montar(_mesa_de_dois_clones())
        jogador_1, _jogador_2 = _cards_na_grade(painel)

        painel._ao_declarar(jogador_1.dados.chave, "cor", DECLARADA)

        assert painel._host._maquina_pendente is None
