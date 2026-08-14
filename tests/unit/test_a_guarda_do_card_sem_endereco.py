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
    """O Controle 3 do payload real, com o endereço ARRANCADO.

    O terceiro (índice 2) é escolhido de propósito: ele está no rádio e NÃO é
    o primário do payload — é o card em que a confusão de alvo dói, porque o
    gesto dela iria para o Controle 1, que está no cabo e é de outra pessoa.
    """
    entry = _controles()[2]
    assert entry["transport"] == "bt"
    assert not entry.get("is_primary"), "o caso perde o sentido no primário"
    entry.pop("uniq")
    return entry


def _com_posse_do_volume(
    entry: dict[str, Any], *, volume: int = 137, muted: bool = False
) -> dict[str, Any]:
    """Acrescenta a chave ``speaker`` do jeito que o DAEMON a publica.

    Não é dublê de conveniência: é o bloco de ``_merge_audio``
    (`daemon/ipc_handlers.py`) — ``{"volume": 0-255, "muted": bool}`` no
    ``entry`` e espelhado em ``inputs``, "MESMO dicionário de origem, copiado".
    O fixture real não o traz porque ninguém tinha escrito volume nenhum quando
    ele foi capturado; a chave nasce no primeiro ``speaker.set``.

    **E num card SEM endereço ela nasce sozinha.** O daemon lê o `uniq` do
    próprio entry e passa `None` adiante; `speaker_state_for(None)` cai em
    `_handle_for(None)`, que devolve o handle do PRIMÁRIO. Com a posse do
    volume no primário, este card sem endereço mostra o volume DELE — e é aí
    que "Silenciar" e "Soltar" ficam sensíveis, e que a tranca de dentro do
    gesto vira a última defesa.
    """
    bloco = {"volume": volume, "muted": muted}
    entry["speaker"] = dict(bloco)
    inputs = entry.get("inputs")
    if isinstance(inputs, dict):
        inputs["speaker"] = dict(bloco)
    return entry


# ---------------------------------------------------------------------------
# A regra, sem GTK: quem tem endereço e quem não tem
# ---------------------------------------------------------------------------


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
    """A proteção a montante do "Silenciar"/"Soltar" NÃO é garantia.

    Ela depende do PAYLOAD (a chave `speaker`), não da regra — e o payload que
    a derruba é o que o daemon publica: sem `uniq`, `_merge_audio` lê o
    alto-falante do PRIMÁRIO e o carimba neste card. Este teste é a razão de o
    caso "com posse" existir; se ele reprovar porque as duas ações passaram a
    nascer insensíveis por outro motivo, a tranca de dentro do gesto deixou de
    ter quem a exercite e o teste da mordida abaixo virou enfeite.
    """
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


# ---------------------------------------------------------------------------
# A tela: o bloco desligado E o porquê
# ---------------------------------------------------------------------------


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
        card._janela_do_teste = janela  # segura a referência viva
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

    # -- A MORDIDA -------------------------------------------------------

    @staticmethod
    def _espiar_o_ipc(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Any]]:
        """Troca as três saídas de som por espiões e devolve a lista de pedidos.

        As três, e não duas: o `ligar_ponte_bt` é módulo, não `ipc_bridge`, e
        sem ele o gesto da ponte abriria hidraw de verdade no caso COM
        endereço — que é justamente onde ele passa da tranca.
        """
        from hefesto_dualsense4unix.app import ipc_bridge
        from hefesto_dualsense4unix.app.widgets import controller_card as cc

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
            cc,
            "ligar_ponte_bt",
            lambda uniq, **_kw: pedidos.append(("ponte_bt", uniq)) or (None, ""),
        )
        return pedidos

    @staticmethod
    def _disparar_os_seis_gestos(card: Any) -> None:
        """Os SEIS gestos que escrevem som, num lugar só.

        Um lugar só porque a afirmação da cura é "os seis": se a lista do caso
        SEM endereço e a do caso COM endereço fossem duas, elas se afastariam,
        e a tranca de um gesto poderia sumir sem ninguém ver.

        Os gestos são disparados NO WIDGET, e de propósito: `clicked()` e
        `set_active()` emitem o sinal mesmo com a peça insensível, e o repouso
        do volume pode estar armado de antes. Se a única tranca fosse a
        sensibilidade, o teste passaria e o produto continuaria escrevendo no
        controle de outra pessoa.
        """
        from hefesto_dualsense4unix.app.widgets import controller_card as cc

        card._mic_botao.clicked()
        card._mic_bt_switch.set_active(True)
        card._speaker_escala.set_value(70)
        card._enviar_volume_do_controle()
        card._speaker_botao_mudo.clicked()
        card._speaker_botao_devolver.clicked()
        card._speaker_canal.set_active_id(cc.CANAL_TODO_O_PC)

    def test_nenhum_gesto_sem_endereco_vira_pedido_ao_daemon(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A MORDIDA: com a guarda arrancada, cada gesto vira byte no PRIMÁRIO.

        Este é o payload CRU, e ele exercita QUATRO dos seis: o "Silenciar" e o
        "Soltar" voltam antes, sem posse do volume. Os seis inteiros estão no
        teste seguinte — e os dois testes existem separados porque o estado sem
        posse é o comum, e não pode deixar de ser coberto.
        """
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
        """A MORDIDA que faltava: o "Silenciar" e o "Soltar" CHEGANDO na tranca.

        Com a posse do volume, as duas ações nascem sensíveis (provado sem GTK
        em `test_a_posse_do_volume_abre_o_silenciar_e_o_soltar_sem_endereco`) e
        a tranca de dentro do gesto passa a ser a ÚNICA coisa entre o clique e
        um `speaker.set` no PRIMÁRIO. Sem este caso, arrancar
        `if self._som_sem_alvo(): return` de `_on_speaker_mudo_clicado` e de
        `_on_speaker_devolucao_clicada` deixava a suíte VERDE.

        A asserção sobre as ações é parte da mordida, não decoração: ela é o
        que impede o teste de voltar a passar por o botão estar insensível, em
        vez de por a tranca ter segurado.
        """
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
        """A outra metade da mordida: a guarda não pode matar o produto.

        Sem isto, "desligar tudo sempre" passaria nos testes de cima — e seria
        a entrega errada com a mesma cara da certa. São os MESMOS seis gestos,
        pela mesma função, e no MESMO estado de posse do caso anterior: a única
        diferença entre passar e não passar é o endereço.
        """
        entry = _com_posse_do_volume(_controles()[2])
        pedidos = self._espiar_o_ipc(monkeypatch)

        card = self._card(entry)
        # O som de confirmação não encosta no sistema: o card avulso nasce com
        # o sink vazio, que é o mesmo "não dá para saber" da mesa cheia real
        # (com mais de um DualSense o `escolher_sink` recusa de propósito).
        assert card._speaker_sink == ""

        self._disparar_os_seis_gestos(card)

        assert [nome for nome, _ in pedidos] == [
            "mic.set",
            "ponte_bt",
            "speaker.set",
            "speaker.set",
            "speaker.set",
            "speaker.set",
        ], f"algum dos seis gestos não chegou ao daemon com endereço: {pedidos}"
        assert {alvo for _, alvo in pedidos} == {entry["uniq"]}, (
            "os gestos saíram sem mirar ESTE controle"
        )
