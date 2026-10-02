#!/usr/bin/env python3
"""A RÉGUA DA D-03: o botão que vai recusar já nasce CINZA, e diz por quê."""
from __future__ import annotations

import re
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

RAZAO = "razão de prova: este botão vai recusar"


def _pagina_de_prova(destino: pathlib.Path) -> pathlib.Path:
    """Uma página montada pelo `monta()`, com as peças da folha em uso."""
    import os

    anterior = os.environ.get("HEFESTO_BANCADA")
    os.environ["HEFESTO_BANCADA"] = str(destino)
    try:
        miolo = f"""    <div class="quadro"><div class="quadro-corpo">
      <div class="acoes">
        {monta.botao_cinza("Livre", "prova-livre")}
        {monta.botao_cinza("Travado", "prova-travado", razao=RAZAO)}
        {monta.botao_cinza("Parar", "prova-tom", tom="vermelho", razao=RAZAO)}
      </div>
      <div class="seg">
        <button id="seg-livre">Seletor livre</button>
        <button id="seg-travado" disabled>Seletor travado</button>
      </div>
    </div></div>"""
        monta.monta("99-prova-da-folha", "Prova da folha", miolo)
    finally:
        if anterior is None:
            os.environ.pop("HEFESTO_BANCADA", None)
        else:
            os.environ["HEFESTO_BANCADA"] = anterior
    return destino / "99-prova-da-folha.html"


O_QUE_O_NAVEGADOR_DESENHA = r"""
(() => {
  const cs = s => {
    const e = document.querySelector(s);
    if (!e) return {ausente: s};
    const c = getComputedStyle(e);
    return {cor: c.color, borda: c.borderTopColor, cursor: c.cursor,
            display: c.display, altura: e.offsetHeight};
  };
  const travado = document.querySelector('[data-campo="prova-travado"]');
  const livre = document.querySelector('[data-campo="prova-livre"]');
  // O CLIQUE, E ELE É A METADE QUE `disabled` MATARIA. `HTMLElement.click()`
  // num botão `disabled` não dispara ouvinte nenhum — então este contador
  // separa "cinza" de "morto" sem depender de nada além do motor.
  let recebeu = 0;
  travado.addEventListener('click', () => { recebeu += 1; });
  travado.click();
  // A DICA DESTE BOTÃO, e não a primeira da página: o `?` é o irmão IMEDIATO
  // do botão, e é essa vizinhança que a folha usa para escondê-lo. Buscar por
  // classe no documento devolveria a dica do botão LIVRE, que vem antes.
  const dica = travado.nextElementSibling
    ? travado.nextElementSibling.querySelector('.dica') : null;
  return {
    normal: cs('[data-campo="prova-livre"]'),
    apagado: cs('[data-campo="prova-travado"]'),
    apagado_com_tom: cs('[data-campo="prova-tom"]'),
    seg_livre: cs('#seg-livre'),
    seg_disabled: cs('#seg-travado'),
    porque_do_travado: cs('[data-campo="prova-travado"] + .ajuda.porque'),
    porque_do_livre: cs('[data-campo="prova-livre"] + .ajuda.porque'),
    tem_atributo_disabled: travado.hasAttribute('disabled'),
    disabled_de_verdade: travado.disabled,
    livre_tem_a_classe: livre.classList.contains('apagado'),
    travado_tem_a_classe: travado.classList.contains('apagado'),
    clique_recebido: recebeu,
    razao_na_dica: dica ? (dica.textContent || '').trim() : null,
    alvo_do_botao: travado.dataset.hefAlvo,
    classe_do_alvo: travado.dataset.hefClasse,
  };
})()
"""


@pytest.fixture(scope="module")
def medido(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """O que o Chrome desenha na página de prova — uma abertura para todos."""
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    from playwright.sync_api import sync_playwright

    arquivo = _pagina_de_prova(tmp_path_factory.mktemp("folha"))
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


def test_a_folha_entra_nas_dez_paginas_da_bancada() -> None:
    """As dez páginas carregam a folha — e é `monta()` quem a põe lá."""
    paginas = sorted(onde.BANCADA.glob("[0-9][0-9]-*.html"))
    assert len(paginas) >= 10, (
        f"achei {len(paginas)} aba(s) em {onde.BANCADA} — as dez abas têm "
        f"uma cada, e uma lista curta faria este caso passar quase vazio")
    sem_a_peca = [p.name for p in paginas
                  if ".btn.apagado" not in p.read_text(encoding="utf-8")]
    assert not sem_a_peca, (
        "estas páginas da bancada não têm a peça do botão cinza:\n  "
        + "\n  ".join(sem_a_peca)
        + "\nRODE os geradores: `monta.CSS_FOLHA` mudou e a bancada ficou para "
          "trás.")


_DISABLED_BOOLEANO = re.compile(r'(?<![-\w])disabled(?=[\s=>])')


def test_o_botao_cinza_nao_emite_disabled_no_html() -> None:
    """A leitura do texto emitido, antes de qualquer navegador."""
    marcado = monta.botao_cinza("Travado", "x", razao=RAZAO)
    assert not _DISABLED_BOOLEANO.search(marcado), (
        f"`botao_cinza` emitiu o atributo booleano `disabled` — o botão "
        f"apagado tem de RESPONDER ao clique (PO, 04/09, aba 09):\n  {marcado}")
    assert 'data-hef-atributo="aria-disabled"' in marcado, (
        f"o botão perdeu o `aria-disabled`. Ele NÃO é o `disabled` proibido: é "
        f"a mesma verdade da classe, dita para quem não enxerga a cor, e o "
        f"alvo `classe` do piloto o reescreve a cada tique — por isso ele não "
        f"congela no desenho:\n  {marcado}")
    assert 'data-hef-alvo="classe"' in marcado and 'data-hef-classe="apagado"' in marcado, (
        f"o botão perdeu o alvo do piloto — sem ele o cinza fica congelado no "
        f"desenho e nunca acende no produto:\n  {marcado}")
    assert marcado.count('data-campo="x"') == 2, (
        f"o botão e a dica têm de levar o MESMO `data-campo`: é o que impede a "
        f"tela de mostrar cinza sem razão, ou razão sem cinza.\n  {marcado}")


def test_sem_razao_o_botao_nao_fica_cinza() -> None:
    """Cinza sem razão é o defeito que a D-03 nasceu para curar."""
    livre = monta.botao_cinza("Livre", "x")
    travado = monta.botao_cinza("Travado", "x", razao=RAZAO)
    assert 'class="btn"' in livre, (
        f"o botão sem razão não nasceu limpo:\n  {livre}")
    assert 'class="btn apagado"' in travado, (
        f"o botão com razão não nasceu cinza:\n  {travado}")
    assert 'class="btn vermelho apagado"' in monta.botao_cinza(
        "Parar", "x", tom="vermelho", razao=RAZAO)


def test_o_botao_sem_endereco_para_a_geracao() -> None:
    """Ausência de âncora PARA, e não segue calada — regra desta casa."""
    with pytest.raises(SystemExit):
        monta.botao_cinza("Travado", "", razao=RAZAO)


@pytest.mark.skipif(not CHROME.exists(),
                    reason="sem o Chrome do sistema — a régua não tem motor")
def test_o_cinza_difere_do_clicavel_na_tela(medido: dict) -> None:
    """Em repouso, a tela distingue o botão que funciona do que vai recusar."""
    assert medido["apagado"]["cor"] != medido["normal"]["cor"], (
        f"o botão apagado tem a MESMA cor de texto do clicável "
        f"({medido['apagado']['cor']}) — a tela em repouso continua sem "
        f"distinguir os dois, que é a queixa inteira da D-03.")
    assert medido["apagado"]["borda"] != medido["normal"]["borda"], (
        f"a borda do apagado não mudou ({medido['apagado']['borda']})")
    assert medido["apagado"]["cursor"] == "not-allowed", (
        f"o cursor do apagado é {medido['apagado']['cursor']!r}")


@pytest.mark.skipif(not CHROME.exists(),
                    reason="sem o Chrome do sistema — a régua não tem motor")
def test_o_cinza_e_a_mesma_gramatica_do_seletor(medido: dict) -> None:
    """A cara do apagado é a que a página JÁ TINHA — não uma segunda."""
    assert medido["apagado"]["cor"] == medido["seg_disabled"]["cor"], (
        f"o `.btn.apagado` pinta {medido['apagado']['cor']} e o "
        f"`.seg button:disabled` pinta {medido['seg_disabled']['cor']} — são "
        f"duas caras de apagado na mesma janela, que é a doença que esta casa "
        f"persegue.")
    assert medido["apagado"]["borda"] == medido["seg_disabled"]["borda"], (
        f"borda: {medido['apagado']['borda']} contra "
        f"{medido['seg_disabled']['borda']}")
    assert medido["seg_livre"]["borda"] != medido["seg_disabled"]["borda"], (
        "o seletor livre e o travado desenham a MESMA borda — a gramática de "
        "referência caiu, e a comparação acima passou a medir dois iguais por "
        "acaso")


@pytest.mark.skipif(not CHROME.exists(),
                    reason="sem o Chrome do sistema — a régua não tem motor")
def test_o_tom_do_botao_nao_vence_o_cinza(medido: dict) -> None:
    """`.btn.vermelho.apagado` fica CINZA, e não vermelho."""
    assert medido["apagado_com_tom"]["cor"] == medido["apagado"]["cor"], (
        f"o `.btn.vermelho.apagado` pinta {medido['apagado_com_tom']['cor']} e "
        f"o apagado puro pinta {medido['apagado']['cor']} — o tom venceu o "
        f"cinza, e o botão travado grita a cor da ação que ele vai recusar.")


@pytest.mark.skipif(not CHROME.exists(),
                    reason="sem o Chrome do sistema — a régua não tem motor")
def test_apagado_e_ainda_assim_responde(medido: dict) -> None:
    """PO, 04/09, aba 09: *"Apagado e ainda assim responde."*"""
    assert medido["travado_tem_a_classe"] is True
    assert medido["livre_tem_a_classe"] is False
    assert medido["tem_atributo_disabled"] is False
    assert medido["disabled_de_verdade"] is False
    assert medido["clique_recebido"] == 1, (
        f"o botão apagado NÃO recebeu o clique ({medido['clique_recebido']}) — "
        f"ele virou `disabled` e levou o recado junto, que é exatamente o que a "
        f"decisão do PO recusou.")


@pytest.mark.skipif(not CHROME.exists(),
                    reason="sem o Chrome do sistema — a régua não tem motor")
def test_o_ponto_de_interrogacao_so_aparece_quando_ha_razao(medido: dict) -> None:
    """O `?` acompanha o cinza, e a razão dentro dele veio de quem chamou."""
    assert medido["porque_do_livre"]["display"] == "none", (
        f"o `?` apareceu ao lado de um botão que NÃO está cinza "
        f"({medido['porque_do_livre']}) — um `?` sem nada a explicar é ruído "
        f"com cara de dado.")
    assert medido["porque_do_travado"]["display"] != "none", (
        "o `?` sumiu ao lado do botão cinza — o botão ficaria apagado sem "
        "dizer por quê, que é metade da D-03 perdida.")
    assert medido["porque_do_travado"]["altura"] > 0
    assert medido["razao_na_dica"] == RAZAO, (
        f"a dica diz {medido['razao_na_dica']!r} e a razão passada foi "
        f"{RAZAO!r} — o texto não atravessa de quem chama até a tela.")
