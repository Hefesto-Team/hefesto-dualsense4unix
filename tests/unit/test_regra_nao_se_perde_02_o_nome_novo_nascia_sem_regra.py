"""REGRA-NAO-SE-PERDE-02 — o nome NOVO nascia sem regra nenhuma (05/08/2026)."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("herança de regra no rodapé (REGRA-NAO-SE-PERDE-02)")

import ast
from pathlib import Path

from hefesto_dualsense4unix.profiles.schema import (
    Profile,
)

from tests.unit.test_gravacao_de_perfil_passa_pelo_funil import _perfil_em_disco
from tests.unit.test_gravacao_de_perfil_passa_pelo_funil import (
    disco as _disco_da_sprint_01,
)

disco = _disco_da_sprint_01

_SRC = Path(__file__).resolve().parents[2] / "src"
_FOOTER = _SRC / "hefesto_dualsense4unix" / "app" / "actions" / "footer_actions.py"

_WM_CLASS_DO_RASCUNHO = "steam_app_3357650"
_WM_CLASS_DO_SACKBOY = "steam_app_1599660"


def _gravado(disco: Path, slug: str) -> Profile:
    """O perfil como ele ficou NO DISCO, revalidado pelo esquema."""
    return Profile.model_validate(_perfil_em_disco(disco, slug))


def _chamadas_a(fonte: Path, nome: str) -> list[int]:
    """Linhas em que ``nome(...)`` é CONSTRUÍDO em ``fonte``."""
    arvore = ast.parse(fonte.read_text(encoding="utf-8"))
    linhas: list[int] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        alvo = no.func
        chamado = (
            alvo.id
            if isinstance(alvo, ast.Name)
            else alvo.attr
            if isinstance(alvo, ast.Attribute)
            else None
        )
        if chamado == nome:
            linhas.append(no.lineno)
    return linhas


def test_o_rodape_nao_constroi_catch_all_por_conta_propria() -> None:
    """Nenhum ``MatchAny(`` dentro de ``footer_actions.py``."""
    ofensoras = _chamadas_a(_FOOTER, "MatchAny")

    assert ofensoras == [], (
        f"footer_actions.py constrói MatchAny() nas linhas {ofensoras} — o "
        "rodapé não tem campo de regra, então um catch-all nascido aqui é "
        "sempre um perfil invisível dentro do jogo e soberano fora dele "
        "(REGRA-NAO-SE-PERDE-02). O ramo sem origem usa MatchManual()"
    )


def test_o_portao_enxerga_a_construcao_que_ele_veta(tmp_path: Path) -> None:
    """O portão acima morde? Um fonte-canário responde, sem tocar no produto."""
    canario = tmp_path / "canario.py"
    canario.write_text(
        "from x import MatchAny, schema\n"
        '"""Docstring que cita MatchAny() e NÃO pode acusar."""\n'
        "a = MatchAny()\n"
        "b = schema.MatchAny()\n",
        encoding="utf-8",
    )

    assert _chamadas_a(canario, "MatchAny") == [3, 4]


