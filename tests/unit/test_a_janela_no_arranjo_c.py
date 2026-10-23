"""A janela da extensão no arranjo C, no produto, e os aparelhos das extensões na aba Conexões.

A nona capacidade genérica da porta (as oito primeiras moram em
``test_as_capacidades_genericas_da_porta``): toda extensão que declara ``agora`` ganha a coluna
«Agora» à esquerda e os grupos em abas à direita, com o «Parar tudo» no topo; o ``por_botao`` e o
``endereco`` são linhas da janela; a aba 08 lista as conexões e os aparelhos de cada extensão
ligada, «via <nome>».

MORDIDAS (22/10/2026, executadas sobre a cura e devolvidas):

- o ``{**_valor_na_janela(...), botao: valor}`` trocado por ``{botao: valor}`` no
  ``guardar_opcao_da_modificacao`` reprova
  ``test_o_toque_mudado_num_botao_guarda_os_outros`` (o validar devolve o padrão nos outros);
- o ``_MEXIDA.aba = opcao.grupo`` arrancado reprova
  ``test_a_janela_redesenhada_abre_a_aba_da_opcao_mudada`` (a janela volta à primeira aba);
- o ``"via "`` tirado do ``html_do_agora_das_extensoes`` reprova
  ``test_a_conexoes_diz_cada_peca_via_a_extensao``;
- o filtro ``entrada.ligada`` arrancado do ``_ler_o_agora_das_extensoes`` reprova
  ``test_a_conexoes_so_pergunta_a_extensao_ligada_que_publica_o_estado``;
- ``flex:none`` de volta à ``.onda`` e ``width:120px`` à lista do ``.tql`` reprovam
  ``test_os_toques_cabem_sem_corte_nos_dois_arranjos[cartoes-*]``.
"""

from __future__ import annotations

import re
import sys
from typing import Any

import pytest

from hefesto_dualsense4unix.mods.manifesto import BOTOES_DO_POR_BOTAO as BOTOES
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    _a07,
    _fonte,
    _instalar,
    ctx,
    lar,
    navegador,
)
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import INTERFACE, MOCKUP
from tests.unit.test_a_coluna_agora_e_o_parar_tudo_vem_do_servico import _Ponte

ESTADO = "publicar:acessorios.estado"
FORMAS = {"Nada": [], "Toque": [[1.0, 0.2]], "Duplo": [[1.0, 0.1], [0.0, 0.1], [1.0, 0.1]]}
OPCOES = [
    {"id": "toques", "rotulo": "Toques", "tipo": "por_botao", "grupo": "Toques",
     "formas": FORMAS, "botoes": ["cross", "circle", "r1"],
     "padrao": {"cross": "Toque"}},  # (noqa-acento): chave do manifesto
    {"id": "onde", "rotulo": "Endereço", "tipo": "endereco", "grupo": "Ligação"},
    {"id": "avisar", "rotulo": "Avisar", "tipo": "ligado", "grupo": "Geral"},
]
VIVO = {"ligado": True,
        "conexoes": [  # (noqa-acento): a chave do estado
            {"id": "cabo", "tipo": "Adaptador", "transporte": "usb", "estado": "ligado",
             "motivo": None}],
        "aparelhos": [{"nome": "Motor", "tipo": "vibrador", "estado": "ligado",
                       "bateria": 80, "forca": 0.5}]}


@pytest.fixture
def janela(lar, ctx, tmp_path, monkeypatch):  # noqa: F811
    """A janela da extensão ``toque``, com as opções do arranjo C e o ``agora`` pedido."""
    a07 = _a07()
    monkeypatch.setattr(a07, "_AGORA", a07._Agora())

    def abrir(**extra: Any) -> dict[str, Any]:
        _instalar(a07, ctx, _fonte(tmp_path, permissoes=(ESTADO,), opcoes=OPCOES, extra=extra))
        return a07.configurar_modificacao(ctx, {"v": "toque"}, _Ponte(VIVO))

    return a07, abrir


def _mudar(a07, ctx, v: str, valor: Any) -> dict[str, Any]:  # noqa: F811
    return a07.guardar_opcao_da_modificacao(
        ctx, {"v": v, "valor": valor, "evento": "change"}, _Ponte(VIVO))


def _aberta(html: str) -> str:
    """O rótulo da aba marcada."""
    achado = re.search(r'id="mj-aba-\d+" checked><label[^>]*>([^<]*)</label>', html)
    assert achado, "a janela não tem aba marcada"
    return achado.group(1)


def test_com_agora_a_janela_e_o_arranjo_c_com_os_grupos_em_abas(janela) -> None:
    _, abrir = janela
    agora = ["conexoes", "aparelhos"]  # (noqa-acento): chave
    html = abrir(agora=agora, parar_tudo=True)["blocos"]["#mod-janela"]
    assert 'class="ja-agora" id="mod-agora"' in html and "ja-opcoes" in html
    assert 'class="ja-parar"' in html and "Para</span>Todos" not in html
    assert re.findall(r'<label for="mj-aba-\d+">([^<]*)</label>', html) == [
        "Toques", "Ligação", "Geral"]
    assert _aberta(html) == "Toques", "a janela nova abre na primeira aba"


def test_sem_agora_a_janela_segue_nos_cartoes(janela) -> None:
    _, abrir = janela
    html = abrir()["blocos"]["#mod-janela"]
    assert "ja-corpo" not in html and "mj-abas" not in html and "tn-corpo" in html


def test_o_por_botao_mostra_cada_botao_com_as_formas_declaradas(janela) -> None:
    _, abrir = janela
    html = abrir(agora=["aparelhos"])["blocos"]["#mod-janela"]
    assert html.count('class="tql"') == 3, "uma linha por botão da janela"
    assert 'href="#bt-cross"' in html and 'data-v="toque:toques:circle"' in html
    linha = html[html.index('data-v="toque:toques:cross"'):]
    linha = linha[:linha.index("</select>")]
    assert re.findall(r"<option[^>]*>([^<]*)", linha) == ["Nada", "Toque", "Duplo"]
    assert "<option selected>Toque" in linha, "o padrão do manifesto"


def test_o_toque_mudado_num_botao_guarda_os_outros(janela, ctx) -> None:  # noqa: F811
    a07, abrir = janela
    abrir(agora=["aparelhos"])
    _mudar(a07, ctx, "toque:toques:circle", "Duplo")
    assert a07._MEXIDA.rascunho["toques"] == {"cross": "Toque", "circle": "Duplo", "r1": "Nada"}
    _mudar(a07, ctx, "toque:toques:r1", "Toque")
    assert a07._MEXIDA.rascunho["toques"] == {"cross": "Toque", "circle": "Duplo", "r1": "Toque"}
    assert a07.guardar_opcao_da_modificacao(
        ctx, {"v": "toque:toques:r1", "valor": "Duplo", "evento": "click"}, _Ponte(VIVO)) is None
    with pytest.raises(RuntimeError, match="Qual botão"):
        _mudar(a07, ctx, "toque:toques:ps", "Toque")
    with pytest.raises(RuntimeError):
        _mudar(a07, ctx, "toque:toques:cross", "Longo")


def test_a_janela_redesenhada_abre_a_aba_da_opcao_mudada(janela, ctx) -> None:  # noqa: F811
    a07, abrir = janela
    abrir(agora=["aparelhos"])
    html = _mudar(a07, ctx, "toque:onde", "192.168.0.10:8080")["blocos"]["#mod-janela"]
    assert _aberta(html) == "Ligação"
    assert 'value="192.168.0.10:8080"' in html
    reaberta = a07.configurar_modificacao(ctx, {"v": "toque"}, _Ponte(VIVO))
    assert _aberta(reaberta["blocos"]["#mod-janela"]) == "Toques", "reabrir volta à primeira"


def test_o_endereco_torto_e_recusado_dizendo(janela, ctx) -> None:  # noqa: F811
    a07, abrir = janela
    abrir(agora=["aparelhos"])
    with pytest.raises(RuntimeError, match="IP e a porta"):
        _mudar(a07, ctx, "toque:onde", "sem-porta")
    assert "onde" not in a07._MEXIDA.rascunho


# -- a aba Conexões -----------------------------------------------------------------------


def _a08():
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


def test_a_conexoes_diz_cada_peca_via_a_extensao() -> None:
    a08 = _a08()
    falhou = {"id": "fone", "tipo": "Telefone", "transporte": "rede", "estado": "falhou",
              "motivo": "Sem resposta"}
    desligada = {"id": "radio", "tipo": "Bluetooth", "transporte": "bluetooth",
                 "estado": "desligado", "motivo": None}
    vivo = {**VIVO, "conexoes": [*VIVO["conexoes"], falhou, desligada]}  # (noqa-acento): chave
    html = a08.html_do_agora_das_extensoes([
        ("Minha <extensão>", vivo)])
    linhas = re.findall(r'<div class="ext-linha ext-acessorio"[^>]*>.*?</div>', html)
    assert len(linhas) == 3, "uma linha por conexão viva e por aparelho"
    assert "Bluetooth" not in html, "a conexão que ninguém escolheu fica só na janela"
    assert all("via Minha &lt;extensão&gt;" in x for x in linhas), "sem o «via», ou sem escapar"
    assert 'data-dica="Sem resposta"' in html, "o motivo fica na dica, nunca no texto"
    assert "c-laranja" in html and "vermelh" not in html and "c-red" not in html
    assert "80%" in linhas[-1], "a pilha do aparelho"
    assert a08.html_do_agora_das_extensoes([]) == ""
    assert a08.html_do_agora_das_extensoes([("Vazia", {"ligado": True})]) == ""


def test_a_conexoes_so_pergunta_a_extensao_ligada_que_publica_o_estado(
        lar, ctx, tmp_path, monkeypatch) -> None:  # noqa: F811
    from hefesto_dualsense4unix.app import ipc_bridge
    from hefesto_dualsense4unix.integrations import bluez_dbus

    a07, a08 = _a07(), _a08()
    _instalar(a07, ctx, _fonte(tmp_path, "toque", nome="Toque", permissoes=(ESTADO,)))
    a07.ligar_modificacao(ctx, {"v": "toque"}, _Ponte())
    a07.ligar_modificacao(ctx, {"v": "toque"}, _Ponte())
    _instalar(a07, ctx, _fonte(tmp_path, "parada", nome="Parada", permissoes=(ESTADO,)))
    _instalar(a07, ctx, _fonte(tmp_path, "tema", nome="Tema"))
    a07.ligar_modificacao(ctx, {"v": "tema"}, _Ponte())
    perguntas: list[str] = []

    def corpo(pedido: str, params: dict[str, Any], timeout: float = 0) -> Any:
        perguntas.append(params["mod"])
        return {**VIVO, "ligado": params["mod"] == "toque"}

    monkeypatch.setattr(ipc_bridge, "_corpo_do_daemon", corpo)
    monkeypatch.setattr(bluez_dbus, "a_suite_esta_rodando", lambda: False)
    assert [nome for nome, _ in a08._ler_o_agora_das_extensoes()] == ["Toque"]
    assert perguntas == ["toque"], "perguntou a quem está desligada ou não publica o estado"


def test_a_extensao_parada_pelo_parar_tudo_segue_mostrando_o_que_esta_ligado(
        lar, ctx, tmp_path, monkeypatch) -> None:  # noqa: F811
    """Depois do «Parar tudo» a extensão devolve ``ligado: false`` com o adaptador ainda ligado e a
    força a zero: a coluna diz «Parada» e mostra os dois, e a aba Conexões não os apaga. A
    conexão que cai devolve o estado vazio, e aí não sobra item nenhum."""
    from hefesto_dualsense4unix.app import ipc_bridge
    from hefesto_dualsense4unix.integrations import bluez_dbus
    from hefesto_dualsense4unix.interface import desenho_da_experimental as exp
    from hefesto_dualsense4unix.mods.porta import estado_vazio_dos_acessorios

    parada = {**VIVO, "ligado": False, "nivel": 3,
              "aparelhos": [{**VIVO["aparelhos"][0], "forca": 0.0}]}
    coluna = exp.agora_html(["conexoes", "aparelhos", "nivel"], parada)  # (noqa-acento): chave
    assert "Parada" in coluna and "Adaptador" in coluna and "Motor" in coluna
    assert '<div class="ap vazio">' not in coluna and "<b>—</b>" in coluna, "o nível segue vazio"
    pedacos = ["conexoes", "aparelhos"]  # (noqa-acento): chave
    vazia = exp.agora_html(pedacos, estado_vazio_dos_acessorios("x"))
    assert "Adaptador" not in vazia and '<div class="ap vazio">' in vazia

    a07, a08 = _a07(), _a08()
    _instalar(a07, ctx, _fonte(tmp_path, "toque", nome="Toque", permissoes=(ESTADO,)))
    a07.ligar_modificacao(ctx, {"v": "toque"}, _Ponte())
    a07.ligar_modificacao(ctx, {"v": "toque"}, _Ponte())
    monkeypatch.setattr(ipc_bridge, "_corpo_do_daemon", lambda *_a, **_k: parada)
    monkeypatch.setattr(bluez_dbus, "a_suite_esta_rodando", lambda: False)
    html = a08.html_do_agora_das_extensoes(a08._ler_o_agora_das_extensoes())
    assert html.count("via Toque") == 2, "a parada sumiu da aba Conexões"


def test_sob_a_suite_a_conexoes_nunca_pergunta_ao_servico(monkeypatch) -> None:
    from hefesto_dualsense4unix.app import ipc_bridge

    def proibido(*_: Any, **__: Any) -> Any:
        raise AssertionError("a suíte fez IPC")

    monkeypatch.setattr(ipc_bridge, "_corpo_do_daemon", proibido)
    assert _a08()._ler_o_agora_das_extensoes() == []


def test_a_vaga_da_conexoes_pinta_o_que_a_leitura_em_fundo_trouxe(monkeypatch) -> None:
    from hefesto_dualsense4unix.interface.pacotes import em_fundo

    a08 = _a08()
    monkeypatch.setattr(em_fundo, "_FUNDO", {})
    monkeypatch.setattr(em_fundo, "LER_NA_HORA", True)
    monkeypatch.setattr(a08, "_ler_o_agora_das_extensoes", lambda: [("Toque", VIVO)])
    html = a08._html_do_agora_das_extensoes()
    assert html.count("via Toque") == 2 and "Adaptador" in html and "Motor" in html


# -- os toques cabem nos dois arranjos ------------------------------------------------------


@pytest.mark.parametrize(("larg", "alt"), [(1212, 809), (1600, 840), (1918, 840)])
@pytest.mark.parametrize("com_agora", [True, False], ids=["arranjo-c", "cartoes"])
def test_os_toques_cabem_sem_corte_nos_dois_arranjos(navegador, larg, alt, com_agora) -> None:  # noqa: F811
    """A linha do toque encolhe a onda e a lista: no cartão da janela sem ``agora`` (meia
    largura), os 19 botões cortavam a lista da direita (medido na bancada de 22/10/2026).
    MORDIDA: devolva ``flex:none`` à ``.onda`` e ``width:120px`` à lista do ``.tql``."""
    sys.path.insert(0, str(INTERFACE))
    import desenho_da_experimental as exp

    todos = [o._replace(botoes=BOTOES) if o.tipo == "por_botao" else o
             for o in exp.OPCOES_DO_DESENHO_C]
    extra: dict[str, Any] = {"agora": exp.AGORA_DO_DESENHO, "estado": exp.ESTADO_DO_DESENHO,
                             "parar_tudo": True} if com_agora else {}
    janela = exp.modificacao_miolo_html("Minha extensão", todos, mod="exemplo", **extra)
    pg = navegador.new_page(viewport={"width": larg, "height": alt})
    try:
        pg.goto(f"{MOCKUP.as_uri()}#modificacao")  # (noqa-acento: âncora do HTML)
        pg.evaluate("h => { document.getElementById('mod-janela').innerHTML = h; }", janela)
        m = pg.evaluate("""() => { const j = document.getElementById('mod-janela');
          const linhas = [...j.querySelectorAll('.tql')];
          const r = j.getBoundingClientRect();
          return {linhas: linhas.length, corte: linhas.filter(
                    l => l.scrollWidth > l.clientWidth + 1).length,
                  lista: Math.min(...linhas.map(
                    l => l.querySelector('select').getBoundingClientRect().width)),
                  cabe: r.top >= 0 && r.bottom <= innerHeight + 1}; }""")
        assert m["linhas"] == len(BOTOES) and m["corte"] == 0 and m["cabe"], m
        assert m["lista"] >= 64, m
    finally:
        pg.close()
