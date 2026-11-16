"""A voz filtrada é a fonte de cada controle, e o 🎙 toca onde a rota do cartão manda."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import (
    canal_do_microfone,
    fontes_de_captura,
    laco_de_audio,
    microfone_filtrado,
    monitor_do_microfone,
)
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
    PRIORIDADE_SESSAO_DA_PONTE,
    marca_do_aparelho,
)

MESA = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02", "02:fe:00:00:00:03", "02:fe:00:00:00:04")


def _cru(uniq: str) -> str:
    return f"hefesto_mic_{marca_do_aparelho(uniq)}"


def _voz(uniq: str) -> str:
    return f"hefesto_mic_voz_{marca_do_aparelho(uniq)}"


class _Processo:
    """Um processo de mentira que responde como o `Popen` de verdade."""

    def __init__(self, argv: list[str]) -> None:
        self.argv = argv
        self.codigo: int | None = None

    def poll(self) -> int | None:
        return self.codigo

    def terminate(self) -> None:
        self.codigo = 0

    def kill(self) -> None:
        self.codigo = -9

    def wait(self, timeout: float | None = None) -> int:
        if self.codigo is None:
            self.codigo = 0
        return self.codigo


class _Source:
    def __init__(self, nome: str, descricao: str) -> None:
        self.nome = nome
        self.descricao = descricao
        self.parado = False

    def iniciar(self) -> bool:
        return True

    def parar(self) -> None:
        self.parado = True


@pytest.fixture
def filtros(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Os filtros nascem num lançador de mentira; a tabela começa e termina vazia."""
    lancados: list[_Processo] = []

    def lancar(argv: list[str]) -> _Processo:
        proc = _Processo(list(argv))
        lancados.append(proc)
        return proc

    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(microfone_filtrado, "_lancar_processo", lancar)
    monkeypatch.setattr(microfone_filtrado.shutil, "which", lambda _n: "/usr/bin/pipewire")
    monkeypatch.setattr(canal_do_microfone, "_passar_a_escolha_do_usuario", lambda *_a: None)
    monkeypatch.setattr(canal_do_microfone, "_a_palavra_do_usuario", lambda _u: None)
    microfone_filtrado.fechar_todos()
    for uniq in list(canal_do_microfone.de_pe()):
        canal_do_microfone.fechar(uniq)
    yield lancados
    for uniq in list(canal_do_microfone.de_pe()):
        canal_do_microfone.fechar(uniq)
    microfone_filtrado.fechar_todos()


def _abrir(uniq: str, descricao: str = "Microfone do Controle 1") -> Any:
    return canal_do_microfone.abrir(
        uniq, descricao, fabrica=_Source, rodar=lambda _argv: True)


def _conf(proc: _Processo) -> str:
    return Path(proc.argv[-1]).read_text(encoding="utf-8")


class TestAVozFiltradaEAFonteDoControle:
    """MORDIDA: tire a regra da voz de `escolher_fonte` e o cru volta a ser o eleito."""

    def test_a_voz_vence_o_cru_do_mesmo_controle(self) -> None:
        uniq = MESA[0]
        fontes = [_cru(uniq), _voz(uniq)]
        assert fontes_de_captura.escolher_fonte(fontes, uniq, list(MESA)) == _voz(uniq)
        assert fontes_de_captura.escolher_fonte(fontes[::-1], uniq, list(MESA)) == _voz(uniq)

    def test_sem_a_voz_o_cru_responde(self) -> None:
        uniq = MESA[1]
        assert fontes_de_captura.escolher_fonte([_cru(uniq)], uniq, list(MESA)) == _cru(uniq)

    @pytest.mark.parametrize("quem", range(4))
    def test_quatro_controles_cada_um_com_a_sua_voz(self, quem: int) -> None:
        fontes = [n for u in MESA for n in (_cru(u), _voz(u))]
        uniq = MESA[quem]
        assert fontes_de_captura.escolher_fonte(fontes, uniq, list(MESA)) == _voz(uniq)

    def test_a_voz_de_outro_controle_nunca_e_desta(self) -> None:
        assert fontes_de_captura.escolher_fonte([_voz(MESA[1])], MESA[0], [MESA[0]]) is None

    def test_a_lista_de_fontes_ve_a_voz_e_a_nativa_nao_a_confunde(self) -> None:
        curta = f"1\t{_cru(MESA[0])}\tx\ts16le\tRUNNING\n2\t{_voz(MESA[0])}\tx\tf32le\tIDLE\n"
        assert fontes_de_captura.fontes_dualsense(curta) == [_cru(MESA[0]), _voz(MESA[0])]
        assert fontes_de_captura.fontes_nativas(curta) == []
        assert fontes_de_captura.identidade_no_nome(_voz(MESA[0])) == marca_do_aparelho(MESA[0])

    def test_o_nivel_le_o_cru(self) -> None:
        from hefesto_dualsense4unix.interface.pacotes import a02_controles

        entrada = {"audio": {"canal_fonte": _voz(MESA[2])}}
        assert a02_controles.no_do_nivel(entrada) == _cru(MESA[2])
        assert fontes_de_captura.fonte_crua_da_voz("alsa_input.x") == "alsa_input.x"


class TestOFiltroDoPipeWire:
    def test_o_conf_e_o_echo_cancel_com_supressao_de_ruido(self) -> None:
        cru = _cru(MESA[0])
        conf = microfone_filtrado.conf_do_filtro(cru, "Microfone do Controle 1")
        assert "libpipewire-module-echo-cancel" in conf
        assert "library.name = aec/libspa-aec-webrtc" in conf
        assert "webrtc.noise_suppression = true" in conf
        assert "monitor.mode = true" in conf
        assert f'target.object = "{cru}"' in conf
        assert "node.dont-reconnect = true" in conf
        assert f'node.name = "{_voz(MESA[0])}"' in conf
        assert "media.class = Audio/Source" in conf
        assert f"priority.session = {PRIORIDADE_SESSAO_DA_PONTE + 1}" in conf
        assert conf.count('hefesto.papel = "voz-filtrada"') == 2

    def test_sem_marca_nao_ha_filtro(self) -> None:
        assert microfone_filtrado.conf_do_filtro("alsa_input.x", "x") == ""
        assert microfone_filtrado.abrir(MESA[0], "alsa_input.x", "x") == ""


class TestOFiltroNasceEMorreComOCanal:
    """MORDIDA: tire o `_filtrar` de `canal_do_microfone.abrir` e o filtro não nasce."""

    def test_o_canal_sobe_a_voz_filtrada(self, filtros: list[_Processo]) -> None:
        uniq = MESA[0]
        assert _abrir(uniq) is not None
        assert len(filtros) == 1
        assert filtros[0].argv[:2] == ["pipewire", "-c"]
        assert f'target.object = "{_cru(uniq)}"' in _conf(filtros[0])
        assert microfone_filtrado.voz_de(uniq) == _voz(uniq)

    def test_fechar_o_canal_mata_o_filtro_e_apaga_o_conf(self, filtros: list[_Processo]) -> None:
        uniq = MESA[1]
        _abrir(uniq)
        conf = Path(filtros[0].argv[-1])
        assert canal_do_microfone.fechar(uniq)
        assert filtros[0].codigo is not None
        assert not conf.exists()
        assert microfone_filtrado.voz_de(uniq) == ""

    def test_quatro_controles_quatro_filtros(self, filtros: list[_Processo]) -> None:
        for uniq in MESA:
            _abrir(uniq)
        assert microfone_filtrado.de_pe() == {u: _voz(u) for u in MESA}
        canal_do_microfone.fechar(MESA[2])
        assert set(microfone_filtrado.de_pe()) == {MESA[0], MESA[1], MESA[3]}
        _abrir(MESA[2])
        assert microfone_filtrado.voz_de(MESA[2]) == _voz(MESA[2])

    def test_renomear_renasce_a_voz_com_o_rotulo_novo(self, filtros: list[_Processo]) -> None:
        uniq = MESA[3]
        _abrir(uniq, "Microfone do Controle 4")
        canal_do_microfone.renomear(uniq, "Microfone do Controle 2", fabrica=_Source,
                                    rodar=lambda _argv: True)
        assert filtros[0].codigo is not None
        assert "Microfone do Controle 2 (voz limpa)" in _conf(filtros[-1])

    def test_filtro_que_morre_devolve_o_cru(self, filtros: list[_Processo]) -> None:
        uniq = MESA[0]
        _abrir(uniq)
        filtros[0].codigo = 1
        assert microfone_filtrado.voz_de(uniq) == ""


class TestAEleicaoEsperaAVoz:
    """MORDIDA: tire o `_a_voz_falta` de `_canal_no_ar` e a eleição fica com o cru."""

    def test_o_cru_chega_antes_e_a_eleicao_espera_a_voz(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.integrations import eleicao_de_microfone as el
        from hefesto_dualsense4unix.integrations.retrato_do_som import RETRATO

        uniq = MESA[0]
        voltas = [[_cru(uniq)], [_cru(uniq)], [_cru(uniq), _voz(uniq)]]

        def agora() -> list[str]:
            return voltas.pop(0) if len(voltas) > 1 else voltas[0]

        monkeypatch.setattr(el, "fontes_de_captura_agora", agora)
        monkeypatch.setattr(el, "casamento_usb_agora", lambda _c: None)
        monkeypatch.setattr(microfone_filtrado, "voz_de", lambda _u: _voz(uniq))
        monkeypatch.setattr(RETRATO, "esperar", lambda marca, *_a, **_k: marca)
        fontes, _usb = el.EleitorDeMicrofone()._canal_no_ar(uniq, [uniq])
        assert fontes_de_captura.escolher_fonte(fontes, uniq, [uniq]) == _voz(uniq)

    def test_sem_filtro_a_eleicao_nao_espera(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from hefesto_dualsense4unix.integrations import eleicao_de_microfone as el

        uniq = MESA[1]
        monkeypatch.setattr(el, "fontes_de_captura_agora", lambda: [_cru(uniq)])
        monkeypatch.setattr(el, "casamento_usb_agora", lambda _c: None)
        monkeypatch.setattr(microfone_filtrado, "voz_de", lambda _u: "")
        fontes, _usb = el.EleitorDeMicrofone()._canal_no_ar(uniq, [uniq])
        assert fontes == [_cru(uniq)]


SINK_P1 = "alsa_output.usb-Sony_DualSense-00.analog-surround-40"
SINK_P2 = "alsa_output.usb-Sony_DualSense-00.2.analog-surround-40"
SINK_PC = "alsa_output.pci-0000_0c_00.4.analog-stereo"
SINK_TV = "alsa_output.pci-0000_0a_00.1.hdmi-stereo"
DE_CONTROLE = {SINK_P1, SINK_P2}


def _destino(rota: str, sink: str, padrao: str, anterior: str = "",
             sinks: tuple[str, ...] = (SINK_P1, SINK_P2, SINK_PC)) -> str:
    return monitor_do_microfone.destino_da_rota(
        rota, sink_do_controle=sink, sink_padrao=padrao, anterior=anterior,
        sinks=sinks, e_de_controle=DE_CONTROLE.__contains__)


class TestODestinoDaRota:
    def test_tudo_no_controle_toca_no_alto_falante_dele(self) -> None:
        assert _destino("pc", SINK_P1, SINK_P1) == SINK_P1

    @pytest.mark.parametrize("rota", ["nada", "jogo", ""])
    def test_as_outras_rotas_tocam_no_pc(self, rota: str) -> None:
        assert _destino(rota, SINK_P1, SINK_TV) == SINK_TV

    def test_o_pc_tomado_por_outro_controle_volta_a_saida_guardada(self) -> None:
        assert _destino("nada", SINK_P1, SINK_P2, anterior=SINK_TV) == SINK_TV

    def test_sem_memoria_vai_a_primeira_saida_que_nao_e_de_controle(self) -> None:
        sinks = (SINK_P1, "hefesto_som_X", SINK_P2, SINK_PC)
        assert _destino("jogo", SINK_P1, SINK_P2, sinks=sinks) == SINK_PC

    def test_no_radio_sem_saida_propria_o_pc_responde(self) -> None:
        assert _destino("pc", "", SINK_TV) == SINK_TV


@pytest.fixture
def lacos(monkeypatch: pytest.MonkeyPatch):
    nascidos: list[_Processo] = []

    def popen(argv: list[str], *_a: Any, **_k: Any) -> _Processo:
        proc = _Processo(list(argv))
        nascidos.append(proc)
        return proc

    monkeypatch.setattr(laco_de_audio.subprocess, "Popen", popen)
    monkeypatch.setattr(laco_de_audio.shutil, "which", lambda _n: "/usr/bin/pw-loopback")
    monitor_do_microfone.desligar_todos()
    yield nascidos
    monitor_do_microfone.desligar_todos()


def _tocando_em(proc: _Processo) -> str:
    return proc.argv[proc.argv.index("--playback") + 1] if "--playback" in proc.argv else ""


class TestORetornoSegueARota:
    """MORDIDA: faça `Lacos.seguir` devolver False sem religar e o retorno fica no lugar velho."""

    def test_seguir_troca_a_saida_e_mantem_a_captura(self, lacos: list[_Processo]) -> None:
        uniq = MESA[0]
        assert monitor_do_microfone.ligar(uniq, _voz(uniq), destino=SINK_TV)
        assert monitor_do_microfone.seguir(uniq, SINK_P1)
        assert lacos[0].codigo is not None
        assert _tocando_em(lacos[-1]) == SINK_P1
        assert lacos[-1].argv[lacos[-1].argv.index("--capture") + 1] == _voz(uniq)
        assert not monitor_do_microfone.seguir(uniq, SINK_P1)
        assert len(lacos) == 2

    def test_sem_retorno_de_pe_nao_se_liga_nada(self, lacos: list[_Processo]) -> None:
        assert not monitor_do_microfone.seguir(MESA[1], SINK_P1)
        assert lacos == []


class _Ctx:
    def __init__(self, conectados: list[dict[str, Any]]) -> None:
        self.conectados = conectados

    def por_uniq(self, uniq: str) -> dict[str, Any]:
        return next((c for c in self.conectados if c.get("uniq") == uniq), {})


def _entrada(uniq: str, rota: str) -> dict[str, Any]:
    from hefesto_dualsense4unix.interface.pacotes import a02_controles

    byte = {v: k for k, v in a02_controles.NOME_DO_BOTAO_DA_ROTA.items()}[rota]
    return {"uniq": uniq, "speaker": {"rota": byte},
            "audio": {"mic_mudo": False, "canal_ativo": True, "canal_mudo": False}}


@pytest.fixture
def gesto(monkeypatch: pytest.MonkeyPatch, lacos: list[_Processo]):
    """O 🎙 da aba com o `pactl` de mentira: P1 no cabo, a TV como saída do PC."""
    from hefesto_dualsense4unix.app import audio_saida
    from hefesto_dualsense4unix.interface.pacotes import a02_controles

    estado = {"saida": SINK_TV}

    def ler(argv: list[str]) -> str:
        if argv[1:] == ["get-default-sink"]:
            return estado["saida"] + "\n"
        if argv[1:] == ["list", "sinks", "short"]:
            return "".join(f"{i}\t{s}\tPipeWire\ts16le 2ch 48000Hz\tIDLE\n"
                           for i, s in enumerate((SINK_P1, SINK_P2, SINK_TV)))
        return ""

    monkeypatch.setattr(audio_saida, "rodar_leitura", ler)
    monkeypatch.setattr(audio_saida, "_ler_anterior", lambda: "")
    monkeypatch.setattr(audio_saida, "e_saida_de_controle",
                        lambda nome, _lista: nome in DE_CONTROLE)
    monkeypatch.setattr(a02_controles, "_sink_para_o_som",
                        lambda uniq, _m: {MESA[0]: SINK_P1, MESA[1]: SINK_P2}.get(uniq, ""))
    monkeypatch.setattr(a02_controles.teste_do_microfone, "fonte_do_controle",
                        lambda uniq, **_k: _voz(uniq))
    monkeypatch.setattr(a02_controles.fios, "soltar",
                        lambda _nome, alvo, *args: alvo(*args))
    a02_controles._CAMADA_1.clear()
    a02_controles._ROTA_DO_RETORNO.clear()
    yield a02_controles, estado
    a02_controles._CAMADA_1.clear()
    a02_controles._ROTA_DO_RETORNO.clear()


class TestOGestoDoMicrofone:
    """MORDIDA: tire o `destino=` do `ligar` do gesto e o retorno volta à saída padrão."""

    def test_rota_no_controle_o_retorno_sai_no_controle(self, gesto, lacos) -> None:
        a02, _ = gesto
        ctx = _Ctx([_entrada(MESA[0], "pc")])
        a02.mic_retorno(ctx, {"uniq": MESA[0]}, None)
        assert _tocando_em(lacos[-1]) == SINK_P1
        assert lacos[-1].argv[lacos[-1].argv.index("--capture") + 1] == _voz(MESA[0])

    def test_rota_no_pc_o_retorno_sai_no_pc(self, gesto, lacos) -> None:
        a02, _ = gesto
        a02.mic_retorno(_Ctx([_entrada(MESA[0], "nada")]), {"uniq": MESA[0]}, None)
        assert _tocando_em(lacos[-1]) == SINK_TV

    def test_a_saida_do_pc_presa_em_outro_controle_nao_leva_o_retorno(self, gesto, lacos) -> None:
        a02, estado = gesto
        estado["saida"] = SINK_P2
        ctx = _Ctx([_entrada(MESA[0], "jogo"), _entrada(MESA[1], "pc")])
        a02.mic_retorno(ctx, {"uniq": MESA[0]}, None)
        assert _tocando_em(lacos[-1]) == SINK_TV

    def test_a_rota_que_troca_leva_o_retorno_junto(self, gesto, lacos) -> None:
        a02, _ = gesto
        entrada = _entrada(MESA[0], "nada")
        ctx = _Ctx([entrada])
        a02.mic_retorno(ctx, {"uniq": MESA[0]}, None)
        a02._seguir_o_retorno(ctx.conectados, (MESA[0],))
        assert _tocando_em(lacos[-1]) == SINK_TV
        entrada["speaker"] = _entrada(MESA[0], "pc")["speaker"]
        a02._seguir_o_retorno(ctx.conectados, (MESA[0],))
        assert _tocando_em(lacos[-1]) == SINK_P1
        assert sum(p.codigo is None for p in lacos) == 1
