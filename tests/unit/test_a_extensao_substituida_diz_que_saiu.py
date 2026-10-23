"""A atualização que manda embora a extensão substituída diz «saiu a <nome>», na CLI e na aba.

A sprint é a A-LOVENSE-VIBRA-O-BRINQUEDO-PELO-ADAPTADOR-E-PELOS-BOTOES-01. O ``Resultado`` do
instalador traz os ids que o ``substitui`` mandou embora; quem instala lê o nome deles ANTES, porque
a substituída sai do registro. Extensões FALSAS, de tema e sem processo, num lar de mentira no
``tmp_path``: o mecanismo é de qualquer extensão, e nenhum nome de extensão real entra aqui.

MORDIDAS (22/10/2026, executadas sobre a cura e devolvidas):

- a frase arrancada do ``_dizer_o_resultado`` da CLI reprova ``test_a_cli_diz_que_saiu_ao_instalar``
  e ``test_a_cli_diz_que_saiu_ao_atualizar``;
- os nomes lidos DEPOIS de instalar (o registro sem a substituída) reprovam os dois pelo nome:
  a frase cai no id;
- a frase arrancada do recado da aba reprova ``test_a_aba_diz_que_saiu_ao_instalar`` e
  ``test_a_aba_diz_que_saiu_ao_atualizar``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli import cmd_mod
from hefesto_dualsense4unix.mods import instalador
from hefesto_dualsense4unix.mods.instalador import Lugares, ler_registro

INTERFACE = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix" / "interface"

ANTIGA, OUTRA_ANTIGA, NOVA = "ponte-velha", "ponte-gasta", "ponte-unica"
NOMES = {ANTIGA: "Ponte velha", OUTRA_ANTIGA: "Ponte gasta", NOVA: "Ponte única"}


def _pasta(raiz: Path, mod_id: str, *, versao: str = "1.0.0",
           substitui: tuple[str, ...] = ()) -> Path:
    """A pasta-fonte de uma extensão de tema de mentira (só declaração, nenhum processo)."""
    pasta = raiz / "fontes" / mod_id
    pasta.mkdir(parents=True, exist_ok=True)
    manifesto: dict[str, Any] = {
        "id": mod_id, "nome": NOMES[mod_id], "versao": versao,  # (noqa-acento): chave
        "api": ">=2,<3", "licenca": "MIT", "tipos": ["tema"], "tema": {},  # (noqa-acento): chave
        "permissoes": [], "descricao": "Muda um detalhe.", "opcoes": [],  # (noqa-acento): chave
    }
    if substitui:
        manifesto["substitui"] = list(substitui)
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    return pasta


@pytest.fixture
def lg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Lugares:
    """O lar de mentira, que a CLI e a aba acham pelo ``Lugares.do_xdg``."""
    lugares = Lugares(codigo=tmp_path / "codigo",  # (noqa-acento): argumento
                      dados=tmp_path / "dados",
                      registro=tmp_path / "config" / "mods.json",
                      estado=tmp_path / "run" / "mods-estado.json")
    monkeypatch.setattr(Lugares, "do_xdg", classmethod(lambda cls: lugares))
    return lugares


def _instalar(lg: Lugares, pasta: Path) -> None:
    instalador.instalar(str(pasta), lugares=lg)


# -- A frase ---------------------------------------------------------------------------------------


def test_a_frase_diz_o_nome_e_cai_no_id_quando_nao_o_sabe() -> None:
    assert cmd_mod.frase_das_substituidas([ANTIGA], NOMES) == "Saiu a «Ponte velha»."
    assert cmd_mod.frase_das_substituidas([ANTIGA, OUTRA_ANTIGA], NOMES) == (
        "Saíram a «Ponte velha» e a «Ponte gasta».")
    assert cmd_mod.frase_das_substituidas(["sumida"], {}) == "Saiu a «sumida»."
    assert cmd_mod.frase_das_substituidas([], NOMES) == ""


# -- A CLI -----------------------------------------------------------------------------------------


def test_a_cli_diz_que_saiu_ao_instalar(lg: Lugares, tmp_path: Path) -> None:
    _instalar(lg, _pasta(tmp_path, ANTIGA))
    saiu = CliRunner().invoke(cmd_mod.app, ["instalar", str(_pasta(tmp_path, NOVA,
                                                                   substitui=(ANTIGA,)))])
    assert saiu.exit_code == 0, saiu.output
    assert "Saiu a «Ponte velha»." in saiu.output
    assert ANTIGA not in ler_registro(lg.registro)


def test_a_cli_diz_que_saiu_ao_atualizar(lg: Lugares, tmp_path: Path) -> None:
    _instalar(lg, _pasta(tmp_path, ANTIGA))
    _instalar(lg, _pasta(tmp_path, OUTRA_ANTIGA))
    _instalar(lg, _pasta(tmp_path, NOVA))
    _pasta(tmp_path, NOVA, versao="1.1.0", substitui=(ANTIGA, OUTRA_ANTIGA))
    saiu = CliRunner().invoke(cmd_mod.app, ["atualizar", NOVA])
    assert saiu.exit_code == 0, saiu.output
    assert "Saíram a «Ponte velha» e a «Ponte gasta»." in saiu.output
    assert set(ler_registro(lg.registro)) == {NOVA}


def test_a_cli_nao_fala_de_saida_quando_nenhuma_saiu(lg: Lugares, tmp_path: Path) -> None:
    _instalar(lg, _pasta(tmp_path, ANTIGA))
    saiu = CliRunner().invoke(cmd_mod.app, ["instalar", str(_pasta(tmp_path, NOVA))])
    assert saiu.exit_code == 0, saiu.output
    assert "Saiu" not in saiu.output and "Saíram" not in saiu.output


# -- A aba -----------------------------------------------------------------------------------------


@pytest.fixture
def a07(lg: Lugares, monkeypatch: pytest.MonkeyPatch) -> Any:
    sys.path.insert(0, str(INTERFACE))
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores

    monkeypatch.setattr(a07_lancadores.VIGIA, "_disparar", lambda: None)
    a07_lancadores.REGISTRO.esquecer()
    a07_lancadores._MEXIDA.limpar()
    yield a07_lancadores
    a07_lancadores.REGISTRO.esquecer()
    a07_lancadores._MEXIDA.limpar()


def test_a_aba_diz_que_saiu_ao_instalar(a07: Any, lg: Lugares, tmp_path: Path) -> None:
    _instalar(lg, _pasta(tmp_path, ANTIGA))
    recado = a07._instalar_a_modificacao(str(_pasta(tmp_path, NOVA, substitui=(ANTIGA,))))
    assert recado == "Ponte única instalada. Saiu a Ponte velha. Ligue-a na chave quando quiser."


def test_a_aba_diz_que_saiu_ao_atualizar(a07: Any, lg: Lugares, tmp_path: Path) -> None:
    _instalar(lg, _pasta(tmp_path, ANTIGA))
    _instalar(lg, _pasta(tmp_path, NOVA))
    _pasta(tmp_path, NOVA, versao="1.1.0", substitui=(ANTIGA,))
    recado = a07._mexer_na_modificacao(NOVA, "atualizar")
    assert recado == "Ponte única atualizada para a versão 1.1.0. Saiu a Ponte velha."


def test_a_aba_nao_fala_de_saida_quando_nenhuma_saiu(a07: Any, lg: Lugares,
                                                       tmp_path: Path) -> None:
    recado = a07._instalar_a_modificacao(str(_pasta(tmp_path, NOVA)))
    assert recado == "Ponte única instalada. Ligue-a na chave quando quiser."
