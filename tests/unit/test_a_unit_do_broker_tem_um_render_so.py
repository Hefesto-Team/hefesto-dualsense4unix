"""A unit do broker se veste num lugar só (A-UNIT-DO-BROKER-TEM-UM-RENDER-SO-01).

Os pacotes, o install nativo e o ajudante de host vestiam a unit do broker cada um com o seu `sed`
e a sua guarda, e o marcador cru de uma das cópias nasceu disso. `_render_broker_units`, em
`scripts/dkms_lib.sh` (o arquivo que o ajudante de host já recebe em todo pacote), é o único render:
os três caminhos o chamam e nenhum outro texto troca `__NO_NASCE_FECHADO__`.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
LIB = RAIZ / "scripts" / "dkms_lib.sh"
MODELO = RAIZ / "assets" / "systemd" / "hefesto-hidraw-broker.service"
SOCKET = RAIZ / "assets" / "systemd" / "hefesto-hidraw-broker.socket"
MARCADOR = "__NO_NASCE_FECHADO__"
CHAMADORES = {
    "install nativo": RAIZ / "scripts" / "lib" / "camada_de_maquina.sh",
    "ajudante de host": RAIZ / "scripts" / "install-host-udev.sh",
    "pacotes": RAIZ / "scripts" / "broker_do_pacote.sh",
}
PASTAS_DE_SCRIPT = ("scripts", "packaging", "flatpak", "assets")
RAIZES_DE_SCRIPT = ("install.sh", "uninstall.sh")


def _textos_de_script() -> dict[str, str]:
    arquivos = [RAIZ / nome for nome in RAIZES_DE_SCRIPT]
    for pasta in PASTAS_DE_SCRIPT:
        arquivos += [p for p in (RAIZ / pasta).rglob("*") if p.is_file()]
    textos: dict[str, str] = {}
    for arquivo in arquivos:
        try:
            textos[arquivo.relative_to(RAIZ).as_posix()] = arquivo.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
    return textos


def test_so_a_lib_e_o_modelo_dizem_o_marcador_da_unit_do_broker():
    """D-2611-A-UNIT-DO-BROKER-TEM-UM-RENDER-SO: nenhum outro `sed` toca o marcador."""
    donos = sorted(c for c, t in _textos_de_script().items() if MARCADOR in t)
    assert donos == ["assets/systemd/hefesto-hidraw-broker.service", "scripts/dkms_lib.sh"], donos


def test_os_tres_caminhos_chamam_o_render_unico_e_nenhum_o_define():
    """D-2611-A-UNIT-DO-BROKER-TEM-UM-RENDER-SO: o install, o ajudante e os pacotes só chamam."""
    for nome, caminho in CHAMADORES.items():
        texto = caminho.read_text(encoding="utf-8")
        assert "_render_broker_units " in texto, f"{nome} não chama o render único"
        assert "_render_broker_units()" not in texto, f"{nome} define um render próprio"
        assert "_render_unit_do_broker" not in texto, f"{nome} guarda o render antigo"
    assert LIB.read_text(encoding="utf-8").count("_render_broker_units() {") == 1


def _render_direto(tmp: Path) -> tuple[str, str]:
    feito = subprocess.run(
        ["bash", "-c", f"source '{LIB}'; _render_broker_units '{MODELO}' '{SOCKET}' '{tmp}' 1"],
        capture_output=True, text=True, check=False, timeout=30,
    )
    assert feito.returncode == 0, feito.stderr
    return ((tmp / "hefesto-hidraw-broker.service").read_text(encoding="utf-8"),
            (tmp / "hefesto-hidraw-broker.socket").read_text(encoding="utf-8"))


def test_o_pacote_veste_a_unit_pelo_render_unico_tirando_so_o_caminho(tmp_path):
    """D-2611-A-UNIT-DO-BROKER-TEM-UM-RENDER-SO: a unit do pacote é a do render direto, com o
    caminho do binário trocado e mais nada."""
    direto = tmp_path / "direto"
    direto.mkdir()
    servico, socket = _render_direto(direto)
    binario = "/usr/lib/hefesto-dualsense4unix/hefesto-hidraw-broker"
    pacote = tmp_path / "pacote"
    feito = subprocess.run(
        ["bash", str(CHAMADORES["pacotes"]), str(pacote), binario],
        capture_output=True, text=True, check=False, timeout=30, cwd=str(RAIZ),
    )
    assert feito.returncode == 0, feito.stderr
    do_pacote = (pacote / "hefesto-hidraw-broker.service").read_text(encoding="utf-8")
    assert do_pacote == servico.replace(
        "/usr/local/lib/hefesto-dualsense4unix/hefesto-hidraw-broker", binario)
    assert (pacote / "hefesto-hidraw-broker.socket").read_text(encoding="utf-8") == socket


@pytest.mark.parametrize("fechado", ["0", "1"])
def test_o_render_unico_recusa_marcador_cru_em_qualquer_dos_dois_modelos(tmp_path, fechado):
    """D-2611-A-UNIT-DO-BROKER-TEM-UM-RENDER-SO: a guarda `__[A-Z_]*__` é uma só, e vale para a
    unit e para o socket."""
    for qual in ("service", "socket"):
        modelo = tmp_path / f"m-{fechado}-{qual}.service"
        socket = tmp_path / f"m-{fechado}-{qual}.socket"
        modelo.write_text(MODELO.read_text(encoding="utf-8"), encoding="utf-8")
        socket.write_text(SOCKET.read_text(encoding="utf-8"), encoding="utf-8")
        alvo = modelo if qual == "service" else socket
        texto = alvo.read_text(encoding="utf-8") + "# __MARCADOR_NOVO__\n"
        alvo.write_text(texto, encoding="utf-8")
        saida = tmp_path / f"s-{fechado}-{qual}"
        saida.mkdir()
        feito = subprocess.run(
            ["bash", "-c",
             f"source '{LIB}'; _render_broker_units '{modelo}' '{socket}' '{saida}' {fechado}"],
            capture_output=True, text=True, check=False, timeout=30,
        )
        assert feito.returncode == 1, (qual, feito)
