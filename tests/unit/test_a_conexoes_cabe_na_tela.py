"""A aba Conexões e o Mapa cabem na tela, sem repetir e sem texto demais.

A-CONEXOES-CABE-NA-TELA-SEM-REPETIR-E-SEM-TEXTO-DEMAIS-01 (05/10/2026), o desenho aprovado
(``docs/process/estudos/2026-10-05-a-conexoes-enxuta/DESENHO-APROVADO.md``). A régua do desenho era
o ``medir_ajustado.py`` (21 vistas num Chrome); esta é a do produto: as mesmas vistas no WebKit,
na página que o produto renderiza depois do ``--publicar`` e, enquanto ele não roda, na bancada.

TUDO É DE MENTIRA: as páginas num WebKit fora da tela, com o pintor do piloto; nada chega a daemon.

AS MORDIDAS (feitas na sprint, uma de cada vez, com a cura devolvida e o md5 conferido):
tirar o ``position:absolute`` do ``.cd-porque`` reprova a régua do ⓘ; devolver o «Mais N» (o
corte do ``html_das_dicas``) reprova a dos quatro cartões; ``LINHAS_NUMA_COLUNA`` sem limite (uma
coluna só) reprova a das linhas do ar; tirar o ``_nao_e_sem_fio`` reprova a da webcam; devolver o
``emTitulo`` ao fim da pintura do Mapa reprova a das frases; devolver a bandeja esticada
(``align-self:start`` fora) reprova a rolagem das Sugestões a 1272 e 1512 px.
"""

from __future__ import annotations

import gc
import json
import re
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes.a08_conexoes`, que carrega o GTK")

from hefesto_dualsense4unix.integrations import dicas_da_conexao as dicas
from hefesto_dualsense4unix.integrations import faixas_do_ar
from hefesto_dualsense4unix.interface import onde, pagina_do_mapa
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08

RAIZ = Path(__file__).resolve().parents[2]
CONJUNTO = "Conexões 3"
#: o Mapa espera a publicação pelas edições da bancada; a 08, pelo desenho novo na página.
MAPA_NA_BANCADA = any(CONJUNTO in e.porque for e in pagina_do_mapa.EDICOES_ESPERANDO_A_SESSAO_DELA)
_PUBLICADA_08 = onde.pagina("08-conexoes.html", publicado=True)
A_08_NA_BANCADA = 'class="ar-do"' not in _PUBLICADA_08.read_text(encoding="utf-8")
LARGURAS = {1272: 860, 1512: 860, 1900: 1000}


# ───────────────────────── sem página: o que o gerador escreve ─────────────────────────


def _dica(chave: str, nivel: str = dicas.AJUSTE) -> dicas.Dica:
    return dicas.Dica(chave=chave, icone=dicas.ICONE_AJUDA, titulo=chave, nivel=nivel,
                      acao=dicas.Acao(dicas.MAPA, dicas.ROTULO_VER_NO_MAPA,
                                      href=dicas.PAGINA_DO_MAPA), porque="Uma frase.")


def test_quatro_cartoes_numa_fileira_sem_mais_n_e_sem_a_linha_dos_certos() -> None:
    from hefesto_dualsense4unix.interface.conexoes import html_das_dicas

    painel = dicas.montar([_dica(f"d{i}") for i in range(6)], certos=("Energia do rádio",))
    html = html_das_dicas(painel)
    assert html.count('<section class="cartao-dica') == 4 == dicas.CARTOES_VISIVEIS
    assert "mais-dicas" not in html and "Mais " not in html, "voltou o «Mais N»"
    assert "dicas-certas" not in html and "✓ Energia" not in html, "voltou a linha dos ✓"
    vazio = html_das_dicas(dicas.montar([]))
    assert re.search(r'class="nada-a-mudar"><i aria-hidden="true"></i>Tudo certo</p>', vazio)


def test_o_gesto_do_cartao_tem_ate_duas_palavras() -> None:
    m = dicas.Movimento(controle="ap", jogador=2, nome_do_controle="Roxo", de_id="L1",
                        de_nome="Meio", para_id="L2", para_nome="Direita", controles_no_de=4)
    rotulos = [dicas.dica_do_movimento(m).acao.rotulo, dicas.ROTULO_VER_NO_MAPA,
               dicas.ROTULO_IGNORAR, dicas.ROTULO_VOLTAR_A_MOSTRAR, dicas.ROTULO_PAREAR,
               dicas.dica_do_wifi("caiu 2\u00d7", False, "", dicas.AJUSTE).acao.rotulo,
               dicas.dica_do_receptor("teclado", "3 teclas presas", "em 1 h").acao.rotulo]
    miudas = {"a", "o", "e", "de", "da", "do", "no", "na"}
    for rotulo in rotulos:
        palavras = [w for w in rotulo.split() if w.lower() not in miudas]
        assert len(palavras) <= dicas.PALAVRAS_NO_GESTO, rotulo
    assert rotulos[0] == "Mover P2"


def _cena_do_ar() -> dict[str, Any]:
    """Um adaptador com cinco aparelhos, outro vazio, o Wi-Fi em 5 GHz, um receptor e a webcam."""
    lugares = [{"id": "L1", "nome": "Meio"}, {"id": "L2", "nome": "Direita"}]
    aparelhos = [{"id": f"aa:bb:cc:00:00:0{i}", "tipo": "controle", "lugar": "L1", "cor": "#ff5555",
                  "nome": f"C{i}", "conectado": True} for i in range(1, 6)]
    vizinhos = [
        {"id": "25a7:fa07", "tipo": "", "sugestao": "Teclado", "sugestao_tipo": "teclado",
         "lido": "Teclado", "receptor": True, "banda": None, "saude": None},
        {"id": "046d:0825", "tipo": "", "sugestao": "Webcam", "sugestao_tipo": "webcam",
         "lido": "Câmera", "receptor": False, "banda": None, "saude": None},
    ]
    return {"lugares": lugares, "aparelhos": aparelhos, "evitados": [],
            "canais_medidos": {"L1": True, "L2": True}, "vizinhos": vizinhos,
            "wifi": [{"mhz": 5805, "ssid": "casa"}], "portas": []}


def test_cada_linha_do_ar_e_icone_faixa_e_ponto_e_so_o_que_fala_pelo_ar() -> None:
    """Um receptor é uma linha; a webcam e o Wi-Fi de 5 GHz não ganham linha; sem a frase do
    grupo."""
    html = a08.html_dos_canais(_cena_do_ar())
    linhas = re.findall(r'<div class="ar-linha" data-id="([^"]+)"', html)
    assert linhas.count("25a7:fa07") == 1, linhas
    assert "046d:0825" not in linhas, "a webcam não é rádio"
    assert not [x for x in linhas if x.startswith("wifi")], "o Wi-Fi de 5 GHz não atrapalha"
    assert a08.OUTROS_SEM_FIO in html and "Os outros rádios da casa" not in html
    assert "dividem o tempo" not in html and "nenhum aparelho no ar" not in html
    assert 'data-grupo="L2"' not in html, "o adaptador sem ninguém no ar ganhou linha"
    assert html.count('class="ar-duas"') == 1, "cinco aparelhos numa entrada vão em duas colunas"
    for nome in ("C1", "Teclado"):
        assert f">{nome}<" not in html, f"o nome {nome} voltou a ser texto da linha"
    assert "ar-regua" not in html and "MHz</span>" not in html
    pontos = re.findall(r'class="ar-selo ([^"]*)"[^>]*title="([^"]*)"', html)
    assert pontos and all(t for _c, t in pontos), pontos
    receptor = re.search(r'data-id="25a7:fa07".*?</div></div>', html, re.S)
    assert receptor and 'data-gesto="receptor-descobrir"' in receptor.group(0)
    assert a08.FAIXA_NAO_DESCOBERTA in receptor.group(0)


def test_o_ponto_verde_diz_tudo_certo_e_o_vermelho_diz_o_problema_so_no_tooltip() -> None:
    bom = faixas_do_ar.Linha(id="x", tipo="controle", nome="X",
                             selo=faixas_do_ar.Selo("boa", "boa 70/79"))
    ruim = faixas_do_ar.Linha(id="y", tipo="wifi", nome="Y", nota="em 24 min",
                              selo=faixas_do_ar.Selo("sofrendo", "caiu 12\u00d7"))
    verde = a08._o_ponto(bom, "")
    assert 'class="ar-selo boa"' in verde and 'title="Tudo certo"' in verde
    assert 'title="Caiu 12\u00d7 em 24 min"' in a08._o_ponto(ruim, "")
    assert "></span>" in a08._o_ponto(ruim, ""), "o texto do problema virou letra na linha"


def test_o_mapa_fala_em_frase_e_sem_primeira_pessoa() -> None:
    """O Mapa da bancada não põe Maiúscula Em Toda Palavra no fim da pintura, e as frases que o
    desenho aprovado reescreveu estão lá (o que o ``emTitulo`` desfaria na tela)."""
    pagina = pagina_do_mapa.pagina()
    assert 'emTitulo(document.querySelector(".pagina"))' not in pagina, (
        "a pintura voltou a pôr maiúscula em toda palavra")
    for frase in ("Leitura de exemplo", "Conectado agora", "Já mudei", "Desfazer"):
        assert frase in pagina, frase
    for velha in ("Atualmente Conectado", "Não achei", "Eu acho"):
        assert f">{velha}" not in pagina, velha


# ───────────────────────── as páginas (WebKit) ─────────────────────────


def _medir() -> str:
    return r"""(function(){
  const r = [];
  for (const e of document.querySelectorAll('*')) {
    const cs = getComputedStyle(e);
    if (/auto|scroll/.test(cs.overflowY) && e.scrollHeight > e.clientHeight + 2
        && e.clientHeight > 80)
      r.push((String(e.className).split(' ')[0] || e.tagName) + ': '
             + (e.scrollHeight - e.clientHeight));
  }
  const d = document.documentElement;
  if (d.scrollHeight > innerHeight + 2) r.push('página: ' + (d.scrollHeight - innerHeight));
  const corta = [...document.querySelectorAll('button,span,b,label,a,h3,h4,p')].filter(e =>
    e.offsetParent && e.scrollWidth > e.clientWidth + 1
    && getComputedStyle(e).overflow !== 'visible'
    && e.children.length === 0 && e.textContent.trim()).map(e => e.textContent.trim().slice(0, 30));
  const alturas = [...document.querySelectorAll('.cartao-dica')].map(
    c => Math.round(c.getBoundingClientRect().height));
  const abertos = [...document.querySelectorAll('.cd-porque')].filter(
    p => !p.hidden && p.offsetParent);
  const porqueFora = abertos.map(p => p.getBoundingClientRect().top + 1
    >= p.closest('.cartao-dica').getBoundingClientRect().bottom);
  const aberta = [...document.querySelectorAll('.radio .sala .lugar.aberto')].length;
  return JSON.stringify({rola: r, corta: corta, alturas: alturas, porqueFora: porqueFora,
                         aberta: aberta});
})()"""


def _clicar(seletor: str, n: int = 0) -> str:
    alvo = json.dumps(seletor)
    return (f"(function(){{const b=document.querySelectorAll({alvo})[{n}];"
            f"if(!b){{return 'sem ' + {alvo};}} b.click(); return 'clicou';}})()")


def _pintar_as_dicas(html: str) -> str:
    return f"String(window.__hef.pintar({json.dumps({'mesa': {'dicas': html}})}))"


def _no_webkit(pagina: Path, tamanho: tuple[int, int], passos: list[str]) -> list[Any]:
    try:
        return _no_webkit_sem_recolher(pagina, tamanho, passos)
    finally:
        gc.collect()
        from gi.repository import Gtk

        while Gtk.events_pending():
            Gtk.main_iteration_do(False)


def _no_webkit_sem_recolher(pagina: Path, tamanho: tuple[int, int],
                            passos: list[str]) -> list[Any]:
    from tests.conftest import exigir_gi_real

    exigir_gi_real("abre a página num WebKit")
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")
    from hefesto_dualsense4unix.interface import hefesto_vivo

    respostas: list[str] = []
    view = WebKit2.WebView()
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(*tamanho)
    view.set_size_request(*tamanho)
    janela.add(view)
    janela.show_all()
    fila = [hefesto_vivo.BOOTSTRAP, *passos]

    def seguinte() -> bool:
        if not fila:
            Gtk.main_quit()
            return False

        def respondeu(v: Any, res: Any, _u: Any = None) -> None:
            try:
                respostas.append(v.evaluate_javascript_finish(res).to_string())
            except Exception as erro:
                respostas.append(f"ERRO {erro}")
            GLib.timeout_add(250, seguinte)

        view.evaluate_javascript(fila.pop(0), -1, None, None, None, respondeu, None)
        return False

    def carregou(_v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            GLib.timeout_add(300, seguinte)

    view.connect("load-changed", carregou)
    view.load_uri(pagina.as_uri())
    guarda = GLib.timeout_add(60000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert len(respostas) == len(passos) + 1, f"o WebKit parou no meio: {respostas}"
    return [json.loads(x) if x.startswith("{") else x for x in respostas[1:]]


_VISTAS: dict[int, dict[str, Any]] = {}


def _vistas(largura: int) -> dict[str, Any]:
    """As sete vistas de uma largura: Gestão, ⓘ aberto, Tudo certo, Rádio, adaptador aberto, Mapa,
    Sugestões e Adicionar."""
    if largura not in _VISTAS:
        from hefesto_dualsense4unix.interface.conexoes import html_das_dicas

        tamanho = (largura, LARGURAS[largura])
        a08_pagina = onde.pagina("08-conexoes.html", publicado=not A_08_NA_BANCADA)
        lidas = _no_webkit(a08_pagina, tamanho, [
            _medir(), _clicar(".cartao-dica .cd-info", 1), _medir(),
            _clicar(".cartao-dica .cd-info", 1), _pintar_as_dicas(html_das_dicas(dicas.montar([]))),
            _medir(), _clicar('label[for="cx8-3"]'), _medir(),
            "(function(){const l=[...document.querySelectorAll('.lugar .abre-lugar')];"
            "if(!l.length) return 'sem caixa'; l[l.length-1].click(); return 'clicou';})()",
            _medir()])
        mapa_pagina = onde.pagina(pagina_do_mapa.DESTINO.name, publicado=not MAPA_NA_BANCADA)
        mapa = _no_webkit(mapa_pagina, tamanho, [
            _medir(), _clicar('.modo[data-modo="ideal"]'), _medir(),
            _clicar('.modo[data-modo="mao"]'), _medir()])
        _VISTAS[largura] = {"gestao": lidas[0], "porque": lidas[2], "certo": lidas[5],
                            "radio": lidas[7], "adaptador": lidas[9], "mapa": mapa[0],
                            "sugestoes": mapa[2], "adicionar": mapa[4]}
    return _VISTAS[largura]


@pytest.mark.parametrize("largura", sorted(LARGURAS))
def test_nenhuma_vista_rola_na_vertical_nem_corta_texto(largura: int) -> None:
    """As 21 vistas do ``medir_ajustado.py`` (sete por largura e o ⓘ aberto), sem rolagem."""
    vistas = _vistas(largura)
    # a vista do adaptador aberto só mede alguma coisa se a caixa abriu de fato: sem isto, um
    # clique que não abre deixa medir o Rádio fechado duas vezes, e o verde não diz nada
    assert vistas["radio"]["aberta"] == 0, "uma caixa nasceu aberta: o desenho as quer fechadas"
    assert vistas["adaptador"]["aberta"] == 1, "o clique não abriu a caixa do adaptador"
    rolam = {nome: v["rola"] for nome, v in vistas.items() if v["rola"]}
    assert not rolam, f"a {largura} px rolam: {rolam}"
    cortam = {nome: v["corta"] for nome, v in vistas.items() if v["corta"]}
    assert not cortam, f"a {largura} px cortam texto: {cortam}"


@pytest.mark.parametrize("largura", sorted(LARGURAS))
def test_os_cartoes_tem_a_mesma_altura_e_o_porque_nao_estica_os_vizinhos(largura: int) -> None:
    vistas = _vistas(largura)
    antes, depois = vistas["gestao"]["alturas"], vistas["porque"]["alturas"]
    assert antes and len(set(antes)) == 1, f"os cartões nascem de alturas diferentes: {antes}"
    assert antes == depois, f"abrir o ⓘ mudou a altura dos cartões: {antes} → {depois}"
    assert vistas["porque"]["porqueFora"] == [True], (
        f"o porquê aberto não flutua por baixo do cartão: {vistas['porque']['porqueFora']}")
    assert vistas["certo"]["alturas"] == [], "o «Tudo certo» ainda tem cartão"
