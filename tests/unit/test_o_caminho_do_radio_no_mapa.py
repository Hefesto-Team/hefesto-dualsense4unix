"""O CAMINHO DO RÁDIO escrito no mapa tem de bater com o envelope de produção."""
from __future__ import annotations

import csv
from collections.abc import Callable
from pathlib import Path

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"

ID_DO_RUMBLE = "combinacao.rumble_simultaneo@dualsense"

ID_DA_ESCADA = "plataforma.escada_de_output@dualsense"

COMMON_MOTOR_DIREITO = 2
COMMON_MOTOR_ESQUERDO = 3

ID_DO_DEGRAU_0X32 = 0x32
TAMANHO_DO_DEGRAU_0X32 = 142


def linha_do_mapa(ident: str) -> dict[str, str]:
    """A linha do CSV com este `id`, ou falha dizendo que ela sumiu."""
    with MAPA.open(encoding="utf-8", newline="") as fonte:
        for linha in csv.DictReader(fonte):
            if linha["id"] == ident:
                return linha
    pytest.fail(f"a linha {ident} sumiu de {MAPA} — o mapa perdeu o caminho escrito")


def deslocamento_do_common(montar: Callable[[bytes], bytearray]) -> int:
    """Onde o `common` cai dentro do report, MEDIDO no builder de produção."""
    marcado = bytes(range(rep.COMMON_LEN))
    report = bytes(montar(marcado))
    inicio = report.find(marcado)
    assert inicio >= 0, "o builder não pôs o `common` inteiro dentro do report"
    return inicio


def test_o_mapa_diz_onde_os_bytes_de_motor_caem_em_cada_envelope() -> None:
    """A célula de caminho tem de nomear os bytes que o builder de fato usa."""
    linha = linha_do_mapa(ID_DO_RUMBLE)
    desloc = {
        "cabo": deslocamento_do_common(rep.build_usb_report),
        "radio": deslocamento_do_common(rep.build_bt_report),
    }
    for lado in ("cabo", "radio"):
        celula = linha[f"{lado}_offset"]
        assert celula.strip(), (
            f"`{lado}_offset` de {ID_DO_RUMBLE} está VAZIA — o caminho do "
            f"{lado} deixou de estar escrito no mapa"
        )
        for nome, dentro_do_common in (
            ("direito", COMMON_MOTOR_DIREITO),
            ("esquerdo", COMMON_MOTOR_ESQUERDO),
        ):
            no_report = desloc[lado] + dentro_do_common
            assert f"common[{dentro_do_common}]" in celula, (
                f"`{lado}_offset` não nomeia o common[{dentro_do_common}] "
                f"(motor {nome})"
            )
            assert f"report[{no_report}]" in celula, (
                f"`{lado}_offset` diz outra coisa: no envelope de {lado} o motor "
                f"{nome} cai em report[{no_report}] (o `common` começa em "
                f"report[{desloc[lado]}]), e a célula não diz isso"
            )


def test_o_mapa_diz_o_id_de_output_de_cada_envelope() -> None:
    """O id do report de cada lado vem do módulo de produção, não da memória."""
    linha = linha_do_mapa(ID_DO_RUMBLE)
    esperado = {"cabo": rep.USB_REPORT_ID, "radio": rep.BT_REPORT_ID}
    for lado, ident in esperado.items():
        celula = linha[f"{lado}_report_id"]
        assert f"{ident:#04x}" in celula, (
            f"`{lado}_report_id` de {ID_DO_RUMBLE} não cita {ident:#04x}, que é o "
            f"que `ds_output_report` monta para esse transporte"
        )


def test_os_motores_saem_no_mesmo_lugar_do_common_nos_dois_envelopes() -> None:
    """O payload é IDÊNTICO nos dois lados — só o envelope muda."""
    common = bytearray(rep.COMMON_LEN)
    common[COMMON_MOTOR_DIREITO] = 0xA7
    common[COMMON_MOTOR_ESQUERDO] = 0x5C
    usb = bytes(rep.build_usb_report(common))
    bt = bytes(rep.build_bt_report(common))
    d_usb = deslocamento_do_common(rep.build_usb_report)
    d_bt = deslocamento_do_common(rep.build_bt_report)
    assert usb[d_usb + COMMON_MOTOR_DIREITO] == 0xA7
    assert usb[d_usb + COMMON_MOTOR_ESQUERDO] == 0x5C
    assert bt[d_bt + COMMON_MOTOR_DIREITO] == 0xA7
    assert bt[d_bt + COMMON_MOTOR_ESQUERDO] == 0x5C
    assert usb[d_usb : d_usb + rep.COMMON_LEN] == bt[d_bt : d_bt + rep.COMMON_LEN]


def test_o_carimbo_de_seq_so_conhece_o_degrau_de_78_bytes() -> None:
    """O limite do NOSSO lado, e a célula do mapa que o declara."""
    degrau = bytearray(TAMANHO_DO_DEGRAU_0X32)
    degrau[0] = ID_DO_DEGRAU_0X32
    with pytest.raises(ValueError):
        rep.stamp_bt_seq(degrau, 1)

    celula = linha_do_mapa(ID_DA_ESCADA)["radio_detalhe"]
    assert "stamp_bt_seq" in celula, (
        f"`radio_detalhe` de {ID_DA_ESCADA} não diz mais que o carimbo de seq é o "
        f"limite do nosso lado — se a escada foi construída, a célula tem de "
        f"mudar junto"
    )
    assert str(rep.BT_REPORT_LEN) in celula, (
        f"`radio_detalhe` de {ID_DA_ESCADA} não cita mais o único tamanho que o "
        f"produto sabe carimbar ({rep.BT_REPORT_LEN} B)"
    )
