"""O-BOTAO-DO-VULKAN-NAO-RESPONDE-01 — o botão que agia calado e no verbo errado.

**Queixa dela, 21/09/2026**, com a janela aberta e um jogo rodando:

    *"tirar a sobreposição do Vulcan. Clico em confirma e não aparece nada. Os
    logs não falam nada que preste também."*  — e, logo depois, *"não sei se
    esse botão presta tambem."*  <!-- noqa-acento: citação literal dela -->

**MEDIDO NA MÁQUINA DELA no mesmo dia**, com `camadas_vulkan --relatorio`: há
UM prefixo com camada (o Sackboy) e as duas do Epic estão **desligadas** — quer
dizer, nós já as tiramos. Logo `tem_tirar` é `False` e `tem_devolver` é `True`:
**o segundo clique dela ia DEVOLVER a sobreposição**, com o botão dizendo
"Tirar" e o armado dizendo "Confirma?".

Os dois defeitos que este arquivo prende:

1. **O verbo não estava onde o dedo clica.** A frase do painel avisava; o olho
   dela estava no botão.
2. **O clique 2 não deixava rastro nenhum na tela.** É o único dos seis
   destrutivos desta aba cujo efeito é invisível — ele escreve no registro do
   prefixo Wine, e a linha do exame diz `✓ OK` antes e depois.

**25/09/2026 — A-09-SISTEMA-EM-TRES-SECOES-01.** O botão virou o ligável
«Corrigir Vulkan» (a pílula do Modo Freestyle), de UM clique: aceso quando há
camada que nós tiramos, e o clique desliga devolvendo. O defeito 1 (o verbo
longe do dedo) perdeu o objeto — o ligável não tem segundo tempo —; o defeito 2
(o ato que não deixa rastro) continua preso aqui.
"""

from __future__ import annotations

from typing import Any

import pytest

pytest_plugins = ["tests.unit.test_a_09_sistema_fecha_a_paridade"]


def _censo(a09: Any, monkeypatch: pytest.MonkeyPatch, *,
           tem_tirar: bool, tem_devolver: bool,
           curou: list[Any] | None = None) -> None:
    """O censo injetado, com o que ele achou — e o `curar_todos` espionado.

    `tem_devolver` é o estado da PÍLULA (há camada que nós tiramos), e é por
    ele que o ligável decide o verbo; `tem_tirar` é o censo ter sobra.
    """
    from types import SimpleNamespace

    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv
    from hefesto_dualsense4unix.integrations import reposicao_dos_lancadores as rl

    monkeypatch.setattr(
        cv, "censo",
        lambda *a, **k: [SimpleNamespace(sobras=["uma"] if tem_tirar else [])])
    monkeypatch.setattr(
        cv, "curar_todos",
        lambda *a, **k: (curou.append(k) if curou is not None else None) or [])
    monkeypatch.setattr(
        a09._emulacao, "frase_do_resultado",
        lambda r, devolver=False: "religuei duas camadas" if devolver
        else "desliguei duas camadas")
    monkeypatch.setattr(rl, "jogo_aberto", lambda: False)
    a09._VULKAN.clear()
    a09._VULKAN.update(tiradas=1 if tem_devolver else 0, postas=0, prefixos=3)


def _clicar(gesto: Any, ctx: Any, texto: str = "") -> Any:
    from tests.unit.test_a_09_sistema_fecha_a_paridade import PonteDeMentira

    return gesto(ctx, {"texto": texto}, PonteDeMentira())


# ---------------------------------------------------------------------------
# 1 — O VERBO NO BOTÃO: SAIU (o ligável não tem segundo tempo)
# ---------------------------------------------------------------------------
def test_a_pilula_segue_o_que_nos_tiramos(a09: Any) -> None:
    """Aceso é «há camada que NÓS desligamos»; sem censo ainda, não se afirma nada."""
    a09._VULKAN.clear()
    assert a09.vulkan_corrigido() is None
    a09._VULKAN.update(tiradas=2, postas=0, prefixos=3)
    assert a09.vulkan_corrigido() is True
    a09._VULKAN.update(tiradas=0)
    assert a09.vulkan_corrigido() is False
    a09._VULKAN.clear()


# ---------------------------------------------------------------------------
# 2 — O ATO DEIXA RASTRO NA TELA
# ---------------------------------------------------------------------------
def test_o_clique_escreve_o_recibo_na_tela(
        a09: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A QUEIXA DELA, presa por régua: "Clico em confirma e não aparece nada".

    MORDE: tire `"corrigir-vulkan"` de `RECIBO_QUE_FICA_NA_TELA` e a régua
    reprova com o painel vazio.
    """
    curou: list[Any] = []
    _censo(a09, monkeypatch, tem_tirar=False, tem_devolver=True, curou=curou)

    _clicar(a09.corrigir_vulkan, ctx)

    assert curou and curou[0]["religar"] is True, curou
    assert a09._PAINEL[0] == "religuei duas camadas", (
        f"o clique não deixou rastro na tela: {a09._PAINEL[0]!r}")


def test_o_recibo_diz_o_ato_que_aconteceu(
        a09: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tirar e devolver não podem produzir o mesmo recibo."""
    curou: list[Any] = []
    _censo(a09, monkeypatch, tem_tirar=True, tem_devolver=False, curou=curou)

    _clicar(a09.corrigir_vulkan, ctx)

    assert curou and curou[0]["religar"] is False and curou[0]["forcar"] is True
    assert a09._PAINEL[0] == "desliguei duas camadas"


def test_sem_nada_a_tirar_o_ligavel_recusa_e_nao_acende(
        a09: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Um ligável que acende sem ter feito nada mentiria sobre o jogo.

    MORDE: tire a pergunta ao censo de `corrigir_vulkan`.
    """
    curou: list[Any] = []
    _censo(a09, monkeypatch, tem_tirar=False, tem_devolver=False, curou=curou)
    with pytest.raises(RuntimeError) as recusa:
        _clicar(a09.corrigir_vulkan, ctx)
    assert "Nenhum jogo" in str(recusa.value)
    assert curou == []


def test_a_lista_do_recibo_que_fica_e_curta_e_declarada() -> None:
    """A TELA-CALADA-03 continua valendo para os outros destrutivos.

    A regra que cabe nas duas: **recibo de status sai; recibo de ato que não se
    vê FICA**. Um gesto novo nesta lista é um ato que se vê no diff.
    """
    from pacotes import a09_sistema as a09

    assert a09.RECIBO_QUE_FICA_NA_TELA == ("corrigir-vulkan",)
    for gesto_ in a09.DESTRUTIVOS:
        assert gesto_ not in a09.RECIBO_QUE_FICA_NA_TELA


def test_o_recibo_dos_outros_continua_fora_da_tela(
        a09: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDE: ponha o gesto do serviço na lista e esta régua reprova."""
    a09._PAINEL[0] = None
    a09._relatar_o_recibo(a09.DESLIGAR, "parei o serviço")
    assert a09._PAINEL[0] is None


# ---------------------------------------------------------------------------
# 3 — A RECUSA POR JOGO ABERTO, E O DONO QUE ELA PASSOU A PERGUNTAR
# ---------------------------------------------------------------------------
def test_a_recusa_pergunta_ao_dono_que_invalida_a_foto(
        a09: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Era `steam_game_running` direto, que lê uma FOTO de até 5 s.

    MORDE: volte a chamar `slo.steam_game_running()` aqui e a régua reprova,
    porque ninguém invalida a varredura antes.
    """
    from hefesto_dualsense4unix.integrations import reposicao_dos_lancadores as rl
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    de_verdade = rl.jogo_aberto
    curou: list[Any] = []
    _censo(a09, monkeypatch, tem_tirar=True, tem_devolver=False, curou=curou)
    monkeypatch.setattr(rl, "jogo_aberto", de_verdade)

    passos: list[str] = []
    monkeypatch.setattr(slo, "invalidar_varredura_de_proc",
                        lambda: passos.append("invalidou"))
    monkeypatch.setattr(slo, "steam_game_running",
                        lambda: passos.append("perguntou") or True)

    with pytest.raises(RuntimeError) as erro:
        _clicar(a09.corrigir_vulkan, ctx)

    assert passos == ["invalidou", "perguntou"], passos
    assert not curou
    assert "jogo aberto" in str(erro.value).lower()
