"""O teto do multiplicador de rumble tem UM dono (HARM-19).

A faixa valeu três valores ao mesmo tempo:

  - `profiles.schema.RumbleConfig.custom_mult` — 0.0 a **2.0**
  - `ipc_handlers._handle_rumble_policy_custom` — recusava mult > **1.0**
  - o trilho da Intensidade na tela — até **200%**

O slider manda `valor / 100` para o `rumble.policy_custom`, então de 101% em
diante a usuária levava um erro de validação — que a aba de gatilhos ainda
reportava como "daemon offline?". O `BUG-RUMBLE-CUSTOM-MULT-CAP-01` subiu o
slider para 200% justamente porque "o schema aceita custom_mult até 2.0", e
esqueceu do handler.

A cura foi alinhar o handler ao schema (não truncar a UI): acima de 100% o
multiplicador AMPLIFICA o que o jogo pediu, que é a razão de a faixa existir.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.profiles.schema import RUMBLE_CUSTOM_MULT_MAX, RumbleConfig

#: O TETO DO TRILHO, na TELA QUE ELA USA — `interface/paginas/05-vibracao.html`,
#: o `<input type="range" data-campo="mult-pos">` da coluna Intensidade.
#:
#: **A FONTE MUDOU EM 06/09/2026** (`GTK-3`, primeira volta). Até aqui esta
#: leitura era o `<property name="upper">` do `rumble_policy_adj` no
#: `gui/main.glade` — a janela GTK, que sai inteira
#: (`D-0609-GTK-LEVA-INTEIRA`). A pergunta medida é a MESMA e continua sendo
#: leitura de arquivo, não número digitado: *o que a tela OFERECE é o que o
#: esquema do perfil ACEITA?*
_TRILHO_DA_INTENSIDADE = re.compile(
    r'<input[^>]*type="range"[^>]*data-campo="mult-pos"[^>]*>'
)


def _atributo_do_trilho(nome: str) -> float:
    """`max`/`min`/`step` do trilho da Intensidade, lido da página publicada."""
    pagina = (
        Path(__file__).resolve().parents[2]
        / "src" / "hefesto_dualsense4unix"
        / "interface" / "paginas" / "05-vibracao.html"  # noqa-acento (pasta)
    ).read_text(encoding="utf-8")
    achado = _TRILHO_DA_INTENSIDADE.search(pagina)
    assert achado is not None, (
        "o trilho `mult-pos` sumiu de `05-vibracao.html` — a coluna "
        "Intensidade perdeu o ajuste livre, ou a régua ficou cega"
    )
    valor = re.search(rf'{nome}="([\d.]+)"', achado.group(0))
    assert valor is not None, f"o trilho da Intensidade perdeu o atributo {nome}"
    return float(valor.group(1))


def test_o_slider_oferece_exatamente_o_que_o_schema_aceita() -> None:
    """O slider é `mult * 100` — a faixa dele é o teto do schema em porcento."""
    assert _atributo_do_trilho("max") == RUMBLE_CUSTOM_MULT_MAX * 100


def test_o_schema_aceita_o_proprio_teto() -> None:
    RumbleConfig(policy="custom", custom_mult=RUMBLE_CUSTOM_MULT_MAX)


def test_o_schema_recusa_acima_do_teto() -> None:
    with pytest.raises(ValueError, match="custom_mult fora"):
        RumbleConfig(policy="custom", custom_mult=RUMBLE_CUSTOM_MULT_MAX + 0.1)


# SATURA-01 (11/08/2026): 150 e 200 saíram porque o teto voltou a 100%. Os
# valores desta lista têm de ser os que o SLIDER produz — derivá-los do teto
# em vez de escrevê-los à mão mantém o teste amarrado ao dono único.
@pytest.mark.parametrize(
    "percentual", [0, 50, int(RUMBLE_CUSTOM_MULT_MAX * 100)]
)
def test_todo_valor_do_slider_passa_no_handler(percentual: int) -> None:
    """O que a UI oferece, o daemon aceita — em TODA a faixa.

    Era o defeito: 150% no slider virava mult=1.5 e o handler levantava
    ValueError. Este teste percorre a régua inteira, não só as pontas.
    """
    from hefesto_dualsense4unix.daemon import ipc_handlers

    mult = percentual / 100.0
    fonte = Path(ipc_handlers.__file__).read_text(encoding="utf-8")
    assert "RUMBLE_CUSTOM_MULT_MAX" in fonte, (
        "o handler voltou a ter um teto próprio — importe do schema"
    )
    assert 0.0 <= mult <= RUMBLE_CUSTOM_MULT_MAX


def test_ninguem_mais_hardcodeia_o_teto() -> None:
    """Um dono só: nem o handler nem a tela repetem o número."""
    from hefesto_dualsense4unix.daemon import ipc_handlers

    fonte = Path(ipc_handlers.__file__).read_text(encoding="utf-8")
    trecho = fonte[fonte.index("_handle_rumble_policy_custom"):][:900]
    assert "<= 1.0" not in trecho, "teto de 1.0 hardcoded voltou ao handler"


# ===========================================================================
# O NÚMERO MEDIDO TEM UM DONO SÓ — as três rotas leem a MESMA memória
# ===========================================================================
#
# BG-02 (26/08/2026). O debounce do "auto" (que impede a força de pular no meio
# da partida) era lido de DOIS lugares:
#
#   - `daemon._last_auto_mult` / `_last_auto_change_at` — a memória viva,
#     declarada em `daemon/protocols.py`, escrita pelo tique de 200 ms
#     (`subsystems/rumble.reassert_rumble`) e pelo force-feedback do jogo
#     (`subsystems/gamepad._game_rumble_mult`);
#   - `daemon._rumble_engine._last_auto_*` — na rota do `rumble.set`, que é a
#     que o "Aplicar" da aba atravessa. Esse atributo **nunca é instanciado**:
#     a leitura começava sempre de 0,7/0,0 e o resultado era jogado fora pelo
#     `if rumble_engine is not None`.
#
# Duas contas para o mesmo número: a intensidade que ela sente pulava conforme
# qual rota mexeu por último.

from types import SimpleNamespace
from unittest.mock import MagicMock

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon import ipc_rumble_policy
from hefesto_dualsense4unix.daemon.ipc_rumble_policy import (
    apply_rumble_policy,
    memoria_viva_do_auto,
)
from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems.rumble import (
    AUTO_DEBOUNCE_SEC,
    reassert_rumble,
)

#: O instante de referência das mordidas. Qualquer número serve — o que importa
#: é ele NÃO ser 0.0, que é o valor que o `_effective_mult` trata como "nunca
#: mudou" e que faz o debounce liberar a primeira troca.
T0 = 1000.0

#: Bateria acima do degrau de cima do "auto" (>50%) → alvo 1,0.
BATERIA_CHEIA = 60
#: Bateria abaixo do degrau de baixo (<20%) → alvo 0,3.
BATERIA_NO_FIM = 10


class _ControleQueAnota:
    """Backend mínimo: guarda os pares que chegaram, e nada mais.

    Sem `set_rumble_for` de propósito — `escrever_rumble_no_dono` cai no
    caminho histórico de broadcast, que é o que interessa aqui (a mira por MAC
    tem mordida própria em `test_mesa_cheia_05_o_rumble_mira.py`).
    """

    def __init__(self) -> None:
        self.pares: list[tuple[int, int]] = []

    def set_rumble(self, weak: int, strong: int) -> None:
        self.pares.append((weak, strong))


def _mesa(bateria: int) -> SimpleNamespace:
    """Daemon de bancada: config de verdade, store de verdade, backend anotador.

    `_last_auto_mult=0.7` / `_last_auto_change_at=0.0` são os valores com que o
    daemon real nasce (`daemon/lifecycle.py`), e são exatamente os que a rota
    quebrada inventava do nada a cada chamada.
    """
    store = StateStore()
    store.update_controller_state(
        ControllerState(
            battery_pct=bateria, l2_raw=0, r2_raw=0, connected=True, transport="bt"
        )
    )
    cfg = DaemonConfig()
    cfg.rumble_policy = "auto"  # type: ignore[assignment]
    cfg.rumble_active = (200, 200)
    cfg.rumble_active_uniq = None
    return SimpleNamespace(
        config=cfg,
        store=store,
        controller=_ControleQueAnota(),
        _last_auto_mult=0.7,
        _last_auto_change_at=0.0,
    )


def _congela_o_relogio(monkeypatch: pytest.MonkeyPatch, quando: float) -> None:
    """`apply_rumble_policy` lê `_time.monotonic()` por dentro — sem injeção.

    Trocar o módulo inteiro por um `SimpleNamespace` mantém a troca dentro
    de `ipc_rumble_policy` (o `time` global da suíte fica intacto).
    """
    monkeypatch.setattr(
        ipc_rumble_policy, "_time", SimpleNamespace(monotonic=lambda: quando)
    )


def test_as_tres_rotas_leem_a_mesma_memoria(monkeypatch: pytest.MonkeyPatch) -> None:
    """A MORDIDA de BG-02: `rumble.set`, depois o poll loop, mesmo número.

    O roteiro é o da partida real: ela fixa a vibração com a bateria cheia
    (o "auto" sobe para 1,0), a bateria despenca segundos depois, e o tique de
    200 ms pergunta de novo DENTRO da janela de debounce. Com uma memória só, o
    tique responde 1,0 — a força não pula no meio da partida, que é a promessa
    inteira do debounce.

    Devolvendo a leitura ao `_rumble_engine`, a rota do `rumble.set` não grava
    nada: o poll loop encontra `(0,7 / 0,0)`, lê `last_auto_change_at == 0.0`
    como "nunca mudou", libera a troca na hora e entrega 0,3. Os dois números
    divergem e as mensagens abaixo imprimem os dois.
    """
    daemon = _mesa(BATERIA_CHEIA)
    _congela_o_relogio(monkeypatch, T0)

    eff = apply_rumble_policy(daemon, 200, 200)
    assert eff == (200, 200), f"bateria cheia no auto é mult 1,0; veio {eff}"

    assert (daemon._last_auto_mult, daemon._last_auto_change_at) == (1.0, T0), (
        "a rota do `rumble.set` NÃO escreveu na memória viva do daemon: "
        f"esperava (1.0, {T0}), veio "
        f"({daemon._last_auto_mult}, {daemon._last_auto_change_at}). "
        "Esse par é o que `reassert_rumble` e `_game_rumble_mult` leem no "
        "tique seguinte — sem ele são duas contas para o mesmo número"
    )

    # A bateria despenca, e o tique de 200 ms chega DENTRO do debounce.
    daemon.store.update_controller_state(
        ControllerState(
            battery_pct=BATERIA_NO_FIM,
            l2_raw=0,
            r2_raw=0,
            connected=True,
            transport="bt",
        )
    )
    reassert_rumble(daemon, T0 + (AUTO_DEBOUNCE_SEC / 2.0))

    assert daemon.controller.pares == [(200, 200)], (
        "o poll loop discordou do `rumble.set` DENTRO da janela de debounce: "
        f"o `rumble.set` aplicou (200, 200) e o tique aplicou "
        f"{daemon.controller.pares}. Com uma memória só, o tique herda o 1,0 "
        f"gravado em {T0} e não troca de degrau; com duas, ele acha que nunca "
        "houve mudança e cai para 0,3 no meio da partida"
    )
    assert daemon._last_auto_mult == 1.0, (
        f"o debounce mudou de degrau {AUTO_DEBOUNCE_SEC / 2.0} s depois — "
        f"multiplicador {daemon._last_auto_mult}"
    )


def test_passado_o_debounce_o_degrau_troca(monkeypatch: pytest.MonkeyPatch) -> None:
    """O outro lado: régua que só sabe segurar não é régua.

    Sem este caso, o de cima passaria também numa cura que simplesmente
    congelasse o multiplicador para sempre.
    """
    daemon = _mesa(BATERIA_CHEIA)
    _congela_o_relogio(monkeypatch, T0)
    apply_rumble_policy(daemon, 200, 200)

    daemon.store.update_controller_state(
        ControllerState(
            battery_pct=BATERIA_NO_FIM,
            l2_raw=0,
            r2_raw=0,
            connected=True,
            transport="bt",
        )
    )
    reassert_rumble(daemon, T0 + AUTO_DEBOUNCE_SEC + 0.1)

    assert daemon.controller.pares == [(60, 60)], (
        "passada a janela de debounce o degrau tinha de cair para 0,3 "
        f"(200 * 0,3 = 60); veio {daemon.controller.pares}"
    )
    assert daemon._last_auto_mult == 0.3


def test_a_rota_do_aplicar_herda_o_que_o_poll_loop_gravou(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E na ordem inversa: quem escreve primeiro é o tique, e o `set` herda.

    A memória é de mão dupla — provar só um sentido deixaria metade do defeito
    viva.
    """
    daemon = _mesa(BATERIA_CHEIA)
    reassert_rumble(daemon, T0)
    assert (daemon._last_auto_mult, daemon._last_auto_change_at) == (1.0, T0)

    daemon.store.update_controller_state(
        ControllerState(
            battery_pct=BATERIA_NO_FIM,
            l2_raw=0,
            r2_raw=0,
            connected=True,
            transport="bt",
        )
    )
    _congela_o_relogio(monkeypatch, T0 + (AUTO_DEBOUNCE_SEC / 2.0))

    eff = apply_rumble_policy(daemon, 200, 200)
    assert eff == (200, 200), (
        "o `rumble.set` ignorou o degrau que o poll loop tinha acabado de "
        f"gravar e recalculou por conta própria: veio {eff}"
    )


def test_a_memoria_viva_blinda_o_duble_que_responde_qualquer_coisa() -> None:
    """`MagicMock` devolve um `Mock` para todo atributo — e ele não é número.

    Sem a blindagem, `now - last_auto_change_at` estoura `TypeError` dentro de
    `_effective_mult` e a vibração morre no dublê. Com ela, o dublê cai nos
    defaults do primeiro tique, que é o comportamento honesto.
    """
    assert memoria_viva_do_auto(MagicMock()) == (0.7, 0.0)
    assert memoria_viva_do_auto(SimpleNamespace()) == (0.7, 0.0)
    assert memoria_viva_do_auto(
        SimpleNamespace(_last_auto_mult=True, _last_auto_change_at=False)
    ) == (0.7, 0.0), "booleano não é multiplicador — `isinstance(True, int)` engana"
    assert memoria_viva_do_auto(
        SimpleNamespace(_last_auto_mult=0.3, _last_auto_change_at=T0)
    ) == (0.3, T0)


def test_ninguem_mais_le_o_rumble_engine_na_rota_do_set() -> None:
    """O caminho morto saiu da árvore, e não só ficou sem efeito.

    Um `_rumble_engine` lido "só por compatibilidade" voltaria a ser a segunda
    fonte no primeiro dia em que alguém o instanciasse.
    """
    fonte = Path(ipc_rumble_policy.__file__).read_text(encoding="utf-8")
    corpo = fonte[fonte.index("def apply_rumble_policy") :]
    assert "_rumble_engine" not in corpo, (
        "`apply_rumble_policy` voltou a consultar `daemon._rumble_engine` — "
        "o atributo que não é instanciado em `src/` em lugar nenhum"
    )
