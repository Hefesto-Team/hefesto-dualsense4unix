"""TELA-QUE-SO-AFIRMA-O-QUE-SABE-01 — duas linhas da janela param de mentir.

A fila de 09/08 (`A-NOITE-DOS-QUATRO-INVENTARIOS-01`, F-6) nomeou três telas que
afirmam o que não sabem. Este arquivo prende as duas da leva:

**(b) o toast da Lightbar dizia "Cor aplicada no controle".** O ``ok`` que
escolhe essa frase vem do daemon e significa "o report saiu" — nunca "a barra
acendeu". E há um estado, MEDIDO e em vigor na mesa dela, em que as duas coisas
são opostas: por Bluetooth, depois que o daemon adota o controle, o firmware
perde o claim da lightbar e passa a ACEITAR E IGNORAR as escritas de cor
(`core/lightbar_reset.py`, provado ao vivo em 17-18/07 — 330 mil escritas
ignoradas). Nesse estado a frase era falsa em 100% das vezes, e ela passou dias
acreditando que a cor tinha ido porque a janela dizia que sim.

**(c) a linha do Rumble ficava MUDA quando tinha algo a dizer.** A contagem de
pedidos de vibração do jogo só aparecia com ``plays > 0``; em ``plays == 0`` a
linha sumia, e o silêncio passava a significar "está tudo bem" e "não sei" ao
mesmo tempo. O caso ruim é o zero: na mesa dela, ``rumble_ff = {plays: 0,
vpads: 0}`` durante dias de zero vibração em qualquer jogo.

**O que estes testes mordem** (arranque a cura e veja):

- devolva "Cor aplicada" ao ``lightbar_actions`` e as três rotas de escrita
  reprovam — a asserção é sobre a PALAVRA, nas três, porque a frase é uma só e
  as três rotas passam por ela;
- devolva o ``if plays > 0`` ao ``rumble_actions`` e reprovam os três casos que
  hoje falam: jogo calado com vpad, jogo calado SEM vpad, e Conexão Nativa;
- os casos de "não sei" (campo ausente, ``plays`` que não é inteiro) NÃO mordem
  por construção — eles existem para provar que a cura não trocou um silêncio
  ambíguo por um zero inventado, que é o defeito irmão.

Nota de portão: ``exigir_gi_real()`` vem antes de qualquer ``import gi`` de
propósito — este módulo PULA no CI headless (dívida declarada do job de GUI,
CI-GUI-PULAVA-CALADO-01) e morde na máquina de desenvolvimento. Os dois módulos
sob teste importam ``gi`` no topo, então nem a função pura do Rumble escapa
disso enquanto a dívida do job existir.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("tela que so afirma o que sabe")

from typing import Any

import gi
import pytest

# BUG-TEST-GDK-VERSION-PIN-01: pina Gdk/Gtk 3.0 ANTES de importar a GUI.
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app import draft_config as draft_mod
from hefesto_dualsense4unix.app.actions import lightbar_actions
from hefesto_dualsense4unix.app.actions.lightbar_actions import LightbarActionsMixin
from hefesto_dualsense4unix.app.actions.rumble_actions import (
    RumbleActionsMixin,
    texto_dos_pedidos_de_vibracao,
)
from hefesto_dualsense4unix.profiles.schema import LedsConfig, MatchAny, Profile

#: MACs forjados (faixa aa:bb:cc — o portão de anonimato reprova MAC real).
UNIQ_1 = "aabbcc000001"

ROXO = (129, 61, 156)


# ---------------------------------------------------------------------------
# (b) Lightbar — a frase do caminho feliz
# ---------------------------------------------------------------------------


class _HostLightbar(LightbarActionsMixin):
    """Host mínimo do mixin: rascunho, alvo, conectados e toast espião."""

    def __init__(
        self,
        draft: draft_mod.DraftConfig,
        *,
        uniq: str | None = None,
        conectados: dict[int, str | None] | None = None,
    ) -> None:
        self.draft = draft
        self._edit_target_uniq = uniq
        self._target_uniq_by_index = conectados if conectados is not None else {}
        self._widgets: dict[str, Any] = {}
        self._toasts: list[str] = []
        self._refresh_guard = False

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _toast_light(self, msg: str) -> None:
        self._toasts.append(msg)


def _draft() -> draft_mod.DraftConfig:
    """Rascunho com o automático DESLIGADO de propósito.

    Com ele ligado o aviso D4 prefixa o toast, e a palavra "desligadas" dele
    entraria na frase que estes testes leem.
    """
    perfil = Profile(
        name="vitoria",
        match=MatchAny(),
        priority=5,
        leds=LedsConfig(
            lightbar=ROXO,
            lightbar_brightness=1.0,
            auto_player_colors=False,
        ),
    )
    return draft_mod.DraftConfig.from_profile(perfil)


def _selar_led_set(monkeypatch: pytest.MonkeyPatch, aceito: bool = True) -> None:
    """Sela a rota ``led.set``: nenhum teste daqui escreve num controle."""
    monkeypatch.setattr(
        lightbar_actions,
        "led_set",
        lambda *_a, **_kw: aceito,
    )


def _selar_apply_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sela a rota ``profile.apply_draft`` com um daemon que aceitou tudo."""
    monkeypatch.setattr(
        lightbar_actions.ipc_bridge,
        "_safe_call",
        lambda *_a, **_kw: (True, {"status": "ok", "applied": ["leds"]}),
    )


def _ultimo_toast(host: _HostLightbar) -> str:
    assert host._toasts, "a aba não disse nada — o toast do resultado sumiu"
    return host._toasts[-1]


def test_a_rota_por_mac_diz_enviada_e_nao_aplicada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Alvo "Todos" com controle conhecido: ``led.set`` por MAC (R-14).

    O ``ok`` aqui é o aceite do daemon para o pedido — ele não olha a barra.
    """
    _selar_led_set(monkeypatch)
    host = _HostLightbar(_draft(), conectados={0: UNIQ_1})
    host._current_brightness = 0.6

    host.on_lightbar_apply(None)

    assert _ultimo_toast(host) == "Cor enviada ao controle (60% de brilho)"


def test_a_rota_do_rascunho_diz_enviada_e_nao_aplicada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Caminho degradado COR-04: a cor viaja no ``apply_draft`` parcial.

    Aqui o ``ok`` é ainda mais indireto — significa que a seção ``leds`` entrou
    no rascunho aplicado, o que continua não sendo a lâmpada.
    """
    _selar_apply_draft(monkeypatch)
    host = _HostLightbar(_draft())
    host._current_brightness = 1.0

    host.on_lightbar_apply(None)

    assert _ultimo_toast(host) == "Cor enviada ao controle (100% de brilho)"


def test_a_rota_do_controle_selecionado_diz_enviada_e_nao_aplicada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Com um controle no seletor, o MAC viaja no pedido (PERFIL-05).

    CONSERTO 1.5: o ``conectados`` passou a ser obrigatório neste host. O
    padrão do ``_HostLightbar`` é o mapa VAZIO, e mapa vazio com um alvo de pé
    significa, no produto, "nenhum DualSense na mesa" — a escrita fica
    *guardada* e o toast diz isso. O que este teste julga é a palavra "enviada"
    contra "aplicada" na rota por-MAC, e para isso o alvo tem de estar NA MESA.
    """
    _selar_led_set(monkeypatch)
    host = _HostLightbar(_draft(), uniq=UNIQ_1, conectados={0: UNIQ_1})
    host._current_brightness = 0.25

    host.on_lightbar_apply(None)

    assert _ultimo_toast(host) == "Cor enviada ao controle (25% de brilho)"


def test_nenhuma_rota_de_sucesso_afirma_que_a_barra_acendeu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A palavra proibida, nas três rotas de uma vez.

    Um teste por rota pega a frase; este pega a REGRA, e é o que sobrevive a
    uma quarta rota nascer: nenhum caminho de escrita da cor pode anunciar um
    efeito que o produto não mediu. A única leitura de volta que existe é o nó
    sysfs ``multi_intensity``, e ele é o eco do nosso pedido, não a lâmpada
    (``core/sysfs_leds.get_rgb``).

    CONSERTO 1.5: as três rotas aqui são as do CAMINHO FELIZ, e por isso o
    terceiro host (alvo no seletor) ganhou o mapa de conectados. Sem ele o
    alvo está fora da mesa — a escrita fica *guardada*, e a frase honesta
    daquele caso não tem por que dizer "enviada".
    """
    _selar_led_set(monkeypatch)
    _selar_apply_draft(monkeypatch)
    hosts = (
        _HostLightbar(_draft(), conectados={0: UNIQ_1}),
        _HostLightbar(_draft()),
        _HostLightbar(_draft(), uniq=UNIQ_1, conectados={0: UNIQ_1}),
    )

    for host in hosts:
        host.on_lightbar_apply(None)
        msg = _ultimo_toast(host)
        assert "aplicada" not in msg, (
            f"a frase volta a afirmar o que não foi medido: {msg!r} — por "
            "Bluetooth o firmware aceita e IGNORA a escrita de cor, e nesse "
            "estado 'aplicada' é falso em 100% das vezes"
        )
        assert "enviada" in msg


def test_a_cura_nao_troca_uma_mentira_por_outra_no_daemon_desligado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guarda (não morde): sem resposta nenhuma, a frase de sempre.

    Está aqui porque a metade fácil de estragar ao mexer no texto do sucesso é
    a do fracasso: a aba Sistema É o lugar certo quando o Hefesto está mesmo
    desligado, e a APLICAR-VERDADE-01/E2 pagou por essa distinção.
    """
    monkeypatch.setattr(
        lightbar_actions.ipc_bridge,
        "_safe_call",
        lambda *_a, **_kw: (False, None),
    )
    host = _HostLightbar(_draft())

    host.on_lightbar_apply(None)

    assert _ultimo_toast(host) == lightbar_actions._AVISO_HEFESTO_DESLIGADO


# ---------------------------------------------------------------------------
# (c) Rumble — a linha dos pedidos do jogo
# ---------------------------------------------------------------------------


class _RotuloEspiao:
    """Rótulo mínimo: guarda o último markup escrito."""

    def __init__(self) -> None:
        self.markup = ""

    def set_markup(self, texto: str) -> None:
        self.markup = texto


class _HostRumble(RumbleActionsMixin):
    def __init__(self) -> None:
        self.rotulo = _RotuloEspiao()
        self._widgets: dict[str, Any] = {"rumble_state_label": self.rotulo}

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)


def _estado(**campos: Any) -> dict[str, Any]:
    """Um ``state_full`` mínimo: o jogo controla a vibração (o caso de jogar)."""
    base: dict[str, Any] = {"rumble_passthrough": True}
    base.update(campos)
    return base


def test_jogo_calado_com_vpad_deixa_de_ser_silencio() -> None:
    """O caso da mesa dela: há caminho, e ninguém pediu nada por ele.

    Esta é a frase que teria poupado quatro agentes: com ela na tela, ela
    saberia sozinha que o problema não está na vibração do Hefesto, e sim em
    que o jogo nunca pediu.
    """
    texto = texto_dos_pedidos_de_vibracao(
        _estado(rumble_ff={"plays": 0, "vpads": 1})
    )

    assert texto == "o jogo ainda não pediu vibração nenhuma"


def test_sem_vpad_a_frase_e_outra_porque_a_conclusao_e_outra() -> None:
    """``vpads == 0`` não é o jogo calado: é jogo NENHUM tendo onde pedir.

    As duas levam a caças opostas — uma manda olhar o jogo, a outra manda
    ligar a emulação —, então a tela não pode dizer a mesma coisa nas duas.
    """
    sem_vpad = texto_dos_pedidos_de_vibracao(
        _estado(rumble_ff={"plays": 0, "vpads": 0})
    )
    com_vpad = texto_dos_pedidos_de_vibracao(
        _estado(rumble_ff={"plays": 0, "vpads": 1})
    )

    assert sem_vpad is not None
    assert "gamepad virtual" in sem_vpad
    assert sem_vpad != com_vpad


def test_conexao_nativa_nao_conta_pedidos_ao_vpad_que_nao_existe() -> None:
    """Ordem da verdade, pergunta 1 (a mesma de ``estado_do_recurso``).

    Em "Conexão Nativa (Sony)" não há gamepad virtual porque não deve haver —
    o jogo abre o hidraw do controle físico. Dizer "ninguém pediu" ou "não há
    gamepad virtual" ali seria mandar caçar um defeito onde há um desenho.
    """
    texto = texto_dos_pedidos_de_vibracao(
        _estado(native_mode=True, rumble_ff={"plays": 0, "vpads": 0})
    )

    assert texto == "Conexão Nativa (Sony): o jogo fala direto com o controle"


def test_o_numero_continua_aparecendo_quando_o_jogo_pede() -> None:
    """Guarda (não morde): a linha que já existia não mudou de palavra."""
    texto = texto_dos_pedidos_de_vibracao(
        _estado(rumble_ff={"plays": 7, "vpads": 1})
    )

    assert texto == "o jogo pediu vibração 7x"


@pytest.mark.parametrize(
    ("estado", "porque"),
    [
        ({}, "daemon que não mandou o bloco (config ausente no state_full)"),
        ({"rumble_ff": None}, "bloco presente e nulo"),
        ({"rumble_ff": "lixo"}, "bloco de tipo errado"),
        ({"rumble_ff": {}}, "bloco sem o contador"),
        ({"rumble_ff": {"plays": None}}, "contador nulo"),
        ({"rumble_ff": {"plays": "3"}}, "contador que veio como texto"),
        ({"rumble_ff": {"plays": True}}, "bool não é contagem"),
    ],
)
def test_dado_ausente_continua_calado_em_vez_de_afirmar_zero(
    estado: dict[str, Any], porque: str
) -> None:
    """Guarda (não morde): "não sei" não pode virar "ninguém pediu".

    É a família de erro que o ``gyro_do_inputs`` já paga para não cometer —
    três barras paradas no centro dizem "o controle está em repouso", não "eu
    não sei". Aqui seria pior: "o jogo nunca pediu" manda ela caçar no jogo um
    problema que pode ser do transporte.
    """
    assert texto_dos_pedidos_de_vibracao(_estado(**estado)) is None, porque


def test_vpads_ausente_nao_autoriza_afirmar_que_nao_ha_vpad() -> None:
    """Com ``plays == 0`` e ``vpads`` ausente, a tela só afirma o que o
    contador prova — que ninguém pediu; nada sobre haver ou não gamepad."""
    texto = texto_dos_pedidos_de_vibracao(_estado(rumble_ff={"plays": 0}))

    assert texto == "o jogo ainda não pediu vibração nenhuma"


def test_a_linha_da_aba_carrega_a_frase_do_zero() -> None:
    """A fiação: a função pura só vale se o rótulo da aba a exibir.

    Sem esta ligação a cura ficaria bonita no módulo e invisível na tela — e é
    a tela que ela olha.
    """
    host = _HostRumble()

    host._update_rumble_state_label(_estado(rumble_ff={"plays": 0, "vpads": 1}))

    assert "o jogo ainda não pediu vibração nenhuma" in host.rotulo.markup
    assert "Estado da vibração:" in host.rotulo.markup


def test_a_linha_da_aba_fica_sem_o_pedaco_quando_nao_sabe() -> None:
    """Guarda (não morde): sem dado, o separador nem aparece — a linha não
    fica com um "·" pendurado no vazio."""
    host = _HostRumble()

    host._update_rumble_state_label(_estado())

    assert "·" not in host.rotulo.markup
