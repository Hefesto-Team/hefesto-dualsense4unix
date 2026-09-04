#!/usr/bin/env python3
"""A RÉGUA DA D-03: o botão que vai recusar já nasce CINZA, e diz por quê.

Decisão dela, 04/09/2026: *"Cinza antes, com a razão na dica."*

O QUE ESTAVA EM JOGO, e está medido nas dezesseis decisões: a janela antiga
apaga o botão e diz o motivo ANTES; a interface nova deixa clicar e responde
DEPOIS. Em repouso, a tela não distingue o botão que funciona do que vai
recusar — mudo sem endereço, microfone no cabo, "a luz não acende" com o
controle no cabo.

E A DECISÃO DO PO POR CIMA, sobre a aba 09: *"Apagado e ainda assim
responde."* Logo o apagado é **visual**, e nunca `disabled`: `disabled` mata o
clique, e o clique é o único caminho de quem navega pelo controle até a razão.
Por isso esta régua cobra as duas metades ao mesmo tempo — **cinza** e
**clicável** —, que é o par que nenhuma das duas sozinha prova.

**ELA LÊ, NÃO DIGITA.** Nenhuma cor está escrita aqui. A régua monta uma página
pelo `monta.monta()` — a mesma função que faz as dez —, abre no Chrome, e
pergunta ao motor o que ele DESENHA. A comparação que importa é entre dois
elementos da MESMA página: o `.btn.apagado` e o `.seg button:disabled` que a
folha já tinha desde 31/08. Se a gramática do apagado mudar, as duas mudam
juntas e a régua continua certa; se alguém inventar uma segunda cara de
apagado, ela reprova. Uma cor digitada aqui mediria este arquivo, não a tela —
é a família de defeito que esta casa pagou onze vezes em 26/08.

A MORDIDA: comente o bloco `.btn.apagado{…}` do `monta.CSS_FOLHA` e rode. Caem
três casos, e o primeiro diz tudo — *"o botão apagado tem a MESMA cor de texto
do clicável (rgb(200, 204, 218))"*: a régua vê o botão travado com a mesma cara
do clicável, que é o defeito que a D-03 existe para curar. Comente as três
regras do `?` e cai o quarto.
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

#: O MESMO MOTOR DAS OUTRAS RÉGUAS DE TELA desta casa
#: (`test_a_aba_controles_reusa_o_motor.py`), e ele roda headless: nenhuma
#: janela nasce na tela dela.
CHROME = pathlib.Path("/usr/bin/google-chrome")

#: A razão de prova. Ela NÃO é texto de tela — texto de tela é dela, e o que
#: cada aba vai dizer sai do produto, nunca daqui. Este é só um valor com forma
#: reconhecível, para a régua provar que ele ATRAVESSA da chamada até a dica.
RAZAO = "razão de prova: este botão vai recusar"


def _pagina_de_prova(destino: pathlib.Path) -> pathlib.Path:
    """Uma página montada pelo `monta()`, com as peças da folha em uso.

    ELA NASCE NUM DIRETÓRIO TEMPORÁRIO, pelo `HEFESTO_BANCADA` — o desvio que
    o `onde.py` documenta. A régua não toca a bancada dela: uma régua que muda
    o que mede não é régua.
    """
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


# ---------------------------------------------------------------------------
# 1. A PEÇA CHEGA — sem isto, tudo abaixo passaria por ausência
# ---------------------------------------------------------------------------
def test_a_folha_entra_nas_dez_paginas_da_bancada() -> None:
    """As dez páginas carregam a folha — e é `monta()` quem a põe lá.

    ELE É O DEGRAU QUE PEGA O GERADOR NUNCA RODADO: mudar o `CSS_FOLHA` sem
    regerar deixa a bancada para trás, e a peça só existe no Python. É a mesma
    família do `test_os_dez_geradores_rodam`, apontada para esta peça.

    SÓ AS ABAS, e o filtro é o número no nome — o mesmo que aquele teste e o
    `test_nenhuma_pagina_publicada_carrega_marcador_de_lint` já usam. A bancada
    guarda TRÊS páginas avulsas (`mapa-do-controle`, `mapa-das-portas`,
    `calibrar-sensores`) que não passam por `monta()`: elas abrem por fora da
    janela e não têm esqueleto de aba. `onde.paginas()` devolve as treze, e a
    primeira redação desta régua reprovou sobre as três — corretamente, do
    ponto de vista dela, e sobre um alvo que não é o desta peça.
    """
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


def test_o_botao_cinza_nao_emite_disabled_no_html() -> None:
    """A leitura do texto emitido, antes de qualquer navegador.

    `disabled` no HTML é o defeito de uma palavra: ele apaga o botão E mata o
    clique, e o recado da D-03 morre junto. Este caso o pega sem motor nenhum.
    """
    marcado = monta.botao_cinza("Travado", "x", razao=RAZAO)
    assert "disabled" not in marcado, (
        f"`botao_cinza` emitiu `disabled` — o botão apagado tem de RESPONDER "
        f"ao clique (PO, 04/09, aba 09):\n  {marcado}")
    assert 'data-hef-alvo="classe"' in marcado and 'data-hef-classe="apagado"' in marcado, (
        f"o botão perdeu o alvo do piloto — sem ele o cinza fica congelado no "
        f"desenho e nunca acende no produto:\n  {marcado}")
    assert marcado.count('data-campo="x"') == 2, (
        f"o botão e a dica têm de levar o MESMO `data-campo`: é o que impede a "
        f"tela de mostrar cinza sem razão, ou razão sem cinza.\n  {marcado}")


def test_sem_razao_o_botao_nao_fica_cinza() -> None:
    """Cinza sem razão é o defeito que a D-03 nasceu para curar.

    A LEITURA É DO ATRIBUTO `class`, e não da palavra solta no HTML: o
    `data-hef-classe="apagado"` está em TODO botão emitido — é o alvo que o
    piloto usa para acender a classe. Procurar `"apagado"` no texto inteiro dá
    verde sobre os dois, que foi como esta régua nasceu errada.
    """
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


# ---------------------------------------------------------------------------
# 2. O QUE O MOTOR DESENHA
# ---------------------------------------------------------------------------
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
    """A cara do apagado é a que a página JÁ TINHA — não uma segunda.

    A `.seg button:disabled` existe desde 31/08 e foi ela que curou o "travado
    com cara de clicável" nos seletores. Reusá-la é a instrução da sprint, e
    esta é a única forma de provar o reuso sem digitar uma cor: perguntar ao
    motor a cor dos DOIS e exigir que sejam a mesma.
    """
    assert medido["apagado"]["cor"] == medido["seg_disabled"]["cor"], (
        f"o `.btn.apagado` pinta {medido['apagado']['cor']} e o "
        f"`.seg button:disabled` pinta {medido['seg_disabled']['cor']} — são "
        f"duas caras de apagado na mesma janela, que é a doença que esta casa "
        f"persegue.")
    assert medido["apagado"]["borda"] == medido["seg_disabled"]["borda"], (
        f"borda: {medido['apagado']['borda']} contra "
        f"{medido['seg_disabled']['borda']}")
    # A CONFERÊNCIA DA REFERÊNCIA, e ela é pela BORDA. Medido nesta bancada:
    # `.seg button` já nasce em `--texto-mudo`, e o `:disabled` de 31/08 muda
    # a BORDA e o cursor, não a cor do texto — os dois pintam
    # `rgb(154, 158, 184)`. A primeira redação deste caso comparava a cor e
    # reprovava sobre a folha CERTA. Quem separa o livre do travado no seletor
    # é a borda; é ela que tem de diferir para a igualdade acima valer alguma
    # coisa.
    assert medido["seg_livre"]["borda"] != medido["seg_disabled"]["borda"], (
        "o seletor livre e o travado desenham a MESMA borda — a gramática de "
        "referência caiu, e a comparação acima passou a medir dois iguais por "
        "acaso")


@pytest.mark.skipif(not CHROME.exists(),
                    reason="sem o Chrome do sistema — a régua não tem motor")
def test_o_tom_do_botao_nao_vence_o_cinza(medido: dict) -> None:
    """`.btn.vermelho.apagado` fica CINZA, e não vermelho.

    As duas classes têm a mesma especificidade; quem decide é a ordem de fonte,
    e a folha entra depois do esqueleto. Um dia em que a injeção mudar de lugar
    isto reprova — e reprova ANTES de a tela mostrar um "Parar o serviço"
    vermelho vivo que não faz nada.
    """
    assert medido["apagado_com_tom"]["cor"] == medido["apagado"]["cor"], (
        f"o `.btn.vermelho.apagado` pinta {medido['apagado_com_tom']['cor']} e "
        f"o apagado puro pinta {medido['apagado']['cor']} — o tom venceu o "
        f"cinza, e o botão travado grita a cor da ação que ele vai recusar.")


@pytest.mark.skipif(not CHROME.exists(),
                    reason="sem o Chrome do sistema — a régua não tem motor")
def test_apagado_e_ainda_assim_responde(medido: dict) -> None:
    """PO, 04/09, aba 09: *"Apagado e ainda assim responde."*

    `HTMLElement.click()` num botão `disabled` não dispara ouvinte nenhum. O
    contador vindo em 1 é a prova de que o cinza é TINTA, e de que quem chega
    pelo controle ainda alcança a razão.
    """
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
    """O `?` acompanha o cinza, e a razão dentro dele veio de quem chamou.

    Na aba 08 o motivo é do PRODUTO, nunca do desenho — a frase congelada já
    mentiu ali ("está no cabo" com o controle no rádio). Por isso a dica leva
    `data-campo` e o alvo `html`: quem a preenche no produto é o pacote.
    """
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
