"""O-ASSENTO-GUARDADO-NAO-ANDA-02 — o jogo também espera a carta 1, e o prazo conta a suspensão.

**A decisão (24/09/2026, por delegação dela, ``D-2409-O-JOGO-ESPERA-O-LUGAR-
GUARDADO``).** Com o P1 fora dentro do prazo, o P2 virava primário na hora e
dirigia o jogador 1 do jogo enquanto a lâmpada e a tela diziam 2. Agora, com o
jogo aberto, o vpad do P1 fica parado à espera dele e o P2 continua no vpad 2.
Passado o prazo, vale a NUM-01.

**A bancada é a de queda (COOP-QUE-NÃO-DESMONTA-01/E4), com a classe real:** o
``PyDualSenseController`` com o ``connect()`` e o ``read_state()`` de verdade,
o ``CoopManager`` com ``sync()`` e ``forward_all()`` de verdade, e o
``ControllerIdentityRegistry`` de verdade — o dono do número que a tela e a
lâmpada mostram. Os dublês são os da bancada de queda (a mesa, os leitores
evdev com grab exclusivo, o vpad), e nenhum nó uinput nasce.

**O que ela mede é o vpad de cada jogador, pelo lado do JOGO:** a mesa do jogo
que o co-op guarda (o lugar de cada vpad, no modelo do SDL) e, para o vpad do
P1, o que o ``read_state()`` entrega a ele — o leitor do P1 carimba de quem é o
node que ele lê.

1. o P1 fora por 20 s: o vpad dele de pé e sem dono, cada um que ficou no
   PRÓPRIO vpad (o mesmo objeto de antes), e o jogo vendo o número da tela;
2. a volta dele: o P1 no vpad 1 de novo, ninguém recriado;
3. depois do prazo: a NUM-01 — o P2 no vpad 1 com o número 1, e ninguém que
   ficou perde o controle;
4. o prazo atravessando uma suspensão simulada pelo relógio do kernel: o
   ``CLOCK_BOOTTIME`` anda, o ``CLOCK_MONOTONIC`` não.

A matriz: dois, três e quatro controles; USB, BT e a mesa mista; o lugar do P1
e os três outros.

AS MORDIDAS (24/09/2026, cada uma devolvida com o md5 conferido):

- ``_quem_senta_no_posto`` sem a vaga (o próximo assume na hora) reprova
  :class:`TestOP1ForaPorVinteSegundos`;
- ``_RELOGIO_DOS_PRAZOS`` no ``CLOCK_MONOTONIC`` reprova
  :class:`TestOPrazoAtravessaASuspensao`;
- o leitor do P1 seguindo o P2 com o posto vago reprova pela metade dos
  BOTÕES (``evdev_buttons_once``) — a régua que lia só o ``read_state()``
  passava 47 de 47 sobre ela (conferência de 24/09/2026);
- o topo da vaga de volta a ``battery_pct=0`` reprova
  :class:`TestOTopoDoEstadoNaVaga`.

Nenhum endereço real: faixa forjada ``aa:bb:cc`` com os octetos 4 e 5 zerados.
"""
from __future__ import annotations

import contextlib
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as backend_mod
from hefesto_dualsense4unix.core.backend_pydualsense import (
    PRIMARIO_RESERVA_SEC,
    PyDualSenseController,
    relogio_do_prazo,
)
from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import external_identity as ei_mod
from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod
from hefesto_dualsense4unix.daemon.subsystems.coop import _CHAVE_DO_P1, CoopManager
from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
    ExternalIdentityRegistry,
)
from hefesto_dualsense4unix.daemon.subsystems.identity import (
    ControllerIdentityRegistry,
    prazo_do_lugar_guardado,
    relogio_do_lugar_guardado,
)
from tests.unit.test_coop_bancada_de_queda_do_primario import (
    _FakeHandle,
    _LeitorDeSecundario,
    _LeitorDoPrimario,
    _Mesa,
    _VpadFalso,
)

#: A mesa de quatro, mais um controle que ninguém viu antes (gente nova).
CHAVES = (
    "AA:BB:CC:00:00:01",
    "AA:BB:CC:00:00:02",
    "AA:BB:CC:00:00:03",
    "AA:BB:CC:00:00:04",
    "AA:BB:CC:00:00:05",
)
UNIQS = tuple(c.replace(":", "").lower() for c in CHAVES)
P1, P2, P3, P4, NOVO = UNIQS
CHAVE_DE = dict(zip(UNIQS, CHAVES, strict=True))

BOOT = "boot-teste-o-jogo-espera-a-carta"

#: O gesto da linha 17: fora vinte segundos.
VINTE_SEGUNDOS = 20.0
#: O tique lento da casa: o registro de identidade e o `sync` do co-op, ~2 s.
TIQUE = 2.0
#: O carimbo que o leitor do P1 põe no estado: de quem é o node que ele lê.
_MARCA = "de:"

#: A matriz de transportes: tudo no cabo, tudo no rádio, e a mesa dela (mista).
TRANSPORTES = {
    "usb": ("usb", "usb", "usb", "usb"),
    "bt": ("bt", "bt", "bt", "bt"),
    "mista": ("usb", "bt", "usb", "bt"),
}
MATRIZ = pytest.mark.parametrize(
    ("quantos", "transporte"),
    [(n, t) for n in (2, 3, 4) for t in TRANSPORTES],
    ids=[f"{n}-controles-{t}" for n in (2, 3, 4) for t in TRANSPORTES],
)

_BOOTTIME = time.CLOCK_BOOTTIME
_MONOTONIC = time.CLOCK_MONOTONIC
_CLOCK_GETTIME_REAL = time.clock_gettime


class _MesaDeCinco(_Mesa):
    """A mesa da bancada de queda, com os cinco controles desta régua."""

    def _keys_presentes(self) -> list[str]:
        return [CHAVE_DE[u] for u in self.nodes]


class _LeitorDoP1(_LeitorDoPrimario):
    """O leitor do P1 da bancada de queda, que diz DE QUEM é o node que lê.

    O `read_state()` de verdade pede o `snapshot()` ao leitor quando há
    primário; o carimbo nos botões é o que a régua lê para saber quem está
    dirigindo o vpad do P1. Sem primário (a vaga), o `read_state()` nem pede: o
    estado é o neutro, sem carimbo nenhum.
    """

    def snapshot(self) -> Any:
        dono = next((u for u, n in self._mesa.nodes.items() if n == self.node), None)
        return SimpleNamespace(
            lx=128,
            ly=128,
            rx=128,
            ry=128,
            l2_raw=0,
            r2_raw=0,
            buttons_pressed=frozenset({_MARCA + dono}) if dono else frozenset(),
        )


class Relogio:
    """Relógio de mentira dos prazos — o tempo anda sem `sleep`."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def avancar(self, segundos: float) -> None:
        self.t += segundos


class Kernel:
    """Os dois relógios do kernel, para simular uma suspensão.

    Acordada, a máquina anda os dois; dormindo, só o ``CLOCK_BOOTTIME`` anda —
    é a diferença entre eles, e é a que o ``CLOCK_MONOTONIC`` (o
    ``time.monotonic``) esconde.
    """

    def __init__(self) -> None:
        self.acordada = 5000.0
        self.dormiu = 0.0

    def avancar(self, segundos: float) -> None:
        self.acordada += segundos

    def dormir(self, segundos: float) -> None:
        self.dormiu += segundos

    def clock_gettime(self, relogio: int) -> float:
        if relogio == _BOOTTIME:
            return self.acordada + self.dormiu
        if relogio == _MONOTONIC:
            return self.acordada
        return _CLOCK_GETTIME_REAL(relogio)


@pytest.fixture
def config_isolado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`config_dir` em tmp — nada aqui toca o `controllers.json` dela."""
    from hefesto_dualsense4unix.utils import xdg_paths

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    monkeypatch.setattr(id_mod, "_read_boot_id", lambda: BOOT)
    monkeypatch.setattr(ei_mod, "_read_boot_id", lambda: BOOT)
    return tmp_path


class MesaDoJogo:
    """Backend real + co-op real + registro de identidade real, e um jogo aberto.

    ``relogio`` None deixa os prazos no relógio do PRODUTO (``relogio_do_prazo``
    e ``relogio_do_lugar_guardado``) — é o caso da suspensão, em que quem move o
    tempo é o :class:`Kernel`.
    """

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        relogio: Relogio | None,
        tempo: Relogio | Kernel,
        jogo: bool = True,
        coop: bool = True,
    ) -> None:
        self.tempo = tempo
        self.mesa = _MesaDeCinco()
        self.leitor_p1 = _LeitorDoP1(self.mesa)
        self.inst = PyDualSenseController(evdev_reader=self.leitor_p1)  # type: ignore[arg-type]
        if relogio is not None:
            self.inst._relogio = relogio
        # A leitura do 0x05 é hidraw de verdade e não tem nada a ver com a vaga.
        self.inst.read_calibration = lambda _uniq=None: None  # type: ignore[assignment]
        self.reg = ControllerIdentityRegistry(clock=relogio)
        self.vpad_do_p1 = _VpadFalso(1)
        self.vpads: list[_VpadFalso] = [self.vpad_do_p1]
        self.daemon = SimpleNamespace(
            # A configuração de verdade do daemon, com os padrões dela.
            config=DaemonConfig(coop_enabled=coop),
            _gamepad_device=self.vpad_do_p1,
            controller=self.inst,
            _coop_manager=None,
            identity_registry=self.reg,
            # O sinal pegajoso da R-04: "game" é o jogo com a autoridade.
            display_authority="game" if jogo else "daemon",
            # Os dois campos do `Daemon` que o multiplicador do rumble lê.
            _last_auto_mult=0.7,
            _last_auto_change_at=0.0,
        )
        self.coop = CoopManager(self.daemon)  # type: ignore[arg-type]
        self.daemon._coop_manager = self.coop
        monkeypatch.setattr(_LeitorDeSecundario, "mesa", self.mesa)
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
        # Hermético: NUNCA o /sys/class/leds real.
        monkeypatch.setattr("hefesto_dualsense4unix.core.sysfs_leds.discover", lambda: {})

    def _nascer_vpad(self, _flavor: Any, *, player: int = 1, **_kw: Any) -> _VpadFalso:
        vpad = _VpadFalso(player)
        self.vpads.append(vpad)
        return vpad

    # -- os laços do daemon ---------------------------------------------

    def connect(self) -> None:
        """Um `connect()` do `reconnect_loop`, com o handle no transporte de cada um."""
        vistos = self.mesa.como_o_backend_ve()
        por_path = {
            path: uniq
            for (_key, path, _edge), uniq in zip(vistos, self.mesa.nodes, strict=True)
        }
        with patch.object(
            PyDualSenseController, "_enumerate_device_keys", return_value=vistos
        ), patch.object(
            PyDualSenseController,
            "_open_one",
            side_effect=lambda path, *, is_edge: _FakeHandle(
                self.mesa.transporte_de(por_path[path])
            ),
        ):
            self.inst.connect()

    def tique(self, segundos: float = TIQUE) -> None:
        """Os laços do daemon, na ordem em que o hotplug os acorda."""
        self.tempo.avancar(segundos)
        self.connect()  # o reconnect_loop vê o /dev/input mudar
        self.inst.read_state()  # o poll loop despacha o P1
        # O `_sync_identity_registry` do lifecycle, com os handles de agora.
        self.reg.sync_connected(
            [u for u in self.inst.alvos_conectados().values() if isinstance(u, str)]
        )
        self.coop.sync()
        self.coop.forward_all()
        self.coop.forward_all()  # o tique seguinte recolhe quem cedeu ao P1
        self.conferir_invariantes()

    def conferir_invariantes(self) -> None:
        """As duas da bancada de queda, em TODO instante: sem EBUSY, sem MAC repetido."""
        assert not self.mesa.ebusy, "; ".join(self.mesa.ebusy)
        macs = [v.mac for v in self.vpads if v.vivo]
        assert len(macs) == len(set(macs)), f"dois vpads vivos com o mesmo MAC: {macs}"

    # -- a leitura --------------------------------------------------------

    def dono_do_vpad_do_p1(self) -> str | None:
        """Quem alimenta o vpad do P1 agora (None = parado), pelas DUAS metades.

        O laço do daemon (`dispatch_gamepad`) manda ao vpad do P1 os analógicos
        do `read_state()` e os BOTÕES do `poll.evdev_buttons_once`, que lê o
        leitor do P1 direto, sem passar pelo `read_state()`. Medir só a
        primeira metade deixaria de fora um leitor que seguisse outro controle
        com o posto vago (conferência de 24/09/2026). As duas têm de dizer o
        mesmo dono.
        """
        from hefesto_dualsense4unix.daemon.subsystems.poll import evdev_buttons_once

        metades = (
            self.inst.read_state().buttons_pressed,
            evdev_buttons_once(self.daemon),
        )
        donos = {b[len(_MARCA):] for metade in metades for b in metade if b.startswith(_MARCA)}
        assert len(donos) <= 1, f"o vpad do P1 recebe de dois controles: {donos}"
        return next(iter(donos), None)

    def o_jogo_ve(self) -> dict[int, str | None]:
        """Jogador N do jogo → o controle que alimenta o vpad daquele lugar."""
        fora: dict[int, str | None] = {}
        for lugar, chave in sorted(self.coop._mesa_do_jogo.items()):
            if chave == _CHAVE_DO_P1:
                fora[lugar + 1] = self.dono_do_vpad_do_p1() if self.vpad_do_p1.vivo else None
                continue
            jogador = self.coop._players.get(chave)
            vivo = (
                jogador is not None
                and jogador.vpad is not None
                and bool(getattr(jogador.vpad, "vivo", False))
                and not jogador.cedido_ao_primario
            )
            fora[lugar + 1] = chave if vivo else None
        return fora

    def a_tela(self) -> dict[str, int]:
        """O número que a TELA mostra — a mesa de agora do registro."""
        return self.reg.numeros_da_mesa()

    def vpad_de(self, uniq: str) -> Any:
        jogador = self.coop._players.get(uniq)
        return jogador.vpad if jogador is not None else None

    def o_jogo_segue_a_tela(self) -> None:
        """Cada controle na mesa dirige, no jogo, o jogador do número que a tela diz."""
        jogo = self.o_jogo_ve()
        for uniq, numero in self.a_tela().items():
            assert jogo.get(numero) == uniq, (
                f"a tela diz {numero} para {uniq}, e o jogador {numero} do jogo é "
                f"{jogo.get(numero)} — o jogo: {jogo}, a tela: {self.a_tela()}"
            )


def montar(
    monkeypatch: pytest.MonkeyPatch,
    quantos: int,
    transporte: str = "mista",
    *,
    relogio: Relogio | None = None,
    tempo: Relogio | Kernel | None = None,
    jogo: bool = True,
    coop: bool = True,
) -> MesaDoJogo:
    """A mesa de ``quantos`` controles na ordem, os vpads nascidos, o jogo aberto."""
    if relogio is None and tempo is None:
        relogio = Relogio()
    bancada = MesaDoJogo(
        monkeypatch,
        relogio=relogio,
        tempo=tempo if tempo is not None else relogio,  # type: ignore[arg-type]
        jogo=jogo,
        coop=coop,
    )
    for uniq, via in zip(UNIQS[:quantos], TRANSPORTES[transporte][:quantos], strict=True):
        bancada.mesa.sentar(uniq, transporte=via)
    for _ in range(3):
        bancada.tique()
    assert bancada.dono_do_vpad_do_p1() == P1
    if coop:
        esperado = {n + 1: UNIQS[n] for n in range(quantos)}
        assert bancada.o_jogo_ve() == esperado, (
            f"a bancada não montou a mesa: {bancada.o_jogo_ve()}"
        )
        assert bancada.a_tela() == {UNIQS[n]: n + 1 for n in range(quantos)}
    return bancada


@pytest.mark.usefixtures("config_isolado")
class TestOP1ForaPorVinteSegundos:
    """As três medidas da sprint, com o jogo aberto e o co-op de pé."""

    @MATRIZ
    def test_o_vpad_do_p1_espera_e_quem_ficou_nao_anda(
        self, monkeypatch: pytest.MonkeyPatch, quantos: int, transporte: str
    ) -> None:
        """A MORDIDA desta sprint: o P2 não dirige o jogador 1 enquanto a tela diz 2."""
        bancada = montar(monkeypatch, quantos, transporte)
        ficaram = UNIQS[1:quantos]
        vpads_de_antes = {u: bancada.vpad_de(u) for u in ficaram}

        bancada.mesa.levantar(P1)
        for _ in range(int(VINTE_SEGUNDOS / TIQUE)):
            bancada.tique()
            assert bancada.vpad_do_p1.vivo, "o vpad do P1 sumiu em vez de parar"
            assert bancada.dono_do_vpad_do_p1() is None, (
                f"o vpad do jogador 1 está sendo dirigido por "
                f"{bancada.dono_do_vpad_do_p1()} com o P1 fora dentro do prazo — "
                f"a tela diz {bancada.a_tela()}"
            )
            for uniq in ficaram:
                assert bancada.vpad_de(uniq) is vpads_de_antes[uniq], (
                    f"{uniq} perdeu o vpad dele com o P1 fora"
                )
            assert bancada.a_tela() == {u: n + 2 for n, u in enumerate(ficaram)}
            assert bancada.o_jogo_ve() == {1: None, **{n + 2: u for n, u in enumerate(ficaram)}}
            bancada.o_jogo_segue_a_tela()
        assert bancada.inst.primary_uniq == P1, "o posto de P1 deixou de ser do P1"

    @MATRIZ
    def test_a_volta_dele_dentro_do_prazo(
        self, monkeypatch: pytest.MonkeyPatch, quantos: int, transporte: str
    ) -> None:
        bancada = montar(monkeypatch, quantos, transporte)
        ficaram = UNIQS[1:quantos]
        vpads_de_antes = {u: bancada.vpad_de(u) for u in ficaram}

        via = bancada.mesa.transporte_de(P1)
        bancada.mesa.levantar(P1)
        for _ in range(int(VINTE_SEGUNDOS / TIQUE)):
            bancada.tique()
        bancada.mesa.sentar(P1, transporte=via)
        bancada.tique()

        assert bancada.dono_do_vpad_do_p1() == P1
        assert bancada.inst.get_transport() == via
        for uniq in ficaram:
            assert bancada.vpad_de(uniq) is vpads_de_antes[uniq], (
                f"{uniq} foi recriado na volta do P1"
            )
        assert bancada.o_jogo_ve() == {n + 1: UNIQS[n] for n in range(quantos)}
        bancada.o_jogo_segue_a_tela()

    @MATRIZ
    def test_depois_do_prazo_vale_a_num01(
        self, monkeypatch: pytest.MonkeyPatch, quantos: int, transporte: str
    ) -> None:
        """Passado o prazo, o P2 assume o vpad do P1 com o número 1, e ninguém fica sem controle.

        Quem ficou atrás do P2 NÃO é recriado: o jogo não perde o controle de
        ninguém, e as cartas seguem em ordem de lugar (a regra do
        ``planejar_a_ordem``, que só exige ordem).
        """
        bancada = montar(monkeypatch, quantos, transporte)
        atras = UNIQS[2:quantos]
        vpads_de_antes = {u: bancada.vpad_de(u) for u in atras}

        bancada.mesa.levantar(P1)
        passos = int((max(PRIMARIO_RESERVA_SEC, prazo_do_lugar_guardado()) + TIQUE) / TIQUE)
        for _ in range(passos + 1):
            bancada.tique()

        assert bancada.dono_do_vpad_do_p1() == P2
        tela = bancada.a_tela()
        assert tela == {u: n + 1 for n, u in enumerate(UNIQS[1:quantos])}
        for uniq in atras:
            assert bancada.vpad_de(uniq) is vpads_de_antes[uniq]
            assert bancada.vpad_de(uniq).vivo
        jogo = bancada.o_jogo_ve()
        donos = [dono for dono in jogo.values() if dono is not None]
        assert sorted(donos) == sorted(UNIQS[1:quantos]), (
            f"alguém ficou sem controle (ou com dois) depois do prazo: {jogo}"
        )
        numeros_por_lugar = [tela[jogo[lugar]] for lugar in sorted(jogo) if jogo[lugar]]
        assert numeros_por_lugar == sorted(numeros_por_lugar)


@pytest.mark.usefixtures("config_isolado")
class TestOsOutrosTresLugares:
    """A matriz dos lugares: o P2, o P3 e o P4 saindo — o que já valia, e continua."""

    @pytest.mark.parametrize("quem", [P2, P3, P4], ids=["p2", "p3", "p4"])
    @pytest.mark.parametrize("transporte", list(TRANSPORTES))
    def test_quem_sai_volta_ao_mesmo_lugar_e_ninguem_anda(
        self, monkeypatch: pytest.MonkeyPatch, quem: str, transporte: str
    ) -> None:
        bancada = montar(monkeypatch, 4, transporte)
        ficaram = [u for u in UNIQS[:4] if u != quem]
        numero = UNIQS.index(quem) + 1
        vpads_de_antes = {u: bancada.vpad_de(u) for u in ficaram if u != P1}

        via = bancada.mesa.transporte_de(quem)
        bancada.mesa.levantar(quem)
        for _ in range(int(VINTE_SEGUNDOS / TIQUE)):
            bancada.tique()
            assert bancada.dono_do_vpad_do_p1() == P1
            assert bancada.a_tela() == {u: UNIQS.index(u) + 1 for u in ficaram}
            assert numero not in bancada.o_jogo_ve()
            bancada.o_jogo_segue_a_tela()

        bancada.mesa.sentar(quem, transporte=via)
        bancada.tique()
        bancada.tique()
        for uniq, vpad in vpads_de_antes.items():
            assert bancada.vpad_de(uniq) is vpad
        assert bancada.o_jogo_ve() == {n + 1: UNIQS[n] for n in range(4)}
        bancada.o_jogo_segue_a_tela()


@pytest.mark.usefixtures("config_isolado")
class TestQuandoOPostoNaoEspera:
    """As três portas de saída da vaga, e os dois casos em que ela nem começa."""

    def test_fora_do_co_op_o_outro_assume_na_hora(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O controle de reserva: sem co-op, o outro não tem vpad próprio."""
        bancada = montar(monkeypatch, 2, coop=False)
        bancada.mesa.levantar(P1)
        bancada.tique()
        assert bancada.dono_do_vpad_do_p1() == P2

    def test_sem_jogo_o_outro_assume_na_hora(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Sem jogo, o dono do posto de P1 também navega o PC — não se para o mouse."""
        bancada = montar(monkeypatch, 3, jogo=False)
        bancada.mesa.levantar(P1)
        bancada.tique()
        assert bancada.dono_do_vpad_do_p1() == P2

    def test_gente_nova_refaz_a_mesa_e_solta_o_posto(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bancada = montar(monkeypatch, 3)
        bancada.mesa.levantar(P1)
        bancada.tique()
        assert bancada.dono_do_vpad_do_p1() is None
        bancada.mesa.sentar(NOVO)
        bancada.tique()
        bancada.tique()
        assert bancada.dono_do_vpad_do_p1() == P2
        assert bancada.a_tela()[P2] == 1

    def test_o_renumerar_agora_solta_o_posto(self, monkeypatch: pytest.MonkeyPatch) -> None:
        bancada = montar(monkeypatch, 3)
        bancada.mesa.levantar(P1)
        bancada.tique()
        assert bancada.dono_do_vpad_do_p1() is None
        # O `identity.renumber` do IPC: o mapa dos lugares gravados.
        bancada.reg.compact(bancada.reg.snapshot())
        bancada.tique()
        assert bancada.dono_do_vpad_do_p1() == P2
        assert bancada.a_tela()[P2] == 1

    def test_o_jogo_que_solta_a_autoridade_solta_o_posto(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bancada = montar(monkeypatch, 3)
        bancada.mesa.levantar(P1)
        bancada.tique()
        assert bancada.dono_do_vpad_do_p1() is None
        bancada.daemon.display_authority = "daemon"
        assert bancada.dono_do_vpad_do_p1() == P2, (
            "a vaga tem de acabar no tique do read_state, sem esperar o connect()"
        )

    def test_o_rumble_do_jogo_para_o_vpad_do_p1_nao_cai_nos_outros(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Na vaga, o rumble que o jogo manda ao vpad do P1 mira o P1 ausente.

        O sink é o de produção (``make_primary_rumble_sink``). Um posto vago que
        respondesse ``None`` ao ``primary_uniq`` cairia no ramo sem endereço do
        ``apply_game_rumble`` — o broadcast, que sacode os três que ficaram.
        """
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
            make_primary_rumble_sink,
        )

        bancada = montar(monkeypatch, 3)
        bancada.mesa.levantar(P1)
        bancada.tique()
        assert bancada.inst.primary_uniq == P1
        assert bancada.inst.hidraw_path() is None

        broadcast: list[tuple[int, int]] = []
        mirados: list[str] = []
        monkeypatch.setattr(
            bancada.inst, "set_rumble", lambda weak, strong: broadcast.append((weak, strong))
        )
        monkeypatch.setattr(
            bancada.inst,
            "set_rumble_for",
            lambda uniq, weak, strong: mirados.append(uniq) or False,
        )
        make_primary_rumble_sink(bancada.daemon)(120, 200)  # type: ignore[arg-type]

        assert broadcast == [], "o rumble do jogador 1 foi em broadcast para os que ficaram"
        assert mirados == [P1]


@pytest.mark.usefixtures("config_isolado")
class TestOPrazoAtravessaASuspensao:
    """O item 2: os prazos contam o tempo em que a máquina dormiu."""

    def test_o_posto_vago_vence_depois_de_dormir(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        kernel = Kernel()
        monkeypatch.setattr(time, "clock_gettime", kernel.clock_gettime)
        bancada = montar(monkeypatch, 4, tempo=kernel)
        bancada.mesa.levantar(P1)
        bancada.tique()
        assert bancada.dono_do_vpad_do_p1() is None

        kernel.dormir(3600.0)
        bancada.tique(0.0)

        assert bancada.dono_do_vpad_do_p1() == P2, (
            "depois de uma hora dormindo, o posto do P1 ainda esperava — o prazo "
            "não contou a suspensão"
        )
        assert bancada.a_tela()[P2] == 1

    def test_quem_volta_primeiro_depois_de_dormir_e_o_um(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O caso da sprint: a mesa saiu antes de dormir, e o primeiro que volta é 1."""
        kernel = Kernel()
        monkeypatch.setattr(time, "clock_gettime", kernel.clock_gettime)
        bancada = montar(monkeypatch, 4, tempo=kernel)
        for uniq in UNIQS[:4]:
            bancada.mesa.levantar(uniq)
        bancada.tique()
        assert bancada.a_tela() == {}

        kernel.dormir(3600.0)
        bancada.mesa.sentar(P3)
        bancada.tique(0.0)

        assert bancada.a_tela() == {P3: 1}, (
            "o primeiro a voltar depois de uma hora dormindo mostrou o número "
            f"antigo sozinho: {bancada.a_tela()}"
        )
        assert bancada.dono_do_vpad_do_p1() == P3

    def test_acordada_o_prazo_ainda_vale(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """O contrapeso: sem dormir, os mesmos segundos não vencem nada."""
        kernel = Kernel()
        monkeypatch.setattr(time, "clock_gettime", kernel.clock_gettime)
        bancada = montar(monkeypatch, 4, tempo=kernel)
        bancada.mesa.levantar(P1)
        bancada.tique()
        bancada.tique(VINTE_SEGUNDOS - TIQUE)
        assert bancada.dono_do_vpad_do_p1() is None


class TestORelogioEUmSo:
    """Um dono só para os dois prazos — e o kernel desta máquina o tem."""

    def test_os_tres_prazos_perguntam_ao_mesmo_dono(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        backend = PyDualSenseController(evdev_reader=_LeitorDoP1(_MesaDeCinco()))  # type: ignore[arg-type]
        assert backend._relogio is relogio_do_prazo
        assert ControllerIdentityRegistry()._clock is relogio_do_lugar_guardado
        assert ExternalIdentityRegistry()._clock is relogio_do_lugar_guardado

        monkeypatch.setattr(backend_mod, "relogio_do_prazo", lambda: 42.0)
        assert relogio_do_lugar_guardado() == 42.0, (
            "o relógio do lugar guardado não pergunta ao dono — são dois relógios"
        )

    def test_o_dono_e_o_relogio_que_anda_na_suspensao(self) -> None:
        assert backend_mod._RELOGIO_DOS_PRAZOS == time.CLOCK_BOOTTIME
        antes = time.clock_gettime(time.CLOCK_MONOTONIC)
        agora = relogio_do_prazo()
        assert agora >= antes, (
            "o CLOCK_BOOTTIME ficou atrás do CLOCK_MONOTONIC — ele soma a "
            "suspensão, nunca a subtrai"
        )


@pytest.mark.usefixtures("config_isolado")
class TestAVoltaPeloOutroTransporte:
    """A linha 3 da bancada dela: o P1 sai do cabo e volta pelo rádio (e o inverso).

    A régua de cima devolve o P1 no MESMO transporte em que ele caiu; o gesto
    que a bancada cobra é o da troca. A key do handle é o MAC nos dois
    transportes, e é por ela que a vaga reconhece quem voltou.
    """

    @pytest.mark.parametrize(
        ("de", "para"), [("usb", "bt"), ("bt", "usb")], ids=["cabo-para-radio", "radio-para-cabo"]
    )
    @pytest.mark.parametrize("quantos", [2, 4])
    def test_o_p1_volta_pelo_outro_transporte_ao_vpad_dele(
        self, monkeypatch: pytest.MonkeyPatch, quantos: int, de: str, para: str
    ) -> None:
        bancada = montar(monkeypatch, quantos, "usb" if de == "usb" else "bt")
        ficaram = UNIQS[1:quantos]
        vpads_de_antes = {u: bancada.vpad_de(u) for u in ficaram}

        bancada.mesa.levantar(P1)
        for _ in range(3):
            bancada.tique()
            assert bancada.dono_do_vpad_do_p1() is None
        bancada.mesa.sentar(P1, transporte=para)
        bancada.tique()

        assert bancada.dono_do_vpad_do_p1() == P1
        assert bancada.inst.get_transport() == para
        for uniq in ficaram:
            assert bancada.vpad_de(uniq) is vpads_de_antes[uniq]
        assert bancada.a_tela()[P1] == 1
        assert bancada.o_jogo_ve() == {n + 1: UNIQS[n] for n in range(quantos)}
        bancada.o_jogo_segue_a_tela()


@pytest.mark.usefixtures("config_isolado")
class TestOTopoDoEstadoNaVaga:
    """Com o posto vago, o estado do topo não diz «desconectado» nem «bateria 0».

    A conferência (24/09/2026) mediu: com o posto vago, o `read_state()` caía no
    ramo da mesa VAZIA — `connected=False` e `battery_pct=0` — com três
    controles jogando. O laço do daemon publica esse estado no store a cada
    tique, e a política «auto» da vibração lê a bateria DALI: com 0, o
    `_game_rumble_mult` desce a 0,3 e enfraquece a vibração que o jogo manda
    ao P2, ao P3 e ao P4 enquanto o P1 está fora. Antes da vaga esse ramo só
    rodava sem controle nenhum, e o laço nem chamava o `read_state()`.

    O `connected` do topo é o AGREGADO (`is_connected()`, o mesmo do ramo de
    sempre), e a bateria é a última leitura do dono do posto — o «não sei»
    nunca vira zero (BATERIA-QUE-PULA-01).
    """

    @staticmethod
    def _carga_no_p1(bancada: MesaDoJogo, nivel: int, estado: int) -> None:
        # O `DSBattery` que o report_thread da pydualsense preenche.
        handle = bancada.inst._handles[CHAVE_DE[P1]]
        handle.battery = SimpleNamespace(Level=nivel, State=estado)

    @pytest.mark.parametrize("transporte", list(TRANSPORTES))
    def test_o_topo_segue_conectado_com_a_carga_do_dono_do_posto(
        self, monkeypatch: pytest.MonkeyPatch, transporte: str
    ) -> None:
        bancada = montar(monkeypatch, 3, transporte)
        self._carga_no_p1(bancada, 75, 0x1)
        antes = bancada.inst.read_state()
        assert (antes.connected, antes.battery_pct, antes.battery_state) == (
            True, 75, "carregando",
        )

        bancada.mesa.levantar(P1)
        for _ in range(int(VINTE_SEGUNDOS / TIQUE)):
            bancada.tique()
            estado = bancada.inst.read_state()
            assert bancada.dono_do_vpad_do_p1() is None
            assert estado.connected is True, (
                "com três controles jogando, o topo disse desconectado"
            )
            assert (estado.battery_pct, estado.battery_state) == (75, "carregando"), (
                f"a vaga respondeu {estado.battery_pct}/{estado.battery_state} — "
                "o «não sei» virou zero"
            )
            assert (estado.raw_lx, estado.raw_ly, estado.buttons_pressed) == (
                128, 128, frozenset(),
            )

    def test_a_vibracao_auto_dos_outros_nao_cai_com_o_p1_fora(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O consumidor: a política «auto» lê a bateria do store que o laço alimenta."""
        from hefesto_dualsense4unix.daemon.state_store import StateStore
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import _game_rumble_mult

        bancada = montar(monkeypatch, 4)
        self._carga_no_p1(bancada, 75, 0x0)
        bancada.daemon.config = DaemonConfig(coop_enabled=True, rumble_policy="auto")
        bancada.daemon.store = StateStore()
        agora = 0.0

        def tique_do_laco() -> float:
            # O que o `_poll_loop` faz: publica o `read_state()` no store, e o
            # rumble do jogo (o de qualquer jogador) lê o degrau dali.
            bancada.daemon.store.update_controller_state(bancada.inst.read_state())
            return _game_rumble_mult(bancada.daemon, agora)  # type: ignore[arg-type]

        assert tique_do_laco() == 1.0
        bancada.mesa.levantar(P1)
        for _ in range(int(VINTE_SEGUNDOS / TIQUE)):
            bancada.tique()
            agora += TIQUE
            assert tique_do_laco() == 1.0, (
                "com o P1 fora, a vibração «auto» do P2, do P3 e do P4 caiu — "
                "o degrau leu a bateria 0 do posto vago"
            )


class TestOP1QueVoltaJogaNaHora:
    """O leitor do P1 reabre o nó assim que ele volta — não dorme no backoff.

    A conferência (24/09/2026) mediu com o `EvdevReader` de verdade (o open é
    dublê): antes da vaga, o leitor do P1 seguia o P2 e voltava ao P1 em 0,1 s,
    pelo `retarget`, que acorda o `select`. Com o posto vago, o leitor fica SEM
    nó e entra no backoff (0,5 → 1 → 2 → 4 → 5 s), e a espera do backoff era um
    `Event.wait` que nada acordava além do `stop()`: o P1 voltava, a lâmpada e a
    tela diziam 1, e o boneco 1 ficava parado por até 4,7 s. O mesmo valia para
    uma mesa de UM controle só.
    """

    def test_o_no_que_volta_acorda_o_leitor_em_backoff(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import errno
        import os
        import threading

        from hefesto_dualsense4unix.core import evdev_reader as er

        aberturas: list[float] = []
        nos: list[Any] = []

        class _No:
            """O nó de evdev: um pipe, para o `select` de verdade ter um fd."""

            def __init__(self) -> None:
                self.r, self.w = os.pipe()
                self.fd = self.r
                self.name = "dublê"

            def read(self) -> Any:
                os.read(self.r, 64)
                raise OSError(errno.ENODEV, "No such device")  # o nó sumiu

            def close(self) -> None:
                for fd in (self.r, self.w):
                    with contextlib.suppress(OSError):
                        os.close(fd)

            def capabilities(self, **_kw: Any) -> dict[Any, Any]:
                return {}

        def abrir(_path: Any, *_a: Any, **_kw: Any) -> _No:
            no = _No()
            nos.append(no)  # antes do carimbo: quem espera lê o carimbo
            aberturas.append(time.monotonic())
            return no

        monkeypatch.setattr(er, "abrir_input_device", abrir)
        sem_no = threading.Semaphore(0)

        class _Leitor(er.EvdevReader):
            no: Path | None = Path("/dev/input/event-dubl")

            def _locate(self) -> Path | None:
                if self.no is None:
                    sem_no.release()
                return self.no

            def _o_kernel_discorda(self, dev: Any, ecodes: Any) -> dict[str, Any]:
                return {}

        leitor = _Leitor(target_uniq=P1)
        try:
            assert leitor.start()
            limite = time.monotonic() + 5
            while not aberturas and time.monotonic() < limite:
                time.sleep(0.005)
            assert aberturas, "o leitor nem abriu o primeiro nó"
            leitor.no = None
            os.write(nos[0].w, b"x")
            # Três buscas sem nó: o leitor entrou na espera de 2 s do backoff.
            for _ in range(3):
                assert sem_no.acquire(timeout=10)
            leitor.no = Path("/dev/input/event-dubl")
            volta = time.monotonic()
            # O que o `_recompute_primary` faz quando o P1 retoma o posto.
            leitor.retarget(P1)
            leitor.refresh_device()
            leitor.start()
            while len(aberturas) < 2 and time.monotonic() - volta < 5:
                time.sleep(0.005)
            assert len(aberturas) == 2, "o leitor não reabriu o nó do P1"
            assert aberturas[1] - volta < 1.0, (
                f"o P1 voltou e o leitor dele levou {aberturas[1] - volta:.2f} s "
                "para reabrir o nó — o backoff não acordou"
            )
        finally:
            leitor.stop()
            for no in nos:
                no.close()
