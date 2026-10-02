"""A calibração grava no disco com o Hefesto DESLIGADO — a ``CAL-2``."""
from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.widgets.calibrar_entradas import (
    FACE_HUB,
    LogicaDaCalibracao,
)
from hefesto_dualsense4unix.utils.maquina import MapaDaMesa, caminho_da_maquina, carregar_maquina
from tests.unit.test_a_fase_sentada_resolve_o_hub import (
    mesa_com_hub_e_tres_aparelhos,
)


class IpcQueRecusaTudo:
    """O daemon MORTO — toda chamada levanta, como no soquete ausente."""

    def __init__(self) -> None:
        self.tentativas: list[str] = []

    def __call__(self, metodo: str, *_a: Any, **_kw: Any) -> Any:
        self.tentativas.append(metodo)
        raise ConnectionRefusedError(
            "o soquete do Hefesto não respondeu (daemon parado)"
        )


def _logica() -> LogicaDaCalibracao:
    """A lógica com o gravador DE PRODUÇÃO — nada de dublê aqui."""
    return LogicaDaCalibracao(MapaDaMesa(), mesa_com_hub_e_tres_aparelhos())


def test_grava_sem_ipc(tmp_path: Path) -> None:
    """Com o IPC recusando tudo, o ``maquina.json`` MUDA."""
    caminho = caminho_da_maquina()
    assert tmp_path in caminho.parents, f"{caminho} escapou do tmp da bancada"
    assert not caminho.exists()

    ipc = IpcQueRecusaTudo()
    logica = _logica()
    numeros = logica.responder(logica.perguntas_sentadas()[0], FACE_HUB)

    assert caminho.exists(), (
        "a resposta dela não chegou ao disco. É a frase que a tela mostraria: "
        "'O Hefesto está desligado — não gravei o que você declarou' — para "
        "uma gravação que não depende de daemon nenhum"
    )
    documento = json.loads(caminho.read_text(encoding="utf-8"))
    portas = documento["mapa"]["portas"]
    assert set(portas) == set(numeros)
    assert "caminho" not in portas[numeros[0]]
    assert carregar_maquina().mapa.portas[numeros[0]].caminho == "3-1"
    assert ipc.tentativas == [], "a gravação passou por IPC, e não devia"
    assert logica.ultimo_recibo is not None and logica.ultimo_recibo.gravou


def test_cada_resposta_vai_ao_disco_na_hora(tmp_path: Path) -> None:
    """Matar o processo no meio não perde nada (R28)."""
    logica = _logica()
    logica.responder(logica.perguntas_sentadas()[0], FACE_HUB)

    do_disco = json.loads(caminho_da_maquina().read_text(encoding="utf-8"))
    assert len(do_disco["mapa"]["portas"]) == 4, (
        "o disco não tem os quatro lugares que ela acabou de dar"
    )


def test_o_disco_recusando_nao_derruba_o_passo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Uma exceção no meio do clique levaria junto a resposta dela."""
    def recusa(_declaracao: Mapping[str, Any]) -> Any:
        raise OSError(28, "sem espaço no dispositivo")

    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.lugar_declarado."
        "gravar_maquina_com_descartes",
        recusa,
    )
    logica = _logica()
    numeros = logica.responder(logica.perguntas_sentadas()[0], FACE_HUB)

    assert len(numeros) == 4, "o passo caiu junto com a gravação"
    assert logica.ultimo_recibo is not None
    assert not logica.ultimo_recibo.gravou
    assert logica.ultimo_recibo.motivo == "disco"


class _PonteDoServico:
    """A ponte do piloto, só com o `machine_declare` — com a resposta escolhida.

    Mesma forma de `ipc_bridge.machine_declare`: `(ok, motivo)`, e `(False,
    None)` quando o serviço não respondeu. O dublê não é mais frouxo que ela:
    ele devolve exatamente a dupla que a ponte devolve em cada caso.
    """

    def __init__(self, resposta: tuple[bool, str | None]) -> None:
        self.resposta = resposta
        self.pedidos: list[dict[str, Any]] = []

    def machine_declare(self, maquina: dict[str, Any]) -> tuple[bool, str | None]:
        self.pedidos.append(maquina)
        return self.resposta


def _a08() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


def test_a_08_grava_a_sala_com_o_servico_parado(tmp_path: Path) -> None:
    caminho = caminho_da_maquina()
    assert tmp_path in caminho.parents, f"{caminho} escapou do tmp da bancada"
    assert not caminho.exists()

    ponte = _PonteDoServico((False, None))
    a08 = _a08()
    a08.sala_altura(None, {"modo": "acima"}, ponte)
    a08.sala_visada(None, {"modo": "com_gente"}, ponte)

    assert ponte.pedidos, "o serviço tem de ser perguntado PRIMEIRO — o disco é o plano B"
    assert caminho.exists(), "a resposta dela não chegou ao disco com o serviço parado"
    gravado = carregar_maquina()
    assert gravado.mesa.altura_da_antena == "acima"
    assert gravado.mesa.linha_de_visada == "com_gente", (
        "a segunda resposta apagou a primeira — a porta tem de fundir, não trocar")


def test_a_08_nao_grava_por_tras_do_servico_que_recusou(tmp_path: Path) -> None:
    """O serviço respondeu «não»: o gesto recusa, e o disco fica como estava."""
    ponte = _PonteDoServico((False, "não vou sobrescrever o que está lá"))
    with pytest.raises(RuntimeError, match="não vou sobrescrever"):
        _a08().sala_altura(None, {"modo": "abaixo"}, ponte)
    assert not caminho_da_maquina().exists()


def test_a_08_nao_grava_de_novo_o_que_o_servico_gravou(tmp_path: Path) -> None:
    """O serviço aceitou: quem gravou foi ele, e a aba não escreve por cima."""
    ponte = _PonteDoServico((True, None))
    _a08().sala_altura(None, {"modo": "acima"}, ponte)
    assert not caminho_da_maquina().exists()


def test_a_08_recusa_dizendo_quando_nem_o_disco_aceita(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem serviço e sem disco, o gesto recusa — nunca um verde sobre nada."""
    def recusa(_declaracao: Mapping[str, Any]) -> Any:
        raise OSError(28, "sem espaço no dispositivo")

    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.lugar_declarado.gravar_rascunho_da_mesa",
        recusa,
    )
    with pytest.raises(RuntimeError):
        _a08().sala_altura(None, {"modo": "acima"}, _PonteDoServico((False, None)))
