"""OS-EFEITOS-NOVOS-DO-GATILHO-DA-HAPTICA-E-DA-LUZ-NASCEM-01: os sete efeitos do bloco C nascem.

A tabela `S` e a lista `E` da página aprovada em 19/10/2026 (`redistribuicao-dos-efeitos.html`)
dão a cada estilo o efeito dele. Aqui cada efeito novo é medido pelo que faz, com dublês (o tocador
é uma lista, o relógio é injetado e o aparelho nunca é tocado), nos quatro controles.

As mordidas (arrancar a cura, ver reprovar, devolver conferindo o md5 do arquivo):
- `golpe-leve` de volta no Point and click (nos dois lados): a régua 1 e a 2;
- a guarda do nível do rumble fora do Motor de época (`if nivel <= 0.0: continue`): a régua 3;
- o Grão sem dono (`receita.grao_escolhido` trocado por `False` em `_levar_o_grao`): a régua 4;
- o Eco sem o limiar (`ECO_A_PARTIR_DE = 0.0`): a régua 5;
- `NA_SOLTURA_DO_ESTILO = {}` (a Onda do Furtivo volta a tocar no aperto): a régua 6;
- o Acende sem o freio de virada (`MEIO_VAIVEM_DO_ACENDE_S = 0.0`): a régua 7;
- a Bateria que respira com o controle no cabo (`ESTADOS_DE_CARGA_EM_DIA = frozenset()`) ou que
  pisca (`"respirar"` por `"piscar"` na luz da Bateria): a régua 8;
- `golpe-falha`, `golpe-aparo` ou `travar-esgotado` fora do `na_frente`: a régua 9.
"""
from __future__ import annotations

import pathlib
import re
from itertools import pairwise
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import luz_animada as luz
from hefesto_dualsense4unix.daemon.subsystems import padroes_de_vibracao as pv
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.profiles import efeitos_de_imersao as ei
from hefesto_dualsense4unix.profiles import efeitos_de_luz as el
from hefesto_dualsense4unix.profiles import estilos_de_jogo as ej
from hefesto_dualsense4unix.profiles import formas_de_haptica as fh
from hefesto_dualsense4unix.profiles.schema import EfeitoDaLuz, LedsConfig, MatchAny, Profile

RAIZ = pathlib.Path(__file__).resolve().parents[2]

#: Os quatro controles, pela cor do plástico: Starlight Blue, White, Cosmic Red e Galactic
#: Purple. Endereços de faixa forjada (`aa:bb:cc`), nunca de aparelho de verdade.
AZUL, BRANCO, VERMELHO, ROXO = (f"aa:bb:cc:00:00:{n:02x}" for n in (0x11, 0x12, 0x13, 0x14))
QUATRO = (AZUL, BRANCO, VERMELHO, ROXO)
COR_DE = {AZUL: (40, 80, 255), BRANCO: (240, 240, 240), VERMELHO: (255, 30, 30),
          ROXO: (170, 60, 255)}
JOGO_LIVRE = tv.EstadoDoCanal(modo=tv.MODO_XBOX, ha_jogo=True)


# --- 1. A receita da página, sem a marca -------------------------------------------------


#: Os sete estilos da tabela e o que a página pede de cada um (a chave do estilo mora no código).
TABELA = {
    "souls": {"haptica": fh.ECO},
    "simulacao": {"haptica": fh.GRAO},
    "retro": {"haptica": fh.MOTOR_DE_EPOCA},
    "point_and_click": {"r2": ("Weapon", "clique-mouse"), "l2": ("Weapon", "clique-mouse")},
    "furtivo": {"l2": ("Resistance", "carga-folego")},
    "corrida": {"luz": "acende"},
    "maratona": {"luz": "bateria"},
}


def test_a_receita_dos_sete_estilos_e_a_da_pagina_e_nenhuma_marca_sobrou() -> None:
    """Os sete efeitos estão nos estilos que a página pede, e `src/` não diz mais `# bloco C`.

    MORDIDA: devolva o `golpe-leve` ao Point and click (ou ponha de volta o `Impacto` na Souls):
    isto reprova.
    """
    for chave, pede in TABELA.items():
        e = ej.POR_CHAVE[chave]
        if "haptica" in pede:
            assert fh.POR_ESTILO[chave] == pede["haptica"], chave
        if "r2" in pede:
            assert (e.r2.modo, e.r2.imersao) == pede["r2"], f"{chave}: R2"
        if "l2" in pede:
            assert (e.l2.modo, e.l2.imersao) == pede["l2"], f"{chave}: L2"
        if "luz" in pede:
            assert e.receita_invisivel is not None
            assert e.receita_invisivel.luz == pede["luz"], f"{chave}: luz"
    sobras = [
        f"{p.relative_to(RAIZ)}:{n}"
        for p in sorted((RAIZ / "src").rglob("*.py"))
        for n, linha in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if re.search(r"#.*\bbloco C\b", linha)
    ]
    assert not sobras, sobras


# --- 2. O Clique · mouse não é o Golpe · fraco -------------------------------------------


def _numeros(chave: str, modo: str = "Weapon") -> dict[str, int]:
    imersao = next(i for i in ei.IMERSOES if i.chave == chave)
    achados = ei.ajustes_da_imersao(imersao, modo)
    assert achados is not None, chave
    return dict(achados)


def test_o_clique_do_mouse_nao_e_o_golpe_fraco_e_comeca_antes() -> None:
    """Os números diferem, o começo do Clique é anterior ao do Golpe e ele é raso e seco.

    MORDIDA: ponha o `golpe-leve` nos dois lados do Point and click e isto reprova.
    """
    clique, golpe = _numeros("clique-mouse"), _numeros("golpe-leve")
    assert clique != golpe
    assert clique["start"] < golpe["start"]
    assert clique["end"] - clique["start"] < golpe["end"] - golpe["start"], "raso"
    assert clique["force"] > golpe["force"], "seco"
    pc = ej.POR_CHAVE["point_and_click"]
    assert (pc.r2.imersao, pc.l2.imersao) == ("clique-mouse", "clique-mouse")
    achada = ei.imersao_dos_numeros("Weapon", [clique[k] for k in ("start", "end", "force")])
    assert achada is not None and achada[0].chave == "clique-mouse"


# --- 3. O Motor de época é mudo sem o jogo -----------------------------------------------


class _AltoFalante:
    def __init__(self) -> None:
        self.corpo: list[tuple[str, Any]] = []

    def tocar_o_corpo(self, uniq: str, amostras: Any) -> bool:
        self.corpo.append((uniq, amostras))
        return True


def _passo(monkeypatch: pytest.MonkeyPatch, estilo: str) -> tuple[tv.Passo, _AltoFalante]:
    alto = _AltoFalante()
    monkeypatch.setattr(tv, "estilo_ativo", lambda _d: estilo)
    passo = tv.Passo(SimpleNamespace(_alto_falante_subsystem=alto), tv.TatoVivo([]))
    return passo, alto


def _vpad(fraco: int, forte: int) -> Any:
    return SimpleNamespace(ff_last_sent=(fraco, forte))


def _rodar_o_motor_de_epoca(
    passo: tv.Passo, nivel: tuple[int, int], segundos: float, desde: float = 0.0,
    quais: tuple[str, ...] = QUATRO,
) -> float:
    """Gira o tique de 60 Hz; devolve o instante final."""
    receita = tv.Receita(motor_de_epoca_escolhido=True)
    t = desde
    while t < desde + segundos:
        passo._agora_da_continua = t
        passo._levar_o_motor_de_epoca(receita, quais, lambda _u: JOGO_LIVRE,
                                      lambda _u: _vpad(*nivel))
        t += tv.INTERVALO_S
    return t


def test_o_motor_de_epoca_e_mudo_sem_rumble_e_toca_com_rumble_nos_quatro(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Rumble do jogo em zero: nada toca; com o rumble ligado, cada um dos quatro toca.

    MORDIDA: tire a guarda `if nivel <= 0.0: continue` do `_levar_o_motor_de_epoca` e isto
    reprova (o zumbido nasceria sem o jogo vibrar).
    """
    passo, alto = _passo(monkeypatch, "retro")
    _rodar_o_motor_de_epoca(passo, (0, 0), 1.0)
    assert alto.corpo == [], "sem o jogo vibrar, o Motor de época não toca nada"

    t = _rodar_o_motor_de_epoca(passo, (0, 200), 1.0)
    assert {uniq for uniq, _ in alto.corpo} == set(QUATRO)
    assert max(abs(x) for _, a in alto.corpo for x in a) > 0.02, "o zumbido soa"
    assert max(abs(x) for _, a in alto.corpo for x in a) <= fh.TETO_DO_CORPO + 1e-9

    # o jogo para: a parada arrasta e depois cala; de novo mudo, e o gerador morre
    t = _rodar_o_motor_de_epoca(passo, (0, 0), 2.0, desde=t)
    assert not passo._motores_de_epoca, "o zumbido acabou e ninguém ficou tocando"
    antes = len(alto.corpo)
    _rodar_o_motor_de_epoca(passo, (0, 0), 0.5, desde=t)
    assert len(alto.corpo) == antes


def test_o_motor_de_epoca_so_toca_no_estilo_que_o_pede(monkeypatch: pytest.MonkeyPatch) -> None:
    passo, alto = _passo(monkeypatch, "acao")  # (noqa-acento) chave
    _rodar_o_motor_de_epoca(passo, (0, 255), 0.5)
    assert alto.corpo == []


# --- 4. O Grão é contínuo e o Eco não ----------------------------------------------------


def test_o_grao_toca_sem_aperto_e_sem_parar_nos_quatro(monkeypatch: pytest.MonkeyPatch) -> None:
    """O Grão não espera dedo nem tiro: um segundo de tique e os quatro receberam grãos.

    MORDIDA: troque `receita.grao_escolhido` por `False` no `_levar_o_grao` (ou ponha o Grão só
    no aperto) e isto reprova.
    """
    passo, alto = _passo(monkeypatch, "simulacao")
    receita = tv.Receita(grao_escolhido=True)
    t = 0.0
    while t < 1.0:
        passo._agora_da_continua = t
        passo._levar_o_grao(receita, QUATRO, lambda _u: JOGO_LIVRE)
        t += tv.INTERVALO_S
    assert {uniq for uniq, _ in alto.corpo} == set(QUATRO)
    amostras = [x for uniq, a in alto.corpo if uniq == AZUL for x in a]
    assert len(amostras) >= fh.TAXA * 0.9, "sem parar: o segundo inteiro de amostras"
    pico = max(abs(x) for x in amostras)
    assert 0.05 < pico <= fh.TETO_DO_CORPO
    # grãos finos e rápidos: entre um grão e outro há silêncio (não é um tom contínuo)
    assert sum(1 for x in amostras if abs(x) < 1e-6) > len(amostras) * 0.2


def test_o_grao_cala_na_bateria_longa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tv, "_controle_na_economia", lambda _u: True)
    passo, alto = _passo(monkeypatch, "simulacao")
    passo._agora_da_continua = 0.0
    passo._levar_o_grao(tv.Receita(grao_escolhido=True), QUATRO, lambda _u: JOGO_LIVRE)
    assert alto.corpo == []


class _Toques:
    def __init__(self) -> None:
        self.feitos: list[tuple[Any, ...]] = []

    def __call__(self, *args: Any) -> bool:
        self.feitos.append(args)
        return True


def _golpe(estilo: str, energia: float, uniq: str = AZUL) -> _Toques:
    toques = _Toques()
    motor = tv.TatoVivo([tv.AtuadorDaHaptica(
        toques, None, lambda _u: None, lambda: estilo, lambda _u: False)])
    motor.anotar(tv.Evento(0.0, uniq, tv.TIPO_RUMBLE, tv.LADO_ESQUERDO, energia))
    motor.tique(1.0, lambda _u: JOGO_LIVRE, tv.Receita(vibracao_por_tiro=True))
    return toques


@pytest.mark.parametrize("uniq", QUATRO)
def test_o_eco_toca_so_no_golpe_forte(uniq: str) -> None:
    """Golpe forte (>= 0,7) leva o Eco; o fraco leva o Impacto, sem a cauda grave.

    MORDIDA: `ECO_A_PARTIR_DE = 0.0` e o golpe fraco reprova aqui.
    """
    assert _golpe("souls", 1.0, uniq).feitos[0][4] == fh.ECO
    assert _golpe("souls", tv.ECO_A_PARTIR_DE, uniq).feitos[0][4] == fh.ECO
    assert _golpe("souls", 0.3, uniq).feitos[0][4] == fh.IMPACTO


def test_o_eco_tem_a_cauda_grave_e_o_impacto_nao() -> None:
    eco = fh.amostras(fh.ECO, 1.0, 40)
    impacto = fh.amostras(fh.IMPACTO, 1.0, 40)
    assert len(eco) - len(impacto) >= fh.TAXA * 0.25, "a cauda de 300 ms vem depois do Impacto"
    assert eco[-1] == 0.0


# --- 5. O Eco e a Onda: a Onda do Furtivo sai ao soltar ----------------------------------


def _onda_do_furtivo(eventos: list[tv.Evento]) -> list[tuple[float, int, int]]:
    escritas: list[tuple[float, int, int]] = []
    relogio = [0.0]

    def escrever(_u: str, fraco: int, forte: int) -> bool:
        escritas.append((relogio[0], fraco, forte))
        return True

    atuador = tv.AtuadorDosMotores(
        escrever,
        lambda _u: pv.padrao_que_vale(None, "furtivo"),
        lambda _u: False,
        lambda _u: 1.0,
        lambda: "furtivo",
    )
    motor = tv.TatoVivo([atuador])
    quais = tuple({e.uniq for e in eventos}) or (AZUL,)
    pendentes = sorted(eventos, key=lambda e: e.instante)
    t = 0.0
    while t <= 6.0:
        relogio[0] = t
        while pendentes and pendentes[0].instante <= t:
            motor.anotar(pendentes.pop(0))
        motor.tique(t, lambda _u: JOGO_LIVRE, tv.Receita(padroes_escolhidos=True), uniqs=quais)
        t += tv.INTERVALO_S
    return escritas


@pytest.mark.parametrize("uniq", QUATRO)
def test_a_onda_do_furtivo_toca_ao_soltar_o_l2_segurado_e_nao_ao_apertar(uniq: str) -> None:
    """A Onda sai quando o L2 solta depois de 2 s; apertar, ou soltar cedo, não toca.

    MORDIDA: `NA_SOLTURA_DO_ESTILO = {}` e a Onda volta a tocar no aperto: a primeira linha
    reprova.
    """
    apertou = tv.Evento(0.5, uniq, tv.TIPO_DEDO, tv.LADO_ESQUERDO, 1.0)
    assert pv.padrao_que_vale(None, "furtivo") == "onda"
    assert _onda_do_furtivo([apertou]) == [], "o aperto não toca a Onda"

    solta_cedo = tv.Evento(1.0, uniq, tv.TIPO_SOLTA, tv.LADO_ESQUERDO, 1.0, None, 1.9)
    assert _onda_do_furtivo([apertou, solta_cedo]) == [], "segurou menos de 2 s"

    solta_no_r2 = tv.Evento(3.0, uniq, tv.TIPO_SOLTA, tv.LADO_DIREITO, 1.0, None, 2.5)
    assert _onda_do_furtivo([solta_no_r2]) == [], "a Onda é da mira (L2), não do tiro (R2)"

    solta = tv.Evento(2.6, uniq, tv.TIPO_SOLTA, tv.LADO_ESQUERDO, 1.0, None, 2.1)
    escritas = _onda_do_furtivo([apertou, solta])
    assert escritas, "soltou depois de 2 s: a Onda toca"
    assert min(t for t, _f, _s in escritas) >= 2.6 - 1e-9, "e só depois de soltar"
    assert escritas[-1][1:] == (0, 0), "a Onda termina em silêncio"


def test_a_regra_da_soltura_e_so_do_furtivo_e_so_da_onda() -> None:
    assert pv.na_soltura_do_estilo("onda", "furtivo") == pv.NaSoltura(2.0, "esquerdo")
    assert pv.na_soltura_do_estilo("onda", "aventura") is None  # a Aventura segue tocando no aperto
    assert pv.na_soltura_do_estilo("batida", "furtivo") is None
    assert pv.na_soltura_do_estilo("onda", None) is None


# --- 6. A luz nova segue a regra ---------------------------------------------------------


def _perfil() -> Profile:
    """Luz fixa (sem efeito) e sem modo: quem anima é só a luz do estilo."""
    return Profile(name="regua", match=MatchAny(), leds=LedsConfig())


class _Barra:
    def __init__(self) -> None:
        self.escritos: list[tuple[float, str, tuple[int, int, int]]] = []
        self.soltos: list[str] = []
        self.relogio = 0.0

    def laco(self) -> luz.LuzAnimada:
        return luz.LuzAnimada(
            lambda u, c: self.escritos.append((self.relogio, u, c)), self.soltos.append)

    def de(self, uniq: str) -> list[tuple[float, tuple[int, int, int]]]:
        return [(t, c) for t, u, c in self.escritos if u == uniq]


class _Mesa:
    """Quatro controles: o curso do gatilho e a carga de cada um mudam pelo teste."""

    def __init__(self) -> None:
        self.l2 = dict.fromkeys(QUATRO, 0)
        self.r2 = dict.fromkeys(QUATRO, 0)
        self.carga: dict[str, tuple[int | None, str | None]] = dict.fromkeys(
            QUATRO, (80, "descarregando"))

    def daemon(self) -> Any:
        pad = SimpleNamespace(backend="uhid", visto_ha_s={}, game_open=False)

        def descrever() -> list[dict[str, Any]]:
            return [{"uniq": u, "battery_pct": p, "battery_state": s}
                    for u, (p, s) in self.carga.items()]

        controller = SimpleNamespace(
            primary_uniq=AZUL, repinturas_da_luz=0, describe_controllers=descrever,
            resolved_led_for=lambda uniq: COR_DE[uniq])
        jogadores = {
            u: SimpleNamespace(
                reader=SimpleNamespace(snapshot=lambda u=u: SimpleNamespace(
                    l2_raw=self.l2[u], r2_raw=self.r2[u])),
                vpad=pad, motion_reader=None)
            for u in QUATRO[1:]
        }
        daemon = SimpleNamespace(
            controller=controller, _gamepad_device=pad, display_authority="unknown",
            _coop_manager=SimpleNamespace(_players=jogadores),
            store=SimpleNamespace(active_profile="regua"))
        daemon._last_state = None  # trocado a cada tique, por `_girar`
        return daemon


def _passo_da_luz(
    monkeypatch: pytest.MonkeyPatch, mesa: _Mesa, estilo: str,
) -> tuple[luz.Passo, _Barra, Any]:
    barra = _Barra()
    daemon = mesa.daemon()
    monkeypatch.setattr(luz, "perfil_ativo", lambda _d: _perfil())
    monkeypatch.setattr(luz, "estilo_ativo", lambda _d: estilo)
    passo = luz.Passo(daemon, barra.laco())
    return passo, barra, daemon


def _girar(passo: luz.Passo, barra: _Barra, mesa: _Mesa, daemon: Any, desde: float,
           segundos: float, passo_s: float = 0.05) -> float:
    t = desde
    while t < desde + segundos - 1e-9:
        barra.relogio = t
        daemon._last_state = SimpleNamespace(l2_raw=mesa.l2[AZUL], r2_raw=mesa.r2[AZUL])
        passo(t)
        t += passo_s
    return t


def _brilho_do_quadro(quadro: tuple[int, int, int], cor: tuple[int, int, int]) -> float:
    canal = max(range(3), key=lambda i: cor[i])
    return quadro[canal] / cor[canal]


def _quadro(cor: tuple[int, int, int], brilho: float) -> tuple[int, int, int]:
    """O quadro que a barra recebe: a cor no brilho, pela mesma conta da luz fixa."""
    r, g, b = luz.cor_com_o_brilho(cor, brilho)
    return (r, g, b)


def test_o_acende_segue_o_curso_do_gatilho_na_cor_de_cada_um_dos_quatro(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Gatilho solto: a barra fica no piso; apertado, sobe até a cor cheia do controle.

    A cor de cada um é a dele (nunca a do vizinho) e só o controle que apertou sobe.
    """
    mesa = _Mesa()
    passo, barra, daemon = _passo_da_luz(monkeypatch, mesa, "corrida")
    t = _girar(passo, barra, mesa, daemon, 0.0, 0.5)
    for u in QUATRO:
        assert barra.de(u)[-1][1] == _quadro(COR_DE[u], el.PISO_DO_ACENDE), u
    for apertado in QUATRO:
        mesa.r2[apertado] = 255
        mesa.l2[apertado] = 0
        t = _girar(passo, barra, mesa, daemon, t, 1.0)
        for u in QUATRO:
            quadro = barra.de(u)[-1][1]
            esperado = 1.0 if u == apertado else el.PISO_DO_ACENDE
            assert quadro == _quadro(COR_DE[u], esperado), (apertado, u)
            # a cor é a do controle: o canal mais forte é o dele
            assert max(range(3), key=lambda i: quadro[i]) == max(
                range(3), key=lambda i: COR_DE[u][i])
        mesa.r2[apertado] = 0
        t = _girar(passo, barra, mesa, daemon, t, 1.0)


def _vaivens(brilhos: list[float]) -> int:
    """Quantas vezes o brilho vira de subida para descida (os picos)."""
    picos, subindo = 0, False
    for antes, depois in pairwise(brilhos):
        if depois > antes + 1e-9:
            subindo = True
        elif depois < antes - 1e-9 and subindo:
            picos += 1
            subindo = False
    return picos


def test_o_acende_nunca_passa_de_tres_vaivens_por_segundo_por_mais_que_o_dedo_bata() -> None:
    """D-2010-O-GOLPE-FALHA-E-O-ACENDE-TEM-TETO.

    O dedo bate o gatilho a cada tique de 60 Hz, por 10 s: no máximo 3 picos por segundo.

    MORDIDA: `MEIO_VAIVEM_DO_ACENDE_S = 0.0` (o brilho virando a cada tique) e isto reprova.
    """
    passo_s = 1.0 / 60.0
    for fase in (0, 1):  # o dedo começa apertando ou solto
        acende, brilhos = el.BrilhoDoAcende(float(fase)), []
        for tique in range(600):
            curso = 1.0 if (tique + fase) % 2 == 0 else 0.0
            brilhos.append(acende.andar(curso, tique * passo_s))
        assert _vaivens(brilhos) <= 3 * 10 + 1, _vaivens(brilhos)
        assert min(brilhos) >= el.PISO_DO_ACENDE - 1e-9 and max(brilhos) <= 1.0 + 1e-9
    assert pytest.approx(2 * (1 - el.PISO_DO_ACENDE) * 3) == el.TETO_DO_ACENDE_POR_S


def test_o_acende_segue_o_dedo_que_nao_bate_sem_atraso_de_virada() -> None:
    """Um aperto e uma soltura de verdade (meio segundo cada) vão do piso à cor cheia e voltam."""
    acende, t, brilhos = el.BrilhoDoAcende(0.0), 0.0, []
    for curso in (0.0, 1.0, 1.0, 0.0):
        for _ in range(30):
            brilhos.append(acende.andar(curso, t))
            t += 1.0 / 60.0
    assert max(brilhos) == pytest.approx(1.0)
    assert brilhos[-1] == pytest.approx(el.PISO_DO_ACENDE)
    assert _vaivens(brilhos) == 1


def test_o_acende_calado_na_economia_e_com_o_brilho_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa()
    passo, barra, daemon = _passo_da_luz(monkeypatch, mesa, "corrida")
    monkeypatch.setattr(luz, "economia_da_mesa", lambda: True)
    _girar(passo, barra, mesa, daemon, 0.0, 1.0)
    assert barra.escritos == [], "na Bateria longa a barra segue fixa, sem animar"


def _lampejos_por_segundo(brilhos: list[float], duracao_s: float) -> float:
    """Quantas vezes o brilho cruza o meio da faixa subindo, por segundo."""
    meio = (max(brilhos) + min(brilhos)) / 2
    return sum(1 for a, b in pairwise(brilhos) if a < meio <= b) / duracao_s


def test_a_bateria_so_respira_com_a_carga_baixa_e_fora_do_cabo(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Abaixo de 30% e descarregando: respira devagar, nunca pisca; senão a barra fica quieta.

    MORDIDAs: `ESTADOS_DE_CARGA_EM_DIA = frozenset()` (respira no cabo) e `"respirar"` trocado
    por `"piscar"` na luz da Bateria reprovam aqui.
    """
    mesa = _Mesa()
    passo, barra, daemon = _passo_da_luz(monkeypatch, mesa, "maratona")
    t = _girar(passo, barra, mesa, daemon, 0.0, 6.0, passo_s=0.1)
    assert barra.escritos == [], "com 80% a barra não anima (a luz fixa a 25% é do perfil)"

    mesa.carga[VERMELHO] = (20, "descarregando")
    mesa.carga[ROXO] = (20, "carregando")   # no cabo: a carga não acaba
    mesa.carga[BRANCO] = (100, "cheio")
    t0 = t
    t = _girar(passo, barra, mesa, daemon, t, 12.0, passo_s=0.1)
    assert barra.de(AZUL) == [] and barra.de(BRANCO) == [], "carga boa não respira"
    assert barra.de(ROXO) == [], "no cabo não respira"
    quadros = barra.de(VERMELHO)
    assert len(quadros) > 10, "a bateria baixa respira"
    assert all(max(range(3), key=lambda i: c[i]) == 0 for _t, c in quadros), "na cor do controle"
    brilhos = [_brilho_do_quadro(c, COR_DE[VERMELHO]) for _t, c in quadros]
    assert max(brilhos) - min(brilhos) > 0.3, "respira de verdade"
    assert _lampejos_por_segundo(brilhos, t - t0) <= el.TETO_DO_PISCAR_HZ
    assert _lampejos_por_segundo(brilhos, t - t0) < 1.0, "devagar: nunca pisca"
    # a curva é a do Respirar quadro a quadro: o Piscar no mesmo ritmo também fica abaixo de um
    # lampejo por segundo (0,6 Hz no ritmo 2), e só a forma o separa
    inicio = quadros[0][0]
    respirar = EfeitoDaLuz("respirar", (COR_DE[VERMELHO],), el.RITMO_DA_BATERIA)
    assert all(c == _quadro(el.cor_no_instante(respirar, t_ - inicio), 1.0)
               for t_, c in quadros), "a Bateria respira, nunca pisca"

    # o cabo entrou: a barra volta ao perfil
    mesa.carga[VERMELHO] = (20, "carregando")
    _girar(passo, barra, mesa, daemon, t, 6.0, passo_s=0.1)
    assert barra.soltos[-1:] == [VERMELHO], "no cabo, a barra volta ao perfil"


def test_nenhuma_luz_nova_passa_do_teto_de_lampejos() -> None:
    assert el.TETO_DO_PISCAR_HZ == 3.0
    receita_acende = ej.POR_CHAVE["corrida"].receita_invisivel
    receita_bateria = ej.POR_CHAVE["maratona"].receita_invisivel
    assert receita_acende is not None and receita_bateria is not None
    assert receita_acende.luz_por_segundo <= ej.TETO_DO_PISCAR
    assert receita_bateria.luz_por_segundo <= ej.TETO_DO_PISCAR
    assert el.RITMO_DA_BATERIA <= 2


def test_o_perfil_que_pede_luz_vence_a_do_estilo(monkeypatch: pytest.MonkeyPatch) -> None:
    """O jogo e o perfil mandam: o efeito que o perfil grava não é pisado pelo Acende."""
    mesa = _Mesa()
    passo, barra, daemon = _passo_da_luz(monkeypatch, mesa, "corrida")
    com_efeito = Profile(
        name="regua", match=MatchAny(), leds=LedsConfig(efeito="piscar;FF0000;2"))
    monkeypatch.setattr(luz, "perfil_ativo", lambda _d: com_efeito)
    mesa.r2[AZUL] = 255
    _girar(passo, barra, mesa, daemon, 0.0, 2.0)
    assert barra.escritos, "o efeito do perfil toca"
    assert all(c in ((255, 0, 0), (0, 0, 0)) or c[0] >= 0 for _t, _u, c in barra.escritos)
    assert all(c[1] == 0 and c[2] == 0 for _t, _u, c in barra.escritos), (
        "só o vermelho do perfil, nunca a cor do controle")


# --- 7. As três imersões novas na frente da lista ----------------------------------------


FRENTE_NOVA = {
    "golpe-falha": {"luta"},
    "golpe-aparo": {"souls"},
    "travar-esgotado": {"souls"},
}


@pytest.mark.parametrize(("chave", "estilos"), sorted(FRENTE_NOVA.items()))
def test_as_tres_imersoes_novas_estao_na_frente_do_estilo_que_a_pagina_pede(
        chave: str, estilos: set[str]) -> None:
    """Cada uma nasce com o nome «Família · variante» e na frente só do estilo da página.

    MORDIDA: tire a chave do `na_frente` e isto reprova.
    """
    imersao = next((i for i in ei.IMERSOES if i.chave == chave), None)
    assert imersao is not None, chave
    assert " · " in imersao.rotulo, imersao.rotulo
    assert set(imersao.na_frente) == estilos


def test_cada_estilo_segue_com_um_a_cinco_na_frente() -> None:
    for e in ej.DE_FABRICA:
        if e.chave in ("nativo", "adulto"):
            continue
        da_frente = [i.chave for i in ei.IMERSOES if e.chave in i.na_frente]
        assert 1 <= len(da_frente) <= 5, (e.chave, da_frente)


def test_o_golpe_falha_e_so_um_momento_que_o_jogo_apaga() -> None:
    """Afunda mole e cede no vazio por um instante; o `Off` é um momento, a parede não some.

    Onde o jogo escreve o gatilho, o jogo vence (decisão por delegação, a validar pelo usuário).
    """
    falha = next(i for i in ei.IMERSOES if i.chave == "golpe-falha")
    assert falha.momentos and falha.momentos[0].modo == "Off"
    assert falha.momentos[0].quando == "ao_apertar"
    assert ei.ajustes_da_imersao(falha, "Weapon") is not None


def test_as_tres_formas_novas_entram_na_lista_da_tela_no_bloco_b() -> None:
    """A tela é do bloco B (20/10/2026): o Eco, o Grão e o Motor de época entram em `ESCOLHAS`."""
    assert {fh.ECO, fh.GRAO, fh.MOTOR_DE_EPOCA} <= set(fh.ESCOLHAS)
    assert set(fh.CONTINUAS) == {fh.SOM_NO_CORPO, fh.GRAO, fh.MOTOR_DE_EPOCA}
