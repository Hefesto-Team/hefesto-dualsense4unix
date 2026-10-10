"""O «Selecionar:» acende quem está escolhido (O-SELECIONAR-ACENDE-QUEM-ESTA-ESCOLHIDO-01).

PEDIDO, 29/09/2026, opção a de 08/10: o chip aceso (fonte clara, negrito) é quem está
escolhido; o «Todos» escolhe os quatro e acende os quatro com ele; nas abas que valem para
todos, os quatro nascem acesos, cada um com a borda do plástico; o balão da fita sai das sete.

QUEM RESPONDE É UMA FUNÇÃO SÓ, `monta.acesos_da_fita(ativo, mesa, escolhe=…)`, e quatro
escritores perguntam a ela (`monta.fita`, `a06_navegacao.chips_da_fita`,
`a09_sistema._html_da_fita` e o `CHIP_ACESO` da `aba02`). A folha não tem mais opinião
própria sobre a fita inerte.

NENHUMA RÉGUA AQUI MEDE A PRÓPRIA SAÍDA: o esperado vem sempre do CENÁRIO (quem foi clicado,
quantos estão na mesa), escrito na régua, e nunca de `acesos_da_fita`.

AS RÉGUAS
  1. as dez páginas do desenho, no motor: sete acesas por inteiro, três só no P1, e a borda de
     2 px de cada chip na cor do plástico LIDA DA MESA (não do `style` do próprio chip);
  2. o clique na 02: Todos acende três, P2 acende só o P2, e Todos de volta acende três;
  3. o piloto (`hefesto_vivo._fita`) com 1 a 4 controles, nas dez páginas, antes e depois do
     gesto: é a única régua que vê o caminho do produto nas sete, onde o piloto manda o P1;
  4. os escritores perguntam ao dono: com um dublê que só devolve o P2, os três acendem só o P2;
  5. a fita de leitura não tem balão.
  (O anel interno do cartão da 02 já tinha saído em 04/10, `fd1d1bbb5`; a régua dele é
  `test_a_borda_do_cartao_tem_a_cor_do_plastico`.)

AS MORDIDAS (feitas em 09/10/2026, md5 antes e depois):
  (i)   devolva a `.fita.inerte .chip.on{…}` apagando ao `topo.html` e regere → caem as sete da 1;
  (ii)  tire o `style="--plastico"` do `chips_da_fita` (06) → cai a 06 da 1;
  (iii) o `CHIP_ACESO` do `c-todos` de volta a um chip só → cai a 2 no primeiro passo;
  (iv)  tire o ramo `escolhe=False` de `acesos_da_fita` → cai a 3 (o P1 sozinho nas sete);
  (v)   cravar o `chip on` do «Todos» de volta no `chips_da_fita` → cai a 4.
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.hefesto_vivo`, que carrega o GTK")

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import monta

from hefesto_dualsense4unix.interface import hefesto_vivo, pacotes
from hefesto_dualsense4unix.interface.pacotes import a06_navegacao, a09_sistema

CHROME = pathlib.Path("/usr/bin/google-chrome")
DESENHO = RAIZ / "mockup"

#: O CENÁRIO do desenho (`monta.CONECTADOS`: P1 Cosmic Red USB, P2 Starlight Blue BT).
ABAS = [f"{a}.html" for _, a in monta.ABAS]
ESCOLHEM = ["01-jogar.html", "02-controles.html", "08-conexoes.html"]
NAO_ESCOLHEM = [a for a in ABAS if a not in ESCOLHEM]

MOTOR = """() => {
  const sonda = document.createElement('i');
  document.body.appendChild(sonda);
  const rgb = (v) => { sonda.style.color = ''; sonda.style.color = v;
                       return getComputedStyle(sonda).color; };
  const fg = rgb(getComputedStyle(document.documentElement).getPropertyValue('--fg').trim());
  const fita = document.querySelector('.fita');
  if (!fita) return {erro: 'a página não tem `.fita`'};
  const chips = [...fita.querySelectorAll('.chip')].map(c => {
    const s = getComputedStyle(c);
    return {texto: (c.textContent || '').trim(), pref: c.dataset.pref || '',
            aceso: s.color === fg && parseInt(s.fontWeight, 10) >= 600,
            borda: s.borderTopWidth, borda_cor: s.borderTopColor,
            plastico: c.classList.contains('plastico')};
  });
  return {inerte: fita.classList.contains('inerte'), balao: fita.getAttribute('title') || '',
          chips, fg};
}"""


def _hex_para_rgb(h: str) -> str:
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgb({r}, {g}, {b})"


@pytest.fixture(scope="module")
def navegador():
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            yield nav
        finally:
            nav.close()


@pytest.fixture(scope="module")
def dez(navegador) -> dict[str, dict[str, Any]]:
    """A fita de cada página do desenho, medida no motor (uma abertura para todas)."""
    fora: dict[str, dict[str, Any]] = {}
    pg = navegador.new_page(viewport={"width": 1600, "height": 900})
    for nome in ABAS:
        pg.goto((DESENHO / nome).as_uri())
        pg.wait_for_load_state("networkidle")
        r = pg.evaluate(MOTOR)
        assert "erro" not in r, f"{nome}: {r.get('erro')}"
        fora[nome] = r
    pg.close()
    assert len(fora) == 10
    return fora


# ---------------------------------------------------------------- régua 1: as dez no motor


@pytest.mark.parametrize("nome", NAO_ESCOLHEM)
def test_nas_sete_que_nao_escolhem_todo_chip_esta_aceso(dez: dict, nome: str) -> None:
    r = dez[nome]
    assert r["inerte"], f"{nome}: a fita deixou de ser a de leitura"
    assert r["chips"], f"{nome}: a fita saiu sem chip"
    apagados = [c["texto"] for c in r["chips"] if not c["aceso"]]
    assert not apagados, (
        f"{nome}: chip apagado numa aba que vale para todos: {apagados}. "
        f"O aceso é medido contra o `--fg` da própria página, com peso de 600 ou mais.")


@pytest.mark.parametrize("nome", ESCOLHEM)
def test_nas_tres_que_escolhem_so_o_p1_do_desenho_esta_aceso(dez: dict, nome: str) -> None:
    r = dez[nome]
    assert not r["inerte"], f"{nome}: a fita virou de leitura"
    acesos = [c["texto"] for c in r["chips"] if c["aceso"]]
    assert len(r["chips"]) == 3, f"{nome}: esperava Todos, P1 e P2"
    assert len(acesos) == 1 and acesos[0].startswith("P1"), (
        f"{nome}: no cenário do desenho (P1 escolhido) só o P1 acende; acesos={acesos}")


@pytest.mark.parametrize("nome", ABAS)
def test_o_chip_de_cada_controle_tem_a_borda_do_plastico_lida_da_mesa(
        dez: dict, nome: str) -> None:
    """2 px na cor de `monta.cor_da_zona(<cor da mesa>)`, e não no `style` do chip."""
    controles = [c for c in dez[nome]["chips"] if c["texto"] != "Todos"]
    if nome == "07-lancadores.html":
        assert controles == [], "a fita da 07 nasce só com o «Todos»"
        return
    assert len(controles) == len(monta.CONECTADOS), f"{nome}: chips={len(controles)}"
    for chip, dono in zip(controles, monta.CONECTADOS, strict=True):
        esperado = _hex_para_rgb(monta.cor_da_zona(dono["cor"]))
        assert (chip["borda"], chip["borda_cor"]) == ("2px", esperado), (
            f"{nome}: o chip do {dono['pref']} tem borda {chip['borda']} {chip['borda_cor']}, "
            f"e a mesa diz 2px {esperado}")


@pytest.mark.parametrize("nome", NAO_ESCOLHEM)
def test_a_fita_de_leitura_nao_tem_balao(dez: dict, nome: str) -> None:
    assert dez[nome]["balao"] == "", f"{nome}: a fita de leitura voltou a ter balão"


# ---------------------------------------------------------------- régua 2: o clique na 02


def test_o_clique_no_todos_acende_os_tres_e_o_clique_no_p2_so_o_p2(navegador) -> None:
    pg = navegador.new_page(viewport={"width": 1600, "height": 900})
    pg.goto((DESENHO / "02-controles.html").as_uri())
    pg.wait_for_load_state("networkidle")

    def acesos() -> list[str]:
        return [c["texto"].split()[0] for c in pg.evaluate(MOTOR)["chips"] if c["aceso"]]

    assert acesos() == ["P1"], "a 02 nasce com o P1 aberto"
    pg.click('.fita label.chip[for="c-todos"]')
    assert sorted(acesos()) == ["P1", "P2", "Todos"], (
        f"depois do clique no «Todos» só acendeu {acesos()}")
    pg.click('.fita label.chip[for="c-p2"]')
    assert acesos() == ["P2"], f"depois do clique no P2 acendeu {acesos()}"
    pg.click('.fita label.chip[for="c-todos"]')
    assert sorted(acesos()) == ["P1", "P2", "Todos"], (
        f"o «Todos» de volta acendeu {acesos()}")
    pg.close()


# ---------------------------------------------------------------- régua 3: o piloto


CORES = ["cosmic-red", "starlight-blue", "white", "galactic-purple"]
NOMES = ["Cosmic Red", "Starlight Blue", "White", "Galactic Purple"]


def _mesa(quantos: int) -> list[dict[str, Any]]:
    return [{"pref": f"p{i + 1}", "jogador": i + 1, "nome": NOMES[i], "cor": CORES[i],
             "via": "USB" if i == 0 else "BT", "transporte": "usb" if i == 0 else "bt",
             "uniq": f"02fe0000000{i + 1}"} for i in range(quantos)]


def _chips(html: str) -> list[tuple[str, bool]]:
    """`(pref ou posição, aceso)` de cada chip: o `on` na classe é o que o piloto escreve."""
    achados = re.findall(r'<label class="chip([^"]*)"([^>]*)>', html)
    fora = []
    for i, (classe, resto) in enumerate(achados):
        m = re.search(r'data-pref="([a-z0-9]+)"', resto)
        fora.append((m.group(1) if m else f"#{i}", re.search(r"\bon\b", classe) is not None))
    return fora


@pytest.fixture(autouse=True)
def escolha_limpa():
    antes = hefesto_vivo.ESCOLHA_DA_FITA.uniq
    hefesto_vivo.ESCOLHA_DA_FITA.uniq = ""
    yield
    hefesto_vivo.ESCOLHA_DA_FITA.uniq = antes


def _ctx(mesa):
    return pacotes.Contexto(state={}, mesa=mesa, conectados=mesa)


@pytest.mark.parametrize("quantos", [1, 2, 3, 4])
@pytest.mark.parametrize("aba", NAO_ESCOLHEM)
def test_o_piloto_acende_todos_nas_sete_qualquer_que_seja_a_escolha(
        quantos: int, aba: str) -> None:
    mesa = _mesa(quantos)
    esperados = quantos + (1 if quantos > 1 else 0)
    for escolha in (None, "p2", "todos"):
        if escolha == "p2" and quantos < 2:
            continue
        if escolha == "todos" and quantos < 2:
            continue
        if escolha:
            hefesto_vivo._escolher_na_fita(_ctx(mesa), {"pref": escolha}, None)
        chips = _chips(hefesto_vivo._fita(mesa, aba))
        assert len(chips) == esperados, (aba, quantos, chips)
        assert all(aceso for _, aceso in chips), (
            f"{aba} com {quantos} controle(s), escolha {escolha}: {chips} — numa aba que "
            f"vale para todos o piloto manda o P1 e a regra tem de acender todos mesmo assim")


@pytest.mark.parametrize("quantos", [2, 3, 4])
@pytest.mark.parametrize("aba", ESCOLHEM)
def test_o_piloto_nas_tres_que_escolhem_todos_acende_todos_e_p2_so_o_p2(
        quantos: int, aba: str) -> None:
    mesa = _mesa(quantos)
    hefesto_vivo._escolher_na_fita(_ctx(mesa), {"pref": "todos"}, None)
    chips = _chips(hefesto_vivo._fita(mesa, aba))
    assert [p for p, _ in chips][:1] == ["todos"] and len(chips) == quantos + 1
    assert all(aceso for _, aceso in chips), f"depois do gesto `todos`: {chips}"

    hefesto_vivo._escolher_na_fita(_ctx(mesa), {"pref": "p2"}, None)
    chips = _chips(hefesto_vivo._fita(mesa, aba))
    assert [p for p, aceso in chips if aceso] == ["p2"], f"depois do gesto `p2`: {chips}"


def test_com_um_controle_o_unico_chip_acende_nas_dez() -> None:
    mesa = _mesa(1)
    for pagina in ABAS:
        chips = _chips(hefesto_vivo._fita(mesa, pagina))
        assert len(chips) == 1 and chips[0][1], (pagina, chips)


# ---------------------------------------------------------------- régua 4: o dono é um só


def test_os_tres_escritores_perguntam_ao_dono(monkeypatch: pytest.MonkeyPatch) -> None:
    """Com um dublê que só devolve o P2, a fita de cada escritor acende só o P2.

    O esperado é o que o dublê devolve, e não o que a função real devolveria.
    """
    mesa = _mesa(2)
    # A 09 importa o `monta` por um apelido de `sys.modules`: são DOIS objetos de módulo,
    # e o dublê vai nos dois (cada escritor pergunta pelo módulo que tem, nunca por cópia).
    for modulo in {id(m): m for m in (monta, a09_sistema._monta())}.values():
        monkeypatch.setattr(modulo, "acesos_da_fita", lambda *a, **k: frozenset({"p2"}))
    for nome, html in (("monta.fita", monta.fita(ativo="todos", mesa=mesa)),
                       ("a06.chips_da_fita", a06_navegacao.chips_da_fita(mesa)),
                       ("a09._html_da_fita", a09_sistema._html_da_fita(mesa))):
        chips = _chips(html)
        assert len(chips) == 3, (nome, chips)
        assert [i for i, (_, aceso) in enumerate(chips) if aceso] == [2], (
            f"{nome} não perguntou ao dono: acesos={chips}")


def test_a_regra_vale_o_que_o_pedido_dela_diz() -> None:
    """A tabela da regra, escrita à mão (cenário → quem acende)."""
    dois = _mesa(2)
    um = _mesa(1)
    assert monta.acesos_da_fita("p2", dois, escolhe=True) == {"p2"}
    assert monta.acesos_da_fita("todos", dois, escolhe=True) == {"todos", "p1", "p2"}
    assert monta.acesos_da_fita("p1", dois, escolhe=False) == {"todos", "p1", "p2"}
    assert monta.acesos_da_fita("todos", um, escolhe=True) == {"p1"}
    assert monta.acesos_da_fita("todos", um, escolhe=False) == {"p1"}


def test_o_chip_acesso_da_02_vem_da_regra() -> None:
    import aba02

    todos = [r for r in aba02.CHIP_ACESO.split(",\n  ") if "#c-todos:checked" in r]
    assert len(todos) == len(aba02.MESA) + 1, (
        f"o rádio `c-todos` tem de acender o «Todos» e os controles: {todos}")
    so_p2 = [r for r in aba02.CHIP_ACESO.split(",\n  ") if "#c-p2:checked" in r]
    assert len(so_p2) == 1 and 'for="c-p2"' in so_p2[0], so_p2
