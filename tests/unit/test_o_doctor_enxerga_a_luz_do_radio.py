"""LUZ-CEGA-01 — o check de LED que se declarava cego em toda mesa de rádio.

`check_led_sysfs_gravavel` (scripts/doctor.sh) precisa separar o DualSense de
verdade do vpad uhid que o próprio daemon cria. Ele separava pelo CAMINHO:

    [[ "${dev_real}" == */devices/virtual/* ]] && continue   # vpad do daemon

O caminho não distingue nada. O BlueZ moderno entrega HID por `uhid`, que é um
`misc` **virtual** — então um DualSense de Bluetooth mora em

    /sys/devices/virtual/misc/uhid/0005:054C:0CE6.0028/leds/inputN:rgb:indicator

byte a byte na mesma forma do vpad, que mora em

    /sys/devices/virtual/misc/uhid/0003:054C:0DF2.002F/leds/inputM:rgb:indicator

MEDIDO em 22/08/2026 nesta bancada, com QUATRO DualSense no rádio e os quatro
`multi_intensity` graváveis: o doctor imprimia *"sem DualSense físico com nó de
LED agora (só o controle virtual, ou nenhum)"*. Zero de quatro.

O custo do silêncio é o pior que este check pode pagar: ela abre o doctor
exatamente quando a cor não está saindo, e a cor falha JUSTAMENTE no rádio. Só
quem usa cabo chegava a ver este check dizer alguma coisa — e o teste que já
existia (`test_doctor_nao_afirma_efeito.py`) montava a cena com o device sob
`pci0000:00`, ou seja, exercitava só o cabo. O ponto cego estava nos dois lados.

O critério certo é a IDENTIDADE: o vpad anuncia `HID_PHYS=hefesto-vpad`, a
mesma marca que `broker/hidraw_broker.py`, `integrations/cor_do_plastico.py` e
`integrations/uhid_gamepad.py` já usam para reconhecê-lo. Controle de verdade
nunca tem esse `phys`, esteja no cabo ou no rádio.

A MORDIDA: devolvendo a linha do `*/devices/virtual/*` ao corpo do check, o
primeiro teste reprova (o controle de rádio some do relatório) e o terceiro
reprova junto (o `pass` deixa de nomear o nó do rádio). Trocando o filtro por
"nunca filtra nada", o segundo reprova (o vpad passa a ser contado como
controle). Os dois erros opostos ficam travados.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

BASH = shutil.which("bash") or "/bin/bash"
REPO_ROOT = Path(__file__).resolve().parents[2]
DOCTOR_PATH = REPO_ROOT / "scripts" / "doctor.sh"
DOCTOR = DOCTOR_PATH.read_text(encoding="utf-8")

NOME_DO_CHECK = "check_led_sysfs_gravavel"

#: A marca de identidade do vpad — a mesma string dos outros quatro lugares
#: que já o reconhecem. Se ela mudar no produto, tem de mudar aqui junto.
PHYS_DO_VPAD = "hefesto-vpad"


def _extrai_funcao_bash(fonte: str, nome: str) -> str:
    match = re.search(rf"^{re.escape(nome)}\(\) \{{\n", fonte, re.MULTILINE)
    assert match is not None, f"função {nome}() não encontrada"
    fim = re.search(r"^\}$", fonte[match.end() :], re.MULTILINE)
    assert fim is not None, f"fim de {nome}() não encontrado"
    return fonte[match.start() : match.end() + fim.end() + 1]


def _no_de_led(
    raiz: Path,
    *,
    nome_do_no: str,
    instancia: str,
    phys: str,
    virtual: bool,
    gravavel: bool = True,
) -> Path:
    """Monta um nó `:rgb:indicator` de mentira com a topologia REAL do sysfs.

    `virtual=True` reproduz a forma do Bluetooth (BlueZ→uhid) e a do vpad — as
    duas são `/devices/virtual/misc/uhid/<instância>/leds/<nó>`, e é essa
    coincidência que derrubou o filtro por caminho. `virtual=False` reproduz o
    cabo (`/devices/pci.../usb.../<instância>`). O que separa os dois casos
    virtuais é só o `HID_PHYS` do `uevent`.
    """
    if virtual:
        device = raiz / "devices" / "virtual" / "misc" / "uhid" / instancia
    else:
        device = raiz / "devices" / "pci0000:00" / "usb1" / "1-1" / instancia
    device.mkdir(parents=True)
    (device / "uevent").write_text(
        f"DRIVER=playstation\nHID_ID=0005:0000054C:00000CE6\nHID_PHYS={phys}\n",
        encoding="utf-8",
    )
    no = device / "leds" / nome_do_no
    no.mkdir(parents=True)
    intensidade = no / "multi_intensity"
    intensidade.write_text("0 0 153\n", encoding="utf-8")
    intensidade.chmod(0o644 if gravavel else 0o444)

    classe = raiz / "class" / "leds"
    classe.mkdir(parents=True, exist_ok=True)
    (classe / nome_do_no).symlink_to(no)
    (no / "device").symlink_to(device)
    return classe / nome_do_no


def _roda_o_check(raiz: Path, corpo_extra: str = "") -> str:
    """Executa só o check, contra o `/sys/class/leds` de mentira em `raiz`."""
    corpo = _extrai_funcao_bash(DOCTOR, NOME_DO_CHECK).replace(
        "/sys/class/leds", str(raiz / "class" / "leds")
    )
    if corpo_extra:
        corpo = corpo_extra
    cena = raiz / "cena.sh"
    cena.write_text(
        "set -u\n"
        'pass() { printf "PASS %s\\n" "$*"; }\n'
        'warn() { printf "WARN %s\\n" "$*"; }\n'
        'info() { printf "INFO %s\\n" "$*"; }\n'
        f"{corpo}\n"
        f"{NOME_DO_CHECK}\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [BASH, str(cena)], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def test_o_controle_do_radio_nao_e_confundido_com_o_vpad(tmp_path: Path) -> None:
    """A cena da bancada de 22/08: um DualSense no rádio + o vpad do daemon."""
    _no_de_led(
        tmp_path,
        nome_do_no="input259:rgb:indicator",
        instancia="0005:054C:0CE6.0028",
        phys="00:00:00:00:00:00",  # o `phys` de um controle BT é o MAC do host
        virtual=True,
    )
    _no_de_led(
        tmp_path,
        nome_do_no="input289:rgb:indicator",
        instancia="0003:054C:0DF2.002F",
        phys=PHYS_DO_VPAD,
        virtual=True,
    )

    saida = _roda_o_check(tmp_path)

    assert "input259:rgb:indicator" in saida, (
        "o DualSense do RÁDIO sumiu do relatório. Ele mora em "
        "/devices/virtual/misc/uhid (BlueZ entrega HID por uhid) — filtrar o "
        "vpad pelo CAMINHO leva junto todo controle sem fio, que é a mesa da "
        f"maioria. Saiu:\n  {saida.strip()}"
    )
    assert saida.startswith("PASS "), (
        f"nó gravável de controle real tinha de dar `pass`; saiu:\n  {saida.strip()}"
    )


def test_o_vpad_do_daemon_continua_fora_da_conta(tmp_path: Path) -> None:
    """O outro erro: contar o próprio vpad como se fosse controle da usuária."""
    _no_de_led(
        tmp_path,
        nome_do_no="input289:rgb:indicator",
        instancia="0003:054C:0DF2.002F",
        phys=PHYS_DO_VPAD,
        virtual=True,
    )

    saida = _roda_o_check(tmp_path)

    assert "input289:rgb:indicator" not in saida, (
        "o vpad uhid do PRÓPRIO daemon entrou na conta como controle da "
        f"usuária — ele anuncia HID_PHYS={PHYS_DO_VPAD}. Saiu:\n  {saida.strip()}"
    )
    assert saida.startswith("INFO "), (
        "só o vpad na mesa = nenhum controle de verdade: a saída tem de ser o "
        f"`info` que pula o teste, não um veredito. Saiu:\n  {saida.strip()}"
    )


def test_cabo_e_radio_sao_relatados_juntos(tmp_path: Path) -> None:
    """Cabo e rádio na mesma mesa: os dois aparecem, o vpad não."""
    _no_de_led(
        tmp_path,
        nome_do_no="input100:rgb:indicator",
        instancia="0003:054C:0CE6.0001",
        phys="usb-0000:00:14.0-1/input0",
        virtual=False,
    )
    _no_de_led(
        tmp_path,
        nome_do_no="input259:rgb:indicator",
        instancia="0005:054C:0CE6.0028",
        phys="00:00:00:00:00:00",
        virtual=True,
    )
    _no_de_led(
        tmp_path,
        nome_do_no="input289:rgb:indicator",
        instancia="0003:054C:0DF2.002F",
        phys=PHYS_DO_VPAD,
        virtual=True,
    )

    saida = _roda_o_check(tmp_path)

    assert "input100:rgb:indicator" in saida, f"o controle do CABO sumiu:\n  {saida}"
    assert "input259:rgb:indicator" in saida, f"o controle do RÁDIO sumiu:\n  {saida}"
    assert "input289:rgb:indicator" not in saida, f"o vpad entrou na conta:\n  {saida}"


def test_o_no_sem_permissao_no_radio_vira_warn(tmp_path: Path) -> None:
    """A regra 77 não pegou no controle do rádio: tem de sair `warn`, não `info`.

    É a metade do defeito que mais custa: sem esta linha o doctor respondia
    `info` ("não tem controle") para a mesa em que a regra udev falhou, e o
    comando que a conserta nunca era mostrado.
    """
    _no_de_led(
        tmp_path,
        nome_do_no="input259:rgb:indicator",
        instancia="0005:054C:0CE6.0028",
        phys="00:00:00:00:00:00",
        virtual=True,
        gravavel=False,
    )

    saida = _roda_o_check(tmp_path)

    assert saida.startswith("WARN "), (
        "controle do rádio SEM permissão de escrita tem de virar `warn` com o "
        f"comando da regra 77; saiu:\n  {saida.strip()}"
    )
    assert "install_udev.sh" in saida, (
        f"o `warn` precisa dizer como consertar; saiu:\n  {saida.strip()}"
    )


def test_bash_n_do_doctor() -> None:
    """Sanidade: a edição não pode ter quebrado a sintaxe do script."""
    proc = subprocess.run(
        [BASH, "-n", str(DOCTOR_PATH)], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, proc.stderr
