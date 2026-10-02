"""O «Conectar» é um interruptor — O-CONECTAR-E-UM-INTERRUPTOR-01.

As duas frases dela, de 30/09/2026: *«pq tá aparecendo o conectar ali?»*, sobre
a pílula verde «Segure PS + Create» acesa na raia Direita com o painel fechado;
e *«falta um switch ali no lado esquerdo do conectar pra clicar e ativar igual
o botão modo freestyle na aba jogar»*. <!-- noqa-acento: citação literal dela -->

MEDIDO antes da cura (01/10, sobre ``da7d842a5``): o gesto ``conectar-aparelho``
sem alvo mandava ``radio.mover`` e a central abria ``StartDiscovery`` no
adaptador aberto; não havia verbo que parasse a busca; a janela tinha os 30 s
do «Mover»; a pílula e o «ocupado» liam a IDADE do movimento; e a busca que
ninguém respondeu virava «Não Conectou».

A decisão (D-3009-O-CONECTAR-E-UM-INTERRUPTOR, D-3009-O-TETO-DA-BUSCA e
D-3009-A-BUSCA-DESLIGADA-NAO-E-FALHA, quem coordena, 30/09/2026, a validar por
ela): a busca é um estado da central, publicado (``busca``), com o verbo
``radio.busca.set`` de valor absoluto e o interruptor «Procurar» à esquerda do
«+ Conectar», que só abre o painel.

A central é a ``CentralDoRadio`` de verdade, com o ``DonoVivo`` de verdade por
cima do rádio de mentira com física, e o pedido atravessa o tratador real do
daemon. A tela é o pacote da 08 com o que a central PUBLICOU. **Nenhuma régua
lê o HTML que a tela montou a partir do que ela mesma disse:** a central é
medida pelos métodos que chegam ao BlueZ de mentira, e a tela pelo pedido que
chega ao daemon.

Faixa sintética da casa: ``aa:bb:cc``, octetos 4 e 5 zerados.
"""

from __future__ import annotations

import asyncio
import re
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import central_do_radio as cr
from hefesto_dualsense4unix.integrations import gesto_de_pareamento as gp
from tests.unit import radio_de_mentira as rm
from tests.unit.radio_de_mentira import AZUL, QUARTO, ROXO, SALA, VARANDA, VERDE, VERMELHO
from tests.unit.test_o_conectar_pareia_no_adaptador_escolhido import (
    ADAPTADORES,
    Bancada,
    id_da_tela,
    preparar_a_tela,
    preparar_o_diario,
)

RAIZ = Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
#: O fio do movimento, o único que a parada segura.
FIO_DA_CENTRAL = "hefesto-central-mover"


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return preparar_o_diario(tmp_path, monkeypatch)


@pytest.fixture()
def a08(monkeypatch: pytest.MonkeyPatch) -> Any:
    return preparar_a_tela(monkeypatch)


class RadioComHora(rm.RadioDeMentira):
    """O rádio de mentira que anota a hora DO RELÓGIO DA CENTRAL em toda chamada
    e em toda escrita — é assim que «em até 1 s» e «aos 120 s» se medem."""

    def __init__(self, relogio: rm.Relogio, **extra: Any) -> None:
        super().__init__(**extra)
        self.relogio = relogio
        #: ``(método ou propriedade, adaptador, valor, hora)``.
        self.com_hora: list[tuple[str, str, Any, float]] = []

    def _anotar(self, nome: str, caminho: str, valor: Any) -> None:
        adaptador = next((e for e, h in rm.HCIS.items()
                          if caminho == h or caminho.startswith(h + "/")), "")
        self.com_hora.append((nome, adaptador, valor, self.relogio()))

    def chamar(self, destino: str, caminho: str, interface: str, metodo: str,
               assinatura: str, argumentos: Any, *, espera: float) -> bd.Escrita:
        self._anotar(metodo, caminho, tuple(argumentos))
        return super().chamar(destino, caminho, interface, metodo, assinatura, argumentos,
                              espera=espera)

    def escrever(self, caminho: str, interface: str, nome: str, assinatura: str, valor: Any,
                 *, espera: float) -> bd.Escrita:
        self._anotar(nome, caminho, valor)
        return super().escrever(caminho, interface, nome, assinatura, valor, espera=espera)

    def horas(self, nome: str, adaptador: str, valor: Any = None) -> list[float]:
        return [h for n, a, v, h in self.com_hora
                if n == nome and a == adaptador and (valor is None or v == valor)]


class Parada:
    """Segura o fio da central quando o relógio de mentira chega a um instante.

    Sem isto a janela de 120 s passaria num piscar — o relógio anda meio
    segundo a cada volta da espera. ``segurar_em(0)`` segura na primeira volta
    (a janela já aberta e publicada); ``soltar`` deixa o fio ir até o fim.
    """

    def __init__(self, relogio: rm.Relogio) -> None:
        self.relogio = relogio
        self.ate: float | None = None
        self.parou = threading.Event()
        self._siga = threading.Event()
        relogio.durante = self._durante

    def _durante(self) -> None:
        if threading.current_thread().name != FIO_DA_CENTRAL:
            return
        ate = self.ate
        if ate is None or self.relogio.agora < ate:
            return
        self.ate = None
        self.parou.set()
        self._siga.wait(30.0)
        self._siga.clear()

    def segurar_em(self, instante: float) -> None:
        self.parou.clear()
        self.ate = instante

    def seguir(self) -> None:
        self._siga.set()

    def soltar(self) -> None:
        self.ate = None
        self._siga.set()


def mundo_da_madrugada(relogio: rm.Relogio) -> RadioComHora:
    """Dois controles no ar na sala (com som), e o verde novo, desligado, na mão dela."""
    mundo = RadioComHora(relogio)
    mundo.pareado(SALA, VERMELHO)
    mundo.pareado(SALA, AZUL)
    mundo.fisicos[VERDE] = rm.Fisico(VERDE, rm.CLASSE_DE_CONTROLE)
    return mundo


def montar(a08: Any, monkeypatch: pytest.MonkeyPatch, mundo: RadioComHora | None = None,
           **extra: Any) -> tuple[Bancada, Parada]:
    relogio = mundo.relogio if mundo is not None else rm.Relogio()
    mundo = mundo if mundo is not None else mundo_da_madrugada(relogio)
    bancada = Bancada(a08, monkeypatch, mundo, relogio, **extra)
    return bancada, Parada(relogio)


def ligar(bancada: Bancada, parada: Parada, onde: str) -> dict[str, Any]:
    """O «Procurar» ligado em ``onde`` pelo tratador real, com o fio da central
    seguro dentro da janela já aberta."""
    parada.segurar_em(0.0)
    resposta = bancada.ponte.resultado("radio.busca.set", ligada=True, destino=id_da_tela(onde))
    assert isinstance(resposta, dict)
    assert parada.parou.wait(5.0), "a central não abriu a janela"
    return resposta


def desligar(bancada: Bancada, parada: Parada) -> dict[str, Any]:
    """O «Procurar» desligado pelo tratador real; o fio solto logo depois, para
    acabar o movimento como ele acaba no produto."""
    soltura = threading.Timer(0.3, parada.soltar)
    soltura.start()
    try:
        resposta = bancada.ponte.resultado("radio.busca.set", ligada=False)
    finally:
        soltura.cancel()
        parada.soltar()
    assert isinstance(resposta, dict)
    return resposta


def tique(a08: Any, ctx: Any) -> dict[str, Any]:
    """Uma volta da tela com um ``Contexto`` dado (o BlueZ relido)."""
    a08._esquecer("bluez")
    return dict(a08.campos_do_radio(ctx))


def aos(ctx: Any, segundos: float) -> Any:
    """O que a central publica ``segundos`` depois do começo: o ``quando`` dos
    movimentos e a hora da busca vão para trás — a tela vive em hora de parede,
    e o relógio de mentira só anda dentro da central."""
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    estado = dict(ctx.state)
    central = dict(estado["radio_central"])
    central["movimentos"] = [dict(m, quando=float(m["quando"]) - segundos)
                             for m in central.get("movimentos") or ()]
    if isinstance(central.get("busca"), dict):
        busca = central["busca"]
        central["busca"] = dict(busca, desde=busca["desde"] - segundos,
                                ate=busca["ate"] - segundos)
    estado["radio_central"] = central
    return Contexto(state=estado, conectados=ctx.conectados, mesa=ctx.mesa)


def nao_conectou(cena: dict[str, Any]) -> list[tuple[str, str]]:
    return [(str(a["lugar"]), str(a.get("aparelho") or "")) for a in cena["aparelhos"]
            if a.get("nao_conectou")]


def posicao(onde: str) -> int:
    return ADAPTADORES.index(onde)


# ---------------------------------------------------------------------------
# 1. abrir o painel não liga o rádio
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("aberto", ADAPTADORES)
def test_abrir_o_painel_nao_liga_o_radio(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, aberto: str,
) -> None:
    """O «+ Conectar» só abre o painel: nenhum pedido ao daemon, nenhum
    ``StartDiscovery``, nenhum movimento; o painel diz «Conectar», e não
    «Procurando», e o interruptor segue apagado. No desenho, o «Procurar» fica
    à esquerda do «+ Conectar», que não apaga mais com a busca.

    MORDIDA: devolva o ``_mover`` ao ``conectar_aparelho`` sem alvo — o pedido
    sai, e a busca abre.
    """
    bancada, _parada = montar(a08, monkeypatch)
    try:
        a08._ABERTO["lugar"] = id_da_tela(aberto)
        bancada.cena()
        assert bancada.gesto("conectar-aparelho") == {"armou": True}
        assert bancada.ponte.chamadas == [], "o «+ Conectar» pediu ao rádio"
        assert bancada.mundo.metodos("StartDiscovery") == []
        assert bancada.central.movimentos() == ()
        campos = bancada.tique()
        assert campos["radio-procurando"] == a08.PROCURAR_DESLIGADO
        assert 'data-painel="conectar" data-alvo="" data-titulo="Conectar">' in (
            campos["radio-moldes"])
    finally:
        bancada.fechar()

    mockup = (RAIZ / "mockup" / "08-conexoes.html").read_text(encoding="utf-8")
    cabecalho = re.search(r'(<button class="cadeado[^>]*data-gesto="radio-procurar"[^>]*>.*?'
                          r'</button>)\s*(<button[^>]*id="rd-b-conectar"[^>]*>)', mockup, re.S)
    assert cabecalho, "o «Procurar» não está à esquerda do «+ Conectar»"
    assert "radio-ocupado" not in cabecalho.group(2), "o «+ Conectar» ainda apaga com a busca"


# ---------------------------------------------------------------------------
# 2. desligar para o rádio
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("onde", ADAPTADORES)
def test_desligar_para_o_radio_em_ate_um_segundo(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, onde: str,
) -> None:
    """Ligada e desligada pelo ``radio.busca.set``: o ``StopDiscovery`` e o
    ``Pairable`` falso chegam ao MESMO adaptador em até 1 s do relógio da
    central, a central publica ``busca: None``, e o movimento acaba
    ``desligada``, não ``sem_gesto``. A tela não faz «Não Conectou» dele (a
    régua 5, primeira metade).

    MORDIDA: faça o ``ligada: false`` só apagar o campo publicado, sem fechar a
    janela — o ``StopDiscovery`` só vem no teto.
    """
    bancada, parada = montar(a08, monkeypatch)
    mundo = bancada.mundo
    try:
        ligada = ligar(bancada, parada, onde)
        assert ligada["status"] == "ok", ligada
        assert id_da_tela(ligada["busca"]["adaptador"]) == id_da_tela(onde), ligada
        assert mundo.propriedade_do_adaptador(onde, "Discovering") is True
        assert mundo.propriedade_do_adaptador(onde, "Pairable") is True
        pedido_em = bancada.relogio()

        resposta = desligar(bancada, parada)
        bancada.esperar_a_central()

        assert resposta == {"status": "ok", "busca": None}, resposta
        (parou,) = mundo.horas("StopDiscovery", onde)
        assert parou - pedido_em <= 1.0, f"o StopDiscovery veio {parou - pedido_em:.1f} s depois"
        fechou = mundo.horas("Pairable", onde, False)
        assert fechou and fechou[-1] - pedido_em <= 1.0, fechou
        assert mundo.propriedade_do_adaptador(onde, "Pairable") is False
        assert bancada.central.publicar()["busca"] is None
        (fim,) = bancada.central.movimentos()
        assert (fim.estado, fim.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_DESLIGADA), fim
        assert nao_conectou(bancada.cena()) == [], "a busca desligada virou «Não Conectou»"
    finally:
        parada.soltar()
        bancada.fechar()


def test_desligar_sem_busca_nao_toca_no_radio(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pedir o estado que já vale responde ``ok`` sem tocar no rádio."""
    bancada, _parada = montar(a08, monkeypatch)
    try:
        assert bancada.ponte.resultado("radio.busca.set", ligada=False) == {
            "status": "ok", "busca": None}
        assert [m for _c, _i, m, _a in bancada.mundo.chamadas
                if m in ("StartDiscovery", "StopDiscovery")] == []
        assert bancada.central.movimentos() == ()
    finally:
        bancada.fechar()


# ---------------------------------------------------------------------------
# 3. o interruptor e a pílula mostram o que a central publica
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("onde", ADAPTADORES)
def test_o_interruptor_e_a_pilula_leem_a_busca_da_central(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, onde: str,
) -> None:
    """Com a busca ligada num dos três adaptadores, o interruptor diz LIGADO e
    a ``radio-conectando`` acende só na posição dele; desligada, em 30 tiques
    seguidos, nenhum dos dois — mesmo com um movimento «esperando» sem
    aparelho, de 5 s, no que a central publica.

    MORDIDA: volte o ``conectando`` para a idade do movimento — a pílula acende
    com a busca já desligada.
    """
    bancada, parada = montar(a08, monkeypatch)
    try:
        ligar(bancada, parada, onde)
        campos = bancada.tique()
        assert campos["radio-procurando"] == a08.PROCURAR_LIGADO
        esperado = ["", "", ""]
        esperado[posicao(onde)] = "sim"
        assert campos["radio-conectando"] == esperado
        assert 'data-titulo="Procurando" data-pulso="1"' in campos["radio-moldes"]

        desligar(bancada, parada)
        bancada.esperar_a_central()
        ctx = bancada.ctx()
        sobra = cr.Movimento(cr.CONECTANDO, onde, cr.ESPERANDO, cr.PASSO_GESTO,
                             quando=time.time() - 5.0).publicar()
        ctx.state["radio_central"]["movimentos"].append(sobra)
        assert ctx.state["radio_central"]["busca"] is None
        for n in range(30):
            campos = tique(a08, ctx)
            assert campos["radio-procurando"] == a08.PROCURAR_DESLIGADO, f"tique {n}"
            assert campos["radio-conectando"] == ["", "", ""], f"tique {n}"
    finally:
        parada.soltar()
        bancada.fechar()


# ---------------------------------------------------------------------------
# 4 e 5. o teto, só do «Conectar», e a busca que acaba não é «Não Conectou»
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("onde", ADAPTADORES)
def test_o_teto_apaga_a_busca_sozinho_aos_cento_e_vinte_segundos(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, onde: str,
) -> None:
    """Aos 90 s a janela da busca ainda está aberta, o interruptor aceso, a
    tela segue ``ocupado`` e não há «Não Conectou» (a idade não vale para a
    busca). Aos 120 s a central fecha a janela (o ``StopDiscovery``), publica
    ``busca: None``, e o interruptor apaga no tique seguinte — sem «Não
    Conectou», porque ninguém escolheu ninguém.

    MORDIDAS, uma por vez: tire o teto (a busca com os 30 s do «Mover») — aos
    90 s ela já fechou; volte o ramo da idade no ``_os_que_nao_conectaram`` —
    aos 90 s a linha aparece; tire a busca do ``_ainda_espera`` — aos 90 s a
    tela solta o ``ocupado``; tire o filtro do motivo — o teto vira linha.
    """
    bancada, parada = montar(a08, monkeypatch)
    mundo = bancada.mundo
    try:
        ligar(bancada, parada, onde)
        (abriu,) = mundo.horas("StartDiscovery", onde)
        parada.segurar_em(abriu + 90.0)
        parada.seguir()
        assert parada.parou.wait(10.0), "a busca acabou antes dos 90 s"
        assert mundo.propriedade_do_adaptador(onde, "Discovering") is True
        assert mundo.horas("StopDiscovery", onde) == []
        assert bancada.central.publicar()["busca"] is not None
        ctx = aos(bancada.ctx(), 90.0)
        campos = tique(a08, ctx)
        cena = dict(a08._CENA_NA_TELA)
        assert campos["radio-procurando"] == a08.PROCURAR_LIGADO
        assert cena["ocupado"] is True, "a tela soltou a busca pela idade"
        assert nao_conectou(cena) == [], "a busca de 90 s virou «Não Conectou»"

        parada.soltar()
        bancada.esperar_a_central()
        (parou,) = mundo.horas("StopDiscovery", onde)
        assert gp.SEGUNDOS_MAX <= parou - abriu <= gp.SEGUNDOS_MAX + 1.0, parou - abriu
        assert bancada.central.publicar()["busca"] is None
        campos = bancada.tique()
        assert campos["radio-procurando"] == a08.PROCURAR_DESLIGADO
        assert nao_conectou(dict(a08._CENA_NA_TELA)) == [], "o teto virou «Não Conectou»"
    finally:
        parada.soltar()
        bancada.fechar()


def test_o_mover_segue_com_os_trinta_segundos_dele(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O teto é só da busca do «Procurar»: o «Mover» do vermelho para o quarto,
    sem o gesto dela, fecha a janela aos 30 s do mesmo relógio, e é «Não
    Conectou» (ela mandou um controle, e ele não chegou).

    MORDIDA: ponha os 120 s no ``self._segundos`` da central — o «Mover» espera
    o teto da busca.
    """
    bancada, parada = montar(a08, monkeypatch)
    mundo = bancada.mundo
    try:
        assert bancada.central.comecar_a_mover(VERMELHO, QUARTO).estado == cr.ESPERANDO
        bancada.esperar_a_central()
        (abriu,) = mundo.horas("StartDiscovery", QUARTO)
        (parou,) = mundo.horas("StopDiscovery", QUARTO)
        assert gp.SEGUNDOS_DA_JANELA <= parou - abriu <= gp.SEGUNDOS_DA_JANELA + 1.0, (
            parou - abriu)
        (fim,) = bancada.central.movimentos()
        assert (fim.estado, fim.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_SEM_GESTO), fim
        assert nao_conectou(bancada.cena()) == [(id_da_tela(QUARTO), id_da_tela(VERMELHO))]
    finally:
        parada.soltar()
        bancada.fechar()


def test_o_parear_que_nao_chega_faz_a_linha(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """«Não Conectou» fica para o que ela mandou e não chegou: com a busca
    ligada no quarto, ela segura PS + Create no verde e clica em «Parear», e o
    ``Pair`` falha — a linha do verde aparece no quarto."""
    bancada, _parada = montar(a08, monkeypatch)
    mundo = bancada.mundo
    try:
        mundo.pair_falha = True
        rm.ela_pareia(bancada.relogio, mundo, bancada.central, VERDE)
        resposta = bancada.ponte.resultado("radio.busca.set", ligada=True,
                                           destino=id_da_tela(QUARTO))
        assert resposta["status"] == "ok", resposta
        bancada.esperar_a_central()
        (fim,) = bancada.central.movimentos()
        assert (fim.aparelho, fim.estado, fim.motivo) == (
            VERDE, cr.NAO_CHEGOU, cr.MOTIVO_NAO_PAREOU), fim
        assert nao_conectou(bancada.cena()) == [(id_da_tela(QUARTO), id_da_tela(VERDE))]
    finally:
        bancada.fechar()


# ---------------------------------------------------------------------------
# 6. a busca própria não é «Outro programa»
# ---------------------------------------------------------------------------


def test_a_busca_do_hefesto_nao_e_outro_programa(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O ``Discovering`` do adaptador da busca não acende a marca «varrendo» e
    não manda o adaptador para o fim da D8 — nem na tela, nem na central. Outro
    programa procurando noutro adaptador (as Configurações do COSMIC) acende a
    marca nele, com ou sem a busca dela.

    A busca liga no adaptador que a D8 escolhe sem ela (um dos dois vazios):
    é ali que «quem varre vai para o fim» mudaria a escolha.

    MORDIDAS, uma por vez: tire a subtração da tela (a marca acende na busca
    dela, e a D8 da tela foge dela); tire a da central (a D8 da central foge).
    """
    bancada, parada = montar(a08, monkeypatch)
    mundo = bancada.mundo
    try:
        cena = bancada.cena()
        sem_busca = str(cena["destino_da_central"])
        assert id_da_tela(bancada.central.escolher_destino() or "") == sem_busca
        onde = next(e for e in ADAPTADORES if id_da_tela(e) == sem_busca)
        outro = next(e for e in (QUARTO, VARANDA) if e != onde)
        assert onde != SALA, "a D8 desta mesa escolheu o adaptador cheio"

        a08._ABERTO["lugar"] = sem_busca
        ligar(bancada, parada, onde)
        campos = bancada.tique()
        cena = dict(a08._CENA_NA_TELA)
        assert campos["radio-varrendo"] == ["", "", ""], "a busca dela virou «outro programa»"
        assert cena["destino_da_central"] == sem_busca, "a D8 da tela fugiu da busca dela"
        bancada.relogio.agora += cr.VALIDADE_DOS_ADAPTADORES_S  # a foto da central venceu
        assert id_da_tela(bancada.central.escolher_destino() or "") == sem_busca, (
            "a D8 da central fugiu da busca dela")

        # As Configurações do COSMIC procuram no outro adaptador: aquela marca é de outro.
        mundo._mudar(rm.HCIS[outro], bd.ADAPTADOR, "Discovering", True)
        esperado = ["", "", ""]
        esperado[posicao(outro)] = "sim"
        assert bancada.tique()["radio-varrendo"] == esperado
        desligar(bancada, parada)
        bancada.esperar_a_central()
        assert bancada.tique()["radio-varrendo"] == esperado
    finally:
        parada.soltar()
        bancada.fechar()


# ---------------------------------------------------------------------------
# 7. valor absoluto, nos três estados
# ---------------------------------------------------------------------------


def test_o_mesmo_clique_entregue_duas_vezes_deixa_a_busca_como_pedida(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tela diz DESLIGADO e o clique chega duas vezes antes do tique (a
    segunda entrega do piloto): os dois pedidos dizem ``ligada: true`` no
    quarto, o rádio abre UMA busca, e ela fica ligada. O que não é ``click``
    não manda nada.

    MORDIDA: faça a tela inverter o que mostra a cada clique (o «inverta») —
    a segunda entrega desliga a busca.
    """
    bancada, parada = montar(a08, monkeypatch)
    try:
        a08._ABERTO["lugar"] = id_da_tela(QUARTO)
        bancada.cena()
        assert bancada.gesto("radio-procurar", evento="change") is None
        assert bancada.ponte.chamadas == []

        parada.segurar_em(0.0)
        assert bancada.gesto("radio-procurar") == {"armou": True}
        assert parada.parou.wait(5.0)
        segunda: Any
        try:
            segunda = bancada.gesto("radio-procurar")
        except RuntimeError as erro:
            segunda = erro
        pedido = ("radio.busca.set", {"ligada": True, "destino": id_da_tela(QUARTO)})
        assert bancada.ponte.chamadas == [pedido, pedido], "a segunda entrega não repetiu o pedido"
        assert segunda == {"armou": True}, segunda
        assert len(bancada.mundo.horas("StartDiscovery", QUARTO)) == 1
        busca = bancada.central.publicar()["busca"]
        assert busca is not None and id_da_tela(busca["adaptador"]) == id_da_tela(QUARTO)
    finally:
        parada.soltar()
        bancada.fechar()


def test_com_o_daemon_mudo_o_interruptor_e_o_travessao_e_nao_manda_nada(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem ``radio_central`` no estado (o daemon não respondeu), o campo é o
    travessão — nenhuma classe casa, a pílula fica apagada sem afirmar nada — e
    o gesto levanta sem mandar pedido.

    MORDIDA: trate o travessão como DESLIGADO — o clique liga uma busca que
    ninguém viu.
    """
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    bancada, _parada = montar(a08, monkeypatch)
    try:
        mudo = Contexto(state={"controllers": []}, conectados=[], mesa=[])
        assert tique(a08, mudo)["radio-procurando"] == a08.TRAVESSAO_DO_PROCURAR
        with pytest.raises(RuntimeError):
            bancada.gesto("radio-procurar")
        assert bancada.ponte.chamadas == []
        assert bancada.mundo.metodos("StartDiscovery") == []
    finally:
        bancada.fechar()


# ---------------------------------------------------------------------------
# 8. os quatro no ar
# ---------------------------------------------------------------------------


def test_ligar_e_desligar_nao_tira_ninguem_do_ar_nem_do_lugar(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quatro controles em três adaptadores (P1 e P2 na sala, P3 no quarto, P4
    na varanda): ligar e desligar a busca em cada um não gera ``Disconnect``
    nem ``RemoveDevice``, ninguém sai do adaptador em que está, e o número de
    cada um na tela é o mesmo.

    MORDIDA: faça o ligar desconectar quem está no adaptador da busca (a forma
    do ``_desligar_e_esquecer_a_origem``) — o rádio recebe ``Disconnect``.
    """
    relogio = rm.Relogio()
    mundo = RadioComHora(relogio)
    for onde, quem in ((SALA, VERMELHO), (SALA, AZUL), (QUARTO, VERDE), (VARANDA, ROXO)):
        mundo.pareado(onde, quem)
    jogadores = {rm.uniq(VERMELHO): 1, rm.uniq(AZUL): 2, rm.uniq(VERDE): 3, rm.uniq(ROXO): 4}
    bancada, parada = montar(a08, monkeypatch, mundo, jogadores=jogadores)

    def quem_esta_onde() -> set[tuple[str, str, Any]]:
        bancada.tique()
        return {(str(a["id"]), str(a["lugar"]), a.get("jogador"))
                for a in a08._CENA_NA_TELA["aparelhos"]
                if a.get("tipo") == "controle" and not a.get("nao_conectou")}

    try:
        antes = quem_esta_onde()
        assert {j for _i, _l, j in antes} == {1, 2, 3, 4}
        for onde in ADAPTADORES:
            assert ligar(bancada, parada, onde)["status"] == "ok"
            assert desligar(bancada, parada)["status"] == "ok"
            bancada.esperar_a_central()
            assert mundo.metodos("Disconnect") == [], onde
            assert mundo.metodos("RemoveDevice") == [] and mundo.lapides == [], onde
            assert {e: f.conectado_em for e, f in mundo.fisicos.items()} == {
                VERMELHO: SALA, AZUL: SALA, VERDE: QUARTO, ROXO: VARANDA}, onde
            assert quem_esta_onde() == antes, onde
    finally:
        parada.soltar()
        bancada.fechar()


# ---------------------------------------------------------------------------
# 9. a peça é a do «Modo Freestyle»
# ---------------------------------------------------------------------------


def _folha(fonte: str, prefixo: str) -> dict[str, dict[str, str]]:
    """As regras ``.cadeado…`` de uma folha, por seletor, sem o ``prefixo``."""
    regras: dict[str, dict[str, str]] = {}
    for seletor, corpo in re.findall(r"^\s*(" + re.escape(prefixo) + r"\.cadeado[^{]*)\{([^}]*)\}",
                                     fonte, re.M):
        chave = seletor[len(prefixo):].strip()
        regras[chave] = dict(
            (p.split(":", 1)[0].strip(), p.split(":", 1)[1].strip())
            for p in corpo.split(";") if ":" in p)
    return regras


def test_a_peca_e_a_do_modo_freestyle() -> None:
    """A folha ``.cadeado`` da seção do rádio tem os mesmos valores da aba
    Jogar — a altura, o ponto e o verde de ``ligada`` —, lidos dos dois
    arquivos: a peça é copiada, e não importada de outra aba.

    MORDIDA: mude a altura de uma das duas — reprova.
    """
    jogar = _folha((INTERFACE / "aba01.py").read_text(encoding="utf-8"), "")
    radio = _folha((INTERFACE / "aba08.py").read_text(encoding="utf-8"), ".radio ")
    assert set(jogar) == {".cadeado", ".cadeado .p", ".cadeado.ligada", ".cadeado.ligada .p"}
    assert radio == jogar
    assert jogar[".cadeado"]["height"] == "26px"


# ---------------------------------------------------------------------------
# 10. o verbo não segura o laço
# ---------------------------------------------------------------------------


class _JanelaQueDorme:
    def fechar(self) -> None:
        time.sleep(2.0)


class _CentralQueDemora:
    """A central de mentira cujo ``fechar`` da janela dorme 2 s."""

    def __init__(self) -> None:
        self.janela = _JanelaQueDorme()

    def ligar_a_busca(self, ligada: bool, destino: str | None = None) -> dict[str, Any]:
        if not ligada:
            self.janela.fechar()
        return {"status": "ok", "busca": None}


@pytest.mark.asyncio
async def test_o_verbo_nao_segura_o_laco_do_servico() -> None:
    """Uma tarefa do laço que acorda a cada 10 ms continua rodando durante o
    ``radio.busca.set`` — o tratador roda a central num fio.

    MORDIDA: chame a central direto, sem ``asyncio.to_thread`` — o laço para
    os 2 s inteiros.
    """
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    class _Daemon(IpcHandlersMixin):
        pass

    eu = _Daemon()
    eu.daemon = SimpleNamespace(_central_do_radio=_CentralQueDemora())  # type: ignore[attr-defined]
    voltas = 0

    async def laco() -> None:
        nonlocal voltas
        while True:
            await asyncio.sleep(0.01)
            voltas += 1

    tarefa = asyncio.create_task(laco())
    try:
        await asyncio.sleep(0.05)
        antes = voltas
        resposta = await eu._handle_radio_busca_set({"ligada": False})
        durante = voltas - antes
    finally:
        tarefa.cancel()
    assert resposta == {"status": "ok", "busca": None}
    assert durante >= 50, f"o laço deu {durante} voltas em 2 s"


@pytest.mark.parametrize("params", [{}, {"ligada": "sim"}, {"ligada": True, "destino": 7}])
def test_o_verbo_recusa_o_que_nao_e_o_contrato(params: dict[str, Any]) -> None:
    """``ligada`` é booleano e ``destino``, quando vem, é o endereço."""
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    class _Daemon(IpcHandlersMixin):
        pass

    eu = _Daemon()
    eu.daemon = SimpleNamespace(_central_do_radio=_CentralQueDemora())  # type: ignore[attr-defined]
    with pytest.raises(ValueError):
        asyncio.run(eu._handle_radio_busca_set(params))
