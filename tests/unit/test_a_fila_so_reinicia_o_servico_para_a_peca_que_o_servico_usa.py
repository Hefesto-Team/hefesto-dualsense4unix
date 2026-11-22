"""A fila só reinicia o serviço para a peça que o serviço usa.

A-FILA-SO-REINICIA-O-SERVICO-PARA-A-PECA-QUE-O-SERVICO-USA-01. Uma atualização que só trouxe o
``umu`` reiniciava o serviço e reabria a janela e a bandeja: o selo do serviço acendia por toda
peça pronta, sem olhar o que a peça troca. TUDO É DE MENTIRA: o lar é ``tmp_path`` com ``XDG_*``
desviados, as peças são dublês, ``reiniciar`` e ``reabrir`` só contam, e a rede é barrada.

AS MORDIDAS (feitas na sprint, com a cura devolvida e o md5 conferido): o ``_prontas_que_reiniciam``
voltando a contar toda peça pronta reprova o caso da peça que o serviço não usa pela frase «a peça
que o serviço não usa reiniciou o serviço», o do reinício do meio e o do jogo que abre no fim; o
``umu`` do registro sem a declaração falsa reprova o caso do registro real.
"""
from __future__ import annotations

import re
import socket
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import atualizador as at
from hefesto_dualsense4unix.app.actions import pecas_do_atualizador as pa


@pytest.fixture(autouse=True)
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    casa = tmp_path / "casa"
    for var, sub in (("XDG_CONFIG_HOME", ".config"), ("XDG_STATE_HOME", ".local/state"),
                     ("XDG_CACHE_HOME", ".cache"), ("XDG_DATA_HOME", ".local/share"),
                     ("XDG_RUNTIME_DIR", "run")):
        (casa / sub).mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(var, str(casa / sub))
    monkeypatch.setenv("HOME", str(casa))
    return casa


@pytest.fixture(autouse=True)
def trava_da_rede(monkeypatch: pytest.MonkeyPatch) -> Any:
    pedidos: list[object] = []

    def _resolver(host: object, *_a: object, **_k: object) -> list[object]:
        pedidos.append(host)
        raise OSError(f"o teste foi à rede: {host}")

    monkeypatch.setattr(socket, "getaddrinfo", _resolver)
    yield pedidos
    assert not pedidos, f"o teste foi à rede: {pedidos}"


def _peca(ident: str, *, reinicia: bool, falha: bool = False, no_baixar: Any = None,
          no_aplicar: Any = None) -> at.Peca:
    def etapa(nome: str) -> Any:
        def fazer(passo: at.Passo, _dados: dict[str, Any]) -> None:
            if nome == "baixar" and no_baixar is not None:
                no_baixar()
            if nome == "instalar" and falha:
                raise at.EtapaFalhouError("o pacote não instala")
            if nome == "aplicar" and no_aplicar is not None:
                no_aplicar()
            passo.fracao(1.0)
        return fazer

    return at.Peca(ident, ident.upper(), "dica", "todos",
                   lambda rede: at.Versoes("1.0", "1.1" if rede else None),
                   etapa("baixar"), etapa("instalar"), etapa("aplicar"),
                   reinicia_o_servico=reinicia)


class _Servico:
    def __init__(self, ao_dormir: Any = None) -> None:
        self.ao_dormir = ao_dormir
        self.reinicios = 0
        self.reaberturas = 0
        self.dormiu = 0
        self.tempo = 0.0

    def reiniciar(self) -> bool:
        self.reinicios += 1
        return True

    def reabrir(self) -> bool:
        self.reaberturas += 1
        return True

    def dormir(self, segundos: float) -> None:
        self.dormiu += 1
        self.tempo += segundos
        if self.ao_dormir is not None:
            self.ao_dormir()


def _rodar(lista: list[at.Peca], servico: _Servico, jogo_aberto: Any = None) -> int:
    at.conferir(rede=True, lista=lista)
    return at.rodar([p.id for p in lista], lista=lista,
                    jogo_aberto=jogo_aberto or (lambda: False),
                    reiniciar=servico.reiniciar, reabrir=servico.reabrir,
                    dormir=servico.dormir, relogio=lambda: servico.tempo)


def _linha(ident: str) -> dict[str, Any]:
    return next(p for p in at.ler_o_andamento()["pecas"] if p["id"] == ident)


def test_a_fila_so_da_peca_que_o_servico_nao_usa_nao_o_reinicia() -> None:
    """D-2211-A-FILA-SO-REINICIA-O-SERVICO-PARA-A-PECA-QUE-ELE-USA."""
    servico = _Servico()
    rc = _rodar([_peca("fora", reinicia=False)], servico)
    assert rc == 0
    assert _linha("fora")["selo"] == at.PRONTA
    assert servico.reinicios == 0, "a peça que o serviço não usa reiniciou o serviço"
    assert servico.reaberturas == 0, "a peça que o serviço não usa reabriu a janela"
    assert at.ler_o_andamento()["reinicio"]["selo"] != at.PRONTA
    assert at.ler_o_andamento()["reinicio"]["selo"] == at.ATUALIZADA


def test_a_fila_da_peca_que_o_servico_usa_o_reinicia_uma_vez() -> None:
    servico = _Servico()
    assert _rodar([_peca("dentro", reinicia=True)], servico) == 0
    assert (servico.reinicios, servico.reaberturas) == (1, 1)
    assert at.ler_o_andamento()["reinicio"]["selo"] == at.PRONTA


def test_a_fila_mista_reinicia_uma_vez_so() -> None:
    servico = _Servico()
    lista = [_peca("fora", reinicia=False), _peca("dentro", reinicia=True)]
    assert _rodar(lista, servico) == 0
    assert (servico.reinicios, servico.reaberturas) == (1, 1)


def test_a_peca_que_nao_reinicia_pronta_com_a_que_reinicia_falhada_nao_reinicia() -> None:
    servico = _Servico()
    lista = [_peca("fora", reinicia=False), _peca("dentro", reinicia=True, falha=True)]
    assert _rodar(lista, servico) == 1
    assert _linha("fora")["selo"] == at.PRONTA
    assert _linha("dentro")["selo"] == at.FALHOU
    assert servico.reinicios == 0, "a peça que o serviço não usa reiniciou o serviço"
    assert servico.reaberturas == 0


def test_o_jogo_que_abre_no_fim_nao_segura_a_fila_da_peca_que_o_servico_nao_usa() -> None:
    servico = _Servico()
    aberto = [False]
    lista = [_peca("fora", reinicia=False, no_aplicar=lambda: aberto.__setitem__(0, True))]
    assert _rodar(lista, servico, jogo_aberto=lambda: aberto[0]) == 0
    assert servico.dormiu == 0, "a fila esperou o jogo por um reinício que não precisava"
    assert servico.reinicios == 0


def test_o_jogo_que_abre_no_fim_segura_a_fila_da_peca_que_o_servico_usa() -> None:
    aberto = [False]
    servico = _Servico(lambda: aberto.__setitem__(0, False))
    lista = [_peca("dentro", reinicia=True, no_aplicar=lambda: aberto.__setitem__(0, True))]
    assert _rodar(lista, servico, jogo_aberto=lambda: aberto[0]) == 0
    assert servico.dormiu > 0
    assert servico.reinicios == 1


def test_o_reinicio_do_meio_nao_vem_da_peca_que_o_servico_nao_usa() -> None:
    """A que não reinicia pronta e a que reinicia esperando o jogo: o serviço só reinicia depois
    que a segunda terminou, e uma vez."""
    aberto = [False]
    servico = _Servico(lambda: aberto.__setitem__(0, False))
    reinicios_na_volta: list[int] = []

    def na_volta() -> None:
        reinicios_na_volta.append(servico.reinicios)

    lista = [_peca("fora", reinicia=False),
             _peca("dentro", reinicia=True, no_baixar=lambda: aberto.__setitem__(0, True),
                   no_aplicar=na_volta)]
    assert _rodar(lista, servico, jogo_aberto=lambda: aberto[0]) == 0
    assert reinicios_na_volta == [0], "a peça que o serviço não usa reiniciou o serviço no meio"
    assert servico.reinicios == 1


def test_o_registro_real_declara_o_que_o_servico_usa() -> None:
    por_id = {p.id: p for p in pa.registro()}
    assert por_id["umu"].reinicia_o_servico is False
    assert por_id["python"].reinicia_o_servico is True
    assert por_id["hefesto"].reinicia_o_servico is True


def test_toda_peca_do_registro_declara_o_campo_e_o_falso_cita_a_medida() -> None:
    doc = pa.registro.__doc__ or ""
    for peca in pa.registro():
        assert isinstance(peca.reinicia_o_servico, bool), peca.id
        if not peca.reinicia_o_servico:
            assert re.search(rf"``{peca.id}`` é falso:", doc), \
                f"{peca.id}: o falso sem a medida na docstring do registro"
            assert re.search(r"\w+\.py:\d+", doc), f"{peca.id}: a medida sem arquivo:linha"
