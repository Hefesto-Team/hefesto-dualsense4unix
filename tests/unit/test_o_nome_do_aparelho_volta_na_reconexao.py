"""O nome que ela dá volta na reconexão — O-RADIO-CONECTA-ONDE-ELA-MANDA-01, item 4.

O relato dela, 26/09/2026:

    *«Eu mudei o nome do dispositivo quando eu conectar os dispositivos bt
    novamente eu quero que o nome deles sejam lidos novamente e não voltem todas
    as vezes quie eu mudar»* <!-- noqa-acento: citação literal dela -->

O nome mora no ``Alias`` do BlueZ, UM POR OBJETO — um objeto por adaptador que
conhece o controle. O ``Pair`` num adaptador novo cria um objeto novo, com o
nome de fábrica; e a faxina da central esquece a chave velha logo depois. Era
assim que cada «Conectar» noutro adaptador apagava o nome dela.

O QUE ESTA RÉGUA SEGURA, para qualquer adaptador de origem e de destino:

1. o «Conectar» num adaptador novo leva o nome que ela deu ao objeto NOVO,
   lido de qualquer outro objeto do MESMO controle antes de a chave velha sair
   (o ``_dar_o_nome`` da central). MEDIDO em 26/09: os seis pares de
   adaptadores já passavam antes desta sprint — a régua é a guarda de que o
   destino que agora é o da caixa aberta não perdeu o nome no caminho;
2. o nome de fábrica não é nome: o controle que ela nunca renomeou chega sem
   escrita de ``Alias``, e o nome dela nunca vai para outro controle;
3. a tela mostra o nome dela em toda linha do controle — no ar, desligado, em
   qualquer adaptador em que ele tenha chave.

O QUE ELA NÃO SEGURA AINDA (pendente, escrito no relato da sprint): com a
ÚLTIMA chave do controle esquecida (o X no único adaptador), não sobra objeto de
onde copiar. A cura durável é o nome no ``maquina.json`` pelo endereço do
controle, e o campo mora em ``utils/maquina.py``, fora da posse desta sprint.

Faixa sintética da casa: ``aa:bb:cc``, octetos 4 e 5 zerados.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import central_do_radio as cr
from tests.unit import radio_de_mentira as rm
from tests.unit.radio_de_mentira import AZUL, QUARTO, ROXO, SALA, VARANDA, VERMELHO
from tests.unit.test_o_conectar_pareia_no_adaptador_escolhido import (
    Bancada,
    ela_segura_ps_create,
    id_da_tela,
    preparar_a_tela,
    preparar_o_diario,
)

FABRICA = rm.NOME_DE_FABRICA[rm.CLASSE_DE_CONTROLE]


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return preparar_o_diario(tmp_path, monkeypatch)


@pytest.fixture()
def a08(monkeypatch: pytest.MonkeyPatch) -> Any:
    return preparar_a_tela(monkeypatch)


def _conectar_em(bancada: Bancada, destino: str, quem: str) -> cr.Movimento:
    """Ela abre ``destino``, clica «Conectar» e segura PS + Create em ``quem``."""
    bancada.cena()
    if bancada.cena().get("aberto") != id_da_tela(destino):
        bancada.gesto("abrir-adaptador", alvo=id_da_tela(destino))
    bancada.cena()
    ela_segura_ps_create(bancada.mundo, bancada.relogio, quem)
    bancada.gesto("conectar-aparelho")
    bancada.esperar_a_central()
    return next(m for m in bancada.central.movimentos() if m.destino == destino)


PARES = [(o, d) for o in (SALA, QUARTO, VARANDA) for d in (SALA, QUARTO, VARANDA) if o != d]


@pytest.mark.parametrize(("origem", "destino"), PARES)
def test_o_conectar_noutro_adaptador_leva_o_nome_dela(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, origem: str, destino: str,
) -> None:
    """O vermelho se chama «André» na origem. Ela o desliga, abre outro adaptador
    e clica «Conectar»: ele chega com «André» no objeto NOVO, e a tela o mostra
    assim — em qualquer par de adaptadores.

    MORDIDA: faça o ``_dar_o_nome`` da central não escrever — o objeto novo
    nasce com o nome de fábrica e esta régua reprova nos seis pares.
    """
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(origem, VERMELHO, nome="André")
    mundo.pareado(origem, AZUL, nome="Vitória")
    mundo.desligar(VERMELHO)
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        feito = _conectar_em(bancada, destino, VERMELHO)
        assert (feito.estado, feito.aparelho) == (cr.CHEGOU, VERMELHO)
        assert mundo.objeto(destino, VERMELHO)["Alias"] == "André"
        assert mundo.objeto(origem, AZUL)["Alias"] == "Vitória", "o nome foi para outro"
        cena = bancada.cena()
        (linha,) = [a for a in cena["aparelhos"] if str(a["id"]).lower() == rm.uniq(VERMELHO)
                    and a.get("lugar") == id_da_tela(destino)]
        assert linha["nome"] == "André"
    finally:
        bancada.fechar()


def test_sem_nome_dela_o_objeto_novo_fica_com_o_de_fabrica(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O nome de fábrica não é nome: o controle que ela nunca renomeou chega
    sem escrita de ``Alias`` nenhuma."""
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(SALA, VERMELHO)
    mundo.desligar(VERMELHO)
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        _conectar_em(bancada, VARANDA, VERMELHO)
        assert mundo.objeto(VARANDA, VERMELHO)["Alias"] == FABRICA
        assert [e for e in mundo.escritas if e[2] == "Alias"] == []
    finally:
        bancada.fechar()


def test_a_tela_mostra_o_nome_dela_em_toda_chave_do_controle(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O roxo se chama «Vitória» só no objeto da varanda; desligado, ele tem
    chave também na sala — e a linha «Desligado» da sala diz «Vitória», não o
    nome de fábrica. O nome é do CONTROLE, lido pelo endereço.

    MORDIDA: faça ``_os_desligados`` ler só o ``Alias`` do próprio objeto — a
    linha da sala volta ao nome de fábrica.
    """
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(VARANDA, ROXO, conectado=False, nome="Vitória")
    mundo.pareado(SALA, ROXO, host=False)
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        cena = bancada.cena()
        linhas = {a["lugar"]: a for a in cena["aparelhos"] if a.get("desligado")}
        assert set(linhas) == {id_da_tela(VARANDA), id_da_tela(SALA)}
        assert {a["nome"] for a in linhas.values()} == {"Vitória"}
    finally:
        bancada.fechar()
