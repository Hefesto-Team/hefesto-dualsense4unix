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

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
exigir_gi_real("status: a bateria cala com a mesa vazia")

import ast
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

#: O payload medido em 23/08 às 21h53, campo a campo. O topo afirma; a lista
#: nega. Nada aqui é inventado para o teste.
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

#: A mesma mesa, com um controle DE VERDADE na lista. É a contraprova: sem
#: ela, "não mostrar nunca" passaria neste arquivo inteiro.
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
    """**A mordida:** arranque a checagem da lista em `_bateria_da_mesa` — o
    ``if mesa_publicada and not ...`` — e a barra volta a escrever "75 %" com
    a mesa vazia. O teste reprova citando o payload inteiro.
    """
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
    """A contraprova, e ela é obrigatória.

    "Não mostrar nunca" passaria no teste de cima e seria um defeito pior —
    a T12 não é para tirar o número, é para ele parar de aparecer quando a
    fonte não existe.

    **A mordida:** troque o corpo de `_bateria_da_mesa` por um
    ``return (0.0, "— %")`` fixo e este teste reprova.
    """
    fracao, texto = S._bateria_da_mesa(_MESA_COM_UM_CONTROLE)
    assert texto == "75 %", (
        f"com um controle conectado na lista a barra escreveu {texto!r} em "
        "vez do número: a guarda da mesa vazia comeu o caso normal"
    )
    assert abs(fracao - 0.75) < 1e-9, f"fração {fracao!r} não acompanha o texto"


def test_sem_lista_publicada_o_topo_continua_valendo() -> None:
    """Hipótese tem de explicar o que JÁ funcionava.

    Daemon antigo, ou payload parcial, não publica ``controllers``. Recusar o
    número aí seria trocar um erro por outro: **ausência de lista não é
    evidência de mesa vazia**, e a aba ficaria muda contra um daemon que só
    fala a língua antiga.

    **A mordida:** faça a guarda disparar sem olhar se a lista existe e este
    teste reprova.
    """
    _fracao, texto = S._bateria_da_mesa(
        {"connected": True, "transport": "usb", "battery_pct": 88}
    )
    assert texto == "88 %", (
        f"sem a lista `controllers` no payload a barra escreveu {texto!r}: a "
        "guarda passou a tratar 'o daemon não contou' como 'não há ninguém'"
    )


def test_a_barra_nao_le_o_topo_por_fora_da_guarda() -> None:
    """O portão: `_render_slow_state` não pode voltar a ler `battery_pct`.

    O defeito não era a falta de uma checagem — era a barra ter uma fonte
    PRÓPRIA, lida direto do topo do payload, ao lado da fonte que a aba usa
    para todo o resto. Enquanto existirem duas leituras, a guarda pode ser
    burlada por acidente na próxima leva que mexer nesse método.

    **A mordida:** devolva o ``battery = state.get("battery_pct")`` ao
    `_render_slow_state` e o portão reprova nomeando a linha.
    """
    arvore = ast.parse(_STATUS_PY.read_text(encoding="utf-8"))
    alvo = next(
        (
            no
            for no in ast.walk(arvore)
            if isinstance(no, ast.FunctionDef) and no.name == "_render_slow_state"
        ),
        None,
    )
    assert alvo is not None, "o `_render_slow_state` sumiu — o teste perdeu o alvo"

    leituras = [
        f"status_actions.py:{no.lineno}"
        for no in ast.walk(alvo)
        if isinstance(no, ast.Call)
        and isinstance(no.func, ast.Attribute)
        and no.func.attr == "get"
        and no.args
        and isinstance(no.args[0], ast.Constant)
        and no.args[0].value == "battery_pct"
    ]
    assert not leituras, (
        "o `_render_slow_state` voltou a ler `battery_pct` do topo do payload "
        f"por conta própria: {leituras}. A única leitura da bateria da aba é "
        "`_bateria_da_mesa`, que olha o topo E a lista"
    )
