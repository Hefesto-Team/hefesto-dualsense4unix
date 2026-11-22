"""O controle que cai e volta no cabo se registra como queda, e o doctor conta.

Os números são os de 21/11/2026, 18h10min28, na porta ``3-1.4`` (atrás do hub ``3-1``): o
``USB disconnect`` às 28,691 e o ``new high-speed USB device number 9`` às 29,044 (353 ms depois,
sem reset no meio); o ``add`` do kernel só ~8,5 s depois da saída anotada, e o censo só o leu aos
19,9 s, porque a primeira leitura das strings espera a probe do som do próprio aparelho. Kernel,
``/sys``, netlink e diário são de mentira (``tests/fixtures/cadeia_usb``): nada aqui lê o journal
nem o USB da máquina que roda a suíte.

Prova da D-2211-A-QUEDA-DO-CABO-SEM-RESET-ENTRA-NO-DIARIO-POR-PORTA: a queda sem reset é uma linha
``caiu`` do diário, a volta se decide pela hora que o kernel avisou, e o diagnóstico conta por
porta, seja qual for o aparelho, o jogador, o cabo ou o rádio.

Mordidas (cada uma arrancada, vista reprovar e devolvida):

* ``fora_s = None`` no ``observar`` (a volta pela hora da foto):
  :func:`test_a_volta_se_decide_pela_hora_que_o_kernel_avisou_e_nao_pela_da_foto` reprova;
* tirar ``or self._motivo_da_queda(caminho) != ""`` da decisão da volta:
  :func:`test_a_queda_do_vigia_e_a_terceira_via_da_volta` reprova;
* tirar o ramo ``disconnect`` da classificação em ``scripts/storm_watch.sh``:
  :func:`test_o_vigia_leva_a_queda_ao_diario_e_nao_leva_o_que_nao_e_queda` reprova;
* tirar o filtro ``hq != "vhci_hcd"`` da classificação: o mesmo teste reprova pelo pad virtual;
* apagar todas as saídas guardadas quando uma porta volta (``delete saiu_em``):
  :func:`test_quatro_portas_que_caem_juntas_viram_quatro_quedas` reprova;
* tirar ``chegou < ponto`` de ``_fora_pelo_kernel``:
  :func:`test_o_aviso_de_antes_da_saida_nao_vira_volta` reprova;
* contar a saída pela leitura e não pelo ``remove`` (``ponto = saiu_em``):
  :func:`test_o_remove_do_kernel_conta_a_saida_pela_hora_dele` reprova;
* ``_campos_da_porta`` que lê o aparelho sem conferir se ele está no censo:
  :func:`test_a_queda_chega_com_a_porta_ainda_vazia_e_leva_a_porta_os_hubs_e_a_controladora`
  reprova;
* tirar o padrão do ``disconnect`` do ``GREP_UNION``:
  :func:`test_o_filtro_do_journal_deixa_passar_o_disconnect_e_o_new` reprova;
* tirar a chamada aos assinantes do ``_avisar_a_volta``: os testes do ouvido reprovam;
* tirar ``_ASSINANTES.append(ouvido.ouviu)`` do laço: o teste do laço reprova;
* tirar as quedas de ``laudo_dos_resets_do_diario``:
  :func:`test_o_doctor_conta_as_quedas_por_porta_e_diz_o_hub` reprova.
"""

from __future__ import annotations

import asyncio
import os
import re
import socket
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import connection
from hefesto_dualsense4unix.daemon.subsystems import ouvido_do_usb as ou
from hefesto_dualsense4unix.integrations import diario_do_usb as du
from hefesto_dualsense4unix.integrations import storm_doctor as sd
from hefesto_dualsense4unix.integrations.censo_do_barramento import ler_o_barramento
from hefesto_dualsense4unix.interface.arranjo_desta_maquina import _o_evento
from tests.fixtures.cadeia_usb.montar import SERIAL_FORJADO, SysDeMentira

RAIZ = Path(__file__).resolve().parents[2]
VIGIA = RAIZ / "scripts" / "storm_watch.sh"
DOCTOR = RAIZ / "scripts" / "doctor.sh"

CONTROLADORA = "0000:aa:00.0"
PORTA = "3-1.4"
OUTRA_PORTA = "3-1.2"
NO_COMPUTADOR = "3-2"
T0 = 1_795_295_429.379

DISCONNECT = "usb 3-1.4: USB disconnect, device number 8"
NOVO = "usb 3-1.4: new high-speed USB device number 9 using xhci_hcd"
LINHAS_DE_21_11 = (
    f"2026-11-21T18:10:28.691289-03:00 computador kernel: {DISCONNECT}",
    f"2026-11-21T18:10:29.044291-03:00 computador kernel: {NOVO}",
)
PAR_DO_PAD_VIRTUAL = (
    "2026-11-21T18:13:13.213000-03:00 computador kernel: usb 5-1: USB disconnect, device number 2",
    "2026-11-21T18:13:13.513000-03:00 computador kernel: "
    "usb 5-1: new high-speed USB device number 3 using vhci_hcd",
)
CABO_TIRADO_A_MAO = (
    "2026-11-21T22:28:30.004000-03:00 computador kernel: "
    "usb 3-1.2: USB disconnect, device number 5",
    "2026-11-21T22:28:41.100000-03:00 computador kernel: "
    "usb 3-1.2: new high-speed USB device number 6 using xhci_hcd",
)


def _controle(devpath: str, pai: str, devnum: int, *, serial: bool = False) -> dict[str, Any]:
    no: dict[str, Any] = {
        "pai": pai,
        "attrs": {
            "idVendor": "054c", "idProduct": "0ce6", "bDeviceClass": "00", "busnum": "3",
            "devpath": devpath, "speed": "480", "version": "2.00", "devnum": str(devnum),
            "bMaxPower": "500mA", "bmAttributes": "80", "manufacturer": "Fabrica Ficticia",
            "product": "Controle de mentira",
        },
        "interfaces": {f"3-{devpath}:1.0": {"tripla": "030000", "driver": "usbhid"}},
    }
    if serial:
        no["serial_forjado"] = True
    return no


def _uevent(acao: str, porta: str, tipo: str = "usb_device") -> bytes:
    caminho = f"/devices/pci0000:00/0000:aa:00.0/usb3/3-1/{porta}"
    return (f"{acao}@{caminho}\0ACTION={acao}\0DEVPATH={caminho}\0SUBSYSTEM=usb\0"
            f"DEVTYPE={tipo}\0PRODUCT=54c/ce6/100\0SEQNUM=1\0").encode()


class Relogio:
    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def sys_usb(tmp_path: Path) -> SysDeMentira:
    return SysDeMentira(tmp_path / "sys")


def _ouvido(sys_usb: SysDeMentira, tmp_path: Path, relogio: Relogio) -> ou.Ouvido:
    return ou.Ouvido(
        ler_censo=lambda: ler_o_barramento(**sys_usb.fontes()),
        diario=tmp_path / "estado" / du.NOME_DO_DIARIO,
        boot_id="boot-a", relogio=relogio, agora=lambda: relogio.t)


class _Daemon:
    def __init__(self) -> None:
        self.parar = False
        self._tasks: list[Any] = []

    def _is_stopping(self) -> bool:
        return self.parar


@pytest.fixture
def sem_sino(monkeypatch: pytest.MonkeyPatch) -> None:
    """O sino da volta e o relógio da conexão não são de quem testa o diário."""
    monkeypatch.setattr(connection, "acordar_a_volta", lambda _daemon, pelo="": None)
    monkeypatch.setattr(ou, "RELOGIO", SimpleNamespace(usb_entrou=lambda _caminho: None))


def _diario(tmp_path: Path) -> Path:
    return tmp_path / "estado" / du.NOME_DO_DIARIO


def _linhas(tmp_path: Path, o_que: str) -> list[dict[str, Any]]:
    return [e for e in du.ler(_diario(tmp_path)) if e["o_que"] == o_que]


def _a_queda_de_21_11(ouvido: ou.Ouvido, sys_usb: SysDeMentira, quando: float) -> None:
    du.registrar_a_queda(
        f"{DISCONNECT}, voltou em 353 ms como new high-speed USB device number 9 using xhci_hcd",
        quando=quando, caminho=ouvido.diario, censo=ler_o_barramento(**sys_usb.fontes()),
        boot_id="boot-a")


def _cenario_da_queda(
    sys_usb: SysDeMentira, tmp_path: Path, *, add_em: float | None, foto_em: float
) -> tuple[ou.Ouvido, Relogio]:
    """O controle sai em ``T0``, o ``add`` vem em ``T0 + add_em``, o censo lê em ``foto_em``."""
    sys_usb.por(PORTA, _controle("1.4", "3-1", 8))
    relogio = Relogio(T0 - 100.0)
    ouvido = _ouvido(sys_usb, tmp_path, relogio)
    ouvido.comecar(com_netlink=True)
    controle = dict(sys_usb.nos[PORTA])
    sys_usb.tirar(PORTA)
    relogio.t = T0
    ouvido.reler()
    if add_em is not None:
        relogio.t = T0 + add_em
        ouvido.ouviu(_uevent("add", PORTA))
    relogio.t = T0 + foto_em
    sys_usb.por(PORTA, controle)
    sys_usb.mudar(PORTA, devnum="11")
    ouvido.reler()
    return ouvido, relogio


def test_a_volta_se_decide_pela_hora_que_o_kernel_avisou_e_nao_pela_da_foto(
        sys_usb: SysDeMentira, tmp_path: Path) -> None:
    """O ``add`` em ``t + 8,5`` e a foto em ``t + 19,9``: é volta, e a linha diz o tempo fora."""
    _cenario_da_queda(sys_usb, tmp_path, add_em=8.5, foto_em=19.9)
    assert [e["o_que"] for e in du.ler(_diario(tmp_path))][1:] == [du.SAIU, du.VOLTOU]
    [volta] = _linhas(tmp_path, du.VOLTOU)
    assert volta["no"] == PORTA
    assert volta["fora_s"] == 8.5
    assert not _linhas(tmp_path, du.ENTROU), "um controle que cai não é um que entra"


def test_o_remove_do_kernel_conta_a_saida_pela_hora_dele(
        sys_usb: SysDeMentira, tmp_path: Path) -> None:
    """O ``remove`` às 28,691 e a saída lida às 29,379: o tempo fora parte do ``remove``."""
    sys_usb.por(PORTA, _controle("1.4", "3-1", 8))
    relogio = Relogio(T0 - 100.0)
    ouvido = _ouvido(sys_usb, tmp_path, relogio)
    ouvido.comecar(com_netlink=True)
    controle = dict(sys_usb.nos[PORTA])
    relogio.t = T0 - 0.688
    ouvido.ouviu(_uevent("remove", PORTA))
    sys_usb.tirar(PORTA)
    relogio.t = T0
    ouvido.reler()
    relogio.t = T0 + 8.5
    ouvido.ouviu(_uevent("add", PORTA))
    relogio.t = T0 + 19.9
    sys_usb.por(PORTA, controle)
    sys_usb.mudar(PORTA, devnum="11")
    ouvido.reler()
    [volta] = _linhas(tmp_path, du.VOLTOU)
    assert volta["fora_s"] == 9.2


def test_o_aviso_de_antes_da_saida_nao_vira_volta(
        sys_usb: SysDeMentira, tmp_path: Path) -> None:
    """Um ``add`` velho, de antes da saída, não diz quando o aparelho voltou."""
    sys_usb.por(PORTA, _controle("1.4", "3-1", 8))
    relogio = Relogio(T0 - 100.0)
    ouvido = _ouvido(sys_usb, tmp_path, relogio)
    ouvido.comecar(com_netlink=True)
    controle = dict(sys_usb.nos[PORTA])
    relogio.t = T0 - 50.0
    ouvido.ouviu(_uevent("add", PORTA))
    sys_usb.tirar(PORTA)
    relogio.t = T0
    ouvido.reler()
    relogio.t = T0 + 19.9
    sys_usb.por(PORTA, controle)
    sys_usb.mudar(PORTA, devnum="11")
    ouvido.reler()
    assert not _linhas(tmp_path, du.VOLTOU)
    assert len(_linhas(tmp_path, du.ENTROU)) == 1


def test_sem_aviso_do_kernel_vale_a_hora_da_leitura(
        sys_usb: SysDeMentira, tmp_path: Path) -> None:
    """Sem netlink vale o de antes: até 10 s depois da saída é volta, sem ``fora_s``."""
    _cenario_da_queda(sys_usb, tmp_path, add_em=None, foto_em=5.0)
    [volta] = _linhas(tmp_path, du.VOLTOU)
    assert "fora_s" not in volta

    outra = tmp_path / "outra"
    outra.mkdir()
    sys2 = SysDeMentira(outra / "sys")
    _cenario_da_queda(sys2, outra, add_em=None, foto_em=19.9)
    assert not _linhas(outra, du.VOLTOU)
    assert len(_linhas(outra, du.ENTROU)) == 1


@pytest.mark.parametrize(
    ("caiu_na_porta", "antes_s", "volta"),
    [
        (PORTA, 20.5, True),
        (OUTRA_PORTA, 20.5, False),
        (PORTA, 300.0, False),
        (None, 0.0, False),
    ],
    ids=["a-queda-desta-porta", "a-queda-de-outra-porta", "a-queda-velha", "sem-queda"],
)
def test_a_queda_do_vigia_e_a_terceira_via_da_volta(
        sys_usb: SysDeMentira, tmp_path: Path, caiu_na_porta: str | None, antes_s: float,
        volta: bool) -> None:
    """O ``add`` em ``t + 12`` passa dos 10 s; só a ``caiu`` desta porta, recente, o salva."""
    sys_usb.por(OUTRA_PORTA, _controle("1.2", "3-1", 5))
    sys_usb.por(PORTA, _controle("1.4", "3-1", 8))
    relogio = Relogio(T0 - 100.0)
    ouvido = _ouvido(sys_usb, tmp_path, relogio)
    ouvido.comecar(com_netlink=True)
    controle = dict(sys_usb.nos[PORTA])
    sys_usb.tirar(PORTA)
    relogio.t = T0
    ouvido.reler()
    if caiu_na_porta is not None:
        mensagem = (
            f"usb {caiu_na_porta}: USB disconnect, device number 8, voltou em 353 ms como new "
            "high-speed USB device number 9 using xhci_hcd")
        du.registrar_a_queda(
            mensagem, quando=T0 + 20.2 - antes_s, caminho=ouvido.diario,
            censo=ler_o_barramento(**sys_usb.fontes()), boot_id="boot-a")
    relogio.t = T0 + 12.0
    ouvido.ouviu(_uevent("add", PORTA))
    relogio.t = T0 + 20.2
    sys_usb.por(PORTA, controle)
    sys_usb.mudar(PORTA, devnum="11")
    ouvido.reler()
    voltas, entradas = _linhas(tmp_path, du.VOLTOU), _linhas(tmp_path, du.ENTROU)
    if volta:
        assert not entradas
        [linha] = voltas
        assert linha["por_que"] == du.MOTIVO_QUEDA_USB
        assert linha["fora_s"] == 12.0
    else:
        assert not voltas and len(entradas) == 1


def test_a_volta_depois_da_queda_leva_o_motivo_mesmo_dentro_dos_dez_segundos(
        sys_usb: SysDeMentira, tmp_path: Path) -> None:
    """A cadeia inteira: a ``caiu`` no diário, o ``add`` ouvido, e a volta sai ``queda_usb``."""
    sys_usb.por(PORTA, _controle("1.4", "3-1", 8))
    relogio = Relogio(T0 - 100.0)
    ouvido = _ouvido(sys_usb, tmp_path, relogio)
    ouvido.comecar(com_netlink=True)
    controle = dict(sys_usb.nos[PORTA])
    sys_usb.tirar(PORTA)
    relogio.t = T0
    ouvido.reler()
    _a_queda_de_21_11(ouvido, sys_usb, T0 - 0.335)
    relogio.t = T0 + 8.5
    ouvido.ouviu(_uevent("add", PORTA))
    relogio.t = T0 + 9.0
    sys_usb.por(PORTA, controle)
    sys_usb.mudar(PORTA, devnum="11")
    ouvido.reler()
    [volta] = _linhas(tmp_path, du.VOLTOU)
    assert (volta["por_que"], volta["fora_s"]) == (du.MOTIVO_QUEDA_USB, 8.5)


def _o_vigia(
    linhas: list[str], sys_usb: SysDeMentira, diario: Path, tmp_path: Path,
    **ambiente_extra: str
) -> subprocess.CompletedProcess[str]:
    """As linhas do journal pelo ``--classify`` e pelo ``anotar``, como a unit as lê."""
    ambiente = {
        **os.environ,
        "HEFESTO_KERNELWATCH_PYTHON": sys.executable,
        "HEFESTO_KERNELWATCH_SUDO": "/nao/existe/sudo",
        "HEFESTO_KERNELWATCH_SYSFS_USB": str(sys_usb.barramento),
        "HEFESTO_USB_DIARIO": str(diario),
        "PYTHONPATH": f"{RAIZ / 'src'}:{RAIZ}",
        "XDG_STATE_HOME": str(tmp_path / "estado"),
        **ambiente_extra,
    }
    classificado = subprocess.run(
        ["bash", str(VIGIA), "--classify"], input="\n".join(linhas) + "\n",
        capture_output=True, text=True, env=ambiente, check=True, timeout=30)
    return subprocess.run(
        ["bash", str(VIGIA), "--test-anotar", str(tmp_path / "trava")],
        input=classificado.stdout, capture_output=True, text=True, env=ambiente, timeout=90)


def test_o_vigia_leva_a_queda_ao_diario_e_nao_leva_o_que_nao_e_queda(
        sys_usb: SysDeMentira, tmp_path: Path) -> None:
    """D-2211-A-QUEDA-DO-CABO-SEM-RESET-ENTRA-NO-DIARIO-POR-PORTA.

    As linhas de 21/11 viram ``caiu``; o cabo tirado e o pad virtual, não."""
    sys_usb.por(PORTA, _controle("1.4", "3-1", 9, serial=True))
    diario = _diario(tmp_path)
    saida = _o_vigia(
        [*LINHAS_DE_21_11, *PAR_DO_PAD_VIRTUAL, *CABO_TIRADO_A_MAO], sys_usb, diario, tmp_path)
    assert saida.returncode == 0, saida.stderr
    assert saida.stdout.count("[USB-QUEDA]") == 1, saida.stdout
    assert "usb 5-1" not in saida.stdout and "usb 3-1.2" not in saida.stdout, saida.stdout
    assert f" · lugar pci-{CONTROLADORA}-usb-0:1.4" in saida.stdout, saida.stdout
    [caiu] = _linhas(tmp_path, du.CAIU)
    assert caiu["no"] == PORTA
    assert (caiu["vid"], caiu["pid"]) == ("054c", "0ce6")
    assert caiu["hubs"] == ["3-1"]
    assert caiu["controladora"] == CONTROLADORA
    assert (caiu["devnum_antes"], caiu["devnum"], caiu["fora_ms"]) == (8, 9, 353)
    assert caiu["host"] == "xhci_hcd"
    assert caiu["carimbo"] == pytest.approx(du.carimbo_do_kernel(
        "2026-11-21T18:10:29.044291-03:00"))
    assert SERIAL_FORJADO not in diario.read_text(encoding="utf-8"), "o serial nunca entra"
    assert len(du.ler(diario)) == 1, "nada além da queda entrou no diário"


def test_a_queda_chega_com_a_porta_ainda_vazia_e_leva_a_porta_os_hubs_e_a_controladora(
        sys_usb: SysDeMentira, tmp_path: Path) -> None:
    """Às 18:10:29,044 o aparelho novo ainda não está no ``/sys``: o lugar vem da porta e do hub."""
    sys_usb.tirar(PORTA)
    saida = _o_vigia(list(LINHAS_DE_21_11), sys_usb, _diario(tmp_path), tmp_path)
    assert saida.returncode == 0, saida.stderr
    assert f" · lugar pci-{CONTROLADORA}-usb-0:1.4" in saida.stdout, saida.stdout
    [caiu] = _linhas(tmp_path, du.CAIU)
    assert (caiu["no"], caiu["hubs"], caiu["controladora"]) == (PORTA, ["3-1"], CONTROLADORA)
    assert (caiu["vid"], caiu["pid"], caiu["fora_ms"]) == ("", "", 353)


def test_quatro_portas_que_caem_juntas_viram_quatro_quedas(
        sys_usb: SysDeMentira, tmp_path: Path) -> None:
    """O hub que pisca com P1 a P4 nele: as linhas se cruzam, cada porta é uma queda."""
    portas = ("3-1.1.2", "3-1.1.3", "3-1.1.4", PORTA)
    hora = "2026-11-21T18:10:{:06.3f}000-03:00 computador kernel: "
    linhas = [hora.format(28.1 + i * 0.01) + f"usb {p}: USB disconnect, device number {10 + i}"
              for i, p in enumerate(portas)]
    linhas.append(hora.format(28.2) + PAR_DO_PAD_VIRTUAL[0].split("kernel: ", 1)[1])
    linhas += [hora.format(28.5 + i * 0.1)
               + f"usb {p}: new high-speed USB device number {20 + i} using xhci_hcd"
               for i, p in enumerate(reversed(portas))]
    saida = _o_vigia(linhas, sys_usb, _diario(tmp_path), tmp_path)
    assert saida.returncode == 0, saida.stderr
    quedas = {c["no"]: c for c in _linhas(tmp_path, du.CAIU)}
    assert set(quedas) == set(portas), saida.stdout
    assert quedas[PORTA]["fora_ms"] == 370
    assert quedas["3-1.1.2"]["fora_ms"] == 700


def test_o_limiar_da_queda_e_um_segundo(sys_usb: SysDeMentira, tmp_path: Path) -> None:
    """353 ms é queda; 1,2 s no mesmo par não é, com o limiar de um segundo."""
    devagar = (
        "2026-11-21T18:10:28.691289-03:00 computador kernel: usb 3-1.4: USB disconnect, "
        "device number 8",
        "2026-11-21T18:10:29.891289-03:00 computador kernel: " + NOVO,
    )
    _o_vigia(list(devagar), sys_usb, _diario(tmp_path), tmp_path)
    assert not _linhas(tmp_path, du.CAIU)


def test_o_vigia_sem_o_python_do_produto_diz_que_a_queda_nao_entrou(
        sys_usb: SysDeMentira, tmp_path: Path) -> None:
    """Ausência é resposta: sem o python, a linha do log confessa e a queda segue no log."""
    diario = _diario(tmp_path)
    saida = _o_vigia(
        list(LINHAS_DE_21_11), sys_usb, diario, tmp_path,
        HEFESTO_KERNELWATCH_PYTHON="", HEFESTO_KERNELWATCH_LANCADOR=str(tmp_path / "sem-lancador"))
    assert "[USB-QUEDA]" in saida.stdout
    assert "a queda não entrou no usb-diario" in saida.stdout, saida.stdout
    assert not diario.exists()


def test_o_filtro_do_journal_deixa_passar_o_disconnect_e_o_new() -> None:
    """O ``--grep`` do journal é o primeiro filtro: sem o padrão, a queda nem chega ao vigia."""
    casou = re.search(r'^GREP_UNION="(.+)"$', VIGIA.read_text(encoding="utf-8"), re.M)
    assert casou is not None
    for mensagem in (DISCONNECT, NOVO):
        assert re.search(casou.group(1), mensagem, re.IGNORECASE), mensagem


@pytest.mark.parametrize("mensagem", [
    "usb 3-1.4: new high-speed USB device number 9 using xhci_hcd",
    "usb 3-1.4: USB disconnect, device number 8",
    "usb 3-1.4: reset high-speed USB device number 12 using xhci_hcd",
])
def test_o_que_nao_e_a_queda_montada_nao_se_le(mensagem: str) -> None:
    assert du.ler_a_queda(mensagem) is None


def test_a_mesma_queda_nao_entra_duas_vezes(sys_usb: SysDeMentira, tmp_path: Path) -> None:
    sys_usb.por(PORTA, _controle("1.4", "3-1", 9))
    mensagem = (
        f"{DISCONNECT}, voltou em 353 ms como new high-speed USB device number 9 using xhci_hcd")
    kw: dict[str, Any] = {
        "caminho": _diario(tmp_path), "censo": ler_o_barramento(**sys_usb.fontes()),
        "boot_id": "boot-a"}
    assert du.registrar_a_queda(mensagem, quando=T0, **kw) is not None
    assert du.registrar_a_queda(mensagem, quando=T0, **kw) is None
    assert du.registrar_a_queda(mensagem, quando=T0 + 7, **kw) is not None
    assert len(_linhas(tmp_path, du.CAIU)) == 2


def test_o_ouvido_guarda_o_add_e_o_remove_de_todo_aparelho_pelo_caminho(
        sys_usb: SysDeMentira, tmp_path: Path, sem_sino: None,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """O aviso do kernel chega pelo ``_drenar``, e interface não conta."""
    relogio = Relogio(T0)
    ouvido = _ouvido(sys_usb, tmp_path, relogio)
    monkeypatch.setattr(ou, "_ASSINANTES", [ouvido.ouviu])
    mensagens = [_uevent("add", PORTA), _uevent("remove", OUTRA_PORTA),
                 _uevent("add", "3-1.3", "usb_interface")]

    class Socket:
        def recv(self, _tamanho: int) -> bytes:
            if not mensagens:
                raise BlockingIOError
            return mensagens.pop(0)

    assert ou._drenar(Socket(), _Daemon())  # type: ignore[arg-type]
    assert ouvido.comparador._chegadas == {PORTA: T0}
    assert ouvido.comparador._partidas == {OUTRA_PORTA: T0}


def test_o_aviso_que_o_laco_espera_tambem_chega_ao_ouvido(
        sys_usb: SysDeMentira, tmp_path: Path, sem_sino: None,
        monkeypatch: pytest.MonkeyPatch) -> None:
    relogio = Relogio(T0)
    ouvido = _ouvido(sys_usb, tmp_path, relogio)
    monkeypatch.setattr(ou, "_ASSINANTES", [ouvido.ouviu])
    nosso, kernel = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
    nosso.setblocking(False)
    kernel.send(_uevent("add", PORTA))
    try:
        mudou, _sock = asyncio.run(ou._ouvir(nosso, 1.0, _Daemon()))
    finally:
        nosso.close()
        kernel.close()
    assert mudou
    assert ouvido.comparador._chegadas == {PORTA: T0}


def test_o_laco_leva_o_aviso_do_kernel_ao_comparador(
        sys_usb: SysDeMentira, tmp_path: Path, sem_sino: None) -> None:
    """O laço de verdade, com o netlink de mentira: o ``remove`` e o ``add`` dão ``fora_s``."""
    sys_usb.por(PORTA, _controle("1.4", "3-1", 8))
    ouvido = ou.Ouvido(
        ler_censo=lambda: ler_o_barramento(**sys_usb.fontes()), diario=_diario(tmp_path),
        boot_id="boot-a")
    daemon = _Daemon()
    nosso, kernel = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
    nosso.setblocking(False)
    controle = dict(sys_usb.nos[PORTA])

    async def cenario() -> None:
        laco = asyncio.create_task(ou.ouvido_do_usb_loop(
            daemon, ouvido, abrir=lambda: nosso, acomodar=0.01, prazo=2.0))

        async def ate(condicao: Any) -> None:
            fim = asyncio.get_running_loop().time() + 20.0
            while not condicao():
                assert not laco.done(), f"o laço morreu: {laco.exception()!r}"
                assert asyncio.get_running_loop().time() < fim, (
                    f"o ouvido não chegou lá no prazo: {du.ler(_diario(tmp_path))}")
                await asyncio.sleep(0.01)

        await ate(lambda: du.ler(_diario(tmp_path)))
        sys_usb.tirar(PORTA)
        kernel.send(_uevent("remove", PORTA))
        await ate(lambda: _linhas(tmp_path, du.SAIU))
        await asyncio.sleep(0.2)
        sys_usb.por(PORTA, controle)
        sys_usb.mudar(PORTA, devnum="11")
        kernel.send(_uevent("add", PORTA))
        await ate(lambda: _linhas(tmp_path, du.VOLTOU))
        daemon.parar = True
        kernel.send(_uevent("add", "3-1.9", "usb_interface"))
        await asyncio.wait_for(laco, 10.0)

    try:
        asyncio.run(cenario())
    finally:
        kernel.close()
    [volta] = _linhas(tmp_path, du.VOLTOU)
    assert 0.1 <= volta["fora_s"] <= 15.0, volta


def _roteiro_do_doctor() -> str:
    fonte = DOCTOR.read_text(encoding="utf-8")
    i = fonte.index("check_resets_do_usb() {\n")
    j = fonte.index("\n}\n", i)
    return textwrap.dedent(
        """
        set -uo pipefail
        warn() { printf 'WARN %s\\n' "$*"; }
        info() { printf 'INFO %s\\n' "$*"; }
        _python_do_produto() { printf '%s\\n' "$TMPPYTHON"; }
        """
    ) + fonte[i:j] + "\n}\ncheck_resets_do_usb\n"


def _doctor(diario: Path) -> str:
    ambiente = dict(
        os.environ, TMPPYTHON=sys.executable, ROOT_DIR=str(RAIZ), HEFESTO_USB_DIARIO=str(diario))
    r = subprocess.run(
        ["bash", "-c", _roteiro_do_doctor()], capture_output=True, text=True, env=ambiente,
        cwd=str(RAIZ), timeout=60)
    return r.stdout + r.stderr


def _caiu(diario: Path, porta: str, dias: float, *, hubs: list[str]) -> None:
    du.registrar(
        du.CAIU,
        {"no": porta, "tipo": "Controle", "hubs": hubs, "controladora": CONTROLADORA,
         "fora_ms": 353},
        boot_id="boot-a", caminho=diario, agora=time.time() - dias * 86400)


def test_o_doctor_conta_as_quedas_por_porta_e_diz_o_hub(tmp_path: Path) -> None:
    """A queda de 21/11 na ``3-1.4`` atrás do hub ``3-1``: 1 queda, a porta e a frase do hub."""
    diario = tmp_path / du.NOME_DO_DIARIO
    _caiu(diario, PORTA, 1, hubs=["3-1"])
    saida = _doctor(diario)
    assert "WARN 1 queda(s) de aparelho USB nos últimos 7 dias, em 1 porta(s)" in saida, saida
    assert f"INFO   porta {PORTA}, atrás do hub 3-1 (Controle): 1 vez(es)" in saida, saida
    assert "WARN todas as quedas foram em portas atrás de hub (3-1) e nenhuma em porta do" in saida
    assert "ligue o aparelho direto numa porta do computador" in saida
    assert "INFO nenhum reset de aparelho USB registrado nos últimos 7 dias" in saida, (
        "o laudo dos resets segue ao lado, sem se misturar com o das quedas")


def test_o_doctor_so_chama_o_hub_de_suspeito_sem_queda_no_computador(tmp_path: Path) -> None:
    diario = tmp_path / du.NOME_DO_DIARIO
    _caiu(diario, PORTA, 1, hubs=["3-1"])
    _caiu(diario, PORTA, 2, hubs=["3-1"])
    _caiu(diario, NO_COMPUTADOR, 3, hubs=[])
    _caiu(diario, OUTRA_PORTA, 9, hubs=["3-1"])
    saida = _doctor(diario)
    assert "WARN 3 queda(s) de aparelho USB nos últimos 7 dias, em 2 porta(s)" in saida, saida
    assert f"porta {PORTA}, atrás do hub 3-1 (Controle): 2 vez(es)" in saida
    assert f"porta {NO_COMPUTADOR}, direto no computador (Controle): 1 vez(es)" in saida
    assert "todas as quedas foram em portas atrás de hub" not in saida
    assert OUTRA_PORTA not in saida, "a queda de nove dias fica fora da janela"


def test_o_doctor_sem_queda_registrada_diz_que_nao_ha(tmp_path: Path) -> None:
    diario = tmp_path / du.NOME_DO_DIARIO
    du.registrar(du.COMECOU_A_OUVIR, {"como": "netlink"}, boot_id="b", caminho=diario)
    saida = _doctor(diario)
    assert "INFO nenhuma queda de aparelho USB registrada nos últimos 7 dias" in saida, saida


def test_a_conta_de_queda_e_por_lugar_e_nao_por_aparelho() -> None:
    agora = 1_795_300_000.0
    entradas = [
        {"carimbo": agora - 100, "o_que": du.CAIU, "no": PORTA, "tipo": "Controle",
         "hubs": ["3-1"], "controladora": CONTROLADORA},
        {"carimbo": agora - 200, "o_que": du.CAIU, "no": PORTA, "tipo": "Receptor 2.4G",
         "hubs": ["3-1"], "controladora": CONTROLADORA},
        {"carimbo": agora - 300, "o_que": du.CAIU, "no": PORTA, "tipo": "Controle",
         "hubs": [], "controladora": "0000:bb:00.0"},
        {"carimbo": agora - 400, "o_que": du.RESETOU, "no": PORTA, "tipo": "Controle",
         "hubs": ["3-1"], "controladora": CONTROLADORA},
    ]
    contagem = sd.contar_as_quedas_do_cabo(entradas, agora=agora)
    assert {c.lugar: c.quantos for c in contagem} == {
        f"pci-{CONTROLADORA}-usb-0:1.4": 2, "pci-0000:bb:00.0-usb-0:1.4": 1}
    assert contagem[0].tipos == ("Controle", "Receptor 2.4G")
    assert [c.quantos for c in sd.contar_os_resets(entradas, agora=agora)] == [1]


def test_a_aba_registro_diz_voltou_e_nao_ganha_linha_para_a_queda() -> None:
    """A ``voltou`` aparece como «Voltou»; a ``caiu`` fica de fora (mostrá-la pede desenho)."""
    assert _o_evento({"o_que": du.VOLTOU}) == ("Voltou", "")
    assert _o_evento({"o_que": du.SAIU}) == ("Saiu", "sai")
    assert _o_evento({"o_que": du.CAIU, "no": PORTA}) is None
