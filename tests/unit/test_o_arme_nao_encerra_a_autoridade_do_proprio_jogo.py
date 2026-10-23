"""O-ARME-NAO-ENCERRA-A-AUTORIDADE-DO-PROPRIO-JOGO-01 — o arme não encerra o próprio jogo.

O que se mediu em 23/10 (a rodada C3 da bancada, a Steam recém-aberta): o tique do sinal
viu o próprio Mullet MadJack 43 ms antes do ping do wrapper e a autoridade foi a `game`;
o arme (`launch_env._encerrar_a_autoridade_do_jogo_que_acabou`) achou `game`, nenhum
OUTRO jogo vivo e a encerrou como se fosse o resíduo de um jogo que acabou. O jogo
voltou a `game` 2 s depois, e nesses 2 s o Hefesto recusou a saída dele e defendeu a
tela. A cura: a casca do sinal guarda o appid da evidência (`GameSignal.appid`), o arme
do mesmo appid mantém a autoridade, e a recriação que ele pede passa pelo
`_recriacao_bloqueada_por_jogo` com a autoridade DELE (`game_signal.o_arme_do_proprio_jogo`).

O `Daemon` é o de verdade, com o `GameSignal` de verdade (o mesmo da régua da
O-JOGO-SEGUINTE); só a borda do aparelho é dublada e a varredura entra pelas leituras.
Os endereços são da faixa forjada da casa. A mordida de cada teste está no docstring.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
import structlog.testing

from hefesto_dualsense4unix.daemon import lifecycle as lc
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.game_signal import (
    DECISAO_ARME_DO_PROPRIO_JOGO,
    GameSignal,
    appid_da_autoridade,
    classify,
    o_arme_do_proprio_jogo,
)
from tests.unit.test_o_jogo_seguinte_veste_a_propria_roupa import (  # noqa: F401
    COMUM,
    EDGE,
    EPOCH_A,
    EPOCH_B,
    JOGO_A,
    JOGO_B,
    _arme,
    _hermetico,
    _linhas,
    _Mesa,
    _processo,
    _Relogio,
    _roupa_do_jogo_novo,
)

DECISAO = "D-2310-O-ARME-NAO-ENCERRA-A-AUTORIDADE-DO-PROPRIO-JOGO"
assert DECISAO == DECISAO_ARME_DO_PROPRIO_JOGO


def _o_tique_ve_o_jogo(mesa: _Mesa, tmp_path: Path, appid: int, *, por: str) -> None:
    """O tique do sinal vê o jogo ANTES do ping do wrapper (a corrida da C3)."""
    if por == "o_processo":
        _processo(tmp_path, 5151, appid)
        mesa.varredura = {"appid_de_jogo_vivo": appid}
    else:
        mesa.varredura = {
            "marker": (appid, EPOCH_B), "marker_pid": 4242, "marker_pid_alive": True,
            "now": float(EPOCH_B) + 1,
        }
    assert mesa.tique() == "game", "premissa: o tique pôs o jogo na autoridade"


@pytest.mark.parametrize("por", ["o_processo", "o_marcador"])
def test_o_arme_do_jogo_que_o_tique_ja_viu_mantem_a_autoridade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, por: str,
) -> None:
    """A C3: o tique viu o jogo A, o arme de A chega, e a autoridade fica `game` sem transição.

    MORDIDA: tire a comparação do appid da autoridade em
    `_encerrar_a_autoridade_do_jogo_que_acabou` e o arme encerra (`daemon_outro_lancamento`).
    """
    _roupa_do_jogo_novo(monkeypatch, EDGE)
    mesa = _Mesa(monkeypatch, "bt", 0)
    _o_tique_ve_o_jogo(mesa, tmp_path, JOGO_A, por=por)
    mesa.lancar(tmp_path, JOGO_A, EPOCH_B)

    with structlog.testing.capture_logs() as diario:
        resultado = _arme(mesa, tmp_path)

    assert resultado is not None and resultado["appid"] == JOGO_A
    assert _linhas(diario, "game_signal_transition") == []
    assert _linhas(diario, "launch_arm_autoridade_mantida_mesmo_jogo") != []
    assert mesa.d.display_authority == "game"


@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_o_arme_do_proprio_jogo_veste_a_roupa_com_a_autoridade_dele(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, transporte: str,
) -> None:
    """D-2310-O-ARME-NAO-ENCERRA-A-AUTORIDADE-DO-PROPRIO-JOGO: o pad de `0df2` veste `0ce6`.

    A roupa do jogo A é a `0ce6`; o tique já o pôs em `game`. O arme veste a roupa sem
    encerrar a autoridade: a recriação não é recusada e a saída do jogo segue valendo.

    MORDIDA: tire a passagem do arme (`game_signal.o_arme_do_proprio_jogo` em
    `launch_env.arm_launch_profile`) e o pad fica `0df2`, com
    `vpad_recriacao_bloqueada_por_jogo` no diário.
    """
    _roupa_do_jogo_novo(monkeypatch, COMUM)
    mesa = _Mesa(monkeypatch, transporte, 0)
    assert mesa.roupas() == {"p1": EDGE}, "premissa: o pad de antes é o Edge"
    _o_tique_ve_o_jogo(mesa, tmp_path, JOGO_A, por="o_marcador")
    mesa.lancar(tmp_path, JOGO_A, EPOCH_B)

    with structlog.testing.capture_logs() as diario:
        _arme(mesa, tmp_path)

    assert mesa.roupas() == {"p1": COMUM}, mesa.roupas()
    assert mesa.d.roupa_do_pad == COMUM
    assert _linhas(diario, "vpad_recriacao_bloqueada_por_jogo") == []
    passagem = _linhas(diario, "pad_recriado_com_o_jogo_aberto")
    assert passagem and passagem[0]["decisao"] == DECISAO, passagem  # noqa-acento: chave do diário
    assert _linhas(diario, "game_signal_transition") == []
    assert mesa.d.display_authority == "game"
    assert mesa.d._pad_travado_pelo_lancamento == (JOGO_A, EPOCH_B), "a trava nasce depois"


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("secundarios", [1, 2, 3], ids=["2j", "3j", "4j"])
def test_o_arme_do_proprio_jogo_veste_a_roupa_nos_quatro_controles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, transporte: str, secundarios: int,
) -> None:
    """O arme de A com P1 a P4 de pé: os quatro vestem a roupa de A, no cabo e no rádio.

    MORDIDA: tire a passagem do arme e o P1 fica no Edge (a recusa do P1 vem do
    juiz da recriação).
    """
    _roupa_do_jogo_novo(monkeypatch, COMUM)
    mesa = _Mesa(monkeypatch, transporte, secundarios)
    _o_tique_ve_o_jogo(mesa, tmp_path, JOGO_A, por="o_marcador")
    mesa.lancar(tmp_path, JOGO_A, EPOCH_B)

    _arme(mesa, tmp_path)

    assert len(mesa.roupas()) == 1 + secundarios
    assert set(mesa.roupas().values()) == {COMUM}, mesa.roupas()


def test_o_arme_de_outro_jogo_segue_encerrando(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A autoridade é do A, o A morreu e o arme é do B: encerra, como na régua da O-JOGO-SEGUINTE.

    MORDIDA: nunca encerrar (`return False` no começo da função) e a transição some, com
    o pad ainda `0ce6`.
    """
    _roupa_do_jogo_novo(monkeypatch, EDGE)
    mesa = _Mesa(monkeypatch, "usb", 0)
    mesa.abrir_o_jogo(JOGO_A, EPOCH_A, COMUM)
    assert appid_da_autoridade(mesa.d) == JOGO_A, "premissa: a autoridade sabe de quem é"
    mesa.fechar_o_jogo(10.0)
    mesa.lancar(tmp_path, JOGO_B, EPOCH_B)

    with structlog.testing.capture_logs() as diario:
        _arme(mesa, tmp_path)

    assert [
        (x["de"], x["para"], x["evidencia"]) for x in _linhas(diario, "game_signal_transition")
    ] == [("game", "daemon", "daemon_outro_lancamento")]
    assert mesa.roupas() == {"p1": EDGE}


@pytest.mark.parametrize("a_autoridade_e_do", ["jogo_a", "jogo_b"])
def test_a_autoridade_de_outro_jogo_vivo_segue_recusando_a_roupa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, a_autoridade_e_do: str,
) -> None:
    """O jogo A está vivo e o arme é do B: a roupa de B fica pendente, de quem for a autoridade.

    No caso `jogo_a` a autoridade é do A e o juiz da recriação recusa pela comparação do
    appid; no `jogo_b` o tique já viu o B, mas o A segue vivo no `/proc` e o arme não abre
    a passagem.

    MORDIDA: abra a passagem sempre (`launch_env`: ``o_arme_do_proprio_jogo(appid)``) e
    tire a comparação do appid do juiz (`game_signal.decisao_do_arme`): o pad é recriado
    `0df2` por cima do jogo A, nos dois casos.
    """
    _roupa_do_jogo_novo(monkeypatch, EDGE)
    mesa = _Mesa(monkeypatch, "usb", 0)
    mesa.abrir_o_jogo(JOGO_A, EPOCH_A, COMUM)
    _processo(tmp_path, 3131, JOGO_A)
    mesa.varredura = {"appid_de_jogo_vivo": JOGO_A if a_autoridade_e_do == "jogo_a" else JOGO_B}
    assert mesa.tique() == "game"
    mesa.lancar(tmp_path, JOGO_B, EPOCH_B)

    with structlog.testing.capture_logs() as diario:
        _arme(mesa, tmp_path)

    assert mesa.d.display_authority == "game"
    assert _linhas(diario, "game_signal_transition") == []
    assert _linhas(diario, "pad_recriado_com_o_jogo_aberto") == []
    assert mesa.d.roupa_do_pad == EDGE, "o pedido fica pendente"
    assert mesa.roupas() == {"p1": COMUM}, "o pad do jogo vivo não é recriado"


def test_a_passagem_vale_so_para_o_appid_da_autoridade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O juiz da recriação: a passagem do arme de B não vale com a autoridade do A.

    MORDIDA: tire a comparação com `appid_da_autoridade` do juiz e o arme de B passa.
    """
    mesa = _Mesa(monkeypatch, "usb", 0)
    mesa.abrir_o_jogo(JOGO_A, EPOCH_A, COMUM)
    mesa.d._pad_travado_pelo_lancamento = None

    def juiz() -> bool:
        return bool(
            gp._recriacao_bloqueada_por_jogo(mesa.d, origin="profile", motivo="regua")
        )

    assert juiz() is True, "premissa: sem o arme, a autoridade de A recusa"
    with o_arme_do_proprio_jogo(JOGO_B):
        assert juiz() is True
    with o_arme_do_proprio_jogo(JOGO_A):
        assert juiz() is False
    assert juiz() is True, "a passagem acaba com o arme"
    with o_arme_do_proprio_jogo(None):
        assert juiz() is True


def test_a_soltura_do_pad_nao_ganha_a_passagem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A volta ao Edge (`_soltar_o_pad_do_lancamento`) segue recusada com o jogo na autoridade.

    MORDIDA: deixe a passagem armada depois do arme (sem o `finally` do gerenciador) e
    a soltura recria o pad.
    """
    _roupa_do_jogo_novo(monkeypatch, COMUM)
    mesa = _Mesa(monkeypatch, "usb", 0)
    _o_tique_ve_o_jogo(mesa, tmp_path, JOGO_A, por="o_marcador")
    mesa.lancar(tmp_path, JOGO_A, EPOCH_B)
    _arme(mesa, tmp_path)
    assert mesa.roupas() == {"p1": COMUM}

    lc._soltar_o_pad_do_lancamento(mesa.d, "regua")

    assert mesa.roupas() == {"p1": COMUM}, "o Edge só volta quando a autoridade sai de game"


def test_a_casca_guarda_o_appid_da_evidencia() -> None:
    """`GameSignal.appid` é o da evidência que pôs (ou mantém) `game`, e some com a saída.

    MORDIDA: tire o `self._appid = appid` do `evaluate` e o primeiro assert reprova.
    """
    relogio = _Relogio()
    sinal = GameSignal(time_fn=relogio)
    assert sinal.appid is None
    sinal.evaluate("game", session_open=True, appid=JOGO_A)
    assert sinal.appid == JOGO_A
    sinal.evaluate("game", session_open=True, appid=None)
    assert sinal.appid == JOGO_A, "a evidência só de janela não apaga o appid"
    sinal.evaluate("game", session_open=True, appid=JOGO_B)
    assert sinal.appid == JOGO_B, "outro appid com a autoridade em game atualiza"
    sinal.evaluate("daemon", session_open=True)
    assert sinal.authority == "game" and sinal.appid == JOGO_B, "a histerese segura o jogo"
    assert sinal.encerrar("regua") is True
    assert sinal.appid is None
    sinal.evaluate("game", session_open=True, appid=JOGO_A)
    sinal.mark_degraded("regua")
    assert sinal.appid is None


def test_o_tique_do_daemon_passa_o_appid_da_evidencia_a_casca(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O `_sync_game_signal` leva o appid de `_o_appid_da_evidencia` à casca: um dono só.

    MORDIDA: chame `signal.evaluate` sem o `appid` no tique e `appid_da_autoridade` fica
    `None` com o jogo na autoridade.
    """
    mesa = _Mesa(monkeypatch, "usb", 0)
    mesa.varredura = {"appid_de_jogo_vivo": JOGO_A}
    leitura = mesa._ler()

    async def _varredura(_funcao: Any) -> dict[str, Any]:
        return leitura

    mesa.d._run_blocking = _varredura
    asyncio.run(mesa.d._sync_game_signal())

    assert mesa.d.display_authority == "game"
    assert appid_da_autoridade(mesa.d) == JOGO_A == lc._o_appid_da_evidencia(leitura)
    assert classify(**leitura) == "game"

    mesa.varredura = {}
    leitura = mesa._ler()
    asyncio.run(mesa.d._sync_game_signal())
    assert appid_da_autoridade(mesa.d) == JOGO_A, "a histerese segura o jogo e o appid"


def test_o_daemon_sem_o_sinal_nao_tem_autoridade_de_ninguem() -> None:
    """Sem `GameSignal` não há appid de autoridade: o arme cai no caminho de antes."""
    from types import SimpleNamespace

    assert appid_da_autoridade(SimpleNamespace(_game_signal=None)) is None
    assert appid_da_autoridade(SimpleNamespace()) is None


def test_a_tarefa_nascida_no_arme_nao_herda_a_passagem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tarefa criada durante o arme copia o contexto dele, mas a passagem acaba com o arme.

    O `asyncio.create_task` copia o contexto da hora em que nasce (`copy_context`): uma
    tarefa que o arme agenda roda depois dele, com o jogo já aberto no pad e a trava de pé.

    MORDIDA: tire a conferência do arme em curso de `game_signal.decisao_do_arme` e a
    recriação pedida pela tarefa passa por cima do jogo.
    """
    import contextvars

    _roupa_do_jogo_novo(monkeypatch, COMUM)
    mesa = _Mesa(monkeypatch, "usb", 0)
    _o_tique_ve_o_jogo(mesa, tmp_path, JOGO_A, por="o_marcador")
    mesa.lancar(tmp_path, JOGO_A, EPOCH_B)
    contextos: list[contextvars.Context] = []
    original = gp.vestir_a_roupa

    def _vestir(daemon: Any, roupa: object) -> list[str]:
        contextos.append(contextvars.copy_context())
        return original(daemon, roupa)

    monkeypatch.setattr(gp, "vestir_a_roupa", _vestir)
    _arme(mesa, tmp_path)
    assert contextos and mesa.roupas() == {"p1": COMUM}, "premissa: o arme vestiu a roupa"

    bloqueada = contextos[0].run(
        gp._recriacao_bloqueada_por_jogo, mesa.d, origin="profile", motivo="regua"
    )

    assert bloqueada is True
