"""A luz animada ganha a lista boa e cura o piscar e o arco-íris (A-LUZ-ANIMADA-GANHA-A-LISTA-BOA).

Funções puras, sem relógio: nenhum efeito sobe mais de 3 vezes por segundo (1 com o «Sem piscar»
da mesa); o piscar tem borda suave e piso; as quatro cores do arco-íris no mesmo instante ficam
a mais de 90 uma da outra; a chama repete a curva com a mesma semente; a maré não aproxima dois
controles; e o motor lê o valor global a cada quadro. Vale para os quatro controles, no cabo e
no Bluetooth: o plano não pergunta pelo transporte.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from itertools import pairwise
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import luz_animada as luz
from hefesto_dualsense4unix.profiles import efeitos_de_luz as fx
from hefesto_dualsense4unix.profiles import estilos_de_jogo, schema
from hefesto_dualsense4unix.profiles.schema import (
    BASES_DA_LUZ,
    ControllerOverrides,
    EfeitoDaLuz,
    LedsConfig,
    MatchAny,
    Profile,
    ler_o_efeito_da_luz,
)
from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

RGB = tuple[int, int, int]
VERMELHO: RGB = (255, 0, 0)
#: Quatro jogadores: faixa forjada (`aa:bb:cc`), nunca endereço de aparelho de verdade.
JOGADORES = [f"aa:bb:cc:00:00:0{n}" for n in range(1, 5)]
RITMOS = range(1, 11)
#: O piso de cada base: o meio do passeio dele é onde se contam as subidas.
PISO = {
    "respirar": fx.PISO_DO_RESPIRAR,
    "piscar": fx.PISO_DO_PISCAR,
    "batimento": fx.PISO_DA_BATIDA,
    "chama": fx.PISO_DA_CHAMA,
}
PASSO_S = 0.005


def _efeito(base: str, ritmo: int = 4, cor: RGB = VERMELHO) -> EfeitoDaLuz:
    cores: tuple[RGB, ...] = () if base == "arco-iris" else (cor,)
    return EfeitoDaLuz(base, cores, ritmo)


def _brilho(cor: RGB) -> float:
    """O brilho da cor como o motor a mede: o canal mais alto (o V do HSV)."""
    return max(cor) / 255


def _subidas(tempos: list[float]) -> int:
    """O maior número de subidas em qualquer janela de 1 s (meio aberto)."""
    mais = 0
    for i, inicio in enumerate(tempos):
        dentro = sum(1 for t in tempos[i:] if t - inicio < 1.0 - 1e-6)
        mais = max(mais, dentro)
    return mais


def _quando_sobe(brilhos: list[float], piso: float) -> list[float]:
    """Os instantes em que o brilho cruza o meio do passeio para cima (com histerese de 10%)."""
    meio = (piso + 1.0) / 2
    folga = 0.1 * (1.0 - piso)
    embaixo, fora = False, []
    for i, b in enumerate(brilhos):
        if b <= meio - folga:
            embaixo = True
        elif embaixo and b >= meio + folga:
            embaixo = False
            fora.append(i * PASSO_S)
    return fora


def _curva(base: str, ritmo: int, sem_piscar: bool, semente: int = 0, segundos: float = 24.0):
    efeito = _efeito(base, ritmo)
    n = int(segundos / PASSO_S)
    return [
        _brilho(fx.cor_no_instante(efeito, i * PASSO_S, 0, semente, sem_piscar))
        for i in range(n)
    ]


# ---------------------------------------------------------------- a lista


def test_a_lista_tem_as_tres_novas_e_o_motor_sabe_desenhar_cada_uma() -> None:
    # Prova da D-1510-A-BATIDA-DO-CORACAO-SE-GRAVA-BATIMENTO.
    assert set(BASES_DA_LUZ) == {"respirar", "piscar", "arco-iris", "batimento", "chama", "mare"}
    for base in BASES_DA_LUZ:
        texto = f"{base};FF0000;4" if base != "arco-iris" else f"{base};;4"
        efeito = ler_o_efeito_da_luz(texto)
        assert efeito is not None, f"{base}: o perfil tem de aceitar a base"
        cor = fx.cor_no_instante(efeito, 1.234)
        assert len(cor) == 3 and all(0 <= c <= 255 for c in cor)


# ---------------------------------------------------------------- o teto de trocas por segundo


@pytest.mark.parametrize("base", sorted(PISO))
@pytest.mark.parametrize("ritmo", RITMOS)
def test_nenhum_efeito_passa_de_tres_subidas_por_segundo(base: str, ritmo: int) -> None:
    subidas = _subidas(_quando_sobe(_curva(base, ritmo, False), PISO[base]))
    assert subidas <= 3, f"{base} no ritmo {ritmo}: {subidas} subidas em 1 s"


@pytest.mark.parametrize("base", sorted(PISO))
@pytest.mark.parametrize("ritmo", RITMOS)
def test_com_o_sem_piscar_nada_passa_de_uma_subida_por_segundo(base: str, ritmo: int) -> None:
    subidas = _subidas(_quando_sobe(_curva(base, ritmo, True), PISO[base]))
    assert subidas <= 1, f"{base} no ritmo {ritmo}: {subidas} subidas em 1 s"


@pytest.mark.parametrize("sem_piscar", [False, True])
@pytest.mark.parametrize("base", sorted(PISO))
def test_todo_efeito_tem_piso_e_nunca_apaga_a_barra(base: str, sem_piscar: bool) -> None:
    for ritmo in RITMOS:
        curva = _curva(base, ritmo, sem_piscar, segundos=12.0)
        # sem piscar o piscar vira respirar, e o fundo dele é o do respirar
        piso = fx.PISO_DO_RESPIRAR if base == "piscar" and sem_piscar else PISO[base]
        assert min(curva) >= piso - 0.01, f"{base} no ritmo {ritmo}: {min(curva)}"
        assert max(curva) > 0.95 or base == "chama"


def test_o_piscar_no_ritmo_mais_alto_chega_aos_tres_por_segundo_e_nao_passa() -> None:
    # Prova da D-1510-O-VALOR-DA-TABELA-E-O-DO-RITMO-10.
    subidas = _subidas(_quando_sobe(_curva("piscar", 10, False), fx.PISO_DO_PISCAR))
    assert subidas == 3


def test_a_batida_do_coracao_tem_duas_subidas_por_segundo_e_uma_sem_piscar() -> None:
    normal = _subidas(_quando_sobe(_curva("batimento", 10, False), fx.PISO_DA_BATIDA))
    suave = _quando_sobe(_curva("batimento", 10, True), fx.PISO_DA_BATIDA)
    assert normal == 2
    assert fx.periodo_da_batida_s(10) == pytest.approx(1.0)
    assert fx.periodo_da_batida_s(10, True) == pytest.approx(1.5)
    assert suave[1] - suave[0] == pytest.approx(1.5, abs=0.02), "um pico a cada 1,5 s"


def test_o_piscar_sem_piscar_e_o_respirar_no_mesmo_ritmo() -> None:
    # Prova da D-1510-O-PISCAR-SEM-PISCAR-VIRA-RESPIRAR.
    piscar = _efeito("piscar", 6)
    respirar_do_ritmo = _efeito("respirar", 6)
    periodo = max(1.0 / fx.frequencia_do_piscar_hz(6), 1.0)
    for t in (0.0, 0.3, 0.7, 1.1, 2.9):
        esperado = fx.cor_no_instante(
            EfeitoDaLuz("respirar", respirar_do_ritmo.cores, round(10.0 / periodo)), t
        )
        assert fx.cor_no_instante(piscar, t, sem_piscar=True) == esperado


# ---------------------------------------------------------------- o piscar curado


def test_o_piscar_tem_borda_suave_de_150_ms() -> None:
    """Da subida de 5% a 95% leva ao menos 100 ms: a onda quadrada levava zero."""
    for ritmo in RITMOS:
        curva = _curva("piscar", ritmo, False, segundos=6.0)
        piso, topo = min(curva), max(curva)
        dez, noventa = piso + 0.05 * (topo - piso), piso + 0.95 * (topo - piso)
        subindo: float | None = None
        durou: list[float] = []
        for i in range(1, len(curva)):
            if curva[i - 1] < dez <= curva[i]:
                subindo = i * PASSO_S
            if subindo is not None and curva[i - 1] < noventa <= curva[i]:
                durou.append(i * PASSO_S - subindo)
                subindo = None
        assert durou and min(durou) >= 0.10, f"ritmo {ritmo}: a subida levou {min(durou or [0])}"


@pytest.mark.parametrize("ritmo", RITMOS)
def test_o_piscar_vermelho_nunca_chega_ao_preto(ritmo: int) -> None:
    efeito = _efeito("piscar", ritmo)
    cores = [fx.cor_no_instante(efeito, i * PASSO_S) for i in range(int(8 / PASSO_S))]
    assert (0, 0, 0) not in cores
    assert min(c[0] for c in cores) >= round(fx.PISO_DO_PISCAR * 255)


def test_o_piscar_troca_de_cor_so_com_a_luz_no_piso() -> None:
    efeito = EfeitoDaLuz("piscar", (VERMELHO, (0, 0, 255)), 5)
    vistas = [fx.cor_no_instante(efeito, i * PASSO_S) for i in range(int(6 / PASSO_S))]
    for antes, depois in pairwise(vistas):
        if (antes[0] > 0) != (depois[0] > 0) and max(antes + depois) > 0.16 * 255:
            pytest.fail(f"a cor trocou no alto: {antes} -> {depois}")
    assert {c[0] > 0 for c in vistas} == {True, False}, "as duas cores aparecem"


# ---------------------------------------------------------------- o arco-íris curado


@pytest.mark.parametrize("ritmo", RITMOS)
def test_as_quatro_cores_do_arco_iris_no_mesmo_instante_ficam_a_mais_de_90(ritmo: int) -> None:
    # Prova da D-1510-O-ARCO-IRIS-E-A-MARE-TEM-UM-RELOGIO-SO.
    efeito = _efeito("arco-iris", ritmo)  # (noqa-acento) chave ASCII
    for i in range(0, 400):
        t = i * 0.1
        quatro = [fx.cor_no_instante(efeito, t, posicao) for posicao in range(4)]
        pior = min(
            estilos_de_jogo._distancia(a, b) for k, a in enumerate(quatro) for b in quatro[k + 1:]
        )
        assert pior >= estilos_de_jogo.DISTANCIA_MINIMA, f"t={t}: {quatro}"


def test_a_volta_do_arco_iris_dura_ao_menos_8_s_em_todo_ritmo() -> None:
    # Prova da D-1510-O-VALOR-DA-TABELA-E-O-DO-RITMO-10.
    assert all(fx.periodo_do_arco_iris_s(r) >= 8.0 for r in RITMOS)
    assert fx.periodo_do_arco_iris_s(10) < fx.periodo_do_arco_iris_s(1)


def test_o_arco_iris_defasa_um_quarto_de_volta_por_controle() -> None:
    efeito = _efeito("arco-iris", 5)  # (noqa-acento) chave ASCII
    volta = fx.periodo_do_arco_iris_s(5)
    for posicao in range(1, 4):
        a = fx.cor_no_instante(efeito, 0.0, posicao)
        b = fx.cor_no_instante(efeito, posicao * volta / 4, 0)
        assert all(abs(x - y) <= 1 for x, y in zip(a, b, strict=True)), (posicao, a, b)


# ---------------------------------------------------------------- a chama e a maré


def test_a_chama_com_a_mesma_semente_da_a_mesma_curva() -> None:
    a = _curva("chama", 6, False, semente=1234, segundos=12.0)
    b = _curva("chama", 6, False, semente=1234, segundos=12.0)
    c = _curva("chama", 6, False, semente=999, segundos=12.0)
    assert a == b
    assert a != c, "outra semente passeia por outro caminho"


@pytest.mark.parametrize("sem_piscar", [False, True])
def test_a_chama_fica_entre_06_e_10_e_muda_no_maximo_uma_vez_por_segundo(sem_piscar: bool) -> None:
    for ritmo in RITMOS:
        curva = _curva("chama", ritmo, sem_piscar, semente=77, segundos=20.0)
        assert min(curva) >= fx.PISO_DA_CHAMA - 0.01 and max(curva) <= 1.0
    troca = fx.troca_da_chama_s(10, sem_piscar)
    assert troca == (3.0 if sem_piscar else 1.0)


def test_a_mare_anda_ate_30_graus_e_volta_ao_fim_do_periodo() -> None:
    assert fx.deslocamento_da_mare(0.0, 8.0) == pytest.approx(0.0)
    assert fx.deslocamento_da_mare(4.0, 8.0) == pytest.approx(30 / 360)
    assert fx.deslocamento_da_mare(8.0, 8.0) == pytest.approx(0.0, abs=1e-12)
    assert fx.periodo_da_mare_s(10) == 8.0


@pytest.mark.parametrize("chave", sorted(set(estilos_de_jogo.POR_CHAVE) - estilos_de_jogo.SEM_COR))
def test_a_mare_nao_aproxima_dois_controles_alem_da_distancia_minima(chave: str) -> None:
    base = estilos_de_jogo.as_quatro(chave)
    piso = min(
        estilos_de_jogo._distancia(a, b) for i, a in enumerate(base) for b in base[i + 1:]
    )
    chao = min(estilos_de_jogo.DISTANCIA_MINIMA, piso)
    amplitude = fx.amplitude_da_mare(base)
    for i in range(0, 161):
        t = i * 0.1
        agora = [
            fx.cor_no_instante(_efeito("mare", 10, cor), t, amplitude=amplitude) for cor in base
        ]
        pior = min(
            estilos_de_jogo._distancia(a, b) for k, a in enumerate(agora) for b in agora[k + 1:]
        )
        assert pior >= chao - 3, f"{chave} t={t}: {pior} < {chao}"


def test_a_mare_inteira_aproximaria_os_controles_de_algum_estilo() -> None:
    """A régua acima não é vazia: sem a amplitude, ao menos um estilo cai da distância mínima."""
    quedas = 0
    for chave in set(estilos_de_jogo.POR_CHAVE) - estilos_de_jogo.SEM_COR:
        base = estilos_de_jogo.as_quatro(chave)
        chao = min(
            estilos_de_jogo.DISTANCIA_MINIMA,
            min(estilos_de_jogo._distancia(a, b) for i, a in enumerate(base) for b in base[i + 1:]),
        )
        agora = [fx.cor_no_instante(_efeito("mare", 10, cor), 4.0) for cor in base]
        pior = min(
            estilos_de_jogo._distancia(a, b) for k, a in enumerate(agora) for b in agora[k + 1:]
        )
        quedas += pior < chao - 3
    assert quedas >= 1


def test_um_controle_so_em_mare_anda_os_30_graus_inteiros() -> None:
    # Prova da D-1510-A-MARE-SE-AFASTA-SO-DE-QUEM-ESTA-EM-MARE.
    assert fx.amplitude_da_mare([VERMELHO]) == 1.0
    assert fx.amplitude_da_mare([]) == 1.0


# ---------------------------------------------------------------- o plano: lugar, semente e maré


def _perfil(efeitos: dict[str, str] | str | None) -> Profile:
    if isinstance(efeitos, dict):
        por_controle = {
            u.replace(":", ""): ControllerOverrides(leds=LedsConfig(efeito=e))
            for u, e in efeitos.items()
        }
        return Profile(name="regua", match=MatchAny(), controllers=por_controle)
    return Profile(name="regua", match=MatchAny(), leds=LedsConfig(efeito=efeitos))


def test_o_plano_da_o_lugar_e_uma_semente_estavel_a_cada_controle() -> None:
    plano = luz.plano_do_perfil(
        _perfil("chama;FF8800;5"), JOGADORES, mesa_em_economia=False, em_economia=frozenset()
    )
    assert [plano[u].posicao for u in JOGADORES] == [0, 1, 2, 3]
    assert len({plano[u].semente for u in JOGADORES}) == 4
    de_novo = luz.plano_do_perfil(
        _perfil("chama;FF8800;5"), JOGADORES, mesa_em_economia=False, em_economia=frozenset()
    )
    assert {u: p.semente for u, p in plano.items()} == {u: p.semente for u, p in de_novo.items()}


def test_o_plano_encurta_a_mare_de_quem_se_aproximaria_dos_outros() -> None:
    # Prova da D-1510-A-MARE-SE-AFASTA-SO-DE-QUEM-ESTA-EM-MARE.
    base = estilos_de_jogo.as_quatro("point_and_click")
    efeitos = {
        u: "mare;{:02X}{:02X}{:02X};10".format(*cor) for u, cor in zip(JOGADORES, base, strict=True)
    }
    plano = luz.plano_do_perfil(
        _perfil(efeitos), JOGADORES, mesa_em_economia=False, em_economia=frozenset()
    )
    assert len(plano) == 4
    assert all(p.amplitude < 1.0 for p in plano.values())
    assert len({p.amplitude for p in plano.values()}) == 1, "os quatro andam o mesmo ângulo"


# ---------------------------------------------------------------- o «Sem piscar» da mesa


@pytest.fixture
def mesa() -> Iterator[dict[str, Any]]:
    """Põe a declaração viva que o motor lê, e a tira no fim."""
    atual: dict[str, Any] = {"declaracao": SimpleNamespace()}
    schema.registrar_declaracao_da_mesa(lambda: atual["declaracao"])
    try:
        yield atual
    finally:
        schema.registrar_declaracao_da_mesa(None)


def _liga(mesa: dict[str, Any], ligado: bool | None) -> None:
    mesa["declaracao"] = SimpleNamespace(luz=SimpleNamespace(sem_piscar=ligado))


def test_o_sem_piscar_nasce_desligado_e_e_um_so_fora_do_perfil(mesa: dict[str, Any]) -> None:
    # Prova da D-1510-O-SEM-PISCAR-E-DO-COMPUTADOR.
    assert schema.sem_piscar_da_mesa() is False
    _liga(mesa, True)
    assert schema.sem_piscar_da_mesa() is True
    _liga(mesa, None)
    assert schema.sem_piscar_da_mesa() is False
    assert "sem_piscar" not in Profile.model_fields
    assert "sem_piscar" not in LedsConfig.model_fields
    assert "sem_piscar" not in ControllerOverrides.model_fields


def test_a_declaracao_do_sem_piscar_passa_pela_maquina() -> None:
    ligada = MaquinaConfig.model_validate(schema.declaracao_do_sem_piscar(True))
    assert schema.sem_piscar_da_declaracao(ligada) is True
    desligada = MaquinaConfig.model_validate(schema.declaracao_do_sem_piscar(False))
    assert schema.sem_piscar_da_declaracao(desligada) is False
    assert schema.sem_piscar_da_declaracao(MaquinaConfig()) is False


def _tocar(
    efeito: str, segundos: float, mexe: Callable[[float], None] | None = None
) -> list[tuple[float, RGB]]:
    """O que o motor escreve num controle a 30 quadros por segundo, com o laço real."""
    escritos: list[tuple[float, RGB]] = []
    relogio = {"t": 0.0}
    motor = luz.LuzAnimada(lambda _u, cor: escritos.append((relogio["t"], cor)), lambda _u: None)
    plano = luz.plano_do_perfil(
        _perfil(efeito), JOGADORES[:1], mesa_em_economia=False, em_economia=frozenset()
    )
    for i in range(int(segundos * 30)):
        relogio["t"] = 1000.0 + i / 30
        if mexe is not None:
            mexe(i / 30)
        motor.tique(relogio["t"], plano)
    return escritos


def _saltos_e_subidas(escritos: list[tuple[float, RGB]]) -> tuple[float, int]:
    brilhos = [_brilho(c) for _t, c in escritos]
    saltos = max(abs(b - a) for a, b in pairwise(brilhos))
    tempos = _quando_sobe_em_quadros(escritos)
    return saltos, _subidas(tempos)


def _quando_sobe_em_quadros(escritos: list[tuple[float, RGB]]) -> list[float]:
    brilhos = [_brilho(c) for _t, c in escritos]
    meio, folga = (fx.PISO_DO_PISCAR + 1.0) / 2, 0.1 * (1.0 - fx.PISO_DO_PISCAR)
    embaixo, tempos = False, []
    for (t, _c), b in zip(escritos, brilhos, strict=True):
        if b <= meio - folga:
            embaixo = True
        elif embaixo and b >= meio + folga:
            embaixo = False
            tempos.append(t)
    return tempos


def test_com_o_valor_global_ligado_o_motor_anima_no_modo_suave(mesa: dict[str, Any]) -> None:
    _liga(mesa, False)
    solto = _tocar("piscar;FF0000;10", 6.0)
    _liga(mesa, True)
    suave = _tocar("piscar;FF0000;10", 6.0)
    _saltos_solto, subidas_solto = _saltos_e_subidas(solto)
    saltos_suave, subidas_suave = _saltos_e_subidas(suave)
    assert subidas_solto == 3, "desligado, o piscar do ritmo 10 sobe 3 vezes por segundo"
    assert subidas_suave <= 1, "ligado, nada passa de uma subida por segundo"
    assert saltos_suave < 0.25, "e cada quadro muda pouco em relação ao anterior"


def test_o_motor_le_o_valor_global_a_cada_quadro_sem_ser_recriado(mesa: dict[str, Any]) -> None:
    _liga(mesa, False)

    def vira(segundo: float) -> None:
        if segundo >= 3.0:
            _liga(mesa, True)

    escritos = _tocar("piscar;FF0000;10", 6.0, vira)
    antes = [(t, c) for t, c in escritos if t < 1003.0]
    depois = [(t, c) for t, c in escritos if t >= 1004.0]
    assert _saltos_e_subidas(antes)[1] == 3
    assert _saltos_e_subidas(depois)[1] <= 1


def test_o_arco_iris_do_motor_mostra_uma_cor_por_controle() -> None:
    plano = luz.plano_do_perfil(
        _perfil("arco-iris;;5"), JOGADORES, mesa_em_economia=False, em_economia=frozenset()
    )
    quadros: dict[str, RGB] = {}
    motor = luz.LuzAnimada(lambda u, cor: quadros.__setitem__(u, cor), lambda _u: None,
                           sem_piscar=lambda: False)
    motor.tique(50.0, plano)
    assert len(quadros) == 4 and len(set(quadros.values())) == 4


@pytest.mark.parametrize("base", sorted(fx.BASES_DO_RELOGIO_COMUM))
@pytest.mark.parametrize("atraso", [0.5, 2.0, 3.7])
def test_quem_entra_depois_segue_o_relogio_da_mesa(base: str, atraso: float) -> None:
    """O controle que entra depois (conectou, ou o jogo soltou a barra dele) não desfaz a
    defasagem do arco-íris nem o ângulo comum da Maré: os dois contam pelo mesmo relógio.
    """
    # Prova da D-1510-O-ARCO-IRIS-E-A-MARE-TEM-UM-RELOGIO-SO.
    texto = "arco-iris;;10" if base == "arco-iris" else "mare;FF0000,0000FF;10"  # (noqa-acento)
    plano = luz.plano_do_perfil(
        _perfil(texto), JOGADORES[:2], mesa_em_economia=False, em_economia=frozenset()
    )
    quadros: dict[str, RGB] = {}
    motor = luz.LuzAnimada(lambda u, cor: quadros.__setitem__(u, cor), lambda _u: None,
                           sem_piscar=lambda: False)
    primeiro, segundo = JOGADORES[:2]
    motor.tique(100.0, {primeiro: plano[primeiro]})
    agora = 100.0 + atraso
    motor.tique(agora, plano)
    efeito = plano[primeiro].efeito
    for uniq in (primeiro, segundo):
        dele = plano[uniq]
        esperado = luz.cor_com_o_brilho(
            fx.cor_no_instante(efeito, atraso, dele.posicao, dele.semente, False, dele.amplitude),
            dele.brilho,
        )
        assert quadros[uniq] == esperado, (uniq, quadros[uniq], esperado)
