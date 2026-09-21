"""TESTAR-O-MICROFONE-01 — o 🎙 deixa de calar e passa a ouvir.

A ordem é dela, 20/09/2026:

    "aquele glifo antigo de mic que servia para ligar o microfone volta a tela
     mas ele passa a ter o efeito do testar microfone do discord, ele reflete os
     slicers que vão mostrar no jogo como o microfone é ouvido e após três
     segundos de fala capturada de audio ele reproduz na tela o seu som falado."

E a razão de o calar poder sair:

    "esse botão segue desativando o microfone, não precisamos dele mais na
     interface pq o botão do
     proprio  # noqa-acento: citação literal dela
     controle já o faz e ele reflete isso"
"""

from __future__ import annotations

import array
import pathlib

from hefesto_dualsense4unix.integrations.teste_do_microfone import (
    BLOCO_MS,
    FALA_ALVO_S,
    TETO_S,
    argv_do_gravador,
    argv_do_reprodutor,
    gravar_ate_falar,
    pico_do_bloco,
)

PAGINA = pathlib.Path(
    "src/hefesto_dualsense4unix/interface/paginas/02-controles.html"
)
GERADOR = pathlib.Path("src/hefesto_dualsense4unix/interface/aba02.py")


def _bloco(amplitude: int, ms: int = BLOCO_MS) -> bytes:
    n = int(48_000 * ms / 1000)
    return array.array("h", [amplitude] * n).tobytes()


class _Fonte:
    """Um `parec` de mentira que entrega os blocos que a régua mandar."""

    def __init__(self, blocos: list[bytes]) -> None:
        self._blocos = list(blocos)
        self.morto = False
        self.stdout = self

    def read(self, _n: int) -> bytes:
        return self._blocos.pop(0) if self._blocos else b""

    def kill(self) -> None:
        self.morto = True

    def wait(self, timeout: float = 0) -> int:
        return 0


class TestTresSegundosDeFalaNaoDeRelogio:
    """A diferença que ela escreveu: *"três segundos de FALA capturada"*."""

    def test_o_silencio_nao_anda_o_contador(self):
        """Um minuto de silêncio não fecha o teste.

        MORDIDA: andar o contador com todo bloco, e não só com os de voz.
        """
        silencio = [_bloco(0)] * 200
        relogio = iter([i * 0.04 for i in range(1000)])
        g = gravar_ate_falar(
            "x",
            abrir=lambda _f: _Fonte(silencio),
            relogio=lambda: next(relogio),
        )
        assert g is not None
        assert g.fala_s == 0.0, "o silêncio andou o contador de fala"
        assert g.motivo != "falou"
        assert g.pcm == b"", "devolveu áudio sem ter ouvido voz"

    def test_tres_segundos_de_voz_fecham_o_teste(self):
        """MORDIDA: parar no primeiro bloco com voz."""
        blocos = [_bloco(20_000)] * 200
        relogio = iter([i * 0.04 for i in range(1000)])
        g = gravar_ate_falar(
            "x",
            abrir=lambda _f: _Fonte(blocos),
            relogio=lambda: next(relogio),
        )
        assert g is not None
        assert g.motivo == "falou"
        assert g.fala_s >= FALA_ALVO_S
        assert g.pcm, "falou três segundos e não devolveu áudio"

    def test_a_pausa_entre_palavras_fica_na_gravacao(self):
        """**É o que o Discord devolve, e é o que ela reconhece como a voz.**

        Guardar só os blocos com voz devolveria uma fala picotada, com as
        sílabas coladas — a pessoa não se reconhece.

        MORDIDA: guardar só os blocos acima do limiar.
        """
        # fala, pausa, fala — a pausa é metade do total
        blocos = ([_bloco(20_000)] * 40) + ([_bloco(0)] * 40) + (
            [_bloco(20_000)] * 40
        )
        relogio = iter([i * 0.04 for i in range(1000)])
        g = gravar_ate_falar(
            "x",
            abrir=lambda _f: _Fonte(blocos),
            relogio=lambda: next(relogio),
        )
        assert g is not None and g.motivo == "falou"
        esperado_min = len(_bloco(0)) * 80  # os 40 de voz + os 40 de pausa
        assert len(g.pcm) >= esperado_min, (
            "a pausa foi descartada — a fala volta picotada"
        )


class TestAAusenciaEResposta:
    def test_sem_gravador_devolve_nao_sei_e_nao_zero(self):
        """`None` é "não sei"; `Gravacao` vazia é "ouvi e não havia voz".

        A tela precisa dos dois para não culpar o aparelho por falta nossa.

        MORDIDA: devolver uma `Gravacao` vazia quando o gravador não sobe.
        """
        assert gravar_ate_falar("x", abrir=lambda _f: None) is None

    def test_gravador_sem_stdout_e_colhido(self):
        class _SemSaida:
            stdout = None

            def __init__(self) -> None:
                self.morto = False

            def kill(self) -> None:
                self.morto = True

        morto = _SemSaida()
        assert gravar_ate_falar("x", abrir=lambda _f: morto) is None
        assert morto.morto, "o gravador sem saída ficou vivo segurando o mic"

    def test_o_gravador_morre_mesmo_quando_a_fonte_fecha(self):
        """Um `parec` órfão segura o microfone dela aberto — 39 minutos, em 03/09."""
        fonte = _Fonte([])
        gravar_ate_falar("x", abrir=lambda _f: fonte)
        assert fonte.morto, "o gravador ficou vivo depois do teste"

    def test_ha_teto_e_ele_nao_e_o_relogio_da_fala(self):
        """Sem teto, um teste sem voz nunca termina.

        MORDIDA: tirar o `teto_s` do laço.
        """
        assert TETO_S > FALA_ALVO_S
        blocos = [_bloco(0)] * 10_000
        relogio = iter([i * 1.0 for i in range(100)])
        g = gravar_ate_falar(
            "x",
            abrir=lambda _f: _Fonte(blocos),
            relogio=lambda: next(relogio),
        )
        assert g is not None and g.motivo == "teto"


class TestAsTravasQueEstaCasaJaPagou:
    def test_o_gravador_leva_latencia_explicita(self):
        """Sem ela a voz chega dois segundos atrasada — mordeu duas vezes."""
        assert "--latency-msec=50" in argv_do_gravador("x")

    def test_o_reprodutor_leva_latencia_explicita(self):
        assert "--latency-msec=50" in argv_do_reprodutor()

    def test_sem_device_o_reprodutor_toca_na_saida_padrao(self):
        """Onde ela ouve o jogo — é onde a pergunta dela se responde.

        E um `--device` inexistente sai com ZERO e toca no padrão de qualquer
        jeito, então passar destino errado não dá erro: dá ilusão.
        """
        assert not any(a.startswith("--device=") for a in argv_do_reprodutor())
        assert "--device=x" in argv_do_reprodutor("x")

    def test_o_pico_de_vazio_nao_e_um_falso_zero(self):
        assert pico_do_bloco(b"") == 0.0
        assert pico_do_bloco(_bloco(0)) == 0.0
        assert pico_do_bloco(_bloco(32_767)) > 0.99


class TestOBotaoTrocouDeAtoNaTela:
    """*A cura escrita e nunca ligada* é o defeito mais caro desta casa."""

    def test_o_glifo_do_mic_nao_cala_mais(self):
        """MORDIDA: devolver `data-gesto="mudo" data-mudo="microfone"`."""
        pagina = PAGINA.read_text(encoding="utf-8")
        assert 'data-mudo="microfone"' not in pagina, (
            "o 🎙 voltou a calar — e o botão do plástico já faz isso"
        )
        assert 'data-gesto="mic-testar"' in pagina, (
            "o gesto de testar não chegou à página publicada"
        )

    def test_o_alto_falante_continua_com_o_mudo(self):
        """**A régua que impede a cura de passar do ponto.**

        Ela mandou tirar o mudo DO MICROFONE, não o do ♪ — o alto-falante não
        tem botão no plástico que o cale.

        MORDIDA: tirar o `data-mudo` do ♪ junto.
        """
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
        assert '@gesto("02-controles.html", "mic-testar")' in fonte
        assert "def mic_testar(" in fonte
        assert "testar_e_devolver" in fonte, (
            "o gesto não chama o ato — é a cura escrita e nunca ligada"
        )
