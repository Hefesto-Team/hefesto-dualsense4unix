#!/usr/bin/env python3
"""A RÉGUA DO CHIP: numa fita que não escolhe nada, o marcado é igual aos outros.

PEDIDO DELA, 08/09/2026, na aba Gatilhos, com os quatro DualSense na mesa. A
citação é palavra por palavra, inclusive onde falta acento — texto dela não se
corrige:

*"o player 1 tipo no caso cosmic red - cabo, fica sempre selecionado com borda
diferente mesmo nas abas que cada player tem sua propria config.  (noqa-acento)
conseguimos deixar ele cinza como os demais?"*

A HIPÓTESE ÓBVIA ESTAVA ERRADA, e é o que esta régua NÃO mede
--------------------------------------------------------------
*"A Gatilhos está na lista das que escolhem"* — falso. A lista é
``monta.ABAS_QUE_ESCOLHEM = {"01-jogar", "02-controles", "08-conexoes"}``, a
Gatilhos não está nela, a fita dela já nascia ``inerte``, e o produto estava
certo nessa parte. O defeito era da folha: ``.fita.inerte .chip.on`` devolvia ao
chip marcado uma borda própria, uma cor de texto mais clara e negrito, desfazendo
as duas regras logo acima que apagavam todos os chips.

O QUE ELA MEDE, e por que é a COR COMPUTADA
--------------------------------------------
Ela abre as páginas PUBLICADAS num Chrome de verdade e pergunta ao motor o que
ele desenha. **Nenhuma cor está escrita aqui.** A comparação é entre chips da
MESMA fita: o marcado contra os irmãos. Se a paleta da casa mudar, os dois mudam
juntos e a régua continua certa; se alguém devolver uma aparência própria ao
marcado, ela reprova — mesmo que a folha tenha sido reescrita de outro jeito.

Uma régua que lesse o texto do CSS mediria o arquivo que a cura editou, e daria
verde sobre a própria edição. É a família de defeito que esta casa mais paga.

E ELA MEDE O CASO DELA, QUE A PÁGINA ESTÁTICA NÃO TEM
------------------------------------------------------
Na página publicada o chip marcado é o ``Todos`` — o desenho nasce com o alvo em
"todos". **Na tela dela o marcado era o P1**, porque o alvo escolhido viaja
entre as abas e o piloto repinta a fita a cada tique. É o mesmo `.on` e a mesma
regra, mas afirmar isso sem medir seria a hipótese que abriu a sprint. Por isso
:func:`test_o_chip_do_plastico_marcado_tambem_fica_igual` MOVE o ``.on`` para o
chip do P1 — que é ``.chip.plastico`` e cai em outra regra de mesma
especificidade — e remede.

A MORDIDA
---------
Devolva a regra antiga ao ``interface/topo.html``::

    .fita.inerte .chip.on{border-color:var(--comment);background:transparent;
                          color:var(--texto-suave);font-weight:600}

regere e publique. Caem os três primeiros casos, com a borda e o peso do
marcado diferentes dos irmãos — que é exatamente o que ela viu.
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

#: O MESMO MOTOR DAS OUTRAS RÉGUAS DE TELA desta casa, e ele roda headless:
#: nenhuma janela nasce na tela dela.
CHROME = pathlib.Path("/usr/bin/google-chrome")

PUBLICADO = INTERFACE / "paginas"  # (noqa-acento) nome de PASTA; caminho não leva acento

#: O QUE O MOTOR RESPONDE sobre cada chip da fita. `borderTopWidth` entra junto
#: da cor porque a borda de 2px do plástico é a marca da peça VIVA: um chip que
#: perdesse a cor e guardasse a espessura continuaria diferente dos irmãos.
O_QUE_O_MOTOR_DESENHA = """() => {
  const f = document.querySelector('.fita');
  if (!f) return {erro: 'esta página não tem `.fita`'};
  const chips = [...f.querySelectorAll('.chip')].map(c => {
    const s = getComputedStyle(c);
    return {
      texto: (c.textContent || '').trim(),
      marcado: c.classList.contains('on'),
      plastico: c.classList.contains('plastico'),
      // o que uma pessoa VÊ, e nada além
      cara: [s.borderTopColor, s.borderTopWidth, s.backgroundColor,
             s.color, s.fontWeight].join(' | '),
      // o endereço do clique: numa fita inerte ele tem de ser VAZIO
      gesto: c.dataset.gesto || '',
    };
  });
  return {inerte: f.classList.contains('inerte'), chips};
}"""


def _abas_publicadas() -> list[pathlib.Path]:
    return sorted(PUBLICADO.glob("[0-9][0-9]-*.html"))


@pytest.fixture(scope="module")
def medido() -> dict:
    """A fita de cada aba publicada, medida no Chrome — uma abertura para todas.

    **RÉGUA QUE ACHA ZERO NÃO É RÉGUA VERDE.** Se a pasta mudar de lugar, ela
    reprova em vez de dar por boas nenhuma aba — o silêncio que esta casa já
    pagou quatro vezes num dia.
    """
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    paginas = _abas_publicadas()
    assert len(paginas) >= 10, (
        f"achei {len(paginas)} abas publicadas em {PUBLICADO} — o caminho mudou? "
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


# ---------------------------------------------------------------------------
# 1. AS SETE — sem esta contagem, tudo abaixo passaria por ausência
# ---------------------------------------------------------------------------
def test_as_abas_de_fita_inerte_continuam_sendo_sete(medido: dict) -> None:
    """Sete das dez não escolhem controle, e a lista tem UM dono.

    O número sai de `monta.ABAS_QUE_ESCOLHEM` (três) contra as dez. Ele está
    aqui para pegar o dia em que alguém mover uma aba de lado sem perceber: a
    cura do chip só alcança a fita inerte, e uma aba que saísse dessa metade
    sairia da cobertura desta régua EM SILÊNCIO.
    """
    import monta

    inertes = {n for n, _ in _inertes(medido)}
    esperadas = {p.name for p in _abas_publicadas()
                 if p.stem not in monta.ABAS_QUE_ESCOLHEM}
    assert inertes == esperadas, (
        f"a fita inerte e a lista do `monta` discordam.\n"
        f"  a folha diz inerte em: {sorted(inertes)}\n"
        f"  `ABAS_QUE_ESCOLHEM` implica: {sorted(esperadas)}")
    assert len(inertes) == 7, f"esperava sete abas de fita inerte, achei {len(inertes)}"


# ---------------------------------------------------------------------------
# 2. A CURA — o marcado tem a MESMA cara dos irmãos, nas sete
# ---------------------------------------------------------------------------
def test_o_chip_marcado_tem_a_mesma_cara_dos_irmaos(medido: dict) -> None:
    """Nas sete abas de fita inerte, todos os chips desenham igual.

    É a frase dela virada medida: *"conseguimos deixar ele cinza como os
    demais?"* — e "como os demais" inclui o peso da letra, que era o que sobrava
    quando se apagava só a cor.
    """
    ruins = []
    for nome, r in _inertes(medido):
        caras = {c["cara"] for c in r["chips"]}
        if len(caras) > 1:
            marcado = next((c for c in r["chips"] if c["marcado"]), None)
            outro = next((c for c in r["chips"] if not c["marcado"]), None)
            ruins.append(
                f"{nome}: {len(caras)} aparências numa fita que não escolhe nada\n"
                f"      marcado {marcado['texto']!r}: {marcado['cara']}\n"
                f"      irmão   {outro['texto']!r}: {outro['cara']}"
                if marcado and outro else f"{nome}: {sorted(caras)}")
    assert not ruins, (
        "numa fita que não escolhe nada, 'o marcado' não quer dizer coisa "
        "nenhuma para quem olha — e ela leu isso como *'fica sempre "
        "selecionado'*:\n  " + "\n  ".join(ruins))


def test_a_fita_inerte_nao_oferece_clique_em_chip_nenhum(medido: dict) -> None:
    """E o chip continua sem endereço — a cura não pode virar a mentira seguinte.

    `monta._endereco_do_chip` devolve string vazia quando `inerte`, e é a metade
    que impede a fita apagada de OFERECER uma escolha que a aba não tem para
    onde levar. Sem este caso, apagar o destaque poderia vir acompanhado de
    alguém "consertando" o chip para clicar.
    """
    com_gesto = [(n, c["texto"]) for n, r in _inertes(medido)
                 for c in r["chips"] if c["gesto"]]
    assert not com_gesto, (
        f"chip de fita inerte com endereço de clique: {com_gesto}. "
        f"Nessas abas o chip não escolhe coisa alguma, e um `data-gesto` ali "
        f"faz a tela oferecer uma escolha sem destino.")


# ---------------------------------------------------------------------------
# 3. O CASO DELA — o marcado era o P1, e ele cai em OUTRA regra
# ---------------------------------------------------------------------------
def test_o_chip_do_plastico_marcado_tambem_fica_igual() -> None:
    """Move o `.on` para o chip do P1 e remede — que é o que ela tinha na tela.

    POR QUE ELE PRECISA EXISTIR: na página publicada o marcado é o `Todos`, que
    é `.chip` puro. O chip do P1 é `.chip.plastico`, e nele DUAS regras de mesma
    especificidade (0,4,0) disputam a borda — `.fita.inerte .chip.plastico` e
    `.fita.inerte .chip.on`. Quem ganha é a última no arquivo. Medir só o
    `Todos` deixaria justamente o caso que ela fotografou sem cobertura, e a
    sprint abriu porque uma hipótese não medida pareceu óbvia.
    """
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    alvo = PUBLICADO / "03-gatilhos.html"
    assert alvo.is_file(), f"{alvo} sumiu — é a aba em que ela viu o defeito"

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = nav.new_page(viewport={"width": 1600, "height": 900})
            pg.goto(alvo.as_uri())
            pg.wait_for_load_state("networkidle")
            movido = pg.evaluate("""() => {
              const f = document.querySelector('.fita');
              const chips = [...f.querySelectorAll('.chip')];
              const plastico = chips.find(c => c.classList.contains('plastico'));
              if (!plastico) return {erro: 'a fita não tem chip de plástico'};
              // é assim que o piloto repinta a fita quando ela escolhe o P1
              chips.forEach(c => c.classList.remove('on'));
              plastico.classList.add('on');
              return null;
            }""")
            assert movido is None, movido
            r = pg.evaluate(O_QUE_O_MOTOR_DESENHA)
        finally:
            nav.close()

    caras = {c["cara"] for c in r["chips"]}
    marcado = next(c for c in r["chips"] if c["marcado"])
    assert marcado["plastico"], "o `.on` não pousou no chip do plástico"
    assert len(caras) == 1, (
        "com o alvo no P1 — que é o que ela tinha na tela — o chip do plástico "
        "volta a se destacar numa fita que não escolhe nada:\n"
        + "\n".join(f"    {c['texto']!r}: {c['cara']}" for c in r["chips"]))
