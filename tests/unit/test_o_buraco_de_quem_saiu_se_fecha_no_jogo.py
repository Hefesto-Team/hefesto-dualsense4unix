"""O-ASSENTO-GUARDADO-NAO-ANDA-03 — passado o prazo, o jogo fecha o buraco junto com a tela.

**A decisão já era dela** (23/09/2026, 22h, ``D-2309-FORA-DE-ORDEM-SE-RECRIA-
NA-HORA``): *a carta renumerada, a menor que chega depois da maior e o buraco
de quem saiu se recriam na hora*. O número que a lâmpada mostra é o boneco que
o jogo mexe. **O limite continua sendo a R-04:** com o jogo na autoridade, o
vpad do P1 não se recria.

**O QUE FOI MEDIDO, antes da cura** (a bancada de queda da O-ASSENTO-02, com a
classe real): passado o prazo do lugar guardado, com o jogo aberto, o P3 e o
P4 seguiam nos bonecos 3 e 4 com a tela e a lâmpada dizendo 2 e 3. Em 18 de 30
casos — dois, três e quatro controles; USB, BT e mista; cada lugar saindo — e
nos três do «Renumerar agora», o jogo discordava da tela. A causa: o
``planejar_a_ordem`` só exigia cartas em ORDEM, e o buraco continua em ordem.

**A cura mora no dono** (``coop.planejar_a_ordem``): entre os planos em ordem,
o que deixa menos gente fora do boneco da própria carta, e no empate o que
recria menos. Só quem ficou atrás do buraco renasce, uma vez cada. **E quem já
está no boneco certo não sai para fechar o buraco de ninguém** — o item 3 da
sprint: a varredura de todas as mesas de até quatro lugares achou 60 em que o
plano de sufixo tiraria do jogo quem não precisava sair (um lugar ainda
guardado atrás do buraco que venceu); esses casos ficam como eram.

**O dublê do vpad tira o MAC como o produto PEDE** (``vpad_mac``, pela
identidade do aparelho — ``MesaDoJogo._nascer_vpad``). O da bancada de queda o
tira do NÚMERO, e é mais frouxo que o real justamente na volta tardia do P1. A
conferência passou o dublê honesto para a bancada da O-ASSENTO-02, e as réguas
dela também medem com ele. **A volta tardia mede com a** :class:`MesaHonesta`
(O-VPAD-DO-P1-NAO-REPETE-O-MAC-01): cada vpad nasce pela fábrica e pela classe
REAIS contra um kernel de mentira que recusa MAC repetido com ``-EEXIST``, e o
MAC é o que o dono dos vivos VESTE — ver :class:`TestAVoltaTardiaDoP1`.

**E o JOGO é visto de fora** (``JogoPorFora``, na bancada da O-ASSENTO-02): o
lugar de cada vpad sai da ordem em que ele nasce e morre, e não da mesa que o
co-op guarda, que é a saída do próprio produto. Medido na conferência: com o
co-op só reescrevendo a própria anotação, sem recriar vpad nenhum, as 56
réguas da O-ASSENTO-02 passavam todas.

AS MORDIDAS (24/09/2026, cada uma devolvida com o md5 conferido):

- ``_fora_do_boneco`` devolvendo sempre 0 (a regra de antes, só a ordem)
  reprova :class:`TestPassadoOPrazoOJogoFechaOBuraco`,
  :class:`TestORenumerarAgoraFechaNaHora` e as linhas do plano;
- sem a guarda de quem já está no boneco certo, reprovam
  ``test_quem_esta_no_boneco_certo_nao_sai_para_fechar_o_buraco_de_ninguem`` e
  a varredura;
- a carta do co-op lida da TELA (``numeros_da_mesa``) em vez da lâmpada
  reprova ``test_o_jogo_muda_junto_com_a_lampada_e_nao_antes`` nos seis casos
  com alguém atrás do buraco: o jogo correria na frente da lâmpada;
- (conferência) ``CoopManager._posto_vago`` devolvendo sempre False reprova
  :class:`TestOPrazoDeOutroVenceComOPostoVago` nos 18 casos com alguém atrás
  de quem saiu; a vaga mexendo no aviso do P1 reprova os nove de
  ``test_a_vaga_nao_diz_que_o_p1_voltou_ao_boneco_dele``; e a carta
  emprestada ao P1 ausente no diário reprova a primeira classe inteira. A
  carta emprestada trocada por 99 passa tudo: com o jogo na autoridade ela
  não escolhe plano nenhum, que é o que a cura afirma;
- (O-VPAD-DO-P1-NAO-REPETE-O-MAC-01) ``_MacsDosVpadsVivos.vestir`` vestindo o
  MAC pedido sem olhar quem já o veste reprova as 18 da volta tardia pela
  :class:`MesaHonesta`, cada uma com o kernel recusando o MAC de quem o posto
  carrega (``Duplicate device found for MAC address``).

Nenhum endereço real: faixa forjada ``aa:bb:cc`` com os octetos 4 e 5 zerados.
"""
from __future__ import annotations

import itertools
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.core.backend_pydualsense import PRIMARIO_RESERVA_SEC
from hefesto_dualsense4unix.daemon.subsystems.coop import (
    _a_mesa_depois,
    _em_ordem,
    _fora_do_boneco,
    planejar_a_ordem,
)
from hefesto_dualsense4unix.daemon.subsystems.gamepad import vpad_vivo
from hefesto_dualsense4unix.daemon.subsystems.identity import prazo_do_lugar_guardado
from hefesto_dualsense4unix.integrations import virtual_pad
from hefesto_dualsense4unix.integrations.uhid_gamepad import vpad_mac
from tests.unit.test_dois_vpads_nunca_tem_o_mesmo_mac import (
    KernelDoHidPlaystation,
    kernel_de_mentira,
)
from tests.unit.test_o_jogo_espera_a_carta_do_lugar_guardado import (  # noqa: F401
    P1,
    P2,
    TIQUE,
    TRANSPORTES,
    UNIQS,
    MesaDoJogo,
    Relogio,
    config_isolado,
    montar,
)

#: A fábrica REAL dos vpads, guardada antes de qualquer bancada trocá-la pelo
#: dublê (a bancada da O-ASSENTO-02 põe o ``_nascer_vpad`` dela no lugar).
_FABRICA_REAL = virtual_pad.make_virtual_pad

#: O gesto da linha 17: fora vinte segundos — ainda dentro do prazo.
VINTE_SEGUNDOS = 20.0

QUEM_SAI = [
    pytest.param(quantos, transporte, quem, id=f"{quantos}-controles-{transporte}-sai-p{quem + 1}")
    for quantos in (2, 3, 4)
    for transporte in TRANSPORTES
    for quem in range(quantos)
]
MATRIZ = pytest.mark.parametrize(
    ("quantos", "transporte"),
    [(n, t) for n in (2, 3, 4) for t in TRANSPORTES],
    ids=[f"{n}-controles-{t}" for n in (2, 3, 4) for t in TRANSPORTES],
)


def _nascidos(bancada: MesaDoJogo, desde: int, uniq: str) -> list[Any]:
    return [v for v in bancada.vpads[desde:] if getattr(v, "identidade", None) == uniq]


def _ticks_ate_o_fim_do_prazo(ja_passou: float) -> int:
    prazo = max(PRIMARIO_RESERVA_SEC, prazo_do_lugar_guardado())
    return int((prazo - ja_passou + TIQUE) / TIQUE) + 1


def _atras_e_na_frente(quantos: int, quem: int) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Quem fica atrás do buraco (renasce) e quem fica na frente (não se mexe).

    Com o P1 fora, o P2 assume o vpad do posto (a NUM-01) e o buraco que se
    fecha é o do vpad dele: atrás ficam o P3 e o P4.
    """
    if quem == 0:
        return UNIQS[2:quantos], ()
    return UNIQS[quem + 1 : quantos], UNIQS[1:quem]


@pytest.fixture
def kernel(monkeypatch: pytest.MonkeyPatch) -> Iterator[KernelDoHidPlaystation]:
    """O kernel de mentira da régua irmã, com a recusa do ``hid_playstation``."""
    with kernel_de_mentira(monkeypatch) as k:
        yield k


class MesaHonesta(MesaDoJogo):
    """A bancada da O-ASSENTO-02 com os vpads da fábrica REAL, contra o kernel de mentira.

    O-VPAD-DO-P1-NAO-REPETE-O-MAC-01. O ``_VpadDaMesa`` da bancada recebe o MAC
    de uma conta feita pela régua e nasce sempre: um vpad que o kernel recusaria
    seguia movendo boneco, e a colisão só aparecia porque a invariante a
    procurava. Aqui cada vpad — o do posto e os dos secundários — nasce por
    ``virtual_pad.make_virtual_pad``, com o ``_try_uhid`` e o
    ``UhidDualSense.start`` de verdade, e quem diz se ele fica de pé é o
    :class:`KernelDoHidPlaystation`. Recusado, o produto cai no ``uinput``, como
    cairia na mesa dela, e a cada tique a bancada confere que o kernel não
    recusou ninguém.
    """

    def __init__(
        self, monkeypatch: pytest.MonkeyPatch, *, kernel: KernelDoHidPlaystation, **kw: Any
    ) -> None:
        self.kernel = kernel
        super().__init__(monkeypatch, **kw)
        # O vpad do P1 da bancada nasceu de mentira: ele sai e o do BOOT nasce
        # pela fábrica — sem identidade, porque o daemon ainda não conhece o
        # primário (a invariante VPAD-03/BT-01).
        self.vpad_do_p1.stop()
        self.vpads = []
        posto = self._nascer_vpad("dualsense", player=1, identity=None, allow_uhid=True)
        self.vpad_do_p1 = self.daemon._gamepad_device = posto

    def _nascer_vpad(
        self, flavor: Any, *, player: int = 1, identity: str | None = None, **kw: Any
    ) -> Any:
        pad = _FABRICA_REAL(flavor, player=player, identity=identity, **kw)
        if pad is None:
            return None
        if getattr(pad, "backend", None) != "uhid":
            pad.player = player  # o uinput não carrega número no nome
        pad.identidade = identity
        pad.vivo = True
        self.jogo.nasceu(pad)
        parar = pad.stop

        def _stop() -> None:
            if pad.vivo:
                pad.vivo = False
                self.jogo.morreu(pad)
            parar()

        pad.stop = _stop
        self.vpads.append(pad)
        return pad

    def conferir_invariantes(self) -> None:
        """As da bancada, sobre os vpads que TÊM MAC — e o kernel não recusou ninguém."""
        todos = self.vpads
        self.vpads = [v for v in todos if getattr(v, "backend", None) == "uhid"]
        try:
            super().conferir_invariantes()
        finally:
            self.vpads = todos
        assert not self.kernel.recusas, f"o kernel recusou: {self.kernel.recusas}"


def montar_honesto(
    monkeypatch: pytest.MonkeyPatch,
    kernel: KernelDoHidPlaystation,
    quantos: int,
    transporte: str = "mista",
) -> MesaHonesta:
    """O ``montar`` da O-ASSENTO-02, com a :class:`MesaHonesta` e o jogo aberto."""
    relogio = Relogio()
    bancada = MesaHonesta(monkeypatch, kernel=kernel, relogio=relogio, tempo=relogio)
    for uniq, via in zip(UNIQS[:quantos], TRANSPORTES[transporte][:quantos], strict=True):
        bancada.mesa.sentar(uniq, transporte=via)
    for _ in range(3):
        bancada.tique()
    assert bancada.dono_do_vpad_do_p1() == P1
    assert bancada.o_jogo_ve() == {n + 1: UNIQS[n] for n in range(quantos)}
    assert bancada.a_tela() == {UNIQS[n]: n + 1 for n in range(quantos)}
    assert all(getattr(v, "backend", None) == "uhid" for v in bancada.vpads)
    return bancada


def _sai_e_volta_tarde(bancada: MesaDoJogo, uniq: str) -> None:
    """``uniq`` sai, o prazo do lugar guardado vence, e ele volta com o jogo aberto."""
    via = bancada.mesa.transporte_de(uniq)
    bancada.mesa.levantar(uniq)
    for _ in range(_ticks_ate_o_fim_do_prazo(0.0)):
        bancada.tique()
    bancada.mesa.sentar(uniq, transporte=via)
    bancada.tique()
    bancada.tique()


def _volta_movendo_um_boneco_de_verdade(bancada: MesaHonesta, uniq: str) -> None:
    """Quem voltou dirige um boneco pelo vpad ``uhid`` que o kernel ACEITOU.

    Boneco só não basta: recusado, o produto cai no ``uinput``, e o jogo ainda
    vê um controle — sem vibração, giroscópio, gatilho nem luz. O vpad dele
    está de pé no driver, com um MAC que só ele veste, e o posto segue vivo.
    """
    vpad = bancada.vpad_de(uniq)
    assert vpad is not None and getattr(vpad, "backend", None) == "uhid", (
        f"{uniq} voltou num vpad degradado: {vpad!r}"
    )
    assert vpad_vivo(vpad), f"o kernel derrubou o vpad de {uniq}"
    assert bancada.vpad_do_p1.vivo and vpad.mac != bancada.vpad_do_p1.mac
    assert uniq in bancada.o_jogo_ve().values(), f"{uniq} voltou e não move boneco nenhum"
    vivos = sorted(
        v.mac for v in bancada.vpads if v.vivo and getattr(v, "backend", None) == "uhid"
    )
    no_driver = bancada.kernel.macs_na_lista()
    assert no_driver == vivos, f"o driver guarda {no_driver}, e os vpads vivos vestem {vivos}"
    assert bancada.kernel.recusas == []


def trocar_a_mascara_do_p1(bancada: MesaHonesta) -> None:
    """O vpad do posto renasce com a identidade do primário DE AGORA.

    É o que ``gamepad.start_gamepad_emulation_desfecho`` faz numa troca de
    máscara ou de caminho (e o ``_reerguer_o_p1`` do co-op): para o vpad velho
    e chama a fábrica com ``primary_identity`` e ``numero_do_nome_do_primario``
    — as mesmas duas perguntas, aos mesmos donos. Com o jogo aberto só o gesto
    dela chega aqui (a R-04 barra o automático), e ela pode trocar a máscara
    no meio da partida.
    """
    from hefesto_dualsense4unix.daemon.subsystems.coop import numero_do_nome_do_primario
    from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
        controller_allows_uhid,
        primary_identity,
    )

    daemon = bancada.daemon
    daemon._gamepad_device.stop()
    daemon._gamepad_device = None
    novo = virtual_pad.make_virtual_pad(
        "dualsense",
        identity=primary_identity(daemon),
        player=numero_do_nome_do_primario(daemon),
        allow_uhid=controller_allows_uhid(daemon),
    )
    assert novo is not None
    bancada.vpad_do_p1 = daemon._gamepad_device = novo


@pytest.mark.usefixtures("config_isolado")
class TestPassadoOPrazoOJogoFechaOBuraco:
    """O boneco de cada jogador antes do prazo, no fim dele, e depois, parado."""

    @pytest.mark.parametrize(("quantos", "transporte", "quem"), QUEM_SAI)
    def test_quem_ficou_atras_renasce_no_boneco_do_numero_novo(
        self, monkeypatch: pytest.MonkeyPatch, quantos: int, transporte: str, quem: int
    ) -> None:
        bancada = montar(monkeypatch, quantos, transporte)
        atras, na_frente = _atras_e_na_frente(quantos, quem)
        vpads_de_antes = {u: bancada.vpad_de(u) for u in UNIQS[1:quantos]}
        vpad_do_posto = bancada.vpad_do_p1
        bancada.mesa.levantar(UNIQS[quem])
        antes = len(bancada.vpads)

        # Antes do prazo: o lugar fica vazio, ninguém anda, ninguém renasce.
        for _ in range(int(VINTE_SEGUNDOS / TIQUE)):
            bancada.tique()
            bancada.o_jogo_segue_a_tela()
        assert len(bancada.vpads) == antes, "alguém renasceu dentro do prazo"

        # O fim do prazo: a fila se fecha na tela e o buraco se fecha no jogo.
        for _ in range(_ticks_ate_o_fim_do_prazo(VINTE_SEGUNDOS)):
            bancada.tique()
        tela = bancada.a_tela()
        assert tela == {
            u: n + 1 for n, u in enumerate(u for u in UNIQS[:quantos] if u != UNIQS[quem])
        }
        bancada.o_jogo_segue_a_tela()
        assert bancada.daemon._gamepad_device is vpad_do_posto, "a R-04: o vpad do P1 fica"
        assert vpad_do_posto.vivo
        for uniq in atras:
            nascidos = _nascidos(bancada, antes, uniq)
            assert len(nascidos) == 1, (
                f"{uniq} renasceu {len(nascidos)} vezes — é uma recriação por controle"
            )
            assert bancada.vpad_de(uniq) is nascidos[0] and nascidos[0].vivo
            # A-MESMA-LINGUA-01: o nome do vpad que renasce já diz o número novo.
            assert nascidos[0].player == tela[uniq]
        for uniq in na_frente:
            assert bancada.vpad_de(uniq) is vpads_de_antes[uniq], (
                f"{uniq} estava na frente do buraco e foi recriado"
            )

        # Depois: a mesa assentada não renasce de novo.
        assentada = len(bancada.vpads)
        for _ in range(3):
            bancada.tique()
            bancada.o_jogo_segue_a_tela()
        assert len(bancada.vpads) == assentada, "a mesa assentada renasceu de novo"

    @MATRIZ
    def test_o_jogo_muda_junto_com_a_lampada_e_nao_antes(
        self, monkeypatch: pytest.MonkeyPatch, quantos: int, transporte: str
    ) -> None:
        """A carta do co-op é o número da LÂMPADA, que só anda no gatilho da cor.

        A bancada deixa a tabela das lâmpadas vazia (a resposta é a mesa de
        agora); aqui ela é congelada como no produto, e só o
        ``liberar_as_lampadas`` — o gatilho que o ``reconnect_loop`` arma
        quando a numeração muda — a solta. A tela muda na hora; o jogo espera
        a lâmpada.
        """
        bancada = montar(monkeypatch, quantos, transporte)
        bancada.reg.liberar_as_lampadas()
        vpads_de_antes = {u: bancada.vpad_de(u) for u in UNIQS[1:quantos]}
        bancada.mesa.levantar(UNIQS[1])
        for _ in range(_ticks_ate_o_fim_do_prazo(0.0)):
            bancada.tique()
        assert bancada.a_tela() == {
            u: n + 1 for n, u in enumerate(u for u in UNIQS[:quantos] if u != UNIQS[1])
        }, "a tela não fechou a fila no fim do prazo"
        for uniq in UNIQS[2:quantos]:
            assert bancada.vpad_de(uniq) is vpads_de_antes[uniq], (
                f"{uniq} renasceu antes de a lâmpada mudar"
            )

        bancada.reg.liberar_as_lampadas()  # o gatilho da cor dispara
        bancada.tique()

        bancada.o_jogo_segue_a_tela()

    @MATRIZ
    def test_o_diario_diz_quem_renasceu(
        self, monkeypatch: pytest.MonkeyPatch, quantos: int, transporte: str
    ) -> None:
        bancada = montar(monkeypatch, quantos, transporte)
        bancada.mesa.levantar(UNIQS[1])
        for _ in range(int(VINTE_SEGUNDOS / TIQUE)):
            bancada.tique()
        with structlog.testing.capture_logs() as registros:
            for _ in range(_ticks_ate_o_fim_do_prazo(VINTE_SEGUNDOS)):
                bancada.tique()
        recriadas = [r for r in registros if r["event"] == "coop_ordem_recriada"]
        if quantos == 2:
            assert recriadas == []
            return
        assert len(recriadas) == 1
        assert recriadas[0]["recriar"] == list(UNIQS[2:quantos])
        assert recriadas[0]["jogo"] is True


@pytest.mark.usefixtures("config_isolado")
class TestORenumerarAgoraFechaNaHora:
    """O «Renumerar agora» fecha a fila dentro do prazo: o jogo fecha junto."""

    @pytest.mark.parametrize("transporte", list(TRANSPORTES))
    @pytest.mark.parametrize("quem", [0, 1, 2], ids=["sai-p1", "sai-p2", "sai-p3"])
    def test_o_jogo_segue_a_fila_fechada(
        self, monkeypatch: pytest.MonkeyPatch, quem: int, transporte: str
    ) -> None:
        bancada = montar(monkeypatch, 4, transporte)
        atras, _na_frente = _atras_e_na_frente(4, quem)
        bancada.mesa.levantar(UNIQS[quem])
        bancada.tique()
        antes = len(bancada.vpads)

        # O `identity.renumber` do IPC: o mapa dos lugares gravados.
        bancada.reg.compact(bancada.reg.snapshot())
        bancada.tique()
        bancada.tique()

        bancada.o_jogo_segue_a_tela()
        for uniq in atras:
            assert len(_nascidos(bancada, antes, uniq)) == 1


@pytest.mark.usefixtures("config_isolado")
class TestAVoltaTardiaDoP1:
    """O P1 que volta depois do prazo: o número na tela, o boneco que o jogo deu.

    O limite é a R-04 e não muda: o vpad do posto segue com o P2 até o jogo
    devolver a autoridade, e o diário diz ``coop_ordem_do_p1_espera_o_jogo``.
    Os secundários seguem a tela entre si.
    """

    @staticmethod
    def _p1_sai_e_volta_tarde(bancada: MesaDoJogo) -> list[dict[str, Any]]:
        via = bancada.mesa.transporte_de(P1)
        bancada.mesa.levantar(P1)
        for _ in range(_ticks_ate_o_fim_do_prazo(0.0)):
            bancada.tique()
        with structlog.testing.capture_logs() as registros:
            bancada.mesa.sentar(P1, transporte=via)
            bancada.tique()
            bancada.tique()
        return registros

    @MATRIZ
    def test_o_p1_recupera_o_numero_e_o_jogo_espera_a_autoridade(
        self, monkeypatch: pytest.MonkeyPatch, quantos: int, transporte: str
    ) -> None:
        bancada = montar(monkeypatch, quantos, transporte)
        vpad_do_posto = bancada.vpad_do_p1

        registros = self._p1_sai_e_volta_tarde(bancada)

        tela = bancada.a_tela()
        assert tela == {UNIQS[n]: n + 1 for n in range(quantos)}, "o P1 não recuperou o 1"
        assert bancada.inst.primary_uniq == P2, "controle que volta nunca rouba o posto"
        assert bancada.daemon._gamepad_device is vpad_do_posto and vpad_do_posto.vivo
        assert bancada.dono_do_vpad_do_p1() == P2
        jogo = bancada.o_jogo_ve()
        assert P1 in jogo.values(), f"o P1 voltou e não dirige boneco nenhum: {jogo}"
        for uniq in UNIQS[2:quantos]:
            assert jogo[tela[uniq]] == uniq, f"os secundários não seguem a tela: {jogo}"
        assert bancada.coop._p1_espera_o_jogo is True
        assert [r for r in registros if r["event"] == "coop_ordem_do_p1_espera_o_jogo"]

    @MATRIZ
    def test_o_vpad_do_p1_que_volta_nao_repete_o_mac_do_posto(
        self,
        monkeypatch: pytest.MonkeyPatch,
        kernel: KernelDoHidPlaystation,
        quantos: int,
        transporte: str,
    ) -> None:
        """O xfail estrito da O-ASSENTO-03, virado régua (O-VPAD-DO-P1-NAO-REPETE-O-MAC-01).

        A bancada honesta: a fábrica e a classe REAIS contra o kernel que
        recusa. A troca de máscara com o jogo aberto (o gesto dela, que a R-04
        nunca barra) faz o vpad do posto renascer com a identidade do P1; o P1
        sai, o prazo vence, o P2 assume o posto, e o P1 volta com o jogo
        aberto. Medido antes da cura: o kernel recusava o MAC do P1 com
        ``-EEXIST`` e ele voltava num vpad ``uinput`` degradado.

        A MORDIDA: ``_MacsDosVpadsVivos.vestir`` devolvendo sempre o
        ``vpad_mac`` pedido reprova os nove — ``Duplicate device found``.
        """
        bancada = montar_honesto(monkeypatch, kernel, quantos, transporte)
        trocar_a_mascara_do_p1(bancada)
        assert bancada.vpad_do_p1.mac == vpad_mac(P1, 1), "o posto nasceu com o MAC do P1"

        _sai_e_volta_tarde(bancada, P1)  # cada tique confere o kernel

        _volta_movendo_um_boneco_de_verdade(bancada, P1)
        assert bancada.inst.primary_uniq == P2, "controle que volta nunca rouba o posto"
        assert bancada.dono_do_vpad_do_p1() == P2

    @pytest.mark.parametrize(
        ("quantos", "transporte", "quem"),
        [
            pytest.param(n, t, q, id=f"{n}-controles-{t}-o-posto-carrega-p{q + 1}")
            for n in (3, 4)
            for t in TRANSPORTES
            for q in range(1, n - 1)
        ],
    )
    def test_quem_o_posto_carrega_volta_tarde_sem_repetir_o_mac(
        self,
        monkeypatch: pytest.MonkeyPatch,
        kernel: KernelDoHidPlaystation,
        quantos: int,
        transporte: str,
        quem: int,
    ) -> None:
        """Não é só o P1: o posto carrega a identidade de quem era o primário quando nasceu.

        Os que vêm antes de ``quem`` saem e o prazo de cada um vence (a NUM-01
        passa o posto adiante); a troca de máscara faz o posto renascer com a
        identidade de ``quem``, que sai, deixa o prazo vencer e volta. É a mesma
        colisão com outro dono — a do P1 é só a primeira da fila.
        """
        bancada = montar_honesto(monkeypatch, kernel, quantos, transporte)
        for antes in UNIQS[:quem]:
            bancada.mesa.levantar(antes)
            for _ in range(_ticks_ate_o_fim_do_prazo(0.0)):
                bancada.tique()
        uniq = UNIQS[quem]
        assert bancada.inst.primary_uniq == uniq
        trocar_a_mascara_do_p1(bancada)
        assert bancada.vpad_do_p1.mac == vpad_mac(uniq, 1)

        _sai_e_volta_tarde(bancada, uniq)

        _volta_movendo_um_boneco_de_verdade(bancada, uniq)
        assert bancada.inst.primary_uniq == UNIQS[quem + 1]


#: Quanto o OUTRO já está fora quando o P1 sai: o prazo dele vence com o do P1
#: ainda correndo.
OUTRO_JA_FORA = 26.0

DOIS_FORA = [
    pytest.param(
        quantos,
        transporte,
        outro,
        volta,
        id=f"{quantos}-controles-{transporte}-sai-p{outro + 1}-p1-{'volta' if volta else 'vence'}",
    )
    for quantos in (3, 4)
    for transporte in TRANSPORTES
    for outro in range(1, quantos)
    for volta in (True, False)
]


@pytest.mark.usefixtures("config_isolado")
class TestOPrazoDeOutroVenceComOPostoVago:
    """Dois fora: o prazo de um vence enquanto o posto do P1 espera por ele.

    A conferência de 24/09/2026. Com o P1 fora dentro do prazo e o jogo
    aberto, o vpad dele fica parado à espera (a O-ASSENTO-02), e o primário
    ausente não tem carta. O ``_ordenar`` desistia da mesa inteira por isso
    («sem carta não há ordem a obedecer»): o P4 ficava no boneco 4 com a tela
    e a lâmpada dizendo 3 até o P1 voltar ou o prazo DELE vencer — 24 s
    medidos na bancada. A cura: o vpad do P1 é fixo com o jogo na autoridade,
    então a carta dele não escolhe plano; ele leva a do lugar em que espera.

    A MORDIDA: ``_posto_vago`` devolvendo sempre False reprova os casos com
    alguém atrás de quem saiu.
    """

    @pytest.mark.parametrize(("quantos", "transporte", "outro", "volta"), DOIS_FORA)
    def test_quem_ficou_atras_desce_com_o_posto_vago(
        self,
        monkeypatch: pytest.MonkeyPatch,
        quantos: int,
        transporte: str,
        outro: int,
        volta: bool,
    ) -> None:
        bancada = montar(monkeypatch, quantos, transporte)
        vpad_do_posto = bancada.vpad_do_p1
        via_do_p1 = bancada.mesa.transporte_de(P1)
        ficaram = [u for u in UNIQS[1:quantos] if u != UNIQS[outro]]
        atras = UNIQS[outro + 1 : quantos]
        vpads_de_antes = {u: bancada.vpad_de(u) for u in ficaram}

        bancada.mesa.levantar(UNIQS[outro])
        for _ in range(int(OUTRO_JA_FORA / TIQUE)):
            bancada.tique()
        bancada.mesa.levantar(P1)
        antes = len(bancada.vpads)
        with structlog.testing.capture_logs() as registros:
            for _ in range(_ticks_ate_o_fim_do_prazo(OUTRO_JA_FORA)):
                bancada.tique()

        # O posto segue vago: o prazo do P1 ainda corre.
        assert bancada.inst.primary_uniq == P1
        assert bancada.dono_do_vpad_do_p1() is None
        assert bancada.daemon._gamepad_device is vpad_do_posto and vpad_do_posto.vivo
        # A fila do outro se fechou na tela, com o lugar do P1 ainda contando.
        assert bancada.a_tela() == {u: n + 2 for n, u in enumerate(ficaram)}
        bancada.o_jogo_segue_a_tela()
        for uniq in atras:
            assert len(_nascidos(bancada, antes, uniq)) == 1, (
                f"{uniq} ficou atrás do buraco com o posto vago e não desceu (ou desceu duas vezes)"
            )
        for uniq in set(ficaram) - set(atras):
            assert bancada.vpad_de(uniq) is vpads_de_antes[uniq], f"{uniq} estava na frente"
        recriadas = [r for r in registros if r["event"] == "coop_ordem_recriada"]
        assert [r["recriar"] for r in recriadas] == ([list(atras)] if atras else [])
        # O diário não inventa carta para o P1 ausente, nem diz que ele espera o jogo.
        assert all("p1" not in r["cartas"] for r in recriadas)
        assert not [r for r in registros if r["event"] == "coop_ordem_do_p1_espera_o_jogo"]

        assentada = len(bancada.vpads)
        if volta:
            bancada.mesa.sentar(P1, transporte=via_do_p1)
            bancada.tique()
            bancada.tique()
            assert bancada.inst.primary_uniq == P1
            assert bancada.dono_do_vpad_do_p1() == P1
            assert bancada.a_tela() == {P1: 1, **{u: n + 2 for n, u in enumerate(ficaram)}}
            assert len(bancada.vpads) == assentada, "a volta do P1 recriou alguém"
        else:
            for _ in range(_ticks_ate_o_fim_do_prazo(0.0)):
                bancada.tique()
            assert bancada.dono_do_vpad_do_p1() == ficaram[0]
            assert bancada.a_tela() == {u: n + 1 for n, u in enumerate(ficaram)}
        bancada.o_jogo_segue_a_tela()

    @MATRIZ
    def test_a_vaga_nao_diz_que_o_p1_voltou_ao_boneco_dele(
        self, monkeypatch: pytest.MonkeyPatch, quantos: int, transporte: str
    ) -> None:
        """Com o P1 no boneco 2 (a volta tardia), o posto vago do P2 não apaga o aviso.

        O P2 dirige o vpad do P1 depois da volta tardia; se ELE cai dentro do
        prazo, o posto fica vago à espera dele, e a carta que a vaga empresta
        ao vpad do P1 não é a de ninguém: ela não pode escrever no diário que
        o P1 voltou ao boneco dele — ele segue no 2 até o jogo fechar.
        """
        bancada = montar(monkeypatch, quantos, transporte)
        TestAVoltaTardiaDoP1._p1_sai_e_volta_tarde(bancada)
        assert bancada.coop._p1_espera_o_jogo is True
        bancada.mesa.levantar(P2)
        with structlog.testing.capture_logs() as registros:
            for _ in range(int(VINTE_SEGUNDOS / TIQUE)):
                bancada.tique()
        assert bancada.inst.primary_uniq == P2 and bancada.dono_do_vpad_do_p1() is None
        assert not [r for r in registros if r["event"] == "coop_ordem_do_p1_voltou"]
        assert bancada.coop._p1_espera_o_jogo is True


class TestOPlano:
    """``planejar_a_ordem``, puro, nas mesas que o produto monta."""

    FIXO = frozenset({"p1"})

    def test_passado_o_prazo_quem_ficou_atras_desce(self) -> None:
        """O P2 saiu: o vpad dele liberou o lugar 1 do jogo, e as cartas andaram.

        É a mesma mesa com o P1 fora: o vpad do posto (fixo, a R-04) leva a
        carta 1 do P2, e o vpad do P2, cedido, liberou o lugar 1.
        """
        mesa = {0: "p1", 2: "p3", 3: "p4"}
        assert planejar_a_ordem(mesa, {"p1": 1, "p3": 2, "p4": 3}, fixos=self.FIXO) == (
            ["p3", "p4"],
            True,
        )

    def test_dentro_do_prazo_o_lugar_guardado_nao_mexe_ninguem(self) -> None:
        mesa = {0: "p1", 2: "p3", 3: "p4"}
        assert planejar_a_ordem(mesa, {"p1": 1, "p3": 3, "p4": 4}, fixos=self.FIXO) == (
            [],
            True,
        )

    def test_so_quem_esta_atras_do_buraco_desce(self) -> None:
        """O P3 saiu: o P2 fica, só o P4 desce."""
        mesa = {0: "p1", 1: "p2", 3: "p4"}
        assert planejar_a_ordem(mesa, {"p1": 1, "p2": 2, "p4": 3}, fixos=self.FIXO) == (
            ["p4"],
            True,
        )

    def test_quem_esta_no_boneco_certo_nao_sai_para_fechar_o_buraco_de_ninguem(self) -> None:
        """O item 3 da sprint, achado pela varredura: o 4 ainda guardado.

        Recriar a partir da carta 2 fecharia o buraco do ``b`` e do ``c`` e
        poria o ``d`` (carta 5, no boneco 5) no lugar 3 do jogo — o do 4 que
        ainda pode voltar. Fica como era.
        """
        mesa = {0: "p1", 2: "b", 3: "c", 4: "d"}
        assert planejar_a_ordem(
            mesa, {"p1": 1, "b": 2, "c": 3, "d": 5}, fixos=self.FIXO
        ) == ([], True)

    def test_sem_jogo_nada_muda(self) -> None:
        """Sem jogo, o que abrir depois enumera na ordem de nascimento."""
        mesa = {0: "p1", 1: "p3", 2: "p4"}
        assert planejar_a_ordem(mesa, {"p1": 1, "p3": 3, "p4": 4}, compacta=True) == (
            [],
            True,
        )

    def test_a_volta_tardia_do_p1_o_fixo_fica(self) -> None:
        """O P1 volta depois do prazo com a carta 1: o posto (fixo) fica com o P2."""
        mesa = {0: "p1", 1: "p3", 2: "p4"}
        cartas = {"p1": 2, "p3": 3, "p4": 4, "volta": 1}
        assert planejar_a_ordem(mesa, cartas, ["volta"], fixos=self.FIXO) == (
            ["p3", "p4"],
            False,
        )


def _o_plano_de_antes(
    mesa: Mapping[int, str],
    cartas: Mapping[str, int],
    nascer: Sequence[str],
    *,
    fixos: frozenset[str],
    compacta: bool,
) -> list[str]:
    """O oráculo: a regra de antes desta sprint, só a ORDEM (STEAM-NO-FISICO-01)."""
    sentados = [c for _lugar, c in sorted(mesa.items())]
    limites = sorted({*(cartas[c] for c in sentados), *(cartas[c] for c in nascer)})
    for t in [max(limites, default=0) + 1, *reversed(limites)]:
        recriar = [c for c in sentados if cartas[c] >= t and c not in fixos]
        depois = _a_mesa_depois(mesa, recriar, nascer, cartas, compacta=compacta)
        if _em_ordem([cartas[c] for c in depois.values() if c not in fixos]):
            return recriar
    return []


def _as_mesas_do_produto() -> Any:
    """Toda mesa de até quatro lugares que o produto monta.

    Com jogo, o vpad do P1 sentado é sempre fixo (a R-04); sem jogo, a mesa
    chega compactada (o ``_ordenar`` roda o ``_compactar`` antes) e nada é fixo.
    """
    chaves = ["p1", "b", "c", "d"]
    for n in range(1, 5):
        for sentados_n in range(1, n + 1):
            sentados, nascer = chaves[:sentados_n], chaves[sentados_n:n]
            for cs in itertools.product(range(1, 6), repeat=n):
                if len(set(cs)) != n:
                    continue
                cartas = dict(zip(chaves[:n], cs, strict=True))
                for lugares in itertools.permutations(range(5), sentados_n):
                    mesa = dict(zip(lugares, sentados, strict=True))
                    yield mesa, cartas, nascer, frozenset({"p1"}), False
                for ordem in itertools.permutations(sentados):
                    yield dict(enumerate(ordem)), cartas, nascer, frozenset(), True


def test_a_varredura_das_mesas_do_produto() -> None:
    """Contra a regra de antes, em todas as mesas: a cura só melhora, e só quem precisa sai.

    - sem jogo, nada muda;
    - o fixo (o vpad do P1 com o jogo aberto) nunca é recriado;
    - quando o plano muda, menos gente fica fora do boneco da própria carta;
    - quem renasce além do plano de antes estava fora do boneco dele.
    """
    casos = mudaram = 0
    for mesa, cartas, nascer, fixos, compacta in _as_mesas_do_produto():
        casos += 1
        novo, _inteira = planejar_a_ordem(mesa, cartas, nascer, fixos=fixos, compacta=compacta)
        antes = _o_plano_de_antes(mesa, cartas, nascer, fixos=fixos, compacta=compacta)
        caso = (mesa, cartas, nascer, compacta)
        assert not set(novo) & fixos, caso
        if novo == antes:
            continue
        mudaram += 1
        assert not compacta, caso
        assert _fora_do_boneco(
            _a_mesa_depois(mesa, novo, nascer, cartas, compacta=compacta), cartas
        ) < _fora_do_boneco(
            _a_mesa_depois(mesa, antes, nascer, cartas, compacta=compacta), cartas
        ), caso
        lugar_de = {c: lugar for lugar, c in mesa.items()}
        for chave in set(novo) - set(antes):
            assert lugar_de[chave] != cartas[chave] - 1, (chave, caso)
    assert casos > 30_000 and mudaram > 1_000, (casos, mudaram)
