"""A BANDEJA DESLIGADA NÃO VOLTA NO LOGIN (A-BANDEJA-DESLIGADA-NAO-VOLTA-NO-LOGIN-01).

A pílula «Ícone na bandeja» desligada gravava só `X-GNOME-Autostart-enabled=false`; o gerador de
autostart do systemd (COSMIC, Plasma) só conhece `Hidden=true` e subia a bandeja no login seguinte.

Decisão proposta (a validar): D-2611-A-BANDEJA-DESLIGADA-GRAVA-AS-DUAS-CHAVES-DO-AUTOSTART,
a escolha «Ícone na bandeja» desligada vale em toda sessão porque o produto grava
`X-GNOME-Autostart-enabled=false` e `Hidden=true` juntos, e lê desligada por qualquer uma.

O que se mede, num lar de mentira:

1. `escolher_a_bandeja` grava as duas chaves e `bandeja_ligada` lê as duas (qualquer uma desligando
   desliga);
2. o bloco do autostart do `install.sh`, rodado de verdade, preserva a escolha por qualquer das duas
   chaves e escreve as duas;
3. o `systemd-xdg-autostart-generator`, rodado sobre o arquivo que o produto grava, não cria unit
   com a bandeja desligada e cria uma com a bandeja ligada;
4. a bandeja que sobe com a escolha desligada sai com rc 0 sem ícone; sem arquivo de escolha segue.

MORDIDAS (25/11/2026): gravar só a chave do GNOME em `escolher_a_bandeja` reprova 1 e 3; tirar o
`-e "s|^Hidden=…"` do `sed` do `install.sh` reprova 2; tirar o desvio de `tray_cmd` reprova 4.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess

import pytest
import typer

from hefesto_dualsense4unix.app.actions import atos_da_bandeja as ab

RAIZ = pathlib.Path(__file__).resolve().parents[2]
BASH = shutil.which("bash") or "/bin/bash"
GERADOR = pathlib.Path("/usr/lib/systemd/user-generators/systemd-xdg-autostart-generator")
NOME = "hefesto-dualsense4unix-tray.desktop"


@pytest.fixture
def lar(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> pathlib.Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    return tmp_path


def _escrever(lar: pathlib.Path, corpo: str) -> pathlib.Path:
    alvo = lar / "config" / "autostart" / NOME
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(f"[Desktop Entry]\nType=Application\nName=T\nExec=/bin/true\n{corpo}",
                    encoding="utf-8")
    return alvo


def test_o_modelo_traz_o_hidden_ligado() -> None:
    linhas = (RAIZ / "packaging" / NOME).read_text(encoding="utf-8").splitlines()
    assert "Hidden=false" in linhas
    assert "X-GNOME-Autostart-enabled=true" in linhas


def test_a_pilula_grava_as_duas_chaves(lar: pathlib.Path,
                                       monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ab, "garantir_a_bandeja", lambda *_a, **_k: False)
    monkeypatch.setattr(ab, "fechar_as_bandejas", lambda *_a, **_k: [])
    monkeypatch.setattr(ab, "bandejas_da_sessao", lambda: [])
    ab.escolher_a_bandeja(False)
    linhas = ab.caminho_do_autostart().read_text(encoding="utf-8").splitlines()
    assert "X-GNOME-Autostart-enabled=false" in linhas
    assert "Hidden=true" in linhas, linhas
    assert ab.bandeja_ligada() is False
    ab.escolher_a_bandeja(True)
    linhas = ab.caminho_do_autostart().read_text(encoding="utf-8").splitlines()
    assert "X-GNOME-Autostart-enabled=true" in linhas
    assert "Hidden=false" in linhas
    assert "Hidden=true" not in linhas
    assert ab.bandeja_ligada() is True


@pytest.mark.parametrize("corpo,ligada", [
    ("X-GNOME-Autostart-enabled=false\n", False),
    ("Hidden=true\n", False),
    ("X-GNOME-Autostart-enabled=true\nHidden=true\n", False),
    ("X-GNOME-Autostart-enabled=false\nHidden=false\n", False),
    ("X-GNOME-Autostart-enabled=true\nHidden=false\n", True),
    ("", True),
])
def test_a_leitura_desliga_por_qualquer_das_chaves(
        lar: pathlib.Path, corpo: str, ligada: bool) -> None:
    _escrever(lar, corpo)
    assert ab.bandeja_ligada() is ligada
    assert ab.bandeja_desligada_pela_escolha() is (not ligada)


def test_sem_arquivo_nao_ha_escolha_e_a_bandeja_nao_e_ligada(lar: pathlib.Path) -> None:
    assert ab.bandeja_ligada() is False
    assert ab.bandeja_desligada_pela_escolha() is False


def _rodar_o_install(home: pathlib.Path, ensaio: bool) -> str:
    texto = (RAIZ / "install.sh").read_text(encoding="utf-8")
    inicio = texto.index('_AUTOSTART_DIR="${HOME}/.config/autostart"')
    fim = texto.index('mkdir -p "${BIN_DIR}"', inicio)
    roteiro = ("_faria(){ echo \"FARIA $*\"; }\nwarn(){ echo \"WARN $*\"; }\n"
               + texto[inicio:fim])
    ambiente = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
                "APP_ID": "hefesto-dualsense4unix", "ROOT_DIR": str(RAIZ),
                "DRY_RUN": "1" if ensaio else "0"}
    return subprocess.run([BASH, "-c", roteiro], env=ambiente, capture_output=True, text=True,
                          timeout=20, check=True).stdout


@pytest.mark.parametrize("antes,gnome,hidden", [
    (None, "true", "false"),
    ("X-GNOME-Autostart-enabled=true\nHidden=false\n", "true", "false"),
    ("X-GNOME-Autostart-enabled=false\nHidden=true\n", "false", "true"),
    ("X-GNOME-Autostart-enabled=false\n", "false", "true"),
    ("Hidden=true\n", "false", "true"),
])
def test_o_install_preserva_a_escolha_pelas_duas_chaves(
        tmp_path: pathlib.Path, antes: str | None, gnome: str, hidden: str) -> None:
    alvo = tmp_path / ".config" / "autostart" / NOME
    if antes is not None:
        alvo.parent.mkdir(parents=True)
        alvo.write_text(f"[Desktop Entry]\n{antes}", encoding="utf-8")
    ensaio = _rodar_o_install(tmp_path, ensaio=True)
    assert f"(ligado={'true' if gnome == 'true' else 'false'})" in ensaio, ensaio
    _rodar_o_install(tmp_path, ensaio=False)
    linhas = alvo.read_text(encoding="utf-8").splitlines()
    assert f"X-GNOME-Autostart-enabled={gnome}" in linhas, linhas
    assert f"Hidden={hidden}" in linhas, linhas


def _unidades_do_gerador(config: pathlib.Path, pasta: pathlib.Path) -> list[str]:
    saida = [pasta / nome for nome in ("n", "e", "l")]
    for destino in saida:
        destino.mkdir(parents=True, exist_ok=True)
    ambiente = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "XDG_CONFIG_HOME": str(config),
                "XDG_CONFIG_DIRS": str(pasta / "nenhum"), "XDG_CURRENT_DESKTOP": "COSMIC"}
    subprocess.run([str(GERADOR), *map(str, saida)], env=ambiente, capture_output=True,
                   timeout=20, check=True)
    return sorted(p.name for p in saida[2].iterdir() if p.suffix == ".service")


@pytest.mark.skipif(not GERADOR.exists(), reason="sem o gerador de autostart do systemd")
@pytest.mark.parametrize("ligada,unidades", [(False, 0), (True, 1)])
def test_o_gerador_do_systemd_respeita_o_arquivo_que_o_produto_grava(
        lar: pathlib.Path, monkeypatch: pytest.MonkeyPatch, ligada: bool, unidades: int) -> None:
    monkeypatch.setattr(ab, "garantir_a_bandeja", lambda *_a, **_k: False)
    monkeypatch.setattr(ab, "fechar_as_bandejas", lambda *_a, **_k: [])
    monkeypatch.setattr(ab, "bandejas_da_sessao", lambda: [])
    _escrever(lar, "")
    ab.escolher_a_bandeja(ligada)
    achadas = _unidades_do_gerador(lar / "config", lar / "gerador")
    assert len(achadas) == unidades, achadas


def test_a_bandeja_com_a_escolha_desligada_sai_sem_icone(
        lar: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    from hefesto_dualsense4unix.app import tray
    from hefesto_dualsense4unix.cli.cmd_tray import tray_cmd

    sondas: list[str] = []

    def _sonda() -> tuple[bool, str]:
        sondas.append("probe")
        return False, "sem gi"

    monkeypatch.setattr(tray, "probe_gi_availability", _sonda)
    _escrever(lar, "X-GNOME-Autostart-enabled=false\nHidden=true\n")
    with pytest.raises(typer.Exit) as desligada:
        tray_cmd()
    assert desligada.value.exit_code == 0
    assert sondas == [], "a bandeja desligada seguiu para subir o ícone"
    assert "aba Sistema" in capsys.readouterr().out, "a recusa não diz onde se liga o ícone"
    ab.caminho_do_autostart().unlink()
    with pytest.raises(typer.Exit) as sem_escolha:
        tray_cmd()
    assert sem_escolha.value.exit_code == 2
    assert sondas == ["probe"], "sem arquivo de escolha a bandeja pedida tem de seguir"
