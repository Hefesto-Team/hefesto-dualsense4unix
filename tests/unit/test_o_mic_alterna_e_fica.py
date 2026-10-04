"""**O 🎙 é uma TRAVA, não um gatilho — ordem dela, 21/09/2026, em caixa alta.**"""

from __future__ import annotations

import pathlib

import pytest

from hefesto_dualsense4unix.integrations import monitor_do_microfone
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import marca_do_aparelho

UNIQ = "aa:bb:cc:00:00:01"
PACOTE = pathlib.Path(
    "src/hefesto_dualsense4unix/interface/pacotes/a02_controles.py")
PAGINA = pathlib.Path(
    "src/hefesto_dualsense4unix/interface/paginas/02-controles.html")


class _Falso:
    """Um `pw-loopback` de mentira que se comporta como o real."""

    def __init__(self, argv: list[str]) -> None:
        self.argv = argv
        self._morto: int | None = None
        self.terminou = False

    def poll(self) -> int | None:
        return self._morto

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
        """O fato que separa a trava do gatilho: ele não termina sozinho."""
        assert monitor_do_microfone.ligar(UNIQ, f"hefesto_mic_{marca_do_aparelho(UNIQ)}")
        assert monitor_do_microfone.esta_ligado(UNIQ)
        assert monitor_do_microfone.ligados() == (marca_do_aparelho(UNIQ),), (
            "a chave do laço é a marca do aparelho, nunca o endereço"
        )
        assert len(mesa) == 1, "o retorno não abriu processo nenhum"
        assert not mesa[0].terminou, "o retorno morreu no mesmo clique"

    def test_o_clique_seguinte_desliga(self, mesa):
        """O SEGUNDO CLIQUE APAGA, e é a metade da ordem dela que faltava."""
        monitor_do_microfone.ligar(UNIQ, f"hefesto_mic_{marca_do_aparelho(UNIQ)}")
        assert monitor_do_microfone.esta_ligado(UNIQ)
        monitor_do_microfone.desligar(UNIQ)
        assert not monitor_do_microfone.esta_ligado(UNIQ)
        assert mesa[0].terminou, "o processo do retorno ficou de pé"

    def test_o_segundo_ligar_nao_abre_um_segundo_processo(self, mesa):
        """Dois cliques rápidos não podem deixar DOIS `pw-loopback` no ar."""
        monitor_do_microfone.ligar(UNIQ, f"hefesto_mic_{marca_do_aparelho(UNIQ)}")
        monitor_do_microfone.ligar(UNIQ, f"hefesto_mic_{marca_do_aparelho(UNIQ)}")
        assert len(mesa) == 1, "abriu um segundo retorno para o mesmo controle"

    def test_um_processo_que_morreu_sozinho_conta_como_desligado(self, mesa):
        """O estado é do SISTEMA, não da nossa lembrança."""
        monitor_do_microfone.ligar(UNIQ, f"hefesto_mic_{marca_do_aparelho(UNIQ)}")
        mesa[0]._morto = 1
        assert not monitor_do_microfone.esta_ligado(UNIQ)

    def test_a_latencia_vai_escrita_no_comando(self, mesa):
        """Gravador sem latência explícita atrasa dois segundos — medido nesta"""
        monitor_do_microfone.ligar(UNIQ, f"hefesto_mic_{marca_do_aparelho(UNIQ)}")
        argv = mesa[0].argv
        assert "--latency" in argv, "o retorno saiu sem latência explícita"
        assert argv[argv.index("--latency") + 1] == str(
            monitor_do_microfone.LATENCIA_MS)


class TestOFechoNaoDeixaMicrofoneAberto:
    def test_desligar_todos_fecha_o_que_estava_de_pe(self, mesa):
        """MORDIDA: faça `desligar_todos` devolver 0 sem terminar nada."""
        monitor_do_microfone.ligar(UNIQ, f"hefesto_mic_{marca_do_aparelho(UNIQ)}")
        monitor_do_microfone.ligar("aa:bb:cc:00:00:02", "hefesto_mic_000002")
        assert monitor_do_microfone.desligar_todos() == 2
        assert monitor_do_microfone.ligados() == ()
        assert all(p.terminou for p in mesa)

    def test_o_atexit_esta_registrado(self):
        """A cura escrita e nunca ligada é o defeito mais caro desta casa."""
        from hefesto_dualsense4unix.integrations import laco_de_audio

        fonte = pathlib.Path(
            laco_de_audio.__file__).read_text(encoding="utf-8")
        assert "atexit.register(fechar_tudo)" in fonte, (
            "o dono do `pw-loopback` não fecha as laçadas no fim do processo")


class TestATelaRefleteOsDoisEstados:
    def test_o_campo_do_botao_e_o_do_retorno(self):
        """Ela pediu que o clique REFLITA na tela."""
        pagina = PAGINA.read_text(encoding="utf-8")
        assert 'data-gesto="mic-retorno" data-campo="mic-retorno"' in pagina

    def test_o_pacote_publica_os_dois_valores(self):
        """Ligado publica a palavra; desligado publica `""`, que REMOVE o"""
        fonte = PACOTE.read_text(encoding="utf-8")
        i = fonte.index('"mic-retorno": (')
        trecho = fonte[i : i + 200]
        assert "monitor_do_microfone.esta_ligado(uniq)" in trecho
        assert 'else ""' in trecho, (
            "o desligado não publica vazio — o atributo fica e o botão trava "
            "verde")
