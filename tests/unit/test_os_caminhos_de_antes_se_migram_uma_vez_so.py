"""Os caminhos de antes se migram uma vez só, e só com os nomes que o produto conhece."""
from __future__ import annotations

import types

import hefesto_dualsense4unix.utils.migrate_legacy_paths as mlp
from hefesto_dualsense4unix.utils import xdg_paths


def _lar(tmp_path, monkeypatch):
    antigo = tmp_path / "antigo"
    (antigo / "profiles").mkdir(parents=True)
    novo = tmp_path / "novo"
    novo.mkdir()
    monkeypatch.setattr(
        mlp,
        "_LEGACY",
        types.SimpleNamespace(user_config_dir=str(antigo), user_data_dir=str(tmp_path / "d")),
    )
    monkeypatch.setattr(xdg_paths, "config_dir", lambda ensure=False: novo)
    monkeypatch.setattr(xdg_paths, "data_dir", lambda ensure=False: tmp_path / "dn")
    return antigo, novo


def test_a_segunda_subida_nao_traz_de_volta_o_que_se_apagou(tmp_path, monkeypatch):
    """D-1911-OS-CAMINHOS-DE-ANTES-SE-MIGRAM-UMA-VEZ-SO: o perfil apagado fica apagado."""
    antigo, novo = _lar(tmp_path, monkeypatch)
    (antigo / "profiles" / "fps.json").write_text("{}", encoding="utf-8")
    (antigo / "native_mode.flag").write_text("x", encoding="utf-8")

    assert sorted(mlp.migrate_legacy_paths()["config"]) == ["native_mode.flag", "profiles/fps.json"]
    (novo / "profiles" / "fps.json").unlink()
    (novo / "native_mode.flag").unlink()

    assert mlp.migrate_legacy_paths() == {}
    assert not (novo / "profiles" / "fps.json").exists()
    assert not (novo / "native_mode.flag").exists()


def test_a_marca_nasce_mesmo_sem_nada_a_copiar(tmp_path, monkeypatch):
    antigo, novo = _lar(tmp_path, monkeypatch)
    assert mlp.migrate_legacy_paths() == {}
    (antigo / "session.json").write_text("{}", encoding="utf-8")
    assert mlp.migrate_legacy_paths() == {}
    assert not (novo / "session.json").exists()


def test_nome_desconhecido_de_outra_ferramenta_nao_se_copia(tmp_path, monkeypatch):
    antigo, novo = _lar(tmp_path, monkeypatch)
    (antigo / "autoria-vedados").write_text("x", encoding="utf-8")
    (antigo / "biblioteca-vedada").mkdir()
    (antigo / "biblioteca-vedada" / "a.json").write_text("{}", encoding="utf-8")
    (antigo / "profiles" / "notas.txt").write_text("x", encoding="utf-8")
    (antigo / "maquina.json").write_text("{}", encoding="utf-8")

    assert mlp.migrate_legacy_paths() == {"config": ["maquina.json"]}
    assert sorted(p.name for p in novo.iterdir() if not p.name.startswith(".")) == ["maquina.json"]


def test_o_que_o_produto_grava_e_e_de_quem_usa_viaja_e_o_que_o_install_refaz_nao(
    tmp_path, monkeypatch
):
    """D-1911-OS-CAMINHOS-DE-ANTES-SE-MIGRAM-UMA-VEZ-SO: só o nome classificado viaja."""
    antigo, novo = _lar(tmp_path, monkeypatch)
    for nome in ("controllers.json", "gui_preferences.json", "zeros-dos-sensores.json",
                 "opcoes_por_jogo.txt", "gabinete.json"):
        (antigo / nome).write_text("{}", encoding="utf-8")

    assert sorted(mlp.migrate_legacy_paths()["config"]) == [
        "controllers.json", "gui_preferences.json", "opcoes_por_jogo.txt",
        "zeros-dos-sensores.json",
    ]
    assert not (novo / "gabinete.json").exists()
