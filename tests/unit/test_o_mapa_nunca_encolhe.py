"""O mapa de canais NUNCA encolhe, e o piso é dado, não palpite.

Em 05/09/2026 um script desta casa apagou 104 linhas do mapa num comando só.
Era `scripts/migrar-mapa-v2.py`: ele rodou uma vez, em 11/08, e rodá-lo de novo
lia o retrato congelado daquele dia (204 linhas) e escrevia **264 linhas por
cima das 308** — sem backup, porque o guardado já existia, e imprimindo
`prova: nenhum campo do v1 se perdeu`, que comparava o v2 recém-montado com o v1
que o gerou e nunca olhava o destino.

O que se perderia: o trabalho de cerca de trezentos agentes que leram os
repositórios externos, mais a validação ao vivo na bancada dela.

    "Não podemos perder ou regenerar errado isso e desconsiderar o excelente
     trabalho deles."  — ela, 05/09/2026

**A primeira cura foi uma trava no script; ela foi trocada pela cura dela.** A
razão, nas palavras dela no mesmo dia: *"a ideia é termos menos arquivos, se
algo vira a v2 deveria ser o mesmo arquivo sobrescrevendo o anterior"*. Um
migrador de uma vez só que já rodou é arma descarregada: não se tranca, apaga-se.
O script e os dois retratos congelados saíram do disco; o git os guarda em
`6ca1417d`, e a medição que justificou o formato v2 está em
`docs/data/LEIA-PRIMEIRO.md`.

Esta régua é o que SOBREVIVE aos três: ela não sabe o nome de nenhum script.
Pergunta só ao mapa se ele continua sendo o que era, e reprova se alguém —
script novo, edição em massa, merge torto — o fizer encolher.
"""
from __future__ import annotations

import csv
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"

#: O piso, medido em 05/09/2026. Ele SOBE quando o mapa crescer — nunca desce
#: sem uma linha datada aqui dizendo o que foi retirado e por quem.
PISO_DE_LINHAS = 308

#: As colunas que o grão `(chave, controle)` exige. Perder qualquer uma é ter
#: voltado a um formato anterior.
COLUNAS_DO_GRAO = ("chave", "controle", "cabo_de_onde_sei", "radio_de_onde_sei")


def _mapa() -> tuple[list[str], list[dict]]:
    with open(MAPA, encoding="utf-8", newline="") as fh:
        leitor = csv.DictReader(fh)
        return list(leitor.fieldnames or []), list(leitor)


def test_o_mapa_nao_encolheu():
    _, linhas = _mapa()
    assert len(linhas) >= PISO_DE_LINHAS, (
        f"o mapa tem {len(linhas)} linhas e o piso é {PISO_DE_LINHAS}. "
        "Alguém regenerou por cima do trabalho dos agentes. NÃO baixe este "
        "número para ficar verde: descubra o que apagou as linhas."
    )


def test_o_grao_continua_sendo_chave_por_controle():
    cabecalho, _ = _mapa()
    faltando = [c for c in COLUNAS_DO_GRAO if c not in cabecalho]
    assert not faltando, (
        f"o mapa perdeu as colunas {faltando}: o formato regrediu para um "
        "anterior ao de 11/08/2026"
    )
    assert cabecalho[0] == "chave", (
        f"a primeira coluna é {cabecalho[0]!r} e devia ser 'chave' — no formato "
        "antigo ela era 'id', então isto é um mapa de antes da migração"
    )


def test_o_trabalho_dos_agentes_continua_no_mapa():
    """As referências de código que eles preencheram são o lastro das inferências."""
    _, linhas = _mapa()
    com_ref = sum(
        1
        for lin in linhas
        for lado in ("cabo", "radio")
        if (lin.get(f"{lado}_codigo_ref") or "").strip()
    )
    assert com_ref >= 500, (
        f"só {com_ref} células citam arquivo em `codigo_ref`, e eram 507 em "
        "05/09/2026. É por essa coluna que o `specs.html` conta quantas "
        "inferências o driver do kernel sustenta — perdê-la é desconsiderar o "
        "trabalho dos agentes de novo."
    )


def test_o_migrador_de_uma_vez_so_nao_voltou():
    """Ele apagava 104 linhas num comando. Se alguém o recriar, esta régua avisa."""
    morto = RAIZ / "scripts" / "migrar-mapa-v2.py"
    assert not morto.exists(), (
        "`scripts/migrar-mapa-v2.py` voltou ao disco. Ele é um migrador de uma "
        "vez só que JÁ RODOU em 11/08/2026, e rodá-lo de novo escreve o retrato "
        "daquele dia por cima do mapa de hoje. Se a intenção é outra migração, "
        "ela precisa de nome próprio e de ler o mapa de HOJE como fonte."
    )
