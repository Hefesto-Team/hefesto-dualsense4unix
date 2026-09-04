#!/usr/bin/env python3
"""A ABA VIBRAÇÃO: barra sem número é a mentira mais barata desta tela.

**O OLHO LÊ A BARRA, NÃO O TRAVESSÃO.** Esta aba tem seis trilhos por coluna
(o multiplicador e os dois motores, e o par número/largura em cada um), e o
número é quem diz se a largura pode ser afirmada. Um ``—`` ao lado de um trilho
cheio não é meia informação: é informação errada, porque quem olha lê o
comprimento primeiro.

**MEDIDO NO DOM VIVO em 03/09/2026**, com a mesa dela (um DualSense White no
cabo), pela ``scripts/ensaios/a_coluna_sem_controle_da_vibracao.py``::

    lugar  identidade          mult/mult-pos    motor-e/motor-e-pct  motor-d/…
    p1     P1 · White · USB      100%/100            —/0%                —/0%
    p2     —                       —/                —/47.1%             —/47.1%

**A COLUNA DO MEIO MUDOU DE CONTRATO EM 03/09/2026**, decisão dela: a linha do
multiplicador virou um ``<input type=range>``, e o que o pintor escreve nela
deixou de ser a LARGURA (``forca-pct``, uma fração de 0 a 100) e passou a ser a
POSIÇÃO (``mult-pos``, o número de 0 ao teto). A medição acima está reescrita
com os nomes de hoje; o que ela mediu — o par número/trilho contando a mesma
história — não mudou.

A coluna do controle DELA está honesta: os motores não sabem, e os trilhos vão
a zero. É essa metade que este arquivo guarda, e ela é do pacote desta aba —
``_barra`` devolve ``w = "0%"`` junto com ``n = "—"``, e o pacote repassa os
dois.

A OUTRA METADE NÃO É DAQUI, e fica dita para ninguém procurar a cura no lugar
errado: a coluna ``p2`` é um lugar que o desenho fez CONECTADO
(``monta.MESA``) e que a mesa de hoje não preenche. Quem a apaga é
``pacotes.apagar_os_lugares_sem_dono``, que escreve o travessão em TODAS as
chaves das colunas vivas — inclusive nas três de alvo ``largura``, que o
``molde_do_lugar`` do mesmo módulo exclui de propósito (``width: "—%"`` o CSSOM
recusa, e o trilho fica com a largura do mockup). O defeito está no arquivo
compartilhado, não nesta aba, e está no relato da frente.

AS MORDIDAS, todas com ``cp`` para devolver — nunca ``git checkout --``:

* em ``a05_vibracao.pacote``, troque ``str(m.get("w", "")).rstrip("%")`` por
  ``""`` → ``test_todo_trilho_desta_aba_sai_com_numero`` reprova dizendo que
  ``motor-e-pct`` não é número;
* apague a linha do ``forca-pct`` do pacote (a ponte de publicação) → o mesmo
  caso reprova, e é o defeito que ELE já teve na tela dela: o trilho do
  multiplicador congelado na largura do mockup;
* emita ``pct["w"]`` em ``mult-pos`` →
  ``test_a_posicao_do_multiplicador_cabe_na_barra`` reprova no ``max``, onde a
  fração (75) e o número (150) divergem;
* troque o ``"0"`` que ``_barra`` devolve no desconhecido por ``"66.7"`` →
  ``test_o_que_nao_se_sabe_manda_o_trilho_a_zero`` reprova nos três pares;
* apague ``id="vib-estado"`` da página publicada →
  ``test_a_linha_do_estado_chegou_ao_produto`` reprova.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.app.telas import vibracao as _tela

PAGINA = "05-vibracao.html"

#: MAC da faixa SINTÉTICA da casa — há dois portões de anonimato nesta árvore.
UNIQS = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02")

#: O PAR NÚMERO → TRILHO desta aba. Os nomes são os do pacote, e o par é o
#: contrato: cada largura tem um número ao lado, e é o número que manda.
#:
#: **CONTINUAM TRÊS, e o do multiplicador é a PONTE DE PUBLICAÇÃO — 03/09/2026.**
#: No desenho novo a linha do multiplicador virou um `<input type=range>` (a
#: decisão dela: *"0 a 200%, e grava na hora"*), e ali o pintor escreve o VALOR,
#: não a largura. Mas publicar é ato dela: a página que ela ABRE hoje ainda tem
#: o `<span class="cheio">`, e o `forca-pct` é o único endereço que ele tem.
#:
#: TIRÁ-LO CUSTOU UMA FOTO, e por isso ele está de volta nesta lista: com
#: `mult-pos` sozinho, o clique em "Economia" trocou o número de `100%` para
#: `30%` na tela dela e o trilho FICOU ONDE ESTAVA, com a largura que o mockup
#: cravou. Os dois endereços convivem enquanto a `05-vibracao` estiver em
#: `mockup/DIVERGENCIAS.md`.
PARES = (("mult", "forca-pct"), ("motor-e", "motor-e-pct"),
         ("motor-d", "motor-d-pct"))

#: O PAR NÚMERO → POSIÇÃO do multiplicador, que é o outro contrato — o da
#: bancada. A faixa dele não é 0-100: é 0-`teto_da_barra()`.
PAR_DO_MULTIPLICADOR = ("mult", "mult-pos")


def _ctx(policy: str = "balanceado", *, per_vpad: list | None = None):
    """Um tique de mentira com dois controles — o pacote não toca o aparelho."""
    import pacotes

    conectados = [
        {"uniq": u, "player": i, "connected": True, "index": i - 1,
         "is_primary": i == 1, "transport": "usb" if i == 1 else "bt",
         "battery_pct": 90, "inputs": {}}
        for i, u in enumerate(UNIQS, start=1)
    ]
    mesa = [{"pref": f"p{i}", "jogador": i, "uniq": u, "nome": "Régua",
             "via": "USB" if i == 1 else "BT", "cor": "starlight-blue",
             "plastico": "#123456", "conectado": True}
            for i, u in enumerate(UNIQS, start=1)]
    estado = {
        "rumble_policy": policy,
        "rumble_mult_applied": 0.7,
        "active_profile": "regua",
        "rumble_ff": {"plays": 0, "nao_nulos": 0, "vpads": len(per_vpad or []),
                      "per_vpad": per_vpad or []},
    }
    return pacotes.Contexto(state=estado, mesa=mesa, conectados=conectados,
                            estados={})


def _colunas(policy: str = "balanceado", *, per_vpad: list | None = None) -> dict:
    import pacotes

    pac = pacotes.pacote_da_pagina(PAGINA, _ctx(policy, per_vpad=per_vpad)) or {}
    colunas = pac.get("colunas") or {}
    assert colunas, "o pacote não montou coluna nenhuma — a régua mediria o vazio"
    return colunas


@pytest.fixture(scope="module")
def publicado() -> str:
    """A página que o produto RENDERIZA. Não a bancada: a pergunta aqui é se a
    cura CHEGOU nela."""
    import onde

    arq = onde.PUBLICADO / PAGINA
    assert arq.exists(), f"a página publicada sumiu: {arq}"
    return arq.read_text(encoding="utf-8")


def _numero(largura: str) -> float:
    """A largura como número. Levanta se não for — que é o ponto da régua."""
    return float(str(largura).rstrip("%"))


# --------------------------------------------------------------------------
# 1. toda largura é um número, sempre
# --------------------------------------------------------------------------
@pytest.mark.parametrize("policy", ["economia", "balanceado", "max", "auto"])
def test_todo_trilho_desta_aba_sai_com_numero(policy: str) -> None:
    """O pacote nunca manda ao trilho algo que o CSSOM recuse.

    O ramo ``largura`` do pintor faz ``el.style.width = t + '%'``. Um valor que
    não seja número — ``""``, ``"—"`` — é recusado pelo CSSOM **em silêncio**: a
    barra fica com a largura que o desenho cravou e a tela passa a afirmar um
    comprimento que ninguém mediu. Não há erro, não há aviso; só a barra errada.
    """
    for uniq, col in _colunas(policy).items():
        for _num, larg in PARES:
            assert larg in col, f"{uniq}: o pacote deixou de emitir {larg}"
            try:
                valor = _numero(col[larg])
            except ValueError:
                pytest.fail(
                    f"{uniq}: {larg} saiu {col[larg]!r}, que não é número — o "
                    f"CSSOM recusa e o trilho fica com a largura do mockup")
            assert 0.0 <= valor <= 100.0, (
                f"{uniq}: {larg} saiu {valor}, fora da faixa de 0 a 100")


@pytest.mark.parametrize("policy", ["economia", "balanceado", "max", "auto"])
def test_a_posicao_do_multiplicador_cabe_na_barra(policy: str) -> None:
    """O `value` de um `<input type=range>` é o NÚMERO, não a fração.

    O ramo `valor` do pintor faz `el.value = t`. Um valor fora de
    `[min, max]` o navegador GRAMPEIA no extremo mais perto, calado: o polegar
    para na ponta e a tela afirma um pedido que ninguém fez. E escrever ali a
    LARGURA (`pct["w"]`, que é `100 * valor / teto`) poria o cursor em 75
    quando o pedido é 150.

    MORDIDA: em `a05_vibracao.pacote`, emita `pct["w"]` em `mult-pos` — este
    caso reprova no `max`, onde a fração (75) e o número (150) divergem.
    """
    from pacotes import a05_vibracao as a05

    num, pos = PAR_DO_MULTIPLICADOR
    teto = a05.teto_da_barra()
    for uniq, col in _colunas(policy).items():
        assert pos in col, f"{uniq}: o pacote deixou de emitir {pos}"
        valor = _numero(col[pos])
        assert 0.0 <= valor <= teto, (
            f"{uniq}: {pos} saiu {valor}, fora da faixa de 0 a {teto} — o "
            f"navegador grampearia o polegar na ponta, calado")
        assert str(col[num]).rstrip("%") == col[pos], (
            f"{uniq}: o número diz {col[num]!r} e o cursor está em {col[pos]!r} "
            f"— a mesma linha contando duas histórias")


# --------------------------------------------------------------------------
# 2. o que não se sabe manda o trilho a ZERO
# --------------------------------------------------------------------------
def test_o_que_nao_se_sabe_manda_o_trilho_a_zero() -> None:
    """Número ``—`` e trilho a zero andam JUNTOS, ou a tela mente.

    A mesa parada é o caso mais comum na bancada dela: ninguém pediu vibração,
    ``per_vpad`` está vazio e ``motores_do_controle`` responde ``None`` nos dois
    lados — *"nada a dizer"*, que nunca é zero. O número vira travessão; a
    largura tem de ir a zero, porque uma barra é uma AFIRMAÇÃO de quantidade e
    "não sei" não afirma nenhuma.

    O MULTIPLICADOR SEGUE OUTRA REGRA desde 03/09/2026, e ela é do elemento: a
    linha dele virou um ``<input type=range>``, e ``0`` ali não é "não sei" — é
    *"nenhuma vibração"*, uma escolha que ela pode ter feito. Um zero escrito no
    desconhecido seria a barra afirmando silêncio. O pacote manda ``""``, o
    pintor o troca por travessão, o navegador recusa e o cursor fica onde
    estava — e o número ao lado diz ``—`` no mesmo tique.
    """
    colunas = _colunas("uma-politica-que-o-produto-nao-conhece", per_vpad=[])
    vistos = 0
    for uniq, col in colunas.items():
        for num, larg in PARES:
            if col.get(num) != _tela.NAO_SEI:
                continue
            vistos += 1
            assert _numero(col[larg]) == 0.0, (
                f"{uniq}: {num} diz {_tela.NAO_SEI!r} e {larg} afirma "
                f"{col[larg]!r} — o olho lê a barra, não o travessão")
    assert vistos == len(PARES) * len(colunas), (
        f"a régua só encontrou {vistos} pares desconhecidos, e esperava "
        f"{len(PARES) * len(colunas)}: sem eles ela ficaria verde por vacuidade")

    num, pos = PAR_DO_MULTIPLICADOR
    for uniq, col in colunas.items():
        assert col.get(num) == _tela.NAO_SEI, (
            f"{uniq}: uma política que o produto não conhece devolveu "
            f"{col.get(num)!r} — a régua mediria o vazio")
        assert col.get(pos) == "", (
            f"{uniq}: {num} diz {_tela.NAO_SEI!r} e {pos} afirma {col[pos]!r} — "
            f"um número ali põe o cursor num lugar que ninguém escolheu")


# --------------------------------------------------------------------------
# 3. a linha do estado CHEGOU ao produto — o fato que estava errado no pacote
# --------------------------------------------------------------------------
def test_a_linha_do_estado_chegou_ao_produto(publicado: str) -> None:
    """O bloco ``#vib-estado`` está na página que ela abre, não só na bancada.

    O pacote afirmava por escrito que este seletor *"só existe na BANCADA até ela
    publicar"* e que na publicada o ``querySelector`` devolvia ``null``. Era
    verdade quando foi escrito e deixou de ser quando ela publicou a aba —
    enquanto ficou lá, ensinava que a ÚNICA linha de texto desta tela não
    chegava ao produto.

    ``.est.info`` entra junto porque é o tom da quarta frase (a confissão de onde
    se grava), e o CSV dizia, na mesma data, que ele *"ficou para trás na
    publicação"*. Os dois estão publicados; esta régua é o que impede as duas
    afirmações de voltarem.
    """
    assert 'id="vib-estado"' in publicado, (
        "o bloco da linha de estado não está na página publicada — a aba voltou "
        "a não ter uma palavra sobre o que acontece com a vibração")
    assert ".est.info" in publicado, (
        "o tom `info` da linha de estado não está no CSS publicado — a confissão "
        "de onde se grava nasceria sem cor")


def test_o_bloco_do_estado_e_o_que_o_pacote_manda(publicado: str) -> None:
    """O seletor que o pacote endereça é o que a página publica.

    Um seletor que o pacote escreve e a página não tem é pintura contada sobre
    nada: o laço do bootstrap acha ``null`` e segue, sem erro. As duas pontas
    conferidas juntas é o que impede isso.
    """
    import pacotes

    pac = pacotes.pacote_da_pagina(PAGINA, _ctx()) or {}
    blocos = pac.get("blocos") or {}
    assert blocos, "o pacote parou de emitir a linha de estado"
    for seletor in blocos:
        assert seletor.startswith("#"), f"seletor inesperado: {seletor!r}"
        assert f'id="{seletor[1:]}"' in publicado, (
            f"o pacote pinta {seletor!r} e a página publicada não o tem")
