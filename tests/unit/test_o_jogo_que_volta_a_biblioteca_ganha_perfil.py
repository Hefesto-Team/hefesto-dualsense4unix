"""O-JOGO-QUE-SAI-DA-BIBLIOTECA-SAI-DA-MARCA-E-VOLTA-COM-PERFIL-01 (02/11/2026).

A marca `.perfis_de_jogo_semeados` diz «este jogo, nesta instalação, já ganhou perfil». O jogo
que sai da biblioteca lida com sucesso sai da marca; quando volta, ganha perfil de novo. O perfil
apagado à mão com o jogo instalado continua apagado, e um tropeço de leitura não esquece nada.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import structlog

from hefesto_dualsense4unix.integrations.jogos_locais import JogoLocal
from hefesto_dualsense4unix.profiles import loader

APPID = "910001"
NOME = "Ilha de Vidro"
ARQUIVO = "ilha_de_vidro.json"

CLASSE = "ChuvaFina"
ATALHO = (
    "[Desktop Entry]\nType=Application\nName=Chuva Fina\n"
    "Exec=/opt/chuva/chuva\nStartupWMClass=ChuvaFina\nCategories=Game;\n"
)
ARQUIVO_DO_ATALHO = "chuva_fina.json"


def _steamapps(casa: Path) -> Path:
    pasta = casa / ".steam" / "steam" / "steamapps"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _instala(casa: Path, appid: str = APPID, nome: str = NOME) -> Path:
    manifesto = _steamapps(casa) / f"appmanifest_{appid}.acf"
    manifesto.write_text(
        f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"{nome}"\n}}\n',
        encoding="utf-8",
    )
    return manifesto


def _atalhos(casa: Path) -> Path:
    pasta = casa / ".local" / "share" / "applications"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _identidades_da_marca(destino: Path) -> list[str]:
    marca = destino / loader.MARCA_DE_SEMEADURA_DE_JOGOS
    if not marca.exists():
        return []
    return [
        ln.split("\t", 1)[0]
        for ln in marca.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]


@pytest.fixture()
def lancadores_ligados(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(loader, "lancadores_sem_perfil_por_jogo", frozenset)


def test_o_jogo_da_steam_que_sai_e_volta_ganha_o_perfil_de_novo(
    tmp_path: Path, lancadores_ligados: None
) -> None:
    casa, destino = tmp_path / "casa", tmp_path / "perfis"
    manifesto = _instala(casa)

    assert loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa).criados == (ARQUIVO,)
    (destino / ARQUIVO).unlink()

    presente = loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa)
    assert [r.desfecho for r in presente.linhas] == ["ja_semeado"]
    assert not (destino / ARQUIVO).exists()
    assert _identidades_da_marca(destino) == [APPID]

    manifesto.unlink()
    with structlog.testing.capture_logs() as registros:
        loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa)
    assert _identidades_da_marca(destino) == []
    esquecidos = [r for r in registros if r["event"] == "perfil_de_jogo_esquecido_na_marca"]
    assert [(r.get("appid"), r.get("classe")) for r in esquecidos] == [(APPID, None)]

    _instala(casa)
    volta = loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa)
    assert volta.criados == (ARQUIVO,)
    dados = json.loads((destino / ARQUIVO).read_text(encoding="utf-8"))
    assert dados["match"]["window_class"] == [f"steam_app_{APPID}"]
    assert _identidades_da_marca(destino) == [APPID]


def test_o_jogo_de_janela_que_sai_e_volta_ganha_o_perfil_de_novo(
    tmp_path: Path, lancadores_ligados: None
) -> None:
    casa, destino = tmp_path / "casa", tmp_path / "perfis"
    _steamapps(casa)
    atalho = _atalhos(casa) / "chuva.desktop"
    atalho.write_text(ATALHO, encoding="utf-8")

    assert loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa).criados == (
        ARQUIVO_DO_ATALHO,
    )
    (destino / ARQUIVO_DO_ATALHO).unlink()
    atalho.unlink()
    with structlog.testing.capture_logs() as registros:
        loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa)
    assert _identidades_da_marca(destino) == []
    esquecidos = [r for r in registros if r["event"] == "perfil_de_jogo_esquecido_na_marca"]
    assert [(r.get("appid"), r.get("classe")) for r in esquecidos] == [
        (None, CLASSE.casefold())
    ]

    atalho.write_text(ATALHO, encoding="utf-8")
    volta = loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa)
    assert volta.criados == (ARQUIVO_DO_ATALHO,)
    dados = json.loads((destino / ARQUIVO_DO_ATALHO).read_text(encoding="utf-8"))
    assert dados["match"]["window_class"] == [CLASSE]


def test_o_perfil_apagado_com_o_jogo_instalado_continua_apagado(
    tmp_path: Path, lancadores_ligados: None
) -> None:
    casa, destino = tmp_path / "casa", tmp_path / "perfis"
    _instala(casa)
    loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa)
    (destino / ARQUIVO).unlink()

    for _ in range(3):
        resultado = loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa)
        assert resultado.criados == ()
    assert not (destino / ARQUIVO).exists()
    assert _identidades_da_marca(destino) == [APPID]


@pytest.mark.skipif(os.geteuid() == 0, reason="root lista a pasta sem permissão")
def test_a_biblioteca_que_nao_se_lista_nao_esquece_nada(
    tmp_path: Path, lancadores_ligados: None
) -> None:
    casa, destino = tmp_path / "casa", tmp_path / "perfis"
    _instala(casa)
    loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa)
    (destino / ARQUIVO).unlink()

    steamapps = _steamapps(casa)
    steamapps.chmod(0)
    try:
        loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa)
    finally:
        steamapps.chmod(0o755)

    assert _identidades_da_marca(destino) == [APPID]
    assert loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa).criados == ()
    assert not (destino / ARQUIVO).exists()


def test_a_steam_que_sumiu_inteira_nao_esquece_nada(
    tmp_path: Path, lancadores_ligados: None
) -> None:
    casa, destino = tmp_path / "casa", tmp_path / "perfis"
    _instala(casa)
    loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa)
    (destino / ARQUIVO).unlink()

    loader.semear_perfis_dos_jogos(dest_dir=destino, home=tmp_path / "outra-casa")

    assert _identidades_da_marca(destino) == [APPID]


def test_o_manifesto_que_nao_se_le_ainda_e_o_jogo_instalado(
    tmp_path: Path, lancadores_ligados: None
) -> None:
    casa, destino = tmp_path / "casa", tmp_path / "perfis"
    manifesto = _instala(casa)
    loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa)
    (destino / ARQUIVO).unlink()

    manifesto.write_text("", encoding="utf-8")
    loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa)

    assert _identidades_da_marca(destino) == [APPID]


def test_a_biblioteca_de_lancador_ilegivel_nao_esquece_o_jogo_de_janela(
    tmp_path: Path, lancadores_ligados: None
) -> None:
    casa, destino = tmp_path / "casa", tmp_path / "perfis"
    _steamapps(casa)
    atalho = _atalhos(casa) / "chuva.desktop"
    atalho.write_text(ATALHO, encoding="utf-8")
    loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa)
    (destino / ARQUIVO_DO_ATALHO).unlink()

    cache = casa / ".config" / "heroic" / "store_cache"
    cache.mkdir(parents=True)
    (cache / "legendary_library.json").write_text('{"library": "torto"}', encoding="utf-8")
    atalho.unlink()
    loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa)

    assert _identidades_da_marca(destino) == [f"janela:{CLASSE.casefold()}"]


def test_o_lancador_desligado_nao_conta_como_jogo_que_saiu(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    casa, destino = tmp_path / "casa", tmp_path / "perfis"
    _instala(casa)
    monkeypatch.setattr(loader, "lancadores_sem_perfil_por_jogo", frozenset)
    loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa)
    (destino / ARQUIVO).unlink()

    monkeypatch.setattr(
        loader, "lancadores_sem_perfil_por_jogo", lambda: frozenset({"steam"})
    )
    resultado = loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa)

    assert resultado.linhas == ()
    assert _identidades_da_marca(destino) == [APPID]


def test_a_lista_de_quem_chama_nao_esquece_nada(tmp_path: Path) -> None:
    destino = tmp_path / "perfis"
    dois = [
        JogoLocal(appid=APPID, nome=NOME, fonte="steam"),
        JogoLocal(appid="910002", nome="Corrida Sem Fim", fonte="steam"),
    ]
    loader.semear_perfis_dos_jogos(dest_dir=destino, jogos=dois)

    loader.semear_perfis_dos_jogos(dest_dir=destino, jogos=dois[:1])

    assert sorted(_identidades_da_marca(destino)) == [APPID, "910002"]


@pytest.mark.skipif(os.geteuid() == 0, reason="root lista a pasta sem permissão")
def test_a_pasta_de_atalhos_que_nao_se_lista_nao_esquece_o_jogo_de_janela(
    tmp_path: Path, lancadores_ligados: None
) -> None:
    casa, destino = tmp_path / "casa", tmp_path / "perfis"
    _steamapps(casa)
    pasta = _atalhos(casa)
    (pasta / "chuva.desktop").write_text(ATALHO, encoding="utf-8")
    loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa)
    (destino / ARQUIVO_DO_ATALHO).unlink()

    pasta.chmod(0)
    try:
        loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa)
    finally:
        pasta.chmod(0o755)

    assert _identidades_da_marca(destino) == [f"janela:{CLASSE.casefold()}"]
    assert loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa).criados == ()
