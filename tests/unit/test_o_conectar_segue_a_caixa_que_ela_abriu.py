"""O «Conectar» segue a caixa que ela abriu — O-CONECTAR-SEGUE-A-CAIXA-QUE-ELA-ABRIU-01."""

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
from tests.unit.test_o_conectar_pareia_no_adaptador_escolhido import (
    BuscaDePe,
    PonteQueVaiAoDaemon,
    mundo_da_madrugada,
    onde_buscou,
    onde_pareou,
    preparar_a_tela,
    preparar_o_diario,
)

TRES = (SALA, QUARTO, VARANDA)
PARES = [(busca, chip) for busca in TRES for chip in TRES if busca != chip]
MOVERES = [(destino, chip) for destino in (QUARTO, VARANDA) for chip in TRES if chip != destino]
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


@pytest.mark.parametrize(("onde_busca", "chip"), PARES)
def test_o_chip_leva_a_busca_do_conectar_para_o_adaptador_dele(
    diario: Path, fechar: list[Any], onde_busca: str, chip: str,
) -> None:
    """A régua (1) da sprint: com a central no gesto num adaptador, o chip de"""
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
    """Ela clica o chip aos 50 s de uma janela de 30 e de um prazo de 60. No"""
    mesa = Mesa(mundo_da_madrugada())
    fechar.append(mesa.fechar)
    busca = BuscaDePe(mesa.relogio)
    fechar.append(busca.soltar)
    fins: list[cr.Movimento] = []
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
    """Dois chips antes de a busca andar: vale o último. Voltar ao adaptador da"""
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
    """Ela clica o chip quando a janela do «Conectar» acaba: o pedido chegou"""
    mesa = Mesa(mundo_da_madrugada())
    fechar.append(mesa.fechar)
    busca = BuscaDePe(mesa.relogio)
    fechar.append(busca.soltar)
    antes = _o_conectar_no_gesto(mesa, busca, SALA)
    mesa.relogio.agora = antes.comecou + gp.SEGUNDOS_MAX

    assert mesa.chip(QUARTO)["status"] == "ok"
    rm.ela_pareia(mesa.relogio, mesa.mundo, mesa.central, VERDE)
    busca.soltar()
    (fim,) = mesa.esperar()
    assert (fim.estado, fim.aparelho, fim.destino) == (cr.CHEGOU, VERDE, QUARTO), fim
    assert onde_buscou(mesa.mundo) == [rm.HCIS[SALA], rm.HCIS[QUARTO]]


def test_o_controle_que_aparece_junto_com_o_chip_pareia_no_adaptador_do_chip(
    diario: Path, fechar: list[Any],
) -> None:
    """O verde aparece na janela da sala no mesmo instante em que ela clica o"""
    mesa = Mesa(mundo_da_madrugada())
    fechar.append(mesa.fechar)
    busca = BuscaDePe(mesa.relogio)
    fechar.append(busca.soltar)
    _o_conectar_no_gesto(mesa, busca, SALA)

    assert mesa.chip(QUARTO)["status"] == "ok"
    mesa.mundo.segurar_ps_create(VERDE)
    assert mesa.mundo.objeto(SALA, VERDE) is not None, "a janela da sala não o achou"
    mesa.relogio.agendar(1.0, rm.o_clique_no_parear(mesa.central, VERDE))
    busca.soltar()
    (fim,) = mesa.esperar()
    assert (fim.estado, fim.aparelho, fim.destino) == (cr.CHEGOU, VERDE, QUARTO), fim
    assert onde_pareou(mesa.mundo) == [rm.HCIS[QUARTO]]


class JanelaDePe:
    """Uma janela que ainda está aberta — o que a espera do gesto deixa para trás"""

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
    """A espera do gesto sai porque ela pediu outro destino, e ela o desfaz no"""
    mesa = Mesa(mundo_da_madrugada())
    fechar.append(mesa.fechar)
    no_gesto = mesa.central._guardar(cr.Movimento(
        cr.CONECTANDO, SALA, cr.ESPERANDO, cr.PASSO_GESTO, comecou=mesa.relogio()))
    comeco = mesa.relogio()
    assert mesa.central._sem_gesto(no_gesto, JanelaDePe(), comeco, gp.SEGUNDOS_MAX) is None
    assert mesa.central.movimentos() == (no_gesto,)

    mesa.relogio.agora = comeco + gp.SEGUNDOS_MAX
    fim = mesa.central._sem_gesto(no_gesto, JanelaDePe(), comeco, gp.SEGUNDOS_MAX)
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
    """Ela clica o chip do quarto, e no mesmo instante o roxo volta sozinho pelo"""
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


@pytest.mark.parametrize(("destino", "chip"), MOVERES)
def test_o_chip_leva_o_mover_do_mesmo_controle(
    diario: Path, fechar: list[Any], destino: str, chip: str,
) -> None:
    """A régua (3) da sprint: um «Mover» de ``aa:bb:cc:00:00:01`` espera no"""
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
    """Todo chamador que pede o MESMO movimento para outro lugar: o ``radio.mover``"""
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
    """O chip leva o «Mover» de volta à sala, a casa de antes. A sala deixa de"""
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


def test_outro_aparelho_e_adaptador_fora_da_maquina_seguem_recusados(
    diario: Path, fechar: list[Any],
) -> None:
    """O chip só leva o movimento que espera. Outro controle, um aparelho"""
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
    """Achado o controle, o ``Pair`` e a conferência são do adaptador em que ele"""
    mesa = Mesa(mundo_da_madrugada())
    fechar.append(mesa.fechar)
    em_voo = mesa.central._guardar(cr.Movimento(
        VERDE, QUARTO, cr.ESPERANDO, passo, pareou_no_destino=passo == cr.PASSO_CONFERINDO,
        comecou=mesa.relogio()))
    assert mesa.chip(VARANDA)["status"] == "ocupado"
    assert mesa.central.movimento_de(VERDE) == em_voo


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
    """O prazo vence com outro motor segurando a trava: o «não chegou» sai (a"""
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
    """O ``GuardaDosNomes`` sem disco: a faxina também cuida dos nomes, e esta"""

    def ler(self) -> dict[str, str]:
        return {}

    def gravar(self, aparelho: str, nome: str | None) -> bool:
        return True


def test_o_fio_da_faxina_paga_a_meia_chave_devida_sozinho(
    diario: Path, fechar: list[Any],
) -> None:
    """No daemon ninguém chama a volta à mão: o fio da faxina tira a meia chave"""
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
    """O defeito que a meia chave faz, visto por ela: o «Conectar» seguinte no"""
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
    """Um erro no meio, DEPOIS de o ``Pair`` dar (aqui, ao dar o nome): o"""
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
    """A vigia que levanta com o prazo vencido fecha «não chegou» sem conseguir"""
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
    """A dívida pergunta ao rádio na hora de pagar: se o verde conectou naquele"""
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


@pytest.mark.parametrize("quem", ["conectar", "mover"])
def test_a_janela_de_antes_fecha_no_pedido_sem_esperar_o_gesto(
    diario: Path, fechar: list[Any], quem: str,
) -> None:
    """O chip não espera a janela de antes acabar nem ela segurar PS + Create:"""
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
    """O verbo ``esquecer`` da ponte que SEGURA o fio do movimento quando esquece"""

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
    (cr.PASSO_PREPARANDO, QUARTO),
    (cr.PASSO_DESLIGANDO, SALA),
])
def test_o_chip_antes_da_janela_leva_o_mover_sem_buscar_no_destino_de_antes(
    diario: Path, fechar: list[Any], passo: str, segura_em: str,
) -> None:
    """O «Mover» muda de destino também ANTES da janela — preparando (a R6"""
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
    """A R6 vale no destino novo também: o objeto velho do vermelho na varanda"""
    mundo = mundo_da_madrugada()
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
    """O roxo que a varanda já tinha visto numa busca antiga (sem chave) está"""
    mundo = mundo_da_madrugada()
    mundo.fisicos[ROXO] = rm.Fisico(ROXO, rm.CLASSE_DE_CONTROLE)
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
    """«Não sei» não é «não é mais meia chave». Com o ``bluetoothd`` fora do"""
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
    """A dívida só sai quando a chave sumiu do rádio. Um esquecer que não"""
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
