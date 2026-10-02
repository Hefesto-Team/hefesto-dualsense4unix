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
2. a busca que ninguém respondeu não vira linha nenhuma (desde a
   O-CONECTAR-E-UM-INTERRUPTOR-01), e o X da linha «Não Conectou» só tira a
   linha (``dispensar-linha``, desde a ESQUECER-E-LIMPAR-AS-CONEXOES-01);
3. o branco — ``Pair`` que dá e controle que não conecta — perde a meia chave
   SÓ naquele adaptador, e «Tentar de Novo» abre outro «Conectar» no mesmo;
4. o controle que o ``Pair`` já conecta não recebe ``Connect`` (item 5b: o
   ``Connect`` fica para quando ele não está no ar);
5. o «Esquecer» do «⋮» esquece o controle ligado ou desligado SÓ no adaptador
   da linha (era um X até a ESQUECER-E-LIMPAR-AS-CONEXOES-01).

E o que a O-RADIO-CONECTA-ONDE-ELA-MANDA-02 fechou (26/09/2026), os dois
buracos que a conferência da 01 deixou fora da posse dela:

6. **a zona morta de 60 a 120 s**: a tela soltava o «esperando» aos 60 s e a
   central recusava com «ocupado» até os 120. Agora o prazo é UM
   (``central_do_radio.PRAZO_DO_PENDENTE_S``, 60 s, medido no diário dela), e o
   «não chegou» libera a central e a tela no mesmo instante — sem esperar a
   volta da vigia;
7. **a meia chave do lado do daemon**: ela saía só com a janela aberta (quem a
   tirava era a tela); agora a central a tira no «não chegou», antes de
   publicá-lo, com a janela fechada — e desde 28/09 só ela
   (A-CAIXA-FICA-ONDE-ELA-ABRIU-01: a tela só mostra).

Faixa sintética da casa: ``aa:bb:cc``, octetos 4 e 5 zerados.
"""

from __future__ import annotations

import re
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
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

    É O «MOVER» DO VERDE DESDE 01/10/2026 (O-CONECTAR-E-UM-INTERRUPTOR-01): a
    busca SEM aparelho não tem mais idade — com a ``busca`` publicada, quem
    manda é ela, e o «Não Conectou» por idade fica para quem ela nomeou. A
    trava da tela que esta régua segura é a do «Mover» (o ``_mover``).

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
            VERDE, destino, cr.ESPERANDO, cr.PASSO_GESTO, e_controle=True,
            quando=agora - (a08.ESPERA_NA_TELA_S - 1.0)))
        cena = bancada.cena()
        assert cena["ocupado"] is True
        assert cena["aberto"] == id_da_tela(destino)
        assert cena["destino_do_conectar"] == id_da_tela(destino)
        assert not _linhas(cena, destino, nao_conectou=True)
        with pytest.raises(RuntimeError):
            bancada.gesto("confirmar-mudanca", alvo=rm.uniq(VERMELHO),
                          destino=id_da_tela(destino))

        _com_a_central(bancada, monkeypatch, cr.Movimento(
            VERDE, destino, cr.ESPERANDO, cr.PASSO_GESTO, e_controle=True,
            quando=agora - (a08.ESPERA_NA_TELA_S + 1.0)))
        sala = bancada.tique()["radio-sala"]
        cena = dict(a08._CENA_NA_TELA)
        assert cena["ocupado"] is False, "a janela morta segurou a tela depois do prazo"
        (linha,) = _linhas(cena, destino, nao_conectou=True)
        assert linha["aparelho"] == id_da_tela(VERDE)
        assert "Não Conectou" in sala
        assert f'data-gesto="tentar-de-novo" data-alvo="{id_da_tela(destino)}"' in sala
        # O X da linha «Não Conectou» TIRA A LINHA e não esquece nada
        # (ESQUECER-E-LIMPAR-AS-CONEXOES-01, D-3009-A-LINHA-TEM-APARELHO): o
        # gesto dele é o ``dispensar-linha``; o «Esquecer» mora no «⋮» de quem
        # tem pareamento ali.
        assert (f'data-gesto="dispensar-linha" data-alvo="{linha["id"]}" '
                f'data-lugar="{id_da_tela(destino)}"') in sala
        assert cena["aberto"] == id_da_tela(destino), "a caixa de quem não chegou fechou"

        # Ela abre outra caixa: o «Conectar» vai para lá, não para a janela morta.
        outro = next(e for e in (SALA, QUARTO, VARANDA) if e != destino)
        bancada.gesto("abrir-adaptador", alvo=id_da_tela(outro))
        assert bancada.cena()["destino_do_conectar"] == id_da_tela(outro)
    finally:
        bancada.fechar()


def test_com_a_janela_aberta_o_esquecer_treme(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O «Esquecer» segue o um-por-vez do «Mover»: com um controle esperando
    PS + Create noutro adaptador, o «⋮» e o «Esquecer» do vermelho tremem e nada
    sai do rádio."""
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        _com_a_central(bancada, monkeypatch, cr.Movimento(
            "", QUARTO, cr.ESPERANDO, cr.PASSO_GESTO, quando=time.time()))
        bancada.cena()
        vermelho = {"alvo": rm.uniq(VERMELHO), "lugar": id_da_tela(SALA)}
        with pytest.raises(RuntimeError):
            bancada.gesto("aparelho-menu", **vermelho)
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


def test_a_busca_que_ninguem_respondeu_acaba_sem_nao_conectou(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ela abre a varanda, liga o «Procurar», e não segura PS + Create: a
    central fecha a janela no teto, sem gesto, e a linha da varanda NÃO diz
    «Não Conectou» — a busca que acabou não é falha.

    FATO SUBSTITUÍDO (01/10/2026, O-CONECTAR-E-UM-INTERRUPTOR-01,
    D-3009-A-BUSCA-DESLIGADA-NAO-E-FALHA, a validar por ela): até aqui esta
    régua cobrava a linha «Não Conectou» dessa busca e o X que a tirava; era o
    «fantasma» das imagens 6 e 7 dela. O X de uma linha sem aparelho é da
    ESQUECER-E-LIMPAR-AS-CONEXOES-01."""
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        bancada.cena()
        bancada.gesto("abrir-adaptador", alvo=id_da_tela(VARANDA))
        bancada.cena()
        # MUDOU NA O-CONECTAR-E-UM-INTERRUPTOR-01: a busca liga pelo «Procurar»;
        # o «+ Conectar» só abre o painel.
        bancada.gesto("radio-procurar")
        bancada.esperar_a_central()
        (feito,) = bancada.central.movimentos()
        assert (feito.estado, feito.motivo, feito.destino) == (
            cr.NAO_CHEGOU, cr.MOTIVO_SEM_GESTO, VARANDA)

        cena = bancada.cena()
        assert not _linhas(cena, VARANDA, nao_conectou=True)
        assert cena["ocupado"] is False and cena["aberto"] == id_da_tela(VARANDA)
        assert cena["procurando"] == a08.PROCURAR_DESLIGADO
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
    naquele adaptador — pelo mesmo verbo do «Esquecer» —, e «Tentar de Novo» abre outro
    «Conectar» no MESMO adaptador, onde ele chega.

    UM DONO PARA A CHAVE, E UMA LÁPIDE SÓ: a central a tira ANTES de publicar o
    «não chegou» (``_esquecer_a_meia_chave``, desde a
    O-RADIO-CONECTA-ONDE-ELA-MANDA-02). Até 28/09 a tela a tirava de novo depois
    do veredito; saiu na A-CAIXA-FICA-ONDE-ELA-ABRIU-01 (achado 8 da auditoria
    de 26/09), e a tela só mostra.

    MORDIDA: faça ``_esquecer_a_meia_chave`` devolver ``False`` sem esquecer — o
    objeto ``Paired`` sem ``Connected`` fica no adaptador e esta régua reprova
    (até 28/09 ela ficava verde assim, pela tela).
    """
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    mundo.pair_mente = True
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        bancada.cena()
        bancada.gesto("escolher-adaptador", alvo=id_da_tela(destino))
        bancada.cena()
        rm.ela_pareia(relogio, mundo, bancada.central, VERDE)
        # MUDOU NA O-CONECTAR-E-UM-INTERRUPTOR-01: a busca liga pelo «Procurar»;
        # o «+ Conectar» só abre o painel.
        bancada.gesto("radio-procurar")
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
        rm.ela_pareia(relogio, mundo, bancada.central, VERDE)
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
        rm.ela_pareia(relogio, mundo, bancada.central, VERDE)
        # MUDOU NA O-CONECTAR-E-UM-INTERRUPTOR-01: a busca liga pelo «Procurar»;
        # o «+ Conectar» só abre o painel.
        bancada.gesto("radio-procurar")
        bancada.esperar_a_central()
        assert mundo.onde_esta(rm.uniq(VERDE)) == QUARTO
        assert mundo.metodos("Connect") == []
    finally:
        bancada.fechar()


# ---------------------------------------------------------------------------
# 5. o «Esquecer» tira só no adaptador da linha
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
    """O «Esquecer» vale para controle ligado ou desligado: o roxo desligado tem
    uma linha «Desligado» (com o «⋮») em cada adaptador em que tem chave; o
    vermelho, no ar na sala, não vira «Desligado» no quarto — a linha dele é a
    viva.

    MUDOU NA ESQUECER-E-LIMPAR-AS-CONEXOES-01 (D-3009-O-ESQUECER-TEM-NOME): o
    X que esquecia virou o «⋮» (``aparelho-menu``) na linha, e o «Esquecer»
    (``esquecer-aparelho``) mora no menu dele, nos moldes. O par
    ``(linha, adaptador)`` é o mesmo."""
    mundo, relogio = _mesa_das_chaves(), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        campos = bancada.tique()
        sala, moldes = campos["radio-sala"], campos["radio-moldes"]
        cena = dict(a08._CENA_NA_TELA)
        assert len(_linhas(cena, VARANDA, desligado=True)) == 1
        assert len(_linhas(cena, SALA, desligado=True)) == 1
        assert not _linhas(cena, QUARTO, desligado=True), "o vermelho no ar virou Desligado"
        assert sala.count("Desligado</span>") == 2
        for lugar in (VARANDA, SALA):
            par = (f'data-alvo="{id_da_tela(ROXO)}" data-lugar="{id_da_tela(lugar)}"')
            assert f'data-gesto="aparelho-menu" {par}' in sala
            assert f'data-gesto="esquecer-aparelho" {par}' in moldes
        # A linha viva tem o ``uniq`` do daemon como id; a desligada, o endereço.
        par = f'data-alvo="{rm.uniq(VERMELHO)}" data-lugar="{id_da_tela(SALA)}"'
        assert f'data-gesto="aparelho-menu" {par}' in sala
        assert f'data-gesto="esquecer-aparelho" {par}' in moldes
    finally:
        bancada.fechar()


@pytest.mark.parametrize(("quem", "onde", "fica"), [
    (ROXO, VARANDA, SALA),      # desligado: sai da varanda, a chave da sala fica
    (ROXO, SALA, VARANDA),      # desligado: sai da sala, a da varanda fica
    (VERMELHO, SALA, QUARTO),   # no ar: sai da sala (e desconecta), a do quarto fica
])
def test_o_esquecer_tira_so_no_adaptador_da_linha(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
    quem: str, onde: str, fica: str,
) -> None:
    """O «Esquecer» do «⋮» abre a pergunta (nada sai), e o «Esquecer» dela tira
    a chave DAQUELE controle NAQUELE adaptador — o ``RemoveDevice`` e o verbo
    ``esquecer`` da ponte, que já existia. A chave dele no outro adaptador fica.

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
        assert mundo.metodos("RemoveDevice") == [] and mundo.lapides == [], (
            "o «Esquecer» esqueceu sem ela")

        bancada.gesto("confirmar-esquecer", **clique)
        assert mundo.objeto(onde, quem) is None
        assert mundo.objeto(fica, quem) is not None, "o «Esquecer» esqueceu noutro adaptador"
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
def test_a_tela_nao_tira_a_meia_chave_nem_depois_do_veredito(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, destino: str,
) -> None:
    """Passado o prazo, a TELA solta o «esperando» e diz «Não Conectou»; a CENTRAL ainda
    diz «esperando» — ela confere o controle até o ``PRAZO_DO_PENDENTE_S`` dela, e
    o objeto ``Paired`` sem ``Connected`` desse instante é a chave que ela está
    conferindo. A tela não a apaga no relógio dela.

    E NEM DEPOIS DO VEREDITO (achado 8 da auditoria de 26/09,
    A-CAIXA-FICA-ONDE-ELA-ABRIU-01): a meia chave é da central, que a tira antes
    de publicar o «não chegou». Aqui o «não chegou» é publicado sem a central
    ter rodado — a chave continua no adaptador, e nada sai do rádio pela tela.
    Quem a tira de verdade é a régua da central,
    ``test_com_a_janela_fechada_a_central_tira_a_meia_chave_no_nao_chegou``.

    MORDIDA: devolva à tela o fio que esquecia a meia chave depois do veredito
    (``_esquecer_as_meias_chaves`` no ``cena_do_radio``) — o ``RemoveDevice`` sai
    pela tela e esta régua reprova nos três adaptadores.
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
        assert linha["aparelho"] == id_da_tela(VERDE)
        assert mundo.objeto(destino, VERDE) is not None, "a tela apagou a chave em conferência"
        assert mundo.metodos("RemoveDevice") == [] and mundo.lapides == []

        _com_a_central(bancada, monkeypatch, cr.Movimento(
            VERDE, destino, cr.NAO_CHEGOU, cr.PASSO_FIM, motivo=cr.MOTIVO_PRAZO,
            pareou_no_destino=True, quando=quando))
        for _ in range(3):
            (linha,) = _linhas(bancada.cena(), destino, nao_conectou=True)
        assert linha["aparelho"] == id_da_tela(VERDE), "a linha «Não Conectou» sumiu"
        assert mundo.objeto(destino, VERDE) is not None, "a tela tirou a meia chave"
        assert mundo.metodos("RemoveDevice") == [] and mundo.lapides == []
    finally:
        bancada.fechar()


def _o_branco_esperando(bancada: Bancada, destino: str, segundos: float) -> None:
    """O branco no estado em que a central o deixa (o ``Pair`` deu, o ``Connect``
    e a conferência não confirmaram, e ela vigia), com ``segundos`` de idade nos
    DOIS relógios: o dela (``comecou``) e o da tela (``quando``)."""
    bancada.central._guardar(cr.Movimento(
        VERDE, destino, cr.ESPERANDO, cr.PASSO_CONFERINDO,
        motivo=cr.MOTIVO_SEM_CONFIRMACAO, pareou_no_destino=True,
        comecou=bancada.relogio() - segundos, quando=time.time() - segundos))


@pytest.mark.parametrize("destino", (SALA, QUARTO, VARANDA))
def test_o_nao_chegou_aos_sessenta_segundos_libera_a_central_e_a_tela_juntas(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, destino: str,
) -> None:
    """E1 da O-RADIO-CONECTA-ONDE-ELA-MANDA-02 — a régua do contrato entre os
    dois relógios, com a CENTRAL REAL atrás do tratador real do daemon, e o
    destino em cada posição dos três adaptadores.

    Aos 59 s a tela segura o «esperando» e a central recusa o próximo
    «Conectar»: as duas dizem «ainda não». Aos 61 s a tela diz «Não Conectou» e
    acende «Tentar de Novo» — e o clique É ACEITO no mesmo instante, sem
    nenhuma volta da vigia no meio: o pedido resolve o vencido antes de
    perguntar se a central está ocupada. E o «não chegou» dela tira a meia
    chave do branco naquele adaptador (uma lápide, e só ali).

    FOI ESTA A ZONA MORTA DA 01 (era a ``xfail`` desta régua): a tela soltava
    aos 60 s e a central aos 120, e entre os dois os botões acesos tremiam.

    MORDIDAS: volte ``PRAZO_DO_PENDENTE_S`` a 120 — o clique dos 61 s treme; tire
    o ``_vencer_os_prazos`` do ``comecar_a_conectar`` — o clique chega antes da
    vigia e treme também.
    """
    assert a08.ESPERA_NA_TELA_S == cr.PRAZO_DO_PENDENTE_S == 60.0, "dois prazos, dois donos"
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    # A meia chave que o Pair do branco deixou: Paired, nunca Connected.
    mundo.pareado(destino, VERDE, conectado=False, host=False)
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        _o_branco_esperando(bancada, destino, a08.ESPERA_NA_TELA_S - 1.0)
        cena = bancada.cena()
        assert cena["ocupado"] is True and not _linhas(cena, destino, nao_conectou=True)
        recusa = bancada.central.comecar_a_conectar(destino)
        assert recusa.motivo == cr.MOTIVO_OCUPADO, "a central soltou antes da tela"
        assert mundo.objeto(destino, VERDE) is not None, "a chave saiu com a central conferindo"

        _o_branco_esperando(bancada, destino, a08.ESPERA_NA_TELA_S + 1.0)
        cena = bancada.cena()
        assert cena["ocupado"] is False and _linhas(cena, destino, nao_conectou=True)
        assert bancada.gesto("tentar-de-novo", alvo=id_da_tela(destino)) == {"armou": True}
        (velho,) = [m for m in bancada.central.movimentos() if m.aparelho == VERDE]
        assert (velho.estado, velho.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_PRAZO)
        assert mundo.objeto(destino, VERDE) is None, "o «não chegou» deixou a meia chave"
        assert mundo.lapides == [(destino, VERDE)]
        assert mundo.objeto(SALA, VERMELHO) is not None and mundo.objeto(SALA, AZUL) is not None
        bancada.esperar_a_central()
        assert onde_buscou(mundo) == [rm.HCIS[destino]], "o Tentar de Novo buscou noutro lugar"
    finally:
        bancada.fechar()


def _central_sem_tela(mundo: rm.RadioDeMentira, relogio: rm.Relogio,
                      **extra: Any) -> tuple[cr.CentralDoRadio, bd.DonoVivo]:
    dono = bd.DonoVivo(mundo)
    assert dono.ligar()
    central = cr.CentralDoRadio(
        dono=dono, onde_esta=mundo.onde_esta, movimento=mundo.hz,
        esquecer_na_ponte=mundo.esquecer_na_ponte, relogio=relogio, dormir=relogio.dormir,
        sysfs={"listar": lambda _p: [], "raiz": "/nao/existe"}, **extra)
    return central, dono


@pytest.mark.parametrize("destino", (SALA, QUARTO, VARANDA))
def test_com_a_janela_fechada_a_central_tira_a_meia_chave_no_nao_chegou(
    diario: Path, destino: str,
) -> None:
    """A meia chave do lado do DAEMON: nenhuma tela aberta, e o branco não
    chega. O «não chegou» do prazo tira a chave dele SÓ naquele adaptador —
    ``RemoveDevice`` e a lápide da ponte, uma vez —, e os controles no ar na
    sala ficam.

    MORDIDA: faça ``_esquecer_a_meia_chave`` devolver ``False`` sem esquecer — a
    chave fica no adaptador, e esta régua reprova.
    """
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    mundo.pair_mente = True
    central, dono = _central_sem_tela(mundo, relogio)
    try:
        rm.ela_pareia(relogio, mundo, central, VERDE)
        feito = central.conectar(destino)
        assert (feito.estado, feito.passo, feito.aparelho) == (
            cr.ESPERANDO, cr.PASSO_CONFERINDO, VERDE)
        assert mundo.objeto(destino, VERDE)["Paired"] is True, "o BlueZ disse que deu"

        relogio.agora = feito.comecou + cr.PRAZO_DO_PENDENTE_S
        central.vigiar()
        fim = central.movimento_de(VERDE)
        assert (fim.estado, fim.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_PRAZO)
        assert mundo.objeto(destino, VERDE) is None, "a meia chave ficou com a janela fechada"
        assert mundo.lapides == [(destino, VERDE)]
        assert mundo.objeto(SALA, VERMELHO) is not None and mundo.objeto(SALA, AZUL) is not None

        central.vigiar()
        assert mundo.lapides == [(destino, VERDE)], "a vigia esqueceu duas vezes"
    finally:
        central.fechar(espera=5.0)
        dono.fechar()


def test_o_prazo_que_vence_na_conferencia_fecha_na_hora(diario: Path) -> None:
    """A conferência não passa do prazo do movimento, que é o da tela: vencido
    no meio dela, o «não chegou» sai NA HORA (e a meia chave com ele), e não
    na volta seguinte da vigia.

    MORDIDAS: tire o ``min`` do fim de ``_conferir`` — ela confere os 10 s
    inteiros e o «não chegou» sai depois do prazo; tire o fecho do prazo depois
    da conferência em ``_parear_e_conferir`` — o movimento volta «esperando».
    """
    prazo = 8.0
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    mundo.pair_mente = True
    central, dono = _central_sem_tela(mundo, relogio, prazo_do_pendente_s=prazo)
    try:
        rm.ela_pareia(relogio, mundo, central, VERDE)
        comeco = relogio.agora
        feito = central.conectar(QUARTO)
        assert (feito.estado, feito.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_PRAZO)
        assert relogio.agora - comeco <= prazo + cr.PASSO_S, "a conferência passou do prazo"
        assert mundo.objeto(QUARTO, VERDE) is None and mundo.lapides == [(QUARTO, VERDE)]
    finally:
        central.fechar(espera=5.0)
        dono.fechar()


# ---------------------------------------------------------------------------
# A conferência da O-RADIO-CONECTA-ONDE-ELA-MANDA-02 (26/09/2026): as curas que
# nenhuma régua mordia. Cada uma foi arrancada e a régua inteira do território
# ficou verde — estas são as que passam a reprovar.
# ---------------------------------------------------------------------------


def _para_onde_move_o_vermelho(destino: str) -> str:
    """O vermelho mora na sala: o «Mover» dele vai para um adaptador que não é
    o dele nem o do branco esperando."""
    return next(a for a in (QUARTO, VARANDA, SALA) if a not in (SALA, destino))


@pytest.mark.parametrize("destino", (SALA, QUARTO, VARANDA))
def test_o_mover_aos_sessenta_e_um_segundos_tambem_e_aceito(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, destino: str,
) -> None:
    """O E1 não é só do «Conectar»: aos 61 s a tela também devolve o «Mover»
    (a pergunta da mudança), e a central o aceita no mesmo instante — sem
    volta da vigia no meio. Aos 59 s, as duas dizem «ainda não».

    MORDIDA: tire o ``_vencer_os_prazos`` do ``comecar_a_mover`` — o «Mover»
    dos 61 s treme, e o E1 valia só para um dos dois gestos que movem.
    """
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    mundo.pareado(destino, VERDE, conectado=False, host=False)
    para = _para_onde_move_o_vermelho(destino)
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        _o_branco_esperando(bancada, destino, a08.ESPERA_NA_TELA_S - 1.0)
        assert bancada.cena()["ocupado"] is True
        recusa = bancada.central.comecar_a_mover(VERMELHO, para)
        assert recusa.motivo == cr.MOTIVO_OCUPADO, "a central soltou antes da tela"

        _o_branco_esperando(bancada, destino, a08.ESPERA_NA_TELA_S + 1.0)
        assert bancada.cena()["ocupado"] is False
        assert bancada.gesto("confirmar-mudanca", alvo=VERMELHO, destino=para) == {
            "armou": True}
        (velho,) = [m for m in bancada.central.movimentos() if m.aparelho == VERDE]
        assert (velho.estado, velho.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_PRAZO)
        assert (destino, VERDE) in mundo.lapides, "o «não chegou» deixou a meia chave"
        bancada.esperar_a_central()
        assert any(m.aparelho == VERMELHO and m.destino == para
                   for m in bancada.central.movimentos()), "o «Mover» não começou"
    finally:
        bancada.fechar()


PARES_DE_ADAPTADORES = [(o, d) for o in (SALA, QUARTO, VARANDA)
                        for d in (SALA, QUARTO, VARANDA) if o != d]


@pytest.mark.parametrize(("origem", "destino"), PARES_DE_ADAPTADORES)
def test_o_que_volta_para_a_origem_leva_embora_a_meia_chave_do_destino(
    diario: Path, origem: str, destino: str,
) -> None:
    """O «não chegou» que não é o do prazo: o branco tem chave na ``origem``,
    ela clica «Conectar» no ``destino``, o ``Pair`` dá e o HID não vem — e ela
    aperta PS: ele volta para a origem. A meia chave que o ``Pair`` deixou no
    destino sai (é o mesmo «não chegou», com a janela fechada), e a chave da
    origem, onde ele está no ar, fica.

    MORDIDA: devolva o «voltou» de ``_vigiar_um`` ao ``_acabou`` sem a meia
    chave — o destino fica com o branco ``Paired`` e nunca ``Connected``.
    """
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    mundo.pareado(origem, VERDE, conectado=False)
    mundo.pair_mente = True
    central, dono = _central_sem_tela(mundo, relogio)
    try:
        rm.ela_pareia(relogio, mundo, central, VERDE)
        feito = central.conectar(destino)
        assert (feito.estado, feito.passo, feito.aparelho) == (
            cr.ESPERANDO, cr.PASSO_CONFERINDO, VERDE)
        assert feito.origens == (origem,)

        mundo.apertar_ps(VERDE)
        assert mundo.onde_esta(rm.uniq(VERDE)) == origem
        central.vigiar()
        fim = central.movimento_de(VERDE)
        assert (fim.estado, fim.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_VOLTOU)
        assert mundo.objeto(destino, VERDE) is None, "a meia chave ficou no destino"
        assert mundo.lapides == [(destino, VERDE)]
        assert mundo.objeto(origem, VERDE)["Connected"] is True
    finally:
        central.fechar(espera=5.0)
        dono.fechar()


@pytest.mark.parametrize("quem_diz", ("o-bluez", "o-kernel"))
@pytest.mark.parametrize("destino", (SALA, QUARTO, VARANDA))
def test_no_nao_chegou_quem_esta_no_ar_no_destino_nao_perde_a_chave(
    diario: Path, destino: str, quem_diz: str,
) -> None:
    """A meia chave é a que NUNCA conectou. Vencido o prazo sem confirmação,
    o branco que o BlueZ diz ``Connected`` no destino (e o kernel ainda não),
    ou que o kernel diz no destino (e o movimento dele ainda não se mediu),
    continua com a chave: o «não chegou» sai, e nada se esquece.

    MORDIDAS: tire de ``_esquecer_a_meia_chave`` a guarda do ``Connected`` — o
    caso ``o-bluez`` reprova; tire a do ``HID_PHYS`` — o caso ``o-kernel``
    reprova. Nos dois, a chave de um controle no ar sairia.
    """
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    mundo.pair_mente = True
    central, dono = _central_sem_tela(mundo, relogio)
    try:
        rm.ela_pareia(relogio, mundo, central, VERDE)
        feito = central.conectar(destino)
        assert (feito.estado, feito.passo) == (cr.ESPERANDO, cr.PASSO_CONFERINDO)
        if quem_diz == "o-bluez":
            mundo.escrever(rm.no_de(destino, VERDE), bd.APARELHO, "Connected", "b", True,
                           espera=1.0)
        else:
            mundo.fisicos[VERDE].conectado_em = destino
            mundo.fisicos[VERDE].hz = 0.0

        relogio.agora = feito.comecou + cr.PRAZO_DO_PENDENTE_S
        central.vigiar()
        fim = central.movimento_de(VERDE)
        assert (fim.estado, fim.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_PRAZO)
        assert mundo.objeto(destino, VERDE) is not None, "a chave de quem está no ar saiu"
        assert mundo.lapides == []
    finally:
        central.fechar(espera=5.0)
        dono.fechar()


@pytest.mark.parametrize("destino", (SALA, QUARTO, VARANDA))
def test_o_pair_em_voo_passado_o_prazo_nao_se_fecha_pelo_pedido(
    diario: Path, destino: str,
) -> None:
    """O pedido só resolve o «esperando» da CONFERÊNCIA. Um movimento que ainda
    está no ``Pair`` (o fio dele segura a trava e o ``Pair`` do BlueZ pode
    levar até 45 s) não se fecha por fora: o próximo «Conectar» recebe
    «ocupado», e o movimento em voo fica como estava. Fechá-lo abriria uma
    segunda janela com a primeira ainda pareando.

    MORDIDA: tire de ``_vencer_os_prazos`` a condição do passo — o pedido
    fecha o ``Pair`` em voo e o «Conectar» seguinte começa por cima dele.
    """
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    central, dono = _central_sem_tela(mundo, relogio)
    try:
        em_voo = central._guardar(cr.Movimento(
            VERDE, destino, cr.ESPERANDO, cr.PASSO_PAREANDO,
            comecou=relogio() - cr.PRAZO_DO_PENDENTE_S - 1.0))
        recusa = central.comecar_a_conectar(_para_onde_move_o_vermelho(destino))
        assert recusa.motivo == cr.MOTIVO_OCUPADO
        assert central.movimento_de(VERDE) == em_voo
    finally:
        central.fechar(espera=5.0)
        dono.fechar()


def test_o_nao_conectou_de_quem_nao_e_controle_tem_x_e_tenta_o_mesmo_aparelho(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O fone que ela moveu para a varanda não chegou. A linha «Não Conectou» dele
    tem o X (a linha nunca fica sem saída), e «Tentar de Novo» refaz o MESMO
    mover — o fone para a varanda —, sem o painel do «Procurando»: a janela do
    «Conectar» só aceita controle, e seguraria o rádio à toa.

    MUDOU NA ESQUECER-E-LIMPAR-AS-CONEXOES-01 (D-3009-A-LINHA-TEM-APARELHO): o X
    da linha «Não Conectou» tira a linha (``dispensar-linha``) e não pergunta
    nada — ele não esquece pareamento. Quem tem chave ali aparece «Desligado»,
    com o «⋮».

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
        assert (f'data-gesto="dispensar-linha" data-alvo="{linha["id"]}" '
                f'data-lugar="{varanda}"') in campos["radio-sala"]
        assert (f'data-esquecer="1" data-alvo="{linha["id"]}"'
                not in campos["radio-moldes"]), "o X que só tira a linha ganhou pergunta"
        tentar = re.search(r'<button class="btn tentar"[^>]*>', campos["radio-sala"])
        assert tentar is not None and "data-abre" not in tentar.group(0)

        bancada.gesto("tentar-de-novo", alvo=varanda)
        bancada.esperar_a_central()
        assert bancada.ponte.chamadas == [
            ("radio.mover", {"destino": varanda, "aparelho": id_da_tela(FONE)})]
    finally:
        bancada.fechar()


def test_todo_menu_na_tela_tem_o_esquecer_e_a_pergunta_dele(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O «Esquecer» não esquece sozinho: o «⋮» da linha abre o menu pelo par
    ``linha|adaptador``, o «Esquecer» de lá abre a pergunta pelo par ``(linha,
    adaptador)``, e sem os moldes o clique não faz NADA. Todo «⋮» (o vermelho no
    ar, o roxo desligado em cada adaptador) tem o menu com o «Esquecer» e a
    pergunta com o ``confirmar-esquecer``; o X do branco que não chegou não tem
    pergunta: ele só tira a linha (``dispensar-linha``).

    MORDIDA: tire ``_moldes_de_esquecer`` de ``html_dos_moldes`` — todo «⋮» vira
    um botão morto, e esta régua reprova.

    MUDOU NA ESQUECER-E-LIMPAR-AS-CONEXOES-01 (D-3009-O-ESQUECER-TEM-NOME e
    D-3009-A-LINHA-TEM-APARELHO): era «todo X na tela tem a pergunta dele». O X
    que esquecia virou o «⋮» com o menu, e o X que sobra só tira a linha «Não
    Conectou». A janela que não abriu (``sem_janela`` sem aparelho) não faz
    mais linha nenhuma.
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
                                    motivo=cr.MOTIVO_SEM_JANELA, quando=agora - 5.0))
        campos = bancada.tique()
        menus = re.findall(r'data-gesto="aparelho-menu" data-alvo="([^"]+)" '
                           r'data-lugar="([^"]+)"', campos["radio-sala"])
        xis = re.findall(r'data-gesto="dispensar-linha" data-alvo="([^"]+)" '
                         r'data-lugar="([^"]+)"', campos["radio-sala"])
        paineis = dict(re.findall(
            r'<template class="painel-molde" data-painel="menu" data-alvo="([^"]+)"'
            r'[^>]*>(.*?)</template>', campos["radio-moldes"]))
        perguntas = set(re.findall(
            r'<template class="pergunta-molde" data-esquecer="1" data-alvo="([^"]+)" '
            r'data-destino="([^"]+)" data-sim="Esquecer" data-gesto="confirmar-esquecer">',
            campos["radio-moldes"]))
        cena = dict(a08._CENA_NA_TELA)
        assert not [a for a in cena["aparelhos"]
                    if a.get("nao_conectou") and not a.get("aparelho")], (
            "a janela que não abriu virou linha sem aparelho")
        assert len(menus) >= 3 and len(xis) == 1
        for alvo, lugar in menus:
            painel = paineis.get(f"{alvo}|{lugar}")
            assert painel is not None, f"o «⋮» de {(alvo, lugar)} não abre menu nenhum"
            assert (f'data-gesto="esquecer-aparelho" data-alvo="{alvo}" '
                    f'data-lugar="{lugar}"') in painel
            assert (alvo, lugar) in perguntas, f"o «Esquecer» de {(alvo, lugar)} não pergunta"
        for par in xis:
            assert par not in perguntas, f"o X que só tira a linha ganhou pergunta: {par}"
    finally:
        bancada.fechar()


def test_o_fone_da_sony_desligado_nao_vira_controle(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A CLASSE decide quando ela existe, e só sem ela o ``Icon`` e o
    ``Modalias`` falam — a regra da central (``_e_controle``). Um fone pareado e
    desligado, com a classe de fone e o ``054C`` da Sony no ``Modalias``, não é
    a linha «Desligado» de um CONTROLE: é a de um fone. O DualSense desligado ao
    lado continua controle.

    MUDOU NA ESQUECER-E-LIMPAR-AS-CONEXOES-01 (D-3009-O-ESQUECER-TEM-NOME): o
    fone desligado passou a ter linha «Desligado», com o tipo fone e o «⋮» que
    esquece o pareamento DELE — até aqui ele não aparecia, e o único jeito de
    esquecê-lo era fora do Hefesto. O que esta régua guarda é o mesmo: o fone
    não vira controle.

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
        desligados = {(a["id"], a["lugar"]): a["tipo"]
                      for a in cena["aparelhos"] if a.get("desligado")}
        assert desligados == {(id_da_tela(ROXO), id_da_tela(QUARTO)): "controle",
                              (id_da_tela(FONE), id_da_tela(SALA)): "fone"}
    finally:
        bancada.fechar()
