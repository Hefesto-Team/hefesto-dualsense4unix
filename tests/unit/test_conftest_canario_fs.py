"""CANARIO-FS-01 — a suíte escreveu no ``$HOME`` de verdade?

O PORQUÊ, medido em 04/08/2026: os perfis dela foram encontrados corrompidos e
a pergunta que ficou sem resposta foi *"como sabemos se algum teste ou algo a
mais corrompeu algo?"*. A fixture `_hefesto_fake_env` isola os diretórios XDG,
mas NÃO isola o ``HOME``, e há constantes de módulo com `Path.home()` avaliadas
na importação (`integrations/storm_doctor.py:34`,
`app/actions/emulation_actions.py:718`) — nenhuma fixture alcança um valor que
já foi calculado no import.

O canário responde a pergunta por medição. Estes testes provam as duas metades
do contrato dele: ele PEGA a escrita, e ele NÃO reclama do que a máquina viva
faz ao lado (senão vira alarme que se aprende a ignorar).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from tests import conftest as canario


class _SessaoFalsa:
    """O mínimo que `pytest_sessionfinish` toca numa Session."""

    def __init__(self) -> None:
        self.exitstatus = 0
        self.config = None


def _lar_falso(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Um ``$HOME`` de mentira com a árvore que o canário vigia."""
    lar = tmp_path / "lar"
    (lar / ".config" / "hefesto-dualsense4unix" / "profiles").mkdir(parents=True)
    (lar / ".config" / "wireplumber").mkdir(parents=True)
    (lar / ".local" / "share" / "hefesto-dualsense4unix").mkdir(parents=True)
    (lar / ".config" / "hefesto-dualsense4unix" / "profiles" / "vitoria.json").write_text(
        '{"name": "vitoria", "match": {"type": "any"}, "priority": 0}\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(lar))
    monkeypatch.delenv(canario._CANARIO_DESLIGADO_ENV, raising=False)
    return lar


def test_canario_vigia_os_tres_diretorios_reais(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Os alvos são resolvidos contra o ``HOME`` VIVO, não contra um valor fixo."""
    lar = _lar_falso(tmp_path, monkeypatch)
    raizes = canario._canario_raizes()
    assert raizes == [
        lar / ".config/hefesto-dualsense4unix",
        lar / ".config/wireplumber",
        lar / ".local/share/hefesto-dualsense4unix",
    ]


def test_escrita_em_perfil_real_vira_delta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Um teste que grava no perfil DELA aparece nomeado no relatório.

    MORDIDA: arrancar a comparação de conteúdo (`_deltas_do_canario`) faz esta
    asserção reprovar — e é ela que descreve o defeito que se quer pegar.
    """
    lar = _lar_falso(tmp_path, monkeypatch)
    antes = canario._fotografar_tudo()

    perfil = lar / ".config/hefesto-dualsense4unix/profiles/vitoria.json"
    perfil.write_text(
        '{"name": "vitoria", "match": {"type": "any"}, "priority": 191}\n',
        encoding="utf-8",
    )

    deltas = canario._deltas_do_canario(antes, canario._fotografar_tudo())
    assert any("MUDADO" in d and "vitoria.json" in d for d in deltas), deltas


def test_arquivo_novo_e_apagado_tambem_contam(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Criar e apagar em ``$HOME`` são deltas — inclusive no wireplumber."""
    lar = _lar_falso(tmp_path, monkeypatch)
    antes = canario._fotografar_tudo()

    (lar / ".config/wireplumber/52-hefesto.conf").write_text("x\n", encoding="utf-8")
    (lar / ".config/hefesto-dualsense4unix/profiles/vitoria.json").unlink()

    deltas = canario._deltas_do_canario(antes, canario._fotografar_tudo())
    assert any(d.startswith("CRIADO") and "52-hefesto.conf" in d for d in deltas), deltas
    assert any(d.startswith("APAGADO") and "vitoria.json" in d for d in deltas), deltas


def test_mtime_sozinho_nao_acusa_ninguem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Toque de mtime SEM mudança de conteúdo não é delta.

    Isto não é folga: é a medição de 05/08. Com o daemon e a janela dela de pé,
    os `*.json.lock` mudam de mtime a cada poucos segundos (o `filelock` toca o
    arquivo a cada aquisição), e um canário que reprovasse por isso acusaria a
    suíte do que o daemon fez — e seria desligado na primeira semana.

    MORDIDA: voltar a comparar a tupla inteira (com mtime_ns) reprova aqui.
    """
    lar = _lar_falso(tmp_path, monkeypatch)
    trava = lar / ".config/hefesto-dualsense4unix/profiles/vitoria.json.lock"
    trava.write_bytes(b"")
    antes = canario._fotografar_tudo()

    futuro = (os.stat(trava).st_mtime_ns + 5_000_000_000) / 1e9
    os.utime(trava, (futuro, futuro))

    assert canario._deltas_do_canario(antes, canario._fotografar_tudo()) == []


def test_sessionfinish_reprova_a_sessao_com_delta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A sessão inteira REPROVA quando o canário encontra rastro.

    MORDIDA: tirar o `session.exitstatus = 1` do fim de `pytest_sessionfinish`
    faz esta asserção reprovar — e é ela que transforma o relatório em portão.
    """
    lar = _lar_falso(tmp_path, monkeypatch)
    monkeypatch.setattr(canario, "_CANARIO_FOTO_INICIAL", canario._fotografar_tudo())
    monkeypatch.setattr(canario, "_CANARIO_ARMADO", True)
    (lar / ".local/share/hefesto-dualsense4unix/plugin.py").write_text(
        "print('oi')\n", encoding="utf-8"
    )

    sessao: Any = _SessaoFalsa()
    canario.pytest_sessionfinish(sessao, 0)

    assert sessao.exitstatus == 1
    saida = capsys.readouterr().out
    assert "CANARIO-FS-01" in saida
    assert "plugin.py" in saida


def test_sessionfinish_calado_quando_nada_mudou(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Suíte hermética = canário invisível (e sessão intacta)."""
    _lar_falso(tmp_path, monkeypatch)
    monkeypatch.setattr(canario, "_CANARIO_FOTO_INICIAL", canario._fotografar_tudo())
    monkeypatch.setattr(canario, "_CANARIO_ARMADO", True)

    sessao: Any = _SessaoFalsa()
    canario.pytest_sessionfinish(sessao, 0)

    assert sessao.exitstatus == 0
    assert "CANARIO-FS-01" not in capsys.readouterr().out


def test_escotilha_de_saida_desliga_o_canario(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Com a escotilha ligada, o canário não fotografa nem reprova."""
    lar = _lar_falso(tmp_path, monkeypatch)
    monkeypatch.setattr(canario, "_CANARIO_FOTO_INICIAL", canario._fotografar_tudo())
    monkeypatch.setattr(canario, "_CANARIO_ARMADO", True)
    monkeypatch.setenv(canario._CANARIO_DESLIGADO_ENV, "1")
    (lar / ".config/hefesto-dualsense4unix/session.json").write_text("{}", encoding="utf-8")

    sessao: Any = _SessaoFalsa()
    canario.pytest_sessionfinish(sessao, 0)
    assert sessao.exitstatus == 0


def test_home_sem_a_arvore_nao_estoura(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Máquina limpa (CI): diretórios ausentes = foto vazia, sem exceção."""
    monkeypatch.setenv("HOME", str(tmp_path / "lar-vazio"))
    assert canario._fotografar_tudo() == {}


def test_canario_desarmado_nao_acusa_o_home_inteiro(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem a foto inicial, o canário fica QUIETO em vez de acusar tudo.

    Uma sessão que começou com o canário desligado e terminou com ele ligado
    compararia contra um dicionário vazio: cada arquivo do ``$HOME`` viraria
    "CRIADO durante a suíte". É o alarme mais falso que existe, e o selo
    `_CANARIO_ARMADO` é o que o impede.

    MORDIDA: tirar o `not _CANARIO_ARMADO` da guarda de `pytest_sessionfinish`
    faz esta sessão reprovar com a árvore inteira na lista.
    """
    _lar_falso(tmp_path, monkeypatch)
    monkeypatch.setattr(canario, "_CANARIO_FOTO_INICIAL", {})
    monkeypatch.setattr(canario, "_CANARIO_ARMADO", False)

    sessao: Any = _SessaoFalsa()
    canario.pytest_sessionfinish(sessao, 0)
    assert sessao.exitstatus == 0
