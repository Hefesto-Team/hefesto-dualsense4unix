#!/usr/bin/env python3
"""A RÉGUA DO CLIQUE DO ANALÓGICO — e do terceiro estado que o produto não via.

POR QUE ELA EXISTE. `data-campo="l3"` e `data-campo="r3"` estão na página da aba
Controles desde o primeiro desenho, e até 02/09/2026 **ninguém os pintava**.
Medido pelo `casamento.medir("02-controles.html")` na ponta de `dev`
(2b219284): `vazios: ['l3', 'r3']` — a tela tinha onde e não havia quem
mandasse. Um endereço sem pintor não dá erro: `querySelector` acha o elemento,
o pacote não emite a chave, e o rótulo do mockup fica lá para sempre.

O QUE ELA COBRA, e o item 3 é o que dói:

1. os dois endereços recebem valor quando há leitura;
2. o clicado se distingue do solto;
3. **sem leitor, o valor é o travessão — nunca "solto".** `inputs` é `None`
   para todo controle que não seja o primário nem tenha retrato vivo do co-op
   (`daemon/ipc_handlers.py:3379-3383`), e foi assim que a mesa dela estava
   medida em 02/09/2026 às 04:23:

       uniq aabbcc000001 · bt  · is_primary True  · inputs presente · buttons []
       uniq aabbcc000002 · usb · is_primary False · inputs None

   Dizer "solto" sobre `None` é a tela afirmando uma leitura que ninguém fez —
   o mesmo defeito que `mesa_viva.SEM_LEITOR` nomeia: *"nunca o último valor
   como se fosse vivo, nunca zero fingindo repouso"*.

4. o mesmo para o touchpad, que era pior: `"touch-estado"` era a **constante**
   `"Sem toque"`. A tela afirmava, sem ler nada, que ninguém estava encostando.

5. e o espelho do item 1: **nada do que o pacote emite cai fora da página.**
   Eram três — `l2`, `r2` e `via` —, e os três entravam na conta de
   `cobertura.pintados` sem escrever um pixel.

A MORDIDA está escrita em cada teste, no lugar onde ela reprova.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: MAC da faixa sintética da casa — há dois portões de anonimato nesta árvore.
UNIQ = "aa:bb:cc:00:00:01"

#: O controle da régua. `is_primary` e `inputs` são o par que decide o terceiro
#: estado, e por isso cada teste os monta explicitamente em vez de herdar.
BASE = {
    "uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
    "battery_pct": 95, "lightbar_rgb": [0, 0, 255], "is_primary": True,
    "audio": {}, "speaker": {},
}


@pytest.fixture(scope="module")
def pac():
    import pacotes

    return pacotes


@pytest.fixture(scope="module")
def a02():
    from pacotes import a02_controles

    return a02_controles


@pytest.fixture(scope="module")
def desenho(a02):
    """O TEXTO DE TELA, e o dono dele é o PACOTE — não o gerador.

    A seta aponta para o produto por medição: o
    `portao_a_casa_sabe_e_o_produto_nao_faz` poda os `abaNN.py` da conta por
    serem BANCADA, e importar o gerador de dentro do pacote arrasta a bancada
    para o fecho de produção — em 02/09/2026 isso acendeu três lápides de
    `interface/monta.py` e reprovou o portão. Quem lê é o gerador.
    """
    return a02


def _card(pac, a02, entrada: dict) -> dict:
    """O dicionário de UM card, do pacote real, sem janela e sem daemon."""
    ctx = pac.Contexto(state={}, mesa=[], conectados=[entrada], estados={})
    return next(iter(a02.pacote(ctx)["cards"].values()))


# --------------------------------------------------------------------------
# 1 e 2. o clique, quando há leitura
# --------------------------------------------------------------------------
def test_sem_apertar_o_rotulo_e_o_do_desenho(pac, a02, desenho):
    """Solto, o círculo mostra o rótulo que o gerador desenhou — e só ele.

    MORDE: se o pacote emitir a marca do clicado por engano (trocar a condição
    por `not campo in apertados`), este teste reprova com `[L3]` no lugar de
    `L3` — e essa troca não apareceria em foto nenhuma, porque um analógico em
    repouso é o estado de 99% do tempo.
    """
    d = _card(pac, a02, {**BASE, "inputs": {}})
    assert d["l3"] == desenho.ROTULO_DO_CLIQUE["l"]
    assert d["r3"] == desenho.ROTULO_DO_CLIQUE["r"]


@pytest.mark.parametrize(
    ("botao", "campo", "lado"),
    [("l3", "l3", "l"), ("r3", "r3", "r")],
)
def test_o_clique_de_cada_analogico_aparece_sozinho(
    pac, a02, desenho, botao, campo, lado
):
    """Clicar L3 marca L3 e **não** marca R3, e vice-versa.

    O par é testado junto de propósito: a forma mais fácil de errar aqui é ler
    `apertados` uma vez e escrever nos dois campos — o defeito que a GTK evita
    com duas variáveis separadas (`controller_card.py:5453-5454`).

    MORDE: fazer os dois campos lerem o mesmo botão reprova na segunda metade.
    """
    d = _card(pac, a02, {**BASE, "inputs": {"buttons": [botao, "cross"]}})
    assert d[campo] == desenho.CLICADO % desenho.ROTULO_DO_CLIQUE[lado]
    outro = "r3" if campo == "l3" else "l3"
    outro_lado = "r" if lado == "l" else "l"
    assert d[outro] == desenho.ROTULO_DO_CLIQUE[outro_lado], (
        "o clique de um analógico acendeu o outro")


# --------------------------------------------------------------------------
# 3. O TERCEIRO ESTADO — e é o que esta régua existe para trancar
# --------------------------------------------------------------------------
def test_sem_leitor_os_dois_analogicos_dao_travessao(pac, a02, desenho):
    """`inputs: None` é "não sei", e nunca "não apertado".

    MEDIDO na mesa dela em 02/09/2026: o controle não-primário chega com
    `inputs` valendo `None` — o daemon só preenche a chave para o primário ou
    para quem tem retrato vivo do co-op (`ipc_handlers.py:3379-3383`). Antes
    desta cura o pacote nem emitia os campos, e o círculo mostrava o `L3` do
    mockup como se fosse leitura.

    MORDE: trocar o `tem_leitor` por `e.get("buttons")` (que é o que um `or {}`
    convida a fazer) faz este teste reprovar com `'L3' != '—'`. É a mordida
    exata: o `or {}` apaga a diferença entre `None` e `{}`.
    """
    import mesa_viva

    d = _card(pac, a02, {**BASE, "is_primary": False, "inputs": None})
    assert d["l3"] == mesa_viva.SEM_LEITOR
    assert d["r3"] == mesa_viva.SEM_LEITOR
    assert d["l3"] != desenho.ROTULO_DO_CLIQUE["l"], (
        "sem leitura, a tela mostrou o rótulo como se tivesse medido o repouso")


def test_dicionario_de_inputs_vazio_nao_e_falta_de_leitor(pac, a02, desenho):
    """`{}` é leitura que veio sem botão apertado — e isso é diferente de `None`.

    Os dois casos vizinhos, no mesmo teste, porque a régua só vale se separar
    os dois: um `inputs` vazio é o primário com as mãos paradas.

    MORDE: tratar `{}` como ausência (um `if not e:` no lugar do `isinstance`)
    põe travessão num controle que o daemon ESTÁ lendo, e reprova aqui.
    """
    d = _card(pac, a02, {**BASE, "inputs": {}})
    assert d["l3"] == desenho.ROTULO_DO_CLIQUE["l"]


# --------------------------------------------------------------------------
# 4. o touchpad, que era uma constante
# --------------------------------------------------------------------------
def test_o_touchpad_deixou_de_ser_constante(pac, a02, desenho):
    """"Sem toque" era literal no código: um dedo não mudava um pixel.

    MORDE: devolver a constante (`"touch-estado": "Sem toque"`) faz o caso do
    dedo reprovar — e era exatamente esse o estado do produto até 02/09/2026.
    """
    import mesa_viva

    tocando = _card(pac, a02, {**BASE, "inputs": {"touchpad": {"touching": True}}})
    solto = _card(pac, a02, {**BASE, "inputs": {"touchpad": {"touching": False}}})
    cego = _card(pac, a02, {**BASE, "is_primary": False, "inputs": None})
    assert tocando["touch-estado"] == desenho.COM_TOQUE
    assert solto["touch-estado"] == desenho.SEM_TOQUE
    assert cego["touch-estado"] == mesa_viva.SEM_LEITOR


# --------------------------------------------------------------------------
# 5. o espelho: nada emitido cai fora da página
# --------------------------------------------------------------------------
def test_a_aba_controles_nao_emite_para_endereco_que_a_pagina_nao_tem():
    """Órfão é valor calculado a cada tique e jogado fora — e conta cobertura falsa.

    Eram três em 02/09/2026, medidos na ponta de `dev`: `l2`, `r2` e `via`. Os
    três entravam em `cobertura.pintados` sem escrever um pixel, e o `via` é o
    pior deles: o cabeçalho do card mostra o transporte como TEXTO DO DESENHO,
    e medido às 04:23 os dois cabeçalhos diziam o contrário da mesa viva
    (`p1 → BT`, `p2 → USB`, e a tela dizia USB e BT).

    MORDE: devolver `"via": (c.get("transport") or "").upper()` ao pacote faz
    este teste reprovar nomeando `via`.
    """
    import casamento

    m = casamento.medir("02-controles.html")
    assert sorted(m["orfaos"]) == [], (
        f"a aba Controles emite {sorted(m['orfaos'])} e a página publicada não "
        f"tem endereço para eles — valor calculado a cada tique e jogado fora.")


def test_a_aba_controles_nao_deixa_endereco_da_pagina_sem_pintor():
    """O outro lado do espelho: `vazios` era `['l3', 'r3']`.

    MORDE: tirar do pacote as duas chaves do clique faz este teste reprovar
    nomeando as duas — que é o estado em que a aba viveu até 02/09/2026.
    """
    import casamento

    m = casamento.medir("02-controles.html")
    assert sorted(m["vazios"]) == [], (
        f"a página 02-controles.html tem {sorted(m['vazios'])} e ninguém os "
        f"pinta — o rótulo do mockup fica na tela como se fosse leitura.")


# --------------------------------------------------------------------------
# 6. o texto de tela tem UM dono, e é o gerador
# --------------------------------------------------------------------------
def test_o_gerador_le_o_texto_de_tela_do_pacote(a02):
    """O `aba02.py` não pode ter uma SEGUNDA cópia das mesmas palavras.

    MORDE: redigitar `SEM_TOQUE = "Sem toque"` no gerador passa neste teste por
    igualdade de valor — por isso a régua compara IDENTIDADE (`is`), que só o
    import satisfaz. Foi por cópia divergente que o "Sem toque" já nasceu duas
    vezes nesta aba.
    """
    import aba02

    achados = [n for n in ("SEM_TOQUE", "COM_TOQUE", "ROTULO_DO_CLIQUE", "CLICADO")
               if hasattr(aba02, n)]
    assert len(achados) >= 3, (
        f"o gerador só conhece {achados} — se ele parou de importar o texto de "
        f"tela do pacote, esta régua ficou vazia e não mede mais nada.")
    for nome in achados:
        assert getattr(aba02, nome) is getattr(a02, nome), (
            f"o gerador tem uma cópia própria de {nome} — duas verdades sobre "
            f"a mesma palavra de tela.")


def test_o_rotulo_do_circulo_e_o_mesmo_no_desenho_e_na_pintura(desenho):
    """A página publicada e o pacote têm de dizer a mesma palavra.

    Sem esta régua, mudar `ROTULO_DO_CLIQUE` no gerador e esquecer de republicar
    faria o primeiro tique TROCAR o rótulo do círculo — e a troca só apareceria
    numa foto que ninguém tira.

    MORDE: mude `ROTULO_DO_CLIQUE["l"]` para `"L³"` sem rodar o gerador; este
    teste reprova dizendo que a página publicada ainda diz `L3`.
    """
    from hefesto_dualsense4unix.interface import onde

    html = onde.pagina("02-controles.html", publicado=True).read_text(encoding="utf-8")
    for lado, campo in (("l", "l3"), ("r", "r3")):
        marca = f'data-campo="{campo}">{desenho.ROTULO_DO_CLIQUE[lado]}<'
        assert marca in html, (
            f"a página publicada não traz {marca!r} — o gerador e o pacote "
            f"passaram a dizer palavras diferentes sobre o mesmo círculo.")
