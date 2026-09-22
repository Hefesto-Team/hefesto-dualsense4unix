"""O alto-falante daquele controle TEM som saindo — o dublê de uma linha.

**Nascido da RADIO-AFOGADO-01, 22/09/2026, e compartilhado de propósito.**
Naquele dia a ponte do som deixou de subir em silêncio: ela escrevia 93,75
reports de 334 B por segundo em cada DualSense do rádio, tocasse alguém ou
não, e com três de pé a mesa dela caía em 11 a 89 segundos.

Seis réguas de FIAÇÃO — quem recebe qual `hidraw`, em que ordem a ponte sobe,
o bit do microfone em cada report — herdaram o mundo de antes: elas chamam
`_casar_as_pontes` e esperam uma ponte do outro lado. Elas não medem o portão
novo (esse tem régua própria,
``test_a_ponte_do_som_nao_afoga_o_radio.py``); medem o que a ponte faz DEPOIS
de existir. Então elas dizem que há som, e seguem medindo o que prometem.

**O DUBLÊ SÓ ACENDE O ALTO-FALANTE.** O `hefesto_som_<hex6>` responde *"está
tocando"*; qualquer outro nome — e o endpoint de quatro canais da háptica é
outro nome — responde *"não"*, que é exatamente o que essas réguas viam antes,
quando o `pactl` de verdade não achava nó nenhum com aquele nome forjado.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import alto_falante_bt as af


def todo_alto_falante_toca(monkeypatch: pytest.MonkeyPatch) -> None:
    """Todo `hefesto_som_<hex6>` tem stream; nenhum outro nó tem."""

    def _toca(nome: Any, *_a: Any, **_k: Any) -> bool:
        return str(nome or "").startswith(af.PREFIXO_SINK_DO_SOM)

    monkeypatch.setattr(af, "sink_esta_tocando", _toca)
