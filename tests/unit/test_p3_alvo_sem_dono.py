"""P3 — o alvo sem dono: "Todos" e "não sei" tinham o mesmo valor.

O defeito de forma, medido em 23/08/2026: ``_edit_target_uniq`` era um
atributo de CLASSE com default ``None`` em ``StatusActionsMixin``, e ``None``
quer dizer, para os nove leitores, *"escreva em TODOS os controles"*. Uma
janela que ainda não sabia qual era o alvo — aba Status recém-montada, mesa
vazia, daemon desligado — respondia "global" com toda a confiança.

O pior caso medido: com os dois controles desligados, o tique de 2 Hz zerava o
alvo (``total < 1`` → ``_sync_edit_target(None)``) e um pixel de arrasto no
brilho da Lightbar apagava os overrides por controle do perfil INTEIRO, com
zero palavras na tela.

Estes testes trancam a separação: ``TODOS`` é escolha dela e continua
escrevendo global byte-a-byte igual; ``DESCONHECIDO`` é ausência de
informação, se declara e não vira ação.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
exigir_gi_real("p3 alvo sem dono")

from typing import Any

from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin
from hefesto_dualsense4unix.app.alvo_de_edicao import (
    ATRIBUTO_LEGADO_LABEL,
    ATRIBUTO_LEGADO_UNIQ,
    MOTIVO_DAEMON_DESLIGADO,
    MOTIVO_MESA_VAZIA,
    MOTIVO_SEM_ESTADO,
    EstadoDoAlvo,
    alvo_de_edicao,
    definir_alvo,
    esquecer_alvo,
)

#: MACs forjados da faixa permitida (tests/unit/test_anonimato_de_fixtures.py).
UNIQ_1 = "aabbcc000001"
UNIQ_2 = "aabbcc000002"


class _Janela:
    """Hospedeiro mínimo: só carrega atributos, como a janela real."""


# ----------------------------------------------------------------------
# O módulo dono do alvo
# ----------------------------------------------------------------------


def test_p3_host_virgem_e_desconhecido_nunca_todos() -> None:
    """A MORDIDA: sem a aba Status montada o alvo é DESCONHECIDO."""
    alvo = alvo_de_edicao(_Janela())
    assert alvo.estado is EstadoDoAlvo.DESCONHECIDO
    assert alvo.desconhecido
    assert not alvo.global_
    assert not alvo.pode_escrever()
    assert alvo.recusa()
    assert MOTIVO_SEM_ESTADO in (alvo.recusa() or "")


def test_p3_todos_e_desconhecido_sao_estados_diferentes() -> None:
    """O ``None`` de antes era os dois; agora nenhum é o outro."""
    escolheu_todos = _Janela()
    definir_alvo(escolheu_todos, None, None)
    nao_sabe = _Janela()
    esquecer_alvo(nao_sabe, MOTIVO_MESA_VAZIA)

    assert alvo_de_edicao(escolheu_todos).estado is EstadoDoAlvo.TODOS
    assert alvo_de_edicao(nao_sabe).estado is EstadoDoAlvo.DESCONHECIDO
    assert alvo_de_edicao(escolheu_todos) != alvo_de_edicao(nao_sabe)
    # "Todos" é escolha dela e continua escrevendo, byte-idêntico ao de hoje.
    assert alvo_de_edicao(escolheu_todos).pode_escrever()
    assert not alvo_de_edicao(nao_sabe).pode_escrever()


def test_p3_definir_alvo_por_controle_espelha_o_atributo_legado() -> None:
    """Os nove leitores não migrados enxergam o mesmo de sempre."""
    janela = _Janela()
    definir_alvo(janela, UNIQ_2, "Controle 2 (USB)")
    assert alvo_de_edicao(janela).estado is EstadoDoAlvo.CONTROLE
    assert getattr(janela, ATRIBUTO_LEGADO_UNIQ, None) == UNIQ_2
    assert getattr(janela, ATRIBUTO_LEGADO_LABEL, None) == "Controle 2 (USB)"


def test_p3_esquecer_apaga_o_atributo_legado_da_instancia() -> None:
    """Esquecer não deixa o valor velho de pé para os não migrados."""
    janela = _Janela()
    definir_alvo(janela, UNIQ_1, "Controle 1 (BT)")
    esquecer_alvo(janela, MOTIVO_DAEMON_DESLIGADO)
    assert not hasattr(janela, ATRIBUTO_LEGADO_UNIQ)
    assert not hasattr(janela, ATRIBUTO_LEGADO_LABEL)
    # o leitor não migrado volta ao `None` de hoje: nenhuma colisão.
    assert getattr(janela, ATRIBUTO_LEGADO_UNIQ, None) is None


def test_p3_ponte_le_quem_ainda_escreve_o_atributo_antigo() -> None:
    """Dublê de teste que escreve direto não vira "desconhecido" por engano."""
    janela = _Janela()
    janela._edit_target_uniq = UNIQ_1  # type: ignore[attr-defined]
    janela._edit_target_label = "Controle 1 (BT)"  # type: ignore[attr-defined]
    alvo = alvo_de_edicao(janela)
    assert alvo.estado is EstadoDoAlvo.CONTROLE
    assert alvo.uniq == UNIQ_1

    global_na_mao = _Janela()
    global_na_mao._edit_target_uniq = None  # type: ignore[attr-defined]
    assert alvo_de_edicao(global_na_mao).estado is EstadoDoAlvo.TODOS


# ----------------------------------------------------------------------
# A aba Status: o escritor único
# ----------------------------------------------------------------------
class _FakeBadge:
    def __init__(self) -> None:
        self.text = ""
        self.visible = False

    def set_text(self, text: str) -> None:
        self.text = text

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False


def _instancia() -> Any:
    inst = StatusActionsMixin.__new__(StatusActionsMixin)
    inst._target_combo = object()
    inst._externals = []
    inst._externals_sig = None
    inst._target_combo_rows = []
    inst._target_combo_active = -1
    inst._target_combo_visible = False
    inst._target_uniq_by_index = {}
    inst._target_label_by_index = {}
    inst._numero_faixa = None
    inst._numero_box = None
    inst._edit_badge = _FakeBadge()
    # Widgets da fita: só o que o caminho medido toca.
    inst._rebuild_target_buttons = lambda box, rows: None
    inst._set_target_active = lambda pos: None
    inst._set_target_strip_visible = lambda visivel: None
    return inst


def _estado(*controles: dict[str, Any]) -> dict[str, Any]:
    return {"controllers": list(controles), "output_target_index": 0}


def _controle(index: int, uniq: str) -> dict[str, Any]:
    return {
        "index": index,
        "connected": True,
        "transport": "bt",
        "uniq": uniq,
        "player_slot": index + 1,
    }


def test_p3_aba_status_nunca_montada_e_desconhecida() -> None:
    """A MORDIDA na aba de verdade: sem montar, o alvo não é "Todos"."""
    crua = StatusActionsMixin.__new__(StatusActionsMixin)
    alvo = alvo_de_edicao(crua)
    assert alvo.desconhecido, (
        "aba Status nunca montada respondeu 'Todos' — é o defeito de forma"
    )
    assert not alvo.pode_escrever()


def test_p3_a_classe_nao_carrega_mais_o_default_global() -> None:
    """A linha do defeito: o atributo de classe respondia por quem não sabia."""
    assert "_edit_target_uniq" not in vars(StatusActionsMixin)
    assert "_edit_target_label" not in vars(StatusActionsMixin)
    crua = StatusActionsMixin.__new__(StatusActionsMixin)
    assert getattr(crua, "_edit_target_uniq", "AUSENTE") == "AUSENTE"


def test_p3_mesa_esvaziou_o_alvo_fica_desconhecido() -> None:
    """O caso alcançável e pior: os dois controles desligados."""
    inst = _instancia()
    inst._refresh_controller_target_combo(_estado(_controle(0, UNIQ_1), _controle(1, UNIQ_2)))
    assert alvo_de_edicao(inst).uniq == UNIQ_1

    inst._refresh_controller_target_combo(_estado())  # mesa vazia

    alvo = alvo_de_edicao(inst)
    assert alvo.desconhecido, "mesa vazia virou 'Todos' — a edição global voltou"
    assert alvo.motivo == MOTIVO_MESA_VAZIA
    assert not hasattr(inst, "_edit_target_uniq")


def test_p3_clique_em_todos_continua_global() -> None:
    """Hipótese explica o que JÁ funcionava: "Todos" não virou recusa."""
    inst = _instancia()
    inst._update_target_maps([_controle(0, UNIQ_1)])
    inst._sync_edit_target(0)
    assert alvo_de_edicao(inst).por_controle

    inst._sync_edit_target(None)  # o clique dela em "Todos"

    alvo = alvo_de_edicao(inst)
    assert alvo.estado is EstadoDoAlvo.TODOS
    assert alvo.pode_escrever()
    assert alvo.uniq is None
    assert getattr(inst, "_edit_target_uniq", "AUSENTE") is None
    assert not inst._edit_badge.visible


def test_p3_de_desconhecido_para_todos_o_gesto_dela_nao_se_perde() -> None:
    """O curto-circuito antigo comparava campos, não estados."""
    inst = _instancia()
    esquecer_alvo(inst, MOTIVO_MESA_VAZIA)
    inst._sync_edit_target(None)
    assert alvo_de_edicao(inst).estado is EstadoDoAlvo.TODOS


def test_p3_numero_recusa_com_o_motivo_quando_nao_sabe() -> None:
    """O único leitor honesto dos nove separa os dois motivos."""
    inst = _instancia()
    toasts: list[tuple[str, str]] = []
    inst._status_toast = lambda chave, texto: toasts.append((chave, texto))
    esquecer_alvo(inst, MOTIVO_MESA_VAZIA)

    botao = type("B", (), {"get_active": lambda self: True})()
    inst._on_numero_button_toggled(botao, 2)

    assert len(toasts) == 1
    assert MOTIVO_MESA_VAZIA in toasts[0][1]
    assert "Nada foi alterado" in toasts[0][1]

    # "Todos" (escolha dela) mantém a instrução de sempre, que ali cabe.
    toasts.clear()
    definir_alvo(inst, None, None)
    inst._on_numero_button_toggled(botao, 2)
    assert toasts == [
        ("numero", "Escolha um controle no cabeçalho antes de trocar o número")
    ]
