"""O "Ativar" da aba Perfis estava na lista dos DEZESSEIS — e a causa era outra.

O MAPA DE 02/09/2026 o acusa em
``docs/process/2026-09-02-O-MAPA-DA-INTERFACE-medido-clicando-e-as-ondas.md:120``:
*"clicou, respondeu `aplicado`, o estado do daemon não mudou, e ele NÃO está
declarado como gesto sem eco"*. O FATO está certo. **A causa, não**: o gesto não
falhava — ele trocava para o perfil que **já estava valendo**.

A CADEIA, e ela é toda de código que já existia:

1. ``pacote()`` roda a cada 500 ms e chama ``_escolhido()``, que grava
   ``_ESCOLHIDO = ativo`` quando ninguém clicou numa linha ainda. É a
   sincronização inicial, escrita lá de propósito;
2. a régua de cliques aciona os gestos **sem ``selecionar`` antes** — e
   ``ativar`` é o primeiro em ordem alfabética;
3. então ele sai com o nome do perfil ATIVO. O daemon reaplica o mesmo arquivo,
   ``active_profile`` continua o mesmo, e a régua lê "nada mudou".

Nada mudou porque **não havia nada a mudar** — e dizer "aplicado" sobre isso é
a forma exata do "responde calado" que esta casa persegue. A cura é a terceira
guarda do gesto: recusa DIZENDO, antes de falar com o daemon.

**E A RECUSA NÃO CHEGAVA A ELA — corrigido em 03/09/2026.** A guarda de 02/09
levantava ``ValueError``, e ``hefesto_vivo._recusou_dizendo`` pinta tarja **só
para ``RuntimeError``**: a frase saía no ``stderr`` do processo que lançou a
janela e mais nada. Medido no produto instalado, clicando "Ativar" com o perfil
ativo já escolhido — ``[gesto falhou] … já é o perfil que está valendo`` no
terminal, e ``document.querySelectorAll('.hef-recado')`` com **zero** elementos.
Ela clicava, o produto recusava com a frase certa, e a tela ficava igual.
Ou seja: *alguém curou o caminho e provou a cura num caminho que ela não usa* —
que é o defeito que o próprio ``_recusou_dizendo`` nomeia no docstring.

AS DUAS MORDIDAS:

1. apague o bloco ``if ativo and mesmo_slug(ativo, nome)`` de
   ``a10_perfis.ativar`` e ``test_reativar_o_mesmo_perfil_e_recusado`` reprova —
   a ponte registra a chamada e o gesto volta a responder "aplicado" sobre um
   não-evento;
2. troque o ``RuntimeError`` daquele bloco de volta por ``ValueError`` e o mesmo
   teste reprova no ``isinstance`` — a recusa volta a existir só no terminal.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis


class PonteDeMentira:
    """Uma ponte que anota o que foi pedido e nunca fala com o daemon vivo.

    ``profile_switch`` devolve ``True`` de propósito: se o gesto chegar até
    aqui, ele responderá "aplicado" — que é exatamente o defeito medido.
    """

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...]]] = []

    def profile_switch(self, nome: str) -> bool:
        self.chamadas.append(("profile_switch", (nome,)))
        return True

    def chamar(self, metodo: str, *args: Any, **kw: Any) -> Any:
        self.chamadas.append((metodo, args))
        return True

    # `resultado` ENTROU EM 03/09/2026 com o ELO-MUDO-01: o `ativar` passou a
    # ler o CORPO da resposta do daemon (`secoes`) em vez do booleano, que é a
    # diferença entre "ativado" e "ativado, menos o que o lock manual
    # descartou". O dublê devolve `{}` — corpo sem relatório, que é o caso do
    # daemon antigo e faz `mensagem_de_ativacao` cair na frase de sempre.
    def resultado(self, metodo: str, *args: Any, **kw: Any) -> Any:
        self.chamadas.append((metodo, tuple(kw.values())))
        return {}


@pytest.fixture(autouse=True)
def _sem_escolha_herdada(monkeypatch: pytest.MonkeyPatch) -> None:
    """`_ESCOLHIDO` é estado de MÓDULO — um teste não pode herdar o do outro."""
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)


def _clicar(ativo: str, escolhido: str) -> tuple[PonteDeMentira, Exception | None]:
    a10_perfis._ESCOLHIDO = escolhido
    ponte = PonteDeMentira()
    ctx = Contexto(state={"active_profile": ativo})
    try:
        a10_perfis.ativar(ctx, {"texto": "Ativar"}, ponte)
    except Exception as erro:  # é a recusa que a régua quer ver
        return ponte, erro
    return ponte, None


def test_reativar_o_mesmo_perfil_e_recusado() -> None:
    """O caso que a régua de cliques produziu, e que virou um dos dezesseis."""
    ponte, erro = _clicar(ativo="meu_perfil", escolhido="meu_perfil")
    assert isinstance(erro, RuntimeError), (
        "reativar o perfil que já vale passou pela guarda e foi ao daemon — ou a\n"
        "        recusa voltou a ser `ValueError`, que `_recusou_dizendo` descarta"
    )
    assert "já é o perfil que está valendo" in str(erro)
    assert ponte.chamadas == [], (
        f"o gesto falou com a ponte sobre um não-evento: {ponte.chamadas}"
    )


def test_a_recusa_compara_por_slug_e_nao_por_string() -> None:
    """R-10: "Navegação" no disco e "Navegacao" no daemon são O MESMO perfil.

    Com um ``==`` cru a guarda nunca pegaria este caso — e é o caso que
    acontece de verdade, porque o nome de arquivo é o slug
    (``profiles/loader.save_profile``).
    """
    ponte, erro = _clicar(ativo="Navegacao", escolhido="Navegação")
    assert isinstance(erro, RuntimeError), (
        "a guarda comparou texto cru: o mesmo perfil passou como se fosse outro"
    )
    assert ponte.chamadas == []


def test_ativar_outro_perfil_continua_passando() -> None:
    """A guarda não pode fechar o gesto: trocar de perfil é o trabalho dele."""
    ponte, erro = _clicar(ativo="meu_perfil", escolhido="Ação")
    assert erro is None, f"ativar outro perfil foi recusado: {erro}"
    assert ponte.chamadas == [("profile.switch", ("Ação",))]


def test_sem_perfil_ativo_o_gesto_nao_e_travado() -> None:
    """Daemon sem perfil ativo (`active_profile` vazio) é estado legítimo, e a
    guarda não pode confundir "nenhum" com "este mesmo"."""
    ponte, erro = _clicar(ativo="", escolhido="Ação")
    assert erro is None, f"a guarda travou com o daemon sem perfil ativo: {erro}"
    assert ponte.chamadas == [("profile.switch", ("Ação",))]
