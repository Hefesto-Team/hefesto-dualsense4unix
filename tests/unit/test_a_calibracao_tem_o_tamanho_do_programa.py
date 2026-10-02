#!/usr/bin/env python3
"""A tela Calibrar tem a largura e a altura das abas — A-CALIBRACAO-TEM-O-TAMANHO-DO-PROGRAMA-01."""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import olhar

CHROME = pathlib.Path("/usr/bin/google-chrome")
PAGINA = "calibrar-sensores.html"
ABA_VIZINHA = "02-controles.html"

FOLGA = 2

PISO = (1212, 809)

VISTAS = {"piso": PISO, "dela": olhar.VISTA_DELA, "ladrilhada": (PISO[0], 700),
          "baixa": (PISO[0], 480)}


def _controle(i: int, via: str) -> dict[str, Any]:
    """Um controle na forma que o piloto entrega ao gerador (`ctx.mesa`)."""
    cores = ("cosmic-red", "starlight-blue", "galactic-purple", "white")
    return {"pref": f"p{i + 1}", "jogador": i + 1, "cor": cores[i],
            "nome": cores[i].replace("-", " ").title(), "via": via.upper(),
            "transporte": via}


MESAS: dict[str, list[dict[str, Any]]] = {
    "nenhum": [],
    "um-no-cabo": [_controle(0, "usb")],
    "um-no-radio": [_controle(0, "bt")],
    "quatro": [_controle(0, "usb"), _controle(1, "bt"),
               _controle(2, "usb"), _controle(3, "bt")],
}

MEDIR = """() => {
  const c = document.querySelector('.janela') || document.querySelector('.cx');
  if (!c) return {erro: 'nem .janela nem .cx nesta página'};
  const r = c.getBoundingClientRect(), d = document.documentElement;
  // O FIM SE ALCANÇA: rola o miolo até o fim e vê se o rodapé e a última
  // linha (o aviso) cabem na caixa. Sem a rolagem por dentro, o que não cabe
  // some cortado pela borda, calado.
  const miolo = c.querySelector('.corpo');
  if (miolo) { miolo.scrollTop = miolo.scrollHeight; }
  const cabe = el => { if (!el) { return false; } const e = el.getBoundingClientRect();
                       return e.bottom <= r.bottom + 1 && e.top >= r.top - 1; };
  // O RODAPÉ NO FIM DA CAIXA: com o miolo rolado até o fim, o que sobra entre
  // a última linha e a borda de baixo é só o recuo do miolo e a borda. A
  // altura que a caixa ganhou vira vão ACIMA do rodapé, nunca abaixo do aviso.
  const folga = miolo ? {
    embaixo: Math.round(r.bottom - miolo.lastElementChild.getBoundingClientRect().bottom),
    esperada: Math.round(parseFloat(getComputedStyle(miolo).paddingBottom)
                         + parseFloat(getComputedStyle(c).borderBottomWidth))} : null;
  return {fim_alcancavel: miolo ? cabe(c.querySelector('.rodape'))
                                  && cabe(miolo.lastElementChild) : null,
          folga: folga,
          x: Math.round(r.left), y: Math.round(r.top),
          largura: Math.round(r.width), altura: Math.round(r.height),
          embaixo: Math.round(r.bottom), vista: [innerWidth, innerHeight],
          rola_de_lado: d.scrollWidth > d.clientWidth,
          rola_a_pagina: d.scrollHeight > d.clientHeight,
          cartoes: document.querySelectorAll('[data-bloco="controles"] .ctr').length};
}"""


@pytest.fixture(scope="module")
def calibrar_mod() -> Any:
    import calibrar
    return calibrar


@pytest.fixture(scope="module")
def medido(calibrar_mod: Any) -> dict[str, dict[str, Any]]:
    """Por vista: a caixa da aba vizinha e a da Calibrar em cada mesa."""
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    from playwright.sync_api import sync_playwright

    import onde

    from hefesto_dualsense4unix.interface.folha_da_casa import seletores_escondidos

    aba = onde.pagina(ABA_VIZINHA)
    calibrar = onde.pagina(PAGINA)
    assert aba.exists() and calibrar.exists(), (
        f"a bancada não tem {ABA_VIZINHA} e {PAGINA} — o caminho mudou? Uma "
        f"régua de tamanho que não abre página passa sobre tudo.")
    esconde = "".join(f"{s}{{display:none}}" for s in seletores_escondidos())

    fora: dict[str, dict[str, Any]] = {}
    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"],
                                 ignore_default_args=["--hide-scrollbars"])
        try:
            for vista, (larg, alt) in VISTAS.items():
                pg = nav.new_page(viewport={"width": larg, "height": alt})
                lido: dict[str, Any] = {}
                for nome, alvo in (("aba", aba), ("dois", calibrar)):
                    pg.goto(alvo.as_uri())
                    pg.wait_for_load_state("networkidle")
                    pg.add_style_tag(content=esconde)
                    lido[nome] = pg.evaluate(MEDIR)
                for nome, quem in MESAS.items():
                    pg.set_content(calibrar_mod.documento(quem))
                    pg.add_style_tag(content=esconde)
                    lido[nome] = pg.evaluate(MEDIR)
                fora[vista] = lido
                pg.close()
        finally:
            nav.close()
    return fora


CASOS = [(v, m) for v in VISTAS for m in ("dois", *MESAS)]


@pytest.mark.parametrize(("vista", "mesa"), CASOS)
def test_a_calibracao_tem_a_caixa_da_aba(medido: dict[str, Any], vista: str,
                                          mesa: str) -> None:
    """A caixa da Calibrar é a caixa da aba: largura, altura e lugar, ±2 px."""
    aba, cal = medido[vista]["aba"], medido[vista][mesa]
    assert "erro" not in aba and "erro" not in cal, (aba, cal)
    esperados = len(MESAS[mesa]) if mesa in MESAS else 2
    assert cal["cartoes"] == esperados, (
        f"a Calibrar ({mesa}) mostrou {cal['cartoes']} cartões e a mesa tem "
        f"{esperados} — a régua está medindo outra página")
    difere = {k: (cal[k], aba[k]) for k in ("largura", "altura", "x", "y")
              if abs(cal[k] - aba[k]) > FOLGA}
    assert not difere, (
        f"na vista {vista} ({mesa}), a caixa da Calibrar difere da da "
        f"{ABA_VIZINHA} em {difere} (calibrar, aba). É a queixa dela: *'altura "
        f"e largura de layout inferior'*. O tamanho mora no `topo.html` e a "
        f"Calibrar o lê por `calibrar.moldura()`.")


@pytest.mark.parametrize("vista", VISTAS)
def test_a_calibracao_nao_passa_da_vista(medido: dict[str, Any], vista: str) -> None:
    """A página não rola e o «Começar» se alcança: quem rola é o miolo, por dentro."""
    _, alt = VISTAS[vista]
    for mesa in ("dois", *MESAS):
        cal = medido[vista][mesa]
        assert not cal["rola_a_pagina"] and not cal["rola_de_lado"], (
            f"na vista {vista} ({mesa}) a página da Calibrar rola: {cal}")
        assert cal["embaixo"] <= alt, (
            f"na vista {vista} ({mesa}) a caixa termina em {cal['embaixo']} e a "
            f"vista em {alt} — o rodapé sai pela borda de baixo")
        assert cal["fim_alcancavel"], (
            f"na vista {vista} ({mesa}) o fim da Calibrar (o rodapé com Começar e "
            f"Fechar, e o aviso) fica fora da caixa mesmo com o miolo rolado")


@pytest.mark.parametrize("vista", VISTAS)
def test_o_rodape_desce_para_o_fim_da_caixa(medido: dict[str, Any], vista: str) -> None:
    """O rodapé e o aviso terminam na borda de baixo da caixa, como o das abas."""
    for mesa in ("dois", *MESAS):
        folga = medido[vista][mesa]["folga"]
        assert folga and abs(folga["embaixo"] - folga["esperada"]) <= FOLGA, (
            f"na vista {vista} ({mesa}) sobram {folga and folga['embaixo']} px "
            f"entre o aviso e a borda de baixo da Calibrar, e o recuo do miolo "
            f"mais a borda são {folga and folga['esperada']} — o rodapé não "
            f"desceu para o fim da caixa")


def test_a_bancada_e_o_que_o_gerador_escreve(calibrar_mod: Any) -> None:
    """O arquivo da bancada é o que o gerador escreve hoje — ninguém esqueceu de regerar."""
    import monta
    import onde

    no_disco = onde.pagina(PAGINA).read_text(encoding="utf-8")
    assert no_disco == calibrar_mod.documento(monta.CONECTADOS), (
        f"`mockup/{PAGINA}` não é o que `calibrar.py` gera — rode "
        f"`python3 src/hefesto_dualsense4unix/interface/calibrar.py`")


def test_o_tamanho_vem_do_topo(calibrar_mod: Any) -> None:
    """Mude o teto da `.janela` no esqueleto e a Calibrar vai junto; tire-o e ela PARA."""
    import monta

    assert "min(100%,1600px)" in monta.TOPO, (
        "o teto da `.janela` mudou de forma no `topo.html` — esta régua mede o "
        "mundo de ontem")
    trocado = monta.TOPO.replace("min(100%,1600px)", "min(100%,1400px)")
    folha = calibrar_mod.moldura(trocado)
    assert "min(100%,1400px)" in folha and "1600px" not in folha, folha

    sem_janela = trocado.replace(".janela{", ".janela-que-sumiu{", 1)
    with pytest.raises(SystemExit):
        calibrar_mod.moldura(sem_janela)
