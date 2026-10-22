"""A luz reage ao que a mão faz (A-LUZ-REAGE-AO-QUE-A-MAO-FAZ-01, 22/10/2026).

Três efeitos novos, no grupo «Que reage» da lista da aba Iluminação:

- «Reage ao botão»: o símbolo apertado dá a cor (△ verde, ○ vermelho, ✕ azul, □ rosa; qualquer outro
  botão acende na cor escolhida) e a barra apaga devagar;
- «Inclinação»: a cor gira pela roda conforme o controle inclina, sem salto na volta;
- «Dedo no touchpad»: o dedo dá a cor (horizontal, o matiz; vertical, o brilho), e sem dedo fica a
  última.

Cada controle pinta pelo dado DELE: a mão do B nunca pinta a barra do A. A regra dos três clarões
por segundo (D-2210-A-LUZ-GANHA-ONDA-E-RELAMPAGO) vale para os três: dez apertos por segundo não
viram estrobo, e a roda de cores não gira mais depressa que uma volta por segundo.

MORDIDAS (22/10/2026): tirar o corte de ``SUBIDAS_DO_REAGE_POR_S`` do ``_apertar`` reprova o teto de
subidas; trocar ``VOLTAS_DO_MATIZ_POR_S`` por 100 reprova o freio da roda; trocar o ``atan2`` da
inclinação por um ângulo sem volta circular reprova o salto; ``self._vistos = None`` no
``andar`` (o primeiro tique não aprende os contadores) reprova o aperto antigo que acendia; o
``leitor_da_mao`` que lê sempre o controle primário reprova a posse por controle; tirar
``reage-ao-botao`` da tupla ``BASES_NOVAS_DA_LUZ`` reprova a lista e a leitura do perfil.
"""
from __future__ import annotations

import math
import pathlib
import re
import sys
from itertools import pairwise
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import luz_animada as luz
from hefesto_dualsense4unix.profiles import efeitos_de_luz as fx
from hefesto_dualsense4unix.profiles.schema import (
    BASES_NOVAS_DA_LUZ,
    TODAS_AS_BASES_DA_LUZ,
    EfeitoDaLuz,
    ler_o_efeito_da_luz,
)

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

MOCKUP = RAIZ / "mockup" / "04-iluminacao.html"
RGB = tuple[int, int, int]
BRANCO: RGB = (255, 255, 255)
LARANJA: RGB = (255, 128, 0)
#: Faixa forjada (`aa:bb:cc`), nunca endereço de aparelho de verdade.
JOGADORES = [f"aa:bb:cc:00:00:0{n}" for n in range(1, 5)]
PASSO_S = 1 / 60
SIMBOLOS = {"triangle": (0, 255, 0), "circle": (255, 0, 0), "cross": (0, 0, 255),
            "square": (255, 105, 180)}


def _canal_mais_alto(cor: RGB) -> float:
    return max(cor) / 255


def _subidas(brilhos: list[float], piso: float) -> list[float]:
    """Os instantes em que o brilho cruza o meio do passeio para cima (histerese de 10%)."""
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


def _mais_em_um_segundo(tempos: list[float]) -> int:
    mais = 0
    for i, inicio in enumerate(tempos):
        dentro = sum(1 for t in tempos[i:] if t - inicio < 1.0 - 1e-6)
        mais = max(mais, dentro)
    return mais


# ---------------------------------------------------------------- as bases existem no perfil


def test_as_tres_bases_novas_estao_fora_das_oito_que_se_criam_e_o_perfil_as_le() -> None:
    assert BASES_NOVAS_DA_LUZ == ("reage-ao-botao", "inclinacao", "dedo-no-touchpad")
    assert set(TODAS_AS_BASES_DA_LUZ) >= set(BASES_NOVAS_DA_LUZ)
    assert len(set(TODAS_AS_BASES_DA_LUZ)) == len(TODAS_AS_BASES_DA_LUZ) == 11
    assert ler_o_efeito_da_luz("reage-ao-botao;FF8000;5") == EfeitoDaLuz(
        "reage-ao-botao", ((255, 128, 0),), 5)
    assert ler_o_efeito_da_luz("inclinacao;;5") == EfeitoDaLuz("inclinacao", (), 5)
    assert ler_o_efeito_da_luz("dedo-no-touchpad;;5") == EfeitoDaLuz("dedo-no-touchpad", (), 5)
    assert ler_o_efeito_da_luz("reage-ao-botao;;5") is None, "leva a cor do botão sem símbolo"
    assert ler_o_efeito_da_luz("invento;FF0000;5") is None


# ---------------------------------------------------------------- «Reage ao botão»


def _aperta(estado: fx.ReageAoBotao, contagem: dict[str, int], agora: float) -> RGB:
    return estado.andar(fx.Entrada(apertos=dict(contagem)), agora)


@pytest.mark.parametrize(("botao", "cor"), list(SIMBOLOS.items()))
def test_o_simbolo_apertado_pinta_a_barra_na_cor_dele_e_ela_apaga_devagar(
        botao: str, cor: RGB) -> None:
    estado = fx.ReageAoBotao(LARANJA, 5)
    contagem: dict[str, int] = {}
    repouso = _aperta(estado, contagem, 0.0)
    assert repouso == fx._escalar(LARANJA, fx.PISO_DO_REAGE)
    contagem[botao] = 1
    _aperta(estado, contagem, 1.0)
    topo = _aperta(estado, contagem, 1.0 + fx.SUBIDA_DO_REAGE_S)
    assert topo == cor, f"{botao}: no topo a barra tem a cor cheia do símbolo"
    meio = _aperta(estado, contagem, 1.0 + fx.SUBIDA_DO_REAGE_S + fx.descida_do_reage_s(5) / 2)
    assert _canal_mais_alto(meio) < 1.0 and meio != repouso, f"{botao}: apaga devagar"
    fim = _aperta(estado, contagem, 10.0)
    assert fim == repouso, "e volta para a cor escolhida, no piso"
    assert fim != (0, 0, 0)


def test_outro_botao_acende_na_cor_escolhida_do_efeito() -> None:
    estado = fx.ReageAoBotao(LARANJA, 5)
    _aperta(estado, {"l1": 0}, 0.0)
    _aperta(estado, {"l1": 1}, 1.0)
    cor = _aperta(estado, {"l1": 1}, 1.0 + fx.SUBIDA_DO_REAGE_S)
    assert cor == LARANJA


def test_o_primeiro_tique_so_aprende_os_contadores() -> None:
    """O que já foi apertado antes de o efeito ligar não acende a barra."""
    estado = fx.ReageAoBotao(LARANJA, 5)
    cor = _aperta(estado, {"triangle": 40, "cross": 9}, 0.0)
    assert cor == fx._escalar(LARANJA, fx.PISO_DO_REAGE)
    cor = _aperta(estado, {"triangle": 40, "cross": 9}, 0.5)
    assert cor == fx._escalar(LARANJA, fx.PISO_DO_REAGE)


def test_sem_dado_dos_apertos_a_barra_fica_na_cor_escolhida() -> None:
    estado = fx.ReageAoBotao(LARANJA, 5)
    for i in range(10):
        assert estado.andar(fx.Entrada(), i * 0.1) == fx._escalar(LARANJA, fx.PISO_DO_REAGE)


@pytest.mark.parametrize("apertos_por_segundo", [4, 10, 30])
def test_apertos_rapidos_nao_passam_de_tres_subidas_por_segundo(apertos_por_segundo: int) -> None:
    # D-2210-A-LUZ-GANHA-ONDA-E-RELAMPAGO
    estado = fx.ReageAoBotao(LARANJA, 10)
    contagem = {"cross": 0, "circle": 0}
    brilhos: list[float] = []
    n = int(8.0 / PASSO_S)
    proximo = 0.0
    for i in range(n):
        t = i * PASSO_S
        if t >= proximo and t > 0.5:
            alvo = "cross" if int(t * apertos_por_segundo) % 2 else "circle"
            contagem[alvo] += 1
            proximo += 1.0 / apertos_por_segundo
        brilhos.append(_canal_mais_alto(_aperta(estado, contagem, t)))
    assert min(brilhos) > 0.0, "a luz nunca apaga"
    subidas = _subidas(brilhos, fx.PISO_DO_REAGE)
    assert subidas, "a varredura viu o aperto acender"
    assert _mais_em_um_segundo(subidas) <= 3


def test_a_borda_do_aperto_e_suave_e_o_brilho_nunca_pula() -> None:
    estado = fx.ReageAoBotao((255, 0, 0), 10)
    contagem = {"cross": 0}
    vistos: list[RGB] = []
    for i in range(int(3.0 / PASSO_S)):
        t = i * PASSO_S
        if i == 30:
            contagem["cross"] = 1
        vistos.append(_aperta(estado, contagem, t))
    saltos = [abs(b[2] - a[2]) + abs(b[0] - a[0]) for a, b in pairwise(vistos)]
    assert max(saltos) < 255 * 0.7, "nenhum quadro vai do piso ao cheio de uma vez"


# ---------------------------------------------------------------- «Inclinação»


def _gravidade(angulo: float) -> tuple[float, float, float]:
    """A gravidade (1 g) no plano x-z para um ângulo de rolagem (0 = o controle deitado)."""
    return (math.sin(angulo), 0.0, math.cos(angulo))


def _matiz(cor: RGB) -> float:
    import colorsys

    return colorsys.rgb_to_hsv(*(c / 255 for c in cor))[0]


def test_a_inclinacao_da_matiz_continuo_e_a_cor_muda_quando_o_controle_inclina() -> None:
    estado = fx.Inclinacao(10)
    cores: list[RGB] = []
    for i in range(int(2.0 / PASSO_S)):
        cores.append(estado.andar(fx.Entrada(gravidade=_gravidade(0.0)), i * PASSO_S))
    parada = cores[-1]
    assert len(set(cores)) == 1, "parado não muda"
    for i in range(int(2.0 / PASSO_S)):
        t = 2.0 + i * PASSO_S
        cores.append(estado.andar(fx.Entrada(gravidade=_gravidade(math.pi / 2)), t))
    assert cores[-1] != parada, "inclinar muda a cor"
    assert _matiz(cores[-1]) == pytest.approx(0.25, abs=0.02), "um quarto de volta, um quarto"


def test_a_inclinacao_nao_salta_quando_passa_da_volta() -> None:
    """Uma volta inteira devagar, e depois outra: o matiz anda sempre pelo caminho curto."""
    estado = fx.Inclinacao(10)
    matizes: list[float] = []
    voltas = 2.0
    n = int(8.0 / PASSO_S)
    for i in range(n):
        t = i * PASSO_S
        angulo = 2 * math.pi * voltas * i / n
        matizes.append(_matiz(estado.andar(fx.Entrada(gravidade=_gravidade(angulo)), t)))
        if i > 30:  # passada a partida, a cor acompanha o ângulo (com o atraso do alisamento)
            erro = abs((matizes[-1] - (angulo / (2 * math.pi)) % 1.0 + 0.5) % 1.0 - 0.5)
            assert erro < 0.05, f"quadro {i}: a cor se perdeu da inclinação ({erro:.3f})"
    for a, b in pairwise(matizes):
        passo = abs((b - a + 0.5) % 1.0 - 0.5)
        assert passo < 0.03, f"o matiz saltou de {a:.3f} para {b:.3f}"


def test_a_roda_de_cores_nao_gira_mais_depressa_que_o_freio() -> None:
    estado = fx.Inclinacao(10)
    estado.andar(fx.Entrada(gravidade=_gravidade(0.0)), 0.0)
    antes = _matiz(estado.andar(fx.Entrada(gravidade=_gravidade(0.0)), PASSO_S))
    # o controle vira um quarto de volta num quadro: o alisamento sozinho andaria ~0,06 de roda
    # (3,5 vezes o freio); a roda anda só o que o freio deixa
    depois = _matiz(estado.andar(fx.Entrada(gravidade=_gravidade(math.pi / 2)), 2 * PASSO_S))
    passo = abs((depois - antes + 0.5) % 1.0 - 0.5)
    assert 0 < passo <= 1.0 * PASSO_S + 0.002  # uma volta por segundo, escrito aqui de propósito


def test_sem_leitura_a_inclinacao_fica_branca_e_depois_fica_a_ultima() -> None:
    estado = fx.Inclinacao(5)
    assert estado.andar(fx.Entrada(), 0.0) == BRANCO
    cor = estado.andar(fx.Entrada(gravidade=_gravidade(1.0)), 0.1)
    assert cor != BRANCO
    assert estado.andar(fx.Entrada(), 0.2) == cor, "sem dado, a cor de antes"
    # gravidade quase nula é leitura solta, não direção
    assert estado.andar(fx.Entrada(gravidade=(0.01, 0.0, 0.02)), 0.3) == cor


# ---------------------------------------------------------------- «Dedo no touchpad»


def test_o_dedo_da_a_cor_pela_posicao_horizontal_e_o_brilho_pela_vertical() -> None:
    estado = fx.DedoNoTouchpad()
    esquerda = estado.andar(fx.Entrada(dedo=(0.0, 0.0)), 0.0)
    assert esquerda == (255, 0, 0), "à esquerda e em cima: vermelho cheio"
    for i in range(1, 120):
        direita = estado.andar(fx.Entrada(dedo=(1.0, 0.0)), i * PASSO_S)
    assert _matiz(direita) == pytest.approx(fx.VOLTA_DO_TOQUE, abs=0.01)
    assert _matiz(direita) != pytest.approx(_matiz(esquerda), abs=0.1), "as pontas não se encontram"
    t0 = 120 * PASSO_S
    embaixo = estado.andar(fx.Entrada(dedo=(1.0, 1.0)), t0)
    for i in range(1, 240):
        embaixo = estado.andar(fx.Entrada(dedo=(1.0, 1.0)), t0 + i * PASSO_S)
    assert _canal_mais_alto(embaixo) == pytest.approx(fx.PISO_DO_ACENDE, abs=0.01)
    assert embaixo != (0, 0, 0), "embaixo é o piso, nunca o apagado"


def test_sem_dedo_fica_a_ultima_cor() -> None:
    estado = fx.DedoNoTouchpad()
    assert estado.andar(fx.Entrada(), 0.0) == BRANCO
    cor = estado.andar(fx.Entrada(dedo=(0.5, 0.0)), 0.1)
    assert cor != BRANCO
    assert estado.andar(fx.Entrada(dedo=None), 0.2) == cor
    assert estado.andar(fx.Entrada(), 5.0) == cor


def test_o_dedo_balancando_na_vertical_nao_passa_de_tres_vaivens_por_segundo() -> None:
    # D-2210-A-LUZ-GANHA-ONDA-E-RELAMPAGO
    estado = fx.DedoNoTouchpad()
    brilhos: list[float] = []
    for i in range(int(8.0 / PASSO_S)):
        t = i * PASSO_S
        y = 0.0 if int(t * 20) % 2 == 0 else 1.0  # 10 vaivéns por segundo
        brilhos.append(_canal_mais_alto(estado.andar(fx.Entrada(dedo=(0.0, y)), t)))
    assert min(brilhos) >= fx.PISO_DO_ACENDE - 1e-6
    subidas = _subidas(brilhos, fx.PISO_DO_ACENDE)
    assert _mais_em_um_segundo(subidas) <= 3


# ---------------------------------------------------------------- o laço real, controle a controle


def _laco(mao: Any) -> tuple[luz.LuzAnimada, dict[str, list[RGB]]]:
    saiu: dict[str, list[RGB]] = {u: [] for u in JOGADORES}
    return luz.LuzAnimada(lambda u, cor: saiu[u].append(cor), lambda u: None, mao=mao), saiu


def _plano(texto: str, quantos: int = 4) -> dict[str, luz.PlanoDoControle]:
    efeito = ler_o_efeito_da_luz(texto)
    assert efeito is not None, texto
    return {u: luz.PlanoDoControle(efeito, 1.0, p, p + 1)
            for p, u in enumerate(JOGADORES[:quantos])}


def test_o_controle_a_nao_pinta_pela_mao_do_b() -> None:
    contagens = {u: {"cross": 0} for u in JOGADORES}

    def mao(uniq: str, base: str) -> fx.Entrada:
        return fx.Entrada(apertos=dict(contagens[uniq]))

    laco, saiu = _laco(mao)
    plano = _plano("reage-ao-botao;FF8000;5")
    for i in range(30):
        laco.tique(100.0 + i / 60, plano)
    contagens[JOGADORES[1]]["cross"] = 1  # só o segundo controle aperta ✕
    for i in range(30, 60):
        laco.tique(100.0 + i / 60, plano)
    assert any(c[2] > c[0] for c in saiu[JOGADORES[1]]), "o B acendeu azul"
    for outro in (JOGADORES[0], JOGADORES[2], JOGADORES[3]):
        assert not any(c[2] > c[0] for c in saiu[outro]), f"{outro} pintou pela mão do B"


def test_o_laco_anima_a_inclinacao_e_o_dedo_nos_quatro_controles_a_30_quadros_por_segundo() -> None:
    for base in ("inclinacao", "dedo-no-touchpad"):
        texto = f"{base};;5"
        def mao(uniq: str, base_pedida: str, _base: str = base) -> fx.Entrada:
            n = JOGADORES.index(uniq)
            assert base_pedida == _base
            return fx.Entrada(gravidade=_gravidade(0.8 * n), dedo=(0.2 * n + 0.1, 0.0))

        laco, saiu = _laco(mao)
        plano = _plano(texto)
        for i in range(4 * 60):
            laco.tique(100.0 + i / 60, plano)
        cores = {u: saiu[u][-1] for u in JOGADORES}
        assert len(set(cores.values())) == 4, f"{base}: cada controle com a cor do seu dado"
        for u in JOGADORES:
            assert len(saiu[u]) <= luz.QUADROS_POR_SEGUNDO_MAXIMO * 4 + 1
            assert (0, 0, 0) not in saiu[u]


def test_trocar_o_efeito_do_controle_recomeca_o_estado() -> None:
    contagem = {"cross": 0}
    laco, saiu = _laco(lambda u, b: fx.Entrada(apertos=dict(contagem)))
    plano = {JOGADORES[0]: _plano("reage-ao-botao;FF8000;5")[JOGADORES[0]]}
    for i in range(10):
        laco.tique(100.0 + i / 60, plano)
    contagem["cross"] = 1
    outro = {JOGADORES[0]: _plano("reage-ao-botao;00FFFF;5")[JOGADORES[0]]}
    antes = len(saiu[JOGADORES[0]])
    for i in range(10, 20):
        laco.tique(100.0 + i / 60, outro)
    depois = saiu[JOGADORES[0]][antes:]
    assert depois, "o efeito novo pintou"
    assert all(b <= g for _, g, b in depois), "estado novo: o aperto velho não acende o azul do ✕"


# ---------------------------------------------------------------- o leitor de produção


class _Leitor:
    def __init__(self, apertos: dict[str, int]) -> None:
        self._apertos = apertos

    def snapshot(self) -> Any:
        return SimpleNamespace(apertos=dict(self._apertos))


class _Hub:
    def __init__(self) -> None:
        self.pediu: list[tuple[str, str]] = []

    def aceleracao_do_movimento(self, uniq: str) -> tuple[float, float, float]:
        self.pediu.append(("accel", uniq))
        return (0.5, 0.0, 0.8)

    def toque_da_peca(self, uniq: str) -> tuple[Any, bool]:
        self.pediu.append(("toque", uniq))
        return SimpleNamespace(touching=True, x=960, y=540, largura=1920, altura=1080), False


def _daemon() -> Any:
    hub = _Hub()
    coop = SimpleNamespace(_players={
        JOGADORES[1]: SimpleNamespace(reader=_Leitor({"cross": 7})),
        JOGADORES[2]: SimpleNamespace(reader=_Leitor({"cross": 3})),
    })
    controller = SimpleNamespace(primary_uniq=JOGADORES[0], _evdev=_Leitor({"cross": 1}))
    return SimpleNamespace(controller=controller, _coop_manager=coop,
                           _garantir_sensor_hub=lambda: hub), hub


def test_o_leitor_de_producao_le_os_apertos_do_proprio_controle() -> None:
    daemon, hub = _daemon()
    ler = luz.leitor_da_mao(daemon)
    assert ler(JOGADORES[0], "reage-ao-botao").apertos == {"cross": 1}
    assert ler(JOGADORES[1], "reage-ao-botao").apertos == {"cross": 7}
    assert ler(JOGADORES[2], "reage-ao-botao").apertos == {"cross": 3}
    assert ler(JOGADORES[3], "reage-ao-botao").apertos is None, "controle sem leitor: sem dado"
    assert hub.pediu == [], "os apertos não pedem sensor nenhum"


def test_o_controle_sem_co_op_le_os_apertos_pelo_leitor_passivo_do_hub() -> None:
    daemon, _ = _daemon()
    daemon._sensor_hub = SimpleNamespace(
        apertos=lambda uniq: {"circle": 2} if uniq == JOGADORES[3] else None)
    ler = luz.leitor_da_mao(daemon)
    assert ler(JOGADORES[3], "reage-ao-botao").apertos == {"circle": 2}
    assert ler(JOGADORES[1], "reage-ao-botao").apertos == {"cross": 7}, "o co-op segue o dele"


def test_o_leitor_de_producao_so_pede_o_sensor_que_a_base_usa() -> None:
    daemon, hub = _daemon()
    ler = luz.leitor_da_mao(daemon)
    inclinado = ler(JOGADORES[1], "inclinacao")
    assert inclinado.gravidade == (0.5, 0.0, 0.8) and inclinado.dedo is None
    assert hub.pediu == [("accel", JOGADORES[1])]
    dedo = ler(JOGADORES[2], "dedo-no-touchpad")
    assert dedo.dedo == (0.5, 0.5) and dedo.gravidade is None
    assert hub.pediu == [("accel", JOGADORES[1]), ("toque", JOGADORES[2])]


def test_o_leitor_de_producao_nunca_levanta() -> None:
    class _Quebrado:
        controller = SimpleNamespace(primary_uniq=JOGADORES[0],
                                     _evdev=SimpleNamespace(snapshot=lambda: 1 / 0))

        def _garantir_sensor_hub(self) -> Any:
            raise RuntimeError("sem hub")

    ler = luz.leitor_da_mao(_Quebrado())
    for base in BASES_NOVAS_DA_LUZ:
        assert ler(JOGADORES[0], base) == fx.Entrada()


# ---------------------------------------------------------------- a tela


def _doc() -> str:
    bruto = MOCKUP.read_text(encoding="utf-8")
    sem_comentario = re.sub(r"<!--.*?-->", "", bruto, flags=re.S)
    return re.sub(r"<(style|script)\b[^>]*>.*?</\1>", "", sem_comentario, flags=re.S)


def _opcoes(lista: str) -> list[tuple[str, str]]:
    return re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)</option>', lista)


def test_o_grupo_que_reage_esta_nas_quatro_listas_do_desenho_e_o_leiaute_nao_mudou() -> None:
    doc = _doc()
    listas = re.findall(r'<select class="g4-efeito".*?</select>', doc, flags=re.S)
    assert len(listas) == 4
    for lista in listas:
        grupo = lista.split('<optgroup label="Que reage">', 1)[1].split("</optgroup>", 1)[0]
        assert _opcoes(grupo)[:3] == [
            ("base:reage-ao-botao", "Reage ao botão"), ("base:inclinacao", "Inclinação"),
            ("base:dedo-no-touchpad", "Dedo no touchpad")]
    assert doc.count('class="g4-efeito"') == 4, "uma lista por controle, nada a mais na tela"
    criar = doc.split('<div class="quadro criar"', 1)[1]
    jeito = criar.split('class="seg-criar"', 1)[1].split('class="g4-cores"', 1)[0]
    assert re.findall(r'<input type="radio" name="base-criar" value="([^"]+)"', jeito) == [
        "respirar", "piscar", "arco-iris", "onda", "relampago"], "o «Jeito» não ganhou nada"


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


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_escolher_cada_base_nova_grava_o_texto_certo_e_a_lista_a_reconhece(n: int) -> None:
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_computador
    from pacotes import a04_iluminacao as a04

    uniq = JOGADORES[n - 1]
    chave = uniq.replace(":", "")
    cor = a04.pacote(_ctx(n))["colunas"][uniq]["hex"].lstrip("#").upper()
    esperado = {"reage-ao-botao": f"reage-ao-botao;{cor};5", "inclinacao": "inclinacao;;5",
                "dedo-no-touchpad": "dedo-no-touchpad;;5"}
    for base, texto in esperado.items():
        _gesto("efeito-da-luz")(_ctx(n), {"uniq": uniq, "valor": f"base:{base}"}, None)
        guardado = o_computador().controles[chave].leds.efeito
        assert guardado == texto, guardado
        assert ler_o_efeito_da_luz(guardado) is not None
        coluna = a04.pacote(_ctx(n))["colunas"][uniq]
        assert coluna[a04.CAMPO_DO_EFEITO] == f"base:{base}", "a lista volta na opção escolhida"
        assert coluna[a04.CAMPO_DA_DICA_DO_EFEITO] == a04.DICA_DA_BASE[base]


def test_trocar_a_cor_leva_o_reage_ao_botao_junto_e_nao_mexe_nas_que_nao_levam_cor() -> None:
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_computador
    from pacotes import a04_iluminacao as a04

    class _Ponte:
        def led_set_detalhado(self, *_a: Any, **_k: Any) -> dict[str, Any]:
            return {"aplicado_em": [JOGADORES[0]], "guardado_em": []}

    uniq, chave = JOGADORES[0], "aabbcc000001"
    for base, depois in (("reage-ao-botao", "reage-ao-botao;FF8000;5"),
                         ("inclinacao", "inclinacao;;5"),
                         ("dedo-no-touchpad", "dedo-no-touchpad;;5")):
        _gesto("efeito-da-luz")(_ctx(), {"uniq": uniq, "valor": f"base:{base}"}, None)
        a04.cor(_ctx(), {"uniq": uniq, "hex": "FF8000"}, _Ponte())
        assert o_computador().controles[chave].leds.efeito == depois, base


@pytest.mark.parametrize("base", BASES_NOVAS_DA_LUZ)
def test_o_criar_efeitos_novos_recusa_as_que_leem_a_mao(base: str) -> None:
    """Elas dependem de um dado vivo do controle: ficam só na lista, nunca no «Criar»."""
    import pacotes

    ctx = pacotes.Contexto(state={"active_profile": ""}, mesa=[], conectados=[], estados={})
    with pytest.raises(RuntimeError, match="Escolha como a luz se move"):
        pacotes.gesto_da_pagina("04-iluminacao.html", "criar-efeito")(
            ctx, {"forma": {"base": base, "cores": "#ff0000", "ritmo": "5", "nome": "X"}}, None)


def test_a_dica_de_cada_base_nova_cabe_na_coluna_e_comeca_maiuscula() -> None:
    from pacotes import a04_iluminacao as a04

    for base in BASES_NOVAS_DA_LUZ:
        frase = a04.DICA_DA_BASE[base]
        assert frase[0].isupper() and frase.endswith(".") and len(frase) <= 36, frase
        assert a04.ROTULO_DA_BASE[base] and a04.RITMO_DA_BASE[base] == 5
