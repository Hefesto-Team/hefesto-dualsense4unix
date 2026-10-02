"""PALAVRA-01 — a janela fala a língua de quem joga."""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PACOTE = RAIZ / "src" / "hefesto_dualsense4unix"
EMULACAO_PY = PACOTE / "app" / "actions" / "emulation_actions.py"
MOUSE_PY = PACOTE / "app" / "actions" / "mouse_actions.py"
GATILHOS_PY = PACOTE / "app" / "actions" / "trigger_specs.py"

CONTROLES_INTERATIVOS_ESPERADOS = 82
COBERTURA_MINIMA_DE_TOOLTIP = 82

_TAG_MARKUP = re.compile(r"<[^>]*>")
_PRIMEIRA_LETRA = re.compile(r"[^\W\d_]", re.UNICODE)


_TABELAS_DE_ROTULO: tuple[str, ...] = ("_MIC_ROTULOS",)


def _textos_de_tela(caminho: Path) -> list[str]:
    """Strings do módulo que chegam ao rótulo — por markup ou por tabela."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    achados: list[str] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Constant) and isinstance(no.value, str):
            achados.append(no.value)
        elif isinstance(no, ast.JoinedStr):
            achados.append(
                "".join(
                    parte.value
                    for parte in no.values
                    if isinstance(parte, ast.Constant) and isinstance(parte.value, str)
                )
            )
    com_markup = [t for t in achados if "<span" in t and ">" in t.split("<span", 1)[1]]
    return com_markup + _textos_das_tabelas(arvore)


def _textos_das_tabelas(arvore: ast.AST) -> list[str]:
    """O texto CURTO de cada estado nas tabelas de rótulo."""
    achados: list[str] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.AnnAssign | ast.Assign):
            continue
        alvos = [no.target] if isinstance(no, ast.AnnAssign) else no.targets
        nomes = {a.id for a in alvos if isinstance(a, ast.Name)}
        if not (nomes & set(_TABELAS_DE_ROTULO)):
            continue
        valor = no.value
        if not isinstance(valor, ast.Dict):
            continue
        for item in valor.values:
            if not isinstance(item, ast.Tuple) or len(item.elts) < 2:
                continue
            texto = item.elts[1]
            if isinstance(texto, ast.Constant) and isinstance(texto.value, str):
                achados.append(texto.value)
    return achados


def _sem_markup(texto: str) -> str:
    return _TAG_MARKUP.sub("", texto).strip()


def _comeca_em_minuscula(texto: str) -> bool:
    m = _PRIMEIRA_LETRA.search(texto)
    return m is not None and m.group(0).islower()


@pytest.mark.parametrize("arquivo", [EMULACAO_PY, MOUSE_PY], ids=["emulacao", "mouse"])
def test_texto_de_estado_nao_comeca_em_minuscula(arquivo: Path) -> None:
    """Ela lê "ligado"/"desligado"/"daemon offline" no meio de uma frase."""
    culpados = [
        _sem_markup(t) for t in _textos_de_tela(arquivo) if _comeca_em_minuscula(_sem_markup(t))
    ]
    assert culpados == [], (
        f"{arquivo.name}: texto de tela começando em minúscula: {culpados}"
    )


def test_os_estados_de_hoje_estao_escritos_como_frase() -> None:
    """Trava, um a um, os textos que a sprint listou por nome."""
    emulacao = [_sem_markup(t) for t in _textos_de_tela(EMULACAO_PY)]
    mouse = [_sem_markup(t) for t in _textos_de_tela(MOUSE_PY)]

    assert "Ligado" in emulacao
    assert "Desligado" in emulacao
    assert "Desligado (suprimido)" in emulacao
    assert "O Hefesto está em pausa" in emulacao
    assert "O Hefesto está desligado" in emulacao
    assert any(t.startswith("Desligado — emulação normal") for t in emulacao)
    assert any(t.startswith("Conexão Nativa (Sony)") for t in emulacao)
    assert any(t.startswith("Ligado —") for t in emulacao)

    assert "Pronto para usar como mouse" in mouse
    assert any(t.startswith("O mouse virtual está sem permissão") for t in mouse)
    assert any(t.startswith("O mouse virtual ainda não está pronto") for t in mouse)
    assert any(t.startswith("Falta um componente do mouse virtual") for t in mouse)


def _rotulos_de_gatilho() -> list[str]:
    from hefesto_dualsense4unix.app.actions.trigger_specs import PRESETS

    rotulos = [spec.label for spec in PRESETS]
    for spec in PRESETS:
        rotulos.extend(p.label for p in spec.params)
    return rotulos


def test_gatilhos_nao_mostram_jargao_em_ingles() -> None:
    """"start+1..8" e "raw HID" estavam dentro de uma janela em português."""
    banidos = ("start+1", "raw HID", "Mode HID", "Force ", "Pos ")
    culpados = [r for r in _rotulos_de_gatilho() if any(b in r for b in banidos)]
    assert culpados == [], f"rótulo de gatilho ainda em jargão: {culpados}"


def test_o_arquivo_de_gatilhos_nao_guarda_mais_o_texto_antigo() -> None:
    """Portão de fonte: o texto banido não pode voltar nem em outro preset."""
    fonte = GATILHOS_PY.read_text(encoding="utf-8")
    for proibido in ("start+1..8", "raw HID"):
        assert proibido not in fonte, f"voltou ao trigger_specs.py: {proibido}"
