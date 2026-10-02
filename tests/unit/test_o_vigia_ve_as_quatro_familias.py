"""O vigia do kernel vê as quatro famílias do rádio — O-DIARIO-DO-RADIO-01."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import diario_do_radio as diario
from hefesto_dualsense4unix.integrations import storm_doctor

RAIZ = Path(__file__).resolve().parents[2]
VIGIA = RAIZ / "scripts" / "storm_watch.sh"

LINHAS_REAIS: dict[str, tuple[str, str]] = {
    "1": (
        "2026-09-21T16:26:28-03:00 maquina kernel: usb 3-4.3: "
        "device not accepting address 9, error -71",
        "[USB-71]",
    ),
    "2A": (
        "2026-09-22T14:58:40-03:00 maquina bluetoothd[910954]: "
        "profiles/input/device.c:hidp_send_message() BT socket write error: "
        "Resource temporarily unavailable (11)",
        "[BT-SOCKET]",
    ),
    "2B": (
        "2026-09-22T16:46:32-03:00 maquina kernel: playstation "
        "0005:054C:0CE6.000C: Output queue is full",
        "[FILA-CHEIA]",
    ),
    "2-link": (
        "2026-08-15T22:20:42-03:00 maquina kernel: Bluetooth: hci0: link tx timeout",
        "[ENLACE-PARADO]",
    ),
    "2-kill": (
        "2026-08-15T22:20:42-03:00 maquina kernel: Bluetooth: hci0: "
        "killing stalled connection aa:bb:cc:00:00:01",
        "[ENLACE-PARADO]",
    ),
    "3": (
        "2026-09-13T01:13:45-03:00 maquina kernel: Bluetooth: hci0: "
        "command 0xfc61 tx timeout",
        "[BT-TRAVADO]",
    ),
    "3-reg16": (
        "2026-09-13T01:13:45-03:00 maquina kernel: Bluetooth: hci0: RTL: RTL: "
        "Read reg16 failed (-110)",
        "[BT-TRAVADO]",
    ),
    "3-devcoredump": (
        "2026-09-13T01:13:45-03:00 maquina kernel: Bluetooth: hci0: RTL: "
        "Failed to generate devcoredump",
        "[BT-TRAVADO]",
    ),
    "4": (
        "2026-09-22T14:07:19-03:00 maquina kernel: playstation "
        "0005:054C:0CE6.0006: DualSense input CRC's check failed",
        "[CRC]",
    ),
}


def _grep_union() -> str:
    casou = re.search(r'^GREP_UNION="(.+)"$', VIGIA.read_text(encoding="utf-8"), re.M)
    assert casou is not None, "GREP_UNION sumiu do storm_watch.sh"
    return casou.group(1)


_GENERICOS = (
    "bluetooth: hci[0-9].*(timeout|failed|error)",
    "xhci_hcd.*(reset|died|timeout|halt)",
)


def _grep_da_familia() -> str:
    """O ``GREP_UNION`` sem os genéricos — o que cada família escreveu por extenso."""
    filtro = _grep_union()
    for generico in _GENERICOS:
        assert "|" + generico in filtro, f"o genérico {generico!r} mudou de forma"
        filtro = filtro.replace("|" + generico, "")
    return filtro


def _mensagem(linha: str) -> str:
    """O campo MESSAGE, que é o que o ``--grep`` do journalctl filtra."""
    return re.sub(r"^\S+ \S+ [^ ]+: ", "", linha)


def _classificar(texto: str, **env_extra: str) -> str:
    env = {**os.environ, **env_extra}
    resultado = subprocess.run(
        ["bash", str(VIGIA), "--classify"],
        input=texto,
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=30,
    )
    assert resultado.returncode == 0, resultado.stderr
    return resultado.stdout


@pytest.mark.parametrize("familia", sorted(LINHAS_REAIS))
def test_a_linha_real_passa_pelo_filtro_do_journal(familia: str) -> None:
    """ARRANQUE UM PADRÃO DE FAMÍLIA do ``GREP_UNION`` e a família dele reprova"""
    linha, _tag = LINHAS_REAIS[familia]
    assert re.search(_grep_union(), _mensagem(linha), re.IGNORECASE)
    assert re.search(_grep_da_familia(), _mensagem(linha), re.IGNORECASE), (
        f"a família {familia} só passa pelo GREP_UNION por um padrão genérico — "
        "tirar o genérico cegaria a vigia para ela"
    )


@pytest.mark.parametrize("familia", sorted(LINHAS_REAIS))
def test_a_linha_real_recebe_a_tag_da_familia(familia: str) -> None:
    linha, tag = LINHAS_REAIS[familia]
    saida = _classificar(linha + "\n")
    assert saida.split()[1] == tag, f"família {familia}: {saida!r}"


def test_o_bluetoothd_esta_na_fonte_do_vigia() -> None:
    """O 2A é do bluetoothd, não do kernel: a unit tem de estar no journalctl."""
    texto = VIGIA.read_text(encoding="utf-8")
    assert "_SYSTEMD_UNIT=bluetooth.service" in texto


def _rajada(segundos: int, por_segundo: int, dispositivo: str = "0005:054C:0CE6.000C") -> str:
    linhas = []
    for s in range(segundos):
        minuto, segundo = divmod(32 + s, 60)
        ts = f"2026-09-22T16:{46 + minuto:02d}:{segundo:02d}-03:00"
        linhas.extend(
            f"{ts} maquina kernel: playstation {dispositivo}: Output queue is full"
            for _ in range(por_segundo)
        )
    return "\n".join(linhas) + "\n"


def _somar(saida: str) -> int:
    total = 0
    for linha in saida.splitlines():
        casou = re.search(r" (?:repetiu|segue) \+(\d+) ", linha)
        total += int(casou.group(1)) if casou else 1
    return total


def test_o_2b_de_22_09_vira_uma_borda_e_resumos(tmp_path: Path) -> None:
    """81 s a 100 linhas por segundo: a borda, um «segue» por minuto, o fim."""
    saida = _classificar(_rajada(81, 100))
    linhas = saida.splitlines()
    assert len(linhas) <= 4, f"{len(linhas)} linhas para uma rajada só"
    assert linhas[0] == (
        "2026-09-22T16:46:32-03:00 [FILA-CHEIA] playstation 0005:054C:0CE6.000C: "
        "Output queue is full"
    )
    assert any(" segue +" in linha for linha in linhas)
    assert " repetiu +" in linhas[-1]
    assert _somar(saida) == 8100, "a borda e os resumos têm de somar o que o kernel disse"


def test_dois_controles_sao_duas_bordas() -> None:
    texto = _rajada(3, 10) + _rajada(3, 10, "0005:054C:0CE6.000D")
    saida = _classificar(texto)
    bordas = [
        linha for linha in saida.splitlines()
        if " repetiu " not in linha and " segue " not in linha
    ]
    assert len(bordas) == 2, saida


def test_a_rajada_acaba_quando_o_kernel_para_de_repetir() -> None:
    texto = (
        _rajada(2, 5)
        + "2026-09-22T16:50:00-03:00 maquina kernel: playstation "
        "0005:054C:0CE6.000C: Output queue is full\n"
    )
    saida = _classificar(texto).splitlines()
    assert saida[1].startswith("2026-09-22T16:46:33-03:00 [FILA-CHEIA] repetiu +9 ")
    assert saida[2].startswith("2026-09-22T16:50:00-03:00 [FILA-CHEIA] playstation")


def test_o_minus_71_continua_linha_a_linha() -> None:
    """O doctor conta o [USB-71] por porta — ele não vira resumo."""
    linha = LINHAS_REAIS["1"][0]
    saida = _classificar(f"{linha}\n{linha}\n")
    assert saida.count("[USB-71] usb 3-4.3") == 2


def test_a_primeira_volta_do_boot_rele_o_arranque(tmp_path: Path) -> None:
    """O -71 da enumeração nasce antes da vigia: a primeira volta relê o boot."""
    marca = tmp_path / "kernel-watch.boot"

    def desde(boot: str) -> list[str]:
        resultado = subprocess.run(
            ["bash", str(VIGIA), "--test-desde", str(marca), boot],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        return resultado.stdout.split()

    assert desde("boot-a") == ["-b", "--lines=all"]
    assert desde("boot-a") == ["-n0"], "a unit re-tentou no mesmo boot: não relê"
    assert desde("boot-b") == ["-b", "--lines=all"], "boot novo relê de novo"


def _kernel_log_de_mentira() -> str:
    """O que a vigia escreve para a semana de 13/09 a 22/09, pela própria vigia."""
    entrada = "".join(linha + "\n" for linha, _tag in LINHAS_REAIS.values())
    entrada += _rajada(81, 100)
    return _classificar(entrada)


def test_o_storm_doctor_separa_as_quatro_familias() -> None:
    historico = storm_doctor.classificar_o_historico(_kernel_log_de_mentira().splitlines())
    assert set(historico) == {"1", "2", "2A", "2B", "3", "4"}
    assert historico["2B"].ocorrencias == 8101
    assert historico["2B"].rajadas == 1
    assert historico["3"].rajadas == 1
    assert historico["3"].ocorrencias == 3
    assert historico["2A"].nome == "rádio afogado"
    assert historico["1"].primeira.startswith("2026-09-21")


def test_o_storm_doctor_le_o_kernel_log_do_lar(tmp_path: Path) -> None:
    log = tmp_path / "kernel.log"
    log.write_text(
        "# 2026-09-22 16:00:00 kernel-watch iniciado (banner)\n"
        + _kernel_log_de_mentira(),
        encoding="utf-8",
    )
    assert storm_doctor.historico_do_radio(log)["2A"].rajadas == 1
    assert storm_doctor.historico_do_radio(tmp_path / "nao-existe.log") == {}


def test_cada_queda_diz_o_fato_das_pontes(tmp_path: Path) -> None:
    """A queda de 22/09 14:58:40 com quatro pontes de som num adaptador só."""
    eventos = storm_doctor.ler_eventos_do_radio(_kernel_log_de_mentira().splitlines())
    [queda] = storm_doctor.quedas(eventos)
    alvo = tmp_path / "radio-diario.jsonl"
    for n in range(1, 5):
        diario.registrar(
            "governador", diario.PONTE_SUBIU, "alguém tocou som",
            caminho=alvo, agora=queda.carimbo - 30 + n,
            controle=f"aa:bb:cc:00:00:0{n}", adaptador="AA:BB:CC:00:00:CE", tipo="som",
        )
    entradas = diario.ler(caminhos=[alvo])
    assert storm_doctor.o_fato_da_queda(queda, entradas) == "4 controles com som (limite 2)"
    assert storm_doctor.o_fato_da_queda(queda, []) is None


BANNER_DE_20_07 = (
    "# 2026-07-20 14:03:11 kernel-watch iniciado (padrões: USB-71 JOYCON BT-HCI "
    "XHCI + contadores hci; preventivos ficam silenciosos até a 1ª ocorrência)"
)
BANNER_DAS_FAMILIAS = (
    "# 2026-09-23 03:00:00 kernel-watch iniciado (padrões: USB-71 JOYCON JOYCON-PROBE "
    "FILA-CHEIA BT-SOCKET ENLACE-PARADO BT-TRAVADO CRC BT-HCI XHCI + contadores hci; "
    "preventivos ficam silenciosos até a 1ª ocorrência; rajada vira borda + resumo)"
)


def test_nao_olhei_nao_e_zero() -> None:
    """A R2 dela: *«tiveram storm nos dias anteriores»*."""
    laco = "2026-09-13T01:14:00-03:00 [BT-HCI] Bluetooth: hci0: command 0xfc61 tx timeout"
    antes = storm_doctor.classificar_o_historico([BANNER_DE_20_07, laco])
    assert set(antes) == {"1", "2", "3"}, "a fila cheia, o EAGAIN e o CRC não eram medidos"
    assert antes["3"].medida_desde == "2026-07-20T14:03:11"
    assert (antes["1"].rajadas, antes["1"].medida_desde) == (0, "2026-07-20T14:03:11")

    depois = storm_doctor.classificar_o_historico([BANNER_DE_20_07, laco, BANNER_DAS_FAMILIAS])
    assert set(depois) == {"1", "2", "2A", "2B", "3", "4"}
    assert (depois["2B"].rajadas, depois["2B"].medida_desde) == (0, "2026-09-23T03:00:00")
    assert depois["3"].rajadas == 1


def test_o_banner_da_vigia_de_hoje_diz_as_seis_familias() -> None:
    """O ``medida_desde`` lê o banner que o ``storm_watch.sh`` escreve."""
    casou = re.search(
        r'^echo "# \$\(date \'\+%F %T\'\) (kernel-watch iniciado \(padrões: [^"]+)" >>',
        VIGIA.read_text(encoding="utf-8"),
        re.M,
    )
    assert casou is not None, "o banner do kernel-watch mudou de forma"
    banner = f"# 2026-09-23 03:00:00 {casou.group(1)}"
    assert set(storm_doctor.classificar_o_historico([banner])) == {
        "1", "2", "2A", "2B", "3", "4",
    }


def test_a_queda_e_a_borda_e_nao_o_resumo() -> None:
    """Os controles levam EAGAIN no mesmo segundo: é UMA queda, não duas."""
    linha = LINHAS_REAIS["2A"][0]
    seguinte = linha.replace("14:58:40", "14:58:41")
    eventos = storm_doctor.ler_eventos_do_radio(
        _classificar(f"{linha}\n{linha}\n{seguinte}\n").splitlines()
    )
    assert [e.borda for e in eventos] == [True, False], eventos
    assert sum(e.ocorrencias for e in eventos) == 3
    assert len(storm_doctor.quedas(eventos)) == 1


def test_o_fato_nao_usa_palavra_proibida_na_tela() -> None:
    """Regra 8 da leva: nunca a palavra «fatia» na tela."""
    texto = (RAIZ / "src/hefesto_dualsense4unix/integrations/storm_doctor.py").read_text(
        encoding="utf-8"
    )
    assert "fatia" not in texto.lower()
    assert all("fatia" not in nome for _f, nome in storm_doctor.FAMILIAS_DO_RADIO.values())


def test_o_log_de_antes_das_familias_tambem_conta(tmp_path: Path) -> None:
    """A R2 dela: *«tiveram storm nos dias anteriores»*."""
    velho = []
    for s in range(0, 30, 3):
        ts = f"2026-09-13T01:14:{s:02d}-03:00"
        velho += [
            f"{ts} [BT-HCI] Bluetooth: hci0: command 0xfc61 tx timeout",
            f"{ts} [BT-HCI] Bluetooth: hci0: RTL: RTL: Read reg16 failed (-110)",
            f"{ts} [BT-HCI] Bluetooth: hci0: RTL: Failed to generate devcoredump",
        ]
    velho += [
        "2026-09-13T18:29:13-03:00 [BT-HCI] Bluetooth: hci0: command 0xfc61 tx timeout",
        "2026-08-15T22:20:42-03:00 [BT-HCI] Bluetooth: hci0: link tx timeout",
        "2026-08-01T10:00:00-03:00 [BT-HCI] Bluetooth: hci0: Opcode 0x080f failed: -22",
    ]
    historico = storm_doctor.classificar_o_historico(velho)
    assert historico["3"].ocorrencias == 31
    assert historico["3"].rajadas == 2, "o laço contínuo é UMA rajada; 18:29 é outra"
    assert historico["2"].rajadas == 1
    assert set(historico) == {"2", "3"}, "o Opcode failed não é de família nenhuma"
