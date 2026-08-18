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
desenho de um parecido e errado (§9 e §12 do plano):

* a caixa da máscara nasce com a ESCOLHA dela — clicou em "Jogar pelo Hefesto",
  a máscara aparece, e um "Aplicar" só resolve os dois;
* com jogo aberto, **modo e máscara** abrem o diálogo — a pergunta mora no
  "Aplicar", onde a decisão está completa;
* o rascunho só recebe o modo quando o Aplicar confirma;
* e nada disto depende de cabo, de Bluetooth ou de quantos controles há na mesa
  (grupo 5) — pedido dela: *"deve ser universal"*.
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

    def test_a_caixa_da_mascara_nasce_com_a_escolha_dela(
        self, fake_gtk: None
    ) -> None:
        """Decisão 2 dela, REVISTA em 08/08 à noite — vendo a tela.

        A primeira versão fazia a visibilidade obedecer ao daemon, e o efeito
        foi o pior possível: ela clicou em "Jogar pelo Hefesto", o botão acendeu
        e a caixa da máscara SUMIU (o daemon ainda estava em desktop). Ela viu e
        cortou: *"a máscara volta ao que era. Não temos que burocratizar aí.
        Clico hefesto, a máscara aparece, clico em jogar xbox ou dualsense e ao
        clicar em aplicar lá embaixo o efeito aplica de fato"*.

        ARRANQUE A CURA (faça esta linha ler o modo do DAEMON) e este teste
        REPROVA — e o "ué?" dela volta com ele.
        """
        janela = _Janela()
        janela._render_home(_estado(modo="desktop"))
        janela._home_mode_selector.set_active_id("gamepad")
        janela._on_home_mode_changed(janela._home_mode_selector)

        janela._render_home(_estado(modo="desktop"))

        assert janela._home_gamepad_opts.visible is True, (
            "a caixa da máscara sumiu depois de ela escolher 'Jogar pelo "
            "Hefesto' — é o defeito que ela viu na tela em 08/08."
        )

    def test_saindo_do_modo_jogo_a_caixa_da_mascara_some(
        self, fake_gtk: None
    ) -> None:
        """O contrapeso: seguir a escolha vale para os DOIS lados.

        Com o daemon em gamepad e ela escolhendo "Controlar o PC", a máscara
        deixa de fazer sentido na hora — não se escolhe como o jogo vê um
        controle que vai virar mouse.
        """
        janela = _Janela()
        janela._render_home(_estado(modo="gamepad"))
        janela._home_mode_selector.set_active_id("desktop")
        janela._on_home_mode_changed(janela._home_mode_selector)

        janela._render_home(_estado(modo="gamepad"))

        assert janela._home_gamepad_opts.visible is False

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

    def test_com_jogo_aberto_o_modo_sozinho_tambem_pergunta(
        self, dialogo: _Dialogo, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """Decisão 1 dela, REVISTA em 08/08 à noite — com a tela na frente.

        Ela tinha mantido a `RELANCAR-ORDEM-01` (só a máscara pergunta) quando a
        pergunta ainda nascia no clique do seletor. Com a pergunta morando no
        "Aplicar", onde modo E máscara já estão escolhidos, ela disse o que
        quer: *"se o jogo tiver aberto aparece o popup falando em fechar o jogo
        pra aplicar e afins. e isso vai permitir aplicar tudo que alterar em
        todas as abas"*.

        Isto fecha o caminho pelo qual o "Jogador 3" fantasma era alcançado sem
        aviso — trocar o modo com o jogo aberto mexe no `compose_env` ao vivo.
        A cura do estado meio-a-meio continua sendo a JOGADOR-3-FANTASMA-01;
        este diálogo é o que impede de chegar lá sem ela saber.
        """
        rodape = _Rodape(jogo_aberto=True)
        rodape._escolha_pendente = {"modo": "desktop"}

        rodape.on_apply_draft()

        assert dialogo.aberto is True, (
            "trocar o modo com o jogo aberto voltou a aplicar direto, sem "
            "perguntar — é o caminho do 'Jogador 3' fantasma."
        )
        assert ipc_do_rodape == [], "algo saiu antes de ela responder"

    def test_sem_jogo_aberto_nada_pergunta(
        self, dialogo: _Dialogo, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """O contrapeso do teste acima, e ele é obrigatório.

        O diálogo é caro — interrompe — e só se paga quando há um jogo para o
        qual a mudança não chegaria. Sem jogo aberto, o "Aplicar" aplica e
        pronto, como sempre fez.
        """
        rodape = _Rodape(jogo_aberto=False)
        rodape._escolha_pendente = {"modo": "desktop", "mascara": "xbox"}

        rodape.on_apply_draft()

        assert dialogo.aberto is False
        assert [m for m, _ in ipc_do_rodape][:1] == ["native.mode.set"]

    def test_cancelar_recusa_o_relancamento_mas_o_agora_sai(
        self, dialogo: _Dialogo, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """O-AGORA-NAO-E-REFEM-DO-DEPOIS-01 — inverte o que este teste dizia.

        NOTA DATADA (08/08/2026, noite). A versão anterior travava o contrário,
        com o raciocínio de que o toast do cancelar promete que "nada mudou" e
        que aplicar depois dele seria mentira. A verificação adversarial derrubou
        o raciocínio: a promessa é sobre o **jogo** — *"não mexe na minha
        partida"* — e as sete seções (cor, brilho, gatilho, vibração) não mexem
        no jogo em curso. Engoli-las era perder trabalho dela em silêncio.

        E o agravante que decidiu a questão: o Cancelar é o botão **default** do
        diálogo, então Esc, Enter distraído e o X da janela caíam todos aqui.

        A pendência, essa sim, FICA: ela recusou relançar o jogo agora, não
        desistiu da escolha.
        """
        rodape = _Rodape(jogo_aberto=True)
        rodape._escolha_pendente = {"mascara": "xbox"}
        rodape.on_apply_draft()

        dialogo.responder(-6)  # Gtk.ResponseType.CANCEL

        metodos = [m for m, _ in ipc_do_rodape]
        assert "gamepad.emulation.set" not in metodos, (
            "cancelar recriou o vpad — é o dano que o diálogo existe para evitar"
        )
        assert metodos == ["profile.apply_draft"], (
            "as cores/gatilhos que ela editou foram engolidos pelo Cancelar"
        )
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


# ---------------------------------------------------------------------------
# 5. Vale para QUALQUER mesa — decisão dela, 08/08 à noite
# ---------------------------------------------------------------------------


class TestValeParaQualquerMesa:
    """A separação dos dois tempos não pode depender de cabo nem de DualSense.

    Pedido dela, literal: *"cada decisão nossa não é pra funcionar só via cabo
    mas via bt também e deve ser universal, caso eu tenha 4 novos controles dual
    sense ou novos pro controler ou 8bitdo e afins"*.

    O modo e a máscara são do SISTEMA, não de um controle — mas isso é fácil de
    quebrar sem perceber, bastando alguém condicionar a pendência ao controle
    primário, ao transporte ou à contagem. Estes testes existem para que a
    quebra apareça no portão, e não numa partida com quatro controles.
    """

    @pytest.mark.parametrize("transporte", ["usb", "bt"])
    @pytest.mark.parametrize("quantos", [1, 2, 4])
    def test_a_escolha_resiste_ao_tique_com_qualquer_mesa(
        self, fake_gtk: None, transporte: str, quantos: int
    ) -> None:
        janela = _Janela()
        estado = _estado(modo="gamepad", mascara="dualsense")
        estado["controllers"] = [
            {
                "index": i,
                "connected": True,
                "transport": transporte,
                "is_primary": i == 0,
                "player": i + 1,
                "player_slot": i + 1,
            }
            for i in range(quantos)
        ]
        janela._render_home(estado)

        janela._home_flavor_selector.set_active_id("xbox")
        janela._on_home_flavor_changed(janela._home_flavor_selector)
        janela._render_home(estado)

        assert janela._escolha_pendente == {"mascara": "xbox"}
        assert janela._home_flavor_selector.active_id == "xbox"
        assert janela._home_pendente_label.visible is True

    def test_sem_controle_nenhum_a_escolha_continua_de_pe(
        self, fake_gtk: None
    ) -> None:
        """O caso extremo, e o que prova que NÃO há acoplamento.

        Com a mesa vazia — nenhum controle conectado — o modo e a máscara
        continuam sendo escolha válida: eles descrevem o que o sistema vai
        entregar ao jogo, não o que um aparelho específico faz. Se algum dia
        alguém condicionar a pendência a haver controle, este teste cai.
        """
        janela = _Janela()
        estado = _estado(modo="desktop")
        estado["controllers"] = []
        janela._render_home(estado)

        janela._home_mode_selector.set_active_id("gamepad")
        janela._on_home_mode_changed(janela._home_mode_selector)
        janela._render_home(estado)

        assert janela._escolha_pendente == {"modo": "gamepad"}
        assert janela._home_mode_selector.active_id == "gamepad"
        # E a caixa da máscara nasce junto (§12.1) mesmo sem controle na mesa.
        assert janela._home_gamepad_opts.visible is True

    def test_o_aplicar_nao_olha_para_controle_nenhum(
        self, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """O payload da transição é do SISTEMA — sem `uniq`, sem índice.

        Um payload por-controle aqui faria a máscara valer para um aparelho e
        não para os outros, e a mesa de quatro controles dela viraria quatro
        verdades diferentes sobre o que o jogo vê.
        """
        rodape = _Rodape()
        rodape._escolha_pendente = {"modo": "gamepad", "mascara": "dualsense"}

        rodape.on_apply_draft()

        for metodo, params in ipc_do_rodape:
            assert "uniq" not in params, f"{metodo} virou por-controle: {params}"
            assert "index" not in params, f"{metodo} virou por-controle: {params}"
            assert "transport" not in params, f"{metodo} olhou o transporte"


# ---------------------------------------------------------------------------
# 6. O AGORA nunca é refém do DEPOIS
# ---------------------------------------------------------------------------


class TestOAgoraNaoEeRefemDoDepois:
    """O-AGORA-NAO-E-REFEM-DO-DEPOIS-01 (08/08/2026, noite).

    Quatro buracos que a verificação adversarial achou no "Aplicar" que EU
    escrevi horas antes, e que juntos são a explicação provável do relato dela:
    *"e não aplica mais as cores"*.

    A regra que os une, e que estes testes travam: **cor, brilho, gatilho e
    vibração mudam na hora e não dependem de o jogo abrir.** Nenhum tropeço no
    caminho do DEPOIS (modo/máscara) pode cancelar, adiar ou engolir o AGORA.
    """

    def test_transicao_que_falha_nao_engole_as_cores(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O buraco principal, e ele era alcançável de verdade.

        `apply_mode` espera 2,0 s por chamada, e a recriação do vpad com dois
        controles — MEDIDA no journal dela em 08/08 — levou ~1,7 s. Um estouro
        do timeout caía no `_fail`, que só dava toast: as sete seções nunca
        saíam, e o toast falava só do modo. Ela não tinha como saber que a cor
        tinha ido junto.

        ARRANQUE A CURA (tire o `_apply_draft_agora()` do `_fail`) e este teste
        REPROVA.
        """
        chamadas: list[str] = []

        def _transicao_que_falha(
            _method: str,
            _params: dict[str, Any] | None = None,
            _on_done: Any = None,
            on_fail: Any = None,
            timeout_s: float = 0.25,
        ) -> None:
            if on_fail is not None:
                on_fail(TimeoutError("2.0s"))

        def _draft(
            method: str,
            _params: dict[str, Any] | None = None,
            on_success: Any = None,
            on_failure: Any = None,
            timeout_s: float = 0.25,
        ) -> None:
            chamadas.append(method)
            if on_success is not None:
                on_success({"status": "ok", "applied": ["leds"]})

        monkeypatch.setattr(mode_transition, "call_async", _transicao_que_falha)
        monkeypatch.setattr(footer_actions.ipc_bridge, "call_async", _draft)
        rodape = _Rodape()
        rodape._escolha_pendente = {"mascara": "xbox"}

        rodape.on_apply_draft()

        assert chamadas == ["profile.apply_draft"], (
            "a transição falhou e levou as sete seções junto — a cor dela some "
            "sem ninguém dizer nada."
        )
        # E a pendência fica: ela ainda não valeu.
        assert rodape._escolha_pendente == {"mascara": "xbox"}

    def test_o_toast_da_falha_diz_que_o_resto_foi_aplicado(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Metade da cura é o texto — senão ela fica sem saber o que valeu.

        O toast antigo dizia só "ERRO ao aplicar o que vale na abertura", e com
        as sete seções silenciosamente engolidas isso era meia verdade. Agora
        que elas saem, o texto tem de dizer as DUAS coisas.
        """

        def _falha(
            _m: str,
            _p: dict[str, Any] | None = None,
            _d: Any = None,
            on_fail: Any = None,
            timeout_s: float = 0.25,
        ) -> None:
            if on_fail is not None:
                on_fail(TimeoutError("2.0s"))

        monkeypatch.setattr(mode_transition, "call_async", _falha)
        monkeypatch.setattr(
            footer_actions.ipc_bridge,
            "call_async",
            lambda *a, **k: None,
        )
        rodape = _Rodape()
        rodape._escolha_pendente = {"modo": "gamepad"}

        rodape.on_apply_draft()

        assert any("resto dos ajustes foi aplicado" in t for t in rodape._toasted), (
            f"o toast não diz que o AGORA valeu: {rodape._toasted}"
        )

    def test_o_payload_e_montado_antes_de_congelar_a_janela(self) -> None:
        """A ordem que impede a janela de ficar com as cores insensíveis.

        `FROZEN_WIDGET_IDS` inclui `lightbar_color_button` e
        `lightbar_brightness_scale`. Congelar ANTES de montar o payload fazia
        uma falha de serialização subir com a UI travada — e os controles de cor
        ficavam mortos pelo resto da sessão. É, ao pé da letra, "não aplica mais
        as cores".

        ARRANQUE A CURA (volte o `_freeze_ui(True)` para antes do
        `to_ipc_dict()`) e este teste REPROVA.
        """
        ordem: list[str] = []

        class _RodapeQueQuebra(_Rodape):
            def _freeze_ui(self, freeze: bool) -> None:
                ordem.append(f"freeze={freeze}")

        rodape = _RodapeQueQuebra()

        class _DraftQueQuebra:
            def to_ipc_dict(self) -> dict[str, Any]:
                ordem.append("payload")
                raise RuntimeError("serialização quebrou")

        rodape.draft = _DraftQueQuebra()  # type: ignore[assignment]

        with pytest.raises(RuntimeError):
            rodape.on_apply_draft()

        assert ordem == ["payload"], (
            f"a janela foi congelada antes de o payload existir: {ordem}"
        )

    def test_dialogo_que_nao_nasce_devolve_o_gesto_em_vez_de_sumir(
        self, monkeypatch: pytest.MonkeyPatch, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """Um clique que não faz nada, sem toast e sem log, é o pior desfecho.

        Se o construtor do diálogo levantar (GTK sem tela, tema quebrado), o
        `_perguntar_antes_de_relancar` já tinha prometido `True` e a exceção
        subia: o clique no verde morria em silêncio. Agora ele devolve o gesto
        — o mesmo fail-safe que o módulo já aplicava na sondagem do jogo.
        """

        def _explode(*_args: Any, **_kwargs: Any) -> Any:
            raise RuntimeError("sem tela")

        monkeypatch.setattr(daemon_actions, "build_consentimento_dialog", _explode)
        rodape = _Rodape(jogo_aberto=True)
        rodape._escolha_pendente = {"mascara": "xbox"}

        rodape.on_apply_draft()

        metodos = [m for m, _ in ipc_do_rodape]
        assert "gamepad.emulation.set" in metodos and "profile.apply_draft" in metodos


# ---------------------------------------------------------------------------
# 7. O diálogo não pode depender de qual aba está à vista
# ---------------------------------------------------------------------------


class TestOJogoAbertoELidoNaHora:
    """JOGO-ABERTO-SO-NA-INICIO-01 (09/08/2026).

    O `_jogo_aberto` tinha UM escritor — `home_actions._render_home` — e ele só
    roda com a aba Início à vista (o poller checa a página corrente antes de
    trabalhar). Quem clicasse no "Aplicar" a partir da aba Lightbar, ou nos
    primeiros 2 s da janela, tinha o flag em `False` e **nenhuma pergunta era
    feita**: a transição saía direto com o jogo aberto.

    É o caminho que produziu o "Jogador 3" fantasma — o mesmo que esta leva
    dizia ter fechado horas antes. A cura é reler o sinal no clique, e estes
    testes existem para que a dependência de aba não volte por descuido.
    """

    def test_o_aplicar_rele_o_sinal_mesmo_sem_a_aba_inicio_ter_rodado(
        self,
        monkeypatch: pytest.MonkeyPatch,
        ipc_do_rodape: list[tuple[str, dict[str, Any]]],
    ) -> None:
        """O cenário exato: janela recém-aberta, ela nunca passou pela Início.

        ARRANQUE A CURA (tire a chamada de `_ha_jogo_aberto_agora`) e este teste
        REPROVA — o diálogo não abre e a transição sai por cima do jogo dela.
        """
        dialogo_falso = _Dialogo()
        monkeypatch.setattr(
            daemon_actions, "build_consentimento_dialog", dialogo_falso.construir
        )
        import hefesto_dualsense4unix.app.ipc_bridge as ponte

        monkeypatch.setattr(
            ponte,
            "_run_call",
            lambda *_a, **_k: {"game_signal": {"authority": "game"}},
        )
        rodape = _Rodape(jogo_aberto=False)  # como nasce, sem a Início renderizar
        rodape._escolha_pendente = {"mascara": "xbox"}

        rodape.on_apply_draft()

        assert rodape._jogo_aberto is True, "o sinal não foi relido no clique"
        assert dialogo_falso.aberto is True, (
            "o diálogo não apareceu porque a aba Início não estava à vista — é o "
            "caminho do 'Jogador 3' fantasma de volta."
        )
        assert ipc_do_rodape == [], "algo saiu antes de ela responder"

    def test_leitura_que_falha_nao_muda_de_opiniao(
        self, monkeypatch: pytest.MonkeyPatch, ipc_do_rodape: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """Fail-safe: IPC que engasga mantém o que já se sabia.

        A assimetria é deliberada e é a mesma que o `_perguntar_antes_de_relancar`
        já declara: um diálogo que não aparece é ruim, mas um diálogo que aparece
        porque o IPC engasgou **interrompe a partida dela**.
        """
        import hefesto_dualsense4unix.app.ipc_bridge as ponte

        def _explode(*_a: Any, **_k: Any) -> Any:
            raise ConnectionError("socket mudo")

        monkeypatch.setattr(ponte, "_run_call", _explode)
        rodape = _Rodape(jogo_aberto=False)
        rodape._escolha_pendente = {"modo": "desktop"}

        rodape.on_apply_draft()

        assert rodape._jogo_aberto is False
        # E o gesto segue: sem jogo conhecido, aplica como sempre aplicou.
        assert [m for m, _ in ipc_do_rodape][:1] == ["native.mode.set"]

    def test_o_criterio_e_o_mesmo_da_aba_inicio(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Duas leituras do mesmo fato não podem discordar.

        A aba Início decide por `game_signal.authority == "game"`. Se o rodapé
        inventasse outro critério, a janela passaria a ter duas verdades sobre
        se há jogo aberto — o defeito que esta casa persegue desde a HARM-01.
        """
        import hefesto_dualsense4unix.app.ipc_bridge as ponte

        for autoridade, esperado in (("game", True), ("daemon", False), (None, False)):
            monkeypatch.setattr(
                ponte,
                "_run_call",
                lambda *_a, _v=autoridade, **_k: {"game_signal": {"authority": _v}},
            )
            rodape = _Rodape(jogo_aberto=not esperado)
            assert rodape._ha_jogo_aberto_agora() is esperado, autoridade
