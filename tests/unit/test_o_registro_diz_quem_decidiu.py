"""O registro de decisões diz QUEM decidiu, e a delegação não revoga calada."""
from __future__ import annotations

import csv
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CSV_ = RAIZ / "docs" / "data" / "decisoes-dela.csv"

VALORES = {"ela", "delegacao", "indeterminado"}

MARCA_INDETERMINADO = "QUEM DECIDIU: INDETERMINADO"
MARCA_ELA = "QUEM DECIDIU: ELA"

LOTE_DE_04_09 = "as 54 levantadas em 04/09"


def _linhas() -> list[dict[str, str]]:
    with CSV_.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_a_coluna_quem_decidiu_existe() -> None:
    """MORDE: apagar a coluna `quem_decidiu` do cabeçalho."""
    linhas = _linhas()
    assert linhas, "o registro está vazio"
    for coluna in ("quem_decidiu", "revoga"):
        assert coluna in linhas[0], (
            f"a coluna `{coluna}` sumiu de {CSV_.name}. Sem ela o registro "
            "volta a guardar 'decisão dela' e 'decisão em nome dela' na mesma "
            "coluna, que é o defeito medido em 05/09/2026"
        )


def test_toda_linha_diz_quem_decidiu() -> None:
    """A régua da tarefa: linha sem `quem_decidiu` reprova, nomeada."""
    orfas = []
    invalidas = []
    for d in _linhas():
        valor = (d.get("quem_decidiu") or "").strip()
        if not valor:
            orfas.append(d["id"])
        elif valor not in VALORES:
            invalidas.append((d["id"], valor))

    assert not orfas, (
        "estas decisões não dizem quem as decidiu — quem ler amanhã não sabe o "
        f"que pode reabrir: {orfas}"
    )
    assert not invalidas, (
        "`quem_decidiu` só aceita "
        f"{sorted(VALORES)}, e estas linhas dizem outra coisa: {invalidas}"
    )


def test_a_delegacao_cita_o_mandato() -> None:
    """Delegação sem procedência é palavra solta."""
    sem_mandato = [
        d["id"]
        for d in _linhas()
        if d["quem_decidiu"] == "delegacao" and "DELEGAÇÃO" not in d["escolha"]
    ]
    assert not sem_mandato, (
        "estas linhas dizem `delegacao` e não citam o mandato que a autorizou "
        "(os três estão em docs/process/2026-09-04-O-PO-DECIDE-as-54-e-os-"
        f"sete-conflitos.md:9-14): {sem_mandato}"
    )


def test_o_indeterminado_diz_por_que_nao_se_sabe() -> None:
    """Não saber é resposta legítima; não saber calado, não."""
    sem_razao = [
        d["id"]
        for d in _linhas()
        if d["quem_decidiu"] == "indeterminado"
        and MARCA_INDETERMINADO not in d["escolha"]
    ]
    assert not sem_razao, (
        f"estas linhas dizem `indeterminado` sem o carimbo `{MARCA_INDETERMINADO}` "
        f"e a razão datada na `escolha`: {sem_razao}"
    )


def test_o_revoga_aponta_decisao_que_existe() -> None:
    """Ponteiro para id inexistente é lápide sobre cova errada."""
    linhas = _linhas()
    ids = {d["id"] for d in linhas}
    quebrados = []
    for d in linhas:
        alvos = [a for a in (d.get("revoga") or "").split("|") if a.strip()]
        for alvo in alvos:
            alvo = alvo.strip()
            if alvo not in ids:
                quebrados.append((d["id"], alvo, "id não existe"))
            elif alvo == d["id"]:
                quebrados.append((d["id"], alvo, "revoga a si mesma"))
    assert not quebrados, f"a coluna `revoga` aponta para o vazio: {quebrados}"


def test_quem_revoga_nomeia_o_revogado_na_prosa() -> None:
    """A lápide tem de ser legível por quem lê, não só pela máquina."""
    mudos = []
    for d in _linhas():
        alvos = [a.strip() for a in (d.get("revoga") or "").split("|") if a.strip()]
        for alvo in alvos:
            if alvo not in d["escolha"]:
                mudos.append((d["id"], alvo))
    assert not mudos, (
        "estas linhas revogam outra decisão e não a nomeiam na `escolha` — a "
        f"revogação fica calada para quem lê: {mudos}"
    )


def test_o_lote_de_04_09_so_vira_dela_com_a_prova() -> None:
    """As 54 nasceram por delegação; virar uma para `ela` exige mostrar a prova."""
    lote = [d for d in _linhas() if d["nasceu_de"].startswith(LOTE_DE_04_09)]
    assert len(lote) == 54, (
        "instrumento inválido: o lote de 04/09 tinha 54 linhas e agora tem "
        f"{len(lote)}"
    )
    sem_prova = [
        d["id"]
        for d in lote
        if d["quem_decidiu"] == "ela" and MARCA_ELA not in d["escolha"]
    ]
    assert not sem_prova, (
        "estas linhas do lote de 04/09 dizem `ela` sem o carimbo "
        f"`{MARCA_ELA}` com a palavra dela na `escolha`: {sem_prova}"
    )
