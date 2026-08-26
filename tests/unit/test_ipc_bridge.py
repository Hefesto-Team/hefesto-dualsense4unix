"""Testes do helper `_safe_call` e wrappers síncronos em ipc_bridge.

Cobre AUDIT-FINDING-IPC-BRIDGE-BARE-EXCEPT-01:

  (a) daemon offline (FileNotFoundError, ConnectionError, IpcError, OSError)
      → wrapper retorna False + log em nível debug;
  (b) daemon online (_run_call retorna valor) → wrapper retorna True;
  (c) exceção inesperada (ValueError, TypeError, RuntimeError) **propaga** —
      bug real não pode ser silenciado;
  (d) wrappers específicos (profile_switch, led_set, rumble_set etc.) seguem o
      mesmo contrato.

E, desde 26/08/2026 (BG-07), a régua do ``__all__``:
``test_o_all_nao_publica_ponte_sem_travessia`` — publicar um nome ali é
prometer uma rota, e rota que ninguém atravessa apodrece sem ninguém ver.
"""
from __future__ import annotations

import ast
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.cli.ipc_client import IpcError

# ---------------------------------------------------------------------------
# _safe_call — contrato central
# ---------------------------------------------------------------------------


class TestSafeCallDaemonOffline:
    """Erros esperados de transporte retornam (False, None) e logam debug."""

    @pytest.mark.parametrize(
        "exc",
        [
            FileNotFoundError("socket ausente"),
            ConnectionRefusedError("daemon recusou conexão"),
            ConnectionResetError("conexão caiu"),
            OSError("erro genérico de socket"),
            IpcError(-32000, "servidor sinalizou erro"),
        ],
    )
    def test_retorna_false_em_erro_de_transporte(self, exc, caplog):
        caplog.set_level(logging.DEBUG, logger="hefesto_dualsense4unix.app.ipc_bridge")

        with patch.object(ipc_bridge, "_run_call", side_effect=exc):
            ok, result = ipc_bridge._safe_call("foo.bar")

        assert ok is False
        assert result is None

    def test_loga_debug_nao_warning(self, caplog):
        caplog.set_level(logging.DEBUG, logger="hefesto_dualsense4unix.app.ipc_bridge")

        with patch.object(
            ipc_bridge,
            "_run_call",
            side_effect=FileNotFoundError("sem socket"),
        ):
            ipc_bridge._safe_call("daemon.status")

        # Falha esperada não deve subir para warning; deve sair em debug.
        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert not warnings, f"warnings indevidos: {warnings!r}"


class TestSafeCallDaemonOnline:
    """Resposta do daemon retorna (True, resultado)."""

    def test_retorna_tupla_true_resultado(self):
        with patch.object(
            ipc_bridge,
            "_run_call",
            return_value={"status": "ok", "data": 42},
        ):
            ok, result = ipc_bridge._safe_call("daemon.status")

        assert ok is True
        assert result == {"status": "ok", "data": 42}

    def test_resultado_none_ainda_retorna_true(self):
        """None pode ser resultado legítimo (ex.: rumble.set sem retorno)."""
        with patch.object(ipc_bridge, "_run_call", return_value=None):
            ok, result = ipc_bridge._safe_call("rumble.set")

        assert ok is True
        assert result is None


class TestSafeCallExcecaoInesperadaPropaga:
    """Bugs reais (não transporte) NÃO podem ser silenciados."""

    @pytest.mark.parametrize(
        "exc",
        [
            ValueError("parâmetro fora de faixa"),
            TypeError("tipo errado"),
            RuntimeError("bug interno do bridge"),
            KeyError("chave ausente"),
            AttributeError("atributo inexistente"),
        ],
    )
    def test_propaga_excecoes_fora_do_filtro(self, exc):
        with (
            patch.object(ipc_bridge, "_run_call", side_effect=exc),
            pytest.raises(type(exc)),
        ):
            ipc_bridge._safe_call("foo.bar")


# ---------------------------------------------------------------------------
# Wrappers públicos — bool na superfície, propagação de bug preservada
# ---------------------------------------------------------------------------


class TestWrappersRetornamBool:
    """Os wrappers públicos retornam bool e respeitam o contrato.

    Eram treze até 26/08/2026; a poda da BG-07 levou três deles
    (``apply_draft``, ``rumble_policy_set``, ``mouse_emulation_set``) por não
    terem chamador nenhum em ``src/``.
    """

    OFFLINE_EXC = FileNotFoundError("daemon offline")

    def test_profile_switch_daemon_offline_false(self):
        with patch.object(ipc_bridge, "_run_call", side_effect=self.OFFLINE_EXC):
            assert ipc_bridge.profile_switch("foo") is False

    def test_profile_switch_online_true(self):
        with patch.object(ipc_bridge, "_run_call", return_value={"ok": True}):
            assert ipc_bridge.profile_switch("foo") is True

    def test_trigger_set_offline_false(self):
        with patch.object(ipc_bridge, "_run_call", side_effect=self.OFFLINE_EXC):
            assert ipc_bridge.trigger_set("left", "rigid", [100]) is False

    def test_trigger_set_online_true(self):
        with patch.object(ipc_bridge, "_run_call", return_value=None):
            assert ipc_bridge.trigger_set("left", "rigid", [100]) is True

    def test_led_set_offline_false(self):
        with patch.object(ipc_bridge, "_run_call", side_effect=self.OFFLINE_EXC):
            assert ipc_bridge.led_set((255, 0, 0)) is False

    def test_led_set_online_true(self):
        with patch.object(ipc_bridge, "_run_call", return_value=None):
            assert ipc_bridge.led_set((255, 0, 0), brightness=0.5) is True

    def test_rumble_set_offline_false(self):
        with patch.object(ipc_bridge, "_run_call", side_effect=self.OFFLINE_EXC):
            assert ipc_bridge.rumble_set(128, 128) is False

    def test_rumble_set_online_true(self):
        with patch.object(ipc_bridge, "_run_call", return_value=None):
            assert ipc_bridge.rumble_set(128, 128) is True

    def test_rumble_stop_offline_false(self):
        with patch.object(ipc_bridge, "_run_call", side_effect=self.OFFLINE_EXC):
            assert ipc_bridge.rumble_stop() is False

    def test_rumble_passthrough_offline_false(self):
        with patch.object(ipc_bridge, "_run_call", side_effect=self.OFFLINE_EXC):
            assert ipc_bridge.rumble_passthrough(True) is False

    def test_rumble_policy_custom_offline_false(self):
        with patch.object(ipc_bridge, "_run_call", side_effect=self.OFFLINE_EXC):
            assert ipc_bridge.rumble_policy_custom(0.5) is False

    def test_player_leds_set_offline_false(self):
        with patch.object(ipc_bridge, "_run_call", side_effect=self.OFFLINE_EXC):
            assert ipc_bridge.player_leds_set((True, False, True, False, True)) is False


class TestApplyDraftDetalhado:
    """APLICAR-VERDADE-01/E2 — a ponte para de estreitar a verdade.

    Havia uma ``apply_draft`` que devolvia ``bool``, e o mapa ``failed``
    (quais seções NÃO entraram) morria nela: quem chamava recebia ``False`` e
    não tinha como distinguir "o daemon está desligado" de "a seção de luzes
    falhou". A cura foi ADITIVA — a booleana ficou de pé (o valor-verdade dela
    É o contrato R-18, e um ``dict`` no lugar seria sempre verdadeiro num
    ``if``), e quem precisa dizer a verdade na tela passou a chamar a
    detalhada. Em 26/08/2026 a booleana foi PODADA (BG-07): ninguém tinha
    migrado de volta, e ela era a última rota do ``__all__`` sem travessia
    nesta família. A regra R-18 continua tendo dono único —
    ``aplicacao_confirmada``, exercitada logo abaixo.

    Esta classe é a metade da E2 que NÃO precisa de GTK, então morde também no
    CI headless; a metade da tela mora em
    ``tests/unit/test_aplicar_verdade_ponte_lightbar.py``.
    """

    OFFLINE_EXC = FileNotFoundError("socket ausente")

    def test_o_failed_atravessa_a_ponte(self):
        """Falha-sem: o mapa de seções que caíram tem de CHEGAR ao chamador."""
        resposta = {
            "status": "ok",
            "applied": [],
            "failed": {"leds": "hidraw: Permission denied"},
        }
        with patch.object(ipc_bridge, "_run_call", return_value=resposta):
            assert ipc_bridge.apply_draft_detalhado({"leds": {}}) == resposta

    def test_offline_devolve_none_e_nao_dicionario_vazio(self):
        """``None`` quer dizer "não houve resposta" — é o que separa "o Hefesto
        está desligado" de "a seção não entrou". Um ``{}`` no lugar apagaria a
        distinção que a aba Lightbar usa para escolher a frase."""
        with patch.object(ipc_bridge, "_run_call", side_effect=self.OFFLINE_EXC):
            assert ipc_bridge.apply_draft_detalhado({"leds": {}}) is None

    def test_resposta_que_nao_e_dicionario_e_tratada_como_ausencia(self):
        with patch.object(ipc_bridge, "_run_call", return_value="ok"):
            assert ipc_bridge.apply_draft_detalhado({"leds": {}}) is None

    def test_aplicacao_confirmada_e_o_dono_unico_da_regra_r18(self):
        """A mesma leitura do payload para os dois caminhos — sem ``failed``
        vazio virando sucesso e sem daemon antigo virando falha."""
        confirmada = ipc_bridge.aplicacao_confirmada
        assert confirmada({"status": "ok", "applied": ["leds"]}) is True
        assert confirmada({"status": "ok", "applied": []}) is False
        assert confirmada({"status": "ok"}) is True  # daemon antigo
        assert confirmada({"status": "erro", "applied": ["leds"]}) is False
        assert confirmada(None) is False
        assert confirmada(True) is False

    def test_daemon_state_full_offline_none(self):
        with patch.object(ipc_bridge, "_run_call", side_effect=self.OFFLINE_EXC):
            assert ipc_bridge.daemon_state_full() is None

    def test_daemon_state_full_online_dict(self):
        with patch.object(ipc_bridge, "_run_call", return_value={"a": 1}):
            assert ipc_bridge.daemon_state_full() == {"a": 1}

    def test_daemon_status_basic_offline_none(self):
        with patch.object(ipc_bridge, "_run_call", side_effect=self.OFFLINE_EXC):
            assert ipc_bridge.daemon_status_basic() is None

    def test_daemon_status_basic_online_dict(self):
        with patch.object(ipc_bridge, "_run_call", return_value={"running": True}):
            assert ipc_bridge.daemon_status_basic() == {"running": True}


class TestWrappersPropagandoBugs:
    """Exceções fora do filtro transporte propagam — executor detecta bug."""

    @pytest.mark.parametrize(
        "wrapper,args",
        [
            (ipc_bridge.profile_switch, ("foo",)),
            (ipc_bridge.trigger_set, ("left", "rigid", [1])),
            (ipc_bridge.led_set, ((10, 20, 30),)),
            (ipc_bridge.rumble_set, (1, 2)),
            (ipc_bridge.rumble_stop, ()),
            (ipc_bridge.rumble_passthrough, (True,)),
            (ipc_bridge.rumble_policy_custom, (0.3,)),
            (ipc_bridge.player_leds_set, ((True, True, False, False, False),)),
            (ipc_bridge.apply_draft_detalhado, ({"x": 1},)),
            (ipc_bridge.daemon_state_full, ()),
            (ipc_bridge.daemon_status_basic, ()),
        ],
    )
    def test_value_error_propaga(self, wrapper, args):
        with (
            patch.object(
                ipc_bridge,
                "_run_call",
                side_effect=ValueError("bug real"),
            ),
            pytest.raises(ValueError, match="bug real"),
        ):
            wrapper(*args)


# ---------------------------------------------------------------------------
# profile_list — fallback de disco preservado
# ---------------------------------------------------------------------------


class TestProfileListFallback:
    """profile_list tem duas camadas: IPC primário + disco fallback."""

    def test_daemon_online_retorna_perfis_do_daemon(self):
        with patch.object(
            ipc_bridge,
            "_run_call",
            return_value={"profiles": [{"name": "default", "active": True}]},
        ):
            resultado = ipc_bridge.profile_list()

        assert resultado == [{"name": "default", "active": True}]

    def test_daemon_offline_usa_fallback_disco(self):
        """IPC falha → loader de disco é consultado."""
        with patch.object(
            ipc_bridge,
            "_run_call",
            side_effect=FileNotFoundError("sem socket"),
        ):
            # Chamada real ao loader — garante formato mínimo.
            resultado = ipc_bridge.profile_list()

        # assets/profiles_default/ tem pelo menos 1 perfil default.
        assert isinstance(resultado, list)
        assert all("name" in p and "active" in p for p in resultado)
        assert all(p["active"] is False for p in resultado)  # fallback marca offline


# ---------------------------------------------------------------------------
# HARM-19 — recusa do daemon != daemon offline
# ---------------------------------------------------------------------------


class TestTriggerSetChecked:
    """`trigger_set_checked` separa "o daemon recusou" de "não achei o daemon".

    `_safe_call` colapsa os dois em (False, None) — e era por isso que a aba
    Triggers pintava "Fim <= Início" como "daemon offline?" com o daemon vivo.
    """

    def test_recusa_de_validacao_devolve_a_mensagem(self):
        from hefesto_dualsense4unix.daemon.ipc_server import CODE_INVALID_PARAMS

        exc = IpcError(CODE_INVALID_PARAMS, "end (3) deve ser > start (5)")
        with patch.object(ipc_bridge, "_run_call", side_effect=exc):
            ok, motivo = ipc_bridge.trigger_set_checked("left", "Bow", [5, 3, 4, 4])

        assert ok is False
        assert motivo == "end (3) deve ser > start (5)"

    def test_daemon_offline_nao_inventa_motivo(self):
        with patch.object(
            ipc_bridge, "_run_call", side_effect=FileNotFoundError("sem socket")
        ):
            ok, motivo = ipc_bridge.trigger_set_checked("left", "Rigid", [5, 200])

        assert (ok, motivo) == (False, None)

    def test_timeout_de_transporte_nao_vira_motivo(self):
        """O timeout do IpcClient também é IpcError — mas com code=-1, não é
        uma recusa do daemon."""
        with patch.object(
            ipc_bridge, "_run_call", side_effect=IpcError(-1, "conexão timeout")
        ):
            ok, motivo = ipc_bridge.trigger_set_checked("left", "Rigid", [5, 200])

        assert (ok, motivo) == (False, None)

    def test_sucesso_sem_motivo(self):
        with patch.object(ipc_bridge, "_run_call", return_value={"status": "ok"}):
            assert ipc_bridge.trigger_set_checked("left", "Rigid", [5, 200]) == (
                True,
                None,
            )

    def test_excecao_inesperada_propaga(self):
        with (
            patch.object(ipc_bridge, "_run_call", side_effect=TypeError("bug")),
            pytest.raises(TypeError),
        ):
            ipc_bridge.trigger_set_checked("left", "Rigid", [5, 200])


# ---------------------------------------------------------------------------
# BG-07 (26/08/2026) — o `__all__` é lista de ROTAS, não vitrine
# ---------------------------------------------------------------------------

_RAIZ = Path(__file__).resolve().parents[2]
_SRC = _RAIZ / "src" / "hefesto_dualsense4unix"
_PONTE = _SRC / "app" / "ipc_bridge.py"

#: Quem ficou no lugar de cada ponte podada em 26/08/2026. A mensagem de falha
#: precisa disto: reprovar dizendo só "sem chamador" manda a próxima pessoa
#: procurar um chamador para uma função que já foi substituída — que é
#: exatamente o gesto que a poda existe para impedir.
_QUEM_FICOU_NO_LUGAR: dict[str, str] = {
    "apply_draft": "apply_draft_detalhado + aplicacao_confirmada",
    "rumble_policy_set": "rumble_policy_set_checked",
    "rumble_policy_set_detalhado": "rumble_policy_set_checked",
    "trigger_reset": "trigger_reset_detalhado",
    "mouse_emulation_set": (
        "call_async('mouse.emulation.set', ...) direto, em "
        "app/actions/mouse_actions.py:462 e :560"
    ),
}

#: As rotas publicadas que HOJE ninguém atravessa, cada uma com onde a dívida
#: já está registrada. Declarar é honesto; o que esta lista não deixa é a
#: sexta nascer calada.
#:
#: Todas as quatro têm lápide viva em
#: `tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py`, com o endereço do
#: que as fecharia — é lá que mora a razão longa, e repeti-la aqui só criaria
#: duas versões para divergirem.
_SEM_TRAVESSIA_DECLARADA: dict[str, str] = {
    "alvo_honrado": (
        "MIC-DA-MESA-CHEIA-01: lê o `por_uniq` do daemon. Lápide em "
        "`_SEM_CAMINHO_HOJE`; fecha em app/widgets/controller_card.py, e o "
        "estado novo de tela que ela pede é DESENHO — a palavra é dela."
    ),
    "led_set": (
        "BG-01 trocou os três chamadores por `led_set_detalhado`. Lápide em "
        "`_SEM_CAMINHO_HOJE`; a razão manda apagar, e a poda não coube na "
        "ordem da BG-07, que nomeia cinco funções e não esta."
    ),
    "machine_declare": (
        "CONFIG-03: invólucro estreito de `machine_declare_detalhado`, que é "
        "quem `app/actions/footer_actions.py:353` chama. Lápide em "
        "`_NAO_E_PROMESSA`."
    ),
    "player_leds_set": (
        "Irmão exato do `led_set`, pela mesma edição (BG-01) e com a mesma "
        "lápide. Cai no mesmo commit que ele, quando cair."
    ),
}


def _nomes_do_all() -> list[str]:
    """Os nomes do ``__all__`` LIDOS DO ARQUIVO, nunca do módulo importado.

    Importar devolveria o que o interpretador montou; a pergunta aqui é o que
    o arquivo PUBLICA. São a mesma coisa hoje, e é justamente por serem a mesma
    coisa hoje que a diferença passaria despercebida amanhã.
    """
    arvore = ast.parse(_PONTE.read_text(encoding="utf-8"))
    for no in arvore.body:
        if isinstance(no, ast.Assign) and any(
            isinstance(alvo, ast.Name) and alvo.id == "__all__" for alvo in no.targets
        ):
            assert isinstance(no.value, ast.List)
            return [
                elemento.value
                for elemento in no.value.elts
                if isinstance(elemento, ast.Constant) and isinstance(elemento.value, str)
            ]
    raise AssertionError(f"`__all__` não encontrado em {_PONTE}")


def _identificadores(no: ast.AST) -> set[str]:
    """Os nomes que este trecho de árvore CITA — só código, nunca texto.

    Ler por AST, e não por ``grep``, é o que separa citação de chamada: em
    26/08/2026 `led_set` aparecia duas vezes em `app/actions/lightbar_actions.py`
    e as duas eram COMENTÁRIO. Comentário não atravessa ponte nenhuma, e um
    portão que o conta por chamador diz "entregue" sobre código morto.
    """
    citados: set[str] = set()
    for filho in ast.walk(no):
        if isinstance(filho, ast.Name):
            citados.add(filho.id)
        elif isinstance(filho, ast.Attribute):
            citados.add(filho.attr)
        elif isinstance(filho, ast.alias):
            citados.add(filho.name.rsplit(".", 1)[-1])
    return citados


def _travessias() -> dict[str, list[str]]:
    """``{nome do __all__: quem o cita}``, varrendo `src/` inteiro.

    Uma citação DENTRO do próprio `ipc_bridge.py` só conta quando vem de outro
    escopo — o corpo de `apply_draft` citando `apply_draft_detalhado` é
    travessia da segunda, não da primeira. Sem essa distinção, todo invólucro
    estreito se daria por vivo citando a irmã que o substituiu, e a régua
    passaria a medir a corrente fechada em vez da rota.
    """
    travessias: dict[str, list[str]] = {nome: [] for nome in _nomes_do_all()}

    def registrar(nome: str, onde: str) -> None:
        if nome in travessias:
            travessias[nome].append(onde)

    for arquivo in sorted(_SRC.rglob("*.py")):
        texto = arquivo.read_text(encoding="utf-8")
        arvore = ast.parse(texto)
        rotulo = arquivo.relative_to(_SRC).as_posix()
        if arquivo != _PONTE:
            for citado in _identificadores(arvore):
                registrar(citado, rotulo)
            continue
        for no in arvore.body:
            dono = getattr(no, "name", None)
            if isinstance(no, ast.Assign) and any(
                isinstance(alvo, ast.Name) and alvo.id == "__all__"
                for alvo in no.targets
            ):
                continue  # o próprio `__all__` não é travessia de ninguém
            for citado in _identificadores(no):
                if citado != dono:
                    registrar(citado, f"{rotulo}:{getattr(no, 'lineno', 0)}")
    return travessias


class TestOAllSoPublicaRotaAtravessada:
    """Nome no ``__all__`` é promessa de rota; rota sem travessia apodrece.

    Régua da BG-07, e ela NÃO substitui
    `tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py`: aquele mede alcance
    a partir dos pontos de entrada do produto e é mais forte. Esta é mais
    estreita e mais barata, e responde a pergunta que é só deste arquivo — o
    que a ponte PUBLICA como rota — em vez de varrer o repositório inteiro.
    """

    def test_o_all_nao_publica_ponte_sem_travessia(self) -> None:
        travessias = _travessias()
        soltas = sorted(
            nome
            for nome, quem in travessias.items()
            if not quem and nome not in _SEM_TRAVESSIA_DECLARADA
        )
        assert not soltas, (
            "o `__all__` de `app/ipc_bridge.py` publica rota que NINGUÉM "
            "atravessa em `src/`:\n"
            + "\n".join(
                f"  - {nome} — quem ficou no lugar: "
                + _QUEM_FICOU_NO_LUGAR.get(
                    nome,
                    f"procure a irmã `{nome}_detalhado`, que é a forma que a "
                    "janela costuma usar",
                )
                for nome in soltas
            )
            + "\n`tests/` NÃO conta: foi assim que cinco invólucros estreitos "
            "passaram por vivos até 26/08/2026 (BG-07).\n"
            "FAÇA UMA das duas: FIE a rota a partir de `src/`, ou APAGUE o "
            "invólucro e a lápide dele no portão de lápides. Se a dívida for "
            "para ficar, DECLARE em `_SEM_TRAVESSIA_DECLARADA` com a razão."
        )

    def test_a_isencao_declarada_nao_vira_cemiterio(self) -> None:
        """A outra direção: isenção citando nome que saiu do ``__all__``.

        Sem ela a lista de cima viraria cemitério e passaria a responder a
        pergunta com entradas mortas — que é o defeito que o portão de lápides
        já pagou uma vez.
        """
        publicados = set(_nomes_do_all())
        fantasmas = sorted(set(_SEM_TRAVESSIA_DECLARADA) - publicados)
        assert not fantasmas, (
            "`_SEM_TRAVESSIA_DECLARADA` isenta nome que o `__all__` não "
            f"publica mais: {fantasmas}\n"
            "Se a rota foi podada, apague a isenção junto — ela existe para "
            "explicar uma dívida VIVA."
        )

    def test_a_regua_enxerga_chamada_e_ignora_texto(self) -> None:
        """Validação do instrumento, em fonte FABRICADA e na árvore de verdade.

        Um instrumento quebrado erra em duas direções opostas, e cada metade
        pega uma:

        * numa fonte fabricada, `chamada_de_verdade` é código e as outras três
          são comentário, docstring e literal. Contar texto é o falso positivo
          que já enganou o portão de lápides: a chave de IPC
          `"profile.apply_draft"`, escrita noutro módulo e para outra coisa,
          dava a função `apply_draft` por alcançada;
        * na árvore de verdade, `call_async` é a rota mais atravessada da ponte
          — dezenas de chamadores em `app/actions/`. Se ela aparecesse sem
          travessia, a varredura não estaria enxergando chamada nenhuma, e o
          verde de cima seria o silêncio de uma régua que não mede.
        """
        fabricada = ast.parse(
            '"""Este docstring cita citada_em_docstring."""\n'
            "# citada_em_comentario(1, 2)\n"
            "def borda():\n"
            '    rotulo = "citada_em_literal"\n'
            "    return chamada_de_verdade(rotulo)\n"
        )
        citados = _identificadores(fabricada)
        assert "chamada_de_verdade" in citados, (
            "a varredura não enxergou uma chamada explícita"
        )
        for texto in (
            "citada_em_docstring",
            "citada_em_comentario",
            "citada_em_literal",
        ):
            assert texto not in citados, (
                f"a varredura contou `{texto}` por chamador — ela está lendo "
                "TEXTO, e texto não atravessa ponte nenhuma"
            )

        assert _travessias()["call_async"], (
            "a varredura não achou chamador de `call_async` em `src/` — ela "
            "não está enxergando a árvore de verdade"
        )
