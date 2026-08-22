"""A página de métricas e a ADR-016 não podem envelhecer caladas.

A LIÇÃO QUE PAGOU POR ESTE PORTÃO. Em 25/07/2026 a ADR-016 escreveu, como
confissão honesta do estado de então, que a variável de ambiente das métricas
*"tem zero ocorrências em `src/`"*. Em 01/08 as duas variáveis nasceram, e a
frase virou mentira. Ela sobreviveu **um mês** — não por descuido de ninguém,
mas porque **confissão específica é o tipo de frase que ninguém relê**: quem
abre uma ADR procura a decisão, não a auditoria de quem a escreveu.

A regra desta casa é que fato errado se SUBSTITUI. A ADR é decisão datada e por
isso ganha nota em vez de tesoura — mas o que impede a nota nova de apodrecer
igual é este arquivo: cada frase verificável das duas páginas vira uma asserção
DERIVADA DO CÓDIGO, nunca copiada do texto.

O que ele prende, e onde cada coisa é medida:

1. **as duas chaves de ambiente** — lidas do módulo, não escritas aqui;
2. **a contagem de ocorrências em `src/`** — a frase que caducou, agora medida
   a cada execução;
3. **`METRICS` não aparece em unit nem no `install.sh`** — é o que sustenta a
   afirmação "nem o systemd nem a janela ligam isto";
4. **os oito nomes de métrica da tabela** — a tabela da doc contra os nomes que
   o módulo de fato registra;
5. **`is_enabled` e `_porta_efetiva`**, com os casos que a nota de 22/08 diz ter
   conferido, inclusive os dois negativos (`"true"` e `"abc"`).
"""
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

#: O prefixo comum das duas chaves. Escrito UMA vez, e as duas chaves conferidas
#: contra ele — assim renomear o prefixo no código reprova aqui, em vez de
#: passar despercebido por o teste ter copiado o nome inteiro.
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


# --- 1. As duas chaves -------------------------------------------------------


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


# --- 2. A contagem que caducou ----------------------------------------------


def test_a_contagem_de_ocorrencias_em_src_e_medida_e_nao_copiada() -> None:
    """A frase de 25/07 dizia ZERO e sobreviveu um mês depois de virar quatro.

    A ADR agora afirma **quatro**, e este teste é o que impede o número novo de
    apodrecer igual: ele mede, e cobra que a ADR diga o que foi medido.

    Mordida: acrescentar um quinto uso do prefixo em `src/`.
    """
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


# --- 3. Ninguém liga isto por fora ------------------------------------------


def test_nem_a_unit_nem_o_install_ligam_as_metricas() -> None:
    """É o que sustenta "nem o systemd nem a janela" na página.

    Mordida: pôr um `Environment=...METRICS_ENABLED=1` em qualquer unit.
    """
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


# --- 4. A tabela de nomes ----------------------------------------------------


def test_a_tabela_da_doc_e_os_nomes_que_o_modulo_registra() -> None:
    """Oito nomes, e os dois lados têm de concordar.

    Mordida: acrescentar uma métrica no módulo sem pôr na tabela.
    """
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


# --- 5. O comportamento que a nota de 22/08 diz ter conferido ---------------


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [("1", True), ("true", False), ("0", False), (None, False)],
)
def test_is_enabled_so_aceita_o_literal_um(
    valor: str | None, esperado: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`"true"` NÃO liga, e a nota afirma isso por extenso.

    Mordida: trocar o `== "1"` por um `in ("1", "true")` no módulo.
    """
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

    if valor is None:
        monkeypatch.delenv(ENV_METRICS_ENABLED, raising=False)
    else:
        monkeypatch.setenv(ENV_METRICS_ENABLED, valor)

    # `is_enabled` é de INSTÂNCIA, e o subsistema não precisa de nada para
    # nascer — a nota da ADR diz "MetricsSubsystem.is_enabled(DaemonConfig())"
    # como abreviação, e a chamada real é esta.
    assert MetricsSubsystem().is_enabled(DaemonConfig()) is esperado


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [("19199", 19199), ("abc", 9090), ("70000", 9090), (None, 9090)],
)
def test_porta_efetiva_recusa_o_que_nao_e_porta(
    valor: str | None, esperado: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Valor inválido cai no default em vez de derrubar o daemon.

    Mordida: tirar a validação de faixa e deixar `70000` passar.
    """
    if valor is None:
        monkeypatch.delenv(ENV_METRICS_PORT, raising=False)
    else:
        monkeypatch.setenv(ENV_METRICS_PORT, valor)

    # `_porta_efetiva` é função de MÓDULO, não método — a nota da ADR a cita
    # sem qualificar, e conferir a citação contra a árvore é metade do trabalho
    # deste arquivo.
    assert _porta_efetiva(9090) == esperado
