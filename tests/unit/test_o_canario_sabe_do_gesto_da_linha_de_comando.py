"""O canário sabe que a extensão se mexeu pelo gesto de quem usa, e não pela suíte.

A sprint é a O-CANARIO-SABE-QUE-A-EXTENSAO-SE-ATUALIZOU-PELA-LINHA-DE-COMANDO-01. O
``mod atualizar`` rodado à mão no lar de verdade, no meio de uma suíte, escrevia o ``mods.json``
e a pasta do código, e o canário pegava essa escrita como da suíte. Todo gesto do instalador que
muda o lar anota, no diário dos gestos das extensões, a linha ``[gesto]`` com os caminhos que
toca; o canário rebaixa a aviso só a mudança dentro desses caminhos, no intervalo da sessão.

Dois lares de mentira: ``real`` é o que o canário vigia (o papel do lar de quem roda), e o
outro é o dos testes. Extensões FALSAS, de tema e sem processo.
"""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli import cmd_mod
from hefesto_dualsense4unix.mods import instalador
from tests import conftest as canario

PRODUTO = "hefesto-dualsense4unix"
MOD = "brilho-falso"
OUTRA = "sombra-falsa"


class _SessaoFalsa:
    def __init__(self) -> None:
        self.exitstatus = 0
        self.config = None


def _fonte(raiz: Path, mod_id: str = MOD, versao: str = "1.0.0") -> Path:
    pasta = raiz / "fontes" / mod_id
    pasta.mkdir(parents=True, exist_ok=True)
    manifesto: dict[str, Any] = {
        "id": mod_id, "nome": "Brilho falso", "versao": versao,  # (noqa-acento)
        "api": ">=2,<3", "licenca": "MIT", "tipos": ["tema"], "tema": {},
        "permissoes": [], "descricao": "Muda um detalhe.", "opcoes": [],  # (noqa-acento)
    }
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    (pasta / "CHANGELOG.md").write_text(f"# {versao}\n", encoding="utf-8")
    return pasta


def _morar_em(lar: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(lar))
    for var in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(lar / "run"))


def _diario(lar: Path) -> Path:
    return lar / ".local" / "state" / PRODUTO / instalador.DIARIO_DOS_GESTOS


def _mod(*argumentos: str) -> None:
    saiu = CliRunner().invoke(cmd_mod.app, list(argumentos))
    assert saiu.exit_code == 0, saiu.output


@pytest.fixture
def real(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """O lar que o canário vigia, com a extensão já instalada antes da sessão começar."""
    lar = tmp_path / "real"
    (lar / ".config" / PRODUTO / "profiles").mkdir(parents=True)
    (lar / ".local" / "state" / PRODUTO).mkdir(parents=True)
    (lar / "run").mkdir()
    _morar_em(lar, monkeypatch)
    _mod("instalar", str(_fonte(tmp_path)))
    _diario(lar).unlink(missing_ok=True)
    return lar


def _armar(lar: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _morar_em(lar, monkeypatch)
    monkeypatch.delenv(canario._CANARIO_DESLIGADO_ENV, raising=False)
    monkeypatch.setattr(canario, "_deltas_do_congelado", lambda: [])
    monkeypatch.setattr(canario, "_gestos_da_janela_do_usuario", lambda: [])
    monkeypatch.setattr(canario, "_GUARDA_DA_SESSAO", [])
    monkeypatch.setattr(canario, "escritas_do_servico_no_journal", lambda _desde: frozenset())
    monkeypatch.setattr(
        canario, "_INICIO_DA_SESSAO", [datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    monkeypatch.setattr(canario, "_DIARIO_DOS_GESTOS", [_diario(lar)], raising=False)
    monkeypatch.setattr(canario, "_CANARIO_FOTO_AVISO", canario._fotografar_tudo_de_aviso())
    monkeypatch.setattr(canario, "_CANARIO_FOTO_INICIAL", canario._fotografar_tudo())
    monkeypatch.setattr(canario, "_CANARIO_ARMADO", True)


def _fechar(capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    sessao = _SessaoFalsa()
    capsys.readouterr()
    canario._sessionfinish_das_guardas(sessao)
    return sessao.exitstatus, capsys.readouterr().out


def _portao(saida: str) -> list[str]:
    inicio = saida.find("CANARIO-FS-01: a suíte ESCREVEU")
    return [] if inicio < 0 else saida[inicio:].splitlines()


def test_o_mod_atualizar_no_meio_da_sessao_e_aviso_com_o_gesto(
    real: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _armar(real, monkeypatch)
    _fonte(tmp_path, versao="1.1.0")
    _mod("atualizar", MOD)

    status, saida = _fechar(capsys)

    assert status == 0 and _portao(saida) == [], saida
    assert f"gesto: [gesto] mod atualizar {MOD}" in saida, saida
    assert "mods.json" in saida and f"mods/{MOD}/CHANGELOG.md" in saida, saida


def test_a_mesma_escrita_sem_o_gesto_reprova_como_antes(
    real: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    _armar(real, monkeypatch)
    lugares = instalador.Lugares.do_xdg()
    registro = instalador.ler_registro(lugares.registro)
    registro[MOD].versao = "1.1.0"
    instalador.gravar_registro(lugares.registro, registro)
    (lugares.codigo / MOD / "CHANGELOG.md").write_text("# 1.1.0\n", encoding="utf-8")

    status, saida = _fechar(capsys)

    portao = "\n".join(_portao(saida))
    assert status == 1, saida
    assert "mods.json" in portao and f"mods/{MOD}/CHANGELOG.md" in portao, saida
    assert "CANARIO-FS-01 PORTÃO" in portao


def test_a_escrita_fora_dos_caminhos_do_gesto_segue_portao(
    real: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _armar(real, monkeypatch)
    _fonte(tmp_path, versao="1.1.0")
    _mod("atualizar", MOD)
    (real / ".config" / PRODUTO / "profiles" / "planeta.json").write_text("{}\n")
    vizinha = real / ".local" / "share" / PRODUTO / "mods" / OUTRA
    vizinha.mkdir()
    (vizinha / "hefesto-mod.json").write_text("{}\n")

    status, saida = _fechar(capsys)

    portao = "\n".join(_portao(saida))
    assert status == 1, saida
    assert "profiles/planeta.json" in portao and f"mods/{OUTRA}" in portao, saida
    assert "mods.json" not in portao and f"mods/{MOD}/" not in portao, saida
    assert f"gesto: [gesto] mod atualizar {MOD}" in saida


def test_o_gesto_de_antes_da_sessao_nao_cobre_a_escrita_de_agora(
    real: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    _armar(real, monkeypatch)
    lugares = instalador.Lugares.do_xdg()
    caminhos = [str(lugares.codigo / MOD), str(lugares.dados / MOD), str(lugares.registro)]
    _diario(real).write_text(
        f"2000-01-01 00:00:00 [gesto] mod atualizar {MOD} → {json.dumps(caminhos)}\n",
        encoding="utf-8")
    (lugares.codigo / MOD / "CHANGELOG.md").write_text("# outra\n", encoding="utf-8")

    status, saida = _fechar(capsys)

    assert status == 1 and f"mods/{MOD}/CHANGELOG.md" in "\n".join(_portao(saida)), saida


def test_o_gesto_no_lar_de_mentira_nunca_anota_no_lar_de_verdade(
    real: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _armar(real, monkeypatch)
    dos_testes = tmp_path / "dos-testes"
    (dos_testes / "run").mkdir(parents=True)
    _morar_em(dos_testes, monkeypatch)
    _mod("instalar", str(_fonte(tmp_path, OUTRA)))
    _mod("ligar", OUTRA, "--sim")
    _morar_em(real, monkeypatch)

    assert _diario(dos_testes).is_file()
    assert not _diario(real).exists()
    assert canario._gestos_das_extensoes_na_sessao() == []
    status, saida = _fechar(capsys)
    assert status == 0 and "CANARIO-FS-01" not in saida, saida


@pytest.mark.parametrize(
    ("argumentos", "verbo"),
    [
        (("ligar", MOD, "--sim"), "ligar"),
        (("desligar", MOD), "desligar"),
        (("remover", MOD), "remover"),
        (("atualizar", MOD), "atualizar"),
    ],
)
def test_todo_comando_que_muda_o_lar_anota_o_gesto_com_os_caminhos(
    real: Path, monkeypatch: pytest.MonkeyPatch, argumentos: tuple[str, ...], verbo: str,
) -> None:
    if verbo == "desligar":
        _mod("ligar", MOD, "--sim")
        _diario(real).unlink()
    _mod(*argumentos)

    gestos = canario.gestos_das_extensoes(_diario(real).read_text(encoding="utf-8"), "")
    lugares = instalador.Lugares.do_xdg()
    assert (f"[gesto] mod {verbo} {MOD}", tuple(str(c) for c in (
        lugares.codigo / MOD, lugares.dados / MOD, lugares.pasta_do_diario(MOD),
        lugares.registro))) in gestos, gestos


def test_o_instalar_anota_antes_de_escrever(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    lar = tmp_path / "novo"
    (lar / "run").mkdir(parents=True)
    _morar_em(lar, monkeypatch)
    _mod("instalar", str(_fonte(tmp_path)))
    gestos = canario.gestos_das_extensoes(_diario(lar).read_text(encoding="utf-8"), "")
    assert [g for g, _c in gestos] == [f"[gesto] mod instalar {MOD}"]


def test_o_canario_le_o_mesmo_diario_que_o_instalador_escreve() -> None:
    assert canario._NOME_DO_DIARIO_DOS_GESTOS == instalador.DIARIO_DOS_GESTOS


def test_o_diario_dos_gestos_tem_teto_e_o_canario_le_a_volta(
    real: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _armar(real, monkeypatch)
    monkeypatch.setattr(instalador, "TETO_DO_DIARIO_DOS_GESTOS_BYTES", 400)
    lugares = instalador.Lugares.do_xdg()
    for _ in range(12):
        instalador.desligar(MOD)
        instalador.ligar(MOD, permissoes_vistas=[])

    diario = _diario(real)
    volta = diario.with_name(diario.name + ".1")
    assert volta.is_file() and os.path.getsize(diario) <= 400 + 400
    assert os.path.getsize(volta) <= 400 + 400
    gestos = canario._gestos_das_extensoes_na_sessao()
    linhas = len(volta.read_text().splitlines()) + len(diario.read_text().splitlines())
    assert len(gestos) == linhas
    assert {g for g, _c in gestos} == {f"[gesto] mod ligar {MOD}", f"[gesto] mod desligar {MOD}"}
    assert all(str(lugares.registro) in c for _g, c in gestos)


def test_o_diario_que_nao_abre_nunca_barra_o_gesto(
    real: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _diario(real).mkdir()
    _fonte(tmp_path, versao="1.1.0")
    _mod("atualizar", MOD)
    _mod("ligar", MOD, "--sim")

    lugares = instalador.Lugares.do_xdg()
    registro = instalador.ler_registro(lugares.registro)
    assert registro[MOD].versao == "1.1.0" and registro[MOD].ligada
    assert _diario(real).is_dir() and not any(_diario(real).iterdir())


def test_o_canario_vigia_o_diario_que_o_produto_escreve_no_lar_real(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert canario._DIARIO_DOS_GESTOS, "a sessão não marcou o diário dos gestos"
    monkeypatch.setenv("HOME", str(canario.lar_real()))
    for var in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
        valor = canario._LAR_ENV_ANTES.get(var)
        if valor:
            monkeypatch.setenv(var, valor)
        else:
            monkeypatch.delenv(var, raising=False)

    assert canario._DIARIO_DOS_GESTOS[0] == instalador.Lugares.do_xdg().diario_dos_gestos


def test_o_gesto_que_corre_enquanto_o_canario_fotografa_tambem_e_aviso(
    real: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _armar(real, monkeypatch)
    _fonte(tmp_path, versao="1.1.0")
    fotografar = canario._fotografar_tudo

    def _com_o_gesto_no_meio(*argumentos: Any) -> Any:
        _mod("atualizar", MOD)
        return fotografar(*argumentos)

    monkeypatch.setattr(canario, "_fotografar_tudo", _com_o_gesto_no_meio)

    status, saida = _fechar(capsys)

    assert status == 0 and _portao(saida) == [], saida
    assert f"gesto: [gesto] mod atualizar {MOD}" in saida, saida
