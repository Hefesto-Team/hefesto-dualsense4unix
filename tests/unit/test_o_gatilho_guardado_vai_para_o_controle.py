#!/usr/bin/env python3
"""A RÉGUA DO "Guardar esse efeito": o gatilho vai para o OVERRIDE do controle.

A ABA GATILHOS APLICA NA HORA — é a decisão dela de 01/09/2026, *"clicar já
aplica"*. Mas aplicar não guarda: o efeito vale até a próxima troca de perfil, e
o disco continua com o que estava lá. Este botão é o ponto de gravação.

DE ONDE VEM O QUE ELE GRAVA, e é o que torna esta aba diferente das outras: o
DualSense **não devolve** o modo em que está. Gatilho é comando de ida, o
`state_full` não o publica, e por isso `modo` e `pronto` estão no `SEM_ECO`
desta aba. O único lugar onde a escolha viva existe é a TELA — daí a `forma`.

AS QUATRO COISAS QUE ESTA RÉGUA COBRA:

1. **Vai para o OVERRIDE DO CONTROLE, nunca para o global.** A aba mostra uma
   coluna por controle; gravar no global faria o "Guardar" do P2 mudar o gatilho
   do P1 — a mesma contradição que mantém o `mic-escopo` recusando.
2. **A chave é o `uniq` NORMALIZADO.** `d4:2f:…` onde o disco guarda `d42f…`
   criaria um segundo dono para o mesmo controle.
3. **Os ajustes vão na ordem do SPEC, e o que faltou cai no PADRÃO do modo.**
   O daemon lê a lista posicional inteira; uma lista curta muda o que ela não
   escolheu.
4. **Nada mudou, nada grava.** Um `profile.switch` no meio de uma partida não é
   de graça.

A MORDIDA: faça o gesto gravar em `prof.triggers` (o global) em vez do override
— o caso 1 reprova dizendo que o Guardar de um controle mexeu no outro.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: Faixa sintética da casa — há dois portões de anonimato nesta árvore.
UNIQ = "aa:bb:cc:00:00:01"
CHAVE = "aabbcc000001"


class PonteDeMentira:
    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def profile_switch(self, nome: str) -> bool:
        self.chamadas.append("profile_switch")
        return True

    def chamar(self, metodo: str, **_: Any) -> bool:
        self.chamadas.append(metodo)
        return True


@pytest.fixture
def pac():
    import pacotes

    return pacotes


@pytest.fixture
def gesto(pac):
    fn = pac.gesto_da_pagina("03-gatilhos.html", "guardar")
    assert fn is not None, "03-gatilhos.html:guardar perdeu o dono"
    return fn


@pytest.fixture
def disco(monkeypatch):
    """Um disco de mentira, com um perfil de verdade dentro.

    O `Profile` É O DE VERDADE, e não um dublê: o que esta régua mede é o que
    vai para o esquema — um dublê aceitaria um `ControllerOverrides` malformado
    e a régua ficaria verde sobre um perfil que o disco recusaria.
    """
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import Profile

    estado = {"Mortal Kombat": Profile(name="Mortal Kombat", match={"type": "any"})}
    gravados: list[Profile] = []
    monkeypatch.setattr(loader, "load_profile", lambda n: estado[n], raising=False)
    monkeypatch.setattr(loader, "save_profile",
                        lambda prof, **_: gravados.append(prof), raising=False)
    return estado, gravados


def _ctx(pac, ativo: str = "Mortal Kombat"):
    dele = {"uniq": UNIQ, "transport": "usb", "connected": True}
    return pac.Contexto(state={"active_profile": ativo, "controllers": [dele]},
                        mesa=[], conectados=[dele], estados={})


def _forma(**extra: str) -> dict[str, str]:
    """A coluna como o piloto a recolhe: os dois modos e os ajustes."""
    base = {"modo-chave-e": "Rigid", "modo-chave-d": "Off"}
    base.update(extra)
    return base


def test_grava_no_override_do_controle_e_nao_no_global(pac, gesto, disco) -> None:
    _estado, gravados = disco
    p = PonteDeMentira()

    gesto(_ctx(pac), {"uniq": UNIQ, "forma": _forma()}, p)

    assert len(gravados) == 1, f"gravou {len(gravados)} vez(es)"
    prof = gravados[0]
    assert CHAVE in (prof.controllers or {}), (
        f"o override do controle não foi criado; controllers={prof.controllers!r}")
    assert prof.controllers[CHAVE].triggers.left.mode == "Rigid"
    assert prof.triggers.left.mode == "Off", (
        "o Guardar mexeu na seção GLOBAL do perfil. A aba mostra uma coluna POR "
        "CONTROLE — gravar no global faria o Guardar do P2 mudar o gatilho do P1.")


def test_a_chave_do_override_e_o_uniq_normalizado(pac, gesto, disco) -> None:
    """`d4:2f:…` onde o disco guarda `d42f…` cria um segundo dono do mesmo controle."""
    _, gravados = disco
    gesto(_ctx(pac), {"uniq": UNIQ, "forma": _forma()}, PonteDeMentira())
    chaves = list(gravados[0].controllers or {})
    assert chaves == [CHAVE], f"as chaves saíram {chaves}, esperava {[CHAVE]}"


def test_os_ajustes_vao_na_ordem_do_spec(pac, gesto, disco) -> None:
    """O índice da barra na tela É o índice do parâmetro no daemon."""
    _, gravados = disco
    gesto(_ctx(pac),
          {"uniq": UNIQ,
           "forma": _forma(**{"aj-val-e-0": "9", "aj-val-e-1": "200"})},
          PonteDeMentira())
    params = gravados[0].controllers[CHAVE].triggers.left.params
    assert params[0] == 9 and params[1] == 200, (
        f"os ajustes saíram {params} — o primeiro e o segundo campo da coluna "
        f"têm de virar o primeiro e o segundo parâmetro do modo.")


def test_o_que_a_tela_nao_disse_cai_no_padrao_do_modo(pac, gesto, disco) -> None:
    """Lista curta muda o que ela não escolheu — o daemon lê a posicional inteira."""
    from pacotes.a03_gatilhos import _padroes

    _, gravados = disco
    gesto(_ctx(pac), {"uniq": UNIQ, "forma": _forma(**{"aj-val-e-0": "9"})},
          PonteDeMentira())
    params = list(gravados[0].controllers[CHAVE].triggers.left.params)
    padrao = _padroes("Rigid")
    assert len(params) == len(padrao), (
        f"gravou {len(params)} parâmetro(s) e o modo Rigid tem {len(padrao)}")
    assert params[1:] == padrao[1:], (
        "o que a coluna não trouxe não caiu no padrão do modo")


def test_valor_que_nao_e_numero_cai_no_padrao(pac, gesto, disco) -> None:
    """Zero é uma MEDIDA. O que a tela não soube dizer não pode virar zero."""
    from pacotes.a03_gatilhos import _padroes

    _, gravados = disco
    gesto(_ctx(pac), {"uniq": UNIQ, "forma": _forma(**{"aj-val-e-0": "—"})},
          PonteDeMentira())
    params = list(gravados[0].controllers[CHAVE].triggers.left.params)
    assert params[0] == _padroes("Rigid")[0], (
        f"um travessão virou {params[0]!r} — o que a tela não disse cai no padrão")


def test_nada_mudou_nada_grava(pac, gesto, disco) -> None:
    _, gravados = disco
    p = PonteDeMentira()
    gesto(_ctx(pac), {"uniq": UNIQ, "forma": _forma()}, p)
    # O DUBLÊ DO DISCO NÃO GUARDA O GRAVADO DE VOLTA, então o segundo clique
    # precisa ler o que o primeiro escreveu — é o que a máquina dela faria.
    estado, _ = disco
    estado["Mortal Kombat"] = gravados[0]
    antes = len(gravados)
    p2 = PonteDeMentira()
    gesto(_ctx(pac), {"uniq": UNIQ, "forma": _forma()}, p2)
    assert len(gravados) == antes, "regravou um perfil idêntico"
    assert p2.chamadas == [], (
        f"pediu {p2.chamadas} ao daemon sem ter o que mudar — um `profile.switch` "
        f"no meio de uma partida não é de graça")


def test_sem_forma_recusa_dizendo(pac, gesto, disco) -> None:
    """O daemon não devolve o gatilho: sem a forma, não há o que guardar."""
    _, gravados = disco
    with pytest.raises(RuntimeError) as erro:
        gesto(_ctx(pac), {"uniq": UNIQ}, PonteDeMentira())
    assert "coluna" in str(erro.value).lower(), str(erro.value)
    assert gravados == []


def test_sem_perfil_ativo_recusa_dizendo(pac, gesto, disco) -> None:
    _, gravados = disco
    with pytest.raises(RuntimeError) as erro:
        gesto(_ctx(pac, ativo=""), {"uniq": UNIQ, "forma": _forma()}, PonteDeMentira())
    assert "perfil" in str(erro.value).lower(), str(erro.value)
    assert gravados == []


def test_clique_solto_recusa(pac, gesto, disco) -> None:
    """O gatilho é de um controle, não da mesa."""
    with pytest.raises(ValueError):
        gesto(_ctx(pac), {"forma": _forma()}, PonteDeMentira())


def test_o_botao_pede_a_forma_da_coluna() -> None:
    """A metade JS da cura: sem `data-hef-forma`, o gesto só sabe recusar.

    E o valor tem de ser `@controle`, não um `id`: as colunas não têm `id` — elas
    se endereçam por `data-controle`, que é o vocabulário que a mesa já usa.
    """
    from hefesto_dualsense4unix.interface import onde

    html = (onde.PUBLICADO / "03-gatilhos.html").read_text(encoding="utf-8")
    assert html.count('data-gesto="guardar" data-hef-forma="@controle"') >= 4, (
        "as quatro colunas precisam do `data-hef-forma` no Guardar — sem ele o "
        "piloto não recolhe a coluna e o botão passa a recusar")
