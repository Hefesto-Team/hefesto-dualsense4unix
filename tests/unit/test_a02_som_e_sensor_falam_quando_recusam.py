"""As queixas 7 e 8 dela — os botões do alto-falante e os quatro de sensor.

    7. *"e os botoes do autofalante"*
    8. *"nem giroscopio e acelerometro"*   <!-- noqa-acento: citação literal dela -->

TRÊS DEFEITOS MEDIDOS, e os três são a mesma família — A CASA SABE E O PRODUTO
NÃO FAZ:

1. **"Todo o som do PC" recusava SEMPRE.** A camada 1 (a saída padrão do
   PipeWire) não tinha dono fora da janela GTK, que a injeta no card por
   `definir_pedido_de_rota`. O motor existia inteiro — `RotaDeSaida` mais a
   resolução de sink de `fontes_de_captura` —, faltava a cola;
2. **os quatro botões de sensor respondiam CALADOS.** Sem `data-gesto`, o
   ouvinte monta o nome como `clique`, aba nenhuma o registra, e a recusa sai no
   **stderr** — que quem clica na janela nunca lê. **E a recusa que os curou
   durou uma tarde:** ela dizia *"não existe método de sensor"*, a ONDA1-D3 pôs
   `sensor.set` no daemon no mesmo dia, e a régua-estopim que a recusa deixou
   armada (`test_o_daemon_continua_sem_metodo_de_sensor`) reprovou pedindo a
   chamada. Ver `TestOsQuatroBotoesDeSensor`;
3. **o `♪` era um beco**, porque o daemon só publica `speaker` depois de alguém
   escrever um volume, e não havia escritor nesta tela. O deslizante da D-08 é o
   escritor que faltava.

AS MORDIDAS DESTE ARQUIVO
--------------------------

* devolver o `raise RuntimeError("'Todo o som do PC' ainda não tem dono…")` ao
  gesto `rota` — reprova `test_o_som_do_pc_move_a_saida_do_sistema`;
* tirar o `data-gesto="sensor"` de `aba02.sensores_da_peca` — reprova
  `test_os_quatro_botoes_de_sensor_tem_endereco_na_bancada`;
* devolver o `raise SEM_INTERRUPTOR_DE_SENSOR` ao gesto `sensor` — reprova
  `test_o_sensor_desliga_pelo_daemon_com_um_campo_so`;
* mandar os DOIS sensores em cada clique — reprova a mesma;
* mandar o volume do alto-falante CRU (0-100) ao daemon, em vez de passar pela
  curva — reprova `test_o_deslizante_do_alto_falante_passa_pela_curva_medida`.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.app import audio_saida
from hefesto_dualsense4unix.core.speaker_scale import (
    volume_do_percentual,
)

UNIQ = "aa:bb:cc:00:00:01"

#: O nome real de um sink de DualSense nesta máquina — é o que
#: `fontes_de_captura.MARCADORES_DUALSENSE` procura. Sem um nome que case, o
#: `escolher_sink` devolve `None` e a régua mediria a recusa em vez da rota.
SINK = ("alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
        "Controller-00.analog-surround-40")
OUTRO = "alsa_output.pci-0000_00_1f.3.analog-stereo"


class PactlDeMentira:
    """Um `pactl` de papel: guarda o que foi pedido e responde como o de verdade.

    ELE NÃO É UM SEGUNDO PIPEWIRE. As três respostas que ele dá são as três que
    a `RotaDeSaida` lê — a lista curta de sinks, a saída padrão e o eco da
    troca —, no formato tabulado que o `pactl` usa quando não está traduzido.
    """

    def __init__(self, *, sinks: list[str], padrao: str) -> None:
        self.sinks = list(sinks)
        self.padrao = padrao
        self.pedidos: list[list[str]] = []

    def __call__(self, argv: list[str]) -> str:
        self.pedidos.append(list(argv))
        if argv[:2] == ["pactl", "get-default-sink"]:
            return self.padrao + "\n"
        if argv[:3] == ["pactl", "list", "sinks"] and argv[3:] == ["short"]:
            return "".join(
                f"{i}\t{n}\tmodule\ts16le 2ch 48000Hz\tSUSPENDED\n"
                for i, n in enumerate(self.sinks)
            )
        if argv[:3] == ["pactl", "list", "sinks"]:
            return ""
        if argv[:2] == ["pactl", "set-default-sink"]:
            self.padrao = argv[2]
            return ""
        return ""


class PonteDeMentira:
    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, nome: str):
        def registrar(*args, **kwargs):
            self.chamadas.append((nome, args, kwargs))
            return True
        return registrar


def _ctx(**over: Any):
    import pacotes

    entrada = {"uniq": UNIQ, "transport": "usb", "connected": True,
               "inputs": {}, "audio": {}, "speaker": {}}
    entrada.update(over)
    return pacotes.Contexto(state={}, mesa=[], conectados=[entrada], estados={})


def _gesto(nome: str):
    import pacotes

    fn = pacotes.gesto_da_pagina("02-controles.html", nome)
    assert fn is not None, f"02-controles.html:{nome} não tem dono"
    return fn


# ===========================================================================
# 1. "Todo o som do PC" — a camada 1 ganhou dono
# ===========================================================================


class TestATodoOSomDoPC:
    def test_o_som_do_pc_move_a_saida_do_sistema(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDIDA: devolva a recusa "ainda não tem dono" e isto reprova.

        A ORDEM IMPORTA E ELA É MEDIDA AQUI: a camada 1 vai ANTES do byte do
        firmware. *"A camada 1 vence a camada 2: volume e rota perfeitos num
        sink mudo é trabalho invisível."*
        """
        pactl = PactlDeMentira(sinks=[OUTRO, SINK], padrao=OUTRO)
        memoria = {"v": ""}
        rota = audio_saida.RotaDeSaida(
            runner=pactl,
            ler_memoria=lambda: memoria["v"],
            gravar_memoria=lambda s: memoria.__setitem__("v", s),
        )
        monkeypatch.setattr(
            audio_saida, "RotaDeSaida", lambda **_k: rota
        )
        monkeypatch.setattr(audio_saida, "rodar_leitura", pactl)

        p = PonteDeMentira()
        _gesto("rota")(_ctx(), {"uniq": UNIQ, "rota": "pc"}, p)

        assert pactl.padrao == SINK, (
            "a saída padrão do sistema não foi para o controle — 'Todo o som do "
            "PC' voltou a acender o botão sem mover uma nota de som"
        )
        assert memoria["v"] == OUTRO, (
            "o sink anterior não foi guardado ANTES da troca, e sem ele não há "
            "caminho de volta"
        )
        assert [c[0] for c in p.chamadas] == ["speaker_set"], (
            "o byte do firmware (camada 2) não foi escrito depois da camada 1"
        )

    def test_sem_placa_de_som_ele_recusa_dizendo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O caso do RÁDIO, e é a ÚNICA assimetria de transporte que sobrou.

        A placa de som segue o transporte (medido em 15/08/2026): um DualSense
        no rádio não publica sink nenhum, e o `mapa-controles.csv` diz o mesmo do
        outro lado — `audio.alto_falante`, `radio_aciona=não`.

        RECUSAR AQUI É A RESPOSTA CERTA, e ela vem ANTES do `speaker.set`:
        escrever o byte deixaria o firmware roteado para um canal que o sistema
        não alimenta, com o botão aceso.
        """
        pactl = PactlDeMentira(sinks=[OUTRO], padrao=OUTRO)
        monkeypatch.setattr(audio_saida, "rodar_leitura", pactl)

        p = PonteDeMentira()
        with pytest.raises(RuntimeError) as erro:
            _gesto("rota")(_ctx(transport="bt"), {"uniq": UNIQ, "rota": "pc"}, p)

        assert str(erro.value) == audio_saida.MOTIVO_ROTA_SEM_SINK
        assert p.chamadas == [], (
            "o byte do firmware foi escrito mesmo sem camada 1 — é o 'acende o "
            "botão e não move som' que este gesto existe para não fazer"
        )

    def test_sons_do_jogo_devolve_a_saida_e_nao_trava_sem_memoria(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A volta existe, e a falta dela não invalida o clique.

        A janela antiga chama `pedir_rota_do_sistema(canal == CANAL_TODO_O_PC)`
        nos DOIS estados: voltar para "Sons do jogo" DEVOLVE a saída padrão.
        Fazer só a ida deixaria o som do PC preso no controle sem botão que o
        soltasse.

        E quando não há memória de volta — o som nunca esteve no controle —,
        "Sons do jogo" continua sendo só o byte da camada 2, que é o que ele
        sempre foi.
        """
        pactl = PactlDeMentira(sinks=[OUTRO, SINK], padrao=SINK)
        memoria = {"v": OUTRO}
        rota = audio_saida.RotaDeSaida(
            runner=pactl,
            ler_memoria=lambda: memoria["v"],
            gravar_memoria=lambda s: memoria.__setitem__("v", s),
        )
        monkeypatch.setattr(audio_saida, "RotaDeSaida", lambda **_k: rota)
        monkeypatch.setattr(audio_saida, "rodar_leitura", pactl)

        p = PonteDeMentira()
        _gesto("rota")(_ctx(), {"uniq": UNIQ, "rota": "jogo"}, p)
        assert pactl.padrao == OUTRO, "a saída do sistema não voltou"
        assert [c[0] for c in p.chamadas] == ["speaker_set"]

        # E sem memória de volta o gesto NÃO levanta.
        pactl2 = PactlDeMentira(sinks=[OUTRO, SINK], padrao=OUTRO)
        vazia = audio_saida.RotaDeSaida(
            runner=pactl2, ler_memoria=lambda: "", gravar_memoria=lambda _s: None
        )
        monkeypatch.setattr(audio_saida, "RotaDeSaida", lambda **_k: vazia)
        monkeypatch.setattr(audio_saida, "rodar_leitura", pactl2)
        p2 = PonteDeMentira()
        _gesto("rota")(_ctx(), {"uniq": UNIQ, "rota": "jogo"}, p2)
        assert [c[0] for c in p2.chamadas] == ["speaker_set"]


# ===========================================================================
# 2. Os quatro botões de sensor
# ===========================================================================


#: O CONTROLE COM O BLOCO `sensores`, que é a chave NOVA do payload — irmã de
#: `inputs`, publicada por `ipc_handlers._merge_sensores`. Sem ela o gesto
#: recusa por falta de LEITURA, e é isso que o teste da recusa mede.
def _com_sensores(*, giro: bool = True, accel: bool = True):
    return {"sensores": {"giroscopio_ligado": giro,
                         "acelerometro_ligado": accel,
                         "grab_do_movimento": "held"}}


class PonteQueDevolveOCorpo(PonteDeMentira):
    """O dublê ESTRITO: devolve o CORPO do daemon, como a ponte real devolve.

    **A cicatriz de 04/09/2026 obriga a este cuidado:** um dublê mais frouxo
    que a ponte real deu verde sobre duas máscaras que nunca gravaram um byte.
    O `PonteDeMentira` de cima responde `True` a todo nome, e um `True` some com
    a `ressalva` — que é exatamente a metade que esta frente entrega.
    """

    def __init__(self, corpo: dict[str, Any]) -> None:
        super().__init__()
        self.corpo = corpo

    def sensor_set_detalhado(self, **kwargs: Any) -> dict[str, Any]:
        self.chamadas.append(("sensor_set_detalhado", (), kwargs))
        return self.corpo


class TestOsQuatroBotoesDeSensor:
    """**O INTERRUPTOR PASSOU A INTERROMPER — 04/09/2026, à tarde.**

    Esta classe cobrava uma RECUSA, e a premissa dela ia à régua a cada volta:
    *"não há método de sensor no daemon"*. A ONDA1-D3 fechou essa ausência no
    mesmo dia, por decisão dela contra a recomendação de virar leitura (*"ele
    tem que funcionar de verdade. ambos independente do modo e da mascara."*),
    e a régua-estopim reprovou dizendo o que fazer: *"o botão deixou de precisar
    recusar, e a frase de recusa virou mentira"*.

    **A régua não foi afrouxada — ela mudou de alvo com o fato.** O que era
    cobrado da recusa passou a ser cobrado da CHAMADA, e a única recusa que
    sobra é a de falta de leitura, que é a mesma disciplina do 🎙: sem saber o
    estado atual, alternar é chutar qual é o oposto.
    """

    def test_os_quatro_botoes_de_sensor_tem_endereco_na_bancada(self) -> None:
        """MORDIDA: tire o `data-gesto="sensor"` do gerador e isto reprova.

        A régua olha a BANCADA — `mockup/02-controles.html` —, que é o desenho
        de hoje. O publicado só recebe com o OK dela.

        E O ENDEREÇO DE ESTADO ENTROU JUNTO: sem `data-campo`, o `.sw` volta a
        ser classe fixa do gerador e o botão fica aceso para sempre — inclusive
        depois de ela desligar o sensor, que é a mentira que o interruptor de
        verdade tornou possível.
        """
        doc = (RAIZ / "mockup/02-controles.html").read_text(encoding="utf-8")
        assert doc.count('data-gesto="sensor"') == doc.count('data-sensor="'), (
            "há botão de sensor sem `data-gesto` — o clique volta a chegar ao "
            "despachante chamando-se `clique`, e a recusa some no stderr"
        )
        assert doc.count('data-sensor="') >= 2, (
            "os interruptores de sensor sumiram do desenho"
        )
        endereços = doc.count('data-campo="giro-ligado"') + doc.count(
            'data-campo="accel-ligado"')
        assert endereços == doc.count('data-sensor="'), (
            "há interruptor de sensor sem endereço de ESTADO — o botão volta a "
            "acender por desenho, e fica aceso sobre um sensor desligado"
        )
        assert doc.count('data-hef-quando="DESLIGADO"') == endereços, (
            "o endereço de estado perdeu o valor que o apaga: sem "
            "`data-hef-quando`, o alvo `classe` vira booleano e o botão acende "
            "com QUALQUER valor pintado, travessão inclusive"
        )

    def test_o_sensor_desliga_pelo_daemon_com_um_campo_so(self) -> None:
        """MORDIDA: devolva o `raise SEM_INTERRUPTOR…` ao gesto e isto reprova.

        **UM CAMPO SÓ, e é o contrato do daemon:** campo omitido NÃO mexe
        naquele sensor (`ipc_handlers._handle_sensor_set`). Mandar os dois faria
        o clique no Giroscópio reafirmar o Acelerômetro a cada vez — que é o
        "pelas costas dela" que a `sensor_set_detalhado` documenta.
        """
        for qual, ligado_agora in (("giroscopio", True), ("acelerometro", False)):
            p = PonteQueDevolveOCorpo({"status": "ok", "ressalva": None})
            _gesto("sensor")(
                _ctx(**_com_sensores(giro=ligado_agora, accel=ligado_agora)),
                {"uniq": UNIQ, "sensor": qual}, p)
            assert p.chamadas == [
                ("sensor_set_detalhado", (), {qual: not ligado_agora,
                                              "uniq": UNIQ})
            ], (
                f"o clique no {qual} não virou o pedido esperado — ou ele "
                "deixou de alternar pela leitura, ou passou a mandar o outro "
                "sensor junto"
            )

    def test_o_sensor_sem_leitura_recusa_dizendo(self) -> None:
        """MORDIDA: troque o `raise` por um `p.sensor_set_detalhado` cego.

        Sem o bloco `sensores` o gesto não sabe qual é o oposto. É a MESMA regra
        do 🎙 — *"mandar um pedido sem saber o estado atual seria chutar qual é
        o oposto"* —, e chutar aqui custa o clique dela sem sinal nenhum.
        """
        import pacotes.a02_controles as a02

        for qual in ("giroscopio", "acelerometro"):
            p = PonteDeMentira()
            with pytest.raises(RuntimeError) as erro:
                _gesto("sensor")(_ctx(), {"uniq": UNIQ, "sensor": qual}, p)
            assert str(erro.value) == a02.SEM_LEITURA_DE_SENSOR
            assert p.chamadas == [], "recusou e mandou o pedido assim mesmo"

    def test_a_ressalva_do_modo_nativo_vira_aviso_no_cartao(self) -> None:
        """O verde falso que esta linha existe para não cometer.

        Em Modo Nativo o jogo lê o movimento pelo `hidraw` do controle FÍSICO, e
        o daemon não escreve byte nenhum nesse caminho. O daemon responde
        `status=ok` COM `ressalva`, e um gesto que olhasse só o `status` diria
        "aplicado" sobre um giro que continua chegando ao jogo.
        """
        recado = ("Modo Nativo: o jogo lê o movimento pelo hidraw do controle "
                  "FÍSICO, e nesse caminho o daemon não escreve byte nenhum.")
        p = PonteQueDevolveOCorpo({"status": "ok", "ressalva": recado})
        with pytest.raises(RuntimeError) as erro:
            _gesto("sensor")(_ctx(**_com_sensores()),
                             {"uniq": UNIQ, "sensor": "giroscopio"}, p)
        assert str(erro.value) == recado
        assert p.chamadas, "levantou a ressalva sem ter chamado o daemon"

    def test_o_calado_nao_confessa_divida_nossa(self) -> None:
        """`_corpo(None)` é o serviço que não respondeu — e a frase é curta.

        **A TERCEIRA CAUSA SAIU — 11/09/2026, A3-056, aprovada por ela.** Ela
        dizia *"o Hefesto instalado é mais velho que esta janela e ainda não
        conhece `sensor.set`"*: um método de IPC na tela, e a tela confessando
        dívida nossa — o que a decisão dela de 07/09 proíbe (*a dívida fica no
        mapa, nunca na tela*). Esta régua cravava aquela redação e teria
        reprovado a melhora em vez do defeito.

        O QUE SOBRA DE MEDÍVEL são as duas causas sobre as quais ela PODE
        agir, e a palavra com que a tela chama o serviço.
        """
        p = PonteQueDevolveOCorpo({})
        p.corpo = None  # type: ignore[assignment]
        with pytest.raises(RuntimeError) as erro:
            _gesto("sensor")(_ctx(**_com_sensores()),
                             {"uniq": UNIQ, "sensor": "giroscopio"}, p)
        frase = str(erro.value)
        assert "não confirmou" in frase and "parou" in frase, frase
        assert "daemon" not in frase.lower(), (
            f"a tela voltou a chamar o Hefesto de «daemon»: {frase!r}")
        assert "sensor.set" not in frase and "esta janela" not in frase, (
            f"a tela voltou a confessar dívida nossa: {frase!r}")

    def test_o_daemon_tem_o_metodo_de_sensor(self) -> None:
        """A premissa da CHAMADA, remedida a cada execução — o estopim invertido.

        Esta régua nasceu ao contrário (*"o daemon continua SEM método de
        sensor"*) e reprovou em 04/09/2026, que era o desfecho que ela previa
        por escrito. Agora ela guarda o fato NOVO: no dia em que `sensor.set`
        sair do daemon, o gesto passa a chamar um fantasma e o clique dela some
        outra vez — e é esta linha que avisa.
        """
        from pacotes import daemon

        metodos = daemon.metodos()
        assert metodos, "o inventário de métodos veio vazio — régua cega"
        assert "sensor.set" in metodos, (
            "o daemon perdeu `sensor.set`: o gesto `sensor` da aba 02 chama "
            f"um método que não existe mais. Os que há: {sorted(metodos)[:8]}…"
        )

    def test_o_botao_pinta_pelo_que_o_aparelho_diz(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """São TRÊS estados, e o terceiro é a razão de o campo não ser `bool`.

        Sem o bloco `sensores` a resposta é o travessão — nunca `DESLIGADO`. Um
        `bool()` cru apagaria o botão de todo controle que ainda não tem leitor
        de entradas, afirmando "desligado" sobre o que ninguém leu.

        MORDIDA: emita `bool(...)` no lugar de `_selo_do_sensor` e o terceiro
        caso vira `DESLIGADO`.
        """
        import mesa_viva

        import pacotes.a02_controles as a02

        # O endereço FORÇADO a existir: a página PUBLICADA ainda não tem os dois
        # campos (a bancada espera o OK dela), e sem este desvio a régua mediria
        # o `_so_se_a_pagina_tiver` em vez do campo.
        monkeypatch.setattr(a02, "_so_se_a_pagina_tiver", lambda campos: campos)

        def _campos(**over: Any) -> dict[str, Any]:
            cards = a02.pacote(_ctx(**over))["cards"]
            assert cards, "o pacote não montou card nenhum — régua cega"
            return next(iter(cards.values()))

        aceso = _campos(**_com_sensores())
        assert aceso["giro-ligado"] == a02.SENSOR_LIGADO
        assert aceso["accel-ligado"] == a02.SENSOR_LIGADO

        meio = _campos(**_com_sensores(giro=False))
        assert meio["giro-ligado"] == a02.SENSOR_DESLIGADO
        assert meio["accel-ligado"] == a02.SENSOR_LIGADO, (
            "desligar um sensor apagou o outro — o botão perdeu a independência "
            "que o `sensor.set` de um campo só existe para garantir"
        )

        mudo = _campos()
        assert mudo["giro-ligado"] == mesa_viva.SEM_LEITOR
        assert mudo["accel-ligado"] == mesa_viva.SEM_LEITOR


# ===========================================================================
# 3. Os dois deslizantes (D-08)
# ===========================================================================


class TestOsDoisDeslizantes:
    def test_o_deslizante_do_microfone_manda_o_numero_cru(self) -> None:
        """`mic.volume.set` é 0-100 por contrato do daemon.

        E ele NÃO toca no firmware: não apaga a luz vermelha e não tira o botão
        físico do controle. É a metade medida da D-12 — o ganho da FONTE é
        literalmente *"o canal específico dele"*.

        **A VARIANTE MUDOU EM 04/09/2026, decisão [03] da ONDA2-02** — de
        `mic_volume_set` para `mic_volume_set_detalhado`. O número mandado é o
        MESMO, e é o que esta régua mede; o que o `bool` da primeira apagava é o
        `por_uniq` do daemon, que separa *"mexi no microfone deste controle"* de
        *"caí na rota global e mexi no de outra pessoa"* (MIC-DA-MESA-CHEIA-01).
        Quem cobra a confissão é `test_a_aba_02_controles_fecha_as_linhas.py`,
        com um dublê que devolve o CORPO — este aqui usa o dublê compartilhado,
        que responde `True` a todo nome.
        """
        p = PonteDeMentira()
        _gesto("volume")(_ctx(), {"uniq": UNIQ, "volume": "microfone",
                                  "valor": "42"}, p)
        assert p.chamadas == [("mic_volume_set_detalhado", (42,), {"uniq": UNIQ})]

    def test_o_deslizante_do_alto_falante_passa_pela_curva_medida(self) -> None:
        """MORDIDA: mande o número cru e isto reprova.

        A tela fala 0-100 e o registrador é 0-255, com uma curva MEDIDA no
        hardware. É a mesma que pinta o `alto-num` ao lado — mandar `80` cru
        faria o número que ela arrasta e o número que ela lê discordarem.
        """
        p = PonteDeMentira()
        _gesto("volume")(_ctx(), {"uniq": UNIQ, "volume": "alto-falante",
                                  "valor": "80"}, p)
        assert p.chamadas == [
            ("speaker_set", (), {"volume": volume_do_percentual(80),
                                 "uniq": UNIQ})
        ]
        assert volume_do_percentual(80) != 80, (
            "a curva virou identidade — se isso for verdade um dia, esta régua "
            "para de medir a conversão e alguém precisa saber"
        )

    def test_o_click_depois_do_change_nao_manda_um_segundo_pedido(self) -> None:
        """Um `<input type="range">` clicado na pista dispara três eventos.

        `input`, `change` e `click`, nesta ordem, e o bootstrap escuta os dois
        últimos. Sem o guarda, cada clique na pista manda DUAS escritas ao
        aparelho — é o mesmo guarda que o trilho de brilho da aba 04 já tem.
        """
        p = PonteDeMentira()
        _gesto("volume")(_ctx(), {"uniq": UNIQ, "volume": "microfone",
                                  "valor": "42", "tipo": "INPUT",
                                  "evento": "click"}, p)
        assert p.chamadas == []

    def test_fora_da_faixa_ele_recusa_em_vez_de_saturar(self) -> None:
        """Saturar calado é o hábito que faz a tela e o aparelho divergirem."""
        for cru in ("101", "-1", "muito"):
            with pytest.raises(ValueError):
                _gesto("volume")(_ctx(), {"uniq": UNIQ, "volume": "microfone",
                                          "valor": cru}, PonteDeMentira())

    def test_os_dois_deslizantes_estao_na_bancada(self) -> None:
        """MORDIDA: tire o `<input type="range">` do gerador e isto reprova.

        E o `data-volume` é o que diz de QUAL volume o deslizante fala — sem ele
        o gesto não sabe se mexe no microfone ou no alto-falante.
        """
        doc = (RAIZ / "mockup/02-controles.html").read_text(encoding="utf-8")
        assert doc.count('data-volume="microfone"') >= 1
        assert doc.count('data-volume="alto-falante"') >= 1
        assert (doc.count('data-volume="microfone"')
                == doc.count('data-volume="alto-falante"')), (
            "os dois blocos deixaram de ter o mesmo número de deslizantes"
        )


# ===========================================================================
# 4. O ♪ acende — decisão [09], e o valor sai do vão invisível
# ===========================================================================


class TestOAltoFalanteMostraOMudo:
    def test_o_alto_estado_saiu_do_vao_invisivel(self) -> None:
        """Ele era escrito a cada tique dentro de um `<span hidden>`.

        Foi assim que o `"102%"` viveu meses sem ninguém ver: o piloto não mexe
        no atributo `hidden` em nenhum dos seus alvos.
        """
        doc = (RAIZ / "mockup/02-controles.html").read_text(encoding="utf-8")
        assert "alto-estado" not in doc, (
            "o `alto-estado` voltou ao desenho — valor vivo num vão que ninguém "
            "vê é o defeito que a decisão [09] fechou"
        )

    def test_o_simbolo_acende_pelo_que_o_aparelho_diz(self) -> None:
        """MORDIDA: tire o `data-campo="alto-mudo"` do ♪ e isto reprova.

        O aceso dele era classe do GERADOR e valia para sempre. Agora ele lê,
        pelo mesmo alvo `classe` dos quatro botões que a leva de 03/09 endereçou.
        """
        doc = (RAIZ / "mockup/02-controles.html").read_text(encoding="utf-8")
        assert doc.count('data-campo="alto-mudo"') >= 1
        assert doc.count('data-hef-quando="MUDO"') >= 1, (
            "o ♪ perdeu o valor que o acende — ele volta a acender por desenho"
        )

    def test_o_pacote_emite_os_tres_estados_do_mudo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """São TRÊS, e o terceiro é a razão de o campo não ser um `bool`.

        `speaker_do_entry` devolve `None` quando o daemon nunca publicou
        `speaker`; e `muted` pode ser `None` dentro de um bloco que traz volume.
        Um `False` nos dois casos acenderia "não está mudo" sobre um
        alto-falante que ninguém leu.
        """
        import mesa_viva

        import pacotes.a02_controles as a02

        # A CONTA, com o dono que a escreve. Ela é a MESMA do selo do microfone
        # — `mesa_viva.selo_do_mic` —, e é isso que impede uma segunda gramática
        # para o mesmo par de palavras a dois blocos de distância na mesma tela.
        assert mesa_viva.selo_do_mic(True, True) == "MUDO"
        assert mesa_viva.selo_do_mic(False, True) == "ATIVO"
        assert mesa_viva.selo_do_mic(False, False) == mesa_viva.SEM_LEITOR

        # E O PACOTE, com o endereço FORÇADO a existir: a página PUBLICADA ainda
        # não tem o `alto-mudo` (a bancada espera o OK dela), e sem este desvio a
        # régua mediria o `_so_se_a_pagina_tiver` em vez do campo.
        monkeypatch.setattr(a02, "_so_se_a_pagina_tiver", lambda campos: campos)

        def _campo(speaker: Any) -> str:
            entrada: dict[str, Any] = {
                "uniq": UNIQ, "transport": "usb", "connected": True,
                "inputs": {}, "audio": {}}
            if speaker is not None:
                entrada["speaker"] = speaker
            cards = a02.pacote(_ctx(**entrada))["cards"]
            assert cards, "o pacote não montou card nenhum — régua cega"
            return next(iter(cards.values())).get("alto-mudo", "AUSENTE")

        assert _campo({"volume": 102, "muted": True}) == "MUDO"
        assert _campo({"volume": 102, "muted": False}) == "ATIVO"
        # Volume conhecido e mudo DESCONHECIDO: `not None` é `True`, e um
        # `bool()` cru aqui pintaria ATIVO sobre o que ninguém leu.
        assert _campo({"volume": 102}) == mesa_viva.SEM_LEITOR
        # E o daemon que nunca publicou `speaker` — o estado real de quem nunca
        # recebeu um `speaker.set`.
        assert _campo(None) == mesa_viva.SEM_LEITOR
