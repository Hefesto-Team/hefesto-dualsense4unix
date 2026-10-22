"""O-DIARIO-DO-DAEMON-CABE-EM-MIL-LINHAS-POR-DIA-01 (22/10/2026): mil linhas por dia.

Medido no `/var/log/syslog` de 18/10 a 21/10/2026: 34.837 linhas do daemon em quatro dias e 76
subidas. Depois da junta da rajada (O-ENOMEM) ficavam 26.884; sem o estado normal (a escrita de
rotina que deu certo, o estado de novo dito e o inventário da subida) e com a janela que dobra
nos laços lentos, ficam 8.498. Aqui o dia é sintético, para valer num clone limpo.

MORDIDAS:
  * tire o `desce_o_estado_normal` da `cadeia_do_diario`: a régua da cadeia reprova;
  * esvazie a tabela do estado normal: o dia passa de mil linhas;
  * deixe a largura da janela fixa: o laço lento de 70 s volta a escrever uma linha por volta;
  * ponha `daemon_starting` ou `uhid_motion_streaming` na tabela do estado normal: a régua do
    leitor reprova (o segundo é lido por `docs/protocol/`).
"""
from __future__ import annotations

import heapq
import io
import logging
import re
from collections.abc import Callable, Iterator
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.utils import logging_config as lc

RAIZ = Path(__file__).resolve().parents[2]
DIA_S = 86400.0


class _Mesa:
    """Um agregado de mentira com relógio e fio de mentira, e o logger do produto em cima dele."""

    def __init__(self, nivel: int = logging.INFO) -> None:
        self.buf = io.StringIO()
        self.agora = 0.0
        self.agendados: list[tuple[float, int, Any, Any]] = []
        self._ordem = 0
        mesa = self

        class _DeMentira(lc.AgregadoDoDiario):
            def _agendar(self, chave: Any, janela: Any, segundos: float) -> None:
                mesa._agendar(chave, janela, segundos)

        self.agregado = _DeMentira(relogio=lambda: self.agora)
        self.diario = structlog.wrap_logger(
            structlog.PrintLogger(file=self.buf),
            processors=[lc.desce_o_estado_normal, self.agregado,
                        structlog.processors.add_log_level,
                        structlog.processors.KeyValueRenderer(sort_keys=True)],
            wrapper_class=structlog.make_filtering_bound_logger(nivel),
            context_class=dict,
        )
        self.agregado.diario = self.diario
        self.brutas = 0

    def _agendar(self, chave: Any, janela: Any, segundos: float) -> None:
        self._ordem += 1
        heapq.heappush(self.agendados, (self.agora + segundos, self._ordem, chave, janela))

    def ate(self, t: float) -> None:
        """Anda o relógio até ``t``, fechando no caminho as janelas que vencem."""
        while self.agendados and self.agendados[0][0] <= t:
            prazo, _, chave, janela = heapq.heappop(self.agendados)
            self.agora = prazo
            self.agregado._fechar(chave, janela)
        self.agora = t

    def dizer(self, t: float, nivel: str, evento: str, **campos: Any) -> None:
        self.ate(t)
        self.brutas += 1
        getattr(self.diario, nivel)(evento, **campos)

    def fim(self) -> None:
        self.ate(self.agora + 2 * lc.JANELA_MAXIMA_DO_AGREGADO_S)
        self.agregado.fechar_tudo()

    def linhas(self, evento: str | None = None) -> list[str]:
        todas = self.buf.getvalue().splitlines()
        return todas if evento is None else [x for x in todas if f"event='{evento}'" in x
                                              or f"event={evento}" in x]


@pytest.fixture(autouse=True)
def _nivel_info(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lc, "_nivel_minimo", logging.INFO)


# 1 ─ O estado normal só vale no DEBUG ───────────────────────────────────────


@pytest.mark.parametrize("evento", sorted(lc.EVENTOS_DE_ESTADO_NORMAL))
def test_o_estado_normal_desce_ao_debug_e_o_aviso_do_mesmo_nome_fica(evento: str) -> None:
    mesa = _Mesa(logging.DEBUG)
    mesa.diario.info(evento, x=1)
    assert mesa.linhas() == [], "o info do estado normal escreveu no nível do produto"
    mesa.diario.warning(evento, x=1)
    mesa.diario.error(evento, x=1)
    assert len(mesa.linhas()) == 2, "o aviso e o erro do mesmo nome têm de seguir escritos"


def test_no_debug_o_estado_normal_volta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lc, "_nivel_minimo", logging.DEBUG)
    mesa = _Mesa(logging.DEBUG)
    for evento in sorted(lc.EVENTOS_DE_ESTADO_NORMAL):
        mesa.diario.info(evento)
    assert len(mesa.linhas()) == len(lc.EVENTOS_DE_ESTADO_NORMAL)


def test_a_cadeia_do_produto_desce_antes_de_juntar() -> None:
    cadeia = lc.cadeia_do_diario("console", io.StringIO())
    assert cadeia[0] is lc.desce_o_estado_normal and cadeia[1] is lc._AGREGADO


def test_o_configure_logging_grava_o_nivel_que_a_cadeia_le(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem mexer na configuração viva do structlog, que é de todos os testes do processo."""
    chamadas: list[dict[str, Any]] = []
    monkeypatch.setattr(lc, "_configured", False)
    monkeypatch.setattr(structlog, "configure", lambda **kw: chamadas.append(kw))
    monkeypatch.setattr(logging, "basicConfig", lambda **kw: None)
    lc.configure_logging(level="debug", stream=io.StringIO())
    assert lc._nivel_minimo == logging.DEBUG and chamadas
    assert chamadas[0]["processors"][0] is lc.desce_o_estado_normal


# 2 ─ Só o emissor conhece o nome ────────────────────────────────────────────


def _fontes() -> Iterator[tuple[Path, str]]:
    alvos = (("src/hefesto_dualsense4unix", ("*.py",)), ("scripts", ("*.py", "*.sh")),
             ("docs/protocol", ("*.md",)), ("docs/method", ("*.md",)), ("docs/usage", ("*.md",)))
    for pasta, padroes in alvos:
        for padrao in padroes:
            for arquivo in (RAIZ / pasta).rglob(padrao):
                if arquivo.name == "logging_config.py" or "__pycache__" in arquivo.parts:
                    continue
                try:
                    yield arquivo, arquivo.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue


def _lidos_por_outro(nomes: set[str]) -> dict[str, list[str]]:
    """Os nomes que mais de um arquivo cita: o emissor e quem lê o diário atrás dele."""
    achados: dict[str, list[str]] = {n: [] for n in nomes}
    regras = {n: re.compile(rf"\b{re.escape(n)}\b") for n in nomes}
    for arquivo, texto in _fontes():
        for nome, regra in regras.items():
            if regra.search(texto):
                achados[nome].append(str(arquivo.relative_to(RAIZ)))
    return {n: f for n, f in achados.items() if len(f) > 1}


def test_o_estado_normal_nao_tem_leitor_no_diario() -> None:
    """Descer ao debug um evento que o doctor, o pad_usb, um ensaio ou uma medição do protocolo
    leem os deixa cegos."""
    assert _lidos_por_outro(set(lc.EVENTOS_DE_ESTADO_NORMAL)) == {}


def test_a_regua_do_leitor_morde() -> None:
    nomes = {"daemon_starting", "vpad_parou", "som_radio_ponte_de_pe", "uhid_motion_streaming"}
    lidos = _lidos_por_outro(nomes)
    assert set(lidos) == nomes, lidos
    assert any(f.startswith("docs/protocol/") for f in lidos["uhid_motion_streaming"]), lidos


def test_o_estado_normal_e_a_rajada_nao_se_misturam() -> None:
    assert not lc.EVENTOS_DE_ESTADO_NORMAL & set(lc.EVENTOS_AGREGADOS)
    for mantido in ("daemon_main", "daemon_starting", "ipc_server_listening",
                    "servico_pronto_avisado", "bateria_amostra", "mods_aberta"):
        assert mantido not in lc.EVENTOS_DE_ESTADO_NORMAL, mantido


# 3 ─ A janela dobra no laço lento ───────────────────────────────────────────


def _laco(
    mesa: _Mesa, evento: str, de_s: float, ate_s: float, passo_s: float, **campos: Any
) -> None:
    t = de_s
    while t < ate_s:
        mesa.dizer(t, "info", evento, **campos)
        t += passo_s


def test_o_laco_de_setenta_segundos_custa_poucas_linhas_por_hora() -> None:
    """Uma volta a cada 70 s nunca cabe na janela de 60 s: sem a que dobra, uma linha cada."""
    mesa = _Mesa()
    _laco(mesa, "haptica_fina_de_pe", 0.0, 6 * 3600.0, 70.0, controle="branco")
    mesa.fim()
    assert mesa.brutas > 300
    linhas = mesa.linhas("haptica_fina_de_pe")
    assert len(linhas) <= 80, f"{len(linhas)} linhas para {mesa.brutas} voltas"
    assert "controle='branco'" in linhas[0], "a primeira ocorrência sai inteira, na hora"


def test_a_janela_dobra_ate_o_teto_e_volta_ao_normal_depois_do_silencio() -> None:
    mesa = _Mesa()
    larguras: list[float] = []
    for volta in range(12):
        mesa.dizer(volta * 70.0, "info", "haptica_fina_saiu", controle="branco")
        janela = next(iter(mesa.agregado._janelas.values()))
        larguras.append(janela.largura)
    assert larguras[0] == lc.JANELA_DO_AGREGADO_S
    assert larguras == sorted(larguras), f"a janela encolheu sem silêncio: {larguras}"
    assert all(b in (a, 2 * a) for a, b in pairwise(larguras)), larguras
    assert larguras[:4] == [60.0, 120.0, 120.0, 240.0], larguras
    assert max(larguras) <= lc.JANELA_MAXIMA_DO_AGREGADO_S
    assert max(larguras) > lc.JANELA_DO_AGREGADO_S, "a janela não dobrou"
    mesa.fim()
    mesa.dizer(mesa.agora + 3 * lc.JANELA_MAXIMA_DO_AGREGADO_S, "info", "haptica_fina_saiu",
               controle="branco")
    assert next(iter(mesa.agregado._janelas.values())).largura == lc.JANELA_DO_AGREGADO_S


def test_o_resumo_diz_a_largura_da_janela_que_valeu() -> None:
    mesa = _Mesa()
    for volta in range(6):
        mesa.dizer(volta * 70.0, "info", "haptica_fina_saiu", controle="branco")
    mesa.fim()
    resumos = [x for x in mesa.linhas("haptica_fina_saiu") if "vezes=" in x]
    assert resumos and all(re.search(r"janela_s=\d+(\.\d+)?", x) for x in resumos), resumos
    assert any("janela_s=60" not in x for x in resumos), "o resumo mente a largura da janela"


def test_o_evento_fora_da_tabela_e_o_aviso_nunca_se_perdem() -> None:
    mesa = _Mesa()
    _laco(mesa, "perfil_trocado_pela_mao", 0.0, 3600.0, 30.0)
    for i in range(5):
        mesa.dizer(i * 70.0, "warning", "ipc_handler_error", method="x")
    assert len(mesa.linhas("perfil_trocado_pela_mao")) == 120
    assert len(mesa.linhas("ipc_handler_error")) == 5


# 4 ─ Um dia inteiro cabe em mil linhas ──────────────────────────────────────

_CONVERSA = ("autoswitch_fica_no_ultimo_jogo", "speaker_volume_set", "microphone_led_set",
             "hidraw_broker_fd_recebido", "hidraw_broker_lease_open", "x11_focus_gate_no_x_focus")
_MANTIDOS = {"profile_activated": 40, "usb_saiu": 10, "controller_connected": 12}


def _um_dia(mesa: _Mesa) -> None:
    """Duas subidas, a conversa de rotina, três laços lentos, uma rajada e as bordas de verdade."""
    for subida in (0.0, DIA_S / 2):
        for nome in ("daemon_main", "daemon_starting", "ipc_server_listening",
                     "servico_pronto_avisado"):
            mesa.dizer(subida, "info", nome)
        for nome in sorted(lc.EVENTOS_DE_ESTADO_NORMAL):
            mesa.dizer(subida + 1.0, "info", nome, uniq="aa:bb:cc:00:00:01")
    for nome in _CONVERSA:
        _laco(mesa, nome, 5.0, DIA_S, 60.0, uniq="aa:bb:cc:00:00:01")
    _laco(mesa, "haptica_fina_de_pe", 7.0, DIA_S / 2, 70.0, controle="branco")
    _laco(mesa, "haptica_fina_saiu", 8.0, DIA_S / 2, 70.0, controle="branco")
    _laco(mesa, "ipc_lento", 9.0, DIA_S, 30.0, metodo="daemon.state_full", ms=229)
    _laco(mesa, "gatilho_armado", 20000.0, 21800.0, 0.6, nome="lightbar", quantos=1)
    for nome, vezes in _MANTIDOS.items():
        for i in range(vezes):
            mesa.dizer(100.0 + i * (DIA_S / (vezes + 1)), "info", nome, i=i)
    for i in range(5):
        mesa.dizer(3000.0 * (i + 1), "warning", "ipc_handler_error", method="x")
    mesa.fim()


def test_um_dia_de_rotina_cabe_em_mil_linhas_e_nenhuma_borda_se_perde() -> None:
    mesa = _Mesa()
    _um_dia(mesa)
    assert mesa.brutas > 15000, mesa.brutas
    escritas = len(mesa.linhas())
    assert escritas < 1000, f"{escritas} linhas para {mesa.brutas} ocorrências"
    for nome, vezes in _MANTIDOS.items():
        assert len(mesa.linhas(nome)) == vezes, f"{nome}: o diário perdeu uma borda de verdade"
    assert len(mesa.linhas("ipc_handler_error")) == 5
    assert len(mesa.linhas("daemon_starting")) == 2


def test_sem_a_tabela_do_estado_normal_o_dia_estoura(monkeypatch: pytest.MonkeyPatch) -> None:
    """A mordida da régua do dia: esvaziada a tabela, a conversa de rotina volta a ser escrita."""
    monkeypatch.setattr(lc, "EVENTOS_DE_ESTADO_NORMAL", frozenset())
    mesa = _Mesa()
    _um_dia(mesa)
    assert len(mesa.linhas()) >= 1000


# 5 ─ A tabela da rajada nasce do syslog ─────────────────────────────────────


@pytest.mark.parametrize("evento", [
    "haptica_fina_saiu", "haptica_fina_de_pe", "haptica_portao_fechado",
    "som_radio_sem_ponte", "som_radio_ponte_saiu", "launch_env_materializado",
    "usb_ausente_neste_boot", "backend_hotplug_reconcile",
])
def test_a_rajada_nova_se_junta_por_controle(evento: str) -> None:
    campos: Callable[[str], dict[str, str]] = lambda quem: {  # noqa: E731
        c: quem for c in lc.EVENTOS_AGREGADOS[evento]}
    mesa = _Mesa()
    for _ in range(30):
        mesa.dizer(mesa.agora, "info", evento, **campos("a"))
        if campos("b"):
            mesa.dizer(mesa.agora, "info", evento, **campos("b"))
    mesa.fim()
    quantos = 2 if campos("b") else 1
    assert len(mesa.linhas(evento)) == 2 * quantos
