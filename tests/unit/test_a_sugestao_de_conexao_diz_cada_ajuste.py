"""A SUGESTÃO DE CONEXÃO DIZ CADA AJUSTE — A-GESTAO-DOS-CONTROLES-NO-PRODUTO-01.

A queixa dela, olhando a aba sem controle: *«pq sumiu a parte da caixinha no
canto superior direito?»* — três AJUSTAR à esquerda e a caixa vazia à direita,
porque o produto só desenhava UMA ordem, e só se ela tinha destino. As decisões
são a `D-2609-A-SUGESTAO-DE-CONEXAO-DIZ-O-QUE-MOVER` (título e instrução) e a
`D-2609-A-SUGESTAO-FICA-LARGA-E-COM-TITULO` (a caixa nunca some).

O que cada régua prova, e a mordida que a derruba:

* E1: três AJUSTAR sem destino → três linhas numeradas com o «O que fazer»;
  zero → «Nada a mudar agora.» — MORDIDA: devolva `monta.NADA_A_DIZER` quando
  a ordem não tem destino (o `_html_da_ordem` de antes) → reprova;
* a ordem com destino traz o de→para, e a calada não entra — MORDIDA: tire o
  `_calada(item)` de `_sugestoes_do_exame` → reprova;
* a proposta da central é a linha do controle no adaptador errado, em qualquer
  adaptador e com qualquer número de jogador — MORDIDA: tire a
  `_sugestao_da_central` do `_html_da_ordem` → reprova;
* o título mora FORA do campo que o tique repinta, nas duas páginas.
"""
from __future__ import annotations

import pathlib
import re
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PAGINAS = [RAIZ / "mockup/08-conexoes.html",
           RAIZ / "src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html"]


def _a08() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


def _ordem(chave: str, acao: str, destino: str = "", arranjo: str = "") -> Any:
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import Identidade, Linha, Ordem

    vazio = Linha(texto="", selo="")
    return Ordem(chave=chave, acao=acao,  # (noqa-acento) campo da Ordem
                 o_que_eu_vi=vazio, por_que_importa=vazio, ganho_esperado=vazio,
                 alvo=Identidade(caminho="3-1.2"), destino=destino, arranjo=arranjo)


def _item(chave: str, estado: str, cura: str | None = None, ordem: Any = None,
          porque: str = "o que eu vi") -> Any:
    from hefesto_dualsense4unix.integrations.exame_da_mesa import Item

    return Item(chave=chave, rotulo=chave, estado=estado, porque=porque, cura=cura, ordem=ordem)


def _linhas(html: str) -> list[tuple[str, str]]:
    """``(número, instrução)`` de cada linha da caixa, na ordem."""
    return re.findall(r'<div class="faca"><span class="n">(\d+)</span>([^<]*)</div>', html)


# ---------------------------------------------------------------------------
# E1 — a cena da imagem 1 dela, e o zero
# ---------------------------------------------------------------------------
def test_tres_ajustar_sem_destino_viram_tres_instrucoes() -> None:
    from hefesto_dualsense4unix.integrations.exame_da_mesa import (
        ESTADO_ATENCAO,
        ESTADO_CERTO,
        ESTADO_NAO_SEI,
        ESTADO_PROBLEMA,
    )

    a08 = _a08()
    vivos = [
        _item("dongle", ESTADO_ATENCAO, ordem=_ordem("dongle", "Tire o adaptador do hub.")),
        _item("energia_das_portas", ESTADO_PROBLEMA, cura="Ligue o hub na tomada."),
        _item("teclado", ESTADO_ATENCAO, ordem=_ordem("teclado", "Ligue o teclado direto.")),
        _item("suporte_ao_controle", ESTADO_CERTO),
        _item("pareamentos", ESTADO_NAO_SEI, cura="Isto não é ajuste."),
    ]
    html = a08._html_da_ordem(vivos, None)
    assert _linhas(html) == [("1", "Tire o adaptador do hub."), ("2", "Ligue o hub na tomada."),
                             ("3", "Ligue o teclado direto.")], html
    assert 'class="receita"' not in html, "sem destino não há de→para"
    assert a08.NADA_A_MUDAR not in html


def test_sem_ajuste_a_caixa_diz_que_nao_ha_o_que_mudar() -> None:
    from hefesto_dualsense4unix.integrations.exame_da_mesa import ESTADO_CERTO

    a08 = _a08()
    for vivos in ([], [_item("energia_do_radio", ESTADO_CERTO)]):
        html = a08._html_da_ordem(vivos, None)
        assert html == f'<div class="nada-a-mudar">{a08.NADA_A_MUDAR}</div>', html
    assert a08.NADA_A_MUDAR == "Nada a mudar agora."


def test_a_ordem_com_destino_traz_o_de_para_e_a_calada_nao_entra(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.integrations.exame_da_mesa import ESTADO_ATENCAO

    a08 = _a08()
    com = _ordem("porta", "Mova o adaptador Bluetooth para a Entrada 9", destino="9",
                 arranjo="a1")
    calada = _ordem("calada", "Isto ela calou.", arranjo="a2")
    monkeypatch.setattr(a08, "_DISPENSADAS", {"calada": "a2"})
    html = a08._html_da_ordem([_item("calada", ESTADO_ATENCAO, ordem=calada),
                               _item("porta", ESTADO_ATENCAO, ordem=com)], None)
    assert _linhas(html) == [("1", "Mova o adaptador Bluetooth para a Entrada 9")], html
    assert ('<div class="receita"><span class="caixa">3-1.2</span><span class="seta">→</span>'
            '<span class="caixa alvo">Entrada 9</span></div>') in html


@pytest.mark.parametrize(("caminho", "esperado"), [
    ("9-1.2", "Entrada 15"),      # o caminho que ela declarou na entrada
    ("10-1.1.4", "Entrada 9"),    # o lado USB 3 do buraco, que o aparelho 3.0 usa
    ("9-7", "9-7"),               # fora do mapa: fica o caminho, que é o que se sabe
])
def test_as_duas_pontas_dizem_a_entrada(monkeypatch: pytest.MonkeyPatch, caminho: str,
                                        esperado: str) -> None:
    """26/09/2026, foto dela: a caixa da esquerda mostrava «4-1.1.4» e a da
    direita só «2». MORDIDA: volte a caixa da esquerda ao `alvo.caminho`, ou
    tire o laço dos nós do `mapa_das_portas.porta_de` — reprova."""
    from types import SimpleNamespace

    from hefesto_dualsense4unix.integrations.ordens_da_mesa import Identidade, Linha, Ordem
    from hefesto_dualsense4unix.utils.maquina import MapaDaMesa, PortaDeclarada

    a08 = _a08()
    mapa = MapaDaMesa(portas={
        "9": PortaDeclarada(caminho="9-1.1.4", nos=["9-1.1-port4", "10-1.1-port4"]),
        "15": PortaDeclarada(caminho="9-1.2", nos=["9-1-port2", "10-1-port2"]),
    })
    monkeypatch.setattr(a08, "_declaracao", lambda recarregar=False: SimpleNamespace(mapa=mapa))
    vazio = Linha(texto="", selo="")
    ordem = Ordem(chave="k", acao="Mova isto para a entrada 2",  # (noqa-acento) campo da Ordem
                  o_que_eu_vi=vazio, por_que_importa=vazio, ganho_esperado=vazio,
                  alvo=Identidade(caminho=caminho), destino="2", arranjo="a")
    html = a08._card_da_ordem(ordem, 1)
    assert (f'<span class="caixa">{esperado}</span><span class="seta">→</span>'
            '<span class="caixa alvo">Entrada 2</span>') in html, html


# ---------------------------------------------------------------------------
# A proposta da central — o controle no adaptador errado
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("jogador", [1, 2, 3, 4])
@pytest.mark.parametrize("de, para", [("L1", "L2"), ("L2", "L1"), ("L3", "L1")])
def test_a_proposta_da_central_e_uma_linha_da_caixa(jogador: int, de: str, para: str) -> None:
    from hefesto_dualsense4unix.integrations.exame_da_mesa import ESTADO_ATENCAO

    a08 = _a08()
    lugares = [{"id": "L1", "nome": "Esquerda"}, {"id": "L2", "nome": "Meio"},
               {"id": "L3", "entrada": "Entrada 4"}]
    aparelhos = [{"id": "ap", "tipo": "controle", "lugar": de, "jogador": jogador},
                 {"id": "outro", "tipo": "controle", "lugar": de, "jogador": 9},
                 {"id": "caixa", "tipo": "caixa", "lugar": para}]
    cena = {"proposta": {"controle": "ap", "destino": para}, "lugares": lugares,
            "aparelhos": aparelhos}
    nomes = {"L1": "Esquerda", "L2": "Meio", "L3": "Entrada 4"}
    html = a08._html_da_ordem([_item("x", ESTADO_ATENCAO, cura="Antes.")], cena)
    assert _linhas(html) == [("1", "Antes."),
                             ("2", f"Pareie o P{jogador} no adaptador {nomes[para]}")], html
    assert (f'<span class="caixa">{nomes[de]} <span class="pt">•</span> 2 controles</span>'
            in html), html
    assert (f'<span class="caixa alvo">{nomes[para]} <span class="pt">•</span> 0 controles'
            in html), html


def test_sem_proposta_ou_com_proposta_sem_aparelho_nao_ha_linha() -> None:
    a08 = _a08()
    cena = {"proposta": {"controle": "sumiu", "destino": "L1"},
            "lugares": [{"id": "L1", "nome": "A"}], "aparelhos": []}
    for c in (None, {}, cena):
        assert a08._html_da_ordem([], c) == f'<div class="nada-a-mudar">{a08.NADA_A_MUDAR}</div>'


# ---------------------------------------------------------------------------
# A página — o título fora do campo, e a caixa que nunca some
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("arquivo", PAGINAS, ids=["bancada", "publicada"])
def test_o_titulo_mora_fora_do_campo_que_o_tique_repinta(arquivo: pathlib.Path) -> None:
    a08 = _a08()
    html = arquivo.read_text(encoding="utf-8")
    caixa = re.search(r'<div class="sugestao">\s*<div class="ordem-tit">([^<]+)</div>\s*'
                      r'<div class="col-ordem" data-campo="ordem" data-hef-alvo="html">', html)
    assert caixa and caixa.group(1) == a08.TITULO_DA_ORDEM == "Sugestão de Conexão"
    # as seis regras que escondiam a coluna vazia saíram
    assert ":has(.col-ordem:empty)" not in html
    assert ".duas-colunas:has(.col-exame):has(.col-ordem > .nada:only-child)" not in html
    assert ".sugestao .nada-a-mudar{" in html


def test_o_lugar_que_o_bluez_ainda_nao_nomeou_nao_entra_na_frase() -> None:
    """No primeiro tique o BlueZ ainda não disse o adaptador (`sabido` falso) e o
    lugar não tem nome nem entrada: a frase sairia «Pareie o P2 no adaptador ».

    Achado pela conferência (26/09/2026); o balão da central já esperava o
    `sabido` (`_molde_do_balao`). Destino sem nome: nenhuma linha. Origem sem
    nome: a linha sai, sem o de→para. MORDIDA: tire o filtro do `sabido` de
    `_sugestao_da_central` → reprova.
    """
    a08 = _a08()
    anonimo = {"id": "L2", "nome": "", "entrada": "", "sabido": False}
    esquerda = {"id": "L1", "nome": "Esquerda"}
    para_o_anonimo = {"proposta": {"controle": "ap", "destino": "L2"},
                      "lugares": [esquerda, anonimo],
                      "aparelhos": [{"id": "ap", "tipo": "controle", "lugar": "L1",
                                     "jogador": 2}]}
    assert a08._html_da_ordem([], para_o_anonimo) == (
        f'<div class="nada-a-mudar">{a08.NADA_A_MUDAR}</div>')
    do_anonimo = {**para_o_anonimo, "proposta": {"controle": "ap", "destino": "L1"},
                  "aparelhos": [{"id": "ap", "tipo": "controle", "lugar": "L2", "jogador": 2}]}
    html = a08._html_da_ordem([], do_anonimo)
    assert _linhas(html) == [("1", "Pareie o P2 no adaptador Esquerda")], html
    assert 'class="receita"' not in html, html
