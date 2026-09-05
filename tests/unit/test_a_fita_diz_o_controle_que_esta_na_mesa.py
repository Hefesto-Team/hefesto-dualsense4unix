"""A FITA DO TOPO — e ela aparece nas DEZ abas, o que multiplica todo defeito.

Ela viu e disse, em 02/09/2026: *"o controle identificado em todas ta
completamente errado"*. Medido no mesmo dia, com os dois controles dela na mesa
(um no cabo, um no rádio) e o daemon respondendo em **1 ms**:

    o daemon publica    modelo="White" (usb, do serial) · null (bt)
    identidade_de()     "White" · "BT"                       ← certo
    o CARD mostrava     "White · USB" · "Não sei · BT"       ← certo
    a FITA mostrava     "P1 • Cosmic Red • USB" · "P2 • Starlight Blue • BT"

Os dois chips do MOCKUP, congelados, com a borda vermelha e a azul do desenho
sobre um controle branco.

**AS TRÊS CAUSAS, e as três moram em `monta.py`:**

1. o nome saía de ``c["nome"]``, que na mesa viva é o nome do PLÁSTICO — e vale
   ``"Não sei"`` quando a cor não foi lida. Quem sabe nomear um controle é
   ``pacotes.identidade_de``;
2. ``cor_da_zona("")`` levantava ``SystemExit`` e derrubava a fita inteira. No
   rádio a cor do plástico NUNCA chega (`identidade.cor_do_aparelho`,
   `radio_aciona = não`), então com um controle no BT a fita morria a cada
   tique — e a tela ficava com o mockup para sempre;
3. ``fita()`` devolvia a string RECUADA. O ``outerHTML`` que o navegador
   devolve não tem recuo, então a comparação de ``hefesto_vivo.py:379`` nunca
   casava: a fita se trocava inteira **a cada tique**, e cada troca deixava
   para trás o nó de texto dos quatro espaços. Medido: 29 tiques, 29 pinturas;
   com o recuo fora, 29 tiques e **2** pinturas.

FIXTURES: faixa sintética ``02fe00`` da casa. Nenhum endereço real entra em
arquivo versionado, e há dois portões que reprovam.
"""

from __future__ import annotations

import sys
from typing import Any

import pytest

# A ORDEM IMPORTA: `pacotes/__init__` põe `interface/` no `sys.path`, e é dele
# que `monta` precisa para achar o `onde`. Importar `monta` primeiro dá
# `ModuleNotFoundError: No module named 'onde'`.
from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface import monta

#: Os dois da bancada, na faixa sintética da casa.
NO_CABO = "02fe00000001"
NO_RADIO = "02fe00000002"


def _item(pref: str, jogador: int, transporte: str, uniq: str,
          cor: str = "", nome: str = "Não sei", **extras: Any) -> dict[str, Any]:
    """Um item de mesa VIVA, com as chaves que `mesa_viva.mesa_do_estado` põe.

    `nome` nasce ``"Não sei"`` de propósito: é o que o leitor de cor devolve
    enquanto não leu, e é o valor que fazia a fita mentir.
    """
    item: dict[str, Any] = {
        "pref": pref, "uniq": uniq, "jogador": jogador, "cor": cor, "nome": nome,
        "via": "USB" if transporte == "usb" else "BT", "transporte": transporte,
        "alvo": pref == "p1", "mascara": "DualSense",
    }
    item.update(extras)
    return item


#: A MESA DELA, como o daemon a entregou em 02/09/2026: um no cabo com a cor do
#: plástico já lida (White), um no rádio sem cor nenhuma — e o rádio nunca terá.
MESA_DELA = [
    _item("p1", 1, "usb", NO_CABO, cor="white", nome="White"),
    _item("p2", 2, "bt", NO_RADIO),
]


def _chips(html: str) -> list[str]:
    """Os chips da fita, sem o "Todos"."""
    return [c for c in html.split("\n") if 'class="chip plastico' in c
            or ('class="chip' in c and "Todos" not in c)]


def _nome_escrito(chip: str, c: dict[str, Any]) -> str:
    """O pedaço do MEIO do chip — o que a fita afirma ser o nome do aparelho.

    O chip é ``P{n} • {nome} • {via}``, e sem nome é ``P{n} • {via}``. Ler o
    meio é o que separa "o chip diz o nome certo" de "a string está lá em algum
    lugar", que é a diferença entre uma régua e um instrumento falso.
    """
    dentro = chip[chip.index(">", chip.index("title=")) + 1: chip.rindex("</span>")]
    partes = [p.strip() for p in dentro.split(monta.SEPARADOR.strip())]
    partes = [p for p in partes if p]
    # O MEIO É POSIÇÃO, NÃO FILTRO. Filtrar "o que não for `P2` nem `BT`"
    # apagaria também o `BT` do MEIO — e a régua ficaria verde exatamente sobre
    # o `P2 • BT • BT` que ela nasceu para pegar. Medido: com o filtro, a
    # mordida 3 passou.
    assert partes[0] == f'P{c["jogador"]}', chip
    assert partes[-1] == c["via"], chip
    return " ".join(partes[1:-1])


# ---------------------------------------------------------------------------
# 1. O NOME VEM DO DONO, E NUNCA DO MOCKUP
# ---------------------------------------------------------------------------
def test_a_fita_viva_nao_repete_um_nome_do_mockup() -> None:
    """Com a mesa dela, nenhum chip pode dizer "Cosmic Red" ou "Starlight Blue".

    É o defeito que ela viu, e o teste que o guarda: os dois nomes são do
    DESENHO, e nenhum dos dois aparelhos dela se chama assim.

    MORDIDA: troque `identidade_do_chip(c, mesa)` por `c["nome"]` em `fita()` e
    este teste continua verde (a mesa diz "White"/"Não sei") — quem o pega é o
    `test_a_fita_pergunta_ao_dono_do_nome` abaixo. Mas ponha `mesa=None` no
    caminho vivo e ele reprova nomeando os dois.
    """
    html = monta.fita(ativo="p1", mesa=MESA_DELA)
    for inventado in ("Cosmic Red", "Starlight Blue", "Galactic Purple"):
        assert inventado not in html, (
            f"a fita viva ainda nomeia {inventado!r}, que é do mockup:\n{html}")


def test_a_fita_pergunta_ao_dono_do_nome() -> None:
    """O nome do chip TEM de ser o que ``pacotes.identidade_de`` responde.

    Não é "um nome parecido": é o MESMO. Uma segunda leitura aqui divergiria no
    dia em que a ordem do dono mudasse — e a ordem dele é *o que ELA nomeou > o
    modelo decodificado > o transporte só*, nunca a posição.

    A RÉGUA PASSA PELA `fita()`, e não por `identidade_do_chip` sozinha: o
    defeito que ela viu não era o dono errado — era a fita **não perguntando a
    ele**. Uma régua que só exercitasse o dono ficaria verde com a chamada
    arrancada, que é o instrumento falso que esta casa persegue.

    MORDIDA: troque `identidade_do_chip(c, mesa)` por `c["nome"]` em `fita()` e
    este teste reprova no controle do rádio — a mesa diz "Não sei" e o dono diz
    "BT" (que o chip então cala, porque já termina no transporte).
    """
    html = monta.fita(ativo="p1", mesa=MESA_DELA)
    for c in MESA_DELA:
        do_dono = pacotes.identidade_de({**c, "transport": c["transporte"]}, MESA_DELA)
        assert monta.identidade_do_chip(c, MESA_DELA) == do_dono, (
            f"o chip de {c['pref']} nomeia diferente do dono ({do_dono!r})")
        # e o que SAIU na fita tem de ser esse nome — ou nada, quando ele não
        # acrescenta ao transporte que o chip já mostra.
        chip = [x for x in _chips(html) if f'P{c["jogador"]} ' in x]
        assert chip, html
        esperado = "" if do_dono in (c["via"], monta.TRAVESSAO) else do_dono
        escrito = _nome_escrito(chip[0], c)
        assert escrito == esperado, (
            f"o chip de {c['pref']} escreveu {escrito!r} e o dono diz "
            f"{esperado!r}:\n  {chip[0]}")


def test_a_fita_nunca_escreve_nao_sei_como_nome_de_controle() -> None:
    """``"Não sei"`` é a AUSÊNCIA da leitura da cor, não um nome de aparelho.

    É o que a mesa viva põe em ``nome`` enquanto o plástico não foi lido — e no
    rádio nunca será. Passá-lo adiante põe "Não sei • BT" onde cabia "BT".

    MORDIDA: troque `identidade_do_chip(c, mesa)` por `c["nome"]` em `fita()` e
    este teste reprova nomeando o chip do rádio.
    """
    html = monta.fita(ativo="p1", mesa=MESA_DELA)
    assert pacotes.NOME_SEM_LEITURA not in html, (
        f"a fita escreveu {pacotes.NOME_SEM_LEITURA!r} como nome:\n{html}")


def test_o_que_ela_nomeou_vence_tudo() -> None:
    """``nome_declarado`` na frente do modelo e do transporte — a ordem do dono.

    MORDIDA: tire o `nome_declarado` do dicionário e o chip volta a "White".
    """
    dela = [{**MESA_DELA[0], "nome_declarado": "o meu do cabo"}, MESA_DELA[1]]
    html = monta.fita(ativo="p1", mesa=dela)
    assert "o meu do cabo" in html, html


def test_o_nome_nao_muda_quando_o_controle_troca_de_posicao() -> None:
    """O MESMO aparelho, na posição 1 e na 2, tem de se chamar igual.

    É o defeito da ROTA-A com outra roupa: *"com um controle o do cabo era
    Starlight Blue; com dois, o MESMO cabo virou Cosmic Red"*. Nomear pela
    posição é o que faz um controle mudar de nome sem ninguém tocar nele.

    MORDIDA: nomeie o chip por `mesa[i]["nome"]` (o índice, não o `uniq`) e
    este teste reprova.
    """
    primeiro = monta.identidade_do_chip(MESA_DELA[0], MESA_DELA)
    invertida = [
        _item("p1", 1, "bt", NO_RADIO),
        _item("p2", 2, "usb", NO_CABO, cor="white", nome="White"),
    ]
    depois = monta.identidade_do_chip(invertida[1], invertida)
    assert primeiro == depois == "White", (
        f"o mesmo aparelho mudou de nome ao trocar de posição: "
        f"{primeiro!r} → {depois!r}")


def test_o_travessao_daqui_e_o_travessao_da_casa() -> None:
    """``monta.TRAVESSAO`` é literal para não fechar o ciclo de import — e por
    isso precisa de régua que o prenda ao original.

    MORDIDA: troque um dos dois por um hífen comum e este teste reprova.
    """
    assert monta.TRAVESSAO == pacotes.TRAVESSAO


# ---------------------------------------------------------------------------
# 2. O QUE NÃO SE SABE NÃO SE ESCREVE
# ---------------------------------------------------------------------------
def test_a_cor_nao_lida_nao_derruba_a_fita() -> None:
    """Um controle sem cor de plástico não pode matar a fita inteira.

    Era `SystemExit: colorway '' não existe`, e no rádio a cor NUNCA chega. Com
    um controle no BT a fita viva morria a cada tique — e a tela ficava com os
    chips do mockup para sempre. Foi assim que ela viu o defeito.

    MORDIDA: volte a `cor_da_zona(str(c["cor"]))` incondicional e este teste
    reprova com o `SystemExit` do portão de cores.
    """
    html = monta.fita(ativo="p1", mesa=MESA_DELA)
    assert 'class="chip"' in html or 'class="chip on"' in html, (
        "o chip sem cor lida devia perder a classe `plastico`:\n" + html)
    assert "--plastico:;" not in html and '--plastico:"' not in html, html


def test_o_chip_sem_cor_diz_por_que_nao_tem_borda() -> None:
    """A borda que some tem de se explicar no `title`, não sumir calada.

    MORDIDA: devolva o `title` fixo *"a borda é a cor do plástico"* e este
    teste reprova — a frase promete uma borda que não está lá.
    """
    html = monta.fita(ativo="p1", mesa=MESA_DELA)
    assert "a cor do plástico deste controle não foi lida" in html, html


def test_o_chip_nao_diz_o_transporte_duas_vezes() -> None:
    """``P2 • BT • BT`` é o mesmo fato dito duas vezes — e o chip já termina no
    transporte.

    O último degrau de `identidade_de` é *"o transporte sozinho"*: honesto num
    card, que só mostra o nome; mudo aqui. Regra dela, 02/09/2026: *"se não tá
    mostrando agora, não tem info pra mostrar no produto"*.

    MORDIDA: tire o ramo `if nome in (c["via"], TRAVESSAO)` e este teste
    reprova com o chip do rádio dizendo `BT` duas vezes.
    """
    radio = MESA_DELA[1]
    html = monta.fita(ativo="p1", mesa=MESA_DELA)
    chip = [c for c in _chips(html) if f'P{radio["jogador"]} ' in c]
    assert chip, html
    # O NOME É O PEDAÇO DO MEIO, e é ele que tem de estar vazio. Contar
    # ocorrências de "BT" na linha inteira seria régua cega: o `title` também
    # diz BT, e o chip termina no transporte de propósito.
    assert _nome_escrito(chip[0], radio) == "", (
        "o chip do rádio diz o transporte duas vezes:\n  " + chip[0])


def test_a_mesa_vazia_nao_inventa_chip() -> None:
    """Zero controles, zero chips — e nem o "Todos" sobra.

    Com a mesa vazia o topo dizia `0 controles` e a MESMA tela mostrava
    `P1 • Cosmic Red • USB`. Fotografado em 02/09/2026.

    A ÚLTIMA LINHA VIROU DO AVESSO EM 04/09/2026, e não foi afrouxamento: ela
    exigia `"Todos" in html`, e a decisão dela desse dia — *"só faz sentido
    aparecer o todos, no selecionar se tiver mais de um controle conectado"* —
    tirou o chip de onde não há escolha. Zero controles não é *mais de um*, e um
    `Todos` sobre mesa vazia ofereceria escolher entre nada. A garantia que este
    teste dá continua a mesma, e agora vale para os três chips: **a fita não
    inventa chip nenhum**.

    MORDIDA: faça o laço cair em `CONECTADOS` quando a mesa viva for vazia
    (o `mesa or CONECTADOS` que parece inofensivo) e este teste reprova.
    """
    html = monta.fita(ativo="todos", mesa=[])
    assert "Cosmic Red" not in html and "P1" not in html, html
    assert "Todos" not in html, html


# ---------------------------------------------------------------------------
# 3. O DESENHO NÃO SE MEXE — e a forma que o gerador da 02 precisa
# ---------------------------------------------------------------------------
def test_o_mockup_sai_igual_ao_que_ela_aprovou() -> None:
    """Sem mesa viva, a fita é a do DESENHO, chip por chip.

    É o que faz as dez páginas saírem byte a byte iguais depois desta cura.

    MORDIDA: aplique `identidade_do_chip` também quando `mesa is None` e este
    teste reprova — os itens do mockup não têm `uniq`, e todos passariam a se
    chamar pelo primeiro da lista.
    """
    html = monta.fita(ativo="p1")
    assert "Cosmic Red" in html and "Starlight Blue" in html, html
    assert html.count('class="chip') == len(monta.CONECTADOS) + 1


def test_a_fita_nasce_sem_recuo_para_o_navegador_poder_compara_la() -> None:
    """``fita()`` não recua a primeira linha; quem monta a PÁGINA é que recua.

    O ``outerHTML`` que o WebKit devolve nunca tem recuo. Com o recuo aqui,
    ``f.outerHTML !== p.fita`` era verdade para sempre e a fita se trocava
    inteira dez vezes por segundo — cada troca deixando o nó de texto dos
    quatro espaços para trás. Medido em 02/09/2026: **29 tiques, 29 pinturas**;
    sem o recuo, 29 tiques e 2 pinturas.

    MORDIDA: devolva o `'    <div class="fita'` para dentro de `fita()` e este
    teste reprova.
    """
    html = monta.fita()
    assert html.startswith('<div class="fita'), repr(html[:40])
    assert not html[0].isspace()


@pytest.mark.parametrize("mesa", [None, MESA_DELA])
def test_o_chip_continua_na_forma_que_a_aba_controles_reescreve(
    mesa: list[dict[str, Any]] | None,
) -> None:
    """A `02-controles` transforma cada chip num ``<label for>`` do rádio dele.

    ``aba02.fita_clicavel`` casa por ``<span class="chip…"…>…</span>`` numa
    linha só, e PARA em vez de entregar uma fita que não clica. Esta régua roda
    o gerador contra a fita viva também: sem ela, uma mudança de forma aqui só
    apareceria no dia em que a tela viva trocasse a fita da aba Controles — e
    aí os cards parariam de abrir, sem sintoma.

    MORDIDA: quebre o chip em duas linhas, ou ponha o `style` antes do `class`,
    e o gerador levanta `SystemExit` — este teste reprova nomeando o chip.
    """
    aba02 = _gerador_da_02()
    html = monta.fita(ativo="p1", mesa=mesa)
    virou = aba02.fita_clicavel(html, mesa=mesa)
    quantos = len(monta.CONECTADOS if mesa is None else mesa)
    assert virou.count("<label for=") == quantos + 1, virou


def _gerador_da_02() -> Any:
    """O ``aba02.py`` importado como ele se importa — só no TESTE.

    Ele insere a própria pasta no `sys.path` e lê o `monta`; no produto isso
    seria uma janela que não abre onde não há repositório, e por isso o gerador
    não atravessa. Aqui é barato e é o único jeito de a régua exercitar a forma
    de verdade em vez de a descrever.
    """
    import pathlib

    from hefesto_dualsense4unix.interface import onde

    pasta = str(pathlib.Path(onde.__file__).resolve().parent)
    if pasta not in sys.path:
        sys.path.insert(0, pasta)
    import aba02  # type: ignore[import-not-found]

    return aba02
