#!/usr/bin/env python3
"""Abre a aba num Chrome de verdade (Playwright) e fotografa o que aparece."""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import monta
import onde

LARG, ALT = 1920, 1080

VISTA_DO_USUARIO = (1918, 840)

DESTINO_DOC = onde.RAIZ / "docs" / "usage" / "assets"

SUBPASTA_DA_VISTA = "maximizada"

PREFIXO_NOVO = "aba-"

NOME_DA_PROVA = "PROVA-DA-FOTO.txt"

PRAZO_DE_CADA_SINAL_MS = 20_000

A_CAIXA = ".janela, .cx, .pagina"

AS_FONTES = "() => document.fonts.ready.then(() => true)"

DOIS_QUADROS = ("() => new Promise(r => requestAnimationFrame("
                "() => requestAnimationFrame(() => r(true))))")


class PaginaNaoFicouProntaError(RuntimeError):
    """O sinal que a página não deu dentro do prazo, com o nome dele."""

    def __init__(self, endereco: str, sinal: str, prazo_ms: int) -> None:
        self.endereco, self.sinal, self.prazo_ms = endereco, sinal, prazo_ms
        super().__init__(
            f"a página não ficou pronta: faltou {sinal} em {prazo_ms} ms ({endereco})")


def endereco_da_pagina(alvo: pathlib.Path | str) -> str:
    if isinstance(alvo, pathlib.Path):
        return alvo.resolve().as_uri()
    return alvo if "://" in alvo else pathlib.Path(alvo).resolve().as_uri()


def _esperar(pg: Any, endereco: str, passos: list[tuple[str, Any]], prazo_ms: int) -> None:
    from playwright.sync_api import TimeoutError as Estourou

    for sinal, esperar in passos:
        try:
            esperar()
        except Estourou:
            raise PaginaNaoFicouProntaError(endereco, sinal, prazo_ms) from None


def abrir_pronta(pg: Any, alvo: pathlib.Path | str, *, seletor: str | None = None,
                 prazo_ms: int = PRAZO_DE_CADA_SINAL_MS) -> None:
    """Abre ``alvo`` e só volta com a página desenhada: o ``load``, o
    ``document.fonts.ready``, dois quadros pintados (o que o motor da página faz depois do
    ``load`` roda antes do quadro) e, pedido, o ``seletor`` no DOM. Nenhuma página pede nada
    à rede depois do ``load``: a rede quieta só somava espera e estourava com a máquina
    carregada. Cada sinal tem prazo; o que não vem sai em ``PaginaNaoFicouProntaError``."""
    endereco = endereco_da_pagina(alvo)
    passos: list[tuple[str, Any]] = [
        ("o load do documento",
         lambda: pg.goto(endereco, wait_until="load", timeout=prazo_ms)),
        ("o document.fonts.ready",
         lambda: pg.wait_for_function(AS_FONTES, timeout=prazo_ms)),
        ("dois quadros pintados",
         lambda: pg.wait_for_function(DOIS_QUADROS, timeout=prazo_ms)),
    ]
    if seletor is not None:
        passos.append((f"o seletor {seletor!r} no DOM",
                       lambda: pg.wait_for_selector(seletor, state="attached",
                                                    timeout=prazo_ms)))
    _esperar(pg, endereco, passos, prazo_ms)


MEDIDA_NA_VISTA = """() => {
  const d = document.documentElement;
  const cx = document.querySelector('.janela') || document.querySelector('.cx')
          || document.querySelector('.pagina');
  if (!cx) return {erro: 'nem .janela, nem .cx, nem .pagina nesta página — não há o que medir'};
  const j = cx.getBoundingClientRect();
  return {caixa: cx.className, larg: Math.round(j.width), alt: Math.round(j.height),
          vista: `${window.innerWidth}x${window.innerHeight}`,
          morto_abaixo: Math.max(0, Math.round(window.innerHeight - j.bottom)),
          vao_dos_lados: Math.max(0, Math.round((window.innerWidth - j.width) / 2)),
          passa_da_dobra: Math.max(0, Math.round(d.scrollHeight - window.innerHeight)),
          rolagem_lateral: d.scrollWidth > d.clientWidth};
}"""


def _gravar_prova_da_foto(destino: pathlib.Path, modo: str, origem: str,
                          vista: str = "") -> pathlib.Path:
    """O recibo do ensaio: quando, quantas, de que pasta, e a soma de cada PNG."""
    import datetime
    import hashlib

    pngs = sorted(p for p in destino.glob(f"{PREFIXO_NOVO}*.png") if p.is_file())
    linhas = [
        f"# Recibo do ensaio de fotos — gerado por {_meu_endereco()}",
        "#",
        "# NÃO edite à mão. Rode o retratista; ele reescreve este arquivo.",
        "# Existe porque uma mudança de tela que não move pixel deixa as fotos",
        "# idênticas, e sem este recibo o portão das fotos ficaria vermelho",
        "# para sempre.",
        "",
        f"ensaio:  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"abas:    {len(pngs)}",
        f"modo:    {modo}",
        f"origem:  {origem}",
        f"vista:   {vista or 'recorte da .janela'}",
        "",
        "# Toda linha destas imagens é PÁGINA DO REPOSITÓRIO fotografada num",
        "# Chrome headless — nenhuma é medição desta ou de qualquer",
        "# máquina, e o retratista não fala com o daemon (portão:",
        "# tests/unit/test_retrato_das_abas_nao_vaza_dado_real.py).",
        "",
        "# soma sha256 de cada foto, em ordem alfabética",
    ]
    for p in pngs:
        linhas.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}")

    alvo = destino / NOME_DA_PROVA
    alvo.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return alvo


def _meu_endereco() -> str:
    """Como o recibo se refere a quem o escreveu."""
    meu = pathlib.Path(__file__).resolve()
    try:
        return str(meu.relative_to(onde.RAIZ))
    except ValueError:
        return f"hefesto_dualsense4unix.interface.{meu.stem}"


def _navegador(pw):
    return pw.chromium.launch(
        executable_path="/usr/bin/google-chrome",
        args=["--no-sandbox"],
        ignore_default_args=["--hide-scrollbars"],
    )


def _retratar(navegador, alvo: pathlib.Path, saida: pathlib.Path,
              so_a_janela: bool = False,
              vista: tuple[int, int] | None = None, tema: str = "",
              prazo_ms: int = PRAZO_DE_CADA_SINAL_MS) -> dict:
    """Uma página, assentada pelos próprios sinais, medida e fotografada; sem um sinal no
    prazo, o erro com o nome dele e nenhuma foto. Na foto, a animação e a transição que
    acabam (a cor do tema transita) saem no fim, e a que não acaba (um pulso) sai no estado
    de base, o mesmo que a página declara para o movimento reduzido: a foto não depende do
    instante em que foi tirada."""
    larg, alt = vista or (LARG, ALT)
    pg = navegador.new_page(viewport={"width": larg, "height": alt}, device_scale_factor=1)
    try:
        abrir_pronta(pg, alvo, seletor=A_CAIXA, prazo_ms=prazo_ms)
        from hefesto_dualsense4unix.interface.folha_da_casa import seletores_escondidos

        pg.add_style_tag(
            content="".join(f"{s}{{display:none}}" for s in seletores_escondidos())
        )
        if tema:
            pg.add_style_tag(content=tema)
        cx = pg.evaluate(MEDIDA_NA_VISTA)
        if cx.get("erro"):
            return {"erro": cx["erro"]}
        saida.parent.mkdir(parents=True, exist_ok=True)
        moldura = (pg.query_selector(".janela") or pg.query_selector(".cx")
                   or pg.query_selector(".pagina"))
        if vista is not None:
            pg.screenshot(path=str(saida), animations="disabled")
        elif so_a_janela and moldura is not None:
            moldura.screenshot(path=str(saida), animations="disabled")
        else:
            pg.screenshot(path=str(saida), full_page=True, animations="disabled")
        return {"png": str(saida), **cx}
    except PaginaNaoFicouProntaError as exc:
        return {"erro": str(exc)}
    finally:
        pg.close()


def _uma(arq: str, publicado: bool, vista: tuple[int, int] | None = None,
         tema: str = "") -> int:
    alvo = onde.pagina(arq, publicado=publicado)
    saida = pathlib.Path(f"/tmp/olhar-{arq[:2]}{'-publicado' if publicado else ''}"
                         f"{'-com-tema' if tema else ''}.png")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = _navegador(pw)
        try:
            r = _retratar(nav, alvo, saida, vista=vista, tema=tema)
        finally:
            nav.close()
    if "erro" in r:
        sys.exit(f"ERRO ao medir {arq}: {r['erro']}")
    print(json.dumps({**r, "olhou": str(alvo.relative_to(onde.RAIZ))}))
    return 0


def destino_das_fotos(para_a_doc: bool, vista: tuple[int, int] | None) -> pathlib.Path:
    """Onde as fotos desta execução caem — e por que a vista tem pasta PRÓPRIA."""
    if not para_a_doc:
        return pathlib.Path("/tmp")
    return DESTINO_DOC / SUBPASTA_DA_VISTA if vista is not None else DESTINO_DOC


def _todas(publicado: bool, para_a_doc: bool,
           vista: tuple[int, int] | None = None, tema: str = "") -> int:
    do_produto = set(monta.as_abas_do_produto())
    paginas = [p for p in onde.paginas(publicado=publicado) if p.name in do_produto]
    if len(paginas) < len(monta.ABAS):
        sys.exit(f"achei {len(paginas)} abas em {'publicado' if publicado else 'mockup'} — o caminho mudou?")

    destino = destino_das_fotos(para_a_doc, vista)
    from playwright.sync_api import sync_playwright

    saiu: list[dict] = []
    with sync_playwright() as pw:
        nav = _navegador(pw)
        try:
            for p in paginas:
                nome = (f"{PREFIXO_NOVO}{p.stem}.png" if para_a_doc
                        else f"olhar-{p.stem}{'-com-tema' if tema else ''}.png")
                r = _retratar(nav, p, destino / nome, so_a_janela=para_a_doc,
                              vista=vista, tema=tema)
                if "erro" in r:
                    sys.exit(f"ERRO ao medir {p.name}: {r['erro']}")
                saiu.append({"aba": p.name, **r})
        finally:
            nav.close()

    for r in saiu:
        dobra = f" · passa {r['passa_da_dobra']} px da dobra" if r["passa_da_dobra"] else ""
        sobra = f" · {r['morto_abaixo']} px mortos embaixo" if r["morto_abaixo"] else ""
        lados = f" · vão {r['vao_dos_lados']} px de cada lado" if r["vao_dos_lados"] else ""
        print(f"{r['aba']:<20} {r['larg']}x{r['alt']} em {r['vista']}"
              f"{dobra}{sobra}{lados}  ->  {r['png']}")
    print(f"\n{len(saiu)} abas retratadas em {destino}")

    if para_a_doc:
        origem = paginas[0].parent
        try:
            origem_legivel = str(origem.relative_to(onde.RAIZ))
        except ValueError:
            origem_legivel = str(origem)
        pedida = f"{vista[0]}x{vista[1]}" if vista else ""
        recibo = _gravar_prova_da_foto(
            destino,
            modo=("--todas --publicado --doc" if publicado else "--todas --doc")
            + (f" --vista {pedida}" if pedida else ""),
            origem=origem_legivel,
            vista=pedida,
        )
        print(f"recibo: {recibo}")
    return 0


def _fontes() -> list[pathlib.Path]:
    aqui = pathlib.Path(__file__).resolve().parent
    return sorted(aqui.glob("aba??.py")) + sorted((aqui / "pacotes").glob("a??_*.py"))


def _de_onde(trecho: str) -> str:
    """O arquivo:linha do gerador que escreveu ``trecho``, ou por que não achei."""
    for tamanho in (60, 40, 24, 14):
        alvo = trecho[:tamanho].strip()
        if len(alvo) < 8:
            continue
        agulha = re.compile(r"\s+".join(re.escape(p) for p in alvo.split()))
        achados = []
        for fonte in _fontes():
            texto = fonte.read_text(encoding="utf-8")
            m = agulha.search(texto)
            if m is not None:
                achados.append(f"{fonte.name}:{texto.count(chr(10), 0, m.start()) + 1}")
        if achados:
            return " · ".join(achados[:3])
    return "não achei no fonte (pode vir de `app/`, que não é desta posse)"


def _palavra(alvo: str, publicado: bool) -> int:
    """A palavra que uma pessoa LÊ, página por página, com origem e contexto."""
    from hefesto_dualsense4unix.interface.frases_banidas import (
        _borda,
        texto_visivel,
        texto_visivel_no_produto,
    )

    ler = texto_visivel_no_produto if publicado else texto_visivel

    do_produto = set(monta.as_abas_do_produto())
    paginas = [p for p in onde.paginas(publicado=publicado) if p.name in do_produto]
    if len(paginas) < len(monta.ABAS):
        sys.exit(f"achei {len(paginas)} abas — o caminho mudou?")

    total = 0
    for p in paginas:
        cru = p.read_text(encoding="utf-8")
        visivel = ler(cru)
        achados = list(_borda(alvo).finditer(visivel))
        total += len(achados)
        print(f"\n{p.name}  —  {len(achados)} ocorrência(s) visível(eis)")
        for m in achados:
            linha = visivel.count("\n", 0, m.start()) + 1
            a, b = max(0, m.start() - 55), m.end() + 55
            contexto = " ".join(visivel[a:b].split())
            print(f"  linha {linha}: …{contexto}…")
            print(f"      vem de: {_de_onde(' '.join(cru[m.start():b].split()))}")
    print(f"\n{alvo!r}: {total} ocorrência(s) visível(eis) em "
          f"{'o produto' if publicado else 'o mockup'}")
    return 1 if total else 0


def _vista_pedida(texto: str) -> tuple[int, int]:
    """`1918x840` -> `(1918, 840)`, e recusa qualquer outra forma."""
    if texto.strip().lower() == "maximizada":
        return VISTA_DO_USUARIO
    m = re.fullmatch(r"\s*(\d{3,5})\s*[xX×]\s*(\d{3,5})\s*", texto)
    if not m:
        raise argparse.ArgumentTypeError(
            f"vista {texto!r} não tem a forma LARGURAxALTURA (ex.: 1918x840), "
            "nem é a palavra 'maximizada'"
        )
    return int(m.group(1)), int(m.group(2))


def _tema_pedido(caminho: str) -> str:
    """A folha do ``--tema``, conferida pela MESMA régua que liga o tema de uma modificação
    (`mods.tema.validar`): o retratista não fotografa um tema que o produto recusaria."""
    from hefesto_dualsense4unix.mods import tema as _tema

    try:
        return _tema.validar(pathlib.Path(caminho).read_text(encoding="utf-8")).folha
    except OSError as exc:
        sys.exit(f"o tema {caminho!r} não abriu: {exc.strerror}")
    except _tema.TemaRecusadoError as exc:
        sys.exit(f"o tema {caminho!r} foi recusado. {exc.frase}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="fotografa a interface nova")
    p.add_argument("pagina", nargs="?",  # (noqa-acento)
                   help="uma página, com extensão: 05-vibracao.html")
    p.add_argument("--publicado", action="store_true", help="o que o produto renderiza")
    p.add_argument("--todas", action="store_true", help="as abas do produto de uma vez")
    p.add_argument("--doc", action="store_true", help="grava em docs/usage/assets/")
    p.add_argument("--palavra", metavar="PALAVRA",
                   help="lista onde esta palavra é LIDA nas abas, com a origem")
    p.add_argument("--vista", metavar="LARGxALT", type=_vista_pedida,
                   help="a vista em que fotografar — 'maximizada' é a janela do usuário "
                        "no tamanho da tela. Com essa vista a foto é a VISTA INTEIRA, não o "
                        "recorte da .janela")
    p.add_argument("--tema", metavar="ARQUIVO",
                   help="fotografa com este tema de cores (um :root{…}), conferido pela "
                        "régua do tema das modificações; as fotos não vão para a doc")
    a = p.parse_args(argv)
    if a.tema and a.doc:
        p.error("--tema não grava em docs/usage/assets/: a documentação mostra a casa")
    tema = _tema_pedido(a.tema) if a.tema else ""
    if a.palavra:
        return _palavra(a.palavra, a.publicado)
    if a.todas:
        return _todas(a.publicado, a.doc, a.vista, tema)
    if not a.pagina:
        p.error("diga a página, ou peça --todas")
    if a.doc:
        p.error("--doc é do modo --todas")
    return _uma(a.pagina, a.publicado, a.vista, tema)


if __name__ == "__main__":
    sys.exit(main())
