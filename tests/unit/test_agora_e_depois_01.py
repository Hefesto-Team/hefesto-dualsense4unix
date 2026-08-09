"""AGORA E DEPOIS — a escolha dela para de voltar sozinha, e o clique para de aplicar.

AGORA-E-DEPOIS-01 (08/08/2026). A aba Início misturava **dois tempos verbais**
com a mesma aparência: o que vale AGORA (cor, brilho, gatilho, vibração — o
daemon é o dono) e o que só vale QUANDO O JOGO ABRIR (o modo e a máscara — ela é
a dona). O jogo lê a configuração UMA VEZ, na abertura
(``assets/hefesto-launch.sh``, ``exec env "$@"``), então mexer nesses dois com o
jogo em curso não o alcança — e mexer no vpad ao vivo invalida os handles que
ele já abriu. Todo defeito da noite de 08/08 nasceu de aplicar o DEPOIS como se
fosse AGORA: uma partida sem controle nenhum, um "Jogador 3" fantasma e três
curas revertidas.

O QUE CADA GRUPO DESTE ARQUIVO TRAVA
====================================
1. **a guarda do valor** — com escolha pendente, os tiques do `_render_home`
   (a cada 2 s) não sobrescrevem o que ela escolheu. Sem isto o desenho inteiro
   cai: a escolha dela voltava sozinha antes de ela alcançar o "Aplicar";
2. **o clique não aplica** — nenhum IPC sai de um seletor da aba Início;
3. **a linha do pendente** — a única prova de que o clique registrou;
4. **o "Aplicar" aplica os dois tempos** — e pergunta UMA vez, só onde a
   decisão está completa.

E trava também as DECISÕES DELA de 08/08 à noite, que são o que separa este
desenho de um parecido e errado: a caixa da máscara continua obedecendo ao
daemon (decisão 2), o modo não pergunta (decisão 1) e o rascunho só recebe o
modo quando o Aplicar confirma (decisão 3).
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi`, como no
# `test_footer_actions` — o rodapé puxa `gui_dialogs` no topo do módulo.
exigir_gi_real("AGORA-E-DEPOIS-01: a escolha pendente")

import sys
import types
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.app.actions import (
    daemon_actions,
    footer_actions,
    home_actions,
    mode_transition,
    relancar,
)
from hefesto_dualsense4unix.app.actions.footer_actions import FooterActionsMixin
from hefesto_dualsense4unix.app.actions.home_actions import HomeActionsMixin
from hefesto_dualsense4unix.app.draft_config import DraftConfig

# ---------------------------------------------------------------------------
# Dublês
# ---------------------------------------------------------------------------


class _StyleCtx:
    def __init__(self) -> None:
        self.classes: list[str] = []

    def add_class(self, name: str) -> None:
        if name not in self.classes:
            self.classes.append(name)

    def remove_class(self, name: str) -> None:
        if name in self.classes:
            self.classes.remove(name)


class _FakeWidget:
    """O subconjunto de `Gtk` que o `_render_home` toca.

    ``active_id`` e ``visible`` são guardados porque são exatamente o que estes
    testes observam: "o seletor mostra o quê?" e "a linha está na tela?".
    """

    def __init__(self, label: str | None = None, **_kwargs: object) -> None:
        self.label = label
        self.children: list[_FakeWidget] = []
        self.style = _StyleCtx()
        self.sensitive = True
        self.visible = True
        self.active_id: str | None = None

    def get_style_context(self) -> _StyleCtx:
        return self.style

    def set_xalign(self, _value: float) -> None:
        pass

    def set_margin_end(self, _value: int) -> None:
        pass

    def set_markup(self, markup: str) -> None:
        self.label = markup

    def set_text(self, text: str) -> None:
        self.label = text

    def set_label(self, text: str) -> None:
        self.label = text

    def get_label(self) -> str:
        return str(self.label or "")

    def get_text(self) -> str:
        return str(self.label or "")

    def get_active_id(self) -> str | None:
        return self.active_id

    def set_sensitive(self, value: bool) -> None:
        self.sensitive = value

    def set_visible(self, value: bool) -> None:
        self.visible = value

    def set_no_show_all(self, _value: bool) -> None:
        pass

    def set_active(self, _value: bool) -> None:
        pass

    def set_active_id(self, value: str) -> None:
        self.active_id = value

    def pack_start(self, child: _FakeWidget, *_args: object) -> None:
        self.children.append(child)

    def get_children(self) -> list[_FakeWidget]:
        return list(self.children)

    def remove(self, child: _FakeWidget) -> None:
        self.children.remove(child)

    def show_all(self) -> None:
        pass


class _Janela:
    """A aba Início com os widgets falsos — render E handlers na mesma casca.

    Junta o que os dublês antigos separavam (`test_home_render_state` só
    renderiza, `test_home_actions_handlers` só clica) porque o defeito que este
    arquivo persegue mora exatamente no ENCONTRO dos dois: o clique marca, o
    tique seguinte reescreve.
    """

    _render_home = HomeActionsMixin._render_home
    _render_home_controllers = HomeActionsMixin._render_home_controllers
    _on_home_mode_changed = HomeActionsMixin._on_home_mode_changed
    _on_home_flavor_changed = HomeActionsMixin._on_home_flavor_changed

    def __init__(self) -> None:
        self._home_installed = True
        self._home_inflight = False
        self._home_guard = False
        self._escolha_pendente: dict[str, str] | None = None
        self._modo_vigente_do_daemon: str | None = None
        self._mascara_vigente_do_daemon: str | None = None
        self._home_controllers_box = _FakeWidget()
        self._home_mode_selector = _FakeWidget()
        self._home_players_hint = _FakeWidget()
        self._home_flavor_selector = _FakeWidget()
        self._home_flavor_custo = _FakeWidget()
        self._home_mode_desc = _FakeWidget()
        self._home_origin_label = _FakeWidget()
        self._home_session_label = _FakeWidget()
        self._home_gamepad_opts = _FakeWidget()
        self._home_pendente_label = _FakeWidget()
        self._home_vpad_banner = _FakeWidget()
        self._home_wrapper_banner = _FakeWidget()
        self._home_shutdown_btn = _FakeWidget()
        self._home_offline = False
        self._home_reconciliar_btn = _FakeWidget()
        self._home_reconciliar_hint = _FakeWidget()
        self.toasts: list[str] = []

    def _status_toast(self, _contexto: str, msg: str) -> None:
        self.toasts.append(msg)

    def _refresh_home_tab(self) -> None:
        pass


@pytest.fixture()
def fake_gtk(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = types.ModuleType("gi.repository")
    repo.Gtk = SimpleNamespace(  # type: ignore[attr-defined]
        Label=_FakeWidget,
        Box=_FakeWidget,
        Orientation=SimpleNamespace(VERTICAL=0, HORIZONTAL=1),
    )
    monkeypatch.setitem(sys.modules, "gi.repository", repo)


@pytest.fixture()
def sem_ipc(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    """Grava toda chamada IPC dos dois módulos que a aba Início usava.

    Cobrir `home_actions` E `mode_transition` é o que dá valor ao teste do
    passo 2: a troca de modo saía por `mode_transition.call_async`, e olhar só
    um dos dois deixaria metade do caminho sem vigia.
    """
    chamadas: list[tuple[str, dict[str, Any]]] = []

    def _fake(
        method: str,
        params: dict[str, Any] | None = None,
        _done: Any = None,
        _fail: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        chamadas.append((method, dict(params or {})))

    monkeypatch.setattr(home_actions, "call_async", _fake)
    monkeypatch.setattr(mode_transition, "call_async", _fake)
    return chamadas


def _estado(
    *, modo: str = "gamepad", mascara: str = "dualsense", jogo: bool = False
) -> dict[str, Any]:
    return {
        "gamepad_emulation": {"enabled": modo == "gamepad", "flavor": mascara},
        "native_mode": modo == "native",
        "controllers": [
            {"index": 0, "connected": True, "transport": "usb", "is_primary": True}
        ],
        "game_signal": {"authority": "game" if jogo else "daemon"},
    }


# ---------------------------------------------------------------------------
# 1. A guarda do valor (passo 1)
# ---------------------------------------------------------------------------


class TestAEscolhaDelaNaoVoltaSozinha:
    def test_dois_tiques_seguidos_nao_mexem_no_que_o_seletor_mostra(
        self, fake_gtk: None
    ) -> None:
        """O teste do plano, literal — e o coração do desenho.

        ARRANQUE A GUARDA (faça `_render_home` escrever sempre o modo do daemon)
        e este teste REPROVA: o poller roda a cada 2 s, e a escolha dela voltaria
        para "Jogar pelo Hefesto" antes de ela alcançar o botão "Aplicar".
        """
        janela = _Janela()
        janela._render_home(_estado(modo="gamepad"))
        janela._home_mode_selector.set_active_id("desktop")
        janela._on_home_mode_changed(janela._home_mode_selector)

        janela._render_home(_estado(modo="gamepad"))
        janela._render_home(_estado(modo="gamepad"))

        assert janela._home_mode_selector.active_id == "desktop", (
            "o tique do daemon reescreveu a escolha dela — é o defeito que "
            "derrubou a cura óbvia do defeito 2 da OITO-DEFEITOS-01."
        )

    def test_a_mascara_escolhida_tambem_resiste_ao_tique(
        self, fake_gtk: None
    ) -> None:
        janela = _Janela()
        janela._render_home(_estado(mascara="dualsense"))
        janela._home_flavor_selector.set_active_id("xbox")
        janela._on_home_flavor_changed(janela._home_flavor_selector)

        janela._render_home(_estado(mascara="dualsense"))

        assert janela._home_flavor_selector.active_id == "xbox"

    def test_sem_pendencia_a_caixa_continua_ecoando_o_daemon(
        self, fake_gtk: None
    ) -> None:
        """O contrapeso, e ele é obrigatório.

        Uma guarda que congela a aba trocaria um defeito por outro pior: a
        janela deixaria de mostrar o que está valendo. Sem pendência, o daemon
        manda — a AUTO-01.3 continua de pé.
        """
        janela = _Janela()

        janela._render_home(_estado(modo="native", mascara="xbox"))

        assert janela._home_mode_selector.active_id == "native"
        assert janela._home_flavor_selector.active_id == "xbox"

    def test_a_caixa_da_mascara_continua_obedecendo_ao_daemon(
        self, fake_gtk: None
    ) -> None:
        """Decisão 2 dela (08/08, noite): a VISIBILIDADE não é guardada.

        Ela escolheu, entre duas saídas com o preço na mesa, pagar dois
        "Aplicar" (um por decisão) em vez de ganhar mais uma guarda. Com o modo
        pendente em "Jogar pelo Hefesto" e o daemon ainda em desktop, a linha da
        máscara **não** aparece — ela só nasce quando o modo está VALENDO.

        Isto está travado de propósito: parece descuido, e a próxima pessoa vai
        querer "consertar". Se for para mudar, muda com ela, não por dedução.
        """
        janela = _Janela()
        janela._render_home(_estado(modo="desktop"))
        janela._home_mode_selector.set_active_id("gamepad")
        janela._on_home_mode_changed(janela._home_mode_selector)

        janela._render_home(_estado(modo="desktop"))

        assert janela._home_gamepad_opts.visible is False, (
            "a caixa da máscara passou a seguir a escolha pendente — isso "
            "contraria a decisão 2 dela de 08/08."
        )

    def test_o_custo_mostrado_e_o_da_mascara_que_ela_escolheu(
        self, fake_gtk: None
    ) -> None:
        """MASCARA-CUSTO-01 continua respondendo a pergunta certa.

        O preço embaixo do seletor existe para ela decidir ANTES de clicar. Com
        uma máscara pendente, mostrar o custo da vigente responderia sobre a
        máscara que ela está deixando para trás.
        """
        janela = _Janela()
        janela._render_home(_estado(mascara="dualsense"))
        janela._home_flavor_selector.set_active_id("xbox")
        janela._on_home_flavor_changed(janela._home_flavor_selector)

        janela._render_home(_estado(mascara="dualsense"))

        esperado = home_actions.texto_do_custo_da_mascara("xbox")
        assert janela._home_flavor_custo.label == esperado

    def test_quando_o_daemon_alcanca_a_escolha_a_pendencia_some(
        self, fake_gtk: None
    ) -> None:
        """A pendência é uma DIVERGÊNCIA, não uma marca permanente.

        Se o daemon chegou ao que ela escolheu — por esta janela, pela CLI, pelo
        applet ou por troca de perfil —, não há mais nada a aplicar. Sem esta
        reconciliação a linha "vai mudar para:" ficaria acesa prometendo uma
        mudança que já aconteceu.
        """
        janela = _Janela()
        janela._render_home(_estado(modo="gamepad"))
        janela._home_mode_selector.set_active_id("desktop")
        janela._on_home_mode_changed(janela._home_mode_selector)
        assert janela._escolha_pendente == {"modo": "desktop"}

        janela._render_home(_estado(modo="desktop"))

        assert janela._escolha_pendente is None
        assert janela._home_pendente_label.visible is False

    def test_daemon_desligado_esconde_a_linha_e_preserva_a_escolha(
        self, fake_gtk: None
    ) -> None:
        """Offline não é "ela desistiu".

        Sem daemon não há como aplicar, então a linha sai da tela — mas apagar a
        ESCOLHA num engasgo de IPC perderia o que ela acabou de decidir, e ela
        teria de refazer sem nunca saber por quê.
        """
        janela = _Janela()
        janela._render_home(_estado(modo="gamepad"))
        janela._home_mode_selector.set_active_id("desktop")
        janela._on_home_mode_changed(janela._home_mode_selector)

        janela._render_home(None)

        assert janela._home_pendente_label.visible is False
        assert janela._escolha_pendente == {"modo": "desktop"}


# ---------------------------------------------------------------------------
# 2. O clique não aplica (passo 2)
# ---------------------------------------------------------------------------


class TestOCliqueSoMarca:
    def test_clicar_no_modo_nao_produz_ipc_nenhum(
        self, fake_gtk: None, sem_ipc: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """O teste do passo 2, literal.

        ARRANQUE A CURA (devolva o `apply_mode` ao handler) e este teste
        REPROVA. Era a segunda metade do defeito 2 dela: *"clicar em dualsense
        ainda pede pra aplicar agora, ao invés de ser só no botão aplicar"*.
        """
        janela = _Janela()
        janela._render_home(_estado(modo="gamepad"))
        sem_ipc.clear()

        janela._home_mode_selector.set_active_id("native")
        janela._on_home_mode_changed(janela._home_mode_selector)

        assert sem_ipc == [], (
            f"o clique no seletor de modo ainda fala com o daemon: {sem_ipc}"
        )

    def test_clicar_na_mascara_nao_produz_ipc_nenhum(
        self, fake_gtk: None, sem_ipc: list[tuple[str, dict[str, Any]]]
    ) -> None:
        janela = _Janela()
        janela._render_home(_estado(modo="gamepad", mascara="dualsense"))
        sem_ipc.clear()

        janela._home_flavor_selector.set_active_id("xbox")
        janela._on_home_flavor_changed(janela._home_flavor_selector)

        assert sem_ipc == []

    def test_o_clique_marca_a_escolha_com_a_aridade_real_do_sinal(
        self, fake_gtk: None
    ) -> None:
        """BUG-HOME-SEGMENTED-SIGNATURE-01 continua travado.

        O sinal "changed" do `SegmentedSelector` chega SEM argumentos (como o
        `GtkComboBox`): o handler recebe só o widget e lê `get_active_id()`. Um
        handler que peça um segundo argumento faz o PyGObject engolir o
        `TypeError` — os botões mudam de visual e nada acontece, em silêncio.
        """
        janela = _Janela()
        janela._render_home(_estado(modo="gamepad", mascara="dualsense"))

        janela._home_flavor_selector.set_active_id("xbox")
        janela._on_home_flavor_changed(janela._home_flavor_selector)
        janela._home_mode_selector.set_active_id("native")
        janela._on_home_mode_changed(janela._home_mode_selector)

        assert janela._escolha_pendente == {"mascara": "xbox", "modo": "native"}

    def test_fora_de_jogar_pelo_hefesto_a_mascara_nao_marca_nada(
        self, fake_gtk: None
    ) -> None:
        """A máscara só existe DENTRO de "Jogar pelo Hefesto".

        O gate lê o seletor de modo — que, com pendência, mostra a escolha dela.
        Quem marcou "Controlar o PC" e ainda não aplicou não está escolhendo
        máscara nenhuma, e gravar uma pendência ali faria o "Aplicar" mandar uma
        máscara para um modo que não a tem.
        """
        janela = _Janela()
        janela._render_home(_estado(modo="gamepad", mascara="dualsense"))
        janela._home_mode_selector.set_active_id("desktop")
        janela._on_home_mode_changed(janela._home_mode_selector)

        janela._home_flavor_selector.set_active_id("xbox")
        janela._on_home_flavor_changed(janela._home_flavor_selector)

        assert janela._escolha_pendente == {"modo": "desktop"}

    def test_o_guard_do_render_nao_vira_escolha_dela(self, fake_gtk: None) -> None:
        """O `_home_guard` continua indispensável — e não foi substituído.

        É ele que impede o `set_active_id` do próprio `_render_home` de entrar
        no handler como se fosse clique: sem ele, cada tique gravaria uma
        "pendência" e a janela inventaria decisões que ninguém tomou.
        """
        janela = _Janela()
        janela._home_guard = True
        janela._home_mode_selector.set_active_id("native")

        janela._on_home_mode_changed(janela._home_mode_selector)

        assert janela._escolha_pendente is None

    def test_voltar_ao_que_ja_esta_valendo_desfaz_a_pendencia(
        self, fake_gtk: None
    ) -> None:
        """Escolher o que já vale não é pendência — e o rodapé diz isso.

        Sem esta volta, clicar "desktop" e depois "gamepad" de novo deixaria uma
        pendência igual ao vigente: o "Aplicar" dispararia uma transição para
        onde o sistema já está, e a linha prometeria uma mudança inexistente.
        """
        janela = _Janela()
        janela._render_home(_estado(modo="gamepad"))
        janela._home_mode_selector.set_active_id("desktop")
        janela._on_home_mode_changed(janela._home_mode_selector)

        janela._home_mode_selector.set_active_id("gamepad")
        janela._on_home_mode_changed(janela._home_mode_selector)

        assert janela._escolha_pendente is None
        assert janela.toasts[-1] == relancar.TOAST_ESCOLHA_DESFEITA


# ---------------------------------------------------------------------------
# 3. A linha do pendente (passo 3)
# ---------------------------------------------------------------------------


class TestALinhaDoPendente:
    def test_a_frase_pura_compoe_os_dois_campos(self) -> None:
        assert relancar.texto_do_pendente() == ""
        so_modo = relancar.texto_do_pendente(modo="Jogar pelo Hefesto")
        assert "vai mudar para" in so_modo and "Jogar pelo Hefesto" in so_modo
        dois = relancar.texto_do_pendente(
            modo="Jogar pelo Hefesto", mascara="DualSense (botões PlayStation)"
        )
        assert "Jogar pelo Hefesto" in dois and "DualSense" in dois

    def test_a_frase_usa_o_lexico_da_tela_e_nao_os_ids(
        self, fake_gtk: None
    ) -> None:
        """Ela recusa nome que não deriva do que já existe na janela.

        "gamepad"/"xbox" são ids internos — palavras que não aparecem em botão
        nenhum. A linha ecoa o rótulo que ela acabou de clicar.
        """
        janela = _Janela()
        janela._render_home(_estado(modo="desktop", mascara="dualsense"))
        janela._home_mode_selector.set_active_id("gamepad")
        janela._on_home_mode_changed(janela._home_mode_selector)

        texto = str(janela._home_pendente_label.label)
        assert "Jogar pelo Hefesto" in texto
        assert "gamepad" not in texto

    def test_a_linha_acende_no_clique_e_apaga_sem_pendencia(
        self, fake_gtk: None
    ) -> None:
        """Sem esta linha o plano vira defeito.

        Com o clique não aplicando mais, ela é a ÚNICA prova de que o gesto
        registrou: a pessoa clica, nada acontece na hora, e sem o rótulo conclui
        que a janela ignorou o clique.
        """
        janela = _Janela()
        janela._render_home(_estado(modo="gamepad"))
        assert janela._home_pendente_label.visible is False

        janela._home_mode_selector.set_active_id("desktop")
        janela._on_home_mode_changed(janela._home_mode_selector)

        assert janela._home_pendente_label.visible is True
        assert janela.toasts[-1] == relancar.TOAST_ESCOLHA_ANOTADA


# ---------------------------------------------------------------------------
# 4. O "Aplicar" aplica o DEPOIS também (passo 4)
# ---------------------------------------------------------------------------


class _Dialogo:
    """Captura o diálogo em vez de abri-lo, e deixa o teste responder por ela."""

    def __init__(self) -> None:
        self.aberto = False
        self.botoes: list[str] = []
        self._on_response: Any = None

    def construir(
        self,
        _parent: Any,
        *,
        titulo: str,
        corpo: str,
        botoes: list[tuple[str, int]],
        on_response: Any,
        destrutivo: int | None = None,
    ) -> Any:
        self.aberto = True
        self.titulo = titulo
        self.corpo = corpo
        self.botoes = [rotulo for rotulo, _ in botoes]
        self._on_response = on_response
        return MagicMock()

    def responder(self, resposta: int) -> None:
        assert self._on_response is not None, "o diálogo não chegou a abrir"
        self._on_response(MagicMock(), resposta)


class _Rodape(FooterActionsMixin):
    """O rodapé com o mínimo da aba Início que ele lê — como na classe real.

    `HefestoApp` junta os dois mixins; aqui o dublê faz o mesmo, porque o passo
    4 existe justamente no ponto onde eles se encontram.
    """

    def __init__(self, *, jogo_aberto: bool = False) -> None:
        self.draft = DraftConfig.default()
        self.window = None
        self._toasted: list[str] = []
        self._escolha_pendente: dict[str, str] | None = None
        self._modo_vigente_do_daemon: str | None = "gamepad"
        self._mascara_vigente_do_daemon: str | None = "dualsense"
        self._jogo_aberto = jogo_aberto
        self._home_pendente_label = _FakeWidget()
        builder = MagicMock()
        builder.get_object.return_value = MagicMock()
        self.builder = builder

    def _footer_toast(self, msg: str, context: str = "footer") -> None:
        self._toasted.append(msg)

    def _reload_profiles_store(self, select_name: str | None = None) -> None:
        pass


@pytest.fixture()
def ipc_do_rodape(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, dict[str, Any]]]:
    """Grava o que sai pelos DOIS canos do "Aplicar": a transição e o rascunho.

    O `apply_draft` sai por `footer_actions.ipc_bridge.call_async`; a transição,
    por `mode_transition.call_async`. Só olhando os dois é possível afirmar a
    ORDEM — e a ordem é metade da entrega.
    """
    chamadas: list[tuple[str, dict[str, Any]]] = []

    def _transicao(
        method: str,
        params: dict[str, Any] | None = None,
        on_done: Any = None,
        _on_fail: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        chamadas.append((method, dict(params or {})))
        if on_done is not None:
            on_done({"status": "ok"})

    def _draft(
        method: str,
        params: dict[str, Any] | None = None,
        on_success: Any = None,
        on_failure: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        chamadas.append((method, {}))
        if on_success is not None:
            on_success({"status": "ok", "applied": ["leds"]})

    monkeypatch.setattr(mode_transition, "call_async", _transicao)
    monkeypatch.setattr(footer_actions.ipc_bridge, "call_async", _draft)
    return chamadas


class TestOBotaoVerdeAplicaOsDoisTempos:
    def test_sem_pendencia_o_aplicar_e_exatamente_o_de_sempre(
        self, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """O caminho comum não pode ter ganhado peso nenhum."""
        rodape = _Rodape()

        rodape.on_apply_draft()

        assert [m for m, _ in ipc_do_rodape] == ["profile.apply_draft"]

    def test_com_pendencia_e_sem_jogo_a_transicao_vem_antes_do_rascunho(
        self, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """A ordem importa: o DEPOIS primeiro, o AGORA emendado no sucesso.

        ARRANQUE A CURA (volte o `on_apply_draft` a mandar só o rascunho) e este
        teste REPROVA — era o defeito 1 dela: *"quando eu clico ali no inferior
        no verde em aplicar, ele não aplica"*. O payload do rascunho não carrega
        modo nem máscara por contrato.
        """
        rodape = _Rodape()
        rodape._escolha_pendente = {"mascara": "xbox"}

        rodape.on_apply_draft()

        metodos = [m for m, _ in ipc_do_rodape]
        assert "gamepad.emulation.set" in metodos
        assert metodos.index("gamepad.emulation.set") < metodos.index(
            "profile.apply_draft"
        )
        assert rodape._escolha_pendente is None

    def test_a_transicao_declara_que_o_gesto_e_dela(
        self, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """ORIGEM-QUE-MENTE-01: silêncio no protocolo significa "automático".

        E automático não fura o portão da allowlist do Steam Input — foi assim
        que o botão "Jogar pelo Hefesto" parou de funcionar na máquina dela com
        o Sackboy marcado. O clique dela vira pedido AQUI agora, então é daqui
        que a declaração tem de sair.
        """
        rodape = _Rodape()
        rodape._escolha_pendente = {"mascara": "xbox"}

        rodape.on_apply_draft()

        params = dict(ipc_do_rodape[0][1])
        for metodo, p in ipc_do_rodape:
            if metodo == "gamepad.emulation.set":
                params = dict(p)
        assert params.get("origin") == "manual"
        assert params.get("flavor") == "xbox"

    def test_o_modo_entra_no_rascunho_so_quando_o_aplicar_confirma(
        self, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """Decisão 3 dela (08/08, noite).

        O registro morava no callback do clique; com o clique não aplicando
        mais, ninguém o chamaria — e "Salvar este perfil" passaria a gravar
        perfil SEM a seção `mode`, em silêncio. E ele continua vindo DEPOIS da
        confirmação: o rascunho descreve o que ficou de pé, não uma intenção.
        """
        rodape = _Rodape()
        rodape._escolha_pendente = {"modo": "desktop"}
        assert rodape.draft.to_profile("Perfil").mode is None

        rodape.on_apply_draft()

        salvo = rodape.draft.to_profile("Perfil")
        assert salvo.mode is not None, (
            "o modo não entrou no rascunho — 'Salvar este perfil' gravaria um "
            "perfil SEM a seção mode, em silêncio."
        )
        assert salvo.mode.kind == "desktop"

    def test_falha_na_transicao_preserva_a_escolha_dela(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A pendência FICA quando a transição falha.

        Apagá-la aqui faria a linha "vai mudar para:" sumir sem que nada tivesse
        mudado — a janela mentindo por omissão, no pior momento possível.
        """

        def _falha(
            _method: str,
            _params: dict[str, Any] | None = None,
            _on_done: Any = None,
            on_fail: Any = None,
            timeout_s: float = 0.25,
        ) -> None:
            if on_fail is not None:
                on_fail(RuntimeError("daemon mudo"))

        monkeypatch.setattr(mode_transition, "call_async", _falha)
        rodape = _Rodape()
        rodape._escolha_pendente = {"mascara": "xbox"}

        rodape.on_apply_draft()

        assert rodape._escolha_pendente == {"mascara": "xbox"}


class TestODialogoPerguntaUmaVezSoENoLugarCerto:
    @pytest.fixture()
    def dialogo(self, monkeypatch: pytest.MonkeyPatch) -> _Dialogo:
        dobro = _Dialogo()
        monkeypatch.setattr(
            daemon_actions, "build_consentimento_dialog", dobro.construir
        )
        return dobro

    def test_com_jogo_aberto_e_mascara_pendente_pergunta_e_nao_dispara_nada(
        self, dialogo: _Dialogo, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """O teste do plano, literal — e o cenário dela.

        Ela vai ao Hefesto no meio da partida, troca a máscara e clica em
        Aplicar. O diálogo pergunta UMA vez, com as três saídas, e **nada** sai
        antes da resposta: nem a transição (que recriaria o vpad embaixo do jogo)
        nem o rascunho.
        """
        rodape = _Rodape(jogo_aberto=True)
        rodape._escolha_pendente = {"mascara": "xbox"}

        rodape.on_apply_draft()

        assert dialogo.aberto is True
        assert ipc_do_rodape == [], (
            f"algo saiu antes de ela responder: {ipc_do_rodape}"
        )
        assert dialogo.botoes == [
            relancar.ROTULO_CANCELAR,
            relancar.ROTULO_DEPOIS,
            relancar.ROTULO_FECHAR,
        ]

    def test_com_jogo_aberto_e_so_o_modo_pendente_aplica_sem_perguntar(
        self, dialogo: _Dialogo, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """Decisão dela, mantida em 08/08 à noite (RELANCAR-ORDEM-01).

        Só a máscara pergunta. O preço está declarado no plano (§9, decisão 1) e
        foi aceito com ele na mesa: o caminho do "Jogador 3" fantasma continua
        alcançável por aqui, e a cura dele é a JOGADOR-3-FANTASMA-01 — impedir o
        estado meio-a-meio —, não mais um diálogo.

        Este teste existe para que ninguém "feche o caso" pondo `"modo"` de
        volta em `EXIGEM_RELANCAR` sem falar com ela.
        """
        rodape = _Rodape(jogo_aberto=True)
        rodape._escolha_pendente = {"modo": "desktop"}

        rodape.on_apply_draft()

        assert dialogo.aberto is False
        assert [m for m, _ in ipc_do_rodape][:1] == ["native.mode.set"]

    def test_cancelar_nao_aplica_nada_nem_o_rascunho(
        self, dialogo: _Dialogo, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """O toast do cancelar promete que NADA mudou.

        Mandar as sete seções do rascunho depois dele faria da promessa uma
        mentira — e a edição dela não se perde: continua no rascunho, a um
        clique de distância.
        """
        rodape = _Rodape(jogo_aberto=True)
        rodape._escolha_pendente = {"mascara": "xbox"}
        rodape.on_apply_draft()

        dialogo.responder(-6)  # Gtk.ResponseType.CANCEL

        assert ipc_do_rodape == []
        assert rodape._escolha_pendente == {"mascara": "xbox"}

    def test_aplicar_agora_dispara_a_transicao_e_o_rascunho(
        self,
        dialogo: _Dialogo,
        ipc_do_rodape: list[tuple[str, dict[str, Any]]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        relancado: list[bool] = []
        monkeypatch.setattr(
            _Rodape, "_relancar_o_jogo", lambda self: relancado.append(True)
        )
        rodape = _Rodape(jogo_aberto=True)
        rodape._escolha_pendente = {"mascara": "xbox"}
        rodape.on_apply_draft()

        dialogo.responder(rodape._RESP_FECHAR_E_ABRIR)

        metodos = [m for m, _ in ipc_do_rodape]
        assert "gamepad.emulation.set" in metodos
        assert "profile.apply_draft" in metodos
        assert relancado == [True]

    def test_na_proxima_abertura_nao_recria_o_vpad_mas_aplica_o_agora(
        self, dialogo: _Dialogo, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """As duas metades desta saída, e as duas já custaram caro.

        DEPOIS-QUE-APLICAVA-AGORA-01: "aplicar depois" chamava `aplicar()`
        incondicionalmente e, na máscara, isso RECRIAVA O VPAD ao vivo — a mesma
        coisa que "aplicar agora", sem fechar o jogo. Continua proibido.

        AGORA-E-DEPOIS-01: mas o "Aplicar" carrega SETE seções que mudam na hora
        (gatilhos, LEDs, rumble…). Adiar o que só vale na abertura não pode
        engolir em silêncio o que valia agora — e é para isso que existe o
        `ao_adiar`.
        """
        rodape = _Rodape(jogo_aberto=True)
        rodape._escolha_pendente = {"mascara": "xbox"}
        rodape.on_apply_draft()

        dialogo.responder(rodape._RESP_DEPOIS)

        metodos = [m for m, _ in ipc_do_rodape]
        assert "gamepad.emulation.set" not in metodos, (
            "o ramo 'na próxima abertura' recriou o vpad ao vivo — é o defeito "
            "DEPOIS-QUE-APLICAVA-AGORA-01 de volta."
        )
        assert metodos == ["profile.apply_draft"]

    def test_adiar_tira_a_linha_da_tela_para_ela_nao_contradizer_o_rodape(
        self, dialogo: _Dialogo, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """Enquanto não houver onde guardar, a tela não pode fingir que guardou.

        O toast desta saída diz *"Não mudei nada agora — refaça a escolha depois
        de fechar"*. Deixar a linha "vai mudar para:" acesa poria a tela
        contradizendo o rodapé, na mesma janela e no mesmo segundo.

        Quando o passo 6 do plano existir (a pendência gravada em disco,
        aplicada sozinha quando o jogo fechar), é ESTE teste que muda — junto
        com o `guardou=` do toast, e não antes dele.
        """
        rodape = _Rodape(jogo_aberto=True)
        rodape._escolha_pendente = {"mascara": "xbox"}
        rodape.on_apply_draft()

        dialogo.responder(rodape._RESP_DEPOIS)

        assert rodape._escolha_pendente is None
        assert rodape._home_pendente_label.visible is False
