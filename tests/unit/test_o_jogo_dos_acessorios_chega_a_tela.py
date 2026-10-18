"""O jogo dos acessórios chega à tela: a aba Vibração sem «Meus toques» e as janelas dos acessórios.

No desenho do todo, aprovado em 12/10/2026 (`todo-05`, «Meus toques sai daqui; vai para a 07»), os
toques do jogador deixaram a aba Vibração e passaram à janela dos acessórios (a Lovense), numa aba
interna. A janela traz a coluna «Agora» (nível, perfil, aparelhos, a sessão), o «Parar tudo» sempre
à vista no topo e sete abas internas; a janela do Kyty traz quatro cartões.

Só o desenho (`mockup/05-vibracao.html` e `mockup/07-lancadores.html`); a segunda passagem liga o
produto. Rótulos com só a primeira letra maiúscula (fora nomes próprios) e nenhuma janela rola na
vertical a 1212x809, a 1918x840 e a 1212x740.

MORDIDAS (executadas aqui): «Parar tudo» escrito com maiúscula no meio, o «Parar tudo» fora do
topo da janela e um cartão a menos no Kyty reprovam a régua; a 05 com «Meus toques» de volta também.
"""

from __future__ import annotations

import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
M05 = RAIZ / "mockup" / "05-vibracao.html"
M07 = RAIZ / "mockup" / "07-lancadores.html"
CHROME = pathlib.Path("/usr/bin/google-chrome")
LARGURAS = ((1212, 809), (1918, 840), (1212, 740))

#: Nomes próprios que a tela escreve com maiúscula no meio da frase: jogos, produtos, abas e o
#: estilo «Adulto». Qualquer outra palavra com maiúscula depois de minúscula reprova.
PROPRIOS = {
    "Adulto", "Adventure", "Conquest", "Crisis", "Domi", "Engine", "Evil", "Ferri", "Game",
    "Hefesto", "Iluminação", "Input", "Intiface", "Knight", "Kombat", "Kyty", "Linux", "Lovense",
    "Lust", "Mode", "Nights", "Nora", "Perfis", "Planet", "Proton", "Ring", "Salvar", "Steam",
    "Village", "Xbox",
    # a cor do plástico, nome próprio do aparelho (a 05 a traz no title do chip do controle)
    "Blue", "Red"}
ABAS_INTERNAS = ["Meus toques", "Segurança", "Gestos", "O que seguem", "Touchpad", "Luz", "Perfis"]
CARTOES_DO_KYTY = ["Programa", "Jogos", "Controle", "Som"]


def _doc(caminho: pathlib.Path, texto: str | None = None) -> str:
    bruto = texto if texto is not None else caminho.read_text(encoding="utf-8")
    sem = re.sub(r"<(style|script)\b[^>]*>.*?</\1>", "", bruto, flags=re.S)
    return re.sub(r"<!--.*?-->", "", sem, flags=re.S)


def _maiusculas_a_mais(doc: str, so_o_que_se_le: bool = False) -> list[str]:
    """Palavra com maiúscula depois de minúscula, na mesma frase, que não é nome próprio.

    `so_o_que_se_le` olha apenas os textos da tela, sem as dicas: nas dicas da 05 o nome de um
    botão («Parar», «Sem efeito») aparece citado com a maiúscula dele.
    """
    textos = re.findall(r">([^<>]{2,90})<", doc)
    if not so_o_que_se_le:
        textos += re.findall(r'(?:data-dica|title|aria-label|placeholder)="([^"]+)"', doc)
    achou: set[str] = set()
    for t in textos:
        for m in re.finditer(r"(?<=[a-zçãõáéíóúâêô] )([A-ZÁÉÍÓÚÂÊÔ][a-zçãõáéíóúâêô]+)", t.strip()):
            if m.group(1) not in PROPRIOS:
                achou.add(m.group(1))
    return sorted(achou)


def _janela(doc: str, ident: str) -> str:
    inicio = doc.index(f'id="{ident}"')
    fim = doc.find('<div class="tela-nova"', inicio + 1)
    return doc[inicio:] if fim < 0 else doc[inicio:fim]


def test_a_aba_vibracao_nao_tem_mais_os_meus_toques() -> None:
    """A seção saiu da 05 e foi para a janela dos acessórios (todo-05, 12/10/2026)."""
    assert "Meus toques" not in _doc(M05)
    assert "Meus toques" in _janela(_doc(M07), "acessorios")


def test_a_regua_morde_os_meus_toques_que_voltam_a_05() -> None:
    assert "Meus toques" in _doc(M05, M05.read_text(encoding="utf-8").replace(
        "</body>", "<div class=\"pc-sub\">Meus toques</div></body>"))


def test_a_janela_dos_acessorios_traz_o_agora_o_parar_tudo_e_as_sete_abas() -> None:
    janela = _janela(_doc(M07), "acessorios")
    topo = re.search(r'<div class="tn-topo">.*?<div class="ja-corpo">', janela, flags=re.S).group(0)
    assert "Parar tudo" in topo, "o «Parar tudo» saiu do topo da janela, que é onde fica à vista"
    agora = re.search(r'<div class="ja-agora">(.*?)<div class="ja-abas">', janela, flags=re.S)
    assert agora, "sem a coluna «Agora»"
    for rotulo in ("Nível", "Perfil", "Aparelhos e o papel de cada um", "Esta sessão", "Comanda"):
        assert rotulo in agora.group(1), f"a coluna «Agora» perdeu «{rotulo}»"
    rotulos = re.findall(r"<label for=\"t\d\"[^>]*>([^<]+)</label>", janela)
    assert rotulos == ABAS_INTERNAS, rotulos


def test_a_regua_morde_o_parar_tudo_fora_do_topo() -> None:
    doc = _doc(M07)
    sem = doc.replace('class="ja-parar"', 'class="ja-parar-x"').replace(
        "Parar tudo</button>", "</button>", 1)
    topo = re.search(r'<div class="tn-topo">.*?<div class="ja-corpo">',
                     _janela(sem, "acessorios"), flags=re.S).group(0)
    assert "Parar tudo" not in topo


def test_a_janela_do_kyty_tem_quatro_cartoes() -> None:
    janela = _janela(_doc(M07), "kyty")
    assert re.findall(r'<span class="ac-tit">([^<]+)</span>', janela) == CARTOES_DO_KYTY
    assert "Guardar" in janela and "Voltar ao molde" in janela


def test_a_regua_morde_um_cartao_a_menos_no_kyty() -> None:
    janela = _janela(_doc(M07), "kyty").replace('<span class="ac-tit">Som</span>', "")
    assert re.findall(r'<span class="ac-tit">([^<]+)</span>', janela) != CARTOES_DO_KYTY


def test_so_a_primeira_letra_e_maiuscula_na_05_e_nas_janelas_da_07() -> None:
    assert _maiusculas_a_mais(_doc(M05), so_o_que_se_le=True) == []
    assert _maiusculas_a_mais(_doc(M07)) == []


def test_a_regua_morde_o_parar_tudo_com_maiuscula_no_meio() -> None:
    doc = _doc(M07).replace("Parar tudo", "Parar Tudo")
    assert "Tudo" in _maiusculas_a_mais(doc)


@pytest.fixture(scope="module")
def navegador():
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        yield nav
        nav.close()


@pytest.mark.parametrize(("larg", "alt"), LARGURAS)
def test_a_05_e_as_janelas_dos_acessorios_nao_rolam_na_vertical(navegador, larg, alt) -> None:
    pg = navegador.new_page(viewport={"width": larg, "height": alt})
    try:
        pg.goto(M05.as_uri())
        m = pg.evaluate("""() => { const d = document.documentElement;
          return {alto: d.scrollHeight, cabe: d.clientHeight,
                  largo: d.scrollWidth > d.clientWidth + 1}; }""")
        assert m["alto"] <= m["cabe"] + 1 and not m["largo"], ("05", m)
        for ancora in ("acessorios", "kyty"):
            pg.goto(f"{M07.as_uri()}#{ancora}")
            if ancora == "acessorios":
                pg.goto(f"{M07.as_uri()}?aba=t2&marcados=1#acessorios")
            dentro = pg.evaluate("""(a) => { const r = document.getElementById(a);
              const cx = r.querySelector('.tn-cx').getBoundingClientRect();
              const roladores = [r, ...r.querySelectorAll('*')].filter(e =>
                e.scrollHeight > e.clientHeight + 1 && e.clientHeight > 0 &&
                ['auto', 'scroll'].includes(getComputedStyle(e).overflowY) &&
                !e.classList.contains('jg-lista')).length;
              return {topo: cx.top, fundo: cx.bottom, alto: innerHeight, roladores}; }""", ancora)
            assert dentro["topo"] >= 0 and dentro["fundo"] <= dentro["alto"] + 1, (ancora, dentro)
            assert dentro["roladores"] == 0, (ancora, dentro)
    finally:
        pg.close()
