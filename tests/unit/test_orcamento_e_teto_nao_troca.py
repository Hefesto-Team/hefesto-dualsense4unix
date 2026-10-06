"""O orçamento da mesa é TETO, não troca — e o teto é `min`, nunca produto."""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.core.rumble import _effective_mult, teto_do_orcamento
from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT
from hefesto_dualsense4unix.profiles.schema import RUMBLE_CUSTOM_MULT_MAX
from hefesto_dualsense4unix.utils.maquina import MaquinaConfig, OrcamentoDeclarado

ORCAMENTOS = ("economia", "balanceado", "max", "auto")


def _config(
    policy: str,
    *,
    custom_mult: float = 1.0,
    orcamento: str | None = None,
) -> DaemonConfig:
    """Um `DaemonConfig` com política e orçamento, fiado como o boot fia."""
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


def test_so_o_economia_impoe_teto() -> None:
    """Três dos quatro orçamentos não limitam nada, e cada um por seu motivo."""
    assert teto_do_orcamento("economia") == RUMBLE_POLICY_MULT["economia"]
    assert teto_do_orcamento("balanceado") is None
    assert teto_do_orcamento("max") is None
    assert teto_do_orcamento("auto") is None
    assert teto_do_orcamento(None) is None


def test_o_teto_do_economia_e_o_degrau_do_economia() -> None:
    """O 0,3 tem UM dono, e é a tabela do daemon."""
    assert teto_do_orcamento("economia") == RUMBLE_POLICY_MULT["economia"]
    assert teto_do_orcamento("economia") != 1.0


@pytest.mark.parametrize("policy", sorted(RUMBLE_POLICY_MULT))
def test_orcamento_balanceado_entrega_o_mult_de_sempre(policy: str) -> None:
    """Com o orçamento em Balanceado, nada muda em relação a antes da leva."""
    assert _mult(_config(policy, orcamento="balanceado")) == RUMBLE_POLICY_MULT[policy]


@pytest.mark.parametrize("policy", sorted(RUMBLE_POLICY_MULT))
def test_sem_orcamento_declarado_entrega_o_mult_de_sempre(policy: str) -> None:
    """Ninguém declarou nada: o produto se comporta como sempre se comportou."""
    assert _mult(_config(policy)) == RUMBLE_POLICY_MULT[policy]


def test_config_sem_o_campo_do_orcamento_nao_limita_nada() -> None:
    """Config sem a fonte fiada (dublê, daemon no meio de um upgrade)."""
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
    """MORDIDA 1, o caso caro: o `custom` no teto de 2,0."""
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
    """MORDIDA 3: o teto entra ANTES do debounce, e é isso que assenta o auto."""
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
    de_novo, ancora_2, quando_2 = _effective_mult(
        config=cfg,
        battery_pct=100,
        now=101.0,
        last_auto_mult=ancora,
        last_auto_change_at=quando,
    )
    assert (de_novo, ancora_2) == (mult, ancora)
    assert quando_2 == quando


def test_voltar_para_balanceado_devolve_tudo_sem_reclicar() -> None:
    """A invariante que dá nome ao arquivo, e ela vale pelas duas pontas."""
    maquina = MaquinaConfig(orcamento=OrcamentoDeclarado(teto="economia"))
    cfg = DaemonConfig()
    cfg.rumble_policy = "max"
    cfg.orcamento_da_mesa = lambda: maquina.orcamento.teto

    assert _mult(cfg) == RUMBLE_POLICY_MULT["economia"]
    assert cfg.rumble_policy == "max", "o teto NÃO reescreve a escolha dela"

    maquina = MaquinaConfig(orcamento=OrcamentoDeclarado(teto="balanceado"))
    assert _mult(cfg) == RUMBLE_POLICY_MULT["max"]


def test_a_fonte_do_orcamento_e_lida_a_cada_calculo() -> None:
    """O "Aplicar" vale no cálculo seguinte, sem reiniciar o Hefesto."""
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


def test_as_chaves_do_orcamento_sao_as_do_schema_que_as_grava() -> None:
    """Renomear quebraria os perfis já gravados no disco do usuário."""
    for chave in ORCAMENTOS:
        assert OrcamentoDeclarado(teto=chave).teto == chave  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        OrcamentoDeclarado(teto="Máximo")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        OrcamentoDeclarado(teto="custom")  # type: ignore[arg-type]
