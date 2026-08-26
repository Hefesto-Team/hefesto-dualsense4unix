"""A fase em pé visita SÓ as entradas vazias — e o veredito sai do ``sysfs``.

``CALIBRAR-AS-ENTRADAS-01``, tarefa ``CAL-4`` (26/08/2026). Dois furos fatais da
refutação moram aqui.

F-2 — A CAMINHADA NUNCA VISITA BURACO OCUPADO
----------------------------------------------

Mandar a pessoa ao fundo do gabinete para ensinar uma entrada que o computador
já sabe é caminhada por dado que a máquina tem: entrada OCUPADA não precisa de
caminhada, porque o aparelho que está nela já diz qual entrada é (§2.3).

E o buraco é a unidade, nunca o nó: um buraco USB 3.x tem **dois** nós, e o lado
3.x do buraco onde o mouse dela está responde ``not attached`` do mesmo jeito.
Perguntar por nó mandaria ela se ajoelhar para encaixar um cabo onde já tem
aparelho.

F-1 — O VEREDITO NÃO PODE VIR DA MÃO
-------------------------------------

*"o controle vibrou, logo a entrada é boa"* é falso sempre que o mesmo controle
também está pareado por Bluetooth — o caso normal dela. Com dois nós do mesmo
aparelho, o pulso sai pelo **rádio** e chega à mão mesmo que o cabo não tenha
feito nada.

A BANCADA DESTE ARQUIVO
------------------------

É a mesma bancada de mentira da ``CAL-1``
(``tests/unit/test_entradas_do_gabinete.py``), importada e não copiada: duas
cópias do mesmo ``/sys`` divergiriam na primeira vez que uma delas ganhasse um
caso novo, e a régua da tela passaria a medir uma máquina que a régua do leitor
não conhece.
"""
from __future__ import annotations

from hefesto_dualsense4unix.app.widgets.calibrar_entradas import (
    FACE_ATRAS,
    LogicaDaCalibracao,
)
from hefesto_dualsense4unix.integrations.censo_do_barramento import Censo
from hefesto_dualsense4unix.utils.maquina import MapaDaMesa
from tests.unit.test_a_fase_sentada_resolve_o_hub import GravadorDeMentira
from tests.unit.test_entradas_do_gabinete import _entradas


def _logica(*, com_hub: bool = False) -> LogicaDaCalibracao:
    """A cerimônia sobre a bancada de mentira, sem censo de aparelho nenhum.

    O ``Censo`` vazio é de propósito: o que esta régua mede é a CAMINHADA, e
    ela nasce das entradas, não dos aparelhos. Misturar as duas fontes aqui
    esconderia qual das duas responde.
    """
    return LogicaDaCalibracao(
        MapaDaMesa(),
        Censo(),
        _entradas(com_hub=com_hub),
        gravar=GravadorDeMentira(),
    )


# ---------------------------------------------------------------------------
# A mordida do F-2
# ---------------------------------------------------------------------------


def test_entrada_ocupada_nao_entra_na_caminhada() -> None:
    """15 buracos, 4 ocupados, 11 na caminhada — e nenhum deles com aparelho.

    MORDIDA: trocar ``vazias(...)`` por ``furos(...)`` em
    ``LogicaDaCalibracao.caminhada`` (listar todas). A lista vai a 15 e o teste
    reprova **nomeando a primeira ocupada** que ela seria mandada a visitar.
    """
    logica = _logica()
    caminhada = logica.caminhada()

    ocupadas = [furo for furo in caminhada if furo.aparelho]
    assert not ocupadas, (
        "a caminhada mandaria ela a um buraco que já tem aparelho — o "
        f"primeiro é {ocupadas[0].nos} com {ocupadas[0].aparelho!r} dentro. "
        "Entrada ocupada não precisa de caminhada: o aparelho que está nela "
        "já diz qual entrada é"
    )
    nos_visitados = {no for furo in caminhada for no in furo.nos}
    assert "usb2-port2" not in nos_visitados, (
        "`usb2-port2` é o lado 3.x do buraco onde o mouse `1-6` está"
    )
    assert len(caminhada) == 11, (
        f"4 buracos ocupados de 15 deixam 11 para a caminhada; contei "
        f"{len(caminhada)}"
    )


def test_a_mesa_toda_ocupada_nao_tem_fase_em_pe() -> None:
    """Sem entrada vazia, a fase em pé simplesmente não acontece.

    Não é caso de borda: é o desenho. A caminhada existe para o que a máquina
    não sabe, e uma mesa cheia não tem nada que ela não saiba.
    """
    logica = LogicaDaCalibracao(MapaDaMesa(), Censo(), (), gravar=GravadorDeMentira())
    assert logica.caminhada() == ()


# ---------------------------------------------------------------------------
# A mordida do F-1
# ---------------------------------------------------------------------------


def test_o_veredito_vem_do_sysfs_e_nao_da_mao() -> None:
    """O cabo inerte não confirma nada, mesmo com o pulso chegando à mão.

    A leitura de ANTES e a de AGORA são a MESMA: o controle está pareado por
    rádio e vibrou, mas nó nenhum saiu de ``not attached``. Confirmar aqui
    seria dar por boa uma entrada que não enumerou coisa nenhuma.

    MORDIDA: fazer ``confirmar_entrada_nova`` devolver o primeiro furo vazio em
    vez de comparar as duas leituras — que é a versão "o controle vibrou, logo
    a entrada é boa". A régua reprova dizendo que ela confirmou com o cabo
    inerte.
    """
    logica = _logica()
    antes = _entradas()
    agora = _entradas()  # nada mudou: o cabo não fez nada

    assert logica.confirmar_entrada_nova(antes, agora) is None, (
        "a tela confirmou uma entrada sem que o barramento tivesse mudado — "
        "é o pulso pelo rádio sendo lido como veredito do cabo"
    )


def test_o_no_que_encheu_confirma_e_e_o_buraco_certo() -> None:
    """Com o hub plugado, dois nós saem de ``not attached`` e ISSO confirma.

    É o outro lado da mesma régua: um dublê que só sabe recusar também não é
    régua. ``3-1-port2`` é o nó que o DualSense ocupa quando o hub volta.
    """
    logica = _logica()
    antes = _entradas()
    agora = _entradas(com_hub=True)

    furo = logica.confirmar_entrada_nova(antes, agora)
    assert furo is not None, "o barramento mudou e a tela não viu"
    assert furo.aparelho, "confirmou um buraco que continua vazio"


# ---------------------------------------------------------------------------
# `[Não alcanço]` — saída de primeira classe (R22)
# ---------------------------------------------------------------------------


def test_nao_alcanco_tira_a_entrada_da_conta_em_vez_de_deixar_divida() -> None:
    """A entrada SOME do total. Não vira pendência, não volta a perguntar.

    MORDIDA: fazer ``nao_alcanco`` só registrar (sem o filtro em
    ``caminhada``). O total continua 11, e o teste reprova — que é a cerimônia
    passando a cobrar por um trabalho que ela já disse que não vai fazer.
    """
    logica = _logica()
    antes = len(logica.caminhada())
    logica.nao_alcanco(logica.caminhada()[0])

    assert len(logica.caminhada()) == antes - 1, (
        "'Não alcanço' deixou dívida em vez de tirar a entrada da conta"
    )


def test_a_entrada_aprendida_guarda_os_nos_do_buraco() -> None:
    """O que alcança a entrada VAZIA é ``nos``, e ``caminho`` não alcança.

    ``caminho`` nomeia o APARELHO e some do ``/sys`` quando ele sai; ``nos``
    nomeia o BURACO. Sem a lista, "a entrada 7" só existiria enquanto houvesse
    algo nela — que é o defeito que esta tela inteira existe para curar.
    """
    logica = _logica()
    furo = logica.caminhada()[0]
    numero = logica.aprender(furo, FACE_ATRAS)

    assert logica.portas[numero]["nos"] == list(furo.nos)
    mapa = MapaDaMesa.model_validate(logica.como_documento())
    assert mapa.portas[numero].nos == list(furo.nos)
    assert mapa.portas[numero].caminho is None, (
        "uma entrada vazia não tem aparelho, e inventar um seria mentir"
    )


# ---------------------------------------------------------------------------
# A fase em pé na JANELA de verdade
# ---------------------------------------------------------------------------
#
# Sem `Gtk.Window` mostrada: sob Xvfb não há gerenciador de janelas e uma janela
# mostrada fica 1x1 para sempre (`COMO-OLHAR-A-TELA.md`). A guarda `exigir_gi_
# real` é chamada dentro do teste para que as réguas puras acima rodem mesmo
# onde não há PyGObject.


def _janela(entradas):
    from hefesto_dualsense4unix.app.widgets.calibrar_entradas import (
        JanelaDeCalibrarEntradas,
    )

    return JanelaDeCalibrarEntradas(
        object(), MapaDaMesa(), Censo(), entradas, gravar=GravadorDeMentira()
    )


def test_a_janela_so_confirma_quando_o_barramento_muda() -> None:
    """O tique da fase em pé, no caminho real: cabo inerte não confirma.

    MORDIDA: fazer ``tique`` aprender o primeiro furo vazio em vez de comparar
    as duas leituras. A janela declara uma entrada que nunca enumerou nada, e
    o teste reprova.
    """
    from tests.conftest import exigir_gi_real

    exigir_gi_real("a janela de calibração")
    janela = _janela(_entradas())
    janela.em_pe = True
    janela.redesenhar()

    assert janela.tique(_entradas()) == "", (
        "a janela confirmou uma entrada com o barramento parado"
    )
    numero = janela.tique(_entradas(com_hub=True))
    assert numero, "o hub voltou ao barramento e a janela não viu"
    assert janela.logica.portas[numero]["nos"], (
        "a entrada aprendida nasceu sem os nós do buraco, e é a lista de nós "
        "que alcança a entrada VAZIA"
    )


def test_nao_alcanco_na_janela_encolhe_a_caminhada() -> None:
    """O botão de primeira classe, no caminho real."""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("a janela de calibração")
    janela = _janela(_entradas())
    janela.em_pe = True
    janela.redesenhar()
    antes = len(janela.logica.caminhada())

    janela.botao_nao_alcanco.clicked()

    assert len(janela.logica.caminhada()) == antes - 1
