"""A guarda do card SEM ENDEREÇO — o som que ia parar no controle errado.

Item 1.10 do índice da mesa cheia (`docs/process/sprints/
2026-08-13-INDICE-a-mesa-cheia-cada-jogador-na-cor-dele.md`, §7).

**O defeito.** Toda saída de som do card viaja com o `uniq` do controle —
`mic.set`, `speaker.set` (volume, mudo, soltar e canal) e a ponte por rádio.
Sem `uniq`, o daemon cai no controle **PRIMÁRIO**: ela clica no bloco do
Controle 3, lê "Controle 3 — BT" no título, e quem muda de volume é o
Controle 1. E `uniq` ausente não é hipótese — o `_key_to_uniq` do backend
devolve `None` de propósito sempre que a key do handle é um caminho
(`/dev/hidrawN`), que é o que sobra quando o MAC não pôde ser lido do sysfs.

**A cura, e as duas metades dela.** Desligar o bloco de som E dizer por quê:
um bloco desabilitado sem explicação é um defeito do mesmo tamanho — ela leria
"o produto quebrou".

**O caso vem do payload REAL de quatro controles**
(`tests/fixtures/state_full_quatro_controles.json`, medido em 14/08/2026 com
dois controles no cabo e dois no rádio). O card sem endereço é construído
ARRANCANDO o `uniq` de um deles, e não inventado: um dublê só contém o que
quem o escreveu já sabia — este traz o `audio` com o microfone captando, que é
justamente o estado em que o botão de mudo fica sensível e o gesto sai.

**Por que há DOIS estados sem endereço aqui, e não um** (correção de 14/08/2026,
depois de a primeira versão ser refutada). A tranca de dentro do gesto
(`_som_sem_alvo`) está em SEIS gestos, mas com o payload cru só QUATRO chegam
nela: o "Silenciar" e o "Soltar" voltam antes, em `acao.sensivel is False`,
porque o fixture não traz a chave `speaker`. Arrancando as duas linhas
`if self._som_sem_alvo(): return` desses dois handlers, os testes ficavam
VERDES — cura arrancada com teste verde não é cura testada.

A proteção a montante **não é garantia**: ela depende do payload, não da regra.
E o payload que a derruba é o que o daemon publica de verdade — em
`daemon/ipc_handlers._merge_audio` o `uniq` do próprio entry é passado adiante,
e `speaker_state_for(None)` cai em `_handle_for(None)`, que devolve o handle do
**PRIMÁRIO** (`core/backend_pydualsense.py`). Ou seja: assim que o primário tem
a posse do volume, o card SEM endereço recebe a chave `speaker` do primário, o
"Silenciar" e o "Soltar" ficam sensíveis, e a tranca passa a ser a única coisa
entre o clique dela e um `speaker.set` no controle de outra pessoa. É a mesma
regra "sem `uniq` = o primário" que causa o defeito, vista do lado da LEITURA.

Por isso os gestos são disparados nos dois estados — sem posse e com posse —, e
sempre pela mesma função (`_disparar_os_seis_gestos`), para que a lista dos seis
não possa se afastar entre o caso sem endereço e o caso com endereço.

**Continuam seis em 16/08/2026, mas um deles trocou.** O interruptor "Pelo
rádio" saiu do card (ponte insegura — `test_o_interruptor_do_mic_por_bluetooth`)
e o controle deslizante do microfone tomou o lugar dele, na lista e na tela. Não
é substituição de conveniência: `mic.volume.set` sem `uniq` cai no controle
PRIMÁRIO exatamente como os outros cinco, então a vaga na guarda tinha dono
antes de estar vazia.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.widgets.controller_card import (
    acao_speaker_devolucao,
    acao_speaker_mudo,
    audio_sem_endereco,
    uniq_do_entry,
)

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "state_full_quatro_controles.json"
)


def _controles() -> list[dict[str, Any]]:
    """Os quatro controles do payload real, cópia profunda por teste."""
    dados = json.loads(FIXTURE.read_text(encoding="utf-8"))
    controles = dados["controllers"]
    assert len(controles) == 4, "o fixture da mesa cheia tem de ter QUATRO"
    return [copy.deepcopy(c) for c in controles]


def _controle_sem_endereco() -> dict[str, Any]:
    """O Controle 3 do payload real, com o endereço ARRANCADO."""
    entry = _controles()[2]
    assert entry["transport"] == "bt"
    assert not entry.get("is_primary"), "o caso perde o sentido no primário"
    entry.pop("uniq")
    return entry


def _com_posse_do_volume(
    entry: dict[str, Any], *, volume: int = 137, muted: bool = False
) -> dict[str, Any]:
    """Acrescenta a chave ``speaker`` do jeito que o DAEMON a publica."""
    bloco = {"volume": volume, "muted": muted}
    entry["speaker"] = dict(bloco)
    inputs = entry.get("inputs")
    if isinstance(inputs, dict):
        inputs["speaker"] = dict(bloco)
    return entry


def test_os_quatro_controles_reais_tem_endereco() -> None:
    """A guarda não pode disparar na mesa cheia — ali todos têm MAC."""
    for entry in _controles():
        assert uniq_do_entry(entry) is not None
        assert audio_sem_endereco(entry) is False, (
            "a guarda desligaria o som de um controle que TEM endereço"
        )


@pytest.mark.parametrize("valor", [None, "", "   "])
def test_endereco_ausente_ou_em_branco_desliga_o_som(valor: Any) -> None:
    """Endereço em branco viaja no IPC como "sem alvo" — é o mesmo defeito."""
    entry = _controle_sem_endereco()
    if valor is not None:
        entry["uniq"] = valor
    assert uniq_do_entry(entry) is None
    assert audio_sem_endereco(entry) is True


def test_a_posse_do_volume_abre_o_silenciar_e_o_soltar_sem_endereco() -> None:
    """A proteção a montante do "Silenciar"/"Soltar" NÃO é garantia."""
    cru = _controle_sem_endereco()
    assert acao_speaker_mudo(cru).sensivel is False, (
        "sem a chave `speaker` os dois botões já voltam ANTES da tranca — é "
        "por isso que o payload cru não prova as seis"
    )
    assert acao_speaker_devolucao(cru).sensivel is False

    com_posse = _com_posse_do_volume(_controle_sem_endereco())
    assert audio_sem_endereco(com_posse) is True, (
        "a posse do volume não dá endereço nenhum a este card"
    )
    assert acao_speaker_mudo(com_posse).sensivel is True
    assert acao_speaker_mudo(com_posse).muted is True
    assert acao_speaker_devolucao(com_posse).sensivel is True
    assert acao_speaker_devolucao(com_posse).release is True


class TestNaTela:
    """A metade que só o GTK real prova."""

    @staticmethod
    def _card(entry: dict[str, Any]) -> Any:
        from tests.conftest import exigir_gi_real

        exigir_gi_real("a guarda do card sem endereço")
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        from hefesto_dualsense4unix.app.widgets.controller_card import (
            ControllerCard,
        )

        if not Gtk.init_check()[0]:
            pytest.skip("sem GTK/display utilizável")
        card = ControllerCard(compact=False)
        janela = Gtk.OffscreenWindow()
        janela.add(card)
        janela.set_size_request(1180, 700)
        janela.show_all()
        card._janela_do_teste = janela
        card.update(entry, {}, None)
        return card

    def test_sem_endereco_as_pecas_de_som_ficam_apagadas(self) -> None:
        card = self._card(_controle_sem_endereco())

        apagadas = [
            peca.__class__.__name__
            for peca in card._pecas_que_escrevem_som()
            if peca.get_sensitive()
        ]
        assert apagadas == [], (
            "estas peças escrevem som e continuaram clicáveis sem endereço: "
            f"{apagadas} — cada uma cairia no controle PRIMÁRIO"
        )

    def test_sem_endereco_a_tela_diz_por_que(self) -> None:
        """Bloco desligado calado é um defeito do mesmo tamanho."""
        from hefesto_dualsense4unix.app.widgets import controller_card as cc

        card = self._card(_controle_sem_endereco())

        assert card._audio_aviso.get_visible() is True
        assert card._audio_aviso.get_text() == cc.TEXTO_AUDIO_SEM_ENDERECO
        for bloco in (card._mic_box, card._speaker_box):
            assert bloco.get_tooltip_text() == cc.DICA_AUDIO_SEM_ENDERECO, (
                "o porquê tem de estar na MOLDURA: peça insensível não recebe "
                "evento no GTK3 e a dica dela nunca apareceria"
            )

    def test_com_endereco_o_som_continua_de_pe(self) -> None:
        """A guarda é condicional — não pode virar um bloco morto para todos."""
        card = self._card(_controles()[2])

        assert card._audio_aviso.get_visible() is False
        assert card._mic_botao.get_sensitive() is True
        assert card._speaker_escala.get_sensitive() is True
        assert card._mic_box.get_tooltip_text() is None

    def test_o_endereco_que_volta_devolve_o_som(self) -> None:
        """A volta é diffada e precisa acontecer UMA vez, sem card novo."""
        card = self._card(_controle_sem_endereco())
        assert card._mic_botao.get_sensitive() is False

        card.update(_controles()[2], {}, None)

        assert card._audio_aviso.get_visible() is False
        assert card._mic_botao.get_sensitive() is True
        assert card._speaker_escala.get_sensitive() is True


    @staticmethod
    def _espiar_o_ipc(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Any]]:
        """Troca as três saídas de som por espiões e devolve a lista de pedidos."""
        from hefesto_dualsense4unix.app import ipc_bridge

        pedidos: list[tuple[str, Any]] = []

        def _direto(fn: Any, on_success: Any = None, on_failure: Any = None) -> None:
            resultado = fn()
            if on_success is not None:
                on_success(resultado)

        monkeypatch.setattr(ipc_bridge, "run_in_thread", _direto)
        monkeypatch.setattr(
            ipc_bridge,
            "mic_set",
            lambda valor, uniq=None: pedidos.append(("mic.set", uniq)) or True,
        )
        monkeypatch.setattr(
            ipc_bridge,
            "speaker_set",
            lambda **kw: pedidos.append(("speaker.set", kw.get("uniq"))) or True,
        )
        monkeypatch.setattr(
            ipc_bridge,
            "mic_volume_set_detalhado",
            lambda **kw: pedidos.append(("mic.volume.set", kw.get("uniq")))
            or {"status": "ok", "por_uniq": True},
        )
        return pedidos

    @staticmethod
    def _disparar_os_seis_gestos(card: Any) -> None:
        """Os SEIS gestos que escrevem som, num lugar só."""
        from hefesto_dualsense4unix.app.widgets import controller_card as cc

        card._mic_botao.clicked()
        card._mic_escala.set_value(70)
        card._enviar_volume_do_mic()
        card._speaker_escala.set_value(70)
        card._enviar_volume_do_controle()
        card._speaker_botao_mudo.clicked()
        card._speaker_botao_devolver.clicked()
        card._speaker_canal.set_active_id(cc.CANAL_TODO_O_PC)

    def test_nenhum_gesto_sem_endereco_vira_pedido_ao_daemon(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A MORDIDA: com a guarda arrancada, cada gesto vira byte no PRIMÁRIO."""
        pedidos = self._espiar_o_ipc(monkeypatch)

        card = self._card(_controle_sem_endereco())
        self._disparar_os_seis_gestos(card)

        assert pedidos == [], (
            "o card sem endereço mandou som ao daemon: cada pedido destes "
            f"cai no controle PRIMÁRIO, não neste card — {pedidos}"
        )

    def test_com_posse_do_volume_os_dois_ultimos_gestos_tambem_morrem(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A MORDIDA que faltava: o "Silenciar" e o "Soltar" CHEGANDO na tranca."""
        pedidos = self._espiar_o_ipc(monkeypatch)

        card = self._card(_com_posse_do_volume(_controle_sem_endereco()))
        assert card._speaker_acao_mudo.sensivel is True, (
            "sem uma ação sensível este teste não exercita a tranca do mudo"
        )
        assert card._speaker_acao_devolucao.sensivel is True, (
            "sem uma ação sensível este teste não exercita a tranca do soltar"
        )

        self._disparar_os_seis_gestos(card)

        assert pedidos == [], (
            "o card sem endereço mandou som ao daemon com a posse do volume "
            f"aberta — cada pedido destes cai no PRIMÁRIO: {pedidos}"
        )

    def test_com_endereco_os_seis_gestos_chegam_e_miram_este_controle(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A outra metade da mordida: a guarda não pode matar o produto."""
        entry = _com_posse_do_volume(_controles()[2])
        pedidos = self._espiar_o_ipc(monkeypatch)

        card = self._card(entry)
        # (com mais de um DualSense o `escolher_sink` recusa de propósito).
        assert card._speaker_sink == ""

        self._disparar_os_seis_gestos(card)

        assert [nome for nome, _ in pedidos] == [
            "mic.set",
            "mic.volume.set",
            "speaker.set",
            "speaker.set",
            "speaker.set",
            "speaker.set",
        ], f"algum dos seis gestos não chegou ao daemon com endereço: {pedidos}"
        assert {alvo for _, alvo in pedidos} == {entry["uniq"]}, (
            "os gestos saíram sem mirar ESTE controle"
        )
