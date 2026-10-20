"""O desenho dos efeitos por família nas abas 03, 04, 05 e 10, em duas opções cada (20/10/2026).

Só desenho: as oito variantes moram em `mockup/variantes/` e nunca entram na página publicada nem
no produto; o conteúdo (nomes, famílias, frases) é o da página aprovada em 19/10/2026. As réguas
cobrem o que a sprint pede: o nome pelo que acontece, a família como grupo ou como prefixo, os
acionamentos fora da lista principal, o padrão dos motores, a receita do estilo, e nenhuma
rolagem vertical nas três larguras.

MORDIDAS (executadas aqui, sobre uma cópia do HTML, e cada uma reprova a régua que a guarda):

* tirar o `<optgroup>` das famílias da variante A do 03 -> `test_o_03_a_agrupa_por_familia`;
* pôr o «Resistência» na lista do efeito -> `test_o_03_nao_mistura_o_acionamento_morde`;
* tirar o prefixo da família do nome na variante B -> `test_o_03_b_poe_a_familia_no_nome`;
* trocar um nome da luz pelo antigo -> `test_o_04_tem_os_nomes_novos_da_luz`;
* devolver o «Efeito imersão» ao 05 -> `test_o_05_chama_de_padrao_dos_motores`;
* tirar o «Eco» da háptica -> `test_o_05_traz_os_tres_padroes_novos_da_haptica`;
* tirar um item da receita do 10 -> `test_o_10_mostra_o_que_o_estilo_liga`;
* pôr uma altura que estoura a tela -> `test_nenhuma_variante_rola_na_vertical`.
"""

from __future__ import annotations

import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup"
VARIANTES = MOCKUP / "variantes"
CHROME = pathlib.Path("/usr/bin/google-chrome")
LARGURAS = ((1212, 809), (1918, 840), (1212, 740))

NOMES = (
    "03-efeitos-A-familia-em-grupos", "03-efeitos-B-familia-no-nome",
    "04-efeitos-A-nome-e-frase", "04-efeitos-B-nome-so",
    "05-efeitos-A-padrao-dos-motores", "05-efeitos-B-padrao-com-frase",
    "10-efeitos-A-receita-em-linhas", "10-efeitos-B-receita-em-chips",
)
FAMILIAS = ("Golpe", "Carga", "Peso", "Travar", "Terreno", "Pulso", "Clique")
ACIONAMENTOS = ("Resistência", "Metralhadora", "Disparo", "Arco", "Gatilho")
LUZ = ("Luz fixa", "Respirar", "Batida", "Chama", "Maré", "Arco-íris", "Na batida",
       "Acende no gatilho", "Bateria")
MOTORES = ("Tranco", "Batida", "Onda", "Coice", "Pancada do lado", "Só o jogo")
HAPTICA_NOVA = ("Eco", "Grão", "Motor de época")
RECEITA = ("R2", "L2", "Háptica", "Motores", "Luz")
PRINCIPAL = {"03": "03-gatilhos", "04": "04-iluminacao", "05": "05-vibracao", "10": "10-perfis"}


def _ler(nome: str) -> str:
    return (VARIANTES / f"{nome}.html").read_text(encoding="utf-8")


def _sem_estilo(doc: str) -> str:
    return re.sub(r"<(style|script)\b[^>]*>.*?</\1>", "", doc, flags=re.S)


def _selects(doc: str, classe: str, extra: str = "") -> list[str]:
    padrao = r'<select\b[^>]*class="' + classe + r'"[^>]*>.*?</select>'
    achados = re.findall(padrao, _sem_estilo(doc), flags=re.S)
    return [s for s in achados if extra in s]


def _opcoes(select: str) -> list[str]:
    return [t for t in re.findall(r"<option\b[^>]*>([^<]*)</option>", select) if t != "—"]


def _grupos(select: str) -> list[str]:
    return re.findall(r'<optgroup label="([^"]*)"', select)


def _maiuscula(texto: str) -> bool:
    return texto[:1] == texto[:1].upper()


# ---------------------------------------------------------------------------------------------
# 03
# ---------------------------------------------------------------------------------------------

def _problemas_03(nome: str, doc: str) -> list[str]:
    falta: list[str] = []
    efeitos = _selects(doc, "g2-imersao")
    acions = _selects(doc, "g2-acion")
    if len(efeitos) != 8 or len(acions) != 8:
        return [f"o 03 tem {len(efeitos)} efeitos e {len(acions)} acionamentos (8 e 8)"]
    for s in efeitos:
        if 'aria-label="Efeito do gatilho"' not in s:
            falta.append("um «Efeito do gatilho» perdeu o rótulo")
        for texto in _opcoes(s):
            if texto in ACIONAMENTOS:
                falta.append(f"o acionamento «{texto}» voltou à lista do efeito")
            if not _maiuscula(texto):
                falta.append(f"«{texto}» não começa por maiúscula")
    for s in acions:
        if 'aria-label="Como o gatilho faz"' not in s:
            falta.append("um acionamento perdeu o rótulo «Como o gatilho faz»")
        if "Resistência" not in _opcoes(s):
            falta.append("o «Como o gatilho faz» perdeu o acionamento")
    if "g2-av" not in doc or 'class="modo-auto g2-avtog"' not in doc:
        falta.append("sem a chave do avançado")
    if "Efeito de imersão</span>" in _sem_estilo(doc) and "Efeito do gatilho" not in doc:
        falta.append("o rótulo antigo de imersão ficou")
    p1 = _opcoes(efeitos[0])
    if nome.endswith("A-familia-em-grupos"):
        if not set(FAMILIAS) <= set(_grupos(efeitos[0])):
            falta.append("a lista da A não agrupa pelas sete famílias")
        if any(" · " in t for t in p1):
            falta.append("a A repete a família no nome, e ela já é o grupo")
    else:
        com_familia = [t for t in p1 if " · " in t]
        if len(com_familia) < 30:
            falta.append("a B não põe a família no nome («Família · variante»)")
        if any(t.split(" · ")[0] not in FAMILIAS for t in com_familia):
            falta.append("a B tem um prefixo que não é família")
    frases = re.findall(r'<span class="g2-frase">([^<]*)</span>', doc)
    if len([f for f in frases if f]) != 4:
        falta.append("a frase do efeito falta nas quatro células conectadas")
    # o mockup de hoje põe a frase de cada imersão na dica da opção; a variante não a perde
    sem_dica = re.findall(r'<option value="(?!—|meu:)[^"]*"(?![^>]*title=)[^>]*>([^<]*)<',
                          efeitos[0])
    if sem_dica:
        falta.append(f"opções sem a frase na dica: {sem_dica[:3]}")
    return falta


@pytest.mark.parametrize("nome", NOMES[:2])
def test_o_03_nao_mistura_o_acionamento(nome: str) -> None:
    assert _problemas_03(nome, _ler(nome)) == []


def test_o_03_a_agrupa_por_familia() -> None:
    doc = _ler("03-efeitos-A-familia-em-grupos")
    assert set(FAMILIAS) <= set(_grupos(_selects(doc, "g2-imersao")[0]))
    mordido = re.sub(r"<optgroup label=\"[^\"]*\">|</optgroup>", "", doc)
    assert any("agrupa" in p for p in _problemas_03("03-efeitos-A-familia-em-grupos", mordido))


def test_o_03_b_poe_a_familia_no_nome() -> None:
    doc = _ler("03-efeitos-B-familia-no-nome")
    assert "Golpe · rajada que sobe" in _opcoes(_selects(doc, "g2-imersao")[0])
    # o prefixo some de todas as opções: a régua conta o que sobra
    familias = "Golpe|Carga|Peso|Travar|Terreno|Pulso|Clique"
    mordido = re.sub(r">(?:" + familias + r") · ([^<]*)</option>", r">\1</option>", doc)
    problemas = _problemas_03("03-efeitos-B-familia-no-nome", mordido)
    assert any("família no nome" in p for p in problemas)


def test_o_03_nao_mistura_o_acionamento_morde() -> None:
    doc = _ler("03-efeitos-B-familia-no-nome")
    primeira = _selects(doc, "g2-imersao")[0]
    mordida = primeira.replace("</select>", "<option>Resistência</option></select>")
    assert any("Resistência" in p for p in _problemas_03("03-efeitos-B-familia-no-nome",
                                                         doc.replace(primeira, mordida, 1)))


def test_o_03_morde_a_opcao_sem_dica() -> None:
    doc = _ler("03-efeitos-A-familia-em-grupos")
    mordido = re.sub(r'(<option value="golpe-leve"[^>]*?) title="[^"]*"', r"\1", doc)
    assert mordido != doc
    assert any("dica" in p for p in _problemas_03("03-efeitos-A-familia-em-grupos", mordido))


def test_o_03_guarda_a_fiacao_dos_selects() -> None:
    """As chaves de antes seguem nos selects: o produto ainda lê `imersao` e `modo`."""
    doc = _ler("03-efeitos-A-familia-em-grupos")
    assert doc.count('data-gesto="imersao"') == 8 and doc.count('data-gesto="modo"') >= 8
    assert 'data-campo="imersao-e"' in doc and 'data-campo="modo-chave-d"' in doc
    assert 'data-hef-forma="acion-p2-d"' in doc


# ---------------------------------------------------------------------------------------------
# 04
# ---------------------------------------------------------------------------------------------

def _problemas_04(nome: str, doc: str) -> list[str]:
    falta: list[str] = []
    listas = _selects(doc, "g4-efeito")
    if len(listas) != 4:
        return [f"o 04 tem {len(listas)} listas de efeito (4)"]
    for s in listas:
        textos = _opcoes(s)
        for esperado in LUZ:
            if esperado not in textos:
                falta.append(f"a luz perdeu «{esperado}»")
        for t in textos:
            if not _maiuscula(t):
                falta.append(f"«{t}» não começa por maiúscula")
    frases = re.findall(r'<span class="g4-frase">([^<]+)</span>', doc)
    if nome.endswith("A-nome-e-frase") and len(frases) != 4:
        falta.append("a A tem a frase embaixo de cada lista")
    if nome.endswith("B-nome-so") and frases:
        falta.append("a B é só o nome, e a frase mora na dica")
    return falta


@pytest.mark.parametrize("nome", NOMES[2:4])
def test_o_04_tem_os_nomes_novos_da_luz(nome: str) -> None:
    assert _problemas_04(nome, _ler(nome)) == []


def test_o_04_morde_o_nome_antigo() -> None:
    doc = _ler("04-efeitos-A-nome-e-frase")
    mordido = doc.replace(">Maré<", ">Onda<")
    assert mordido != doc
    assert any("Maré" in p for p in _problemas_04("04-efeitos-A-nome-e-frase", mordido))


# ---------------------------------------------------------------------------------------------
# 05
# ---------------------------------------------------------------------------------------------

def _problemas_05(nome: str, doc: str) -> list[str]:
    falta: list[str] = []
    texto = _sem_estilo(doc)
    if "Efeito imersão" in texto:
        falta.append("o «Efeito imersão» ficou; o nome é «Padrão dos motores»")
    padroes = [s for s in _selects(doc, "vib-efeito") if 'data-gesto="efeito-imersao"' in s]
    haptica = [s for s in _selects(doc, "vib-efeito") if 'data-gesto="efeito-haptico"' in s]
    if len(padroes) != 4 or len(haptica) != 4:
        return [*falta, f"o 05 tem {len(padroes)} padrões e {len(haptica)} hápticas (4 e 4)"]
    for s in padroes:
        if 'aria-label="Padrão dos motores"' not in s:
            falta.append("um padrão perdeu o rótulo «Padrão dos motores»")
        for t in MOTORES:
            if t not in _opcoes(s):
                falta.append(f"o padrão dos motores perdeu «{t}»")
    for s in haptica:
        for t in HAPTICA_NOVA:
            if t not in _opcoes(s):
                falta.append(f"a háptica perdeu «{t}»")
    frases = re.findall(r'<span class="vib-frase">([^<]+)</span>', doc)
    if nome.endswith("B-padrao-com-frase") and len(frases) != 4:
        falta.append("a B tem a frase embaixo de cada padrão")
    if nome.endswith("A-padrao-dos-motores") and frases:
        falta.append("a A só troca o nome, sem frase")
    return falta


@pytest.mark.parametrize("nome", NOMES[4:6])
def test_o_05_chama_de_padrao_dos_motores(nome: str) -> None:
    assert _problemas_05(nome, _ler(nome)) == []


def test_o_05_morde_o_nome_antigo() -> None:
    doc = _ler("05-efeitos-A-padrao-dos-motores")
    mordido = doc.replace('aria-label="Padrão dos motores"', 'aria-label="Efeito imersão"', 1)
    assert mordido != doc
    assert any("rótulo" in p for p in _problemas_05("05-efeitos-A-padrao-dos-motores", mordido))


def test_o_05_traz_os_tres_padroes_novos_da_haptica() -> None:
    doc = _ler("05-efeitos-B-padrao-com-frase")
    mordido = doc.replace("<option value=\"eco\">Eco</option>", "")
    assert mordido != doc
    assert any("Eco" in p for p in _problemas_05("05-efeitos-B-padrao-com-frase", mordido))


# ---------------------------------------------------------------------------------------------
# 10
# ---------------------------------------------------------------------------------------------

def _problemas_10(nome: str, doc: str) -> list[str]:
    falta: list[str] = []
    bloco = re.search(r'<div class="estilo-liga"[^>]*>(.*?)</div></div>', _sem_estilo(doc),
                      flags=re.S)
    if not bloco:
        return ["sem o bloco «O que o estilo liga»"]
    corpo = bloco.group(1)
    itens = re.findall(r'<span class="rot">([^<]+)</span>', corpo)
    if tuple(itens) != RECEITA:
        falta.append(f"a receita mostra {itens}, e devia ser {list(RECEITA)}")
    if nome.endswith("A-receita-em-linhas") and corpo.count('class="frase"') != 5:
        falta.append("a A leva a frase em cada linha")
    if nome.endswith("B-receita-em-chips") and corpo.count('class="chip-liga"') != 5:
        falta.append("a B leva um chip por item")
    for nome_do_efeito in re.findall(r'<span class="nome">([^<]+)</span>', corpo):
        if not _maiuscula(nome_do_efeito):
            falta.append(f"«{nome_do_efeito}» não começa por maiúscula")
    return falta


@pytest.mark.parametrize("nome", NOMES[6:])
def test_o_10_mostra_o_que_o_estilo_liga(nome: str) -> None:
    assert _problemas_10(nome, _ler(nome)) == []


def test_o_10_morde_item_faltando() -> None:
    doc = _ler("10-efeitos-B-receita-em-chips")
    mordido = re.sub(r'<span class="chip-liga".{0,400}?Luz</span>.*?</span></span>', "", doc,
                     count=1, flags=re.S)
    assert mordido != doc
    assert _problemas_10("10-efeitos-B-receita-em-chips", mordido)


# ---------------------------------------------------------------------------------------------
# o que vale para as oito
# ---------------------------------------------------------------------------------------------

def test_as_oito_variantes_existem_e_os_mockups_principais_ficam_como_estao() -> None:
    for nome in NOMES:
        assert (VARIANTES / f"{nome}.html").is_file(), nome
    for principal in ("03-gatilhos", "04-iluminacao", "05-vibracao", "10-perfis"):
        doc = (MOCKUP / f"{principal}.html").read_text(encoding="utf-8")
        marcas = ("g2-avtog", "estilo-liga", "g4-frase")
        assert not any(m in doc for m in marcas), principal
        assert "vib-frase" not in doc, principal


def test_nenhuma_variante_traz_selo_nem_recado_novo() -> None:
    for nome in NOMES:
        base = _sem_estilo((MOCKUP / f"{PRINCIPAL[nome[:2]]}.html").read_text(encoding="utf-8"))
        doc = _sem_estilo(_ler(nome))
        selos = r'class="[^"]*\bselo\b'
        assert len(re.findall(selos, doc)) <= len(re.findall(selos, base)), nome
        recado = r">\s*(Novo|Nova|Bancada)\s*<"
        assert len(re.findall(recado, doc)) <= len(re.findall(recado, base)), nome


def _folhas_do_corpo(doc: str) -> list[str]:
    corpo = doc[doc.index("</head>"):]
    return re.findall(r"<style\b[^>]*>.*?</style>", corpo, flags=re.S)


def test_a_folha_da_variante_mora_na_cabeca() -> None:
    """O `<style>` do corpo é do produto: o `#plastico-vivo` da 04 é trocado a cada tique vivo, e a
    regra que entrasse ali sumiria no primeiro tique. MORDIDA: a regra da frase da 04 A dentro do
    `#plastico-vivo` (onde a primeira versão a pôs) reprova."""
    for nome in NOMES:
        base = (MOCKUP / f"{PRINCIPAL[nome[:2]]}.html").read_text(encoding="utf-8")
        assert _folhas_do_corpo(_ler(nome)) == _folhas_do_corpo(base), nome
    doc = _ler("04-efeitos-A-nome-e-frase")
    mordido = doc.replace('<style id="plastico-vivo"></style>',
                          '<style id="plastico-vivo">.g4-frase{display:block}</style>', 1)
    assert mordido != doc
    base = (MOCKUP / "04-iluminacao.html").read_text(encoding="utf-8")
    assert _folhas_do_corpo(mordido) != _folhas_do_corpo(base)


@pytest.fixture(scope="module")
def navegador():
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        yield nav
        nav.close()


_ROLADORES = """() => { const d = document.documentElement;
  const rol = [...document.querySelectorAll('*')].filter(e => e.clientHeight > 0
    && e.scrollHeight > e.clientHeight + 1
    && ['auto', 'scroll'].includes(getComputedStyle(e).overflowY))
    .map(e => e.tagName + '.' + e.className);
  return {lateral: d.scrollWidth > d.clientWidth + 1, rol,
          sobra: d.scrollHeight - d.clientHeight}; }"""


def _medir(navegador, arquivo: pathlib.Path, larg: int, alt: int, antes: str = "") -> dict:
    pg = navegador.new_page(viewport={"width": larg, "height": alt})
    try:
        pg.goto(arquivo.as_uri())
        pg.wait_for_load_state("networkidle")
        if antes:
            pg.evaluate(antes)
            pg.wait_for_timeout(150)
        return pg.evaluate(_ROLADORES)
    finally:
        pg.close()


@pytest.mark.parametrize(("larg", "alt"), LARGURAS)
@pytest.mark.parametrize("nome", NOMES)
def test_nenhuma_variante_rola_na_vertical(navegador, nome: str, larg: int, alt: int) -> None:
    """Nada rola além do que o mockup de hoje já rolava (a lista de perfis a 740 de altura)."""
    principal = PRINCIPAL[nome[:2]]
    base = _medir(navegador, MOCKUP / f"{principal}.html", larg, alt)
    cena = _medir(navegador, VARIANTES / f"{nome}.html", larg, alt)
    novos = [r for r in cena["rol"] if r not in base["rol"]]
    assert not novos and not cena["lateral"], (nome, larg, alt, novos)
    # o documento também: a 04 de hoje já passa da vista, e a variante não passa mais que ela
    assert cena["sobra"] <= base["sobra"], (nome, larg, alt, "documento", cena["sobra"],
                                            base["sobra"])
    if nome.startswith("03-"):
        aberto = _medir(navegador, VARIANTES / f"{nome}.html", larg, alt,
                        'document.querySelector(".g2-avtog input").click()')
        novos = [r for r in aberto["rol"] if r not in base["rol"]]
        assert not novos and not aberto["lateral"], (nome, "avançado aberto", larg, alt, novos)
        assert aberto["sobra"] <= base["sobra"], (nome, "avançado aberto", larg, alt)


def test_a_regua_de_rolagem_morde_o_documento_que_cresce(navegador, tmp_path) -> None:
    """A régua de elementos não vê o documento (o `html` não tem `overflow:auto`); esta vê."""
    doc = _ler("04-efeitos-A-nome-e-frase").replace(
        "</body>", '<div style="height:400px"></div></body>', 1)
    arquivo = tmp_path / "cresce.html"
    arquivo.write_text(doc, encoding="utf-8")
    base = _medir(navegador, MOCKUP / "04-iluminacao.html", 1212, 809)
    assert _medir(navegador, arquivo, 1212, 809)["sobra"] > base["sobra"]


_ORDEM_DA_RECEITA = """() => [...document.querySelectorAll('.estilo-liga .lin')].map(l => {
  const r = l.getBoundingClientRect();
  return [l.querySelector('.rot').textContent, r.left, r.top]; })"""


@pytest.mark.parametrize(("larg", "alt"), LARGURAS[:2])
def test_o_10_a_le_os_gatilhos_juntos_de_cima_para_baixo(navegador, tmp_path, larg: int,
                                                         alt: int) -> None:
    """Na grade de duas colunas (altura até 830 px), o R2 e o L2 ficam na mesma coluna, nessa ordem,
    e o título não empurra o R2 para o lado. MORDIDA: sem o `grid-auto-flow:column` o R2 vai para a
    direita do título e o L2 para baixo dele, na outra coluna."""
    def ordem(arquivo: pathlib.Path) -> dict:
        pg = navegador.new_page(viewport={"width": larg, "height": alt})
        try:
            pg.goto(arquivo.as_uri())
            pg.wait_for_load_state("networkidle")
            return {rot: (x, y) for rot, x, y in pg.evaluate(_ORDEM_DA_RECEITA)}
        finally:
            pg.close()

    def junto(o: dict) -> bool:
        return o["R2"][0] == o["L2"][0] and o["R2"][1] < o["L2"][1]

    assert junto(ordem(VARIANTES / "10-efeitos-A-receita-em-linhas.html")), (larg, alt)
    if alt <= 830:
        doc = _ler("10-efeitos-A-receita-em-linhas").replace(
            "grid-template-rows:repeat(3,auto);grid-auto-flow:column", "", 1)
        arquivo = tmp_path / "ordem.html"
        arquivo.write_text(doc, encoding="utf-8")
        assert not junto(ordem(arquivo))


def test_a_regua_de_rolagem_morde_uma_altura_que_estoura(navegador, tmp_path) -> None:
    doc = _ler("10-efeitos-B-receita-em-chips")
    doc = doc.replace("</style>", ".estilo-liga{height:260px !important}</style>", 1)
    arquivo = tmp_path / "estoura.html"
    arquivo.write_text(doc, encoding="utf-8")
    base = _medir(navegador, MOCKUP / "10-perfis.html", 1212, 809)
    cena = _medir(navegador, arquivo, 1212, 809)
    assert [r for r in cena["rol"] if r not in base["rol"]], cena
