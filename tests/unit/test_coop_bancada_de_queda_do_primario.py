"""COOP-QUE-NÃO-DESMONTA-01 / E4 — a bancada de queda programável.

**A noite dela, encenada.** Dois DualSense no rádio; o Jogador 2 entra e sai em
dois segundos, quatro vezes em 22 minutos. O journal de 02/08/2026 mostrou o
instante da morte, e o `EBUSY` não veio da Steam nem do jogo — veio de DENTRO
do daemon::

    21:10:41.867  coop_player_grab_pending  path=/dev/input/event30  player=2
    21:10:42.135  coop_player_added         identity=…ab            player=2
    21:10:43.700  controller_primary_bound  transport=usb
    21:10:43.754  evdev_started             path=/dev/input/event30
    21:10:43.754  evdev_grab_failed         [Errno 16] EBUSY
    21:10:44.116  coop_player_removed       players=1

O co-op pegou o `event30` como Jogador 2, e 1,9 s depois o leitor do primário
foi apontado para o MESMO node.

**Por que uma BANCADA e não mais um teste.** Cada subsistema desta casa já
tinha teste, e todos passavam durante a noite ruim dela: o defeito não mora
dentro de nenhum deles, mora na ORDEM em que eles se cruzam. Não existia lugar
onde o `connect()` do `reconnect_loop`, o `sync()` do poll loop e o
`CoopManager` corressem contra o mesmo relógio — e sem esse lugar o defeito
volta e ninguém nota. É a entrega mais valiosa da sprint por isso.

O que a bancada monta, e o que ela NÃO promete
==============================================

MONTA (é código de produto de verdade rodando):

- ``PyDualSenseController`` REAL, com o ``connect()`` real: enumeração,
  ``_close_handles``, ``_recompute_primary``, a eleição do primário e o aviso
  de troca;
- ``CoopManager`` REAL, com ``sync()``/``forward_all()`` reais: o ``want``, o
  teardown, o spawn, a promoção e a numeração de jogador;
- **um enumerador só** alimentando os DOIS lados — ``_enumerate_device_keys``
  (o que o backend vê) e ``discover_dualsense_evdevs`` (o que o co-op vê) saem
  da MESMA :class:`_Mesa`. Duas listas independentes fariam a bancada medir
  uma mesa que não existe, e a armadilha nº 1 desta casa é justamente medir
  contra a régua errada;
- **node renumerado a cada volta**, que é o que o replug por Bluetooth faz de
  verdade (o ``event30`` do journal não é o mesmo node de antes da queda);
- **o grab é EXCLUSIVO de verdade**: :meth:`_Mesa.grab` recusa com `EBUSY`
  quando outro leitor já segura o node, exatamente como o kernel. É daí que
  sai a asserção 1 — e é o que faz o dublê saber RECUSAR, em vez de ser uma
  régua que só sabe passar.

NÃO promete (declarado, para ninguém ler mais do que está escrito):

- **não modela a latência do self-pipe.** No produto o ``retarget`` só SINALIZA
  a thread do leitor, que fecha o fd antigo microssegundos depois; aqui o node
  antigo é solto no mesmo instante do ``retarget``. O que a bancada modela é a
  ORDEM — e a ORDEM é o defeito;
- **não é hardware.** Não há DualSense nesta bancada nem no repositório; toda
  afirmação sobre o aparelho é inferência declarada e mora na sprint;
- **não mede tempo de parede.** O relógio é virtual (:class:`_Relogio`), e é
  ele que envelhece a reserva do posto de primário sem ninguém dormir.

O roteiro (o mínimo que reproduz a noite dela)
==============================================

``t=0: A,B`` → ``t=5: B`` (o primário A cai) → ``t=8: B,A`` (A volta com node
novo). Rodado nas DUAS ordens de propósito — ``connect()`` antes do ``sync()``
e ``sync()`` antes do ``connect()`` —, porque os dois laços são independentes e
qual chega primeiro é sorteio na máquina dela.

As asserções que MORDEM
=======================

1. nenhum `EBUSY` no roteiro inteiro;
2. o Jogador 2 do fim é o MESMO controle do começo;
3. quem nunca saiu da mesa não muda de `player_index`;
4. nenhum instante tem dois vpads com o mesmo MAC.

Arranque a cura e cada uma reprova — as duas curas, e cada uma com a sua régua:

- tirar o AVISO (``set_primary_change_observer``, E1) derruba a 1;
- tirar a RESERVA do posto (``PRIMARIO_RESERVA_SEC``, E2a) derruba a 2.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.integrations.uhid_gamepad import player_mac

#: Os dois controles da mesa. Faixa FORJADA (aa:bb:cc) e octetos 4-5 zerados —
#: a máscara desta casa. Nenhum endereço real entra em arquivo versionado.
KEY_A = "AA:BB:CC:00:00:0A"
KEY_B = "AA:BB:CC:00:00:0B"
UNIQ_A = "aabbcc00000a"
UNIQ_B = "aabbcc00000b"


class _Relogio:
    """Relógio virtual. Nada nesta bancada dorme."""

    def __init__(self) -> None:
        self.t = 100.0

    def agora(self) -> float:
        return self.t

    def avancar(self, segundos: float) -> None:
        self.t += segundos


class _Mesa:
    """O mundo: quem está na mesa, em que node, e quem segura o grab de cada um.

    Fonte ÚNICA dos dois enumeradores do produto. O grab é exclusivo de
    verdade: um segundo pretendente leva `EBUSY`, como no kernel.
    """

    def __init__(self) -> None:
        self.nodes: dict[str, str] = {}
        self.dono_do_grab: dict[str, str] = {}
        #: Todo `EBUSY` recusado, com quem pediu e quem já tinha. A asserção 1
        #: lê daqui — e a lista guarda o TEXTO da colisão, para o teste que
        #: reprova dizer O QUE está errado, não só que algo está.
        self.ebusy: list[str] = []
        self._proximo = 30

    # -- o mundo muda ---------------------------------------------------

    def sentar(self, uniq: str) -> str:
        """Um controle entra. O node é SEMPRE novo — é o que o replug BT faz."""
        node = f"/dev/input/event{self._proximo}"
        self._proximo += 1
        self.nodes[uniq] = node
        return node

    def levantar(self, uniq: str) -> None:
        """Um controle sai: o node some, e o grab de quem o segurava some junto."""
        node = self.nodes.pop(uniq, None)
        if node is not None:
            self.dono_do_grab.pop(node, None)

    # -- o kernel responde ----------------------------------------------

    def grab(self, node: str, quem: str) -> bool:
        dono = self.dono_do_grab.get(node)
        if dono is not None and dono != quem:
            self.ebusy.append(
                f"EBUSY em {node}: '{quem}' pediu o grab, '{dono}' já segurava"
            )
            return False
        self.dono_do_grab[node] = quem
        return True

    def ungrab(self, node: str | None, quem: str) -> None:
        if node is not None and self.dono_do_grab.get(node) == quem:
            del self.dono_do_grab[node]

    # -- as duas réguas do produto, saindo da MESMA fonte ----------------

    def como_o_backend_ve(self) -> list[tuple[str, bytes, bool]]:
        """O que `_enumerate_device_keys` devolveria: `(key, path_hidraw, edge)`."""
        return [
            (key, f"/dev/hidraw{i}".encode(), False)
            for i, key in enumerate(self._keys_presentes())
        ]

    def como_o_coop_ve(self) -> dict[str, Path]:
        """O que `discover_dualsense_evdevs` devolveria: `{uniq: node}`."""
        return {uniq: Path(node) for uniq, node in self.nodes.items()}

    def _keys_presentes(self) -> list[str]:
        por_uniq = {UNIQ_A: KEY_A, UNIQ_B: KEY_B}
        return [por_uniq[u] for u in self.nodes]


class _LeitorDoPrimario:
    """O `EvdevReader` do P1, injetado no backend real.

    Modela as três coisas que o `_recompute_primary` faz com ele: mirar outro
    MAC (`retarget`), reabrir (`refresh_device`) e subir (`start`) — e o `start`
    é onde ele pede o grab, que é onde o `EBUSY` do journal aconteceu.
    """

    NOME = "leitor-do-P1"

    def __init__(self, mesa: _Mesa, *, solta_na_hora: bool = True) -> None:
        self._mesa = mesa
        self._alvo: str | None = None
        self.node: str | None = None
        #: `False` liga o modo HONESTO-E-LENTO: o node antigo só é solto quando
        #: `a_thread_do_leitor_acorda()` for chamada. É assim que o produto se
        #: comporta — `retarget` só SINALIZA (`request_reopen`), e quem fecha o
        #: fd é a thread dona. O default `True` é a simplificação declarada no
        #: cabeçalho; este knob existe para o teste que mede o que ela esconde.
        self.solta_na_hora = solta_na_hora
        self._a_soltar: str | None = None

    def retarget(self, uniq: str | None) -> None:
        # O fd antigo fecha ao reabrir, e fechar solta o grab.
        if uniq != self._alvo:
            if self.solta_na_hora:
                self._mesa.ungrab(self.node, self.NOME)
            else:
                self._a_soltar = self.node
            self.node = None
        self._alvo = uniq

    def a_thread_do_leitor_acorda(self) -> None:
        """O self-pipe acordou a thread dona: ela fecha o fd antigo, enfim."""
        if self._a_soltar is not None:
            self._mesa.ungrab(self._a_soltar, self.NOME)
            self._a_soltar = None

    def refresh_device(self) -> None:
        self.node = self._mesa.nodes.get(self._alvo) if self._alvo else None

    def is_available(self) -> bool:
        return self.node is not None

    def start(self) -> bool:
        if self.node is None:
            return False
        return self._mesa.grab(self.node, self.NOME)

    def stop(self) -> None:
        self._mesa.ungrab(self.node, self.NOME)
        self.node = None

    def is_stale(self) -> bool:
        return False

    def request_reopen(self, reason: str = "") -> None:
        self.refresh_device()

    def snapshot(self) -> Any:  # pragma: no cover — a bancada não lê input do P1
        raise AssertionError("a bancada não usa o input do primário")


class _LeitorDeSecundario:
    """O `EvdevReader` de um jogador de co-op. Uma instância por spawn.

    `mesa` é atributo de CLASSE porque quem constrói é o produto
    (`_spawn_player` faz `EvdevReader(device_path=..., target_uniq=...)`) e não
    o teste — o mesmo truque dos knobs de `_FakeReader` em
    `test_subsystem_coop.py`.
    """

    mesa: _Mesa | None = None

    def __init__(self, device_path: Any = None, target_uniq: str | None = None) -> None:
        self.node = str(device_path)
        self.target_uniq = target_uniq
        self.grab_state = "off"
        self.stopped = False
        self.snap = SimpleNamespace(
            lx=128, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0,
            buttons_pressed=frozenset(),
        )

    @property
    def _quem(self) -> str:
        return f"coop:{self.target_uniq}"

    def start(self) -> bool:
        return True

    def set_grab(self, grab: bool) -> bool:
        assert type(self).mesa is not None
        mesa = type(self).mesa
        assert mesa is not None
        if not grab:
            mesa.ungrab(self.node, self._quem)
            self.grab_state = "off"
            return True
        if not mesa.grab(self.node, self._quem):
            self.grab_state = "failed"
            return False
        self.grab_state = "held"
        return True

    def stop(self) -> None:
        assert type(self).mesa is not None
        mesa = type(self).mesa
        assert mesa is not None
        mesa.ungrab(self.node, self._quem)
        self.stopped = True

    def snapshot(self) -> Any:
        return self.snap


class _VpadFalso:
    """O gamepad virtual de um jogador. O MAC vem da função REAL do produto."""

    def __init__(self, player: int) -> None:
        self.player = player
        self.mac = player_mac(player)
        self.flavor = "dualsense"
        self.backend = "uinput"
        self.vivo = True

    def stop(self) -> None:
        self.vivo = False

    def forward_analog(self, **_kw: int) -> None:
        pass

    def forward_buttons(self, _pressed: frozenset[str]) -> None:
        pass

    def pump_ff(self) -> None:
        pass


class _FakeHandle:
    """Handle pydualsense de um controle no RÁDIO (é o transporte do defeito)."""

    def __init__(self) -> None:
        self.connected = True
        self.closed = False
        self.conType = type("CT", (), {"name": "BT"})()

    def close(self) -> None:
        self.closed = True


class Bancada:
    """Backend real + co-op real + uma mesa só, contra um relógio virtual."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.mesa = _Mesa()
        self.relogio = _Relogio()
        self.leitor_p1 = _LeitorDoPrimario(self.mesa)
        self.inst = PyDualSenseController(evdev_reader=self.leitor_p1)  # type: ignore[arg-type]
        self.inst._relogio = self.relogio.agora
        # A leitura do 0x05 é hidraw de verdade e não tem nada a ver com este
        # defeito: neutralizada em voz alta (o vpad nasce com o canônico, que é
        # o fail-safe que o próprio produto já prevê).
        self.inst.read_calibration = lambda _uniq=None: None  # type: ignore[assignment]
        self.daemon = SimpleNamespace(
            config=SimpleNamespace(coop_enabled=True, gamepad_flavor="dualsense"),
            _gamepad_device=object(),
            controller=self.inst,
            _coop_manager=None,
            identity_registry=None,
        )
        self.coop = CoopManager(self.daemon)  # type: ignore[arg-type]
        self.daemon._coop_manager = self.coop
        #: Todo vpad que já nasceu, para a asserção 4 (colisão de MAC).
        self.vpads: list[_VpadFalso] = []
        self._instalar_dubles(monkeypatch)
        #: `(instante, uniq_do_jogador_2)` a cada olhada — a linha do tempo que
        #: as asserções 2 e 3 leem.
        self.historico: list[tuple[float, str | None, int | None]] = []

    # -- fiação ---------------------------------------------------------

    def _instalar_dubles(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _LeitorDeSecundario.mesa = self.mesa
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.evdev_reader.EvdevReader", _LeitorDeSecundario
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.evdev_reader.discover_dualsense_evdevs",
            self.mesa.como_o_coop_ve,
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.evdev_reader.InputDirWatch.poll",
            lambda _self: True,
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad",
            self._nascer_vpad,
        )
        # Hermético: NUNCA o /sys/class/leds real (há DualSense de verdade na
        # máquina da mantenedora).
        monkeypatch.setattr("hefesto_dualsense4unix.core.sysfs_leds.discover", lambda: {})

    def _nascer_vpad(self, _flavor: Any, *, player: int = 1, **_kw: Any) -> _VpadFalso:
        vpad = _VpadFalso(player)
        self.vpads.append(vpad)
        return vpad

    # -- o mundo muda ---------------------------------------------------

    def sentar(self, uniq: str) -> None:
        self.mesa.sentar(uniq)

    def levantar(self, uniq: str) -> None:
        self.mesa.levantar(uniq)

    # -- os dois laços do daemon ----------------------------------------

    def tique_do_reconnect_loop(self) -> None:
        """Um `connect()` — o `backend_hotplug_reconcile` do `reconnect_loop`."""
        fila = [_FakeHandle() for _ in self.mesa.nodes]
        with patch.object(
            PyDualSenseController,
            "_enumerate_device_keys",
            return_value=self.mesa.como_o_backend_ve(),
        ), patch.object(
            PyDualSenseController,
            "_open_one",
            side_effect=lambda _path, *, is_edge: fila.pop(0),
        ):
            self.inst.connect()

    def tique_do_poll_loop(self, *, sync: bool = True) -> None:
        """Um tique do poll loop: `sync` a cada ~2 s, `forward_all` sempre."""
        if sync:
            self.coop.sync()
        self.coop.forward_all()

    def passo(self, segundos: float, *, sync_antes_do_connect: bool) -> None:
        """Avança o relógio e roda os dois laços na ordem pedida."""
        self.relogio.avancar(segundos)
        if sync_antes_do_connect:
            self.tique_do_poll_loop()
            self.tique_do_reconnect_loop()
        else:
            self.tique_do_reconnect_loop()
            self.tique_do_poll_loop()
        # O poll loop gira a ~100 Hz: o tique seguinte, sem sync, é o que
        # recolhe quem cedeu o controle ao primário.
        self.tique_do_poll_loop(sync=False)
        self.anotar()
        self.conferir_invariantes()

    # -- leitura ---------------------------------------------------------

    def jogador_2(self) -> str | None:
        """O MAC do controle que ALIMENTA o vpad do Jogador 2 agora."""
        for mac, numero in self.coop.player_indexes().items():
            if numero == 2:
                return mac
        return None

    def indice_de(self, uniq: str) -> int | None:
        jogador = self.coop._players.get(uniq)
        return jogador.player_index if jogador is not None else None

    def anotar(self) -> None:
        self.historico.append(
            (self.relogio.agora(), self.jogador_2(), self.indice_de(UNIQ_B))
        )

    def conferir_invariantes(self) -> None:
        """Asserções 1 e 4 — as que valem em TODO instante, não só no fim."""
        assert not self.mesa.ebusy, (
            "asserção 1: dois donos do mesmo node evdev dentro do daemon — "
            + "; ".join(self.mesa.ebusy)
        )
        vivos = [v for v in self.vpads if v.vivo]
        macs = [v.mac for v in vivos]
        assert len(macs) == len(set(macs)), (
            "asserção 4: dois vpads VIVOS com o mesmo MAC — o probe do "
            f"hid_playstation recusa o segundo com -EEXIST. MACs: {macs}"
        )


def _rodar_a_noite_dela(bancada: Bancada, *, sync_antes_do_connect: bool) -> None:
    """O roteiro mínimo: A,B → só B (A cai) → B,A (A volta com node novo)."""
    ordem = {"sync_antes_do_connect": sync_antes_do_connect}
    # t=0 — os dois na mesa; A é o primeiro a ser enumerado, logo é o P1.
    bancada.sentar(UNIQ_A)
    bancada.sentar(UNIQ_B)
    bancada.passo(0.0, **ordem)
    bancada.passo(2.0, **ordem)  # o co-op assenta o Jogador 2
    # t=5 — a piscada: o primário A cai.
    bancada.levantar(UNIQ_A)
    bancada.passo(3.0, **ordem)
    # t=8 — A volta, com node NOVO (é o que o replug por BT faz).
    bancada.sentar(UNIQ_A)
    bancada.passo(3.0, **ordem)
    bancada.passo(2.0, **ordem)  # e a mesa assenta


@pytest.fixture
def bancada(monkeypatch: pytest.MonkeyPatch) -> Bancada:
    return Bancada(monkeypatch)


@pytest.mark.parametrize("sync_antes_do_connect", [False, True])
class TestAPiscadaDoPrimario:
    """O roteiro inteiro, nas duas ordens possíveis dos dois laços."""

    def test_o_jogador_2_continua_sendo_o_mesmo_controle(
        self, bancada: Bancada, sync_antes_do_connect: bool
    ) -> None:
        """Asserção 2 — a queixa dela, em uma linha.

        Antes da piscada o Jogador 2 é B. Depois dela também tem de ser B: o
        controle de quem está jogando não muda de mãos porque o controle da
        OUTRA pessoa piscou.
        """
        _rodar_a_noite_dela(bancada, sync_antes_do_connect=sync_antes_do_connect)

        assert bancada.jogador_2() == UNIQ_B, (
            "asserção 2: o Jogador 2 trocou de dono na piscada do P1 — era "
            f"{UNIQ_B} e virou {bancada.jogador_2()}. Linha do tempo "
            f"(t, jogador_2, índice de B): {bancada.historico}"
        )
        assert bancada.inst.primary_uniq == UNIQ_A, (
            "o controle que era o Jogador 1 voltou e NÃO retomou o posto — "
            f"o primário agora é {bancada.inst.primary_uniq}"
        )

    def test_quem_nao_saiu_da_mesa_nao_muda_de_indice(
        self, bancada: Bancada, sync_antes_do_connect: bool
    ) -> None:
        """Asserção 3 — o índice vira o MAC do vpad no kernel.

        B nunca saiu da mesa. Se o índice dele passeia, o MAC do vpad do
        Jogador 2 passa a pertencer a outra pessoa — e em jogo que salve por
        slot de dispositivo, os perfis trocam de dono.

        A janela em que B é o PRIMÁRIO (entre a queda de A e a volta dele)
        fica de fora de propósito: ali B não é secundário nenhum, é o P1, e
        isso é o produto funcionando com um controle só — não um passeio.
        """
        _rodar_a_noite_dela(bancada, sync_antes_do_connect=sync_antes_do_connect)

        indices = {i for _t, _j2, i in bancada.historico if i is not None}
        assert indices == {2}, (
            "asserção 3: B nunca saiu da mesa e mesmo assim mudou de "
            f"player_index — índices vistos: {sorted(indices)}. Linha do "
            f"tempo: {bancada.historico}"
        )

    def test_o_vpad_do_jogador_1_e_alimentado_pelo_mesmo_mac_do_comeco_ao_fim(
        self, bancada: Bancada, sync_antes_do_connect: bool
    ) -> None:
        """O outro lado da asserção 2: quem é o Jogador 1 também não passeia."""
        bancada.sentar(UNIQ_A)
        bancada.sentar(UNIQ_B)
        bancada.passo(0.0, sync_antes_do_connect=sync_antes_do_connect)
        primario_no_comeco = bancada.inst.primary_uniq
        assert primario_no_comeco == UNIQ_A

        bancada.levantar(UNIQ_A)
        bancada.passo(3.0, sync_antes_do_connect=sync_antes_do_connect)
        bancada.sentar(UNIQ_A)
        bancada.passo(3.0, sync_antes_do_connect=sync_antes_do_connect)

        assert bancada.inst.primary_uniq == primario_no_comeco


class TestOQueOInstrumentoPrecisaSaberRecusar:
    """Régua que só sabe passar não é régua — estes provam que ela RECUSA."""

    def test_a_mesa_recusa_o_segundo_grab_do_mesmo_node(self) -> None:
        mesa = _Mesa()
        node = mesa.sentar(UNIQ_A)
        assert mesa.grab(node, "primeiro") is True
        assert mesa.grab(node, "segundo") is False
        assert mesa.ebusy and node in mesa.ebusy[0]

    def test_a_mesa_deixa_o_mesmo_dono_regrabar(self) -> None:
        """O `EBUSY` de re-grab do próprio fd não é colisão (BUG-GRAB-DOUBLE-
        EBUSY-01) — se a bancada o contasse, ela acusaria defeito onde não há."""
        mesa = _Mesa()
        node = mesa.sentar(UNIQ_A)
        assert mesa.grab(node, "dono") is True
        assert mesa.grab(node, "dono") is True
        assert mesa.ebusy == []

    def test_o_node_e_renumerado_a_cada_volta(self) -> None:
        """Se a bancada devolvesse o mesmo node, ela não seria um replug BT."""
        mesa = _Mesa()
        primeiro = mesa.sentar(UNIQ_A)
        mesa.levantar(UNIQ_A)
        assert mesa.sentar(UNIQ_A) != primeiro

    def test_a_invariante_de_mac_duplicado_reprova(
        self, bancada: Bancada
    ) -> None:
        """A asserção 4 tem de saber acusar: dois vpads vivos com o MESMO MAC."""
        bancada.vpads.extend([_VpadFalso(2), _VpadFalso(2)])
        with pytest.raises(AssertionError, match="mesmo MAC"):
            bancada.conferir_invariantes()

    def test_a_invariante_de_ebusy_reprova(self, bancada: Bancada) -> None:
        bancada.mesa.ebusy.append("EBUSY forjado")
        with pytest.raises(AssertionError, match="dois donos do mesmo node"):
            bancada.conferir_invariantes()


class TestOAvisoDeTrocaDePrimario:
    """E1 isolado: o backend AVISA, e avisa ANTES do retarget."""

    def test_o_backend_avisa_antes_de_re_atrelar_o_evdev(
        self, bancada: Bancada
    ) -> None:
        """A ordem É a cura. Avisar depois do retarget seria avisar tarde: o
        `EBUSY` do journal já teria acontecido."""
        ordem: list[str] = []

        def _observador(_anterior: str | None, _novo: str | None) -> None:
            ordem.append("aviso")

        alvo_original = bancada.leitor_p1.retarget

        def _retarget(uniq: str | None) -> None:
            ordem.append("retarget")
            alvo_original(uniq)

        bancada.inst.set_primary_change_observer(_observador)
        bancada.leitor_p1.retarget = _retarget  # type: ignore[method-assign]
        bancada.sentar(UNIQ_A)
        bancada.tique_do_reconnect_loop()

        assert ordem == ["aviso", "retarget"]

    def test_o_coop_liga_o_aviso_sozinho_no_primeiro_sync(
        self, bancada: Bancada
    ) -> None:
        """A fiação é do co-op, não do `lifecycle`: o manager nasce sob demanda
        e o backend pode nem existir no boot."""
        assert bancada.inst._primary_change_observer is None
        bancada.sentar(UNIQ_A)
        bancada.sentar(UNIQ_B)
        bancada.coop.sync()
        assert bancada.inst._primary_change_observer == bancada.coop.ceder_ao_primario

    def test_backend_sem_a_api_nao_derruba_o_coop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Degradação declarada: fake/legado sem `set_primary_change_observer`
        segue funcionando (com o defeito), nunca quebrando."""
        bancada = Bancada(monkeypatch)
        bancada.daemon.controller = SimpleNamespace(primary_uniq=UNIQ_A, _evdev=None)
        bancada.sentar(UNIQ_A)
        bancada.sentar(UNIQ_B)
        bancada.coop.sync()  # não levanta
        assert UNIQ_B in bancada.coop._players

    def test_ceder_solta_o_grab_e_nao_para_o_reader(self, bancada: Bancada) -> None:
        """As regras do que pode rodar sob o `_io_lock`: solta o grab (ioctl,
        µs) e NÃO chama `stop()` (que faz `join(timeout=2.0)`)."""
        bancada.sentar(UNIQ_A)
        bancada.sentar(UNIQ_B)
        bancada.tique_do_reconnect_loop()
        bancada.tique_do_poll_loop()
        jogador = bancada.coop._players[UNIQ_B]
        node_de_b = bancada.mesa.nodes[UNIQ_B]
        assert bancada.mesa.dono_do_grab[node_de_b] == f"coop:{UNIQ_B}"

        bancada.coop.ceder_ao_primario(UNIQ_A, UNIQ_B)

        assert node_de_b not in bancada.mesa.dono_do_grab, (
            "o grab do secundário continua de pé — o leitor do primário vai "
            "levar EBUSY quando mirar este node"
        )
        assert jogador.reader.stopped is False, (
            "`stop()` faz join de até 2 s e roda sob o `_io_lock` do backend — "
            "quem para o reader é o poll loop, no desmonte"
        )
        assert jogador.cedido_ao_primario is True

    def test_o_cedido_para_de_alimentar_o_vpad_na_hora(
        self, bancada: Bancada
    ) -> None:
        """Entre o `ungrab` e o desmonte o vpad fica MUDO, não solto — senão o
        físico alimentaria o vpad do P1 E o do P2 ao mesmo tempo."""
        bancada.sentar(UNIQ_A)
        bancada.sentar(UNIQ_B)
        bancada.tique_do_reconnect_loop()
        bancada.tique_do_poll_loop()
        jogador = bancada.coop._players[UNIQ_B]
        vpad = jogador.vpad
        assert vpad is not None
        enviados: list[Any] = []
        vpad.forward_buttons = enviados.append  # type: ignore[method-assign]

        bancada.coop.ceder_ao_primario(UNIQ_A, UNIQ_B)
        # O tique que ainda encontra o jogador na lista (o desmonte é feito
        # pelo `_recolher_os_cedidos`, e a marca é lida antes de repassar).
        bancada.coop.forward_all()

        assert enviados == []
        assert UNIQ_B not in bancada.coop._players
        assert vpad.vivo is False, "o vpad do jogador cedido tem de ser desmontado"


class TestAReservaDoPostoDePrimario:
    """E2(a) isolado: o posto do Jogador 1 fica guardado por uma janela."""

    def test_o_deposto_retoma_o_posto_dentro_da_janela(
        self, bancada: Bancada
    ) -> None:
        bancada.sentar(UNIQ_A)
        bancada.sentar(UNIQ_B)
        bancada.tique_do_reconnect_loop()
        assert bancada.inst.primary_uniq == UNIQ_A

        bancada.levantar(UNIQ_A)
        bancada.tique_do_reconnect_loop()
        assert bancada.inst.primary_uniq == UNIQ_B, "com A fora, B TEM de assumir"

        bancada.relogio.avancar(3.0)
        bancada.sentar(UNIQ_A)
        bancada.tique_do_reconnect_loop()
        assert bancada.inst.primary_uniq == UNIQ_A

    def test_a_reserva_caduca_e_o_posto_nao_fica_pendurado(
        self, bancada: Bancada
    ) -> None:
        """Ela desligou o controle e continuou jogando com o outro: passados 30 s
        o posto é de quem está na mesa, e a volta de A não desmonta nada."""
        from hefesto_dualsense4unix.core.backend_pydualsense import PRIMARIO_RESERVA_SEC

        bancada.sentar(UNIQ_A)
        bancada.sentar(UNIQ_B)
        bancada.tique_do_reconnect_loop()
        bancada.levantar(UNIQ_A)
        bancada.tique_do_reconnect_loop()

        bancada.relogio.avancar(PRIMARIO_RESERVA_SEC + 1.0)
        bancada.sentar(UNIQ_A)
        bancada.tique_do_reconnect_loop()

        assert bancada.inst.primary_uniq == UNIQ_B

    def test_controle_novo_nunca_rouba_o_posto(self, bancada: Bancada) -> None:
        """A regra da 1ª chave continua valendo para todo o resto: só o DEPOSTO
        tem reserva, e ele só tem porque já era o P1."""
        bancada.sentar(UNIQ_A)
        bancada.tique_do_reconnect_loop()
        bancada.sentar(UNIQ_B)
        bancada.tique_do_reconnect_loop()

        assert bancada.inst.primary_uniq == UNIQ_A

    def test_o_deposto_que_vira_secundario_e_a_corrida_que_sobrou(
        self, bancada: Bancada
    ) -> None:
        """**A corrida que esta sprint NÃO fecha, medida em vez de suposta.**

        O aviso cobre um sentido — o secundário solta ANTES de o primário
        pegar. O sentido INVERSO não tem aviso: quando A retoma o posto, o
        leitor do primário larga o node de B de forma ASSÍNCRONA (o `retarget`
        só sinaliza; quem fecha o fd é a thread dona). Se o `sync` do co-op
        chegar antes desse fechamento, quem leva `EBUSY` é o co-op.

        Não dá para fechar por aqui: fechar fd de outra thread é justamente o
        que o HANG-01/GYRO-FD-01 baniu nesta casa. O que dá é **medir o
        desfecho**, e o desfecho é aceitável — o retry que o co-op já tinha
        (`BUG-COOP-GRAB-SILENT-FAIL-01`) assenta o Jogador 2 no ciclo seguinte.
        O preço é ~2 s a mais para o P2 entrar, e uma linha no journal.

        O que este teste PROÍBE: que o desfecho vire "o jogador morre" ou "o
        físico dobra o input". Se algum dia virar, ele reprova aqui.
        """
        bancada.leitor_p1.solta_na_hora = False
        bancada.sentar(UNIQ_A)
        bancada.sentar(UNIQ_B)
        bancada.tique_do_reconnect_loop()
        bancada.tique_do_poll_loop()
        bancada.leitor_p1.a_thread_do_leitor_acorda()
        assert bancada.jogador_2() == UNIQ_B

        bancada.levantar(UNIQ_A)
        bancada.tique_do_reconnect_loop()
        bancada.tique_do_poll_loop()
        bancada.leitor_p1.a_thread_do_leitor_acorda()

        # A conta zerada AQUI é o que garante que o `EBUSY` medido abaixo é o
        # desta corrida, e não sobra de um passo anterior.
        assert bancada.mesa.ebusy == []

        bancada.relogio.avancar(3.0)
        bancada.sentar(UNIQ_A)
        bancada.tique_do_reconnect_loop()  # A retoma; o node de B fica preso
        bancada.tique_do_poll_loop()  # o co-op tenta B cedo demais

        assert bancada.mesa.ebusy, (
            "a corrida deixou de existir — se foi de propósito, esta lápide "
            "e o texto acima têm de sair junto"
        )
        assert UNIQ_B not in bancada.coop._players, (
            "sem grab confirmado o jogador NÃO pode existir: o físico dobraria "
            "o input no jogo (BUG-COOP-GRAB-SILENT-FAIL-01)"
        )

        # ...e o ciclo seguinte, com o fd já fechado, assenta o Jogador 2.
        bancada.leitor_p1.a_thread_do_leitor_acorda()
        bancada.tique_do_poll_loop()

        assert bancada.jogador_2() == UNIQ_B
        assert bancada.inst.primary_uniq == UNIQ_A

    def test_a_retomada_refaz_o_transporte_e_o_retarget(
        self, bancada: Bancada
    ) -> None:
        """A armadilha nomeada na sprint: uma 'estabilidade' que devolvesse o
        posto sem refazer `_detect_transport` e o `retarget` deixaria o daemon
        achando que o controle está no cabo quando ele voltou por rádio."""
        bancada.sentar(UNIQ_A)
        bancada.sentar(UNIQ_B)
        bancada.tique_do_reconnect_loop()
        bancada.levantar(UNIQ_A)
        bancada.tique_do_reconnect_loop()
        bancada.inst._transport = "usb"  # o que um atalho deixaria para trás

        bancada.sentar(UNIQ_A)
        bancada.tique_do_reconnect_loop()

        assert bancada.inst._transport == "bt"
        assert bancada.leitor_p1.node == bancada.mesa.nodes[UNIQ_A]
