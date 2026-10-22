"""A luz ganha a Onda e o Relâmpago (A-LUZ-GANHA-ONDA-E-RELAMPAGO-01, 22/10/2026).

Duas bases novas, como funções puras do tempo, ao lado das seis que existem: a Onda corre a crista
pelos cinco LEDs do jogador (a barra acompanha o do meio) e o Relâmpago é o estrobo dentro da regra
da casa (WCAG 2.3.1): no máximo 3 subidas por segundo em qualquer ritmo, borda suave, piso de
brilho, e nunca o vermelho saturado alternando com o apagado. O pulso de batimento que ela citou já
é a Batida e não se duplica.

O desenho de cada LED do jogador existe (``brilhos_da_onda``), mas o daemon só leva a barra: um
quadro com a barra e os LEDs juntos pede um escritor novo no backend (a barra sozinha é 1 report por
quadro no rádio; a barra mais as luzinhas pelas duas pontas de hoje são 2). Por isso a prova de
daemon aqui é a da barra, nos quatro controles.

MORDIDAS (22/10/2026): trocar o piso do Relâmpago por 0, o `_entre_ritmos(ritmo, 7.0, 1.4)` por
`(ritmo, 7.0, 0.3)` (o teto de 3 por segundo vai a ~7), o `LED_DO_MEIO_DA_ONDA` por 0, ou tirar
`relampago` da tupla `BASES_DA_LUZ` reprova.
"""
from __future__ import annotations

import pathlib
import re
import sys
from itertools import pairwise
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import luz_animada as luz
from hefesto_dualsense4unix.profiles import efeitos_de_luz as fx
from hefesto_dualsense4unix.profiles.schema import (
    BASES_DA_LUZ,
    EfeitoDaLuz,
    LedsConfig,
    Profile,
    ler_o_efeito_da_luz,
)

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

MOCKUP = RAIZ / "mockup" / "04-iluminacao.html"
RGB = tuple[int, int, int]
VERMELHO: RGB = (255, 0, 0)
NOVAS = ("onda", "relampago")
RITMOS = range(1, 11)
#: Faixa forjada (`aa:bb:cc`), nunca endereço de aparelho de verdade.
JOGADORES = [f"aa:bb:cc:00:00:0{n}" for n in range(1, 5)]
PASSO_S = 1 / 60  # a varredura de 10 s a 60 quadros por segundo
PISO = {"onda": fx.PISO_DA_ONDA, "relampago": fx.PISO_DO_RELAMPAGO}


def _efeito(base: str, ritmo: int = 5, cor: RGB = VERMELHO) -> EfeitoDaLuz:
    return EfeitoDaLuz(base, (cor,), ritmo)


def _curva(base: str, ritmo: int, segundos: float = 10.0) -> list[float]:
    """O brilho da barra (o canal mais alto) de 10 s a 60 quadros por segundo."""
    efeito = _efeito(base, ritmo)
    n = int(segundos / PASSO_S)
    return [max(fx.cor_no_instante(efeito, i * PASSO_S)) / 255 for i in range(n)]


def _quando_sobe(brilhos: list[float], piso: float) -> list[float]:
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


def _mais_subidas_em_um_segundo(tempos: list[float]) -> int:
    mais = 0
    for i, inicio in enumerate(tempos):
        dentro = sum(1 for t in tempos[i:] if t - inicio < 1.0 - 1e-6)
        mais = max(mais, dentro)
    return mais


# ---------------------------------------------------------------- as bases existem


def test_as_duas_bases_estao_na_tupla_e_o_perfil_as_le_com_cor_e_ritmo() -> None:
    assert set(NOVAS) <= set(BASES_DA_LUZ)
    assert len(set(BASES_DA_LUZ)) == len(BASES_DA_LUZ) == 8
    for base in NOVAS:
        for ritmo in (1, 5, 10):
            lido = ler_o_efeito_da_luz(f"{base};FF8000;{ritmo}")
            assert lido == EfeitoDaLuz(base, ((255, 128, 0),), ritmo)
        assert ler_o_efeito_da_luz(f"{base};;5") is None, "as duas levam cor, como a Batida"
        cor = fx.cor_no_instante(_efeito(base), 1.234)
        assert len(cor) == 3 and all(0 <= c <= 255 for c in cor)


def test_o_batimento_continua_um_so_e_nao_ganhou_irmao() -> None:
    """O pulso de batimento que ela citou já é a Batida: ninguém o duplica."""
    assert BASES_DA_LUZ.count("batimento") == 1
    assert not {"pulso", "estrobo", "batida"} & set(BASES_DA_LUZ)


# ---------------------------------------------------------------- o teto de subidas por segundo


@pytest.mark.parametrize("base", NOVAS)
@pytest.mark.parametrize("ritmo", RITMOS)
def test_nenhuma_das_duas_passa_de_tres_subidas_por_segundo(base: str, ritmo: int) -> None:
    subidas = _quando_sobe(_curva(base, ritmo), PISO[base])
    assert subidas, f"{base} no ritmo {ritmo}: a varredura de 10 s não viu nenhuma subida"
    assert _mais_subidas_em_um_segundo(subidas) <= 3, f"{base} no ritmo {ritmo}"


def test_o_relampago_no_ritmo_mais_alto_tem_duas_subidas_por_rajada_e_a_rajada_dura_1_4_s() -> None:
    assert fx.periodo_do_relampago_s(10) == pytest.approx(1.4)
    assert fx.periodo_do_relampago_s(1) == pytest.approx(7.0)
    subidas = _quando_sobe(_curva("relampago", 10), fx.PISO_DO_RELAMPAGO)
    assert len(subidas) >= 2 * 7, "duas subidas por rajada em 10 s"
    assert _mais_subidas_em_um_segundo(subidas) == 2
    # a rajada mais curta do mundo (1,4 s com duas subidas) fica abaixo de 3 por segundo
    assert 2 / fx.periodo_do_relampago_s(10) < 3.0


def test_a_onda_tem_no_maximo_uma_subida_por_passada_e_a_passada_mais_curta_e_1_5_s() -> None:
    assert fx.periodo_da_onda_s(10) == pytest.approx(1.5)
    assert fx.periodo_da_onda_s(1) == pytest.approx(6.0)
    subidas = _quando_sobe(_curva("onda", 10), fx.PISO_DA_ONDA)
    assert _mais_subidas_em_um_segundo(subidas) == 1


def test_o_ritmo_alto_e_mais_rapido_que_o_baixo_nas_duas() -> None:
    assert fx.periodo_da_onda_s(10) < fx.periodo_da_onda_s(1)
    assert fx.periodo_do_relampago_s(10) < fx.periodo_do_relampago_s(1)
    for ritmo in range(1, 10):
        assert fx.periodo_da_onda_s(ritmo + 1) < fx.periodo_da_onda_s(ritmo)
        assert fx.periodo_do_relampago_s(ritmo + 1) < fx.periodo_do_relampago_s(ritmo)


# ---------------------------------------------------------------- o piso e a borda


@pytest.mark.parametrize("base", NOVAS)
def test_as_duas_tem_piso_e_nunca_apagam_a_barra(base: str) -> None:
    for ritmo in RITMOS:
        curva = _curva(base, ritmo)
        assert min(curva) >= PISO[base] - 0.01, f"{base} no ritmo {ritmo}: {min(curva)}"
        assert max(curva) > 0.95, f"{base} no ritmo {ritmo}: não chega ao topo"


@pytest.mark.parametrize("base", NOVAS)
@pytest.mark.parametrize("ritmo", RITMOS)
def test_o_vermelho_saturado_nunca_chega_ao_preto(base: str, ritmo: int) -> None:
    efeito = _efeito(base, ritmo)
    cores = [fx.cor_no_instante(efeito, i * PASSO_S) for i in range(int(10 / PASSO_S))]
    assert (0, 0, 0) not in cores
    assert min(c[0] for c in cores) >= round(PISO[base] * 255)


def test_o_relampago_tem_borda_suave_na_subida() -> None:
    """Da subida de 5% a 95% do passeio leva ao menos 60 ms: o estrobo de verdade leva zero."""
    for ritmo in RITMOS:
        curva = _curva("relampago", ritmo, segundos=15.0)
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
        assert durou and min(durou) >= 0.06, f"ritmo {ritmo}: a subida levou {min(durou or [0])}"


def test_o_relampago_escurece_mais_devagar_do_que_clareia_e_o_eco_e_mais_fraco() -> None:
    p = fx.periodo_do_relampago_s(3)
    assert fx.brilho_do_relampago(0.0, p) == pytest.approx(fx.PISO_DO_RELAMPAGO)
    assert fx.brilho_do_relampago(fx.SUBIDA_DO_RELAMPAGO_S, p) == pytest.approx(1.0)
    eco = fx.brilho_do_relampago(fx.ECO_DO_RELAMPAGO_S + fx.SUBIDA_DO_RELAMPAGO_S, p)
    assert fx.PISO_DO_RELAMPAGO + 0.5 < eco < 1.0
    assert fx.DESCIDA_DO_RELAMPAGO_S > fx.SUBIDA_DO_RELAMPAGO_S


def test_a_cor_do_relampago_e_da_onda_troca_so_com_a_luz_no_piso() -> None:
    for base in NOVAS:
        efeito = EfeitoDaLuz(base, (VERMELHO, (0, 0, 255)), 6)
        vistas = [fx.cor_no_instante(efeito, i * PASSO_S) for i in range(int(12 / PASSO_S))]
        for antes, depois in pairwise(vistas):
            if (antes[0] > 0) != (depois[0] > 0):
                assert max(antes + depois) <= 0.25 * 255, f"{base}: a cor trocou no alto"
        assert {c[0] > 0 for c in vistas} == {True, False}, f"{base}: as duas cores aparecem"


# ---------------------------------------------------------------- a Onda anda pelos 5 LEDs


@pytest.mark.parametrize("ritmo", RITMOS)
def test_a_onda_anda_pelos_cinco_leds_da_esquerda_para_a_direita(ritmo: int) -> None:
    periodo = fx.periodo_da_onda_s(ritmo)
    assert fx.LEDS_DA_ONDA == 5
    topo = [0.0] * 5
    quando = [0.0] * 5
    for i in range(int(periodo / PASSO_S) + 1):
        t = i * PASSO_S
        brilhos = fx.brilhos_da_onda(t, periodo)
        assert len(brilhos) == 5 and all(fx.PISO_DA_ONDA - 1e-9 <= b <= 1.0 for b in brilhos)
        for led, b in enumerate(brilhos):
            if b > topo[led]:
                topo[led], quando[led] = b, t
    instantes = quando
    assert all(b > 0.95 for b in topo), f"toda LED chega ao topo: {topo}"
    assert instantes == sorted(instantes) and len(set(instantes)) == 5, instantes


def test_a_barra_da_onda_e_o_led_do_meio_e_o_desenho_e_o_mesmo_nos_quatro_controles() -> None:
    assert fx.LED_DO_MEIO_DA_ONDA == 2
    efeito = _efeito("onda", 7)
    periodo = fx.periodo_da_onda_s(7)
    for i in range(0, 400):
        t = i * 0.05
        esperado = fx._escalar(VERMELHO, fx.brilho_da_onda(t, periodo, 2))
        for posicao in range(4):
            assert fx.cor_no_instante(efeito, t, posicao, semente=posicao) == esperado


def test_a_onda_passa_e_a_barra_volta_ao_piso_entre_uma_passada_e_outra() -> None:
    periodo = fx.periodo_da_onda_s(5)
    assert fx.brilho_da_onda(0.0, periodo) == pytest.approx(fx.PISO_DA_ONDA)
    assert fx.brilho_da_onda(periodo / 2, periodo) == pytest.approx(1.0)
    assert fx.brilho_da_onda(periodo * 0.999, periodo) < fx.PISO_DA_ONDA + 0.05


# ---------------------------------------------------------------- o motor anima no laço real


def _quadros(texto: str, segundos: float = 6.0, controles: int = 4) -> dict[str, list[RGB]]:
    """O laço real (``LuzAnimada``) a 60 tiques por segundo: o que sai para cada controle."""
    saiu: dict[str, list[RGB]] = {u: [] for u in JOGADORES[:controles]}
    laco = luz.LuzAnimada(lambda u, cor: saiu[u].append(cor), lambda u: None)
    efeito = ler_o_efeito_da_luz(texto)
    assert efeito is not None, texto
    plano = {
        u: luz.PlanoDoControle(efeito, 1.0, posicao, posicao + 1)
        for posicao, u in enumerate(JOGADORES[:controles])
    }
    for i in range(int(segundos * 60)):
        laco.tique(100.0 + i / 60, plano)
    return saiu


@pytest.mark.parametrize("texto", ["onda;FF0000;5", "relampago;00FFFF;9", "onda;FFFFFF;10"])
def test_o_laco_anima_os_quatro_controles_a_no_maximo_30_quadros_por_segundo(texto: str) -> None:
    segundos = 6.0
    saiu = _quadros(texto, segundos)
    assert set(saiu) == set(JOGADORES)
    for uniq, quadros in saiu.items():
        assert len(quadros) <= luz.QUADROS_POR_SEGUNDO_MAXIMO * segundos + 1, uniq
        assert len(set(quadros)) > 5, f"{uniq}: a barra não se mexeu"
        assert (0, 0, 0) not in quadros, f"{uniq}: a barra apagou"


def test_o_plano_do_perfil_le_a_onda_e_o_relampago_para_todo_controle() -> None:
    for base in NOVAS:
        perfil = Profile(name="Régua", match={"type": "any"},
                         leds=LedsConfig(efeito=f"{base};FF0000;5", lightbar_brightness=0.8))
        plano = luz.plano_do_perfil(perfil, JOGADORES, mesa_em_economia=False,
                                    em_economia=frozenset())
        assert set(plano) == set(JOGADORES)
        assert all(p.efeito.base == base for p in plano.values())


# ---------------------------------------------------------------- a tela


def _doc() -> str:
    bruto = MOCKUP.read_text(encoding="utf-8")
    sem_comentario = re.sub(r"<!--.*?-->", "", bruto, flags=re.S)
    return re.sub(r"<(style|script)\b[^>]*>.*?</\1>", "", sem_comentario, flags=re.S)


def _opcoes(lista: str) -> list[tuple[str, str]]:
    return re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)</option>', lista)


def test_as_duas_estao_em_que_se_move_em_cada_lista_do_desenho_e_na_frase_da_dica() -> None:
    from pacotes import a04_iluminacao as a04

    doc = _doc()
    listas = re.findall(r'<select class="g4-efeito".*?</select>', doc, flags=re.S)
    assert len(listas) == 4
    for lista in listas:
        grupo = lista.split('<optgroup label="Que se move">', 1)[1].split("</optgroup>", 1)[0]
        assert _opcoes(grupo) == [
            ("base:piscar", "Piscar"), ("base:arco-iris", "Arco-íris"),
            ("base:onda", "Onda"), ("base:relampago", "Relâmpago")]
    for base in NOVAS:
        assert a04.dica_do_efeito(f"base:{base}") == a04.DICA_DA_BASE[base]
        assert a04.rotulo_da_opcao(f"base:{base}") == a04.ROTULO_DA_BASE[base]
    assert "Estrobo" not in doc and "estrobo" not in doc.lower(), "o nome na tela é «Relâmpago»"


def test_o_criar_efeitos_novos_oferece_as_duas_como_base() -> None:
    doc = _doc()
    criar = doc.split('<div class="quadro criar"', 1)[1]
    jeito = criar.split('class="seg-criar"', 1)[1].split('class="g4-cores"', 1)[0]
    assert re.findall(r'<input type="radio" name="base-criar" value="([^"]+)"', jeito) == [
        "respirar", "piscar", "arco-iris", "onda", "relampago"]
    assert "<span>Onda</span>" in jeito and "<span>Relâmpago</span>" in jeito


def _criar(forma: dict[str, Any]) -> None:
    import pacotes

    ctx = pacotes.Contexto(state={"active_profile": ""}, mesa=[], conectados=[], estados={})
    pacotes.gesto_da_pagina("04-iluminacao.html", "criar-efeito")(ctx, {"forma": forma}, None)


@pytest.mark.parametrize("base", NOVAS)
def test_criar_um_efeito_com_a_onda_ou_o_relampago_guarda_na_biblioteca(base: str) -> None:
    from pacotes import a04_iluminacao as a04

    _criar({"base": base, "cores": "#ff0000,#00ff00", "ritmo": "6", "nome": f"Meu {base}"})
    guardado = a04.meus_efeitos("luz")[f"Meu {base}"]
    assert guardado["base"] == base
    assert a04.efeito_do_item(guardado) == f"{base};FF0000,00FF00;6"
    assert ler_o_efeito_da_luz(a04.efeito_do_item(guardado)) is not None


def test_a_dica_de_cada_base_nova_cabe_na_coluna_e_comeca_maiuscula() -> None:
    from pacotes import a04_iluminacao as a04

    for base in NOVAS:
        frase = a04.DICA_DA_BASE[base]
        assert frase[0].isupper() and frase.endswith(".") and len(frase) <= 36, frase
        assert "Relâmpago" not in frase or base == "relampago"
    assert set(a04.DICA_DA_BASE) == set(a04.RITMO_DA_BASE) == set(a04.ROTULO_DA_BASE)


def test_a_dica_da_onda_diz_o_que_o_aparelho_faz_so_a_barra() -> None:
    """A tela diz o que o aparelho faz: o escritor do daemon leva só a barra, então a dica da Onda
    fala da barra e não promete o brilho correndo de um lado ao outro. Quando o quadro único levar
    os LEDs do jogador, esta régua reprova e a dica muda junto."""
    import inspect

    from pacotes import a04_iluminacao as a04

    escritor = inspect.getsource(luz.escritor_de_producao)
    assert "pintar_a_barra_sem_lembrar" in escritor
    assert "luzinhas" not in escritor, "o daemon passou a levar os LEDs: a dica da Onda muda junto"
    frase = a04.DICA_DA_BASE["onda"]
    assert "barra" in frase and "lado" not in frase, frase


CHROME = pathlib.Path("/usr/bin/google-chrome")
#: 940 fica de fora: a janela do produto não desce de 1212 (``LARGURA_DO_DESENHO``), e a 940 a
#: linha «Criar efeitos novos» já quebrava antes das duas opções (82 px, o miolo com 35 de sobra).
VISTAS_DA_04 = [(1212, 809), (1272, 860), (1512, 860), (1900, 1000)]


@pytest.mark.skipif(not CHROME.exists(), reason="sem o Chrome do sistema: a régua não tem motor")
def test_a_04_com_as_duas_opcoes_a_mais_nao_rola_na_vertical() -> None:
    """A linha «Criar efeitos novos» fica numa linha só (com 5 jeitos no lugar de 3) e nada rola."""
    from playwright.sync_api import sync_playwright

    from hefesto_dualsense4unix.interface.folha_da_casa import seletores_escondidos

    escondidos = "".join(f"{s}{{display:none}}" for s in seletores_escondidos())
    medir = """() => {
      const rola = [];
      for (const e of document.querySelectorAll('*')) {
        const s = getComputedStyle(e);
        if ((s.overflowY === 'auto' || s.overflowY === 'scroll')
            && e.scrollHeight > e.clientHeight + 1) {
          rola.push((e.className || e.tagName) + ':' + (e.scrollHeight - e.clientHeight));
        }
      }
      const d = document.documentElement;
      if (d.scrollHeight - window.innerHeight > 1) rola.push('doc');
      const linha = document.querySelector('.criar-linha').getBoundingClientRect();
      return {rola, linha: Math.round(linha.height)};
    }"""
    achados = []
    with sync_playwright() as pw:
        # com a barra de rolagem de verdade (15 px): é ela que a linha de criar tem de aguentar
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"],
                                 ignore_default_args=["--hide-scrollbars"])
        for larg, alt in VISTAS_DA_04:
            pg = nav.new_page(viewport={"width": larg, "height": alt})
            pg.goto(MOCKUP.as_uri())
            pg.wait_for_load_state("networkidle")
            pg.add_style_tag(content=escondidos)  # o que o piloto esconde, como o `olhar.py`
            pg.wait_for_timeout(300)
            m = pg.evaluate(medir)
            if m["rola"] or m["linha"] > 50:
                achados.append((larg, alt, m))
            pg.close()
        nav.close()
    assert not achados, f"a 04 rola ou a linha de criar quebrou: {achados}"
