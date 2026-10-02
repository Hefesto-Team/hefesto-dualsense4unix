"""TESTAR-O-MICROFONE-01 — o 🎙 deixa de calar e passa a ouvir."""

from __future__ import annotations

import pathlib

PAGINA = pathlib.Path(
    "src/hefesto_dualsense4unix/interface/paginas/02-controles.html"
)
GERADOR = pathlib.Path("src/hefesto_dualsense4unix/interface/aba02.py")


class TestOBotaoTrocouDeAtoNaTela:
    """*A cura escrita e nunca ligada* é o defeito mais caro desta casa."""

    def test_o_glifo_do_mic_nao_cala_mais(self):
        """MORDIDA: devolver `data-gesto="mudo" data-mudo="microfone"`."""
        pagina = PAGINA.read_text(encoding="utf-8")
        assert 'data-mudo="microfone"' not in pagina, (
            "o 🎙 voltou a calar — e o botão do plástico já faz isso"
        )
        assert 'data-gesto="mic-retorno"' in pagina, (
            "o gesto do retorno não chegou à página publicada"
        )

    def test_o_alto_falante_continua_com_o_mudo(self):
        """**A régua que impede a cura de passar do ponto.**"""
        pagina = PAGINA.read_text(encoding="utf-8")
        assert 'data-mudo="alto-falante"' in pagina, (
            "o ♪ perdeu o mudo — e ele não tem botão no plástico"
        )

    def test_a_dica_diz_onde_se_cala_agora(self):
        """Tirar o ato sem dizer para onde ele foi deixa quem lê procurando."""
        fonte = GERADOR.read_text(encoding="utf-8")
        i = fonte.index("DICA_MIC_TESTAR")
        dica = fonte[i : i + 400]
        assert "controle" in dica.lower()
        assert "reinicie o Hefesto" not in dica, (
            "a dica ainda manda reiniciar — o botão não confisca mais nada"
        )

    def test_o_gesto_esta_registrado_no_pacote(self):
        """MORDIDA: tirar o decorador `@gesto`."""
        fonte = pathlib.Path(
            "src/hefesto_dualsense4unix/interface/pacotes/a02_controles.py"
        ).read_text(encoding="utf-8")
        assert '@gesto("02-controles.html", "mic-retorno")' in fonte
        assert "def mic_retorno(" in fonte
        assert "monitor_do_microfone.ligar(" in fonte, (
            "o gesto não chama o ato — é a cura escrita e nunca ligada"
        )


class TestOMudoNaoVIRAFALTADEVOZ:
    """**21/09/2026, medido na mesa dela com os quatro na mão.**"""

    def _gesto(self):
        fonte = pathlib.Path(
            "src/hefesto_dualsense4unix/interface/pacotes/a02_controles.py"
        ).read_text(encoding="utf-8")
        i = fonte.index("def mic_retorno(")
        return fonte[i : fonte.index("\n@gesto", i)]

    def test_o_gesto_pergunta_o_mudo_antes_de_gravar(self):
        """MORDIDA: tire a guarda. O gesto volta a abrir o microfone de um"""
        corpo = self._gesto()
        assert "_faces_do_microfone(" in corpo, (
            "o gesto não pergunta se o microfone está calado antes de gravar")
        assert corpo.index("_faces_do_microfone(") < corpo.index(
            "monitor_do_microfone.ligar("
        ), "a pergunta vem DEPOIS de abrir o retorno — o microfone calado abre"

    def test_a_recusa_manda_ao_botao_do_plastico_e_nao_a_boca(self):
        """O recado diz o que FAZER, e onde."""
        corpo = self._gesto()
        i = corpo.index("_faces_do_microfone(")
        recusa = corpo[i : i + 900]
        assert "botão" in recusa and "controle" in recusa, (
            "a recusa não diz onde ligar o microfone")
        assert "fale mais perto" not in recusa, (
            "a recusa manda aproximar a boca de um microfone desligado")

    def test_o_nao_sei_nao_recusa(self):
        """*Não sei* não é *está mudo*."""
        from hefesto_dualsense4unix.interface.pacotes.a02_controles import (
            _faces_do_microfone,
        )

        calado, nao_sei = _faces_do_microfone({})
        assert nao_sei and not calado, (
            "um estado que ninguém leu está sendo lido como «mudo»")
        corpo = self._gesto()
        assert "_nao_sei" in corpo, (
            "o gesto passou a recusar também quando NÃO SABE — o botão morre "
            "nos primeiros tiques de toda aba")

    def test_o_mudo_do_plastico_sozinho_ja_recusa(self):
        """As quatro faces são um OU: qualquer uma calada cala o conjunto."""
        from hefesto_dualsense4unix.interface.pacotes.a02_controles import (
            _faces_do_microfone,
        )

        calado, _ = _faces_do_microfone(
            {"mic_mudo": True, "canal_ativo": True, "canal_mudo": False})
        assert calado
        vivo, _ = _faces_do_microfone(
            {"mic_mudo": False, "canal_ativo": True, "canal_mudo": False})
        assert not vivo


class TestOLeitorLEOFORMATOQueOParserConhece:
    """**21/09/2026 — o botão calou por uma palavra que faltava no comando.**"""

    FONTE = pathlib.Path(
        "src/hefesto_dualsense4unix/integrations/teste_do_microfone.py")

    CURTA = (
        "40\talsa_output.pci-0000_0a_00.1.hdmi-stereo.monitor\tPipeWire\t"
        "s16le 2ch 48000Hz\tIDLE\n"
        "71\thefesto_mic_000001\tPipeWire\ts16le 1ch 48000Hz\tRUNNING\n")

    LONGA = (
        "Source #71\n"
        "\tState: RUNNING\n"
        "\tName: hefesto_mic_000001\n"
        "\tDescription: Microfone do Controle 1\n"
        "\tDriver: PipeWire\n")

    def test_o_comando_pede_o_formato_curto(self):
        """MORDIDA: tire o `"short"` do argv. Os quatro controles da mesa dela"""
        fonte = self.FONTE.read_text(encoding="utf-8")
        assert '["pactl", "list", "short", "sources"]' in fonte, (
            "o leitor voltou ao formato longo — `fontes_dualsense` não o "
            "parseia, e o botão cala com o microfone de pé")

    def test_a_saida_curta_acha_o_no_e_a_longa_nao(self):
        """**A régua que prova a causa, e não só a cura.**"""
        from hefesto_dualsense4unix.integrations.teste_do_microfone import (
            fonte_do_controle,
        )

        assert fonte_do_controle(
            "aa:bb:cc:00:00:01", saida_pactl=self.CURTA) == "hefesto_mic_000001"
        assert fonte_do_controle(
            "aa:bb:cc:00:00:01", saida_pactl=self.LONGA) is None, (
            "o parser passou a aceitar o formato longo — esta régua deixou de "
            "medir o que quebrou em 21/09")

    def test_o_monitor_nao_vira_microfone(self):
        """Medir o `.monitor` faria o nível do mic subir com a trilha do jogo."""
        from hefesto_dualsense4unix.integrations.teste_do_microfone import (
            fonte_do_controle,
        )

        so_monitor = (
            "40\talsa_output.pci-0000_0a_00.1.hdmi-stereo.monitor\tPipeWire\t"
            "s16le 2ch 48000Hz\tIDLE\n")
        assert fonte_do_controle(
            "aa:bb:cc:00:00:01", saida_pactl=so_monitor) is None
