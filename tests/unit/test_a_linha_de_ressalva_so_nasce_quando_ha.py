#!/usr/bin/env python3
"""A RÉGUA DA D-02: a linha de ressalva NASCE quando há o que dizer, e só então.

Decisão dela, 04/09/2026: *"Linha fixa só quando HÁ ressalva."*

O QUE ESTAVA EM JOGO: as ressalvas que explicam um valor estranho — *"em Nativo
o jogo é dono do LED"*, *"a Steam segurou"*, *"barra apagada"* — vivem só no
`title` de hover. Medido nas dezesseis decisões: a cura de quatro das cinco
conferências da aba 08 chega à tela SÓ dentro de um tooltip.

E O PREÇO QUE ELA NÃO ACEITA PAGAR é o contrário: uma linha permanente cobra a
altura da fonte em toda tela, inclusive nas que não têm nada a ressalvar. A
regra dela de 30/08 é *"texto na interface é zero"*. A peça concilia as duas —
**zero pixel no repouso, uma linha curta no estado estranho**.

**AS DUAS METADES SÃO A MESMA PEÇA**, e faltando uma a linha reaparece calada
num dos dois caminhos de emissão:

* `:empty{display:none}` — a linha que nasce vazia no desenho e nunca é pintada;
* `:has(.nada){display:none}` — a que o piloto pinta a CADA tique. Aqui o
  `:empty` não alcança: `escrever()` troca valor vazio por travessão, de
  propósito (um lugar vazio da mesa tem de apagar o que estava lá), e a linha
  ficaria com um `—` solto. Foi o que a primeira foto da `06-navegacao` mostrou.

**ELA LÊ, NÃO DIGITA.** Nenhum `display` e nenhum pixel estão escritos aqui. A
régua monta uma página pelo `monta.monta()`, abre no Chrome e compara a altura
de cada cena com a de uma cena de REFERÊNCIA medida na mesma página — o valor
sozinho, sem linha nenhuma. `display` é o mecanismo, e medir o mecanismo
deixaria passar uma linha escondida que ainda cobra espaço.

**A CENA É UMA COLUNA COM VÃO, e isso é medição, não cenário inventado.**
Primeira redação desta régua mediu a linha VAZIA dentro de um bloco comum e
dava VERDE COM A CURA ARRANCADA — as duas metades comentadas, sete casos
verdes. A causa está medida nesta bancada, com o Chrome:

    a linha vazia mede ZERO de altura mesmo SEM `display:none`
    (bloco vazio não gera caixa de linha, e o `margin-top` colapsa)

    e mesmo assim ela CUSTA 11 px na cena: 6 do `gap` da coluna + 5 do
    `margin-top` que, dentro de um flex, não colapsa com nada

Ou seja: **medir a altura do elemento responde "não ocupa" sobre uma linha que
ocupa.** Quem paga o pixel é o pai, e é lá que a régua tem de olhar. A coluna
com vão é como as abas empilham de verdade — `.vib-estado` da `05-vibracao`
(`display:flex;flex-direction:column;gap:6px`) e `.estados` da `06-navegacao`
são as duas precedentes vivas.

A MORDIDA: comente as duas metades no `monta.CSS_FOLHA` e rode. As cenas sem
ressalva ficam 11 px mais altas que a referência — a régua vê a ressalva sem
ressalva cobrando pixel na tela dela.
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

import monta
from hefesto_dualsense4unix.interface import onde

CHROME = pathlib.Path("/usr/bin/google-chrome")

#: A ressalva de prova. NÃO é texto de tela — o que cada aba vai dizer sai do
#: produto. Aqui ela só precisa ter forma reconhecível para a régua provar que
#: atravessa de quem chama até a altura na tela.
DIZ = "ressalva de prova: em Nativo o jogo é dono do LED"


def _pagina_de_prova(destino: pathlib.Path) -> pathlib.Path:
    """Uma página montada pelo `monta()`, com as quatro cenas da linha.

    Ela nasce num diretório temporário, pelo desvio `HEFESTO_BANCADA` que o
    `onde.py` documenta: a régua não toca a bancada dela.
    """
    import os

    anterior = os.environ.get("HEFESTO_BANCADA")
    os.environ["HEFESTO_BANCADA"] = str(destino)
    try:
        # A COLUNA COM VÃO — a forma em que as abas empilham valor e ressalva
        # (`.vib-estado` da 05, `.estados` da 06). É onde o custo da linha
        # invisível aparece: dentro de um flex o `gap` conta todo filho que
        # exista, e a margem não colapsa. Fora dele a régua dá verde sobre
        # defeito — medido, e está no cabeçalho.
        col = 'style="display:flex;flex-direction:column;gap:6px"'
        miolo = f"""    <div class="quadro"><div class="quadro-corpo">
      <div id="cena-so-valor" {col}><span>valor</span></div>
      <div id="cena-cheia" {col}><span>valor</span>
        {monta.ressalva("prova-cheia", DIZ)}</div>
      <div id="cena-nada" {col}><span>valor</span>
        {monta.ressalva("prova-nada")}</div>
      <div id="cena-nua" {col}><span>valor</span>
        <div class="ressalva"></div></div>
      <div id="cena-travessao" {col}><span>valor</span>
        <div class="ressalva">—</div></div>
    </div></div>"""
        monta.monta("98-prova-da-ressalva", "Prova da ressalva", miolo)
    finally:
        if anterior is None:
            os.environ.pop("HEFESTO_BANCADA", None)
        else:
            os.environ["HEFESTO_BANCADA"] = anterior
    return destino / "98-prova-da-ressalva.html"


O_QUE_O_NAVEGADOR_DESENHA = r"""
(() => {
  // A ALTURA DA CENA, e não a da linha. Uma `.ressalva` vazia mede ZERO de
  // altura com ou sem a cura — e mesmo assim cobra o `gap` da coluna e a
  // própria margem. Quem paga o pixel é o PAI, e é ele que a régua mede; assim
  // ela continua certa se alguém trocar o mecanismo (`height:0`, `hidden`, um
  // `:has()` no pai), porque o que ela lê é o espaço.
  const cena = id => {
    const e = document.getElementById(id);
    if (!e) return {ausente: id};
    const linha = e.querySelector('.ressalva');
    return {
      altura_da_cena: e.offsetHeight,
      altura_da_linha: linha ? linha.offsetHeight : null,
      display: linha ? getComputedStyle(linha).display : null,
      texto: linha ? (linha.textContent || '').trim() : null,
      alvo: linha ? (linha.dataset.hefAlvo || '') : null,
    };
  };
  return {sem_linha: cena('cena-so-valor'), cheia: cena('cena-cheia'),
          nada: cena('cena-nada'), nua: cena('cena-nua'),
          travessao: cena('cena-travessao')};
})()
"""


@pytest.fixture(scope="module")
def medido(tmp_path_factory: pytest.TempPathFactory) -> dict:
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    from playwright.sync_api import sync_playwright

    arquivo = _pagina_de_prova(tmp_path_factory.mktemp("ressalva"))
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(
            executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = navegador.new_page(viewport={"width": 1180, "height": 900})
            pg.goto(arquivo.as_uri())
            saida = pg.evaluate(O_QUE_O_NAVEGADOR_DESENHA)
        finally:
            navegador.close()
    return dict(saida)


# ---------------------------------------------------------------------------
# 1. A PEÇA CHEGA
# ---------------------------------------------------------------------------
def test_a_peca_da_ressalva_entra_nas_dez_paginas_da_bancada() -> None:
    """As dez páginas carregam as duas metades — e é `monta()` quem as põe lá.

    SÓ AS ABAS: a bancada guarda três páginas avulsas (`mapa-do-controle`,
    `mapa-das-portas`, `calibrar-sensores`) que abrem por fora da janela e não
    passam por `monta()`. O filtro é o número no nome, como no
    `test_os_dez_geradores_rodam`.
    """
    paginas = sorted(onde.BANCADA.glob("[0-9][0-9]-*.html"))
    assert len(paginas) >= 10, (
        f"achei {len(paginas)} aba(s) em {onde.BANCADA} — uma lista curta "
        f"faria este caso passar quase vazio")
    faltando: list[str] = []
    for p in paginas:
        texto = p.read_text(encoding="utf-8")
        metades = [m for m in (".ressalva:empty", ".ressalva:has(.nada)")
                   if m not in texto]
        if metades:
            faltando.append(f"{p.name}: sem {', '.join(metades)}")
    assert not faltando, (
        "estas páginas da bancada não têm as duas metades da peça:\n  "
        + "\n  ".join(faltando)
        + "\nRODE os geradores: `monta.CSS_FOLHA` mudou e a bancada ficou para "
          "trás.")


def test_a_ressalva_vazia_manda_o_marcador_e_nunca_o_travessao() -> None:
    """Sem o marcador, o piloto pinta `—` e a linha vira ruído com cara de dado.

    Esta é a metade que o navegador não pode provar sozinho: a página parada
    não sabe o que o piloto vai escrever nela. Aqui a régua cobra o CONTRATO —
    quem não tem o que dizer manda o marcador, e o alvo é `html`, que é o único
    por onde um `<i>` chega como ELEMENTO em vez de virar texto na tela.
    """
    vazia = monta.ressalva("x")
    assert monta.NADA_A_DIZER in vazia, (
        f"a ressalva sem texto não manda o marcador:\n  {vazia}")
    assert "—" not in vazia, (
        f"a ressalva sem texto nasceu com um travessão dentro:\n  {vazia}")
    assert 'data-hef-alvo="html"' in vazia, (
        f"o alvo não é `html` — pelo alvo de texto o marcador chegaria à tela "
        f"escrito, letra por letra:\n  {vazia}")
    cheia = monta.ressalva("x", DIZ)
    assert DIZ in cheia and monta.NADA_A_DIZER not in cheia


def test_o_marcador_e_o_mesmo_das_duas_casas() -> None:
    """`monta.NADA_A_DIZER` e o da `a06_navegacao` não divergem calados.

    A DUPLICAÇÃO É DECLARADA, e não descuido: o marcador nasceu na
    `pacotes/a06_navegacao.py`, que é arquivo de OUTRA frente (a da aba 06, na
    Onda 2). A folha precisa dele para escrever a regra que o lê, e esta frente
    não pode editar aquele arquivo — a regra da casa é relatar, nunca editar.

    Enquanto as duas cópias existirem, esta régua é o que impede que uma mude
    sem a outra: no dia em que a frente da 06 apontar a dela para cá, este caso
    continua verde e vira redundante, que é o fim certo dele.
    """
    from pacotes import a06_navegacao

    assert monta.NADA_A_DIZER == a06_navegacao.NADA_A_DIZER, (
        f"o marcador divergiu: `monta` diz {monta.NADA_A_DIZER!r} e "
        f"`a06_navegacao` diz {a06_navegacao.NADA_A_DIZER!r}. A folha esconde "
        f"a linha por `.nada`; um marcador com outra classe deixa a linha "
        f"visível, com um elemento vazio dentro.")


def test_a_ressalva_sem_endereco_para_a_geracao() -> None:
    """Ausência de âncora PARA — senão a ressalva nasce congelada no desenho."""
    with pytest.raises(SystemExit):
        monta.ressalva("", DIZ)


# ---------------------------------------------------------------------------
# 2. O QUE O MOTOR DESENHA
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not CHROME.exists(),
                    reason="sem o Chrome do sistema — a régua não tem motor")
def test_com_ressalva_a_linha_ocupa_a_tela(medido: dict) -> None:
    """No estado estranho ela nasce, e diz o que quem chamou mandou dizer."""
    assert medido["cheia"]["altura_da_linha"] > 0, (
        f"a linha COM ressalva não ocupa altura: {medido['cheia']}")
    assert medido["cheia"]["altura_da_cena"] > medido["sem_linha"]["altura_da_cena"], (
        f"a cena com ressalva mede {medido['cheia']['altura_da_cena']}px e a "
        f"cena sem linha nenhuma mede {medido['sem_linha']['altura_da_cena']}px "
        f"— a linha não cresceu a tela, então ela não está lá.")
    assert medido["cheia"]["texto"] == DIZ, (
        f"a linha diz {medido['cheia']['texto']!r} e o texto passado foi "
        f"{DIZ!r} — a ressalva não atravessa de quem chama até a tela.")


@pytest.mark.skipif(not CHROME.exists(),
                    reason="sem o Chrome do sistema — a régua não tem motor")
def test_sem_ressalva_a_linha_nao_ocupa_nada(medido: dict) -> None:
    """No repouso ela custa ZERO pixel — as duas metades, medidas.

    A REFERÊNCIA É A CENA SEM LINHA NENHUMA, medida na mesma página: "não ocupa
    nada" quer dizer *idêntica à tela que nunca teve a linha*, e não um número
    escrito aqui.
    """
    sem_linha = medido["sem_linha"]["altura_da_cena"]
    assert sem_linha > 0, (
        "a cena de referência mede zero — a página não desenhou nada, e as "
        "comparações abaixo passariam por ausência")
    assert medido["nua"]["altura_da_cena"] == sem_linha, (
        f"a linha VAZIA de nascença cobra "
        f"{medido['nua']['altura_da_cena'] - sem_linha}px na cena — o "
        f"`:empty{{display:none}}` caiu, e toda aba que reservar a linha passa "
        f"a pagar o vão da coluna sem ter o que dizer.")
    assert medido["nada"]["altura_da_cena"] == sem_linha, (
        f"a linha com o marcador `.nada` cobra "
        f"{medido['nada']['altura_da_cena'] - sem_linha}px na cena — o "
        f"`:has(.nada){{display:none}}` caiu, e a linha que o piloto pinta a "
        f"cada tique volta a ocupar espaço.")


@pytest.mark.skipif(not CHROME.exists(),
                    reason="sem o Chrome do sistema — a régua não tem motor")
def test_o_travessao_solto_e_o_que_o_marcador_evita(medido: dict) -> None:
    """A cena que PROVA por que o marcador existe, e não é zelo.

    Uma `.ressalva` com o travessão que `escrever()` põe no lugar do vazio
    OCUPA a tela — é o `—` solto que a primeira foto da `06-navegacao` mostrou.
    Este caso mede o custo do caminho errado; os de cima medem que o caminho
    certo não o paga.
    """
    assert (medido["travessao"]["altura_da_cena"]
            > medido["sem_linha"]["altura_da_cena"]), (
        "um `—` solto numa ressalva não ocupou nada — se isto passar a ser "
        "verdade, o marcador `.nada` perdeu a razão de existir e esta peça "
        "precisa ser remedida, não remendada")
    assert medido["travessao"]["altura_da_linha"] > 0
