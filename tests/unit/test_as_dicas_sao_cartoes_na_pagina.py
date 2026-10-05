"""As dicas da 08 são cartões com UM gesto, e a página os desenha, abre e despacha de verdade.

AS-DICAS-SAO-CARTOES-COM-UM-GESTO-01 (04/10/2026). A caixa «Sugestão de Conexão» e o exame de
cinco frases viraram uma fileira de cartões: no máximo três à vista, «mais N» para o resto, o
porquê atrás do ⓘ e um botão só por cartão.

TUDO É DE MENTIRA: a bancada ``mockup/08-conexoes.html`` num WebKit fora da tela, com o pintor do
piloto; o que a página «manda ao produto» fica numa lista, nada chega a daemon algum.

AS MORDIDAS (feitas na sprint): tirar o corte de ``CARTOES_VISIVEIS`` do ``montar`` reprova a
régua dos três à vista; tirar o ramo ``.cd-info`` do JavaScript da aba reprova a régua do ⓘ;
tirar ``data-gesto`` do botão de mover reprova a régua do gesto.
"""

from __future__ import annotations

import gc
import json
import re
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import dicas_da_conexao as dicas

RAIZ = Path(__file__).resolve().parents[2]
BANCADA = RAIZ / "mockup/08-conexoes.html"
PALAVRAS = re.compile(r"\w+", re.UNICODE)


# ───────────────────────── a tabela e o painel (sem página) ─────────────────────────


def _palavras(texto: str) -> int:
    """A conta da régua dos títulos (o produto não conta palavras: ele corta no limite)."""
    return len(texto.split())


def test_todo_titulo_da_tabela_tem_de_duas_a_cinco_palavras() -> None:
    """O título é a dica: curto para ler de relance, longo o bastante para dizer o quê."""
    todos = {chave: titulo for chave, (_i, titulo, _c) in dicas.DA_ORDEM.items()}
    todos |= {chave: titulo for chave, (_i, titulo, _c) in dicas.DA_CONFERENCIA.items()}
    todos["sem verbete"] = dicas.TITULO_SEM_VERBETE
    assert len(todos) > 8, "a tabela encolheu: a régua ficou cega"
    for chave, titulo in todos.items():
        n = _palavras(titulo)
        assert 2 <= n <= dicas.PALAVRAS_NO_TITULO, f"{chave}: «{titulo}» tem {n} palavras"
    longo = "Um título comprido demais para caber num cartão de dica"
    assert _palavras(dicas.limitar_o_titulo(longo)) <= dicas.PALAVRAS_NO_TITULO


def test_o_porque_e_uma_frase_so_e_nunca_traz_tag() -> None:
    assert dicas.uma_frase("O hub divide o caminho. Isto não entra.") == "O hub divide o caminho."
    assert dicas.uma_frase("Veja <b>isto</b> agora.") == "Veja isto agora."
    comprida = "palavra " * 60
    assert len(dicas.uma_frase(comprida)) <= dicas.LIMITE_DA_FRASE + 1


def _dica(chave: str, nivel: str, calada: bool = False) -> dicas.Dica:
    return dicas.Dica(chave=chave, icone=dicas.ICONE_AJUDA, titulo=chave, nivel=nivel,
                      acao=dicas.Acao(dicas.MAPA, "Ver no mapa", href=dicas.PAGINA_DO_MAPA),
                      calada=calada)


def test_o_painel_poe_o_grave_primeiro_corta_em_tres_e_deixa_a_calada_por_ultimo() -> None:
    entrada = [_dica("n1", dicas.NOTA), _dica("a1", dicas.AJUSTE), _dica("c", dicas.GRAVE, True),
               _dica("g1", dicas.GRAVE), _dica("a2", dicas.AJUSTE), _dica("n2", dicas.NOTA)]
    painel = dicas.montar(entrada, certos=("x", "x", "y", ""))
    assert [d.chave for d in painel.visiveis] == ["g1", "a1", "a2"]
    assert [d.chave for d in painel.demais] == ["n1", "n2", "c"], "a calada vai depois de todas"
    assert painel.certos == ("x", "y")
    assert len(painel.visiveis) == dicas.CARTOES_VISIVEIS == 3


# ───────────────────────── a página (WebKit, bancada) ─────────────────────────


def _html_de_cinco() -> str:
    """Duas ordens, duas conferências e a proposta da central: cinco cartões e o que está certo."""
    from hefesto_dualsense4unix.integrations.exame_da_mesa import (
        ESTADO_ATENCAO,
        ESTADO_CERTO,
        ESTADO_PROBLEMA,
        Item,
    )
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import (
        R3_DONGLE_ATRAS_DE_HUB,
        R4_TECLADO_SO_NO_HUB,
        Identidade,
        Linha,
        Ordem,
    )
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    frase = Linha(texto="O hub divide o caminho. Isto não entra no cartão.", selo="")

    def ordem(chave: str, destino: str = "") -> Any:
        return Ordem(
            chave=chave,
            acao="Mova o adaptador Bluetooth para a Entrada 9",  # (noqa-acento) campo
            o_que_eu_vi=frase, por_que_importa=frase, ganho_esperado=frase,
            alvo=Identidade(caminho="3-1.2"), destino=destino, arranjo="a1")

    def item(chave: str, estado: str, **mais: Any) -> Any:
        return Item(chave=chave, rotulo=chave, estado=estado, porque="o que eu vi", cura=None,
                    ordem=mais.get("ordem"))

    vivos = [
        item("a", ESTADO_ATENCAO, ordem=ordem(R3_DONGLE_ATRAS_DE_HUB, "9")),
        item("b", ESTADO_ATENCAO, ordem=ordem(R4_TECLADO_SO_NO_HUB, "9")),
        item("energia_das_portas", ESTADO_PROBLEMA),
        item("pareamentos", ESTADO_ATENCAO),
        item("suporte_ao_controle", ESTADO_CERTO),
    ]
    cena = {"proposta": {"controle": "ap", "destino": "L2"},
            "lugares": [{"id": "L1", "nome": "Esquerda"}, {"id": "L2", "nome": "Meio"}],
            "aparelhos": [{"id": "ap", "tipo": "controle", "lugar": "L1", "jogador": 2},
                          {"id": "ou", "tipo": "controle", "lugar": "L1", "jogador": 3}]}
    return str(a08_conexoes._html_das_dicas(vivos, cena))


def test_o_nivel_do_cartao_e_dito_no_nome_da_regiao_e_nao_em_texto_escondido() -> None:
    """Cor nunca sozinha: o leitor de tela ouve «Urgente: …», e nenhuma letra se esconde na tela.

    A palavra do nível já foi um ``<span>`` recortado a 1 px dentro do título, e a régua da
    janela estreita (``test_a_janela_estreita_nao_engole_o_desenho``) o lia, com razão, como
    texto engolido na 08. MORDE: devolver o ``aria-labelledby`` ao título reprova a primeira
    asserção; devolver o texto escondido reprova a segunda.
    """
    html = _html_de_cinco()
    secoes = re.findall(r'<section class="cartao-dica[^>]*>', html)
    assert len(secoes) == 5, f"a bancada de cinco achados deu {len(secoes)} cartões"
    palavras = tuple(f"{p}: " for p in dicas.PALAVRA_DO_NIVEL.values())
    for secao in secoes:
        nome = re.search(r'aria-label="([^"]*)"', secao)
        assert nome and nome.group(1).startswith(palavras), (
            f"o cartão não diz o nível no nome da região: {secao}")
    assert "so-leitor" not in html, "voltou o texto escondido dentro do cartão"


_LER = r"""
(function(){
  const raiz = document.querySelector('[data-campo="dicas"]');
  const cartoes = raiz ? [...raiz.querySelectorAll('section.cartao-dica')] : [];
  const mais = raiz && raiz.querySelector('details.mais-dicas');
  return JSON.stringify({
    achou: !!raiz,
    cartoes: cartoes.length,
    aVista: cartoes.filter(c => !c.closest('details:not([open])')).length,
    botoes: cartoes.map(c => c.querySelectorAll('.cd-botao').length),
    mais: mais ? mais.querySelector('summary').textContent.trim() : null,
    maisAberto: mais ? mais.open : null,
    sugestao: !!document.querySelector('.sugestao, [data-campo="ordem"]'),
    info: (cartoes[0] && cartoes[0].querySelector('.cd-info')
           ? cartoes[0].querySelector('.cd-info').getAttribute('aria-expanded') : null),
    porque: (cartoes[0] && cartoes[0].querySelector('.cd-porque')
             ? !cartoes[0].querySelector('.cd-porque').hidden : null),
    certo: (raiz.querySelector('.dicas-certas') || {textContent: ''}).textContent.trim(),
  });
})()
"""


def _clicar(seletor: str) -> str:
    alvo = json.dumps(seletor)
    return (f"(function(){{const b=document.querySelector({alvo});"
            f"if(!b){{return 'sem ' + {alvo};}} b.click(); return 'clicou';}})()")


def _pintar(carga: dict[str, Any]) -> str:
    return f"String(window.__hef.pintar({json.dumps(carga)}))"


def _na_pagina(passos: list[str]) -> tuple[list[Any], list[dict[str, Any]]]:
    try:
        return _na_pagina_sem_recolher(passos)
    finally:
        gc.collect()
        from gi.repository import Gtk

        while Gtk.events_pending():
            Gtk.main_iteration_do(False)


def _na_pagina_sem_recolher(passos: list[str]) -> tuple[list[Any], list[dict[str, Any]]]:
    from tests.conftest import exigir_gi_real

    exigir_gi_real("abre a 08 num WebKit")
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")
    from hefesto_dualsense4unix.interface import hefesto_vivo

    mensagens: list[dict[str, Any]] = []
    respostas: list[str] = []
    ucm = WebKit2.UserContentManager()
    ucm.register_script_message_handler("hefesto")
    ucm.connect("script-message-received::hefesto",
                lambda _u, r: mensagens.append(json.loads(r.get_js_value().to_string())))
    view = WebKit2.WebView.new_with_user_content_manager(ucm)
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(1400, 1000)
    janela.add(view)
    janela.show_all()
    fila = [hefesto_vivo.BOOTSTRAP, *passos]

    def seguinte() -> bool:
        if not fila:
            GLib.timeout_add(400, lambda: (Gtk.main_quit(), False)[1])
            return False
        js = fila.pop(0)

        def respondeu(v: Any, res: Any, _u: Any = None) -> None:
            try:
                respostas.append(v.evaluate_javascript_finish(res).to_string())
            except Exception as erro:
                respostas.append(f"ERRO {erro}")
            GLib.timeout_add(150, seguinte)

        view.evaluate_javascript(js, -1, None, None, None, respondeu, None)
        return False

    def carregou(_v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            seguinte()

    view.connect("load-changed", carregou)
    view.load_uri(BANCADA.as_uri())
    guarda = GLib.timeout_add(30000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert len(respostas) == len(passos) + 1, f"o WebKit parou no meio: {respostas}"
    assert respostas[0] == "ok", f"o BOOTSTRAP do piloto não instalou: {respostas[0]}"
    lidas = [json.loads(r) if r.startswith("{") else r for r in respostas[1:]]
    return lidas, mensagens


def test_cinco_achados_viram_tres_cartoes_a_vista_e_mais_dois() -> None:
    lidas, _ = _na_pagina([_LER, _pintar({"mesa": {"dicas": _html_de_cinco()}}), _LER])
    antes, _, depois = lidas
    assert antes["achou"] and not antes["sugestao"], "a bancada ainda tem a caixa velha"
    assert depois["cartoes"] == 5, depois
    assert depois["aVista"] == dicas.CARTOES_VISIVEIS, f"à vista: {depois['aVista']}"
    assert depois["mais"] == "mais 2" and depois["maisAberto"] is False, depois
    assert depois["botoes"] == [1] * 5, f"cada cartão tem UM botão: {depois['botoes']}"
    assert depois["certo"] == "✓ Suporte ao controle", depois["certo"]


def test_o_mais_n_abre_e_mostra_os_outros_dois() -> None:
    lidas, _ = _na_pagina([
        _pintar({"mesa": {"dicas": _html_de_cinco()}}),
        _clicar(".dicas details.mais-dicas summary"),
        _LER,
    ])
    assert lidas[2]["maisAberto"] is True and lidas[2]["aVista"] == 5, lidas[2]


def test_o_i_abre_e_fecha_o_porque_sem_mexer_no_botao() -> None:
    lidas, mensagens = _na_pagina([
        _pintar({"mesa": {"dicas": _html_de_cinco()}}),
        _LER,
        _clicar(".dicas .cd-info"),
        _LER,
        _clicar(".dicas .cd-info"),
        _LER,
    ])
    fechado, aberto, de_novo = lidas[1], lidas[3], lidas[5]
    assert (fechado["info"], fechado["porque"]) == ("false", False), fechado
    assert (aberto["info"], aberto["porque"]) == ("true", True), "o ⓘ não abriu o porquê"
    assert (de_novo["info"], de_novo["porque"]) == ("false", False), "o ⓘ não fechou"
    assert not [m for m in mensagens if m.get("gesto")], f"o ⓘ mandou gesto: {mensagens}"


def test_o_botao_de_mover_chega_ao_piloto_com_o_gesto_e_os_dados() -> None:
    _, mensagens = _na_pagina([
        _pintar({"mesa": {"dicas": _html_de_cinco()}}),
        _clicar('.dicas .cd-botao[data-gesto="aceitar-sugestao"]'),
    ])
    gestos = [m for m in mensagens if m.get("gesto")]
    assert [g["gesto"] for g in gestos] == [dicas.GESTO_DE_MOVER], mensagens
    assert (gestos[0].get("alvo"), gestos[0].get("destino")) == ("ap", "L2"), gestos


def test_pintar_o_mesmo_html_duas_vezes_nao_fecha_o_porque_aberto() -> None:
    """O alvo ``html`` só repinta quando o HTML muda: o tique não derruba o que ela abriu."""
    html = _html_de_cinco()
    lidas, _ = _na_pagina([
        _pintar({"mesa": {"dicas": html}}),
        _clicar(".dicas .cd-info"),
        _pintar({"mesa": {"dicas": html}}),
        _LER,
    ])
    assert lidas[3]["porque"] is True, "o tique fechou o porquê que ela tinha aberto"
