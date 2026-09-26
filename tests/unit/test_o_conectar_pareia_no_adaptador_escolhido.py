"""O «Conectar» pareia no adaptador ABERTO, e em nenhum outro — O-RADIO-CONECTA-ONDE-ELA-MANDA-01.

Os relatos dela de 26/09/2026, com três DualSense e três adaptadores:

    *«controle conectado ainda cliquei na guia de conexão no botão
    correspondente a esquerda e ele ainda assim conectou no da direita. Não
    respeitaw nem a guia selecionada no radio e adaptadores e nem o botão
    correspondente ao Conectar.»* <!-- noqa-acento: citação literal dela -->

E a decisão dela, às 04h: *«No adaptador aberto (a Esquerda)»*.

MEDIDO no ``radio-diario.jsonl`` dela: os oito «Conectar» da madrugada abriram
a busca no ``hci0``, qualquer que fosse o adaptador aberto — o destino era o da
D8, e o chip do «Procurando» morava num painel que o próprio «Conectar» abria
com a busca já de pé noutro adaptador.

A RÉGUA É A DELA, a frase 1: *idempotente, universal, independente do número do
jogador, da posição do adaptador na lista, da quantidade de adaptadores e do
transporte*. Então cada caso roda na MATRIZ: o destino em cada uma das três
posições, a lista em três ordens, e dois arranjos de números de jogador. O
rádio é o ``radio_de_mentira`` (três adaptadores, com física), o dono do BlueZ é
o ``DonoVivo`` de verdade por cima dele, e o pedido atravessa o tratador REAL do
daemon (``_handle_radio_mover``) até a ``CentralDoRadio`` real.

MORDIDA: faça ``_destino_do_conectar`` ignorar o adaptador aberto (devolver o
``destino_da_central``) — a busca volta para a D8 e os casos em que o destino
não é o da D8 reprovam.

Faixa sintética da casa: ``aa:bb:cc``, octetos 4 e 5 zerados.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import central_do_radio as cr
from hefesto_dualsense4unix.integrations import diario_do_radio
from hefesto_dualsense4unix.integrations import gesto_de_pareamento as gp
from tests.unit import radio_de_mentira as rm
from tests.unit.radio_de_mentira import AZUL, QUARTO, SALA, VARANDA, VERDE, VERMELHO

PAGINA = "08-conexoes.html"
ADAPTADORES = (SALA, QUARTO, VARANDA)


def id_da_tela(endereco: str) -> str:
    """O id da tela: 12 hex em maiúsculas, a forma do ``_mac`` do pacote."""
    return endereco.replace(":", "").upper()


class PonteQueVaiAoDaemon:
    """O ``ponte.resultado`` com o TRATADOR REAL do daemon atrás — a validação de
    parâmetro e a tradução de «ocupado» são as dele, nunca mais frouxas."""

    def __init__(self, central: cr.CentralDoRadio) -> None:
        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

        class _Daemon(IpcHandlersMixin):
            pass

        self.eu = _Daemon()
        self.eu.daemon = SimpleNamespace(_central_do_radio=central)  # type: ignore[attr-defined]
        self.chamadas: list[tuple[str, dict[str, Any]]] = []

    def resultado(self, metodo: str, timeout: float | None = None, **params: Any) -> Any:
        assert metodo == "radio.mover", f"método que esta régua não esperava: {metodo}"
        self.chamadas.append((metodo, dict(params)))
        return asyncio.run(self.eu._handle_radio_mover(params))


class Bancada:
    """A tela (o pacote da 08), a central e o rádio de mentira, ligados como no produto."""

    def __init__(self, a08: Any, monkeypatch: pytest.MonkeyPatch, mundo: rm.RadioDeMentira,
                 relogio: rm.Relogio, *, ordem: tuple[str, ...] = ADAPTADORES,
                 jogadores: dict[str, int] | None = None) -> None:
        self.a08, self.mundo, self.relogio = a08, mundo, relogio
        self.jogadores = jogadores or {}
        self.dono = bd.DonoVivo(mundo)
        assert self.dono.ligar()
        self.central = cr.CentralDoRadio(
            dono=self.dono, onde_esta=mundo.onde_esta, movimento=mundo.hz,
            esquecer_na_ponte=mundo.esquecer_na_ponte, relogio=relogio,
            dormir=relogio.dormir, sysfs={"listar": lambda _p: [], "raiz": "/nao/existe"})
        self.ponte = PonteQueVaiAoDaemon(self.central)
        monkeypatch.setattr(a08, "_ler_o_bluez", lambda: (
            tuple(self.dono.adaptadores() or ()), tuple(self.dono.aparelhos() or ())))
        monkeypatch.setattr(a08, "_ordem_gravada", lambda: [id_da_tela(e) for e in ordem])

        def esquecer(lugar: str, aparelho: str) -> Any:
            return gp.esquecer_o_pareamento(
                a08._com_dois_pontos(lugar), a08._com_dois_pontos(aparelho), dono=self.dono,
                esquecer_na_ponte=mundo.esquecer_na_ponte, quem="tela")

        monkeypatch.setattr(a08, "_esquecer_o_pareamento", esquecer)

    def estado(self) -> dict[str, Any]:
        """O ``state_full`` que o daemon publicaria para esta mesa, agora."""
        controles = [
            {"uniq": rm.uniq(f.endereco), "transport": "bt", "connected": True,
             "adaptador": f.conectado_em, "hz_movimento": 150.0, "hz_voz": 0.0,
             "ponte_do_radio": "som", "audio": {"mic_mudo": True}}
            for f in self.mundo.fisicos.values() if f.conectado_em]
        return {"controllers": controles,
                "radio_central": self.central.publicar(controles)}

    def ctx(self) -> Any:
        from hefesto_dualsense4unix.interface.pacotes import Contexto

        estado = self.estado()
        mesa = [{"uniq": c["uniq"], "cor": "", "nome": "",
                 "jogador": self.jogadores.get(c["uniq"])} for c in estado["controllers"]]
        return Contexto(state=estado, conectados=list(estado["controllers"]), mesa=mesa)

    def tique(self) -> dict[str, Any]:
        """Uma volta da tela, com o BlueZ lido de novo (a leitura vale 3 s)."""
        self.a08._esquecer("bluez")
        return dict(self.a08.campos_do_radio(self.ctx()))

    def cena(self) -> dict[str, Any]:
        self.tique()
        return dict(self.a08._CENA_NA_TELA)

    def gesto(self, nome: str, **clique: Any) -> Any:
        from hefesto_dualsense4unix.interface.pacotes import GESTOS

        return GESTOS[(PAGINA, nome)](self.ctx(), clique, self.ponte)

    def esperar_a_central(self, teto: float = 15.0) -> None:
        """O «Conectar» segue num fio da central; a régua espera ele acabar."""
        fim = time.monotonic() + teto
        while time.monotonic() < fim:
            movimentos = self.central.movimentos()
            if movimentos and not any(m.em_curso for m in movimentos):
                return
            time.sleep(0.01)
        raise AssertionError(f"a central não terminou: {self.central.movimentos()}")

    def fechar(self) -> None:
        self.central.fechar(espera=5.0)
        self.dono.fechar()


def preparar_o_diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A trava e o diário numa pasta de teste — nunca os dela, em ``/run``."""
    monkeypatch.setenv(diario_do_radio.ENV_TRAVA, str(tmp_path / "radio.lock"))
    caminho = tmp_path / "radio-diario.jsonl"
    monkeypatch.setenv(diario_do_radio.ENV_DIARIO, str(caminho))
    return caminho


def preparar_a_tela(monkeypatch: pytest.MonkeyPatch) -> Any:
    """O pacote da 08 lendo na hora, sem nada da tela de antes nem do disco dela."""
    from hefesto_dualsense4unix.integrations.mesa_de_radio import Mesa
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

    monkeypatch.setattr(a08_conexoes, "LER_NA_HORA", True)
    monkeypatch.setattr(a08_conexoes, "_FUNDO", {})
    monkeypatch.setattr(a08_conexoes, "_ABERTO", {})
    monkeypatch.setattr(a08_conexoes, "_CENA_NA_TELA", {})
    monkeypatch.setattr(a08_conexoes, "_DISPENSADOS", set())
    monkeypatch.setattr(a08_conexoes, "_MEIAS_CHAVES_PEDIDAS", set())
    monkeypatch.setattr(a08_conexoes, "_mesa_do_radio", lambda recarregar=False: Mesa())
    monkeypatch.setattr(a08_conexoes, "_ler_o_historico", lambda: {})
    monkeypatch.setattr(a08_conexoes, "_ler_a_maquina", lambda: (MaquinaConfig(), {}))
    return a08_conexoes



@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return preparar_o_diario(tmp_path, monkeypatch)


@pytest.fixture()
def a08(monkeypatch: pytest.MonkeyPatch) -> Any:
    return preparar_a_tela(monkeypatch)


def mundo_da_madrugada() -> rm.RadioDeMentira:
    """Dois controles no ar na sala (com som), e o verde novo, desligado, na mão dela."""
    mundo = rm.RadioDeMentira()
    mundo.pareado(SALA, VERMELHO)
    mundo.pareado(SALA, AZUL)
    mundo.fisicos[VERDE] = rm.Fisico(VERDE, rm.CLASSE_DE_CONTROLE)
    return mundo


def ela_segura_ps_create(mundo: rm.RadioDeMentira, relogio: rm.Relogio, aparelho: str) -> None:
    """Dois segundos depois de a janela abrir, ela segura PS + Create."""
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(aparelho))


def onde_buscou(mundo: rm.RadioDeMentira) -> list[str]:
    return [c for c, _a in mundo.metodos("StartDiscovery")]


def onde_pareou(mundo: rm.RadioDeMentira) -> list[str]:
    return [c.rsplit("/", 1)[0] for c, _a in mundo.metodos("Pair")]


ORDENS = {
    "sala-quarto-varanda": (SALA, QUARTO, VARANDA),
    "varanda-sala-quarto": (VARANDA, SALA, QUARTO),
    "quarto-varanda-sala": (QUARTO, VARANDA, SALA),
}
JOGADORES = {
    "vermelho-p1": {rm.uniq(VERMELHO): 1, rm.uniq(AZUL): 2},
    "vermelho-p4": {rm.uniq(VERMELHO): 4, rm.uniq(AZUL): 3},
}


@pytest.mark.parametrize("jogadores", sorted(JOGADORES))
@pytest.mark.parametrize("ordem", sorted(ORDENS))
@pytest.mark.parametrize("destino", ADAPTADORES)
def test_abrir_o_adaptador_e_conectar_pareia_nele(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
    destino: str, ordem: str, jogadores: str,
) -> None:
    """E1 da sprint: abrir um adaptador e clicar «Conectar» — a busca, o ``Pair``
    e a chegada saem DAQUELE adaptador, em qualquer posição da lista e com
    qualquer número de jogador."""
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio, ordem=ORDENS[ordem],
                      jogadores=JOGADORES[jogadores])
    try:
        cena = bancada.cena()
        assert [lug["id"] for lug in cena["lugares"]] == [id_da_tela(e) for e in ORDENS[ordem]]
        if cena.get("aberto") != id_da_tela(destino):
            bancada.gesto("abrir-adaptador", alvo=id_da_tela(destino))
        assert bancada.cena()["destino_do_conectar"] == id_da_tela(destino)

        ela_segura_ps_create(mundo, relogio, VERDE)
        assert bancada.gesto("conectar-aparelho") == {"armou": True}
        bancada.esperar_a_central()

        assert bancada.ponte.chamadas == [("radio.mover", {"destino": id_da_tela(destino)})]
        assert onde_buscou(mundo) == [rm.HCIS[destino]], "a busca saiu de outro adaptador"
        assert onde_pareou(mundo) == [rm.HCIS[destino]], "o Pair saiu de outro adaptador"
        (feito,) = [m for m in bancada.central.movimentos() if m.aparelho == VERDE]
        assert (feito.estado, feito.destino) == (cr.CHEGOU, destino)
        assert mundo.onde_esta(rm.uniq(VERDE)) == destino
    finally:
        bancada.fechar()


def test_o_chip_do_procurando_abre_o_mesmo_adaptador(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O chip e a lista dizem a mesma coisa: escolher a varanda no chip ABRE a
    caixa da varanda, e é nela que a busca acontece."""
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        bancada.cena()
        bancada.gesto("escolher-adaptador", alvo=id_da_tela(VARANDA))
        cena = bancada.cena()
        assert cena["aberto"] == id_da_tela(VARANDA)
        assert cena["destino_do_conectar"] == id_da_tela(VARANDA)
        sala = bancada.tique()["radio-sala"]
        assert f'class="lugar aberto" data-id="{id_da_tela(VARANDA)}"' in sala

        ela_segura_ps_create(mundo, relogio, VERDE)
        bancada.gesto("conectar-aparelho")
        bancada.esperar_a_central()
        assert onde_buscou(mundo) == [rm.HCIS[VARANDA]]
    finally:
        bancada.fechar()


def test_sem_nenhum_aberto_vale_a_escolha_da_central(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Com todas as caixas fechadas por ela, o destino é o da D8 — e a caixa
    dele fica aberta depois, onde ela vê o «Segure PS + Create» e a chegada."""
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        cena = bancada.cena()
        if cena.get("aberto"):
            bancada.gesto("abrir-adaptador", alvo=cena["aberto"])
        cena = bancada.cena()
        assert cena["aberto"] is None
        d8 = cena["destino_da_central"]
        assert cena["destino_do_conectar"] == d8

        ela_segura_ps_create(mundo, relogio, VERDE)
        bancada.gesto("conectar-aparelho")
        bancada.esperar_a_central()
        (hci,) = onde_buscou(mundo)
        assert id_da_tela(next(e for e, c in rm.HCIS.items() if c == hci)) == d8
        assert bancada.cena()["aberto"] == d8, "a caixa do destino não ficou aberta"
    finally:
        bancada.fechar()


def test_com_a_janela_aberta_o_chip_de_outro_adaptador_treme(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A janela não muda de adaptador no meio: com a busca de pé no quarto, o chip
    da varanda recusa (o botão treme), e o destino continua o quarto."""
    import time as relogio_de_parede

    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        esperando = {"movimentos": [{"aparelho": "", "destino": QUARTO, "estado": "esperando",
                                     "passo": "gesto", "quando": relogio_de_parede.time()}]}
        monkeypatch.setattr(bancada, "estado", lambda: {"controllers": [],
                                                        "radio_central": esperando})
        cena = bancada.cena()
        assert cena["ocupado"] and cena["destino_do_conectar"] == id_da_tela(QUARTO)
        with pytest.raises(RuntimeError):
            bancada.gesto("escolher-adaptador", alvo=id_da_tela(VARANDA))
        assert a08._CENA_NA_TELA["destino_do_conectar"] == id_da_tela(QUARTO)
    finally:
        bancada.fechar()

