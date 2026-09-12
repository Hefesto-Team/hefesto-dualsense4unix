"""O volume do MICROFONE sai do desenho e passa a ser leitura — 12/09/2026.

## A METADE QUE FALTOU, e a decisão é dela

Em 02/09/2026, item 16: *"o número E a barra. Hoje os dois estão congelados no
desenho: com o volume em 40, a tela continua mostrando 100"*.

Aquela cura deu `alto-num` e `alto-barra` ao ALTO-FALANTE e parou ali. O
deslizante do MICROFONE — **na mesma coluna, um bloco acima, com o mesmo
defeito** — ficou sem endereço nenhum: nem o `<span class="n">` nem o `.cheio`
tinham `data-campo`, e o produto mostrava o número do desenho (`80`) para
sempre, qualquer que fosse o ganho da captura.

É a regra desta casa cobrada por dentro: *quando a cura conhece a causa, ela
cobre TODOS os chamadores.* Cobrir um deixa a próxima pessoa remedindo o mesmo
defeito — e aqui foram dez dias.

## O QUE ESTA RÉGUA TRAVA

1. o dono do número (`a02_controles.volume_do_microfone`) lê do ESTADO, nunca
   do `pactl`, e sabe dizer *"não sei"*;
2. o pacote emite `mic-num` e `mic-barra` em todo tique, com os dois desfechos
   do alto-falante: travessão no número e ZERO na barra quando não se leu;
3. o gerador carrega os dois endereços nos quatro lugares, com os alvos certos
   (`largura` na barra pintada, `valor` no deslizante).

**A MORDIDA de cada teste está na sua docstring.**
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

ABA02 = RAIZ / "src/hefesto_dualsense4unix/interface/aba02.py"


@pytest.fixture(autouse=True)
def sem_tocar_o_pipewire_da_maquina() -> Any:
    """Esta régua deixa o cache da camada 1 como o encontrou. MEDIDO.

    `a02.pacote()` chama `_camada_1`, que dispara uma THREAD com dois `pactl`
    por controle e escreve o resultado em `_CAMADA_1`, que é **estado de
    módulo**. Duas consequências, e as duas doem:

    1. a régua vai ao PipeWire da máquina de quem a roda — e a máquina dela
       está em uso;
    2. a leitura fica no módulo para a régua SEGUINTE. Medido em 12/09/2026:
       com este arquivo antes de `test_a02_a_fonte_do_som_ganha_gesto.py`, duas
       daquelas caíram — `aceso_da_fileira` passou a ler a camada 1 REAL em vez
       de cair no `rota_na_tela`, que é o caminho que elas medem. E caíram
       **de forma intermitente**, porque depende de a thread voltar antes ou
       depois da asserção: a pior forma de vermelho que esta casa conhece.

    O relógio adiantado é o que impede a thread de nascer (`_camada_1` devolve
    o cache enquanto `agora - _CAMADA_1_QUANDO < CAMADA_1_S`), e não um dublê:
    nenhuma função do produto é trocada aqui.
    """
    import time

    import pacotes.a02_controles as a02

    antes = dict(a02._CAMADA_1)
    quando, em_voo = a02._CAMADA_1_QUANDO[0], a02._CAMADA_1_EM_VOO[0]
    sono = dict(a02._SONO)
    a02._CAMADA_1_QUANDO[0] = time.monotonic()
    yield
    a02._CAMADA_1.clear()
    a02._CAMADA_1.update(antes)
    a02._SONO.clear()
    a02._SONO.update(sono)
    a02._CAMADA_1_QUANDO[0], a02._CAMADA_1_EM_VOO[0] = quando, em_voo


class TestODonoDoNumero:
    """Um valor, um dono — e ele não pergunta ao sistema."""

    def test_o_que_o_daemon_disse_e_o_que_sai(self) -> None:
        """MORDIDA: devolva `audio["volume_captura"]` sem conferir o tipo.

        O campo chega do `state_full`, que copia o que o laço do canal deixou:
        `None` enquanto ninguém perguntou, e o `bool` que todo `isinstance(x,
        int)` distraído deixa passar. `True` viraria "volume 1".
        """
        import pacotes.a02_controles as a02

        assert a02.volume_do_microfone({"volume_captura": 40}) == 40
        assert a02.volume_do_microfone({"volume_captura": 0}) == 0
        assert a02.volume_do_microfone({"volume_captura": True}) is None
        assert a02.volume_do_microfone({"volume_captura": "40"}) is None
        assert a02.volume_do_microfone({}) is None
        assert a02.volume_do_microfone(None) is None

    def test_o_teto_e_o_do_trilho(self) -> None:
        """MORDIDA: devolva o número do `pactl` cru.

        O `pactl` admite passar de 100 (super-amplificação) e o
        `<input type="range" max="100">` desta tela não representa isso: o
        texto diria `140` e o polegar pararia no fim. Dois valores para o mesmo
        volume no mesmo bloco é o defeito que o dono único existe para impedir.
        """
        import pacotes.a02_controles as a02

        assert a02.volume_do_microfone({"volume_captura": 140}) == 100
        assert a02.volume_do_microfone({"volume_captura": -3}) == 0

    def test_ele_nao_pergunta_ao_sistema(self, monkeypatch: Any) -> None:
        """MORDIDA: faça o dono chamar `volume_da_captura` (que roda `pactl`).

        Ele é chamado no TIQUE da pintura, por controle. Um subprocesso ali
        multiplica por quatro o custo de cada quadro — é a mesma razão escrita
        no daemon, no bloco do `audio`, para a leitura morar numa thread a 2 Hz.

        **ESTA RÉGUA MEDE O ATO, e não o texto do fonte.** A primeira versão
        procurava `"pactl"` em `inspect.getsource` e REPROVOU a própria entrega:
        o comentário que explica por que o `pactl` não entra aqui *virou* a
        primeira ocorrência de `pactl` no arquivo. É a armadilha de PROSA que
        esta casa já pagou quatro vezes em cinco dias.
        """
        import subprocess

        import pacotes.a02_controles as a02
        from hefesto_dualsense4unix.integrations import audio_control

        def estoura(*_a: Any, **_k: Any) -> Any:
            raise AssertionError("o dono do número foi ao sistema perguntar")

        monkeypatch.setattr(subprocess, "run", estoura)
        monkeypatch.setattr(audio_control, "volume_da_captura", estoura)
        assert a02.volume_do_microfone({"volume_captura": 55}) == 55


class TestOPacoteEmite:
    """Os dois campos saem em todo tique, e dizem "não sei" quando é o caso."""

    def _campos(self, volume: Any) -> dict[str, Any]:
        import pacotes
        import pacotes.a02_controles as a02

        audio: dict[str, Any] = {"mic_mudo": False, "canal_ativo": True}
        if volume is not None:
            audio["volume_captura"] = volume
        ctx = pacotes.Contexto(
            state={}, mesa=[], estados={},
            conectados=[{"uniq": "aa:bb:cc:00:00:01", "transport": "usb",
                         "connected": True, "inputs": {}, "audio": audio,
                         "speaker": {"volume": 100, "muted": False}}])
        saida = a02.pacote(ctx)
        for valores in (saida.get("cards") or {}).values():
            if "mic-num" in valores:
                return valores
        return {}

    def test_o_numero_e_a_barra_saem_do_estado(self) -> None:
        """MORDIDA: emita `mic_vol` do desenho, ou o volume do alto-falante.

        São dois blocos diferentes com dois volumes diferentes na mesma coluna;
        trocá-los pinta o ganho da captura com o número do alto-falante e
        ninguém vê, porque os dois são números plausíveis de 0 a 100.
        """
        campos = self._campos(40)
        assert campos.get("mic-num") == 40
        assert campos.get("mic-barra") == 40

    def test_sem_leitura_o_numero_diz_nao_sei_e_a_barra_vai_a_zero(self) -> None:
        """MORDIDA: omita as duas chaves, ou mande travessão na barra.

        Omitir deixa o número do DESENHO pendurado na tela para sempre, que é o
        defeito inteiro. E travessão na barra é pior que inútil: `largura` é um
        dos `ALVOS_QUE_O_TRAVESSAO_NAO_ATENDE` — o CSSOM descarta `width: "—%"`
        calado e o contador de pintura soma +1 por tique, para sempre.
        """
        campos = self._campos(None)
        assert "mic-num" in campos
        assert "mic-barra" in campos
        assert campos["mic-num"] == "—"
        assert campos["mic-barra"] == 0

    def test_o_zero_lido_nao_vira_nao_sei(self) -> None:
        """MORDIDA: escreva `mic_volume or mesa_viva.SEM_LEITOR`.

        Microfone no mínimo é um fato, e é diferente de microfone não lido. O
        `or` colapsa os dois — o mesmo `or {}` que esta aba já pagou no bloco
        do alto-falante.
        """
        campos = self._campos(0)
        assert campos.get("mic-num") == 0
        assert campos.get("mic-barra") == 0


class TestOGeradorEnderecou:
    """Os quatro lugares, com os dois alvos — senão o pacote escreve no vazio."""

    def test_os_dois_enderecos_estao_no_gerador(self) -> None:
        """MORDIDA: tire o `data-campo` do `<span class="n">` do microfone.

        Sem endereço o campo sai do pacote a cada tique e a tela não muda —
        verde sobre um número congelado, que é como este defeito sobreviveu a
        dez dias de réguas.
        """
        fonte = ABA02.read_text(encoding="utf-8")
        assert 'data-campo="mic-num"' in fonte
        assert 'data-campo="mic-barra"' in fonte

    def test_a_pagina_publicada_tem_os_quatro_lugares(self) -> None:
        """MORDIDA: publique uma página sem os endereços novos.

        **O PRODUTO RENDERIZA O PUBLICADO**, não a bancada — curar o gerador e
        não publicar deixa a tela dela exatamente como estava. É a armadilha
        que esta casa já pagou quatro vezes num dia só.
        """
        from hefesto_dualsense4unix.interface import onde

        doc = onde.pagina("02-controles.html", publicado=True).read_text(
            encoding="utf-8")
        assert doc.count('data-campo="mic-num"') == 4
        assert doc.count('data-campo="mic-barra"') == 8

    def test_cada_alvo_no_seu_elemento(self) -> None:
        """MORDIDA: ponha `valor` na barra pintada e `largura` no deslizante.

        Trocados, o `<span>` recebe `el.value` (que ele não tem) e o `<input>`
        ganha `style.width` — os dois calados, os dois parados. É o motivo de a
        régua do gerador contar POR ALVO, e não por quantidade.
        """
        import re

        from hefesto_dualsense4unix.interface import onde

        doc = onde.pagina("02-controles.html", publicado=True).read_text(
            encoding="utf-8")
        tags = re.findall(r'<[^>]*data-campo="mic-barra"[^>]*>', doc)
        assert len(tags) == 8
        larguras = [t for t in tags if 'data-hef-alvo="largura"' in t]
        valores = [t for t in tags if 'data-hef-alvo="valor"' in t]
        assert len(larguras) == 4
        assert len(valores) == 4
        assert all("<span" in t for t in larguras)
        assert all("<input" in t for t in valores)
