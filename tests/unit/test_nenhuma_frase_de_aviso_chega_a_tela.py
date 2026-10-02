#!/usr/bin/env python3
"""FRASES-E-DICAS-02 — nenhuma frase de aviso chega à tela nas abas 02, 03, 07 e 08."""
from __future__ import annotations

import html
import pathlib
import re
import sys
from html.parser import HTMLParser
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

AVISO_QUE_SAIU = "outro programa está segurando controle"

COR_QUE_SAIU = "não foi lida"

RAZAO_QUE_SAIU = "a barra não obedece"

NARRACAO_QUE_SAIU = "jogo(s) —"

SO_NA_08 = "o prefixo da cura"

UNIQ_1, UNIQ_2 = "aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"
MESA = [
    {"pref": "p1", "uniq": UNIQ_1, "jogador": 1, "cor": "white", "nome": "White",
     "via": "USB", "transporte": "usb", "mascara": "DualSense"},
    {"pref": "p2", "uniq": UNIQ_2, "jogador": 2, "cor": "", "nome": "Galactic Purple",
     "via": "BT", "transporte": "bt", "mascara": "DualSense"},
]


def _sem_etiqueta(marcacao: str) -> str:
    """O texto de um valor `html` do pacote, sem as etiquetas."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", marcacao)).split())


def _ctx() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    conectados = [
        {"uniq": UNIQ_1, "transport": "usb", "connected": True, "battery_pct": 100},
        {"uniq": UNIQ_2, "transport": "bt", "connected": True, "battery_pct": 64},
    ]
    return Contexto(state={"controllers": conectados}, mesa=MESA,
                    conectados=conectados, estados={})


def _cena(destino: str) -> list[Any]:
    """Duas ordens com o ganho não medido e uma conferência com cura."""
    from hefesto_dualsense4unix.integrations.exame_da_mesa import ESTADO_ATENCAO, Item
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import (
        DERIVADO_DA_CONTA,
        MEDIDO_AQUI,
        NAO_MEDI,
        Identidade,
        Linha,
        Ordem,
    )

    def ordem(chave: str) -> Ordem:
        return Ordem(
            chave=chave, acao=f"Leve o adaptador {chave} para uma entrada do computador",
            o_que_eu_vi=Linha(texto="dois rádios no mesmo hub", selo=MEDIDO_AQUI),
            por_que_importa=Linha(texto="o hub divide o caminho", selo=MEDIDO_AQUI),
            ganho_esperado=Linha(texto=NAO_MEDI, selo=DERIVADO_DA_CONTA),
            alvo=Identidade(vid="2357", pid="0604", caminho="3-1.2"),
            arranjo="3-1.2 3-1.4", destino=destino)

    return [
        Item(chave="uma", rotulo="A", estado=ESTADO_ATENCAO, porque="vi isto",
             cura="mova o cabo", ordem=ordem("uma")),
        Item(chave="outra", rotulo="B", estado=ESTADO_ATENCAO, porque="vi aquilo",
             cura="tire o hub", ordem=ordem("outra")),
        Item(chave="conf-1", rotulo="C", estado=ESTADO_ATENCAO,
             porque="a economia de energia está ligada",
             cura="desligue a economia de energia"),
    ]


def test_o_interrogacao_do_exame_continua_dizendo_o_que_fazer() -> None:
    """O que saiu da coluna mora no `?` da linha — e continua lá."""
    from hefesto_dualsense4unix.app.actions.config.secao_exame import PREFIXO_DA_CURA
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as p

    for item in _cena(""):
        dica = _sem_etiqueta(p._dica_da_linha(item))
        assert str(PREFIXO_DA_CURA).strip() in dica and item.cura in dica, dica


def test_a_dica_do_canal_nao_chega_a_tela() -> None:
    """A dica do canal SAIU EM 23/09/2026 — O-ALTO-FALANTE-DIZ-ATIVO-01."""
    from hefesto_dualsense4unix.interface.pacotes import a02_controles as p2

    assert not hasattr(p2, "dica_do_canal")


def _paginas() -> list[pathlib.Path]:
    publicadas = sorted((INTERFACE / "paginas").glob("??-*.html"))  # (noqa-acento) nome de pasta
    bancada = sorted((RAIZ / "mockup").glob("??-*.html"))
    assert len(publicadas) == 10 and len(bancada) == 10, (
        "a régua não achou as dez abas — o caminho mudou, e uma régua que não "
        "acha a tela não mede a tela")
    return publicadas + bancada


def _visivel_sem_a_ajuda(pagina: str) -> str:
    """O que a janela mostra, com o `title` junto e sem o conteúdo dos `?`."""
    from hefesto_dualsense4unix.interface.folha_da_casa import seletores_escondidos
    from hefesto_dualsense4unix.interface.frases_que_ela_baniu import _ler

    return " ".join(_ler(pagina, (*seletores_escondidos(), ".ajuda")).split())


_VAZIOS = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input",
                     "link", "meta", "source", "track", "wbr"})

CLASSES_QUE_SAIRAM_DA_COLUNA = frozenset({"ganho", "proc", "cura"})


class _ClassesDoCampo(HTMLParser):
    """As classes de tudo o que mora DENTRO do elemento de um `data-campo`."""

    def __init__(self, campo: str) -> None:
        super().__init__(convert_charrefs=True)
        self.campo = campo
        self.fundo = 0
        self.achou = False
        self.classes: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        atributos = dict(attrs)
        if self.fundo:
            self.classes += (atributos.get("class") or "").split()
            if tag not in _VAZIOS:
                self.fundo += 1
        elif atributos.get("data-campo") == self.campo and tag not in _VAZIOS:
            self.achou = True
            self.fundo = 1

    def handle_endtag(self, tag: str) -> None:
        if self.fundo and tag not in _VAZIOS:
            self.fundo -= 1


def _campo_da_ordem() -> str:
    """O endereço da coluna, lido do gerador da 08 sem importá-lo."""
    fonte = (INTERFACE / "aba08.py").read_text(encoding="utf-8")
    achado = re.search(r'^CAMPO_DA_ORDEM = "([^"]+)"$', fonte, flags=re.M)
    assert achado, "o gerador da 08 perdeu `CAMPO_DA_ORDEM`: a régua ficaria cega"
    return achado.group(1)


@pytest.mark.parametrize("arquivo", [p for p in _paginas() if p.name.startswith("08-")],
                         ids=lambda p: f"{p.parent.name}/{p.name}")
def test_a_coluna_da_ordem_cravada_na_08_nao_traz_imperativo_nem_ganho(
        arquivo: pathlib.Path) -> None:
    """A §D da sprint vale também para o que a página crava antes do primeiro tique."""
    leitor = _ClassesDoCampo(_campo_da_ordem())
    leitor.feed(arquivo.read_text(encoding="utf-8"))
    assert leitor.achou and leitor.classes, (
        f"{arquivo.parent.name}/{arquivo.name}: a régua não achou a coluna da ordem")
    voltaram = sorted(CLASSES_QUE_SAIRAM_DA_COLUNA & set(leitor.classes))
    assert not voltaram, (
        f"{arquivo.parent.name}/{arquivo.name}: a coluna da ordem crava {voltaram}")
