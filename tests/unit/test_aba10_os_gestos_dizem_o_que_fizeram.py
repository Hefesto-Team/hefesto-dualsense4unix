"""A aba Perfis parou de responder calada — e o "Recarregar" deixou de ser morto.

DOIS DEFEITOS, medidos em 03/09/2026 contra a interface nova. Os dois são de
PARIDADE: a janela estável faz as duas coisas há meses.

1. **O SUCESSO ERA SILÊNCIO.** Lá, todo gesto desta aba termina num
   ``_toast_profile`` no rodapé (``profiles_actions.py:4579``) — "Perfil
   removido: X", "Lista recarregada", ``mensagem_de_ativacao``. Aqui só a
   RECUSA falava: ``RuntimeError`` vira tarja (``hefesto_vivo._recusou_dizendo``)
   e o sucesso não escrevia uma letra — o piloto anota ``("aplicou", "")``.
   Para os NOVE gestos desta aba que ESCREVEM NO DISCO DELA, silêncio no
   sucesso é a mesma classe de defeito que o toast existe para curar.

2. **O "Recarregar" ERA UM BOTÃO MORTO COM APARÊNCIA DE VIVO.** O
   ``data-hef-gesto="recarregar"`` está na página desde 31/08 e não havia
   ``@gesto``: o piloto caía no ramo do gesto SEM DONO e imprimia
   ``[gesto sem dono]`` **no stdout de quem lançou a janela**. Ela clicava,
   nada acontecia, e nada dizia por quê — nem a tarja, porque
   ``_recusou_dizendo`` só pinta para exceção de HANDLER.

E O TERCEIRO, que é o mais fácil de escrever errado: **o embrulho da carga**.
O ``_deu_certo`` entrega o que o gesto devolveu CRU ao ``window.__hef.pintar``,
que lê ``p.blocos``, ``p.mesa``, ``p.colunas`` e ``p.vazios`` — e mais nada. Um
dicionário achatado passa por todos os laços sem casar com nenhum: zero escrito,
zero erro. É a forma exata do defeito que já custou dois dias ao ``blocos`` do
``normalizar``, e um gesto que a repetisse ficaria verde em toda régua de
registro enquanto a tela dela continuava muda.
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

#: O endereço da tira, e ele é UM só nos dois lados: o pacote emite este nome e
#: o gerador o escreve na tira (`aba10.py`). Digitá-lo aqui e mudá-lo lá é a
#: divergência que a régua de endereços cobra.
DESFECHO = "perfis.desfecho"


class PonteDeMentira:
    """Anota o que foi pedido e nunca fala com o daemon vivo.

    O ``resultado`` devolve o CORPO que o daemon manda no ``profile.switch`` —
    é o que separa "ativado" de "ativado, menos o que o lock manual descartou".
    """

    def __init__(self, corpo: Any = None) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.corpo = corpo if corpo is not None else {}

    def profile_switch(self, nome: str) -> bool:
        self.chamadas.append(("profile_switch", (nome,), {}))
        return True

    def chamar(self, metodo: str, *a: Any, **kw: Any) -> Any:
        self.chamadas.append(("chamar", (metodo, *a), kw))
        return True

    def resultado(self, metodo: str, *a: Any, **kw: Any) -> Any:
        self.chamadas.append(("resultado", (metodo, *a), kw))
        return self.corpo


@pytest.fixture(autouse=True)
def _memoria_limpa(monkeypatch: pytest.MonkeyPatch) -> None:
    """Estado de MÓDULO herdado de outro teste não é prova de nada."""
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ARMADO", None, raising=False)
    monkeypatch.setattr(a10_perfis, "_ARMADO_REBAIXAR", None, raising=False)
    monkeypatch.setattr(a10_perfis, "_DESFECHO", None, raising=False)
    monkeypatch.setattr(a10_perfis, "_PINTADO_PARA", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ULTIMO_TIQUE", 0.0, raising=False)


def _perfis(*nomes: str) -> list[Any]:
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    return [Profile(name=n, match=MatchAny(), priority=100 - i)
            for i, n in enumerate(nomes)]


def _o_disco_tem(monkeypatch: pytest.MonkeyPatch, *nomes: str) -> list[Any]:
    """A pasta de perfis, sem escrever no disco.

    SEM ISTO A PASTA É VAZIA: a ``conftest.py`` põe
    ``HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1`` em TODO teste.
    """
    todos = _perfis(*nomes)
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: todos)
    monkeypatch.setattr(
        loader, "load_profile",
        lambda nome, *a, **k: next(p for p in todos if p.name == nome))
    return todos


def _ctx(ativo: str | None = None) -> Contexto:
    return Contexto(state={"active_profile": ativo}, mesa=list(MESA),
                    conectados=list(MESA), estados={})


def _o_marcador_diz(monkeypatch: pytest.MonkeyPatch, nome: str | None) -> None:
    from hefesto_dualsense4unix.app.actions import profiles_actions

    monkeypatch.setattr(profiles_actions, "perfil_que_ela_ativou", lambda: nome)


# --------------------------------------------------------------------------
# 1. O EMBRULHO — sem ele nada disto chega à tela
# --------------------------------------------------------------------------
def test_o_desfecho_vai_no_embrulho_que_a_pintura_le() -> None:
    """``{"mesa": {…}}``, e não o dicionário achatado.

    O ``pintar`` do piloto lê ``p.blocos``, ``p.mesa``, ``p.colunas`` e
    ``p.vazios``. Uma chave na RAIZ não casa com nenhum laço: **zero escrito,
    zero erro**.

    MORDIDA: devolva ``{"perfis.desfecho": frase}`` em ``_dizer`` (que é a forma
    que parece certa e não pinta nada) e este teste reprova.
    """
    carga = a10_perfis._dizer("Perfil ativado: Pragmata")
    assert set(carga) == {"mesa"}, (
        f"a carga do desfecho saiu como {sorted(carga)}. O `pintar` só lê "
        f"`blocos`, `mesa`, `colunas` e `vazios` — o resto cai no vazio.")
    assert carga["mesa"][DESFECHO] == "Perfil ativado: Pragmata"


def test_o_desfecho_tambem_fica_guardado_para_o_tique_seguinte() -> None:
    """A pintura imediata é o "agora"; o tique é o que o mantém trinta segundos.

    Sem o guardado, a frase apareceria e o PRÓXIMO tique — 500 ms depois — a
    apagaria com o valor vazio do pacote. Ela leria um lampejo.
    """
    a10_perfis._dizer("Perfil removido: Sackboy")
    assert a10_perfis._desfecho_para_a_tela() == "Perfil removido: Sackboy"


def test_o_desfecho_vence_e_a_tira_apaga(monkeypatch: pytest.MonkeyPatch) -> None:
    """Trinta segundos, e o relógio é MONOTÔNICO — o mesmo prazo da tarja.

    Um desfecho que ficasse para sempre viraria a tela afirmando um ato velho: o
    "Perfil removido" de meia hora atrás ao lado de uma lista já mudada.
    """
    a10_perfis._dizer("Lista recarregada · 33 perfis")
    agora = a10_perfis.time.monotonic()
    monkeypatch.setattr(a10_perfis.time, "monotonic",
                        lambda: agora + a10_perfis.SEGUNDOS_DO_DESFECHO + 0.1)
    assert a10_perfis._desfecho_para_a_tela() == "", (
        "o desfecho não venceu — a tira ficaria acesa com uma notícia velha")


def test_o_pacote_emite_o_desfecho_no_endereco_da_tira(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tira é pintada pelo tique, como o rótulo do Remover — não pelo JS."""
    _o_disco_tem(monkeypatch, "Pragmata", "Sackboy")
    _o_marcador_diz(monkeypatch, None)
    a10_perfis._dizer("Perfil removido: Sackboy")

    fora = a10_perfis.pacote(_ctx())
    assert fora[DESFECHO] == "Perfil removido: Sackboy"


# --------------------------------------------------------------------------
# 2. O "ATIVAR" LÊ O CORPO — e diz o que NÃO entrou
# --------------------------------------------------------------------------
def test_o_ativar_diz_o_que_o_lock_manual_comeu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ELO-MUDO-01: o booleano jogava fora o relatório de seções do daemon.

    A frase é a do produto — ``mensagem_de_ativacao`` reusa
    ``footer_actions._mensagem_de_aplicacao`` para a metade que nomeia o que
    ficou de fora. Esta régua não digita a frase: ela pergunta à função.

    MORDIDA: troque a chamada por ``p.profile_switch(nome)`` (que é como o gesto
    era até 03/09) e este teste reprova — a frase volta a ser só
    "Perfil ativado: X", com o daemon tendo dito que os gatilhos não entraram.
    """
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        mensagem_de_ativacao,
    )

    _o_disco_tem(monkeypatch, "Pragmata", "Sackboy")
    _o_marcador_diz(monkeypatch, None)
    a10_perfis._ESCOLHIDO = "Pragmata"
    corpo = {"secoes": {"leds": "aplicado", "triggers": "adiado_lock_manual"}}
    ponte = PonteDeMentira(corpo=corpo)

    carga = a10_perfis.ativar(_ctx(ativo="Sackboy"), {"texto": "Ativar"}, ponte)

    esperado = mensagem_de_ativacao("Pragmata", corpo)
    assert carga["mesa"][DESFECHO] == esperado, (
        f"o desfecho saiu {carga['mesa'][DESFECHO]!r} e o produto diz "
        f"{esperado!r}")
    assert "menos" in esperado, (
        "a frase do produto deixou de nomear o que ficou de fora — a régua "
        "está medindo contra um alvo que mudou")


def test_o_ativar_pede_o_corpo_e_nao_o_booleano(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A chamada é ``resultado("profile.switch", name=…)``, com o teto de 3 s.

    O invólucro ``profile_switch`` do ``ipc_bridge`` devolve ``bool`` e descarta
    o ``secoes``. Enquanto o gesto o usasse, não havia relatório a mostrar,
    dissesse o daemon o que dissesse.
    """
    _o_disco_tem(monkeypatch, "Pragmata", "Sackboy")
    _o_marcador_diz(monkeypatch, None)
    a10_perfis._ESCOLHIDO = "Pragmata"
    ponte = PonteDeMentira()

    a10_perfis.ativar(_ctx(ativo="Sackboy"), {"texto": "Ativar"}, ponte)

    pedidos = [(c[1][0], c[2].get("name")) for c in ponte.chamadas
               if c[0] == "resultado"]
    assert pedidos == [("profile.switch", "Pragmata")], (
        f"o `ativar` chamou {ponte.chamadas} — o corpo do daemon é o que "
        f"carrega o relatório de seções.")


def test_o_ativar_ainda_recusa_dizendo_quando_o_daemon_nao_atende(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A frase da recusa continua NOMEANDO o perfil, e não o método.

    ``ponte.resultado`` levanta ``RuntimeError("o daemon não respondeu a
    profile.switch")``, que é linguagem de quem programa. A tarja é lida por
    quem está com o controle na mão.
    """
    class PonteMuda(PonteDeMentira):
        def resultado(self, metodo: str, *a: Any, **kw: Any) -> Any:
            raise RuntimeError(f"o daemon não respondeu a {metodo}")

    _o_disco_tem(monkeypatch, "Pragmata", "Sackboy")
    _o_marcador_diz(monkeypatch, None)
    a10_perfis._ESCOLHIDO = "Pragmata"

    with pytest.raises(RuntimeError) as erro:
        a10_perfis.ativar(_ctx(ativo="Sackboy"), {"texto": "Ativar"}, PonteMuda())
    assert "Pragmata" in str(erro.value), (
        f"a recusa saiu {str(erro.value)!r} e não nomeia o perfil")


# --------------------------------------------------------------------------
# 3. O "RECARREGAR" TEM DONO
# --------------------------------------------------------------------------
def test_o_recarregar_tem_dono() -> None:
    """Um clique sem dono não chega nem à tarja: vai para o stdout.

    MORDIDA: tire o ``@gesto("10-perfis.html", "recarregar")`` e este teste
    reprova — é exatamente o estado em que o botão ficou de 31/08 a 03/09.
    """
    from hefesto_dualsense4unix.interface import pacotes

    assert pacotes.gesto_da_pagina("10-perfis.html", "recarregar") is not None, (
        "o `recarregar` voltou a ser botão morto: o piloto imprime `[gesto sem "
        "dono]` no terminal de quem lançou a janela, e a tela não diz nada.")


def test_o_recarregar_devolve_a_lista_relida(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ele é o ``_reload_profiles_store`` desta tela: relê e REPINTA na hora.

    A carga tem de trazer o ``blocos`` da lista — é ele que troca o ``<tbody>``
    inteiro. Sem ele o clique não mudaria um pixel até o tique seguinte, e um
    botão que parece não ter pego é o defeito que ele existe para curar.
    """
    _o_disco_tem(monkeypatch, "Pragmata", "Sackboy", "Elden Ring")
    _o_marcador_diz(monkeypatch, None)

    carga = a10_perfis.recarregar(_ctx(), {}, PonteDeMentira())

    assert a10_perfis.SELETOR_DA_LISTA in carga["blocos"], (
        f"o `recarregar` não devolveu o bloco da lista: {sorted(carga)}")
    assert "Elden Ring" in carga["blocos"][a10_perfis.SELETOR_DA_LISTA]
    assert carga["mesa"][DESFECHO] == "Lista recarregada · 3 perfis", (
        f"o desfecho saiu {carga['mesa'][DESFECHO]!r}")


def test_o_recarregar_nao_fala_com_o_daemon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fonte da lista é o DISCO — o daemon só sabe qual está ativo.

    Um ``load_all`` extra pelo IPC seria o botão fingindo trabalho que já está
    feito, que é a metade CERTA do motivo antigo de ele não ter dono.
    """
    _o_disco_tem(monkeypatch, "Pragmata")
    _o_marcador_diz(monkeypatch, None)
    ponte = PonteDeMentira()

    a10_perfis.recarregar(_ctx(), {}, ponte)

    assert ponte.chamadas == [], (
        f"o `recarregar` foi ao daemon: {ponte.chamadas}")


def test_o_recarregar_traz_o_desfecho_novo_e_nao_o_do_gesto_anterior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ordem dentro do gesto importa, e é fácil de errar.

    ``pacote()`` LÊ o desfecho para pintá-lo, então a carga que ele acabou de
    montar carrega o desfecho ANTERIOR. Sem sobrescrever a chave depois, o
    clique em "Recarregar" mostraria "Perfil removido: X" — o desfecho de outro
    gesto, ao lado de uma lista que acabou de ser relida.
    """
    _o_disco_tem(monkeypatch, "Pragmata")
    _o_marcador_diz(monkeypatch, None)
    a10_perfis._dizer("Perfil removido: Sackboy")

    carga = a10_perfis.recarregar(_ctx(), {}, PonteDeMentira())

    assert carga["mesa"][DESFECHO] == "Lista recarregada · 1 perfis", (
        f"o `recarregar` pintou {carga['mesa'][DESFECHO]!r} — o desfecho do "
        f"gesto anterior.")


# --------------------------------------------------------------------------
# 4. O "REMOVER" DIZ QUE REMOVEU
# --------------------------------------------------------------------------
def test_o_remover_anota_a_frase_da_janela_estavel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """"Perfil removido: X" — a MESMA frase, não uma parecida.

    ``profiles_actions.py:3197`` é o dono. Escrever outra aqui seria a segunda
    verdade sobre o mesmo ato.
    """
    _o_disco_tem(monkeypatch, "Pragmata", "Sackboy")
    _o_marcador_diz(monkeypatch, None)
    apagados: list[str] = []
    monkeypatch.setattr(loader, "delete_profile",
                        lambda nome, *a, **k: apagados.append(nome))
    a10_perfis._ESCOLHIDO = "Sackboy"
    ponte = PonteDeMentira()

    # O primeiro clique ARMA e levanta — a pergunta mora no rótulo do botão.
    with pytest.raises(RuntimeError):
        a10_perfis.remover(_ctx(), {}, ponte)
    a10_perfis.remover(_ctx(), {}, ponte)

    assert apagados == ["Sackboy"]
    assert a10_perfis._desfecho_para_a_tela() == "Perfil removido: Sackboy"
