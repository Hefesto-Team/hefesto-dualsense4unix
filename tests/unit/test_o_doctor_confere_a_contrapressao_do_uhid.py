"""O doctor sabe dizer se a contrapressão do uhid, quando pedida, está de pé."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"
KERNEL = "7.2.11-arch1-1"


def _doctor(
    tmp_path: Path,
    *,
    pedido: bool,
    param: str | None,
    instalado: bool = False,
    veredito: tuple[str, str] | None = None,
) -> str:
    conf = tmp_path / "hefesto-uhid.conf"
    if pedido:
        conf.write_text("options uhid backpressure=1\n", encoding="utf-8")
    parametro = tmp_path / "backpressure"
    if param is not None:
        parametro.write_text(param + "\n", encoding="utf-8")
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    arquivo = (
        "/lib/modules/k/updates/dkms/uhid.ko.zst"
        if instalado
        else "/lib/modules/k/kernel/drivers/hid/uhid.ko.zst"
    )
    (bin_ / "modinfo").write_text(f'#!/bin/sh\necho "{arquivo}"\n', encoding="utf-8")
    (bin_ / "modinfo").chmod(0o755)
    arvore = tmp_path / "arvore-do-dkms"
    if veredito is not None:
        pasta = arvore / "hefesto-uhid" / "1.0.0"
        pasta.mkdir(parents=True)
        (pasta / f"fonte-{KERNEL}.txt").write_text("\n".join(veredito) + "\n", encoding="utf-8")
    r = subprocess.run(
        [BASH, "-c", f'source "{DOCTOR}"; check_uhid_contrapressao'],
        env={
            "PATH": f"{bin_}:/usr/bin:/bin",
            "HOME": str(tmp_path),
            "HEFESTO_DOCTOR_UHID_CONF": str(conf),
            "HEFESTO_DOCTOR_UHID_PARAM": str(parametro),
            "HEFESTO_DOCTOR_KERNEL": KERNEL,
            "HEFESTO_DKMS_TREE": str(arvore),
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return r.stdout + r.stderr


def test_sem_o_pedido_nao_ha_o_que_conferir(tmp_path: Path) -> None:
    assert _doctor(tmp_path, pedido=False, param="1").strip() == ""


def test_pedida_e_ligada_passa(tmp_path: Path) -> None:
    saida = _doctor(tmp_path, pedido=True, param="1")
    assert "[ OK ] contrapressão do uhid ligada" in saida, saida


def test_pedida_e_desligada_a_quente_avisa_com_o_gesto(tmp_path: Path) -> None:
    saida = _doctor(tmp_path, pedido=True, param="0")
    assert "[WARN]" in saida and "DESLIGADA" in saida and "sudo tee" in saida, saida


def test_o_do_hefesto_instalado_entra_no_proximo_boot(tmp_path: Path) -> None:
    saida = _doctor(tmp_path, pedido=True, param=None, instalado=True)
    assert "PRÓXIMO BOOT" in saida and "[WARN]" not in saida, saida


def test_o_motivo_do_pre_build_diz_por_que_o_pedido_nao_vale(tmp_path: Path) -> None:
    frase = "hefesto-uhid: nenhuma série guardada aplica no de fábrica de 7.2.11-arch1-1"
    saida = _doctor(tmp_path, pedido=True, param=None, veredito=("nao-aplica", frase))
    assert "[WARN]" in saida and frase in saida, saida
    assert "PRÓXIMO BOOT" not in saida, saida


def test_sem_o_do_hefesto_manda_instalar(tmp_path: Path) -> None:
    saida = _doctor(tmp_path, pedido=True, param=None)
    assert f"não está instalado para o kernel {KERNEL}" in saida, saida
    assert "PRÓXIMO BOOT" not in saida, saida


def test_o_main_pergunta() -> None:
    assert "\n    check_uhid_contrapressao\n" in DOCTOR.read_text(encoding="utf-8")
