"""O-BOTAO-DO-MIC-GRAVA-NO-PERFIL-01 — o botão do microfone vale depois de reconectar.

**O ACHADO, 25/09/2026**, de um agente de leitura, a pedido dela (*«to com a
sensação real que ele é o unico com o mic com algum problema»*). O P4 não tinha
defeito: o perfil Freestyle guardava ``mic.muted: true`` só para ele. Ela ligou o
microfone pelo botão do controle às 17:19:55 (``mic_ato … feito=True
ligado=True``), e o perfil continuou dizendo mudo; no restart do install, às
18:08:02, ele calou de novo — ``profile_mic_mute_applied muted=True
origin=replug`` e ``mic_nasce_calado_por_perfil``. O mesmo ciclo às 23h59, 09h32
e 09h56. A palavra dela: *«isso aqui deveriamos ter uma correção a nivel de
produto.»* <!-- noqa-acento: citação literal dela -->

A CENA É A DO PRODUTO, E NO TEMPO
------------------------------------------------------------------------------
Os dois laços do botão (`mic_da_mesa_loop` e `mic_button_loop`) sobem de
verdade, e o aperto nasce do toggle cego do `hid-playstation` — o molde da
régua MIC-FASE-01. O ato, o `ProfileManager`, o `loader` que grava o `.json`,
o gancho de conexão (`connection.reapply_mic_after_connect`), o applier do
daemon (`Daemon.apply_profile_mic`), o registro da ponte e o nascimento são os
REAIS. Dublês só onde está o aparelho (o kernel) e o PipeWire (o eleitor).

O QUE SE AFIRMA
------------------------------------------------------------------------------
1. o botão liga e o disco guarda; a reconexão e o restart deixam ligado — e o
   contrário, e para os quatro;
2. a troca AUTOMÁTICA de perfil não desfaz o ato na reconexão; a EXPLÍCITA
   vale, porque é ato dela;
3. o mudo da peça vence o do global também no replug (dois leitores, um
   veredito);
4. o que se grava é o mesmo que o 🎙 da tela grava (`DraftConfig`);
5. o `mic_nasce_calado_por_perfil` só aparece quando o último ato foi calar.

A MORDIDA, arrancada uma a uma e medida (25/09/2026) — ver a seção
«O que foi feito» da sprint, e o `pendente` do relato.

Os endereços são da faixa FORJADA de fixture (`aa:bb:cc`), nunca da bancada dela.
"""

from __future__ import annotations

import asyncio
import json
import types
from pathlib import Path
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.app.draft_config import DraftConfig
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
from hefesto_dualsense4unix.profiles.manager import (
    ProfileManager,
    gravar_o_mic_no_perfil_ativo,
)
from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile
from hefesto_dualsense4unix.testing.fake_controller import FakeController
from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

P1 = "aabbcc000011"
P2 = "aabbcc000022"
P3 = "aabbcc000033"
P4 = "aabbcc000044"
OS_QUATRO = (P1, P2, P3, P4)

#: O perfil de fora do jogo (o que o boot restaura) e o de um jogo.
FREESTYLE = "Freestyle"
JOGO = "Jogo"

#: A espera que faz a cena medir o GESTO e não as guardas — a de MIC-FASE-01.
ESPERA_DAS_GUARDAS_S: float = INPUT_GRACE_SEC + hotkey.MIC_SOSSEGO_S + 0.15


# ---------------------------------------------------------------------------
# Os dublês — o do backend É O KERNEL, e o do eleitor tem o contrato do real
# ---------------------------------------------------------------------------


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

    def eleger_por_uniq(self, uniq: str, **_kw: Any) -> _Resultado:
        return self.eleger_o_controle(uniq, [])


class _Kernel(FakeController):  # type: ignore[misc]
    """O `hid-playstation` por trás de um `FakeController` de verdade.

    O botão alterna o estado DO KERNEL (``ds->mic_muted``) e ele manda o valor
    ao firmware; a borda que o produto vê é a mudança do bit no report — a
    consequência, não o aperto. A NOSSA escrita (`set_microphone_mute`) move o
    firmware sem contar borda, como o backend real, que engole o eco. O
    firmware nasce ABERTO a cada conexão: é a premissa do replug.

    É um `FakeController` de propósito: a troca de perfil desta régua é o
    `ProfileManager.activate` REAL, e ele fala com o backend inteiro.
    """

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
        #: Cada escrita do mudo que chegou ao aparelho, com endereço.
        self.escritas_do_mudo: list[tuple[bool | None, str | None]] = []

    def apertar(self, uniq: str) -> None:
        self._kernel_mudo[uniq] = not self._kernel_mudo[uniq]
        if self._firmware_mudo[uniq] != self._kernel_mudo[uniq]:
            self._firmware_mudo[uniq] = self._kernel_mudo[uniq]
            self._seq[uniq] += 1

    def bordas_do_mic(self) -> dict[str, tuple[int, bool, float | None]]:
        return {u: (self._seq[u], self._firmware_mudo[u], None) for u in self.uniqs}

    def audio_status_for(self, uniq: str | None = None) -> dict[str, bool] | None:
        # O MAC casa NORMALIZADO, como o `_handle_for` do backend real: a tela
        # manda `aa:bb:…` e o plástico `aabb…`.
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
        if muted is not None:
            self._firmware_mudo[uniq] = bool(muted)
            # A escrita com posse leva o firmware; o toggle seguinte do kernel
            # parte do valor que o aparelho mostra — é o que a borda de
            # `mudo=False` do journal dela às 17:19:55 prova.
            self._kernel_mudo[uniq] = bool(muted)
        return True

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
        #: A recusa do `maquina.json`, CHAMÁVEL, como o `lifecycle` a fia.
        self.bt_mic_recusados: Any = lambda: frozenset()


class _Daemon:
    """O daemon mínimo que os laços, o ato e o gancho de conexão tocam.

    **`_run_blocking` NÃO ACEITA KEYWORDS** — é a assinatura do real. O
    `apply_profile_mic` é o do `Daemon` REAL, amarrado a este objeto: é ele
    que o gancho de conexão injeta como `mic_applier`.
    """

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


# ---------------------------------------------------------------------------
# A casa: perfis num XDG só deste teste, e a ponte do microfone de verdade
# ---------------------------------------------------------------------------


@pytest.fixture
def casa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    profiles_dir(ensure=True)
    registro = RegistroDePedidosDeCanal()
    sub = BtMicSubsystem(registro=registro)
    # "Existe outro microfone na máquina?" é dublado no DONO: sem isto o
    # nascimento perguntaria ao `pactl` de quem roda a suíte.
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
    """O controle volta: firmware ABERTO, e os dois ganchos REAIS da conexão."""
    daemon.controller._firmware_mudo[uniq] = False
    daemon.controller._kernel_mudo[uniq] = False
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


# ===========================================================================
# 1. O ACHADO: o P4 calado no perfil, o botão liga, e ele segue ligado
# ===========================================================================


class TestOBotaoLigaEODiscoGuarda:
    @pytest.mark.asyncio
    async def test_o_botao_grava_o_ligado_no_perfil_ativo(self, casa: Any) -> None:
        """A cena de 17:19:55. MORDIDA: arrancar a gravação do ato."""
        casa.perfil(FREESTYLE, por_peca={P4: {"mic": {"muted": True}}})
        daemon = casa.daemon()
        # A conexão que abre a cena: o replug devolve o calado do perfil.
        assert await _reconectar(daemon, P4) is False
        assert daemon.controller.mudo_no_firmware(P4) is True

        await _apertar(daemon, P4)

        assert daemon.controller.mudo_no_firmware(P4) is False, "a cena não ligou"
        assert casa.mic_no_disco(FREESTYLE, P4) == {"muted": False}, (
            "o botão ligou o microfone e o perfil continuou dizendo mudo — a "
            "reconexão seguinte o cala de novo, que é o achado de 25/09"
        )

    @pytest.mark.asyncio
    async def test_a_reconexao_e_o_restart_deixam_ligado(self, casa: Any) -> None:
        """O restart de 18:08:02, e o replug de 23h59, 09h32 e 09h56."""
        casa.perfil(FREESTYLE, por_peca={P4: {"mic": {"muted": True}}})
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
        assert not [r for r in registros if r["event"] == "mic_nasce_calado_por_perfil"], (
            "o restart disse `mic_nasce_calado_por_perfil` depois de ela ligar"
        )

    @pytest.mark.asyncio
    async def test_o_contrario_calar_tambem_grava_e_vale(self, casa: Any) -> None:
        """Nos dois sentidos: o P4 no ar, o botão cala, o restart segue calado."""
        casa.perfil(FREESTYLE)
        daemon = casa.daemon()
        assert await hotkey.nascer_no_ar(daemon, P4) is True  # a cena começa no ar

        await _apertar(daemon, P4)

        assert daemon.controller.mudo_no_firmware(P4) is True, "a cena não calou"
        assert casa.mic_no_disco(FREESTYLE, P4) == {"muted": True}, (
            "o botão calou e o perfil não guardou — a reconexão abriria o "
            "microfone de quem pediu silêncio"
        )
        novo = _reiniciar(casa)
        with structlog.testing.capture_logs() as registros:
            assert await _reconectar(novo, P4) is False, "o restart pôs no ar quem ela calou"
        assert novo.controller.mudos_escritos(P4) == [True], (
            "o replug não devolveu o mudo ao firmware que volta aberto"
        )
        assert [r for r in registros if r["event"] == "mic_nasce_calado_por_perfil"]


class TestOsQuatro:
    @pytest.mark.asyncio
    async def test_os_quatro_ligam_e_os_quatro_calam(self, casa: Any) -> None:
        """Cabo e rádio, os quatro jogadores: cada botão grava a SUA peça."""
        calados = {u: {"mic": {"muted": True}} for u in OS_QUATRO}
        casa.perfil(FREESTYLE, por_peca=calados)
        transportes = ("usb", "bt", "usb", "bt")
        daemon = casa.daemon(OS_QUATRO, transportes=transportes)
        for u in OS_QUATRO:
            assert await _reconectar(daemon, u) is False, f"o {u} não nasceu calado"

        await _apertar(daemon, *OS_QUATRO)

        for u in OS_QUATRO:
            assert casa.mic_no_disco(FREESTYLE, u) == {"muted": False}, (
                f"o botão do {u} não gravou no perfil"
            )
        novo = casa.daemon(OS_QUATRO, transportes=transportes)
        for u in OS_QUATRO:
            assert await _reconectar(novo, u) is True, f"o restart calou o {u}"
        assert all(m is not True for m, _u in novo.controller.escritas_do_mudo)

        await _apertar(novo, *OS_QUATRO)

        for u in OS_QUATRO:
            assert casa.mic_no_disco(FREESTYLE, u) == {"muted": True}, (
                f"o calar do {u} não gravou no perfil"
            )
        terceiro = casa.daemon(OS_QUATRO, transportes=transportes)
        for u in OS_QUATRO:
            assert await _reconectar(terceiro, u) is False, f"o restart abriu o {u}"


# ===========================================================================
# 2. A TROCA DE PERFIL DEPOIS DO ATO
# ===========================================================================


class TestATrocaDePerfilDepois:
    @pytest.mark.asyncio
    async def test_a_troca_automatica_nao_desfaz_o_ato_na_reconexao(self, casa: Any) -> None:
        """O ato no Freestyle, o jogo abre, o rádio pisca: o P4 segue ligado.

        O perfil do jogo guarda um registro MAIS VELHO do P4 (calado). A troca
        automática não escreve o mudo (MIC-GRAVACAO-01) — mas a reconexão
        seguinte lia o perfil do jogo e desfazia o ato dela.

        MORDIDA: `_ato_da_sessao` devolvendo sempre `None`.
        """
        casa.perfil(FREESTYLE, por_peca={P4: {"mic": {"muted": True}}})
        casa.perfil(JOGO, por_peca={P4: {"mic": {"muted": True}}})
        daemon = casa.daemon()
        assert await _reconectar(daemon, P4) is False
        await _apertar(daemon, P4)
        assert daemon.controller.mudo_no_firmware(P4) is False, "a cena não ligou"
        daemon.controller.escritas_do_mudo.clear()

        _ativar(daemon, JOGO, origin="autoswitch")
        assert daemon.store.active_profile == JOGO
        assert daemon.controller.mudos_escritos(P4) == [], "a troca automática calou"

        assert await _reconectar(daemon, P4) is True, (
            "a reconexão sob o perfil do jogo desfez o ato dela no Freestyle"
        )
        assert True not in daemon.controller.mudos_escritos(P4)
        assert casa.mic_no_disco(JOGO, P4) == {"muted": True}, (
            "o ato reescreveu um perfil que não estava ativo"
        )

    @pytest.mark.asyncio
    async def test_a_troca_explicita_vale_porque_e_ato_dela(self, casa: Any) -> None:
        """Ela escolhe na mão o perfil que diz calado: ESSE é o último ato.

        MORDIDA: arrancar o `_esquecer_o_ato_da_sessao` do `apply_mic`.
        """
        casa.perfil(FREESTYLE, por_peca={P4: {"mic": {"muted": True}}})
        casa.perfil(JOGO, por_peca={P4: {"mic": {"muted": True}}})
        daemon = casa.daemon()
        assert await _reconectar(daemon, P4) is False
        await _apertar(daemon, P4)
        assert daemon.controller.mudo_no_firmware(P4) is False, "a cena não ligou"
        daemon.controller.escritas_do_mudo.clear()

        _ativar(daemon, JOGO, origin="manual")
        assert daemon.controller.mudo_no_firmware(P4) is True, "a troca explícita não calou"

        assert await _reconectar(daemon, P4) is False, (
            "a reconexão abriu o microfone que ela calou escolhendo o perfil"
        )
        assert daemon.controller.mudos_escritos(P4)[-1] is True

    @pytest.mark.asyncio
    async def test_perfil_sem_opiniao_escolhido_na_mao_nao_apaga_o_ato(self, casa: Any) -> None:
        """Um perfil que não diz nada sobre o microfone não é ato sobre ele."""
        casa.perfil(FREESTYLE)
        casa.perfil(JOGO)
        daemon = casa.daemon()
        assert await hotkey.nascer_no_ar(daemon, P4) is True
        await _apertar(daemon, P4)  # calou

        _ativar(daemon, JOGO, origin="manual")

        assert await _reconectar(daemon, P4) is False, (
            "o perfil sem opinião apagou o silêncio que ela pediu no botão"
        )
        assert daemon.controller.mudos_escritos(P4)[-1] is True


# ===========================================================================
# 3. O MUDO DA PEÇA VENCE O DO GLOBAL, TAMBÉM NO REPLUG
# ===========================================================================


class TestAPecaVenceOGlobalNoReplug:
    def test_o_global_calado_nao_pisa_a_peca_ligada(self, casa: Any) -> None:
        """O `pragmata.json` dela tem `mic.muted: true` no global.

        O botão grava a PEÇA; o replug escrevia o global por cima, e o `False`
        da peça não atravessa o replug para desfazê-lo — medido num lar de
        mentira: `o_perfil_pede_silencio` dizia `False` e o replug escrevia
        `True`. MORDIDA: tirar a guarda do global em `reapply_mic_on_connect`.
        """
        casa.perfil(FREESTYLE, mic={"muted": True, "volume": 70},
                    por_peca={P4: {"mic": {"muted": False}}})
        chamadas: list[dict[str, Any]] = []

        def applier(volume: Any, muted: Any, *, uniq: Any = None, origin: str = "") -> str:
            chamadas.append({"volume": volume, "muted": muted, "uniq": uniq})
            return "aplicado"

        store = StateStore()
        store.set_active_profile(FREESTYLE)
        m = ProfileManager(controller=object(), store=store, mic_applier=applier)

        assert m.o_perfil_pede_silencio(P4) is False
        m.reapply_mic_on_connect(P4)

        assert [c["muted"] for c in chamadas if c["muted"] is not None] == [], (
            "o replug calou a peça que diz ligado — dois leitores, dois vereditos"
        )
        assert chamadas and chamadas[0]["volume"] == 70, "o volume do global sumiu"


# ===========================================================================
# 4. O MESMO LUGAR E AS MESMAS REGRAS DO CLIQUE DA TELA
# ===========================================================================


class TestOMesmoLugarDoCliqueDaTela:
    @pytest.mark.parametrize(
        ("mic_global", "peca", "mudo"),
        [
            (None, {"muted": True}, False),
            (None, None, True),
            ({"muted": True}, None, False),
            ({"muted": False}, {"muted": True, "volume": 40}, False),
            ({"muted": True}, {"muted": False}, True),
            (None, {"gain": 30}, True),
        ],
    )
    def test_o_disco_fica_igual_ao_que_a_tela_grava(
        self, casa: Any, mic_global: Any, peca: Any, mudo: bool
    ) -> None:
        """`DraftConfig.with_controller_mic` é o escritor do 🎙 da aba 02.

        MORDIDA: tirar a regra "igual ao global não vira override".
        """
        casa.perfil(FREESTYLE, mic=mic_global,
                    por_peca={P4: {"mic": peca}} if peca is not None else None)
        prof = loader.load_profile(FREESTYLE)
        draft = DraftConfig.from_profile(prof)
        tela = draft.with_controller_mic(
            P4, draft.effective_mic_for(P4).model_copy(update={"muted": mudo})
        ).to_profile(FREESTYLE, priority=prof.priority)
        esperado = {
            k: v.model_dump(exclude_unset=True) for k, v in (tela.controllers or {}).items()
        }

        gravar_o_mic_no_perfil_ativo(FREESTYLE, chave=P4, muted=mudo)

        agora = loader.load_profile(FREESTYLE)
        obtido = {
            k: v.model_dump(exclude_unset=True) for k, v in (agora.controllers or {}).items()
        }
        assert obtido == esperado

    def test_o_mesmo_lado_duas_vezes_nao_regrava(self, casa: Any) -> None:
        casa.perfil(FREESTYLE)
        assert gravar_o_mic_no_perfil_ativo(FREESTYLE, chave=P4, muted=True) == (
            FREESTYLE, True, None)
        assert gravar_o_mic_no_perfil_ativo(FREESTYLE, chave=P4, muted=True) == (
            FREESTYLE, False, "sem_mudanca")


class TestOAtoDaTelaGravaPeloMesmoCaminho:
    @pytest.mark.asyncio
    async def test_o_mic_canal_set_grava_como_o_botao(self, casa: Any) -> None:
        """O 🎙 chega pelo `mic.canal.set`, que é `ligar_o_microfone` — o mesmo ato."""
        casa.perfil(FREESTYLE, por_peca={P4: {"mic": {"muted": True}}})
        daemon = casa.daemon()
        daemon.controller._firmware_mudo[P4] = True

        ato = await hotkey.ligar_o_microfone(daemon, "aa:bb:cc:00:00:44", ligado=True)
        await _derrubar(daemon)

        assert ato.feito
        assert casa.mic_no_disco(FREESTYLE, P4) == {"muted": False}

    @pytest.mark.asyncio
    async def test_o_ato_em_que_nada_ficou_de_pe_nao_vai_ao_disco(
        self, casa: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """As duas metades recusadas: o arquivo não diz o que o aparelho não teve.

        MORDIDA: tirar a guarda "nada ficou de pé".
        """
        casa.perfil(FREESTYLE, por_peca={P4: {"mic": {"muted": True}}})
        daemon = casa.daemon(elege_ok=False)
        daemon.controller._firmware_mudo[P4] = True
        monkeypatch.setattr(daemon.controller, "set_microphone_mute",
                            lambda muted, *, uniq=None: False)

        ato = await hotkey.ligar_o_microfone(daemon, P4, ligado=True)

        assert not ato.canal_no_sistema.feita and not ato.firmware.feita
        assert casa.mic_no_disco(FREESTYLE, P4) == {"muted": True}
        assert daemon.store.ato_do_mic(P4) is None

    @pytest.mark.asyncio
    async def test_o_vpad_nao_e_peca_e_nao_grava(self, casa: Any) -> None:
        casa.perfil(FREESTYLE)
        vpad = "02fe00000001"
        daemon = casa.daemon((vpad,))

        await hotkey.ligar_o_microfone(daemon, vpad, ligado=False)
        await _derrubar(daemon)

        assert loader.load_profile(FREESTYLE).controllers is None
