"""O-TERCEIRO-NOME-DELA-01 — o QUARTO botão do alto-falante, e a saída do PC é UMA.

**DECISÃO DELA, 23/09/2026** (`D-2309-O-QUARTO-BOTAO-VOLTA`), respondendo à
pergunta que a sprint deixou aberta em 20/09:

    "Gostaria de voltar o botão o 4 mas acho que quebraria o layout
    vertical. Na real temos que encaixar ele. Mas fazer isso certo com
    mockup antes."
    <!-- noqa-acento: citação literal dela -->

O quarto é «Tudo no Controle e Nada no PC»: a rota 3 no firmware mais a saída
padrão do sistema mandada para ESTE controle. É o `pc` que o gesto, o IPC e a
CLI já conheciam.

**ESTA RÉGUA MEDE ONDE O SOM SAI, e não o campo gravado** — é o §5 da sprint:
*"uma que só confere o valor no disco passa verde sobre o defeito que esta
família já teve"*. O servidor de som aqui é de mentira, mas com ESTADO: ele
guarda a saída padrão e recusa trocar para um sink que não existe, como o de
verdade. Depois de cada clique a pergunta é a do ouvido dela — *para onde vai
o som do PC agora?* — e a da tela — *que botão cada cartão acende?*.

**A MESA É A DELA, e não só o P1**: dois controles no USB e dois no BT. A
saída do PC é UMA para a máquina, e é na troca entre controles que as duas
curas de 24/09 mordem:

* a VOLTA só acontece a partir de quem está com a saída
  (`audio_saida.devolver_o_som_do_pc`, parâmetro `de`) — sem isso, o botão do
  meio do P3 desfazia o quarto do P1;
* a MEMÓRIA da volta não troca o PC por outro controle
  (`RotaDeSaida.mandar_para_o_controle`) — sem isso, passar a saída do P1 ao
  P3 e devolver deixava o som do PC preso no plástico do P1.

A MORDIDA de cada teste está na docstring dele. Nada aqui toca o PipeWire, o
daemon ou o perfil dela: o `pactl` é o servidor de mentira abaixo, o daemon é a
ponte de papel, e o perfil mora num `XDG_CONFIG_HOME` de teste.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    nome_do_sink,
)

#: A mesa dela, com endereços da faixa sintética desta casa.
P1, P2, P3, P4 = (f"aa:bb:cc:00:00:0{n}" for n in (1, 2, 3, 4))
TRANSPORTE = {P1: "usb", P2: "usb", P3: "bluetooth", P4: "bluetooth"}
NOME = "Regua-Do-Quarto-Botao"

#: A saída de cada controle: a placa da Sony no USB, o nó desta casa no BT. E o
#: PC — a saída que ela tem antes de clicar em qualquer coisa.
PLACA = ("alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
         "Controller-00.analog-surround-40")
SAIDA = {P1: PLACA, P2: PLACA.replace("-00.", "-00.2."),
         P3: nome_do_sink(P3), P4: nome_do_sink(P4)}
PC = "alsa_output.pci-0000_0a_00.1.hdmi-stereo"


class ServidorDeSom:
    """O `pactl` de mentira, COM ESTADO. Ele guarda a saída padrão e recusa
    trocar para o que não existe — o de verdade responde erro e fica onde
    estava, e um dublê que aceitasse qualquer nome seria mais frouxo que ele.
    """

    def __init__(self) -> None:
        self.padrao = PC
        self.sinks = [PC, *SAIDA.values()]
        self.pedidos: list[list[str]] = []

    def __call__(self, argv: list[str]) -> str:
        self.pedidos.append(list(argv))
        if argv[:4] == ["pactl", "list", "sinks", "short"]:
            return "\n".join(f"{50 + i}\t{nome}\tPipeWire\ts16le 2ch 48000Hz\tIDLE"
                             for i, nome in enumerate(self.sinks))
        if argv[:2] == ["pactl", "get-default-sink"]:
            return self.padrao + "\n"
        if argv[:2] == ["pactl", "set-default-sink"]:
            if argv[2] in self.sinks:
                self.padrao = argv[2]
            return ""
        if argv[:2] == ["pactl", "get-sink-mute"]:
            return "Mute: no\n"
        return ""


class Ponte:
    """O daemon de papel: guarda o byte e a `fonte` de cada controle."""

    def __init__(self) -> None:
        self.byte = {u: 2 for u in TRANSPORTE}
        self.fonte = {u: "sfx" for u in TRANSPORTE}
        self.pedidos: list[dict[str, Any]] = []

    def speaker_set(self, **k: Any) -> bool:
        self.pedidos.append(dict(k))
        uniq = str(k.get("uniq") or "")
        if uniq not in self.byte:
            return False
        if "rota" in k:
            self.byte[uniq] = int(k["rota"])
        if "fonte" in k:
            self.fonte[uniq] = str(k["fonte"])
        return True

    def __getattr__(self, nome: str) -> Any:
        return lambda *a, **k: True


@pytest.fixture
def mesa(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """A mesa de quatro, o servidor de som de mentira e a memória da volta."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from hefesto_dualsense4unix.app import audio_saida
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir
    from pacotes import a02_controles as a02

    profiles_dir().mkdir(parents=True, exist_ok=True)
    loader.save_profile(Profile(name=NOME, match=MatchManual()), origem="regua")

    servidor = ServidorDeSom()
    memoria = {"anterior": ""}
    monkeypatch.setattr(audio_saida, "rodar_leitura", servidor)
    monkeypatch.setattr(audio_saida, "_ler_anterior", lambda: memoria["anterior"])
    monkeypatch.setattr(audio_saida, "_gravar_anterior",
                        lambda s: memoria.__setitem__("anterior", s))

    def _saida_deste(uniq: str, uniqs_na_mesa: Any = (), *, runner: Any = None) -> str:
        # O CASAMENTO É OUTRA RÉGUA (`test_o_no_do_radio_conta_como_placa`).
        # Aqui a resposta é a do dono, e só se o sink estiver vivo — como a
        # de verdade, que nunca devolve um nome que o servidor não tem.
        nome = SAIDA.get(uniq, "")
        return nome if nome in servidor.sinks else ""

    monkeypatch.setattr(audio_saida, "sink_do_controle", _saida_deste)
    monkeypatch.setattr(audio_saida, "tocar_confirmacao", lambda *a, **k: None)
    lacos: dict[str, list[str]] = {"ligou": [], "desligou": []}
    monkeypatch.setattr(a02.som_do_controle_na_tv, "ligar",
                        lambda u, **k: lacos["ligou"].append(u) or True)
    monkeypatch.setattr(a02.som_do_controle_na_tv, "desligar",
                        lambda u, **k: lacos["desligou"].append(u) or True)
    antes = dict(a02._CAMADA_1)
    a02._CAMADA_1.clear()
    yield {"servidor": servidor, "memoria": memoria, "ponte": Ponte(),
           "lacos": lacos}
    a02._CAMADA_1.clear()
    a02._CAMADA_1.update(antes)


def _entry(uniq: str, ponte: Ponte) -> dict[str, Any]:
    return {"uniq": uniq, "transport": TRANSPORTE[uniq], "connected": True,
            "inputs": {}, "audio": {"mic_mudo": False},
            "speaker": {"volume": 100, "muted": False, "rota": ponte.byte[uniq],
                        "fonte": ponte.fonte[uniq]}}


def _clicar(m: dict[str, Any], uniq: str, rota: str) -> None:
    """O clique dela, pelo mesmo gesto que a página chama."""
    import pacotes
    import pacotes.a02_controles  # importar é registrar

    ponte = m["ponte"]
    ctx = pacotes.Contexto(state={"active_profile": NOME}, mesa=[],
                           conectados=[_entry(u, ponte) for u in TRANSPORTE],
                           estados={})
    fn = pacotes.gesto_da_pagina("02-controles.html", "rota")
    assert fn is not None, "o botão da rota perdeu o dono"
    fn(ctx, {"uniq": uniq, "rota": rota}, ponte)


def _fileira(m: dict[str, Any]) -> dict[str, str]:
    """O que cada cartão ACENDE agora — lendo as duas camadas, como a aba lê."""
    from hefesto_dualsense4unix.app import audio_saida
    from pacotes import a02_controles as a02

    ponte = m["ponte"]
    na_mesa = list(TRANSPORTE)
    for u in TRANSPORTE:
        a02._CAMADA_1[u] = audio_saida.ler_as_duas_camadas(u, ponte.byte[u], na_mesa)
    return {u: a02.aceso_da_fileira(u, _entry(u, ponte)) for u in TRANSPORTE}


# ===========================================================================
# 1. O quarto manda a saída do PC para o controle DELE — nos quatro
# ===========================================================================


@pytest.mark.parametrize("uniq", [P1, P2, P3, P4], ids=["p1-usb", "p2-usb", "p3-bt", "p4-bt"])
def test_o_quarto_manda_o_som_do_pc_so_para_aquele_controle(
        mesa: dict[str, Any], uniq: str) -> None:
    """O som do PC sai no controle clicado, e o firmware dele toca SÓ o
    alto-falante. Os outros três não mudam de botão.

    MORDIDA: troque, no gesto, o `mandar_o_som_do_pc` do quarto pelo
    `devolver_o_som_do_pc`. O byte vai, a tela acenderia — e o som do PC
    continuaria no PC, que é a mentira que esta família já contou.
    """
    _clicar(mesa, uniq, "pc")

    assert mesa["servidor"].padrao == SAIDA[uniq], (
        f"o som do PC foi para {mesa['servidor'].padrao!r}, e o botão clicado "
        f"é o do controle cuja saída é {SAIDA[uniq]!r}")
    assert mesa["ponte"].byte[uniq] == 3, "o firmware não foi para «só o alto-falante»"
    com_byte = [p for p in mesa["ponte"].pedidos if "rota" in p]
    assert all(p["uniq"] == uniq for p in com_byte), (
        f"o quarto mexeu no byte de outro controle: {com_byte}")
    acesos = _fileira(mesa)
    assert acesos[uniq] == "pc", acesos
    assert all(acesos[u] == "jogo" for u in TRANSPORTE if u != uniq), acesos


@pytest.mark.parametrize("volta", ["jogo", "junto", "nada"])
@pytest.mark.parametrize("uniq", [P1, P3], ids=["p1-usb", "p3-bt"])
def test_sair_do_quarto_devolve_o_som_ao_pc(
        mesa: dict[str, Any], uniq: str, volta: str) -> None:
    """Qualquer um dos outros três botões devolve a saída ao PC — é o «no PC»
    que os três nomes dizem.

    MORDIDA: faça `devolver_o_som_do_pc` recusar sempre que receber `de`. O
    firmware muda, a tela troca de botão, e o som do PC fica no controle.
    """
    _clicar(mesa, uniq, "pc")
    _clicar(mesa, uniq, volta)

    assert mesa["servidor"].padrao == PC, (
        f"depois de «{volta}» o som do PC ficou em {mesa['servidor'].padrao!r}")
    assert _fileira(mesa)[uniq] == volta


# ===========================================================================
# 2. A saída é UMA — o clique de um jogador não desfaz o do outro
# ===========================================================================


def test_o_botao_de_um_nao_desfaz_o_quarto_do_outro(mesa: dict[str, Any]) -> None:
    """O P1 (USB) pede a saída do PC; o P3 e o P4 (BT) trocam de botão. A
    saída continua no P1.

    MORDIDA: tire o `de=uniq` da volta nos ramos do gesto. O «Efeitos do Jogo
    e Áudio do PC no Controle» do P3 devolve ao PC a saída que o P1 pediu, e o
    cartão do P1 apaga sem ninguém ter tocado nele.
    """
    _clicar(mesa, P1, "pc")
    _clicar(mesa, P3, "junto")
    _clicar(mesa, P4, "nada")
    _clicar(mesa, P2, "jogo")

    assert mesa["servidor"].padrao == SAIDA[P1], (
        f"o som do PC saiu do P1 sem ele pedir: está em {mesa['servidor'].padrao!r}")
    acesos = _fileira(mesa)
    assert acesos == {P1: "pc", P2: "jogo", P3: "junto", P4: "nada"}, acesos


def test_a_saida_passa_de_um_controle_ao_outro_e_volta_ao_pc(
        mesa: dict[str, Any]) -> None:
    """O P1 (USB) pede, o P3 (BT) pede depois — o último clique decide
    (`D-2109`). Quando o P3 larga, o som volta ao PC, e não ao P1.

    MORDIDA: devolva a `RotaDeSaida.mandar_para_o_controle` a gravar sempre o
    `atual`. A memória guarda o P1 no lugar do PC, a volta do P3 manda o som
    do PC para o plástico do P1, e o «Efeitos do Jogo no Controle, Áudio do PC
    no PC» do P1 depois não tem mais para onde devolver.
    """
    _clicar(mesa, P1, "pc")
    _clicar(mesa, P3, "pc")
    assert mesa["servidor"].padrao == SAIDA[P3]
    acesos = _fileira(mesa)
    # O P1 APAGA, e é a linha honesta da tabela de `botao_da_rota_aceso`: o
    # firmware dele ainda está no «só o alto-falante», e a saída do PC não é
    # mais ele — nenhum dos quatro nomes descreve isso.
    assert acesos[P3] == "pc" and acesos[P1] == "", acesos

    _clicar(mesa, P3, "jogo")
    assert mesa["servidor"].padrao == PC, (
        f"o P3 largou e o som do PC foi para {mesa['servidor'].padrao!r}")

    _clicar(mesa, P1, "jogo")
    assert mesa["servidor"].padrao == PC
    assert _fileira(mesa) == {u: "jogo" for u in TRANSPORTE}


# ===========================================================================
# 3. O quarto é um estado só com os outros três
# ===========================================================================


def test_o_quarto_apaga_o_mix_e_fecha_o_laco(mesa: dict[str, Any]) -> None:
    """Vindo do «Efeitos do Jogo e Áudio do PC no Controle» (o `mix`), o
    quarto diz `sfx` ao nó; vindo do «Tudo no PC e Nada no Controle» (o laço
    que manda o som do controle ao PC), ele fecha o laço. Com os dois de pé o
    som daria a volta: o PC no controle, e o controle de novo no PC.

    MORDIDA: tire o ramo do `mix` que vem antes da camada 1 no gesto.
    """
    _clicar(mesa, P2, "junto")
    assert mesa["ponte"].fonte[P2] == "mix"
    _clicar(mesa, P2, "pc")
    assert mesa["ponte"].fonte[P2] == "sfx", "o `mix` ficou de pé embaixo do quarto"

    _clicar(mesa, P4, "nada")
    assert P4 in mesa["lacos"]["ligou"]
    antes = mesa["lacos"]["desligou"].count(P4)
    _clicar(mesa, P4, "pc")
    assert mesa["lacos"]["desligou"].count(P4) > antes, (
        "o laço do terceiro ficou de pé embaixo do quarto")


# ===========================================================================
# 4. As duas curas, no dono
# ===========================================================================


def test_a_memoria_guarda_o_pc_quando_a_saida_passa_entre_controles() -> None:
    """MORDIDA: a mesma do teste da troca — grave sempre o `atual`."""
    from hefesto_dualsense4unix.app.audio_saida import RotaDeSaida

    servidor = ServidorDeSom()
    memoria = {"anterior": ""}
    rota = RotaDeSaida(runner=servidor, ler_memoria=lambda: memoria["anterior"],
                       gravar_memoria=lambda s: memoria.__setitem__("anterior", s))

    assert rota.mandar_para_o_controle(SAIDA[P1])
    assert memoria["anterior"] == PC
    assert rota.mandar_para_o_controle(SAIDA[P3])
    assert memoria["anterior"] == PC, "a memória trocou o PC pelo P1"


def test_sem_memoria_a_saida_de_um_controle_ainda_e_para_onde_voltar() -> None:
    """A outra metade: quando ninguém guardou nada (a saída foi posta no P1
    pelo painel do sistema), o P1 É o único caminho de volta que existe — e
    não guardá-lo deixaria a volta sem destino nenhum.

    MORDIDA: recuse gravar qualquer saída de controle, com ou sem memória.
    """
    from hefesto_dualsense4unix.app.audio_saida import RotaDeSaida

    servidor = ServidorDeSom()
    servidor.padrao = SAIDA[P1]
    memoria = {"anterior": ""}
    rota = RotaDeSaida(runner=servidor, ler_memoria=lambda: memoria["anterior"],
                       gravar_memoria=lambda s: memoria.__setitem__("anterior", s))

    assert rota.mandar_para_o_controle(SAIDA[P3])
    assert memoria["anterior"] == SAIDA[P1]


def test_a_volta_recusa_quem_nao_esta_com_a_saida() -> None:
    """MORDIDA: apague o bloco do `de` em `devolver_o_som_do_pc`."""
    from hefesto_dualsense4unix.app import audio_saida

    servidor = ServidorDeSom()
    servidor.padrao = SAIDA[P1]
    trocas: list[str] = []

    class Motor:
        def voltar_ao_anterior(self) -> bool:
            trocas.append("voltou")
            return True

    original = audio_saida.sink_do_controle
    audio_saida.sink_do_controle = lambda u, m=(), *, runner=None: SAIDA.get(u, "")
    try:
        desfecho = audio_saida.devolver_o_som_do_pc(
            de=P3, uniqs_na_mesa=list(TRANSPORTE), rota=Motor(), runner=servidor)
        assert not desfecho.ok
        assert desfecho.motivo == audio_saida.MOTIVO_A_SAIDA_NAO_E_DESTE
        assert trocas == [], "a volta aconteceu a partir de quem não tinha a saída"

        desfecho = audio_saida.devolver_o_som_do_pc(
            de=P1, uniqs_na_mesa=list(TRANSPORTE), rota=Motor(), runner=servidor)
        assert desfecho.ok and trocas == ["voltou"]
    finally:
        audio_saida.sink_do_controle = original


@pytest.mark.parametrize(
    ("sink", "e_de_controle"),
    [(PLACA, True), (SAIDA[P2], True), (SAIDA[P3], True), (PC, False), ("", False)],
    ids=["placa-p1", "placa-p2", "no-do-radio", "o-pc", "vazio"],
)
def test_quem_e_saida_de_controle(sink: str, e_de_controle: bool) -> None:
    """A placa da Sony e o nó desta casa são de controle; a saída do PC não.

    MORDIDA: responda só pelo prefixo do nó — as placas do USB viram «PC», e a
    memória volta a guardar o P1 no lugar da TV dela.
    """
    from hefesto_dualsense4unix.app.audio_saida import e_saida_de_controle

    lista_viva = ServidorDeSom()(["pactl", "list", "sinks", "short"])
    assert e_saida_de_controle(sink, lista_viva) is e_de_controle


# ===========================================================================
# 5. No USB, o dono de verdade — sem o dublê do `sink_do_controle`
# ===========================================================================


def test_no_cabo_o_quarto_escolhe_a_placa_e_a_volta_pergunta_ao_dono() -> None:
    """Os testes acima trocam o `sink_do_controle` por um dicionário. Este não:
    no USB quem responde é o `escolher_sink` sobre a placa da Sony, e a placa
    é o destino do quarto, e não o «Alto-falante do Controle N» (o nó desta
    casa, que no cabo termina na mesma placa). A bancada manda conferir isso
    (`audio.saida_dedicada-cabo`, linha 19): a lista do sistema mostra a placa.

    E a volta vale a partir da placa, não do nó: a saída que ela escolheu pela
    lista, no nó, é ela quem devolve pela lista.

    MORDIDA: no bloco do `de` de `devolver_o_som_do_pc`, troque
    `padrao != deste` por `False` — o nó escolhido pela lista passa a ser
    devolvido pelo botão de cima.
    """
    from hefesto_dualsense4unix.app import audio_saida

    servidor = ServidorDeSom()
    servidor.sinks = [PC, PLACA, nome_do_sink(P1)]
    memoria = {"anterior": ""}
    rota = audio_saida.RotaDeSaida(
        runner=servidor, ler_memoria=lambda: memoria["anterior"],
        gravar_memoria=lambda s: memoria.__setitem__("anterior", s))

    desfecho = audio_saida.mandar_o_som_do_pc(P1, (P1,), rota=rota, runner=servidor)
    assert desfecho.ok, desfecho.motivo
    assert servidor.padrao == PLACA, (
        f"no USB o quarto mandou o som para {servidor.padrao!r}, e o dono "
        f"(`escolher_sink`) diz que a saída do P1 é a placa")

    class Motor:
        voltas = 0

        def voltar_ao_anterior(self) -> bool:
            Motor.voltas += 1
            return True

    assert audio_saida.devolver_o_som_do_pc(
        de=P1, uniqs_na_mesa=(P1,), rota=Motor(), runner=servidor).ok
    assert Motor.voltas == 1

    servidor.padrao = nome_do_sink(P1)
    desfecho = audio_saida.devolver_o_som_do_pc(
        de=P1, uniqs_na_mesa=(P1,), rota=Motor(), runner=servidor)
    assert not desfecho.ok and Motor.voltas == 1, (
        "o botão de cima devolveu uma saída que o quarto não levou — ela a "
        "escolheu pela lista")
