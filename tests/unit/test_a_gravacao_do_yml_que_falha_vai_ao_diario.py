"""A-GRAVACAO-DO-YML-QUE-FALHA-DEPOIS-DA-ANOTACAO-VAI-AO-DIARIO-01 — as réguas.

A carona anota o registro («feito») e só então grava o `.yml` do excluído. A falha da
anotação já tinha linha no diário; a falha da gravação, depois da anotação, também
tem: o registro volta ao de antes, e a reanotação que falha não é engolida calada.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest
import structlog

from hefesto_dualsense4unix.integrations import cura_por_estrada as cpe
from hefesto_dualsense4unix.integrations import lista_de_exclusao as lx
from tests.unit.test_a_exclusao_mora_na_camada_do_jogo import (
    _JANELA,
    _PONTE,
    _carona,
    _lutris_flatpak,
)
from tests.unit import a_exclusao_de_antes as antiga

_EVENTO = "carona_nao_gravou_o_yml"


@pytest.fixture(autouse=True)
def _lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    lar = tmp_path / "lar"
    lar.mkdir()
    monkeypatch.setenv("HOME", str(lar))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(lar / ".config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(lar / ".local" / "state"))
    monkeypatch.setenv("XDG_DATA_HOME", str(lar / ".local" / "share"))
    from hefesto_dualsense4unix.utils.xdg_paths import launch_env_dir

    amb = launch_env_dir(ensure=True)
    (amb / "default.env").write_text("".join(f"{k}={v}\n" for k, v in _PONTE.items()))
    return lar


def _excluido_com_a_carona_por_fazer(lar: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """O jogo pelo Proton excluído quando a carona ainda não punha o par do Xalia."""
    yml = _lutris_flatpak(lar)
    _carona(lar)
    with monkeypatch.context() as m:
        m.setattr(cpe, "_pelo_proton_por_yml", lambda _lar: {})
        assert antiga.adicionar(_JANELA, lancador="lutris", nome="Recettear",
                                lar=lar) == "adicionado"
    return yml


def _o_registro() -> cpe.YmlDoJogo:
    return lx.ler()[0].lutris[0]


def _so_o_yml_falha(monkeypatch: pytest.MonkeyPatch, yml: Path) -> None:
    escrever = cpe._escrever_atomico

    def _falha(alvo: Path, texto: str) -> None:
        if Path(alvo).resolve() == yml.resolve():
            raise OSError("disco cheio")
        escrever(alvo, texto)

    monkeypatch.setattr(cpe, "_escrever_atomico", _falha)


def test_a_gravacao_que_falha_depois_da_anotacao_vai_ao_diario(
        _lar: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A decisão D-0810-A-GRAVACAO-QUE-FALHA-VAI-AO-DIARIO.
    yml = _excluido_com_a_carona_por_fazer(_lar, monkeypatch)
    disco_antes = yml.read_bytes()
    registro_antes = _o_registro()
    with monkeypatch.context() as m:
        _so_o_yml_falha(m, yml)
        with structlog.testing.capture_logs() as diario:
            _carona(_lar)
    assert yml.read_bytes() == disco_antes
    assert _o_registro() == registro_antes, "o registro ficou com o que o disco não tem"
    linhas = [x for x in diario if x.get("event") == _EVENTO]
    assert len(linhas) == 1, diario
    assert linhas[0]["status"] == "OSError", linhas
    assert linhas[0]["reanotou"] == "feito", linhas
    assert linhas[0]["arquivos"] == 1 and linhas[0]["quem"] == cpe.QUEM_SERVICO, linhas


@pytest.mark.parametrize("como", ["erro", "excecao"])
def test_a_reanotacao_que_tambem_falha_nao_morre_calada(
        _lar: Path, monkeypatch: pytest.MonkeyPatch, como: str) -> None:
    # A decisão D-0810-A-GRAVACAO-QUE-FALHA-VAI-AO-DIARIO.
    yml = _excluido_com_a_carona_por_fazer(_lar, monkeypatch)
    disco_antes = yml.read_bytes()
    registro_antes = _o_registro()
    anotar = lx.anotar_os_ymls
    chamadas: list[int] = []

    def _a_segunda_falha(ymls: object, *a: object, **k: object) -> str:
        chamadas.append(1)
        if len(chamadas) == 1:
            return anotar(ymls, *a, **k)  # type: ignore[arg-type]
        if como == "excecao":
            raise RuntimeError("lista sumiu")
        return "erro"

    with monkeypatch.context() as m:
        _so_o_yml_falha(m, yml)
        m.setattr(lx, "anotar_os_ymls", _a_segunda_falha)
        with structlog.testing.capture_logs() as diario:
            _carona(_lar)
    assert len(chamadas) == 2, chamadas
    assert yml.read_bytes() == disco_antes
    assert _o_registro() != registro_antes, "a segunda anotação não devia ter passado"
    linhas = [x for x in diario if x.get("event") == _EVENTO]
    assert len(linhas) == 1, diario
    assert linhas[0]["status"] == "OSError" and linhas[0]["reanotou"] == como, linhas


def test_a_janela_tambem_diz_quem_desistiu_da_gravacao(
        _lar: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    yml = _excluido_com_a_carona_por_fazer(_lar, monkeypatch)
    with monkeypatch.context() as m:
        _so_o_yml_falha(m, yml)
        with structlog.testing.capture_logs() as diario:
            cpe.curar_todas_as_estradas(lar=_lar, raiz_sistema=_lar.parent / "sistema",
                                        espera=2.0)
    linhas = [x for x in diario if x.get("event") == _EVENTO]
    assert [(x["arquivos"], x["quem"]) for x in linhas] == [(1, cpe.QUEM_JANELA)], diario


def test_a_gravacao_que_passa_nao_deixa_linha(
        _lar: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    yml = _excluido_com_a_carona_por_fazer(_lar, monkeypatch)
    disco_antes = yml.read_bytes()
    with structlog.testing.capture_logs() as diario:
        _carona(_lar)
    assert yml.read_bytes() != disco_antes, "a carona devia ter gravado o `.yml`"
    assert not [x for x in diario if x.get("event") == _EVENTO], diario


def test_o_docstring_da_carona_nao_chama_o_usuario_de_ela() -> None:
    doc = cpe.EstradasEscritas.__doc__ or ""
    assert "em que ela" not in doc, doc
    assert "onde a carona escreveu" in doc, doc


def test_a_pasta_que_recusa_de_verdade_tambem_vai_ao_diario(
        _lar: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem dublê na gravação: a pasta dos `.yml` sem escrita, como o disco a recusa."""
    if os.geteuid() == 0:  # pragma: no cover - como root o 0555 não recusa nada
        pytest.skip("como root a pasta sem escrita não recusa")
    yml = _excluido_com_a_carona_por_fazer(_lar, monkeypatch)
    disco_antes = yml.read_bytes()
    registro_antes = _o_registro()
    pasta = yml.parent
    modo = pasta.stat().st_mode
    pasta.chmod(0o555)
    try:
        with structlog.testing.capture_logs() as diario:
            _carona(_lar)
    finally:
        pasta.chmod(modo)
    assert yml.read_bytes() == disco_antes
    assert _o_registro() == registro_antes, "o registro ficou com o que o disco não tem"
    linhas = [x for x in diario if x.get("event") == _EVENTO]
    assert [(x["status"], x["reanotou"], x["arquivos"]) for x in linhas] == [
        ("PermissionError", "feito", 1)], diario



def _segunda_copia(yml: Path) -> Path:
    """A mesma loja, instalada duas vezes no mesmo Lutris: dois `.yml` para um jogo."""
    outro = yml.with_name("recettear-1759370001.yml")
    outro.write_bytes(yml.read_bytes())
    con = sqlite3.connect(yml.parent.parent / "pga.db")
    with con:
        con.execute(
            "INSERT INTO games (name, slug, runner, executable, directory, installed, "
            "configpath, service, service_id) "
            "SELECT name, slug || '-2', runner, executable, directory, installed, "
            "'recettear-1759370001', service, service_id FROM games WHERE slug = 'recettear'")
    con.close()
    return outro


def test_so_o_yml_que_falhou_conta_e_volta(
        _lar: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A decisão D-0810-A-GRAVACAO-QUE-FALHA-VAI-AO-DIARIO.
    """Dois `.yml` no mesmo jogo: só o que falhou volta ao de antes e entra na conta."""
    falha = _lutris_flatpak(_lar)
    grava = _segunda_copia(falha)
    _carona(_lar)
    with monkeypatch.context() as m:
        m.setattr(cpe, "_pelo_proton_por_yml", lambda _lar: {})
        assert antiga.adicionar(_JANELA, lancador="lutris", nome="Recettear",
                                lar=_lar) == "adicionado"
    antes = {Path(y.arquivo).name: y for y in lx.ler()[0].lutris}
    assert set(antes) == {falha.name, grava.name}, antes
    disco_de_quem_grava = grava.read_bytes()
    with monkeypatch.context() as m:
        _so_o_yml_falha(m, falha)
        with structlog.testing.capture_logs() as diario:
            _carona(_lar)
    depois = {Path(y.arquivo).name: y for y in lx.ler()[0].lutris}
    assert depois[falha.name] == antes[falha.name], "o que falhou devia voltar"
    assert depois[grava.name] != antes[grava.name], "o que gravou devia andar"
    assert grava.read_bytes() != disco_de_quem_grava, "a carona devia ter gravado o outro"
    linhas = [x for x in diario if x.get("event") == _EVENTO]
    assert [(x["status"], x["reanotou"], x["arquivos"]) for x in linhas] == [
        ("OSError", "feito", 1)], diario
