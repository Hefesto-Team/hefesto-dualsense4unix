"""A mira virtual segue o movimento como o PRAGMATA (A-MIRA-VIRTUAL-SEGUE-O-MOVIMENTO-...-01).

O gesto real, em qualquer altura da mão, sai pela mesma resposta nos dois eixos: a velocidade da
mão pede a velocidade da câmera, a partir do ponto em que o jogo começa a ler o analógico.

θ é o nariz levantado, a pose de quem segura o controle na mão: o acelerômetro em repouso aponta
para cima do mundo, e o `z` do controle, para quem segura, desce.

MORDIDAS: `_no_espaco_do_jogador` de volta ao `gy` reprova os gestos em θ; sem o `como_volante`
a régua do volante reprova; sem o `piso` em `_saida_do_eixo` a régua da mão lenta reprova; sem o
`_com_o_resto` a soma do tique reprova; sem trocar o sinal em `_componentes` a régua do sentido
reprova.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from hefesto_dualsense4unix.core import roteador_de_movimento as rot
from hefesto_dualsense4unix.core.evdev_reader import MotionSensorReader

MIRA = rot.ArranjoDeMovimento(destino=rot.DESTINO_ANALOGICO_DIREITO)
ALTURAS = (0.0, 15.0, 30.0, 45.0, 60.0, 75.0, 90.0)
FRACAO_A_60_GRAUS_S = 0.6168


def _um_tique(
    giro: tuple[float, float, float],
    arranjo: rot.ArranjoDeMovimento,
    ganho: float = 1.0,
    gravidade: tuple[float, float, float] | None = None,
) -> tuple[int, int]:
    return rot.deflexao_do_tique(
        SimpleNamespace(), "aa:bb:cc:00:00:01", giro, arranjo, ganho, gravidade
    )


def _gravidade(theta: float) -> tuple[float, float, float]:
    return 0.0, math.cos(math.radians(theta)), -math.sin(math.radians(theta))


def _virar(theta: float, esquerda: float) -> tuple[float, float, float]:
    """Girar em torno da vertical do mundo, com o controle levantado θ graus na mão."""
    _x, y, z = _gravidade(theta)
    return 0.0, esquerda * y, esquerda * z


def _volante(theta: float, esquerda: float) -> tuple[float, float, float]:
    """Um punho desce e o outro sobe: girar em torno do eixo que aponta para quem segura."""
    return (
        0.0,
        esquerda * math.sin(math.radians(theta)),
        esquerda * math.cos(math.radians(theta)),
    )


@pytest.mark.parametrize("theta", ALTURAS)
def test_virar_da_a_mesma_saida_em_qualquer_altura_da_mao(theta: float) -> None:
    dh, dv = _um_tique(_virar(theta, 60.0), MIRA, gravidade=_gravidade(theta))
    assert dv == 0
    assert dh == pytest.approx(-FRACAO_A_60_GRAUS_S * rot.DEFLEXAO_MAXIMA, abs=1)


@pytest.mark.parametrize("theta", ALTURAS)
def test_levantar_o_nariz_da_a_mesma_saida_em_qualquer_altura_da_mao(theta: float) -> None:
    dh, dv = _um_tique((60.0, 0.0, 0.0), MIRA, gravidade=_gravidade(theta))
    assert dh == 0
    assert dv == pytest.approx(-FRACAO_A_60_GRAUS_S * rot.DEFLEXAO_MAXIMA, abs=1)


@pytest.mark.parametrize("theta", ALTURAS)
@pytest.mark.parametrize(("esquerda", "sinal"), [(60.0, -1), (-60.0, 1)])
def test_o_volante_vira_como_virar_em_qualquer_altura_da_mao(
    theta: float, esquerda: float, sinal: int
) -> None:
    """O gesto medido em 06/11 com o controle de pé sai em `ABS_RY` e tem de mover a câmera."""
    dh, dv = _um_tique(_volante(theta, esquerda), MIRA, gravidade=_gravidade(theta))
    assert dv == 0
    assert dh == pytest.approx(sinal * FRACAO_A_60_GRAUS_S * rot.DEFLEXAO_MAXIMA, abs=1)


def test_o_gesto_entre_virar_e_volante_nao_vale_em_dobro() -> None:
    theta = 30.0
    meio = tuple(
        (a + b) / math.sqrt(2)
        for a, b in zip(_virar(theta, 60.0), _volante(theta, 60.0), strict=True)
    )
    dh, _dv = _um_tique(meio, MIRA, gravidade=_gravidade(theta))
    assert dh == pytest.approx(-FRACAO_A_60_GRAUS_S * rot.DEFLEXAO_MAXIMA, abs=1)


def test_o_volante_segue_andando_com_a_gravidade_saindo_para_o_lado() -> None:
    """Rolar 45° leva a gravidade ao `x`, e o plano em y e z não pode encolher a mira."""
    uy, uz = _gravidade(90.0)[1:]
    rolada = (math.sin(math.radians(45.0)), uy * math.cos(math.radians(45.0)),
              uz * math.cos(math.radians(45.0)))
    dh = _um_tique(_volante(90.0, 60.0), MIRA, gravidade=rolada)[0]
    assert dh == pytest.approx(-FRACAO_A_60_GRAUS_S * rot.DEFLEXAO_MAXIMA, abs=1)


def test_o_controle_deitado_de_lado_nao_divide_por_zero() -> None:
    assert _um_tique((0.0, 60.0, 0.0), MIRA, gravidade=(1.0, 0.0, 0.0)) == (0, 0)


def test_o_sentido_e_o_da_mao_medido_em_06_11() -> None:
    assert _um_tique((0.0, 60.0, 0.0), MIRA)[0] < 0, "esquerda tem de ir à esquerda"
    assert _um_tique((0.0, -60.0, 0.0), MIRA)[0] > 0
    assert _um_tique((60.0, 0.0, 0.0), MIRA)[1] < 0, "nariz para cima tem de ir para cima"
    assert _um_tique((-60.0, 0.0, 0.0), MIRA)[1] > 0


def test_inverter_troca_cada_eixo_sozinho() -> None:
    giro = (60.0, 60.0, 0.0)
    normal = _um_tique(giro, MIRA)
    assert _um_tique(
        giro, rot.ArranjoDeMovimento(destino=MIRA.destino, inverter_horizontal=True)
    ) == (-normal[0], normal[1])
    assert _um_tique(
        giro, rot.ArranjoDeMovimento(destino=MIRA.destino, inverter_vertical=True)
    ) == (normal[0], -normal[1])


def test_o_gesto_diagonal_passa_nos_dois_eixos() -> None:
    dh, dv = _um_tique((40.0, 100.0, 0.0), MIRA)
    assert abs(dh) / rot.DEFLEXAO_MAXIMA > rot.PISO_PADRAO
    assert abs(dv) / rot.DEFLEXAO_MAXIMA > rot.PISO_PADRAO
    assert (dh, dv) == pytest.approx((-109, -64), abs=2)


@pytest.mark.parametrize("sens", range(1, 11))
def test_a_mao_lenta_sai_da_zona_morta_do_jogo_em_toda_sensibilidade(sens: int) -> None:
    arranjo = rot.ArranjoDeMovimento(
        destino=MIRA.destino, sensibilidade_h=sens, sensibilidade_v=sens
    )
    dh, dv = _um_tique((20.0, 20.0, 0.0), arranjo)
    assert abs(dh) >= 34
    assert abs(dv) >= 34


@pytest.mark.parametrize("sens", range(1, 11))
def test_o_tremor_abaixo_da_zona_nao_anda(sens: int) -> None:
    arranjo = rot.ArranjoDeMovimento(
        destino=MIRA.destino, sensibilidade_h=sens, sensibilidade_v=sens
    )
    assert _um_tique((3.0, 3.0, 0.0), arranjo) == (0, 0)


def test_com_a_zona_em_zero_o_ruido_do_sensor_nao_acende_o_piso() -> None:
    arranjo = rot.ArranjoDeMovimento(destino=MIRA.destino, zona_morta_graus_s=0.0)
    assert _um_tique((0.85, 0.85, 0.0), arranjo) == (0, 0)
    assert _um_tique((0.0, 2.0, 0.0), arranjo)[0] != 0


def test_a_sensibilidade_zero_desliga_so_aquele_eixo() -> None:
    giro = (60.0, 60.0, 0.0)
    sem_h = rot.ArranjoDeMovimento(destino=MIRA.destino, sensibilidade_h=0)
    sem_v = rot.ArranjoDeMovimento(destino=MIRA.destino, sensibilidade_v=0)
    assert _um_tique(giro, sem_h)[0] == 0
    assert _um_tique(giro, sem_h)[1] != 0
    assert _um_tique(giro, sem_v)[1] == 0
    assert _um_tique(giro, sem_v)[0] != 0


def test_a_sensibilidade_nao_muda_o_outro_eixo() -> None:
    giro = (60.0, 60.0, 0.0)
    forte = rot.ArranjoDeMovimento(destino=MIRA.destino, sensibilidade_h=10)
    assert _um_tique(giro, forte)[1] == _um_tique(giro, MIRA)[1]
    assert abs(_um_tique(giro, forte)[0]) > abs(_um_tique(giro, MIRA)[0])


def test_o_innocent_assault_anda_com_o_que_ficou_no_perfil() -> None:
    """Sensibilidade 1, zona 60: antes o chip acendia e nada andava."""
    arranjo = rot.ArranjoDeMovimento(
        destino=MIRA.destino, sensibilidade_h=1, sensibilidade_v=1, zona_morta_graus_s=60.0
    )
    assert _um_tique((0.0, 120.0, 0.0), arranjo)[0] == pytest.approx(
        -0.361 * rot.DEFLEXAO_MAXIMA, abs=1
    )


def test_o_piso_e_a_velocidade_do_jogo_sao_do_arranjo() -> None:
    sem_piso = rot.ArranjoDeMovimento(destino=MIRA.destino, piso=0.0)
    assert abs(_um_tique((0.0, 4.0, 0.0), sem_piso)[0]) <= 2
    lento = rot.ArranjoDeMovimento(destino=MIRA.destino, velocidade_do_jogo=90.0)
    assert abs(_um_tique((0.0, 60.0, 0.0), lento)[0]) > abs(
        _um_tique((0.0, 60.0, 0.0), MIRA)[0]
    )


def test_com_o_peso_da_imersao_a_mira_fica_acima_do_piso() -> None:
    for velocidade in (20.0, 60.0, 120.0):
        pesada = _um_tique((0.0, velocidade, 0.0), MIRA, 0.3)[0]
        inteira = _um_tique((0.0, velocidade, 0.0), MIRA)[0]
        assert abs(pesada) >= 34
        assert abs(pesada) < abs(inteira)


def test_o_cursor_nao_ganha_piso_e_tem_h_e_v() -> None:
    cursor = rot.ArranjoDeMovimento(destino=rot.DESTINO_MOUSE, sensibilidade_h=2)
    x, y = rot.pixels((0.001, 0.001, 0.0), cursor)
    assert abs(x) < 0.02 and abs(y) < 0.02
    assert abs(y) == pytest.approx(2 * abs(x))
    assert rot.pixels((0.0, 1.0, 0.0), cursor)[0] < 0


def test_o_que_o_arredondamento_perde_chega_no_tique_seguinte() -> None:
    dono = SimpleNamespace()
    soma = 0
    for _ in range(100):
        soma += rot.deflexao_do_tique(dono, "aa:bb:cc:00:00:01", (0.0, 20.0, 0.0), MIRA)[0]
    exata = 100 * rot._deflexao_exata((0.0, 20.0, 0.0), MIRA, 1.0, None)[0]
    assert soma == pytest.approx(exata, abs=1)


def test_o_resto_nao_atravessa_a_ativacao() -> None:
    dono = SimpleNamespace()
    uniq = "aa:bb:cc:00:00:01"
    rot.deflexao_do_tique(dono, uniq, (0.0, 20.0, 0.0), MIRA)
    assert rot._mira_da_peca(dono, uniq).resto_h != 0.0
    rot.zerar_o_resto(dono, uniq)
    assert rot._mira_da_peca(dono, uniq).resto_h == 0.0


def test_o_resto_nao_anda_com_a_mao_parada() -> None:
    dono = SimpleNamespace()
    uniq = "aa:bb:cc:00:00:01"
    rot.deflexao_do_tique(dono, uniq, (0.0, 20.0, 0.0), MIRA)
    assert rot.deflexao_do_tique(dono, uniq, (0.0, 0.0, 0.0), MIRA) == (0, 0)
    assert rot._mira_da_peca(dono, uniq).resto_h == 0.0


def test_o_tique_e_a_media_do_angulo_sobre_o_tempo_do_kernel() -> None:
    dono = SimpleNamespace()
    assert rot.velocidade_do_tique(dono, "a1", ((0.0, 2.0, 0.0), 0.016), 1.0) == (
        pytest.approx(0.0), pytest.approx(125.0), pytest.approx(0.0))


def test_tique_sem_amostra_repete_ate_50_ms_e_depois_para() -> None:
    dono = SimpleNamespace()
    rot.velocidade_do_tique(dono, "a1", ((0.0, 1.0, 0.0), 0.01), 10.0)
    repetida = rot.velocidade_do_tique(dono, "a1", ((0.0, 0.0, 0.0), 0.0), 10.04)
    assert repetida == (pytest.approx(0.0), pytest.approx(100.0), pytest.approx(0.0))
    assert rot.velocidade_do_tique(dono, "a1", ((0.0, 0.0, 0.0), 0.0), 10.06) == (0.0, 0.0, 0.0)


def test_o_que_acumulou_sem_dreno_nao_vira_movimento() -> None:
    dono = SimpleNamespace()
    assert rot.velocidade_do_tique(dono, "a1", ((0.0, 90.0, 0.0), 3.0), 1.0) == (0.0, 0.0, 0.0)


def test_sem_leitor_nao_ha_velocidade() -> None:
    assert rot.velocidade_do_tique(SimpleNamespace(), "a1", None, 1.0) is None


def test_o_vies_do_zero_sai_da_media() -> None:
    dono = SimpleNamespace()
    rot.definir_o_zero(dono, "a1", rot.ZeroDoControle(giro=(0.0, 5.0, 0.0)))
    assert rot.velocidade_do_tique(dono, "a1", ((0.0, 1.0, 0.0), 0.01), 1.0) == (
        pytest.approx(0.0), pytest.approx(95.0), pytest.approx(0.0))


def _leitor_que_recebe(hz: float, segundos: float, giro_y: float) -> MotionSensorReader:
    leitor = MotionSensorReader(device_path=None, target_uniq="a1")
    leitor._eixos["y"] = giro_y
    passo = 1.0 / hz
    for n in range(int(segundos * hz) + 1):
        leitor._integrar_o_angulo(100.0 + n * passo)
    return leitor


def test_cabo_e_radio_dao_a_mesma_velocidade_com_taxas_diferentes() -> None:
    """Cabo ~250 eventos por segundo, rádio ~600: a mira não pode depender da taxa."""
    por_taxa = []
    for hz in (250.0, 600.0):
        lido = _leitor_que_recebe(hz, 0.5, 90.0).consume_angulo()
        por_taxa.append(rot.velocidade_do_tique(SimpleNamespace(), "a1", lido, 1.0))
    assert por_taxa[0][1] == pytest.approx(90.0)
    assert por_taxa[1][1] == pytest.approx(90.0)


def test_a_gravidade_filtrada_nao_depende_da_taxa_do_tique() -> None:
    finais = []
    for passo in (0.004, 0.016):
        dono = SimpleNamespace()
        rot.gravidade_do_tique(dono, "a1", (0.0, 1.0, 0.0), 1.0)
        agora = 1.0
        while agora < 1.2:
            agora += passo
            rot.gravidade_do_tique(dono, "a1", (0.0, 0.0, 1.0), agora)
        finais.append(rot._mira_da_peca(dono, "a1").gravidade)
    assert finais[0][2] == pytest.approx(finais[1][2], abs=0.04)


def test_sem_gravidade_lida_o_horizontal_e_o_gy() -> None:
    dono = SimpleNamespace()
    assert rot.gravidade_do_tique(dono, "a1", None, 1.0) is None
    assert rot.gravidade_do_tique(dono, "a1", (0.0, 0.0, 0.0), 1.0) is None
    assert _um_tique((0.0, 60.0, 0.0), MIRA, gravidade=None)[0] != 0


def test_o_tique_de_quatro_pecas_fica_no_teto_medido() -> None:
    """A conta nova não pode pesar no laço: 12 µs nas quatro peças, medidos em 06/11."""
    import time

    dono = SimpleNamespace()
    pecas = [f"aa:bb:cc:00:00:0{n}" for n in range(1, 5)]
    inicio = time.perf_counter()
    voltas = 2000
    for volta in range(voltas):
        agora = 1.0 + volta * 0.004
        for uniq in pecas:
            velocidade = rot.velocidade_do_tique(dono, uniq, ((0.1, 0.8, 0.2), 0.004), agora)
            gravidade = rot.gravidade_do_tique(dono, uniq, (0.0, 0.9, 0.3), agora)
            rot.parada_agora(dono, uniq, velocidade, (0.0, 0.9, 0.3), agora)
            rot.deflexao_do_tique(dono, uniq, velocidade, MIRA, 1.0, gravidade)
    por_tique = (time.perf_counter() - inicio) / voltas
    assert por_tique < 0.000_250, f"{por_tique * 1e6:.0f} µs por tique nas quatro peças"
