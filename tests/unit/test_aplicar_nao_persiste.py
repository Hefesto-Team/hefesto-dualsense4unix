"""APLICAR-NAO-PERSISTE-01 — o botão que a documentação dizia que salvava."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PAGINA_DAS_ABAS = REPO_ROOT / "docs" / "usage" / "AS-DEZ-ABAS-o-que-cada-uma-faz.md"
FOOTER_ACTIONS_PY = (
    REPO_ROOT / "src" / "hefesto_dualsense4unix" / "app" / "actions" / "footer_actions.py"
)

GRAVACOES = (
    r"\bsave_profile\s*\(",
    r"\b_gravar_perfil_async\s*\(",
    r"\b_persist_profile_async\s*\(",
    r"\.write_text\s*\(",
    r"\.write_bytes\s*\(",
    r"\bjson\.dump\s*\(",
    r"\bshutil\.(copy|move)",
    r"\bopen\s*\([^)]*[\"'][wax]",
)


def test_o_documento_nao_promete_persistencia_no_aplicar() -> None:
    texto = PAGINA_DAS_ABAS.read_text(encoding="utf-8")
    assert not re.search(
        r"\*\*Aplicar\*\*.{0,120}persistem o que está editado",
        texto,
        re.DOTALL,
    ), (
        "a tabela dos botões voltou a dizer que o Aplicar persiste — ele despacha "
        "`profile.apply_draft` pelo IPC e não abre arquivo nenhum"
    )
    assert "**Salvar Perfil**" in texto, (
        "o documento tem de nomear quem realmente salva; dizer só o que o Aplicar "
        "NÃO faz deixa a pergunta sem resposta"
    )
