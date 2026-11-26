"""O ajudante de host não deixa marcador cru na unit do broker.

O-AJUDANTE-DE-HOST-NAO-DEIXA-MARCADOR-CRU-NO-BROKER-01. O ajudante vestia as units do broker com
`sed` de marcadores que o modelo não tem mais e a guarda só procurava esses: o único marcador de
hoje, `__NO_NASCE_FECHADO__`, passava cru, o broker lia diferente de `1` e devolvia o nó aberto
(o DualSense físico voltava a aparecer para o jogo ao lado do virtual, no cabo e no rádio). E a
cópia de `/etc` vencia a unit correta do pacote em `/usr/lib/systemd/system`.

O instrumento é o script de verdade com a raiz de mentira do ajudante do Flatpak: o comando elevado
roda sem root, e cada caminho do sistema vira uma pasta de teste.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from tests.unit.test_o_ajudante_de_host_do_flatpak_grava_e_desfaz_no_host import _Cena

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "install-host-udev.sh"
MODELO = RAIZ / "assets" / "systemd" / "hefesto-hidraw-broker.service"
SOCKET = RAIZ / "assets" / "systemd" / "hefesto-hidraw-broker.socket"
POSTINST = RAIZ / "packaging" / "debian" / "postinst"
ARCH = RAIZ / "packaging" / "arch" / "hefesto-dualsense4unix.install"
SPEC = RAIZ / "packaging" / "fedora" / "hefesto-dualsense4unix.spec"

MARCADOR = re.compile(r"__[A-Z_]+__")
LINHA_DO_NO = "Environment=HEFESTO_BROKER_NO_NASCE_FECHADO="
LINHA_DA_UNIT = "etc/systemd/system/hefesto-hidraw-broker.service"
LINHA_DO_SOCKET = "etc/systemd/system/hefesto-hidraw-broker.socket"


def _script_que_olha_a_raiz_de_mentira(raiz: Path) -> str:
    texto = SCRIPT.read_text(encoding="utf-8")
    antigo = "/usr/lib/systemd/system /lib/systemd/system"
    assert antigo in texto
    return texto.replace(antigo, f"{raiz}/usr/lib/systemd/system {raiz}/lib/systemd/system")


def _cena(tmp: Path) -> _Cena:
    return _Cena(tmp, texto=_script_que_olha_a_raiz_de_mentira(tmp / "raiz"))


def _unit_do_pacote(cena: _Cena, com_marcador: bool = False) -> Path:
    pasta = cena.raiz / "usr" / "lib" / "systemd" / "system"
    pasta.mkdir(parents=True)
    broker = cena.raiz / "usr" / "lib" / "hefesto-dualsense4unix" / "hefesto-hidraw-broker"
    broker.parent.mkdir(parents=True)
    broker.write_text("#!/bin/sh\ntrue\n", encoding="utf-8")
    broker.chmod(0o755)
    texto = MODELO.read_text(encoding="utf-8").replace(
        "/usr/local/lib/hefesto-dualsense4unix/hefesto-hidraw-broker", str(broker)
    )
    if not com_marcador:
        texto = texto.replace("__NO_NASCE_FECHADO__", "1")
    (pasta / "hefesto-hidraw-broker.service").write_text(texto, encoding="utf-8")
    (pasta / "hefesto-hidraw-broker.socket").write_text(
        SOCKET.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return pasta


def _valor_do_no(texto: str) -> list[str]:
    return [
        linha.removeprefix(LINHA_DO_NO).strip()
        for linha in texto.splitlines()
        if linha.startswith(LINHA_DO_NO)
    ]


def test_o_modelo_de_hoje_tem_um_marcador_so_e_o_do_no_que_nasce_fechado() -> None:
    """A premissa do defeito: o único marcador do modelo é `__NO_NASCE_FECHADO__`."""
    assert MARCADOR.findall(MODELO.read_text(encoding="utf-8")) == ["__NO_NASCE_FECHADO__"]
    assert MARCADOR.findall(SOCKET.read_text(encoding="utf-8")) == []


def test_sem_unit_de_pacote_o_ajudante_renderiza_sem_marcador_e_com_o_no_fechado(
    tmp_path: Path,
) -> None:
    """Flatpak e clone: a unit gravada em `/etc` sai sem marcador e o broker lê `1`."""
    cena = _cena(tmp_path)
    r = cena.rodar()
    assert r.returncode == 0, r.stdout + r.stderr
    unit = (cena.raiz / LINHA_DA_UNIT).read_text(encoding="utf-8")
    socket = (cena.raiz / LINHA_DO_SOCKET).read_text(encoding="utf-8")
    assert MARCADOR.findall(unit) == []
    assert MARCADOR.findall(socket) == []
    assert _valor_do_no(unit) == ["1"]
    regra = (cena.raiz / "etc/udev/rules.d/73-hefesto-ps5-controller.rules").read_text("utf-8")
    assert 'TAG-="uaccess"' in regra, "a regra instalada tem de ser a fechada para o 1 valer"


def test_com_a_unit_do_pacote_o_ajudante_nao_grava_copia_em_etc_e_so_liga_a_do_pacote(
    tmp_path: Path,
) -> None:
    """Deb, Arch e Fedora: nada vai para `/etc/systemd/system`, o socket do pacote é ligado."""
    cena = _cena(tmp_path)
    _unit_do_pacote(cena)
    r = cena.rodar()
    assert r.returncode == 0, r.stdout + r.stderr
    gravados = cena.arquivos()
    assert not any(a.startswith("etc/systemd/system/hefesto-hidraw-broker") for a in gravados)
    assert "usr/local/lib/hefesto-dualsense4unix/hefesto-hidraw-broker" not in gravados
    assert "etc/systemd/system/hefesto-bt-bonds-snapshot.service" in gravados
    assert "systemctl enable --now hefesto-hidraw-broker.socket" in cena.chamadas()
    assert "a unit do pacote em" in r.stdout


def test_com_a_unit_do_pacote_a_copia_antiga_de_etc_que_a_sombreava_sai(tmp_path: Path) -> None:
    """A cópia que uma rodada de antes deixou em `/etc` venceria a do pacote: o ajudante a tira."""
    cena = _cena(tmp_path)
    _unit_do_pacote(cena)
    antiga = cena.raiz / "etc" / "systemd" / "system"
    antiga.mkdir(parents=True)
    (antiga / "hefesto-hidraw-broker.service").write_text(
        MODELO.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (antiga / "hefesto-hidraw-broker.socket").write_text("[Socket]\n", encoding="utf-8")
    r = cena.rodar()
    assert r.returncode == 0, r.stdout + r.stderr
    restos = [a for a in cena.arquivos() if a.startswith("etc/systemd/system/hefesto-hidraw")]
    assert restos == []


def test_unit_de_pacote_com_marcador_cru_nao_vale_e_o_ajudante_renderiza_a_dele(
    tmp_path: Path,
) -> None:
    """Pacote com unit torta não serve de alvo: o ajudante cai no render e a de `/etc` sai limpa."""
    cena = _cena(tmp_path)
    _unit_do_pacote(cena, com_marcador=True)
    r = cena.rodar()
    assert r.returncode == 0, r.stdout + r.stderr
    unit = (cena.raiz / LINHA_DA_UNIT).read_text(encoding="utf-8")
    assert MARCADOR.findall(unit) == []
    assert _valor_do_no(unit) == ["1"]


def _funcao_render() -> str:
    texto = SCRIPT.read_text(encoding="utf-8")
    achado = re.search(r"^_render_unit_do_broker\(\) \{\n.*?^\}\n", texto, re.M | re.S)
    assert achado, "o ajudante não tem a função única de render"
    return achado.group(0)


def _renderizar(tmp: Path, fechado: str, modelo: Path = MODELO) -> subprocess.CompletedProcess[str]:
    saida = tmp / "saida"
    saida.mkdir(exist_ok=True)
    return subprocess.run(
        ["bash", "-c", f"{_funcao_render()}\n_render_unit_do_broker '{modelo}' '{SOCKET}' "
         f"'{saida}' '{fechado}'"],
        capture_output=True, text=True, check=False, timeout=30,
    )


@pytest.mark.parametrize("fechado", ["1", "0"])
def test_o_render_veste_o_valor_da_regra_instalada_e_nao_deixa_marcador(
    tmp_path: Path, fechado: str
) -> None:
    """Regra fechada renderiza 1, regra aberta renderiza 0, e nunca sobra marcador."""
    r = _renderizar(tmp_path, fechado)
    assert r.returncode == 0, r.stderr
    unit = (tmp_path / "saida" / "hefesto-hidraw-broker.service").read_text(encoding="utf-8")
    assert _valor_do_no(unit) == [fechado]
    assert MARCADOR.findall(unit) == []


def test_o_render_recusa_qualquer_marcador_e_nao_so_os_de_antes(tmp_path: Path) -> None:
    """A guarda é `__[A-Z_]*__`: um marcador novo no modelo reprova, o `sed` o saiba ou não."""
    modelo = tmp_path / "modelo.service"
    modelo.write_text(
        MODELO.read_text(encoding="utf-8") + "Environment=OUTRA=__MARCADOR_NOVO__\n",
        encoding="utf-8",
    )
    r = _renderizar(tmp_path, "1", modelo)
    assert r.returncode == 1


def _laco_de_limpeza(texto: str) -> str:
    achado = re.search(r"for _u in service socket; do\n.*?\n\s*done\n", texto, re.S)
    assert achado, "o laço que apaga a cópia de /etc não está no script do pacote"
    return achado.group(0)


@pytest.mark.parametrize("pacote", [POSTINST, ARCH, SPEC], ids=["deb", "arch", "fedora"])
def test_o_script_do_pacote_apaga_a_copia_de_etc_com_marcador_cru_e_a_do_uid_gravado(
    tmp_path: Path, pacote: Path
) -> None:
    """A cópia com marcador cru ou com uid gravado sai; a cópia limpa de outro dono fica."""
    etc = tmp_path / "etc" / "systemd" / "system"
    etc.mkdir(parents=True)
    laco = _laco_de_limpeza(pacote.read_text(encoding="utf-8")).replace(
        "/etc/systemd/system", str(etc)
    )
    casos = {
        "service": "[Service]\nEnvironment=HEFESTO_BROKER_NO_NASCE_FECHADO=__NO_NASCE_FECHADO__\n",
        "socket": "[Socket]\nSocketGroup=__SESSION_GROUP__\n",
    }
    for _u, corpo in casos.items():
        (etc / f"hefesto-hidraw-broker.{_u}").write_text(corpo, encoding="utf-8")
    r = subprocess.run(["bash", "-c", laco], capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr
    assert sorted(p.name for p in etc.iterdir()) == []

    (etc / "hefesto-hidraw-broker.service").write_text(
        "[Service]\nEnvironment=HEFESTO_BROKER_ALLOWED_UID=1000\n", encoding="utf-8"
    )
    (etc / "hefesto-hidraw-broker.socket").write_text("[Socket]\nSocketMode=0660\n", "utf-8")
    subprocess.run(["bash", "-c", laco], capture_output=True, text=True, check=False)
    assert sorted(p.name for p in etc.iterdir()) == ["hefesto-hidraw-broker.socket"]
