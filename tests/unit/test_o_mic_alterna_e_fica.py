"""**O 🎙 é uma TRAVA, não um gatilho — ordem dela, 21/09/2026, em caixa alta.**

    *"SE EU ATIVAR COM UM CLICK E ELE FICAR VERDE ELE TÁ ATIVADO E SEGUE ASSIM
    ATÉ EU DESATIVAR CLICANDO NOVAMENTE E ELE FICANDO CINZA. POR DEFAULT SEGUE
    DESLIGADO, ATÉ ALGUME CLICAR E VER ISSO REFLETINDO LÁ."*

Antes disto o botão GRAVAVA três segundos e devolvia — um gatilho, que termina
sozinho. Ela pediu o botão do Discord: liga, fica, desliga. São quatro fatos, e
cada um tem régua abaixo:

1. **Por default, desligado.** Ninguém nasce com o microfone aberto.
2. **Um clique liga**, e fica ligado — o retorno é um processo de pé.
3. **O clique seguinte desliga**, e fica desligado.
4. **A tela reflete os dois**, pelo campo `mic-retorno`.

E uma quinta, que não é dela mas é desta casa: **o retorno morre com o
processo**. Um `pw-loopback` órfão deixaria o microfone dela aberto depois de a
interface fechar — o defeito que o `atexit` existe para não deixar acontecer, e
o irmão daquele em que 22 `null-sinks` vazaram onde cabiam 4.
"""

from __future__ import annotations

import pathlib

import pytest

from hefesto_dualsense4unix.integrations import monitor_do_microfone

UNIQ = "aa:bb:cc:00:00:01"
PACOTE = pathlib.Path(
    "src/hefesto_dualsense4unix/interface/pacotes/a02_controles.py")
PAGINA = pathlib.Path(
    "src/hefesto_dualsense4unix/interface/paginas/02-controles.html")


class _Falso:
    """Um `pw-loopback` de mentira que se comporta como o real.

    **MAIS RIGOROSO QUE O PRODUTO, de propósito** — esta casa já pagou três
    vezes por dublê mais frouxo que o aparelho. Ele responde `poll()` como o
    `Popen` real (None enquanto vivo, o código quando morto) e registra o
    `terminate`, que é o que o desligar tem de chamar.
    """

    def __init__(self, argv: list[str]) -> None:
        self.argv = argv
        self._morto: int | None = None
        self.terminou = False

    def poll(self) -> int | None:
        return self._morto

    # AS DUAS MORTES CONTAM. O produto usa `kill()` de propósito — um loopback
    # de áudio não tem estado a salvar, e um segundo entre o clique e o
    # silêncio é um segundo em que o botão mente. Um dublê que só registrasse
    # o `terminate` reprovaria a escolha CERTA do produto, que é a forma mais
    # cara de régua falsa desta casa.
    def terminate(self) -> None:
        self.terminou = True
        self._morto = 0

    def kill(self) -> None:
        self.terminou = True
        self._morto = -9

    def wait(self, timeout: float | None = None) -> int:
        if self._morto is None:
            self._morto = 0
        return self._morto


@pytest.fixture
def mesa(monkeypatch):
    """A mesa limpa: nenhum retorno de pé, e o `pw-loopback` dublado."""
    nascidos: list[_Falso] = []

    def _popen(argv, *a, **k):
        p = _Falso(list(argv))
        nascidos.append(p)
        return p

    # **O DUBLÊ MIRA O DONO, NÃO A FACHADA** — desde 21/09 o `pw-loopback` tem
    # um dono só (`integrations/laco_de_audio.py`) e este módulo é a fachada
    # dele para o eixo do microfone. Mirar aqui deixaria o produto abrindo
    # processo de verdade na máquina que roda a suíte.
    from hefesto_dualsense4unix.integrations import laco_de_audio

    monkeypatch.setattr(laco_de_audio.subprocess, "Popen", _popen)
    monkeypatch.setattr(laco_de_audio.shutil, "which", lambda _nome: "/usr/bin/pw-loopback")
    monitor_do_microfone._LACOS._vivos.clear()
    yield nascidos
    monitor_do_microfone._LACOS._vivos.clear()


class TestOBotaoEUmaTrava:
    def test_por_default_desligado(self, mesa):
        """MORDIDA: faça `esta_ligado` devolver True quando não sabe."""
        assert not monitor_do_microfone.esta_ligado(UNIQ)
        assert monitor_do_microfone.ligados() == ()

    def test_um_clique_liga_e_fica_ligado(self, mesa):
        """O fato que separa a trava do gatilho: ele não termina sozinho.

        MORDIDA: faça o `ligar` esperar o processo (`wait`) — o retorno passa a
        durar um instante e o botão volta a ser um gatilho.
        """
        assert monitor_do_microfone.ligar(UNIQ, "hefesto_mic_000001")
        assert monitor_do_microfone.esta_ligado(UNIQ)
        assert monitor_do_microfone.ligados() == (UNIQ,)
        assert len(mesa) == 1, "o retorno não abriu processo nenhum"
        assert not mesa[0].terminou, "o retorno morreu no mesmo clique"

    def test_o_clique_seguinte_desliga(self, mesa):
        """MORDIDA: faça `alternar` sempre ligar. O segundo clique não apaga."""
        monitor_do_microfone.alternar(UNIQ, "hefesto_mic_000001")
        assert monitor_do_microfone.esta_ligado(UNIQ)
        monitor_do_microfone.alternar(UNIQ, "hefesto_mic_000001")
        assert not monitor_do_microfone.esta_ligado(UNIQ)
        assert mesa[0].terminou, "o processo do retorno ficou de pé"

    def test_o_segundo_ligar_nao_abre_um_segundo_processo(self, mesa):
        """Dois cliques rápidos não podem deixar DOIS `pw-loopback` no ar.

        É o defeito dos 22 `null-sinks` onde cabiam 4, na mesma casa e no mesmo
        mês: quem pergunta à lembrança em vez de ao estado vaza.

        MORDIDA: tire a guarda do `esta_ligado` no topo do `ligar`.
        """
        monitor_do_microfone.ligar(UNIQ, "hefesto_mic_000001")
        monitor_do_microfone.ligar(UNIQ, "hefesto_mic_000001")
        assert len(mesa) == 1, "abriu um segundo retorno para o mesmo controle"

    def test_um_processo_que_morreu_sozinho_conta_como_desligado(self, mesa):
        """O estado é do SISTEMA, não da nossa lembrança.

        MORDIDA: guarde um booleano em vez de perguntar ao `poll()`. O botão
        fica verde para sempre depois de o `pw-loopback` cair.
        """
        monitor_do_microfone.ligar(UNIQ, "hefesto_mic_000001")
        mesa[0]._morto = 1  # o loopback caiu sozinho
        assert not monitor_do_microfone.esta_ligado(UNIQ)

    def test_a_latencia_vai_escrita_no_comando(self, mesa):
        """Gravador sem latência explícita atrasa dois segundos — medido nesta
        casa, e mordeu o microfone e a ponte do rádio.

        MORDIDA: tire o `--latency` do argv.
        """
        monitor_do_microfone.ligar(UNIQ, "hefesto_mic_000001")
        argv = mesa[0].argv
        assert "--latency" in argv, "o retorno saiu sem latência explícita"
        assert argv[argv.index("--latency") + 1] == str(
            monitor_do_microfone.LATENCIA_MS)


class TestOFechoNaoDeixaMicrofoneAberto:
    def test_desligar_todos_fecha_o_que_estava_de_pe(self, mesa):
        """MORDIDA: faça `desligar_todos` devolver 0 sem terminar nada."""
        monitor_do_microfone.ligar(UNIQ, "hefesto_mic_000001")
        monitor_do_microfone.ligar("aa:bb:cc:00:00:02", "hefesto_mic_000002")
        assert monitor_do_microfone.desligar_todos() == 2
        assert monitor_do_microfone.ligados() == ()
        assert all(p.terminou for p in mesa)

    def test_o_atexit_esta_registrado(self):
        """A cura escrita e nunca ligada é o defeito mais caro desta casa.

        MORDIDA: tire o `atexit.register`. O microfone dela fica aberto depois
        de a interface fechar, e nada na tela diz isso.
        """
        from hefesto_dualsense4unix.integrations import laco_de_audio

        fonte = pathlib.Path(
            laco_de_audio.__file__).read_text(encoding="utf-8")
        assert "atexit.register(fechar_tudo)" in fonte, (
            "o dono do `pw-loopback` não fecha as laçadas no fim do processo")


class TestATelaRefleteOsDoisEstados:
    def test_o_campo_do_botao_e_o_do_retorno(self):
        """Ela pediu que o clique REFLITA na tela.

        O botão veste o que o botão CAUSA. A luz do plástico tem dono no daemon
        e aparece no selo ao lado — dois donos no mesmo elemento é o defeito que
        os `data-campo` existem para não deixar acontecer.

        MORDIDA: devolva `data-campo="mic-botao-estado"` ao 🎙.
        """
        pagina = PAGINA.read_text(encoding="utf-8")
        assert 'data-gesto="mic-retorno" data-campo="mic-retorno"' in pagina

    def test_o_pacote_publica_os_dois_valores(self):
        """Ligado publica a palavra; desligado publica `""`, que REMOVE o
        atributo e devolve o cinza de base.

        MORDIDA: publique a palavra sempre. O botão nasce verde.
        """
        fonte = PACOTE.read_text(encoding="utf-8")
        i = fonte.index('"mic-retorno": (')
        trecho = fonte[i : i + 200]
        assert "monitor_do_microfone.esta_ligado(uniq)" in trecho
        assert 'else ""' in trecho, (
            "o desligado não publica vazio — o atributo fica e o botão trava "
            "verde")
