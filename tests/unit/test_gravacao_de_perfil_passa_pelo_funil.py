"""GRAVA-POR-UM-FUNIL-01 — o rodapé grava e o rascunho não fica sabendo (04/08)."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("funil de gravação de perfil")

import ast
import json
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import footer_actions
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchCriteria,
    Profile,
)

_SRC = Path(__file__).resolve().parents[2] / "src"
_APP = _SRC / "hefesto_dualsense4unix" / "app"

_PRIORIDADE_DO_PRIMEIRO_SAVE = 10
_PRIORIDADE_DA_CATRACA = 20


@pytest.fixture(autouse=True)
def _sync_run_in_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """Roda ``ipc_bridge.run_in_thread`` de forma síncrona (sem loop GTK)."""

    def _sync(fn: Any, on_success: Any, on_failure: Any = None) -> None:
        try:
            resultado = fn()
        except Exception as exc:
            if on_failure is not None:
                on_failure(exc)
            return
        on_success(resultado)

    monkeypatch.setattr(footer_actions.ipc_bridge, "run_in_thread", _sync)


@pytest.fixture
def disco(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Diretório de perfis isolado — o disco de verdade, num tmp."""
    import hefesto_dualsense4unix.profiles.loader as loader_mod

    destino = tmp_path / "profiles"
    destino.mkdir()
    monkeypatch.setattr(loader_mod, "profiles_dir", lambda ensure=False: destino)
    return destino


def _perfil_do_jogo(nome: str = "Pragmata") -> Profile:
    """Perfil com REGRA de janela e prioridade alta — o que ela tem em disco."""
    return Profile(
        name=nome,
        match=MatchCriteria(window_class=["steam_app_3357650"]),
        priority=60,
        leds=LedsConfig(lightbar=(97, 53, 131)),
    )


def _perfil_em_disco(disco: Path, slug: str) -> dict[str, Any]:
    return json.loads((disco / f"{slug}.json").read_text(encoding="utf-8"))


#: ``_reconciliar_rascunho_com_perfil_salvo``. Convertê-la é trabalho de outra
_AUTORIZADOS_A_GRAVAR = {
    "actions/profile_writer.py",
    "actions/profiles_actions.py",
}


def _chamadas_a_save_profile(caminho: Path) -> list[int]:
    """Linhas em que ``caminho`` CHAMA ``save_profile`` (AST, não texto)."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    linhas: list[int] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        alvo = no.func
        if isinstance(alvo, ast.Name):
            nome = alvo.id
        elif isinstance(alvo, ast.Attribute):
            nome = alvo.attr
        else:
            continue
        if nome == "save_profile":
            linhas.append(no.lineno)
    return linhas


def test_nenhuma_gravacao_de_perfil_fora_do_funil() -> None:
    """O pedido central da mantenedora, em forma de portão."""
    ofensores: dict[str, list[int]] = {}
    for caminho in sorted(_APP.rglob("*.py")):
        relativo = caminho.relative_to(_APP).as_posix()
        if relativo in _AUTORIZADOS_A_GRAVAR:
            continue
        linhas = _chamadas_a_save_profile(caminho)
        if linhas:
            ofensores[relativo] = linhas

    assert ofensores == {}, (
        "gravação de perfil fora do funil (GRAVA-POR-UM-FUNIL-01): "
        f"{ofensores} — use `self._gravar_perfil_async(...)` de "
        "`app/actions/profile_writer.py`, que grava E reaponta o rascunho"
    )


def test_a_lista_de_autorizados_nao_cresce_em_silencio() -> None:
    """A exceção da aba Perfis é datada; a lista só pode encolher."""
    assert sorted(_AUTORIZADOS_A_GRAVAR) == [
        "actions/profile_writer.py",
        "actions/profiles_actions.py",
    ]


def test_o_funil_carimba_a_origem_da_gravacao() -> None:
    """Toda gravação da janela diz de ONDE veio, no journal."""
    texto = (_APP / "actions/profile_writer.py").read_text(encoding="utf-8")
    assert "save_profile(profile, origem=" in texto, (
        "o funil grava sem dizer de onde veio — o `profile_salvo` do journal "
        "perde o único campo que distingue um botão do outro"
    )
    assert "janela:" in texto, (
        "a origem precisa identificar a JANELA, não só o processo: o basename "
        "do argv[0] é igual para todos os botões"
    )
