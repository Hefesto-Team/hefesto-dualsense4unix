#!/usr/bin/env python3
"""A RÉGUA DO CASAMENTO: o que o pacote emite tem onde cair na página.

POR QUE ELA EXISTE, medido em 01/09/2026 quando o piloto único abriu pela
primeira vez: a aba Jogar, com um pacote de CINCO valores, pintou **UM**. Nada
acusou — `querySelector` de um endereço que não existe devolve `null`, a pintura
escreve zero, e zero passa por "nada mudou".

O defeito era estrutural: **os endereços da página e as chaves do pacote foram
escolhidos separadamente.** O pacote emitia `mascara`, a página tinha
`identidade`; emitia `conta_b`, a página tinha `conta-b`. As palavras diziam a
mesma coisa e nenhuma máquina sabia disso.

O QUE ESTA RÉGUA COBRA, e é o mínimo que impede a recaída:

1. toda aba com pacote casa pelo menos um endereço com a página PUBLICADA;
2. as abas que já casavam N não passam a casar menos;
3. o `casamento.py` — que é o instrumento — acha os três vocabulários.

Ela NÃO cobra que tudo case. Um pacote pode emitir mais do que a tela mostra (o
`rumble_ff` traz contagens que o desenho dela não pede), e uma página pode ter
endereços que só o piloto daquela aba usa (os rótulos `l3`/`r3` da Controles).
O que ela proíbe é o ZERO, e a queda.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: O PISO MEDIDO em 01/09/2026, com o alinhamento fechado. Cada número é quantos
#: endereços daquela página têm quem os pinte. Eles só sobem: uma queda é um
#: pacote que parou de emitir, ou um gerador que parou de marcar — e as duas
#: coisas são invisíveis na tela, que é o motivo de estarem escritas aqui.
#:
#: `07-lancadores.html` NÃO está na lista, e a razão MUDOU em 02/09/2026.
#:
#: Era: ela não tinha pacote, por decisão dela em 01/09 (*"a única que não
#: faremos, só deixamos o botão levando pra ela, é a de lançadores."*).
#:
#: É: ela TEM pacote (`a07_lancadores.py`, 26 endereços) desde que a decisão de
#: 02/09 a reabriu (*"não daria para incluir G e F aqui? (…) temos um mapa
#: funcional disso no gtk."*). O que falta é a PÁGINA: esta régua mede contra o
#: **publicado**, e os endereços da 07 estão na BANCADA — publicar é ato dela,
#: `scripts/check_o_desenho_aprovado.py --publicar 07`. Pôr um piso aqui antes
#: disso faria a régua exigir um casamento contra a página de 31/08, que não tem
#: um endereço sequer.
#:
#: **Quem publicar a 07 acrescenta a linha aqui**, com o número que
#: `casamento.medir("07-lancadores.html")["casam"]` devolver — enquanto ela não
#: estiver na lista, uma queda naquela aba é invisível para esta régua.
#: A régua que cobre a 07 hoje é `test_a_aba_lancadores_diz_a_verdade.py`, que
#: mede contra a BANCADA de propósito.
PISO = {
    "01-jogar.html": 9,
    "02-controles.html": 9,
    "03-gatilhos.html": 19,
    "04-iluminacao.html": 8,
    "05-vibracao.html": 9,
    "06-navegacao.html": 4,
    "08-conexoes.html": 5,
    "09-sistema.html": 9,
    "10-perfis.html": 10,
}


#: O perfil de mentira, com a forma do disco dela. **Ele é obrigatório**: sem
#: perfil, o pacote da Gatilhos emite `Desligado` nos dois lados e o da Perfis
#: lista zero — e o piso desta régua cairia por falta de DADO, não por
#: regressão. O `conftest.py` desta casa desvia `HOME` e os `XDG_*` para um lar
#: de mentira, que nasce sem perfil nenhum.
PERFIL = {
    "name": "Régua", "version": 1, "priority": 50, "match": {"type": "criteria"},
    "triggers": {"left": {"mode": "Rigid", "params": [0, 180]},
                 "right": {"mode": "Vibration", "params": [3, 8, 20]}},
    "leds": {"lightbar": [255, 80, 0], "player_leds": [True] * 5,
             "lightbar_brightness": 0.7},
    "rumble": {"passthrough": True},
    "mouse": {"enabled": True, "speed": 6, "scroll_speed": 1},
}


@pytest.fixture(scope="module")
def casamento(tmp_path_factory):
    import casamento as mod
    from pacotes import perfil

    pasta = tmp_path_factory.mktemp("perfis")
    (pasta / "regua.json").write_text(json.dumps(PERFIL), encoding="utf-8")
    perfil.pasta = lambda: pasta
    mod.ESTADO_DA_REGUA = {"active_profile": "regua", "rumble_policy": "balanceado"}
    return mod


def test_o_instrumento_acha_os_tres_vocabularios(casamento):
    """`data-campo`, `data-papel` e `data-hef` — as dez páginas usam os três.

    Medido: oito abas endereçam por `data-campo`, a Vibração tem 28
    `data-papel` (um PAR com `data-lado`) e a Perfis tem 77 `data-hef` (nomes
    com ponto). Cada um nasceu com o piloto da sua aba, e os pilotos vivem.

    Uma régua que só contasse `data-campo` daria a Perfis como página SEM
    endereço nenhum — e foi assim que ela apareceu com 3 de 80.
    """
    campos, _ = casamento.do_html("10-perfis.html")
    assert len(campos) >= 14, (
        f"a Perfis tem {len(campos)} endereços e ela endereça por `data-hef` — "
        f"se caiu para 3, a régua voltou a contar só `data-campo`.")
    campos5, _ = casamento.do_html("05-vibracao.html")
    assert len(campos5) >= 10, "a Vibração endereça por `data-papel`"


@pytest.mark.parametrize("pagina", sorted(PISO))  # (noqa-acento)  (nome do parâmetro)
def test_a_aba_casa_pelo_menos_o_piso(casamento, pagina):
    """Zero é ERRO, e uma queda também.

    A mordida: renomeie uma chave no pacote daquela aba (`identidade` →
    `mascara`, por exemplo) e este teste reprova com a diferença nomeada. Foi
    exatamente esse renome, nascido de um descuido em dois lados diferentes, que
    deixou a aba Jogar pintando 1 de 5.
    """
    m = casamento.medir(pagina)
    assert m["emite"], f"{pagina}: o pacote não emitiu nada — ver a régua do despachante"
    assert len(m["casam"]) >= PISO[pagina], (
        f"{pagina} casa {len(m['casam'])} endereços e o piso medido é "
        f"{PISO[pagina]}.\n"
        f"  casam : {sorted(m['casam'])}\n"
        f"  órfãos (o pacote manda e a tela não tem onde): {sorted(m['orfaos'])}\n"
        f"  vazios (a tela tem onde e ninguém manda): {sorted(m['vazios'])}\n"
        f"Uma queda aqui não aparece na tela: o valor simplesmente não é escrito.")


def test_nenhuma_aba_com_pacote_casa_zero(casamento):
    """O resumo, e é o que o `casamento.py` devolve como rc=1.

    Antes do alinhamento de 01/09 eram QUATRO abas com zero — 05, 08, 09 e 10.
    """
    zeradas = [p for p in PISO if casamento.medir(p)["emite"]
               and not casamento.medir(p)["casam"]]
    assert zeradas == [], (
        f"estas abas emitem valores e não têm onde pô-los: {zeradas}. "
        f"É a forma exata do defeito que esta régua existe para pegar — a "
        f"pintura escreve zero e nada acusa.")
