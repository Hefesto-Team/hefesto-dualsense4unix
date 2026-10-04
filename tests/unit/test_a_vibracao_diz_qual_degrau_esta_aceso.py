#!/usr/bin/env python3
"""A ABA VIBRAÇÃO: o degrau aceso vem do daemon, e a largura sai sem `%`.

DUAS COISAS, e as duas foram medidas em 02/09/2026 com o daemon dela vivo e
DOIS controles na mesa (um no `usb`, um no `bt`).

1. **O DEGRAU ACESO SAÍA DO DESENHO, e o desenho MENTIA.** A política de
   vibração é UMA, da mesa (``state_full.rumble_policy``), e o mockup crava um
   degrau aceso por coluna: o P1 nasce em "Máximo" e o P2 em "Balanceado". Com
   o daemon respondendo ``rumble_policy = 'balanceado'``, a coluna do P1
   afirmava o contrário do que está no disco. Não era desenho esperando dado —
   era a tela dizendo o oposto.

   A cura NÃO É ESCREVER TEXTO nos botões: isso já foi tentado na manhã do
   mesmo dia e apagou os quatro rótulos, tirando dela a escolha. QUAL dos
   quatro está aceso é a **classe** ``on``, e o alvo ``classe`` do
   ``escrever()`` (``hefesto_vivo.py:83``) acende quem casa com o
   ``data-hef-quando`` e apaga as irmãs.

2. **``motor-e-pct`` NÃO É ENDEREÇO MORTO** — a acusação da régua do mockup é
   FALSA, e esta régua pina o contrato que a desmente. O alvo ``largura`` do
   ``escrever()`` faz ``el.style.width = valor + '%'``: quem emite escreve o
   número PELADO. A régua do mockup compara a declaração (``'0'``) com o que o
   CSSOM devolve (``'0%'``) sem refazer essa tradução — e só percebe a
   diferença quando o valor pintado COINCIDE com o cravado, que é o caso do
   ``motor-e-pct`` do P1 (o desenho crava ``width:0.0%``). O ``motor-d-pct``
   emite o MESMO ``'0'`` e é contado PRODUTO só porque o desenho crava
   ``23.5%``. Mesmo código, veredito oposto: a diferença está no cravado, não
   no endereço. A cura mora em ``regua_do_mockup._declarado_neste_elemento``,
   que é território de outra frente.

A MORDIDA:

* tire o ``data-hef-quando`` dos quatro botões em ``aba05._coluna``, rode o
  gerador, e ``test_cada_degrau_diz_quem_ele_e`` reprova — e a reprovação não é
  cosmética: sem ele o alvo ``classe`` vira BOOLEANO e ``'balanceado'`` acende
  os QUATRO ao mesmo tempo;
* tire a chave ``degrau`` do ``a05_vibracao.pacote`` e
  ``test_o_pacote_emite_o_degrau_que_o_produto_calculou`` reprova;
* devolva o ``%`` ao ``forca-pct`` e ``test_a_largura_sai_sem_o_por_cento``
  reprova — a barra viraria ``width:46.7%%``, que o CSS descarta.

ONDE ELA MEDE: na **BANCADA**, que é onde o gerador escreve e onde o endereço
existe. A página publicada ainda não o tem, e é por isso que a tela dela não
muda até o ``--publicar 05``.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.aba05`, que carrega o GTK")

from hefesto_dualsense4unix.interface import aba05 as _aba05
from hefesto_dualsense4unix.interface import regua_do_mockup as _regua

PAGINA = "05-vibracao.html"

UNIQS = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02")

TOKEN_VIZINHO = "maximo"  # (noqa-acento) chave de máquina


@pytest.fixture(scope="module")
def bancada() -> str:
    import onde

    arq = onde.pagina(PAGINA)
    assert arq.exists(), f"a bancada não tem {PAGINA} — rode `python3 aba05.py`"
    return arq.read_text(encoding="utf-8")


def _bloco_do_lugar(html: str, pref: str) -> str:
    """O HTML de UM lugar da mesa, do `<div class="ctrl…">` até o próximo."""
    ate_a_faixa = html.split('class="vib-estado"', 1)[0]
    for pedaco in ate_a_faixa.split('<div class="ctrl')[1:]:
        achado = re.search(r'data-controle="(p\d+)"', pedaco.split(">", 1)[0])
        if achado and achado.group(1) == pref:
            return pedaco
    raise AssertionError(f"a bancada não tem o lugar {pref!r}")


def _ctx(policy: str = "balanceado"):
    """Um tique de mentira com dois controles — o pacote não toca o aparelho."""
    import pacotes

    conectados = [
        {"uniq": u, "player": i, "connected": True, "index": i - 1,
         "transport": "usb" if i == 1 else "bt", "battery_pct": 90, "inputs": {}}
        for i, u in enumerate(UNIQS, start=1)
    ]
    mesa = [{"pref": f"p{i}", "jogador": i, "uniq": u, "nome": "Régua",
             "via": "USB" if i == 1 else "BT", "cor": "starlight-blue",
             "plastico": "#123456", "conectado": True}
            for i, u in enumerate(UNIQS, start=1)]
    return pacotes.Contexto(
        state={"rumble_policy": policy, "rumble_mult_applied": 0.7,
               "active_profile": "regua"},
        mesa=mesa, conectados=conectados, estados={})


@pytest.fixture(scope="module")
def pacote():
    import pacotes

    return pacotes.pacote_da_pagina(PAGINA, _ctx())


def test_cada_degrau_diz_quem_ele_e(bancada) -> None:
    """Os quatro botões dividem UM `data-campo` e se distinguem pelo `quando`."""
    for _rot, chave in _aba05.FORCA:
        alvo = (f'data-campo="degrau" data-hef-alvo="classe" '
                f'data-hef-quando="{chave}"')
        assert alvo in bancada, f"o degrau {chave!r} não tem endereço de classe"

    # A CONTA É DOS DEGRAUS, e o filtro por `data-campo="degrau"` entrou em
    # vocabulário (`data-campo="lado-<sigla>" data-hef-alvo="classe"
    quandos = re.findall(
        r'data-campo="degrau" data-hef-alvo="classe" data-hef-quando="([^"]+)"',
        bancada)
    lugares = bancada.count('data-controle="p')
    # dela. Com quatro DualSense ligados o pacote manda quatro colunas e duas
    assert 'class="vib-mesa"' not in bancada, (
        "a linha de mesa voltou ao desenho da aba 05")
    assert lugares == len(_aba05.MESA), (
        f"a bancada tem {lugares} lugares e a mesa do desenho tem "
        f"{len(_aba05.MESA)}")
    esperado = len(_aba05.FORCA) * lugares
    assert len(quandos) == esperado, (
        f"são {len(_aba05.FORCA)} degraus em {lugares} "
        f"lugares = {esperado}, e achei "
        f"{len(quandos)}")
    assert set(quandos) == {c for _, c in _aba05.FORCA}, (
        f"os degraus endereçados não são os do produto: {sorted(set(quandos))}")


def test_o_degrau_nunca_e_nome_de_clique(bancada) -> None:
    """`degrau` é endereço de PINTURA; `forca` é endereço de CLIQUE."""
    assert 'data-papel="degrau"' not in bancada
    assert 'data-campo="forca"' not in bancada


def test_o_lugar_vazio_nao_acende_degrau_mas_tem_onde_receber(bancada) -> None:
    """Uma coluna sem controle não ACENDE degrau nenhum — e tem os três.

    ESTA RÉGUA INVERTEU EM 07/09/2026. Ela pedia que o bloco vazio não tivesse
    `data-campo="degrau"`, e era essa ausência o defeito: medido com os quatro
    DualSense dela na mesa, o daemon publicava os quatro, o pacote mandava as
    quatro colunas e o P3 e o P4 continuavam no travessão — o dado chegava e não
    tinha onde pousar (`hefesto_vivo._pintar` procura `data-campo` DENTRO do
    bloco daquele `data-controle`).

    O QUE CONTINUA PROIBIDO é a classe `on` cravada no HTML de nascença: um
    lugar sem controle não tem política para mostrar, e acender um degrau ali
    seria a mesma mentira noutro lugar. Quem some com o botão é a folha
    (`.ctrl[data-conectado="nao"] .seg > *{display:none}`), e `display:none` não
    recebe clique.

    A MORDIDA: tire o `conectado` do `if` que escolhe o estado em
    `aba05._coluna` (para o lugar vazio herdar `ESTADO[pref]`, que tem
    `propria=True` no p3) e a segunda asserção reprova.
    """
    vazios = [c["pref"] for c in _aba05.MESA if not c.get("conectado", True)]
    assert vazios, "a mesa do desenho não tem lugar vazio — não há o que medir"
    for pref in vazios:
        bloco = _bloco_do_lugar(bancada, pref)
        assert bloco.count('data-campo="degrau"') == len(_aba05.FORCA), (
            f"o lugar vazio {pref} não tem os {len(_aba05.FORCA)} degraus "
            f"endereçados — sem eles o degrau do controle que chegar ali não "
            f"tem onde pousar")
        assert '<button class="on"' not in bloco, (
            f"o lugar vazio {pref} nasceu com um degrau ACESO")


def test_o_pacote_emite_o_degrau_que_o_produto_calculou(pacote) -> None:
    """O valor é a CHAVE do produto, e ele sai do `app/telas/vibracao`.

    Não se calcula degrau aqui: `pacote_da_coluna` já monta `forca` a partir do
    `state_full.rumble_policy`. A interface só traduz o nome do campo.
    """
    colunas = pacote["colunas"]
    assert len(colunas) == 2, f"a mesa de mentira tem dois controles: {list(colunas)}"
    for uniq, col in colunas.items():
        assert col["degrau"] == "balanceado", (
            f"a coluna {uniq} não acendeu o degrau que está valendo — sem "
            f"ajuste próprio ela HERDA o da força geral, e herdar não é motivo "
            f"para a tela apagar os três botões")
        assert col["degrau-herdado"] == "1", (
            f"a coluna {uniq} acendeu {col['degrau']!r} sem dizer que é "
            f"HERDADO — aceso igual ao escolhido é a mentira que a decisão "
            f"[05] dela nasceu para matar")
    assert pacote["mesa"] == {}, (
        f"a mesa desta aba voltou a emitir {sorted(pacote['mesa'])}")
    assert {c for _, c in _aba05.FORCA} >= {"balanceado"}, (
        "o degrau emitido tem de ser uma das chaves do produto")


def test_o_degrau_emitido_e_sempre_um_dos_quatro() -> None:
    """Um token que nenhum botão conhece APAGA os quatro, calado."""
    import pacotes

    conhecidos = {c for _, c in _aba05.FORCA}
    for policy in sorted(conhecidos):
        pac = pacotes.pacote_da_pagina(PAGINA, _ctx(policy))
        assert pac["mesa"] == {}, (
            f"a mesa emitiu {sorted(pac['mesa'])!r} para a "
            f"política {policy!r}")
        for col in pac["colunas"].values():
            assert col["degrau"] in conhecidos | {""}, (
                f"o pacote emitiu {col['degrau']!r} para a política {policy!r}")


def test_a_mesa_sem_politica_nao_acende_degrau_nenhum() -> None:
    """Campo sem informação NÃO MOSTRA NADA — a regra dela, 02/09/2026."""
    import pacotes

    pac = pacotes.pacote_da_pagina(PAGINA, _ctx(policy=""))
    for col in pac["colunas"].values():
        assert col["degrau"] == "", f"o vazio virou {col['degrau']!r}"


def _campos(bancada: str, chave: str) -> list:
    return [c for c in _regua._campos_cravados(bancada) if c.chave == chave]


def test_a_regua_ve_os_oito_degraus_com_alvo_classe(bancada) -> None:
    """O parser da régua lê o mesmo endereço que o pintor escreve."""
    esperado = len(_aba05.FORCA) * len(_aba05.MESA)
    degraus = _campos(bancada, "degrau")
    assert len(degraus) == esperado, (
        f"a régua achou {len(degraus)} degraus, e são {esperado}")
    assert {c.alvo for c in degraus} == {"classe"}
    assert {c.quando for c in degraus} == {c for _, c in _aba05.FORCA}
    acesos = sorted(c.quando for c in degraus if c.valor)
    assert acesos == ["max"], (
        f"o desenho crava {acesos} — a cena tem UMA coluna com ajuste próprio "
        f"e UMA herdando, e é o que a decisão [05] existe para ensinar")
    assert not _campos(bancada, "degrau-mesa"), (
        "o `degrau-mesa` voltou ao desenho da aba 05")


def test_o_degrau_deixa_de_ser_desenho_quando_o_pacote_o_declara(bancada, pacote) -> None:
    """O veredito da régua sobre os quatro botões da coluna do P1."""
    cravados = [c for c in _regua._campos_cravados(bancada)
                if c.chave == "degrau" and c.dono == "p1"]
    declarados = {("p1", "degrau"): "balanceado"}
    vivos = ["balanceado" if c.quando == "balanceado" else "" for c in cravados]
    selos = [True] * len(cravados)
    vereditos = _regua._classificar(cravados, vivos, declarados, selos)
    classes = {v.classe for v in vereditos}
    assert classes == {_regua.PRODUTO}, (
        f"a régua ainda vê desenho nos degraus: "
        f"{[(v.campo.quando, v.classe, v.nota) for v in vereditos]}")


def test_a_regua_acusa_o_degrau_que_ninguem_conhece(bancada) -> None:
    """A MORDIDA de dentro: um token errado tem de ser ACUSADO, não perdoado."""
    cravados = [c for c in _regua._campos_cravados(bancada)
                if c.chave == "degrau" and c.dono == "p1"]
    vivos = ["" for _ in cravados]
    vereditos = _regua._classificar(
        cravados, vivos, {("p1", "degrau"): TOKEN_VIZINHO},
        [True] * len(cravados))
    assert any(v.classe == _regua.MOCKUP for v in vereditos), (
        "a régua deu verde sobre um grupo inteiramente apagado")


def test_a_largura_sai_sem_o_por_cento(pacote, bancada) -> None:
    """O alvo `largura` faz `el.style.width = valor + '%'` — o `%` é do pintor."""
    largura = {c.chave for c in _regua._campos_cravados(bancada)
               if c.alvo == "largura"}
    assert not largura, (
        f"voltou alvo `largura` a esta aba: {sorted(largura)} — as três barras "
        f"são `<input type=range>`, e o que o pintor escreve nelas é o `value`")
    for uniq, col in pacote["colunas"].items():
        for chave in ("motor-e-pct", "motor-d-pct", "forca-pct"):
            assert "%" not in str(col.get(chave, "")), (
                f"{uniq}·{chave} saiu {col[chave]!r} — o pintor acrescenta o `%`")


def test_os_dois_motores_tem_o_mesmo_destino(pacote) -> None:
    """`motor-e-pct` e `motor-d-pct` saem do MESMO laço, com a MESMA forma.

    A acusação de que só o esquerdo é endereço morto não sobrevive a isto: os
    dois são emitidos pelo mesmo `for` sobre `motores_do_controle`, com o mesmo
    `_barra` por trás. O que difere entre eles, na régua, é só o valor que o
    DESENHO cravou.
    """
    for uniq, col in pacote["colunas"].items():
        for lado in ("e", "d"):
            assert f"motor-{lado}-pct" in col, f"{uniq} não emite o motor {lado}"
            assert f"motor-{lado}" in col, f"{uniq} não emite o número do motor {lado}"
        assert col["motor-e-pct"] == col["motor-d-pct"], (
            "sem pedido de vibração fresco os dois lados respondem igual — "
            f"e saíram {col['motor-e-pct']!r} e {col['motor-d-pct']!r}")


def test_o_testar_de_cada_lugar_tem_endereco_de_estado(bancada) -> None:
    """O "Testar" acende pelo alvo `classe`, e diz o mesmo pelo `aria-pressed`."""
    lugares = bancada.count('data-controle="p')
    tags = re.findall(r'<button class="btn" data-papel="testar"[^>]*>', bancada)
    assert len(tags) == lugares, (
        f"a bancada tem {len(tags)} botões Testar para {lugares} lugares")
    for tag in tags:
        assert 'data-campo="em-teste"' in tag, tag
        assert 'data-hef-alvo="classe"' in tag, tag
        assert 'data-hef-atributo="aria-pressed"' in tag, (
            f"o Testar acende sem dizer a quem não vê a cor: {tag}")
        assert "data-hef-rotulo" not in tag, (
            f"o Testar voltou a ser só rótulo, e o estado dele some da régua: {tag}")
    assert ".acoes-col .btn.on{" in bancada, (
        "o Testar aceso não tem cor na folha da aba: a classe acende e nada muda")


def test_o_testar_acende_so_na_coluna_em_teste() -> None:
    """O campo `em-teste` vale `"1"` na coluna do teste ligado, e só nela."""
    import pacotes
    from pacotes import a05_vibracao as a05

    try:
        a05._EM_TESTE.add(UNIQS[1])
        colunas = pacotes.pacote_da_pagina(PAGINA, _ctx())["colunas"]
        assert {u: colunas[u].get("em-teste") for u in UNIQS} == {
            UNIQS[0]: "", UNIQS[1]: "1"}, colunas
        a05.parar_o_teste()
        colunas = pacotes.pacote_da_pagina(PAGINA, _ctx())["colunas"]
        assert {u: colunas[u].get("em-teste") for u in UNIQS} == {
            UNIQS[0]: "", UNIQS[1]: ""}, (
            "o Parar apagou a marca e a tela continuou acesa")
    finally:
        a05.parar_o_teste()


def test_a_recusa_do_clique_sem_degrau_pergunta_ao_dono(monkeypatch) -> None:
    """A frase que lista os degraus sai de `degraus_da_forca`, e não da escada."""
    from hefesto_dualsense4unix.app.telas import vibracao as tela
    from pacotes import a05_vibracao as a05

    assert a05._degraus_que_a_tela_oferece() == "Economia, Balanceado ou Máximo"
    monkeypatch.setattr(tela, "degraus_da_forca", lambda: ("max",))
    assert a05._degraus_que_a_tela_oferece() == "Máximo", (
        "a recusa do clique sem degrau deixou de perguntar ao dono dos degraus")


def test_os_degraus_do_dono_sao_os_botoes_da_tela() -> None:
    """`degraus_da_forca` devolve os três botões, na ordem da fileira desenhada."""
    from hefesto_dualsense4unix.app.telas import vibracao as tela

    assert tela.degraus_da_forca() == tuple(c for _, c in _aba05.FORCA)
    assert tela.FORCA_SEM_MULTIPLICADOR not in tela.degraus_da_forca()
