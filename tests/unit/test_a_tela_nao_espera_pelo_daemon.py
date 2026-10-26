"""O tique da janela NÃO espera pelo daemon — A-TELA-QUE-TRAVA-01."""
from __future__ import annotations

import inspect
import pathlib
import sys
import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.hefesto_vivo`, que carrega o GTK")

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.interface import hefesto_vivo as hv

PIOR_MEDIDO_S = 0.30


def test_a_primeira_leitura_sai_do_fio_de_quem_chama() -> None:
    """`comecar()` não lê no fio de quem chama, e o fio avisa quando a primeira chega.

    O contrato mudou em 21/10/2026 (O-FIO-DA-JANELA-NUNCA-ESPERA-01): a semeadura
    síncrona era um IPC no fio do GTK, dentro do `_instalado`.
    """
    quem_leu: list[int] = []
    chegou = threading.Event()

    def ler() -> dict[str, Any]:
        quem_leu.append(threading.get_ident())
        return {"controllers": [{"uniq": "aa"}]}

    leitor = hv.LeitorDoEstado(ler, intervalo=10.0, avisar=chegou.set)
    assert leitor.ultimo() == (None, None, 0), (
        "o leitor já tinha resposta antes de `comecar()` — então ele leu no "
        "`__init__`, e um Piloto construído por uma régua abriria socket")
    try:
        leitor.comecar()
        assert chegou.wait(5.0), "a primeira leitura não avisou a janela"
        st, erro, geracao = leitor.ultimo()
    finally:
        leitor.parar()
    assert threading.get_ident() not in quem_leu, (
        "`comecar()` leu no fio de quem chama — na janela, é o fio do GTK esperando o IPC")
    assert erro is None and st == {"controllers": [{"uniq": "aa"}]} and geracao == 1


def _o_que_o_init_da(campo: str) -> Any:
    """O valor que o `Piloto.__init__` DE VERDADE dá a `campo` (a janela não sobe aqui)."""
    import ast
    import textwrap

    arvore = ast.parse(textwrap.dedent(inspect.getsource(hv.Piloto.__init__)))
    for no in ast.walk(arvore):
        alvo = no.target if isinstance(no, ast.AnnAssign) else (
            no.targets[0] if isinstance(no, ast.Assign) else None)
        if isinstance(alvo, ast.Attribute) and alvo.attr == campo and no.value is not None:
            return ast.literal_eval(no.value)
    raise AssertionError(f"o __init__ não dá mais valor a {campo}")


def test_o_tique_sem_resposta_nao_pinta_a_mesa_vazia(monkeypatch: pytest.MonkeyPatch) -> None:
    """Antes da primeira resposta o tique não pinta — senão `{}` diria que a mesa está vazia."""
    monkeypatch.setattr(hv.pacotes, "bater_os_coracoes", lambda *_a, **_k: None)
    leitor = hv.LeitorDoEstado(lambda: {}, intervalo=10.0)
    contou: list[str] = []
    piloto: Any = SimpleNamespace(
        pronto=True, _estado_vivo=leitor, _escondida=False, _ctx_de_agora=None,
        _geracao_vista=_o_que_o_init_da("_geracao_vista"),
        _geracao_na_volta=_o_que_o_init_da("_geracao_na_volta"),
        _pintura_no_ar=False, _pular=0, args=SimpleNamespace(prova_de_mockup=False))
    piloto._estado_do_tique = lambda: contou.append("pintou") or {}

    def montar(*_a: Any, **_k: Any) -> Any:
        contou.append("montou")
        raise RuntimeError("a régua não monta mesa")

    piloto._contexto = montar
    for metodo in ("_esperando_o_estado_novo", "_o_contexto_anda_escondido"):
        setattr(piloto, metodo, getattr(hv.Piloto, metodo).__get__(piloto))
    assert hv.Piloto._tique(piloto) is True
    assert contou == [], f"o tique trabalhou sem resposta do serviço: {contou}"


def test_quem_pergunta_nao_espera_pela_leitura_lenta() -> None:
    """O teto desta régua é o custo de UM tique, e a leitura demora três."""
    soltar = threading.Event()

    def devagar() -> dict[str, Any]:
        soltar.wait(PIOR_MEDIDO_S)
        return {"controllers": []}

    leitor = hv.LeitorDoEstado(devagar, intervalo=0.0)
    fio = threading.Thread(target=leitor.comecar, daemon=True)
    fio.start()
    try:
        t0 = time.perf_counter()
        for _ in range(10):
            leitor.ultimo()
        custo = (time.perf_counter() - t0) * 1000
    finally:
        soltar.set()
        leitor.parar()
    assert custo < hv.TIQUE_MS, (
        f"dez perguntas ao escaninho custaram {custo:.0f} ms com uma leitura de "
        f"{PIOR_MEDIDO_S * 1000:.0f} ms a caminho — o teto de UM tique é "
        f"{hv.TIQUE_MS} ms. Quem pergunta voltou a esperar pela leitura")


def test_a_geracao_anda_uma_vez_por_resposta() -> None:
    """Boa ou muda, cada resposta sobe a geração UMA vez — nem zero, nem duas."""
    respostas: list[Any] = [{"a": 1}, RuntimeError("caiu"), {"a": 2}]

    def uma() -> dict[str, Any]:
        r = respostas.pop(0)
        if isinstance(r, BaseException):
            raise r
        return r

    leitor = hv.LeitorDoEstado(uma, intervalo=10.0)
    vistas = []
    try:
        for _ in range(3):
            leitor._uma_leitura()
            vistas.append(leitor.ultimo())
    finally:
        leitor.parar()
    assert [g for _, _, g in vistas] == [1, 2, 3]
    assert vistas[0][0] == {"a": 1} and vistas[0][1] is None
    assert vistas[1][0] is None and isinstance(vistas[1][1], RuntimeError), (
        "a leitura muda não guardou o motivo — sem ele a folga não sabe "
        "distinguir DEMORA de serviço fora do ar, e passa a repintar estado "
        "velho sobre um daemon que morreu")
    assert vistas[2][0] == {"a": 2} and vistas[2][1] is None, (
        "a resposta boa não apagou o erro anterior — a tela ficaria muda para "
        "sempre depois do primeiro `timed out`")


def test_o_fio_nao_sobe_duas_vezes() -> None:
    leitor = hv.LeitorDoEstado(lambda: {}, intervalo=10.0)
    try:
        leitor.comecar()
        primeiro = leitor._fio
        leitor.comecar()
        assert leitor._fio is primeiro, (
            "um segundo `comecar()` subiu outro fio — o `_instalado` roda a "
            "cada carga de página, e em dez abas seriam dez fios perguntando "
            "ao daemon dela")
    finally:
        leitor.parar()


def test_o_fio_pede_na_mesma_cadencia_do_tique() -> None:
    """O daemon não recebe uma pergunta a mais por causa desta cura.

    O `intervalo` de fábrica é o próprio `TIQUE_MS`. Um leitor que lesse em
    laço apertado curaria o travamento e cobraria o preço do outro lado —
    dezenas de `state_full` por segundo no daemon do usuário.
    """
    leitor = hv.LeitorDoEstado()
    assert leitor._intervalo == pytest.approx(hv.TIQUE_MS / 1000.0)


def _piloto_de_mentira(leitor: hv.LeitorDoEstado) -> Any:
    """O mínimo do `Piloto` que o caminho da resposta toca."""
    piloto = SimpleNamespace(
        _folga=hv.FolgaDoServicoMudo(),
        _estado_vivo=leitor,
        _geracao_vista=-1,
        _st_de_agora={},
    )
    piloto._da_resposta = hv.Piloto._da_resposta.__get__(piloto)
    piloto._estado_do_tique = hv.Piloto._estado_do_tique.__get__(piloto)
    return piloto


def _um_tique(piloto: Any) -> dict[str, Any]:
    """UM tique, pelo método DO PRODUTO."""
    return piloto._estado_do_tique()


def test_a_folga_nao_queima_em_tiques_sem_resposta_nova() -> None:
    """Dez tiques sobre UMA leitura muda gastam UM mudo da folga, não dez."""
    leitor = hv.LeitorDoEstado(lambda: {}, intervalo=10.0)
    leitor._estado, leitor._erro, leitor._geracao = {"controllers": ["x"]}, None, 1
    piloto = _piloto_de_mentira(leitor)
    assert _um_tique(piloto) == {"controllers": ["x"]}

    leitor._estado, leitor._erro, leitor._geracao = None, TimeoutError("timed out"), 2
    for _ in range(10):
        assert _um_tique(piloto) == {"controllers": ["x"]}, (
            "o tique deixou de repintar o último estado bom dentro da folga")
    assert piloto._folga.seguidos == 1, (
        f"dez tiques sobre UMA leitura muda gastaram "
        f"{piloto._folga.seguidos} mudos da folga. A folga conta RESPOSTAS — "
        f"se ela contar tiques, os três de "
        f"`MUDOS_SEGUIDOS_QUE_VOLTARAM` acabam em "
        f"{hv.MUDOS_SEGUIDOS_QUE_VOLTARAM * hv.TIQUE_MS} ms")


def test_depois_da_folga_a_tela_diz_a_verdade() -> None:
    """O quarto mudo SEGUIDO pinta `{}` — a regra da RECONECTAR-SAMBA-02 fica."""
    leitor = hv.LeitorDoEstado(lambda: {}, intervalo=10.0)
    leitor._estado, leitor._erro, leitor._geracao = {"controllers": ["x"]}, None, 1
    piloto = _piloto_de_mentira(leitor)
    _um_tique(piloto)
    for n in range(hv.MUDOS_SEGUIDOS_QUE_VOLTARAM):
        leitor._erro, leitor._estado = TimeoutError("timed out"), None
        leitor._geracao += 1
        assert _um_tique(piloto) == {"controllers": ["x"]}, (
            f"o mudo nº {n + 1} devia caber na folga de "
            f"{hv.MUDOS_SEGUIDOS_QUE_VOLTARAM}")
    leitor._geracao += 1
    assert _um_tique(piloto) == {}, (
        "passada a folga, a tela tem de parar de afirmar um estado que ela não "
        "tem como confirmar — é a metade construída pela JOGAR-O-QUE-FALTA-01")


def test_o_servico_fora_do_ar_se_pinta_na_hora() -> None:
    """Fora do ar NÃO é demora: `{}` no primeiro, sem folga nenhuma."""
    leitor = hv.LeitorDoEstado(lambda: {}, intervalo=10.0)
    leitor._estado, leitor._erro, leitor._geracao = {"controllers": ["x"]}, None, 1
    piloto = _piloto_de_mentira(leitor)
    _um_tique(piloto)
    leitor._estado, leitor._erro = None, ConnectionRefusedError(111, "recusada")
    leitor._geracao += 1
    assert _um_tique(piloto) == {}, (
        "o serviço que não está lá foi tratado como demora — a tela pintaria "
        "controles de minutos atrás sobre um daemon desligado")


def test_o_tique_nao_chama_o_daemon_de_dentro_do_laco() -> None:
    """`Piloto._tique` não fala com o socket — quem fala é o fio."""
    corpo = inspect.getsource(hv.Piloto._tique)
    linhas = [ln for ln in corpo.splitlines()
              if "estado_do_daemon" in ln and not ln.lstrip().startswith("#")]
    assert not linhas, (
        "o `_tique` voltou a chamar o daemon de dentro do laço do GTK:\n  "
        + "\n  ".join(ln.strip() for ln in linhas)
        + "\nEnquanto essa chamada não volta, a janela inteira fica parada — "
          "612 tiques lentos no diário dela de 14/09, o pior de 6 segundos. "
          "Quem lê é o `LeitorDoEstado`, num fio próprio.")


def test_o_piloto_sobe_o_fio_junto_com_o_timer() -> None:
    """Sem o `comecar()` no `_instalado`, o escaninho fica vazio para sempre."""
    corpo = inspect.getsource(hv.Piloto._instalado)
    assert "_estado_vivo.comecar()" in corpo, (
        "o `_instalado` não sobe mais o fio do estado — o tique passaria a ler "
        "um escaninho que ninguém enche, e a tela nasceria e morreria com `{}`")
    assert "_estado_vivo.parar()" in inspect.getsource(hv.Piloto._relatar), (
        "o relato não para mais o fio — a janela iria embora perguntando ao "
        "daemon dela")
