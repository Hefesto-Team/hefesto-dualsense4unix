"""8BIT-03 — o doctor aprende a assinatura de morte por BT do clone 8BitDo.

A lógica de detecção vive em shell puro no doctor.sh (`_hid_nintendo_cascade_scan`,
função testável via `source`); aqui ela é EXECUTADA de verdade com fixtures que
replicam o journal medido ao vivo em 2026-07-16 nesta máquina:

- morte real (instância ``0005:057E:2009.0014``, 13:23:47->13:24:00): dezenas de
  ``timeout waiting for input report`` culminando em
  ``joycon_enforce_subcmd_rate: exceeded max attempts``;
- caso NÃO-terminal (``.0008`` às 12:38:46: 3x ``exceeded`` com UM timeout — o
  controle viveu mais ~8 minutos) e o boot seguinte (``.0007``: 3x ``exceeded``
  com ZERO timeouts): a linha isolada NUNCA pode disparar.

Critério central do aceite: ZERO falso-positivo — journal limpo ou só linhas
isoladas => saída vazia.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCTOR = ROOT / "scripts" / "doctor.sh"

_PREFIX = "jul 16 13:23:47 MeowSystem kernel: nintendo"

# Ruído real presente no journal medido (nenhuma linha destas pode contar).
_RUIDO = [
    "jul 16 12:38:45 MeowSystem kernel: nintendo 0005:057E:2009.0008: "
    "unknown main item tag 0x0",
    "jul 16 12:38:45 MeowSystem kernel: nintendo 0005:057E:2009.0008: hidraw7: "
    "BLUETOOTH HID v80.01 Gamepad [Pro Controller] on aa:bb:cc:04:13:c4",
    "jul 16 12:38:47 MeowSystem kernel: nintendo 0005:057E:2009.0008: "
    "compensating for 15 dropped IMU reports",
    "jul 16 12:51:29 MeowSystem kernel: joycon_parse_imu_report: 1 callbacks suppressed",
    "jul 16 12:41:10 MeowSystem kernel: Modules linked in: hid_nintendo "
    "hid_playstation ff_memless led_class_multicolor hidp",
    "jul 16 12:31:40 MeowSystem kernel: usb 3-2: new full-speed USB device number 4 "
    "using xhci_hcd",
]


def _timeout(inst: str) -> str:
    return f"{_PREFIX} {inst}: timeout waiting for input report"


def _exceeded(inst: str) -> str:
    return f"{_PREFIX} {inst}: joycon_enforce_subcmd_rate: exceeded max attempts"


def _scan(linhas: list[str], min_timeouts: int | None = None) -> str:
    """Executa a função shell real (via source, sem rodar o main do doctor)."""
    arg = "" if min_timeouts is None else f" {min_timeouts}"
    res = subprocess.run(
        ["bash", "-c", f'set --; source "$DOCTOR_SH"; _hid_nintendo_cascade_scan{arg}'],
        input="\n".join(linhas) + "\n",
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={"PATH": "/usr/bin:/bin", "DOCTOR_SH": str(DOCTOR)},
    )
    assert res.returncode == 0, res.stderr
    assert res.stderr == "", res.stderr
    return res.stdout.strip()


class TestCascataDispara:
    """O caso positivo: série de timeouts CULMINANDO em exceeded, mesma instância."""

    def test_cascata_real_dispara_citando_a_instancia(self) -> None:
        inst = "0005:057E:2009.0014"
        linhas = [*_RUIDO, *([_timeout(inst)] * 45), _exceeded(inst)]
        saida = _scan(linhas)
        assert saida == f"{inst} 45"

    def test_duas_instancias_so_a_cascata_aparece(self) -> None:
        """Réplica do boot medido: .0014 morreu de cascata; .0008 teve exceeded
        isolado (1 timeout) e NÃO pode ser citada."""
        morta, viva = "0005:057E:2009.0014", "0005:057E:2009.0008"
        linhas = (
            [_exceeded(viva), _exceeded(viva), _timeout(viva), _exceeded(viva)]
            + [_timeout(morta)] * 12
            + [_exceeded(morta)]
        )
        saida = _scan(linhas)
        assert morta in saida
        assert viva not in saida

    def test_limiar_da_serie_e_10_timeouts(self) -> None:
        inst = "0005:057E:2009.0014"
        assert _scan([_timeout(inst)] * 9 + [_exceeded(inst)]) == ""
        assert _scan([_timeout(inst)] * 10 + [_exceeded(inst)]) == f"{inst} 10"


class TestZeroFalsoPositivo:
    """O critério central do aceite: linha isolada ou journal limpo => silêncio."""

    def test_exceeded_isolado_nao_terminal_nao_dispara(self) -> None:
        """Réplica verbatim do caso medido às 12:38:46 (.0008): 3x exceeded com
        UM timeout no meio — o controle viveu mais ~8 minutos."""
        inst = "0005:057E:2009.0008"
        linhas = [
            *_RUIDO,
            _exceeded(inst),
            _exceeded(inst),
            _timeout(inst),
            _exceeded(inst),
        ]
        assert _scan(linhas) == ""

    def test_exceeded_sem_nenhum_timeout_nao_dispara(self) -> None:
        """Réplica do boot seguinte (.0007 às 23:52): só exceeded, zero timeouts."""
        inst = "0005:057E:2009.0007"
        assert _scan([*_RUIDO, *([_exceeded(inst)] * 3)]) == ""

    def test_timeouts_sem_exceeded_nao_disparam(self) -> None:
        """Driver sofrendo mas sem desistir: sem o exceeded, não há morte."""
        inst = "0005:057E:2009.0014"
        assert _scan([_timeout(inst)] * 40) == ""

    def test_instancias_diferentes_nao_se_somam(self) -> None:
        """Timeouts numa instância + exceeded noutra: nada é a MESMA instância."""
        a, b = "0005:057E:2009.0014", "0005:057E:2009.0015"
        assert _scan([_timeout(a)] * 20 + [_exceeded(b)]) == ""

    def test_exceeded_antes_da_serie_nao_dispara(self) -> None:
        """'Culminando' é literal: exceeded no bind seguido de timeouts (sem um
        novo exceeded depois da série) não é a cascata."""
        inst = "0005:057E:2009.0008"
        assert _scan([_exceeded(inst)] + [_timeout(inst)] * 20) == ""

    def test_journal_limpo_fica_em_silencio(self) -> None:
        assert _scan(_RUIDO) == ""
        assert _scan(["jul 17 00:00:01 MeowSystem kernel: wlan0: associated"]) == ""


class TestFiacaoNoDoctor:
    """Contratos de texto (padrão do repo para lógica do doctor.sh)."""

    def _texto(self) -> str:
        return DOCTOR.read_text(encoding="utf-8")

    def _bloco_do_check(self) -> str:
        texto = self._texto()
        inicio = texto.index("check_hid_nintendo_bt_cascade() {")
        return texto[inicio : texto.index("\n}", inicio)]

    def test_check_e_chamado_no_main(self) -> None:
        assert "\n    check_hid_nintendo_bt_cascade\n" in self._texto()

    def test_usa_journal_do_boot_atual_sem_sudo(self) -> None:
        bloco = self._bloco_do_check()
        assert "journalctl -b -k" in bloco
        assert "sudo" not in bloco
        assert "dmesg" not in bloco

    def test_coabitacao_steam_hidraw_nunca_vira_warning(self) -> None:
        """O Steam segura o hidraw de TODO controle suportado (DualSense
        saudáveis inclusive) — warning de coabitação seria alarme falso crônico."""
        bloco = self._bloco_do_check()
        for linha in bloco.splitlines():
            if "warn " in linha:
                assert "steam" not in linha.lower()
                assert "hidraw" not in linha.lower()

    def test_nao_recomenda_blacklist_nem_fechar_o_steam(self) -> None:
        """Nas linhas de SAÍDA (warn/info/pass/fail) — comentários podem citar
        a proibição ("'feche o Steam' não é cura"), a saída nunca a recomenda."""
        texto = self._texto()
        assert "blacklist" not in texto.lower()
        for linha in texto.splitlines():
            saida = linha.lstrip()
            if saida.startswith(("warn ", "info ", "pass ", "fail ")):
                assert "feche o steam" not in saida.lower()
                assert "feche a steam" not in saida.lower()

    def test_warn_cita_instancia_e_a_config_estavel(self) -> None:
        bloco = self._bloco_do_check()
        assert "${inst}" in bloco
        assert "cabo em modo Switch" in bloco
