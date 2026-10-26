"""O ÍCONE NA BANDEJA SEGUE A ESCOLHA, E VOLTA COM O SERVIÇO (AS-TELAS-QUE-ELA-PEDIU-EM-16-10-01,
S3 e S4).

O pedido de 16/10: *«a tray do app não aparece mais na interface. Adiciona um botão (…) pra
permitir voltar a usar o app na tray desativar ou ativar»*. <!-- noqa-acento: citação literal -->

O que se mede, num lar de mentira (`XDG_CONFIG_HOME` e `XDG_RUNTIME_DIR` em `tmp_path`):

1. a pílula «Ícone na bandeja» grava `X-GNOME-Autostart-enabled` e faz valer agora: ligar sobe a
   bandeja (o `Popen` é um dublê que sobe um `sleep` com «tray» na linha), desligar a encerra
   pelo PID dela;
2. `garantir_a_bandeja` não sobe uma segunda com a viva de pé, e sobe com o PID morto;
3. o «Retomar» e o «Ativar» da Sistema e o «start» da bandeja chamam `garantir_a_bandeja`;
4. o bloco do autostart do `install.sh`, rodado de verdade, preserva o `false` e o ensaio diz.
5. o bloco seguinte do `install.sh`, depois do restart do serviço, devolve a bandeja quando a
   escolha está ligada (17/10/2026).

MORDIDAS (feitas à mão, 16/10/2026): tirar o `bandeja_viva() is not None` de `garantir_a_bandeja`
reprova 2, e casar «tray» como pedaço da linha em `bandeja_viva` também; tirar a chamada a
`garantir_a_bandeja` do ramo do «Retomar» em `a09_sistema.desligar` reprova 3; tirar o
`-e "s|^X-GNOME-Autostart-enabled=…"` do `sed` do `install.sh` reprova 4; trocar o
`garantir_a_bandeja()` do bloco da volta por `sys.exit(1)` reprova 5.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import time
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.app.actions import atos_da_bandeja as ab

BASH = shutil.which("bash") or "/bin/bash"
_POPEN = subprocess.Popen


@pytest.fixture
def lar(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> pathlib.Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    return tmp_path


@pytest.fixture
def subidas(monkeypatch: pytest.MonkeyPatch) -> Any:
    """O `Popen` da bandeja vira um `sleep` com «tray» na linha, morto no fim pelo PID dele."""
    feitas: list[tuple[list[str], dict[str, Any]]] = []
    filhos: list[subprocess.Popen[bytes]] = []

    def _popen(argv: list[str], **k: Any) -> subprocess.Popen[bytes]:
        feitas.append((list(argv), k))
        filho = _POPEN(["sh", "-c", "sleep 30; :", "tray"])
        filhos.append(filho)
        return filho

    monkeypatch.setattr(ab.subprocess, "Popen", _popen)
    yield feitas, filhos
    for filho in filhos:
        if filho.poll() is None:
            filho.kill()
        filho.wait(timeout=5)


def _autostart() -> str:
    return ab.caminho_do_autostart().read_text(encoding="utf-8")


def _gesto_da_bandeja() -> Any:
    import pacotes

    pacotes._carregar_tudo()
    fn = pacotes.gesto_da_pagina("09-sistema.html", "bandeja")
    assert fn is not None, "a pílula da bandeja ficou sem dono"
    return lambda: fn(pacotes.Contexto(state={}), {}, None)


def test_a_pilula_liga_e_desliga_a_bandeja(lar: pathlib.Path, subidas: Any) -> None:
    """Prova da D-1610-A-BANDEJA-TEM-INTERRUPTOR-E-VOLTA-COM-O-SERVICO."""
    feitas, filhos = subidas
    clicar = _gesto_da_bandeja()
    assert not ab.bandeja_ligada()
    clicar()
    assert "X-GNOME-Autostart-enabled=true" in _autostart().splitlines()
    assert "@RAIZ@" not in _autostart(), "o autostart nasceu sem o caminho da instalação"
    assert ab.bandeja_ligada()
    assert len(feitas) == 1 and feitas[0][1].get("start_new_session") is True, feitas
    assert ab.bandeja_viva() == filhos[0].pid
    clicar()
    assert "X-GNOME-Autostart-enabled=false" in _autostart().splitlines()
    assert not ab.bandeja_ligada()
    assert filhos[0].wait(timeout=5) is not None, "desligar não encerrou a bandeja viva"
    assert len(feitas) == 1, "desligar subiu outra bandeja"


def test_garantir_nao_sobe_a_segunda_e_sobe_com_o_pid_morto(
        lar: pathlib.Path, subidas: Any) -> None:
    feitas, filhos = subidas
    ab.escolher_a_bandeja(True)
    assert len(feitas) == 1
    for _ in range(3):
        assert ab.garantir_a_bandeja() is False
    assert len(feitas) == 1, "subiu uma segunda bandeja com a primeira de pé"
    filhos[0].kill()
    filhos[0].wait(timeout=5)
    assert ab.bandeja_viva() is None
    assert ab.garantir_a_bandeja() is True
    assert len(feitas) == 2
    ab.caminho_do_pid().write_text(f"{os.getpid()}\n", encoding="ascii")
    assert ab.bandeja_viva() is None
    outro = _POPEN(["sh", "-c", "sleep 30; :", "tests/unit/test_cmd_tray.py"])
    try:
        ab.caminho_do_pid().write_text(f"{outro.pid}\n", encoding="ascii")
        assert ab.bandeja_viva() is None, "um argumento com «tray» dentro virou bandeja"
    finally:
        outro.kill()
        outro.wait(timeout=5)


def test_com_a_escolha_desligada_nada_sobe(lar: pathlib.Path, subidas: Any) -> None:
    feitas, _filhos = subidas
    assert ab.garantir_a_bandeja() is False, "sem autostart, a escolha é desligada"
    ab.escolher_a_bandeja(False)
    assert ab.garantir_a_bandeja() is False
    assert feitas == []


def test_o_retomar_o_ativar_e_o_start_trazem_a_bandeja(
        lar: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Prova da D-1610-A-BANDEJA-TEM-INTERRUPTOR-E-VOLTA-COM-O-SERVICO."""
    import pacotes
    from pacotes import a09_sistema as a09

    pacotes._carregar_tudo()
    chamadas: list[str] = []
    monkeypatch.setattr(ab, "garantir_a_bandeja", lambda: chamadas.append("bandeja") or True)
    monkeypatch.setattr(a09, "_trava", lambda *_a, **_k: None)
    monkeypatch.setattr(a09, "blocos_dos_botoes", lambda *_a, **_k: {})

    class _Ponte:
        def chamar(self, metodo: str, *_a: Any, **_k: Any) -> dict[str, Any]:
            chamadas.append(metodo)
            return {"status": "ok"}

    ctx = pacotes.Contexto(state={})
    monkeypatch.setattr(a09, "_de_pe", lambda _c: True)
    monkeypatch.setattr(a09, "_pausado", lambda _c: True)
    a09.desligar(ctx, {}, _Ponte())
    assert chamadas == ["daemon.resume", "bandeja"], chamadas
    chamadas.clear()
    monkeypatch.setattr(a09, "_de_pe", lambda _c: False)
    monkeypatch.setattr(a09, "ativar_o_servico", lambda: True)
    a09.desligar(ctx, {}, _Ponte())
    assert chamadas == ["bandeja"], chamadas
    chamadas.clear()
    from hefesto_dualsense4unix.app.actions.daemon_actions import DaemonActionsMixin

    monkeypatch.setattr(DaemonActionsMixin, "_invoke_systemctl",
                        lambda _s, *_a, **_k: subprocess.CompletedProcess([], 0))
    assert ab.mexer_no_servico("start")
    assert ab.mexer_no_servico("stop")
    assert chamadas == ["bandeja"], "só o «start» devolve a bandeja; o «stop» não"


def _bloco_do_autostart() -> str:
    texto = (RAIZ / "install.sh").read_text(encoding="utf-8")
    inicio = texto.index("# O AUTOSTART DO TRAY")
    fim = texto.index('mkdir -p "${BIN_DIR}"', inicio)
    return texto[inicio:fim]


def _rodar_o_install(home: pathlib.Path, ensaio: bool) -> str:
    roteiro = ("_faria(){ echo \"FARIA $*\"; }\nwarn(){ echo \"WARN $*\"; }\n"
               + _bloco_do_autostart())
    ambiente = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
                "APP_ID": "hefesto-dualsense4unix", "ROOT_DIR": str(RAIZ),
                "DRY_RUN": "1" if ensaio else "0"}
    feito = subprocess.run([BASH, "-c", roteiro], env=ambiente, capture_output=True,
                           text=True, timeout=20, check=True)
    return feito.stdout


@pytest.mark.parametrize("antes", [None, "true", "false"])
def test_o_install_preserva_a_escolha(tmp_path: pathlib.Path, antes: str | None) -> None:
    alvo = tmp_path / ".config/autostart/hefesto-dualsense4unix-tray.desktop"
    if antes is not None:
        alvo.parent.mkdir(parents=True)
        alvo.write_text(f"[Desktop Entry]\nX-GNOME-Autostart-enabled={antes}\n",
                        encoding="utf-8")
    esperado = antes or "true"
    ensaio = _rodar_o_install(tmp_path, ensaio=True)
    assert f"(ligado={esperado})" in ensaio, ensaio
    assert (alvo.exists() if antes else not alvo.exists()), "o ensaio escreveu o autostart"
    _rodar_o_install(tmp_path, ensaio=False)
    linhas = alvo.read_text(encoding="utf-8").splitlines()
    assert f"X-GNOME-Autostart-enabled={esperado}" in linhas, linhas
    assert f"Exec={RAIZ}/run.sh --tray" in linhas


def _bloco_da_volta() -> str:
    texto = (RAIZ / "install.sh").read_text(encoding="utf-8")
    inicio = texto.index("# A BANDEJA VOLTA DEPOIS DO SERVIÇO")
    fim = texto.index("# ----", inicio)
    return texto[inicio:fim]


@pytest.mark.parametrize(
    ("escolha", "grafica", "ensaio", "sobe"),
    [("true", True, False, True), ("false", True, False, False),
     ("true", False, False, False), ("true", True, True, False)],
    ids=["ligada", "desligada", "sem-sessao-grafica", "ensaio"],
)
def test_o_install_devolve_a_bandeja_depois_do_restart(
    tmp_path: pathlib.Path, escolha: str, grafica: bool, ensaio: bool, sobe: bool,
) -> None:
    """O bloco do `install.sh`, rodado de verdade: o `garantir_a_bandeja` do venv sobe a bandeja.

    A bandeja é um roteiro de mentira (o `Exec=` do autostart) que só deixa a marca e sai.
    A MORDIDA: tire o bloco «A BANDEJA VOLTA DEPOIS DO SERVIÇO» do `install.sh` e o caso
    «ligada» reprova.
    """
    marca = tmp_path / "subiu"
    bandeja = tmp_path / "bandeja-de-mentira.sh"
    bandeja.write_text(f"#!/bin/sh\necho \"$@\" > {marca}\n", encoding="utf-8")
    bandeja.chmod(0o755)
    autostart = tmp_path / "config/autostart/hefesto-dualsense4unix-tray.desktop"
    autostart.parent.mkdir(parents=True)
    autostart.write_text(f"[Desktop Entry]\nExec={bandeja} --tray\n"
                         f"X-GNOME-Autostart-enabled={escolha}\n", encoding="utf-8")
    venv = tmp_path / "venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin/python").write_text(f"#!/bin/sh\nexec {sys.executable} \"$@\"\n",
                                     encoding="utf-8")
    (venv / "bin/python").chmod(0o755)
    ambiente = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(tmp_path),
                "XDG_CONFIG_HOME": str(tmp_path / "config"),
                "XDG_RUNTIME_DIR": str(tmp_path / "run"),
                "PYTHONPATH": os.pathsep.join(p for p in sys.path if p),
                "VENV_DIR": str(venv), "DRY_RUN": "1" if ensaio else "0"}
    if grafica:
        ambiente["WAYLAND_DISPLAY"] = "wayland-de-mentira"
    roteiro = "_faria(){ echo \"FARIA $*\"; }\n" + _bloco_da_volta()
    feito = subprocess.run([BASH, "-c", roteiro], env=ambiente, capture_output=True,
                           text=True, timeout=30, check=True)
    if sobe:
        for _ in range(100):
            if marca.exists():
                break
            time.sleep(0.05)
        assert "subiu" in feito.stdout, feito.stdout + feito.stderr
        assert marca.read_text(encoding="utf-8").split() == ["--tray"]
    else:
        assert not marca.exists(), feito.stdout
    if ensaio:
        assert "FARIA subir o ícone na bandeja" in feito.stdout, feito.stdout
