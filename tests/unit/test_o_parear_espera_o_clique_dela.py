"""O parear espera o clique dela — O-PAREAR-ESPERA-O-CLIQUE-01.

A queixa dela, de 30/09/2026: *«eu não consigo escolher qual o controle vou
conectar e nem clicar nele. ele já vai automaticamente não espera eu clicar no
parear»*. Medido no código e no diário da madrugada: a janela do «Conectar»
pareava o PRIMEIRO controle que a busca achasse, em meio segundo, e a tela o
via em três; e o controle com a chave só do lado dele (o 01:23:40) era pareado
de novo sem modo de parear. <!-- noqa-acento: citação literal dela -->

A decisão (D-3009-O-PAREAR-E-O-CLIQUE-DELA, quem coordena, 30/09/2026, a
validar por ela): nada pareia sem o clique dela no «Parear» da linha.

Todas no rádio de mentira (``radio_de_mentira``), com o ``DonoVivo`` de
verdade por cima. **Nenhuma lê a própria saída:** a central é medida pelos
métodos que chegam ao BlueZ de mentira, e a tela pelo pedido que chega ao
daemon de mentira.

Faixa sintética da casa: ``aa:bb:cc``, octetos 4 e 5 zerados.
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import central_do_radio as cr
from hefesto_dualsense4unix.integrations import diario_do_radio
from tests.unit import radio_de_mentira as rm
from tests.unit.radio_de_mentira import AZUL, FONE, QUARTO, ROXO, SALA, VERDE, VERMELHO


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A trava e o diário numa pasta de teste — nunca os dela, em ``/run``."""
    monkeypatch.setenv(diario_do_radio.ENV_TRAVA, str(tmp_path / "radio.lock"))
    caminho = tmp_path / "radio-diario.jsonl"
    monkeypatch.setenv(diario_do_radio.ENV_DIARIO, str(caminho))
    return caminho


@pytest.fixture()
def relogio() -> rm.Relogio:
    return rm.Relogio()


@pytest.fixture()
def mesa(diario: Path, relogio: rm.Relogio) -> Iterator[Any]:
    """``mesa(mundo)`` → (dono, central): o dono vivo e a central real sobre ele."""
    abertos: list[bd.DonoVivo] = []

    def montar(mundo: rm.RadioDeMentira) -> tuple[bd.DonoVivo, cr.CentralDoRadio]:
        dono = bd.DonoVivo(mundo)
        assert dono.ligar()
        abertos.append(dono)
        central = cr.CentralDoRadio(
            dono=dono, onde_esta=mundo.onde_esta, movimento=mundo.hz,
            esquecer_na_ponte=mundo.esquecer_na_ponte, relogio=relogio,
            dormir=relogio.dormir, sysfs={"listar": lambda _p: [], "raiz": "/nao/existe"})
        return dono, central

    yield montar
    for dono in abertos:
        dono.fechar()


def _mundo(*novos: str) -> rm.RadioDeMentira:
    """O vermelho e o azul no ar na sala; ``novos`` são controles sem chave."""
    mundo = rm.RadioDeMentira()
    mundo.pareado(SALA, VERMELHO)
    mundo.pareado(SALA, AZUL)
    for aparelho in novos:
        mundo.fisicos[aparelho] = rm.Fisico(aparelho, rm.CLASSE_DE_CONTROLE)
    return mundo


def _onde_pareou(mundo: rm.RadioDeMentira) -> list[str]:
    return [c for c, _a in mundo.metodos("Pair")]


# ---------------------------------------------------------------------------
# 1. sem clique, nada pareia
# ---------------------------------------------------------------------------


def test_sem_clique_nada_pareia(mesa: Any, relogio: rm.Relogio) -> None:
    """O verde em PS + Create desde o segundo 2, e a janela inteira passa sem
    o clique dela: nenhum ``Pair``, o ``Pairable`` volta a ``False``, a busca
    acaba «não chegou» sem gesto, e o verde continua em modo de parear.

    MORDIDA: devolva à janela o primeiro controle que ela achar (o
    ``return str(endereco), False`` de 23/09) — o ``Pair`` aparece.
    """
    mundo = _mundo(VERDE)
    _dono, central = mesa(mundo)
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(VERDE))

    feito = central.conectar(QUARTO)

    assert mundo.metodos("Pair") == []
    assert mundo.propriedade_do_adaptador(QUARTO, "Pairable") is False
    assert (feito.estado, feito.motivo, feito.aparelho) == (
        cr.NAO_CHEGOU, cr.MOTIVO_SEM_GESTO, cr.CONECTANDO)
    assert mundo.fisicos[VERDE].pareando is True


# ---------------------------------------------------------------------------
# 2. ela escolhe entre dois
# ---------------------------------------------------------------------------


def test_ela_escolhe_entre_dois(mesa: Any, relogio: rm.Relogio) -> None:
    """O verde aos 2 s e o roxo aos 3 s, os dois em PS + Create; o clique dela
    no roxo aos 5 s. Um ``Pair`` só, no roxo; o verde fica sem chave.

    MORDIDA: devolva à janela o primeiro controle que ela achar — o ``Pair``
    vai para o verde.
    """
    mundo = _mundo(VERDE, ROXO)
    _dono, central = mesa(mundo)
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(VERDE))
    relogio.agendar(3.0, lambda: mundo.segurar_ps_create(ROXO))
    relogio.agendar(5.0, lambda: central.comecar_a_mover(ROXO, QUARTO))

    feito = central.conectar(QUARTO)

    assert _onde_pareou(mundo) == [rm.no_de(QUARTO, ROXO)]
    assert (feito.estado, feito.aparelho, feito.destino) == (cr.CHEGOU, ROXO, QUARTO)
    verde = mundo.objeto(QUARTO, VERDE)
    assert verde is None or verde.get("Paired") is False


# ---------------------------------------------------------------------------
# 3. o clique durante a busca não é «ocupado»
# ---------------------------------------------------------------------------


def test_o_clique_durante_a_busca_nao_e_ocupado(mesa: Any, relogio: rm.Relogio) -> None:
    """Com o «Conectar» no passo do gesto e o roxo já visto pela janela, o
    ``comecar_a_mover`` do roxo volta o movimento em curso: nem a recusa do um
    por vez, nem uma segunda busca.

    MORDIDA: tire a escolha (``_a_escolha_dela``) de antes do ``_ocupada`` no
    ``comecar_a_mover`` — a recusa volta.
    """
    mundo = _mundo(ROXO)
    _dono, central = mesa(mundo)
    respostas: list[cr.Movimento] = []
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(ROXO))
    relogio.agendar(4.0, lambda: respostas.append(central.comecar_a_mover(ROXO, QUARTO)))

    feito = central.conectar(QUARTO)

    (resposta,) = respostas
    assert resposta.motivo != cr.MOTIVO_OCUPADO
    assert (resposta.aparelho, resposta.passo) == (cr.CONECTANDO, cr.PASSO_GESTO)
    assert len(mundo.metodos("StartDiscovery")) == 1
    assert (feito.estado, feito.aparelho) == (cr.CHEGOU, ROXO)


# ---------------------------------------------------------------------------
# 4. a escolha é de qualquer aparelho, e o destino é o da busca
# ---------------------------------------------------------------------------


def test_a_escolha_e_de_qualquer_aparelho(mesa: Any, relogio: rm.Relogio) -> None:
    """Ela escolhe o fone na janela da sala: um ``Pair`` nele, e o CONFERIR
    pelo ``Connected`` do BlueZ — fone não tem ``HID_PHYS``.

    MORDIDA: o ``e_controle=True`` fixo no ``_quem_chegou`` — o CONFERIR
    espera um movimento que fone não tem, e ele não chega.
    """
    mundo = _mundo()
    mundo.fisicos[FONE] = rm.Fisico(FONE, rm.CLASSE_DE_FONE)
    _dono, central = mesa(mundo)
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(FONE))
    relogio.agendar(3.0, lambda: central.comecar_a_mover(FONE, SALA))

    feito = central.conectar(SALA)

    assert _onde_pareou(mundo) == [rm.no_de(SALA, FONE)]
    assert (feito.estado, feito.aparelho, feito.e_controle) == (cr.CHEGOU, FONE, False)
    assert mundo.onde_esta(rm.uniq(FONE)) == "", "o fone não é HID: o kernel não o diz"


def test_o_clique_noutro_destino_que_nao_o_da_busca_recusa(
        mesa: Any, relogio: rm.Relogio) -> None:
    """A busca na sala, e o clique pede o fone no quarto: não é escolha — é a
    recusa do um por vez, e nada pareia.

    MORDIDA: tire da escolha a comparação do destino — o clique do quarto é
    aceito, e o ``Pair`` sai na sala.
    """
    mundo = _mundo()
    mundo.fisicos[FONE] = rm.Fisico(FONE, rm.CLASSE_DE_FONE)
    _dono, central = mesa(mundo)
    respostas: list[cr.Movimento] = []
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(FONE))
    relogio.agendar(3.0, lambda: respostas.append(central.comecar_a_mover(FONE, QUARTO)))

    feito = central.conectar(SALA)

    assert [r.motivo for r in respostas] == [cr.MOTIVO_OCUPADO]
    assert mundo.metodos("Pair") == []
    assert (feito.estado, feito.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_SEM_GESTO)


# ---------------------------------------------------------------------------
# 5. a tela manda a escolha e acha a linha
# ---------------------------------------------------------------------------

PCI = "0000:00:14.0"
#: Esquerda (hci0), Direita (hci1) e Meio (hci2).
ADAPTADORES = ("aa:bb:cc:00:00:09", "aa:bb:cc:00:00:15", "aa:bb:cc:00:00:21")
NOMES = ("Esquerda", "Direita", "Meio")
NOVO = "aa:bb:cc:00:00:3d"


def _id(endereco: str) -> str:
    return endereco.replace(":", "").upper()


class PonteDeMentira:
    """O ``p.resultado`` da tela: guarda o pedido e responde que deu."""

    def __init__(self) -> None:
        self.pedidos: list[tuple[str, dict[str, Any]]] = []

    def resultado(self, metodo: str, timeout: float | None = None, **params: Any) -> Any:
        self.pedidos.append((metodo, dict(params)))
        return {"status": "ok"}


@pytest.fixture()
def tela(monkeypatch: pytest.MonkeyPatch) -> Any:
    """A 08 lendo na hora, com três adaptadores e o DualSense novo que a
    Direita está vendo: classe de controle, com sinal, sem ``Modalias``."""
    from hefesto_dualsense4unix.integrations.bluez_dbus import AdaptadorDoBluez, AparelhoDoBluez
    from hefesto_dualsense4unix.integrations.mesa_de_radio import Mesa
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

    for nome in ("_FUNDO", "_ABERTO", "_CENA_NA_TELA", "_SALA_NA_TELA", "_CHEGADAS"):
        monkeypatch.setattr(a08_conexoes, nome, {})
    monkeypatch.setattr(a08_conexoes, "LER_NA_HORA", True)
    monkeypatch.setattr(a08_conexoes, "_mesa_do_radio", lambda recarregar=False: Mesa())
    monkeypatch.setattr(a08_conexoes, "_ler_o_historico", lambda: {})
    maquina = MaquinaConfig(adaptadores={_id(ADAPTADORES[i]).lower(): {"nome": NOMES[i]}
                                         for i in range(3)})
    monkeypatch.setattr(a08_conexoes, "_ler_a_maquina", lambda: (maquina, {3: PCI}))

    def ler(nome: str = "") -> Any:
        adaptadores = tuple(AdaptadorDoBluez(f"/org/bluez/hci{i}", f"hci{i}",
                                             ADAPTADORES[i].upper(), varrendo=False)
                            for i in range(3))
        novo = AparelhoDoBluez(f"/org/bluez/hci1/dev_{NOVO.upper().replace(':', '_')}",
                               "/org/bluez/hci1", NOVO.upper(), nome=nome, conectado=False,
                               pareado=False, rssi=-55, classe=rm.CLASSE_DE_CONTROLE)
        a08_conexoes._FUNDO.clear()
        monkeypatch.setattr(a08_conexoes, "_ler_o_bluez", lambda: (adaptadores, (novo,)))

    return a08_conexoes, ler


def _campos_com_a_busca_na_direita(a08: Any) -> dict[str, Any]:
    """A busca de pé na Direita, e a caixa Meio aberta por ela.

    MUDOU NA O-CONECTAR-E-UM-INTERRUPTOR-01: a busca é a que a central
    PUBLICA (``busca``), ao lado do movimento sem aparelho; a tela lê dali
    onde ela está. O pedido é o mesmo.
    """
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    a08._ABERTO["lugar"] = _id(ADAPTADORES[2])
    busca = {"aparelho": "", "destino": ADAPTADORES[1], "estado": "esperando",
             "passo": "gesto", "quando": time.time() - 2.0, "e_controle": False}
    publicada = {"adaptador": ADAPTADORES[1], "desde": time.time() - 2.0,
                 "ate": time.time() + 118.0}
    estado = {"controllers": [], "radio_central": {"movimentos": [busca], "proposta": None,
                                                   "busca": publicada}}
    return dict(a08.campos_do_radio(Contexto(state=estado, conectados=[], mesa=[])))


def _texto_visivel(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


@pytest.mark.parametrize("nome", ["", "AA-BB-CC-00-00-3D"], ids=["sem-nome", "alias-endereco"])
def test_a_tela_mostra_o_dualsense_novo_e_manda_a_escolha(tela: Any, nome: str) -> None:
    """A linha do DualSense novo diz «DualSense» com o desenho dele, e nunca o
    endereço — nem quando o BlueZ põe o endereço no ``Alias`` de quem não
    anuncia nome. O «Parear» dela chega ao daemon como ``radio.mover`` com
    aquele aparelho e o adaptador da BUSCA (a Direita), e não o da caixa
    aberta (o Meio).

    MORDIDAS, uma por vez: o ``_mover`` com a trava de volta no
    ``parear_aparelho`` (o gesto levanta «outro movimento está esperando»); o
    ``destino_do_conectar`` no lugar do ``_onde_espera`` (vai o Meio); o
    ``054C`` de volta no ``_perto`` (o tipo vira «outro»); o
    ``or _mac(a.endereco)`` de volta no nome (o endereço vai ao molde).
    """
    from hefesto_dualsense4unix.interface.pacotes import GESTOS, Contexto

    a08, ler = tela
    ler(nome)
    campos = _campos_com_a_busca_na_direita(a08)

    (linha,) = [a for a in a08._CENA_NA_TELA["perto"] if a["id"] == _id(NOVO)]
    assert (linha["tipo"], linha["nome"], linha["adaptador"]) == (
        "controle", "DualSense", _id(ADAPTADORES[1]))
    molde = re.search(r'<template class="painel-molde" data-painel="conectar".*?</template>',
                      campos["radio-moldes"], re.S).group(0)
    visivel = _texto_visivel(molde).upper()
    for forma in (NOVO.upper(), _id(NOVO), NOVO.upper().replace(":", "-")):
        assert forma not in visivel, forma
    assert '<svg class="i ds cheio"' in molde

    ponte = PonteDeMentira()
    feito = GESTOS[("08-conexoes.html", "parear-aparelho")](
        Contexto(state={}, conectados=[], mesa=[]), {"alvo": _id(NOVO)}, ponte)
    assert feito == {"armou": True}
    assert ponte.pedidos == [("radio.mover", {"destino": _id(ADAPTADORES[1]),
                                              "aparelho": _id(NOVO)})]


# ---------------------------------------------------------------------------
# 6. o «Mover» de quem a janela não viu continua recusado
# ---------------------------------------------------------------------------


def test_o_mover_de_quem_a_janela_nao_viu_continua_recusado(
        mesa: Any, relogio: rm.Relogio) -> None:
    """Com o «Conectar» no gesto no quarto, um «Mover» do azul (no ar na sala,
    fora da janela) que chega entre dois tiques volta «ocupado»: nada desliga
    o azul, e o verde que entra em PS + Create depois continua sem ``Pair``.

    MORDIDA: tire da escolha o filtro dos VISTOS — o pedido vira escolha (sem
    recusa), e a janela espera um azul que nunca aparece.
    """
    mundo = _mundo(VERDE)
    _dono, central = mesa(mundo)
    respostas: list[cr.Movimento] = []
    relogio.agendar(1.0, lambda: respostas.append(central.comecar_a_mover(AZUL, QUARTO)))
    relogio.agendar(3.0, lambda: mundo.segurar_ps_create(VERDE))

    feito = central.conectar(QUARTO)

    assert [r.motivo for r in respostas] == [cr.MOTIVO_OCUPADO]
    azul = rm.no_de(SALA, AZUL)
    assert [c for c, _a in mundo.metodos("Disconnect") + mundo.metodos("RemoveDevice")
            if azul in (c, *(str(x) for x in _a))] == []
    assert mundo.onde_esta(rm.uniq(AZUL)) == SALA
    assert mundo.metodos("Pair") == []
    assert (feito.estado, feito.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_SEM_GESTO)


# ---------------------------------------------------------------------------
# 7. o que o adaptador já conhece também se escolhe
# ---------------------------------------------------------------------------


def test_o_que_o_adaptador_ja_conhece_tambem_se_escolhe(
        mesa: Any, relogio: rm.Relogio) -> None:
    """O roxo tem chave no quarto (no ``antes`` da janela, e ``ja_pareado``) e
    ela o liga em PS + Create; o clique dela («Conectar», na linha de quem o
    adaptador conhece) chega ao ``Connect`` no quarto, e ele chega.

    MORDIDA: deixe o filtro do já pareado valer também para o escolhido — ele
    não entra nos VISTOS, o clique é recusado, e ele acaba «não chegou» sem
    ``Connect``.
    """
    mundo = _mundo()
    mundo.pareado(QUARTO, ROXO, conectado=False)
    _dono, central = mesa(mundo)
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(ROXO))
    relogio.agendar(3.0, lambda: central.comecar_a_mover(ROXO, QUARTO))

    feito = central.conectar(QUARTO)

    assert [c for c, _a in mundo.metodos("Connect")] == [rm.no_de(QUARTO, ROXO)]
    assert (feito.estado, feito.aparelho, feito.destino) == (cr.CHEGOU, ROXO, QUARTO)


# ---------------------------------------------------------------------------
# 8. o controle com a chave só do lado dele espera o clique
# ---------------------------------------------------------------------------


def _o_roxo_com_a_chave_so_do_lado_dele() -> rm.RadioDeMentira:
    """O roxo pareado no quarto; o quarto esqueceu a chave (a ponte), o roxo
    não — e ele está desligado."""
    mundo = _mundo()
    mundo.pareado(QUARTO, ROXO)
    mundo.desligar(ROXO)
    mundo.esquecer_na_ponte(QUARTO, ROXO)
    assert mundo.fisicos[ROXO].host == QUARTO and mundo.objeto(QUARTO, ROXO) is None
    return mundo


def test_o_controle_que_chama_o_host_sem_clique_nao_pareia(
        mesa: Any, relogio: rm.Relogio) -> None:
    """O 01:23:40 da madrugada dela: ligado só com o PS, ele chama o quarto, que
    não tem mais a chave dele. Com a busca de pé ali e sem o clique dela,
    nenhum ``Pair``.

    MORDIDA: devolva à janela o primeiro controle que ela achar — o ``Pair``
    sai no primeiro passo, sem clique, como às 01:23:40.
    """
    mundo = _o_roxo_com_a_chave_so_do_lado_dele()
    _dono, central = mesa(mundo)
    relogio.agendar(2.0, lambda: mundo.chamar_o_host(ROXO))

    feito = central.conectar(QUARTO)

    assert mundo.metodos("Pair") == []
    assert (feito.estado, feito.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_SEM_GESTO)


def test_o_controle_que_chama_o_host_pareia_no_clique_dela(
        mesa: Any, relogio: rm.Relogio, monkeypatch: pytest.MonkeyPatch) -> None:
    """O mesmo roxo, e o clique dela um passo depois: um ``Pair`` no quarto, e
    ele chega. A linha dele é «DualSense» na lista do quarto — com o sinal que
    o objeto tiver; o ``RSSI`` desse objeto não está medido (a prova 0 b da
    sprint fica para o aparelho), e a régua o dá."""
    from hefesto_dualsense4unix.integrations.mesa_de_radio import Mesa
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08

    mundo = _o_roxo_com_a_chave_so_do_lado_dele()
    dono, central = mesa(mundo)
    relogio.agendar(2.0, lambda: mundo.chamar_o_host(ROXO, rssi=-61))
    relogio.agendar(3.0, rm.o_clique_no_parear(central, ROXO))

    vistos: list[Any] = []
    relogio.agendar(2.5, lambda: vistos.append(tuple(dono.aparelhos() or ())))
    feito = central.conectar(QUARTO)

    assert _onde_pareou(mundo) == [rm.no_de(QUARTO, ROXO)]
    assert (feito.estado, feito.aparelho, feito.destino) == (cr.CHEGOU, ROXO, QUARTO)

    monkeypatch.setattr(a08, "_mesa_do_radio", lambda recarregar=False: Mesa())
    monkeypatch.setattr(a08, "_CHEGADAS", {})
    perto = a08._perto(vistos[0], tuple(dono.adaptadores() or ()), [])
    assert [(a["id"], a["nome"], a["tipo"], a["forca"]) for a in perto] == [
        (_id(ROXO), "DualSense", "controle", -61)]
