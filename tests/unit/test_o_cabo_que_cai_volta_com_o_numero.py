"""O controle que cai por -71 volta com o MESMO número — STORM-USB-02, 24/09/2026.

A palavra dela de 23/09 é «nomear e religar»: o controle que cai por ``-71``
volta sozinho, **com o mesmo número de jogador**. O religar existia desde a
STORM-USB-01, no tique do watchdog root (``OnUnitActiveSec`` de 2 min; medido
no journal dela, mediana de 120 s entre dois tiques), e o lugar guardado de
quem sai vale 30 s (``identity.prazo_do_lugar_guardado``): religado no tique, o
controle voltava depois do prazo e os outros já tinham trocado de número. A
cura é o religar NA HORA do aviso do kernel.

A PROVA É A CORRENTE INTEIRA, DE VERDADE, CONTRA UM ``/sys`` DE MENTIRA::

    a linha do kernel ─► storm_watch.sh (classify | anotar) ─► o sudo de mentira
      ─► bt_ponte_privilegiada.sh religar-orfaos ─► bt_rebind_orphans.sh --evento
      ─► o ``bind`` ─► o kernel de mentira liga o driver
      ─► o registro de identidade REAL, com o relógio de mentira

Os três dublês, e por que nenhum é mais frouxo que o de verdade:

* **o /sys** — pastas e um arquivo ``bind`` por driver, como as réguas da 01;
* **o sudo** — aceita SÓ as linhas que a regra do sudoers aceita, lidas da
  saída do ``regra-sudo`` da ponte (o caminho instalado trocado pelo da
  árvore): sem a linha do verbo na regra, ele recusa e o controle não volta. O
  que ele NÃO faz, de propósito, é apagar o ambiente — o ``/sys`` de mentira
  chega à ponte pelos ganchos, que o sudo de verdade apagaria (e que a ponte e
  o religar apagam sob ``SUDO_UID``: a régua disso é a
  ``test_os_ganchos_de_teste_morrem_sob_sudo.py``). E ele recusa rodar sem
  os ganchos apontando para a mesa de mentira: é a guarda que sai. A única
  coisa que ele tem a mais é uma PAUSA pedida pela régua depois da N-ésima
  passada (o trabalho fica parado com a trava na mão), que é onde ela põe o
  aviso de outro controle no meio do trabalho sem depender do relógio;
* **o kernel** — o ``bind`` do kernel é SÍNCRONO (``bind_store`` →
  ``device_driver_attach`` → a probe): o link ``driver`` existe quando a
  escrita volta, e é isso que o religar confere na linha seguinte. Um arquivo
  comum não faz isso; por isso o kernel de mentira mora no ``printf`` do shell
  que escreve (``BASH_ENV``, só no que o sudo de mentira roda). A escrita
  falha, como no kernel, quando o aparelho não existe, já tem driver, não é do
  driver, ou a probe cai de novo (o arquivo ``probe-falha`` do nó).

O TEMPO. A corrente roda com as esperas em zero, e a régua soma as de verdade
no relógio do registro — todas LIDAS do produto: as esperas do
``storm_watch.sh``, o hotplug do daemon, o prazo do lugar guardado e o tique do
watchdog. Os dois números que não são do produto são medidas, e estão escritos
abaixo com a origem (:data:`ATRASO_DO_KERNEL`, :data:`CADEIA`).

AS MORDIDAS (arranque a cura, veja reprovar, devolva):

* :func:`test_o_cabo_que_perde_a_hid_volta_com_o_numero` e
  :func:`test_o_adaptador_que_cai_derruba_os_dois_e_cada_um_volta_com_o_seu`
  — tire a chamada do ``religar_em_fundo`` no ``anotar`` (ou a linha do
  ``religar-orfaos`` da regra do sudo) e as duas reprovam PELO NÚMERO: o
  controle voltaria no tique, e o P3 vira P2 enquanto o P2 está fora;
* :func:`test_as_esperas_cabem_no_lugar_guardado` — suba a primeira espera
  do ``storm_watch.sh`` para 4 s e ela reprova;
* :func:`test_o_aviso_que_chega_no_meio_do_trabalho_ganha_as_passadas_dele` —
  ponha ``RELIGAR_VOLTAS=1``, tire o byte do pedido ou esvazie o arquivo da
  trava no fim da volta (e não antes da primeira passada), e o P1 que perde a
  HID depois da última passada do trabalho do P2 fica sem driver até o tique;
* :func:`test_o_lugar_do_vigia_e_o_do_dono` — faça o ``lugar_da_porta`` pegar
  o PRIMEIRO controlador do caminho, e não o último;
* :func:`test_so_a_probe_perdida_chama_o_religar` — tire o ``0005`` da forma
  do ``[PROBE-PERDIDA]`` (o vpad do ``-17`` passaria a chamar o religar);
* :func:`test_o_aviso_tem_orcamento_proprio_e_esgota_calado` — tire o
  ``PREFIXO`` do contador (o aviso comeria as três do tique);
* :func:`test_quem_religa_limpa_os_dois_contadores` — volte o ``rm`` a apagar
  só o contador da passada;
* :func:`test_o_minus_71_de_outro_boot_e_lido_pelo_lugar` — tire a tradução
  do ``_porta_de_hoje`` e o -71 de ontem cai na entrada errada;
* :func:`test_como_root_a_ponte_so_roda_o_religar_que_e_so_do_root` — tire a
  guarda de dono (ou a de modo) do ``_o_religar`` e o religar gravável por
  outra conta passa a rodar como root.

Nada aqui toca o aparelho dela: nenhum ``/sys`` de verdade, nenhum sudo de
verdade, nenhum journal (o log do religar vai para um arquivo do ``tmp_path``).
Endereços forjados: MAC na faixa ``aa:bb:cc``, controladores PCI ``0000:0a`` e
``0000:0b``.
"""

from __future__ import annotations

import datetime
import os
import re
import subprocess
import time
from pathlib import Path

import pytest

from hefesto_dualsense4unix.daemon.connection import RECONNECT_HOTPLUG_POLL_INTERVAL_SEC
from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod
from hefesto_dualsense4unix.daemon.subsystems.identity import (
    ControllerIdentityRegistry,
    prazo_do_lugar_guardado,
)
from hefesto_dualsense4unix.integrations import exame_da_mesa as em
from hefesto_dualsense4unix.integrations.exame_da_mesa import (
    porta_do_evento,
    storm_por_porta,
)
from hefesto_dualsense4unix.integrations.mesa_de_radio import controladores_dos_barramentos
from hefesto_dualsense4unix.utils.lugar import lugar_do_caminho

REPO = Path(__file__).resolve().parents[2]
VIGIA = REPO / "scripts" / "storm_watch.sh"
PONTE = REPO / "scripts" / "bt_ponte_privilegiada.sh"
RELIGAR = REPO / "scripts" / "bt_rebind_orphans.sh"
CAMADA = REPO / "scripts" / "lib" / "camada_de_maquina.sh"
TIMER_DO_WATCHDOG = REPO / "assets" / "systemd" / "hefesto-bt-health-watchdog.timer"
UNIT_DO_VIGIA = REPO / "assets" / "hefesto-dualsense4unix-storm-watch.service"


# --- os números: do produto, lidos; e as duas medidas ----------------------


def _esperas() -> tuple[float, ...]:
    """As esperas do religar, do ``storm_watch.sh`` — nunca digitadas aqui."""
    casado = re.search(
        r"HEFESTO_KERNELWATCH_RELIGAR_ESPERAS:-([0-9. ]+)\}", VIGIA.read_text(encoding="utf-8")
    )
    assert casado, "as esperas do religar sumiram do storm_watch.sh"
    return tuple(float(x) for x in casado.group(1).split())


def _teto_do_religar() -> int:
    casado = re.search(
        r"HEFESTO_REBIND_MAX_TENTATIVAS:-([0-9]+)\}", RELIGAR.read_text(encoding="utf-8")
    )
    assert casado, "o teto do bt_rebind_orphans.sh sumiu"
    return int(casado.group(1))


def _tique_do_watchdog() -> float:
    casado = re.search(
        r"^OnUnitActiveSec=([0-9]+)(min|s)?\s*$",
        TIMER_DO_WATCHDOG.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert casado, "o timer do watchdog perdeu o OnUnitActiveSec"
    return float(casado.group(1)) * (60.0 if casado.group(2) == "min" else 1.0)


ESPERAS = _esperas()
POLL = float(RECONNECT_HOTPLUG_POLL_INTERVAL_SEC)
TIQUE = _tique_do_watchdog()

#: Da queda à linha do kernel que chama o religar. MEDIDO no journal dela em
#: 24/09 (só leitura, 27 boots): no cabo, a linha da HID perdida chegou 23 s e
#: 30 s depois da re-enumeração — as duas únicas da história dela —, porque a
#: HID é a ÚLTIMA interface do DualSense a subir: o áudio vem antes, e só ele
#: leva 15 s de mediana nas 43 enumerações que deram certo. A régua usa a
#: menor; a de 30 s passa do prazo mesmo com o religar na hora, e está escrita
#: no relatório como o limite desta cura.
ATRASO_DO_KERNEL = 23.0

#: O sudo, a ponte, o religar e a probe do ``hid-playstation`` que o ``bind``
#: dispara: décimos de segundo. Um segundo é folga — a corrente de mentira é
#: medida em cada caso e só precisa não esperar nada (:func:`Bancada.aviso`).
CADEIA = 1.0

#: O instante antes de o daemon ver o controle de volta.
QUASE = 0.001


# --- a bancada: o /sys de mentira, o sudo de mentira e o kernel de mentira --

PCI_DO_HUB = "0000:0a:00.0"
PCI_DO_RADIO = "0000:0b:00.0"
#: A ponte PCI de cima: o caminho real tem mais de um endereço, e o controlador
#: é o ÚLTIMO (é o que a mordida do lugar precisa para morder).
PONTE_PCI = "0000:00:08.1"

P1, P2, P3, P4 = "aabbcc000001", "aabbcc000002", "aabbcc000003", "aabbcc000004"
#: A bancada dela: o P1 e o P2 no cabo (um atrás do hub de 4 entradas, outro
#: direto nele), o P3 e o P4 no rádio de um adaptador USB.
NO_CABO = {P1: "3-4.1.3", P2: "3-4.4"}
NO_RADIO = {P3: "0005:054C:0CE6.0003", P4: "0005:054C:0CE6.0004"}
ADAPTADOR = "1-4"
HORA = "2026-09-24T21:00:00-03:00"

KERNEL_DE_MENTIRA = r"""
# O KERNEL DE MENTIRA (STORM-USB-02): o `bind` síncrono, no shell que escreve.
printf() {
    builtin printf "$@" || return
    local __k_eu="${BASHPID}" __k_alvo __k_nome __k_raiz __k_no __k_resto
    __k_alvo="$(readlink -f -- "/proc/${__k_eu}/fd/1" 2>/dev/null)" || return 0
    case "${__k_alvo}" in
        "$(readlink -f -- "${HEFESTO_USB_DRIVERS_DIR:-/nao}")/usbhid/bind")
            __k_raiz="${HEFESTO_USB_DEVICES_DIR:-/nao}" ;;
        "$(readlink -f -- "${HEFESTO_HID_DRIVERS_DIR:-/nao}")/playstation/bind")
            __k_raiz="${HEFESTO_HID_DEVICES_DIR:-/nao}" ;;
        *) return 0 ;;
    esac
    __k_nome="$(< "${__k_alvo}")"
    : > "${__k_alvo}"
    __k_no="${__k_raiz}/${__k_nome}"
    [[ -n "${__k_nome}" && -d "${__k_no}" && ! -L "${__k_no}/driver" ]] || return 1
    if [[ "${__k_raiz}" == "${HEFESTO_USB_DEVICES_DIR:-/nao}" ]]; then
        [[ "$(< "${__k_no}/bInterfaceClass")" == "03" ]] || return 1
    else
        [[ "${__k_nome}" =~ ^000[35]:054C:(0CE6|0DF2)\.[0-9A-F]{4}$ ]] || return 1
    fi
    if [[ -f "${__k_no}/probe-falha" ]]; then
        __k_resto="$(< "${__k_no}/probe-falha")"
        if (( __k_resto > 0 )); then
            builtin printf '%s' "$(( __k_resto - 1 ))" > "${__k_no}/probe-falha"
            return 1
        fi
    fi
    ln -s -- "${__k_alvo%/bind}" "${__k_no}/driver" || return 1
}
"""

SUDO_DE_MENTIRA = r"""#!/usr/bin/env bash
# O SUDO DE MENTIRA (STORM-USB-02): aceita SÓ o que a regra do sudoers aceita.
set -u
registro="${HEFESTO_TESTE_SUDO_REGISTRO:?}"
# A GUARDA QUE SAI: sem o /sys de mentira nos ganchos, a ponte olharia o de verdade.
raiz="${HEFESTO_TESTE_RAIZ:?}"
if [[ "${HEFESTO_HID_DEVICES_DIR:-}" != "${raiz}"/* \
      || "${HEFESTO_USB_DEVICES_DIR:-}" != "${raiz}"/* \
      || -n "${SUDO_UID:-}${SUDO_USER:-}" ]]; then
    echo "guarda: $*" >>"${registro}"
    exit 97
fi
[[ "${1:-}" == "-n" ]] || { echo "recusado (sem -n): $*" >>"${registro}"; exit 1; }
shift
lista=0
if [[ "${1:-}" == "-l" ]]; then lista=1; shift; fi
pedido="$*"
if ! grep -Fxq -- "${pedido}" "${HEFESTO_TESTE_SUDO_REGRAS:?}"; then
    echo "recusado: ${pedido}" >>"${registro}"
    exit 1
fi
if (( lista )); then echo "lista: ${pedido}" >>"${registro}"; exit 0; fi
echo "roda: ${pedido}" >>"${registro}"
BASH_ENV="${HEFESTO_TESTE_KERNEL:?}" "$@"
rc=$?
# A PAUSA DA RÉGUA: depois da N-ésima passada, o trabalho do religar fica
# parado aqui — com a trava na mão — até a régua dizer que siga. É onde ela põe
# o aviso de OUTRO controle no meio do trabalho, sem depender do relógio.
if [[ -n "${HEFESTO_TESTE_PAUSA_DEPOIS_DE:-}" ]] \
      && (( $(grep -c '^roda: ' "${registro}") == HEFESTO_TESTE_PAUSA_DEPOIS_DE )); then
    : >"${HEFESTO_TESTE_PAUSA:?}.parou"
    for _ in $(seq 600); do
        [[ -e "${HEFESTO_TESTE_PAUSA}.segue" ]] && break
        sleep 0.05
    done
fi
exit "${rc}"
"""


def _alvo_instalado() -> str:
    casado = re.search(r'^ALVO_INSTALADO="([^"]+)"', PONTE.read_text(encoding="utf-8"), re.M)
    assert casado, "a ponte perdeu o ALVO_INSTALADO"
    return casado.group(1)


def _regra_do_sudo() -> str:
    feito = subprocess.run(
        ["bash", str(PONTE), "regra-sudo", "fulana"],
        capture_output=True,
        text=True,
        check=False,
        env={**_ambiente_limpo(), "HEFESTO_BT_LOG_DEST": "none"},
        timeout=30,
    )
    assert feito.returncode == 0, feito.stderr
    return feito.stdout


def _linhas_permitidas(regra: str, ponte: Path) -> list[str]:
    """As linhas SEM curinga da regra, com o caminho instalado trocado pelo da árvore.

    As de curinga (os MAC) ficam de fora: o sudo de mentira não as aceita, o
    que é MAIS estrito que o de verdade — e o verbo desta sprint não tem
    argumento a casar.
    """
    alvo = _alvo_instalado()
    permitidas = []
    for linha in regra.splitlines():
        limpa = linha.strip().rstrip("\\").strip().rstrip(",").strip()
        if limpa.startswith(alvo + " ") and "[" not in limpa and "*" not in limpa:
            permitidas.append(str(ponte) + limpa[len(alvo):])
    return permitidas


def _ambiente_limpo() -> dict[str, str]:
    """O ambiente de quem roda, sem gancho da casa, sem SUDO_* e sem BASH_ENV."""
    return {
        chave: valor
        for chave, valor in os.environ.items()
        if not chave.startswith(("HEFESTO_", "SUDO_")) and chave != "BASH_ENV"
    }


class Bancada:
    """O ``/sys`` de mentira da mesa dela, e a corrente do religar ligada nele."""

    def __init__(self, tmp_path: Path, *, esperas: str = "0 0 0", regras: bool = True) -> None:
        self.tmp = tmp_path
        self.raiz = tmp_path / "sys"
        self.usb = self.raiz / "bus" / "usb" / "devices"
        self.usb_drivers = self.raiz / "bus" / "usb" / "drivers"
        self.hid = self.raiz / "bus" / "hid" / "devices"
        self.hid_drivers = self.raiz / "bus" / "hid" / "drivers"
        for pasta in (
            self.usb, self.usb_drivers / "usbhid", self.hid, self.hid_drivers / "playstation"
        ):
            pasta.mkdir(parents=True)
        (self.usb_drivers / "usbhid" / "bind").write_text("", encoding="utf-8")
        (self.hid_drivers / "playstation" / "bind").write_text("", encoding="utf-8")
        self.stamps = tmp_path / "run" / "hefesto-bt-rebind"
        self.stamps.mkdir(parents=True)
        self.log = tmp_path / "religar.log"
        self.registro = tmp_path / "sudo.log"
        self.trava = tmp_path / "estado" / "kernel-watch.religar"
        self.trava.parent.mkdir(parents=True)
        self.kernel = tmp_path / "kernel-de-mentira.bash"
        self.kernel.write_text(KERNEL_DE_MENTIRA, encoding="utf-8")
        self.sudo = tmp_path / "bin" / "sudo"
        self.sudo.parent.mkdir()
        self.sudo.write_text(SUDO_DE_MENTIRA, encoding="utf-8")
        self.sudo.chmod(0o755)
        self.regras = tmp_path / "regras-do-sudo"
        self.regras.write_text(
            "\n".join(_linhas_permitidas(_regra_do_sudo(), PONTE) if regras else []) + "\n",
            encoding="utf-8",
        )
        self.esperas = esperas
        #: nó do /sys (relativo à raiz) → o controle
        self.quem: dict[str, str] = {}
        self.devnum = 20
        self._hub_raiz(1, PCI_DO_RADIO, "0000:00:02.1")
        self._hub_raiz(2, PCI_DO_RADIO, "0000:00:02.1")
        self._hub_raiz(3, PCI_DO_HUB, PONTE_PCI)
        self._hub_raiz(4, PCI_DO_HUB, PONTE_PCI)
        self._no_usb(ADAPTADOR, vid="2357")
        self._interface(f"{ADAPTADOR}:1.0", classe="e0", driver="btusb")
        for uniq, porta in NO_CABO.items():
            self._controle_no_cabo(uniq, porta)
        for uniq, no in NO_RADIO.items():
            self._controle_no_radio(uniq, no, com_driver=True)

    # -- o /sys ---------------------------------------------------------------

    def _hub_raiz(self, bus: int, pci: str, ponte_pci: str) -> None:
        alvo = self.raiz / "devices" / "pci0000:00" / ponte_pci / pci / f"usb{bus}"
        alvo.mkdir(parents=True)
        os.symlink(alvo, self.usb / f"usb{bus}")

    def _no_usb(self, porta: str, *, vid: str = "054c") -> None:
        no = self.usb / porta
        no.mkdir(parents=True, exist_ok=True)
        (no / "idVendor").write_text(vid + "\n", encoding="utf-8")
        self.devnum += 1
        (no / "devnum").write_text(f"{self.devnum}\n", encoding="utf-8")

    def _interface(self, nome: str, *, classe: str, driver: str | None) -> None:
        no = self.usb / nome
        no.mkdir(parents=True, exist_ok=True)
        (no / "bInterfaceClass").write_text(classe + "\n", encoding="utf-8")
        if driver is not None:
            (self.usb_drivers / driver).mkdir(exist_ok=True)
            os.symlink(self.usb_drivers / driver, no / "driver")

    def _controle_no_cabo(self, uniq: str, porta: str) -> None:
        self._no_usb(porta)
        self._interface(f"{porta}:1.0", classe="01", driver="snd-usb-audio")
        self._interface(f"{porta}:1.3", classe="03", driver="usbhid")
        self.quem[f"bus/usb/devices/{porta}:1.3"] = uniq

    def _controle_no_radio(self, uniq: str, no: str, *, com_driver: bool) -> None:
        pasta = self.hid / no
        pasta.mkdir()
        if com_driver:
            os.symlink(self.hid_drivers / "playstation", pasta / "driver")
        self.quem[f"bus/hid/devices/{no}"] = uniq

    def ligados(self) -> set[str]:
        """O que o daemon enxerga: os controles com o HID de pé."""
        return {
            uniq
            for no, uniq in self.quem.items()
            if (self.raiz / no / "driver").exists()
        }

    # -- as quedas ------------------------------------------------------------

    def cai_o_cabo(self, uniq: str, *, probe_falha: int = 0) -> list[str]:
        """O -71: o aparelho re-enumera (outro ``devnum``) e a HID fica sem driver."""
        porta = NO_CABO[uniq]
        intf = self.usb / f"{porta}:1.3"
        (intf / "driver").unlink()
        self.devnum += 1
        (self.usb / porta / "devnum").write_text(f"{self.devnum}\n", encoding="utf-8")
        if probe_falha:
            (intf / "probe-falha").write_text(str(probe_falha), encoding="utf-8")
        return [
            f"{HORA} maquina kernel: usb {porta}: device descriptor read/64, error -71",
            f"{HORA} maquina kernel: usbhid {porta}:1.3: can't add hid device: -71",
            f"{HORA} maquina kernel: usbhid {porta}:1.3: "
            "probe with driver usbhid failed with error -71",
        ]

    def cai_o_radio(self) -> list[str]:
        """O -71 no adaptador: ele re-enumera, e os controles dele caem juntos."""
        for no in NO_RADIO.values():
            pasta = self.hid / no
            (pasta / "driver").unlink()
            pasta.rmdir()
            del self.quem[f"bus/hid/devices/{no}"]
        return [f"{HORA} maquina kernel: usb {ADAPTADOR}: device descriptor read/64, error -71"]

    def voltam_pelo_radio(self, orfaos: tuple[str, ...]) -> list[str]:
        """Os dois reconectam juntos (ids novos); os ``orfaos`` perdem a probe."""
        linhas = []
        for indice, (uniq, _) in enumerate(sorted(NO_RADIO.items()), start=0x11):
            no = f"0005:054C:0CE6.{indice:04X}"
            self._controle_no_radio(uniq, no, com_driver=uniq not in orfaos)
            if uniq in orfaos:
                linhas.append(
                    f"{HORA} maquina kernel: playstation {no}: "
                    "probe with driver playstation failed with error -5"
                )
        return linhas

    def no_de(self, uniq: str) -> str:
        return next(Path(no).name for no, dono in self.quem.items() if dono == uniq)

    # -- a corrente -----------------------------------------------------------

    def ambiente(self) -> dict[str, str]:
        return {
            **_ambiente_limpo(),
            "XDG_STATE_HOME": str(self.tmp / "estado"),
            "HEFESTO_KERNELWATCH_SUDO": str(self.sudo),
            "HEFESTO_KERNELWATCH_PONTE": str(PONTE),
            "HEFESTO_KERNELWATCH_SYSFS_USB": str(self.usb),
            "HEFESTO_KERNELWATCH_RELIGAR_ESPERAS": self.esperas,
            "HEFESTO_HID_DEVICES_DIR": str(self.hid),
            "HEFESTO_HID_DRIVERS_DIR": str(self.hid_drivers),
            "HEFESTO_USB_DEVICES_DIR": str(self.usb),
            "HEFESTO_USB_DRIVERS_DIR": str(self.usb_drivers),
            "HEFESTO_REBIND_STAMP_DIR": str(self.stamps),
            "HEFESTO_BT_LOG_DEST": str(self.log),
            "HEFESTO_TESTE_RAIZ": str(self.raiz),
            "HEFESTO_TESTE_SUDO_REGISTRO": str(self.registro),
            "HEFESTO_TESTE_SUDO_REGRAS": str(self.regras),
            "HEFESTO_TESTE_KERNEL": str(self.kernel),
        }

    def classificar(self, linhas: list[str]) -> list[str]:
        feito = subprocess.run(
            ["bash", str(VIGIA), "--classify"],
            input="\n".join(linhas) + "\n",
            capture_output=True,
            text=True,
            check=False,
            env=self.ambiente(),
            timeout=60,
        )
        assert feito.returncode == 0, feito.stderr
        return feito.stdout.splitlines()

    def aviso(self, linhas: list[str]) -> list[str]:
        """O aviso do kernel atravessa o ``classify | anotar`` de verdade."""
        classificadas = self.classificar(linhas)
        inicio = time.monotonic()
        feito = subprocess.run(
            ["bash", str(VIGIA), "--test-anotar", str(self.trava)],
            input="\n".join(classificadas) + "\n",
            capture_output=True,
            text=True,
            check=False,
            env=self.ambiente(),
            timeout=120,
        )
        duracao = time.monotonic() - inicio
        assert feito.returncode == 0, feito.stderr
        # Com as esperas em zero a corrente não espera nada: se esperasse, o
        # gancho das esperas teria parado de valer, e o tempo da régua mentiria.
        assert duracao < sum(ESPERAS), f"a corrente esperou {duracao:.1f} s com as esperas em zero"
        return feito.stdout.splitlines()

    def chamadas(self) -> list[str]:
        if not self.registro.exists():
            return []
        return self.registro.read_text(encoding="utf-8").splitlines()

    def frases(self) -> list[str]:
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []

    def passada_que_religou(self, uniq: str) -> int | None:
        """Qual passada do aviso religou este controle (0 = a primeira), ou ``None``."""
        no = self.no_de(uniq)
        falhas = 0
        for frase in self.frases():
            if no not in frase:
                continue
            if "NÃO pegou" in frase:
                falhas += 1
            elif "RELIGADO" in frase or "RECUPERADO" in frase:
                return falhas
        return None


class Relogio:
    """O relógio monotônico de mentira do registro — o prazo sem ``sleep``."""

    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora


class Mesa:
    """O registro de identidade DE PRODUÇÃO, com os quatro ligados em ordem."""

    ORDEM = (P1, P2, P3, P4)

    def __init__(self) -> None:
        self.relogio = Relogio()
        self.reg = ControllerIdentityRegistry(clock=self.relogio)
        presentes: list[str] = []
        for uniq in self.ORDEM:
            presentes.append(uniq)
            self.reg.sync_connected(list(presentes))
            self.relogio.agora += id_mod.JANELA_DE_ONDA_SEC * 2
        self.reg.liberar_as_lampadas()
        self.queda = self.relogio.agora

    def ve(self, ligados: set[str]) -> None:
        """O tique do daemon: o que está de pé, na ordem da mesa."""
        self.reg.sync_connected([u for u in self.ORDEM if u in ligados])

    def cai(self, ligados: set[str]) -> None:
        self.queda = self.relogio.agora
        self.ve(ligados)

    def em(self, segundos: float) -> None:
        """O relógio vai para ``segundos`` depois da queda."""
        alvo = self.queda + segundos
        assert alvo >= self.relogio.agora, "o relógio da régua não volta"
        self.relogio.agora = alvo

    def tela(self) -> dict[str, int]:
        return self.reg.numeros_da_mesa()


@pytest.fixture
def config_isolado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """``config_dir`` em tmp — nada aqui toca o ``controllers.json`` dela."""
    from hefesto_dualsense4unix.utils import xdg_paths

    config = tmp_path / "config"

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            config.mkdir(parents=True, exist_ok=True)
        return config

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    monkeypatch.setattr(id_mod, "_read_boot_id", lambda: "boot-teste-o-cabo-que-cai")
    return config


def _volta(bancada: Bancada, uniq: str) -> float:
    """Segundos entre a linha do kernel e o daemon ver o controle de volta.

    Pela passada do aviso que o religou; sem ela, pelo tique do watchdog — a
    espera mediana até o próximo tique é metade do intervalo dele.
    """
    passada = bancada.passada_que_religou(uniq)
    if passada is None:
        return TIQUE / 2 + POLL
    return sum(ESPERAS[: passada + 1]) + CADEIA + POLL


# --- a prova: o cabo, o rádio, e o número ------------------------------------


@pytest.mark.usefixtures("config_isolado")
@pytest.mark.parametrize("quem", [P1, P2], ids=["p1-atras-do-hub", "p2-direto-no-hub"])
def test_o_cabo_que_perde_a_hid_volta_com_o_numero(tmp_path: Path, quem: str) -> None:
    """O -71 no cabo: a HID fica sem driver, o aviso religa, e ninguém anda.

    Nunca só o P1: os dois do cabo, um atrás do hub e outro direto nele.
    """
    bancada = Bancada(tmp_path)
    mesa = Mesa()
    antes = mesa.tela()
    assert antes == {P1: 1, P2: 2, P3: 3, P4: 4}

    linhas = bancada.cai_o_cabo(quem)
    mesa.cai(bancada.ligados())
    assert quem not in mesa.tela()
    mesa.em(ATRASO_DO_KERNEL)

    anotadas = bancada.aviso(linhas)
    lugar = f"pci-{PCI_DO_HUB}-usb-0:{NO_CABO[quem].partition('-')[2]}"
    assert all(linha.endswith(f" · lugar {lugar}") for linha in anotadas), anotadas

    # A régua mede PELO NÚMERO: sem o religar na hora, a volta é a do tique.
    volta = _volta(bancada, quem)
    mesa.em(ATRASO_DO_KERNEL + volta - QUASE)
    mesa.ve(bancada.ligados() - {quem})
    ficaram = {u: n for u, n in antes.items() if u != quem}
    assert mesa.tela() == ficaram, (
        f"o controle voltaria {ATRASO_DO_KERNEL + volta:.0f} s depois da queda, com o prazo em "
        f"{prazo_do_lugar_guardado():.0f} s — e os outros trocaram de número enquanto ele "
        f"estava fora: {mesa.tela()}"
    )
    mesa.em(ATRASO_DO_KERNEL + volta)
    mesa.ve(bancada.ligados())
    assert quem in bancada.ligados(), " | ".join(bancada.chamadas() + bancada.frases())
    assert mesa.tela() == antes, "ele voltou com outro número"


@pytest.mark.usefixtures("config_isolado")
@pytest.mark.parametrize(
    "orfaos", [(P3,), (P4,), (P3, P4)], ids=["o-p3-perde-a-probe", "o-p4-perde-a-probe", "os-dois"]
)
def test_o_adaptador_que_cai_derruba_os_dois_e_cada_um_volta_com_o_seu(
    tmp_path: Path, orfaos: tuple[str, ...]
) -> None:
    """O -71 no adaptador: os dois do rádio caem, voltam, e cada um fica com o seu.

    Os dois reconectam juntos, e quem perde a probe na disputa (a de 25/07) é
    religado pelo aviso. Quem reconecta limpo volta primeiro — e volta com o
    número DELE, não com o do que ainda está fora.
    """
    bancada = Bancada(tmp_path)
    mesa = Mesa()
    antes = mesa.tela()

    anotadas = bancada.aviso(bancada.cai_o_radio())
    assert anotadas[0].endswith(f" · lugar pci-{PCI_DO_RADIO}-usb-0:4"), anotadas
    assert not bancada.chamadas(), "o -71 do adaptador não é probe perdida: nada a religar ainda"
    mesa.cai(bancada.ligados())
    assert mesa.tela() == {P1: 1, P2: 2}

    mesa.em(ATRASO_DO_KERNEL)
    linhas = bancada.voltam_pelo_radio(orfaos)
    limpos = {P3, P4} - set(orfaos)
    mesa.em(ATRASO_DO_KERNEL + POLL)
    mesa.ve(bancada.ligados())
    assert mesa.tela() == {P1: 1, P2: 2, **{u: antes[u] for u in limpos}}, (
        "quem reconectou limpo pegou o número de quem ainda está fora"
    )

    bancada.aviso(linhas)
    volta = max(_volta(bancada, uniq) for uniq in orfaos)
    mesa.em(ATRASO_DO_KERNEL + volta - QUASE)
    mesa.ve(bancada.ligados() - set(orfaos))
    assert mesa.tela() == {u: n for u, n in antes.items() if u not in orfaos}, (
        f"os do rádio voltariam {ATRASO_DO_KERNEL + volta:.0f} s depois da queda, e os outros "
        f"trocaram de número: {mesa.tela()}"
    )
    mesa.em(ATRASO_DO_KERNEL + volta)
    mesa.ve(bancada.ligados())
    assert set(orfaos) <= bancada.ligados(), " | ".join(bancada.chamadas() + bancada.frases())
    assert mesa.tela() == antes


def test_as_esperas_cabem_no_lugar_guardado() -> None:
    """A primeira passada, a corrente e o hotplug cabem no prazo depois do kernel.

    E são tantas esperas quanto o teto do aviso no religar: uma a mais seria
    uma chamada que o contador recusa; uma a menos, uma tentativa jogada fora.
    """
    prazo = prazo_do_lugar_guardado()
    assert len(ESPERAS) == _teto_do_religar()
    assert ATRASO_DO_KERNEL + ESPERAS[0] + CADEIA + POLL < prazo, (
        "com a HID perdida mais rápida da mesa dela (23 s), a primeira passada "
        "já não devolve o controle dentro do prazo"
    )
    assert sum(ESPERAS) + CADEIA + POLL < prazo, "a última passada cai fora do prazo"
    # E o porquê da cura: pelo tique, a espera mediana sozinha passa do prazo.
    assert prazo < TIQUE / 2 + POLL


# --- a corrente, peça por peça ------------------------------------------------


def test_a_probe_que_cai_de_novo_tem_a_segunda_passada(tmp_path: Path) -> None:
    """A primeira escrita no ``bind`` falha (a probe caiu de novo); a segunda religa."""
    bancada = Bancada(tmp_path)
    bancada.aviso(bancada.cai_o_cabo(P2, probe_falha=1))
    assert P2 in bancada.ligados()
    assert bancada.passada_que_religou(P2) == 1, bancada.frases()
    frases = " | ".join(bancada.frases())
    assert "NÃO pegou (tentativa 1/3, na hora do aviso do kernel)" in frases
    assert "o kernel-watch tenta de novo em segundos, e depois o watchdog" in frases
    assert f"controle do cabo RELIGADO em {NO_CABO[P2]}, na hora do aviso do kernel" in frases


def test_sem_a_regra_do_sudo_nada_muda(tmp_path: Path) -> None:
    """O install sem senha, o Flatpak: o sudo recusa o ``-l`` e a corrente para ali.

    A linha segue para o log do mesmo jeito, e o tique continua religando.
    """
    bancada = Bancada(tmp_path, regras=False)
    linha = bancada.cai_o_cabo(P2)[1]
    anotadas = bancada.aviso([linha])
    assert len(anotadas) == 1
    assert P2 not in bancada.ligados()
    assert bancada.chamadas() == [f"recusado: {PONTE} religar-orfaos"]


def test_uma_rajada_e_um_trabalho_so(tmp_path: Path) -> None:
    """As duas linhas da HID perdida chegam juntas: um ``-l``, uma passada por espera."""
    bancada = Bancada(tmp_path, esperas="1")
    bancada.aviso(bancada.cai_o_cabo(P2))
    chamadas = bancada.chamadas()
    assert chamadas == [f"lista: {PONTE} religar-orfaos", f"roda: {PONTE} religar-orfaos"], chamadas


def test_o_aviso_que_chega_no_meio_do_trabalho_ganha_as_passadas_dele(tmp_path: Path) -> None:
    """Nunca só o primeiro: o P1 perde a HID quando o trabalho do P2 já passou.

    Os controles de um adaptador que caiu reconectam cada um no seu tempo, e no
    cabo cada entrada falha na sua hora. O aviso do P1 chega com a trava na mão
    do trabalho do P2, DEPOIS da última passada dele: absorvido sem mais nada,
    o P1 esperaria o tique — e sairia do lugar guardado. O pedido que ele deixa
    no arquivo da trava dá ao trabalho mais uma volta inteira.

    A MORDIDA: tire a segunda volta do ``religar_em_fundo`` (o ``while``) e o
    P1 fica sem driver.
    """
    bancada = Bancada(tmp_path)
    pausa = tmp_path / "pausa"
    env = {
        **bancada.ambiente(),
        "HEFESTO_TESTE_PAUSA_DEPOIS_DE": str(len(ESPERAS)),
        "HEFESTO_TESTE_PAUSA": str(pausa),
    }
    do_p2 = bancada.classificar(bancada.cai_o_cabo(P2))
    trabalho = subprocess.Popen(
        ["bash", str(VIGIA), "--test-anotar", str(bancada.trava)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        assert trabalho.stdin is not None
        trabalho.stdin.write("\n".join(do_p2) + "\n")
        trabalho.stdin.close()
        parou = pausa.with_name(pausa.name + ".parou")
        limite = time.monotonic() + 60
        while not parou.exists():
            assert trabalho.poll() is None, "o trabalho do P2 acabou sem chegar à última passada"
            assert time.monotonic() < limite, " | ".join(bancada.chamadas())
            time.sleep(0.02)
        assert P2 in bancada.ligados(), " | ".join(bancada.frases())

        # O P1 cai AGORA, com o trabalho do P2 de pé e a trava na mão dele.
        do_p1 = bancada.classificar(bancada.cai_o_cabo(P1))
        feito = subprocess.run(
            ["bash", str(VIGIA), "--test-anotar", str(bancada.trava)],
            input="\n".join(do_p1) + "\n",
            capture_output=True,
            text=True,
            check=False,
            env=bancada.ambiente(),
            timeout=60,
        )
        assert feito.returncode == 0, feito.stderr
        assert bancada.chamadas().count(f"lista: {PONTE} religar-orfaos") == 1, (
            "o aviso do P1 abriu um trabalho seu: a trava não estava na mão do do P2"
        )
    finally:
        pausa.with_name(pausa.name + ".segue").touch()
        trabalho.wait(timeout=120)
    assert trabalho.returncode == 0, trabalho.stderr.read() if trabalho.stderr else ""
    assert P1 in bancada.ligados(), " | ".join(bancada.chamadas() + bancada.frases())
    assert bancada.passada_que_religou(P1) == 0, bancada.frases()


@pytest.mark.parametrize(
    "mensagem",
    [
        "usbhid 3-4.4:1.3: can't add hid device: -71",
        "usbhid 3-4.4:1.3: probe with driver usbhid failed with error -71",
        "playstation 0005:054C:0CE6.000F: probe with driver playstation failed with error -5",
        "playstation 0005:054C:0CE6.000F: probe with driver playstation failed with error -110",
    ],
)
def test_so_a_probe_perdida_chama_o_religar(tmp_path: Path, mensagem: str) -> None:
    """As duas formas que o ``bt_rebind_orphans.sh`` cura chamam o religar."""
    bancada = Bancada(tmp_path, regras=False)
    bancada.aviso([f"{HORA} maquina kernel: {mensagem}"])
    assert bancada.chamadas() == [f"recusado: {PONTE} religar-orfaos"]


@pytest.mark.parametrize(
    "mensagem",
    [
        "usb 3-4.4: device descriptor read/64, error -71",
        "usb 3-4.4: device not accepting address 12, error -71",
        "usb 3-4-port4: unable to enumerate USB device",
        # O vpad do próprio Hefesto no barramento 0003, com o MAC repetido.
        "playstation 0003:054C:0CE6.0011: probe with driver playstation failed with error -17",
        "Bluetooth: hci0: command 0x0c03 tx timeout",
    ],
)
def test_o_que_nao_e_probe_perdida_nao_chama(tmp_path: Path, mensagem: str) -> None:
    bancada = Bancada(tmp_path, regras=False)
    bancada.aviso([f"{HORA} maquina kernel: {mensagem}"])
    assert bancada.chamadas() == []


def test_a_guarda_do_gancho_sai_antes_de_ler(tmp_path: Path) -> None:
    """Sem o sudo de mentira, o ``--test-anotar`` sai com 2 e não escreve nada."""
    env = {k: v for k, v in Bancada(tmp_path).ambiente().items() if k != "HEFESTO_KERNELWATCH_SUDO"}
    feito = subprocess.run(
        ["bash", str(VIGIA), "--test-anotar", str(tmp_path / "trava")],
        input=(
            f"{HORA} [PROBE-PERDIDA] playstation 0005:054C:0CE6.000F: "
            "probe with driver playstation failed\n"
        ),
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=30,
    )
    assert feito.returncode == 2
    assert feito.stdout == ""


def test_a_linha_que_ja_tem_lugar_nao_ganha_outro(tmp_path: Path) -> None:
    bancada = Bancada(tmp_path, regras=False)
    ja = (
        f"{HORA} [USB-71] usb 3-4.4: device descriptor read/64, error -71"
        f" · lugar pci-{PCI_DO_HUB}-usb-0:4.4"
    )
    feito = subprocess.run(
        ["bash", str(VIGIA), "--test-anotar", str(bancada.trava)],
        input=ja + "\n",
        capture_output=True,
        text=True,
        check=False,
        env=bancada.ambiente(),
        timeout=30,
    )
    assert feito.stdout.splitlines() == [ja]


# --- o lugar: a cópia do vigia contra o dono ---------------------------------

MENSAGENS_DO_LUGAR = (
    "usb 3-4.1.3: device descriptor read/64, error -71",
    "usbhid 3-4.4:1.3: can't add hid device: -71",
    "uvcvideo 1-6:1.0: Failed to query (GET_CUR) UVC control 2 on unit 1: -71 (exp. 1).",
    "usb usb3-port4: Cannot enable. Maybe the USB cable is bad?",
    "usb 3-1.1-port3: Cannot enable. Maybe the USB cable is bad?",
    "usb 4-2: device not accepting address 7, error -71",
    "usb 9-1: device descriptor read/64, error -71",
    "xhci_hcd 0000:0a:00.0: HC died; cleaning up",
    "Bluetooth: hci0: command 0x0c03 tx timeout",
    "playstation 0005:054C:0CE6.000F: probe with driver playstation failed with error -5",
)


def test_o_lugar_do_vigia_e_o_do_dono(tmp_path: Path) -> None:
    """DUAS CÓPIAS, UMA FORMA: a porta e o lugar do bash contra os do Python.

    O vigia não carrega o Python do produto (roda no ``bash`` da unit); a
    grafia do lugar é do ``utils/lugar``, a porta é do ``exame_da_mesa``, e o
    controlador é o do ``mesa_de_radio``. As cinco formas da linha, mais um
    barramento que este ``/sys`` não tem e três linhas que não são de porta.
    """
    bancada = Bancada(tmp_path)
    feito = subprocess.run(
        ["bash", str(VIGIA), "--test-lugar"],
        input="\n".join(MENSAGENS_DO_LUGAR) + "\n",
        capture_output=True,
        text=True,
        check=False,
        env=bancada.ambiente(),
        timeout=30,
    )
    assert feito.returncode == 0, feito.stderr
    do_vigia = [tuple(linha.split("\t")) for linha in feito.stdout.splitlines()]
    controladores = controladores_dos_barramentos(raiz_usb=str(bancada.usb))
    assert controladores == {1: PCI_DO_RADIO, 2: PCI_DO_RADIO, 3: PCI_DO_HUB, 4: PCI_DO_HUB}
    do_dono = [
        (porta, lugar_do_caminho(porta, controladores) if porta else "")
        for porta in (porta_do_evento(m) for m in MENSAGENS_DO_LUGAR)
    ]
    assert do_vigia == do_dono
    assert ("3-4.4", f"pci-{PCI_DO_HUB}-usb-0:4.4") in do_vigia, "a régua não mediu nada"


def test_o_minus_71_de_outro_boot_e_lido_pelo_lugar(tmp_path: Path) -> None:
    """O -71 de ontem cai na entrada certa hoje, mesmo que a ordem dos xHCI mude.

    Ontem o hub pendurava no barramento 3 (``3-4.4``); hoje o mesmo controlador
    subiu como barramento 1. O lugar gravado na linha diz qual entrada é.
    """
    raiz = tmp_path / "sys" / "bus" / "usb" / "devices"
    raiz.mkdir(parents=True)
    for bus, pci in ((1, PCI_DO_HUB), (2, PCI_DO_HUB), (3, PCI_DO_RADIO), (4, PCI_DO_RADIO)):
        alvo = tmp_path / "sys" / "devices" / "pci0000:00" / PONTE_PCI / pci / f"usb{bus}"
        alvo.mkdir(parents=True)
        os.symlink(alvo, raiz / f"usb{bus}")
    (raiz / "1-4.4").mkdir()
    linhas = [
        f"2026-09-23T21:00:00-03:00 [USB-71] usbhid 3-4.4:1.3: can't add hid device: -71"
        f" · lugar pci-{PCI_DO_HUB}-usb-0:4.4",
        # A linha de antes de 24/09 não tem lugar: vale o caminho do log.
        "2026-09-23T21:05:00-03:00 [USB-71] usb 3-2: device descriptor read/64, error -71",
    ]
    laudo = storm_por_porta(
        linhas=linhas, hoje=datetime.date(2026, 9, 24), raiz_usb=raiz, nomear=em._sem_nome
    )
    assert sorted(p.porta for p in laudo.portas) == ["1-4.4", "3-2"], laudo.portas
    assert laudo.sem_endereco == 0


# --- a ponte: o verbo novo ------------------------------------------------------


def _ponte(
    bancada: Bancada, *args: str, ponte: Path = PONTE, ganchos: bool = True
) -> subprocess.CompletedProcess[str]:
    env = bancada.ambiente()
    if not ganchos:
        fora = ("HEFESTO_HID_DEVICES_DIR", "HEFESTO_USB_DEVICES_DIR")
        env = {k: v for k, v in env.items() if k not in fora}
    return subprocess.run(
        ["bash", str(ponte), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=60,
    )


def test_o_verbo_nao_recebe_argumento(tmp_path: Path) -> None:
    feito = _ponte(Bancada(tmp_path), "religar-orfaos", "3-4.4:1.3")
    assert feito.returncode == 2
    assert "quem escolhe o controle é o /sys" in feito.stderr


@pytest.mark.skipif(os.geteuid() == 0, reason="mede a recusa de quem não é root")
def test_sem_os_ganchos_o_verbo_exige_root(tmp_path: Path) -> None:
    bancada = Bancada(tmp_path)
    bancada.cai_o_cabo(P2)
    feito = _ponte(bancada, "religar-orfaos", ganchos=False)
    assert feito.returncode == 1
    assert "requer root" in feito.stderr
    assert bancada.frases() == []


def test_o_ensaio_diz_e_nao_escreve(tmp_path: Path) -> None:
    bancada = Bancada(tmp_path)
    bancada.cai_o_cabo(P2)
    feito = _ponte(bancada, "--dry-run", "religar-orfaos")
    assert feito.returncode == 0, feito.stderr
    assert (
        f"[dry-run] faria: echo '{NO_CABO[P2]}:1.3' > {bancada.usb_drivers}/usbhid/bind "
        "(tentativa 1/3, na hora do aviso do kernel)"
    ) in feito.stdout
    assert (bancada.usb_drivers / "usbhid" / "bind").read_text(encoding="utf-8") == ""
    assert list(bancada.stamps.iterdir()) == []


def test_sem_o_religar_ao_lado_a_ponte_recusa(tmp_path: Path) -> None:
    sozinha = tmp_path / "sozinha" / PONTE.name
    sozinha.parent.mkdir()
    sozinha.write_text(PONTE.read_text(encoding="utf-8"), encoding="utf-8")
    feito = _ponte(Bancada(tmp_path), "religar-orfaos", ponte=sozinha)
    assert feito.returncode == 1
    assert "não está ao lado desta ponte" in feito.stderr


#: O root de mentira: o ``id -u`` diz 0, e o ``stat -c %u`` diz o dono que a
#: régua pede (``HEFESTO_TESTE_DONO``); o resto vai para os de verdade.
ID_DE_MENTIRA = (
    "#!/usr/bin/env bash\n"
    '[[ "${1:-}" == "-u" ]] && { echo 0; exit 0; }\n'
    'exec /usr/bin/id "$@"\n'
)
STAT_DE_MENTIRA = (
    "#!/usr/bin/env bash\n"
    'if [[ "${1:-}" == "-c" && "${2:-}" == "%u" && -n "${HEFESTO_TESTE_DONO:-}" ]]; then\n'
    '    echo "${HEFESTO_TESTE_DONO}"; exit 0\n'
    "fi\n"
    'exec /usr/bin/stat "$@"\n'
)


@pytest.mark.parametrize(
    ("dono", "modo", "roda"),
    [("1000", 0o755, False), ("0", 0o775, False), ("0", 0o757, False), ("0", 0o755, True)],
    ids=["de-outra-conta", "gravavel-pelo-grupo", "gravavel-por-todos", "so-do-root"],
)
def test_como_root_a_ponte_so_roda_o_religar_que_e_so_do_root(
    tmp_path: Path, dono: str, modo: int, roda: bool
) -> None:
    """A regra do sudo abre o verbo sem senha, e o que ele RODA é o arquivo ao lado.

    Um religar que outra conta pode gravar seria root para quem o gravasse: como
    root, a ponte só o roda se ele for do root e ninguém mais puder escrever
    nele. O root aqui é de mentira (o ``id`` e o ``stat`` no PATH), e o par
    ponte-religar é uma cópia com o modo que a régua pede — o do disco é da conta
    de quem roda a suíte.

    A MORDIDA: tire a guarda de dono e de modo do ``_o_religar`` e as três
    recusas viram religar.
    """
    bancada = Bancada(tmp_path)
    bancada.cai_o_cabo(P2)
    lib = tmp_path / "lib"
    lib.mkdir()
    ponte = lib / PONTE.name
    ponte.write_text(PONTE.read_text(encoding="utf-8"), encoding="utf-8")
    religar = lib / RELIGAR.name
    religar.write_text(RELIGAR.read_text(encoding="utf-8"), encoding="utf-8")
    religar.chmod(modo)
    falsos = tmp_path / "bin-de-root"
    falsos.mkdir()
    for nome, texto in (("id", ID_DE_MENTIRA), ("stat", STAT_DE_MENTIRA)):
        (falsos / nome).write_text(texto, encoding="utf-8")
        (falsos / nome).chmod(0o755)
    env = {
        **bancada.ambiente(),
        "PATH": f"{falsos}{os.pathsep}{os.environ.get('PATH', '/usr/bin:/bin')}",
        "HEFESTO_TESTE_DONO": dono,
        "BASH_ENV": str(bancada.kernel),
    }
    feito = subprocess.run(
        ["bash", str(ponte), "religar-orfaos"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=60,
    )
    if roda:
        assert feito.returncode == 0, feito.stderr
        assert P2 in bancada.ligados(), " | ".join(bancada.frases())
    else:
        assert feito.returncode == 1, feito.stdout + feito.stderr
        assert "não é só do root" in feito.stderr
        assert P2 not in bancada.ligados()
        assert bancada.frases() == []


def test_a_regra_do_sudo_tem_o_verbo_sem_argumento() -> None:
    alvo = _alvo_instalado()
    linhas = [
        linha.strip()
        for linha in _regra_do_sudo().splitlines()
        if "religar-orfaos" in linha and not linha.lstrip().startswith("#")
    ]
    assert linhas == [f"{alvo} religar-orfaos, \\"], linhas


def test_o_vigia_chama_a_ponte_onde_o_install_a_poe() -> None:
    """O caminho que o kernel-watch chama é o da regra, e o religar mora ao lado.

    O verbo roda o ``bt_rebind_orphans.sh`` do MESMO diretório da ponte; é a
    camada do install que põe os dois lá.
    """
    alvo = _alvo_instalado()
    casado = re.search(r"HEFESTO_KERNELWATCH_PONTE:-([^}]+)\}", VIGIA.read_text(encoding="utf-8"))
    assert casado and casado.group(1) == alvo
    camada = CAMADA.read_text(encoding="utf-8")
    assert f"local _ponte_alvo={alvo}" in camada
    lista = re.search(
        r'for _btres_s in ([^;]+); do\s+sudo install -Dm755 \S+\s+\\\s+"([^"]+)/\$\{_btres_s\}"',
        camada,
    )
    assert lista, "a camada mudou a forma de instalar os scripts do rádio"
    assert "bt_rebind_orphans.sh" in lista.group(1).split()
    assert lista.group(2) == os.path.dirname(alvo)


def test_a_unit_do_vigia_deixa_o_sudo_funcionar() -> None:
    """Nada na unit do kernel-watch que implique ``NoNewPrivileges``.

    Numa unit de usuário, estas opções só se aplicam com ``NoNewPrivileges``
    ligado, e com ele o sudo (setuid) morre calado: o religar voltaria ao tique
    sem uma linha de aviso.
    """
    texto = UNIT_DO_VIGIA.read_text(encoding="utf-8")
    proibidas = (
        "NoNewPrivileges", "SystemCallFilter", "SystemCallArchitectures", "RestrictAddressFamilies",
        "RestrictNamespaces", "PrivateDevices", "ProtectKernelTunables", "ProtectKernelModules",
        "ProtectKernelLogs", "MemoryDenyWriteExecute", "RestrictRealtime", "RestrictSUIDSGID",
        "LockPersonality", "ProtectClock", "ProtectHostname",
    )
    assert [p for p in proibidas if re.search(rf"^\s*{p}\s*=", texto, re.MULTILINE)] == []


def test_o_servico_passa_pelo_anotar() -> None:
    """O serviço de verdade põe o ``anotar`` depois do ``classify``, com a trava volátil.

    A trava mora no diretório de execução (que o uninstall apaga inteiro), e
    não no estado: um arquivo que sobrasse ali seguraria o ``rmdir`` do estado.
    """
    texto = VIGIA.read_text(encoding="utf-8")
    assert '| classify | anotar "${TRAVA_DO_RELIGAR}" >>"${LOG}"' in texto
    volatil = 'TRAVA_DO_RELIGAR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/hefesto-dualsense4unix"'
    assert volatil in texto


# --- o religar: o orçamento do aviso -------------------------------------------


def _religar(
    bancada: Bancada, *args: str, kernel: bool = False
) -> subprocess.CompletedProcess[str]:
    env = bancada.ambiente()
    if kernel:
        env["BASH_ENV"] = str(bancada.kernel)
    return subprocess.run(
        ["bash", str(RELIGAR), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=60,
    )


def test_o_aviso_tem_orcamento_proprio_e_esgota_calado(tmp_path: Path) -> None:
    """As três do aviso não comem as três do tique, e a desistência é do tique."""
    bancada = Bancada(tmp_path)
    bancada.cai_o_cabo(P2)
    saidas = [_religar(bancada, "--evento", "--quiet").stdout for _ in range(4)]
    assert [s.count("NÃO pegou") for s in saidas] == [1, 1, 1, 0], saidas
    assert "(tentativa 3/3, na hora do aviso do kernel)" in saidas[2]
    assert saidas[3] == "", "o aviso esgotado fala — quem diz a desistência é o tique"
    assert "DESISTINDO" not in "".join(saidas)
    no = f"{NO_CABO[P2]}:1.3"
    devnum = (bancada.usb / NO_CABO[P2] / "devnum").read_text(encoding="utf-8").strip()
    assert sorted(p.name for p in bancada.stamps.iterdir()) == [f"evento-cabo-{no}-{devnum}"]

    tique = _religar(bancada, "--quiet").stdout
    assert "NÃO pegou (tentativa 1/3) — nova tentativa na próxima passagem do watchdog" in tique


@pytest.mark.parametrize("onde", ["cabo", "radio"])
def test_quem_religa_limpa_os_dois_contadores(tmp_path: Path, onde: str) -> None:
    bancada = Bancada(tmp_path)
    if onde == "cabo":
        bancada.cai_o_cabo(P2)
        devnum = (bancada.usb / NO_CABO[P2] / "devnum").read_text(encoding="utf-8").strip()
        chave = f"cabo-{NO_CABO[P2]}:1.3-{devnum}"
        frase = f"controle do cabo RELIGADO em {NO_CABO[P2]}, na hora do aviso do kernel"
    else:
        bancada.cai_o_radio()
        bancada.voltam_pelo_radio((P3,))
        chave = bancada.no_de(P3)
        frase = f"controle órfão RECUPERADO por rebind, na hora do aviso do kernel: {chave}"
    for nome, conteudo in ((chave, "1"), (f"{chave}.desisti", ""), (f"evento-{chave}", "2")):
        (bancada.stamps / nome).write_text(conteudo, encoding="utf-8")
    feito = _religar(bancada, "--evento", "--quiet", kernel=True)
    assert frase in feito.stdout, feito.stdout
    assert list(bancada.stamps.iterdir()) == []


def test_o_religar_diz_o_novo_uso() -> None:
    feito = subprocess.run(
        ["bash", str(RELIGAR), "--nao-existe"],
        capture_output=True,
        text=True,
        check=False,
        env={**_ambiente_limpo(), "HEFESTO_BT_LOG_DEST": "none"},
        timeout=30,
    )
    assert feito.returncode == 2
    assert "[--dry-run] [--quiet] [--evento]" in feito.stderr
