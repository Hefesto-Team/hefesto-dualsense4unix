"""A-CHEGADA-E-A-ASSINATURA-DE-CADA-CONTROLE-01: o aperto de mão de cada controle ao entrar.

Ao conectar, a barra sobe na cor do controle, a háptica dá um Toque na nota da unidade e o gatilho
clica uma vez, depois que a rajada da Steam passa. O aparelho nunca é tocado: as pontas da
Chegada são listas, o relógio do gatilho é o `devidos(agora)` e o tempo da subida é injetado.

As mordidas (arrancar a cura, ver reprovar, devolver conferindo o md5 do arquivo):
- tirar a espera (`ESPERA_S = 0.0`) faz a régua 2 reprovar;
- trocar a unidade pelo índice do jogador (a nota sai da posição na mesa) faz a régua 3 reprovar;
- escrever o gatilho por cima do jogo (`jogo_escreve(uniq, "gatilho")` ignorado) faz a 4 reprovar;
- valer no Personalizado e no Nativo (`SEM_COR` esvaziado) faz a 1 reprovar;
- o laço sem a chamada da Chegada (no primeiro controle ou nos que chegam depois): a régua 5.
"""
from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Callable
from itertools import pairwise
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon import connection as conn
from hefesto_dualsense4unix.daemon.subsystems import chegada as ch
from hefesto_dualsense4unix.integrations.cor_do_plastico import cor_do_nome
from hefesto_dualsense4unix.profiles import estilos_de_jogo as ej
from hefesto_dualsense4unix.profiles import formas_de_haptica as fh

#: Os quatro controles pela cor do plástico (Starlight Blue, White, Cosmic Red, Galactic Purple),
#: com endereços de faixa forjada (`aa:bb:cc`), nunca de aparelho de verdade.
AZUL, BRANCO, VERMELHO, ROXO = (f"aa:bb:cc:00:00:{n:02x}" for n in (0x11, 0x12, 0x13, 0x14))
COR_DE = {AZUL: "Starlight Blue", BRANCO: "White", VERMELHO: "Cosmic Red", ROXO: "Galactic Purple"}
NOTA_DE = {AZUL: 150, BRANCO: 165, VERMELHO: 180, ROXO: 195}
LUZ_DE = {AZUL: (40, 80, 255), BRANCO: (240, 240, 240), VERMELHO: (255, 30, 30),
          ROXO: (170, 60, 255)}


class _Mesa:
    """As pontas da Chegada como listas: o que tocou, o que pintou, o que clicou."""

    def __init__(self, na_mesa: tuple[str, ...] = (AZUL, BRANCO, VERMELHO, ROXO)) -> None:
        self.na_mesa = frozenset(na_mesa)
        self.vale = True
        self.do_jogo: set[tuple[str, str]] = set()
        self.registro: list[tuple[str, str, Any]] = []
        self.dormiu: list[float] = []
        # a nota vem da cor de fábrica, pela mesma função da produção
        self.daemon = SimpleNamespace(identity_registry=SimpleNamespace(
            identidade_de_fabrica=lambda uniq: SimpleNamespace(cor=cor_do_nome(COR_DE[uniq]))))

    def pontas(self) -> ch.PontasDaChegada:
        def anotar(canal: str) -> Any:
            def _f(uniq: str, *resto: Any) -> bool:
                self.registro.append((canal, uniq, resto))
                return True
            return _f

        return ch.PontasDaChegada(
            pode=lambda: self.vale,
            conectados=lambda: self.na_mesa,
            jogo_escreve=lambda uniq, canal: (uniq, canal) in self.do_jogo,
            nota=lambda uniq: ch.nota_da_unidade(self.daemon, uniq),
            cor=lambda uniq: LUZ_DE[uniq],
            pintar=anotar("luz"),
            devolver_a_luz=lambda: self.registro.append(("luz-devolvida", "", ())),
            tocar=anotar("toque"),
            clicar=anotar("gatilho"),
            soltar_o_clique=anotar("gatilho-solto"),
            dormir=self.dormiu.append,
        )

    def canais(self, uniq: str) -> set[str]:
        return {c for c, u, _ in self.registro if u == uniq and c in ("luz", "toque", "gatilho")}


def _daemon(mesa: _Mesa) -> Any:
    """Um daemon mínimo com a Chegada já montada nas pontas de lista."""
    return SimpleNamespace(
        _chegada=ch.Chegada(mesa.pontas()), _registro_de_gatilhos=None,
        identity_registry=mesa.daemon.identity_registry)


def _chegar(daemon: Any, *uniqs: str) -> int:
    agora = {f"k{n}": u for n, u in enumerate(uniqs)}
    return int(conn.anunciar_a_chegada(daemon, {}, agora))


def _devidos(daemon: Any, depois_s: float) -> list[str]:
    registro = conn.registro_de_gatilhos_de(daemon)
    return [g.nome for g, _ in registro.devidos(time.monotonic() + depois_s)]


def _disparar(daemon: Any) -> None:
    for gatilho, _ in conn.registro_de_gatilhos_de(daemon).devidos(time.monotonic() + 3600):
        gatilho.tarefa()


# --- 1. Uma Chegada por conexão; Nativo e Personalizado não tocam -----------------------


def test_uma_chegada_por_conexao_e_reconectar_toca_de_novo() -> None:
    """A Chegada é da conexão: uma por controle que entra, e reconectar toca de novo."""
    mesa = _Mesa()
    daemon = _daemon(mesa)
    assert _chegar(daemon, AZUL, BRANCO, VERMELHO, ROXO) == 4
    _disparar(daemon)
    for uniq in (AZUL, BRANCO, VERMELHO, ROXO):
        assert mesa.canais(uniq) == {"luz", "toque", "gatilho"}, uniq
    assert sum(1 for c, *_ in mesa.registro if c == "toque") == 4
    mesa.registro.clear()
    _disparar(daemon)  # nada novo chegou: não toca outra vez
    assert mesa.registro == []
    assert _chegar(daemon, VERMELHO) == 1  # reconectou
    _disparar(daemon)
    assert mesa.canais(VERMELHO) == {"luz", "toque", "gatilho"}
    assert mesa.canais(AZUL) == set()


@pytest.mark.parametrize("estilo", [e.chave for e in ej.ESTILOS])
def test_a_chegada_vale_em_todo_estilo_menos_o_nativo_e_o_personalizado(estilo: str) -> None:
    assert ch.a_chegada_vale(estilo, False) is (estilo not in {"nativo", "personalizado"})
    assert ch.a_chegada_vale(estilo, True) is False  # o Modo Nativo devolve o controle à Steam


def test_sem_estilo_a_chegada_nao_toca() -> None:
    assert ch.a_chegada_vale(None, False) is False
    mesa = _Mesa()
    mesa.vale = False
    daemon = _daemon(mesa)
    _chegar(daemon, AZUL)
    _disparar(daemon)
    assert mesa.registro == []


def test_o_controle_que_saiu_antes_da_hora_nao_ganha_chegada() -> None:
    mesa = _Mesa(na_mesa=(AZUL,))
    daemon = _daemon(mesa)
    _chegar(daemon, AZUL, ROXO)
    _disparar(daemon)
    assert mesa.canais(AZUL) and not mesa.canais(ROXO)


# --- 2. A Chegada espera a Steam ----------------------------------------------------------


def test_a_chegada_espera_a_rajada_da_steam_e_depois_toca_os_tres_canais() -> None:
    """D-2010-A-CHEGADA-ESPERA-A-RAJADA-DA-STEAM."""
    mesa = _Mesa(na_mesa=(AZUL,))
    daemon = _daemon(mesa)
    _chegar(daemon, AZUL)
    assert ch.ESPERA_S >= 3.9  # a rajada medida vai a 3,9 s (ensaio btmon-a-rajada-tem-hora)
    assert _devidos(daemon, ch.ESPERA_S - 0.5) == []
    assert mesa.registro == []
    registro = conn.registro_de_gatilhos_de(daemon)
    for gatilho, _ in registro.devidos(time.monotonic() + ch.ESPERA_S + 0.5):
        assert gatilho.nome == ch.NOME_DO_GATILHO
        gatilho.tarefa()
    assert mesa.canais(AZUL) == {"luz", "toque", "gatilho"}


def test_um_controle_novo_re_adia_a_chegada_dos_que_ja_esperavam() -> None:
    mesa = _Mesa()
    daemon = _daemon(mesa)
    _chegar(daemon, AZUL)
    gatilho = conn.registro_de_gatilhos_de(daemon).obter(ch.NOME_DO_GATILHO)
    assert gatilho is not None
    primeiro = gatilho.falta_para_disparar(time.monotonic())
    _chegar(daemon, BRANCO)
    assert gatilho.eventos_armados == 2
    assert gatilho.falta_para_disparar(time.monotonic()) is not None
    assert primeiro is not None and primeiro <= ch.ESPERA_S


def test_a_luz_sobe_em_degraus_e_nunca_pisca() -> None:
    mesa = _Mesa(na_mesa=(AZUL,))
    daemon = _daemon(mesa)
    _chegar(daemon, AZUL)
    _disparar(daemon)
    quadros = [r[2][0] for r in mesa.registro if r[0] == "luz"]
    assert len(quadros) == len(ch.BRILHOS_DA_SUBIDA)
    assert quadros[-1] == LUZ_DE[AZUL]
    assert all(a[0] <= b[0] and a[1] <= b[1] and a[2] <= b[2] for a, b in pairwise(quadros))
    assert mesa.registro[-1][0] in ("luz-devolvida", "gatilho-solto")
    assert any(c == "luz-devolvida" for c, *_ in mesa.registro)
    # um quadro a cada 0,12 s: a subida inteira cabe em 0,6 s, uma só, sem voltar atrás
    assert sum(mesa.dormiu) <= 1.0


# --- 3. A nota é da unidade ---------------------------------------------------------------


def _potencia(onda: Any, hz: int) -> float:
    re = sum(x * math.cos(2 * math.pi * hz * i / fh.TAXA) for i, x in enumerate(onda))
    im = sum(x * math.sin(2 * math.pi * hz * i / fh.TAXA) for i, x in enumerate(onda))
    return float(re * re + im * im)


def test_a_nota_e_da_cor_do_plastico_e_as_quatro_sao_distintas() -> None:
    mesa = _Mesa()
    notas = {u: ch.nota_da_unidade(mesa.daemon, u) for u in (AZUL, BRANCO, VERMELHO, ROXO)}
    assert notas == NOTA_DE
    assert len(set(notas.values())) == 4
    for uniq, hz in NOTA_DE.items():
        onda = fh.amostras(fh.forma_da_nota(hz), 1.0, ch.DURACAO_DO_TOQUE_MS)
        outras = [h for h in fh.NOTAS_DA_ASSINATURA if h != hz]
        assert all(_potencia(onda, hz) > 3 * _potencia(onda, o) for o in outras), uniq


@pytest.mark.parametrize("ordem", [(AZUL, BRANCO, VERMELHO, ROXO), (ROXO, VERMELHO, BRANCO, AZUL)])
def test_trocar_o_jogador_de_lugar_nao_muda_a_nota(ordem: tuple[str, ...]) -> None:
    """D-2010-A-ASSINATURA-E-A-NOTA-DA-COR-DO-PLASTICO."""
    mesa = _Mesa()
    daemon = _daemon(mesa)
    _chegar(daemon, *ordem)  # a ordem de chegada é a do número de jogador
    _disparar(daemon)
    formas = {u: resto[-1] for c, u, resto in mesa.registro if c == "toque"}
    assert formas == {u: fh.forma_da_nota(NOTA_DE[u]) for u in ordem}


def test_cor_sem_nota_toca_o_toque_de_sempre() -> None:
    daemon = SimpleNamespace(identity_registry=SimpleNamespace(
        identidade_de_fabrica=lambda uniq: SimpleNamespace(cor=cor_do_nome("Midnight Black"))))
    assert ch.nota_da_unidade(daemon, AZUL) is None
    assert fh.forma_da_nota(None) == fh.TOQUE
    sem_fabrica = SimpleNamespace(identity_registry=SimpleNamespace(
        identidade_de_fabrica=lambda uniq: None))
    assert ch.nota_da_unidade(sem_fabrica, AZUL) is None


def test_a_assinatura_nao_vira_escolha_da_tela() -> None:
    assert not set(fh.ASSINATURAS) & set(fh.ESCOLHAS)
    assert not set(fh.ASSINATURAS) & set(fh.FORMAS)


# --- 4. O jogo vence ----------------------------------------------------------------------


def test_com_o_gatilho_escrito_pelo_jogo_a_chegada_nao_escreve_o_gatilho() -> None:
    mesa = _Mesa(na_mesa=(AZUL, BRANCO))
    mesa.do_jogo = {(AZUL, "gatilho")}
    daemon = _daemon(mesa)
    _chegar(daemon, AZUL, BRANCO)
    _disparar(daemon)
    assert mesa.canais(AZUL) == {"luz", "toque"}
    assert mesa.canais(BRANCO) == {"luz", "toque", "gatilho"}
    assert not any(c.startswith("gatilho") and u == AZUL for c, u, _ in mesa.registro)


def test_com_a_luz_escrita_pelo_jogo_a_chegada_nao_pinta() -> None:
    mesa = _Mesa(na_mesa=(AZUL,))
    mesa.do_jogo = {(AZUL, "luz")}
    daemon = _daemon(mesa)
    _chegar(daemon, AZUL)
    _disparar(daemon)
    assert mesa.canais(AZUL) == {"toque", "gatilho"}
    assert not any(c.startswith("luz") for c, *_ in mesa.registro)


def test_o_clique_do_gatilho_e_o_clique_mouse_e_sai_na_hora() -> None:
    from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv

    bloco = tv.bloco_do_clique()
    assert len(bloco) == 11 and any(bloco[1:])
    mesa = _Mesa(na_mesa=(AZUL,))
    daemon = _daemon(mesa)
    _chegar(daemon, AZUL)
    _disparar(daemon)
    ordem = [c for c, u, _ in mesa.registro if c.startswith("gatilho")]
    assert ordem == ["gatilho", "gatilho-solto"]


# --- 5. O laço de reconexão chama a Chegada (o primeiro controle e os que chegam depois) ----


class _Controlador:
    """Um backend de lista: a mesa muda quando o teste manda, sem aparelho nenhum."""

    def __init__(self) -> None:
        self.online = False
        self.alvos: dict[str, str | None] = {}

    def connect(self) -> None:
        pass

    def is_connected(self) -> bool:
        return self.online

    def get_transport(self) -> str:
        return "bt"

    def alvos_conectados(self) -> dict[str, str | None]:
        return dict(self.alvos)


class _Vigia:
    def __init__(self) -> None:
        self._mudou = False

    def acordar(self) -> None:
        self._mudou = True

    def poll(self) -> bool:
        mudou, self._mudou = self._mudou, False
        return mudou


class _DaemonDoLaco:
    def __init__(self, mesa: _Mesa, controle: _Controlador) -> None:
        self.controller = controle
        self.bus = EventBus()
        self.config = SimpleNamespace()
        self._stop_event = asyncio.Event()
        self._registro_de_gatilhos: Any = None
        self._chegada = ch.Chegada(mesa.pontas())
        self.identity_registry = mesa.daemon.identity_registry

    def _is_stopping(self) -> bool:
        return self._stop_event.is_set()

    async def _run_blocking(self, fn: Callable[..., Any], *args: Any) -> Any:
        return fn(*args)

    def _arm_input_grace(self) -> None:
        pass


async def _ate(cond: Callable[[], bool], prazo: float = 3.0) -> None:
    fim = asyncio.get_running_loop().time() + prazo
    while not cond():
        assert asyncio.get_running_loop().time() < fim, "a condição não veio no prazo"
        await asyncio.sleep(0.005)


@pytest.mark.asyncio
async def test_o_laco_anuncia_o_primeiro_controle_e_os_que_chegam_depois(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(conn, "RECONNECT_PROBE_INTERVAL_SEC", 0.01)
    monkeypatch.setattr(conn, "RECONNECT_HOTPLUG_POLL_INTERVAL_SEC", 0.01)
    monkeypatch.setattr(conn, "RECONNECT_ONLINE_CHECK_INTERVAL_SEC", 30.0)
    monkeypatch.setattr(conn, "PASSO_ENQUANTO_O_GATILHO_ESTA_ARMADO_SEC", 0.01)
    monkeypatch.setattr(ch, "ESPERA_S", 0.05)  # o laço registra o gatilho com o prazo de agora
    mesa = _Mesa(na_mesa=(AZUL, BRANCO))
    controle = _Controlador()
    daemon: Any = _DaemonDoLaco(mesa, controle)
    vigia = _Vigia()
    laco = asyncio.create_task(conn.reconnect_loop(daemon, input_watch=vigia))
    try:
        registro = conn.registro_de_gatilhos_de(daemon)
        await _ate(lambda: registro.obter(ch.NOME_DO_GATILHO) is not None)
        gatilho = registro.obter(ch.NOME_DO_GATILHO)
        assert gatilho is not None and gatilho.atraso_s == ch.ESPERA_S
        controle.online, controle.alvos = True, {"k1": AZUL}
        vigia.acordar()
        await _ate(lambda: mesa.canais(AZUL) == {"luz", "toque", "gatilho"})
        controle.alvos = {"k1": AZUL, "k2": BRANCO}
        vigia.acordar()
        await _ate(lambda: mesa.canais(BRANCO) == {"luz", "toque", "gatilho"})
        assert sum(1 for c, u, _ in mesa.registro if c == "toque" and u == AZUL) == 1
    finally:
        daemon._stop_event.set()
        await laco


@pytest.mark.asyncio
async def test_a_subida_do_daemon_toca_todos_que_ja_estavam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A-CHEGADA-TOCA-TODOS-QUANDO-O-HEFESTO-REINICIA-01: reiniciar o daemon toca os quatro.

    A prova da D-2010-A-CHEGADA-TOCA-TODOS-NA-SUBIDA-DO-DAEMON.

    O laço nasce com a mesa cheia (é o `install.sh` reiniciando o serviço): cada controle ganha
    a Chegada, depois da espera da rajada. A troca de fio de um deles, depois, não toca de novo.
    MORDIDA: tire o `anunciar_a_chegada(daemon, {}, alvos_antes)` da subida do laço e reprova.
    """
    monkeypatch.setattr(conn, "RECONNECT_PROBE_INTERVAL_SEC", 0.01)
    monkeypatch.setattr(conn, "RECONNECT_HOTPLUG_POLL_INTERVAL_SEC", 0.01)
    monkeypatch.setattr(conn, "RECONNECT_ONLINE_CHECK_INTERVAL_SEC", 30.0)
    monkeypatch.setattr(conn, "PASSO_ENQUANTO_O_GATILHO_ESTA_ARMADO_SEC", 0.01)
    monkeypatch.setattr(ch, "ESPERA_S", 0.05)
    quatro = (AZUL, BRANCO, VERMELHO, ROXO)
    mesa = _Mesa(na_mesa=quatro)
    controle = _Controlador()
    controle.online, controle.alvos = True, {f"k{n}": u for n, u in enumerate(quatro)}
    daemon: Any = _DaemonDoLaco(mesa, controle)
    vigia = _Vigia()
    laco = asyncio.create_task(conn.reconnect_loop(daemon, input_watch=vigia))
    try:
        registro = conn.registro_de_gatilhos_de(daemon)
        await _ate(lambda: registro.obter(ch.NOME_DO_GATILHO) is not None)
        gatilho = registro.obter(ch.NOME_DO_GATILHO)
        assert gatilho is not None and gatilho.atraso_s == ch.ESPERA_S, "sem a espera da rajada"
        await _ate(lambda: all(mesa.canais(u) == {"luz", "toque", "gatilho"} for u in quatro))
        assert sorted(u for c, u, _ in mesa.registro if c == "toque") == sorted(quatro)
        mesa.registro.clear()
        # o AZUL troca de fio: o mesmo controle numa chave nova
        controle.alvos = {**{f"k{n}": u for n, u in enumerate(quatro) if u != AZUL}, "k9": AZUL}
        vigia.acordar()
        await asyncio.sleep(0.3)
        assert [u for c, u, _ in mesa.registro if c == "toque"] == [], (
            "a troca de fio de quem já estava tocou a Chegada")
    finally:
        daemon._stop_event.set()
        await laco


# --- 6. A subida da barra tem um dono só (o laço da luz animada espera) --------------------


def test_durante_a_subida_o_laco_da_luz_animada_nao_pinta_a_barra() -> None:
    """O laço da luz pinta a barra a até 30 quadros/s; a subida dura 0,6 s. Sem a pausa, os dois
    se alternam e a subida vira um pisca entre a rampa e o efeito do estilo.

    MORDIDA: tire o `segurando_a_luz` da pausa do `Passo` (ou o `_subindo` da subida) e o laço
    escreve no meio da subida: isto reprova.
    """
    from hefesto_dualsense4unix.daemon.subsystems import luz_animada as la
    from hefesto_dualsense4unix.profiles.schema import EfeitoDaLuz

    mesa = _Mesa(na_mesa=(AZUL,))
    daemon = _daemon(mesa)
    do_laco: list[tuple[str, Any]] = []
    animada = la.LuzAnimada(lambda u, c: do_laco.append((u, c)), lambda _u: None)
    passo = la.Passo(daemon, animada)
    plano = {AZUL: la.PlanoDoControle(EfeitoDaLuz("respirar", (LUZ_DE[AZUL],), 5), 1.0)}
    relogio = [0.0]
    segurados: list[frozenset[str]] = []

    def um_quadro_do_laco(_s: float) -> None:
        relogio[0] += 0.12
        segurados.append(ch.segurando_a_luz(daemon))
        animada.tique(relogio[0], plano, frozenset(), passo._quem_tem_outro_dono())

    daemon._chegada._pontas.dormir = um_quadro_do_laco
    assert animada.tique(0.0, plano) == 1  # antes da Chegada, o laço é o dono da barra
    do_laco.clear()
    _chegar(daemon, AZUL)
    _disparar(daemon)
    assert len(segurados) == len(ch.BRILHOS_DA_SUBIDA)
    assert all(s == frozenset({AZUL}) for s in segurados), segurados
    assert do_laco == [], "o laço pintou a barra no meio da subida"
    assert ch.segurando_a_luz(daemon) == frozenset()  # a subida acabou: a barra volta ao laço
    assert animada.tique(relogio[0] + 0.2, plano) == 1  # e o primeiro quadro sai, mesmo igual


def test_a_subida_que_falha_no_meio_devolve_a_barra_ao_laco() -> None:
    mesa = _Mesa(na_mesa=(AZUL,))
    daemon = _daemon(mesa)

    def cai(_s: float) -> None:
        raise RuntimeError("o rádio caiu")

    daemon._chegada._pontas.dormir = cai
    _chegar(daemon, AZUL)
    with pytest.raises(RuntimeError):
        _disparar(daemon)
    assert ch.segurando_a_luz(daemon) == frozenset()


def test_sem_chegada_montada_ninguem_segura_a_luz() -> None:
    assert ch.segurando_a_luz(SimpleNamespace()) == frozenset()


# --- 7. A Assinatura vale no Toque de todo tiro, não só no da Chegada ---------------------


def _toque_do_tiro(estilo: str | None, escolha: str | None = None,
                   uniqs: tuple[str, ...] = (AZUL, BRANCO, VERMELHO, ROXO)) -> dict[str, str]:
    """A forma que o Toque do tiro leva a cada controle (pelo tocador de lista)."""
    from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv

    mesa = _Mesa()
    feitos: list[tuple[Any, ...]] = []
    atuador = tv.AtuadorDaHaptica(
        lambda *a: feitos.append(a) or True, None, lambda _u: escolha, lambda: estilo, None,
        lambda uniq: ch.nota_da_unidade(mesa.daemon, uniq))
    receita = tv.Receita(vibracao_por_tiro=True)
    for uniq in uniqs:
        atuador.escrever(tv.Evento(0.0, uniq, tv.TIPO_RUMBLE, tv.LADO_ESQUERDO, 1.0), receita, 0.0)
    return {a[0]: (a[4] if len(a) > 4 else fh.TOQUE) for a in feitos}


def test_o_toque_do_tiro_toca_na_nota_de_cada_controle() -> None:
    """D-2010-O-TOQUE-DO-TIRO-LEVA-A-NOTA-DO-CONTROLE.

    MORDIDA: tire o `_toque_da_unidade` do `AtuadorDaHaptica.escrever` e os quatro tocam o
    mesmo Toque de 160 Hz: isto reprova (a régua 3 da Chegada seguiria verde)."""
    formas = _toque_do_tiro("fps")
    assert formas == {u: fh.forma_da_nota(NOTA_DE[u]) for u in (AZUL, BRANCO, VERMELHO, ROXO)}
    assert len(set(formas.values())) == 4


@pytest.mark.parametrize("estilo", ["personalizado", "nativo", None])
def test_no_personalizado_no_nativo_e_sem_estilo_o_toque_e_o_de_sempre(estilo: str | None) -> None:
    assert set(_toque_do_tiro(estilo).values()) == {fh.TOQUE}


def test_a_forma_que_nao_e_o_toque_nao_ganha_nota() -> None:
    assert set(_toque_do_tiro("fps", fh.IMPACTO).values()) == {fh.IMPACTO}
    assert set(_toque_do_tiro("luta").values()) == {fh.IMPACTO}  # a forma do estilo manda


def test_a_producao_liga_a_nota_da_unidade_ao_toque_do_tiro(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv

    mesa = _Mesa()
    tocados: list[tuple[Any, ...]] = []
    alto = SimpleNamespace(tocar_o_toque=lambda *a: tocados.append(a) or True)
    daemon = SimpleNamespace(
        _alto_falante_subsystem=alto, identity_registry=mesa.daemon.identity_registry,
        controller=None)
    monkeypatch.setattr(tv, "estilo_ativo", lambda _d: "fps")
    monkeypatch.setattr(tv, "_controle_na_economia", lambda _u: False)
    atuador = next(a for a in tv.atuadores_de_producao(daemon)
                   if isinstance(a, tv.AtuadorDaHaptica))
    atuador.escrever(tv.Evento(0.0, ROXO, tv.TIPO_RUMBLE, tv.LADO_ESQUERDO, 1.0),
                     tv.Receita(vibracao_por_tiro=True), 0.0)
    assert [(a[0], a[4]) for a in tocados] == [(ROXO, "toque-195")]


# --- 8. As pontas de produção falam a língua do backend -------------------------------------


class _Backend:
    """Os nomes e as assinaturas do backend de verdade, com o que cada um recebeu."""

    def __init__(self) -> None:
        self.feito: list[tuple[str, tuple[Any, ...]]] = []
        self._game_output_by_uniq: dict[str, Any] = {}
        self._game_triggers_by_uniq: dict[str, Any] = {}

    def alvos_conectados(self) -> dict[str, str | None]:
        return {"k1": AZUL, "k2": None}

    def resolved_led_for(self, uniq: str) -> tuple[int, int, int] | None:
        return LUZ_DE.get(uniq)

    def pintar_a_barra_sem_lembrar(self, uniq: str, rgb: tuple[int, int, int]) -> bool:
        self.feito.append(("pintar", (uniq, rgb)))
        return True

    def reassert_resolved_outputs(self, *, verify: bool = False) -> None:
        self.feito.append(("devolver", ()))

    def set_game_trigger_for(self, uniq: str, side: str, block: bytes) -> bool:
        self.feito.append(("clicar", (uniq, side, block)))
        return True

    def soltar_o_gatilho_do_jogo_for(self, uniq: str, side: str, bloco: bytes) -> bool:
        self.feito.append(("soltar", (uniq, side, bloco)))
        return True


def test_as_pontas_de_producao_chegam_ao_backend_e_ao_tocador(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv

    backend = _Backend()
    tocados: list[tuple[Any, ...]] = []
    mesa = _Mesa()
    daemon = SimpleNamespace(
        controller=backend, identity_registry=mesa.daemon.identity_registry,
        _alto_falante_subsystem=SimpleNamespace(tocar_o_toque=lambda *a: tocados.append(a) or True),
        is_native_mode=lambda: False)
    monkeypatch.setattr(tv, "estilo_ativo", lambda _d: "fps")
    chegada = ch.Chegada(ch.pontas_de_producao(daemon))
    chegada._pontas.dormir = lambda _s: None
    chegada.chegou(AZUL)
    feito = chegada.tocar()
    assert feito == {AZUL: {"luz": True, "toque": True, "gatilho": True}}
    assert tocados == [(AZUL, ch.ENERGIA_DO_TOQUE, "centro", ch.DURACAO_DO_TOQUE_MS, "toque-150")]
    nomes = [n for n, _ in backend.feito]
    assert nomes == ["clicar", *["pintar"] * len(ch.BRILHOS_DA_SUBIDA), "devolver", "soltar"]
    bloco = tv.bloco_do_clique()
    assert backend.feito[0][1] == (AZUL, "right", bloco)
    assert backend.feito[-1][1] == (AZUL, "right", bloco)
    assert backend.feito[-3][1] == (AZUL, LUZ_DE[AZUL])  # o último degrau é a cor cheia


def test_as_pontas_de_producao_cedem_ao_que_o_jogo_escreveu(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv

    backend = _Backend()
    chave = AZUL.replace(":", "")  # a camada do jogo mora pelo `norm_mac`, como no backend
    backend._game_output_by_uniq[chave] = SimpleNamespace(
        led=(1, 2, 3), trigger_left=None, trigger_right=None)
    backend._game_triggers_by_uniq[chave] = {"right": b"\x21"}
    mesa = _Mesa()
    daemon = SimpleNamespace(
        controller=backend, identity_registry=mesa.daemon.identity_registry,
        _alto_falante_subsystem=SimpleNamespace(tocar_o_toque=lambda *a: True),
        is_native_mode=lambda: False)
    monkeypatch.setattr(tv, "estilo_ativo", lambda _d: "fps")
    chegada = ch.Chegada(ch.pontas_de_producao(daemon))
    chegada._pontas.dormir = lambda _s: None
    chegada.chegou(AZUL)
    assert chegada.tocar() == {AZUL: {"luz": False, "toque": True, "gatilho": False}}
    assert backend.feito == []


def test_as_pontas_de_producao_nao_tocam_no_modo_nativo(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv

    backend = _Backend()
    daemon = SimpleNamespace(
        controller=backend, identity_registry=_Mesa().daemon.identity_registry,
        _alto_falante_subsystem=None, is_native_mode=lambda: True)
    monkeypatch.setattr(tv, "estilo_ativo", lambda _d: "fps")
    chegada = ch.Chegada(ch.pontas_de_producao(daemon))
    chegada.chegou(AZUL)
    assert chegada.tocar() == {}
    assert backend.feito == []
