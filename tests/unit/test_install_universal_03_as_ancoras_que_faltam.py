"""INSTALL-UNIVERSAL (18/09/2026) — o controle no rádio sem âncora deixa de ser mudo.

Pelo rádio, o endpoint que o jogo acha é um nó nosso que declara o
`sysfs.path` de um aparelho USB SEM placa de som (a âncora do ContainerId). É
uma âncora por controle, e o `distribuir_ancoras` só entrega enquanto houver: o
controle que sobrava era pulado por um `continue`, sem log, sem estado e sem
doctor. Numa máquina com poucos aparelhos USB (um notebook com a mesa de
quatro), a vibração de um jogador sumia sem rastro.

Duas pontas, e cada uma morde:

* o daemon avisa no journal — **na mudança**, porque a volta roda a cada
  `RECONCILIA_S` e um aviso por volta encheria o log;
* o doctor conta as MESMAS âncoras (o código do daemon, importado) contra os
  DualSense no rádio, e diz o gesto.

Nada vai para a tela: a dívida é nossa, e a tela não a confessa.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod
from tests.unit.test_haptica_por_radio_01_a_ponte_troca_de_modo import (
    _Controle,
    _EndpointDeMentira,
    _PonteDeMentira,
)

RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"


# ------------------------------------------------------------------ o daemon


class _Bancada:
    def __init__(self, sub: Any, ancoras: list[Any]) -> None:
        self.sub = sub
        self.ancoras = ancoras


@pytest.fixture
def bancada(monkeypatch: pytest.MonkeyPatch) -> _Bancada:
    from hefesto_dualsense4unix.integrations import alto_falante_bt as af
    from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
    from hefesto_dualsense4unix.integrations import hidraw_broker_client as broker

    _PonteDeMentira.criadas = []
    _EndpointDeMentira.criados = []
    _EndpointDeMentira.quedas = []
    ancoras: list[Any] = [eh.Ancora(syspath="/d/0", declarado="/d/0/i:1.0")]

    monkeypatch.setattr(af, "fonte_do_monitor_do_no", lambda *_a, **_k: (None, None, "teste"))
    monkeypatch.setattr(af, "PonteDeSomPorRadio", _PonteDeMentira)
    monkeypatch.setattr(af, "sink_esta_tocando", lambda *_a, **_k: False)
    monkeypatch.setattr(eh, "EndpointDeHaptica", _EndpointDeMentira)
    monkeypatch.setattr(eh, "ancoras", lambda *_a, **_k: list(ancoras))
    monkeypatch.setattr(eh, "varrer_endpoints_orfaos", lambda *_a, **_k: None)
    monkeypatch.setattr(broker, "abrir_hidraw", lambda no, **_: type("N", (), {"fd": 7})())

    class _Ger:
        def reconciliar(self, *_a: Any, **_k: Any) -> None:
            return None

        def dormir(self, _s: float) -> bool:
            return False

        def parar(self) -> None:
            return None

    sub = mod.AltoFalanteSubsystem(gerenciador=_Ger(), fonte_de_controles=lambda: [])
    return _Bancada(sub, ancoras)


def _tres_no_radio() -> list[_Controle]:
    return [
        _Controle(f"aa:bb:cc:00:00:0{i}", f"/dev/hidraw{i}", "bluetooth") for i in range(1, 4)
    ]


def _avisos(registros: list[dict[str, Any]], evento: str) -> list[dict[str, Any]]:
    return [r for r in registros if r["event"] == evento]


def test_faltando_ancora_o_daemon_diz_quantos(bancada: _Bancada) -> None:
    """A MORDIDA: arranque o aviso e o `continue` volta a ser mudo."""
    with structlog.testing.capture_logs() as registros:
        bancada.sub._casar_as_pontes(_tres_no_radio())
    avisos = _avisos(registros, "haptica_sem_ancora")
    assert len(avisos) == 1, registros
    assert avisos[0]["faltam"] == 2
    assert avisos[0]["controles"] == 3
    assert avisos[0]["log_level"] == "warning"
    assert len(_EndpointDeMentira.criados) == 1, "o que tinha âncora continua ganhando endpoint"


def test_o_aviso_sai_na_mudanca_e_nao_a_cada_volta(bancada: _Bancada) -> None:
    """A volta roda a cada RECONCILIA_S: dez voltas iguais, um aviso só."""
    with structlog.testing.capture_logs() as registros:
        for _ in range(10):
            bancada.sub._casar_as_pontes(_tres_no_radio())
    assert len(_avisos(registros, "haptica_sem_ancora")) == 1


def test_a_ancora_que_chega_desliga_o_aviso(bancada: _Bancada) -> None:
    from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh

    bancada.sub._casar_as_pontes(_tres_no_radio())
    bancada.ancoras.extend(
        eh.Ancora(syspath=f"/d/{i}", declarado=f"/d/{i}/i:1.0") for i in (1, 2)
    )
    with structlog.testing.capture_logs() as registros:
        bancada.sub._casar_as_pontes(_tres_no_radio())
    assert _avisos(registros, "haptica_ancoras_bastam"), registros
    assert not _avisos(registros, "haptica_sem_ancora")
    assert len(_EndpointDeMentira.criados) == 3


def test_ancoras_de_sobra_nao_avisam_nada(bancada: _Bancada) -> None:
    with structlog.testing.capture_logs() as registros:
        bancada.sub._casar_as_pontes(_tres_no_radio()[:1])
    assert not _avisos(registros, "haptica_sem_ancora")
    assert not _avisos(registros, "haptica_ancoras_bastam")


# ------------------------------------------------------------------ o doctor


def _sysfs(raiz: Path, *, no_radio: int, ancoras: int, no_cabo: int = 0) -> Path:
    """`/sys` de mentira: DualSense por BT em `class/hidraw`, âncoras em `bus/usb`.

    O vpad do próprio Hefesto (HID_PHYS `hefesto-vpad`) entra de propósito: ele
    se diz DualSense, e contar ele seria o produto pedindo âncora para o
    próprio gamepad virtual.
    """
    hidraw = raiz / "class" / "hidraw"
    n = 0
    for i in range(no_radio):
        d = hidraw / f"hidraw{n}" / "device"
        d.mkdir(parents=True)
        d.joinpath("uevent").write_text(
            f"HID_ID=0005:0000054C:00000CE6\nHID_UNIQ=aa:bb:cc:00:00:{i + 1:02x}\n",
            encoding="utf-8",
        )
        n += 1
    for i in range(no_cabo):
        d = hidraw / f"hidraw{n}" / "device"
        d.mkdir(parents=True)
        d.joinpath("uevent").write_text(
            f"HID_ID=0003:0000054C:00000CE6\nHID_UNIQ=aa:bb:cc:00:01:{i + 1:02x}\n",
            encoding="utf-8",
        )
        n += 1
    vpad = hidraw / f"hidraw{n}" / "device"
    vpad.mkdir(parents=True)
    vpad.joinpath("uevent").write_text(
        "HID_ID=0005:0000054C:00000CE6\nHID_UNIQ=02:fe:00:00:00:01\nHID_PHYS=hefesto-vpad\n",
        encoding="utf-8",
    )
    usb = raiz / "bus" / "usb" / "devices"
    usb.mkdir(parents=True)
    for i in range(ancoras):
        nome = f"3-{i + 1}"
        d = usb / nome
        (d / f"{nome}:1.0").mkdir(parents=True)
        (d / f"{nome}:1.0" / "uevent").write_text("DEVTYPE=usb_interface\n", encoding="utf-8")
        (d / "busnum").write_text("3\n", encoding="utf-8")
        (d / "devnum").write_text(f"{i + 2}\n", encoding="utf-8")
    # Um aparelho COM placa de som não é âncora (o ContainerId dele já é de um
    # endpoint de verdade): tem de ficar de fora da conta.
    com_som = usb / "3-9"
    (com_som / "3-9:1.0" / "sound" / "card3").mkdir(parents=True)
    (com_som / "3-9:1.0" / "uevent").write_text("DEVTYPE=usb_interface\n", encoding="utf-8")
    (com_som / "busnum").write_text("3\n", encoding="utf-8")
    (com_som / "devnum").write_text("20\n", encoding="utf-8")
    return raiz


def _doctor(tmp_path: Path, sysfs: Path, python: str = sys.executable) -> str:
    r = subprocess.run(
        [
            "bash",
            "-c",
            f'source "{DOCTOR}"; '
            f"_python_do_produto() {{ printf '%s\\n' '{python}'; }}; "
            "check_ancoras_da_haptica_por_radio",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "HEFESTO_SYSFS": str(sysfs)},
    )
    return r.stdout + r.stderr


def test_doctor_acusa_as_ancoras_que_faltam(tmp_path: Path) -> None:
    """A MORDIDA: troque a comparação e a falta passa em verde."""
    saida = _doctor(tmp_path, _sysfs(tmp_path / "sys", no_radio=3, ancoras=1))
    assert "[WARN] a vibração pelo rádio precisa de um aparelho USB sem som por controle" in saida
    assert "há 1 para 3 DualSense no rádio, e 2 fica(m) sem vibração" in saida


def test_doctor_passa_com_ancoras_de_sobra(tmp_path: Path) -> None:
    saida = _doctor(tmp_path, _sysfs(tmp_path / "sys", no_radio=2, ancoras=2, no_cabo=1))
    assert "[WARN]" not in saida
    assert "[ OK ] âncoras USB da vibração pelo rádio: 2 para 2 controle(s)" in saida


def test_doctor_calado_sem_dualsense_no_radio(tmp_path: Path) -> None:
    saida = _doctor(tmp_path, _sysfs(tmp_path / "sys", no_radio=0, ancoras=0, no_cabo=2))
    assert "[WARN]" not in saida and "[ OK ]" not in saida
    assert "nenhum DualSense no rádio" in saida


def test_doctor_sem_o_pacote_se_declara_incapaz(tmp_path: Path) -> None:
    """Um python que não acha o pacote não pode responder "está tudo bem"."""
    falso = tmp_path / "python-sem-pacote"
    falso.write_text("#!/bin/sh\nprintf 'sem-produto\\n'\n", encoding="utf-8")
    falso.chmod(0o755)
    saida = _doctor(tmp_path, _sysfs(tmp_path / "sys", no_radio=3, ancoras=0), str(falso))
    assert "[WARN]" not in saida and "[ OK ]" not in saida
    assert "não conferidas" in saida


def test_o_doctor_roda_a_checagem() -> None:
    texto = DOCTOR.read_text(encoding="utf-8")
    corpo = texto[texto.index("\nmain() {") :]
    corpo = corpo[: corpo.index("\n}\n")]
    assert "\n    check_ancoras_da_haptica_por_radio\n" in corpo
