"""RADIO-ABERTO-01/E10 — o restaurador de bonds recusa snapshot preparado.

`scripts/bt_bonds_restore.sh` copiava o diretório do device com `cp -a`, e
**`cp -a` preserva symlinks — não os segue**. Um snapshot contendo

    <adaptador>/<MAC>/info -> /etc/sudoers.d/x

era copiado tal e qual para `/var/lib/bluetooth`, e o `bluetoothd` — que roda
como **root** — passava a escrever ATRAVÉS do link. Isso é escrita arbitrária
como root a partir de um snapshot.

Hoje o acervo é local e só o root escreve nele, o que limita o alcance. Mas a
`BONDS-QUE-SOBREVIVEM-01` quer **acionar a restauração automaticamente**, e
qualquer futuro que inclua importar, sincronizar ou receber um snapshot
transforma isto em execução remota. É por isso que a cura veio antes do
acionamento, e não depois.

A cura tem duas camadas, de propósito:

  1. `_validar_snapshot` percorre a árvore ANTES de qualquer coisa — antes de
     parar o `bluetooth.service`, antes de tocar o storage. Recusa symlink,
     device, socket, FIFO, hardlink (`nlink > 1`) e todo nome fora do conjunto
     esperado (`info`, `attributes`, `settings`, `cache/<MAC>`);
  2. a cópia passou a ser por **conteúdo** — arquivo a arquivo do conjunto
     esperado — em vez de `cp -a` do diretório. Defesa em profundidade: o que
     sai daqui não depende de a validação ter enxergado tudo.

E a validação roda antes do `systemctl stop`: um snapshot recusado **não custa
a ela os controles conectados**.

MORDIDA: troque a chamada a `_validar_snapshot` por `true` e
`test_symlink_para_fora_da_arvore_e_recusado` fica vermelho.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RESTORE = REPO_ROOT / "scripts" / "bt_bonds_restore.sh"

# Faixa sintética canônica das fixtures (test_anonimato_de_fixtures.py).
ADAPTER = "AA:BB:CC:00:00:01"
DEVICE = "AA:BB:CC:00:00:02"

INFO = """[General]
Name=DualSense Wireless Controller

[LinkKey]
Type=4
PINLength=0
"""


def _snapshot(raiz: Path, ts: str = "20260805-000000") -> Path:
    """Monta um acervo com UM snapshot sadio e devolve o diretório do snapshot."""
    snap = raiz / ts
    dev = snap / ADAPTER / DEVICE
    dev.mkdir(parents=True)
    (dev / "info").write_text(INFO, encoding="utf-8")
    (snap / ADAPTER / "settings").write_text(
        "[General]\nDiscoverable=false\n", encoding="utf-8"
    )
    return snap


def _verificar(src_root: Path, ts: str = "20260805-000000") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(RESTORE), "--verificar", ts],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "HEFESTO_BT_BONDS_SRC": str(src_root)},
    )


def test_snapshot_sadio_passa(tmp_path: Path) -> None:
    """Linha de base — sem ela, um validador que recusa tudo 'passaria'."""
    _snapshot(tmp_path)
    proc = _verificar(tmp_path)
    assert proc.returncode == 0, f"snapshot legítimo recusado: {proc.stderr}"
    assert "validação OK" in proc.stdout


def test_symlink_para_fora_da_arvore_e_recusado(tmp_path: Path) -> None:
    """O ataque da sprint, literal: `info` que aponta para fora."""
    snap = _snapshot(tmp_path)
    alvo = tmp_path / "alvo_fora_da_arvore"
    alvo.write_text("original\n", encoding="utf-8")
    info = snap / ADAPTER / DEVICE / "info"
    info.unlink()
    info.symlink_to(alvo)

    proc = _verificar(tmp_path)

    assert proc.returncode != 0, (
        "snapshot com symlink foi ACEITO — o bluetoothd escreveria como root "
        "através do link"
    )
    assert "SYMLINK" in proc.stderr
    assert alvo.read_text(encoding="utf-8") == "original\n", (
        "o alvo fora da árvore foi tocado"
    )


def test_symlink_de_diretorio_de_device_e_recusado(tmp_path: Path) -> None:
    """Não só o arquivo: o diretório do device também pode ser link."""
    snap = _snapshot(tmp_path)
    fora = tmp_path / "diretorio_fora"
    fora.mkdir()
    link = snap / ADAPTER / "AA:BB:CC:00:00:03"
    link.symlink_to(fora)

    proc = _verificar(tmp_path)

    assert proc.returncode != 0
    assert "SYMLINK" in proc.stderr


def test_nome_fora_do_conjunto_esperado_e_recusado(tmp_path: Path) -> None:
    """Conjunto explícito de nomes — não 'tudo menos o que eu lembrei de barrar'."""
    snap = _snapshot(tmp_path)
    (snap / ADAPTER / DEVICE / "payload.sh").write_text("#!/bin/sh\n", encoding="utf-8")

    proc = _verificar(tmp_path)

    assert proc.returncode != 0
    assert "payload.sh" in proc.stderr


def test_nome_de_adaptador_que_nao_e_mac_e_recusado(tmp_path: Path) -> None:
    """`..` ou nome arbitrário no lugar do MAC do adaptador."""
    snap = _snapshot(tmp_path)
    (snap / "nao-e-um-mac").mkdir()

    proc = _verificar(tmp_path)

    assert proc.returncode != 0
    assert "não é um MAC" in proc.stderr


def test_hardlink_e_recusado(tmp_path: Path) -> None:
    """Hardlink escreve no mesmo inode — um bond legítimo nunca tem nlink > 1."""
    snap = _snapshot(tmp_path)
    alvo = tmp_path / "alvo_hardlink"
    alvo.write_text("original\n", encoding="utf-8")
    info = snap / ADAPTER / DEVICE / "info"
    info.unlink()
    os.link(alvo, info)

    proc = _verificar(tmp_path)

    assert proc.returncode != 0
    assert "hardlink" in proc.stderr.lower()


def test_verificar_nao_para_o_servico_nem_exige_root(tmp_path: Path) -> None:
    """O modo `--verificar` é só leitura — e é o que o torna testável.

    Se ele tocasse `systemctl`, este teste derrubaria o Bluetooth da máquina em
    que a suíte roda. A asserção é sobre o CÓDIGO: o caminho de verificação sai
    antes de qualquer chamada a systemctl.
    """
    _snapshot(tmp_path)
    proc = _verificar(tmp_path)
    assert proc.returncode == 0
    assert "systemctl" not in proc.stdout
    assert "PARADO" not in proc.stdout, (
        "o modo --verificar chegou ao caminho que para o bluetooth.service"
    )


@pytest.mark.parametrize("modo", ["--list", "--verificar"])
def test_modos_de_leitura_nao_exigem_root(tmp_path: Path, modo: str) -> None:
    """A suíte não roda como root — e estes dois modos precisam funcionar assim."""
    _snapshot(tmp_path)
    args = [modo] if modo == "--list" else [modo, "20260805-000000"]
    proc = subprocess.run(
        ["bash", str(RESTORE), *args],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "HEFESTO_BT_BONDS_SRC": str(tmp_path)},
    )
    assert "requer root" not in proc.stderr
    assert proc.returncode == 0
