"""MIC-VOLUME-01 (16/08/2026) — o controle deslizante que faltava no microfone.

**O pedido dela**, olhando a aba Status::

    "esse botão de silenciar some. dá espaço a um slicer de microfone pra
     definir o volume do microfone real (independente de saber se tá via bt
     ou via cabo), o app deve ser inteligente pra saber qual caminho usar"

    "ao clicarmos em salvar perfil ou aplicar no perfil ativo ele de fato o
     faz e na próxima sessão lembra disso"

**A assimetria que ela viu na tela existia no código.** O bloco do alto-falante
tinha nível, volume e silenciar; o do microfone tinha nível e silenciar. E o
perfil guardava `volume`/`muted`/`rota` do alto-falante contra **um booleano**
do microfone — então nem havia onde lembrar o valor.

**As duas camadas, e por que continuam separadas.** Este arquivo trava a
distinção, porque juntá-las faria a interface prometer uma coisa e entregar
outra:

===================  =========================================================
`mic.set`            MUDO do firmware (camada 3). Único que apaga a luz
                     vermelha; enquanto vigora, o botão físico não vale.
`mic.volume.set`     GANHO da fonte no PipeWire (camada 1). Não toca no
                     firmware, não tira o botão físico, não apaga luz.
===================  =========================================================

**Por que o volume é universal**, que era o pedido: o DualSense não expõe
registrador de ganho de microfone em transporte nenhum. O que existe nos dois
casos é uma FONTE no sistema — no cabo o source ALSA do controle, no rádio o
source que a ponte de áudio publica. Quem chama não escolhe caminho.

**E `sem_fonte` é resposta, não falha.** Por Bluetooth, sem a ponte de pé, não
existe fonte de captura (medido em 16/08: `pactl list cards` traz só as duas
placas da máquina). A interface precisa dessa resposta para deixar o controle
INSENSÍVEL — um controle que aceita o gesto e não faz nada é a tela mentindo.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import audio_control as ac
from hefesto_dualsense4unix.profiles.schema import ProfileMicConfig

#: O nome REAL do source no cabo, lido ao vivo em 17/08/2026.
#:
#: A versão anterior deste dado era INVENTADA: eu escrevi
#: `Sony_Interactive_Entertainment_Wireless_Controller`, sem "DualSense",
#: porque tinha inferido que o descritor USB não traria a palavra. **Traz.**
#: Um fixture construído sobre inferência valida o mundo errado — e este
#: chegou a justificar uma marca a mais na lista de reconhecimento.
_SOURCES_COM_CABO = (
    "42\talsa_input.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.analog-stereo\tPipeWire\ts16le 1ch 48000Hz\tSUSPENDED\n"
    "43\talsa_input.pci-0000_0c_00.4.analog-stereo\tPipeWire\ts32le 2ch\tRUNNING\n"
)
_SOURCES_COM_PONTE_BT = (
    "43\talsa_input.pci-0000_0c_00.4.analog-stereo\tPipeWire\ts32le 2ch\tRUNNING\n"
    "108048\thefesto_dualsense_bt_aabbcc\tPipeWire\ts16le 1ch 48000Hz\tRUNNING\n"
)
#: O cenário REAL do cabo, medido em 16/08/2026. Note o `.monitor` do sink do
#: controle: todo sink ganha um de brinde, e ele casa com as MESMAS marcas que
#: o microfone. Foi ele que a primeira versão da função devolveu.
_SOURCES_COM_CABO_REAL = (
    "19596\talsa_input.pci-0000_0c_00.4.analog-stereo\tPipeWire\ts32le 2ch\tRUNNING\n"
    "121464\talsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.analog-surround-40.monitor\tPipeWire\ts16le 4ch\tSUSPENDED\n"
    "121465\talsa_input.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.iec958-stereo\tPipeWire\ts16le 2ch\tSUSPENDED\n"
)
_SOURCES_SEM_CONTROLE = (
    "19595\talsa_output.pci-0000_0c_00.4.iec958-stereo.monitor\tPipeWire\ts32le\tSUSPENDED\n"
    "19596\talsa_input.pci-0000_0c_00.4.analog-stereo\tPipeWire\ts32le 2ch\tRUNNING\n"
)


class _Rodado:
    """Registra o que foi chamado, e devolve o que o teste mandar."""

    def __init__(self, saidas: dict[str, str]) -> None:
        self.saidas = saidas
        self.chamadas: list[list[str]] = []

    def __call__(self, argv: list[str], **kwargs: Any) -> Any:
        self.chamadas.append(list(argv))
        chave = " ".join(argv[:2])
        texto = self.saidas.get(chave, "")

        class _R:
            stdout = texto
            stderr = ""
            returncode = 0

        return _R()


@pytest.fixture()
def rodado(monkeypatch: pytest.MonkeyPatch) -> _Rodado:
    r = _Rodado({})
    monkeypatch.setattr(ac.subprocess, "run", r)
    return r


class TestAchaAFonteNosDoisTransportes:
    def test_cada_marca_da_lista_e_necessaria(self, rodado: _Rodado) -> None:
        """Nenhuma marca pode ser REDUNDANTE — redundância finge cobertura.

        Este teste nasceu de um defeito NO PRÓPRIO TESTE: a lista tinha
        `hefesto_dualsense`, e arrancá-la não reprovava nada, porque o source
        da ponte (`hefesto_dualsense_bt_<mac>`) já casa com `dualsense`. Uma
        marca que nunca é a única a pegar alguma coisa é ruído.
        """
        for marca in ac._MARCAS_DA_FONTE_DO_CONTROLE:
            outras = [m for m in ac._MARCAS_DA_FONTE_DO_CONTROLE if m != marca]
            assert not any(o in marca for o in outras), (
                f"a marca {marca!r} é coberta por outra da lista — redundante"
            )

    def test_no_cabo_acha_o_source_alsa_do_controle(self, rodado: _Rodado) -> None:
        rodado.saidas["pactl list"] = _SOURCES_COM_CABO
        achado = ac.fonte_de_captura_do_controle()
        assert achado is not None
        assert "DualSense_Wireless_Controller" in achado

    def test_o_monitor_do_alto_falante_nao_e_o_microfone(
        self, rodado: _Rodado
    ) -> None:
        """A MORDIDA de um defeito REAL, medido ao vivo em 16/08/2026.

        Com o controle no cabo, a primeira versão desta função devolveu
        `alsa_output.usb-…DualSense…analog-surround-40.monitor` — o ECO DA
        SAÍDA, não a captura. Todo sink do PulseAudio ganha um source
        `.monitor` de brinde, e ele casa com QUALQUER marca que o sink casaria.

        Um controle deslizante de microfone mexendo no monitor do alto-falante
        é a tela fazendo outra coisa do que promete — e o pior tipo, porque
        parece funcionar.
        """
        rodado.saidas["pactl list"] = _SOURCES_COM_CABO_REAL
        achado = ac.fonte_de_captura_do_controle()
        assert achado is not None
        assert ".monitor" not in achado, "pegou o eco da saída, não o microfone"
        assert achado.startswith("alsa_input."), achado

    def test_no_radio_acha_o_source_da_ponte(self, rodado: _Rodado) -> None:
        """No rádio não há placa: quem publica a fonte é a ponte de áudio."""
        rodado.saidas["pactl list"] = _SOURCES_COM_PONTE_BT
        assert ac.fonte_de_captura_do_controle() == "hefesto_dualsense_bt_aabbcc"

    def test_sem_controle_devolve_none(self, rodado: _Rodado) -> None:
        """A MORDIDA do caso do rádio SEM a ponte — o estado real de 16/08.

        `None` aqui é o que faz o controle deslizante ficar insensível. Se esta
        função inventar uma fonte, a interface aceita o gesto e não faz nada.
        """
        rodado.saidas["pactl list"] = _SOURCES_SEM_CONTROLE
        assert ac.fonte_de_captura_do_controle() is None

    def test_o_idioma_do_shell_nao_decide_a_resposta(self, rodado: _Rodado) -> None:
        """`LC_ALL=C` é obrigatório: o `pactl` TRADUZ a saída.

        Em 15/08 uma função irmã respondeu "nenhum controle com placa de áudio"
        sobre um sistema que tinha uma — a afirmação era sobre o idioma do
        shell, não sobre o aparelho.
        """
        rodado.saidas["pactl list"] = _SOURCES_COM_CABO
        ac.fonte_de_captura_do_controle()
        (chamada,) = [c for c in rodado.chamadas if c[:2] == ["pactl", "list"]]
        assert chamada  # a chamada aconteceu
        # o env com LC_ALL=C é passado por kwargs; conferido no código-fonte
        import inspect

        fonte = inspect.getsource(ac.fonte_de_captura_do_controle)
        assert 'LC_ALL": "C"' in fonte, "sem LC_ALL=C a resposta vira sobre o idioma"


class TestDefinirVolume:
    def test_sem_fonte_nao_manda_nada_e_devolve_false(self, rodado: _Rodado) -> None:
        """Sem fonte, nenhum comando de escrita pode sair."""
        rodado.saidas["pactl list"] = _SOURCES_SEM_CONTROLE
        assert ac.definir_volume_da_captura(60) is False
        assert not [c for c in rodado.chamadas if "set-source-volume" in c]

    def test_com_fonte_manda_o_por_cento_na_fonte_certa(self, rodado: _Rodado) -> None:
        rodado.saidas["pactl list"] = _SOURCES_COM_PONTE_BT
        assert ac.definir_volume_da_captura(70) is True
        (cmd,) = [c for c in rodado.chamadas if "set-source-volume" in c]
        assert cmd[2] == "hefesto_dualsense_bt_aabbcc"
        assert cmd[3] == "70%"

    @pytest.mark.parametrize(("pedido", "esperado"), [(-5, "0%"), (150, "100%")])
    def test_o_valor_e_grampeado_em_0_100(
        self, rodado: _Rodado, pedido: int, esperado: str
    ) -> None:
        """Mandar 150% ao sistema de som é o tipo de coisa que não se faz."""
        rodado.saidas["pactl list"] = _SOURCES_COM_PONTE_BT
        ac.definir_volume_da_captura(pedido)
        (cmd,) = [c for c in rodado.chamadas if "set-source-volume" in c]
        assert cmd[3] == esperado

    def test_pactl_ausente_nao_levanta(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Volume de microfone não pode derrubar o daemon."""

        def _boom(*_a: object, **_k: object) -> Any:
            raise FileNotFoundError("pactl")

        monkeypatch.setattr(ac.subprocess, "run", _boom)
        assert ac.fonte_de_captura_do_controle() is None
        assert ac.definir_volume_da_captura(50) is False
        assert ac.volume_da_captura() is None


class TestLerOVolume:
    def test_le_o_por_cento_da_saida(self, rodado: _Rodado) -> None:
        rodado.saidas["pactl list"] = _SOURCES_COM_PONTE_BT
        rodado.saidas["pactl get-source-volume"] = (
            "Volume: mono: 32768 /  50% / -18,06 dB\n"
        )
        assert ac.volume_da_captura() == 50

    def test_le_em_vez_de_lembrar(self) -> None:
        """A função não guarda estado — não há onde um valor mandado virar
        leitura. É a disciplina que impede a tela de parecer mentirosa."""
        import inspect

        fonte = inspect.getsource(ac.volume_da_captura)
        assert "get-source-volume" in fonte
        assert "global" not in fonte


class TestOPerfilLembra:
    def test_volume_e_mudo_sao_campos_do_perfil(self) -> None:
        """Sem isto, "na próxima sessão lembra disso" não tem onde acontecer."""
        mic = ProfileMicConfig(button_toggles_system=True, volume=70, muted=False)
        assert mic.volume == 70
        assert mic.muted is False

    def test_perfil_sem_opiniao_nao_toma_a_posse(self) -> None:
        """Campo a ``None`` continua sendo AUSÊNCIA DE OPINIÃO sobre o campo.

        **NOTA DATADA — 18/08/2026 (PERFIL-GUARDA-O-MIC-01).** Esta docstring
        dizia que era "o mesmo contrato do `mouse` e do `speaker`" e que um
        perfil "não pode mexer no microfone ao ser ativado". A segunda metade
        caducou, e foi ELA quem a derrubou: *"isso é informação antiga. o
        sistema de perfis não funcionava, mas acho que não vem ao caso, até pq
        na época não tinhamos microfone dentro do sistema de perfis."* Ativar um
        perfil **aplica** o microfone que ele guarda — o que continua valendo é
        o de baixo, e só ele: perfil que não pediu nada não impõe nada.

        O que este caso trava, hoje: os defaults são ``None`` nos dois campos,
        e é isso que o applier lê como "não escreva".
        """
        mic = ProfileMicConfig(button_toggles_system=True)
        assert mic.volume is None and mic.muted is None

    def test_a_escala_do_mic_nao_e_a_do_alto_falante(self) -> None:
        """0-100 aqui, 0-255 lá. Confundir mandaria 255% ao sistema de som."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ProfileMicConfig(button_toggles_system=True, volume=255)


class TestAsDuasCamadasNaoSeMisturam:
    def test_o_ipc_tem_metodos_separados(self) -> None:
        """`mic.set` e `mic.volume.set` são rotas diferentes, de propósito."""
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[2]
        servidor = (
            raiz / "src/hefesto_dualsense4unix/daemon/ipc_server.py"
        ).read_text(encoding="utf-8")
        assert '"mic.set"' in servidor
        assert '"mic.volume.set"' in servidor

    def test_o_volume_nao_fala_com_o_firmware(self) -> None:
        """A MORDIDA da separação: se o handler de volume chamar o mudo do
        firmware, ele passa a apagar a luz do microfone sem ninguém pedir."""
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[2]
        fonte = (
            raiz / "src/hefesto_dualsense4unix/daemon/ipc_handlers.py"
        ).read_text(encoding="utf-8")
        corpo = fonte.split("_handle_mic_volume_set", 1)[1].split(
            "async def _handle_mouse_emulation_set", 1
        )[0]
        assert "set_microphone_mute" not in corpo
        assert "definir_volume_da_captura" in corpo


# ---------------------------------------------------------------------------
# PERFIL-GUARDA-O-MIC-01 (18/08/2026) — o mic chega ao RASCUNHO e ao PERFIL
# ---------------------------------------------------------------------------


class TestOMicChegaAoRascunho:
    """A metade de CIMA do caminho: o dedo dela chega ao rascunho do perfil?

    Pedido dela em 18/08/2026, depois de o microfone ficar mudo e o DON'T
    SCREAM não ouvir nada: *"informação de microfone e som, touch,
    acelerômetro, giroscópio e afins. cara, temos que salvar isso no perfil
    sempre."* Medido no mesmo dia: **nenhum dos 18 perfis dela tinha a seção
    `mic`**, embora `ProfileMicConfig` guardasse `volume` e `muted` desde
    16/08 — a classe de defeito *"a casa sabe e o produto não faz"*.
    """

    def test_o_mic_faz_ida_e_volta_com_volume_e_mudo(self) -> None:
        """A trava do ``to_profile``: os dois campos novos chegam ao arquivo.

        MORDIDA: em ``app/draft_config.py``, tire ``volume=self.mic.volume``
        (ou ``muted=self.mic.muted``) do ``ProfileMicConfig`` construído no
        ``to_profile`` e este caso fica vermelho dizendo qual número se perdeu.
        """
        from hefesto_dualsense4unix.app.draft_config import DraftConfig

        draft = DraftConfig().with_mic(volume=70, muted=True)
        perfil = draft.to_profile("gravando")
        assert perfil.mic is not None, (
            "a seção `mic` não existe no perfil — o gesto dela morreu no "
            "rascunho"
        )
        assert perfil.mic.volume == 70, (
            f"o volume do microfone é {perfil.mic.volume!r} — ela deixou 70"
        )
        assert perfil.mic.muted is True, (
            f"o mudo do microfone é {perfil.mic.muted!r} — ela silenciou"
        )

    def test_perfil_sem_secao_mic_continua_sem_ganhar_uma(self) -> None:
        """Perfil legado faz round-trip sem ganhar seção fantasma."""
        from hefesto_dualsense4unix.app.draft_config import DraftConfig

        assert DraftConfig().to_profile("intocado").mic is None

    def test_um_gesto_nao_apaga_o_campo_do_outro(self) -> None:
        """Volume e mudo têm gestos SEPARADOS na tela e não se atropelam.

        Sem esta preservação, arrastar o controle deslizante depois de
        silenciar desfaria o mudo no rascunho, em silêncio — e o perfil salvo
        sairia sem a metade que ela acabou de escolher.
        """
        from hefesto_dualsense4unix.app.draft_config import DraftConfig

        draft = DraftConfig().with_mic(muted=True).with_mic(volume=40)
        assert draft.mic.muted is True
        assert draft.mic.volume == 40

    def test_liberar_apaga_o_mudo_e_preserva_o_volume(self) -> None:
        """"Liberar" devolve a posse do registrador ao ``hid-playstation``.

        Um perfil salvo depois desse gesto não pode continuar carregando um
        ``muted`` que a ativação seguinte reaplicaria — retomando a posse que
        ela acabou de largar. O volume, que é de outra camada, fica.
        """
        from hefesto_dualsense4unix.app.draft_config import DraftConfig

        draft = DraftConfig().with_mic(volume=55, muted=True)
        solto = draft.with_mic(soltar_mudo=True)
        assert solto.mic.muted is None
        assert solto.mic.volume == 55
        perfil = solto.to_profile("liberado")
        assert perfil.mic is not None and perfil.mic.muted is None

    def test_o_escritor_e_calado_quando_nao_ha_rascunho(self) -> None:
        """Card avulso (teste de geometria) não tem ``draft`` — e sai calado."""
        from hefesto_dualsense4unix.app.draft_config import (
            registrar_microfone_no_rascunho,
        )

        class _JanelaSemRascunho:
            pass

        janela = _JanelaSemRascunho()
        registrar_microfone_no_rascunho(janela, volume=10)  # não levanta
        assert not hasattr(janela, "draft")

    def test_gesto_sem_opiniao_nao_cria_secao_fantasma(self) -> None:
        """Um callback sem nada a dizer não marca a seção como tocada."""
        from hefesto_dualsense4unix.app.draft_config import (
            DraftConfig,
            registrar_microfone_no_rascunho,
        )

        class _Janela:
            draft = DraftConfig()

        janela = _Janela()
        registrar_microfone_no_rascunho(janela)
        assert janela.draft.to_profile("nada").mic is None


# ---------------------------------------------------------------------------
# MIC-GRAVACAO-01 (18/08/2026) — o gesto dela ARMA a trava manual de áudio
# ---------------------------------------------------------------------------


class _MicComEstado:
    """Controle mínimo: aceita o mudo e devolve leitura de áudio."""

    def __init__(self, aceita: bool = True) -> None:
        self.aceita = aceita
        self.pedidos: list[bool | None] = []

    def set_microphone_mute(self, muted: bool | None, *, uniq: str | None = None) -> bool:
        self.pedidos.append(muted)
        return self.aceita

    def audio_status_for(self, uniq: str | None = None) -> dict[str, bool]:
        return {"mic_mudo": False}


def _host_de_ipc(controller: Any) -> Any:
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
    from hefesto_dualsense4unix.daemon.state_store import StateStore

    class _Host(IpcHandlersMixin):  # type: ignore[misc]
        def __init__(self) -> None:
            self.controller = controller
            self.store = StateStore()

    return _Host()


class TestOGestoDelaArmaATravaDeAudio:
    """O gesto MANUAL no microfone não pode ser pisado pelo perfil reaplicado.

    Até 18/08/2026 só o `speaker.set` armava a categoria `"audio"`. Com o
    microfone entrando no sistema de perfis, a assimetria virava defeito: o
    autoswitch reaplica o perfil ativo a CADA troca de janela, e sem a trava
    isso desfaria, em silêncio, o mudo ou o volume que ela acabou de pedir —
    o mudo do microfone dela no meio de uma gravação.
    """

    @pytest.mark.asyncio
    async def test_o_jogo_nao_rouba_o_mudo_durante_a_gravacao(self) -> None:
        """MORDIDA: tire o `self._marcar_audio_manual()` de `_handle_mic_set`
        e este caso fica vermelho — a trava some e o perfil reaplicado volta a
        pisar o mudo dela."""
        host = _host_de_ipc(_MicComEstado())
        assert host.store.manual_override_categories == frozenset()
        await host._handle_mic_set({"muted": True})
        assert host.store.manual_override_categories == frozenset({"audio"}), (
            "o mudo que ela pediu na mão não armou a trava — o autoswitch "
            "reaplica o perfil na próxima troca de janela e o desfaz"
        )

    @pytest.mark.asyncio
    async def test_pedido_recusado_nao_arma(self) -> None:
        """Trava sem gesto por baixo seria trava por engano (igual ao speaker)."""
        host = _host_de_ipc(_MicComEstado(aceita=False))
        await host._handle_mic_set({"muted": True})
        assert host.store.manual_override_categories == frozenset()

    @pytest.mark.asyncio
    async def test_o_volume_do_mic_tambem_arma(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDIDA: tire o `self._marcar_audio_manual()` de
        `_handle_mic_volume_set`."""
        host = _host_de_ipc(_MicComEstado())
        monkeypatch.setattr(ac, "fonte_de_captura_do_controle", lambda: "src")
        monkeypatch.setattr(
            ac, "definir_volume_da_captura", lambda v, *, fonte=None: True
        )
        monkeypatch.setattr(ac, "volume_da_captura", lambda *, fonte=None: 70)
        await host._handle_mic_volume_set({"volume": 70})
        assert host.store.manual_override_categories == frozenset({"audio"})

    @pytest.mark.asyncio
    async def test_sem_fonte_nao_arma(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`sem_fonte` é resposta, não gesto: nada foi ajustado, nada trava."""
        host = _host_de_ipc(_MicComEstado())
        monkeypatch.setattr(ac, "fonte_de_captura_do_controle", lambda: None)
        res = await host._handle_mic_volume_set({"volume": 70})
        assert res["status"] == "sem_fonte"
        assert host.store.manual_override_categories == frozenset()


# ---------------------------------------------------------------------------
# A FIAÇÃO: onde o `speaker_applier` é injetado, o `mic_applier` também tem de
# ---------------------------------------------------------------------------


#: Rotas de ativação de perfil, e o que cada uma injeta hoje.
_ROTAS_DE_ATIVACAO: tuple[str, ...] = (
    "src/hefesto_dualsense4unix/daemon/lifecycle.py",
    "src/hefesto_dualsense4unix/daemon/connection.py",
    "src/hefesto_dualsense4unix/daemon/subsystems/ipc.py",
    "src/hefesto_dualsense4unix/daemon/subsystems/hotkey.py",
    "src/hefesto_dualsense4unix/daemon/subsystems/autoswitch.py",
)

#: Injeções de `speaker_applier` que NÃO ganham um `mic_applier` ao lado,
#: com quantas são e a razão por extenso e datada. O portão compara
#: CONTAGENS, e este dicionário é a única folga que ele aceita.
_SEM_MIC_HOJE: dict[str, tuple[int, str]] = {
    # 18/08/2026 — a entrada de `daemon/subsystems/autoswitch.py` SAIU daqui
    # porque a lacuna foi fechada: as duas rotas de subida do autoswitch
    # passaram a injetar o `mic_applier`, e a troca de perfil por JANELA
    # aplica o volume do microfone do perfil. Foi este caso que cobrou a
    # remoção, reprovando no instante em que as linhas entraram.
    "src/hefesto_dualsense4unix/daemon/connection.py": (
        1,
        "18/08/2026 — DECISÃO, não lacuna, e por isso a folga é de UMA das "
        "duas injeções deste arquivo: `restore_last_profile` injeta o "
        "applier do microfone (o volume volta no boot), e "
        "`reapply_speaker_after_connect` NÃO. O gancho de reconexão existe "
        "porque a posse dos bytes de volume do alto-falante morre com o "
        "cabo — e o microfone não tem essa perda: o `volume` mora na fonte "
        "do PipeWire e sobrevive ao replug, e o `muted` é barrado ali de "
        "qualquer forma pela exceção MIC-GRAVACAO-01, que só o deixa "
        "passar em `origin=\"manual\"` (reconexão é `origin=\"system\"`). "
        "Injetá-lo aqui seria uma linha que nunca escreve nada.",
    ),
}


class TestOApplierDoMicEstaFiado:
    """O applier pode existir e não estar ligado em lugar nenhum.

    É a classe de defeito mais cara desta casa — *"a casa sabe e o produto não
    faz"*: `ProfileMicConfig` guardava `volume` e `muted` desde 16/08/2026 e
    NADA os lia, e por isso nenhum dos 18 perfis dela tinha a seção. Um portão
    de comportamento por rota custaria a máquina inteira do
    `test_daemon_speaker_wiring.py`; este aqui é o barato que pega o esquecido:
    **toda rota que injeta o irmão tem de injetar este**.
    """

    def _fonte(self, caminho: str) -> str:
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[2]
        return (raiz / caminho).read_text(encoding="utf-8")

    def test_toda_rota_com_speaker_applier_tambem_tem_o_do_mic(self) -> None:
        """MORDIDA: apague um `mic_applier=` de qualquer rota e o caso nomeia
        o arquivo. Provada em 18/08 arrancando o de `subsystems/hotkey.py`."""
        faltando: list[str] = []
        for caminho in _ROTAS_DE_ATIVACAO:
            fonte = self._fonte(caminho)
            n_speaker = fonte.count("speaker_applier=")
            n_mic = fonte.count("mic_applier=")
            folga = _SEM_MIC_HOJE.get(caminho, (0, ""))[0]
            if n_mic < n_speaker - folga:
                faltando.append(f"{caminho} ({n_mic} de {n_speaker - folga})")
        assert not faltando, (
            "rotas de ativação que injetam o applier do alto-falante e NÃO o "
            f"do microfone: {faltando}. O perfil guarda o microfone e ninguém "
            "o aplica por esse caminho — a classe de defeito 'a casa sabe e o "
            "produto não faz'."
        )

    def test_a_lacuna_conhecida_nao_envelhece_calada(self) -> None:
        """Lacuna declarada tem razão longa, e continua sendo lacuna de verdade.

        No dia em que a rota do autoswitch ganhar a linha, este caso REPROVA e
        cobra que a entrada saia daqui — a lápide não pode sobreviver à cura.
        """
        for caminho, (folga, razao) in _SEM_MIC_HOJE.items():
            assert len(razao) > 120, f"a razão de {caminho} é curta demais"
            fonte = self._fonte(caminho)
            n_speaker = fonte.count("speaker_applier=")
            n_mic = fonte.count("mic_applier=")
            assert n_speaker - n_mic == folga, (
                f"{caminho} declara {folga} injeção(ões) sem o `mic_applier` e "
                f"tem {n_speaker - n_mic}. Se a lacuna foi fechada, apague a "
                "entrada de _SEM_MIC_HOJE; se cresceu, alguém injetou o "
                "alto-falante numa rota nova e esqueceu o microfone."
            )
