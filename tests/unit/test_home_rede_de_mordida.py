"""A rede de mordida que faltava na primeira tela — I7.

INÍCIO NÃO MENTE-01. Duas redes, e cada uma cobre um defeito de forma que esta
casa já pagou:

**(a) as três réguas.** Nenhum teste reprovava quando o TOPO do `state_full`, a
LISTA de controles dele e o `controller.list` discordam sobre quantos controles
há. Foi por isso que a divergência do §2.1 sobreviveu até alguém a medir à mão,
com um socket cru, em 23/08/2026: a mesma tela dizia, no mesmo instante, que
havia um controle com 75% de bateria e que não havia controle nenhum.

**(b) o chamador de PRODUÇÃO.** Nenhum portão desta casa perguntava *"existe
chamador fora de `tests/`?"* para um símbolo específico — e essa é exatamente a
forma da mordida que faltou em I1, I2 e I3. O
`portao_a_casa_sabe_e_o_produto_nao_faz.py` faz a pergunta para a árvore
inteira, com registro de lacunas conhecidas; aqui ela é feita para os TRÊS
símbolos desta onda, sem registro nenhum onde se esconder.

POR QUE (a) É `xfail(strict=True)` E NÃO VERMELHO
--------------------------------------------------

A incoerência do §2.1 é do DAEMON, não desta aba: quem publica o topo do
`state_full` a partir de um controle que já saiu é o `ipc_handlers`, e a cura
tem dono e sprint próprios (a **Z5** da Onda 0). Deixar o teste vermelho aqui
não a aproxima e derruba os portões da leva inteira.

`strict=True` é o que o mantém honesto: no dia em que a Z5 fechar, este teste
passa a PASSAR e o pytest reprova por `XPASS(strict)` — obrigando quem
integrar a apagar o `xfail` e a nota. É o oposto de um `skip`, que envelheceria
calado.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"
FIXTURE_MEDIDA = RAIZ / "tests" / "fixtures" / "state_full_mesa_vazia_medida.json"

#: A resposta do `controller.list` na MESMA medição de 23/08/2026, copiada do
#: §2.1 da sprint. Fica aqui, e não no fixture, porque é outra chamada de IPC —
#: juntar as duas num arquivo só faria parecer que o daemon publica as duas
#: coisas no mesmo payload, que é justamente o engano que este teste mede.
CONTROLLER_LIST_MEDIDO: dict[str, Any] = {
    "controllers": [
        {"connected": False, "transport": None, "is_primary": False}
    ]
}


# ----------------------------------------------------------------------
# (a) As três réguas
# ----------------------------------------------------------------------


def quantos_o_topo_diz(state: dict[str, Any]) -> int:
    """A régua 1: o TOPO do `state_full`.

    Ele responde por UM controle — o primário — com as chaves soltas
    `connected`, `transport` e `battery_pct`. `connected` verdadeiro é a
    afirmação "há pelo menos um controle na casa"; falso é "não há nenhum".

    Não é a lista, e é essa a diferença que teste nenhum olhava: as duas são
    publicadas pelo mesmo handler, no mesmo dicionário, e podem discordar.
    """
    return 1 if state.get("connected") else 0


def quantos_a_lista_diz(state: dict[str, Any]) -> int:
    """A régua 2: `state_full.controllers`, contando só os conectados.

    O filtro por `connected` é o do PRODUTO, não uma escolha deste teste:
    `describe_controllers` devolve UMA entrada com `connected=False` quando não
    há controle nenhum, e a aba Início filtra exatamente assim desde a
    HARM-CARD-FANTASMA-01 (`home_actions._render_home`). Contar sem filtrar
    produziria aqui um achado que a tela não tem.
    """
    entradas = state.get("controllers") or []
    return len(
        [c for c in entradas if isinstance(c, dict) and c.get("connected")]
    )


def quantos_o_controller_list_diz(resposta: dict[str, Any]) -> int:
    """A régua 3: a resposta do `controller.list`, com o mesmo filtro."""
    entradas = resposta.get("controllers") or []
    return len(
        [c for c in entradas if isinstance(c, dict) and c.get("connected")]
    )


def divergencia_das_tres_reguas(
    state: dict[str, Any], controller_list: dict[str, Any]
) -> str | None:
    """``None`` quando as três concordam; a frase do desacordo quando não.

    "Concordar" aqui é mais frouxo que igualdade, e de propósito: o topo só
    sabe contar até um. O que ele afirma é a EXISTÊNCIA de controle, e é sobre
    isso que as três têm de dizer a mesma coisa — havia zero, ou havia pelo
    menos um. Exigir o número exato do topo reprovaria toda mesa de dois, que
    está certa.
    """
    topo = quantos_o_topo_diz(state)
    lista = quantos_a_lista_diz(state)
    crua = quantos_o_controller_list_diz(controller_list)
    ha_algum = {bool(topo), bool(lista), bool(crua)}
    if len(ha_algum) > 1:
        return (
            f"as três réguas discordam sobre haver controle: o topo do "
            f"state_full diz {topo}, a lista dele diz {lista}, o "
            f"controller.list diz {crua}"
        )
    if lista != crua:
        return (
            f"a lista do state_full diz {lista} controle(s) e o controller.list "
            f"diz {crua}"
        )
    return None


def test_a_regua_da_coerencia_sabe_acusar() -> None:
    """A régua reprova quando as três discordam — o dublê que sabe recusar.

    Sem este teste a função acima poderia devolver ``None`` para tudo e o teste
    do payload coerente passaria por severo (A2, 23/08/2026).
    """
    topo_mente = {"connected": True, "controllers": []}
    assert divergencia_das_tres_reguas(topo_mente, {"controllers": []}) is not None

    lista_mente = {
        "connected": True,
        "controllers": [{"connected": True}, {"connected": True}],
    }
    assert (
        divergencia_das_tres_reguas(
            lista_mente, {"controllers": [{"connected": True}]}
        )
        is not None
    )


def test_a_regua_da_coerencia_aceita_uma_mesa_coerente() -> None:
    """E aprova quando as três dizem a mesma coisa — nos dois sentidos."""
    mesa_de_dois = {
        "connected": True,
        "controllers": [{"connected": True}, {"connected": True}],
    }
    lista_de_dois = {"controllers": [{"connected": True}, {"connected": True}]}
    assert divergencia_das_tres_reguas(mesa_de_dois, lista_de_dois) is None

    mesa_vazia = {"connected": False, "controllers": []}
    assert divergencia_das_tres_reguas(mesa_vazia, {"controllers": []}) is None


def test_o_fixture_medido_existe_e_e_o_do_paragrafo_2_1() -> None:
    """O payload de 23/08 está no disco, e ainda é o que a sprint descreve.

    Sem esta conferência o `xfail` abaixo poderia ficar verde por o fixture ter
    sido "consertado" à mão — o que apagaria a medição em vez de curá-la.
    """
    assert FIXTURE_MEDIDA.is_file(), (
        f"{FIXTURE_MEDIDA} sumiu. É a única cópia versionada do payload que "
        "mostrou os três vereditos contraditórios da aba Início."
    )
    estado = json.loads(FIXTURE_MEDIDA.read_text(encoding="utf-8"))
    assert estado["connected"] is True
    assert estado["battery_pct"] == 75
    assert quantos_a_lista_diz(estado) == 0


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Z5 (Onda 0) ainda aberta: quem publica o topo do state_full a partir "
        "de um controle que já saiu é o daemon, não esta aba. Medido em "
        "23/08/2026 com socket cru. Quando a Z5 fechar este teste PASSA e o "
        "strict reprova — que é o gatilho para apagar este xfail."
    ),
)
def test_as_tres_reguas_concordam_no_payload_medido() -> None:
    """A mordida do §2.1: um payload, três vereditos, e nenhum teste reprovava.

    É esta a linha que faltava. Enquanto ela não estiver verde, a aba Início
    pode continuar dizendo "conectado, 75%" no topo e "Nenhum controle
    conectado." no frame, no mesmo segundo, sem que a suíte pisque.
    """
    estado = json.loads(FIXTURE_MEDIDA.read_text(encoding="utf-8"))
    problema = divergencia_das_tres_reguas(estado, CONTROLLER_LIST_MEDIDO)
    assert problema is None, problema


# ----------------------------------------------------------------------
# (b) O chamador de PRODUÇÃO
# ----------------------------------------------------------------------

#: Os três símbolos desta onda que existiam sem ninguém os chamar em produção.
#: `_home_flavor_pedido` não é função: é o campo que guarda a escolha recusada
#: dela, e o que faltava era um ESCRITOR com valor (o nascimento em `None` e a
#: limpeza não contam — ver a docstring de `_escritores_com_valor`).
_SIMBOLOS_QUE_PRECISAM_DE_CHAMADOR = (
    "desfecho_da_troca",
    "toast_da_troca_de_mascara",
)

#: Onde NÃO procurar: o próprio módulo que define os símbolos. Uma função
#: chamada só por ela mesma (ou pelo `__all__` do módulo dela) continua sem
#: caminho de produção — foi assim que as duas de cima passaram um mês
#: parecendo entregues.
_MODULO_DE_ORIGEM = "app/actions/home_actions.py"


def _arquivos_de_producao() -> list[Path]:
    return sorted(p for p in SRC.rglob("*.py") if p.is_file())


def _chamadores(nome: str) -> list[str]:
    """Arquivos de `src/` que CHAMAM `nome`, tirando o módulo que o define.

    Chamada, e não menção: `ast.Call` com `func` sendo o nome (ou um atributo
    com esse nome). Uma linha de `__all__` ou um comentário citando a função
    não é caminho — é exatamente o que fazia `grep` dizer "3 ocorrências" para
    algo que ninguém executava.
    """
    achados: list[str] = []
    for arquivo in _arquivos_de_producao():
        relativo = str(arquivo.relative_to(SRC)).replace("\\", "/")
        if relativo == _MODULO_DE_ORIGEM:
            continue
        try:
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover — arquivo quebrado é outro erro
            continue
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            alvo = no.func
            if isinstance(alvo, ast.Name) and alvo.id == nome:
                achados.append(relativo)
                break
            if isinstance(alvo, ast.Attribute) and alvo.attr == nome:
                achados.append(relativo)
                break
    return achados


def _escritores_com_valor(campo: str) -> list[str]:
    """Arquivos de `src/` que atribuem algo NÃO-``None`` a ``self.<campo>``.

    O nascimento (`self._home_flavor_pedido: str | None = None`) e a limpeza
    (`= None`) não contam, e essa é a distinção que o `grep` do §2.2c não fazia:
    o campo tinha duas atribuições em `src/` e mesmo assim NUNCA guardava
    escolha nenhuma. Só um escritor com valor faz a escolha recusada dela
    sobreviver ao próximo tique de 2 s.
    """
    achados: list[str] = []
    for arquivo in _arquivos_de_producao():
        relativo = str(arquivo.relative_to(SRC)).replace("\\", "/")
        try:
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover
            continue
        for no in ast.walk(arvore):
            alvos: list[ast.expr] = []
            valor: ast.expr | None = None
            if isinstance(no, ast.Assign):
                alvos, valor = list(no.targets), no.value
            elif isinstance(no, ast.AnnAssign):
                alvos, valor = [no.target], no.value
            if valor is None:
                continue
            if isinstance(valor, ast.Constant) and valor.value is None:
                continue
            for alvo in alvos:
                if isinstance(alvo, ast.Attribute) and alvo.attr == campo:
                    achados.append(relativo)
                    break
    return sorted(set(achados))


def test_as_duas_funcoes_do_desfecho_tem_chamador_de_producao() -> None:
    """I1: elas existem desde 19/08 e ninguém as chamava fora de `tests/`.

    `desfecho_da_troca` separa aplicou / já-estava / recusado-pelo-gate;
    `toast_da_troca_de_mascara` dá a frase de cada desfecho. Sem chamador, o
    rodapé continua dizendo "O jogo agora vê: Xbox 360" sobre uma troca que o
    gate R-04 RECUSOU — que é o que ele fez na noite de 18→19/08/2026, com o
    journal registrando `vpad_recriacao_bloqueada_por_jogo` sete milissegundos
    antes.

    As duas entram JUNTAS: meia cura escreveria a frase certa sobre um desfecho
    que ninguém apurou.
    """
    orfas = {
        nome: _chamadores(nome)
        for nome in _SIMBOLOS_QUE_PRECISAM_DE_CHAMADOR
    }
    sem_caminho = [nome for nome, onde in orfas.items() if not onde]
    assert not sem_caminho, (
        f"sem chamador de produção: {sem_caminho}. Elas são a cura escrita e "
        "nunca ligada — o defeito-mãe desta casa. Quem as chama é o rodapé, no "
        "`_transicao_de_modo`, onde a resposta do daemon chega e hoje é "
        "descartada."
    )


def test_a_escolha_recusada_dela_tem_quem_a_grave() -> None:
    """I2: `_home_flavor_pedido` é a única memória de um pedido não atendido.

    Medido no §2.2c: em `src/` só existiam o nascimento (`= None`) e a limpeza
    (`= None`); os únicos escritores com valor eram quatro linhas de teste.
    Consequência na tela: o `_render_home` reescreve o seletor com o valor do
    daemon a cada 2 s, então a escolha recusada dela some em dois segundos, sem
    uma palavra.
    """
    escritores = _escritores_com_valor("_home_flavor_pedido")
    assert escritores, (
        "ninguém grava `_home_flavor_pedido` com valor em `src/`. A escolha "
        "que o daemon recusou não sobrevive ao próximo tique — e a linha de "
        "divergência, que é quem a contaria, não tem o que ler."
    )


def test_a_varredura_de_chamador_sabe_dizer_nao() -> None:
    """A régua recusa: um nome que ninguém chama tem de sair sem chamador.

    Sem isto, uma varredura quebrada (um `ast.walk` que nunca casa) devolveria
    listas vazias para tudo e os dois testes acima ficariam vermelhos por
    defeito de instrumento — ou, pior, uma que casasse com tudo os deixaria
    verdes para sempre.
    """
    assert _chamadores("funcao_que_nao_existe_em_lugar_nenhum_desta_arvore") == []
    assert _escritores_com_valor("_campo_que_ninguem_jamais_escreveu") == []
    # E ela ACHA o que existe: `texto_da_ponte` é chamada pelo próprio
    # `home_actions`... que está excluído. Mas `mode_of_state`, de
    # `mode_transition`, é chamada por várias abas.
    assert _chamadores("mode_of_state"), (
        "a varredura não acha nem `mode_of_state`, que meia GUI chama — o "
        "instrumento está cego, e o vermelho dos outros testes não seria do "
        "código"
    )
