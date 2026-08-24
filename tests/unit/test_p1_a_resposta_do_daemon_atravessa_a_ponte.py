"""P1 / ELO-MUDO-01: a resposta do daemon ATRAVESSA a ponte de IPC.

O que estes testes provam não é que a função foi chamada — é que o CORPO que o
daemon montou chega inteiro do outro lado. Um dublê que responde "mesa vazia"
tem de produzir "mesa vazia" na saída da ponte; um que recusa tem de produzir a
recusa.

**O dublê fica em ``_run_call``**, e isso é de propósito: ``_run_call`` é a
única fronteira com o socket. Tudo acima dele — ``_safe_call``,
``_corpo_do_daemon``, ``_call_checked_detalhado`` e os invólucros públicos — é
código de produção rodando de verdade. Dublar ``_safe_call`` (como outros
testes desta casa fazem, legitimamente, para outro fim) deixaria justamente o
encanamento sob suspeita fora do exercício.

Os payloads de resposta são LITERAIS: copiados dos handlers do daemon
(``_handle_trigger_set``, ``_handle_led_set``, ``_handle_mic_volume_set`` …) e
conferidos contra a bancada viva em 23/08/2026. O de mesa vazia é o medido:
``{"status": "ok", "aplicado_em": [], "guardado_em": []}`` — ZERO destino, com a
aba Gatilhos dizendo "aplicado".

**COMO ESTES TESTES MORDEM.** Arranque o encanamento novo, das duas formas:

1. em ``_call_checked_detalhado``, volte a linha do RPC para
   ``_run_call(method, params, timeout=timeout)`` **sem atribuição** e devolva
   ``return True, None, None``;
2. em ``_corpo_do_daemon``, devolva ``None`` sempre.

É exatamente o estado da árvore antes desta leva. A saída da reprovação está
colada no relatório da leva.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.cli.ipc_client import IpcError
from hefesto_dualsense4unix.daemon.ipc_server import CODE_INVALID_PARAMS

# --- as respostas LITERAIS do daemon ---------------------------------------

#: Medido na bancada viva em 23/08/2026 com a mesa VAZIA. Nenhum byte no fio,
#: nada guardado — e a tela dizia "SimpleRigid aplicado".
TRIGGER_MESA_VAZIA: dict[str, Any] = {
    "status": "ok",
    "aplicado_em": [],
    "guardado_em": [],
}

#: Mesa com um controle presente e outro só registrado (MESA-CHEIA-09).
TRIGGER_UM_APLICOU_UM_GUARDOU: dict[str, Any] = {
    "status": "ok",
    "aplicado_em": ["e8:47:3a:00:00:f6"],
    "guardado_em": ["aa:bb:cc:00:00:66"],
}

LED_MESA_VAZIA: dict[str, Any] = {
    "status": "ok",
    "aplicado_em": [],
    "guardado_em": [],
}

PLAYER_LEDS_GUARDADO: dict[str, Any] = {
    "status": "ok",
    "bits": [True, False, False, False, False],
    "aplicado_em": [],
    "guardado_em": ["e8:47:3a:00:00:f6"],
}

#: `_handle_mic_volume_set`: sem ponte de áudio no rádio não há fonte de
#: captura. NÃO é falha — é resposta, e o daemon está vivo.
MIC_VOLUME_SEM_FONTE: dict[str, Any] = {
    "status": "sem_fonte",
    "fonte": None,
    "volume": None,
}

#: O gesto caiu na ROTA GLOBAL: mexeu no microfone de outra pessoa
#: (MIC-DA-MESA-CHEIA-01). `por_uniq: False` é o único jeito de saber.
MIC_VOLUME_ROTA_GLOBAL: dict[str, Any] = {
    "status": "ok",
    "fonte": "alsa_input.usb-Sony_Wireless_Controller-00.analog-stereo",
    "volume": 62,
    "por_uniq": False,
}

MIC_VOLUME_ALVO_HONRADO: dict[str, Any] = dict(MIC_VOLUME_ROTA_GLOBAL, por_uniq=True)

MIC_SET_SEM_CONTROLE: dict[str, Any] = {
    "status": "sem_controle",
    "audio": None,
    "mic_mudo_desejado": True,
}

SPEAKER_SEM_CONTROLE: dict[str, Any] = {"status": "sem_controle", "speaker": None}

RUMBLE_POLICY_OK: dict[str, Any] = {"status": "ok", "policy": "economia"}

#: A outra forma de o daemon dizer não: a frase dentro de um corpo bem-sucedido
#: (`_recusa_no_corpo`). Hoje nenhuma rota de gatilho a usa; o contrato tem de
#: aguentá-la mesmo assim, porque foi assim que o rumble sob Modo Nativo
#: apareceu e ninguém quer descobrir isso duas vezes.
TRIGGER_RECUSADO: dict[str, Any] = {
    "status": "recusado",
    "motivo": "O Modo Nativo está ligado e o jogo manda nos gatilhos",
}


class _Espiao:
    """Dublê de ``_run_call``: devolve o combinado e guarda o que foi pedido."""

    def __init__(self, resposta: Any) -> None:
        self.resposta = resposta
        self.chamadas: list[tuple[str, dict[str, Any] | None]] = []

    def __call__(
        self, method: str, params: dict[str, Any] | None = None, timeout: Any = None
    ) -> Any:
        self.chamadas.append((method, params))
        if isinstance(self.resposta, BaseException):
            raise self.resposta
        return self.resposta


@pytest.fixture
def daemon_diz(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """Instala um daemon dublê no lugar do socket e devolve o espião."""

    def _instalar(resposta: Any) -> _Espiao:
        espiao = _Espiao(resposta)
        monkeypatch.setattr(ipc_bridge, "_run_call", espiao)
        return espiao

    return _instalar


# ---------------------------------------------------------------------------
# Gatilhos — a mentira medida ao vivo
# ---------------------------------------------------------------------------


class TestGatilhoEntregaOsDestinos:
    def test_mesa_vazia_chega_como_zero_destinos(self, daemon_diz) -> None:  # type: ignore[no-untyped-def]
        daemon_diz(TRIGGER_MESA_VAZIA)

        ok, motivo, corpo = ipc_bridge.trigger_set_detalhado(
            "left", "SimpleRigid", [5]
        )

        assert ok is True
        assert motivo is None
        assert corpo == TRIGGER_MESA_VAZIA, (
            "o corpo do daemon tem de chegar INTEIRO — foi ele que morreu no "
            "socket e fez a aba Gatilhos dizer 'aplicado' com zero destino"
        )
        assert ipc_bridge.destinos_da_aplicacao(corpo) == ([], [])

    def test_destinos_separam_o_que_saiu_do_que_ficou_guardado(
        self, daemon_diz
    ) -> None:  # type: ignore[no-untyped-def]
        daemon_diz(TRIGGER_UM_APLICOU_UM_GUARDOU)

        _ok, _motivo, corpo = ipc_bridge.trigger_set_detalhado(
            "right", "Rigid", [0, 8, 8], uniq="e8:47:3a:00:00:f6"
        )

        assert ipc_bridge.destinos_da_aplicacao(corpo) == (
            ["e8:47:3a:00:00:f6"],
            ["aa:bb:cc:00:00:66"],
        )

    def test_o_pedido_e_identico_ao_da_porta_antiga(self, daemon_diz) -> None:  # type: ignore[no-untyped-def]
        """A porta nova não pode inventar rota nem payload."""
        espiao = daemon_diz(TRIGGER_MESA_VAZIA)

        ipc_bridge.trigger_set_detalhado("left", "Rigid", [1, 2], uniq="aa:bb:cc:00:00:ff")
        ipc_bridge.trigger_set_checked("left", "Rigid", [1, 2], uniq="aa:bb:cc:00:00:ff")

        assert espiao.chamadas[0] == espiao.chamadas[1]
        assert espiao.chamadas[0] == (
            "trigger.set",
            {
                "side": "left",
                "mode": "Rigid",
                "params": [1, 2],
                "uniq": "aa:bb:cc:00:00:ff",
            },
        )

    def test_recusa_no_corpo_vira_motivo(self, daemon_diz) -> None:  # type: ignore[no-untyped-def]
        daemon_diz(TRIGGER_RECUSADO)

        ok, motivo, corpo = ipc_bridge.trigger_set_detalhado("left", "Off", [])

        assert motivo == TRIGGER_RECUSADO["motivo"]
        assert corpo == TRIGGER_RECUSADO
        assert ok is True, (
            "o RPC foi bem-sucedido; quem decide o que fazer com a frase é a "
            "janela — mas a frase tem de CHEGAR"
        )

    def test_parametro_invalido_continua_separado_de_daemon_morto(
        self, daemon_diz
    ) -> None:  # type: ignore[no-untyped-def]
        daemon_diz(IpcError(CODE_INVALID_PARAMS, "Fim deve ser maior que Início"))

        assert ipc_bridge.trigger_set_detalhado("left", "Rigid", [8, 2]) == (
            False,
            "Fim deve ser maior que Início",
            None,
        )

    def test_daemon_offline_nao_inventa_corpo(self, daemon_diz) -> None:  # type: ignore[no-untyped-def]
        daemon_diz(FileNotFoundError("socket ausente"))

        assert ipc_bridge.trigger_set_detalhado("left", "Rigid", [2, 8]) == (
            False,
            None,
            None,
        )

    def test_reset_entrega_os_mesmos_destinos(self, daemon_diz) -> None:  # type: ignore[no-untyped-def]
        espiao = daemon_diz(TRIGGER_UM_APLICOU_UM_GUARDOU)

        ok, _motivo, corpo = ipc_bridge.trigger_reset_detalhado(
            side="left", uniq="e8:47:3a:00:00:f6"
        )

        assert ok is True
        assert ipc_bridge.destinos_da_aplicacao(corpo) == (
            ["e8:47:3a:00:00:f6"],
            ["aa:bb:cc:00:00:66"],
        )
        assert espiao.chamadas[0] == (
            "trigger.reset",
            {"side": "left", "uniq": "e8:47:3a:00:00:f6"},
        )


# ---------------------------------------------------------------------------
# Lightbar — mesmo payload, outro arquivo de aba
# ---------------------------------------------------------------------------


class TestLightbarEntregaOsDestinos:
    def test_led_set_detalhado_traz_as_duas_listas(self, daemon_diz) -> None:  # type: ignore[no-untyped-def]
        espiao = daemon_diz(LED_MESA_VAZIA)

        corpo = ipc_bridge.led_set_detalhado((255, 0, 0), brightness=0.5)

        assert corpo == LED_MESA_VAZIA
        assert ipc_bridge.destinos_da_aplicacao(corpo) == ([], [])
        assert espiao.chamadas[0] == (
            "led.set",
            {"rgb": [255, 0, 0], "brightness": 0.5},
        )

    def test_player_leds_detalhado_traz_bits_e_destinos(self, daemon_diz) -> None:  # type: ignore[no-untyped-def]
        daemon_diz(PLAYER_LEDS_GUARDADO)

        corpo = ipc_bridge.player_leds_set_detalhado(
            (True, False, False, False, False), uniq="e8:47:3a:00:00:f6"
        )

        assert corpo is not None
        assert corpo["bits"] == [True, False, False, False, False]
        assert ipc_bridge.destinos_da_aplicacao(corpo) == ([], ["e8:47:3a:00:00:f6"])

    def test_daemon_offline_volta_none_e_nao_dict_vazio(self, daemon_diz) -> None:  # type: ignore[no-untyped-def]
        """``None`` é "não respondeu"; ``{}`` seria "respondeu nada" — diferente."""
        daemon_diz(ConnectionRefusedError("daemon fora"))

        assert ipc_bridge.led_set_detalhado((1, 2, 3)) is None
        assert ipc_bridge.player_leds_set_detalhado((False,) * 5) is None


# ---------------------------------------------------------------------------
# Microfone e alto-falante — "sem fonte" deixa de ser "daemon offline"
# ---------------------------------------------------------------------------


class TestMicrofoneEntregaAResposta:
    def test_sem_fonte_deixa_de_ser_igual_a_daemon_offline(self, daemon_diz) -> None:  # type: ignore[no-untyped-def]
        daemon_diz(MIC_VOLUME_SEM_FONTE)
        sem_fonte = ipc_bridge.mic_volume_set_detalhado(60)

        daemon_diz(FileNotFoundError("socket ausente"))
        offline = ipc_bridge.mic_volume_set_detalhado(60)

        assert sem_fonte == MIC_VOLUME_SEM_FONTE
        assert offline is None
        assert sem_fonte != offline, (
            "os dois casos voltavam False e a janela mandava procurar um daemon "
            "que estava vivo"
        )

    def test_volume_lido_de_volta_chega(self, daemon_diz) -> None:  # type: ignore[no-untyped-def]
        daemon_diz(MIC_VOLUME_ALVO_HONRADO)

        corpo = ipc_bridge.mic_volume_set_detalhado(99, uniq="e8:47:3a:00:00:f6")

        assert corpo is not None
        assert corpo["volume"] == 62, "a LEITURA de volta, não o número que mandamos"
        assert corpo["fonte"]

    def test_alvo_honrado_distingue_a_rota_global(self, daemon_diz) -> None:  # type: ignore[no-untyped-def]
        daemon_diz(MIC_VOLUME_ROTA_GLOBAL)
        global_ = ipc_bridge.mic_volume_set_detalhado(62, uniq="e8:47:3a:00:00:f6")

        daemon_diz(MIC_VOLUME_ALVO_HONRADO)
        honrado = ipc_bridge.mic_volume_set_detalhado(62, uniq="e8:47:3a:00:00:f6")

        assert ipc_bridge.alvo_honrado(global_) is False
        assert ipc_bridge.alvo_honrado(honrado) is True

    def test_alvo_honrado_nao_confunde_nao_sei_com_nao(self) -> None:
        assert ipc_bridge.alvo_honrado({"status": "ok"}) is None
        assert ipc_bridge.alvo_honrado(None) is None

    def test_mic_set_separa_sem_controle_de_offline(self, daemon_diz) -> None:  # type: ignore[no-untyped-def]
        daemon_diz(MIC_SET_SEM_CONTROLE)
        assert ipc_bridge.mic_set_detalhado(True) == MIC_SET_SEM_CONTROLE

        daemon_diz(FileNotFoundError("socket ausente"))
        assert ipc_bridge.mic_set_detalhado(True) is None

    def test_speaker_detalhado_entrega_o_corpo(self, daemon_diz) -> None:  # type: ignore[no-untyped-def]
        espiao = daemon_diz(SPEAKER_SEM_CONTROLE)

        corpo = ipc_bridge.speaker_set_detalhado(volume=80, uniq="e8:47:3a:00:00:f6")

        assert corpo == SPEAKER_SEM_CONTROLE
        assert espiao.chamadas[0] == (
            "speaker.set",
            {"volume": 80, "uniq": "e8:47:3a:00:00:f6"},
        )

    def test_speaker_detalhado_mantem_a_guarda_do_release(self, daemon_diz) -> None:  # type: ignore[no-untyped-def]
        espiao = daemon_diz(SPEAKER_SEM_CONTROLE)

        with pytest.raises(ValueError, match="release"):
            ipc_bridge.speaker_set_detalhado(volume=80, release=True)

        assert espiao.chamadas == [], "a guarda tem de barrar ANTES do socket"


class TestRumblePolicyEntregaOCorpo:
    def test_policy_chega(self, daemon_diz) -> None:  # type: ignore[no-untyped-def]
        daemon_diz(RUMBLE_POLICY_OK)

        assert ipc_bridge.rumble_policy_set_detalhado("economia") == (
            True,
            None,
            RUMBLE_POLICY_OK,
        )


# ---------------------------------------------------------------------------
# O CAMINHO FELIZ INTACTO — nenhum chamador de hoje muda de resposta
# ---------------------------------------------------------------------------


class TestOsInvolucrosDeHojeNaoMudaram:
    """A leva é ADITIVA: quem já chamava continua recebendo o que recebia."""

    def test_trigger_set_checked_continua_dupla(self, daemon_diz) -> None:  # type: ignore[no-untyped-def]
        daemon_diz(TRIGGER_MESA_VAZIA)
        assert ipc_bridge.trigger_set_checked("left", "Rigid", [2, 8]) == (True, None)

        daemon_diz(IpcError(CODE_INVALID_PARAMS, "Fim <= Início"))
        assert ipc_bridge.trigger_set_checked("left", "Rigid", [8, 2]) == (
            False,
            "Fim <= Início",
        )

    def test_trigger_set_checked_ignora_a_frase_do_corpo(self, daemon_diz) -> None:  # type: ignore[no-untyped-def]
        """O invólucro antigo é NARROWING puro — não ganhou motivo novo.

        Se ele passasse a devolver a frase do corpo, a aba Gatilhos começaria a
        pintar recusa onde hoje pinta sucesso sem ninguém ter olhado a tela.
        """
        daemon_diz(TRIGGER_RECUSADO)
        assert ipc_bridge.trigger_set_checked("left", "Off", []) == (True, None)

    def test_trigger_reset_continua_dupla(self, daemon_diz) -> None:  # type: ignore[no-untyped-def]
        daemon_diz(TRIGGER_MESA_VAZIA)
        assert ipc_bridge.trigger_reset() == (True, None)

    def test_trigger_set_bool_continua_bool(self, daemon_diz) -> None:  # type: ignore[no-untyped-def]
        daemon_diz(TRIGGER_MESA_VAZIA)
        assert ipc_bridge.trigger_set("left", "Rigid", [2, 8]) is True

    def test_led_e_player_leds_continuam_bool(self, daemon_diz) -> None:  # type: ignore[no-untyped-def]
        daemon_diz(LED_MESA_VAZIA)
        assert ipc_bridge.led_set((1, 2, 3)) is True
        assert ipc_bridge.player_leds_set((True,) * 5) is True

        daemon_diz(OSError("socket morto"))
        assert ipc_bridge.led_set((1, 2, 3)) is False
        assert ipc_bridge.player_leds_set((True,) * 5) is False

    def test_led_set_continua_true_com_resposta_que_nao_e_dicionario(
        self, daemon_diz
    ) -> None:  # type: ignore[no-untyped-def]
        """Contrato v1 do ``led_set``: o ``bool`` é do TRANSPORTE, não do corpo."""
        daemon_diz(None)
        assert ipc_bridge.led_set((1, 2, 3)) is True
        assert ipc_bridge.led_set_detalhado((1, 2, 3)) is None

    @pytest.mark.parametrize(
        ("resposta", "esperado"),
        [
            ({"status": "ok", "audio": None, "mic_mudo_desejado": True}, True),
            (MIC_SET_SEM_CONTROLE, False),
            (None, False),
        ],
    )
    def test_mic_set_bool_inalterado(self, daemon_diz, resposta, esperado) -> None:  # type: ignore[no-untyped-def]
        daemon_diz(resposta)
        assert ipc_bridge.mic_set(True) is esperado

    @pytest.mark.parametrize(
        ("resposta", "esperado"),
        [
            (MIC_VOLUME_ALVO_HONRADO, True),
            (MIC_VOLUME_SEM_FONTE, False),
            (FileNotFoundError("sem socket"), False),
        ],
    )
    def test_mic_volume_set_bool_inalterado(self, daemon_diz, resposta, esperado) -> None:  # type: ignore[no-untyped-def]
        daemon_diz(resposta)
        assert ipc_bridge.mic_volume_set(60) is esperado

    @pytest.mark.parametrize(
        ("resposta", "esperado"),
        [
            ({"status": "ok", "speaker": {"volume": 80}}, True),
            (SPEAKER_SEM_CONTROLE, False),
            (ConnectionResetError("caiu"), False),
        ],
    )
    def test_speaker_set_bool_inalterado(self, daemon_diz, resposta, esperado) -> None:  # type: ignore[no-untyped-def]
        daemon_diz(resposta)
        assert ipc_bridge.speaker_set(volume=80) is esperado

    def test_speaker_set_mantem_o_valueerror(self) -> None:
        with pytest.raises(ValueError, match="release"):
            ipc_bridge.speaker_set(volume=10, release=True)

    def test_rumble_policy_set_checked_continua_dupla(self, daemon_diz) -> None:  # type: ignore[no-untyped-def]
        daemon_diz(RUMBLE_POLICY_OK)
        assert ipc_bridge.rumble_policy_set_checked("economia") == (True, None)
        assert ipc_bridge.rumble_policy_set("economia") is True
