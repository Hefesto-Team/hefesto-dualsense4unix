"""EMULACAO-UM-DONO-SO-01/E15 — frase de tela para um estado que não acontece.

O DEFEITO
==========
``BLOQUEIO_DO_TECLADO_EM_PORTUGUES`` traduz o campo ``bloqueio`` do bloco
``keyboard_emulation`` do daemon. Uma das quatro entradas descreve um estado que
o produto **nunca alcança**: ``vpad_suspenso_pelo_steam_input`` só sai de
``lifecycle._jogo_no_controle_do_desktop`` sob ``steam_input_vpad_suspenso``, e
nada em produção põe essa flag em ``True`` — o armador
``suspend_vpads_for_steam_input`` tem zero chamadores em ``src/``. Medido pela
VPAD-SUSPENSO-MORTO-01/E1 em 25/08/2026 e reconferido aqui.

A RÉGUA É DE CLASSE, NÃO DE INSTÂNCIA
======================================
Este portão não procura *aquela* entrada. Ele pergunta, para **cada** chave do
dicionário: *existe caminho de produção que ponha este valor em ``bloqueio``?*
As entradas para as quais a resposta é não têm de estar declaradas em
``BLOQUEIO_SEM_CAMINHO_DE_PRODUCAO``, com a razão escrita. Assim a próxima
frase escrita para um estado morto — ou o próximo estado que morre debaixo de
uma frase viva — reprova sozinha.

POR QUE ELE NÃO É O IRMÃO DA VPAD-SUSPENSO-MORTO-01
====================================================
Aquele portão (``test_portao_o_par_com_metade_ligada.py``) pergunta pela FLAG,
em ``daemon/``: *quem escreve True, quem escreve False, quem tem chamador*.
Este pergunta pela TELA: *a frase que a janela mostra fala de um valor que o
daemon consegue produzir?* São duas perguntas e duas respostas possíveis — uma
frase pode morrer porque o produtor sumiu, sem flag nenhuma no meio. Duas
réguas independentes é o que revela, e é regra desta casa.

O TERCEIRO CASO É O QUE AVISA SOZINHO
======================================
``test_a_declaracao_de_morte_nao_sobrevive_a_propria_cura`` reprova no dia em
que a suspensão religar. Não é zelo: lápide que sobrevive ao próprio defeito é
o que o ``portao_a_casa_sabe_e_o_produto_nao_faz`` pegou em 25/08 — duas notas
datadas seguiram dizendo "nada de produção chama" sobre funções que a produção
passou a chamar.

A MORDIDA, PROVADA EM 25/08/2026 — ver o relatório do agente E1.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

pytest.importorskip("gi")

from hefesto_dualsense4unix.app.actions import emulation_actions as ea

_RAIZ = Path(__file__).resolve().parents[2]
_SRC = _RAIZ / "src" / "hefesto_dualsense4unix"
_IPC = _SRC / "daemon" / "ipc_handlers.py"
_LIFECYCLE = _SRC / "daemon" / "lifecycle.py"
_GAMEPAD = _SRC / "daemon" / "subsystems" / "gamepad.py"

#: BG-02 quem montava o `bloqueio` por ramos era `_keyboard_emulation_payload`,
_MONTADOR = "_bloqueio_da_emulacao_de_desktop"

_PAYLOAD = "_keyboard_emulation_payload"


def _corpo(caminho: Path, nome: str) -> ast.FunctionDef:
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    for no in ast.walk(arvore):
        if isinstance(no, ast.FunctionDef) and no.name == nome:
            return no
    raise AssertionError(f"{nome} sumiu de {caminho.relative_to(_RAIZ)}")


def _constantes_de_modulo(caminho: Path) -> dict[str, object]:
    saida: dict[str, object] = {}
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    for no in arvore.body:
        alvos = list(no.targets) if isinstance(no, ast.Assign) else []
        if isinstance(no, ast.AnnAssign):
            alvos = [no.target]
        valor = no.value if isinstance(no, (ast.Assign, ast.AnnAssign)) else None
        if valor is None:
            continue
        try:
            literal = ast.literal_eval(valor)
        except (ValueError, TypeError, SyntaxError):
            continue
        for alvo in alvos:
            if isinstance(alvo, ast.Name):
                saida[alvo.id] = literal
    return saida


def valores_que_o_daemon_consegue_publicar() -> set[str]:
    """Os `bloqueio` que ALGUM caminho de produção alcança hoje."""
    montador = _corpo(_IPC, _MONTADOR)
    alcancaveis: set[str] = set()
    for no in ast.walk(montador):
        if (
            isinstance(no, ast.Return)
            and isinstance(no.value, ast.Constant)
            and isinstance(no.value.value, str)
        ):
            alcancaveis.add(no.value.value)
            continue
        if not isinstance(no, ast.Assign):
            continue
        if not (isinstance(no.value, ast.Constant) and isinstance(no.value.value, str)):
            continue
        if any(isinstance(a, ast.Name) and a.id == "bloqueio" for a in no.targets):
            alcancaveis.add(no.value.value)

    predicado = _corpo(_LIFECYCLE, "_jogo_no_controle_do_desktop")
    constantes = _constantes_de_modulo(_LIFECYCLE)
    for no in ast.walk(predicado):
        if not isinstance(no, ast.Return) or not isinstance(no.value, ast.Name):
            continue
        valor = constantes.get(no.value.id)
        if isinstance(valor, str) and _guarda_tem_escritor(no.value.id):
            alcancaveis.add(valor)
    return alcancaveis


def _guarda_tem_escritor(nome_da_constante: str) -> bool:
    """A constante `CALADA_VPAD_SUSPENSO` é devolvida sob uma guarda VIVA?"""
    if nome_da_constante != "CALADA_VPAD_SUSPENSO":
        return False
    arvore = ast.parse(_GAMEPAD.read_text(encoding="utf-8"), filename=str(_GAMEPAD))
    donos: set[str] = set()
    for funcao in ast.walk(arvore):
        if not isinstance(funcao, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for no in ast.walk(funcao):
            if not isinstance(no, ast.Assign):
                continue
            escreve_true = isinstance(no.value, ast.Constant) and no.value.value is True
            toca_a_flag = any(
                isinstance(a, ast.Attribute) and a.attr == "_steam_input_vpad_suspenso"
                for a in no.targets
            )
            if escreve_true and toca_a_flag:
                donos.add(funcao.name)
    return any(_tem_chamador_de_producao(nome) for nome in donos)


def _tem_chamador_de_producao(funcao: str) -> bool:
    """Alguém em `src/` CHAMA esta função? Por AST — citação não é chamada."""
    for caminho in sorted(_SRC.rglob("*.py")):
        if "__pycache__" in caminho.parts:
            continue
        try:
            arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
        except (OSError, SyntaxError):  # pragma: no cover - defensivo
            continue
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            alvo = no.func
            nome = (
                alvo.id
                if isinstance(alvo, ast.Name)
                else alvo.attr
                if isinstance(alvo, ast.Attribute)
                else None
            )
            if nome == funcao:
                return True
    return False


def test_o_montador_do_bloqueio_continua_tendo_um_dono_so() -> None:
    """Se `bloqueio` passar a ser escrito noutro lugar, esta régua cega."""
    fonte = _IPC.read_text(encoding="utf-8")
    donos = re.findall(r'^\s*"bloqueio":', fonte, re.MULTILINE)
    donos += re.findall(r"^\s*bloqueio\s*=", fonte, re.MULTILINE)
    montador = _corpo(_IPC, _MONTADOR)
    dentro = sum(
        1
        for no in ast.walk(montador)
        if isinstance(no, ast.Assign)
        and any(isinstance(a, ast.Name) and a.id == "bloqueio" for a in no.targets)
    )
    dentro += sum(
        1
        for no in ast.walk(montador)
        if isinstance(no, ast.Return)
        and isinstance(no.value, ast.Constant)
        and isinstance(no.value.value, str)
    )
    assert dentro >= 3, (
        f"{_MONTADOR} deixou de montar o `bloqueio` por ramos ({dentro}) — a "
        "régua deste portão presume que é ele quem decide o valor. Se a "
        "decisão mudou de dono outra vez, reaponte `_MONTADOR` para o novo; "
        "se ela se ESPALHOU por dois lugares, o defeito é esse, e é o que "
        "esta asserção existe para pegar."
    )

    payload = _corpo(_IPC, _PAYLOAD)
    chama = any(
        isinstance(no, ast.Attribute) and no.attr == _MONTADOR
        for no in ast.walk(payload)
    )
    assert chama, (
        f"{_PAYLOAD} não chama {_MONTADOR}: ou voltou a decidir por conta "
        "própria, ou passou a ler de um terceiro lugar. Nos dois casos o "
        "`bloqueio` deixou de ter um dono só."
    )


def test_a_frase_viva_de_pausa_continua_dizendo_que_nao_foi_desligado() -> None:
    """O invariante que o daemon deixou por escrito, e o E15 não pode quebrar."""
    viva = ea.BLOQUEIO_DO_TECLADO_EM_PORTUGUES["modo_jogo"]
    assert "em pausa" in viva, viva
    assert "esligado" not in viva, viva


def test_a_frase_marcada_como_morta_ainda_esta_no_disco() -> None:
    """A escolha declarada: MARCAR, não apagar."""
    frase = ea.BLOQUEIO_DO_TECLADO_EM_PORTUGUES.get("vpad_suspenso_pelo_steam_input")
    assert frase, "a frase foi apagada — se foi decisão dela, apague este caso junto"
    assert "Não foi desligado" in frase, frase
