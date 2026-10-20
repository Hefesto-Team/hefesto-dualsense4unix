"""A aba Experimental do todo (a 07, antes «Lançadores»): fila dos lançadores, três botões cada.

O cartão por lançador saiu. Cada lançador é uma fila com o nome, os jogos achados e exatamente três
botões: «Identificar», «Criar perfis» e «Configurar». Achado, só o «Identificar» fica apagado; não
achado, só ele fica aceso. Nenhum «Abrir», nenhum «?», nenhum aviso fixo. A janela dos
impedimentos só se alcança por «Configurar» da Steam, e a tira chama a aba de «Experimental».

Só o desenho (`mockup/07-lancadores.html`); a segunda passagem liga o produto.

MORDIDAS (executadas aqui): devolver o «Abrir» a uma fila, acender os três de um não achado, tirar
um botão, devolver o gesto a um apagado ou devolver o `span.ajuda` reprova a régua; o clique que não
abre a janela reprova no Chrome.
"""

from __future__ import annotations

import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup" / "07-lancadores.html"
CHROME = pathlib.Path("/usr/bin/google-chrome")
# 19/10/2026: Steam, Heroic e Flatpak de fábrica e o Lutris como extensão instalada; o RetroArch é a
# linha da migração (sem botões), medida em `test_os_lancadores_de_fora_viram_extensoes.py`.
ACHADOS = {"steam", "lutris"}
NAO_ACHADOS = {"heroic", "flatpak"}
GESTOS = ["identificar-lancador", "criar-perfil-para-um-jogo", "configurar-lancador"]
ROTULOS = ["Identificar", "Criar perfis", "Configurar"]


def _doc(texto: str | None = None) -> str:
    bruto = texto if texto is not None else MOCKUP.read_text(encoding="utf-8")
    sem = re.sub(r"<(style|script)\b[^>]*>.*?</\1>", "", bruto, flags=re.S)
    return re.sub(r"<!--.*?-->", "", sem, flags=re.S)


def _filas(doc: str) -> dict[str, str]:
    """`chave -> HTML dos botões` de cada fila `.lf` com lançador."""
    achadas = re.findall(r'<div class="lf( ausente)?" data-lancador="([a-z0-9]+)">.*?'
                         r'<span class="lf-botoes">(.*?)</span>\s*</div>', doc, flags=re.S)
    return {chave: (ausente + "|" + botoes) for ausente, chave, botoes in achadas}


def _problemas(doc: str) -> list[str]:
    falta: list[str] = []
    filas = _filas(doc)
    if set(filas) != ACHADOS | NAO_ACHADOS:
        falta.append(f"filas {sorted(filas)}, e o desenho tem {sorted(ACHADOS | NAO_ACHADOS)}")
    for chave, bloco in filas.items():
        ausente, botoes = bloco.split("|", 1)
        pecas = re.findall(r'<(?:button|a|span) class="btn mini( apagado)?"([^>]*)>([^<]+)', botoes)
        if [r for _, _, r in pecas] != ROTULOS:
            falta.append(f"{chave}: os botões não são {ROTULOS}")
            continue
        for (apagado, resto, _), gesto in zip(pecas, GESTOS, strict=True):
            deve_apagar = (gesto == "identificar-lancador") == (chave in ACHADOS)
            if bool(apagado) != deve_apagar:
                falta.append(f"{chave}: {gesto} {'apagado' if apagado else 'aceso'} fora do estado")
            if bool(apagado) != ('aria-disabled="true"' in resto):
                falta.append(f"{chave}: {gesto} apagado sem aria-disabled (ou o inverso)")
            # O apagado não leva gesto, destino nem chave: o Enter e o `click()` o disparavam.
            if apagado and re.search(r'data-gesto=|href=|data-v=', resto):
                falta.append(f"{chave}: {gesto} apagado ainda dispara o gesto")
            if not apagado and f'data-gesto="{gesto}"' not in resto:
                falta.append(f"{chave}: {gesto} aceso sem o gesto")
        if bool(ausente.strip()) == (chave in ACHADOS):
            falta.append(f"{chave}: a fila não diz se foi achada")
    if "abrir-lancador" in doc or re.search(r">Abrir<", doc):
        falta.append("o «Abrir» voltou a uma fila")
    if 'class="ajuda' in doc:
        falta.append("um «?» voltou; a dica mora no data-dica")
    return falta


def test_as_filas_tem_os_tres_botoes_e_o_estado_certo() -> None:
    assert _problemas(_doc()) == []


def test_a_tira_chama_a_aba_de_experimental() -> None:
    # D-1810-A-ABA-EXPERIMENTAL-SE-PUBLICA-COMO-FICOU
    tira = re.search(r'<div class="tira">(.*?)</div>', _doc(), flags=re.S).group(1)
    ativa = re.findall(r'<a class="aba ativa" href="07-lancadores.html">([^<]+)</a>', tira)
    assert ativa == ["Experimental"], ativa
    assert "Lançadores</a>" not in tira


def test_a_regua_morde_o_abrir_o_acender_o_botao_errado_e_o_ponto_de_interrogacao() -> None:
    doc = _doc()
    abrir = '<button class="btn mini" data-gesto="abrir-lancador">Abrir</button>'
    com_abrir = doc.replace('<span class="lf-botoes">', f'<span class="lf-botoes">{abrir}', 1)
    assert any("Abrir" in p for p in _problemas(com_abrir))
    heroic = doc.index('data-lancador="heroic"')
    apagado = '<span class="btn mini apagado" aria-disabled="true">Configurar</span>'
    pos = doc.index(apagado, heroic)
    aceso = (doc[:pos] + '<a class="btn mini" href="#lanc-conf" data-gesto="configurar-lancador"'
             ' data-v="heroic">Configurar</a>' + doc[pos + len(apagado):])
    assert any("heroic: configurar-lancador aceso" in p for p in _problemas(aceso))
    com_gesto = (doc[:pos] + '<a class="btn mini apagado" aria-disabled="true" href="#lanc-conf" '
                 'data-gesto="configurar-lancador" data-v="heroic">Configurar</a>'
                 + doc[pos + len(apagado):])
    assert any("heroic: configurar-lancador apagado ainda dispara" in p
               for p in _problemas(com_gesto))
    sem_botao = doc.replace('<a class="btn mini" href="#lanc-conf" data-gesto="configurar-lancador"'
                            ' data-v="lutris">Configurar</a>', "")
    assert any(p.startswith("lutris: os botões") for p in _problemas(sem_botao))
    com_span = doc.replace('<div class="miolo">', '<div class="miolo"><span class="ajuda">?</span>')
    assert any("«?»" in p for p in _problemas(com_span))


def test_nenhuma_fila_tem_texto_de_ajuda_nem_aviso() -> None:
    """A dica mora no `data-dica` do nome do quadro; a fila não explica nem avisa."""
    doc = _doc()
    assert 'class="ajuda' not in doc
    fila = re.search(r'<div class="lanc-fila">.*?</div>\s*</div>\s*</div>', doc,
                     flags=re.S).group(0)
    assert "data-dica=" in doc[doc.index('class="quadro-titulo" for="cx7-2"'):][:200]
    assert "impedimento" not in fila.lower() and "aviso" not in fila.lower()


def test_a_janela_dos_impedimentos_so_se_alcanca_por_configurar() -> None:
    doc = _doc()
    alvos = [(m.start(), m.group(0)) for m in re.finditer(r'href="#impedimentos"', doc)]
    assert alvos, "ninguém leva à janela dos impedimentos"
    conf = doc.index('id="lanc-conf"')
    imp = doc.index('id="impedimentos"')
    fora = [pos for pos, _ in alvos if not (conf <= pos < imp) and pos < imp]
    assert fora == [], "um link para #impedimentos fora de «Configurar»"
    steam = _filas(doc)["steam"]
    assert "impedimentos" not in steam


@pytest.fixture(scope="module")
def pagina():
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        pg = nav.new_page(viewport={"width": 1212, "height": 809})
        yield pg
        nav.close()


def _visivel(pg, ident: str) -> bool:
    return bool(pg.evaluate(
        "(i) => { const e = document.getElementById(i); const r = e.getBoundingClientRect();"
        " return getComputedStyle(e).display !== 'none' && r.width > 0; }", ident))


def test_configurar_e_criar_perfis_abrem_a_janela_e_o_impedimento_vem_depois(pagina) -> None:
    pagina.goto(MOCKUP.as_uri())
    assert not _visivel(pagina, "lanc-conf") and not _visivel(pagina, "escolher-jogo")
    pagina.click('.lf[data-lancador="steam"] [data-gesto="configurar-lancador"]')
    assert _visivel(pagina, "lanc-conf")
    pagina.click('#lanc-conf [data-gesto="ver-impedimentos"]')
    assert _visivel(pagina, "impedimentos")
    pagina.goto(MOCKUP.as_uri() + "#")
    pagina.click('.lf[data-lancador="steam"] [data-gesto="criar-perfil-para-um-jogo"]')
    assert _visivel(pagina, "escolher-jogo")


def test_o_botao_apagado_de_um_nao_achado_nao_abre_nada(pagina) -> None:
    """Nem o mouse nem o ``click()`` da ponte: o apagado não abre a janela nem acha gesto."""
    pagina.goto(MOCKUP.as_uri() + "#")
    ev, gesto = pagina.evaluate("""() => { const a = document.querySelectorAll(
      '.lf[data-lancador="heroic"] .lf-botoes .btn')[2];
      a.click();
      return [getComputedStyle(a).pointerEvents, a.closest('[data-gesto],[data-v],a[href]')]; }""")
    assert ev == "none", "o botão apagado ainda recebe o clique"
    assert gesto is None, "o botão apagado ainda leva um gesto que o clique dispara"
    assert not _visivel(pagina, "lanc-conf"), "o «Configurar» apagado abriu a janela"
