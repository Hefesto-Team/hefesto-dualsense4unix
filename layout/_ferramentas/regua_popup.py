#!/usr/bin/env python3
"""Régua das POP-UPS: abre cada `.tela-nova` pelo fragmento e mede a caixa.

POR QUE ELA EXISTE, e o buraco que ela fecha (29/08/2026). Nenhuma régua desta
casa media pop-up, e as duas medições que já existiam são cegas a ela por  (noqa-acento: verbo medir)
motivos DIFERENTES — o que é pior do que uma cegueira só, porque cada uma
parecia cobrir o que a outra não cobria:

  · a `regua.py` carrega a página **sem fragmento** (`file://{tmp}`), e a
    `.tela-nova` só aparece em `:target`. Ela nunca viu uma pop-up ABERTA.
  · a `regua_estados.py` varre `.miolo, .miolo *`, e a `.tela-nova` nasce
    IRMÃ da `.janela`, fora do miolo. Ela nunca viu uma pop-up, ponto.

Resultado medido: as três pop-ups da Navegação **nunca tinham sido medidas** —
nem quando ganharam teto de altura, em 28/08. O defeito que o teto cura (o
conteúdo sair da caixa sem barra e sem aviso) é exatamente o defeito que régua
nenhuma pegava.

O QUE ELA MEDE CONTRA. Não contra o viewport do Chrome: no mockup a
`.tela-nova` é `position:fixed`, logo ela se centra nos 1920×1080 do navegador,
e não nos 1180×757 da `.janela` desenhada. Medir contra o viewport daria verde
numa caixa de 1000px de altura que no produto ficaria com 243px para fora.
**A régua mede contra a `.janela` da própria página** — que é a janela do
produto — e projeta a caixa centrada nela.

A MORDIDA VEM JUNTO: `regua_popup.py --morde` sabota as pop-ups de propósito
(caixa de 2000px, teto sem rolagem, tabela mais larga que a caixa) e exige que
cada sabotagem seja REPROVADA. Régua nova desta pasta já nasceu falsa uma vez
— ver as duas cicatrizes no LEIA-ME — e por isso ela se prova sozinha.

Uso:  regua_popup.py                      # todas as abas
      regua_popup.py 06-navegacao.html    # uma
      regua_popup.py --morde              # prova que ela morde
"""
import pathlib
import re
import sys

from playwright.sync_api import sync_playwright

# A RAIZ SAI DE `__file__`, NUNCA CRAVADA — mesma razão da `regua.py`: rodar uma
# CÓPIA do gerador não pode reescrever o mockup DELA.
D = pathlib.Path(__file__).resolve().parents[1]

# O RESPIRO, e por que 20px de cada lado: é o mesmo número que o teto da
# `.tn-cx` já usa — `min(717px, calc(100vh - 40px))`, com 717 = 757 − 40. A
# régua não inventa um limite novo; ela mede o limite que o CSS declara, e o
# ancora na janela REAL da página em vez de num número digitado.
RESPIRO = 20

# O que pode abrir para FORA da caixa sem ser defeito. A `.dica` é `position:
# absolute` e nasce para fora de propósito (comentário do `.tn-cx .dica` no
# aba06.py); ela continua respondendo pelo envelope contra a janela, que é o
# que de fato a cortaria no produto.
FORA_DE_PROPOSITO = ".dica"

SONDA = r"""
(cfg) => {
  const R = o => Math.round(o * 10) / 10;
  const tela = document.querySelector('.tela-nova:target');
  if (!tela) return {erro: 'o fragmento não abriu nenhuma .tela-nova'};
  const cx = tela.querySelector('.tn-cx');
  if (!cx) return {erro: 'a .tela-nova não tem .tn-cx'};
  const jan = document.querySelector('.janela');
  if (!jan) return {erro: 'a página não tem .janela — não há contra o que medir'};

  const jr = jan.getBoundingClientRect();
  const cr = cx.getBoundingClientRect();
  const erros = [], notas = [];

  // ---- 1 e 2: a CAIXA cabe na janela do produto, com o respiro do teto?
  const tetoAlt = jr.height - 2 * cfg.respiro, tetoLarg = jr.width - 2 * cfg.respiro;
  if (cr.height > tetoAlt + 0.5)
    erros.push(`a caixa tem ${R(cr.height)}px de altura e a janela do produto `
             + `oferece ${R(tetoAlt)} (${R(jr.height)} menos ${2 * cfg.respiro} de respiro)`);
  if (cr.width > tetoLarg + 0.5)
    erros.push(`a caixa tem ${R(cr.width)}px de largura e a janela do produto `
             + `oferece ${R(tetoLarg)} (${R(jr.width)} menos ${2 * cfg.respiro} de respiro)`);

  // ---- 3: TOPO e RODAPÉ à vista. O teto sem eles não vale nada: a razão de
  //         ele existir é o título e o "Guardar" nunca saírem da tela.
  for (const k of ['tn-topo', 'tn-rod']) {
    const p = tela.querySelector('.' + k);
    if (!p) continue;
    const r = p.getBoundingClientRect();
    if (r.height < 1) { erros.push(`o .${k} ficou com 0px de altura`); continue; }
    if (r.top < cr.top - 0.5 || r.bottom > cr.bottom + 0.5)
      erros.push(`o .${k} está fora da caixa (${R(r.top)}..${R(r.bottom)} contra `
               + `${R(cr.top)}..${R(cr.bottom)})`);
  }

  // ---- o que ROLA por dentro, e o que RECORTA em silêncio
  const rolam = [], mudos = [];
  const clipa = new Set();   // quem, dentro da pop-up, corta os filhos
  tela.querySelectorAll('*').forEach(e => {
    const s = getComputedStyle(e);
    if (e.clientHeight === 0 && e.clientWidth === 0) return;
    const rolavel = /auto|scroll/.test(s.overflowY) || /auto|scroll/.test(s.overflowX);
    const oculto  = s.overflowY === 'hidden' || s.overflowX === 'hidden';
    if (rolavel || oculto) clipa.add(e);
    const dv = e.scrollHeight - e.clientHeight, dh = e.scrollWidth - e.clientWidth;
    const quem = (e.className || e.tagName).toString().split(' ')[0];
    if (rolavel && (dv > 2 || dh > 2))
      rolam.push({quem, vao: R(e.clientHeight), conteudo: R(e.scrollHeight),  // (noqa-acento): chave do JSON que o Python lê em r['conteudo']
                  esconde: R(dv), lado: R(dh)});
    // ROLAGEM DE LADO é sempre defeito: numa tabela ela esconde a segunda
    // coluna atrás de uma barra que quase ninguém procura.
    if (rolavel && dh > 2)
      erros.push(`"${quem}" rola DE LADO: ${R(e.scrollWidth)}px de conteúdo em `
               + `${R(e.clientWidth)} de vão`);
    // RECORTE MUDO: `overflow:hidden` com conteúdo a mais não dá barra, não dá
    // aviso, e some com o que está embaixo. É o defeito de origem do teto.
    if (oculto && !rolavel && (dv > 2 || dh > 2))
      mudos.push({quem, esconde: R(dv), lado: R(dh)});
  });
  for (const m of mudos)
    erros.push(`"${m.quem}" RECORTA EM SILÊNCIO: overflow:hidden escondendo `
             + `${m.esconde}px embaixo e ${m.lado}px de lado, sem barra`);

  // ---- 4: conteúdo FORA da caixa sem nada que role. Quem tem um antepassado
  //         que corta (auto/scroll/hidden) está apenas rolado para fora — a
  //         pessoa alcança, e isso não é este defeito. Sem antepassado que
  //         corte, o pedaço está simplesmente na rua, e ninguém avisa.
  let env = {left: cr.left, right: cr.right, top: cr.top, bottom: cr.bottom};
  const vazados = [];
  tela.querySelectorAll('*').forEach(e => {
    const r = e.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return;
    const deProposito = e.closest(cfg.foraDeProposito);
    let p = e.parentElement, cortado = false;
    while (p && p !== tela) { if (clipa.has(p)) { cortado = true; break; } p = p.parentElement; }
    // O ENVELOPE CONTA QUEM DE FATO PINTA FORA DA CAIXA — e quem está rolado
    // para fora de um `overflow:auto` NÃO pinta: ele está recortado, e a pessoa
    // o alcança rolando. Contá-lo inflava o envelope com o próprio conteúdo que
    // o teto de altura existe para esconder, e a conta reprovava a pop-up por
    // ela ter conteúdo — que é o contrário do que ela promete medir.
    // MEDIDO em 29/08 na `#mapear-entradas`: envelope de 756,5px de altura
    // contra a janela de 757, a meio pixel de um vermelho falso; com a correção,
    // 717 — a altura da caixa, que é o que ele deve ser.
    //
    // A `.dica` É A EXCEÇÃO, E ELA TEM DE SER: ela abre para fora de propósito e
    // não responde pela conta 4, então se ela também saísse do envelope uma dica
    // dentro da `.moldura` ficaria invisível às DUAS contas. Foi exatamente esse
    // o defeito que esta régua pegou nesta pop-up, e ele tem de continuar pego.
    if (!cortado || deProposito)
      env = {left: Math.min(env.left, r.left), right: Math.max(env.right, r.right),
             top: Math.min(env.top, r.top), bottom: Math.max(env.bottom, r.bottom)};
    if (deProposito) return;
    if (cortado) return;
    const fora = Math.max(cr.top - r.top, r.bottom - cr.bottom,
                          cr.left - r.left, r.right - cr.right);
    if (fora > 2)
      vazados.push({quem: (e.className || e.tagName).toString().split(' ')[0], fora: R(fora)});
  });
  // um só recado por classe: uma tabela vazada põe todas as linhas na lista.
  const porClasse = {};
  for (const v of vazados) porClasse[v.quem] = Math.max(porClasse[v.quem] || 0, v.fora);
  for (const [quem, fora] of Object.entries(porClasse))
    erros.push(`"${quem}" está ${fora}px FORA da caixa e nada rola — `
             + `sai da pop-up sem barra e sem aviso`);

  // ---- 5: TRANSBORDO MUDO, e ele NÃO é o mesmo defeito de cima. Um filho pode
  //         sair do pai sem sair da CAIXA: aí ele não some da tela, ele PINTA
  //         POR CIMA do que vem depois. Medido na mordida do teto de 400px: na
  //         Point-and-click a tabela transborda a moldura em 34,1px e cai
  //         inteira sobre as linhas de Velocidade, com a caixa intacta e nada
  //         para fora dela. Sem esta conta a régua dava VERDE nessa mordida.
  //         Só conta quem está EM FLUXO (o `.dica` e o `.confirma` são
  //         posicionados, e sobrepor é o trabalho deles) e cujo pai não corta:
  //         pai que corta já responde pelas contas de rolagem e de recorte.
  const transborda = {};
  tela.querySelectorAll('*').forEach(e => {
    const s = getComputedStyle(e);
    if (s.position !== 'static' && s.position !== 'relative') return;
    if (e.closest(cfg.foraDeProposito) || e.closest('.confirma')) return;
    const p = e.parentElement;
    if (!p || p === tela) return;
    const ps = getComputedStyle(p);
    if (ps.overflowY !== 'visible' || ps.overflowX !== 'visible') return;
    const r = e.getBoundingClientRect(), pr = p.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return;
    const fora = Math.max(pr.top - r.top, r.bottom - pr.bottom,
                          pr.left - r.left, r.right - pr.right);
    const quem = (e.className || e.tagName).toString().split(' ')[0]
               + ' dentro de ' + (p.className || p.tagName).toString().split(' ')[0];
    if (fora > 2) transborda[quem] = Math.max(transborda[quem] || 0, R(fora));
  });
  for (const [quem, fora] of Object.entries(transborda))
    erros.push(`"${quem}" TRANSBORDA ${fora}px e o pai não corta nem rola — `
             + `o conteúdo pinta por cima do que vem depois`);

  // ---- 6b: DICA DENTRO DE QUEM CORTA. É uma conta própria, e não um caso da
  //          conta 6, porque o tamanho não tem nada com o defeito: um ancestral
  //          com `overflow:auto` RECORTA todo descendente absoluto, role ou não,
  //          e a dica sai cortada mesmo cabendo folgada na janela. É a cicatriz
  //          que o `CSS_POPUP` já traz escrita — "não há uma só dica dentro
  //          dela" — e que era regra de comentário sem régua nenhuma atrás.
  //          MEDIDO em 29/08: a `#mapear-entradas` nasceu com quatro dicas
  //          dentro da `.moldura`; a conta 6 pegou porque somavam 762,5px de
  //          envelope, e teria deixado passar a que sobrasse sozinha (747,8).
  tela.querySelectorAll(cfg.foraDeProposito).forEach(d => {
    let p = d.parentElement, corta = null;
    while (p && p !== tela) { if (clipa.has(p)) { corta = p; break; } p = p.parentElement; }
    if (!corta) return;
    const quem = (corta.className || corta.tagName).toString().split(' ')[0];
    erros.push(`uma "${cfg.foraDeProposito}" mora dentro de "${quem}", que CORTA: `
             + `overflow recorta todo descendente absoluto, role ou não, e ela `
             + `aparece cortada. O lugar dela é fora do que rola.`);
  });

  // ---- 6: o ENVELOPE (caixa + o que abre para fora) cabe na janela?
  const ew = env.right - env.left, eh = env.bottom - env.top;
  if (ew > jr.width + 0.5 || eh > jr.height + 0.5)
    erros.push(`o envelope (caixa mais o que abre para fora) mede ${R(ew)}×${R(eh)}px `
             + `e a janela do produto tem ${R(jr.width)}×${R(jr.height)}`);

  // O RODAPÉ NO PRODUTO, projetado: a pop-up centrada na janela de verdade, e
  // não no viewport do navegador, que é onde o `position:fixed` do mockup a põe.
  const rod = tela.querySelector('.tn-rod');
  const topoNoProduto = (jr.height - cr.height) / 2;
  const rodNoProduto = rod
    ? R(topoNoProduto + (rod.getBoundingClientRect().bottom - cr.top)) : null;

  return {
    erros, notas,
    janela: {w: R(jr.width), h: R(jr.height)},
    caixa: {w: R(cr.width), h: R(cr.height), teto: getComputedStyle(cx).maxHeight},
    envelope: {w: R(ew), h: R(eh),
               sai_esq: R(cr.left - env.left), sai_dir: R(env.right - cr.right),
               sai_cima: R(cr.top - env.top), sai_baixo: R(env.bottom - cr.bottom)},
    rod_no_produto: rodNoProduto,
    rolam
  };
}
"""


def alvos_de(arq: pathlib.Path):
    """Os `id` de toda `.tela-nova` do arquivo, na ordem em que aparecem."""
    return re.findall(r'class="tela-nova"\s+id="([^"]+)"', arq.read_text())


def mede(pg, arq, ident, css_extra=""):
    # `about:blank` ANTES, e não é zelo: trocar só o FRAGMENTO da mesma URL é
    # navegação no mesmo documento — o Chrome não recarrega nada, e todo
    # `add_style_tag` da pop-up anterior continua valendo na seguinte. Foi a
    # própria mordida que revelou: sabotada a #definicoes-mouse, as duas telas
    # medidas depois dela reprovavam "sem sabotagem nenhuma", porque a
    # sabotagem tinha viajado junto. Uma régua com esse vazamento acusaria
    # defeito na pop-up errada — ou, na ordem inversa, daria verde na certa.
    pg.goto("about:blank")
    pg.goto(f"file://{D / arq}#{ident}")
    pg.wait_for_load_state("networkidle")
    # As dicas nascem `display:none` e só aparecem no hover. Elas entram no
    # envelope, então a régua as ACENDE por CSS — nunca por `hover()` do
    # Playwright, que faz `scrollIntoViewIfNeeded` antes e cega toda medição de
    # posição feita depois (cicatriz de 27/08).
    pg.add_style_tag(content=".tela-nova:target .dica{display:block !important}")
    if css_extra:
        pg.add_style_tag(content=css_extra)
    pg.wait_for_timeout(250)
    return pg.evaluate(SONDA, {"respiro": RESPIRO, "foraDeProposito": FORA_DE_PROPOSITO})


def relata(arq, ident, o):
    if o.get("erro"):
        print(f"   ✗ #{ident}: {o['erro']}")
        return True
    print(f"   #{ident}: caixa {o['caixa']['w']}×{o['caixa']['h']}px "
          f"(teto {o['caixa']['teto']}) · envelope {o['envelope']['w']}×{o['envelope']['h']} "
          f"· rodapé fecha em y={o['rod_no_produto']} da janela de {o['janela']['h']}")
    for r in o["rolam"]:
        print(f"      rola por dentro: \"{r['quem']}\" mostra {r['vao']} de "
              f"{r['conteudo']}px (esconde {r['esconde']})")  # (noqa-acento): chave do JSON da sonda
    if not o["rolam"]:
        print("      não rola nada por dentro — cabe inteira")
    for e in o["erros"]:
        print(f"      ✗ {e}")
    return bool(o["erros"])


# ---------------------------------------------------------------------------
# AS MORDIDAS. Cada uma é um defeito REAL que a pop-up pode ganhar, e a régua
# tem de reprovar as três. A primeira é a que o enunciado pediu; as outras duas
# são os dois modos de perder conteúdo em silêncio, que é o defeito que o teto
# de altura curou em 28/08 sem nenhuma régua olhando.
# ---------------------------------------------------------------------------
#
# AS DUAS ÚLTIMAS FORAM GENERALIZADAS EM 29/08, e o motivo é medido: escritas
# para a Navegação, elas assumiam uma pop-up ALTA e com `.tab` dentro. Contra as
# três telas da cerimônia da Conexões — 351 a 392px, sem tabela nenhuma — o teto
# de 400px não punha nada para fora e a regra da tabela não achava alvo: as duas
# davam VERDE por não terem sabotado coisa alguma, e o `--morde` acusava a régua
# de não morder quando quem não mordia era a mordida. Sabotagem que não alcança
# a página é pior que sabotagem nenhuma — ela ENSINA que a régua está furada.
MORDIDAS = [
    ("caixa de 2000px de altura",
     ".tn-cx{max-height:none !important;height:2000px !important}"),
    # 200 e não 400: tem de ficar abaixo da MENOR pop-up desta casa (351,2px na
    # `#mapear-entrada-a-entrada`), senão não sobra nada para pôr para fora.
    ("teto de 200px com a rolagem arrancada",
     ".tn-cx{max-height:200px !important} "
     ".tn-corpo>.moldura{overflow-y:visible !important}"),
    # o primeiro filho da moldura, e não `.tab`: na Navegação ele É a tabela, na
    # Conexões é o cartão do passo. Uma regra alcança as duas formas.
    ("conteúdo mais largo que a caixa",
     ".tn-cx .moldura > *:first-child{width:1400px !important;"
     "table-layout:fixed !important;flex:0 0 1400px !important}"),
    # a cicatriz do `CSS_POPUP` virou conta (6b) em 29/08: basta um ancestral que
    # corte para a dica sair recortada, e o tamanho dela não tem nada com isso.
    # `auto` e NÃO `hidden`: com `hidden` quem reprova é a conta do recorte mudo,
    # e a mordida provaria a conta errada. Com `auto` o `.tn-topo` passa a cortar
    # sem esconder nada dele próprio, e só a 6b tem o que dizer.
    ("dica dentro de quem corta",
     ".tn-topo{overflow:auto !important}"),
]


def morde(pg, arq, ident):
    """Sabota, exige reprovação, e devolve True se ALGUMA mordida passou verde."""
    falhou = False
    limpo = mede(pg, arq, ident)
    if limpo.get("erro") or limpo["erros"]:
        print(f"   ✗ a mordida não vale: #{ident} já reprova SEM sabotagem")
        return True
    print(f"   #{ident} limpa: verde (é daqui que a mordida parte)")
    for nome, css in MORDIDAS:
        o = mede(pg, arq, ident, css)
        if o.get("erro") or not o["erros"]:
            print(f"      ✗ MORDIDA IGNORADA — {nome}: a régua deu VERDE")
            falhou = True
        else:
            print(f"      ✓ mordida pega — {nome}: {o['erros'][0]}")
    return falhou


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mordendo = "--morde" in sys.argv
    arquivos = args or sorted(p.name for p in D.glob("[0-9][0-9]-*.html"))
    ruim = False
    with sync_playwright() as pw:
        # SEM `--hide-scrollbars`: o Playwright liga essa bandeira por padrão, e
        # ela esconde a barra que é a única prova de que algo rola por dentro.
        b = pw.chromium.launch(executable_path="/usr/bin/google-chrome",
                               args=["--no-sandbox"],
                               ignore_default_args=["--hide-scrollbars"])
        pg = b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        for arq in arquivos:
            ids = alvos_de(D / arq)
            print(f"\n=== {arq} === {len(ids)} pop-up(s)")
            if not ids:
                print("   sem `.tela-nova` nesta aba")
                continue
            for ident in ids:
                ruim = (morde(pg, arq, ident) if mordendo
                        else relata(arq, ident, mede(pg, arq, ident))) or ruim
        b.close()
    if mordendo:
        print("\n" + ("REPROVADO — alguma sabotagem passou verde: a régua não morde"
                      if ruim else
                      "OK — toda sabotagem foi reprovada, e a página limpa passou"))
    else:
        print("\n" + ("REPROVADO" if ruim
                      else "OK — toda pop-up cabe na janela do produto"))
    sys.exit(1 if ruim else 0)
