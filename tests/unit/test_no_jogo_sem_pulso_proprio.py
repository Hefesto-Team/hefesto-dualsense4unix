"""NO-JOGO-SEM-FALSO-VERDE-01/T8 — o painel não pode ganhar pulso próprio."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("test_no_jogo_sem_pulso_proprio: importa código da janela GTK")

import re
from pathlib import Path

from hefesto_dualsense4unix.app.widgets import painel_no_jogo as pnj_mod

_AGENDADORES = (
    r"GLib\.timeout_add\(",
    r"GLib\.timeout_add_seconds\(",
    r"GLib\.idle_add\(",
)


def _fonte_do_painel() -> str:
    return Path(pnj_mod.__file__).read_text(encoding="utf-8")


def test_o_painel_no_jogo_nao_agenda_nada() -> None:
    """Zero timers no fonte do widget — o que a docstring dele promete."""
    fonte = _fonte_do_painel()

    encontrados = {
        padrao: len(re.findall(padrao, fonte)) for padrao in _AGENDADORES
    }

    assert encontrados == dict.fromkeys(_AGENDADORES, 0), (
        "O painel da aba No jogo ganhou pulso próprio "
        f"({encontrados}). Ele é montado POR CONTROLE: com a mesa cheia isso "
        "são quatro laços. Quem repinta é o tique de 2 Hz da "
        "`_sync_paineis_no_jogo`, e só com esta aba à vista."
    )


def test_a_regua_enxerga_o_arquivo_certo() -> None:
    """A contraprova da régua de cima, e ela não é cerimônia."""
    caminho = Path(pnj_mod.__file__)
    fonte = _fonte_do_painel()

    assert caminho.name == "painel_no_jogo.py"
    assert "class PainelNoJogo" in fonte
    assert "GLib.timeout_add" in fonte, (
        "A docstring do painel cita `GLib.timeout_add` para dizer que não usa "
        "nenhum. Se nem a menção sobrou, a régua de cima passou a medir a "
        "ausência de um texto que ninguém escreveu."
    )
