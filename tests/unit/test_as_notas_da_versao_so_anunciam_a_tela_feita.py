"""As notas da versão só anunciam a tela que foi feita: o bloco `publico` que nomeia uma aba
sai da seção quando o relato diz que a sprint fechou sem tela."""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]
CHANGELOG = RAIZ / "scripts" / "release" / "changelog.py"


def _changelog() -> Any:
    spec = importlib.util.spec_from_file_location("changelog_da_tela_feita", CHANGELOG)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _sprint(raiz: Path, ident: str, muda: str, feito: str) -> None:
    pasta = raiz / "docs" / "process" / "sprints"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"2026-10-07-{ident}.md").write_text(
        f"---\nsprint: {ident}\nestado: feita\n# fechada 07/10/2026: 3 commits\n"
        "ensaio: false\n---\n\n"
        f"# {ident}\n\n```publico\ntitulo: Os toques da vibração\ntipo: adicionado\narea: som\n"
        f"muda: {muda}\npronto: Abra a janela e veja.\n```\n\n"
        f"## O que foi feito (07/10/2026)\n\n{feito}\n",
        encoding="utf-8",
    )


def _entram(raiz: Path) -> tuple[list[str], list[str]]:
    avisos: list[str] = []
    achados = _changelog().do_sprints(raiz, dt.date(2026, 10, 1), avisos)
    return [texto for _grupo, texto in achados], avisos


@pytest.mark.parametrize("feito", ["Só o motor. Sem tela.", "Sem cartão nem tela (item 49)."])
def test_a_sprint_que_nomeia_a_aba_e_fechou_sem_tela_fica_fora_e_vai_ao_aviso(
    tmp_path: Path, feito: str
) -> None:
    """D-2511-A-NOTA-DE-VERSAO-DIZ-SO-O-QUE-MUDA-PARA-QUEM-USA: sem tela, fica fora."""
    _sprint(tmp_path, "COM-ABA-01", "Na aba Vibração, cada perfil escolhe os toques.", feito)
    entram, avisos = _entram(tmp_path)
    assert entram == []
    assert any("COM-ABA-01" in aviso and "sem tela" in aviso for aviso in avisos), avisos


def test_a_mesma_sprint_com_a_tela_feita_entra(tmp_path: Path) -> None:
    """D-2511-A-NOTA-DE-VERSAO-DIZ-SO-O-QUE-MUDA-PARA-QUEM-USA: com a tela, entra."""
    _sprint(
        tmp_path,
        "COM-ABA-01",
        "Na aba Vibração, cada perfil escolhe os toques.",
        "A aba mostra a escolha.",
    )
    entram, avisos = _entram(tmp_path)
    assert entram == ["- Na aba Vibração, cada perfil escolhe os toques."], avisos


def test_o_texto_que_nao_nomeia_aba_entra_mesmo_com_o_relato_sem_tela(tmp_path: Path) -> None:
    """D-2511-A-NOTA-DE-VERSAO-DIZ-SO-O-QUE-MUDA-PARA-QUEM-USA: sem aba, entra."""
    _sprint(
        tmp_path, "SEM-ABA-01", "O perfil guarda os toques de cada jogo.", "Só o motor. Sem tela."
    )
    entram, _avisos = _entram(tmp_path)
    assert entram == ["- O perfil guarda os toques de cada jogo."]
