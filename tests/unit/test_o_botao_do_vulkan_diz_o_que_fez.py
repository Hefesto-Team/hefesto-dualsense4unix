"""O-BOTAO-DO-VULKAN-NAO-RESPONDE-01 — o botão que agia calado e no verbo errado."""

from __future__ import annotations

from typing import Any

import pytest

pytest_plugins = ["tests.unit.test_a_09_sistema_fecha_a_paridade"]


def _mesa(a09: Any, monkeypatch: pytest.MonkeyPatch, *, ligado: bool,
          com_registro: bool = False, curou: list[Any] | None = None) -> None:
    """A escolha e o estado PELO DONO, e o `curar_todos` espionado."""
    from types import SimpleNamespace

    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv
    from hefesto_dualsense4unix.integrations import reposicao_dos_lancadores as rl

    cv.gravar_camadas_da_steam_fora(ligado)
    cv.gravar_estado(
        {"222": {"x": {"feito": "desligada", "valor_antes": "00000000"}}}
        if com_registro else {})
    monkeypatch.setattr(
        cv, "curar_todos",
        lambda *a, **k: (curou.append(k) if curou is not None else None)
        or [SimpleNamespace(mexeu=True, erro="")])
    monkeypatch.setattr(
        a09._emulacao, "frase_do_resultado",
        lambda r, devolver=False: "Devolvi em 1 jogo: x." if devolver else "?")
    monkeypatch.setattr(rl, "jogo_aberto", lambda: False)


def _clicar(gesto: Any, ctx: Any, texto: str = "") -> Any:
    from tests.unit.test_a_09_sistema_fecha_a_paridade import PonteDeMentira

    return gesto(ctx, {"texto": texto}, PonteDeMentira())


def test_a_pilula_segue_a_escolha_que_o_lancador_le(a09: Any) -> None:
    """Acesa é «o jogo nasce sem as camadas da Steam», e nada mais."""
    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

    cv.gravar_camadas_da_steam_fora(False)
    assert a09.vulkan_corrigido() is False
    cv.gravar_camadas_da_steam_fora(True)
    assert a09.vulkan_corrigido() is True


def test_o_clique_liga_e_desliga_pela_escolha(
        a09: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Um clique liga, o seguinte desliga — e a pílula segue o disco."""
    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

    _mesa(a09, monkeypatch, ligado=False)
    _clicar(a09.corrigir_vulkan, ctx)
    assert cv.camadas_da_steam_fora() is True
    _clicar(a09.corrigir_vulkan, ctx)
    assert cv.camadas_da_steam_fora() is False


def test_o_clique_escreve_o_recibo_na_tela(
        a09: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A QUEIXA DELA, presa por régua: "Clico em confirma e não aparece nada"."""
    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

    _mesa(a09, monkeypatch, ligado=False)
    _clicar(a09.corrigir_vulkan, ctx)
    assert a09._PAINEL[0] == cv.frase_do_ato(True), (
        f"o clique não deixou rastro na tela: {a09._PAINEL[0]!r}")


def test_o_recibo_diz_o_ato_que_aconteceu(
        a09: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ligar e desligar não produzem o mesmo recibo, e a devolução se conta."""
    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

    curou: list[Any] = []
    _mesa(a09, monkeypatch, ligado=True, com_registro=True, curou=curou)
    _clicar(a09.corrigir_vulkan, ctx)
    assert curou and curou[0]["religar"] is True and curou[0]["forcar"] is True
    assert a09._PAINEL[0] == f"{cv.frase_do_ato(False)} Devolvi em 1 jogo: x."
    assert cv.frase_do_ato(True) != cv.frase_do_ato(False)


def test_desligar_sem_nada_nosso_no_registro_nao_mexe_nele(
        a09: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """O registro dela só se abre quando há o que devolver."""
    curou: list[Any] = []
    _mesa(a09, monkeypatch, ligado=True, com_registro=False, curou=curou)
    _clicar(a09.corrigir_vulkan, ctx)
    assert curou == []


def test_ligar_nao_mexe_no_registro(
        a09: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ligar é a escolha que o lançador lê; o registro só se mexe no lançamento."""
    curou: list[Any] = []
    _mesa(a09, monkeypatch, ligado=False, com_registro=True, curou=curou)
    _clicar(a09.corrigir_vulkan, ctx)
    assert curou == []


def test_a_escolha_que_nao_grava_recusa_e_nao_diz_pronto(
        a09: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pasta de configuração sem escrita: a tela diz que não pegou."""
    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

    _mesa(a09, monkeypatch, ligado=False)

    def sem_escrita(*_a: Any, **_k: Any) -> None:
        raise PermissionError(13, "Permissão negada")

    monkeypatch.setattr(cv, "gravar_camadas_da_steam_fora", sem_escrita)
    a09._PAINEL[0] = None
    with pytest.raises(RuntimeError) as recusa:
        _clicar(a09.corrigir_vulkan, ctx)
    assert "Não consegui guardar" in str(recusa.value)
    assert a09._PAINEL[0] is None or "Pronto" not in a09._PAINEL[0]
    assert cv.camadas_da_steam_fora() is False


def test_a_lista_do_recibo_que_fica_e_curta_e_declarada() -> None:
    """A TELA-CALADA-03 continua valendo para os outros destrutivos."""
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


def test_a_recusa_pergunta_ao_dono_que_invalida_a_foto(
        a09: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Era `steam_game_running` direto, que lê uma FOTO de até 5 s."""
    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv
    from hefesto_dualsense4unix.integrations import reposicao_dos_lancadores as rl
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    de_verdade = rl.jogo_aberto
    curou: list[Any] = []
    _mesa(a09, monkeypatch, ligado=True, com_registro=True, curou=curou)
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
    assert cv.camadas_da_steam_fora() is True, "a recusa desligou a pílula pela metade"
