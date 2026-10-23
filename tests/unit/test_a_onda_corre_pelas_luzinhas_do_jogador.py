"""A Onda corre pelas luzinhas do jogador (A-ONDA-CORRE-PELAS-LUZINHAS-DO-JOGADOR-01, 22/10/2026).

A crista da Onda já andava pelos cinco LEDs no desenho (``brilhos_da_onda``), mas o daemon levava só
a barra. Agora a Onda é uma base com luzinhas: o quadro único do backend
(``pintar_o_quadro_da_luz_sem_lembrar``, o das Estrelas) leva a barra, as luzinhas e o degrau num
report só no rádio. A luzinha é liga/desliga: acende quando a crista passa do meio do passeio. Entre
uma passada e outra nenhuma acende e o número do jogador volta, com a barra no piso. Enquanto o
medidor do gesto (``volta_dos_acessorios``) mostra as luzinhas, a Onda segue só na barra.

MORDIDAS (22/10/2026): tirar ``onda`` de ``BASES_COM_LUZINHAS``, escrever a barra avulsa além do
quadro (um segundo report por quadro), devolver as luzinhas sempre acesas em vez do número no
intervalo, ou ignorar ``luzinhas_com_dono`` no laço reprova. Tirar o ramo que manda o controle do
medidor só para a barra reprova o medidor que abre no meio da Onda (o quadro levaria o número por
cima do nível).
"""
from __future__ import annotations

import inspect
import pathlib
import sys
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.lightbar_gatilho import COMMON_PLAYER_LEDS
from hefesto_dualsense4unix.daemon.subsystems import luz_animada as luz
from hefesto_dualsense4unix.daemon.subsystems import volta_dos_acessorios as va
from hefesto_dualsense4unix.profiles import efeitos_de_luz as fx
from hefesto_dualsense4unix.profiles.schema import ler_o_efeito_da_luz

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

RGB = tuple[int, int, int]
Luzinhas = tuple[bool, bool, bool, bool, bool]
#: Faixa forjada (`aa:bb:cc`), nunca endereço de aparelho de verdade.
JOGADORES = [f"aa:bb:cc:00:00:0{n}" for n in range(1, 5)]
#: O número de cada jogador nas cinco luzinhas, como o DualSense o mostra.
NUMEROS: list[Luzinhas] = [
    (False, False, True, False, False),
    (False, True, False, True, False),
    (True, False, True, False, True),
    (True, True, False, True, True),
]
PASSO_S = 1 / 60
RITMOS = range(1, 11)


def _onda(ritmo: int = 5) -> Any:
    efeito = ler_o_efeito_da_luz(f"onda;FF0000;{ritmo}")
    assert efeito is not None
    return efeito


# ---------------------------------------------------------------- o desenho das luzinhas


def test_a_onda_e_uma_base_com_luzinhas() -> None:
    assert "onda" in fx.BASES_COM_LUZINHAS
    assert "onda" not in fx.BASES_DE_DADO_VIVO, "a Onda continua função só do tempo"


@pytest.mark.parametrize("ritmo", RITMOS)
def test_o_limiar_acende_as_cinco_luzinhas_em_ordem(ritmo: int) -> None:
    periodo = fx.periodo_da_onda_s(ritmo)
    primeira_vez: list[float | None] = [None] * 5
    for i in range(int(periodo / PASSO_S)):
        t = i * PASSO_S
        acesas = fx.luzinhas_da_onda(t, periodo)
        if acesas is None:
            continue
        assert sum(acesas) in (1, 2), f"a crista acende uma luzinha ou duas vizinhas: {acesas}"
        for led, acesa in enumerate(acesas):
            if acesa and primeira_vez[led] is None:
                primeira_vez[led] = t
    assert all(t is not None for t in primeira_vez), f"toda luzinha acende: {primeira_vez}"
    instantes = [t for t in primeira_vez if t is not None]
    assert instantes == sorted(instantes) and len(set(instantes)) == 5, instantes


@pytest.mark.parametrize("ritmo", RITMOS)
def test_entre_uma_passada_e_outra_o_numero_volta_com_a_barra_no_piso(ritmo: int) -> None:
    periodo = fx.periodo_da_onda_s(ritmo)
    no_numero = 0
    for i in range(int(periodo / PASSO_S)):
        t = i * PASSO_S
        acesas = fx.luzinhas_da_onda(t, periodo)
        if acesas is None:
            no_numero += 1
            assert fx.brilho_da_onda(t, periodo) == pytest.approx(fx.PISO_DA_ONDA)
    assert no_numero * PASSO_S >= 0.15 * periodo, "o número aparece entre as passadas"
    assert fx.luzinhas_da_onda(0.0, periodo) is None
    assert fx.luzinhas_da_onda(periodo / 2, periodo) == (False, False, True, False, False)


def _o_que_se_ve(efeito: Any, numero: Luzinhas, segundos: float) -> list[Luzinhas]:
    """O que as cinco luzinhas mostram, quadro a quadro: a onda ou, no intervalo, o número."""
    vistos = []
    for i in range(int(segundos / PASSO_S)):
        acesas = fx.luzinhas_no_instante(efeito, i * PASSO_S)
        vistos.append(numero if acesas is None else acesas)
    return vistos


@pytest.mark.parametrize("ritmo", RITMOS)
@pytest.mark.parametrize("jogador", range(4))
def test_nenhuma_luzinha_acende_mais_de_tres_vezes_por_segundo_contando_o_numero(
    ritmo: int, jogador: int
) -> None:
    # D-2210-A-ONDA-CORRE-PELAS-LUZINHAS-DO-JOGADOR (a validar pelo usuário)
    vistos = _o_que_se_ve(_onda(ritmo), NUMEROS[jogador], 10.0)
    for led in range(5):
        subidas = [i * PASSO_S for i in range(1, len(vistos))
                   if vistos[i][led] and not vistos[i - 1][led]]
        for k, inicio in enumerate(subidas):
            no_segundo = sum(1 for t in subidas[k:] if t - inicio < 1.0 - 1e-9)
            assert no_segundo <= 3, f"P{jogador + 1}, ritmo {ritmo}, luzinha {led}: {no_segundo}"


def test_os_outros_efeitos_de_tempo_nao_mexem_nas_luzinhas() -> None:
    for texto in ("respirar;FF0000;5", "relampago;FF0000;5", "mare;FF0000;5", "arco-iris;;5"):
        efeito = ler_o_efeito_da_luz(texto)
        assert efeito is not None
        assert all(fx.luzinhas_no_instante(efeito, i * 0.1) is None for i in range(100)), texto


# ---------------------------------------------------------------- o laço leva o quadro único


def _laco() -> tuple[luz.LuzAnimada, list[tuple[str, RGB]], list[tuple[str, RGB, Any]]]:
    barra: list[tuple[str, RGB]] = []
    quadros: list[tuple[str, RGB, Any]] = []
    laco = luz.LuzAnimada(
        lambda u, c: barra.append((u, c)), lambda u: None,
        quadro=lambda u, c, lz: quadros.append((u, c, lz)))
    return laco, barra, quadros


def _plano(ritmo: int = 10) -> dict[str, luz.PlanoDoControle]:
    return {u: luz.PlanoDoControle(_onda(ritmo), 1.0, i, i + 1) for i, u in enumerate(JOGADORES)}


def test_a_onda_sai_pelo_quadro_unico_nos_quatro_controles() -> None:
    laco, barra, quadros = _laco()
    segundos = 6.0
    for i in range(int(segundos * 60)):
        laco.tique(100.0 + i / 60, _plano())
    assert quadros and not barra, "o quadro único leva tudo; a barra avulsa não sai"
    assert {u for u, _, _ in quadros} == set(JOGADORES)
    for uniq in JOGADORES:
        dele = [q for q in quadros if q[0] == uniq]
        assert len(dele) <= luz.QUADROS_POR_SEGUNDO_MAXIMO * segundos + 1, uniq
        assert any(lz is None for _, _, lz in dele), f"{uniq}: o número nunca voltou"
        assert {lz for _, _, lz in dele if lz is not None} >= {
            (True, False, False, False, False), (False, False, False, False, True)}, uniq


def test_com_o_medidor_do_gesto_a_onda_fica_so_na_barra_e_volta_depois() -> None:
    laco, barra, quadros = _laco()
    dono = frozenset({JOGADORES[1]})
    agora = 100.0
    for _ in range(90):
        agora += PASSO_S
        laco.tique(agora, _plano(), luzinhas_com_dono=dono)
    assert JOGADORES[1] not in {u for u, _, _ in quadros}, "a onda brigou com o medidor"
    assert {u for u, _ in barra} == {JOGADORES[1]}, "a barra do controle do medidor segue"
    quadros.clear()
    for _ in range(90):
        agora += PASSO_S
        laco.tique(agora, _plano())
    assert JOGADORES[1] in {u for u, _, _ in quadros}, "o medidor fechou e a onda voltou"


def test_o_medidor_que_abre_no_meio_da_onda_nao_leva_o_numero_por_cima() -> None:
    """O caso de quem joga: a Onda já corre pelas luzinhas e o gesto abre o medidor. Nenhum
    quadro sai mais para esse controle (nem o ``None`` que devolveria o número por cima do
    nível); só a barra segue, e os outros três continuam no quadro."""
    laco, barra, quadros = _laco()
    agora = 100.0
    for _ in range(120):
        agora += PASSO_S
        laco.tique(agora, _plano())
    assert any(u == JOGADORES[1] and lz is not None for u, _, lz in quadros), "a onda não correu"
    quadros.clear()
    barra.clear()
    dono = frozenset({JOGADORES[1]})
    for _ in range(120):
        agora += PASSO_S
        laco.tique(agora, _plano(), luzinhas_com_dono=dono)
    assert JOGADORES[1] not in {u for u, _, _ in quadros}, (
        "com o medidor aberto, o quadro ainda escreveu as luzinhas desse controle")
    assert {u for u, _ in barra} == {JOGADORES[1]}, "a barra do controle do medidor segue"
    assert {u for u, _, _ in quadros} == set(JOGADORES) - dono


def _volta() -> va.VoltaDosAcessorios:
    ligacoes = va.Ligacoes(
        motores=lambda u, fraco, forte: None,
        ler_luzinhas=lambda u: (NUMEROS[0], 2),
        luzinhas=lambda u, acesas, degrau: None,
        barra=lambda u, c: None,
        soltar_barra=lambda u: None,
        pode_falar=lambda u: True,
        o_jogo_pinta=lambda u: False,
        estilo=lambda: None,
    )
    return va.VoltaDosAcessorios(ligacoes)


def test_o_medidor_aberto_segura_as_luzinhas_e_ao_fechar_as_solta() -> None:
    volta = _volta()
    assert volta.segurando_as_luzinhas() == frozenset()
    volta.ao_estado({"ligado": True, "nivel": 2}, 10.0)
    volta.ao_gesto({"uniq": JOGADORES[2], "gesto": "sobe"}, 10.0)
    assert volta.segurando_as_luzinhas() == frozenset({JOGADORES[2]})
    volta.soltar_tudo(20.0)
    assert volta.segurando_as_luzinhas() == frozenset()


def test_o_passo_pergunta_ao_medidor_do_tato_vivo_quem_mostra_as_luzinhas() -> None:
    from hefesto_dualsense4unix.daemon.subsystems.tato_vivo import TatoVivo

    motor = TatoVivo([])
    motor.volta = _volta()
    daemon = SimpleNamespace(_tato_vivo=motor)
    passo = luz.Passo(daemon, luz.LuzAnimada(lambda u, c: None, lambda u: None))
    assert passo._quem_mostra_as_luzinhas() == frozenset()
    motor.volta.ao_estado({"ligado": True, "nivel": 1}, 10.0)
    motor.volta.ao_gesto({"uniq": JOGADORES[3], "gesto": "desce"}, 10.0)
    assert passo._quem_mostra_as_luzinhas() == frozenset({JOGADORES[3]})
    assert luz.Passo(SimpleNamespace(), passo.luz)._quem_mostra_as_luzinhas() == frozenset()
    assert "luzinhas_com_dono=self._quem_mostra_as_luzinhas()" in inspect.getsource(luz.Passo)


# ---------------------------------------------------------------- um report por quadro


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
    """O backend de verdade com dois controles no cabo e dois no rádio, de mentira por baixo."""
    ctl: Any = bp.PyDualSenseController()
    handles = [_handle(t) for t in ("usb", "usb", "bt", "bt")]
    macs = [m.upper() for m in JOGADORES]
    ctl._handles = dict(zip(macs, handles, strict=True))
    nos = {m: _NoDeLed() for m in macs}
    ctl._sysfs = dict(nos)
    numero = {m.replace(":", ""): NUMEROS[i] for i, m in enumerate(macs)}
    ctl._merged_desired_for_key = lambda key, **_k: bp._DesiredOutput(
        player_leds=numero[str(key).upper().replace(":", "")], player_led_brightness=2)
    return ctl, handles, nos


def test_a_onda_e_um_report_por_quadro_no_radio_e_o_numero_volta_nos_dois_transportes() -> None:
    ctl, handles, nos = _mesa()
    daemon = SimpleNamespace(controller=ctl)
    escrever, soltar = luz.escritor_de_producao(daemon)
    contados: dict[str, int] = {}
    ponta = luz.escritor_do_quadro(daemon)

    def quadro(uniq: str, cor: RGB, luzinhas: Any) -> object:
        contados[uniq] = contados.get(uniq, 0) + 1
        return ponta(uniq, cor, luzinhas)

    laco = luz.LuzAnimada(escrever, soltar, quadro=quadro)
    for i in range(int(4.0 * 60)):
        laco.tique(100.0 + i / 60, _plano(10))
    for indice, uniq in enumerate(JOGADORES):
        no = nos[uniq.upper()]
        assert contados.get(uniq, 0) > 10, uniq
        assert len(no.cores) == contados[uniq], f"{uniq}: a cor vai em todo quadro"
        assert NUMEROS[indice] in no.numeros, f"{uniq}: o número do jogador não voltou"
        assert (True, False, False, False, False) in no.numeros, f"{uniq}: a onda não correu"
        escritos = handles[indice].escritos
        if indice >= 2:  # rádio: UM report 0x31 por quadro, com a barra e as luzinhas
            radio = [r for r in escritos if r[0] == 0x31]
            assert len(radio) == len(escritos) == contados[uniq], (
                f"{uniq}: {len(escritos)} reports para {contados[uniq]} quadros")
            mascaras = {r[3 + COMMON_PLAYER_LEDS] & 0x1F for r in radio}
            assert len(mascaras) >= 5, f"{uniq}: as luzinhas não andaram no report: {mascaras}"
        else:  # cabo: a cor e o número pelo nó; o degrau não se repete a cada quadro
            assert len(escritos) <= 1, f"{uniq}: o cabo escreveu {len(escritos)} reports"
    assert not ctl._desired_by_uniq, "o quadro da onda não entra no estado desejado"


# ---------------------------------------------------------------- a tela diz o que o aparelho faz


def test_a_dica_da_onda_diz_que_ela_corre_pelas_luzinhas_e_pela_barra() -> None:
    """A tela diz o que o aparelho faz: a Onda sai pelo quadro único, então a dica fala das
    luzinhas e da barra."""
    from pacotes import a04_iluminacao as a04

    assert "pintar_o_quadro_da_luz_sem_lembrar" in inspect.getsource(luz.escritor_do_quadro)
    frase = a04.DICA_DA_BASE["onda"]
    assert "luzinhas" in frase and "barra" in frase, frase
    assert frase[0].isupper() and frase.endswith(".") and len(frase) <= 36, frase
