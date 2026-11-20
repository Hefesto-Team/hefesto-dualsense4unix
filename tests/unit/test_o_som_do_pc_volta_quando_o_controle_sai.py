"""O som do PC volta à saída de antes quando o controle sai (O-SOM-DO-PC-VOLTA-QUANDO-...-SAI).

Com «todo o som no controle» a saída padrão é o nó ``hefesto_som_<marca>``. O nó fica de pé quando
o controle sai (D-0809), então o serviço devolve a saída padrão: ao sink guardado, ou à primeira
saída que não é de controle nem desta casa, e a repõe no nó quando o controle volta. O servidor é
o de mentira (``pactl`` dos sinks e da saída padrão); a rota de saída e o subsistema são os reais.

MORDIDAS: tirar o passo ``saida_padrao`` da volta deixa o padrão no nó sem rota; tirar a conferência
de que a saída padrão é o nó derruba a escolha de outra fonte; tirar a reposição deixa o som na TV
depois que o controle volta; contar o rádio mudo sem ponte como sem rota desfaz a escolha no
silêncio e nunca a repõe; repor sem a volta à lista nem a ponte faz o som ir e voltar.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.app.audio_saida import RotaDeSaida
from hefesto_dualsense4unix.daemon.subsystems import alto_falante as af
from hefesto_dualsense4unix.integrations.alto_falante_bt import nome_do_sink

P = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03", "aa:bb:cc:00:00:04")
HDMI = "alsa_output.pci-0000_01_00.1.hdmi-stereo"
FONE = "alsa_output.usb-fone.analog-stereo"
RADIO, CABO = "bt", "usb"


class _Servidor:
    """Os sinks e a saída padrão; ``set-default-sink`` só pega num sink que existe."""

    def __init__(self, padrao: str, sinks: list[str]) -> None:
        self.padrao = padrao
        self.sinks = sinks
        self.escritas: list[str] = []

    def __call__(self, argv: list[str]) -> str:
        if argv[:2] == ["pactl", "get-default-sink"]:
            return self.padrao + "\n"
        if argv[:4] == ["pactl", "list", "sinks", "short"]:
            return "".join(f"{i}\t{n}\tPipeWire\ts16le\tIDLE\n" for i, n in enumerate(self.sinks))
        if argv[:2] == ["pactl", "set-default-sink"]:
            self.escritas.append(argv[2])
            if argv[2] in self.sinks:
                self.padrao = argv[2]
        return ""


class _Gerenciador:
    """O nó de cada controle que entrou fica de pé: só o ``parar`` o derruba."""

    def __init__(self) -> None:
        self.nos: dict[str, Any] = {}

    def reconciliar(self, alvos: list[Any]) -> None:
        for controle in alvos:
            self.nos.setdefault(controle.uniq, object())


class _Mesa:
    def __init__(self, monkeypatch: pytest.MonkeyPatch, padrao: str, guardada: str = "",
                 sinks: list[str] | None = None) -> None:
        self.no = {u: nome_do_sink(u) for u in P}
        self.servidor = _Servidor(padrao, sinks or [HDMI, FONE, *self.no.values()])
        self.memoria = guardada
        self.rota = RotaDeSaida(
            runner=self.servidor, ler_memoria=lambda: self.memoria,
            gravar_memoria=lambda sink: setattr(self, "memoria", sink))
        self.na_lista: list[af.ControleNaLista] = []
        self.sub = af.AltoFalanteSubsystem(
            fonte_de_controles=lambda: self.na_lista, rota_de_saida=self.rota)
        self.gerenciador = _Gerenciador()
        for nome in ("_anotar_o_que_a_volta_viu", "_anotar_as_placas", "_anotar_o_pc_inteiro",
                     "_casar_as_pontes"):
            monkeypatch.setattr(self.sub, nome, lambda *_a: None)

    def lista(self, *uniqs: str, transporte: str = RADIO, tocando: bool = True) -> None:
        """Os controles na lista; no rádio, o nó que toca tem a ponte de pé, e o mudo não."""
        self.na_lista = [af.ControleNaLista(u, f"/dev/hidraw{i}", transporte)
                         for i, u in enumerate(uniqs)]
        radio = {u for u in uniqs if transporte == RADIO}
        self.sub._pontes = {u: object() for u in radio} if tocando else {}
        self.sub._nos_que_tocam = set(radio) if tocando else set()

    def volta(self, vezes: int = 1) -> None:
        for _ in range(vezes):
            self.sub._reconciliar(self.gerenciador)


def _mesa(monkeypatch: pytest.MonkeyPatch, padrao: str, **kw: Any) -> _Mesa:
    return _Mesa(monkeypatch, padrao, **kw)


def test_o_controle_que_sai_devolve_o_som_ao_sink_guardado_e_o_repoe_na_volta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-1911-O-SOM-DO-PC-VOLTA-QUANDO-O-CONTROLE-SAI: sai e a TV toca, volta e o som vai a ele."""
    mesa = _mesa(monkeypatch, padrao=nome_do_sink(P[0]), guardada=HDMI)
    mesa.lista(P[0], P[1])
    mesa.volta()
    assert mesa.servidor.padrao == nome_do_sink(P[0]), "o controle está na lista e o som é dele"
    mesa.lista(P[1])
    mesa.volta()
    assert mesa.servidor.padrao == nome_do_sink(P[0]), "a saída mudou na primeira volta sem ele"
    mesa.volta()
    assert mesa.servidor.padrao == HDMI, "o PC ficou mudo: o padrão ficou no nó sem rota"
    assert mesa.memoria == "", "a saída guardada foi usada e esquecida"
    mesa.lista(P[0], P[1])
    mesa.volta()
    assert mesa.servidor.padrao == nome_do_sink(P[0]), "o controle voltou e o som não"
    assert mesa.memoria == HDMI, "a saída de antes ficou guardada para a próxima saída"


def test_sem_saida_guardada_viva_o_som_vai_a_primeira_saida_que_nao_e_do_controle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-1911-O-SOM-DO-PC-VOLTA-QUANDO-O-CONTROLE-SAI: guardada morta, vai à primeira comum."""
    sinks = [nome_do_sink(P[1]), "hefesto_haptica_x", FONE, HDMI, nome_do_sink(P[0])]
    mesa = _mesa(monkeypatch, padrao=nome_do_sink(P[0]), guardada="alsa_output.sumiu", sinks=sinks)
    mesa.lista(P[0], P[1])
    mesa.volta()
    mesa.lista(P[1])
    mesa.volta(2)
    assert mesa.servidor.padrao == FONE, "foi a um nó desta casa, ou a nenhuma saída"
    assert mesa.memoria == "alsa_output.sumiu"


def test_a_saida_padrao_de_outra_fonte_nao_e_tocada(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-1911-O-SOM-DO-PC-VOLTA-QUANDO-O-CONTROLE-SAI: o padrão que não é o nó fica como está."""
    mesa = _mesa(monkeypatch, padrao=FONE, guardada=HDMI)
    mesa.lista(P[0])
    mesa.volta()
    mesa.lista()
    mesa.volta(3)
    assert mesa.servidor.escritas == [] and mesa.servidor.padrao == FONE
    mesa.lista(P[0])
    mesa.volta()
    assert mesa.servidor.escritas == []


def test_quem_mudou_o_padrao_depois_da_devolucao_nao_perde_a_escolha_na_volta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-1911-O-SOM-DO-PC-VOLTA-QUANDO-O-CONTROLE-SAI: a reposição vale só sobre a devolvida."""
    mesa = _mesa(monkeypatch, padrao=nome_do_sink(P[0]), guardada=HDMI)
    mesa.lista(P[0])
    mesa.volta()
    mesa.lista()
    mesa.volta(2)
    assert mesa.servidor.padrao == HDMI
    mesa.servidor.padrao = FONE
    mesa.lista(P[0])
    mesa.volta()
    assert mesa.servidor.padrao == FONE, "o controle voltou e levou o som que era de outra saída"


@pytest.mark.parametrize("transportes", [
    (RADIO, RADIO, RADIO, RADIO), (CABO, RADIO, CABO, RADIO), (CABO, CABO, CABO, CABO)])
def test_com_quatro_controles_so_a_saida_do_no_que_perdeu_a_rota_volta(
    monkeypatch: pytest.MonkeyPatch, transportes: tuple[str, ...],
) -> None:
    """D-1911-O-SOM-DO-PC-VOLTA-QUANDO-O-CONTROLE-SAI: sai e volta um controle, os outros ficam."""
    mesa = _mesa(monkeypatch, padrao=nome_do_sink(P[2]), guardada=HDMI)
    todos = list(zip(P, transportes, strict=True))

    def lista(*fora: str) -> None:
        mesa.na_lista = [af.ControleNaLista(u, f"/dev/hidraw{i}", t)
                         for i, (u, t) in enumerate(todos) if u not in fora]
        mesa.sub._pontes = {c.uniq: object() for c in mesa.na_lista if c.transporte == RADIO}
        mesa.sub._nos_que_tocam = set(mesa.sub._pontes)

    lista()
    mesa.volta()
    for saiu in (P[0], P[1], P[3]):
        lista(saiu)
        mesa.volta(3)
        assert mesa.servidor.padrao == nome_do_sink(P[2]), "saiu outro controle e o som foi mexido"
        lista()
        mesa.volta()
    lista(P[2])
    mesa.volta(2)
    assert mesa.servidor.padrao == HDMI
    lista()
    mesa.volta()
    assert mesa.servidor.padrao == nome_do_sink(P[2])


def test_o_radio_sem_ponte_em_duas_voltas_devolve_o_som(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-1911-O-SOM-DO-PC-VOLTA-QUANDO-O-CONTROLE-SAI: o nó sem ponte não é destino de som."""
    mesa = _mesa(monkeypatch, padrao=nome_do_sink(P[0]), guardada=HDMI)
    mesa.lista(P[0])
    mesa.volta(3)
    assert mesa.servidor.padrao == nome_do_sink(P[0]), "o rádio com ponte perdeu o som"
    mesa.sub._pontes.clear()
    mesa.volta()
    assert mesa.servidor.padrao == nome_do_sink(P[0]), "devolveu na primeira volta sem ponte"
    mesa.volta()
    assert mesa.servidor.padrao == HDMI
    mesa.sub._pontes[P[0]] = object()
    mesa.volta()
    assert mesa.servidor.padrao == nome_do_sink(P[0]), "a ponte voltou e o som não"


def test_o_radio_em_silencio_sem_ponte_segue_com_o_som_que_se_escolheu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-1911-O-SOM-DO-PC-VOLTA-QUANDO-O-CONTROLE-SAI: o nó mudo desce a ponte e fica o padrão."""
    mesa = _mesa(monkeypatch, padrao=nome_do_sink(P[0]), guardada=HDMI)
    mesa.lista(P[0], tocando=False)
    mesa.volta(4)
    assert mesa.servidor.escritas == [], "o PC em silêncio desfez a escolha do som no controle"


def test_o_radio_que_volta_sem_ponte_recebe_o_som_de_volta(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-1911-O-SOM-DO-PC-VOLTA-QUANDO-O-CONTROLE-SAI: o nó que voltou mudo ganha o som de novo."""
    mesa = _mesa(monkeypatch, padrao=nome_do_sink(P[0]), guardada=HDMI)
    mesa.lista(P[0])
    mesa.volta()
    mesa.lista()
    mesa.volta(2)
    assert mesa.servidor.padrao == HDMI
    mesa.lista(P[0], tocando=False)
    mesa.volta()
    assert mesa.servidor.padrao == nome_do_sink(P[0]), "a ponte só sobe se o nó toca, e não toca"


def test_o_som_devolvido_pela_ponte_que_nao_sobe_nao_vai_e_volta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-1911-O-SOM-DO-PC-VOLTA-QUANDO-O-CONTROLE-SAI: o nó que toca sem ponte não oscila."""
    mesa = _mesa(monkeypatch, padrao=nome_do_sink(P[0]), guardada=HDMI)
    mesa.lista(P[0])
    mesa.sub._pontes.clear()
    mesa.volta(2)
    assert mesa.servidor.padrao == HDMI
    mesa.lista(P[0], tocando=False)
    mesa.volta(4)
    assert mesa.servidor.escritas == [HDMI], "o som voltou ao nó que segue sem ponte"
    mesa.lista()
    mesa.volta()
    mesa.lista(P[0], tocando=False)
    mesa.volta()
    assert mesa.servidor.padrao == nome_do_sink(P[0]), "o controle saiu e voltou e o som não"
