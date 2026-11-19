"""A guarda da renumeração não devolve a seção que o documento completo esvaziou depois."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.utils import maquina, xdg_paths

CHIPSET = "1022:43d5"
PROCESSADOR = "1022:149c"
INTEL = "8086:a36d"
DEPOIS = {"0000:01:00.0": CHIPSET, "0000:0b:00.3": PROCESSADOR}
DA_PLACA = ("0000:02:00.0",) * 4 + ("0000:0c:00.3",) * 11

QUATRO = {
    "aabbcc000001": {"nome": "Azul"},
    "aabbcc000002": {"nome": "Rosa"},
    "aabbcc000003": {"nome": "Verde"},
    "aabbcc000004": {"nome": "Roxo"},
}


def _placa() -> dict[str, Any]:
    return {
        "fabricante": {"de_onde_sei": "lido-do-firmware", "valor": "Fabricante R"},
        "modelo": {"de_onde_sei": "lido-do-firmware", "valor": "Placa R"},
    }


def _sys_de_mentira(raiz: Path, usb: dict[str, str]) -> Path:
    dmi = raiz / "class" / "dmi" / "id"
    dmi.mkdir(parents=True)
    (dmi / "board_vendor").write_text("Fabricante R\n", encoding="utf-8")
    (dmi / "board_name").write_text("Placa R\n", encoding="utf-8")
    for endereco, vendor_device in usb.items():
        pasta = raiz / "bus" / "pci" / "devices" / endereco
        pasta.mkdir(parents=True)
        (pasta / "class").write_text("0x0c0330\n", encoding="utf-8")
        vendor, _, device = vendor_device.partition(":")
        (pasta / "vendor").write_text(f"0x{vendor}\n", encoding="utf-8")
        (pasta / "device").write_text(f"0x{device}\n", encoding="utf-8")
    return raiz


def _secoes(*controladores: str, nome: str) -> dict[str, Any]:
    portas = {
        str(n): {"lugar": f"pci-{pci}-usb-0:{n}"} for n, pci in enumerate(controladores, start=1)
    }
    return {
        "mapa": {"faces": [{"nome": nome, "portas": sorted(portas, key=int)}], "portas": portas},
        "mesa": {"altura_da_antena": "acima", "radios": {"0bda:8771": {"tipo": "wifi"}}},
        "adaptadores": {"aabbcc0000ff": {"nome": nome, "ordem": 0}},
    }


@pytest.fixture
def casa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pasta = tmp_path / "config"
    pasta.mkdir()
    monkeypatch.setattr(xdg_paths, "config_dir", lambda ensure=False: pasta)
    return pasta


def _nesta_maquina(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, usb: dict[str, str]) -> None:
    monkeypatch.setenv(maquina.RAIZ_DO_SYS_ENV, str(_sys_de_mentira(tmp_path / "sys", usb)))


def _gravar(casa: Path, documento: dict[str, Any], nome: str = "maquina.json") -> None:
    (casa / nome).write_text(json.dumps(documento), encoding="utf-8")


def _no_disco(casa: Path) -> dict[str, Any]:
    return dict(json.loads((casa / "maquina.json").read_text(encoding="utf-8")))


def _guardas(casa: Path) -> list[str]:
    return sorted(p.name for p in casa.iterdir() if p.name != "maquina.json")


@pytest.mark.parametrize("secao", maquina.SECOES_DESTE_COMPUTADOR)
def test_a_secao_esvaziada_segue_vazia_com_a_guarda_viva(
    casa: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, secao: str
) -> None:
    """D-1911-A-GUARDA-VELHA-NAO-RESSUSCITA-O-MAPA: a seção esvaziada segue vazia."""
    feito_depois = _secoes("0000:01:00.0", "0000:0b:00.3", nome="Nova")
    _gravar(casa, {"version": 1, "placa": _placa(), **feito_depois, "controles": QUATRO})
    _gravar(casa, {"version": 1, **_secoes(*DA_PLACA, nome="Velha")}, "maquina.json.de-outra-placa")
    _nesta_maquina(tmp_path, monkeypatch, DEPOIS)

    lida = maquina.carregar_maquina()
    assert lida.mapa.faces[0].nome == "Nova"
    vizinhas = {
        vizinha: lida.model_dump(mode="json")[vizinha]
        for vizinha in set(maquina.SECOES_DESTE_COMPUTADOR) - {secao}
    }

    assert maquina.gravar_maquina_com_descartes({secao: {}}, substituir=(secao,)).gravou
    for _ in range(2):
        relida = maquina.carregar_maquina().model_dump(mode="json")
        disco = _no_disco(casa)
        assert not disco.get(secao)
        assert {vizinha: relida[vizinha] for vizinha in vizinhas} == vizinhas
        assert {k: v["nome"] for k, v in disco["controles"].items()} == {
            k: v["nome"] for k, v in QUATRO.items()
        }
    assert _guardas(casa) == ["maquina.json.de-outra-placa.aposentada"]


def test_a_guarda_que_nao_se_reconhece_aqui_fica(
    casa: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _gravar(casa, {"version": 1, "placa": _placa(),
                   **_secoes("0000:01:00.0", nome="Nova"), "controles": QUATRO})
    antes = {"0000:02:00.0": CHIPSET, "0000:0c:00.3": PROCESSADOR}
    _gravar(casa, {"version": 1, **_secoes(*DA_PLACA, nome="Velha"),
                   maquina.CONTROLADORES_USB_FIELD: antes}, "maquina.json.de-outra-placa")
    _nesta_maquina(tmp_path, monkeypatch, {"0000:01:00.0": INTEL, "0000:0b:00.3": INTEL})

    assert maquina.carregar_maquina().mapa.faces[0].nome == "Nova"
    assert maquina.gravar_maquina_com_descartes({"mapa": {}}, substituir=("mapa",)).gravou

    assert _guardas(casa) == ["maquina.json.de-outra-placa"]
