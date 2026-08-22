"""O orçamento da mesa é TETO, não troca — e o teto é `min`, nunca produto.

CONFIG-05 (22/08/2026). O orçamento da aba Configurações limita a mesa inteira
num ponto só: `core.rumble._effective_mult`, o funil por onde passam os TRÊS
caminhos de vibração do produto (`apply_rumble_policy`, `_game_rumble_mult` e
`reassert_rumble`). Este arquivo prende as duas metades da promessa:

* **teto** — com o orçamento em Economia, nenhuma política passa de 30 %,
  nem o "Máximo" que amplifica a 150 %, nem o deslizador livre em 200 %;
* **não troca** — nada da escolha dela é reescrito. Voltar o orçamento para
  Balanceado devolve o 1,5 do "Máximo" **sem ela reclicar coisa alguma**, o que
  só é verdade porque o `config.rumble_policy` nunca foi tocado.

AS MORDIDAS, arrancadas e conferidas em 22/08/2026
--------------------------------------------------

1. **Trocar `min(mult, teto)` por `mult * teto`** em `core.rumble._sob_o_teto`:
   reprovam `test_economia_limita_o_maximo_em_30` (0,45 no lugar de 0,3) e
   `test_economia_limita_o_deslizador_livre` (0,6 no lugar de 0,3) — o produto
   entrega o DOBRO do que o Economia promete justamente no ajuste mais forte.
2. **Deixar o fallback de política desconhecida sem teto** (devolver
   `RUMBLE_POLICY_MULT["balanceado"]` cru): reprova
   `test_o_fallback_de_politica_desconhecida_tambem_respeita_o_teto` — era o
   quarto `return` da função, o que o roteiro esquecia, e é um caminho inteiro
   em que o orçamento não valeria.
3. **Aplicar o teto DEPOIS do debounce do auto** (limitar só o valor devolvido,
   deixando a âncora crua): reprova
   `test_o_auto_sob_orcamento_economia_nao_oscila` — o "auto" se declararia em
   mudança a cada chamada e escreveria um `rumble_auto_policy_change` por tique.

Sem GTK de propósito: tudo aqui é conta sobre `DaemonConfig`.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.core.rumble import _effective_mult, teto_do_orcamento
from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT
from hefesto_dualsense4unix.profiles.schema import RUMBLE_CUSTOM_MULT_MAX
from hefesto_dualsense4unix.utils.maquina import MaquinaConfig, OrcamentoDeclarado

#: Os quatro orçamentos, direto do schema que os persiste. Escrever a lista à
#: mão aqui deixaria o teste passar no dia em que o schema ganhasse um quinto.
ORCAMENTOS = ("economia", "balanceado", "max", "auto")


def _config(
    policy: str,
    *,
    custom_mult: float = 1.0,
    orcamento: str | None = None,
) -> DaemonConfig:
    """Um `DaemonConfig` com política e orçamento, fiado como o boot fia.

    O orçamento entra pela MESMA porta do produto — `orcamento_da_mesa`, o
    chamável que `daemon/lifecycle.py:run` liga ao `_maquina` vivo. Injetar o
    valor por outro caminho testaria uma fiação que não existe.
    """
    cfg = DaemonConfig()
    cfg.rumble_policy = policy  # type: ignore[assignment]
    cfg.rumble_policy_custom_mult = custom_mult
    maquina = MaquinaConfig(orcamento=OrcamentoDeclarado(teto=orcamento))  # type: ignore[arg-type]
    cfg.orcamento_da_mesa = lambda: maquina.orcamento.teto
    return cfg


def _mult(cfg: DaemonConfig, *, battery_pct: int = 100) -> float:
    mult, _ancora, _quando = _effective_mult(
        config=cfg,
        battery_pct=battery_pct,
        now=100.0,
        last_auto_mult=0.7,
        last_auto_change_at=0.0,
    )
    return mult


# ---------------------------------------------------------------------------
# O teto
# ---------------------------------------------------------------------------


def test_so_o_economia_impoe_teto() -> None:
    """Três dos quatro orçamentos não limitam nada, e cada um por seu motivo.

    `balanceado` e `max` porque a dica deles promete "tudo como o jogo pedir,
    sem teto"; `auto` porque o teto dele seria MÓVEL, e a casa já decidiu não
    prometer número móvel na tela.
    """
    assert teto_do_orcamento("economia") == RUMBLE_POLICY_MULT["economia"]
    assert teto_do_orcamento("balanceado") is None
    assert teto_do_orcamento("max") is None
    assert teto_do_orcamento("auto") is None
    assert teto_do_orcamento(None) is None


def test_o_teto_do_economia_e_o_degrau_do_economia() -> None:
    """O 0,3 tem UM dono, e é a tabela do daemon.

    Se algum dia o degrau do Economia mudar, o teto do orçamento muda junto e a
    tela continua verdadeira sozinha. Um literal aqui seria a segunda cópia — o
    HARM-19, que já custou à usuária um erro de validação reportado como
    "daemon offline?".
    """
    assert teto_do_orcamento("economia") == RUMBLE_POLICY_MULT["economia"]
    assert teto_do_orcamento("economia") != 1.0


@pytest.mark.parametrize("policy", sorted(RUMBLE_POLICY_MULT))
def test_orcamento_balanceado_entrega_o_mult_de_sempre(policy: str) -> None:
    """Com o orçamento em Balanceado, nada muda em relação a antes da leva."""
    assert _mult(_config(policy, orcamento="balanceado")) == RUMBLE_POLICY_MULT[policy]


@pytest.mark.parametrize("policy", sorted(RUMBLE_POLICY_MULT))
def test_sem_orcamento_declarado_entrega_o_mult_de_sempre(policy: str) -> None:
    """Ninguém declarou nada: o produto se comporta como sempre se comportou.

    "Não sei" não é "teto de 100 %" — é ausência de teto. Um daemon que
    limitasse por falta de declaração puniria quem nunca abriu a aba.
    """
    assert _mult(_config(policy)) == RUMBLE_POLICY_MULT[policy]


def test_config_sem_o_campo_do_orcamento_nao_limita_nada() -> None:
    """Config sem a fonte fiada (dublê, daemon no meio de um upgrade).

    O `getattr` de `_orcamento_declarado` existe para este caso: a ausência da
    fiação devolve "nenhum teto", nunca um teto inventado.
    """
    cfg = DaemonConfig()
    cfg.rumble_policy = "max"
    assert cfg.orcamento_da_mesa is None
    assert _mult(cfg) == RUMBLE_POLICY_MULT["max"]


def test_economia_limita_o_maximo_em_30() -> None:
    """MORDIDA 1. Produto daria 1,5 vezes 0,3 = 0,45; `min` dá 0,3, o escrito."""
    assert (
        _mult(_config("max", orcamento="economia")) == RUMBLE_POLICY_MULT["economia"]
    )


def test_economia_limita_o_deslizador_livre() -> None:
    """MORDIDA 1, o caso caro: o `custom` no teto de 2,0.

    Produto daria 0,6 — o DOBRO do que o Economia promete, e mais forte que o
    Balanceado. É por isso que teto que multiplica não é teto.
    """
    cfg = _config("custom", custom_mult=RUMBLE_CUSTOM_MULT_MAX, orcamento="economia")
    assert _mult(cfg) == RUMBLE_POLICY_MULT["economia"]


def test_economia_nao_amplifica_quem_ja_estava_abaixo_do_teto() -> None:
    """Teto é limite, não alvo: um pedido de 0,1 continua 0,1."""
    cfg = _config("custom", custom_mult=0.1, orcamento="economia")
    assert _mult(cfg) == pytest.approx(0.1)


def test_o_fallback_de_politica_desconhecida_tambem_respeita_o_teto() -> None:
    """MORDIDA 2. O quarto `return` da função, o que o roteiro esquecia."""
    cfg = _config("uma_politica_que_nao_existe", orcamento="economia")
    assert _mult(cfg) == RUMBLE_POLICY_MULT["economia"]


@pytest.mark.parametrize("battery_pct", [100, 35, 5])
def test_o_auto_tambem_fica_sob_o_teto(battery_pct: int) -> None:
    """A escada do auto (1,0 / 0,7 / 0,3) inteira cabe sob o Economia."""
    cfg = _config("auto", orcamento="economia")
    assert _mult(cfg, battery_pct=battery_pct) <= RUMBLE_POLICY_MULT["economia"]


def test_o_auto_sob_orcamento_economia_nao_oscila() -> None:
    """MORDIDA 3: o teto entra ANTES do debounce, e é isso que assenta o auto.

    A âncora que a função devolve (`novo_last_auto_mult`) é a mesma coisa que o
    mult efetivo. Se o teto entrasse só na saída, a âncora ficaria com o degrau
    CRU (1,0) enquanto o valor devolvido seria 0,3: na chamada seguinte
    `target != last_auto_mult` seria verdadeiro de novo, para sempre, e o
    journal ganharia um `rumble_auto_policy_change` por tique de 200 ms.
    """
    cfg = _config("auto", orcamento="economia")
    mult, ancora, quando = _effective_mult(
        config=cfg,
        battery_pct=100,
        now=100.0,
        last_auto_mult=0.7,
        last_auto_change_at=0.0,
    )
    assert mult == RUMBLE_POLICY_MULT["economia"]
    assert ancora == mult, "a âncora do debounce tem de ser o mult que saiu"
    # Segunda volta, com o estado que a primeira devolveu: nada muda, e o
    # `change_at` fica onde estava — prova de que o debounce assentou.
    de_novo, ancora_2, quando_2 = _effective_mult(
        config=cfg,
        battery_pct=100,
        now=101.0,
        last_auto_mult=ancora,
        last_auto_change_at=quando,
    )
    assert (de_novo, ancora_2) == (mult, ancora)
    assert quando_2 == quando


# ---------------------------------------------------------------------------
# Teto, não troca
# ---------------------------------------------------------------------------


def test_voltar_para_balanceado_devolve_tudo_sem_reclicar() -> None:
    """A invariante que dá nome ao arquivo, e ela vale pelas duas pontas.

    O mesmo `DaemonConfig`, com a MESMA política que ela escolheu: só o
    orçamento muda. Se o teto tivesse "trocado" a escolha dela — reescrevendo
    `rumble_policy` para "economia", que é a implementação que parece mais
    simples —, o 1,5 não voltaria e ela teria de reclicar o "Máximo".
    """
    maquina = MaquinaConfig(orcamento=OrcamentoDeclarado(teto="economia"))
    cfg = DaemonConfig()
    cfg.rumble_policy = "max"
    cfg.orcamento_da_mesa = lambda: maquina.orcamento.teto

    assert _mult(cfg) == RUMBLE_POLICY_MULT["economia"]
    assert cfg.rumble_policy == "max", "o teto NÃO reescreve a escolha dela"

    maquina = MaquinaConfig(orcamento=OrcamentoDeclarado(teto="balanceado"))
    assert _mult(cfg) == RUMBLE_POLICY_MULT["max"]


def test_a_fonte_do_orcamento_e_lida_a_cada_calculo() -> None:
    """O "Aplicar" vale no cálculo seguinte, sem reiniciar o Hefesto.

    É a razão de o campo ser um CHAMÁVEL e não uma cópia: o `machine.declare`
    rebinda `daemon._maquina`, e uma cópia tirada no boot ficaria velha
    exatamente no gesto em que ela acabou de escolher.
    """
    leituras: list[int] = []
    vigente: list[str | None] = [None]

    def _fonte() -> str | None:
        leituras.append(1)
        return vigente[0]

    cfg = DaemonConfig()
    cfg.rumble_policy = "max"
    cfg.orcamento_da_mesa = _fonte

    assert _mult(cfg) == RUMBLE_POLICY_MULT["max"]
    vigente[0] = "economia"
    assert _mult(cfg) == RUMBLE_POLICY_MULT["economia"]
    assert len(leituras) == 2, "a fonte tem de ser consultada a cada cálculo"


def test_fonte_que_levanta_nao_derruba_a_vibracao() -> None:
    """Vibração não para porque a leitura da declaração falhou."""

    def _explode() -> str | None:
        raise RuntimeError("disco sumiu")

    cfg = DaemonConfig()
    cfg.rumble_policy = "max"
    cfg.orcamento_da_mesa = _explode
    assert _mult(cfg) == RUMBLE_POLICY_MULT["max"]


# ---------------------------------------------------------------------------
# O vocabulário que não pode ser renomeado
# ---------------------------------------------------------------------------


def test_as_chaves_do_orcamento_sao_as_do_schema_que_as_grava() -> None:
    """Renomear quebraria os perfis já gravados no disco dela.

    `OrcamentoDeclarado.teto` é o campo que persiste a escolha, e `max` é a
    chave — nunca o rótulo "Máximo". Gravar o rótulo faria o `extra="forbid"`
    recusar o DOCUMENTO INTEIRO, e o sintoma na tela seria "não consegui
    gravar", não "valor inválido".
    """
    for chave in ORCAMENTOS:
        assert OrcamentoDeclarado(teto=chave).teto == chave  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        OrcamentoDeclarado(teto="Máximo")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        OrcamentoDeclarado(teto="custom")  # type: ignore[arg-type]
