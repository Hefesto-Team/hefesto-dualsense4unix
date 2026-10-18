"""O vigia do rádio só toca os controles (O-VIGIA-DO-RADIO-SO-TOCA-OS-CONTROLES-DO-HEFESTO-01).

Medido em 09/10/2026: o ``hefesto-bt-health-watchdog`` pareava e dava confiança
a QUALQUER aparelho conectado. Três acessórios BLE de outro dono, sempre
``Paired=true, Bonded=false`` por natureza, recebiam ``Pair()`` a cada boot
(30 s cada, com a trava do rádio na mão) e um aviso a cada tique de dois minutos.

A pergunta «isto é um controle?» é a do produto, em Python
(``e_controle_pelo_info``); o vigia a repete em shell. As réguas:

1. a PARIDADE das duas contas, pelo gancho ``--e-controle``;
2. o COMPORTAMENTO: o tique inteiro, com ``busctl``, ``bluetoothctl`` e
   ``systemctl`` de mentira, e a trava e o diário em ``tmp_path``;
3. a vigia 1 continua contando todo aparelho conectado.

Nada aqui toca o rádio, o diário ou a trava da máquina de quem roda.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.utils.memoria_dos_controles import e_controle_pelo_info

RAIZ = Path(__file__).resolve().parents[2]
WATCHDOG = RAIZ / "scripts" / "bt_health_watchdog.sh"

# (classe, aparência) como o BlueZ os anuncia; None = não anunciou.
TABELA: list[tuple[int | str | None, int | str | None, str]] = [
    (0x002508, None, "DualSense (gamepad)"),
    (0x002504, None, "joystick"),
    (0x002540, None, "teclado"),
    (0x002580, None, "apontador"),
    (0x0025C8, None, "combo teclado e apontador"),
    (0x240404, None, "fone"),
    (None, 0x03C4, "LE gamepad"),
    (None, 0x03C3, "LE joystick"),
    (None, 0x0000, "aparência zero"),
    (None, None, "nada anunciado"),
    ("torto", None, "classe que não se lê"),
    (None, "torto", "aparência que não se lê"),
    (0x002508, "torto", "classe boa e aparência torta"),
    ("torto", 0x03C4, "classe torta e aparência de controle"),
    ("09480", None, "decimal com zero à esquerda, que o int(…, 0) recusa"),
]


def _como_o_busctl(valor: int | str | None) -> str:
    """O ``busctl`` devolve inteiro em decimal; o torto vai como veio."""
    if valor is None:
        return ""
    return str(valor)


def _info_do_bluez(classe: int | str | None, aparencia: int | str | None) -> str:
    """O ``info`` do BlueZ guarda a classe em hexadecimal."""
    linhas = ["[General]"]
    if classe is not None:
        linhas.append(f"Class={classe:#08x}" if isinstance(classe, int) else f"Class={classe}")
    if aparencia is not None:
        texto = f"{aparencia:#06x}" if isinstance(aparencia, int) else aparencia
        linhas.append(f"Appearance={texto}")
    return "\n".join(linhas) + "\n"


def _ambiente_do_gancho(tmp_path: Path) -> dict[str, str]:
    """O mesmo idioma do ``--sdp-cache-only``: a árvore do BlueZ desviada, sem root."""
    return {
        **os.environ,
        "HEFESTO_BT_SRC": str(tmp_path / "bluetooth"),
        "HEFESTO_BT_STAMP_DIR": str(tmp_path / "stamps"),
    }


@pytest.mark.parametrize(("classe", "aparencia", "quem"), TABELA, ids=[t[2] for t in TABELA])
def test_a_conta_do_shell_e_a_do_python_dao_a_mesma_resposta(
    tmp_path: Path, classe: int | str | None, aparencia: int | str | None, quem: str
) -> None:
    esperado = e_controle_pelo_info(_info_do_bluez(classe, aparencia))
    proc = subprocess.run(
        ["bash", str(WATCHDOG), "--e-controle", _como_o_busctl(classe), _como_o_busctl(aparencia)],
        capture_output=True,
        text=True,
        env=_ambiente_do_gancho(tmp_path),
        timeout=30,
    )
    assert proc.returncode in (0, 1), (
        f"{quem}: o gancho morreu (rc={proc.returncode}, {proc.stderr!r})"
    )
    assert (proc.returncode == 0) is esperado, (
        f"{quem}: o vigia e o produto discordam (shell rc={proc.returncode}, python={esperado})"
    )


def test_o_gancho_aceita_hexadecimal_como_o_info_do_bluez(tmp_path: Path) -> None:
    proc = subprocess.run(
        ["bash", str(WATCHDOG), "--e-controle", "0x002508", ""],
        capture_output=True,
        env=_ambiente_do_gancho(tmp_path),
        timeout=30,
    )
    assert proc.returncode == 0


# --- o comportamento: o tique inteiro com o BlueZ de mentira ------------------

CONTROLE = "AA_BB_CC_00_00_01"
ACESSORIO = "AA_BB_CC_00_00_02"


def _executavel(caminho: Path, corpo: str) -> None:
    caminho.write_text("#!/usr/bin/env bash\n" + corpo, encoding="utf-8")
    caminho.chmod(caminho.stat().st_mode | stat.S_IXUSR)


def _prop(mentira: Path, dispositivo: str, nome: str, valor: str | None) -> None:
    if valor is None:
        return
    pasta = mentira / "props" / dispositivo
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / nome).write_text(valor + "\n", encoding="utf-8")


def _bancada(
    tmp_path: Path, *, bonded: bool, recusas: bool = False
) -> tuple[dict[str, str], Path]:
    """Dois aparelhos conectados e pareados: um controle e um acessório sem classe."""
    mentira = tmp_path / "mentira"
    bin_ = mentira / "bin"
    bin_.mkdir(parents=True)
    (mentira / "props").mkdir()
    (mentira / "chamadas").write_text("", encoding="utf-8")
    objetos = [f"/org/bluez/hci0/dev_{CONTROLE}", f"/org/bluez/hci1/dev_{ACESSORIO}"]
    (mentira / "arvore").write_text("\n".join(objetos) + "\n", encoding="utf-8")
    for dispositivo, classe in ((CONTROLE, "u 9480"), (ACESSORIO, None)):
        _prop(mentira, dispositivo, "Connected", "b true")
        _prop(mentira, dispositivo, "Paired", "b true")
        _prop(mentira, dispositivo, "Bonded", "b true" if bonded else "b false")
        _prop(mentira, dispositivo, "Trusted", "b false")
        _prop(mentira, dispositivo, "Class", classe)
    _executavel(
        bin_ / "busctl",
        f'''M="{mentira}"
case "$1" in
    tree) cat "$M/arvore" ;;
    get-property)
        d="${{3##*dev_}}"
        [[ -f "$M/props/$d/$5" ]] && cat "$M/props/$d/$5" || exit 1 ;;
    *) printf 'busctl %s\\n' "$*" >>"$M/chamadas" ;;
esac
''',
    )
    # `pair` e `trust` chegam ao bluetoothctl de mentira pela entrada padrão.
    _executavel(
        bin_ / "bluetoothctl",
        f'''while IFS= read -r l; do printf 'btctl %s\\n' "$l" >>"{mentira}/chamadas"; done\n''',
    )
    _executavel(bin_ / "sleep", "exit 0\n")
    _executavel(
        bin_ / "systemctl",
        f'''case "$1" in
    is-active) exit 0 ;;
    *) printf 'systemctl %s\\n' "$*" >>"{mentira}/chamadas" ;;
esac
''',
    )
    # Oito recusas de dois aparelhos presentes: a doença que a vigia 1 existe para pegar.
    linhas = [
        f"Refusing connection from {mac}: unknown device"
        for mac in ("AA:BB:CC:00:00:01", "AA:BB:CC:00:00:02")
        for _ in range(4)
    ]
    texto_do_journal = "\n".join(linhas) + "\n" if recusas else ""
    (mentira / "journal").write_text(texto_do_journal, encoding="utf-8")
    _executavel(bin_ / "journalctl", f'cat "{mentira}/journal"\n')
    _executavel(bin_ / "logger", "exit 0\n")
    vazio = tmp_path / "vazio"
    for nome in ("bt", "hid", "usb", "sys", "lib", "hdrv", "udrv", "rebind"):
        (vazio / nome).mkdir(parents=True)
    env = {
        **os.environ,
        "PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}",
        "HEFESTO_BT_SRC": str(vazio / "bt"),
        "HEFESTO_HIDRAW_ROOT": str(vazio / "hid"),
        "HEFESTO_BT_STAMP_DIR": str(tmp_path / "stamps"),
        "HEFESTO_BT_LOG_DEST": str(tmp_path / "log.txt"),
        "HEFESTO_RADIO_TRAVA": str(tmp_path / "radio.lock"),
        "HEFESTO_RADIO_DIARIO_ROOT": str(tmp_path / "diario.jsonl"),
        # Os vizinhos que o tique chama, desviados para o vazio: nada da máquina.
        "HEFESTO_SYS_BLUETOOTH": str(vazio / "sys"),
        "HEFESTO_BT_LIB": str(vazio / "lib"),
        "HEFESTO_HID_DEVICES_DIR": str(vazio / "hid"),
        "HEFESTO_HID_DRIVERS_DIR": str(vazio / "hdrv"),
        "HEFESTO_USB_DEVICES_DIR": str(vazio / "usb"),
        "HEFESTO_USB_DRIVERS_DIR": str(vazio / "udrv"),
        "HEFESTO_REBIND_STAMP_DIR": str(vazio / "rebind"),
    }
    env.pop("SUDO_UID", None)
    env.pop("SUDO_USER", None)
    return env, mentira


def _tique(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(WATCHDOG)], capture_output=True, text=True, env=env, timeout=60
    )


def _chamadas(mentira: Path) -> list[str]:
    return (mentira / "chamadas").read_text(encoding="utf-8").splitlines()


def _log(tmp_path: Path) -> str:
    arquivo = tmp_path / "log.txt"
    return arquivo.read_text(encoding="utf-8") if arquivo.exists() else ""


def test_o_bond_temporario_so_e_promovido_no_controle(tmp_path: Path) -> None:
    env, mentira = _bancada(tmp_path, bonded=False)
    proc = _tique(env)
    assert proc.returncode == 0, proc.stderr
    chamadas = _chamadas(mentira)
    mac_do_controle = CONTROLE.replace("_", ":")
    mac_do_acessorio = ACESSORIO.replace("_", ":")
    assert f"btctl pair {mac_do_controle}" in chamadas, f"o controle ficou sem Pair(): {chamadas}"
    assert f"btctl trust {mac_do_controle}" in chamadas
    outros = [c for c in chamadas if mac_do_acessorio.lower() in c.lower()]
    assert not outros, f"o vigia tocou o aparelho que não é controle: {outros}"
    assert mac_do_acessorio.lower() not in _log(tmp_path).lower(), (
        "o aparelho de outro dono não é assunto do journal do Hefesto"
    )


def test_o_trust_so_e_aplicado_no_controle(tmp_path: Path) -> None:
    env, mentira = _bancada(tmp_path, bonded=True)
    proc = _tique(env)
    assert proc.returncode == 0, proc.stderr
    sets = [c for c in _chamadas(mentira) if c.startswith("busctl set-property")]
    assert len(sets) == 1, f"esperava o Trusted só no controle, vieram: {sets}"
    assert f"dev_{CONTROLE}" in sets[0]
    assert not any(ACESSORIO in c for c in _chamadas(mentira))
    assert ACESSORIO.replace("_", ":").lower() not in _log(tmp_path).lower()


def test_a_vigia_1_ainda_conta_o_aparelho_que_nao_e_controle(tmp_path: Path) -> None:
    """Só o acessório sem classe está conectado: o restart continua adiado."""
    env, mentira = _bancada(tmp_path, bonded=True, recusas=True)
    # O controle sai do ar; sobra conectado só o aparelho que não é controle.
    _prop(mentira, CONTROLE, "Connected", "b false")
    proc = _tique(env)
    assert proc.returncode == 0, proc.stderr
    assert "restart adiado (nunca derrubo sessão viva)" in proc.stdout, proc.stdout
    assert not any(c.startswith("systemctl restart") for c in _chamadas(mentira)), (
        "o aparelho conectado que não é controle deixou de segurar o restart do bluetoothd"
    )
