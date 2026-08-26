"""Um toque em "Num hub" coloca o hub **e tudo que pende dele**.

``CALIBRAR-AS-ENTRADAS-01``, tarefa ``CAL-3`` (26/08/2026). É a mordida que
manda desta frente.

POR QUE ESTA É A PERGUNTA QUE MAIS PAGA
----------------------------------------

Quem pende do hub **está no hub** — isso o barramento já diz sozinho, pelo
``cadeia_de_hubs``. Perguntar aparelho por aparelho seria cobrar dela uma
resposta que a máquina já tem, e a cerimônia de quatro toques viraria de sete
na mesa dela.

A MESA DESTE ARQUIVO
---------------------

Um hub e três aparelhos pendurados, montados à mão. Não é a bancada de mentira
do mapa 2D de propósito: aquela tem DOIS hubs encadeados, e o que esta régua
mede é a conta — quatro aparelhos, um toque, quatro lugares. Uma mesa com dois
hubs mediria a mesma coisa com mais ruído e uma conta que ninguém confere de
cabeça.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from hefesto_dualsense4unix.app.widgets.calibrar_entradas import (
    FACE_ATRAS,
    FACE_HUB,
    LogicaDaCalibracao,
)
from hefesto_dualsense4unix.integrations.censo_do_barramento import Aparelho, Censo
from hefesto_dualsense4unix.integrations.lugar_declarado import Recibo
from hefesto_dualsense4unix.utils.maquina import MapaDaMesa

#: A raiz de mentira. Nenhum caminho do ``/sys`` desta máquina é tocado: o
#: ``Censo`` entra por argumento, que é o mesmo ponto de injeção do resto da
#: casa.
RAIZ = "/mentira/bus/usb/devices"
USB3 = f"{RAIZ}/usb3"


class GravadorDeMentira:
    """O disco, em memória. Guarda o que foi mandado gravar e quantas vezes."""

    def __init__(self, *, recusa: bool = False) -> None:
        self.recusa = recusa
        self.chamadas: list[dict[str, Any]] = []

    def __call__(self, declaracao: Mapping[str, Any]) -> Recibo:
        self.chamadas.append(dict(declaracao))
        if self.recusa:
            return Recibo(False, "disco")
        return Recibo(True)


def _aparelho(
    nome: str,
    *,
    pai: str = "",
    e_hub: bool = False,
    e_raiz: bool = False,
    especie: str = "aparelho",
) -> Aparelho:
    return Aparelho(
        no=f"{USB3}/{nome}",
        nome_do_kernel=nome,
        pai=f"{USB3}/{pai}" if pai else "",
        e_hub=e_hub,
        e_raiz=e_raiz,
        especie=especie,
        busnum=3,
    )


def mesa_com_hub_e_tres_aparelhos() -> Censo:
    """O hub ``3-1`` e três aparelhos pendurados nele — quatro ao todo.

    O hub-raiz entra porque ``conectados()`` é quem o filtra, e um censo sem
    raiz nenhuma não parece com o que o produto lê.
    """
    raiz = Aparelho(no=USB3, nome_do_kernel="usb3", e_hub=True, e_raiz=True, busnum=3)
    hub = _aparelho("3-1", pai="", e_hub=True, especie="hub")
    # O pai dos três é o próprio hub, e o `no` do pai tem de casar byte a byte
    # com o `no` do hub — é assim que `cadeia_de_hubs` sobe a árvore.
    filhos = [
        _aparelho("3-1.1", pai="3-1", especie="adaptador Bluetooth"),
        _aparelho("3-1.2", pai="3-1", especie="DualSense"),
        _aparelho("3-1.3", pai="3-1", especie="receptor 2,4 GHz"),
    ]
    return Censo(aparelhos=(raiz, hub, *filhos))


def _logica(gravador: GravadorDeMentira | None = None) -> LogicaDaCalibracao:
    return LogicaDaCalibracao(
        MapaDaMesa(),
        mesa_com_hub_e_tres_aparelhos(),
        gravar=gravador or GravadorDeMentira(),
    )


# ---------------------------------------------------------------------------
# A mordida que manda
# ---------------------------------------------------------------------------


def test_um_toque_no_hub_coloca_tudo_que_pende_dele() -> None:
    """Quatro aparelhos, UM toque, quatro lugares.

    MORDIDA: arrancar a descida de ``_pendentes_de`` (devolver só o próprio
    aparelho, como se hub fosse aparelho comum). O toque coloca o hub e os três
    pendurados ficam sem lugar — e o teste reprova **listando quais**, que é o
    que separa "falhou" de um diagnóstico.
    """
    logica = _logica()
    perguntas = logica.perguntas_sentadas()
    do_hub = next(p for p in perguntas if p.caminho == "3-1")
    assert do_hub.e_hub

    numeros = logica.responder(do_hub, FACE_HUB)

    com_lugar = {
        valor["caminho"]
        for valor in logica.portas.values()
        if valor.get("caminho")
    }
    esperados = {"3-1", "3-1.1", "3-1.2", "3-1.3"}
    faltando = sorted(esperados - com_lugar)
    assert not faltando, (
        "um toque em 'Num hub ou extensão' tinha de dar lugar aos quatro, e "
        f"estes ficaram sem: {', '.join(faltando)}. Quem pende do hub ESTÁ no "
        "hub, e o barramento já diz isso sozinho"
    )
    assert len(numeros) == 4, f"quatro aparelhos, {len(numeros)} número(s)"
    assert len(perguntas) == 1, (
        "quatro aparelhos deviam caber numa pergunta só, porque três pendem do "
        f"hub; virei {len(perguntas)} pergunta(s): "
        + ", ".join(p.caminho for p in perguntas)
    )
    assert len(set(numeros)) == 4, (
        f"dois aparelhos receberam o mesmo número de entrada: {numeros}"
    )
    # E a fase sentada ACABA: não sobrou pergunta para ninguém.
    assert logica.perguntas_sentadas() == ()


# ---------------------------------------------------------------------------
# O resto do contrato da fase sentada
# ---------------------------------------------------------------------------


def test_aparelho_que_ja_tem_lugar_nao_vira_pergunta() -> None:
    """Reabrir cai na primeira entrada SEM lugar, com a conta refeita (R29)."""
    logica = _logica()
    logica.responder(logica.perguntas_sentadas()[0], FACE_HUB)

    segunda = LogicaDaCalibracao(
        MapaDaMesa.model_validate(logica.como_documento()),
        mesa_com_hub_e_tres_aparelhos(),
        gravar=GravadorDeMentira(),
    )
    assert segunda.perguntas_sentadas() == (), (
        "a segunda abertura perguntou de novo o que já estava respondido"
    )


def test_a_face_da_frente_nasce_com_perto_e_as_outras_nao() -> None:
    """``perto`` e ``alto`` são fato dela, e este é o único lugar de onde saem.

    Até 25/08/2026 nenhum dos dois tinha fonte: toda face nascia
    ``perto=False``, e o bônus de +20 do teclado no motor do arranjo nunca
    podia disparar. Juízo montado sobre um fato que nunca chega é juízo
    otimista demais.

    MORDIDA: apagar as duas chaves de ``_por_na_face``. A face nasce sem elas e
    o teste reprova dizendo que a frente do gabinete não é "perto" de ninguém.
    """
    logica = _logica()
    logica.responder(logica.perguntas_sentadas()[0], FACE_ATRAS)
    (face,) = logica.faces
    assert face["nome"] == FACE_ATRAS
    assert face["perto"] is False and face["alto"] is False

    outra = _logica()
    outra.responder(outra.perguntas_sentadas()[0], "Frente do gabinete")
    assert outra.faces[0]["perto"] is True, (
        "a frente do gabinete nasceu sem `perto`, e é o único fato que "
        "nenhuma leitura de /sys tem como saber"
    )


def test_as_quatro_palavras_sao_as_que_ela_carimbou() -> None:
    """Verbatim do carimbo dela de 25/08/2026, às ~03h55, vendo o mockup."""
    from hefesto_dualsense4unix.app.widgets.calibrar_entradas import FACES

    assert FACES == (
        "Frente do gabinete",
        "Atrás do gabinete",
        "Num hub ou extensão",
        "Em cima da mesa",
    )


def test_o_mapa_declarado_passa_no_schema() -> None:
    """O que a cerimônia escreve tem de ser aceito pelo ``MapaDaMesa``.

    Sem esta linha, um número de entrada fora do formato só apareceria no
    ``ValueError`` da gravação — em produção, no meio da cerimônia dela.
    """
    logica = _logica()
    logica.responder(logica.perguntas_sentadas()[0], FACE_HUB)
    mapa = MapaDaMesa.model_validate(logica.como_documento())
    assert len(mapa.portas) == 4
    assert mapa.faces[0].nome == FACE_HUB


# ---------------------------------------------------------------------------
# R1 — todo passo é confirmável sem teclado, sem mouse e sem olhar
# ---------------------------------------------------------------------------


def test_o_payload_do_controle_confirma_sem_teclado_e_sem_mouse() -> None:
    """O DualSense já é entrada da GUI; aqui ele vira gesto.

    Durante a fase em pé a pessoa está atrás do computador, com um cabo na
    mão, sem ver a tela e sem alcançar teclado ou mouse. Se confirmar exigisse
    clicar, a cerimônia seria impossível justamente para quem ela foi
    desenhada.

    MORDIDA: arrancar o ramo do ``cross`` de ``NavegacaoPorControle.passo``
    (que é arrancar o handler do R1). O payload deixa de avançar e o teste
    reprova.
    """
    from hefesto_dualsense4unix.app.widgets.calibrar_entradas import (
        GESTO_ANDAR,
        GESTO_CONFIRMAR,
        NavegacaoPorControle,
    )

    navegacao = NavegacaoPorControle()
    assert navegacao.passo({"buttons": ["cross"]}) == GESTO_CONFIRMAR
    assert navegacao.escolha == 0

    # E o direcional anda pelas quatro respostas, também sem olhar.
    navegacao.passo({"buttons": []})
    assert navegacao.passo({"buttons": ["dpad_down"]}) == GESTO_ANDAR
    assert navegacao.escolha == 1


def test_botao_segurado_nao_repete_o_gesto() -> None:
    """Só a BORDA de subida conta — a 10 Hz, segurar avançaria cinco entradas.

    Quem está atrás do gabinete não veria nenhuma delas passar. É a mesma
    disciplina do anti-ghost-input do daemon.
    """
    from hefesto_dualsense4unix.app.widgets.calibrar_entradas import (
        GESTO_CONFIRMAR,
        NavegacaoPorControle,
    )

    navegacao = NavegacaoPorControle()
    assert navegacao.passo({"buttons": ["cross"]}) == GESTO_CONFIRMAR
    assert navegacao.passo({"buttons": ["cross"]}) == ""
    assert navegacao.passo({"buttons": ["cross"]}) == ""
    navegacao.passo({"buttons": []})
    assert navegacao.passo({"buttons": ["cross"]}) == GESTO_CONFIRMAR


def test_payload_vazio_nao_e_gesto() -> None:
    """Um tique sem botão nenhum não faz nada, e é 99% dos tiques."""
    from hefesto_dualsense4unix.app.widgets.calibrar_entradas import (
        NavegacaoPorControle,
    )

    navegacao = NavegacaoPorControle()
    assert navegacao.passo({}) == ""
    assert navegacao.passo({"buttons": None}) == ""
