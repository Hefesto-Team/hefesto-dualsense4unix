"""A cadeia USB se reconhece pelo tipo, com o nome de cada fonte e o hub físico contado uma vez.

O ``/sys`` de mentira (``tests/fixtures/cadeia_usb/``) tem a forma medida em 12/10/2026, com
``vid:pid``, Container ID e nomes sintéticos.

Mordidas:

* tirar o agrupamento por Container ID em ``hubs_fisicos``: o hub deixa de ser um, e
  :func:`test_um_hub_de_dois_lados_com_cascata_e_um_hub_de_sete_entradas` reprova;
* trocar o teste da capacidade ``0x03`` por ``version >= 3``: o Wi-Fi a 480M publica ``2.10`` e
  some do enlace abaixo, e :func:`test_o_enlace_abaixo_so_no_que_publica_superspeed` reprova.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    Aparelho,
    Censo,
    cadeia_de_hubs,
    enlace_abaixo,
    hubs_fisicos,
    ler_o_barramento,
    ler_o_bos,
)
from tests.fixtures.cadeia_usb.montar import SysDeMentira


@pytest.fixture
def sys_usb(tmp_path: Path) -> SysDeMentira:
    return SysDeMentira(tmp_path)


def _censo(sys_usb: SysDeMentira) -> Censo:
    return ler_o_barramento(**sys_usb.fontes())


def _por_nome(censo: Censo) -> dict[str, Aparelho]:
    return {a.nome_do_kernel: a for a in censo.aparelhos}


def test_um_hub_de_dois_lados_com_cascata_e_um_hub_de_sete_entradas(sys_usb: SysDeMentira) -> None:
    censo = _censo(sys_usb)
    hubs = hubs_fisicos(censo)
    assert len(hubs) == 1, [h.nos for h in hubs]
    (hub,) = hubs
    assert sorted(Path(n).name for n in hub.nos) == ["3-1", "3-1.1", "4-1", "4-1.1"]
    assert hub.entradas == 7
    assert hub.container_id == "0123456789abcdef0123456789abcdef"


def test_os_dois_lados_do_hub_dao_o_mesmo_hub_na_cadeia(sys_usb: SysDeMentira) -> None:
    censo = _censo(sys_usb)
    nomes = _por_nome(censo)
    receptor = cadeia_de_hubs(censo, nomes["3-1.1.2"].no)
    wifi = cadeia_de_hubs(censo, nomes["3-1.4"].no)
    assert len(receptor) == 1, receptor
    assert receptor == wifi
    assert cadeia_de_hubs(censo, nomes["3-1.1"].no) == (), "um hub não está atrás de si mesmo"


def test_sem_container_id_o_par_sai_do_peer(sys_usb: SysDeMentira) -> None:
    for nome in ("3-1", "3-1.1", "4-1", "4-1.1"):
        sys_usb.nos[nome].pop("bos")
    sys_usb.montar()
    hubs = hubs_fisicos(_censo(sys_usb))
    grupos = sorted(sorted(Path(n).name for n in h.nos) for h in hubs)
    # sem o Container ID a cascata interna não se prova: cada lado se amarra ao par dele
    assert grupos == [["3-1", "4-1"], ["3-1.1", "4-1.1"]]


def test_sem_container_id_e_sem_peer_cada_no_e_um_hub(sys_usb: SysDeMentira) -> None:
    for nome in ("3-1", "3-1.1", "4-1", "4-1.1"):
        sys_usb.nos[nome].pop("bos")
        for interface in sys_usb.nos[nome]["interfaces"].values():
            interface["portas"] = {}
    sys_usb.montar()
    assert len(hubs_fisicos(_censo(sys_usb))) == 4


def test_o_enlace_abaixo_so_no_que_publica_superspeed(sys_usb: SysDeMentira) -> None:
    censo = _censo(sys_usb)
    marcados = {Path(a.no).name: e for a in censo.aparelhos if (e := enlace_abaixo(censo, a))}
    assert set(marcados) == {"3-1.4"}, marcados
    assert marcados["3-1.4"].velocidade_mbps == 480.0
    assert marcados["3-1.4"].caminho_era_3x, "o par SuperSpeed da porta acima está livre"


def test_com_o_par_superspeed_ocupado_o_caminho_nao_se_afirma(sys_usb: SysDeMentira) -> None:
    sys_usb.por("4-1.4", {
        "pai": "4-1", "attrs": {"idVendor": "f0e6", "idProduct": "0001", "bDeviceClass": "08",
                                "busnum": "4", "devpath": "4", "speed": "5000", "version": "3.20"}})
    censo = _censo(sys_usb)
    enlace = enlace_abaixo(censo, _por_nome(censo)["3-1.4"])
    assert enlace is not None and not enlace.caminho_era_3x


def test_o_nome_vem_do_descritor_e_da_base_cada_um_com_a_origem(sys_usb: SysDeMentira) -> None:
    nomes = _por_nome(_censo(sys_usb))
    wifi = nomes["3-1.4"]
    assert (wifi.fabricante, wifi.produto) == ("Realcom", "Placa de rede sem fio")
    assert (wifi.fabricante_da_base, wifi.produto_da_base) == (
        "Rádios de Mentira", "Placa Sem Fio Modelo X")
    assert wifi.driver == "sem_fio_de_mentira"
    receptor = nomes["3-1.1.2"]
    assert receptor.produto == "2.4G Wireless Receiver"
    assert (receptor.fabricante_da_base, receptor.produto_da_base) == ("", "")
    assert nomes["3-1.1.3"].driver == "btusb", "o driver repetido nas interfaces aparece uma vez"


def test_a_versao_e_o_devnum_vem_do_sys(sys_usb: SysDeMentira) -> None:
    nomes = _por_nome(_censo(sys_usb))
    assert (nomes["3-1.4"].versao_usb, nomes["3-1.4"].devnum) == ("2.10", 9)
    assert (nomes["4-1"].versao_usb, nomes["4-1"].devnum) == ("3.20", 2)


def test_o_tipo_nao_sai_do_nome(sys_usb: SysDeMentira) -> None:
    antes = {n: a.especie for n, a in _por_nome(_censo(sys_usb)).items()}
    for no in sys_usb.nos.values():
        no["attrs"].pop("manufacturer", None)
        no["attrs"].pop("product", None)
    sys_usb.dados["base"] = {}
    sys_usb.montar()
    depois = {n: a.especie for n, a in _por_nome(_censo(sys_usb)).items()}
    assert depois == antes
    assert {antes["3-1.4"], antes["3-1.1.3"], antes["3-1"]} == {"Wi-Fi", "Bluetooth", "Hub"}


def test_sem_bos_descriptors_e_nao_sei(sys_usb: SysDeMentira) -> None:
    nomes = _por_nome(_censo(sys_usb))
    assert nomes["3-1.1.2"].sabe_superspeed is None
    assert nomes["3-1.1.4"].sabe_superspeed is False, "BOS sem SuperSpeed é «não sabe»"
    assert nomes["3-1.4"].sabe_superspeed is True


@pytest.mark.parametrize("dados", [b"", b"\x05", b"\x05\x02\x0c\x00\x01"])
def test_sem_cabecalho_de_bos_e_nao_sei(dados: bytes) -> None:
    assert ler_o_bos(dados) == (None, "")


def test_a_capacidade_cortada_nao_se_le_alem_do_fim() -> None:
    assert ler_o_bos(b"\x05\x0f\x09\x00\x01\x02\x10") == (False, "")
