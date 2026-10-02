"""STEAM-INPUT-01/E7 — o vigia do Steam Input não pode nascer `elapsed`."""
from __future__ import annotations

from tests.conftest import exigir_gi_real, olhar_insumo

exigir_gi_real("o vigia do Steam Input não nasce morto")

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]
UNIDADES_DO_VIGIA = (
    RAIZ / "assets" / "hefesto-steam-input-guard.timer",
    RAIZ / "assets" / "hefesto-steam-input-guard.path",
    RAIZ / "assets" / "hefesto-steam-input-guard.service",
)
TIMER = UNIDADES_DO_VIGIA[0]

SHOW_MORTO = """\
NextElapseUSecRealtime=
NextElapseUSecMonotonic=infinity
LoadState=loaded
ActiveState=active
SubState=elapsed
UnitFileState=enabled
"""

SHOW_VIVO = """\
NextElapseUSecRealtime=
NextElapseUSecMonotonic=18h 39min 15.342126s
LoadState=loaded
ActiveState=active
SubState=waiting
UnitFileState=enabled
"""

SHOW_PARADO_HABILITADO = """\
NextElapseUSecRealtime=
NextElapseUSecMonotonic=infinity
LoadState=loaded
ActiveState=inactive
SubState=dead
UnitFileState=enabled
"""

SHOW_DESLIGADO_DE_PROPOSITO = """\
NextElapseUSecRealtime=
NextElapseUSecMonotonic=infinity
LoadState=loaded
ActiveState=inactive
SubState=dead
UnitFileState=disabled
"""

SHOW_AUSENTE = """\
NextElapseUSecRealtime=
NextElapseUSecMonotonic=infinity
LoadState=not-found
ActiveState=inactive
SubState=dead
UnitFileState=
"""

SHOW_VIVO_CALENDARIO = """\
NextElapseUSecRealtime=Sat 2026-08-22 20:30:00 -03
NextElapseUSecMonotonic=0
LoadState=loaded
ActiveState=active
SubState=waiting
UnitFileState=enabled
"""


def _campos_do_timer() -> dict[str, str]:
    """Chaves da seção `[Timer]` da unidade entregue."""
    campos: dict[str, str] = {}
    secao = ""
    for linha in TIMER.read_text(encoding="utf-8").splitlines():
        crua = linha.strip()
        if crua.startswith("[") and crua.endswith("]"):
            secao = crua
            continue
        if secao != "[Timer]" or not crua or crua.startswith("#"):
            continue
        chave, sep, valor = crua.partition("=")
        if sep:
            campos[chave.strip()] = valor.strip()
    return campos


class TestAUnidadeConsertada:
    def test_persistent_nao_volta_sem_oncalendar(self) -> None:
        """A linha que matava o vigia."""
        campos = _campos_do_timer()
        if "Persistent" in campos:
            assert "OnCalendar" in campos, (
                "`Persistent=` sem `OnCalendar=` não agenda nada e MATA o timer: "
                "ele lê o carimbo do disco, o systemd desabilita o `OnBootSec=` "
                "como disparo já ocorrido, o `OnUnitActiveSec=` fica sem âncora "
                "e a unidade nasce `elapsed`. Medido em 22/08/2026, systemd 255."
            )

    def test_sobra_uma_base_que_dispara_sem_ancora(self) -> None:
        """Numa instalação nova o serviço nunca rodou — algo tem de disparar."""
        campos = _campos_do_timer()
        bases_independentes = {"OnBootSec", "OnStartupSec", "OnActiveSec", "OnCalendar"}
        assert bases_independentes & set(campos), (
            "o timer só tem bases que dependem de uma ativação anterior do "
            f"serviço; chaves presentes: {sorted(campos)}"
        )
        assert "OnUnitActiveSec" in campos, "o vigia perdeu a repetição periódica"

    def test_as_unidades_nao_apontam_para_sprint_fantasma(self) -> None:
        """E8: as três unidades citavam `FEAT-STEAM-INPUT-SELF-HEAL-01.md`, que"""
        conferidos = 0
        dispensados: list[str] = []
        for unidade in UNIDADES_DO_VIGIA:
            for linha in unidade.read_text(encoding="utf-8").splitlines():
                if not linha.startswith("# doc:"):
                    continue
                relativo = linha.split(":", 1)[1].strip()
                assert relativo.startswith("docs/usage/"), (
                    f"{unidade.name} aponta `# doc:` para {relativo}: a unidade "
                    "vai para a máquina de quem instala, e o seu documento tem "
                    "de ser uma página de uso (docs/usage/)"
                )
                insumo = olhar_insumo(relativo)
                if insumo.nao_viaja:
                    dispensados.append(f"{unidade.name} -> {insumo.razao}")
                    continue
                conferidos += 1
                assert (RAIZ / relativo).is_file(), (
                    f"{unidade.name} aponta para {Path(relativo).name}, que não existe"
                )

        if conferidos == 0:
            pytest.skip(
                "nenhum `# doc:` das três unidades veio para esta árvore: "
                + "; ".join(dispensados)
            )


LAB = "zz-hefesto-prova-vigia"


def _proximo_disparo_do_lab(corpo_do_timer: str) -> tuple[str, str]:
    """Instala um timer descartável com `corpo_do_timer` e mede o que o systemd"""
    unidades = Path.home() / ".config" / "systemd" / "user"
    carimbo = Path.home() / ".local" / "share" / "systemd" / "timers" / f"stamp-{LAB}.timer"
    servico = unidades / f"{LAB}.service"
    timer = unidades / f"{LAB}.timer"

    def _sc(*args: str) -> None:
        subprocess.run(["systemctl", "--user", *args], check=False, timeout=15)

    _sc("stop", f"{LAB}.timer")
    servico.unlink(missing_ok=True)
    timer.unlink(missing_ok=True)
    _sc("daemon-reload")

    unidades.mkdir(parents=True, exist_ok=True)
    servico.write_text(
        "[Unit]\nDescription=prova do vigia\n"
        "[Service]\nType=oneshot\nExecStart=/usr/bin/true\n",
        encoding="utf-8",
    )
    timer.write_text(
        f"[Unit]\nDescription=prova do vigia\n[Timer]\n{corpo_do_timer}\n"
        f"Unit={LAB}.service\n",
        encoding="utf-8",
    )
    _sc("daemon-reload")
    carimbo.parent.mkdir(parents=True, exist_ok=True)
    carimbo.touch()
    _sc("start", f"{LAB}.timer")

    saida = subprocess.run(
        [
            "systemctl", "--user", "show", f"{LAB}.timer",
            "--property=SubState", "--property=NextElapseUSecMonotonic",
        ],
        capture_output=True, text=True, check=False, timeout=15,
    ).stdout
    campos = dict(
        linha.split("=", 1) for linha in saida.splitlines() if "=" in linha
    )
    return campos.get("SubState", ""), campos.get("NextElapseUSecMonotonic", "")


def _limpar_lab() -> None:
    unidades = Path.home() / ".config" / "systemd" / "user"
    subprocess.run(
        ["systemctl", "--user", "stop", f"{LAB}.timer"], check=False, timeout=15
    )
    (unidades / f"{LAB}.timer").unlink(missing_ok=True)
    (unidades / f"{LAB}.service").unlink(missing_ok=True)
    (
        Path.home() / ".local" / "share" / "systemd" / "timers" / f"stamp-{LAB}.timer"
    ).unlink(missing_ok=True)
    subprocess.run(
        ["systemctl", "--user", "daemon-reload"], check=False, timeout=15
    )


@pytest.mark.skipif(
    os.environ.get("HEFESTO_TESTE_SYSTEMD_VIVO") != "1",
    reason="cria units no systemd --user da bancada; opt-in",
)
def test_systemd_vivo_a_unidade_entregue_agenda_o_proximo_disparo() -> None:
    """O A/B de 22/08/2026, executável."""
    corpo = "\n".join(
        linha
        for linha in TIMER.read_text(encoding="utf-8").splitlines()
        if linha.strip()
        and not linha.startswith(("#", "["))
        and not linha.startswith(("Description=", "WantedBy=", "Unit="))
    )
    try:
        controle = _proximo_disparo_do_lab(corpo + "\nPersistent=true")
        entregue = _proximo_disparo_do_lab(corpo)
    finally:
        _limpar_lab()

    assert controle == ("elapsed", "infinity"), (
        "o roteiro não reproduziu mais o defeito de 26/07 — a régua deixou de "
        f"medir o que promete; o controle devolveu {controle}"
    )
    assert entregue[0] == "waiting" and entregue[1] not in {"infinity", ""}, (
        f"a unidade ENTREGUE nasce sem próximo disparo: {entregue}"
    )


class TestARegraDoAchado:
    """A régua responde pelo EFEITO (próximo disparo), não pelo transporte."""

    def test_o_cadaver_diz_active_e_ainda_assim_vira_aviso(self) -> None:
        """ELO-MUDO-01, o motivo de a régua não poder ser `ActiveState`."""
        from hefesto_dualsense4unix.app.actions import daemon_actions as da

        assert "ActiveState=active" in SHOW_MORTO, "a fixture deixou de morder"
        achado = da.interpretar_guarda_do_steam_input(SHOW_MORTO)
        assert achado is not None, (
            "o vigia `elapsed` (sem próximo disparo) passou como saudável"
        )
        tag, msg = achado
        assert tag == "[WARN]"
        assert "rede de segurança" in msg
        assert "não tem próximo disparo" in msg

    def test_o_vigia_parado_mas_habilitado_tambem_vira_aviso(self) -> None:
        from hefesto_dualsense4unix.app.actions import daemon_actions as da

        achado = da.interpretar_guarda_do_steam_input(SHOW_PARADO_HABILITADO)
        assert achado is not None
        assert "não está rodando" in achado[1]

    def test_o_desligar_de_proposito_nao_vira_resmungo(self) -> None:
        """`troubleshooting-8bitdo.md` ensina a desabilitar o vigia para segurar"""
        from hefesto_dualsense4unix.app.actions import daemon_actions as da

        so_o_unitfilestate = SHOW_PARADO_HABILITADO.replace(
            "UnitFileState=enabled", "UnitFileState=disabled"
        )
        assert so_o_unitfilestate == SHOW_DESLIGADO_DE_PROPOSITO, (
            "as duas fixtures deixaram de ser iguais em tudo menos UnitFileState"
        )
        assert da.interpretar_guarda_do_steam_input(SHOW_DESLIGADO_DE_PROPOSITO) is None

    @pytest.mark.parametrize(
        ("rotulo", "saida"),
        [
            ("vigia vivo (monotônico)", SHOW_VIVO),
            ("vigia vivo (calendário)", SHOW_VIVO_CALENDARIO),
            ("vigia não instalado", SHOW_AUSENTE),
            ("vigia desabilitado de propósito", SHOW_DESLIGADO_DE_PROPOSITO),
            ("sem systemctl", ""),
            ("sem saída", None),
        ],
    )
    def test_calado_quando_nao_ha_o_que_dizer(self, rotulo: str, saida: object) -> None:
        """Decisão dela, 22/08/2026: nada de linha permanente dizendo "tudo bem"."""
        from hefesto_dualsense4unix.app.actions import daemon_actions as da

        assert da.interpretar_guarda_do_steam_input(saida) is None, (
            f"o cartão ganhou linha permanente no caso: {rotulo}"
        )


class _ExecutorSincrono:
    def submit(self, fn: Any, *args: Any, **kwargs: Any) -> None:
        fn(*args, **kwargs)


class _RotuloFalso:
    def __init__(self) -> None:
        self.markup = ""

    def set_markup(self, markup: str) -> None:
        self.markup = markup


def _montar_cartao(monkeypatch: pytest.MonkeyPatch, saida_do_systemctl: str) -> str:
    """Roda `_refresh_storm_diag` de ponta a ponta e devolve o markup do rótulo."""
    from hefesto_dualsense4unix.app import ipc_bridge
    from hefesto_dualsense4unix.app.actions import daemon_actions as da
    from hefesto_dualsense4unix.integrations import storm_doctor

    monkeypatch.setattr(ipc_bridge, "daemon_state_full", lambda: None)
    monkeypatch.setattr(
        storm_doctor, "storm_report", lambda **_kw: [("[ OK ]", "linha de teste")]
    )
    monkeypatch.setattr(da, "_get_executor", lambda: _ExecutorSincrono())
    monkeypatch.setattr(da.GLib, "idle_add", lambda fn, *a, **k: (fn(*a, **k), 0)[1])

    def _run_falso(cmd: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        assert cmd[:3] == ["systemctl", "--user", "show"], cmd
        assert cmd[3] == TIMER.name, cmd
        return subprocess.CompletedProcess(cmd, 0, saida_do_systemctl, "")

    monkeypatch.setattr(da.subprocess, "run", _run_falso)

    rotulo = _RotuloFalso()

    class _HostDoCartao(da.DaemonActionsMixin):
        def _get(self, widget_id: str) -> Any:
            return rotulo if widget_id == "storm_diag_label" else None

    _HostDoCartao()._refresh_storm_diag()
    return rotulo.markup


class TestOAchadoChegaAoCartao:
    def test_o_guarda_morto_aparece_em_saude_do_sistema(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Arrancar a costura em `_refresh_storm_diag` reprova aqui."""
        markup = _montar_cartao(monkeypatch, SHOW_MORTO)
        assert "linha de teste" in markup, "o cartão nem foi montado"
        assert "rede de segurança" in markup, (
            "o guarda morto não chegou ao cartão 'Saúde do sistema':\n" + markup
        )
        assert "[WARN]" in markup

    def test_o_guarda_vivo_nao_deixa_rastro_no_cartao(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        markup = _montar_cartao(monkeypatch, SHOW_VIVO)
        assert "linha de teste" in markup, "o cartão nem foi montado"
        assert "rede de segurança" not in markup, (
            "linha permanente sobre o vigia com ele saudável:\n" + markup
        )
