#!/usr/bin/env python3
"""A ABA VIBRAÇÃO: a «Força» é o trilho que o daemon move, e a largura sai sem `%`.

A FORÇA SAIU DOS DEGRAUS EM 20/10/2026 (A-INTENSIDADE-DA-VIBRACAO-E-DO-GATILHO-SAI-DO-FIRMWARE-COMO-
NO-PS5-01): a «Força da vibração» é um trilho de 0 a 200%, de 5 em 5, por controle, sem os botões
Economia, Padrão e Máximo. O pacote deixou de pintar `degrau` e `degrau-herdado`, e as réguas que
mediam os quatro botões na página publicada saíram com eles (o `--publicar 05` da costura os tira
da página). Fica o que o trilho herdou delas: o número vem do daemon (a política e o multiplicador
aplicado que o tique publica), e campo sem informação não mostra nada.

**``motor-e-pct`` NÃO É ENDEREÇO MORTO** (02/09/2026): o alvo ``largura`` do ``escrever()`` faz
``el.style.width = valor + '%'``, e quem emite escreve o número PELADO. Hoje as três barras são
``<input type=range>``, e a régua cobra que o alvo ``largura`` não volte.

A MORDIDA:

* devolva ``"degrau"`` ao plano do ``a05_vibracao.pacote`` e
  ``test_o_pacote_pinta_o_trilho_e_nao_o_degrau`` reprova;
* troque o ``mult-pos`` do plano por um número fixo e a mesma régua reprova nas quatro políticas;
* devolva o ``%`` ao ``forca-pct`` e ``test_a_largura_sai_sem_o_por_cento`` reprova.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))


from hefesto_dualsense4unix.interface import aba05 as _aba05
from hefesto_dualsense4unix.interface import regua_do_mockup as _regua

PAGINA = "05-vibracao.html"

UNIQS = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02")

@pytest.fixture(scope="module")
def bancada() -> str:
    import onde

    arq = onde.pagina(PAGINA, publicado=True)
    assert arq.exists(), f"o publicado não tem {PAGINA}"
    return arq.read_text(encoding="utf-8")


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


#: o número que o trilho mostra em cada política do produto (o `RUMBLE_POLICY_MULT` em porcento,
#: e o multiplicador aplicado de 0,7 do tique de mentira no personalizado)
NO_TRILHO = {"economia": "30", "balanceado": "100", "max": "150", "custom": "70"}


@pytest.mark.parametrize(("policy", "numero"), sorted(NO_TRILHO.items()))
def test_o_pacote_pinta_o_trilho_e_nao_o_degrau(policy: str, numero: str) -> None:
    """O cursor e o número do trilho vêm da política do daemon; degrau não se pinta mais.

    A prova da D-2010-O-HERDADO-SAI-COM-OS-DEGRAUS.
    """
    import pacotes

    from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT

    if policy in RUMBLE_POLICY_MULT:
        assert numero == str(round(RUMBLE_POLICY_MULT[policy] * 100)), "a régua saiu do produto"
    pac = pacotes.pacote_da_pagina(PAGINA, _ctx(policy))
    assert pac["mesa"] == {}, f"a mesa desta aba voltou a emitir {sorted(pac['mesa'])}"
    assert len(pac["colunas"]) == 2, f"a mesa de mentira tem dois controles: {list(pac['colunas'])}"
    for uniq, col in pac["colunas"].items():
        assert "degrau" not in col and "degrau-herdado" not in col, (
            f"a coluna {uniq} voltou a pintar o degrau: a Força é o trilho, sem botões")
        assert col["mult-pos"] == col["mult"] == numero, (
            f"{uniq} com {policy!r} pôs o cursor em {col['mult-pos']!r} e o número em "
            f"{col['mult']!r}; o daemon diz {numero}")


def test_a_mesa_sem_politica_nao_poe_o_cursor_em_lugar_nenhum() -> None:
    """Campo sem informação NÃO MOSTRA NADA — a regra, 02/09/2026."""
    import pacotes

    pac = pacotes.pacote_da_pagina(PAGINA, _ctx(policy=""))
    for col in pac["colunas"].values():
        assert col["mult-pos"] == "" and col["mult"] == "—", (col["mult-pos"], col["mult"])


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


def test_os_degraus_do_dono_sao_os_botoes_da_tela() -> None:
    """`degraus_da_forca` devolve os três botões, na ordem da fileira desenhada."""
    from hefesto_dualsense4unix.app.telas import vibracao as tela

    assert tela.degraus_da_forca() == tuple(c for _, c in _aba05.FORCA)
    assert tela.FORCA_SEM_MULTIPLICADOR not in tela.degraus_da_forca()
