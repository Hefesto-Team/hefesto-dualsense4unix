"""A aba Lançadores (Experimental no desenho do todo) ganha as modificações.

O quadro «Extensões» traz uma linha por modificação instalada (Kyty e Lovense), cada uma com a
chave de ligar, a engrenagem das configurações e o menu «⋮»; o quadro «Lançadores» fica com as
filas. A instalação é de um endereço ou de uma pasta. A Lovense é UMA extensão com três jeitos de
ligar, e o contador «N de 3 ligadas» acompanha as chaves da janela. Os impedimentos da Steam moram
na janela de configurar o lançador, e não em aviso fixo na aba.

Só o desenho (`mockup/07-lancadores.html`); a segunda passagem liga o produto.

MORDIDAS (executadas aqui, sobre uma cópia do HTML): tirar a engrenagem de uma linha, o «⋮», o
campo do endereço, ou devolver o aviso fixo da Steam reprova a régua; o contador que não reage ao
clique reprova no Chrome.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup" / "07-lancadores.html"
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
CHROME = pathlib.Path("/usr/bin/google-chrome")
LARGURAS = ((1212, 809), (1918, 840), (1212, 740))


def _doc(texto: str | None = None) -> str:
    """O desenho sem estilo e sem script: o que a pessoa vê e o que ela aciona."""
    bruto = texto if texto is not None else MOCKUP.read_text(encoding="utf-8")
    return re.sub(r"<(style|script)\b[^>]*>.*?</\1>", "", bruto, flags=re.S)


def _problemas(doc: str) -> list[str]:
    """O que falta ao quadro das extensões. Vazio quando a forma do desenho está inteira."""
    falta: list[str] = []
    quadro = re.search(r'<label class="quadro-titulo"[^>]*>Extensões</label>(.*?)'
                       r'<div class="quadro estica">', doc, flags=re.S)
    if not quadro:
        return ["sem o quadro «Extensões» antes do quadro dos lançadores"]
    corpo = quadro.group(1)
    linhas = re.split(r'(?=<div class="ext" data-modificacao=)', corpo)[1:]
    chaves = [re.search(r'data-modificacao="([^"]+)"', x).group(1) for x in linhas]
    if chaves != ["kyty", "lovense"]:
        falta.append(f"linhas de extensão {chaves}, e o desenho tem kyty e lovense")
    for chave, linha in zip(chaves, linhas, strict=False):
        for gesto, rotulo in (("ligar-modificacao", "a chave"),
                              ("configurar-modificacao", "a engrenagem"),
                              ("mais-da-modificacao", "o «⋮»")):
            if f'data-gesto="{gesto}" data-v="{chave}"' not in linha:
                falta.append(f"{chave}: sem {rotulo}")
        faz = re.search(r'<span class="ext-faz" data-dica="([^"]*)">([^<]*)</span>', linha)
        if not faz or faz.group(1) != faz.group(2):
            falta.append(f"{chave}: o «o que faz» não é igual à dica")
    instalar = re.search(r'<div class="ext-instalar.*?</div>', corpo, flags=re.S)
    if not instalar:
        falta.append("sem a linha «Instalar de um endereço»")
    else:
        for marca in ('data-linha="mod-endereco"', 'data-gesto="escolher-arquivo-da-modificacao"',
                      'data-gesto="instalar-modificacao"'):
            if marca not in instalar.group(0):
                falta.append(f"a instalação perdeu {marca}")
    if "class=\"ajuda" in doc:
        falta.append("um «?» voltou; a dica mora no data-dica")
    if re.search(r'class="[^"]*\b(aviso|lanc-aviso)\b', doc):
        falta.append("um aviso fixo voltou à aba; os impedimentos moram em «Configurar»")
    return falta


def test_o_quadro_das_extensoes_traz_kyty_e_lovense_com_as_tres_acoes() -> None:
    assert _problemas(_doc()) == []


def test_a_regua_morde_a_engrenagem_o_mais_o_endereco_e_o_aviso() -> None:
    doc = _doc()
    sem_engrenagem = doc.replace('data-gesto="configurar-modificacao" data-v="kyty"', 'data-x="1"')
    assert any("kyty: sem a engrenagem" in p for p in _problemas(sem_engrenagem))
    sem_mais = doc.replace('data-gesto="mais-da-modificacao" data-v="lovense"', 'data-x="1"')
    assert any("lovense: sem o «⋮»" in p for p in _problemas(sem_mais))
    sem_endereco = doc.replace('data-linha="mod-endereco"', 'data-x="1"')
    assert any("mod-endereco" in p for p in _problemas(sem_endereco))
    com_aviso = doc.replace('<div class="quadro estica">',
                            '<div class="aviso">x</div><div class="quadro estica">', 1)
    assert any("aviso fixo" in p for p in _problemas(com_aviso))
    sem_faz = doc.replace('<span class="ext-faz" data-dica="Jogos do Kyty',
                          '<span class="ext-faz" data-dica="Outra', 1)
    assert any("kyty" in p and "igual à dica" in p for p in _problemas(sem_faz))


def test_os_impedimentos_da_steam_moram_na_janela_de_configurar() -> None:
    """A fila da Steam não carrega aviso; o caminho é «Configurar», depois «Ver e resolver»."""
    doc = _doc()
    conf = doc[doc.index('id="lanc-conf"'):]
    linha = re.search(r"<span>Impedimentos</span>.*?</div>", conf, flags=re.S)
    assert linha, "a janela de configurar não tem a linha «Impedimentos»"
    assert 'href="#impedimentos"' in linha.group(0) and "Ver e resolver" in linha.group(0)
    fila = re.search(r'<div class="lanc-fila">.*?<div class="lf ausente"', doc, flags=re.S).group(0)
    assert "impedimento" not in fila.lower(), "a fila da Steam voltou a avisar do impedimento"


def test_a_lovense_e_uma_extensao_com_tres_jeitos_de_ligar() -> None:
    doc = _doc()
    janela = doc[doc.index('id="lovense"'):doc.index('id="impedimentos"')]
    jeitos = re.findall(r'<div class="lv-linha" data-modificacao="([^"]+)"', janela)
    assert jeitos == ["intiface", "lovense-celular", "buttplug"], jeitos
    for jeito in jeitos:
        assert f'data-gesto="ligar-modificacao" data-v="{jeito}"' in janela, jeito
        assert f'data-gesto="configurar-modificacao" data-v="{jeito}"' in janela, jeito
    assert "2 de 3 ligadas" in doc


def test_o_gerador_confere_o_proprio_desenho() -> None:
    """`aba07.py --conferir` roda só a régua de identidade: nenhuma cor de aparelho cravada."""
    r = subprocess.run([sys.executable, str(INTERFACE / "aba07.py"), "--conferir", str(MOCKUP)],
                       capture_output=True, text=True, cwd=str(INTERFACE), check=False)
    assert r.returncode == 0, r.stderr + r.stdout


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
def test_a_aba_e_as_janelas_da_lovense_cabem_sem_rolagem_vertical(navegador, larg, alt) -> None:
    pg = navegador.new_page(viewport={"width": larg, "height": alt})
    try:
        pg.goto(MOCKUP.as_uri())
        m = pg.evaluate("""() => { const d = document.documentElement;
          return {alto: d.scrollHeight, cabe: d.clientHeight,
                  largo: d.scrollWidth > d.clientWidth + 1}; }""")
        assert m["alto"] <= m["cabe"] + 1 and not m["largo"], ("aba", m)
        for ancora in ("lovense", "lanc-conf", "impedimentos"):
            pg.goto(f"{MOCKUP.as_uri()}#{ancora}")
            dentro = pg.evaluate("""(a) => { const r = document.getElementById(a);
              const cx = r.querySelector('.tn-cx').getBoundingClientRect();
              const roladores = [r, ...r.querySelectorAll('*')].filter(e =>
                e.scrollHeight > e.clientHeight + 1 && e.clientHeight > 0 &&
                ['auto', 'scroll'].includes(getComputedStyle(e).overflowY)).length;
              return {topo: cx.top, fundo: cx.bottom, alto: innerHeight, roladores}; }""", ancora)
            assert dentro["topo"] >= 0 and dentro["fundo"] <= dentro["alto"] + 1, (ancora, dentro)
            assert dentro["roladores"] == 0, (ancora, dentro)
    finally:
        pg.close()


def test_o_contador_da_lovense_acompanha_as_chaves(navegador) -> None:
    """Ligar o terceiro jeito leva a «3 de 3 ligadas»; desligar todos desliga a extensão."""
    pg = navegador.new_page(viewport={"width": 1212, "height": 809})
    try:
        pg.goto(MOCKUP.as_uri())
        conta = "[data-lv-conta]"
        assert pg.inner_text(conta).strip() == "2 de 3 ligadas"
        pg.goto(f"{MOCKUP.as_uri()}#lovense")
        pg.click('#lovense .lv-linha[data-modificacao="buttplug"] .nj-tog')
        pg.goto(MOCKUP.as_uri() + "#")
        assert pg.inner_text(conta).strip() == "3 de 3 ligadas"
        for jeito in ("intiface", "lovense-celular", "buttplug"):
            pg.goto(f"{MOCKUP.as_uri()}#lovense")
            pg.click(f'#lovense .lv-linha[data-modificacao="{jeito}"] .nj-tog')
        assert pg.inner_text(conta).strip() == "0 de 3 ligadas"
        chave = pg.evaluate(
            "document.querySelector('.ext[data-modificacao=lovense] > .nj-tog').className")
        assert "ligado" not in chave, chave
    finally:
        pg.close()
