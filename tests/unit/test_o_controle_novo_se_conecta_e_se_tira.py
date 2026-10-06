"""O controle novo se conecta, e se tira, pela Conexões.

O-CONTROLE-NOVO-SE-CONECTA-E-SE-TIRA-PELA-CONEXOES-01.

A física do diário do rádio dela, 06/10/2026, 17:14 e 17:15, no adaptador que já tinha dois
controles no ar: o ``Pair`` do terceiro deu, o ``Connect`` correu com a varredura AINDA de pé no
mesmo adaptador e voltou ``org.bluez.Error.Failed``, o ``StopDiscovery`` só veio depois, e
ninguém chamou o controle de novo — aos 60 s da janela a central tirou a chave que tinha acabado
de fazer como «meia chave», e o controle voltou a pedir PS + Create. Às 17:17, no outro
adaptador, o mesmo controle conectou sozinho três segundos depois do ``Pair``.

O mundo de mentira daqui reproduz isso: o controle aceita o host no ``Pair`` (a chave é inteira),
mas não conecta sozinho; o ``Connect`` falha enquanto o adaptador varre, e, no controle que
«acorda tarde», também nos primeiros segundos depois do ``Pair``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import central_do_radio as cr
from tests.unit import radio_de_mentira as rm
from tests.unit.radio_de_mentira import AZUL, QUARTO, ROXO, SALA, VARANDA, VERDE, VERMELHO
from tests.unit.test_o_conectar_pareia_no_adaptador_escolhido import (
    mundo_da_madrugada,
    preparar_o_diario,
)

ADAPTADORES = (SALA, QUARTO, VARANDA)


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return preparar_o_diario(tmp_path, monkeypatch)


def o_controle_do_diario(mundo: rm.RadioDeMentira, relogio: rm.Relogio, aparelho: str, *,
                         acorda_em: float = 0.0) -> dict[str, Any]:
    """O ``aparelho`` com a física de 06/10: o ``Pair`` dá e o controle guarda o host, mas não
    conecta sozinho; o ``Connect`` volta ``Failed`` com a varredura de pé no adaptador, e antes
    de ``acorda_em`` segundos do ``Pair``. Devolve o que se viu (``pareou``: a hora do ``Pair``)."""
    original = mundo._no_aparelho
    visto: dict[str, Any] = {"pareou": None}

    def no_aparelho(caminho: str, metodo: str) -> bd.Escrita:
        adaptador = mundo._endereco_do_hci(caminho.rsplit("/", 1)[0])
        if (bd.endereco_do_aparelho(caminho) or "") != aparelho:
            return original(caminho, metodo)
        fisico = mundo.fisicos[aparelho]
        if metodo == "Pair":
            antes, mundo.pair_mente = mundo.pair_mente, True
            try:
                feito = original(caminho, metodo)
            finally:
                mundo.pair_mente = antes
            if feito.feita:
                fisico.pareando = fisico.chamando = False
                fisico.host = adaptador
                visto["pareou"] = relogio.agora
            return feito
        if metodo == "Connect" and visto["pareou"] is not None:
            varrendo = mundo.mesa[rm.HCIS[adaptador]][bd.ADAPTADOR].get("Discovering")
            if varrendo or relogio.agora < visto["pareou"] + acorda_em:
                mundo.linha_do_tempo.append(("Connect", adaptador, aparelho))
                return bd.Escrita(False, "org.bluez.Error.Failed")
        return original(caminho, metodo)

    mundo._no_aparelho = no_aparelho  # type: ignore[method-assign]
    return visto


def central_sem_tela(mundo: rm.RadioDeMentira,
                     relogio: rm.Relogio) -> tuple[cr.CentralDoRadio, bd.DonoVivo]:
    dono = bd.DonoVivo(mundo)
    assert dono.ligar()
    central = cr.CentralDoRadio(
        dono=dono, onde_esta=mundo.onde_esta, movimento=mundo.hz,
        esquecer_na_ponte=mundo.esquecer_na_ponte, relogio=relogio, dormir=relogio.dormir,
        sysfs={"listar": lambda _p: [], "raiz": "/nao/existe"})
    return central, dono


def a_vigia_por(central: cr.CentralDoRadio, relogio: rm.Relogio, aparelho: str,
                segundos: float) -> cr.Movimento | None:
    """O fio do gesto depois do mover (``_vigiar_ate_resolver``): uma volta por segundo, NO
    TEMPO, até o movimento resolver ou os ``segundos`` passarem."""
    fim = relogio.agora + segundos
    while relogio.agora < fim:
        atual = central.movimento_de(aparelho)
        if atual is None or not atual.em_curso:
            return atual
        relogio.dormir(1.0)
        central.vigiar()
    return central.movimento_de(aparelho)


def _o_quarto_controle() -> rm.RadioDeMentira:
    """Três no ar na sala (o terceiro é o roxo), e o verde novo na mão: o quarto controle."""
    mundo = mundo_da_madrugada()
    mundo.pareado(SALA, ROXO)
    return mundo


def _linha(mundo: rm.RadioDeMentira, metodo: str, aparelho: str = "") -> list[int]:
    return [i for i, (m, _a, ap) in enumerate(mundo.linha_do_tempo)
            if m == metodo and (not aparelho or ap == aparelho)]


@pytest.mark.parametrize("destino", ADAPTADORES)
def test_a_busca_sai_do_destino_antes_do_connect_da_chave_nova(
    diario: Path, destino: str,
) -> None:
    """A ORDEM do diário, invertida: ``Pair`` → ``StopDiscovery`` → ``Connect``. Com a busca
    fechada antes, o primeiro ``Connect`` já encontra o adaptador livre e o controle chega.

    MORDIDA: tire o ``janela.fechar()`` que vem logo depois do ``Pair`` em ``_uma_janela``.
    """
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    o_controle_do_diario(mundo, relogio, VERDE)
    central, dono = central_sem_tela(mundo, relogio)
    try:
        rm.ela_pareia(relogio, mundo, central, VERDE)
        feito = central.conectar(destino)
        (pair,) = _linha(mundo, "Pair", VERDE)
        parou = [i for i in _linha(mundo, "StopDiscovery") if i > pair]
        conectou = _linha(mundo, "Connect", VERDE)
        assert parou and conectou, mundo.linha_do_tempo
        assert parou[0] < conectou[0], (
            f"o Connect correu com a busca de pé, como no diário: {mundo.linha_do_tempo}")
        assert len(conectou) == 1, "o primeiro Connect, já sem a busca, não chegou"
        assert (feito.estado, feito.destino) == (cr.CHEGOU, destino)
        assert mundo.onde_esta(rm.uniq(VERDE)) == destino
        assert mundo.lapides == []
    finally:
        central.fechar(espera=5.0)
        dono.fechar()


@pytest.mark.parametrize("mundo_de", (mundo_da_madrugada, _o_quarto_controle),
                         ids=("terceiro", "quarto"))
@pytest.mark.parametrize("destino", ADAPTADORES)
def test_a_chave_nova_que_conecta_tarde_nao_sai_como_meia_chave(
    diario: Path, destino: str, mundo_de: Any,
) -> None:
    """O ciclo do diário: logo depois do ``Pair``, pareado e AINDA não conectado. O controle só
    atende aos 20 s. A central chama de novo (``Trusted`` e ``Connect``), e a chave NÃO sai —
    nem no tique da vigia, nem depois: quem chegou fica, com os outros no ar.

    MORDIDA: faça ``_provocar_a_chave_nova`` voltar logo no começo; a vigia passa os 60 s sem
    chamar o controle e o ``central_esquece_a_meia_chave`` volta (a lápide no destino).
    """
    mundo, relogio = mundo_de(), rm.Relogio()
    o_controle_do_diario(mundo, relogio, VERDE, acorda_em=20.0)
    no_ar_antes = {a: f.conectado_em for a, f in mundo.fisicos.items() if f.conectado_em}
    central, dono = central_sem_tela(mundo, relogio)
    try:
        rm.ela_pareia(relogio, mundo, central, VERDE)
        feito = central.conectar(destino)
        assert (feito.estado, feito.passo) == (cr.ESPERANDO, cr.PASSO_CONFERINDO), (
            "a régua não reproduziu o pareado-e-ainda-não-conectado")
        assert mundo.objeto(destino, VERDE)["Paired"] is True
        assert mundo.objeto(destino, VERDE)["Connected"] is False

        fim = a_vigia_por(central, relogio, VERDE, cr.PRAZO_DO_PENDENTE_S + 5.0)
        assert fim is not None and (fim.estado, fim.destino) == (cr.CHEGOU, destino), (
            f"a chave nova não ficou: {fim} — lápides {mundo.lapides}")
        assert mundo.lapides == [], "a central esqueceu a chave que acabou de fazer"
        assert mundo.objeto(destino, VERDE)["Connected"] is True
        assert len(_linha(mundo, "Connect", VERDE)) >= 2, "ninguém chamou o controle de novo"
        for aparelho, onde in no_ar_antes.items():
            assert mundo.fisicos[aparelho].conectado_em == onde, f"{aparelho} caiu do ar"

        a_vigia_por(central, relogio, VERDE, 10.0)
        assert mundo.lapides == [] and mundo.onde_esta(rm.uniq(VERDE)) == destino
    finally:
        central.fechar(espera=5.0)
        dono.fechar()


@pytest.mark.parametrize("destino", ADAPTADORES)
def test_o_prazo_da_chave_nova_conta_do_pair_e_nao_da_janela(
    diario: Path, destino: str,
) -> None:
    """Ela segura PS + Create aos 50 s da janela (no diário foram 16 s, e a chave viveu só
    os 42 s que sobravam). O controle atende 20 s depois do ``Pair``: aos 70 s da janela,
    depois dos 60 s do prazo velho — e a chave fica, porque o prazo conta do ``Pair``.

    MORDIDA: faça ``Movimento.prazo_desde`` devolver só o ``comecou``.
    """
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    visto = o_controle_do_diario(mundo, relogio, VERDE, acorda_em=20.0)
    central, dono = central_sem_tela(mundo, relogio)
    try:
        rm.ela_pareia(relogio, mundo, central, VERDE, depois_de=50.0)
        feito = central.conectar(destino)
        assert visto["pareou"] is not None and visto["pareou"] - feito.comecou >= 50.0
        assert feito.prazo_desde == visto["pareou"]
        assert feito.publicar()["prazo_desde"] >= feito.publicar()["quando"] + 50.0
        fim = a_vigia_por(central, relogio, VERDE, cr.PRAZO_DO_PENDENTE_S + 5.0)
        assert fim is not None and fim.estado == cr.CHEGOU, f"{fim} — lápides {mundo.lapides}"
        assert mundo.lapides == []
    finally:
        central.fechar(espera=5.0)
        dono.fechar()


def test_a_chave_que_nunca_atende_sai_aos_sessenta_segundos_do_pair(diario: Path) -> None:
    """O outro lado do contrato, que continua: a chave que o controle nunca atende sai como
    meia chave — mas só aos 60 s do ``Pair``, depois de chamada de novo a cada
    :data:`~central_do_radio.REPROVOCAR_S`."""
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    visto = o_controle_do_diario(mundo, relogio, VERDE, acorda_em=1e9)
    central, dono = central_sem_tela(mundo, relogio)
    try:
        rm.ela_pareia(relogio, mundo, central, VERDE)
        central.conectar(QUARTO)
        fim = a_vigia_por(central, relogio, VERDE, cr.PRAZO_DO_PENDENTE_S + 5.0)
        assert fim is not None and (fim.estado, fim.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_PRAZO)
        assert relogio.agora - visto["pareou"] >= cr.PRAZO_DO_PENDENTE_S
        assert mundo.lapides == [(QUARTO, VERDE)]
        chamadas = len(_linha(mundo, "Connect", VERDE))
        assert chamadas >= cr.PRAZO_DO_PENDENTE_S // cr.REPROVOCAR_S - 1, chamadas
        assert mundo.objeto(SALA, VERMELHO) is not None and mundo.objeto(SALA, AZUL) is not None
    finally:
        central.fechar(espera=5.0)
        dono.fechar()
