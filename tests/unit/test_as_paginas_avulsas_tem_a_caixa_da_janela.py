#!/usr/bin/env python3
"""As três páginas avulsas têm a caixa da janela — AS-PAGINAS-AVULSAS-TEM-A-CAIXA-DA-JANELA-01."""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
from typing import Any

import pytest

from tests.conftest import skip_sem_gi_real

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import caixa_da_janela
import olhar

CHROME = pathlib.Path("/usr/bin/google-chrome")
ABA = "02-controles.html"
AVULSAS = ("calibrar-sensores.html", "mapa-do-controle.html", "mapa-das-portas.html")

FOLGA = 2

PISO = (1212, 809)

VISTAS = {"piso": PISO, "dela": olhar.VISTA_DELA, "tv-inteira": (olhar.LARG, olhar.ALT),
          "ladrilhada": (PISO[0], 700), "baixa": (PISO[0], 480)}

FIM = """() => {
  const c = document.querySelector('.janela') || document.querySelector('.cx')
         || document.querySelector('.pagina');
  const miolo = c && c.querySelector(':scope > .corpo');
  if (!miolo) return {erro: 'a caixa não tem um .corpo que role por dentro'};
  miolo.scrollTop = miolo.scrollHeight;
  const fim = [...miolo.children].filter(e => e.getClientRects().length).reduce((a, b) =>
    b.getBoundingClientRect().bottom > a.getBoundingClientRect().bottom ? b : a);
  const r = c.getBoundingClientRect(), u = fim.getBoundingClientRect();
  return {alcancavel: u.bottom <= r.bottom + 1 && u.bottom > r.top,
          bloco_do_fim: fim.className, embaixo: Math.round(u.bottom),
          caixa_embaixo: Math.round(r.bottom),
          rola_por_dentro: miolo.scrollHeight > miolo.clientHeight};
}"""

LUGAR = """() => {
  const c = document.querySelector('.janela') || document.querySelector('.cx')
         || document.querySelector('.pagina');
  if (!c) return {erro: 'nem .janela, nem .cx, nem .pagina — não há lugar a ler'};
  const r = c.getBoundingClientRect();
  return {x: Math.round(r.left), y: Math.round(r.top),
          vao_da_direita: Math.round(window.innerWidth - r.right)};
}"""


@pytest.fixture(scope="module")
def medido() -> dict[str, dict[str, Any]]:
    """Por vista: a medida da aba e a de cada avulsa, na mesma aba do Chrome."""
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    from playwright.sync_api import sync_playwright

    import onde

    from hefesto_dualsense4unix.interface.folha_da_casa import seletores_escondidos

    paginas = {nome: onde.pagina(nome) for nome in (ABA, *AVULSAS)}
    faltam = [n for n, p in paginas.items() if not p.exists()]
    assert not faltam, (
        f"a bancada não tem {faltam} — o caminho mudou? Uma régua de tamanho "
        f"que não abre página passa sobre tudo.")
    esconde = "".join(f"{s}{{display:none}}" for s in seletores_escondidos())

    fora: dict[str, dict[str, Any]] = {}
    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"],
                                 ignore_default_args=["--hide-scrollbars"])
        try:
            for vista, (larg, alt) in VISTAS.items():
                pg = nav.new_page(viewport={"width": larg, "height": alt})
                lido: dict[str, Any] = {}
                for nome, alvo in paginas.items():
                    pg.goto(alvo.as_uri())
                    pg.wait_for_load_state("networkidle")
                    pg.add_style_tag(content=esconde)
                    lido[nome] = pg.evaluate(olhar.MEDIDA_NA_VISTA)
                    lido[nome]["lugar"] = pg.evaluate(LUGAR)
                    if nome != ABA:
                        lido[nome]["fim"] = pg.evaluate(FIM)
                fora[vista] = lido
                pg.close()
        finally:
            nav.close()
    return fora


CASOS = [(v, n) for v in VISTAS for n in AVULSAS]


@pytest.mark.parametrize(("vista", "nome"), CASOS)
def test_a_caixa_da_avulsa_e_a_da_janela(medido: dict[str, Any], vista: str,
                                         nome: str) -> None:
    """Tamanho e LUGAR: os da `.janela`, ±2 px."""
    aba, avulsa = medido[vista][ABA], medido[vista][nome]
    assert "erro" not in aba and "erro" not in avulsa, (aba, avulsa)
    assert "erro" not in aba["lugar"] and "erro" not in avulsa["lugar"], (aba, avulsa)
    assert aba["caixa"] == "janela", f"a {ABA} não mediu a `.janela`: {aba}"
    difere = {k: (avulsa[k], aba[k]) for k in ("larg", "alt", "vao_dos_lados", "morto_abaixo")
              if abs(avulsa[k] - aba[k]) > FOLGA}
    difere |= {k: (avulsa["lugar"][k], aba["lugar"][k]) for k in ("x", "y", "vao_da_direita")
               if abs(avulsa["lugar"][k] - aba["lugar"][k]) > FOLGA}
    assert not difere, (
        f"na vista {vista}, a caixa `.{avulsa['caixa']}` de {nome} difere da "
        f"`.janela` da {ABA} em {difere} (avulsa, aba). A palavra dela, 24/09: "
        f"*«segue a caixa da janela»*. A caixa mora no `topo.html`, e as "
        f"avulsas a pedem a `caixa_da_janela.moldura()`.")


@pytest.mark.parametrize(("vista", "nome"), CASOS)
def test_a_avulsa_rola_por_dentro(medido: dict[str, Any], vista: str, nome: str) -> None:
    """A página não rola; o `.corpo` rola, e o rodapé se alcança."""
    avulsa = medido[vista][nome]
    assert avulsa["passa_da_dobra"] == 0 and not avulsa["rolagem_lateral"], (
        f"na vista {vista}, {nome} rola a PÁGINA ({avulsa['passa_da_dobra']} px "
        f"abaixo da dobra, lateral={avulsa['rolagem_lateral']}). A palavra dela: "
        f"*«rolando por dentro»* — quem rola é o `.corpo` da caixa.")
    fim = avulsa["fim"]
    assert "erro" not in fim, f"{nome}: {fim['erro']}"
    assert fim["alcancavel"], (
        f"na vista {vista}, o fim de {nome} (`.{fim['bloco_do_fim']}`) termina em "
        f"{fim['embaixo']} e a caixa em {fim['caixa_embaixo']}, mesmo com o "
        f"`.corpo` rolado até o fim")


def test_a_vista_baixa_faz_as_tres_rolarem(medido: dict[str, Any]) -> None:
    """O CONTROLE DA RÉGUA DE CIMA: na vista baixa as três TÊM de rolar por dentro."""
    for pagina in AVULSAS:
        assert medido["baixa"][pagina]["fim"]["rola_por_dentro"], (
            f"na vista baixa ({VISTAS['baixa']}) o `.corpo` de {pagina} não rola — "
            f"ou a página encolheu, ou a régua está medindo outra coisa")


def test_as_tres_pedem_a_caixa_ao_mesmo_dono() -> None:
    """Mude o teto da `.janela` no esqueleto e a caixa vai junto; tire-a e ela PARA."""
    import calibrar

    import onde

    from hefesto_dualsense4unix.interface import pagina_do_mapa

    assert calibrar.moldura is caixa_da_janela.moldura, (
        "a Calibrar tem um leitor de caixa próprio de novo — a caixa tem UM dono")
    topo = caixa_da_janela.TOPO.read_text(encoding="utf-8")
    assert "min(100%,1600px)" in topo, (
        "o teto da `.janela` mudou de forma no `topo.html` — esta régua mede o "
        "mundo de ontem")
    trocado = topo.replace("min(100%,1600px)", "min(100%,1400px)")
    for caixa in (".cx", ".pagina"):
        folha = caixa_da_janela.moldura(trocado, caixa=caixa)
        assert f"{caixa}{{width:min(100%,1400px)" in folha and "1600px" not in folha, folha
    with pytest.raises(SystemExit):
        caixa_da_janela.moldura(trocado.replace(".janela{", ".janela-que-sumiu{", 1))

    do_mapa = onde.pagina("mapa-do-controle.html").read_text(encoding="utf-8")
    assert caixa_da_janela.moldura() in do_mapa, (
        "o `mockup/mapa-do-controle.html` não traz a caixa que o dono escreve hoje")
    assert caixa_da_janela.moldura(caixa=".pagina") in pagina_do_mapa.pagina(), (
        "o mapa das portas não traz a caixa que o dono escreve hoje")


@skip_sem_gi_real  # o gerador do mapa do controle importa o pacote das abas, que é do lado GTK
def test_a_bancada_e_o_que_os_geradores_escrevem(tmp_path: pathlib.Path) -> None:
    """Os dois mockups são o que `mapa.py` e `pagina_do_mapa.py` escrevem hoje."""
    import onde

    from hefesto_dualsense4unix.interface import pagina_do_mapa

    ambiente = dict(os.environ, HEFESTO_BANCADA=str(tmp_path), PYTHONPATH=str(RAIZ / "src"))
    r = subprocess.run([sys.executable, str(INTERFACE / "mapa.py")], capture_output=True,
                       text=True, timeout=180, env=ambiente, cwd=str(RAIZ))
    assert r.returncode == 0, r.stderr[-1200:]
    gerado = (tmp_path / "mapa-do-controle.html").read_text(encoding="utf-8")
    assert gerado == onde.pagina("mapa-do-controle.html").read_text(encoding="utf-8"), (
        "`mockup/mapa-do-controle.html` não é o que `mapa.py` gera — rode "
        "`python3 src/hefesto_dualsense4unix/interface/mapa.py`")
    no_disco = onde.pagina("mapa-das-portas.html").read_text(encoding="utf-8")
    assert pagina_do_mapa.pagina() == no_disco, (
        "`mockup/mapa-das-portas.html` não é o que `pagina_do_mapa.py` gera — rode "
        "`python3 -m hefesto_dualsense4unix.interface.pagina_do_mapa`")
