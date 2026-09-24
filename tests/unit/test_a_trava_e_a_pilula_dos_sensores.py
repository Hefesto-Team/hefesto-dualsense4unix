"""A trava do perfil ativo é a pílula que ela pediu, e o travessão não acende.

`TRAVA-PILULA-01` — pedido dela, 19/09/2026, com as duas abas abertas lado a
lado: *"vê os botões do giroscopio e acelerometro queria esse tipo de botão ali
no Trava o perfil Ativo."*  <!-- noqa-acento: citação literal dela -->

A TROCA NÃO É DE MARCAÇÃO — ela muda o alvo da ponte, e o alvo tem dono:

* até 19/09 a trava era `<input type="checkbox">` com `data-hef-alvo="marcado"`,
  o DÉCIMO alvo da ponte e o **único que escreve `el.checked`**;
* a pílula usa `classe` + `data-hef-quando`, como o Giroscópio;
* e um `<button>` **não emite `change`** — só `<input>`, `<select>` e
  `<textarea>` emitem. O gesto filtrava por `change`, então sem a troca do
  evento a trava viraria enfeite: a tela pisca e o disco não muda.

**A POLARIDADE É INVERTIDA EM RELAÇÃO AO MODELO, e é o que esta régua mais
protege.** O `.sw` da aba Controles está ACESO em repouso e ganha `.off` ao
desligar, porque o default dos sensores é ligado. O default desta trava é
DESTRAVADA — e o caso que decide não é o default, é o TRAVESSÃO: com a
polaridade do modelo, um estado que o daemon não respondeu ficaria VERDE, e a
tela afirmaria uma escolha dela que ela não fez.
"""
from __future__ import annotations

import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PAGINA = RAIZ / "src/hefesto_dualsense4unix/interface/paginas/01-jogar.html"
#: O DESENHO, medido junto — O-MODO-FREESTYLE-02, 24/09/2026: é ele que o
#: `--publicar 01` leva ao produto.
DESENHO = RAIZ / "mockup/01-jogar.html"
CHROME = pathlib.Path("/usr/bin/google-chrome")


def _altura_esperada(rotulo: str) -> int:
    """Os 17 px da palavra de ontem, ou a altura do gerador para a de hoje.

    O PRAZO DOS 17 PX: eles valem enquanto a página disser
    `CADEADO_ROTULO_ESPERANDO_A_SESSAO_DELA`. No commit do `--publicar 01` a
    constante sai (`test_o_modo_freestyle.test_a_palavra_de_ontem_tem_prazo`) e
    este ramo sai junto. A de hoje é lida no dono (`aba01.py`), nunca digitada —
    é a decisão `D-2409-O-BOTAO-FREESTYLE-TEM-26-PX`.
    """
    from hefesto_dualsense4unix.interface.pacotes import a01_jogar as p

    if rotulo == p.CADEADO_ROTULO_ESPERANDO_A_SESSAO_DELA:
        return 17
    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/aba01.py").read_text(
        encoding="utf-8")
    achado = re.search(r"\.cadeado\{(?:[^}]*;)?height:(\d+)px", fonte)
    assert achado, "o `.cadeado` do gerador perdeu a altura — a régua ficaria cega"
    return int(achado.group(1))


def _bootstrap() -> str:
    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py").read_text(
        encoding="utf-8")
    m = re.search(r'BOOTSTRAP = r"""(.*?)"""', fonte, re.S)
    assert m, "não achei o BOOTSTRAP no piloto — a régua ficaria verde sobre nada"
    return m.group(1)


def test_o_emissor_responde_as_tres_e_so_o_true_acende() -> None:
    """`_cadeado` na língua do alvo `classe`, e o travessão é o "não sei"."""
    from hefesto_dualsense4unix.interface.pacotes import a01_jogar as p

    assert p._cadeado({"autoswitch_locked": True}) == p.CADEADO_LIGADO
    assert p._cadeado({"autoswitch_locked": False}) == p.CADEADO_DESLIGADO
    # SEM DAEMON E COM LIXO caem no MESMO lugar, e não no `DESLIGADO`: a tela
    # não sabe, e o que ela mostra é o padrão do produto — não uma leitura.
    for sem_resposta in ({}, {"autoswitch_locked": "sim"}, {"autoswitch_locked": 1}):
        assert p._cadeado(sem_resposta) not in (p.CADEADO_LIGADO, p.CADEADO_DESLIGADO), (
            f"{sem_resposta!r} produziu uma AFIRMAÇÃO sobre a trava. Só o `True` "
            f"literal acende, e só o `False` literal nega.")


def test_o_gesto_ouve_click_porque_um_botao_nao_emite_change() -> None:
    """O contrato de clique, e ele é a metade que grava no disco dela."""
    from hefesto_dualsense4unix.interface.pacotes import a01_jogar as p

    fonte = pathlib.Path(p.__file__).read_text(encoding="utf-8")
    assert '"gesto": "cadeado", "clique": {"evento": "click"}' in fonte, (
        "o contrato do cadeado voltou a pedir `change`. Um `<button>` não emite "
        "`change` — o gesto voltaria cedo em todo clique e a trava viraria "
        "enfeite: a tela pisca e o disco não muda.")
    assert 'o.get("evento") or "click"' in fonte, (
        "o padrão do filtro dentro do handler divergiu do contrato")


@pytest.mark.skipif(not CHROME.exists(), reason="sem o Chrome do sistema")
@pytest.mark.parametrize("arquivo", [PAGINA, DESENHO], ids=["publicada", "desenho"])
def test_a_pilula_acende_apaga_e_nao_afirma_sobre_o_travessao(arquivo: pathlib.Path) -> None:
    """Os TRÊS estados na página publicada e no desenho, lidos do CSS calculado."""
    from playwright.sync_api import sync_playwright

    from hefesto_dualsense4unix.interface.folha_da_casa import FOLHA_DA_CASA
    from hefesto_dualsense4unix.interface.pacotes import a01_jogar as p

    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = nav.new_page(viewport={"width": 1180, "height": 780})
            pg.goto(arquivo.as_uri())
            pg.add_style_tag(content=FOLHA_DA_CASA)
            pg.evaluate("window.__recebido=[];window.webkit={messageHandlers:"
                        "{hefesto:{postMessage:function(s){window.__recebido.push(s)}}}};")
            pg.evaluate(_bootstrap())

            def olhar() -> dict:
                return pg.evaluate("""() => {
                    const b = document.querySelector('.cadeado');
                    const ps = getComputedStyle(b.querySelector('.p'));
                    return {tag: b.tagName, acesa: b.classList.contains('ligada'),
                            brilho: ps.boxShadow !== 'none',
                            alt: Math.round(b.getBoundingClientRect().height),
                            rotulo: (b.textContent || '').trim()}}""")

            assert olhar()["tag"] == "BUTTON", (
                "a trava voltou a ser `<input>`/`<label>` — ela pediu o botão "
                "do Giroscópio")

            pg.evaluate("v => window.__hef.pintar({mesa:{cadeado:v}})", p.CADEADO_LIGADO)
            aceso = olhar()
            assert aceso["acesa"] and aceso["brilho"], (
                f"travado e a pílula não acendeu: {aceso}")

            pg.evaluate("v => window.__hef.pintar({mesa:{cadeado:v}})", p.CADEADO_DESLIGADO)
            assert not olhar()["acesa"], "destravado e a pílula ficou verde"

            # O CASO QUE DECIDE A POLARIDADE.
            pg.evaluate("v => window.__hef.pintar({mesa:{cadeado:v}})", p._cadeado({}))
            mudo = olhar()
            assert not mudo["acesa"] and not mudo["brilho"], (
                f"SEM DAEMON a pílula ficou acesa: {mudo}. Com `off` no "
                f"`DESLIGADO` (a polaridade do `.sw`) é exatamente isto que "
                f"acontece — a tela afirma uma escolha dela sobre um estado que "
                f"ninguém leu.")

            # A ALTURA, que é a trava cara desta linha — e que tem PRAZO: ver
            # `_altura_esperada`.
            assert mudo["alt"] == _altura_esperada(mudo["rotulo"]), (
                f"a pílula mede {mudo['alt']}px com a palavra {mudo['rotulo']!r}. "
                f"O `.quadro-topo` é `align-items:center`: a altura da pílula é a "
                f"da linha do título inteira, e a porta da Navegação já pagou "
                f"esse preço com 2px.")

            # E O CLIQUE SAI, uma vez só.
            pg.evaluate("window.__recebido = []")
            pg.eval_on_selector(".cadeado", "el => el.click()")
            crus = pg.evaluate("window.__recebido")
            assert len(crus) == 1, (
                f"o clique produziu {len(crus)} recado(s). Dois seriam o "
                f"defeito que o `change` filtrava no checkbox — e um botão não "
                f"deveria ter como produzi-los.")
            assert '"gesto":"cadeado"' in crus[0], crus[0]
        finally:
            nav.close()
