"""A aba Gatilhos com a paridade que faltava — 03/09/2026.

DUAS DÍVIDAS MEDIDAS CONTRA A GTK, e as duas nesta régua:

1. **A escolha não ficava na tela.** Clicar `Rígido` aplicava no aparelho — ela
   sente na mão — e, em no máximo meio segundo, o tique repintava o campo com o
   modo do PERFIL NO DISCO. Aplicar não grava, e a pintura não conhecia o que
   foi aplicado. Isso não é tela vazia: é **tela que mente**.
   *Na GTK:* `_persist_params_to_draft` grava antes de todo envio e
   `_refresh_triggers_from_draft` repinta do RASCUNHO.

2. **A tela calava sobre o desfecho.** `_desfecho` jogava o corpo do daemon
   fora, e três coisas diferentes viravam o mesmo silêncio de sucesso: nada
   aconteceu, ficou guardado, e a recusa que vem DENTRO de uma resposta
   bem-sucedida.
   *Na GTK:* `_toast_trigger` → `frase_do_desfecho`, lendo o corpo (ELO-MUDO-01/T3).

As barras de ajuste e o «Efeito pronto» saíram da aba com o desenho do todo (15/10/2026), e
as réguas deles saíram junto.

A MORDIDA DE CADA UMA está no docstring do teste que a mede, e as duas foram
arrancadas de verdade antes deste arquivo entrar.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

PAGINA = "03-gatilhos.html"

UNIQ = "aa:bb:cc:00:00:01"
FALSO = {"uniq": UNIQ, "player": 1, "transport": "usb", "is_primary": True,
         "inputs": {"l2_raw": 0, "r2_raw": 0}}
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
         "via": "USB", "cor": "starlight-blue", "mascara": "DualSense"}]

#: contrato de `ipc_bridge.trigger_set_detalhado`.
APLICOU = {"status": "ok", "aplicado_em": [UNIQ], "guardado_em": []}


_PERFIL_DA_CENA: dict = {}


@pytest.fixture(autouse=True)
def _o_perfil_de_mentira_nao_vaza():
    """O dublê de `perfil.ativo` VOLTA — e sem isto ele envenenava a suíte."""
    from pacotes import perfil

    original = perfil.ativo
    perfil.ativo = lambda _nome: dict(_PERFIL_DA_CENA)  # type: ignore[assignment]
    yield
    perfil.ativo = original
    _PERFIL_DA_CENA.clear()


@pytest.fixture
def a03():
    """O pacote, com o rascunho LIMPO — ele é estado de módulo."""
    import pacotes  # noqa: F401  (registra os dez)
    from pacotes import a03_gatilhos

    a03_gatilhos.esquecer_o_rascunho()
    yield a03_gatilhos
    a03_gatilhos.esquecer_o_rascunho()


class _Ponte:
    """A ponte que ACEITA e diz onde aplicou. Guarda o que foi chamado."""

    def __init__(self, corpo: dict | None = None) -> None:
        self.chamadas: list[tuple[str, tuple, dict]] = []
        self.corpo = APLICOU if corpo is None else corpo

    def _responder(self, nome, *a, **k):
        self.chamadas.append((nome, a, k))
        return (True, str(self.corpo.get("motivo") or ""), self.corpo)

    def trigger_set_detalhado(self, *a, **k):
        return self._responder("trigger_set_detalhado", *a, **k)

    def trigger_reset_detalhado(self, *a, **k):
        return self._responder("trigger_reset_detalhado", *a, **k)


def _ctx(perfil_ativo: str = "régua", modo_no_disco: str = "Off"):
    """O contexto da mesa de um controle, com o perfil injetado pela porta de cima."""
    from pacotes import Contexto

    _PERFIL_DA_CENA.clear()
    _PERFIL_DA_CENA.update({
        "triggers": {"left": {"mode": modo_no_disco, "params": []},
                     "right": {"mode": modo_no_disco, "params": []}},
        "controllers": {},
    })
    return Contexto(state={"active_profile": perfil_ativo}, mesa=MESA,
                    conectados=[FALSO], estados={})


def _clicar(gesto_: str, o: dict, p) -> None:
    from pacotes import gesto_da_pagina

    acao = gesto_da_pagina(PAGINA, gesto_)
    assert acao is not None, f"o gesto {gesto_!r} não tem dono nesta página"
    acao(_clicar.ctx, {"uniq": UNIQ, **o}, p)  # type: ignore[attr-defined]


def _modo(a03, ctx) -> str:
    """O modo do L2 depois de um tique: o `pacote()` poda o rascunho, e `_modo_de_agora` o lê."""
    a03.pacote(ctx)
    return str(a03._modo_de_agora(ctx, UNIQ, "left"))


def test_o_modo_aplicado_continua_no_campo_no_tique_seguinte(a03):
    """Clicar `Rígido` e ver o campo voltar para o disco é a queixa de uso.

    A MORDIDA: apague a linha `_do_rascunho(uniq, disco) or` do `cfgs` em
    `pacote()` — ou chame `esquecer_o_rascunho()` entre o gesto e a leitura — e
    o campo volta a dizer `Off` sobre um gatilho que está em `Resistance`.
    """
    ctx = _ctx(modo_no_disco="Off")
    antes = _modo(a03, ctx)
    assert antes == "Off", "o cenário partiu do lugar errado"

    _clicar.ctx = ctx  # type: ignore[attr-defined]
    _clicar("modo", {"lado": "e", "valor": "Resistance"}, _Ponte())

    depois = _modo(a03, ctx)
    assert depois == "Resistance", (
        f"o campo voltou para {depois!r} meio segundo depois do clique. É a "
        f"queixa dela: a escolha não fica.")


def test_trocar_de_perfil_esquece_o_que_foi_aplicado(a03):
    """O daemon REAPLICA o perfil no `profile.switch` — o rascunho tem de morrer.

    Guardá-lo por perfil e ressuscitá-lo na volta faria a tela afirmar um efeito
    que o daemon já desfez. A GTK paga o mesmo preço: o draft é remontado.

    A MORDIDA: tire a poda `_o_rascunho_e_deste_perfil` do `pacote()` e o modo
    aplicado no perfil anterior reaparece no perfil novo.
    """
    ctx = _ctx(perfil_ativo="ação", modo_no_disco="Off")
    _clicar.ctx = ctx  # type: ignore[attr-defined]
    _clicar("modo", {"lado": "e", "valor": "Resistance"}, _Ponte())
    assert _modo(a03, ctx) == "Resistance"

    outro = _ctx(perfil_ativo="corrida", modo_no_disco="Off")
    assert _modo(a03, outro) == "Off", (
        "o rascunho do perfil anterior sobreviveu à troca — a tela afirmaria "
        "um efeito que o `profile.switch` já desfez")


def test_o_controle_que_sai_da_mesa_leva_o_rascunho(a03):
    """No replug o daemon aplica o perfil de novo. Ver a nota da seção do rascunho."""
    from pacotes import Contexto

    ctx = _ctx(modo_no_disco="Off")
    _clicar.ctx = ctx  # type: ignore[attr-defined]
    _clicar("modo", {"lado": "e", "valor": "Resistance"}, _Ponte())

    a03.pacote(Contexto(state={"active_profile": "régua"}, mesa=MESA,
                        conectados=[], estados={}))
    assert _modo(a03, ctx) == "Off", (
        "o rascunho de um controle que saiu da mesa sobreviveu — no replug o "
        "daemon reaplica o perfil, e a tela diria o efeito de antes de ele sair")


def test_o_rascunho_so_recebe_o_que_o_daemon_aceitou(a03):
    """Guardar antes da resposta trocaria uma mentira por outra, pior."""
    ctx = _ctx(modo_no_disco="Off")
    _clicar.ctx = ctx  # type: ignore[attr-defined]
    guardado = {"status": "ok", "aplicado_em": [], "guardado_em": [UNIQ]}
    with pytest.raises(RuntimeError):
        _clicar("modo", {"lado": "e", "valor": "Resistance"}, _Ponte(guardado))
    assert _modo(a03, ctx) == "Off", (
        "o rascunho ficou com um efeito que o daemon GUARDOU sem mandar ao fio")


@pytest.mark.parametrize(
    ("corpo", "pedaco"),
    [
        ({"status": "ok", "aplicado_em": [], "guardado_em": []},
         "nenhum controle recebeu"),
        ({"status": "ok", "aplicado_em": [], "guardado_em": [UNIQ]},
         "guardado"),
        ({"status": "ok", "motivo": "o jogo segura o hidraw",
          "aplicado_em": [UNIQ], "guardado_em": []},
         "o jogo segura o hidraw"),
    ],
    ids=["nada-aconteceu", "guardado", "recusa-dentro-do-sucesso"],
)
def test_o_que_nao_chegou_ao_gatilho_e_dito(a03, corpo, pedaco):
    """Os três desfechos que passavam por sucesso silencioso.

    O CANAL É O `RuntimeError`: é o único que o piloto leva ao cartão daquele
    controle (`hefesto_vivo._recusou_dizendo`). E a frase é do dono do assunto —
    `app/textos_de_aplicacao.frase_do_desfecho`, a mesma que a barra de status
    da GTK usa —, nunca uma escrita aqui.

    A MORDIDA: faça `_desfecho` devolver `(ok, motivo)` de novo, jogando o corpo
    fora, e os três voltam a ser silêncio.
    """
    ctx = _ctx(modo_no_disco="Off")
    _clicar.ctx = ctx  # type: ignore[attr-defined]
    with pytest.raises(RuntimeError) as erro:
        _clicar("modo", {"lado": "e", "valor": "Resistance"}, _Ponte(corpo))
    assert pedaco in str(erro.value), (
        f"a frase não diz o que aconteceu: {erro.value!r}")
    assert a03.NOME_DO_LADO["left"] in str(erro.value), (
        f"a frase não nomeia o gatilho com a palavra da GTK — a barra de "
        f"status dela diz {a03.NOME_DO_LADO['left']!r}, e a cura TRG-01 existe "
        f"porque um dia ela dizia `LEFT`: {erro.value!r}")


def test_o_que_chegou_ao_gatilho_nao_vira_recusa(a03):
    """A mordida gêmea: a cura não pode avançar longe demais."""
    ctx = _ctx(modo_no_disco="Off")
    _clicar.ctx = ctx  # type: ignore[attr-defined]
    _clicar("modo", {"lado": "e", "valor": "Resistance"}, _Ponte())


def test_a_ponte_sem_corpo_continua_calada(a03):
    """A ponte antiga e o dublê da régua não dizem ONDE a escrita parou."""
    class _Muda:
        def trigger_set_detalhado(self, *a, **k):
            return (True, "", {})

        def trigger_reset_detalhado(self, *a, **k):
            return (True, "", {})

    ctx = _ctx(modo_no_disco="Off")
    _clicar.ctx = ctx  # type: ignore[attr-defined]
    _clicar("modo", {"lado": "e", "valor": "Resistance"}, _Muda())


def test_o_ctx_nao_troca_simbolo_de_modulo() -> None:
    """`_ctx()` escreve a CENA e não troca `perfil.ativo` — é o que cura o vazamento."""
    from pacotes import perfil

    antes = perfil.ativo
    _ctx(modo_no_disco="Resistance")
    assert perfil.ativo is antes, (
        "`_ctx()` trocou `perfil.ativo` por atribuição crua. Foi assim que este "
        "arquivo envenenou a suíte até 05/09/2026: o dublê ficava no módulo e o "
        "casamento da aba 03 caía de 19 para 15 endereços no arquivo seguinte, "
        "acusando uma regressão que não existia.")
    assert perfil.ativo("qualquer")["triggers"]["left"]["mode"] == "Resistance", (
        "a cena escrita por `_ctx()` não chega ao dublê — a troca virou pura e "
        "o caminho do dado se perdeu junto")

