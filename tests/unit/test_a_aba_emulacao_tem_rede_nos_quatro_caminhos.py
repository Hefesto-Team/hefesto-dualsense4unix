"""EMULACAO-UM-DONO-SO-01/E13 — os buracos de rede da aba Emulação.

O DEFEITO
==========
Dois defeitos com nome próprio que esta aba JÁ PAGOU podiam voltar sem uma linha
vermelha. Medido em 24/08/2026: ``grep -rl`` em ``tests/`` devolvia **zero
arquivos** para ``_sync_hotkey_card``, ``_sync_uinput_card``,
``on_emulation_test_device`` e ``on_emulation_refresh``.

- ``BUG-EMULATION-HOTKEY-CARD-FIXO-01`` — as duas linhas do cartão de atalhos
  escreviam a CONSTANTE de compilação uma vez e ninguém mais as tocava: a tela
  afirmava "buffer 150" e "Passthrough: Não" como se fossem estado LIDO do
  daemon, com o daemon offline.
- ``BUG-EMULATION-UINPUT-CARD-STALE-01/02`` — o cartão UINPUT ficava com o
  VID:PID de Xbox na tela depois de a máscara mudar, ou com o gamepad virtual
  desligado.

E O ``grep`` VAZIO NÃO PROVA QUE A MUTAÇÃO PASSARIA
====================================================
Ele prova ausência de NOME, não ausência de rede — um teste de outro arquivo
podia estar cobrindo o caminho por acaso. A sprint exige as mutações
EXECUTADAS, e elas foram: ver o relatório do agente E1.

O QUE ESTE ARQUIVO **NÃO** TRAZ, E POR QUE
===========================================
O quarto caso da sprint — *"entrar em `emulation_box` chama o refresher da
aba"* — **já tem rede**, e é rede que morde. Medido em 25/08/2026 apagando a
linha ``"emulation_box": ("_refresh_emulation_tab",)`` de ``app/app.py:1114``:
``test_notebook_switch_page.py`` reprova em DOIS casos, e um deles nomeia a aba.
Escrever um terceiro seria a terceira régua da mesma pergunta, que é
verbosidade — e verbosidade tem custo medido nesta casa.
"""
from __future__ import annotations

import sys
from typing import Any

import pytest

pytest.importorskip("gi")

from hefesto_dualsense4unix.app.actions.emulation_actions import (
    EmulationActionsMixin as Mixin,
)
from hefesto_dualsense4unix.integrations.hotkey_daemon import DEFAULT_BUFFER_MS


class _RotuloFalso:
    def __init__(self) -> None:
        self.texto = ""

    def set_text(self, t: str) -> None:
        self.texto = t

    def set_markup(self, t: str) -> None:
        self.texto = t


class _Aba(Mixin):
    """A aba com um dicionário de rótulos no lugar do `Gtk.Builder`.

    `Gtk.OffscreenWindow` não entra aqui de propósito: nenhum destes caminhos
    desenha — todos escrevem em rótulo. Montar janela custaria segundos por caso
    e não mediria nada a mais.
    """

    def __init__(self) -> None:
        self.rotulos: dict[str, _RotuloFalso] = {}
        self.toasts: list[str] = []

    def _get(self, ident: str) -> Any:
        return self.rotulos.setdefault(ident, _RotuloFalso())

    def _toast_emulation(self, msg: str) -> None:
        self.toasts.append(msg)


# ---------------------------------------------------------------------------
# BUG-EMULATION-HOTKEY-CARD-FIXO-01
# ---------------------------------------------------------------------------
def test_sem_bloco_hotkey_o_cartao_diz_padrao_em_vez_de_afirmar_numero() -> None:
    """Sem estado, a tela não finge conhecer o estado.

    ARRANQUE A CURA: tire o sufixo `(padrão)` dos dois ramos de `else` em
    `_sync_hotkey_card` e este caso REPROVA — a tela volta a afirmar a
    constante de compilação como se fosse leitura do daemon.
    """
    aba = _Aba()
    aba._sync_hotkey_card(None)
    assert aba.rotulos["emulation_combo_buffer_label"].texto == (
        f"{DEFAULT_BUFFER_MS} (padrão)"
    )
    assert aba.rotulos["emulation_passthrough_label"].texto == "Não (padrão)"


@pytest.mark.parametrize("estado", [None, {}, {"hotkey": None}, {"hotkey": "x"}, 7])
def test_todo_estado_ilegivel_cai_no_padrao_e_nao_estoura(estado: object) -> None:
    """O `state_full` chega de um daemon que pode ser mais velho, ou não chegar."""
    aba = _Aba()
    aba._sync_hotkey_card(estado)
    assert "(padrão)" in aba.rotulos["emulation_combo_buffer_label"].texto


def test_com_bloco_hotkey_o_cartao_mostra_o_valor_efetivo() -> None:
    """O contrapeso: sem ele, "curar" viraria dizer (padrão) para sempre."""
    aba = _Aba()
    aba._sync_hotkey_card({"hotkey": {"buffer_ms": 220, "passthrough_in_emulation": True}})
    assert aba.rotulos["emulation_combo_buffer_label"].texto == "220"
    assert aba.rotulos["emulation_passthrough_label"].texto == "Sim"


def test_o_buffer_booleano_nao_passa_por_numero() -> None:
    """`bool` é subclasse de `int`: sem a guarda, `True` viraria "True" na tela."""
    aba = _Aba()
    aba._sync_hotkey_card({"hotkey": {"buffer_ms": True}})
    assert "(padrão)" in aba.rotulos["emulation_combo_buffer_label"].texto


# ---------------------------------------------------------------------------
# BUG-EMULATION-UINPUT-CARD-STALE-01/02
# ---------------------------------------------------------------------------
def test_o_cartao_uinput_mostra_o_vidpid_da_mascara_viva() -> None:
    """ARRANQUE A CURA: devolva a constante de Xbox cravada e este caso REPROVA."""
    aba = _Aba()
    aba._sync_uinput_card("dualsense")
    vid = aba.rotulos["emulation_vidpid_label"].texto
    assert vid.startswith("054C:0DF2"), vid
    assert "DualSense" in vid, vid
    assert "Xbox" not in vid, vid


def test_a_mascara_xbox_mostra_o_vidpid_de_xbox() -> None:
    aba = _Aba()
    aba._sync_uinput_card("xbox")
    vid = aba.rotulos["emulation_vidpid_label"].texto
    assert "Xbox 360" in vid, vid
    assert "054C" not in vid, vid


@pytest.mark.parametrize("desligado", [None, "off", "", "flavor-que-nao-existe"])
def test_com_o_gamepad_virtual_desligado_nao_sobra_vidpid_de_ninguem(
    desligado: str | None,
) -> None:
    """BUG-EMULATION-UINPUT-CARD-STALE-02: o cartão não pode ficar com o de antes."""
    aba = _Aba()
    aba._sync_uinput_card("xbox")
    aba._sync_uinput_card(desligado)
    assert aba.rotulos["emulation_vidpid_label"].texto == "—"
    assert "desligado" in aba.rotulos["emulation_device_name_label"].texto


# ---------------------------------------------------------------------------
# "Testar o controle virtual" sem uinput
# ---------------------------------------------------------------------------
def test_testar_o_controle_virtual_sem_uinput_avisa_e_nao_cria_no(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem o módulo, o botão avisa — e NÃO chega a instanciar nada.

    `sys.modules["uinput"] = None` é a forma documentada de fazer `import
    uinput` levantar `ImportError` sem mexer no disco. E a segunda asserção é a
    que importa: um aviso na tela com um nó de uinput criado atrás dele seria o
    pior dos dois mundos — a suíte desta casa já derrubou a sessão gráfica dela
    criando nós de verdade (TEMPESTADE-DE-TECLADOS-01).
    """
    criados: list[str] = []

    class _Espia:
        """Dublê COMPLETO de propósito.

        Um dublê incompleto faz a mutação reprovar por `AttributeError`, e
        `AttributeError` não prova nada — prova que o dublê é pobre. Com
        `start`/`stop` no lugar, o caminho roda inteiro e quem reprova é a
        asserção que mede o defeito: criou nó sem uinput.
        """

        def __init__(self, *a: object, **k: object) -> None:
            criados.append("instanciou")

        def start(self) -> bool:
            return True

        def stop(self) -> None:
            return None

    import hefesto_dualsense4unix.integrations.uinput_gamepad as ug

    monkeypatch.setattr(ug, "UinputGamepad", _Espia)
    monkeypatch.setitem(sys.modules, "uinput", None)

    aba = _Aba()
    aba.on_emulation_test_device(None)  # type: ignore[arg-type]

    assert aba.toasts, "o botão ficou mudo sem o gamepad virtual disponível"
    assert not criados, f"criou nó mesmo sem uinput: {criados}"
    aviso = aba.toasts[-1]
    assert "reinstale" in aviso.lower(), aviso
