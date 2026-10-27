"""Os motores ganham o golpe que ressoa (OS-MOTORES-GANHAM-O-GOLPE-QUE-RESSOA-01).

Dois padrões novos no «Padrão dos motores», depois de «Pancada do lado»: o Ressoar (o golpe nos
dois motores e a cauda só no esquerdo, o grave, caindo em degraus até zero em ~300 ms) e o
Ricochete (o golpe num lado e a resposta mais fraca no outro, como a bola que quica). A força
passa pelo funil de sempre (o degrau do estilo, a Bateria longa, as barras de cada motor), nos
quatro controles e nos dois modos em que o Hefesto fala (DualSense e Xbox). O transporte, cabo ou
rádio, fica abaixo deste funil: a escrita dos motores do controle, a mesma dos outros padrões. A
tela só ganha os dois itens na lista, com a dica em tooltip; «Criar efeitos novos» não muda.
"""
from __future__ import annotations

import re
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import padroes_de_vibracao as pv
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.interface import aba05, pacotes
from hefesto_dualsense4unix.interface.pacotes import a05_vibracao as a05
from hefesto_dualsense4unix.profiles import schema
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.schema import ControllerRumbleOverride, MatchAny, Profile
from tests.unit.test_a_aba_vibracao_ganha_os_botoes_de_efeito import (
    UNIQ,
    _ctx,
    _PonteQueGrava,
    _rumble_do_disco,
    perfis,  # noqa: F401
)
from tests.unit.test_cada_motor_tem_o_seu_multiplicador import BRANCO, _Handlers

RAIZ = Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup/05-vibracao.html"
NOVOS = ("ressoar", "ricochete")
QUATRO = ("aa:bb:cc:00:00:21", "aa:bb:cc:00:00:22", "aa:bb:cc:00:00:23", "aa:bb:cc:00:00:24")
_MODO_DUALSENSE = tv.EstadoDoCanal(modo=tv.MODO_DUALSENSE, ha_jogo=True, sessao_aberta=False)
_MODO_XBOX = tv.EstadoDoCanal(modo=tv.MODO_XBOX, ha_jogo=True, sessao_aberta=False)


def test_os_dois_entram_depois_da_pancada_do_lado_no_produto_e_no_esquema() -> None:
    assert pv.ESCOLHAS[-3:] == ("pancada_do_lado", *NOVOS)
    assert schema.ESCOLHAS_DE_IMERSAO == pv.ESCOLHAS
    assert (pv.ROTULOS["ressoar"], pv.ROTULOS["ricochete"]) == ("Ressoar", "Ricochete")
    for chave in NOVOS:
        assert 0 < len(pv.DICAS[chave]) <= 36, chave
        assert ControllerRumbleOverride(efeito_imersao=chave).efeito_imersao == chave
        assert chave not in pv.FORMAS_DE_CRIAR


@pytest.mark.parametrize("chave", NOVOS)
def test_cabem_no_teto_tem_passos_de_60_ms_e_acabam_em_zero(chave: str) -> None:
    passos = pv.PADROES[chave]
    assert sum(ms for ms, _e, _d in passos) <= pv.TETO_MS
    assert all(ms >= 60 for ms, _e, _d in passos)
    assert passos[-1][1:] == (0, 0)


def test_o_ressoar_bate_nos_dois_e_a_cauda_do_grave_cai_em_degraus_ate_zero() -> None:
    """MORDIDA: a cauda sem decaimento (o mesmo degrau até o fim) reprova aqui.

    Prova da D-2210-O-RESSOAR-E-O-RICOCHETE-DOS-MOTORES.
    """
    golpe, *cauda = pv.PADROES["ressoar"]
    assert golpe[1:] == (255, 255)
    assert all(direito == 0 for _ms, _e, direito in cauda), "a cauda é só do esquerdo"
    forcas = [esquerdo for _ms, esquerdo, _d in cauda]
    assert len(forcas) >= 4, "degraus que o motor sente, não um corte"
    assert all(a > b for a, b in pairwise(forcas)), f"a cauda não decai: {forcas}"
    assert forcas[0] < golpe[1] and forcas[-1] == 0
    assert 240 <= sum(ms for ms, _e, _d in cauda[:-1]) <= 360, "a cauda dura ~300 ms"


def test_o_ricochete_alterna_o_lado_e_cada_resposta_e_mais_fraca() -> None:
    """MORDIDA: a resposta no mesmo motor do golpe, ou tão forte quanto, reprova aqui."""
    batidas = [(e, d) for _ms, e, d in pv.PADROES["ricochete"] if (e, d) != (0, 0)]
    assert all(min(e, d) == 0 for e, d in batidas), "cada batida é num lado só"
    lados = ["esquerdo" if e else "direito" for e, _d in batidas]
    assert 2 <= len(batidas) <= 3, "o golpe e uma ou duas respostas"
    assert all(a != b for a, b in pairwise(lados)), f"o lado não alterna: {lados}"
    forcas = [max(b) for b in batidas]
    assert forcas[0] == 255 and all(a > b for a, b in pairwise(forcas)), forcas
    passos = pv.PADROES["ricochete"]
    assert all(passos[i + 1][1:] == (0, 0) for i, p in enumerate(passos[:-1]) if p[1:] != (0, 0))


class _Motores:
    def __init__(self) -> None:
        self.relogio = 0.0
        self.escritas: list[tuple[str, int, int]] = []

    def __call__(self, uniq: str, fraco: int, forte: int) -> bool:
        self.escritas.append((uniq, fraco, forte))
        return True

    def de(self, uniq: str) -> list[tuple[int, int]]:
        return [(f, s) for u, f, s in self.escritas if u == uniq]


def _tocar(escolhas: dict[str, str], forca: float, estado: tv.EstadoDoCanal) -> _Motores:
    motores = _Motores()
    atuador = tv.AtuadorDosMotores(
        motores, lambda uniq: pv.padrao_que_vale(escolhas.get(uniq), None),
        lambda _u: False, lambda _u: forca)
    motor = tv.TatoVivo([atuador])
    for uniq in escolhas:
        motor.anotar(tv.Evento(0.0, uniq, tv.TIPO_DEDO, tv.LADO_DIREITO, 1.0))
    t = 0.0
    while t <= 2.5:
        motor.tique(t, lambda _u: estado, tv.Receita(padroes_escolhidos=True),
                    uniqs=tuple(escolhas))
        t += tv.INTERVALO_S
    return motores


def _esperado(chave: str, forca: float) -> list[tuple[int, int]]:
    """Os passos como o motor os escreve: (fraco = direito, forte = esquerdo), vezes a força."""
    return [(round(d * forca), round(e * forca)) for _ms, e, d in pv.PADROES[chave]]


@pytest.mark.parametrize("estado", [_MODO_DUALSENSE, _MODO_XBOX], ids=["dualsense", "xbox"])
@pytest.mark.parametrize("forca", [1.0, tv.FORCA_NA_ECONOMIA], ids=["cheia", "bateria-longa"])
def test_os_quatro_controles_tocam_os_dois_pelo_funil_de_sempre(
    estado: tv.EstadoDoCanal, forca: float,
) -> None:
    escolhas = dict(zip(QUATRO, ("ressoar", "ricochete", "ricochete", "ressoar"), strict=True))
    motores = _tocar(escolhas, forca, estado)
    for uniq, chave in escolhas.items():
        tocado = motores.de(uniq)
        assert tocado == _esperado(chave, forca), (uniq, chave)
        assert max(max(par) for par in tocado) == round(255 * forca)


def test_a_bateria_longa_baixa_a_cauda_inteira_e_ela_continua_caindo() -> None:
    motores = _tocar({QUATRO[0]: "ressoar"}, tv.FORCA_NA_ECONOMIA, _MODO_DUALSENSE)
    cauda = [forte for _fraco, forte in motores.de(QUATRO[0])[1:]]
    assert cauda[0] == round(200 * tv.FORCA_NA_ECONOMIA)
    assert all(a > b for a, b in pairwise(cauda)) and cauda[-1] == 0


def test_as_quatro_colunas_ganham_os_dois_itens_e_criar_nao_muda() -> None:
    html = MOCKUP.read_text(encoding="utf-8")
    listas = re.findall(
        r'<select class="vib-efeito" data-gesto="efeito-imersao"[^>]*>(.*?)</select>', html,
        flags=re.S)
    assert len(listas) == 4
    for opcoes in listas:
        valores = re.findall(r'<option value="([^"]+)"[^>]*>([^<]+)</option>', opcoes)
        assert valores[-3:] == [("pancada_do_lado", "Pancada do lado"),
                                ("ressoar", "Ressoar"), ("ricochete", "Ricochete")]
    assert 'aria-label="Forma"' not in html, "o «Criar efeitos novos» saiu da Vibração em 27/10"
    assert aba05._ROTULOS_DA_IMERSAO["ressoar"] == "Ressoar"


@pytest.mark.parametrize("chave", NOVOS)
def test_o_clique_grava_no_perfil_e_a_pintura_poe_a_dica(perfis: Path, chave: str) -> None:  # noqa: F811
    save_profile(Profile(name="Bancada", match=MatchAny()))
    ponte = _PonteQueGrava(_Handlers(ativo="Bancada", primario=BRANCO))
    gesto = pacotes.gesto_da_pagina("05-vibracao.html", "efeito-imersao")
    assert gesto is not None
    gesto(_ctx("Bancada"), {"uniq": UNIQ, "valor": chave}, ponte)
    assert ponte.pedidos == [{"efeito_imersao": chave, "uniq": UNIQ}]
    rumble = _rumble_do_disco()
    assert rumble is not None and rumble.efeito_imersao == chave
    coluna: dict[str, Any] = next(iter(a05.pacote(_ctx("Bancada"))["colunas"].values()))
    assert coluna["imersao-escolha"] == chave
    assert coluna["imersao-dica"] == pv.DICAS[chave]


def test_criar_efeito_recusa_os_dois_que_moram_nos_dois_motores(perfis: Path) -> None:  # noqa: F811
    gesto = pacotes.gesto_da_pagina("05-vibracao.html", "criar-efeito")
    assert gesto is not None
    with pytest.raises(RuntimeError, match="Escolha a forma"):
        forma = {"padrao": "ressoar", "motores": pv.ESQUERDO, "nome": "x"}  # (noqa-acento)
        gesto(_ctx(), {"forma": forma}, None)
