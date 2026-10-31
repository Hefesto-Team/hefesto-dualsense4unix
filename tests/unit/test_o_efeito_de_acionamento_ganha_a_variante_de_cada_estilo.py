"""O-EFEITO-DE-ACIONAMENTO-GANHA-A-VARIANTE-DE-CADA-ESTILO-01: o ritmo do tiro é do lado da arma.

**A causa, medida em 31/10/2026** (o motor do tato com o atuador do gatilho, relógio injetado):
os estilos de rajada eram só o FPS; dez apertos do L2 a 70 ms escreviam 2 blocos no L2 (o ponto
duro da mira trocado pela arma), e o primeiro tiro do R2 escrevia ``2548000400000000000000``, a
arma semi-automática de fábrica, no FPS, na Ação e no Terror, por cima do R2 do estilo.

**A cura:** a Ação e o Terror entram nos estilos de rajada; o ritmo escreve só no lado em que o
perfil põe uma arma (Disparo ou Metralhadora) naquele controle, e a arma sai com os números
dele: no automático, os do estilo; no personalizado, os que a aba escreveu, e o lado que a aba
tirou da arma o ritmo não toca. O rumble no dedo cede só esse lado.

Sem aparelho: o backend anota os blocos. Endereços da faixa forjada ``aa:bb:cc``.
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import trigger_specs as specs
from hefesto_dualsense4unix.core.trigger_effects import build_from_name, traduzir_chave_velha
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.interface.pacotes import a10_perfis
from hefesto_dualsense4unix.profiles.estilos_de_jogo import ESTILOS, POR_CHAVE
from hefesto_dualsense4unix.profiles.schema import MODO_AUTOMATICO, MatchAny, Profile

DIREITO, ESQUERDO = tv.LADO_DIREITO, tv.LADO_ESQUERDO
QUATRO = ("aa:bb:cc:00:00:41", "aa:bb:cc:00:00:42", "aa:bb:cc:00:00:43", "aa:bb:cc:00:00:44")
P1 = QUATRO[0]
_ACAO = "acao"  # (noqa-acento)
DE_RAJADA = ("fps", _ACAO, "terror")
TIQUE_S = 1.0 / 60.0


def _automatico(estilo: str) -> Profile:
    return Profile(name="Ritmo", match=MatchAny(), estilo=estilo,
                   triggers={"modo": MODO_AUTOMATICO})


def _armas(estilo: str) -> tv.ArmasDoGatilho:
    return tv.armas_do_gatilho_do_perfil(_automatico(estilo))


def _xbox(_uniq: str) -> tv.EstadoDoCanal:
    return tv.EstadoDoCanal(modo=tv.MODO_XBOX, ha_jogo=True)


def _receita(estilo: str) -> tv.Receita:
    return tv.receita_do_estilo(POR_CHAVE[estilo])


def _do_perfil(estilo: str, lado: str) -> bytes:
    """O bloco que o perfil do estilo põe no lado, pelo caminho da aba Perfis."""
    dele = POR_CHAVE[estilo]
    invisivel = dele.receita_invisivel
    ajustes = dict(invisivel.ajustes_do_gatilho) if invisivel else {}
    config = a10_perfis._gatilho_do_lado(
        specs, dele, dele.r2 if lado == DIREITO else dele.l2, ajustes)
    efeito = build_from_name(config.mode, list(config.params))
    f = efeito.forces
    return bytes([efeito.mode, f[0], f[1], f[2], f[3], f[4], f[5], 0, 0, f[6], 0])


class _Mesa:
    def __init__(
        self, estilos: dict[str, str] | None = None, apertado: Any = None,
        armas: tv.ArmasDoGatilho | None = None,
    ) -> None:
        self.blocos: list[tuple[str, str, bytes]] = []
        de_cada = {uniq: _armas(estilo) for uniq, estilo in (estilos or {}).items()}

        def arma_de(uniq: str, lado: str) -> bytes | None:
            dele = de_cada.get(uniq, armas or tv.SEM_ARMAS)
            return dele.de(uniq, lado)

        self.atuador = tv.AtuadorDoGatilho(
            lambda u, lado, bloco: self.blocos.append((u, lado, bytes(bloco))),
            lambda _u: True,
            apertado,
            arma_de=arma_de,
        )
        self.motor = tv.TatoVivo([self.atuador])

    def atirar(
        self, uniq: str, lado: str, instantes: list[float], receita: tv.Receita,
        estado_de: Any = _xbox,
    ) -> None:
        for t in instantes:
            self.motor.anotar(tv.Evento(t, uniq, tv.TIPO_DEDO, lado))
            self.motor.tique(t + 0.001, estado_de, receita)

    def de(self, uniq: str, lado: str | None = None) -> list[bytes]:
        disco = None if lado is None else {DIREITO: "right", ESQUERDO: "left"}[lado]
        return [b for u, d, b in self.blocos if u == uniq and (disco is None or d == disco)]


def _cadencia(inicio: float, passo: float, n: int) -> list[float]:
    return [round(inicio + i * passo, 6) for i in range(n)]


def test_os_estilos_de_rajada_sao_o_fps_a_acao_e_o_terror() -> None:
    """MORDIDA: tire ``terror`` de ``ESTILOS_DE_RAJADA`` e veja reprovar."""
    assert frozenset(DE_RAJADA) == tv.ESTILOS_DE_RAJADA
    for estilo in ESTILOS:
        assert tv.receita_do_estilo(estilo).gatilho_no_ritmo == (estilo.chave in DE_RAJADA)


@pytest.mark.parametrize("estilo", DE_RAJADA)
def test_a_arma_dos_estilos_de_rajada_e_so_o_r2(estilo: str) -> None:
    assert tv.lados_da_arma(estilo) == frozenset({DIREITO})


def test_sem_estilo_o_ritmo_nao_tem_lado() -> None:
    assert tv.lados_da_arma(None) == frozenset()
    assert tv.lados_da_arma("corrida") == frozenset()


@pytest.mark.parametrize("estilo", DE_RAJADA)
def test_dez_apertos_do_l2_em_rajada_nao_escrevem_no_l2(estilo: str) -> None:
    """MORDIDA: devolva o ``_lados`` ao lado de qualquer dedo e veja o L2 receber a arma."""
    mesa = _Mesa({P1: estilo})
    mesa.atirar(P1, ESQUERDO, _cadencia(10.0, 0.07, 10), _receita(estilo))
    assert mesa.blocos == []
    mesa.atirar(P1, DIREITO, _cadencia(20.0, 0.07, 10), _receita(estilo))
    assert mesa.de(P1, DIREITO), "o R2 do mesmo estilo segue no ritmo"
    assert mesa.de(P1, ESQUERDO) == []


def test_o_rumble_com_os_dois_gatilhos_apertados_so_escreve_no_r2() -> None:
    mesa = _Mesa({P1: "fps"}, apertado=lambda _u, _lado: True)
    receita = _receita("fps")
    for t in _cadencia(10.0, 0.07, 10):
        mesa.motor.anotar(tv.Evento(t, P1, tv.TIPO_RUMBLE, ""))
        mesa.motor.tique(t + 0.001, _xbox, receita)
    assert mesa.de(P1, ESQUERDO) == []
    assert mesa.de(P1, DIREITO)


@pytest.mark.parametrize("estilo", DE_RAJADA)
def test_a_arma_do_r2_sai_com_os_numeros_do_estilo(estilo: str) -> None:
    """MORDIDA: devolva o preset de fábrica ao ``bloco_do_gatilho`` e veja o Terror reprovar."""
    mesa = _Mesa({P1: estilo})
    mesa.atirar(P1, DIREITO, [10.0], _receita(estilo))
    assert mesa.de(P1) == [_do_perfil(estilo, DIREITO)]
    assert mesa.de(P1) != [tv._bloco_cru("SemiAutoGun", {})]


@pytest.mark.parametrize("estilo", DE_RAJADA)
def test_a_rajada_e_a_vibracao_a_20_hz(estilo: str) -> None:
    receita = _receita(estilo)
    assert receita.frequencia_da_rajada_hz == 20
    mesa = _Mesa({P1: estilo})
    mesa.atirar(P1, DIREITO, _cadencia(10.0, 0.07, 12), receita)
    rajada = tv.bloco_do_gatilho(tv.GATILHO_RAJADA, receita)
    assert mesa.de(P1) == [_do_perfil(estilo, DIREITO), rajada]
    assert rajada == tv._bloco_cru("MultiPositionVibration", {"frequency": 20})


def test_com_o_jogo_mandando_no_gatilho_o_ritmo_nao_escreve() -> None:
    def mandando(_uniq: str) -> tv.EstadoDoCanal:
        return tv.EstadoDoCanal(
            modo=tv.MODO_DUALSENSE, visto_ha_s={"trigger": 0.4},
            sessao_aberta=True, ha_jogo=True,
        )

    mesa = _Mesa({P1: "terror"})
    mesa.atirar(P1, DIREITO, _cadencia(10.0, 0.07, 12), _receita("terror"), mandando)
    assert mesa.blocos == []


def test_os_quatro_controles_cada_um_com_o_ritmo_do_seu_estilo() -> None:
    estilos = dict(zip(QUATRO, ("fps", "terror", "corrida", _ACAO), strict=True))
    mesa = _Mesa(estilos)
    receita = replace(tv.DESLIGADA, gatilho_no_ritmo=True)
    for n, uniq in enumerate(QUATRO):
        mesa.atirar(uniq, DIREITO, _cadencia(10.0 + 10 * n, 0.07, 12), receita)
        mesa.atirar(uniq, ESQUERDO, _cadencia(50.0 + 10 * n, 0.07, 12), receita)
    for uniq, estilo in estilos.items():
        if estilo == "corrida":
            assert mesa.de(uniq) == [], "a corrida não tem arma"
            continue
        rajada = tv.bloco_do_gatilho(tv.GATILHO_RAJADA, receita)
        assert mesa.de(uniq, DIREITO) == [_do_perfil(estilo, DIREITO), rajada], uniq
        assert mesa.de(uniq, ESQUERDO) == [], uniq


class _Controle:
    def __init__(self) -> None:
        self.gatilhos: list[tuple[str, str, bytes]] = []

    def set_game_trigger_for(self, uniq: str, lado: str, bloco: bytes) -> bool:
        self.gatilhos.append((uniq, lado, bytes(bloco)))
        return True

    def end_game_session_for(self, _uniq: str) -> bool:
        return True


def _producao(monkeypatch: pytest.MonkeyPatch, perfil: Any) -> tuple[Any, tv.TatoVivo]:
    """O motor de produção com a vista do perfil lida, como a ``receita_ativa`` a deixa."""
    monkeypatch.setattr(tv, "_controle_na_economia", lambda _u: False)
    monkeypatch.setattr(tv, "_VISTA_LIDA", ("", perfil))
    alvo = SimpleNamespace(controller=_Controle(), _alto_falante_subsystem=None)
    motor = tv.TatoVivo(tv.atuadores_de_producao(alvo))
    motor.ligado = True
    motor.armas_do_gatilho = tv.armas_do_gatilho_ativas(alvo)
    alvo._tato_vivo = motor
    return alvo, motor


def test_a_producao_le_o_estilo_do_perfil_ativo(monkeypatch: pytest.MonkeyPatch) -> None:
    alvo, motor = _producao(monkeypatch, _automatico("terror"))
    receita = _receita("terror")
    for t in _cadencia(10.0, 0.4, 2):
        motor.anotar(tv.Evento(t, P1, tv.TIPO_DEDO, ESQUERDO))
        motor.anotar(tv.Evento(t, P1, tv.TIPO_DEDO, DIREITO))
        motor.tique(t + 0.001, _xbox, receita, (P1,))
    assert alvo.controller.gatilhos == [(P1, "right", _do_perfil("terror", DIREITO))]


def test_a_producao_sem_estilo_ativo_nao_escreve(monkeypatch: pytest.MonkeyPatch) -> None:
    alvo, motor = _producao(monkeypatch, Profile(name="Ritmo", match=MatchAny()))
    motor.anotar(tv.Evento(10.0, P1, tv.TIPO_DEDO, DIREITO))
    motor.tique(10.001, _xbox, _receita("fps"), (P1,))
    assert alvo.controller.gatilhos == []


def test_na_acao_o_rumble_no_dedo_fica_no_l2_e_cede_o_r2_ao_ritmo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MORDIDA: devolva a cessão do dedo aos dois lados e veja o L2 da Ação calar."""
    alvo, motor = _producao(monkeypatch, _automatico(_ACAO))
    receita = _receita(_ACAO)
    assert receita.rumble_no_dedo and receita.gatilho_no_ritmo
    motor.borda_do_dedo.ver(P1, 230, 230, 50.0)
    tv.anotar_o_rumble(alvo, P1, 0, 200, 50.0)
    motor.tique(50.0 + TIQUE_S, _xbox, receita, (P1,))
    por_lado = {lado: [b for _u, d, b in alvo.controller.gatilhos if d == lado]
                for lado in ("left", "right")}
    assert por_lado == {"left": [tv.bloco_do_dedo(7)], "right": [_do_perfil(_ACAO, DIREITO)]}


def _personalizado(**campos: Any) -> Profile:
    return Profile(name="Ritmo", match=MatchAny(), estilo="fps", **campos)


def test_o_estilo_aplicado_pela_aba_perfis_da_a_mesma_arma_do_automatico() -> None:
    for estilo in DE_RAJADA:
        perfil = a10_perfis._com_o_estilo(Profile(name="Ritmo", match=MatchAny()),
                                          POR_CHAVE[estilo], [])[0]
        assert tv.armas_do_gatilho_do_perfil(perfil) == _armas(estilo), estilo
        assert _armas(estilo).geral == {DIREITO: _do_perfil(estilo, DIREITO)}


def test_no_personalizado_o_r2_fora_da_arma_nao_recebe_o_ritmo() -> None:
    """MORDIDA: leia só o estilo no personalizado e veja o Rígido da aba virar arma."""
    armas = tv.armas_do_gatilho_do_perfil(
        _personalizado(triggers={"right": {"mode": "Rigid", "params": [2, 150]}}))
    assert armas == tv.SEM_ARMAS
    mesa = _Mesa(armas=armas)
    mesa.atirar(P1, DIREITO, _cadencia(10.0, 0.07, 12), _receita("fps"))
    assert mesa.blocos == []


def test_no_personalizado_a_arma_sai_com_os_numeros_da_aba() -> None:
    da_aba = {"mode": "Weapon", "params": [2, 6, 120]}
    armas = tv.armas_do_gatilho_do_perfil(_personalizado(triggers={"right": da_aba}))
    esperado = tv._bloco_do_efeito(build_from_name("Weapon", [2, 6, 120]))
    assert armas.geral == {DIREITO: esperado}
    mesa = _Mesa(armas=armas)
    receita = _receita("fps")
    mesa.atirar(P1, DIREITO, _cadencia(10.0, 0.07, 12), receita)
    assert mesa.de(P1) == [esperado, tv.bloco_do_gatilho(tv.GATILHO_RAJADA, receita)]


def test_a_chave_velha_da_arma_vale_pela_de_hoje() -> None:
    armas = tv.armas_do_gatilho_do_perfil(
        _personalizado(triggers={"right": {"mode": "SemiAutoGun", "params": [3, 6, 5]}}))
    traduzida = traduzir_chave_velha("SemiAutoGun", [3, 6, 5])
    assert traduzida is not None and traduzida[0] == "Weapon"
    assert armas.geral == {DIREITO: tv._bloco_do_efeito(build_from_name(*traduzida))}


def test_no_personalizado_cada_controle_tem_a_arma_que_a_aba_deu_a_ele() -> None:
    p2, p3 = QUATRO[1], QUATRO[2]
    perfil = _personalizado(
        triggers={"right": {"mode": "Machine", "params": [2, 9, 4, 40]}},
        controllers={
            p2.replace(":", ""): {"triggers": {"right": {"mode": "Rigid", "params": [2, 150]}}},
            p3.replace(":", ""): {"triggers": {"right": {"mode": "Weapon", "params": [2, 6, 120]}}},
        },
    )
    armas = tv.armas_do_gatilho_do_perfil(perfil)
    mesa = _Mesa(armas=armas)
    receita = _receita("fps")
    for n, uniq in enumerate(QUATRO):
        mesa.atirar(uniq, DIREITO, [10.0 + n], receita)
    assert mesa.de(P1, DIREITO) == [tv._bloco_do_efeito(build_from_name("Machine", [2, 9, 4, 40]))]
    assert mesa.de(p2) == [], "o P2 deixou o R2 no Rígido"
    assert mesa.de(p3, DIREITO) == [tv._bloco_do_efeito(build_from_name("Weapon", [2, 6, 120]))]
    assert mesa.de(QUATRO[3], DIREITO) == mesa.de(P1, DIREITO)
