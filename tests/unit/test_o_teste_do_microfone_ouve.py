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
        assert 'data-gesto="mic-retorno"' in pagina, (
            "o gesto do retorno não chegou à página publicada"
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
        assert '@gesto("02-controles.html", "mic-retorno")' in fonte
        assert "def mic_retorno(" in fonte
        assert "monitor_do_microfone.ligar(" in fonte, (
            "o gesto não chama o ato — é a cura escrita e nunca ligada"
        )


class TestOMudoNaoVIRAFALTADEVOZ:
    """**21/09/2026, medido na mesa dela com os quatro na mão.**

    Dois dos quatro microfones entregavam `pico = 0.0000` EXATO — nem ruído de
    fundo —, e o `mic_mudo` do daemon dizia `true` nesses dois. O produto
    estava certo; o que mentia era o recado: o 🎙 gravava quinze segundos de
    silêncio e terminava em *"não ouvi sua voz — fale mais perto do controle"*.

    **A frase culpava quem clicou por um fato que o produto já sabia**, e
    mandava aproximar a boca de um microfone desligado.
    """

    def _gesto(self):
        fonte = pathlib.Path(
            "src/hefesto_dualsense4unix/interface/pacotes/a02_controles.py"
        ).read_text(encoding="utf-8")
        i = fonte.index("def mic_retorno(")
        return fonte[i : fonte.index("\n@gesto", i)]

    def test_o_gesto_pergunta_o_mudo_antes_de_gravar(self):
        """MORDIDA: tire a guarda. O gesto volta a abrir o microfone de um
        controle desligado e a terminar culpando quem clicou.
        """
        corpo = self._gesto()
        assert "_faces_do_microfone(" in corpo, (
            "o gesto não pergunta se o microfone está calado antes de gravar")
        # A ORDEM É O PONTO: perguntar DEPOIS de gravar não pouparia os 15 s,
        # e o recado certo chegaria tarde.
        assert corpo.index("_faces_do_microfone(") < corpo.index(
            "monitor_do_microfone.ligar("
        ), "a pergunta vem DEPOIS de abrir o retorno — o microfone calado abre"

    def test_a_recusa_manda_ao_botao_do_plastico_e_nao_a_boca(self):
        """O recado diz o que FAZER, e onde.

        MORDIDA: devolva *"fale mais perto"* neste ramo.
        """
        corpo = self._gesto()
        i = corpo.index("_faces_do_microfone(")
        recusa = corpo[i : i + 900]
        assert "botão" in recusa and "controle" in recusa, (
            "a recusa não diz onde ligar o microfone")
        assert "fale mais perto" not in recusa, (
            "a recusa manda aproximar a boca de um microfone desligado")

    def test_o_nao_sei_nao_recusa(self):
        """*Não sei* não é *está mudo*.

        `_faces_do_microfone` devolve um par, e só a PRIMEIRA metade recusa:
        um controle cujo `mic_mudo` ainda não chegou tem de poder ser testado
        — é o teste que vai responder. Recusar aqui apagaria o botão nos
        primeiros tiques de toda aba.

        MORDIDA: troque `calado, _nao_sei` por `calado, nao_sei` e recuse nos
        dois. O caso abaixo reprova.
        """
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
        """As quatro faces são um OU: qualquer uma calada cala o conjunto.

        É o estado medido dos controles p2 e p4 dela em 21/09: o bit do
        plástico dizendo `true`, o canal ativo, e o nó entregando zeros.
        """
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
    """**21/09/2026 — o botão calou por uma palavra que faltava no comando.**

    Ela clicou o 🎙 com o microfone ATIVO e o nó de pé, e não ouviu nada. O
    `interface.log` às 01:36: ``[gesto falhou] 02-controles.html · mic-testar:
    não consegui abrir o microfone deste controle para testar``.

    A causa: :func:`fonte_do_controle` rodava ``pactl list sources`` (o formato
    LONGO) e entregava a saída a :func:`fontes_dualsense`, cuja docstring diz,
    com todas as letras, que ela lê ``pactl list sources **short**``. No
    formato longo o ``linha.split("\\t")`` devolve ``["", "Name: hefesto_mic_…"]``
    e o nome sai com o rótulo colado: nenhum nó casa, a lista volta com lixo
    (``Description:``, ``Monitor of Sink:``) e os quatro controles respondem
    ``None``.

    *É a família do instrumento que aponta para outra coisa* — aqui, para o
    formato errado da mesma pergunta.
    """

    FONTE = pathlib.Path(
        "src/hefesto_dualsense4unix/integrations/teste_do_microfone.py")

    #: A saída CURTA, como o `pactl list short sources` a imprime.
    #:
    #: **O sufixo do canal são os SEIS ÚLTIMOS do uniq normalizado** — o
    #: `aa:bb:cc:00:00:01` vira `hefesto_mic_000001`, e não `…_aabbcc`. Escrever
    #: o prefixo aqui faria a régua medir um nó que o produto nunca cria, e ela
    #: reprovaria a cura em vez do defeito.
    CURTA = (
        "40\talsa_output.pci-0000_0a_00.1.hdmi-stereo.monitor\tPipeWire\t"
        "s16le 2ch 48000Hz\tIDLE\n"
        "71\thefesto_mic_000001\tPipeWire\ts16le 1ch 48000Hz\tRUNNING\n")

    #: A mesma informação no formato LONGO — o que o produto pedia até hoje.
    LONGA = (
        "Source #71\n"
        "\tState: RUNNING\n"
        "\tName: hefesto_mic_000001\n"
        "\tDescription: Microfone do Controle 1\n"
        "\tDriver: PipeWire\n")

    def test_o_comando_pede_o_formato_curto(self):
        """MORDIDA: tire o `"short"` do argv. Os quatro controles da mesa dela
        voltam a responder `None` com o microfone ligado.
        """
        fonte = self.FONTE.read_text(encoding="utf-8")
        assert '["pactl", "list", "short", "sources"]' in fonte, (
            "o leitor voltou ao formato longo — `fontes_dualsense` não o "
            "parseia, e o botão cala com o microfone de pé")

    def test_a_saida_curta_acha_o_no_e_a_longa_nao(self):
        """**A régua que prova a causa, e não só a cura.**

        Ela exercita as DUAS saídas contra o mesmo parser: a curta acha, a
        longa não. Sem o segundo `assert` esta régua passaria verde se alguém
        fizesse `fontes_dualsense` aceitar os dois formatos por acidente — e
        aí o número que ela mede deixaria de ser o que quebrou.
        """
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
        """Medir o `.monitor` faria o nível do mic subir com a trilha do jogo.

        MORDIDA: tire o `endswith(".monitor")` do `fontes_dualsense`.
        """
        from hefesto_dualsense4unix.integrations.teste_do_microfone import (
            fonte_do_controle,
        )

        so_monitor = (
            "40\talsa_output.pci-0000_0a_00.1.hdmi-stereo.monitor\tPipeWire\t"
            "s16le 2ch 48000Hz\tIDLE\n")
        assert fonte_do_controle(
            "aa:bb:cc:00:00:01", saida_pactl=so_monitor) is None
