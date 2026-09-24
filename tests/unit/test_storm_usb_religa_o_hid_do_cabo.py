"""O controle do cabo que perdeu a HID no -71 é RELIGADO — STORM-USB-01, 24/09/2026.

A palavra dela de 23/09 é «nomear e religar»: *o controle que cai por -71 volta
sozinho*. No cabo, a probe perdida tem uma forma que o journal da mesa dela
guardou (16/09, a 3-4.4)::

    usbhid 3-4.4:1.3: can't add hid device: -71
    usbhid 3-4.4:1.3: probe with driver usbhid failed with error -71

O aparelho enumerou, a interface HID ficou sem driver, e o driver não refaz a
probe sozinho. O religar é o bind da interface no ``usbhid`` — pelo caminho
root que JÁ EXISTE: o ``bt_rebind_orphans.sh``, que o watchdog do Bluetooth
roda a cada 2 minutos como root, e que o install instala e o uninstall tira.

A CLASSE REAL CONTRA UM ``/sys`` DE MENTIRA: o script de verdade, com as raízes
desviadas para o ``tmp_path`` (as costuras ``HEFESTO_USB_*``), sem root e sem
hardware. O ``bind`` do ``usbhid`` é um arquivo comum: a régua lê o que o
script escreveu nele, e é isso que prova o gesto — o resto é do kernel.

AS MORDIDAS (arranque a cura, veja reprovar, devolva):

* :func:`test_religa_a_hid_do_controle_sony` — troque o nome escrito no
  ``bind`` pela porta (sem o ``:1.3``) e ela reprova.
* :func:`test_a_interface_de_audio_sem_driver_nao_e_tocada` — tire a guarda da
  classe ``03`` e ela reprova: a regra 75 desliga o áudio do DualSense de
  propósito, e o religar brigaria com ela.
* :func:`test_interface_desligada_de_proposito_nao_e_tocada` — tire a guarda do
  ``authorized``.
* :func:`test_orfa_que_nao_e_da_sony_e_ignorada` — tire a guarda do ``054c``.
* :func:`test_para_apos_o_teto_e_desiste_uma_vez_so` — tire o teto.
* :func:`test_tirar_e_por_o_cabo_da_orcamento_novo` — tire o ``devnum`` da
  chave do contador.
* :func:`test_a_arvore_de_25_07_nao_varre_o_cabo_de_quem_roda` — tire o ramo
  que zera a raiz do cabo quando só o HID foi desviado (morde pelo texto; o
  porquê está nela).
* :func:`test_sem_radio_o_tique_ainda_religa_o_cabo` (conferência de 24/09) —
  tire o ``vigia_rebind_orfaos`` de uma das duas guardas do Bluetooth no
  watchdog, ou devolva a definição dela para depois das guardas, e ela
  reprova: numa máquina sem adaptador o tique saía antes da vigia 4, e o cabo
  nunca era religado.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "bt_rebind_orphans.sh"
WATCHDOG = REPO_ROOT / "scripts" / "bt_health_watchdog.sh"
CAMADA = REPO_ROOT / "scripts" / "lib" / "camada_de_maquina.sh"
UNINSTALL = REPO_ROOT / "uninstall.sh"

INTERFACE = "3-4.4:1.3"
PORTA = "3-4.4"


def _aparelho(
    usb: Path, porta: str, *, vid: str = "054c", devnum: str = "12"
) -> None:
    no = usb / "devices" / porta
    no.mkdir(parents=True)
    (no / "idVendor").write_text(vid + "\n", encoding="utf-8")
    (no / "devnum").write_text(devnum + "\n", encoding="utf-8")


def _interface(
    usb: Path,
    nome: str,
    *,
    classe: str = "03",
    com_driver: bool = False,
    authorized: str | None = None,
) -> None:
    no = usb / "devices" / nome
    no.mkdir(parents=True)
    (no / "bInterfaceClass").write_text(classe + "\n", encoding="utf-8")
    if com_driver:
        alvo = usb / "drivers" / "algum"
        alvo.mkdir(parents=True, exist_ok=True)
        os.symlink(alvo, no / "driver")
    if authorized is not None:
        (no / "authorized").write_text(authorized + "\n", encoding="utf-8")


def _bancada(tmp_path: Path) -> Path:
    """O ``/sys`` de mentira: o HID do rádio vazio, e o ``usbhid/bind`` do cabo."""
    (tmp_path / "hid" / "devices").mkdir(parents=True)
    (tmp_path / "hid" / "drivers" / "playstation").mkdir(parents=True)
    (tmp_path / "hid" / "drivers" / "playstation" / "bind").write_text("", encoding="utf-8")
    (tmp_path / "usb" / "drivers" / "usbhid").mkdir(parents=True)
    (tmp_path / "usb" / "drivers" / "usbhid" / "bind").write_text("", encoding="utf-8")
    (tmp_path / "stamps").mkdir()
    return tmp_path / "usb"


def _roda(tmp_path: Path, *args: str, so_o_hid: bool = False) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    for chave in ("HEFESTO_USB_DEVICES_DIR", "HEFESTO_USB_DRIVERS_DIR"):
        env.pop(chave, None)
    env.update(
        HEFESTO_HID_DEVICES_DIR=str(tmp_path / "hid" / "devices"),
        HEFESTO_HID_DRIVERS_DIR=str(tmp_path / "hid" / "drivers"),
        HEFESTO_REBIND_STAMP_DIR=str(tmp_path / "stamps"),
        HEFESTO_BT_LOG_DEST="none",
    )
    if not so_o_hid:
        env.update(
            HEFESTO_USB_DEVICES_DIR=str(tmp_path / "usb" / "devices"),
            HEFESTO_USB_DRIVERS_DIR=str(tmp_path / "usb" / "drivers"),
        )
    return subprocess.run(
        ["bash", str(SCRIPT), *args], capture_output=True, text=True, check=False, env=env
    )


def _bind(tmp_path: Path) -> str:
    return (tmp_path / "usb" / "drivers" / "usbhid" / "bind").read_text(encoding="utf-8")


# --- o gesto -----------------------------------------------------------------


def test_religa_a_hid_do_controle_sony(tmp_path: Path) -> None:
    """A interface HID órfã de um DualSense vai para o ``bind`` do ``usbhid``."""
    usb = _bancada(tmp_path)
    _aparelho(usb, PORTA)
    _interface(usb, f"{PORTA}:1.0", classe="01", com_driver=True)
    _interface(usb, INTERFACE)
    r = _roda(tmp_path)
    assert r.returncode == 0, r.stderr
    assert _bind(tmp_path) == INTERFACE, "o religar escreve a INTERFACE, não o aparelho"
    # O /sys de mentira não tem kernel: a probe não acontece, e o script diz
    # que não pegou — nunca "RELIGADO" sobre uma HID que continua sem driver.
    assert "NÃO pegou (tentativa 1/3)" in r.stdout, r.stdout
    assert "RELIGADO" not in r.stdout


def test_dry_run_diz_o_que_faria_e_nao_escreve(tmp_path: Path) -> None:
    usb = _bancada(tmp_path)
    _aparelho(usb, PORTA)
    _interface(usb, INTERFACE)
    r = _roda(tmp_path, "--dry-run")
    assert f"faria: echo '{INTERFACE}' > " in r.stdout, r.stdout
    assert _bind(tmp_path) == ""


# --- o escopo ----------------------------------------------------------------


def test_a_interface_com_driver_nao_e_tocada(tmp_path: Path) -> None:
    usb = _bancada(tmp_path)
    _aparelho(usb, PORTA)
    _interface(usb, INTERFACE, com_driver=True)
    r = _roda(tmp_path)
    assert _bind(tmp_path) == ""
    assert "nenhum device HID órfão, nem no rádio nem no cabo" in r.stdout, r.stdout


def test_a_interface_de_audio_sem_driver_nao_e_tocada(tmp_path: Path) -> None:
    """O áudio do DualSense fica sem driver POR DESENHO (a regra 75): não é HID."""
    usb = _bancada(tmp_path)
    _aparelho(usb, PORTA)
    _interface(usb, f"{PORTA}:1.0", classe="01")
    _interface(usb, f"{PORTA}:1.1", classe="01")
    _roda(tmp_path)
    assert _bind(tmp_path) == ""


def test_interface_desligada_de_proposito_nao_e_tocada(tmp_path: Path) -> None:
    usb = _bancada(tmp_path)
    _aparelho(usb, PORTA)
    _interface(usb, INTERFACE, authorized="0")
    _roda(tmp_path)
    assert _bind(tmp_path) == ""


def test_orfa_que_nao_e_da_sony_e_ignorada(tmp_path: Path) -> None:
    """O teclado com a HID órfã não é nosso: conta, diz, e não toca."""
    usb = _bancada(tmp_path)
    _aparelho(usb, "3-4.1.2", vid="258a")
    _interface(usb, "3-4.1.2:1.0")
    r = _roda(tmp_path)
    assert _bind(tmp_path) == ""
    assert "FORA do escopo, ignorada: 3-4.1.2:1.0" in r.stdout, r.stdout


def test_o_vid_em_maiusculas_tambem_e_sony(tmp_path: Path) -> None:
    usb = _bancada(tmp_path)
    _aparelho(usb, PORTA, vid="054C")
    _interface(usb, INTERFACE)
    _roda(tmp_path)
    assert _bind(tmp_path) == INTERFACE


# --- o teto, e o orçamento que recomeça ----------------------------------------


def test_para_apos_o_teto_e_desiste_uma_vez_so(tmp_path: Path) -> None:
    usb = _bancada(tmp_path)
    _aparelho(usb, PORTA)
    _interface(usb, INTERFACE)
    saidas = [_roda(tmp_path, "--quiet").stdout for _ in range(5)]
    assert sum("NÃO pegou" in s for s in saidas) == 3, saidas
    assert sum("DESISTINDO do controle do cabo em 3-4.4" in s for s in saidas) == 1, saidas
    assert saidas[-1].strip() == "", "depois de desistir, silêncio"


def test_tirar_e_por_o_cabo_da_orcamento_novo(tmp_path: Path) -> None:
    """Outro ``devnum`` é outro encaixe: a desistência do anterior não vale para ele."""
    usb = _bancada(tmp_path)
    _aparelho(usb, PORTA, devnum="12")
    _interface(usb, INTERFACE)
    antes = [_roda(tmp_path, "--quiet").stdout for _ in range(4)]
    assert any("DESISTINDO" in s for s in antes), "o encaixe 12 tinha de esgotar"
    (usb / "devices" / PORTA / "devnum").write_text("15\n", encoding="utf-8")
    r = _roda(tmp_path, "--quiet")
    assert "NÃO pegou (tentativa 1/3)" in r.stdout, r.stdout
    assert (tmp_path / "stamps" / f"cabo-{INTERFACE}-15").read_text(encoding="utf-8") == "1"


def test_o_contador_do_encaixe_que_saiu_e_limpo(tmp_path: Path) -> None:
    """O ``/run`` não acumula contador de encaixe morto — nem apaga o do vivo."""
    usb = _bancada(tmp_path)
    _aparelho(usb, PORTA, devnum="12")
    _interface(usb, INTERFACE)
    _roda(tmp_path, "--quiet")
    vivo = tmp_path / "stamps" / f"cabo-{INTERFACE}-12"
    assert vivo.exists()
    _roda(tmp_path, "--quiet")
    assert vivo.exists(), "a limpeza apagou o contador de quem ainda está encaixado"
    (usb / "devices" / PORTA / "devnum").write_text("15\n", encoding="utf-8")
    _roda(tmp_path, "--quiet")
    assert not vivo.exists(), "o contador do encaixe anterior ficou para trás"


# --- a árvore desviada não lê a real --------------------------------------------


def test_a_arvore_de_25_07_nao_varre_o_cabo_de_quem_roda(tmp_path: Path) -> None:
    """Quem desvia só o HID (as réguas de 25/07) não ganha a varredura do cabo.

    Sem a guarda, o script leria o ``/sys/bus/usb`` da máquina que roda a
    suíte. **A mordida é pelo TEXTO, e está escrito aqui de propósito:** o
    ``/sys`` de quem roda não tem controle sem HID, então arrancar a guarda não
    muda nenhuma saída que uma régua possa ler — e uma régua que dependesse de
    haver um órfão na máquina dela mediria a máquina, não o produto. O que a
    parte de comportamento cobra é o outro lado: com só o HID desviado, a
    passada fecha limpa e o ``bind`` de mentira não é tocado.
    """
    usb = _bancada(tmp_path)
    _aparelho(usb, PORTA)
    _interface(usb, INTERFACE)
    env = dict(os.environ)
    env.pop("HEFESTO_USB_DEVICES_DIR", None)
    env.update(
        HEFESTO_HID_DEVICES_DIR=str(tmp_path / "hid" / "devices"),
        HEFESTO_HID_DRIVERS_DIR=str(tmp_path / "hid" / "drivers"),
        HEFESTO_REBIND_STAMP_DIR=str(tmp_path / "stamps"),
        HEFESTO_USB_DRIVERS_DIR=str(tmp_path / "usb" / "drivers"),
        HEFESTO_BT_LOG_DEST="none",
    )
    texto = SCRIPT.read_text(encoding="utf-8")
    assert 'elif [[ -n "${HEFESTO_HID_DEVICES_DIR:-}" ]]; then\n    USB_DEVICES=""' in texto
    r = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, check=False, env=env)
    assert r.returncode == 0, r.stderr
    assert _bind(tmp_path) == ""
    assert "nenhum device HID órfão" in r.stdout, r.stdout


# --- o caminho root que já existe ----------------------------------------------


def test_o_religar_anda_pelo_caminho_root_que_ja_existe() -> None:
    """O watchdog roda o script a cada tique; o install o instala; o uninstall o tira.

    É por isso que o religar do cabo não pede nada novo ao install: ele mora num
    script que já é instalado, já roda como root e já sai no uninstall.
    """
    watchdog = WATCHDOG.read_text(encoding="utf-8")
    assert '"${_s}" --quiet || true' in watchdog
    assert "bt_rebind_orphans.sh" in watchdog
    assert "bt_rebind_orphans.sh" in CAMADA.read_text(encoding="utf-8")
    assert "/usr/local/lib/hefesto-dualsense4unix/bt_rebind_orphans.sh" in (
        UNINSTALL.read_text(encoding="utf-8")
    )


# --- o tique sem rádio -----------------------------------------------------------


def _codigo_do_watchdog() -> list[str]:
    """As linhas de CÓDIGO do watchdog, do fonte — comentário vira linha vazia."""
    return [
        "" if linha.lstrip().startswith("#") else linha
        for linha in WATCHDOG.read_text(encoding="utf-8").splitlines()
    ]


def _as_guardas_do_radio() -> list[str]:
    """As duas guardas do Bluetooth do watchdog, copiadas do FONTE a cada corrida."""
    guardas = [
        linha
        for linha in _codigo_do_watchdog()
        if linha.startswith(("command -v busctl ", "systemctl is-active --quiet bluetooth.service"))
    ]
    assert len(guardas) == 2, f"as duas guardas do rádio mudaram de forma: {guardas}"
    return guardas


@pytest.mark.parametrize("falta", ["o busctl", "o bluetooth.service"])
def test_sem_radio_o_tique_ainda_religa_o_cabo(tmp_path: Path, falta: str) -> None:
    """Numa máquina sem Bluetooth, o tique ainda chama a vigia que religa o cabo.

    Achado da conferência (24/09): as duas guardas do watchdog (``busctl``
    ausente, ``bluetooth.service`` inativo — o estado de todo computador sem
    adaptador) saíam com ``exit 0`` ANTES da vigia 4. O ramo do cabo morava num
    script que, nessa máquina, nunca rodava — a cura só valia para quem tem
    rádio, e a matriz dela diz que nenhuma decisão é só de um transporte.

    Roda as guardas DO FONTE, com a vigia trocada por um eco: o tique de
    verdade chamaria o ``bt_active_mode.sh`` instalado e falaria com o rádio
    dela, e isso nenhuma régua faz.
    """
    roteiro = textwrap.dedent(
        """
        set -euo pipefail
        log() { :; }
        vigia_rebind_orfaos() { echo CHAMOU-A-VIGIA; }
        """
    )
    if falta == "o bluetooth.service":
        roteiro += "busctl() { :; }\nsystemctl() { return 3; }\n"
    roteiro += "\n".join(_as_guardas_do_radio()) + "\necho PASSOU-DAS-GUARDAS\n"
    bash = shutil.which("bash") or "/bin/bash"
    r = subprocess.run(
        [bash, "-c", roteiro],
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": str(tmp_path)},  # vazio: sem busctl, sem systemctl de verdade
    )
    assert r.returncode == 0, r.stderr
    assert "PASSOU-DAS-GUARDAS" not in r.stdout, "controle: a guarda tinha de fechar o tique"
    assert "CHAMOU-A-VIGIA" in r.stdout, (
        f"sem {falta}, o tique sai sem religar o controle do cabo:\n{r.stdout}"
    )


def test_com_radio_as_guardas_deixam_o_tique_seguir(tmp_path: Path) -> None:
    """O controle do lado de lá: com o rádio de pé, as guardas não chamam nada."""
    roteiro = textwrap.dedent(
        """
        set -euo pipefail
        log() { :; }
        vigia_rebind_orfaos() { echo CHAMOU-A-VIGIA; }
        busctl() { :; }
        systemctl() { return 0; }
        """
    ) + "\n".join(_as_guardas_do_radio()) + "\necho PASSOU-DAS-GUARDAS\n"
    r = subprocess.run(
        [shutil.which("bash") or "/bin/bash", "-c", roteiro],
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": str(tmp_path)},
    )
    assert "PASSOU-DAS-GUARDAS" in r.stdout, r.stdout + r.stderr
    assert "CHAMOU-A-VIGIA" not in r.stdout, r.stdout


def test_a_vigia_existe_antes_das_guardas_e_roda_depois_delas() -> None:
    """A função nasce ANTES das guardas (senão a guarda chamaria um nome que não
    existe), e a chamada de sempre continua depois delas, para a máquina com rádio."""
    codigo = _codigo_do_watchdog()
    definicao = codigo.index("vigia_rebind_orfaos() {")
    guardas = [i for i, linha in enumerate(codigo) if linha in _as_guardas_do_radio()]
    assert definicao < min(guardas), "a vigia 4 é definida depois das guardas que a chamam"
    chamadas = [i for i, linha in enumerate(codigo) if linha.strip() == "vigia_rebind_orfaos"]
    assert chamadas and min(chamadas) > max(guardas), (
        "o tique da máquina com rádio perdeu a chamada da vigia 4"
    )

