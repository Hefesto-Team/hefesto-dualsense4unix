#!/usr/bin/env python3
"""Os avisos do produto: o mais grave em cima, e a lista do exame da 09 os recebe."""
from __future__ import annotations

import pathlib
import sys
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"


for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.app.actions.jogar import painel
from pacotes import Contexto
from pacotes import a01_jogar as aba

VIVO_NAVEGACAO: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": False, "flavor": "dualsense"},
    "paused": False,
    "controllers": [{"uniq": "aa:bb:cc:00:00:01", "connected": True,
                     "player_slot": 1}],
}


def _ctx(state: dict[str, Any]) -> Contexto:
    return Contexto(state=state, mesa=[], conectados=[], estados={})


def _acesas(fora: list[dict[str, str]]) -> tuple[list[str], list[str]]:
    """Os selos e os textos da lista, na ordem em que ela os devolveu."""
    return [a["selo"] for a in fora], [a["texto"] for a in fora]


def _so_estes(monkeypatch: Any, avisos: list[dict[str, str]]) -> None:
    """Cala as outras fontes: a régua mede a ORDEM, não quem fala."""
    monkeypatch.setattr(painel, "avisos_do_estado", lambda _s: list(avisos))


def test_o_mais_grave_sobe_e_a_ordem_e_a_da_gravidade(monkeypatch: Any) -> None:
    """A PAUSA vem antes do PERFIL, mesmo chegando depois dele."""
    _so_estes(monkeypatch, [
        {"selo": "PERFIL", "texto": "cadeado", "fonte": "x"},
        {"selo": "RÁDIO", "texto": "frágil", "fonte": "x"},
        {"selo": "GAMEPAD", "texto": "degradado", "fonte": "x"},
    ])
    selos, _ = _acesas(aba.coluna_de_atencao(_ctx(VIVO_NAVEGACAO)))
    assert selos == ["GAMEPAD", "RÁDIO", "PERFIL"], (
        f"a coluna não pôs o mais grave em cima: {selos!r}")


def test_a_pausa_vence_tudo_porque_ela_invalida_tudo(monkeypatch: Any) -> None:
    """Com o Hefesto em pausa, nada do resto está acontecendo."""
    _so_estes(monkeypatch, [
        {"selo": "RÁDIO", "texto": "frágil", "fonte": "x"},
        {"selo": "PAUSA", "texto": "em pausa", "fonte": "x"},
    ])
    selos, _ = _acesas(aba.coluna_de_atencao(_ctx(VIVO_NAVEGACAO)))
    assert selos[0] == "PAUSA", f"a pausa não subiu: {selos!r}"


def test_a_ordem_e_estavel_entre_iguais(monkeypatch: Any) -> None:
    """Dois avisos do mesmo selo mantêm a ordem em que as fontes falaram."""
    _so_estes(monkeypatch, [
        {"selo": "PERFIL", "texto": "primeiro", "fonte": "x"},
        {"selo": "PERFIL", "texto": "segundo", "fonte": "y"},
    ])
    _, textos = _acesas(aba.coluna_de_atencao(_ctx(VIVO_NAVEGACAO)))
    assert textos == ["primeiro", "segundo"], (
        f"a ordem entre iguais mudou: {textos!r}")


def test_a_lista_leva_todos_os_avisos(monkeypatch: Any) -> None:
    """Dez avisos, dez linhas: a lista do exame da 09 não tem o teto da coluna.

    A MORDIDA: corte a devolução de `coluna_de_atencao` em três (o teto que a
    coluna da Jogar tinha) e esta régua reprova — sete avisos somem calados.
    """
    _so_estes(monkeypatch, [{"selo": "PAUSA", "texto": str(i), "fonte": "x"}
                            for i in range(10)])
    _, textos = _acesas(aba.coluna_de_atencao(_ctx(VIVO_NAVEGACAO)))
    assert textos == [str(i) for i in range(10)], (
        f"a lista cortou avisos: {textos!r}")


def test_o_que_o_status_da_09_ja_diz_nao_se_repete_no_exame() -> None:
    """Pausa, detector cego e Freestyle: o painel os diz, e eles ficam fora da lista da 09."""
    from hefesto_dualsense4unix.interface import sistema as aba_sistema

    estado = {**VIVO_NAVEGACAO, "paused": True, "freestyle_ligado": True,
              "window_detect_backend": "x11", "window_detect_seeing": False,
              "window_detect_reason": "sem_conexao_x"}
    ctx = _ctx(estado)
    tres = {"home_actions.texto_da_pausa", "home_actions.texto_do_cadeado_cego",
            "home_actions.autoswitch_lock_text"}
    no_painel = {a["fonte"] for a in painel.avisos_do_estado(estado)}
    assert tres <= no_painel, f"o painel perdeu uma das três: {sorted(tres - no_painel)}"
    na_09 = {a["fonte"] for a in aba.coluna_de_atencao(ctx)} & tres
    assert not na_09, f"voltou à lista da 09, ao lado da linha que já diz o mesmo: {na_09}"
    assert aba_sistema.status_do_servico("online_systemd", estado)["selo"] == "PAUSADO"
    assert aba_sistema.status_da_troca(estado)["selo"] == "SEM VER"


def test_a_lista_do_exame_da_09_recebe_os_avisos(monkeypatch: Any) -> None:
    """O aviso entra no fim da lista do exame, com o selo AVISO do desenho.

    O SELO NÃO SE DIGITA: o veredito é ``[WARN]`` e quem o traduz é
    `interface/sistema.exame`, o mesmo dono que traduz as linhas do `doctor`.

    A MORDIDA: faça `_com_os_avisos` devolver o `exame` sem tocar e a frase da
    pausa some da lista — reprova na primeira asserção.
    """
    from pacotes import a09_sistema

    frase = "O Hefesto está em pausa."
    monkeypatch.setattr(aba, "coluna_de_atencao", lambda _c: [
        {"selo": "PAUSA", "texto": frase, "fonte": "home_actions.texto_da_pausa"}])
    exame = {"linhas": [{"selo": "OK", "cls": "ok", "g": "✓", "txt": "do doctor"}],
             "vazio": ""}
    fora = a09_sistema._com_os_avisos(exame, _ctx(VIVO_NAVEGACAO))
    assert [linha["txt"] for linha in fora["linhas"]] == ["do doctor", frase], (
        f"o aviso não entrou no fim do exame: {fora['linhas']!r}")
    assert fora["linhas"][-1]["selo"] == "AVISO"
    assert frase in a09_sistema._html_do_exame(fora)


def test_o_exame_que_nao_respondeu_nao_some_atras_do_aviso(monkeypatch: Any) -> None:
    """Sem linha do exame e com aviso, a frase do vazio vira uma linha de NOTA."""
    from pacotes import a09_sistema

    monkeypatch.setattr(aba, "coluna_de_atencao", lambda _c: [
        {"selo": "RÁDIO", "texto": "o rádio está frágil", "fonte": "x"}])
    nao_respondeu = a09_sistema._tela.exame(None)
    fora = a09_sistema._com_os_avisos(nao_respondeu, _ctx(VIVO_NAVEGACAO))
    textos = [linha["txt"] for linha in fora["linhas"]]
    assert textos == [nao_respondeu["vazio"], "o rádio está frágil"], textos


def test_o_pacote_da_09_passa_o_exame_pelos_avisos() -> None:
    """`a09_sistema.pacote` chama `_com_os_avisos` antes de desenhar o exame.

    Medido pelo FONTE, e não pelo pacote inteiro: ele pergunta ao `systemctl`,
    ao disco e ao Proton, e cada dublê a mais é uma chance de a régua medir o
    dublê. O que se cobra aqui é a costura; o que ela faz, as duas acima.

    A MORDIDA: troque `_html_do_exame(_com_os_avisos(exame, ctx))` por
    `_html_do_exame(exame)` e esta régua reprova.
    """
    import ast

    fonte = (INTERFACE / "pacotes" / "a09_sistema.py").read_text(encoding="utf-8")
    pacote = next(no for no in ast.walk(ast.parse(fonte))
                  if isinstance(no, ast.FunctionDef) and no.name == "pacote")
    chamadas = {no.func.id for no in ast.walk(pacote)
                if isinstance(no, ast.Call) and isinstance(no.func, ast.Name)}
    assert "_com_os_avisos" in chamadas, (
        "o pacote da 09 deixou de levar os avisos do produto ao exame")
