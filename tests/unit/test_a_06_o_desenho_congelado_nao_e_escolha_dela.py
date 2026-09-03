#!/usr/bin/env python3
"""O "GUARDAR" DA NAVEGAÇÃO NÃO GRAVA O QUE A TELA NÃO SOUBE MOSTRAR.

O DEFEITO, medido em 02/09/2026 e declarado em
`core/keyboard_mappings.PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ`:

    1. o L3 nasceu ALTERNADOR — decisão 6 dela, *"aperta abre o teclado virtual,
       aperta de novo fecha"* (`keyboard_mappings.DEFAULT_BUTTON_BINDINGS`);
    2. `acoes_de_botao.padrao()` deriva daí o padrão das 21 linhas;
    3. a página que o produto RENDERIZA foi congelada antes do alternador e não
       tem a `<option>` do rótulo novo, então a pintura do `acao-l3` é RECUSADA
       EM SILÊNCIO (`hefesto_vivo.escrever`, alvo `valor`: um `<select>` só
       aceita o texto exato de uma opção que ele oferece). A linha continua
       mostrando "Abrir o teclado na tela";
    4. `a06_navegacao.guardar_definicoes` recolhia o `select.value` das 21
       linhas e gravava a diferença — `{'l3': '__OPEN_OSK__'}` no perfil ATIVO
       dela, **em silêncio**, bastando um clique para mudar qualquer OUTRA
       linha. O L3 parava de alternar naquele perfil.

A DECLARAÇÃO já existia e tornava o defeito visível e datado
(`test_o_padrao_de_fabrica_cabe_na_tela_publicada.py`). **Ela não é a cura**, e
o próprio módulo dizia onde a cura podia morar: aqui, no gesto que grava. Esta
régua cobra a cura.

ELA MEDE CONTRA O HTML PUBLICADO, e não contra um literal: a forma que o
"Guardar" recebe é montada lendo o que cada `<select>` da página que o produto
RENDERIZA abre mostrando. Digitar "Abrir o teclado na tela" aqui faria a régua
sobreviver ao dia da publicação — e ela tem de morrer nesse dia, junto com a
declaração.

A MORDIDA, e ela é uma linha: tire o `del diferentes[botao]` de
`guardar_definicoes` (o laço logo abaixo de `congelado = ...`). O primeiro teste
reprova mostrando `{'l3': '__OPEN_OSK__'}` chegando ao disco.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.core import acoes_de_botao as acoes
from hefesto_dualsense4unix.core.keyboard_mappings import (
    PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ,
)
from hefesto_dualsense4unix.interface import onde

PAGINA = "06-navegacao.html"

#: O controle de mentira e o estado do daemon, na forma dos arquivos irmãos.
#: MAC da faixa sintética da casa — há dois portões de anonimato nesta árvore.
UNIQ = "aa:bb:cc:00:00:01"
FALSO = {"uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
         "battery_pct": 90, "is_primary": True, "inputs": {}, "audio": {},
         "speaker": {}}
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
         "via": "USB", "cor": "cosmic-red", "mascara": "DualSense"}]
ESTADO = {
    "active_profile": "regua",
    "mouse_emulation": {"enabled": True, "speed": 6, "scroll_speed": 1,
                        "bloqueio": "", "despachando": True},
    "keyboard_emulation": {"enabled": True, "osk_disponivel": True},
    "controllers": [FALSO],
}

_SELECT = re.compile(r"<select\b(?P<attrs>[^>]*)>(?P<miolo>.*?)</select>", re.S)
_LINHA = re.compile(r'data-linha="(?P<v>[^"]+)"')
_OPCAO = re.compile(r"<option(?P<attrs>[^>]*)>(?P<texto>[^<]*)</option>")


def _forma_da_pagina_publicada() -> dict[str, str]:
    """O que o "Guardar" recolhe de uma página recém-aberta, por `data-linha`.

    É o `select.value` que o navegador devolveria: a opção `selected`, ou a
    primeira quando não há nenhuma marcada. As opções desta tela não têm
    atributo `value`, então o `value` é o TEXTO da opção.
    """
    fora: dict[str, str] = {}
    html = onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")
    for m in _SELECT.finditer(html):
        alvo = _LINHA.search(m.group("attrs"))
        if not alvo:
            continue
        rotulos: list[str] = []
        marcada: str | None = None
        for o in _OPCAO.finditer(m.group("miolo")):
            texto = o.group("texto").strip()
            rotulos.append(texto)
            if marcada is None and "selected" in o.group("attrs"):
                marcada = texto
        fora[alvo.group("v")] = (
            marcada if marcada is not None else (rotulos[0] if rotulos else ""))
    return {b: r for b, r in fora.items() if b in acoes.BOTOES}


class _PonteMuda:
    """Aceita tudo e ANOTA. É o que separa "não gravou" de "não chamou"."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, dict]] = []

    def chamar(self, metodo: str, **params: object) -> bool:
        self.chamadas.append((metodo, dict(params)))
        return True

    def __getattr__(self, _nome: str):
        return lambda *a, **k: True


class _PerfilDeMentira:
    """O mínimo de um `Profile` que o "Guardar" toca, no idioma do pydantic."""

    def __init__(self, nome, button_actions=None, key_bindings=None):
        self.name = nome
        self.button_actions = button_actions
        self.key_bindings = key_bindings

    def model_copy(self, *, update):
        novo = _PerfilDeMentira(self.name, self.button_actions, self.key_bindings)
        for k, v in update.items():
            setattr(novo, k, v)
        return novo


@pytest.fixture
def aba(monkeypatch):
    """O pacote da 06 com um perfil de mentira, e a trava sempre limpa.

    `_MEXENDO` é estado de MÓDULO — um teste que o deixasse sujo contaminaria o
    seguinte, e o vazamento seria justamente o que estes testes medem.
    """
    import pacotes
    from pacotes import a06_navegacao as mod
    from pacotes import perfil

    guardadas: dict[str, str] = {}
    monkeypatch.setattr(perfil, "ativo",
                        lambda nome: ({"name": "regua",
                                       "button_actions": dict(guardadas)}
                                      if nome else {}))
    mod._MEXENDO.clear()
    monkeypatch.setattr(mod, "_ULTIMA_PINTURA", 0.0, raising=False)
    ctx = pacotes.Contexto(state=ESTADO, mesa=MESA, conectados=[FALSO], estados={})
    yield ctx, mod, guardadas
    mod._MEXENDO.clear()


@pytest.fixture
def disco(monkeypatch):
    """Um disco de mentira: guarda o que o gesto mandou gravar."""
    from hefesto_dualsense4unix.profiles import loader

    gravados: list[_PerfilDeMentira] = []
    estado: dict[str, _PerfilDeMentira] = {}
    monkeypatch.setattr(loader, "load_profile", lambda n: estado[n], raising=False)
    monkeypatch.setattr(loader, "save_profile",
                        lambda prof, **_: gravados.append(prof), raising=False)
    return estado, gravados


def test_o_defeito_existe_na_pagina_publicada() -> None:
    """A PREMISSA, medida antes de qualquer cura: a tela mente em alguma linha.

    Sem esta guarda, os testes abaixo poderiam ficar verdes por não haver
    divergência nenhuma — verde sobre uma página já publicada, que é o
    não-achado convincente desta casa. Se ela reprovar, a `06` foi publicada e
    a declaração de `PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ` tem de sair junto com
    este arquivo.
    """
    forma = _forma_da_pagina_publicada()
    assert PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ, (
        "nada está declarado como fora do vocabulário da tela publicada — se a "
        "`06` foi publicada, apague este arquivo e a declaração junto.")
    for botao, (de_fabrica, da_tela) in PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ.items():
        assert acoes.token_do_rotulo(forma[botao]) == da_tela, (
            f"{botao}: a página publicada abre em {forma[botao]!r}, e a "
            f"declaração diz que ela poria {da_tela!r} no lugar de {de_fabrica!r}.")


def test_o_guardar_nao_grava_o_que_a_tela_nao_soube_mostrar(aba, disco) -> None:
    """O CORAÇÃO: página recém-aberta, ela não tocou em nada, clicou em Guardar.

    A MORDIDA: tire o `del diferentes[botao]` de `guardar_definicoes` — esta
    linha reprova mostrando `{'l3': '__OPEN_OSK__'}` chegando ao disco, que é
    exatamente a medição de 02/09.
    """
    ctx, mod, _ = aba
    estado, gravados = disco
    estado["regua"] = _PerfilDeMentira("regua")

    with pytest.raises(RuntimeError) as caiu:
        mod.guardar_definicoes(
            ctx, {"forma": _forma_da_pagina_publicada()}, _PonteMuda())

    escrito = [p.button_actions for p in gravados]
    assert all(not (a or {}) for a in escrito), (
        f"o Guardar gravou {escrito} sem ela ter escolhido nada — a linha que a "
        "tela não soube mostrar virou escolha dela no disco.")
    for botao in PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ:
        assert mod._nome_do_botao(botao) in str(caiu.value), (
            f"a recusa não nomeia o {botao}: {caiu.value}. Deixar de gravar em "
            "silêncio troca um defeito por outro.")


def test_se_ela_escolhe_a_opcao_com_o_dedo_o_guardar_grava(aba, disco) -> None:
    """A outra metade: escolher "Abrir o teclado na tela" É uma escolha legítima.

    A guarda separa o desenho congelado da vontade dela por `_MEXENDO`, que só
    tem linha trocada pelo gesto `linha-de-botao`. Sem esta metade, a cura viraria
    uma linha que ela nunca mais consegue configurar.

    A MORDIDA: tire o `if f"{PREFIXO_DA_ACAO}{botao}" in _MEXENDO: continue` de
    `_o_desenho_congelado` — esta linha reprova dizendo que o disco não recebeu
    a escolha dela.
    """
    ctx, mod, _ = aba
    estado, gravados = disco
    estado["regua"] = _PerfilDeMentira("regua")
    forma = _forma_da_pagina_publicada()

    for botao in PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ:
        mod.linha_de_botao(
            ctx, {"linha": botao, "valor": forma[botao]}, _PonteMuda())

    mod.guardar_definicoes(ctx, {"forma": forma}, _PonteMuda())

    assert len(gravados) == 1, f"gravou {len(gravados)} vez(es), esperava uma"
    guardado = gravados[0].button_actions or {}
    for botao, (_de_fabrica, da_tela) in PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ.items():
        assert guardado.get(botao) == da_tela, (
            f"ela escolheu {forma[botao]!r} no {botao} com o dedo dela e o "
            f"disco recebeu {guardado.get(botao)!r} — a guarda passou a comer "
            "escolha em vez de desenho.")


def test_a_linha_congelada_nao_leva_o_resto_junto(aba, disco) -> None:
    """Ela mudou OUTRA linha: essa vai ao disco, e a congelada não.

    Era assim que o defeito chegava ao perfil dela — um clique em qualquer outra
    linha bastava. A cura não pode ter virado "o Guardar deixou de guardar".
    """
    ctx, mod, _ = aba
    estado, gravados = disco
    estado["regua"] = _PerfilDeMentira("regua")
    forma = _forma_da_pagina_publicada()
    outro = acoes.rotulo("KEY_F11")
    assert forma["cross"] != outro
    forma["cross"] = outro
    mod.linha_de_botao(ctx, {"linha": "cross", "valor": outro}, _PonteMuda())

    with pytest.raises(RuntimeError, match="não guardei estas linhas"):
        mod.guardar_definicoes(ctx, {"forma": forma}, _PonteMuda())

    assert len(gravados) == 1, f"gravou {len(gravados)} vez(es), esperava uma"
    guardado = gravados[0].button_actions or {}
    assert guardado.get("cross") == "KEY_F11", (
        f"a escolha dela no cross não chegou ao disco: {guardado}")
    for botao in PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ:
        assert botao not in guardado, (
            f"o {botao} pegou carona na gravação de outra linha: {guardado}")


def test_a_guarda_morre_no_dia_da_publicacao(aba, monkeypatch) -> None:
    """Sem declaração, sem guarda — ela não pode virar lápide.

    A tabela que alimenta `_o_desenho_congelado` é a MESMA que
    `test_o_padrao_de_fabrica_cabe_na_tela_publicada` obriga a apagar no dia em
    que ela publicar a `06`. Apagada a linha, esta função devolve `{}` e o
    "Guardar" volta a gravar as 21 sem exceção — sem ninguém precisar lembrar.
    """
    _ctx, mod, _ = aba
    monkeypatch.setattr(mod, "PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ", {})
    diferentes = {b: t for b, t in PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ.items()}
    assert mod._o_desenho_congelado(
        {b: v[1] for b, v in diferentes.items()}) == {}, (
        "a declaração está vazia e a guarda continuou comendo linha — ela "
        "sobreviveria à publicação, que é a definição de lápide.")


# "O homem é a medida de todas as coisas." — Protágoras
