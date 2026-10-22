"""O rumble do jogo chega ao dedo no gatilho (O-RUMBLE-DO-JOGO-CHEGA-AO-DEDO-NO-GATILHO-01).

O lado com o dedo além do disparo vibra no modo ``0x26`` com o degrau (1 a 8) do par cru do jogo;
a soltura, ou 150 ms sem rumble, devolve o efeito do estilo. Escreve só quando o degrau muda além
da histerese, no máximo uma vez por ciclo do gatilho, e cede a quem já é dono do lado. Nada toca
o aparelho: o controle e o alto-falante são de mentira, o motor é o de produção.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.trigger_effects import TriggerMode, vibration
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.profiles.estilos_de_jogo import ESTILOS, POR_CHAVE

P1 = "aa:bb:cc:00:00:01"
QUATRO = (P1, "aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03", "aa:bb:cc:00:00:04")
_ACAO = "acao"  # (noqa-acento): chave do estilo
_GOLPE = {_ACAO, "luta", "souls", "terror", "aventura", "esportes"}
DIREITO, ESQUERDO = tv.LADO_DIREITO, tv.LADO_ESQUERDO
TIQUE_S = 1.0 / 60.0


class _Mesa:
    """O motor de produção com o atuador do dedo e as pontas de mentira."""

    def __init__(
        self,
        uniqs: tuple[str, ...] = (P1,),
        *,
        estilo: str = _ACAO,
        cede: Callable[[str, str], bool] | None = None,
        radio_cede: Callable[[str], bool] | None = None,
    ) -> None:
        self.uniqs = uniqs
        self.escritas: list[tuple[str, str, bytes]] = []
        self.devolvidos: list[str] = []
        self.soltos_por_lado: list[tuple[str, str, bytes]] = []
        self.largados: list[str] = []
        self.dedo: dict[tuple[str, str], bool] = {}
        self.atuador = tv.AtuadorDoDedo(
            lambda u, disco, bloco: self.escritas.append((u, disco, bloco)),
            self._devolver,
            lambda u, lado: self.dedo.get((u, lado), False),
            self.largados.append,
            cede,
            lambda u, disco, bloco: self.soltos_por_lado.append((u, disco, bloco)),
            radio_cede,
        )
        self.motor = tv.TatoVivo([self.atuador])
        self.motor.ligado = True
        self.daemon = SimpleNamespace(_tato_vivo=self.motor)
        self.estado = {u: tv.EstadoDoCanal(tv.MODO_XBOX, ha_jogo=True) for u in uniqs}
        self.receita = tv.receita_do_estilo(POR_CHAVE[estilo])
        self.t = 100.0

    def _devolver(self, uniq: str) -> bool:
        self.devolvidos.append(uniq)
        return True

    def rumble(self, fraco: int, forte: int, uniq: str = P1, em: float | None = None) -> None:
        tv.anotar_o_rumble(self.daemon, uniq, fraco, forte, self.t if em is None else em)

    def tique(self, passo: float = TIQUE_S) -> int:
        self.t += passo
        return int(self.motor.tique(self.t, self.estado.get, self.receita, self.uniqs))


def test_o_degrau_e_o_par_cru_em_oito_degraus() -> None:
    assert tv.degrau_do_rumble(0, 0) == 0
    assert tv.degrau_do_rumble(7, 7) == 0  # abaixo do mínimo: o jogo calado
    assert tv.degrau_do_rumble(0, 200) == 7
    assert tv.degrau_do_rumble(200, 0) == 7  # o maior dos dois motores
    assert tv.degrau_do_rumble(8, 0) == 1
    assert tv.degrau_do_rumble(255, 255) == 8


def test_rumble_200_com_o_r2_em_220_da_o_bloco_0x26_no_r2_com_o_degrau_certo() -> None:
    mesa = _Mesa()
    mesa.motor.borda_do_dedo.ver(P1, 0, 220, mesa.t)
    mesa.dedo[(P1, DIREITO)] = mesa.motor.borda_do_dedo.apertado(P1, DIREITO)
    mesa.rumble(0, 200)
    assert mesa.tique() == 1
    assert mesa.escritas == [(P1, "right", tv.bloco_do_dedo(7))]
    bloco = mesa.escritas[0][2]
    assert bloco[0] == TriggerMode.VIBRATION == 0x26
    esperado = vibration(0, 7, tv.FREQUENCIA_DO_DEDO_HZ)
    assert bloco == bytes([esperado.mode, *esperado.forces[:6], 0, 0, esperado.forces[6], 0])


def test_o_mesmo_rumble_com_o_r2_solto_nao_escreve_nada() -> None:
    mesa = _Mesa()
    mesa.motor.borda_do_dedo.ver(P1, 0, 150, mesa.t)  # abaixo do disparo (160)
    mesa.dedo[(P1, DIREITO)] = mesa.motor.borda_do_dedo.apertado(P1, DIREITO)
    mesa.rumble(0, 200)
    for _ in range(30):
        mesa.tique()
    assert mesa.escritas == []
    assert mesa.devolvidos == [] and mesa.soltos_por_lado == []


def test_a_rajada_de_vinte_pulsos_com_o_nivel_num_degrau_da_uma_escrita_so() -> None:
    mesa = _Mesa()
    mesa.dedo[(P1, DIREITO)] = True
    # Um segundo de rajada: um pulso a cada 50 ms, 10 ms de força entre 150 e 170 (os
    # degraus 5 e 6 se encostam), e o zero no meio; o tique é o do laço, 60 por segundo.
    inicio = mesa.t
    pulsos = [inicio + 0.05 * i for i in range(20)]
    acontecimentos = sorted(
        [(p, 150 if i % 2 else 170) for i, p in enumerate(pulsos)]
        + [(p + 0.010, 0) for p in pulsos])
    for _ in range(60):
        proximo = mesa.t + TIQUE_S
        while acontecimentos and acontecimentos[0][0] <= proximo:
            instante, nivel = acontecimentos.pop(0)
            mesa.rumble(0, nivel, em=instante)
        mesa.tique()
    assert not acontecimentos
    assert len(mesa.escritas) == 1
    assert mesa.escritas[0][2] in (tv.bloco_do_dedo(5), tv.bloco_do_dedo(6))
    assert mesa.devolvidos == []  # o zero entre dois pulsos não devolve o lado


def test_o_degrau_que_sobe_espera_o_ciclo_do_gatilho() -> None:
    mesa = _Mesa()
    mesa.dedo[(P1, DIREITO)] = True
    mesa.rumble(0, 40)
    mesa.tique()
    mesa.rumble(0, 255)
    mesa.tique(0.010)  # 10 ms depois da escrita: o ciclo do gatilho (32 ms) ainda não passou
    assert len(mesa.escritas) == 1
    mesa.tique(tv.CICLO_DO_GATILHO_S)
    assert [b for _u, _d, b in mesa.escritas] == [tv.bloco_do_dedo(2), tv.bloco_do_dedo(8)]


def test_soltar_o_gatilho_devolve_o_efeito_do_estilo_no_tique_seguinte() -> None:
    mesa = _Mesa()
    mesa.dedo[(P1, DIREITO)] = True
    mesa.rumble(0, 200)
    mesa.tique()
    mesa.dedo[(P1, DIREITO)] = False
    mesa.tique()
    assert mesa.devolvidos == [P1]
    assert mesa.atuador.segura(P1) == []


def test_150_ms_sem_rumble_devolvem_o_lado_mesmo_com_o_dedo_no_fundo() -> None:
    mesa = _Mesa()
    mesa.dedo[(P1, DIREITO)] = True
    mesa.rumble(0, 200)
    mesa.tique()
    mesa.rumble(0, 0)
    mesa.tique(0.100)
    assert mesa.devolvidos == []
    mesa.tique(0.060)
    assert mesa.devolvidos == [P1]


def test_um_lado_volta_sozinho_enquanto_o_outro_segue_no_dedo() -> None:
    mesa = _Mesa()
    mesa.dedo[(P1, DIREITO)] = mesa.dedo[(P1, ESQUERDO)] = True
    mesa.rumble(200, 200)
    mesa.tique()
    assert sorted(d for _u, d, _b in mesa.escritas) == ["left", "right"]
    mesa.dedo[(P1, ESQUERDO)] = False
    mesa.tique()
    assert mesa.devolvidos == []
    assert mesa.soltos_por_lado == [(P1, "left", tv.bloco_do_dedo(7))]
    assert mesa.atuador.segura(P1) == [DIREITO]


def test_o_lado_com_momento_da_imersao_nao_recebe_nada() -> None:
    mesa = _Mesa(cede=lambda u, lado: lado == DIREITO)
    mesa.dedo[(P1, DIREITO)] = mesa.dedo[(P1, ESQUERDO)] = True
    mesa.rumble(0, 200)
    mesa.tique()
    assert [d for _u, d, _b in mesa.escritas] == ["left"]


def test_o_fps_nao_recebe_nada_o_ritmo_do_tiro_e_o_dono() -> None:
    mesa = _Mesa(estilo="fps")
    assert mesa.receita.gatilho_no_ritmo
    mesa.receita = replace(mesa.receita, rumble_no_dedo=True)  # nem com o campo ligado
    mesa.dedo[(P1, DIREITO)] = True
    mesa.rumble(0, 200)
    for _ in range(10):
        mesa.tique()
    assert mesa.escritas == []


def test_o_jogo_que_escreveu_o_gatilho_ha_menos_de_3_s_nao_recebe_nada() -> None:
    mesa = _Mesa()
    mesa.estado[P1] = tv.EstadoDoCanal(tv.MODO_DUALSENSE, {"trigger": 1.0}, ha_jogo=True)
    mesa.dedo[(P1, DIREITO)] = True
    mesa.rumble(0, 200)
    mesa.tique()
    assert mesa.escritas == []


def test_o_jogo_que_toma_o_gatilho_no_meio_fica_com_ele() -> None:
    mesa = _Mesa()
    mesa.dedo[(P1, DIREITO)] = True
    mesa.rumble(0, 200)
    mesa.tique()
    mesa.estado[P1] = tv.EstadoDoCanal(tv.MODO_DUALSENSE, {"trigger": 0.2}, ha_jogo=True)
    mesa.tique()
    assert mesa.largados == [P1]
    assert mesa.devolvidos == []  # o valor agora é do jogo: devolver apagaria o dele
    assert mesa.motor.contadores["soltos_ao_jogo"] == 1


def test_sem_jogo_na_frente_o_lado_volta_ao_estilo() -> None:
    mesa = _Mesa()
    mesa.dedo[(P1, DIREITO)] = True
    mesa.rumble(0, 200)
    mesa.tique()
    mesa.estado[P1] = tv.EstadoDoCanal(tv.MODO_XBOX, ha_jogo=False)
    mesa.tique()
    assert mesa.devolvidos == [P1]


def test_nos_quatro_controles_cada_um_tem_o_dedo_e_o_rumble_dele() -> None:
    mesa = _Mesa(QUATRO)
    for uniq in QUATRO:
        mesa.dedo[(uniq, DIREITO)] = True
    mesa.rumble(0, 255, QUATRO[1])
    mesa.rumble(0, 40, QUATRO[3])
    mesa.tique()
    assert sorted((u, b) for u, _d, b in mesa.escritas) == sorted([
        (QUATRO[1], tv.bloco_do_dedo(8)), (QUATRO[3], tv.bloco_do_dedo(2))])


def test_no_radio_sem_fatia_livre_o_degrau_espera() -> None:
    cheio = {"agora": True}
    mesa = _Mesa(radio_cede=lambda _u: cheio["agora"])
    mesa.dedo[(P1, DIREITO)] = True
    mesa.rumble(0, 200)
    mesa.tique()
    assert mesa.escritas == []
    assert mesa.motor.contadores["recusas_do_radio"] == 1
    cheio["agora"] = False
    mesa.tique()
    assert len(mesa.escritas) == 1


def test_a_rajada_longa_fica_no_teto_do_tato() -> None:
    mesa = _Mesa()
    mesa.dedo[(P1, DIREITO)] = True
    for i in range(120):  # dois segundos com o degrau saltando de 1 a 8 a cada tique
        mesa.rumble(0, 255 if i % 2 else 8)
        mesa.tique()
    por_segundo = len(mesa.escritas) / 2.0
    assert por_segundo <= tv.TETO_POR_CONTROLE


def test_os_estilos_de_golpe_nascem_com_o_rumble_no_dedo() -> None:
    ligados = {e.chave for e in ESTILOS
               if e.receita_invisivel is not None and e.receita_invisivel.rumble_no_dedo}
    assert ligados == _GOLPE
    for estilo in ESTILOS:
        receita = tv.receita_do_estilo(estilo)
        assert receita.rumble_no_dedo == (estilo.chave in _GOLPE)
    assert tv.Receita.de({"rumble_no_dedo": True}).rumble_no_dedo
    assert tv.Receita(rumble_no_dedo=True).ligada
    assert not tv.Receita.de({}).rumble_no_dedo


class _Controle:
    def __init__(self) -> None:
        self.gatilhos: list[tuple[str, str, bytes]] = []
        self.encerrados: list[str] = []
        self.soltos: list[tuple[str, str, bytes]] = []

    def set_game_trigger_for(self, uniq: str, lado: str, bloco: bytes) -> bool:
        self.gatilhos.append((uniq, lado, bloco))
        return True

    def end_game_session_for(self, uniq: str) -> bool:
        self.encerrados.append(uniq)
        return True

    def soltar_o_gatilho_do_jogo_for(self, uniq: str, lado: str, bloco: bytes) -> bool:
        self.soltos.append((uniq, lado, bloco))
        return True


def _producao(
    monkeypatch: pytest.MonkeyPatch, falante: Any = None
) -> tuple[Any, tv.TatoVivo]:
    monkeypatch.setattr(tv, "_controle_na_economia", lambda _u: False)
    alvo = SimpleNamespace(controller=_Controle(), _alto_falante_subsystem=falante)
    motor = tv.TatoVivo(tv.atuadores_de_producao(alvo))
    motor.ligado = True
    alvo._tato_vivo = motor
    return alvo, motor


def test_a_producao_leva_o_dedo_ao_controle_e_a_soltura_encerra_a_sessao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alvo, motor = _producao(monkeypatch)
    assert any(isinstance(a, tv.AtuadorDoDedo) for a in motor.atuadores)
    receita = tv.receita_do_estilo(POR_CHAVE["souls"])
    estado = {P1: tv.EstadoDoCanal(tv.MODO_XBOX, ha_jogo=True)}
    t = 50.0
    motor.borda_do_dedo.ver(P1, 0, 230, t)
    tv.anotar_o_rumble(alvo, P1, 90, 30, t)
    motor.tique(t + TIQUE_S, estado.get, receita, (P1,))
    assert alvo.controller.gatilhos == [(P1, "right", tv.bloco_do_dedo(3))]
    motor.borda_do_dedo.ver(P1, 0, 40, t + 0.1)
    motor.tique(t + 0.1, estado.get, receita, (P1,))
    assert alvo.controller.encerrados == [P1]


def test_a_producao_cede_ao_gatilho_do_perfil_que_ja_vibra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alvo, motor = _producao(monkeypatch)
    motor.vibra_o_gatilho = tv.VibracaoDoGatilho(geral=True)
    receita = tv.receita_do_estilo(POR_CHAVE["luta"])
    estado = {P1: tv.EstadoDoCanal(tv.MODO_XBOX, ha_jogo=True)}
    motor.borda_do_dedo.ver(P1, 0, 230, 50.0)
    tv.anotar_o_rumble(alvo, P1, 0, 200, 50.0)
    motor.tique(50.0 + TIQUE_S, estado.get, receita, (P1,))
    assert alvo.controller.gatilhos == []


def test_a_producao_no_radio_sem_fatia_espera(monkeypatch: pytest.MonkeyPatch) -> None:
    falante = SimpleNamespace(_chave_do_rumble=lambda u: u, _o_radio_cede=lambda _u: True)
    alvo, motor = _producao(monkeypatch, falante)
    estado = {P1: tv.EstadoDoCanal(tv.MODO_XBOX, ha_jogo=True)}
    motor.borda_do_dedo.ver(P1, 0, 230, 50.0)
    tv.anotar_o_rumble(alvo, P1, 0, 200, 50.0)
    motor.tique(50.0 + TIQUE_S, estado.get, tv.receita_do_estilo(POR_CHAVE["terror"]), (P1,))
    assert alvo.controller.gatilhos == []
