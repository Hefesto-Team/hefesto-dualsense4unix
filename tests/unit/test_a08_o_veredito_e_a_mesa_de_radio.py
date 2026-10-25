#!/usr/bin/env python3
"""O CHECK-UP RESPONDE EM UMA LINHA, e a mesa de rádio é a DO USUÁRIO."""
from __future__ import annotations

import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

BANCADA = RAIZ / "mockup/08-conexoes.html"


def _pacote():  # type: ignore[no-untyped-def]
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


def _item(estado: str, chave: str = "", ordem: object = None):  # type: ignore[no-untyped-def]
    """Um `Item` do exame — o do PRODUTO, nunca um dublê de forma parecida."""
    from hefesto_dualsense4unix.integrations.exame_da_mesa import Item

    return Item(chave=chave or f"c-{estado}", rotulo="", estado=estado,
                porque="", ordem=ordem)


def _ordem(chave: str, arranjo: str):  # type: ignore[no-untyped-def]
    """Uma `Ordem` do catálogo, com o mínimo que a dispensa endereça."""
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import Linha, Ordem

    vazia = Linha(texto="", selo="medido_aqui")
    return Ordem(
        chave=chave,
        acao="Mova o adaptador",
        o_que_eu_vi=vazia,
        por_que_importa=vazia,
        ganho_esperado=vazia,
        arranjo=arranjo,
    )


def test_a_frase_do_veredito_e_a_do_dono() -> None:
    """A frase NÃO nasce no pacote: ela é de `ordens_da_mesa.cabecalho()`."""
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import cabecalho

    p = _pacote()
    saiu = p._veredito_do_exame([_item("certo"), _item("certo")])
    esperado = cabecalho(ordens=[], conferidas=2, sem_resposta=0, dispensadas=0)
    assert saiu["veredito"] == esperado.texto, (
        f"o veredito disse {saiu['veredito']!r} e o dono escreve "
        f"{esperado.texto!r} — alguém digitou a frase no pacote")


def test_a_cor_e_a_do_pior_achado() -> None:
    """Um `problema` entre cinco `certo` acende o vermelho, e só ele."""
    p = _pacote()
    itens = [_item("certo"), _item("problema"), _item("certo")]
    saiu = p._veredito_do_exame(itens)
    assert saiu["veredito-problema"] == "problema", (
        "a linha de veredito não acendeu no pior achado")
    for estado, endereco in p.ENDERECO_DO_VEREDITO.items():
        if estado == "problema":
            continue
        assert saiu[endereco] == "", (
            f"`{endereco}` acendeu junto com o `problema`. Um instante com dois "
            f"acesos deixa o que está QUEBRADO com a cor do que só podia estar "
            f"melhor, que é a confusão que ela mandou desfazer em 02/09.")


def test_o_veredito_nao_diz_nada_a_mudar_com_uma_linha_grave() -> None:
    """A MORDIDA da cicatriz `6fffd547`, e ela é a razão de a função existir."""
    from hefesto_dualsense4unix.app.actions.config.secao_exame import FRASE_DO_SELO
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import cabecalho

    p = _pacote()
    saiu = p._veredito_do_exame([_item("problema"), _item("certo")])
    verde = cabecalho(ordens=[], conferidas=2, sem_resposta=0, dispensadas=0).texto
    assert saiu["veredito"] != verde, (
        f"com uma linha em `problema` o veredito escreveu {verde!r} — a frase "
        f"do cabeçalho, que não conhece `problema`. É a cicatriz 6fffd547 "
        f"voltando: o verde convivendo com o vermelho na mesma seção.")
    assert saiu["veredito"] == FRASE_DO_SELO["problema"], (
        "quando o estado das linhas vence o do cabeçalho, a frase tem de ser a "
        "do estado — e ela também tem dono (`secao_exame.FRASE_DO_SELO`)")


def test_o_que_ela_calou_nao_segura_a_cor() -> None:
    """A ordem DISPENSADA sai da conta — senão o ⊘ é botão morto."""
    p = _pacote()
    ordem = _ordem("vizinhanca", "arranjo-de-hoje")
    itens = [_item("certo"), _item("atencao", chave="o1", ordem=ordem)]  # (dado) noqa-acento

    antes = dict(p._DISPENSADAS)
    try:
        p._DISPENSADAS = {}
        com_ordem = p._veredito_do_exame(itens)
        p._DISPENSADAS = {"vizinhanca": "arranjo-de-hoje"}
        calada = p._veredito_do_exame(itens)
    finally:
        p._DISPENSADAS = antes

    assert com_ordem["veredito-atencao"] == "atencao", (  # (noqa-acento) chave e valor de dado
        "com a ordem aberta o topo tinha de estar em `atencao`")  # (noqa-acento) nome do estado
    assert calada["veredito-atencao"] == "", (
        "a ordem que ela dispensou continuou segurando o topo em laranja — o ⊘ "
        "grava e a tela não muda, que é a definição de botão morto")


def test_a_linha_de_veredito_saiu_da_tela() -> None:
    """A LINHA SAIU — 26/09/2026, pedido com a janela maximizada."""
    html = BANCADA.read_text()
    assert 'class="veredito"' not in html, (
        "a linha de veredito voltou ao desenho — ela saiu a pedido dela")
    saiu = _pacote().pacote(_ctx())
    assert "veredito" not in saiu, (
        "o `pacote()` emite `veredito` para um endereço que a tela não tem")


def _ctx():  # type: ignore[no-untyped-def]
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    p1, p2 = "aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"
    mesa = [
        {"pref": "p1", "uniq": p1, "jogador": 1, "cor": "white",
         "nome": "White", "via": "USB", "transporte": "usb", "mascara": "DualSense"},
        {"pref": "p2", "uniq": p2, "jogador": 2, "cor": "galactic-purple",
         "nome": "Galactic Purple", "via": "BT", "transporte": "bt",
         "mascara": "DualSense"},
    ]
    conectados = [
        {"uniq": p1, "transport": "usb", "connected": True, "battery_pct": 100},
        {"uniq": p2, "transport": "bt", "connected": True, "battery_pct": 64},
    ]
    return Contexto(state={"controllers": conectados}, mesa=mesa,
                    conectados=conectados, estados={})


def test_o_escopo_le_o_valor_da_maquina() -> None:
    """As duas falas são as do `<select>` que saiu — nem uma palavra nova."""
    p = _pacote()
    assert p.escopo_do_botao_do_mic({"mic_button_toggles_system": True}) == (
        p.FALA_DO_BOTAO_DO_MIC[True])
    assert p.escopo_do_botao_do_mic({"mic_button_toggles_system": False}) == (
        p.FALA_DO_BOTAO_DO_MIC[False])
    assert p.escopo_do_botao_do_mic({}) == "", (
        "sem resposta do daemon a tela afirmou um dos dois — o travessão do "
        "piloto é a resposta honesta")
    assert p.pacote(_ctx())["mic-escopo"] == "", (
        "o `_ctx()` não publica a chave, e o pacote inventou um valor")
