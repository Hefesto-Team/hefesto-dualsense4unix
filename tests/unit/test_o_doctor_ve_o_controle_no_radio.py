"""O-DOCTOR-VE-O-CONTROLE-NO-RADIO-01 — o doctor dizia «não detectado» com o controle no rádio.

Medido na mesa dela depois do install de 25/09/2026: um DualSense conectado pelo
BT, e o ``check_controller`` avisando «controle não detectado agora». A causa:
as duas perguntas «há controle agora?» rodavam ``timeout 4 bluetoothctl
devices``, e o ``timeout`` é um BINÁRIO — ele executa o bluetoothctl de verdade
e pula o embrulho BLUEZ-586-CTL-01 que o próprio ``doctor.sh`` escreveu em 22/07
para o 5.86, que no modo de um comando só não imprime nada (``rc=0``).

A resposta agora vem do kernel (o ``uevent`` de cada hidraw) para «conectado» e
do BlueZ pelo D-Bus para «pareado». Estas réguas rodam as FUNÇÕES do shell,
extraídas do ``doctor.sh``, sobre um ``/sys`` de mentira: de zero a quatro
controles, no cabo, no rádio e misto, de quatro fabricantes, com o vpad de cada
máscara no meio.
"""

from __future__ import annotations

import re
import subprocess
import textwrap
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations.exame_da_mesa import VIDS_DE_CONTROLE

RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"

#: ``(vid, pid)`` de quatro famílias que o produto adota.
CONTROLES = (
    ("054c", "0ce6"),  # DualSense
    ("054c", "0df2"),  # DualSense Edge
    ("057e", "2009"),  # Pro Controller
    ("2dc8", "6012"),  # 8BitDo
)


def _uevent(bus: str, vid: str, pid: str, phys: str, uniq: str) -> str:
    return (
        f"DRIVER=playstation\nHID_ID={bus}:0000{vid.upper()}:0000{pid.upper()}\n"
        f"HID_NAME=controle de mentira\nHID_PHYS={phys}\nHID_UNIQ={uniq}\n"
    )


def _sys(raiz: Path, nos: list[str]) -> Path:
    for n, texto in enumerate(nos):
        pasta = raiz / f"hidraw{n}" / "device"
        pasta.mkdir(parents=True)
        (pasta / "uevent").write_text(texto, encoding="utf-8")
    return raiz


def _rodar(
    raiz: Path,
    *,
    caminhos: list[str] | None = None,
    pareados: dict[str, int] | None = None,
    corpo: str = "check_controller",
) -> str:
    """Roda ``corpo`` com as funções do doctor e um BlueZ de mentira.

    ``pareados`` é ``{caminho do objeto: classe}`` dos que têm ``Paired=true``.
    """
    pareados = pareados or {}
    tabela = "\n".join(f"{c} {k}" for c, k in pareados.items())
    roteiro = textwrap.dedent(f"""
        set -uo pipefail
        pass() {{ echo "[OK] $*"; }}
        warn() {{ echo "[WARN] $*"; }}
        info() {{ echo "[INFO] $*"; }}
        _dbus_bt_device_paths() {{ printf '%s\\n' "$CAMINHOS"; }}
        _dbus_bt_prop() {{
            local linha
            linha="$(grep -m1 -- "^$1 " <<<"$PAREADOS")"
            case "$3" in
                Paired) if [[ -n "$linha" ]]; then echo true; else echo false; fi ;;
                Class) echo "${{linha##* }}" ;;
            esac
        }}
        eval "$(sed -n '/^_VIDS_DE_CONTROLE=/p' {DOCTOR})"
        for f in _controles_no_kernel _controles_pareados_no_bluez check_controller; do
            eval "$(sed -n "/^${{f}}() {{/,/^}}/p" {DOCTOR})"
        done
        {corpo}
    """)
    fim = subprocess.run(
        ["bash", "-c", roteiro],
        capture_output=True,
        text=True,
        env={
            "HEFESTO_HIDRAW_ROOT": str(raiz),
            "CAMINHOS": "\n".join(caminhos or list(pareados)),
            "PAREADOS": tabela,
            "PATH": "/usr/bin:/bin",
        },
        check=False,
    )
    return fim.stdout + fim.stderr


def test_o_dualsense_no_radio_e_visto(tmp_path: Path) -> None:
    """O caso da mesa dela, 25/09.

    MORDIDA: troque o ``0005)`` do ``_controles_no_kernel`` por outro barramento —
    o controle no rádio some, o doctor volta a dizer «não detectado», e esta
    régua reprova.
    """
    raiz = _sys(
        tmp_path, [_uevent("0005", "054c", "0ce6", "aa:bb:cc:00:00:a1", "aa:bb:cc:00:00:01")]
    )
    saida = _rodar(raiz)
    assert "[OK] controle conectado agora: 0 pelo USB e 1 pelo BT" in saida, saida
    assert "[WARN]" not in saida, saida


@pytest.mark.parametrize("mascara", ["nativo", "dualsense", "xbox"])
@pytest.mark.parametrize("transporte", ["usb", "bt", "misto"])
@pytest.mark.parametrize("jogadores", [0, 1, 2, 3, 4])
def test_a_mesa_inteira(tmp_path: Path, jogadores: int, transporte: str, mascara: str) -> None:
    """Cada jogador conta UMA vez, no transporte dele; o vpad não conta nunca.

    Na máscara DualSense cada jogador tem um vpad hidraw (``hefesto-vpad``, uniq
    02:fe, e o ``HID_ID`` de um DualSense Edge no USB: ``0003:054C:0DF2``, medido
    em 25/09); no Xbox o vpad é uinput, sem hidraw; no nativo não há vpad.
    """
    nos: list[str] = []
    esperado = {"USB": 0, "BT": 0}
    for i in range(jogadores):
        vid, pid = CONTROLES[i]
        pelo_bt = transporte == "bt" or (transporte == "misto" and i % 2 == 1)
        bus, phys = (
            ("0005", "aa:bb:cc:00:00:a1") if pelo_bt else ("0003", f"usb-0000:0c:00.3-{i}/input3")
        )
        nos.append(_uevent(bus, vid, pid, phys, f"aa:bb:cc:00:00:0{i + 1}"))
        esperado["BT" if pelo_bt else "USB"] += 1
        if mascara == "dualsense":
            # A forma medida em 25/09: o vpad anuncia USB e DualSense Edge.
            nos.append(_uevent("0003", "054c", "0df2", "hefesto-vpad", f"02:fe:00:00:00:0{i + 1}"))
    raiz = _sys(tmp_path, nos)
    saida = _rodar(raiz)
    if jogadores:
        linha = (
            f"[OK] controle conectado agora: {esperado['USB']} pelo USB e {esperado['BT']} pelo BT"
        )
        assert linha in saida, saida
    else:
        assert "[WARN] controle não detectado agora" in saida, saida


def test_o_vpad_sozinho_nao_e_controle(tmp_path: Path) -> None:
    """MORDIDA: tire o ``hefesto-vpad``/``02:fe`` do ``_controles_no_kernel`` — o
    boneco vira controle conectado, e esta régua reprova."""
    raiz = _sys(tmp_path, [_uevent("0003", "054c", "0df2", "hefesto-vpad", "02:fe:00:00:00:01")])
    saida = _rodar(raiz)
    assert "[WARN] controle não detectado agora" in saida, saida


def test_teclado_nao_e_controle(tmp_path: Path) -> None:
    raiz = _sys(
        tmp_path, [_uevent("0005", "046d", "b35b", "aa:bb:cc:00:00:a1", "aa:bb:cc:00:00:09")]
    )
    assert "[WARN] controle não detectado agora" in _rodar(raiz)


def test_desligado_e_pareado_passa_com_o_pareado(tmp_path: Path) -> None:
    """Nenhum nó no kernel e um DualSense com chave no BlueZ: «pareado»."""
    saida = _rodar(tmp_path, pareados={"/org/bluez/hci1/dev_AA_BB_CC_00_00_01": 0x2508})
    assert "[OK] controle pareado pelo BT" in saida, saida


def test_o_vizinho_e_o_teclado_pareados_nao_sao_controle(tmp_path: Path) -> None:
    """MORDIDA: tire a conta da classe do ``_controles_pareados_no_bluez`` — o
    teclado pareado vira «controle pareado», e esta régua reprova."""
    saida = _rodar(
        tmp_path,
        caminhos=["/org/bluez/hci1/dev_AA_BB_CC_00_00_77", "/org/bluez/hci0/dev_AA_BB_CC_00_00_09"],
        pareados={"/org/bluez/hci0/dev_AA_BB_CC_00_00_09": 0x002540},
    )
    assert "[WARN] controle não detectado agora" in saida, saida


def test_a_lista_de_fabricantes_e_a_do_produto() -> None:
    """Uma pergunta, uma lista: a do doctor é a de ``exame_da_mesa``.

    MORDIDA: tire um fabricante do ``_VIDS_DE_CONTROLE`` — esta régua reprova.
    """
    texto = DOCTOR.read_text(encoding="utf-8")
    achado = re.search(r'^_VIDS_DE_CONTROLE="([^"]*)"', texto, re.MULTILINE)
    assert achado, "a lista sumiu do doctor"
    assert set(achado.group(1).split()) == set(VIDS_DE_CONTROLE)


def test_nenhum_bluetoothctl_escapa_do_embrulho() -> None:
    """A forma do defeito: um comando externo na frente executa o BINÁRIO e pula
    a função ``bluetoothctl`` que sombreia o 5.86 mudo.

    MORDIDA: devolva o ``timeout 4 bluetoothctl devices`` a qualquer check — esta
    régua reprova.
    """
    forma = re.compile(
        r"\b(timeout|env|xargs|sudo|nice|stdbuf|command)(\s+-\S+)*(\s+\d+[smh]?)?\s+bluetoothctl\b"
    )
    fora = []
    dentro_do_embrulho = False
    for n, linha in enumerate(DOCTOR.read_text(encoding="utf-8").splitlines(), 1):
        if linha.startswith("bluetoothctl() {"):
            dentro_do_embrulho = True
        elif dentro_do_embrulho and linha.startswith("}"):
            dentro_do_embrulho = False
        if dentro_do_embrulho or linha.lstrip().startswith("#"):
            continue
        # `command -v bluetoothctl` só pergunta se existe; tirado ele, o resto
        # da linha ainda é medido (a linha do defeito começava por ele).
        if forma.search(linha.replace("command -v bluetoothctl", "")):
            fora.append(f"{n}: {linha.strip()}")
    assert not fora, "bluetoothctl chamado por fora do embrulho:\n" + "\n".join(fora)
