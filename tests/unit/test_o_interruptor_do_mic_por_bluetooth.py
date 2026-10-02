"""O interruptor da ponte de mic por BT — o portão que o mantém FORA da janela."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from hefesto_dualsense4unix.interface import cartao_do_controle as cc

MOTIVO = (
    "held_ms=17.6 na ponte do mic; a volta depende de arbitrar o hidraw"
)

PECAS_DO_INTERRUPTOR = (
    "TEXTO_MIC_BT_ROTULO",
    "DICA_MIC_BT_LIGAR",
    "DICA_MIC_BT_DESLIGAR",
    "DICA_MIC_BT_NO_CABO",
    "DICA_MIC_BT_IMPEDIDA",
    "AcaoPonteBt",
    "acao_ponte_bt",
    "ligar_ponte_bt",
    "desligar_ponte_bt",
)


def _raiz() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("peca", PECAS_DO_INTERRUPTOR)
def test_o_card_nao_carrega_mais_nenhuma_peca_do_interruptor(peca: str) -> None:
    """A MORDIDA: devolva qualquer uma delas ao módulo e este teste reprova."""
    assert not hasattr(cc, peca), (
        f"`{peca}` voltou ao card: a ponte de mic por BT prende o botão PS em "
        f"pulsos de ~17 ms e o daemon abre a Steam em laço. Antes de religar "
        f"qualquer parte disto, o motivo é {MOTIVO} — feche a arbitragem "
        "do hidraw antes."
    )


def test_o_card_nao_fala_com_o_modulo_da_ponte() -> None:
    """Nem por importação indireta: o gesto tem de estar fora do processo."""
    fonte = inspect.getsource(cc)
    linhas_de_codigo = [
        linha
        for linha in fonte.splitlines()
        if "dualsense_bt_audio" in linha and not linha.lstrip().startswith("#")
    ]

    assert linhas_de_codigo == [], (
        "o card voltou a falar com o módulo da ponte: "
        f"{linhas_de_codigo}. A ponte é capacidade de linha de comando e de "
        "daemon enquanto a posse do hidraw não for arbitrada."
    )


def test_a_tela_nao_diz_mais_pelo_radio() -> None:
    """O rótulo era o convite; some o convite, some o gesto perigoso."""
    codigo = [
        linha
        for linha in inspect.getsource(cc).splitlines()
        if "Pelo rádio" in linha and not linha.lstrip().startswith("#")
    ]

    assert codigo == [], (
        f"a tela voltou a oferecer a ponte pelo rótulo 'Pelo rádio': {codigo}"
    )


def test_a_ponte_continua_existindo_inteira() -> None:
    """Saiu o botão, não a ponte — ela publicou o source no PipeWire em 16/08."""
    from hefesto_dualsense4unix.integrations import dualsense_bt_audio as bt

    assert hasattr(bt, "GerenciadorMicBluetooth")
    assert hasattr(bt, "nos_dualsense_bluetooth")
    assert hasattr(bt, "diagnosticar")

    from hefesto_dualsense4unix.daemon.subsystems import bt_mic

    assert hasattr(bt_mic, "BtMicSubsystem")


def test_o_gate_de_ambiente_continua_sendo_o_caminho_a_mao() -> None:
    """`HEFESTO_DUALSENSE4UNIX_BT_MIC` é como a ponte sobe hoje, e só assim."""
    fonte = (
        _raiz() / "src/hefesto_dualsense4unix/daemon/subsystems/bt_mic.py"
    ).read_text(encoding="utf-8")

    assert "HEFESTO_DUALSENSE4UNIX_BT_MIC" in fonte, (
        "o gate sumiu: sem ele não há NENHUMA forma de subir a ponte, e aí a "
        "remoção do interruptor virou remoção da capacidade"
    )


def test_o_card_diz_no_codigo_como_o_interruptor_volta() -> None:
    """O comentário no lugar da remoção é o mapa, e ele tem de ter endereço."""
    fonte = inspect.getsource(cc)

    assert "O-PS-PRESO" in fonte, "o comentário não aponta para o estudo"
    assert "hidraw" in fonte, "o comentário não diz qual é a condição de volta"
    assert "0x32" in fonte, "o comentário não nomeia a disputa do contador"
