"""LIGHTBAR-MEDIR-O-0X08-01 — o instrumento que separa duas medições que brigam.

08/08/2026. A lightbar dos DualSense do usuário por Bluetooth **não acende mais**:
LEDs de jogador acesos, barra morta, escritas de cor ignoradas — a assinatura
exata do latch de firmware documentado em `core/lightbar_reset.py:1-11`.

TRÊS MEDIÇÕES QUE PRECISAM CABER JUNTAS
=======================================
1. a ADOÇÃO do controle derruba o claim da lightbar (17-18/07, provado ao vivo);
2. o 0x08 mandado DENTRO da janela de ~3,4 s pós-conexão TRAVOU a barra, 7 de 7
   (`LIGHTBAR-BT-CULPADO-01`, 03/08) — e por isso ele foi removido em `108b711`;
3. o 0x08 mandado FORA dessa janela **não travou** (controle negativo da MESMA
   sprint).

CORREÇÃO DATADA (11/08/2026), porque o item 3 tinha uma cauda FALSA
==================================================================
Colada ao item 3 lia-se aqui "e sem 0x08 nenhum a barra ficou morta por 5 dias
e 20 adoções". Ela **nunca foi medição**: era uma frase que só existia em
docstring — a armadilha `A-12` de `docs/method/METODO-DE-ISOLAMENTO.md`, *"o
caderno envelhecer sem que ninguém note"*. A escavação do journal, em 11/08,
achou a barra **ACESA** no rádio dentro daqueles cinco dias, quatro vezes
(08/08 16:39, 08/08 21:35, 08/08 23:48 e 11/08 11:40 — ensaios
`lightbar-bt-aceso-*` em `docs/data/ensaios.csv`; a correção está registrada no
ensaio `lightbar-bt-sem-0x08-cinco-dias`).

Esta era a ÚLTIMA cópia viva da frase: `cli/cmd_lightbar_reset.py` foi corrigido
em 13/08 e serviu de molde, e `core/backend_pydualsense.py`, `cli/app.py` e
`daemon/ipc_server.py` foram corrigidos em 15/08. A correção inteira, com todos
os endereços de ensaio, está no docstring de `core/backend_pydualsense.py`
(`enviar_release_leds`).

Do que a frase afirmava, o que sobra de pé é o oposto do que ela dizia: nesses
cinco dias sem 0x08 a barra **obedeceu**, o que mantém o 0x08 fora do banco dos
réus — mas pela razão contrária. E a correlação de 03/08 (7/7 dentro da janela)
segue de pé como correlação, tendo caído como causa SUFICIENTE no ensaio
`lightbar-bt-sem-0x08-hoje-2300`.

A hipótese que concilia o que restou, e que segue sem ensaio que a feche: **o
0x08 devolve o claim, e só derruba quando é mandado em cima da conexão.** Este
arquivo não prova a hipótese — hardware não cabe em teste unitário. Ele garante
que o INSTRUMENTO usado para prová-la na bancada não minta, que é a armadilha
nº 3 desta casa: *"o instrumento pode estar brigando com o produto"*.

O QUE ESTES TESTES TRAVAM
=========================
- o report sai pelo `writeReport` do handle (sequência e CRC certos), nunca
  cru no `device` — foi assim que a cura de 17/07 morreu uma vez (RESET-03);
- o cache do nó sysfs é invalidado junto, senão a escrita de cor seguinte é
  pulada e a barra fica apagada com o produto achando que pintou;
- `uniq` restringe a UM controle — sem isso não há variável única com dois
  controles na mesa;
- e o instrumento **não vira cura por acidente**: nenhum caminho automático
  pode passar a chamá-lo sem decisão de produto.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[2]
BACKEND_PY = RAIZ / "src" / "hefesto_dualsense4unix" / "core" / "backend_pydualsense.py"


class _NoSysfsFalso:
    def __init__(self) -> None:
        self.invalidado = 0

    def invalidate_cache(self) -> None:
        self.invalidado += 1


class _HandleFalso:
    """Espelha o handle da pydualsense no que o reset usa: `writeReport`."""

    def __init__(self) -> None:
        self.reports: list[list[int]] = []

    def writeReport(self, dados: list[int]) -> None:  # noqa: N802 (API do upstream)
        self.reports.append(list(dados))


class _BackendMinimo:
    """Só o necessário para exercitar `enviar_release_leds` sem hardware."""

    enviar_release_leds = None

    def __init__(self, handles: dict[str, Any], sysfs: dict[str, Any]) -> None:
        import threading

        self._handles = handles
        self._sysfs = sysfs
        self._io_lock = threading.RLock()


def _backend(handles: dict[str, Any], sysfs: dict[str, Any]) -> Any:
    from hefesto_dualsense4unix.core.backend_pydualsense import (
        PyDualSenseController,
    )

    alvo = _BackendMinimo(handles, sysfs)
    alvo.enviar_release_leds = (  # type: ignore[assignment]
        PyDualSenseController.enviar_release_leds.__get__(alvo)
    )
    return alvo


def test_o_report_sai_pelo_write_report_do_handle() -> None:
    """RESET-03: seq/CRC por handle. Escrever cru no device já matou a cura uma vez."""
    handle = _HandleFalso()
    backend = _backend({"aa:bb": handle}, {})

    resultado = backend.enviar_release_leds()

    assert resultado == {"aa:bb": True}
    assert len(handle.reports) == 1
    report = handle.reports[0]
    assert report[0] == 0x31, "não é o report de output BT"
    assert report[4] == 0x08, "o flag de Reset LED state não está no report"


def test_o_cache_do_no_sysfs_e_invalidado_junto() -> None:
    """Sem isto, a barra fica apagada com o produto achando que já pintou."""
    no = _NoSysfsFalso()
    backend = _backend({"aa:bb": _HandleFalso()}, {"aa:bb": no})

    backend.enviar_release_leds()

    assert no.invalidado == 1


def test_uniq_restringe_a_um_controle_so() -> None:
    """Variável única: com dois controles na mesa, mandar aos dois não mede nada."""
    um, outro = _HandleFalso(), _HandleFalso()
    backend = _backend({"aa:bb": um, "cc:dd": outro}, {})

    resultado = backend.enviar_release_leds(uniq="aa:bb")

    assert resultado == {"aa:bb": True}
    assert len(um.reports) == 1
    assert outro.reports == [], "o outro controle recebeu report sem ser o alvo"


def test_sem_handle_aberto_devolve_vazio_em_vez_de_estourar() -> None:
    """"Nenhum controle aberto" é resposta, não falha."""
    backend = _backend({}, {})

    assert backend.enviar_release_leds() == {}
    assert backend.enviar_release_leds(uniq="00:00:00:00:00:00") == {}


def test_falha_de_um_handle_nao_derruba_o_outro() -> None:
    """Um controle mudo não pode calar a medição do outro."""

    class _HandleQuebrado:
        def writeReport(self, _dados: list[int]) -> None:  # noqa: N802
            raise OSError("controle sumiu do rádio")

    bom = _HandleFalso()
    backend = _backend({"ruim": _HandleQuebrado(), "bom": bom}, {})

    resultado = backend.enviar_release_leds()

    assert resultado == {"ruim": False, "bom": True}
    assert len(bom.reports) == 1


def test_o_instrumento_nao_virou_cura_por_acidente() -> None:
    """O portão que impede o 0x08 de voltar à adoção sem decisão de produto."""
    arvore = ast.parse(BACKEND_PY.read_text(encoding="utf-8"))
    donos: list[str] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.FunctionDef):
            continue
        for filho in ast.walk(no):
            if (
                isinstance(filho, ast.Call)
                and isinstance(filho.func, ast.Name)
                and filho.func.id == "send_release_leds"
            ):
                donos.append(no.name)

    assert donos == ["enviar_release_leds"], (
        f"`send_release_leds` passou a ser chamado por {donos} — se a cura está "
        "voltando ao caminho automático, isso é decisão dela (a remoção de "
        "108b711 foi deliberada), e este teste tem de ser reescrito junto com a "
        "nota datada na LIGHTBAR-BT-CULPADO-01."
    )
