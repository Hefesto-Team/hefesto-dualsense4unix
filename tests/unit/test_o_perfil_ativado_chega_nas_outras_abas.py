"""O perfil ativado chega às OUTRAS abas — PERFIL-MODO-01, Passo 2 (06/09/2026).

A linha 358 do CSV da paridade, `FALTA_NO_HTML`, com o sintoma escrito:

    *"as abas que leem o PERFIL do disco — gatilhos, brilho, atalhos —
    continuam mostrando o perfil anterior até o próximo tique que releia disco,
    e nenhum tique o faz."*

O QUE FOI MEDIDO, e a causa não era a que a linha supunha
---------------------------------------------------------
Os pacotes das outras abas **relêem** o disco a cada tique — `a03_gatilhos`,
`a04_iluminacao`, `a06_navegacao` e `a08_conexoes` chamam
`perfil.ativo(ctx.state.get("active_profile"))`, e `perfil.ativo` abre o `.json`
em toda chamada. O que não acontecia era o outro lado: **o nome nunca chegava**.

    perfil.ativo("régua")   ->  {'name': 'régua', …}
    perfil.ativo(None)      ->  {}                       <- o que as abas viam
    perfil_que_esta_valendo ->  PerfilQueVale('régua', fonte='disco')

``state["active_profile"]`` é ``null`` sempre que o daemon não sabe dizer — e o
`perfil_que_esta_valendo` de `profiles_actions` (§P1) existe desde 24/08 EXATO
para isso: *"Sobrevive ao daemon responder `active_profile: null`, que é o
estado da máquina dela hoje"*. As abas novas liam o campo CRU e caíam no `{}`.

**E o «Ativar» não curava nada disso**: `profile.switch` grava os dois
marcadores manuais em disco (`session.json` + `active_profile.txt`), que é
justamente o que o dono do §P1 lê na segunda perna — e ninguém perguntava a ele.

A CURA É DO DONO DO ESTADO, não de uma segunda leitura na aba Perfis:
`pacotes/perfil.nome_do_ativo`, com `perfil.ativo` caindo nele. Cobre TODOS os
chamadores diretos de uma vez — é a regra que 05/09 deixou escrita.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from hefesto_dualsense4unix.interface.pacotes import Contexto, perfil

#: OS DOIS PERFIS: o que estava valendo e o que ela ATIVOU. Dois, e não um,
#: porque o defeito é de TROCA — com um só, uma aba congelada no perfil anterior
#: mostraria o mesmo dado e a régua ficaria verde sobre ele.
DE_ONTEM = "Perfil de ontem"
ATIVADO = "Perfil que ela ativou"

#: QUEM AINDA CURTO-CIRCUITA O DONO — declarado, com a razão e o endereço.
#:
#: `a05_vibracao._perfil_ativo:247` faz `return _perfil.ativo(nome) if nome
#: else {}`: a guarda decide ANTES de chamar o dono, então a cura de
#: `perfil.ativo` não o alcança e, com o daemon calado, aquela aba volta a ver
#: `{}` — o teto de vibração e a ressalva da mesa em travessão.
#:
#: **ELE ESTÁ FORA DA POSSE DA `PERFIL-MODO-01`** e a cura é de uma linha:
#: trocar a expressão por `return _perfil.ativo(nome)`. Está no relatório
#: `docs/process/agentes/2026-09-06/PERFIL-MODO-01.md`.
CURTO_CIRCUITO_DECLARADO = {"a05_vibracao.py"}


@pytest.fixture
def pasta_de_perfis(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Dois perfis num diretório temporário. Nada toca a pasta DELA."""
    pasta = tmp_path / "perfis"
    pasta.mkdir()
    (pasta / "perfil_de_ontem.json").write_text(json.dumps({
        "name": DE_ONTEM, "priority": 10,
        "leds": {"lightbar_brightness": 20},
    }), encoding="utf-8")
    (pasta / "perfil_que_ela_ativou.json").write_text(json.dumps({
        "name": ATIVADO, "priority": 90,
        "leds": {"lightbar_brightness": 90},
    }), encoding="utf-8")
    monkeypatch.setattr(perfil, "pasta", lambda: pasta)
    return pasta


@pytest.fixture
def marcador(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """O marcador em disco que o `profile.switch` grava — o dublê dele.

    ELE SABE RECUSAR: com `{"nome": ""}` a resolução devolve vazio, que é o
    caminho "ninguém ativou nada" — e é o que faz esta régua exercitar as duas
    respostas em vez de só a boa.
    """
    estado = {"nome": DE_ONTEM}
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.resolve_boot_profile",
        lambda: estado["nome"] or None)
    return estado


def _ctx_com_daemon_calado() -> Contexto:
    """O estado VIVO da máquina dela: o daemon responde, e não sabe o perfil."""
    return Contexto(state={"active_profile": None})


# --------------------------------------------------------------------------
# 1. O DEFEITO, E A CURA — com o daemon calado, as outras abas viam NADA
# --------------------------------------------------------------------------

def test_com_o_daemon_calado_as_outras_abas_leem_o_perfil_do_disco(
    pasta_de_perfis: Any, marcador: dict[str, str],
) -> None:
    """MORDIDA: troque `nome = nome_do_ativo(None)` por `return {}` em
    `perfil.ativo` e isto reprova — é o estado de antes de 06/09, em que
    gatilho, brilho e atalhos viravam travessão em TODA aba."""
    ctx = _ctx_com_daemon_calado()
    lido = perfil.ativo(ctx.state.get("active_profile"))
    assert lido.get("name") == DE_ONTEM, (
        "com o daemon calado, as outras abas não leem perfil nenhum — é a "
        "AUSÊNCIA de dado, que se lê como «a mudança não pegou»")


def test_o_ativar_troca_o_que_as_outras_abas_mostram(
    pasta_de_perfis: Any, marcador: dict[str, str],
) -> None:
    """O TIQUE SEGUINTE: ela ativa, e a outra aba mostra o valor NOVO.

    O `profile.switch` grava os dois marcadores manuais em disco — é isso que o
    dublê do `marcador` representa. A régua faz a leitura ANTES e DEPOIS, no
    mesmo processo, como dois tiques consecutivos.

    MORDIDA: com a cura arrancada as DUAS leituras devolvem `{}`, e a asserção
    do brilho reprova dizendo que a aba Iluminação mostraria travessão nos dois
    tiques — antes e depois de ela ativar.
    """
    ctx = _ctx_com_daemon_calado()
    antes = perfil.ativo(ctx.state.get("active_profile"))
    assert (antes.get("leds") or {}).get("lightbar_brightness") == 20

    marcador["nome"] = ATIVADO  # <- o que o `profile.switch` acabou de gravar

    depois = perfil.ativo(ctx.state.get("active_profile"))
    assert depois.get("name") == ATIVADO, (
        "o «Ativar» gravou o marcador em disco e a leitura do tique seguinte "
        "continua no perfil de ontem — nada relê o perfil")
    assert (depois.get("leds") or {}).get("lightbar_brightness") == 90, (
        "a aba Iluminação continuaria mostrando o brilho do perfil anterior")


# --------------------------------------------------------------------------
# 2. O DONO É UM SÓ — e o daemon vence quando ele sabe
# --------------------------------------------------------------------------

def test_o_daemon_vence_quando_ele_sabe(
    pasta_de_perfis: Any, marcador: dict[str, str],
) -> None:
    """A ordem do §P1: o daemon primeiro, o marcador em disco depois.

    Ele é quem APLICOU as seções no controle, e um autoswitch por janela só
    existe lá. Inverter a ordem faria um perfil trocado pelo jogo em foco
    aparecer como o de ontem.
    """
    ctx = Contexto(state={"active_profile": ATIVADO})
    assert perfil.nome_do_ativo(ctx.state) == ATIVADO
    marcador["nome"] = DE_ONTEM
    assert perfil.nome_do_ativo(ctx.state) == ATIVADO, (
        "o marcador em disco venceu o daemon — a ordem do §P1 é o contrário")


def test_sem_daemon_e_sem_marcador_a_resposta_e_vazia(
    pasta_de_perfis: Any, marcador: dict[str, str],
) -> None:
    """Régua que só sabe passar não é régua: o caminho do "ninguém sabe".

    `{}` aqui é o estado HONESTO — a tela mostra travessão porque não há
    perfil, que é diferente de mostrar travessão porque ninguém perguntou.
    """
    marcador["nome"] = ""
    assert perfil.nome_do_ativo({"active_profile": None}) == ""
    assert perfil.ativo(None) == {}


def test_nome_do_ativo_nunca_levanta(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ela é pintura a duas vezes por segundo: exceção aqui derruba a aba.

    MORDIDA: tire o `try/except` de `perfil.nome_do_ativo` e isto reprova com o
    `RuntimeError` do dublê subindo — que na janela viva é a aba inteira
    congelando por causa de um arquivo de sessão.
    """
    def _explode() -> str:
        raise RuntimeError("o arquivo de sessão está ilegível")

    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.resolve_boot_profile", _explode)
    assert perfil.nome_do_ativo({"active_profile": None}) == ""


# --------------------------------------------------------------------------
# 3. A CURA COBRE TODOS OS CHAMADORES — o censo, por árvore de sintaxe
# --------------------------------------------------------------------------

def test_todo_pacote_que_le_o_perfil_passa_pelo_dono() -> None:
    """O censo dos chamadores de `perfil.ativo`, e quem ainda os guarda.

    A regra de 05/09: *quando a cura conhece a causa, ela cobre TODOS os
    chamadores*. Aqui a cura mora no dono (`perfil.ativo`), então quem passa o
    nome CRU já está coberto — o que esta régua persegue é o contrário: um
    chamador que **curto-circuita** o dono com um `if nome else {}` antes de
    chamá-lo, porque esse não é alcançado pela cura e volta a ver `{}`.

    O ÚNICO DECLARADO É O `a05_vibracao`, e ele está FORA da posse desta
    sprint — está no relatório, com a linha exata. Um segundo aparecer aqui é
    dívida nova e tem de ser declarada junto com a razão.
    """
    import ast
    import pathlib

    pacotes = pathlib.Path(
        perfil.__file__).resolve().parent  # `interface/pacotes/`
    curto_circuito: set[str] = set()
    for arquivo in sorted(pacotes.glob("a*.py")):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            # `X.ativo(nome) if nome else {}` — o `IfExp` com a chamada dentro.
            if not isinstance(no, ast.IfExp):
                continue
            chamadas = [d for d in ast.walk(no.body) if isinstance(d, ast.Call)]
            for c in chamadas:
                alvo = c.func
                if isinstance(alvo, ast.Attribute) and alvo.attr == "ativo":
                    curto_circuito.add(arquivo.name)
    assert curto_circuito <= CURTO_CIRCUITO_DECLARADO, (
        f"{sorted(curto_circuito - CURTO_CIRCUITO_DECLARADO)} pergunta(m) "
        f"`if nome` ANTES de "
        f"chamar `perfil.ativo` — a cura do dono não alcança quem não o chama, "
        f"e com o daemon calado essa aba volta a ver `{{}}`. Ou tira a guarda, "
        f"ou declara aqui com a razão.")
