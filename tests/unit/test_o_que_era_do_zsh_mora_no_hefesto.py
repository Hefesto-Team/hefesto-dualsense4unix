"""O que faz o Hefesto funcionar mora no Hefesto — O-QUE-E-DO-HEFESTO-SAI-DO-ZSH-01.

Ordem dela, 23/09/2026: *"tudo que diz respeito ao funcionamento do hefesto
tem que ser tirado do meu repo pessoal. desativado no zsh e fazer parte do
hefesto como um todo dentro do install e tudo mais."* O estudo da sprint achou
DUAS peças da classe A (é do Hefesto e o Hefesto não tinha):

1. **o Wi-Fi USB inteiro** — o `scripts/wifi_usb.sh` (o `aurora-wifi-usb.sh` de
   23/09, sem nome da máquina dela), o dispatcher `90-hefesto-wifi-usb` e o
   vigia `hefesto-wifi-usb-vigia.{service,timer}`;
2. **a pergunta do rfkill** — o rádio Bluetooth desligado por software, que
   parece «sem adaptador» e passa a ser resposta do `scripts/doctor.sh`.

Toda peça A tem o par — o install faz, o uninstall desfaz, a paridade confere e
o doctor sabe dizer se está de pé — e este arquivo cobra os quatro. O
`wifi_usb.sh` passa pelos mesmos oito cenários a seco que o `aurora-` passou em
23/09 (o roteador de verdade, o roteador morto contando até 3, os dois freios,
a volta que zera, o dispatcher com a interface vazia, o `up` e o `usage`),
agora contra sysfs e comandos de MENTIRA: a suíte roda como usuário comum e
nunca fala com o rádio de quem a roda.

E os dois pedidos que a onda 3a deixou para a dona de `assets/systemd/`: o
watchdog do Bluetooth enxerga o `maquina.json` (e só ele), e o `ExecStartPost`
do bluetoothd sai do sandbox para o nome do lugar chegar no start.

Nenhuma fixture aqui carrega endereço de rádio: a interface de mentira se chama
`wlan-usb0` e o roteador é o 192.0.2.1 da faixa de documentação.
"""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
WIFI = RAIZ / "scripts" / "wifi_usb.sh"
DOCTOR = RAIZ / "scripts" / "doctor.sh"
INSTALL = RAIZ / "install.sh"
UNINSTALL = RAIZ / "uninstall.sh"
LIB = RAIZ / "scripts" / "lib" / "camada_de_maquina.sh"
PARIDADE = RAIZ / "scripts" / "check_packaging_parity.sh"
SYSTEMD = RAIZ / "assets" / "systemd"
DROPIN_BT = SYSTEMD / "bluetooth-dropin-10-hefesto-resilience.conf"
WATCHDOG = SYSTEMD / "hefesto-bt-health-watchdog.service"
MODO_ATIVO = RAIZ / "scripts" / "bt_active_mode.sh"

IFC = "wlan-usb0"
GW = "192.0.2.1"
PORTA = "3-4.1.2"


# ---------------------------------------------------------------------------
# A mesa de mentira do Wi-Fi USB
# ---------------------------------------------------------------------------

#: Os dublês. Cada um é tão estrito quanto o comando real no que o script usa:
#: o `wpa_cli` de verdade responde `FAIL` para campo não definido e `OK` só
#: quando grava; o `ping` sai 1 quando ninguém responde; o `ip neigh` devolve
#: vazio quando não há vizinho.
_DUBLES = {
    "wpa_cli": r"""#!/bin/sh
# wpa_cli -i IFC <cmd> [args]
shift 2
case "$1" in
  status)
    if [ -e "$FAKE/associado" ]; then printf 'wpa_state=COMPLETED\nid=0\n'
    else printf 'wpa_state=DISCONNECTED\n'; fi ;;
  get_network)
    if [ -e "$FAKE/bgscan" ]; then cat "$FAKE/bgscan"; else echo FAIL; fi ;;
  set_network)
    echo "set_network $2 $3 $4" >> "$FAKE/chamadas"
    printf '%s\n' "$4" > "$FAKE/bgscan"
    echo OK ;;
  *) echo FAIL ;;
esac
""",
    "ping": '#!/bin/sh\necho "ping $*" >> "$FAKE/chamadas"\n[ -e "$FAKE/roteador_vivo" ]\n',
    "ip": r"""#!/bin/sh
case "$*" in
  *neigh*) [ -e "$FAKE/vizinho" ] && cat "$FAKE/vizinho" ;;
  *route*) echo "default via 192.0.2.1 dev wlan-usb0 proto dhcp" ;;
esac
exit 0
""",
    "python3": '#!/bin/sh\necho "reset $2" >> "$FAKE/reset"\nexit 0\n',
    "logger": '#!/bin/sh\necho "[$2] $(cat)" >> "$FAKE/logger"\n',
    "journalctl": '#!/bin/sh\n[ -e "$FAKE/journal" ] && cat "$FAKE/journal"\nexit 0\n',
    "id": '#!/bin/sh\ncat "$FAKE/uid" 2>/dev/null || echo 1000\n',
}


def _mesa(
    tmp_path: Path, *, com_dongle: bool = True, bt_no_mesmo_hub: bool = False
) -> dict[str, str]:
    """Monta o sysfs, o /dev, o estado e os dublês; devolve o ambiente."""
    sysfs = tmp_path / "sys"
    (sysfs / "bus" / "usb" / "devices").mkdir(parents=True)
    (sysfs / "class" / "net").mkdir(parents=True)
    (sysfs / "class" / "bluetooth").mkdir(parents=True)
    hub = sysfs / "devices" / "pci0000:00" / "0000:00:08.1" / "usb3" / "3-4" / "3-4.1"
    # Uma placa com fio, que o script tem de ignorar.
    (sysfs / "class" / "net" / "enp0").mkdir()
    if com_dongle:
        porta = hub / PORTA
        interface = porta / f"{PORTA}:1.0"
        interface.mkdir(parents=True)
        for nome, valor in (
            ("busnum", "3"),
            ("devnum", "7"),
            ("speed", "5000"),
            ("authorized", "1"),
        ):
            (porta / nome).write_text(valor + "\n", encoding="utf-8")
        (interface / "subsystem").symlink_to(sysfs / "bus" / "usb")
        (sysfs / "bus" / "usb" / "devices" / PORTA).symlink_to(porta)
        ifc = sysfs / "class" / "net" / IFC
        (ifc / "wireless").mkdir(parents=True)
        (ifc / "device").symlink_to(interface)
    if bt_no_mesmo_hub:
        bt = hub / "3-4.1.4" / "3-4.1.4:1.0"
        bt.mkdir(parents=True)
        (sysfs / "class" / "bluetooth" / "hci1").mkdir()
        (sysfs / "class" / "bluetooth" / "hci1" / "device").symlink_to(bt)
    dev = tmp_path / "dev"
    dev.mkdir()
    fake = tmp_path / "fake"
    fake.mkdir()
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for nome, corpo in _DUBLES.items():
        alvo = bindir / nome
        alvo.write_text(corpo, encoding="utf-8")
        alvo.chmod(0o755)
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(tmp_path),
        "LC_ALL": "C.UTF-8",
        "FAKE": str(fake),
        "HEFESTO_WIFI_BIN": str(bindir),
        "HEFESTO_WIFI_SYSFS": str(sysfs),
        "HEFESTO_WIFI_DEV": str(dev),
        "HEFESTO_WIFI_ESTADO": str(tmp_path / "estado"),
        "HEFESTO_WIFI_GW_TESTE": GW,
    }


def _wifi(
    amb: dict[str, str], *args: str, extra: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = dict(amb)
    env.update(extra or {})
    return subprocess.run(
        ["bash", str(WIFI), *args], capture_output=True, text=True, timeout=30, check=False, env=env
    )


def _fake(amb: dict[str, str]) -> Path:
    return Path(amb["FAKE"])


def _estado(amb: dict[str, str], nome: str) -> str:
    arq = Path(amb["HEFESTO_WIFI_ESTADO"]) / f"{IFC}.{nome}"
    return arq.read_text(encoding="utf-8").strip() if arq.exists() else ""


def _associar(amb: dict[str, str], *, bgscan: str = '""', roteador: bool = True) -> None:
    fake = _fake(amb)
    (fake / "associado").touch()
    (fake / "bgscan").write_text(bgscan + "\n", encoding="utf-8")
    if roteador:
        (fake / "roteador_vivo").touch()
    else:
        (fake / "roteador_vivo").unlink(missing_ok=True)
        (fake / "vizinho").write_text(f"{GW} dev {IFC}  FAILED\n", encoding="utf-8")


# --- os oito cenários de 23/09 ----------------------------------------------


def test_cenario_1_o_roteador_de_verdade_nao_conta_falha(tmp_path: Path) -> None:
    amb = _mesa(tmp_path)
    _associar(amb)
    r = _wifi(amb, "--vigiar")
    assert r.returncode == 0, r.stderr
    assert r.stdout == ""
    assert _estado(amb, "falhas") == "0"
    assert not (_fake(amb) / "reset").exists()


def test_cenario_2_o_roteador_morto_conta_ate_tres_e_reinicia_a_porta(tmp_path: Path) -> None:
    amb = _mesa(tmp_path)
    _associar(amb, roteador=False)
    for n in (1, 2):
        r = _wifi(amb, "--vigiar")
        assert f"{IFC}: associado e o roteador {GW} sem responder — {n} de 3" in r.stdout
        assert not (_fake(amb) / "reset").exists()
    r = _wifi(amb, "--vigiar")
    assert "3 de 3" in r.stdout
    assert f"porta {PORTA} reiniciada (reset USB)" in r.stdout
    # O reset mira o nó do aparelho certo, montado do busnum/devnum do sysfs.
    reset = (_fake(amb) / "reset").read_text(encoding="utf-8")
    assert f"{amb['HEFESTO_WIFI_DEV']}/bus/usb/003/007" in reset
    assert _estado(amb, "reinicios") == "1"
    assert _estado(amb, "falhas") == "0"


def test_cenario_2_seco_diz_e_nao_reinicia(tmp_path: Path) -> None:
    amb = _mesa(tmp_path)
    _associar(amb, roteador=False)
    for _ in range(3):
        r = _wifi(amb, "--vigiar", "--seco")
    assert "reiniciaria a porta do dongle agora (--seco, nada feito)" in r.stdout
    assert not (_fake(amb) / "reset").exists()


def test_cenario_3_o_freio_dos_dez_minutos(tmp_path: Path) -> None:
    amb = _mesa(tmp_path)
    _associar(amb, roteador=False)
    estado = Path(amb["HEFESTO_WIFI_ESTADO"])
    estado.mkdir()
    (estado / f"{IFC}.falhas").write_text("2\n", encoding="utf-8")
    (estado / f"{IFC}.reinicios").write_text("1\n", encoding="utf-8")
    (estado / f"{IFC}.reiniciou_em").write_text(f"{int(time.time()) - 60}\n", encoding="utf-8")
    r = _wifi(amb, "--vigiar")
    assert "espero dar 600 s" in r.stdout
    assert not (_fake(amb) / "reset").exists()


def test_cenario_4_o_freio_dos_tres_reinicios_sem_cura(tmp_path: Path) -> None:
    amb = _mesa(tmp_path)
    _associar(amb, roteador=False)
    estado = Path(amb["HEFESTO_WIFI_ESTADO"])
    estado.mkdir()
    (estado / f"{IFC}.falhas").write_text("2\n", encoding="utf-8")
    (estado / f"{IFC}.reinicios").write_text("3\n", encoding="utf-8")
    r = _wifi(amb, "--vigiar")
    assert "3 reinícios seguidos sem cura — parei. Tire e ponha o dongle." in r.stdout
    assert not (_fake(amb) / "reset").exists()


def test_cenario_5_a_volta_zera_a_contagem(tmp_path: Path) -> None:
    amb = _mesa(tmp_path)
    _associar(amb)
    estado = Path(amb["HEFESTO_WIFI_ESTADO"])
    estado.mkdir()
    (estado / f"{IFC}.falhas").write_text("2\n", encoding="utf-8")
    (estado / f"{IFC}.reinicios").write_text("2\n", encoding="utf-8")
    r = _wifi(amb, "--vigiar")
    assert f"{IFC}: o roteador voltou a responder" in r.stdout
    assert f"{IFC}: curado depois de 2 reinício(s)" in r.stdout
    assert _estado(amb, "falhas") == "0"
    assert _estado(amb, "reinicios") == "0"


def test_o_roteador_que_nao_responde_ping_mas_responde_arp_nao_e_travamento(tmp_path: Path) -> None:
    amb = _mesa(tmp_path)
    _associar(amb, roteador=False)
    (_fake(amb) / "vizinho").write_text(
        f"{GW} dev {IFC} lladdr aa:bb:cc:00:00:01 REACHABLE\n", encoding="utf-8"
    )
    r = _wifi(amb, "--vigiar")
    assert "sem responder" not in r.stdout
    assert _estado(amb, "falhas") == "0"


def test_cenario_6_o_dispatcher_com_a_interface_vazia_sai_limpo(tmp_path: Path) -> None:
    """No `connectivity-change` o NetworkManager manda a interface VAZIA.

    A primeira versão do zsh caía no `usage` e saía com 2 — o NetworkManager
    registrou "failed" duas vezes na madrugada de 23/09.
    """
    amb = _mesa(tmp_path)
    for acao, iface in (("connectivity-change", ""), ("up", ""), ("down", IFC)):
        r = _wifi(amb, extra={"NM_DISPATCHER_ACTION": acao, "DEVICE_IFACE": iface})
        assert r.returncode == 0, (acao, r.stdout, r.stderr)
        assert r.stdout == ""
    assert not (_fake(amb) / "logger").exists()


def test_cenario_7_o_up_desliga_o_scan_de_fundo_e_diz_no_journal(tmp_path: Path) -> None:
    amb = _mesa(tmp_path)
    _associar(amb, bgscan='"simple:30:-65:300"')
    r = _wifi(amb, IFC, "up", extra={"NM_DISPATCHER_ACTION": "up", "DEVICE_IFACE": IFC})
    assert r.returncode == 0, r.stderr
    log = (_fake(amb) / "logger").read_text(encoding="utf-8")
    assert "[hefesto-wifi-usb]" in log
    assert 'scan de fundo DESLIGADO (era "simple:30:-65:300")' in log
    assert 'set_network 0 bgscan ""' in (_fake(amb) / "chamadas").read_text(encoding="utf-8")


def test_cenario_7_o_up_de_placa_que_nao_e_usb_nao_mexe(tmp_path: Path) -> None:
    amb = _mesa(tmp_path)
    _associar(amb, bgscan='"simple:30:-65:300"')
    r = _wifi(amb, extra={"NM_DISPATCHER_ACTION": "up", "DEVICE_IFACE": "enp0"})
    assert r.returncode == 0
    assert not (_fake(amb) / "logger").exists()
    assert not (_fake(amb) / "chamadas").exists(), (
        "o dispatcher mexeu no wpa_supplicant por uma placa com fio"
    )


def test_cenario_8_o_usage(tmp_path: Path) -> None:
    amb = _mesa(tmp_path)
    r = _wifi(amb)
    assert r.returncode == 2
    assert "uso: wifi_usb.sh --ensure" in r.stdout
    r = _wifi(amb, "--help")
    assert r.returncode == 0
    assert "--vigiar" in r.stdout


# --- o que o vigia herdou do self-heal, e o que o --status diz ---------------


def test_o_vigia_faz_o_reforco_do_dispatcher_e_cala_quando_nao_ha_o_que_fazer(
    tmp_path: Path,
) -> None:
    """O `--ensure` horário do self-heal pegava a associação que o dispatcher
    perdeu. Tirar o self-heal sem dar esse papel a alguém abriria a janela sem
    dono que a sprint proíbe — o vigia passou a fazer, calado no caso comum."""
    amb = _mesa(tmp_path)
    _associar(amb, bgscan='"simple:30:-65:300"')
    r = _wifi(amb, "--vigiar")
    assert 'scan de fundo DESLIGADO (era "simple:30:-65:300")' in r.stdout
    r = _wifi(amb, "--vigiar")
    assert r.stdout == "", "com o scan já desligado, o tique de minuto em minuto não escreve nada"


def test_o_ensure_a_mao_diz_tudo(tmp_path: Path) -> None:
    amb = _mesa(tmp_path)
    _associar(amb)
    r = _wifi(amb, "--ensure")
    assert r.returncode == 0
    assert f"{IFC}: scan de fundo já desligado" in r.stdout


def test_o_status_sem_root_diz_que_nao_tem_permissao_em_vez_de_interrogacao(tmp_path: Path) -> None:
    amb = _mesa(tmp_path)
    _associar(amb)
    r = _wifi(amb, "--status")
    assert "scan de fundo sem permissão para ler (só root)" in r.stdout
    assert "scan de fundo ?" not in r.stdout
    assert f"{IFC} · porta {PORTA} · USB3 (5000M)" in r.stdout


def test_o_status_como_root_le_o_scan_e_acusa_o_hub_do_bluetooth(tmp_path: Path) -> None:
    amb = _mesa(tmp_path, bt_no_mesmo_hub=True)
    _associar(amb)
    (_fake(amb) / "uid").write_text("0\n", encoding="utf-8")
    (_fake(amb) / "journal").write_text(
        "set 23 03:00:00 k: rtw88_8822bu 3-4.1.2:1.0: device gone, stopping register I/O\n",
        encoding="utf-8",
    )
    r = _wifi(amb, "--status")
    assert "scan de fundo desligado" in r.stdout
    assert "1 quedas do rtw88 neste boot" in r.stdout
    assert "AVISO: mesmo hub que o Bluetooth ( hci1 )" in r.stdout


def test_sem_wifi_usb_nada_acontece_e_o_status_diz(tmp_path: Path) -> None:
    amb = _mesa(tmp_path, com_dongle=False)
    assert _wifi(amb, "--lista").stdout == ""
    assert _wifi(amb, "--vigiar").stdout == ""
    assert _wifi(amb, "--ensure").returncode == 0
    assert (
        "nenhum Wi-Fi USB agora — o vigia fica armado e não faz nada"
        in _wifi(amb, "--status").stdout
    )


def test_a_lista_so_traz_wifi_no_barramento_usb(tmp_path: Path) -> None:
    amb = _mesa(tmp_path)
    assert _wifi(amb, "--lista").stdout.split() == [IFC]


def test_gancho_de_comando_sem_sysfs_de_mentira_e_recusado(tmp_path: Path) -> None:
    """A trava: dublê de `wpa_cli` com o sysfs de verdade leria o dongle de quem
    roda a suíte — e o `--vigiar` reiniciaria a porta dele."""
    amb = _mesa(tmp_path)
    for tira in ("HEFESTO_WIFI_SYSFS", "HEFESTO_WIFI_DEV"):
        env = {k: v for k, v in amb.items() if k != tira}
        r = subprocess.run(
            ["bash", str(WIFI), "--vigiar"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env=env,
        )
        assert r.returncode == 97, (tira, r.stdout, r.stderr)
        assert "recuso" in r.stderr


def test_o_script_nao_carrega_o_nome_da_maquina_dela() -> None:
    texto = WIFI.read_text(encoding="utf-8")
    for proibido in ("aurora", "AURORA_", "/run/aurora", "wlx"):
        assert proibido not in texto.replace("aurora-wifi-usb.sh`", ""), proibido
    assert "switch_usb_mode=N" in texto, "a recusa do modo USB2 fica escrita"
    assert not re.search(r"^\s*[^#].*switch_usb_mode", texto, re.M), (
        "o modo USB2 não entra (recusado por ela)"
    )


# ---------------------------------------------------------------------------
# A2 — o rfkill vira pergunta do doctor
# ---------------------------------------------------------------------------


def _bt_sysfs(tmp_path: Path, estados: dict[str, tuple[str, str]]) -> Path:
    raiz = tmp_path / "bt"
    raiz.mkdir()
    for n, (hci, (soft, hard)) in enumerate(estados.items()):
        rf = raiz / hci / f"rfkill{80 + n}"
        rf.mkdir(parents=True)
        (rf / "soft").write_text(soft + "\n", encoding="utf-8")
        (rf / "hard").write_text(hard + "\n", encoding="utf-8")
        (rf / "type").write_text("bluetooth\n", encoding="utf-8")
    return raiz


def _doctor_rfkill(tmp_path: Path, raiz: Path) -> str:
    bindir = tmp_path / "bin-doctor"
    bindir.mkdir(exist_ok=True)
    marca = tmp_path / "rfkill-chamado"
    # O doctor nunca roda `rfkill`, nem o `busctl`/`hciconfig` do fallback:
    # dublês que só deixam rastro.
    for nome in ("rfkill", "busctl", "hciconfig"):
        alvo = bindir / nome
        alvo.write_text(f'#!/bin/sh\necho {nome} >> "{marca}"\n', encoding="utf-8")
        alvo.chmod(0o755)
    r = subprocess.run(
        ["bash", "-c", f'source "{DOCTOR}"; check_bt_rfkill'],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={
            "PATH": f"{bindir}:/usr/bin:/bin",
            "HOME": str(tmp_path),
            "HEFESTO_BT_SYSFS_ROOT": str(raiz),
        },
    )
    assert "rfkill" not in (marca.read_text(encoding="utf-8") if marca.exists() else ""), (
        "o doctor RODOU o rfkill — ele só lê arquivo, e nunca desbloqueia"
    )
    return r.stdout + r.stderr


def test_o_doctor_acusa_o_adaptador_soft_blocked_pelo_nome_mesmo_sendo_o_segundo(
    tmp_path: Path,
) -> None:
    """O zsh olhava só o primeiro adaptador (`head -1`) no nome que imprimia."""
    raiz = _bt_sysfs(tmp_path, {"hci0": ("0", "0"), "hci1": ("1", "0")})
    saida = _doctor_rfkill(tmp_path, raiz)
    assert "[WARN] hci1 desligado por software (rfkill soft)" in saida
    assert "rfkill unblock bluetooth" in saida
    assert "hci0" not in saida.split("[WARN]", 1)[1].split("\n", 1)[0]


def test_o_doctor_acusa_o_bloqueio_da_chave_fisica(tmp_path: Path) -> None:
    raiz = _bt_sysfs(tmp_path, {"hci0": ("0", "1")})
    assert "[WARN] hci0 bloqueado pela chave física ou pela BIOS (rfkill hard)" in _doctor_rfkill(
        tmp_path, raiz
    )


def test_o_doctor_passa_com_o_radio_ligado(tmp_path: Path) -> None:
    raiz = _bt_sysfs(tmp_path, {"hci0": ("0", "0"), "hci1": ("0", "0")})
    saida = _doctor_rfkill(tmp_path, raiz)
    assert "[ OK ] rádio Bluetooth ligado em 2 adaptador(es)" in saida
    assert "[WARN]" not in saida


def test_o_doctor_nao_conta_como_ligado_o_adaptador_que_nao_leu(tmp_path: Path) -> None:
    """Dois adaptadores e UM rfkill legível: o «ligado em N» conta só o que foi
    lido, e o outro vira «não sei» — nunca «ligado»."""
    raiz = _bt_sysfs(tmp_path, {"hci0": ("0", "0")})
    (raiz / "hci1").mkdir()
    saida = _doctor_rfkill(tmp_path, raiz)
    assert "[ OK ] rádio Bluetooth ligado em 1 adaptador(es)" in saida
    assert "não consegui ler o rfkill de hci1" in saida


def test_o_doctor_sem_adaptador_informa_e_nao_acusa(tmp_path: Path) -> None:
    raiz = tmp_path / "vazio"
    raiz.mkdir()
    saida = _doctor_rfkill(tmp_path, raiz)
    assert "nenhum adaptador Bluetooth presente" in saida
    assert "[WARN]" not in saida and "[FAIL]" not in saida


def _corpo_do_main() -> str:
    texto = DOCTOR.read_text(encoding="utf-8")
    return texto[texto.index("\nmain() {") :]


def test_o_main_do_doctor_chama_o_rfkill_na_secao_do_radio() -> None:
    main = _corpo_do_main()
    secao = main[
        main.index('hdr "energia USB e rádio"') : main.index('hdr "rádio e pareamento (G2)"')
    ]
    assert re.search(r"^\s*check_bt_rfkill\s*$", secao, re.M), (
        "a pergunta existe e o doctor não a faz"
    )


def test_o_quirk_do_cabo_nao_e_mais_chamado_de_opt_in() -> None:
    """O passo 3e aplica o `usbcore.quirks` por DEFAULT; a frase de «ausente»
    ainda dizia opt-in (resposta 6 de quem coordena)."""
    texto = DOCTOR.read_text(encoding="utf-8")
    ini = texto.index("check_usb_quirk() {")
    corpo = texto[ini : texto.index("\n}\n", ini)]
    assert "opt-in" not in corpo
    assert "passo 3e" in corpo


@pytest.mark.parametrize("nome", ["check_bt_rfkill"])
def test_a_funcao_nova_do_doctor_nao_roda_comando_de_radio(nome: str) -> None:
    texto = DOCTOR.read_text(encoding="utf-8")
    ini = texto.index(f"{nome}() {{")
    corpo = texto[ini : texto.index("\n}\n", ini)]
    codigo = "\n".join(ln for ln in corpo.splitlines() if not ln.strip().startswith("#"))
    # A linha de recado pode ENSINAR o comando; o que não pode é rodá-lo. Sai a
    # linha inteira de recado — e só ela: apagar o texto entre aspas esconderia
    # um `"$(rfkill …)"`, que é justamente a forma de rodar dentro de aspas.
    codigo = "\n".join(
        ln
        for ln in codigo.splitlines()
        if not re.match(r"\s*(warn|info|pass|fail|echo|printf)\s", ln)
    )
    for proibido in ("rfkill", "systemctl", "busctl"):
        em_posicao_de_comando = re.search(
            rf"(^|[;&|(]|\$\(|\bthen\b|\bdo\b)\s*(sudo\s+)?{proibido}\b", codigo, re.M
        )
        assert not em_posicao_de_comando, (
            f"{nome} RODA `{proibido}`: {em_posicao_de_comando.group(0)!r}"
        )


# ---------------------------------------------------------------------------
# O par da peça A1: install faz, uninstall desfaz, paridade confere, doctor diz
# ---------------------------------------------------------------------------

ABERTURA_DA_CERCA = 'if [[ "${FORMAT}" != "native" ]]; then'
DESTINOS_DO_WIFI = (
    "/usr/local/lib/hefesto-dualsense4unix/wifi_usb.sh",
    "/etc/NetworkManager/dispatcher.d/90-hefesto-wifi-usb",
    "/etc/systemd/system/hefesto-wifi-usb-vigia.service",
    "/etc/systemd/system/hefesto-wifi-usb-vigia.timer",
)


def _codigo(texto: str) -> str:
    return "\n".join(ln for ln in texto.splitlines() if not ln.strip().startswith("#"))


def test_o_install_chama_o_vigia_dos_dois_lados_da_cerca() -> None:
    """Mudança de SISTEMA é ortogonal ao formato: `--deb`/`--flatpak`/
    `--appimage` saem pelo `exit 0` da cerca e têm de levar o vigia também."""
    texto = _codigo(INSTALL.read_text(encoding="utf-8"))
    ini = texto.index(ABERTURA_DA_CERCA)
    saida = re.search(r"^\s+exit 0\s*$", texto[ini:], re.M)
    assert saida is not None
    formatos = texto[ini : ini + saida.start()]
    nativo = texto[ini + saida.end() :]
    for lado, bloco in (("formatos", formatos), ("nativo", nativo)):
        assert re.search(r"^\s*install_wifi_usb_host\s*$", bloco, re.M), f"falta no lado {lado}"


def test_a_saida_no_wifi_usb_esta_no_parser_no_help_e_no_ensaio() -> None:
    texto = INSTALL.read_text(encoding="utf-8")
    assert re.search(r"^\s+--no-wifi-usb\)\s+NO_WIFI_USB=1 ;;", texto, re.M)
    cabecalho = texto[: texto.index("\nset -euo pipefail")]
    assert "--no-wifi-usb" in cabecalho, "o --help lê o cabeçalho e tem de anunciar a saída"
    assert '"install_wifi_usb_host:wifi-usb"' in texto, (
        "sem a linha no ensaio, o --dry-run escreveria em /etc"
    )
    assert re.search(r"^\s+wifi-usb\)\s*$", texto, re.M), (
        "o ensaio não descreve o que o vigia faria"
    )


def _roda_a_cura(tmp_path: Path, funcao: str, extra: dict[str, str]) -> tuple[str, str, Path]:
    """Roda uma cura de HOST da lib com `sudo` de mentira, que só anota — e,
    quando o verbo é `install`, guarda uma cópia do que seria instalado."""
    captura = tmp_path / "captura"
    captura.mkdir(exist_ok=True)
    diario = tmp_path / "sudo.log"
    bindir = tmp_path / "bin-sudo"
    bindir.mkdir(exist_ok=True)
    (bindir / "sudo").write_text(
        "#!/bin/bash\n"
        f'printf "%s\\n" "$*" >> "{diario}"\n'
        '[ "$1" = "-n" ] && exit 0\n'
        'if [ "$1" = "install" ] && [ "$#" -ge 3 ]; then\n'
        '  eval "src=\\${$(( $# - 1 ))}"; eval "dst=\\${$#}"\n'
        f'  [ -f "$src" ] && cp "$src" "{captura}/$(basename "$dst")"\n'
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    (bindir / "sudo").chmod(0o755)
    env = {
        "PATH": f"{bindir}:/usr/bin:/bin",
        "HOME": str(tmp_path / "casa"),
        "LC_ALL": "C.UTF-8",
        "ROOT_DIR": str(RAIZ),
    }
    env.update(extra)
    r = subprocess.run(
        ["bash", "-c", f'set -euo pipefail; source "{LIB}"; {funcao}'],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=env,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    return (
        r.stdout + r.stderr,
        diario.read_text(encoding="utf-8") if diario.exists() else "",
        captura,
    )


def test_o_install_poe_os_quatro_destinos_e_liga_o_timer(tmp_path: Path) -> None:
    amb = _mesa(tmp_path)
    nm = tmp_path / "NetworkManager"
    nm.mkdir()
    saida, sudo, captura = _roda_a_cura(
        tmp_path,
        "install_wifi_usb_host",
        {"HEFESTO_WIFI_SYSFS": amb["HEFESTO_WIFI_SYSFS"], "HEFESTO_NM_ETC": str(nm)},
    )
    linhas = sudo.splitlines()
    # O destino tem de ser o ALVO de um `install`, e não só aparecer no diário:
    # o caminho do script também vem na linha do `--ensure` na hora, e com o
    # `install` dele arrancado a pergunta "o caminho está no diário?" seguia
    # verde — medido pela conferência em 23/09.
    instalados = [ln.split()[-1] for ln in linhas if ln.startswith("install ")]
    for destino in DESTINOS_DO_WIFI:
        assert destino in instalados, f"o install não pôs {destino}"
    assert "install -Dm755 -o root -g root" in sudo, "o dispatcher tem de ser de root, 755"
    assert "systemctl enable --now hefesto-wifi-usb-vigia.timer" in linhas
    # O daemon-reload vem DEPOIS das units no disco e ANTES do enable: numa
    # reinstalação, o systemd habilitaria a unit de ontem.
    ultima_unit = max(
        i for i, ln in enumerate(linhas) if ln.startswith("install ") and "wifi-usb-vigia" in ln
    )
    reload = linhas.index("systemctl daemon-reload", ultima_unit)
    assert reload < linhas.index("systemctl enable --now hefesto-wifi-usb-vigia.timer")
    # Com dongle agora, o reforço vai na hora.
    assert "/usr/local/lib/hefesto-dualsense4unix/wifi_usb.sh --ensure" in sudo
    assert (captura / "90-hefesto-wifi-usb").read_bytes() == WIFI.read_bytes(), (
        "o dispatcher é CÓPIA do mesmo fonte"
    )
    assert (captura / "wifi_usb.sh").read_bytes() == WIFI.read_bytes(), (
        "o ExecStart do vigia é o mesmo fonte"
    )
    assert "vigia do Wi-Fi USB ativo" in saida


def test_sem_dongle_o_install_instala_e_diz_que_fica_armado(tmp_path: Path) -> None:
    amb = _mesa(tmp_path, com_dongle=False)
    nm = tmp_path / "NetworkManager"
    nm.mkdir()
    saida, sudo, _ = _roda_a_cura(
        tmp_path,
        "install_wifi_usb_host",
        {"HEFESTO_WIFI_SYSFS": amb["HEFESTO_WIFI_SYSFS"], "HEFESTO_NM_ETC": str(nm)},
    )
    assert "nenhum Wi-Fi USB agora — o vigia fica armado e não faz nada" in saida
    assert "enable --now hefesto-wifi-usb-vigia.timer" in sudo
    assert "--ensure" not in sudo


def test_sem_networkmanager_o_dispatcher_nao_vai(tmp_path: Path) -> None:
    amb = _mesa(tmp_path, com_dongle=False)
    saida, sudo, _ = _roda_a_cura(
        tmp_path,
        "install_wifi_usb_host",
        {
            "HEFESTO_WIFI_SYSFS": amb["HEFESTO_WIFI_SYSFS"],
            "HEFESTO_NM_ETC": str(tmp_path / "nao-ha"),
        },
    )
    assert "90-hefesto-wifi-usb" not in sudo
    assert "sem NetworkManager nesta máquina" in saida
    assert "hefesto-wifi-usb-vigia.timer" in sudo


@pytest.mark.parametrize(
    ("flag", "frase"),
    [("NO_WIFI_USB", "pulado (--no-wifi-usb)"), ("SKIP_UDEV", "pulado (--no-udev)")],
)
def test_as_duas_saidas_nao_tocam_em_nada(tmp_path: Path, flag: str, frase: str) -> None:
    saida, sudo, _ = _roda_a_cura(tmp_path, "install_wifi_usb_host", {flag: "1"})
    assert frase in saida
    assert sudo == "", f"com {flag}=1 o install ainda chamou o sudo: {sudo!r}"


def test_o_uninstall_tira_os_quatro_antes_de_apagar_a_casa_dos_scripts() -> None:
    texto = _codigo(UNINSTALL.read_text(encoding="utf-8"))
    ini = texto.index("removendo o vigia do Wi-Fi USB")
    # Sem as linhas de RECADO: o ramo sem sudo ensina os mesmos comandos num
    # `log`, e um recado basta a um `in` solto com o `disable` ou o `rm`
    # arrancados (medido pela conferência em 23/09: o `disable` arrancado
    # passava verde, lido do recado do outro ramo).
    bloco = "\n".join(
        ln
        for ln in texto[ini : texto.index("\nfi\n", ini)].replace("\\\n", " ").splitlines()
        if not re.match(r"\s*(log|echo|printf|warn|info)\s", ln)
    )
    for destino in DESTINOS_DO_WIFI:
        assert destino in bloco, f"o uninstall não tira {destino}"
    assert "disable --now hefesto-wifi-usb-vigia.timer" in bloco
    assert "rm -rf /run/hefesto-wifi-usb" in bloco
    assert "systemctl daemon-reload" in bloco, (
        "sem o reload, o systemd segue com a unit que saiu do disco"
    )
    assert ini < texto.index("sudo rmdir /usr/local/lib/hefesto-dualsense4unix"), (
        "o wifi_usb.sh tem de sair ANTES do rmdir da casa dos scripts de sistema"
    )
    # E o uninstall pede a credencial quando há o que tirar.
    for destino in DESTINOS_DO_WIFI:
        assert f"[[ -e {destino} ]] && _NEEDS_SUDO=1" in texto, destino


def _paridade_numa_arvore(tmp_path: Path, muta: dict[str, tuple[str, str]] | None = None) -> str:
    """O portão de paridade numa árvore sintética com só o que a família usa.

    O portão faz `cd` para a pasta-mãe do PRÓPRIO arquivo, então ele viaja
    junto — chamado de fora, mediria a árvore de verdade e a mordida passaria
    verde sobre nada (foi o que a primeira versão deste teste fez).
    """
    arvore = tmp_path / "arvore"
    for rel in (
        "scripts/check_packaging_parity.sh",
        "install.sh",
        "uninstall.sh",
        "scripts/lib/camada_de_maquina.sh",
        "scripts/doctor.sh",
        "scripts/wifi_usb.sh",
        "assets/systemd/hefesto-wifi-usb-vigia.service",
        "assets/systemd/hefesto-wifi-usb-vigia.timer",
    ):
        alvo = arvore / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        texto = (RAIZ / rel).read_text(encoding="utf-8")
        if muta and rel in muta:
            velho, novo = muta[rel]
            assert velho in texto, (rel, velho)
            texto = texto.replace(velho, novo)
        alvo.write_text(texto, encoding="utf-8")
    r = subprocess.run(
        ["bash", str(arvore / "scripts" / "check_packaging_parity.sh")],
        cwd=arvore,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return r.stdout + r.stderr


def test_a_paridade_da_familia_passa_e_morde(tmp_path: Path) -> None:
    saida = _paridade_numa_arvore(tmp_path / "a")
    assert "[ OK ] vigia do Wi-Fi USB:" in saida, saida
    # A MORDIDA embutida: o uninstall "esquece" o dispatcher.
    saida = _paridade_numa_arvore(
        tmp_path / "b",
        {
            "uninstall.sh": (
                "            /etc/NetworkManager/dispatcher.d/90-hefesto-wifi-usb \\\n",
                "",
            )
        },
    )
    assert "[FAIL] vigia do Wi-Fi USB" in saida
    assert "uninstall.sh(não remove /etc/NetworkManager/dispatcher.d/90-hefesto-wifi-usb)" in saida


@pytest.mark.parametrize(
    ("arquivo", "velho", "queixa"),
    [
        # O caminho do script vem também na linha do `--ensure` na hora.
        (
            "scripts/lib/camada_de_maquina.sh",
            '    sudo install -Dm755 "${ROOT_DIR}/scripts/wifi_usb.sh" \\\n'
            "        /usr/local/lib/hefesto-dualsense4unix/wifi_usb.sh 2>/dev/null || _wifi_ok=0\n",
            "scripts/lib/camada_de_maquina.sh(não instala "
            "/usr/local/lib/hefesto-dualsense4unix/wifi_usb.sh)",
        ),
        # O `disable` vem também no recado do ramo sem sudo.
        (
            "uninstall.sh",
            "        sudo systemctl disable --now hefesto-wifi-usb-vigia.timer"
            " >/dev/null 2>&1 || true\n",
            "uninstall.sh(não desabilita o timer)",
        ),
    ],
)
def test_a_paridade_nao_le_o_ato_no_recado(
    tmp_path: Path, arquivo: str, velho: str, queixa: str
) -> None:
    """As duas mordidas que a conferência de 23/09 achou passando verde: o ato
    arrancado e o mesmo caminho ainda escrito num recado ou noutra linha."""
    saida = _paridade_numa_arvore(tmp_path, {arquivo: (velho, "")})
    assert "[FAIL] vigia do Wi-Fi USB" in saida, saida
    assert queixa in saida


# --- o doctor sabe dizer se está de pé ---------------------------------------


def _doctor_wifi(
    tmp_path: Path,
    amb: dict[str, str],
    *,
    instalado: bool,
    timer: str = "active",
    dispatcher: str | None = "root 755",
    diario: str = "",
) -> str:
    bindir = tmp_path / "bin-doctor-wifi"
    bindir.mkdir(exist_ok=True)
    (bindir / "systemctl").write_text(f'#!/bin/sh\necho "{timer}"\n', encoding="utf-8")
    (bindir / "stat").write_text(f'#!/bin/sh\necho "{dispatcher or ""}"\n', encoding="utf-8")
    (bindir / "journalctl").write_text(
        "#!/bin/sh\n"
        f"case \"$*\" in *hefesto-wifi-usb*) cat <<'FIM'\n{diario}\nFIM\n;; esac\n"
        "exit 0\n",
        encoding="utf-8",
    )
    for nome in ("systemctl", "stat", "journalctl"):
        (bindir / nome).chmod(0o755)
    inst = tmp_path / "lib" / "wifi_usb.sh"
    if instalado:
        inst.parent.mkdir(exist_ok=True)
        inst.write_bytes(WIFI.read_bytes())
        inst.chmod(0o755)
    nm = tmp_path / "etc-nm" / "dispatcher.d"
    nm.mkdir(parents=True, exist_ok=True)
    disp = nm / "90-hefesto-wifi-usb"
    if dispatcher is not None:
        disp.write_text("x", encoding="utf-8")
    else:
        disp.unlink(missing_ok=True)
    env = {
        "PATH": f"{bindir}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "LC_ALL": "C.UTF-8",
        # O `wifi_usb.sh` que o doctor chama tem PATH fixo: sem o gancho, o
        # `--status` leria o journal do kernel de quem roda a suíte.
        "HEFESTO_WIFI_BIN": str(bindir),
        "HEFESTO_WIFI_DEV": amb["HEFESTO_WIFI_DEV"],
        "HEFESTO_WIFI_SYSFS": amb["HEFESTO_WIFI_SYSFS"],
        "HEFESTO_WIFI_INSTALADO": str(inst),
        "HEFESTO_WIFI_DISPATCHER": str(disp),
    }
    r = subprocess.run(
        ["bash", "-c", f'source "{DOCTOR}"; check_wifi_usb'],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=env,
    )
    return r.stdout + r.stderr


def test_o_doctor_acusa_o_dongle_sem_vigia(tmp_path: Path) -> None:
    amb = _mesa(tmp_path)
    saida = _doctor_wifi(tmp_path, amb, instalado=False)
    assert f"[WARN] há Wi-Fi USB ({IFC}) e o vigia do dongle não está instalado" in saida


def test_o_doctor_passa_com_o_vigia_de_pe(tmp_path: Path) -> None:
    amb = _mesa(tmp_path)
    saida = _doctor_wifi(tmp_path, amb, instalado=True)
    assert f"[ OK ] vigia do Wi-Fi USB de pé ({IFC})" in saida
    assert "[WARN]" not in saida
    # A linha do --status chega, e diz que o scan de fundo não se lê sem root.
    assert "scan de fundo sem permissão para ler (só root)" in saida


def test_o_doctor_acusa_o_timer_parado_e_o_dispatcher_que_o_networkmanager_recusa(
    tmp_path: Path,
) -> None:
    amb = _mesa(tmp_path)
    saida = _doctor_wifi(tmp_path, amb, instalado=True, timer="inactive")
    assert "[WARN] o vigia do Wi-Fi USB está instalado e o timer não está ativo (inactive)" in saida
    saida = _doctor_wifi(tmp_path, amb, instalado=True, dispatcher="vitoria 775")
    assert "NetworkManager só roda script de root, 755" in saida
    saida = _doctor_wifi(tmp_path, amb, instalado=True, dispatcher=None)
    assert "não existe — cada associação nova nasce com o scan de fundo ligado" in saida


def test_o_doctor_acusa_o_vigia_que_parou_e_o_hub_do_bluetooth(tmp_path: Path) -> None:
    amb = _mesa(tmp_path, bt_no_mesmo_hub=True)
    saida = _doctor_wifi(
        tmp_path,
        amb,
        instalado=True,
        diario=f"{IFC}: 3 reinícios seguidos sem cura — parei. Tire e ponha o dongle.",
    )
    assert "PAROU neste boot — tire e ponha o dongle" in saida
    assert "[WARN] Wi-Fi USB e Bluetooth no mesmo hub" in saida


def test_o_parei_de_manha_curado_depois_nao_e_defeito_de_agora(tmp_path: Path) -> None:
    """O vigia repete o «parei» a cada tique enquanto o rádio segue mudo; o
    dongle que ela tirou e pôs de volta cura, e o journal do boot guarda as
    duas coisas. Quem decide é a ÚLTIMA — não a existência de um «parei»."""
    amb = _mesa(tmp_path)
    diario = "\n".join(
        [
            f"{IFC}: porta {PORTA} reiniciada (reset USB)",
            f"{IFC}: 3 reinícios seguidos sem cura — parei. Tire e ponha o dongle.",
            f"{IFC}: o roteador voltou a responder",
            f"{IFC}: curado depois de 3 reinício(s)",
        ]
    )
    saida = _doctor_wifi(tmp_path, amb, instalado=True, diario=diario)
    assert "PAROU" not in saida
    assert f"[ OK ] vigia do Wi-Fi USB de pé ({IFC})" in saida
    assert "o roteador voltou a responder depois" in saida


def test_o_doctor_sem_dongle_nao_acusa(tmp_path: Path) -> None:
    amb = _mesa(tmp_path, com_dongle=False)
    assert "[ OK ] nenhum Wi-Fi USB agora — o vigia está armado" in _doctor_wifi(
        tmp_path, amb, instalado=True
    )
    saida = _doctor_wifi(tmp_path, amb, instalado=False, timer="inactive")
    assert "[WARN]" not in saida and "[FAIL]" not in saida


def test_o_main_do_doctor_pergunta_pelo_vigia_na_secao_do_wifi() -> None:
    main = _corpo_do_main()
    secao = main[main.index('hdr "DKMS rtw88_usb / WiFi') : main.index('hdr "USB / dropout"')]
    assert re.search(r"^\s*check_wifi_usb\s*$", secao, re.M)


# ---------------------------------------------------------------------------
# Os dois pedidos da onda 3a: o nome do lugar chega ao adaptador
# ---------------------------------------------------------------------------


#: O que o `bt_active_mode.sh` lê, derivado DELE — se o caminho mudar lá, esta
#: régua acompanha em vez de conferir um caminho de ontem.
def _o_que_o_modo_ativo_le() -> str:
    achado = re.search(r'arquivo="\$\{casa\}(/[^"]+)"', MODO_ATIVO.read_text(encoding="utf-8"))
    assert achado, "não achei no bt_active_mode.sh onde ele lê o maquina.json da casa"
    return achado.group(1)


def _render_dropin(tmp_path: Path, casa: str) -> tuple[int, str]:
    saida = tmp_path / "dropin.conf"
    r = subprocess.run(
        [
            "bash",
            "-c",
            f'source "{LIB}"; _render_dropin_do_watchdog "$1" "$2"',
            "_",
            casa,
            str(saida),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={"PATH": "/usr/bin:/bin", "ROOT_DIR": str(RAIZ), "HOME": str(tmp_path)},
    )
    return r.returncode, saida.read_text(encoding="utf-8") if saida.exists() else ""


def _visivel_no_sandbox(unit: str, dropin: str, caminho: str) -> bool:
    """O que o systemd deixa a unit ver da casa — o modelo das duas diretivas.

    `ProtectHome=yes` torna /home, /root e /run/user INACESSÍVEIS, e um bind
    não tem onde nascer dentro deles; `tmpfs` monta um vazio só de leitura, e
    cada `BindReadOnlyPaths=` abre por cima exatamente um caminho. Sem
    `ProtectHome` a casa inteira é visível.
    """
    texto = unit + "\n" + dropin
    valores = re.findall(r"^ProtectHome=(\S+)", texto, re.M)
    protege = valores[-1] if valores else "no"
    if protege in {"no", "false"}:
        return True
    if protege in {"yes", "true", "read-only"}:
        return protege == "read-only"
    binds = []
    for linha in re.findall(r"^BindReadOnlyPaths=(.+)$", texto, re.M):
        binds += [b.lstrip("-").split(":", 1)[0] for b in linha.split()]
    return caminho in binds


def test_o_watchdog_enxerga_o_maquina_json_e_so_ele(tmp_path: Path) -> None:
    casa = "/home/pessoa"
    rc, dropin = _render_dropin(tmp_path, casa)
    assert rc == 0
    unit = WATCHDOG.read_text(encoding="utf-8")
    lido = casa + _o_que_o_modo_ativo_le()
    assert _visivel_no_sandbox(unit, dropin, lido), (
        f"o watchdog não enxerga {lido} — o nome do lugar não chega ao Alias no tique dele"
    )
    assert not _visivel_no_sandbox(unit, dropin, casa + "/.ssh/id_ed25519"), (
        "a casa inteira ficou visível"
    )
    assert f"BindReadOnlyPaths=-{lido}" in dropin, (
        "sem o `-`, a unit não sobe antes do primeiro nome"
    )
    # A mordida da decisão: sem o drop-in, o arquivo some do alcance.
    assert not _visivel_no_sandbox(unit, "", lido)


def test_casa_com_separador_do_systemd_nao_vira_drop_in(tmp_path: Path) -> None:
    for casa in ("/home/nome com espaco", '/home/aspas"', "relativa/casa", "/"):
        rc, dropin = _render_dropin(tmp_path, casa)
        assert rc == 1 and dropin == "", casa


def test_o_install_da_resiliencia_escreve_o_drop_in_com_a_casa_de_quem_instalou(
    tmp_path: Path,
) -> None:
    _, sudo, captura = _roda_a_cura(tmp_path, "install_bt_resilience_host", {})
    destino = "/etc/systemd/system/hefesto-bt-health-watchdog.service.d/10-hefesto-maquina.conf"
    assert destino in sudo
    gravado = (captura / "10-hefesto-maquina.conf").read_text(encoding="utf-8")
    assert f"BindReadOnlyPaths=-{tmp_path / 'casa'}{_o_que_o_modo_ativo_le()}" in gravado
    # E ANTES do daemon-reload, para o próximo tique já montar o arquivo.
    assert sudo.index(destino) < sudo.index("systemctl daemon-reload")


def test_o_uninstall_leva_o_drop_in_do_watchdog() -> None:
    texto = _codigo(UNINSTALL.read_text(encoding="utf-8"))
    dropin = "/etc/systemd/system/hefesto-bt-health-watchdog.service.d/10-hefesto-maquina.conf"
    assert f"sudo rm -f {dropin}" in texto
    assert "sudo rmdir /etc/systemd/system/hefesto-bt-health-watchdog.service.d" in texto


def test_o_modo_ativo_no_start_do_bluetoothd_roda_fora_do_sandbox() -> None:
    """O `bluetooth.service` roda com `ProtectHome=true`, e o `ExecStartPost`
    herda o sandbox; sem o `+`, o nome do lugar só chegava 2 min depois."""
    linhas = [
        ln
        for ln in DROPIN_BT.read_text(encoding="utf-8").splitlines()
        if ln.startswith("ExecStartPost=") and "bt_active_mode.sh" in ln
    ]
    assert len(linhas) == 1
    prefixo = linhas[0].split("=", 1)[1].split("/", 1)[0]
    assert "+" in prefixo, f"sem o `+` o gancho herda o ProtectHome do bluetoothd: {linhas[0]!r}"
    assert "-" in prefixo, (
        "o `-` continua: adaptador que não subiu no start não derruba o bluetoothd"
    )
    assert "!" not in prefixo, "`+` e `!` não se combinam no systemd"
