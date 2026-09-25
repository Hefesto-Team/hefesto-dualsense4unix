"""A-HAPTICA-SEGUE-QUEM-ALIMENTA-O-VPAD-01 — vibra o controle que dirige o boneco.

**O defeito.** O gate da háptica pelo rádio (QUEM-JOGA-E-QUEM-VIBRA-01) só
deixa entrar em modo háptica o controle que o JOGO está lendo, e com máscara o
jogo lê o vpad. A tradução vpad→físico derivava o MAC de cada físico
(``vpad_mac``) e comparava — o que responde de quem o vpad NASCEU. O posto
nasce sem identidade no boot (o piso ``02:fe:00:00:00:01``) ou com a do
primário de quando renasceu, e troca de mão sem renascer.

**Medido antes da cura** (25/09/2026), na bancada de queda com os vpads REAIS
(a :class:`MesaHonesta` da O-VPAD-DO-P1-NAO-REPETE-O-MAC-01) e o jogo visto de
fora (``/proc/<pid>/fd`` e o ``uniq`` de cada nó, montados do que a bancada
tem de pé), 174 casos — 2, 3 e 4 controles; USB, BT e mista; o posto com o
P1, o P2 e o P3; o posto do boot e o que renasceu com o P1; a volta tardia; a
vaga do posto; um jogo de um jogador e um que lê todos:

- a forja errava **138**;
- em **15** fazia vibrar a MÃO ERRADA: o P1 que voltou tarde recebia a
  háptica do posto enquanto o P2 ou o P3 o dirigia;
- ``CoopManager.mesa()`` — o co-op, que liga cada físico ao vpad dele —
  acertava os 174.

**A cura pergunta ao dono da ligação**: ``CoopManager.quem_alimenta_cada_vpad``
(o posto é do primário de agora; cada secundário, do físico dele — o mesmo
alvo que o rumble do jogo já segue) e ``quem_o_jogo_le.dono_do_vpad_pelo_coop``.

**Quem vibra** é medido também pela FIAÇÃO: ``_casar_as_pontes`` com o jogo
tocando no endpoint de TODO controle no rádio (o pior caso de 20/09) — só a
ponte de quem dirige um boneco que o jogo lê entra em modo háptica.

**Nada muda** no Modo Nativo (o jogo abre o físico, que casa pelo ``uniq``
dele) nem com a máscara Xbox (o vpad é ``uinput`` e não carrega ``uniq``).

AS MORDIDAS (25/09/2026, cada uma devolvida com o md5 conferido):

- **a forja de hoje** de volta no ``_quem_o_jogo_le`` (a mordida da sprint):
  79 reprovam — 69 da matriz, as 9 da prova (o gate diz o P1) e a do diário;
- o posto dado a quem ele NASCEU (``posto.identity``) e não ao primário: 83;
- sem o ``cedido_ao_primario``: 1; andando na lista viva dos jogadores: 1;
- o tradutor sem a grafia da mesa (``aabbcc…`` contra ``aa:bb:cc:…``): 97;
- o tradutor que CHUTA o primeiro da mesa quando ninguém alimenta: 10 (as 9
  da vaga, e a do vpad sem dono);
- a pergunta que falha engolida em vez de subir: 1; o ``self._daemon`` sem
  ``getattr`` (o dublê por ``__new__``): 1;
- o tradutor consultado ANTES do casamento pelo físico: as 3 do Nativo.

A do Xbox fixa a invariância e não tem mordida própria: o nó do ``uinput``
não tem ``uniq``, e nada chega ao tradutor.

Nenhum endereço real: faixa forjada ``aa:bb:cc`` com os octetos 4 e 5
zerados; os ``02:fe:`` são os que o produto forja.
"""
from __future__ import annotations

import functools
import os
import pathlib
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.daemon.subsystems.alto_falante import (
    AltoFalanteSubsystem,
    ControleNaLista,
)
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer
from hefesto_dualsense4unix.integrations import quem_o_jogo_le as qjl
from hefesto_dualsense4unix.integrations.quem_o_jogo_le import dono_do_vpad_pelo_coop
from hefesto_dualsense4unix.integrations.uhid_gamepad import player_mac, vpad_mac
from tests.unit.test_dois_vpads_nunca_tem_o_mesmo_mac import (
    KernelDoHidPlaystation,
    kernel_de_mentira,
)
from tests.unit.test_haptica_por_radio_01_a_ponte_troca_de_modo import (
    _EndpointDeMentira,
    _PonteDeMentira,
)
from tests.unit.test_o_buraco_de_quem_saiu_se_fecha_no_jogo import (
    MesaHonesta,
    _ticks_ate_o_fim_do_prazo,
    montar_honesto,
    trocar_a_mascara_do_p1,
)
from tests.unit.test_o_jogo_espera_a_carta_do_lugar_guardado import (  # noqa: F401
    P1,
    P2,
    P3,
    TRANSPORTES,
    UNIQS,
    VINTE_SEGUNDOS,
    Relogio,
    config_isolado,
)

#: O pid do jogo no ``/proc`` de mentira.
_PID_DO_JOGO = 4242
#: Onde começam os ``eventN`` dos vpads — longe dos da mesa (``event30``…).
_PRIMEIRO_EVENTO_DE_VPAD = 500
#: Os dois jogos que a régua abre: um de um jogador (lê o jogador 1 do jogo)
#: e um co-op (lê todos). O de um jogador é o que separa a MÃO ERRADA.
JOGOS = ("um-jogador", "todos")


@pytest.fixture
def kernel(monkeypatch: pytest.MonkeyPatch) -> Iterator[KernelDoHidPlaystation]:
    """O kernel de mentira da O-VPAD, com a recusa do ``hid_playstation``."""
    with kernel_de_mentira(monkeypatch) as k:
        yield k


def com_dois_pontos(uniq: str) -> str:
    """``aabbcc000001`` → ``aa:bb:cc:00:00:01``: a grafia do ``HID_UNIQ`` no sysfs."""
    return ":".join(uniq[i : i + 2] for i in range(0, 12, 2))


# ---------------------------------------------------------------------------
# O jogo visto de fora: o /proc e o /sys/class/input que a bancada tem de pé
# ---------------------------------------------------------------------------


def vpads_vivos(bancada: MesaHonesta) -> list[Any]:
    return [v for v in bancada.vpads if getattr(v, "vivo", False)]


def o_que_o_jogo_le(bancada: MesaHonesta, jogo: str) -> list[Any]:
    """Os vpads que o jogo tem abertos: o jogador 1 do jogo, ou todos."""
    lugares = bancada.jogo.ve()[1]
    if jogo == "um-jogador":
        return [lugares[0]] if 0 in lugares else []
    return [v for _lugar, v in sorted(lugares.items())]


def montar_o_mundo(
    bancada: MesaHonesta,
    raiz: pathlib.Path,
    abertos: list[Any],
    *,
    fisicos_abertos: tuple[str, ...] = (),
) -> tuple[pathlib.Path, pathlib.Path]:
    """``/proc`` e ``/sys/class/input`` de mentira, do que está de pé na bancada.

    Cada controle da mesa publica o nó dele com o ``uniq`` na grafia do sysfs;
    cada vpad vivo publica o dele com o MAC que VESTE (o que o kernel
    republica do 0x09) — o ``uinput`` não tem ``uniq``, e o nó sai vazio, como
    no kernel. O jogo é um processo com a variável do Proton e um descritor
    para cada nó que ele lê.
    """
    entrada = raiz / "input"
    proc = raiz / "proc"
    dev = raiz / "dev" / "input"
    dev.mkdir(parents=True)
    no_de: dict[int, str] = {}
    for uniq, node in bancada.mesa.nodes.items():
        evento = node.rsplit("/", 1)[1]
        (entrada / evento / "device").mkdir(parents=True)
        (entrada / evento / "device" / "uniq").write_text(com_dois_pontos(uniq) + "\n")
    for i, vpad in enumerate(vpads_vivos(bancada)):
        evento = f"event{_PRIMEIRO_EVENTO_DE_VPAD + i}"
        no_de[id(vpad)] = evento
        uniq = vpad.mac if getattr(vpad, "backend", None) == "uhid" else ""
        (entrada / evento / "device").mkdir(parents=True)
        (entrada / evento / "device" / "uniq").write_text(uniq + "\n")
    descritores = [no_de[id(v)] for v in abertos]
    descritores += [bancada.mesa.nodes[u].rsplit("/", 1)[1] for u in fisicos_abertos]
    (proc / str(_PID_DO_JOGO) / "fd").mkdir(parents=True)
    (proc / str(_PID_DO_JOGO) / "environ").write_bytes(
        f"{qjl.ENV_DO_JOGO}=/prefixo\0HOME=/x\0".encode()
    )
    for fd, evento in enumerate(descritores, start=3):
        (dev / evento).touch(exist_ok=True)
        os.symlink(dev / evento, proc / str(_PID_DO_JOGO) / "fd" / str(fd))
    return proc, entrada


def quem_dirige(bancada: MesaHonesta, vpad: Any) -> str | None:
    """Quem ALIMENTA ``vpad`` agora, medido no MUNDO e não na anotação do co-op.

    O posto: o carimbo que o leitor do P1 põe no estado (as duas metades,
    ``read_state`` e ``evdev_buttons_once``). Um secundário: o dono do nó que
    o leitor dele segura com o grab — o plástico de verdade, na mesa.
    """
    if vpad is bancada.daemon._gamepad_device:
        return bancada.dono_do_vpad_do_p1()
    dono_do_no = {node: uniq for uniq, node in bancada.mesa.nodes.items()}
    for jogador in bancada.coop._players.values():
        if jogador.vpad is not vpad or jogador.cedido_ao_primario:
            continue
        leitor = jogador.reader
        if bancada.mesa.dono_do_grab.get(leitor.node) != leitor._quem:
            return None
        return dono_do_no.get(leitor.node)
    return None


def a_verdade(bancada: MesaHonesta, abertos: list[Any]) -> set[str]:
    """Os físicos que dirigem os vpads que o jogo lê, na grafia do sysfs."""
    return {com_dois_pontos(u) for u in (quem_dirige(bancada, v) for v in abertos) if u}


def os_controles(bancada: MesaHonesta) -> list[ControleNaLista]:
    """A lista que o ``controles_na_lista`` devolveria: um por DualSense na mesa."""
    return [
        ControleNaLista(
            uniq=com_dois_pontos(uniq),
            caminho=f"/dev/hidraw{i}",
            transporte="rádio" if bancada.mesa.transporte_de(uniq) == "bt" else "cabo",
        )
        for i, uniq in enumerate(bancada.mesa.nodes)
    ]


def o_subsystem_responde(
    bancada: MesaHonesta,
    monkeypatch: pytest.MonkeyPatch,
    proc: pathlib.Path,
    entrada: pathlib.Path,
    *,
    daemon: Any = None,
) -> set[str]:
    """``AltoFalanteSubsystem._quem_o_jogo_le`` do produto, lendo o mundo de mentira."""
    monkeypatch.setattr(
        qjl,
        "quem_o_jogo_le",
        functools.partial(qjl.quem_o_jogo_le, raiz_proc=proc, raiz_input=entrada),
    )
    sub = AltoFalanteSubsystem(daemon=bancada.daemon if daemon is None else daemon)
    return sub._quem_o_jogo_le(os_controles(bancada))


# ---------------------------------------------------------------------------
# Os cenários: quem o posto carrega, de onde ele nasceu, e quem voltou
# ---------------------------------------------------------------------------


def levar_o_posto(bancada: MesaHonesta, quem: int, *, nasceu: str, volta: bool) -> None:
    """O posto passa a ser dirigido por ``UNIQS[quem]``.

    ``nasceu="p1"`` é a troca de máscara com o jogo aberto (o gesto dela, que a
    R-04 nunca barra): o posto renasce com a identidade do P1. Os que vêm antes
    de ``quem`` saem e o prazo de cada um vence (a NUM-01 passa o posto
    adiante); com ``volta``, eles voltam depois do prazo, cada um no vpad
    próprio — o P1 com o MAC seguinte do aparelho quando o posto já veste o
    dele.
    """
    if nasceu == "p1":
        trocar_a_mascara_do_p1(bancada)
    saidos = list(UNIQS[:quem])
    vias = {u: bancada.mesa.transporte_de(u) for u in saidos}
    for uniq in saidos:
        bancada.mesa.levantar(uniq)
        for _ in range(_ticks_ate_o_fim_do_prazo(0.0)):
            bancada.tique()
    if volta:
        for uniq in saidos:
            bancada.mesa.sentar(uniq, transporte=vias[uniq])
            bancada.tique()
            bancada.tique()
    assert bancada.dono_do_vpad_do_p1() == UNIQS[quem], "a bancada não levou o posto"


CENARIOS = [
    pytest.param(
        n,
        t,
        quem,
        nasceu,
        volta,
        id=f"{n}-controles-{t}-posto-com-p{quem + 1}-nasceu-{nasceu}"
        + ("-volta-tardia" if volta else ""),
    )
    for n in (2, 3, 4)
    for t in TRANSPORTES
    for quem in range(min(n, 3))
    for nasceu in ("boot", "p1")
    for volta in ((False, True) if quem else (False,))
]


@pytest.mark.usefixtures("config_isolado")
class TestOJogoLeQuemDirigeOPosto:
    """A matriz: o conjunto que o gate devolve é o de quem dirige o que o jogo lê."""

    @pytest.mark.parametrize(("quantos", "transporte", "quem", "nasceu", "volta"), CENARIOS)
    def test_o_gate_segue_quem_alimenta_o_vpad(
        self,
        monkeypatch: pytest.MonkeyPatch,
        kernel: KernelDoHidPlaystation,
        tmp_path: pathlib.Path,
        quantos: int,
        transporte: str,
        quem: int,
        nasceu: str,
        volta: bool,
    ) -> None:
        bancada = montar_honesto(monkeypatch, kernel, quantos, transporte)
        levar_o_posto(bancada, quem, nasceu=nasceu, volta=volta)
        for jogo in JOGOS:
            abertos = o_que_o_jogo_le(bancada, jogo)
            proc, entrada = montar_o_mundo(bancada, tmp_path / jogo, abertos)
            verdade = a_verdade(bancada, abertos)
            assert verdade, f"{jogo}: a bancada não tem ninguém dirigindo o que o jogo lê"
            resposta = o_subsystem_responde(bancada, monkeypatch, proc, entrada)
            assert resposta == verdade, (
                f"{jogo}: o gate diz {sorted(resposta)} e quem dirige é {sorted(verdade)} "
                f"(o posto veste {bancada.daemon._gamepad_device.mac})"
            )

    @pytest.mark.parametrize(
        ("quantos", "transporte"),
        [(n, t) for n in (2, 3, 4) for t in TRANSPORTES],
        ids=[f"{n}-controles-{t}" for n in (2, 3, 4) for t in TRANSPORTES],
    )
    def test_com_o_posto_vago_ninguem_vibra_por_ele(
        self,
        monkeypatch: pytest.MonkeyPatch,
        kernel: KernelDoHidPlaystation,
        tmp_path: pathlib.Path,
        quantos: int,
        transporte: str,
    ) -> None:
        """O P1 fora dentro do prazo: o posto espera por ele, parado — ninguém o dirige.

        O jogo de um jogador lê só o posto, e ninguém vibra; o que lê todos
        acende quem ficou, cada um no próprio vpad (O-ASSENTO-GUARDADO-NAO-ANDA-02).
        """
        bancada = montar_honesto(monkeypatch, kernel, quantos, transporte)
        bancada.mesa.levantar(P1)
        for _ in range(int(VINTE_SEGUNDOS / 2.0)):
            bancada.tique()
        assert bancada.dono_do_vpad_do_p1() is None, "o posto não ficou vago"
        for jogo, esperado in (
            ("um-jogador", set()),
            ("todos", {com_dois_pontos(u) for u in UNIQS[1:quantos]}),
        ):
            abertos = o_que_o_jogo_le(bancada, jogo)
            proc, entrada = montar_o_mundo(bancada, tmp_path / jogo, abertos)
            assert a_verdade(bancada, abertos) == esperado
            assert o_subsystem_responde(bancada, monkeypatch, proc, entrada) == esperado


# ---------------------------------------------------------------------------
# A prova da sprint: o P2 dirige o posto nascido do P1, e o P1 voltou tarde
# ---------------------------------------------------------------------------


def _as_pontes_de_mentira(monkeypatch: pytest.MonkeyPatch) -> dict[str, bool]:
    """A fiação do ``_casar_as_pontes`` com dublês — e o jogo tocando em TODO endpoint.

    Os dublês são os da régua da troca de modo (HAPTICA-POR-RADIO-01): nenhuma
    ponte escreve no aparelho, nenhum endpoint vai ao servidor de som. O gate
    (``_quem_o_jogo_le``) NÃO é dublado: é ele que esta régua mede.
    """
    from hefesto_dualsense4unix.integrations import alto_falante_bt as af
    from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
    from hefesto_dualsense4unix.integrations import hidraw_broker_client as broker

    _PonteDeMentira.criadas = []
    _EndpointDeMentira.criados = []
    _EndpointDeMentira.quedas = []
    tocando: dict[str, bool] = {}

    def _tocando(nome: str, *_a: Any, **_k: Any) -> bool:
        # O pior caso de 20/09: o jogo tem o canal de TODO endpoint de háptica
        # aberto. O alto-falante (o nó do som) está calado.
        return nome.startswith("endpoint::") or tocando.get(nome, False)

    monkeypatch.setattr(
        af, "fonte_do_monitor_do_no", lambda nome, **kw: ((lambda _n: b""), f"g:{nome}", "")
    )
    monkeypatch.setattr(af, "PonteDeSomPorRadio", _PonteDeMentira)
    monkeypatch.setattr(af, "sink_esta_tocando", _tocando)
    monkeypatch.setattr(eh, "EndpointDeHaptica", _EndpointDeMentira)
    monkeypatch.setattr(
        eh,
        "ancoras",
        lambda *a, **k: [eh.Ancora(syspath=f"/d/{i}", declarado=f"/d/{i}/i:1.0") for i in range(4)],
    )
    monkeypatch.setattr(broker, "abrir_hidraw", lambda no, **_: type("N", (), {"fd": 7})())
    return tocando


def quem_vibra(
    bancada: MesaHonesta,
    monkeypatch: pytest.MonkeyPatch,
    proc: pathlib.Path,
    entrada: pathlib.Path,
) -> set[str]:
    """Os controles no rádio cuja ponte subiu em modo HÁPTICA nesta volta."""
    _as_pontes_de_mentira(monkeypatch)
    monkeypatch.setattr(
        qjl,
        "quem_o_jogo_le",
        functools.partial(qjl.quem_o_jogo_le, raiz_proc=proc, raiz_input=entrada),
    )
    sub = AltoFalanteSubsystem(daemon=bancada.daemon)
    sub._casar_as_pontes(os_controles(bancada))
    return {uniq for uniq, modo in sub._modo_da_ponte.items() if modo == "haptica"}


@pytest.mark.usefixtures("config_isolado")
class TestAProvaDaSprint:
    """O P2 dirige o posto nascido do P1: a háptica sai no P2, e nunca no P1 que voltou."""

    @pytest.mark.parametrize(
        ("quantos", "transporte"),
        [(n, t) for n in (2, 3, 4) for t in TRANSPORTES],
        ids=[f"{n}-controles-{t}" for n in (2, 3, 4) for t in TRANSPORTES],
    )
    def test_a_haptica_sai_no_p2_que_dirige_o_posto(
        self,
        monkeypatch: pytest.MonkeyPatch,
        kernel: KernelDoHidPlaystation,
        tmp_path: pathlib.Path,
        quantos: int,
        transporte: str,
    ) -> None:
        """A régua da sprint. A mordida é a forja: ela devolvia o P1.

        O posto renasceu com o P1 (a troca de máscara); o P1 saiu, o prazo
        venceu, o P2 assumiu o posto, e o P1 voltou tarde num vpad próprio. O
        jogo de um jogador lê o posto, e tem o canal de háptica de todo
        controle no rádio aberto. Vibra o P2 — se está no rádio; no cabo a
        háptica é a placa de som dele, e nenhuma ponte sobe.
        """
        bancada = montar_honesto(monkeypatch, kernel, quantos, transporte)
        levar_o_posto(bancada, 1, nasceu="p1", volta=True)
        assert bancada.daemon._gamepad_device.mac == vpad_mac(P1, 1)
        assert bancada.vpad_de(P1).mac != vpad_mac(P1, 1), "o P1 voltou vestindo o do posto"

        abertos = o_que_o_jogo_le(bancada, "um-jogador")
        assert abertos == [bancada.daemon._gamepad_device]
        proc, entrada = montar_o_mundo(bancada, tmp_path, abertos)
        assert o_subsystem_responde(bancada, monkeypatch, proc, entrada) == {
            com_dois_pontos(P2)
        }

        no_radio = {
            com_dois_pontos(u) for u in bancada.mesa.nodes if bancada.mesa.transporte_de(u) == "bt"
        }
        vibram = quem_vibra(bancada, monkeypatch, proc, entrada)
        assert vibram == {com_dois_pontos(P2)} & no_radio, (
            f"vibram {sorted(vibram)}; no rádio: {sorted(no_radio)}"
        )
        assert com_dois_pontos(P1) not in vibram, "a mão do P1 vibrou pelo posto que o P2 dirige"


# ---------------------------------------------------------------------------
# As máscaras: DualSense (acima), Nativo e Xbox — nestas duas, nada muda
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("config_isolado")
class TestAsOutrasMascaras:
    """No Nativo o jogo abre o físico; no Xbox o vpad não tem ``uniq``. Nada muda."""

    @pytest.mark.parametrize("transporte", list(TRANSPORTES))
    def test_no_nativo_o_jogo_le_o_fisico_e_o_coop_nao_decide_nada(
        self,
        monkeypatch: pytest.MonkeyPatch,
        kernel: KernelDoHidPlaystation,
        tmp_path: pathlib.Path,
        transporte: str,
    ) -> None:
        """O jogo abre o P2 e o P3 direto: é isso que vibra, com co-op ou sem.

        E um co-op que respondesse outra coisa para cada vpad não mudaria nada:
        o físico casa pelo ``uniq`` dele, e o tradutor só é consultado para o
        que não é físico.
        """
        bancada = montar_honesto(monkeypatch, kernel, 4, transporte)
        proc, entrada = montar_o_mundo(bancada, tmp_path, [], fisicos_abertos=(P2, P3))
        esperado = {com_dois_pontos(P2), com_dois_pontos(P3)}
        assert o_subsystem_responde(bancada, monkeypatch, proc, entrada) == esperado
        sem_coop = SimpleNamespace(_coop_manager=None)
        assert (
            o_subsystem_responde(bancada, monkeypatch, proc, entrada, daemon=sem_coop) == esperado
        )
        # O co-op hostil diz que TUDO — os vpads e os próprios físicos — é do P1.
        tudo_do_p1 = {v.mac: P1 for v in vpads_vivos(bancada)}
        tudo_do_p1.update({com_dois_pontos(u): P1 for u in bancada.mesa.nodes})
        hostil = SimpleNamespace(
            _coop_manager=SimpleNamespace(quem_alimenta_cada_vpad=lambda: tudo_do_p1)
        )
        assert o_subsystem_responde(bancada, monkeypatch, proc, entrada, daemon=hostil) == esperado

    @pytest.mark.parametrize("transporte", list(TRANSPORTES))
    def test_com_a_mascara_xbox_o_vpad_nao_tem_uniq_e_ninguem_entra_na_haptica(
        self,
        monkeypatch: pytest.MonkeyPatch,
        kernel: KernelDoHidPlaystation,
        tmp_path: pathlib.Path,
        transporte: str,
    ) -> None:
        """Os vpads nascem ``uinput`` pela fábrica real, e o jogo que os lê não entra.

        Um controle de Xbox não tem a háptica do DualSense: a vibração dele é o
        rumble do FF, que já vai ao físico de quem o alimenta. O co-op também
        não os lista — sem MAC não há o que casar.
        """
        relogio = Relogio()
        bancada = MesaHonesta(monkeypatch, kernel=kernel, relogio=relogio, tempo=relogio)
        bancada.daemon.config.gamepad_flavor = "xbox"
        bancada.vpad_do_p1.stop()
        posto = bancada._nascer_vpad("xbox", player=1, identity=None, allow_uhid=True)
        bancada.vpad_do_p1 = bancada.daemon._gamepad_device = posto
        for uniq, via in zip(UNIQS[:3], TRANSPORTES[transporte][:3], strict=True):
            bancada.mesa.sentar(uniq, transporte=via)
        for _ in range(3):
            bancada.tique()
        abertos = o_que_o_jogo_le(bancada, "todos")
        assert len(abertos) == 3
        assert all(getattr(v, "backend", None) == "uinput" for v in abertos)
        assert a_verdade(bancada, abertos) == {com_dois_pontos(u) for u in UNIQS[:3]}
        assert bancada.coop.quem_alimenta_cada_vpad() == {}
        proc, entrada = montar_o_mundo(bancada, tmp_path, abertos)
        assert o_subsystem_responde(bancada, monkeypatch, proc, entrada) == set()


# ---------------------------------------------------------------------------
# O dono da resposta: o acessor do co-op e o tradutor
# ---------------------------------------------------------------------------


class _Vpad:
    def __init__(self, mac: str | None) -> None:
        if mac is not None:
            self.mac = mac


def _coop(
    primario: str | None, posto: Any, jogadores: dict[str, _SecondaryPlayer]
) -> CoopManager:
    daemon = SimpleNamespace(
        controller=SimpleNamespace(primary_uniq=primario, _evdev=None),
        _gamepad_device=posto,
        config=SimpleNamespace(coop_enabled=True),
    )
    coop = CoopManager(daemon)  # type: ignore[arg-type]
    coop._players = jogadores
    return coop


def _jogador(identidade: str, vpad: Any, *, cedido: bool = False) -> _SecondaryPlayer:
    return _SecondaryPlayer(
        identity=identidade,
        evdev_path="/dev/input/event9",
        reader=None,  # type: ignore[arg-type]
        player_index=2,
        vpad=vpad,
        cedido_ao_primario=cedido,
    )


class TestQuemAlimentaCadaVpad:
    """``CoopManager.quem_alimenta_cada_vpad`` — o posto é do primário de AGORA."""

    def test_o_posto_e_do_primario_de_agora_e_nao_de_quem_ele_nasceu(self) -> None:
        posto = _Vpad(vpad_mac(P1, 1))
        coop = _coop(P2, posto, {P3: _jogador(P3, _Vpad(vpad_mac(P3, 3)))})
        assert coop.quem_alimenta_cada_vpad() == {vpad_mac(P1, 1): P2, vpad_mac(P3, 3): P3}

    def test_o_posto_do_boot_tambem_tem_dono(self) -> None:
        """O piso não deriva de ninguém — e o primário o dirige assim mesmo."""
        coop = _coop(P1, _Vpad(player_mac(1)), {})
        assert coop.quem_alimenta_cada_vpad() == {player_mac(1): P1}

    def test_quem_cedeu_ao_primario_e_quem_espera_o_grab_ficam_de_fora(self) -> None:
        jogadores = {
            P2: _jogador(P2, _Vpad(vpad_mac(P2, 2)), cedido=True),
            P3: _jogador(P3, None),
        }
        coop = _coop(P2, _Vpad(vpad_mac(P1, 1)), jogadores)
        assert coop.quem_alimenta_cada_vpad() == {vpad_mac(P1, 1): P2}

    def test_sem_mac_e_sem_identidade_de_aparelho_nao_ha_o_que_casar(self) -> None:
        jogadores = {
            "path:/dev/input/event9": _jogador("path:/dev/input/event9", _Vpad(vpad_mac(P3, 3))),
            P2: _jogador(P2, _Vpad(None)),  # o uinput da máscara Xbox
        }
        coop = _coop(None, _Vpad(player_mac(1)), jogadores)
        assert coop.quem_alimenta_cada_vpad() == {}

    def test_o_mac_sai_em_minusculas(self) -> None:
        coop = _coop(P1, _Vpad(vpad_mac(P1, 1).upper()), {})
        assert coop.quem_alimenta_cada_vpad() == {vpad_mac(P1, 1): P1}

    def test_a_mesa_que_muda_no_meio_da_pergunta_nao_derruba_a_resposta(self) -> None:
        """Quem pergunta roda fora do laço: o laço pode sentar alguém no meio.

        O vpad do P2, ao dizer o MAC, senta o P3 — o que o ``forward_all``
        faria, na outra thread, entre dois passos da pergunta. Andar na lista
        viva levantaria «dictionary changed size during iteration», e a volta
        do alto-falante calaria a háptica da mesa inteira.
        """
        jogadores: dict[str, _SecondaryPlayer] = {}

        class _VpadDoP2:
            @property
            def mac(self) -> str:
                jogadores[P3] = _jogador(P3, _Vpad(vpad_mac(P3, 3)))
                return vpad_mac(P2, 2)

        jogadores[P2] = _jogador(P2, _VpadDoP2())
        coop = _coop(P1, _Vpad(vpad_mac(P1, 1)), jogadores)
        assert coop.quem_alimenta_cada_vpad() == {vpad_mac(P1, 1): P1, vpad_mac(P2, 2): P2}


class TestOTradutor:
    """``dono_do_vpad_pelo_coop`` — a grafia da mesa, e nunca um chute."""

    MESA = tuple(com_dois_pontos(u) for u in (P1, P2, P3))

    def test_devolve_o_fisico_na_grafia_da_mesa(self) -> None:
        coop = SimpleNamespace(quem_alimenta_cada_vpad=lambda: {vpad_mac(P1, 1): P2})
        dono = dono_do_vpad_pelo_coop(coop, self.MESA)
        assert dono(vpad_mac(P1, 1)) == com_dois_pontos(P2)
        assert dono(vpad_mac(P1, 1).upper()) == com_dois_pontos(P2)

    def test_vpad_sem_dono_e_dono_fora_da_mesa_dao_ninguem(self) -> None:
        coop = SimpleNamespace(quem_alimenta_cada_vpad=lambda: {vpad_mac(P1, 1): "aabbcc000009"})
        dono = dono_do_vpad_pelo_coop(coop, self.MESA)
        assert dono(vpad_mac(P1, 1)) is None, "o dono não está na mesa"
        assert dono(player_mac(1)) is None, "ninguém alimenta este vpad"

    @pytest.mark.parametrize("coop", [None, SimpleNamespace()], ids=["sem-co-op", "sem-a-pergunta"])
    def test_sem_quem_responda_ninguem_vibra_pelo_vpad(self, coop: Any) -> None:
        dono = dono_do_vpad_pelo_coop(coop, self.MESA)
        assert dono(vpad_mac(P1, 1)) is None

    def test_a_pergunta_que_falha_cala_a_mesa_e_diz_por_que(self) -> None:
        """Na dúvida, ninguém vibra — e o diário diz a razão."""

        def _falha() -> dict[str, str]:
            raise RuntimeError("a mesa mudou no meio")

        daemon = SimpleNamespace(_coop_manager=SimpleNamespace(quem_alimenta_cada_vpad=_falha))
        sub = AltoFalanteSubsystem(daemon=daemon)
        controles = [
            ControleNaLista(uniq=u, caminho="/dev/hidraw1", transporte="rádio") for u in self.MESA
        ]
        with structlog.testing.capture_logs() as registros:
            assert sub._quem_o_jogo_le(controles) == set()
        assert [r["event"] for r in registros] == ["haptica_nao_sei_quem_joga"]
        assert registros[0]["motivo"] == "a mesa mudou no meio"

    def test_o_duble_sem_daemon_segue_sem_levantar(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        """O dublê montado por ``__new__`` não tem daemon: sem co-op, e sem exceção."""
        monkeypatch.setattr(
            qjl,
            "quem_o_jogo_le",
            functools.partial(qjl.quem_o_jogo_le, raiz_proc=tmp_path, raiz_input=tmp_path),
        )
        sub = object.__new__(AltoFalanteSubsystem)
        controle = ControleNaLista(uniq=self.MESA[0], caminho="/dev/hidraw1", transporte="rádio")
        with structlog.testing.capture_logs() as registros:
            assert sub._quem_o_jogo_le([controle]) == set()
        assert registros == []
