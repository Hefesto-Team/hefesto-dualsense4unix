"""STATUS-DIZ-O-QUE-VÊ-01/T12 — a barra de bateria para de afirmar 75 % de ninguém.

Duas medições se somam neste defeito, e nenhuma delas é hipótese:

* o mapa de canais **rebaixou** `energia.bateria.percentual` do DualSense de
  `medido` para inferência de código em **15/08/2026 (D-14)** — *"a evidência
  registrada descreve LEITURA DE FONTE (arquivo, linha, grep), não medição no
  aparelho"*;
* e o daemon publica, no MESMO payload, um topo que discorda da lista. Medido
  em 23/08/2026 às 21h53, com **zero** DualSense no sistema:

      daemon.status                        -> connected: true, battery_pct: 75
      daemon.state_full (topo)             -> connected: true, battery_pct: 75
      daemon.state_full ["controllers"][0] -> connected: false, transport: null
      controller.list                      -> connected: false, transport: null

  A barra da aba Status escrevia **75 %** — de um controle que não existe.

É a afirmação mais silenciosa e mais crível da aba: um número exato, numa
barra, sem adjetivo. Por isso é a mais cara quando erra.

**O que esta leva NÃO cura:** as duas fontes de `connected` no mesmo payload.
Essa é a Z5, e esta régua a CONSOME — se a Z5 escorregar, esta guarda ainda
segura a tela, mas o daemon continua publicando as duas versões.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("status: a bateria cala com a mesa vazia")

from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin as S

_STATUS_PY = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "hefesto_dualsense4unix"
    / "app"
    / "actions"
    / "status_actions.py"
)

_MESA_VAZIA_COM_TOPO_MENTINDO: dict[str, Any] = {
    "connected": True,
    "transport": "bt",
    "battery_pct": 75,
    "controllers": [
        {
            "index": 0,
            "connected": False,
            "transport": None,
            "player": None,
            "uniq": None,
        }
    ],
}

_MESA_COM_UM_CONTROLE: dict[str, Any] = {
    "connected": True,
    "transport": "usb",
    "battery_pct": 75,
    "controllers": [
        {
            "index": 0,
            "connected": True,
            "transport": "usb",
            "is_primary": True,
            "player_slot": 1,
            "uniq": "aa:bb:cc:00:00:01",
            "battery_pct": 75,
        }
    ],
}


def test_a_bateria_cala_com_a_mesa_vazia() -> None:
    """**A mordida:** arranque a checagem da lista em `_bateria_da_mesa` — o"""
    fracao, texto = S._bateria_da_mesa(_MESA_VAZIA_COM_TOPO_MENTINDO)

    assert "%" not in texto or texto == "— %", (
        f"a barra escreveu {texto!r} com ZERO controles na lista do daemon. "
        f"O payload medido: {_MESA_VAZIA_COM_TOPO_MENTINDO}. O topo afirma "
        "75 % e a lista diz que não há aparelho nenhum — a barra não pode "
        "escolher a metade que soa melhor"
    )
    assert fracao == 0.0, (
        f"a barra ficou preenchida em {fracao:.0%} com a mesa vazia: o "
        "desenho afirma o que o texto acabou de recusar"
    )


def test_a_bateria_continua_dizendo_o_numero_com_controle_na_mesa() -> None:
    """A contraprova, e ela é obrigatória."""
    fracao, texto = S._bateria_da_mesa(_MESA_COM_UM_CONTROLE)
    assert texto == "75 %", (
        f"com um controle conectado na lista a barra escreveu {texto!r} em "
        "vez do número: a guarda da mesa vazia comeu o caso normal"
    )
    assert abs(fracao - 0.75) < 1e-9, f"fração {fracao!r} não acompanha o texto"


def test_sem_lista_publicada_o_topo_continua_valendo() -> None:
    """Hipótese tem de explicar o que JÁ funcionava."""
    _fracao, texto = S._bateria_da_mesa(
        {"connected": True, "transport": "usb", "battery_pct": 88}
    )
    assert texto == "88 %", (
        f"sem a lista `controllers` no payload a barra escreveu {texto!r}: a "
        "guarda passou a tratar 'o daemon não contou' como 'não há ninguém'"
    )


