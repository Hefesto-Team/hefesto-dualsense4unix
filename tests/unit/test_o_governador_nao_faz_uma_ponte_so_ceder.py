"""O-GOVERNADOR-NAO-FAZ-UMA-PONTE-SO-CEDER-01 — cede só o que não cabe.

A bancada de 03/10 (com ela): com dois controles por adaptador, `cedidos=0` e o
som contínuo nos quatro; com quatro num adaptador, ~22% cedidos e o som
alternando. E ela já tinha ouvido alternância com UM controle por adaptador.
Lido no código: em `_a_vez`, ``ceder = min(n, max(1, n - cabem))`` fazia pelo
menos uma ponte ceder em todo episódio, mesmo a única do adaptador; e o
episódio abria com 20 pacotes de fila, colado nas ~23 escritas que uma ponte de
93,75/s faz numa janela de 0,25 s.

A cura: ``max(0, n - cabem)``, uma ponte de pé enquanto a janela põe pacote no
ar (o engasgo), e o limiar relativo ao que uma ponte escreve por janela
(`JANELAS_DO_LIMIAR`, com o piso de 20). A defesa de 22/09 (a terceira ponte
num adaptador que escoa duas cede, em rodízio) segue de pé.

A BANCADA é o governador real, com o relógio e o diário de mentira, e um
adaptador de mentira que escoa até a capacidade de cada janela, com a fila do
host de verdade (o que não sai fica para a janela seguinte): o mesmo dublê das
réguas da O-GOVERNADOR-COM-UM-ADAPTADOR-SO-01. As pontes escrevem 93,75
quadros/s cada. A MORDIDA de cada régua está no docstring dela.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from hefesto_dualsense4unix.daemon.subsystems import governador_do_radio as gov
from tests.unit.test_o_governador_com_um_adaptador_so import CONTROLE_4
from tests.unit.test_o_governador_do_radio import (
    ADAPTADOR_A,
    CONTROLE_1,
    CONTROLE_2,
    CONTROLE_3,
    _AdaptadorQueEscoaDuas,
    _Diario,
    _Relogio,
)

CINCO_MINUTOS = int(300 / gov.PERIODO_S)
POR_JANELA = 93.75 * gov.PERIODO_S


class _AdaptadorQueOscila(_AdaptadorQueEscoaDuas):
    """Escoa ``lenta`` por ``fase`` janelas e ``rapida`` pelas ``fase`` seguintes.

    A média passa do que as pontes escrevem, e a fila do host sobe e desce: é o
    adaptador que escoa tudo com engasgos, e não o que não dá conta.
    """

    def __init__(self, lenta: int, rapida: int, fase: int) -> None:
        super().__init__(capacidade=lenta)
        self.lenta, self.rapida, self.fase = lenta, rapida, fase
        self.janelas = 0
        self.pico = 0

    def janela(self, escritas: int) -> None:
        self.capacidade = self.lenta if (self.janelas // self.fase) % 2 == 0 else self.rapida
        self.janelas += 1
        super().janela(escritas)
        self.pico = max(self.pico, self.fila)


@dataclass
class _Corrida:
    partes: dict[str, float]
    vagas: list[gov.Vaga]
    registro: _Diario
    cedendo_por_janela: list[int] = field(default_factory=list)


def _correr(
    ordem: tuple[str, ...], medidor: _AdaptadorQueEscoaDuas, janelas: int = CINCO_MINUTOS
) -> _Corrida:
    relogio, registro = _Relogio(), _Diario()
    governador = gov.GovernadorDoRadio(
        medidor=medidor,
        adaptador_de=lambda _u: ADAPTADOR_A,
        registrar=registro,
        relogio=relogio,
        n_max=4,
    )
    governador.tique()
    vagas: list[gov.Vaga] = []
    for uniq in ordem:
        vaga = governador.pedir_vaga(uniq, "som")
        assert isinstance(vaga, gov.Vaga), f"{uniq} não recebeu vaga: {vaga}"
        vaga.subiu("som")
        vagas.append(vaga)
    pedidas = dict.fromkeys(ordem, 0)
    no_ar = dict.fromkeys(ordem, 0)
    corrida = _Corrida(partes={}, vagas=vagas, registro=registro)
    sobra = 0.0
    for _ in range(janelas):
        sobra += POR_JANELA
        por_ponte, sobra = int(sobra), sobra - int(sobra)
        escritas = 0
        corrida.cedendo_por_janela.append(sum(1 for v in vagas if v.cedendo))
        for vaga in vagas:
            pedidas[vaga.uniq] += por_ponte
            if vaga.cedendo:
                continue
            for _ in range(por_ponte):
                vaga.contar_escrita()
            no_ar[vaga.uniq] += por_ponte
            escritas += por_ponte
        medidor.janela(escritas)
        relogio.agora += gov.PERIODO_S
        governador.tique()
    corrida.partes = {u: no_ar[u] / pedidas[u] for u in ordem}
    return corrida


def test_uma_ponte_com_a_fila_em_torno_de_20_nao_cede() -> None:
    """Régua 1: uma ponte, o adaptador escoando 20 e 27 em fases de 8 janelas.

    A fila do host oscila em torno de 20 pacotes. Nenhuma janela cedida.

    MORDIDA: o limiar fixo de 20 e a janela que cabe em parte cedendo o
    adaptador inteiro (o código de antes) cedem quadros da ponte sozinha.
    """
    medidor = _AdaptadorQueOscila(lenta=20, rapida=27, fase=8)
    corrida = _correr((CONTROLE_1,), medidor)

    assert 15 <= medidor.pico <= 35, f"premissa: a fila oscilou até {medidor.pico}"
    assert corrida.partes[CONTROLE_1] == 1.0, (
        f"a ponte sozinha cedeu {1 - corrida.partes[CONTROLE_1]:.1%} dos quadros")
    assert corrida.registro.de(gov.CEDEU_NA_FONTE) == [], "o diário disse «cedeu» sem ninguém ceder"


def test_uma_ponte_com_a_fila_acima_do_limiar_nao_cede_a_si_mesma() -> None:
    """Régua 1, a da sprint: a fila passa do limiar, e a ponte sozinha não cede.

    Fases de 20 janelas: a fila sobe a ~68 pacotes, acima das duas janelas de
    uma ponte (~47), e desce. O adaptador escoa tudo na média.

    MORDIDA: a conta da vez com ``max(1, n - cabem)`` faz a ponte ceder a si
    mesma em toda janela acima do limiar.
    """
    medidor = _AdaptadorQueOscila(lenta=20, rapida=27, fase=20)
    corrida = _correr((CONTROLE_1,), medidor)

    assert medidor.pico > gov.JANELAS_DO_LIMIAR * POR_JANELA, (
        f"premissa: a fila não passou do limiar ({medidor.pico})")
    assert corrida.partes[CONTROLE_1] == 1.0, (
        f"a ponte sozinha cedeu {1 - corrida.partes[CONTROLE_1]:.1%} dos quadros")
    assert not corrida.vagas[0].derrubar


def test_uma_ponte_no_adaptador_parado_de_fato_ainda_cede_e_cai() -> None:
    """Nada no ar: a ponte sozinha cede (o adaptador inteiro) e cai no teto.

    A cura não tira a defesa do 2B: uma ponte só não cede a si mesma enquanto o
    adaptador põe pacote no ar.
    """
    corrida = _correr((CONTROLE_1,), _AdaptadorQueEscoaDuas(capacidade=0))

    assert corrida.vagas[0].derrubar, "o adaptador parado não derrubou a ponte no teto"
    assert len(corrida.registro.de(gov.FILA_PARADA)) >= 1


def test_duas_pontes_num_adaptador_que_escoa_duas_nao_cedem() -> None:
    """Régua 2: duas pontes, o adaptador escoando duas com engasgos (44 e 50).

    É a bancada de 03/10 com dois controles por adaptador: `cedidos=0`.

    MORDIDA: o limiar fixo de 20 pacotes (``fila > LIMIAR_DO_DEFICIT``) abre
    episódio no engasgo, e a janela de 44 (uma ponte e meia) cede uma ponte.
    """
    medidor = _AdaptadorQueOscila(lenta=44, rapida=50, fase=8)
    corrida = _correr((CONTROLE_1, CONTROLE_2), medidor)

    assert medidor.pico > gov.LIMIAR_DO_DEFICIT, f"premissa: a fila ficou em {medidor.pico}"
    assert corrida.partes == {CONTROLE_1: 1.0, CONTROLE_2: 1.0}, corrida.partes
    assert corrida.registro.de(gov.CEDEU_NA_FONTE) == []


def test_tres_pontes_num_adaptador_que_escoa_duas_cedem_uma_por_vez() -> None:
    """Régua 3, a defesa de 22/09: três pontes num adaptador que escoa duas.

    O adaptador escoa 50 pacotes por janela: duas pontes de 24 escritas (a
    janela de 93,75/s alterna 23 e 24) cabem, três não.

    Cede uma por vez, em rodízio: nunca duas juntas (no regime), cada uma fica
    com ~2/3, e ninguém cai.

    MORDIDA: a conta da vez que nunca cede (``ceder = 0``) deixa as três
    escrevendo, a fila do host cresce sem teto e nenhuma janela cede.
    """
    medidor = _AdaptadorQueOscila(lenta=50, rapida=50, fase=1)
    corrida = _correr((CONTROLE_1, CONTROLE_2, CONTROLE_3), medidor)

    regime = corrida.cedendo_por_janela[40:]
    assert sum(1 for n in regime if n == 1) >= len(regime) // 2, (
        "a terceira ponte não cedeu: a defesa de 22/09 caiu")
    assert max(regime) == 1, f"cederam {max(regime)} pontes juntas"
    assert min(corrida.partes.values()) >= 0.60, corrida.partes
    assert max(corrida.partes.values()) - min(corrida.partes.values()) <= 0.10, corrida.partes
    assert not any(v.derrubar for v in corrida.vagas)
    assert medidor.pico <= 4 * gov.JANELAS_DO_LIMIAR * POR_JANELA, (
        f"a fila do host chegou a {medidor.pico} pacotes")


def test_quatro_pontes_num_adaptador_que_escoa_tres_cedem_uma_por_vez() -> None:
    """Quatro num adaptador (o teste de 03/10): cede uma por vez, ~3/4 cada."""
    medidor = _AdaptadorQueEscoaDuas(capacidade=75)
    corrida = _correr((CONTROLE_1, CONTROLE_2, CONTROLE_3, CONTROLE_4), medidor)

    regime = corrida.cedendo_por_janela[40:]
    assert max(regime) == 1, f"cederam {max(regime)} pontes juntas"
    assert min(corrida.partes.values()) >= 0.70, corrida.partes
    assert not any(v.derrubar for v in corrida.vagas)


@pytest.mark.parametrize("capacidade", [12, 15, 20])
def test_uma_ponte_num_adaptador_que_nao_da_conta_dela_cede_e_nao_cai(capacidade: int) -> None:
    """O engasgo tem teto: o adaptador que escoa menos que uma ponte, sempre, não é engasgo.

    Cada janela põe no ar mais que meia ponte (12, 15 ou 20 de ~23), então a
    janela sozinha parece engasgo; mas a fila do host cresce sem parar.
    Passados os dois limiares, cede o adaptador inteiro até a fila escoar, e
    volta: a ponte fica de pé, cedendo em rodízio consigo mesma, como o código
    de antes, com a fila contida.

    MORDIDA: tire o teto da fila (`FILA_DO_ENGASGO_EM_LIMIARES`) da conta do
    engasgo e a ponte nunca cede (a fila do host cresce por cinco minutos); ou
    deixe o engasgo valer no episódio que já cede inteiro, e o episódio nunca
    fecha, o relógio do teto anda e a ponte cai.
    """
    medidor = _AdaptadorQueOscila(lenta=capacidade, rapida=capacidade, fase=1)
    corrida = _correr((CONTROLE_1,), medidor)

    teto_do_engasgo = gov.FILA_DO_ENGASGO_EM_LIMIARES * gov.JANELAS_DO_LIMIAR * POR_JANELA
    assert corrida.partes[CONTROLE_1] < 1.0, "a ponte que o adaptador não escoa nunca cedeu"
    assert not corrida.vagas[0].derrubar, "a ponte sozinha caiu no teto, onde antes ficava de pé"
    assert medidor.pico <= teto_do_engasgo + 2 * POR_JANELA, (
        f"a fila do host chegou a {medidor.pico} pacotes")
