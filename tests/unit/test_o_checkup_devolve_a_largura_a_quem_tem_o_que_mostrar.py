"""O exame fica com a largura do texto dele, e a Sugestão de Conexão nunca some.

**A METADE «SEM ORDEM, O EXAME LEVA TUDO» CAIU EM 26/09/2026**, por pergunta
dela olhando a aba sem controle: *«pq sumiu a parte da caixinha no canto
superior direito?»* (`D-2609-A-SUGESTAO-FICA-LARGA-E-COM-TITULO`,
A-GESTAO-DOS-CONTROLES-NO-PRODUTO-01). A caixa tem título, fica sempre, e
quando não há o que mudar diz «Nada a mudar agora.»; e os dois blocos têm a
mesma altura, com a Sugestão encostada no exame (*«equipa a altura dos dois
blocos e aumenta a largura do bloco da direita até chegar ao lado do bloco da
esquerda»*). O exame fica com a largura do texto dele, até 62% — a frase de 90
caracteres continua cabendo numa linha. A metade que ficou de 19/09 é o teto
das frases do exame (`TETO_DA_FRASE`), e a medição no navegador, que agora mede
a caixa que FICA. O registro de 19/09 segue abaixo, porque é decisão medida.

CHECKUP-VAO-01 — decisão dela, 19/09/2026:

    *"falta deixarmos a área sempre disponível pra ocupar o espaço vazio do
    checkup mesmo sem mostrar nada"*  ·  *"aumenta a largura aqui e resume mais
    pra ter uma linha só"*

**MEDIDO NO NAVEGADOR**, com o achado mais longo do produto injetado nas cinco
linhas, contando quantas ocupam DUAS linhas:

    =========  ===========  =========  ====================  ==============
    janela     ordem?       coluna     frase de 111 (antes)  de 90 (depois)
    =========  ===========  =========  ====================  ==============
    1600 px    com          927 px     0 de 5                0 de 5
    1200 px    com          676 px     **5 de 5**            0 de 5
     940 px    com          512 px     5 de 5                5 de 5
    1200 px    **sem**     1100 px     —                     0 de 5
     940 px    **sem**      840 px     —                     0 de 5
     820 px    **sem**      720 px     —                     0 de 5
    =========  ===========  =========  ====================  ==============

O resumo ganhou a faixa dos 1200; o alargamento ganhou a dos 940 **quando a
coluna da direita está vazia**, que é o caso que ela fotografou. Com ordem de
serviço a 940 px ainda quebra, e isso está declarado: 90 caracteres não cabem em
512 px a 12 px de fonte, e encurtar mais custaria sentido.

ESTA RÉGUA NASCEU DIGITANDO O CSS, E FICOU VERDE SOBRE O DEFEITO VIVO
---------------------------------------------------------------------

As três primeiras versões conferiam se o TEXTO da regra estava no arquivo. Elas
passaram, a cura foi instalada, e ela fotografou a mesma tela vazia horas
depois: *"tá vazio aqui ainda"*.

A regra estava lá e não valia. `:empty` não casa um elemento que tem filho, e a
coluna sem card recebe `monta.NADA_A_DIZER` — `<i class="nada"></i>`, que vai
ali de propósito porque o `escrever()` do piloto troca `''` por travessão. Na
bancada dela as ordens não têm DESTINO (`dongle_atras_de_hub`,
`teclado_so_no_hub`), então o caminho do `NADA_A_DIZER` é o NORMAL, não a
exceção — e era justamente o que o seletor não pegava.

É a armadilha que esta casa já pagou onze vezes num dia: *a régua digita o que
devia LER*. Os testes de texto ficam (publicar é outro erro possível), mas quem
MANDA agora é a medição no Chrome, abaixo — ela reprova com a regra presente e
inválida, que é o caso que aconteceu.
"""

from __future__ import annotations

import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
GERADOR = RAIZ / "src/hefesto_dualsense4unix/interface/aba08.py"
PAGINA = RAIZ / "src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html"
EXAME = RAIZ / "src/hefesto_dualsense4unix/integrations/exame_da_mesa.py"

#: O teto que a medição sustenta. 90 é a maior frase que sobrou; o folgado é
#: para a próxima pessoa não precisar remedir ao acrescentar um achado.
TETO_DA_FRASE = 100

#: As regras do desenho de 26/09: o exame com a largura do texto (até 62%) e a
#: Sugestão com o resto, encostada nele; e a frase de quando não há o que mudar.
REGRAS = (
    ".duas-colunas:has(.col-exame){grid-template-columns:fit-content(62%) minmax(0,1fr);",
    ".sugestao .nada-a-mudar{",
)

#: As que ESCONDIAM a coluna (19/09) e saíram em 26/09: nenhuma delas pode
#: voltar à página, porque a caixa não some mais.
AS_QUE_ESCONDIAM = (
    ".duas-colunas:has(.col-exame){grid-template-columns:1.7fr 1fr}",
    ".duas-colunas:has(.col-exame):has(.col-ordem:empty)",
    ".duas-colunas:has(.col-exame):has(.col-ordem > .nada:only-child)",
)

#: O QUE O PRODUTO PÕE NA COLUNA DA DIREITA, nos três estados que ela tem.
#: Lido do dono (`monta.NADA_A_DIZER`) e não digitado: se o dono trocar a tag,
#: a régua acompanha em vez de medir um mundo que não existe mais.
CHROME = pathlib.Path("/usr/bin/google-chrome")


@pytest.mark.parametrize("regra", REGRAS)
def test_o_gerador_traz_as_tres_regras(regra: str) -> None:
    assert regra in GERADOR.read_text(encoding="utf-8"), (
        "sem esta regra a coluna do exame volta à metade exata, e o achado "
        "mais longo quebra em duas linhas a partir de 1200 px"
    )


@pytest.mark.parametrize("regra", REGRAS)
def test_a_pagina_publicada_traz_as_tres(regra: str) -> None:
    """Curar o gerador e não publicar deixa a tela dela igual."""
    if not PAGINA.exists():  # pragma: no cover — árvore sem a página publicada
        pytest.skip(f"{PAGINA.name} não está publicada nesta árvore")
    assert regra in PAGINA.read_text(encoding="utf-8"), (
        "falta `check_o_desenho_aprovado.py --publicar 08`"
    )


@pytest.mark.parametrize("regra", AS_QUE_ESCONDIAM)
def test_nenhuma_regra_que_escondia_a_caixa_voltou(regra: str) -> None:
    """A caixa não some mais (26/09): nenhuma regra de 19/09 volta à página."""
    for pagina in (PAGINA, RAIZ / "mockup/08-conexoes.html"):
        assert regra not in pagina.read_text(encoding="utf-8"), (
            f"{pagina.name} voltou a trazer `{regra}` — a Sugestão de Conexão "
            "sumiria na tela sem ajuste, a foto de *«pq sumiu a parte da caixinha»*")


def frases_do_exame() -> list[str]:
    fonte = EXAME.read_text(encoding="utf-8")
    achadas = []
    for bloco in re.finditer(r'porque=\(?\s*((?:f?"[^"]*"\s*)+)\)?', fonte):
        achadas.append("".join(re.findall(r'"([^"]*)"', bloco.group(1))))
    return achadas


def test_ha_frases_para_medir() -> None:
    """Conjunto vazio não é verde — é a régua medindo o nada."""
    assert len(frases_do_exame()) >= 15, "o extrator perdeu as frases do exame"


def test_nenhuma_frase_do_exame_passa_do_teto() -> None:
    """*"resume mais pra ter uma linha só"* — a ordem dela, virada número.

    A MORDIDA: devolver qualquer uma das seis frases encurtadas em 19/09 faz
    esta régua reprovar. A pior tinha 129 caracteres.
    """
    longas = [f for f in frases_do_exame() if len(f) > TETO_DA_FRASE]
    assert not longas, "\n".join(
        f"  {len(f)} caracteres: {f}" for f in longas
    ) + (
        f"\n\n{len(longas)} frase(s) acima de {TETO_DA_FRASE} — elas quebram a "
        "linha do achado, que é o que a CHECKUP-VAO-01 veio fechar"
    )


# ──────────────────────────────────────────────────────────────────────────
# A MEDIÇÃO QUE MANDA — a largura LIDA da tela, não a regra digitada
# ──────────────────────────────────────────────────────────────────────────

def _bootstrap() -> str:
    """O `BOOTSTRAP` do piloto, lido do fonte SEM importar `gi`."""
    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py").read_text(
        encoding="utf-8")
    m = re.search(r'BOOTSTRAP = r"""(.*?)"""', fonte, re.S)
    assert m, "não achei o BOOTSTRAP no piloto — a régua ficaria verde sobre nada"
    return m.group(1)


@pytest.fixture(scope="module")
def tela():  # o tipo é o `Page` do playwright, importado lá dentro
    """A `08-conexoes` publicada, num Chrome, com o piloto e a folha da casa."""
    if not CHROME.exists():  # pragma: no cover — CI sem o Chrome do sistema
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    from playwright.sync_api import sync_playwright

    from hefesto_dualsense4unix.interface import onde
    from hefesto_dualsense4unix.interface.folha_da_casa import FOLHA_DA_CASA

    with sync_playwright() as pw:
        navegador = pw.chromium.launch(
            executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = navegador.new_page(viewport={"width": 1180, "height": 780})
            pg.goto(onde.pagina("08-conexoes.html", publicado=True).as_uri())
            pg.add_style_tag(content=FOLHA_DA_CASA)
            pg.evaluate(
                "window.webkit={messageHandlers:{hefesto:{postMessage:function(){}}}};")
            pg.evaluate(_bootstrap())
            yield pg
        finally:
            navegador.close()


def _larguras(pg, ordem: str, achados: int = 8) -> dict:
    """Pinta um tique com essa coluna da direita e mede os dois blocos."""
    # O ESTADO VEM DO DONO (`exame_da_mesa.ESTADO_ATENCAO`) e não digitado. Ele
    # é chave de MÁQUINA, ASCII por contrato — digitá-lo aqui poria a régua a
    # afirmar uma palavra do produto por conta própria, e é a classe de defeito
    # que esta casa mede há um mês: *quando um valor tem dono, a régua pergunta
    # ao dono*. De quebra, o portão de acentuação para de ver prosa sem acento.
    from hefesto_dualsense4unix.integrations.exame_da_mesa import ESTADO_ATENCAO

    pg.evaluate("p => window.__hef.pintar(p)", {"mesa": {
        "achado": [f"achado {i + 1}" for i in range(achados)],
        "achado-explica": ["<b>x</b>"] * achados,
        "selo-estado": [ESTADO_ATENCAO] * achados,
        "exame-calada": [""] * achados,
        "ignorar-dica": [""] * achados,
        "ordem": ordem,
    }})
    return pg.evaluate("""() => {
        const e = document.querySelector('.lado-e').getBoundingClientRect();
        const d = document.querySelector('.lado-d');
        const s = document.querySelector('.sugestao');
        const r = s.getBoundingClientRect();
        const nada = s.querySelector('.nada-a-mudar');
        const quadro = document.querySelector('.duas-colunas').getBoundingClientRect();
        return {esquerda: Math.round(e.width),
                direita: d.offsetHeight > 0 ? Math.round(r.width) : 0,
                quadro: Math.round(quadro.width),
                vao: Math.round(r.left - e.right),
                altura_e: Math.round(e.height), altura_d: Math.round(r.height),
                titulo: (s.querySelector('.ordem-tit') || {}).textContent || '',
                nada: nada && nada.offsetHeight > 0 ? nada.textContent : ''}}""")


def _a08():
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


def _os_dois_blocos_se_encostam(r: dict) -> None:
    assert r["direita"] > 300, (
        f"a Sugestão de Conexão ficou com {r['direita']}px — a caixa sumiu, que é "
        "a foto de *«pq sumiu a parte da caixinha no canto superior direito?»*")
    assert r["titulo"] == _a08().TITULO_DA_ORDEM, r
    assert r["vao"] == 10, f"a Sugestão não encosta no exame (vão de {r['vao']}px)"
    assert abs(r["altura_e"] - r["altura_d"]) <= 1, (
        f"os dois blocos não têm a mesma altura ({r['altura_e']} e {r['altura_d']} px)")
    assert r["esquerda"] <= round(r["quadro"] * 0.62) + 1, (
        f"o exame passou dos 62% ({r['esquerda']} de {r['quadro']}px)")


def test_sem_ajuste_a_caixa_fica_e_diz_que_nao_ha_o_que_mudar(tela) -> None:
    """O CASO DELA de 26/09: a aba sem ajuste — a caixa fica, com a frase."""
    a08 = _a08()
    r = _larguras(tela, a08._html_da_ordem([], None))
    _os_dois_blocos_se_encostam(r)
    assert r["nada"] == a08.NADA_A_MUDAR, r


def test_o_nada_a_dizer_do_piloto_tambem_nao_esconde_a_caixa(tela) -> None:
    """O filho invisível de 19/09 (`monta.NADA_A_DIZER`) não esconde mais nada.

    MORDIDA: devolva à página publicada a regra
    `.duas-colunas:has(.col-exame):has(.col-ordem > .nada:only-child) > .lado-d{display:none}`
    — esta reprova com a caixa em zero px.
    """
    # O APELIDO EM `sys.modules`, e não um `sys.path.insert`: `monta.py` faz
    # `import onde` CRU (nasceu como script de gerador, onde `interface/` é o
    # `sys.path[0]`). É o mesmo truque de `a08_conexoes._monta`, e a razão de
    # não pôr a pasta no caminho de busca está escrita lá — vinte nomes curtos
    # (`casamento`, `mapa`, `regua`, `ver`…) virariam módulos de topo.
    import sys

    from hefesto_dualsense4unix.interface import onde as _onde

    sys.modules.setdefault("onde", _onde)
    from hefesto_dualsense4unix.interface.monta import NADA_A_DIZER

    _os_dois_blocos_se_encostam(_larguras(tela, NADA_A_DIZER))


def test_com_card_de_verdade_a_coluna_fica(tela) -> None:
    """Com um de→para a mostrar, a caixa fica, do mesmo tamanho do exame."""
    card = ('<div class="ordem"><div class="faca"><span class="n">1</span>Mova o '
            'adaptador</div><div class="receita">'
            '<span class="caixa">Entrada 3</span><span class="seta">→</span>'
            '<span class="caixa alvo">Entrada 9</span></div></div>')
    r = _larguras(tela, card)
    _os_dois_blocos_se_encostam(r)
    assert r["nada"] == "", r
