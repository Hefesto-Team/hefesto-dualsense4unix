"""O pareamento que não chega devolve os botões — O-RADIO-CONECTA-ONDE-ELA-MANDA-01.

Os relatos dela de 26/09/2026:

    *«Ficou com a mensagem esperando por eternidade (…) e os botões ficaram
    desabilitados sem resposta nenhuma. Travou num estado morto.»*
    <!-- noqa-acento: citação literal dela -->

    *«precisamos de um X do lado de cada controle, pra poder remover o pareamento
    dele»* (item 3) <!-- noqa-acento: citação literal dela -->

E o controle BRANCO (item 5), MEDIDO no ``radio-diario.jsonl`` dela: o ``Pair``
deu, a busca de serviços caiu em ``Host is down``, e ele ficou ``Paired`` sem
nunca ficar ``Connected`` — um pareamento pela metade no adaptador, e a tela
esperando PS + Create para sempre.

O que esta régua segura, sempre com o rádio de mentira de três adaptadores:

1. o «esperando» segura a tela por :data:`ESPERA_NA_TELA_S` — o prazo da
   central, ``central_do_radio.PRAZO_DO_PENDENTE_S``, desde 26/09/2026 — e NÃO MAIS —
   depois disso a linha diz «Não Conectou», e «Tentar de Novo» e o X aparecem;
2. a busca que ninguém respondeu vira «Não Conectou» sem aparelho, e o X só
   tira a linha (não há pareamento a esquecer);
3. o branco — ``Pair`` que dá e controle que não conecta — perde a meia chave
   SÓ naquele adaptador, e «Tentar de Novo» abre outro «Conectar» no mesmo;
4. o controle que o ``Pair`` já conecta não recebe ``Connect`` (item 5b: o
   ``Connect`` fica para quando ele não está no ar);
5. o X esquece o controle ligado ou desligado SÓ no adaptador da linha.

Faixa sintética da casa: ``aa:bb:cc``, octetos 4 e 5 zerados.
"""

from __future__ import annotations

import re
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import central_do_radio as cr
from tests.unit import radio_de_mentira as rm
from tests.unit.radio_de_mentira import (
    AZUL,
    FONE,
    QUARTO,
    ROXO,
    SALA,
    VARANDA,
    VERDE,
    VERMELHO,
)
from tests.unit.test_o_conectar_pareia_no_adaptador_escolhido import (
    Bancada,
    ela_segura_ps_create,
    id_da_tela,
    mundo_da_madrugada,
    onde_buscou,
    onde_pareou,
    preparar_a_tela,
    preparar_o_diario,
)


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return preparar_o_diario(tmp_path, monkeypatch)


@pytest.fixture()
def a08(monkeypatch: pytest.MonkeyPatch) -> Any:
    return preparar_a_tela(monkeypatch)


def _com_a_central(bancada: Bancada, monkeypatch: pytest.MonkeyPatch,
                   *movimentos: cr.Movimento) -> None:
    """O ``radio_central`` publicado com ESTES movimentos (a hora de parede é a
    que a régua quer), e os controles da mesa como o daemon publicaria."""
    real = bancada.estado

    def estado() -> dict[str, Any]:
        st = real()
        st["radio_central"] = {"movimentos": [m.publicar() for m in movimentos],
                               "em_curso": any(m.em_curso for m in movimentos),
                               "proposta": None}
        return st

    monkeypatch.setattr(bancada, "estado", estado)


def _linhas(cena: dict[str, Any], lugar: str, **marca: Any) -> list[dict[str, Any]]:
    return [a for a in cena["aparelhos"] if a.get("lugar") == id_da_tela(lugar)
            and all(a.get(k) == v for k, v in marca.items())]


# ---------------------------------------------------------------------------
# 1. o «esperando» segura a tela pelo prazo da central, e não mais
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("destino", (SALA, QUARTO, VARANDA))
def test_o_esperando_segura_a_tela_pelo_prazo_da_central_e_nao_mais(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, destino: str,
) -> None:
    """Um segundo antes do prazo a janela ainda é dela: a tela está ocupada, a
    caixa do destino aberta, e nada de «Não Conectou». Um segundo depois os
    botões voltam: a linha diz
    «Não Conectou», com «Tentar de Novo» NAQUELE adaptador e o X — e o próximo
    «Conectar» vai para onde ela abrir, não mais para a janela morta.

    O PRAZO É UM SÓ desde 26/09/2026 (A-GESTAO-DOS-CONTROLES-NO-PRODUTO-01):
    a tela lê o da central (``ESPERA_NA_TELA_S = PRAZO_DO_PENDENTE_S``), e era
    de 60 s contra os 120 s dela — a zona morta da régua do contrato abaixo.

    MORDIDA: tire a idade de ``_ainda_espera`` (o «esperando» vale para sempre)
    — o caso de depois do prazo reprova, que é o «estado morto» dela.
    """
    assert a08.ESPERA_NA_TELA_S == cr.PRAZO_DO_PENDENTE_S, (
        "a tela e a central voltaram a ter dois prazos")
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        agora = time.time()
        _com_a_central(bancada, monkeypatch, cr.Movimento(
            "", destino, cr.ESPERANDO, cr.PASSO_GESTO,
            quando=agora - (a08.ESPERA_NA_TELA_S - 1.0)))
        cena = bancada.cena()
        assert cena["ocupado"] is True
        assert cena["aberto"] == id_da_tela(destino)
        assert cena["destino_do_conectar"] == id_da_tela(destino)
        assert not _linhas(cena, destino, nao_conectou=True)
        with pytest.raises(RuntimeError):
            bancada.gesto("conectar-aparelho")

        _com_a_central(bancada, monkeypatch, cr.Movimento(
            "", destino, cr.ESPERANDO, cr.PASSO_GESTO,
            quando=agora - (a08.ESPERA_NA_TELA_S + 1.0)))
        sala = bancada.tique()["radio-sala"]
        cena = dict(a08._CENA_NA_TELA)
        assert cena["ocupado"] is False, "a janela morta segurou a tela depois do prazo"
        (linha,) = _linhas(cena, destino, nao_conectou=True)
        assert linha["aparelho"] == ""
        assert "Não Conectou" in sala
        assert f'data-gesto="tentar-de-novo" data-alvo="{id_da_tela(destino)}"' in sala
        assert (f'data-gesto="esquecer-aparelho" data-alvo="{linha["id"]}" '
                f'data-lugar="{id_da_tela(destino)}"') in sala
        assert cena["aberto"] == id_da_tela(destino), "a caixa de quem não chegou fechou"

        # Ela abre outra caixa: o «Conectar» vai para lá, não para a janela morta.
        outro = next(e for e in (SALA, QUARTO, VARANDA) if e != destino)
        bancada.gesto("abrir-adaptador", alvo=id_da_tela(outro))
        assert bancada.cena()["destino_do_conectar"] == id_da_tela(outro)
    finally:
        bancada.fechar()


def test_com_a_janela_aberta_o_x_treme(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O X segue o um-por-vez do «Mover»: com um controle esperando PS + Create
    noutro adaptador, o X do vermelho treme e nada sai do rádio."""
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        _com_a_central(bancada, monkeypatch, cr.Movimento(
            "", QUARTO, cr.ESPERANDO, cr.PASSO_GESTO, quando=time.time()))
        bancada.cena()
        vermelho = {"alvo": rm.uniq(VERMELHO), "lugar": id_da_tela(SALA)}
        with pytest.raises(RuntimeError):
            bancada.gesto("esquecer-aparelho", **vermelho)
        with pytest.raises(RuntimeError):
            bancada.gesto("confirmar-esquecer", **vermelho)
        assert mundo.metodos("RemoveDevice") == [] and mundo.lapides == []
    finally:
        bancada.fechar()


# ---------------------------------------------------------------------------
# 2. a busca que ninguém respondeu
# ---------------------------------------------------------------------------


def test_a_busca_que_ninguem_respondeu_vira_nao_conectou_e_o_x_tira_a_linha(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ela abre a varanda, clica «Conectar», e não segura PS + Create: a central
    fecha a janela com «não chegou», e a linha da varanda diz «Não Conectou».
    O X não tem pareamento a esquecer — ele tira a linha, e nada sai do rádio."""
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        bancada.cena()
        bancada.gesto("abrir-adaptador", alvo=id_da_tela(VARANDA))
        bancada.cena()
        bancada.gesto("conectar-aparelho")
        bancada.esperar_a_central()
        (feito,) = bancada.central.movimentos()
        assert (feito.estado, feito.destino) == (cr.NAO_CHEGOU, VARANDA)

        cena = bancada.cena()
        (linha,) = _linhas(cena, VARANDA, nao_conectou=True)
        assert linha["aparelho"] == "" and linha["meia_chave"] is False
        assert cena["ocupado"] is False and cena["aberto"] == id_da_tela(VARANDA)

        assert bancada.gesto("esquecer-aparelho", alvo=linha["id"],
                             lugar=id_da_tela(VARANDA)) == {"armou": True}
        assert not _linhas(bancada.cena(), VARANDA, nao_conectou=True)
        assert mundo.metodos("RemoveDevice") == [] and mundo.lapides == []
    finally:
        bancada.fechar()


# ---------------------------------------------------------------------------
# 3. o controle branco: o Pair dá e ele não conecta
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("destino", (SALA, QUARTO, VARANDA))
def test_o_branco_perde_a_meia_chave_so_ali_e_tenta_de_novo_no_mesmo_adaptador(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, destino: str,
) -> None:
    """O ``Pair`` do branco dá, e ele não fica ``Connected`` (a física do diário
    dela). A tela mostra «Não Conectou» com o nome dele, a meia chave sai SÓ
    naquele adaptador — pelo mesmo verbo do X —, e «Tentar de Novo» abre outro
    «Conectar» no MESMO adaptador, onde ele chega.

    MORDIDA: faça ``_esquecer_as_meias_chaves`` não fazer nada — o objeto
    ``Paired`` sem ``Connected`` fica no adaptador e esta régua reprova.
    """
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    mundo.pair_mente = True
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        bancada.cena()
        bancada.gesto("escolher-adaptador", alvo=id_da_tela(destino))
        bancada.cena()
        ela_segura_ps_create(mundo, relogio, VERDE)
        bancada.gesto("conectar-aparelho")
        bancada.esperar_a_central()
        (feito,) = [m for m in bancada.central.movimentos() if m.estado == cr.NAO_CHEGOU]
        assert feito.destino == destino
        assert onde_pareou(mundo) == [rm.HCIS[destino]]

        cena = bancada.cena()
        (linha,) = _linhas(cena, destino, nao_conectou=True)
        assert linha["aparelho"] == id_da_tela(VERDE)
        assert mundo.objeto(destino, VERDE) is None, "a meia chave ficou no adaptador"
        assert mundo.lapides == [(destino, VERDE)]
        for outro in (SALA, QUARTO, VARANDA):
            if outro != destino:
                assert mundo.objeto(outro, VERDE) is None
        assert mundo.objeto(SALA, VERMELHO) is not None and mundo.objeto(SALA, AZUL) is not None

        # Uma vez por movimento: o tique seguinte não pede de novo.
        bancada.cena()
        assert mundo.lapides == [(destino, VERDE)]

        # «Tentar de Novo»: agora ele conecta.
        mundo.pair_mente = False
        ela_segura_ps_create(mundo, relogio, VERDE)
        assert bancada.gesto("tentar-de-novo", alvo=id_da_tela(destino)) == {"armou": True}
        bancada.esperar_a_central()
        assert onde_buscou(mundo) == [rm.HCIS[destino]] * 2
        assert mundo.onde_esta(rm.uniq(VERDE)) == destino
        cena = bancada.cena()
        assert not _linhas(cena, destino, nao_conectou=True)
        assert cena["aberto"] == id_da_tela(destino)
    finally:
        bancada.fechar()


# ---------------------------------------------------------------------------
# 4. o Connect fica para quem não está no ar
# ---------------------------------------------------------------------------


def test_o_controle_que_o_pair_conecta_nao_recebe_connect(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Item 5b, MEDIDO no diário dela: dos sete pareamentos da madrugada, só o
    do branco recebeu ``Connect`` — o ``Pair`` do DualSense já conecta. A régua
    segura isso: o ``Connect`` depois do ``Pair`` é a última tentativa, só para
    quem não está no ar.

    MORDIDA: faça o ``_parear_e_conferir`` da central chamar ``Connect`` sempre.
    """
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        bancada.cena()
        bancada.gesto("abrir-adaptador", alvo=id_da_tela(QUARTO))
        bancada.cena()
        ela_segura_ps_create(mundo, relogio, VERDE)
        bancada.gesto("conectar-aparelho")
        bancada.esperar_a_central()
        assert mundo.onde_esta(rm.uniq(VERDE)) == QUARTO
        assert mundo.metodos("Connect") == []
    finally:
        bancada.fechar()


# ---------------------------------------------------------------------------
# 5. o X esquece só no adaptador da linha
# ---------------------------------------------------------------------------


def _mesa_das_chaves() -> rm.RadioDeMentira:
    """O vermelho no ar na sala, com uma chave velha no quarto; o roxo desligado,
    com chave na varanda e na sala."""
    mundo = rm.RadioDeMentira()
    mundo.pareado(SALA, VERMELHO, nome="André")
    mundo.pareado(QUARTO, VERMELHO, host=False)
    mundo.pareado(VARANDA, ROXO, conectado=False, nome="Vitória")
    mundo.pareado(SALA, ROXO, host=False)
    return mundo


def test_o_desligado_aparece_em_cada_adaptador_em_que_tem_chave(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O X vale para controle ligado ou desligado: o roxo desligado tem uma linha
    «Desligado» (com X) em cada adaptador em que tem chave; o vermelho, no ar na
    sala, não vira «Desligado» no quarto — a linha dele é a viva."""
    mundo, relogio = _mesa_das_chaves(), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        sala = bancada.tique()["radio-sala"]
        cena = dict(a08._CENA_NA_TELA)
        assert len(_linhas(cena, VARANDA, desligado=True)) == 1
        assert len(_linhas(cena, SALA, desligado=True)) == 1
        assert not _linhas(cena, QUARTO, desligado=True), "o vermelho no ar virou Desligado"
        assert sala.count("Desligado</span>") == 2
        for lugar in (VARANDA, SALA):
            assert (f'data-gesto="esquecer-aparelho" data-alvo="{id_da_tela(ROXO)}" '
                    f'data-lugar="{id_da_tela(lugar)}"') in sala
        # A linha viva tem o ``uniq`` do daemon como id; a desligada, o endereço.
        assert (f'data-gesto="esquecer-aparelho" data-alvo="{rm.uniq(VERMELHO)}" '
                f'data-lugar="{id_da_tela(SALA)}"') in sala
    finally:
        bancada.fechar()


@pytest.mark.parametrize(("quem", "onde", "fica"), [
    (ROXO, VARANDA, SALA),      # desligado: sai da varanda, a chave da sala fica
    (ROXO, SALA, VARANDA),      # desligado: sai da sala, a da varanda fica
    (VERMELHO, SALA, QUARTO),   # no ar: sai da sala (e desconecta), a do quarto fica
])
def test_o_x_esquece_so_no_adaptador_da_linha(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
    quem: str, onde: str, fica: str,
) -> None:
    """O X abre a pergunta (nada sai), e o «Esquecer» dela tira a chave DAQUELE
    controle NAQUELE adaptador — o ``RemoveDevice`` e o verbo ``esquecer`` da
    ponte, que já existia. A chave dele no outro adaptador fica.

    MORDIDA: faça ``esquecer_o_pareamento`` procurar o objeto sem o adaptador
    (``caminho_do_aparelho(alvo)``) — ele tira a chave do primeiro adaptador da
    árvore, e os casos em que a linha não é a primeira reprovam.
    """
    mundo, relogio = _mesa_das_chaves(), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        bancada.cena()
        no_ar = mundo.onde_esta(rm.uniq(quem)) == onde
        clique = {"alvo": rm.uniq(quem) if no_ar else id_da_tela(quem),
                  "lugar": id_da_tela(onde)}
        assert bancada.gesto("esquecer-aparelho", **clique) == {"armou": True}
        assert mundo.metodos("RemoveDevice") == [] and mundo.lapides == [], "o X esqueceu sem ela"

        bancada.gesto("confirmar-esquecer", **clique)
        assert mundo.objeto(onde, quem) is None
        assert mundo.objeto(fica, quem) is not None, "o X esqueceu noutro adaptador"
        assert mundo.lapides == [(onde, quem)]
        cena = bancada.cena()
        assert not [a for a in cena["aparelhos"]
                    if str(a["id"]).lower() == rm.uniq(quem)
                    and a.get("lugar") == id_da_tela(onde)]
        if quem == VERMELHO:
            assert mundo.onde_esta(rm.uniq(VERMELHO)) == ""
    finally:
        bancada.fechar()


def test_o_esquecer_que_nao_deu_treme(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem a trava do rádio (outro dono a segura), o «Esquecer» não finge: o
    botão treme e a linha continua lá."""
    from hefesto_dualsense4unix.integrations import diario_do_radio

    mundo, relogio = _mesa_das_chaves(), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        bancada.cena()
        clique = {"alvo": id_da_tela(ROXO), "lugar": id_da_tela(VARANDA)}
        segurando, soltar = threading.Event(), threading.Event()

        def outro_dono() -> None:
            with diario_do_radio.trava_do_radio("outro"):
                segurando.set()
                soltar.wait(5)

        fio = threading.Thread(target=outro_dono, daemon=True)
        fio.start()
        assert segurando.wait(5)
        try:
            with pytest.raises(RuntimeError):
                _esquecer_com_prazo_curto(a08, bancada, clique)
        finally:
            soltar.set()
            fio.join(5)
        assert mundo.objeto(VARANDA, ROXO) is not None
        assert _linhas(bancada.cena(), VARANDA, desligado=True)
    finally:
        bancada.fechar()


def _esquecer_com_prazo_curto(a08: Any, bancada: Bancada, clique: dict[str, Any]) -> Any:
    """O «Esquecer» com o prazo da trava curto — a trava do outro dono não solta."""
    from hefesto_dualsense4unix.integrations import gesto_de_pareamento as gp

    def esquecer(lugar: str, aparelho: str) -> Any:
        return gp.esquecer_o_pareamento(
            a08._com_dois_pontos(lugar), a08._com_dois_pontos(aparelho), dono=bancada.dono,
            esquecer_na_ponte=bancada.mundo.esquecer_na_ponte, quem="tela", prazo_s=0.1)

    a08._esquecer_o_pareamento, antes = esquecer, a08._esquecer_o_pareamento
    try:
        return bancada.gesto("confirmar-esquecer", **clique)
    finally:
        a08._esquecer_o_pareamento = antes


# ---------------------------------------------------------------------------
# 6. o conferente, 26/09/2026: o que a primeira entrega deixava passar
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("destino", (SALA, QUARTO, VARANDA))
def test_a_meia_chave_so_sai_depois_do_veredito_da_central(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, destino: str,
) -> None:
    """Passado o prazo, a TELA solta o «esperando» e diz «Não Conectou»; a CENTRAL ainda
    diz «esperando» — ela confere o controle até o ``PRAZO_DO_PENDENTE_S`` dela, e
    o objeto ``Paired`` sem ``Connected`` desse instante é a chave que ela está
    conferindo. A tela não a apaga no relógio dela: a chave só sai quando a
    central disser «não chegou».

    MORDIDA: tire ``estado == _NAO_CHEGOU_NA_CENTRAL`` da ``meia`` de
    ``_os_que_nao_conectaram`` — a chave sai com o prazo da tela, com a central ainda
    conferindo, e esta régua reprova nos três adaptadores.
    """
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    mundo.pareado(destino, VERDE, conectado=False)
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        quando = time.time() - (a08.ESPERA_NA_TELA_S + 1.0)
        conferindo = cr.Movimento(VERDE, destino, cr.ESPERANDO, cr.PASSO_CONFERINDO,
                                  motivo=cr.MOTIVO_SEM_CONFIRMACAO, pareou_no_destino=True,
                                  quando=quando)
        _com_a_central(bancada, monkeypatch, conferindo)
        cena = bancada.cena()
        (linha,) = _linhas(cena, destino, nao_conectou=True)
        assert linha["aparelho"] == id_da_tela(VERDE) and linha["meia_chave"] is False
        assert mundo.objeto(destino, VERDE) is not None, "a tela apagou a chave em conferência"
        assert mundo.metodos("RemoveDevice") == [] and mundo.lapides == []

        _com_a_central(bancada, monkeypatch, cr.Movimento(
            VERDE, destino, cr.NAO_CHEGOU, cr.PASSO_FIM, motivo=cr.MOTIVO_PRAZO,
            pareou_no_destino=True, quando=quando))
        bancada.cena()
        assert mundo.objeto(destino, VERDE) is None, "o «não chegou» deixou a meia chave"
        assert mundo.lapides == [(destino, VERDE)]
    finally:
        bancada.fechar()


# A ZONA MORTA FECHOU em 26/09/2026 (A-GESTAO-DOS-CONTROLES-NO-PRODUTO-01), e o
# `xfail(strict=True)` que a guardava saiu: a tela soltava o «esperando» aos 60 s
# (`a08_conexoes.ESPERA_NA_TELA_S`) e a central o segurava até os 120 s dela
# (`central_do_radio.PRAZO_DO_PENDENTE_S`); entre os dois, «Tentar de Novo» e
# «Conectar» apareciam acesos e tremiam. A cura foi um dono só para o prazo — a
# tela lê o da central —, e esta régua passou a ser o contrato que segura isso.
def test_quando_a_tela_solta_o_esperando_a_central_aceita_o_tentar_de_novo(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A régua do contrato entre os dois relógios, com a CENTRAL REAL atrás do
    tratador real do daemon: no instante em que a tela diz «Não Conectou» e acende
    os botões, a central aceita o próximo «Conectar».

    O movimento é o do branco, no estado em que a central o deixa (o ``Pair``
    deu, o ``Connect`` e a conferência não confirmaram, e ela vigia), e a volta da
    vigia é a de verdade (``vigiar``, o que o fio dela roda a cada segundo).

    FOI ESTA A PROVA QUE A PRIMEIRA ENTREGA NÃO TINHA: a prova de tela clicou
    «Tentar de Novo» aos 70 s contra um daemon de mentira que só recusava quando
    o movimento em curso era um «Conectar» sem aparelho — mais frouxo que a
    central, que recusa com QUALQUER movimento em curso.
    """
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        passou = a08.ESPERA_NA_TELA_S + 1.0
        bancada.central._guardar(cr.Movimento(
            VERDE, QUARTO, cr.ESPERANDO, cr.PASSO_CONFERINDO,
            motivo=cr.MOTIVO_SEM_CONFIRMACAO, pareou_no_destino=True,
            comecou=relogio() - passou, quando=time.time() - passou))
        bancada.central.vigiar()
        cena = bancada.cena()
        assert cena["ocupado"] is False and _linhas(cena, QUARTO, nao_conectou=True)
        assert bancada.gesto("tentar-de-novo", alvo=id_da_tela(QUARTO)) == {"armou": True}
        bancada.esperar_a_central()
    finally:
        bancada.fechar()


def test_o_nao_conectou_de_quem_nao_e_controle_tem_x_e_tenta_o_mesmo_aparelho(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O fone que ela moveu para a varanda não chegou. A linha «Não Conectou» dele
    tem o X, com a pergunta (a linha nunca fica sem saída), e «Tentar de Novo»
    refaz o MESMO mover — o fone para a varanda —, sem o painel do «Procurando»:
    a janela do «Conectar» só aceita controle, e seguraria o rádio à toa.

    MORDIDAS: o X só em controle (``_tem_x`` pedindo ``tipo == "controle"``) — a
    linha fica sem X; e ``tentar_de_novo`` sempre com ``_mover(p, None, …)`` — o
    pedido sai sem o aparelho.
    """
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        _com_a_central(bancada, monkeypatch, cr.Movimento(
            FONE, VARANDA, cr.NAO_CHEGOU, cr.PASSO_FIM, motivo=cr.MOTIVO_SEM_GESTO,
            e_controle=False, classe=rm.CLASSE_DE_FONE, quando=time.time() - 5.0))
        campos = bancada.tique()
        cena = dict(a08._CENA_NA_TELA)
        (linha,) = _linhas(cena, VARANDA, nao_conectou=True)
        assert linha["tipo"] != "controle" and linha["aparelho"] == id_da_tela(FONE)
        varanda = id_da_tela(VARANDA)
        assert (f'data-gesto="esquecer-aparelho" data-alvo="{linha["id"]}" '
                f'data-lugar="{varanda}"') in campos["radio-sala"]
        assert (f'data-esquecer="1" data-alvo="{linha["id"]}" data-destino="{varanda}"'
                in campos["radio-moldes"])
        tentar = re.search(r'<button class="btn tentar"[^>]*>', campos["radio-sala"])
        assert tentar is not None and "data-abre" not in tentar.group(0)

        bancada.gesto("tentar-de-novo", alvo=varanda)
        bancada.esperar_a_central()
        assert bancada.ponte.chamadas == [
            ("radio.mover", {"destino": varanda, "aparelho": id_da_tela(FONE)})]
    finally:
        bancada.fechar()


def test_todo_x_na_tela_tem_a_pergunta_dele(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O X não esquece sozinho: a página abre a pergunta pelo par ``(linha,
    adaptador)``, e sem o molde dela o clique não faz NADA — nem pergunta, nem
    tremida. Todo X que tem o que esquecer (o vermelho no ar, o roxo desligado em
    cada adaptador, o branco que não chegou) tem a pergunta com o «Esquecer»
    (``confirmar-esquecer``); o «Não Conectou» da busca que ninguém respondeu não
    tem: o X dele só tira a linha.

    MORDIDA: tire ``_moldes_de_esquecer`` de ``html_dos_moldes`` — todo X vira um
    botão morto, e esta régua reprova.
    """
    mundo, relogio = _mesa_das_chaves(), rm.Relogio()
    mundo.fisicos[VERDE] = rm.Fisico(VERDE, rm.CLASSE_DE_CONTROLE)
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        agora = time.time()
        _com_a_central(bancada, monkeypatch,
                       cr.Movimento(VERDE, QUARTO, cr.NAO_CHEGOU, cr.PASSO_FIM,
                                    motivo=cr.MOTIVO_NAO_PAREOU, quando=agora - 5.0),
                       cr.Movimento("", VARANDA, cr.NAO_CHEGOU, cr.PASSO_FIM,
                                    motivo=cr.MOTIVO_SEM_GESTO, quando=agora - 5.0))
        campos = bancada.tique()
        xis = re.findall(r'data-gesto="esquecer-aparelho" data-alvo="([^"]+)" '
                         r'data-lugar="([^"]+)"', campos["radio-sala"])
        moldes = set(re.findall(
            r'<template class="pergunta-molde" data-esquecer="1" data-alvo="([^"]+)" '
            r'data-destino="([^"]+)" data-sim="Esquecer" data-gesto="confirmar-esquecer">',
            campos["radio-moldes"]))
        cena = dict(a08._CENA_NA_TELA)
        sem_aparelho = {(a["id"], a["lugar"]) for a in cena["aparelhos"]
                        if a.get("nao_conectou") and not a.get("aparelho")}
        assert len(xis) >= 5 and len(sem_aparelho) == 1
        for par in xis:
            if par in sem_aparelho:
                assert par not in moldes, f"o X que só tira a linha ganhou pergunta: {par}"
            else:
                assert par in moldes, f"o X de {par} não abre pergunta nenhuma"
    finally:
        bancada.fechar()


def test_o_fone_da_sony_desligado_nao_vira_controle(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A CLASSE decide quando ela existe, e só sem ela o ``Icon`` e o
    ``Modalias`` falam — a regra da central (``_e_controle``). Um fone pareado e
    desligado, com a classe de fone e o ``054C`` da Sony no ``Modalias``, não é
    a linha «Desligado» de um controle, e não ganha o X que esqueceria o
    pareamento dele. O DualSense desligado ao lado continua ganhando.

    MORDIDA: volte ``_e_controle_do_bluez`` a perguntar às três com ``or`` — o
    fone vira controle, e esta régua reprova.
    """
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    mundo.pareado(SALA, FONE, classe=rm.CLASSE_DE_FONE, conectado=False,
                  modalias="bluetooth:v054Cp0D58d0100")
    mundo.pareado(QUARTO, ROXO, conectado=False)
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        cena = bancada.cena()
        desligados = {(a["id"], a["lugar"]) for a in cena["aparelhos"] if a.get("desligado")}
        assert desligados == {(id_da_tela(ROXO), id_da_tela(QUARTO))}
    finally:
        bancada.fechar()
