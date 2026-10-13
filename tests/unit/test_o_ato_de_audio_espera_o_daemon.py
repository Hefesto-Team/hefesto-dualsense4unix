"""O ato de áudio espera o daemon terminar — MEDIDO na bancada."""

from __future__ import annotations

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


def test_o_teto_padrao_nao_mudou_para_os_outros(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A folga é dos TRÊS atos de áudio, e de mais ninguém.

    Sem ``timeout``, o transporte espera o ``teto(method)``; um método fora da
    tabela de tetos espera o padrão de uma leitura. Mede-se o prazo que chega
    ao ``_run_call``, e não o valor default da assinatura, que é ``None``.
    """
    fora_da_tabela = "daemon.state_full"
    assert fora_da_tabela not in ipc_bridge.TETOS
    visto: dict[str, Any] = {}

    def espiao(method: str, params: Any = None, timeout: Any = None) -> Any:
        visto["timeout"] = timeout
        return {}

    monkeypatch.setattr(ipc_bridge, "_run_call", espiao)
    ipc_bridge._safe_call(fora_da_tabela)
    assert visto.get("timeout") == 0.25, (
        f"o teto PADRÃO do transporte virou {visto.get('timeout')!r}. A cura de "
        f"08/09 é dos três atos de áudio, que varrem o PulseAudio; alargar o "
        f"padrão prende a janela no tique quando o daemon trava.")
