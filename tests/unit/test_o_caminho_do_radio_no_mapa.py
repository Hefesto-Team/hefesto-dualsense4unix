"""O CAMINHO DO RÁDIO escrito no mapa tem de bater com o envelope de produção.

Pedido dela, 03/09/2026: *"a ideia é ver o que no código tá setado pra funcionar
só via cabo e não BT. e verificar no specs o caminho do Bt pra garantir que lá
ele possa funcionar em ambos os modos."* — e o mecanismo que ela descreveu é o
mapa: *"quando colocarmos o caminho certo no specs o script original vai fazer
uso desse place holder setado e automaticamente parear."*

Esta régua fecha o buraco que sobra desse mecanismo: **uma célula de caminho
pode envelhecer em silêncio.** O `check_paridade_transporte.py` é cego ao
CONTEÚDO das colunas sem domínio — está escrito na docstring dele, medido em
31/08/2026 com quatro estragos plausíveis passando de `rc=0`. Trocar
`report[5]` por `report[27]` no `radio_offset` não reprova em lugar nenhum, e o
`specs.html` publica o número errado como fato.

O que se trava aqui, e são duas coisas de naturezas diferentes:

1. **O CAMINHO ESCRITO** (linha `combinacao.rumble_simultaneo@dualsense`) — a
   célula diz em que byte de cada envelope os motores caem, e o teste MEDE isso
   nos builders de produção em vez de redigitar o número. Se o deslocamento do
   `common` mudar, ou se alguém esvaziar a célula, reprova.
2. **O LIMITE DO NOSSO LADO** (linha `plataforma.escada_de_output@dualsense`) —
   o rádio declara NOVE reports de output (0x31..0x39) e o firmware já obedeceu
   a três deles com o olho dela (15/08/2026); o produto só sabe montar e
   carimbar o de 78 bytes. Quem construir a escada faz este nó reprovar, e é o
   ponto: o mapa não pode continuar dizendo "só o 78" depois que deixar de ser
   verdade.

O que esta régua NÃO faz: dizer o que o aparelho faz com os bytes. Isso é
bancada e olho dela; aqui o teto é o que o produto MONTA.
"""
from __future__ import annotations

import csv
from collections.abc import Callable
from pathlib import Path

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"

#: A linha do rumble em par, que é onde o caminho dos DOIS envelopes está escrito.
ID_DO_RUMBLE = "combinacao.rumble_simultaneo@dualsense"

#: A linha da escada de output por rádio, que é onde o LIMITE está escrito.
ID_DA_ESCADA = "plataforma.escada_de_output@dualsense"

#: Offsets dos motores DENTRO do `common` (espelho do
#: `dualsense_output_report_common`): direito/weak em [2], esquerdo/strong em [3].
COMMON_MOTOR_DIREITO = 2
COMMON_MOTOR_ESQUERDO = 3

#: Um degrau da escada que o produto NÃO sabe carimbar hoje: o 0x32 de 142 B.
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
    """Onde o `common` cai dentro do report, MEDIDO no builder de produção.

    Não se redigita 1 e 3 aqui: monta-se um `common` de bytes distinguíveis e
    procura-se onde ele foi parar. É a mesma disciplina do
    `test_paridade_transporte_envelope.py` — o instrumento não pode ser uma
    segunda implementação do envelope.
    """
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
    """O payload é IDÊNTICO nos dois lados — só o envelope muda.

    É esta simetria que faz o rumble não ter caminho de rádio a construir: quem
    escolhe o envelope é o transporte, e o `common` viaja igual. Se alguém
    reintroduzir uma diferença de payload por transporte, este nó cai.
    """
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
    """O limite do NOSSO lado, e a célula do mapa que o declara.

    O rádio declara nove reports de output; o `stamp_bt_seq` recusa todos menos
    o 0x31 de 78 B. Um degrau maior entregue pelo `writeReport` sairia com seq 0
    e sem CRC recalculado — descartado pelo firmware, com o nosso log dizendo
    "escrito", que é o pior desfecho que esta casa conhece.
    """
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
