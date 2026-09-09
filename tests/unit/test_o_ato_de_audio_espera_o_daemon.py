"""O ato de áudio espera o daemon terminar — MEDIDO na máquina dela.

**O DEFEITO, 08/09/2026, e ela o viu na tela minutos depois do `install.sh`:**
uma faixa laranja no cartão do P1 dizendo *"o daemon não confirmou o mudo do
microfone — ou o Hefesto está parado, ou este controle se desligou, ou o Hefesto
instalado é mais velho que esta janela"*.

**Nenhuma das três causas era verdade.** O daemon era o recém-instalado, conhecia
o método, e tinha respondido com a razão CERTA — *"não há canal de captura
atribuível a este controle — no rádio ele só aparece com a ponte de microfone de
pé"*. Medido no socket vivo: `mic.canal.set` leva **3.070 ms** (três voltas:
3071, 3069, 3070) e o teto de `_safe_call` é **250 ms**. A resposta chegava
sempre tarde, e o transporte jogava fora a frase que ela precisava ler.

*É o mesmo defeito que `a02_controles` diz ter curado em 04/09, por outra porta:
da primeira vez a lista de causas não continha o caso real; desta vez a razão
verdadeira existia e o TEMPO a descartou.*

**A RÉGUA MEDE O TEMPO, e não a frase.** Uma régua que conferisse o texto da
mensagem daria verde sobre este defeito — a mensagem estava lá, certinha, e
nunca chegava.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from hefesto_dualsense4unix.app import ipc_bridge

#: O que o daemon leva de verdade, medido no socket vivo em 08/09/2026 com os
#: quatro na mesa. O teto tem de caber isto com folga.
_MEDIDO_MS = 3070

#: Os atos que varrem as fontes do PulseAudio e por isso demoram. Cada um TEM de
#: passar o teto largo — o `_safe_call` sozinho reprova os três.
_ATOS_DE_AUDIO = (
    ("mic_canal_set_detalhado", (True,)),
    ("mic_volume_set_detalhado", (50,)),
    ("speaker_set_detalhado", (50,)),
)


def test_o_teto_cabe_o_que_o_daemon_leva() -> None:
    """O teto é maior que o medido, com folga que se escreve.

    MORDE: baixe `_TETO_DO_ATO_DE_AUDIO` para 3.0 e esta régua reprova — três
    segundos "cabem" o medido de hoje e não cabem uma máquina mais carregada,
    que é o dia em que o defeito volta parecendo daemon quebrado.
    """
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
    """Cada ato de áudio passa o teto largo ao transporte — medido, não lido.

    A régua CHAMA a função e olha o que chegou ao `_safe_call`. Ler o texto do
    arquivo diria que a linha existe; só a chamada diz que ela é a que roda.

    MORDE: tire o `timeout=` de qualquer um dos três e o caso dele reprova
    nomeando a função.
    """
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
    """A folga é dos TRÊS atos de áudio, e de mais ninguém.

    Alargar o teto de todo o transporte pagaria o preço no lugar errado: o tique
    da tela roda a 2 Hz e um daemon travado prenderia a janela. A folga é
    cirúrgica de propósito.
    """
    padrao = inspect.signature(ipc_bridge._safe_call).parameters["timeout"].default
    assert padrao == 0.25, (
        f"o teto PADRÃO do transporte virou {padrao!r}. A cura de 08/09 é dos "
        f"três atos de áudio, que varrem o PulseAudio; alargar o padrão prende "
        f"a janela no tique quando o daemon trava.")
