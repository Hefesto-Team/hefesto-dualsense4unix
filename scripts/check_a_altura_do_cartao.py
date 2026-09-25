#!/usr/bin/env python3
"""PORTÃO — o cartão de controle cabe na caixa, e o texto dele não é cortado.

Entrega da `O-BOTAO-ENTREGA-O-QUE-PROMETE-01` (20/09/2026). Ela nasceu de uma
troca de rótulos que ela aprovou vendo a foto — *"ṕqp perfeito. vc mandou muito
bem. aprovadíssimo."* <!-- noqa-acento: citação literal dela --> —, e o que ela
guarda é o preço daquela aprovação: **a altura do cartão vira trava**. Mudança
futura que o faça crescer reprova aqui, em vez de aparecer na tela dela.

POR QUE ELA MEDE O RENDERIZADO, E NÃO O CSS ESCRITO
---------------------------------------------------
O CSS não diz quantas linhas um texto ocupa. Um rótulo maior, uma fonte que
troca, um `?` a mais na linha do rótulo — nenhum deles muda uma declaração de
altura, e todos mudam a altura do cartão. Por isso a régua abre a página num
Chrome sem janela e pergunta ao navegador.

**E ELA MEDE O TEXTO JUNTO, que é a metade que faz a outra morder.** Uma régua
que só olha pixels de altura tem uma saída fácil e errada: comprimir até o
texto cortar. Foi para fechar essa porta que o teto de altura veio acompanhado
da medição de corte — os dois numa régua só, porque separados cada um paga o
preço do outro.

**O DETECTOR INGÊNUO NÃO SERVE, e o número é medido:** `scrollHeight >
clientHeight` (com o irmão de largura) acusa **13** elementos desta página, a
1180px, com o desenho inteiramente certo — o nome do cartão, os dois trilhos de
volume de cada controle, a caixa do touchpad e a dos analógicos. Nenhum deles
tem texto cortado; o que eles têm é filho que passa do pai por desenho. A
sprint que encomendou esta régua contou **14** na página de antes do
empilhamento, e a diferença é só o desenho que mudou no meio: o defeito do
detector é o mesmo nos dois números.

O que mede corte de verdade é comparar a largura NATURAL do texto, tirada do
canvas com a fonte computada daquele elemento, contra a largura interna da
caixa. É o que esta régua faz.

QUEM É O DONO DO NÚMERO
-----------------------
`interface/aba02.PARA_O_CARD` — o orçamento que a caixa da aba reserva para o
cartão aberto, e que o próprio gerador já usa num `assert`. **A régua PERGUNTA
ao dono** em vez de digitar 328: valor com dono digitado numa segunda régua é
como as duas divergem no dia em que a caixa mudar de tamanho.

A PÁGINA QUE ELA MEDE É A BANCADA (`mockup/`), e é de propósito. O publicado é
a página CONGELADA até ela aprovar a aba; apontar a régua para lá daria verde
sobre o desenho de ontem — a armadilha mais cara de
`docs/method/COMO-OLHAR-A-TELA.md`, que reincidiu quatro vezes só em 31/08.
O `--publicado` existe para quem quiser medir o produto depois de publicar.

    scripts/check_a_altura_do_cartao.py              # a bancada
    scripts/check_a_altura_do_cartao.py --publicado  # o que o produto renderiza
"""
import pathlib
import sys

from playwright.sync_api import sync_playwright

# A RAIZ SAI DE `__file__`, NUNCA CRAVADA — a mesma razão do
# `check_pecas_do_dualsense.py`: uma cópia desta árvore rodando com o caminho
# da árvore DELA já reescreveu o mockup dela uma vez.
R = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / "src"))

from hefesto_dualsense4unix.interface import aba02 as _aba02
from hefesto_dualsense4unix.interface import onde as _onde

#: A janela do produto abre com 1180px por dentro (`interface/olhar.py`), e é
#: nessa largura que a conta de `PARA_O_CARD` foi feita. As outras duas são as
#: bordas do intervalo em que a aba já quebrou: 1120 é onde a fileira de três
#: transbordava a coluna em 12/09, e 1440 é a janela dela numa tela cheia.
LARGURAS = (1120, 1180, 1440)

#: O Chrome do sistema, sem baixar navegador — a mesma escolha dos outros dois
#: portões de Playwright desta casa. `launch()` sem `headless=False` não abre
#: janela nenhuma na tela dela.
CHROME = "/usr/bin/google-chrome"

#: Quanto o texto pode passar da caixa antes de a régua chamar de corte. Não é
#: folga de gosto: `measureText` e o layout do Chrome arredondam diferente, e
#: sub-pixel de diferença num rótulo que cabe daria falso positivo em toda
#: execução. Meio pixel é menor que qualquer letra.
FOLGA_DO_TEXTO = 0.5

# A MEDIÇÃO INTEIRA MORA NUMA EXPRESSÃO SÓ, e ela roda DENTRO da página: o que
# volta para o Python já são números. Medir daqui pediria uma viagem de IPC por
# elemento, e são centenas.
#
# O `measureText` recebe a fonte COMPUTADA daquele elemento (`font-style`,
# `font-weight`, `font-size` e `font-family`, nessa ordem, que é a forma curta
# que o canvas aceita). Digitar a fonte aqui faria a régua medir uma tela que
# não é esta no dia em que a folha trocar de família.
_MEDIR = r"""() => {
  const cv = document.createElement('canvas');
  const ctx = cv.getContext('2d');
  const fonte = (cs) =>
    `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
  const cartoes = [];
  for (const c of document.querySelectorAll('.ctl.card')) {
    if (c.classList.contains('off')) continue;   // linha fechada: não é cartão
    cartoes.push({id: c.dataset.controle || '?',
                  h: Math.round(c.getBoundingClientRect().height * 100) / 100});
  }
  // O TEXTO QUE SE MEDE É O DE UMA LINHA SÓ. Quem pode quebrar em duas não é
  // cortado quando o texto cresce — ele desce, e quem denuncia isso é a altura
  // do cartão, que esta mesma régua já mede. Medir os dois pelo mesmo critério
  // é como nascem os falsos positivos que o cabeçalho descreve.
  const cortados = [];
  for (const el of document.querySelectorAll('.ctl.card:not(.off) *')) {
    if (!el.firstChild || el.children.length) continue;      // só folha de texto
    const t = (el.textContent || '').trim();
    if (!t) continue;
    const cs = getComputedStyle(el);
    if (cs.whiteSpace !== 'nowrap' && cs.whiteSpace !== 'pre') continue;
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const cx = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
    const dentro = el.clientWidth - cx;
    if (dentro <= 0) continue;                               // não está no fluxo
    ctx.font = fonte(cs);
    const natural = ctx.measureText(t).width;
    if (natural > dentro + FOLGA) {
      cortados.push({texto: t.slice(0, 60),
                     onde: el.tagName.toLowerCase() +
                           (el.className ? '.' + String(el.className).split(' ')[0] : ''),
                     pede: Math.round(natural * 10) / 10,
                     cabe: Math.round(dentro * 10) / 10});
    }
  }
  return {cartoes, cortados};
}"""


def medir(caminho: pathlib.Path, largura: int) -> dict:
    """Abre a página numa janela de `largura` e devolve o que o navegador viu."""
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": largura, "height": 1080},
                        device_scale_factor=1)
        pg.goto(caminho.as_uri())
        pg.wait_for_load_state("networkidle")
        pg.wait_for_timeout(250)
        visto = pg.evaluate(_MEDIR.replace("FOLGA", repr(FOLGA_DO_TEXTO)))
        b.close()
    return visto


def main(argv: list[str]) -> int:
    publicado = "--publicado" in argv
    pagina = _onde.pagina("02-controles.html", publicado=publicado)
    teto = _aba02.PARA_O_CARD
    if not pagina.exists():
        print(f"ERRO: a página não está no disco — {pagina}")
        return 1

    print(f"=== a altura do cartão · {pagina.name} "
          f"({'publicado' if publicado else 'bancada'}) · teto {teto}px ===")
    falhas: list[str] = []
    for larg in LARGURAS:
        visto = medir(pagina, larg)
        cartoes = visto["cartoes"]
        if not cartoes:
            # RÉGUA QUE ACHA ZERO É ERRO, NÃO SILÊNCIO — regra desta casa, e a
            # aba 02 já a pagou: um seletor que deixou de casar publicou
            # sucesso sobre nada.
            falhas.append(f"{larg}px: nenhum cartão aberto na página — o "
                          f"seletor `.ctl.card:not(.off)` não casa mais nada")
            continue
        alto = max(cartoes, key=lambda c: c["h"])
        marca = "OK " if alto["h"] <= teto else "NÃO"
        print(f"  {marca} {larg}px · o mais alto é o {alto['id']} com "
              f"{alto['h']}px ({len(cartoes)} aberto(s))")
        if alto["h"] > teto:
            falhas.append(
                f"{larg}px: o cartão {alto['id']} mede {alto['h']}px e a caixa "
                f"reserva {teto} (`aba02.PARA_O_CARD`) — a aba passa a rolar "
                f"por dentro e o último controle sai da tela")
        for c in visto["cortados"]:
            falhas.append(
                f"{larg}px: o texto {c['texto']!r} ({c['onde']}) pede "
                f"{c['pede']}px e a caixa dá {c['cabe']} — ele sai cortado")

    if falhas:
        print("\nERRO — o cartão não cabe, ou o texto dele não cabe:")
        for f in falhas:
            print(f"  - {f}")
        print("\n  O teto tem dono: `interface/aba02.PARA_O_CARD`. Se a caixa\n"
              "  mudou de tamanho, o número muda LÁ e esta régua o segue.")
        return 1
    print("OK — o cartão cabe nas três larguras e nenhum rótulo sai cortado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
