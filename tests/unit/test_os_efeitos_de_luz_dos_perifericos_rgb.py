"""Os efeitos de luz dos periféricos RGB chegam ao controle.

A sprint é a OS-EFEITOS-DE-LUZ-DOS-PERIFERICOS-RGB-01 (22/10/2026).

Quatro bases novas, dos modos dos teclados e mouses Redragon que cabem no controle: a Ondulação (o
aperto corre pelas luzinhas a partir do lado do botão), o Vaivém (a crista vai e volta), o Enche (as
luzinhas acendem uma a uma) e o Respira em cores (cada respiração numa cor, os quatro lugares sempre
em cores diferentes). As três primeiras levam as luzinhas no quadro único; nenhuma toca o LED do
mic.
Todas herdam a regra das três subidas por segundo (contando a volta do número do jogador), o piso da
barra e o teto de 30 quadros por segundo.

MORDIDAS (22/10/2026): o passo do Enche a 0,04 s reprova (a 0,1 s passa); piso zero no Vaivém
reprova; tirar a janela das três subidas da Ondulação reprova; apagar a luzinha que o anel já passou
reprova a contagem do P4; tirar a ``ondulacao`` do ``if`` dos apertos no ``leitor_da_mao`` reprova;
tirar o quarto de volta do Respira em cores reprova; trocar a cor no topo da respiração reprova.
"""
from __future__ import annotations

import os
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
    BASES_DA_LUZ,
    BASES_DOS_PERIFERICOS_DA_LUZ,
    BASES_SEM_COR_DA_LUZ,
    TODAS_AS_BASES_DA_LUZ,
    EfeitoDaLuz,
    ler_o_efeito_da_luz,
)

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

RGB = tuple[int, int, int]
Luzinhas = tuple[bool, bool, bool, bool, bool]
JOGADORES = [f"aa:bb:cc:00:00:0{n}" for n in range(1, 5)]
NUMEROS: list[Luzinhas] = [
    (False, False, True, False, False),
    (False, True, False, True, False),
    (True, False, True, False, True),
    (True, True, False, True, True),
]
PASSO_S = 1 / 60
SEGUNDOS = 10.0
RITMOS = range(1, 11)
POSICOES = range(4)
VERMELHO: RGB = (255, 0, 0)


def _efeito(texto: str) -> EfeitoDaLuz:
    efeito = ler_o_efeito_da_luz(texto)
    assert efeito is not None, texto
    return efeito


def _subidas_num_segundo(tempos: list[float]) -> int:
    """O maior número de subidas em qualquer janela de 1 s (meio aberto)."""
    mais = 0
    for i, inicio in enumerate(tempos):
        mais = max(mais, sum(1 for t in tempos[i:] if t - inicio < 1.0 - 1e-6))
    return mais


def _quando_a_barra_sobe(brilhos: list[float], piso: float) -> list[float]:
    """Os instantes em que o brilho cruza o meio do passeio para cima (com histerese de 10%),
    como no ``test_a_luz_animada_ganha_a_lista_boa._quando_sobe``."""
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


def _quando_a_luzinha_sobe(vistos: list[Luzinhas], led: int) -> list[float]:
    return [i * PASSO_S for i in range(1, len(vistos)) if vistos[i][led] and not vistos[i - 1][led]]


def _brilho(cor: RGB) -> float:
    return max(cor) / 255


def test_as_quatro_bases_novas_entram_so_na_lista() -> None:
    """Prova da D-2210-OS-EFEITOS-DE-LUZ-DOS-PERIFERICOS-RGB."""
    assert BASES_DOS_PERIFERICOS_DA_LUZ == ("ondulacao", "vaivem", "enche", "respira-em-cores")
    assert set(BASES_DOS_PERIFERICOS_DA_LUZ) <= set(TODAS_AS_BASES_DA_LUZ)
    assert not set(BASES_DOS_PERIFERICOS_DA_LUZ) & set(BASES_DA_LUZ), "«Criar efeitos» não muda"
    assert len(set(TODAS_AS_BASES_DA_LUZ)) == len(TODAS_AS_BASES_DA_LUZ)
    assert {"ondulacao", "vaivem", "enche"} <= fx.BASES_COM_LUZINHAS
    assert "respira-em-cores" not in fx.BASES_COM_LUZINHAS
    assert "ondulacao" in fx.BASES_DE_DADO_VIVO
    assert not {"vaivem", "enche", "respira-em-cores"} & fx.BASES_DE_DADO_VIVO, "função do tempo"
    assert "respira-em-cores" in fx.BASES_DO_RELOGIO_COMUM
    assert "respira-em-cores" in BASES_SEM_COR_DA_LUZ


@pytest.mark.parametrize("texto", [
    "ondulacao;FF0000;5", "vaivem;FF0000;5", "enche;00FF00,0000FF;5", "respira-em-cores;;2"])
def test_o_texto_de_cada_uma_passa_na_leitura_do_perfil(texto: str) -> None:
    assert _efeito(texto).base == texto.split(";")[0]


def test_a_que_nao_tem_cor_exige_cor_e_a_sem_cor_nasce_sem() -> None:
    assert ler_o_efeito_da_luz("vaivem;;5") is None, "o Vaivém tem a cor do controle"
    assert ler_o_efeito_da_luz("respira-em-cores;;2") is not None


def _o_que_as_luzinhas_mostram(efeito: EfeitoDaLuz, numero: Luzinhas) -> list[Luzinhas]:
    vistos = []
    for i in range(int(SEGUNDOS / PASSO_S)):
        acesas = fx.luzinhas_no_instante(efeito, i * PASSO_S)
        vistos.append(numero if acesas is None else acesas)
    return vistos


@pytest.mark.parametrize("base", ["vaivem", "enche"])
@pytest.mark.parametrize("ritmo", RITMOS)
@pytest.mark.parametrize("jogador", range(4))
def test_nenhuma_luzinha_sobe_mais_de_tres_vezes_por_segundo_contando_o_numero(
    base: str, ritmo: int, jogador: int
) -> None:
    vistos = _o_que_as_luzinhas_mostram(_efeito(f"{base};FF0000;{ritmo}"), NUMEROS[jogador])
    for led in range(5):
        subidas = _quando_a_luzinha_sobe(vistos, led)
        assert _subidas_num_segundo(subidas) <= 3, f"P{jogador + 1}, ritmo {ritmo}, luzinha {led}"


@pytest.mark.parametrize(("base", "piso"), [
    ("vaivem", fx.PISO_DA_ONDA), ("enche", fx.PISO_DA_ONDA),
    ("respira-em-cores", fx.PISO_DO_RESPIRAR)])
@pytest.mark.parametrize("ritmo", RITMOS)
@pytest.mark.parametrize("posicao", POSICOES)
def test_nenhuma_barra_sobe_mais_de_tres_vezes_por_segundo(
    base: str, piso: float, ritmo: int, posicao: int
) -> None:
    cor = "" if base == "respira-em-cores" else "FF0000"
    efeito = _efeito(f"{base};{cor};{ritmo}")
    brilhos = [_brilho(fx.cor_no_instante(efeito, i * PASSO_S, posicao))
               for i in range(int(SEGUNDOS / PASSO_S))]
    subidas = _quando_a_barra_sobe(brilhos, piso)
    assert subidas, f"{base}, ritmo {ritmo}: a barra nunca subiu em 10 s"
    assert _subidas_num_segundo(subidas) <= 3, f"{base}, ritmo {ritmo}, lugar {posicao}"


@pytest.mark.parametrize(("base", "piso"), [
    ("vaivem", fx.PISO_DA_ONDA), ("enche", fx.PISO_DA_ONDA),
    ("respira-em-cores", fx.PISO_DO_RESPIRAR)])
@pytest.mark.parametrize("ritmo", RITMOS)
def test_a_barra_nunca_fica_abaixo_do_piso(base: str, piso: float, ritmo: int) -> None:
    cor = "" if base == "respira-em-cores" else "FF0000"
    efeito = _efeito(f"{base};{cor};{ritmo}")
    for posicao in POSICOES:
        for i in range(int(SEGUNDOS / PASSO_S)):
            brilho = _brilho(fx.cor_no_instante(efeito, i * PASSO_S, posicao))
            assert brilho >= piso - 1 / 255, f"{base}, ritmo {ritmo}, t={i * PASSO_S:.2f}: {brilho}"


@pytest.mark.parametrize("ritmo", RITMOS)
def test_o_vaivem_vai_da_luzinha_0_a_4_e_volta_e_o_numero_volta_entre_as_idas(ritmo: int) -> None:
    periodo = fx.periodo_do_vaivem_s(ritmo)
    assert 2.0 - 1e-9 <= periodo <= 8.0 + 1e-9
    assert fx.periodo_do_vaivem_s(1) == pytest.approx(8.0)
    assert fx.periodo_do_vaivem_s(10) == pytest.approx(2.0)
    primeira: list[float | None] = [None] * 5
    ultima: list[float | None] = [None] * 5
    no_numero = 0
    for i in range(int(periodo / PASSO_S)):
        t = i * PASSO_S
        acesas = fx.luzinhas_no_instante(_efeito(f"vaivem;FF0000;{ritmo}"), t)
        if acesas is None:
            no_numero += 1
            assert fx.brilho_do_vaivem(t, periodo) == pytest.approx(fx.PISO_DA_ONDA)
            continue
        for led, acesa in enumerate(acesas):
            if acesa:
                primeira[led] = t if primeira[led] is None else primeira[led]
                ultima[led] = t
    assert no_numero > 0, "o número volta entre uma ida e volta e a seguinte"
    idas = [t for t in primeira if t is not None]
    voltas = [t for t in ultima if t is not None]
    assert len(idas) == 5 and idas == sorted(idas), f"a ida acende da 0 à 4: {idas}"
    assert voltas == sorted(voltas, reverse=True), f"a volta apaga da 4 à 0: {voltas}"


@pytest.mark.parametrize("ritmo", RITMOS)
def test_o_enche_acende_uma_por_passo_fica_cheio_e_devolve_o_numero(ritmo: int) -> None:
    passo = fx.passo_do_enche_s(ritmo)
    efeito = _efeito(f"enche;FF0000;{ritmo}")
    vistos = [fx.luzinhas_no_instante(efeito, (k + 0.5) * passo) for k in range(fx.PASSOS_DO_ENCHE)]
    assert vistos == [
        (True, False, False, False, False), (True, True, False, False, False),
        (True, True, True, False, False), (True, True, True, True, False),
        (True, True, True, True, True), (True, True, True, True, True), None]
    assert fx.PASSOS_DO_ENCHE * passo >= 2.8 - 1e-9, "o ciclo mais curto é de 2,8 s"
    meio_do_cheio = fx.brilho_do_enche(5.5 * passo, passo)
    assert meio_do_cheio == pytest.approx(1.0), "as cinco acesas: a barra cheia"
    assert fx.brilho_do_enche(6.99 * passo, passo) == pytest.approx(fx.PISO_DA_ONDA, abs=0.02)
    degraus = {round(fx.brilho_do_enche(i * passo / 50, passo) * 16, 9) for i in range(350)}
    assert all(d == int(d) or d == pytest.approx(fx.PISO_DA_ONDA * 16) for d in degraus), degraus


def _apertos(**contagem: int) -> fx.Entrada:
    return fx.Entrada(apertos=contagem)


def test_o_anel_parte_do_lado_do_botao_e_o_quarto_aperto_nao_ondula() -> None:
    anel = fx.Ondulacao(VERMELHO, 5)
    contagem: dict[str, int] = {}
    assert anel.quadro(fx.Entrada(apertos={}), 0.0).luzinhas is None, "o primeiro tique só aprende"

    def apertar(nome: str, agora: float) -> Luzinhas | None:
        contagem[nome] = contagem.get(nome, 0) + 1
        return anel.quadro(fx.Entrada(apertos=dict(contagem)), agora).luzinhas

    assert fx.passo_da_ondulacao_s(5) == pytest.approx(0.11)
    assert apertar("cross", 1.0) == (False, False, False, False, True), "o ✕ parte da 4"
    assert apertar("dpad_left", 1.15) == (True, False, False, False, False), "a seta parte da 0"
    assert apertar("ps", 1.30) == (False, False, True, False, False), "o PS parte do meio"
    assert apertar("cross", 1.45) == (False, True, True, True, False), "o quarto não ondula"
    assert apertar("cross", 1.60) == (True, True, True, True, True), "nem o quinto"
    assert apertar("square", 1.75) is None, "nem o sexto: o anel do PS fechou e o número voltou"
    assert apertar("cross", 2.05) == (False, False, False, False, True), "passou 1 s: ondula"


@pytest.mark.parametrize(("nome", "origem"), [
    ("cross", 4), ("r2_btn", 4), ("options", 4), ("dpad_left", 0), ("l1", 0), ("create", 0),
    ("ps", 2)])
@pytest.mark.parametrize("ritmo", [1, 5, 10])
def test_as_acesas_ficam_ate_as_cinco_e_entao_volta_o_numero(
    nome: str, origem: int, ritmo: int
) -> None:
    anel = fx.Ondulacao(VERMELHO, ritmo)
    anel.quadro(fx.Entrada(apertos={}), 0.0)
    vistos = [anel.quadro(fx.Entrada(apertos={nome: 1}), 1.0 + i * PASSO_S).luzinhas
              for i in range(60)]
    primeiro = vistos[0]
    assert primeiro is not None and [led for led in range(5) if primeiro[led]] == [origem]
    ate_o_numero = vistos[:vistos.index(None)]
    for antes, depois in pairwise(ate_o_numero):
        assert antes is not None and depois is not None
        assert all(d or not a for a, d in zip(antes, depois, strict=True)), "a acesa fica"
    assert ate_o_numero[-1] == (True, True, True, True, True), "as cinco antes do número"
    assert all(v is None for v in vistos[vistos.index(None):]), "o número fica"


def _ondulacao_com_apertos(ritmo: int, nome: str, numero: Luzinhas
                           ) -> tuple[list[Luzinhas], list[float]]:
    """Seis apertos por segundo durante 10 s: o que as luzinhas mostram e o brilho da barra."""
    anel = fx.Ondulacao(VERMELHO, ritmo)
    anel.quadro(fx.Entrada(apertos={}), 0.0)
    vistos, brilhos, apertos = [], [], 0
    for i in range(int(SEGUNDOS / PASSO_S)):
        if i % 10 == 0:
            apertos += 1
        quadro = anel.quadro(fx.Entrada(apertos={nome: apertos}), i * PASSO_S)
        vistos.append(numero if quadro.luzinhas is None else quadro.luzinhas)
        brilhos.append(_brilho(quadro.cor))
    return vistos, brilhos


@pytest.mark.parametrize("ritmo", RITMOS)
@pytest.mark.parametrize("jogador", range(4))
@pytest.mark.parametrize("nome", ["cross", "dpad_left", "ps"])
def test_a_ondulacao_nunca_sobe_uma_luzinha_mais_de_tres_vezes_por_segundo(
    ritmo: int, jogador: int, nome: str
) -> None:
    vistos, brilhos = _ondulacao_com_apertos(ritmo, nome, NUMEROS[jogador])
    for led in range(5):
        subidas = _quando_a_luzinha_sobe(vistos, led)
        assert _subidas_num_segundo(subidas) <= 3, f"P{jogador + 1}, ritmo {ritmo}, luzinha {led}"
    if nome == "dpad_left":
        assert _subidas_num_segundo(_quando_a_barra_sobe(brilhos, fx.PISO_DO_REAGE)) <= 3
        assert min(brilhos) >= fx.PISO_DO_REAGE - 1 / 255


def _daemon_com_apertos() -> Any:
    leitor = SimpleNamespace(snapshot=lambda: SimpleNamespace(apertos={"cross": 4}))
    return SimpleNamespace(controller=SimpleNamespace(primary_uniq=JOGADORES[0], _evdev=leitor))


def test_o_leitor_da_mao_entrega_os_apertos_a_ondulacao() -> None:
    ler = luz.leitor_da_mao(_daemon_com_apertos())
    assert ler(JOGADORES[0], "reage-ao-botao").apertos == {"cross": 4}
    assert ler(JOGADORES[0], "ondulacao").apertos == {"cross": 4}


@pytest.mark.parametrize("ritmo", RITMOS)
@pytest.mark.parametrize("posicao", POSICOES)
def test_a_cor_do_respira_em_cores_so_troca_no_piso(ritmo: int, posicao: int) -> None:
    efeito = _efeito(f"respira-em-cores;;{ritmo}")
    antes = fx.matiz_do_respira_em_cores(0.0, ritmo, posicao)
    trocas = 0
    duracao = max(SEGUNDOS, 2.5 * fx.periodo_do_respirar_s(ritmo))
    for i in range(1, int(duracao / PASSO_S)):
        t = i * PASSO_S
        matiz = fx.matiz_do_respira_em_cores(t, ritmo, posicao)
        if matiz != antes:
            trocas += 1
            for quando in (t - PASSO_S, t):
                brilho = _brilho(fx.cor_no_instante(efeito, quando, posicao))
                assert brilho <= fx.PISO_DO_RESPIRAR + 0.05, f"a cor trocou no alto: {brilho}"
            distancia = abs((matiz - antes + 0.5) % 1.0 - 0.5)
            assert distancia >= 0.35, "a cor seguinte fica longe da anterior"
        antes = matiz
    assert trocas >= 1


@pytest.mark.parametrize("ritmo", RITMOS)
def test_os_quatro_lugares_nunca_respiram_na_mesma_cor(ritmo: int) -> None:
    for i in range(int(SEGUNDOS / PASSO_S)):
        matizes = [fx.matiz_do_respira_em_cores(i * PASSO_S, ritmo, p) for p in POSICOES]
        for a in range(4):
            for b in range(a + 1, 4):
                distancia = abs((matizes[a] - matizes[b] + 0.5) % 1.0 - 0.5)
                assert distancia >= 0.2, f"ritmo {ritmo}: lugares {a} e {b} na mesma cor"


def test_o_respira_em_cores_pinta_o_matiz_que_diz() -> None:
    import colorsys

    efeito = _efeito("respira-em-cores;;2")
    periodo = fx.periodo_do_respirar_s(2)
    for k in range(4):
        topo = (k + 0.5) * periodo
        r, g, b = fx.cor_no_instante(efeito, topo, 1)
        matiz = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)[0]
        assert abs((matiz - fx.matiz_do_respira_em_cores(topo, 2, 1) + 0.5) % 1.0 - 0.5) < 0.01


def _laco(
    mao: Any = None,
) -> tuple[luz.LuzAnimada, list[tuple[str, RGB]], list[tuple[str, RGB, Any]]]:
    barra: list[tuple[str, RGB]] = []
    quadros: list[tuple[str, RGB, Any]] = []
    laco = luz.LuzAnimada(
        lambda u, c: barra.append((u, c)), lambda u: None, mao=mao,
        quadro=lambda u, c, lz: quadros.append((u, c, lz)))
    return laco, barra, quadros


@pytest.mark.parametrize("base", ["vaivem", "enche", "ondulacao"])
def test_o_laco_leva_as_tres_pelo_quadro_unico_sem_repetir_e_no_teto(base: str) -> None:
    contagem = {"cross": 0}

    def mao(uniq: str, nome_da_base: str) -> fx.Entrada:
        return fx.Entrada(apertos=dict(contagem))

    laco, barra, quadros = _laco(mao)
    plano = {u: luz.PlanoDoControle(_efeito(f"{base};FF0000;10"), 1.0, i, i + 1)
             for i, u in enumerate(JOGADORES)}
    segundos = 6.0
    for i in range(int(segundos * 120)):
        if i % 40 == 1:
            contagem["cross"] += 1
        laco.tique(100.0 + i / 120, plano)
    assert quadros and not barra, "o quadro único leva barra e luzinhas; a barra avulsa não sai"
    for uniq in JOGADORES:
        dele = [(c, lz) for u, c, lz in quadros if u == uniq]
        assert len(dele) <= luz.QUADROS_POR_SEGUNDO_MAXIMO * segundos + 1, uniq
        assert all(a != b for a, b in pairwise(dele)), "quadro igual não sai"
        assert any(lz is None for _, lz in dele), f"{uniq}: o número nunca voltou"
        assert any(lz is not None for _, lz in dele), f"{uniq}: as luzinhas nunca andaram"


def test_o_respira_em_cores_conta_no_relogio_comum_e_nao_toca_as_luzinhas() -> None:
    import colorsys

    efeito = _efeito("respira-em-cores;;10")
    agora = [100.0]
    ultimas: dict[str, tuple[RGB, float]] = {}
    quadros: list[object] = []
    laco = luz.LuzAnimada(
        lambda u, c: ultimas.__setitem__(u, (c, agora[0])), lambda u: None,
        quadro=lambda u, c, lz: quadros.append((u, c, lz)))
    for i in range(572):
        agora[0] = 100.0 + i / 60
        entraram = JOGADORES[: 1 + min(3, i // 37)]
        plano = {u: luz.PlanoDoControle(efeito, 1.0, JOGADORES.index(u), 1) for u in entraram}
        laco.tique(agora[0], plano)
    assert not quadros, "o Respira em cores é só a barra"
    assert set(ultimas) == set(JOGADORES)
    for posicao, uniq in enumerate(JOGADORES):
        (r, g, b), quando = ultimas[uniq]
        matiz = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)[0]
        esperado = fx.matiz_do_respira_em_cores(quando - 100.0, 10, posicao)
        assert abs((matiz - esperado + 0.5) % 1.0 - 0.5) < 0.01, f"{uniq} saiu do relógio comum"


GRUPO_DE = {"ondulacao": "Que reage", "vaivem": "Que se move", "enche": "Que se move",
            "respira-em-cores": "Que respira"}
ROTULO_DE = {"ondulacao": "Ondulação", "vaivem": "Vaivém", "enche": "Enche",
             "respira-em-cores": "Respira em cores"}
DICA_DE = {"ondulacao": "O aperto corre pelas luzinhas.",
           "vaivem": "Uma luz vai e volta nas luzinhas.",
           "enche": "As luzinhas acendem uma a uma.",
           "respira-em-cores": "Cada respiração numa cor."}


def test_a_aba_tem_rotulo_ritmo_dica_e_grupo_de_cada_uma() -> None:
    from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

    grupos = dict(a04.GRUPOS_DA_LISTA)
    for base in BASES_DOS_PERIFERICOS_DA_LUZ:
        token = a04.token_da_base(base)
        assert a04.rotulo_da_opcao(token) == ROTULO_DE[base]
        assert a04.dica_do_efeito(token) == DICA_DE[base]
        assert base in grupos[GRUPO_DE[base]], base
        assert sum(base in nomes for nomes in grupos.values()) == 1, base
    assert a04.RITMO_DA_BASE["respira-em-cores"] == a04.RITMO_DA_BASE["respirar"] == 2
    assert {a04.RITMO_DA_BASE[b] for b in ("ondulacao", "vaivem", "enche")} == {5}


def _grupos_de_cada_lista(html: str) -> list[dict[str, list[str]]]:
    listas = re.findall(r'<select class="g4-efeito".*?</select>', html, flags=re.S)
    return [{rotulo: re.findall(r'<option value="base:([^"]+)">', miolo)
             for rotulo, miolo in re.findall(r'<optgroup label="([^"]+)">(.*?)</optgroup>', lista,
                                             flags=re.S)} for lista in listas]


def test_o_mockup_lista_as_quatro_em_cada_lugar_no_grupo_certo() -> None:
    html = (RAIZ / "mockup/04-iluminacao.html").read_text()
    listas = _grupos_de_cada_lista(html)
    assert len(listas) == 4, "uma lista por lugar"
    for lista in listas:
        for base, grupo in GRUPO_DE.items():
            assert base in lista[grupo], f"{base} fora de «{grupo}»"
    for base, rotulo in ROTULO_DE.items():
        assert html.count(f'<option value="base:{base}">{rotulo}</option>') == 4, base


def test_o_gerador_da_aba_monta_e_confere_sem_exigir_vermelho(tmp_path: pathlib.Path) -> None:
    anterior = os.environ.get("HEFESTO_BANCADA")
    os.environ["HEFESTO_BANCADA"] = str(tmp_path)
    try:
        import aba04
        import onde
        from monta import monta

        monta("04-iluminacao", "Iluminação", aba04.MIOLO,
              aba04.CSS + aba04.CSS_DAS_MEDIDAS, legenda=aba04.LEGENDA)
        doc = onde.pagina("04-iluminacao.html").read_text()
        aba04._conferir(doc)
    finally:
        if anterior is None:
            os.environ.pop("HEFESTO_BANCADA", None)
        else:
            os.environ["HEFESTO_BANCADA"] = anterior
    for lista in _grupos_de_cada_lista(doc):
        for base, grupo in GRUPO_DE.items():
            assert base in lista[grupo]


def _ctx(n: int) -> Any:
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


@pytest.mark.parametrize("base", BASES_DOS_PERIFERICOS_DA_LUZ)
@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_escolher_cada_uma_na_lista_grava_o_texto_que_o_perfil_le(n: int, base: str) -> None:
    import pacotes
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_computador
    from pacotes import a04_iluminacao as a04

    uniq = JOGADORES[n - 1]
    cor = a04.pacote(_ctx(n))["colunas"][uniq]["hex"].lstrip("#").upper()
    gesto = pacotes.gesto_da_pagina("04-iluminacao.html", "efeito-da-luz")
    assert gesto is not None
    gesto(_ctx(n), {"uniq": uniq, "valor": f"base:{base}"}, None)
    guardado = o_computador().controles[uniq.replace(":", "")].leds.efeito
    ritmo = a04.RITMO_DA_BASE[base]
    sem_cor = base == "respira-em-cores"
    assert guardado == (f"{base};;{ritmo}" if sem_cor else f"{base};{cor};{ritmo}")
    assert _efeito(guardado).base == base
    coluna = a04.pacote(_ctx(n))["colunas"][uniq]
    assert coluna[a04.CAMPO_DO_EFEITO] == f"base:{base}"
    assert coluna[a04.CAMPO_DA_DICA_DO_EFEITO] == DICA_DE[base]


def test_nenhum_efeito_novo_toca_o_led_do_mic() -> None:
    fonte = pathlib.Path(fx.__file__).read_text()
    assert "luz_do_mic" not in fonte and "mic_led" not in fonte, "o LED do mic tem dono"
