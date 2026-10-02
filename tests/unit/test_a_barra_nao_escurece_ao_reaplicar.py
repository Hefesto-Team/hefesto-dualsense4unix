"""A-BARRA-NAO-ESCURECE-AO-REAPLICAR-01 — reaplicar o perfil não escurece a barra."""
from __future__ import annotations

from typing import Any


from hefesto_dualsense4unix.core.led_control import (
    LedSettings,
    PecaDaMesa,
    _acende_o_tom,
    cores_sem_colisao,
    player_slot_color,
    reescalar,
)
from tests.unit.test_a_marca_da_cor_nao_some import (
    MACS,
    NOME,
    VERDE_AGUA,
    Mesa,
)
from tests.unit.ponte_do_rodape import PonteDoRodape

PALETA = tuple(player_slot_color(n) for n in range(1, 9))

CLIQUE_DA_04 = {"tipo": "button", "evento": "click",
                "pagina": "04-iluminacao.html"}  # (noqa-acento: chave do clique)


def _na(rgb: tuple[int, int, int], brilho: float) -> tuple[int, int, int]:
    """`rgb` no `brilho`, pela conta do dono (`LedSettings.apply_brightness`)."""
    return LedSettings(lightbar=rgb).apply_brightness(brilho).lightbar


def _luz(mesa: Mesa) -> list[tuple[int, int, int]]:
    """O que cada barra ACENDE: o nó de LED de cada controle, P1 a P4."""
    acesas = []
    for m in MACS:
        no = mesa.ctl._sysfs[m].get_rgb()
        with mesa.ctl._io_lock:
            decidido = mesa.ctl._merged_desired_for_key(m).led
        assert no == decidido, f"o nó de {m} acende {no} e o produto decidiu {decidido}"
        acesas.append(no)
    return acesas


class _PonteDoRodape:
    """A ponte do rodapé com o `profile.reaplicar` entregue ao handler REAL."""

    def __init__(self, mesa: Mesa) -> None:
        self.mesa = mesa

    def profile_reaplicar(self, nome: str) -> dict[str, Any]:
        return self.mesa.rodar(self.mesa.server._handle_profile_reaplicar({"name": nome}))

    def apply_draft_detalhado(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.mesa.rodar(self.mesa.server._handle_profile_apply_draft(payload))

    def __getattr__(self, nome: str) -> Any:
        raise AttributeError(f"a régua não previu o rodapé chamar a ponte em {nome!r}")


def _reaplicar(mesa: Mesa, caminho: str) -> None:
    """O perfil do disco aplicado de novo, pela porta de cada caminho do produto."""
    if caminho == "boot":
        mesa.ctl.clear_user_output_overrides()
        mesa.pm.apply(mesa._perfil(), origin="system")
    elif caminho == "troca-manual":
        mesa.rodar(mesa.server._handle_profile_switch({"name": NOME}))
    elif caminho == "troca-de-jogo":
        from hefesto_dualsense4unix.profiles.schema import LedsConfig, MatchAny, Profile

        jogo = Profile(name="o-jogo", match=MatchAny(),
                       leds=LedsConfig(lightbar=(255, 255, 255), lightbar_brightness=0.4))
        mesa.pm.apply(jogo, origin="launch")
        mesa.pm.apply(mesa._perfil(), origin="autoswitch")
    elif caminho == "autoswitch":
        mesa.pm.apply(mesa._perfil(), origin="autoswitch")
    elif caminho == "aplicar":
        from pacotes import rodape

        rodape.aplicar(mesa.ctx(), {"tipo": "button", "evento": "click"},
                       _PonteDoRodape(mesa))
    elif caminho == "salvar":
        from pacotes import rodape

        rodape.salvar(mesa.ctx(), CLIQUE_DA_04, PonteDoRodape())
        mesa.pm.apply(mesa._perfil(), origin="system")
    else:
        raise AssertionError(caminho)


CAMINHOS = ["boot", "troca-manual", "troca-de-jogo", "autoswitch", "aplicar", "salvar"]


CAMINHOS_COM_O_PISO = CAMINHOS


def _tons_de(luz: tuple[int, int, int]) -> set[tuple[int, int, int]]:
    return {t for t in PALETA if _acende_o_tom(luz, t)}


def test_o_deslocado_nao_cai_no_tom_de_quem_fica():
    """A mesa pura: o deslocado evita o tom de quem fica, venha antes ou depois."""
    from hefesto_dualsense4unix.core.led_control import DO_GLOBAL

    azul = player_slot_color(1)
    ciano = (0, 255, 255)
    saida = cores_sem_colisao([
        PecaDaMesa(uniq="p1", pedida=_na(azul, 0.82), do_numero=None,
                   procedencia=DO_GLOBAL, numero=1, brilho=0.82),
        PecaDaMesa(uniq="p3", pedida=_na(ciano, 0.5), do_numero=None,
                   procedencia=2, numero=3, brilho=0.5),
    ])
    assert saida["p1"] == _na(azul, 0.82)
    assert azul not in _tons_de(saida["p3"]), saida
    saida = cores_sem_colisao([
        PecaDaMesa(uniq="p1", pedida=_na(ciano, 0.82), do_numero=None,
                   procedencia=2, numero=1, brilho=0.82),
        PecaDaMesa(uniq="p4", pedida=_na(azul, 0.5), do_numero=None,
                   procedencia=4, numero=4, brilho=0.5),
    ])
    assert saida["p4"] == _na(azul, 0.5)
    assert azul not in _tons_de(saida["p1"]), saida


def test_acende_o_tom_e_a_pergunta_do_tom_e_nao_do_byte():
    """O azul a 82% é o azul; o verde-água nunca é o verde nem o ciano."""
    azul = player_slot_color(1)
    assert _acende_o_tom((0, 0, 209), azul)
    assert _acende_o_tom(azul, azul)
    assert not _acende_o_tom((0, 0, 209), player_slot_color(8))
    assert not _acende_o_tom(_na(VERDE_AGUA, 0.82), player_slot_color(3))
    assert not _acende_o_tom(_na(VERDE_AGUA, 0.82), player_slot_color(6))
    for pct in range(1, 101):
        for tom in PALETA:
            assert _acende_o_tom(_na(tom, pct / 100), tom), (tom, pct)


def test_reescalar_faz_a_conta_de_uma_vez_na_paleta_e_a_razao_fora_dela():
    """Tom único da paleta: a conta do trilho. Fora dela ou ambíguo: a razão."""
    for de in (0.05, 0.5, 0.82, 1.0):
        for para in (0.0, 0.3, 0.6, 1.0):
            for tom in PALETA:
                assert reescalar(_na(tom, de), de, para) == _na(tom, para), (tom, de, para)
    from hefesto_dualsense4unix.core.led_control import _escala_crua, fator_do_brilho

    fora = _na((40, 80, 180), 0.82)
    assert reescalar(fora, 0.82, 0.41) == _escala_crua(
        fora, fator_do_brilho(0.41) / fator_do_brilho(0.82))
    assert reescalar(fora, 0.82, 0.41, ((40, 80, 180),)) == _na((40, 80, 180), 0.41)
    assert reescalar((1, 0, 0), 0.005, 1.0) == _escala_crua(
        (1, 0, 0), fator_do_brilho(1.0) / fator_do_brilho(0.005))


def test_o_tom_livre_sai_no_brilho_da_peca():
    """A mesa pura da regra: o fóssil a 60% vai ao primeiro tom livre a 60%."""
    mesa = [
        PecaDaMesa(uniq="p1", pedida=_na(player_slot_color(1), 0.82),
                   do_numero=None, procedencia=1, numero=1, brilho=0.82),
        PecaDaMesa(uniq="p3", pedida=_na((0, 255, 255), 0.6), do_numero=None,
                   procedencia=2, numero=3, brilho=0.6),
    ]
    saida = cores_sem_colisao(mesa)
    assert saida["p1"] == _na(player_slot_color(1), 0.82)
    assert saida["p3"] == _na(player_slot_color(2), 0.6), saida
