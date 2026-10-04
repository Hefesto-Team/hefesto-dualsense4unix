#!/usr/bin/env python3
"""O-APLICAR-SOLUCOES-COM-JOGO-ABERTO-DIZ-O-QUE-FEZ-01 (03/10/2026).

Com um jogo aberto, o «Aplicar soluções nos lançadores» aplica o que não exige
fechar a Steam (os outros lançadores) e diz isso em uma linha, com a Steam para
quando o jogo fechar. Não é falha: antes, o clique caía inteiro como «gesto
falhou» e ela não sabia se os outros tinham recebido.
"""
from __future__ import annotations

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.app.actions import daemon_actions as _daemon
from hefesto_dualsense4unix.integrations import cura_por_estrada as cpe
from hefesto_dualsense4unix.integrations import steam_launch_options as slo
from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

GESTO = "aplicar-aos-jogos"


def _ctx() -> Contexto:
    return Contexto(state={"active_profile": "regua"}, mesa=[], conectados=[], estados={})


@pytest.fixture(autouse=True)
def _limpo():
    a09._ARMADO.clear()
    a09._PAINEL[0] = None
    yield
    a09._ARMADO.clear()
    a09._PAINEL[0] = None


def _dubles(monkeypatch: pytest.MonkeyPatch, janela: str, escritos: tuple[str, ...]):
    visto = {"estradas": 0, "steam_aplicou": 0}

    def _estradas(*_a, **_k):
        visto["estradas"] += 1
        return escritos

    def _aplicar():
        visto["steam_aplicou"] += 1
        return {"applied": 1, "skipped": 0, "errors": 0}

    monkeypatch.setattr(cpe, "curar_todas_as_estradas", _estradas)
    monkeypatch.setattr(slo, "apply_wrapper_to_all_games", _aplicar, raising=False)
    monkeypatch.setattr(slo, "with_steam_closed",
                        lambda acao: (janela, acao() if janela == "ok" else None))
    return visto


def _dois_cliques():
    a09.aplicar_aos_jogos(_ctx(), {"gesto": GESTO, "texto": "x"}, None)
    return a09.aplicar_aos_jogos(_ctx(), {"gesto": GESTO, "texto": a09.CONFIRMA}, None)


def test_com_jogo_aberto_o_gesto_nao_cai_e_diz_o_que_aplicou(
        monkeypatch: pytest.MonkeyPatch) -> None:
    visto = _dubles(monkeypatch, "jogo_aberto", ("heroic", "lutris"))

    fora = _dois_cliques()

    assert visto == {"estradas": 1, "steam_aplicou": 0}
    assert fora["mesa"][a09.REGISTRO] == (
        "O ambiente do Hefesto está em: Heroic, Lutris. "
        "A Steam fica para quando o jogo fechar.")
    assert "blocos" in fora


def test_com_jogo_aberto_e_nenhum_outro_lancador_ainda_diz_a_verdade(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _dubles(monkeypatch, "jogo_aberto", ())

    frase = _dois_cliques()["mesa"][a09.REGISTRO]

    assert frase == ("Nenhum outro lançador recebeu o ambiente do Hefesto agora. "
                     "A Steam fica para quando o jogo fechar.")


def test_o_recibo_nao_e_a_frase_de_falha() -> None:
    falha = _daemon.format_steam_janela_recusa("jogo_aberto")
    assert falha is not None
    assert a09.STEAM_FICA_PARA_DEPOIS not in falha
    assert "Nada foi mudado" not in a09.STEAM_FICA_PARA_DEPOIS


def test_a_steam_que_nao_fechou_segue_recusando(monkeypatch: pytest.MonkeyPatch) -> None:
    """Só o jogo aberto virou recibo: as outras recusas da Steam seguem levantando."""
    _dubles(monkeypatch, "nao_fechou", ("heroic",))
    with pytest.raises(RuntimeError) as erro:
        _dois_cliques()
    assert str(erro.value) == _daemon.format_steam_janela_recusa("nao_fechou")


def test_com_a_steam_livre_nada_muda_o_resultado_sai_pelo_diario(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    visto = _dubles(monkeypatch, "ok", ("heroic",))

    fora = _dois_cliques()

    assert visto == {"estradas": 1, "steam_aplicou": 1}
    assert set(fora) == {"blocos"}
    assert a09.STEAM_FICA_PARA_DEPOIS not in capsys.readouterr().err
