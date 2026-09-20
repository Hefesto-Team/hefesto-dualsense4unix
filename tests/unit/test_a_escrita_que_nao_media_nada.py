"""ESCRITA-QUE-NAO-MEDE-01 e ESCRITOR-CRU-03 — dois instrumentos que diziam
«enviado» e «disputada» sem medir coisa nenhuma, achados lendo o código em
19/09/2026.

O QUE ESTE ARQUIVO TRAVA, e os dois são a mesma família
=======================================================

**1. O log que dizia `enviado=True` sem conferir byte nenhum.** O corpo do
`gatilho_da_cor` fazia ``escritor(list(report))`` e logo depois ``ok = True``,
incondicional; o `writeReport` do handle escrevia e **jogava fora o retorno**
do `device.write`. A única conferência que existia
(``int(escrito) == len(report)``) morava no ramo de fallback — e handle BT
toma SEMPRE o ramo do `writeReport`, então ela nunca rodava no rádio. Medido
contra o aparelho na mesma noite: o log dizia ``cor=(0,255,0) enviado=True``
com a barra física APAGADA, e ela confirmou com o olho.

**2. O `lightbar_disputada` que continuava `True` com a Steam morta.** O campo
é lido da FOTO que o sentinela tira no tique de 30 s, e era devolvido cru.
Medido: SIGTERM na Steam, `pgrep` zero, e sete segundos depois o
`daemon.state_full` ainda publicava `True`. E há estados em que ninguém zera a
foto NUNCA — em Modo Nativo o `vigiar_escritor_cru` é no-op total (nem sonda),
e sem nó mapeado ele desiste antes de chegar ao sentinela.

A ASSINATURA É A DA CASA: *o instrumento respondia sobre outra coisa que não o
produto* — sobre a chamada não ter levantado exceção, e sobre a foto de trinta
segundos atrás.

**O QUE ESTE ARQUIVO NÃO TESTA, de propósito:** nada aqui toca o aparelho, o
daemon vivo, o rádio ou a Steam. A escrita é exercitada contra um `device` de
mentira que DEVOLVE NÚMERO, e a liveness de PID entra por injeção — é o que
permite exercitar "o processo morreu" sem matar processo nenhum.

**Onde a cura mora:**
- `core/backend_pydualsense.py` — `_bytes_que_sairam`, `_escrita_completa`,
  `_PinnedPyDualSense._escrever_conferindo` e o `ok` do gatilho da cor;
- `core/escritor_cru.py` — `processo_vivo` e `Veredito.segurado_de_fato`;
- `daemon/ipc_handlers.py` — `_lightbar_disputada`.
"""
from __future__ import annotations

import threading
from typing import Any

import pytest

from hefesto_dualsense4unix.core import escritor_cru as _escritor_cru
from hefesto_dualsense4unix.core.backend_pydualsense import (
    PyDualSenseController,
    _bytes_que_sairam,
    _DesiredOutput,
    _escrita_completa,
)
from hefesto_dualsense4unix.core.escritor_cru import Veredito

# --------------------------------------------------------------------------
# O predicado, nu: o que conta como prova de que a escrita saiu
# --------------------------------------------------------------------------


def test_escrita_curta_nao_e_escrita_completa() -> None:
    """78 pedidos, 40 saídos: o fio disse que faltou, e `False` é a resposta."""
    assert _escrita_completa(40, 78) is False
    assert _bytes_que_sairam(40) == 40


def test_o_erro_do_hidapi_nao_e_escrita_completa() -> None:
    """`-1` é o erro do `hid_write`, e `-1 != 78`. Nunca vira `enviado=True`."""
    assert _escrita_completa(-1, 78) is False


def test_escrita_inteira_e_escrita_completa() -> None:
    assert _escrita_completa(78, 78) is True


def test_o_fio_que_nao_responde_nao_e_acusado() -> None:
    """`None` = o device não disse. Ausência de dado não é prova de falha.

    É a mesma disciplina do `sondado_em is None` do `escritor_cru`: esta casa
    não acusa sem prova, nos dois sentidos.
    """
    assert _bytes_que_sairam(None) is None
    assert _escrita_completa(None, 78) is True


def test_o_duble_nao_inventa_escrita_curta() -> None:
    """Um objeto que não é `int` é ausência de resposta, não acusação.

    Sem isto, `int(MagicMock())` devolveria `1` e TODA escrita da suíte viraria
    "curta" — uma acusação nascida de dublê, que é o mesmo defeito com o sinal
    trocado.
    """

    class _Qualquer:
        pass

    assert _bytes_que_sairam(_Qualquer()) is None
    assert _escrita_completa(_Qualquer(), 78) is True


def test_bool_nao_conta_como_numero_de_bytes() -> None:
    """`True` É `int` em Python, e um dublê que o devolve não quis dizer «1»."""
    assert _bytes_que_sairam(True) is None
    assert _escrita_completa(True, 78) is True


# --------------------------------------------------------------------------
# O `writeReport` do handle: o retorno deixou de ser jogado fora
# --------------------------------------------------------------------------


class _DeviceQueResponde:
    """Um `device` de mentira que DEVOLVE NÚMERO, como o `hidapi` devolve.

    Os dublês que já existiam na suíte devolvem `None` — e por isso nenhum
    deles conseguia revelar este defeito. Este devolve o que mandarem.
    """

    def __init__(self, resposta: Any) -> None:
        self.resposta = resposta
        self.quadros: list[bytes] = []

    def write(self, dados: bytes) -> Any:
        self.quadros.append(bytes(dados))
        return self.resposta


def _handle_cru(resposta: Any) -> Any:
    """Um objeto mínimo com o `writeReport` DO PRODUTO emprestado.

    O método exercitado é o do produto, como manda o método do
    `test_lightbar_medir_o_0x08.py`: um dublê que reimplementasse a regra
    mediria o dublê.
    """
    from hefesto_dualsense4unix.core.backend_pydualsense import _PinnedPyDualSense

    class _Handle:
        pass

    inst = _Handle()
    inst.device = _DeviceQueResponde(resposta)  # type: ignore[attr-defined]
    inst._write_lock = threading.RLock()  # type: ignore[attr-defined]
    inst._bt_seq = 0  # type: ignore[attr-defined]
    inst.writeReport = _PinnedPyDualSense.writeReport.__get__(inst)  # type: ignore[attr-defined]
    inst._escrever_conferindo = (  # type: ignore[attr-defined]
        _PinnedPyDualSense._escrever_conferindo.__get__(inst)
    )
    return inst


def test_write_report_devolve_quantos_bytes_sairam() -> None:
    """O retorno do `device.write` PARA de ser jogado fora."""
    handle = _handle_cru(64)
    assert handle.writeReport([0x02] + [0] * 47) == 64


def test_write_report_do_radio_tambem_devolve() -> None:
    """O ramo 0x31 (78 bytes, carimbado) confere igual ao do cabo.

    É o ramo que o rádio toma SEMPRE, e era o único sem conferência nenhuma.
    """
    quadro = [0x31] + [0] * 77
    handle = _handle_cru(78)
    assert handle.writeReport(list(quadro)) == 78
    # o carimbo continua acontecendo: o comportamento da escrita não mudou
    assert len(handle.device.quadros) == 1
    assert len(handle.device.quadros[0]) == 78


def test_write_report_nao_mente_sobre_escrita_curta() -> None:
    handle = _handle_cru(12)
    assert handle.writeReport([0x31] + [0] * 77) == 12


# --------------------------------------------------------------------------
# A RÉGUA QUE MORDE (1): escrita curta tem de produzir `enviado=False`
# --------------------------------------------------------------------------


class _HandleDoRadio:
    """Handle BT mínimo: `conType` de rádio + o `writeReport` que RESPONDE.

    É o ramo `callable(escritor)` do gatilho da cor — o que handle BT toma
    sempre, e onde o `ok = True` era incondicional.
    """

    def __init__(self, resposta: Any) -> None:
        self.conType = type("Con", (), {"name": "BT_31"})()
        self.resposta = resposta
        self.reports: list[list[int]] = []

    def writeReport(self, dados: list[int]) -> Any:  # noqa: N802 (API do upstream)
        self.reports.append(list(dados))
        return self.resposta


def _controlador_com(handle: Any) -> PyDualSenseController:
    ctl = PyDualSenseController()
    ctl._handles = {"aa:bb:cc:00:00:01": handle}
    ctl._primary_key = "aa:bb:cc:00:00:01"
    ctl._desired_default = _DesiredOutput(led=(0, 255, 0))
    return ctl


def test_a_escrita_curta_no_radio_sai_como_nao_enviado() -> None:
    """A MORDIDA. O fio disse que só metade saiu — `enviado` tem de ser False.

    Este é o caso exato da noite de 19/09: o report vai, a chamada não levanta
    exceção, e a barra fica apagada. Com `ok = True` incondicional este teste
    reprova.
    """
    handle = _HandleDoRadio(20)
    ctl = _controlador_com(handle)
    resultado = ctl.reescrever_lightbar_por_hidraw()
    assert handle.reports, "o produto nem chegou a escrever — teste inválido"
    assert resultado == {"aa:bb:cc:00:00:01": False}


def test_o_erro_do_fio_no_radio_sai_como_nao_enviado() -> None:
    """`-1` é o `hid_write` falhando, e não pode virar «enviado»."""
    ctl = _controlador_com(_HandleDoRadio(-1))
    assert ctl.reescrever_lightbar_por_hidraw() == {"aa:bb:cc:00:00:01": False}


def test_a_escrita_inteira_no_radio_continua_enviada() -> None:
    """O outro lado da mordida: escrita boa NÃO pode virar `False`.

    Uma régua que só sabe reprovar passaria dizendo que nada funciona.
    """
    handle = _HandleDoRadio(None)
    ctl = _controlador_com(handle)
    resultado = ctl.reescrever_lightbar_por_hidraw()
    assert resultado == {"aa:bb:cc:00:00:01": True}
    tamanho = len(handle.reports[0])
    ctl_dois = _controlador_com(_HandleDoRadio(tamanho))
    assert ctl_dois.reescrever_lightbar_por_hidraw() == {
        "aa:bb:cc:00:00:01": True
    }


# --------------------------------------------------------------------------
# A RÉGUA QUE MORDE (2): a foto conferida contra o presente
# --------------------------------------------------------------------------

#: O nó da mesa de mentira. Nada aqui chega perto de `/dev/hidraw*` de verdade.
NO = "/dev/hidraw9"


def _foto_com(pids: tuple[int, ...]) -> Veredito:
    return Veredito(sondado_em=100.0, por_no={NO: pids})


def test_a_foto_com_o_processo_morto_para_de_acusar() -> None:
    """A MORDIDA. A Steam morreu; a foto ainda a lembra; o campo tem de zerar.

    Com `segurado` cru no lugar de `segurado_de_fato`, isto reprova — que é o
    defeito medido em 19/09, sete segundos depois do SIGTERM.
    """
    foto = _foto_com((4242,))
    assert foto.segurado(NO) is True, "a foto guarda o PID — preparo do teste"
    assert foto.segurado_de_fato(NO, vivo=lambda _p: False) is False
    assert foto.nos_segurados_de_fato(vivo=lambda _p: False) == ()


def test_a_foto_com_o_processo_vivo_continua_acusando() -> None:
    """O outro lado: a Steam ABERTA continua sendo dita, e é o caso normal."""
    foto = _foto_com((4242,))
    assert foto.segurado_de_fato(NO, vivo=lambda _p: True) is True
    assert foto.nos_segurados_de_fato(vivo=lambda _p: True) == (NO,)


def test_basta_um_vivo_entre_varios_para_o_no_seguir_disputado() -> None:
    """Dois PIDs lembrados, um morto: quem sobrou ainda segura o nó."""
    foto = _foto_com((11, 22))
    assert foto.segurado_de_fato(NO, vivo=lambda p: p == 22) is True
    assert foto.pids_vivos(NO, vivo=lambda p: p == 22) == (22,)


def test_a_conferencia_so_apaga_aviso_nunca_acende() -> None:
    """Nó que a sonda viu LIVRE não pode virar disputado pela conferência."""
    foto = Veredito(sondado_em=100.0, por_no={NO: ()})
    assert foto.segurado_de_fato(NO, vivo=lambda _p: True) is False
    assert foto.nos_segurados_de_fato(vivo=lambda _p: True) == ()


def test_sem_sonda_nenhuma_a_resposta_continua_falsa() -> None:
    """Ausência de sonda não é prova de que ninguém segura — e nunca foi."""
    assert Veredito().segurado_de_fato(NO) is False


def test_processo_vivo_conhece_o_proprio_processo() -> None:
    """A sonda real, sem injeção: este processo existe, e o PID 0 não."""
    import os

    assert _escritor_cru.processo_vivo(os.getpid()) is True
    assert _escritor_cru.processo_vivo(0) is False


# --------------------------------------------------------------------------
# A RÉGUA QUE MORDE (3): o campo que a TELA dela lê
# --------------------------------------------------------------------------


class _DaemonComSentinela:
    """Um daemon de mentira que carrega um sentinela REAL com a foto posta."""

    def __init__(self, pids: tuple[int, ...]) -> None:
        self._sentinela_de_escritor_cru = _escritor_cru.SentinelaDeEscritorCru()
        self._sentinela_de_escritor_cru._veredito = _foto_com(pids)


@pytest.fixture()
def _handler() -> Any:
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    return IpcHandlersMixin.__new__(IpcHandlersMixin)


def test_lightbar_disputada_zera_quando_o_escritor_cru_some(
    _handler: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A MORDIDA, no campo que chega à tela dela.

    O `state_full` publicava `True` com a Steam morta. Trocar
    `segurado_de_fato` de volta por `segurado` faz este teste reprovar.
    """
    monkeypatch.setattr(_escritor_cru, "processo_vivo", lambda _p: False)
    _handler.daemon = _DaemonComSentinela((4242,))
    assert _handler._lightbar_disputada("aabbcc000001", {"aabbcc000001": NO}) is False


def test_lightbar_disputada_segue_verdadeira_com_a_steam_viva(
    _handler: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E o aviso continua aparecendo quando ele é verdade."""
    monkeypatch.setattr(_escritor_cru, "processo_vivo", lambda _p: True)
    _handler.daemon = _DaemonComSentinela((4242,))
    assert _handler._lightbar_disputada("aabbcc000001", {"aabbcc000001": NO}) is True
