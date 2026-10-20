"""O efeito háptico ganha as formas (O-EFEITO-HAPTICO-GANHA-AS-FORMAS-...-01).

Cada forma tem a frequência, a duração e o ataque que a sprint pede; nenhuma passa do teto que o
pedido deu nem termina fora de zero; a Bateria longa troca as longas pelo Toque; e a escolha do
controle (``rumble.efeito_haptico``) manda na forma, sem tirar o Toque de hoje de quem não
escolheu. Tudo com dublês: o tocador é uma lista e o relógio é injetado.
"""
from __future__ import annotations

import math
from array import array
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from hefesto_dualsense4unix.profiles import formas_de_haptica as fh
from hefesto_dualsense4unix.profiles.schema import ControllerRumbleOverride

P1 = "aa:bb:cc:00:00:11"
P2 = "aa:bb:cc:00:00:12"
_XBOX = tv.EstadoDoCanal(modo=tv.MODO_XBOX, ha_jogo=True)


def _potencia(amostras: Any, hz: float, taxa: int = fh.TAXA) -> float:
    """A potência da amostra na frequência ``hz`` (Goertzel)."""
    w = 2.0 * math.pi * hz / taxa
    coef = 2.0 * math.cos(w)
    s1 = s2 = 0.0
    for x in amostras:
        s0 = x + coef * s1 - s2
        s2, s1 = s1, s0
    return s1 * s1 + s2 * s2 - coef * s1 * s2


# --- A conta de cada forma --------------------------------------------------------------


@pytest.mark.parametrize(
    ("chave", "ms", "componentes", "ataque_ms"),
    [
        (fh.TOQUE, 40, (160,), 3),
        (fh.IMPACTO, 80, (60, 160), 2),
        (fh.ESTALO, 15, (250,), 1),
        (fh.GUARDA, 850, (115, 220), 3),
        (fh.APARO, 600, (170, 270), 3),
    ],
)
def test_cada_forma_tem_a_frequencia_a_duracao_e_o_ataque_da_sprint(
    chave: str, ms: int, componentes: tuple[int, ...], ataque_ms: int
) -> None:
    onda = fh.amostras(chave, 1.0, 40)
    assert len(onda) == round(fh.TAXA * ms / 1000)
    # o ataque sobe de zero e o pico vem logo: depois de ataque + 3 períodos da menor componente
    # a onda não cresce mais
    janela = round(fh.TAXA * (ataque_ms / 1000 + 3 / min(componentes)))
    assert max(abs(x) for x in onda[:janela]) >= 0.9 * max(abs(x) for x in onda)
    assert max(abs(x) for x in onda[: round(fh.TAXA * ataque_ms / 3000)]) < 0.5 * max(
        abs(x) for x in onda)
    cheio = sorted(_potencia(onda, hz) for hz in range(40, 400, 5))
    for hz in componentes:
        assert _potencia(onda, hz) > cheio[-12], f"{chave}: sem energia em {hz} Hz"


def test_o_estalo_toca_a_250_hz_e_nao_a_160() -> None:
    onda = fh.amostras(fh.ESTALO, 1.0)
    assert _potencia(onda, 250) > 4 * _potencia(onda, 160)


@pytest.mark.parametrize("chave", list(fh.FORMAS))
@pytest.mark.parametrize("energia", [0.2, 0.6, 1.0])
def test_nenhuma_forma_passa_do_teto_e_todas_terminam_em_zero(chave: str, energia: float) -> None:
    onda = fh.amostras(chave, energia, 40)
    assert max(abs(x) for x in onda) <= energia + 1e-6
    assert onda[0] == 0.0
    assert abs(onda[-1]) < 1e-6


def test_a_energia_fora_da_faixa_e_trazida_para_ela() -> None:
    assert max(abs(x) for x in fh.amostras(fh.IMPACTO, 7.0)) <= 1.0 + 1e-6
    assert max(abs(x) for x in fh.amostras(fh.IMPACTO, -1.0)) == 0.0


def test_forma_desconhecida_recusa_dizendo_as_que_existem() -> None:
    with pytest.raises(ValueError, match="toque"):
        fh.amostras("trovao", 1.0)


def test_o_toque_de_hoje_nao_mudou() -> None:
    antigo = eh.forma_do_toque(0.8, 40)
    assert list(antigo) == list(fh.amostras(fh.TOQUE, 0.8, 40))
    assert len(antigo) == round(fh.TAXA * 0.040)
    assert abs(antigo[-1]) < 1e-6 and max(abs(x) for x in antigo) <= 0.8 + 1e-6
    assert list(eh.forma_do_toque(0.8, 40, fh.GUARDA)) == list(fh.amostras(fh.GUARDA, 0.8, 40))


def test_a_conta_dos_senos_nao_se_refaz_a_cada_tiro(monkeypatch: pytest.MonkeyPatch) -> None:
    """O toque sai no laço do tato, no fio do daemon; refazer a Guarda custava ~20 ms."""
    primeira = fh.amostras(fh.GUARDA, 1.0)
    contados = {"sin": 0}
    seno = math.sin

    def contar(x: float) -> float:
        contados["sin"] += 1
        return seno(x)

    monkeypatch.setattr(fh.math, "sin", contar)
    segunda = fh.amostras(fh.GUARDA, 0.5)
    assert contados["sin"] == 0, "a Guarda refez os senos num tiro que só mudou a força"
    assert all(abs(b - 0.5 * a) < 1e-6 for a, b in zip(primeira, segunda, strict=True))


def test_o_toque_que_cai_atras_da_guarda_nem_faz_a_conta(monkeypatch: pytest.MonkeyPatch) -> None:
    tocador = eh.TocadorDoRumble(
        "x", argv_de=lambda _s, _r: [], conferir=lambda _r: None, folga_s=0.05
    )
    try:
        tocador.tocar_o_toque(1.0, tv.LADO_CENTRO, 40, sink="", dono="p1", forma=fh.GUARDA)

        def proibida(*_a: Any, **_k: Any) -> Any:
            raise AssertionError("o toque que cai atrás da Guarda fez a conta das amostras")

        monkeypatch.setattr(eh, "forma_do_toque", proibida)
        tocador.tocar_o_toque(1.0, tv.LADO_CENTRO, 40, sink="", dono="p1", forma=fh.IMPACTO)
        assert tocador.tocando_o_toque
    finally:
        tocador.parar()


# --- A Bateria longa e o estilo ---------------------------------------------------------


def test_a_bateria_longa_troca_as_longas_por_toque_e_cala_o_som_no_corpo() -> None:
    # D-1610-A-BATERIA-LONGA-ENCURTA-AS-FORMAS-DO-TOQUE
    assert fh.forma_que_vale(fh.GUARDA, None, economia=True) == fh.TOQUE
    assert fh.forma_que_vale(fh.APARO, None, economia=True) == fh.TOQUE
    assert fh.forma_que_vale(fh.SOM_NO_CORPO, None, economia=True) is None
    for curta in (fh.TOQUE, fh.IMPACTO, fh.ESTALO):
        assert fh.forma_que_vale(curta, None, economia=True) == curta
    assert fh.forma_que_vale(fh.GUARDA, None, economia=False) == fh.GUARDA


def test_sem_escolha_vale_o_estilo_e_o_toque_quando_ele_nao_pede(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert fh.forma_que_vale(None, "fps") == fh.TOQUE
    assert fh.forma_que_vale(fh.DO_ESTILO, "fps") == fh.TOQUE
    monkeypatch.setitem(fh.POR_ESTILO, "fps", fh.IMPACTO)
    assert fh.forma_que_vale(None, "fps") == fh.IMPACTO
    assert fh.forma_que_vale(fh.ESTALO, "fps") == fh.ESTALO  # a escolha vence o estilo
    assert fh.forma_que_vale(fh.SEM_EFEITO, "fps") is None


def test_o_continuo_so_e_forma_do_estilo_onde_o_corpo_e_o_motor() -> None:
    # D-2010-O-CONTINUO-VOLTA-A-CORRIDA-E-A-SIMULACAO: revoga a de 16/10 (CATALOGO, 3)
    donos = {e for e, f in fh.POR_ESTILO.items() if f == fh.SOM_NO_CORPO}
    assert donos == {"corrida", "simulacao"}
    assert fh.SOM_NO_CORPO not in fh.FORMAS


# --- O atuador: a escolha por controle ---------------------------------------------------


class Toques:
    def __init__(self) -> None:
        self.feitos: list[tuple[Any, ...]] = []

    def __call__(self, *args: Any) -> bool:
        self.feitos.append(args)
        return True


def _tiro(uniq: str, instante: float = 0.0) -> tv.Evento:
    return tv.Evento(instante, uniq, tv.TIPO_RUMBLE, tv.LADO_ESQUERDO, 1.0)


def _tocar(
    escolhas: dict[str, str], receita: tv.Receita, *uniqs: str, economia: bool = False,
    estilo: str | None = None,
) -> Toques:
    toques = Toques()
    motor = tv.TatoVivo([tv.AtuadorDaHaptica(
        toques, None, escolhas.get, lambda: estilo, lambda _u: economia)])
    for i, uniq in enumerate(uniqs):
        motor.anotar(_tiro(uniq, i * 0.2))
    motor.tique(1.0, lambda _u: _XBOX, receita)
    return toques


def test_sem_escolha_o_toque_e_o_de_hoje_com_quatro_argumentos() -> None:
    toques = _tocar({}, tv.Receita(vibracao_por_tiro=True), P1)
    assert [t[0] for t in toques.feitos] == [P1]
    assert len(toques.feitos[0]) == 4  # a chamada de sempre: ninguém precisa saber de forma


def test_a_forma_escolhida_chega_ao_tocador_de_quem_escolheu() -> None:
    toques = _tocar({P1: fh.IMPACTO}, tv.Receita(vibracao_por_tiro=True), P1, P2)
    formas = {t[0]: (t[4] if len(t) > 4 else fh.TOQUE) for t in toques.feitos}
    assert formas == {P1: fh.IMPACTO, P2: fh.TOQUE}


def test_a_escolha_dispara_mesmo_quando_o_estilo_nao_pede_toque() -> None:
    assert not tv.Receita().ligada  # sem a escolha o motor nem liga
    assert tv.Receita(efeitos_escolhidos=True).ligada
    com = _tocar({P1: fh.ESTALO}, tv.Receita(efeitos_escolhidos=True), P1, P2)
    assert [t[0] for t in com.feitos] == [P1]  # P2 não escolheu e o estilo não pede


def test_sem_efeito_cala_so_o_controle_que_escolheu() -> None:
    toques = _tocar({P1: fh.SEM_EFEITO}, tv.Receita(vibracao_por_tiro=True), P1, P2)
    assert [t[0] for t in toques.feitos] == [P2]


def test_na_bateria_longa_a_guarda_toca_como_toque() -> None:
    toques = _tocar({P1: fh.GUARDA}, tv.Receita(efeitos_escolhidos=True), P1, economia=True)
    assert len(toques.feitos[0]) == 4  # Toque: sem o argumento da forma
    longa = _tocar({P1: fh.GUARDA}, tv.Receita(efeitos_escolhidos=True), P1, economia=False)
    assert longa.feitos[0][4] == fh.GUARDA


def test_o_som_no_corpo_nao_responde_a_tiro() -> None:
    toques = _tocar({P1: fh.SOM_NO_CORPO}, tv.Receita(vibracao_por_tiro=True), P1)
    assert toques.feitos == []


def test_o_estilo_pede_a_forma_quando_ninguem_escolheu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(fh.POR_ESTILO, "fps", fh.ESTALO)
    toques = _tocar({}, tv.Receita(vibracao_por_tiro=True), P1, estilo="fps")
    assert toques.feitos[0][4] == fh.ESTALO


# --- O perfil: o campo, a receita e o disco ----------------------------------------------


def test_o_campo_do_perfil_so_aceita_forma_conhecida() -> None:
    assert ControllerRumbleOverride(efeito_haptico="guarda").efeito_haptico == "guarda"
    assert ControllerRumbleOverride(efeito_haptico="do_estilo").efeito_haptico == "do_estilo"
    assert ControllerRumbleOverride(efeito_haptico="trovao").efeito_haptico is None
    assert ControllerRumbleOverride().efeito_haptico is None


def test_quem_nao_escolheu_nada_nao_grava_o_campo() -> None:
    assert "efeito_haptico" not in ControllerRumbleOverride().model_dump()
    assert "efeito_haptico" not in ControllerRumbleOverride(efeito_haptico="x").model_dump()
    gravado = ControllerRumbleOverride(efeito_haptico="aparo").model_dump()
    assert gravado["efeito_haptico"] == "aparo"
    volta = ControllerRumbleOverride.model_validate(
        ControllerRumbleOverride(efeito_haptico="aparo").model_dump())
    assert volta.efeito_haptico == "aparo"


def _perfil(**por_controle: str) -> dict[str, Any]:
    return {"controllers": {u: {"rumble": {"efeito_haptico": e}} for u, e in por_controle.items()}}


def test_a_receita_liga_pela_escolha_de_forma_e_pelo_som_no_corpo() -> None:
    forma = tv.receita_do_perfil(_perfil(**{P1: fh.IMPACTO}))
    assert forma.efeitos_escolhidos and not forma.som_no_corpo_escolhido and forma.ligada
    corpo = tv.receita_do_perfil(_perfil(**{P1: fh.SOM_NO_CORPO}))
    assert corpo.som_no_corpo_escolhido and not corpo.efeitos_escolhidos and corpo.ligada


@pytest.mark.parametrize("escolha", [fh.DO_ESTILO, fh.SEM_EFEITO, "trovao"])
def test_do_estilo_sem_efeito_e_ilegivel_nao_ligam_o_motor(escolha: str) -> None:
    receita = tv.receita_do_perfil(_perfil(**{P1: escolha}))
    assert not receita.efeitos_escolhidos and not receita.ligada


def test_as_escolhas_do_perfil_saem_por_mac_normalizado() -> None:
    escolhas = tv.escolhas_do_perfil(_perfil(**{"AA:BB:CC:00:00:11": fh.APARO, P2: fh.DO_ESTILO}))
    assert escolhas == {norm_mac(P1): fh.APARO}


# --- O Som no corpo -----------------------------------------------------------------------


def _pcm(hz: float, quadros: int = 9600, amplitude: float = 0.5, inicio: int = 0) -> bytes:
    saida = array("h")
    for i in range(inicio, inicio + quadros):
        v = int(32767 * amplitude * math.sin(2.0 * math.pi * hz * i / fh.TAXA))
        saida.extend((v, v))
    return saida.tobytes()


def _rms(amostras: Any) -> float:
    return math.sqrt(sum(x * x for x in amostras) / max(1, len(amostras)))


def test_o_filtro_deixa_passar_o_grave_e_barra_o_agudo_e_o_infragrave() -> None:
    def medir(hz: float) -> float:
        filtro = fh.FiltroDoCorpo()
        filtro.processar(_pcm(hz, 4800))  # o regime, depois da partida do filtro
        return _rms(filtro.processar(_pcm(hz, 9600, inicio=4800)))

    grave = medir(100)
    assert grave > 0.1
    assert medir(2000) < grave * 0.05
    assert medir(10) < grave * 0.2


def test_o_corpo_nunca_passa_do_teto() -> None:
    saida = fh.FiltroDoCorpo().processar(_pcm(100, 9600, amplitude=1.0))
    assert max(abs(x) for x in saida) <= fh.TETO_DO_CORPO + 1e-9


def test_meio_quadro_solto_no_fim_do_pedaco_e_descartado() -> None:
    assert len(fh.FiltroDoCorpo().processar(_pcm(100, 100) + b"\x01\x02")) == 100


class _AltoFalante:
    def __init__(self) -> None:
        self.corpo: list[str] = []

    def tocar_o_corpo(self, uniq: str, amostras: Any) -> bool:
        self.corpo.append(uniq)
        return True


def _passo(escolhas: dict[str, str]) -> tuple[tv.Passo, _AltoFalante]:
    alto = _AltoFalante()
    motor = tv.TatoVivo([])
    motor.escolhas = {norm_mac(u): e for u, e in escolhas.items()}
    passo = tv.Passo(SimpleNamespace(_alto_falante_subsystem=alto), motor)
    passo.receita_vigente = tv.Receita(som_no_corpo_escolhido=True)
    return passo, alto


def _levar(passo: tv.Passo, estado: tv.EstadoDoCanal = _XBOX) -> None:
    passo.alimentar_o_corpo(_pcm(100, 960))
    passo._levar_o_corpo(passo.receita_vigente, (P1, P2), lambda _u: estado)


def test_o_corpo_vai_so_a_quem_escolheu() -> None:
    passo, alto = _passo({P1: fh.SOM_NO_CORPO, P2: fh.IMPACTO})
    _levar(passo)
    assert alto.corpo == [P1]


def test_o_corpo_cala_quando_o_jogo_escreve_a_haptica() -> None:
    passo, alto = _passo({P1: fh.SOM_NO_CORPO})
    jogo = tv.EstadoDoCanal(
        modo=tv.MODO_DUALSENSE, visto_ha_s={"audio_do_jogo": 0.2}, sessao_aberta=True,
        ha_jogo=True)
    _levar(passo, jogo)
    assert alto.corpo == []


def test_o_corpo_cala_na_bateria_longa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tv, "_controle_na_economia", lambda _u: True)
    passo, alto = _passo({P1: fh.SOM_NO_CORPO})
    _levar(passo)
    assert alto.corpo == []


def test_sem_ninguem_que_escolheu_o_filtro_nem_roda() -> None:
    passo, alto = _passo({})
    passo.receita_vigente = tv.Receita()
    passo.alimentar_o_corpo(_pcm(100, 960))
    assert not passo._corpo
    assert alto.corpo == []
