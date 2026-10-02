"""RADIO-ABERTO-01/E7+E9 — o portão da política do core dump."""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
POLITICA = REPO_ROOT / "docs" / "method" / "POLITICA-core-nunca-sai-da-maquina.md"

RAIZES = (REPO_ROOT / "docs", REPO_ROOT / "scripts")
EXTENSOES = (".md", ".sh", ".py")

_VERBOS = (
    r"\b(?:anex\w*|envi\w*|mand\w*|compartilh\w*|attach\w*|upload\w*|submit\w*)\b"
)
_CORE = r"\bcore(?:\s*-?\s*dumps?)?\b(?!\s*/)"
_INSTRUCOES = re.compile(rf"{_VERBOS}[^.\n]{{0,40}}?{_CORE}", re.IGNORECASE)

_MARCA_DA_POLITICA = re.compile(
    r"(RADIO-ABERTO-01|POLITICA-core-nunca-sai-da-maquina|"
    r"core.{0,30}nunca sai)",
    re.IGNORECASE,
)


def _arquivos_varridos() -> list[Path]:
    achados: list[Path] = []
    for raiz in RAIZES:
        for caminho in raiz.rglob("*"):
            if caminho.is_file() and caminho.suffix in EXTENSOES:
                achados.append(caminho)
    return achados


def test_a_politica_existe_e_diz_o_essencial() -> None:
    """E7 — a política escrita, não combinada de boca."""
    assert POLITICA.exists(), (
        "a política do core sumiu — ela é a única coisa entre um relatório "
        "upstream e a publicação das chaves de rádio dela"
    )
    texto = POLITICA.read_text(encoding="utf-8")
    assert "coredumpctl info" in texto, "a política tem de dizer O QUE enviar no lugar"
    assert "LinkKey" in texto, "a política tem de dizer o que o core contém"
    assert "nunca sai" in texto.lower()


def test_ninguem_instrui_a_enviar_o_core() -> None:
    """E9 — o portão. Instrução de envio só acompanhada da política."""
    violacoes: list[str] = []
    for caminho in _arquivos_varridos():
        texto = caminho.read_text(encoding="utf-8", errors="replace")
        if not _INSTRUCOES.search(texto):
            continue
        if _MARCA_DA_POLITICA.search(texto):
            continue
        for numero, linha in enumerate(texto.splitlines(), start=1):
            if _INSTRUCOES.search(linha):
                violacoes.append(
                    f"{caminho.relative_to(REPO_ROOT)}:{numero}: {linha.strip()[:100]}"
                )
    assert not violacoes, (
        "documento(s) instruindo a enviar um core sem trazer a política junto.\n"
        "Um core do bluetoothd carrega todas as LinkKeys, LTKs e IRKs da casa.\n"
        "Para upstream vai o BACKTRACE (coredumpctl info), nunca o core.\n"
        + "\n".join(violacoes)
    )


def test_o_script_de_captura_nao_manda_abrir_o_core_sem_avisar() -> None:
    """O `--on` é o ponto onde ela lê a instrução — a política tem de estar lá."""
    texto = (REPO_ROOT / "scripts" / "bt_crash_capture.sh").read_text(encoding="utf-8")
    assert "coredumpctl info" in texto, (
        "o script sugere o caminho de análise, e o que vai para upstream é o "
        "backtrace — `coredumpctl info`, não o core"
    )
    assert "NUNCA sai desta máquina" in texto, (
        "quem liga a janela de captura precisa ler a política ali mesmo"
    )


def test_a_janela_de_captura_arma_o_proprio_desligamento() -> None:
    """E8 — `core_pattern` é global; o `--off` não pode depender da memória."""
    texto = (REPO_ROOT / "scripts" / "bt_crash_capture.sh").read_text(encoding="utf-8")
    assert "systemd-run" in texto and "--on-active" in texto, (
        "o --on tem de armar o próprio --off por timer: uma janela esquecida "
        "aberta deixa a máquina gravando core de todo processo que morrer"
    )
    assert re.search(r'--unit="\$\{AUTO_OFF_UNIT\}"', texto), (
        "o timer precisa de nome fixo, senão ligar duas vezes acumula timers"
    )
    assert 'systemctl stop "${AUTO_OFF_UNIT}.timer"' in texto, (
        "o --off manual tem de desarmar o timer pendente"
    )
