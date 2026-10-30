"""O «Conectar» pareia no adaptador ABERTO, e em nenhum outro —
O-RADIO-CONECTA-ONDE-O-USUARIO-MANDA-01.

Os relatos de 26/09/2026, com três DualSense e três adaptadores: com um controle conectado, o
clique na guia do adaptador da Esquerda e no Conectar correspondente ainda conectava no da
Direita; nem a guia escolhida nem o botão Conectar eram respeitados.

E a decisão de produto, às 04h: *«No adaptador aberto (a Esquerda)»*.

MEDIDO no ``radio-diario.jsonl``: os oito «Conectar» da madrugada abriram
a busca no ``hci0``, qualquer que fosse o adaptador aberto — o destino era o da
D8, e o chip do «Procurando» morava num painel que o próprio «Conectar» abria
com a busca já de pé noutro adaptador.

A RÉGUA É A DO USUÁRIO, a frase 1: *idempotente, universal, independente do número do
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
import threading
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
    """O ``ponte.resultado`` com o TRATADOR REAL do daemon atrás — a validação de"""

    def __init__(self, central: cr.CentralDoRadio) -> None:
        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

        class _Daemon(IpcHandlersMixin):
            pass

        self.eu = _Daemon()
        self.eu.daemon = SimpleNamespace(_central_do_radio=central)  # type: ignore[attr-defined]
        self.chamadas: list[tuple[str, dict[str, Any]]] = []

    def resultado(self, metodo: str, timeout: float | None = None, **params: Any) -> Any:
        tratadores = {"radio.mover": self.eu._handle_radio_mover,
                      "radio.busca.set": self.eu._handle_radio_busca_set}
        assert metodo in tratadores, f"método que esta régua não esperava: {metodo}"
        self.chamadas.append((metodo, dict(params)))
        return asyncio.run(tratadores[metodo](params))


class Ensaio:
    """A tela (o pacote da 08), a central e o rádio de mentira, ligados como no produto."""

    def __init__(self, a08: Any, monkeypatch: pytest.MonkeyPatch, mundo: rm.RadioDeMentira,
                 relogio: rm.Relogio, *, ordem: tuple[str, ...] = ADAPTADORES,
                 jogadores: dict[str, int] | None = None) -> None:
        from hefesto_dualsense4unix.interface.pacotes import em_fundo
        self.a08, self.mundo, self.relogio = a08, mundo, relogio
        self.jogadores = jogadores or {}
        self.dono = bd.DonoVivo(mundo)
        assert self.dono.ligar()
        self.central = cr.CentralDoRadio(
            dono=self.dono, onde_esta=mundo.onde_esta, movimento=mundo.hz,
            esquecer_na_ponte=mundo.esquecer_na_ponte, relogio=relogio,
            dormir=relogio.dormir, sysfs={"listar": lambda _p: [], "raiz": "/nao/existe"})
        self.ponte = PonteQueVaiAoDaemon(self.central)
        monkeypatch.setattr(em_fundo, "ler_o_bluez", lambda: (
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
        from hefesto_dualsense4unix.interface.pacotes import em_fundo
        em_fundo.esquecer("bluez")
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
            if movimentos and not any(m.em_curso for m in movimentos) and not self._fios_vivos():
                return
            time.sleep(0.01)
        raise AssertionError(f"a central não terminou: {self.central.movimentos()} "
                             f"(fios vivos: {self._fios_vivos()})")

    def _fios_vivos(self) -> list[str]:
        from hefesto_dualsense4unix.integrations import central_do_radio as cr

        with self.central._tranca:
            fios = list(self.central._fios.items())
        return [chave for chave, fio in fios
                if chave != cr._FIO_DA_FAXINA and fio.is_alive()]

    def fechar(self) -> None:
        self.central.fechar(espera=5.0)
        self.dono.fechar()


def preparar_o_diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A trava e o diário numa pasta de teste — nunca os reais, em ``/run``."""
    monkeypatch.setenv(diario_do_radio.ENV_TRAVA, str(tmp_path / "radio.lock"))
    caminho = tmp_path / "radio-diario.jsonl"
    monkeypatch.setenv(diario_do_radio.ENV_DIARIO, str(caminho))
    return caminho


def preparar_a_tela(monkeypatch: pytest.MonkeyPatch) -> Any:
    """O pacote da 08 lendo na hora, sem nada da tela de antes nem do disco do usuário."""
    from hefesto_dualsense4unix.interface.pacotes import em_fundo
    from hefesto_dualsense4unix.integrations.mesa_de_radio import Mesa
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

    monkeypatch.setattr(em_fundo, "LER_NA_HORA", True)
    monkeypatch.setattr(em_fundo, "_FUNDO", {})
    monkeypatch.setattr(a08_conexoes, "_ABERTO", {})
    monkeypatch.setattr(a08_conexoes, "_CENA_NA_TELA", {})
    monkeypatch.setattr(a08_conexoes, "_DISPENSADOS", set())
    monkeypatch.setattr(a08_conexoes, "_SALA_NA_TELA", {})
    monkeypatch.setattr(a08_conexoes, "_CHEGADAS", {})
    monkeypatch.setattr(a08_conexoes, "_NIVEL_NA_TELA", {})
    monkeypatch.setattr(a08_conexoes, "_mesa_do_radio", lambda recarregar=False: Mesa())
    monkeypatch.setattr(a08_conexoes, "_ler_a_maquina", lambda: (MaquinaConfig(), {}))
    return a08_conexoes


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return preparar_o_diario(tmp_path, monkeypatch)


@pytest.fixture()
def a08(monkeypatch: pytest.MonkeyPatch) -> Any:
    return preparar_a_tela(monkeypatch)


def mundo_da_madrugada() -> rm.RadioDeMentira:
    """Dois controles no ar na sala (com som), e o verde novo, desligado, na mão do usuário."""
    mundo = rm.RadioDeMentira()
    mundo.pareado(SALA, VERMELHO)
    mundo.pareado(SALA, AZUL)
    mundo.fisicos[VERDE] = rm.Fisico(VERDE, rm.CLASSE_DE_CONTROLE)
    return mundo


def o_usuario_segura_ps_create(
    mundo: rm.RadioDeMentira, relogio: rm.Relogio, aparelho: str,
) -> None:
    """Dois segundos depois de a janela abrir, quem usa segura PS + Create."""
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(aparelho))


class BuscaDePe:
    """Segura o fio da central DENTRO da janela, esperando o gesto do usuário."""

    def __init__(self, relogio: rm.Relogio) -> None:
        self.portao = threading.Event()
        self.dentro = threading.Event()
        relogio.durante = self._segurar

    def _segurar(self) -> None:
        if self.portao.is_set() or threading.current_thread().name != "hefesto-central-mover":
            return
        self.dentro.set()
        self.portao.wait(30.0)

    def soltar(self) -> None:
        self.portao.set()


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
    """E1 da sprint: abrir um adaptador e clicar «Conectar» — a busca, o ``Pair``"""
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    ensaio = Ensaio(a08, monkeypatch, mundo, relogio, ordem=ORDENS[ordem],
                      jogadores=JOGADORES[jogadores])
    try:
        cena = ensaio.cena()
        assert [lug["id"] for lug in cena["lugares"]] == [id_da_tela(e) for e in ORDENS[ordem]]
        if cena.get("aberto") != id_da_tela(destino):
            ensaio.gesto("abrir-adaptador", alvo=id_da_tela(destino))
        assert ensaio.cena()["destino_do_conectar"] == id_da_tela(destino)

        rm.o_usuario_pareia(relogio, mundo, ensaio.central, VERDE)
        assert ensaio.gesto("radio-procurar") == {"armou": True}
        ensaio.esperar_a_central()

        assert ensaio.ponte.chamadas == [
            ("radio.busca.set", {"ligada": True, "destino": id_da_tela(destino)})]
        assert onde_buscou(mundo) == [rm.HCIS[destino]], "a busca saiu de outro adaptador"
        assert onde_pareou(mundo) == [rm.HCIS[destino]], "o Pair saiu de outro adaptador"
        (feito,) = [m for m in ensaio.central.movimentos() if m.aparelho == VERDE]
        assert (feito.estado, feito.destino) == (cr.CHEGOU, destino)
        assert mundo.onde_esta(rm.uniq(VERDE)) == destino
    finally:
        ensaio.fechar()


def test_o_chip_do_procurando_abre_o_mesmo_adaptador(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O chip e a lista dizem a mesma coisa: escolher a varanda no chip ABRE a"""
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    ensaio = Ensaio(a08, monkeypatch, mundo, relogio)
    try:
        ensaio.cena()
        ensaio.gesto("escolher-adaptador", alvo=id_da_tela(VARANDA))
        cena = ensaio.cena()
        assert cena["aberto"] == id_da_tela(VARANDA)
        assert cena["destino_do_conectar"] == id_da_tela(VARANDA)
        sala = ensaio.tique()["radio-sala"]
        assert f'class="lugar aberto" data-id="{id_da_tela(VARANDA)}"' in sala

        o_usuario_segura_ps_create(mundo, relogio, VERDE)
        ensaio.gesto("radio-procurar")
        ensaio.esperar_a_central()
        assert onde_buscou(mundo) == [rm.HCIS[VARANDA]]
    finally:
        ensaio.fechar()


def test_sem_nenhum_aberto_vale_a_escolha_da_central(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Com todas as caixas fechadas à mão, o destino é o da D8 — e a caixa"""
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    ensaio = Ensaio(a08, monkeypatch, mundo, relogio)
    try:
        cena = ensaio.cena()
        if cena.get("aberto"):
            ensaio.gesto("abrir-adaptador", alvo=cena["aberto"])
        cena = ensaio.cena()
        assert cena["aberto"] is None
        d8 = cena["destino_da_central"]
        assert cena["destino_do_conectar"] == d8

        o_usuario_segura_ps_create(mundo, relogio, VERDE)
        ensaio.gesto("radio-procurar")
        ensaio.esperar_a_central()
        (hci,) = onde_buscou(mundo)
        assert id_da_tela(next(e for e, c in rm.HCIS.items() if c == hci)) == d8
        assert ensaio.cena()["aberto"] == d8, "a caixa do destino não ficou aberta"
    finally:
        ensaio.fechar()


def test_com_a_janela_aberta_o_chip_de_outro_adaptador_leva_a_busca(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Com a busca de pé no quarto, o chip da varanda PEDE ao rádio a busca"""
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    ensaio = Ensaio(a08, monkeypatch, mundo, relogio)
    busca = BuscaDePe(relogio)
    try:
        ensaio.cena()
        ensaio.gesto("escolher-adaptador", alvo=id_da_tela(QUARTO))
        ensaio.cena()
        ensaio.gesto("radio-procurar")
        assert busca.dentro.wait(5.0), "a central não abriu a janela"
        cena = ensaio.cena()
        assert cena["ocupado"] and cena["destino_do_conectar"] == id_da_tela(QUARTO)
        assert ensaio.gesto("escolher-adaptador", alvo=id_da_tela(VARANDA)) == {"armou": True}
        assert ensaio.ponte.chamadas[-1] == ("radio.mover", {"destino": id_da_tela(VARANDA)})
        assert a08._CENA_NA_TELA["destino_do_conectar"] == id_da_tela(VARANDA)

        rm.o_usuario_pareia(relogio, mundo, ensaio.central, VERDE)
        busca.soltar()
        ensaio.esperar_a_central()
        assert onde_buscou(mundo) == [rm.HCIS[QUARTO], rm.HCIS[VARANDA]]
        assert onde_pareou(mundo) == [rm.HCIS[VARANDA]]
        assert mundo.onde_esta(rm.uniq(VERDE)) == VARANDA
        assert ensaio.cena()["aberto"] == id_da_tela(VARANDA)
    finally:
        busca.soltar()
        ensaio.fechar()
