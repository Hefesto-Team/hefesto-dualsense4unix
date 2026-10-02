"""A-TELA-PROMETE-PAREAR-01 — a frase que oferecia o que o produto não faz."""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
GERADOR = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "pagina_do_mapa.py"
BANCADA = RAIZ / "mockup" / "mapa-das-portas.html"
PUBLICADO = (
    RAIZ
    / "src"
    / "hefesto_dualsense4unix"
    / "interface"
    / "paginas"  # noqa-acento: nome da pasta no disco, não prosa
    / "mapa-das-portas.html"
)
CONGELADO = RAIZ / "mockup" / "congelados" / "2026-08-24-mapa-das-portas.html"

PROMESSA = "pareia de novo no adaptador certo — sem terminal"


def test_o_congelado_ainda_tem_a_promessa() -> None:
    assert PROMESSA in CONGELADO.read_text(encoding="utf-8"), (
        "a promessa sumiu da origem congelada — ou alguém reescreveu o "
        "congelado (o que a decisão proíbe), ou a Edicao perdeu o alvo."
    )


def test_a_promessa_saiu_da_bancada_e_do_publicado() -> None:
    for arquivo in (BANCADA, PUBLICADO):
        texto = arquivo.read_text(encoding="utf-8")
        assert PROMESSA not in texto, (
            f"{arquivo.name} ainda oferece parear sem terminal — e o botão não "
            "existe. Rode o gerador e publique."
        )


LISTA_DE_MOVER = "no adaptador errado"


def test_o_texto_novo_diz_o_que_ha_hoje() -> None:
    """Onde a página propõe mover um controle, ela diz o caminho de hoje."""
    assert LISTA_DE_MOVER in CONGELADO.read_text(encoding="utf-8")
    for arquivo in (BANCADA, PUBLICADO):
        texto = re.sub(r"\s+", " ", arquivo.read_text(encoding="utf-8"))
        if LISTA_DE_MOVER not in texto:
            continue
        assert "gesto de terminal" in texto, (
            f"{arquivo.name}: a promessa saiu mas nada entrou no lugar — a "
            "pessoa fica sem saber como mover o controle."
        )
        assert "bluetooth-varios-adaptadores" in texto, (
            f"{arquivo.name}: o texto novo não diz ONDE está o passo a passo. "
            "Tirar a promessa e não apontar o caminho troca um defeito por outro."
        )


def test_a_edicao_esta_no_gerador_e_nao_so_no_html() -> None:
    texto = GERADOR.read_text(encoding="utf-8")
    assert "A-TELA-PROMETE-PAREAR-01" in texto, (
        "a correção não está no gerador — a próxima geração do "
        "mapa-das-portas devolve a promessa."
    )


def test_a_tela_so_promete_o_que_tem_chamador() -> None:
    ponte_ligada = bool(
        list((RAIZ / "src").rglob("*.py"))
        and [
            p
            for p in (RAIZ / "src").rglob("*.py")
            if "bt_ponte_privilegiada" in p.read_text(encoding="utf-8", errors="ignore")
        ]
    )
    texto = PUBLICADO.read_text(encoding="utf-8")
    if ponte_ligada:
        return
    assert PROMESSA not in texto, (
        "a tela promete parear e NENHUM Python chama a ponte "
        "(`bt_ponte_privilegiada` não aparece em src/). Ver PONTE-SEM-CHAMADOR-01."
    )
