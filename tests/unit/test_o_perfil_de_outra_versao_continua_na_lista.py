"""O perfil de outra versão continua na lista, e a prioridade tem faixa na gravação.

D-2211-O-PERFIL-DE-OUTRA-VERSAO-FICA-NA-LISTA-E-A-LEITURA-TOLERA: a gravação é estrita e a leitura
é tolerante, como no `maquina.json` (D-LEITURA-MAQUINA-JSON). O campo que esta versão não conhece
sai com aviso e o resto vale; o formato mais novo aparece marcado e fora da seleção; a
`priority` fora de 0-200 se recusa ao gravar e se grampeia ao ler. O arquivo do disco não muda
por ler. A pasta de perfis é do lar de mentira do conftest.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli.app import app
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile
from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

runner = CliRunner()


@pytest.fixture
def aviso(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    espiao = MagicMock()
    monkeypatch.setattr(loader, "logger", espiao)
    monkeypatch.setattr(loader, "_CAMPOS_JA_AVISADOS", set())
    monkeypatch.setattr(loader, "_PRIORIDADES_JA_AVISADAS", set())
    return espiao


def _eventos(espiao: MagicMock) -> list[str]:
    return [c.args[0] for c in espiao.warning.call_args_list]


def _grava(nome: str, **mudancas: Any) -> Path:
    base: dict[str, Any] = {
        "name": nome,
        "version": 1,
        "match": {"type": "criteria", "window_class": [f"{nome}_janela"]},
        "priority": 10,
    }
    base.update(mudancas)
    caminho = profiles_dir(ensure=True) / f"{nome}.json"
    caminho.write_text(json.dumps(base, indent=2), encoding="utf-8")
    return caminho


def _nomes() -> list[str]:
    return [p.name for p in loader.load_all_profiles()]


def test_o_campo_desconhecido_sai_com_aviso_e_o_perfil_continua(aviso: MagicMock) -> None:
    arquivo = _grava(
        "campo_novo",
        campo_novo={"x": 1},
        leds={"lightbar": [1, 2, 3], "efeito_novo": "arco-iris"},
        match={"type": "criteria", "window_class": ["jogo"], "peso_novo": 3},
    )
    bytes_de_antes = arquivo.read_bytes()

    perfis = {p.name: p for p in loader.load_all_profiles()}

    assert "campo_novo" in perfis
    assert perfis["campo_novo"].match.matches({"wm_class": "jogo"})
    assert perfis["campo_novo"].leds.lightbar == (1, 2, 3)
    assert "profile_campo_desconhecido" in _eventos(aviso)
    campos = next(
        c.kwargs["campos"] for c in aviso.warning.call_args_list
        if c.args[0] == "profile_campo_desconhecido")
    assert campos == ["campo_novo", "leds.efeito_novo", "match.peso_novo"]
    assert arquivo.read_bytes() == bytes_de_antes


def test_a_gravacao_continua_estrita_com_o_campo_desconhecido() -> None:
    with pytest.raises(ValidationError):
        Profile.model_validate({"name": "x", "match": {"type": "any"}, "campo_novo": 1})


def test_o_formato_mais_novo_fica_fora_da_selecao_e_aparece_marcado(aviso: MagicMock) -> None:
    """D-2211-O-PERFIL-DE-OUTRA-VERSAO-FICA-NA-LISTA-E-A-LEITURA-TOLERA."""
    _grava("bom")
    futuro = _grava("futuro", version=2)
    bytes_de_antes = futuro.read_bytes()

    assert _nomes() == ["bom"]
    assert loader.perfis_de_versao_mais_nova() == [
        loader.PerfilDeVersaoMaisNova("futuro", "futuro.json", 2)]
    with pytest.raises(loader.PerfilDeVersaoMaisNovaError):
        loader.load_profile("futuro")
    assert futuro.read_bytes() == bytes_de_antes


def test_o_comando_lista_o_de_formato_mais_novo_marcado(aviso: MagicMock) -> None:
    _grava("bom")
    _grava("futuro", version=2)

    resultado = runner.invoke(app, ["profile", "list"])

    assert resultado.exit_code == 0, resultado.output
    assert "bom" in resultado.output
    assert "futuro" in resultado.output
    assert "versão mais nova" in resultado.output

    em_json = json.loads(runner.invoke(app, ["profile", "list", "--json"]).output)
    assert {"nome": "futuro", "de_versao_mais_nova": True, "formato": 2} in em_json


def test_o_comando_show_do_formato_mais_novo_diz_a_frase(aviso: MagicMock) -> None:
    _grava("futuro", version=2)

    resultado = runner.invoke(app, ["profile", "show", "futuro"])

    assert resultado.exit_code == 1
    assert "versão mais nova" in resultado.output
    assert "Traceback" not in resultado.output


def test_ler_e_listar_deixa_todo_arquivo_byte_a_byte(aviso: MagicMock) -> None:
    arquivos = [
        _grava("campo_novo", campo_novo=1),
        _grava("futuro", version=2),
        _grava("alto", priority=99999),
        _grava("bom"),
    ]
    antes = [a.read_bytes() for a in arquivos]

    loader.load_all_profiles()
    loader.perfis_de_versao_mais_nova()
    loader.audit_profiles()
    runner.invoke(app, ["profile", "list"])

    assert [a.read_bytes() for a in arquivos] == antes


@pytest.mark.parametrize("fora", ["201", "-1", "99999"])
def test_o_comando_recusa_prioridade_fora_da_faixa_com_rc_2(fora: str) -> None:
    resultado = runner.invoke(
        app, ["profile", "create", "alto", "--priority", fora, "--match-class", "jogo"])

    assert resultado.exit_code == 2
    assert not list(profiles_dir(ensure=True).glob("*.json"))


@pytest.mark.parametrize("limite", ["0", "200"])
def test_a_faixa_inclui_os_dois_limites(limite: str) -> None:
    resultado = runner.invoke(
        app, ["profile", "create", "limite", "--priority", limite, "--match-class", "jogo"])

    assert resultado.exit_code == 0, resultado.output
    assert json.loads(
        (profiles_dir() / "limite.json").read_text(encoding="utf-8"))["priority"] == int(limite)


def test_o_schema_recusa_a_prioridade_fora_da_faixa_para_todo_chamador() -> None:
    for fora in (201, -1):
        with pytest.raises(ValidationError):
            Profile(name="x", match=MatchCriteria(window_class=["a"]), priority=fora)
    assert Profile(name="x", match=MatchCriteria(window_class=["a"]), priority=200).priority == 200


def test_o_arquivo_antigo_fora_da_faixa_se_grampeia_com_aviso(aviso: MagicMock) -> None:
    arquivo = _grava("alto", priority=99999)
    _grava("baixo", priority=-5)
    bytes_de_antes = arquivo.read_bytes()

    prioridades = {p.name: p.priority for p in loader.load_all_profiles()}

    assert prioridades == {"alto": 200, "baixo": 0}
    assert _eventos(aviso).count("profile_prioridade_grampeada") == 2
    assert arquivo.read_bytes() == bytes_de_antes


def test_a_migracao_automatica_nao_regrava_o_que_so_a_leitura_tolerante_aceita(
    aviso: MagicMock,
) -> None:
    from hefesto_dualsense4unix.integrations.censo_dos_lancadores import JogoDoLancador

    jogo = JogoDoLancador(chave="app", nome="Jogo", loja="Epic", instalado=True,
                          executavel="retail/jogo.exe", umu_id="umu-9921001")
    catalogo = [("Heroic", jogo)]
    tolerados = [
        _grava("com_campo", match={"type": "criteria", "window_class": ["jogo.exe"]},
               campo_novo=1),
        _grava("alto", match={"type": "criteria", "window_class": ["jogo.exe"]},
               priority=99999),
    ]
    antes = [a.read_bytes() for a in tolerados]

    loader.reapontar_perfis_com_chave_de_executavel(catalogo)

    assert [a.read_bytes() for a in tolerados] == antes
    _grava("estrito", match={"type": "criteria", "window_class": ["jogo.exe"]})
    assert loader.reapontar_perfis_com_chave_de_executavel(catalogo) == ("estrito",)


def test_o_erro_que_nao_e_campo_desconhecido_continua_derrubando_so_aquele_arquivo(
    aviso: MagicMock,
) -> None:
    _grava("bom")
    _grava("quebrado", leds={"lightbar": "nao-e-cor"})

    assert _nomes() == ["bom"]
