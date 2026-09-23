"""O reinício do adaptador travado PARA depois de três sem cura — GOVERNADOR-DO-RADIO-01.

O ``reiniciar-travado`` da ponte privilegiada (O-DIARIO-DO-RADIO-01) tirava e
punha a porta USB de um adaptador em laço de «command tx timeout», com um freio
de 15 min entre reinícios. O freio só ESPAÇAVA: um adaptador que volta a travar
depois de cada reinício era reiniciado quatro vezes por hora, para sempre — e
cada reinício é o dongle sumindo e voltando na porta dela, o que ninguém cura.

A decisão de quem coordena (23/09/2026): depois de TRÊS reinícios seguidos sem
cura, o verbo PARA, grava isso no diário UMA vez, e o sino fica com a frase de
pôr a mão. O freio solta quando o laço some do journal.

A MORDIDA, feita em 23/09/2026: tirar o bloco ``seguidos >=
MAX_REINICIOS_SEGUIDOS`` do verbo faz
``test_o_quarto_reinicio_sem_cura_nao_acontece`` reprovar com a porta
reautorizada. Devolvido o arquivo, md5 conferido.

Nada aqui toca o /sys, o journal ou o diário dela: as três raízes vêm de
``tmp_path`` pelos ganchos da ponte, e o verbo roda como ela, sem sudo.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from hefesto_dualsense4unix.integrations import diario_do_radio as diario

RAIZ = Path(__file__).resolve().parents[2]
PONTE = RAIZ / "scripts" / "bt_ponte_privilegiada.sh"
PORTA = "3-1.1.2"

_MENSAGENS_DA_VOLTA = (
    "command 0xfc61 tx timeout",
    "RTL: RTL: Read reg16 failed (-110)",
)


def _laco(mais_novo: int, hci: str = "hci0") -> str:
    """Oito voltas do laço de 13/09, a mais nova em ``mais_novo``."""
    return "".join(
        f"{mais_novo - 14 + s}.250000 maquina kernel: Bluetooth: {hci}: {m}\n"
        for s in range(0, 15, 2)
        for m in _MENSAGENS_DA_VOLTA
    )


def _mesa_sysfs(raiz: Path, adaptadores: dict[str, str]) -> Path:
    """``{hciN: porta}`` → um /sys com class/bluetooth, bus/usb/devices e o authorized."""
    for hci, porta in adaptadores.items():
        aparelho = raiz / "devices" / "pci0000:00" / "usb" / porta
        interface = aparelho / f"{porta}:1.0"
        (interface / "bluetooth" / hci).mkdir(parents=True)
        (aparelho / "authorized").write_text("semente", encoding="utf-8")
        classe = raiz / "class" / "bluetooth"
        classe.mkdir(parents=True, exist_ok=True)
        (classe / hci).symlink_to(interface / "bluetooth" / hci)
        barramento = raiz / "bus" / "usb" / "devices"
        barramento.mkdir(parents=True, exist_ok=True)
        (barramento / porta).symlink_to(aparelho)
    return raiz


def _reiniciar(tmp_path: Path, sysfs: Path, journal: str) -> subprocess.CompletedProcess[str]:
    (tmp_path / "journal.txt").write_text(journal, encoding="utf-8")
    env = {
        chave: valor
        for chave, valor in os.environ.items()
        if chave not in ("SUDO_UID", "SUDO_USER")
    }
    env.update(
        HEFESTO_BT_LIB=str(tmp_path / "bluetooth"),
        HEFESTO_BT_LOG_DEST="none",
        HEFESTO_RADIO_DIARIO_ROOT=str(tmp_path / "diario-root.jsonl"),
        HEFESTO_SYSFS_RAIZ=str(sysfs),
        HEFESTO_BT_JOURNAL=str(tmp_path / "journal.txt"),
        HEFESTO_PONTE_STAMPS=str(tmp_path / "stamps"),
        HEFESTO_USB_PAUSA_S="0",
        HEFESTO_USB_ESPERA_S="0",
    )
    return subprocess.run(
        ["bash", str(PONTE), "reiniciar-travado"],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )


def _estampas(tmp_path: Path) -> Path:
    pasta = tmp_path / "stamps"
    pasta.mkdir(exist_ok=True)
    return pasta


def _carimbar(tmp_path: Path, *, anterior: int, seguidos: int | None = None) -> None:
    pasta = _estampas(tmp_path)
    (pasta / f"reset-{PORTA}").write_text(f"{anterior}\n", encoding="utf-8")
    if seguidos is not None:
        (pasta / f"reset-{PORTA}.seguidos").write_text(f"{seguidos}\n", encoding="utf-8")


def _autorizado(sysfs: Path) -> str:
    return (sysfs / "bus" / "usb" / "devices" / PORTA / "authorized").read_text(encoding="utf-8")


def _entradas(tmp_path: Path) -> list[dict]:
    return diario.ler(caminhos=[tmp_path / "diario-root.jsonl"])


def test_o_quarto_reinicio_sem_cura_nao_acontece(tmp_path: Path) -> None:
    """Três reinícios seguidos, e o laço voltou depois de cada um: o quarto não vem.

    O verbo segura, diz no diário UMA vez, e o sino fica com «tire e ponha».
    """
    agora = int(time.time())
    sysfs = _mesa_sysfs(tmp_path / "sys", {"hci0": PORTA})
    _carimbar(tmp_path, anterior=agora - 901, seguidos=3)
    resultado = _reiniciar(tmp_path, sysfs, _laco(agora - 1))
    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout.splitlines() == [
        f"segurado\t{PORTA}\thci0\tparou depois de 3 reinícios"
    ]
    assert _autorizado(sysfs) == "semente", "o quarto reinício sem cura aconteceu"
    [entrada] = _entradas(tmp_path)
    assert entrada["o_que"] == "parou de reiniciar o adaptador"
    assert (entrada["porta"], entrada["familia"]) == (PORTA, "3")
    assert entrada["antes"]["reinicios"] == 3
    assert entrada["frase"] == (
        f"O adaptador da porta {PORTA} não se cura sozinho. Tire e ponha ele."
    )

    # Os tiques seguintes seguram CALADOS: o sino não repete a frase.
    for _ in range(2):
        de_novo = _reiniciar(tmp_path, sysfs, _laco(int(time.time()) - 1))
        assert de_novo.stdout.startswith(f"segurado\t{PORTA}\thci0\tparou depois de")
        assert _autorizado(sysfs) == "semente"
    assert len(_entradas(tmp_path)) == 1, "a mesma frase entrou no diário a cada tique"


def test_o_segundo_e_o_terceiro_reinicio_seguidos_acontecem_e_contam(tmp_path: Path) -> None:
    """O freio não pode parar cedo: até três, o reinício é a cura por software."""
    agora = int(time.time())
    sysfs = _mesa_sysfs(tmp_path / "sys", {"hci0": PORTA})
    _carimbar(tmp_path, anterior=agora - 901, seguidos=2)
    resultado = _reiniciar(tmp_path, sysfs, _laco(agora - 1))
    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout.startswith(f"reiniciado\t{PORTA}\thci0\t")
    assert _autorizado(sysfs) == "1"
    seguidos = (_estampas(tmp_path) / f"reset-{PORTA}.seguidos").read_text(encoding="utf-8")
    assert seguidos.strip() == "3"


def test_o_reinicio_que_curou_por_horas_zera_a_conta(tmp_path: Path) -> None:
    """Um laço que volta três horas depois não é o mesmo defeito: a conta recomeça."""
    agora = int(time.time())
    sysfs = _mesa_sysfs(tmp_path / "sys", {"hci0": PORTA})
    _carimbar(tmp_path, anterior=agora - 3 * 3600, seguidos=3)
    resultado = _reiniciar(tmp_path, sysfs, _laco(agora - 1))
    assert resultado.stdout.startswith(f"reiniciado\t{PORTA}\thci0\t"), resultado.stdout
    seguidos = (_estampas(tmp_path) / f"reset-{PORTA}.seguidos").read_text(encoding="utf-8")
    assert seguidos.strip() == "1"


def test_o_freio_solta_quando_o_laco_some_e_volta_a_valer_depois(tmp_path: Path) -> None:
    """A mão dela curou (tirou e pôs): o laço sumiu do journal, e o freio solta.

    Sem soltar, uma porta que parou de reiniciar uma vez ficaria parada para
    sempre — inclusive para o travamento de outro dia, que o reinício curaria.
    """
    agora = int(time.time())
    sysfs = _mesa_sysfs(tmp_path / "sys", {"hci0": PORTA})
    _carimbar(tmp_path, anterior=agora - 901, seguidos=3)
    assert _reiniciar(tmp_path, sysfs, _laco(agora - 1)).stdout.startswith("segurado")
    marca = _estampas(tmp_path) / f"reset-{PORTA}.desistiu"
    assert marca.exists()

    # O journal sem o laço — o adaptador voltou são.
    calado = _reiniciar(tmp_path, sysfs, "")
    assert calado.returncode == 0, calado.stderr
    assert calado.stdout == ""
    assert not marca.exists(), "o laço sumiu e o freio continuou preso"
    assert [e["o_que"] for e in _entradas(tmp_path)] == [
        "parou de reiniciar o adaptador",
        "soltou o freio do reinício",
    ]
    assert _entradas(tmp_path)[-1]["por_que"] == (
        f"o laço sumiu do journal: nenhum «command tx timeout» do hci0 da porta {PORTA} em 150 s"
    )


def test_a_porta_vazia_solta_o_freio_sem_dizer_que_o_adaptador_voltou(tmp_path: Path) -> None:
    """Ela tirou o adaptador e ainda não o pôs de volta: a porta está VAZIA.

    O freio solta — a mão dela agiu —, mas o diário diz o que foi medido: a
    porta sem aparelho. Conferência de 23/09/2026: ele dizia «voltou».

    MORDIDA: devolva o texto único de antes e a porta vazia vira «voltou».
    """
    agora = int(time.time())
    sysfs = _mesa_sysfs(tmp_path / "sys", {"hci0": PORTA})
    _carimbar(tmp_path, anterior=agora - 901, seguidos=3)
    _reiniciar(tmp_path, sysfs, _laco(agora - 1))
    vazia = _mesa_sysfs(tmp_path / "sys-vazio", {})
    (vazia / "bus" / "usb" / "devices").mkdir(parents=True, exist_ok=True)
    assert _reiniciar(tmp_path, vazia, "").returncode == 0
    ultima = _entradas(tmp_path)[-1]
    assert ultima["o_que"] == "soltou o freio do reinício"
    assert ultima["por_que"] == f"a porta {PORTA} ficou sem adaptador: o laço saiu com ele"
    assert "voltou" not in ultima["por_que"]


def test_o_freio_nao_solta_com_o_laco_vivo_mas_espacado(tmp_path: Path) -> None:
    """O laço que ainda está na janela do journal não é cura, mesmo parado há 20 s."""
    agora = int(time.time())
    sysfs = _mesa_sysfs(tmp_path / "sys", {"hci0": PORTA})
    _carimbar(tmp_path, anterior=agora - 901, seguidos=3)
    _reiniciar(tmp_path, sysfs, _laco(agora - 1))
    marca = _estampas(tmp_path) / f"reset-{PORTA}.desistiu"
    _reiniciar(tmp_path, sysfs, _laco(agora - 20))
    assert marca.exists(), "um intervalo de 20 s no laço soltou o freio"
