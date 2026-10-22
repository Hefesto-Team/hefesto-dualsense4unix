"""A luz de ambiente e de aviso (A-LUZ-DE-AMBIENTE-E-DE-AVISO-01, 22/10/2026).

Quatro itens do grupo «De ambiente» da lista «como a luz se move»: a Aurora (as cores passam devagar
de uma para outra), as Estrelas (as luzinhas cintilam e a barra as acompanha baixinho), a «Cor da
bateria» (verde cheia, amarela na metade, vermelha no fim, cada controle com a carga dele) e a «Cor
da temperatura» (azul no frio, vermelha no calor da máquina, com os limites que o próprio sensor
declara). Em todos: luz nunca preta, no máximo três clarões por segundo e o quadro sai pelo cabo e
pelo rádio.

MORDIDAS (22/10/2026): trocar o ``_nunca_preta`` por ``lambda cor: cor`` reprova a Aurora de cor
preta; trocar ``matiz_da_carga`` por um verde fixo reprova a escala da bateria; ler a carga do
primeiro controle em vez do próprio reprova os quatro controles; trocar o limite descoberto por 95
graus fixos reprova a temperatura; tirar o alisamento do calor reprova o salto; encolher o
``CINTILADA_S`` e o ``NUMERO_S`` a 0,1 s reprova os clarões das Estrelas; mandar as luzinhas por
``pintar_as_luzinhas_sem_lembrar`` e a cor por outra chamada reprova o quadro único; tirar o
``escritor_do_quadro`` do ``start_luz_animada`` reprova a ligação.
"""
from __future__ import annotations

import asyncio
import pathlib
import re
import sys
from itertools import pairwise
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.lightbar_gatilho import (
    COMMON_LIGHTBAR_B,
    COMMON_LIGHTBAR_R,
    COMMON_PLAYER_LEDS,
)
from hefesto_dualsense4unix.daemon.subsystems import luz_animada as luz
from hefesto_dualsense4unix.integrations import temperatura_da_maquina as calor
from hefesto_dualsense4unix.profiles import efeitos_de_luz as fx
from hefesto_dualsense4unix.profiles.schema import (
    BASES_DE_AMBIENTE_DA_LUZ,
    BASES_SEM_COR_DA_LUZ,
    TODAS_AS_BASES_DA_LUZ,
    EfeitoDaLuz,
    ler_o_efeito_da_luz,
)

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

MOCKUP = RAIZ / "mockup" / "04-iluminacao.html"
RGB = tuple[int, int, int]
LARANJA: RGB = (255, 128, 0)
#: Faixa forjada (`aa:bb:cc`), nunca endereço de aparelho de verdade.
JOGADORES = [f"aa:bb:cc:00:00:0{n}" for n in range(1, 5)]
PASSO_S = 1 / 30


# ---------------------------------------------------------------- as bases existem no perfil


def test_as_quatro_bases_de_ambiente_estao_no_perfil_e_as_de_dado_puro_nao_levam_cor() -> None:
    assert BASES_DE_AMBIENTE_DA_LUZ == (
        "aurora", "estrelas", "cor-da-bateria", "cor-da-temperatura")
    for base in BASES_DE_AMBIENTE_DA_LUZ:
        assert base in TODAS_AS_BASES_DA_LUZ
    assert ler_o_efeito_da_luz("aurora;FF8000;5") == EfeitoDaLuz("aurora", (LARANJA,), 5)
    assert ler_o_efeito_da_luz("estrelas;FF8000;5") == EfeitoDaLuz("estrelas", (LARANJA,), 5)
    assert ler_o_efeito_da_luz("cor-da-bateria;;5") == EfeitoDaLuz("cor-da-bateria", (), 5)
    assert ler_o_efeito_da_luz("cor-da-temperatura;;5") == EfeitoDaLuz("cor-da-temperatura", (), 5)
    assert {"cor-da-bateria", "cor-da-temperatura"} <= set(BASES_SEM_COR_DA_LUZ)
    assert not {"aurora", "estrelas"} & set(BASES_SEM_COR_DA_LUZ), "essas duas levam a cor"
    assert ler_o_efeito_da_luz("aurora;;5") is None, "sem cor a Aurora não tem de onde partir"


def test_sem_o_dado_vivo_cada_base_cai_numa_cor_que_nao_e_preta() -> None:
    for texto in ("aurora;FF8000;5", "estrelas;FF8000;5", "cor-da-bateria;;5",
                  "cor-da-temperatura;;5"):
        efeito = ler_o_efeito_da_luz(texto)
        assert efeito is not None
        assert max(fx.cor_no_instante(efeito, 3.0)) > 0, texto


# ---------------------------------------------------------------- a Aurora


def test_a_aurora_com_uma_cor_vai_aos_vizinhos_dela_e_volta() -> None:
    efeito = EfeitoDaLuz("aurora", (LARANJA,), 5)
    assert fx.cores_da_aurora(efeito.cores)[0] == LARANJA
    assert len(set(fx.cores_da_aurora(efeito.cores))) == 3, "a cor e os dois vizinhos"
    periodo = fx.periodo_da_aurora_s(5)
    cores = {fx.cor_da_aurora(efeito, periodo * i / 24) for i in range(24)}
    assert len(cores) > 12, "passa por muitas cores intermediárias"
    assert fx.cor_da_aurora(efeito, 0.0) == fx.cor_da_aurora(efeito, periodo), "fecha o ciclo"


def test_a_aurora_passa_pelas_cores_escolhidas_ate_tres_em_ordem() -> None:
    vermelho, verde, azul, branco = (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)
    efeito = EfeitoDaLuz("aurora", (vermelho, verde, azul, branco), 5)
    assert fx.cores_da_aurora(efeito.cores) == (vermelho, verde, azul), "a quarta não entra"
    periodo = fx.periodo_da_aurora_s(5)
    assert fx.cor_da_aurora(efeito, 0.0) == vermelho
    assert fx.cor_da_aurora(efeito, periodo / 3) == verde
    assert fx.cor_da_aurora(efeito, 2 * periodo / 3) == azul


def test_o_ciclo_da_aurora_vai_de_sessenta_a_vinte_segundos() -> None:
    assert fx.periodo_da_aurora_s(1) == pytest.approx(60.0)
    assert fx.periodo_da_aurora_s(10) == pytest.approx(20.0)
    assert fx.periodo_da_aurora_s(1) > fx.periodo_da_aurora_s(5) > fx.periodo_da_aurora_s(10)


@pytest.mark.parametrize("ritmo", [1, 5, 10])
def test_a_aurora_nunca_e_preta_e_nunca_pisca(ritmo: int) -> None:
    efeito = EfeitoDaLuz("aurora", ((255, 0, 0), (0, 0, 255)), ritmo)
    periodo = fx.periodo_da_aurora_s(ritmo)
    quadros = [fx.cor_da_aurora(efeito, i * PASSO_S) for i in range(int(2 * periodo / PASSO_S))]
    assert all(max(q) > 0 for q in quadros)
    saltos = [max(abs(a[k] - b[k]) for k in range(3)) for a, b in pairwise(quadros)]
    assert max(saltos) <= 12, "a cor anda em linha reta, sem salto"


def test_a_aurora_nunca_e_preta_nem_com_a_cor_escolhida_preta() -> None:
    efeito = EfeitoDaLuz("aurora", ((0, 0, 0), (0, 0, 0)), 5)
    assert all(max(fx.cor_da_aurora(efeito, t)) > 0 for t in range(0, 40, 3))


def test_cada_controle_anda_um_oitavo_de_ciclo_atras_do_anterior() -> None:
    efeito = EfeitoDaLuz("aurora", ((255, 0, 0), (0, 0, 255)), 5)
    quatro = [fx.cor_no_instante(efeito, 10.0, posicao=p) for p in range(4)]
    assert len(set(quatro)) == 4, quatro
    assert "aurora" in fx.BASES_DO_RELOGIO_COMUM, "a mesa conta pelo mesmo relógio"


# ---------------------------------------------------------------- a «Cor da bateria»


def test_a_escala_da_bateria_e_verde_cheia_amarela_na_metade_e_vermelha_no_fim() -> None:
    assert fx.cor_da_carga(100) == (0, 255, 0)
    assert fx.cor_da_carga(50) == (255, 255, 0)
    assert fx.cor_da_carga(10) == (255, 0, 0)
    assert fx.cor_da_carga(3) == (255, 0, 0)
    matizes = [fx.matiz_da_carga(p) for p in range(0, 101, 5)]
    assert matizes == sorted(matizes), "mais carga nunca é mais vermelho"
    meio = fx.cor_da_carga(30)
    assert 0 < meio[1] < 255 and meio[0] == 255, "entre o vermelho e o amarelo anda em linha reta"


def test_a_cor_da_bateria_segue_a_carga_do_proprio_controle() -> None:
    cheio, quase_no_fim = fx.CorDaBateria(), fx.CorDaBateria()
    assert cheio.andar(fx.Entrada(carga=(100, "descarregando")), 1.0) == (0, 255, 0)
    assert quase_no_fim.andar(fx.Entrada(carga=(8, "descarregando")), 1.0) == (255, 0, 0)
    assert cheio.andar(fx.Entrada(carga=(100, "descarregando")), 2.0) == (0, 255, 0), \
        "a carga do outro não mexe nesta"


def test_sem_carga_lida_fica_no_neutro_e_uma_leitura_que_falha_segura_a_ultima() -> None:
    estado = fx.CorDaBateria()
    assert estado.sem_leitura
    assert estado.andar(fx.Entrada(), 0.0) == fx.COR_SEM_LEITURA
    assert max(fx.COR_SEM_LEITURA) > 0, "o neutro não é preto"
    estado.andar(fx.Entrada(carga=(60, "descarregando")), 1.0)
    antes = estado.andar(fx.Entrada(), 2.0)
    assert antes == estado.andar(fx.Entrada(carga=(None, None)), 3.0), "segura a última"
    assert not estado.sem_leitura and antes != fx.COR_SEM_LEITURA


def test_carregando_a_bateria_respira_devagar_sem_apagar_e_sem_passar_de_tres_por_segundo() -> None:
    estado = fx.CorDaBateria()
    quadros = [estado.andar(fx.Entrada(carga=(70, "carregando")), i * PASSO_S) for i in range(900)]
    brilho = [max(q) / 255 for q in quadros]
    assert min(brilho) >= fx.PISO_DO_ACENDE - 0.01, "nunca preta"
    assert max(brilho) - min(brilho) > 0.5, "e a respiração se vê"
    subidas = sum(1 for a, b in pairwise(brilho) if a < 0.6 <= b)
    assert subidas / 30 <= 3, "no máximo três por segundo"
    parada = fx.CorDaBateria()
    fixas = {parada.andar(fx.Entrada(carga=(70, "descarregando")), i * PASSO_S)
             for i in range(60)}
    assert len(fixas) == 1, "descarregando a cor fica parada"


# ---------------------------------------------------------------- a «Cor da temperatura»


def test_a_escala_do_calor_vai_do_azul_ao_vermelho() -> None:
    assert fx.cor_do_calor(0.0) == (0, 0, 255)
    assert fx.cor_do_calor(1.0) == (255, 0, 0)
    assert fx.cor_do_calor(-3.0) == (0, 0, 255) and fx.cor_do_calor(9.0) == (255, 0, 0)
    vermelho = [fx.cor_do_calor(c / 10)[0] for c in range(11)]
    assert vermelho == sorted(vermelho), "mais calor nunca é mais azul"


def test_o_calor_chega_alisado_e_a_cor_nunca_salta() -> None:
    estado = fx.CorDaTemperatura()
    estado.andar(fx.Entrada(calor=0.0), 0.0)
    quadros = [estado.andar(fx.Entrada(calor=1.0), (i + 1) * PASSO_S) for i in range(150)]
    saltos = [max(abs(a[k] - b[k]) for k in range(3)) for a, b in pairwise(quadros)]
    assert max(saltos) < 40, max(saltos)
    assert quadros[0] != (255, 0, 0) and quadros[-1][0] > 200, "anda para o calor novo"
    assert all(max(q) > 0 for q in quadros)


def test_sem_sensor_a_temperatura_nao_inventa_um_numero() -> None:
    estado = fx.CorDaTemperatura()
    assert estado.sem_leitura
    assert estado.andar(fx.Entrada(), 0.0) == fx.COR_SEM_LEITURA
    estado.andar(fx.Entrada(calor=0.5), 1.0)
    assert not estado.sem_leitura
    assert estado.andar(fx.Entrada(), 2.0) != fx.COR_SEM_LEITURA, "a que falha segura a última"


# ---------------------------------------------------------------- o hwmon, com os limites do sensor


def _hwmon(raiz: pathlib.Path, pasta: str, chip: str, **temps: dict[str, int]) -> None:
    d = raiz / pasta
    d.mkdir(parents=True)
    (d / "name").write_text(chip + "\n")
    for nome, campos in temps.items():
        for sufixo, valor in campos.items():
            (d / f"{nome}_{sufixo}").write_text(f"{valor}\n")


def test_descobre_o_processador_e_a_placa_de_video_pelo_nome_do_chip(
        tmp_path: pathlib.Path) -> None:
    _hwmon(tmp_path, "hwmon0", "k10temp", temp1={"input": 60000, "crit": 95000})
    _hwmon(tmp_path, "hwmon1", "amdgpu", temp1={"input": 50000, "crit": 110000})
    _hwmon(tmp_path, "hwmon2", "nvme", temp1={"input": 80000, "crit": 84000})
    _hwmon(tmp_path, "hwmon3", "acpitz", temp1={"input": 80000, "crit": 99000})
    achados = calor.descobrir(tmp_path)
    assert {s.chip for s in achados} == {"k10temp", "amdgpu"}, "disco e ACPI não entram"


def test_o_limite_vem_do_proprio_sensor_e_muda_de_maquina_para_maquina(
        tmp_path: pathlib.Path) -> None:
    uma, outra = tmp_path / "uma", tmp_path / "outra"
    _hwmon(uma, "hwmon0", "k10temp", temp1={"input": 70000, "crit": 90000})
    _hwmon(outra, "hwmon0", "k10temp", temp1={"input": 70000, "crit": 110000})
    c_uma, c_outra = calor.calor_da_maquina(uma), calor.calor_da_maquina(outra)
    assert c_uma == pytest.approx((70 - calor.FRIO_C) / (90 - calor.FRIO_C))
    assert c_outra == pytest.approx((70 - calor.FRIO_C) / (110 - calor.FRIO_C))
    assert c_uma is not None and c_outra is not None and c_uma > c_outra
    assert calor.descobrir(uma)[0].limite_c == pytest.approx(90.0)


def test_sem_crit_vale_o_max_e_sem_nenhum_dos_dois_o_sensor_e_ignorado(
        tmp_path: pathlib.Path) -> None:
    _hwmon(tmp_path, "hwmon0", "coretemp", temp1={"input": 60000, "max": 100000},
           temp2={"input": 60000})
    achados = calor.descobrir(tmp_path)
    assert [s.limite_c for s in achados] == [100.0], "o sensor sem limite não adivinha um"
    assert calor.calor_da_maquina(tmp_path / "nao-existe") is None


def test_o_ryzen_que_nao_declara_limite_usa_o_tctl_maximo_documentado_do_chip(
        tmp_path: pathlib.Path) -> None:
    """O ``k10temp`` dos Ryzen exporta só o ``Tctl`` e os ``Tccd``, sem ``crit`` nem ``max`` (é a
    forma do hwmon de um Ryzen de verdade): a cor da temperatura não pode morrer branca por isso."""
    _hwmon(tmp_path, "hwmon2", "k10temp", temp1={"input": 73625, "label": "Tctl"},
           temp3={"input": 64500, "label": "Tccd1"})
    achados = calor.descobrir(tmp_path)
    assert [s.limite_c for s in achados] == [95.0, 95.0]
    assert calor.calor_da_maquina(tmp_path) == pytest.approx(
        (73.625 - calor.FRIO_C) / (95.0 - calor.FRIO_C))
    _hwmon(tmp_path, "hwmon3", "zenpower", temp1={"input": 60000, "crit": 85000})
    assert {s.limite_c for s in calor.descobrir(tmp_path) if s.chip == "zenpower"} == {85.0}, (
        "o limite declarado vence o documentado")


def test_o_leitor_do_calor_redescobre_quando_o_sensor_some(tmp_path: pathlib.Path) -> None:
    """O hwmon renumera quando um driver volta: o leitor que perdeu os sensores procura de novo."""
    _hwmon(tmp_path, "hwmon0", "amdgpu", temp1={"input": 50000, "crit": 100000})
    relogio = [100.0]
    leitor = calor.LeitorDoCalor(tmp_path, agora=lambda: relogio[0])
    assert leitor.calor() is not None
    (tmp_path / "hwmon0").rename(tmp_path / "hwmon7")
    relogio[0] += calor.VALIDADE_S
    assert leitor.calor() is None
    relogio[0] += calor.REDESCOBRIR_A_CADA_S
    assert leitor.calor() == pytest.approx((50 - calor.FRIO_C) / (100 - calor.FRIO_C))


def test_vale_o_sensor_mais_perto_do_limite_e_o_ilegivel_nao_derruba(
        tmp_path: pathlib.Path) -> None:
    _hwmon(tmp_path, "hwmon0", "k10temp", temp1={"input": 40000, "crit": 100000})
    _hwmon(tmp_path, "hwmon1", "amdgpu", temp1={"input": 90000, "crit": 100000},
           temp2={"input": 50000, "crit": 100000})
    (tmp_path / "hwmon1" / "temp2_input").write_text("lixo\n")
    esperado = (90 - calor.FRIO_C) / (100 - calor.FRIO_C)
    assert calor.calor_da_maquina(tmp_path) == pytest.approx(esperado)
    (tmp_path / "hwmon1" / "temp1_input").write_text("5000\n")  # abaixo do frio: fração 0
    assert calor.calor_da_maquina(tmp_path) == pytest.approx((40 - calor.FRIO_C) / 70)


def test_o_leitor_do_calor_guarda_a_leitura_por_dois_segundos(tmp_path: pathlib.Path) -> None:
    _hwmon(tmp_path, "hwmon0", "k10temp", temp1={"input": 50000, "crit": 100000})
    relogio = [100.0]
    leitor = calor.LeitorDoCalor(tmp_path, agora=lambda: relogio[0])
    primeiro = leitor.calor()
    (tmp_path / "hwmon0" / "temp1_input").write_text("90000\n")
    relogio[0] += 1.0
    assert leitor.calor() == primeiro, "ainda vale a leitura guardada"
    relogio[0] += calor.VALIDADE_S
    assert leitor.calor() != primeiro and leitor.calor() is not None


# ---------------------------------------------------------------- as Estrelas


def _estrelas(ritmo: int, semente: int = 0, segundos: int = 40) -> list[fx.Quadro]:
    estado = fx.Estrelas(LARANJA, ritmo, semente)
    return [estado.quadro(fx.Entrada(), i * PASSO_S) for i in range(int(segundos / PASSO_S))]


@pytest.mark.parametrize("ritmo", [1, 5, 10])
def test_nenhuma_luzinha_acende_mais_de_tres_vezes_por_segundo(ritmo: int) -> None:
    quadros = _estrelas(ritmo)
    for lampada in range(5):
        acesa = [bool(q.luzinhas and q.luzinhas[lampada]) for q in quadros]
        subidas = [i * PASSO_S for i, (a, b) in enumerate(pairwise(acesa)) if b and not a]
        assert subidas, f"a luzinha {lampada} cintila"
        for i, inicio in enumerate(subidas):
            assert sum(1 for t in subidas[i:] if t - inicio < 1.0 - 1e-6) <= 3


def test_uma_cintilada_acende_de_uma_a_tres_luzinhas_e_o_numero_volta_entre_elas() -> None:
    quadros = _estrelas(5)
    cintiladas = [q.luzinhas for q in quadros if q.luzinhas is not None]
    assert cintiladas and all(1 <= sum(c) <= 3 for c in cintiladas)
    assert any(q.luzinhas is None for q in quadros), "entre uma e outra volta o número do jogador"
    fases = [q.luzinhas is None for q in quadros]
    assert any(a != b for a, b in pairwise(fases))


def test_cada_controle_cintila_diferente_e_a_mesma_semente_repete() -> None:
    assert _estrelas(5, semente=1) == _estrelas(5, semente=1)
    um, dois = _estrelas(5, semente=1), _estrelas(5, semente=2)
    assert [q.luzinhas for q in um] != [q.luzinhas for q in dois]


def test_a_barra_das_estrelas_fica_baixa_nunca_preta_e_anda_sem_salto() -> None:
    quadros = _estrelas(5)
    barra = [q.cor for q in quadros]
    assert all(max(c) > 0 for c in barra)
    assert max(max(c) for c in barra) < 200, "ela acompanha baixinho, a estrela é a luzinha"
    saltos = [max(abs(a[k] - b[k]) for k in range(3)) for a, b in pairwise(barra)]
    assert max(saltos) <= 20, max(saltos)


def test_o_ritmo_das_estrelas_estica_os_tempos() -> None:
    assert fx.esticar_das_estrelas(1) > fx.esticar_das_estrelas(10) == pytest.approx(1.0)
    def trocas(ritmo: int) -> int:
        fases = [q.luzinhas is None for q in _estrelas(ritmo, segundos=60)]
        return sum(1 for a, b in pairwise(fases) if a != b)
    assert trocas(1) < trocas(10)


# ---------------------------------------------------------------- o laço de luz


class _Mao:
    """O leitor da mão de mentira: cada controle tem a carga e o calor dele."""

    def __init__(self) -> None:
        self.cargas: dict[str, tuple[int | None, str | None]] = {}
        self.calor: float | None = None
        self.pediu: list[tuple[str, str]] = []

    def __call__(self, uniq: str, base: str) -> fx.Entrada:
        self.pediu.append((uniq, base))
        return fx.Entrada(carga=self.cargas.get(uniq), calor=self.calor)


def _plano(texto: str, uniqs: list[str] | None = None) -> dict[str, luz.PlanoDoControle]:
    efeito = ler_o_efeito_da_luz(texto)
    assert efeito is not None
    return {u: luz.PlanoDoControle(efeito, 1.0, i, i) for i, u in enumerate(uniqs or JOGADORES[:1])}


def _laco(mao: _Mao | None = None) -> tuple[luz.LuzAnimada, list[tuple[str, RGB]],
                                          list[tuple[str, RGB, Any]]]:
    barra: list[tuple[str, RGB]] = []
    quadros: list[tuple[str, RGB, Any]] = []
    laco = luz.LuzAnimada(lambda u, c: barra.append((u, c)), lambda u: None, mao=mao,
                          quadro=lambda u, c, lz: quadros.append((u, c, lz)))
    return laco, barra, quadros


def test_a_bateria_de_cada_controle_pinta_a_cor_da_carga_dele() -> None:
    mao = _Mao()
    mao.cargas = {JOGADORES[0]: (100, "descarregando"), JOGADORES[1]: (8, "descarregando"),
                  JOGADORES[2]: (50, "descarregando"), JOGADORES[3]: (None, None)}
    laco, barra, _ = _laco(mao)
    laco.tique(100.0, _plano("cor-da-bateria;;5", JOGADORES))
    cores = dict(barra)
    assert cores[JOGADORES[0]] == (0, 255, 0)
    assert cores[JOGADORES[1]] == (255, 0, 0)
    assert cores[JOGADORES[2]] == (255, 255, 0)
    assert cores[JOGADORES[3]] == fx.COR_SEM_LEITURA
    assert {(u, b) for u, b in mao.pediu} == {(u, "cor-da-bateria") for u in JOGADORES}


def test_a_temperatura_pinta_o_calor_da_maquina_nos_quatro() -> None:
    mao = _Mao()
    mao.calor = 1.0
    laco, barra, _ = _laco(mao)
    laco.tique(100.0, _plano("cor-da-temperatura;;5", JOGADORES))
    assert [c for _, c in barra] == [(255, 0, 0)] * 4


def test_as_estrelas_saem_num_quadro_so_com_a_barra_e_as_luzinhas() -> None:
    laco, barra, quadros = _laco(_Mao())
    plano = _plano("estrelas;FF8000;5", JOGADORES[:2])
    for i in range(300):
        laco.tique(100.0 + i * PASSO_S, plano)
    assert quadros and not barra, "o quadro único leva tudo; a barra avulsa não é chamada"
    assert {u for u, _, _ in quadros} == set(JOGADORES[:2])
    assert any(lz is not None for _, _, lz in quadros)
    assert any(lz is None for _, _, lz in quadros)
    assert all(max(c) > 0 for _, c, _ in quadros)


def test_o_quadro_das_estrelas_so_sai_quando_muda() -> None:
    laco, _, quadros = _laco(_Mao())
    plano = _plano("estrelas;FF8000;1")
    laco.tique(100.0, plano)
    laco.tique(100.0 + PASSO_S, plano)
    assert len(quadros) == 1, "dois tiques iguais, um quadro"


def test_sair_das_estrelas_no_meio_da_cintilada_devolve_o_numero_do_jogador() -> None:
    """Trocar as Estrelas por outro efeito não deixa as luzinhas presas na cintilada: o primeiro
    quadro do efeito novo leva a barra e o número do jogador juntos, e os seguintes só a barra."""
    laco, barra, quadros = _laco(_Mao())
    estrelas = _plano("estrelas;FF8000;5")
    agora = 100.0
    while not (quadros and quadros[-1][2] is not None):  # até a cintilada estar acesa
        agora += PASSO_S
        laco.tique(agora, estrelas)
        assert agora < 130.0, "as Estrelas nunca cintilaram"
    quadros.clear()
    aurora = _plano("aurora;FF8000;5")
    for i in range(1, 4):
        laco.tique(agora + i * 2.0, aurora)
    assert [lz for _, _, lz in quadros] == [None], "o número volta uma vez, junto com a barra"
    assert barra, "depois do número, a Aurora segue pela barra"


def test_a_aurora_pinta_so_a_barra_pelo_escritor_de_sempre() -> None:
    laco, barra, quadros = _laco(_Mao())
    for i in range(5):
        laco.tique(100.0 + i * 2.0, _plano("aurora;FF8000;5", JOGADORES[:2]))
    assert barra and not quadros


def test_sem_escritor_de_quadro_as_estrelas_pintam_a_barra_e_nao_quebram() -> None:
    barra: list[tuple[str, RGB]] = []
    laco = luz.LuzAnimada(lambda u, c: barra.append((u, c)), lambda u: None, mao=_Mao())
    assert laco.tique(100.0, _plano("estrelas;FF8000;5")) == 1
    assert barra


def test_o_daemon_sobe_o_laco_com_o_escritor_do_quadro() -> None:
    async def subir() -> Any:
        daemon = SimpleNamespace(_tasks=[], _is_stopping=lambda: True, controller=None)
        luz.start_luz_animada(daemon)
        await asyncio.gather(*daemon._tasks, return_exceptions=True)
        return daemon._luz_animada

    laco = asyncio.run(subir())
    assert laco._escrever_quadro is not None


# ---------------------------------------------------------------- o leitor de produção


def _daemon(controles: list[dict[str, Any]]) -> Any:
    return SimpleNamespace(controller=SimpleNamespace(describe_controllers=lambda: controles))


def test_o_leitor_de_producao_le_a_carga_de_cada_controle_pelo_endereco_dele() -> None:
    leitor = luz.leitor_da_mao(_daemon([
        {"uniq": "AA:BB:CC:00:00:01", "battery_pct": 90, "battery_state": "descarregando"},
        {"uniq": "AA:BB:CC:00:00:02", "battery_pct": 7, "battery_state": "carregando"},
    ]))
    assert leitor(JOGADORES[0], "cor-da-bateria").carga == (90, "descarregando")
    assert leitor(JOGADORES[1], "cor-da-bateria").carga == (7, "carregando")
    assert leitor(JOGADORES[2], "cor-da-bateria").carga is None, "controle que não veio: sem carga"


def test_o_leitor_de_producao_le_o_calor_do_hwmon(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Quente:
        def calor(self) -> float:
            return 0.8

    monkeypatch.setattr(calor, "LeitorDoCalor", _Quente)
    assert luz.leitor_da_mao(_daemon([]))(JOGADORES[0], "cor-da-temperatura").calor == 0.8


def test_o_leitor_de_producao_nao_pede_nada_ao_aparelho_para_as_estrelas() -> None:
    assert luz.leitor_da_mao(_daemon([]))(JOGADORES[0], "estrelas") == fx.Entrada()


# ---------------------------------------------------------------- o quadro chega ao controle


class _NoDeLed:
    def __init__(self) -> None:
        self.cores: list[RGB] = []
        self.numeros: list[tuple[bool, ...]] = []
        self.indicator_dir = "/sys/class/leds/x"

    def writable(self) -> bool:
        return True

    def set_rgb(self, r: int, g: int, b: int, *, verify: bool = False) -> bool:
        self.cores.append((r, g, b))
        return True

    def set_players(self, bits: tuple[bool, ...]) -> bool:
        self.numeros.append(tuple(bits))
        return True

    def set_players_verified(self, bits: tuple[bool, ...]) -> bool:
        return self.set_players(bits)

    def invalidate_cache(self) -> None:
        return None

    def get_rgb(self) -> RGB | None:
        return self.cores[-1] if self.cores else None


def _handle(transporte: str) -> Any:
    from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

    escritos: list[list[int]] = []
    handle = SimpleNamespace(
        conType=SimpleNamespace(name="BT_31" if transporte == "bt" else "USB_01"),
        triggerL=DSTrigger(), triggerR=DSTrigger(), light=DSLight(), audio=DSAudio(),
        _raw_trigger_left=None, _raw_trigger_right=None, _output_muted=False, escritos=escritos)

    def _escreve(report: Any) -> int:
        escritos.append(list(report))
        return len(report)

    handle.writeReport = _escreve
    return handle


def _mesa() -> tuple[Any, list[Any], dict[str, _NoDeLed]]:
    ctl = bp.PyDualSenseController()
    handles = [_handle(t) for t in ("usb", "usb", "bt", "bt")]
    macs = [m.upper() for m in JOGADORES]
    ctl._handles = dict(zip(macs, handles, strict=True))
    nos = {m: _NoDeLed() for m in macs}
    ctl._sysfs = dict(nos)
    return ctl, handles, nos


NUMERO_DO_PERFIL = (False, False, True, False, False)


def _com_o_numero_do_perfil(ctl: Any) -> None:
    ctl._merged_desired_for_key = lambda *_a, **_k: bp._DesiredOutput(
        player_leds=NUMERO_DO_PERFIL, player_led_brightness=2)


def _no_0x31(report: list[int]) -> tuple[RGB, int]:
    common = report[3:50]
    cor = (common[COMMON_LIGHTBAR_R], common[COMMON_LIGHTBAR_R + 1], common[COMMON_LIGHTBAR_B])
    return cor, common[COMMON_PLAYER_LEDS]


@pytest.mark.parametrize("indice", [0, 1, 2, 3])
def test_o_quadro_das_estrelas_leva_barra_e_luzinhas_juntas_no_cabo_e_no_radio(indice: int) -> None:
    ctl, handles, nos = _mesa()
    _com_o_numero_do_perfil(ctl)
    mac = JOGADORES[indice]
    luzes = (True, False, True, False, False)
    assert ctl.pintar_o_quadro_da_luz_sem_lembrar(mac, (10, 20, 30), luzes) is True
    assert nos[mac.upper()].cores[-1] == (10, 20, 30)
    assert nos[mac.upper()].numeros[-1] == luzes
    if indice >= 2:  # rádio: UM report 0x31 com a cor e o número
        quadros = [r for r in handles[indice].escritos if r[0] == 0x31]
        assert len(quadros) == 1, "dois reports custariam quatro fatias de rádio"
        cor, bits = _no_0x31(quadros[0])
        assert cor == (10, 20, 30) and bits & 0b00101 == 0b00101 and bits & 0b11010 == 0


def test_com_luzinhas_none_o_numero_do_jogador_e_o_resolvido_do_controle() -> None:
    ctl, _handles, nos = _mesa()
    _com_o_numero_do_perfil(ctl)
    assert ctl.pintar_o_quadro_da_luz_sem_lembrar(JOGADORES[0], (10, 20, 30), None) is True
    assert nos[JOGADORES[0].upper()].numeros[-1] == NUMERO_DO_PERFIL


def test_o_quadro_das_estrelas_nao_entra_no_estado_desejado() -> None:
    ctl, _handles, _nos = _mesa()
    _com_o_numero_do_perfil(ctl)
    ctl.pintar_o_quadro_da_luz_sem_lembrar(JOGADORES[2], (10, 20, 30), (True,) * 4 + (False,))
    assert not ctl._desired_by_uniq


def test_controle_que_nao_esta_ligado_nao_escreve_nada() -> None:
    ctl, handles, _nos = _mesa()
    assert ctl.pintar_o_quadro_da_luz_sem_lembrar("aa:bb:cc:00:00:09", (1, 2, 3), None) is False
    assert not any(h.escritos for h in handles)


def test_o_escritor_de_producao_chama_o_quadro_do_backend() -> None:
    chamadas: list[tuple[str, RGB, Any]] = []

    def pintar(uniq: str, cor: RGB, luzinhas: Any) -> bool:
        chamadas.append((uniq, cor, luzinhas))
        return True

    controller = SimpleNamespace(pintar_o_quadro_da_luz_sem_lembrar=pintar)
    escrever = luz.escritor_do_quadro(SimpleNamespace(controller=controller))
    assert escrever(JOGADORES[0], (1, 2, 3), (True,) * 5) is True
    assert chamadas == [(JOGADORES[0], (1, 2, 3), (True,) * 5)]
    sem_backend = luz.escritor_do_quadro(SimpleNamespace(controller=None))
    assert sem_backend(JOGADORES[0], (1, 2, 3), None) is False


# ---------------------------------------------------------------- a tela


def _doc() -> str:
    bruto = MOCKUP.read_text(encoding="utf-8")
    sem_comentario = re.sub(r"<!--.*?-->", "", bruto, flags=re.S)
    return re.sub(r"<(style|script)\b[^>]*>.*?</\1>", "", sem_comentario, flags=re.S)


def _ctx(n: int = 1) -> Any:
    import pacotes
    from hefesto_dualsense4unix.core.led_control import player_slot_color

    uniq = JOGADORES[n - 1]
    return pacotes.Contexto(
        state={"active_profile": ""},
        mesa=[{"pref": f"p{n}", "jogador": n, "uniq": uniq, "nome": "Régua", "via": "USB",
               "cor": "starlight-blue"}],
        conectados=[{"uniq": uniq, "connected": True, "transport": "usb", "index": n - 1,
                     "player": n, "lightbar_rgb": list(player_slot_color(n))}],
        estados={})


def _gesto(nome: str) -> Any:
    import pacotes

    gesto = pacotes.gesto_da_pagina("04-iluminacao.html", nome)
    assert gesto is not None, nome
    return gesto


def test_o_grupo_de_ambiente_esta_nas_quatro_listas_e_nada_novo_na_tela() -> None:
    doc = _doc()
    listas = re.findall(r'<select class="g4-efeito".*?</select>', doc, flags=re.S)
    assert len(listas) == 4
    for lista in listas:
        grupo = lista.split('<optgroup label="De ambiente">', 1)[1].split("</optgroup>", 1)[0]
        opcoes = re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)</option>', grupo)
        assert opcoes == [("base:aurora", "Aurora"), ("base:estrelas", "Estrelas"),
                          ("base:cor-da-bateria", "Cor da bateria"),
                          ("base:cor-da-temperatura", "Cor da temperatura")]
    assert doc.count('class="g4-efeito"') == 4, "uma lista por controle, nada a mais na tela"


@pytest.mark.parametrize("base", ["aurora", "estrelas", "cor-da-bateria", "cor-da-temperatura"])
@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_escolher_o_efeito_grava_o_texto_e_a_lista_o_reconhece(n: int, base: str) -> None:
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_computador
    from pacotes import a04_iluminacao as a04

    uniq = JOGADORES[n - 1]
    cor = a04.pacote(_ctx(n))["colunas"][uniq]["hex"].lstrip("#").upper()
    _gesto("efeito-da-luz")(_ctx(n), {"uniq": uniq, "valor": f"base:{base}"}, None)
    guardado = o_computador().controles[uniq.replace(":", "")].leds.efeito
    assert guardado == (f"{base};;5" if base in BASES_SEM_COR_DA_LUZ else f"{base};{cor};5")
    coluna = a04.pacote(_ctx(n))["colunas"][uniq]
    assert coluna[a04.CAMPO_DO_EFEITO] == f"base:{base}"
    assert coluna[a04.CAMPO_DA_DICA_DO_EFEITO] == a04.DICA_DA_BASE[base]


def test_trocar_a_cor_leva_a_aurora_e_as_estrelas_junto_mas_nao_a_bateria() -> None:
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_computador
    from pacotes import a04_iluminacao as a04

    class _Ponte:
        def led_set_detalhado(self, *_a: Any, **_k: Any) -> dict[str, Any]:
            return {"aplicado_em": [JOGADORES[0]], "guardado_em": []}

    for base, esperado in (("aurora", "aurora;FF8000;5"), ("estrelas", "estrelas;FF8000;5"),
                           ("cor-da-bateria", "cor-da-bateria;;5")):
        _gesto("efeito-da-luz")(_ctx(), {"uniq": JOGADORES[0], "valor": f"base:{base}"}, None)
        a04.cor(_ctx(), {"uniq": JOGADORES[0], "hex": "FF8000"}, _Ponte())
        assert o_computador().controles["aabbcc000001"].leds.efeito == esperado, base


def test_o_criar_efeitos_novos_recusa_as_de_ambiente() -> None:
    import pacotes

    ctx = pacotes.Contexto(state={"active_profile": ""}, mesa=[], conectados=[], estados={})
    for base in BASES_DE_AMBIENTE_DA_LUZ:
        with pytest.raises(RuntimeError, match="Escolha como a luz se move"):
            pacotes.gesto_da_pagina("04-iluminacao.html", "criar-efeito")(
                ctx, {"forma": {"base": base, "cores": "#ff0000", "ritmo": "5", "nome": "X"}},
                None)
