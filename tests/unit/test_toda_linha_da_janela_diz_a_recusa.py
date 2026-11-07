"""O-GESTO-DE-GRAVAR-A-OPCAO-DIZ-QUANDO-FALHA-01 — toda linha da janela, a extensão junto.

A recusa de gravar só aparecia nas linhas de rótulo à esquerda: o ``por_botao``, os ``jogos`` e as
entradas com glifo são o miolo da janela da Toque e da Lovense, e ali o botão só piscava. A nota
ficava depois de um gesto que gravou, e a extensão seguia no último arrastar de uma barra que a
janela devolvera ao guardado.

MORDIDAS (07/11/2026, executadas sobre a cura e devolvidas):
- sem a nota na grade do ``por_botao``, no ``_linha_da_entrada`` ou nos ``jogos``:
  ``test_todo_controle_diz_a_recusa_na_linha`` e ``test_os_jogos_dizem_a_recusa``;
- sem limpar a recusa velha ao gravar a opção: ``test_a_nota_sai_quando_outro_gesto_grava[modo]``;
- sem limpar ao gravar a chave: ``test_a_nota_sai_quando_outro_gesto_grava[chave]``;
- sem ``_a_extensao_volta_ao_guardado``: ``test_a_barra_que_nao_gravou_devolve_a_extensao``;
- sem o ``_desfazer_o_modo`` da recusa: ``test_o_modo_que_nao_gravou_devolve_a_extensao``.
"""
from __future__ import annotations

import os
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import desenho_da_experimental as exp
from hefesto_dualsense4unix.mods import instalador, opcoes
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    ctx,
    lar,
)
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import (  # noqa: F401
    VIVO,
    _Ponte,
    janela,
)
from tests.unit.test_toda_escolha_da_janela_da_extensao_grava_na_hora import (
    MOD,
    OPCOES,
    SUAVE,
    _controles,
    _gesto,
    _janela,
    _opcao,
)

_FRASE = "A opção não foi gravada: Sem espaço no dispositivo."
_COM_A_ENTRADA = [*OPCOES, _opcao("entrada_l2", "L2", "escolha", "Toques", "Nenhum", **SUAVE)]
_COM_A_CHAVE = [_opcao("ligada", "Ligada", "ligado", "Brinquedos", True), *_COM_A_ENTRADA]


def _sem_escrita(monkeypatch: pytest.MonkeyPatch) -> None:
    verdadeiro = os.replace

    def cheio(de: str, para: Any, **mais: Any) -> None:
        if ".gravando-" in str(de):
            raise OSError(28, "Sem espaço no dispositivo")
        verdadeiro(de, para, **mais)

    monkeypatch.setattr(instalador.os, "replace", cheio)


def _recusar(a07: Any, ctx: Any, ponte: _Ponte) -> None:  # noqa: F811
    with pytest.raises(RuntimeError, match="não foi gravada"):
        a07.guardar_opcao_da_modificacao(
            ctx, {"v": f"{MOD}:touchpad", "evento": "change", "valor": "Suave"}, ponte)
    assert f'{_FRASE}</span>' in a07._MEXIDA.html_mod


def test_todo_controle_diz_a_recusa_na_linha(
    janela: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch,  # noqa: F811
) -> None:
    a07, instalar, abrir = janela
    instalar(opcoes=_COM_A_ENTRADA)
    ponte = _Ponte(VIVO)
    a07.guardar_opcao_da_modificacao(
        ctx, {"v": f"{MOD}:servidor", "evento": "change", "valor": "Intiface Central"}, ponte)
    controles = _controles(_janela(abrir, ponte))
    assert {f"{MOD}:toques:circle", f"{MOD}:entrada_l2", f"{MOD}:endereco"} <= controles.keys()
    _sem_escrita(monkeypatch)
    for data_v, (tag, atributos, miolo) in controles.items():
        a07._MEXIDA.recusa_do_importar = {}
        evento, _ = _gesto(tag, atributos, miolo)
        with pytest.raises(RuntimeError, match="não foi gravada"):
            a07.guardar_opcao_da_modificacao(ctx, {"v": data_v, **evento}, ponte)
        assert _FRASE in a07._MEXIDA.html_mod, data_v


def test_os_jogos_dizem_a_recusa() -> None:
    html = exp._linha_da_opcao(exp.OpcaoDaJanela("m", "j", "Jogos", "jogos", [], nota=_FRASE))
    assert f'<span class="ky-recusa">{_FRASE}</span>' in html


@pytest.mark.parametrize(("frase", "palavra"), [
    ("O texto ficaria ilegível: «--fg» sobre «--app-bg» dá 1,2.", "Ilegível"),
    (_FRASE, "Não gravou"),
    ("O arquivo não foi gravado: Permissão negada.", "Não gravou"),
    ("O arquivo não foi apagado: Permissão negada.", "Não apagou"),
    ("O tema não troca cor nenhuma.", "Não ligou"),
])
def test_a_palavra_curta_diz_o_que_nao_aconteceu(frase: str, palavra: str) -> None:
    assert exp.recusa_curta(frase) == palavra
    assert f">{palavra}</span>" in exp.nota_curta(frase)


@pytest.mark.parametrize("gesto", ["modo", "chave"])
def test_a_nota_sai_quando_outro_gesto_grava(
    janela: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch, gesto: str,  # noqa: F811
) -> None:
    a07, instalar, abrir = janela
    instalar(opcoes=_COM_A_CHAVE, chave="ligada")
    ponte = _Ponte(VIVO)
    abrir(ponte)
    with monkeypatch.context() as sem_disco:
        _sem_escrita(sem_disco)
        _recusar(a07, ctx, ponte)

    if gesto == "modo":
        a07.modo_do_livre_da_modificacao(ctx, {"v": f"{MOD}:ao-vivo:segurar"}, ponte)
    else:
        a07.chave_da_modificacao(ctx, {"v": MOD}, ponte)
    assert _FRASE not in a07._MEXIDA.html_mod


def test_a_barra_que_nao_gravou_devolve_a_extensao(
    janela: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch,  # noqa: F811
) -> None:
    a07, instalar, abrir = janela
    instalar(opcoes=OPCOES)
    ponte = _Ponte(VIVO)
    abrir(ponte)
    a07.arrastar_a_opcao_da_modificacao(
        ctx, {"v": f"{MOD}:forca", "valor": "40", "carimbo": "1"}, ponte)
    _sem_escrita(monkeypatch)

    with pytest.raises(RuntimeError, match="não foi gravada"):
        a07.guardar_opcao_da_modificacao(
            ctx, {"v": f"{MOD}:forca", "evento": "change", "valor": "40", "carimbo": "2"}, ponte)

    enviados = [c for c in ponte.chamadas if c[0] == a07.METODO_DA_OPCAO]
    assert [c[1]["valor"] for c in enviados] == [40, 100]
    guardado = opcoes.ler(a07._a_instalada(MOD).manifesto, a07._lugares())
    assert enviados[-1][1] == {"mod": MOD, "id": "forca", "valor": guardado["forca"]}


def test_o_modo_que_nao_gravou_devolve_a_extensao(
    janela: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch,  # noqa: F811
) -> None:
    a07, instalar, abrir = janela
    instalar(opcoes=OPCOES)
    ponte = _Ponte(VIVO)
    abrir(ponte)
    a07.mover_o_livre_da_modificacao(
        ctx, {"v": f"{MOD}:ao-vivo", "valor": "20", "vivo": "1", "carimbo": "1"}, ponte)
    _sem_escrita(monkeypatch)

    with pytest.raises(RuntimeError, match="não foi gravada"):
        a07.modo_do_livre_da_modificacao(ctx, {"v": f"{MOD}:ao-vivo:segurar"}, ponte)

    guardado = opcoes.ler(a07._a_instalada(MOD).manifesto, a07._lugares())["ao-vivo:modo"]
    assert guardado != "segurar"
    soltos = [c[1]["modo"] for c in ponte.chamadas if c[0] == "mods.livre" and c[1]["soltou"]]
    assert soltos == ["segurar", guardado]
    assert a07._VIVA.modo == guardado
