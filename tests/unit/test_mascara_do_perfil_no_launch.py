"""MASCARA-01 — a máscara escolhida tem de CHEGAR ao aparelho (19/08/2026).

O defeito medido na madrugada de 18→19/08: ela escolheu Xbox e salvou às 00:36;
às 00:40 a bandeira viva `gamepad_emulation.flag` foi reescrita com `dualsense`.
O arquivo de env do jogo registrou a contradição na MESMA linha, sem que nada
agisse:

    estado: perfil gamepad xbox | native=False emulacao=True mascara=dualsense
    backends=['uhid']

Duas coisas estavam erradas nessa linha, e cada teste aqui morde uma:

1. o `mascara=` era o do estado GLOBAL, não o do perfil que aquele arquivo
   materializa — ou seja, o arquivo por appid DESCREVIA um estado que não é o
   dele. Quem lesse o arquivo do jogo não sabia qual máscara aquele jogo teria;
2. a divergência era só TEXTO. Não havia evento no journal nem campo no estado
   publicado, então nem o produto nem a GUI podiam agir sobre ela.

E o terceiro teste morde o arming: `arm_launch_profile` só rodava na
reconciliação de 1 Hz do `dispatch_gamepad`, que o `_poll_loop` gateia em
`_gamepad_device is not None` — com a emulação desligada no momento do launch,
o modo do perfil nunca era armado.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import hefesto_dualsense4unix.daemon.launch_env as le
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin


class _LoggerEspiao:
    """Dublê do logger structlog do módulo: registra (nível, evento, kwargs)."""

    def __init__(self) -> None:
        self.eventos: list[tuple[str, str, dict[str, Any]]] = []

    def _registra(self, nivel: str, evento: str, **kw: Any) -> None:
        self.eventos.append((nivel, evento, kw))

    def debug(self, evento: str, **kw: Any) -> None:
        self._registra("debug", evento, **kw)

    def info(self, evento: str, **kw: Any) -> None:
        self._registra("info", evento, **kw)

    def warning(self, evento: str, **kw: Any) -> None:
        self._registra("warning", evento, **kw)

    def nomes(self) -> list[str]:
        return [evento for _nivel, evento, _kw in self.eventos]

    def por_evento(self, nome: str) -> dict[str, Any]:
        for _nivel, evento, kw in self.eventos:
            if evento == nome:
                return kw
        raise AssertionError(f"evento {nome!r} não saiu; saíram {self.nomes()}")


APPID = 2497900  # DON'T SCREAM, o jogo da noite


def _perfil_xbox(nome: str = "DONT SCREAM") -> SimpleNamespace:
    return SimpleNamespace(
        name=nome,
        mode=SimpleNamespace(kind="gamepad", gamepad_flavor="xbox"),
        match=SimpleNamespace(
            window_class=[f"steam_app_{APPID}"],
            window_title_regex=None,
            process_name=[],
        ),
    )


def _daemon_dualsense_vivo(**extra: Any) -> SimpleNamespace:
    """Daemon com a máscara VIVA em `dualsense` — o estado medido às 00:40."""
    return SimpleNamespace(
        is_native_mode=lambda: False,
        config=SimpleNamespace(
            gamepad_emulation_enabled=True, gamepad_flavor="dualsense"
        ),
        _gamepad_device=SimpleNamespace(backend="uhid"),
        _coop_manager=None,
        controller=SimpleNamespace(),
        store=SimpleNamespace(window_detect_current_class=None),
        **extra,
    )


def _linha_de_estado(path: Path) -> str:
    for linha in path.read_text(encoding="utf-8").splitlines():
        if linha.startswith("# estado:"):
            return linha
    raise AssertionError(f"{path} não tem linha de estado")


@pytest.fixture
def env_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
    monkeypatch.setattr(le, "_permite_uhid", lambda daemon: True)
    return tmp_path


# --- 1. o arquivo do jogo diz a máscara DAQUELE jogo -------------------------


def test_env_do_jogo_materializa_a_mascara_do_perfil(
    env_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A MORDIDA: perfil `gamepad_flavor="xbox"` => `mascara=xbox` no env.

    Com a cura arrancada (a linha `estado:` do arquivo por appid copiando o
    estado GLOBAL) esta asserção reproduz literalmente a contradição de 00:40:
    "perfil gamepad xbox" e "mascara=dualsense" na mesma linha.
    """
    monkeypatch.setattr(
        le, "_steam_profiles", lambda daemon: [(APPID, _perfil_xbox())]
    )

    le.materialize_launch_env(_daemon_dualsense_vivo())

    linha = _linha_de_estado(env_dir / f"steam_app_{APPID}.env")
    assert "mascara=xbox" in linha
    assert "perfil gamepad xbox" in linha
    # o estado vivo continua na linha — atrás de `vivo:`, que é de quem ele fala
    assert "vivo: native=False emulacao=True mascara=dualsense" in linha


def test_env_do_jogo_sem_divergencia_nao_carimba_divergencia(
    env_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Máscara viva IGUAL à do perfil não é divergência — nada a carimbar."""
    monkeypatch.setattr(
        le, "_steam_profiles", lambda daemon: [(APPID, _perfil_xbox())]
    )
    daemon = _daemon_dualsense_vivo()
    daemon.config.gamepad_flavor = "xbox"

    le.materialize_launch_env(daemon)

    linha = _linha_de_estado(env_dir / f"steam_app_{APPID}.env")
    assert "mascara=xbox" in linha
    assert "divergente=" not in linha
    assert le.divergencias_publicadas(daemon) == []


# --- 2. a divergência vira SINAL (journal + estado publicado) ----------------


def test_divergencia_com_o_jogo_em_cena_vira_evento_no_journal(
    env_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    espiao = _LoggerEspiao()
    monkeypatch.setattr(le, "logger", espiao)
    monkeypatch.setattr(
        le, "_steam_profiles", lambda daemon: [(APPID, _perfil_xbox())]
    )
    daemon = _daemon_dualsense_vivo()
    daemon.store.window_detect_current_class = f"steam_app_{APPID}"

    le.materialize_launch_env(daemon)

    kw = espiao.por_evento("mascara_do_perfil_divergente")
    assert kw["appid"] == APPID
    assert kw["mascara_perfil"] == "xbox"
    assert kw["mascara_viva"] == "dualsense"
    assert kw["motivo"] == "perfil_xbox_vs_vivo_dualsense"


def test_divergencia_e_publicada_no_daemon_para_o_state_full(
    env_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        le, "_steam_profiles", lambda daemon: [(APPID, _perfil_xbox())]
    )
    daemon = _daemon_dualsense_vivo()
    daemon.store.window_detect_current_class = f"steam_app_{APPID}"

    le.materialize_launch_env(daemon)

    publicadas = le.divergencias_publicadas(daemon)
    assert publicadas == [
        {
            "appid": APPID,
            "profile": "DONT SCREAM",
            "mascara_perfil": "xbox",
            "mascara_viva": "dualsense",
            "motivo": "perfil_xbox_vs_vivo_dualsense",
            "em_cena": True,
        }
    ]


def test_jogo_fora_de_cena_e_antecipacao_nao_alarme(
    env_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Perfil de jogo FECHADO divergindo do global é o normal — o arquivo por
    appid ANTECIPA o modo. Alarme só com o jogo em cena."""
    espiao = _LoggerEspiao()
    monkeypatch.setattr(le, "logger", espiao)
    monkeypatch.setattr(
        le, "_steam_profiles", lambda daemon: [(APPID, _perfil_xbox())]
    )

    daemon = _daemon_dualsense_vivo()
    le.materialize_launch_env(daemon)

    assert "mascara_do_perfil_divergente" not in espiao.nomes()
    assert "mascara_do_perfil_antecipada" in espiao.nomes()
    assert le.divergencias_publicadas(daemon)[0]["em_cena"] is False


def test_divergencia_repetida_nao_reloga_e_convergencia_loga(
    env_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Só TRANSIÇÕES vão ao journal: a materialização roda em toda troca de
    estado, e um log por passagem viraria ruído."""
    espiao = _LoggerEspiao()
    monkeypatch.setattr(le, "logger", espiao)
    monkeypatch.setattr(
        le, "_steam_profiles", lambda daemon: [(APPID, _perfil_xbox())]
    )
    daemon = _daemon_dualsense_vivo()
    daemon.store.window_detect_current_class = f"steam_app_{APPID}"

    le.materialize_launch_env(daemon)
    le.materialize_launch_env(daemon)
    assert espiao.nomes().count("mascara_do_perfil_divergente") == 1

    daemon.config.gamepad_flavor = "xbox"
    le.materialize_launch_env(daemon)
    assert "mascara_do_perfil_convergiu" in espiao.nomes()
    assert le.divergencias_publicadas(daemon) == []


@pytest.mark.parametrize(
    ("kind", "flavor_perfil", "native_vivo", "emulacao_viva", "flavor_vivo", "esperado"),
    [
        ("gamepad", "xbox", False, True, "dualsense", "perfil_xbox_vs_vivo_dualsense"),
        ("gamepad", "xbox", False, True, "xbox", None),
        ("gamepad", "xbox", True, True, "xbox", "perfil_xbox_vs_vivo_nativo"),
        (
            "gamepad",
            "dualsense",
            False,
            False,
            "dualsense",
            "perfil_dualsense_vs_vivo_sem_emulacao",
        ),
        # perfil nativo/desktop não promete máscara nenhuma
        ("native", None, False, True, "dualsense", None),
        ("desktop", None, False, True, "dualsense", None),
    ],
)
def test_divergencia_de_mascara_e_pura(
    kind: str,
    flavor_perfil: str | None,
    native_vivo: bool,
    emulacao_viva: bool,
    flavor_vivo: str,
    esperado: str | None,
) -> None:
    perfil = SimpleNamespace(
        name="x", mode=SimpleNamespace(kind=kind, gamepad_flavor=flavor_perfil)
    )
    modo = le._modo_antecipado(
        perfil, flavor_atual=flavor_vivo, backends=["uhid"], permite_uhid=True
    )
    assert (
        le.divergencia_de_mascara(
            modo,
            native_vivo=native_vivo,
            emulacao_viva=emulacao_viva,
            flavor_vivo=flavor_vivo,
        )
        == esperado
    )


class _Handlers(IpcHandlersMixin):  # type: ignore[misc, valid-type]
    """Só as três dependências que o `state_full` consome (molde do JOGO-01)."""

    def __init__(self, daemon: Any, store: Any, controller: Any) -> None:
        self.daemon = daemon
        self.store = store
        self.controller = controller


def _bloco_do_state_full(divergencias: list[dict[str, Any]]) -> dict[str, Any]:
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.testing import FakeController

    daemon = Daemon(controller=FakeController(transport="usb"))
    daemon._mascara_divergencias = divergencias
    handlers = _Handlers(daemon, daemon.store, daemon.controller)
    cheio = asyncio.run(handlers._handle_daemon_state_full({}))
    return dict(cheio["gamepad_emulation"])


DIVERGENCIA = {
    "appid": APPID,
    "profile": "DONT SCREAM",
    "mascara_perfil": "xbox",
    "mascara_viva": "dualsense",
    "motivo": "perfil_xbox_vs_vivo_dualsense",
    "em_cena": True,
}


def test_state_full_publica_a_divergencia() -> None:
    """A GUI (outra frente) precisa do dado no `state_full` — sem I/O aqui."""
    bloco = _bloco_do_state_full([DIVERGENCIA])
    assert bloco["mascara_divergente"] == DIVERGENCIA
    assert bloco["mascara_divergencias"] == [DIVERGENCIA]


def test_state_full_sem_divergencia_publica_none() -> None:
    bloco = _bloco_do_state_full([])
    assert bloco["mascara_divergente"] is None
    assert bloco["mascara_divergencias"] == []


def test_state_full_divergencia_fora_de_cena_nao_e_alarme() -> None:
    fora = dict(DIVERGENCIA, em_cena=False)
    bloco = _bloco_do_state_full([fora])
    assert bloco["mascara_divergente"] is None
    assert bloco["mascara_divergencias"] == [fora]


# --- 3. o arming no launch --------------------------------------------------


def _daemon_para_arming(*, applier_aplica: bool) -> SimpleNamespace:
    daemon = _daemon_dualsense_vivo()

    def _applier(mode: Any, *, profile: Any, origin: str) -> bool:
        daemon.aplicou = (getattr(mode, "gamepad_flavor", None), origin)
        if applier_aplica:
            daemon.config.gamepad_flavor = str(mode.gamepad_flavor)
        # O contrato mentiroso do produto: True para "aplicou", "já estava" E
        # "foi bloqueado pelo gate R-04".
        return True

    daemon.apply_profile_mode = _applier
    daemon.aplicou = None
    return daemon


def _grava_marker(env_dir: Path, *, appid: int = APPID, epoch: int = 1000) -> None:
    """O marker que o wrapper grava ANTES do gate de vida e do `exec`."""
    (env_dir / "last_run").write_text(
        f"appid={appid}\nepoch={epoch}\npid=1\n", encoding="utf-8"
    )


def test_arm_no_launch_aplica_a_mascara_do_perfil(
    env_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        le, "_steam_profiles", lambda daemon: [(APPID, _perfil_xbox())]
    )
    _grava_marker(env_dir)
    daemon = _daemon_para_arming(applier_aplica=True)

    resultado = le.arm_launch_profile(daemon, base_dir=env_dir, now=1001.0)

    assert resultado is not None
    assert resultado["armado"] is True
    assert resultado["convergiu"] is True
    assert daemon.aplicou == ("xbox", "launch")
    assert daemon.config.gamepad_flavor == "xbox"


def test_arm_recusado_pelo_gate_nao_mente_que_convergiu(
    env_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A MORDIDA do item 2: o applier devolve True mesmo quando o gate R-04
    RECUSA a troca. Sem conferir o aparelho depois, o arming registrava
    "armado" numa troca que nunca aconteceu."""
    espiao = _LoggerEspiao()
    monkeypatch.setattr(le, "logger", espiao)
    monkeypatch.setattr(
        le, "_steam_profiles", lambda daemon: [(APPID, _perfil_xbox())]
    )
    _grava_marker(env_dir)
    daemon = _daemon_para_arming(applier_aplica=False)

    resultado = le.arm_launch_profile(daemon, base_dir=env_dir, now=1001.0)

    assert resultado is not None
    assert resultado["resultado"] is True  # o que o applier disse
    assert resultado["convergiu"] is False  # o que o aparelho mostra
    assert resultado["divergente"] == "perfil_xbox_vs_vivo_dualsense"
    kw = espiao.por_evento("launch_arm_mascara_nao_convergiu")
    assert kw["mascara_perfil"] == "xbox"
    assert kw["mascara_viva"] == "dualsense"


# --- 4. o ping do wrapper arma o launch (ipc_handlers) ----------------------


def _daemon_real() -> Any:
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.testing import FakeController

    return Daemon(controller=FakeController(transport="usb"))


class _HandlerDeLaunch(_Handlers):
    """`daemon.status` com o marker do wrapper injetado (sem tocar o disco)."""

    def __init__(self, daemon: Any, marker: tuple[int, int] | None) -> None:
        super().__init__(daemon, daemon.store, daemon.controller)
        self._marker = marker

    def _wrapper_marker_cached(self) -> tuple[int, int] | None:
        return self._marker


def _armou_pelo_status(daemon: Any, marker: tuple[int, int] | None) -> list[Any]:
    """Roda o `daemon.status` (o gate de vida do wrapper) e devolve o que o
    arming recebeu — lista vazia = não armou."""
    armados: list[Any] = []

    async def _corpo() -> None:
        await _HandlerDeLaunch(daemon, marker)._handle_daemon_status({})
        # o arming sai FORA da resposta: dois tiques do loop para ele rodar
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    def _falso_arm(alvo: Any, **kw: Any) -> dict[str, Any]:
        armados.append(alvo)
        return {"appid": APPID, "armado": True, "convergiu": True}

    original = le.arm_launch_profile
    le.arm_launch_profile = _falso_arm  # type: ignore[assignment]
    try:
        asyncio.run(_corpo())
    finally:
        le.arm_launch_profile = original  # type: ignore[assignment]
    return armados


def test_ping_do_wrapper_no_launch_arma_o_modo_do_perfil() -> None:
    """A MORDIDA do arming determinístico: o gate de vida do wrapper
    (`daemon.status`) é o único ponto da árvore que sabe que um jogo está
    SUBINDO agora. Sem isto o arming dependia da reconciliação de 1 Hz do
    `dispatch_gamepad`, que o `_poll_loop` gateia em `_gamepad_device is not
    None` — com a emulação desligada no launch, o modo do perfil NUNCA era
    armado."""
    daemon = _daemon_real()
    assert _armou_pelo_status(daemon, (APPID, int(time.time()))) == [daemon]


def test_ping_sem_marker_fresco_nao_paga_nada() -> None:
    """`daemon.status` de CLI/GUI não pode arrastar o arming atrás."""
    daemon = _daemon_real()
    velho = int(time.time() - le.LAUNCH_ARM_WINDOW_SEC - 10)
    assert _armou_pelo_status(daemon, (APPID, velho)) == []
    assert _armou_pelo_status(daemon, None) == []


def test_ping_nao_rearma_o_mesmo_launch() -> None:
    daemon = _daemon_real()
    marker = (APPID, int(time.time()))
    daemon._launch_armed_for = marker
    assert _armou_pelo_status(daemon, marker) == []
