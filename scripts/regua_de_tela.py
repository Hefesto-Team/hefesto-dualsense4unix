#!/usr/bin/env python3
"""régua_de_tela — dirigir a interface nova POR DENTRO, e perguntar a ela."""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import pathlib
import subprocess
import sys
import time
from collections.abc import Callable
from typing import Any, NamedTuple

_RAIZ_TELA = str(pathlib.Path(__file__).resolve().parents[1] / 'src')
if _RAIZ_TELA not in sys.path:
    sys.path.insert(0, _RAIZ_TELA)
from hefesto_dualsense4unix.utils.tela_de_mentira import (
    garantir_tela_de_mentira,
)

garantir_tela_de_mentira()

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("WebKit2", "4.1")

from gi.repository import GLib, Gtk, WebKit2

O_QUE_ELE_NAO_FAZ = (
    "não clica por COORDENADA nem move o ponteiro: `el.click()` percorre o mesmo "
    "caminho de eventos do clique do rato, mas :hover, drag, roda do rato e "
    "foco por teclado ficam de fora — para `:hover` o instrumento certo é o "
    "olhar.py (Playwright) sobre o mockup",
    "não vê o que o WebKit PINTOU: `medir` lê a geometria do DOM, não os pixels. "
    "Cor errada por CSS mal calculado passa; use `foto()` e o olho dela",
    "não alcança widget GTK — só o que está DENTRO do WebView. A tira, a barra "
    "de título e qualquer diálogo GTK ficam fora do alcance",
    "não roda sem servidor gráfico: `Gtk.OffscreenWindow` ainda precisa de um "
    "GDK display. No CI sem Xvfb a régua PULA, e um pulo não é um verde",
    "não traz o mockup consigo: `layout/` é .gitignore, então numa árvore "
    "sem ele a régua PULA nomeando onde procurou",
    "não conhece aba nenhuma: o vocabulário é de DOM. Quem sabe o que uma aba "
    "promete é a régua daquela aba, não este arquivo",
    "não detecta página PELA METADE: medido em 29/08, uma leitura caiu no exato "
    "instante em que outra leva regerava o `02-controles.html` e a tela veio "
    "vazia — `readyState` era 'complete' e o título estava certo, porque um "
    "arquivo truncado carrega inteiro. A defesa não é do instrumento, é da "
    "régua: toda régua tem de exigir um PISO (`contar(...) == 4`), porque "
    "`contar` devolvendo 0 é resposta legítima e só uma asserção a torna "
    "reprovação",
    "não sente o GERADOR, só a página GERADA. MEDIDO em 29/08: arrancado o "
    "`transform:translate(-50%,-50%)` do `.stick .p` no `aba02.py`, os 17 "
    "testes da aba Controles ficaram VERDES; o mesmo arranque no "
    "`02-controles.html` deu 3 vermelhos com -43,50/+52,50 px. O CSS do "
    "gerador só chega à tela depois do `regerar.py`. O que a remontagem do "
    "piloto devolve é a MARCAÇÃO, não a folha de estilo — quem mexe em `aba*.py` "
    "regera antes de medir, ou mede o arquivo de ontem",
)

O_MANUAL = "docs/method/2026-08-29-A-REGUA-DE-TELA-como-se-prova-a-interface.md"


class ErroDeRegua(AssertionError):
    """Raiz de tudo que esta régua reprova."""


class SemElemento(ErroDeRegua):
    """O seletor não casou (ou casou menos que o índice pedido)."""


class TelaMuda(ErroDeRegua):
    """A tela foi tocada e não respondeu — o defeito do botão sem ouvinte."""


class Impaciencia(ErroDeRegua):
    """A consequência não chegou dentro do prazo."""


class ErroDeJS(ErroDeRegua):
    """O JavaScript levantou, ou devolveu o que não se pode ler."""


class CargaFalhou(ErroDeRegua):
    """A página não é a página — e quem diz isso é ela mesma."""


class MockupAusente(ErroDeRegua):
    """O alvo não está nesta árvore. Nomeia onde se procurou."""


class Caixa(NamedTuple):
    """A geometria de um elemento, em pixels de viewport."""

    x: float
    y: float
    largura: float
    altura: float

    @property
    def centro(self) -> tuple[float, float]:
        return (self.x + self.largura / 2, self.y + self.altura / 2)

    def __str__(self) -> str:  # pragma: no cover — conforto de relatório
        return (
            f"x={self.x:g} y={self.y:g} {self.largura:g}x{self.altura:g} "
            f"(centro {self.centro[0]:g},{self.centro[1]:g})"
        )


def _worktrees_do_git(daqui: pathlib.Path) -> list[pathlib.Path]:
    """Toda árvore que o `git` declara — a principal e as de trabalho."""
    try:
        saida = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=daqui,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover
        return []
    if saida.returncode != 0:
        return []
    return [
        pathlib.Path(linha[len("worktree ") :].strip())
        for linha in saida.stdout.splitlines()
        if linha.startswith("worktree ")
    ]


def raizes_candidatas() -> list[pathlib.Path]:
    """As raízes onde o `layout/` pode estar, em ordem de preferência."""
    fora: list[pathlib.Path] = []

    def por(caminho: pathlib.Path | None) -> None:
        if caminho is None:
            return
        caminho = caminho.resolve()
        if caminho not in fora:
            fora.append(caminho)

    variavel = os.environ.get("HEFESTO_NOVO_LAYOUT")
    if variavel:
        alvo = pathlib.Path(variavel)
        por(alvo.parent if alvo.name == "layout" else alvo)
        return fora
    aqui = pathlib.Path(__file__).resolve().parent.parent
    por(aqui)
    for arvore in _worktrees_do_git(aqui):
        por(arvore)
    return fora


PASTAS_DAS_ABAS = ("mockup", "src/hefesto_dualsense4unix/interface/paginas")


def _paginas_da_raiz(raiz: pathlib.Path) -> list[pathlib.Path]:
    """As páginas de aba de uma raiz, em todas as casas que ela tiver."""
    fora: list[pathlib.Path] = []
    for pasta in PASTAS_DAS_ABAS:
        alvo = raiz / pasta
        if alvo.is_dir():
            fora.extend(sorted(alvo.glob("[0-9][0-9]-*.html")))
    return fora


def abas_conhecidas() -> list[pathlib.Path]:
    """Uma linha por aba — a cópia mais nova de cada uma, venha de onde vier."""
    nomes: set[str] = set()
    for raiz in raizes_candidatas():
        for pagina in _paginas_da_raiz(raiz):
            nomes.add(pagina.stem)
    return [achar_a_aba(nome, avisar=False) for nome in sorted(nomes)]


def candidatas_da_aba(nome: str) -> list[pathlib.Path]:
    """TODA cópia da aba, em todas as raízes, da mais nova para a mais velha."""
    pedido = nome.removesuffix(".html").strip().lower()
    achadas: list[tuple[int, float, pathlib.Path]] = []
    for ordem, raiz in enumerate(raizes_candidatas()):
        for pagina in _paginas_da_raiz(raiz):
            miolo = pagina.stem.lower()
            if pedido in (miolo, miolo.split("-", 1)[0], miolo.split("-", 1)[1]):
                achadas.append((ordem, -pagina.stat().st_mtime, pagina))
    return [p for _, _, p in sorted(achadas)]


def achar_a_aba(nome: str, *, avisar: bool = True) -> pathlib.Path:
    """`"02"`, `"controles"` ou `"02-controles.html"` → o arquivo."""
    alvo = pathlib.Path(nome)
    if alvo.is_file():
        return alvo.resolve()
    achadas = candidatas_da_aba(nome)
    if not achadas:
        raise MockupAusente(
            f"não achei a aba {nome!r}. `layout/` é .gitignore:108 e não "
            "viaja em worktree — aponte com HEFESTO_NOVO_LAYOUT. Procurei em: "
            + " · ".join(str(r / "layout") for r in raizes_candidatas())
        )
    if avisar and len(achadas) > 1:
        print(
            f"régua_de_tela: {len(achadas)} cópias de {nome!r}; uso a mais nova. "
            + " · ".join(
                f"{p} ({time.strftime('%d/%m %H:%M', time.localtime(p.stat().st_mtime))}"
                f", {p.stat().st_size} B)"
                for p in achadas
            ),
            file=sys.stderr,
        )
    return achadas[0]


AJUDANTE = r"""
window.__REGUA = (function(){
  function lista(sel){
    try { return Array.from(document.querySelectorAll(sel)); }
    catch(e){ return {erro:'seletor inválido: ' + e.message}; }
  }
  function pega(sel, i){
    var l = lista(sel);
    if(!Array.isArray(l)) return {achou:-1, erro:l.erro};
    var el = (i >= 0 && i < l.length) ? l[i] : null;
    return {achou:l.length, indice:i, el:el};
  }
  function caixa(el){
    var r = el.getBoundingClientRect();
    var a = function(v){ return Math.round(v*100)/100; };
    return {x:a(r.x), y:a(r.y), largura:a(r.width), altura:a(r.height)};
  }
  function sai(p, valor){ p.valor = valor; delete p.el; return p; }
  function classe(el){ return el.getAttribute('class') || ''; }
  return {
    contar: function(sel){
      var l = lista(sel);
      return Array.isArray(l) ? {achou:l.length, valor:l.length}
                              : {achou:-1, erro:l.erro};
    },
    ler: function(sel,i){ var p=pega(sel,i); return p.el ? sai(p, p.el.textContent) : p; },
    medir: function(sel,i){
      var p = pega(sel,i); if(!p.el) return p;
      // NÃO ROLA NADA. `scrollIntoViewIfNeeded` cega toda medição feita depois
      // (foi assim que um portão deu verde sobre uma linha fora da caixa), então
      // a rolagem de agora vai JUNTO da resposta, para quem lê poder desconfiar.
      p.rolagem = document.scrollingElement ? document.scrollingElement.scrollTop : 0;
      return sai(p, caixa(p.el));
    },
    atributo: function(sel,i,nome){
      var p = pega(sel,i); return p.el ? sai(p, p.el.getAttribute(nome)) : p;
    },
    estilo: function(sel,i,prop){
      var p = pega(sel,i); return p.el ? sai(p, getComputedStyle(p.el)[prop]) : p;
    },
    classes: function(sel,i){
      var p = pega(sel,i);
      return p.el ? sai(p, classe(p.el).split(/\s+/).filter(Boolean)) : p;
    },
    travado: function(sel,i){
      var p = pega(sel,i); if(!p.el) return p;
      return sai(p, p.el.disabled === true || p.el.getAttribute('aria-disabled') === 'true');
    },
    clicar: function(sel,i){
      var p = pega(sel,i); if(!p.el) return p;
      var el = p.el;
      // O RETRATO DO ALVO VAI JUNTO, sempre. Quando o clique não produz eco, é
      // ele que diz por quê: travado, invisível, ou de tamanho zero.
      p.travado = el.disabled === true;
      p.visivel = el.getClientRects().length > 0;
      p.caixa = caixa(el);
      p.alvo = {tag: el.tagName.toLowerCase(), classe: classe(el),
                texto: (el.textContent || '').trim().slice(0, 48)};
      try { el.click(); }
      catch(e){ p.erro = 'o clique levantou: ' + e.message; return sai(p, false); }
      return sai(p, true);
    },
    verdade: function(expr){
      try { return {achou:1, valor: !!eval(expr)}; }
      catch(e){ return {achou:-1, erro:'a pergunta levantou: ' + e.message}; }
    }
  };
})(); 'REGUA-PRONTA'
"""


class Recado(NamedTuple):
    """Uma mensagem que a PÁGINA mandou ao Python, com a hora."""

    canal: str
    bruto: str
    objeto: Any
    aos: float

    @property
    def gesto(self) -> str:
        return str(self.objeto.get("gesto") or "") if isinstance(self.objeto, dict) else ""


class Tela:
    """Uma aba aberta num WebView oculto, e o vocabulário para interrogá-la."""

    def __init__(
        self,
        pagina: pathlib.Path,
        *,
        titulo_esperado: str | None = None,
        oculta: bool = True,
        largura: int = 1180,
        altura: int = 900,
        canais: tuple[str, ...] = ("hefesto",),
        prazo: float = 20.0,
    ) -> None:
        self.pagina = pagina
        self.titulo_esperado = titulo_esperado
        self.canais = canais
        self._recados: list[Recado] = []
        self._falhas_de_carga: list[str] = []
        self._t0 = time.monotonic()
        self._ajudante_posto = False
        self._contexto = GLib.MainContext.default()

        ucm = WebKit2.UserContentManager()
        for canal in canais:
            ucm.register_script_message_handler(canal)
            ucm.connect(
                f"script-message-received::{canal}",
                lambda _ucm, resultado, canal=canal: self._da_tela(canal, resultado),
            )
        self.view = WebKit2.WebView.new_with_user_content_manager(ucm)
        self.view.connect("load-changed", self._carregou)
        self.view.connect("load-failed", self._falhou)

        if oculta:
            self.janela: Any = Gtk.OffscreenWindow()
        else:  # pragma: no cover — ela tem UMA tela; o padrão é oculta
            self.janela = Gtk.Window(title=f"régua — {pagina.name}")
            self.janela.connect("destroy", Gtk.main_quit)
        self.janela.set_default_size(largura, altura)
        self.janela.add(self.view)
        self.janela.show_all()
        self.view.load_uri(pagina.as_uri())
        self._esperar_a_pagina(prazo)

    @classmethod
    def abrir(cls, aba: str, **kwargs: Any) -> Tela:
        """`Tela.abrir("02")` — o atalho, com o alvo resolvido pelo nome."""
        return cls(achar_a_aba(aba), **kwargs)

    def __enter__(self) -> Tela:
        return self

    def __exit__(self, *_erro: Any) -> None:
        self.fechar()

    def fechar(self) -> None:
        with contextlib.suppress(Exception):  # pragma: no cover
            self.janela.destroy()
        self._bombear(lambda: False, 0.05)

    def _bombear(self, pronto: Callable[[], bool], prazo: float) -> bool:
        """Roda o laço GLib até `pronto()` ou até o prazo. Devolve se deu."""
        fim = time.monotonic() + prazo
        while True:
            while self._contexto.pending():
                self._contexto.iteration(False)
            if pronto():
                return True
            if time.monotonic() >= fim:
                return False
            time.sleep(0.004)

    def avancar(self, segundos: float) -> Tela:
        """Deixa o tempo passar com o laço vivo. É como se espera de propósito."""
        self._bombear(lambda: False, segundos)
        return self

    def aos(self, segundos: float, funcao: Callable[[], Any]) -> Tela:
        """Marca uma ação para daqui a N segundos — o roteiro no tempo."""
        GLib.timeout_add(int(segundos * 1000), lambda: (funcao(), False)[1])
        return self

    @property
    def relogio(self) -> float:
        """Segundos desde que esta tela abriu."""
        return time.monotonic() - self._t0

    def _falhou(self, _view: Any, _evento: Any, uri: str, erro: Any) -> bool:
        self._falhas_de_carga.append(f"{uri}: {erro}")
        return False

    def _carregou(self, _view: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            self._ajudante_posto = False

    def _esperar_a_pagina(self, prazo: float) -> None:
        """Quem diz que a carga deu certo é a PÁGINA, não o evento nem o URI."""
        visto: dict[str, Any] = {}

        def pronta() -> bool:
            try:
                estado = self._cru("[document.readyState, document.title]")
            except ErroDeJS:
                return False
            visto["estado"], visto["titulo"] = estado
            if estado[0] != "complete":
                return False
            if self.titulo_esperado is None:
                return True
            return self.titulo_esperado in (estado[1] or "")

        if not self._bombear(pronta, prazo):
            raise CargaFalhou(
                f"a página não confirmou em {prazo:g}s. alvo={self.pagina} · "
                f"uri de agora={self.view.get_uri()!r} · readyState="
                f"{visto.get('estado', ['?'])[0]!r} · título={visto.get('titulo')!r}"
                + (
                    " · load-failed: " + " | ".join(self._falhas_de_carga)
                    if self._falhas_de_carga
                    else " · nenhum load-failed (host recusando não dispara)"
                )
            )
        self._por_o_ajudante()

    def _por_o_ajudante(self) -> None:
        if self._ajudante_posto:
            return
        if self._cru("typeof window.__REGUA") != "object":
            self.executar(AJUDANTE)
        self._ajudante_posto = True

    def _cru(self, js: str, prazo: float = 8.0) -> Any:
        """Avalia `js` e devolve o valor, passando por JSON."""
        caixa: dict[str, Any] = {}

        def respondeu(view: Any, res: Any, _u: Any = None) -> None:
            try:
                caixa["v"] = view.evaluate_javascript_finish(res).to_string()
            except Exception as erro:
                caixa["erro"] = erro

        self.view.evaluate_javascript(
            f"JSON.stringify({js})", -1, None, None, None, respondeu, None
        )
        if not self._bombear(lambda: bool(caixa), prazo):
            raise ErroDeJS(f"a página não respondeu em {prazo:g}s: {js[:120]}")
        if "erro" in caixa:
            raise ErroDeJS(f"{caixa['erro']} — ao avaliar: {js[:200]}")
        try:
            return json.loads(caixa["v"])
        except (TypeError, ValueError) as erro:
            raise ErroDeJS(
                f"resposta ilegível ({caixa['v']!r}) ao avaliar: {js[:200]} "
                f"[{erro}]"
            ) from erro

    def executar(self, script: str, prazo: float = 8.0) -> Any:
        """Roda JavaScript solto e REPROVA se ele levantar."""
        caixa: dict[str, Any] = {}

        def respondeu(view: Any, res: Any, _u: Any = None) -> None:
            try:
                valor = view.evaluate_javascript_finish(res)
                caixa["v"] = valor.to_string() if valor is not None else None
            except Exception as erro:
                caixa["erro"] = erro

        self.view.evaluate_javascript(script, -1, None, None, None, respondeu, None)
        if not self._bombear(lambda: bool(caixa), prazo):
            raise ErroDeJS(f"o script não respondeu em {prazo:g}s: {script[:120]}")
        if "erro" in caixa:
            raise ErroDeJS(f"{caixa['erro']} — ao rodar: {script[:200]}")
        return caixa["v"]

    def _perguntar(self, funcao: str, *args: Any) -> dict[str, Any]:
        self._por_o_ajudante()
        crus = ", ".join(json.dumps(a) for a in args)
        resposta = self._cru(f"window.__REGUA.{funcao}({crus})")
        if not isinstance(resposta, dict):  # pragma: no cover — defesa
            raise ErroDeJS(f"__REGUA.{funcao} devolveu {resposta!r}")
        if resposta.get("erro"):
            raise ErroDeJS(f"__REGUA.{funcao}({crus}): {resposta['erro']}")
        return resposta

    def _exigir(self, funcao: str, seletor: str, indice: int, *extra: Any) -> dict[str, Any]:
        """Pergunta e REPROVA quando o seletor não casou. Nunca devolve silêncio."""
        resposta = self._perguntar(funcao, seletor, indice, *extra)
        achou = int(resposta.get("achou", 0))
        if achou <= indice:
            raise SemElemento(
                f"{funcao}({seletor!r}, índice {indice}): o seletor casou {achou} "
                f"elemento(s) na aba {self.pagina.name}. Zero não é 'nada mudou' — "
                "é a régua olhando para um endereço que não existe."
            )
        return resposta

    def contar(self, seletor: str) -> int:
        """Quantos casam. Aqui `0` é resposta legítima, e não erro."""
        return int(self._perguntar("contar", seletor)["valor"])

    def existe(self, seletor: str) -> bool:
        return self.contar(seletor) > 0

    def ler(self, seletor: str, indice: int = 0) -> str:
        """O `textContent`. Reprova se o seletor não casar."""
        return str(self._exigir("ler", seletor, indice)["valor"])

    def medir(self, seletor: str, indice: int = 0) -> Caixa:
        """A geometria, em pixels de viewport. NÃO rola a página para medir."""
        v = self._exigir("medir", seletor, indice)["valor"]
        return Caixa(v["x"], v["y"], v["largura"], v["altura"])

    def atributo(self, seletor: str, nome: str, indice: int = 0) -> str | None:
        valor = self._exigir("atributo", seletor, indice, nome)["valor"]
        return None if valor is None else str(valor)

    def estilo(self, seletor: str, propriedade: str, indice: int = 0) -> str:
        """O estilo COMPUTADO (o que vale), não o que está escrito no `style`."""
        return str(self._exigir("estilo", seletor, indice, propriedade)["valor"])

    def classes(self, seletor: str, indice: int = 0) -> list[str]:
        return list(self._exigir("classes", seletor, indice)["valor"])

    def tem_classe(self, seletor: str, classe: str, indice: int = 0) -> bool:
        return classe in self.classes(seletor, indice)

    def travado(self, seletor: str, indice: int = 0) -> bool:
        """`disabled` (ou `aria-disabled`) — o "não dá" dito no lugar certo."""
        return bool(self._exigir("travado", seletor, indice)["valor"])

    def clicar(self, seletor: str, indice: int = 0) -> dict[str, Any]:
        """Clica e devolve o RETRATO do alvo (travado, visível, caixa, texto)."""
        return self._exigir("clicar", seletor, indice)

    def esperar_ate(
        self,
        pergunta: str | Callable[[], bool],
        *,
        prazo: float = 5.0,
        motivo: str = "",
    ) -> float:
        """Bombeia o laço até a pergunta virar verdade. REPROVA no estouro."""
        comeco = time.monotonic()
        ultimo: dict[str, Any] = {}

        def sonda() -> bool:
            if callable(pergunta):
                try:
                    ultimo["v"] = bool(pergunta())
                except SemElemento as erro:
                    ultimo["v"] = False
                    ultimo["nota"] = str(erro)
                    return False
            else:
                ultimo["v"] = bool(self._perguntar("verdade", pergunta)["valor"])
            return bool(ultimo["v"])

        if self._bombear(sonda, prazo):
            return time.monotonic() - comeco
        alvo = pergunta if isinstance(pergunta, str) else getattr(
            pergunta, "__doc__", None
        ) or repr(pergunta)
        raise Impaciencia(
            f"{prazo:g}s e não aconteceu: {motivo or alvo}"
            + (f" · última nota: {ultimo['nota']}" if "nota" in ultimo else "")
        )

    def _da_tela(self, canal: str, resultado: Any) -> None:
        valor = resultado.get_js_value() if hasattr(resultado, "get_js_value") else resultado
        bruto = valor.to_string()
        try:
            objeto = json.loads(bruto)
        except (TypeError, ValueError):
            objeto = None
        self._recados.append(Recado(canal, bruto, objeto, self.relogio))

    def recados(self, gesto: str | None = None) -> list[Recado]:
        """Tudo que a página mandou, na ordem — opcionalmente de um gesto só."""
        if gesto is None:
            return list(self._recados)
        return [r for r in self._recados if r.gesto == gesto]

    def limpar_recados(self) -> None:
        self._recados.clear()

    def clicar_e_ouvir(
        self,
        seletor: str,
        *,
        esperados: int = 1,
        prazo: float = 1.5,
        assentar: float = 0.2,
        indice: int = 0,
        ignorar: tuple[str, ...] = (),
    ) -> list[Recado]:
        """Clica e EXIGE que a página responda — o teste do botão morto."""
        antes = len(self._recados)

        def novos() -> list[Recado]:
            return [r for r in self._recados[antes:] if r.gesto not in ignorar]

        retrato = self.clicar(seletor, indice)
        if esperados > 0:
            self._bombear(lambda: len(novos()) >= esperados, prazo)
            self._bombear(lambda: False, assentar)
        else:
            self._bombear(lambda: False, prazo)
        vindos = novos()
        if len(vindos) != esperados:
            raise TelaMuda(
                f"cliquei {seletor!r} e a tela mandou {len(vindos)} recado(s), "
                f"esperava {esperados}. Alvo: <{retrato['alvo']['tag']} "
                f"class={retrato['alvo']['classe']!r}> texto="
                f"{retrato['alvo']['texto']!r} · travado={retrato['travado']} · "
                f"visível={retrato['visivel']} · caixa={retrato['caixa']} · "
                f"recados: {[r.bruto[:90] for r in vindos]}"
            )
        return vindos

    def foto(self, caminho: str | pathlib.Path) -> pathlib.Path:
        """Um PNG da janela oculta — para o olho de quem confere, que é a palavra final."""
        if not isinstance(self.janela, Gtk.OffscreenWindow):  # pragma: no cover
            raise ErroDeRegua("só a janela oculta fotografa (Gtk.OffscreenWindow)")
        self._bombear(lambda: False, 0.15)
        pix = self.janela.get_pixbuf()
        if pix is None:
            raise ErroDeRegua("a janela oculta não devolveu pixbuf")
        destino = pathlib.Path(caminho)
        pix.savev(str(destino), "png", [], [])
        return destino


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Dirige uma aba da interface nova.")
    p.add_argument("--aba", help='"02", "controles" ou um caminho .html')
    p.add_argument("--listar", action="store_true", help="as abas que achei")
    p.add_argument("--limites", action="store_true", help="o que ele NÃO faz")
    p.add_argument("--titulo", help="exige este pedaço no <title> da página")
    p.add_argument("--contar", action="append", default=[], metavar="SEL")
    p.add_argument("--ler", action="append", default=[], metavar="SEL")
    p.add_argument("--medir", action="append", default=[], metavar="SEL")
    p.add_argument("--clicar", action="append", default=[], metavar="SEL")
    p.add_argument("--segundos", type=float, default=0.0, help="espera antes de perguntar")
    p.add_argument("--foto", help="salva um PNG da janela oculta")
    args = p.parse_args(argv)

    if args.limites:
        print("O que a régua_de_tela NÃO faz:")
        for linha in O_QUE_ELE_NAO_FAZ:
            print(f"  · {linha}")
        print()
        if (pathlib.Path(__file__).resolve().parents[1] / O_MANUAL).is_file():
            print(f"Como se escreve a próxima: {O_MANUAL}")
        return 0
    if args.listar or not args.aba:
        paginas = abas_conhecidas()
        if not paginas:
            print("nenhuma aba: procurei em " + " · ".join(
                str(r / "layout") for r in raizes_candidatas()), file=sys.stderr)
            return 1
        for pagina in paginas:
            print(pagina)
        return 0 if args.listar else 1

    with Tela.abrir(args.aba, titulo_esperado=args.titulo) as t:
        print(f"aberta: {t.pagina}")
        if args.segundos:
            t.avancar(args.segundos)
        for sel in args.clicar:
            print(f"clicar {sel!r} → {t.clicar(sel)}")
        for sel in args.contar:
            print(f"contar {sel!r} → {t.contar(sel)}")
        for sel in args.ler:
            print(f"ler    {sel!r} → {t.ler(sel)!r}")
        for sel in args.medir:
            print(f"medir  {sel!r} → {t.medir(sel)}")
        for recado in t.recados():
            print(f"[{recado.aos:5.2f}s] {recado.canal}: {recado.bruto[:120]}")
        if args.foto:
            print(f"foto: {t.foto(args.foto)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
