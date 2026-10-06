"""Os portões lentos ficam rápidos por dentro — e o veredito continua o mesmo.

``OS-PORTOES-LENTOS-FICAM-RAPIDOS-POR-DENTRO-01`` (06/10/2026, leva 1.6). Esta régua
guarda as duas metades da cura:

* **Os três portões de página não dependem da rede.** As páginas pedem a fonte ao
  Google; com a rede fora o ``goto`` esperava o ``load`` por 30 s e REPROVAVA. O ponto
  comum ``scripts/chrome_sem_rede.py`` recusa o que não é local. A régua prova (1) que
  a página abre depressa com uma rede que NUNCA responde, (2) que o instrumento morde
  (sem o bloqueio, a mesma rede pendura de verdade), (3) que o veredito de página
  aberta sem rede é o de página aberta com a rede respondendo, e (4) que os três
  portões passam por esse ponto comum.
* **Os caches dos outros três não adoçam o veredito.** A árvore compartilhada por
  conteúdo nunca vira alvo de poda, e a árvore de prefixos da acentuação casa o que a
  alternância plana casava.

O que cada cura de tempo tirou do caminho está nos testes de cada portão (as mordidas
plantadas continuam lá, e continuam reprovando).
"""
from __future__ import annotations

import importlib.util
import pathlib
import re
import sys
import time
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _caminho in (str(RAIZ / "src"), str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface"),
                 str(RAIZ / "scripts")):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import chrome_sem_rede  # o ponto comum dos portões de página

CHROME = pathlib.Path(chrome_sem_rede.CHROME)
EXTERNO = "https://exemplo.invalid/fonte.css"

_PAGINA_COM_FONTE_DE_FORA = f"""<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="{EXTERNO}">
<style>#caixa{{width:200px;height:40px;background:#ccc}}</style></head>
<body><div id="caixa">oi</div></body></html>"""

_LARGURA_DA_CAIXA = "document.getElementById('caixa').getBoundingClientRect().width"

pytestmark = pytest.mark.skipif(
    not CHROME.exists(), reason="sem o Chrome do sistema — a régua não tem motor")


def _playwright() -> Any:
    return pytest.importorskip("playwright.sync_api")


def _modulo_do_script(nome: str) -> Any:
    spec = importlib.util.spec_from_file_location(nome, RAIZ / "scripts" / f"{nome}.py")
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def pagina_com_fonte_de_fora(tmp_path: pathlib.Path) -> pathlib.Path:
    arquivo = tmp_path / "pagina.html"
    arquivo.write_text(_PAGINA_COM_FONTE_DE_FORA, encoding="utf-8")
    return arquivo


def _rede_que_nunca_responde(contexto: Any) -> list[str]:
    """Uma rede FORA de verdade: o pedido externo fica pendurado, sem resposta nem erro."""
    pedidos: list[str] = []

    def pendura(rota: Any) -> None:
        url = rota.request.url
        if chrome_sem_rede.e_local(url):
            rota.continue_()
            return
        pedidos.append(url)  # nem continue_, nem abort, nem fulfill: o pedido não termina

    contexto.route("**/*", pendura)
    return pedidos


class TestAPaginaNaoPedeARede:
    def test_com_a_rede_fora_a_pagina_abre_depressa_e_o_externo_e_recusado(
        self, pagina_com_fonte_de_fora: pathlib.Path
    ) -> None:
        with _playwright().sync_playwright() as pw:
            navegador = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
            try:
                contexto = navegador.new_context()
                pendurados = _rede_que_nunca_responde(contexto)
                inicio = time.monotonic()
                pagina, recusadas = chrome_sem_rede.abrir_sem_rede(
                    contexto, pagina_com_fonte_de_fora.as_uri(),
                    largura=800, altura=600, espera_ms=8_000)
                gasto = time.monotonic() - inicio
                largura = pagina.evaluate(_LARGURA_DA_CAIXA)
            finally:
                navegador.close()
        assert recusadas == [EXTERNO], (
            f"o recurso externo da página não foi RECUSADO pelo bloqueio: {recusadas}")
        assert pendurados == [], (
            f"o pedido externo chegou à rede ({pendurados}): o bloqueio não o segurou "
            "antes de sair da máquina")
        assert largura == 200, f"a página não foi medida inteira: {largura}"
        assert gasto < 5, (
            f"a página levou {gasto:.1f} s com uma rede que nunca responde: o portão "
            "voltou a esperar a rede para medir a página")

    def test_sem_o_bloqueio_a_mesma_rede_pendura_de_verdade(
        self, pagina_com_fonte_de_fora: pathlib.Path
    ) -> None:
        """A MORDIDA DO INSTRUMENTO: arrancado o bloqueio, a rede simulada volta a esperar."""
        playwright = _playwright()
        with playwright.sync_playwright() as pw:
            navegador = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
            try:
                contexto = navegador.new_context()
                pendurados = _rede_que_nunca_responde(contexto)
                with pytest.raises(playwright.TimeoutError):
                    chrome_sem_rede.abrir_sem_rede(
                        contexto, pagina_com_fonte_de_fora.as_uri(),
                        largura=800, altura=600, bloquear=False, espera_ms=1_500)
            finally:
                navegador.close()
        assert pendurados == [EXTERNO], (
            "a rede simulada não chegou a ser pedida: o instrumento não mede nada, "
            "porque nada ficaria pendurado nem COM o bloqueio fora")

    def test_o_veredito_da_pagina_real_e_o_mesmo_com_a_rede_recusada_e_com_ela_respondendo(
        self, tmp_path: pathlib.Path
    ) -> None:
        """A rede bloqueada não muda o que o portão lê da página."""
        a01 = pytest.importorskip("tests.unit.test_a_01_jogar_nao_oferece_gesto_em_lugar_vazio")
        arquivo = a01._gerar(tmp_path)
        with _playwright().sync_playwright() as pw:
            navegador = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
            try:
                bloqueada, recusadas = chrome_sem_rede.abrir_sem_rede(
                    navegador, arquivo.as_uri(), largura=1280, altura=900)
                lido_sem_rede = bloqueada.evaluate(a01.O_QUE_O_NAVEGADOR_DESENHA)

                contexto = navegador.new_context(viewport={"width": 1280, "height": 900})
                respondendo = contexto.new_page()
                respondendo.route(
                    "**/*",
                    lambda rota: rota.fulfill(status=200, content_type="text/css", body="")
                    if not chrome_sem_rede.e_local(rota.request.url) else rota.continue_())
                respondendo.goto(arquivo.as_uri(), wait_until="load")
                respondendo.evaluate(chrome_sem_rede._ESPERA_O_DESENHO_ASSENTAR)
                lido_com_rede = respondendo.evaluate(a01.O_QUE_O_NAVEGADOR_DESENHA)
            finally:
                navegador.close()
        assert recusadas, "a página real deixou de pedir recurso externo: o caso desta régua mudou"
        assert lido_sem_rede == lido_com_rede, (
            "o veredito da página muda com a rede recusada: o bloqueio alterou o que o "
            "portão mede, e deixou de ser a mesma pergunta")


class TestOsTresPortoesDePaginaPassamPeloPontoComum:
    """Cada um abre a página pelo `abrir_sem_rede`, com o bloqueio ligado."""

    @pytest.fixture
    def chamadas(self, monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
        registro: list[dict[str, Any]] = []
        original = chrome_sem_rede.abrir_sem_rede

        def espia(navegador: Any, uri: str, **opcoes: Any) -> Any:
            pagina, recusadas = original(navegador, uri, **opcoes)
            registro.append({"uri": uri, "bloquear": opcoes.get("bloquear", True),
                             "recusadas": list(recusadas)})
            return pagina, recusadas

        monkeypatch.setattr(chrome_sem_rede, "abrir_sem_rede", espia)
        return registro

    def test_gesto_em_lugar_vazio_e_gesto_onde_deve_04(
        self, chamadas: list[dict[str, Any]], tmp_path: pathlib.Path
    ) -> None:
        a01 = pytest.importorskip("tests.unit.test_a_01_jogar_nao_oferece_gesto_em_lugar_vazio")
        a04 = pytest.importorskip("tests.unit.test_a_04_iluminacao_o_gesto_esta_onde_deve")
        (tmp_path / "a01").mkdir()
        (tmp_path / "a04").mkdir()
        a01.abrir_e_medir(a01._gerar(tmp_path / "a01"))
        a04.abrir_e_medir(a04._gerar(tmp_path / "a04"))
        assert [c["uri"].rsplit("/", 1)[-1] for c in chamadas] == [
            "01-jogar.html", "04-iluminacao.html"], chamadas
        assert all(c["bloquear"] for c in chamadas), chamadas
        assert all(c["recusadas"] for c in chamadas), (
            "uma página real pede a fonte de fora e o bloqueio TEM de recusá-la: "
            f"{chamadas}")

    def test_altura_do_cartao(self, chamadas: list[dict[str, Any]]) -> None:
        altura = _modulo_do_script("check_a_altura_do_cartao")
        pagina = altura._onde.pagina("02-controles.html")
        if not pagina.exists():  # pragma: no cover — a bancada se gera com o gerador
            pytest.skip("a página da aba 02 não está na bancada desta árvore")
        altura.medir(pagina, altura.LARGURAS)
        assert [c["uri"].rsplit("/", 1)[-1] for c in chamadas] == (
            ["02-controles.html"] * len(altura.LARGURAS)), chamadas
        assert all(c["bloquear"] and c["recusadas"] for c in chamadas), chamadas


class TestOsCachesNaoAdocamOVeredito:
    def test_a_poda_da_ponte_nao_suja_a_arvore_compartilhada(self) -> None:
        """A árvore lida por conteúdo é só de leitura: podar a ponte não pode alterá-la."""
        import ast

        casa = pytest.importorskip("tests.unit.portao_a_casa_sabe_e_o_produto_nao_faz")
        piloto = RAIZ / casa._PILOTO_DA_INTERFACE_NOVA
        antes = ast.dump(casa._arvore(piloto))
        podadas = dict(casa._fontes_externas(RAIZ, podar_a_bancada=True))
        assert casa._PASTA_DA_PONTE + "/hefesto_vivo.py" in podadas, (
            "instrumento inválido: a poda nem chegou ao piloto")
        depois = ast.dump(casa._arvore(piloto))
        assert antes == depois, (
            "a poda da ponte alterou a árvore COMPARTILHADA do piloto: a varredura "
            "seguinte lê um piloto já podado e o portão adoça o próprio veredito")
        assert ast.dump(podadas[casa._PASTA_DA_PONTE + "/hefesto_vivo.py"]) != antes, (
            "a árvore podada saiu igual à inteira: a poda não podou nada, e esta "
            "régua não mede a cópia")

    def test_a_arvore_de_prefixos_casa_o_que_a_alternancia_plana_casava(self) -> None:
        """A cura de tempo da acentuação não pode mudar quem é acusado."""
        acentuacao = _modulo_do_script("validar-acentuacao")
        palavras = sorted(acentuacao._CORRECOES, key=len, reverse=True)
        borda_ini, borda_fim = r"(?<![A-Za-z0-9_])", r"(?![A-Za-z0-9_])"
        plana = re.compile(
            borda_ini + "(?:" + "|".join(re.escape(p) for p in palavras) + ")" + borda_fim,
            re.IGNORECASE,
        )
        arvore = acentuacao._alternancia()
        divergentes = []
        for palavra in palavras:
            for texto in (palavra, palavra.upper(), palavra.capitalize(), f"x {palavra}, y",
                          f"{palavra}a", f"a{palavra}", f"{palavra}_x", f"{palavra}-x",
                          f"{palavra} {palavra[:-1]} {palavra}s"):
                esperado = [(m.start(), m.group()) for m in plana.finditer(texto)]
                lido = [(m.start(), m.group()) for m in arvore.finditer(texto)]
                if esperado != lido:
                    divergentes.append((texto, esperado, lido))
        assert not divergentes, (
            f"a árvore de prefixos diverge da alternância plana: {divergentes[:5]}")
        assert len(palavras) > 100, "instrumento inválido: o dicionário encolheu demais"
