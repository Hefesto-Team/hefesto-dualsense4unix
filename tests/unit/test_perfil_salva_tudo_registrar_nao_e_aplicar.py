"""PERFIL-SALVA-TUDO-01/E3 — o cadeado estrutural: REGISTRAR não é APLICAR."""
from __future__ import annotations

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ACOES = RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "actions"
EMULACAO_PY = ACOES / "emulation_actions.py"
INICIO_PY = ACOES / "home_actions.py"
RODAPE_PY = ACOES / "footer_actions.py"
CARD_PY = (
    RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "widgets" / "controller_card.py"
)
RASCUNHO_PY = RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "draft_config.py"
STATUS_PY = ACOES / "status_actions.py"

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
        "freestyle_set",
    }
)

ESCRITORES = {
    INICIO_PY: (
        "_coop_do_rascunho",
        "rascunho_com_modo",
        "registrar_modo_no_rascunho",
        # (`footer_actions._aplicar_o_modo_que_foi_gravado`, pela mesma
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
    """``with_suppress`` tem UM chamador na janela: ``rascunho_com_modo_jogo``."""
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
    """A fiação: apagar a chamada devolve a queixa dela inteira."""
    esperado: dict[tuple[Path, str], str | tuple[str, ...]] = {
        (EMULACAO_PY, "_apply_mode"): "registrar_modo_no_rascunho",
        (EMULACAO_PY, "_set_suppress"): "registrar_modo_jogo_no_rascunho",
        (RODAPE_PY, "_aplicar_escolha_pendente"): "registrar_modo_no_rascunho",
        (RODAPE_PY, "_persist_profile_async"): (
            "recolher_escolha_pendente_no_rascunho",
            "_aplicar_o_modo_que_foi_gravado",
        ),
        (RODAPE_PY, "_aplicar_o_modo_que_foi_gravado"): "_transicao_de_modo",
        (CARD_PY, "_enviar_volume_do_controle"): "_confirmado_pelo_daemon",
        (CARD_PY, "_on_speaker_mudo_clicado"): "_confirmado_pelo_daemon",
        (CARD_PY, "_on_canal_do_speaker_mudou"): "_confirmado_pelo_daemon",
        (CARD_PY, "_on_speaker_devolucao_clicada"): "_confirmado_pelo_daemon",
        (CARD_PY, "_confirmado_pelo_daemon"): "registrar_alto_falante_no_rascunho",
        (CARD_PY, "_enviar_volume_do_mic"): "_mic_confirmado_pelo_daemon",
        (CARD_PY, "_on_mic_clicado"): "_mic_confirmado_pelo_daemon",
        (CARD_PY, "_mic_confirmado_pelo_daemon"): "registrar_microfone_no_rascunho",
    }
    for (caminho, gesto), elos in esperado.items():
        chamados = _nomes_chamados(_funcao(caminho, gesto))
        for escritor in (elos,) if isinstance(elos, str) else elos:
            assert escritor in chamados, (
                f"{caminho.name}:{gesto} não chama {escritor} — o gesto dela "
                "volta a morrer com a sessão (PERFIL-SALVA-TUDO-01)"
            )


def test_o_rascunho_tem_um_escritor_so_de_modo_em_cada_aba() -> None:
    """Quem escreve ``janela.draft`` nestas duas abas são as DUAS funções, e só."""
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
    """SOM-02/E4, a FIAÇÃO da aba (09/08/2026) — o andar sem o qual nada chega."""
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
