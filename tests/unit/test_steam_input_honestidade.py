"""HONESTIDADE-STEAM-01 — nenhum toast afirma sucesso sobre um no-op.

O bug curado (medido 25/07): o botão "Desligar Steam Input" da aba Emulação

  1. mostrava "desligando Steam Input (fecha e reabre a Steam)…" — e o
     tooltip do glade prometia o mesmo;
  2. rodava `scripts/disable_steam_input.sh --apply-quiet`, cujo contrato é
     literalmente "nunca fecha a Steam; se ela está viva, ADIA e sai 0";
  3. anunciava "Steam Input desligado" INCONDICIONALMENTE (`check=False` +
     `contextlib.suppress` engoliam rc e exceção).

Ou seja: prometia fechar a Steam e não fechava, e afirmava sucesso sobre uma
execução que não tocou em nada. Este arquivo trava as três pernas da cura:

- **script**: emite `[steam-input] resultado=<tag>` como ÚLTIMA linha e RECUSA
  (exit 4) quando há um JOGO da Steam aberto — testado por EXECUÇÃO real do
  bash com HOME em tmp e `pgrep`/`steam`/`sleep` stubados no PATH (nenhum
  processo da máquina é tocado);
- **formatter puro**: "Pronto" exige evidência (releitura do vdf);
- **handler**: jogo aberto ⇒ recusa; Steam viva ⇒ pede permissão para fechar;
  Steam fechada ⇒ aplica direto.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import daemon_actions, emulation_actions
from hefesto_dualsense4unix.app.actions.emulation_actions import (
    format_steam_input_result,
    steam_input_result_tag,
)
from tests.conftest import skip_sem_gtk_response

BASH = shutil.which("bash") or "/bin/bash"
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "disable_steam_input.sh"

# VDF mínimo no formato REAL da Steam: tabs LITERAIS entre chave e valor (é o
# que o awk do script casa — espaço no lugar de tab não seria reescrito).
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


# ---------------------------------------------------------------------------
# 1. O script: contrato `resultado=` + recusa com jogo aberto (bash de verdade)
# ---------------------------------------------------------------------------


@pytest.fixture()
def ambiente(tmp_path: Path) -> dict[str, Any]:
    """HOME falso com um localconfig.vdf + stubs de pgrep/steam/sleep no PATH.

    `sleep` vira no-op para o `stop_steam` (loop de 15 voltas de 2 s + margem) não
    custar 30 s de suíte; `steam` só registra o que foi pedido — nada na
    máquina é fechado.
    """
    home = tmp_path / "home"
    vdf = home / ".steam" / "steam" / "userdata" / "1234" / "config" / "localconfig.vdf"
    vdf.parent.mkdir(parents=True)
    vdf.write_text(_VDF, encoding="utf-8")

    estado = tmp_path / "estado"
    estado.mkdir()
    stubs = tmp_path / "stubs"
    stubs.mkdir()

    def _stub(nome: str, corpo: str) -> None:
        caminho = stubs / nome
        caminho.write_text(f"#!/bin/sh\n{corpo}\n", encoding="utf-8")
        caminho.chmod(0o755)

    # O stub distingue as TRÊS consultas do script: jogo (SteamLaunch AppId=),
    # runtime da Steam (steamrt64/steam) e webhelper (nome exato).
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
    _stub("sleep", "exit 0")

    return {"home": home, "vdf": vdf, "estado": estado, "stubs": stubs}


def _roda(
    ambiente: dict[str, Any], *args: str, steam: bool = False, jogo: bool = False
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["HOME"] = str(ambiente["home"])
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

        assert proc.returncode == 0  # contrato do guard oneshot: adiar não é falhar
        assert _tag(proc) == "adiado-steam-aberta"
        assert ambiente["vdf"].read_text(encoding="utf-8") == original
        assert not (ambiente["estado"] / "steam_calls").exists()  # não fechou nada

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
        """`steam -shutdown` com jogo aberto MATA o jogo (DEDUP-05).

        O gate mora no SCRIPT (e não só em quem chama) porque install.sh,
        purge.sh e a GUI chamam `--apply` direto. A prova de que nada foi
        derrubado é a ausência do arquivo de chamadas do stub `steam`.
        """
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
        # A reabertura é DESANEXADA (`setsid nohup steam &`), então checá-la
        # pelo arquivo do stub seria corrida — o sinal determinístico é o log.
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
        """Script de instalação ANTIGA não emite a linha — e isso é dito, não
        fingido (o formatter cai no ramo "sem confirmação")."""
        assert steam_input_result_tag(saida) is None


# ---------------------------------------------------------------------------
# 2. O formatter: "Pronto" exige evidência
# ---------------------------------------------------------------------------


class TestFormatSteamInputResult:
    def test_sucesso_so_com_vdf_conferido(self) -> None:
        msg = format_steam_input_result(
            status="executado", rc=0, tag="aplicado", ainda_ligado=False
        )
        assert "Pronto" in msg

    def test_rodou_mas_continua_ligado_nao_diz_pronto(self) -> None:
        """O caso que a versão antiga chamava de sucesso: script sai 0 e o
        estado no disco não mudou."""
        msg = format_steam_input_result(
            status="executado", rc=0, tag="aplicado", ainda_ligado=True
        )
        assert "Pronto" not in msg
        assert "CONTINUA ligado" in msg

    def test_adiado_diz_que_nada_mudou(self) -> None:
        msg = format_steam_input_result(
            status="executado", rc=0, tag="adiado-steam-aberta", ainda_ligado=True
        )
        assert "Pronto" not in msg
        assert "ADIADA" in msg
        assert "nada mudou" in msg

    def test_rc_nao_zero_nao_diz_pronto(self) -> None:
        msg = format_steam_input_result(
            status="executado", rc=1, tag="erro", ainda_ligado=False
        )
        assert "Pronto" not in msg
        assert "erro 1" in msg

    def test_jogo_aberto_recusa_e_explica_o_risco(self) -> None:
        msg = format_steam_input_result(status="jogo_aberto")
        assert "jogo aberto" in msg
        assert "progresso" in msg
        assert "Nada foi mudado" in msg

    def test_cancelado_nao_promete_nada(self) -> None:
        msg = format_steam_input_result(status="cancelado")
        assert "Nada foi mudado" in msg
        assert "Pronto" not in msg

    def test_steam_nao_fechou(self) -> None:
        msg = format_steam_input_result(status="nao_fechou")
        assert "não fechou" in msg
        assert "Pronto" not in msg

    def test_sem_script_aponta_o_install(self) -> None:
        msg = format_steam_input_result(status="sem_script")
        assert "install.sh" in msg

    def test_nada_a_fazer(self) -> None:
        msg = format_steam_input_result(
            status="executado", rc=0, tag="nada-a-fazer", ainda_ligado=False
        )
        assert "já estava desligado" in msg

    def test_indeterminado_admite_que_nao_conferiu(self) -> None:
        msg = format_steam_input_result(
            status="executado", rc=0, tag=None, ainda_ligado=None
        )
        assert "Pronto" not in msg
        assert "não consegui conferir" in msg

    @pytest.mark.parametrize(
        ("status", "tag", "ainda"),
        [
            ("executado", "adiado-steam-aberta", None),
            ("executado", "recusado-jogo-aberto", None),
            ("executado", "erro", None),
            ("executado", None, True),
            ("jogo_aberto", None, None),
            ("cancelado", None, None),
            ("nao_fechou", None, None),
            ("sem_script", None, None),
        ],
    )
    def test_nenhum_caminho_sem_evidencia_diz_pronto(
        self, status: str, tag: str | None, ainda: bool | None
    ) -> None:
        """Regra-muralha: 'Pronto' SÓ com ainda_ligado=False e rc=0."""
        msg = format_steam_input_result(
            status=status, rc=0, tag=tag, ainda_ligado=ainda
        )
        assert "Pronto" not in msg


# ---------------------------------------------------------------------------
# 3. O handler: recusa / consentimento / aplicação direta
# ---------------------------------------------------------------------------


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


class TestHandlerDesligarSteamInput:
    def test_jogo_aberto_recusa_sem_rodar_nada(
        self, sincrono: None, slo_fake: dict[str, Any], monkeypatch
    ) -> None:
        slo_fake["jogo"] = True
        slo_fake["steam"] = True
        stub = _StubEmu()

        stub.on_emulation_steam_input_disable(None)

        assert slo_fake["runs"] == []
        assert slo_fake["parou"] == 0
        assert any("jogo aberto" in t for t in stub.toasts)

    def test_steam_fechada_aplica_direto_sem_dialogo(
        self, sincrono: None, slo_fake: dict[str, Any], monkeypatch
    ) -> None:
        chamou_dialogo = []
        monkeypatch.setattr(
            daemon_actions,
            "build_steam_close_consent_dialog",
            lambda *a, **k: chamou_dialogo.append(True),
        )
        stub = _StubEmu()
        monkeypatch.setattr(_StubEmu, "_steam_input_is_on", staticmethod(lambda: False))

        stub.on_emulation_steam_input_disable(None)

        assert chamou_dialogo == []
        assert slo_fake["runs"] and "--apply-quiet" in slo_fake["runs"][0]
        assert slo_fake["parou"] == 0
        assert any("Pronto" in t for t in stub.toasts)

    def test_steam_viva_pede_permissao_e_nao_fecha_sozinha(
        self, sincrono: None, slo_fake: dict[str, Any], monkeypatch
    ) -> None:
        """`stop_steam` escala para pkill -KILL: jamais sem sim explícito."""
        slo_fake["steam"] = True
        capturado: dict[str, Any] = {}

        def _fake_dialog(_parent, **kwargs):
            capturado.update(kwargs)
            return SimpleNamespace(show_all=lambda: None)

        monkeypatch.setattr(
            daemon_actions, "build_steam_close_consent_dialog", _fake_dialog
        )
        stub = _StubEmu()

        stub.on_emulation_steam_input_disable(None)

        assert capturado, "nenhum diálogo de consentimento foi montado"
        assert "20 segundos" in capturado["titulo"]
        assert "pause os downloads" in capturado["corpo"].lower()
        assert slo_fake["runs"] == []  # nada rodou ainda
        assert slo_fake["parou"] == 0  # e a Steam segue viva

    @skip_sem_gtk_response
    def test_cancelar_no_dialogo_nao_muda_nada(
        self, sincrono: None, slo_fake: dict[str, Any], monkeypatch
    ) -> None:
        from gi.repository import Gtk

        slo_fake["steam"] = True
        capturado: dict[str, Any] = {}
        monkeypatch.setattr(
            daemon_actions,
            "build_steam_close_consent_dialog",
            lambda _p, **kw: (capturado.update(kw), SimpleNamespace(show_all=lambda: None))[1],
        )
        stub = _StubEmu()
        stub.on_emulation_steam_input_disable(None)

        capturado["on_response"](
            SimpleNamespace(destroy=lambda: None), int(Gtk.ResponseType.CANCEL)
        )

        assert slo_fake["runs"] == []
        assert slo_fake["parou"] == 0
        assert any("Nada foi mudado" in t for t in stub.toasts)

    @skip_sem_gtk_response
    def test_ok_no_dialogo_fecha_aplica_e_reabre(
        self, sincrono: None, slo_fake: dict[str, Any], monkeypatch
    ) -> None:
        from gi.repository import Gtk

        slo_fake["steam"] = True
        capturado: dict[str, Any] = {}
        monkeypatch.setattr(
            daemon_actions,
            "build_steam_close_consent_dialog",
            lambda _p, **kw: (capturado.update(kw), SimpleNamespace(show_all=lambda: None))[1],
        )
        monkeypatch.setattr(_StubEmu, "_steam_input_is_on", staticmethod(lambda: False))
        stub = _StubEmu()
        stub.on_emulation_steam_input_disable(None)

        capturado["on_response"](
            SimpleNamespace(destroy=lambda: None), int(Gtk.ResponseType.OK)
        )

        assert slo_fake["parou"] == 1
        assert slo_fake["reabriu"] == 1
        assert slo_fake["runs"] and "--apply-quiet" in slo_fake["runs"][0]
        assert any("Pronto" in t for t in stub.toasts)
        assert stub.refreshes >= 1

    def test_script_ausente_aponta_o_install(
        self, sincrono: None, slo_fake: dict[str, Any], monkeypatch
    ) -> None:
        monkeypatch.setattr(_StubEmu, "_steam_input_script", lambda _self: None)
        stub = _StubEmu()

        stub.on_emulation_steam_input_disable(None)

        assert any("install.sh" in t for t in stub.toasts)
        assert slo_fake["runs"] == []

    def test_falha_de_execucao_vira_frase_e_nao_silencio(
        self, sincrono: None, slo_fake: dict[str, Any], monkeypatch
    ) -> None:
        """Worker no executor engole exceção não tratada — e toast que nunca
        chega é a mesma doença do "desligado" incondicional, ao contrário."""

        def _explode(_args, **_kwargs):
            raise OSError("bash sumiu")

        monkeypatch.setattr(
            emulation_actions,
            "subprocess",
            SimpleNamespace(run=_explode, SubprocessError=Exception),
        )
        stub = _StubEmu()

        stub.on_emulation_steam_input_disable(None)

        assert any("Não consegui rodar o script" in t for t in stub.toasts)
        assert not any("Pronto" in t for t in stub.toasts)
