"""A janela e a bandeja que a troca no fim do jogo reabre nascem fora da unidade dela.

Queixa de 29/10/2026: a janela mostrava a página velha horas depois do install. Medido no
`interface.log` e no diário: todo install da noite teve um jogo aberto, então a janela ficou com o
código velho até a troca no fim do jogo; a troca reabriu a janela às 02:10:32 e às 08:49:29, e a
unidade `hefesto-troca-no-fim-do-jogo` terminou dois segundos depois, levando junto a janela nova,
que era filha dela por `Popen`. Sobrava a janela velha que ela abrisse depois, ou nenhuma. Provado
vivo no mesmo dia: dentro de uma unidade do `systemd-run`, o filho por `Popen` morre com ela, e o
aberto por `fora_do_servico.abrir` segue de pé.

A régua roda a `recarregar` de verdade, como se estivesse dentro da unidade da troca, com o
`systemd-run` e o `Popen` trocados por dublês: a janela e a bandeja têm de sair pela linha do
`systemd-run`, com a tela e a aba, e nenhuma pelo `Popen`.

MORDIDA (29/10/2026): devolver o `subprocess.Popen` a `abrir_a_janela` reprova a janela, e o de
`garantir_a_bandeja` reprova a bandeja, com o `Popen` nomeado.
"""
from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import atos_da_bandeja as bandeja
from hefesto_dualsense4unix.app.actions import recarga_do_install as recarga
from hefesto_dualsense4unix.integrations import fora_do_servico

UNIDADE_DA_TROCA = "hefesto-troca-no-fim-do-jogo.service"
ESPERA = "import time\nfor _ in range(600): time.sleep(0.1)"
_POPEN = subprocess.Popen


class Dubles:
    def __init__(self) -> None:
        self.linhas: list[list[str]] = []
        self.popen: list[list[str]] = []

    def executar(self, cmd: Sequence[str], env: Mapping[str, str]) -> Any:
        self.linhas.append(list(cmd))
        return subprocess.CompletedProcess(list(cmd), 0, "", "")

    def depois_do_traco(self, linha: list[str]) -> list[str]:
        return linha[linha.index("--") + 1:]


@pytest.fixture
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Path, Dubles]]:
    corre = tmp_path / "corre"
    (corre / "hefesto-dualsense4unix").mkdir(parents=True)
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    lancador = bin_ / bandeja.LANCADOR_DO_PAINEL
    lancador.write_text("#!/bin/sh\n", encoding="ascii")
    lancador.chmod(0o755)
    autostart = tmp_path / "config" / "autostart"
    autostart.mkdir(parents=True)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(corre))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("PATH", str(bin_))
    bandeja.caminho_do_autostart().write_text(
        "[Desktop Entry]\nExec=/bin/true tray\nX-GNOME-Autostart-enabled=true\n",
        encoding="utf-8")
    dubles = Dubles()
    filhos: list[subprocess.Popen[bytes]] = []

    def _popen(argv: Sequence[str], **_k: Any) -> subprocess.Popen[bytes]:
        dubles.popen.append(list(argv))
        filho = _POPEN(["/bin/sleep", "30"])
        filhos.append(filho)
        return filho

    monkeypatch.setattr(fora_do_servico, "contexto_atual", lambda **_k: fora_do_servico.Contexto(
        gerenciador=True, herdaria=f"dentro do serviço {UNIDADE_DA_TROCA}",
        oom_do_gerenciador=None))
    monkeypatch.setattr(fora_do_servico, "_executar_de_verdade", dubles.executar)
    monkeypatch.setattr(subprocess, "Popen", _popen)
    yield corre, dubles
    for filho in filhos:
        if filho.poll() is None:
            filho.kill()
        filho.wait(timeout=5)


def _janela_velha(corre: Path) -> subprocess.Popen[bytes]:
    filho = _POPEN([sys.executable, "-c", ESPERA, "hefesto", "--gui"],
                   env={"PATH": "/usr/bin:/bin", "WAYLAND_DISPLAY": "wayland-9"})
    (corre / "hefesto-dualsense4unix" / "gui-wayland-9.pid").write_text(
        f"{filho.pid}\n", encoding="ascii")
    recarga.arquivo_da_aba(filho.pid).write_text("04-iluminacao.html\n", encoding="utf-8")
    return filho


def test_a_janela_reaberta_pela_troca_nasce_numa_unidade_propria(
        lar: tuple[Path, Dubles]) -> None:
    corre, dubles = lar
    velha = _janela_velha(corre)
    try:
        frases = recarga.recarregar(subir_a_bandeja=lambda: False)
        velha.wait(timeout=10)
    finally:
        if velha.poll() is None:
            velha.kill()
            velha.wait(timeout=5)
    assert "janela: fechada e reaberta" in frases, frases
    assert not dubles.popen, f"a janela saiu pelo Popen e morre com a unidade: {dubles.popen}"
    janelas = [x for x in dubles.linhas
               if dubles.depois_do_traco(x)[0].endswith(bandeja.LANCADOR_DO_PAINEL)]
    assert len(janelas) == 1, dubles.linhas
    linha = janelas[0]
    assert linha[:2] == ["systemd-run", "--user"], linha
    assert dubles.depois_do_traco(linha)[1:] == ["--abre", "04-iluminacao.html"], linha
    assert "--setenv=WAYLAND_DISPLAY=wayland-9" in linha, linha
    assert "--setenv=HEFESTO_NA_TELA=1" in linha, linha


def test_a_bandeja_subida_pela_troca_nasce_numa_unidade_propria(
        lar: tuple[Path, Dubles]) -> None:
    _corre, dubles = lar
    assert bandeja.garantir_a_bandeja() is True
    assert not dubles.popen, f"a bandeja saiu pelo Popen e morre com a unidade: {dubles.popen}"
    assert len(dubles.linhas) == 1, dubles.linhas
    linha = dubles.linhas[0]
    assert linha[:2] == ["systemd-run", "--user"], linha
    assert dubles.depois_do_traco(linha) == ["/bin/true", "tray"], linha
