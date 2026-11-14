"""A caixa do controle toca só o SFX, e o corpo sente o som inteiro.

Sprint A-CAIXA-DO-CONTROLE-TOCA-SO-O-SFX-01. O sinal é o da medida de 14/11/2026:
um acorde sustentado (lá, dó# e mi, sete harmônicos) e cliques de ruído de 4 ms em
instantes IRREGULARES (um clique periódico seria «música» para qualquer régua de
ritmo). Na saída da caixa o acorde cai 20 dB ou mais e os cliques ficam a menos de
3 dB, no cabo (48 kHz) e no rádio (45 kHz), de um a quatro controles.

MORDIDAS (cada uma reprova pelo menos um teste daqui): arrancar o separador da
bomba do rádio; devolver o ``module-loopback`` da saída no cabo com a chave ligada;
tirar a porta (só o HPSS) ou o HPSS (só a porta) da máscara.
"""

from __future__ import annotations

import os
import threading
import time
from types import SimpleNamespace
from typing import Any, ClassVar

import numpy as np
import pytest

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import dualsense_bt_audio as bt
from hefesto_dualsense4unix.integrations.separador_do_som import SeparadorDoSom

TAXA_DO_CABO = af.TAXA_DA_CAIXA_NO_CABO
TAXA_DO_RADIO = af.TAXA_DA_FONTE_DO_SOM
BLOCO = af.AMOSTRAS_POR_QUADRO


def _sinal(taxa: int, segundos: float = 6.0, semente: int = 11) -> tuple[Any, Any]:
    t = np.arange(int(segundos * taxa)) / taxa
    acorde = np.zeros_like(t)
    for fundamental in (220.0, 277.18, 329.63):
        for harmonico in range(1, 8):
            fase = 2 * np.pi * fundamental * harmonico * t + harmonico
            acorde += (0.6**harmonico) * np.sin(fase)
    acorde *= 0.05 / np.sqrt(np.mean(acorde**2))
    sorte = np.random.default_rng(semente)
    cliques = np.zeros_like(t)
    duracao = int(0.004 * taxa)
    instantes = []
    agora = 0.8
    while agora < segundos - 0.3:
        inicio = int(agora * taxa)
        cliques[inicio:inicio + duracao] += sorte.normal(0, 1, duracao) * np.exp(
            -np.arange(duracao) / (0.0008 * taxa)
        )
        instantes.append(inicio)
        agora += sorte.uniform(0.35, 0.9)
    pico = max(np.sqrt(np.mean(cliques[i:i + duracao] ** 2)) for i in instantes)
    cliques *= 0.2 / pico
    return acorde, cliques


def _energia(sinal: Any) -> float:
    return float(np.sum(np.asarray(sinal, dtype=float) ** 2)) + 1e-20


def _db(saida: Any, entrada: Any) -> float:
    return float(10 * np.log10(_energia(saida) / _energia(entrada)))


def _pcm(mono: Any, canais: int = 2) -> bytes:
    inteiros = np.clip(np.rint(np.asarray(mono) * 32768.0), -32768, 32767).astype("<i2")
    return np.repeat(inteiros, canais).tobytes()


def _mono(pcm: bytes, canais: int = 2) -> Any:
    return np.frombuffer(pcm, dtype="<i2").reshape(-1, canais)[:, 0] / 32768.0


def _acorde_e_cliques_na_caixa(taxa: int) -> tuple[float, float]:
    acorde, cliques = _sinal(taxa)
    separador = SeparadorDoSom(taxa)
    tamanho = len(acorde) - len(acorde) % BLOCO
    saidas = [np.zeros(tamanho) for _ in range(3)]
    for p in range(0, tamanho, BLOCO):
        trecho = slice(p, p + BLOCO)
        mistura = acorde[trecho] + cliques[trecho]
        pedacos = separador.separar(mistura, acorde[trecho], cliques[trecho])
        for indice in range(3):
            saidas[indice][trecho] = pedacos[indice]
    atraso = separador.latencia_amostras
    um_segundo = taxa
    acorde_db = _db(saidas[1][um_segundo + atraso:], acorde[um_segundo:tamanho - atraso])
    cliques_db = _db(saidas[2][atraso:], cliques[:tamanho - atraso])
    return acorde_db, cliques_db


@pytest.mark.parametrize("taxa", [TAXA_DO_CABO, TAXA_DO_RADIO], ids=["cabo-48k", "radio-45k"])
def test_o_acorde_cai_20_db_e_os_cliques_ficam(taxa: int) -> None:
    acorde_db, cliques_db = _acorde_e_cliques_na_caixa(taxa)
    assert acorde_db <= -20.0, f"a música vaza na caixa: {acorde_db:.1f} dB"
    assert cliques_db >= -3.0, f"o efeito se perde na caixa: {cliques_db:.1f} dB"


@pytest.mark.parametrize("taxa", [TAXA_DO_CABO, TAXA_DO_RADIO], ids=["cabo-48k", "radio-45k"])
def test_o_atraso_da_caixa_e_de_no_maximo_20_ms(taxa: int) -> None:
    separador = SeparadorDoSom(taxa)
    entrada = np.zeros(taxa // 2)
    entrada[int(0.2 * taxa)] = 0.5
    saida = np.concatenate([
        separador.separar(entrada[p:p + BLOCO])[0] for p in range(0, len(entrada), BLOCO)
    ])
    atraso = int(np.argmax(np.abs(saida))) - int(0.2 * taxa)
    assert atraso == separador.latencia_amostras
    assert atraso / taxa <= 0.020


def test_o_silencio_sai_zero_exato_e_o_resto_de_1_lsb_tambem() -> None:
    separador = SeparadorDoSom(TAXA_DO_RADIO)
    assert separador.processar(bytes(4 * BLOCO)) == bytes(4 * BLOCO)
    sorte = np.random.default_rng(3)
    for _ in range(300):
        ruido = sorte.integers(-1, 2, 2 * BLOCO).astype("<i2").tobytes()
        assert separador.processar(ruido) == bytes(len(ruido))


def test_os_bytes_passam_pela_mesma_mascara_e_do_mesmo_tamanho() -> None:
    acorde, cliques = _sinal(TAXA_DO_CABO, segundos=2.0)
    mistura = acorde + cliques
    pelos_bytes = SeparadorDoSom(TAXA_DO_CABO)
    pela_conta = SeparadorDoSom(TAXA_DO_CABO)
    for p in range(0, len(mistura) - BLOCO, BLOCO):
        pcm = _pcm(mistura[p:p + BLOCO])
        saida = pelos_bytes.processar(pcm)
        assert len(saida) == len(pcm)
        (esperado,) = pela_conta.separar(_mono(pcm))
        assert np.max(np.abs(_mono(saida) - esperado)) <= 2.5 / 32768.0
    assert pelos_bytes.processar(b"\x01\x02\x03") == bytes(3)


def test_a_chave_desligada_devolve_o_som_inteiro_e_religada_volta_a_separar() -> None:
    chave = {"ligada": True}
    separador = SeparadorDoSom(TAXA_DO_CABO, so_efeitos=lambda: chave["ligada"])
    acorde, cliques = _sinal(TAXA_DO_CABO)
    mistura = acorde + cliques
    pela_mistura, pelo_acorde = [], []
    for p in range(0, len(acorde) - BLOCO + 1, BLOCO):
        chave["ligada"] = not (2.5 <= p / TAXA_DO_CABO < 4.0)
        a, b = separador.separar(mistura[p:p + BLOCO], acorde[p:p + BLOCO])
        pela_mistura.append(a)
        pelo_acorde.append(b)
    saida = np.concatenate(pelo_acorde)
    atraso = separador.latencia_amostras
    taxa = TAXA_DO_CABO

    def trecho(a: float, b: float) -> float:
        inicio, fim = int(a * taxa), int(b * taxa)
        return _db(saida[inicio + atraso:fim + atraso], acorde[inicio:fim])

    assert trecho(1.0, 2.5) <= -15.0
    assert trecho(2.6, 4.0) >= -0.5, "desligada, a caixa tem de tocar a música"
    assert trecho(4.2, 5.9) <= -20.0, "religada, a música tem de sair de novo"
    janela = slice(int(2.45 * taxa), int(2.6 * taxa))
    degrau_da_saida = float(np.abs(np.diff(np.concatenate(pela_mistura)[janela])).max())
    degrau_da_entrada = float(np.abs(np.diff(mistura[janela])).max())
    assert degrau_da_saida <= 1.5 * degrau_da_entrada, "a troca da chave estalou"


def test_um_separador_por_controle_nao_mistura_o_estado_dos_quatro() -> None:
    acorde, cliques = _sinal(TAXA_DO_RADIO, segundos=3.0)
    sozinho = SeparadorDoSom(TAXA_DO_RADIO)
    quatro = [SeparadorDoSom(TAXA_DO_RADIO) for _ in range(4)]
    entradas = [acorde + cliques, acorde, cliques, acorde * 0.0]
    for p in range(0, len(acorde) - BLOCO, BLOCO):
        trecho = slice(p, p + BLOCO)
        referencia = sozinho.separar(entradas[0][trecho])[0]
        saidas = [s.separar(e[trecho])[0] for s, e in zip(quatro, entradas, strict=True)]
        assert np.array_equal(saidas[0], referencia)
        assert not np.any(saidas[3])


def _bomba(fonte: Any, separador: Any) -> tuple[Any, list[bytes]]:
    capturados: list[bytes] = []
    bomba = af.BombaDeSomPeloRadio(fonte=fonte, seco=True, so_com_sinal=True, separador=separador)

    def _codificar(pcm: bytes) -> bytes:
        capturados.append(bytes(pcm))
        return b"\x01"

    bomba._codificar = _codificar  # type: ignore[method-assign]
    return bomba, capturados


def _fonte_de(mono: Any) -> Any:
    pcm = _pcm(mono)
    posicao = {"p": 0}

    def _ler(quantos: int) -> bytes:
        inicio = posicao["p"]
        posicao["p"] = inicio + quantos
        return pcm[inicio:inicio + quantos]

    return _ler


def _pelo_radio(mono: Any, separador: Any, frente: Any = None) -> tuple[Any, list[bool], Any]:
    bomba, capturados = _bomba(_fonte_de(mono), separador)
    som_no_fio: list[bool] = []
    quadros = len(mono) // BLOCO
    saida = np.zeros(quadros * BLOCO)
    for quadro in range(quadros):
        if frente is not None:
            bomba._frente_do_quadro = _pcm(frente[quadro * BLOCO:(quadro + 1) * BLOCO])
        antes = len(capturados)
        bomba.um_report()
        foi = len(capturados) > antes
        som_no_fio.append(foi)
        if foi:
            saida[quadro * BLOCO:(quadro + 1) * BLOCO] = _mono(capturados[-1])
    return saida, som_no_fio, bomba


def test_pelo_radio_a_musica_sai_da_caixa_e_o_efeito_fica() -> None:
    acorde, cliques = _sinal(TAXA_DO_RADIO)
    atraso = 480
    um = TAXA_DO_RADIO
    separador = af.separador_da_caixa(TAXA_DO_RADIO, True)
    so_musica, _, _ = _pelo_radio(acorde, separador)
    dois = 2 * um
    assert _db(so_musica[dois + atraso:], acorde[dois:len(so_musica) - atraso]) <= -20.0
    so_efeito, _, _ = _pelo_radio(cliques, af.separador_da_caixa(TAXA_DO_RADIO, True))
    assert _db(so_efeito[atraso:], cliques[:len(so_efeito) - atraso]) >= -3.0


def test_pelo_radio_o_no_calado_cala_o_quadro_de_som_depois_do_separador() -> None:
    _, cliques = _sinal(TAXA_DO_RADIO, segundos=4.0)
    cliques[2 * TAXA_DO_RADIO:] = 0.0
    _, som_no_fio, _ = _pelo_radio(cliques, af.separador_da_caixa(TAXA_DO_RADIO, True))
    depois = som_no_fio[int(2.05 * TAXA_DO_RADIO) // BLOCO:]
    assert sum(som_no_fio) >= 3
    assert sum(depois) <= 1, "o separador deixou resto no silêncio e o rádio não cala"


def test_pelo_radio_sem_a_chave_a_caixa_toca_tudo_como_antes() -> None:
    acorde, _ = _sinal(TAXA_DO_RADIO, segundos=2.0)
    assert af.separador_da_caixa(TAXA_DO_RADIO, False) is None
    saida, _, _ = _pelo_radio(acorde, None)
    assert _db(saida, acorde[:len(saida)]) >= -0.1


def test_a_frente_que_o_jogo_manda_ao_controle_nao_passa_pelo_separador() -> None:
    acorde, _ = _sinal(TAXA_DO_RADIO, segundos=3.0)
    silencio = np.zeros_like(acorde)
    separador = af.separador_da_caixa(TAXA_DO_RADIO, True)
    saida, _, bomba = _pelo_radio(silencio, separador, frente=acorde)
    um = TAXA_DO_RADIO
    assert _db(saida[um:], acorde[um:len(saida)]) >= -0.5
    assert bomba.contagem.quadros_com_frente > 0


def test_a_ponte_do_radio_monta_a_bomba_com_o_separador_que_segue_a_chave(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(af, "a_ponte_do_radio_pode_subir", lambda: (True, ""))
    chave = {"ligada": True}

    def _a_chave() -> bool:
        return chave["ligada"]

    bombas = []
    escolhas: tuple[Any, ...] = (_a_chave, False)
    for so_efeitos in escolhas:
        leitura, escrita = os.pipe()
        os.close(leitura)

        def _abrir(fd: int = escrita) -> int:
            return fd

        ponte = af.PonteDeSomPorRadio(
            uniq="aa:bb:cc:00:00:e1",
            abrir_hidraw=_abrir,
            fonte_de_pcm=lambda _q: b"",
            so_efeitos=so_efeitos,
        )
        assert ponte.subir()
        ponte.descer()
        assert ponte._bomba is not None
        bombas.append(ponte._bomba)
    separador = bombas[0].separador
    assert isinstance(separador, SeparadorDoSom)
    chave["ligada"] = False
    assert separador._a_chave() is False
    assert bombas[1].separador is None


class _Processo:
    """Um filho de mentira com um cano de verdade: o separador roda inteiro no meio."""

    def __init__(self, *, stdout: Any = None, stdin: Any = None) -> None:
        self.stdout = stdout
        self.stdin = stdin
        self.returncode: int | None = None
        self.argv: list[str] = []

    def terminate(self) -> None:
        self.returncode = -15

    def kill(self) -> None:
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        if self.returncode is None:
            self.returncode = 0
        return self.returncode


def _pela_caixa_do_cabo(monkeypatch: pytest.MonkeyPatch, mono: Any) -> Any:
    monkeypatch.setattr(af, "argv_do_gravador", lambda *_a, **_k: ["pw-record", "-"])
    monkeypatch.setattr(af, "rotulo_do_gravador", lambda **_k: "hefesto-ponte-teste-caixa")
    monkeypatch.setattr(af, "conferir_o_alvo_do_gravador", lambda _r: "hefesto_som_teste")
    pcm = _pcm(mono)
    leitura_g, escrita_g = os.pipe()
    leitura_t, escrita_t = os.pipe()
    recebido: list[bytes] = []

    def _escrever() -> None:
        with os.fdopen(escrita_g, "wb") as cano:
            cano.write(pcm)

    def _ler() -> None:
        with os.fdopen(leitura_t, "rb") as cano:
            while pedaco := cano.read(65536):
                recebido.append(pedaco)

    gravador = _Processo(stdout=os.fdopen(leitura_g, "rb"))
    tocador = _Processo(stdin=os.fdopen(escrita_t, "wb"))
    argvs: list[list[str]] = []

    def _lancar_tocador(argv: list[str]) -> _Processo:
        argvs.append(argv)
        return tocador

    escritor = threading.Thread(target=_escrever, daemon=True)
    leitor = threading.Thread(target=_ler, daemon=True)
    escritor.start()
    leitor.start()
    caixa = af.CaixaQueSeparaNoCabo(
        uniq="aa:bb:cc:00:00:c1",
        no="hefesto_som_teste",
        sink="alsa_output.placa-do-controle",
        lancar_gravador=lambda _argv: gravador,
        lancar_o_tocador=_lancar_tocador,
        argv_tocador=lambda sink, rotulo: ["pw-cat", f"--target={sink}", rotulo],
    )
    assert caixa.subir(), caixa.motivo
    prazo = time.monotonic() + 30
    while caixa.viva() and time.monotonic() < prazo:
        time.sleep(0.02)
    caixa.descer()
    leitor.join(timeout=5)
    assert argvs == [["pw-cat", "--target=alsa_output.placa-do-controle",
                      "hefesto-ponte-teste-caixa-saida"]]
    saida = b"".join(recebido)
    assert len(saida) == len(pcm) - len(pcm) % af.BYTES_POR_LEITURA_DA_CAIXA
    return _mono(saida)


def test_no_cabo_a_caixa_separada_tira_a_musica_e_guarda_o_efeito(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    acorde, cliques = _sinal(TAXA_DO_CABO)
    atraso = 480
    um = TAXA_DO_CABO
    so_musica = _pela_caixa_do_cabo(monkeypatch, acorde)
    dois = 2 * um
    assert _db(so_musica[dois + atraso:], acorde[dois:len(so_musica) - atraso]) <= -20.0
    so_efeito = _pela_caixa_do_cabo(monkeypatch, cliques)
    assert _db(so_efeito[atraso:], cliques[:len(so_efeito) - atraso]) >= -3.0


def test_o_tocador_da_caixa_toca_so_nos_canais_da_frente_sem_vazar_para_os_motores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(af, "o_servidor_e_o_pipewire", lambda *_a: True)
    argv = af.argv_do_tocador_da_caixa(
        "alsa_output.placa", "rotulo", achar=lambda _b: "/usr/bin/x", serial_de=lambda _s: 77
    )
    assert "--target=77" in argv
    assert "--channel-map=FL,FR" in argv
    assert "channelmix.upmix=false" in argv[argv.index("-P") + 1]
    assert "node.dont-fallback=true" in argv[argv.index("-P") + 1]
    pacat = af.argv_do_tocador_da_caixa(
        "alsa_output.placa", "rotulo", achar=lambda b: None if b == "pw-cat" else "/usr/bin/x"
    )
    assert f"--channel-map={af.CANAIS_DO_ALTO_FALANTE}" in pacat
    assert af.argv_do_tocador_da_caixa("", "rotulo") == []


PLACA = "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller-0{}"
CONTROLES = [f"aa:bb:cc:00:00:{n:02x}" for n in (0xA1, 0xA2, 0xA3, 0xA4)]


class _Servidor:
    """O `pipewire-pulse` de mentira: carrega, descarrega e diz o que está de pé."""

    def __init__(self) -> None:
        self.carregados: dict[str, list[str]] = {}
        self._proximo = 700

    def __call__(self, argv: list[str]) -> str | None:
        if argv[:2] == ["pactl", "load-module"]:
            self._proximo += 1
            self.carregados[str(self._proximo)] = list(argv)
            return f"{self._proximo}\n"
        if argv[:2] == ["pactl", "unload-module"]:
            self.carregados.pop(argv[2], None)
            return ""
        if argv[:4] == ["pactl", "list", "short", "modules"]:
            linhas = ["1\tmodule-native-protocol-unix\t\t"]
            linhas += [f"{i}\t{a[2]}\t{' '.join(a[3:])}\t" for i, a in self.carregados.items()]
            return "\n".join(linhas) + "\n"
        return ""

    def saidas(self) -> set[tuple[str, str]]:
        achados: set[tuple[str, str]] = set()
        for argv in self.carregados.values():
            if argv[2] != "module-loopback":
                continue
            campos = dict(a.split("=", 1) for a in argv[3:] if "=" in a)
            if campos.get("source", "").endswith(".monitor"):
                achados.add((campos["source"], campos.get("sink", "")))
        return achados


class _CaixaDeMentira:
    vivas: ClassVar[list[_CaixaDeMentira]] = []
    recusar: ClassVar[bool] = False

    def __init__(self, *, uniq: str, no: str, sink: str) -> None:
        self.uniq, self.no, self.sink = uniq, no, sink
        self.de_pe = False
        self.motivo = ""

    def subir(self) -> bool:
        if _CaixaDeMentira.recusar:
            self.motivo = "recusada"
            return False
        self.de_pe = True
        _CaixaDeMentira.vivas.append(self)
        return True

    def viva(self) -> bool:
        return self.de_pe

    def descer(self) -> None:
        self.de_pe = False
        if self in _CaixaDeMentira.vivas:
            _CaixaDeMentira.vivas.remove(self)


@pytest.fixture
def servidor(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> _Servidor:
    servidor = _Servidor()
    _CaixaDeMentira.vivas = []
    _CaixaDeMentira.recusar = False
    monkeypatch.setattr(bt, "PACTL", bt.RecuoDoPactl(relogio=lambda: 1000.0))
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.dualsense_bt_audio.shutil.which",
        lambda _nome: "/usr/bin/pactl",
    )
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(af, "_rodar", servidor)
    monkeypatch.setattr(af.SinkVirtualPipeWire, "_passar_a_escolha_do_usuario", lambda _self: None)
    monkeypatch.setattr(af, "CaixaQueSeparaNoCabo", _CaixaDeMentira)
    monkeypatch.setattr(
        af, "sink_do_controle",
        lambda uniq, *_a, **_k: PLACA.format(CONTROLES.index(uniq)) if uniq in CONTROLES else "",
    )
    return servidor


def _mesa(transportes: dict[str, str]) -> list[Any]:
    return [
        mod.ControleNaLista(uniq=u, caminho=f"/dev/hidraw-de-mentira{i}", transporte=t)
        for i, (u, t) in enumerate(transportes.items())
    ]


MESAS = {
    "4-cabos": "cccc",
    "3-cabos-1-radio": "cccr",
    "2-e-2": "crcr",
    "1-cabo-3-radios": "rrrc",
    "4-radios": "rrrr",
}


@pytest.mark.parametrize("arranjo", list(MESAS.values()), ids=list(MESAS))
def test_na_mesa_misturada_cada_cabo_toca_pela_caixa_separada_e_cada_chave_e_do_seu(
    servidor: _Servidor, arranjo: str
) -> None:
    sub = mod.AltoFalanteSubsystem(fonte_de_controles=lambda: [])
    ger = mod.GerenciadorDeNosDeSom(
        fonte_por_controle=lambda _u: af.FONTE_SFX,
        ponte_do_radio_por_controle=lambda _u: (lambda: True),
        runner=servidor,
        so_efeitos_por_controle=sub.so_efeitos,
    )
    transportes = {
        u: ("cabo" if letra == "c" else "rádio")
        for u, letra in zip(reversed(CONTROLES), arranjo, strict=True)
    }
    cabos = [u for u, t in transportes.items() if t == "cabo"]
    ger.reconciliar(_mesa(transportes))

    assert all(sub.so_efeitos(u) for u in CONTROLES), "«Só efeitos» nasce ligado"
    assert servidor.saidas() == set(), "com a chave ligada a placa não recebe o nó inteiro"
    assert sorted(c.uniq for c in _CaixaDeMentira.vivas) == sorted(cabos)
    for caixa in _CaixaDeMentira.vivas:
        assert caixa.sink == PLACA.format(CONTROLES.index(caixa.uniq))
        assert caixa.no == af.nome_do_sink(caixa.uniq)

    if cabos:
        desligado = cabos[-1]
        sub.escolher_so_efeitos(desligado, False)
        ger.reconciliar(_mesa(transportes))
        assert servidor.saidas() == {
            (f"{af.nome_do_sink(desligado)}.monitor", PLACA.format(CONTROLES.index(desligado)))
        }
        assert sorted(c.uniq for c in _CaixaDeMentira.vivas) == sorted(cabos[:-1])
        sub.escolher_so_efeitos(desligado, True)
        ger.reconciliar(_mesa(transportes))
        assert servidor.saidas() == set()
        assert sorted(c.uniq for c in _CaixaDeMentira.vivas) == sorted(cabos)

        saiu = cabos[0]
        ger.reconciliar(_mesa({u: t for u, t in transportes.items() if u != saiu}))
        assert saiu not in [c.uniq for c in _CaixaDeMentira.vivas]
        ger.reconciliar(_mesa(transportes))
        assert sorted(c.uniq for c in _CaixaDeMentira.vivas) == sorted(cabos)

    for no in ger.nos.values():
        no.parar()
    assert _CaixaDeMentira.vivas == []


def test_a_caixa_que_nao_sobe_deixa_o_loopback_e_nao_pisca_a_cada_volta(
    servidor: _Servidor,
) -> None:
    agora = {"t": 100.0}
    uniq = CONTROLES[0]
    rota = af.RotaDoNo(True, sink=PLACA.format(0), por_onde=af.POR_CABO, so_efeitos=True)
    no = af.SinkVirtualPipeWire(uniq=uniq, runner=servidor, rota=rota, relogio=lambda: agora["t"])
    _CaixaDeMentira.recusar = True
    assert no.iniciar()
    fio = {(f"{no.nome}.monitor", PLACA.format(0))}
    assert servidor.saidas() == fio, "sem a caixa, a placa fica com o loopback de sempre"

    _CaixaDeMentira.recusar = False
    agora["t"] += 5.0
    no.religar(rota)
    assert servidor.saidas() == fio and _CaixaDeMentira.vivas == []

    agora["t"] += af.RECUSA_DA_CAIXA_S
    no.religar(rota)
    assert servidor.saidas() == set()
    assert [c.uniq for c in _CaixaDeMentira.vivas] == [uniq]

    _CaixaDeMentira.vivas[0].de_pe = False
    agora["t"] += 1.0
    no.religar(rota)
    assert servidor.saidas() == fio, "a caixa que caiu devolve o loopback"
    no.parar()
    assert servidor.carregados == {}


def test_sem_numpy_a_rota_segue_sem_a_chave(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.integrations import separador_do_som as sep

    monkeypatch.setattr(sep, "o_separador_cabe_aqui", lambda: False)
    rota = af.rota_do_no(
        CONTROLES[0], af.TRANSPORTE_CABO, so_efeitos=True,
        runner=lambda _a: "", ponte_do_radio=None,
    )
    assert rota.so_efeitos is False
    assert af.separador_da_caixa(TAXA_DO_RADIO, True) is None


def test_a_chave_e_de_cada_controle_e_nasce_ligada() -> None:
    sub = mod.AltoFalanteSubsystem(fonte_de_controles=lambda: [])
    sub._acordar_a_volta = lambda *_a: None  # type: ignore[method-assign]
    for uniq in CONTROLES:
        assert sub.so_efeitos(uniq) is True
    sub.escolher_so_efeitos(CONTROLES[2], False)
    assert [sub.so_efeitos(u) for u in CONTROLES] == [True, True, False, True]
    assert sub.so_efeitos(CONTROLES[2].upper().replace(":", "")) is False
    assert sub.escolher_so_efeitos("", True) is False


class _PonteDeMentira:
    criadas: ClassVar[list[_PonteDeMentira]] = []

    def __init__(self, **kw: Any) -> None:
        self.uniq = kw["uniq"]
        self.so_efeitos = kw.get("so_efeitos", False)
        self.motivo = ""
        self.subiu = False
        _PonteDeMentira.criadas.append(self)

    def subir(self) -> bool:
        self.subiu = True
        return True

    def descer(self, **_: Any) -> bool:
        self.subiu = False
        return True

    def esta_de_pe(self) -> bool:
        return self.subiu


class _GerenciadorQueSoOuve:
    def reconciliar(self, controles: list[Any] | None = None) -> None:
        del controles

    def dormir(self, _s: float) -> bool:
        return False

    def parar(self) -> None:
        return None


def test_cada_ponte_do_radio_leva_a_chave_viva_do_seu_controle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hefesto_dualsense4unix.integrations import hidraw_broker_client as broker
    from tests.unit.o_alto_falante_que_toca import todo_alto_falante_toca

    _PonteDeMentira.criadas = []
    monkeypatch.setattr(
        af, "fonte_do_monitor_do_no", lambda no, **_k: ((lambda _n: b""), f"gravador:{no}", "")
    )
    monkeypatch.setattr(af, "PonteDeSomPorRadio", _PonteDeMentira)
    todo_alto_falante_toca(monkeypatch)
    monkeypatch.setattr(broker, "abrir_hidraw", lambda no, **_: SimpleNamespace(fd=101))
    controles = [
        SimpleNamespace(uniq=u, caminho=f"/dev/hidraw{i}", transporte=t)
        for i, (u, t) in enumerate(
            zip(CONTROLES, ("bluetooth", "usb", "bluetooth", "bluetooth"), strict=True)
        )
    ]
    ger = _GerenciadorQueSoOuve()
    sub = mod.AltoFalanteSubsystem(gerenciador=ger, fonte_de_controles=lambda: list(controles))
    sub._gerenciador = ger
    sub._acordar_a_volta = lambda *_a: None  # type: ignore[method-assign]
    sub._reconciliar(ger)

    pontes = {p.uniq: p for p in _PonteDeMentira.criadas}
    assert sorted(pontes) == sorted([CONTROLES[0], CONTROLES[2], CONTROLES[3]])
    assert all(callable(p.so_efeitos) and p.so_efeitos() for p in pontes.values())
    sub.escolher_so_efeitos(CONTROLES[2], False)
    assert {u: p.so_efeitos() for u, p in pontes.items()} == {
        CONTROLES[0]: True, CONTROLES[2]: False, CONTROLES[3]: True,
    }
