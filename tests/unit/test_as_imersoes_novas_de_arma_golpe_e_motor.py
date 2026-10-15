"""As imersões novas de arma, golpe e motor entram no gatilho
(AS-IMERSOES-NOVAS-DE-ARMA-GOLPE-E-MOTOR-ENTRAM-NO-GATILHO-01).

As doze saem só nos acionamentos da lista de onze, com o bloco da tabela do catálogo; as novas
famílias (Rampa de força e Vibração por posição) abrem a lista; o Golpe carregado escreve cinco
blocos no máximo em 1,65 s nos quatro controles; o Clique no meio nasce do status do Disparo, no
cabo e no rádio.

MORDIDAS (cada uma reprova o teste que a nomeia, e o arquivo volta idêntico):
baixar a força do degrau de 1000 ms do Golpe carregado, ou tirar o «pronto» dele, reprova
`test_o_golpe_carregado_endurece_treme_de_pronto_e_some`; mudar um degrau das Duas travas reprova
`test_cada_nova_sai_com_o_bloco_da_tabela`; pôr o Clique no meio no relógio do aperto, e não no
status do Disparo, reprova `test_o_clique_no_meio_nasce_do_status_do_disparo`.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.app.actions.trigger_specs import PRESETS
from hefesto_dualsense4unix.core.trigger_effects import build_from_name, frequencia_limpa
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.profiles import efeitos_de_imersao as ei
from tests.unit.test_o_motor_dos_momentos_nao_reescreve_e_le_o_clique import (
    FOLGA,
    P1,
    QUATRO,
    _bloco,
    _mesa,
)

#: (imersão, acionamento, estilo) → os 8 primeiros bytes do bloco (modo + 7 forças)
BLOCOS: dict[tuple[str, str, str], str] = {
    ("golpe-leve", "Weapon", ""): "2528000000000000",
    ("golpe-pesado", "Weapon", ""): "2504010500000000",
    ("golpe-carregado", "Resistance", ""): "21f0030020491200",
    ("escudo-que-aguenta", "MultiPositionFeedback", ""): "21fc0340a2b13e00",
    ("besta", "SlopeFeedback", ""): "21fc0300d9da3f00",
    ("agarrar", "SlopeFeedback", ""): "21fc0340a4912d00",
    ("energia-que-cresce", "MultiPositionVibration", ""): "26fe034034d63f32",
    ("energia-que-cresce", "MultiPositionVibration", "corrida"): "26fe034034d63f19",
    ("clique-no-meio", "Weapon", ""): "2550000400000000",
    ("mira-firme", "Resistance", ""): "21fc038024491200",
    ("motor-no-acelerador", "MultiPositionVibration", ""): "26ff0340226d2419",
    ("duas-travas", "MultiPositionFeedback", ""): "21e700c801e40000",
    ("pique-que-cansa", "Resistance", ""): "21ff034992240900",
}

#: o que se sente, com o tempo dito onde o motor o toca
DICAS = {
    "golpe-leve": "Um clique curto e macio no meio do curso.",
    "golpe-pesado": "Parede longa e dura que estala no fundo.",
    "golpe-carregado": "Uma parede que endurece segurando, treme de pronto aos 1,5 s e some.",
    "escudo-que-aguenta":
        "O gatilho endurece do meio ao fim e fica mais duro depois de 2 s segurando.",
    "besta": "Rampa curta e dura, que solta seca.",
    "agarrar": "O gatilho resiste mais à medida que aperta, como apertar algo.",
    "energia-que-cresce":
        "Vibração que fica mais forte quanto mais fundo vai o dedo, e cheia aos 1,5 s.",
    "clique-no-meio": "Um clique na metade, e a resistência cresce depois dele.",
    "mira-firme": "Peso leve e constante no gatilho da mira.",
    "motor-no-acelerador": "Ronco fraco que cresce com o pedal.",
    "duas-travas": "Duas travas no curso, uma na entrada e outra no meio.",
    "pique-que-cansa":
        "Um peso leve que vai pesando segurando a corrida: mais forte aos 2, 4 e 6 s.",
}

NOVAS = tuple(DICAS)
ONZE = {s.name for s in PRESETS}


def _bytes(modo: str, ajustes: dict[str, int]) -> str:
    spec = next(s for s in PRESETS if s.name == modo)
    efeito = build_from_name(modo, {**{p.name: p.default for p in spec.params}, **ajustes})
    return bytes([efeito.mode, *efeito.forces]).hex()[:16]


def _plano(chave: str) -> tv.PlanoDoGatilho:
    imersao = ei.POR_CHAVE[chave]
    modo = next(iter(imersao.ajustes))
    return tv.PlanoDoGatilho(
        imersao, modo, "", dict(imersao.ajustes[modo]), ei.momentos_no_modo(imersao, modo))


def test_as_doze_entram_pelo_nome_novo_e_so_nos_onze_acionamentos() -> None:
    assert set(NOVAS) <= set(ei.POR_CHAVE) and len(NOVAS) == 12
    assert ei.FAMILIAS["rampa"] == ("SlopeFeedback",)
    assert ei.FAMILIAS["vibração por posição"] == ("MultiPositionVibration",)
    for chave in NOVAS:
        imersao = ei.POR_CHAVE[chave]
        assert imersao.dica == DICAS[chave], chave
        assert imersao.rotulo and "'" not in imersao.rotulo, chave
        assert set(imersao.ajustes) <= ONZE and set(imersao.ajustes) <= set(
            ei.FAMILIAS[imersao.familia]), chave
        for m in imersao.momentos:
            assert m.modo in ONZE and m.a_cada_ms is None, (chave, m)


def test_cada_nova_sai_com_o_bloco_da_tabela() -> None:
    vistas = set()
    for imersao, modo, estilo, ajustes in ei.todos_os_ajustes():
        chave = (imersao.chave, modo, estilo)
        if chave in BLOCOS:
            vistas.add(chave)
            assert _bytes(modo, ajustes) == BLOCOS[chave], chave
    assert vistas == set(BLOCOS)


def test_nenhuma_frequencia_nova_cai_fora_do_divisor_limpo() -> None:
    for chave in NOVAS:
        imersao = ei.POR_CHAVE[chave]
        pedidas = [a["frequency"] for a in imersao.ajustes.values() if "frequency" in a]
        pedidas += [a["frequency"] for por_modo in imersao.variantes.values()
                    for a in por_modo.values() if "frequency" in a]
        pedidas += [m.ajustes["frequency"] for m in imersao.momentos if "frequency" in m.ajustes]
        assert all(frequencia_limpa(f) == f for f in pedidas), chave


def test_o_golpe_pesado_da_luta_nao_vira_a_arma_pesada() -> None:
    """O catálogo pedia 2/8/255 na luta, que é a Arma pesada: a tela os confundiria."""
    assert ei.POR_CHAVE["golpe-pesado"].variantes == {}
    assert ei.imersao_dos_numeros("Weapon", [2, 8, 255])[0].chave == "arma-pesada"
    assert ei.imersao_dos_numeros("Weapon", [2, 8, 191])[0].chave == "golpe-pesado"


@pytest.mark.parametrize("uniq", QUATRO)
def test_o_golpe_carregado_endurece_treme_de_pronto_e_some(
    monkeypatch: pytest.MonkeyPatch, uniq: str
) -> None:
    mesa = _mesa(monkeypatch, _plano("golpe-carregado"))
    apertou = mesa.t
    mesa.apertar(uniq)
    mesa.rodar(1.9)
    escritas = mesa.backend.de(uniq, "right")
    assert [b for _t, b in escritas] == [
        _bloco("Resistance", start=4, force=5),
        _bloco("Resistance", start=4, force=7),
        _bloco("Machine", start=4, end=9, strength=3, frequency=40),
        _bloco("Off"),
    ]
    tempos = [0.5, 1.0, 1.5, 1.65]
    for (t, _b), esperado in zip(escritas, tempos, strict=True):
        assert esperado <= t - apertou <= esperado + FOLGA, (esperado, t - apertou)
    assert len(escritas) <= 5, "cinco escritas em 1,65 s, no máximo (o teto do motor)"
    mesa.soltar(uniq)
    mesa.rodar(0.2)
    assert len(mesa.backend.voltou(uniq)) == 1, "soltar devolve o gatilho"


def test_o_golpe_carregado_solto_antes_do_pronto_nao_treme(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _mesa(monkeypatch, _plano("golpe-carregado"))
    mesa.apertar(P1)
    mesa.rodar(1.2)
    mesa.soltar(P1)
    mesa.rodar(1.0)
    escritos = [b for _t, b in mesa.backend.de(P1, "right")]
    assert _bloco("Machine", start=4, end=9, strength=3, frequency=40) not in escritos
    assert escritos == [_bloco("Resistance", start=4, force=5),
                        _bloco("Resistance", start=4, force=7)]


@pytest.mark.parametrize("via", ["usb", "bt"])
@pytest.mark.parametrize("uniq", QUATRO)
def test_o_clique_no_meio_nasce_do_status_do_disparo(
    monkeypatch: pytest.MonkeyPatch, uniq: str, via: str
) -> None:
    mesa = _mesa(monkeypatch, _plano("clique-no-meio"))
    mesa.apertar(uniq)
    mesa.disparo(uniq, 1, via)
    mesa.rodar(0.8)
    assert mesa.backend.de(uniq) == [], "dentro do clique, nada se escreve"
    mesa.disparo(uniq, 2, via)
    passou = mesa.t
    mesa.rodar(0.3)
    [(t, bloco)] = mesa.backend.de(uniq, "right")
    assert bloco == _bloco("Resistance", start=7, force=6)
    assert 0 <= t - passou <= FOLGA


def test_o_pique_que_cansa_pesa_a_cada_dois_segundos_e_para_ali(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _mesa(monkeypatch, _plano("pique-que-cansa"))
    apertou = mesa.t
    mesa.apertar(P1)
    mesa.rodar(8.0)
    escritas = mesa.backend.de(P1, "right")
    assert [b for _t, b in escritas] == [
        _bloco("Resistance", start=0, force=f) for f in (3, 4, 5)]
    for (t, _b), esperado in zip(escritas, (2.0, 4.0, 6.0), strict=True):
        assert esperado <= t - apertou <= esperado + FOLGA


def test_as_que_nao_tem_momento_nao_escrevem_nada_no_aperto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for chave in ("golpe-leve", "mira-firme", "besta", "motor-no-acelerador", "duas-travas"):
        assert not ei.POR_CHAVE[chave].momentos, chave
    # A Energia que cresce só escreve o degrau da carga cheia, uma vez.
    mesa = _mesa(monkeypatch, _plano("energia-que-cresce"))
    mesa.apertar(P1)
    mesa.rodar(3.0)
    assert [b for _t, b in mesa.backend.de(P1, "right")] == [
        _bloco("Machine", start=2, end=9, strength=8, frequency=50)]
