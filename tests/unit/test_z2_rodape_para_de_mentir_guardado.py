"""Z2-3 — o rodapé para de chamar de "guardado" o que não tem alvo.

24/08/2026. ``alvo_fora_da_mesa`` lia ``_edit_target_uniq`` cru: ``None``
saía tanto para "ela clicou em Todos" quanto para "a janela não sabe" — e
os dois casos alimentavam ``frase_de_guardado(...) or _TOAST_COR_ENVIADA``,
o mesmo padrão ``or`` que deixava a mentira do P3 (``app/alvo_de_edicao.py``)
sumir em silêncio. Estes testes trancam a distinção pela raiz: agora a
função lê o dono único e RECUSA alto quando não sabe, em vez de devolver
``None`` e deixar quem chama compor sucesso por engano.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
exigir_gi_real("z2 rodape para de mentir guardado")

import pytest

from hefesto_dualsense4unix.app import draft_config as draft_mod
from hefesto_dualsense4unix.app.alvo_de_edicao import (
    MOTIVO_MESA_VAZIA,
    definir_alvo,
    esquecer_alvo,
)
from hefesto_dualsense4unix.app.draft_config import registrar_alto_falante_no_rascunho
from hefesto_dualsense4unix.app.textos_de_aplicacao import (
    AlvoDesconhecidoNaMesa,
    alvo_fora_da_mesa,
)

#: MAC forjado da faixa permitida (tests/unit/test_anonimato_de_fixtures.py).
UNIQ_1 = "aabbcc000001"


class _Janela:
    """Hospedeiro mínimo: só o que a função lê."""


def test_desconhecido_recusa_alto_em_vez_de_devolver_none() -> None:
    """A MORDIDA: sem saber o alvo, a função não finge que sabe."""
    host = _Janela()
    esquecer_alvo(host, MOTIVO_MESA_VAZIA)

    with pytest.raises(AlvoDesconhecidoNaMesa) as excinfo:
        alvo_fora_da_mesa(host)
    assert MOTIVO_MESA_VAZIA in str(excinfo.value)


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


# ---------------------------------------------------------------------------
# Z2-4 — o escritor do perfil (alto-falante) migra
# ---------------------------------------------------------------------------


def test_alto_falante_desconhecido_nao_escreve_no_rascunho() -> None:
    """A MORDIDA: sem saber o alvo, o volume do card não anota GLOBAL."""
    host = _Janela()
    host.draft = draft_mod.DraftConfig.default()  # type: ignore[attr-defined]
    antes = host.draft  # type: ignore[attr-defined]

    registrar_alto_falante_no_rascunho(host, volume=200, muted=False, uniq=UNIQ_1)

    assert host.draft is antes, "gravou a peça errada no global (P3)"  # type: ignore[attr-defined]


def test_alto_falante_definido_em_todos_continua_gravando_global() -> None:
    """A2 — 'Todos' (escolha dela) continua indo para a seção global."""
    host = _Janela()
    host.draft = draft_mod.DraftConfig.default()  # type: ignore[attr-defined]
    definir_alvo(host, None, None)

    registrar_alto_falante_no_rascunho(host, volume=200, muted=False, uniq=UNIQ_1)

    assert host.draft.speaker.volume == 200  # type: ignore[attr-defined]
