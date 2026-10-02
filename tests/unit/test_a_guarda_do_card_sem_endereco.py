"""A guarda do card SEM ENDEREÇO — o som que ia parar no controle errado.

Item 1.10 do índice da mesa cheia (`docs/process/sprints/
2026-08-13-INDICE-a-mesa-cheia-cada-jogador-na-cor-dele.md`, §7).

**O defeito.** Toda saída de som do card viaja com o `uniq` do controle —
`mic.set`, `speaker.set` (volume, mudo, soltar e canal) e a ponte por rádio.
Sem `uniq`, o daemon cai no controle **PRIMÁRIO**: ela clica no bloco do
Controle 3, lê "Controle 3 — BT" no título, e quem muda de volume é o
Controle 1. E `uniq` ausente não é hipótese — o `_key_to_uniq` do backend
devolve `None` de propósito sempre que a key do handle é um caminho
(`/dev/hidrawN`), que é o que sobra quando o MAC não pôde ser lido do sysfs.

**A cura, e as duas metades dela.** Desligar o bloco de som E dizer por quê:
um bloco desabilitado sem explicação é um defeito do mesmo tamanho — ela leria
"o produto quebrou".

**O caso vem do payload REAL de quatro controles**
(`tests/fixtures/state_full_quatro_controles.json`, medido em 14/08/2026 com
dois controles no cabo e dois no rádio). O card sem endereço é construído
ARRANCANDO o `uniq` de um deles, e não inventado: um dublê só contém o que
quem o escreveu já sabia — este traz o `audio` com o microfone captando, que é
justamente o estado em que o botão de mudo fica sensível e o gesto sai.

**Por que há DOIS estados sem endereço aqui, e não um** (correção de 14/08/2026,
depois de a primeira versão ser refutada). A tranca de dentro do gesto
(`_som_sem_alvo`) está em SEIS gestos, mas com o payload cru só QUATRO chegam
nela: o "Silenciar" e o "Soltar" voltam antes, em `acao.sensivel is False`,
porque o fixture não traz a chave `speaker`. Arrancando as duas linhas
`if self._som_sem_alvo(): return` desses dois handlers, os testes ficavam
VERDES — cura arrancada com teste verde não é cura testada.

A proteção a montante **não é garantia**: ela depende do payload, não da regra.
E o payload que a derruba é o que o daemon publica de verdade — em
`daemon/ipc_handlers._merge_audio` o `uniq` do próprio entry é passado adiante,
e `speaker_state_for(None)` cai em `_handle_for(None)`, que devolve o handle do
**PRIMÁRIO** (`core/backend_pydualsense.py`). Ou seja: assim que o primário tem
a posse do volume, o card SEM endereço recebe a chave `speaker` do primário, o
"Silenciar" e o "Soltar" ficam sensíveis, e a tranca passa a ser a única coisa
entre o clique dela e um `speaker.set` no controle de outra pessoa. É a mesma
regra "sem `uniq` = o primário" que causa o defeito, vista do lado da LEITURA.

Por isso os gestos são disparados nos dois estados — sem posse e com posse —, e
sempre pela mesma função (`_disparar_os_seis_gestos`), para que a lista dos seis
não possa se afastar entre o caso sem endereço e o caso com endereço.

**Continuam seis em 16/08/2026, mas um deles trocou.** O interruptor "Pelo
rádio" saiu do card (ponte insegura — `test_o_interruptor_do_mic_por_bluetooth`)
e o controle deslizante do microfone tomou o lugar dele, na lista e na tela. Não
é substituição de conveniência: `mic.volume.set` sem `uniq` cai no controle
PRIMÁRIO exatamente como os outros cinco, então a vaga na guarda tinha dono
antes de estar vazia.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "state_full_quatro_controles.json"
)


def _controles() -> list[dict[str, Any]]:
    """Os quatro controles do payload real, cópia profunda por teste."""
    dados = json.loads(FIXTURE.read_text(encoding="utf-8"))
    controles = dados["controllers"]
    assert len(controles) == 4, "o fixture da mesa cheia tem de ter QUATRO"
    return [copy.deepcopy(c) for c in controles]


def _controle_sem_endereco() -> dict[str, Any]:
    """O Controle 3 do payload real, com o endereço ARRANCADO."""
    entry = _controles()[2]
    assert entry["transport"] == "bt"
    assert not entry.get("is_primary"), "o caso perde o sentido no primário"
    entry.pop("uniq")
    return entry


def _com_posse_do_volume(
    entry: dict[str, Any], *, volume: int = 137, muted: bool = False
) -> dict[str, Any]:
    """Acrescenta a chave ``speaker`` do jeito que o DAEMON a publica."""
    bloco = {"volume": volume, "muted": muted}
    entry["speaker"] = dict(bloco)
    inputs = entry.get("inputs")
    if isinstance(inputs, dict):
        inputs["speaker"] = dict(bloco)
    return entry


class TestNaTela:
    """A metade que só o GTK real prova."""


    @staticmethod
    def _espiar_o_ipc(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Any]]:
        """Troca as três saídas de som por espiões e devolve a lista de pedidos."""
        from hefesto_dualsense4unix.app import ipc_bridge

        pedidos: list[tuple[str, Any]] = []

        def _direto(fn: Any, on_success: Any = None, on_failure: Any = None) -> None:
            resultado = fn()
            if on_success is not None:
                on_success(resultado)

        monkeypatch.setattr(ipc_bridge, "run_in_thread", _direto)
        monkeypatch.setattr(
            ipc_bridge,
            "mic_set",
            lambda valor, uniq=None: pedidos.append(("mic.set", uniq)) or True,
        )
        monkeypatch.setattr(
            ipc_bridge,
            "speaker_set",
            lambda **kw: pedidos.append(("speaker.set", kw.get("uniq"))) or True,
        )
        monkeypatch.setattr(
            ipc_bridge,
            "mic_volume_set_detalhado",
            lambda **kw: pedidos.append(("mic.volume.set", kw.get("uniq")))
            or {"status": "ok", "por_uniq": True},
        )
        return pedidos


    def test_nenhum_gesto_sem_endereco_vira_pedido_ao_daemon(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A MORDIDA: com a guarda arrancada, cada gesto vira byte no PRIMÁRIO."""
        pedidos = self._espiar_o_ipc(monkeypatch)

        card = self._card(_controle_sem_endereco())
        self._disparar_os_seis_gestos(card)

        assert pedidos == [], (
            "o card sem endereço mandou som ao daemon: cada pedido destes "
            f"cai no controle PRIMÁRIO, não neste card — {pedidos}"
        )


