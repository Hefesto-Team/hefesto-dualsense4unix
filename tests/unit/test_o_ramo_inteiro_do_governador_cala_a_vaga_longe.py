"""O ramo «inteiro» do governador não dá o flag da fila à vaga longe.

AS-REGUAS-DO-RAMO-INTEIRO-E-DAS-QUATRO-RESPOSTAS-MORDEM-01.

Em `_a_vez`, o ramo `if cabem <= 0 or not na_vez:` cede o adaptador inteiro com
`vaga.cedendo = not vaga.longe`. A vaga longe (pausada pelo sinal) já está muda: a fila não tem o
que cobrar dela. Sem o `not vaga.longe`, o adaptador cuja única ponte está longe, com a fila acima
do limiar, abriria um episódio `governador_cedeu` (diário `CEDEU_NA_FONTE`) por uma ponte que não
escreve. A régua vizinha (`test_o_flag_da_fila_nao_fica_na_vaga_longe`) não alcança este ramo: lá,
o zerar do flag no sinal e o `not v.longe` da conta da vez se cobrem, e o do `inteiro` fica sem quem
o arranque sozinho.

A cena: quatro controles. O longe é a única ponte do adaptador A; no adaptador B, duas pontes de
rádio escrevem com folga; o quarto está no cabo e nem entra na fila. Na janela em que o sinal do
longe cai, a ponte dele ainda escreveu a janela inteira e o adaptador A não pôs nada no ar: a fila
passa do limiar com a única ponte já longe, e o governador cai no ramo `inteiro`.

MORDIDA: em `governador_do_radio._a_vez`, trocar `vaga.cedendo = not vaga.longe` por
`vaga.cedendo = True` (só o do ramo `inteiro`). O diário ganha um `CEDEU_NA_FONTE` do adaptador A
e o flag da fila fica na vaga longe, e a régua reprova.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import governador_do_radio as gov
from hefesto_dualsense4unix.integrations import ar_do_adaptador as ar
from hefesto_dualsense4unix.integrations import radio_da_mesa as rm
from tests.unit.test_o_governador_do_radio import (
    ADAPTADOR_A,
    ADAPTADOR_B,
    CONTROLE_1,
    CONTROLE_2,
    CONTROLE_3,
    _Diario,
    _Relogio,
)

CONTROLE_4 = "aa:bb:cc:00:00:04"
OS_QUATRO = (CONTROLE_1, CONTROLE_2, CONTROLE_3, CONTROLE_4)
#: o que uma ponte de som escreve numa janela (93,75 quadros/s); acima do piso do limiar
POR_JANELA = 23
#: o que o adaptador B põe no ar por janela: folga para as duas pontes dele
FOLGA_DO_B = 4 * POR_JANELA


class _Sinal:
    """O leitor do sinal na mão da régua: o que ela põe em `dbm` é o que o governador lê."""

    def __init__(self) -> None:
        self.dbm: dict[str, int] = {}
        self._n = 0

    def talvez_ler(self, _amostra: object) -> None:
        return None

    def leitura(self) -> tuple[int, dict[str, int | None]]:
        self._n += 1
        return self._n, dict(self.dbm)


class _DoisAdaptadores:
    """O medidor de dois adaptadores; cada um põe no ar até a capacidade da janela."""

    def __init__(self) -> None:
        self.capacidade = {ADAPTADOR_A: FOLGA_DO_B, ADAPTADOR_B: FOLGA_DO_B}
        self.fila = dict.fromkeys(self.capacidade, 0)
        self.saiu = dict.fromkeys(self.capacidade, 0)

    def janela(self, escritas: dict[str, int]) -> None:
        for endereco in self.fila:
            self.fila[endereco] += escritas.get(endereco, 0)
            self.saiu[endereco] = min(self.fila[endereco], self.capacidade[endereco])
            self.fila[endereco] -= self.saiu[endereco]

    def amostrar(self) -> dict[str, ar.ArDoAdaptador]:
        return {
            endereco: ar.ArDoAdaptador(
                hci=i, endereco=endereco, entrada_por_s=700.0,
                saida_por_s=self.saiu[endereco] / gov.PERIODO_S, janela_s=gov.PERIODO_S,
                conexoes=(),
            )
            for i, endereco in enumerate(self.fila)
        }


class _Cena:
    def __init__(self, longe: str) -> None:
        resto = [c for c in OS_QUATRO if c != longe]
        self.longe = longe
        self.cabo = resto[2]
        self.onde = {longe: ADAPTADOR_A, resto[0]: ADAPTADOR_B, resto[1]: ADAPTADOR_B,
                     self.cabo: ""}
        self.relogio, self.diario = _Relogio(), _Diario()
        self.medidor = _DoisAdaptadores()
        self.governador = gov.GovernadorDoRadio(
            medidor=self.medidor, adaptador_de=lambda u: self.onde[u],
            registrar=self.diario, relogio=self.relogio, n_max=4,
        )
        self.sinal = _Sinal()
        self.governador.leitor_do_sinal = self.sinal
        self.governador.tique()
        self.vagas: dict[str, gov.Vaga] = {}
        for uniq in OS_QUATRO:
            vaga = self.governador.pedir_vaga(uniq, "som")
            assert isinstance(vaga, gov.Vaga), f"{uniq} não recebeu vaga: {vaga}"
            vaga.subiu("som")
            self.vagas[uniq] = vaga

    def passo(self) -> None:
        """Uma janela: quem não cede escreve a sua parte; o medidor fecha e o governador decide."""
        escritas: dict[str, int] = {}
        for uniq, vaga in self.vagas.items():
            if vaga.cedendo:
                continue
            for _ in range(POR_JANELA):
                vaga.contar_escrita()
            if self.onde[uniq]:
                escritas[self.onde[uniq]] = escritas.get(self.onde[uniq], 0) + POR_JANELA
        self.medidor.janela(escritas)
        self.relogio.agora += gov.PERIODO_S
        self.governador.tique()

    def cedeu(self, endereco: str) -> list[dict[str, Any]]:
        return [e for e in self.diario.de(gov.CEDEU_NA_FONTE) if e.get("adaptador") == endereco]


@pytest.mark.parametrize("longe", OS_QUATRO, ids=("P1", "P2", "P3", "P4"))
def test_a_unica_ponte_longe_nao_abre_episodio_no_ramo_inteiro(longe: str) -> None:
    cena = _Cena(longe)
    for _ in range(8):
        cena.passo()
    assert not cena.diario.de(gov.CEDEU_NA_FONTE), "a cena cedeu antes do sinal cair"
    a = cena.governador._estados[ADAPTADOR_A]
    assert a.por_ponte and a.por_ponte > 0, "o adaptador A não mediu a ponte"

    # A janela em que o sinal cai: a ponte longe escreveu a janela inteira e A não pôs nada no ar.
    cena.medidor.capacidade[ADAPTADOR_A] = 0
    cena.sinal.dbm[gov._chave(longe)] = rm.SINAL_QUE_ATRASA_DBM - 5
    cena.passo()
    vaga = cena.vagas[longe]
    assert vaga.longe, "o sinal fraco não pausou a ponte: a cena não chegou ao ramo"
    assert a.fila > gov.LIMIAR_DO_DEFICIT, f"a fila de A ({a.fila}) não passou do limiar"
    assert a.inteiro, "o governador não passou pelo ramo `inteiro` de `_a_vez`"
    assert not vaga._cedendo_pela_fila, "o ramo `inteiro` deu o flag da fila à vaga longe"
    assert not a.cedendo, "uma ponte só, e longe: não há episódio no adaptador A"
    assert not cena.cedeu(ADAPTADOR_A), "o diário diz «cedeu» por uma ponte que já está muda"

    # As janelas seguintes: A volta a escoar, a ponte segue longe e muda, nada se abre.
    cena.medidor.capacidade[ADAPTADOR_A] = FOLGA_DO_B
    for _ in range(12):
        cena.passo()
        assert not vaga._cedendo_pela_fila
    publicado = cena.governador.publicar()
    assert publicado[ADAPTADOR_A]["cedendo"] is False
    assert not cena.cedeu(ADAPTADOR_A)

    # O adaptador B, com as duas pontes de rádio de pé, não cedeu por causa do A.
    assert publicado[ADAPTADOR_B]["cedendo"] is False
    assert not cena.cedeu(ADAPTADOR_B)
    assert all(not v.cedendo for u, v in cena.vagas.items() if cena.onde[u] == ADAPTADOR_B)

    # O cabo não entra na fila: nem estado, nem flag, nem linha no que se publica.
    cabo = cena.vagas[cena.cabo]
    assert cabo.adaptador == ""
    assert "" not in cena.governador._estados and "" not in publicado
    assert not cabo.cedendo
