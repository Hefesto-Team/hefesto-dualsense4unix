"""Os efeitos aparecem por família nas abas 03, 04 e 05, e a chave de cada um não muda (20/10/2026).

Decisões que esta prova segura (as cinco do registro de 20/10, `docs/data/decisoes-de-produto.csv`):

* D-2010-A-FRASE-DO-EFEITO-MORA-NA-DICA: a frase vai no `title` da opção e na dica da caixa, nunca
  como texto embaixo do campo;
* D-2010-O-EFEITO-DO-GATILHO-SE-AGRUPA-POR-FAMILIA: a lista do 03 abre em `optgroup` por família e
  a família é a etiqueta à esquerda da caixa;
* D-2010-OS-ACIONAMENTOS-FICAM-ATRAS-DO-AVANCADO: «Como o gatilho faz» só aparece com a chave
  «Avançado» ligada, e a chave nasce desligada;
* D-2010-O-EFEITO-IMERSAO-VIRA-PADRAO-DOS-MOTORES: o 05 chama de «Padrão dos motores», sem «Só o
  jogo», e a háptica ganha Eco, Grão e Motor de época;
* D-2010-A-PERFIS-NAO-GANHA-A-RECEITA-DO-ESTILO: a aba 10 não muda (nenhuma das três abas desta
  prova a toca, e a 10 segue sem o bloco do estilo).

MORDIDAS (executadas sobre uma cópia, e cada uma reprova a régua que a guarda):

* devolver a frase como texto embaixo do select da 03 (`<span class="g2-frase">`) ->
  `test_a_03_nao_escreve_a_frase_embaixo_da_caixa`;
* tirar a guarda do «Avançado» (`.g2-av{display:none !important}`) ->
  `test_o_avancado_guarda_os_acionamentos_e_lembra_na_sessao`;
* trocar a chave de um efeito (`golpe-leve` por `golpe-fraco`) ->
  `test_as_chaves_dos_efeitos_nao_mudam`.
"""

from __future__ import annotations

import pathlib
import re
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

import pytest

from hefesto_dualsense4unix.interface.pacotes import a03_gatilhos
from hefesto_dualsense4unix.interface.pacotes.meus_efeitos import PREFIXO_DO_MEU
from hefesto_dualsense4unix.profiles import efeitos_de_imersao as imersoes
from hefesto_dualsense4unix.profiles import formas_de_haptica, schema

if TYPE_CHECKING:
    from playwright.sync_api import Browser

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup"
_INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
PUBLICADO = _INTERFACE / "paginas"  # (noqa-acento: nome da pasta)
CHROME = pathlib.Path("/usr/bin/google-chrome")
LARGURAS = ((1212, 809), (1918, 840), (1212, 740))

FAMILIAS = ("Golpe", "Carga", "Peso", "Travar", "Terreno", "Pulso", "Clique")
ACIONAMENTOS = ("Resistência", "Metralhadora", "Disparo", "Arco", "Gatilho")
LUZ_DA_04 = ("Sem efeito", "Luz fixa", "Respirar", "Batida", "Chama", "Maré", "Piscar",
             "Arco-íris")
MOTORES_DA_05 = ("Tranco", "Batida", "Onda", "Coice", "Pancada do lado")
HAPTICA_NOVA = ("Eco", "Grão", "Motor de época")

#: As 35 chaves das imersões do gatilho em 19/10/2026: o perfil e o clique falam por elas, e o
#: nome que a tela mostra nunca as define.
CHAVES_DAS_IMERSOES = (
    "ferrolho-que-volta", "trava-seca", "pino-que-falha", "batida-do-coracao", "arma-pesada",
    "aperto-que-trava", "golpe-leve", "golpe-pesado", "clique-no-meio", "clique-mouse",
    "golpe-falha", "golpe-aparo", "rajada-que-sobe-sozinha", "cano-que-esquenta",
    "recuo-pesado", "corda-que-estica", "flecha-que-escapa", "braco-cansado",
    "freio-abs-que-pulsa", "pedal-duro", "pique-que-cansa", "golpe-carregado", "mira-firme",
    "carga-folego", "travar-esgotado", "porta-emperrada", "escudo-que-aguenta", "duas-travas",
    "galope-no-chao", "motor-que-sobe", "terreno-que-muda", "besta", "agarrar",
    "energia-que-cresce", "motor-no-acelerador")
HAPTICA_ANTIGA = ("do_estilo", "sem_efeito", "toque", "impacto", "estalo", "guarda", "aparo",
                  "som_no_corpo")
LUZ_ANTIGA = ("respirar", "piscar", "arco-iris", "batimento", "chama", "mare")


def _doc(nome: str) -> str:
    return (MOCKUP / f"{nome}.html").read_text(encoding="utf-8")


def _sem_estilo(doc: str) -> str:
    return re.sub(r"<(style|script)\b[^>]*>.*?</\1>", "", doc, flags=re.S)


def _selects(doc: str, classe: str, extra: str = "") -> list[str]:
    padrao = r'<select\b[^>]*class="[^"]*\b' + classe + r'\b[^"]*"[^>]*>.*?</select>'
    return [s for s in re.findall(padrao, _sem_estilo(doc), flags=re.S) if extra in s]


def _opcoes(select: str) -> list[str]:
    return [t for t in re.findall(r"<option\b[^>]*>([^<]*)</option>", select) if t != "—"]


def _grupos(select: str) -> list[str]:
    return re.findall(r'<optgroup label="([^"]*)"', select)


def _valores(select: str) -> list[str]:
    return re.findall(r'<option value="([^"]*)"', select)


# ---------------------------------------------------------------------------------------------
# 03 — a família, a frase na dica e o avançado
# ---------------------------------------------------------------------------------------------

def _problemas_da_lista_do_03(doc: str) -> list[str]:
    falta: list[str] = []
    efeitos = _selects(doc, "g2-imersao")
    if len(efeitos) != 8:
        return [f"o 03 tem {len(efeitos)} listas de efeito do gatilho (8)"]
    for s in efeitos:
        if not set(FAMILIAS) <= set(_grupos(s)):
            falta.append("a lista não abre em grupos pelas sete famílias")
        if "Sem efeito" not in _opcoes(s):
            falta.append("a lista perdeu o «Sem efeito»")
        for t in _opcoes(s):
            if t in ACIONAMENTOS:
                falta.append(f"o acionamento «{t}» voltou à lista do efeito")
            if t[:1] != t[:1].upper():
                falta.append(f"«{t}» não começa por maiúscula")
            if " · " in t:
                falta.append(f"«{t}» repete a família, que já é o grupo")
    sem_dica = re.findall(r'<option value="(?!—|meu:)[^"]*"(?![^>]*title=)[^>]*>([^<]*)<',
                          efeitos[0])
    if sem_dica:
        falta.append(f"opções sem a frase na dica: {sem_dica[:3]}")
    etiquetas = re.findall(r'<i class="g2-fam"[^>]*data-campo="familia-imersao-[ed]"', doc)
    if len(etiquetas) != 8:
        falta.append(f"a etiqueta de família está em {len(etiquetas)} lugares (8)")
    return falta


def test_a_03_agrupa_o_efeito_do_gatilho_por_familia() -> None:
    # D-2010-O-EFEITO-DO-GATILHO-SE-AGRUPA-POR-FAMILIA
    assert _problemas_da_lista_do_03(_doc("03-gatilhos")) == []


def _problemas_da_frase_do_03(doc: str) -> list[str]:
    visivel = _sem_estilo(doc)
    falta: list[str] = []
    if re.search(r'class="[^"]*\bg2-frase\b', visivel):
        falta.append("a frase do efeito é texto embaixo da caixa")
    if "g2-frase" in doc:
        falta.append("a folha ainda cuida de uma frase embaixo da caixa")
    return falta


def test_a_03_nao_escreve_a_frase_embaixo_da_caixa() -> None:
    # D-2010-A-FRASE-DO-EFEITO-MORA-NA-DICA
    """MORDIDA: devolver `<span class="g2-frase">` sob o select reprova."""
    doc = _doc("03-gatilhos")
    assert _problemas_da_frase_do_03(doc) == []
    frase = '<span class="g2-frase">Uma frase.</span>'
    mordido = doc.replace('<i class="g2-fam"', frase + '<i class="g2-fam"', 1)
    assert mordido != doc
    assert _problemas_da_frase_do_03(mordido)


def test_a_dica_da_caixa_leva_o_nome_e_a_frase() -> None:
    """O nome vem de `Família · variante`, e a frase só aparece na dica."""
    for imersao in imersoes.IMERSOES:
        dica = a03_gatilhos.dica_da_imersao(imersao.chave)
        assert dica == f"{imersao.rotulo}. {imersao.dica}"
        assert " · " in imersao.rotulo, imersao.chave
        assert imersoes.familia_da_pagina(imersao) in imersoes.FAMILIAS_DA_PAGINA
    assert a03_gatilhos.dica_da_imersao(a03_gatilhos.SEM_IMERSAO).startswith("Sem efeito.")
    assert a03_gatilhos.familia_da_imersao(a03_gatilhos.SEM_IMERSAO) == ""
    assert a03_gatilhos.familia_da_imersao("golpe-leve") == "Golpe"


def test_o_pacote_monta_a_lista_em_grupos_com_a_frase_no_title() -> None:
    html = a03_gatilhos.html_das_opcoes_de_imersao()
    assert all(f'<optgroup label="{f}">' in html for f in FAMILIAS)
    assert re.search(r'<option value="nenhum" title="[^"]+">Sem efeito</option>', html)
    chaves = set(re.findall(r'<option value="([^"]+)" title=', html))
    esperadas = {i.chave for i in imersoes.IMERSOES} - set(imersoes.IGUAL_A)
    assert esperadas <= chaves


_ACIONAMENTOS_VISIVEIS = """() => [...document.querySelectorAll('.g2-av')]
  .filter(e => getComputedStyle(e).display !== 'none' && e.clientHeight > 0).length"""


@pytest.fixture(scope="module")
def navegador() -> Iterator[Browser]:
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        yield nav
        nav.close()


def _o_avancado(navegador: Browser, arquivo: pathlib.Path) -> tuple[int, int, bool]:
    """(visíveis fechado, visíveis aberto, aberto de novo após recarregar na mesma sessão)."""
    pg = navegador.new_page(viewport={"width": 1212, "height": 809})
    try:
        pg.goto(arquivo.as_uri())
        pg.wait_for_load_state("networkidle")
        fechado = int(pg.evaluate(_ACIONAMENTOS_VISIVEIS))
        pg.click(".g2-avtog")
        aberto = int(pg.evaluate(_ACIONAMENTOS_VISIVEIS))
        pg.reload()
        pg.wait_for_load_state("networkidle")
        lembrou = bool(pg.evaluate("document.querySelector('.g2-avtog input').checked"))
        return fechado, aberto, lembrou
    finally:
        pg.close()


def test_o_avancado_nasce_desligado_e_tem_as_mesmas_chaves() -> None:
    doc = _doc("03-gatilhos")
    topo = doc[doc.index('class="quadro-topo"'):]
    topo = topo[:topo.index('class="quadro-corpo"')]
    assert 'class="g2-avtog"' in topo
    assert 'modo-auto g2-avtog' not in topo, (
        "a chave local não leva a classe do Modo automático: o piloto a leria como gesto")
    assert topo.index("g2-avtog") < topo.index('data-gesto="modo-dos-gatilhos"')
    assert "checked" not in re.search(r'<input type="checkbox"[^>]*>', topo).group(0)  # type: ignore[union-attr]
    acions = _selects(doc, "g2-acion")
    assert len(acions) == 8
    publicado = (PUBLICADO / "03-gatilhos.html").read_text(encoding="utf-8")
    for s, velho in zip(acions, _selects(publicado, "g2-acion"), strict=True):
        assert 'data-gesto="modo"' in s
        assert _valores(s) == _valores(velho), "as chaves dos acionamentos mudaram"
    assert doc.count('class="g2-cel g2-av') == 8 and doc.count('class="g2-rot g2-av"') == 2


def test_o_avancado_guarda_os_acionamentos_e_lembra_na_sessao(navegador: Browser,
                                                              tmp_path: pathlib.Path) -> None:
    # D-2010-OS-ACIONAMENTOS-FICAM-ATRAS-DO-AVANCADO
    """Fechado esconde as linhas «Como o gatilho faz»; ligado as mostra e a sessão lembra.

    MORDIDA: tirar a guarda `.g2-av{display:none !important}` deixa as linhas à mostra com a
    chave desligada, e a régua reprova.
    """
    fechado, aberto, lembrou = _o_avancado(navegador, MOCKUP / "03-gatilhos.html")
    assert fechado == 0, "com o Avançado desligado nada de «Como o gatilho faz» à mostra"
    assert aberto >= 4 and lembrou
    doc = _doc("03-gatilhos")
    mordido = doc.replace(".g2-av{display:none !important}", "", 1)
    assert mordido != doc
    arquivo = tmp_path / "03-mordido.html"
    arquivo.write_text(mordido, encoding="utf-8")
    assert _o_avancado(navegador, arquivo)[0] > 0


# ---------------------------------------------------------------------------------------------
# 04 e 05
# ---------------------------------------------------------------------------------------------

def test_a_04_tem_os_nomes_novos_da_luz_com_a_frase_na_dica() -> None:
    doc = _doc("04-iluminacao")
    listas = _selects(doc, "g4-efeito")
    assert len(listas) == 4
    for s in listas:
        textos = _opcoes(s)
        for esperado in LUZ_DA_04:
            assert esperado in textos, esperado
        assert "Batida do coração" not in textos
        assert _grupos(s), "a lista da luz abre em grupos"
        assert all(t[:1] == t[:1].upper() for t in textos)
    assert 'class="g4-frase"' not in _sem_estilo(doc), "a frase da luz mora só na dica"


def test_o_05_chama_de_padrao_dos_motores_e_traz_a_haptica_nova() -> None:
    # D-2010-O-EFEITO-IMERSAO-VIRA-PADRAO-DOS-MOTORES
    doc = _doc("05-vibracao")
    texto = _sem_estilo(doc)
    assert "Efeito imersão" not in texto
    padroes = _selects(doc, "vib-efeito", 'data-gesto="efeito-imersao"')
    haptica = _selects(doc, "vib-efeito", 'data-gesto="efeito-haptico"')
    assert len(padroes) == 4 and len(haptica) == 4
    for s in padroes:
        assert 'aria-label="Padrão dos motores"' in s
        opcoes = _opcoes(s)
        assert "Sem efeito" in opcoes and not any("Só o jogo" in t for t in opcoes)
        assert all(t in opcoes for t in MOTORES_DA_05)
    for s in haptica:
        assert all(t in _opcoes(s) for t in HAPTICA_NOVA)
    assert "Só o jogo" not in texto
    assert 'class="vib-frase"' not in texto


def test_a_10_nao_ganha_a_receita_do_estilo() -> None:
    # D-2010-A-PERFIS-NAO-GANHA-A-RECEITA-DO-ESTILO
    assert "estilo-liga" not in _doc("10-perfis")


# ---------------------------------------------------------------------------------------------
# as chaves não mudam
# ---------------------------------------------------------------------------------------------

def test_as_chaves_dos_efeitos_nao_mudam() -> None:
    """O perfil guarda os números e a chave; o nome da tela é só rótulo.

    MORDIDA: trocar `golpe-leve` por `golpe-fraco` (o nome novo) reprova.
    """
    assert tuple(i.chave for i in imersoes.IMERSOES) == CHAVES_DAS_IMERSOES
    assert set(HAPTICA_ANTIGA) <= set(formas_de_haptica.ESCOLHAS)
    assert set(HAPTICA_NOVA) == {formas_de_haptica.ROTULOS[c] for c in formas_de_haptica.ESCOLHAS
                                 if c not in HAPTICA_ANTIGA}
    assert tuple(schema.BASES_DA_LUZ) == LUZ_ANTIGA


def test_um_perfil_de_chave_velha_abre_com_o_efeito_certo() -> None:
    """Os números de cada imersão acham a própria chave, e essa chave existe na lista nova."""
    from hefesto_dualsense4unix.app.actions.trigger_specs import (
        get_spec,
        preset_to_positional_params,
    )

    html = a03_gatilhos.html_das_opcoes_de_imersao()
    for imersao in imersoes.IMERSOES:
        modo = next(iter(imersao.ajustes))
        spec = get_spec(modo)
        achados = imersoes.ajustes_da_imersao(imersao, modo)
        if spec is None or achados is None:
            continue
        params = [int(v) for v in preset_to_positional_params(spec, achados)]
        chave = a03_gatilhos._imersao_que_casa(modo, params)
        esperado = imersoes.IGUAL_A.get(imersao.chave, imersao.chave)
        assert chave in (imersao.chave, esperado) or chave.startswith(PREFIXO_DO_MEU)
        assert f'value="{chave}"' in html, (imersao.chave, chave)


def test_a_escolha_de_um_efeito_de_outro_acionamento_leva_ao_acionamento_dele() -> None:
    """A lista mostra todos os efeitos: o que não vale no acionamento de agora vai ao de origem."""
    arco = imersoes.POR_CHAVE["corda-que-estica"]
    assert imersoes.modo_que_a_imersao_pede(arco, "Weapon") == "Bow"
    assert imersoes.modo_que_a_imersao_pede(arco, "Bow") == "Bow"
    golpe = imersoes.POR_CHAVE["golpe-leve"]
    assert imersoes.modo_que_a_imersao_pede(golpe, "Resistance") == "Weapon"


# ---------------------------------------------------------------------------------------------
# sem rolagem vertical
# ---------------------------------------------------------------------------------------------

_ROLADORES = """() => { const d = document.documentElement;
  const rol = [...document.querySelectorAll('*')].filter(e => e.clientHeight > 0
    && e.scrollHeight > e.clientHeight + 1
    && ['auto', 'scroll'].includes(getComputedStyle(e).overflowY))
    .map(e => e.tagName + '.' + e.className);
  return {lateral: d.scrollWidth > d.clientWidth + 1, rol,
          sobra: d.scrollHeight - d.clientHeight}; }"""


def _medir(navegador: Browser, arquivo: pathlib.Path, larg: int, alt: int,
           antes: str = "") -> dict[str, Any]:
    pg = navegador.new_page(viewport={"width": larg, "height": alt})
    try:
        pg.goto(arquivo.as_uri())
        pg.wait_for_load_state("networkidle")
        if antes:
            pg.evaluate(antes)
            pg.wait_for_timeout(150)
        medida: dict[str, Any] = pg.evaluate(_ROLADORES)
        return medida
    finally:
        pg.close()


@pytest.mark.parametrize(("larg", "alt"), LARGURAS)
@pytest.mark.parametrize("nome", ("03-gatilhos", "04-iluminacao", "05-vibracao"))
def test_nenhuma_das_tres_abas_rola_na_vertical(navegador: Browser, nome: str, larg: int,
                                                alt: int) -> None:
    """Nada rola além do que a página publicada de hoje já rolava, nem com o Avançado ligado."""
    base = _medir(navegador, PUBLICADO / f"{nome}.html", larg, alt)
    cena = _medir(navegador, MOCKUP / f"{nome}.html", larg, alt)
    novos = [r for r in cena["rol"] if r not in base["rol"]]
    assert not novos and not cena["lateral"], (nome, larg, alt, novos)
    assert cena["sobra"] <= base["sobra"], (nome, larg, alt, cena["sobra"], base["sobra"])
    if nome.startswith("03-"):
        aberto = _medir(navegador, MOCKUP / f"{nome}.html", larg, alt,
                        'document.querySelector(".g2-avtog input").click()')
        novos = [r for r in aberto["rol"] if r not in base["rol"]]
        assert not novos and not aberto["lateral"], (nome, "avançado ligado", larg, alt, novos)
        assert aberto["sobra"] <= base["sobra"], (nome, "avançado ligado", larg, alt)
