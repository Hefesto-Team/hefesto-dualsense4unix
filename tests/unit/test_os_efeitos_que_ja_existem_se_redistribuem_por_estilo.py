#!/usr/bin/env python3
"""OS-EFEITOS-QUE-JA-EXISTEM-SE-REDISTRIBUEM-POR-ESTILO-01 — a receita de cada estilo é a da página.

A tabela `S` da página aprovada em 19/10/2026 (`redistribuicao-dos-efeitos.html`) dá a cada estilo o
R2, o L2, a háptica, os motores, a luz base e a frente da lista. Aqui ela está escrita à mão, sem
ler o módulo que mede, e as seis réguas comparam o produto com ela.

As mordidas (arrancar, ver reprovar, devolver conferindo o md5 do arquivo):
- `TriggersConfig(left=lado, right=lado)` de volta no `_com_o_estilo` (o L2 igual ao R2): a régua 2;
- a linha do `souls` fora de `ESTILOS`: a régua 5;
- o `SAIU_DO_CATALOGO`/`POR_CHAVE["arco"]` fora de `estilos_de_jogo`: a régua 4;
- `POR_ESTILO = {}` nos motores (`padroes_de_vibracao`): a régua 1.
"""
from __future__ import annotations

from typing import Any

import pytest


from hefesto_dualsense4unix.daemon.subsystems import padroes_de_vibracao as pv
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.interface.pacotes import a10_perfis
from hefesto_dualsense4unix.profiles import efeitos_de_imersao as ei
from hefesto_dualsense4unix.profiles import estilos_de_jogo as ej
from hefesto_dualsense4unix.profiles import formas_de_haptica as fh
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

OFF = ("Off", None)

#: A tabela S da página, na língua do código: (R2, L2, háptica, motores, base da luz, brilho).
#: `None` na imersão é o acionamento de partida do modo (o FPS tem a Metralhadora, a Simulação a
#: Rampa). Os efeitos novos do bloco C (20/10/2026) estão na tabela com o nome deles.
TABELA: dict[str, tuple[Any, Any, str, str | None, str | None, float]] = {
    "fps": (("Machine", None), ("Resistance", "mira-firme"), "toque", "coice", "respirar", 1.0),
    "acao": (("Weapon", "golpe-pesado"), ("Resistance", "mira-firme"),  # (noqa-acento) chave
             "impacto", "tranco", "respirar", 1.0),
    "luta": (("Weapon", "golpe-pesado"), ("Weapon", "golpe-leve"),
             "impacto", "pancada_do_lado", "respirar", 1.0),
    "souls": (("Weapon", "golpe-pesado"), ("MultiPositionFeedback", "escudo-que-aguenta"),
              "eco", "tranco", "chama", 0.6),
    "furtivo": (("Weapon", "golpe-leve"), ("Resistance", "carga-folego"),
                "estalo", "onda", None, 0.3),
    "aventura": (("Bow", "corda-que-estica"), ("Resistance", "mira-firme"),
                 "toque", "onda", "chama", 1.0),
    "terror": (("Weapon", "pino-que-falha"), ("Resistance", "mira-firme"),
               "toque", "batida", "batimento", 0.7),
    "corrida": (("MultiPositionVibration", "motor-no-acelerador"),
                ("Resistance", "freio-abs-que-pulsa"), "som_no_corpo", None, None, 1.0),
    "simulacao": (("SlopeFeedback", None), ("Galloping", "terreno-que-muda"),
                  "grao", None, "mare", 0.6),
    "esportes": (("Resistance", "golpe-carregado"), ("Resistance", "pique-que-cansa"),
                 "impacto", "tranco", None, 1.0),
    "plataforma": (("SlopeFeedback", "agarrar"), ("MultiPositionVibration", "energia-que-cresce"),
                   "estalo", None, "arco-iris", 1.0),
    "ritmo": (("Weapon", "golpe-leve"), ("Weapon", "golpe-leve"), "estalo", None, None, 1.0),
    "retro": (OFF, OFF, "motor_de_epoca", None, None, 1.0),
    "maratona": (OFF, OFF, "toque", None, None, 0.25),
    "point_and_click": (("Weapon", "clique-mouse"), ("Weapon", "clique-mouse"),
                        "toque", None, None, 0.4),
    "visual_novel": (OFF, OFF, "toque", None, "mare", 0.5),
}

#: A «frente» da página, em imersões que existem (com as três do bloco C de 20/10/2026: Golpe ·
#: falha, Golpe · aparo e Travar · esgotado).
FRENTE: dict[str, set[str]] = {
    "fps": {"ferrolho-que-volta", "rajada-que-sobe-sozinha", "recuo-pesado", "clique-no-meio",
            "trava-seca"},
    "acao": {"golpe-leve", "golpe-carregado", "corda-que-estica",  # (noqa-acento) chave
             "energia-que-cresce",
             "escudo-que-aguenta"},
    "luta": {"golpe-carregado", "golpe-falha", "ferrolho-que-volta"},
    "souls": {"golpe-aparo", "golpe-carregado", "pique-que-cansa", "travar-esgotado"},
    "furtivo": {"flecha-que-escapa", "clique-no-meio", "mira-firme"},
    "aventura": {"agarrar", "flecha-que-escapa", "besta", "porta-emperrada", "galope-no-chao"},
    "terror": {"trava-seca", "porta-emperrada", "golpe-pesado", "batida-do-coracao"},
    "corrida": {"pedal-duro", "motor-que-sobe", "terreno-que-muda"},
    "simulacao": {"pedal-duro", "motor-no-acelerador", "mira-firme"},
    "esportes": {"golpe-leve", "ferrolho-que-volta", "mira-firme"},
    "plataforma": {"golpe-leve", "corda-que-estica", "mira-firme"},
    "ritmo": {"ferrolho-que-volta"},
    "retro": {"clique-no-meio", "mira-firme", "golpe-leve"},
    "maratona": {"mira-firme", "golpe-leve"},
    "point_and_click": {"golpe-leve"},
    "visual_novel": {"golpe-leve"},
    "adulto": set(),
}

MESA = [
    {"uniq": f"aabbcc00000{n}", "jogador": n} for n in (1, 2, 3, 4)
]


def _perfil() -> Profile:
    return Profile(name="Redistribuicao", match=MatchAny(), priority=40)


def _aplicado(chave: str) -> Any:
    return a10_perfis._com_o_estilo(_perfil(), ej.POR_CHAVE[chave], MESA)[0]


def _luz(prof: Any, uniq: Any) -> Any:
    return prof.controllers[uniq].leds


def test_a_receita_de_cada_estilo_e_a_da_tabela_da_pagina() -> None:
    """Régua 1: R2, L2, háptica, motores, base da luz e brilho de cada estilo batem com a tabela.

    MORDIDA: `POR_ESTILO = {}` nos motores (ou uma linha trocada nos estilos) reprova aqui.
    """
    for chave, (r2, l2, forma, motores, base, brilho) in TABELA.items():
        e = ej.POR_CHAVE[chave]
        assert (e.r2.modo, e.r2.imersao) == r2, f"{chave}: R2"
        assert (e.l2.modo, e.l2.imersao) == l2, f"{chave}: L2"
        assert fh.POR_ESTILO.get(chave) == forma, f"{chave}: háptica"
        assert pv.POR_ESTILO.get(chave) == motores, f"{chave}: motores"
        receita = e.receita_invisivel
        assert receita is not None
        assert receita.luz_base == base, f"{chave}: base da luz"
        assert e.brilho == brilho, f"{chave}: brilho"
    assert (ej.POR_CHAVE["ritmo"].receita_invisivel.luz) == "batida"  # type: ignore[union-attr]


def test_os_dois_lados_chegam_ao_perfil_e_a_imersao_dos_numeros_os_reconhece() -> None:
    # D-2010-O-R2-E-O-L2-DO-ESTILO-SAO-RECEITAS-SEPARADAS
    """Régua 2: o R2 e o L2 são gravados cada um com a imersão do `Lado` dele.

    MORDIDA: `TriggersConfig(left=lado, right=lado)` de volta no `_com_o_estilo` reprova aqui.
    """
    for chave, (r2, l2, *_resto) in TABELA.items():
        prof = _aplicado(chave)
        for disco, (modo, imersao) in (("right", r2), ("left", l2)):
            gravado = getattr(prof.triggers, disco)
            assert gravado.mode == modo, f"{chave}/{disco}"
            if imersao is None:
                continue
            achada = ei.imersao_dos_numeros(modo, gravado.params)
            assert achada is not None, f"{chave}/{disco}: os números não são de imersão nenhuma"
            assert achada[0].chave == imersao, f"{chave}/{disco}: {achada[0].chave}"
    esportes = _aplicado("esportes")
    assert esportes.triggers.right.params != esportes.triggers.left.params, (
        "o chute carrega e o fôlego cansa: dois gatilhos, duas receitas")


def test_a_frente_de_cada_estilo_tem_de_um_a_cinco_efeitos() -> None:
    """Régua 3: a frente da lista é a da página, entre um e cinco efeitos (o Adulto, nenhum)."""
    for chave, esperado in FRENTE.items():
        da_frente = {i.chave for i in ei.IMERSOES if chave in i.na_frente}
        assert da_frente == esperado, f"{chave}: {sorted(da_frente ^ esperado)}"
        assert len(da_frente) <= 5, chave
        if chave != "adulto":
            assert da_frente, f"{chave}: a frente ficou vazia"


def test_o_arco_carrega_como_acao_e_nao_esta_no_catalogo() -> None:
    """Régua 4: o `arco` saiu de `ESTILOS`; o perfil salvo com a chave velha vira Ação.

    MORDIDA: tire o apelido `POR_CHAVE["arco"]` e isto reprova.
    """
    assert "arco" not in {e.chave for e in ej.ESTILOS}
    assert "Arco" not in ej.POR_ROTULO
    assert ej.POR_CHAVE["arco"] is ej.POR_CHAVE["acao"]  # (noqa-acento) chave
    assert ej.chave_do_catalogo("arco") == "acao"  # (noqa-acento) chave
    antigo = Profile(name="Arco antigo", match=MatchAny(), estilo="arco")
    nova = Profile(name="Acao nova", match=MatchAny(), estilo="acao")  # (noqa-acento) chave
    assert tv.receita_do_perfil(antigo) == tv.receita_do_perfil(nova)


def test_as_cores_seguem_distintas_com_souls_e_furtivo_e_a_luz_base_nao_as_iguala() -> None:
    # D-2010-NASCEM-O-SOULS-RPG-E-O-FURTIVO
    """Régua 5: nenhuma unidade repete a cor de outra, e a base da luz leva a cor DE CADA UMA.

    MORDIDA: tire a linha do `souls` de `ESTILOS` (ou tire a cor do `escrever_o_efeito_da_luz`)
    e isto reprova.
    """
    familias = {e.chave: e.familia for e in ej.DE_FABRICA}
    for novo in ("souls", "furtivo"):
        quatro = ej.as_quatro(novo)
        assert min(ej._distancia(quatro[i], quatro[j])
                   for i in range(4) for j in range(i + 1, 4)) >= ej.DISTANCIA_MINIMA
        for outro, familia in familias.items():
            if outro != novo:
                assert ej._distancia(familias[novo], familia) >= ej.DISTANCIA_MINIMA, (
                    f"{novo} e {outro} pintam a mesma família")
    for chave in ("souls", "furtivo", "aventura", "terror", "simulacao"):
        prof = _aplicado(chave)
        cores = [_luz(prof, u["uniq"]).lightbar for u in MESA]
        assert len(set(cores)) == 4, f"{chave}: duas unidades com a mesma cor"
        base = TABELA[chave][4]
        for u in MESA:
            leds = _luz(prof, u["uniq"])
            if base is None:
                assert not leds.efeito, f"{chave}: a luz fixa ganhou uma base"
                continue
            partes = (leds.efeito or "").split(";")
            assert len(partes) == 3 and partes[0] == base, f"{chave}: a base não chegou ao perfil"
            r, g, b = leds.lightbar
            assert partes[1] == f"{r:02X}{g:02X}{b:02X}", (
                f"{chave}: a base da luz não leva a cor da unidade")


def test_o_terror_troca_o_piscar_pela_batida_e_nada_passa_do_teto() -> None:
    # D-2010-O-TERROR-TROCA-O-PISCAR-PELA-BATIDA
    """Régua 6: o Terror não pisca (batimento na luz, Batida nos motores); nada passa de 3/s."""
    terror = ej.POR_CHAVE["terror"]
    assert terror.receita_invisivel is not None
    assert terror.receita_invisivel.luz != "pisca"
    assert terror.receita_invisivel.luz_base == "batimento"
    assert pv.POR_ESTILO["terror"] == "batida"
    prof = _aplicado("terror")
    for u in MESA:
        assert (_luz(prof, u["uniq"]).efeito or "").startswith("batimento")
    for e in ej.ESTILOS:
        if e.receita_invisivel is not None:
            assert e.receita_invisivel.luz_por_segundo <= ej.TETO_DO_PISCAR, e.chave


@pytest.mark.parametrize("chave", sorted(FRENTE))
def test_toda_chave_da_tabela_existe(chave: str) -> None:
    """A tabela e o catálogo falam das mesmas chaves (o Arco fica de fora de propósito)."""
    assert chave in ej.POR_CHAVE


@pytest.mark.parametrize("chave", sorted(TABELA))
def test_o_motor_do_tato_liga_o_que_a_receita_do_estilo_pede(chave: str) -> None:
    """Régua 7: o estilo sozinho, sem escolha nenhuma por controle, liga o contínuo e os motores.

    A tabela diz o que o estilo pede; aqui é o motor do tato que tem de acender: o Som no corpo
    da Corrida, o Grão da Simulação, o Motor de época do Retrô, o padrão dos motores e a Pancada
    do lado da Luta.

    MORDIDA: tire `som_no_corpo_escolhido`, `grao_escolhido`, `motor_de_epoca_escolhido`,
    `padroes_escolhidos` ou `pancada_escolhida` do `receita_do_estilo` e isto reprova (a tabela da
    régua 1 seguiria verde).
    """
    _r2, _l2, forma, motores, _base, _brilho = TABELA[chave]
    from types import SimpleNamespace

    receita = tv.receita_do_perfil(SimpleNamespace(estilo=chave))
    assert receita.som_no_corpo_escolhido == (forma == fh.SOM_NO_CORPO), chave
    assert receita.grao_escolhido == (forma == fh.GRAO), chave
    assert receita.motor_de_epoca_escolhido == (forma == fh.MOTOR_DE_EPOCA), chave
    assert receita.padroes_escolhidos == (motores is not None), chave
    assert receita.pancada_escolhida == (motores == "pancada_do_lado"), chave
    vale = fh.forma_que_vale(None, chave)
    assert vale == (None if forma == fh.SEM_EFEITO else forma), chave
    assert pv.padrao_que_vale(pv.DO_ESTILO, chave) == motores, chave
