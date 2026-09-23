"""A cor que FALHOU se pergunta de novo — A-FITA-PERDEU-O-MODELO-E-A-COR-01.

A queixa dela, 22/09/2026: *"houve uma regressão nos botões selecionar. sumiram
o tipo de plástico (modelo) e a cor dele."* A fita dizia ``P1 • BT`` sem borda,
e os cartões ``Não sei · BT`` nos dois controles. Reabrir a janela, sem mudar
uma linha, trouxe ``White`` e ``Galactic Purple`` de volta.

A causa: a janela (``mesa_viva.LeitorDeCor``) e o daemon
(``ipc_handlers._perguntar_identidade``) guardavam a primeira resposta PARA
SEMPRE, e a fonte (``ler_identidade_pelo_cabo``) devolvia a falha de um
instante igual à resposta «não sei a cor». As réguas daqui medem as três
metades: a fonte separa, a agenda decide, e os dois guardadores obedecem.

Nenhum byte vai a aparelho: o leitor é injetado, e o relógio também.
"""
from __future__ import annotations

import ast
import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import monta
from hefesto_dualsense4unix.integrations import cor_do_plastico as cp
from hefesto_dualsense4unix.interface import mesa_viva

UNIQ = "aa:bb:cc:00:00:01"
SERIAL_ROXO = "P5A004XXXXXXXXXXX"  # código 04 = Galactic Purple


class Relogio:
    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora


def _resposta(serial: str) -> bytes:
    buf = bytearray(cp.TAMANHO_DO_FEATURE)
    buf[0] = cp.FEATURE_RESPOSTA
    buf[1] = cp.BASE_DO_SERIAL
    buf[2] = cp.NUM_DO_SERIAL
    buf[3] = cp.MARCA_DE_RESPOSTA_BOA
    buf[4 : 4 + cp.TAMANHO_DO_SERIAL] = serial.encode("ascii")
    return bytes(buf)


def _ler(hid_id: str = "0005:0000054C:00000CE6") -> Any:
    return lambda _c: f"HID_UNIQ={UNIQ}\nHID_ID={hid_id}\nHID_PHYS=x\n"


#: A fonte de verdade, guardada antes de qualquer `monkeypatch` do daemon.
_LER_DE_VERDADE = cp.ler_identidade_pelo_cabo


def _identidade(perguntar: Any, *, listar: Any = None, hid_id: str | None = None) -> Any:
    return _LER_DE_VERDADE(
        UNIQ,
        raiz="/lugar-nenhum",
        listar=listar or (lambda _r: ["hidraw9"]),
        ler=_ler(hid_id) if hid_id else _ler(),
        perguntar=perguntar,
    )


class LeitorQueFalhaUmaVez:
    """Falha na 1ª pergunta (o descritor que não chegou), responde na 2ª."""

    def __init__(self, falhas: int = 1) -> None:
        self.falhas = falhas
        self.perguntas = 0

    def __call__(self, uniq: str) -> cp.IdentidadeDeFabrica:
        self.perguntas += 1
        if self.perguntas <= self.falhas:
            return _identidade(lambda _c, _p: None)
        return _identidade(lambda _c, _p: _resposta(SERIAL_ROXO))


def _estado(transporte: str = "bt") -> dict[str, Any]:
    return {"controllers": [
        {"uniq": UNIQ, "transport": transporte, "connected": True, "player": 1}]}


# ---------------------------------------------------------------------------
# 1 · A FONTE separa «falhou agora» de «respondeu que não sabe»
# ---------------------------------------------------------------------------
class TestAFonteSepara:
    def test_o_aparelho_que_nao_respondeu_nao_e_resposta(self) -> None:
        achado = _identidade(lambda _c, _p: None)
        assert achado.cor is None and not achado.definitiva
        assert achado.motivo, "a falha tem de dizer qual foi"

    def test_o_eco_errado_nao_e_resposta(self) -> None:
        ruim = bytearray(_resposta(SERIAL_ROXO))
        ruim[3] = 0
        assert not _identidade(lambda _c, _p: bytes(ruim)).definitiva

    def test_a_conversa_que_levanta_nao_e_resposta(self) -> None:
        def _estoura(_c: str, _p: bytes) -> bytes:
            raise OSError(5, "Input/output error")

        assert not _identidade(_estoura).definitiva

    def test_o_no_que_ainda_nao_nasceu_nao_e_resposta(self) -> None:
        assert not _identidade(lambda _c, _p: None, listar=lambda _r: []).definitiva

    def test_o_codigo_fora_da_tabela_e_resposta(self) -> None:
        """«Sei qual aparelho é, não sei a cor» não muda — perguntar de novo não adianta."""
        achado = _identidade(lambda _c, _p: _resposta("P5A099XXXXXXXXXXX"))
        assert achado.cor is None and achado.respondeu and achado.definitiva

    def test_o_aparelho_de_outro_fabricante_nao_recebe_byte_nenhum(self) -> None:
        """Sem alvo é falha — a agenda desiste sozinha —, e o pedido nem sai."""
        pedidos: list[bytes] = []

        def _anota(_c: str, pedido: bytes) -> None:
            pedidos.append(pedido)

        achado = _identidade(_anota, hid_id="0005:0000057E:00002009")
        assert pedidos == [] and not achado.definitiva

    def test_a_trava_que_recusa_nao_pode(self) -> None:
        def _recusa(_c: str, _p: bytes) -> bytes:
            raise cp.PedidoRecusadoError("par proibido")

        achado = _identidade(_recusa)
        assert achado.nao_pode and achado.definitiva


# ---------------------------------------------------------------------------
# 2 · A AGENDA — o dono único da nova tentativa
# ---------------------------------------------------------------------------
FALHA = cp.IdentidadeDeFabrica(motivo="o aparelho não respondeu")


class TestAAgenda:
    def test_a_falha_volta_com_recuo_e_depois_desiste(self) -> None:
        relogio = Relogio()
        agenda = cp.AgendaDaPergunta(relogio=relogio)
        instantes = []
        for _ in range(60 * 10 * 5):  # cinco minutos de tique a 10 Hz
            if agenda.reservar(UNIQ):
                instantes.append(relogio.agora - 1000.0)
                agenda.registrar(UNIQ, FALHA)
            relogio.agora += 0.1
        assert [round(t) for t in instantes] == [0, 5, 35, 155], instantes

    def test_nunca_duas_em_voo(self) -> None:
        relogio = Relogio()
        agenda = cp.AgendaDaPergunta(relogio=relogio)
        assert agenda.reservar(UNIQ)
        for _ in range(3000):
            relogio.agora += 0.1
            assert not agenda.reservar(UNIQ)
        agenda.esquecer_ausentes(set())  # o controle saiu e voltou no meio
        assert not agenda.reservar(UNIQ), "a pergunta ainda está no ar"

    def test_a_resposta_fecha(self) -> None:
        relogio = Relogio()
        agenda = cp.AgendaDaPergunta(relogio=relogio)
        assert agenda.reservar(UNIQ)
        agenda.registrar(UNIQ, cp.IdentidadeDeFabrica(serial=SERIAL_ROXO))
        relogio.agora += 3600
        assert not agenda.reservar(UNIQ)

    def test_quem_desistiu_recomeca_ao_voltar_para_a_mesa(self) -> None:
        relogio = Relogio()
        agenda = cp.AgendaDaPergunta(relogio=relogio)
        for _ in range(4):
            relogio.agora += 200
            assert agenda.reservar(UNIQ)
            agenda.registrar(UNIQ, FALHA)
        relogio.agora += 3600
        assert not agenda.reservar(UNIQ), "desistiu"
        agenda.esquecer_ausentes({"outro"})
        assert agenda.reservar(UNIQ), "reconectou: pergunta de novo"

    def test_a_lista_que_pisca_nao_vira_rajada(self) -> None:
        """O esquecimento a cada tique não pode furar o intervalo mínimo."""
        relogio = Relogio()
        agenda = cp.AgendaDaPergunta(relogio=relogio)
        perguntas = 0
        for _ in range(100):  # dez segundos, a lista vazia um tique sim outro não
            if agenda.reservar(UNIQ):
                perguntas += 1
                agenda.registrar(UNIQ, cp.IdentidadeDeFabrica(serial=SERIAL_ROXO))
            agenda.esquecer_ausentes(set())
            relogio.agora += 0.1
        assert perguntas <= 2, perguntas


# ---------------------------------------------------------------------------
# 3 · A JANELA — a fita mostra o modelo e a borda depois da nova tentativa
# ---------------------------------------------------------------------------
def _tique(leitor: mesa_viva.LeitorDeCor, estado: dict[str, Any]) -> list[dict[str, Any]]:
    """O que o tique do piloto faz, com a pergunta síncrona no lugar da thread."""
    conectados = estado["controllers"]
    leitor.esquecer_ausentes({c["uniq"] for c in conectados})
    for uniq in leitor.pendentes(conectados):
        leitor.perguntar(uniq)
    return list(mesa_viva.mesa_do_estado(estado, leitor.conhecidos()))


def test_a_fita_ganha_modelo_e_borda_depois_da_nova_tentativa() -> None:
    relogio = Relogio()
    falso = LeitorQueFalhaUmaVez()
    leitor = mesa_viva.LeitorDeCor(leitor=falso, agenda=cp.AgendaDaPergunta(relogio=relogio))

    mesa = _tique(leitor, _estado())
    assert mesa[0]["nome"] == mesa_viva.COR_DESCONHECIDA
    assert "--plastico" not in monta.fita(mesa=mesa), "a 1ª pergunta falhou"

    for _ in range(60):  # seis segundos de tique
        relogio.agora += 0.1
        mesa = _tique(leitor, _estado())

    fita = monta.fita(mesa=mesa)
    assert falso.perguntas == 2, falso.perguntas
    assert "Galactic Purple" in fita, fita
    assert "--plastico" in fita, fita


def test_o_transporte_que_o_mapa_nega_e_perguntado_nenhuma_vez(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(mesa_viva.MAPA, "identidade.cor_do_aparelho", ("não", "não"))
    relogio = Relogio()
    falso = LeitorQueFalhaUmaVez(falhas=0)
    leitor = mesa_viva.LeitorDeCor(leitor=falso, agenda=cp.AgendaDaPergunta(relogio=relogio))
    for _ in range(3000):
        _tique(leitor, _estado())
        relogio.agora += 0.1
    assert falso.perguntas == 0
    assert UNIQ in leitor.conhecidos() and leitor.conhecidos()[UNIQ] is None


def test_a_falha_nao_apaga_a_cor_que_ja_se_sabia() -> None:
    relogio = Relogio()
    agenda = cp.AgendaDaPergunta(relogio=relogio)
    leitor = mesa_viva.LeitorDeCor(
        leitor=lambda _u: _identidade(lambda _c, _p: _resposta(SERIAL_ROXO)), agenda=agenda)
    _tique(leitor, _estado())
    leitor._leitor = lambda _u: FALHA
    assert agenda.reservar(UNIQ) is False, "respondeu: fechado"
    leitor.perguntar(UNIQ)  # uma pergunta avulsa que falhou
    assert leitor.conhecidos()[UNIQ].nome == "Galactic Purple"


def test_a_janela_que_desistiu_pergunta_de_novo_quando_o_controle_volta() -> None:
    """A desistência dura até o controle sair da mesa — e o `LeitorDeCor` é quem avisa a agenda."""
    relogio = Relogio()
    falso = LeitorQueFalhaUmaVez(falhas=99)
    leitor = mesa_viva.LeitorDeCor(leitor=falso, agenda=cp.AgendaDaPergunta(relogio=relogio))
    for _ in range(10 * 60 * 5):  # cinco minutos de tique
        _tique(leitor, _estado())
        relogio.agora += 0.1
    assert falso.perguntas == 4, "a 1ª e as três novas tentativas"
    _tique(leitor, {"controllers": []})  # saiu da mesa
    relogio.agora += 0.1
    _tique(leitor, _estado())  # voltou
    assert falso.perguntas == 5, falso.perguntas

def test_o_piloto_dela_pergunta_pelo_leitor_e_nao_por_trava_propria() -> None:
    """O lançador abre `hefesto_vivo`, e era ali a TERCEIRA cópia do defeito.

    Um conjunto `perguntados` próprio, uma pergunta por controle por janela:
    a cura do `LeitorDeCor` não alcançaria a tela dela sem esta linha.
    """
    fonte = (INTERFACE / "hefesto_vivo.py").read_text(encoding="utf-8")
    contexto = next(
        no for no in ast.walk(ast.parse(fonte))
        if isinstance(no, ast.FunctionDef) and no.name == "_contexto"
    )
    chamadas = {
        no.func.attr for no in ast.walk(contexto)
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
    }
    assert "disparar" in chamadas and "perguntar" not in chamadas, chamadas


# ---------------------------------------------------------------------------
# 4 · O DAEMON — a mesma agenda, e o `modelo` do `state_full` volta
# ---------------------------------------------------------------------------
class _Handler:
    """O mixin com o mínimo que `_identidade_de_fabrica` toca."""

    def __init__(self, relogio: Relogio) -> None:
        self.daemon = None
        self._identidade_de_fabrica_cache: dict[str, Any] | None = None
        self._agenda_da_identidade = cp.AgendaDaPergunta(relogio=relogio)

    def __getattr__(self, nome: str) -> Any:
        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

        return getattr(IpcHandlersMixin, nome).__get__(self, type(self))


class _FioNaHora:
    """`threading.Thread` que roda o alvo no `start` — a régua é de ordem, não de fio."""

    def __init__(self, *, target: Any, args: tuple[Any, ...] = (), **_k: Any) -> None:
        self._alvo, self._args = target, args

    def start(self) -> None:
        self._alvo(*self._args)


@pytest.fixture
def daemon(monkeypatch: pytest.MonkeyPatch) -> Any:
    import threading

    monkeypatch.setattr(threading, "Thread", _FioNaHora)
    relogio = Relogio()
    return _Handler(relogio), relogio


def test_o_daemon_volta_a_perguntar_e_o_modelo_chega(
    daemon: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    handler, relogio = daemon
    falso = LeitorQueFalhaUmaVez()
    monkeypatch.setattr(cp, "ler_identidade_pelo_cabo", falso)
    entrada = {"uniq": UNIQ, "connected": True}

    assert handler._identidade_de_fabrica(UNIQ, entrada)["modelo"] is None
    for _ in range(40):  # quatro segundos: ainda no recuo
        relogio.agora += 0.1
        assert handler._identidade_de_fabrica(UNIQ, entrada)["modelo"] is None
    assert falso.perguntas == 1
    for _ in range(20):
        relogio.agora += 0.1
        publicado = handler._identidade_de_fabrica(UNIQ, entrada)
    assert falso.perguntas == 2
    assert publicado == {"serial": SERIAL_ROXO, "modelo": "Galactic Purple"}


def test_o_daemon_nao_pergunta_de_novo_a_quem_nao_pode(
    daemon: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    handler, relogio = daemon
    perguntas: list[str] = []

    def _nao_pode(uniq: str) -> cp.IdentidadeDeFabrica:
        perguntas.append(uniq)
        return cp.IdentidadeDeFabrica(nao_pode=True, motivo="a trava recusou o pedido")

    monkeypatch.setattr(cp, "ler_identidade_pelo_cabo", _nao_pode)
    for _ in range(3000):
        handler._identidade_de_fabrica(UNIQ, {"uniq": UNIQ, "connected": True})
        relogio.agora += 0.1
    assert perguntas == [UNIQ]


class _HandlerDaMesa(_Handler):
    """O mesmo mixin, com o que o enriquecimento do `state_full` toca fora do assunto."""

    controller = None

    def _player_slot_for(self, _uniq: Any) -> None:
        return None

    def _lightbar_for_uniq(self, *_a: Any) -> tuple[None, bool, str]:
        return (None, False, "desconhecida")

    def _lightbar_disputada(self, *_a: Any) -> bool:
        return False

    def _nascimento_para(self, *_a: Any) -> None:
        return None

    def _coop_live_snapshots(self) -> dict[str, Any]:
        return {}

    def _coop_uniqs_com_leitor(self) -> set[str]:
        return set()

    def _coop_vpads_by_uniq(self) -> dict[str, Any]:
        return {}

    def _inputs_passivos(self, *_a: Any) -> None:
        return None

    def _merge_sensores(self, *_a: Any) -> None:
        return None

    def _merge_audio(self, *_a: Any) -> None:
        return None


def test_o_daemon_que_desistiu_pergunta_de_novo_quando_o_controle_volta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pelo caminho do `state_full`: é o enriquecimento que diz à agenda quem saiu."""
    import threading

    monkeypatch.setattr(threading, "Thread", _FioNaHora)
    relogio = Relogio()
    handler = _HandlerDaMesa(relogio)
    perguntas: list[str] = []

    def _falha(uniq: str) -> cp.IdentidadeDeFabrica:
        perguntas.append(uniq)
        return FALHA

    monkeypatch.setattr(cp, "ler_identidade_pelo_cabo", _falha)

    def tique(entradas: list[dict[str, Any]]) -> None:
        handler._enrich_controllers_per_controller(entradas, None)
        relogio.agora += 0.1

    for _ in range(10 * 60 * 5):  # cinco minutos
        tique([{"uniq": UNIQ, "connected": True}])
    assert len(perguntas) == 4, "a 1ª e as três novas tentativas"
    tique([])  # saiu da mesa
    tique([{"uniq": UNIQ, "connected": True}])
    assert len(perguntas) == 5, perguntas
