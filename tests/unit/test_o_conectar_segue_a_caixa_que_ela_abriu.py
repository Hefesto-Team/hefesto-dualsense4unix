"""O «Conectar» segue a caixa que ela abriu — O-CONECTAR-SEGUE-A-CAIXA-QUE-ELA-ABRIU-01.

Nasceu da conferência da A-CAIXA-FICA-ONDE-ELA-ABRIU-01 (28/09/2026): a tela
passou a pedir ao rádio que a busca vá junto com o chip, e a central respondia
``ocupado``. A foto 34 dela, 26/09:

    *«toda hora mesmo selecionando meio o negocio vai pra outra aba da direita
    mesmo comigo tentando sincroniZar o controle.»* <!-- noqa-acento: citação literal dela -->

MEDIDO antes da cura (28/09, com a ``CentralDoRadio`` real, o ``DonoVivo`` real
por cima do rádio de mentira e o tratador real do daemon): com o «Conectar» no
gesto num adaptador, o ``radio.mover`` do chip de outro voltava ``ocupado`` nos
seis pares de três adaptadores, e também com um «Mover» esperando; o «não
chegou» com a trava de outro motor, o ``_falhou`` depois do ``Pair`` e a vigia
que levanta no prazo deixavam a meia chave no destino — e o «Conectar» seguinte
ali nem via o controle (o destino já o «conhecia»).

O que esta régua segura:

1. **o destino muda no pedido do chip**: com o movimento ainda antes do
   aparelho (preparando, desligando ou no gesto), o chip de outro adaptador
   fecha a janela onde estava e a abre no novo, com a janela e o prazo
   recomeçando; o último clique dela vence;
2. **a meia chave sai em toda saída sem chegada**: sem a trava, ela fica devida
   e sai na primeira vez em que a central segura a trava — a faxina, ou o
   próximo movimento, antes de a janela dele abrir;
3. **o pedido sem aparelho não vira um «Conectar» anônimo por cima de um
   «Mover»**: o chip leva o «Mover» dela, com o mesmo controle.

Um por vez continua: outro aparelho, ou o movimento que já passou do gesto,
recebe ``ocupado``. Vale em qualquer adaptador e em qualquer ordem — a matriz
cobre os seis pares de três.

Faixa sintética da casa: ``aa:bb:cc``, octetos 4 e 5 zerados.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import central_do_radio as cr
from hefesto_dualsense4unix.integrations import diario_do_radio
from hefesto_dualsense4unix.integrations import gesto_de_pareamento as gp
from tests.unit import radio_de_mentira as rm
from tests.unit.radio_de_mentira import AZUL, QUARTO, ROXO, SALA, VARANDA, VERDE, VERMELHO
from tests.unit.test_a_caixa_fica_onde_ela_abriu import CHIP, _cartao
from tests.unit.test_o_conectar_pareia_no_adaptador_escolhido import (
    Bancada,
    BuscaDePe,
    PonteQueVaiAoDaemon,
    id_da_tela,
    mundo_da_madrugada,
    onde_buscou,
    onde_pareou,
    preparar_a_tela,
    preparar_o_diario,
)

TRES = (SALA, QUARTO, VARANDA)
#: Todo par (onde a busca está, o chip que ela clica), nos três adaptadores.
PARES = [(busca, chip) for busca in TRES for chip in TRES if busca != chip]
#: O «Mover» do vermelho (que mora na sala) para cada destino, e o chip de
#: cada um dos outros dois adaptadores — inclusive a sala, a casa de antes.
MOVERES = [(destino, chip) for destino in (QUARTO, VARANDA) for chip in TRES if chip != destino]
#: Um adaptador que não está na máquina.
FORA_DA_MAQUINA = "aa:bb:cc:00:00:d4"


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return preparar_o_diario(tmp_path, monkeypatch)


@pytest.fixture()
def a08(monkeypatch: pytest.MonkeyPatch) -> Any:
    return preparar_a_tela(monkeypatch)


class Mesa:
    """A central real, o dono real e o tratador real do daemon sobre o rádio de mentira."""

    def __init__(self, mundo: rm.RadioDeMentira, **extra: Any) -> None:
        self.mundo, self.relogio = mundo, rm.Relogio()
        self.dono = bd.DonoVivo(mundo)
        assert self.dono.ligar()
        self.central = cr.CentralDoRadio(
            dono=self.dono, onde_esta=mundo.onde_esta, movimento=mundo.hz,
            esquecer_na_ponte=mundo.esquecer_na_ponte, relogio=self.relogio,
            dormir=self.relogio.dormir, sysfs={"listar": lambda _p: [], "raiz": "/nao/existe"},
            **extra)
        self.ponte = PonteQueVaiAoDaemon(self.central)

    def chip(self, destino: str) -> dict[str, Any]:
        """O chip do «Procurando»: o ``radio.mover`` SEM aparelho, como a tela manda."""
        resposta = self.ponte.resultado("radio.mover", destino=destino)
        assert isinstance(resposta, dict)
        return resposta

    def no_gesto(self) -> cr.Movimento:
        (movimento,) = [m for m in self.central.movimentos() if m.em_curso]
        assert movimento.passo == cr.PASSO_GESTO, movimento
        return movimento

    def esperar(self, teto: float = 15.0) -> tuple[cr.Movimento, ...]:
        """O fio da central acaba (a janela, o ``Pair`` e a conferência)."""
        fim = time.monotonic() + teto
        while time.monotonic() < fim:
            movimentos = self.central.movimentos()
            if movimentos and not any(m.em_curso for m in movimentos):
                return movimentos
            time.sleep(0.01)
        raise AssertionError(f"a central não terminou: {self.central.movimentos()}")

    def de(self, aparelho: str) -> cr.Movimento:
        """O movimento deste aparelho — que tem de existir."""
        movimento = self.central.movimento_de(aparelho)
        assert movimento is not None, self.central.movimentos()
        return movimento

    def objeto(self, adaptador: str, aparelho: str) -> dict[str, Any]:
        """O objeto do aparelho naquele adaptador — que tem de existir."""
        objeto = self.mundo.objeto(adaptador, aparelho)
        assert objeto is not None, (adaptador, aparelho)
        return objeto

    def fechar(self) -> None:
        self.central.fechar(espera=5.0)
        self.dono.fechar()


@pytest.fixture()
def fechar() -> Iterator[list[Any]]:
    """O que a régua abriu fecha no fim, mesmo quando ela reprova no meio."""
    abertos: list[Any] = []
    yield abertos
    for coisa in reversed(abertos):
        coisa()


def _a_janela_de_cada_um_fechou(mundo: rm.RadioDeMentira) -> None:
    for adaptador in TRES:
        assert mundo.propriedade_do_adaptador(adaptador, "Discovering") is False, adaptador
        assert mundo.propriedade_do_adaptador(adaptador, "Pairable") is False, adaptador


def _o_conectar_no_gesto(mesa: Mesa, busca: BuscaDePe, onde: str) -> cr.Movimento:
    """O «Conectar» dela em ``onde``, com a janela aberta esperando o gesto."""
    assert mesa.central.comecar_a_conectar(onde).estado == cr.ESPERANDO
    assert busca.dentro.wait(5.0), "a central não abriu a janela"
    movimento = mesa.no_gesto()
    assert (movimento.aparelho, movimento.destino) == (cr.CONECTANDO, onde)
    return movimento


def _o_mover_no_gesto(mesa: Mesa, busca: BuscaDePe, destino: str) -> cr.Movimento:
    """O «Mover» do vermelho, da sala para ``destino``, com a janela esperando o gesto."""
    assert mesa.central.comecar_a_mover(VERMELHO, destino).estado == cr.ESPERANDO
    assert busca.dentro.wait(5.0), "a central não abriu a janela"
    movimento = mesa.no_gesto()
    assert (movimento.aparelho, movimento.destino, movimento.origens) == (
        VERMELHO, destino, (SALA,))
    return movimento


# ---------------------------------------------------------------------------
# 1. o destino muda no pedido do chip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("onde_busca", "chip"), PARES)
def test_o_chip_leva_a_busca_do_conectar_para_o_adaptador_dele(
    diario: Path, fechar: list[Any], onde_busca: str, chip: str,
) -> None:
    """A régua (1) da sprint: com a central no gesto num adaptador, o chip de
    outro abre a janela nele e fecha a de onde estava; o controle que ela segura
    depois pareia no do chip, e em nenhum outro.

    MORDIDA: o ``ocupado`` de hoje — tire o :meth:`CentralDoRadio._mudar_o_destino`
    do ``comecar_a_conectar`` e o chip volta recusado em todos os pares.
    """
    mesa = Mesa(mundo_da_madrugada())
    fechar.append(mesa.fechar)
    busca = BuscaDePe(mesa.relogio)
    fechar.append(busca.soltar)
    _o_conectar_no_gesto(mesa, busca, onde_busca)

    resposta = mesa.chip(chip)
    assert resposta["status"] == "ok", resposta
    assert (resposta["movimento"]["aparelho"], resposta["movimento"]["destino"]) == (
        cr.CONECTANDO, chip)

    rm.ela_pareia(mesa.relogio, mesa.mundo, mesa.central, VERDE)
    busca.soltar()
    (fim,) = mesa.esperar()
    assert (fim.estado, fim.aparelho, fim.destino) == (cr.CHEGOU, VERDE, chip), fim
    assert onde_buscou(mesa.mundo) == [rm.HCIS[onde_busca], rm.HCIS[chip]]
    assert onde_pareou(mesa.mundo) == [rm.HCIS[chip]]
    assert mesa.mundo.onde_esta(rm.uniq(VERDE)) == chip
    _a_janela_de_cada_um_fechou(mesa.mundo)


def test_a_janela_e_o_prazo_recomecam_no_destino_novo(diario: Path, fechar: list[Any]) -> None:
    """Ela clica o chip aos 50 s de uma janela de 30 e de um prazo de 60. No
    destino novo a janela é inteira (o gesto 25 s depois ainda pareia) e o
    prazo também: o ``Pair`` que não confirma continua «esperando», em vez de
    cair no prazo do começo. A tela conta o dela do ``quando`` publicado, que
    recomeça junto.

    MORDIDA: guarde o destino novo sem recomeçar o ``comecou`` — a conferência
    corta no prazo do começo e o movimento vira «não chegou» (``prazo``).
    """
    mesa = Mesa(mundo_da_madrugada())
    fechar.append(mesa.fechar)
    busca = BuscaDePe(mesa.relogio)
    fechar.append(busca.soltar)
    fins: list[cr.Movimento] = []
    # O corpo do fio, sem a vigia depois: a régua lê o que a conferência devolve.
    fio = threading.Thread(target=lambda: fins.append(mesa.central.conectar(SALA)),
                           name="hefesto-central-mover")
    fio.start()
    fechar.append(lambda: fio.join(timeout=15.0))
    assert busca.dentro.wait(5.0), "a central não abriu a janela"
    antes = mesa.no_gesto()
    mesa.relogio.agora = antes.comecou + 50.0

    assert mesa.chip(VARANDA)["status"] == "ok"
    mesa.mundo.pair_mente = True
    rm.ela_pareia(mesa.relogio, mesa.mundo, mesa.central, VERDE, depois_de=25.0)
    busca.soltar()
    fio.join(timeout=15.0)

    (pendente,) = fins
    assert (pendente.estado, pendente.passo, pendente.motivo, pendente.destino) == (
        cr.ESPERANDO, cr.PASSO_CONFERINDO, cr.MOTIVO_SEM_CONFIRMACAO, VARANDA), pendente
    assert pendente.comecou >= antes.comecou + 50.0, "o prazo não recomeçou com a janela"
    assert pendente.quando > antes.quando, "o «quando» da tela não recomeçou"
    assert onde_pareou(mesa.mundo) == [rm.HCIS[VARANDA]]


@pytest.mark.parametrize(("onde_busca", "chip"), PARES)
def test_o_ultimo_clique_dela_vence(
    diario: Path, fechar: list[Any], onde_busca: str, chip: str,
) -> None:
    """Dois chips antes de a busca andar: vale o último. Voltar ao adaptador da
    busca desfaz o pedido (nenhuma janela nova); o terceiro vai direto para ele,
    sem abrir no do meio."""
    mesa = Mesa(mundo_da_madrugada())
    fechar.append(mesa.fechar)
    busca = BuscaDePe(mesa.relogio)
    fechar.append(busca.soltar)
    _o_conectar_no_gesto(mesa, busca, onde_busca)
    terceiro = next(a for a in TRES if a not in (onde_busca, chip))

    assert mesa.chip(chip)["status"] == "ok"
    assert mesa.chip(onde_busca)["status"] == "ok"
    assert mesa.chip(chip)["status"] == "ok"
    assert mesa.chip(terceiro)["status"] == "ok"
    rm.ela_pareia(mesa.relogio, mesa.mundo, mesa.central, VERDE)
    busca.soltar()
    (fim,) = mesa.esperar()
    assert (fim.estado, fim.destino) == (cr.CHEGOU, terceiro), fim
    assert onde_buscou(mesa.mundo) == [rm.HCIS[onde_busca], rm.HCIS[terceiro]]


def test_o_chip_no_ultimo_instante_da_janela_ainda_leva_a_busca(
    diario: Path, fechar: list[Any],
) -> None:
    """Ela clica o chip quando a janela de 30 s acaba: o pedido chegou antes
    do fim, e o fim não vira «não chegou» — a busca vai para o chip, inteira.

    MORDIDA: tire da saída do gesto (``_sair_do_gesto``) a pergunta pelo
    pedido — a janela que acabou fecha «não chegou» no adaptador de antes.
    """
    mesa = Mesa(mundo_da_madrugada())
    fechar.append(mesa.fechar)
    busca = BuscaDePe(mesa.relogio)
    fechar.append(busca.soltar)
    antes = _o_conectar_no_gesto(mesa, busca, SALA)
    mesa.relogio.agora = antes.comecou + gp.SEGUNDOS_DA_JANELA

    assert mesa.chip(QUARTO)["status"] == "ok"
    rm.ela_pareia(mesa.relogio, mesa.mundo, mesa.central, VERDE)
    busca.soltar()
    (fim,) = mesa.esperar()
    assert (fim.estado, fim.aparelho, fim.destino) == (cr.CHEGOU, VERDE, QUARTO), fim
    assert onde_buscou(mesa.mundo) == [rm.HCIS[SALA], rm.HCIS[QUARTO]]


def test_o_controle_que_aparece_junto_com_o_chip_pareia_no_adaptador_do_chip(
    diario: Path, fechar: list[Any],
) -> None:
    """O verde aparece na janela da sala no mesmo instante em que ela clica o
    chip do quarto. O último que ela escolheu vence: nenhum ``Pair`` na sala, e
    o verde chega no quarto.

    MORDIDA: tire da saída do gesto (``_sair_do_gesto``) a pergunta pelo
    pedido — o verde pareia na sala, que ela acabou de deixar.
    """
    mesa = Mesa(mundo_da_madrugada())
    fechar.append(mesa.fechar)
    busca = BuscaDePe(mesa.relogio)
    fechar.append(busca.soltar)
    _o_conectar_no_gesto(mesa, busca, SALA)

    assert mesa.chip(QUARTO)["status"] == "ok"
    mesa.mundo.segurar_ps_create(VERDE)
    assert mesa.mundo.objeto(SALA, VERDE) is not None, "a janela da sala não o achou"
    # O clique dela no «Parear» do verde, na lista do quarto, onde a busca está.
    mesa.relogio.agendar(1.0, rm.o_clique_no_parear(mesa.central, VERDE))
    busca.soltar()
    (fim,) = mesa.esperar()
    assert (fim.estado, fim.aparelho, fim.destino) == (cr.CHEGOU, VERDE, QUARTO), fim
    assert onde_pareou(mesa.mundo) == [rm.HCIS[QUARTO]]


class JanelaDePe:
    """Uma janela que ainda está aberta — o que a espera do gesto deixa para trás
    quando sai por um pedido, e não pelo fim."""

    @property
    def aberta(self) -> bool:
        return True

    def abrir_a_janela(self) -> str:
        return ""

    def candidatos(self) -> tuple[Any, ...]:
        return ()

    def parear(self, endereco: str) -> gp.Resultado:
        raise AssertionError("esta régua não pareia")

    def fechar(self) -> None:
        return None


def test_a_janela_que_um_pedido_desfeito_interrompeu_recomeca(
    diario: Path, fechar: list[Any],
) -> None:
    """A espera do gesto sai porque ela pediu outro destino, e ela o desfaz no
    mesmo instante (clicou de volta): a janela ainda estava de pé, e isso não é
    «não chegou» — o movimento segue, e a janela recomeça onde estava. Acabada
    a janela de verdade, aí sim.

    MORDIDA: tire do ``_sem_gesto`` a pergunta pela janela — o clique de volta
    fecha a busca «não chegou».
    """
    mesa = Mesa(mundo_da_madrugada())
    fechar.append(mesa.fechar)
    no_gesto = mesa.central._guardar(cr.Movimento(
        cr.CONECTANDO, SALA, cr.ESPERANDO, cr.PASSO_GESTO, comecou=mesa.relogio()))
    comeco = mesa.relogio()
    assert mesa.central._sem_gesto(no_gesto, JanelaDePe(), comeco) is None
    assert mesa.central.movimentos() == (no_gesto,)

    mesa.relogio.agora = comeco + gp.SEGUNDOS_DA_JANELA
    fim = mesa.central._sem_gesto(no_gesto, JanelaDePe(), comeco)
    assert fim is not None and (fim.estado, fim.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_SEM_GESTO)


def test_voltar_ao_chip_da_busca_desfaz_o_pedido(diario: Path, fechar: list[Any]) -> None:
    mesa = Mesa(mundo_da_madrugada())
    fechar.append(mesa.fechar)
    busca = BuscaDePe(mesa.relogio)
    fechar.append(busca.soltar)
    _o_conectar_no_gesto(mesa, busca, QUARTO)

    assert mesa.chip(VARANDA)["status"] == "ok"
    assert mesa.chip(QUARTO)["status"] == "ok"
    rm.ela_pareia(mesa.relogio, mesa.mundo, mesa.central, VERDE)
    busca.soltar()
    (fim,) = mesa.esperar()
    assert (fim.estado, fim.destino) == (cr.CHEGOU, QUARTO), fim
    assert onde_buscou(mesa.mundo) == [rm.HCIS[QUARTO]], "a janela andou sem ela pedir"


def test_o_pedido_que_a_busca_nao_atendeu_nao_vale_para_a_proxima(
    diario: Path, fechar: list[Any],
) -> None:
    """Ela clica o chip do quarto, e no mesmo instante o roxo volta sozinho pelo
    pareamento antigo: o «Conectar» acaba «chegou» ali, sem andar. O pedido do
    quarto era daquela busca; o «Conectar» seguinte, na varanda, busca na
    varanda.

    MORDIDA: tire a limpeza do pedido do começo do movimento (``_comecar``) — o
    «Conectar» seguinte vai para o quarto que ninguém pediu para ele.
    """
    mundo = mundo_da_madrugada()
    mundo.pareado(VARANDA, ROXO, conectado=False)
    mesa = Mesa(mundo)
    fechar.append(mesa.fechar)
    busca = BuscaDePe(mesa.relogio)
    fechar.append(busca.soltar)
    _o_conectar_no_gesto(mesa, busca, SALA)

    assert mesa.chip(QUARTO)["status"] == "ok"
    mundo.apertar_ps(ROXO)
    busca.soltar()
    (voltou,) = mesa.esperar()
    assert (voltou.estado, voltou.motivo, voltou.aparelho) == (
        cr.CHEGOU, cr.MOTIVO_PELO_PAREAMENTO_ANTIGO, ROXO), voltou

    rm.ela_pareia(mesa.relogio, mundo, mesa.central, VERDE)
    fim = mesa.central.conectar(VARANDA)
    assert (fim.estado, fim.aparelho, fim.destino) == (cr.CHEGOU, VERDE, VARANDA), fim
    assert onde_buscou(mundo) == [rm.HCIS[SALA], rm.HCIS[VARANDA]]


@pytest.mark.parametrize(("onde_busca", "chip"), PARES)
def test_a_tela_mostra_a_busca_no_adaptador_do_chip(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, onde_busca: str, chip: str,
) -> None:
    """O que ela vê, pela tela de verdade (o pacote da 08, o gesto do chip, o
    tratador real e a central real): com a busca já no destino novo, o chip
    aceso é o dela, o «Segure PS + Create» está no cartão daquele adaptador e
    em nenhum outro, e os botões seguem apagados enquanto a busca espera.

    MORDIDA: o ``ocupado`` de hoje (o ``_mudar_o_destino`` fora) — o gesto do
    chip levanta, e o «Segure PS + Create» fica no cartão de antes.
    """
    mundo = mundo_da_madrugada()
    relogio = rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    busca = BuscaDePe(relogio)
    try:
        bancada.cena()
        bancada.gesto("escolher-adaptador", alvo=id_da_tela(onde_busca))
        bancada.cena()
        assert bancada.gesto("conectar-aparelho") == {"armou": True}
        assert busca.dentro.wait(5.0), "a central não abriu a janela"

        bancada.cena()
        assert bancada.gesto("escolher-adaptador", alvo=id_da_tela(chip)) == {"armou": True}
        assert bancada.ponte.chamadas[-1] == ("radio.mover", {"destino": id_da_tela(chip)})
        # A busca anda e a janela nova fica de pé, esperando o gesto dela.
        de_pe = BuscaDePe(relogio)
        busca.soltar()
        assert de_pe.dentro.wait(5.0), "a janela nova não abriu"
        busca = de_pe
        assert onde_buscou(mundo) == [rm.HCIS[onde_busca], rm.HCIS[chip]]

        campos = bancada.tique()
        cena = dict(a08._CENA_NA_TELA)
        assert cena["ocupado"] is True
        assert cena["aberto"] == cena["destino_do_conectar"] == id_da_tela(chip)
        acesos = [lid for aceso, lid in CHIP.findall(campos["radio-moldes"]) if aceso == "true"]
        assert acesos == [id_da_tela(chip)]
        _a_busca_acende_so_no(campos, a08, chip)
    finally:
        busca.soltar()
        bancada.fechar()


# ---------------------------------------------------------------------------
# 3. o chip leva o «Mover» dela, com o mesmo controle
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("destino", "chip"), MOVERES)
def test_o_chip_leva_o_mover_do_mesmo_controle(
    diario: Path, fechar: list[Any], destino: str, chip: str,
) -> None:
    """A régua (3) da sprint: um «Mover» de ``aa:bb:cc:00:00:01`` espera no
    destino, e o chip de outro adaptador leva o MESMO «Mover» para lá. O verde,
    novo, também está pareando — e antes do vermelho: um «Conectar» anônimo o
    pegaria. Quem pareia é o vermelho, no adaptador do chip, com o nome dela.

    MORDIDA: trate o pedido do chip como «Conectar» (o ``_mudar_o_destino``
    devolvendo ``None`` quando o que espera tem aparelho, ou o movimento
    trocando de chave para ``CONECTANDO``) — o chip treme, ou o verde chega no
    lugar do vermelho.
    """
    mundo = mundo_da_madrugada()
    mundo.escrever(rm.no_de(SALA, VERMELHO), bd.APARELHO, "Alias", "s", "Vitória", espera=1.0)
    mesa = Mesa(mundo)
    fechar.append(mesa.fechar)
    busca = BuscaDePe(mesa.relogio)
    fechar.append(busca.soltar)
    _o_mover_no_gesto(mesa, busca, destino)

    resposta = mesa.chip(chip)
    assert resposta["status"] == "ok", resposta
    assert (resposta["movimento"]["aparelho"], resposta["movimento"]["destino"]) == (
        VERMELHO, chip)

    mesa.relogio.agendar(1.0, lambda: mundo.segurar_ps_create(VERDE))
    mesa.relogio.agendar(2.0, lambda: mundo.segurar_ps_create(VERMELHO))
    busca.soltar()
    (fim,) = mesa.esperar()
    assert (fim.estado, fim.aparelho, fim.destino) == (cr.CHEGOU, VERMELHO, chip), fim
    assert chip not in fim.origens, "o destino novo ficou como origem"
    assert fim.nome == "Vitória"
    assert [(c.rsplit("/", 1)[0], bd.endereco_do_aparelho(c)) for c, _a in mundo.metodos("Pair")
            ] == [(rm.HCIS[chip], VERMELHO)]
    assert mundo.onde_esta(rm.uniq(VERMELHO)) == chip
    assert mesa.objeto(chip, VERMELHO)["Alias"] == "Vitória"
    assert onde_buscou(mundo) == [rm.HCIS[destino], rm.HCIS[chip]]
    _a_janela_de_cada_um_fechou(mundo)


def test_o_mesmo_controle_pedido_de_novo_tambem_segue_a_caixa(
    diario: Path, fechar: list[Any],
) -> None:
    """Todo chamador que pede o MESMO movimento para outro lugar: o ``radio.mover``
    com o aparelho do «Mover» que espera leva a busca junto, como o chip."""
    mesa = Mesa(mundo_da_madrugada())
    fechar.append(mesa.fechar)
    busca = BuscaDePe(mesa.relogio)
    fechar.append(busca.soltar)
    _o_mover_no_gesto(mesa, busca, QUARTO)

    resposta = mesa.ponte.resultado("radio.mover", aparelho=rm.uniq(VERMELHO), destino=VARANDA)
    assert resposta["status"] == "ok", resposta
    mesa.relogio.agendar(2.0, lambda: mesa.mundo.segurar_ps_create(VERMELHO))
    busca.soltar()
    (fim,) = mesa.esperar()
    assert (fim.estado, fim.aparelho, fim.destino) == (cr.CHEGOU, VERMELHO, VARANDA), fim


def test_o_destino_novo_nao_vira_origem(diario: Path, fechar: list[Any]) -> None:
    """O chip leva o «Mover» de volta à sala, a casa de antes. A sala deixa de
    ser origem: com o vermelho no ar ali e o movimento dele ainda não medido, a
    vigia NÃO o diz «voltou» — ele chegou onde ela pediu.

    MORDIDA: deixe o destino novo nas ``origens`` — a vigia fecha «não chegou»
    (``voltou``) com o controle no adaptador que ela escolheu.
    """
    mundo = mundo_da_madrugada()
    mesa = Mesa(mundo)
    fechar.append(mesa.fechar)
    busca = BuscaDePe(mesa.relogio)
    fechar.append(busca.soltar)
    fins: list[cr.Movimento] = []
    fio = threading.Thread(target=lambda: fins.append(mesa.central.mover(VERMELHO, QUARTO)),
                           name="hefesto-central-mover")
    fio.start()
    assert busca.dentro.wait(5.0)
    assert mesa.chip(SALA)["status"] == "ok"
    mundo.fisicos[VERMELHO].hz = 0.0
    mesa.relogio.agendar(2.0, lambda: mundo.segurar_ps_create(VERMELHO))
    busca.soltar()
    fio.join(timeout=15.0)

    (pendente,) = fins
    assert (pendente.estado, pendente.passo, pendente.destino) == (
        cr.ESPERANDO, cr.PASSO_CONFERINDO, SALA), pendente
    assert SALA not in pendente.origens
    mesa.central.vigiar()
    assert mesa.de(VERMELHO).estado == cr.ESPERANDO, "a vigia disse «voltou»"
    mundo.fisicos[VERMELHO].hz = 250.0
    mesa.central.vigiar()
    fim = mesa.de(VERMELHO)
    assert (fim.estado, fim.destino) == (cr.CHEGOU, SALA), fim


# ---------------------------------------------------------------------------
# o um por vez continua: só o destino do mesmo movimento muda, e só no gesto
# ---------------------------------------------------------------------------


def test_outro_aparelho_e_adaptador_fora_da_maquina_seguem_recusados(
    diario: Path, fechar: list[Any],
) -> None:
    """O chip só leva o movimento que espera. Outro controle, um aparelho
    para o «Conectar» anônimo, ou um adaptador que não está na máquina: a
    recusa de sempre, e a busca fica onde estava."""
    mesa = Mesa(mundo_da_madrugada())
    fechar.append(mesa.fechar)
    busca = BuscaDePe(mesa.relogio)
    fechar.append(busca.soltar)
    _o_mover_no_gesto(mesa, busca, QUARTO)

    assert mesa.ponte.resultado("radio.mover", aparelho=rm.uniq(AZUL),
                                destino=VARANDA)["status"] == "ocupado"
    assert mesa.chip(FORA_DA_MAQUINA)["status"] == "ocupado"
    busca.soltar()
    mesa.esperar()
    assert onde_buscou(mesa.mundo) == [rm.HCIS[QUARTO]]

    mesa2 = Mesa(mundo_da_madrugada())
    fechar.append(mesa2.fechar)
    busca2 = BuscaDePe(mesa2.relogio)
    fechar.append(busca2.soltar)
    _o_conectar_no_gesto(mesa2, busca2, QUARTO)
    assert mesa2.ponte.resultado("radio.mover", aparelho=rm.uniq(AZUL),
                                 destino=VARANDA)["status"] == "ocupado"
    busca2.soltar()
    mesa2.esperar()
    assert onde_buscou(mesa2.mundo) == [rm.HCIS[QUARTO]]


@pytest.mark.parametrize("passo", [cr.PASSO_PAREANDO, cr.PASSO_CONFERINDO])
def test_depois_do_gesto_o_destino_nao_muda(diario: Path, fechar: list[Any], passo: str) -> None:
    """Achado o controle, o ``Pair`` e a conferência são do adaptador em que ele
    apareceu: o chip recebe ``ocupado``, e o movimento fica como estava."""
    mesa = Mesa(mundo_da_madrugada())
    fechar.append(mesa.fechar)
    em_voo = mesa.central._guardar(cr.Movimento(
        VERDE, QUARTO, cr.ESPERANDO, passo, pareou_no_destino=passo == cr.PASSO_CONFERINDO,
        comecou=mesa.relogio()))
    assert mesa.chip(VARANDA)["status"] == "ocupado"
    assert mesa.central.movimento_de(VERDE) == em_voo


# ---------------------------------------------------------------------------
# 2. a meia chave sai em toda saída sem chegada
# ---------------------------------------------------------------------------


def _o_verde_pareou_e_nao_conectou(mesa: Mesa, destino: str) -> cr.Movimento:
    """O ``Pair`` do verde dá e ele não conecta (o branco do diário dela)."""
    mesa.mundo.pair_mente = True
    rm.ela_pareia(mesa.relogio, mesa.mundo, mesa.central, VERDE)
    feito = mesa.central.conectar(destino)
    assert (feito.estado, feito.passo, feito.aparelho) == (
        cr.ESPERANDO, cr.PASSO_CONFERINDO, VERDE)
    assert mesa.objeto(destino, VERDE)["Paired"] is True
    return feito


def _sem_a_trava(trabalho: Any) -> None:
    """O ``trabalho`` num fio, com OUTRO motor segurando a trava do rádio."""
    with diario_do_radio.trava_do_radio("vigia"):
        fio = threading.Thread(target=trabalho, name="hefesto-central-vigia")
        fio.start()
        fio.join(timeout=10.0)
        assert not fio.is_alive()


@pytest.mark.parametrize("destino", TRES)
def test_o_nao_chegou_sem_a_trava_deve_a_meia_chave_e_ela_sai_na_faxina(
    diario: Path, fechar: list[Any], destino: str,
) -> None:
    """O prazo vence com outro motor segurando a trava: o «não chegou» sai (a
    central não fica ocupada por uma chave), e a chave, que não se escreve sem
    a trava, fica DEVIDA. A primeira volta da faxina com a trava livre a tira —
    só ali, com a lápide —, e os controles no ar na sala ficam.

    MORDIDA: tire a dívida do ``_fechar_sem_chegar`` sem a trava — a faxina
    não tem o que pagar e a meia chave fica no adaptador.
    """
    mesa = Mesa(mundo_da_madrugada(), prazo_da_trava_s=0.2)
    fechar.append(mesa.fechar)
    feito = _o_verde_pareou_e_nao_conectou(mesa, destino)
    mesa.relogio.agora = feito.comecou + cr.PRAZO_DO_PENDENTE_S

    _sem_a_trava(mesa.central.vigiar)
    fim = mesa.de(VERDE)
    assert (fim.estado, fim.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_PRAZO)
    assert not mesa.central.em_curso
    assert mesa.mundo.lapides == [], "a chave saiu sem a trava"

    assert mesa.central.tirar_as_meias_chaves() == ((destino, VERDE),)
    assert mesa.mundo.objeto(destino, VERDE) is None, "a meia chave ficou no adaptador"
    assert mesa.mundo.lapides == [(destino, VERDE)]
    assert mesa.mundo.objeto(SALA, VERMELHO) is not None
    assert mesa.mundo.objeto(SALA, AZUL) is not None
    assert mesa.central.tirar_as_meias_chaves() == (), "a mesma chave saiu duas vezes"


class NomesEmMemoria:
    """O ``GuardaDosNomes`` sem disco: a faxina também cuida dos nomes, e esta
    régua não é sobre eles."""

    def ler(self) -> dict[str, str]:
        return {}

    def gravar(self, aparelho: str, nome: str | None) -> bool:
        return True


def test_o_fio_da_faxina_paga_a_meia_chave_devida_sozinho(
    diario: Path, fechar: list[Any],
) -> None:
    """No daemon ninguém chama a volta à mão: o fio da faxina tira a meia chave
    devida no passo dele, sem esperar a faxina inteira nem um movimento novo.

    MORDIDA: tire o ``tirar_as_meias_chaves`` do ``_faxinar_sempre`` — a chave
    fica no adaptador até alguém mover um controle.
    """
    mesa = Mesa(mundo_da_madrugada(), prazo_da_trava_s=0.2, nomes=NomesEmMemoria())
    fechar.append(mesa.fechar)
    feito = _o_verde_pareou_e_nao_conectou(mesa, VARANDA)
    mesa.relogio.agora = feito.comecou + cr.PRAZO_DO_PENDENTE_S
    _sem_a_trava(mesa.central.vigiar)
    assert mesa.mundo.objeto(VARANDA, VERDE) is not None

    mesa.central.comecar_a_faxina(intervalo_s=60.0)
    fim = time.monotonic() + 10.0
    while mesa.mundo.objeto(VARANDA, VERDE) is not None and time.monotonic() < fim:
        time.sleep(0.05)
    assert mesa.mundo.objeto(VARANDA, VERDE) is None, "o fio da faxina não pagou a dívida"
    assert mesa.mundo.lapides == [(VARANDA, VERDE)]


@pytest.mark.parametrize("destino", TRES)
def test_a_meia_chave_devida_sai_antes_do_conectar_seguinte_ali(
    diario: Path, fechar: list[Any], destino: str,
) -> None:
    """O defeito que a meia chave faz, visto por ela: o «Conectar» seguinte no
    mesmo adaptador. Com a chave devida, ele a tira ANTES de abrir a janela, e
    o verde — agora segurando PS + Create de novo — chega.

    MORDIDA: tire o pagamento do começo do movimento — o destino guarda a chave
    velha do verde, o «Parear» dela volta «já pareado», o ``Connect`` não dá, e
    ele não chega.
    """
    mesa = Mesa(mundo_da_madrugada(), prazo_da_trava_s=0.2)
    fechar.append(mesa.fechar)
    feito = _o_verde_pareou_e_nao_conectou(mesa, destino)
    mesa.relogio.agora = feito.comecou + cr.PRAZO_DO_PENDENTE_S
    _sem_a_trava(mesa.central.vigiar)
    assert mesa.de(VERDE).estado == cr.NAO_CHEGOU

    mesa.mundo.pair_mente = False
    rm.ela_pareia(mesa.relogio, mesa.mundo, mesa.central, VERDE)
    fim = mesa.central.conectar(destino)
    assert (fim.estado, fim.aparelho, fim.destino) == (cr.CHEGOU, VERDE, destino), fim
    assert mesa.mundo.lapides == [(destino, VERDE)]
    assert mesa.mundo.onde_esta(rm.uniq(VERDE)) == destino


@pytest.mark.parametrize("quem", ["conectar", "mover"])
@pytest.mark.parametrize("destino", (QUARTO, VARANDA))
def test_o_falhou_depois_do_pair_tira_a_meia_chave(
    diario: Path, fechar: list[Any], destino: str, quem: str,
) -> None:
    """Um erro no meio, DEPOIS de o ``Pair`` dar (aqui, ao dar o nome): o
    movimento acaba «não chegou» (``falhou``), e a chave que ele deixou no
    destino sai antes do veredito — no «Conectar» e no «Mover».

    MORDIDA: devolva o ``_falhou`` ao ``_acabou`` direto — a meia chave fica no
    destino até alguém pegar a trava.
    """
    mundo = mundo_da_madrugada()
    mundo.pair_mente = True
    mesa = Mesa(mundo)
    fechar.append(mesa.fechar)

    def quebrou(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("o BlueZ caiu no meio")

    mesa.central._dar_o_nome = quebrou  # type: ignore[method-assign]
    alvo = VERDE if quem == "conectar" else VERMELHO
    rm.ela_pareia(mesa.relogio, mundo, mesa.central, alvo)
    fim = (mesa.central.conectar(destino) if quem == "conectar"
           else mesa.central.mover(VERMELHO, destino))
    assert (fim.estado, fim.motivo, fim.aparelho) == (cr.NAO_CHEGOU, cr.MOTIVO_FALHOU, alvo)
    assert mundo.objeto(destino, alvo) is None, "a meia chave ficou no destino"
    assert (destino, alvo) in mundo.lapides
    assert mesa.central.tirar_as_meias_chaves() == ()


def test_a_vigia_que_levanta_no_prazo_deve_a_meia_chave(
    diario: Path, fechar: list[Any],
) -> None:
    """A vigia que levanta com o prazo vencido fecha «não chegou» sem conseguir
    perguntar nada ao rádio: a chave fica devida, e sai na volta seguinte."""
    mesa = Mesa(mundo_da_madrugada())
    fechar.append(mesa.fechar)
    feito = _o_verde_pareou_e_nao_conectou(mesa, QUARTO)
    mesa.relogio.agora = feito.comecou + cr.PRAZO_DO_PENDENTE_S

    def quebrou(*_a: Any, **_k: Any) -> bool:
        raise RuntimeError("o BlueZ caiu no meio")

    mesa.central._chegou = quebrou  # type: ignore[method-assign]
    mesa.central.vigiar()
    fim = mesa.de(VERDE)
    assert (fim.estado, fim.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_PRAZO)
    assert mesa.central.tirar_as_meias_chaves() == ((QUARTO, VERDE),)
    assert mesa.mundo.objeto(QUARTO, VERDE) is None


def test_a_chave_devida_de_quem_conectou_depois_nao_sai(
    diario: Path, fechar: list[Any],
) -> None:
    """A dívida pergunta ao rádio na hora de pagar: se o verde conectou naquele
    adaptador depois (ela apertou PS), a chave é a dele, e fica."""
    mesa = Mesa(mundo_da_madrugada(), prazo_da_trava_s=0.2)
    fechar.append(mesa.fechar)
    feito = _o_verde_pareou_e_nao_conectou(mesa, QUARTO)
    mesa.relogio.agora = feito.comecou + cr.PRAZO_DO_PENDENTE_S
    _sem_a_trava(mesa.central.vigiar)

    mesa.mundo.fisicos[VERDE].host = QUARTO
    mesa.mundo.apertar_ps(VERDE)
    assert mesa.mundo.onde_esta(rm.uniq(VERDE)) == QUARTO
    assert mesa.central.tirar_as_meias_chaves() == ()
    assert mesa.mundo.objeto(QUARTO, VERDE) is not None and mesa.mundo.lapides == []


# ---------------------------------------------------------------------------
# a conferência (28/09/2026): o que a cura dizia fazer e régua nenhuma segurava
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("quem", ["conectar", "mover"])
def test_a_janela_de_antes_fecha_no_pedido_sem_esperar_o_gesto(
    diario: Path, fechar: list[Any], quem: str,
) -> None:
    """O chip não espera a janela de antes acabar nem ela segurar PS + Create:
    a espera do gesto sai no pedido, a janela de antes fecha, e a do adaptador
    do chip já está aberta — no «Conectar» e no «Mover».

    MORDIDA: tire da espera do gesto (``_esperar_o_gesto`` ou
    ``_esperar_um_controle_novo``) a saída pelo pedido — a busca fica no
    adaptador de antes até a janela dele acabar.
    """
    mesa = Mesa(mundo_da_madrugada())
    fechar.append(mesa.fechar)
    busca = BuscaDePe(mesa.relogio)
    fechar.append(busca.soltar)
    if quem == "conectar":
        _o_conectar_no_gesto(mesa, busca, QUARTO)
    else:
        _o_mover_no_gesto(mesa, busca, QUARTO)

    assert mesa.chip(VARANDA)["status"] == "ok"
    de_pe = BuscaDePe(mesa.relogio)
    fechar.append(de_pe.soltar)
    busca.soltar()
    assert de_pe.dentro.wait(5.0), "a janela nova não abriu"
    assert onde_buscou(mesa.mundo) == [rm.HCIS[QUARTO], rm.HCIS[VARANDA]]
    assert mesa.mundo.propriedade_do_adaptador(QUARTO, "Discovering") is False
    assert mesa.mundo.propriedade_do_adaptador(VARANDA, "Discovering") is True
    assert mesa.no_gesto().destino == VARANDA


class PonteQueSegura:
    """O verbo ``esquecer`` da ponte que SEGURA o fio do movimento quando esquece
    em ``onde`` — o «Mover» parado no passo em que tira a chave dali."""

    def __init__(self, mundo: rm.RadioDeMentira, onde: str) -> None:
        self.mundo, self.onde = mundo, onde
        self.dentro, self.portao = threading.Event(), threading.Event()

    def __call__(self, adaptador: str, aparelho: str) -> tuple[bool, str]:
        if adaptador == self.onde and not self.portao.is_set():
            self.dentro.set()
            self.portao.wait(30.0)
        return self.mundo.esquecer_na_ponte(adaptador, aparelho)

    def soltar(self) -> None:
        self.portao.set()


@pytest.mark.parametrize(("passo", "segura_em"), [
    (cr.PASSO_PREPARANDO, QUARTO),  # a R6: o bond velho dele no destino sai
    (cr.PASSO_DESLIGANDO, SALA),  # a R1: a origem sai antes do gesto
])
def test_o_chip_antes_da_janela_leva_o_mover_sem_buscar_no_destino_de_antes(
    diario: Path, fechar: list[Any], passo: str, segura_em: str,
) -> None:
    """O «Mover» muda de destino também ANTES da janela — preparando (a R6
    tirando o bond velho dele do destino) e desligando (a R1 esquecendo a
    origem): nada foi pareado ainda. A busca abre só no adaptador do chip, e
    nunca no de antes.

    MORDIDA: tire o passo de ``PASSOS_EM_QUE_O_DESTINO_MUDA`` — o chip treme
    (``ocupado``) e a busca abre no destino de antes.
    """
    mundo = mundo_da_madrugada()
    mundo.pareado(QUARTO, VERMELHO, conectado=False, host=False)
    mesa = Mesa(mundo)
    fechar.append(mesa.fechar)
    ponte = PonteQueSegura(mundo, segura_em)
    fechar.append(ponte.soltar)
    mesa.central._esquecer_na_ponte = ponte
    assert mesa.central.comecar_a_mover(VERMELHO, QUARTO).estado == cr.ESPERANDO
    assert ponte.dentro.wait(5.0), "o «Mover» não chegou ao passo"
    assert mesa.de(VERMELHO).passo == passo

    resposta = mesa.chip(VARANDA)
    assert resposta["status"] == "ok", resposta
    mesa.relogio.agendar(2.0, lambda: mundo.segurar_ps_create(VERMELHO))
    ponte.soltar()
    (fim,) = mesa.esperar()
    assert (fim.estado, fim.aparelho, fim.destino) == (cr.CHEGOU, VERMELHO, VARANDA), fim
    assert onde_buscou(mundo) == [rm.HCIS[VARANDA]], "a busca abriu no destino de antes"
    assert onde_pareou(mundo) == [rm.HCIS[VARANDA]]
    assert mundo.objeto(QUARTO, VERMELHO) is None and mundo.objeto(SALA, VERMELHO) is None


def test_o_mover_que_muda_de_destino_tira_a_sobra_dele_no_destino_novo(
    diario: Path, fechar: list[Any],
) -> None:
    """A R6 vale no destino novo também: o objeto velho do vermelho na varanda
    (a sobra de uma busca antiga, sem chave) sai antes de a janela de lá abrir
    — senão a espera do gesto o leria como ela segurando PS + Create, e o
    ``Pair`` iria a um controle que não está pareando.

    MORDIDA: tire a R6 do ``_ir_para`` — o «Mover» acaba «não chegou»
    (``nao_pareou``) antes de ela apertar.
    """
    mundo = mundo_da_madrugada()
    # A física do rádio de mentira: a varanda achou o vermelho numa busca antiga.
    mundo._achar(VARANDA, mundo.fisicos[VERMELHO])
    mesa = Mesa(mundo)
    fechar.append(mesa.fechar)
    busca = BuscaDePe(mesa.relogio)
    fechar.append(busca.soltar)
    _o_mover_no_gesto(mesa, busca, QUARTO)

    assert mesa.chip(VARANDA)["status"] == "ok"
    mesa.relogio.agendar(2.0, lambda: mundo.segurar_ps_create(VERMELHO))
    busca.soltar()
    (fim,) = mesa.esperar()
    assert (fim.estado, fim.aparelho, fim.destino) == (cr.CHEGOU, VERMELHO, VARANDA), fim
    assert onde_pareou(mundo) == [rm.HCIS[VARANDA]]


def test_o_conectar_que_muda_de_destino_ignora_o_que_o_destino_novo_ja_conhecia(
    diario: Path, fechar: list[Any],
) -> None:
    """O roxo que a varanda já tinha visto numa busca antiga (sem chave) está
    na lista de lá, e não é quem ela está segurando: ela clica no verde, e só
    ele pareia (O-PAREAR-ESPERA-O-CLIQUE-01).

    MORDIDA: devolva à janela o primeiro controle que ela achar, sem a escolha
    dela — a janela da varanda pega o roxo, e o ``Pair`` vai a um controle que
    não está pareando.
    """
    mundo = mundo_da_madrugada()
    mundo.fisicos[ROXO] = rm.Fisico(ROXO, rm.CLASSE_DE_CONTROLE)
    # A física do rádio de mentira: a varanda achou o roxo numa busca antiga.
    mundo._achar(VARANDA, mundo.fisicos[ROXO])
    mesa = Mesa(mundo)
    fechar.append(mesa.fechar)
    busca = BuscaDePe(mesa.relogio)
    fechar.append(busca.soltar)
    _o_conectar_no_gesto(mesa, busca, QUARTO)

    assert mesa.chip(VARANDA)["status"] == "ok"
    rm.ela_pareia(mesa.relogio, mundo, mesa.central, VERDE)
    busca.soltar()
    (fim,) = mesa.esperar()
    assert (fim.estado, fim.aparelho, fim.destino) == (cr.CHEGOU, VERDE, VARANDA), fim
    assert [bd.endereco_do_aparelho(c) for c, _a in mundo.metodos("Pair")] == [VERDE]


@pytest.mark.parametrize(("onde_busca", "chip"), PARES)
def test_o_clique_de_volta_pela_tela_desfaz_o_pedido_que_a_busca_ainda_nao_levou(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, onde_busca: str, chip: str,
) -> None:
    """O último clique dela vence também pela TELA. Entre o chip aceito e o fio
    da busca levar o pedido (meio segundo no gesto; segundos no «Mover» que
    ainda desliga), o tique da tela lê onde a busca está. Se o publicado
    dissesse o destino de antes, o chip de volta seria só «abrir a caixa» (a
    tela não pede ao rádio o adaptador em que a busca já está), e a busca iria
    para o chip que ela desfez.

    MORDIDA: publique o movimento sem o destino pedido (o ``publicar`` com o
    ``movimentos()`` cru) — o clique de volta não chega ao rádio, e o verde
    pareia no chip que ela deixou.
    """
    mundo = mundo_da_madrugada()
    relogio = rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    busca = BuscaDePe(relogio)
    try:
        bancada.cena()
        bancada.gesto("escolher-adaptador", alvo=id_da_tela(onde_busca))
        bancada.cena()
        assert bancada.gesto("conectar-aparelho") == {"armou": True}
        assert busca.dentro.wait(5.0), "a central não abriu a janela"
        bancada.cena()
        assert bancada.gesto("escolher-adaptador", alvo=id_da_tela(chip)) == {"armou": True}

        # O fio ainda não levou o pedido (a espera está presa): o tique da tela
        # já diz a busca indo para o chip, e só nele.
        campos = bancada.tique()
        _a_busca_acende_so_no(campos, a08, chip)

        assert bancada.gesto("escolher-adaptador", alvo=id_da_tela(onde_busca)) == {
            "armou": True}
        assert bancada.ponte.chamadas[-1] == (
            "radio.mover", {"destino": id_da_tela(onde_busca)}), "o clique de volta não chegou"
        rm.ela_pareia(relogio, mundo, bancada.central, VERDE)
        busca.soltar()
        bancada.esperar_a_central()
        assert onde_buscou(mundo) == [rm.HCIS[onde_busca]], "a busca foi para o chip desfeito"
        assert onde_pareou(mundo) == [rm.HCIS[onde_busca]]
        assert bancada.cena()["aberto"] == id_da_tela(onde_busca)
    finally:
        busca.soltar()
        bancada.fechar()


def _a_busca_acende_so_no(campos: dict[str, Any], a08: Any, adaptador: str) -> None:
    """A pílula «Segure PS + Create» mora em toda caixa, escondida, e acende só
    na que busca: pela lista `radio-conectando` e pela classe `buscando` com que
    a caixa nasce (O-CONECTAR-ABRE-INTEIRO-TODA-VEZ-01, cura 2)."""
    ids = [lug["id"] for lug in a08._CENA_NA_TELA["lugares"]]
    assert campos["radio-conectando"] == [
        "sim" if lid == id_da_tela(adaptador) else "" for lid in ids]
    for outro in TRES:
        cartao = _cartao(campos["radio-sala"], id_da_tela(outro))
        assert ("buscando" in cartao.split('"', 2)[1].split()) == (outro == adaptador), outro


def _o_bluetoothd_sai(mundo: rm.RadioDeMentira) -> None:
    """O ``bluetoothd`` sai do barramento (um restart, a queda do rádio)."""
    mundo.bluez_de_pe = False
    mundo._emitir(bd.Sinal("dono", dono_novo=""))


def _o_bluetoothd_volta(mesa: Mesa) -> None:
    mesa.mundo.bluez_de_pe = True
    mesa.mundo._emitir(bd.Sinal("dono", dono_novo=rm.RadioDeMentira.DONO_DO_BLUEZ))
    fim = time.monotonic() + 5.0
    while mesa.dono.caminhos() is None and time.monotonic() < fim:
        time.sleep(0.01)
    assert mesa.dono.caminhos() is not None, "o dono não refotografou"


@pytest.mark.parametrize("quando_cala", ["no_veredito", "no_pagamento"])
def test_nao_sei_do_radio_nao_paga_a_meia_chave(
    diario: Path, fechar: list[Any], quando_cala: str,
) -> None:
    """«Não sei» não é «não é mais meia chave». Com o ``bluetoothd`` fora do
    barramento, a pergunta «ainda é meia chave?» não tem resposta: no veredito
    do «não chegou» (com a trava na mão) a chave fica DEVIDA, e no pagamento a
    dívida fica na fila. Quando o rádio volta, ela sai.

    MORDIDA: responda «não sei» como «não é» no ``_esquecer_se_meia_chave`` — a
    dívida some com o rádio mudo, e a meia chave fica no adaptador para sempre
    (o «Conectar» seguinte ali não vê o controle).
    """
    mesa = Mesa(mundo_da_madrugada(), prazo_da_trava_s=0.2)
    fechar.append(mesa.fechar)
    feito = _o_verde_pareou_e_nao_conectou(mesa, QUARTO)
    mesa.relogio.agora = feito.comecou + cr.PRAZO_DO_PENDENTE_S
    if quando_cala == "no_veredito":
        _o_bluetoothd_sai(mesa.mundo)
        mesa.central.vigiar()
    else:
        _sem_a_trava(mesa.central.vigiar)
        _o_bluetoothd_sai(mesa.mundo)
        assert mesa.central.tirar_as_meias_chaves() == ()
    fim = mesa.de(VERDE)
    assert (fim.estado, fim.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_PRAZO)
    assert mesa.mundo.lapides == []

    _o_bluetoothd_volta(mesa)
    assert mesa.central.tirar_as_meias_chaves() == ((QUARTO, VERDE),)
    assert mesa.mundo.objeto(QUARTO, VERDE) is None, "a meia chave ficou no adaptador"
    assert mesa.mundo.lapides == [(QUARTO, VERDE)]


def test_a_chave_que_nao_sumiu_nao_conta_como_paga(
    diario: Path, fechar: list[Any],
) -> None:
    """A dívida só sai quando a chave sumiu do rádio. Um esquecer que não
    tirou nada (o ``RemoveDevice`` e a ponte recusados) deixa a dívida para a
    volta seguinte — e o diário não diz «esqueceu».

    MORDIDA: dê a dívida por paga sem conferir que a chave sumiu — a primeira
    volta a devolve como paga, e a chave fica.
    """
    mesa = Mesa(mundo_da_madrugada(), prazo_da_trava_s=0.2)
    fechar.append(mesa.fechar)
    feito = _o_verde_pareou_e_nao_conectou(mesa, QUARTO)
    mesa.relogio.agora = feito.comecou + cr.PRAZO_DO_PENDENTE_S
    _sem_a_trava(mesa.central.vigiar)

    mesa.central._esquecer = lambda _dono, _adaptador, _aparelho: False  # type: ignore[method-assign,assignment]
    assert mesa.central.tirar_as_meias_chaves() == ()
    assert mesa.mundo.objeto(QUARTO, VERDE) is not None
    del mesa.central._esquecer
    assert mesa.central.tirar_as_meias_chaves() == ((QUARTO, VERDE),)
    assert mesa.mundo.objeto(QUARTO, VERDE) is None
    pagas = [e for e in diario_do_radio.ler(caminhos=[diario])
             if e["o_que"] == cr.ESQUECEU_A_MEIA_CHAVE]
    assert len(pagas) == 1, pagas
