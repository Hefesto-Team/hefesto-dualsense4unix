"""O-JOGO-SEGUINTE-VESTE-A-PROPRIA-ROUPA-01 — o jogo seguinte veste a própria roupa.

O que se mediu em 23/10 (a sessão C da bancada, o rádio, 10 s entre o fecho de um jogo
e o lançamento do seguinte): a autoridade do sinal de jogo ficava `game` pela histerese
de 30 s do jogo que já fechou, o arme do jogo novo não recriava o pad
(`gamepad._recriacao_bloqueada_por_jogo` recusa a origem `profile`) e o jogo novo
enumerava o pad do anterior. A cura é na origem: o arme de um lançamento novo, sem
outro jogo vivo na varredura, encerra a autoridade (`daemon_outro_lancamento`) pela
mesma porta da borda `game -> daemon`, e só então veste a roupa do jogo novo.

O `Daemon` aqui é o de verdade, com o `GameSignal` de verdade e o relógio dado pela
régua; só a borda do aparelho é dublada (o pad, o leitor evdev, o broker). A varredura
de processos entra pelas leituras do `_gather_game_signal_inputs` e por um `/proc` de
mentira (`steam_launch_options.PROC`), com a cmdline que a Steam dá ao `reaper`.
Os endereços são da faixa forjada da casa. A mordida de cada teste está no docstring dele.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest
import structlog.testing

from hefesto_dualsense4unix.core.numeros_da_sony import (
    ROUPA_COMUM,
    ROUPA_PADRAO,
    roupa_normalizada,
)
from hefesto_dualsense4unix.daemon import launch_env as le
from hefesto_dualsense4unix.daemon import lifecycle as lc
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
    _zerar_registro_de_mascaras,
)
from hefesto_dualsense4unix.daemon.subsystems.game_signal import (
    HYSTERESIS_SEC,
    GameSignal,
    classify,
)
from hefesto_dualsense4unix.integrations import steam_launch_options as slo
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.profiles.schema import (
    MatchCriteria,
    Profile,
    ProfileModeConfig,
)
from hefesto_dualsense4unix.testing.fake_controller import FakeController
from hefesto_dualsense4unix.utils import session as session_mod

MAC_P1 = "aa:bb:cc:00:00:01"
SECUNDARIOS = ("aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03", "aa:bb:cc:00:00:04")
NOS = {
    MAC_P1: "/dev/input/event5",
    SECUNDARIOS[0]: "/dev/input/event7",
    SECUNDARIOS[1]: "/dev/input/event9",
    SECUNDARIOS[2]: "/dev/input/event11",
}
EDGE = ROUPA_PADRAO
COMUM = ROUPA_COMUM

JOGO_A = 1118010  # o jogo que fechou
JOGO_B = 1627720  # o jogo aberto logo depois
EPOCH_A = 900
EPOCH_B = 1000


class _Pad:
    """O pad uhid de mentira: veste a roupa que a fábrica recebeu."""

    def __init__(
        self, flavor: str | None, identity: str | None, roupa: object, caminho: str | None,
    ) -> None:
        self.flavor = flavor or "dualsense"
        self.identity = identity
        self.product = roupa_normalizada(roupa)
        self.caminho = vp.caminho_resolvido(caminho, self.flavor)
        self.backend = "uhid" if vp.quer_uhid(caminho, self.flavor) else "uinput"
        self.parado = False

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        self.parado = True

    def forward_analog(self, **_kw: int) -> None:
        return None

    def forward_buttons(self, _pressed: Any) -> None:
        return None

    def pump_ff(self) -> None:
        return None


class _Leitor:
    """O leitor evdev de mentira: o grab confirma na hora."""

    def __init__(self, device_path: Any = None, target_uniq: str | None = None) -> None:
        self.device_path = device_path
        self.target_uniq = target_uniq
        self.grab_state = "off"

    def start(self) -> bool:
        return True

    def set_grab(self, grab: bool) -> bool:
        self.grab_state = "held" if grab else "off"
        return True

    def stop(self) -> None:
        return None

    def snapshot(self) -> Any:
        return None


class _Nascidos:
    todos: ClassVar[list[_Pad]] = []


class _Relogio:
    def __init__(self) -> None:
        self.agora = 5000.0

    def __call__(self) -> float:
        return self.agora


@pytest.fixture(autouse=True)
def _hermetico(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Disco em tmp, o registro zerado, a borda do pad, do evdev e do broker dublada."""
    from hefesto_dualsense4unix.utils import xdg_paths

    alvo = tmp_path / "config"

    def _config_dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(xdg_paths, "config_dir", _config_dir)
    monkeypatch.setattr(session_mod, "config_dir", _config_dir)

    def _fabrica(
        flavor: Any, *, identity: Any = None, roupa: Any = None, caminho: Any = None, **_kw: Any,
    ) -> _Pad:
        pad = _Pad(flavor, identity, roupa, caminho)
        _Nascidos.todos.append(pad)
        return pad

    _Nascidos.todos = []
    monkeypatch.setattr(vp, "make_virtual_pad", _fabrica)
    monkeypatch.setattr(le, "materialize_launch_env", lambda _d: None)
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
    (tmp_path / "proc").mkdir()
    monkeypatch.setattr(slo, "PROC", tmp_path / "proc")
    monkeypatch.setattr(gp, "_set_controller_grab", lambda *_a: None)
    monkeypatch.setattr(gp, "controller_allows_uhid", lambda _d: True)
    monkeypatch.setattr(gp, "_o_broker_atende", lambda _d: True)
    monkeypatch.setattr("hefesto_dualsense4unix.core.evdev_reader.EvdevReader", _Leitor)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.InputDirWatch.poll", lambda self: True
    )
    monkeypatch.setattr("hefesto_dualsense4unix.core.sysfs_leds.discover", lambda: {})
    _zerar_registro_de_mascaras()
    yield
    _zerar_registro_de_mascaras()


def _na_mesa(monkeypatch: pytest.MonkeyPatch, secundarios: int) -> None:
    macs = (MAC_P1, *SECUNDARIOS[:secundarios])
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.discover_dualsense_evdevs",
        lambda: {mac: Path(NOS[mac]) for mac in macs},
    )


class _Mesa:
    """O `Daemon` real com o sinal real, o relógio dado e a varredura injetada."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, transporte: str, secundarios: int) -> None:
        self.relogio = _Relogio()
        d = Daemon(
            controller=FakeController(transport=transporte),
            config=DaemonConfig(ipc_enabled=False, udp_enabled=False),
        )
        d.controller.primary_uniq = MAC_P1
        d._game_signal = GameSignal(time_fn=self.relogio)
        self.d = d
        self.varredura: dict[str, Any] = {}
        self.sessao_aberta = True
        d._gather_game_signal_inputs = self._ler
        self.mesa: Any = None
        gp.start_gamepad_emulation_desfecho(
            d, "dualsense", origin="profile", caminho=vp.CAMINHO_DUALSENSE
        )
        if secundarios:
            _na_mesa(monkeypatch, secundarios)
            self.mesa = coop_mod.get_coop_manager(d)
            self.mesa.sync()
            assert len([p for p in self.mesa._players.values() if p.vpad]) == secundarios, (
                "premissa: os secundários de pé")

    def _ler(self) -> dict[str, Any]:
        base: dict[str, Any] = {
            "window_healthy": True, "window_class_current": None, "window_seen_age": None,
            "profile_rule_match": False, "marker": None, "marker_pid_alive": False,
            "marker_pid": None, "exit_marker": None, "exit_pid": None,
            "appid_de_jogo_vivo": None, "session_open": self.sessao_aberta,
            "now": self.relogio.agora,
        }
        base.update(self.varredura)
        return base

    def tique(self) -> str:
        """Um tique do sinal, como o `_sync_game_signal` o faz (a varredura vem da régua)."""
        inputs = self._ler()
        self.d._game_signal.evaluate(
            classify(**inputs), session_open=bool(inputs["session_open"])
        )
        return str(self.d.display_authority)

    def abrir_o_jogo(self, appid: int, epoch: float, roupa: int) -> None:
        """O jogo A de pé: autoridade `game`, a trava e a roupa dele armadas pelo arme."""
        gp.vestir_a_roupa(self.d, roupa)
        assert set(self.roupas().values()) == {roupa}, "premissa: os pads vestem a roupa do jogo"
        self.varredura = {"appid_de_jogo_vivo": appid}
        assert self.tique() == "game"
        self.d._pad_travado_pelo_lancamento = (appid, epoch)

    def fechar_o_jogo(self, segundos_ate_o_proximo: float) -> None:
        """O jogo A fecha: nenhum processo, a janela some, o tempo corre até o lançamento B."""
        self.varredura = {}
        assert self.tique() == "game", "premissa: a histerese segura o jogo que fechou"
        self.relogio.agora += segundos_ate_o_proximo

    def lancar(self, pasta: Path, appid: int, epoch: float) -> None:
        """O wrapper do jogo novo grava o `last_run` e o processo dele nasce."""
        (pasta / "last_run").write_text(
            f"appid={appid}\nepoch={int(epoch)}\npid=4242\n", encoding="utf-8"
        )
        _processo(pasta, 4242, appid)

    def roupas(self) -> dict[str, int]:
        p1 = self.d._gamepad_device
        todas = {"p1": int(p1.product)}
        if self.mesa is not None:
            for chave, jogador in self.mesa._players.items():
                if jogador.vpad is not None:
                    todas[chave] = int(jogador.vpad.product)
        return todas


def _processo(pasta: Path, pid: int, appid: int, *, install: bool = False) -> None:
    """Um processo de jogo da Steam no `/proc` de mentira, com a cmdline do `reaper`."""
    extra = ["Install=1"] if install else []
    argv = ["/lar/.steam/ubuntu12_32/reaper", "SteamLaunch", f"AppId={appid}", *extra,
            "--", "/lar/jogo/jogo.exe"]
    (pasta / "proc" / str(pid)).mkdir()
    (pasta / "proc" / str(pid) / "cmdline").write_bytes("\0".join(argv).encode() + b"\0")


def _perfil(appid: int, flavor: str = "dualsense", caminho: Any = None) -> Profile:
    return Profile(
        name=f"jogo_{appid}",
        match=MatchCriteria(window_class=[f"steam_app_{appid}"]),
        priority=80,
        mode=ProfileModeConfig(kind="gamepad", gamepad_flavor=flavor, caminho=caminho),
    )


def _roupa_do_jogo_novo(monkeypatch: pytest.MonkeyPatch, roupa: int) -> None:
    """A roupa que o `materialize` gravou para o jogo novo (`roupa_gravada`)."""
    monkeypatch.setattr(le, "roupa_gravada", lambda appid, base_dir=None, lido_ate=None: roupa)


def _arme(mesa: _Mesa, pasta: Path, *, depois_s: float = 10.0) -> dict[str, Any] | None:
    resultado: dict[str, Any] | None = le.arm_launch_profile(
        mesa.d, base_dir=pasta, now=float(EPOCH_B) + depois_s / 10
    )
    return resultado


def _linhas(diario: Any, evento: str) -> list[dict[str, Any]]:
    return [x for x in diario if x.get("event") == evento]


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("secundarios", [0, 1, 2, 3], ids=["1j", "2j", "3j", "4j"])
def test_o_lancamento_de_outro_appid_encerra_a_autoridade_do_jogo_que_acabou(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, transporte: str, secundarios: int,
) -> None:
    """A prova de D-2310-O-JOGO-SEGUINTE-VESTE-A-PROPRIA-ROUPA: o A (`0ce6`) fechou há 10 s e o B
    (Edge) arma: os pads vestem o Edge, no cabo e no rádio.

    MORDIDA: tire o encerramento do `arm_launch_profile` e a autoridade fica `game`,
    a troca é recusada e os pads ficam `0ce6` (o Sackboy de 23/10).
    """
    _roupa_do_jogo_novo(monkeypatch, EDGE)
    mesa = _Mesa(monkeypatch, transporte, secundarios)
    mesa.abrir_o_jogo(JOGO_A, EPOCH_A, COMUM)
    mesa.fechar_o_jogo(10.0)
    mesa.lancar(tmp_path, JOGO_B, EPOCH_B)

    with structlog.testing.capture_logs() as diario:
        resultado = _arme(mesa, tmp_path)

    assert resultado is not None and resultado["appid"] == JOGO_B
    transicoes = [
        (x["de"], x["para"], x["evidencia"]) for x in _linhas(diario, "game_signal_transition")
    ]
    assert transicoes == [("game", "daemon", "daemon_outro_lancamento")], transicoes
    assert _linhas(diario, "pad_do_lancamento_destravado")[0]["motivo"] == lc.MOTIVO_DA_AUTORIDADE
    assert set(mesa.roupas().values()) == {EDGE}, mesa.roupas()
    assert len(mesa.roupas()) == 1 + secundarios
    assert _linhas(diario, "vpad_recriacao_bloqueada_por_jogo") == []
    assert mesa.d._pad_travado_pelo_lancamento == (JOGO_B, EPOCH_B), "a trava é a do jogo novo"
    assert mesa.d.roupa_do_pad == EDGE


def test_a_soltura_roda_antes_de_vestir_a_roupa_nova(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ordem do arme: a borda `game -> daemon` (a soltura) e só então a roupa de B.

    MORDIDA: troque as duas no `arm_launch_profile` e a roupa do jogo novo é vestida
    sobre a trava do anterior, que a recusa.
    """
    _roupa_do_jogo_novo(monkeypatch, COMUM)
    mesa = _Mesa(monkeypatch, "bt", 0)
    mesa.abrir_o_jogo(JOGO_A, EPOCH_A, EDGE)
    mesa.fechar_o_jogo(10.0)
    mesa.lancar(tmp_path, JOGO_B, EPOCH_B)
    ordem: list[str] = []
    solta = lc._soltar_o_pad_do_lancamento
    veste = gp.vestir_a_roupa

    def soltar_e_anotar(d: Any, motivo: str) -> Any:
        ordem.append("soltar")
        return solta(d, motivo)

    def vestir_e_anotar(d: Any, roupa: Any) -> Any:
        ordem.append(f"vestir:{int(roupa):04x}")
        return veste(d, roupa)

    monkeypatch.setattr(lc, "_soltar_o_pad_do_lancamento", soltar_e_anotar)
    monkeypatch.setattr(gp, "vestir_a_roupa", vestir_e_anotar)

    _arme(mesa, tmp_path)

    assert ordem == ["soltar", "vestir:0ce6"], ordem
    assert mesa.roupas() == {"p1": COMUM}


@pytest.mark.parametrize("quem_vive", ["o_processo", "a_janela", "a_regra_do_perfil"])
def test_o_jogo_vivo_segura_a_autoridade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, quem_vive: str,
) -> None:
    """O mesmo arme de B com A vivo na varredura (o launcher que fica): a autoridade fica `game`.

    O processo de A é o caso da varredura de verdade: no arme, a do sinal responde o
    appid de B (o marcador é dele), e só o `/proc` mostra A ainda de pé.

    MORDIDA: encerre sempre e este teste reprova (a transição aparece); tire a
    pergunta ao `/proc` (`appids_de_jogo_vivos`) e o caso do processo reprova.
    """
    _roupa_do_jogo_novo(monkeypatch, EDGE)
    mesa = _Mesa(monkeypatch, "usb", 0)
    mesa.abrir_o_jogo(JOGO_A, EPOCH_A, COMUM)
    if quem_vive == "o_processo":
        _processo(tmp_path, 3131, JOGO_A)
    escolhas: dict[str, dict[str, Any]] = {
        "o_processo": {"appid_de_jogo_vivo": JOGO_B},
        "a_janela": {"window_class_current": f"steam_app_{JOGO_A}"},
        "a_regra_do_perfil": {"window_class_current": "heroic-algum", "profile_rule_match": True},
    }
    mesa.varredura = escolhas[quem_vive]
    assert mesa.tique() == "game"
    mesa.lancar(tmp_path, JOGO_B, EPOCH_B)

    with structlog.testing.capture_logs() as diario:
        _arme(mesa, tmp_path)

    assert mesa.d.display_authority == "game"
    assert _linhas(diario, "game_signal_transition") == []
    assert _linhas(diario, "pad_do_lancamento_destravado") == []
    assert mesa.roupas() == {"p1": COMUM}, "o pad do jogo vivo não é recriado"


@pytest.mark.parametrize("quem_lembra", ["a_trava", "o_arme_anterior"])
def test_o_mesmo_jogo_lancado_de_novo_nao_encerra_a_autoridade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, quem_lembra: str,
) -> None:
    """O A fecha e abre de novo em 10 s: não é outro jogo, a autoridade e o pad ficam.

    MORDIDA: tire a comparação com o lançamento anterior e a autoridade cai, com a
    soltura devolvendo o Edge e o arme vestindo de novo a roupa que o pad já tinha.
    """
    _roupa_do_jogo_novo(monkeypatch, COMUM)
    mesa = _Mesa(monkeypatch, "bt", 1)
    mesa.abrir_o_jogo(JOGO_A, EPOCH_A, COMUM)
    if quem_lembra == "o_arme_anterior":
        mesa.d._pad_travado_pelo_lancamento = None
        mesa.d._launch_armed_for = (JOGO_A, EPOCH_A)
    mesa.fechar_o_jogo(10.0)
    mesa.lancar(tmp_path, JOGO_A, EPOCH_B)
    nascidos = len(_Nascidos.todos)

    with structlog.testing.capture_logs() as diario:
        _arme(mesa, tmp_path)

    assert mesa.d.display_authority == "game"
    assert _linhas(diario, "game_signal_transition") == []
    assert _linhas(diario, "launch_arm_autoridade_mantida_mesmo_jogo") != []
    assert len(_Nascidos.todos) == nascidos, "nenhum pad recriado"
    assert set(mesa.roupas().values()) == {COMUM}


def test_o_avaliador_do_install_script_de_outro_jogo_nao_segura_a_autoridade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O `reaper ... Install=1` de outro appid não é jogo: o lançamento de B encerra.

    MORDIDA: conte o avaliador como jogo e a autoridade fica `game`.
    """
    _roupa_do_jogo_novo(monkeypatch, EDGE)
    mesa = _Mesa(monkeypatch, "usb", 0)
    mesa.abrir_o_jogo(JOGO_A, EPOCH_A, COMUM)
    mesa.fechar_o_jogo(10.0)
    _processo(tmp_path, 3131, JOGO_A, install=True)
    mesa.lancar(tmp_path, JOGO_B, EPOCH_B)

    _arme(mesa, tmp_path)

    assert mesa.d.display_authority == "daemon"
    assert mesa.roupas() == {"p1": EDGE}


def test_o_caminho_do_perfil_do_jogo_seguinte_nao_e_adiado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O perfil de B pede o caminho Xbox depois de A (DualSense): a troca sai no arme.

    MORDIDA: tire o encerramento e o diário traz `profile_mode_mascara_adiada_jogo_aberto`
    com o pad ainda DualSense (o Future Knight de 23/10).
    """
    _roupa_do_jogo_novo(monkeypatch, EDGE)
    perfil = _perfil(JOGO_B, flavor="xbox", caminho="xbox")
    monkeypatch.setattr(le, "_steam_profiles", lambda _d: [(JOGO_B, perfil)])
    mesa = _Mesa(monkeypatch, "bt", 0)
    mesa.abrir_o_jogo(JOGO_A, EPOCH_A, EDGE)
    mesa.fechar_o_jogo(10.0)
    mesa.lancar(tmp_path, JOGO_B, EPOCH_B)
    assert mesa.d._gamepad_device.flavor == "dualsense"

    with structlog.testing.capture_logs() as diario:
        resultado = _arme(mesa, tmp_path)

    assert resultado is not None and resultado["appid"] == JOGO_B
    assert _linhas(diario, "profile_mode_mascara_adiada_jogo_aberto") == []
    assert _linhas(diario, "vpad_recriacao_bloqueada_por_jogo") == []
    assert mesa.d._gamepad_device.flavor == "xbox", "o caminho Xbox do perfil não foi vestido"


def test_o_tique_seguinte_devolve_o_jogo_novo_a_game(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Depois do encerramento, o marcador de B volta o sinal a `game`, sem esperar nada."""
    _roupa_do_jogo_novo(monkeypatch, EDGE)
    mesa = _Mesa(monkeypatch, "usb", 0)
    mesa.abrir_o_jogo(JOGO_A, EPOCH_A, EDGE)
    mesa.fechar_o_jogo(10.0)
    mesa.lancar(tmp_path, JOGO_B, EPOCH_B)
    _arme(mesa, tmp_path)
    assert mesa.d.display_authority == "daemon"

    mesa.varredura = {
        "marker": (JOGO_B, EPOCH_B), "marker_pid": 4242, "marker_pid_alive": True,
        "now": float(EPOCH_B) + 2,
    }
    mesa.relogio.agora += 2

    assert mesa.tique() == "game"


@pytest.mark.parametrize("pausa_s", [20.0, 29.0])
def test_a_mesma_janela_que_pisca_segue_com_a_histerese(pausa_s: float) -> None:
    """O mesmo jogo some do foco e volta dentro da janela: nenhuma transição.

    MORDIDA: zere a histerese (`HYSTERESIS_SEC` a 0) e a autoridade cai no primeiro
    tique sem jogo.
    """
    relogio = _Relogio()
    sinal = GameSignal(time_fn=relogio)
    jogo = {"appid_de_jogo_vivo": JOGO_A, "window_healthy": True}
    sem_jogo = {"appid_de_jogo_vivo": None, "window_healthy": True}
    base: dict[str, Any] = {
        "window_class_current": None, "window_seen_age": None, "profile_rule_match": False,
        "marker": None, "marker_pid_alive": False, "exit_marker": None, "now": 0.0,
        "session_open": True,
    }

    with structlog.testing.capture_logs() as diario:
        sinal.evaluate(classify(**{**base, **jogo}), session_open=True)
        for _ in range(int(pausa_s // 2)):
            relogio.agora += 2.0
            sinal.evaluate(classify(**{**base, **sem_jogo}), session_open=True)
        sinal.evaluate(classify(**{**base, **jogo}), session_open=True)

    assert sinal.authority == "game"
    assert [(x["de"], x["para"]) for x in _linhas(diario, "game_signal_transition")] == [
        ("unknown", "game")]
    assert HYSTERESIS_SEC == 30.0 and pausa_s < HYSTERESIS_SEC


def test_sem_jogo_a_histerese_de_30s_encerra_como_sempre() -> None:
    """O encerramento explícito não toca a histerese: ela expira aos 30 s sem jogo."""
    relogio = _Relogio()
    sinal = GameSignal(time_fn=relogio)
    base: dict[str, Any] = {
        "window_class_current": None, "window_seen_age": None, "profile_rule_match": False,
        "marker": None, "marker_pid_alive": False, "exit_marker": None, "now": 0.0,
        "window_healthy": True, "session_open": True,
    }
    sinal.evaluate(classify(**base, appid_de_jogo_vivo=JOGO_A), session_open=True)
    assert sinal.authority == "game"
    sinal.evaluate(classify(**base, appid_de_jogo_vivo=None), session_open=True)
    relogio.agora += HYSTERESIS_SEC - 1
    sinal.evaluate(classify(**base, appid_de_jogo_vivo=None), session_open=True)
    assert sinal.authority == "game"
    relogio.agora += 1
    sinal.evaluate(classify(**base, appid_de_jogo_vivo=None), session_open=True)
    assert sinal.authority == "daemon"


def test_encerrar_sem_jogo_na_autoridade_nao_faz_nada() -> None:
    """`encerrar` só age sobre `game`; em `daemon` e `unknown` devolve ``False`` calado."""
    sinal = GameSignal(time_fn=_Relogio())
    with structlog.testing.capture_logs() as diario:
        assert sinal.encerrar("daemon_outro_lancamento") is False
        sinal.evaluate("daemon", session_open=False)
        assert sinal.encerrar("daemon_outro_lancamento") is False
    assert [x["evidencia"] for x in _linhas(diario, "game_signal_transition")] == [
        "daemon_sem_sessao"]


def test_a_varredura_que_falha_deixa_a_autoridade_como_esta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Na dúvida, a autoridade fica: a leitura das evidências levantou, nada se encerra.

    MORDIDA: troque o `except` do arme por «encerrar» e a transição aparece.
    """
    _roupa_do_jogo_novo(monkeypatch, EDGE)
    mesa = _Mesa(monkeypatch, "usb", 0)
    mesa.abrir_o_jogo(JOGO_A, EPOCH_A, COMUM)
    mesa.fechar_o_jogo(10.0)
    mesa.lancar(tmp_path, JOGO_B, EPOCH_B)

    def _quebra() -> dict[str, Any]:
        raise OSError("/proc ilegível")

    mesa.d._gather_game_signal_inputs = _quebra
    with structlog.testing.capture_logs() as diario:
        _arme(mesa, tmp_path)

    assert mesa.d.display_authority == "game"
    assert _linhas(diario, "game_signal_transition") == []


def test_o_tique_que_cruza_o_encerramento_reenvia_as_saidas_retidas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O encerramento defende a tela como a borda `game -> daemon`; o tique que o cruza vê a volta.

    O `_sync_game_signal` lê a autoridade DEPOIS da varredura: se o arme encerrou a
    autoridade enquanto ela rodava, o jogo novo volta a `game` pela evidência dele e o
    tique reenvia as saídas retidas (`replay_retained_game_outputs`).

    MORDIDA: leia o `anterior` antes da espera (como era) e o replay não acontece.
    """
    import asyncio

    _roupa_do_jogo_novo(monkeypatch, EDGE)
    mesa = _Mesa(monkeypatch, "usb", 0)
    eventos: list[str] = []
    mesa.d.controller.defend_display = lambda: eventos.append("defend")
    mesa.d.controller.replay_retained_game_outputs = lambda: eventos.append("replay")
    mesa.abrir_o_jogo(JOGO_A, EPOCH_A, COMUM)
    mesa.fechar_o_jogo(10.0)
    mesa.lancar(tmp_path, JOGO_B, EPOCH_B)

    async def _no_meio_da_varredura(_leitura: Any) -> dict[str, Any]:
        _arme(mesa, tmp_path)  # o ping do wrapper chega enquanto a varredura corre
        mesa.varredura = {
            "marker": (JOGO_B, EPOCH_B), "marker_pid": 4242, "marker_pid_alive": True,
            "now": float(EPOCH_B) + 2,
        }
        return mesa._ler()

    mesa.d._run_blocking = _no_meio_da_varredura
    asyncio.run(mesa.d._sync_game_signal())

    assert eventos == ["defend", "replay"], eventos
    assert mesa.d.display_authority == "game"


def test_o_mesmo_lancamento_arma_uma_vez_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O arme é idempotente por `(appid, epoch)`: a varredura roda UMA vez por lançamento."""
    _roupa_do_jogo_novo(monkeypatch, EDGE)
    mesa = _Mesa(monkeypatch, "usb", 0)
    mesa.abrir_o_jogo(JOGO_A, EPOCH_A, COMUM)
    mesa.fechar_o_jogo(10.0)
    mesa.lancar(tmp_path, JOGO_B, EPOCH_B)
    chamadas: list[int] = []
    leitura = mesa._ler

    def _conta() -> dict[str, Any]:
        chamadas.append(1)
        return leitura()

    mesa.d._gather_game_signal_inputs = _conta
    for _ in range(5):
        _arme(mesa, tmp_path)

    assert len(chamadas) == 1, chamadas


def test_o_arme_so_pergunta_a_varredura_com_o_jogo_na_autoridade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem jogo na autoridade não há o que encerrar: nem `/proc` é varrido."""
    _roupa_do_jogo_novo(monkeypatch, EDGE)
    mesa = _Mesa(monkeypatch, "usb", 0)
    mesa.lancar(tmp_path, JOGO_B, EPOCH_B)
    chamadas: list[int] = []

    def ler_e_contar() -> dict[str, Any]:
        chamadas.append(1)
        return mesa._ler()

    mesa.d._gather_game_signal_inputs = ler_e_contar

    _arme(mesa, tmp_path)

    assert chamadas == []


def test_o_daemon_sem_o_sinal_nao_levanta(tmp_path: Path) -> None:
    """Dublê sem `_game_signal` nem `encerrar_a_autoridade_do_jogo`: o arme segue (R-04 antigo)."""
    (tmp_path / "last_run").write_text(
        f"appid={JOGO_B}\nepoch={EPOCH_B}\npid=1\n", encoding="utf-8"
    )
    daemon = SimpleNamespace(display_authority="game")
    resultado = le.arm_launch_profile(daemon, base_dir=tmp_path, now=float(EPOCH_B) + 1)
    assert resultado is not None and resultado["appid"] == JOGO_B
