"""As queixas 7 e 8 dela — os botões do alto-falante e os quatro de sensor."""
from __future__ import annotations

import pathlib
import re
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
SINK = ("alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
        "Controller-00.analog-surround-40")
OUTRO = "alsa_output.pci-0000_00_1f.3.analog-stereo"


class PactlDeMentira:
    """Um `pactl` de papel: guarda o que foi pedido e responde como o de verdade."""

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


class TestATodoOSomDoPC:
    def test_o_som_do_pc_move_a_saida_do_sistema(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDIDA: devolva a recusa "ainda não tem dono" e isto reprova."""
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
        """A volta existe, e a falta dela não invalida o clique."""
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

        pactl2 = PactlDeMentira(sinks=[OUTRO, SINK], padrao=OUTRO)
        vazia = audio_saida.RotaDeSaida(
            runner=pactl2, ler_memoria=lambda: "", gravar_memoria=lambda _s: None
        )
        monkeypatch.setattr(audio_saida, "RotaDeSaida", lambda **_k: vazia)
        monkeypatch.setattr(audio_saida, "rodar_leitura", pactl2)
        p2 = PonteDeMentira()
        _gesto("rota")(_ctx(), {"uniq": UNIQ, "rota": "jogo"}, p2)
        assert [c[0] for c in p2.chamadas] == ["speaker_set"]


def _com_sensores(*, giro: bool = True, accel: bool = True):
    return {"sensores": {"giroscopio_ligado": giro,
                         "acelerometro_ligado": accel,
                         "grab_do_movimento": "held"}}


class PonteQueDevolveOCorpo(PonteDeMentira):
    """O dublê ESTRITO: devolve o CORPO do daemon, como a ponte real devolve."""

    def __init__(self, corpo: dict[str, Any]) -> None:
        super().__init__()
        self.corpo = corpo

    def sensor_set_detalhado(self, **kwargs: Any) -> dict[str, Any]:
        self.chamadas.append(("sensor_set_detalhado", (), kwargs))
        return self.corpo


class TestOsQuatroBotoesDeSensor:
    """**O INTERRUPTOR PASSOU A INTERROMPER — 04/09/2026, à tarde.**"""

    def test_os_quatro_botoes_de_sensor_tem_endereco_na_bancada(self) -> None:
        """MORDIDA: tire o `data-gesto="sensor"` do gerador e isto reprova."""
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
        dos_sensores = sum(
            1 for tag in re.findall(r"<[^>]*data-sensor=\"[^>]*>", doc)
            if 'data-hef-quando="DESLIGADO"' in tag)
        assert dos_sensores == endereços, (
            "o endereço de estado perdeu o valor que o apaga: sem "
            "`data-hef-quando`, o alvo `classe` vira booleano e o botão acende "
            "com QUALQUER valor pintado, travessão inclusive"
        )

    def test_o_sensor_desliga_pelo_daemon_com_um_campo_so(self) -> None:
        """MORDIDA: devolva o `raise SEM_INTERRUPTOR…` ao gesto e isto reprova."""
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
        """MORDIDA: troque o `raise` por um `p.sensor_set_detalhado` cego."""
        import pacotes.a02_controles as a02

        for qual in ("giroscopio", "acelerometro"):
            p = PonteDeMentira()
            with pytest.raises(RuntimeError) as erro:
                _gesto("sensor")(_ctx(), {"uniq": UNIQ, "sensor": qual}, p)
            assert str(erro.value) == a02.SEM_LEITURA_DE_SENSOR
            assert p.chamadas == [], "recusou e mandou o pedido assim mesmo"

    def test_a_ressalva_do_modo_nativo_vira_aviso_no_cartao(self) -> None:
        """O verde falso que esta linha existe para não cometer."""
        recado = ("Modo Nativo: o jogo lê o movimento pelo hidraw do controle "
                  "FÍSICO, e nesse caminho o daemon não escreve byte nenhum.")
        p = PonteQueDevolveOCorpo({"status": "ok", "ressalva": recado})
        with pytest.raises(RuntimeError) as erro:
            _gesto("sensor")(_ctx(**_com_sensores()),
                             {"uniq": UNIQ, "sensor": "giroscopio"}, p)
        assert str(erro.value) == recado
        assert p.chamadas, "levantou a ressalva sem ter chamado o daemon"


    def test_o_botao_pinta_pelo_que_o_aparelho_diz(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """São TRÊS estados, e o terceiro é a razão de o campo não ser `bool`."""
        import mesa_viva

        import pacotes.a02_controles as a02

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


class TestOsDoisDeslizantes:
    def test_o_deslizante_do_microfone_manda_o_numero_cru(self) -> None:
        """`mic.volume.set` é 0-100 por contrato do daemon."""
        p = PonteDeMentira()
        _gesto("volume")(_ctx(), {"uniq": UNIQ, "volume": "microfone",
                                  "valor": "42"}, p)
        assert p.chamadas == [("mic_volume_set_detalhado", (42,), {"uniq": UNIQ})]

    def test_o_deslizante_do_alto_falante_passa_pela_curva_medida(self) -> None:
        """MORDIDA: mande o número cru e isto reprova."""
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
        """Um `<input type="range">` clicado na pista dispara três eventos."""
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
        """MORDIDA: tire o `<input type="range">` do gerador e isto reprova."""
        doc = (RAIZ / "mockup/02-controles.html").read_text(encoding="utf-8")
        assert doc.count('data-volume="microfone"') >= 1
        assert doc.count('data-volume="alto-falante"') >= 1
        assert (doc.count('data-volume="microfone"')
                == doc.count('data-volume="alto-falante"')), (
            "os dois blocos deixaram de ter o mesmo número de deslizantes"
        )


class TestOAltoFalanteMostraOMudo:
    def test_o_alto_estado_saiu_do_vao_invisivel(self) -> None:
        """Ele era escrito a cada tique dentro de um `<span hidden>`."""
        doc = (RAIZ / "mockup/02-controles.html").read_text(encoding="utf-8")
        assert "alto-estado" not in doc, (
            "o `alto-estado` voltou ao desenho — valor vivo num vão que ninguém "
            "vê é o defeito que a decisão [09] fechou"
        )

    def test_o_simbolo_acende_pelo_que_o_aparelho_diz(self) -> None:
        """MORDIDA: tire o `data-campo="alto-mudo"` do ♪ e isto reprova."""
        doc = (RAIZ / "mockup/02-controles.html").read_text(encoding="utf-8")
        assert doc.count('data-campo="alto-mudo"') >= 1
        import mesa_viva

        assert doc.count(f'data-hef-quando="{mesa_viva.DESLIGADO}"') >= 1, (
            "o ♪ perdeu o valor que o acende — ele volta a acender por desenho"
        )

    def test_o_pacote_emite_os_tres_estados_do_mudo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """São TRÊS, e o terceiro é a razão de o campo não ser um `bool`."""
        import mesa_viva

        import pacotes.a02_controles as a02

        assert mesa_viva.selo_do_mic(True, True) == mesa_viva.DESLIGADO
        assert mesa_viva.selo_do_mic(False, True) == "ATIVO"
        assert mesa_viva.selo_do_mic(False, False) == mesa_viva.SEM_LEITOR

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

        assert _campo({"volume": 102, "muted": True}) == mesa_viva.DESLIGADO
        assert _campo({"volume": 102, "muted": False}) == "ATIVO"
        assert _campo({"volume": 102}) == mesa_viva.SEM_LEITOR
        assert _campo(None) == mesa_viva.SEM_LEITOR
