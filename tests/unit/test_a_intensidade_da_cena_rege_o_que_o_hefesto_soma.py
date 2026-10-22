"""A intensidade da cena rege o que o Hefesto soma.

A-INTENSIDADE-DA-CENA-REGE-O-QUE-O-HEFESTO-SOMA-01 (22/10/2026).

A energia do som do jogo e as bordas do rumble e do dedo andam por uma média lenta; a intensidade
cai em calma, tensa ou combate, com histerese e quatro segundos de permanência, e a faixa gradua
o toque do tiro, o padrão dos motores, o corpo e o ritmo da luz que respira. O par do jogo (o
degrau do dedo) não muda em faixa nenhuma. A graduação nasce desligada (a bancada liga); aqui ela
liga por parâmetro. Nada toca o aparelho: o pad, o leitor e o alto-falante são de mentira, o
motor é o de produção.
"""
from __future__ import annotations

import json
import math
import struct
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import intensidade_da_cena as ic
from hefesto_dualsense4unix.daemon.subsystems import luz_animada as luz
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.profiles import formas_de_haptica as formas
from hefesto_dualsense4unix.profiles.estilos_de_jogo import POR_CHAVE
from hefesto_dualsense4unix.profiles.schema import EfeitoDaLuz

P1 = "aa:bb:cc:00:00:01"
QUATRO = (P1, "aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03", "aa:bb:cc:00:00:04")
_ACAO = "acao"  # (noqa-acento): chave do estilo
TIQUE_S = 0.1


# --- a régua pura -----------------------------------------------------------------------------


def _evento(tipo: str, uniq: str = P1) -> Any:
    return SimpleNamespace(tipo=tipo, uniq=uniq)


def _sessao(cena: ic.IntensidadeDaCena, segundos: float, por_s: float, *, inicio: float = 0.0,
            tipo: str = ic.TIPO_RUMBLE, uniqs: tuple[str, ...] = (P1,)) -> float:
    """``segundos`` de jogo com ``por_s`` bordas por segundo em cada controle; devolve o fim."""
    agora, devido = inicio, 0.0
    for _ in range(round(segundos / TIQUE_S)):
        agora += TIQUE_S
        devido += por_s * TIQUE_S
        while devido >= 1.0:
            devido -= 1.0
            cena.contar([_evento(tipo, u) for u in uniqs])
        cena.andar(agora, jogo=True, ouvido=False, uniqs=uniqs)
    return agora


def test_a_cena_calma_e_o_combate_caem_em_faixas_diferentes() -> None:
    calma = ic.IntensidadeDaCena(graduar=True)
    calma.contar([_evento(ic.TIPO_RUMBLE)])  # o jogo mostrou que vibra, e a cena acalma
    _sessao(calma, 30.0, 0.0)
    combate = ic.IntensidadeDaCena(graduar=True)
    _sessao(combate, 30.0, 4.0)
    tensa = ic.IntensidadeDaCena(graduar=True)
    _sessao(tensa, 30.0, 1.5)
    assert (calma.faixa, tensa.faixa, combate.faixa) == (ic.CALMA, ic.TENSA, ic.COMBATE)
    assert calma.intensidade is not None and combate.intensidade is not None
    assert calma.intensidade < 0.1 < 0.9 < combate.intensidade


def test_a_energia_do_som_do_jogo_separa_o_silencio_do_estrondo() -> None:
    def tocar(nivel: float) -> ic.IntensidadeDaCena:
        cena = ic.IntensidadeDaCena(graduar=True)
        amostra = round(32767 * nivel)
        pcm = struct.pack("<hh", amostra, -amostra) * 480
        agora = 0.0
        for _ in range(300):
            agora += TIQUE_S
            cena.ouvir_o_som(pcm)
            cena.andar(agora, jogo=True, ouvido=True, uniqs=(P1,))
        return cena

    assert tocar(0.01).faixa == ic.CALMA
    assert tocar(0.4).faixa == ic.COMBATE
    assert ic.rms_do_pcm(struct.pack("<hh", 16384, -16384)) == pytest.approx(0.5)


def test_a_faixa_so_troca_depois_de_quatro_segundos_nela() -> None:
    cena = ic.IntensidadeDaCena(graduar=True)
    cena.contar([_evento(ic.TIPO_RUMBLE)])
    fim = _sessao(cena, 3.9, 0.0)
    assert cena.intensidade is not None and cena.intensidade < 0.2, "a média já diz calma"
    assert cena.faixa == ic.COMBATE, "o jogo começa na força de antes e não pula antes dos 4 s"
    _sessao(cena, 0.3, 0.0, inicio=fim)
    assert cena.faixa == ic.CALMA


def test_a_histerese_segura_a_faixa_em_volta_da_divisa() -> None:
    assert ic.faixa_de(0.27, ic.CALMA) == ic.CALMA
    assert ic.faixa_de(0.31, ic.CALMA) == ic.TENSA
    assert ic.faixa_de(0.22, ic.TENSA) == ic.TENSA
    assert ic.faixa_de(0.19, ic.TENSA) == ic.CALMA
    assert ic.faixa_de(0.52, ic.COMBATE) == ic.COMBATE
    assert ic.faixa_de(0.49, ic.COMBATE) == ic.TENSA


def test_o_jogo_que_nunca_vibrou_nao_cai_na_calma_por_um_sinal_que_ele_nao_da() -> None:
    cena = ic.IntensidadeDaCena(graduar=True)
    _sessao(cena, 30.0, 0.0)
    assert cena.intensidade is None
    assert cena.faixa == ic.COMBATE and cena.fator(_ACAO) == 1.0


def test_sem_jogo_a_cena_se_esquece_e_o_fator_e_1() -> None:
    cena = ic.IntensidadeDaCena(graduar=True)
    cena.contar([_evento(ic.TIPO_RUMBLE)])
    _sessao(cena, 10.0, 0.0)
    assert cena.fator(_ACAO) == ic.FATOR_DA_FAIXA[ic.CALMA]
    cena.andar(11.0, jogo=False, ouvido=False)
    assert (cena.jogo, cena.faixa, cena.fator(_ACAO)) == (False, None, 1.0)
    assert cena.velocidade_da_luz(5, _ACAO) == 1.0


@pytest.mark.parametrize("estilo", ["nativo", "personalizado", None, ""])
def test_o_nativo_e_o_personalizado_nao_graduam(estilo: str | None) -> None:
    cena = ic.IntensidadeDaCena(graduar=True)
    cena.contar([_evento(ic.TIPO_RUMBLE)])
    _sessao(cena, 10.0, 0.0)
    assert cena.faixa == ic.CALMA
    assert cena.fator(estilo) == 1.0
    assert cena.velocidade_da_luz(5, estilo) == 1.0


def test_a_graduacao_nasce_desligada_e_a_cena_se_calcula_mesmo_assim() -> None:
    assert ic.GRADUACAO_LIGADA is False
    cena = ic.IntensidadeDaCena()
    cena.contar([_evento(ic.TIPO_RUMBLE)])
    _sessao(cena, 10.0, 0.0)
    assert cena.faixa == ic.CALMA, "a faixa se calcula e se expõe"
    assert cena.fator(_ACAO) == 1.0 and cena.velocidade_da_luz(5, _ACAO) == 1.0
    assert cena.estado(_ACAO)["graduando"] is False


def test_a_cena_e_a_do_controle_mais_agitado_entre_os_quatro() -> None:
    cena = ic.IntensidadeDaCena(graduar=True)
    agora = 0.0
    for i in range(300):
        agora += TIQUE_S
        if i % 2 == 0:
            cena.contar([_evento(ic.TIPO_RUMBLE, QUATRO[3])])  # só o quarto controle luta
        cena.andar(agora, jogo=True, ouvido=False, uniqs=QUATRO)
    assert cena.faixa == ic.COMBATE
    assert cena.por_segundo(ic.TIPO_RUMBLE) == pytest.approx(5.0, rel=0.05)


# --- o motor de produção --------------------------------------------------------------------


class _Pad:
    def __init__(self) -> None:
        self.backend = "uinput"
        self.visto_ha_s: dict[str, float] = {}
        self.game_open = True
        self.ff_last_sent = (0, 0)
        self.ff_nao_nulo_count = 0


class _Leitor:
    def __init__(self) -> None:
        self.foto = SimpleNamespace(l2_raw=0, r2_raw=0, buttons_pressed=frozenset(),
                                    lx=128, ly=128, rx=128, ry=128)

    def snapshot(self) -> Any:
        return self.foto


class _AltoFalante:
    def __init__(self) -> None:
        self.toques: list[tuple[str, float]] = []
        self.corpos: list[tuple[str, float]] = []

    def tocar_o_toque(self, uniq: str, energia: float, lado: str, duracao_ms: int,
                      forma: str = formas.TOQUE) -> bool:
        self.toques.append((uniq, energia))
        return True

    def tocar_o_corpo(self, uniq: str, amostras: Any, lado: str = "centro") -> bool:
        self.corpos.append((uniq, max((abs(x) for x in amostras), default=0.0)))
        return True


class _Ouvido:
    ouvindo = True

    def comecar(self) -> None:
        return None

    def tirar(self) -> list[Any]:
        return []


class _Mesa:
    """O daemon de mentira com o motor de produção e a cena graduando por parâmetro."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, estilo: str = _ACAO,
                 jogadores: tuple[str, ...] = (P1,), graduar: bool = True) -> None:
        receita = tv.receita_do_estilo(POR_CHAVE[estilo])
        monkeypatch.setattr(tv, "receita_ativa", lambda _d: receita)
        monkeypatch.setattr(tv, "estilo_ativo", lambda _d: estilo)
        monkeypatch.setattr(tv, "_controle_na_economia", lambda _u: False)
        self.pads = {uniq: _Pad() for uniq in jogadores}
        self.alto_falante = _AltoFalante()
        self.daemon = SimpleNamespace(
            controller=SimpleNamespace(primary_uniq=jogadores[0]),
            _last_state=SimpleNamespace(l2_raw=0, r2_raw=0, buttons_pressed=frozenset(),
                                        raw_lx=128, raw_ly=128, raw_rx=128, raw_ry=128),
            _gamepad_device=self.pads[jogadores[0]],
            _coop_manager=SimpleNamespace(_players={
                uniq: SimpleNamespace(vpad=self.pads[uniq], reader=_Leitor())
                for uniq in jogadores[1:]}),
            _alto_falante_subsystem=self.alto_falante,
            display_authority="game",
        )
        self.motor = tv.TatoVivo(tv.atuadores_de_producao(self.daemon))
        self.motor.cena = ic.IntensidadeDaCena(graduar=graduar)
        self.daemon._tato_vivo = self.motor
        self.passo = tv.Passo(self.daemon, self.motor)
        self.agora = 0.0
        self.passo(self.agora)

    def tique(self, segundos: float = 1.0 / 60.0) -> None:
        self.agora += segundos
        self.passo(self.agora)

    def golpe(self, uniq: str = P1, nivel: int = 200) -> None:
        tv.anotar_o_rumble(self.daemon, uniq, 0, 0, self.agora)
        tv.anotar_o_rumble(self.daemon, uniq, nivel, nivel, self.agora)

    def calma(self, segundos: int = 20) -> None:
        for _ in range(segundos):
            self.tique(1.0)

    def combate(self, segundos: int = 20) -> None:
        for _ in range(segundos * 4):
            self.golpe()
            self.tique(0.125)
            tv.anotar_o_rumble(self.daemon, P1, 0, 0, self.agora)
            self.tique(0.125)

    def ultimo_toque(self, uniq: str = P1) -> float:
        self.golpe(uniq)
        self.tique()
        return [e for u, e in self.alto_falante.toques if u == uniq][-1]

    def na_faixa(self, faixa: str) -> None:
        """A cena posta numa faixa agora (a permanência segura até o fim do teste)."""
        cena = self.motor.cena
        cena.jogo, cena.faixa, cena._desde = True, faixa, self.agora


def _toques_na_calma_e_no_combate(monkeypatch: pytest.MonkeyPatch, graduar: bool) -> tuple[
        float, float]:
    mesa = _Mesa(monkeypatch, graduar=graduar)
    mesa.golpe()
    mesa.tique()  # o jogo mostrou que vibra
    mesa.calma()
    calmo = mesa.ultimo_toque()
    assert mesa.motor.cena.faixa == ic.CALMA
    mesa.combate()
    assert mesa.motor.cena.faixa == ic.COMBATE
    return calmo, mesa.ultimo_toque()


def test_na_cena_calma_o_toque_que_o_hefesto_soma_e_0_6_do_combate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calmo, combate = _toques_na_calma_e_no_combate(monkeypatch, graduar=True)
    assert calmo == pytest.approx(combate * ic.FATOR_DA_FAIXA[ic.CALMA], rel=1e-3)


def test_com_a_graduacao_desligada_o_toque_e_o_de_hoje_em_toda_cena(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calmo, combate = _toques_na_calma_e_no_combate(monkeypatch, graduar=False)
    receita = tv.receita_do_estilo(POR_CHAVE[_ACAO])
    assert calmo == combate
    assert combate == pytest.approx(200 / 255.0 * receita.forca_do_toque, rel=1e-3)


def test_os_quatro_controles_graduam_cada_um_com_o_seu_toque(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hoje = _Mesa(monkeypatch, jogadores=QUATRO, graduar=False)
    mesa = _Mesa(monkeypatch, jogadores=QUATRO)
    mesa.na_faixa(ic.CALMA)
    for uniq in QUATRO:
        assert mesa.ultimo_toque(uniq) == pytest.approx(
            hoje.ultimo_toque(uniq) * ic.FATOR_DA_FAIXA[ic.CALMA], rel=1e-3)


def test_o_padrao_dos_motores_segue_a_faixa(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch)
    motores = next(a for a in mesa.motor.atuadores if isinstance(a, tv.AtuadorDosMotores))
    degrau = tv.FORCA_DO_DEGRAU[POR_CHAVE[_ACAO].vibracao]
    mesa.na_faixa(ic.COMBATE)
    assert motores._forca_de(P1) == pytest.approx(degrau)
    mesa.na_faixa(ic.TENSA)
    assert motores._forca_de(P1) == pytest.approx(degrau * ic.FATOR_DA_FAIXA[ic.TENSA])


def _grave(mesa: _Mesa) -> None:
    n = round(0.04 * formas.TAXA)
    mesa.passo.alimentar_o_corpo(b"".join(
        struct.pack("<hh", v, v) for v in (
            round(20000 * math.sin(2 * math.pi * 60 * i / formas.TAXA)) for i in range(n))))


def test_o_corpo_que_o_hefesto_soma_segue_a_faixa(monkeypatch: pytest.MonkeyPatch) -> None:
    def corpo(faixa: str) -> float:
        mesa = _Mesa(monkeypatch, "corrida")  # a Corrida veste o Som no corpo inteiro
        mesa.motor.ouvido = _Ouvido()
        mesa.na_faixa(faixa)
        _grave(mesa)
        mesa.tique()
        (_, pico), = mesa.alto_falante.corpos
        return pico

    cheio = corpo(ic.COMBATE)
    assert cheio > 0.05
    assert corpo(ic.CALMA) == pytest.approx(cheio * ic.FATOR_DA_FAIXA[ic.CALMA], rel=1e-3)


# --- o par do jogo não muda -----------------------------------------------------------------


def test_o_degrau_do_dedo_e_o_par_cru_do_jogo_em_toda_faixa() -> None:
    def blocos(faixa: str) -> list[bytes]:
        escritas: list[bytes] = []
        dedo = tv.AtuadorDoDedo(lambda _u, _d, bloco: escritas.append(bloco), lambda _u: True,
                                lambda _u, _l: True)
        motor = tv.TatoVivo([dedo])
        motor.ligado = True
        motor.cena = ic.IntensidadeDaCena(graduar=True)
        motor.cena.jogo, motor.cena.faixa = True, faixa
        daemon = SimpleNamespace(_tato_vivo=motor)
        receita = tv.receita_do_estilo(POR_CHAVE[_ACAO])
        estado = {P1: tv.EstadoDoCanal(tv.MODO_XBOX, ha_jogo=True)}
        agora = 100.0
        for nivel in (40, 120, 200, 255):
            tv.anotar_o_rumble(daemon, P1, 0, nivel, agora)
            agora += 0.5
            motor.tique(agora, estado.get, receita, (P1,))
        return escritas

    combate = blocos(ic.COMBATE)
    assert combate == [tv.bloco_do_dedo(tv.degrau_do_rumble(0, n))
                       for n in (40, 120, 200, 255) for _lado in ("esquerdo", "direito")]
    assert blocos(ic.CALMA) == combate, "o rumble do jogo no dedo não passa pela cena"


# --- a luz que respira ----------------------------------------------------------------------


def test_a_luz_que_respira_desacelera_na_calma_e_nunca_passa_do_ritmo_do_efeito() -> None:
    cena = ic.IntensidadeDaCena(graduar=True)
    cena.jogo = True
    for faixa in ic.FAIXAS:
        cena.faixa = faixa
        for ritmo in range(1, 11):
            assert 0.0 < cena.velocidade_da_luz(ritmo, _ACAO) <= 1.0
    cena.faixa = ic.CALMA
    assert cena.velocidade_da_luz(3, _ACAO) == pytest.approx(1 / 3)
    cena.faixa = ic.TENSA
    assert cena.velocidade_da_luz(3, _ACAO) == pytest.approx(2 / 3)


def _subidas_por_segundo(velocidade: float | None, ritmo: int = 10,
                         segundos: float = 20.0) -> tuple[float, int]:
    quadros: list[tuple[int, int, int]] = []
    animada = luz.LuzAnimada(lambda _u, cor: quadros.append(cor) or True, lambda _u: True)
    plano = {P1: luz.PlanoDoControle(EfeitoDaLuz("respirar", ((255, 0, 0),), ritmo), 1.0)}
    agora = 0.0
    while agora < segundos:
        agora += luz.INTERVALO_MINIMO
        animada.tique(agora, plano, velocidade_do_respirar=(
            None if velocidade is None else (lambda _r: velocidade)))
    vermelho = [c[0] for c in quadros]
    subidas = sum(1 for a, b, c in zip(vermelho, vermelho[1:], vermelho[2:], strict=False)
                  if b > a and b >= c)
    return subidas / segundos, len(quadros)


@pytest.mark.parametrize("faixa", ic.FAIXAS)
def test_a_luz_nao_passa_de_tres_subidas_por_segundo_em_faixa_nenhuma(faixa: str) -> None:
    cena = ic.IntensidadeDaCena(graduar=True)
    cena.jogo, cena.faixa = True, faixa
    por_s, _ = _subidas_por_segundo(cena.velocidade_da_luz(10, _ACAO))
    assert por_s <= 3.0
    assert tv.TETO_DA_LUZ_POR_S <= 3.0, "o pulso do tiro segue no teto dele, fora da cena"


def test_a_calma_respira_mais_devagar_que_o_combate() -> None:
    combate, _ = _subidas_por_segundo(1.0, ritmo=5, segundos=40.0)
    calma, _ = _subidas_por_segundo(1 / 5, ritmo=5, segundos=40.0)
    assert combate == pytest.approx(0.5, abs=0.05)
    assert calma == pytest.approx(0.1, abs=0.05)


def test_sem_a_cena_a_luz_respira_no_relogio_de_sempre() -> None:
    sem, _ = _subidas_por_segundo(None, ritmo=5, segundos=40.0)
    com_um, _ = _subidas_por_segundo(1.0, ritmo=5, segundos=40.0)
    assert sem == com_um


# --- a bancada lê a cena ao vivo ------------------------------------------------------------


def test_o_estado_do_daemon_traz_a_cena_e_sem_motor_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    assert ic.estado_do_daemon(SimpleNamespace()) is None
    mesa = _Mesa(monkeypatch)
    mesa.golpe()
    mesa.tique()
    estado = ic.estado_do_daemon(mesa.daemon)
    assert estado is not None
    assert {"ligado", "jogo", "ouvido", "graduando", "intensidade", "faixa", "fator",
            "energia", "rumble_por_s", "dedo_por_s", "bordas_do_rumble"} <= set(estado)
    assert estado["bordas_do_rumble"] == 1
    assert mesa.motor.estado()["intensidade_da_cena"]["jogo"] is True


# --- o gravador da bancada: a análise é pura -----------------------------------------------


def _gravador() -> Any:
    import importlib.util
    import sys
    from pathlib import Path

    caminho = (Path(__file__).resolve().parents[2] / "scripts" / "ensaios"
               / "gravar_a_intensidade_da_cena.py")
    spec = importlib.util.spec_from_file_location("gravar_a_intensidade_da_cena", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _gravacao(gravador: Any, jogo: str, genero: str, calmo: float, combate: float) -> Any:
    perguntas = [{"t": i * 0.1, "marca": marca, "cena": {"jogo": True, "intensidade": valor}}
                 for i, (marca, valor) in enumerate(
                     [("calmo", calmo)] * 20 + [(None, 0.5)] * 5 + [("combate", combate)] * 20)]
    return gravador.ler_gravacao("\n".join(
        json.dumps(x) for x in [{"jogo": jogo, "genero": genero}, *perguntas]))


def test_o_gravador_so_da_verde_com_o_combate_acima_do_calmo_nos_tres_generos() -> None:
    g = _gravador()
    tres = [_gravacao(g, j, gen, 0.1, 0.8) for j, gen in
            (("A", "tiro"), ("B", "luta"), ("C", "terror"))]
    assert g.veredito(tres).rc == g.RC_SEPARA
    assert g.veredito(tres[:2]).rc == g.RC_FALTA, "dois gêneros não provam"
    invertido = [*tres[:2], _gravacao(g, "C", "terror", 0.8, 0.1)]
    assert g.veredito(invertido).rc == g.RC_NAO_SEPARA
    assert g.veredito([]).rc == g.RC_SEM_DADO


def test_as_marcas_escritas_depois_trocam_as_do_teclado() -> None:
    g = _gravador()
    gravacao = _gravacao(g, "A", "tiro", 0.1, 0.8)
    trocada = g.com_as_marcas(gravacao, g.ler_marcas("0 2.0 combate  # o começo\n2.5 4.5 calmo"))
    medianas = g.medianas_por_trecho(trocada)
    assert medianas["combate"]["intensidade"] == pytest.approx(0.1)
    assert medianas["calmo"]["intensidade"] == pytest.approx(0.8)
