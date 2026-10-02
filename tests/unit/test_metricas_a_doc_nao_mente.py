"""A página de métricas e a ADR-016 não podem envelhecer caladas."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.daemon.subsystems.metrics import (
    ENV_METRICS_ENABLED,
    ENV_METRICS_PORT,
    MetricsSubsystem,
    _porta_efetiva,
)

_RAIZ = Path(__file__).resolve().parents[2]
_SRC = _RAIZ / "src" / "hefesto_dualsense4unix"
_METRICS_MD = _RAIZ / "docs" / "usage" / "metrics.md"
_ADR = _RAIZ / "docs" / "adr" / "016-prometheus-metrics.md"

_PREFIXO = "HEFESTO_DUALSENSE4UNIX_METRICS"


def _ocorrencias_em_src() -> list[str]:
    """Linhas de `src/` que citam o prefixo — a régua da frase que caducou."""
    achados: list[str] = []
    for arquivo in sorted(_SRC.rglob("*.py")):
        if "__pycache__" in arquivo.parts:
            continue
        for numero, linha in enumerate(
            arquivo.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if _PREFIXO in linha:
                achados.append(f"{arquivo.relative_to(_RAIZ)}:{numero}")
    return achados


def test_as_duas_chaves_sao_as_que_a_doc_nomeia() -> None:
    """Mordida: renomear `ENV_METRICS_PORT` no módulo."""
    assert f"{_PREFIXO}_ENABLED" == ENV_METRICS_ENABLED
    assert f"{_PREFIXO}_PORT" == ENV_METRICS_PORT

    texto = _METRICS_MD.read_text(encoding="utf-8")
    for chave in (ENV_METRICS_ENABLED, ENV_METRICS_PORT):
        assert chave in texto, (
            f"a página de métricas não cita {chave}, que é como se liga o "
            "endpoint. Sem o nome exato, a instrução não é executável"
        )


def test_a_contagem_de_ocorrencias_em_src_e_medida_e_nao_copiada() -> None:
    """A frase de 25/07 dizia ZERO e sobreviveu um mês depois de virar quatro."""
    achados = _ocorrencias_em_src()
    assert achados, "a régua quebrou: o prefixo sumiu de `src/` inteiro"

    modulos = {caminho.split(":")[0] for caminho in achados}
    assert modulos == {"src/hefesto_dualsense4unix/daemon/subsystems/metrics.py"}, (
        f"o prefixo saiu do módulo de métricas e a ADR não sabe: {sorted(modulos)}"
    )

    quantidade = len(achados)
    adr = _ADR.read_text(encoding="utf-8")
    escrito = re.search(
        r"devolve \*\*(\w+)\*\* linhas", adr
    ) or re.search(r"devolve \*\*(\w+)\*\*", adr)
    assert escrito is not None, (
        "a ADR deixou de declarar a contagem medida. Ela é o único número "
        "desta página que já mentiu por um mês — não pode voltar a ser implícito"
    )
    por_extenso = {
        1: "uma",
        2: "duas",
        3: "três",
        4: "quatro",
        5: "cinco",
        6: "seis",
        7: "sete",
        8: "oito",
    }
    assert escrito.group(1) == por_extenso.get(quantidade, str(quantidade)), (
        f"a ADR diz {escrito.group(1)!r} e a árvore tem {quantidade}: "
        f"{achados}"
    )


def test_nem_a_unit_nem_o_install_ligam_as_metricas() -> None:
    """É o que sustenta "nem o systemd nem a janela" na página."""
    suspeitos: list[str] = []
    for arquivo in [*sorted((_RAIZ / "assets").rglob("*.service")), _RAIZ / "install.sh"]:
        if not arquivo.exists():
            continue
        if _PREFIXO in arquivo.read_text(encoding="utf-8"):
            suspeitos.append(str(arquivo.relative_to(_RAIZ)))
    assert not suspeitos, (
        f"alguém passou a ligar as métricas por fora: {suspeitos}. A página diz "
        "o contrário, e a frase é o que a pessoa lê antes de procurar o endpoint"
    )


def test_a_tabela_da_doc_e_os_nomes_que_o_modulo_registra() -> None:
    """Oito nomes, e os dois lados têm de concordar."""
    fonte = (_SRC / "daemon" / "subsystems" / "metrics.py").read_text(encoding="utf-8")
    do_codigo = set(re.findall(r'"(hefesto_[a-z0-9_]+)"', fonte))

    tabela = _METRICS_MD.read_text(encoding="utf-8")
    da_doc = set(re.findall(r"\|\s*`(hefesto_[a-z0-9_]+)", tabela))

    assert do_codigo, "a régua quebrou: nenhum nome `hefesto_*` no módulo"
    assert do_codigo == da_doc, (
        "a tabela da página e o módulo discordam. Só no código: "
        f"{sorted(do_codigo - da_doc)}; só na doc: {sorted(da_doc - do_codigo)}"
    )
    assert len(do_codigo) == 8, (
        f"a página diz OITO nomes e há {len(do_codigo)}: {sorted(do_codigo)}"
    )


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [("1", True), ("true", False), ("0", False), (None, False)],
)
def test_is_enabled_so_aceita_o_literal_um(
    valor: str | None, esperado: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`"true"` NÃO liga, e a nota afirma isso por extenso."""
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

    if valor is None:
        monkeypatch.delenv(ENV_METRICS_ENABLED, raising=False)
    else:
        monkeypatch.setenv(ENV_METRICS_ENABLED, valor)

    assert MetricsSubsystem().is_enabled(DaemonConfig()) is esperado


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [("19199", 19199), ("abc", 9090), ("70000", 9090), (None, 9090)],
)
def test_porta_efetiva_recusa_o_que_nao_e_porta(
    valor: str | None, esperado: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Valor inválido cai no default em vez de derrubar o daemon."""
    if valor is None:
        monkeypatch.delenv(ENV_METRICS_PORT, raising=False)
    else:
        monkeypatch.setenv(ENV_METRICS_PORT, valor)

    assert _porta_efetiva(9090) == esperado
