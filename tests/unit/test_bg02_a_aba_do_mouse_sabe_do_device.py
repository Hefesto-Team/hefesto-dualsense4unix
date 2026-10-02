"""BG-02, lado da janela — a aba para de adivinhar se o mouse virtual subiu."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("a aba do mouse sabe do device")


import pytest

pytest.importorskip("gi")

from hefesto_dualsense4unix.app.actions.mouse_actions import BLOQUEIO_DO_MOUSE_EM_PORTUGUES

PRONTO = "Pronto para usar como mouse"
SEM_PERMISSAO = "está sem permissão"
NAO_ESTA_PRONTO = "ainda não está pronto"
FALTA_COMPONENTE = "Falta um componente"


class _FakeLabel:
    def __init__(self) -> None:
        self.markup = ""

    def set_markup(self, texto: str) -> None:
        self.markup = texto


def test_todo_motivo_que_o_daemon_emite_tem_traducao() -> None:
    """A régua contra a divergência silenciosa entre daemon e janela.

    `_bloqueio_da_emulacao_de_desktop` emite estes quatro códigos, e são os
    quatro que a tabela traduz. Um código novo do daemon sem linha aqui sai na
    tela como texto cru (`frase_da_recusa_do_mouse` é honesta nesse caso) — o
    que este teste impede é que ele sirva DUAS vezes, com dois vocabulários.
    """
    do_daemon = {"desligada", "sem_device", "modo_jogo"}
    assert do_daemon == set(BLOQUEIO_DO_MOUSE_EM_PORTUGUES), (
        "o vocabulário do daemon e o da janela divergiram: "
        f"{do_daemon ^ set(BLOQUEIO_DO_MOUSE_EM_PORTUGUES)}"
    )


