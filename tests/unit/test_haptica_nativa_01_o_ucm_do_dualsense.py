"""HAPTICA-NATIVA-01 — o perfil UCM do DualSense entra sem tocar o pacote.

O GE-Proton manda a vibração dos jogos da Sony pelo sink `…HiFi__Speaker__sink`,
e esse nome só existe com a placa do controle aberta por UCM. O `alsa-ucm-conf`
do Ubuntu 24.04 não conhece o DualSense. O `scripts/install_ucm_dualsense.sh`
grava o verbo em `USB-Audio/Hefesto/` e um gancho em `conf.d/USB-Audio/<nome
longo da placa>.conf`, que o `ucm.conf` procura ANTES do `USB-Audio.conf`.

MEDIDO em 18/09/2026, com o pacote intacto (`dpkg -V alsa-ucm-conf` limpo):
sem o gancho, `alsaucm -c hw:2 list _verbs` diz *"UCM is not supported for this
USB device"*; com ele, responde `HiFi` com `Speaker` e `Mic`.

O nome longo sai do kernel cortado em 79 caracteres, e o que estas réguas
travam é a conta desse corte: errar um caractere faz o arquivo existir e nunca
ser lido. Tudo roda num sysfs e numa árvore UCM de mentira.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
ROTEIRO = RAIZ / "scripts" / "install_ucm_dualsense.sh"
ASSETS = RAIZ / "assets" / "ucm"

#: O nome longo da placa do DualSense da bancada, lido em /proc/asound/cards
#: em 18/09/2026 — o controlador USB é `0000:0c:00.3`.
NOME_MEDIDO = "Sony Interactive Entertainment DualSense Wireless Controller at usb-0000:0c:00."

PADRAO = f"{NOME_MEDIDO}.conf"
EDGE_PCI = "Sony Interactive Entertainment DualSense Edge Wireless Controller at usb-0000:0.conf"
PADRAO_VHCI = "Sony Interactive Entertainment DualSense Wireless Controller at usb-vhci_hcd.0-.conf"
EDGE_VHCI = "Sony Interactive Entertainment DualSense Edge Wireless Controller at usb-vhci_h.conf"


def _sysfs(raiz: Path, controladores: dict[str, list[str]]) -> Path:
    """`/sys/bus/usb/devices/usbN` apontando para o controlador, como no kernel."""
    sysfs = raiz / "sys"
    barramento = sysfs / "bus" / "usb" / "devices"
    barramento.mkdir(parents=True)
    for caminho, hubs in controladores.items():
        for hub in hubs:
            alvo = sysfs / "devices" / caminho / hub
            alvo.mkdir(parents=True)
            (barramento / hub).symlink_to(os.path.relpath(alvo, barramento))
    return sysfs


def _arvore_ucm(raiz: Path, *, com_confd: bool = True) -> Path:
    ucm = raiz / "ucm2"
    (ucm / "conf.d" / "USB-Audio").mkdir(parents=True)
    texto = "Syntax 4\n"
    if com_confd:
        texto = 'UseCasePath.confd1 {\n\tDirectory "conf.d/${var:Driver}"\n}\n'
    (ucm / "ucm.conf").write_text(texto, encoding="utf-8")
    alheio = ucm / "conf.d" / "USB-Audio" / "Alheio de outra placa.conf"
    alheio.write_text("Syntax 6\n", encoding="utf-8")
    return ucm


def _mesa(tmp_path: Path) -> tuple[Path, Path]:
    sysfs = _sysfs(
        tmp_path,
        {
            "pci0000:00/0000:00:01.2/0000:02:00.0": ["usb1", "usb2"],
            "pci0000:00/0000:00:08.1/0000:0c:00.3": ["usb3", "usb4"],
            "platform/vhci_hcd.0": ["usb5", "usb6"],
            "platform/abc": ["usb7"],
        },
    )
    return sysfs, _arvore_ucm(tmp_path)


def _rodar(ucm: Path, sysfs: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(ROTEIRO), "--raiz-ucm", str(ucm), "--sysfs", str(sysfs), *extra],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _ganchos(ucm: Path) -> set[str]:
    return {p.name for p in (ucm / "conf.d" / "USB-Audio").iterdir()}


def test_o_nome_medido_tem_o_corte_do_kernel() -> None:
    assert len(NOME_MEDIDO) == 79


def test_um_gancho_por_controlador_e_modelo(tmp_path: Path) -> None:
    sysfs, ucm = _mesa(tmp_path)
    r = _rodar(ucm, sysfs)
    assert r.returncode == 0, r.stderr
    assert _ganchos(ucm) == {
        "Alheio de outra placa.conf",
        "Sony Interactive Entertainment DualSense Wireless Controller at usb-0000:02:00..conf",
        PADRAO,
        EDGE_PCI,
        PADRAO_VHCI,
        EDGE_VHCI,
    }
    gancho = (ASSETS / "DualSense-gancho.conf").read_bytes()
    assert (ucm / "conf.d" / "USB-Audio" / PADRAO).read_bytes() == gancho


def test_o_controlador_de_nome_curto_fica_de_fora_e_e_nomeado(tmp_path: Path) -> None:
    sysfs, ucm = _mesa(tmp_path)
    r = _rodar(ucm, sysfs)
    assert not any("usb-abc" in nome for nome in _ganchos(ucm))
    assert "controlador abc" in r.stderr


def test_o_gancho_aponta_para_o_verbo_que_o_roteiro_grava(tmp_path: Path) -> None:
    sysfs, ucm = _mesa(tmp_path)
    _rodar(ucm, sysfs)
    gancho = (ASSETS / "DualSense-gancho.conf").read_text(encoding="utf-8")
    assert 'File "/USB-Audio/Hefesto/DualSense-HiFi.conf"' in gancho
    verbo = ucm / "USB-Audio" / "Hefesto" / "DualSense-HiFi.conf"
    assert verbo.read_bytes() == (ASSETS / "DualSense-HiFi.conf").read_bytes()


def test_o_verbo_da_quatro_canais_ao_speaker() -> None:
    """`Speaker` é o que vira `HiFi__Speaker__sink`; os canais 3 e 4 são os motores."""
    verbo = (ASSETS / "DualSense-HiFi.conf").read_text(encoding="utf-8")
    assert 'SectionDevice."Speaker"' in verbo
    assert "PlaybackChannels 4" in verbo
    assert 'SectionUseCase."HiFi"' in (ASSETS / "DualSense-gancho.conf").read_text(encoding="utf-8")


def test_idempotente(tmp_path: Path) -> None:
    sysfs, ucm = _mesa(tmp_path)
    _rodar(ucm, sysfs)
    alvo = ucm / "conf.d" / "USB-Audio" / PADRAO
    antes = alvo.stat().st_mtime_ns
    r = _rodar(ucm, sysfs)
    assert "(0 novo(s))" in r.stdout
    assert alvo.stat().st_mtime_ns == antes


def test_o_controlador_que_saiu_leva_o_gancho_e_o_alheio_fica(tmp_path: Path) -> None:
    sysfs, ucm = _mesa(tmp_path)
    _rodar(ucm, sysfs)
    for hub in ("usb5", "usb6"):
        (sysfs / "bus" / "usb" / "devices" / hub).unlink()
    _rodar(ucm, sysfs)
    nomes = _ganchos(ucm)
    assert PADRAO_VHCI not in nomes and EDGE_VHCI not in nomes
    assert PADRAO in nomes
    assert "Alheio de outra placa.conf" in nomes


def test_remover_tira_so_o_que_e_nosso(tmp_path: Path) -> None:
    sysfs, ucm = _mesa(tmp_path)
    _rodar(ucm, sysfs)
    r = _rodar(ucm, sysfs, "--remover")
    assert r.returncode == 0, r.stderr
    assert _ganchos(ucm) == {"Alheio de outra placa.conf"}
    assert not (ucm / "USB-Audio" / "Hefesto").exists()


def test_status_so_le(tmp_path: Path) -> None:
    sysfs, ucm = _mesa(tmp_path)
    assert _rodar(ucm, sysfs, "--status").returncode == 1
    assert _ganchos(ucm) == {"Alheio de outra placa.conf"}
    _rodar(ucm, sysfs)
    assert _rodar(ucm, sysfs, "--status").returncode == 0


def test_sem_ucm_ou_sem_conf_d_nada_e_gravado(tmp_path: Path) -> None:
    sysfs, _ = _mesa(tmp_path)
    vazio = tmp_path / "sem-ucm"
    vazio.mkdir()
    assert _rodar(vazio, sysfs).returncode == 0
    assert not any(vazio.rglob("*.conf"))

    velho = _arvore_ucm(tmp_path / "velho", com_confd=False)
    assert _rodar(velho, sysfs).returncode == 0
    assert _ganchos(velho) == {"Alheio de outra placa.conf"}


def test_o_uninstall_chama_o_mesmo_dono() -> None:
    texto = (RAIZ / "uninstall.sh").read_text(encoding="utf-8")
    assert 'install_ucm_dualsense.sh" --remover' in texto


# --- o doctor e o boot do daemon fazem a mesma pergunta -------------------


def _cards(raiz: Path, *nomes_longos: str) -> Path:
    """`/proc/asound/cards` no formato do kernel: o nome longo na 2ª linha."""
    linhas = [" 0 [Generic        ]: HDA-Intel - HD-Audio Generic",
              "                      HD-Audio Generic at 0xfc400000 irq 85"]
    for i, nome in enumerate(nomes_longos, start=2):
        linhas.append(f" {i} [Controller     ]: USB-Audio - DualSense Wireless Controller")
        linhas.append(f"                      {nome}")
    arq = raiz / "cards"
    arq.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return arq


def _doctor(ucm: Path, cards: Path, sinks: str, tmp_path: Path) -> str:
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    pactl = bindir / "pactl"
    pactl.write_text(f"#!/bin/sh\ncat <<'FIM'\n{sinks}\nFIM\n", encoding="utf-8")
    pactl.chmod(0o755)
    r = subprocess.run(
        ["bash", "-c", f'source "{RAIZ}/scripts/doctor.sh"; check_ucm_do_dualsense'],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={
            "PATH": f"{bindir}:/usr/bin:/bin",
            "HOME": str(tmp_path),
            "HEFESTO_RAIZ_UCM": str(ucm),
            "HEFESTO_PROC_CARDS": str(cards),
        },
    )
    return r.stdout + r.stderr


_NO = "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller-00"
SINK_HIFI = f"4298\t{_NO}.HiFi__Speaker__sink\tPipeWire\ts16le 4ch 48000Hz\tRUNNING"
SINK_ACP = f"4298\t{_NO}.analog-surround-40\tPipeWire\ts16le 4ch 48000Hz\tRUNNING"


def test_doctor_acusa_a_placa_sem_gancho(tmp_path: Path) -> None:
    ucm = _arvore_ucm(tmp_path)
    saida = _doctor(ucm, _cards(tmp_path, NOME_MEDIDO), SINK_ACP, tmp_path)
    assert "[WARN] DualSense no cabo sem o perfil UCM" in saida
    assert "install_ucm_dualsense.sh" in saida


def test_doctor_acusa_o_gancho_que_ainda_nao_valeu(tmp_path: Path) -> None:
    sysfs, ucm = _mesa(tmp_path)
    _rodar(ucm, sysfs)
    saida = _doctor(ucm, _cards(tmp_path, NOME_MEDIDO), SINK_ACP, tmp_path)
    assert "[WARN] o gancho UCM existe, mas 1 placa(s)" in saida


def test_doctor_passa_com_o_sink_da_vibracao(tmp_path: Path) -> None:
    sysfs, ucm = _mesa(tmp_path)
    _rodar(ucm, sysfs)
    saida = _doctor(ucm, _cards(tmp_path, NOME_MEDIDO), SINK_HIFI, tmp_path)
    assert "[ OK ] perfil UCM do DualSense armado (1 placa(s) no cabo)" in saida
    assert "[WARN]" not in saida


def test_doctor_calado_sem_dualsense_no_cabo(tmp_path: Path) -> None:
    ucm = _arvore_ucm(tmp_path)
    saida = _doctor(ucm, _cards(tmp_path), "", tmp_path)
    assert "[WARN]" not in saida
    assert "nenhum DualSense no cabo" in saida


def test_o_boot_do_daemon_avisa_a_placa_sem_gancho(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hefesto_dualsense4unix.core import system_check as sc

    sysfs, ucm = _mesa(tmp_path)
    monkeypatch.setattr(sc, "_RAIZ_UCM", str(ucm))
    monkeypatch.setattr(sc, "_PROC_CARDS", str(_cards(tmp_path, NOME_MEDIDO)))
    monkeypatch.setattr(sc, "_UDEV_RULES", ())
    monkeypatch.setenv("HOME", str(tmp_path))
    assert sc._dualsenses_no_cabo_sem_ucm() == [NOME_MEDIDO]
    assert any("perfil UCM" in aviso for aviso in sc.system_warnings())

    _rodar(ucm, sysfs)
    assert sc._dualsenses_no_cabo_sem_ucm() == []
    assert sc.system_warnings() == []


def test_o_boot_do_daemon_calado_sem_ucm_conf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hefesto_dualsense4unix.core import system_check as sc

    monkeypatch.setattr(sc, "_RAIZ_UCM", str(tmp_path / "sem-ucm"))
    monkeypatch.setattr(sc, "_PROC_CARDS", str(_cards(tmp_path, NOME_MEDIDO)))
    assert sc._dualsenses_no_cabo_sem_ucm() == []


def test_o_doctor_roda_a_checagem() -> None:
    """A função existir não basta: ela tem de estar no `main()` do doctor."""
    texto = (RAIZ / "scripts" / "doctor.sh").read_text(encoding="utf-8")
    corpo = texto[texto.index("\nmain() {") :]
    corpo = corpo[: corpo.index("\n}\n")]
    assert "\n    check_ucm_do_dualsense\n" in corpo
