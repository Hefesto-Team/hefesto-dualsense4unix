"""O upgrade do pacote não reenumera o controle do jogo aberto.

O-UPGRADE-DO-PACOTE-NAO-REENUMERA-O-CONTROLE-DO-JOGO-ABERTO-01: o `udevadm trigger` sem filtro do
`.install` do Arch, do `%post` do Fedora, o de usb do `postinst` do .deb e os do ajudante de host
reenumeravam o controle no meio do jogo. O disparo tem um dono, `scripts/disparo_do_udev.sh`, que
pergunta ao `quem_o_jogo_le.py` e, com jogo, só dispara o que não reenumera o controle.

A MORDIDA: devolva um `udevadm trigger` cru ao `post_install` do `.install`, tire o ramo do jogo
do dono ou deixe o pacote sem o `quem_o_jogo_le.py` ao lado do dono, e a régua reprova.
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import quem_o_jogo_le

RAIZ = Path(__file__).resolve().parents[2]
DONO = RAIZ / "scripts" / "disparo_do_udev.sh"
LEITOR = RAIZ / "src" / "hefesto_dualsense4unix" / "integrations" / "quem_o_jogo_le.py"

INSTALL_DO_ARCH = RAIZ / "packaging/arch/hefesto-dualsense4unix.install"
PKGBUILD = RAIZ / "packaging/arch/PKGBUILD"
SPEC = RAIZ / "packaging/fedora/hefesto-dualsense4unix.spec"
POSTINST = RAIZ / "packaging/debian/postinst"
BUILD_DEB = RAIZ / "scripts/build_deb.sh"
FLATPAK = RAIZ / "flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml"
AJUDANTE = RAIZ / "scripts/install-host-udev.sh"
NATIVO = RAIZ / "scripts/install_udev.sh"

QUE_REENUMERAM = ("hidraw", "idVendor=054c", "subsystem-match=usb", "subsystem-match=input")
QUE_NAO_REENUMERAM = ("subsystem-match=leds", "subsystem-match=misc", "subsystem-match=pci")


def _na_instalacao(arquivo: Path) -> str:
    texto = arquivo.read_text(encoding="utf-8")
    for corte in ("post_remove()", "%postun"):
        texto = texto.split(corte)[0]
    return texto


def _linhas_de_codigo(texto: str) -> list[str]:
    return [ln.strip() for ln in texto.splitlines() if not ln.strip().startswith("#")]


@pytest.mark.parametrize(
    "arquivo",
    [INSTALL_DO_ARCH, SPEC, POSTINST, AJUDANTE, NATIVO, BUILD_DEB, FLATPAK],
    ids=lambda p: p.name,
)
def test_nenhum_scriptlet_dispara_o_udev_fora_do_dono(arquivo: Path) -> None:
    """MORDIDA: devolva `udevadm trigger` ao `post_install` do `.install`, e esta régua reprova."""
    culpadas = [
        ln for ln in _linhas_de_codigo(_na_instalacao(arquivo)) if "udevadm trigger" in ln
    ]
    assert not culpadas, f"{arquivo.name} dispara o udev por conta própria: {culpadas}"


@pytest.mark.parametrize(
    "arquivo", [INSTALL_DO_ARCH, SPEC, POSTINST, AJUDANTE, NATIVO], ids=lambda p: p.name
)
def test_quem_instala_chama_o_dono(arquivo: Path) -> None:
    assert "disparo_do_udev.sh" in _na_instalacao(arquivo)


@pytest.mark.parametrize(
    "arquivo", [PKGBUILD, SPEC, BUILD_DEB, FLATPAK], ids=lambda p: p.name
)
def test_todo_pacote_leva_o_dono_e_o_leitor_lado_a_lado(arquivo: Path) -> None:
    """O dono acha o `quem_o_jogo_le.py` ao lado de si: os dois vão na mesma pasta do pacote."""
    codigo = "\n".join(_linhas_de_codigo(arquivo.read_text(encoding="utf-8")))
    for nome in ("scripts/disparo_do_udev.sh", "integrations/quem_o_jogo_le.py"):
        assert nome in codigo, f"{arquivo.name} não leva {nome}"


def test_o_spec_lista_os_dois_arquivos_do_dono_nos_files() -> None:
    files = SPEC.read_text(encoding="utf-8").split("\n%files\n")[1]
    assert "%{_datadir}/%{app_id}/scripts/disparo_do_udev.sh" in files
    assert "%{_datadir}/%{app_id}/scripts/quem_o_jogo_le.py" in files


def _udevadm_de_mentira(raiz: Path) -> tuple[dict[str, str], Path]:
    bin_ = raiz / "bin"
    bin_.mkdir(parents=True, exist_ok=True)
    diario = raiz / "udevadm.txt"
    falso = bin_ / "udevadm"
    falso.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{diario}"\n', encoding="utf-8")
    falso.chmod(falso.stat().st_mode | stat.S_IEXEC)
    ambiente = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}"}
    return ambiente, diario


def _proc(raiz: Path, *, jogo: bool) -> Path:
    proc = raiz / ("proc-com-jogo" if jogo else "proc-sem-jogo")
    (proc / "42").mkdir(parents=True)
    ambiente = b"HOME=/x\0"
    if jogo:
        ambiente += quem_o_jogo_le.ENV_DO_JOGO.encode() + b"=/compat/1234\0"
    (proc / "42" / "environ").write_bytes(ambiente)
    (proc / "self").mkdir()
    return proc


def _dispara(dono: Path, raiz: Path, proc: Path) -> tuple[list[str], str]:
    ambiente, diario = _udevadm_de_mentira(raiz)
    ambiente["HEFESTO_RAIZ_PROC"] = str(proc)
    saida = subprocess.run(
        ["bash", str(dono)], env=ambiente, capture_output=True, text=True, check=False
    )
    assert saida.returncode == 0, saida.stderr
    chamadas = diario.read_text(encoding="utf-8").splitlines() if diario.exists() else []
    return chamadas, saida.stdout


def _alguma_casa(chamadas: list[str], alvos: tuple[str, ...]) -> bool:
    return any(alvo in c for c in chamadas for alvo in alvos)


def test_com_jogo_aberto_so_dispara_o_que_nao_reenumera_o_controle(tmp_path: Path) -> None:
    """MORDIDA: tire o ramo do jogo do dono e o hidraw, o usb e o input voltam a disparar."""
    chamadas, saida = _dispara(DONO, tmp_path, _proc(tmp_path, jogo=True))
    assert not _alguma_casa(chamadas, QUE_REENUMERAM)
    assert all(c != "trigger" for c in chamadas)
    for alvo in QUE_NAO_REENUMERAM:
        assert any(alvo in c for c in chamadas), alvo
    assert "próximo plugue" in saida


def test_sem_jogo_dispara_o_que_o_instalador_disparava(tmp_path: Path) -> None:
    chamadas, saida = _dispara(DONO, tmp_path, _proc(tmp_path, jogo=False))
    for alvo in (*QUE_REENUMERAM, *QUE_NAO_REENUMERAM):
        assert any(alvo in c for c in chamadas), alvo
    assert "trigger" in chamadas
    assert "próximo plugue" not in saida


def _pasta_do_pacote(raiz: Path, *, com_leitor: bool) -> Path:
    pasta = raiz / "usr" / "share" / "hefesto-dualsense4unix" / "scripts"
    pasta.mkdir(parents=True)
    shutil.copy2(DONO, pasta / DONO.name)
    if com_leitor:
        shutil.copy2(LEITOR, pasta / LEITOR.name)
    return pasta / DONO.name


def test_o_dono_instalado_acha_o_leitor_ao_lado_e_ve_o_jogo(tmp_path: Path) -> None:
    dono = _pasta_do_pacote(tmp_path, com_leitor=True)
    chamadas, _ = _dispara(dono, tmp_path, _proc(tmp_path, jogo=True))
    assert not _alguma_casa(chamadas, QUE_REENUMERAM)
    assert chamadas


def test_sem_o_leitor_o_dono_nao_reenumera_e_diz_que_nao_soube(tmp_path: Path) -> None:
    """MORDIDA: deixe o pacote sem o `quem_o_jogo_le.py` e o upgrade reenumera às cegas."""
    dono = _pasta_do_pacote(tmp_path, com_leitor=False)
    chamadas, saida = _dispara(dono, tmp_path, _proc(tmp_path, jogo=False))
    assert not _alguma_casa(chamadas, QUE_REENUMERAM)
    assert "não deu para saber" in saida
