"""G2 — seção "Rádio e pareamento" do doctor.sh (sprint 2026-07-19-sprint-onda-
g-gyro02-doctor.md), hermética.

A lógica vive em shell puro no doctor.sh (mesmo padrão de
`test_doctor_vpad_motion.py`/`test_doctor_8bitdo_cascade.py`: funções PURAS
testáveis via `source`, testadas primeiro isoladamente e depois em contratos
de "fiação" com main()). Cobre os 6 checks do sprint:

1. versão do bluez < 5.79 => FAIL (backport da Onda R); >= 5.79 => OK.
2. `hefesto-bt-agent.service` ativo => OK; ausente/inativo => WARN.
3. "Connected sem hidraw" (bond meio-salvo por um ângulo).
4. "Paired sem Bonded" (bond meio-salvo pelo outro ângulo).
5. sink de áudio PADRÃO mudo => WARN (sintoma U12).
6. autoridade de exibição unknown presa: JÁ coberta por NUMA-05
   (`check_display_authority`, testada em test_doctor_display_authority.py) —
   aqui só provamos que não foi duplicada.

Os checks 1/2/5 chamam comando único (dpkg-query/systemctl/wpctl) e por isso
ganham teste de ponta-a-ponta com um binário FAKE no PATH (sem tocar no
sistema real). Os checks 3/4 dependem de `bluetoothctl info` por MAC — aqui a
prova de ponta-a-ponta cobre o `bluetoothctl` (fake), e o lado do hidraw
(sysfs real, read-only) é exercitado com um MAC que não pode colidir com
hardware nenhum — falha-sem determinística sem precisar mockar /sys.
"""
from __future__ import annotations

import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCTOR = ROOT / "scripts" / "doctor.sh"


def _rodar(func: str, *args: str, env_extra: dict[str, str] | None = None) -> str:
    """Executa uma função shell REAL do doctor (source, sem rodar o main)."""
    linha = " ".join([func, *[f'"{a}"' for a in args]])
    env = {"PATH": "/usr/bin:/bin", "DOCTOR_SH": str(DOCTOR)}
    if env_extra:
        env.update(env_extra)
    res = subprocess.run(
        ["bash", "-c", f'set --; source "$DOCTOR_SH"; {linha}'],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=env,
    )
    assert res.returncode == 0, res.stderr
    return res.stdout.strip()


def _escrever_fake_bin(tmp_path: Path, nome: str, corpo: str) -> Path:
    fake_bin = tmp_path / "fakebin"
    fake_bin.mkdir(exist_ok=True)
    alvo = fake_bin / nome
    alvo.write_text(f"#!/usr/bin/env bash\n{corpo}\n", encoding="utf-8")
    alvo.chmod(alvo.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return fake_bin


def _rodar_check(
    func: str, fake_bin: Path, env_extra: dict[str, str] | None = None
) -> str:
    """Executa o check_ real com PATH = fakebin primeiro (esconde o binário
    real do sistema atrás do fake) — mesmo padrão de teste hermético."""
    env = {
        "PATH": f"{fake_bin}:/usr/bin:/bin",
        "DOCTOR_SH": str(DOCTOR),
    }
    if env_extra:
        env.update(env_extra)
    # `; true` no fim: alguns checks terminam com `cond && pass ...` (padrão
    # já usado no doctor.sh) — o próprio bash -c herdaria esse exit code como
    # se fosse "erro", mas main() nunca olha o retorno de um check_ (só os
    # contadores FAILS/WARNS); aqui replicamos esse mesmo desinteresse.
    res = subprocess.run(
        ["bash", "-c", f'set --; source "$DOCTOR_SH"; {func}; true'],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=env,
    )
    assert res.returncode == 0, res.stderr
    return res.stdout


# ---------------------------------------------------------------------------
# 1. bluez: versão vs. o piso 5.79 (backport da Onda R).
# ---------------------------------------------------------------------------
class TestBluezVersionVerdict:
    def test_versao_velha_e_old(self) -> None:
        assert _rodar("_bluez_version_verdict", "5.72-0ubuntu5.5") == "old"

    def test_versao_no_piso_e_ok(self) -> None:
        """Boundary: 5.79 exatamente já é 'ok' (dpkg --compare-versions ge)."""
        assert _rodar("_bluez_version_verdict", "5.79") == "ok"

    def test_versao_backport_e_ok(self) -> None:
        assert _rodar("_bluez_version_verdict", "5.85") == "ok"

    def test_versao_vazia_e_unknown(self) -> None:
        assert _rodar("_bluez_version_verdict", "") == "unknown"


class TestCheckBluezBackportVersion:
    """FALHA-SEM/PASSA-COM de ponta-a-ponta: dpkg-query FAKE, dpkg real
    (comparação de string, sem tocar em pacote nenhum)."""

    def _fake_dpkg_query(self, tmp_path: Path, versao: str) -> Path:
        return _escrever_fake_bin(
            tmp_path,
            "dpkg-query",
            f'echo -n "{versao}"',
        )

    def test_bluez_velho_e_fail(self, tmp_path: Path) -> None:
        fake_bin = self._fake_dpkg_query(tmp_path, "5.72-0ubuntu5.5")
        saida = _rodar_check("check_bluez_backport_version", fake_bin)
        assert "[FAIL]" in saida
        assert "5.72-0ubuntu5.5" in saida
        assert "backport" in saida.lower()

    def test_bluez_novo_e_pass(self, tmp_path: Path) -> None:
        fake_bin = self._fake_dpkg_query(tmp_path, "5.85")
        saida = _rodar_check("check_bluez_backport_version", fake_bin)
        assert "[ OK ]" in saida
        assert "[FAIL]" not in saida

    def test_bluez_ausente_e_info_neutro(self, tmp_path: Path) -> None:
        """dpkg-query sem saída (bluez não instalado via dpkg) — nunca FAIL/WARN."""
        fake_bin = self._fake_dpkg_query(tmp_path, "")
        saida = _rodar_check("check_bluez_backport_version", fake_bin)
        assert "[FAIL]" not in saida
        assert "[WARN]" not in saida


# ---------------------------------------------------------------------------
# 2. hefesto-bt-agent.service (unit de SISTEMA — systemctl sem --user).
# ---------------------------------------------------------------------------
class TestCheckBtAgentService:
    def _fake_systemctl(self, tmp_path: Path, ativo: bool, instalado: bool) -> Path:
        estado = "active" if ativo else "inactive"
        corpo = f"""
if [[ "$1 $2" == "is-active hefesto-bt-agent.service" ]]; then
    echo "{estado}"
    [[ "{ativo}" == "True" ]] && exit 0 || exit 3
fi
if [[ "$1 $2" == "cat hefesto-bt-agent.service" ]]; then
    [[ "{instalado}" == "True" ]] && exit 0 || exit 1
fi
exit 1
"""
        return _escrever_fake_bin(tmp_path, "systemctl", corpo)

    def test_ativo_e_pass(self, tmp_path: Path) -> None:
        fake_bin = self._fake_systemctl(tmp_path, ativo=True, instalado=True)
        saida = _rodar_check("check_bt_agent_service", fake_bin)
        assert "[ OK ]" in saida
        assert "hefesto-bt-agent.service ativo" in saida

    def test_instalado_mas_inativo_e_warn(self, tmp_path: Path) -> None:
        """Bond meio-salvo à espreita: instalado mas parado."""
        fake_bin = self._fake_systemctl(tmp_path, ativo=False, instalado=True)
        saida = _rodar_check("check_bt_agent_service", fake_bin)
        assert "[WARN]" in saida
        assert "instalado mas" in saida

    def test_ausente_e_warn(self, tmp_path: Path) -> None:
        fake_bin = self._fake_systemctl(tmp_path, ativo=False, instalado=False)
        saida = _rodar_check("check_bt_agent_service", fake_bin)
        assert "[WARN]" in saida
        assert "não instalado" in saida


# ---------------------------------------------------------------------------
# 3. "Connected sem hidraw" — parte pura (_bt_gamepad_missing_hidraw) +
#    _hidraw_uniqs (sysfs parametrizado) + _mac_norm.
# ---------------------------------------------------------------------------
_INFO_CONECTADO_GAMEPAD = """\
Device AA:BB:CC:13:EB:AB (public)
\tName: DualSense Wireless Controller
\tAlias: DualSense Wireless Controller
\tClass: 0x00000508 (1288)
\tIcon: input-gaming
\tPaired: yes
\tBonded: yes
\tTrusted: no
\tBlocked: no
\tConnected: yes
"""

_INFO_DESCONECTADO_GAMEPAD = _INFO_CONECTADO_GAMEPAD.replace(
    "Connected: yes", "Connected: no"
)

_INFO_NAO_GAMEPAD_CONECTADO = """\
Device AA:BB:CC:DD:EE:FF (public)
\tName: Fone Bluetooth Qualquer
\tIcon: audio-headset
\tPaired: yes
\tBonded: yes
\tConnected: yes
"""


class TestMacNorm:
    def test_normaliza_minusculo_sem_dois_pontos(self) -> None:
        assert _rodar("_mac_norm", "AA:BB:CC:13:EB:AB") == "aabbcc13ebab"

    def test_ja_normalizado_fica_igual(self) -> None:
        assert _rodar("_mac_norm", "aabbcc13ebab") == "aabbcc13ebab"


class TestHidrawUniqs:
    def test_le_hid_uniq_normalizado(self, tmp_path: Path) -> None:
        d = tmp_path / "hidraw4" / "device"
        d.mkdir(parents=True)
        (d / "uevent").write_text(
            "DRIVER=playstation\nHID_UNIQ=aa:bb:cc:13:eb:ab\n", encoding="utf-8"
        )
        assert _rodar("_hidraw_uniqs", str(tmp_path)) == "aabbcc13ebab"

    def test_hid_uniq_vazio_e_ignorado(self, tmp_path: Path) -> None:
        """HID_UNIQ= vazio (ex.: receiver 2.4G genérico) não entra na lista."""
        d = tmp_path / "hidraw0" / "device"
        d.mkdir(parents=True)
        (d / "uevent").write_text("DRIVER=hid-generic\nHID_UNIQ=\n", encoding="utf-8")
        assert _rodar("_hidraw_uniqs", str(tmp_path)) == ""

    def test_raiz_vazia_devolve_vazio_sem_erro(self, tmp_path: Path) -> None:
        assert _rodar("_hidraw_uniqs", str(tmp_path / "nao-existe")) == ""

    def test_varios_hidraw_uma_linha_cada(self, tmp_path: Path) -> None:
        for n, mac in enumerate(["AA:BB:CC:13:EB:AB", "02:FE:00:00:00:01"]):
            d = tmp_path / f"hidraw{n}" / "device"
            d.mkdir(parents=True)
            (d / "uevent").write_text(f"HID_UNIQ={mac}\n", encoding="utf-8")
        saida = _rodar("_hidraw_uniqs", str(tmp_path)).splitlines()
        assert sorted(saida) == ["02fe00000001", "aabbcc13ebab"]


class TestBtGamepadMissingHidraw:
    def test_conectado_sem_hidraw_acusa_o_mac(self) -> None:
        saida = _rodar(
            "_bt_gamepad_missing_hidraw", _INFO_CONECTADO_GAMEPAD, "outromac"
        )
        assert saida == "AA:BB:CC:13:EB:AB"

    def test_conectado_com_hidraw_correspondente_fica_silencioso(self) -> None:
        hidraw_list = "aabbcc13ebab"
        saida = _rodar(
            "_bt_gamepad_missing_hidraw", _INFO_CONECTADO_GAMEPAD, hidraw_list
        )
        assert saida == ""

    def test_desconectado_nunca_acusa(self) -> None:
        """Só Connected: yes importa — desconectado não é 'meio-salvo'."""
        saida = _rodar(
            "_bt_gamepad_missing_hidraw", _INFO_DESCONECTADO_GAMEPAD, ""
        )
        assert saida == ""

    def test_dispositivo_nao_gamepad_nunca_acusa(self) -> None:
        """Fone/headset conectado sem hidraw é NORMAL (não tem hidraw mesmo)."""
        saida = _rodar(
            "_bt_gamepad_missing_hidraw", _INFO_NAO_GAMEPAD_CONECTADO, ""
        )
        assert saida == ""


# ---------------------------------------------------------------------------
# 4. "Paired sem Bonded".
# ---------------------------------------------------------------------------
_INFO_MEIO_SALVO = """\
Device AA:BB:CC:13:EB:AB (public)
\tName: DualSense Wireless Controller
\tIcon: input-gaming
\tPaired: yes
\tBonded: no
\tConnected: yes
"""

_INFO_BOND_OK = _INFO_MEIO_SALVO.replace("Bonded: no", "Bonded: yes")
_INFO_NUNCA_PAREADO = _INFO_MEIO_SALVO.replace("Paired: yes", "Paired: no")


class TestBtPairedSemBonded:
    def test_paired_sem_bonded_acusa_o_mac(self) -> None:
        assert _rodar("_bt_paired_sem_bonded", _INFO_MEIO_SALVO) == "AA:BB:CC:13:EB:AB"

    def test_paired_e_bonded_fica_silencioso(self) -> None:
        assert _rodar("_bt_paired_sem_bonded", _INFO_BOND_OK) == ""

    def test_nunca_pareado_fica_silencioso(self) -> None:
        assert _rodar("_bt_paired_sem_bonded", _INFO_NUNCA_PAREADO) == ""


class TestCheckBtPairedSemBonded:
    """Ponta-a-ponta com `bluetoothctl` FAKE (devices + info por MAC) — este
    check NÃO depende de sysfs, então dá para cobrir os dois lados inteiros."""

    def _fake_bluetoothctl(self, tmp_path: Path, mac: str, info: str) -> Path:
        info_dir = tmp_path / "btinfo"
        info_dir.mkdir(exist_ok=True)
        (info_dir / mac).write_text(info, encoding="utf-8")
        corpo = f"""
case "$1" in
    devices) printf 'Device {mac} Fake\\n' ;;
    info) cat "{info_dir}/$2" 2>/dev/null ;;
esac
exit 0
"""
        return _escrever_fake_bin(tmp_path, "bluetoothctl", corpo)

    def test_bond_meio_salvo_e_fail(self, tmp_path: Path) -> None:
        mac = "AA:BB:CC:13:EB:AB"
        fake_bin = self._fake_bluetoothctl(tmp_path, mac, _INFO_MEIO_SALVO)
        saida = _rodar_check("check_bt_paired_sem_bonded", fake_bin)
        assert "[FAIL]" in saida
        assert mac in saida
        assert "meio-salvo" in saida

    def test_bond_ok_e_pass(self, tmp_path: Path) -> None:
        mac = "AA:BB:CC:13:EB:AB"
        fake_bin = self._fake_bluetoothctl(tmp_path, mac, _INFO_BOND_OK)
        saida = _rodar_check("check_bt_paired_sem_bonded", fake_bin)
        assert "[ OK ]" in saida
        assert "[FAIL]" not in saida

    def test_sem_dispositivos_pareados_e_info_neutro(self, tmp_path: Path) -> None:
        corpo = 'case "$1" in devices) printf "" ;; esac\nexit 0\n'
        fake_bin = _escrever_fake_bin(tmp_path, "bluetoothctl", corpo)
        saida = _rodar_check("check_bt_paired_sem_bonded", fake_bin)
        assert "[FAIL]" not in saida
        assert "[WARN]" not in saida
        assert "nenhum dispositivo" in saida


class TestCheckBtConnectedSemHidraw:
    """MAC exótico (impossível de colidir com HID_UNIQ real) => FAIL
    determinístico mesmo lendo o /sys/class/hidraw REAL da máquina (a leitura
    em si é read-only e não muda o veredito: nenhum hidraw real pode ter
    este HID_UNIQ)."""

    _MAC_EXOTICO = "AA:BB:CC:EF:00:99"

    def test_conectado_sem_hidraw_correspondente_e_fail(self, tmp_path: Path) -> None:
        info = _INFO_CONECTADO_GAMEPAD.replace("AA:BB:CC:13:EB:AB", self._MAC_EXOTICO)
        info_dir = tmp_path / "btinfo"
        info_dir.mkdir()
        (info_dir / self._MAC_EXOTICO).write_text(info, encoding="utf-8")
        corpo = f"""
case "$1" in
    devices) printf 'Device {self._MAC_EXOTICO} Fake\\n' ;;
    info) cat "{info_dir}/$2" 2>/dev/null ;;
esac
exit 0
"""
        fake_bin = _escrever_fake_bin(tmp_path, "bluetoothctl", corpo)
        saida = _rodar_check("check_bt_connected_sem_hidraw", fake_bin)
        assert "[FAIL]" in saida
        assert self._MAC_EXOTICO in saida
        assert "meio-salvo" in saida

    def test_sem_dispositivos_pareados_e_info_neutro(self, tmp_path: Path) -> None:
        corpo = 'case "$1" in devices) printf "" ;; esac\nexit 0\n'
        fake_bin = _escrever_fake_bin(tmp_path, "bluetoothctl", corpo)
        saida = _rodar_check("check_bt_connected_sem_hidraw", fake_bin)
        assert "[FAIL]" not in saida
        assert "[WARN]" not in saida
        assert "nenhum dispositivo" in saida


# ---------------------------------------------------------------------------
# 5. sink de áudio PADRÃO mudo (sintoma U12).
# ---------------------------------------------------------------------------
class TestWpctlVolumeMuted:
    def test_com_muted_e_muted(self) -> None:
        assert _rodar("_wpctl_volume_muted", "Volume: 0.50 [MUTED]") == "muted"

    def test_sem_muted_e_unmuted(self) -> None:
        assert _rodar("_wpctl_volume_muted", "Volume: 1.50") == "unmuted"

    def test_vazio_e_unknown(self) -> None:
        assert _rodar("_wpctl_volume_muted", "") == "unknown"


class TestCheckAudioSinkMuted:
    def _fake_wpctl(self, tmp_path: Path, saida: str) -> Path:
        corpo = f'echo "{saida}"\nexit 0\n'
        return _escrever_fake_bin(tmp_path, "wpctl", corpo)

    def test_mudo_e_warn(self, tmp_path: Path) -> None:
        fake_bin = self._fake_wpctl(tmp_path, "Volume: 0.50 [MUTED]")
        saida = _rodar_check("check_audio_sink_muted", fake_bin)
        assert "[WARN]" in saida
        assert "MUDO" in saida
        assert "wpctl set-mute" in saida

    def test_nao_mudo_e_pass(self, tmp_path: Path) -> None:
        fake_bin = self._fake_wpctl(tmp_path, "Volume: 1.00")
        saida = _rodar_check("check_audio_sink_muted", fake_bin)
        assert "[ OK ]" in saida
        assert "[WARN]" not in saida

    def test_sem_saida_e_info_neutro(self, tmp_path: Path) -> None:
        fake_bin = self._fake_wpctl(tmp_path, "")
        saida = _rodar_check("check_audio_sink_muted", fake_bin)
        assert "[FAIL]" not in saida
        assert "[WARN]" not in saida


# ---------------------------------------------------------------------------
# Contratos de fiação (padrão do repo para lógica do doctor.sh).
# ---------------------------------------------------------------------------
class TestFiacaoNoDoctor:
    def _texto(self) -> str:
        return DOCTOR.read_text(encoding="utf-8")

    def _bloco(self, inicio_marca: str) -> str:
        texto = self._texto()
        inicio = texto.index(inicio_marca)
        return texto[inicio : texto.index("\n}", inicio)]

    @pytest.mark.parametrize(
        "func",
        [
            "check_bluez_backport_version",
            "check_bt_agent_service",
            "check_bt_connected_sem_hidraw",
            "check_bt_paired_sem_bonded",
            "check_audio_sink_muted",
        ],
    )
    def test_checks_chamados_no_main(self, func: str) -> None:
        assert f"\n    {func}\n" in self._texto()

    def test_check_bluez_usa_a_funcao_pura(self) -> None:
        bloco = self._bloco("check_bluez_backport_version() {")
        assert "_bluez_version_verdict" in bloco

    def test_check_hidraw_usa_as_funcoes_puras(self) -> None:
        bloco = self._bloco("check_bt_connected_sem_hidraw() {")
        assert "_bt_gamepad_missing_hidraw" in bloco
        assert "_hidraw_uniqs" in bloco

    def test_check_bonded_usa_a_funcao_pura(self) -> None:
        bloco = self._bloco("check_bt_paired_sem_bonded() {")
        assert "_bt_paired_sem_bonded" in bloco

    def test_check_audio_usa_a_funcao_pura(self) -> None:
        bloco = self._bloco("check_audio_sink_muted() {")
        assert "_wpctl_volume_muted" in bloco

    def test_bt_agent_e_unit_de_sistema_sem_dash_dash_user(self) -> None:
        """hefesto-bt-agent.service é WantedBy=multi-user.target (system) —
        ao contrário de check_service (--user), este NUNCA usa --user."""
        bloco = self._bloco("check_bt_agent_service() {")
        assert "--user" not in bloco

    def test_read_only_nenhum_check_novo_escreve_em_dev_ou_sys(self) -> None:
        texto = self._texto()
        inicio = texto.index("# G2 — doctor:")
        fim = texto.index("# PLAT-01: relatório read-only do Proton pinado")
        regiao = texto[inicio:fim] + self._bloco("check_audio_sink_muted() {")
        assert "of=" not in regiao
        assert "> /dev" not in regiao
        assert "> /sys" not in regiao

    def test_comandos_de_cura_sao_so_texto_de_conselho_nunca_executados(self) -> None:
        """'bluetoothctl remove', 'wpctl set-mute' e 'systemctl enable --now'
        só podem aparecer DENTRO de uma mensagem de warn/fail (conselho pro
        humano) — nunca como uma chamada de comando real do próprio check."""
        texto = self._texto()
        inicio = texto.index("# G2 — doctor:")
        fim = texto.index("check_bt_paired_sem_bonded() {")
        fim = texto.index("\n}", fim)
        regiao = texto[inicio:fim] + "\n" + self._bloco("check_audio_sink_muted() {")
        for linha in regiao.splitlines():
            marcada = linha.lstrip()
            if "bluetoothctl remove" in linha or "wpctl set-mute" in linha or (
                "systemctl enable --now hefesto-bt-agent" in linha
            ):
                assert marcada.startswith(("warn ", "fail ", "info ", "pass ")), linha

    def test_check6_autoridade_de_exibicao_nao_foi_duplicado(self) -> None:
        """G2 item 6 (unknown preso) já existe via NUMA-05 — não duplicar."""
        texto = self._texto()
        assert texto.count("check_display_authority() {") == 1
        assert texto.count("\n    check_display_authority\n") == 1
