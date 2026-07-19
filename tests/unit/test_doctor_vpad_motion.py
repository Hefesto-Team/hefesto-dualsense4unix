"""GYRO-03 — check "giroscópio no jogo" do doctor.sh, hermético.

A lógica vive em shell puro no doctor.sh (funções testáveis via ``source``,
padrão de `test_doctor_8bitdo_cascade`):

- ``_vpad_motion_event_nodes``: extrai de /proc/bus/input/devices (fonte
  parametrizada) SOMENTE os eventN dos Motion Sensors DOS VPADS ("Hefesto
  Virtual DualSense PN Motion Sensors") — nunca os do físico Sony nem o nó
  principal do vpad.
- ``_motion_node_sample``: amostra ~1s de um nó evdev e imprime
  ``vivo``/``silencio`` — aqui exercitada com nós FAKE (arquivo com structs
  ``input_event`` sintéticos; FIFO sem escritor = silêncio até o timeout),
  sem hardware. GYRO-03-FIX: só EV_ABS (type=3) de eixo gyro/accel (codes
  0..5) conta como "vivo" — o hid_playstation emite EV_MSC/MSC_TIMESTAMP a
  cada report do vpad MESMO com o espelho morto, então botão/stick durante a
  amostra dava falso "SIM".

Critério do sprint: o probe que a mantenedora rodou à mão (leitura O_RDONLY,
sem grab) virado ferramenta pro leigo, read-only por construção.
"""
from __future__ import annotations

import os
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCTOR = ROOT / "scripts" / "doctor.sh"

# Réplica do formato real de /proc/bus/input/devices desta máquina: físico
# Sony (USB e BT), nó principal do vpad (sem "Motion Sensors") e os Motion
# dos vpads P1/P2 — só os dois últimos podem sair.
_PROC_DEVICES = """\
I: Bus=0003 Vendor=054c Product=0ce6 Version=0111
N: Name="Sony Interactive Entertainment DualSense Wireless Controller"
H: Handlers=event24 js0
B: EV=1b

I: Bus=0003 Vendor=054c Product=0ce6 Version=0111
N: Name="Sony Interactive Entertainment DualSense Wireless Controller Motion Sensors"
H: Handlers=event26
B: EV=19

I: Bus=0005 Vendor=054c Product=0ce6 Version=0100
N: Name="DualSense Wireless Controller Motion Sensors"
H: Handlers=event30
B: EV=19

I: Bus=0003 Vendor=054c Product=0df2 Version=0111
N: Name="Hefesto Virtual DualSense P1"
H: Handlers=event28 js1
B: EV=1b

I: Bus=0003 Vendor=054c Product=0df2 Version=0111
N: Name="Hefesto Virtual DualSense P1 Motion Sensors"
H: Handlers=event27
B: EV=19

I: Bus=0003 Vendor=054c Product=0df2 Version=0111
N: Name="Hefesto Virtual DualSense P2 Motion Sensors"
H: Handlers=event29
B: EV=19
"""


def _rodar(func: str, *args: str) -> str:
    """Executa uma função shell REAL do doctor (source, sem rodar o main)."""
    linha = " ".join([func, *[f'"{a}"' for a in args]])
    res = subprocess.run(
        ["bash", "-c", f'set --; source "$DOCTOR_SH"; {linha}'],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={"PATH": "/usr/bin:/bin", "DOCTOR_SH": str(DOCTOR)},
    )
    assert res.returncode == 0, res.stderr
    return res.stdout.strip()


class TestVpadMotionEventNodes:
    def test_extrai_so_os_motion_dos_vpads(self, tmp_path: Path) -> None:
        src = tmp_path / "devices"
        src.write_text(_PROC_DEVICES, encoding="utf-8")
        saida = _rodar("_vpad_motion_event_nodes", str(src))
        assert saida.splitlines() == ["event27", "event29"]

    def test_fisico_sony_nunca_e_confundido_com_vpad(self, tmp_path: Path) -> None:
        """Só os Motion do físico no ar (emulação off) → lista vazia."""
        so_fisico = "\n".join(
            linha
            for linha in _PROC_DEVICES.splitlines()
            if "Hefesto" not in linha
        )
        src = tmp_path / "devices"
        src.write_text(so_fisico + "\n", encoding="utf-8")
        assert _rodar("_vpad_motion_event_nodes", str(src)) == ""

    def test_fonte_ausente_devolve_vazio_sem_erro(self, tmp_path: Path) -> None:
        assert _rodar("_vpad_motion_event_nodes", str(tmp_path / "nao-existe")) == ""


# Constantes do input core (linux/input-event-codes.h) usadas nos dumps.
_EV_SYN = 0
_EV_KEY = 1
_EV_ABS = 3
_EV_MSC = 4
_MSC_TIMESTAMP = 5
_BTN_SOUTH = 304  # cross
_ABS_X = 0  # 1º eixo de gyro/accel no nó Motion
_ABS_RZ = 5  # último eixo de gyro/accel
_ABS_HAT0X = 16  # d-pad — NUNCA existe no nó Motion, e não é gyro


def _evento(tipo: int, code: int, valor: int) -> bytes:
    """struct input_event de 64-bit (24 B): timeval zerado + type/code/value."""
    return struct.pack("<qqHHi", 0, 0, tipo, code, valor)


class TestMotionNodeSample:
    def test_dump_com_gyro_e_vivo(self, tmp_path: Path) -> None:
        """>=1 EV_ABS de eixo gyro/accel → vivo (o awk sai no primeiro)."""
        node = tmp_path / "event-fake"
        node.write_bytes(
            _evento(_EV_MSC, _MSC_TIMESTAMP, 999)
            + _evento(_EV_ABS, _ABS_X, 123)
            + _evento(_EV_SYN, 0, 0)
        )
        assert _rodar("_motion_node_sample", str(node), "1") == "vivo"

    def test_dump_so_com_botoes_e_msc_da_silencio(self, tmp_path: Path) -> None:
        """Regressão GYRO-03-FIX: input de stick/botão durante a amostra gera
        EV_KEY + EV_MSC/MSC_TIMESTAMP + EV_SYN no nó Motion (o hid_playstation
        carimba MSC_TIMESTAMP em TODO report) — nada disso é gyro → NÃO."""
        node = tmp_path / "event-fake"
        node.write_bytes(
            _evento(_EV_MSC, _MSC_TIMESTAMP, 111)
            + _evento(_EV_KEY, _BTN_SOUTH, 1)
            + _evento(_EV_SYN, 0, 0)
            + _evento(_EV_MSC, _MSC_TIMESTAMP, 222)
            + _evento(_EV_KEY, _BTN_SOUTH, 0)
            + _evento(_EV_SYN, 0, 0)
        )
        assert _rodar("_motion_node_sample", str(node), "1") == "silencio"

    def test_gyro_no_meio_de_botoes_e_vivo(self, tmp_path: Path) -> None:
        """Uso real do diagnóstico: mexer no controle COM o espelho vivo —
        botões e gyro misturados na amostra → SIM (o EV_ABS decide)."""
        node = tmp_path / "event-fake"
        node.write_bytes(
            _evento(_EV_KEY, _BTN_SOUTH, 1)
            + _evento(_EV_MSC, _MSC_TIMESTAMP, 1)
            + _evento(_EV_SYN, 0, 0)
            + _evento(_EV_ABS, _ABS_RZ, -512)
            + _evento(_EV_SYN, 0, 0)
        )
        assert _rodar("_motion_node_sample", str(node), "1") == "vivo"

    def test_abs_fora_dos_eixos_de_gyro_nao_conta(self, tmp_path: Path) -> None:
        """EV_ABS com code > 5 (ex.: d-pad ABS_HAT0X) não é gyro/accel."""
        node = tmp_path / "event-fake"
        node.write_bytes(_evento(_EV_ABS, _ABS_HAT0X, 1))
        assert _rodar("_motion_node_sample", str(node), "1") == "silencio"

    def test_no_mudo_da_silencio_no_timeout(self, tmp_path: Path) -> None:
        """FIFO sem escritor = nó aberto que nunca entrega evento — o probe
        espera o timeout e declara silêncio (o caso 'gyro não flui')."""
        fifo = tmp_path / "fifo-fake"
        os.mkfifo(fifo)
        assert _rodar("_motion_node_sample", str(fifo), "0.4") == "silencio"

    def test_leitura_curta_nao_conta_como_evento(self, tmp_path: Path) -> None:
        """Menos de 24 B não é um input_event inteiro → silêncio."""
        node = tmp_path / "event-fake"
        node.write_bytes(bytes(10))
        assert _rodar("_motion_node_sample", str(node), "0.4") == "silencio"


class TestFiacaoNoDoctor:
    """Contratos de texto (padrão do repo para lógica do doctor.sh)."""

    def _texto(self) -> str:
        return DOCTOR.read_text(encoding="utf-8")

    def _bloco_do_check(self) -> str:
        texto = self._texto()
        inicio = texto.index("check_vpad_motion() {")
        return texto[inicio : texto.index("\n}", inicio)]

    def test_check_e_chamado_no_main(self) -> None:
        assert "\n    check_vpad_motion\n" in self._texto()

    def test_usa_as_funcoes_testadas_aqui(self) -> None:
        bloco = self._bloco_do_check()
        assert "_vpad_motion_event_nodes" in bloco
        assert "_motion_node_sample" in bloco

    def test_read_only_por_construcao(self) -> None:
        """O check NUNCA escreve em nó de input: dd só com if= (nunca of=),
        sem redirecionamento para /dev, sem sudo."""
        texto = self._texto()
        inicio = texto.index("_vpad_motion_event_nodes() {")
        fim = texto.index("check_steam_input() {")
        regiao = texto[inicio:fim]
        assert "of=" not in regiao
        assert "> /dev" not in regiao
        assert "sudo" not in regiao

    def test_fala_com_o_leigo_e_cita_a_telemetria(self) -> None:
        bloco = self._bloco_do_check()
        assert "giroscópio chegando ao jogo: SIM" in bloco
        assert "giroscópio chegando ao jogo: NÃO" in bloco
        assert "motion_streaming" in bloco
        assert "daemon.state_full" in bloco

    def test_silencio_e_warn_nunca_fail(self) -> None:
        """Gyro parado não derruba o exit code do doctor (emulação recém
        ligada, jogo sem gyro): é aviso acionável, não falha dura."""
        bloco = self._bloco_do_check()
        for linha in bloco.splitlines():
            if "giroscópio chegando ao jogo: NÃO" in linha:
                assert linha.lstrip().startswith("warn ")
