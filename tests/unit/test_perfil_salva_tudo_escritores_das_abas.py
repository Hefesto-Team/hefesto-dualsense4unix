"""PERFIL-SALVA-TUDO-01/E3 — os escritores que faltavam nas abas Início/Emulação.

A queixa dela, 29/07: *"temos o perfil do jogo tipo pragmata, aí em todas as abas
fiz alterações e salvei o perfil, aí essas configs de outras abas não ficam
salvas"*. A onda 2 construiu o lugar de guardar (``DraftConfig.with_mode`` e
``with_suppress``) e registrou por escrito que não havia UM escritor fora do
próprio ``draft_config`` — ``grep -c 'self\\.draft'`` valia **0** nas duas abas
que mexem em modo, máscara, co-op e "modo jogo".

Estes testes entram pelos handlers PÚBLICOS das duas abas (o gesto dela) e
terminam em ``to_profile`` (o arquivo que o "Salvar Perfil" grava) — o defeito
vive na fronteira entre o clique e o disco, e nenhum teste de módulo isolado o
veria.

Os dois lados que precisam morder:

1. o gesto CHEGA ao rascunho e sai no ``Profile`` (a queixa dela);
2. o escritor NÃO aplica nada (HARM-05). Registrar no rascunho não pode virar um
   "Aplicar" ao vivo: se virar, um toque num gatilho passa a poder recriar o vpad
   ou suspender a emulação no meio da partida. O portão estrutural desse contrato
   mora em ``test_perfil_salva_tudo_registrar_nao_e_aplicar.py`` (roda sem GTK);
   aqui ele é provado com IPC ENVENENADO.
"""
from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: no lugar de `pytest.importorskip("gi")`, que ACEITA o stub
# que outro arquivo de teste planta em sys.modules. No TOPO, antes de qualquer
# import do pacote: `app/actions/base.py` importa `gi` na primeira linha útil.
exigir_gi_real("PERFIL-SALVA-TUDO-01/E3 (escritores das abas Inicio/Emulacao)")

from hefesto_dualsense4unix.app.actions import emulation_actions as ea
from hefesto_dualsense4unix.app.actions import footer_actions as fa
from hefesto_dualsense4unix.app.actions import home_actions as ha
from hefesto_dualsense4unix.app.actions import mode_transition as mt
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
    ProfileModeConfig,
)

ROXO = (97, 53, 131)


def _perfil(
    nome: str,
    *,
    com_regra: bool,
    mode: ProfileModeConfig | None = None,
    suppress: bool = False,
    priority: int = 100,
) -> Profile:
    """Perfil de teste; ``com_regra=False`` é o catch-all (os cinco dela)."""
    return Profile(
        name=nome,
        match=(
            MatchCriteria(window_class=["steam_app_3357650"])
            if com_regra
            else MatchAny()
        ),
        priority=priority,
        leds=LedsConfig(lightbar=ROXO, auto_player_colors=False),
        mode=mode,
        suppress_desktop_emulation=suppress,
    )


class _FakeSelector:
    """SegmentedSelector: API por-ID, "changed" emitido SEM argumentos."""

    def __init__(self, active: str | None = None) -> None:
        self._active_id = active
        self._handlers: list[Any] = []

    def connect(self, signal: str, handler: Any) -> None:
        if signal == "changed":
            self._handlers.append(handler)

    def get_active_id(self) -> str | None:
        return self._active_id

    def set_active_id(self, the_id: str) -> None:
        if the_id == self._active_id:
            return
        self._active_id = the_id
        for handler in list(self._handlers):
            handler(self)


class _FakeLabel:
    def __init__(self) -> None:
        self.text = ""

    def set_text(self, text: str) -> None:
        self.text = text


class _Janela(ea.EmulationActionsMixin, ha.HomeActionsMixin, fa.FooterActionsMixin):
    """Emulação + Início + rodapé compartilhando UM rascunho (a MRO do HefestoApp).

    AGORA-E-DEPOIS-01 (08/08/2026): o rodapé entrou na lista porque o gesto da
    aba Início passou a terminar nele — o clique no seletor marca, o "Aplicar"
    aplica e registra. Sem os três na mesma casca, este arquivo mediria metade
    do caminho.
    """

    def __init__(self, perfil: Profile) -> None:
        self.draft = DraftConfig.from_profile(perfil)
        self.toasts: list[str] = []
        self.window = None
        self._escolha_pendente = None
        self._modo_vigente_do_daemon = "desktop"
        self._mascara_vigente_do_daemon = "xbox"
        self._jogo_aberto = False
        self._home_guard = False
        self._home_mode_desc = _FakeLabel()
        self._home_mode_selector = _FakeSelector("desktop")
        self._home_flavor_selector = _FakeSelector("xbox")
        self._home_mode_selector.connect("changed", self._on_home_mode_changed)
        self._home_flavor_selector.connect("changed", self._on_home_flavor_changed)

    # --- superfícies que os handlers tocam e que não são o assunto daqui ---

    def _get(self, _widget_id: str) -> Any:
        return None

    def _status_toast(self, _contexto: str, msg: str) -> None:
        self.toasts.append(msg)

    def _refresh_gamepad_and_gamemode(self) -> None:
        return None

    def _refresh_home_tab(self) -> None:
        return None

    def _footer_toast(self, msg: str, _context: str = "footer") -> None:
        self.toasts.append(msg)

    def _reload_profiles_store(self, select_name: str | None = None) -> None:
        return None


def _ipc_que_confirma(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, dict[str, Any]]]:
    """IPC falso que SEMPRE confirma — grava as chamadas e chama on_success."""
    chamadas: list[tuple[str, dict[str, Any]]] = []

    def _fake(
        method: str,
        params: dict[str, Any] | None = None,
        on_success: Any = None,
        on_failure: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        chamadas.append((method, dict(params or {})))
        if on_success is not None:
            on_success({"status": "ok"})

    monkeypatch.setattr(ea, "call_async", _fake)
    monkeypatch.setattr(ha, "call_async", _fake)
    monkeypatch.setattr(mt, "call_async", _fake)
    # AGORA-E-DEPOIS-01: o "Aplicar" do rodapé manda o rascunho por outro
    # cano (`footer_actions.ipc_bridge`) — sem cobri-lo, o gesto novo da aba
    # Início falaria com o daemon de verdade no meio do teste.
    monkeypatch.setattr(fa.ipc_bridge, "call_async", _fake)
    return chamadas


def _ipc_que_falha(monkeypatch: pytest.MonkeyPatch) -> None:
    """IPC falso que SEMPRE falha (daemon desligado)."""

    def _fake(
        method: str,
        params: dict[str, Any] | None = None,
        on_success: Any = None,
        on_failure: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        if on_failure is not None:
            on_failure(RuntimeError("daemon desligado"))

    monkeypatch.setattr(ea, "call_async", _fake)
    monkeypatch.setattr(ha, "call_async", _fake)
    monkeypatch.setattr(mt, "call_async", _fake)
    # AGORA-E-DEPOIS-01: o "Aplicar" do rodapé manda o rascunho por outro
    # cano (`footer_actions.ipc_bridge`) — sem cobri-lo, o gesto novo da aba
    # Início falaria com o daemon de verdade no meio do teste.
    monkeypatch.setattr(fa.ipc_bridge, "call_async", _fake)


def _ipc_envenenado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Qualquer IPC daqui para a frente REPROVA o teste.

    É a prova de que REGISTRAR não é APLICAR (HARM-05): o escritor do rascunho
    não pode encostar no daemon.
    """

    def _bomba(*args: Any, **kwargs: Any) -> None:
        raise AssertionError(
            "o escritor do rascunho disparou IPC — registrar NÃO é aplicar "
            f"(HARM-05); chamada: {args!r} {kwargs!r}"
        )

    monkeypatch.setattr(ea, "call_async", _bomba)
    monkeypatch.setattr(ha, "call_async", _bomba)
    monkeypatch.setattr(mt, "call_async", _bomba)
    monkeypatch.setattr(mt, "apply_mode", _bomba)
    monkeypatch.setattr(fa.ipc_bridge, "call_async", _bomba)


# ---------------------------------------------------------------------------
# O modo e a máscara da aba Emulação
# ---------------------------------------------------------------------------


class TestAAbaEmulacaoEscreveNoRascunho:
    def test_clicar_dualsense_registra_a_mascara_e_o_salvar_persiste(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        janela = _Janela(_perfil("Pragmata", com_regra=True))
        _ipc_que_confirma(monkeypatch)

        janela.on_emulation_gamepad_dualsense(None)

        assert janela.draft.mode_dirty is True
        salvo = janela.draft.to_profile("Pragmata")
        assert salvo.mode is not None, "a aba Emulação não escreveu o modo"
        assert salvo.mode.kind == "gamepad"
        assert salvo.mode.gamepad_flavor == "dualsense"

    def test_clicar_desligado_registra_o_modo_desktop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """"Desligado" nesta aba É o modo "Controlar o PC" (o comentário do
        handler diz isso) — o perfil tem de nascer declarando desktop, não
        ``mode: null``."""
        janela = _Janela(_perfil("Navegação", com_regra=True))
        _ipc_que_confirma(monkeypatch)

        janela.on_emulation_gamepad_off(None)

        salvo = janela.draft.to_profile("Navegação")
        assert salvo.mode is not None and salvo.mode.kind == "desktop"
        assert salvo.mode.gamepad_flavor is None

    def test_daemon_desligado_nao_registra_nada(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O rascunho descreve o que FICOU de pé, não a intenção.

        Se o registro fosse no clique (e não na confirmação), um daemon morto
        deixaria o perfil dela dizendo um modo que nunca subiu.
        """
        janela = _Janela(_perfil("Pragmata", com_regra=True))
        _ipc_que_falha(monkeypatch)

        janela.on_emulation_gamepad_xbox(None)

        assert janela.draft.mode_dirty is False
        assert janela.draft.to_profile("Perfil Novo").mode is None


class TestAAbaInicioEscreveNoRascunho:
    def test_comutador_de_modo_registra_o_que_ela_escolheu(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AGORA-E-DEPOIS-01: o gesto tem dois tempos, e o registro é no segundo.

        O clique no seletor MARCA (e nada mais); o "Aplicar" do rodapé aplica e
        registra. A queixa dela que este teste guarda continua a mesma — *"salvei
        o perfil e as configs das outras abas não ficam salvas"* — e agora ela só
        estaria de volta se o caminho INTEIRO falhasse.
        """
        janela = _Janela(_perfil("Pragmata", com_regra=True))
        _ipc_que_confirma(monkeypatch)

        # O gesto real: clique no seletor emite "changed" com UM argumento.
        janela._home_mode_selector.set_active_id("native")
        assert janela.draft.to_profile("Pragmata").mode is None, (
            "o clique registrou sozinho — o rascunho voltou a guardar intenção "
            "em vez do que ficou de pé"
        )
        janela.on_apply_draft()

        salvo = janela.draft.to_profile("Pragmata")
        assert salvo.mode is not None and salvo.mode.kind == "native"

    def test_trocar_a_mascara_na_inicio_registra_gamepad_com_a_mascara(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        janela = _Janela(_perfil("Pragmata", com_regra=True))
        janela._home_mode_selector = _FakeSelector("gamepad")
        janela._modo_vigente_do_daemon = "gamepad"
        _ipc_que_confirma(monkeypatch)

        janela._home_flavor_selector.set_active_id("dualsense")
        janela.on_apply_draft()

        salvo = janela.draft.to_profile("Pragmata")
        assert salvo.mode is not None and salvo.mode.kind == "gamepad"
        assert salvo.mode.gamepad_flavor == "dualsense"

    def test_reconciliacao_do_poller_nao_conta_como_gesto(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``_render_home`` mexe nos seletores para refletir o daemon.

        Com o guard de pé isso NÃO é gesto dela — se contasse, o simples fato de
        a aba estar aberta marcaria o rascunho como editado e o modo do daemon
        entraria no perfil dela sem ninguém pedir.
        """
        janela = _Janela(_perfil("Pragmata", com_regra=True))
        _ipc_que_confirma(monkeypatch)
        janela._home_guard = True

        janela._home_mode_selector.set_active_id("gamepad")
        janela._home_flavor_selector.set_active_id("dualsense")

        assert janela.draft.mode_dirty is False

    def test_trocar_a_mascara_nao_mexe_no_resto_da_secao(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O que a janela não edita, ela não reescreve.

        Trocar a MÁSCARA é um gesto sobre UM campo. Se ele devolvesse o resto
        da seção `mode` ao default, mudaria o arquivo dela sem pedido — e é o
        defeito que esta classe inteira persegue.
        """
        janela = _Janela(
            _perfil(
                "Solo",
                com_regra=True,
                mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="xbox"),
            )
        )
        _ipc_que_confirma(monkeypatch)

        janela.on_emulation_gamepad_dualsense(None)

        salvo = janela.draft.to_profile("Solo")
        assert salvo.mode is not None
        assert salvo.mode.gamepad_flavor == "dualsense", "a máscara não trocou"
        assert salvo.mode.kind == "gamepad", (
            "a troca de máscara mexeu no `kind` — um gesto sobre um campo "
            "devolveu o vizinho ao default"
        )


# ---------------------------------------------------------------------------
# HARM-05: registrar NÃO é aplicar
# ---------------------------------------------------------------------------


class TestRegistrarNaoEAplicar:
    def test_os_escritores_do_rascunho_nao_encostam_no_daemon(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Com todo IPC envenenado, os três escritores ainda funcionam.

        É o cadeado do HARM-05. Se alguém "melhorar" o escritor fazendo-o aplicar
        junto, um toque num gatilho (que também escreve no rascunho) passaria a
        poder recriar o vpad ou suspender a emulação no meio da partida.
        """
        janela = _Janela(_perfil("Sackboy", com_regra=True))
        _ipc_envenenado(monkeypatch)

        ha.registrar_modo_no_rascunho(janela, "gamepad", "dualsense")
        ha.registrar_modo_no_rascunho(janela, "gamepad", "xbox")
        guardado = ea.registrar_modo_jogo_no_rascunho(janela, True)

        assert guardado is True
        salvo = janela.draft.to_profile("Sackboy")
        assert salvo.mode is not None and salvo.mode.gamepad_flavor == "xbox"
        assert salvo.suppress_desktop_emulation is True

    def test_o_aplicar_do_rodape_continua_sem_levar_modo_nem_modo_jogo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O outro lado do mesmo contrato (HARM-05, seção ``mouse``).

        Registrar no rascunho não pode fazer o "Aplicar" passar a empurrar modo e
        supressão pelo IPC — é o caminho por onde um gesto de gatilho recriaria o
        vpad no meio do jogo.
        """
        janela = _Janela(_perfil("Sackboy", com_regra=True))
        _ipc_que_confirma(monkeypatch)

        janela.on_emulation_gamepad_dualsense(None)
        janela.on_emulation_pause(None)

        payload = janela.draft.to_ipc_dict()
        assert "mode" not in payload
        assert "suppress_desktop_emulation" not in payload


class TestOEscritorNaoDependeDaMontagemDaJanela:
    """Dublê PARCIAL não pode quebrar por causa do escritor novo.

    MEDIDO: o `_HomeStub` de ``test_auto01_um_clique_em_vez_de_dez`` copia
    handlers avulsos da Início (sem o resto da classe e sem `draft`). Chamada
    entre mixins quebra esse dublê — a onda 2 já pagou esse preço uma vez. Por
    isso o escritor é FUNÇÃO de módulo e o rascunho vem por ``getattr``.
    """

    def test_janela_sem_rascunho_nao_estoura(self) -> None:
        class _JanelaCrua:
            pass

        crua = _JanelaCrua()
        ha.registrar_modo_no_rascunho(crua, "gamepad", "xbox")
        assert ea.registrar_modo_jogo_no_rascunho(crua, True) is False
        assert not hasattr(crua, "draft")


class TestOsMiolosPuros:
    def test_modo_desconhecido_nao_registra_lixo(self) -> None:
        draft = DraftConfig.from_profile(_perfil("Pragmata", com_regra=True))
        assert ha.rascunho_com_modo(draft, kind="modo_que_nao_existe") is draft

    def test_sem_rascunho_o_escritor_e_um_no_op(self) -> None:
        assert ha.rascunho_com_modo(None, kind="gamepad") is None
        assert ea.rascunho_com_modo_jogo(None, True) == (None, False)

    def test_mascara_desconhecida_vira_none_em_vez_de_recriar_o_vpad(self) -> None:
        """MODO-01: máscara que ninguém reconhece significa "mantém a atual"."""
        draft = DraftConfig.from_profile(_perfil("Pragmata", com_regra=True))
        novo = ha.rascunho_com_modo(draft, kind="gamepad", flavor="playstation-6")
        assert novo is not None
        assert novo.to_profile("Pragmata").mode is not None
        assert novo.to_profile("Pragmata").mode.gamepad_flavor is None  # type: ignore[union-attr]

    def test_a_frase_do_modo_jogo_so_ressalva_o_ligar_sem_regra(self) -> None:
        """O miolo puro da frase (MODO-JOGO-VONTADE-DELA-01), nos quatro casos."""
        padrao = "Modo jogo ligado"
        assert (
            ea.frase_do_modo_jogo(padrao, ligado=True, guardado=True, tem_regra=False)
            == ea.MODO_JOGO_GUARDADO_SEM_REGRA
        )
        assert (
            ea.frase_do_modo_jogo(padrao, ligado=True, guardado=True, tem_regra=True)
            == padrao
        )
        # Sem rascunho não há perfil para guardar nem promessa a desmentir.
        assert (
            ea.frase_do_modo_jogo(padrao, ligado=True, guardado=False, tem_regra=False)
            == padrao
        )
        assert (
            ea.frase_do_modo_jogo(padrao, ligado=False, guardado=True, tem_regra=False)
            == padrao
        )

    def test_o_catch_all_guarda_no_miolo_puro(self) -> None:
        """``rascunho_com_modo_jogo`` não recusa mais — nem no ligar.

        A recusa morava exatamente aqui (um ``if ligado and not
        perfil_do_rascunho_tem_opiniao(draft)``), e é o miolo que o resto da aba
        usa. Sem esta linha, o teste de handler acima é o único a morder.
        """
        catch_all = DraftConfig.from_profile(_perfil("vitoria", com_regra=False))

        novo, guardado = ea.rascunho_com_modo_jogo(catch_all, True)

        assert guardado is True
        assert novo is not None
        assert novo.to_profile("vitoria").suppress_desktop_emulation is True

    def test_o_predicado_de_opiniao_espelha_o_do_daemon(self) -> None:
        """Mesmo veredito do ``Profile.e_catch_all`` (R-01), nos três formatos."""
        com_regra = DraftConfig.from_profile(_perfil("Sackboy", com_regra=True))
        catch_all = DraftConfig.from_profile(_perfil("vitoria", com_regra=False))
        criteria_vazio = DraftConfig.from_profile(
            Profile(name="coop_local", match=MatchCriteria())
        )
        assert ea.perfil_do_rascunho_tem_opiniao(com_regra) is True
        assert ea.perfil_do_rascunho_tem_opiniao(catch_all) is False
        assert ea.perfil_do_rascunho_tem_opiniao(criteria_vazio) is False
        assert ea.perfil_do_rascunho_tem_opiniao(DraftConfig.default()) is False
