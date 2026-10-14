"""O que a coleta deixou vivo não pesa na passada do coletor de lixo.

O servidor e o cliente do IPC dos testes moram no processo da suíte, e o
cliente espera 1 s pelo `daemon.state_full`. Sem o congelamento do
`tests/conftest.py`, cada passada cheia varria ~1 milhão de objetos da coleta,
levava 1,2 a 2,3 s no runner do CI e reprovava o teste de contrato que caísse
nela (14/10/2026). Uma biblioteca já congela algumas centenas por conta
própria, e por isso a régua compara com o que a varredura ainda alcança.
"""

from __future__ import annotations

import gc


def test_a_coleta_congelada_e_maior_que_o_que_a_varredura_alcanca() -> None:
    congelados = gc.get_freeze_count()
    varridos = len(gc.get_objects())
    assert congelados > varridos, (
        f"{congelados} congelados e {varridos} na varredura: o "
        "`pytest_collection_finish` do conftest saiu, e a passada cheia do "
        "coletor volta a varrer tudo o que a coleta deixou"
    )
