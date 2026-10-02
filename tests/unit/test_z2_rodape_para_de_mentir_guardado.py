"""Z2-3 — o rodapé para de chamar de "guardado" o que não tem alvo."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("z2 rodape para de mentir guardado")


from hefesto_dualsense4unix.app.alvo_de_edicao import definir_alvo
from hefesto_dualsense4unix.app.textos_de_aplicacao import (
    alvo_fora_da_mesa,
)

UNIQ_1 = "aabbcc000001"


class _Janela:
    """Hospedeiro mínimo: só o que a função lê."""


def test_clique_legitimo_em_todos_continua_devolvendo_none() -> None:
    """A2: o dublê também sabe ACEITAR — 'Todos' não é recusa."""
    host = _Janela()
    definir_alvo(host, None, None)
    assert alvo_fora_da_mesa(host) is None


def test_alvo_conectado_continua_devolvendo_none() -> None:
    host = _Janela()
    definir_alvo(host, UNIQ_1, "Controle 1 (BT)")
    host._target_uniq_by_index = {0: UNIQ_1}  # type: ignore[attr-defined]
    assert alvo_fora_da_mesa(host) is None


def test_alvo_fora_da_mesa_continua_devolvendo_o_nome() -> None:
    """Hipótese explica o que já funcionava: o caminho normal não mudou."""
    host = _Janela()
    definir_alvo(host, UNIQ_1, "Controle 1 (BT)")
    host._target_uniq_by_index = {}  # type: ignore[attr-defined]
    assert alvo_fora_da_mesa(host) == "Controle 1"


