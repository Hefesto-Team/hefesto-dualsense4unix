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
"""

from __future__ import annotations

from typing import Any

import pytest

pytest_plugins = ["tests.unit.test_a_09_sistema_fecha_a_paridade"]


def _censo(a09: Any, monkeypatch: pytest.MonkeyPatch, *,
           tem_tirar: bool, tem_devolver: bool,
           curou: list[Any] | None = None) -> None:
    """O censo injetado, com o que ele achou — e o `curar_todos` espionado."""
    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv
    from hefesto_dualsense4unix.integrations import reposicao_dos_lancadores as rl

    monkeypatch.setattr(cv, "censo", lambda *a, **k: ["um-prefixo"])
    monkeypatch.setattr(cv, "pastas_compatdata", lambda *a, **k: ["/uma/pasta"])
    monkeypatch.setattr(
        cv, "curar_todos",
        lambda *a, **k: (curou.append(k) if curou is not None else None) or [])
    monkeypatch.setattr(
        a09._emulacao, "frase_do_censo",
        lambda p, bibliotecas=1: ("o censo", tem_tirar, tem_devolver))
    monkeypatch.setattr(
        a09._emulacao, "frase_do_resultado",
        lambda r, devolver=False: "religuei duas camadas" if devolver
        else "desliguei duas camadas")
    monkeypatch.setattr(rl, "jogo_aberto", lambda: False)


def _clicar(gesto: Any, ctx: Any, texto: str = "") -> Any:
    from tests.unit.test_a_09_sistema_fecha_a_paridade import PonteDeMentira

    return gesto(ctx, {"texto": texto}, PonteDeMentira())


# ---------------------------------------------------------------------------
# 1 — O VERBO VAI PARA O BOTÃO
# ---------------------------------------------------------------------------
def test_o_botao_armado_diz_devolver_quando_e_isso_que_ele_fara(
        a09: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """O CASO DELA, exatamente: nada a tirar, só a devolver.

    MORDE: devolva o `CONFIRMA` genérico a `_CONFIRMA_DO_GESTO` e a régua
    reprova — o botão volta a dizer só "Confirma?" sobre um ato que é o
    contrário do nome dele.
    """
    _censo(a09, monkeypatch, tem_tirar=False, tem_devolver=True)

    carga = _clicar(a09.procurar_camadas, ctx)

    assert carga["blocos"][a09._seletor("procurar-camadas")] == (
        a09.CONFIRMA_DEVOLVER)


def test_o_botao_armado_diz_tirar_quando_ha_o_que_tirar(
        a09: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """E o caso comum continua dizendo o verbo certo — senão a régua de cima
    passaria com o rótulo cravado."""
    _censo(a09, monkeypatch, tem_tirar=True, tem_devolver=False)

    carga = _clicar(a09.procurar_camadas, ctx)

    assert carga["blocos"][a09._seletor("procurar-camadas")] == (
        a09.CONFIRMA_TIRAR)


def test_os_dois_verbos_sao_palavras_diferentes() -> None:
    """Sem isto, as duas réguas acima passariam com um rótulo só."""
    from pacotes import a09_sistema as a09

    assert a09.CONFIRMA_TIRAR != a09.CONFIRMA_DEVOLVER
    assert a09.CONFIRMA not in (a09.CONFIRMA_TIRAR, a09.CONFIRMA_DEVOLVER)


def test_o_verbo_do_botao_vale_como_consentimento(
        a09: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """O piloto manda o `textContent` DO BOTÃO. Se ele diz o verbo, é o verbo
    que volta — e recusá-lo mataria o clique 2 que o próprio botão ofereceu.

    MORDE: volte `_confirmado` a comparar `rotulo == CONFIRMA` e a régua
    reprova, porque o segundo clique passa a rearmar em vez de agir.
    """
    curou: list[Any] = []
    _censo(a09, monkeypatch, tem_tirar=False, tem_devolver=True, curou=curou)

    _clicar(a09.procurar_camadas, ctx)
    _clicar(a09.procurar_camadas, ctx, a09.CONFIRMA_DEVOLVER)

    assert curou, "o consentimento com o verbo do botão não foi aceito"
    assert curou[0].get("religar") is True


def test_o_verbo_de_um_gesto_nao_arma_outro(
        a09: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A palavra específica vale SÓ para o gesto que a ofereceu."""
    _censo(a09, monkeypatch, tem_tirar=False, tem_devolver=True)
    _clicar(a09.procurar_camadas, ctx)

    # o «Parar o serviço» não aceita a palavra do Vulkan como consentimento
    assert a09._confirmado({"texto": a09.CONFIRMA_DEVOLVER}, a09.DESLIGAR) is False


# ---------------------------------------------------------------------------
# 2 — O CLIQUE 2 DEIXA RASTRO
# ---------------------------------------------------------------------------
def test_o_clique_dois_escreve_o_recibo_na_tela(
        a09: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A QUEIXA DELA, presa por régua: "Clico em confirma e não aparece nada".

    MORDE: tire `"procurar-camadas"` de `RECIBO_QUE_FICA_NA_TELA` e a régua
    reprova com o painel vazio — que é o estado em que ela clicou.
    """
    _censo(a09, monkeypatch, tem_tirar=False, tem_devolver=True)

    _clicar(a09.procurar_camadas, ctx)
    _clicar(a09.procurar_camadas, ctx, a09.CONFIRMA_DEVOLVER)

    assert a09._PAINEL[0] == "religuei duas camadas", (
        f"o clique 2 não deixou rastro na tela: {a09._PAINEL[0]!r}")


def test_o_recibo_diz_o_ato_que_aconteceu(
        a09: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tirar e devolver não podem produzir o mesmo recibo."""
    _censo(a09, monkeypatch, tem_tirar=True, tem_devolver=False)

    _clicar(a09.procurar_camadas, ctx)
    _clicar(a09.procurar_camadas, ctx, a09.CONFIRMA_TIRAR)

    assert a09._PAINEL[0] == "desliguei duas camadas"


def test_a_lista_do_recibo_que_fica_e_curta_e_declarada() -> None:
    """A TELA-CALADA-03 continua valendo para os outros cinco destrutivos.

    A regra que cabe nas duas: **recibo de status sai; recibo de ato que não se
    vê FICA**. Um gesto novo nesta lista é um ato que se vê no diff.
    """
    from pacotes import a09_sistema as a09

    assert a09.RECIBO_QUE_FICA_NA_TELA == ("procurar-camadas",)
    for gesto_ in a09.DESTRUTIVOS:
        if gesto_ != "procurar-camadas":
            assert gesto_ not in a09.RECIBO_QUE_FICA_NA_TELA


def test_o_recibo_dos_outros_continua_fora_da_tela(
        a09: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDE: ponha `desligar` na lista e esta régua reprova."""
    a09._PAINEL[0] = None
    a09._relatar_o_recibo(a09.DESLIGAR, "parei o serviço")
    assert a09._PAINEL[0] is None


# ---------------------------------------------------------------------------
# 3 — A RECUSA POR JOGO ABERTO, E O DONO QUE ELA PASSOU A PERGUNTAR
# ---------------------------------------------------------------------------
def test_a_recusa_pergunta_ao_dono_que_invalida_a_foto(
        a09: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Era `steam_game_running` direto, que lê uma FOTO de até 5 s.

    Decidir um ato destrutivo sobre uma foto velha é decidir sobre um jogo que
    já fechou — ou não ver um que acabou de abrir. E o dono novo alcança o
    Heroic e o Lutris, que lançam pelo `umu` e se anunciam como Steam.

    MORDE: volte a chamar `slo.steam_game_running()` aqui e a régua reprova,
    porque ninguém invalida a varredura antes.
    """
    from hefesto_dualsense4unix.integrations import reposicao_dos_lancadores as rl
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    # O `jogo_aberto` DE VERDADE tem de correr aqui: é ele que se está medindo.
    # `_censo` o dubla para `False` (todas as outras réguas precisam disso), e
    # esta o devolve — guardado ANTES, senão o que volta é o dublê.
    de_verdade = rl.jogo_aberto
    curou: list[Any] = []
    _censo(a09, monkeypatch, tem_tirar=True, tem_devolver=False, curou=curou)
    monkeypatch.setattr(rl, "jogo_aberto", de_verdade)

    passos: list[str] = []
    monkeypatch.setattr(slo, "invalidar_varredura_de_proc",
                        lambda: passos.append("invalidou"))
    monkeypatch.setattr(slo, "steam_game_running",
                        lambda: passos.append("perguntou") or True)

    _clicar(a09.procurar_camadas, ctx)
    with pytest.raises(RuntimeError) as erro:
        _clicar(a09.procurar_camadas, ctx, a09.CONFIRMA_TIRAR)

    assert passos == ["invalidou", "perguntou"], passos
    assert not curou
    assert "jogo aberto" in str(erro.value).lower()


def test_a_recusa_desarma_o_verbo(
        a09: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Recusado o clique 2, o botão não pode ficar preso em "Confirma devolver?".

    Um verbo pendurado faria o tique seguinte oferecer um segundo tempo que já
    foi recusado.
    """
    from hefesto_dualsense4unix.integrations import reposicao_dos_lancadores as rl

    _censo(a09, monkeypatch, tem_tirar=False, tem_devolver=True)
    _clicar(a09.procurar_camadas, ctx)
    monkeypatch.setattr(rl, "jogo_aberto", lambda: True)

    with pytest.raises(RuntimeError):
        _clicar(a09.procurar_camadas, ctx, a09.CONFIRMA_DEVOLVER)

    assert "procurar-camadas" not in a09._CONFIRMA_DO_GESTO
