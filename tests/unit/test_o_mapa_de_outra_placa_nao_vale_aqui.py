"""O mapa das conexões, a mesa e os adaptadores valem só na placa-mãe em que nasceram."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.utils import maquina, xdg_paths

CONTROLADOR_VIVO = "0000:01:00.0"
PONTE_PCI = "0000:02:00.0"
CONTROLADOR_QUE_NAO_EXISTE = "0000:0c:00.3"


def _sys_de_mentira(
    raiz: Path,
    *,
    fabricante: str | None,
    modelo: str | None,
    pci: dict[str, str] | None,
) -> Path:
    dmi = raiz / "class" / "dmi" / "id"
    dmi.mkdir(parents=True)
    if fabricante is not None:
        (dmi / "board_vendor").write_text(fabricante + "\n", encoding="utf-8")
    if modelo is not None:
        (dmi / "board_name").write_text(modelo + "\n", encoding="utf-8")
    if pci is not None:
        devices = raiz / "bus" / "pci" / "devices"
        devices.mkdir(parents=True)
        for endereco, classe in pci.items():
            (devices / endereco).mkdir()
            (devices / endereco / "class").write_text(classe + "\n", encoding="utf-8")
    return raiz


def _placa(fabricante: str, modelo: str) -> dict[str, Any]:
    return {
        "fabricante": {"de_onde_sei": "lido-do-firmware", "valor": fabricante},
        "modelo": {"de_onde_sei": "lido-do-firmware", "valor": modelo},
    }


def _documento(*pcis: str, placa: dict[str, Any] | None = None) -> dict[str, Any]:
    documento: dict[str, Any] = {
        "version": 1,
        "mapa": {
            "faces": [{"nome": "Frente", "portas": [str(n) for n in range(1, len(pcis) + 1)]}],
            "portas": {
                str(n): {"lugar": f"pci-{pci}-usb-0:4.{n}"}
                for n, pci in enumerate(pcis, start=1)
            },
        },
        "mesa": {"altura_da_antena": "acima", "radios": {"0bda:8771": {"tipo": "wifi"}}},
        "adaptadores": {"aabbcc0000ff": {"nome": "Meio", "ordem": 0}},
        "controles": {"aabbcc0000fe": {"nome": "Azul"}},
    }
    if placa is not None:
        documento["placa"] = placa
    return documento


@pytest.fixture
def casa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pasta = tmp_path / "config"
    pasta.mkdir()

    def config_dir(ensure: bool = False) -> Path:
        return pasta

    monkeypatch.setattr(xdg_paths, "config_dir", config_dir)
    return pasta


def _nesta_placa(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    fabricante: str | None = "Fabricante B",
    modelo: str | None = "Placa B",
    pci: dict[str, str] | None = None,
) -> None:
    if pci is None:
        pci = {CONTROLADOR_VIVO: "0x0c0330", PONTE_PCI: "0x060400"}
    raiz = _sys_de_mentira(
        tmp_path / f"sys-{fabricante}-{modelo}", fabricante=fabricante, modelo=modelo, pci=pci
    )
    monkeypatch.setenv(maquina.RAIZ_DO_SYS_ENV, str(raiz))


def _gravar(casa: Path, documento: dict[str, Any]) -> Path:
    arquivo = casa / "maquina.json"
    arquivo.write_text(json.dumps(documento), encoding="utf-8")
    return arquivo


def _no_disco(casa: Path) -> dict[str, Any]:
    return dict(json.loads((casa / "maquina.json").read_text(encoding="utf-8")))


def _de_outra_placa(casa: Path) -> list[str]:
    return sorted(p.name for p in casa.iterdir() if ".de-outra-placa" in p.name)


def test_a_suite_nao_le_a_placa_da_maquina_que_a_roda() -> None:
    assert os.environ[maquina.RAIZ_DO_SYS_ENV].startswith("/dev/null/")
    assert maquina.placa_daqui() is None
    assert maquina.controladores_usb_daqui() is None


def test_o_mapa_da_placa_a_lido_na_placa_b_sai_inteiro_para_o_lado(
    casa: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _gravar(casa, _documento(CONTROLADOR_VIVO, placa=_placa("Fabricante A", "Placa A")))
    _nesta_placa(tmp_path, monkeypatch)

    lida = maquina.carregar_maquina()

    assert lida.mapa == maquina.MapaDaMesa()
    assert lida.mesa == maquina.MesaDeclarada()
    assert lida.adaptadores == {}
    assert lida.controles["aabbcc0000fe"].nome == "Azul"
    assert _de_outra_placa(casa) == ["maquina.json.de-outra-placa"]
    guardado = json.loads((casa / "maquina.json.de-outra-placa").read_text(encoding="utf-8"))
    original = _documento(CONTROLADOR_VIVO)
    assert {k: guardado[k] for k in ("mapa", "mesa", "adaptadores")} == {
        k: original[k] for k in ("mapa", "mesa", "adaptadores")
    }
    assert guardado["placa"] == _placa("Fabricante A", "Placa A")
    disco = _no_disco(casa)
    assert not set(disco) & set(maquina.SECOES_DESTE_COMPUTADOR)
    assert disco["placa"] == _placa("Fabricante B", "Placa B")
    assert disco["version"] == 1
    assert "aabbcc0000fe" in disco["controles"]


def test_a_segunda_leitura_nao_regrava(
    casa: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    arquivo = _gravar(casa, _documento(CONTROLADOR_VIVO, placa=_placa("Fabricante A", "Placa A")))
    _nesta_placa(tmp_path, monkeypatch)
    maquina.carregar_maquina()
    antes = arquivo.read_bytes(), os.stat(arquivo).st_ino, os.stat(arquivo).st_mtime_ns

    maquina.carregar_maquina()
    maquina.carregar_maquina()

    assert (arquivo.read_bytes(), os.stat(arquivo).st_ino, os.stat(arquivo).st_mtime_ns) == antes
    assert _de_outra_placa(casa) == ["maquina.json.de-outra-placa"]


def test_o_documento_sem_placa_com_um_controlador_daqui_ganha_a_placa_e_fica(
    casa: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _gravar(casa, _documento(CONTROLADOR_VIVO, PONTE_PCI))
    _nesta_placa(tmp_path, monkeypatch)

    lida = maquina.carregar_maquina()

    assert sorted(lida.mapa.portas) == ["1", "2"]
    assert sorted(lida.mesa.radios) == ["0bda:8771"]
    assert sorted(lida.adaptadores) == ["aabbcc0000ff"]
    assert _de_outra_placa(casa) == []
    disco = _no_disco(casa)
    assert disco["placa"] == _placa("Fabricante B", "Placa B")
    assert disco["mapa"] == _documento(CONTROLADOR_VIVO, PONTE_PCI)["mapa"]


def test_o_documento_sem_placa_cujo_mapa_nao_cai_em_controlador_usb_daqui_sai(
    casa: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _gravar(casa, _documento(PONTE_PCI, CONTROLADOR_QUE_NAO_EXISTE))
    _nesta_placa(tmp_path, monkeypatch)

    lida = maquina.carregar_maquina()

    assert lida.mapa == maquina.MapaDaMesa()
    assert lida.mesa == maquina.MesaDeclarada()
    assert lida.adaptadores == {}
    assert _de_outra_placa(casa) == ["maquina.json.de-outra-placa"]
    guardado = json.loads((casa / "maquina.json.de-outra-placa").read_text(encoding="utf-8"))
    assert guardado["mapa"] == _documento(PONTE_PCI, CONTROLADOR_QUE_NAO_EXISTE)["mapa"]
    assert "placa" not in guardado
    assert _no_disco(casa)["placa"] == _placa("Fabricante B", "Placa B")


@pytest.mark.parametrize(
    ("fabricante", "modelo", "pci"),
    [
        (None, None, {"0000:00:14.0": "0x0c0330"}),
        ("Fabricante B", None, {"0000:00:14.0": "0x0c0330"}),
        ("Default string", "Default string", {"0000:00:14.0": "0x0c0330"}),
        ("Fabricante B", "Placa B", {}),
    ],
    ids=["sem-dmi", "sem-modelo", "gabarito-do-firmware", "sem-pci"],
)
def test_a_placa_ou_o_pci_que_nao_se_leem_nao_carimbam_nem_esvaziam(
    casa: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fabricante: str | None,
    modelo: str | None,
    pci: dict[str, str],
) -> None:
    for documento in (
        _documento(PONTE_PCI, CONTROLADOR_QUE_NAO_EXISTE),
        _documento(PONTE_PCI, placa=_placa("Fabricante A", "Placa A")),
    ):
        arquivo = _gravar(casa, documento)
        bytes_antes = arquivo.read_bytes()
        raiz = _sys_de_mentira(
            tmp_path / f"sys-{id(documento)}", fabricante=fabricante, modelo=modelo, pci=pci
        )
        monkeypatch.setenv(maquina.RAIZ_DO_SYS_ENV, str(raiz))
        if pci == {}:
            if "placa" in documento:
                continue
            assert maquina.controladores_usb_daqui() is None
        else:
            assert maquina.placa_daqui() is None

        lida = maquina.carregar_maquina()

        assert sorted(lida.mapa.portas) == sorted(documento["mapa"]["portas"])
        assert sorted(lida.adaptadores) == ["aabbcc0000ff"]
        assert arquivo.read_bytes() == bytes_antes
        assert _de_outra_placa(casa) == []


def test_a_primeira_gravacao_do_mapa_carimba_a_placa(
    casa: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _nesta_placa(tmp_path, monkeypatch)
    assert maquina.gravar_maquina({"controles": {"aabbcc0000fe": {"nome": "Azul"}}})
    assert "placa" not in _no_disco(casa)

    assert maquina.gravar_maquina(
        {"mapa": {"portas": {"1": {"lugar": f"pci-{CONTROLADOR_VIVO}-usb-0:4.1"}}}}
    )

    assert _no_disco(casa)["placa"] == _placa("Fabricante B", "Placa B")
    assert sorted(maquina.carregar_maquina().mapa.portas) == ["1"]


def test_a_gravacao_sobre_o_documento_de_outra_placa_tira_o_de_la_antes_de_fundir(
    casa: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _gravar(casa, _documento(CONTROLADOR_VIVO, placa=_placa("Fabricante A", "Placa A")))
    _nesta_placa(tmp_path, monkeypatch)

    assert maquina.gravar_maquina({"mesa": {"linha_de_visada": "livre"}})

    disco = _no_disco(casa)
    assert disco["placa"] == _placa("Fabricante B", "Placa B")
    assert disco["mesa"] == {"linha_de_visada": "livre"}
    assert "mapa" not in disco
    assert "adaptadores" not in disco
    assert _de_outra_placa(casa) == ["maquina.json.de-outra-placa"]


def test_o_de_outra_placa_nunca_se_sobrescreve(
    casa: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _nesta_placa(tmp_path, monkeypatch)
    _gravar(casa, _documento(CONTROLADOR_VIVO, placa=_placa("Fabricante A", "Placa A")))
    maquina.carregar_maquina()
    _gravar(casa, _documento(PONTE_PCI, placa=_placa("Fabricante C", "Placa C")))
    maquina.carregar_maquina()

    assert _de_outra_placa(casa) == ["maquina.json.de-outra-placa", "maquina.json.de-outra-placa-2"]
    primeiro = json.loads((casa / "maquina.json.de-outra-placa").read_text(encoding="utf-8"))
    segundo = json.loads((casa / "maquina.json.de-outra-placa-2").read_text(encoding="utf-8"))
    assert primeiro["placa"] == _placa("Fabricante A", "Placa A")
    assert segundo["placa"] == _placa("Fabricante C", "Placa C")


def test_a_placa_nao_sobe_a_versao_e_o_schema_a_ignora(
    casa: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _gravar(casa, _documento(CONTROLADOR_VIVO))
    _nesta_placa(tmp_path, monkeypatch)
    maquina.carregar_maquina()

    disco = _no_disco(casa)
    assert disco["version"] == maquina.MAQUINA_SCHEMA_VERSION == 1
    assert "placa" not in maquina.MaquinaConfig.model_fields
    assert maquina.MaquinaConfig.model_validate(maquina._so_o_que_o_schema_conhece(disco))


def test_a_leitura_que_nao_regrava_nao_multiplica_o_de_outra_placa(
    casa: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _gravar(casa, _documento(CONTROLADOR_VIVO, placa=_placa("Fabricante A", "Placa A")))
    _nesta_placa(tmp_path, monkeypatch)

    def _disco_cheio(documento: dict[str, Any]) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(maquina, "_escrever", _disco_cheio)

    for _ in range(3):
        assert maquina.carregar_maquina().mapa == maquina.MapaDaMesa()

    assert _de_outra_placa(casa) == ["maquina.json.de-outra-placa"]
    assert _no_disco(casa)["placa"] == _placa("Fabricante A", "Placa A")


def test_sem_o_desvio_a_placa_se_le_pela_raiz_do_dono_dela(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hefesto_dualsense4unix.integrations import censo_do_gabinete

    raiz = _sys_de_mentira(tmp_path / "sys-do-dono", fabricante="Fabricante D", modelo="Placa D",
                           pci=None)
    monkeypatch.delenv(maquina.RAIZ_DO_SYS_ENV)
    monkeypatch.setattr(maquina, "_PLACAS_LIDAS", {})
    monkeypatch.setattr(
        censo_do_gabinete.ler_a_placa,
        "__kwdefaults__",
        {**(censo_do_gabinete.ler_a_placa.__kwdefaults__ or {}),
         "raiz_dmi_id": str(raiz / "class" / "dmi" / "id")},
    )

    assert maquina.placa_daqui() == _placa("Fabricante D", "Placa D")
