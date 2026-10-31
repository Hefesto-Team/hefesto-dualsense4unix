"""A estreia sem jogo: o posto de P1 nasce na carta que a tela vai mostrar, já no hotplug.

O ensaio é o de queda, com as classes reais (``MesaDoJogo``): o ``PyDualSenseController``, o
``CoopManager`` e o ``ControllerIdentityRegistry`` de verdade, o provider de cor fiado como o
daemon o fia, e o tique na ordem do ``lifecycle`` (o ``sync_connected`` e logo o
``seguir_a_carta``).

O que se mede, em dois, três e quatro controles, no cabo, no rádio e na mesa mista, sem jogo:

1. a sessão nova com a fila gravada, todos juntos e um de cada vez;
2. o lugar guardado de quem sai e volta no prazo, sozinho ou junto com um controle que estreia
   (a carta mista: quem estreia acende a lâmpada no hotplug, quem volta ainda não);
3. a troca de número feita na tela, que só o ``seguir_a_carta`` leva ao posto de P1.

Em todo tique, o posto de P1 escolhido no hotplug é o 1 da tela depois do ``sync_connected``
(o ``seguir_a_carta`` não precisa mexer) e o jogo segue a tela.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.daemon.subsystems.identity import (
    ControllerIdentityRegistry,
    prazo_do_lugar_guardado,
)
from tests.unit.test_o_jogo_espera_a_carta_do_lugar_guardado import (
    NOVO,
    TIQUE,
    TRANSPORTES,
    UNIQS,
    MesaDoJogo,
    Relogio,
    config_isolado,
    montar,
)

__all__ = ["config_isolado"]

MATRIZ = pytest.mark.parametrize(
    ("quantos", "transporte"),
    [(n, t) for n in (2, 3, 4) for t in TRANSPORTES],
    ids=[f"{n}-controles-{t}" for n in (2, 3, 4) for t in TRANSPORTES],
)
LUGARES = pytest.mark.parametrize(
    ("quantos", "transporte", "lugar"),
    [(n, t, i) for n in (2, 3, 4) for t in TRANSPORTES for i in range(n)],
    ids=[f"{n}-controles-{t}-p{i + 1}" for n in (2, 3, 4) for t in TRANSPORTES for i in range(n)],
)


class Registro:
    """O posto de P1 no fim de cada ``connect()`` e cada vez que o ``seguir_a_carta`` o moveu."""

    def __init__(self, ensaio: MesaDoJogo, monkeypatch: pytest.MonkeyPatch) -> None:
        self.no_hotplug: list[str | None] = []
        self.seguiu: list[str | None] = []
        connect = ensaio.connect
        seguir = ensaio.inst.seguir_a_carta

        def _connect() -> None:
            connect()
            self.no_hotplug.append(ensaio.inst.primary_uniq)

        def _seguir() -> bool:
            andou = seguir()
            if andou:
                self.seguiu.append(ensaio.inst.primary_uniq)
            return andou

        monkeypatch.setattr(ensaio, "connect", _connect)
        monkeypatch.setattr(ensaio.inst, "seguir_a_carta", _seguir)


def o_1_da_tela(ensaio: MesaDoJogo) -> str | None:
    """Quem está na mesa com o menor número da tela (o 1, ou o primeiro depois de um guardado)."""
    tela = ensaio.a_tela()
    return min(tela, key=tela.__getitem__) if tela else None


def conferir_o_tique(ensaio: MesaDoJogo, registro: Registro, contexto: str) -> None:
    """O hotplug já pôs no posto o 1 da tela, e o jogo segue a tela."""
    tela = ensaio.a_tela()
    primeiro = o_1_da_tela(ensaio)
    assert registro.seguiu == [], (
        f"{contexto}: o hotplug pôs no posto {registro.no_hotplug[-1:]} e o seguir_a_carta "
        f"teve de levá-lo a {registro.seguiu}; a tela: {tela}"
    )
    assert ensaio.inst.primary_uniq == primeiro, (
        f"{contexto}: o posto de P1 é {ensaio.inst.primary_uniq}, e o 1 da tela é {primeiro}; "
        f"a tela: {tela}"
    )
    assert registro.no_hotplug[-1] == primeiro, (
        f"{contexto}: no hotplug o posto foi para {registro.no_hotplug[-1]}, e o 1 da tela é "
        f"{primeiro}; a tela: {tela}"
    )
    if ensaio.coop.should_be_active() and sorted(tela.values()) == list(range(1, len(tela) + 1)):
        ensaio.o_jogo_segue_a_tela()


def _sessao_anterior(fila: tuple[str, ...]) -> None:
    """A fila de outra sessão no disco do lar de mentira, na ordem de ``fila``."""
    ControllerIdentityRegistry(clock=Relogio()).sync_connected(list(fila))


def _sessao_nova(monkeypatch: pytest.MonkeyPatch) -> MesaDoJogo:
    relogio = Relogio()
    ensaio = MesaDoJogo(monkeypatch, relogio=relogio, tempo=relogio, jogo=False)
    ensaio.reg.load()
    return ensaio


@pytest.mark.usefixtures("config_isolado")
class TestASessaoNovaComAFilaGravada:
    """O daemon sobe com a fila de outra sessão no disco e os controles chegam."""

    @MATRIZ
    def test_todos_juntos_sentam_na_fila_gravada(
        self, monkeypatch: pytest.MonkeyPatch, quantos: int, transporte: str
    ) -> None:
        mesa = UNIQS[:quantos]
        _sessao_anterior(mesa)
        ensaio = _sessao_nova(monkeypatch)
        registro = Registro(ensaio, monkeypatch)
        for uniq, via in zip(mesa, TRANSPORTES[transporte], strict=False):
            ensaio.mesa.sentar(uniq, transporte=via)
        for passo in range(4):
            ensaio.tique()
            conferir_o_tique(ensaio, registro, f"tique {passo}")
        assert ensaio.a_tela() == {u: n + 1 for n, u in enumerate(mesa)}

    @MATRIZ
    @pytest.mark.parametrize("ordem", ["a-da-fila", "a-do-avesso"])
    def test_um_de_cada_vez_o_primeiro_que_chega_e_o_1(
        self, monkeypatch: pytest.MonkeyPatch, quantos: int, transporte: str, ordem: str
    ) -> None:
        """A fila do momento (D-30): quem chega primeiro na sessão é o 1, e o posto nasce nele."""
        mesa = UNIQS[:quantos]
        _sessao_anterior(mesa)
        ensaio = _sessao_nova(monkeypatch)
        registro = Registro(ensaio, monkeypatch)
        chegada = mesa if ordem == "a-da-fila" else tuple(reversed(mesa))
        vias = dict(zip(mesa, TRANSPORTES[transporte], strict=False))
        for uniq in chegada:
            ensaio.mesa.sentar(uniq, transporte=vias[uniq])
            for passo in range(2):
                ensaio.tique()
                conferir_o_tique(ensaio, registro, f"{uniq} chegou, tique {passo}")
        assert ensaio.a_tela() == {u: n + 1 for n, u in enumerate(chegada)}


@pytest.mark.usefixtures("config_isolado")
class TestOLugarGuardadoNaEstreiaSemJogo:
    """Quem sai e volta no prazo, sem jogo, encontra o número dele, com ou sem gente nova."""

    @LUGARES
    @pytest.mark.parametrize("junto", ["sozinho", "com-quem-estreia"])
    def test_quem_volta_no_prazo_e_o_numero_dele_ja_no_hotplug(
        self,
        monkeypatch: pytest.MonkeyPatch,
        quantos: int,
        transporte: str,
        lugar: int,
        junto: str,
    ) -> None:
        ensaio = montar(monkeypatch, quantos, transporte, jogo=False)
        registro = Registro(ensaio, monkeypatch)
        quem = UNIQS[lugar]
        antes = ensaio.a_tela()
        via = ensaio.mesa.transporte_de(quem)

        ensaio.mesa.levantar(quem)
        for passo in range(3):
            ensaio.tique()
            conferir_o_tique(ensaio, registro, f"{quem} fora, tique {passo}")
        assert ensaio.reg.guardados(), "o lugar de quem saiu não ficou guardado"
        assert prazo_do_lugar_guardado() > 3 * TIQUE

        ensaio.mesa.sentar(quem, transporte=via)
        if junto == "com-quem-estreia":
            ensaio.mesa.sentar(NOVO, transporte="bt")
        for passo in range(3):
            ensaio.tique()
            conferir_o_tique(ensaio, registro, f"{quem} voltou {junto}, tique {passo}")
        tela = ensaio.a_tela()
        assert tela[quem] == antes[quem], (
            f"{quem} voltou no prazo e a tela diz {tela[quem]}, era {antes[quem]}"
        )
        if junto == "com-quem-estreia":
            assert tela[NOVO] == quantos + 1


@pytest.mark.usefixtures("config_isolado")
class TestATrocaNaTelaLevaOPosto:
    """O número trocado na tela muda o 1 sem hotplug: só o ``seguir_a_carta`` leva o posto.

    Sem nó novo, o ``reconnect_loop`` não chama o ``connect()`` nos dois tiques
    (``daemon/connection.py``, a sonda de 30 s com a mesa ligada).
    """

    @MATRIZ
    def test_o_ultimo_vira_o_1_e_o_posto_vai_com_ele(
        self, monkeypatch: pytest.MonkeyPatch, quantos: int, transporte: str
    ) -> None:
        ensaio = montar(monkeypatch, quantos, transporte, jogo=False)
        monkeypatch.setattr(ensaio, "connect", lambda: None)
        mesa = list(UNIQS[:quantos])
        desejada = [mesa[-1], *mesa[:-1]]
        postos = sorted(ensaio.reg.posto_na_fila(u) or 0 for u in mesa)
        ensaio.reg.escolha_da_mao(
            {
                ControllerIdentityRegistry._canonical(u)[0]: p
                for u, p in zip(desejada, postos, strict=True)
            }
        )
        ensaio.tique()
        ensaio.tique()
        assert ensaio.a_tela() == {u: n + 1 for n, u in enumerate(desejada)}
        assert ensaio.inst.primary_uniq == desejada[0], (
            f"a tela diz 1 para {desejada[0]} e o posto de P1 ficou com "
            f"{ensaio.inst.primary_uniq}"
        )
        assert ensaio.dono_do_vpad_do_p1() == desejada[0]
