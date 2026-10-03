#!/usr/bin/env python3
"""AS TRÊS DECISÕES DA ABA `09` SISTEMA — e as três são sobre o mesmo botão.

A [02] é do PO em 04/09/2026
(o registro «O-PO-DECIDE-as-54-e-os-sete-conflitos» de 04/09/2026, §2 `09`);
a [01] e a [03] são DELA, em 05/09/2026, e a [01] REVERTEU o PO.

**[01] — o botão continua se chamando "Atualizar".** Palavra dela na 09-Q1:
*"Segue fazendo os dois. Com mesmo nome"*. Ele faz DOIS trabalhos, e a dica
NEGAVA o caro: dizia *"Relê tudo o que esta aba mostra. Não muda nada."* — e o
clique manda o IPC `daemon.reload`, que do outro lado derruba e sobe o leitor
dos atalhos do controle e reescreve os arquivos de ambiente que a Steam usa
para lançar jogo. Quem para de mentir é a DICA, não o rótulo: a metade barata
(reler a aba, 4 ms) **já acontece sozinha a cada 2 s** (`a09_sistema.LENTO_S`),
e é por isso que o nome cabe num botão que faz os dois.

**[02] — apagado e ainda assim responde.** Três botões desta página ficam sem
trabalho a fazer, e a conta de quem está sem já existia no produto
(`interface/sistema.travas()`, com o motivo em português). O que faltava era a
metade do desenho. `disabled` mataria o clique, e o clique é o único caminho de
quem chega pelo controle até a razão.

**[03] — o botão diz que está trabalhando.** `daemon.reload` leva **9,5 s**
(medido no daemon dela em 01/09) e o clique sumia por nove segundos e meio: o
segundo clique parecia o primeiro. A palavra da espera é dela, na 09-Q3:
*"Atualizando…"*.

O QUE ESTA RÉGUA MEDE, e em três camadas — cada uma pega o que a de cima não
consegue ver:

1. **o PACOTE** emite a razão de cada botão em TODO tique, inclusive vazia, e a
   frase é a do produto — nunca uma digitada aqui;
2. **o DESENHO** carrega a peça inteira (botão + `?` no MESMO `data-campo`), o
   rótulo que ela mandou manter, o rótulo da espera, e a dica que parou de
   negar;
3. **a TELA VIVA**, num WebKit de verdade com o piloto do produto: a razão
   ACENDE o cinza, o `?` aparece com a frase, a razão vazia APAGA o cinza de
   volta, as duas colunas irmãs continuam acabando no mesmo `y` nos dois
   estados, e o botão troca de palavra DURANTE a espera e volta inteiro.

POR QUE A CAMADA 3 ABRE O DESENHO E NÃO O PUBLICADO: **publicar é ato dela**, e
a [01] move dois pixels (o rótulo e o da espera). A régua aponta o
`onde.PUBLICADO` para
uma cópia da bancada num diretório temporário — que é o desenho de HOJE — em vez
de dar verde sobre a página congelada, a armadilha mais cara do
`COMO-OLHAR-A-TELA.md`.

A MORDIDA (colada no relato desta frente):

* apague `fora.update(razoes_do_cinza(ctx))` do `pacote()` e a camada 1 reprova
  nomeando as três chaves que sumiram — e com elas o botão que ficaria cinza
  para sempre;
* troque um `item_cinza(...)` por `item(...)` no gerador e a régua 7 dele
  reprova antes mesmo de a página existir;
* tire o `em_voo=EM_VOO_ATUALIZAR` do gerador e a aba inteira cai no `import
  aba09`, com o `SystemExit` da régua 9 dele — **a camada 3 nunca chega a
  medir**, porque a página não é escrita. Medido em 06/09/2026; a guarda do
  gerador é mais dura que esta régua, e é ela que responde;
* tire a palavra "atalhos" da `DICA_ATUALIZAR` e a camada 2 reprova nomeando a
  dica que voltou a esconder o trabalho caro;
* troque só o VALOR de `ROTULO_ATUALIZAR` e as duas linhas que o comparam com
  `aba09.ROTULO_ATUALIZAR` continuam VERDES — medido. Quem morde é a linha que
  cobra a palavra dela LITERAL, logo abaixo delas.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.sistema`, que carrega o GTK")

from hefesto_dualsense4unix.interface import sistema as _tela
from hefesto_dualsense4unix.interface import monta as _monta
from hefesto_dualsense4unix.interface import onde as _onde
from hefesto_dualsense4unix.interface.pacotes import (
    Contexto,
    normalizar,
)
from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

PAGINA = "09-sistema.html"

BANCADA = _onde.pagina(PAGINA)


def _html() -> str:
    return BANCADA.read_text(encoding="utf-8")


def _ctx(status: str, pausado: bool | None) -> Contexto:
    """Um contexto com o estado que a camada do produto sabe ler."""
    estado: dict = {"active_profile": "regua"}
    if pausado is not None:
        estado["paused"] = pausado
    return Contexto(state=estado, mesa=[], conectados=[], estados={})


def _com_a_leitura(monkeypatch: pytest.MonkeyPatch, status: str,
                   pausado: bool | None) -> Contexto:
    """Desvia SÓ a leitura cara; quem decide continua sendo o produto.

    `aba_sistema.travas()` é uma função PURA de `Leitura`, e é ela que produz a
    frase. Dublá-la seria medir o dublê; dublar `_leitura` é dar-lhe a entrada
    e deixar a conta acontecer.
    """
    ctx = _ctx(status, pausado)
    #: preço foi medido: `aba_sistema.pacote()` levantava `AttributeError`, o
    leitura = _tela.Leitura(status=status, autostart="enabled", state=ctx.state,
                            achados=None, deteccao=None, ambiente=None,
                            perfil=None)
    monkeypatch.setattr(a09, "_leitura", lambda _c: leitura)
    return ctx


class TestOPacoteEmiteARazao:
    """A razão de cada botão cinza, em todo tique."""

    def test_de_pe_e_sem_pausa_o_reiniciar_nao_tem_razao(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        ctx = _com_a_leitura(monkeypatch, "online_systemd", pausado=False)
        fora = a09.razoes_do_cinza(ctx)
        assert f"retomar{a09.SUFIXO_DA_RAZAO}" not in fora, fora
        assert fora[f"reiniciar{a09.SUFIXO_DA_RAZAO}"] == ""
        assert f"ver-plugins{a09.SUFIXO_DA_RAZAO}" not in fora

    def test_com_o_servico_parado_os_tres_tem_razao(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        ctx = _com_a_leitura(monkeypatch, "offline", pausado=False)
        fora = a09.razoes_do_cinza(ctx)
        vazias = [k for k, v in fora.items() if not v]
        assert not vazias, (
            f"com o serviço desligado estes continuam clicáveis: {vazias}. A "
            "conta é de `aba_sistema.travas()`, e ela tranca os três.")

    def test_a_chave_vem_mesmo_vazia(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        """É esta que faz o botão DESACENDER."""
        ctx = _com_a_leitura(monkeypatch, "online_systemd", pausado=True)
        fora = a09.razoes_do_cinza(ctx)
        assert set(fora) == {f"{g}{a09.SUFIXO_DA_RAZAO}"
                             for g in a09.BOTOES_CINZAS}, fora
        assert all(v == "" for v in fora.values()), fora

    def test_a_frase_e_a_do_produto_e_nao_uma_digitada_aqui(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        ctx = _com_a_leitura(monkeypatch, "offline", pausado=False)
        do_produto = _tela.travas(a09._leitura(ctx))
        for nome in a09.BOTOES_CINZAS:
            assert (a09.razoes_do_cinza(ctx)[f"{nome}{a09.SUFIXO_DA_RAZAO}"]
                    == do_produto[nome])

    def test_a_leitura_que_levanta_nao_pinta_ninguem_de_cinza(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Sem leitura não há razão para apagar, e apagar sem razão é a tela"""
        def explode(_c: object) -> object:
            raise RuntimeError("o daemon calou no meio do tique")

        monkeypatch.setattr(a09, "_leitura", explode)
        fora = a09.razoes_do_cinza(_ctx("online_systemd", pausado=False))
        assert all(v == "" for v in fora.values()), fora

    def test_o_marcador_do_nada_nao_serve_a_este_campo(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`monta.NADA_A_DIZER` acenderia o cinza PARA SEMPRE."""
        ctx = _com_a_leitura(monkeypatch, "online_systemd", pausado=True)
        assert _monta.NADA_A_DIZER not in a09.razoes_do_cinza(ctx).values()

    @pytest.mark.parametrize("status", ["online_systemd", "offline"])
    def test_o_pacote_do_tique_leva_as_tres_chaves(
            self, monkeypatch: pytest.MonkeyPatch, status: str) -> None:
        """A metade que `razoes_do_cinza` sozinha não prova."""
        ctx = _com_a_leitura(monkeypatch, status, pausado=False)
        monkeypatch.setattr(
            a09, "_faixa_lenta",
            lambda *a, **k: ("enabled", None, None, status, None))
        fora = a09.pacote(ctx)
        for nome in a09.BOTOES_CINZAS:
            assert f"{nome}{a09.SUFIXO_DA_RAZAO}" in fora, sorted(fora)

    def test_o_ramo_de_erro_tambem_leva_as_tres_chaves(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        """UM DEFEITO VIVO, achado medindo em 04/09/2026."""
        ctx = _com_a_leitura(monkeypatch, "offline", pausado=False)
        monkeypatch.setattr(
            a09, "_faixa_lenta",
            lambda *a, **k: ("enabled", None, None, "offline", None))

        def cala(_leitura: object) -> object:
            raise RuntimeError("a camada do produto calou")

        monkeypatch.setattr(a09._tela, "pacote", cala)
        fora = a09.pacote(ctx)
        assert fora.get("sem_dono"), "a régua não chegou ao ramo de erro"
        for nome in a09.BOTOES_CINZAS:
            assert f"{nome}{a09.SUFIXO_DA_RAZAO}" in fora, sorted(fora)

    def test_normalizar_leva_a_chave_vazia_ate_a_mesa(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        """O funil da pintura não pode comer o vazio no caminho."""
        ctx = _com_a_leitura(monkeypatch, "online_systemd", pausado=True)
        mesa = normalizar(dict(a09.razoes_do_cinza(ctx)))["mesa"]
        for nome in a09.BOTOES_CINZAS:
            assert f"{nome}{a09.SUFIXO_DA_RAZAO}" in mesa, mesa


class TestODesenhoCarregaAPeca:
    """O que a página tem de trazer para a decisão [02] existir."""

    def test_o_que_espera_a_publicacao_esta_declarado_nos_dois_sentidos(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A declaração morre no dia em que a dívida é paga."""
        import re

        publicada = set(re.findall(
            r'data-campo="([^"]+)"',
            _onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")))
        no_desenho = set(re.findall(r'data-campo="([^"]+)"', _html()))
        do_cinza = {f"{n}{a09.SUFIXO_DA_RAZAO}" for n in a09.BOTOES_CINZAS}

        assert do_cinza <= no_desenho, (
            f"o DESENHO não tem {sorted(do_cinza - no_desenho)} — rode "
            "`src/hefesto_dualsense4unix/interface/aba09.py`.")
        ctx = _com_a_leitura(monkeypatch, "online_systemd", pausado=True)
        emitidos = set(normalizar(dict(a09.pacote(ctx)))["mesa"])
        esperados = (no_desenho & emitidos) - publicada
        assert set(a09.ESPERA_A_PUBLICACAO) == esperados, (
            "a declaração `ESPERA_A_PUBLICACAO` divergiu do disco: ela diz "
            f"{sorted(a09.ESPERA_A_PUBLICACAO)} e o que o pacote emite, o "
            f"desenho tem e a publicada não tem é {sorted(esperados)}. Se a aba "
            "foi publicada, TIRE a declaração — ela já não descreve nada.")

    def test_o_par_de_sufixos_nao_diverge(self) -> None:
        """O gerador escreve o `data-campo`; o pacote escreve NELE."""
        import aba09

        assert aba09.SUFIXO_DA_RAZAO == a09.SUFIXO_DA_RAZAO

    @pytest.mark.parametrize("nome", a09.BOTOES_CINZAS)
    def test_o_botao_tem_as_quatro_metades(self, nome: str) -> None:
        import re

        campo = f"{nome}{a09.SUFIXO_DA_RAZAO}"
        achado = re.search(
            r'<button class="[^"]*"[^>]*data-campo="' + re.escape(campo)
            + r'"[^>]*>', _html())
        assert achado, f"o botão de {nome!r} não endereça {campo!r}"
        for exigido in ('data-hef-alvo="classe"', 'data-hef-classe="apagado"',
                        'data-hef-atributo="aria-disabled"',
                        f'data-gesto="{nome}"'):
            assert exigido in achado.group(0), (
                f"{nome}: falta {exigido} — a peça da D-03 é inteira, e o "
                "`data-gesto` é o que faz o clique CHEGAR ao botão apagado.")

    @pytest.mark.parametrize("nome", a09.BOTOES_CINZAS)
    def test_a_dica_leva_o_mesmo_campo(self, nome: str) -> None:
        campo = f"{nome}{a09.SUFIXO_DA_RAZAO}"
        assert (f'<span class="dica" data-campo="{campo}" data-hef-alvo="html">'
                in _html()), (
            f"o `?` de {nome!r} não recebe {campo!r}. Um campo só alimenta os "
            "dois: com dois, dá para pintar um botão cinza sem razão.")

    def test_nenhum_botao_cinza_emite_disabled(self) -> None:
        """*"Apagado e ainda assim responde."* `disabled` mata o clique."""
        import re

        for achado in re.finditer(r"<button[^>]*data-hef-classe=\"apagado\"[^>]*>",
                                  _html()):
            solto = re.search(r'(?<![-\w])disabled(?=[\s=>])', achado.group(0))
            assert not solto, achado.group(0)

    def test_o_botao_do_reload_manteve_o_nome_e_diz_a_espera(self) -> None:
        import re

        import aba09

        achado = re.search(
            r'<button class="btn"([^>]*data-gesto="atualizar"[^>]*)>([^<]*)</button>',
            _html())
        assert achado, "o botão do `atualizar` sumiu da página"
        atributos, rotulo = achado.group(1), achado.group(2)
        assert rotulo == aba09.ROTULO_ATUALIZAR, rotulo
        assert f'data-hef-em-voo="{aba09.EM_VOO_ATUALIZAR}"' in atributos
        assert rotulo == "Atualizar", (
            f"o botão diz {rotulo!r}. Ela mandou manter 'Atualizar' — *\"Segue "
            "fazendo os dois. Com mesmo nome\"*, 09-Q1, 05/09/2026 —, "
            "revertendo a recomendação de 04/09 que o rebatizava pela metade "
            "cara.")
        assert 'data-hef-em-voo="Atualizando…"' in atributos, (
            f"o rótulo da espera não é o dela: {atributos!r}. Na 09-Q3 ela "
            "escreveu *\"o botão diz Atualizando…\"*.")

    def test_a_dica_do_reload_parou_de_negar_o_trabalho_caro(self) -> None:
        import re

        achado = re.search(
            r'<button class="btn" title="([^"]*)"[^>]*data-gesto="atualizar"',
            _html())
        assert achado, "a dica do botão do `atualizar` sumiu"
        dica = achado.group(1)
        assert "Não muda nada" not in dica, dica
        # `config_overrides` vazio o `daemon.reload` NÃO reaplica configuração
        assert "atalhos" in dica.lower() and "Steam" in dica, dica
        assert "reaplicar" not in dica.lower(), dica


LER_A_TELA = r"""
(function(){
  // o 'ver-plugins' saiu em 13/09/2026; o 'retomar' virou o 'parar-ou-retomar'
  // em 25/09/2026 (A-09-SISTEMA-EM-TRES-SECOES-01), e ele não tem cinza.
  const alvos = ['reiniciar'];
  const botoes = {};
  for(const g of alvos){
    const b = document.querySelector('[data-gesto="' + g + '"]');
    if(!b){ botoes[g] = null; continue; }
    const ajuda = b.nextElementSibling;
    const dica = ajuda ? ajuda.querySelector('.dica') : null;
    botoes[g] = {
      apagado: b.classList.contains('apagado'),
      aria: b.getAttribute('aria-disabled'),
      // O QUE A TELA MOSTRA, e não o que a regra diz: `display` vem do CSSOM.
      ajuda_visivel: ajuda ? getComputedStyle(ajuda).display !== 'none' : null,
      razao: dica ? (dica.textContent || '').trim() : null,
      rotulo: (b.textContent || '').trim(),
      largura: Math.round(b.getBoundingClientRect().width),
    };
  }
  // AS COLUNAS IRMÃS DE HOJE são as das Configurações Avançadas (25/09/2026):
  // a do Serviço, onde mora o botão que acinzenta, e a dos ligáveis, a última.
  const est = document.querySelector('.avancadas .col-servico');
  const acao = document.querySelector('.avancadas .col-ligaveis');  // (noqa-acento) nome
  const bloco = document.querySelector('.avancadas');
  const miolo = document.querySelector('.janela > .miolo') ||
                document.querySelector('.miolo');
  const rea = document.querySelector('[data-gesto="atualizar"]');
  // ONDE UM ELEMENTO ACABA, arredondado. As duas irmãs medem pela mesma peça.
  const fim = (el) => el ? Math.round(el.getBoundingClientRect().bottom) : null;
  return JSON.stringify({
    botoes: botoes,
    // AS DUAS COLUNAS IRMÃS, medidas onde elas ACABAM.
    fim_do_estado: fim(est),
    fim_da_acao: fim(acao),  // (noqa-acento) `acao` é nome de variável do JS
    // E A ALTURA DA FAIXA. Ela é o que o `?` faria crescer se virasse fileira —
    // e o `align-items:stretch` do `.par2` ESCONDE isso de quem só compara os
    // dois fins: a coluna irmã estica junto, os dois `bottom` continuam iguais,
    // e o que muda é a faixa INTEIRA empurrando o resto da aba para baixo.
    altura_da_faixa: bloco ? Math.round(bloco.getBoundingClientRect().height) : null,
    rola_por_dentro: miolo ? Math.max(0, miolo.scrollHeight - miolo.clientHeight) : null,
    reaplicar: rea ? {
      rotulo: (rea.textContent || '').trim(),
      em_voo: rea.classList.contains('hef-em-voo'),
      // A PISCADA DO "DEU CERTO" (05/09/2026, decisão dela na `03-Q4`). Ela é o
      // que responde no lugar da frase quando o gesto não trouxe notícia — ver
      // `test_o_gesto_que_da_certo_pisca_no_botao`.
      deu_certo: rea.classList.contains('hef-deu-certo'),
      filhos: rea.children.length,
    } : null,
    // O RECIBO DO GESTO (D-01), que é a linha L323 do CSV. Ele não é desta
    // frente — o canal é da ONDA0-P —, mas esta aba é uma das cinco que ele
    // fecha, e afirmar sem medir é o que esta casa não faz.
    recados: Array.prototype.map.call(
      document.querySelectorAll('.hef-recado'),
      function(el){ return {texto: (el.textContent || '').trim(),
                            tom: el.dataset.hefTom || ''}; }),
    // A CONTA DA RÉGUA DO MOCKUP no mesmo instante: a peça não pode mexer no
    // número de endereços da página.
    enderecos: document.querySelectorAll('[data-campo],[data-papel],[data-hef]').length,
  });
})()
"""

CLICAR_NO_ATUALIZAR = r"""
(function(){
  const b = document.querySelector('[data-gesto="atualizar"]');
  if(!b) return 'NAO ACHEI O BOTAO DO ATUALIZAR';
  b.click();
  return 'cliquei';
})()
"""

#: QUANTO O GESTO DUBLÊ DEMORA. O `daemon.reload` do produto leva 9,5 s; aqui
GESTO_LENTO_S = 1.4


@pytest.fixture(scope="module")
def na_tela() -> dict:
    """Abre o DESENHO DE HOJE no motor do produto, oculto, e mede."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    import argparse
    import tempfile
    import time as _time

    import hefesto_vivo as hv

    berco = pathlib.Path(tempfile.mkdtemp(prefix="a09-desenho-"))
    shutil.copytree(_onde.PUBLICADO, berco / "paginas",  # (noqa-acento) PASTA
                    dirs_exist_ok=True)
    shutil.copy2(BANCADA, berco / "paginas" / PAGINA)  # (noqa-acento) PASTA

    chave = (PAGINA, "atualizar")
    guardado = (hv.onde.PUBLICADO, hv.mesa_viva.estado_do_daemon,
                hv.pacotes.PACOTES.get(PAGINA), hv.pacotes.GESTOS.get(chave))
    hv.onde.PUBLICADO = berco / "paginas"  # type: ignore[assignment]  # (noqa-acento) PASTA
    hv.mesa_viva.estado_do_daemon = lambda *a, **k: {"active_profile": "regua"}  # type: ignore[assignment]

    leitura_parada = _tela.Leitura(
        status="offline", autostart=True, state={"paused": False},
        achados=None, deteccao=None, ambiente=None, perfil=None)
    leitura_de_pe = _tela.Leitura(
        status="online_systemd", autostart=True, state={"paused": True},
        achados=None, deteccao=None, ambiente=None, perfil=None)
    ctx_da_regua = Contexto(state={"paused": False}, mesa=[], conectados=[],
                         estados={})

    def _razoes(leitura: object) -> dict:
        antes = a09._leitura
        a09._leitura = lambda _c: leitura  # type: ignore[assignment]
        try:
            return dict(a09.razoes_do_cinza(ctx_da_regua))
        finally:
            a09._leitura = antes  # type: ignore[assignment]

    com_razao = _razoes(leitura_parada)
    sem_razao = _razoes(leitura_de_pe)

    carga = {"o_que": dict(com_razao)}
    hv.pacotes.PACOTES[PAGINA] = lambda ctx: dict(carga["o_que"])  # type: ignore[assignment]

    args = argparse.Namespace(
        oculta=True, segundos=0.0, passear=False, parada=900, foto="",
        abre=PAGINA, prova_no_aparelho=False, entre=2500, espera=1200,
        incluir_perigosos=False, prova_clique="", sem_cor=True,
        prova_de_mockup=False, voltas_por_aba=8, teto_de_mockup=-1,
        sem_cravado=False, sem_selo=False,
    )
    piloto = hv.Piloto(args)
    fora: dict[str, object] = {"do_produto": {"com_razao": com_razao,
                                              "sem_razao": sem_razao}}

    def ler(rotulo: str):
        def _leu(valor, erro):
            fora[rotulo] = (f"ERRO {erro}" if erro is not None
                            else json.loads(str(valor)))
        return _leu

    def anotar(rotulo: str):
        def _leu(valor, erro):
            fora[rotulo] = f"ERRO {erro}" if erro is not None else str(valor)
        return _leu

    def com_o_cinza() -> bool:
        if not piloto.pronto:
            return True
        piloto.ponte.perguntar(LER_A_TELA, ler("com-razao"))
        import os

        if os.environ.get("A9_FOTO"):
            piloto.tela.fotografar(os.environ["A9_FOTO"])
        GLib.timeout_add(600, sem_o_cinza)
        return False

    def sem_o_cinza() -> bool:
        carga["o_que"] = dict(sem_razao)
        GLib.timeout_add(600, leu_sem_o_cinza)
        return False

    def leu_sem_o_cinza() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("sem-razao"))
        GLib.timeout_add(300, o_voo)
        return False

    def o_voo() -> bool:
        hv.pacotes.GESTOS[chave] = (  # type: ignore[assignment]
            lambda ctx, o, p: (_time.sleep(GESTO_LENTO_S), None)[1])
        piloto.ponte.perguntar(CLICAR_NO_ATUALIZAR, anotar("clique"))
        GLib.timeout_add(450, no_meio_do_voo)
        return False

    def no_meio_do_voo() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("no-meio-do-voo"))
        GLib.timeout_add(int(GESTO_LENTO_S * 1000) + 900, pousou)
        return False

    def pousou() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("depois-do-pouso"))
        GLib.timeout_add(400, fim)
        return False

    def fim() -> bool:
        fora["fim"] = True
        Gtk.main_quit()
        return False

    GLib.timeout_add(400, lambda: piloto._ir(PAGINA))
    GLib.timeout_add(1800, com_o_cinza)
    guarda = GLib.timeout_add(60000, Gtk.main_quit)
    try:
        limite = _time.monotonic() + 60.0
        while "fim" not in fora and _time.monotonic() < limite:
            Gtk.main()
    finally:
        GLib.source_remove(guarda)
        piloto.pronto = False
        piloto.tela.janela.destroy()
        (hv.onde.PUBLICADO, hv.mesa_viva.estado_do_daemon,
         pacote_antigo, gesto_antigo) = guardado
        if pacote_antigo is not None:
            hv.pacotes.PACOTES[PAGINA] = pacote_antigo
        if gesto_antigo is not None:
            hv.pacotes.GESTOS[chave] = gesto_antigo
        else:
            hv.pacotes.GESTOS.pop(chave, None)
        shutil.rmtree(berco, ignore_errors=True)
    if "depois-do-pouso" not in fora:
        pytest.fail(f"o roteiro não chegou ao fim: {sorted(fora)}")
    return fora


class TestNaTelaViva:
    """A peça medida onde ela vive: no motor que ela usa."""

    def test_a_razao_acende_o_cinza_e_veste_o_aria(self, na_tela: dict) -> None:
        do_produto = na_tela["do_produto"]["com_razao"]
        for nome, visto in na_tela["com-razao"]["botoes"].items():
            assert visto is not None, f"{nome} sumiu da página"
            assert visto["apagado"] is True, (nome, visto)
            assert visto["aria"] == "true", (nome, visto)
            assert visto["razao"] == do_produto[f"{nome}{a09.SUFIXO_DA_RAZAO}"]

    def test_o_interrogacao_aparece_com_a_razao(self, na_tela: dict) -> None:
        for nome, visto in na_tela["com-razao"]["botoes"].items():
            assert visto["ajuda_visivel"] is True, (nome, visto)

    def test_a_razao_vazia_apaga_o_cinza_de_volta(self, na_tela: dict) -> None:
        """A metade que faz a peça ser um ESTADO e não um carimbo."""
        for nome, visto in na_tela["sem-razao"]["botoes"].items():
            assert visto["apagado"] is False, (nome, visto)
            assert visto["aria"] == "false", (nome, visto)
            assert visto["ajuda_visivel"] is False, (nome, visto)

    def test_as_duas_colunas_irmas_acabam_no_mesmo_y_nos_dois_estados(
            self, na_tela: dict) -> None:
        """A lei desta aba: colunas irmãs acabam no mesmo `y`."""
        for quando in ("com-razao", "sem-razao"):
            visto = na_tela[quando]
            desencontro = abs(visto["fim_do_estado"] - visto["fim_da_acao"])
            assert desencontro <= 2, (
                f"{quando}: a coluna de estado acaba em y={visto['fim_do_estado']} "
                f"e a de ações em y={visto['fim_da_acao']} — {desencontro}px de "
                "desencontro. Duas colunas irmãs desta aba acabam no mesmo y.")

    def test_o_interrogacao_nao_faz_a_faixa_crescer(self, na_tela: dict) -> None:
        """O motivo do invólucro `.acao`, e ele é de ALTURA."""
        com = na_tela["com-razao"]["altura_da_faixa"]
        sem = na_tela["sem-razao"]["altura_da_faixa"]
        assert com == sem, (
            f"a faixa mede {com}px com os três `?` à vista e {sem}px sem eles — "
            f"{abs(com - sem)}px que o `?` cobrou de altura. Ele tem de ficar "
            "na LINHA do botão (`.acao`), não numa fileira própria.")

    def test_a_aba_nao_passa_a_rolar_por_dentro_com_os_tres_cinzas(
            self, na_tela: dict) -> None:
        """O preço final de a faixa crescer, e é o que ela VÊ."""
        for quando in ("com-razao", "sem-razao"):
            assert na_tela[quando]["rola_por_dentro"] == 0, (
                f"{quando}: o miolo rola {na_tela[quando]['rola_por_dentro']}px "
                "por dentro — foi assim que a aba escondeu 93px em 28/08.")

    def test_o_botao_encolhe_em_vez_de_estourar_a_coluna(
            self, na_tela: dict) -> None:
        """Com o `?` à vista o botão perde largura; nenhum dos dois transborda."""
        for nome, com in na_tela["com-razao"]["botoes"].items():
            sem = na_tela["sem-razao"]["botoes"][nome]
            assert com["largura"] < sem["largura"], (nome, com, sem)

    def test_o_botao_diz_que_esta_trabalhando(self, na_tela: dict) -> None:
        import aba09

        voando = na_tela["no-meio-do-voo"]["reaplicar"]
        assert voando["em_voo"] is True, voando
        assert voando["rotulo"] == aba09.EM_VOO_ATUALIZAR, voando

    def test_e_volta_inteiro_quando_o_gesto_pousa(self, na_tela: dict) -> None:
        import aba09

        pousado = na_tela["depois-do-pouso"]["reaplicar"]
        assert pousado["em_voo"] is False, pousado
        assert pousado["rotulo"] == aba09.ROTULO_ATUALIZAR, pousado

    def test_o_gesto_que_da_certo_pisca_no_botao(self, na_tela: dict) -> None:
        """A linha **L323** do CSV, medida nesta aba — e não afirmada."""
        pousado = na_tela["depois-do-pouso"]["reaplicar"]
        assert pousado and pousado["deu_certo"], (
            "o gesto voltou sem levantar e a tela não disse nada — é o buraco "
            f"da L323, e agora quem o fecha é a piscada da `03-Q4`: {pousado}")
        recados = na_tela["depois-do-pouso"]["recados"]
        assert not recados, (
            "o gesto não trouxe notícia e a tela falou mesmo assim — a palavra "
            f"nova é o que a decisão dela tirou: {recados}")

    def test_a_peca_nao_mexe_no_numero_de_enderecos_da_pagina(
            self, na_tela: dict) -> None:
        """O contador é O instrumento com que esta casa prova que um endereço"""
        assert (na_tela["com-razao"]["enderecos"]
                == na_tela["sem-razao"]["enderecos"]
                == na_tela["depois-do-pouso"]["enderecos"])
