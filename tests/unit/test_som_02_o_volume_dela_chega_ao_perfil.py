"""SOM-02/E4 — o volume que ela ajusta CHEGA ao perfil salvo.

O defeito, medido na auditoria de 09/08/2026 e o pior do dia: o bloco
"Alto-falante" do card mandava o volume por IPC e **não tocava no rascunho**.
``DraftConfig.with_speaker`` existia desde 29/07, com teste próprio e **zero
chamadores no produto** — API que ninguém chama é dívida com aparência de
recurso. Consequência medida: perfil com ``speaker.volume=60``, ela sobe para
200 ao vivo, e ``draft.to_profile("pragmata")`` devolve **60**.

E o dano fecha o círculo, que é o que faz este ser o caso 2 e não mais um
"não salva": ``lifecycle.apply_profile_speaker`` reaplica o valor do perfil na
ativação, e a troca explícita de perfil — que é o que o "Salvar este perfil"
dispara — solta a trava manual de áudio. **Ela salvava, e o volume dela era
desfeito no mesmo gesto.** Não é só perder o valor novo: é persistir um eco de
estado velho.

POR QUE ESTE ARQUIVO ENTRA PELO HANDLER DO CARD. O teste que já existia
(`test_profile_speaker_section.py`) exercita ``with_speaker`` direto e passa
com o defeito inteiro de pé — ele afere o modelo, e o que estava quebrado era
a FIAÇÃO. Aqui todo caminho começa no mesmo handler que o gesto dela dispara e
termina em ``to_profile``, que é onde o "Salvar Perfil" lê.

A MORDIDA de cada teste está no docstring dele: o que arrancar do
`controller_card.py` (ou do `draft_config.py`) para vê-lo em vermelho.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi`. `importorskip("gi")`
# aceitaria o stub que outro arquivo planta em `sys.modules`, e sem guarda
# nenhuma este módulo derruba a COLETA inteira no CI headless em vez de pular.
#
# O que roda headless é o portão de AST irmão deste arquivo
# (`test_perfil_salva_tudo_registrar_nao_e_aplicar.py`), que tranca a fiação
# sem precisar de GTK — PORTÃO-VIVO-01.
exigir_gi_real("som 02 o volume dela chega ao perfil")

import contextlib
from typing import Any, Final

import gi

gi.require_version("Gtk", "3.0")

import pytest

# CI headless sem libcairo cai no stub do card (sem os sub-widgets do bloco).
pytest.importorskip("cairo")

from gi.repository import Gtk

from hefesto_dualsense4unix.app import audio_saida, ipc_bridge
from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin
from hefesto_dualsense4unix.app.draft_config import (
    DraftConfig,
    registrar_alto_falante_no_rascunho,
)
from hefesto_dualsense4unix.app.widgets.controller_card import (
    CANAL_SONS_DO_JOGO,
    CANAL_TODO_O_PC,
    ROTA_DO_CANAL,
    ControllerCard,
)
from hefesto_dualsense4unix.core.speaker_scale import (
    percentual_do_volume,
    volume_do_percentual,
)
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)

#: O volume que o perfil dela tinha ANTES — o número que voltava ao controle na
#: ativação seguinte, desfazendo o ajuste no mesmo gesto de salvar.
VOLUME_VELHO: Final[int] = 60

#: Onde ela leva o controle deslizante, em porcentagem da TELA (o widget é
#: 0-100; quem converte para os 0-255 do protocolo é `volume_do_percentual`).
PORCENTAGEM_NOVA: Final[float] = 90.0

#: Um volume ACIMA da saturação medida (o registrador satura em 102, medição
#: dela de 01/08). Ele existe para aferir que os gestos SEM número — o mudo e
#: o canal — anotam a leitura do daemon e não o valor da tela: 200 desenha
#: 100 % e a volta pela tela devolveria 102.
VOLUME_SATURADO: Final[int] = 200

_ENTRY: dict[str, Any] = {
    "index": 0,
    "connected": True,
    "transport": "usb",
    "is_primary": True,
    "uniq": "aabbcc000001",
    "battery_pct": 80,
    "player_slot": 1,
    "lightbar_rgb": [97, 53, 131],
    "lightbar_on": True,
    "inputs": {"buttons": [], "l2": 0, "r2": 0},
    "audio": {
        "fone_plugado": False,
        "mic_externo": False,
        "mic_mudo": False,
        "mic_mudo_desejado": None,
    },
}
_ESTADO: dict[str, Any] = {"native_mode": False}

#: As janelas ficam vivas numa lista de módulo: o Python coleta a referência
#: local assim que a função retorna, e o card perde o toplevel no meio do teste.
_janelas_vivas: list[Any] = []


class _ResultadoDoSom:
    """O que ``tocar_confirmacao`` devolve — o card só lê o ``recado``."""

    recado = ""


class _Janela:
    """A `HefestoApp` reduzida ao que o card precisa: o rascunho.

    É o mesmo contrato de ``registrar_modo_no_rascunho`` — quem guarda o
    rascunho é a janela, e o escritor só sabe que ela tem um ``draft``.
    """

    def __init__(self, draft: DraftConfig) -> None:
        self.draft = draft


class _Seletor:
    """O `Gtk.ComboBoxText` do canal reduzido ao que o handler lê."""

    def __init__(self, canal: str) -> None:
        self._canal = canal

    def get_active_id(self) -> str:
        return self._canal


class _Pedidos:
    """Registra o que a interface MANDOU, e SEGURA o callback de sucesso.

    O ``run_in_thread`` real roda em thread worker e repõe o callback na thread
    do GTK; aqui as duas metades ficam na mão do teste, que é o que permite
    aferir a ordem que a entrega exige: **primeiro o daemon confirma, só então
    o rascunho é anotado.**

    ``ok=False`` é o daemon RECUSANDO (offline, sem controle) — o caminho em
    que nada pode ser registrado, porque o rascunho descreve o que ficou de
    pé e não a intenção.
    """

    def __init__(self, *, ok: bool = True) -> None:
        self.ok = ok
        self.pendentes: list[tuple[Any, Any]] = []
        self.chamadas: list[dict[str, Any]] = []

    def run_in_thread(self, fn: Any, on_ok: Any, _on_err: Any = None) -> None:
        self.pendentes.append((fn, on_ok))

    def speaker_set(self, **kwargs: Any) -> bool:
        self.chamadas.append(kwargs)
        return self.ok

    def rodar(self) -> None:
        """Executa o pedido e devolve o resultado ao callback de sucesso."""
        pendentes, self.pendentes = self.pendentes, []
        for fn, on_ok in pendentes:
            on_ok(fn())


@pytest.fixture
def pedidos(monkeypatch: pytest.MonkeyPatch) -> _Pedidos:
    espiao = _Pedidos()
    monkeypatch.setattr(ipc_bridge, "run_in_thread", espiao.run_in_thread)
    monkeypatch.setattr(ipc_bridge, "speaker_set", espiao.speaker_set)
    monkeypatch.setattr(
        audio_saida, "tocar_confirmacao", lambda *a, **k: _ResultadoDoSom()
    )
    monkeypatch.setattr(audio_saida, "garantir_saida_audivel", lambda *a, **k: None)
    return espiao


@pytest.fixture
def pedidos_recusados(monkeypatch: pytest.MonkeyPatch) -> _Pedidos:
    espiao = _Pedidos(ok=False)
    monkeypatch.setattr(ipc_bridge, "run_in_thread", espiao.run_in_thread)
    monkeypatch.setattr(ipc_bridge, "speaker_set", espiao.speaker_set)
    monkeypatch.setattr(
        audio_saida, "tocar_confirmacao", lambda *a, **k: _ResultadoDoSom()
    )
    return espiao


def _perfil(**speaker: Any) -> Profile:
    """O perfil dela, com (ou sem) a seção de alto-falante."""
    return Profile(
        name="pragmata",
        match=MatchCriteria(window_class=["pragmata_class"]),
        priority=10,
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Off"), right=TriggerConfig(mode="Off")
        ),
        leds=LedsConfig(lightbar=(0, 0, 0), player_leds=[False] * 5),
        speaker=speaker or None,  # type: ignore[arg-type]
    )


def _bancada(
    *, perfil: Profile | None = None, volume_lido: int | None = VOLUME_VELHO
) -> tuple[Any, _Janela]:
    """Card montado e ligado à janela, com o estado que o daemon publica.

    ``volume_lido=None`` é a sessão em que ninguém escreveu ainda: a chave
    ``speaker`` NÃO existe no payload, que é como o daemon publica a ausência
    de posse.
    """
    card = ControllerCard(compact=False)
    janela = Gtk.OffscreenWindow()
    janela.add(card)
    janela.show_all()
    _janelas_vivas.append(janela)

    dona = _Janela(
        DraftConfig.from_profile(perfil) if perfil is not None else DraftConfig()
    )
    card.definir_dono_do_rascunho(dona)

    entrada = dict(_ENTRY)
    if volume_lido is None:
        entrada.pop("speaker", None)
    else:
        entrada["speaker"] = {"volume": volume_lido, "muted": False}
    card.update(entrada, _ESTADO, None)
    with contextlib.suppress(Exception):
        while Gtk.events_pending():
            Gtk.main_iteration()
    return card, dona


def _arrastar_e_soltar(card: Any, porcentagem: float) -> None:
    """O gesto dela: leva o cursor e SOLTA o botão — o fim do gesto."""
    card._speaker_escala.set_value(porcentagem)
    card._on_speaker_escala_solta(None, None)


# --- 1. O defeito, pelo caminho dela -----------------------------------------


def test_o_volume_que_ela_ajusta_chega_ao_perfil_salvo(pedidos: _Pedidos) -> None:
    """A MORDIDA principal: perfil com 60, ela sobe, o perfil salvo tem o novo.

    Este é o teste que reprova com o defeito de pé — e o `with_speaker` puro,
    exercitado pelo `test_profile_speaker_section.py`, passa mesmo assim.

    Mordida: apagar a chamada a ``_confirmado_pelo_daemon`` em
    ``_enviar_volume_do_controle`` (voltando ao ``self._on_som_de_confirmacao``
    cru) devolve o `60` aqui, que é literalmente o número medido na auditoria.
    """
    card, dona = _bancada(perfil=_perfil(volume=VOLUME_VELHO))
    assert dona.draft.to_profile("pragmata").speaker.volume == VOLUME_VELHO

    _arrastar_e_soltar(card, PORCENTAGEM_NOVA)
    pedidos.rodar()

    enviado = pedidos.chamadas[-1]["volume"]
    assert enviado == volume_do_percentual(PORCENTAGEM_NOVA)
    salvo = dona.draft.to_profile("pragmata").speaker
    assert salvo is not None
    assert salvo.volume == enviado
    assert salvo.volume != VOLUME_VELHO


def test_o_dirty_do_alto_falante_sobe_no_gesto_dela(pedidos: _Pedidos) -> None:
    """``speaker.dirty`` nasce baixo e SOBE no gesto — nunca subia antes.

    É o `dirty` que faz o valor sobreviver a um "Salvar Perfil" com nome NOVO
    (a mesma disciplina do `mouse.dirty`): carga programática não é toque dela,
    gesto é.

    Mordida: tirar o ``dirty=True`` do ``SpeakerDraft`` de ``with_speaker``.
    """
    card, dona = _bancada(perfil=_perfil(volume=VOLUME_VELHO))
    assert dona.draft.speaker.dirty is False

    _arrastar_e_soltar(card, PORCENTAGEM_NOVA)
    pedidos.rodar()

    assert dona.draft.speaker.dirty is True


def test_o_volume_novo_sobrevive_ao_salvar_com_nome_novo(pedidos: _Pedidos) -> None:
    """Perfil que NÃO tinha a seção ganha o volume dela ao salvar.

    Sem `dirty`, um perfil sem seção de origem descartaria o gesto inteiro no
    ``to_profile`` — o gate é ``volume is not None and (dirty or in_profile)``.
    """
    card, dona = _bancada(perfil=_perfil(), volume_lido=None)
    assert dona.draft.to_profile("pragmata").speaker is None

    _arrastar_e_soltar(card, PORCENTAGEM_NOVA)
    pedidos.rodar()

    salvo = dona.draft.to_profile("outro_nome").speaker
    assert salvo is not None
    assert salvo.volume == pedidos.chamadas[-1]["volume"]


# --- 2. Registrar é DEPOIS, e é o que ficou de pé ------------------------------


def test_o_daemon_recusando_nao_registra_nada(pedidos_recusados: _Pedidos) -> None:
    """Pedido recusado não vira perfil — o rascunho não guarda intenção.

    A auditoria de 09/08 flagrou a política de rumble como a exceção ruim
    (grava ANTES da confirmação). Aqui a ordem é a da casa: o daemon confirma,
    e só então o rascunho anota.

    Mordida: mover o ``registrar_alto_falante_no_rascunho`` para fora do
    ``if resultado is not None`` de ``_confirmado_pelo_daemon``.
    """
    card, dona = _bancada(perfil=_perfil(volume=VOLUME_VELHO))

    _arrastar_e_soltar(card, PORCENTAGEM_NOVA)
    pedidos_recusados.rodar()

    assert pedidos_recusados.chamadas, "o pedido tem de ter SAÍDO"
    assert dona.draft.to_profile("pragmata").speaker.volume == VOLUME_VELHO
    assert dona.draft.speaker.dirty is False


def test_o_registro_nao_acontece_antes_de_o_pedido_ir(pedidos: _Pedidos) -> None:
    """Enquanto o pedido está em voo, o rascunho ainda é o de antes.

    Mordida: chamar o escritor no corpo de ``_enviar_volume_do_controle`` em
    vez de no callback de sucesso.
    """
    card, dona = _bancada(perfil=_perfil(volume=VOLUME_VELHO))

    _arrastar_e_soltar(card, PORCENTAGEM_NOVA)
    assert dona.draft.speaker.volume == VOLUME_VELHO  # em voo, nada anotado

    pedidos.rodar()
    assert dona.draft.speaker.volume != VOLUME_VELHO


# --- 3. Mudo ------------------------------------------------------------------


def test_o_mudo_dela_chega_ao_perfil_com_o_volume_lido_do_daemon(pedidos: _Pedidos) -> None:
    """Silenciar persiste ``muted`` E o volume que o daemon PUBLICA.

    O volume anotado é a LEITURA, não o número do controle deslizante. Fora da
    faixa útil do registrador a volta ``bruto -> pct -> bruto`` NÃO é
    identidade — 200 vira 100 % e volta como 102 (a saturação medida em
    01/08) —, e um clique em Silenciar não pode baixar o volume guardado dela
    de lambuja.

    Mordida: trocar ``self._volume_lido_do_daemon()`` por
    ``volume_do_percentual(self._speaker_escala.get_value())`` em
    ``_on_speaker_mudo_clicado``: o perfil passa a guardar 102 no lugar de 200.
    """
    card, dona = _bancada(
        perfil=_perfil(volume=VOLUME_SATURADO), volume_lido=VOLUME_SATURADO
    )
    # A ida e volta pela TELA não devolve o mesmo número — é o que o teste afere.
    pela_tela = volume_do_percentual(percentual_do_volume(VOLUME_SATURADO))
    assert pela_tela != VOLUME_SATURADO

    card._on_speaker_mudo_clicado(None)
    pedidos.rodar()

    assert pedidos.chamadas[-1]["muted"] is True
    salvo = dona.draft.to_profile("pragmata").speaker
    assert (salvo.volume, salvo.muted) == (VOLUME_SATURADO, True)


def test_desmutar_tambem_chega_ao_perfil(pedidos: _Pedidos) -> None:
    """Ativar volta o perfil para ``muted: false`` — o par é sempre completo."""
    card = ControllerCard(compact=False)
    janela = Gtk.OffscreenWindow()
    janela.add(card)
    janela.show_all()
    _janelas_vivas.append(janela)
    dona = _Janela(DraftConfig.from_profile(_perfil(volume=180, muted=True)))
    card.definir_dono_do_rascunho(dona)
    entrada = dict(_ENTRY)
    entrada["speaker"] = {"volume": 180, "muted": True}
    card.update(entrada, _ESTADO, None)

    card._on_speaker_mudo_clicado(None)
    pedidos.rodar()

    assert pedidos.chamadas[-1]["muted"] is False
    salvo = dona.draft.to_profile("pragmata").speaker
    assert (salvo.volume, salvo.muted) == (180, False)


def test_mover_o_volume_desmuta_no_perfil_como_desmuta_no_firmware(
    pedidos: _Pedidos,
) -> None:
    """``speaker.set`` só com volume faz ``efetivo = pref`` — ou seja, DESMUDA.

    Registrar ``muted=False`` aqui não é chute: é o que o
    ``set_speaker_volume`` faz com ``muted=None``. Anotar ``muted=True`` de um
    estado anterior faria o perfil salvo silenciar o controle na ativação.
    """
    card, dona = _bancada(perfil=_perfil(volume=180, muted=True))
    assert dona.draft.speaker.muted is True

    _arrastar_e_soltar(card, PORCENTAGEM_NOVA)
    pedidos.rodar()

    assert dona.draft.to_profile("pragmata").speaker.muted is False


# --- 4. Canal de saída (a rota) ------------------------------------------------


def test_o_canal_de_saida_dela_chega_ao_perfil(pedidos: _Pedidos) -> None:
    """SOM-CANAL-NO-PERFIL-01, pedido dela em 09/08: *"respeitar tudo"*.

    O seletor escolhe o ``OUTPUT_PATH_SEL`` (camada 2) e agora ele fica no
    perfil, junto do volume — é a MESMA posse, e o gesto já manda os dois no
    mesmo ``speaker.set``.

    Mordida: tirar o ``rota=rota`` do ``_confirmado_pelo_daemon`` em
    ``_on_canal_do_speaker_mudou``.
    """
    card, dona = _bancada(perfil=_perfil(volume=VOLUME_VELHO))

    card._on_canal_do_speaker_mudou(_Seletor(CANAL_TODO_O_PC))
    pedidos.rodar()

    assert pedidos.chamadas[-1]["rota"] == ROTA_DO_CANAL[CANAL_TODO_O_PC]
    salvo = dona.draft.to_profile("pragmata").speaker
    assert salvo.rota == ROTA_DO_CANAL[CANAL_TODO_O_PC]
    # A rota não pode viajar sozinha: a seção inteira exige volume, e é o mesmo
    # `set_speaker_volume` que escreve os dois bytes.
    assert salvo.volume == VOLUME_VELHO


def test_mexer_no_volume_depois_nao_apaga_o_canal_escolhido(
    pedidos: _Pedidos,
) -> None:
    """O gesto do volume não tem opinião sobre o canal — e não pode apagá-lo.

    Mordida: fazer ``with_speaker`` gravar ``rota=rota`` cru (sem o
    ``self.speaker.rota if rota is None``); o canal dela some no gesto
    seguinte, em silêncio.
    """
    card, dona = _bancada(perfil=_perfil(volume=VOLUME_VELHO))

    card._on_canal_do_speaker_mudou(_Seletor(CANAL_SONS_DO_JOGO))
    pedidos.rodar()
    _arrastar_e_soltar(card, PORCENTAGEM_NOVA)
    pedidos.rodar()

    salvo = dona.draft.to_profile("pragmata").speaker
    assert salvo.rota == ROTA_DO_CANAL[CANAL_SONS_DO_JOGO]
    assert salvo.volume == pedidos.chamadas[-1]["volume"]


def test_perfil_com_rota_volta_para_o_rascunho_ao_abrir() -> None:
    """Round-trip: o canal salvo reaparece no rascunho, sem virar toque dela."""
    draft = DraftConfig.from_profile(_perfil(volume=120, rota=2))
    assert draft.speaker.rota == 2
    assert draft.speaker.dirty is False
    assert draft.to_profile("pragmata").speaker.rota == 2


def test_perfil_sem_rota_nao_grava_a_chave_nova() -> None:
    """Perfil sem opinião de canal sai do ``to_profile`` idêntico ao que era.

    ``extra="forbid"`` faz um hefesto ANTIGO recusar o perfil inteiro ao ver
    uma chave que não conhece: gravar ``"rota": null`` em todo perfil com som
    transformaria "voltar uma versão" em "perfis quebrados".
    """
    salvo = DraftConfig.from_profile(_perfil(volume=120)).to_profile("pragmata")
    assert "rota" not in salvo.speaker.model_dump(mode="json")


# --- 5. Devolver a posse: registrar a AUSÊNCIA --------------------------------


def test_soltar_a_posse_apaga_a_secao_do_perfil(pedidos: _Pedidos) -> None:
    """"Soltar" tem de tirar o número do perfil — senão a ativação o retoma.

    É a metade do defeito que não é "perder o valor novo", e sim "persistir um
    eco de estado velho": sem isto, salvar depois de devolver a posse guardaria
    o último volume, e ``apply_profile_speaker`` retomaria na ativação seguinte
    uma posse que ela acabou de largar.

    Mordida: trocar ``soltar=True`` por ``volume=None`` sem o ``soltar`` — o
    registro some e a seção fica no perfil.
    """
    card, dona = _bancada(perfil=_perfil(volume=VOLUME_VELHO, rota=3))
    assert dona.draft.to_profile("pragmata").speaker is not None

    card._on_speaker_devolucao_clicada(None)
    pedidos.rodar()

    assert pedidos.chamadas[-1] == {"release": True, "uniq": _ENTRY["uniq"]}
    assert dona.draft.to_profile("pragmata").speaker is None
    assert dona.draft.speaker.rota is None


def test_soltar_recusado_pelo_daemon_nao_apaga_nada(
    pedidos_recusados: _Pedidos,
) -> None:
    """Devolução que o daemon recusou não pode apagar a seção do perfil."""
    card, dona = _bancada(perfil=_perfil(volume=VOLUME_VELHO))

    card._on_speaker_devolucao_clicada(None)
    pedidos_recusados.rodar()

    assert dona.draft.to_profile("pragmata").speaker.volume == VOLUME_VELHO


# --- 6. As cercas: registrar NÃO é aplicar ------------------------------------


def test_a_secao_do_alto_falante_nao_viaja_no_aplicar(pedidos: _Pedidos) -> None:
    """SOM-02/E4: o "Aplicar" do rodapé não pode tomar a posse do volume.

    Registrar é para o SALVAR. Se a seção viajasse no ``to_ipc_dict``, um
    "Aplicar" disparado por ela ter mexido num GATILHO mandaria ``speaker.set``
    e tomaria os bytes de volume do controle sem ninguém ter pedido volume
    nenhum — o estrago do HARM-05 numa seção com preço.
    """
    card, dona = _bancada(perfil=_perfil(volume=VOLUME_VELHO))
    _arrastar_e_soltar(card, PORCENTAGEM_NOVA)
    pedidos.rodar()

    assert "speaker" not in dona.draft.to_ipc_dict()


def test_card_sem_dono_do_rascunho_continua_mandando_ao_vivo(
    pedidos: _Pedidos,
) -> None:
    """Card avulso (todo teste de geometria monta assim) não pode explodir.

    Sem janela injetada o gesto ao vivo continua indo e nada é anotado — que é
    o comportamento correto, e não uma exceção engolida.
    """
    card = ControllerCard(compact=False)
    janela = Gtk.OffscreenWindow()
    janela.add(card)
    janela.show_all()
    _janelas_vivas.append(janela)
    card.update(dict(_ENTRY, speaker={"volume": 90, "muted": False}), _ESTADO, None)

    _arrastar_e_soltar(card, PORCENTAGEM_NOVA)
    pedidos.rodar()

    assert pedidos.chamadas[-1]["volume"] == volume_do_percentual(PORCENTAGEM_NOVA)


# --- 7. A FIAÇÃO da aba: quem entrega a janela ao card ------------------------
#
# O andar que faltava, e sem o qual TODO o resto deste arquivo é encenação: o
# card só anota no rascunho depois que alguém lhe diz QUEM é o dono dele. Nos
# testes acima quem diz é a bancada (`card.definir_dono_do_rascunho(dona)`); no
# produto tem de ser a aba Status, no mesmo lugar em que ela já injeta o sink de
# saída e o pedido de rota. Enquanto essa linha não existisse, `with_speaker`
# continuaria com zero chamadores VIVOS — a dívida com aparência de recurso que
# a auditoria de 09/08 achou, só que um andar acima.


class _CardEspiao:
    """O card reduzido ao que a fiação da aba toca.

    Não é o `ControllerCard` real de propósito: o que este teste afere é a ABA,
    e o card real já tem os seus testes acima. O espião registra o dono que
    recebeu — e é o teste que faz a escrita, com o escritor REAL, para provar
    que o objeto entregue serve de fato como rascunho.
    """

    def __init__(self) -> None:
        self.dono: Any = None
        self.updates = 0

    def update(self, *_a: Any, **_k: Any) -> None:
        self.updates += 1

    def definir_dono_do_rascunho(self, janela: Any) -> None:
        self.dono = janela


class _SlotComAttach:
    """O `GtkGrid` do Glade reduzido: `_sync_status_cards` só exige o `attach`."""

    def attach(self, *_a: Any, **_k: Any) -> None:  # pragma: no cover - inerte
        raise AssertionError("rebuild não devia acontecer com as chaves estáveis")


class _BuilderDaAba:
    def __init__(self, slot: Any) -> None:
        self._slot = slot

    def get_object(self, wid: str) -> Any:
        return self._slot if wid == "status_players_slot" else None


class _AbaStatus(StatusActionsMixin):
    """A janela do produto reduzida ao que este caminho toca.

    Herda a mixin REAL — é `_sync_status_cards` de verdade que roda. E tem
    `draft`, porque no produto a aba É a janela: é esse o objeto que o card
    recebe, e é isso que este teste prova.
    """

    def __init__(self, card: _CardEspiao, draft: DraftConfig) -> None:
        self.builder = _BuilderDaAba(_SlotComAttach())
        self.draft = draft
        self._mic_monitor = None
        chave = (0, str(_ENTRY["uniq"]))
        self._status_cards = {chave: card}
        self._status_card_keys = [chave]


def _estado_com_um_controle() -> dict[str, Any]:
    return {"controllers": [dict(_ENTRY)]}


def test_a_aba_entrega_a_janela_ao_card_e_o_registro_deixa_de_ser_inerte() -> None:
    """A fiação da Parte 1, aferida pelo EFEITO e não pela linha digitada.

    O tique da aba roda; o card recebe um dono; e o escritor REAL do produto,
    chamado com esse dono, muda o rascunho da JANELA. É a cadeia inteira sem
    nenhum dublê no meio dela.

    MORDIDA: apagar o bloco `definir_dono_do_rascunho` de
    `status_actions._sync_status_cards` deixa `card.dono` em None; o escritor
    então sai calado (janela sem `draft`) e o rascunho continua com o volume
    VELHO — que é exatamente o defeito: o registro existe, tem teste, e não
    chega ao perfil dela.
    """
    card = _CardEspiao()
    aba = _AbaStatus(card, DraftConfig.from_profile(_perfil(volume=VOLUME_VELHO)))

    aba._sync_status_cards(_estado_com_um_controle())

    assert card.dono is aba, "a aba não entregou a janela ao card"
    registrar_alto_falante_no_rascunho(card.dono, volume=VOLUME_SATURADO, muted=False)
    assert aba.draft.to_profile("pragmata").speaker.volume == VOLUME_SATURADO


def test_a_janela_entregue_e_a_mesma_que_o_rodape_salva() -> None:
    """O dono tem de ser a janela, não um objeto de conveniência.

    Um `definir_dono_do_rascunho(card)` ou um dono improvisado passariam no
    teste acima se ele olhasse só "recebeu alguém" — e o "Salvar Perfil" leria
    o rascunho da JANELA, que continuaria intocado. Por isso a asserção é de
    identidade, e a leitura vem de `aba.draft`.
    """
    card = _CardEspiao()
    aba = _AbaStatus(card, DraftConfig())
    aba._sync_status_cards(_estado_com_um_controle())

    registrar_alto_falante_no_rascunho(card.dono, volume=VOLUME_SATURADO, muted=True)

    salvo = aba.draft.to_profile("pragmata").speaker
    assert (salvo.volume, salvo.muted) == (VOLUME_SATURADO, True)
