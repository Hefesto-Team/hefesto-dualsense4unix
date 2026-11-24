"""O-VIRTUAL-DE-QUEM-FICOU-RENASCE-UMA-VEZ-SO-QUANDO-OS-OUTROS-SAEM-01 — a carta espera a lâmpada.

**A decisão (24/11/2026, ``D-2411-A-CARTA-DE-QUEM-FICOU-ESPERA-A-LAMPADA``,
a validar pelo usuário).** O nome do virtual vai no ``UHID_CREATE2`` e não se troca vivo. O
co-op lê a carta na lâmpada, que só avança quando o gatilho da cor solta a
tabela (1,5 s depois da última mudança). Com o último lugar guardado vencido e a
lâmpada ainda no número velho, o virtual de quem ficou renascia com o número
intermediário e, soltas as lâmpadas, de novo com o final: duas enumerações em
2 s, a barra de luz e o número trocando a cada uma (diário de 23/11/2026,
01h19). Agora a carta de quem ficou espera a lâmpada alcançar a mesa, com teto
no prazo do lugar guardado, e o virtual renasce uma vez só, com o número final
(ou não renasce, quando o nome dele já é o número final).

**O que se mediu (24/11/2026, o instrumento é o desta régua):** quatro controles
no cabo, sem jogo, três saem em fila e fica um; o relógio anda de 1 s; o
gatilho da cor é o de produção (``armar_gatilho_da_cor_por_numeracao`` e o
preparo ``_preparar_a_lightbar``), armado quando a numeração muda e disparado
1,5 s depois. Antes da cura, em 30 das 48 ordens e espaços (quem fica, a ordem
em que os outros saem, 1 s ou 3 s entre as saídas) o virtual de quem ficou
renasceu duas vezes, com a carta velha e depois com a final; nas outras 18 o
que ficou já era o controle da carta 1 e nada renasce. A reserva do posto de primário
não entra na conta: sem o jogo na autoridade a reserva não segura o posto nem muda a
carta de ninguém (medido pela mesma régua).

A mesa é a do Hefesto: máscara única para todos os controles
(``D-2710-O-MODO-E-UM-SO-PARA-TODOS-OS-CONTROLES``), então a régua varre os dois
modos de vpad (DualSense e Xbox) em vez de uma máscara por controle; mouse e
teclado não tem virtual e não passa por aqui.

AS MORDIDAS (24/11/2026, cada uma devolvida com o md5 conferido):

- ``_a_lampada_alcancou_a_mesa`` devolvendo sempre ``True`` reprova a
  sequência do diário, as matrizes de quem fica e a espera do controle novo;
- o teto da espera arrancado (``False`` até a lâmpada alcançar) reprova
  :func:`test_a_espera_tem_teto`.
"""
from __future__ import annotations

import itertools
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.core.lightbar_gatilho import ATRASO_APOS_A_ULTIMA_CONEXAO_S
from hefesto_dualsense4unix.daemon import connection as cx
from hefesto_dualsense4unix.daemon.subsystems.identity import prazo_do_lugar_guardado
from tests.unit.test_a_entrada_de_cada_jogador_chega_inteira import _nomes_errados
from tests.unit.test_o_jogo_espera_a_carta_do_lugar_guardado import (
    NOVO,
    MesaDoJogo,
    config_isolado,  # noqa: F401
)
from tests.unit.test_o_modo_tem_um_dono import FILA_DO_USUARIO, TRANSPORTES, _a_mesa_do_boot

PRAZO = prazo_do_lugar_guardado()
APOS_O_PRAZO = int(PRAZO) + 15
MODOS = ("dualsense", "xbox")


class MesaComOGatilho:
    """O ensaio de nomes, com o gatilho da cor de produção disparando as lâmpadas."""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        transporte: str = "usb",
        modo: str = "dualsense",
        solta_a_lampada: bool = True,
    ) -> None:
        self.armados: list[float] = []
        self.solta_a_lampada = solta_a_lampada
        monkeypatch.setattr(cx, "registrar_gatilho_da_lightbar", lambda _d: None)
        monkeypatch.setattr(
            cx, "armar_gatilho", lambda _d, _nome, **_kw: self.armados.append(self.agora())
        )
        self.ensaio: MesaDoJogo = _a_mesa_do_boot(
            monkeypatch, FILA_DO_USUARIO, jogo=False, transporte=transporte
        )
        self.ensaio.daemon.config.gamepad_flavor = modo
        for _ in range(6):
            self.volta(2.0)

    def agora(self) -> float:
        return float(self.ensaio.tempo.t)  # type: ignore[union-attr]

    def volta(self, segundos: float = 1.0) -> None:
        """Um tique do co-op e a volta do laço que confere a numeração e dispara o gatilho."""
        self.ensaio.tique(segundos)
        cx.armar_gatilho_da_cor_por_numeracao(self.ensaio.daemon)
        if self.solta_a_lampada and self.armados and (
            self.agora() - self.armados[-1] >= ATRASO_APOS_A_ULTIMA_CONEXAO_S
        ):
            self.armados.clear()
            cx._preparar_a_lightbar(self.ensaio.daemon)

    def sair(self, quem: tuple[str, ...], *, entre_saidas: int) -> None:
        for uniq in quem:
            self.ensaio.mesa.levantar(uniq)
            for _ in range(entre_saidas):
                self.volta()

    def passar(self, tiques: int) -> None:
        for _ in range(tiques):
            self.volta()


def _recriacoes(diario: Sequence[Mapping[str, Any]]) -> Counter[str]:
    """Quantas vezes cada virtual (pelo rótulo do co-op) foi recriado pela ordem."""
    contas: Counter[str] = Counter()
    for registro in diario:
        if registro["event"] == "coop_ordem_recriada":
            contas.update(registro["recriar"])
    return contas


def _o_final_de_cada_um(mesa: MesaComOGatilho) -> dict[str, int]:
    """Rótulo do co-op -> o número que a tela diz depois de tudo assentar."""
    tela = mesa.ensaio.a_tela()
    primario = mesa.ensaio.coop._primary_identity()
    return {("p1" if uniq == primario else uniq): numero for uniq, numero in tela.items()}


def _confere_uma_vez_so(
    mesa: MesaComOGatilho, diario: Sequence[Mapping[str, Any]], ficam: tuple[str, ...]
) -> None:
    final = _o_final_de_cada_um(mesa)
    assert mesa.ensaio.a_tela() == {u: n + 1 for n, u in enumerate(ficam)}
    assert _nomes_errados(mesa.ensaio) == [], "um virtual ficou com o número de quando nasceu"
    contas = _recriacoes(diario)
    assert all(vezes <= 1 for vezes in contas.values()), (
        f"um virtual renasceu mais de uma vez: {dict(contas)}"
    )
    for registro in diario:
        if registro["event"] != "coop_ordem_recriada":
            continue
        for rotulo in registro["recriar"]:
            assert registro["cartas"][rotulo] == final[rotulo], (
                f"{rotulo} renasceu com a carta {registro['cartas'][rotulo]} e a final é "
                f"{final[rotulo]}: {registro}"
            )
    nomes = [r for r in diario if r["event"] == "coop_nome_do_virtual_renasce"]
    assert len(nomes) <= len(ficam), f"o diário diz {len(nomes)} episódios de nome velho"


@pytest.mark.usefixtures("config_isolado")
@pytest.mark.parametrize("modo", MODOS)
def test_a_sequencia_do_diario_nao_recria_duas_vezes(
    monkeypatch: pytest.MonkeyPatch, modo: str
) -> None:
    """Quatro no cabo, saem o 4, o 2 e o 1 em seis segundos, fica o 3 (diário de 23/11, 01h18).

    Na base esta ordem renascia o virtual de quem ficou duas vezes: «Hefesto P2» e,
    2 s depois, «Hefesto P1».
    """
    mesa = MesaComOGatilho(monkeypatch, transporte="usb", modo=modo)
    roxo = FILA_DO_USUARIO[2]
    with structlog.testing.capture_logs() as diario:
        mesa.sair(
            (FILA_DO_USUARIO[3], FILA_DO_USUARIO[1], FILA_DO_USUARIO[0]), entre_saidas=3
        )
        mesa.passar(APOS_O_PRAZO)
    assert [r["event"] for r in diario].count("lugar_guardado_venceu") == 3
    _confere_uma_vez_so(mesa, diario, (roxo,))
    assert _recriacoes(diario) == Counter(), "o virtual de quem ficou já era o P1: nada renasce"
    assert [v.player for v in mesa.ensaio.vpads if v.vivo] == [1]


_COMBINACOES = [
    (ancora, quantos_saem, ordem_dos_que_saem)
    for ancora in range(4)
    for quantos_saem in (1, 2, 3)
    for ordem_dos_que_saem in ("fila", "inversa")
]


@pytest.mark.usefixtures("config_isolado")
@pytest.mark.parametrize("transporte", sorted(TRANSPORTES))
@pytest.mark.parametrize(
    ("ancora", "quantos_saem", "ordem"),
    _COMBINACOES,
    ids=[f"fica-p{a + 1}-saem-{q}-{o}" for a, q, o in _COMBINACOES],
)
def test_quem_fica_renasce_no_maximo_uma_vez_com_a_carta_final(
    monkeypatch: pytest.MonkeyPatch,
    transporte: str,
    ancora: int,
    quantos_saem: int,
    ordem: str,
) -> None:
    """Quem fica (P1 a P4) por quantos saem (1 a 3), cabo, rádio e a mesa mista."""
    mesa = MesaComOGatilho(monkeypatch, transporte=transporte)
    ancora_uniq = FILA_DO_USUARIO[ancora]
    outros = [u for u in FILA_DO_USUARIO if u != ancora_uniq]
    saem = tuple(outros[:quantos_saem])
    saem = saem if ordem == "fila" else tuple(reversed(saem))
    ficam = tuple(u for u in FILA_DO_USUARIO if u not in saem)
    with structlog.testing.capture_logs() as diario:
        mesa.sair(saem, entre_saidas=2)
        mesa.passar(APOS_O_PRAZO)
    _confere_uma_vez_so(mesa, diario, ficam)


@pytest.mark.usefixtures("config_isolado")
@pytest.mark.parametrize("espaco", [1, 3])
@pytest.mark.parametrize("saem", list(itertools.permutations(range(3))))
def test_toda_ordem_de_saida_do_p4_e_do_p2_e_do_p1_deixa_o_p3_sem_recriar(
    monkeypatch: pytest.MonkeyPatch, saem: tuple[int, ...], espaco: int
) -> None:
    """As seis ordens em que os três saem, com 1 s e 3 s entre as saídas: fica o P3."""
    mesa = MesaComOGatilho(monkeypatch, transporte="mista")
    de_fora = (FILA_DO_USUARIO[0], FILA_DO_USUARIO[1], FILA_DO_USUARIO[3])
    with structlog.testing.capture_logs() as diario:
        mesa.sair(tuple(de_fora[i] for i in saem), entre_saidas=espaco)
        mesa.passar(APOS_O_PRAZO)
    _confere_uma_vez_so(mesa, diario, (FILA_DO_USUARIO[2],))
    assert _recriacoes(diario) == Counter()


@pytest.mark.usefixtures("config_isolado")
@pytest.mark.parametrize("transporte", ["usb", "mista"])
@pytest.mark.parametrize("quem", range(4), ids=["p1", "p2", "p3", "p4"])
def test_quem_sai_e_volta_antes_do_prazo_nao_renasce_pelo_nome(
    monkeypatch: pytest.MonkeyPatch, quem: int, transporte: str
) -> None:
    """Dentro do prazo ninguém renasce pelo nome; só quem ficou ATRÁS do que voltou, pela ordem.

    Sem jogo o lugar de cada virtual é a ordem em que ele nasceu: o controle que
    volta nasce de novo e os de trás renascem uma vez para ficar depois dele
    (``planejar_a_ordem``, medido na base em 24/11/2026). O último da fila não
    move ninguém.
    """
    mesa = MesaComOGatilho(monkeypatch, transporte=transporte)
    uniq = FILA_DO_USUARIO[quem]
    with structlog.testing.capture_logs() as diario:
        mesa.sair((uniq,), entre_saidas=2)
        mesa.passar(10)
        mesa.ensaio.mesa.sentar(uniq, transporte=TRANSPORTES[transporte][quem])
        mesa.passar(40)
    assert [r for r in diario if r["event"] == "lugar_guardado_venceu"] == []
    assert [r for r in diario if r["event"] == "coop_nome_do_virtual_renasce"] == []
    contas = _recriacoes(diario)
    assert all(vezes <= 1 for vezes in contas.values()), dict(contas)
    atras = set(FILA_DO_USUARIO[quem + 1 :])
    assert set(contas) <= atras, f"renasceu quem estava na frente de quem voltou: {dict(contas)}"
    if quem == len(FILA_DO_USUARIO) - 1:
        assert contas == Counter()
    assert mesa.ensaio.a_tela() == {u: n + 1 for n, u in enumerate(FILA_DO_USUARIO)}
    assert _nomes_errados(mesa.ensaio) == []


@pytest.mark.usefixtures("config_isolado")
def test_controle_novo_na_espera_nasce_na_hora_com_o_numero_certo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Três saem; um controle novo entra com os lugares ainda guardados: nasce já."""
    mesa = MesaComOGatilho(monkeypatch, transporte="usb")
    mesa.sair(
        (FILA_DO_USUARIO[0], FILA_DO_USUARIO[1], FILA_DO_USUARIO[3]), entre_saidas=2
    )
    mesa.passar(4)
    assert mesa.ensaio.vpad_de(NOVO) is None
    with structlog.testing.capture_logs() as diario:
        mesa.ensaio.mesa.sentar(NOVO, transporte="usb")
        nasceu_em = None
        for tique in range(1, 7):
            mesa.passar(1)
            if mesa.ensaio.vpad_de(NOVO) is not None:
                nasceu_em = tique
                break
        assert nasceu_em is not None, "o controle novo esperou a mesa assentar"
        assert mesa.ensaio.vpad_de(NOVO).player == mesa.ensaio.a_tela()[NOVO]
        mesa.passar(APOS_O_PRAZO)
    assert _recriacoes(diario)[NOVO] == 0
    assert all(vezes <= 1 for vezes in _recriacoes(diario).values())
    assert _nomes_errados(mesa.ensaio) == []


@pytest.mark.usefixtures("config_isolado")
def test_a_espera_tem_teto(monkeypatch: pytest.MonkeyPatch) -> None:
    """Com a lâmpada que nunca é solta, o nome velho espera o prazo e então renasce."""
    relogio = {"t": 5000.0}
    monkeypatch.setattr(time, "monotonic", lambda: relogio["t"])
    mesa = MesaComOGatilho(monkeypatch, transporte="usb", solta_a_lampada=False)
    mesa.ensaio.reg.liberar_as_lampadas()
    mesa.ensaio.mesa.levantar(FILA_DO_USUARIO[0])
    with structlog.testing.capture_logs() as diario:
        for _ in range(int(PRAZO) + 3):
            relogio["t"] += 1.0
            mesa.volta()
        antes_do_teto = [
            r for r in diario if r["event"] == "coop_nome_do_virtual_renasce"
        ]
        for _ in range(int(PRAZO) + 6):
            relogio["t"] += 1.0
            mesa.volta()
    depois = [r for r in diario if r["event"] == "coop_nome_do_virtual_renasce"]
    assert antes_do_teto == [], "o nome renasceu com a lâmpada ainda atrasada"
    assert depois, "a espera não tem teto: a lâmpada nunca solta e o nome nunca renasce"
