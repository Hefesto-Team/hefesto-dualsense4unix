"""O Flatpak, o install-host-udev e o .deb leem a lista de módulos do dono, que tem cinco."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
DKMS = RAIZ / "assets" / "dkms"
FLATPAK = RAIZ / "flatpak" / "io.github.hefesto_team.hefesto_dualsense4unix.yml"
HOST_UDEV = RAIZ / "scripts" / "install-host-udev.sh"
POSTINST = RAIZ / "packaging" / "debian" / "postinst"
CINCO = {"hid-nintendo", "hid-playstation", "rtw88-usb", "uhid", "usb-f-hid"}


def _campo(conf: Path, campo: str) -> str:
    achado = re.search(rf'^{re.escape(campo)}="(.*)"$', conf.read_text(encoding="utf-8"), re.M)
    assert achado, (conf, campo)
    return achado.group(1)


def _dono(raiz: Path = DKMS) -> dict[str, tuple[str, str]]:
    return {
        conf.parent.name: (_campo(conf, "PACKAGE_NAME"), _campo(conf, "BUILT_MODULE_NAME[0]"))
        for conf in sorted(raiz.glob("*/dkms.conf"))
    }


def _comando_do_flatpak() -> str:
    manifesto = yaml.safe_load(FLATPAK.read_text(encoding="utf-8"))
    comandos = [c for m in manifesto["modules"] for c in m.get("build-commands", [])]
    achados = [c for c in comandos if "dkms.conf" in c]
    assert len(achados) == 1, "o Flatpak copia as fontes DKMS por um laço sobre o dono"
    return achados[0]


def _roda_o_comando(comando: str, trabalho: Path, destino: Path) -> set[str]:
    destino.mkdir(parents=True)
    corpo = comando.replace("/app/share/hefesto-dualsense4unix/dkms/", f"{destino}/")
    subprocess.run(["sh", "-eu", "-c", corpo], cwd=trabalho, check=True, timeout=60)
    return {p.name for p in destino.iterdir() if (p / "dkms.conf").is_file()}


def test_o_dono_tem_os_cinco_modulos() -> None:
    assert set(_dono()) == CINCO


def test_o_flatpak_leva_todo_modulo_do_dono(tmp_path: Path) -> None:
    """D-0811-O-FLATPAK-E-O-DEB-LEVAM-OS-CINCO-MODULOS: o laço do manifesto cobre o dono."""
    levados = _roda_o_comando(_comando_do_flatpak(), RAIZ, tmp_path / "saida")
    assert levados == set(_dono()), levados
    assert "uhid" in levados


def test_o_flatpak_acompanha_uma_pasta_nova_do_dono(tmp_path: Path) -> None:
    trabalho = tmp_path / "arvore"
    shutil.copytree(DKMS, trabalho / "assets" / "dkms")
    novo = trabalho / "assets" / "dkms" / "novo-modulo"
    novo.mkdir()
    (novo / "dkms.conf").write_text('PACKAGE_NAME="hefesto-novo"\n', encoding="utf-8")
    levados = _roda_o_comando(_comando_do_flatpak(), trabalho, tmp_path / "saida")
    assert levados == CINCO | {"novo-modulo"}


def test_a_lista_a_mao_deixaria_o_uhid_de_fora(tmp_path: Path) -> None:
    """A MORDIDA: a lista de quatro, como o manifesto tinha, não bate com o dono."""
    a_mao = "; ".join(
        f"cp -a assets/dkms/{m} /app/share/hefesto-dualsense4unix/dkms/"
        for m in ("hid-nintendo", "hid-playstation", "usb-f-hid", "rtw88-usb")
    )
    levados = _roda_o_comando(a_mao, RAIZ, tmp_path / "saida")
    assert levados != set(_dono())
    assert set(_dono()) - levados == {"uhid"}


def _funcoes_do_host_udev() -> str:
    texto = HOST_UDEV.read_text(encoding="utf-8")
    inicio = texto.index("_depois_do_usb_f_hid() {")
    fim = texto.index('if [[ -n "${DKMS_DIR}" && -n "${DKMS_LIB_SH}" ]]; then')
    return texto[inicio:fim]


def _instala_pelo_host_udev(
    dkms_dir: Path, tmp_path: Path, *, opt_in: bool = True
) -> list[str]:
    registro = tmp_path / "chamadas.log"
    script = "\n".join(
        (
            "set -eu",
            f"export COM_UHID_CONTRAPRESSAO={int(opt_in)}",
            f"export HEFESTO_UHID_CONF='{tmp_path}/nao-existe.conf'",
            "sudo() { :; }",
            f'dkms_install_patched_module() {{ echo "$1 $2 $4" >> "{registro}"; }}',
            "dkms_module_from_updates() { return 0; }",
            "dkms_usb_f_hid_marcas_que_faltam() { :; }",
            _funcoes_do_host_udev(),
            f"DKMS_DIR='{dkms_dir}'",
            "_dkms_do_dono",
        )
    )
    feito = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, check=False, timeout=60
    )
    assert feito.returncode == 0, feito.stderr
    return registro.read_text(encoding="utf-8").splitlines() if registro.exists() else []


def test_o_install_host_udev_instala_todo_modulo_do_dono(tmp_path: Path) -> None:
    """D-0811-O-FLATPAK-E-O-DEB-LEVAM-OS-CINCO-MODULOS: o passo instala cada módulo do dono."""
    chamadas = _instala_pelo_host_udev(DKMS, tmp_path)
    esperado = sorted(f"{pacote} 1.0.0 {modulo}" for pacote, modulo in _dono().values())
    assert sorted(chamadas) == esperado, chamadas
    assert any(c.endswith(" uhid") for c in chamadas)


def test_o_install_host_udev_sem_o_uhid_no_dono_nao_o_instala(tmp_path: Path) -> None:
    """A MORDIDA: a lista vem do dono, e não do script."""
    copia = tmp_path / "dkms"
    shutil.copytree(DKMS, copia)
    shutil.rmtree(copia / "uhid")
    chamadas = _instala_pelo_host_udev(copia, tmp_path)
    assert len(chamadas) == 4
    assert not any(c.endswith(" uhid") for c in chamadas)


def test_o_script_nao_nomeia_modulo_a_mao() -> None:
    texto = HOST_UDEV.read_text(encoding="utf-8")
    a_mao = re.findall(r"dkms_install_patched_module hefesto-[\w-]+", texto)
    assert not a_mao, a_mao
    assert "compgen -G" in texto and "/*/dkms.conf" in texto


def test_o_deb_diz_os_modulos_que_o_dono_tem(tmp_path: Path) -> None:
    texto = POSTINST.read_text(encoding="utf-8")
    linhas = texto.splitlines()
    inicio = next(i for i, ln in enumerate(linhas) if ln.strip().startswith('_modulos="$(sed'))
    comando = "\n".join(linhas[inicio : inicio + 2])
    base = tmp_path / "usr" / "share" / "hefesto-dualsense4unix" / "dkms"
    shutil.copytree(DKMS, base)
    comando = comando.replace("/usr/share/hefesto-dualsense4unix/dkms", str(base))
    feito = subprocess.run(
        ["bash", "-c", f'set -e\n{comando}\necho "${{_modulos}}"'],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert feito.returncode == 0, feito.stderr
    nomes = {_dono()[p][1] for p in _dono()}
    assert set(feito.stdout.split()) == nomes
    assert "uhid" in feito.stdout.split()


@pytest.mark.parametrize("nome", sorted(m for _, m in _dono().values()))
def test_o_deb_nao_lista_modulo_a_mao(nome: str) -> None:
    texto = POSTINST.read_text(encoding="utf-8")
    assert nome not in texto, f"{nome} escrito à mão no postinst: a lista é do dono"


def test_o_uhid_e_opt_in_no_install_host_udev(tmp_path: Path) -> None:
    """D-0811-O-FLATPAK-E-O-DEB-LEVAM-OS-CINCO-MODULOS: sem o opt-in, o uhid de fábrica fica."""
    chamadas = _instala_pelo_host_udev(DKMS, tmp_path, opt_in=False)
    assert len(chamadas) == 4
    assert not any(c.endswith(" uhid") for c in chamadas), chamadas


def test_o_conf_do_uhid_da_casa_vale_como_opt_in(tmp_path: Path) -> None:
    (tmp_path / "nao-existe.conf").write_text("options uhid backpressure=1\n", encoding="utf-8")
    chamadas = _instala_pelo_host_udev(DKMS, tmp_path, opt_in=False)
    assert any(c.endswith(" uhid") for c in chamadas), chamadas


def _ajudante_do_pacote(tmp_path: Path, extra: dict[str, str]) -> str:
    base = tmp_path / "pacote"
    (base / "scripts").mkdir(parents=True)
    (base / "scripts" / "dkms_lib.sh").write_text(
        'dkms_pkg_version() { echo 1.0.0; }\n'
        f'dkms_install_patched_module() {{ echo "$1" >> "{tmp_path}/c.log"; }}\n'
        "dkms_flush_initramfs() { :; }\n",
        encoding="utf-8",
    )
    shutil.copytree(DKMS, base / "dkms")
    env = {
        "PATH": "/usr/bin:/bin",
        "HEFESTO_PACOTE_BASE": str(base),
        "HEFESTO_UHID_CONF": str(tmp_path / "sem.conf"),
        **extra,
    }
    feito = subprocess.run(
        ["bash", str(RAIZ / "scripts" / "dkms_do_pacote.sh")],
        env=env, capture_output=True, text=True, check=False, timeout=60,
    )
    assert feito.returncode == 0, feito.stderr
    return (tmp_path / "c.log").read_text(encoding="utf-8")


def test_o_ajudante_do_pacote_so_instala_o_uhid_com_o_opt_in(tmp_path: Path) -> None:
    """D-0811-O-FLATPAK-E-O-DEB-LEVAM-OS-CINCO-MODULOS: o postinst do deb herda o opt-in."""
    sem = _ajudante_do_pacote(tmp_path / "a", {})
    assert "hefesto-uhid" not in sem and "hefesto-usb-f-hid" in sem
    com = _ajudante_do_pacote(tmp_path / "b", {"COM_UHID_CONTRAPRESSAO": "1"})
    assert "hefesto-uhid" in com
