"""O canário reconhece a escrita que o serviço de verdade anota no diário.

Na partida, o daemon regrava perfis no ``~/.config`` (o semeio do ``loader``). Antes, o canário
só sabia da escrita da janela, e um pytest que coincidia com um restart do daemon reprovava por
uma escrita que a suíte não fez. O serviço anota cada caminho que muda num evento
``escrita_do_servico``; o canário lê esses eventos da unidade e tira do portão só os caminhos
exatos que eles citam.
"""
from __future__ import annotations

import io
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.utils.logging_config import cadeia_do_diario
from tests import conftest as canario


class _SessaoFalsa:
    def __init__(self) -> None:
        self.exitstatus = 0
        self.config = None


def _lar_falso(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    lar = tmp_path / "lar"
    perfis = lar / ".config" / "hefesto-dualsense4unix" / "profiles"
    (perfis / ".historico" / "viajante").mkdir(parents=True)
    (perfis / "viajante.json").write_text('{"name": "viajante"}\n', encoding="utf-8")
    (perfis / "andarilho.json").write_text('{"name": "andarilho"}\n', encoding="utf-8")
    monkeypatch.setenv("HOME", str(lar))
    monkeypatch.delenv(canario._CANARIO_DESLIGADO_ENV, raising=False)
    monkeypatch.setattr(canario, "_CANARIO_FOTO_AVISO", canario._fotografar_tudo_de_aviso())
    monkeypatch.setattr(canario, "_deltas_do_congelado", lambda: [])
    monkeypatch.setattr(canario, "_gestos_da_janela_do_usuario", lambda: [])
    monkeypatch.setattr(canario, "_GUARDA_DA_SESSAO", [])
    monkeypatch.setattr(canario, "_INICIO_DA_SESSAO", ["2026-10-31 06:40:00"])
    monkeypatch.setattr(canario, "_CANARIO_FOTO_INICIAL", canario._fotografar_tudo())
    monkeypatch.setattr(canario, "_CANARIO_ARMADO", True)
    return perfis


def _linha_do_diario(caminho: Path, formato: str) -> str:
    evento: Any = {"event": "escrita_do_servico", "caminho": str(caminho)}
    for processador in cadeia_do_diario(formato, io.StringIO()):
        evento = processador(None, "info", evento)
    return str(evento)


def _diario(monkeypatch: pytest.MonkeyPatch, caminhos: list[Path], formato: str) -> None:
    texto = "\n".join(
        [
            "2026-10-31T07:46:27.706515 [info     ] perfis_no_formato_da_aba_jogar perfis=[]",
            *(_linha_do_diario(c, formato) for c in caminhos),
        ]
    )
    monkeypatch.setattr(
        canario,
        "escritas_do_servico_no_journal",
        lambda desde: canario.caminhos_da_escrita_do_servico(texto),
    )


def _veredito(capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    sessao: Any = _SessaoFalsa()
    canario.pytest_sessionfinish(sessao, 0)
    return sessao.exitstatus, capsys.readouterr().out


def _anotados(registros: Sequence[Mapping[str, Any]]) -> set[str]:
    return {r["caminho"] for r in registros if r.get("event") == "escrita_do_servico"}


@pytest.mark.parametrize("formato", ["console", "json"])
def test_o_perfil_e_o_historico_anotados_pelo_servico_sao_aviso(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    formato: str,
) -> None:
    perfis = _lar_falso(tmp_path, monkeypatch)
    perfil = perfis / "viajante.json"
    copia = perfis / ".historico" / "viajante" / "20261031T074627_706515.json"
    with structlog.testing.capture_logs() as registros, loader._anota_o_perfil(perfil):
        copia.write_bytes(perfil.read_bytes())
        perfil.write_text('{"name": "viajante", "mode": {}}\n', encoding="utf-8")
    anotados = _anotados(registros)
    assert {str(perfil), str(copia)} <= anotados
    _diario(monkeypatch, [Path(c) for c in sorted(anotados)], formato)

    status, saida = _veredito(capsys)

    assert status == 0, saida
    assert canario._GUARDA_PORTAO not in saida
    assert "escrita_do_servico" in saida and str(perfil) in saida and str(copia) in saida


def test_sem_o_evento_a_mesma_mudanca_e_portao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    perfis = _lar_falso(tmp_path, monkeypatch)
    perfil = perfis / "viajante.json"
    copia = perfis / ".historico" / "viajante" / "20261031T074627_706515.json"
    copia.write_bytes(perfil.read_bytes())
    perfil.write_text('{"name": "viajante", "mode": {}}\n', encoding="utf-8")
    _diario(monkeypatch, [], "console")

    status, saida = _veredito(capsys)

    assert status == 1
    assert canario._GUARDA_PORTAO in saida and str(perfil) in saida


def test_o_evento_de_um_perfil_nao_cobre_o_vizinho(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    perfis = _lar_falso(tmp_path, monkeypatch)
    vizinho = perfis / "andarilho.json"
    vizinho.write_text('{"name": "andarilho", "mode": {}}\n', encoding="utf-8")
    _diario(monkeypatch, [perfis / "viajante.json", perfis, perfis / ".historico"], "console")

    status, saida = _veredito(capsys)

    assert status == 1
    portao = saida.split(canario._GUARDA_PORTAO, 1)[-1]
    assert str(vizinho) in portao


_ANTIGO = {
    "name": "Sem Caminho",
    "match": {"type": "criteria", "window_class": ["steam_app_9931001"]},
    "priority": 80,
    "modificado_em": "2026-10-01T12:00:00-03:00",
    "mode": {"kind": "gamepad", "gamepad_flavor": "xbox"},
}


def test_a_migracao_anota_cada_arquivo_que_grava_e_nada_quando_nada_muda(
    tmp_path: Path,
) -> None:
    pasta = tmp_path / "profiles"
    pasta.mkdir()
    perfil = pasta / "sem_caminho.json"
    perfil.write_text(json.dumps(_ANTIGO), encoding="utf-8")

    with structlog.testing.capture_logs() as registros:
        convertidos = loader.todo_perfil_no_formato_da_aba_jogar(pasta)

    assert convertidos == ["sem_caminho.json"]
    gravados = {
        str(c) for c in pasta.rglob("*")
        if c.is_file() and not c.name.endswith(loader.LOCK_SUFFIX)
    }
    copias = list((pasta / loader.HISTORICO_DIR_NAME / "sem_caminho").glob("*.json"))
    assert len(copias) == 1
    anotados = _anotados(registros)
    assert gravados <= anotados, gravados - anotados
    assert {str(perfil), str(copias[0])} <= anotados
    assert all(Path(c).is_relative_to(pasta) for c in anotados), anotados

    with structlog.testing.capture_logs() as de_novo:
        assert loader.todo_perfil_no_formato_da_aba_jogar(pasta) == []
    assert _anotados(de_novo) == set()
