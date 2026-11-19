"""O grub recebe os parâmetros dentro do valor que já estava lá.

O-GRUB-RECEBE-OS-PARAMETROS-DENTRO-DO-VALOR-01 (19/11/2026). ``kernel_cmdline`` lê a
``GRUB_CMDLINE_LINUX_DEFAULT`` como o shell lê (``export`` opcional, aspas, comentário) e
reescreve só o valor. O juiz é o próprio ``bash``: o arquivo gravado passa no ``bash -n`` e o
``source`` dele traz os parâmetros de quem usa e os dois da casa. Nada roda no carregador de boot:
o ``which`` não acha gerador e o ``rodar`` é de mentira.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import kernel_cmdline as kc

BASH = shutil.which("bash") or "/bin/bash"
DOCTOR = Path(__file__).resolve().parents[2] / "scripts" / "doctor.sh"
CASA = ["usbcore.autosuspend=-1", "usbcore.quirks=054c:0ce6:gn"]
FORMAS = {
    "simples": ('GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"\n', "quiet splash"),
    "sem aspas": ("GRUB_CMDLINE_LINUX_DEFAULT=quiet\n", "quiet"),
    "comentario": ('GRUB_CMDLINE_LINUX_DEFAULT="quiet splash" # padrão\n', "quiet splash"),
    "export": ('  export GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"\n', "quiet splash"),
    "aspas escapadas": ('GRUB_CMDLINE_LINUX_DEFAULT="quiet acpi_osi=\\"Windows 2015\\""\n',
                        'quiet acpi_osi="Windows 2015"'),
}


def _lugares(tmp_path: Path, texto: str) -> kc.Lugares:
    grub = tmp_path / "grub"
    grub.write_text('GRUB_TIMEOUT=5\n' + texto, encoding="utf-8")
    return kc.Lugares(kernelstub=tmp_path / "sem-kernelstub", grub=grub,
                      kernel_cmdline=tmp_path / "sem-cmdline", raiz=tmp_path)


def _o_shell_le(arquivo: Path) -> tuple[int, str]:
    sintaxe = subprocess.run([BASH, "-n", str(arquivo)], capture_output=True, check=False)
    lido = subprocess.run(
        [BASH, "-c", f'source "{arquivo}"; printf "%s" "$GRUB_CMDLINE_LINUX_DEFAULT"'],
        capture_output=True, text=True, check=False,
    )
    return sintaxe.returncode, lido.stdout


@pytest.mark.parametrize("forma", list(FORMAS))
def test_os_dois_da_casa_entram_no_valor_de_quem_usa(tmp_path: Path, forma: str) -> None:
    """D-1911-O-GRUB-MUDA-SO-O-VALOR-DA-LINHA: prefixo, comentário e parâmetros ficam."""
    texto, de_quem_usa = FORMAS[forma]
    lugares = _lugares(tmp_path, texto)
    carregador = kc.ler_o_carregador(lugares, which=lambda _nome: None)
    assert " ".join(carregador.tokens) == de_quem_usa
    escrita = kc.escrever(carregador, [], CASA, lugares, which=lambda _nome: None,
                          rodar=lambda _comando: 0)
    assert escrita.falhas == ()
    assert _o_shell_le(lugares.grub) == (0, " ".join([de_quem_usa, *CASA]))
    gravado = lugares.grub.read_text(encoding="utf-8")
    assert gravado.count("GRUB_CMDLINE_LINUX_DEFAULT=") == 1
    assert ("# padrão" in gravado) == (forma == "comentario")
    assert ("  export " in gravado) == (forma == "export")


@pytest.mark.parametrize("linha", [
    'GRUB_CMDLINE_LINUX_DEFAULT="$GRUB_CMDLINE_LINUX_DEFAULT quiet"\n',
    'GRUB_CMDLINE_LINUX_DEFAULT="quiet splash\n',
    "GRUB_CMDLINE_LINUX_DEFAULT=quiet splash\n",
    'GRUB_CMDLINE_LINUX_DEFAULT="quiet splash";\n',
])
def test_a_forma_que_nao_se_entende_e_recusa_sem_gravar(
    tmp_path: Path, linha: str, capsys: pytest.CaptureFixture[str]
) -> None:
    lugares = _lugares(tmp_path, linha)
    antes = lugares.grub.read_text(encoding="utf-8")
    carregador = kc.Carregador(kc.BACKEND_GRUB, ("quiet",), str(lugares.grub))
    with pytest.raises(ValueError, match=re.escape(linha.strip())):
        kc.escrever(carregador, [], CASA, lugares, which=lambda _nome: None,
                    rodar=lambda _comando: 0)
    assert lugares.grub.read_text(encoding="utf-8") == antes
    rc = kc.main(["ler", "--grub-conf", str(lugares.grub),
                  "--kernelstub-conf", str(lugares.kernelstub),
                  "--kernel-cmdline", str(lugares.kernel_cmdline)])
    saida = capsys.readouterr().out
    assert rc == 2 and saida.startswith("falhou\t") and linha.strip() in saida, saida
    nada = str(tmp_path / "nao-ha")
    doctor = subprocess.run(
        [BASH, "-c", f'source "{DOCTOR}"; QUIET=0; check_cmdline_platform'],
        capture_output=True, text=True, timeout=60, check=False,
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "HEFESTO_DOCTOR_SYS": nada,
             "HEFESTO_DOCTOR_CMDLINE": nada, "HEFESTO_DOCTOR_KERNELSTUB": nada,
             "HEFESTO_DOCTOR_GRUB": str(lugares.grub), "HEFESTO_DOCTOR_KERNEL_CMDLINE": nada},
    ).stdout
    assert "install.sh" not in doctor and doctor.count(linha.strip()) == 2, doctor
    assert "ponha à mão no cmdline do kernel usbcore.quirks=054c:0ce6:gn" in doctor, doctor
