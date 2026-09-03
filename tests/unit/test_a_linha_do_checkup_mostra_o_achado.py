#!/usr/bin/env python3
"""A LINHA DO CHECK-UP MOSTRA O ACHADO — e não o nome de quem o procurou.

**02/09/2026.** As cinco linhas do Check-up da aba Conexões têm três partes: o
selo, a frase e o `?`. A frase e o selo já vinham do exame da mesa dela; as
TRÊS estavam erradas, cada uma de um jeito, e as três têm dono no produto.

**A FRASE MOSTRAVA O RÓTULO.** O pacote emitia ``[i["titulo"] for i in itens]``
— o ``Item.rotulo``, que é o NOME da conferência. Fotografado nesta bancada,
com dois controles na mesa::

    CERTO  Economia de energia desligada        ← o nome do exame
    CERTO  Energia das portas                   ← o nome do exame
    CERTO  Suporte ao controle                  ← o nome do exame

onde o desenho dela promete um achado. A regra é do produto e está escrita no
docstring de ``gui.aba_conexoes.html_do_exame``: *"O texto é o ``porque`` — a
MEDIÇÃO em uma frase —, nunca o rótulo: a tela aprovada mostra o que se achou,
não o nome do que se conferiu."* Os mesmos três itens, pelo ``porque``::

    O sistema está proibido de desligar o rádio dos controles.
    Conferido agora: nenhuma das 16 portas USB está em economia de energia.
    A parte do sistema que fala com o DualSense está carregada.

**O SELO PERDIA UMA PALAVRA.** Ele saía de ``"AJUSTAR" if grave else "CERTO"``,
e o ``Item`` tem QUATRO estados. ``gui.aba_conexoes.SELO_DO_ESTADO`` os mapeia
em TRÊS palavras, e a que sumia era a **NOTA** do ``nao_sei`` — a mesma que o
desenho dela crava na quarta linha. Um "não deu para olhar" chegava à tela como
"AJUSTAR": a tela afirmando um problema que ninguém mediu.

**O `?` NÃO TINHA ENDEREÇO.** Ele continuava sendo o do MOCKUP enquanto o selo
e a frase ao lado já eram os dela — a linha 1 dizia "Economia de energia
desligada" e o `?` explicava *"as entradas em uso entregam 500 mA ou mais"*, que
é a medição de OUTRO achado.

**E ENTÃO O `?` PASSOU A REPETIR A LINHA — decisão dela, 02/09/2026.** Com a
publicação do mesmo dia a linha passou a mostrar a MEDIÇÃO, e a dica ao lado
trazia essa mesma medição na segunda das três metades: a pessoa lia a frase e
a lia de novo ao parar o ponteiro. O `?` fica com o que a linha NÃO diz — **por
que aquilo importa** e **o que fazer**.

A montagem continua sendo do produto (``DICAS_DAS_LINHAS`` e
``PREFIXO_DA_CURA``, de ``secao_exame``); o que mudou é QUEM PEDE. O dono
``_dica_do_item`` fica intacto porque a janela GTK também o usa, e **lá a linha
mostra o ``rotulo``** (``secao_exame.PainelDoExame``, ``:1177``) — naquela tela
a dica é o único caminho de ``Item.porque`` até a pessoa. Duas telas mostram
coisas diferentes na linha, logo pedem dicas diferentes.

**O QUARTO SELO — decisão dela, 02/09/2026.** ``SELO_DO_ESTADO`` manda
``atencao`` e ``problema`` para a MESMA palavra e a MESMA pílula  (noqa-acento)
laranja, e ela
decidiu que *"o que está quebrado agora não pode parecer igual ao que só podia
estar melhor"*. Esta leva entrega a **cor**: a pílula ganhou o endereço
``selo-estado`` (alvo ``classe``), o pacote emite o ESTADO cru e o desenho traz
``.selo.grave`` em ``var(--red)``. **A PALAVRA continua sendo "AJUSTAR" e é
espera dela** — trocá-la seria escolher no lugar dela.

**A MORDIDA:** troque ``i["porque"]`` por ``i["titulo"]`` na chave ``achado`` do
pacote, devolva o selo binário, tire o ``data-campo="achado-explica"`` do
gerador, ponha o ``porque`` de volta na dica, ou apague o ``selo-estado`` —
todos reprovam, cada um com a sua frase.
"""
from __future__ import annotations

import dataclasses
import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.integrations.exame_da_mesa import Item
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08

PACOTE = RAIZ / "src/hefesto_dualsense4unix/interface/pacotes/a08_conexoes.py"
GERADOR = RAIZ / "src/hefesto_dualsense4unix/interface/aba08.py"
BANCADA = RAIZ / "mockup/08-conexoes.html"


def _item(**troca):
    """Um `Item` do exame de mentira, com os campos que a tela lê."""
    base = {
        "chave": "energia_das_portas",
        "rotulo": "Energia das portas",
        "estado": "certo",
        "porque": "Conferido agora: nenhuma das 16 portas USB está em economia de energia.",
        "cura": None,
    }
    base.update(troca)
    return Item(**base)


# --- a frase: o achado, nunca o nome do exame ------------------------------


def test_a_frase_da_linha_e_a_medicao_e_nao_o_rotulo():
    """O que vai para `data-campo="achado"` é o `porque` do `Item`."""
    it = _item()
    linha = a08._linha(it)
    assert linha["porque"] == it.porque
    # O rótulo continua existindo — ele é a primeira metade do `?` —, mas não
    # é ele que a linha mostra.
    assert linha["titulo"] == it.rotulo
    assert linha["porque"] != linha["titulo"]


def test_o_pacote_emite_o_porque_na_chave_achado():
    """A ponta que a foto mostra: a chave `achado` lê `porque`, não `titulo`.

    Lida do FONTE porque `pacote()` precisa do daemon e do sysfs desta máquina.
    O que se trava aqui é a decisão, e ela é uma linha só.
    """
    fonte = PACOTE.read_text(encoding="utf-8")
    assert re.search(r'"achado":\s*\[i\["porque"\] for i in itens\]', fonte), (
        "a chave `achado` do pacote deixou de emitir o `porque` do exame — a "
        "linha do Check-up volta a mostrar o NOME da conferência no lugar do "
        "que ela achou (`gui.aba_conexoes.html_do_exame` diz por quê)"
    )


# --- o selo: as três palavras do produto, não duas -------------------------


@pytest.mark.parametrize(
    ("estado", "palavra", "classe"),
    [
        ("certo", "CERTO", "ok"),
        ("atencao", "AJUSTAR", "warn"),  # (noqa-acento) chave de máquina
        ("problema", "AJUSTAR", "warn"),
        ("nao_sei", "NOTA", "info"),
    ],
)
def test_o_selo_sai_do_mapa_do_produto(estado, palavra, classe):
    """Os quatro estados do `Item` viram as três palavras do desenho dela."""
    linha = a08._linha(_item(estado=estado))
    assert linha["selo"] == palavra
    assert linha["classe"] == classe


def test_o_nao_sei_nao_vira_um_alarme():
    """A regressão que o selo binário produzia, nomeada.

    "Não deu para olhar" é o oposto de "há algo a ajustar". Com a regra antiga
    (`"AJUSTAR" if grave else "CERTO"`) o `nao_sei` caía em "AJUSTAR", porque
    ele não é `certo` — e a tela passava a afirmar um problema que ninguém
    mediu.
    """
    assert a08._linha(_item(estado="nao_sei"))["selo"] != "AJUSTAR"


def test_um_estado_que_a_tela_nao_conhece_nao_vira_verde():
    """Reserva do dono: o desconhecido é NOTA, que é a palavra que não afirma."""
    linha = a08._linha(_item(estado="um_estado_que_ninguem_escreveu"))
    assert linha["selo"] == "NOTA"
    assert linha["classe"] == "info"


# --- o QUARTO selo: `problema` deixa de parecer `atencao` ---  # (noqa-acento)


def test_o_problema_e_o_atencao_chegam_a_tela_como_estados_diferentes():
    """A cor sai do ESTADO, e é ele que separa os dois — não a palavra.

    Enquanto o único canal era `SELO_DO_ESTADO`, os dois estados chegavam à
    tela como a mesma pílula laranja e a mesma palavra: *"o que está quebrado
    agora parecia igual ao que só podia estar melhor"*, que é a frase dela.
    """
    quebrado = a08._linha(_item(estado="problema"))
    so_podia_melhorar = a08._linha(_item(estado="atencao"))  # (noqa-acento) id
    assert quebrado["estado"] != so_podia_melhorar["estado"], (
        "o pacote parou de distinguir `problema` de `atencao` no que manda "  # (noqa-acento) chave
        "para a tela — sem isso a cor do quarto selo não tem em que se apoiar"
    )
    # A PALAVRA AINDA É A MESMA, e isso é ESPERA DELA, não descuido.
    assert quebrado["selo"] == so_podia_melhorar["selo"] == "AJUSTAR"


def test_o_pacote_emite_o_estado_de_cada_selo():
    """Sem a cor por estado, a pílula não tem como saber que ficou vermelha.

    **A RÉGUA ENVELHECEU E FOI REESCRITA — 03/09/2026.** Ela procurava, com um
    `re.search` na FONTE, a linha `"selo-estado": [i["estado"] for i in itens]`
    — o endereço ÚNICO que carregava o estado cru. Essa linha morreu no mesmo
    dia, e morreu por uma MELHORA: o pacote passou a emitir QUATRO endereços,
    um por estado (:func:`a08._selos_por_estado`), porque um nó que pergunta
    *"o estado desta linha é `problema`?"* só aceita `problema` ou o vazio como
    resposta — mandar-lhe `certo` era o pacote respondendo a outra pergunta, e
    a régua do mockup acusava três endereços mortos por isso.

    Reprovar aqui seria reprovar a melhora em vez do defeito, que é o erro mais
    caro desta casa. E a causa da fragilidade era a forma da régua: ela
    **digitava** o texto de uma linha em vez de **ler** o que o pacote faz.

    ENTÃO ELA PASSOU A CHAMAR A FUNÇÃO. `_selos_por_estado` é pura — não pede
    daemon nem sysfs, ao contrário de `pacote()` —, então não há motivo para
    ler fonte nenhuma: mede-se o comportamento.

    O QUE ELA COBRA, e cada uma é a razão de um defeito real:
      1. os QUATRO estados do `Item` têm endereço — sem isso um estado volta a
         não ter cor;
      2. `problema` continua em `selo-estado`, que é a pílula: é o único cuja
         cor ACRESCENTA (`.selo.grave`) em vez de substituir, e mudá-lo de
         endereço quebraria a metade que já funcionava;
      3. cada endereço responde SÓ à sua pergunta — a linha `certo` manda
         `certo` para `selo-certo` e VAZIO para os outros três.

    MORDIDAS (três, e cada uma tem a sua frase): tire uma chave de
    `ENDERECO_DO_ESTADO`; troque o endereço do `problema`; ou devolva o estado
    cru a todos os endereços (`[i["estado"] for i in itens]`).
    """
    # Uma linha de cada estado, na ordem — é o que a mesa dela produz quando um
    # exame acha problema e os outros passam.
    estados = ["certo", "atencao", "problema", "nao_sei"]  # (noqa-acento) chaves
    itens = [a08._linha(_item(estado=e)) for e in estados]
    saida = a08._selos_por_estado(itens)

    assert set(a08.ENDERECO_DO_ESTADO) == set(estados), (
        "o `Item` tem quatro estados e o mapa de endereços não os cobre — o "
        "estado que sobrar chega à tela sem cor nenhuma"
    )
    assert a08.ENDERECO_DO_ESTADO["problema"] == "selo-estado", (
        "o `problema` saiu da pílula. Ele é o único cujo vermelho ACRESCENTA "
        "(`.selo.grave`) em vez de substituir; mudá-lo de endereço quebra a "
        "única metade que já funcionava"
    )
    # CADA ENDEREÇO SÓ RESPONDE À SUA PERGUNTA: na posição do seu estado vai o
    # nome dele; em toda outra posição vai o vazio, que é o `não` desta
    # pergunta — e o `escrever()` do piloto o traduz em apagar a cor.
    for estado, endereco in a08.ENDERECO_DO_ESTADO.items():
        esperado = [e if e == estado else "" for e in estados]
        assert saida[endereco] == esperado, (
            f"o endereço `{endereco}` respondeu {saida[endereco]} para as "
            f"linhas {estados}. Ele pergunta *'o estado é {estado}?'*, e as "
            f"únicas respostas são `{estado}` e o vazio — qualquer outra é o "
            f"pacote respondendo a outra pergunta, que é o que acendia a cor "
            f"errada até 03/09/2026"
        )


def test_a_bancada_acende_o_quarto_selo_pelo_estado():
    """As cinco pílulas do Check-up sabem virar `grave` quando o estado é `problema`.

    O endereço é do DESENHO — é ele que traduz estado em cor. `data-hef-quando`
    lê o estado do exame, e não a classe CSS: o pacote emite o estado cru
    justamente para não pôr a folha de estilo dentro do Python.
    """
    html = BANCADA.read_text(encoding="utf-8")
    endereco = ('data-campo="selo-estado" data-hef-alvo="classe" '
                'data-hef-classe="grave" data-hef-quando="problema"')
    assert html.count(endereco) == 5, (
        "as cinco pílulas do Check-up perderam o endereço do quarto selo — "
        "regere com `python src/hefesto_dualsense4unix/interface/aba08.py`"
    )
    # A PALAVRA CONTINUA NO SEU PRÓPRIO ENDEREÇO, e num elemento à parte: um
    # `data-campo` por nó, e o selo tem dois dados (a palavra e a cor).
    assert html.count('<span data-campo="selo">') == 5


def test_a_bancada_tem_a_cor_do_quarto_selo_e_ela_vence_a_laranja():
    """`.selo.grave` existe, é `--red`, e vem DEPOIS de `.selo.warn`.

    A ordem é o que decide: a pílula nasce no HTML com a classe do desenho
    (`warn`) e o produto ACRESCENTA `grave`. As duas têm a mesma
    especificidade, então a última declarada é a que pinta. Escrita antes,
    a regra existiria e não mudaria um pixel.
    """
    html = BANCADA.read_text(encoding="utf-8")
    assert ".selo.grave{background:var(--red);color:var(--app-bg)}" in html
    assert html.index(".selo.grave{") > html.index(".selo.warn{"), (
        "a cor do quarto selo foi declarada ANTES da laranja — com a mesma "
        "especificidade, a laranja volta a ganhar e a linha quebrada volta a "
        "parecer com a que só podia estar melhor"
    )


def test_o_gerador_e_quem_escreve_o_endereco_do_quarto_selo():
    """A bancada é gerada: quem o apagar do gerador some com ele no próximo `abaNN.py`."""
    fonte = GERADOR.read_text(encoding="utf-8")
    assert 'data-hef-classe="grave" data-hef-quando="problema"' in fonte
    assert ".selo.grave{background:var(--red);color:var(--app-bg)}" in fonte


# --- o `?`: a montagem do produto, em HTML ---------------------------------


def test_a_dica_da_linha_traz_as_duas_metades_do_produto():
    """O `?` traz o "por que importa" e a cura — as duas frases do produto."""
    from hefesto_dualsense4unix.app.actions.config.secao_exame import (
        DICAS_DAS_LINHAS,
        PREFIXO_DA_CURA,
    )

    it = _item(estado="atencao", cura="Troque o cabo de entrada.")  # (noqa-acento)
    dica = a08._linha(it)["dica"]
    assert DICAS_DAS_LINHAS["energia_das_portas"] in dica
    assert PREFIXO_DA_CURA + it.cura in dica


def test_a_dica_nao_repete_a_medicao_que_a_linha_ja_mostra():
    """Decisão dela, 02/09/2026 — e é a metade do meio que sai.

    A linha ao lado mostra o `porque` (ver `achado`, acima). Repeti-lo no `?`
    fazia a pessoa ler a mesma frase duas vezes: uma na tela, outra ao parar o
    ponteiro. Na versão GTK a dica era o único lugar onde a medição cabia,
    porque lá a linha mostra o RÓTULO — aqui ela não é mais.
    """
    it = _item(estado="atencao", cura="Troque o cabo de entrada.")  # (noqa-acento) id
    linha = a08._linha(it)
    assert linha["porque"] == it.porque, "a linha continua mostrando a medição"
    assert it.porque not in linha["dica"], (
        "o `?` da linha voltou a repetir a medição que a linha ao lado já "
        "mostra — decisão dela de 02/09/2026"
    )


def test_o_dono_da_dica_continua_inteiro_para_a_janela_gtk():
    """Curar no dono apagaria a medição da janela estável, onde ela é única.

    `secao_exame._dica_do_item` é chamado pelo `PainelDoExame`, e ali a linha
    mostra `item.rotulo` — o NOME da conferência. Tirar o `porque` DE LÁ deixaria
    a janela GTK sem um caminho para a medição. Por isso quem pede a metade é
    este pacote, e não o dono que muda.
    """
    from hefesto_dualsense4unix.app.actions.config.secao_exame import _dica_do_item

    it = _item(estado="atencao", cura="Troque o cabo de entrada.")  # (noqa-acento) id
    assert it.porque in _dica_do_item(it), (
        "o dono da dica perdeu a medição — a janela GTK mostra o rótulo na "
        "linha, e a dica era o único caminho do `porque` até a tela dela"
    )


def test_a_dica_quebra_linha_em_html_e_nao_em_texto():
    """O alvo é `html`: `\\n\\n` não quebra nada num `<span>`."""
    dica = a08._linha(_item(cura="Faça isto."))["dica"]
    assert "<br><br>" in dica
    assert "\n" not in dica


def test_a_dica_escapa_o_que_viesse_do_exame():
    """Alvo `html` sem escape é marcação vinda do sistema entrando na tela.

    A CURA É A METADE QUE VEM DO SISTEMA — ela nomeia porta, nó e comando
    (`exame_da_mesa`), e é por ela que um `&` ou um `<` entraria. Este teste
    usava o `porque` até 02/09/2026; ele saiu da dica (decisão dela, ver
    acima) e o caminho de escape passou a ser este.
    """
    dica = a08._linha(_item(cura="use a & b < c"))["dica"]
    assert "&amp;" in dica
    assert "&lt;" in dica


def test_uma_linha_sem_cura_nao_inventa_o_que_fazer():
    """`cura=None` é o caso normal do `certo` — e não vira uma frase vazia."""
    from hefesto_dualsense4unix.app.actions.config.secao_exame import PREFIXO_DA_CURA

    assert PREFIXO_DA_CURA not in a08._linha(_item())["dica"]


# --- os endereços novos, na BANCADA (publicar é ato dela) ------------------


def test_o_desenho_da_bancada_endereca_o_ponto_de_interrogacao():
    """Sem `data-campo`, o `?` fica sendo o do mockup ao lado do achado dela."""
    html = BANCADA.read_text(encoding="utf-8")
    assert html.count('data-campo="achado-explica" data-hef-alvo="html"') == 5, (
        "as cinco linhas do Check-up da bancada perderam o endereço do `?` — "
        "regere com `python src/hefesto_dualsense4unix/interface/aba08.py`"
    )
    assert 'data-campo="examinado"' in html


def test_o_gerador_e_quem_escreve_os_dois_enderecos():
    """A bancada é gerada: quem os apagar do gerador some com eles no próximo `abaNN.py`."""
    fonte = GERADOR.read_text(encoding="utf-8")
    assert 'data-campo="achado-explica" data-hef-alvo="html"' in fonte
    assert 'data-campo="examinado"' in fonte


def test_o_pacote_emite_os_dois_enderecos_novos():
    """Emitir antes da publicação é o que faz a dica nascer certa no dia dela."""
    fonte = PACOTE.read_text(encoding="utf-8")
    assert '"achado-explica": [i["dica"] for i in itens]' in fonte
    assert '"examinado": _carimbo_do_exame()' in fonte


# --- o carimbo ------------------------------------------------------------


def test_o_carimbo_diz_agora_mesmo_antes_do_botao():
    """Sem **Examinar Portas** nesta sessão, o que a tira mostra é deste tique."""
    guardado = a08._QUANDO_O_EXAME
    try:
        a08._QUANDO_O_EXAME = None
        assert a08._carimbo_do_exame() == "Examinado agora mesmo"
    finally:
        a08._QUANDO_O_EXAME = guardado


def test_o_carimbo_envelhece_com_o_exame_completo():
    """Ele deixou de ser a frase fixa "há 3 minutos" que o mockup cravava."""
    import time

    guardado = a08._QUANDO_O_EXAME
    try:
        a08._QUANDO_O_EXAME = time.monotonic() - 600
        assert a08._carimbo_do_exame() == "Examinado há 10 minutos"
    finally:
        a08._QUANDO_O_EXAME = guardado


# --- a chave do `maquina.json`: uma conta só ------------------------------


@pytest.mark.parametrize(
    "entrada",
    ["aa:bb:cc:00:00:22", "AA-BB-CC-00-00-22", "  aabbcc000022  ", "aabbcc000022", ""],
)
def test_a_chave_do_maquina_json_e_a_do_produto(entrada):
    """`_so_hex` é embrulho de `core.sysfs_leds.norm_mac`, e não a segunda conta.

    O embrulho existe por UMA razão: `norm_mac` devolve `None` quando não há
    hexa nenhum, e as três chamadas desta aba usam o resultado como chave de
    dicionário e como pedaço de frase — um `None` viraria a chave `None` ou a
    palavra "None" no texto.
    """
    assert a08._so_hex(entrada) == (norm_mac(entrada) or "")


def test_o_so_hex_nunca_devolve_none():
    """`norm_mac` devolve `None` sem um hexa sequer; aqui isso tem de virar `""`."""
    assert norm_mac("zzz") is None
    assert a08._so_hex("zzz") == ""


def test_nao_sobrou_uma_segunda_conta_de_normalizacao_neste_arquivo():
    """A cópia à mão (`.replace(":", "").replace("-", "")`) não pode voltar."""
    fonte = PACOTE.read_text(encoding="utf-8")
    corpo = fonte.split("def _so_hex", 1)[1].split("\ndef ", 1)[0]
    assert 'replace(":", "")' not in corpo, (
        "o `_so_hex` desta aba voltou a normalizar por conta própria — a chave "
        "do `maquina.json` tem um dono só, `core.sysfs_leds.norm_mac`"
    )


def test_o_dataclass_do_exame_ainda_tem_os_campos_que_a_tela_le():
    """Se o `Item` mudar de forma, a tela some sem uma linha de erro.

    É a armadilha que esta casa já pagou: um `getattr` com reserva não levanta,
    e o que sai parece dado — foi assim que o `repr` de um objeto Python foi
    parar na tela dela em 01/09.
    """
    campos = {c.name for c in dataclasses.fields(Item)}
    assert {"chave", "rotulo", "estado", "porque", "cura"} <= campos
