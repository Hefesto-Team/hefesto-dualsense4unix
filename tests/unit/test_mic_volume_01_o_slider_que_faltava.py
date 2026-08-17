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

_SOURCES_COM_CABO = (
    "42\talsa_input.usb-Sony_Interactive_Entertainment_Wireless_Controller"
    "-00.analog-stereo\tPipeWire\ts16le 1ch 48000Hz\tSUSPENDED\n"
    "43\talsa_input.pci-0000_0c_00.4.analog-stereo\tPipeWire\ts32le 2ch\tRUNNING\n"
)
_SOURCES_COM_PONTE_BT = (
    "43\talsa_input.pci-0000_0c_00.4.analog-stereo\tPipeWire\ts32le 2ch\tRUNNING\n"
    "108048\thefesto_dualsense_bt_aabbcc\tPipeWire\ts16le 1ch 48000Hz\tRUNNING\n"
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
        assert "Wireless_Controller" in achado

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
        """Mesmo contrato do `mouse` e do `speaker`.

        Um perfil que não pediu volume não pode mexer no microfone ao ser
        ativado — a queixa "a config que eu deixo nunca é respeitada" vale nos
        dois sentidos: não respeitar o que ela pôs, e impor o que ela não pediu.
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
