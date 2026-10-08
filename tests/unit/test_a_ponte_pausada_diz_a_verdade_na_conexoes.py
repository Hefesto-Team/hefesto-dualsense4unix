"""A-PONTE-PAUSADA-DIZ-A-VERDADE-NA-CONEXOES-01: a ponte pausada diz a verdade na Conexões.

Três furos que a conferência da O-SINAL-DE-CADA-CONTROLE-DIZ-SE-ELE-ESTA-LONGE-01 achou, uma
régua para cada um:

1. a caixa da ponte do controle longe dizia «94 Hz», a constante de projeto, com a ponte
   pausada: o campo ao vivo `hz-ponte` diz a taxa que a ponte escreve de verdade (vazio quando
   ela cede);
2. o governador contava a ponte `longe` (muda, não escreve) na vez da fila, e as vizinhas
   cediam por ela: `_a_vez` exclui a vaga longe da conta e do rodízio;
3. a proposta do Equilibrar não dizia que veio do sinal: a proposta leva `pelo_sinal` e os dois
   dBm, e o cartão e o balão dizem «sinal fraco».

A BANCADA do furo 2 é o governador real com o relógio e o diário de mentira, e o adaptador
de mentira que escoa até a capacidade de cada janela (o dublê das réguas da O-GOVERNADOR-NAO-
FAZ-UMA-PONTE-SO-CEDER-01), com o sinal na mão da régua. A MORDIDA de cada régua está no
docstring dela.
"""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.daemon.subsystems import governador_do_radio as gov
from hefesto_dualsense4unix.integrations import radio_da_mesa as rm
from tests.unit.test_o_governador_do_radio import (
    ADAPTADOR_A,
    CONTROLE_1,
    CONTROLE_2,
    CONTROLE_3,
    _AdaptadorQueEscoaDuas,
    _Diario,
    _Relogio,
)

POR_JANELA = 93.75 * gov.PERIODO_S
JANELAS_ANTES = 100
JANELAS_DEPOIS = 300


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


class _Bancada:
    """O governador real com `controles` (uma ponte de som cada) num adaptador que escoa
    `capacidade` pacotes por janela. `passo()` fecha uma janela; `fraco(uniq)` põe o sinal dele
    abaixo do que atrasa o botão (o tique seguinte o lê).
    """

    def __init__(self, controles: tuple[str, ...], capacidade: int) -> None:
        self.relogio, registro = _Relogio(), _Diario()
        self.medidor = _AdaptadorQueEscoaDuas(capacidade=capacidade)
        self.governador = gov.GovernadorDoRadio(
            medidor=self.medidor, adaptador_de=lambda _u: ADAPTADOR_A,
            registrar=registro, relogio=self.relogio, n_max=4,
        )
        self.sinal = _Sinal()
        self.governador.leitor_do_sinal = self.sinal  # type: ignore[assignment]
        self.governador.tique()
        self.vagas: dict[str, gov.Vaga] = {}
        for uniq in controles:
            vaga = self.governador.pedir_vaga(uniq, "som")
            assert isinstance(vaga, gov.Vaga), f"{uniq} não recebeu vaga: {vaga}"
            vaga.subiu("som")
            self.vagas[uniq] = vaga
        self.cedidas = dict.fromkeys(controles, 0)
        self.quadros = dict.fromkeys(controles, 0)
        self.parada = 0
        self._sobra = 0.0
        self.contando = False

    def fraco(self, uniq: str) -> None:
        self.sinal.dbm[gov._chave(uniq)] = rm.SINAL_QUE_ATRASA_DBM - 5

    def passo(self) -> int:
        """Uma janela: quem não cede escreve a sua parte. Devolve quantas pontes escreveram."""
        self._sobra += POR_JANELA
        por_ponte, self._sobra = int(self._sobra), self._sobra - int(self._sobra)
        escreveram = 0
        for uniq, vaga in self.vagas.items():
            if self.contando and vaga.cedendo:
                self.cedidas[uniq] += 1
            if vaga.cedendo:
                continue
            for _ in range(por_ponte):
                vaga.contar_escrita()
            if self.contando:
                self.quadros[uniq] += por_ponte
            escreveram += 1
        if self.contando and not escreveram:
            self.parada += 1
        self.medidor.janela(escreveram * por_ponte)
        self.relogio.agora += gov.PERIODO_S
        self.governador.tique()
        return escreveram


def _correr(
    controles: tuple[str, ...], capacidade: int, *, longe: str | None = None
) -> _Bancada:
    """`longe` fica com o sinal fraco a partir da janela `JANELAS_ANTES`; o que se conta é só o
    que acontece nas `JANELAS_DEPOIS` seguintes (janelas cedidas e quadros de cada controle).
    """
    bancada = _Bancada(controles, capacidade)
    for janela in range(JANELAS_ANTES + JANELAS_DEPOIS):
        if janela == JANELAS_ANTES:
            bancada.contando = True
            if longe is not None:
                bancada.fraco(longe)
        bancada.passo()
    return bancada


# ---------------------------------------------------------------------------------------------
# Furo 2: a ponte longe não gasta a vez das outras
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("capacidade", [47, 24])
def test_a_ponte_longe_nao_gasta_a_vez_das_vizinhas(capacidade: int) -> None:
    """Três pontes, a A longe: B e C escrevem tanto quanto se a A nem existisse.

    O controle é a corrida de B e C sozinhas no mesmo adaptador (nunca um número tirado da
    saída), medida depois de `ASSENTA` janelas, quando a fila que a A deixou já escoou. A A
    está pausada pelo sinal: não escreve, e a fila não tem o que cobrar dela. MEDIDO em
    08/10/2026: a diferença da conta errada é de uma ou duas janelas (o flag some quando o
    rodízio solta a A), e não as dezenas que o dossiê da sprint contava; por isso a régua
    também pega o instante em que a A vira longe, no teste do flag logo abaixo.

    Esta régua não morde sozinha (a conta errada some em duas janelas): quem morde é a do flag,
    logo abaixo. Ela guarda o desfecho, a taxa das vizinhas, contra uma regressão maior.
    """
    com_a = _correr((CONTROLE_1, CONTROLE_2, CONTROLE_3), capacidade, longe=CONTROLE_1)
    controle = _correr((CONTROLE_2, CONTROLE_3), capacidade)

    assert com_a.vagas[CONTROLE_1].longe, "premissa: a A ficou pausada pelo sinal"
    # o tique que lê o sinal vem depois da janela em que ele ficou fraco: uma janela escapa
    assert com_a.quadros[CONTROLE_1] <= int(POR_JANELA) + 1, "premissa: a A pausada não escreve"
    de_b_e_c = com_a.quadros[CONTROLE_2] + com_a.quadros[CONTROLE_3]
    do_controle = controle.quadros[CONTROLE_2] + controle.quadros[CONTROLE_3]
    assert de_b_e_c >= do_controle - 4 * int(POR_JANELA), (
        f"B e C puseram {de_b_e_c} quadros com a A longe, e {do_controle} sem a A: a ponte "
        "muda gastou a vez das outras")


def test_o_flag_da_fila_nao_fica_na_vaga_longe() -> None:
    """A vaga que a fila mandou ceder e depois ficou longe larga o «cedendo pela fila» na hora.

    O flag existe para a fila do adaptador; numa vaga longe ele a deixaria na conta da vez
    (as vizinhas cedendo por uma ponte muda) e, quando o sinal voltasse, cedendo por uma fila
    que não é dela. Na capacidade 24 a A é escolhida pelo rodízio quase toda janela.

    MORDIDA: tirar o `vaga.cedendo = False` de `_o_sinal_protege_o_botao`, ou o `not vaga.longe`
    do `_conceder`/`_a_vez`.
    """
    bancada = _Bancada((CONTROLE_1, CONTROLE_2, CONTROLE_3), 24)
    a = bancada.vagas[CONTROLE_1]
    na_vez_do_par_b_e_c = False
    for _ in range(JANELAS_ANTES):
        bancada.passo()
        estado = next(iter(bancada.governador._estados.values()))
        # a A com o flag e o rodízio na vez do par B+C: com a A na conta, as duas cedem juntas
        na_vez_do_par_b_e_c = a._cedendo_pela_fila and estado.vez % 3 == 1
        if na_vez_do_par_b_e_c:
            break
    assert na_vez_do_par_b_e_c, "premissa: a A leva o flag e a vez cai no par B+C"
    bancada.fraco(CONTROLE_1)
    bancada.contando = True
    bancada.passo()  # o tique que lê o sinal
    assert a.longe and a._cedendo_pela_fila is False
    for _ in range(40):
        bancada.passo()
        assert a._cedendo_pela_fila is False, "a fila voltou a pôr o flag na vaga longe"
    assert bancada.parada == 0, "janelas sem nenhuma ponte escrevendo: as duas vizinhas cederam"


def test_a_ponte_que_nasce_no_episodio_com_o_controle_longe_nao_leva_o_flag() -> None:
    """A vaga concedida enquanto a fila cede e o controle está longe nasce só `longe`.

    MORDIDA: o `_conceder` voltando a pôr `vaga.cedendo = True` sem olhar a pausa.
    """
    bancada = _Bancada((CONTROLE_1, CONTROLE_2, CONTROLE_3), 24)
    for _ in range(20):
        bancada.passo()
    estado = next(iter(bancada.governador._estados.values()))
    assert estado.cedendo, "premissa: o adaptador está num episódio de ceder"
    bancada.fraco(CONTROLE_2)
    bancada.passo()
    bancada.passo()
    vaga = bancada.governador.pedir_vaga(CONTROLE_2, "vibracao")
    assert isinstance(vaga, gov.Vaga)
    assert vaga.longe and vaga._cedendo_pela_fila is False
