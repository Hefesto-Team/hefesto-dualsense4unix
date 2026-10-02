"""SOM-02/E4 — o volume que ela ajusta CHEGA ao perfil salvo."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# (`test_perfil_salva_tudo_registrar_nao_e_aplicar.py`), que tranca a fiação
exigir_gi_real("som 02 o volume dela chega ao perfil")

import contextlib
from typing import Any, Final

import gi

gi.require_version("Gtk", "3.0")

import pytest

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

VOLUME_VELHO: Final[int] = 60

PORCENTAGEM_NOVA: Final[float] = 90.0

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

_janelas_vivas: list[Any] = []


class _ResultadoDoSom:
    """O que ``tocar_confirmacao`` devolve — o card só lê o ``recado``."""

    recado = ""


class _Janela:
    """A `HefestoApp` reduzida ao que o card precisa: o rascunho."""

    def __init__(self, draft: DraftConfig) -> None:
        self.draft = draft
        self._edit_target_uniq = None


class _Seletor:
    """O `Gtk.ComboBoxText` do canal reduzido ao que o handler lê."""

    def __init__(self, canal: str) -> None:
        self._canal = canal

    def get_active_id(self) -> str:
        return self._canal


class _Pedidos:
    """Registra o que a interface MANDOU, e SEGURA o callback de sucesso."""

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
    """Card montado e ligado à janela, com o estado que o daemon publica."""
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


def test_o_volume_que_ela_ajusta_chega_ao_perfil_salvo(pedidos: _Pedidos) -> None:
    """A MORDIDA principal: perfil com 60, ela sobe, o perfil salvo tem o novo."""
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
    """``speaker.dirty`` nasce baixo e SOBE no gesto — nunca subia antes."""
    card, dona = _bancada(perfil=_perfil(volume=VOLUME_VELHO))
    assert dona.draft.speaker.dirty is False

    _arrastar_e_soltar(card, PORCENTAGEM_NOVA)
    pedidos.rodar()

    assert dona.draft.speaker.dirty is True


def test_o_volume_novo_sobrevive_ao_salvar_com_nome_novo(pedidos: _Pedidos) -> None:
    """Perfil que NÃO tinha a seção ganha o volume dela ao salvar."""
    card, dona = _bancada(perfil=_perfil(), volume_lido=None)
    assert dona.draft.to_profile("pragmata").speaker is None

    _arrastar_e_soltar(card, PORCENTAGEM_NOVA)
    pedidos.rodar()

    salvo = dona.draft.to_profile("outro_nome").speaker
    assert salvo is not None
    assert salvo.volume == pedidos.chamadas[-1]["volume"]


def test_o_daemon_recusando_nao_registra_nada(pedidos_recusados: _Pedidos) -> None:
    """Pedido recusado não vira perfil — o rascunho não guarda intenção."""
    card, dona = _bancada(perfil=_perfil(volume=VOLUME_VELHO))

    _arrastar_e_soltar(card, PORCENTAGEM_NOVA)
    pedidos_recusados.rodar()

    assert pedidos_recusados.chamadas, "o pedido tem de ter SAÍDO"
    assert dona.draft.to_profile("pragmata").speaker.volume == VOLUME_VELHO
    assert dona.draft.speaker.dirty is False


def test_o_registro_nao_acontece_antes_de_o_pedido_ir(pedidos: _Pedidos) -> None:
    """Enquanto o pedido está em voo, o rascunho ainda é o de antes."""
    card, dona = _bancada(perfil=_perfil(volume=VOLUME_VELHO))

    _arrastar_e_soltar(card, PORCENTAGEM_NOVA)
    assert dona.draft.speaker.volume == VOLUME_VELHO

    pedidos.rodar()
    assert dona.draft.speaker.volume != VOLUME_VELHO


def test_o_mudo_dela_chega_ao_perfil_com_o_volume_lido_do_daemon(pedidos: _Pedidos) -> None:
    """Silenciar persiste ``muted`` E o volume que o daemon PUBLICA."""
    card, dona = _bancada(
        perfil=_perfil(volume=VOLUME_SATURADO), volume_lido=VOLUME_SATURADO
    )
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
    """``speaker.set`` só com volume faz ``efetivo = pref`` — ou seja, DESMUDA."""
    card, dona = _bancada(perfil=_perfil(volume=180, muted=True))
    assert dona.draft.speaker.muted is True

    _arrastar_e_soltar(card, PORCENTAGEM_NOVA)
    pedidos.rodar()

    assert dona.draft.to_profile("pragmata").speaker.muted is False


def test_o_canal_de_saida_dela_chega_ao_perfil(pedidos: _Pedidos) -> None:
    """SOM-CANAL-NO-PERFIL-01, pedido dela em 09/08: *"respeitar tudo"*."""
    card, dona = _bancada(perfil=_perfil(volume=VOLUME_VELHO))

    card._on_canal_do_speaker_mudou(_Seletor(CANAL_TODO_O_PC))
    pedidos.rodar()

    assert pedidos.chamadas[-1]["rota"] == ROTA_DO_CANAL[CANAL_TODO_O_PC]
    salvo = dona.draft.to_profile("pragmata").speaker
    assert salvo.rota == ROTA_DO_CANAL[CANAL_TODO_O_PC]
    assert salvo.volume == VOLUME_VELHO


def test_mexer_no_volume_depois_nao_apaga_o_canal_escolhido(
    pedidos: _Pedidos,
) -> None:
    """O gesto do volume não tem opinião sobre o canal — e não pode apagá-lo."""
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
    """Perfil sem opinião de canal sai do ``to_profile`` idêntico ao que era."""
    salvo = DraftConfig.from_profile(_perfil(volume=120)).to_profile("pragmata")
    assert "rota" not in salvo.speaker.model_dump(mode="json")


def test_soltar_a_posse_apaga_a_secao_do_perfil(pedidos: _Pedidos) -> None:
    """"Soltar" tem de tirar o número do perfil — senão a ativação o retoma."""
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


def test_a_secao_do_alto_falante_so_viaja_quando_ela_mexeu_no_som(
    pedidos: _Pedidos,
) -> None:
    """NOTA DATADA — 10/08/2026 (O-VERDE-NAO-LEVAVA-O-SOM-01).

    Este teste se chamava ``test_a_secao_do_alto_falante_nao_viaja_no_aplicar`` e
    exigia ``"speaker" not in to_ipc_dict()``. **O medo dele estava certo e
    continua valendo**, palavra por palavra:

        Registrar é para o SALVAR. Se a seção viajasse no ``to_ipc_dict``, um
        "Aplicar" disparado por ela ter mexido num GATILHO mandaria
        ``speaker.set`` e tomaria os bytes de volume do controle sem ninguém ter
        pedido volume nenhum — o estrago do HARM-05 numa seção com preço.

    O que caducou foi a CURA, não a razão. A ausência total protegia contra o
    Aplicar alheio e cobrava o preço no gesto dela: ela mexia no volume, clicava
    no verde, e o som **não mudava** até a próxima troca de perfil — metade exata
    da queixa de 10/08, *"literalmente nenhuma feature ficou lá"*.

    O gate ``dirty`` separa as duas coisas que a ausência juntava: a seção viaja
    quando ela mexeu NO SOM, e continua calada num Aplicar disparado de qualquer
    outra aba. É a mesma regra que o ``mouse`` e o ``mic`` já usavam ao lado, e o
    HARM-05 segue coberto — pelo gate, agora, e não pelo silêncio.

    As duas metades estão medidas aqui: mexeu, viaja; não mexeu, não viaja.
    """
    card, dona = _bancada(perfil=_perfil(volume=VOLUME_VELHO))

    assert dona.draft.to_ipc_dict().get("speaker") is None

    _arrastar_e_soltar(card, PORCENTAGEM_NOVA)
    pedidos.rodar()

    secao = dona.draft.to_ipc_dict().get("speaker")
    assert secao is not None, "ela mexeu no volume e o Aplicar não leva o som"
    assert secao["volume"] == volume_do_percentual(PORCENTAGEM_NOVA)


def test_card_sem_dono_do_rascunho_continua_mandando_ao_vivo(
    pedidos: _Pedidos,
) -> None:
    """Card avulso (todo teste de geometria monta assim) não pode explodir."""
    card = ControllerCard(compact=False)
    janela = Gtk.OffscreenWindow()
    janela.add(card)
    janela.show_all()
    _janelas_vivas.append(janela)
    card.update(dict(_ENTRY, speaker={"volume": 90, "muted": False}), _ESTADO, None)

    _arrastar_e_soltar(card, PORCENTAGEM_NOVA)
    pedidos.rodar()

    assert pedidos.chamadas[-1]["volume"] == volume_do_percentual(PORCENTAGEM_NOVA)


class _CardEspiao:
    """O card reduzido ao que a fiação da aba toca."""

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
    """A janela do produto reduzida ao que este caminho toca."""

    def __init__(self, card: _CardEspiao, draft: DraftConfig) -> None:
        self.builder = _BuilderDaAba(_SlotComAttach())
        self.draft = draft
        self._mic_monitor = None
        chave = (0, str(_ENTRY["uniq"]))
        self._status_cards = {chave: card}
        self._status_card_keys = [chave]
        self._edit_target_uniq = None


def _estado_com_um_controle() -> dict[str, Any]:
    return {"controllers": [dict(_ENTRY)]}


def test_a_aba_entrega_a_janela_ao_card_e_o_registro_deixa_de_ser_inerte() -> None:
    """A fiação da Parte 1, aferida pelo EFEITO e não pela linha digitada."""
    card = _CardEspiao()
    aba = _AbaStatus(card, DraftConfig.from_profile(_perfil(volume=VOLUME_VELHO)))

    aba._sync_status_cards(_estado_com_um_controle())

    assert card.dono is aba, "a aba não entregou a janela ao card"
    registrar_alto_falante_no_rascunho(card.dono, volume=VOLUME_SATURADO, muted=False)
    assert aba.draft.to_profile("pragmata").speaker.volume == VOLUME_SATURADO


def test_a_janela_entregue_e_a_mesma_que_o_rodape_salva() -> None:
    """O dono tem de ser a janela, não um objeto de conveniência."""
    card = _CardEspiao()
    aba = _AbaStatus(card, DraftConfig())
    aba._sync_status_cards(_estado_com_um_controle())

    registrar_alto_falante_no_rascunho(card.dono, volume=VOLUME_SATURADO, muted=True)

    salvo = aba.draft.to_profile("pragmata").speaker
    assert (salvo.volume, salvo.muted) == (VOLUME_SATURADO, True)
