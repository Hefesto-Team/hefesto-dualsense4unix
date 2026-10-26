"""O-TOUCHPAD-VIRA-FONTE-DE-VIBRACAO-01: o dedo no touchpad vibra o controle, do lado em que está.

Hub de mentira (o dedo que a mesa mostra a cada tique) e relógio injetado. O motor esquerdo é o
forte e o direito o fraco do rumble.
"""
from __future__ import annotations

from collections.abc import Callable
from itertools import pairwise
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.daemon.subsystems.meus_toques import (
    Ajuste,
    AjusteDoTouchpad,
    Entrada,
    Ligacoes,
    MeusToques,
    Toque,
    ajuste_do_perfil,
    meus_toques_de_producao,
)
from hefesto_dualsense4unix.profiles.schema import Profile

P1, P2 = "aabbcc000001", "aabbcc000002"
L, A = 1920, 1080
BASE = 76


@dataclass
class Mesa:
    """O controle e o hub de mentira."""

    agora: float = 1000.0
    motores: list[tuple[float, str, int, int]] = field(default_factory=list)
    eventos: list[tuple[str, tuple[int, int]]] = field(default_factory=list)
    dedos: dict[str, tuple[tuple[int, int], ...]] = field(default_factory=dict)
    clicado: dict[str, bool] = field(default_factory=dict)
    perguntas: int = 0
    pode: bool = True

    def ligacoes(self) -> Ligacoes:
        return Ligacoes(
            motores=lambda uniq, fraco, forte: self.motores.append(
                (self.agora, uniq, fraco, forte)),
            pode_falar=lambda uniq: self.pode,
            haptica_do_jogo=lambda uniq: False,
            gatilho_do_jogo=lambda uniq: False,
            dizer=lambda uniq, pedido, efetivo, jogo, toques: self.eventos.append((uniq, toques)),
            toque=self.toque,
        )

    def toque(self, uniq: str) -> Toque | None:
        self.perguntas += 1
        return Toque(self.dedos.get(uniq, ()), L, A, self.clicado.get(uniq, False))

    def de(self, uniq: str = P1) -> list[tuple[float, int, int]]:
        """``(t, esquerdo, direito)``: o esquerdo é o forte, o direito o fraco."""
        return [(t, forte, fraco) for t, u, fraco, forte in self.motores if u == uniq]


def _meus(mesa: Mesa, **touchpad: Any) -> MeusToques:
    touchpad.setdefault("leitura", "pelos_lados")
    meus = MeusToques(mesa.ligacoes())
    meus.ajustar(Ajuste(
        modo="jogo_e_meus_toques", analogicos="desligado", botoes=False, gatilhos=False,
        chacoalhar=False, touchpad=AjusteDoTouchpad(**touchpad)))
    return meus


def _andar(
    meus: MeusToques, mesa: Mesa, ate: float, *, passo: float = 0.005,
    antes: Callable[[float], None] | None = None, uniqs: tuple[str, ...] = (P1,),
) -> None:
    while mesa.agora < ate:
        mesa.agora = round(mesa.agora + passo, 6)
        if antes is not None:
            antes(mesa.agora)
        meus.tique([Entrada(u) for u in uniqs], mesa.agora)


def _dedo(mesa: Mesa, fx: float, fy: float, uniq: str = P1) -> None:
    mesa.dedos[uniq] = ((round(fx * L), round(fy * A)),)


def _apoiar(meus: MeusToques, mesa: Mesa, fx: float, fy: float, por: float = 0.4) -> None:
    _dedo(mesa, fx, fy)
    _andar(meus, mesa, mesa.agora + por)


def _ultimo(mesa: Mesa, uniq: str = P1) -> tuple[int, int]:
    esq, dir_ = mesa.de(uniq)[-1][1:]
    return esq, dir_


def test_desligado_nao_pergunta_nada() -> None:
    mesa = Mesa()
    meus = _meus(mesa, leitura="desligado")
    _dedo(mesa, 0.9, 0.1)
    _andar(meus, mesa, mesa.agora + 0.5)
    assert mesa.perguntas == 0, "com o touchpad desligado o hub nem é consultado"
    assert mesa.motores == []


def test_so_o_jogo_com_o_touchpad_ligado_nao_vibra() -> None:
    mesa = Mesa()
    meus = MeusToques(mesa.ligacoes())
    meus.ajustar(Ajuste(touchpad=AjusteDoTouchpad(leitura="pelos_lados")))
    _dedo(mesa, 0.9, 0.1)
    _andar(meus, mesa, mesa.agora + 0.5)
    assert mesa.perguntas == 0 and mesa.motores == []


def test_no_modo_nativo_nao_pergunta_nem_escreve() -> None:
    mesa = Mesa(pode=False)
    meus = _meus(mesa)
    _dedo(mesa, 0.9, 0.1)
    _andar(meus, mesa, mesa.agora + 0.5)
    assert mesa.perguntas == 0 and mesa.motores == []


def test_o_dedo_a_direita_vibra_so_o_motor_direito() -> None:
    mesa = Mesa()
    meus = _meus(mesa)
    _apoiar(meus, mesa, 0.9, 0.1)
    esq, dir_ = _ultimo(mesa)
    assert esq == 0 and dir_ >= round(BASE * 0.9), f"esq={esq} dir={dir_}"


def test_o_dedo_a_esquerda_vibra_so_o_motor_esquerdo() -> None:
    mesa = Mesa()
    meus = _meus(mesa)
    _apoiar(meus, mesa, 0.1, 0.1)
    esq, dir_ = _ultimo(mesa)
    assert dir_ == 0 and esq >= round(BASE * 0.9)


def test_o_dedo_no_centro_vibra_os_dois() -> None:
    mesa = Mesa()
    meus = _meus(mesa)
    _apoiar(meus, mesa, 0.5, 0.1)
    esq, dir_ = _ultimo(mesa)
    assert esq == dir_ and esq > 0


def test_dois_dedos_vibram_os_dois_lados() -> None:
    """Prova da D-1610-O-TOUCHPAD-VIBRA-O-LADO-TOCADO."""
    mesa = Mesa()
    meus = _meus(mesa)
    mesa.dedos[P1] = ((round(0.9 * L), round(0.1 * A)), (round(0.95 * L), round(0.5 * A)))
    _andar(meus, mesa, mesa.agora + 0.4)
    esq, dir_ = _ultimo(mesa)
    assert esq == dir_ and esq > 0, "dois dedos, mesmo os dois à direita, vibram os dois lados"


def test_a_altura_e_a_forca() -> None:
    mesa = Mesa()
    meus = _meus(mesa)
    _apoiar(meus, mesa, 0.9, 0.9)
    embaixo = _ultimo(mesa)[1]
    _apoiar(meus, mesa, 0.9, 0.1, por=1.0)
    em_cima = _ultimo(mesa)[1]
    assert 0 < embaixo < em_cima


def test_a_altura_invertida_e_o_contrario() -> None:
    mesa = Mesa()
    meus = _meus(mesa, altura="invertida")
    _apoiar(meus, mesa, 0.9, 0.9)
    embaixo = _ultimo(mesa)[1]
    _apoiar(meus, mesa, 0.9, 0.1, por=1.0)
    em_cima = _ultimo(mesa)[1]
    assert embaixo > em_cima > 0


def test_a_altura_fixa_nao_muda_a_forca() -> None:
    mesa = Mesa()
    meus = _meus(mesa, altura="fixa")
    _apoiar(meus, mesa, 0.9, 0.9)
    embaixo = _ultimo(mesa)[1]
    _apoiar(meus, mesa, 0.9, 0.1, por=1.0)
    em_cima = _ultimo(mesa)[1]
    assert embaixo == em_cima == BASE


def test_a_mistura_atravessa_sem_degrau() -> None:
    mesa = Mesa()
    meus = _meus(mesa, leitura="mistura", altura="fixa")
    _dedo(mesa, 0.0, 0.5)
    _andar(meus, mesa, mesa.agora + 0.3)
    assert _ultimo(mesa) == (BASE, 0), "no canto esquerdo só o motor esquerdo"
    inicio = mesa.agora

    def arrastar(t: float) -> None:
        _dedo(mesa, min(1.0, (t - inicio) / 1.0), 0.5)

    _andar(meus, mesa, inicio + 1.0, antes=arrastar)
    _dedo(mesa, 1.0, 0.5)
    _andar(meus, mesa, mesa.agora + 0.4)
    escritas = [(e, d) for _, e, d in mesa.de()]
    passos = [abs(a[0] - b[0]) for a, b in pairwise(escritas)]
    assert max(passos) <= 12, f"o balanço deu um degrau de {max(passos)} em uma escrita"
    assert escritas[-1] == (0, BASE), "no canto direito só o motor direito"
    assert any(e == BASE and 0 < d < BASE for e, d in escritas), "o direito sobe até o meio"
    assert any(d == BASE and 0 < e < BASE for e, d in escritas), "o esquerdo desce depois do meio"


def test_a_mistura_suaviza_o_salto_do_dedo() -> None:
    mesa = Mesa()
    meus = _meus(mesa, leitura="mistura", altura="fixa")
    _apoiar(meus, mesa, 0.0, 0.5)
    pulo = mesa.agora
    _dedo(mesa, 1.0, 0.5)
    _andar(meus, mesa, pulo + 0.4)
    depois = [(e, d) for t, e, d in mesa.de() if t > pulo]
    assert any(0 < d < BASE for _, d in depois), "o direito sobe em degraus, não de uma vez"
    assert depois[-1][0] <= 2 and depois[-1][1] == BASE, "a suavização chega ao canto"


def test_na_mistura_o_centro_vibra_os_dois_na_forca_cheia() -> None:
    mesa = Mesa()
    meus = _meus(mesa, leitura="mistura", altura="fixa")
    _apoiar(meus, mesa, 0.5, 0.5)
    assert _ultimo(mesa) == (BASE, BASE)


def test_soltar_o_dedo_zera_em_150_ms() -> None:
    mesa = Mesa()
    meus = _meus(mesa, altura="fixa")
    _apoiar(meus, mesa, 0.9, 0.5)
    assert _ultimo(mesa)[1] == BASE
    mesa.dedos[P1] = ()
    soltou = mesa.agora
    _andar(meus, mesa, soltou + 0.05)
    meio = _ultimo(mesa)[1]
    assert 0 < meio < BASE, "no meio do caminho ele desce"
    _andar(meus, mesa, soltou + 0.16)
    assert _ultimo(mesa) == (0, 0)
    zero = next(t for t, e, d in mesa.de() if t > soltou and (e, d) == (0, 0))
    assert zero - soltou <= 0.16
    assert meus.precisa_andar() is True


def test_o_dedo_parado_vibra_enquanto_apoiado() -> None:
    mesa = Mesa()
    meus = _meus(mesa, altura="fixa", dedo_parado="vibra")
    _apoiar(meus, mesa, 0.9, 0.5, por=2.0)
    assert _ultimo(mesa)[1] == BASE


def test_so_o_toque_cala_o_dedo_parado() -> None:
    mesa = Mesa()
    meus = _meus(mesa, altura="fixa", dedo_parado="so_o_toque")
    _dedo(mesa, 0.9, 0.5)
    inicio = mesa.agora
    _andar(meus, mesa, inicio + 0.2)
    assert _ultimo(mesa)[1] == BASE, "no toque vibra"
    _andar(meus, mesa, inicio + 0.5)
    ultimo = mesa.de()[-1]
    assert (ultimo[1], ultimo[2]) == (0, 0)
    assert 0.29 <= ultimo[0] - inicio <= 0.36, f"calou em {ultimo[0] - inicio:.3f} s"


def test_o_deslize_rapido_da_um_surto_nos_dois_lados() -> None:
    mesa = Mesa()
    meus = _meus(mesa, altura="fixa")
    _apoiar(meus, mesa, 0.1, 0.5)
    assert _ultimo(mesa)[1] == 0
    inicio = mesa.agora

    def correr(t: float) -> None:
        _dedo(mesa, min(0.1 + (t - inicio) * 2.0, 0.9), 0.5)

    _andar(meus, mesa, inicio + 0.1, antes=correr)
    assert meus.toques_dados == 1, "um surto só, mesmo com o dedo rápido o tempo todo"
    assert any(d == BASE for _, e, d in mesa.de()), "o surto chega ao motor direito"


def test_sem_o_deslize_rapido_nao_ha_surto() -> None:
    mesa = Mesa()
    meus = _meus(mesa, altura="fixa", deslize_rapido=False)
    _apoiar(meus, mesa, 0.1, 0.5)
    inicio = mesa.agora

    def correr(t: float) -> None:
        _dedo(mesa, min(0.1 + (t - inicio) * 2.0, 0.9), 0.5)

    _andar(meus, mesa, inicio + 0.1, antes=correr)
    assert meus.toques_dados == 0


def test_na_mistura_o_deslize_e_o_balanco_e_nao_surto() -> None:
    mesa = Mesa()
    meus = _meus(mesa, leitura="mistura", altura="fixa")
    _apoiar(meus, mesa, 0.1, 0.5)
    inicio = mesa.agora

    def correr(t: float) -> None:
        _dedo(mesa, min(0.1 + (t - inicio) * 2.0, 0.9), 0.5)

    _andar(meus, mesa, inicio + 0.1, antes=correr)
    assert meus.toques_dados == 0


def test_o_deslize_rapido_respeita_o_teto() -> None:
    mesa = Mesa()
    meus = _meus(mesa, altura="fixa")
    _apoiar(meus, mesa, 0.1, 0.5)
    estado = {"n": 0}

    def vai_e_vem(t: float) -> None:
        estado["n"] += 1
        _dedo(mesa, 0.1 if (estado["n"] // 8) % 2 else 0.9, 0.5)

    _andar(meus, mesa, mesa.agora + 1.0, antes=vai_e_vem, passo=0.005)
    assert 0 < meus.toques_dados <= 12, f"{meus.toques_dados} surtos em 1 s"


def test_o_clique_respeita_o_teto() -> None:
    mesa = Mesa()
    meus = _meus(mesa, altura="fixa")
    _apoiar(meus, mesa, 0.1, 0.5)
    estado = {"n": 0}

    def bater(t: float) -> None:
        estado["n"] += 1
        mesa.clicado[P1] = (estado["n"] // 8) % 2 == 1

    _andar(meus, mesa, mesa.agora + 1.0, antes=bater, passo=0.005)
    assert 0 < meus.toques_dados <= 12, f"{meus.toques_dados} cliques em 1 s"


def test_o_clique_e_uma_borda() -> None:
    mesa = Mesa()
    meus = _meus(mesa, altura="fixa")
    _apoiar(meus, mesa, 0.1, 0.5)
    assert _ultimo(mesa)[1] == 0
    mesa.clicado[P1] = True
    clicou = mesa.agora
    _andar(meus, mesa, clicou + 0.1)
    assert _ultimo(mesa) == (BASE, BASE), "o acento vai aos dois lados"
    _andar(meus, mesa, clicou + 0.4)
    assert _ultimo(mesa)[1] == 0, "o clique segurado não vibra mais que o acento de 200 ms"
    assert meus.toques_dados == 1


def test_sem_o_clique_o_touchpad_nao_acentua() -> None:
    mesa = Mesa()
    meus = _meus(mesa, altura="fixa", clique=False)
    _apoiar(meus, mesa, 0.1, 0.5)
    mesa.clicado[P1] = True
    _andar(meus, mesa, mesa.agora + 0.1)
    assert _ultimo(mesa)[1] == 0 and meus.toques_dados == 0


def test_o_dedo_do_jogador_2_nao_vibra_o_jogador_1() -> None:
    mesa = Mesa()
    meus = _meus(mesa)
    _dedo(mesa, 0.9, 0.1, uniq=P2)
    _andar(meus, mesa, mesa.agora + 0.4, uniqs=(P1, P2))
    assert mesa.de(P1) == []
    assert _ultimo(mesa, P2)[1] > 0


def test_o_dedo_entra_no_par_dos_toques_e_chega_aos_acessorios() -> None:
    mesa = Mesa()
    meus = _meus(mesa)
    _apoiar(meus, mesa, 0.9, 0.1)
    uniq, toques = mesa.eventos[-1]
    assert uniq == P1 and toques[0] == 0 and toques[1] > 0


def test_o_dedo_se_junta_ao_jogo_pela_mistura_do_perfil() -> None:
    mesa = Mesa()
    meus = _meus(mesa, altura="fixa")
    _apoiar(meus, mesa, 0.9, 0.5)
    mistura = meus.misturar_o_jogo(P1, (20, 20))
    assert mistura is not None
    assert mistura.motores == (BASE, 20), "o dedo à direita é o fraco; o jogo, 20 em cada"
    assert mistura.toques == (0, BASE)


def _perfil(bloco: dict[str, Any]) -> Profile:
    return Profile.model_validate({"name": "Jogo", "match": {"type": "any"}, "meus_toques": bloco})


def test_o_bloco_sem_touchpad_nasce_desligado() -> None:
    perfil = _perfil({"modo": "jogo_e_meus_toques"})
    assert perfil.meus_toques is not None
    assert perfil.meus_toques.touchpad.leitura == "desligado"
    assert ajuste_do_perfil(perfil).touchpad == AjusteDoTouchpad()
    assert AjusteDoTouchpad().liga is False


def test_o_touchpad_do_perfil_vira_o_ajuste() -> None:
    perfil = _perfil({
        "modo": "jogo_e_meus_toques",
        "touchpad": {"leitura": "mistura", "altura": "invertida", "dedo_parado": "so_o_toque",
                     "deslize_rapido": False, "clique": False}})
    assert ajuste_do_perfil(perfil).touchpad == AjusteDoTouchpad(
        "mistura", "invertida", "so_o_toque", False, False)


def test_o_schema_recusa_o_que_nao_e_do_touchpad() -> None:
    for ruim in ({"leitura": "sempre"}, {"altura": "meio"}, {"dedo_parado": "treme"},
                 {"botao": True}):
        with pytest.raises(ValidationError):
            _perfil({"touchpad": ruim})


def test_o_touchpad_ilegivel_cai_na_fabrica() -> None:
    ruim = SimpleNamespace(meus_toques={"touchpad": {"leitura": "x", "clique": "talvez"}})
    assert ajuste_do_perfil(ruim).touchpad == AjusteDoTouchpad()


def test_o_hub_de_verdade_so_e_escutado() -> None:
    chamadas: list[str] = []
    estado = SimpleNamespace(
        touching=True, x=1700, y=100, largura=1920, altura=1080,
        pontos=(SimpleNamespace(slot=0, x=1700, y=100, identidade=7),))

    class Hub:
        def toque_da_peca(self, uniq: str) -> tuple[Any, bool]:
            chamadas.append(uniq)
            return estado, True

        def __getattr__(self, nome: str) -> Any:
            raise AssertionError(f"o meus_toques mexeu no hub: {nome}")

    daemon = SimpleNamespace(
        _garantir_sensor_hub=lambda: Hub(), controller=SimpleNamespace(primary_uniq=P1))
    meus = meus_toques_de_producao(daemon)
    toque = meus._l.toque(P1)
    assert toque == Toque(((1700, 100),), 1920, 1080, True)
    assert chamadas == [P1]


def test_sem_hub_o_toque_e_nada() -> None:
    daemon = SimpleNamespace(controller=SimpleNamespace(primary_uniq=P1))
    assert meus_toques_de_producao(daemon)._l.toque(P1) is None
