"""O tique da janela NÃO espera pelo daemon — A-TELA-QUE-TRAVA-01.

QUEIXA DELA, 14/09/2026, com os dois controles na mesa:

    *"tem algo muito estranho travando a interface do app. como um todo."*
    (noqa-acento: citação literal dela)

A CAUSA JÁ ESTAVA ESCRITA DENTRO DO PRÓPRIO TIQUE, desde a A-TELA-SAMBA-01 de
03/09/2026: *"as DUAS VIAGENS de IPC do começo deste método são SÍNCRONAS —
elas seguram o laço do GTK inteiro"*. Aquela leva mediu certo e curou de menos:
ela fez o tique PULAR o seguinte quando o atual estourava o teto, o que encurta
a fila e não desbloqueia nada. Enquanto `mesa_viva.estado_do_daemon()` não
volta, o laço do GTK não roda — e janela que não roda o laço não rola, não
recebe clique, não muda o `:hover` e não pisca o cursor. É travar.

O NÚMERO SAI DO DIÁRIO DELA (`interface.log`, a sessão de 14/09/2026, lido sem
escrever): **612 tiques lentos**, e em **457 deles o IPC é 80% ou mais do
custo**. Por aba, o pior e a média do IPC:

    01-jogar      244 lentos   IPC médio 568 ms   pior 6.016 ms
    02-controles   55 lentos   IPC médio 929 ms   pior 2.665 ms
    09-sistema      7 lentos   IPC médio 678 ms   pior 2.002 ms

A CURA É DE FORMA: a leitura passou para um fio próprio (`LeitorDoEstado`), que
pergunta na MESMA cadência de antes — uma por tique — e deixa a resposta num
escaninho. O tique pega o que está lá e segue.

AS TRÊS COISAS QUE ESTA RÉGUA SEGURA, e cada uma é uma forma de a cura morrer:

1. **o tique não espera** — com uma leitura que demora, `leitor.ultimo()` volta
   na hora;
2. **a folga conta RESPOSTAS, não tiques** — sem a `self._geracao`, uma leitura
   muda seria entregue a dez tiques por segundo e os três mudos de
   `MUDOS_SEGUIDOS_QUE_VOLTARAM` queimariam em 300 ms, apagando os quatro
   lugares da tela num piscar. É o defeito que a RECONECTAR-SAMBA-02 curou, e
   que voltaria por outra porta;
3. **a primeira leitura é síncrona** — sem ela o tique de abertura pinta `{}`,
   que a tela lê como *"perguntei e não há ninguém na mesa"*.

A MORDIDA, e ela é a de cima do arquivo: devolva
`st = mesa_viva.estado_do_daemon()` ao corpo de `Piloto._tique` e
:func:`test_o_tique_nao_chama_o_daemon_de_dentro_do_laco` reprova nomeando a
linha.
"""
from __future__ import annotations

import inspect
import pathlib
import sys
import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.interface import hefesto_vivo as hv

#: Uma leitura de mentira que demora o que o daemon dela demorou no pior tique
#: medido. Ela é o instrumento inteiro: se o tique voltar a esperar, é este
#: número que aparece no relógio.
PIOR_MEDIDO_S = 0.30


# --------------------------------------------------------------------------
# 1. O FIO: ele lê fora do laço, e quem pergunta não espera
# --------------------------------------------------------------------------
def test_a_primeira_leitura_e_sincrona() -> None:
    """`comecar()` semeia ANTES de soltar o fio — senão a tela nasce mentindo."""
    leitor = hv.LeitorDoEstado(lambda: {"controllers": [{"uniq": "aa"}]},
                               intervalo=10.0)
    st, erro, geracao = leitor.ultimo()
    assert (st, erro, geracao) == (None, None, 0), (
        "o leitor já tinha resposta antes de `comecar()` — então ele leu no "
        "`__init__`, e um Piloto construído por uma régua abriria socket")
    try:
        leitor.comecar()
        st, erro, geracao = leitor.ultimo()
    finally:
        leitor.parar()
    assert erro is None and st == {"controllers": [{"uniq": "aa"}]}, (
        "a semeadura de `comecar()` não deixou o estado no escaninho — o "
        "primeiro tique pintaria `{}`, e a tela diria que a mesa está vazia")
    assert geracao == 1


def test_quem_pergunta_nao_espera_pela_leitura_lenta() -> None:
    """O teto desta régua é o custo de UM tique, e a leitura demora três.

    MORDIDA: faça `leitor.ultimo()` chamar `self._ler()` e este teste reprova
    relógio na mão — é exatamente o que o tique fazia até 14/09/2026.
    """
    soltar = threading.Event()

    def devagar() -> dict[str, Any]:
        soltar.wait(PIOR_MEDIDO_S)
        return {"controllers": []}

    leitor = hv.LeitorDoEstado(devagar, intervalo=0.0)
    fio = threading.Thread(target=leitor.comecar, daemon=True)
    fio.start()
    try:
        # A primeira resposta ainda está a caminho — e é justamente aí que o
        # tique antigo ficava preso.
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
    dezenas de `state_full` por segundo no daemon dela.
    """
    leitor = hv.LeitorDoEstado()
    assert leitor._intervalo == pytest.approx(hv.TIQUE_MS / 1000.0)


# --------------------------------------------------------------------------
# 2. A FOLGA: ela conta RESPOSTAS, e é a geração que a segura
# --------------------------------------------------------------------------
def _piloto_de_mentira(leitor: hv.LeitorDoEstado) -> Any:
    """O mínimo do `Piloto` que o caminho da resposta toca.

    Montar o Piloto inteiro abriria janela GTK na tela dela, que é a TELA-DELA-01
    desta casa. O que esta régua mede é o caminho, e ele cabe aqui.
    """
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
    """UM tique, pelo método DO PRODUTO.

    Reescrever aqui as linhas do portão da geração faria esta régua medir a
    cópia e dar verde sobre o original — que é a forma de instrumento falso que
    esta casa mais paga. `Piloto._estado_do_tique` é o dono, e é ele que roda.
    """
    return piloto._estado_do_tique()


def test_a_folga_nao_queima_em_tiques_sem_resposta_nova() -> None:
    """Dez tiques sobre UMA leitura muda gastam UM mudo da folga, não dez.

    ESTE É O TESTE QUE A CURA PRECISAVA TER, e sem ele a A-TELA-QUE-TRAVA-01
    reabriria a RECONECTAR-SAMBA-02 por outra porta: com o tique a 100 ms e a
    leitura a 2 s, dez tiques leriam o mesmo `timed out` e a folga de TRÊS
    acabaria em 300 ms — os quatro lugares apagariam e o «Reconectar controles»
    voltaria a sambar, desta vez sem ninguém ter mexido nele.
    """
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


# --------------------------------------------------------------------------
# 3. A MORDIDA: o tique não pode voltar a chamar o daemon
# --------------------------------------------------------------------------
def test_o_tique_nao_chama_o_daemon_de_dentro_do_laco() -> None:
    """`Piloto._tique` não fala com o socket — quem fala é o fio.

    A RÉGUA LÊ O CORPO DO MÉTODO, e a razão de ser assim é que o defeito é
    ESTRUTURAL: não há valor de retorno que denuncie uma chamada síncrona, só a
    espera — e medir espera dentro do `_tique` pediria a janela inteira de pé,
    que é a TELA-DELA-01 desta casa. O que ela pega é a forma que custou seis
    segundos de janela morta.
    """
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
