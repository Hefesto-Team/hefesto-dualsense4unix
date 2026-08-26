"""SINAL-DE-JOGO-01/E4 — o jogo VIVO é evidência, e a árvore da Steam não é.

A sprint
`docs/process/sprints/2026-07-31-SINAL-DE-JOGO-01-o-daemon-desiste-do-jogo-antes-do-jogo-acabar.md`
mediu que a autoridade de exibição vivia pendurada em evidências que dependem
todas de o detector de janela enxergar (nº 1 e nº 2) ou de o jogo ter passado
pelo wrapper (nº 3) — e o jogo dela **não passa pelo wrapper**. Pior: a
evidência nº 3 avalia o teto de frescor do marker (`WRAPPER_MARKER_WINDOW_SEC`,
900 s) **antes** de olhar o pid (`launch_env.wrapper_game_running`), então uma
partida mais longa que 15 minutos deixava de ser evidência com o processo do
jogo de pé. No meio da partida a autoridade caía, o produto repintava a barra de
luz e devolvia o controle ao desktop sem nada ter acontecido no jogo.

A cura é a evidência E4: o PROCESSO do jogo vivo, por varredura independente do
wrapper (`steam_launch_options.steam_game_running_appid`, que a casa já tinha e
o sinal de jogo ignorava).

Os dois testes são espelho um do outro, e é o par que morde:

- `test_jogo_vivo_sem_wrapper_e_evidencia` — marker VENCIDO e pid do jogo vivo:
  o sinal não cai. Arrancada a E4, o veredito volta a `daemon` e ele reprova.
- `test_steam_viva_nao_e_jogo` — vivos **apenas** `steam`, `steamwebhelper` e
  `reaper`: o sinal não sobe. É o incidente das 14:42 escrito como teste (o
  cliente Steam sem jogo nenhum escreveu lightbar/player-LEDs e o daemon passou
  a defender a cor dele), e é o que reprova a implementação preguiçosa — varrer
  a árvore da Steam inteira e chamar qualquer processo dela de jogo.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.launch_env import (
    WRAPPER_MARKER_WINDOW_SEC,
    wrapper_game_running,
)
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems.game_signal import GameSignal, classify
from hefesto_dualsense4unix.integrations import steam_launch_options as slo
from hefesto_dualsense4unix.testing import FakeController

#: Appid e cmdline reais do disco dela (copiados de `test_steam_launch_scan.py`,
#: que os mediu em 12/08): é o `reaper` COM `SteamLaunch AppId=<dígitos>` — a
#: única forma da árvore da Steam que atesta um jogo em execução.
APPID = 1599660
REAPER_COM_JOGO = (
    "/home/vitoriamaria/.steam/debian-installation/ubuntu12_32/reaper "
    f"SteamLaunch AppId={APPID} -- /.../proton waitforexitandrun /.../Launcher.exe"
)

#: A árvore da Steam SEM jogo nenhum: o cliente, o CEF da loja/biblioteca, e um
#: `reaper` sem `SteamLaunch AppId=` — os três nomes que a sprint nomeia como
#: "não são jogo" e que a varredura preguiçosa aceitaria.
PROC_STEAM_SEM_JOGO = {
    "1000": "/usr/bin/steam",
    "1001": "/home/vitoriamaria/.steam/.../steamwebhelper --type=utility",
    "1002": "/home/vitoriamaria/.steam/.../reaper",
}


@pytest.fixture(autouse=True)
def _sem_foto_herdada() -> Any:
    """A varredura tem memória de 5 s (BG-03) e ela sobrevive ao teste.

    Sem este reset o `/proc` sintético de um caso responde pelo do seguinte —
    medido em `test_steam_launch_scan.py`, onde quatro de onze reprovavam por
    herança e não por defeito.
    """
    slo.invalidar_varredura_de_proc()
    yield
    slo.invalidar_varredura_de_proc()


def _proc_falso(monkeypatch: pytest.MonkeyPatch, mapa: dict[str, str]) -> None:
    """Instala um `/proc` sintético para a varredura da casa (mesma costura
    de `test_steam_launch_scan.py`: a leitura de cmdline e o `listdir`)."""
    monkeypatch.setattr(slo, "_cmdline_of", lambda pid: mapa.get(str(pid), ""))
    monkeypatch.setattr(slo.os, "listdir", lambda path: [*mapa, "self", "cpuinfo"])


def _launch_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Aponta o diretório do wrapper para um tmp — sem isto o teste leria
    `~/.local/state/hefesto-dualsense4unix/launch_env` da máquina real e a
    evidência nº 3 poderia salvar o veredito sozinha."""
    import hefesto_dualsense4unix.daemon.launch_env as le_mod

    destino = tmp_path / "launch_env"
    destino.mkdir(exist_ok=True)
    monkeypatch.setattr(le_mod, "launch_env_dir", lambda ensure=False: destino)
    return destino


def _sem_perfis(monkeypatch: pytest.MonkeyPatch) -> None:
    """Apaga a evidência nº 2: nenhum perfil no disco casa coisa nenhuma."""
    from hefesto_dualsense4unix.profiles import manager as manager_module

    monkeypatch.setattr(manager_module, "load_all_profiles", lambda: [])


def _daemon_no_desktop() -> Daemon:
    """Daemon com o detector de janela SÃO e olhando o desktop.

    É o cenário que apaga a evidência nº 1 (a janela em foco não é
    `steam_app_*` e nada de jogo foi visto) e que faz `classify` responder
    `daemon` quando não sobra evidência nenhuma — sem isto, um veredito `game`
    não provaria nada sobre a E4.
    """
    daemon = Daemon(
        controller=FakeController(transport="usb"),
        config=DaemonConfig(ipc_enabled=False, udp_enabled=False),
    )
    daemon.store.set_window_detect_backend("xlib", healthy=True)
    daemon.store.record_window_detect_read(
        "xlib", "firefox", wm_name="Ache aqui — Navegador", exe_basename="firefox"
    )
    return daemon


def test_jogo_vivo_sem_wrapper_e_evidencia(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Marker VENCIDO, pid do jogo vivo: a autoridade não cai.

    O teto de frescor do marker (900 s) é avaliado ANTES do pid, então a
    evidência nº 3 está morta aqui — e o teste prova isso, em vez de supor.
    O que segura a autoridade é a E4, que não tem teto: enquanto o processo do
    jogo estiver vivo, ele é evidência.
    """
    destino = _launch_env(monkeypatch, tmp_path)
    _sem_perfis(monkeypatch)

    meu_pid = os.getpid()  # garantidamente vivo: é o processo deste teste
    agora = int(time.time())
    vencido_ha = int(WRAPPER_MARKER_WINDOW_SEC) + 900  # 30 min de partida
    (destino / "last_run").write_text(
        f"appid={APPID}\nepoch={agora - vencido_ha}\npid={meu_pid}\n",
        encoding="utf-8",
    )
    _proc_falso(monkeypatch, {str(meu_pid): REAPER_COM_JOGO, "1": "/sbin/init"})

    daemon = _daemon_no_desktop()
    inputs = daemon._gather_game_signal_inputs()

    # O cenário é o que se diz que é: marker no disco, pid vivo, e as outras
    # três evidências apagadas.
    assert inputs["marker"] == (APPID, agora - vencido_ha)
    assert inputs["marker_pid_alive"] is True
    assert inputs["window_seen_age"] is None
    assert inputs["profile_rule_match"] is False
    # E a evidência nº 3 está MORTA por causa do teto — é o defeito, medido:
    assert (
        wrapper_game_running(
            marker=inputs["marker"],
            exit_marker=inputs["exit_marker"],
            pid_alive=inputs["marker_pid_alive"],
            marker_pid=inputs["marker_pid"],
            exit_pid=inputs["exit_pid"],
            now=inputs["now"],
        )
        is False
    ), "o teto de frescor tinha de ter vencido — senão este teste mede outra coisa"

    assert inputs["appid_de_jogo_vivo"] == APPID
    assert classify(**inputs) == "game", (
        "jogo vivo com marker vencido tem de continuar sendo evidência — "
        f"appid_de_jogo_vivo={inputs['appid_de_jogo_vivo']!r}"
    )

    # E o SINAL, não só o veredito cru: com a sessão aberta, a autoridade que
    # já estava em `game` não cai.
    sinal = GameSignal()
    sinal.evaluate("game", session_open=True)
    assert sinal.evaluate(classify(**inputs), session_open=True) == "game"


def test_steam_viva_nao_e_jogo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Vivos só `steam`, `steamwebhelper` e `reaper`: a autoridade não sobe.

    O incidente das 14:42 como teste. Uma varredura preguiçosa — qualquer
    processo da árvore da Steam conta — devolve `game` aqui, o daemon passa a
    defender a cor que o CLIENTE Steam escreveu, e o defeito que o subsistema
    existe para curar volta por dentro da cura.
    """
    _launch_env(monkeypatch, tmp_path)  # sem `last_run`: nada de marker
    _sem_perfis(monkeypatch)
    _proc_falso(monkeypatch, dict(PROC_STEAM_SEM_JOGO))

    daemon = _daemon_no_desktop()
    inputs = daemon._gather_game_signal_inputs()

    assert inputs["marker"] is None
    assert inputs["profile_rule_match"] is False
    assert inputs["window_seen_age"] is None

    # A cmdline que a varredura CANÔNICA da casa aceitou (None = nenhuma).
    # Ela entra na mensagem porque é o que separa "a régua canônica afrouxou"
    # de "alguém trocou a régua por uma mais frouxa".
    aceito = slo._steam_launch_cmdline()
    processos = sorted(PROC_STEAM_SEM_JOGO.values())
    assert inputs["appid_de_jogo_vivo"] is None, (
        "a árvore da Steam SEM jogo virou evidência de jogo "
        f"(appid_de_jogo_vivo={inputs['appid_de_jogo_vivo']!r}). "
        f"A varredura canônica aceitou a cmdline {aceito!r}; o /proc deste "
        f"teste só tinha estes processos, e nenhum deles é jogo: {processos}"
    )
    assert classify(**inputs) == "daemon", (
        "sem jogo nenhum vivo o veredito tem de ser `daemon` — "
        f"appid_de_jogo_vivo={inputs['appid_de_jogo_vivo']!r}, "
        f"cmdline aceita pela varredura canônica: {aceito!r}, "
        f"processos do /proc do teste: {processos}"
    )


def test_jogo_vivo_sem_marker_nenhum_e_evidencia(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O caso dela, medido em 31/07: **o jogo não passa pelo wrapper**.

    Sem marker nenhum no disco, a varredura de `/proc` é a única perna de pé —
    e o pid do jogo não é o do processo do teste, então o caminho rápido pelo
    marker não existe: quem responde é a varredura completa.
    """
    _launch_env(monkeypatch, tmp_path)  # sem `last_run`
    _sem_perfis(monkeypatch)
    _proc_falso(
        monkeypatch,
        {"1": "/sbin/init", "4242": REAPER_COM_JOGO, **PROC_STEAM_SEM_JOGO},
    )

    daemon = _daemon_no_desktop()
    inputs = daemon._gather_game_signal_inputs()

    assert inputs["marker"] is None
    assert inputs["marker_pid_alive"] is False
    assert inputs["appid_de_jogo_vivo"] == APPID
    assert classify(**inputs) == "game"


def test_appid_zero_nao_e_jogo() -> None:
    """`AppId=0` não identifica jogo nenhum, e a agulha `SteamLaunch AppId=\\d`
    casa o zero. O contrapeso mora em `classify`, que é onde a evidência é
    lida — sem ele, um launch degenerado autorizaria a autoridade."""
    base = dict(
        window_healthy=True,
        window_class_current="firefox",
        window_seen_age=None,
        profile_rule_match=False,
        marker=None,
        marker_pid_alive=False,
        exit_marker=None,
        session_open=False,
        now=time.time(),
    )
    assert classify(**base, appid_de_jogo_vivo=0) == "daemon"
    assert classify(**base, appid_de_jogo_vivo=None) == "daemon"
    assert classify(**base, appid_de_jogo_vivo=APPID) == "game"
