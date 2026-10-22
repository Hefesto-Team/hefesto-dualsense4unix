"""O-ENOMEM-DA-LEITURA-DO-PAD-USB-TEM-CAUSA-01 (22/10/2026): a rajada vira uma linha.

Medido no `/var/log/syslog` de 18/10 a 21/10/2026: 34.837 linhas do daemon, e 9.446
delas de cinco eventos `info` que chegam em rajada (`gatilho_armado` a 186 por minuto).
A cadeia do diário do produto junta cada rajada numa janela: a primeira ocorrência sai
inteira, e as seguintes saem numa linha só, no fim da janela, com `vezes=`.

MORDIDA: tirar o `_AGREGADO` da `cadeia_do_diario` devolve uma linha por evento, e a
primeira régua reprova com 200 linhas.
"""

from __future__ import annotations

import io
import json
import logging
import types
from collections.abc import Iterator
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.daemon import connection
from hefesto_dualsense4unix.utils import logging_config


class _Mesa:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.buf = io.StringIO()
        self.agora = [1000.0]
        self.agendados: list[tuple[Any, ...]] = []
        agregado = logging_config._AGREGADO
        monkeypatch.setattr(agregado, "_janelas", {})
        monkeypatch.setattr(agregado, "relogio", lambda: self.agora[0])
        monkeypatch.setattr(
            agregado, "_agendar", lambda chave, janela, _s: self.agendados.append((chave, janela))
        )
        self.diario = structlog.wrap_logger(
            structlog.PrintLogger(file=self.buf),
            processors=logging_config.cadeia_do_diario("console", self.buf),
            wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
            context_class=dict,
        )
        monkeypatch.setattr(agregado, "diario", self.diario)
        self.agregado = agregado

    def linhas(self, evento: str) -> list[str]:
        return [
            linha for linha in self.buf.getvalue().splitlines()
            if f" {evento} " in linha or linha.endswith(f" {evento}")
        ]

    def fim_das_janelas(self) -> None:
        self.agora[0] += logging_config.JANELA_DO_AGREGADO_S
        agendados, self.agendados = self.agendados, []
        for chave, janela in agendados:
            self.agregado._fechar(chave, janela)


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Mesa]:
    yield _Mesa(monkeypatch)


def _daemon_com_gatilho(nome: str) -> Any:
    daemon = types.SimpleNamespace()
    connection.registrar_gatilho(daemon, nome, lambda: None, atraso_s=0.5)
    return daemon


def test_duzentos_gatilhos_armados_dao_duas_linhas(
    mesa: _Mesa, monkeypatch: pytest.MonkeyPatch
) -> None:
    # D-2210-O-DIARIO-JUNTA-A-RAJADA
    """O chamador de verdade (`armar_gatilho`), 200 vezes na mesma janela."""
    monkeypatch.setattr(connection, "logger", mesa.diario)
    daemon = _daemon_com_gatilho("lightbar")
    for _ in range(200):
        assert connection.armar_gatilho(daemon, "lightbar", evento="perfil")
    assert len(mesa.linhas("gatilho_armado")) == 1, mesa.buf.getvalue()
    mesa.fim_das_janelas()
    linhas = mesa.linhas("gatilho_armado")
    assert len(linhas) == 2, linhas
    assert "vezes=199" in linhas[1] and "nome=lightbar" in linhas[1]


@pytest.mark.parametrize("evento", sorted(logging_config.EVENTOS_AGREGADOS))
def test_cada_evento_da_tabela_se_junta(mesa: _Mesa, evento: str) -> None:
    campos = {c: "x" for c in logging_config.EVENTOS_AGREGADOS[evento]}
    for _ in range(50):
        mesa.diario.info(evento, **campos)
    mesa.fim_das_janelas()
    assert len(mesa.linhas(evento)) == 2, mesa.buf.getvalue()


def test_a_chave_separa_as_rajadas_e_o_evento_de_fora_nao_se_junta(mesa: _Mesa) -> None:
    for _ in range(5):
        mesa.diario.info("ipc_lento", metodo="daemon.status", ms=150)
        mesa.diario.info("ipc_lento", metodo="profile.switch", ms=300)
        mesa.diario.info("perfil_trocado_pela_mao", origem="tela")
    assert len(mesa.linhas("ipc_lento")) == 2
    assert len(mesa.linhas("perfil_trocado_pela_mao")) == 5


def test_a_ocorrencia_da_janela_vencida_fecha_a_conta(mesa: _Mesa) -> None:
    """Sem o fio do fim da janela, quem chega depois dela leva a conta junto."""

    def escrever() -> None:
        mesa.diario.info("gatilho_armado", nome="cor")

    for _ in range(4):
        escrever()
    mesa.agora[0] += logging_config.JANELA_DO_AGREGADO_S + 1
    escrever()
    linhas = mesa.linhas("gatilho_armado")
    assert len(linhas) == 2 and "vezes=4" in linhas[1], linhas
    escrever()
    mesa.agregado.fechar_tudo()
    linhas = mesa.linhas("gatilho_armado")
    assert len(linhas) == 3 and "vezes=1" in linhas[2], linhas


def test_o_perfil_fechado_que_diverge_fica_no_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    # D-2210-A-MASCARA-ANTECIPADA-VAI-AO-DEBUG
    """A troca da máscara viva fazia 25 linhas `info` no mesmo segundo, uma por perfil.

    MORDIDA: devolver o `logger.info` ao `mascara_do_perfil_antecipada`.
    """
    from hefesto_dualsense4unix.daemon import launch_env

    diario = io.StringIO()
    monkeypatch.setattr(launch_env, "logger", structlog.wrap_logger(
        structlog.PrintLogger(file=diario),
        processors=[structlog.processors.add_log_level, structlog.processors.JSONRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
    ))
    launch_env._publicar_divergencias(
        types.SimpleNamespace(),
        [
            {"appid": 10 + i, "motivo": "perfil_xbox_vs_vivo_dualsense", "em_cena": False,
             "profile": f"P{i}", "mascara_perfil": "xbox", "mascara_viva": "dualsense"}
            for i in range(25)
        ],
    )
    registros = [json.loads(linha) for linha in diario.getvalue().splitlines()]
    niveis = [r["level"] for r in registros if r["event"] == "mascara_do_perfil_antecipada"]
    assert niveis == ["debug"] * 25, registros
