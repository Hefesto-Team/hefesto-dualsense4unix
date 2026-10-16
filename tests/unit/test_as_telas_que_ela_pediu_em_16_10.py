"""As telas que o usuário pediu em 16/10, lidas no desenho que o gerador escreve
(AS-TELAS-QUE-ELA-PEDIU-EM-16-10-01: N1 a N9 da Navegação e S1 a S4 do Sistema).

Só o gerador: o HTML de `mockup/` e o pacote da aba, sem janela. A geometria (sem rolagem em
1212x809 e em 1920x1080) mora em `test_as_telas_de_16_10_no_webkit.py`, no motor que o produto usa.

MORDIDAS (feitas à mão, 16/10/2026): devolver o «Toque» a `COLUNA_2` de `aba06.py` reprova
`test_o_toque_mora_em_opcoes_e_as_duas_colunas_sao_pares`; devolver `"botao": "cross"` ao
`_estado` do pacote do mapa reprova `test_o_mapa_nasce_sem_botao_aceso`; tirar o `TITULO` da
âncora do mapa gerado reprova `test_o_titulo_do_mapa_diz_qual_das_duas_telas_e`.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.core import acoes_do_gesto as ag

MOCKUP = RAIZ / "mockup"


def _pagina(nome: str) -> str:
    return (MOCKUP / nome).read_text(encoding="utf-8")


def _opcoes(doc: str) -> str:
    return doc.split('<section class="nav2-opcoes">')[1].split("</section>")[0]


# --------------------------------------------------------------------- Navegação


def test_o_titulo_do_mapa_diz_qual_das_duas_telas_e() -> None:
    """N1: o mesmo desenho, com o título da âncora por que se entrou."""
    doc = _pagina("mapa-do-controle.html")
    titulos = re.search(r"const TITULO = (\{[^}]*\})", doc)
    assert titulos, "o mapa perdeu o título que segue a âncora"
    assert "'#trocar': 'Trocar os botões'" in titulos.group(1)
    assert "'#point-and-click': 'Point and click'" in titulos.group(1)
    nav = _pagina("06-navegacao.html")
    for ancora in ("#trocar", "#point-and-click"):
        assert f'mapa-do-controle.html{ancora}"' in nav, f"a 06 não abre o mapa por {ancora}"


def test_o_mapa_nasce_sem_botao_aceso() -> None:
    """N2: ninguém apertou nada, nenhuma linha acende (a Cruz nascia escolhida)."""
    assert not re.search(r'class="b2[^"]*"[^>]*data-estado="[^"]*\bon\b',
                         _pagina("mapa-do-controle.html"))
    from pacotes import a13_mapa_do_controle as mapa

    mapa._EDITANDO.clear()
    assert mapa._estado()["botao"] is None


def test_o_toque_mora_em_opcoes_e_as_duas_colunas_sao_pares() -> None:
    """N3 e N7: o «Toque» e o Touchpad no quadrante da direita; as duas colunas iguais."""
    import aba06

    doc = _pagina("06-navegacao.html")
    assert len(aba06.COLUNA_1) == len(aba06.COLUNA_2)
    assert "touchpad_toque" not in aba06.LINHAS
    esquerda = doc.split('<section class="nav2-opcoes">')[0]
    assert 'data-linha="touchpad_toque"' not in esquerda
    assert 'data-linha="touchpad_toque"' in _opcoes(doc)
    assert re.search(r'class="op2-rot"[^>]*>Touchpad<', _opcoes(doc))


def test_o_quadrante_da_direita_se_chama_opcoes_e_tem_os_tres_de_permitir() -> None:
    """N4, N5 e N6."""
    doc = _pagina("06-navegacao.html")
    op = _opcoes(doc)
    assert op.lstrip().startswith('<div class="sec2">Opções</div>')
    botoes = re.findall(r'<button[^>]*value="([a-z-]+)"[^>]*data-gesto="permitir-navegacao"', op)
    assert botoes == ["interna", "steam", "uso-geral"], botoes
    for velho in ("Quem navega", "Tipo de navegação", "Navega com", "navegacao-tipo"):
        assert velho not in doc, f"«{velho}» voltou à 06"
    assert "Perfil Jogo - Navegação" in op
    moldes = re.findall(r"<option[^>]*>([^<]+)</option>",
                        _pagina("mapa-do-controle.html").split('id="perfil"')[1].split("</select>")[0])
    for nome in ("Point and click", "Visual novel", "Adulto"):
        assert nome in moldes, f"o molde «{nome}» saiu da lista do perfil"


def test_os_gestos_do_ps_se_acrescentam_e_tiram_sem_frase_e_sem_o_ps_sozinho() -> None:
    """N8: «+ Gesto» com um botão por peça (o proibido sem endereço), o botão de tirar em toda
    linha, e o PS sozinho mora em «Os botões» como lista única."""
    doc = _pagina("06-navegacao.html")
    op = _opcoes(doc)
    assert '<summary class="btn roxo mais-gesto"' in op
    escolha = op.split('<details class="novo-gesto">')[1].split("</details>")[0]
    pecas = re.findall(r'<button[^>]*data-gesto="novo-gesto" data-b="([a-z0-9_]+)"', escolha)
    candidatas = {g.botoes[1] for g in ag.TODOS_OS_GESTOS.values() if len(g.botoes) == 2}
    assert set(pecas) == candidatas | set(ag.BOTOES_PROIBIDOS), pecas
    for b in ag.BOTOES_PROIBIDOS:
        botao = re.search(rf'<button[^>]*data-b="{b}"[^>]*>', escolha)
        assert botao and 'data-livre="nao"' in botao.group(0) and "data-campo" not in botao.group(0)
    assert escolha.count("<svg") >= len(pecas), "um botão da escolha ficou sem o glifo"
    assert not re.search(r"proibid|em uso|já usad", escolha, flags=re.I), "frase de aviso na tela"
    linhas = re.findall(r'data-gesto="acao-do-gesto" data-linha="([a-z0-9_]+)"', op)
    assert "ps" not in linhas and set(linhas) == set(ag.TODOS_OS_GESTOS) - {"ps"}
    tiram = re.findall(r'data-gesto="remover-gesto" data-linha="([a-z0-9_]+)"', op)
    assert sorted(tiram) == sorted(linhas)
    ps = re.search(r'<select[^>]*data-linha="ps"[^>]*>(.*?)</select>', doc, flags=re.S)
    assert ps and "Abrir a Steam" in ps.group(1) and "Seta para cima" in ps.group(1)


def test_o_gesto_permitir_navegacao_grava_o_que_cada_botao_diz() -> None:
    """N5 pelo gesto: Steam liga o Big Picture; Interna e Uso geral o desligam e escolhem o tipo."""
    import pacotes
    from pacotes import a06_navegacao as a06

    pacotes._carregar_tudo()
    pedidos: list[tuple[str, dict[str, object]]] = []

    class _Ponte:
        def resultado(self, metodo: str, **params: object) -> dict[str, object]:
            pedidos.append((metodo, params))
            return {"status": "ok"}

        def __getattr__(self, nome: str) -> object:
            raise AttributeError(nome)

    fn = pacotes.gesto_da_pagina("06-navegacao.html", a06.PERMITIR)
    assert fn is not None
    esperado = {
        "steam": [("navegacao.big_picture.set", True)],
        "interna": [("navegacao.big_picture.set", False), ("navegacao.interna.set", "interna")],
        "uso-geral": [("navegacao.big_picture.set", False),
                      ("navegacao.interna.set", "computador")],
    }
    for valor, quer in esperado.items():
        pedidos.clear()
        try:
            fn(pacotes.Contexto(state={}), {"valor": valor}, _Ponte())
        except (AttributeError, TypeError) as erro:
            pytest.fail(f"o gesto pediu à ponte o que ela não tem: {erro}")
        vistos = [(m, p.get("ligado", p.get("tipo"))) for m, p in pedidos]
        assert vistos == quer, (valor, pedidos)
        assert all("ligada" not in p for _m, p in pedidos), "o Permitir mexeu no liga/desliga"
