"""STEAM-INPUT-01/E7 — o vigia do Steam Input não pode nascer `elapsed`.

Medido em 22/08/2026 na bancada dela (systemd 255), reproduzindo o defeito de
26/07 (o guarda passou cinco horas sem rodar):

    Persistent= só tem efeito em timer com OnCalendar= (systemd.timer(5)).
    No `hefesto-steam-input-guard.timer` ele não agendava nada — MATAVA o
    timer. Persistent= faz o systemd ler o carimbo
    (~/.local/share/systemd/timers/stamp-*) e gravá-lo em `last_trigger`; com
    `last_trigger` preenchido o OnBootSec= é tratado como disparo único já
    ocorrido e é DESABILITADO, e o OnUnitActiveSec= não tem em que se ancorar
    enquanto o serviço não rodar uma vez neste boot. Sem os dois, o timer não
    tem próximo disparo.

O gatilho é o ciclo `uninstall.sh` -> `install.sh`: o uninstall apaga as
unidades (`uninstall.sh:411-413`) e DEIXA o carimbo no disco; o install
recria — objeto de unidade novo, `last_trigger` zerado, carimbo velho vivo.

A/B na bancada, mesmo roteiro, só a linha `Persistent=true` de diferença:

    com Persistent=true -> SubState=elapsed, NextElapseUSecMonotonic=infinity
    sem Persistent      -> SubState=waiting, dispara na hora, rearma em 30min
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# `daemon_actions` importa `gi`; sem `gi` real este arquivo ficaria verde contra
# um stub e não mediria a fiação do cartão.
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

# ---------------------------------------------------------------------------
# Saídas VERBATIM de `systemctl --user show <timer>` capturadas na bancada dela
# em 22/08/2026, systemd 255. Não são inventadas: cada bloco saiu de um estado
# reproduzido de verdade (ver o docstring do módulo).
# ---------------------------------------------------------------------------
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

# Parado SEM ninguém ter desabilitado: o `enable` do install não pegou, ou algo
# derrubou a unidade. É problema, e o cartão fala.
SHOW_PARADO_HABILITADO = """\
NextElapseUSecRealtime=
NextElapseUSecMonotonic=infinity
LoadState=loaded
ActiveState=inactive
SubState=dead
UnitFileState=enabled
"""

# O gesto que `docs/usage/troubleshooting-8bitdo.md` ensina para segurar o gyro.
# Idêntico ao de cima em TUDO menos `UnitFileState` — medido em 22/08/2026.
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

# Um timer de calendário sadio: o próximo disparo é REALTIME e o monotônico é
# `0`. Sem esta linha na régua, `0` seria lido como "sem próximo disparo".
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
        """A linha que matava o vigia.

        Devolver `Persistent=true` à unidade reprova aqui — e reprova na
        máquina: medido, o timer volta a nascer `SubState=elapsed` com
        `NextElapseUSecMonotonic=infinity`.
        """
        campos = _campos_do_timer()
        if "Persistent" in campos:
            assert "OnCalendar" in campos, (
                "`Persistent=` sem `OnCalendar=` não agenda nada e MATA o timer: "
                "ele lê o carimbo do disco, o systemd desabilita o `OnBootSec=` "
                "como disparo já ocorrido, o `OnUnitActiveSec=` fica sem âncora "
                "e a unidade nasce `elapsed`. Medido em 22/08/2026, systemd 255."
            )

    def test_sobra_uma_base_que_dispara_sem_ancora(self) -> None:
        """Numa instalação nova o serviço nunca rodou — algo tem de disparar.

        `OnUnitActiveSec=` sozinho se ancora no serviço, e num objeto de
        unidade recém-criado o serviço ainda não tem ativação nenhuma. Sem uma
        base independente (`OnBootSec=` ou `OnCalendar=`) o vigia nunca começa.
        """
        campos = _campos_do_timer()
        bases_independentes = {"OnBootSec", "OnStartupSec", "OnActiveSec", "OnCalendar"}
        assert bases_independentes & set(campos), (
            "o timer só tem bases que dependem de uma ativação anterior do "
            f"serviço; chaves presentes: {sorted(campos)}"
        )
        assert "OnUnitActiveSec" in campos, "o vigia perdeu a repetição periódica"

    def test_as_unidades_nao_apontam_para_sprint_fantasma(self) -> None:
        """E8: as três unidades citavam `FEAT-STEAM-INPUT-SELF-HEAL-01.md`, que
        nunca existiu. Referência de unidade tem de abrir."""
        for unidade in UNIDADES_DO_VIGIA:
            for linha in unidade.read_text(encoding="utf-8").splitlines():
                if not linha.startswith("# doc:"):
                    continue
                alvo = RAIZ / linha.split(":", 1)[1].strip()
                assert alvo.is_file(), (
                    f"{unidade.name} aponta para {alvo.name}, que não existe"
                )


# ---------------------------------------------------------------------------
# A régua da régua: os testes acima leem texto de unidade. O que dá autoridade a
# eles é a medição abaixo, que roda systemd de verdade — e por isso NÃO entra na
# suíte por padrão (a bancada dela não pode ganhar units a cada `pytest`).
#
#   HEFESTO_TESTE_SYSTEMD_VIVO=1 .venv/bin/python -m pytest -q \
#       tests/unit/test_o_vigia_do_steam_input_nao_nasce_morto.py -k systemd_vivo
# ---------------------------------------------------------------------------
LAB = "zz-hefesto-prova-vigia"


def _proximo_disparo_do_lab(corpo_do_timer: str) -> tuple[str, str]:
    """Instala um timer descartável com `corpo_do_timer` e mede o que o systemd
    agenda, com um carimbo velho no disco (o cenário do `uninstall` -> `install`).

    Devolve `(SubState, NextElapseUSecMonotonic)`.
    """
    unidades = Path.home() / ".config" / "systemd" / "user"
    carimbo = Path.home() / ".local" / "share" / "systemd" / "timers" / f"stamp-{LAB}.timer"
    servico = unidades / f"{LAB}.service"
    timer = unidades / f"{LAB}.timer"

    def _sc(*args: str) -> None:
        subprocess.run(["systemctl", "--user", *args], check=False, timeout=15)

    _sc("stop", f"{LAB}.timer")
    servico.unlink(missing_ok=True)
    timer.unlink(missing_ok=True)
    _sc("daemon-reload")  # solta o objeto de unidade: `last_trigger` volta a zero

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
    carimbo.touch()  # o carimbo que o `uninstall.sh` deixa para trás
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
    """O A/B de 22/08/2026, executável.

    O controle (mesmo corpo + `Persistent=true`) é o que valida a régua: sem ele
    um "waiting" verde não provaria que este roteiro consegue detectar o defeito.
    """
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
        """ELO-MUDO-01, o motivo de a régua não poder ser `ActiveState`.

        Trocar a régua por `ActiveState`/`is-active` faz este teste reprovar:
        o cadáver responde `active` e o cartão calaria sobre um guarda que
        passou cinco horas sem rodar.
        """
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
        """`troubleshooting-8bitdo.md` ensina a desabilitar o vigia para segurar
        o gyro do 8BitDo. Sem a guarda de `UnitFileState`, o cartão passa a
        resmungar para sempre sobre um gesto documentado — e este teste reprova.

        A régua é fina de propósito: medido em 22/08/2026, "parado mas
        habilitado" e "desligado de propósito" só diferem em `UnitFileState`.
        """
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
            ("vigia não instalado (--keep-steam-input)", SHOW_AUSENTE),
            ("vigia desabilitado de propósito", SHOW_DESLIGADO_DE_PROPOSITO),
            ("sem systemctl", ""),
            ("sem saída", None),
        ],
    )
    def test_calado_quando_nao_ha_o_que_dizer(self, rotulo: str, saida: object) -> None:
        """Decisão dela, 22/08/2026: nada de linha permanente dizendo "tudo bem".

        Fazer a função devolver um `[ OK ]` no caso saudável reprova aqui.
        """
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
    """Roda `_refresh_storm_diag` de ponta a ponta e devolve o markup do rótulo.

    O dublê fica no `subprocess.run`, não em `medir_guarda_do_steam_input`:
    assim o teste atravessa a leitura do systemd, a interpretação e a costura no
    cartão. Um dublê mais alto conferiria a construção e nunca o efeito.
    """
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
        # A régua é o ARQUIVO em `assets/`, não a constante sob teste.
        # Achado do conferente em 22/08/2026: comparar `cmd[3]` com
        # `da.GUARDA_STEAM_INPUT_TIMER` é a régua conferindo a si mesma —
        # trocar a constante por "unidade-que-nao-existe.timer" deixava os 14
        # testes verdes, e o produto passaria a perguntar por uma unidade
        # inexistente com o cartão calado para sempre.
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
