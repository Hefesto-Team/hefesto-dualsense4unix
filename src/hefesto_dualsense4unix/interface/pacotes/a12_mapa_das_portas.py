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
  está num conector 2.0 da placa — «Velocidade»: USB 3.0 ou 2.0 (desde 04/10/2026
  só na entrada VAZIA: com aparelho nela, a máquina mede e a medida vence).

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

PISO_DA_ABA = 6

DIRETO = "direto"


def _a_entrada(o: dict[str, Any]) -> str:
    numero = str(o.get("entrada") or "").strip()
    if not numero:
        raise ValueError("o clique não disse qual entrada")
    return numero


def _as_faixas(ctx: Contexto | None) -> Any:
    """A fonte das faixas do painel (a conta da aba 08), ou `None` sem contexto."""
    if ctx is None:
        return None
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return lambda: a08_conexoes.faixas_para_o_mapa(ctx)


def _gravou(recibo: Any, ctx: Contexto | None = None) -> dict[str, Any]:
    """A gravação aconteceu, e a página recebe o arranjo RELIDO do disco."""
    if not getattr(recibo, "gravou", False):
        raise RuntimeError(f"não gravei no mapa desta máquina ({recibo.motivo})")
    _o_rascunho_da_08_caducou()
    dado = arranjo_desta_maquina.depois_de_gravar(faixas=_as_faixas(ctx))
    return {} if dado is None else {arranjo_desta_maquina.CHAVE_DEPOIS_DE_GRAVAR: dado}


def _o_rascunho_da_08_caducou() -> None:
    """O rascunho do gabinete da aba 08 (`a08_conexoes._LOGICA`) é do mapa de"""
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    a08_conexoes.esquecer_o_rascunho_do_mapa()


EXTENSOR_DE_ANTES = "extensor"


@gesto(PAGINA, "entrada-o-que-tem", grava="declarar_a_ligacao")
def entrada_o_que_tem(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Direto» ou «Hub» na entrada — no `maquina.json` dela.

    O «Extensor» deixou de ser uma resposta daqui (04/10/2026): é a chave da porta, o gesto
    ``entrada-extensor``. A página publicada até o próximo ``--publicar`` ainda o manda por
    este gesto, e ele é atendido como a chave.
    """
    liga = str(o.get("liga") or "")
    if liga == EXTENSOR_DE_ANTES:
        return _gravou(ee.declarar_o_extensor(_a_entrada(o), True), ctx)
    if liga != DIRETO and liga not in ee.LIGACOES_DECLARAVEIS:
        raise ValueError(f"o clique não disse o que tem na entrada ({liga!r})")
    return _gravou(ee.declarar_a_ligacao(_a_entrada(o), None if liga == DIRETO else liga), ctx)


@gesto(PAGINA, "entrada-extensor", grava="declarar_o_extensor")
def entrada_extensor(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """A chave «Extensor» da entrada: há um cabo de extensão entre o buraco e o aparelho."""
    ligado = str(o.get("ligado") or "").lower()
    if ligado not in ("true", "false"):
        raise ValueError("o clique não disse se o extensor liga ou desliga")
    return _gravou(ee.declarar_o_extensor(_a_entrada(o), ligado == "true"), ctx)


@gesto(PAGINA, "entrada-lugar", grava="declarar_o_lugar_da_entrada")
def entrada_lugar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """O «Lugar» da entrada: a face do gabinete em que ela está (a do Mapear, no mesmo dono)."""
    if str(o.get("evento") or "") == "click":
        return {"armou": True}
    face = str(o.get("valor") or "").strip()
    if not face:
        return None
    return _gravou(ee.declarar_o_lugar_da_entrada(_a_entrada(o), face), ctx)


def _o_modelo(o: dict[str, Any]) -> str:
    modelo = str(o.get("modelo") or "").strip()
    if not modelo:
        raise ValueError("o clique não disse qual aparelho")
    return modelo


@gesto(PAGINA, "aparelho-tipo", grava="declarar_o_aparelho")
def aparelho_tipo(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O tipo que ela dá ao aparelho (o que a máquina não mede) — pelo ``vid:pid`` dele."""
    return _gravou(ee.declarar_o_aparelho(_o_modelo(o), tipo=str(o.get("tipodito") or "")), ctx)


@gesto(PAGINA, "aparelho-nome", grava="declarar_o_aparelho")
def aparelho_nome(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O nome que ela dá ao aparelho — pelo ``vid:pid`` dele; vazio apaga."""
    if str(o.get("evento") or "") == "click":
        return {"armou": True}
    return _gravou(ee.declarar_o_aparelho(_o_modelo(o), apelido=str(o.get("valor") or "")), ctx)


@gesto(PAGINA, "voltar-ao-automatico", grava="voltar_ao_automatico")
def voltar_ao_automatico(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Voltar ao automático»: tira o que ela disse do aparelho (tipo, nome) e da entrada."""
    modelo = str(o.get("modelo") or "").strip() or None
    entrada = str(o.get("entrada") or "").strip() or None
    return _gravou(ee.voltar_ao_automatico(numero=entrada, modelo=modelo), ctx)


@gesto(PAGINA, "entrada-velocidade", grava="declarar_a_velocidade")
def entrada_velocidade(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """USB 3.0 ou USB 2.0 na entrada — o que ela diz vence o firmware da placa."""
    try:
        usb = int(str(o.get("usb") or ""))
    except ValueError:
        raise ValueError("o clique não disse a velocidade") from None
    return _gravou(ee.declarar_a_velocidade(_a_entrada(o), usb), ctx)


@gesto(PAGINA, "entrada-nome", grava="dar_nome_a_entrada")
def entrada_nome(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O nome que ela dá à entrada — da POSIÇÃO, no `maquina.json` dela."""
    if str(o.get("evento") or "") == "click":
        return {"armou": True}
    return _gravou(ee.dar_nome_a_entrada(_a_entrada(o), str(o.get("valor") or "")), ctx)


@gesto(PAGINA, "entrada-trocar", grava="trocar_as_entradas")
def entrada_trocar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """«Trocar com…»: o buraco desta entrada e o da escolhida trocam de posição."""
    if str(o.get("evento") or "") == "click":
        return {"armou": True}
    outra = str(o.get("valor") or "").strip()
    if not outra:
        return None
    return _gravou(ee.trocar_as_entradas(_a_entrada(o), outra), ctx)


@gesto(PAGINA, "entrada-ensinar", grava="ensinar_a_entrada")
def entrada_ensinar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """Ensinar: o aparelho fora do mapa está NESTA entrada — o nó dele passa a ser dela."""
    caminho = str(o.get("caminho") or "").strip()
    if not caminho:
        raise ValueError("o clique não disse qual aparelho")
    return _gravou(ee.ensinar_a_entrada(_a_entrada(o), caminho), ctx)


@gesto(PAGINA, "reexaminar")
def reexaminar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Examinar»: relê a máquina e devolve o arranjo novo para a página."""
    dado = arranjo_desta_maquina.reexaminar(faixas=_as_faixas(ctx))
    if dado is None:
        raise RuntimeError("não li o mapa deste computador de novo")
    return {arranjo_desta_maquina.CHAVE_DA_ENTREGA: dado}


PONTE: set[str] = set()
METODOS: set[str] = set()
