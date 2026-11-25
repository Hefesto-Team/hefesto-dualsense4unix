"""O doctor para colar num relato público sai na máscara da casa.

D-2511-O-DOCTOR-PARA-COLAR-SAI-NA-MASCARA: `doctor --para-colar` passa toda linha (a do
`doctor.sh` e a dos blocos em Python) pela máscara: nenhum endereço inteiro, o home em `~`, sem o
nome da conta. Sem a opção a saída segue igual.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli import cmd_doctor
from hefesto_dualsense4unix.cli.app import app

RAIZ = Path(__file__).resolve().parents[2]
CONTA = "contaficticia"
HOME = f"/home/{CONTA}"
ENDERECO = "aa:bb:cc:dd:ee:ff"
ENDERECO_NA_PERNA = f"{ENDERECO[:8]}:00:00:ff"
FORMAS_DO_ENDERECO = (
    "aa:bb:cc:dd:ee:ff",
    "aa-bb-cc-dd-ee-ff",
    "dev_AA_BB_CC_DD_EE_FF",
    "aabbccddeeff",
)
_O_MIOLO = re.compile(r"dd[:\-_.]?ee", re.IGNORECASE)


def _o_sh_de_mentira(pasta: Path) -> Path:
    corpo = ["#!/usr/bin/env bash"]
    corpo += [f"printf '[WARN] controle %s sem pareamento\\n' '{f}'" for f in FORMAS_DO_ENDERECO]
    corpo += [
        f"printf '[FAIL] sem a pasta {HOME}/.config/hefesto (conta %s)\\n' '{CONTA}'",
        f"printf '[INFO] %s\\n' 'o stderr do script também: {ENDERECO}' >&2",
        "exit 1",
    ]
    sh = pasta / "doctor.sh"
    sh.write_text("\n".join(corpo) + "\n", encoding="utf-8")
    return sh


@pytest.fixture
def conta(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("HOME", HOME)
    monkeypatch.setenv("LOGNAME", CONTA)
    monkeypatch.setenv("USER", CONTA)
    sh = _o_sh_de_mentira(tmp_path)
    monkeypatch.setattr(cmd_doctor, "_find_doctor_sh", lambda: sh)
    return sh


def _rodar_o_sh(capfd: pytest.CaptureFixture[str], para_colar: bool) -> tuple[int, str]:
    cmd_doctor._SAIDA.para_colar = para_colar
    try:
        rc = cmd_doctor._rodar_o_doctor_sh(fix=False, quiet=False)
    finally:
        cmd_doctor._SAIDA.para_colar = False
    saida = capfd.readouterr()
    return rc, saida.out + saida.err


def test_a_saida_de_colar_do_doctor_sh_nao_traz_endereco_nem_conta(
    conta: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """D-2511-O-DOCTOR-PARA-COLAR-SAI-NA-MASCARA: sem endereço inteiro, sem a conta e o home."""
    rc, saida = _rodar_o_sh(capfd, para_colar=True)
    assert rc == cmd_doctor._GRAVIDADE_FAIL
    assert not _O_MIOLO.search(saida), saida
    assert CONTA not in saida, saida
    assert HOME not in saida, saida
    assert "~/.config/hefesto" in saida
    assert saida.count(ENDERECO_NA_PERNA) == 2, saida
    assert "o stderr do script também" in saida


def test_sem_a_opcao_a_saida_segue_igual(conta: Path, capfd: pytest.CaptureFixture[str]) -> None:
    rc, saida = _rodar_o_sh(capfd, para_colar=False)
    assert rc == cmd_doctor._GRAVIDADE_FAIL
    for forma in FORMAS_DO_ENDERECO:
        assert forma in saida
    assert f"{HOME}/.config/hefesto" in saida
    assert CONTA in saida


def test_os_blocos_em_python_saem_na_mascara(
    conta: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    linhas = [
        ("[WARN]", f"o controle {ENDERECO} está no bond de {HOME}/.local/state"),
        ("[ OK ]", f"conta {CONTA}"),
    ]
    cmd_doctor._SAIDA.para_colar = True
    try:
        cmd_doctor._bloco("bloco de teste", linhas)
        cmd_doctor._SAIDA.como_json = True
        cmd_doctor._bloco("bloco de teste", linhas)
    finally:
        cmd_doctor._SAIDA.para_colar = False
        cmd_doctor._SAIDA.como_json = False
        achados = cmd_doctor._SAIDA.achados
        cmd_doctor._SAIDA.achados = []
    texto = capsys.readouterr().out
    em_json = json.dumps(achados)
    for saida in (texto, em_json):
        assert not _O_MIOLO.search(saida), saida
        assert CONTA not in saida and HOME not in saida, saida
    assert ENDERECO_NA_PERNA in texto
    assert "~/.local/state" in texto


def test_a_opcao_chega_ao_comando(monkeypatch: pytest.MonkeyPatch) -> None:
    pedidos: dict[str, Any] = {}
    monkeypatch.setattr(cmd_doctor, "doctor_cmd", lambda **kw: pedidos.update(kw))
    resultado = CliRunner().invoke(app, ["doctor", "--para-colar"])
    assert resultado.exit_code == 0, resultado.output
    assert pedidos["para_colar"] is True
    CliRunner().invoke(app, ["doctor"])
    assert pedidos["para_colar"] is False


def _triagem() -> Any:
    spec = importlib.util.spec_from_file_location(
        "triagem_do_doctor_para_colar", RAIZ / "scripts" / "github" / "triagem.py"
    )
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["triagem_do_doctor_para_colar"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _corpo(doctor: str) -> str:
    campo = f"### Saída do doctor\n\n```shell\n{doctor}\n```"
    return f"### O que aconteceu\n\nx\n\n{campo}\n\n### Mais\n\ny"


def test_a_triagem_pede_para_editar_a_issue_com_endereco_inteiro() -> None:
    t = _triagem()
    cru = f"[WARN] o controle {ENDERECO} está pela metade e o resto da saida"
    for acao in ("opened", "edited"):
        d = t.decidir(_corpo(cru), ["bug"], acao)
        assert d == {"adicionar": [t.ROTULO], "remover": [], "comentar": True, "endereco": True}
    assert "--para-colar" in t.COMENTARIO_DO_ENDERECO
    assert "edite a issue" in t.COMENTARIO_DO_ENDERECO


def test_a_triagem_aceita_a_saida_mascarada_e_tira_o_rotulo_depois_da_edicao() -> None:
    t = _triagem()
    mascarada = f"[WARN] o controle {ENDERECO_NA_PERNA} está pela metade e o resto da saida"
    assert t.decidir(_corpo(mascarada), ["bug"], "opened") == {
        "adicionar": [], "remover": [], "comentar": False,
    }
    assert t.decidir(_corpo(mascarada), ["bug", t.ROTULO], "edited") == {
        "adicionar": [], "remover": [t.ROTULO], "comentar": False,
    }
    cru = f"[WARN] o controle {ENDERECO} está pela metade e o resto da saida"
    assert t.decidir(_corpo(cru), ["bug", t.ROTULO], "edited") == {
        "adicionar": [], "remover": [], "comentar": False,
    }


@pytest.mark.parametrize(
    "caminho",
    [
        ".github/ISSUE_TEMPLATE/bug.yml",
        ".github/ISSUE_TEMPLATE/jogo.yml",
        "README.md",
        "docs/usage/troubleshooting.md",
    ],
)
def test_todo_lugar_que_pede_a_saida_em_publico_pede_a_de_colar(caminho: str) -> None:
    texto = (RAIZ / caminho).read_text(encoding="utf-8")
    assert "doctor --para-colar" in texto
    for achado in re.finditer(r"`hefesto-dualsense4unix doctor([^`]*)`", texto):
        trecho = texto[max(0, achado.start() - 80) : achado.end() + 80]
        if "cole" in trecho or "relato" in trecho or "Issues" in trecho:
            assert "--para-colar" in achado.group(1), trecho


def test_o_comentario_da_triagem_pede_o_doctor_de_colar() -> None:
    t = _triagem()
    assert "doctor --para-colar" in t.COMENTARIO
