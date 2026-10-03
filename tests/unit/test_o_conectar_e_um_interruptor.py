"""O «Conectar» é um interruptor — O-CONECTAR-E-UM-INTERRUPTOR-01."""

from __future__ import annotations

import asyncio
import re
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import central_do_radio as cr
from hefesto_dualsense4unix.integrations import gesto_de_pareamento as gp
from tests.unit import radio_de_mentira as rm
from tests.unit.radio_de_mentira import AZUL, QUARTO, ROXO, SALA, VARANDA, VERDE, VERMELHO
from tests.unit.test_o_conectar_pareia_no_adaptador_escolhido import (
    ADAPTADORES,
    Bancada,
    id_da_tela,
    preparar_a_tela,
    preparar_o_diario,
)

RAIZ = Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
FIO_DA_CENTRAL = "hefesto-central-mover"


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return preparar_o_diario(tmp_path, monkeypatch)


@pytest.fixture()
def a08(monkeypatch: pytest.MonkeyPatch) -> Any:
    return preparar_a_tela(monkeypatch)


class RadioComHora(rm.RadioDeMentira):
    """O rádio de mentira que anota a hora DO RELÓGIO DA CENTRAL em toda chamada"""

    def __init__(self, relogio: rm.Relogio, **extra: Any) -> None:
        super().__init__(**extra)
        self.relogio = relogio
        self.com_hora: list[tuple[str, str, Any, float]] = []

    def _anotar(self, nome: str, caminho: str, valor: Any) -> None:
        adaptador = next((e for e, h in rm.HCIS.items()
                          if caminho == h or caminho.startswith(h + "/")), "")
        self.com_hora.append((nome, adaptador, valor, self.relogio()))

    def chamar(self, destino: str, caminho: str, interface: str, metodo: str,
               assinatura: str, argumentos: Any, *, espera: float) -> bd.Escrita:
        self._anotar(metodo, caminho, tuple(argumentos))
        return super().chamar(destino, caminho, interface, metodo, assinatura, argumentos,
                              espera=espera)

    def escrever(self, caminho: str, interface: str, nome: str, assinatura: str, valor: Any,
                 *, espera: float) -> bd.Escrita:
        self._anotar(nome, caminho, valor)
        return super().escrever(caminho, interface, nome, assinatura, valor, espera=espera)

    def horas(self, nome: str, adaptador: str, valor: Any = None) -> list[float]:
        return [h for n, a, v, h in self.com_hora
                if n == nome and a == adaptador and (valor is None or v == valor)]


class Parada:
    """Segura o fio da central quando o relógio de mentira chega a um instante."""

    def __init__(self, relogio: rm.Relogio) -> None:
        self.relogio = relogio
        self.ate: float | None = None
        self.parou = threading.Event()
        self._siga = threading.Event()
        relogio.durante = self._durante

    def _durante(self) -> None:
        if threading.current_thread().name != FIO_DA_CENTRAL:
            return
        ate = self.ate
        if ate is None or self.relogio.agora < ate:
            return
        self.ate = None
        self.parou.set()
        self._siga.wait(30.0)
        self._siga.clear()

    def segurar_em(self, instante: float) -> None:
        self.parou.clear()
        self.ate = instante

    def seguir(self) -> None:
        self._siga.set()

    def soltar(self) -> None:
        self.ate = None
        self._siga.set()


def mundo_da_madrugada(relogio: rm.Relogio) -> RadioComHora:
    """Dois controles no ar na sala (com som), e o verde novo, desligado, na mão dela."""
    mundo = RadioComHora(relogio)
    mundo.pareado(SALA, VERMELHO)
    mundo.pareado(SALA, AZUL)
    mundo.fisicos[VERDE] = rm.Fisico(VERDE, rm.CLASSE_DE_CONTROLE)
    return mundo


def montar(a08: Any, monkeypatch: pytest.MonkeyPatch, mundo: RadioComHora | None = None,
           **extra: Any) -> tuple[Bancada, Parada]:
    relogio = mundo.relogio if mundo is not None else rm.Relogio()
    mundo = mundo if mundo is not None else mundo_da_madrugada(relogio)
    bancada = Bancada(a08, monkeypatch, mundo, relogio, **extra)
    return bancada, Parada(relogio)


def ligar(bancada: Bancada, parada: Parada, onde: str) -> dict[str, Any]:
    """O «Procurar» ligado em ``onde`` pelo tratador real, com o fio da central"""
    parada.segurar_em(0.0)
    resposta = bancada.ponte.resultado("radio.busca.set", ligada=True, destino=id_da_tela(onde))
    assert isinstance(resposta, dict)
    assert parada.parou.wait(5.0), "a central não abriu a janela"
    return resposta


def desligar(bancada: Bancada, parada: Parada) -> dict[str, Any]:
    """O «Procurar» desligado pelo tratador real; o fio solto logo depois, para"""
    soltura = threading.Timer(0.3, parada.soltar)
    soltura.start()
    try:
        resposta = bancada.ponte.resultado("radio.busca.set", ligada=False)
    finally:
        soltura.cancel()
        parada.soltar()
    assert isinstance(resposta, dict)
    return resposta


def tique(a08: Any, ctx: Any) -> dict[str, Any]:
    """Uma volta da tela com um ``Contexto`` dado (o BlueZ relido)."""
    a08._esquecer("bluez")
    return dict(a08.campos_do_radio(ctx))


def aos(ctx: Any, segundos: float) -> Any:
    """O que a central publica ``segundos`` depois do começo: o ``quando`` dos"""
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    estado = dict(ctx.state)
    central = dict(estado["radio_central"])
    central["movimentos"] = [dict(m, quando=float(m["quando"]) - segundos)
                             for m in central.get("movimentos") or ()]
    if isinstance(central.get("busca"), dict):
        busca = central["busca"]
        central["busca"] = dict(busca, desde=busca["desde"] - segundos,
                                ate=busca["ate"] - segundos)
    estado["radio_central"] = central
    return Contexto(state=estado, conectados=ctx.conectados, mesa=ctx.mesa)


def nao_conectou(cena: dict[str, Any]) -> list[tuple[str, str]]:
    return [(str(a["lugar"]), str(a.get("aparelho") or "")) for a in cena["aparelhos"]
            if a.get("nao_conectou")]


def posicao(onde: str) -> int:
    return ADAPTADORES.index(onde)


@pytest.mark.parametrize("aberto", ADAPTADORES)
def test_abrir_o_painel_nao_liga_o_radio(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, aberto: str,
) -> None:
    """O «+ Conectar» só abre o painel: nenhum pedido ao daemon, nenhum"""
    bancada, _parada = montar(a08, monkeypatch)
    try:
        a08._ABERTO["lugar"] = id_da_tela(aberto)
        bancada.cena()
        assert bancada.gesto("conectar-aparelho") == {"armou": True}
        assert bancada.ponte.chamadas == [], "o «+ Conectar» pediu ao rádio"
        assert bancada.mundo.metodos("StartDiscovery") == []
        assert bancada.central.movimentos() == ()
        campos = bancada.tique()
        assert campos["radio-procurando"] == a08.PROCURAR_DESLIGADO
        assert 'data-painel="conectar" data-alvo="" data-titulo="Conectar">' in (
            campos["radio-moldes"])
    finally:
        bancada.fechar()

    mockup = (RAIZ / "mockup" / "08-conexoes.html").read_text(encoding="utf-8")
    cabecalho = re.search(r'(<button class="cadeado[^>]*data-gesto="radio-procurar"[^>]*>.*?'
                          r'</button>)\s*(<button[^>]*id="rd-b-conectar"[^>]*>)', mockup, re.S)
    assert cabecalho, "o «Procurar» não está à esquerda do «+ Conectar»"
    assert "radio-ocupado" not in cabecalho.group(2), "o «+ Conectar» ainda apaga com a busca"


@pytest.mark.parametrize("onde", ADAPTADORES)
def test_desligar_para_o_radio_em_ate_um_segundo(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, onde: str,
) -> None:
    """Ligada e desligada pelo ``radio.busca.set``: o ``StopDiscovery`` e o"""
    bancada, parada = montar(a08, monkeypatch)
    mundo = bancada.mundo
    try:
        ligada = ligar(bancada, parada, onde)
        assert ligada["status"] == "ok", ligada
        assert id_da_tela(ligada["busca"]["adaptador"]) == id_da_tela(onde), ligada
        assert mundo.propriedade_do_adaptador(onde, "Discovering") is True
        assert mundo.propriedade_do_adaptador(onde, "Pairable") is True
        pedido_em = bancada.relogio()

        resposta = desligar(bancada, parada)
        bancada.esperar_a_central()

        assert resposta == {"status": "ok", "busca": None}, resposta
        (parou,) = mundo.horas("StopDiscovery", onde)
        assert parou - pedido_em <= 1.0, f"o StopDiscovery veio {parou - pedido_em:.1f} s depois"
        fechou = mundo.horas("Pairable", onde, False)
        assert fechou and fechou[-1] - pedido_em <= 1.0, fechou
        assert mundo.propriedade_do_adaptador(onde, "Pairable") is False
        assert bancada.central.publicar()["busca"] is None
        (fim,) = bancada.central.movimentos()
        assert (fim.estado, fim.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_DESLIGADA), fim
        assert nao_conectou(bancada.cena()) == [], "a busca desligada virou «Não Conectou»"
    finally:
        parada.soltar()
        bancada.fechar()


def test_desligar_sem_busca_nao_toca_no_radio(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pedir o estado que já vale responde ``ok`` sem tocar no rádio."""
    bancada, _parada = montar(a08, monkeypatch)
    try:
        assert bancada.ponte.resultado("radio.busca.set", ligada=False) == {
            "status": "ok", "busca": None}
        assert [m for _c, _i, m, _a in bancada.mundo.chamadas
                if m in ("StartDiscovery", "StopDiscovery")] == []
        assert bancada.central.movimentos() == ()
    finally:
        bancada.fechar()


@pytest.mark.parametrize("onde", ADAPTADORES)
def test_o_interruptor_e_a_pilula_leem_a_busca_da_central(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, onde: str,
) -> None:
    """Com a busca ligada num dos três adaptadores, o interruptor diz LIGADO e"""
    bancada, parada = montar(a08, monkeypatch)
    try:
        ligar(bancada, parada, onde)
        campos = bancada.tique()
        assert campos["radio-procurando"] == a08.PROCURAR_LIGADO
        esperado = ["", "", ""]
        esperado[posicao(onde)] = "sim"
        assert campos["radio-conectando"] == esperado
        assert 'data-titulo="Procurando" data-pulso="1"' in campos["radio-moldes"]

        desligar(bancada, parada)
        bancada.esperar_a_central()
        ctx = bancada.ctx()
        sobra = cr.Movimento(cr.CONECTANDO, onde, cr.ESPERANDO, cr.PASSO_GESTO,
                             quando=time.time() - 5.0).publicar()
        ctx.state["radio_central"]["movimentos"].append(sobra)
        assert ctx.state["radio_central"]["busca"] is None
        for n in range(30):
            campos = tique(a08, ctx)
            assert campos["radio-procurando"] == a08.PROCURAR_DESLIGADO, f"tique {n}"
            assert campos["radio-conectando"] == ["", "", ""], f"tique {n}"
    finally:
        parada.soltar()
        bancada.fechar()


@pytest.mark.parametrize("onde", ADAPTADORES)
def test_o_teto_apaga_a_busca_sozinho_aos_cento_e_vinte_segundos(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, onde: str,
) -> None:
    """Aos 90 s a janela da busca ainda está aberta, o interruptor aceso, a"""
    bancada, parada = montar(a08, monkeypatch)
    mundo = bancada.mundo
    try:
        ligar(bancada, parada, onde)
        (abriu,) = mundo.horas("StartDiscovery", onde)
        parada.segurar_em(abriu + 90.0)
        parada.seguir()
        assert parada.parou.wait(10.0), "a busca acabou antes dos 90 s"
        assert mundo.propriedade_do_adaptador(onde, "Discovering") is True
        assert mundo.horas("StopDiscovery", onde) == []
        assert bancada.central.publicar()["busca"] is not None
        ctx = aos(bancada.ctx(), 90.0)
        campos = tique(a08, ctx)
        cena = dict(a08._CENA_NA_TELA)
        assert campos["radio-procurando"] == a08.PROCURAR_LIGADO
        assert cena["ocupado"] is True, "a tela soltou a busca pela idade"
        assert nao_conectou(cena) == [], "a busca de 90 s virou «Não Conectou»"

        parada.soltar()
        bancada.esperar_a_central()
        (parou,) = mundo.horas("StopDiscovery", onde)
        assert gp.SEGUNDOS_MAX <= parou - abriu <= gp.SEGUNDOS_MAX + 1.0, parou - abriu
        assert bancada.central.publicar()["busca"] is None
        campos = bancada.tique()
        assert campos["radio-procurando"] == a08.PROCURAR_DESLIGADO
        assert nao_conectou(dict(a08._CENA_NA_TELA)) == [], "o teto virou «Não Conectou»"
    finally:
        parada.soltar()
        bancada.fechar()


def test_o_mover_segue_com_os_trinta_segundos_dele(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O teto é só da busca do «Procurar»: o «Mover» do vermelho para o quarto,"""
    bancada, parada = montar(a08, monkeypatch)
    mundo = bancada.mundo
    try:
        assert bancada.central.comecar_a_mover(VERMELHO, QUARTO).estado == cr.ESPERANDO
        bancada.esperar_a_central()
        (abriu,) = mundo.horas("StartDiscovery", QUARTO)
        (parou,) = mundo.horas("StopDiscovery", QUARTO)
        assert gp.SEGUNDOS_DA_JANELA <= parou - abriu <= gp.SEGUNDOS_DA_JANELA + 1.0, (
            parou - abriu)
        (fim,) = bancada.central.movimentos()
        assert (fim.estado, fim.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_SEM_GESTO), fim
        assert nao_conectou(bancada.cena()) == [(id_da_tela(QUARTO), id_da_tela(VERMELHO))]
    finally:
        parada.soltar()
        bancada.fechar()


def test_o_parear_que_nao_chega_faz_a_linha(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """«Não Conectou» fica para o que ela mandou e não chegou: com a busca"""
    bancada, _parada = montar(a08, monkeypatch)
    mundo = bancada.mundo
    try:
        mundo.pair_falha = True
        rm.ela_pareia(bancada.relogio, mundo, bancada.central, VERDE)
        resposta = bancada.ponte.resultado("radio.busca.set", ligada=True,
                                           destino=id_da_tela(QUARTO))
        assert resposta["status"] == "ok", resposta
        bancada.esperar_a_central()
        (fim,) = bancada.central.movimentos()
        assert (fim.aparelho, fim.estado, fim.motivo) == (
            VERDE, cr.NAO_CHEGOU, cr.MOTIVO_NAO_PAREOU), fim
        assert nao_conectou(bancada.cena()) == [(id_da_tela(QUARTO), id_da_tela(VERDE))]
    finally:
        bancada.fechar()


def test_a_busca_do_hefesto_nao_e_outro_programa(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O ``Discovering`` do adaptador da busca não acende a marca «varrendo» e"""
    bancada, parada = montar(a08, monkeypatch)
    mundo = bancada.mundo
    try:
        cena = bancada.cena()
        sem_busca = str(cena["destino_da_central"])
        assert id_da_tela(bancada.central.escolher_destino() or "") == sem_busca
        onde = next(e for e in ADAPTADORES if id_da_tela(e) == sem_busca)
        outro = next(e for e in (QUARTO, VARANDA) if e != onde)
        assert onde != SALA, "a D8 desta mesa escolheu o adaptador cheio"

        a08._ABERTO["lugar"] = sem_busca
        ligar(bancada, parada, onde)
        campos = bancada.tique()
        cena = dict(a08._CENA_NA_TELA)
        assert campos["radio-varrendo"] == ["", "", ""], "a busca dela virou «outro programa»"
        assert cena["destino_da_central"] == sem_busca, "a D8 da tela fugiu da busca dela"
        bancada.relogio.agora += cr.VALIDADE_DOS_ADAPTADORES_S
        assert id_da_tela(bancada.central.escolher_destino() or "") == sem_busca, (
            "a D8 da central fugiu da busca dela")

        mundo._mudar(rm.HCIS[outro], bd.ADAPTADOR, "Discovering", True)
        esperado = ["", "", ""]
        esperado[posicao(outro)] = "sim"
        assert bancada.tique()["radio-varrendo"] == esperado
        desligar(bancada, parada)
        bancada.esperar_a_central()
        assert bancada.tique()["radio-varrendo"] == esperado
    finally:
        parada.soltar()
        bancada.fechar()


def test_o_mesmo_clique_entregue_duas_vezes_deixa_a_busca_como_pedida(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tela diz DESLIGADO e o clique chega duas vezes antes do tique (a"""
    bancada, parada = montar(a08, monkeypatch)
    try:
        a08._ABERTO["lugar"] = id_da_tela(QUARTO)
        bancada.cena()
        assert bancada.gesto("radio-procurar", evento="change") is None
        assert bancada.ponte.chamadas == []

        parada.segurar_em(0.0)
        assert bancada.gesto("radio-procurar") == {"armou": True}
        assert parada.parou.wait(5.0)
        segunda: Any
        try:
            segunda = bancada.gesto("radio-procurar")
        except RuntimeError as erro:
            segunda = erro
        pedido = ("radio.busca.set", {"ligada": True, "destino": id_da_tela(QUARTO)})
        assert bancada.ponte.chamadas == [pedido, pedido], "a segunda entrega não repetiu o pedido"
        assert segunda == {"armou": True}, segunda
        assert len(bancada.mundo.horas("StartDiscovery", QUARTO)) == 1
        busca = bancada.central.publicar()["busca"]
        assert busca is not None and id_da_tela(busca["adaptador"]) == id_da_tela(QUARTO)
    finally:
        parada.soltar()
        bancada.fechar()


def test_com_o_daemon_mudo_o_interruptor_e_o_travessao_e_nao_manda_nada(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem ``radio_central`` no estado (o daemon não respondeu), o campo é o"""
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    bancada, _parada = montar(a08, monkeypatch)
    try:
        mudo = Contexto(state={"controllers": []}, conectados=[], mesa=[])
        assert tique(a08, mudo)["radio-procurando"] == a08.TRAVESSAO_DO_PROCURAR
        with pytest.raises(RuntimeError):
            bancada.gesto("radio-procurar")
        assert bancada.ponte.chamadas == []
        assert bancada.mundo.metodos("StartDiscovery") == []
    finally:
        bancada.fechar()


def test_ligar_e_desligar_nao_tira_ninguem_do_ar_nem_do_lugar(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quatro controles em três adaptadores (P1 e P2 na sala, P3 no quarto, P4"""
    relogio = rm.Relogio()
    mundo = RadioComHora(relogio)
    for onde, quem in ((SALA, VERMELHO), (SALA, AZUL), (QUARTO, VERDE), (VARANDA, ROXO)):
        mundo.pareado(onde, quem)
    jogadores = {rm.uniq(VERMELHO): 1, rm.uniq(AZUL): 2, rm.uniq(VERDE): 3, rm.uniq(ROXO): 4}
    bancada, parada = montar(a08, monkeypatch, mundo, jogadores=jogadores)

    def quem_esta_onde() -> set[tuple[str, str, Any]]:
        bancada.tique()
        return {(str(a["id"]), str(a["lugar"]), a.get("jogador"))
                for a in a08._CENA_NA_TELA["aparelhos"]
                if a.get("tipo") == "controle" and not a.get("nao_conectou")}

    try:
        antes = quem_esta_onde()
        assert {j for _i, _l, j in antes} == {1, 2, 3, 4}
        for onde in ADAPTADORES:
            assert ligar(bancada, parada, onde)["status"] == "ok"
            assert desligar(bancada, parada)["status"] == "ok"
            bancada.esperar_a_central()
            assert mundo.metodos("Disconnect") == [], onde
            assert mundo.metodos("RemoveDevice") == [] and mundo.lapides == [], onde
            assert {e: f.conectado_em for e, f in mundo.fisicos.items()} == {
                VERMELHO: SALA, AZUL: SALA, VERDE: QUARTO, ROXO: VARANDA}, onde
            assert quem_esta_onde() == antes, onde
    finally:
        parada.soltar()
        bancada.fechar()


def _folha(fonte: str, prefixo: str) -> dict[str, dict[str, str]]:
    """As regras ``.cadeado…`` de uma folha, por seletor, sem o ``prefixo``."""
    regras: dict[str, dict[str, str]] = {}
    for seletor, corpo in re.findall(r"^\s*(" + re.escape(prefixo) + r"\.cadeado[^{]*)\{([^}]*)\}",
                                     fonte, re.M):
        chave = seletor[len(prefixo):].strip()
        regras[chave] = dict(
            (p.split(":", 1)[0].strip(), p.split(":", 1)[1].strip())
            for p in corpo.split(";") if ":" in p)
    return regras


def test_a_peca_e_a_do_modo_freestyle() -> None:
    """A folha ``.cadeado`` da seção do rádio tem os mesmos valores da aba"""
    jogar = _folha((INTERFACE / "aba01.py").read_text(encoding="utf-8"), "")
    radio = _folha((INTERFACE / "aba08.py").read_text(encoding="utf-8"), ".radio ")
    assert set(jogar) == {".cadeado", ".cadeado .p", ".cadeado.ligada", ".cadeado.ligada .p"}
    assert radio == jogar
    assert jogar[".cadeado"]["height"] == "26px"


class _JanelaQueDorme:
    def fechar(self) -> None:
        time.sleep(2.0)


class _CentralQueDemora:
    """A central de mentira cujo ``fechar`` da janela dorme 2 s."""

    def __init__(self) -> None:
        self.janela = _JanelaQueDorme()

    def ligar_a_busca(self, ligada: bool, destino: str | None = None) -> dict[str, Any]:
        if not ligada:
            self.janela.fechar()
        return {"status": "ok", "busca": None}


@pytest.mark.asyncio
async def test_o_verbo_nao_segura_o_laco_do_servico() -> None:
    """Uma tarefa do laço que acorda a cada 10 ms continua rodando durante o"""
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    class _Daemon(IpcHandlersMixin):
        pass

    eu = _Daemon()
    eu.daemon = SimpleNamespace(_central_do_radio=_CentralQueDemora())  # type: ignore[attr-defined]
    voltas = 0

    async def laco() -> None:
        nonlocal voltas
        while True:
            await asyncio.sleep(0.01)
            voltas += 1

    tarefa = asyncio.create_task(laco())
    try:
        await asyncio.sleep(0.05)
        antes = voltas
        resposta = await eu._handle_radio_busca_set({"ligada": False})
        durante = voltas - antes
    finally:
        tarefa.cancel()
    assert resposta == {"status": "ok", "busca": None}
    assert durante >= 50, f"o laço deu {durante} voltas em 2 s"


@pytest.mark.parametrize("params", [{}, {"ligada": "sim"}, {"ligada": True, "destino": 7}])
def test_o_verbo_recusa_o_que_nao_e_o_contrato(params: dict[str, Any]) -> None:
    """``ligada`` é booleano e ``destino``, quando vem, é o endereço."""
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    class _Daemon(IpcHandlersMixin):
        pass

    eu = _Daemon()
    eu.daemon = SimpleNamespace(_central_do_radio=_CentralQueDemora())  # type: ignore[attr-defined]
    with pytest.raises(ValueError):
        asyncio.run(eu._handle_radio_busca_set(params))
