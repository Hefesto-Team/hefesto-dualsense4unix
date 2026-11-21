"""O-REINICIAR-ESPERA-O-SERVICO-E-DIZ-O-QUE-FEZ-01 — o prazo cobre a parada e o recibo chega.

O `restart` soma a parada da unit à partida; o prazo estourado é dito como reinício em curso e a
reposição do lançador roda quando o serviço volta; o recibo da reposição vai ao painel da aba e à
notificação do desktop quando algum lançador não fechou ou não reabriu. O `systemctl`, os
lançadores e o desktop são de mentira.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import daemon_actions as da
from hefesto_dualsense4unix.integrations.reposicao_dos_lancadores import Recibo
from hefesto_dualsense4unix.utils import sd_notify, single_instance

RAIZ = Path(__file__).resolve().parents[2]
UNIT = "hefesto-dualsense4unix.service"
DICA_NOVA = "Para e liga de novo; a Steam e os outros lançadores abertos fecham e reabrem"


def test_o_restart_espera_a_parada_da_unit_mais_a_partida() -> None:
    """D-2011-O-REINICIAR-ESPERA-O-SERVICO-E-DIZ-O-QUE-FEZ: o prazo do restart cobre os dois tempos.

    MORDIDA: devolva ao ``restart`` o prazo do ``start``.
    """
    parada_e_partida = single_instance.PRAZO_DO_DESLIGAMENTO_S + sd_notify.PRAZO_DA_PARTIDA_S
    assert da.prazo_do_systemctl(["restart", UNIT]) > parada_e_partida
    assert da.prazo_do_systemctl(["start", UNIT]) == (
        sd_notify.PRAZO_DA_PARTIDA_S + da.FOLGA_DO_START_S)
    assert da.prazo_do_systemctl(["is-active", UNIT]) == da.PRAZO_DA_CONSULTA_S


def test_o_prazo_estourado_nao_se_confunde_com_o_comando_ausente(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2011-O-REINICIAR-ESPERA-O-SERVICO-E-DIZ-O-QUE-FEZ: o estouro tem código, a falta é None.

    MORDIDA: junte ``TimeoutExpired`` ao ``except`` da falta do comando.
    """
    def estoura(argv: list[str], **_: Any) -> Any:
        raise subprocess.TimeoutExpired(argv, 1.0)

    def falta(argv: list[str], **_: Any) -> Any:
        raise FileNotFoundError(argv[0])

    janela = da.DaemonActionsMixin()
    monkeypatch.setattr(subprocess, "run", estoura)
    resultado = janela._invoke_systemctl(["restart", UNIT], capture=True)
    assert resultado is not None and resultado.returncode == da.PRAZO_ESTOURADO_RC
    monkeypatch.setattr(subprocess, "run", falta)
    assert janela._invoke_systemctl(["restart", UNIT], capture=True) is None


@pytest.fixture
def a09(monkeypatch: pytest.MonkeyPatch) -> Any:
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes.a09_sistema`, que carrega o GTK")
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema

    a09_sistema._PAINEL[0] = None
    a09_sistema._PERGUNTA.clear()
    monkeypatch.setattr(a09_sistema, "_trava", lambda *_a, **_k: None)
    yield a09_sistema
    a09_sistema._PAINEL[0] = None
    a09_sistema._PERGUNTA.clear()


class _Janela:
    def __init__(self, rc_do_restart: int, rc_do_start: int = 0) -> None:
        self.rcs = {"restart": rc_do_restart, "start": rc_do_start}
        self.comandos: list[list[str]] = []

    def _invoke_systemctl(self, args: list[str], **_: Any) -> Any:
        self.comandos.append(list(args))
        return SimpleNamespace(returncode=self.rcs.get(args[0], 0), stderr="", stdout="")


def _montar(a09: Any, monkeypatch: pytest.MonkeyPatch, janela: _Janela) -> list[str]:
    reposicoes: list[str] = []
    monkeypatch.setattr(a09, "_matriz", lambda: janela)
    monkeypatch.setattr(a09, "_repor_o_lancador", lambda: reposicoes.append("repos"))
    monkeypatch.setattr(a09, "na_fila", lambda _filas, trabalho, nome="": trabalho())
    return reposicoes


def test_o_reinicio_que_estoura_o_prazo_diz_que_segue_em_curso_e_repoe_quando_volta(
        a09: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2011-O-REINICIAR-ESPERA-O-SERVICO-E-DIZ-O-QUE-FEZ: prazo estourado não é falha.

    O painel diz que o reinício segue em curso, nunca a frase genérica do sistema; a reposição do
    lançador roda depois que o ``start`` volta bem, e não roda se ele não voltar.

    MORDIDA: tire de ``_systemctl`` o ramo do prazo estourado do ``restart``.
    """
    janela = _Janela(da.PRAZO_ESTOURADO_RC)
    reposicoes = _montar(a09, monkeypatch, janela)
    a09.reiniciar(SimpleNamespace(state={}), {}, None)
    assert a09._PAINEL[0] == a09.REINICIO_EM_CURSO
    assert "Não consegui falar com o sistema" not in a09._PAINEL[0]
    assert [c[0] for c in janela.comandos if c[0] != "reset-failed"] == ["restart", "start"]
    assert reposicoes == ["repos"]

    a09._PAINEL[0] = None
    sem_volta = _Janela(da.PRAZO_ESTOURADO_RC, rc_do_start=1)
    reposicoes = _montar(a09, monkeypatch, sem_volta)
    a09.reiniciar(SimpleNamespace(state={}), {}, None)
    assert reposicoes == []


def test_o_restart_que_falha_de_verdade_continua_falhando(
        a09: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2011-O-REINICIAR-ESPERA-O-SERVICO-E-DIZ-O-QUE-FEZ: outro rc segue recusando."""
    janela = _Janela(1)
    reposicoes = _montar(a09, monkeypatch, janela)
    with pytest.raises(RuntimeError):
        a09.reiniciar(SimpleNamespace(state={}), {}, None)
    assert reposicoes == [] and a09._PAINEL[0] is None


@pytest.mark.parametrize("recibo,na_tela", [
    (Recibo(estavam_abertos=("Steam",), nao_reabriram=("Steam",)), True),
    (Recibo(estavam_abertos=("Steam",), nao_fecharam=("Steam",)), True),
    (Recibo(estavam_abertos=("Steam",), repostos=("Steam",)), False),
    (Recibo(), False),
    (Recibo(barrado_por_jogo=True), False),
])
def test_o_recibo_da_reposicao_so_vai_a_tela_quando_algum_lancador_falhou(
        a09: Any, monkeypatch: pytest.MonkeyPatch, recibo: Recibo, na_tela: bool) -> None:
    """D-2011-O-REINICIAR-ESPERA-O-SERVICO-E-DIZ-O-QUE-FEZ: a falha da reposição chega ao painel.

    O recibo que deu certo fica no diário, como antes; o que falhou vai ao painel.

    MORDIDA: tire ``na_tela=recibo.falhou`` da chamada em ``_repor_o_lancador``.
    """
    from hefesto_dualsense4unix.integrations import reposicao_dos_lancadores as rl

    monkeypatch.setattr(rl, "repor", lambda: recibo)
    a09._repor_o_lancador()
    if na_tela:
        assert a09._PAINEL[0] == rl.frase_do_recibo(recibo)
    else:
        assert a09._PAINEL[0] is None


def test_a_reposicao_que_levanta_chega_ao_painel(
        a09: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2011-O-REINICIAR-ESPERA-O-SERVICO-E-DIZ-O-QUE-FEZ: o erro da reposição também aparece."""
    from hefesto_dualsense4unix.integrations import reposicao_dos_lancadores as rl

    def quebra() -> Recibo:
        raise OSError("sem permissão")

    monkeypatch.setattr(rl, "repor", quebra)
    a09._repor_o_lancador()
    assert "não consegui repor o lançador" in str(a09._PAINEL[0])


@pytest.mark.parametrize("recibo,avisa", [
    (Recibo(estavam_abertos=("Steam",), nao_reabriram=("Steam",)), True),
    (Recibo(estavam_abertos=("Steam",), repostos=("Steam",)), False),
])
def test_o_recibo_da_bandeja_vai_a_notificacao_do_desktop_so_quando_falhou(
        monkeypatch: pytest.MonkeyPatch, recibo: Recibo, avisa: bool) -> None:
    """D-2011-O-REINICIAR-ESPERA-O-SERVICO-E-DIZ-O-QUE-FEZ: a bandeja avisa pelo desktop.

    MORDIDA: tire de ``repor_o_lancador`` a chamada de ``_avisar_no_desktop``.
    """
    from hefesto_dualsense4unix.app.actions import atos_da_bandeja as ab
    from hefesto_dualsense4unix.integrations import desktop_notifications as dn
    from hefesto_dualsense4unix.integrations import reposicao_dos_lancadores as rl

    avisos: list[tuple[str, str]] = []
    monkeypatch.setattr(rl, "repor", lambda: recibo)
    monkeypatch.setattr(dn, "notify", lambda resumo, corpo="", **_: avisos.append((resumo, corpo)))
    ab.repor_o_lancador()
    assert avisos == ([("Reiniciar o serviço", rl.frase_do_recibo(recibo))] if avisa else [])


def test_a_dica_do_reiniciar_avisa_que_o_lancador_fecha_e_reabre() -> None:
    """D-2011-O-REINICIAR-ESPERA-O-SERVICO-E-DIZ-O-QUE-FEZ: a dica do desenho diz o que o botão faz.

    MORDIDA: devolva a dica antiga ao gerador (``aba09.py``) e regenere o mockup.
    """
    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/aba09.py").read_text(encoding="utf-8")
    mockup = (RAIZ / "mockup/09-sistema.html").read_text(encoding="utf-8")
    assert DICA_NOVA in fonte and DICA_NOVA in mockup
    assert "nenhum ajuste se perde" not in fonte + mockup
