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

#: A função do daemon que MONTA o campo. É ela, e só ela: quem publicar
#: `bloqueio` de outro lugar cria um segundo dono do contrato, e este portão
#: passa a olhar para o lugar errado — por isso o primeiro caso confere que ela
#: continua sendo a única.
#: Quem DECIDE o valor de `bloqueio` hoje.
#:
#: REAPONTADO em 25/08/2026, e a régua estava certa em reclamar. Até a frente
#: BG-02 quem montava o `bloqueio` por ramos era `_keyboard_emulation_payload`,
#: e esta régua lia os ramos DELE. A BG-02 extraiu a decisão para um DONO ÚNICO
#: — `_bloqueio_da_emulacao_de_desktop` —, porque o mouse precisava da MESMA
#: conjunção e duas cópias divergiriam na primeira edição.
#:
#: A régua não cegou em silêncio: `test_o_montador_do_bloqueio_continua_tendo_um_dono_so`
#: reprovou dizendo "deixou de montar o `bloqueio` por ramos (1)", e o outro
#: caso reprovou com "a régua não achou NENHUM valor produzível — ela cegou".
#: **É assim que um portão deve morrer** — avisando, não passando verde.
_MONTADOR = "_bloqueio_da_emulacao_de_desktop"

#: O montador do payload, que agora CHAMA o dono acima em vez de decidir.
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
    """Os `bloqueio` que ALGUM caminho de produção alcança hoje.

    Duas fontes, e é isso que a função tem de fazer certo:

    1. os literais que o montador atribui direto a `bloqueio`;
    2. o que os PRODUTORES do `motivo_jogo` conseguem devolver — hoje só
       `lifecycle._jogo_no_controle_do_desktop`, e ele devolve `CALADA_*` sob
       guarda. Um `return CALADA_X` cuja guarda é uma função sem escritor de
       `True` não conta: é o defeito desta sprint. Por isso a constante só entra
       quando a guarda tem escritor vivo (`_guarda_tem_escritor`).
    """
    montador = _corpo(_IPC, _MONTADOR)
    alcancaveis: set[str] = set()
    for no in ast.walk(montador):
        # O dono único devolve o literal em vez de atribuí-lo (ver a nota do
        # contador de ramos acima). Sem este ramo a régua não acha valor
        # nenhum e reprova dizendo que cegou — o que ela fez, e bem.
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
    """A constante `CALADA_VPAD_SUSPENSO` é devolvida sob uma guarda VIVA?

    Régua estreita e declarada: hoje há UMA constante devolvida sob guarda, e a
    guarda é `steam_input_vpad_suspenso`, que lê `_steam_input_vpad_suspenso`.
    Se um dia houver uma segunda constante sob outra guarda, esta função devolve
    `False` para ela e a entrada terá de ser declarada — falso positivo
    barulhento, que é o lado certo de errar: portão que perde em silêncio é pior
    que portão nenhum.

    O DEFEITO QUE ESTA FUNÇÃO JÁ TEVE, e é a armadilha inteira desta sprint:
    a primeira versão procurava a ATRIBUIÇÃO `= True` e parava aí. Ela existe —
    dentro de `suspend_vpads_for_steam_input`, que **não tem chamador de
    produção**. O instrumento respondia "viva" para a flag exatamente onde a
    medição diz "morta", e teria dado verde na pergunta errada. Escritor só
    conta se a função que o contém for CHAMADA.
    """
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
    """Alguém em `src/` CHAMA esta função? Por AST — citação não é chamada.

    Procurar o nome com `grep` contaria comentário e docstring, que é como a
    `suspend_vpads_for_steam_input` parecia viva: seis das sete ocorrências dela
    em `src/` são prosa.
    """
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


# ---------------------------------------------------------------------------
def test_o_montador_do_bloqueio_continua_tendo_um_dono_so() -> None:
    """Se `bloqueio` passar a ser escrito noutro lugar, esta régua cega."""
    fonte = _IPC.read_text(encoding="utf-8")
    donos = re.findall(r'^\s*"bloqueio":', fonte, re.MULTILINE)
    donos += re.findall(r"^\s*bloqueio\s*=", fonte, re.MULTILINE)
    montador = _corpo(_IPC, _MONTADOR)
    # DUAS FORMAS, e a régua conta as duas de propósito. O montador antigo
    # atribuía (`bloqueio = "modo_jogo"`); o dono único de 25/08 é uma função
    # de decisão e RETORNA (`return "modo_jogo"`). Contar só uma faria a régua
    # cegar na próxima vez que alguém trocasse o estilo — que é exatamente o
    # que acabou de acontecer.
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

    # E o payload tem de CHAMAR o dono, senão haveria dois caminhos vivos: o
    # dono único decidindo para ninguém, e o payload decidindo por conta.
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


def test_toda_frase_do_teclado_fala_de_um_estado_que_o_daemon_produz() -> None:
    """A régua de classe.

    ARRANQUE A CURA: apague a entrada de `BLOQUEIO_SEM_CAMINHO_DE_PRODUCAO` e
    este caso REPROVA nomeando a frase morta — é o defeito de hoje, medido pelo
    instrumento, sem plantio nenhum.
    """
    alcancaveis = valores_que_o_daemon_consegue_publicar()
    assert alcancaveis, "a régua não achou NENHUM valor produzível — ela cegou"

    mortas = [
        chave
        for chave in ea.BLOQUEIO_DO_TECLADO_EM_PORTUGUES
        if chave not in alcancaveis
        and chave not in ea.BLOQUEIO_SEM_CAMINHO_DE_PRODUCAO
    ]
    assert not mortas, (
        "frase de tela para um estado que nenhum caminho de produção alcança, "
        "e sem declaração em BLOQUEIO_SEM_CAMINHO_DE_PRODUCAO:\n"
        + "\n".join(f"  {c!r}" for c in mortas)
        + f"\n(alcançáveis hoje: {sorted(alcancaveis)})"
    )


def test_a_declaracao_de_morte_nao_sobrevive_a_propria_cura() -> None:
    """A metade que avisa sozinha se alguma frente RELIGAR a suspensão.

    ARRANQUE A CURA: devolva um escritor de `True` à flag em
    `daemon/subsystems/gamepad.py` e este caso REPROVA — a declaração virou
    lápide de um defeito que acabou, e a frase precisa ser revisitada.
    """
    alcancaveis = valores_que_o_daemon_consegue_publicar()
    ressuscitadas = [
        chave for chave in ea.BLOQUEIO_SEM_CAMINHO_DE_PRODUCAO if chave in alcancaveis
    ]
    assert not ressuscitadas, (
        "declaração obsoleta em BLOQUEIO_SEM_CAMINHO_DE_PRODUCAO: "
        f"{ressuscitadas}. O estado voltou a ser alcançável — APAGUE a entrada, "
        "e confira se a frase da tela ainda descreve o que acontece hoje "
        "(EMULACAO-UM-DONO-SO-01/E15)."
    )


def test_toda_declaracao_de_morte_aponta_o_dono_da_decisao() -> None:
    """Declaração sem razão escrita é paisagem — vira "sempre foi assim"."""
    for chave, razao in ea.BLOQUEIO_SEM_CAMINHO_DE_PRODUCAO.items():
        assert chave in ea.BLOQUEIO_DO_TECLADO_EM_PORTUGUES, (
            f"{chave!r} está declarada morta e não é frase de tela nenhuma"
        )
        assert "MEDIDO em" in razao, f"{chave}: razão sem data de medição"
        assert re.search(r"\d{2}/\d{2}/\d{4}", razao), f"{chave}: sem data"


def test_a_frase_viva_de_pausa_continua_dizendo_que_nao_foi_desligado() -> None:
    """O invariante que o daemon deixou por escrito, e o E15 não pode quebrar.

    Nos casos de PAUSA o `enabled` continua TRUE — o teclado dela não foi
    desligado. Marcar uma frase como morta não pode virar a porta para mexer no
    texto das que estão vivas.
    """
    viva = ea.BLOQUEIO_DO_TECLADO_EM_PORTUGUES["modo_jogo"]
    assert "em pausa" in viva, viva
    assert "esligado" not in viva, viva


def test_a_frase_marcada_como_morta_ainda_esta_no_disco() -> None:
    """A escolha declarada: MARCAR, não apagar.

    Apagar a frase decidiria por ela uma pergunta que a VPAD-SUSPENSO-MORTO-01
    deixou aberta e que é da mantenedora. Este caso registra a escolha em
    código, para que apagá-la seja um gesto deliberado e não um efeito colateral
    de outra leva.
    """
    frase = ea.BLOQUEIO_DO_TECLADO_EM_PORTUGUES.get("vpad_suspenso_pelo_steam_input")
    assert frase, "a frase foi apagada — se foi decisão dela, apague este caso junto"
    assert "Não foi desligado" in frase, frase
