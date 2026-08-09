"""PERFIL-SALVA-TUDO-01/E3 — o cadeado estrutural: REGISTRAR não é APLICAR.

Por AST e não por import: estes portões leem a árvore de sintaxe das duas abas,
então rodam na CI headless (sem PyGObject, sem typelib) — que é exatamente onde
os testes de comportamento das abas SKIPAM. O defeito que eles trancam é caro e
silencioso, e não pode ficar protegido só na máquina da mantenedora
(PORTÃO-VIVO-01).

O contrato, escrito na docstring de ``draft_config.to_ipc_dict`` e no HARM-05:
as abas Emulação/Início aplicam modo e supressão AO VIVO por caminhos próprios
(``mode_transition.apply_mode``, ``daemon.emulation.suppress``); o rascunho só
GUARDA o que ficou, para o "Salvar Perfil" persistir. Se um escritor de rascunho
passar a aplicar, um toque num gatilho — que também escreve no rascunho — passa a
poder recriar o vpad ou suspender a emulação no meio da partida.

Dois portões de fiação vêm junto, pela mesma razão de custo:

1. cada gesto continua CHAMANDO o escritor (apagar a chamada devolve a queixa
   dela, "salvei o perfil e as configs das outras abas não ficam salvas");
2. o rascunho continua tendo UM escritor de modo por assunto, e ele é função de
   módulo — não método de mixin. Os dois mixins entram na mesma classe
   (``HefestoApp``), onde nomes iguais se sombreariam pela MRO em silêncio, e
   chamada entre mixins quebra dublê PARCIAL de teste (o ``_HomeStub`` de
   ``test_auto01_um_clique_em_vez_de_dez`` copia handlers avulsos): as duas
   armadilhas que a onda 2 já pagou.
"""
from __future__ import annotations

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ACOES = RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "actions"
EMULACAO_PY = ACOES / "emulation_actions.py"
INICIO_PY = ACOES / "home_actions.py"
#: AGORA-E-DEPOIS-01 (08/08/2026): o gesto que registra o modo mudou de aba.
#: Ele saiu dos cliques da Início (que deixaram de aplicar) e foi para o
#: "Aplicar" do rodapé, que é onde a mudança sai — e onde o daemon confirma.
RODAPE_PY = ACOES / "footer_actions.py"

#: Tudo que MUDA a máquina dela: IPC, transição de modo, worker, timer da GUI.
#: Um escritor de rascunho não pode mencionar nenhum destes nomes.
NOMES_QUE_APLICAM = frozenset(
    {
        "call_async",
        "apply_mode",
        "plan_mode_transition",
        "run_in_thread",
        "_get_executor",
        "idle_add",
        "timeout_add",
        "run",
        "Popen",
        "autoswitch_lock_set",
    }
)

#: As funções e métodos que ESCREVEM no rascunho nesta entrega.
ESCRITORES = {
    INICIO_PY: (
        "_coop_do_rascunho",
        "rascunho_com_modo",
        "registrar_modo_no_rascunho",
    ),
    EMULACAO_PY: (
        "perfil_do_rascunho_tem_opiniao",
        "rascunho_com_modo_jogo",
        "registrar_modo_jogo_no_rascunho",
    ),
}


def _arvore(caminho: Path) -> ast.Module:
    return ast.parse(caminho.read_text(encoding="utf-8"))


def _funcao(caminho: Path, nome: str) -> ast.FunctionDef:
    for no in ast.walk(_arvore(caminho)):
        if isinstance(no, ast.FunctionDef) and no.name == nome:
            return no
    raise AssertionError(f"{nome!r} não existe em {caminho.name}")


def _nomes_chamados(no: ast.AST) -> set[str]:
    """Nomes de tudo que é CHAMADO dentro de ``no`` (inclui ``a.b()`` como "b")."""
    chamados: set[str] = set()
    for interno in ast.walk(no):
        if not isinstance(interno, ast.Call):
            continue
        alvo = interno.func
        if isinstance(alvo, ast.Name):
            chamados.add(alvo.id)
        elif isinstance(alvo, ast.Attribute):
            chamados.add(alvo.attr)
    return chamados


def test_nenhum_escritor_de_rascunho_aplica_nada() -> None:
    """HARM-05: o escritor anota; quem aplica é o gesto dela, em outro lugar."""
    for caminho, nomes in ESCRITORES.items():
        for nome in nomes:
            chamados = _nomes_chamados(_funcao(caminho, nome))
            proibidos = chamados & NOMES_QUE_APLICAM
            assert not proibidos, (
                f"{caminho.name}:{nome} chama {sorted(proibidos)} — registrar no "
                "rascunho NÃO pode virar um Aplicar ao vivo (HARM-05)"
            )


def test_o_modo_jogo_so_e_gravado_pelo_lugar_que_tem_o_gate_do_catch_all() -> None:
    """``with_suppress`` tem UM chamador na janela, e ele é o que recusa.

    O gate mora em ``rascunho_com_modo_jogo`` porque
    ``lifecycle.apply_profile_suppression`` liga a supressão SEM passar pelo
    ``_perfil_tem_opiniao`` (só o ramo de LIBERAR passa). Um segundo chamador
    plantaria ``suppress: true`` num catch-all dela por outra porta — e ali é
    alçapão de mão única.
    """
    for caminho in (EMULACAO_PY, INICIO_PY):
        for no in ast.walk(_arvore(caminho)):
            if not isinstance(no, ast.FunctionDef):
                continue
            if "with_suppress" not in _nomes_chamados(no):
                continue
            assert no.name == "rascunho_com_modo_jogo", (
                f"{caminho.name}:{no.name} chama with_suppress direto, sem o gate "
                "do catch-all (R-02)"
            )


def test_cada_gesto_continua_chamando_o_escritor() -> None:
    """A fiação: apagar a chamada devolve a queixa dela inteira."""
    esperado = {
        (EMULACAO_PY, "_apply_mode"): "registrar_modo_no_rascunho",
        (EMULACAO_PY, "_set_suppress"): "registrar_modo_jogo_no_rascunho",
        # AGORA-E-DEPOIS-01: o gesto da aba Início é o "Aplicar" do rodapé.
        # Os cliques nos seletores só MARCAM a escolha (nenhum IPC, nenhum
        # rascunho); quem registra é o callback de sucesso da transição, para o
        # rascunho continuar descrevendo o que ficou DE PÉ.
        (RODAPE_PY, "_aplicar_escolha_pendente"): "registrar_modo_no_rascunho",
    }
    for (caminho, gesto), escritor in esperado.items():
        chamados = _nomes_chamados(_funcao(caminho, gesto))
        assert escritor in chamados, (
            f"{caminho.name}:{gesto} não chama {escritor} — o gesto dela volta a "
            "morrer com a sessão (PERFIL-SALVA-TUDO-01)"
        )


def test_o_rascunho_tem_um_escritor_so_de_modo_em_cada_aba() -> None:
    """Quem escreve ``janela.draft`` nestas duas abas são as DUAS funções, e só.

    Um segundo escritor é a classe de bug desta casa: *"três escritores do perfil
    sem dono"* (auditoria 23/07). Aqui ele seria pior — um escritor que não passe
    por ``rascunho_com_modo_jogo`` planta ``suppress: true`` num catch-all dela
    sem o gate do R-02, e ali é alçapão de mão única.

    O portão também tranca o desenho: nada de método-ponte por aba. Os dois
    mixins entram na MESMA classe (``HefestoApp``) e nomes iguais se sombreariam
    pela MRO em silêncio; e chamada entre mixins quebra dublê PARCIAL de teste,
    preço que a onda 2 já pagou.
    """
    donos = {"registrar_modo_no_rascunho", "registrar_modo_jogo_no_rascunho"}
    for caminho in (EMULACAO_PY, INICIO_PY):
        for no in ast.walk(_arvore(caminho)):
            if not isinstance(no, ast.FunctionDef):
                continue
            escreve = any(
                isinstance(alvo, ast.Attribute) and alvo.attr == "draft"
                for atrib in ast.walk(no)
                if isinstance(atrib, ast.Assign)
                for alvo in atrib.targets
            )
            if not escreve:
                continue
            assert no.name in donos, (
                f"{caminho.name}:{no.name} escreve no rascunho por fora dos donos "
                f"{sorted(donos)} — segundo escritor sem dono (auditoria 23/07)"
            )
