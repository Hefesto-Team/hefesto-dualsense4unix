"""O-CANARIO-NAO-ACUSA-O-SERVICO-VIVO-01: o canário separa o escrevente da suíte do serviço vivo.

Em 07/11 uma parte do lote fechou vermelha pelo `ultimo_jogo.json` real, gravado pelo serviço vivo
(o evento dele não cita o caminho, e o diário não o confessava). O escrevente passou a ser medido: a
guarda vê toda escrita do processo dos testes, e o `Popen` da sessão vê o filho que nasce com o
lar real. Sem recusa e sem filho assim, o delta é de outro processo.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import Any

import pytest

from tests import conftest as canario

RAIZ = Path(__file__).resolve().parents[2]
ARQUIVO = "ultimo_jogo.json"


class _SessaoFalsa:
    def __init__(self) -> None:
        self.exitstatus = 0
        self.config = None


def _lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    lar = tmp_path / "lar"
    pasta = lar / ".config" / "hefesto-dualsense4unix"
    pasta.mkdir(parents=True)
    (lar / ".config" / "wireplumber").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(lar))
    monkeypatch.delenv(canario._CANARIO_DESLIGADO_ENV, raising=False)
    monkeypatch.setattr(canario, "_CANARIO_FOTO_AVISO", canario._fotografar_tudo_de_aviso())
    monkeypatch.setattr(canario, "_deltas_do_congelado", lambda: [])
    monkeypatch.setattr(canario, "_gestos_da_janela_do_usuario", lambda: [])
    monkeypatch.setattr(canario, "_INICIO_DA_SESSAO", ["2026-11-11 06:40:00"])
    monkeypatch.setattr(canario, "escritas_do_servico_no_journal", lambda desde: frozenset())
    monkeypatch.setattr(canario, "o_servico_falou_desde", lambda desde: True)
    monkeypatch.setattr(canario, "_FILHOS_COM_O_LAR_REAL", [])
    monkeypatch.setattr(canario, "_CANARIO_FOTO_INICIAL", canario._fotografar_tudo())
    monkeypatch.setattr(canario, "_CANARIO_ARMADO", True)
    return lar


def _com_a_guarda(monkeypatch: pytest.MonkeyPatch, lar: Path) -> canario.GuardaDoReal:
    guarda = canario.GuardaDoReal([lar / ".config" / "hefesto-dualsense4unix"], [])
    monkeypatch.setattr(canario, "_GUARDA_DA_SESSAO", [guarda])
    return guarda


def _veredito(capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    sessao: Any = _SessaoFalsa()
    canario.pytest_sessionfinish(sessao, 0)
    return sessao.exitstatus, capsys.readouterr().out


def _o_servico_grava(lar: Path, pasta: str = "hefesto-dualsense4unix") -> Path:
    alvo = lar / ".config" / pasta / ARQUIVO
    alvo.write_text('{"perfil": "viajante"}\n', encoding="utf-8")
    return alvo


def test_o_servico_vivo_gravando_com_a_guarda_limpa_e_aviso(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    lar = _lar(tmp_path, monkeypatch)
    _com_a_guarda(monkeypatch, lar)
    alvo = _o_servico_grava(lar)

    status, saida = _veredito(capsys)

    assert status == 0, saida
    assert canario._GUARDA_PORTAO not in saida
    assert "nenhum escrevente da suíte" in saida and str(alvo) in saida


def test_sem_o_servico_falar_no_diario_a_escrita_e_da_suite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A guarda não vê a escrita em C: sem o serviço vivo, ninguém de fora escreveu."""
    lar = _lar(tmp_path, monkeypatch)
    _com_a_guarda(monkeypatch, lar)
    monkeypatch.setattr(canario, "o_servico_falou_desde", lambda desde: False)
    _o_servico_grava(lar)

    status, saida = _veredito(capsys)

    assert status == 1, saida
    assert "a suíte ESCREVEU" in saida and "nenhum escrevente da suíte" not in saida


def test_guarda_com_recusa_mantem_o_portao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    lar = _lar(tmp_path, monkeypatch)
    guarda = _com_a_guarda(monkeypatch, lar)
    guarda.recusas.append("open /x (um teste)")
    _o_servico_grava(lar)

    status, saida = _veredito(capsys)

    assert status == 1
    assert "a suíte ESCREVEU" in saida


def test_filho_com_o_lar_real_mantem_o_portao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    lar = _lar(tmp_path, monkeypatch)
    _com_a_guarda(monkeypatch, lar)
    monkeypatch.setattr(canario, "_FILHOS_COM_O_LAR_REAL", ["['python', '-c', 'x']"])
    _o_servico_grava(lar)

    status, saida = _veredito(capsys)

    assert status == 1
    assert "filho lançado com o lar real" in saida


def test_sem_a_guarda_a_atribuicao_nao_existe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    lar = _lar(tmp_path, monkeypatch)
    monkeypatch.setattr(canario, "_GUARDA_DA_SESSAO", [])
    _o_servico_grava(lar)

    status, _saida = _veredito(capsys)

    assert status == 1


def test_pasta_que_a_guarda_nao_cobre_continua_portao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    lar = _lar(tmp_path, monkeypatch)
    _com_a_guarda(monkeypatch, lar)
    _o_servico_grava(lar, "wireplumber")

    status, saida = _veredito(capsys)

    assert status == 1
    assert "wireplumber" in saida


def test_o_filho_so_conta_quando_o_ambiente_dele_resolve_o_lar_real(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lar = _lar(tmp_path, monkeypatch)
    _com_a_guarda(monkeypatch, lar)
    monkeypatch.setattr(canario, "_LAR_REAL", [lar])
    monkeypatch.setattr(canario, "_FIM_DA_SESSAO", [])
    falso = str(tmp_path / "falso")

    def lanca(env: dict[str, str] | None) -> int:
        monkeypatch.setattr(canario, "_FILHOS_COM_O_LAR_REAL", [])
        canario._anotar_o_filho_que_alcanca_o_lar_real({"args": ["x"], "env": env})
        return len(canario._FILHOS_COM_O_LAR_REAL)

    assert lanca({"HOME": falso}) == 0
    assert lanca({"HOME": falso, "XDG_CONFIG_HOME": falso + "/c"}) == 0
    assert lanca({"HOME": str(lar)}) == 1
    assert lanca({"HOME": falso, "XDG_CONFIG_HOME": str(lar / ".config")}) == 1
    assert lanca({"PATH": "/usr/bin"}) == 1
    monkeypatch.setattr(canario, "_FIM_DA_SESSAO", [True])
    assert lanca({"HOME": str(lar)}) == 0


_DENTRO = textwrap.dedent('''
    import os, pathlib, subprocess, sys, time

    def test_dentro():
        pasta = pathlib.Path(os.environ["HEFESTO_SINAL"])
        (pasta / "pronto").write_text("1")
        limite = time.monotonic() + 60
        while not (pasta / "liberar").exists() and time.monotonic() < limite:
            time.sleep(0.05)
        modo = os.environ["HEFESTO_MODO"]
        real = pathlib.Path(os.environ["HEFESTO_LAR_REAL"]) / ".config" / "hefesto-dualsense4unix"
        if modo == "teste":
            try:
                (real / "do_teste.json").write_text("{}")
            except PermissionError:
                pass
        if modo == "filho":
            subprocess.run(
                [sys.executable, "-c",
                 "import pathlib,sys;pathlib.Path(sys.argv[1], 'do_filho.json').write_text('{}')",
                 str(real)],
                env={"HOME": os.environ["HEFESTO_LAR_REAL"], "PATH": os.environ["PATH"]},
                check=True)
''')


def _diario_de_mentira(tmp_path: Path) -> Path:
    """O diário do serviço de mentira: ele fala só no modo `vivo`, e a régua não lê a máquina."""
    pasta = tmp_path / "bin"
    pasta.mkdir()
    falso = pasta / "journalctl"
    falso.write_text(
        '#!/bin/sh\n'
        'case " $* " in *" -u hefesto-dualsense4unix.service "*)\n'
        '  [ "$HEFESTO_MODO" = vivo ] && echo o_ultimo_jogo_lembrado ;;\n'
        'esac\n'
        'exit 0\n',
        encoding="utf-8")
    falso.chmod(0o755)
    return pasta


def _sessao_interna(tmp_path: Path, modo: str) -> tuple[int, str]:
    """Uma sessão de pytest inteira, com este `conftest` como plugin e um `HOME` real de mentira."""
    lar = tmp_path / "lar-real"
    real = lar / ".config" / "hefesto-dualsense4unix"
    real.mkdir(parents=True)
    sinal = tmp_path / "sinal"
    sinal.mkdir()
    teste = tmp_path / "test_dentro.py"
    teste.write_text(_DENTRO, encoding="utf-8")
    env = {
        "HOME": str(lar), "PATH": os.environ["PATH"], "PYTHONPATH": str(RAIZ / "src"),
        "HEFESTO_SINAL": str(sinal), "HEFESTO_MODO": modo, "HEFESTO_LAR_REAL": str(lar),
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
    }
    env["PATH"] = f"{_diario_de_mentira(tmp_path)}{os.pathsep}{env['PATH']}"
    filho = subprocess.Popen(
        [sys.executable, "-m", "pytest", "-p", "tests.conftest", "-p", "no:cacheprovider",
         "--rootdir", str(tmp_path), "-q", str(teste)],
        cwd=RAIZ, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    limite = time.monotonic() + 60
    while not (sinal / "pronto").exists() and filho.poll() is None and time.monotonic() < limite:
        time.sleep(0.05)
    if modo in ("vivo", "mudo"):
        (real / ARQUIVO).write_text('{"perfil": "viajante"}\n', encoding="utf-8")
    (sinal / "liberar").write_text("1")
    saida, _ = filho.communicate(timeout=120)
    return filho.returncode, saida


def test_sessao_inteira_com_o_servico_gravando_nao_reprova(tmp_path: Path) -> None:
    status, saida = _sessao_interna(tmp_path, "vivo")

    assert status == 0, saida
    assert "nenhum escrevente da suíte" in saida


def test_sessao_inteira_com_a_escrita_de_fora_e_o_servico_mudo_reprova(tmp_path: Path) -> None:
    status, saida = _sessao_interna(tmp_path, "mudo")

    assert status != 0, saida
    assert "a suíte ESCREVEU" in saida and ARQUIVO in saida


def test_sessao_inteira_com_teste_que_grava_no_lar_real_reprova(tmp_path: Path) -> None:
    status, saida = _sessao_interna(tmp_path, "teste")

    assert status != 0, saida
    assert "a suíte tentou alcançar o serviço ou o lar real" in saida


def test_sessao_inteira_com_filho_que_grava_no_lar_real_reprova(tmp_path: Path) -> None:
    status, saida = _sessao_interna(tmp_path, "filho")

    assert status != 0, saida
    assert "do_filho.json" in saida and "filho lançado com o lar real" in saida
