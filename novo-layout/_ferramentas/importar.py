#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""O CAMINHO DE VOLTA: lê o SVG que ela arrumou e traz para o mapa.

Ela, 27/08/2026: "ou converter o controle inteiro pra svg que arrumo agora",
"com os nomes de cada elemento descritos nas layers e objetos".

Como funciona o ciclo:
    _ferramentas/exportar.py   ->  ~/Imagens/dualsense-para-editar.svg
    (ela arruma no editor e salva por cima)
    _ferramentas/importar.py   ->  ds_limpo.svg + dualsense.svg + o CSV
    _ferramentas/mapa.py       ->  mapa-do-controle.html

O que ele traz de volta: a GEOMETRIA de cada peça, pelo `id` do grupo. É por isso
que os ids não podem ser renomeados no editor — o nome que aparece na árvore é o
<title>, e esse ela muda à vontade.

O que ele NÃO traz: cor, estilo e a folha do mapa, que continuam sendo da casa.

    python3 importar.py            confere e mostra o que mudou, sem gravar
    python3 importar.py --gravar   grava
"""
import csv, io, pathlib, re, subprocess, sys

# A RAIZ SAI DE `__file__`, NUNCA CRAVADA. Medido em 28/08/2026: oito
# arquivos desta casa cravavam o caminho absoluto da árvore DELA, e por isso
# rodar uma CÓPIA do gerador REESCREVIA o mockup dela. Aconteceu numa prova:
# o `05-vibracao.html` dela ficou com `--r-motor:56px` porque um agente rodou
# uma cópia noutro diretório. É o mesmo estrago de 25/08, quando o mockup que
# ela ia abrir sumiu do disco na frente dela — e é o que impediria qualquer
# segunda árvore de trabalhar sem tocar na primeira.
R = pathlib.Path(__file__).resolve().parents[2]
EDITADO = pathlib.Path("/home/vitoriamaria/Imagens/dualsense-para-editar.svg")
LIMPO = R / "novo-layout/_ferramentas/ds_limpo.svg"
PROD = R / "assets/control-svg/dualsense.svg"
CSV = R / "docs/data/pecas-do-dualsense.csv"


def grupos(texto):
    """Os grupos com id, e o conteúdo de desenho de cada um."""
    fora = {}
    for m in re.finditer(r'<g\b[^>]*\bid="([^"]+)"[^>]*>', texto):
        pid = m.group(1)
        # os `glifo-*` ENTRAM: eles são o trabalho dela tanto quanto as peças.
        if pid.startswith("grupo-") or pid == "fundo":
            continue
        i = m.start()
        prof, j = 0, i
        while True:
            n = re.search(r"<g\b|</g>", texto[j:])
            if not n:
                break
            j += n.end()
            prof += 1 if n.group(0) == "<g" else -1
            if prof == 0:
                break
        fora[pid] = texto[i:j]
    return fora


def medir_matriz(caminho):
    """A matriz de cada glifo no espaço do viewBox, e o `--lado` que ele declara."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 1200, "height": 900})
        pg.goto(f"file://{caminho}")
        pg.wait_for_timeout(500)
        r = pg.evaluate("""() => {const R=n=>Math.round(n*100000)/100000, o={};
          const raiz=document.querySelector('svg');
          document.querySelectorAll('[id^="glifo-"]').forEach(g=>{
            const m = raiz.getScreenCTM().inverse().multiply(g.getScreenCTM());
            const lado = getComputedStyle(g).getPropertyValue('--lado').trim();
            o[g.id.slice(6)] = {
              transform: `matrix(${R(m.a)},${R(m.b)},${R(m.c)},${R(m.d)},${R(m.e)},${R(m.f)})`,
              lado: parseFloat(lado) || 5.2};});
          return o;}""")
        b.close()
    return r


def medir_glifo_contra_peca(caminho):
    """Quantos px separam o centro de cada glifo do centro da peça dele."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 1200, "height": 900})
        pg.goto(f"file://{caminho}")
        pg.wait_for_timeout(500)
        r = pg.evaluate("""() => {const o={};
          document.querySelectorAll('[id^="glifo-"]').forEach(g=>{
            const pid=g.id.slice(6);
            const p=document.getElementById(pid); if(!p) return;
            const a=g.getBoundingClientRect(), z=p.getBoundingClientRect();
            if(!a.width || !z.width) return;
            o[pid]=Math.hypot((a.x+a.width/2)-(z.x+z.width/2),
                              (a.y+a.height/2)-(z.y+z.height/2));});
          return o;}""")
        b.close()
    return r


def medir_no_mapa():
    """Quais glifos ficaram longe da peça DEPOIS de o mapa ser gerado."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        pg.goto(f"file://{R}/novo-layout/mapa-do-controle.html")
        pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(500)
        r = pg.evaluate("""() => {const o={};
          document.querySelectorAll('.sobre').forEach(g=>{
            const id=[...g.classList].find(c=>c.startsWith('s-')).slice(2);
            const p=document.getElementById('mp-'+id); if(!p) return;
            const a=g.getBoundingClientRect(), z=p.getBoundingClientRect();
            const d=Math.hypot((a.x+a.width/2)-(z.x+z.width/2),(a.y+a.height/2)-(z.y+z.height/2));
            if(d>4) o[id]=Math.round(d*10)/10;});
          return o;}""")
        b.close()
    return r


def caixas(caminho):
    """A caixa de cada peça, medida no navegador — é o único jeito honesto."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 1200, "height": 900})
        pg.goto(f"file://{caminho}")
        pg.wait_for_timeout(500)
        r = pg.evaluate("""() => {const R=n=>Math.round(n*100)/100, o={};
          const raiz = document.querySelector('svg');
          document.querySelectorAll('svg g[id]').forEach(g=>{
            if(g.id.startsWith('grupo-') || g.id.startsWith('glifo-')) return;
            let b; try{ b=g.getBBox(); }catch(e){ return; }
            if(!b.width && !b.height) return;
            // A CAIXA NO ESPAÇO DO SVG, não no espaço local do grupo.
            // Ela fez o L1 e o L2 espelhando os direitos com uma matriz; lendo o
            // bbox local, os dois voltavam com as coordenadas do LADO DIREITO —
            // e o CSV teria gravado o L1 em cima do R1.
            // do espaço LOCAL do grupo para o espaço do viewBox: a tela é a
            // única referência comum, e as duas pontas se cancelam nela.
            const m = raiz.getScreenCTM().inverse().multiply(g.getScreenCTM());
            const pt = (x,y) => { const p=raiz.createSVGPoint(); p.x=x; p.y=y;
                                  return p.matrixTransform(m); };
            const cs = [pt(b.x,b.y), pt(b.x+b.width,b.y),
                        pt(b.x,b.y+b.height), pt(b.x+b.width,b.y+b.height)];
            const xs = cs.map(p=>p.x), ys = cs.map(p=>p.y);
            o[g.id]=[R(Math.min(...xs)),R(Math.min(...ys)),
                     R(Math.max(...xs)),R(Math.max(...ys))];});
          return o;}""")
        b.close()
    return r


def main():
    gravar = "--gravar" in sys.argv
    if not EDITADO.exists():
        sys.exit(f"não achei {EDITADO} — rode o exportar.py primeiro")

    # O ARQUIVO TEM DE SER XML VÁLIDO. Um atributo duplicado fez o parser abortar
    # no meio e os 18 glifos sumirem da tela dela — e o importador anterior teria
    # gravado o estrago sem reclamar.
    import xml.etree.ElementTree as ET
    try:
        ET.parse(EDITADO)
    except Exception as exc:
        sys.exit(f"o SVG editado não é XML válido: {exc}\n"
                 "nada foi lido. Conserte no editor e salve de novo.")

    novo = grupos(EDITADO.read_text())
    velho = grupos(LIMPO.read_text())
    faltam = [k for k in velho if k not in novo]
    if faltam:
        sys.exit(f"o arquivo editado perdeu peças: {faltam}\n"
                 "os `id` dos grupos não podem ser renomeados nem apagados.")

    cx_novo, cx_velho = caixas(EDITADO), caixas(LIMPO)
    mudou = {k: (cx_velho.get(k), cx_novo[k]) for k in cx_novo
             if cx_velho.get(k) != cx_novo[k]}
    print(f"=== {len(novo)} peças lidas · {len(mudou)} mudaram de lugar ===")
    for k, (a, z) in sorted(mudou.items()):
        print(f"  {k:22} {a} -> {z}")
    if not mudou:
        print("  nada mudou.")
        return
    if not gravar:
        print("\n(nada foi gravado — rode com --gravar)")
        return

    # A OPACIDADE DAS FEATURES É DA FOLHA, não do arquivo. O exportador as mostra
    # a 35% para ela ver onde estão; se esse valor voltar como `style` inline, ele
    # vence o CSS e a peça fica visível no mapa em repouso — foi assim que o motor
    # direito apareceu tracejado por cima da empunhadura. Limpo na entrada.
    for pid in [k for k in novo if k.startswith("feat-")]:
        novo[pid] = re.sub(r'\s(opacity="[^"]*"|style="[^"]*opacity[^"]*")', "",
                           novo[pid], count=1)

    # 1. a geometria volta para os dois SVGs
    for alvo in (LIMPO, PROD):
        s = alvo.read_text()
        for pid, bloco in novo.items():
            if pid not in velho:
                # O QUE É NOVO ENTRA. Os grupos `glifo-*` nunca estiveram no
                # ds_limpo — eles nasceram no arquivo de edição —, e por isso o
                # importador os pulava: as três horas dela paravam nas peças e os
                # símbolos voltavam a ser redesenhados pelo gerador.
                if pid.startswith("glifo-"):
                    s = s.replace("</svg>", "  " + bloco + "\n</svg>", 1)
                continue
            i = s.index(f'id="{pid}"'); ini = s.rindex("<g ", 0, i)
            prof, j = 0, ini
            while True:
                n = re.search(r"<g\b|</g>", s[j:])
                if not n:
                    break
                j += n.end(); prof += 1 if n.group(0) == "<g" else -1
                if prof == 0:
                    break
            s = s[:ini] + bloco + s[j:]
        alvo.write_text(s)
        print(f"  ok  {alvo.name}")
    subprocess.run(["cp", str(LIMPO), "/tmp/ds_limpo.svg"], check=True)

    # 2. A POSIÇÃO DOS GLIFOS volta como transform literal.
    # Ela: "sumiu os glifos preciso deles lá". Agora que eles vão no arquivo de
    # edição, o que ela fizer com cada um — mover, girar, redimensionar — vira uma
    # matriz, e o mapa passa a aplicá-la em vez de calcular a posição. Quem manda
    # na posição do glifo deixa de ser a conta e passa a ser ela.
    import json
    # A MATRIZ ACUMULADA, medida no navegador — não o atributo `transform` do
    # grupo. Um glifo dentro de um grupo espelhado ou transladado tem a posição
    # dele decidida pela CADEIA inteira; lendo só o atributo, os rótulos dos ombros
    # e as setas do d-pad caíram fora do desenho.
    glifos = medir_matriz(EDITADO)
    t = CSV.read_text()
    for pid, cx in cx_novo.items():
        alvo = [l for l in t.splitlines() if l.startswith(pid + ",")]
        if not alvo:
            continue
        c = next(csv.reader([alvo[0]]))
        c[7], c[8], c[9], c[10] = (f"{v}" for v in cx)
        buf = io.StringIO(); csv.writer(buf, lineterminator="").writerow(c)
        t = t.replace(alvo[0], buf.getvalue())
    CSV.write_text(t)
    print(f"  ok  {CSV.name}")

    # AS ZONAS DE COR VOLTAM POR CIMA. O bloco `<g>` que ela salvou do editor
    # substitui o do disco INTEIRO — e com ele vai embora o `class="z-<zona>"`
    # que o gerador de cores escreveu. Sem esta chamada, o ciclo dela apaga a
    # cor do desenho a cada volta, em silêncio: o SVG continua desenhando, só
    # que todo modelo passa a pintar igual. O gerador não toca em geometria; ele
    # só reaplica as classes e a folha.
    subprocess.run([sys.executable, str(R / "scripts/gerar_cores_do_dualsense.py")],
                   check=True)

    print("\nagora: python3 mapa.py && ../../.venv/bin/python "
          "../../scripts/check_pecas_do_dualsense.py "
          "&& ../../.venv/bin/python ../../scripts/check_cores_do_dualsense.py")


if __name__ == "__main__":
    main()
