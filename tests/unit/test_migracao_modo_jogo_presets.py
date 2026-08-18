"""MODO-01 — a sprint precisa alcançar quem JÁ tem o Hefesto instalado.

O defeito que estes testes travam não é de código, é de alcance: a semeadura de
presets não sobrescreve arquivo existente (de propósito — é o que impede o
projeto de apagar configuração da usuária), então mudar o preset em `assets/`
conserta só a instalação nova. Medido na máquina de desenvolvimento em 25/07:
11 dos 13 perfis com ``mode: null`` e o `coop_local` em prioridade 45, perdendo
para o perfil de navegação (50) — abrir um jogo de co-op pela Steam entregava o
perfil de navegação.

O outro lado é igualmente importante e tem teste próprio: a migração NÃO pode
passar por cima de escolha dela. Onde houver edição, recua.
"""
from __future__ import annotations

import json
from pathlib import Path

from hefesto_dualsense4unix.profiles import loader


def _escreve(directory: Path, nome: str, dados: dict) -> Path:
    caminho = directory / f"{nome}.json"
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    return caminho


def _le(caminho: Path) -> dict:
    return json.loads(caminho.read_text(encoding="utf-8"))


def test_preset_de_jogo_sem_modo_recebe_o_modo_jogo(tmp_path: Path) -> None:
    """O caso dela: preset de gênero instalado antes da sprint, com `mode` nulo."""
    fps = _escreve(tmp_path, "fps", {"name": "FPS", "priority": 60, "mode": None})

    migrados = loader.migrate_modo_jogo_nos_presets(dest_dir=tmp_path)

    assert "fps.json" in migrados
    modo = _le(fps)["mode"]
    assert isinstance(modo, dict) and modo.get("kind") == "gamepad", (
        "preset de jogo sem modo é exatamente o que fazia o modo jogo não ligar"
    )


def test_modo_escolhido_por_ela_nao_e_sobrescrito(tmp_path: Path) -> None:
    """A regra que torna a migração segura: onde ela mexeu, recua.

    Um perfil de jogo em Modo Nativo é uma escolha deliberada ("Jogar direto
    (Sony)") — trocá-la por gamepad seria a migração decidindo no lugar dela.
    """
    escolha = {"kind": "native"}
    fps = _escreve(tmp_path, "fps", {"name": "FPS", "priority": 60,
                                     "mode": dict(escolha)})

    loader.migrate_modo_jogo_nos_presets(dest_dir=tmp_path)

    assert _le(fps)["mode"] == escolha


def test_coop_local_sai_de_tras_do_perfil_de_navegacao(tmp_path: Path) -> None:
    """Prioridade 45 perdia para `navegacao` (50), que casa a janela da Steam."""
    coop = _escreve(tmp_path, "coop_local", {"name": "Co-op local", "priority": 45,
                                             "mode": {"kind": "gamepad"}})

    loader.migrate_modo_jogo_nos_presets(dest_dir=tmp_path)

    assert _le(coop)["priority"] >= 75, (
        "co-op precisa vencer o perfil que casa a janela do cliente Steam"
    )


def test_prioridade_ajustada_por_ela_e_preservada(tmp_path: Path) -> None:
    """Qualquer número diferente do de fábrica antigo é escolha dela."""
    coop = _escreve(tmp_path, "coop_local", {"name": "Co-op local", "priority": 92,
                                             "mode": {"kind": "gamepad"}})

    loader.migrate_modo_jogo_nos_presets(dest_dir=tmp_path)

    assert _le(coop)["priority"] == 92


def test_migracao_e_one_shot(tmp_path: Path) -> None:
    """Rodou uma vez, não roda de novo — nem desfaz o que ela mudar depois."""
    fps = _escreve(tmp_path, "fps", {"name": "FPS", "priority": 60, "mode": None})
    assert loader.migrate_modo_jogo_nos_presets(dest_dir=tmp_path) != []

    dados = _le(fps)
    dados["mode"] = {"kind": "desktop"}
    _escreve(tmp_path, "fps", dados)

    assert loader.migrate_modo_jogo_nos_presets(dest_dir=tmp_path) == []
    assert _le(fps)["mode"] == {"kind": "desktop"}


def test_perfil_ausente_nao_e_criado(tmp_path: Path) -> None:
    """Migração não semeia: quem apagou um preset não o vê voltar por aqui."""
    loader.migrate_modo_jogo_nos_presets(dest_dir=tmp_path)
    assert not (tmp_path / "fps.json").exists()


def test_arquivo_corrompido_nao_derruba_a_migracao(tmp_path: Path) -> None:
    """Best-effort: um JSON quebrado não pode impedir os outros de migrarem."""
    (tmp_path / "acao.json").write_text("{ isto não é json", encoding="utf-8")
    fps = _escreve(tmp_path, "fps", {"name": "FPS", "priority": 60, "mode": None})

    migrados = loader.migrate_modo_jogo_nos_presets(dest_dir=tmp_path)

    assert "fps.json" in migrados
    assert _le(fps)["mode"] is not None
