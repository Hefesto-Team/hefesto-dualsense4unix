#!/usr/bin/env python3
"""O editor da entrada grava — `mapa-das-portas.html`, o «Mapa das Conexões».

O-MAPA-DAS-CONEXOES-NO-PRODUTO-01, 26/09/2026. Até aqui um clique nesta página
chegava ao piloto como `[gesto sem dono] mapa-das-portas.html · clique · …`: a
página não tinha pacote, e o que ela declarava numa entrada sumia ao reler.

Os dois pedidos dela que isto atende:

* *«ao clicar em um desses usb mapeados eu pudesse setar que tem tal coisa lá.
  no caso o hub ou afins»* — «O que tem aqui»: Direto, Hub ou Extensor;
* a velocidade da entrada, porque o par SuperSpeed que o firmware da placa
  publica (``peer``) não prova o conector: na mesa em que isto nasceu, as duas
  USB 2.0 pretas de trás têm o par, e a frente que o gabinete chama de 3.0
  está num conector 2.0 da placa — «Velocidade»: USB 3.0 ou 2.0.

<!-- noqa-acento: citação literal dela -->

Os dois vão ao `maquina.json` DELA, em `mapa.portas[N]`, pelo gravador único do
Mapear (`integrations/entrada_a_entrada`), sem IPC: a declaração é dado de
quem usa, no disco dele. O produto lê de lá (`interface/arranjo_desta_maquina`
e `integrations/mapa_das_portas.velocidade_da_entrada`).

POR QUE `a12_` E ISTO NÃO É UMA ABA: é página avulsa, como a `a11` da
calibração. O prefixo é o que o `_carregar_tudo()` e as réguas varrem.

O «EXAMINAR» RELÊ (O-MAPA-DAS-CONEXOES-NO-PRODUTO-02, 26/09/2026). Ele dizia
sempre «Nada Mudou de Lugar»: as duas leituras nasciam iguais e o gesto não
tinha por onde entregar outra. O gesto `reexaminar` relê a máquina no fio do
gesto (nunca no da janela) e devolve o arranjo novo na chave
`arranjo_desta_maquina.CHAVE_DA_ENTREGA`, com a leitura que a página tinha
como «antes»; o piloto o entrega pelo mesmo `window.hefestoArranjo` da
abertura.

O QUE ELE NÃO FAZ: não pinta nada (a página recebe o arranjo inteiro pelo
`hefesto_vivo._entregar_o_arranjo`, e entrar em `PACOTES` faria o despachante
das dez contar onze), e não grava as entradas do hub desenhado (`5.1`…): o
número delas não cabe no disco, e o editor da página nem manda o gesto para
elas. A ponta do extensor grava desde a 02, como entrada-filha.
"""
from __future__ import annotations

from typing import Any

from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee
from hefesto_dualsense4unix.interface import arranjo_desta_maquina

from . import Contexto, gesto

PAGINA = "mapa-das-portas.html"

#: Os gestos do editor da entrada (o que tem, a velocidade, o nome, a troca),
#: o ensinar e o «Examinar». Só sobe.
PISO_DA_ABA = 6

#: O «Direto» do editor: é a ausência de declaração no disco (`liga` nulo).
DIRETO = "direto"


def _a_entrada(o: dict[str, Any]) -> str:
    numero = str(o.get("entrada") or "").strip()
    if not numero:
        raise ValueError("o clique não disse qual entrada")
    return numero


def _gravou(recibo: Any) -> dict[str, Any]:
    """A gravação aconteceu, e a página recebe o arranjo RELIDO do disco.

    D-2609-A-TELA-DO-MAPA-ESPERA-O-DISCO (O-MAPA-QUE-ELA-CORRIGE-01): a página
    não pinta o clique; ela repinta pelo que voltou daqui, com o editor aberto
    na mesma entrada. A recusa levanta antes da releitura, e a página fica
    como estava — com o botão clicado ainda lá para a piscada o achar.
    """
    if not getattr(recibo, "gravou", False):
        raise RuntimeError(f"não gravei no mapa desta máquina ({recibo.motivo})")
    _o_rascunho_da_08_caducou()
    dado = arranjo_desta_maquina.depois_de_gravar()
    return {} if dado is None else {arranjo_desta_maquina.CHAVE_DEPOIS_DE_GRAVAR: dado}


def _o_rascunho_da_08_caducou() -> None:
    """O rascunho do gabinete da aba 08 (`a08_conexoes._LOGICA`) é do mapa de
    antes: sem esquecê-lo, o próximo gesto dele regravaria o mapa velho por cima
    do que o editor acabou de gravar (O-MAPA-QUE-ELA-CORRIGE-01)."""
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    a08_conexoes.esquecer_o_rascunho_do_mapa()


@gesto(PAGINA, "entrada-o-que-tem", grava="declarar_a_ligacao")
def entrada_o_que_tem(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Direto», «Hub» ou «Extensor» na entrada — no `maquina.json` dela."""
    liga = str(o.get("liga") or "")
    if liga != DIRETO and liga not in ee.LIGACOES_DECLARAVEIS:
        raise ValueError(f"o clique não disse o que tem na entrada ({liga!r})")
    return _gravou(ee.declarar_a_ligacao(_a_entrada(o), None if liga == DIRETO else liga))


@gesto(PAGINA, "entrada-velocidade", grava="declarar_a_velocidade")
def entrada_velocidade(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """USB 3.0 ou USB 2.0 na entrada — o que ela diz vence o firmware da placa."""
    try:
        usb = int(str(o.get("usb") or ""))
    except ValueError:
        raise ValueError("o clique não disse a velocidade") from None
    return _gravou(ee.declarar_a_velocidade(_a_entrada(o), usb))


@gesto(PAGINA, "entrada-nome", grava="dar_nome_a_entrada")
def entrada_nome(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O nome que ela dá à entrada — da POSIÇÃO, no `maquina.json` dela.

    O-MAPA-QUE-ELA-CORRIGE-01 (D-2609-O-NOME-E-DA-POSICAO). Pedido dela:
    *«me referi as portas renomear»*. O clique que só põe o cursor no campo
    arma e não grava (o ouvinte do piloto ouve `click` e `change` no mesmo
    campo); o `change` grava; vazio volta a «Entrada N». Mais de 24
    caracteres é recusa, com a frase do dono. <!-- noqa-acento: citação literal dela -->
    """
    if str(o.get("evento") or "") == "click":
        return {"armou": True}
    return _gravou(ee.dar_nome_a_entrada(_a_entrada(o), str(o.get("valor") or "")))


@gesto(PAGINA, "entrada-trocar", grava="trocar_as_entradas")
def entrada_trocar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """«Trocar com…»: o buraco desta entrada e o da escolhida trocam de posição.

    O-MAPA-QUE-ELA-CORRIGE-01 (D-2609-TROCAR-MOVE-O-BURACO). A entrada vem do
    `data-entrada`, e a outra do `valor` do `<select>`. O clique que só abre a
    lista arma; o valor vazio («Trocar com…») não faz nada. As recusas são as
    frases do dono.
    """
    if str(o.get("evento") or "") == "click":
        return {"armou": True}
    outra = str(o.get("valor") or "").strip()
    if not outra:
        return None
    return _gravou(ee.trocar_as_entradas(_a_entrada(o), outra))


@gesto(PAGINA, "entrada-ensinar", grava="ensinar_a_entrada")
def entrada_ensinar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """Ensinar: o aparelho fora do mapa está NESTA entrada — o nó dele passa a ser dela.

    O-MAPA-QUE-ELA-CORRIGE-01 (D-2609-ENSINAR-GRAVA-O-NO). A entrada vem do
    `data-entrada` do plugue, e o aparelho do `data-caminho` (o caminho em que
    a página o lê agora). As recusas são as frases do dono.
    """
    caminho = str(o.get("caminho") or "").strip()
    if not caminho:
        raise ValueError("o clique não disse qual aparelho")
    return _gravou(ee.ensinar_a_entrada(_a_entrada(o), caminho))


@gesto(PAGINA, "reexaminar")
def reexaminar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Examinar»: relê a máquina e devolve o arranjo novo para a página.

    Não grava nada: a leitura anterior mora na memória
    (`arranjo_desta_maquina.reexaminar`). ``None`` é a leitura que não veio (o
    mapa sumiu do disco, o ``/sys`` não respondeu): recusar pisca o botão, e a
    página continua com o que tinha — nunca um gabinete vazio.
    """
    dado = arranjo_desta_maquina.reexaminar()
    if dado is None:
        raise RuntimeError("não li o mapa deste computador de novo")
    return {arranjo_desta_maquina.CHAVE_DA_ENTREGA: dado}


PONTE: set[str] = set()
METODOS: set[str] = set()
