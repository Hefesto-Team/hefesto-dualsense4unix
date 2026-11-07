"""O ouvido confere o link no grafo e se refaz sozinho (O-OUVIDO-CONFERE-O-LINK-E-SE-RELIGA-01).

O gravador nasce com ``node.dont-reconnect``: se o link cai, o processo segue vivo e surdo. Estas
réguas rodam o :class:`OuvidoDoJogo` do produto com relógio falso, o gravador de mentira e o grafo
na forma do ``pw-dump``; só o processo e o relógio são dublês.
"""
from __future__ import annotations

import json
from array import array
from collections.abc import Callable
from itertools import pairwise
from types import SimpleNamespace
from typing import Any

import pytest
import structlog.testing

from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.integrations import transiente_do_jogo as tj
from hefesto_dualsense4unix.integrations.alto_falante_bt import OrigemDoGravador
from hefesto_dualsense4unix.profiles import formas_de_haptica as fh

ID_DO_OUVIDO = 90
ID_DO_JOGO = 171
SERIAL_DO_JOGO = 719


def _no(ident: int, serial: int, nome: str) -> dict[str, Any]:
    return {"id": ident, "type": "PipeWire:Interface:Node",
            "info": {"props": {"node.name": nome, "object.serial": serial}}}


def _grafo(*, origem: int | None = ID_DO_JOGO, com_gravador: bool = True) -> str:
    objetos = [_no(ID_DO_JOGO, SERIAL_DO_JOGO, "village.exe"), _no(47, 77, "microfone")]
    if com_gravador:
        objetos.append(_no(ID_DO_OUVIDO, 2001, tj.ROTULO_DO_OUVIDO))
    if origem is not None:
        objetos.append({"id": 5000, "type": "PipeWire:Interface:Link",
                        "info": {"output-node-id": origem, "input-node-id": ID_DO_OUVIDO}})
    return json.dumps(objetos)


class _Gravador:
    """O processo: vive até ``morrer``, e a saída fica por conta de quem o escreve."""

    def __init__(self) -> None:
        self.codigo: int | None = None
        self.stdout = SimpleNamespace(read=lambda _n: b"")

    def poll(self) -> int | None:
        return self.codigo


def _fluxo(serial: int = SERIAL_DO_JOGO, *, pausado: bool = False) -> tj.FluxoDoJogo:
    return tj.FluxoDoJogo(78, serial, "village.exe", 4242, ident=ID_DO_JOGO, pausado=pausado)


class _Mesa:
    """O ouvido do produto, com o alvo lido do grafo pelo conferente do produto."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, grafo: str | None = None) -> None:
        self.agora = 100.0
        self.grafo: str | None = _grafo() if grafo is None else grafo
        self.fluxo: tj.FluxoDoJogo | None = _fluxo()
        self.gravadores: list[_Gravador] = []
        self.derrubados: list[Any] = []
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.retrato_do_som.ler_o_pw_dump",
            lambda: self.grafo,
        )
        self.ouvido = tj.OuvidoDoJogo(
            lambda: True,
            achar_o_fluxo=lambda: self.fluxo,
            montar_argv=lambda f: ["pw-record", f"--target={f.serial}"],
            abrir=self._abrir,
            derrubar=lambda proc, **_k: self.derrubados.append(proc),
            relogio=lambda: self.agora,
        )

    def _abrir(self, _argv: list[str]) -> _Gravador:
        self.gravadores.append(_Gravador())
        return self.gravadores[-1]

    def volta(self, passar_s: float = tj.PROCURA_S) -> None:
        self.agora += passar_s
        self.ouvido.uma_volta()

    def pcm(self) -> None:
        self.ouvido._ultimo_pcm = self.agora

    @property
    def gravacoes(self) -> int:
        return self.ouvido.contadores["gravacoes"]

    @property
    def religadas(self) -> int:
        return self.ouvido.contadores["religadas"]


def test_gravador_vivo_sem_link_a_volta_o_refaz_e_o_diario_diz_o_motivo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**A régua do defeito**: 03:34, o processo vivo, o ``wchar`` parado e zero links."""
    mesa = _Mesa(monkeypatch)
    mesa.volta()
    assert mesa.gravacoes == 1
    mesa.grafo = _grafo(origem=None)
    with structlog.testing.capture_logs() as linhas:
        mesa.volta()
    assert mesa.gravacoes == 2, "o gravador surdo ficou no ar: o teste voltou a ser só de processo"
    assert mesa.derrubados == [mesa.gravadores[0]]
    assert mesa.religadas == 1
    religada = [x for x in linhas if x["event"] == "tato_ouvido_religado"]
    assert [x["motivo"] for x in religada] == [tj.MOTIVO_LINK_CAIDO]


def test_o_no_do_gravador_sumiu_do_grafo_e_link_caido(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch)
    mesa.volta()
    mesa.volta()
    mesa.grafo = _grafo(origem=None, com_gravador=False)
    mesa.volta()
    assert mesa.gravacoes == 2


@pytest.mark.parametrize("grafo", ["", "não é json", "[]"])
def test_grafo_mudo_e_nao_sei_e_nada_se_refaz(
    grafo: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    mesa = _Mesa(monkeypatch)
    mesa.volta()
    mesa.grafo = grafo
    mesa.volta(3600.0)
    assert mesa.gravacoes == 1 and mesa.religadas == 0
    assert not mesa.ouvido._conferido


def test_o_conferente_separa_a_origem_o_sem_link_e_o_nao_sei(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _Mesa(monkeypatch)
    conferir = tj.conferir_o_alvo_do_ouvido
    assert conferir(tj.ROTULO_DO_OUVIDO) == OrigemDoGravador(
        ID_DO_JOGO, SERIAL_DO_JOGO, "village.exe")
    mesa.grafo = _grafo(origem=None)
    assert conferir(tj.ROTULO_DO_OUVIDO) is tj.SEM_LINK
    mesa.grafo = _grafo(origem=None, com_gravador=False)
    assert conferir(tj.ROTULO_DO_OUVIDO) is tj.SEM_NO
    mesa.grafo = None
    assert conferir(tj.ROTULO_DO_OUVIDO) is None


def test_o_gravador_que_o_grafo_nunca_mostrou_nao_se_refaz(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O ``parec`` no PipeWire nasce sem o rótulo no ``node.name``: nada prova que ficou surdo."""
    mesa = _Mesa(monkeypatch)
    mesa.grafo = _grafo(origem=None, com_gravador=False)
    for _ in range(40):
        mesa.volta(60.0)
    assert mesa.gravacoes == 1 and mesa.religadas == 0


def test_o_gravador_refeito_precisa_aparecer_de_novo_para_contar_como_sumido(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _Mesa(monkeypatch)
    mesa.volta()
    mesa.volta()
    mesa.grafo = _grafo(origem=None, com_gravador=False)
    mesa.volta()
    assert mesa.gravacoes == 2
    mesa.volta(3600.0)
    assert mesa.gravacoes == 2


def test_jogo_pausado_com_o_link_de_pe_nao_se_refaz(monkeypatch: pytest.MonkeyPatch) -> None:
    """Medido em PipeWire próprio: o cork deixa os links em ``paused`` e o PCM em zero."""
    mesa = _Mesa(monkeypatch)
    mesa.volta()
    mesa.pcm()
    mesa.fluxo = _fluxo(pausado=True)
    for _ in range(40):
        mesa.volta()
    assert mesa.gravacoes == 1 and mesa.religadas == 0
    assert mesa.ouvido.pausado


def test_a_pausa_nao_sobrevive_ao_gravador(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem gravador não há pausa a reconhecer: o surdo volta a contar."""
    mesa = _Mesa(monkeypatch)
    mesa.volta()
    mesa.pcm()
    mesa.fluxo = _fluxo(pausado=True)
    for _ in range(3):
        mesa.volta()
    assert mesa.ouvido.pausado and mesa.ouvido.surdo_ha_s() == 0.0
    mesa.fluxo = None
    mesa.gravadores[-1].codigo = 0
    mesa.volta()
    assert not mesa.ouvido.pausado and mesa.ouvido.surdo_ha_s() > 0.0


def test_o_silencio_sozinho_nunca_refaz(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem resposta do grafo, ou sem fluxo a confirmar, o silêncio não basta."""
    mesa = _Mesa(monkeypatch)
    mesa.volta()
    mesa.fluxo = None
    mesa.volta(3600.0)
    assert mesa.gravacoes == 1
    mesa.fluxo = _fluxo()
    mesa.grafo = ""
    mesa.volta(3600.0)
    assert mesa.gravacoes == 1


def test_link_de_pe_fluxo_tocando_e_gravador_mudo_se_refaz(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _Mesa(monkeypatch)
    mesa.volta()
    mesa.pcm()
    mesa.volta(tj.PRAZO_DO_SILENCIO_S - 0.1)
    assert mesa.gravacoes == 1, "abaixo do prazo o silêncio não pesa"
    with structlog.testing.capture_logs() as linhas:
        mesa.volta(0.2)
    assert mesa.gravacoes == 2 and mesa.religadas == 1
    assert [x["motivo"] for x in linhas if x["event"] == "tato_ouvido_religado"] == [
        tj.MOTIVO_SEM_PCM]


def test_fluxo_novo_do_jogo_troca_o_alvo_quando_o_velho_cala(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _Mesa(monkeypatch)
    mesa.volta()
    mesa.fluxo = _fluxo(serial=800)
    with structlog.testing.capture_logs() as linhas:
        mesa.volta(tj.PRAZO_DO_SILENCIO_S)
    assert mesa.ouvido._fluxo is mesa.fluxo
    assert [x["motivo"] for x in linhas if x["event"] == "tato_ouvido_religado"] == [
        tj.MOTIVO_FLUXO_NOVO]


def test_dois_fluxos_com_pcm_chegando_nao_ha_troca(monkeypatch: pytest.MonkeyPatch) -> None:
    """O jogo de mentira com dois: o ouvido fica no que ouve e nada oscila."""
    mesa = _Mesa(monkeypatch)
    mesa.volta()
    mesa.fluxo = _fluxo(serial=800)
    for _ in range(20):
        mesa.pcm()
        mesa.volta()
    assert mesa.gravacoes == 1


def test_o_outro_fluxo_tambem_pausado_nao_troca(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch)
    mesa.volta()
    mesa.fluxo = _fluxo(serial=800, pausado=True)
    mesa.volta(3600.0)
    assert mesa.gravacoes == 1


def test_o_gravador_saiu_o_motivo_diz_se_o_fluxo_mudou(monkeypatch: pytest.MonkeyPatch) -> None:
    """Medido em PipeWire próprio: o nó do jogo some e o ``pw-record`` sai sozinho."""
    mesa = _Mesa(monkeypatch)
    mesa.volta()
    mesa.gravadores[0].codigo = 0
    with structlog.testing.capture_logs() as linhas:
        mesa.volta()
        mesa.gravadores[1].codigo = 0
        mesa.fluxo = _fluxo(serial=800)
        mesa.volta(tj.RECUO_TETO_S)
    assert [x["motivo"] for x in linhas if x["event"] == "tato_ouvido_religado"] == [
        tj.MOTIVO_GRAVADOR_SAIU, tj.MOTIVO_FLUXO_NOVO]


def test_sem_fluxo_o_motivo_espera_o_jogo_voltar(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch)
    mesa.volta()
    mesa.grafo = _grafo(origem=None)
    mesa.fluxo = None
    mesa.volta()
    assert mesa.ouvido._proc is None and mesa.religadas == 0
    mesa.volta()
    assert mesa.religadas == 0
    mesa.fluxo = _fluxo(serial=800)
    mesa.volta()
    assert mesa.gravacoes == 2 and mesa.religadas == 1


def test_o_recuo_cresce_e_para_no_teto_e_o_contador_conta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _Mesa(monkeypatch)
    mesa.volta()
    mesa.grafo = _grafo(origem=None)
    instantes = []
    for _ in range(400):
        antes = mesa.religadas
        mesa.volta()
        if mesa.religadas != antes:
            instantes.append(mesa.agora)
    intervalos = [b - a for a, b in pairwise(instantes)]
    assert intervalos[:6] == [5.0, 10.0, 20.0, 40.0, 60.0, 60.0], intervalos
    assert set(intervalos[4:]) == {tj.RECUO_TETO_S}
    assert mesa.religadas == len(instantes)


def test_o_recuo_tambem_segura_o_gravador_que_sai_em_seguida(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _Mesa(monkeypatch)
    mesa.volta()
    instantes = []
    for _ in range(200):
        mesa.gravadores[-1].codigo = 0
        antes = mesa.gravacoes
        mesa.volta()
        if mesa.gravacoes != antes:
            instantes.append(mesa.agora)
    intervalos = [b - a for a, b in pairwise(instantes)]
    assert intervalos[:5] == [5.0, 10.0, 20.0, 40.0, 60.0], intervalos


def test_link_firme_com_pcm_zera_o_recuo(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch)
    mesa.volta()
    mesa.grafo = _grafo(origem=None)
    for _ in range(4):
        mesa.volta(tj.RECUO_TETO_S)
    assert mesa.ouvido._seguidas == 4
    mesa.grafo = _grafo()
    mesa.pcm()
    mesa.agora += 1.0
    for _ in range(7):
        mesa.pcm()
        mesa.volta()
    assert mesa.ouvido._seguidas == 0
    mesa.grafo = _grafo(origem=None)
    gravacoes = mesa.gravacoes
    mesa.volta(0.1)
    assert mesa.gravacoes == gravacoes + 1, "depois do link firme a religada é imediata"


def test_o_link_que_nao_firma_nao_zera_o_recuo(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch)
    mesa.volta()
    mesa.grafo = _grafo(origem=None)
    mesa.volta()
    mesa.grafo = _grafo()
    mesa.pcm()
    mesa.volta()
    assert mesa.ouvido._seguidas == 1


def test_o_link_firme_sem_pcm_nao_zera_o_recuo(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch)
    mesa.volta()
    mesa.grafo = _grafo(origem=None)
    mesa.volta()
    assert mesa.ouvido._seguidas == 1
    mesa.grafo = _grafo()
    mesa.fluxo = _fluxo(pausado=True)
    for _ in range(8):
        mesa.volta()
    assert mesa.ouvido._seguidas == 1


def test_o_alvo_se_confere_a_cada_volta_e_nao_uma_vez_so(monkeypatch: pytest.MonkeyPatch) -> None:
    """``_conferido`` fixo deixava o gravador no microfone depois da primeira conferência."""
    mesa = _Mesa(monkeypatch)
    mesa.volta()
    mesa.pcm()
    mesa.volta()
    assert mesa.ouvido._conferido
    mesa.grafo = _grafo(origem=47)
    mesa.pcm()
    mesa.volta()
    assert mesa.ouvido.contadores["alvo_errado"] == 1
    assert mesa.gravacoes == 2 and mesa.religadas == 1


def test_o_alvo_se_confere_depois_de_religar(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch)
    mesa.volta()
    mesa.grafo = _grafo(origem=None)
    mesa.volta()
    mesa.grafo = _grafo(origem=47)
    mesa.volta(tj.RECUO_TETO_S)
    assert mesa.ouvido.contadores["alvo_errado"] == 1


def test_sem_pedido_o_gravador_cala_e_o_recuo_recomeca(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch)
    pedido = {"quer": True}
    mesa.ouvido._querer = lambda: pedido["quer"]
    mesa.volta()
    mesa.grafo = _grafo(origem=None)
    mesa.volta()
    pedido["quer"] = False
    mesa.volta()
    assert mesa.ouvido._proc is None and mesa.ouvido._seguidas == 0
    assert mesa.ouvido._motivo is None


def test_o_recorte_do_fluxo_diz_o_pausado() -> None:
    def fluxo(indice: int, corked: bool) -> SimpleNamespace:
        return SimpleNamespace(
            indice=indice, corked=corked,
            propriedades={"application.process.id": "7", "object.serial": str(indice),
                          "node.name": "jogo"})

    assert tj.fluxo_do_jogo([fluxo(1, True)], {7}) == tj.FluxoDoJogo(
        1, 1, "jogo", 7, pausado=True)
    assert tj.fluxo_do_jogo([fluxo(1, True), fluxo(2, False)], {7}) == tj.FluxoDoJogo(
        2, 2, "jogo", 7)


P = tuple(f"aa:bb:cc:00:00:{i:02x}" for i in range(1, 5))
_CABO, _RADIO = "cabo", "radio"
MESAS = (
    (_CABO, _CABO, _CABO, _CABO),
    (_CABO, _CABO, _CABO, _RADIO),
    (_RADIO, _CABO, _CABO, _CABO),
    (_CABO, _RADIO, _CABO, _RADIO),
    (_RADIO, _RADIO, _CABO, _CABO),
    (_RADIO, _RADIO, _CABO, _RADIO),
    (_CABO, _RADIO, _RADIO, _RADIO),
    (_RADIO, _RADIO, _RADIO, _RADIO),
)
MASCARAS = (
    (tv.MODO_DUALSENSE, tv.MODO_XBOX, tv.MODO_DUALSENSE, tv.MODO_XBOX),
    (tv.MODO_XBOX, tv.MODO_XBOX, tv.MODO_XBOX, tv.MODO_XBOX),
    (tv.MODO_XBOX, tv.MODO_DUALSENSE, tv.MODO_NATIVO, tv.MODO_DUALSENSE),
    (tv.MODO_NATIVO, tv.MODO_DUALSENSE, tv.MODO_XBOX, tv.MODO_NATIVO),
)


class _AltoFalante:
    def __init__(self) -> None:
        self.corpo: list[str] = []

    def tocar_o_corpo(self, uniq: str, amostras: Any) -> bool:
        self.corpo.append(uniq)
        return True


def _pcm(quadros: int) -> bytes:
    return array("h", [8000, 8000] * quadros).tobytes()


class _Maos:
    """O gravador que devolve um pedaço de PCM e fecha: o ``ao_pcm`` corre na thread do ouvido."""

    def __init__(self, pcm: Callable[[], bytes]) -> None:
        pedacos = [pcm(), b""]
        self.stdout = SimpleNamespace(read=lambda _n: pedacos.pop(0))

    def poll(self) -> int | None:
        return None


def _levar_o_pcm(ouvido: tj.OuvidoDoJogo) -> None:
    leitor = ouvido._leitor
    assert leitor is not None
    leitor.join(timeout=5.0)


@pytest.mark.parametrize("modos", MASCARAS)
@pytest.mark.parametrize("mesa", MESAS)
def test_depois_da_religada_cada_controle_que_escolheu_o_corpo_volta_a_receber(
    mesa: tuple[str, ...], modos: tuple[str, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    """O ouvido é um por jogo: a religada devolve o PCM a todos, em qualquer posição.

    A conexão não entra no ouvido nem na decisão do corpo: a mesa misturada entra pela ordem
    dos controles, e no Nativo nada toca.
    """
    alto = _AltoFalante()
    motor = tv.TatoVivo([])
    motor.escolhas = {norm_mac(u): fh.SOM_NO_CORPO for u in P}
    passo = tv.Passo(SimpleNamespace(_alto_falante_subsystem=alto), motor)
    passo.receita_vigente = tv.Receita(som_no_corpo_escolhido=True)
    ordem = tuple(p for _t, p in sorted(zip(mesa, P, strict=True)))
    estados = {
        u: tv.EstadoDoCanal(modo=m, ha_jogo=True) for u, m in zip(P, modos, strict=True)}

    grafo = {"texto": _grafo()}
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.retrato_do_som.ler_o_pw_dump",
        lambda: grafo["texto"],
    )
    gravadores: list[_Maos] = []

    def abrir(_argv: list[str]) -> _Maos:
        gravadores.append(_Maos(lambda: _pcm(4800)))
        return gravadores[-1]

    agora = {"t": 100.0}
    ouvido = tj.OuvidoDoJogo(
        lambda: True, achar_o_fluxo=_fluxo, montar_argv=lambda _f: ["pw-record"], abrir=abrir,
        derrubar=lambda _p, **_k: None, relogio=lambda: agora["t"],
        ao_pcm=passo.alimentar_o_corpo)

    ouvido.uma_volta()
    _levar_o_pcm(ouvido)
    passo._levar_o_corpo(passo.receita_vigente, ordem, lambda u: estados[u])
    donos = sorted(u for u in P if estados[u].modo != tv.MODO_NATIVO)
    assert sorted(alto.corpo) == donos

    alto.corpo.clear()
    grafo["texto"] = _grafo(origem=None)
    agora["t"] += tj.PROCURA_S
    ouvido.uma_volta()
    _levar_o_pcm(ouvido)
    assert len(gravadores) == 2
    passo._levar_o_corpo(passo.receita_vigente, ordem, lambda u: estados[u])
    assert sorted(alto.corpo) == donos
