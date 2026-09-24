#!/usr/bin/env python3
"""O «Reconectar controles» não diz nada quando um número muda — 24/09/2026.

A-FRASE-DO-RECONECTAR-SAI-01. A decisão é dela, na página «Decisões do
Hefesto» (`D-2409-O-RECONECTAR-NAO-DIZ-NADA`): *«Nada: o número novo aparece no
próprio cartão»*. É o fim da proposta da JOGAR-02 (09/09/2026), que esperava o
olho dela.

O QUE ESTA RÉGUA COBRA, em quatro partes:

1. **a numeração que mudou não vira recado** — o gesto volta `None`, que é a
   piscada verde do botão, com o `renumbered` cheio ou vazio;
2. **as frases que pedem um gesto dela FICAM** — as duas falhas do passo 2, a
   recusa do passo 1 e as duas do rádio (passo 0). O rádio continua falando
   inteiro mesmo quando o passo 2 renumerou;
3. **a frase não volta** — o trecho está em `FRASES_BANIDAS`, e nenhuma das
   frases que ficam cai na lista: uma régua contra a frase que calasse as que
   pedem um gesto seria o defeito ao contrário;
4. **o cartão diz o número novo** — é a premissa da decisão. Se o cartão
   parasse de ler o número do `state`, o silêncio esconderia a mudança.

AS MORDIDAS, aplicadas na entrega (o relatório tem a saída de cada uma):

* devolva o `painel.py` da base (`git show 2b283c81a:<caminho>`) — a frase
  volta: reprovam as do item 1, o recibo direto e a guarda do fonte
  (`test_a_frase_que_ela_baniu_nao_chega_a_tela.test_nenhuma_banida_vive_no_fonte`);
* faça `painel._sem_noticia` devolver `False` para o `ok` — o sucesso vira uma
  falha que não houve, e reprovam as do item 1;
* tire `"foram renumerados"` de `FRASES_BANIDAS` — reprova a do item 3.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.app.actions.jogar import painel
from hefesto_dualsense4unix.integrations import gesto_de_reconexao as radio
from hefesto_dualsense4unix.interface.frases_que_ela_baniu import (
    FRASES_BANIDAS,
    primeiro_trecho_banido,
)
from pacotes import Contexto
from pacotes import a01_jogar as aba

#: A faixa sintética da casa — octetos 4 e 5 zerados, nunca endereço real.
UNIQ_P2 = "aa:bb:cc:00:00:02"
UNIQ_P3 = "aa:bb:cc:00:00:03"
RADIO_VOLTA = "aa:bb:cc:00:00:07"
RADIO_DORME = "aa:bb:cc:00:00:08"

#: O CORPO DE DELITO — a frase como o produto a dizia até 24/09/2026
#: (`painel._RENUMEROU`, formatada com dois assentos). Ela mora aqui, num texto
#: de TESTE, porque `app/actions/` e `interface/` não podem mais carregá-la.
FRASE_QUE_SAIU = "Os controles foram renumerados: P1, P2."

#: O QUE O DAEMON RESPONDE quando a numeração muda — a forma do
#: `_handle_identity_renumber`: só quem mudou volta, com o lugar novo.
MUDOU = {"ok": True, "renumbered": {UNIQ_P2: 1, UNIQ_P3: 2}}


class _Ponte:
    """O `ponte.resultado` de mentira — e NÃO mais frouxo que o real.

    O real levanta `RuntimeError` quando o daemon não atende, e o daemon não
    atende método que não conhece. Por isso um método que ninguém declarou
    levanta aqui também, em vez de devolver `None` calado.
    """

    def __init__(self, respostas: dict[str, Any]) -> None:
        self.respostas = respostas
        self.chamadas: list[str] = []

    def resultado(self, metodo: str, timeout: float | None = None, **_: Any) -> Any:
        self.chamadas.append(metodo)
        if metodo not in self.respostas:
            raise RuntimeError(f"o daemon não respondeu a {metodo}")
        valor = self.respostas[metodo]
        if isinstance(valor, Exception):
            raise valor
        return valor


def _ponte(renumber: Any) -> _Ponte:
    return _Ponte({
        "coop.sync": {"status": "ok", "players": 2, "active": True},
        "identity.renumber": renumber,
    })


def _ctx() -> Contexto:
    return Contexto(state={"connected": True}, mesa=[], conectados=[], estados={})


@pytest.fixture(autouse=True)
def _radio_sem_ninguem(monkeypatch: pytest.MonkeyPatch) -> None:
    """O passo 0 não vê rádio nenhum, a não ser que o caso diga o contrário.

    A suíte já recusa o barramento dela na borda (`bluez_dbus`); aqui o dono
    nem chega a ser perguntado, para o desfecho não depender da máquina.
    """
    monkeypatch.setattr(radio, "dualsenses_do_radio", lambda **_k: [])


# ---------------------------------------------------------------------------
# 1. a numeração que mudou não vira recado
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("renumber", [
    MUDOU,
    {"ok": True, "renumbered": {UNIQ_P3: 3}},
    {"ok": True, "renumbered": {}},
    {"ok": True},
], ids=["dois-mudaram", "um-mudou", "ja-compacta", "sem-renumbered"])
def test_a_numeracao_que_deu_certo_nao_vira_recado(renumber: dict[str, Any]) -> None:
    """O caso da decisão, e os vizinhos dele: todo `ok` volta sem recado.

    `None` é o que faz o piloto responder com a piscada verde no botão; um
    `{"recado": ""}` NÃO é o mesmo — ver o comentário do gesto em `a01_jogar`.
    """
    p = _ponte(renumber)
    fora = aba.reconectar(_ctx(), {}, p)
    assert p.chamadas == ["coop.sync", "identity.renumber"], p.chamadas
    assert fora is None, (
        f"o «Reconectar» renumerou e devolveu {fora!r}. A decisão dela "
        f"(D-2409-O-RECONECTAR-NAO-DIZ-NADA) é «Nada: o número novo aparece no "
        f"próprio cartão».")


@pytest.mark.parametrize(("resultado", "esperado"), [
    (MUDOU, ""),
    ({"ok": True, "renumbered": {}}, ""),
    ({"ok": False, "reason": "sessao_de_jogo_aberta"}, ""),
    ({"ok": False, "reason": "lock_timeout"}, painel._NAO_COMPACTOU),
    ({"ok": False}, painel._NAO_COMPACTOU),
    (None, painel._NAO_CONFERIU),
    ("não é um dicionário", painel._NAO_CONFERIU),
], ids=["mudou", "compacta", "jogo-aberto", "lock-timeout", "ok-falso",
        "sem-resposta", "resposta-torta"])
def test_o_recibo_cala_o_sucesso_e_diz_as_duas_falhas(resultado: Any, esperado: str) -> None:
    """O dono da frase, direto — e as duas funções dele dizem a mesma coisa.

    `_na_lingua_da_tela` é o dono que o mapa dos donos aponta
    (`docs/data/donos-de-comportamento.csv`, `reconciliar.recado`); chamá-lo
    sem passar pelo recibo não pode fazer um sucesso cair num ramo de falha.
    """
    assert painel.recibo_do_reconectar(None, resultado) == esperado
    assert painel._na_lingua_da_tela(resultado) == esperado
    assert painel._sem_noticia(resultado) is (esperado == "")


# ---------------------------------------------------------------------------
# 2. as frases que pedem um gesto dela FICAM
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(("renumber", "frase"), [
    (RuntimeError("o daemon não respondeu a identity.renumber"), painel._NAO_CONFERIU),
    ({"ok": False, "reason": "lock_timeout"}, painel._NAO_COMPACTOU),
], ids=["nao-conferiu", "nao-ajustou"])
def test_as_duas_falhas_do_passo_2_continuam_chegando(renumber: Any, frase: str) -> None:
    """*"Não consegui"* é o produto dizendo que não fez — e fica."""
    fora = aba.reconectar(_ctx(), {}, _ponte(renumber))
    assert fora == {"recado": frase}, fora


def test_a_recusa_do_passo_1_continua_levantando() -> None:
    """Sem o `coop.sync`, o botão recusa dizendo — e o passo 2 não corre."""
    p = _Ponte({"coop.sync": RuntimeError("o daemon não respondeu a coop.sync")})
    with pytest.raises(RuntimeError) as erro:
        aba.reconectar(_ctx(), {}, p)
    assert str(erro.value) == painel.RECONECTAR_SEM_SERVICO
    assert p.chamadas == ["coop.sync"], p.chamadas


def _radio_com_um_que_volta_e_um_que_dorme(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Dois DualSense que o BlueZ conhece e o daemon não vê: um volta, um dorme."""
    tocados: list[str] = []

    def _lista(**_k: Any) -> list[tuple[str, bool | None]]:
        return [(RADIO_VOLTA, True), (RADIO_DORME, False)]

    def _reconectar(mac: str, **_k: Any) -> Any:
        tocados.append(mac)
        if mac == RADIO_VOLTA:
            return radio.Resultado(radio.ESTADO_VOLTOU, radio.FRASE_VOLTOU, mac)
        return radio.Resultado(radio.ESTADO_SO_O_PS, radio.FRASE_SO_O_PS, mac)

    monkeypatch.setattr(radio, "dualsenses_do_radio", _lista)
    monkeypatch.setattr(radio, "reconectar", _reconectar)
    return tocados


def test_o_radio_continua_falando_quando_a_numeracao_muda(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """As duas frases do rádio pedem coisas diferentes dela, e as duas ficam.

    O recado é o do rádio INTEIRO e nada mais: a numeração que mudou no mesmo
    clique não pega carona nele.
    """
    tocados = _radio_com_um_que_volta_e_um_que_dorme(monkeypatch)
    fora = aba.reconectar(_ctx(), {}, _ponte(MUDOU))
    assert tocados == [RADIO_VOLTA, RADIO_DORME], tocados
    assert fora == {"recado": painel.recado_do_radio(1, 1)}, fora
    assert painel._VOLTARAM_PELO_RADIO.format(quantos=1) in fora["recado"]
    assert painel._ESPERAM_O_PS.format(quantos=1) in fora["recado"]


def test_o_radio_e_a_falha_saem_juntos_e_na_ordem(monkeypatch: pytest.MonkeyPatch) -> None:
    """O rádio vem na frente — é o que pede alguma coisa dela —, e a falha depois."""
    _radio_com_um_que_volta_e_um_que_dorme(monkeypatch)
    fora = aba.reconectar(
        _ctx(), {}, _ponte(RuntimeError("o daemon não respondeu a identity.renumber")))
    assert fora == {"recado": f"{painel.recado_do_radio(1, 1)} {painel._NAO_CONFERIU}"}, fora


# ---------------------------------------------------------------------------
# 3. a frase não volta — e a lista não cala as que ficam
# ---------------------------------------------------------------------------
def test_a_frase_que_saiu_esta_na_lista_das_banidas() -> None:
    """O trecho pega a frase como ela era, e com outros assentos também."""
    assert "foram renumerados" in FRASES_BANIDAS, (
        "a frase do «Reconectar» saiu da lista das banidas — nada mais a "
        "impede de voltar por este gesto ou por outro (D-2409-O-RECONECTAR-NAO-DIZ-NADA)")
    assert primeiro_trecho_banido(FRASE_QUE_SAIU) == "foram renumerados"
    assert primeiro_trecho_banido(
        "Os controles foram renumerados: P2, P3 e P4.") == "foram renumerados"


def test_nenhuma_frase_que_fica_cai_na_lista() -> None:
    """A régua contra a frase não pode calar as que pedem um gesto dela.

    O funil de execução (`hefesto_vivo._json`) e a guarda do fonte leem a
    MESMA lista: um trecho largo demais denunciaria no diário, e reprovaria no
    fonte, uma frase medida e viva — foi o que o ``"como no PS5"`` faria em
    06/09/2026.
    """
    que_ficam = {
        "_NAO_CONFERIU": painel._NAO_CONFERIU,
        "_NAO_COMPACTOU": painel._NAO_COMPACTOU,
        "RECONECTAR_SEM_SERVICO": painel.RECONECTAR_SEM_SERVICO,
        "recado_do_radio(1, 1)": painel.recado_do_radio(1, 1),
        "recado_do_radio(4, 0)": painel.recado_do_radio(4, 0),
        "recado_do_radio(0, 4)": painel.recado_do_radio(0, 4),
    }
    pegas = {nome: primeiro_trecho_banido(frase) for nome, frase in que_ficam.items()}
    assert not any(pegas.values()), f"a lista das banidas pegou frase que fica: {pegas}"


# ---------------------------------------------------------------------------
# 4. o cartão diz o número novo — a premissa da decisão
# ---------------------------------------------------------------------------
def _contexto_com(slots: dict[str, int]) -> Contexto:
    from hefesto_dualsense4unix.interface import mesa_viva

    conectados = [
        {"uniq": uniq, "connected": True, "player": slot, "player_slot": slot,
         "transport": transporte}
        for (uniq, slot), transporte in zip(slots.items(), ("usb", "bt"), strict=True)
    ]
    state = {"connected": True, "native_mode": False, "paused": False,
             "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
             "controllers": conectados}
    return Contexto(state=state, mesa=mesa_viva.mesa_do_estado(state, {}),
                    conectados=conectados, estados={})


def test_o_cartao_diz_o_numero_novo_no_tique_seguinte() -> None:
    """O P2 e o P3 viram P1 e P2, e o cartão de cada um diz o número novo.

    É o que torna a frase dispensável: o número mora no cartão, lido do
    `state` do daemon a cada tique (`a01_jogar.pacote`, a chave `jogador`).
    """
    antes = aba.pacote(_contexto_com({UNIQ_P2: 2, UNIQ_P3: 3}))["cartoes"]
    depois = aba.pacote(_contexto_com({UNIQ_P2: 1, UNIQ_P3: 2}))["cartoes"]
    assert {u: c["jogador"] for u, c in antes.items()} == {
        UNIQ_P2: "Player 2", UNIQ_P3: "Player 3"}, antes
    assert {u: c["jogador"] for u, c in depois.items()} == {
        UNIQ_P2: "Player 1", UNIQ_P3: "Player 2"}, (
        "o cartão não mostrou o número novo — sem ele, o silêncio da decisão "
        "D-2409-O-RECONECTAR-NAO-DIZ-NADA esconderia a mudança")
