"""A-TELA-PROMETE-PAREAR-01 — a frase que oferecia o que o produto não faz.

O `mapa-das-portas` dizia, ao propor mover um controle de adaptador:

    «o Hefesto desfaz o pareamento antigo, limpa o que ficou para trás e
     pareia de novo no adaptador certo — sem terminal, com o controle na mão.»

**Nenhuma linha de Python jamais chamou a ponte** (`grep -rn
bt_ponte_privilegiada src/` devolve zero), e os 18 gestos da aba Conexões não
tocam em pareamento. A tela oferecia um botão que não existe.

Regra desta casa: *fato errado se SUBSTITUI, e sai de TODOS os lugares onde
aparece.* Aqui são três: o gerador, a bancada e o publicado.
"""

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
    # A origem congelada NÃO se reescreve — ela é o registro de como o motor
    # falava em 24/08/2026, e o ouro de 120 cenários se apoia nela. A cura é
    # uma Edicao sobre ela, e este teste é o que garante que a `antes` da
    # edição continua tendo alvo: zero ocorrências aqui e a troca envelheceu
    # calada.
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


def test_o_texto_novo_diz_o_que_ha_hoje() -> None:
    for arquivo in (BANCADA, PUBLICADO):
        texto = re.sub(r"\s+", " ", arquivo.read_text(encoding="utf-8"))
        assert "gesto de terminal" in texto, (
            f"{arquivo.name}: a promessa saiu mas nada entrou no lugar — a "
            "pessoa fica sem saber como mover o controle."
        )
        assert "GUIA-RADIO-DA-SALA" in texto, (
            f"{arquivo.name}: o texto novo não diz ONDE está o passo a passo. "
            "Tirar a promessa e não apontar o caminho troca um defeito por outro."
        )


def test_a_edicao_esta_no_gerador_e_nao_so_no_html() -> None:
    # Editar o HTML à mão é o defeito que esta casa já pagou: a próxima corrida
    # do gerador desfaz tudo, calada.
    texto = GERADOR.read_text(encoding="utf-8")
    assert "A-TELA-PROMETE-PAREAR-01" in texto, (
        "a correção não está no gerador — a próxima geração do "
        "mapa-das-portas devolve a promessa."
    )


def test_a_tela_so_promete_o_que_tem_chamador() -> None:
    # A régua que impede a PRÓXIMA frase de repetir o defeito: se algum dia
    # alguém ligar a ponte, este teste cai e a promessa pode voltar — de
    # propósito.
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
        return  # alguém ligou a ponte: a promessa deixou de ser falsa.
    assert PROMESSA not in texto, (
        "a tela promete parear e NENHUM Python chama a ponte "
        "(`bt_ponte_privilegiada` não aparece em src/). Ver PONTE-SEM-CHAMADOR-01."
    )
