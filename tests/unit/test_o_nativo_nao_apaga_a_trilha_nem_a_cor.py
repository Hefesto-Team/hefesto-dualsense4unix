"""No Nativo, o deslizante guarda a trilha e o quadrado da cor guarda a cor.

Queixa, 29/10/2026 (fotos 10, 14, 15 e 16): no Nativo os deslizantes de Gatilhos
(«Intensidade do gatilho» e os quatro de «Criar efeitos novos») e o «Força da vibração»
mostravam só a bolinha, e os oito quadrados de «Cor» da Iluminação ficavam vazios.

A causa medida: a folha `monta.CSS_DO_NATIVO` tirava o clique e, na MESMA regra, punha
`appearance:none` e `background:transparent!important` em todo elemento com gesto. Num
`input[type=range]` isso apaga a trilha; no `.tom`, o `!important` vence a cor que mora no
`style` do próprio botão.

A régua mede o motor de verdade (Chrome) sobre as páginas PUBLICADAS, que são as que a
janela abre: com e sem `body.nativo`, cada deslizante e cada quadrado de cor têm de ter o
mesmo desenho, e no Nativo nenhum dos que têm gesto recebe clique.

MORDIDA (29/10/2026): devolver `input[type=range],.tom` ao corte, ou juntar de novo as duas
regras do `CSS_DO_NATIVO`, reprova `test_o_desenho_do_deslizante_e_da_cor_e_o_mesmo_no_nativo`
com o gesto e a aba nomeados.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import onde

RAIZ = Path(__file__).resolve().parents[2]
CHROME = Path("/usr/bin/google-chrome")

O_DESENHO = r"""
(nativo) => {
  document.body.classList.toggle('nativo', !!nativo);
  const visivel = (e) => { const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden'; };
  const ler = (e) => { const s = getComputedStyle(e);
    return {nome: (e.dataset.gesto || e.dataset.papel || e.className) + ':' +
                  (e.dataset.linha || e.dataset.campo || e.getAttribute('style') || ''),
            aparencia: s.appearance, fundo: s.backgroundColor, imagem: s.backgroundImage,
            acento: s.accentColor, clique: s.pointerEvents,
            gesto: !!(e.dataset.gesto || e.dataset.papel)}; };
  return {
    faixas: Array.from(document.querySelectorAll('input[type=range]')).filter(visivel).map(ler),
    tons: Array.from(document.querySelectorAll('.tom')).filter(visivel).map(ler),
  };
}
"""


def _por_controle() -> list[Path]:
    return sorted(p for p in onde.PUBLICADO.glob("*.html")
                  if '<body class="por-controle"' in p.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def medido() -> dict[str, dict[str, Any]]:
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema: a régua não tem motor")
    import sys

    from playwright.sync_api import sync_playwright

    sys.path.insert(0, str(RAIZ / "scripts"))
    try:
        import chrome_sem_rede
    finally:
        sys.path.remove(str(RAIZ / "scripts"))
    saida: dict[str, dict[str, Any]] = {}
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            for arquivo in _por_controle():
                pg, _ = chrome_sem_rede.abrir_sem_rede(
                    navegador, arquivo.as_uri(), largura=1212, altura=809)
                saida[arquivo.name] = {"normal": pg.evaluate(O_DESENHO, False),
                                       "nativo": pg.evaluate(O_DESENHO, True)}
        finally:
            navegador.close()
    return saida


def test_ha_o_que_medir(medido: dict[str, Any]) -> None:
    assert {"03-gatilhos.html", "04-iluminacao.html", "05-vibracao.html"} <= set(medido)
    assert len(medido["03-gatilhos.html"]["normal"]["faixas"]) >= 5
    assert len(medido["05-vibracao.html"]["normal"]["faixas"]) >= 4
    assert len(medido["04-iluminacao.html"]["normal"]["tons"]) >= 8


def test_o_desenho_do_deslizante_e_da_cor_e_o_mesmo_no_nativo(medido: dict[str, Any]) -> None:
    perdidos = []
    for pagina, m in medido.items():
        for tipo in ("faixas", "tons"):
            assert len(m["nativo"][tipo]) == len(m["normal"][tipo]), (pagina, tipo)
            for fora, dentro in zip(m["normal"][tipo], m["nativo"][tipo], strict=True):
                for chave in ("aparencia", "fundo", "imagem", "acento"):
                    if fora[chave] != dentro[chave]:
                        perdidos.append(
                            f"{pagina} {fora['nome']}: {chave} {fora[chave]} -> {dentro[chave]}")
    assert not perdidos, "no Nativo o desenho some:\n" + "\n".join(perdidos)


def test_no_nativo_o_deslizante_e_a_cor_seguem_sem_clique(medido: dict[str, Any]) -> None:
    vivos = [f"{pagina} {e['nome']}" for pagina, m in medido.items()
             for tipo in ("faixas", "tons") for e in m["nativo"][tipo]
             if e["gesto"] and e["clique"] != "none"]
    assert not vivos, f"no Nativo recebem clique: {vivos}"


def test_o_quadrado_da_cor_nao_e_transparente(medido: dict[str, Any]) -> None:
    vazios = [t["nome"] for m in medido.values() for modo in ("normal", "nativo")
              for t in m[modo]["tons"] if t["fundo"] in ("rgba(0, 0, 0, 0)", "transparent")]
    assert not vazios, f"quadrados de cor vazios: {vazios}"
