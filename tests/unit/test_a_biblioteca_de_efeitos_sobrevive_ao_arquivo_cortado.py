"""A biblioteca «Meus efeitos» sobrevive ao arquivo de preferências cortado."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from hefesto_dualsense4unix.app import gui_prefs
from hefesto_dualsense4unix.interface.pacotes import meus_efeitos


@pytest.fixture
def pasta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path / "hefesto-dualsense4unix"


def _guardar_a_biblioteca() -> None:
    for i in range(6):
        meus_efeitos.criar_efeito("imersao", f"imersao {i}", "base", {"forca": i})
    meus_efeitos.criar_efeito("luz", "luz 0", "base", {"brilho": 3})
    gui_prefs.guardar_largura_de_coluna("lista", "nome", 200)


def _cortar(arquivo: Path) -> None:
    bruto = arquivo.read_bytes()
    arquivo.write_bytes(bruto[: len(bruto) // 2])


def test_criar_efeito_com_o_arquivo_cortado_traz_os_anteriores_de_volta(pasta: Path) -> None:
    """D-1911-O-ESTADO-SE-GRAVA-INTEIRO: o arquivo cortado não apaga a biblioteca."""
    _guardar_a_biblioteca()
    arquivo = pasta / "gui_preferences.json"
    _cortar(arquivo)

    meus_efeitos.criar_efeito("imersao", "novo", "base", {"forca": 9})

    assert len(meus_efeitos.meus_efeitos("imersao")) == 7
    assert set(meus_efeitos.meus_efeitos("luz")) == {"luz 0"}
    assert gui_prefs.larguras_da_tabela("lista") == {"nome": 200}
    assert isinstance(json.loads(arquivo.read_text(encoding="utf-8")), dict)


def test_o_arquivo_torto_fica_ao_lado_com_a_data(pasta: Path) -> None:
    """D-1911-O-ESTADO-SE-GRAVA-INTEIRO: nada que estava no disco some sem rastro."""
    _guardar_a_biblioteca()
    arquivo = pasta / "gui_preferences.json"
    _cortar(arquivo)
    torto = arquivo.read_bytes()

    gui_prefs.load_gui_prefs()
    gui_prefs.load_gui_prefs()

    guardados = list(pasta.glob("gui_preferences.json.corrompido-*"))
    assert len(guardados) == 1
    assert guardados[0].read_bytes() == torto


def test_sem_copia_o_torto_vai_ao_lado_antes_de_gravar(pasta: Path) -> None:
    """D-1911-O-ESTADO-SE-GRAVA-INTEIRO: sem cópia boa, o torto é preservado e valem os padrões."""
    pasta.mkdir(parents=True)
    arquivo = pasta / "gui_preferences.json"
    arquivo.write_text('{"gatilhos_meus_efeitos": {"a": {"le', encoding="utf-8")

    meus_efeitos.criar_efeito("imersao", "novo", "base", {"forca": 1})

    assert list(meus_efeitos.meus_efeitos("imersao")) == ["novo"]
    guardados = list(pasta.glob("gui_preferences.json.corrompido-*"))
    assert len(guardados) == 1
    assert guardados[0].read_text(encoding="utf-8").startswith('{"gatilhos_meus_efeitos"')


def test_arquivo_que_nao_e_texto_ou_nao_e_objeto_tambem_se_recupera(pasta: Path) -> None:
    """D-1911-O-ESTADO-SE-GRAVA-INTEIRO: bytes soltos e JSON que não é objeto valem o mesmo."""
    _guardar_a_biblioteca()
    arquivo = pasta / "gui_preferences.json"
    for torto in (b"\xff\xfe\x00\x80", b"[1, 2]"):
        arquivo.write_bytes(torto)
        assert len(gui_prefs.load_gui_prefs()["imersao_meus_efeitos"]) == 6


def test_pasta_so_de_leitura_levanta_e_deixa_o_arquivo_de_antes(pasta: Path) -> None:
    """D-1911-O-ESTADO-SE-GRAVA-INTEIRO: a gravação que falha levanta e o arquivo fica intacto."""
    _guardar_a_biblioteca()
    arquivo = pasta / "gui_preferences.json"
    antes = arquivo.read_bytes()
    pasta.chmod(0o500)
    try:
        if os.access(pasta, os.W_OK):
            pytest.skip("a pasta continua gravável (usuário sem restrição de permissão)")
        with pytest.raises(OSError):
            meus_efeitos.criar_efeito("imersao", "novo", "base", {"forca": 1})
        assert arquivo.read_bytes() == antes
    finally:
        pasta.chmod(0o700)
    assert sorted(p.name for p in pasta.iterdir() if p.name.endswith(".tmp")) == []


def test_a_memoria_da_rota_de_som_nao_derruba_a_troca_de_saida(pasta: Path) -> None:
    """D-1911-O-ESTADO-SE-GRAVA-INTEIRO: `set_pref` segue sem levantar para a rota de som."""
    pasta.mkdir(parents=True)
    (pasta / "gui_preferences.json").write_text("{}", encoding="utf-8")
    pasta.chmod(0o500)
    try:
        if os.access(pasta, os.W_OK):
            pytest.skip("a pasta continua gravável (usuário sem restrição de permissão)")
        gui_prefs.set_pref("rota_anterior", "sink")
    finally:
        pasta.chmod(0o700)
