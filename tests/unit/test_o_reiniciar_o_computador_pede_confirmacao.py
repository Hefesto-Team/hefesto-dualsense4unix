"""O «Reiniciar o computador» do fim da fila só abre a pergunta; o «Reiniciar» da pergunta reinicia.

O-REINICIAR-O-COMPUTADOR-PEDE-CONFIRMACAO-E-DIZ-O-QUE-REINICIA-01 (20/11/2026). O lar é
``tmp_path`` com ``XDG_*`` desviados; o andamento é um fim que trocou o kernel, e o
``subprocess.run`` é um dublê que conta cada comando: nenhum ``systemctl`` chega à máquina.

AS MORDIDAS (feitas na sprint, com a cura devolvida e o md5 conferido): o primeiro gesto chamando
``systemctl reboot`` reprova o caso do primeiro clique; o «Reiniciar» sem conferir a pergunta
reprova o caso da pergunta aberta; a pergunta conferida só pela vista, sem reler a fila, reprova o
caso da pergunta armada.
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import atualizador as at
from hefesto_dualsense4unix.app.actions import daemon_actions as da
from hefesto_dualsense4unix.interface import atualizacoes as tela
from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import atualizacoes as gestos

ABRE = "atualizacoes-reiniciar-o-computador"
AGORA_NAO = "atualizacoes-nao-reiniciar"
REINICIA = "atualizacoes-confirmar-o-reinicio"


@pytest.fixture(autouse=True)
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    casa = tmp_path / "casa"
    for var, sub in (("XDG_CONFIG_HOME", ".config"), ("XDG_STATE_HOME", ".local/state"),
                     ("XDG_CACHE_HOME", ".cache"), ("XDG_DATA_HOME", ".local/share"),
                     ("XDG_RUNTIME_DIR", "run")):
        (casa / sub).mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(var, str(casa / sub))
    monkeypatch.setenv("HOME", str(casa))
    monkeypatch.setattr(gestos, "TELA", {"vista": "", "perguntou": False, "escondida": 0.0,
                                         "lido_em": 0.0, "enviado": "", "aba": "",
                                         "vez": 0, "calculado": None,
                                         "calculando": False})
    return casa


@pytest.fixture
def comandos(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Cada ``systemctl`` pedido, com o prazo conferido; os outros comandos respondem vazio."""
    pedidos: list[list[str]] = []

    def rodar(argv: list[str], **k: Any) -> Any:
        if argv[:1] == ["systemctl"]:
            assert k.get("timeout") == da.PRAZO_DE_DESLIGAR_A_MAQUINA_S
            pedidos.append(list(argv))
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(subprocess, "run", rodar)
    return pedidos


def _fim(**mais: Any) -> None:
    andamento = {"inicio": 123.0, "fase": at.FIM, "fim_em": time.time(),
                 "pecas": [{"id": "kernel", "nome": "Kernel", "de": "7.2.15", "para": "7.2.18",
                            "selo": at.PRONTA, "etapas": {}, "pct": 100}],
                 "total": {"feitas": 1, "de": 1, "pct": 100, "falhas": 0},
                 "reinicio": {"etapas": {}, "pct": 0, "selo": "pronta"}, **mais}
    at._gravar_json(at._estado() / at.ARQUIVO_DO_ANDAMENTO, andamento)


def _gesto(nome: str) -> Any:
    return pacotes.GESTOS[("*", nome)](pacotes.Contexto(state={}), {}, None)


def _a_pergunta_aberta(corpo: str) -> bool:
    return tela.PERGUNTA_DO_REINICIO in corpo and f'data-gesto="{REINICIA}"' in corpo


def test_o_primeiro_clique_so_abre_a_pergunta(comandos: list[list[str]]) -> None:
    """D-2011-O-REINICIAR-O-COMPUTADOR-PEDE-CONFIRMACAO: o primeiro clique só pergunta."""
    _fim()
    corpo = gestos.conteudo(None)
    assert f'data-gesto="{ABRE}"' in corpo and ">Reiniciar o computador</button>" in corpo
    assert "Reiniciar agora" not in corpo and not _a_pergunta_aberta(corpo)
    _gesto(ABRE)
    assert comandos == []
    corpo = gestos.conteudo(None)
    assert _a_pergunta_aberta(corpo)
    assert "Reiniciar o computador agora?" in corpo and "O que estiver aberto fecha." in corpo
    assert f'<button class="btn empurra" data-gesto="{AGORA_NAO}">Agora não</button>' in corpo
    assert f'<button class="btn borda-vermelha" data-gesto="{REINICIA}">Reiniciar</button>' \
        in corpo


def test_agora_nao_volta_a_caixa_como_estava(comandos: list[list[str]]) -> None:
    _fim()
    antes = gestos.conteudo(None)
    _gesto(ABRE)
    assert _a_pergunta_aberta(gestos.conteudo(None))
    _gesto(AGORA_NAO)
    assert comandos == []
    assert gestos.conteudo(None) == antes


def test_so_o_reiniciar_da_pergunta_aberta_reinicia(comandos: list[list[str]]) -> None:
    _fim()
    with pytest.raises(ValueError):
        _gesto(REINICIA)
    assert comandos == []
    _gesto(ABRE)
    gestos.conteudo(None)
    _gesto(REINICIA)
    assert comandos == [["systemctl", "reboot"]]
    with pytest.raises(ValueError):
        _gesto(REINICIA)
    assert len(comandos) == 1


def test_a_pergunta_nunca_fica_armada(comandos: list[list[str]]) -> None:
    """A pergunta fecha com a caixa, com o fim que deixa de pedir o reinício e com a fila nova."""
    _fim()
    _gesto(ABRE)
    _gesto("atualizacoes-fechar")
    assert gestos.conteudo(None) == ""
    with pytest.raises(ValueError):
        _gesto(REINICIA)

    _fim(fase=at.PARADO)
    gestos.TELA["escondida"] = 0.0
    _gesto(ABRE)
    assert not _a_pergunta_aberta(gestos.conteudo(None))
    with pytest.raises(ValueError):
        _gesto(REINICIA)

    _fim()
    _gesto(ABRE)
    assert _a_pergunta_aberta(gestos.conteudo(None))
    _gesto("atualizacoes-registro")
    assert not _a_pergunta_aberta(gestos.conteudo(None))
    with pytest.raises(ValueError):
        _gesto(REINICIA)

    _gesto("atualizacoes-registro-voltar")
    _gesto(ABRE)
    assert _a_pergunta_aberta(gestos.conteudo(None))
    trava = at._a_trava()
    assert trava is not None
    try:
        with pytest.raises(ValueError):
            _gesto(REINICIA)
        assert not _a_pergunta_aberta(gestos.conteudo(None))
    finally:
        os.close(trava)
    assert not _a_pergunta_aberta(gestos.conteudo(None))
    with pytest.raises(ValueError):
        _gesto(REINICIA)
    assert comandos == []


def test_o_reinicio_recusado_pelo_sistema_diz_o_erro_e_desarma(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _fim()
    rodados: list[list[str]] = []

    def recusar(argv: list[str], **_k: Any) -> Any:
        rodados.append(list(argv))
        return type("R", (), {"returncode": 1, "stdout": "", "stderr": "negado pelo polkit"})()

    monkeypatch.setattr(subprocess, "run", recusar)
    _gesto(ABRE)
    with pytest.raises(RuntimeError, match="negado pelo polkit"):
        _gesto(REINICIA)
    assert [a for a in rodados if a[:1] == ["systemctl"]] == [["systemctl", "reboot"]]
    assert not _a_pergunta_aberta(gestos.conteudo(None))
