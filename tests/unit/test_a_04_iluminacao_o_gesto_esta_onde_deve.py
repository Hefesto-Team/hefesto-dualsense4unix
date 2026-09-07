#!/usr/bin/env python3
"""A RÉGUA DA 04-ILUMINAÇÃO: o gesto some no lugar vazio **e aparece no cheio**.

**ESTA RÉGUA NASCEU DE UM ACHADO DE CONFERÊNCIA, em 07/09/2026, e o achado é que
a cobertura só existia NUMA DIREÇÃO.** O conferente pegou a folha desta aba,
manteve intacta a regra que esconde os botões no lugar sem dono
(``[data-conectado="nao"] .cel-acoes .btn{display:none}``) e acrescentou UMA
linha por cima::

    .luz-grade .ctrl .cel-acoes .btn{display:none}

`Automático` e `Desligar` sumiram das DUAS colunas CONECTADAS — de 220x34 para
0x0, medido em Chrome de verdade. **São os botões que ela usa.** A suíte inteira
foi rodada antes e depois: 13 falhas antes, 13 depois, lista idêntica.
**NENHUMA RÉGUA REPROVOU.**

REPRODUZIDO NESTA BANCADA antes de escrever a cura, com a mesma linha por cima::

    p1 (cheio)  auto 0x0 · apagar 0x0     ← e ela precisa dos dois
    p2 (cheio)  auto 0x0 · apagar 0x0     ← idem
    p3 (vazio)  auto 0x0 · apagar 0x0
    p4 (vazio)  auto 0x0 · apagar 0x0

**POR QUE NADA PEGAVA, e são três buracos que se somam:**

1. **A COBERTURA ERA DE UM LADO SÓ.** As réguas desta aba cobravam o
   ``display:none`` no lugar VAZIO. Uma cura que esconde DEMAIS passa por todas
   elas, porque esconder demais satisfaz "está escondido no vazio".
2. **A AUTO-CHECAGEM DA ABA NÃO RODA NA INTEGRAÇÃO.** O ``aba04._conferir`` tem
   quatorze seções, e a §4 cobre exatamente estes botões — mas ele só é chamado
   dentro de ``if __name__ == "__main__"`` (``aba04.py``, no rodapé). Roda quando
   alguém digita ``python aba04.py``; nunca no ``pytest``, nunca no
   ``portoes.sh``. *Uma régua que espera alguém lembrar de a chamar não protege
   ninguém.*
3. **A REDE DA CASA NÃO ALCANÇA ESTA ABA**, e isto é estrutural — ver
   ``test_a_rede_da_casa_nao_cobre_esta_aba``, no fim deste arquivo.

**ELA LÊ, NÃO DIGITA.** Nenhum seletor de CSS está afirmado aqui. A régua gera a
página pelo gerador de verdade, abre no Chrome e pergunta ao MOTOR o que ele
desenha e quem recebe o clique (``elementFromPoint``). Uma regra digitada aqui
mediria este arquivo, e não a tela — é a família de defeito que esta casa pagou
onze vezes em 26/08.

**OS DOIS SENTIDOS, e é o par que nenhuma metade sozinha prova:**

1. **ESCONDIDO NO VAZIO** — ``data-conectado="nao"``: nenhum ``[data-gesto]``
   com caixa maior que zero recebendo clique. A decisão é dela, 31/08/2026:
   *um lugar sem aparelho não oferece gesto nenhum*.
2. **VISÍVEL E CLICÁVEL NO CHEIO** — ``data-conectado="sim"``: TODOS com caixa
   maior que zero, TODOS recebendo o clique no próprio centro, TODOS com
   ``pointer-events`` útil. **É esta a metade que faltava**, e é a que teria
   pego a mordida do conferente.

E OS DOIS PASSOS DO PILOTO, porque o estado inicial pode ser sorte e não regra:
a régua faz o que ``hefesto_vivo`` faz nos passos ``1c`` e ``1b`` — vira a marca
``data-conectado`` **sem recarregar a página** — e cobra que os gestos do P3
apareçam e os do P1 sumam no mesmo tique. É o estado da mesa DELA, que está com
os quatro DualSense agora. O piloto vira marca e escreve campo; ele não
materializa widget.

**A EXCEÇÃO DECLARADA É A CAIXA DO HEXADECIMAL**, e ela é de propósito: o
``<span class="hex reenvia">`` É o travessão da célula no lugar vazio — o mesmo
elemento que mostra ``#0000FF`` na coluna viva. Ele não pode SUMIR como a guia
some; o que se apaga nele é o CLIQUE. A régua o cobra pelo
``pointer-events``, e não pela caixa. Ver ``GESTOS_QUE_FICAM_A_VISTA``.

A MORDIDA, e foi feita antes de o arquivo entrar:

  (i)   a do conferente — acrescente ``.luz-grade .ctrl .cel-acoes .btn{
        display:none}`` ao ``CSS`` da ``aba04.py``:
        ``test_o_lugar_cheio_oferece_todos_os_gestos`` reprova nomeando `auto`
        e `apagar` nas duas colunas cheias. **Era esta a que não existia.**
  (ii)  a simétrica — troque a chave ``[data-conectado="nao"]`` daquele mesmo
        bloco por ``.off``: ``test_o_lugar_vazio_nao_oferece_gesto`` reprova,
        porque a coluna que NASCE vazia carrega ``.vazia`` e nunca ganha
        ``.off``.
  (iii) a do piloto — troque a chave por ``.vazia``:
        ``test_o_passo_1c_do_piloto_devolve_o_gesto_sem_recarregar`` reprova, e
        só ela: o lugar que GANHA controle ficaria sem guia de cores para
        sempre, que é o defeito que a leva de 07/09 acabou de fechar.
"""
from __future__ import annotations

import os
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

#: O MESMO MOTOR DAS OUTRAS RÉGUAS DE TELA desta casa, e ele roda headless:
#: nenhuma janela nasce na tela dela. TELA-DELA-01 continua honrada.
CHROME = pathlib.Path("/usr/bin/google-chrome")

PAGINA = "04-iluminacao.html"

#: OS GESTOS QUE CONTINUAM À VISTA NO LUGAR VAZIO, e cada um com a razão.
#:
#: `reenviar` — a caixa `#RRGGBB` É o travessão daquela célula (`aba04.coluna`,
#: o `<span class="hex reenvia">`). Some ela e a coluna sem dono fica com a
#: linha "Cor" em branco, quando as outras seis mostram "—". O que a folha
#: apaga nela é o `pointer-events` e a borda de botão, não o elemento — então a
#: régua a cobra pelo ALCANCE, que é o que importa: ela não recebe o clique.
GESTOS_QUE_FICAM_A_VISTA = frozenset({"reenviar"})

#: A CÉLULA QUE NÃO PODE TER GESTO NENHUM, nem cheia nem vazia — 07/09/2026,
#: ordem dela: *"só olhar a linha de cima da seleção de player e replicar o que
#: tem lá."* As cinco lâmpadas são ESPELHO do número; quem escolhe o número é a
#: linha `Jogador`, uma célula acima. Ver `test_a_celula_de_leds_nao_tem_gesto`.
CELULA_DE_LEDS = "cel-leds"


def _gerar(destino: pathlib.Path) -> pathlib.Path:
    """A página da aba 04 montada pelo gerador de verdade, num lar de mentira.

    O DESVIO É O `HEFESTO_BANCADA` que o `onde.py:90` documenta. A régua não
    toca a bancada dela: uma régua que muda o que mede não é régua.
    """
    anterior = os.environ.get("HEFESTO_BANCADA")
    os.environ["HEFESTO_BANCADA"] = str(destino)
    try:
        import aba04
        import onde
        from monta import monta

        monta("04-iluminacao", "Iluminação", aba04.MIOLO,
              aba04.CSS + aba04.CSS_DAS_MEDIDAS, legenda=aba04.LEGENDA)
        return onde.pagina(PAGINA)
    finally:
        if anterior is None:
            os.environ.pop("HEFESTO_BANCADA", None)
        else:
            os.environ["HEFESTO_BANCADA"] = anterior


#: O QUE SE PERGUNTA AO MOTOR, e são quatro coisas por gesto: a CAIXA (largura e
#: altura maiores que zero), quem RECEBE o clique naquele ponto
#: (`elementFromPoint` — é ele que separa "está desenhado" de "está alcançável",
#: e é o que uma leitura de `display` sozinha não sabe responder), o
#: `pointer-events` e a `visibility`. Um gesto só conta como OFERECIDO se as
#: quatro casarem.
O_QUE_O_NAVEGADOR_DESENHA = r"""
(() => {
  const medir = () => {
    const saida = {};
    for (const bloco of document.querySelectorAll('.luz-grade [data-controle]')) {
      const quem = bloco.dataset.controle || '';
      if (!/^p[0-9]+$/.test(quem)) continue;
      const gestos = [];
      for (const el of bloco.querySelectorAll('[data-gesto]')) {
        const r = el.getBoundingClientRect();
        const cs = getComputedStyle(el);
        const caixa = r.width > 0 && r.height > 0;
        let pega = false;
        if (caixa) {
          const em = document.elementFromPoint(r.x + r.width / 2,
                                               r.y + r.height / 2);
          pega = !!em && (em === el || el.contains(em));
        }
        const cel = el.closest('[class^="cel-"]');
        gestos.push({
          gesto: el.dataset.gesto,
          celula: cel ? cel.className : '',
          rotulo: (el.textContent || '').trim().slice(0, 30),
          largura: +r.width.toFixed(1), altura: +r.height.toFixed(1),
          caixa: caixa,
          oferecido: caixa && pega && cs.visibility !== 'hidden'
                     && cs.pointerEvents !== 'none',
        });
      }
      saida[quem] = {conectado: bloco.dataset.conectado || '', gestos: gestos};
    }
    return saida;
  };
  // O PASSO 1c DO PILOTO, letra por letra (`hefesto_vivo`): a marca vira e a
  // classe sai. NENHUM nó é criado — é justamente o ponto.
  const encher = (quem) => {
    for (const el of document.querySelectorAll('[data-controle="' + quem + '"]')) {
      el.dataset.conectado = 'sim';
      el.classList.remove('off');
    }
  };
  // E O PASSO 1b, que é o simétrico.
  const esvaziar = (quem) => {
    for (const el of document.querySelectorAll('[data-controle="' + quem + '"]')) {
      el.dataset.conectado = 'nao';  // (noqa-acento) o valor, não a palavra
      el.classList.add('off');
    }
  };
  const comoNasce = medir();
  encher('p3'); encher('p4');
  const depoisDo1c = medir();
  esvaziar('p1');
  const depoisDo1b = medir();
  return {como_nasce: comoNasce, depois_do_1c: depoisDo1c,
          depois_do_1b: depoisDo1b};
})()
"""


@pytest.fixture(scope="module")
def medido(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """O que o Chrome desenha, nos três estados — uma abertura para todos."""
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    playwright = pytest.importorskip("playwright.sync_api")

    arquivo = _gerar(tmp_path_factory.mktemp("iluminacao"))
    with playwright.sync_playwright() as pw:
        navegador = pw.chromium.launch(
            executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = navegador.new_page(viewport={"width": 1280, "height": 900})
            pg.goto(arquivo.as_uri())
            pg.wait_for_load_state("networkidle")
            saida = pg.evaluate(O_QUE_O_NAVEGADOR_DESENHA)
        finally:
            navegador.close()
    return dict(saida)


def _lugares(estado: dict, marca: str) -> dict:
    """Os lugares de um estado cuja marca de conexão é `marca`."""
    return {q: d for q, d in estado.items() if d["conectado"] == marca}


def _oferecidos(dado: dict) -> list[dict]:
    """Os gestos daquele lugar que o motor entrega ao clique."""
    return [g for g in dado["gestos"] if g["oferecido"]]


def _acusar(quem: str, g: dict, oque: str) -> str:
    return (f'{quem} · gesto `{g["gesto"]}` ("{g["rotulo"]}") — '
            f'caixa {g["largura"]}x{g["altura"]}, oferecido={g["oferecido"]}: '
            f"{oque}")


# ---------------------------------------------------------------------------
# 0. A MEDIDA CHEGOU — sem isto tudo abaixo passaria por AUSÊNCIA
# ---------------------------------------------------------------------------
def test_a_pagina_tem_os_quatro_lugares_e_gestos_em_todos(medido: dict) -> None:
    """Quatro lugares, e nenhum deles sem `data-gesto` no HTML.

    ESTA É A PRIMEIRA RÉGUA DE PROPÓSITO. Sem ela, uma página que deixasse de
    emitir a grade inteira faria todas as asserções seguintes passarem por não
    ter o que medir — que é a forma mais barata de verde falso, e a que esta
    casa já pagou seis vezes.

    E OS QUATRO TÊM GESTO no HTML desde 07/09/2026: os widgets nascem nos quatro
    lugares e quem cumpre a decisão dela é a FOLHA, não a ausência. Um lugar
    vazio SEM `data-gesto` no HTML voltaria a ficar mudo quando o controle
    chegasse — o piloto não materializa widget.
    """
    nasce = medido["como_nasce"]
    assert sorted(nasce) == ["p1", "p2", "p3", "p4"], (
        f"a grade não tem os quatro lugares endereçados: {sorted(nasce)}")
    assert sorted(_lugares(nasce, "sim")) == ["p1", "p2"], (
        f"a mesa desta bancada tem dois conectados: {nasce}")
    assert sorted(_lugares(nasce, "nao")) == ["p3", "p4"], (  # (noqa-acento) valor
        f"a mesa desta bancada tem dois lugares vazios: {nasce}")
    for quem, dado in nasce.items():
        assert dado["gestos"], (
            f"{quem} não tem um `data-gesto` sequer no HTML — o lugar que "
            f"ganha um controle ficaria mudo, porque o piloto vira marca e "
            f"escreve campo, mas não cria widget")


# ---------------------------------------------------------------------------
# 1. O LUGAR VAZIO NÃO OFERECE — a decisão dela de 31/08/2026
# ---------------------------------------------------------------------------
def test_o_lugar_vazio_nao_oferece_gesto(medido: dict) -> None:
    """*Um lugar sem aparelho não oferece gesto nenhum.*

    Os dez endereços desta coluna levantam `o clique não disse em qual
    controle`, e a tela só recebe `RuntimeError` — então um botão vivo ali ou
    não faz nada e mente, ou engole o toque.

    A MORDIDA (ii): troque a chave `[data-conectado="nao"]` do bloco que esconde
    a guia, o trilho e os dois botões por `.off`, e esta régua reprova — a
    coluna que NASCE vazia carrega `.vazia` e nunca ganha `.off`.
    """
    for quem, dado in _lugares(medido["como_nasce"], "nao").items():  # (noqa-acento) valor
        for g in _oferecidos(dado):
            assert g["gesto"] in GESTOS_QUE_FICAM_A_VISTA, _acusar(
                quem, g, "um lugar SEM aparelho está oferecendo este clique")


def test_a_caixa_do_hexadecimal_fica_a_vista_e_nao_recebe_clique(
        medido: dict) -> None:
    """A exceção declarada, e ela é cobrada nas duas metades.

    O `<span class="hex reenvia">` É o travessão da célula "Cor" no lugar sem
    dono — o mesmo elemento que mostra `#0000FF` na coluna viva. Ele FICA à
    vista (senão a linha nasce em branco, quando as outras seis mostram "—") e
    NÃO recebe o clique.

    A MORDIDA: tire o `pointer-events:none` da regra
    `[data-conectado="nao"] .cel-cor .hex.reenvia` e a segunda asserção reprova.
    """
    for quem, dado in _lugares(medido["como_nasce"], "nao").items():  # (noqa-acento) valor
        caixas = [g for g in dado["gestos"] if g["gesto"] == "reenviar"]
        assert caixas, f"{quem} perdeu a caixa do hexadecimal"
        for g in caixas:
            assert g["caixa"], _acusar(
                quem, g, "a caixa do hexadecimal SUMIU do lugar vazio — ela é "
                         "o travessão daquela célula, e sem ela a linha `Cor` "
                         "nasce em branco")
            assert not g["oferecido"], _acusar(
                quem, g, "a caixa do hexadecimal aceita clique num lugar sem "
                         "controle — o gesto levantaria `o clique não disse em "
                         "qual controle`")


# ---------------------------------------------------------------------------
# 2. O LUGAR CHEIO OFERECE — **a metade que faltava**
# ---------------------------------------------------------------------------
def test_o_lugar_cheio_oferece_todos_os_gestos(medido: dict) -> None:
    """TODO `data-gesto` de uma coluna conectada tem caixa e recebe o clique.

    **ESTA É A RÉGUA QUE O CONFERENTE DERRUBOU A CASA POR NÃO TER**, em
    07/09/2026. A cobertura desta aba só olhava o `display:none` no lugar VAZIO,
    e uma cura que esconde DEMAIS satisfaz essa metade inteira: os botões
    `Automático` e `Desligar` foram a 0x0 nas DUAS colunas conectadas e a suíte
    inteira não mudou uma linha — 13 falhas antes, 13 depois.

    ELA NÃO NOMEIA GESTO NENHUM de propósito. Cobrar uma lista escrita aqui
    mediria a minha memória do que a aba tem hoje; cobrar TODO `[data-gesto]`
    que o HTML emite faz a régua crescer sozinha com a aba — o gesto que alguém
    acrescentar amanhã já nasce coberto.

    A MORDIDA (i): acrescente `.luz-grade .ctrl .cel-acoes .btn{display:none}`
    ao `CSS` da `aba04.py` e esta régua reprova nomeando `auto` e `apagar` no
    p1 e no p2.
    """
    cheios = _lugares(medido["como_nasce"], "sim")
    assert cheios, "nenhuma coluna conectada — a régua mediria o vazio"
    for quem, dado in cheios.items():
        assert dado["gestos"], f"{quem} está conectado e não tem gesto nenhum"
        for g in dado["gestos"]:
            assert g["oferecido"], _acusar(
                quem, g, "um lugar COM aparelho não entrega este clique — ela "
                         "vê o controle na tela e o botão não responde")


# ---------------------------------------------------------------------------
# 3. OS DOIS PASSOS DO PILOTO — a mesa dela muda sem recarregar
# ---------------------------------------------------------------------------
def test_o_passo_1c_do_piloto_devolve_o_gesto_sem_recarregar(
        medido: dict) -> None:
    """O P3 que GANHA um controle passa a oferecer os gestos, no mesmo tique.

    O piloto vira a marca `data-conectado` e escreve campo; ele **não cria
    widget**. Por isso os quatro lugares nascem com os widgets no HTML e quem
    os esconde é a folha — e por isso a chave tem de ser `data-conectado`, que
    o piloto vira nos dois sentidos, e não `.vazia`, que é fato de NASCIMENTO e
    ninguém tira nunca.

    A MORDIDA (iii): troque a chave por `.vazia` e só esta régua reprova.
    """
    depois = medido["depois_do_1c"]
    for quem in ("p3", "p4"):
        dado = depois[quem]
        assert dado["conectado"] == "sim", (
            f"{quem} não recebeu a marca do passo 1c")
        mudos = [g for g in dado["gestos"] if not g["oferecido"]
                 and g["gesto"] not in GESTOS_QUE_FICAM_A_VISTA]
        assert not mudos, (
            f"{quem} ganhou um controle e continua sem oferecer "
            f"{[g['gesto'] for g in mudos]} — ela teria de RECARREGAR a página "
            f"para trocar a cor desse controle, e a página é ela quem abre")


def test_o_passo_1b_do_piloto_recolhe_o_gesto_sem_recarregar(
        medido: dict) -> None:
    """E o simétrico: o P1 que ESVAZIA para de oferecer, no mesmo tique.

    Sem esta metade a cura poderia ser um estado inicial sortudo em vez de uma
    regra que segue a mesa.
    """
    dado = medido["depois_do_1b"]["p1"]
    assert dado["conectado"] == "nao", "o p1 não recebeu a marca"  # (noqa-acento) valor
    for g in _oferecidos(dado):
        assert g["gesto"] in GESTOS_QUE_FICAM_A_VISTA, _acusar(
            "p1", g, "o lugar esvaziou e o clique continua sendo entregue")


# ---------------------------------------------------------------------------
# 4. A CÉLULA `LEDs` NÃO TEM GESTO — ordem dela, 07/09/2026
# ---------------------------------------------------------------------------
def test_a_celula_de_leds_nao_tem_gesto(medido: dict) -> None:
    """As cinco lâmpadas MOSTRAM o número; quem o escolhe é a linha `Jogador`.

    *"pq tá surgindo os leds no lado da iluminação se acima já tem o canto dos
    players? pode remover?"* — e a forma final: *"só olhar a linha de cima da
    seleção de player e replicar o que tem lá."*

    ELA MEDE NO NAVEGADOR, e não no texto do HTML, porque é aqui que a pergunta
    é sobre o que ela ALCANÇA com o rato. A régua irmã
    (`test_a_04_as_lampadas_espelham_o_numero`) cobra a mesma ausência no
    fonte; as duas juntas cobrem o caso de um gesto que entra pela folha em vez
    de pelo gerador.
    """
    for estado in ("como_nasce", "depois_do_1c"):
        for quem, dado in medido[estado].items():
            na_celula = [g for g in dado["gestos"]
                         if CELULA_DE_LEDS in g["celula"]]
            assert not na_celula, (
                f"[{estado}] {quem} tem gesto na célula dos LEDs "
                f"({[g['gesto'] for g in na_celula]}) — ela é desenho de "
                f"leitura desde 07/09/2026, e as cinco lâmpadas espelham o "
                f"número sem escolha própria")


# ---------------------------------------------------------------------------
# 5. A FOLGA ESTRUTURAL, MEDIDA E DECLARADA — não é cura, é o laudo
# ---------------------------------------------------------------------------
def test_a_rede_da_casa_nao_cobre_esta_aba() -> None:
    """**A 04 é a única aba onde a rede das dez não protege — e está medido.**

    A rede da casa (`monta.py`, a regra S-04 da folha das dez) desliga os
    controles de um lugar sem dono com um seletor que exclui `.vazia`. A razão
    de excluir é legítima e antiga: o `<span class="nada">` do travessão mora
    lá dentro, e a regra o apagaria.

    **O QUE ISSO CUSTA AQUI:** a 04 é a única aba cujas colunas nascidas vazias
    são `.vazia` **E** carregam widget de gesto — as outras nove ou não têm
    widget no lugar vazio, ou não usam `.vazia`. Logo é a única onde a rede da
    casa não alcança, e a segurança inteira depende de três seletores escritos à
    mão num arquivo só (`aba04.CSS`).

    **A DECISÃO, e ela fica escrita porque a cura NÃO é local:** mudar
    `monta.py` é mexer na folha das DEZ abas, e uma mudança lá sem medir as dez
    é como a leva aprende a errar. Esta frente não a faz — a régua fica no lugar
    da cura, e é ela que impede a folga de virar defeito de novo: qualquer
    caminho pelo qual um gesto desapareça do lugar cheio, ou apareça no vazio,
    reprova aqui, venha ele de `aba04.CSS`, de `monta.py` ou de um `style`
    inline.

    **RELATADO para quem for mexer em `monta.py`:** se a S-04 passar a alcançar
    `.vazia` sem apagar o `<span class="nada">`, os três seletores à mão da
    `aba04.CSS` viram redundância — e é ESTA régua que dirá se a troca ficou
    equivalente, porque ela mede a tela e não a folha.

    ESTE CASO NÃO ABRE NAVEGADOR de propósito: ele afirma um FATO sobre o fonte
    da folha, e o fato é o que sustenta a decisão acima. Se alguém trocar o
    seletor da rede, esta régua avisa que o laudo envelheceu.
    """
    import monta

    folha = monta.CSS_FOLHA
    assert ":not(.vazia)" in folha, (
        "a rede da casa (`monta.CSS_FOLHA`) deixou de excluir `.vazia`. Se "
        "isso foi de propósito, os três seletores à mão da `aba04.CSS` podem "
        "ser redundância agora — meça as dez abas antes de os tirar, e "
        "reescreva este laudo com a data")
