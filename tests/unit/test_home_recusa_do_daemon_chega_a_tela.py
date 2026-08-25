"""A recusa do daemon chega à tela, e a escolha dela sobrevive — I1 e I2.

INÍCIO NÃO MENTE-01, §2.2a e §2.2c. Dois defeitos que são um só, medidos na
noite de 18→19/08/2026 com o DON'T SCREAM aberto:

1. ``set_gamepad_emulation`` devolve o MESMO ``True`` para três desfechos —
   apliquei / já estava / **recusei pelo gate R-04** — e o handler traduz os
   três em ``status: "ok"``. A resposta chegava ao ``_done(_resultado)`` do
   ``_transicao_de_modo`` e era **descartada**, porque ``ao_aplicar`` era um
   callback de zero argumentos nos dois chamadores. Resultado na tela: com o
   jogo aberto o daemon RECUSAVA a troca e o rodapé anunciava *"O jogo agora
   vê: Xbox 360"*;
2. ``_home_flavor_pedido`` — a única memória de um pedido recusado — **não
   tinha escritor com valor em `src/`**. O ``_render_home`` reescreve o seletor
   com o valor do daemon a cada 2 s, então a escolha recusada dela sumia da
   tela em dois segundos, sem uma palavra.

As duas entram JUNTAS, e a sprint diz por quê: meia cura escreveria a frase
certa sobre um desfecho que ninguém apurou.

O QUE ESTE ARQUIVO NÃO ABENÇOA
-------------------------------

O TEXTO das três frases é **estrutural** e espera o olho dela
(PROVA-DE-TELA-01). O que se mede aqui é o que a frase NÃO pode dizer — nunca
que a redação está aprovada.
"""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from typing import Any

import pytest


# NOTA — este arquivo NÃO planta `gi` falso em `sys.modules` no import, e é
# de propósito: `home_actions` e `footer_actions` importam `gi` DENTRO das
# funções, então o módulo carrega sem toolkit nenhum. O único ponto que
# precisa de widget é o `_render_home`, e ali o stub entra por
# `monkeypatch.setitem` (fixture `gtk_de_render`), que se desfaz sozinho.
#
# GUARDA-GI-REAL-01: plantar o stub no import faria este arquivo rodar VERDE
# contra widgets de mentira no job de lint e NUNCA entrar no job `gtk-real`,
# que seleciona por `exigir_gi_real|skip_sem_gi_real`. Há portão que reprova
# (`test_guarda_gi_falso_precisa_de_exigir_gi_real.py`), e ele pegou esta
# versão do arquivo em 25/08/2026.


from hefesto_dualsense4unix.app.actions import (
    footer_actions,
    home_actions,
    mode_transition,
)

#: A resposta MEDIDA de um `gamepad.emulation.set` que o gate R-04 recusou: o
#: `status` diz "ok" (é "recebi", não "apliquei") e o `flavor` devolve a máscara
#: ANTIGA, porque o daemon só grava `config.gamepad_flavor` depois de o vpad
#: novo nascer. É o payload inteiro que separa "aplicou" de "não aplicou", e era
#: só ninguém olhar para ele.
RECUSA_DO_GATE: dict[str, Any] = {
    "status": "ok",
    "enabled": True,
    "flavor": "dualsense",
}

#: A mesma chamada quando ela é de fato aplicada.
APLICOU: dict[str, Any] = {"status": "ok", "enabled": True, "flavor": "xbox"}


class _Widget:
    """O mínimo que o `_render_home` toca. Guarda o que lhe mandaram."""

    def __init__(self) -> None:
        self.texto = ""
        self.markup = ""
        self.visivel = False
        self.active_id: str | None = None
        self.sensivel = True
        self.filhos: list[Any] = []
        self.classes: list[str] = []

    def set_text(self, valor: str) -> None:
        self.texto = valor

    def get_text(self) -> str:
        return self.texto

    def set_markup(self, valor: str) -> None:
        self.markup = valor
        self.texto = valor

    def set_label(self, valor: str) -> None:
        self.texto = valor

    def set_visible(self, valor: bool) -> None:
        self.visivel = bool(valor)

    def get_visible(self) -> bool:
        return self.visivel

    def set_sensitive(self, valor: bool) -> None:
        self.sensivel = bool(valor)

    def set_no_show_all(self, _valor: bool) -> None:
        pass

    def set_margin_end(self, _valor: int) -> None:
        pass

    def set_xalign(self, _valor: float) -> None:
        pass

    def set_active(self, _valor: bool) -> None:
        pass

    def set_active_id(self, valor: str) -> None:
        self.active_id = valor

    def get_active_id(self) -> str | None:
        return self.active_id

    def get_style_context(self) -> Any:
        return SimpleNamespace(
            add_class=self.classes.append,
            remove_class=lambda n: self.classes.remove(n)
            if n in self.classes
            else None,
        )

    def pack_start(self, filho: Any, *_a: object) -> None:
        self.filhos.append(filho)

    def get_children(self) -> list[Any]:
        return list(self.filhos)

    def remove(self, filho: Any) -> None:
        self.filhos.remove(filho)

    def show_all(self) -> None:
        pass


class _Janela:
    """A janela composta: o rodapé e a aba Início na MESMA instância.

    É assim que o produto é (`HefestoApp` junta os dois mixins), e é o que este
    arquivo precisa medir — o rodapé escreve um campo que a aba lê no tique
    seguinte. Dois dublês separados não alcançariam a costura.
    """

    _aplicar_escolha_pendente = (
        footer_actions.FooterActionsMixin._aplicar_escolha_pendente
    )
    _dizer_com_o_recado_da_maquina = (
        footer_actions.FooterActionsMixin._dizer_com_o_recado_da_maquina
    )
    _render_home = home_actions.HomeActionsMixin._render_home
    _render_home_controllers = home_actions.HomeActionsMixin._render_home_controllers
    _render_ponte_e_divergencia = (
        home_actions.HomeActionsMixin._render_ponte_e_divergencia
    )
    _mascara_escolhida_por_ela = (
        home_actions.HomeActionsMixin._mascara_escolhida_por_ela
    )
    _mascara_escolhida_com_fonte = (
        home_actions.HomeActionsMixin._mascara_escolhida_com_fonte
    )

    def __init__(self, pendente: dict[str, str]) -> None:
        self.toasts: list[str] = []
        self._recado_da_maquina: str | None = None
        self._escolha_pendente: dict[str, str] | None = dict(pendente)
        self._modo_vigente_do_daemon = "gamepad"
        self._mascara_vigente_do_daemon: str | None = "dualsense"
        self._home_flavor_pedido: str | None = None
        self.draft = None
        # A aba montada, no mínimo que o `_render_home` percorre.
        self._home_installed = True
        self._home_guard = False
        self._home_inflight = False
        self._home_mode_selector = _Widget()
        self._home_flavor_selector = _Widget()
        self._home_mode_desc = _Widget()
        self._home_origin_label = _Widget()
        self._home_session_label = _Widget()
        self._home_players_hint = _Widget()
        self._home_gamepad_opts = _Widget()
        self._home_controllers_box = _Widget()
        self._home_vpad_banner = _Widget()
        self._home_wrapper_banner = _Widget()
        self._home_shutdown_btn = _Widget()
        self._home_reconciliar_btn = _Widget()
        self._home_reconciliar_hint = _Widget()
        self._home_ponte_label = _Widget()
        self._home_divergencia_banner = _Widget()
        self._home_pendente_label = _Widget()
        self._home_offline = False

    # --- o que o rodapé espera da janela -------------------------------
    def _perguntar_antes_de_relancar(self, **_kw: object) -> bool:
        return False

    def _ha_jogo_aberto_agora(self) -> bool:
        return True  # é o gate R-04 que se está medindo

    def _footer_toast(self, msg: str, _contexto: str = "footer") -> None:
        self.toasts.append(msg)

    def _apply_draft_agora(self) -> None:
        # O AGORA das sete seções não é o assunto daqui — o que importa é que
        # ele é quem consome o recado, e a frase FINAL é a que ela lê.
        self._dizer_com_o_recado_da_maquina("Perfil aplicado.")

    def _status_toast(self, _contexto: str, _msg: str) -> None:
        pass

    def aplicar(self) -> None:
        self._aplicar_escolha_pendente(dict(self._escolha_pendente or {}))


@pytest.fixture()
def gtk_de_render(monkeypatch: pytest.MonkeyPatch) -> None:
    """O `gi.repository` que o `_render_home` importa DENTRO da função.

    Trocado por `SimpleNamespace` durante o teste (mesmo desenho do
    `fake_gtk` de `test_home_render_state.py`): o render monta cards de
    verdade, e com o `gi` real isso exigiria display. O que se mede aqui é a
    DECISÃO do render, não a montagem do widget.
    """
    repo = types.ModuleType("gi.repository")
    repo.Gtk = SimpleNamespace(  # type: ignore[attr-defined]
        Label=lambda **kw: _Widget(),
        Box=lambda **kw: _Widget(),
        Orientation=SimpleNamespace(VERTICAL=0, HORIZONTAL=1),
    )
    monkeypatch.setitem(sys.modules, "gi.repository", repo)


@pytest.fixture()
def daemon(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """O daemon do outro lado do socket, com a resposta escolhida pelo teste.

    O dublê SABE RECUSAR (A2, 23/08/2026): `resposta` é trocável, e os testes
    exercitam a recusa e o sucesso. Um dublê que só devolvesse "aplicado"
    deixaria o caminho de erro sem régua — que é o defeito que a I1 cura.
    """
    estado: dict[str, Any] = {"resposta": RECUSA_DO_GATE, "chamadas": []}

    def _fake(
        metodo: str,
        params: dict[str, Any] | None,
        ok: Any = None,
        _err: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        estado["chamadas"].append((metodo, dict(params or {})))
        # Só o passo REPORTADO devolve à UI — os outros são preparo. É o mesmo
        # critério do `reported_step_index`, e por isso o desfecho medido é o do
        # `gamepad.emulation.set`.
        if metodo == "gamepad.emulation.set" and callable(ok):
            ok(estado["resposta"])

    monkeypatch.setattr(mode_transition, "call_async", _fake)
    return estado


def _estado_do_daemon(flavor: str = "dualsense") -> dict[str, Any]:
    """`state_full` com o jogo aberto e o vpad na máscara que ``flavor`` diz.

    O `backend` acompanha a máscara porque no produto ele NÃO é livre:
    `virtual_pad._try_uhid` recusa o uhid para qualquer sabor que não seja
    `dualsense` (o `hid_playstation` só faz bind em produto Sony). Um payload
    com `xbox` em `uhid` não existe na máquina — e mediria a função errada, já
    que `mascara_viva` lê `backend == "uhid"` como "é DualSense, e não pode ser
    outra coisa".
    """
    return {
        "connected": True,
        "native_mode": False,
        "gamepad_emulation": {
            "enabled": True,
            "flavor": flavor,
            "backend": "uhid" if flavor == "dualsense" else "uinput",
        },
        "controllers": [
            {"index": 0, "connected": True, "transport": "usb", "is_primary": True}
        ],
        "game_signal": {"authority": "game"},
    }


# ----------------------------------------------------------------------
# I1 — a recusa chega à tela
# ----------------------------------------------------------------------


def test_a_recusa_do_gate_nao_vira_o_jogo_agora_ve(daemon: dict[str, Any]) -> None:
    """A MORDIDA da I1, literal do §5 da sprint.

    Payload ``{"status":"ok","flavor":"dualsense"}`` como resposta a um pedido
    de ``xbox``: o toast NÃO pode conter "O jogo agora vê".

    Arranque a chamada a `desfecho_da_troca` em
    `footer_actions._aplicar_escolha_pendente._done` (ou volte `ao_aplicar` a
    zero argumentos) e este teste reprova — porque a frase volta a ser a do
    sucesso, que é o que ele dizia em 18/08.
    """
    daemon["resposta"] = RECUSA_DO_GATE
    janela = _Janela({"modo": "gamepad", "mascara": "xbox"})

    janela.aplicar()

    frase = janela.toasts[-1]
    assert "O jogo agora vê" not in frase, (
        f"o rodapé anunciou sucesso sobre uma recusa: {frase!r}. O gate R-04 "
        "devolveu a máscara ANTIGA, que é como o daemon diz 'não apliquei'."
    )
    assert "Ainda não" in frase, (
        f"a recusa não foi dita: {frase!r}. Não basta calar — a frase precisa "
        "dizer o motivo E o caminho, senão a recusa vira 'o Hefesto não "
        "obedece'."
    )


def test_a_troca_que_entrou_continua_dizendo_que_entrou(
    daemon: dict[str, Any],
) -> None:
    """A régua sabe dizer SIM: sem isto, calar sempre passaria por severo."""
    daemon["resposta"] = APLICOU
    janela = _Janela({"modo": "gamepad", "mascara": "xbox"})

    janela.aplicar()

    assert "O jogo agora vê" in janela.toasts[-1]


def test_sem_mascara_escolhida_o_rodape_nao_inventa_desfecho(
    daemon: dict[str, Any],
) -> None:
    """Trocar SÓ o modo não é trocar máscara — e não tem desfecho de máscara.

    Sem esta guarda, "Jogar pelo Hefesto" sem escolher máscara acenderia uma
    frase sobre uma troca que ela nunca pediu. É a mesma disciplina do
    `AUTO-01.3`: quem não escolheu não manda, e sobre quem não mandou não se
    afirma desfecho.
    """
    daemon["resposta"] = RECUSA_DO_GATE
    janela = _Janela({"modo": "gamepad"})

    janela.aplicar()

    frase = janela.toasts[-1]
    assert "Ainda não" not in frase
    assert "O jogo agora vê" not in frase


# ----------------------------------------------------------------------
# I2 — a escolha recusada sobrevive ao próximo tique
# ----------------------------------------------------------------------


def test_a_escolha_recusada_sobrevive_a_dois_tiques(
    daemon: dict[str, Any], gtk_de_render: None
) -> None:
    """A MORDIDA da I2, literal do §5: dois tiques depois, o banner de pé.

    O `_render_home` roda a cada 2 s e reescreve o seletor com o valor do
    daemon. Sem `_home_flavor_pedido` gravado, a divergência não teria o que
    ler e a escolha recusada dela sumiria da tela em dois segundos — sem uma
    palavra, que é o pior desfecho possível: ela conclui que clicou errado.

    Arranque a chamada a `lembrar_mascara_recusada` e este teste reprova no
    primeiro tique.
    """
    daemon["resposta"] = RECUSA_DO_GATE
    janela = _Janela({"modo": "gamepad", "mascara": "xbox"})

    janela.aplicar()
    assert janela._home_flavor_pedido == "xbox", (
        "o rodapé recebeu a recusa e não guardou o que ela pediu"
    )

    for _tique in range(2):
        janela._render_home(_estado_do_daemon("dualsense"))

    banner = janela._home_divergencia_banner
    assert banner.get_visible() is True, (
        "dois tiques depois da recusa o banner de divergência sumiu — a janela "
        "voltou a mostrar o estado do daemon como se fosse a escolha dela"
    )
    assert "Xbox 360" in banner.markup


def test_o_pedido_morre_quando_o_aparelho_alcanca_a_escolha(
    daemon: dict[str, Any], gtk_de_render: None
) -> None:
    """Pendência, não preferência: atendida, ela some sozinha.

    Sem isto um pedido antigo e já atendido acusaria divergência falsa na
    próxima troca vinda de outro lugar (a aba Perfis, o autoswitch) — a aba
    passaria a mentir para o outro lado.
    """
    daemon["resposta"] = RECUSA_DO_GATE
    janela = _Janela({"modo": "gamepad", "mascara": "xbox"})
    janela.aplicar()

    # O jogo fechou e abriu: o daemon aplicou o que ela tinha pedido.
    janela._render_home(_estado_do_daemon("xbox"))

    assert janela._home_flavor_pedido is None
    assert janela._home_divergencia_banner.get_visible() is False


def test_um_desfecho_incerto_nao_grava_pedido(daemon: dict[str, Any]) -> None:
    """"Não sei" não pode virar "ela pediu e não recebeu".

    Um daemon velho demais para dizer qualquer coisa devolve `True` cru. Ali o
    honesto é a frase que manda ela conferir na linha "Ponte com o jogo" — e
    não acender a divergência contra um aparelho sobre o qual nada se apurou.
    """
    daemon["resposta"] = True
    janela = _Janela({"modo": "gamepad", "mascara": "xbox"})

    janela.aplicar()

    assert janela._home_flavor_pedido is None
    assert "Ponte com o jogo" in janela.toasts[-1]
