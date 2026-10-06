"""O ato de áudio espera o daemon terminar — MEDIDO na bancada."""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from hefesto_dualsense4unix.app import ipc_bridge

_MEDIDO_MS = 3070

_ATOS_DE_AUDIO = (
    ("mic_canal_set_detalhado", (True,)),
    ("mic_volume_set_detalhado", (50,)),
    ("speaker_set_detalhado", (50,)),
)


def test_o_teto_cabe_o_que_o_daemon_leva() -> None:
    """O teto é maior que o medido, com folga que se escreve."""
    teto_ms = ipc_bridge._TETO_DO_ATO_DE_AUDIO * 1000
    assert teto_ms >= _MEDIDO_MS * 1.5, (
        f"o teto do ato de áudio é {teto_ms:.0f} ms e o daemon leva "
        f"{_MEDIDO_MS} ms medidos. Sem pelo menos 50% de folga, uma máquina "
        f"mais carregada devolve a frase de três causas que ela leu em 08/09 — "
        f"e o modo de falhar é o pior: não parece um teto, parece um daemon "
        f"quebrado.")


@pytest.mark.parametrize(("nome", "args"), _ATOS_DE_AUDIO)
def test_o_ato_de_audio_pede_o_teto_largo(nome: str, args: tuple[Any, ...],
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    """Cada ato de áudio passa o teto largo ao transporte — medido, não lido."""
    visto: dict[str, Any] = {}

    def espiao(chamado: str, params: Any = None, **kw: Any) -> tuple[bool, Any]:
        visto["chamado"] = chamado
        visto["timeout"] = kw.get("timeout")
        return True, {"status": "ok"}

    monkeypatch.setattr(ipc_bridge, "_safe_call", espiao)
    getattr(ipc_bridge, nome)(*args)

    assert visto.get("timeout") == ipc_bridge._TETO_DO_ATO_DE_AUDIO, (
        f"`{nome}` chamou `{visto.get('chamado')}` com timeout "
        f"{visto.get('timeout')!r} em vez do teto largo "
        f"({ipc_bridge._TETO_DO_ATO_DE_AUDIO}). Com o teto padrão de 250 ms a "
        f"resposta do daemon chega tarde, o corpo vira `None`, e a tela mostra "
        f"três causas — nenhuma delas a verdadeira.")


def test_o_teto_padrao_nao_mudou_para_os_outros() -> None:
    """A folga é dos TRÊS atos de áudio, e de mais ninguém."""
    padrao = inspect.signature(ipc_bridge._safe_call).parameters["timeout"].default
    assert padrao == 0.25, (
        f"o teto PADRÃO do transporte virou {padrao!r}. A cura de 08/09 é dos "
        f"três atos de áudio, que varrem o PulseAudio; alargar o padrão prende "
        f"a janela no tique quando o daemon trava.")
