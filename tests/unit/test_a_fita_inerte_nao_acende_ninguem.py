#!/usr/bin/env python3
"""A RÉGUA DO CHIP: numa fita que não escolhe, todos os chips estão acesos e iguais.

MEDIDA NOVA, 09/10/2026 (O-SELECIONAR-ACENDE-QUEM-ESTA-ESCOLHIDO-01). A régua de
08/09 dizia o contrário: «o marcado é cinza como os demais», a pedido dela na aba
Gatilhos (*"conseguimos deixar ele cinza como os demais?"*, citação dela, sem o
acento onde faltava). Em 29/09 ela revogou o cinza: *"a cor de todos os botões do
Selecionar deveriam estar acesas e com as bordas corretas"* (noqa-acento: citação
literal dela). Quem leu o pedido de 08/09 certo foi esta régua; o que mudou foi o
pedido. O que NÃO mudou: numa aba que não escolhe, ninguém se destaca sozinho, e o
chip não leva a lugar nenhum (sem endereço de clique).

O QUE ELA MEDE, e por que é a COR COMPUTADA
--------------------------------------------
Ela abre as páginas do DESENHO (``mockup/``, que o gerador reescreve; o publicado
só muda no ``--publicar`` da costura) num Chrome de verdade e pergunta ao motor o que
ele desenha. **Nenhuma cor está escrita aqui.** A comparação é entre chips da MESMA
fita: cada um contra os irmãos, no fundo, na cor do texto e no peso da letra. A borda
fica de fora de propósito: cada controle leva a do seu plástico.

Uma régua que lesse o texto do CSS mediria o arquivo que a cura editou, e daria
verde sobre a própria edição. É a família de defeito que esta casa mais paga.

A prova de que ela ENXERGA o aceso: ``test_o_apagado_tem_outra_cara`` tira o ``on``
de um chip e exige que a cara mude. Sem ela, «todos iguais» passaria também sobre
uma folha que apagasse tudo.

A MORDIDA
---------
Devolva as regras antigas ao ``interface/topo.html``::

    .fita.inerte .chip{border-color:var(--border-sutil);background:transparent;
                       color:var(--comment)}
    .fita.inerte .chip.on{border-color:var(--border-sutil);background:transparent;
                          color:var(--comment);font-weight:400}

e regere (``aba03.py``): o chip aceso da Gatilhos perde fundo, cor e peso, e caem os
casos de «todos acesos» e de «a mesma cara».
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

CHROME = pathlib.Path("/usr/bin/google-chrome")

DESENHO = RAIZ / "mockup"

O_QUE_O_MOTOR_DESENHA = """() => {
  const f = document.querySelector('.fita');
  if (!f) return {erro: 'esta página não tem `.fita`'};
  const chips = [...f.querySelectorAll('.chip')].map(c => {
    const s = getComputedStyle(c);
    return {
      texto: (c.textContent || '').trim(),
      marcado: c.classList.contains('on'),
      plastico: c.classList.contains('plastico'),
      // o que uma pessoa VÊ no chip, menos a borda (cada plástico tem a sua)
      cara: [s.backgroundColor, s.color, s.fontWeight].join(' | '),
      // o endereço do clique: numa fita inerte ele tem de ser VAZIO
      gesto: c.dataset.gesto || '',
    };
  });
  return {inerte: f.classList.contains('inerte'), chips};
}"""


def _abas_do_desenho() -> list[pathlib.Path]:
    return sorted(DESENHO.glob("[0-9][0-9]-*.html"))


@pytest.fixture(scope="module")
def medido() -> dict:
    """A fita de cada aba publicada, medida no Chrome — uma abertura para todas."""
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    paginas = _abas_do_desenho()
    assert len(paginas) >= 10, (
        f"achei {len(paginas)} abas do desenho em {DESENHO} — o caminho mudou? "
        f"Uma régua de tela que mede zero página passa sobre tudo.")

    from playwright.sync_api import sync_playwright

    fora: dict = {}
    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = nav.new_page(viewport={"width": 1600, "height": 900})
            for p in paginas:
                pg.goto(p.as_uri())
                pg.wait_for_load_state("networkidle")
                fora[p.name] = pg.evaluate(O_QUE_O_MOTOR_DESENHA)
        finally:
            nav.close()
    return fora


def _inertes(medido: dict) -> list[tuple[str, dict]]:
    return [(n, r) for n, r in medido.items() if r.get("inerte")]


def test_as_abas_de_fita_inerte_continuam_sendo_sete(medido: dict) -> None:
    """Sete das dez não escolhem controle, e a lista tem UM dono."""
    import monta

    inertes = {n for n, _ in _inertes(medido)}
    esperadas = {p.name for p in _abas_do_desenho()
                 if p.stem not in monta.ABAS_QUE_ESCOLHEM}
    assert inertes == esperadas, (
        f"a fita inerte e a lista do `monta` discordam.\n"
        f"  a folha diz inerte em: {sorted(inertes)}\n"
        f"  `ABAS_QUE_ESCOLHEM` implica: {sorted(esperadas)}")
    assert len(inertes) == 7, f"esperava sete abas de fita inerte, achei {len(inertes)}"


def test_todo_chip_da_fita_inerte_esta_aceso(medido: dict) -> None:
    """Nas sete abas, ninguém fica apagado: a aba vale para os quatro."""
    apagados = [(n, c["texto"]) for n, r in _inertes(medido)
                for c in r["chips"] if not c["marcado"]]
    assert not apagados, f"chip apagado numa fita que não escolhe: {apagados}"


def test_os_chips_da_fita_inerte_tem_a_mesma_cara(medido: dict) -> None:
    """Fundo, cor do texto e peso da letra iguais em todos os chips da fita."""
    ruins = []
    for nome, r in _inertes(medido):
        caras = {c["cara"] for c in r["chips"]}
        if len(caras) != 1:
            ruins.append(f"{nome}: {len(caras)} aparências: " + "; ".join(
                f"{c['texto']!r} → {c['cara']}" for c in r["chips"]))
    assert not ruins, (
        "numa fita que não escolhe, os chips acesos têm de ser iguais:\n  "
        + "\n  ".join(ruins))


def test_a_fita_inerte_nao_oferece_clique_em_chip_nenhum(medido: dict) -> None:
    """E o chip continua sem endereço — a cura não pode virar a mentira seguinte."""
    com_gesto = [(n, c["texto"]) for n, r in _inertes(medido)
                 for c in r["chips"] if c["gesto"]]
    assert not com_gesto, (
        f"chip de fita inerte com endereço de clique: {com_gesto}. "
        f"Nessas abas o chip não escolhe coisa alguma, e um `data-gesto` ali "
        f"faz a tela oferecer uma escolha sem destino.")


def test_o_apagado_tem_outra_cara() -> None:
    """Tira o `on` de um chip e remede: a régua tem de ENXERGAR a diferença."""
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    alvo = DESENHO / "03-gatilhos.html"
    assert alvo.is_file(), f"{alvo} sumiu — é a aba em que ela viu o defeito"

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = nav.new_page(viewport={"width": 1600, "height": 900})
            pg.goto(alvo.as_uri())
            pg.wait_for_load_state("networkidle")
            pg.evaluate("""() => {
              const plastico = [...document.querySelectorAll('.fita .chip')]
                .find(c => c.classList.contains('plastico'));
              plastico.classList.remove('on');
            }""")
            r = pg.evaluate(O_QUE_O_MOTOR_DESENHA)
        finally:
            nav.close()

    assert len(r["chips"]) >= 3, "a fita do desenho tem de ter o Todos e dois controles"
    apagado = [c for c in r["chips"] if not c["marcado"]]
    assert len(apagado) == 1, "o `on` não saiu do chip do plástico"
    acesos = {c["cara"] for c in r["chips"] if c["marcado"]}
    assert len(acesos) == 1 and apagado[0]["cara"] not in acesos, (
        "o chip apagado tem a mesma cara dos acesos: a régua não enxerga o aceso, "
        "e «todos iguais» passaria sobre uma folha que apagasse tudo.\n"
        f"    apagado: {apagado[0]['cara']}\n    acesos: {sorted(acesos)}")
