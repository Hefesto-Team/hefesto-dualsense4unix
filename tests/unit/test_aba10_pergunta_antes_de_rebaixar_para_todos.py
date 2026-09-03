"""Trocar "Funciona em" para "Todos" APAGA a regra do jogo. Agora pergunta antes.

COR-A + SALVAR-NAO-REBAIXA-02, trazidas para a interface nova em 03/09/2026.

A janela estável tem CINCO perguntas no Salvar, e cada uma nasceu de um defeito
medido. A forma dos gestos da interface nova — **um campo por vez, sem
rascunho** — dispensa três delas: gravar UM campo não pode rebaixar
``match`` e ``priority`` juntos, que era o caminho do defeito de 27/07 (o
``Pragmata`` era regra de jogo com prioridade 100 e amanheceu catch-all).

**Esta continuava aberta e alcançável em UM clique.** Escolher "Todos" no
seletor de um perfil de jogo gravava o catch-all calado: o perfil que valia só
no Elden Ring passava a valer para tudo, sem aviso, e sem caminho de volta pela
tela (a regra antiga não fica em lugar nenhum que o editor mostre).

A GUARDA É A DA JANELA ESTÁVEL, condição por condição
(``profiles_actions.py:3400``): a regra NOVA é ``MatchAny`` e a ANTIGA não é. O
``MatchManual`` e o ``criteria`` vazio entram junto — virar "vale para TUDO" é,
nesses dois, a mudança mais violenta que a aba sabe fazer, e era a única que
passava calada.

A PERGUNTA MORA NO GESTO, e não num diálogo, pela razão já escrita em
``_rotulo_do_remover``: os gestos rodam em thread e o GTK só aceita diálogo no
laço principal. O primeiro clique RECUSA dizendo — a frase vira tarja de 30 s —
e o segundo, dentro de oito segundos, grava.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import loader

#: A MESA — endereço MASCARADO (octetos 4 e 5 zerados).
MESA = [
    {"pref": "p1", "uniq": "aabbcc000001", "jogador": 1, "cor": "cosmic-red",
     "nome": "Cosmic Red", "via": "USB", "transporte": "usb", "alvo": True,
     "mascara": "DualSense"},
]


class PonteDeMentira:
    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...]]] = []

    def profile_switch(self, nome: str) -> bool:
        self.chamadas.append(("profile_switch", (nome,)))
        return True

    def chamar(self, metodo: str, *a: Any, **kw: Any) -> Any:
        self.chamadas.append((metodo, a))
        return True

    def resultado(self, metodo: str, *a: Any, **kw: Any) -> Any:
        self.chamadas.append((metodo, tuple(kw.values())))
        return {}


@pytest.fixture(autouse=True)
def _memoria_limpa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ARMADO", None, raising=False)
    monkeypatch.setattr(a10_perfis, "_ARMADO_REBAIXAR", None, raising=False)
    monkeypatch.setattr(a10_perfis, "_DESFECHO", None, raising=False)


@pytest.fixture
def gravados(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    fora: list[Any] = []
    monkeypatch.setattr(loader, "save_profile",
                        lambda prof, **kw: fora.append(prof))
    return fora


def _de_jogo(nome: str) -> Any:
    """Um perfil que vale SÓ num programa — o caso que o rebaixamento apaga."""
    from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile

    return Profile(name=nome, priority=80,
                   match=MatchCriteria(process_name=["eldenring.exe"]))


def _catch_all(nome: str) -> Any:
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    return Profile(name=nome, match=MatchAny(), priority=1)


def _o_disco_tem(monkeypatch: pytest.MonkeyPatch, *perfis: Any) -> list[Any]:
    todos = list(perfis)
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: todos)
    monkeypatch.setattr(
        loader, "load_profile",
        lambda nome, *a, **k: next(p for p in todos if p.name == nome))
    return todos


def _ctx() -> Contexto:
    """Daemon calado: nada é reaplicado, e as chamadas ficam legíveis."""
    return Contexto(state={"active_profile": None}, mesa=list(MESA),
                    conectados=list(MESA), estados={})


def _escolher(rotulo: str) -> dict[str, Any]:
    """O clique que o piloto manda: o `value` do `<select>` e o evento."""
    return {"valor": rotulo, "rotulo": rotulo, "evento": "change",
            "tipo": "select"}


# --------------------------------------------------------------------------
def test_o_primeiro_clique_recusa_dizendo_o_que_se_perde(
    monkeypatch: pytest.MonkeyPatch, gravados: list[Any],
) -> None:
    """A frase nomeia o perfil, o que ele É HOJE, e o que "Todos" apaga.

    MORDIDA: tire a chamada a ``_pergunta_antes_de_rebaixar`` do
    ``editor_ambiente`` (que é como o gesto era até 03/09) e este teste reprova
    — o catch-all é gravado no primeiro clique, calado.
    """
    from hefesto_dualsense4unix.app.actions.profiles_actions import _match_label

    todos = _o_disco_tem(monkeypatch, _de_jogo("Elden Ring"))
    a10_perfis._ESCOLHIDO = "Elden Ring"

    with pytest.raises(RuntimeError) as erro:
        a10_perfis.editor_ambiente(_ctx(), _escolher("Todos"), PonteDeMentira())

    frase = str(erro.value)
    assert "Elden Ring" in frase, f"a recusa não nomeia o perfil: {frase!r}"
    assert _match_label(todos[0].match) in frase, (
        f"a recusa não diz o que o perfil É HOJE — a janela estável usa o "
        f"rótulo da coluna 'Quando usar' para não chamar de 'programas "
        f"específicos' um perfil que a lista chama de outra coisa: {frase!r}")
    assert "apaga os programas em que ele valia" in frase, (
        f"a recusa não diz o que se PERDE: {frase!r}")
    assert gravados == [], (
        f"o gesto recusou e gravou assim mesmo: {gravados}")


def test_o_segundo_clique_grava(
    monkeypatch: pytest.MonkeyPatch, gravados: list[Any],
) -> None:
    """A vontade dela prevalece — a guarda pergunta, nunca decide por ela.

    É a mesma escolha da janela estável, escrita lá com todas as letras:
    *"PERGUNTA, nunca recusa: a vontade dela na GUI prevalece sempre."*
    """
    from hefesto_dualsense4unix.profiles.schema import MatchAny

    _o_disco_tem(monkeypatch, _de_jogo("Elden Ring"))
    a10_perfis._ESCOLHIDO = "Elden Ring"
    ponte = PonteDeMentira()

    with pytest.raises(RuntimeError):
        a10_perfis.editor_ambiente(_ctx(), _escolher("Todos"), ponte)
    a10_perfis.editor_ambiente(_ctx(), _escolher("Todos"), ponte)

    assert len(gravados) == 1, "o segundo clique não gravou"
    assert isinstance(gravados[0].match, MatchAny), (
        f"a regra gravada foi {gravados[0].match!r} e ela escolheu 'Todos'")


def test_o_armamento_vence_com_o_prazo(
    monkeypatch: pytest.MonkeyPatch, gravados: list[Any],
) -> None:
    """Oito segundos, o mesmo prazo do Remover — armamento sem prazo é armadilha.

    Ela clica, se distrai, volta meia hora depois e escolhe "Todos" de novo: sem
    o prazo, a regra do jogo dela sumiria sem que nada tivesse perguntado
    naquele minuto.
    """
    _o_disco_tem(monkeypatch, _de_jogo("Elden Ring"))
    a10_perfis._ESCOLHIDO = "Elden Ring"
    ponte = PonteDeMentira()

    with pytest.raises(RuntimeError):
        a10_perfis.editor_ambiente(_ctx(), _escolher("Todos"), ponte)

    agora = a10_perfis.time.monotonic()
    monkeypatch.setattr(a10_perfis.time, "monotonic",
                        lambda: agora + a10_perfis.SEGUNDOS_PARA_CONFIRMAR + 0.1)
    with pytest.raises(RuntimeError):
        a10_perfis.editor_ambiente(_ctx(), _escolher("Todos"), ponte)
    assert gravados == [], "o armamento vencido ainda gravou"


def test_o_armamento_e_por_perfil(
    monkeypatch: pytest.MonkeyPatch, gravados: list[Any],
) -> None:
    """Armar num perfil não pode liberar o rebaixamento de OUTRO.

    É a mesma disciplina do Remover, e pela mesma razão: seria a pior forma de
    perder a regra do perfil errado.
    """
    _o_disco_tem(monkeypatch, _de_jogo("Elden Ring"), _de_jogo("Pragmata"))
    ponte = PonteDeMentira()

    a10_perfis._ESCOLHIDO = "Elden Ring"
    with pytest.raises(RuntimeError):
        a10_perfis.editor_ambiente(_ctx(), _escolher("Todos"), ponte)

    a10_perfis._ESCOLHIDO = "Pragmata"
    with pytest.raises(RuntimeError) as erro:
        a10_perfis.editor_ambiente(_ctx(), _escolher("Todos"), ponte)
    assert "Pragmata" in str(erro.value)
    assert gravados == [], "o armamento de um perfil liberou o outro"


def test_quem_ja_e_catch_all_nao_e_perguntado(
    monkeypatch: pytest.MonkeyPatch, gravados: list[Any],
) -> None:
    """A guarda protege o que se PERDE — e um catch-all não perde nada.

    Perguntar aqui seria ruído, e ruído treina a pessoa a confirmar sem ler.
    """
    _o_disco_tem(monkeypatch, _catch_all("meu_perfil"))
    a10_perfis._ESCOLHIDO = "meu_perfil"

    a10_perfis.editor_ambiente(_ctx(), _escolher("Todos"), PonteDeMentira())
    assert len(gravados) == 1, "o gesto perguntou sobre um perfil que já vale sempre"


def test_as_outras_escolhas_nao_perguntam(
    monkeypatch: pytest.MonkeyPatch, gravados: list[Any],
) -> None:
    """"Steam", "Jogo" e "Jogo da Steam" continuam gravando no primeiro clique.

    A guarda é sobre PERDER o alvo, não sobre trocá-lo. Uma guarda que pegasse
    toda troca de regra viraria dois cliques para tudo — e a decisão dela de
    01/09 é ação imediata.
    """
    _o_disco_tem(monkeypatch, _de_jogo("Elden Ring"))
    a10_perfis._ESCOLHIDO = "Elden Ring"

    a10_perfis.editor_ambiente(_ctx(), _escolher("Steam"), PonteDeMentira())
    assert len(gravados) == 1, "trocar para 'Steam' passou a exigir confirmação"


def test_a_guarda_desarma_quando_ela_escolhe_outra_coisa(
    monkeypatch: pytest.MonkeyPatch, gravados: list[Any],
) -> None:
    """Armar "Todos", desistir e escolher "Steam" não deixa o armamento de pé.

    Sem isto, a próxima escolha de "Todos" — em qualquer momento dos oito
    segundos, e sobre o mesmo perfil — gravaria sem perguntar, e a pergunta que
    a autorizou falava de outro gesto.
    """
    _o_disco_tem(monkeypatch, _de_jogo("Elden Ring"))
    a10_perfis._ESCOLHIDO = "Elden Ring"
    ponte = PonteDeMentira()

    with pytest.raises(RuntimeError):
        a10_perfis.editor_ambiente(_ctx(), _escolher("Todos"), ponte)
    a10_perfis.editor_ambiente(_ctx(), _escolher("Steam"), ponte)

    with pytest.raises(RuntimeError):
        a10_perfis.editor_ambiente(_ctx(), _escolher("Todos"), ponte)
