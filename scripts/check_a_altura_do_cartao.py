#!/usr/bin/env python3
"""PORTÃO — o cartão de controle cabe na caixa, e o texto dele não é cortado."""
import pathlib
import sys

from playwright.sync_api import sync_playwright

R = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import chrome_sem_rede as _rede

from hefesto_dualsense4unix.interface import aba02 as _aba02
from hefesto_dualsense4unix.interface import onde as _onde

LARGURAS = (1120, 1180, 1440)

CHROME = _rede.CHROME

FOLGA_DO_TEXTO = 0.5

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


def medir(caminho: pathlib.Path, larguras: tuple[int, ...] | int) -> dict:
    """Abre a página em cada largura e devolve o que o navegador viu.

    Um navegador para as três larguras (o lançamento do Chrome era o grosso do
    custo), a rede recusada (`chrome_sem_rede`) e a espera pelo desenho assentado.
    Com uma largura só devolve o resultado dela; com várias, `{largura: resultado}`.
    """
    uma = isinstance(larguras, int)
    lista = (larguras,) if isinstance(larguras, int) else larguras
    saida: dict = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        try:
            for largura in lista:
                pg, _recusadas = _rede.abrir_sem_rede(
                    b, caminho.as_uri(), largura=largura, altura=1080,
                    device_scale_factor=1)
                try:
                    saida[largura] = pg.evaluate(
                        _MEDIR.replace("FOLGA", repr(FOLGA_DO_TEXTO)))
                finally:
                    pg.close()
        finally:
            b.close()
    return saida[lista[0]] if uma else saida


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
    vistos = medir(pagina, LARGURAS)
    for larg in LARGURAS:
        visto = vistos[larg]
        cartoes = visto["cartoes"]
        if not cartoes:
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
