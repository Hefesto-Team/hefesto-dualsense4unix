"""A trava do perfil ativo é a pílula que o usuário pediu, e o travessão não acende."""
from __future__ import annotations

import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PAGINA = RAIZ / "src/hefesto_dualsense4unix/interface/paginas/01-jogar.html"
DESENHO = RAIZ / "mockup/01-jogar.html"
CHROME = pathlib.Path("/usr/bin/google-chrome")


def _altura_esperada(rotulo: str) -> int:
    """A altura do «Modo Freestyle», lida no dono (`aba01.py`), nunca digitada."""
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

    assert p._cadeado({"freestyle_ligado": True}) == p.CADEADO_LIGADO
    assert p._cadeado({"freestyle_ligado": False}) == p.CADEADO_DESLIGADO
    for sem_resposta in ({}, {"freestyle_ligado": "sim"}, {"freestyle_ligado": 1}):
        assert p._cadeado(sem_resposta) not in (p.CADEADO_LIGADO, p.CADEADO_DESLIGADO), (
            f"{sem_resposta!r} produziu uma AFIRMAÇÃO sobre a trava. Só o `True` "
            f"literal acende, e só o `False` literal nega.")


def test_o_gesto_ouve_click_porque_um_botao_nao_emite_change() -> None:
    """O contrato de clique, e ele é a metade que grava no disco do usuário."""
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

            pg.evaluate("v => window.__hef.pintar({mesa:{cadeado:v}})", p._cadeado({}))
            mudo = olhar()
            assert not mudo["acesa"] and not mudo["brilho"], (
                f"SEM DAEMON a pílula ficou acesa: {mudo}. Com `off` no "
                f"`DESLIGADO` (a polaridade do `.sw`) é exatamente isto que "
                f"acontece — a tela afirma uma escolha dela sobre um estado que "
                f"ninguém leu.")

            assert mudo["alt"] == _altura_esperada(mudo["rotulo"]), (
                f"a pílula mede {mudo['alt']}px com a palavra {mudo['rotulo']!r}. "
                f"O `.quadro-topo` é `align-items:center`: a altura da pílula é a "
                f"da linha do título inteira, e a porta da Navegação já pagou "
                f"esse preço com 2px.")

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
