"""O-BOTAO-DO-MIC-GRAVA-NO-PERFIL-01 — o botão do microfone vale depois de reconectar."""

from __future__ import annotations

import asyncio
import json
import types
from pathlib import Path
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.daemon import connection, lifecycle
from hefesto_dualsense4unix.daemon.lifecycle import INPUT_GRACE_SEC
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import hotkey, mic_da_mesa
from hefesto_dualsense4unix.daemon.subsystems.bt_mic import (
    BtMicSubsystem,
    RegistroDePedidosDeCanal,
)
from hefesto_dualsense4unix.integrations import eleicao_de_microfone as elm
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile
from hefesto_dualsense4unix.testing.fake_controller import FakeController
from hefesto_dualsense4unix.utils import maquina
from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

P1 = "aabbcc000011"
P2 = "aabbcc000022"
P3 = "aabbcc000033"
P4 = "aabbcc000044"
OS_QUATRO = (P1, P2, P3, P4)

FREESTYLE = "Freestyle"
JOGO = "Jogo"

ESPERA_DAS_GUARDAS_S: float = INPUT_GRACE_SEC + hotkey.MIC_SOSSEGO_S + 0.15


class _Resultado:
    def __init__(self, *, ok: bool, ativo: str | None = None, motivo: str = "") -> None:
        self.ok = ok
        self.ativo = ativo
        self.motivo = motivo


class _Eleitor:
    """`eleito` só passa a valer o `uniq` na eleição conferida, como o produto."""

    def __init__(self, *, elege_ok: bool = True) -> None:
        self.eleito: str | None = None
        self.fonte_do_eleito: str | None = None
        self._elege_ok = elege_ok

    def eleger_o_controle(self, uniq: str, conectados: list[str]) -> _Resultado:
        del conectados
        if not self._elege_ok:
            return _Resultado(ok=False, motivo="a bancada recusou de propósito")
        self.eleito = uniq
        self.fonte_do_eleito = f"hefesto_mic_{uniq[-6:]}"
        return _Resultado(ok=True, ativo=self.fonte_do_eleito)

    def devolver_o_microfone(self) -> _Resultado:
        self.eleito = None
        self.fonte_do_eleito = None
        return _Resultado(ok=True, ativo="mic_da_placa_mae")

    def passar_o_padrao(
        self, no_ar: list[str], conectados: list[str], calou: str | None = None
    ) -> _Resultado:
        """A pergunta de `EleitorDeMicrofone.passar_o_padrao`: quem está no ar,"""
        for candidato in no_ar:
            passado = self.eleger_o_controle(candidato, conectados)
            if passado.ok:
                return passado
        return self.devolver_o_microfone()

    def eleger_por_uniq(self, uniq: str, **_kw: Any) -> _Resultado:
        return self.eleger_o_controle(uniq, [])


class _Kernel(FakeController):  # type: ignore[misc]
    """O `hid-playstation` por trás de um `FakeController` de verdade."""

    def __init__(
        self, uniqs: tuple[str, ...] = (P4,), *, transportes: tuple[str, ...] = ()
    ) -> None:
        super().__init__()
        self.connect()
        self.uniqs = list(uniqs)
        self.transportes = dict(zip(uniqs, transportes or ("usb",) * len(uniqs), strict=False))
        self._kernel_mudo = dict.fromkeys(uniqs, False)
        self._firmware_mudo = dict.fromkeys(uniqs, False)
        self._seq = dict.fromkeys(uniqs, 0)
        self._pedido: dict[str, bool] = {}
        self._posse: dict[str, bool] = {}
        self.escritas_do_mudo: list[tuple[bool | None, str | None]] = []

    def apertar(self, uniq: str) -> None:
        """Todo aperto é UMA borda; a mão devolve a posse e o kernel escreve."""
        self._pedido[uniq] = not self._firmware_mudo[uniq]
        self._posse.pop(uniq, None)
        self._seq[uniq] += 1
        self._kernel_mudo[uniq] = not self._kernel_mudo[uniq]
        self._firmware_mudo[uniq] = self._kernel_mudo[uniq]

    def bordas_do_mic(self) -> dict[str, tuple[int, bool, float | None]]:
        return {
            u: (self._seq[u], self._pedido.get(u, self._firmware_mudo[u]), None)
            for u in self.uniqs
        }

    def audio_status_for(self, uniq: str | None = None) -> dict[str, bool] | None:
        uniq = norm_mac(str(uniq or "")) or uniq
        if uniq not in self._firmware_mudo:
            return None
        return {"fone_plugado": False, "mic_externo": False,
                "mic_mudo": self._firmware_mudo[uniq]}

    def set_microphone_mute(self, muted: bool | None, *, uniq: str | None = None) -> bool:
        uniq = norm_mac(str(uniq or "")) or uniq
        self.escritas_do_mudo.append((muted, uniq))
        if uniq not in self._firmware_mudo:
            return False
        if muted is None:
            self._posse.pop(uniq, None)
        else:
            self._posse[uniq] = bool(muted)
            self._firmware_mudo[uniq] = bool(muted)
            self._kernel_mudo[uniq] = bool(muted)
        return True

    def microphone_mute_for(self, uniq: str | None = None) -> bool | None:
        uniq = norm_mac(str(uniq or "")) or uniq
        return self._posse.get(str(uniq))

    def report(self, uniq: str) -> None:
        """O report seguinte do Hefesto: a posse que ficou vai ao firmware."""
        if uniq in self._posse:
            self._firmware_mudo[uniq] = self._posse[uniq]
            self._kernel_mudo[uniq] = self._posse[uniq]

    def set_mic_led(self, aceso: bool, *, uniq: str | None = None) -> None:
        self.mic_led_history.append(bool(aceso))

    def describe_controllers(self) -> list[dict[str, Any]]:
        return [{"uniq": u, "connected": True, "transport": self.transportes.get(u, "usb")}
                for u in self.uniqs]

    def alvos_conectados(self) -> dict[str, str | None]:
        return {f"hidraw{i}": u for i, u in enumerate(self.uniqs)}

    def mudo_no_firmware(self, uniq: str) -> bool:
        return self._firmware_mudo[uniq]

    def mudos_escritos(self, uniq: str) -> list[bool | None]:
        return [m for m, u in self.escritas_do_mudo if u == uniq]


class _Config:
    mic_button_toggles_system = True

    def __init__(self) -> None:
        self.bt_mic_recusados: Any = lambda: frozenset()


class _Daemon:
    """O daemon mínimo que os laços, o ato e o gancho de conexão tocam."""

    def __init__(self, backend: _Kernel, store: StateStore, eleitor: _Eleitor) -> None:
        self.bus = EventBus()
        self.config = _Config()
        self.controller = backend
        self.store = store
        self._eleitor_de_microfone = eleitor
        self._tasks: list[asyncio.Task[Any]] = []
        self._parando = False
        self.apply_profile_mic = types.MethodType(lifecycle.Daemon.apply_profile_mic, self)

    def _is_stopping(self) -> bool:
        return self._parando

    def is_paused(self) -> bool:
        return False

    def is_native_mode(self) -> bool:
        return False

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        await asyncio.sleep(0)
        return fn(*args)


@pytest.fixture
def casa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    profiles_dir(ensure=True)
    registro = RegistroDePedidosDeCanal()
    sub = BtMicSubsystem(registro=registro)
    monkeypatch.setattr(elm, "outra_captura_elegivel", lambda: None)
    anterior_pedidor = elm.registrar_pedidor_de_canal(sub.pedir_canal)
    anteriores = elm.registrar_dizedor_do_no_ar(
        sub.no_ar, sub.esquecer_a_palavra, sub.palavra_no_ar
    )
    monkeypatch.setattr(
        hotkey, "_ler_o_canal",
        lambda uniq: {"fonte": f"hefesto_mic_{uniq[-6:]}", "canal_ativo": False,
                      "canal_mudo": False, "volume_captura": 100},
    )
    hotkey._ECO_DO_ATO.clear()

    class Casa:
        subsystem = sub

        def perfil(self, nome: str, *, mic: dict[str, Any] | None = None,
                   por_peca: dict[str, Any] | None = None) -> None:
            dados: dict[str, Any] = {"name": nome, "match": MatchManual()}
            if mic is not None:
                dados["mic"] = {"button_toggles_system": True, **mic}
            if por_peca is not None:
                dados["controllers"] = por_peca
            loader.save_profile(Profile(**dados), origem="regua")

        def mic_no_disco(self, nome: str, uniq: str) -> dict[str, Any] | None:
            arquivo = profiles_dir() / f"{nome.lower()}.json"
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
            dele = (dados.get("controllers") or {}).get(uniq) or {}
            mic = dele.get("mic")
            return mic if isinstance(mic, dict) else None

        def calar_no_dono(self, *uniqs: str) -> None:
            """O calado que ela deu antes da cena, no dono (o `maquina.json`)."""
            for uniq in uniqs:
                assert maquina.gravar_o_mudo_do_microfone(uniq, True)

        def mudo_no_dono(self, uniq: str) -> bool | None:
            return maquina.mudo_do_microfone(uniq)

        def daemon(self, uniqs: tuple[str, ...] = (P4,), *, ativo: str = FREESTYLE,
                   store: StateStore | None = None, elege_ok: bool = True,
                   transportes: tuple[str, ...] = ()) -> _Daemon:
            if store is None:
                store = StateStore()
                store.set_active_profile(ativo)
            d = _Daemon(_Kernel(uniqs, transportes=transportes), store, _Eleitor(elege_ok=elege_ok))
            sub._config = d.config
            return d

    try:
        yield Casa()
    finally:
        hotkey._ECO_DO_ATO.clear()
        elm.registrar_pedidor_de_canal(anterior_pedidor)
        elm.registrar_dizedor_do_no_ar(*anteriores)


async def _drenar(segundos: float) -> None:
    fim = asyncio.get_running_loop().time() + segundos
    while asyncio.get_running_loop().time() < fim:
        await asyncio.sleep(0.01)


async def _apertar(daemon: _Daemon, *uniqs: str) -> None:
    """Os dois laços do produto no ar, as guardas vencidas, e os apertos dela."""
    consumidor = asyncio.create_task(hotkey.mic_button_loop(daemon))
    for _ in range(40):
        await asyncio.sleep(0.005)
        if daemon.bus.subscriber_count(EventTopic.MIC_DA_MESA):
            break
    assert daemon.bus.subscriber_count(EventTopic.MIC_DA_MESA) == 1, "a cena mediria o vazio"
    bordas = asyncio.create_task(mic_da_mesa.mic_da_mesa_loop(daemon))
    try:
        await _drenar(ESPERA_DAS_GUARDAS_S)
        for uniq in uniqs:
            daemon.controller.apertar(uniq)
            await _drenar(0.4)
        await _drenar(0.3)
    finally:
        daemon._parando = True
        tarefas = [bordas, consumidor, *daemon._tasks]
        for t in tarefas:
            t.cancel()
        await asyncio.gather(*tarefas, return_exceptions=True)
        daemon._parando = False
        daemon._tasks.clear()


async def _reconectar(daemon: _Daemon, uniq: str) -> bool:
    """O controle volta: firmware ABERTO, posse do kernel, e os dois ganchos REAIS."""
    daemon.controller._firmware_mudo[uniq] = False
    daemon.controller._kernel_mudo[uniq] = False
    daemon.controller._posse.pop(uniq, None)
    await connection.reapply_mic_after_connect(daemon, uniq=uniq)
    return bool(await hotkey.nascer_no_ar(daemon, uniq))


async def _derrubar(daemon: _Daemon) -> None:
    """Cancela e espera as tarefas que o ato pendurou (a devolução da posse)."""
    for t in daemon._tasks:
        t.cancel()
    await asyncio.gather(*daemon._tasks, return_exceptions=True)
    daemon._tasks.clear()


def _reiniciar(casa: Any, uniqs: tuple[str, ...] = (P4,)) -> _Daemon:
    """O restart do install: daemon, sessão e aparelho novos; o disco é o mesmo."""
    novo: _Daemon = casa.daemon(uniqs, ativo=FREESTYLE)
    return novo


def _ativar(daemon: _Daemon, nome: str, *, origin: str) -> None:
    """A troca de perfil pelo `ProfileManager.activate` REAL, como o daemon."""
    ProfileManager(
        controller=daemon.controller, store=daemon.store,
        mic_applier=daemon.apply_profile_mic,
    ).activate(nome, origin=origin)


class TestOBotaoLigaEODonoGuarda:
    @pytest.mark.asyncio
    async def test_o_botao_grava_o_ligado_no_dono(self, casa: Any) -> None:
        """A cena de 17:19:55. MORDIDA: arrancar a gravação do ato."""
        casa.perfil(FREESTYLE)
        casa.calar_no_dono(P4)
        daemon = casa.daemon()
        assert await _reconectar(daemon, P4) is False
        assert daemon.controller.mudo_no_firmware(P4) is True

        await _apertar(daemon, P4)

        assert daemon.controller.mudo_no_firmware(P4) is False, "a cena não ligou"
        assert casa.mudo_no_dono(P4) is False, (
            "o botão ligou o microfone e o dono continuou dizendo mudo — a "
            "reconexão seguinte o cala de novo, que é o achado de 25/09"
        )

    @pytest.mark.asyncio
    async def test_a_reconexao_e_o_restart_deixam_ligado(self, casa: Any) -> None:
        """O restart de 18:08:02, e o replug de 23h59, 09h32 e 09h56."""
        casa.perfil(FREESTYLE)
        casa.calar_no_dono(P4)
        daemon = casa.daemon()
        assert await _reconectar(daemon, P4) is False
        await _apertar(daemon, P4)
        daemon.controller.escritas_do_mudo.clear()

        assert await _reconectar(daemon, P4) is True, "o replug calou o P4"
        assert True not in daemon.controller.mudos_escritos(P4), (
            "o replug escreveu o mudo no firmware do P4 que ela tinha ligado"
        )

        novo = _reiniciar(casa)
        with structlog.testing.capture_logs() as registros:
            assert await _reconectar(novo, P4) is True
        assert novo.controller.mudos_escritos(P4) == []
        assert not [r for r in registros if r["event"] == "mic_nasce_calado_pelo_controle"], (
            "o restart disse `mic_nasce_calado_pelo_controle` depois de ela ligar"
        )

    @pytest.mark.asyncio
    async def test_o_contrario_calar_tambem_grava_e_vale(self, casa: Any) -> None:
        """Nos dois sentidos: o P4 no ar, o botão cala, o restart segue calado."""
        casa.perfil(FREESTYLE)
        daemon = casa.daemon()
        assert await hotkey.nascer_no_ar(daemon, P4) is True

        await _apertar(daemon, P4)

        assert daemon.controller.mudo_no_firmware(P4) is True, "a cena não calou"
        assert casa.mudo_no_dono(P4) is True, (
            "o botão calou e o dono não guardou — a reconexão abriria o "
            "microfone de quem pediu silêncio"
        )
        assert loader.load_profile(FREESTYLE).controllers is None, (
            "o ato gravou o mudo no perfil — o mudo é do controle"
        )
        novo = _reiniciar(casa)
        with structlog.testing.capture_logs() as registros:
            assert await _reconectar(novo, P4) is False, "o restart pôs no ar quem ela calou"
        assert novo.controller.mudos_escritos(P4) == [True], (
            "o replug não devolveu o mudo ao firmware que volta aberto"
        )
        assert [r for r in registros if r["event"] == "mic_nasce_calado_pelo_controle"]


class TestOsQuatro:
    @pytest.mark.asyncio
    async def test_os_quatro_ligam_e_os_quatro_calam(self, casa: Any) -> None:
        """Cabo e rádio, os quatro jogadores: cada botão grava o SEU controle."""
        casa.perfil(FREESTYLE)
        casa.calar_no_dono(*OS_QUATRO)
        transportes = ("usb", "bt", "usb", "bt")
        daemon = casa.daemon(OS_QUATRO, transportes=transportes)
        for u in OS_QUATRO:
            assert await _reconectar(daemon, u) is False, f"o {u} não nasceu calado"

        await _apertar(daemon, *OS_QUATRO)

        for u in OS_QUATRO:
            assert casa.mudo_no_dono(u) is False, f"o botão do {u} não gravou no dono"
        novo = casa.daemon(OS_QUATRO, transportes=transportes)
        for u in OS_QUATRO:
            assert await _reconectar(novo, u) is True, f"o restart calou o {u}"
        assert all(m is not True for m, _u in novo.controller.escritas_do_mudo)

        await _apertar(novo, *OS_QUATRO)

        for u in OS_QUATRO:
            assert casa.mudo_no_dono(u) is True, f"o calar do {u} não gravou no dono"
        terceiro = casa.daemon(OS_QUATRO, transportes=transportes)
        for u in OS_QUATRO:
            assert await _reconectar(terceiro, u) is False, f"o restart abriu o {u}"


class TestUmaMetadeDePeBasta:
    """O ato vai ao dono quando UMA das metades ficou de pé."""

    @pytest.mark.asyncio
    async def test_o_radio_que_recusa_o_canal_nao_impede_o_dono(self, casa: Any) -> None:
        """O desfecho COMUM por rádio: a ponte ainda não publicou o canal."""
        casa.perfil(FREESTYLE)
        casa.calar_no_dono(P4)
        daemon = casa.daemon(elege_ok=False, transportes=("bt",))
        assert await _reconectar(daemon, P4) is False

        await _apertar(daemon, P4)

        assert daemon.controller.mudo_no_firmware(P4) is False, "a cena não ligou"
        assert casa.mudo_no_dono(P4) is False, (
            "o canal recusado pelo rádio impediu o dono de guardar o ligado"
        )
        novo = casa.daemon(transportes=("bt",))
        assert await _reconectar(novo, P4) is True, "o restart calou o P4"
        assert novo.controller.mudos_escritos(P4) == []

    @pytest.mark.asyncio
    async def test_calar_com_o_canal_recusado_grava_o_silencio(self, casa: Any) -> None:
        """O 🎙 cala quem não está no ar: o canal recusa, o firmware obedece."""
        casa.perfil(FREESTYLE)
        daemon = casa.daemon()

        ato = await hotkey.ligar_o_microfone(daemon, P4, ligado=False)
        await _derrubar(daemon)

        assert not ato.canal_no_sistema.feita and ato.firmware.feita, (
            "a cena não é a de uma metade só"
        )
        assert casa.mudo_no_dono(P4) is True, "o calar com o canal recusado não foi ao dono"
        novo = _reiniciar(casa)
        assert await _reconectar(novo, P4) is False, "o restart pôs no ar quem ela calou"
        assert novo.controller.mudos_escritos(P4) == [True]


class TestOCalarDoDonoSemPerfil:
    @pytest.mark.asyncio
    async def test_o_calar_do_dono_chega_ao_firmware_sem_perfil_legivel(
        self, casa: Any
    ) -> None:
        """O ativo não carrega (apagado, ilegível): o calado dela ainda vale."""
        daemon = casa.daemon(ativo="Sumiu")
        ato = await hotkey.ligar_o_microfone(daemon, P4, ligado=False)
        await _derrubar(daemon)
        assert ato.firmware.feita and casa.mudo_no_dono(P4) is True
        daemon.controller.escritas_do_mudo.clear()

        assert await _reconectar(daemon, P4) is False
        assert daemon.controller.mudos_escritos(P4) == [True], (
            "o replug deixou o firmware aberto sobre o silêncio do dono"
        )

    def test_o_dono_casa_o_mac_com_dois_pontos(self, casa: Any) -> None:
        """A tela manda `aa:bb:…`; o dono guarda 12 hex. MORDIDA: ler cru."""
        casa.calar_no_dono(P4)
        m = ProfileManager(controller=object(), store=StateStore())

        assert m.o_controle_pede_silencio("aa:bb:cc:00:00:44") is True
        assert m.o_controle_pede_silencio(P3) is False, "quem nunca disse nasce no ar"


class TestOMudoDoPerfilNaoFalaNoReplug:
    def _applier(self) -> tuple[list[dict[str, Any]], Any]:
        chamadas: list[dict[str, Any]] = []

        def applier(volume: Any, muted: Any, *, uniq: Any = None, origin: str = "") -> str:
            chamadas.append({"volume": volume, "muted": muted, "uniq": uniq})
            return "aplicado"

        return chamadas, applier

    def test_o_global_calado_de_um_perfil_nao_cala_o_controle(self, casa: Any) -> None:
        """O `pragmata.json` dela tinha `mic.muted: true` no global."""
        casa.perfil(FREESTYLE, mic={"muted": True, "volume": 70})
        chamadas, applier = self._applier()
        store = StateStore()
        store.set_active_profile(FREESTYLE)
        m = ProfileManager(controller=object(), store=store, mic_applier=applier)

        assert m.o_controle_pede_silencio(P4) is False
        m.reapply_mic_on_connect(P4)

        assert [c["muted"] for c in chamadas if c["muted"] is not None] == [], (
            "o replug calou o controle pelo mudo que o perfil ainda carrega"
        )
        assert chamadas and chamadas[0]["volume"] == 70, "o volume do global sumiu"

    def test_a_peca_do_perfil_nao_vence_o_dono(self, casa: Any) -> None:
        """O perfil diz a peça no ar; o dono diz calado: vale o dono."""
        casa.perfil(FREESTYLE, por_peca={P4: {"mic": {"muted": False}}})
        casa.calar_no_dono(P4)
        chamadas, applier = self._applier()
        store = StateStore()
        store.set_active_profile(FREESTYLE)
        m = ProfileManager(controller=object(), store=store, mic_applier=applier)

        m.reapply_mic_on_connect(P4)

        assert [c["muted"] for c in chamadas] == [True], (
            "o replug deixou o firmware aberto sobre o calado do dono"
        )


class TestOAtoDaTelaGravaPeloMesmoCaminho:
    @pytest.mark.asyncio
    async def test_o_mic_canal_set_grava_como_o_botao(self, casa: Any) -> None:
        """O 🎙 chega pelo `mic.canal.set`, que é `ligar_o_microfone` — o mesmo ato."""
        casa.perfil(FREESTYLE)
        casa.calar_no_dono(P4)
        daemon = casa.daemon()
        daemon.controller._firmware_mudo[P4] = True

        ato = await hotkey.ligar_o_microfone(daemon, "aa:bb:cc:00:00:44", ligado=True)
        await _derrubar(daemon)

        assert ato.feito
        assert casa.mudo_no_dono(P4) is False

    @pytest.mark.asyncio
    async def test_o_ato_em_que_nada_ficou_de_pe_nao_vai_ao_dono(
        self, casa: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """As duas metades recusadas: o arquivo não diz o que o aparelho não teve."""
        casa.perfil(FREESTYLE)
        casa.calar_no_dono(P4)
        daemon = casa.daemon(elege_ok=False)
        daemon.controller._firmware_mudo[P4] = True
        monkeypatch.setattr(daemon.controller, "set_microphone_mute",
                            lambda muted, *, uniq=None: False)

        ato = await hotkey.ligar_o_microfone(daemon, P4, ligado=True)

        assert not ato.canal_no_sistema.feita and not ato.firmware.feita
        assert casa.mudo_no_dono(P4) is True

    @pytest.mark.asyncio
    async def test_o_vpad_nao_e_controle_e_nao_grava(self, casa: Any) -> None:
        casa.perfil(FREESTYLE)
        vpad = "02fe00000001"
        daemon = casa.daemon((vpad,))

        await hotkey.ligar_o_microfone(daemon, vpad, ligado=False)
        await _derrubar(daemon)

        assert maquina.carregar_maquina().controles == {}
        assert loader.load_profile(FREESTYLE).controllers is None

