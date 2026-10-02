#!/usr/bin/env python3
"""Abre a aba num Chrome de verdade (Playwright) e fotografa o que aparece."""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import onde  # noqa: E402

LARG, ALT = 1920, 1080

VISTA_DELA = (1918, 840)

DESTINO_DOC = onde.RAIZ / "docs" / "usage" / "assets"

SUBPASTA_DA_VISTA = "maximizada"

PREFIXO_NOVO = "aba-"

E_ABA = re.compile(r"^\d\d-")

NOME_DA_PROVA = "PROVA-DA-FOTO.txt"

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
    """O recibo do ensaio: quando, quantas, de que bancada, e a soma de cada PNG."""
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
        "# Chrome headless — nenhuma delas é medição desta ou de qualquer",
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
    # DEFEITO GRAVE um comentário do gerador que estava certo. A régua não media  # (noqa-acento: verbo medir, imperfeito)
    # a tela — media o próprio flag.  # (noqa-acento: verbo medir, imperfeito) verbo medir
    return pw.chromium.launch(
        executable_path="/usr/bin/google-chrome",
        args=["--no-sandbox"],
        ignore_default_args=["--hide-scrollbars"],
    )


def _retratar(navegador, alvo: pathlib.Path, saida: pathlib.Path,
              so_a_janela: bool = False,
              vista: tuple[int, int] | None = None) -> dict:
    """Uma página, já assentada, medida e fotografada."""
    larg, alt = vista or (LARG, ALT)
    pg = navegador.new_page(viewport={"width": larg, "height": alt}, device_scale_factor=1)
    try:
        pg.goto(f"file://{alvo}")
        pg.wait_for_load_state("networkidle")
        from hefesto_dualsense4unix.interface.folha_da_casa import seletores_escondidos

        pg.add_style_tag(
            content="".join(f"{s}{{display:none}}" for s in seletores_escondidos())
        )
        pg.wait_for_timeout(400)
        cx = pg.evaluate(MEDIDA_NA_VISTA)
        if cx.get("erro"):
            return {"erro": cx["erro"]}
        saida.parent.mkdir(parents=True, exist_ok=True)
        moldura = (pg.query_selector(".janela") or pg.query_selector(".cx")
                   or pg.query_selector(".pagina"))
        if vista is not None:
            pg.screenshot(path=str(saida))
        elif so_a_janela and moldura is not None:
            moldura.screenshot(path=str(saida))
        else:
            pg.screenshot(path=str(saida), full_page=True)
        return {"png": str(saida), **cx}
    finally:
        pg.close()


def _uma(arq: str, publicado: bool, vista: tuple[int, int] | None = None) -> int:
    alvo = onde.pagina(arq, publicado=publicado)
    saida = pathlib.Path(f"/tmp/olhar-{arq[:2]}{'-publicado' if publicado else ''}.png")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = _navegador(pw)
        try:
            r = _retratar(nav, alvo, saida, vista=vista)
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
           vista: tuple[int, int] | None = None) -> int:
    paginas = [p for p in onde.paginas(publicado=publicado) if E_ABA.match(p.name)]
    if len(paginas) < 10:
        sys.exit(f"achei {len(paginas)} abas em {'publicado' if publicado else 'bancada'} — o caminho mudou?")

    destino = destino_das_fotos(para_a_doc, vista)
    from playwright.sync_api import sync_playwright

    saiu: list[dict] = []
    with sync_playwright() as pw:
        nav = _navegador(pw)
        try:
            for p in paginas:
                nome = f"{PREFIXO_NOVO}{p.stem}.png" if para_a_doc else f"olhar-{p.stem}.png"
                r = _retratar(nav, p, destino / nome, so_a_janela=para_a_doc,
                              vista=vista)
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
    from hefesto_dualsense4unix.interface.frases_que_ela_baniu import (
        _borda,
        texto_visivel,
        texto_visivel_no_produto,
    )

    ler = texto_visivel_no_produto if publicado else texto_visivel

    paginas = [p for p in onde.paginas(publicado=publicado) if E_ABA.match(p.name)]
    if len(paginas) < 10:
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
          f"{'o produto' if publicado else 'a bancada'}")
    return 1 if total else 0


def _vista_pedida(texto: str) -> tuple[int, int]:
    """`1918x840` -> `(1918, 840)`, e recusa qualquer outra forma."""
    if texto.strip().lower() == "dela":
        return VISTA_DELA
    m = re.fullmatch(r"\s*(\d{3,5})\s*[xX×]\s*(\d{3,5})\s*", texto)
    if not m:
        raise argparse.ArgumentTypeError(
            f"vista {texto!r} não tem a forma LARGURAxALTURA (ex.: 1918x840), "
            "nem é a palavra 'dela'"
        )
    return int(m.group(1)), int(m.group(2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="fotografa a interface nova")
    p.add_argument("pagina", nargs="?",  # (noqa-acento)  (nome do argumento)
                   help="uma página, com extensão: 05-vibracao.html")
    p.add_argument("--publicado", action="store_true", help="o que o produto renderiza")
    p.add_argument("--todas", action="store_true", help="as dez abas de uma vez")
    p.add_argument("--doc", action="store_true", help="grava em docs/usage/assets/")
    p.add_argument("--palavra", metavar="PALAVRA",
                   help="lista onde esta palavra é LIDA nas dez abas, com a origem")
    p.add_argument("--vista", metavar="LARGxALT", type=_vista_pedida,
                   help="a vista em que fotografar — 'dela' é a janela dela "
                        "maximizada. Com ela a foto é a VISTA INTEIRA, não o "
                        "recorte da .janela")
    a = p.parse_args(argv)
    if a.palavra:
        return _palavra(a.palavra, a.publicado)
    if a.todas:
        return _todas(a.publicado, a.doc, a.vista)
    if not a.pagina:  # (noqa-acento)  (nome do argumento)
        p.error("diga a página, ou peça --todas")
    if a.doc:
        p.error("--doc é do modo --todas")
    return _uma(a.pagina, a.publicado, a.vista)  # (noqa-acento)  (nome do argumento)


if __name__ == "__main__":
    sys.exit(main())
