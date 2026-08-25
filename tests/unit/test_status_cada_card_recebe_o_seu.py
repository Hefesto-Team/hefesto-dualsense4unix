"""STATUS-DIZ-O-QUE-VÊ-01/T4 — o card ordenado tem de receber o registro dele.

**O defeito que este arquivo mede nasceu da CURA de T4, e por isso ele existe.**

A Z2-7 (24/08/2026, `b036dca`) pôs `_status_card_keys_for` a percorrer
`_por_numero_de_identidade` — a mesma ordem da fita —, e o teste daquela leva
(`test_z2_ordem_dos_cards.py`) mediu só a função de chaves, isolada. As duas
grades que CONSOMEM as chaves continuaram casando ``keys`` com ``conectados``
por posição, na ordem crua do daemon — um ``zip`` das chaves com a lista que
o daemon devolveu.

Com a mesa fora de ordem — o caso normal, e o da fixture versionada — o card
do Controle 1 passou a ser alimentado com o registro do Controle 4: bateria,
analógicos, luz e microfone do vizinho, debaixo do título certo.

É a família do defeito que a própria `_por_numero_de_identidade` documenta
("clicar no chip do 1 editaria outro controle"), agravada: lá a pessoa clicava
errado, aqui ela **lê** errado, e nada na tela denuncia.

O portão do fim do arquivo é o que impede a volta: **nenhum `zip` desta aba
pode casar as chaves com a lista crua.**
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
exigir_gi_real("status: cada card recebe o seu")

import json
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin as S

#: A mesa cheia versionada — a mesma que o `--mesa-cheia` fotografa, e a
#: única prova possível de quatro controles sem quatro controles na bancada.
_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "state_full_quatro_controles.json"


def _mesa_cheia() -> dict[str, Any]:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def _nome(no: Any) -> str:
    """O nome legível de um nó de AST — ``keys``, ``self.x``, ou ``<expr>``."""
    import ast

    if isinstance(no, ast.Name):
        return no.id
    if isinstance(no, ast.Attribute):
        return f"{_nome(no.value)}.{no.attr}"
    if isinstance(no, ast.Call):
        return f"{_nome(no.func)}(...)"
    return "<expr>"


class _AbaDeMentira(S):  # type: ignore[misc]
    """A aba Status reduzida ao que este teste afere: quem recebe o quê.

    Sem GTK e sem IPC de propósito. O que está em julgamento é o PAREAMENTO
    entre a chave de um card e o registro que o alimenta — pôr uma janela no
    caminho só acrescentaria lugar para o teste errar, e a armadilha do 1x1
    não protege de nada aqui.
    """

    def __init__(self) -> None:
        self._status_cards: dict[Any, Any] = {}
        self._status_card_keys: list[Any] = []
        self.alimentados: list[tuple[Any, dict[str, Any]]] = []

    def parear(self, state: dict[str, Any]) -> list[tuple[Any, dict[str, Any]]]:
        """O laço de `_sync_status_cards`, sem os widgets no meio."""
        conectados = self._connected_controllers(state)
        keys = self._status_card_keys_for(conectados)
        ordenados = self._conectados_na_ordem_dos_cards(conectados)
        return list(zip(keys, ordenados, strict=True))


def test_cada_card_recebe_o_registro_do_proprio_controle() -> None:
    """A MORDIDA: troque `_conectados_na_ordem_dos_cards(conectados)` de volta
    por `conectados` no `parear` (e nas duas grades de produção) e o teste
    reprova nomeando, controle a controle, qual `uniq` estava na chave e qual
    chegou no registro.

    A fixture serve porque a mesa dela está fora de ordem de propósito:
    ``player_slot`` 4, 1, 3, 2 na ordem de enumeração do daemon.
    """
    pares = _AbaDeMentira().parear(_mesa_cheia())

    errados = [
        {
            "posição": pos,
            "uniq na chave": key[1],
            "uniq no registro": entry.get("uniq"),
            "player_slot que a tela vai imprimir": entry.get("player_slot"),
        }
        for pos, (key, entry) in enumerate(pares)
        if key[1] != entry.get("uniq")
    ]

    assert not errados, (
        "card alimentado com o registro de OUTRO controle — a chave diz um "
        f"aparelho e o dado é de outro: {errados}"
    )


def test_a_ordem_dos_cards_e_a_ordem_da_fita() -> None:
    """A metade que a Z2-7 já entregou, agora medida sobre a mesa cheia.

    Com o código de 23/08 ela reprovava com ``[4, 1, 3, 2]`` contra
    ``[1, 2, 3, 4]``; hoje passa, e fica aqui como rede — arranque a
    ordenação de `_conectados_na_ordem_dos_cards` e os dois vetores voltam a
    divergir.
    """
    state = _mesa_cheia()
    conectados = S._connected_controllers(state)

    slots_dos_cards = [
        c.get("player_slot") for c in S._conectados_na_ordem_dos_cards(conectados)
    ]
    # A fita, sem a linha "Todos os controles" da posição 0.
    rotulos_da_fita = [rotulo for rotulo, _idx in S._controller_target_rows(conectados)][1:]
    slots_da_fita = [
        int("".join(ch for ch in rotulo.split("—")[0] if ch.isdigit()))
        for rotulo in rotulos_da_fita
    ]

    assert slots_dos_cards == slots_da_fita, (
        f"os cards nascem em {slots_dos_cards} e a fita em {slots_da_fita}: "
        "quem aponta para o segundo chip e olha o segundo card está olhando "
        "outro controle"
    )


def test_o_indice_de_enumeracao_nao_e_reordenado_junto() -> None:
    """A hipótese explica o que JÁ funcionava (regra da casa).

    Reordenar a EXIBIÇÃO não pode reordenar o ``index``: é ele que o
    ``controller.target.set`` espera, e trocá-lo faria a pessoa clicar no
    chip do 1 e editar outro controle — o defeito que
    `_por_numero_de_identidade` documenta e evita desde a PLAYER-01.
    """
    state = _mesa_cheia()
    conectados = S._connected_controllers(state)
    indice_por_uniq_cru = {c.get("uniq"): c.get("index") for c in conectados}

    for key in S._status_card_keys_for(conectados):
        indice, uniq = key[0], key[1]
        assert indice == indice_por_uniq_cru[uniq], (
            f"o índice de enumeração de {uniq} virou {indice} na chave do "
            f"card, e o registro do daemon diz {indice_por_uniq_cru[uniq]}: "
            "a ordem de exibição vazou para o endereço do controle"
        )


def test_nenhuma_grade_da_aba_casa_as_chaves_com_a_lista_crua() -> None:
    """O portão que teria pego este defeito no dia em que ele nasceu.

    Varredura de FONTE, e não de comportamento: as duas grades vivem em
    funções que pedem GTK, IPC e um `state_full` inteiro para rodar, e um
    teste de comportamento por grade nasceria caro e cobriria uma delas de
    cada vez. A pergunta aqui é sintática e é a certa — *existe algum `zip`
    que case `keys` com a lista crua?* — e ela vale para a grade que a Onda 4
    ainda vai escrever.

    **A mordida:** devolva `zip(keys, conectados, strict=True)` a qualquer uma
    das duas e o portão reprova nomeando arquivo e linha.
    """
    import ast

    fonte = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "hefesto_dualsense4unix"
        / "app"
        / "actions"
        / "status_actions.py"
    )
    arvore = ast.parse(fonte.read_text(encoding="utf-8"))

    # AST, e não `grep`: um `grep` acharia também as citações desta mesma
    # forma dentro de comentário e docstring — e um portão que obriga a
    # documentação a evitar a palavra que ele proíbe vira ruído, não régua.
    # Aqui só existe CÓDIGO.
    suspeitos = [
        f"status_actions.py:{no.lineno}: zip({', '.join(_nome(a) for a in no.args)})"
        for no in ast.walk(arvore)
        if isinstance(no, ast.Call)
        and _nome(no.func) == "zip"
        and [_nome(a) for a in no.args[:2]] == ["keys", "conectados"]
    ]

    assert not suspeitos, (
        "uma grade da aba Status volta a casar as chaves ORDENADAS com a "
        "lista CRUA do daemon, posição a posição — é o defeito de T4, e ele "
        f"alimenta cada card com o registro do vizinho: {suspeitos}"
    )
