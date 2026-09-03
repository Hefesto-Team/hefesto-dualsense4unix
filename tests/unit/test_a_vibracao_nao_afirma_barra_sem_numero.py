#!/usr/bin/env python3
"""A ABA VIBRAÇÃO: barra sem número é a mentira mais barata desta tela.

**O OLHO LÊ A BARRA, NÃO O TRAVESSÃO.** Esta aba tem seis trilhos por coluna
(o multiplicador e os dois motores, e o par número/largura em cada um), e o
número é quem diz se a largura pode ser afirmada. Um ``—`` ao lado de um trilho
cheio não é meia informação: é informação errada, porque quem olha lê o
comprimento primeiro.

**MEDIDO NO DOM VIVO em 03/09/2026**, com a mesa dela (um DualSense White no
cabo), pela ``scripts/ensaios/a_coluna_sem_controle_da_vibracao.py``::

    lugar  identidade          mult/forca-pct   motor-e/motor-e-pct  motor-d/…
    p1     P1 · White · USB      100%/66.7%          —/0%                —/0%
    p2     —                       —/66.7%           —/47.1%             —/47.1%

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

* em ``a05_vibracao.pacote``, troque ``str(pct.get("w", "")).rstrip("%")`` por
  ``""`` → ``test_todo_trilho_desta_aba_sai_com_numero`` reprova dizendo que
  ``forca-pct`` não é número;
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
PARES = (("mult", "forca-pct"), ("motor-e", "motor-e-pct"),
         ("motor-d", "motor-d-pct"))


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

    O degrau desconhecido cobre o mesmo par do multiplicador: uma política que o
    produto não conhece devolve ``None`` em ``_pedido_da_politica``.
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
