"""O-CANARIO-NAO-FOTOGRAFA-A-CASA-01 — a foto do canário tem teto, e o link não é caminho."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests import conftest as canario

TETO = 20


class _SessaoFalsa:
    """O mínimo que `pytest_sessionfinish` toca numa Session."""

    def __init__(self) -> None:
        self.exitstatus = 0
        self.config = None


def _lar_falso(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Um ``$HOME`` de mentira com as árvores que o canário vigia, e o teto baixo."""
    lar = tmp_path / "lar"
    estado = lar / ".local" / "state" / "hefesto-dualsense4unix"
    (lar / ".config" / "hefesto-dualsense4unix" / "profiles").mkdir(parents=True)
    (lar / ".config" / "wireplumber").mkdir(parents=True)
    (lar / ".local" / "share" / "hefesto-dualsense4unix").mkdir(parents=True)
    (estado / "launch_env").mkdir(parents=True)
    (lar / ".config" / "hefesto-dualsense4unix" / "profiles" / "vitoria.json").write_text(
        '{"name": "vitoria"}\n', encoding="utf-8"
    )
    (estado / "launch_env" / "default.env").write_text("A=1\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(lar))
    monkeypatch.delenv(canario._CANARIO_DESLIGADO_ENV, raising=False)
    monkeypatch.setattr(canario, "_CANARIO_TETO_ENTRADAS", TETO)
    monkeypatch.setattr(canario, "_deltas_do_congelado", lambda: [])
    return lar


def _estado(lar: Path) -> Path:
    return lar / ".local" / "state" / "hefesto-dualsense4unix"


def _encher(pasta: Path, quantos: int) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    for n in range(quantos):
        (pasta / f"f{n:05d}.txt").write_text(str(n), encoding="utf-8")


def _contar_resumos(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    chamadas: list[str] = []
    original = canario._resumo_do_arquivo

    def _contado(caminho: Path, tamanho: int) -> str:
        chamadas.append(str(caminho))
        return original(caminho, tamanho)

    monkeypatch.setattr(canario, "_resumo_do_arquivo", _contado)
    return chamadas


def _armar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(canario, "_CANARIO_FOTO_INICIAL", canario._fotografar_tudo())
    monkeypatch.setattr(
        canario, "_CANARIO_FOTO_AVISO", canario._fotografar_tudo_de_aviso()
    )
    monkeypatch.setattr(canario, "_CANARIO_ARMADO", True)


def test_o_custo_da_foto_tem_teto_qualquer_que_seja_o_nome_do_filho(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Um filho de nome qualquer com 3x o teto não custa mais que o teto."""
    lar = _lar_falso(tmp_path, monkeypatch)
    _encher(_estado(lar) / "uma-pasta-qualquer", 3 * TETO)
    chamadas = _contar_resumos(monkeypatch)

    foto = canario._fotografar_tudo_de_aviso()

    resto = 1  # launch_env/default.env
    assert len(chamadas) <= TETO + resto, len(chamadas)
    pasta = str(_estado(lar) / "uma-pasta-qualquer")
    assert foto[pasta][2] == canario._CANARIO_PESADO
    assert not [c for c in foto if c.startswith(pasta + "/")], "entrou na pasta pesada"


def test_o_teto_de_hoje_nao_corta_o_perfil_dela(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Com o teto de verdade, o `profiles/` (286 entradas em 06/10) fica inteiro, com sha256."""
    lar = tmp_path / "lar"
    perfis = lar / ".config" / "hefesto-dualsense4unix" / "profiles"
    _encher(perfis, 286)
    monkeypatch.setenv("HOME", str(lar))

    foto = canario._fotografar_tudo()

    arquivos = [c for c in foto if c.startswith(str(perfis) + "/")]
    assert len(arquivos) == 286
    assert all(foto[c][2] for c in arquivos)
    assert canario._CANARIO_PESADO not in {v[2] for v in foto.values()}


def test_o_canario_nao_fica_cego_com_um_filho_pesado_no_lugar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Escrita em `launch_env/` aparece no aviso e em `profiles/` reprova a sessão."""
    lar = _lar_falso(tmp_path, monkeypatch)
    _encher(_estado(lar) / "uma-pasta-qualquer", 3 * TETO)
    _encher(lar / ".config" / "hefesto-dualsense4unix" / "outra-pesada", 3 * TETO)
    _armar(monkeypatch)
    (_estado(lar) / "launch_env" / "default.env").write_text("A=2\n", encoding="utf-8")
    (lar / ".config/hefesto-dualsense4unix/profiles/vitoria.json").write_text(
        '{"name": "outra"}\n', encoding="utf-8"
    )

    sessao: Any = _SessaoFalsa()
    canario.pytest_sessionfinish(sessao, 0)

    saida = capsys.readouterr().out
    assert "aviso, não é portão" in saida
    assert "default.env" in saida
    assert "vitoria.json" in saida
    assert sessao.exitstatus == 1


def test_o_pesado_que_nasce_no_meio_e_uma_linha_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nasce pesado: um CRIADO. Já era pesado e encolhe: nenhum delta."""
    lar = _lar_falso(tmp_path, monkeypatch)
    _encher(_estado(lar) / "ja-era-pesado", 3 * TETO)
    antes = canario._fotografar_tudo_de_aviso()

    _encher(_estado(lar) / "nasceu-pesado", 3 * TETO)
    for arquivo in sorted((_estado(lar) / "ja-era-pesado").iterdir())[1:]:
        arquivo.unlink()

    deltas = canario._deltas_do_canario(
        antes, canario._fotografar_tudo_de_aviso(antes)
    )
    assert deltas == [f"CRIADO   {_estado(lar) / 'nasceu-pesado'}"], deltas


def test_o_pesado_que_some_aparece_como_apagado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fixar a lista não esconde quem foi embora: a pasta pesada apagada é um APAGADO."""
    lar = _lar_falso(tmp_path, monkeypatch)
    _encher(_estado(lar) / "ja-era-pesado", 3 * TETO)
    antes = canario._fotografar_tudo_de_aviso()
    for arquivo in (_estado(lar) / "ja-era-pesado").iterdir():
        arquivo.unlink()
    (_estado(lar) / "ja-era-pesado").rmdir()

    deltas = canario._deltas_do_canario(
        antes, canario._fotografar_tudo_de_aviso(antes)
    )
    assert deltas == [f"APAGADO  {_estado(lar) / 'ja-era-pesado'}"], deltas


def test_o_primeiro_nivel_pesado_vira_a_arvore_inteira_numa_entrada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Se o primeiro nível sozinho passa do teto, a árvore é uma entrada só."""
    lar = _lar_falso(tmp_path, monkeypatch)
    _encher(_estado(lar), 3 * TETO)
    chamadas = _contar_resumos(monkeypatch)

    foto = canario._fotografar_tudo_de_aviso()

    assert foto == {str(_estado(lar)): (0, 0, canario._CANARIO_PESADO)}
    assert chamadas == []


def test_o_link_nao_e_seguido_e_so_o_de_fora_e_nomeado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Link para pasta de fora pesada: o contador não estoura e o relato o nomeia."""
    lar = _lar_falso(tmp_path, monkeypatch)
    fora = tmp_path / "fora-da-arvore"
    _encher(fora, 3 * TETO)
    (_estado(lar) / "casa-de-fora").symlink_to(fora)
    (_estado(lar) / "kernel.log").write_text("k\n", encoding="utf-8")
    (_estado(lar) / "storm.log").symlink_to("kernel.log")
    chamadas = _contar_resumos(monkeypatch)

    _armar(monkeypatch)
    resumos_da_foto = len(chamadas)
    sessao: Any = _SessaoFalsa()
    canario.pytest_sessionfinish(sessao, 0)

    assert resumos_da_foto <= 3, resumos_da_foto  # vitoria.json, default.env, kernel.log
    assert not [c for c in chamadas if "fora-da-arvore" in c]
    saida = capsys.readouterr().out
    assert "casa-de-fora" in saida
    assert "storm.log" not in saida
    assert "1 link(s) para fora" in saida
    assert sessao.exitstatus == 0


def test_trocar_o_alvo_do_link_conta_como_mudanca(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O link entra pelo `lstat` com o alvo no lugar do resumo."""
    lar = _lar_falso(tmp_path, monkeypatch)
    um, dois = tmp_path / "um", tmp_path / "dois"
    um.mkdir()
    dois.mkdir()
    ligacao = _estado(lar) / "casa"
    ligacao.symlink_to(um)
    antes = canario._fotografar_tudo_de_aviso()
    ligacao.unlink()
    ligacao.symlink_to(dois)

    deltas = canario._deltas_do_canario(antes, canario._fotografar_tudo_de_aviso())
    assert len(deltas) == 1
    assert deltas[0].startswith("MUDADO") and "casa" in deltas[0]


def test_o_relato_chega_no_fim_da_sessao_e_nao_reprova(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Com pesado e link para fora, o bloco sai do `sessionfinish` (o `-q` não o esconde)."""
    lar = _lar_falso(tmp_path, monkeypatch)
    _encher(_estado(lar) / "uma-pasta-qualquer", 3 * TETO)
    (_estado(lar) / "casa-de-fora").symlink_to(tmp_path)
    _armar(monkeypatch)

    sessao: Any = _SessaoFalsa()
    canario.pytest_sessionfinish(sessao, 0)

    saida = capsys.readouterr().out
    assert "CANARIO-FS-01 (relato, não é portão)" in saida
    assert ".local/state/hefesto-dualsense4unix: 1 pasta(s) pesada(s) e 1 link(s)" in saida
    assert "uma-pasta-qualquer" in saida
    assert "o state do produto não guarda a casa" in saida
    assert "~/.local/state/hefesto-casa/" in saida
    assert sessao.exitstatus == 0, "o relato NÃO pode reprovar a sessão"


def test_o_relato_cita_no_maximo_tres_nomes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    lar = _lar_falso(tmp_path, monkeypatch)
    for n in range(5):
        (_estado(lar) / f"fora-{n}").symlink_to(tmp_path)
    _armar(monkeypatch)

    canario.pytest_sessionfinish(_SessaoFalsa(), 0)

    saida = capsys.readouterr().out
    assert "5 link(s) para fora" in saida
    assert "fora-0, fora-1, fora-2)" in saida
    assert "fora-3" not in saida


def test_sem_pesado_nem_link_para_fora_nao_ha_linha_do_bloco(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Árvore pequena e com link para dentro: nada do bloco aparece."""
    lar = _lar_falso(tmp_path, monkeypatch)
    (_estado(lar) / "kernel.log").write_text("k\n", encoding="utf-8")
    (_estado(lar) / "storm.log").symlink_to("kernel.log")
    _armar(monkeypatch)

    sessao: Any = _SessaoFalsa()
    canario.pytest_sessionfinish(sessao, 0)

    saida = capsys.readouterr().out
    assert "CANARIO-FS-01" not in saida
    assert "o canário não entrou" not in saida
    assert "hefesto-casa" not in saida
    assert sessao.exitstatus == 0


def test_a_escotilha_cala_o_relato(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    lar = _lar_falso(tmp_path, monkeypatch)
    (_estado(lar) / "casa-de-fora").symlink_to(tmp_path)
    _armar(monkeypatch)
    monkeypatch.setenv(canario._CANARIO_DESLIGADO_ENV, "1")

    canario.pytest_sessionfinish(_SessaoFalsa(), 0)

    assert "CANARIO-FS-01" not in capsys.readouterr().out
