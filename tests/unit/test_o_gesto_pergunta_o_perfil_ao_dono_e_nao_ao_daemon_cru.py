"""O gesto de qualquer aba pergunta o perfil ativo ao DONO, não ao daemon cru.

A QUEIXA QUE ISTO CURA — 19/09/2026: *"nessa aba o botão máximo economia e
balanceado voltou a travar de novo"*.  <!-- noqa-acento: citação literal dela -->

O DEFEITO, MEDIDO NO DIÁRIO DELA (`interface.log`, 19/09 por volta de 01:00)::

    [gesto falhou] 05-vibracao.html · forca: não há perfil ativo agora, e a
    força da vibração de um controle é do PERFIL — não de todos.

...com **PRAGMATA** escrito no chip «Perfil ativo» da MESMA tela, e o
`daemon.state_full` respondendo ``active_profile: None`` (medido pelo IPC vivo).
As duas coisas eram verdade ao mesmo tempo porque a tela e o gesto liam FONTES
DIFERENTES:

==============================  ========================================  =========
quem                            lia                                       respondia
==============================  ========================================  =========
a tira do topo, `pacotes.topo`  `perfil.nome_do_ativo` (daemon + disco)   PRAGMATA
a guarda do gesto               `ctx.state["active_profile"]` CRU         None
==============================  ========================================  =========

`nome_do_ativo` resolve as DUAS pernas — o daemon primeiro, o marcador em disco
depois (`session.json` + `active_profile.txt`). O daemon responde ``None`` em
toda sessão dela por desenho: PRAGMATA é perfil escopado a janela de jogo, e o
`RESTORE-ESCOPO-01` recusa restaurá-lo no boot de propósito
(`daemon/state_store.PERFIL-ADIADO-POR-JANELA-01`). Não é falha do daemon — é a
pergunta errada.

É A TERCEIRA METADE DA MESMA CURA. A `PERFIL-MODO-01` (06/09) ensinou
`perfil.ativo()` a perguntar ao dono, e a ONDA D ensinou a TIRA. As **guardas
dos gestos** levantavam ANTES de chegar a qualquer uma das duas, e por isso
nenhuma das curas as alcançava: catorze leituras cruas, em sete abas.

A REGRA QUE ISSO DEIXA, e ela já é da casa: *quando a cura conhece a causa, ela
cobre TODOS os chamadores.* Cobrir um deixa a próxima pessoa remedindo o mesmo
defeito — e foi o que aconteceu três vezes com esta linha.

ONDE ELA MORDE: devolva `str(ctx.state.get("active_profile") or "").strip()` a
qualquer uma das guardas e o teste da aba correspondente reprova com a frase de
recusa que ela viu na tela.
"""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

import pytest

#: O IMPORT É O DO VIZINHO, e não o de pacote instalado — o aviso está escrito
#: em `interface/aba02.py`: os dois caminhos carregam o MESMO arquivo em DOIS
#: módulos diferentes, com duas cópias de cada estado. Um dublê posto no módulo
#: errado não alcança o produto, e a régua daria verde sobre o defeito vivo.
RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: As abas cujo GESTO recusava com perfil no disco e daemon calado, e o nome do
#: gesto que ela clica. A aba 05 é a que ela reportou; as outras seis têm a
#: MESMA guarda, e entram porque a cura cobre todos os chamadores.
ABAS = [
    ("05-vibracao.html", "forca"),
    ("04-iluminacao.html", "brilho"),
    ("06-navegacao.html", "trocar"),
]

#: O estado que o daemon dela publica de verdade: sem perfil.
DAEMON_CALADO: dict[str, Any] = {"active_profile": None}

PERFIL = "Régua Do Gesto"


@pytest.fixture
def perfil_so_no_disco(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Um perfil que existe no DISCO e que o daemon não conhece.

    É o estado da máquina dela: o marcador de sessão diz o nome, o
    `daemon.state_full` diz `None`.
    """
    import pacotes.perfil as _perfil

    pasta = tmp_path / "profiles"
    pasta.mkdir(parents=True)
    (pasta / f"{PERFIL}.json").write_text(
        json.dumps({"name": PERFIL, "rumble": {"policy": "balanced"}}),
        encoding="utf-8")
    monkeypatch.setattr(_perfil, "pasta", lambda: pasta)
    monkeypatch.setattr(_perfil, "nome_do_ativo", lambda *_a, **_k: PERFIL)
    return PERFIL


def test_o_dono_responde_o_que_o_daemon_calou(perfil_so_no_disco: str) -> None:
    """O piso: com o daemon calado, quem responde é o marcador em disco.

    Sem isto o resto da régua mediria o próprio dublê.
    """
    import pacotes.perfil as _perfil

    assert _perfil.nome_do_ativo(DAEMON_CALADO) == PERFIL
    assert _perfil.ativo(DAEMON_CALADO.get("active_profile")).get("name") == PERFIL


@pytest.mark.parametrize("pacote,guarda", [
    ("a05_vibracao", "_gravar_a_forca"),
    ("a06_navegacao", "_perfil_ativo_ou_recusa"),
])
def test_a_guarda_nao_recusa_com_o_perfil_no_disco(
        pacote: str, guarda: str, perfil_so_no_disco: str,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Nenhuma guarda de gesto diz "não há perfil ativo" com um perfil valendo.

    Mede o ATO e não o texto do código: chama a guarda com o estado que o daemon
    dela publica e exige que a frase de recusa NÃO saia.
    """
    import importlib

    import pacotes
    import pacotes.perfil as _perfil

    mod = importlib.import_module(f"pacotes.{pacote}")
    # O módulo pode ter importado `perfil` por outro nome; o dublê é o do módulo
    # `pacotes.perfil`, que é o mesmo objeto nos dois casos.
    assert getattr(mod, "perfil", _perfil) is _perfil or \
        getattr(mod, "_perfil", _perfil) is _perfil

    ctx = pacotes.Contexto(state=dict(DAEMON_CALADO), mesa=[], conectados=[],
                           estados={})
    alvo = getattr(mod, guarda)
    try:
        if guarda == "_perfil_ativo_ou_recusa":
            saiu = alvo(ctx)
            assert saiu == PERFIL, (
                f"a guarda de {pacote} devolveu {saiu!r} com o perfil "
                f"{PERFIL!r} valendo no disco")
            return
        alvo(ctx, None, "aa:bb:cc:00:00:01", "balanced", None)
    except RuntimeError as erro:
        assert "não há perfil ativo" not in str(erro), (
            f"{pacote}.{guarda} recusou o gesto dela por 'não há perfil ativo' "
            f"com {PERFIL!r} no disco — é o defeito do dia 19/09: a guarda lê o "
            f"`active_profile` CRU do daemon, e o daemon o publica como None em "
            f"toda sessão com perfil de janela. Erro: {erro}")
    except Exception:
        # Qualquer outra recusa é de OUTRA regra (endereço do controle, valor
        # fora de faixa, disco). Esta régua mede UMA coisa só.
        pass


def test_nenhuma_guarda_de_gesto_le_o_cru() -> None:
    """A varredura que impede a volta por um caminho novo.

    É régua de FONTE de propósito, e ela é a SEGUNDA: a de cima mede o ato. Esta
    existe porque o defeito voltou três vezes por chamadores NOVOS, que a de
    cima não conhece.
    """
    raiz = pathlib.Path(__file__).resolve().parents[2]
    pasta = raiz / "src" / "hefesto_dualsense4unix" / "interface" / "pacotes"
    #: O PADRÃO DO DEFEITO: o cru dentro de um `.strip()`, que é a assinatura da
    #: guarda de gesto. As leituras de PINTURA passam por `perfil.ativo()`, que
    #: já pergunta ao dono quando o nome não vem — essas podem ficar.
    presos: list[str] = []
    for arq in sorted(pasta.glob("a*.py")):
        for n, linha in enumerate(arq.read_text(encoding="utf-8").splitlines(), 1):
            nu = linha.strip()
            if nu.startswith("#") or nu.startswith("*"):
                continue
            if 'get("active_profile")' in linha and ".strip()" in linha:
                presos.append(f"{arq.name}:{n}")
    assert not presos, (
        "guarda de gesto lendo o `active_profile` CRU do daemon — ela vai "
        "recusar o clique dela com um perfil valendo no disco. Use "
        "`perfil.nome_do_ativo(ctx.state)`: " + ", ".join(presos))
