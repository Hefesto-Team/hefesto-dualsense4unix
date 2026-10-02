"""MODO-01 — a sprint precisa alcançar quem JÁ tem o Hefesto instalado."""
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
    """A regra que torna a migração segura: onde ela mexeu, recua."""
    escolha = {"kind": "native"}
    fps = _escreve(tmp_path, "fps", {"name": "FPS", "priority": 60,
                                     "mode": dict(escolha)})

    loader.migrate_modo_jogo_nos_presets(dest_dir=tmp_path)

    assert _le(fps)["mode"] == escolha


def test_o_ramo_do_coop_local_esta_aposentado_e_relata(tmp_path: Path) -> None:
    """NOTA DATADA — 26/08/2026: o ramo `coop_local` desta migração aposentou."""
    import structlog.testing

    coop = _escreve(tmp_path, "coop_local", {"name": "Co-op local", "priority": 45,
                                             "mode": {"kind": "gamepad"}})

    with structlog.testing.capture_logs() as registros:
        loader.migrate_modo_jogo_nos_presets(dest_dir=tmp_path)

    assert _le(coop)["priority"] == 45, (
        "a migração aposentada escreveu prioridade sem asset de onde copiá-la"
    )
    assert [
        r for r in registros
        if r.get("event") == "migracao_aposentada_sem_asset"
        and r.get("arquivo") == "coop_local.json"
    ], (
        "a migração virou no-op SILENCIOSO. Eventos vistos: "
        f"{sorted({str(r.get('event')) for r in registros})}"
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
