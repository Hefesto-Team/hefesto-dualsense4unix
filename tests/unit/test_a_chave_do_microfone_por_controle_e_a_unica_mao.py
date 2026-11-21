"""A chave do microfone por controle é a única mão (a variável de ambiente antiga saiu).

A-CHAVE-DO-MICROFONE-POR-CONTROLE-E-A-UNICA-MAO-01. Antes, com a variável no ambiente do
serviço, `alvos()` devolvia todo nó antes de consultar a recusa, e o `daemon.state_full`
respondia `enabled` verdadeiro pela variável: o microfone desligado na tela de um controle ganhava a
ponte mesmo assim. Curas, cada uma com a sua mordida:

* `alvos()` só tira o recusado na tela, com a variável antiga no ambiente ou fora dele
  (mordida: `return list(nos)` de volta no início de `alvos`);
* o `enabled` do `state_full` vem só do que foi pedido na tela (mordida: o `or` da variável de
  volta no tratador);
* a variável não existe mais em `src/` nem em `tests/` (mordida: a constante de volta).

Quatro controles pelo rádio, dois no mesmo adaptador; o que passa ao cabo some da lista de nós
(no cabo não há ponte) e volta: a recusa de cada um vale em qualquer ordem.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems.bt_mic import (
    BtMicSubsystem,
    RegistroDePedidosDeCanal,
)
from tests.unit.test_a_barra_do_radio_sai_do_zero_quando_o_mic_liga import (  # noqa: F401
    _state_full,
    isolated_profiles_dir,
    servidor,
)

A = "aabbcc000001"
B = "aabbcc000002"
C = "aabbcc000003"
D = "aabbcc000004"

VARIAVEL_ANTIGA = "HEFESTO_DUALSENSE4UNIX_" + "BT_MIC"

RAIZ = Path(__file__).resolve().parents[2]


class _No:
    def __init__(self, uniq: str) -> None:
        self.uniq = uniq
        self.caminho = f"/dev/hidraw-{uniq}"


class _Config:
    def __init__(self, recusados: frozenset[str]) -> None:
        self._recusados = recusados

    def bt_mic_recusados(self) -> frozenset[str]:
        return self._recusados

    def bt_mic_uniqs(self) -> frozenset[str]:
        return frozenset()


def _subsistema(recusados: frozenset[str]) -> BtMicSubsystem:
    sub = BtMicSubsystem(registro=RegistroDePedidosDeCanal())
    sub._config = _Config(recusados)
    return sub


def _quem(sub: BtMicSubsystem, *uniqs: str) -> list[str]:
    return sorted(no.uniq for no in sub.alvos([_No(u) for u in uniqs]))


@pytest.mark.parametrize("variavel", [None, "1", "true", "on"])
def test_o_controle_desligado_na_tela_nao_ganha_a_ponte_com_a_variavel_antiga_no_ambiente(
    monkeypatch: pytest.MonkeyPatch, variavel: str | None
) -> None:
    """Quatro no rádio, B desligado na tela: B fora, os outros três dentro, venha o que vier."""
    if variavel is None:
        monkeypatch.delenv(VARIAVEL_ANTIGA, raising=False)
    else:
        monkeypatch.setenv(VARIAVEL_ANTIGA, variavel)
    sub = _subsistema(frozenset({B}))

    assert _quem(sub, A, B, C, D) == [A, C, D]


def test_o_que_passa_ao_cabo_e_volta_nao_leva_nem_perde_a_recusa_de_ninguem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A e B no mesmo adaptador, C e D em outros; D vai ao cabo e volta; B segue recusado."""
    monkeypatch.setenv(VARIAVEL_ANTIGA, "1")
    sub = _subsistema(frozenset({B}))

    assert _quem(sub, A, B, C, D) == [A, C, D]
    assert _quem(sub, A, B, C) == [A, C], "D no cabo: não há nó de rádio dele"
    assert _quem(sub, A, B, C, D) == [A, C, D], "D de volta ao rádio: a ponte dele volta"

    sub._config = _Config(frozenset({D}))
    assert _quem(sub, A, B, C, D) == [A, B, C], "a recusa mudou de dono e a regra seguiu"
    sub._config = _Config(frozenset())
    assert _quem(sub, A, B, C, D) == [A, B, C, D]


@pytest.mark.asyncio
async def test_o_state_full_nao_diz_enabled_pela_variavel_antiga(
    servidor: Any, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    monkeypatch.setenv(VARIAVEL_ANTIGA, "1")
    socket_path, _daemon = servidor

    bloco = (await _state_full(socket_path))["bt_mic"]

    assert bloco["enabled"] is False, "a variável antiga ainda liga o `enabled` do state_full"


def test_a_variavel_antiga_nao_existe_em_src_nem_em_tests() -> None:
    achados = []
    for pasta in ("src", "tests"):
        for arquivo in (RAIZ / pasta).rglob("*.py"):
            if VARIAVEL_ANTIGA in arquivo.read_text(encoding="utf-8"):
                achados.append(str(arquivo.relative_to(RAIZ)))
    assert achados == [], f"a variável antiga voltou: {sorted(achados)}"
