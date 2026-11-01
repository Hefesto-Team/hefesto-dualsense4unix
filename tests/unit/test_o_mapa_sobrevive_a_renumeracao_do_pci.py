"""O mapa das conexões sobrevive à renumeração do barramento PCI da mesma placa."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.utils import lugar, maquina, xdg_paths

CHIPSET = "1022:43d5"
PROCESSADOR = "1022:149c"
INTEL = "8086:a36d"

ANTES = {"0000:02:00.0": CHIPSET, "0000:0c:00.3": PROCESSADOR}
DEPOIS = {"0000:01:00.0": CHIPSET, "0000:0b:00.3": PROCESSADOR}
DE_ANTES_PARA_DEPOIS = {"0000:02:00.0": "0000:01:00.0", "0000:0c:00.3": "0000:0b:00.3"}
PONTES = {"0000:02:00.0": "", "0000:02:01.0": ""}

FABRICANTE = "Fabricante R"
MODELO = "Placa R"


def _placa(fabricante: str = FABRICANTE, modelo: str = MODELO) -> dict[str, Any]:
    return {
        "fabricante": {"de_onde_sei": "lido-do-firmware", "valor": fabricante},
        "modelo": {"de_onde_sei": "lido-do-firmware", "valor": modelo},
    }


def _sys_de_mentira(
    raiz: Path,
    usb: dict[str, str],
    pontes: dict[str, str] | None = None,
    *,
    fabricante: str = FABRICANTE,
    modelo: str = MODELO,
) -> Path:
    dmi = raiz / "class" / "dmi" / "id"
    dmi.mkdir(parents=True)
    (dmi / "board_vendor").write_text(fabricante + "\n", encoding="utf-8")
    (dmi / "board_name").write_text(modelo + "\n", encoding="utf-8")
    devices = raiz / "bus" / "pci" / "devices"
    devices.mkdir(parents=True)
    for classe, enderecos in (("0x0c0330", usb), ("0x060400", pontes or {})):
        for endereco, vendor_device in enderecos.items():
            if endereco in usb and classe != "0x0c0330":
                continue
            pasta = devices / endereco
            pasta.mkdir()
            (pasta / "class").write_text(classe + "\n", encoding="utf-8")
            vendor, _, device = (vendor_device or "1022:1483").partition(":")
            (pasta / "vendor").write_text(f"0x{vendor}\n", encoding="utf-8")
            (pasta / "device").write_text(f"0x{device}\n", encoding="utf-8")
    return raiz


def _mapa(*controladores: str) -> dict[str, Any]:
    portas = {
        str(n): {"lugar": f"pci-{pci}-usb-0:{n}"}
        for n, pci in enumerate(controladores, start=1)
    }
    return {
        "faces": [{"nome": "Frente", "portas": sorted(portas, key=int)}],
        "portas": portas,
        "fora": [f"pci-{controladores[-1]}-usb-0:99"],
    }


def _mapa_reapontado(mapa: dict[str, Any], novos: dict[str, str]) -> dict[str, Any]:
    texto = json.dumps(mapa)
    for antes, depois in novos.items():
        texto = texto.replace(antes, depois)
    return dict(json.loads(texto))


def _secoes(*controladores: str) -> dict[str, Any]:
    return {
        "mapa": _mapa(*controladores),
        "mesa": {"altura_da_antena": "acima", "radios": {"0bda:8771": {"tipo": "wifi"}}},
        "adaptadores": {"aabbcc0000ff": {"nome": "Meio", "ordem": 0}},
    }


DA_PLACA = ("0000:02:00.0",) * 4 + ("0000:0c:00.3",) * 11


@pytest.fixture
def casa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pasta = tmp_path / "config"
    pasta.mkdir()

    def config_dir(ensure: bool = False) -> Path:
        return pasta

    monkeypatch.setattr(xdg_paths, "config_dir", config_dir)
    return pasta


def _nesta_maquina(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    usb: dict[str, str],
    pontes: dict[str, str] | None = None,
    **placa: str,
) -> None:
    raiz = _sys_de_mentira(tmp_path / f"sys-{len(list(tmp_path.iterdir()))}", usb, pontes, **placa)
    monkeypatch.setenv(maquina.RAIZ_DO_SYS_ENV, str(raiz))


def _gravar(casa: Path, documento: dict[str, Any], nome: str = "maquina.json") -> Path:
    arquivo = casa / nome
    arquivo.write_text(json.dumps(documento), encoding="utf-8")
    return arquivo


def _no_disco(casa: Path, nome: str = "maquina.json") -> dict[str, Any]:
    return dict(json.loads((casa / nome).read_text(encoding="utf-8")))


def _guardas(casa: Path) -> list[str]:
    return sorted(p.name for p in casa.iterdir() if p.name != "maquina.json")


def test_o_mapa_sem_placa_feito_antes_da_renumeracao_fica_e_os_lugares_andam(
    casa: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _gravar(casa, {"version": 1, **_secoes(*DA_PLACA), "controles": {"aabbcc0000fe": {}}})
    _nesta_maquina(tmp_path, monkeypatch, DEPOIS, PONTES)

    lida = maquina.carregar_maquina()

    assert len(lida.mapa.portas) == 15
    esperado = _mapa_reapontado(_mapa(*DA_PLACA), DE_ANTES_PARA_DEPOIS)
    assert {n: p.lugar for n, p in lida.mapa.portas.items()} == {
        n: p["lugar"] for n, p in esperado["portas"].items()
    }
    assert lida.mapa.fora == esperado["fora"]
    assert sorted(lida.adaptadores) == ["aabbcc0000ff"]
    assert _guardas(casa) == []
    disco = _no_disco(casa)
    assert disco["mapa"] == esperado
    assert disco["placa"] == _placa()
    assert disco[maquina.CONTROLADORES_USB_FIELD] == DEPOIS


def test_com_a_placa_gravada_igual_a_renumeracao_so_anda_os_lugares(
    casa: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _gravar(casa, {"version": 1, **_secoes(*DA_PLACA), "placa": _placa(),
                   maquina.CONTROLADORES_USB_FIELD: ANTES})
    _nesta_maquina(tmp_path, monkeypatch, DEPOIS, PONTES)

    lida = maquina.carregar_maquina()

    assert len(lida.mapa.portas) == 15
    assert {p.lugar.split("-usb")[0] for p in lida.mapa.portas.values() if p.lugar} == {
        "pci-0000:01:00.0", "pci-0000:0b:00.3"
    }
    assert _guardas(casa) == []
    disco = _no_disco(casa)
    assert disco["mapa"] == _mapa_reapontado(_mapa(*DA_PLACA), DE_ANTES_PARA_DEPOIS)
    assert disco[maquina.CONTROLADORES_USB_FIELD] == DEPOIS


def test_a_ordem_entre_os_iguais_reconhece_quem_tomou_o_endereco_do_outro(
    casa: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    antes = {"0000:0c:00.3": PROCESSADOR, "0000:0d:00.3": PROCESSADOR}
    depois = {"0000:0b:00.3": PROCESSADOR, "0000:0c:00.3": PROCESSADOR}
    _gravar(casa, {"version": 1, **_secoes("0000:0c:00.3", "0000:0d:00.3"), "placa": _placa(),
                   maquina.CONTROLADORES_USB_FIELD: antes})
    _nesta_maquina(tmp_path, monkeypatch, depois)

    lida = maquina.carregar_maquina()

    assert lida.mapa.portas["1"].lugar == "pci-0000:0b:00.3-usb-0:1"
    assert lida.mapa.portas["2"].lugar == "pci-0000:0c:00.3-usb-0:2"


def test_a_segunda_leitura_depois_da_renumeracao_nao_regrava(
    casa: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    arquivo = _gravar(casa, {"version": 1, **_secoes(*DA_PLACA)})
    _nesta_maquina(tmp_path, monkeypatch, DEPOIS, PONTES)
    maquina.carregar_maquina()
    antes = arquivo.read_bytes(), os.stat(arquivo).st_ino, os.stat(arquivo).st_mtime_ns

    maquina.carregar_maquina()
    maquina.carregar_maquina()

    assert (arquivo.read_bytes(), os.stat(arquivo).st_ino, os.stat(arquivo).st_mtime_ns) == antes


@pytest.mark.parametrize(
    ("usb", "gravados"),
    [
        ({"0000:01:00.0": INTEL, "0000:0b:00.3": INTEL}, ANTES),
        ({"0000:00:14.0": INTEL}, None),
        ({"0000:01:00.0": CHIPSET}, None),
    ],
    ids=["mesma-forma-outra-familia", "outra-forma-sem-registro", "falta-um-controlador"],
)
def test_os_controladores_de_outra_familia_tiram_o_mapa(
    casa: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    usb: dict[str, str],
    gravados: dict[str, str] | None,
) -> None:
    documento: dict[str, Any] = {"version": 1, **_secoes(*DA_PLACA)}
    if gravados is not None:
        documento[maquina.CONTROLADORES_USB_FIELD] = gravados
    _gravar(casa, documento)
    _nesta_maquina(tmp_path, monkeypatch, usb, PONTES)

    lida = maquina.carregar_maquina()

    assert lida.mapa == maquina.MapaDaMesa()
    assert lida.adaptadores == {}
    assert _guardas(casa) == ["maquina.json.de-outra-placa"]
    guardado = _no_disco(casa, "maquina.json.de-outra-placa")
    assert guardado["mapa"] == _mapa(*DA_PLACA)
    assert guardado.get(maquina.CONTROLADORES_USB_FIELD) == gravados
    assert maquina.CONTROLADORES_USB_FIELD not in _no_disco(casa)


def _guarda_da_renumeracao(casa: Path, **extra: Any) -> Path:
    return _gravar(
        casa, {"version": 1, **_secoes(*DA_PLACA), **extra}, "maquina.json.de-outra-placa"
    )


def test_a_guarda_feita_pela_renumeracao_volta_uma_vez_so(
    casa: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    azul = {"aabbcc0000fe": {"nome": "Azul"}}
    _gravar(casa, {"version": 1, "placa": _placa(), "controles": azul})
    guarda = _guarda_da_renumeracao(casa)
    bytes_da_guarda = guarda.read_bytes()
    _nesta_maquina(tmp_path, monkeypatch, DEPOIS, PONTES)

    lida = maquina.carregar_maquina()

    assert len(lida.mapa.portas) == 15
    assert lida.mapa.portas["1"].lugar == "pci-0000:01:00.0-usb-0:1"
    assert lida.mapa.portas["15"].lugar == "pci-0000:0b:00.3-usb-0:15"
    assert sorted(lida.mesa.radios) == ["0bda:8771"]
    assert sorted(lida.adaptadores) == ["aabbcc0000ff"]
    assert lida.controles["aabbcc0000fe"].nome == "Azul"
    assert _guardas(casa) == ["maquina.json.de-outra-placa.devolvida"]
    assert (casa / "maquina.json.de-outra-placa.devolvida").read_bytes() == bytes_da_guarda
    disco = _no_disco(casa)
    assert disco["mapa"] == _mapa_reapontado(_mapa(*DA_PLACA), DE_ANTES_PARA_DEPOIS)
    assert disco[maquina.CONTROLADORES_USB_FIELD] == DEPOIS

    assert maquina.gravar_maquina_com_descartes({"mapa": {}}, substituir=("mapa",)).gravou
    for _ in range(2):
        assert maquina.carregar_maquina().mapa == maquina.MapaDaMesa()
    assert _guardas(casa) == ["maquina.json.de-outra-placa.devolvida"]


def test_a_gravacao_tambem_devolve_a_guarda_da_renumeracao(
    casa: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _gravar(casa, {"version": 1, "placa": _placa()})
    _guarda_da_renumeracao(casa)
    _nesta_maquina(tmp_path, monkeypatch, DEPOIS, PONTES)

    assert maquina.gravar_maquina({"controles": {"aabbcc0000fe": {"nome": "Azul"}}})

    disco = _no_disco(casa)
    assert len(disco["mapa"]["portas"]) == 15
    assert disco["controles"]["aabbcc0000fe"]["nome"] == "Azul"
    assert _guardas(casa) == ["maquina.json.de-outra-placa.devolvida"]


@pytest.mark.parametrize(
    ("usb", "extra"),
    [
        (DEPOIS, {"placa": _placa("Fabricante A", "Placa A")}),
        ({"0000:01:00.0": CHIPSET}, {}),
        ({"0000:01:00.0": INTEL, "0000:0b:00.3": INTEL}, {maquina.CONTROLADORES_USB_FIELD: ANTES}),
        (DEPOIS, {"version": 2}),
    ],
    ids=["troca-de-placa", "um-controlador-falta", "outra-familia", "outra-versao"],
)
def test_a_guarda_da_troca_de_computador_nao_volta(
    casa: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    usb: dict[str, str],
    extra: dict[str, Any],
) -> None:
    arquivo = _gravar(casa, {"version": 1, "placa": _placa()})
    bytes_antes = arquivo.read_bytes()
    _guarda_da_renumeracao(casa, **extra)
    _nesta_maquina(tmp_path, monkeypatch, usb, PONTES)

    assert maquina.carregar_maquina().mapa == maquina.MapaDaMesa()

    assert arquivo.read_bytes() == bytes_antes
    assert _guardas(casa) == ["maquina.json.de-outra-placa"]


def test_das_guardas_da_renumeracao_a_mais_nova_volta_primeiro(
    casa: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _gravar(casa, {"version": 1, "placa": _placa()})
    _guarda_da_renumeracao(casa)
    _gravar(casa, {"version": 1, **_secoes("0000:02:00.0", "0000:0c:00.3")},
            "maquina.json.de-outra-placa-2")
    _nesta_maquina(tmp_path, monkeypatch, DEPOIS, PONTES)

    lida = maquina.carregar_maquina()

    assert {n: p.lugar for n, p in lida.mapa.portas.items()} == {
        "1": "pci-0000:01:00.0-usb-0:1", "2": "pci-0000:0b:00.3-usb-0:2"
    }
    assert "maquina.json.de-outra-placa-2.devolvida" in _guardas(casa)


def test_a_guarda_nao_passa_por_cima_do_mapa_feito_depois(
    casa: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    novo = {"portas": {"1": {"lugar": "pci-0000:01:00.0-usb-0:7"}}}
    _gravar(casa, {"version": 1, "placa": _placa(), "mapa": novo})
    _guarda_da_renumeracao(casa)
    _nesta_maquina(tmp_path, monkeypatch, DEPOIS, PONTES)

    lida = maquina.carregar_maquina()

    assert sorted(lida.mapa.portas) == ["1"]
    assert lida.mapa.portas["1"].lugar == "pci-0000:01:00.0-usb-0:7"
    assert sorted(lida.mesa.radios) == ["0bda:8771"]
    assert sorted(lida.adaptadores) == ["aabbcc0000ff"]
    assert _guardas(casa) == ["maquina.json.de-outra-placa.devolvida"]


def test_sem_placa_legivel_a_guarda_fica_onde_esta(
    casa: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _gravar(casa, {"version": 1, "placa": _placa()})
    _guarda_da_renumeracao(casa)

    assert maquina.carregar_maquina().mapa == maquina.MapaDaMesa()

    assert _guardas(casa) == ["maquina.json.de-outra-placa"]


@pytest.mark.parametrize(
    ("gravados", "vivos", "identidades", "esperado"),
    [
        (ANTES, DEPOIS, None, DE_ANTES_PARA_DEPOIS),
        (ANTES, DEPOIS, ANTES, DE_ANTES_PARA_DEPOIS),
        (DEPOIS, DEPOIS, None, {k: k for k in DEPOIS}),
        (ANTES, {"0000:01:00.0": CHIPSET, "0000:05:00.0": CHIPSET, "0000:0b:00.3": PROCESSADOR},
         None, None),
        (ANTES, {"0000:01:00.0": INTEL, "0000:0b:00.3": PROCESSADOR}, ANTES, None),
        ({"0000:02:00.0": CHIPSET}, {"0000:01:00.0": CHIPSET, "0000:0b:00.3": PROCESSADOR},
         ANTES, {"0000:02:00.0": "0000:01:00.0"}),
        (ANTES, {"0000:00:14.0": INTEL}, None, None),
        ({"0000:02:00.0": CHIPSET, "0000:03:00.0": CHIPSET}, {"0000:01:00.0": CHIPSET},
         {"0000:02:00.0": CHIPSET}, None),
    ],
    ids=["sem-registro", "com-registro", "sem-renumeracao", "iguais-a-mais", "familia-trocada",
         "um-do-registro", "outra-forma", "dois-no-mesmo-vivo"],
)
def test_o_reconhecimento_do_controlador(
    gravados: dict[str, str],
    vivos: dict[str, str],
    identidades: dict[str, str] | None,
    esperado: dict[str, str] | None,
) -> None:
    assert lugar.reconhecer_os_controladores(gravados, vivos, identidades) == esperado


def test_o_lugar_anda_para_o_endereco_vivo_e_o_resto_fica() -> None:
    assert lugar.lugar_reapontado("pci-0000:02:00.0-usb-0:4.1", DE_ANTES_PARA_DEPOIS) == (
        "pci-0000:01:00.0-usb-0:4.1"
    )
    assert lugar.lugar_reapontado("pci-0000:03:00.0-usb-0:4", DE_ANTES_PARA_DEPOIS) == (
        "pci-0000:03:00.0-usb-0:4"
    )
    assert lugar.lugar_reapontado("não é lugar", DE_ANTES_PARA_DEPOIS) == "não é lugar"
