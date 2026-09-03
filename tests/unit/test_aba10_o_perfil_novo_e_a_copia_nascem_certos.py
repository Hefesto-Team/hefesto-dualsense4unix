"""O "Novo" e o "Duplicar" da aba Perfis nascem como a janela estável os faz.

DOIS DEFEITOS DE COMPORTAMENTO, medidos em 03/09/2026 contra a interface nova.
Nenhum é de desenho, e nenhum aparece na tela: os dois só se veem no `.json`
que ficou no disco dela.

1. **O perfil novo nascia em prioridade ZERO** — PERFIL-NASCE-CERTO-01. A
   janela estável calcula ``max(prioridade dos catch-all) + 10``
   (``_prioridade_acima_dos_catch_all``, ``profiles_actions.py:4172``); esta aba
   não calculava nada. O defeito tem caso medido, com ela jogando, em 26/07: o
   perfil que ela criou para o Pragmata nasceu em 0 e NUNCA valia no jogo,
   porque o catch-all dela (100) vencia em todo o resto. **Ela não errou a
   configuração — a janela não tinha saída.**

   O motivo que estava escrito no produto para não fazer a conta — *"essa conta
   mora num mixin GTK que depende de widget"* — **caiu na leitura**: o corpo do
   método lê UM atributo, ``self._profiles_cache``, e mais nada. Sem ``Gtk``,
   sem ``self._get``, sem widget. Faltava alguém lhe entregar a lista.

2. **A cópia herdava o CARIMBO DE PONTE** — PONTE-CONFIRMADA-01. O
   ``model_copy`` levava o campo ``ponte`` junto, e a janela estável o corta de
   propósito: o duplicar entra como estreia, o degrau 2 de
   ``carimbo_que_o_save_leva`` é cortado e o degrau 1 (o disco, pelo nome NOVO)
   devolve ``None``. O carimbo é REGISTRO de uma confirmação, não configuração
   que se copia — e o gesto seguinte ao duplicar é justamente repontar a cópia
   para outro jogo, onde ninguém provou ponte nenhuma.

O QUE ESTAS RÉGUAS NÃO FAZEM: escrever no disco. ``save_profile`` é substituído
por um coletor, e o que se mede é o ``Profile`` que ele receberia.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import loader

#: A MESA — endereço MASCARADO (octetos 4 e 5 zerados). Nenhum endereço real de
#: rádio entra em arquivo versionado.
MESA = [
    {"pref": "p1", "uniq": "aabbcc000001", "jogador": 1, "cor": "cosmic-red",
     "nome": "Cosmic Red", "via": "USB", "transporte": "usb", "alvo": True,
     "mascara": "DualSense"},
]


class PonteDeMentira:
    """Anota o que foi pedido e nunca fala com o daemon vivo."""

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
    """Estado de MÓDULO herdado de outro teste não é prova de nada."""
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ARMADO", None, raising=False)
    monkeypatch.setattr(a10_perfis, "_ARMADO_REBAIXAR", None, raising=False)
    monkeypatch.setattr(a10_perfis, "_DESFECHO", None, raising=False)


@pytest.fixture
def gravados(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """O que o ``save_profile`` receberia — sem tocar na pasta dela.

    O gesto grava por ``pacotes/perfil.gravar_e_reaplicar``, que resolve o
    ``loader`` no momento da chamada: substituir o atributo do MÓDULO alcança os
    dois caminhos.
    """
    fora: list[Any] = []
    monkeypatch.setattr(loader, "save_profile",
                        lambda prof, **kw: fora.append(prof))
    return fora


def _catch_all(nome: str, prioridade: int) -> Any:
    """Um perfil "vale sempre" — ``MatchAny`` é o que ``e_catch_all`` reconhece."""
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    return Profile(name=nome, match=MatchAny(), priority=prioridade)


def _de_jogo(nome: str, prioridade: int, **extra: Any) -> Any:
    from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile

    return Profile(name=nome, match=MatchCriteria(process_name=[f"{nome}.exe"]),
                   priority=prioridade, **extra)


def _o_disco_tem(monkeypatch: pytest.MonkeyPatch, *perfis: Any) -> list[Any]:
    todos = list(perfis)
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: todos)
    monkeypatch.setattr(
        loader, "load_profile",
        lambda nome, *a, **k: next(p for p in todos if p.name == nome))
    return todos


def _ctx() -> Contexto:
    """O daemon calado — ``active_profile: null`` é o estado da máquina dela.

    Calado importa aqui: com ele, ``gravar_e_reaplicar`` não manda
    ``profile.switch``, e o que sobra nas chamadas é só o ``launch_env.refresh``.
    """
    return Contexto(state={"active_profile": None}, mesa=list(MESA),
                    conectados=list(MESA), estados={})


# --------------------------------------------------------------------------
# 1. O PERFIL NOVO NASCE ACIMA DOS QUE VALEM SEMPRE
# --------------------------------------------------------------------------
def test_o_perfil_novo_nasce_acima_dos_catch_all(
    monkeypatch: pytest.MonkeyPatch, gravados: list[Any],
) -> None:
    """A conta é a da janela estável: maior catch-all + a folga de 10.

    Os números são os do disco DELA, medidos em 03/09: os catch-all são
    ``meu_perfil`` (1) e ``fallback`` (0), então o novo sai em **11**.

    MORDIDA: troque a chamada por ``Profile(name=nome, match=regra)`` (que é
    como o gesto era até 03/09) e este teste reprova dizendo "nasceu em 0".
    """
    _o_disco_tem(monkeypatch, _catch_all("meu_perfil", 1),
                 _catch_all("fallback", 0), _de_jogo("Pragmata", 80))
    a10_perfis.novo(_ctx(), {}, PonteDeMentira())

    assert len(gravados) == 1, "o Novo não gravou perfil nenhum"
    assert gravados[0].priority == 11, (
        f"o perfil novo nasceu em {gravados[0].priority} e os catch-all do "
        f"disco estão em 1 e 0 — a folga do produto é 10. Em prioridade 0 ele "
        f"perde para todo mundo e NUNCA vale, que é o defeito de 26/07.")


def test_a_conta_do_perfil_novo_respeita_o_teto_do_esquema(
    monkeypatch: pytest.MonkeyPatch, gravados: list[Any],
) -> None:
    """Com um catch-all no teto, somar 10 estouraria o esquema.

    Quem sabe disso é a função do produto (``min(PRIORIDADE_MAXIMA, …)``), e é
    por isso que ela é CHAMADA em vez de copiada: uma segunda conta aqui teria
    de lembrar do teto sozinha, e o ``Profile`` recusaria a gravação.
    """
    from hefesto_dualsense4unix.app.actions.profiles_actions import PRIORIDADE_MAXIMA

    _o_disco_tem(monkeypatch, _catch_all("teto", PRIORIDADE_MAXIMA))
    a10_perfis.novo(_ctx(), {}, PonteDeMentira())

    assert gravados[0].priority == PRIORIDADE_MAXIMA, (
        f"nasceu em {gravados[0].priority} com o teto em {PRIORIDADE_MAXIMA}")


def test_a_conta_e_a_do_produto_e_nao_uma_copia(
    monkeypatch: pytest.MonkeyPatch, gravados: list[Any],
) -> None:
    """O valor gravado é o que a função da janela estável devolve, sempre.

    É a régua contra a REESCRITA, não contra o número: ela compara o que o gesto
    gravou com o que ``_prioridade_acima_dos_catch_all`` responde para a MESMA
    lista. Uma segunda conta que hoje concorda e amanhã divirja reprova aqui.
    """
    from types import SimpleNamespace

    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        ProfilesActionsMixin,
    )

    todos = _o_disco_tem(monkeypatch, _catch_all("a", 37), _de_jogo("b", 90))
    a10_perfis.novo(_ctx(), {}, PonteDeMentira())

    esperado = ProfilesActionsMixin._prioridade_acima_dos_catch_all(
        SimpleNamespace(_profiles_cache=todos))
    assert gravados[0].priority == esperado, (
        f"o gesto gravou {gravados[0].priority} e a função do produto diz "
        f"{esperado}. A conta tem UM dono.")


def test_o_perfil_novo_nao_e_ativado(
    monkeypatch: pytest.MonkeyPatch, gravados: list[Any],
) -> None:
    """Nascer não é passar a valer — a coluna tem um "Ativar" para isso."""
    _o_disco_tem(monkeypatch, _catch_all("meu_perfil", 1))
    ponte = PonteDeMentira()
    a10_perfis.novo(_ctx(), {}, ponte)

    assert [c for c in ponte.chamadas if c[0] == "profile_switch"] == [], (
        f"o Novo trocou o perfil que está valendo: {ponte.chamadas}")


# --------------------------------------------------------------------------
# 2. A CÓPIA NÃO HERDA O CARIMBO DE PONTE
# --------------------------------------------------------------------------
def _com_carimbo(nome: str) -> Any:
    """Um perfil de jogo que JÁ TEM ponte confirmada — o caso do defeito."""
    from hefesto_dualsense4unix.profiles.schema import PonteConfirmada

    return _de_jogo(nome, 80, ponte=PonteConfirmada(
        kind="gamepad", gamepad_flavor="dualsense", steam_input=True))


def test_a_copia_nao_leva_o_carimbo_de_ponte(
    monkeypatch: pytest.MonkeyPatch, gravados: list[Any],
) -> None:
    """A cópia nasce SEM carimbo, como na janela estável.

    O cenário é o gesto seguinte ao duplicar: repontar a cópia para OUTRO jogo.
    Com o carimbo herdado, ``pontes_confirmadas()`` publica uma ponte que
    ninguém provou naquele appid, e a escada de ``ponte_escada.py`` para num
    jogo nunca testado — o produto jurando saber o que não sabe.

    MORDIDA: tire o ``"ponte": carimbo`` do ``model_copy`` (que é como o gesto
    era até 03/09) e este teste reprova nomeando o degrau herdado.
    """
    _o_disco_tem(monkeypatch, _com_carimbo("Pragmata"))
    a10_perfis._ESCOLHIDO = "Pragmata"
    a10_perfis.duplicar(_ctx(), {}, PonteDeMentira())

    assert len(gravados) == 1, "o Duplicar não gravou a cópia"
    assert gravados[0].ponte is None, (
        f"a cópia nasceu com o carimbo {gravados[0].ponte!r} do original. "
        f"Carimbo é REGISTRO de uma confirmação, não configuração que se copia.")


def test_a_copia_continua_levando_o_perfil_inteiro(
    monkeypatch: pytest.MonkeyPatch, gravados: list[Any],
) -> None:
    """A outra ponta, e ela é a cura que NÃO pode ser desfeita por esta.

    BUG-DUPLICATE-NO-CONFIG-COPY-01: a cópia já teve só o nome trocado e o resto
    virando default. Cortar o carimbo não pode virar cortar o resto — a dica
    dela promete *"Copia o perfil inteiro"*.
    """
    original = _com_carimbo("Pragmata")
    original.priority = 77
    _o_disco_tem(monkeypatch, original)
    a10_perfis._ESCOLHIDO = "Pragmata"
    a10_perfis.duplicar(_ctx(), {}, PonteDeMentira())

    copia = gravados[0]
    assert copia.name == "Pragmata (cópia)", f"o nome saiu {copia.name!r}"
    assert copia.priority == 77, "a cópia perdeu a prioridade do original"
    assert copia.match == original.match, "a cópia perdeu a regra do original"


def test_a_regra_do_carimbo_e_a_do_produto(
    monkeypatch: pytest.MonkeyPatch, gravados: list[Any],
) -> None:
    """Quem decide é ``carimbo_que_o_save_leva`` — não um ``None`` digitado.

    A diferença aparece se a escada mudar: um ``ponte=None`` cravado aqui
    continuaria dizendo ``None`` no dia em que o degrau 1 passasse a devolver
    outra coisa. Esta régua chama a função do produto com os MESMOS argumentos
    do gesto e compara.
    """
    from hefesto_dualsense4unix.app.actions.profile_writer import (
        carimbo_que_o_save_leva,
    )
    from hefesto_dualsense4unix.profiles.slug import find_by_slug

    todos = _o_disco_tem(monkeypatch, _com_carimbo("Pragmata"))
    a10_perfis._ESCOLHIDO = "Pragmata"
    a10_perfis.duplicar(_ctx(), {}, PonteDeMentira())

    esperado = carimbo_que_o_save_leva(
        find_by_slug("Pragmata (cópia)", todos), None)
    assert gravados[0].ponte == esperado
