"""O efeito imersão dos motores ganha a lista nova (O-EFEITO-IMERSAO-DOS-MOTORES-...-01).

Sete padrões (Tranco, Batida, Onda, Coice, Pancada do lado, Ressoar e Ricochete): nenhum passa
de 2000 ms, nenhum passo dura menos de 60 ms e todos terminam em zero. O padrão toca no mesmo
tiro da receita, no motor que a pessoa escolheu, só onde o jogo não vibra o motor, e com o
gatilho que vibra (Metralhadora e vizinhas) só na soltura do tiro. Tudo com dublês: o motor do
rumble é uma lista e o relógio é injetado.
"""
from __future__ import annotations

from itertools import pairwise
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.daemon.subsystems import padroes_de_vibracao as pv
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.profiles import schema
from hefesto_dualsense4unix.profiles.schema import ControllerRumbleOverride

AZUL = "aa:bb:cc:00:00:11"
BRANCO = "aa:bb:cc:00:00:12"
VERMELHO = "aa:bb:cc:00:00:13"
ROXO = "aa:bb:cc:00:00:14"
QUATRO = (AZUL, BRANCO, VERMELHO, ROXO)

_LIVRE = tv.EstadoDoCanal(modo=tv.MODO_XBOX, ha_jogo=True)
_CABO = tv.EstadoDoCanal(modo=tv.MODO_DUALSENSE, ha_jogo=True, sessao_aberta=False)
_RADIO = tv.EstadoDoCanal(modo=tv.MODO_XBOX, ha_jogo=True, sessao_aberta=False)
_JOGO_VIBRA = tv.EstadoDoCanal(
    modo=tv.MODO_DUALSENSE, ha_jogo=True, sessao_aberta=True, visto_ha_s={"rumble": 0.2})
MODO_AUTO = "automatico"  # (noqa-acento)
ESTILO_ACAO = "acao"  # (noqa-acento)


def test_a_lista_final_e_a_da_sprint_sem_o_ronco() -> None:
    assert tuple(pv.PADROES) == ("batida", "onda", "tranco", "coice", "pancada_do_lado",
                                 "ressoar", "ricochete")
    assert pv.ESCOLHAS == (pv.DO_ESTILO, pv.SEM_EFEITO, "tranco", "batida", "onda", "coice",
                           "pancada_do_lado", "ressoar", "ricochete")
    assert "ronco" not in pv.PADROES and "ronco" not in pv.ESCOLHAS
    assert set(pv.ROTULOS) == set(pv.PADROES)
    assert set(pv.DICAS) == set(pv.ESCOLHAS)
    assert all(len(frase) <= 36 for frase in pv.DICAS.values())


def test_o_vocabulario_do_esquema_e_o_da_lista() -> None:
    assert schema.ESCOLHAS_DE_IMERSAO == pv.ESCOLHAS


@pytest.mark.parametrize("forma", list(pv.PADROES))
def test_cada_padrao_cabe_em_2000_ms_tem_passos_de_60_ms_e_termina_em_zero(forma: str) -> None:
    passos = pv.PADROES[forma]
    assert sum(ms for ms, _e, _d in passos) <= pv.TETO_MS == 2000
    assert all(ms >= 60 for ms, _e, _d in passos)
    assert passos[-1][1:] == (0, 0)
    assert pv.duracao_ms(forma) == sum(ms for ms, _e, _d in passos)


def test_o_coice_e_o_golpe_fundo_que_cai_logo() -> None:
    assert pv.PADROES["coice"] == ((60, 200, 120), (60, 0, 0))


@pytest.mark.parametrize(("motores", "esperado"), [
    (pv.ESQUERDO, (255, 0)), (pv.DIREITO, (0, 255)), (pv.AMBOS, (255, 255))])
def test_a_pancada_respeita_o_motor_escolhido(motores: str, esperado: tuple[int, int]) -> None:
    assert pv.sequencia("pancada_do_lado", motores)[0][1:] == esperado
    assert pv.sequencia("pancada_do_lado", motores)[-1][1:] == (0, 0)


def test_padrao_que_vale_segue_a_escolha_e_o_estilo_que_nao_pede_nenhum_fica_mudo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert pv.padrao_que_vale(None, "fps") == "coice"
    assert pv.padrao_que_vale(pv.DO_ESTILO, "retro") is None
    assert pv.padrao_que_vale(None, "corrida") is None
    assert pv.padrao_que_vale(pv.SEM_EFEITO, "fps") is None
    assert pv.padrao_que_vale("onda", "fps") == "onda"
    assert pv.padrao_que_vale("trovao", "retro") is None
    monkeypatch.setitem(pv.POR_ESTILO, "retro", "tranco")
    assert pv.padrao_que_vale(None, "retro") == "tranco"
    assert pv.padrao_que_vale("onda", "retro") == "onda"
    assert pv.padrao_que_vale(pv.SEM_EFEITO, "retro") is None


class Motores:
    """Os dois motores de cada controle: lembra o que o atuador escreveu e quando."""

    def __init__(self) -> None:
        self.relogio = 0.0
        self.escritas: list[tuple[float, str, int, int]] = []

    def __call__(self, uniq: str, fraco: int, forte: int) -> bool:
        self.escritas.append((self.relogio, uniq, fraco, forte))
        return True

    def de(self, uniq: str) -> list[tuple[float, int, int]]:
        return [(t, f, s) for t, u, f, s in self.escritas if u == uniq]


def _montar(
    escolhas: dict[str, str], *, vibra: bool = False, forca: float = 1.0,
) -> tuple[tv.TatoVivo, Motores]:
    motores = Motores()
    atuador = tv.AtuadorDosMotores(
        motores,
        lambda uniq: pv.padrao_que_vale(escolhas.get(uniq), None),
        lambda _uniq: vibra,
        lambda _uniq: forca,
    )
    return tv.TatoVivo([atuador]), motores


def _tiro(uniq: str, t: float, tipo: str = tv.TIPO_DEDO, lado: str = tv.LADO_DIREITO) -> tv.Evento:
    return tv.Evento(t, uniq, tipo, lado, 1.0)


def _correr(
    motor: tv.TatoVivo, motores: Motores, uniqs: tuple[str, ...], ate_s: float,
    estado: tv.EstadoDoCanal = _LIVRE, receita: tv.Receita | None = None, desde_s: float = 0.0,
) -> None:
    """Gira o tique de 60 Hz de ``desde_s`` até ``ate_s``."""
    receita = receita or tv.Receita(padroes_escolhidos=True)
    t = desde_s
    while t <= ate_s + 1e-9:
        motores.relogio = t
        motor.tique(t, lambda _u: estado, receita, uniqs=uniqs)
        t += tv.INTERVALO_S


@pytest.mark.parametrize("forma", ["tranco", "batida", "onda"])
def test_o_padrao_toca_no_tiro_acaba_em_zero_e_cabe_em_2000_ms(forma: str) -> None:
    motor, motores = _montar({AZUL: forma})
    motor.anotar(_tiro(AZUL, 0.0))
    _correr(motor, motores, (AZUL,), 2.5)
    escritas = motores.de(AZUL)
    assert escritas, "o padrão escolhido tinha de tocar no tiro"
    assert escritas[-1][1:] == (0, 0), "o padrão termina em silêncio"
    assert escritas[-1][0] <= 2.0 + tv.INTERVALO_S
    tocados = [(f, s) for _t, f, s in escritas]
    assert tocados[0] == pv.PADROES[forma][0][1:][::-1]
    assert max(max(f, s) for f, s in tocados) <= 255
    tempos = [t for t, _f, _s in escritas]
    assert all(b - a >= 0.06 - tv.INTERVALO_S for a, b in pairwise(tempos))


def test_o_padrao_nao_reinicia_enquanto_toca() -> None:
    motor, motores = _montar({AZUL: "batida"})
    motor.anotar(_tiro(AZUL, 0.0))
    motor.anotar(_tiro(AZUL, 0.0))
    _correr(motor, motores, (AZUL,), 0.1)
    motor.anotar(_tiro(AZUL, 0.1))
    _correr(motor, motores, (AZUL,), 2.0, desde_s=0.11)
    inicios = [e for e in motores.de(AZUL) if (e[1], e[2]) == (255, 255)]
    assert len(inicios) == 1


def test_sem_efeito_e_sem_escolha_nao_tocam_nada() -> None:
    for escolhas in ({AZUL: pv.SEM_EFEITO}, {}):
        motor, motores = _montar(escolhas)
        motor.anotar(_tiro(AZUL, 0.0))
        _correr(motor, motores, (AZUL,), 0.5)
        assert motores.escritas == []


@pytest.mark.parametrize("estado", [_CABO, _RADIO], ids=["cabo", "radio"])
def test_os_quatro_controles_tocam_cada_um_o_seu_pelo_cabo_e_pelo_radio(
    estado: tv.EstadoDoCanal,
) -> None:
    escolhas = {AZUL: "tranco", BRANCO: "batida", VERMELHO: "onda", ROXO: pv.SEM_EFEITO}
    motor, motores = _montar(escolhas)
    for uniq in QUATRO:
        motor.anotar(_tiro(uniq, 0.0))
    _correr(motor, motores, QUATRO, 2.5, estado=estado)
    for uniq, padrao in zip(QUATRO[:3], ("tranco", "batida", "onda"), strict=True):
        tocado = [(f, s) for _t, f, s in motores.de(uniq)]
        assert tocado[0] == pv.PADROES[padrao][0][1:][::-1], uniq
        assert tocado[-1] == (0, 0), uniq
    assert motores.de(ROXO) == []


def test_o_jogo_que_vibra_o_motor_vence_e_o_padrao_cala() -> None:
    """Prova da D-1610-O-PADRAO-DOS-MOTORES-CALA-ONDE-O-JOGO-VIBRA."""
    motor, motores = _montar({AZUL: "tranco"})
    motor.anotar(_tiro(AZUL, 0.0))
    _correr(motor, motores, (AZUL,), 0.5, estado=_JOGO_VIBRA)
    assert motores.escritas == []


def test_o_jogo_que_passa_a_vibrar_no_meio_solta_o_padrao_sem_escrever_por_cima() -> None:
    motor, motores = _montar({AZUL: "onda"})
    motor.anotar(_tiro(AZUL, 0.0))
    _correr(motor, motores, (AZUL,), 0.2)
    antes = len(motores.escritas)
    assert antes >= 1
    _correr(motor, motores, (AZUL,), 2.5, estado=_JOGO_VIBRA, desde_s=0.21)
    assert len(motores.escritas) == antes


@pytest.mark.parametrize("forma", ["tranco", "batida", "onda", "pancada_do_lado"])
def test_com_o_gatilho_vibrando_o_padrao_nao_toca_na_rajada(forma: str) -> None:
    motor, motores = _montar({AZUL: forma}, vibra=True)
    for i in range(10):
        for tipo in (tv.TIPO_DEDO, tv.TIPO_SOM, tv.TIPO_RUMBLE):
            motor.anotar(_tiro(AZUL, i * 0.05, tipo))
    _correr(motor, motores, (AZUL,), 0.6)
    assert motores.escritas == [], "a rajada é do gatilho: o padrão só toca ao soltar"


@pytest.mark.parametrize("forma", ["tranco", "batida", "onda", "coice", "pancada_do_lado"])
def test_com_o_gatilho_vibrando_o_padrao_toca_na_soltura(forma: str) -> None:
    motor, motores = _montar({AZUL: forma}, vibra=True)
    motor.anotar(_tiro(AZUL, 0.0, tv.TIPO_DEDO))
    _correr(motor, motores, (AZUL,), 0.3)
    assert motores.escritas == []
    motor.anotar(_tiro(AZUL, 0.31, tv.TIPO_SOLTA))
    _correr(motor, motores, (AZUL,), 2.5, desde_s=0.31)
    assert motores.de(AZUL)[-1][1:] == (0, 0)
    assert len(motores.de(AZUL)) >= 2


def test_o_ritmo_do_estilo_de_rajada_tambem_segura_o_padrao() -> None:
    motor, motores = _montar({AZUL: "tranco"}, vibra=False)
    receita = tv.Receita(padroes_escolhidos=True, gatilho_no_ritmo=True)
    motor.anotar(_tiro(AZUL, 0.0, tv.TIPO_DEDO))
    _correr(motor, motores, (AZUL,), 0.3, receita=receita)
    assert motores.escritas == []
    motor.anotar(_tiro(AZUL, 0.31, tv.TIPO_SOLTA))
    _correr(motor, motores, (AZUL,), 1.0, receita=receita, desde_s=0.31)
    assert motores.escritas


def test_o_coice_toca_na_soltura_e_nunca_no_aperto() -> None:
    motor, motores = _montar({AZUL: "coice"})
    motor.anotar(_tiro(AZUL, 0.0, tv.TIPO_DEDO))
    motor.anotar(_tiro(AZUL, 0.0, tv.TIPO_RUMBLE))
    _correr(motor, motores, (AZUL,), 0.3)
    assert motores.escritas == []
    motor.anotar(_tiro(AZUL, 0.31, tv.TIPO_SOLTA))
    _correr(motor, motores, (AZUL,), 0.6, desde_s=0.31)
    assert [(f, s) for _t, f, s in motores.de(AZUL)] == [(120, 200), (0, 0)]


def test_o_coice_toca_no_maximo_tres_por_segundo() -> None:
    """Prova da D-1610-O-COICE-E-A-PANCADA-DO-LADO."""
    motor, motores = _montar({AZUL: "coice"})
    for i in range(8):
        motor.anotar(_tiro(AZUL, i * 0.125, tv.TIPO_SOLTA))
        _correr(motor, motores, (AZUL,), i * 0.125 + 0.124, desde_s=i * 0.125)
    inicios = [e for e in motores.de(AZUL) if (e[1], e[2]) == (120, 200)]
    assert len(inicios) == 3
    _correr(motor, motores, (AZUL,), 1.3, desde_s=1.0)
    motor.anotar(_tiro(AZUL, 1.2, tv.TIPO_SOLTA))
    _correr(motor, motores, (AZUL,), 1.5, desde_s=1.2)
    assert len([e for e in motores.de(AZUL) if (e[1], e[2]) == (120, 200)]) == 4


@pytest.mark.parametrize(("lado", "esperado"), [
    (tv.LADO_ESQUERDO, (0, 255)),
    (tv.LADO_DIREITO, (255, 0)),
    (tv.LADO_CENTRO, (255, 255)),
])
def test_a_pancada_do_lado_bate_no_motor_do_lado_do_som(
    lado: str, esperado: tuple[int, int],
) -> None:
    motor, motores = _montar({AZUL: "pancada_do_lado"})
    motor.anotar(_tiro(AZUL, 0.0, tv.TIPO_SOM, lado))
    _correr(motor, motores, (AZUL,), 0.5)
    tocado = [(f, s) for _t, f, s in motores.de(AZUL)]
    assert tocado[0] == esperado
    assert tocado[-1] == (0, 0)


def test_a_pancada_do_lado_nao_responde_ao_dedo_nem_ao_rumble() -> None:
    motor, motores = _montar({AZUL: "pancada_do_lado"})
    motor.anotar(_tiro(AZUL, 0.0, tv.TIPO_DEDO))
    motor.anotar(_tiro(AZUL, 0.0, tv.TIPO_RUMBLE))
    _correr(motor, motores, (AZUL,), 0.5)
    assert motores.escritas == []


@pytest.mark.parametrize(("forca", "esperado"), [(1.0, 255), (0.6, 153), (0.35, 89)])
def test_o_degrau_de_forca_multiplica_o_padrao(forca: float, esperado: int) -> None:
    motor, motores = _montar({AZUL: "tranco"}, forca=forca)
    motor.anotar(_tiro(AZUL, 0.0))
    _correr(motor, motores, (AZUL,), 0.3)
    assert motores.de(AZUL)[0][1:] == (esperado, esperado)


def _daemon(controller: Any) -> Any:
    return SimpleNamespace(controller=controller, store=SimpleNamespace(active_profile="x"))


class _Controller:
    def __init__(self) -> None:
        self.rumble: list[tuple[str, int, int]] = []

    def set_rumble_for(self, uniq: str, weak: int, strong: int) -> bool:
        self.rumble.append((uniq, weak, strong))
        return True


def _o_atuador_de_producao(
    monkeypatch: pytest.MonkeyPatch, estilo: str | None, economia: bool,
    escolha: str = "tranco",
) -> tuple[tv.AtuadorDosMotores, _Controller, tv.TatoVivo]:
    monkeypatch.setattr(tv, "_controle_na_economia", lambda _u: economia)
    monkeypatch.setattr(tv, "estilo_ativo", lambda _d: estilo)
    controller = _Controller()
    daemon = _daemon(controller)
    atuador = next(
        a for a in tv.atuadores_de_producao(daemon) if isinstance(a, tv.AtuadorDosMotores))
    motor = tv.TatoVivo([atuador])
    daemon._tato_vivo = motor
    motor.escolhas_de_imersao = {norm_mac(AZUL): escolha}
    return atuador, controller, motor


@pytest.mark.parametrize(("estilo", "economia", "esperado"), [
    (None, False, 255), ("fps", False, 255), ("corrida", False, 153), ("simulacao", False, 89),
    ("fps", True, 89), ("corrida", True, 89),
])
def test_na_producao_a_forca_vem_do_estilo_e_a_bateria_longa_vale_035(
    monkeypatch: pytest.MonkeyPatch, estilo: str | None, economia: bool, esperado: int,
) -> None:
    _atuador, controller, motor = _o_atuador_de_producao(monkeypatch, estilo, economia)
    motor.anotar(_tiro(AZUL, 0.0))
    motor.tique(0.0, lambda _u: _LIVRE, tv.Receita(padroes_escolhidos=True), uniqs=(AZUL,))
    assert controller.rumble[0] == (AZUL, esperado, esperado)


def test_na_producao_o_padrao_para_no_motor_parado(monkeypatch: pytest.MonkeyPatch) -> None:
    _atuador, controller, motor = _o_atuador_de_producao(monkeypatch, None, False, "onda")
    motor.anotar(_tiro(AZUL, 0.0))
    motor.tique(0.0, lambda _u: _LIVRE, tv.Receita(padroes_escolhidos=True), uniqs=(AZUL,))
    assert controller.rumble and controller.rumble[-1][1:] != (0, 0)
    motor.parar(0.1)
    assert controller.rumble[-1] == (AZUL, 0, 0)


def test_na_producao_o_gatilho_que_vibra_segura_o_padrao(monkeypatch: pytest.MonkeyPatch) -> None:
    _atuador, controller, motor = _o_atuador_de_producao(monkeypatch, "fps", False)
    motor.vibra_o_gatilho = tv.VibracaoDoGatilho(geral=True)
    motor.anotar(_tiro(AZUL, 0.0))
    motor.tique(0.0, lambda _u: _LIVRE, tv.Receita(padroes_escolhidos=True), uniqs=(AZUL,))
    assert controller.rumble == []
    motor.anotar(_tiro(AZUL, 0.1, tv.TIPO_SOLTA))
    motor.tique(0.1, lambda _u: _LIVRE, tv.Receita(padroes_escolhidos=True), uniqs=(AZUL,))
    assert controller.rumble


@pytest.mark.parametrize(("barras", "esperado"), [
    ((100, 100), (255, 255)), ((50, 100), (255, 128)), ((100, 0), (0, 255)), ((0, 0), (0, 0)),
])
def test_na_producao_o_padrao_passa_pelas_barras_de_cada_motor(
    monkeypatch: pytest.MonkeyPatch, barras: tuple[int, int], esperado: tuple[int, int],
) -> None:
    """A barra Motor esquerdo (o forte) e a direito (o fraco) valem no padrão, como no Testar.

    MORDIDA: a escrita de produção sem `_barras_dos_motores` toca 255 com a barra em zero.
    """
    from hefesto_dualsense4unix.daemon.subsystems import gamepad

    monkeypatch.setattr(gamepad, "_pcts_dos_motores", lambda _d, _u: barras)
    _atuador, controller, motor = _o_atuador_de_producao(monkeypatch, None, False)
    motor.anotar(_tiro(AZUL, 0.0))
    motor.tique(0.0, lambda _u: _LIVRE, tv.Receita(padroes_escolhidos=True), uniqs=(AZUL,))
    assert controller.rumble[0] == (AZUL, *esperado)


def test_no_modo_xbox_o_rumble_do_jogo_pelo_pad_uinput_cala_o_padrao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O pad ``uinput`` não tem ``visto_ha_s``: o rumble anotado é o que diz que o jogo vibra.

    MORDIDA: sem `com_o_rumble_anotado` no passo, o padrão toca por cima do jogo no modo Xbox.
    """
    motor, motores = _montar({AZUL: "tranco"})
    motor.ligado = True
    controle = tv.Controle(uniq=AZUL, vpad=SimpleNamespace(backend="uinput"))
    daemon = SimpleNamespace(_tato_vivo=motor)
    passo = tv.Passo(daemon, motor)
    receita = tv.Receita(padroes_escolhidos=True)
    monkeypatch.setattr(passo, "receita_de_agora", lambda _agora: receita)
    monkeypatch.setattr(tv, "controles_do_daemon", lambda _d: [controle])
    monkeypatch.setattr(tv, "ha_jogo", lambda _d: True)
    monkeypatch.setattr(tv, "modo_do_pad", lambda _p: tv.MODO_XBOX)
    tv.anotar_o_rumble(daemon, AZUL.upper(), 0, 200, agora=1.0)
    motor.anotar(_tiro(AZUL, 1.1))
    passo(1.1)
    assert motores.escritas == []
    depois = 1.0 + tv.JANELA_DO_JOGO_S + 0.5
    motor.anotar(_tiro(AZUL, depois))
    passo(depois)
    assert motores.escritas


def test_o_rumble_anotado_vale_a_idade_menor_entre_o_pad_e_o_motor() -> None:
    uhid = tv.EstadoDoCanal(modo=tv.MODO_DUALSENSE, ha_jogo=True, visto_ha_s={"rumble": 0.4})
    assert tv.com_o_rumble_anotado(uhid, None, 10.0) is uhid
    assert tv.com_o_rumble_anotado(uhid, 9.0, 10.0).visto_ha_s["rumble"] == 0.4
    assert tv.com_o_rumble_anotado(uhid, 9.9, 10.0).visto_ha_s["rumble"] == 0.1
    sem = tv.EstadoDoCanal(modo=tv.MODO_XBOX, ha_jogo=True)
    assert not tv.decidir(tv.CANAL_MOTORES, tv.com_o_rumble_anotado(sem, 9.0, 10.0))
    assert tv.decidir(tv.CANAL_MOTORES, tv.com_o_rumble_anotado(sem, 6.0, 10.0))


def test_a_borda_do_dedo_anota_a_soltura_com_o_pico_sem_mudar_o_que_ver_devolve() -> None:
    borda = tv.BordaDoDedo()
    assert [e.tipo for e in borda.ver(AZUL, 0, 255, 0.0)] == [tv.TIPO_DEDO]
    assert borda.ver(AZUL, 0, 200, 0.1) == []
    assert borda.ver(AZUL, 0, 60, 0.2) == []
    (solta,) = borda.tirar_as_soltas()
    assert (solta.tipo, solta.lado, solta.uniq, solta.instante) == (
        tv.TIPO_SOLTA, tv.LADO_DIREITO, AZUL, 0.2)
    assert solta.energia == pytest.approx(1.0)
    assert borda.tirar_as_soltas() == []


def test_a_soltura_leva_o_pico_do_aperto() -> None:
    borda = tv.BordaDoDedo()
    borda.ver(AZUL, 170, 0, 0.0)
    borda.ver(AZUL, 120, 0, 0.1)
    borda.ver(AZUL, 0, 0, 0.2)
    (solta,) = borda.tirar_as_soltas()
    assert solta.lado == tv.LADO_ESQUERDO
    assert solta.energia == pytest.approx(170 / 255)


def test_o_passo_leva_a_soltura_ao_motor() -> None:
    motor = tv.TatoVivo([])
    passo = tv.Passo(SimpleNamespace(), motor)
    passo.dedo.ver(AZUL, 0, 255, 0.0)
    passo.dedo.ver(AZUL, 0, 0, 0.1)
    for solta in passo.dedo.tirar_as_soltas():
        motor.anotar(solta)
    assert motor.contadores["eventos"] == 1


def test_o_campo_do_perfil_so_aceita_padrao_conhecido() -> None:
    assert ControllerRumbleOverride(efeito_imersao="coice").efeito_imersao == "coice"
    assert ControllerRumbleOverride(efeito_imersao="do_estilo").efeito_imersao == "do_estilo"
    assert ControllerRumbleOverride(efeito_imersao="ronco").efeito_imersao is None
    assert ControllerRumbleOverride().efeito_imersao is None


def test_quem_nao_escolheu_nada_nao_grava_os_campos() -> None:
    gravado = ControllerRumbleOverride().model_dump()
    assert "efeito_imersao" not in gravado and "efeito_haptico" not in gravado
    assert ControllerRumbleOverride(efeito_imersao="onda").model_dump()["efeito_imersao"] == "onda"
    volta = ControllerRumbleOverride.model_validate(
        ControllerRumbleOverride(efeito_imersao="onda").model_dump())
    assert volta.efeito_imersao == "onda"


def _perfil(**por_controle: str) -> dict[str, Any]:
    return {"controllers": {u: {"rumble": {"efeito_imersao": e}} for u, e in por_controle.items()}}


def test_a_receita_liga_pelo_padrao_escolhido_e_a_pancada_sobe_o_ouvido() -> None:
    onda = tv.receita_do_perfil(_perfil(**{AZUL: "onda"}))
    assert onda.padroes_escolhidos and not onda.pancada_escolhida and onda.ligada
    pancada = tv.receita_do_perfil(_perfil(**{AZUL: "pancada_do_lado"}))
    assert pancada.padroes_escolhidos and pancada.pancada_escolhida


@pytest.mark.parametrize("escolha", [pv.DO_ESTILO, pv.SEM_EFEITO, "ronco"])
def test_do_estilo_sem_efeito_e_ilegivel_nao_ligam_o_motor(escolha: str) -> None:
    receita = tv.receita_do_perfil(_perfil(**{AZUL: escolha}))
    assert not receita.padroes_escolhidos and not receita.ligada


def test_os_padroes_do_perfil_saem_por_mac_normalizado() -> None:
    padroes = tv.padroes_do_perfil(_perfil(**{"AA:BB:CC:00:00:11": "coice", BRANCO: "do_estilo"}))
    assert padroes == {norm_mac(AZUL): "coice"}


def _gatilhos(esq: str, dir_: str, modo: str = "personalizado") -> dict[str, Any]:
    return {
        "triggers": {
            "modo": modo,
            "left": {"mode": esq, "params": []},
            "right": {"mode": dir_, "params": []},
        },
    }


def test_o_gatilho_do_perfil_vibra_quando_algum_lado_esta_em_modo_de_vibracao() -> None:
    assert tv.vibracao_do_gatilho_do_perfil(_gatilhos("Rigid", "Machine")).de(AZUL)
    assert tv.vibracao_do_gatilho_do_perfil(_gatilhos("Vibration", "Rigid")).de(AZUL)
    assert tv.vibracao_do_gatilho_do_perfil(_gatilhos("MultiPositionVibration", "Off")).de(AZUL)
    assert not tv.vibracao_do_gatilho_do_perfil(_gatilhos("Weapon", "Bow")).de(AZUL)
    assert not tv.vibracao_do_gatilho_do_perfil({}).de(AZUL)


def test_o_gatilho_de_um_controle_escrito_por_cima_vale_so_para_ele() -> None:
    perfil = _gatilhos("Weapon", "Bow")
    perfil["controllers"] = {
        BRANCO: {"triggers": {"right": {"mode": "Machine", "params": []}}}}
    vibra = tv.vibracao_do_gatilho_do_perfil(perfil)
    assert vibra.de(BRANCO) and not vibra.de(AZUL)
    perfil2 = _gatilhos("Machine", "Bow")
    perfil2["controllers"] = {
        BRANCO: {"triggers": {"left": {"mode": "Weapon", "params": []}}}}
    vibra2 = tv.vibracao_do_gatilho_do_perfil(perfil2)
    assert vibra2.de(AZUL) and not vibra2.de(BRANCO)


def test_no_automatico_vale_o_acionamento_do_estilo() -> None:
    fps = {**_gatilhos("Weapon", "Weapon", MODO_AUTO), "estilo": "fps"}
    acao = {**_gatilhos("Machine", "Machine", MODO_AUTO), "estilo": ESTILO_ACAO}
    assert tv.vibracao_do_gatilho_do_perfil(fps).de(AZUL)
    assert not tv.vibracao_do_gatilho_do_perfil(acao).de(AZUL)


def test_o_passo_rele_o_padrao_e_o_gatilho_junto_da_receita(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    motor = tv.TatoVivo([])
    passo = tv.Passo(SimpleNamespace(), motor)
    monkeypatch.setattr(tv, "receita_ativa", lambda _d: tv.Receita(padroes_escolhidos=True))
    monkeypatch.setattr(tv, "momentos_ativos", lambda _d: tv.SEM_MOMENTOS)
    monkeypatch.setattr(tv, "escolhas_ativas", lambda _d: {})
    monkeypatch.setattr(tv, "escolhas_de_imersao_ativas", lambda _d: {"x": "onda"})
    monkeypatch.setattr(
        tv, "vibracao_do_gatilho_ativa", lambda _d: tv.VibracaoDoGatilho(geral=True))
    passo.receita_de_agora(0.0)
    assert motor.escolhas_de_imersao == {"x": "onda"}
    assert motor.vibra_o_gatilho.de(AZUL)
