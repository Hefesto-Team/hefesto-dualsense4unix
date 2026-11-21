"""O reset do cabo se registra por porta e o doctor conta.

O vigia do kernel recebe a linha ``reset high-speed USB device`` e a leva ao ``usb-diario`` com a
porta, os hubs acima e a controladora; a volta do aparelho na mesma porta sai com o motivo
``reset_usb``; o doctor conta por porta nos últimos sete dias. Kernel, ``/sys`` e diário são de
mentira (``tests/fixtures/cadeia_usb``), nada lê o barramento da máquina que roda a suíte.

A conta é por porta e por controle: o reset de um controle no cabo não entra na conta de outro, o
controle que passa do rádio para o cabo no meio do jogo começa a contar na porta em que entrou, e
o adaptador de rádio que carrega dois controles conta como a porta dele, nunca como a de um deles.

Mordidas:

* tirar o ramo ``[USB-RESET]`` do ``anotar`` em ``scripts/storm_watch.sh``: o reset não chega ao
  diário e :func:`test_o_vigia_leva_o_reset_ao_diario_com_porta_hubs_e_controladora` reprova;
* tirar ``por_que=self._motivo_da_volta(...)`` da volta no ``Comparador``:
  :func:`test_a_volta_leva_o_motivo_reset_usb_so_na_porta_que_resetou` reprova;
* tirar o mesmo motivo da volta que passa pela saída (o aparelho sumiu do barramento):
  :func:`test_a_volta_que_some_do_barramento_depois_do_reset_leva_o_motivo` reprova;
* tirar o corte de sete dias de ``contar_os_resets``:
  :func:`test_o_doctor_conta_por_porta_na_janela` reprova;
* trocar ``len(com_hub) == len(contagem)`` por ``bool(com_hub)`` em ``laudo_dos_resets``:
  :func:`test_o_hub_so_e_o_suspeito_sem_reset_em_porta_do_computador` reprova.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import ouvido_do_usb as ou
from hefesto_dualsense4unix.integrations import diario_do_usb as du
from hefesto_dualsense4unix.integrations import storm_doctor as sd
from hefesto_dualsense4unix.integrations.censo_do_barramento import ler_o_barramento
from tests.fixtures.cadeia_usb.montar import SERIAL_FORJADO, SysDeMentira, carregar

RAIZ = Path(__file__).resolve().parents[2]
VIGIA = RAIZ / "scripts" / "storm_watch.sh"
DOCTOR = RAIZ / "scripts" / "doctor.sh"

CONTROLADORA = "0000:aa:00.0"
ATRAS_DO_HUB = "3-1.1.1"
NO_COMPUTADOR = "3-2"
OUTRO_ATRAS_DO_HUB = "3-1.1.4"
ADAPTADOR = "3-1.1.3"
HORA_DO_KERNEL = "2026-11-21T11:25:18-03:00"
CARIMBO_DO_KERNEL = 1_795_000_000.0


def _controle(devpath: str, pai: str, devnum: int, *, serial: bool = False) -> dict[str, Any]:
    no: dict[str, Any] = {
        "pai": pai,
        "attrs": {
            "idVendor": "054c", "idProduct": "0ce6", "bDeviceClass": "00", "busnum": "3",
            "devpath": devpath, "speed": "12", "version": "2.00", "devnum": str(devnum),
            "bMaxPower": "500mA", "bmAttributes": "80", "manufacturer": "Fabrica Ficticia",
            "product": "Controle de mentira",
        },
        "interfaces": {f"3-{devpath}:1.0": {"tripla": "030000", "driver": "usbhid"}},
    }
    if serial:
        no["serial_forjado"] = True
    return no


def _adaptador(devpath: str, devnum: int) -> dict[str, Any]:
    """Outro adaptador de rádio, com a forma do que o ``/sys`` de mentira já traz."""
    modelo = carregar()["nos"][ADAPTADOR]
    modelo["attrs"].update(devpath=devpath, devnum=str(devnum))
    modelo["interfaces"] = {
        f"3-{devpath}:{nome.split(':')[1]}": dados
        for nome, dados in modelo["interfaces"].items()
    }
    return modelo


def _linha_do_kernel(porta: str, velocidade: str = "high-speed", devnum: int = 12) -> str:
    return f"usb {porta}: reset {velocidade} USB device number {devnum} using xhci_hcd"


def _linha_do_diario_do_sistema(
    porta: str, quando: str = HORA_DO_KERNEL, velocidade: str = "high-speed"
) -> str:
    return f"{quando} computador kernel: {_linha_do_kernel(porta, velocidade)}"


@pytest.fixture
def sys_usb(tmp_path: Path) -> SysDeMentira:
    return SysDeMentira(tmp_path / "sys")


class Relogio:
    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


def _o_vigia(
    linhas: list[str], sys_usb: SysDeMentira, diario: Path, tmp_path: Path
) -> subprocess.CompletedProcess[str]:
    """As linhas do diário do sistema pelo ``--classify`` e pelo ``anotar``, como a unit as lê."""
    ambiente = dict(
        os.environ,
        HEFESTO_KERNELWATCH_PYTHON=sys.executable,
        HEFESTO_KERNELWATCH_SUDO="/nao/existe/sudo",
        HEFESTO_KERNELWATCH_SYSFS_USB=str(sys_usb.barramento),
        HEFESTO_USB_DIARIO=str(diario),
        PYTHONPATH=f"{RAIZ / 'src'}:{RAIZ}",
        XDG_STATE_HOME=str(tmp_path / "estado"),
    )
    classificado = subprocess.run(
        ["bash", str(VIGIA), "--classify"], input="\n".join(linhas) + "\n",
        capture_output=True, text=True, env=ambiente, check=True, timeout=30)
    return subprocess.run(
        ["bash", str(VIGIA), "--test-anotar", str(tmp_path / "trava")],
        input=classificado.stdout, capture_output=True, text=True, env=ambiente, timeout=90)


def _resets(diario: Path) -> list[dict[str, Any]]:
    return [e for e in du.ler(diario) if e["o_que"] == du.RESETOU]


def test_o_vigia_leva_o_reset_ao_diario_com_porta_hubs_e_controladora(
        sys_usb: SysDeMentira, tmp_path: Path) -> None:
    """Prova da D-2111-O-RESET-DO-CABO-ENTRA-NO-USB-DIARIO-POR-PORTA: a linha real do kernel."""
    sys_usb.por(ATRAS_DO_HUB, _controle("1.1.1", "3-1.1", 40, serial=True))
    diario = tmp_path / "estado" / du.NOME_DO_DIARIO
    saida = _o_vigia([_linha_do_diario_do_sistema(ATRAS_DO_HUB)], sys_usb, diario, tmp_path)
    assert saida.returncode == 0, saida.stderr
    assert "[USB-RESET]" in saida.stdout, saida.stdout
    assert f"usb {ATRAS_DO_HUB}: reset high-speed" in saida.stdout
    assert f" · lugar pci-{CONTROLADORA}-usb-0:1.1.1" in saida.stdout, saida.stdout
    resets = _resets(diario)
    assert len(resets) == 1, "o reset não chegou ao usb-diario"
    [linha] = resets
    assert linha["no"] == ATRAS_DO_HUB
    assert (linha["vid"], linha["pid"]) == ("054c", "0ce6")
    assert linha["velocidade"] == "high-speed"
    assert linha["hubs"] == ["3-1"], "o hub de plástico, com a cascata interna contada uma vez"
    assert linha["controladora"] == CONTROLADORA
    assert linha["carimbo"] == du.carimbo_do_kernel(HORA_DO_KERNEL)
    assert SERIAL_FORJADO not in diario.read_text(encoding="utf-8"), "o serial nunca entra"


def test_o_vigia_sem_o_python_do_produto_diz_que_o_reset_nao_entrou(
        sys_usb: SysDeMentira, tmp_path: Path) -> None:
    """Ausência é resposta: sem o python, a linha do log confessa e o reset segue no log."""
    diario = tmp_path / "estado" / du.NOME_DO_DIARIO
    ambiente = dict(
        os.environ, HEFESTO_KERNELWATCH_PYTHON="", HEFESTO_KERNELWATCH_SUDO="/nao/existe/sudo",
        HEFESTO_KERNELWATCH_LANCADOR=str(tmp_path / "sem-lancador"),
        HEFESTO_KERNELWATCH_SYSFS_USB=str(sys_usb.barramento), HEFESTO_USB_DIARIO=str(diario))
    classificado = subprocess.run(
        ["bash", str(VIGIA), "--classify"], input=_linha_do_diario_do_sistema(ATRAS_DO_HUB) + "\n",
        capture_output=True, text=True, env=ambiente, check=True, timeout=30)
    saida = subprocess.run(
        ["bash", str(VIGIA), "--test-anotar", str(tmp_path / "trava")],
        input=classificado.stdout, capture_output=True, text=True, env=ambiente, timeout=60)
    assert "[USB-RESET]" in saida.stdout
    assert "o reset não entrou no usb-diario" in saida.stdout, saida.stdout
    assert not diario.exists()


@pytest.mark.parametrize(
    "velocidade",
    ["high-speed", "full-speed", "low-speed", "SuperSpeed", "SuperSpeed Plus Gen 2x1"],
)
def test_o_reset_em_qualquer_velocidade_se_le(velocidade: str) -> None:
    lido = du.ler_o_reset(_linha_do_kernel("3-4.4", velocidade, devnum=7))
    assert lido is not None
    assert (lido.no, lido.velocidade, lido.devnum, lido.host) == (
        "3-4.4", velocidade, 7, "xhci_hcd")


@pytest.mark.parametrize("mensagem", [
    "usb 3-4.4: new high-speed USB device number 12 using xhci_hcd",
    "usb 3-4: device descriptor read/64, error -71",
    "usbhid 3-4.4:1.3: can't add hid device: -71",
    "Bluetooth: hci0: command tx timeout",
])
def test_o_que_nao_e_reset_nao_se_le(mensagem: str) -> None:
    assert du.ler_o_reset(mensagem) is None


def test_a_mesma_linha_do_kernel_nao_entra_duas_vezes(
        sys_usb: SysDeMentira, tmp_path: Path) -> None:
    diario = tmp_path / "estado" / du.NOME_DO_DIARIO
    censo = ler_o_barramento(**sys_usb.fontes())
    mensagem = _linha_do_kernel(NO_COMPUTADOR)
    kw: dict[str, Any] = {"caminho": diario, "censo": censo, "boot_id": "boot-a"}
    assert du.registrar_o_reset(mensagem, quando=CARIMBO_DO_KERNEL, **kw) is not None
    assert du.registrar_o_reset(mensagem, quando=CARIMBO_DO_KERNEL, **kw) is None
    assert du.registrar_o_reset(mensagem, quando=CARIMBO_DO_KERNEL + 5, **kw) is not None
    assert len(_resets(diario)) == 2


def test_porta_do_computador_leva_hubs_vazio_e_aparelho_ausente_leva_so_a_porta(
        sys_usb: SysDeMentira, tmp_path: Path) -> None:
    sys_usb.por(NO_COMPUTADOR, _controle("2", "usb3", 41))
    diario = tmp_path / "estado" / du.NOME_DO_DIARIO
    kw: dict[str, Any] = {"caminho": diario, "boot_id": "boot-a"}
    censo = ler_o_barramento(**sys_usb.fontes())
    du.registrar_o_reset(_linha_do_kernel(NO_COMPUTADOR), quando=CARIMBO_DO_KERNEL,
                         censo=censo, **kw)
    du.registrar_o_reset(_linha_do_kernel("3-1.1.2.5"), quando=CARIMBO_DO_KERNEL + 1,
                         censo=censo, **kw)
    no_computador, ausente = _resets(diario)
    assert no_computador["hubs"] == [] and no_computador["controladora"] == CONTROLADORA
    assert (ausente["vid"], ausente["tipo"]) == ("", "")
    assert ausente["hubs"] == ["3-1"], "sem o aparelho, vale o primeiro ancestral no censo"
    assert ausente["controladora"] == CONTROLADORA


def _ouvido(sys_usb: SysDeMentira, tmp_path: Path, relogio: Relogio) -> ou.Ouvido:
    return ou.Ouvido(
        ler_censo=lambda: ler_o_barramento(**sys_usb.fontes()),
        diario=tmp_path / "estado" / du.NOME_DO_DIARIO,
        boot_id="boot-a", relogio=relogio, agora=lambda: relogio.t)


def _voltas(tmp_path: Path) -> dict[str, str]:
    return {
        str(e["no"]): str(e.get("por_que") or "")
        for e in du.ler(tmp_path / "estado" / du.NOME_DO_DIARIO) if e["o_que"] == du.VOLTOU
    }


def test_a_volta_leva_o_motivo_reset_usb_so_na_porta_que_resetou(
        sys_usb: SysDeMentira, tmp_path: Path) -> None:
    """Dois controles no cabo: o reset de um não dá motivo à volta do outro."""
    sys_usb.por(ATRAS_DO_HUB, _controle("1.1.1", "3-1.1", 40))
    sys_usb.por(NO_COMPUTADOR, _controle("2", "usb3", 41))
    relogio = Relogio(1_795_000_000.0)
    ouvido = _ouvido(sys_usb, tmp_path, relogio)
    ouvido.comecar(com_netlink=True)
    censo = ler_o_barramento(**sys_usb.fontes())
    du.registrar_o_reset(
        _linha_do_kernel(ATRAS_DO_HUB), quando=relogio.t - 2, caminho=ouvido.diario,
        censo=censo, boot_id="boot-a")

    sys_usb.mudar(ATRAS_DO_HUB, devnum="50")
    sys_usb.mudar(NO_COMPUTADOR, devnum="51")
    ouvido.reler()

    assert _voltas(tmp_path) == {ATRAS_DO_HUB: du.MOTIVO_RESET_USB, NO_COMPUTADOR: ""}


def test_o_cabo_tirado_e_o_reset_velho_nao_dao_motivo(
        sys_usb: SysDeMentira, tmp_path: Path) -> None:
    sys_usb.por(ATRAS_DO_HUB, _controle("1.1.1", "3-1.1", 40))
    sys_usb.por(NO_COMPUTADOR, _controle("2", "usb3", 41))
    relogio = Relogio(1_795_000_000.0)
    ouvido = _ouvido(sys_usb, tmp_path, relogio)
    ouvido.comecar(com_netlink=True)
    censo = ler_o_barramento(**sys_usb.fontes())
    du.registrar_o_reset(
        _linha_do_kernel(NO_COMPUTADOR), quando=relogio.t - du.JANELA_DO_RESET_S - 30,
        caminho=ouvido.diario, censo=censo, boot_id="boot-a")
    controle = dict(sys_usb.nos[ATRAS_DO_HUB])

    sys_usb.tirar(ATRAS_DO_HUB)
    ouvido.reler()
    relogio.t += 3
    sys_usb.por(ATRAS_DO_HUB, controle)
    sys_usb.mudar(NO_COMPUTADOR, devnum="52")
    ouvido.reler()

    assert _voltas(tmp_path) == {ATRAS_DO_HUB: "", NO_COMPUTADOR: ""}


def test_a_volta_que_some_do_barramento_depois_do_reset_leva_o_motivo(
        sys_usb: SysDeMentira, tmp_path: Path) -> None:
    """O reset que tira o aparelho do barramento: ele sai e volta na mesma porta com outro número.

    O outro controle no cabo sai e volta no mesmo instante, sem reset na porta dele, e segue sem
    motivo.
    """
    sys_usb.por(ATRAS_DO_HUB, _controle("1.1.1", "3-1.1", 40))
    sys_usb.por(NO_COMPUTADOR, _controle("2", "usb3", 41))
    relogio = Relogio(1_795_000_000.0)
    ouvido = _ouvido(sys_usb, tmp_path, relogio)
    ouvido.comecar(com_netlink=True)
    du.registrar_o_reset(
        _linha_do_kernel(ATRAS_DO_HUB), quando=relogio.t, caminho=ouvido.diario,
        censo=ler_o_barramento(**sys_usb.fontes()), boot_id="boot-a")
    atras, no_computador = dict(sys_usb.nos[ATRAS_DO_HUB]), dict(sys_usb.nos[NO_COMPUTADOR])

    sys_usb.tirar(ATRAS_DO_HUB)
    sys_usb.tirar(NO_COMPUTADOR)
    relogio.t += 1
    ouvido.reler()
    relogio.t += 2.5
    sys_usb.por(ATRAS_DO_HUB, atras)
    sys_usb.por(NO_COMPUTADOR, no_computador)
    sys_usb.mudar(ATRAS_DO_HUB, devnum="50")
    sys_usb.mudar(NO_COMPUTADOR, devnum="51")
    ouvido.reler()

    assert _voltas(tmp_path) == {ATRAS_DO_HUB: du.MOTIVO_RESET_USB, NO_COMPUTADOR: ""}


def _entrada(porta: str, dias_atras: float, *, hubs: list[str], tipo: str = "Controle",
             controladora: str = CONTROLADORA, agora: float = 1_795_000_000.0) -> dict[str, Any]:
    return {
        "quando": "", "carimbo": agora - dias_atras * 86400, "quem": du.QUEM,
        "o_que": du.RESETOU, "no": porta, "hubs": hubs, "tipo": tipo,
        "controladora": controladora,
    }


def test_o_doctor_conta_por_porta_na_janela() -> None:
    agora = 1_795_000_000.0
    entradas = [
        _entrada(ATRAS_DO_HUB, 1, hubs=["3-1.1", "3-1"]),
        _entrada(ATRAS_DO_HUB, 3, hubs=["3-1.1", "3-1"]),
        _entrada(ATRAS_DO_HUB, 9, hubs=["3-1.1", "3-1"]),
        _entrada(NO_COMPUTADOR, 2, hubs=[]),
        _entrada(ATRAS_DO_HUB, 1, hubs=[], controladora="0000:bb:00.0"),
    ]
    contagem = sd.contar_os_resets(entradas, agora=agora)
    assert {c.lugar: c.quantos for c in contagem} == {
        f"pci-{CONTROLADORA}-usb-0:1.1.1": 2,
        f"pci-{CONTROLADORA}-usb-0:2": 1,
        "pci-0000:bb:00.0-usb-0:1.1.1": 1,
    }, "o reset de nove dias fica fora; a mesma porta em outra controladora é outra porta"
    assert contagem[0].quantos == 2


def test_o_hub_so_e_o_suspeito_sem_reset_em_porta_do_computador() -> None:
    atras = [_entrada(ATRAS_DO_HUB, 1, hubs=["3-1.1", "3-1"]),
             _entrada(OUTRO_ATRAS_DO_HUB, 2, hubs=["3-1.1", "3-1"])]
    marcas = [m for m, _ in sd.laudo_dos_resets(sd.contar_os_resets(atras, agora=1_795_000_000.0))]
    assert marcas.count("hub") == 1 and marcas[0] == "total"

    misturado = [*atras, _entrada(NO_COMPUTADOR, 1, hubs=[])]
    marcas = [m for m, _ in sd.laudo_dos_resets(
        sd.contar_os_resets(misturado, agora=1_795_000_000.0))]
    assert "hub" not in marcas

    vazio = sd.laudo_dos_resets(sd.contar_os_resets([], agora=1_795_000_000.0))
    assert [m for m, _ in vazio] == ["vazio"]


def test_o_cenario_de_quatro_controles_o_reset_conta_na_porta_em_que_o_controle_esta(
        sys_usb: SysDeMentira, tmp_path: Path) -> None:
    """Quatro controles, três adaptadores, o cabo no meio do jogo.

    D-2111-O-RESET-DO-CABO-ENTRA-NO-USB-DIARIO-POR-PORTA.

    P1 e P2 no mesmo adaptador de rádio, P3 e P4 em adaptadores próprios. P3 passa para o cabo
    atrás do hub, volta ao rádio e passa de novo para o cabo, agora numa porta do computador. O
    rádio não gera linha de reset; o reset do adaptador conta como a porta dele; cada porta do cabo
    conta os resets da própria porta, e a volta de um controle não toma o motivo de outro.
    """
    sys_usb.por("3-1.1.5", _adaptador("1.1.5", 45))
    sys_usb.por("3-1.1.6", _adaptador("1.1.6", 46))
    diario = tmp_path / "estado" / du.NOME_DO_DIARIO
    relogio = Relogio(1_795_000_000.0)
    ouvido = _ouvido(sys_usb, tmp_path, relogio)
    ouvido.comecar(com_netlink=True)

    def reset(porta: str, atraso: float = 1.0) -> None:
        du.registrar_o_reset(
            _linha_do_kernel(porta), quando=relogio.t - atraso, caminho=diario,
            censo=ler_o_barramento(**sys_usb.fontes()), boot_id="boot-a")

    reset(ADAPTADOR)

    p3_no_cabo = _controle("1.1.1", "3-1.1", 40)
    sys_usb.por(ATRAS_DO_HUB, p3_no_cabo)
    ouvido.reler()
    reset(ATRAS_DO_HUB)
    reset(ATRAS_DO_HUB, atraso=0.5)
    sys_usb.mudar(ATRAS_DO_HUB, devnum="41")
    relogio.t += 2
    ouvido.reler()

    sys_usb.tirar(ATRAS_DO_HUB)
    ouvido.reler()
    relogio.t += 120
    sys_usb.por(NO_COMPUTADOR, _controle("2", "usb3", 42))
    ouvido.reler()
    reset(NO_COMPUTADOR)

    contagem = {c.porta: c for c in sd.contar_os_resets(du.ler(diario), agora=relogio.t)}
    assert {p: c.quantos for p, c in contagem.items()} == {
        ADAPTADOR: 1, ATRAS_DO_HUB: 2, NO_COMPUTADOR: 1}
    assert contagem[ADAPTADOR].tipos == ("Bluetooth",)
    assert contagem[NO_COMPUTADOR].hubs == ()
    assert contagem[ATRAS_DO_HUB].hubs == ("3-1",)
    assert "hub" not in [m for m, _ in sd.laudo_dos_resets(list(contagem.values()))]
    assert _voltas(tmp_path) == {ATRAS_DO_HUB: du.MOTIVO_RESET_USB}


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


def _doctor(diario: Path | None) -> str:
    ambiente = dict(
        os.environ, TMPPYTHON=sys.executable, ROOT_DIR=str(RAIZ),
        HEFESTO_USB_DIARIO=str(diario or "/nao/existe/usb-diario.jsonl"),
    )
    r = subprocess.run(
        ["bash", "-c", _roteiro_do_doctor()], capture_output=True, text=True, env=ambiente,
        cwd=str(RAIZ), timeout=60)
    return r.stdout + r.stderr


def test_o_doctor_diz_a_porta_a_contagem_e_o_hub(tmp_path: Path) -> None:
    diario = tmp_path / du.NOME_DO_DIARIO
    agora = time.time()
    for porta, dias in ((ATRAS_DO_HUB, 1), (ATRAS_DO_HUB, 2), (OUTRO_ATRAS_DO_HUB, 3)):
        du.registrar(
            du.RESETOU,
            {"no": porta, "tipo": "Controle", "hubs": ["3-1.1", "3-1"],
             "controladora": CONTROLADORA},
            boot_id="boot-a", caminho=diario, agora=agora - dias * 86400)
    saida = _doctor(diario)
    assert "WARN 3 reset(s) de aparelho USB nos últimos 7 dias, em 2 porta(s)" in saida, saida
    assert f"INFO   porta {ATRAS_DO_HUB}, atrás do hub 3-1.1 (Controle): 2 vez(es)" in saida, saida
    assert "WARN todos os resets foram em portas atrás de hub (3-1.1)" in saida, saida
    assert "nenhum em porta do computador: a queda acompanha o hub" in saida, saida
    assert "ligue o aparelho direto numa porta do computador" in saida, (
        "o reset atrás do hub pode ser do adaptador de rádio, não só do controle")


def test_o_doctor_sem_diario_nao_inventa_contagem(tmp_path: Path) -> None:
    assert _doctor(None).strip() == ""
    diario = tmp_path / du.NOME_DO_DIARIO
    du.registrar(du.COMECOU_A_OUVIR, {"como": "netlink"}, boot_id="b", caminho=diario)
    assert "INFO nenhum reset de aparelho USB registrado nos últimos 7 dias" in _doctor(diario)
