"""HONESTIDADE-STEAM-01 — nenhum toast afirma sucesso sobre um no-op."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("test_steam_input_honestidade: importa código da janela GTK")

import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import emulation_actions
from hefesto_dualsense4unix.app.actions.emulation_actions import steam_input_result_tag

BASH = shutil.which("bash") or "/bin/bash"
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "disable_steam_input.sh"

_VDF = (
    '"UserLocalConfigStore"\n'
    "{\n"
    '\t"apps"\n'
    "\t{\n"
    '\t\t"2111190"\n'
    "\t\t{\n"
    '\t\t\t"UseSteamControllerConfig"\t\t"2"\n'
    "\t\t}\n"
    "\t}\n"
    '\t"system"\n'
    "\t{\n"
    '\t\t"SteamController_PSSupport"\t\t"2"\n'
    '\t\t"SteamController_SwitchSupport"\t\t"2"\n'
    "\t}\n"
    "}\n"
)


@pytest.fixture()
def ambiente(tmp_path: Path) -> dict[str, Any]:
    """HOME falso com um localconfig.vdf + stubs de pgrep/steam/pkill/sleep no PATH."""
    home = tmp_path / "home"
    vdf = home / ".steam" / "steam" / "userdata" / "1234" / "config" / "localconfig.vdf"
    vdf.parent.mkdir(parents=True)
    vdf.write_text(_VDF, encoding="utf-8")

    estado = tmp_path / "estado"
    estado.mkdir()
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    runtime = tmp_path / "run"
    runtime.mkdir()

    def _stub(nome: str, corpo: str) -> None:
        caminho = stubs / nome
        caminho.write_text(f"#!/bin/sh\n{corpo}\n", encoding="utf-8")
        caminho.chmod(0o755)

    _stub(
        "pgrep",
        'case "$*" in\n'
        '  *SteamLaunch*) [ -n "${FAKE_GAME:-}" ] && exit 0 ; exit 1 ;;\n'
        "esac\n"
        'if [ -f "$FAKE_STATE/steam_down" ]; then exit 1; fi\n'
        '[ -n "${FAKE_STEAM:-}" ] && exit 0\n'
        "exit 1",
    )
    _stub(
        "steam",
        'printf "%s\\n" "$*" >> "$FAKE_STATE/steam_calls"\n'
        'case "$1" in -shutdown) touch "$FAKE_STATE/steam_down" ;; esac\n'
        "exit 0",
    )
    _stub("pkill", 'printf "%s\\n" "$*" >> "$FAKE_STATE/pkill"\nexit 0')
    dorme = shutil.which("sleep", path="/usr/bin:/bin") or "/bin/sleep"
    _stub("sleep", f"exec {dorme} 0.05")

    return {"home": home, "vdf": vdf, "estado": estado, "stubs": stubs, "runtime": runtime}


def _roda(
    ambiente: dict[str, Any], *args: str, steam: bool = False, jogo: bool = False
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["HOME"] = str(ambiente["home"])
    env["XDG_CONFIG_HOME"] = str(ambiente["home"] / ".config")
    env["XDG_RUNTIME_DIR"] = str(ambiente["runtime"])
    env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={ambiente['runtime'] / 'bus'}"
    env["PATH"] = f"{ambiente['stubs']}:/usr/bin:/bin"
    env["FAKE_STATE"] = str(ambiente["estado"])
    if steam:
        env["FAKE_STEAM"] = "1"
    if jogo:
        env["FAKE_GAME"] = "1"
    return subprocess.run(
        [BASH, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=60,
    )


def _tag(proc: subprocess.CompletedProcess[str]) -> str | None:
    return steam_input_result_tag(proc.stdout + proc.stderr)


class TestContratoDoScript:
    def test_bash_n_limpo(self) -> None:
        proc = subprocess.run(
            ["bash", "-n", str(SCRIPT)], capture_output=True, text=True, check=False
        )
        assert proc.returncode == 0, proc.stderr

    def test_apply_quiet_com_steam_viva_adia_e_diz_que_adiou(
        self, ambiente: dict[str, Any]
    ) -> None:
        """O no-op que a GUI vendia como sucesso — agora ele se identifica."""
        original = ambiente["vdf"].read_text(encoding="utf-8")

        proc = _roda(ambiente, "--apply-quiet", steam=True)

        assert proc.returncode == 0
        assert _tag(proc) == "adiado-steam-aberta"
        assert ambiente["vdf"].read_text(encoding="utf-8") == original
        assert not (ambiente["estado"] / "steam_calls").exists()

    def test_apply_quiet_com_steam_fechada_aplica_e_diz_aplicado(
        self, ambiente: dict[str, Any]
    ) -> None:
        proc = _roda(ambiente, "--apply-quiet")

        assert proc.returncode == 0
        assert _tag(proc) == "aplicado"
        texto = ambiente["vdf"].read_text(encoding="utf-8")
        assert '"SteamController_PSSupport"\t\t"0"' in texto
        assert '"SteamController_SwitchSupport"\t\t"0"' in texto

    def test_segunda_rodada_e_nada_a_fazer(self, ambiente: dict[str, Any]) -> None:
        _roda(ambiente, "--apply-quiet")
        proc = _roda(ambiente, "--apply-quiet")

        assert proc.returncode == 0
        assert _tag(proc) == "nada-a-fazer"

    def test_apply_com_jogo_aberto_recusa_e_nao_encosta_na_steam(
        self, ambiente: dict[str, Any]
    ) -> None:
        """`steam -shutdown` com jogo aberto MATA o jogo (DEDUP-05)."""
        original = ambiente["vdf"].read_text(encoding="utf-8")

        proc = _roda(ambiente, "--apply", steam=True, jogo=True)

        assert proc.returncode == 4
        assert _tag(proc) == "recusado-jogo-aberto"
        assert ambiente["vdf"].read_text(encoding="utf-8") == original
        assert not (ambiente["estado"] / "steam_calls").exists()

    def test_restore_com_jogo_aberto_tambem_recusa(
        self, ambiente: dict[str, Any]
    ) -> None:
        proc = _roda(ambiente, "--restore", steam=True, jogo=True)

        assert proc.returncode == 4
        assert _tag(proc) == "recusado-jogo-aberto"
        assert not (ambiente["estado"] / "steam_calls").exists()

    def test_apply_com_steam_viva_fecha_aplica_e_reabre(
        self, ambiente: dict[str, Any]
    ) -> None:
        proc = _roda(ambiente, "--apply", steam=True)

        assert proc.returncode == 0
        assert _tag(proc) == "aplicado"
        chamadas = (ambiente["estado"] / "steam_calls").read_text(encoding="utf-8")
        assert "-shutdown" in chamadas
        assert not (ambiente["estado"] / "pkill").exists()
        assert "reabrindo Steam" in proc.stdout
        assert '"SteamController_PSSupport"\t\t"0"' in ambiente["vdf"].read_text(
            encoding="utf-8"
        )

    def test_status_nao_toca_e_classifica(self, ambiente: dict[str, Any]) -> None:
        original = ambiente["vdf"].read_text(encoding="utf-8")
        proc = _roda(ambiente, "--status", steam=True)
        assert _tag(proc) == "precisa-corrigir"
        assert ambiente["vdf"].read_text(encoding="utf-8") == original

        _roda(ambiente, "--apply-quiet")
        assert _tag(_roda(ambiente, "--status")) == "nada-a-fazer"

    def test_resultado_e_sempre_a_ultima_linha(
        self, ambiente: dict[str, Any]
    ) -> None:
        """Contrato de parsing: quem lê a saída pega a tag do fim, sempre."""
        proc = _roda(ambiente, "--apply-quiet")
        linhas = [linha for linha in proc.stdout.splitlines() if linha.strip()]
        assert linhas[-1].startswith("[steam-input] resultado=")


_VDF_SO_ALLOWLIST = (
    '"UserLocalConfigStore"\n'
    "{\n"
    '\t"apps"\n'
    "\t{\n"
    '\t\t"2111190"\n'
    "\t\t{\n"
    '\t\t\t"UseSteamControllerConfig"\t\t"2"\n'
    "\t\t}\n"
    '\t\t"3357650"\n'
    "\t\t{\n"
    '\t\t\t"UseSteamControllerConfig"\t\t"2"\n'
    "\t\t}\n"
    "\t}\n"
    '\t"system"\n'
    "\t{\n"
    '\t\t"SteamController_PSSupport"\t\t"0"\n'
    '\t\t"SteamController_SwitchSupport"\t\t"0"\n'
    "\t}\n"
    "}\n"
)


@pytest.fixture()
def bancada_allowlist(ambiente: dict[str, Any]) -> dict[str, Any]:
    """`ambiente`, mas com um vdf que SÓ tem appids da allowlist ligados."""
    ambiente["vdf"].write_text(_VDF_SO_ALLOWLIST, encoding="utf-8")
    lista = (
        ambiente["home"] / ".config" / "hefesto-dualsense4unix" / "steam_input_apps.txt"
    )
    lista.parent.mkdir(parents=True, exist_ok=True)
    lista.write_text(
        "# bancada — jogos cujo DualSense vem pela Steam\n2111190\n3357650\n",
        encoding="utf-8",
    )
    ambiente["allowlist"] = lista
    return ambiente


class TestPreVooNaoFechaSteamAToa:
    """D-32 (05/08/2026) — o pré-voo do apply casava a allowlist e mentia."""

    def test_apply_nao_fecha_a_steam_nem_diz_aplicado(
        self, bancada_allowlist: dict[str, Any]
    ) -> None:
        original = bancada_allowlist["vdf"].read_text(encoding="utf-8")

        proc = _roda(bancada_allowlist, "--apply", steam=True)

        assert proc.returncode == 0
        assert _tag(proc) == "nada-a-fazer", proc.stdout
        assert not (bancada_allowlist["estado"] / "steam_calls").exists()
        assert bancada_allowlist["vdf"].read_text(encoding="utf-8") == original

    def test_apply_quiet_do_guarda_tambem_para_de_dizer_aplicado(
        self, bancada_allowlist: dict[str, Any]
    ) -> None:
        """É o modo do timer de 30 min — a origem do `resultado=aplicado` das 02:13."""
        original = bancada_allowlist["vdf"].read_text(encoding="utf-8")

        proc = _roda(bancada_allowlist, "--apply-quiet")

        assert proc.returncode == 0
        assert _tag(proc) == "nada-a-fazer", proc.stdout
        assert bancada_allowlist["vdf"].read_text(encoding="utf-8") == original

    def test_jogo_fora_da_allowlist_continua_fechando_e_aplicando(
        self, bancada_allowlist: dict[str, Any]
    ) -> None:
        """Contraprova: a cura não anestesiou o guarda."""
        bancada_allowlist["vdf"].write_text(
            _VDF_SO_ALLOWLIST.replace('"3357650"', '"1599660"'), encoding="utf-8"
        )

        proc = _roda(bancada_allowlist, "--apply", steam=True)

        assert proc.returncode == 0
        assert _tag(proc) == "aplicado", proc.stdout
        chamadas = (bancada_allowlist["estado"] / "steam_calls").read_text(
            encoding="utf-8"
        )
        assert "-shutdown" in chamadas
        assert not (bancada_allowlist["estado"] / "pkill").exists()
        texto = bancada_allowlist["vdf"].read_text(encoding="utf-8")
        assert texto.count('"UseSteamControllerConfig"\t\t"0"') == 1
        assert texto.count('"UseSteamControllerConfig"\t\t"2"') == 1


class TestTagParser:
    def test_pega_a_ultima_tag(self) -> None:
        saida = (
            "[steam-input] resultado=nada-a-fazer\n"
            "[steam-input] barulho\n"
            "[steam-input] resultado=aplicado\n"
        )
        assert steam_input_result_tag(saida) == "aplicado"

    @pytest.mark.parametrize("saida", ["", "nada aqui", "resultado=aplicado"])
    def test_sem_tag_devolve_none(self, saida: str) -> None:
        """Script de instalação ANTIGA não emite a linha — e isso é dito, não"""
        assert steam_input_result_tag(saida) is None


class _StubEmu(emulation_actions.EmulationActionsMixin):
    def __init__(self) -> None:
        self.toasts: list[str] = []
        self.refreshes = 0
        self.window = None

    def _status_toast(self, _ctx: str, msg: str) -> None:
        self.toasts.append(msg)

    def _refresh_steam_input_status(self) -> None:  # type: ignore[override]
        self.refreshes += 1

    def _steam_input_script(self):  # type: ignore[override]
        return Path("/fake/disable_steam_input.sh")


@pytest.fixture()
def sincrono(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        emulation_actions,
        "_get_executor",
        lambda: SimpleNamespace(submit=lambda fn: fn()),
    )
    monkeypatch.setattr(
        emulation_actions,
        "GLib",
        SimpleNamespace(idle_add=lambda fn, *args: fn(*args)),
    )


@pytest.fixture()
def slo_fake(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    caixa: dict[str, Any] = {
        "steam": False,
        "jogo": False,
        "parou": 0,
        "reabriu": 0,
        "rc": 0,
        "saida": "[steam-input] resultado=aplicado\n",
        "runs": [],
    }
    monkeypatch.setattr(slo, "steam_running", lambda: caixa["steam"])
    monkeypatch.setattr(slo, "steam_game_running", lambda: caixa["jogo"])

    def _stop() -> bool:
        caixa["parou"] += 1
        caixa["steam"] = False
        return True

    monkeypatch.setattr(slo, "stop_steam", _stop)
    monkeypatch.setattr(
        slo, "reopen_steam", lambda: caixa.__setitem__("reabriu", caixa["reabriu"] + 1)
    )

    def _run(args, **kwargs):
        caixa["runs"].append(list(args))
        return SimpleNamespace(
            returncode=caixa["rc"], stdout=caixa["saida"], stderr=""
        )

    monkeypatch.setattr(
        emulation_actions, "subprocess", SimpleNamespace(run=_run, SubprocessError=Exception)
    )
    return caixa


