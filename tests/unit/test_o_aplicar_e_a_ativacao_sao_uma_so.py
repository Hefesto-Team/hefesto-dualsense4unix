"""O-APLICAR-E-A-ATIVACAO-SAO-UMA-SO-01 — o «Aplicar» e a ativação são uma só."""
from __future__ import annotations

import asyncio
import time
import types
from typing import Any

import pytest

from hefesto_dualsense4unix.core.controller import OutputSpec
from hefesto_dualsense4unix.daemon.lifecycle import ADIADO_LOCK_MANUAL, Daemon
from hefesto_dualsense4unix.daemon.subsystems import mouse as sub_mouse
from hefesto_dualsense4unix.daemon.subsystems.mouse import trocar_a_tabela_no_jogo
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles import manager as manager_mod
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    ControllerMicOverride,
    ControllerOverrides,
    ControllerRumbleOverride,
    ControllerSensoresOverride,
    LedsConfig,
    MatchCriteria,
    Profile,
    ProfileMicConfig,
    ProfileModeConfig,
    ProfileMouseConfig,
    ProfileMovimentoConfig,
    ProfileSpeakerConfig,
    RumbleConfig,
    TriggerConfig,
    TriggersConfig,
)
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import session

CABO = ("aabbcc000001", "aabbcc000002")
RADIO = ("02fe00000003", "02fe00000004")
UNIQS = CABO + RADIO
NOME = "Jogo da Régua"

FORA: dict[str, str] = {
    "name": "é o nome do arquivo, não um ajuste",
    "version": "é a versão do formato, não um ajuste",
    "match": "decide QUANDO o perfil entra (a seleção), não o que ele aplica",
    "priority": "decide QUEM ganha na seleção, não o que ele aplica",
    "ponte": "é o carimbo da escada do lançamento, lido por ela no jogo",
    "teclado_emulado": "é lido na entrada da Navegação, pelo arranjo do desktop",
    "estilo": "é lido pelo motor do tato vivo a cada segundo, não pelo aplicar",
    "receita_do_tato": "é o desvio da bancada, lido pelo motor do tato vivo",
    "marcas": "são etiquetas da pessoa, lidas pela tela e pelas modificações",
    "criado_em": "é a data em que o arquivo nasceu, lida pela lista da aba Perfis",
    "alvo": "é onde o perfil vale, lido pela aba Perfis; nenhum motor o lê ainda",
    "evento": "é o momento que chama o perfil nos eventos; nenhum motor o lê ainda",
    "evento_comando": "é o comando do «Meu comando»; nenhum motor o lê ainda",
    "modificado_em": "é a data da última mudança dela, lida pela lista da aba Perfis",
    "controles_modo": "é a escolha do botão «Modo automático» da aba Controles, lida pela tela",
}
FORA_POR_CONTROLE: dict[str, str] = {}


class _ControleQueAnota(FakeController):
    """O controle de mentira que anota o que chegou a cada `uniq`."""

    def __init__(self) -> None:
        super().__init__(transport="usb")
        self.padrao: list[OutputSpec] = []
        self.por_uniq: dict[str, OutputSpec] = {}

    def apply_output_defaults(self, spec: OutputSpec) -> None:
        self.padrao.append(spec)

    def reset_output_overrides(self, overrides: Any = None, **_kw: Any) -> None:
        self.por_uniq = dict(overrides or {})

    def apply_output_for(self, uniq: str, spec: OutputSpec, **_kw: Any) -> str:
        self.por_uniq[uniq] = spec
        return "escreveu"


def _espiao(modelo: Any, caminho: str, lidos: set[str]) -> Any:
    """O mesmo modelo, numa subclasse que anota cada CAMPO lido por atributo."""
    base = type(modelo)
    campos = frozenset(base.model_fields)

    class _Espia(base):  # type: ignore[valid-type,misc]
        def __getattribute__(self, nome: str) -> Any:
            if nome in campos:
                lidos.add(f"{caminho}{nome}")
            return super().__getattribute__(nome)

    _Espia.__name__ = base.__name__
    copia = _Espia.model_construct(_fields_set=modelo.model_fields_set,
                                   **dict(modelo.__dict__))
    return copia


def _o_perfil_inteiro() -> Profile:
    """Um perfil em que todo campo diz alguma coisa, nos quatro controles."""
    def _peca(n: int) -> ControllerOverrides:
        return ControllerOverrides(
            leds=LedsConfig(lightbar=(10 * n, 20, 30), lightbar_brightness=0.5,
                            player_led_brightness="forte"),
            triggers=TriggersConfig(left=TriggerConfig(mode="Rigid", params=[5, 200])),
            rumble=ControllerRumbleOverride(motor_forte_pct=50),
            speaker=ProfileSpeakerConfig(volume=40 + n, muted=False),
            mic=ControllerMicOverride(volume=30 + n),
            sensores=ControllerSensoresOverride(giroscopio=False),
            mascara="xbox" if n % 2 else "dualsense",
            movimento=ProfileMovimentoConfig(),
        )

    return Profile(
        name=NOME,
        match=MatchCriteria(window_class=["steam_app_480"]),
        priority=80,
        triggers=TriggersConfig(right=TriggerConfig(mode="Rigid", params=[5, 100])),
        leds=LedsConfig(lightbar=(1, 2, 3)),
        rumble=RumbleConfig(passthrough=True, policy="max"),
        key_bindings={"cross": ["KEY_ENTER"]},
        button_actions={"cross": "BTN_LEFT"},
        remapeamento={"cross": "circle"},
        movimento=ProfileMovimentoConfig(),
        mouse=ProfileMouseConfig(enabled=True, speed=7, scroll_speed=2),
        teclado_emulado=True,
        mic=ProfileMicConfig(button_toggles_system=False, volume=55),
        speaker=ProfileSpeakerConfig(volume=60, muted=False),
        mode=ProfileModeConfig(kind="gamepad", caminho="dualsense"),
        suppress_desktop_emulation=True,
        controllers={uniq: _peca(n) for n, uniq in enumerate(UNIQS, start=1)},
    )


def _anotador() -> tuple[dict[str, list[Any]], dict[str, Any]]:
    """Os appliers do daemon, de mentira: cada um anota o que recebeu."""
    chegou: dict[str, list[Any]] = {}

    def _anota(nome: str) -> Any:
        def _applier(*args: Any, **kwargs: Any) -> str:
            chegou.setdefault(nome, []).append((args, kwargs))
            return "aplicado"
        return _applier

    appliers = {
        nome: _anota(nome)
        for nome in ("mouse_applier", "suppression_applier", "mode_applier",
                     "rumble_policy_applier", "rumble_passthrough_applier",
                     "speaker_applier", "mic_applier")
    }
    anota_a_supressao = appliers["suppression_applier"]

    def _supressao(*args: Any, **kwargs: Any) -> str:
        # O `apply_profile_suppression` do daemon entrega o perfil ao dono da
        # chave «Também no jogo» e do «Só dentro do jogo» ANTES de tudo (ver
        # `test_o_applier_da_supressao_entrega_o_perfil_ao_dono_da_tabela`).
        trocar_a_tabela_no_jogo(types.SimpleNamespace(), kwargs["profile"])
        return str(anota_a_supressao(*args, **kwargs))

    appliers["suppression_applier"] = _supressao
    return chegou, appliers


def _gerente(controle: _ControleQueAnota, store: StateStore) -> tuple[ProfileManager, Any]:
    chegou, appliers = _anotador()
    gerente = ProfileManager(controller=controle, store=store, **appliers)
    return gerente, chegou


def test_todo_campo_do_perfil_e_de_cada_controle_e_levado_pelo_aplicar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cada campo do esquema é lido pela cadeia do `reaplicar`, ou está em `FORA`."""
    loader.save_profile(_o_perfil_inteiro(), origem="régua")
    lidos: set[str] = set()

    def _carregar_espiado(nome: str) -> Profile:
        perfil = loader.load_profile(nome)
        controles = {
            uniq: _espiao(peca, f"controllers.{uniq}.", lidos)
            for uniq, peca in (perfil.controllers or {}).items()
        }
        espiado = _espiao(perfil, "", lidos)
        object.__setattr__(espiado, "controllers", controles)
        return espiado

    monkeypatch.setattr(manager_mod, "load_profile", _carregar_espiado)
    controle = _ControleQueAnota()
    gerente, chegou = _gerente(controle, StateStore())

    gerente.reaplicar(NOME)

    faltam = sorted(
        campo for campo in Profile.model_fields
        if campo not in lidos and campo not in FORA
    )
    for uniq in UNIQS:
        faltam += sorted(
            f"controllers.{uniq}.{campo}" for campo in ControllerOverrides.model_fields
            if f"controllers.{uniq}.{campo}" not in lidos
            and campo not in FORA_POR_CONTROLE
        )
    assert not faltam, (
        "o «Aplicar» (a cadeia da ativação) não leva estes campos, e nenhum está "
        "declarado fora com a razão:\n  " + "\n  ".join(faltam))
    assert set(controle.por_uniq) == set(UNIQS), (
        f"a luz e o gatilho por controle não chegaram aos quatro: {sorted(controle.por_uniq)}")
    for nome in ("mode_applier", "rumble_policy_applier", "mic_applier",
                 "speaker_applier", "suppression_applier", "mouse_applier"):
        assert chegou.get(nome), f"o {nome} não recebeu nada no «Aplicar»"


def test_o_aplicar_nao_e_escolha_nem_liga_o_freestyle() -> None:
    """O `reaplicar` não grava a sessão, o marcador nem o último jogo, e não mexe no Freestyle.

    D-0110-O-APLICAR-NAO-E-ESCOLHA, a parte que a D-1410-O-APLICAR-SEGURA manteve: ele arma a
    trava, mas o disco fica byte a byte como estava.
    """
    loader.save_profile(_o_perfil_inteiro(), origem="régua")
    store = StateStore()
    gerente, _chegou = _gerente(_ControleQueAnota(), store)
    session.save_last_profile("A Escolha Dela")
    session.lembrar_o_ultimo_jogo("O Último Jogo")
    sessao_antes = session._session_path().read_bytes()
    ultimo_antes = session._ultimo_jogo_path().read_bytes()

    gerente.reaplicar(NOME)

    assert session.load_last_profile() == "A Escolha Dela", (
        "o «Aplicar» gravou a escolha dela")
    assert session._session_path().read_bytes() == sessao_antes, "o «Aplicar» mexeu no session.json"
    assert session._ultimo_jogo_path().read_bytes() == ultimo_antes, (
        "o «Aplicar» mexeu no ultimo_jogo.json")
    assert session.read_active_marker() is None, "o «Aplicar» escreveu o marcador"
    assert store.freestyle_ligado is False
    assert store.active_profile == NOME


def _o_handler_do_reaplicar(store: StateStore) -> tuple[Any, dict[str, Any]]:
    """O handler REAL do `profile.reaplicar`, sobre o gerente de verdade."""
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    loader.save_profile(_o_perfil_inteiro(), origem="régua")
    gerente, chegou = _gerente(_ControleQueAnota(), store)

    class _Handlers(IpcHandlersMixin):
        def __init__(self) -> None:
            self.daemon = None  # type: ignore[assignment]
            self.store = store
            self.profile_manager = gerente

    return _Handlers(), chegou


def test_o_profile_reaplicar_do_gesto_arma_a_trava_da_troca_a_mao() -> None:
    """O handler do `profile.reaplicar` com ``prender`` responde como o switch e arma a trava.

    D-1410-O-APLICAR-SEGURA (14/10/2026): o «Aplicar» do rodapé e o «Voltar à de ontem» são
    gesto do usuário e seguram, sem prazo, até o próximo gesto ou outro jogo com perfil.
    MORDIDA: tire o ``armar_a_trava_da_mao`` do ramo da reaplicação no ``_ativar``.
    """
    import time

    store = StateStore()
    handlers, chegou = _o_handler_do_reaplicar(store)

    resposta = asyncio.run(handlers._handle_profile_reaplicar({"name": NOME, "prender": True}))

    assert resposta["active_profile"] == NOME
    assert resposta["mode_aplicado"] is True and "mode" in resposta["secoes"]
    assert store.manual_profile_lock_active(time.monotonic() + 3600.0), (
        "o «Aplicar» não armou a trava da troca à mão (ou armou com prazo)")
    (_args, kwargs), = chegou["mode_applier"]
    assert kwargs["origin"] == "manual", (
        "o «Aplicar» é gesto dela: a R-04 vale igual à da ativação")


def test_o_profile_reaplicar_sem_o_gesto_nao_prende() -> None:
    """D-1410-O-APLICAR-SEGURA, parte 3: o ajuste numa aba reaplica SEM armar a trava.

    O padrão do IPC é sem trava, para os dois lados da régua: sem ``prender`` (e com
    ``prender: false``) o perfil volta aos controles e o autoswitch segue livre. MORDIDA: faça
    o ramo da reaplicação armar sem olhar o ``prender`` e esta régua reprova.
    """
    import time

    for params in ({"name": NOME}, {"name": NOME, "prender": False}):
        store = StateStore()
        handlers, _chegou = _o_handler_do_reaplicar(store)
        resposta = asyncio.run(handlers._handle_profile_reaplicar(dict(params)))
        assert resposta["active_profile"] == NOME
        assert not store.manual_profile_lock_active(time.monotonic()), (
            f"o reaplicar de um ajuste prendeu o autoswitch ({params})")

    store = StateStore()
    handlers, _chegou = _o_handler_do_reaplicar(store)
    asyncio.run(handlers._handle_profile_reaplicar({"name": NOME, "prender": "sim"}))
    assert not store.manual_profile_lock_active(time.monotonic()), (
        "só o booleano verdadeiro prende: o texto «sim» armou a trava")


def test_o_applier_da_supressao_entrega_o_perfil_ao_dono_da_tabela(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O applier real chama `trocar_a_tabela_no_jogo` com o perfil, mesmo sob a trava manual."""
    recebidos: list[Any] = []
    monkeypatch.setattr(sub_mouse, "trocar_a_tabela_no_jogo",
                        lambda _daemon, perfil: recebidos.append(perfil))
    perfil = _o_perfil_inteiro()
    daemon = types.SimpleNamespace(_suppress_manual_ts=time.monotonic())

    desfecho = Daemon.apply_profile_suppression(
        daemon, True, profile=perfil, origin="autoswitch")

    assert desfecho == ADIADO_LOCK_MANUAL
    assert recebidos == [perfil], (
        "o applier da supressão não entregou o perfil ao dono da tabela no jogo: "
        "a chave «Também no jogo» e o «Só dentro do jogo» não andam no «Aplicar»")
