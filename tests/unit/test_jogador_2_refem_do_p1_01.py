"""JOGADOR-2-REFEM-01 — o P2 perdia o input quando o controle do P1 saía da mesa.

O DEFEITO, medido lendo o laço do daemon
========================================
`coop.sync()` e `coop.forward_all()` moravam **depois** do gate de conexão::

    if not self.controller.is_connected():
        ...
        continue          # <- levava o co-op junto
    ...
    if grace_passed:
        coop.forward_all()

Cada jogador secundário tem o **seu** controle físico e o **seu** gamepad
virtual, e nenhum dos dois depende do primário. Mas o `continue` levava tudo: com
o DualSense do P1 fora da mesa — bateria, cabo solto, um blip de Bluetooth — o
jogador 2 ficava sem input no meio da partida, e nada no journal explicava.

Estava registrado como aberto e SEM DONO em
`docs/process/sprints/2026-08-10-ESTADO-DA-NOITE-01*.md`.

A CURA
======
O co-op sobe para antes do gate — o **sexto** bloco a fazer essa viagem, ao lado
do reconcile de identidade, do LED dos externos, do sinal de jogo, do diário da
bateria e do dreno de modo pendente. O código já dizia a razão, para os externos:
*"o 8BitDo/Pro Controller merece número mesmo sem nenhum DualSense plugado"*.
Vale ainda mais aqui: número é cosmética, input é o produto.

O `grace_passed` sobe junto e continua sendo o gate. Ele é o anti-ghost-input da
conexão e é um relógio (`_input_ready_at`), não um estado de link: desconectar
não o rearma, então o P2 não paga o settling de um controle que nem está lá.
"""

from __future__ import annotations

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
LIFECYCLE = RAIZ / "src" / "hefesto_dualsense4unix" / "daemon" / "lifecycle.py"


def _poll_loop() -> ast.AsyncFunctionDef:
    arvore = ast.parse(LIFECYCLE.read_text(encoding="utf-8"), filename=str(LIFECYCLE))
    for no in ast.walk(arvore):
        if isinstance(no, ast.AsyncFunctionDef) and no.name == "_poll_loop":
            return no
    raise AssertionError("não achei o _poll_loop")


def _linha_do_gate_de_conexao() -> int:
    """A linha do `if not self.controller.is_connected():` que dá `continue`."""
    for no in ast.walk(_poll_loop()):
        if not isinstance(no, ast.If) or not isinstance(no.test, ast.UnaryOp):
            continue
        if not isinstance(no.test.op, ast.Not):
            continue
        fonte = ast.dump(no.test)
        if "is_connected" not in fonte:
            continue
        if any(isinstance(f, ast.Continue) for f in ast.walk(no)):
            return no.lineno
    raise AssertionError("não achei o gate de conexão com `continue`")


def _linhas_de_chamada(nome: str) -> list[int]:
    achadas = []
    for no in ast.walk(_poll_loop()):
        if (
            isinstance(no, ast.Call)
            and isinstance(no.func, ast.Attribute)
            and no.func.attr == nome
        ):
            achadas.append(no.lineno)
    return achadas


def test_o_forward_do_coop_roda_antes_do_gate_de_conexao() -> None:
    """A cura, e é uma questão de ORDEM no arquivo.

    Morde ao devolver o bloco do co-op para depois do gate: é o estado do
    produto até 10/08/2026, e o efeito é o jogador 2 mudo no meio da partida
    sempre que o controle do P1 sai da mesa.
    """
    gate = _linha_do_gate_de_conexao()
    forwards = _linhas_de_chamada("forward_all")
    assert forwards, "o laço não repassa mais input aos secundários?"
    assert min(forwards) < gate, (
        "o `forward_all` do co-op está depois do gate de conexão — com o "
        "controle do P1 fora da mesa, o jogador 2 fica sem input"
    )


def test_o_sync_do_coop_tambem_roda_antes_do_gate() -> None:
    """Repassar sem reconciliar não basta.

    O `sync` é quem CRIA o gamepad virtual de cada secundário. Deixá-lo para
    depois do gate curaria só metade: um P2 que já estivesse de pé continuaria
    andando, e um que entrasse na mesa com o P1 desconectado nunca nasceria.
    """
    gate = _linha_do_gate_de_conexao()
    syncs = [
        n.lineno
        for n in ast.walk(_poll_loop())
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "sync"
    ]
    assert syncs, "o laço não reconcilia mais os secundários?"
    assert min(syncs) < gate


def test_o_primario_continua_sendo_lido_depois_do_gate() -> None:
    """O contraponto: a cura não pode virar leitura de controle desconectado.

    Se o `read_state` do primário subisse junto, o daemon passaria a ler um
    aparelho que não está lá a cada tique — o gate existe por isso
    (BUG-DAEMON-NO-DEVICE-FATAL-01).
    """
    gate = _linha_do_gate_de_conexao()
    leituras = [
        n.lineno
        for n in ast.walk(_poll_loop())
        if isinstance(n, ast.Attribute) and n.attr == "read_state"
    ]
    assert leituras, "o laço não lê mais o primário?"
    assert min(leituras) > gate, (
        "o `read_state` do primário subiu para antes do gate — o daemon passa "
        "a ler um controle que não está conectado"
    )


def test_o_grace_e_recalculado_depois_da_borda_de_reconexao() -> None:
    """As DUAS atribuições de `grace_passed` são necessárias, e por quê.

    A de cima (pré-gate) serve o co-op. A de baixo serve o primário — e entre as
    duas está a borda desconectado→conectado, que ARMA um grace novo. Apagar a
    de baixo por parecer duplicada faria o primário despachar sem o settling
    anti-ghost, que é o defeito que o BUG-DAEMON-CONNECT-GHOST-INPUT-01 curou.

    Morde ao apagar qualquer uma das duas.
    """
    fonte = LIFECYCLE.read_text(encoding="utf-8").splitlines()
    graces = [
        i + 1
        for i, linha in enumerate(fonte)
        if linha.strip() == "grace_passed = tick_started >= self._input_ready_at"
    ]
    arma = [
        i + 1
        for i, linha in enumerate(fonte)
        if "self._input_ready_at = tick_started + INPUT_GRACE_SEC" in linha
    ]
    assert len(graces) == 2, f"esperava duas atribuições de grace, achei {len(graces)}"
    assert arma, "ninguém arma mais o grace na borda de reconexão?"
    assert graces[0] < arma[0] < graces[1], (
        "a borda que arma o grace tem de ficar ENTRE as duas atribuições — "
        "senão uma delas é mesmo redundante e a outra lê o valor errado"
    )
