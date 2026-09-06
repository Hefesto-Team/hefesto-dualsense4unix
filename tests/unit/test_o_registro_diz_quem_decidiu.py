"""O registro de decisões diz QUEM decidiu, e a delegação não revoga calada.

**NASCEU DE UM DEFEITO MEDIDO EM 05/09/2026**, e o laudo que o nomeia é
`docs/process/2026-09-05-POR-QUE-A-FILA-REPETE-a-queixa-dela-medida.md`, §5:

    "Decisão dela" e "decisão tomada em nome dela" moram na mesma coluna do
    mesmo arquivo, então uma delegação de terça revoga uma palavra dela de
    segunda sem que ninguém veja.

Aconteceu três vezes num dia — o cadeado (26/08 → 04/09), o botão de reenvio
(27/08 → 04/09) e o preço da máscara Xbox (31/08 → 04/09). Nos três a palavra
dela estava no disco, datada, e foi atropelada por uma decisão do PO que tinha
o **mesmo formato de linha**. O conserto proposto no §6 do laudo (C1 e C2) é o
que este arquivo prende: duas colunas, `quem_decidiu` e `revoga`.

O QUE A RÉGUA COBRA, e por quê:

1. **Toda linha diz quem decidiu.** Ausência calada é o defeito inteiro.
2. **`delegacao` cita o mandato.** Os três mandatos dela estão tabelados em
   `docs/process/2026-09-04-O-PO-DECIDE-as-54-e-os-sete-conflitos.md:9-14`;
   sem a citação, "delegação" é palavra sem procedência.
3. **`indeterminado` diz POR QUE não se sabe**, com a data. Sete linhas do
   registro fecharam sem palavra dela e sem mandato — inventar autoria nelas
   seria exatamente o defeito que esta régua existe para matar.
4. **`revoga` só aponta id que existe**, e nunca a si mesmo.
5. **A lápide é legível.** Quem revoga nomeia o revogado NA PROSA da `escolha`,
   não só na coluna: foi a leitura HUMANA que falhou nos três casos acima.
6. **Quem diz `ela` sobre o lote de 04/09 mostra a prova.** As 54 linhas
   nasceram por delegação; virar uma para `ela` exige o carimbo
   `QUEM DECIDIU: ELA` com a palavra dela, senão a coluna volta a ser opinião.

O QUE ELA **NÃO** COBRA, e a razão é medida nesta árvore: o §6 do laudo propôs
que `quem_decidiu = ela` exigisse um trecho entre aspas na `escolha`. Medido em
06/09/2026: **37 linhas de autoria dela não têm verbatim** — inclusive as de
06/09, em que ela respondeu por escolha e não por frase. Exigir aspas empurraria
autoria PROVADA para `indeterminado`, que é piorar o registro para satisfazer a
régua. A exigência de prova ficou onde o trabalho de hoje aconteceu: a regra 6.
"""
from __future__ import annotations

import csv
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CSV_ = RAIZ / "docs" / "data" / "decisoes-dela.csv"

#: Os três valores, e só eles. `indeterminado` é o terceiro DE PROPÓSITO: sem
#: ele, quem não sabe chuta, e chutar autoria é o defeito de origem.
VALORES = {"ela", "delegacao", "indeterminado"}

MARCA_INDETERMINADO = "QUEM DECIDIU: INDETERMINADO"
MARCA_ELA = "QUEM DECIDIU: ELA"

#: O lote de 04/09: 54 perguntas decididas pelo PO num arquivo só.
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
    """A régua da tarefa: linha sem `quem_decidiu` reprova, nomeada.

    MORDE: esvaziar o `quem_decidiu` de qualquer linha, ou escrever nele
    qualquer coisa fora dos três valores.
    """
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
    """Delegação sem procedência é palavra solta.

    MORDE: apagar "DELEGAÇÃO" da `escolha` de uma linha marcada `delegacao`.
    """
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
    """Não saber é resposta legítima; não saber calado, não.

    MORDE: marcar uma linha como `indeterminado` sem o carimbo com a razão.
    """
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
    """Ponteiro para id inexistente é lápide sobre cova errada.

    MORDE: trocar um alvo de `revoga` por um id que não está no arquivo, ou
    fazer uma linha revogar a si mesma.
    """
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
    """A lápide tem de ser legível por quem lê, não só pela máquina.

    Nos três casos de 05/09 a palavra dela estava no disco e ninguém a viu —
    porque a revogação era uma inferência, não uma frase.

    MORDE: apagar o id revogado da `escolha` de quem o revoga.
    """
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
    """As 54 nasceram por delegação; virar uma para `ela` exige mostrar a prova.

    MORDE: trocar o `quem_decidiu` de qualquer linha do lote de 04/09 para
    `ela` sem o carimbo `QUEM DECIDIU: ELA` e a palavra dela na `escolha`.
    """
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
