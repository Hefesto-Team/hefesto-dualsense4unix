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
#: SOM-02/E4 (09/08/2026): o alto-falante entrou no mesmo contrato. O gesto
#: mora no CARD (é widget, não mixin) e o escritor mora no ``draft_config``,
#: escritor único — a fiação que faltava desde 29/07, quando ``with_speaker``
#: nasceu com teste e sem um único chamador no produto.
CARD_PY = (
    RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "widgets" / "controller_card.py"
)
RASCUNHO_PY = RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "draft_config.py"
#: A aba que MONTA os cards, e por isso a única que pode dizer a cada um quem é
#: o dono do rascunho. Sem essa injeção o escritor do alto-falante fica com
#: chamador de mentira: ele roda, e não tem em que escrever.
STATUS_PY = ACOES / "status_actions.py"

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
        # A-INICIO-TAMBEM-SALVA-01 (10/08/2026): o recolhimento que o "Salvar
        # Perfil" faz da escolha pendente da Início. Ele entra AQUI e não na
        # lista de gestos porque é escritor, e é o escritor cuja tentação de
        # aplicar é maior de todas — está a uma linha do botão que grava.
        #
        # NOTA DATADA — 11/08/2026 (O-SALVAR-TAMBEM-APLICA-01): a pergunta que
        # esta linha registrava como EM ABERTO — *"o Salvar não deveria aplicar
        # também?"* — foi respondida por ela: *"salvar também aplica"*. O texto
        # antigo previa o que aconteceria nesse dia (*"quem mudar isto vai bater
        # neste portão e ter de mover o gesto de lugar, em vez de plantar um
        # `apply_mode` dentro de um escritor de rascunho"*) e é exatamente o que
        # aconteceu: o `apply_mode` do Salvar mora no RODAPÉ
        # (`footer_actions._aplicar_o_modo_que_foi_gravado`, pela mesma
        # `_transicao_de_modo` do botão verde), e esta função continua pura.
        #
        # O portão FICA, e agora com dois donos em vez de um: ele separa o
        # ESCRITOR (que só anota no rascunho) do GESTO (que aplica). A entrada
        # nova em `test_cada_gesto_continua_chamando_o_escritor` é a outra
        # metade — ela cobra que o gesto exista.
        "recolher_escolha_pendente_no_rascunho",
    ),
    EMULACAO_PY: (
        "perfil_do_rascunho_tem_opiniao",
        "rascunho_com_modo_jogo",
        "registrar_modo_jogo_no_rascunho",
    ),
    RASCUNHO_PY: ("registrar_alto_falante_no_rascunho",),
    CARD_PY: ("_confirmado_pelo_daemon",),
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


def test_o_modo_jogo_so_e_gravado_por_um_lugar_na_janela() -> None:
    """``with_suppress`` tem UM chamador na janela: ``rascunho_com_modo_jogo``.

    NOTA DATADA — 09/08/2026 (MODO-JOGO-VONTADE-DELA-01). Este portão se chamava
    ``..._que_tem_o_gate_do_catch_all`` e existia para proteger uma RECUSA: até
    hoje ``rascunho_com_modo_jogo`` não guardava ``suppress: true`` em perfil
    catch-all, e um segundo chamador de ``with_suppress`` plantaria o valor por
    outra porta. A recusa caiu por decisão dela (*"a vontade na GUI prevalece
    sempre"*) — a premissa dela, "o daemon liga sem gate", já era falsa desde
    05/08.

    O portão FICA, com o dono trocado. Quem impede o alçapão hoje é o gate do
    daemon (``apply_profile_suppression``, ramo ``if desired:``); o que se
    protege aqui é o mesmo de sempre nesta casa — um escritor só por assunto,
    porque "três escritores do perfil sem dono" (auditoria 23/07) é a classe de
    bug desta janela — e mais uma coisa nova: é ``rascunho_com_modo_jogo`` que
    sabe quando a janela deve DIZER que o valor guardado não volta sozinho. Um
    segundo escritor grava calado.
    """
    for caminho in (EMULACAO_PY, INICIO_PY):
        for no in ast.walk(_arvore(caminho)):
            if not isinstance(no, ast.FunctionDef):
                continue
            if "with_suppress" not in _nomes_chamados(no):
                continue
            assert no.name == "rascunho_com_modo_jogo", (
                f"{caminho.name}:{no.name} chama with_suppress direto, fora do "
                "único escritor do modo jogo"
            )


def test_cada_gesto_continua_chamando_o_escritor() -> None:
    """A fiação: apagar a chamada devolve a queixa dela inteira.

    O valor é UM nome ou uma TUPLA deles — um gesto pode ter mais de um elo
    obrigatório (o "Salvar Perfil" tem dois desde 11/08/2026: levar a escolha
    ao arquivo e levar a mesma escolha à máquina).
    """
    esperado: dict[tuple[Path, str], str | tuple[str, ...]] = {
        (EMULACAO_PY, "_apply_mode"): "registrar_modo_no_rascunho",
        (EMULACAO_PY, "_set_suppress"): "registrar_modo_jogo_no_rascunho",
        # AGORA-E-DEPOIS-01: o gesto da aba Início é o "Aplicar" do rodapé.
        # Os cliques nos seletores só MARCAM a escolha (nenhum IPC, nenhum
        # rascunho); quem registra é o callback de sucesso da transição, para o
        # rascunho continuar descrevendo o que ficou DE PÉ.
        (RODAPE_PY, "_aplicar_escolha_pendente"): "registrar_modo_no_rascunho",
        # A-INICIO-TAMBEM-SALVA-01 (10/08/2026): o OUTRO botão do rodapé. Medido
        # na bancada neste dia — com um Salvar só no fim, sete das oito abas
        # chegavam ao arquivo e a Início não, porque a escolha dela mora em
        # `_escolha_pendente` e só o verde a trazia para o rascunho. Apagar esta
        # chamada devolve o `mode: null` do `pragmata2.json`.
        # O-SALVAR-TAMBEM-APLICA-01 (11/08/2026), decisão dela: *"salvar também
        # aplica"*. O Salvar passou a ter DOIS elos obrigatórios no mesmo
        # método, e eles medem coisas diferentes: recolher leva a escolha ao
        # ARQUIVO; o gesto de aplicar leva a mesma escolha à MÁQUINA. Apagar o
        # segundo devolve o defeito que ela mandou consertar — o arquivo com o
        # modo novo, o daemon no antigo, e a linha "vai mudar para:" acesa
        # apontando para um valor JÁ gravado.
        (RODAPE_PY, "_persist_profile_async"): (
            "recolher_escolha_pendente_no_rascunho",
            "_aplicar_o_modo_que_foi_gravado",
        ),
        # E o gesto passa pela transição ÚNICA, a mesma do botão verde. Este é o
        # elo que impede a recaída cara: quem "simplificar" isto para dentro do
        # `apply_draft` reencontra o `timeout_s=1.5` contra os 3 x 2,0 s do
        # `apply_mode` — o "ERRO ao aplicar" com o modo JÁ aplicado que o
        # APLICAR-VERDADE-02 existe para matar (ver `on_apply_draft`).
        (RODAPE_PY, "_aplicar_o_modo_que_foi_gravado"): "_transicao_de_modo",
        # SOM-02/E4: os TRÊS gestos do bloco "Alto-falante" que viram perfil —
        # volume, mudo e canal de saída — mais a devolução da posse, que
        # registra a AUSÊNCIA. Apagar qualquer uma destas chamadas devolve o
        # defeito medido em 09/08/2026: ela ajusta o volume, salva o perfil, e
        # o valor VELHO volta ao controle na ativação seguinte.
        (CARD_PY, "_enviar_volume_do_controle"): "_confirmado_pelo_daemon",
        (CARD_PY, "_on_speaker_mudo_clicado"): "_confirmado_pelo_daemon",
        (CARD_PY, "_on_canal_do_speaker_mudou"): "_confirmado_pelo_daemon",
        (CARD_PY, "_on_speaker_devolucao_clicada"): "_confirmado_pelo_daemon",
        (CARD_PY, "_confirmado_pelo_daemon"): "registrar_alto_falante_no_rascunho",
    }
    for (caminho, gesto), elos in esperado.items():
        chamados = _nomes_chamados(_funcao(caminho, gesto))
        for escritor in (elos,) if isinstance(elos, str) else elos:
            assert escritor in chamados, (
                f"{caminho.name}:{gesto} não chama {escritor} — o gesto dela "
                "volta a morrer com a sessão (PERFIL-SALVA-TUDO-01)"
            )


def test_o_rascunho_tem_um_escritor_so_de_modo_em_cada_aba() -> None:
    """Quem escreve ``janela.draft`` nestas duas abas são as DUAS funções, e só.

    Um segundo escritor é a classe de bug desta casa: *"três escritores do perfil
    sem dono"* (auditoria 23/07). Aqui ele seria pior — um escritor que não passe
    por ``rascunho_com_modo_jogo`` grava o modo jogo sem a ressalva que a janela
    deve a ela quando o perfil vale para qualquer janela (09/08/2026,
    MODO-JOGO-VONTADE-DELA-01).

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


def test_a_aba_status_diz_ao_card_quem_e_o_dono_do_rascunho() -> None:
    """SOM-02/E4, a FIAÇÃO da aba (09/08/2026) — o andar sem o qual nada chega.

    O escritor existe, o gesto do card o chama, e ainda assim o perfil dela
    guardava o número VELHO: faltava alguém DIZER ao card quem é o dono. A aba
    Status é a única que pode — é ela que monta os cards, e é ela que já injeta
    ali o sink de saída e o pedido de rota.

    Este portão é irmão do ``test_cada_gesto_continua_chamando_o_escritor`` e
    está separado dele porque a injeção é por ``getattr`` com nome em string (o
    card pode ser um dublê de outra leva), e não por chamada de nome — o
    ``_nomes_chamados`` não a enxerga. O que se afere aqui é o par completo:
    o nome procurado E a chamada do que foi encontrado, com ``self``.

    MORDIDA: apagar o bloco `definir_dono_do_rascunho` de
    ``_sync_status_cards``. O produto continua verde em tudo o mais — os gestos
    seguem indo ao vivo — e o "Salvar Perfil" volta a gravar o volume velho,
    que a ativação seguinte reaplica ao controle.
    """
    funcao = _funcao(STATUS_PY, "_sync_status_cards")
    procurados = [
        no
        for no in ast.walk(funcao)
        if isinstance(no, ast.Call)
        and isinstance(no.func, ast.Name)
        and no.func.id == "getattr"
        and len(no.args) >= 2
        and isinstance(no.args[1], ast.Constant)
        and no.args[1].value == "definir_dono_do_rascunho"
    ]
    assert procurados, (
        "status_actions._sync_status_cards não procura "
        "'definir_dono_do_rascunho' no card — o registro do alto-falante volta "
        "a ser inerte e o 'Salvar Perfil' grava o volume velho"
    )
    # E o que foi encontrado tem de ser CHAMADO com a janela. Um `getattr` cujo
    # resultado ninguém usa passaria no portão acima e não ligaria nada.
    ligou = False
    for no in ast.walk(funcao):
        if not isinstance(no, ast.Assign) or no.value not in procurados:
            continue
        alvos = {a.id for a in no.targets if isinstance(a, ast.Name)}
        for chamada in ast.walk(funcao):
            if (
                isinstance(chamada, ast.Call)
                and isinstance(chamada.func, ast.Name)
                and chamada.func.id in alvos
                and any(
                    isinstance(arg, ast.Name) and arg.id == "self"
                    for arg in chamada.args
                )
            ):
                ligou = True
    assert ligou, (
        "o `definir_dono_do_rascunho` do card é procurado e nunca chamado com "
        "`self` — a janela não chega ao card e o rascunho fica sem dono"
    )
