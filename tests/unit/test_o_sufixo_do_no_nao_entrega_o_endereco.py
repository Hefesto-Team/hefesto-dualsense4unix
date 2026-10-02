"""O-SUFIXO-DO-NO-NAO-ENTREGA-O-ENDERECO-01 — as duas réguas que veem o pedaço."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

RAIZ = Path(__file__).resolve().parents[2]

_OCTETOS = ("06", "de", "ad", "4c", "5d", "6e")


def _carregar(rel: str, nome: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(nome, RAIZ / rel)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


FORMA = _carregar("scripts/check_endereco_de_radio.py", "_regua_de_forma")
DONO = _carregar("scripts/check_o_endereco_dela_em_toda_forma.py", "_regua_do_dono")


def _no(prefixo: str, octetos: tuple[str, ...]) -> str:
    return prefixo + "".join(octetos[3:])


def test_a_regua_de_forma_acusa_o_no_sem_mascara() -> None:
    assert FORMA.acusa_no(_no("hefesto_som_", _OCTETOS)) != []
    assert FORMA.acusa_no(_no("hefesto_mic_", _OCTETOS)) != []
    assert FORMA.acusa_no("alsa_output.usb-Sony_" + _no("HEFESTO", _OCTETOS) + "-00") != []


def test_a_regua_de_forma_aceita_o_no_mascarado() -> None:
    mascarado = ("06", "de", "ad", "00", "00", "6e")
    assert FORMA.acusa_no(_no("hefesto_som_", mascarado)) == []
    assert FORMA.acusa_no(_no("HEFESTO", mascarado)) == []


def test_as_janelas_sao_as_que_carregam_o_quarto_ou_o_quinto() -> None:
    assert [inicio for inicio, _ in DONO.janelas(_OCTETOS)] == [1, 2, 3]
    assert DONO.janelas(("06", "de", "ad", "00", "00", "6e")) == []


def test_o_dono_acha_a_janela_com_separador() -> None:
    padroes = DONO.padrao_das_janelas({_OCTETOS})
    ((rotulo, padrao),) = padroes.items()
    assert rotulo.endswith(_OCTETOS[5])
    fixture = ":".join(("aa", "bb", "cc", *_OCTETOS[3:]))
    assert padrao.search(fixture)
    assert padrao.search("-".join(_OCTETOS[2:5]).upper())


def test_o_dono_acha_a_janela_dentro_do_endereco_colado() -> None:
    coladas = DONO.janelas_coladas({_OCTETOS})
    assert DONO.achados_colados("uniq=" + "".join(_OCTETOS), coladas)
    assert DONO.achados_colados(_no("hefesto_som_", _OCTETOS), coladas)
    assert DONO.achados_colados("f" + "".join(_OCTETOS[3:]) + "f", coladas) == []


def test_o_dono_varre_e_nomeia_sem_imprimir_o_valor(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    arquivo = tmp_path / "fixture.txt"
    arquivo.write_text("x\nno=" + _no("hefesto_mic_", _OCTETOS) + "\n", encoding="utf-8")
    monkeypatch.setattr(DONO, "RAIZ", tmp_path)
    achados = DONO.varrer(
        [arquivo], DONO.padrao_das_janelas({_OCTETOS}), DONO.janelas_coladas({_OCTETOS})
    )
    assert len(achados) == 1
    assert achados[0].startswith("fixture.txt:2:")
    assert "".join(_OCTETOS[3:5]) not in achados[0]
