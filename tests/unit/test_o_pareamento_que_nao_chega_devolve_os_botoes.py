"""O pareamento que não chega devolve os botões — O-RADIO-CONECTA-ONDE-ELA-MANDA-01."""

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
    """O ``radio_central`` publicado com ESTES movimentos (a hora de parede é a"""
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


@pytest.mark.parametrize("destino", (SALA, QUARTO, VARANDA))
def test_o_esperando_segura_a_tela_pelo_prazo_da_central_e_nao_mais(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, destino: str,
) -> None:
    """Um segundo antes do prazo a janela ainda é dela: a tela está ocupada, a"""
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
        campos = bancada.tique()
        sala = campos["radio-sala"]
        cena = dict(a08._CENA_NA_TELA)
        assert cena["ocupado"] is False, "a janela morta segurou a tela depois do prazo"
        (linha,) = _linhas(cena, destino, nao_conectou=True)
        assert linha["aparelho"] == id_da_tela(VERDE)
        assert f'title="{a08.NAO_CONECTOU}"' in sala
        assert f'data-gesto="tentar-de-novo" data-alvo="{id_da_tela(destino)}"' in sala
        # o X virou o «Tirar esta linha» do «⋮» (desenho aprovado de 05/10/2026)
        assert (f'data-gesto="dispensar-linha" data-alvo="{linha["id"]}" '
                f'data-lugar="{id_da_tela(destino)}"') in campos["radio-moldes"]
        assert cena["aberto"] == id_da_tela(destino), "a caixa de quem não chegou fechou"

        outro = next(e for e in (SALA, QUARTO, VARANDA) if e != destino)
        bancada.gesto("abrir-adaptador", alvo=id_da_tela(outro))
        assert bancada.cena()["destino_do_conectar"] == id_da_tela(outro)
    finally:
        bancada.fechar()


def test_com_a_janela_aberta_o_esquecer_treme(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O «Esquecer» segue o um-por-vez do «Mover»: com um controle esperando"""
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        _com_a_central(bancada, monkeypatch, cr.Movimento(
            "", QUARTO, cr.ESPERANDO, cr.PASSO_GESTO, quando=time.time()))
        bancada.cena()
        vermelho = {"alvo": rm.uniq(VERMELHO), "lugar": id_da_tela(SALA)}
        # o «⋮» e a pergunta abrem com a busca ligada (O-CONTROLE-JA-PAREADO-…, 03/10): só o
        # esquecer de verdade espera o rádio desocupar
        bancada.gesto("aparelho-menu", **vermelho)
        bancada.gesto("esquecer-aparelho", **vermelho)
        with pytest.raises(RuntimeError):
            bancada.gesto("confirmar-esquecer", **vermelho)
        assert mundo.metodos("RemoveDevice") == [] and mundo.lapides == []
    finally:
        bancada.fechar()


def test_a_busca_que_ninguem_respondeu_acaba_sem_nao_conectou(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ela abre a varanda, liga o «Procurar», e não segura PS + Create: a"""
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        bancada.cena()
        bancada.gesto("abrir-adaptador", alvo=id_da_tela(VARANDA))
        bancada.cena()
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


@pytest.mark.parametrize("destino", (SALA, QUARTO, VARANDA))
def test_o_branco_perde_a_meia_chave_so_ali_e_tenta_de_novo_no_mesmo_adaptador(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, destino: str,
) -> None:
    """O ``Pair`` do branco dá, e ele não fica ``Connected`` (a física do diário"""
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    mundo.pair_mente = True
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        bancada.cena()
        bancada.gesto("escolher-adaptador", alvo=id_da_tela(destino))
        bancada.cena()
        rm.ela_pareia(relogio, mundo, bancada.central, VERDE)
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

        bancada.cena()
        assert mundo.lapides == [(destino, VERDE)]

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
        bancada.gesto("radio-procurar")
        bancada.esperar_a_central()
        assert mundo.onde_esta(rm.uniq(VERDE)) == QUARTO
        assert mundo.metodos("Connect") == []
    finally:
        bancada.fechar()


def _mesa_das_chaves() -> rm.RadioDeMentira:
    """O vermelho no ar na sala, com uma chave velha no quarto; o roxo desligado,"""
    mundo = rm.RadioDeMentira()
    mundo.pareado(SALA, VERMELHO, nome="André")
    mundo.pareado(QUARTO, VERMELHO, host=False)
    mundo.pareado(VARANDA, ROXO, conectado=False, nome="Vitória")
    mundo.pareado(SALA, ROXO, host=False)
    return mundo


def test_o_desligado_aparece_em_cada_adaptador_em_que_tem_chave(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O «Esquecer» vale para controle ligado ou desligado: o roxo desligado tem"""
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
        par = f'data-alvo="{rm.uniq(VERMELHO)}" data-lugar="{id_da_tela(SALA)}"'
        assert f'data-gesto="aparelho-menu" {par}' in sala
        assert f'data-gesto="esquecer-aparelho" {par}' in moldes
    finally:
        bancada.fechar()


@pytest.mark.parametrize(("quem", "onde", "fica"), [
    (ROXO, VARANDA, SALA),
    (ROXO, SALA, VARANDA),
    (VERMELHO, SALA, QUARTO),
])
def test_o_esquecer_tira_so_no_adaptador_da_linha(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
    quem: str, onde: str, fica: str,
) -> None:
    """O «Esquecer» do «⋮» abre a pergunta (nada sai), e o «Esquecer» dela tira"""
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
    """Sem a trava do rádio (outro dono a segura), o «Esquecer» não finge: o"""
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


@pytest.mark.parametrize("destino", (SALA, QUARTO, VARANDA))
def test_a_tela_nao_tira_a_meia_chave_nem_depois_do_veredito(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, destino: str,
) -> None:
    """Passado o prazo, a TELA solta o «esperando» e diz «Não Conectou»; a CENTRAL ainda"""
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
    """O branco no estado em que a central o deixa (o ``Pair`` deu, o ``Connect``"""
    bancada.central._guardar(cr.Movimento(
        VERDE, destino, cr.ESPERANDO, cr.PASSO_CONFERINDO,
        motivo=cr.MOTIVO_SEM_CONFIRMACAO, pareou_no_destino=True,
        comecou=bancada.relogio() - segundos, quando=time.time() - segundos))


@pytest.mark.parametrize("destino", (SALA, QUARTO, VARANDA))
def test_o_nao_chegou_aos_sessenta_segundos_libera_a_central_e_a_tela_juntas(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, destino: str,
) -> None:
    """E1 da O-RADIO-CONECTA-ONDE-ELA-MANDA-02 — a régua do contrato entre os"""
    assert a08.ESPERA_NA_TELA_S == cr.PRAZO_DO_PENDENTE_S == 60.0, "dois prazos, dois donos"
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
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
    """A meia chave do lado do DAEMON: nenhuma tela aberta, e o branco não"""
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
    """A conferência não passa do prazo do movimento, que é o da tela: vencido"""
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


def _para_onde_move_o_vermelho(destino: str) -> str:
    """O vermelho mora na sala: o «Mover» dele vai para um adaptador que não é"""
    return next(a for a in (QUARTO, VARANDA, SALA) if a not in (SALA, destino))


@pytest.mark.parametrize("destino", (SALA, QUARTO, VARANDA))
def test_o_mover_aos_sessenta_e_um_segundos_tambem_e_aceito(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, destino: str,
) -> None:
    """O E1 não é só do «Conectar»: aos 61 s a tela também devolve o «Mover»"""
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
    """O «não chegou» que não é o do prazo: o branco tem chave na ``origem``,"""
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
    """A meia chave é a que NUNCA conectou. Vencido o prazo sem confirmação,"""
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
    """O pedido só resolve o «esperando» da CONFERÊNCIA. Um movimento que ainda"""
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
    """O fone que ela moveu para a varanda não chegou. A linha «Não Conectou» dele"""
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
                f'data-lugar="{varanda}"') in campos["radio-moldes"]
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
    """O «Esquecer» não esquece sozinho: o «⋮» da linha abre o menu pelo par"""
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
                         r'data-lugar="([^"]+)"', campos["radio-moldes"])
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
            if (alvo, lugar) in xis:  # a linha «Não conectou»: só «Tirar esta linha»
                assert 'data-gesto="esquecer-aparelho"' not in painel, (alvo, lugar)
                continue
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
