"""A fase em pé visita SÓ as entradas vazias — e o veredito sai do ``sysfs``."""
from __future__ import annotations

from hefesto_dualsense4unix.app.widgets.calibrar_entradas import (
    FACE_ATRAS,
    LogicaDaCalibracao,
)
from hefesto_dualsense4unix.integrations.censo_do_barramento import Censo
from hefesto_dualsense4unix.utils.maquina import CALCULADOS_DA_ENTRADA, MapaDaMesa
from tests.unit.test_a_fase_sentada_resolve_o_hub import GravadorDeMentira
from tests.unit.test_entradas_do_gabinete import _entradas


def _logica(*, com_hub: bool = False) -> LogicaDaCalibracao:
    """A cerimônia sobre a bancada de mentira, sem censo de aparelho nenhum."""
    return LogicaDaCalibracao(
        MapaDaMesa(),
        Censo(),
        _entradas(com_hub=com_hub),
        gravar=GravadorDeMentira(),
    )


def test_entrada_ocupada_nao_entra_na_caminhada() -> None:
    """15 buracos, 4 ocupados, 11 na caminhada — e nenhum deles com aparelho."""
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
    """Sem entrada vazia, a fase em pé simplesmente não acontece."""
    logica = LogicaDaCalibracao(MapaDaMesa(), Censo(), (), gravar=GravadorDeMentira())
    assert logica.caminhada() == ()


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
    agora = _entradas()

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


def test_nao_alcanco_tira_a_entrada_da_conta_em_vez_de_deixar_divida() -> None:
    """A entrada SOME do total. Não vira pendência, não volta a perguntar."""
    logica = _logica()
    antes = len(logica.caminhada())
    logica.nao_alcanco(logica.caminhada()[0])

    assert len(logica.caminhada()) == antes - 1, (
        "'Não alcanço' deixou dívida em vez de tirar a entrada da conta"
    )


def test_a_entrada_aprendida_guarda_os_nos_do_buraco() -> None:
    """O que alcança a entrada VAZIA é ``nos``, e ``caminho`` não alcança."""
    from hefesto_dualsense4unix.utils.lugar import caminho_do_lado_20

    logica = _logica()
    furo = logica.caminhada()[0]
    numero = logica.aprender(furo, FACE_ATRAS)

    assert logica.portas[numero]["nos"] == list(furo.nos)
    mapa = MapaDaMesa.model_validate(logica.como_documento())
    assert mapa.portas[numero].nos == list(furo.nos)
    assert mapa.portas[numero].caminho == caminho_do_lado_20(furo.nos)
    assert "caminho" not in mapa.portas[numero].model_dump(exclude=set(CALCULADOS_DA_ENTRADA)), (
        "uma entrada vazia não guarda aparelho, e inventar um seria mentir"
    )


def _janela(entradas):
    from hefesto_dualsense4unix.app.widgets.calibrar_entradas import (
        JanelaDeCalibrarEntradas,
    )

    return JanelaDeCalibrarEntradas(
        object(), MapaDaMesa(), Censo(), entradas, gravar=GravadorDeMentira()
    )


def test_a_janela_so_confirma_quando_o_barramento_muda() -> None:
    """O tique da fase em pé, no caminho real: cabo inerte não confirma."""
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
