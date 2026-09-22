#!/usr/bin/env python3
"""O CONTADOR EM TODO CARTÃO — «◆ N jogos já sabem por onde entrar».

A palavra dela, 21/09/2026, olhando a aba Lançadores: *"falta o mesmo textinho
de contador da steam pros demais. pq não faz sentido só os ouitros não terem e
a steam ter. todos tem que serem iguais."*  <!-- noqa-acento: citação literal dela -->

Ela escolheu o texto entre três, e escolheu o contador no CORPO de todo cartão
LOCALIZADO, o zero inclusive. O que esta régua cobra, ponta a ponta:

    o perfil com ponte no disco     `prontuario_dos_jogos.classes_com_ponte`
    ∩ os jogos DAQUELE lançador     `desenho.medir_no_disco` (na vigia)
    → o número do cartão            `DoDisco.pontes_de`
    → o corpo de todo localizado    `desenho.contador_html`, igual nos oito

A MORDIDA DE CADA PONTA está na docstring do teste dela.

NADA AQUI TOCA A MÁQUINA DELA: os perfis são escritos num `tmp_path`, e a
biblioteca de cada lançador é dublada — uma régua que dependesse dos jogos
dela mediria a mesa, não o código.
"""
from __future__ import annotations

import json
import re
import types
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import prontuario_dos_jogos as pdj
from hefesto_dualsense4unix.interface import desenho_dos_lancadores as desenho

#: O contador como a TELA o mostra — o texto que ela escolheu.
_CONTADOR = re.compile(r"◆ (\d+) jogos? já sabem? por onde entrar")


def _numero(diz: str) -> int | None:
    """O N do contador no corpo, ou `None` se o corpo não o traz."""
    achado = _CONTADOR.search(diz)
    return int(achado.group(1)) if achado else None


def _todos_localizados(**extra) -> desenho.Leitura:
    """Uma leitura em que a Steam E os de fábrica foram achados."""
    onde = tuple((x.chave, f"/usr/bin/{x.chave}") for x in desenho.EMBUTIDOS)
    return desenho.Leitura(com_wrapper=("1",), instalados=1, onde_estao=onde,
                           **extra)


# --------------------------------------------------------------------------
# a tela — o mesmo contador nos oito
# --------------------------------------------------------------------------
def test_todo_cartao_localizado_abre_o_corpo_com_o_contador():
    """Os oito localizados dizem o contador — e o zero também se diz.

    A MORDIDA: troque o `diz=contador_html(…)` de `cartao_sem_censo` por
    `diz=""` e este teste reprova nomeando os cartões calados; tire a linha do
    contador de `cartao_da_steam` e ele reprova nomeando a Steam.
    """
    cartoes = desenho.cartoes(_todos_localizados())
    localizados = [c for c in cartoes if c.presente]
    assert len(localizados) >= 2, "a régua mediria um cartão só"
    sem = [c.chave for c in localizados
           if not c.diz.startswith(desenho.contador_html(0))]
    assert not sem, (
        f"cartão(ões) localizado(s) sem o contador abrindo o corpo: {sem}. "
        f"Ela pediu o mesmo texto em todos — «todos tem que serem iguais»")


def test_o_cartao_que_nao_achou_nao_conta():
    """Sem o lançador na máquina não há jogo dele — e o contador não nasce.

    Um «0 jogos já sabem» num cartão `NÃO LOCALIZADO` responderia uma pergunta
    que o produto não fez.
    """
    onde = tuple((x.chave, "") for x in desenho.EMBUTIDOS)
    for cartao in desenho.cartoes(desenho.Leitura(onde_estao=onde)):
        assert _numero(cartao.diz) is None, (
            f"o cartão {cartao.chave!r}, não localizado, traz o contador: "
            f"{cartao.diz!r}")


def test_o_numero_de_cada_cartao_e_o_do_disco_dele():
    """Cada cartão mostra o SEU número — e a Steam, o da `Leitura`.

    A MORDIDA: faça `DoDisco.pontes_de` devolver sempre 0 e este teste
    reprova no Heroic.
    """
    do_disco = desenho.DoDisco(pontes=(("heroic", 2), ("lutris", 1)))
    cartoes = {c.chave: c for c in desenho.cartoes(
        _todos_localizados(pontes=3, do_disco=do_disco))}
    assert _numero(cartoes["heroic"].diz) == 2
    assert _numero(cartoes["lutris"].diz) == 1
    assert _numero(cartoes[desenho.STEAM].diz) == 3
    assert "1 jogo já sabe por onde entrar" in cartoes["lutris"].diz, (
        "o singular sumiu — «1 jogos já sabem» é o erro que a tela mostraria")


# --------------------------------------------------------------------------
# o disco — perfis com ponte ∩ jogos do lançador
# --------------------------------------------------------------------------
def _perfil(pasta: Path, nome: str, dados: dict) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"{nome}.json").write_text(json.dumps(dados), encoding="utf-8")


def test_classes_com_ponte_so_conta_perfil_carimbado(tmp_path):
    """Só entra o perfil COM carimbo de ponte e `match` de critério.

    *"Ainda não sei"* é ausência, nunca uma ponte vazia — a mesma regra de
    `pontes_confirmadas`. A MORDIDA: tire o `continue` do perfil sem `ponte`
    e o segundo jogo entra na conta.
    """
    pasta = pdj.pasta_de_perfis(tmp_path)
    criterio = {"type": "criteria"}
    _perfil(pasta, "com", {"ponte": {"kind": "vpad"},
                           "match": {**criterio, "window_class": ["Com.Um.Jogo"]}})
    _perfil(pasta, "sem", {"match": {**criterio, "window_class": ["sem.ponte"]}})
    _perfil(pasta, "qualquer", {"ponte": {"kind": "vpad"}, "match": {"type": "any"}})
    (pasta / "quebrado.json").write_text("{", encoding="utf-8")

    assert pdj.classes_com_ponte(tmp_path) == {"com.um.jogo"}


def test_o_contador_casa_a_janela_sem_ligar_para_maiusculas(monkeypatch):
    """`medir_no_disco` conta os jogos DAQUELE lançador que têm ponte.

    A janela medida vem com a grafia do programa (`com.libretro.RetroArch`), e
    o perfil pode tê-la escrito de outro jeito. A MORDIDA: tire o `casefold` da
    conta em `medir_no_disco` e o número cai de 1 para 0.
    """
    jogos = [types.SimpleNamespace(classe_de_janela=c)
             for c in ("Com.Um.Jogo", "outro.jogo", "")]
    monkeypatch.setattr(desenho._censo, "biblioteca_do_cartao",
                        lambda chave, lar=None: types.SimpleNamespace(
                            resumo="", jogos=jogos))
    monkeypatch.setattr(desenho._caixa, "app_ids_do_cartao", lambda *a, **k: ())
    monkeypatch.setattr(desenho, "resposta_do_flatpak", lambda *a, **k: "")

    medido = desenho.medir_no_disco((("heroic", "/usr/bin/heroic"),),
                                    com_ponte=frozenset({"com.um.jogo"}))
    assert medido.pontes_de("heroic") == 1
    assert medido.pontes_de("lutris") == 0, (
        "um lançador que a busca não achou ganhou número")


def test_a_vigia_leva_as_pontes_do_disco_ate_a_conta(monkeypatch, tmp_path):
    """`_ler_do_disco` pergunta ao prontuário e entrega a resposta à conta.

    SEM ESTA RÉGUA as duas pontas de cima poderiam estar certas e o número
    nunca chegar à tela — a forma de defeito que esta casa chama de *pintura
    perdida*. A MORDIDA: apague o `com_ponte=com_ponte` da chamada a
    `medir_no_disco` e este teste reprova.
    """
    from hefesto_dualsense4unix.integrations import jogos_locais as jl
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07

    recebido: list[frozenset[str]] = []

    def _medir(onde, declarados=(), lar=None, raiz_sistema=None,
               com_ponte=frozenset()):
        recebido.append(com_ponte)
        return desenho.SEM_DISCO

    monkeypatch.setattr(jl, "pastas_de_atalhos", lambda: [tmp_path])
    monkeypatch.setattr(pdj, "classes_com_ponte", lambda: {"com.um.jogo"})
    monkeypatch.setattr(desenho, "medir_no_disco", _medir)
    a07._ler_do_disco()
    assert recebido == [frozenset({"com.um.jogo"})], recebido


@pytest.mark.parametrize("pontes, texto", [
    (0, "0 jogos já sabem por onde entrar"),
    (1, "1 jogo já sabe por onde entrar"),
    (5, "5 jogos já sabem por onde entrar"),
])
def test_o_texto_e_o_que_ela_escolheu(pontes, texto):
    """A frase é a da escolha dela, com o plural certo."""
    assert texto in desenho.contador_html(pontes)
