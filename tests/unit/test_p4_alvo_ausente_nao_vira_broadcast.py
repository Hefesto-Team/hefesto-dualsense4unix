"""P4 (23/08/2026) — alvo que saiu da mesa NÃO vira "todos".

O defeito, medido: ela mira o Controle 2 no cabeçalho, o Controle 2 desliga
(bateria, botão PS, rádio), e o próximo gesto de output — vibração, cor,
gatilho, LED de jogador — caía no **broadcast histórico**. Em co-op, que nesta
casa é sempre ligado, isso é a mão de OUTRA pessoa sacudindo no meio da
partida; e como o rumble tem reassert de 5 Hz, um clique vira um defeito
contínuo até alguém apertar "Parar".

A causa era uma condição copiada em três helpers de
`core/backend_pydualsense.py` (`_for_each`, `_for_each_com_key`,
`_for_each_led`), cujo `else` fundia dois casos de destino OPOSTO: *"o alvo é
Todos"* (broadcast pedido) e *"o alvo sumiu"* (broadcast NUNCA pedido). A cura
é `_resolver_escopo`, que separa os dois e devolve o terceiro caso —
`alvo_ausente` — com lista de handles VAZIA.

**O backend é REAL aqui**, e tem de ser: o defeito mora na resolução de alvo
do `PyDualSenseController`. O que é dublê são os handles (motores e cores
viram lista), no mesmo molde de `test_mesa_cheia_05_o_rumble_mira.py`, com os
quatro MACs do fixture versionado `state_full_quatro_controles.json`.

**A mordida:** devolver o `else` de antes nos três helpers (isto é, fazer
`_resolver_escopo` cair em `list(self._handles.items())` quando o alvo
está ausente) tem de reprovar as classes `TestOExemplar`, `TestAInsistencia` e
`TestOsOutrosSetores`, e NÃO pode reprovar `TestAMiraContinuaMirando` nem
`TestOBroadcastLegitimoContinua` — que existem exatamente para a cura não
virar "nunca manda nada".

**BROADCAST-PROIBIDO-01 (Z3-6/Z3-7, 24/08/2026)**: o aceite da §0.2 pede um
teste por família — rumble, gatilho e lightbar. Gatilho faltava
(`TestOsOutrosSetores.test_o_gatilho_nao_vai_para_os_outros`, abaixo) mesmo
`set_trigger` já passando pelo `_for_each` curado — "curado e sem rede" é
exatamente o que um refactor futuro quebra em silêncio. E a rota do JOGO
(`apply_game_rumble`, `daemon.subsystems.gamepad`) não tinha contra-classe
NENHUMA com o backend REAL — só com dublê de backend
(`test_vpad_ff_passthrough.py`), que já provou poder passar verde sem tocar o
código que diz medir (§2.1(c) da sprint). `TestAReplicaDoJogoContinuaChegando`
é a segunda régua, independente, sobre o mesmo comportamento.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
from hefesto_dualsense4unix.core.trigger_effects import rigid
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems.gamepad import apply_game_rumble
from hefesto_dualsense4unix.daemon.subsystems.rumble import reassert_rumble
from hefesto_dualsense4unix.profiles.manager import ProfileManager

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "state_full_quatro_controles.json"
)


def _uniqs_da_mesa_cheia() -> list[str]:
    """Os quatro MACs medidos em 14/08 — dois USB, dois BT."""
    dados = json.loads(FIXTURE.read_text(encoding="utf-8"))
    uniqs = [c["uniq"] for c in dados["controllers"]]
    assert len(uniqs) == 4, "a mesa cheia tem quatro; o fixture mudou"
    return uniqs


def _key_de(uniq: str) -> str:
    """A key do handle no formato MAC que o backend normaliza de volta."""
    return ":".join(uniq[i : i + 2] for i in range(0, 12, 2)).upper()


class _FakeLight:
    def __init__(self) -> None:
        self.colors: list[tuple[int, int, int]] = []

    def setColorI(self, r: int, g: int, b: int) -> None:  # noqa: N802 — API pydualsense
        self.colors.append((r, g, b))


class _FakeTrigger:
    """Gatilho mínimo: `mode`/`forces`, no mesmo par que `_apply_trigger`
    grava no handle real (`trigger.mode = ...`, `trigger.setForce(idx, v)`)."""

    def __init__(self) -> None:
        self.mode: object | None = None
        self.forces: list[int] = []

    def setForce(self, idx: int, value: int) -> None:  # noqa: N802 — API pydualsense
        self.forces.append(value)


class _FakeHandle:
    """Handle mínimo: motores, cor, LED de mic e gatilhos viram listas."""

    def __init__(self) -> None:
        self.connected = True
        self.conType = type("CT", (), {"name": "USB"})()
        self.motors: list[tuple[str, int]] = []
        self.light = _FakeLight()
        self.mic: list[bool] = []
        self.audio = SimpleNamespace(setMicrophoneLED=self.mic.append)
        self.triggerL = _FakeTrigger()
        self.triggerR = _FakeTrigger()

    def setLeftMotor(self, intensity: int) -> None:  # noqa: N802 — API pydualsense
        self.motors.append(("left", intensity))

    def setRightMotor(self, intensity: int) -> None:  # noqa: N802 — API pydualsense
        self.motors.append(("right", intensity))


def _null_evdev() -> EvdevReader:
    reader = EvdevReader(device_path=None)
    reader._device_path = None
    return reader


class _Mesa:
    """A mesa cheia montada: backend real, quatro handles, um IpcServer real."""

    def __init__(self, tmp_path: Path) -> None:
        self.uniqs = _uniqs_da_mesa_cheia()
        self.backend = PyDualSenseController(evdev_reader=_null_evdev())
        self.handles = {u: _FakeHandle() for u in self.uniqs}
        self.backend._handles = {  # type: ignore[assignment]
            _key_de(u): h for u, h in self.handles.items()
        }
        self.backend._primary_key = _key_de(self.uniqs[0])

        self.store = StateStore()
        self.store.update_controller_state(
            ControllerState(
                battery_pct=100, l2_raw=0, r2_raw=0, connected=True, transport="usb"
            )
        )
        self.config = DaemonConfig()
        # "balanceado" = 1,0: a política não entra na conta e o que sai do
        # motor é o que ela pediu.
        self.config.rumble_policy = "balanceado"

        self.daemon = MagicMock()
        self.daemon.config = self.config
        self.daemon.store = self.store
        self.daemon.controller = self.backend
        self.daemon._rumble_engine = None
        self.daemon._last_auto_mult = 1.0
        self.daemon._last_auto_change_at = 0.0

        self.server = IpcServer(
            controller=self.backend,
            store=self.store,
            profile_manager=ProfileManager(controller=self.backend, store=self.store),
            socket_path=tmp_path / "p4_alvo_ausente.sock",
            daemon=self.daemon,
        )

    def indice_de(self, uniq: str) -> int:
        return self.uniqs.index(uniq)

    def motores_de(self, uniq: str) -> list[tuple[str, int]]:
        return self.handles[uniq].motors

    def cores_de(self, uniq: str) -> list[tuple[int, int, int]]:
        return self.handles[uniq].light.colors

    def desligar(self, uniq: str) -> None:
        """O Controle sai da mesa (hotplug-out simplificado, como o vizinho)."""
        del self.backend._handles[_key_de(uniq)]

    def limpar(self) -> None:
        for handle in self.handles.values():
            handle.motors.clear()
            handle.light.colors.clear()
            handle.mic.clear()
            handle.triggerL.forces.clear()
            handle.triggerR.forces.clear()

    def ticks(self, quantos: int = 3) -> None:
        for i in range(quantos):
            reassert_rumble(self.daemon, float(i))

    def quem_recebeu_motor(self) -> dict[str, list[tuple[str, int]]]:
        return {u: h.motors for u, h in self.handles.items() if h.motors}

    def gatilho_tocou(self, uniq: str) -> bool:
        """True quando ALGUM force chegou em qualquer lado do gatilho deste
        controle — o mesmo teto de verdade do `_apply_trigger` real."""
        h = self.handles[uniq]
        return bool(h.triggerL.forces) or bool(h.triggerR.forces)


@pytest.fixture
def mesa(tmp_path: Path) -> _Mesa:
    return _Mesa(tmp_path)


class TestOExemplar:
    """O gesto medido: mira o 2, o 2 desliga, ela clica "Testar"."""

    @pytest.mark.asyncio
    async def test_o_rumble_nao_vai_para_os_outros_tres(self, mesa: _Mesa) -> None:
        dois = mesa.uniqs[1]
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        mesa.desligar(dois)
        mesa.limpar()

        await mesa.server._handle_rumble_set({"weak": 160, "strong": 220})

        recebeu = mesa.quem_recebeu_motor()
        assert recebeu == {}, (
            "o alvo saiu da mesa e a vibração foi para quem ficou — em co-op "
            f"isso é a mão de outra pessoa. Receberam: {recebeu}"
        )

    def test_o_backend_sabe_dizer_que_o_alvo_sumiu(self, mesa: _Mesa) -> None:
        """A metade "e DIZ" da regra: o estado é consultável, não mascarado.

        `get_output_target_index`/`get_output_target_uniq` devolvem `None`
        tanto para "Todos" quanto para "alvo sumiu" — quem precisa responder
        *"o Controle 2 não está na mesa, nada foi enviado"* não consegue
        separar os dois por ali. `alvo_de_output_ausente` separa.
        """
        dois = mesa.uniqs[1]
        mesa.backend.set_output_target(mesa.indice_de(dois))
        assert mesa.backend.alvo_de_output_ausente() is None  # presente
        mesa.desligar(dois)
        assert mesa.backend.alvo_de_output_ausente() == dois
        # "Todos" nunca é ausência de destinatário.
        mesa.backend.set_output_target(None)
        assert mesa.backend.alvo_de_output_ausente() is None


class TestAInsistencia:
    """Um clique não pode virar defeito contínuo: o reassert de 5 Hz."""

    @pytest.mark.asyncio
    async def test_tres_reasserts_depois_continua_ninguem(self, mesa: _Mesa) -> None:
        dois = mesa.uniqs[1]
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        mesa.desligar(dois)
        mesa.limpar()

        await mesa.server._handle_rumble_set({"weak": 160, "strong": 220})
        mesa.limpar()
        mesa.ticks(3)

        recebeu = mesa.quem_recebeu_motor()
        assert recebeu == {}, (
            "o clique virou insistência: o poll loop repinta o valor de um "
            f"controle ausente nos presentes a cada tick. Receberam: {recebeu}"
        )


class TestOsOutrosSetores:
    """A mesma condição estava copiada em `_for_each` e `_for_each_led`."""

    def test_a_cor_nao_vai_para_os_outros(self, mesa: _Mesa) -> None:
        dois = mesa.uniqs[1]
        mesa.backend.set_output_target(mesa.indice_de(dois))
        mesa.desligar(dois)
        mesa.limpar()

        mesa.backend.set_led((0, 255, 0))

        pintados = {u: c for u, c in ((x, mesa.cores_de(x)) for x in mesa.uniqs) if c}
        assert pintados == {}, f"a barra dos outros mudou de cor: {pintados}"

    def test_o_led_do_mic_nao_vai_para_os_outros(self, mesa: _Mesa) -> None:
        dois = mesa.uniqs[1]
        mesa.backend.set_output_target(mesa.indice_de(dois))
        mesa.desligar(dois)
        mesa.limpar()

        mesa.backend.set_mic_led(True)

        acesos = {u: h.mic for u, h in mesa.handles.items() if h.mic}
        assert acesos == {}, f"o LED de mic dos outros mudou: {acesos}"

    def test_o_gatilho_nao_vai_para_os_outros(self, mesa: _Mesa) -> None:
        """Z3-6: a terceira família do aceite (§0.2) — faltava gatilho.

        `set_trigger` passa pelo `_for_each` (já curado pelo F4) e por isso
        NÃO tinha rede: um refactor que reintroduzisse o `else` histórico só
        aqui não reprovaria nada, porque nenhum teste chamava `set_trigger`
        com o alvo ausente.
        """
        dois = mesa.uniqs[1]
        mesa.backend.set_output_target(mesa.indice_de(dois))
        mesa.desligar(dois)
        mesa.limpar()

        mesa.backend.set_trigger("left", rigid(0, 128))

        tocaram = {u for u in mesa.uniqs if mesa.gatilho_tocou(u)}
        assert tocaram == set(), f"o gatilho dos outros mexeu: {tocaram}"

    def test_o_valor_fica_guardado_no_alvo_que_voltou(self, mesa: _Mesa) -> None:
        """Não escrever não é esquecer: o campo vira override POR-UNIQ dele.

        É a palavra que a casa já usa (`"registrado"` de `apply_output_for`):
        *guardado — vai valer quando o Controle 2 voltar*. O defeito antigo
        gravava no DEFAULT do perfil (porque zerava o `target` antes do
        `record`), então o valor mirado num ausente virava o padrão de TODOS.
        """
        um, dois = mesa.uniqs[0], mesa.uniqs[1]
        mesa.backend.set_output_target(mesa.indice_de(dois))
        mesa.desligar(dois)

        mesa.backend.set_led((0, 255, 0))

        assert mesa.backend._desired_by_uniq[dois].led == (0, 255, 0)
        assert mesa.backend._desired_default.led != (0, 255, 0), (
            "a cor mirada num controle ausente virou o PADRÃO do perfil"
        )
        assert um not in mesa.backend._desired_by_uniq


class TestAMiraContinuaMirando:
    """Controle positivo: com o alvo PRESENTE, nada mudou."""

    @pytest.mark.asyncio
    async def test_rumble_chega_no_alvo_e_so_nele(self, mesa: _Mesa) -> None:
        dois = mesa.uniqs[1]
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        mesa.limpar()

        await mesa.server._handle_rumble_set({"weak": 160, "strong": 220})

        assert mesa.motores_de(dois) == [("left", 220), ("right", 160)]
        for outro in mesa.uniqs:
            if outro == dois:
                continue
            assert mesa.motores_de(outro) == [], f"{outro} recebeu sem ser o alvo"

    def test_cor_chega_no_alvo_e_so_nele(self, mesa: _Mesa) -> None:
        tres = mesa.uniqs[2]
        mesa.backend.set_output_target(mesa.indice_de(tres))
        mesa.limpar()

        mesa.backend.set_led((9, 9, 9))

        assert mesa.cores_de(tres) == [(9, 9, 9)]
        for outro in mesa.uniqs:
            if outro == tres:
                continue
            assert mesa.cores_de(outro) == [], f"{outro} foi pintado sem ser o alvo"


class TestOBroadcastLegitimoContinua:
    """Controle do caminho feliz: "Todos" continua sendo todos.

    Sem esta classe, "nunca mandar nada" passaria na mordida — e a hipótese
    tem de explicar o que JÁ funcionava.
    """

    @pytest.mark.asyncio
    async def test_sem_alvo_o_rumble_vai_para_os_quatro(self, mesa: _Mesa) -> None:
        await mesa.server._handle_controller_target_set({"index": None})
        mesa.limpar()

        await mesa.server._handle_rumble_set({"weak": 160, "strong": 220})

        for u in mesa.uniqs:
            assert mesa.motores_de(u) == [("left", 220), ("right", 160)], (
                f'"Todos" deixou {u} de fora'
            )

    def test_sem_alvo_a_cor_vai_para_os_quatro(self, mesa: _Mesa) -> None:
        mesa.backend.set_output_target(None)
        mesa.limpar()

        mesa.backend.set_led((1, 2, 3))

        for u in mesa.uniqs:
            assert mesa.cores_de(u) == [(1, 2, 3)], f'"Todos" deixou {u} de fora'

    def test_o_perfil_continua_ignorando_o_seletor(self, mesa: _Mesa) -> None:
        """PERFIL-01: `broadcast=True` passa por cima do alvo, presente ou não.

        Ativar perfil com um alvo AUSENTE no seletor não pode virar no-op —
        seria trocar um defeito por outro (o perfil deixaria de pintar a mesa).
        """
        from hefesto_dualsense4unix.core.backend_pydualsense import OutputSpec

        dois = mesa.uniqs[1]
        mesa.backend.set_output_target(mesa.indice_de(dois))
        mesa.desligar(dois)
        mesa.limpar()

        mesa.backend.apply_output_defaults(OutputSpec(led=(4, 5, 6)))

        for u in mesa.uniqs:
            if u == dois:
                continue
            assert mesa.cores_de(u) == [(4, 5, 6)], f"o perfil não pintou {u}"


class TestAReplicaDoJogoContinuaChegando:
    """Z3-7: contra-classe da rota do JOGO, com o backend REAL.

    O teste de A (`test_vpad_ff_passthrough.py`) usa dublê de BACKEND
    (`_FakeBackend`) — e o §2.1(c) desta sprint já mediu que um dublê pode
    passar verde sem tocar o código que diz medir (o `daemon = MagicMock()`
    cujo `is_native_mode()` mentia verdadeiro). Esta classe usa o backend
    REAL (`PyDualSenseController`) com handles de dublê — a MESMA régua do
    resto deste arquivo — para provar, por uma via independente, que
    `apply_game_rumble` continua entregando a réplica do jogo ao motor certo
    depois de Z3-1 parar de degradar para broadcast.
    """

    def test_mac_casado_vai_so_naquele_motor(self, mesa: _Mesa) -> None:
        tres = mesa.uniqs[2]
        mesa.limpar()

        efetivo = apply_game_rumble(mesa.daemon, 200, 180, target_uniq=tres)

        assert efetivo == (200, 180)
        assert mesa.motores_de(tres) == [("left", 180), ("right", 200)]
        for outro in mesa.uniqs:
            if outro == tres:
                continue
            assert mesa.motores_de(outro) == [], (
                f"{outro} recebeu a réplica do jogo sem ser o alvo dela"
            )

    def test_mesa_de_um_controle_so_continua_vibrando(self, mesa: _Mesa) -> None:
        """Sem MAC pedido (`target_uniq=None`), broadcast e mira são a MESMA
        coisa numa mesa de um controle só — é a ressalva que Z3-1 fixou para
        a cura não virar "nunca vibra". A MORDIDA desta classe (§5 da
        sprint): arrancar a ressalva `target_uniq is None` de
        `apply_game_rumble` faz este teste reprovar dizendo que o produto
        parou de vibrar — provado em Z3-1/Z3-2, reproduzido aqui numa régua
        independente."""
        sobrevivente = mesa.uniqs[0]
        for outro in mesa.uniqs[1:]:
            mesa.desligar(outro)
        mesa.limpar()

        efetivo = apply_game_rumble(mesa.daemon, 100, 50, target_uniq=None)

        assert efetivo == (100, 50)
        assert mesa.motores_de(sobrevivente) == [("left", 50), ("right", 100)]


class TestOReleaseLedsAchaOAlvoPeloMac:
    """FORMA 4 do censo: mira que erra o FORMATO do endereço.

    `enviar_release_leds` indexava `self._handles` com o `uniq` 12-hex CRU,
    enquanto a key do handle é "AA:BB:CC:...". Para um controle CONECTADO a
    busca devolvia `{}` — que o docstring do método manda ler como "nenhum
    handle aberto, que é informação, não falha". Instrumento mentindo.
    """

    def test_uniq_12_hex_casa_o_handle(self, mesa: _Mesa, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        import hefesto_dualsense4unix.core.lightbar_reset as reset

        monkeypatch.setattr(reset, "send_release_leds", lambda handle: True)
        dois = mesa.uniqs[1]

        resultado = mesa.backend.enviar_release_leds(uniq=dois)

        assert resultado == {_key_de(dois): True}, (
            "o MAC 12-hex que o IPC repassa não casou o handle do controle "
            f"CONECTADO — devolveu {resultado}"
        )

    def test_key_no_formato_mac_continua_casando(
        self, mesa: _Mesa, monkeypatch  # type: ignore[no-untyped-def]
    ) -> None:
        import hefesto_dualsense4unix.core.lightbar_reset as reset

        monkeypatch.setattr(reset, "send_release_leds", lambda handle: True)
        key = _key_de(mesa.uniqs[1])

        assert mesa.backend.enviar_release_leds(uniq=key) == {key: True}

    def test_mac_de_quem_nao_esta_na_mesa_devolve_vazio(
        self, mesa: _Mesa, monkeypatch  # type: ignore[no-untyped-def]
    ) -> None:
        import hefesto_dualsense4unix.core.lightbar_reset as reset

        monkeypatch.setattr(reset, "send_release_leds", lambda handle: True)
        dois = mesa.uniqs[1]
        mesa.desligar(dois)

        assert mesa.backend.enviar_release_leds(uniq=dois) == {}
