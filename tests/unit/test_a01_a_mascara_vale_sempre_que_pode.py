#!/usr/bin/env python3
"""A máscara: ela vale sempre que PODE valer, e a tela para de ficar calada.

A QUEIXA É DELA, 04/09/2026, e é a primeira da lista:

    *"independente do modo a mascara deve funcionar ali sempre. E todas as
     demais features do programa também."*

O QUE FOI MEDIDO — e esta régua tranca cada fato:

1. **`gamepad.mask.set` grava SEMPRE**, sem gate de modo
   (`daemon/ipc_handlers.py:4022`); `set_mask` persiste em
   `controller_masks.json`; `mascara_efetiva` é consultada na criação de todo
   gamepad virtual (`gamepad.py:1322`, `uinput_gamepad.py:187`). **Logo a
   escolha dela JÁ vale sempre que pode valer** — o motor estava pronto;
2. o que faltava era a TELA dizer isso. Fora do modo `gamepad` não existe vpad,
   então o clique era aceito, gravado, e não mudava nada que se visse — que é
   exatamente o que ela sente como *"não funciona"*;
3. o chip **Nintendo Pro** recusa em TODO modo: `mascaras_validas()` devolve
   `{dualsense, xbox}`. Um botão que nunca funciona não pode parecer que
   funciona.

AS DUAS CURAS SÃO DIFERENTES DE PROPÓSITO, e a diferença é a D-03 dela lida com
cuidado (*"cinza antes, com a razão na dica"*):

    a máscara fora do modo jogo   → RESSALVA. Ela PODE escolher agora, e a
                                    escolha vale quando o vpad nascer. Apagar o
                                    chip diria "você não pode escolher", que é
                                    falso — e trocaria a queixa dela por outra
                                    pior.
    o Nintendo Pro                → CINZA. Ele nunca pode. É o caso em que o
                                    cinza é a verdade.

NOTA DATADA — 13/09/2026, JOGAR-A-FAIXA-QUE-PULA-01 §3.1: a RESSALVA saiu da
tela (*"em todas as abas da interface"*, TELA-CALADA-01). O motor que ela
anunciava continua trancado aqui; o que mudou de contrato é a metade 2.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import monta
from hefesto_dualsense4unix.interface import onde
from pacotes import Contexto
from pacotes import a01_jogar as aba

VIVO_GAMEPAD: dict[str, Any] = {
    "connected": True, "native_mode": False,
    "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
    "paused": False,
}
VIVO_NATIVO: dict[str, Any] = {
    "connected": True, "native_mode": True,
    "gamepad_emulation": {"enabled": False, "flavor": "dualsense"},
    "paused": False,
}
VIVO_NAVEGACAO: dict[str, Any] = {
    "connected": True, "native_mode": False,
    "gamepad_emulation": {"enabled": False, "flavor": "dualsense"},
    "paused": False,
}


def _ctx(state: dict[str, Any]) -> Contexto:
    return Contexto(state=state, mesa=[], conectados=[], estados={})


def test_a_escolha_da_mascara_persiste_e_vale_na_criacao_do_vpad() -> None:
    """As duas pontas do caminho que a queixa dela supõe quebrado."""
    from hefesto_dualsense4unix.daemon.subsystems import external_mask

    assert hasattr(external_mask.registro_de_mascaras(), "set_mask")
    fonte = (RAIZ / "src/hefesto_dualsense4unix/daemon/subsystems/gamepad.py"
             ).read_text(encoding="utf-8")
    assert "mascara_efetiva(" in fonte, (
        "a criação do gamepad virtual deixou de consultar `mascara_efetiva` — a "
        "escolha por aparelho parou de valer, e a ressalva da tela passou a "
        "prometer o que não acontece")


def test_o_gesto_da_mascara_nao_tem_gate_de_modo() -> None:
    """*"independente do modo"* — e o gesto não pergunta o modo a ninguém."""
    import inspect

    corpo = inspect.getsource(aba.mascara_do_controle)
    for proibido in ("modo_vivo", "native_mode", "MODE_GAMEPAD", "mode_of_state"):
        assert proibido not in corpo, (
            f"o gesto da máscara voltou a olhar o modo ({proibido!r}): a decisão "
            "dela é que a escolha vale em qualquer um")


@pytest.mark.parametrize("estado", [VIVO_NATIVO, VIVO_NAVEGACAO])
def test_fora_do_modo_jogo_a_escolha_fica_guardada_sem_frase_na_tela(
        estado: dict[str, Any]) -> None:
    """Os DOIS modos sem vpad — e a frase que os anunciava saiu da tela."""
    fora = aba.pacote(_ctx(estado))
    assert fora["mascara-ressalva"] == "", (
        f"a ressalva voltou a ser pintada fora do modo jogo: "
        f"{fora['mascara-ressalva']!r}")


def test_no_modo_jogo_a_ressalva_nao_existe() -> None:
    """Com o vpad de pé a escolha vale AGORA — e a linha não ocupa nada."""
    assert aba.pacote(_ctx(VIVO_GAMEPAD))["mascara-ressalva"] == ""


def test_sem_daemon_a_ressalva_nao_afirma_nada() -> None:
    """`mode_of_state({})` devolve **desktop** — a armadilha desta aba.

    Sem a guarda, um tique sem resposta acusaria "o Hefesto não está entregando
    o controle ao jogo" sobre um estado que ninguém leu.
    """
    assert aba.pacote(Contexto(state={}, mesa=[], conectados=[],
                               estados={}))["mascara-ressalva"] == ""


def test_a_ressalva_nao_manda_ligar_o_que_ja_esta_ligado() -> None:
    """A frase não nomeia o modo, e é escolha medida."""
    frase = aba.RESSALVA_DA_MASCARA.lower()
    for armadilha in ("ligue", "ligado", "modo nativo", "navegação"):
        assert armadilha not in frase, (
            f"a ressalva nomeia um modo/uma ação que não vale nos dois casos: "
            f"{armadilha!r} em {aba.RESSALVA_DA_MASCARA!r}")


def test_o_produto_diz_quais_mascaras_ele_monta() -> None:
    """A lista não se digita: ela sai do catálogo do vpad.

    A MORDIDA: troque `mascaras_montaveis()` por um literal
    `{"DualSense", "Xbox 360"}` e a régua ainda passa hoje — mas o gerador
    deixa de acender o chip sozinho no dia em que o produto aprender a montar
    um terceiro. Esta asserção é o que amarra os dois lados.
    """
    from hefesto_dualsense4unix.daemon.subsystems.external_mask import mascaras_validas
    from hefesto_dualsense4unix.interface.mesa_viva import NOME_DA_MASCARA

    assert aba.mascaras_montaveis() == {
        NOME_DA_MASCARA[f] for f in mascaras_validas() if f in NOME_DA_MASCARA}
    assert "Nintendo Pro" in aba.mascaras_montaveis(), (
        "o Nintendo Pro saiu do catálogo do vpad, ou a tela perdeu o rótulo "
        "dele — nos dois casos o chip volta a nascer cinza")


def test_o_chip_sem_motor_nasce_cinza_com_a_razao_nos_quatro_lugares() -> None:
    """D-03 dela: *"cinza antes, com a razão na dica."*"""
    corpo = onde.pagina("01-jogar.html").read_text(encoding="utf-8")
    sem_motor = [m for m in monta.MASCARAS if m not in aba.mascaras_montaveis()]
    assert corpo.count('class="chip inerte"') == len(sem_motor) * len(monta.MESA)
    for pedaco in corpo.split('class="chip inerte"')[1:]:
        assert pedaco.lstrip().startswith('title="'), (
            "um chip cinza saiu sem a razão na dica — troca 'clico e não "
            "acontece nada' por 'não deixa clicar e não diz por quê'")


def test_o_chip_cinza_continua_clicavel_e_recusa_dizendo() -> None:
    """Tirar o `data-gesto` faria o clique sumir CALADO."""
    corpo = onde.pagina("01-jogar.html").read_text(encoding="utf-8")
    assert corpo.count('data-gesto="mascara"') == len(monta.MASCARAS) * len(monta.MESA)

    class _Ponte:
        def __init__(self) -> None:
            self.chamadas: list[tuple[str, Any]] = []

        def chamar_detalhado(self, metodo: str, **k: Any) -> tuple[bool, str | None]:
            self.chamadas.append((metodo, k))
            return True, None

    p = _Ponte()
    aba.mascara_do_controle(
        _ctx(VIVO_GAMEPAD),
        {"uniq": "aa:bb:cc:00:00:01", "mascara": "Nintendo Pro"}, p)
    assert p.chamadas, "o chip com motor não chamou o daemon"

    q = _Ponte()
    with pytest.raises(RuntimeError) as erro:
        aba.mascara_do_controle(
            _ctx(VIVO_GAMEPAD),
            {"uniq": "aa:bb:cc:00:00:01", "mascara": "Wiimote"}, q)
    assert "Wiimote" in str(erro.value)
    assert "DualSense" in str(erro.value), (
        "a recusa não diz quais máscaras existem")
    assert q.chamadas == [], "a recusa gravou alguma coisa no daemon"


def test_a_mascara_que_o_produto_monta_e_gravada_em_qualquer_modo() -> None:
    """O outro lado da queixa 1: em Modo Nativo o clique GRAVA."""
    class _Ponte:
        def __init__(self) -> None:
            self.chamadas: list[tuple[str, Any]] = []

        def chamar_detalhado(self, metodo: str, **k: Any) -> tuple[bool, str | None]:
            self.chamadas.append((metodo, k))
            return True, None

    for estado in (VIVO_NATIVO, VIVO_NAVEGACAO, VIVO_GAMEPAD):
        p = _Ponte()
        aba.mascara_do_controle(
            _ctx(estado), {"uniq": "aa:bb:cc:00:00:01", "mascara": "Xbox 360"}, p)
        assert p.chamadas == [
            ("gamepad.mask.set",
             {"uniq": "aa:bb:cc:00:00:01", "flavor": "xbox"})], (
            f"a máscara não foi gravada neste modo: {p.chamadas!r}")


def test_a_mascara_nao_consta_mais_como_botao_sem_dono() -> None:
    """Ela tinha dono desde 03/09, e o arquivo listava os dois ao mesmo tempo."""
    assert "mascara" not in aba.BOTOES_SEM_DONO, (
        "o `mascara` voltou aos BOTOES_SEM_DONO — e ele tem dono: "
        "`gamepad.mask.set` recebe `uniq` desde 03/09/2026")
    from hefesto_dualsense4unix.interface import pacotes

    mentem = sorted(
        nome for nome in aba.BOTOES_SEM_DONO
        if ("01-jogar.html", nome) in pacotes.GESTOS
    )
    assert not mentem, (
        f"botão(ões) listado(s) em BOTOES_SEM_DONO com `@gesto` registrado: "
        f"{mentem}. A lista manda a próxima pessoa construir o que já está "
        f"construído — foi o que o `mascara` fez em 03/09 e o `modo-steam` "
        f"em 20/09")
