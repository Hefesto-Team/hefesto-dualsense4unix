"""A calibração grava no disco com o Hefesto DESLIGADO — a ``CAL-2``.

``CALIBRAR-AS-ENTRADAS-01`` §2.6 e §7.3 (26/08/2026).

O DEFEITO QUE ESTA RÉGUA SEGURA
--------------------------------

Até 25/08/2026 o único escritor de produção do ``maquina.json`` era o handler
``machine.declare``, atrás do IPC. **Com o daemon parado, nada do que ela
declara é gravado** — e o rodapé responde *"O Hefesto está desligado — não
gravei o que você declarou"* para uma gravação que não depende de daemon
nenhum. É a ``A-CASA-SABE-E-O-PRODUTO-NÃO-FAZ`` bem no meio do caminho desta
tela: ``gravar_rascunho_da_mesa`` estava escrita desde 24/08 e nunca teve
chamador.

A cerimônia é abandonável — ``[Já chega por hoje]`` em todo passo, sem "tem
certeza?" e sem resumo do que faltou. Isso só é honesto se **nenhuma saída
perder trabalho**, logo cada resposta vai ao disco na hora (R28).

POR QUE A PORTA É A LARGA
--------------------------

``declarar_a_mesa`` é escopada à seção ``mesa`` do documento, e o mapa é chave
de TOPO. Mandar o mapa por ela gravaria a mesa e perderia o mapa **calado** —
que é exatamente o defeito que ``lugar_declarado`` existe para não repetir.
Esta janela usa ``declarar_a_maquina``.

O DISCO DESTE ARQUIVO É O ``tmp_path`` DA BANCADA
--------------------------------------------------

A fixture ``_hefesto_fake_env`` (``tests/conftest.py``, autouse) já desvia os
diretórios XDG para o ``tmp_path`` do teste. A primeira asserção CONFERE isso
antes de escrever qualquer coisa: uma régua que gravasse no ``~/.config`` dela
seria o ``CANARIO-FS-01`` disparando, e o defeito estaria na régua.
"""
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
    """O daemon MORTO — toda chamada levanta, como no soquete ausente.

    Um dublê que só sabe passar não é régua (``COMO-EXECUTAR-UMA-SPRINT`` §4);
    este só sabe RECUSAR, que é o estado que a régua precisa exercer.
    """

    def __init__(self) -> None:
        self.tentativas: list[str] = []

    def __call__(self, metodo: str, *_a: Any, **_kw: Any) -> Any:
        self.tentativas.append(metodo)
        raise ConnectionRefusedError(
            "o soquete do Hefesto não respondeu (daemon parado)"
        )


def _logica() -> LogicaDaCalibracao:
    """A lógica com o gravador DE PRODUÇÃO — nada de dublê aqui.

    É o ponto do arquivo: o default de ``LogicaDaCalibracao`` tem de ser o
    caminho que não passa por IPC nenhum.
    """
    return LogicaDaCalibracao(MapaDaMesa(), mesa_com_hub_e_tres_aparelhos())


# ---------------------------------------------------------------------------
# A mordida da CAL-2
# ---------------------------------------------------------------------------


def test_grava_sem_ipc(tmp_path: Path) -> None:
    """Com o IPC recusando tudo, o ``maquina.json`` MUDA.

    MORDIDA: comentar a chamada a ``self._gravar()`` no fim de
    ``LogicaDaCalibracao.responder`` — que é voltar ao mundo em que só o
    "Aplicar" do rodapé (ou o ``machine.declare``) escreve. O arquivo não
    nasce, e o teste reprova imprimindo a frase que a tela mostraria.
    """
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
    # O caminho não vai ao disco desde a A-ENTRADA-TEM-UM-REGISTRO-SO-01
    # (28/09/2026): o buraco do hub vai pelo nó dele.
    assert "caminho" not in portas[numeros[0]]
    assert carregar_maquina().mapa.portas[numeros[0]].caminho == "3-1"
    assert ipc.tentativas == [], "a gravação passou por IPC, e não devia"
    assert logica.ultimo_recibo is not None and logica.ultimo_recibo.gravou


def test_cada_resposta_vai_ao_disco_na_hora(tmp_path: Path) -> None:
    """Matar o processo no meio não perde nada (R28).

    Não há "aplicar" pendente: entre uma resposta e a seguinte, o que está no
    disco já é o que ela respondeu. A régua simula a morte relendo o arquivo
    sem que ninguém tenha fechado a janela.
    """
    logica = _logica()
    logica.responder(logica.perguntas_sentadas()[0], FACE_HUB)

    do_disco = json.loads(caminho_da_maquina().read_text(encoding="utf-8"))
    assert len(do_disco["mapa"]["portas"]) == 4, (
        "o disco não tem os quatro lugares que ela acabou de dar"
    )


def test_o_disco_recusando_nao_derruba_o_passo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Uma exceção no meio do clique levaria junto a resposta dela.

    ``declarar_a_maquina`` **nunca levanta** — traduz as três falhas possíveis
    em ``Recibo``. Esta régua exerce o caminho de erro, que é o que o dublê que
    só sabe passar nunca exercita.
    """
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


# ---------------------------------------------------------------------------
# A ABA 08 GRAVA A SEÇÃO `mesa` COM O HEFESTO DESLIGADO — 28/09/2026
# ---------------------------------------------------------------------------
#
# A-CONEXOES-DIZ-O-QUE-O-PRODUTO-JA-MEDE-01. `lugar_declarado.declarar_a_mesa`,
# a porta da seção `mesa`, não tinha chamador: as duas perguntas da sala (a
# altura da antena e a visada) e o «— O que é? —» de um vizinho só gravavam
# pelo `machine.declare`, e com o serviço parado o gesto recusava. Agora o
# `_declarar` da aba desce ao disco quando o serviço NÃO respondeu, e só aí.
#
# A MORDIDA: arranque o desvio (`if not motivo:` em `a08_conexoes._declarar`) e
# `test_a_08_grava_a_sala_com_o_servico_parado` reprova, com o disco vazio.


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
