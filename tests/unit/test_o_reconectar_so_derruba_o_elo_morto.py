"""O «Reconectar» só derruba o elo morto (O-RECONECTAR-SO-DERRUBA-O-ELO-MORTO-01, 02/10/2026).

Às 19h07 de 01/10, com o serviço mudo e a lista de jogadores vazia, o
«Reconectar controles» derrubou do rádio os dois DualSense que o kernel tinha
registrado de volta às 19h06: quem decidia «elo morto» era o chamador, por
«não está entre os jogadores», e a lista era a do serviço que não respondia.
O dono do «este endereço tem HID?» é o kernel (`conexao_zumbi.quem_tem_hid`),
e agora o `reconectar` pergunta a ele antes de derrubar; na dúvida, o
controle fica.

O BlueZ é o de mentira da casa (`tests/unit/bluez_de_mentira.py`: o dono vivo
sobre um barramento em processo, nunca o `busctl` da máquina), e a raiz de
`hidraw` mora em `tmp_path`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import conexao_zumbi, diario_do_radio
from hefesto_dualsense4unix.integrations import gesto_de_reconexao as radio
from tests.unit import bluez_de_mentira as bm

#: O segundo DualSense da bancada de mentira (a faixa sintética da casa).
SEGUNDO = "aa:bb:cc:00:00:44"


@pytest.fixture()
def barramento(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> bm.BarramentoDeMentira:
    """Dois DualSense que o BlueZ diz conectados, e o dono vivo sobre eles."""
    monkeypatch.setenv(diario_do_radio.ENV_TRAVA, str(tmp_path / "radio.lock"))
    monkeypatch.setenv(diario_do_radio.ENV_DIARIO, str(tmp_path / "radio-diario.jsonl"))
    barramento = bm.BarramentoDeMentira()
    barramento.mesa[bm.no_de(bm.CONTROLE)][bd.APARELHO]["Connected"] = True
    barramento.mesa[bm.no_de(SEGUNDO)] = {
        bd.APARELHO: {
            "Address": SEGUNDO.upper(),
            "Alias": "DualSense Wireless Controller",
            "Paired": True,
            "Connected": True,
            "Modalias": "usb:v054Cp0CE6d0100",
        }
    }
    dono = bd.DonoVivo(barramento)
    assert dono.ligar()
    monkeypatch.setattr(bd, "_DONO", dono)
    return barramento


def _raiz(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *com_hid: str) -> Path:
    """A raiz de `hidraw` de mentira, com um nó por endereço, como o kernel a escreve."""
    raiz = tmp_path / "class-hidraw"
    for numero, mac in enumerate(com_hid):
        pai = raiz / f"hidraw{numero}" / "device"
        pai.mkdir(parents=True)
        (pai / "uevent").write_text(
            "DRIVER=playstation\nHID_ID=0005:0000054C:00000CE6\n"
            "HID_NAME=DualSense Wireless Controller\n"
            f"HID_PHYS=aa:bb:cc:00:00:11\nHID_UNIQ={mac}\n",
            encoding="utf-8",
        )
    raiz.mkdir(exist_ok=True)
    monkeypatch.setattr(conexao_zumbi, "RAIZ_HIDRAW", str(raiz))
    return raiz


def _quedas(barramento: bm.BarramentoDeMentira) -> list[str]:
    return [
        caminho for caminho, _i, metodo, _a, _t in barramento.chamadas if metodo == "Disconnect"
    ]


# ---------------------------------------------------------------------------
# 1. o vivo fica
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "grafia", [bm.CONTROLE, bm.CONTROLE.upper()], ids=["caixa-baixa", "caixa-alta"]
)
def test_o_vivo_fica(
    barramento: bm.BarramentoDeMentira,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    grafia: str,
) -> None:
    """O BlueZ diz `Connected` e o kernel tem o HID: nem `Disconnect`, nem `Connect`.

    MORDIDA: tire a conferência do kernel de `reconectar` — o `Disconnect`
    sai, como saiu às 19h07.
    """
    _raiz(tmp_path, monkeypatch, bm.CONTROLE)
    with structlog.testing.capture_logs() as registros:
        desfecho = radio.reconectar(grafia)

    assert barramento.metodos() == [], f"o elo vivo foi mexido: {barramento.metodos()}"
    assert desfecho.estado == radio.ESTADO_JA_NO_AR
    assert desfecho.porque == radio.FRASE_JA_NO_AR
    assert not desfecho.caiu
    assert [r["event"] for r in registros if r["event"].startswith("reconexao_")] == [
        "reconexao_elo_vivo_preservado"
    ]


# ---------------------------------------------------------------------------
# 2. o morto cai (o caso de 22/09)
# ---------------------------------------------------------------------------
def test_o_morto_cai_e_e_chamado_de_volta(
    barramento: bm.BarramentoDeMentira, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O BlueZ diz `Connected` e o kernel não tem o endereço: `Disconnect`, depois `Connect`.

    MORDIDA: faça `reconectar` nunca derrubar — este caso reprova.
    """
    _raiz(tmp_path, monkeypatch, SEGUNDO)
    desfecho = radio.reconectar(bm.CONTROLE)

    assert barramento.metodos() == ["Disconnect", "Connect"], barramento.metodos()
    assert _quedas(barramento) == [bm.no_de(bm.CONTROLE)]
    assert desfecho.estado == radio.ESTADO_VOLTOU


# ---------------------------------------------------------------------------
# 3. a dúvida não derruba
# ---------------------------------------------------------------------------
def test_a_duvida_nao_derruba(
    barramento: bm.BarramentoDeMentira, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A raiz que não abre é «não sei», e na dúvida o controle fica.

    MORDIDA: leia a dúvida como conjunto vazio (o `uniqs_com_hid` de antes) —
    o `Disconnect` sai.
    """
    monkeypatch.setattr(conexao_zumbi, "RAIZ_HIDRAW", str(tmp_path / "nao-abre"))
    desfecho = radio.reconectar(bm.CONTROLE)

    assert _quedas(barramento) == [], "a dúvida derrubou o controle"
    assert barramento.metodos() == []
    assert desfecho.estado == radio.ESTADO_NAO_DEU
    assert not desfecho.caiu


def test_a_duvida_com_o_bluez_dizendo_fora_ainda_chama(
    barramento: bm.BarramentoDeMentira, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem elo de pé não há o que derrubar: o `Connect` segue, como antes."""
    barramento.emitir(
        bd.Sinal(
            "mudou",
            caminho=bm.no_de(bm.CONTROLE),
            interface=bd.APARELHO,
            mudadas={"Connected": False},
        )
    )
    monkeypatch.setattr(conexao_zumbi, "RAIZ_HIDRAW", str(tmp_path / "nao-abre"))
    desfecho = radio.reconectar(bm.CONTROLE)

    assert barramento.metodos() == ["Connect"]
    assert desfecho.estado == radio.ESTADO_VOLTOU


def test_o_dono_do_hid_responde_em_tres_valores(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O conjunto, o vazio (ninguém tem) e o `None` (não deu para ler) são três respostas.

    A cura do zumbi segue lendo o vazio, como antes (`uniqs_com_hid`).
    """
    raiz = _raiz(tmp_path, monkeypatch, bm.CONTROLE.upper())
    assert conexao_zumbi.quem_tem_hid(raiz) == {bm.CONTROLE}
    vazia = tmp_path / "vazia"
    vazia.mkdir()
    assert conexao_zumbi.quem_tem_hid(vazia) == set()
    assert conexao_zumbi.quem_tem_hid(tmp_path / "nao-abre") is None
    assert conexao_zumbi.uniqs_com_hid(tmp_path / "nao-abre") == set()
    assert conexao_zumbi.uniqs_com_hid(raiz) == {bm.CONTROLE}


# ---------------------------------------------------------------------------
# 4. o botão de 19h07
# ---------------------------------------------------------------------------
def _a01() -> Any:
    raiz = Path(__file__).resolve().parents[2]
    interface = raiz / "src" / "hefesto_dualsense4unix" / "interface"
    if str(interface) not in sys.path:
        sys.path.insert(0, str(interface))
    from pacotes import a01_jogar

    return a01_jogar


def test_o_botao_com_o_servico_mudo_nao_derruba_quem_tem_hid(
    barramento: bm.BarramentoDeMentira, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O passo 0 com a lista de jogadores vazia (o `{}` do serviço mudo) e os dois com HID.

    MORDIDA: tire a conferência do kernel — os dois caem e são chamados, como
    às 19h07, e o recibo passa a contar dois que «voltaram».
    """
    a01 = _a01()
    from pacotes import Contexto

    _raiz(tmp_path, monkeypatch, bm.CONTROLE, SEGUNDO)
    ctx = Contexto(state={}, mesa=[], conectados=[], estados={})
    voltaram, esperam = a01._o_radio_de_volta(ctx)

    assert _quedas(barramento) == [], f"o botão derrubou {len(_quedas(barramento))} elo(s) vivo(s)"
    assert barramento.metodos() == []
    assert (voltaram, esperam) == (0, 0), "o recibo do botão mudou"
