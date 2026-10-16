"""O-CONTROLLERS-JSON-ILEGIVEL-NAO-SE-SOBRESCREVE-CALADO-01.

O ``controllers.json`` (a fila que dá o número a cada controle) que existe e não
se lê (truncado, bytes que não são texto, documento que não é objeto) não vale
como ausente, nos DOIS donos dele (DualSense e externos): a carga avisa no
diário (``identidade_ilegivel``), e a primeira escrita guarda o original ao lado
(``controllers.json.ilegivel-<data>``) antes de gravar a fila nova. O arquivo
ausente continua sendo o começo limpo, sem aviso, e o de OUTRA versão do schema
(legível) continua sendo descartado como antes.

Tudo num ``config_dir`` de mentira em ``tmp_path``.
"""
from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.daemon.subsystems import external_identity as ei_mod
from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod
from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
    ExternalIdentityRegistry,
)
from hefesto_dualsense4unix.daemon.subsystems.identity import (
    CONTROLLERS_SCHEMA_VERSION,
    SUFIXO_DO_ILEGIVEL,
    ControllerIdentityRegistry,
)

DS_1 = "aabbcc000001"
DS_2 = "aabbcc000002"
DS_3 = "aabbcc000003"
EXT_1 = "aabbcc0000fe"
EXT_2 = "aabbcc0000ff"
BOOT = "boot-teste-ilegivel"


@pytest.fixture
def casa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """O ``config_dir`` de mentira, com a guarda que sai se ele escapar do tmp."""
    from hefesto_dualsense4unix.utils import xdg_paths

    alvo = tmp_path / "config"

    def _config_dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(xdg_paths, "config_dir", _config_dir)
    monkeypatch.setattr(id_mod, "_read_boot_id", lambda: BOOT)
    monkeypatch.setattr(ei_mod, "_read_boot_id", lambda: BOOT)
    for dono in (ControllerIdentityRegistry, ExternalIdentityRegistry):
        if not str(dono._path()).startswith(str(tmp_path)):
            pytest.exit("a régua ia escrever no config_dir de verdade", returncode=3)
    return alvo


def _arquivo(casa: Path) -> Path:
    return casa / "controllers.json"


def _guardados(casa: Path) -> list[Path]:
    return sorted(p for p in casa.iterdir() if SUFIXO_DO_ILEGIVEL in p.name)


def _avisos(logs: Iterable[Mapping[str, Any]]) -> list[Any]:
    return [e["event"] for e in logs if e.get("log_level") == "warning"]


def _fila_no_disco(casa: Path, kind: str) -> dict[str, int]:
    doc = json.loads(_arquivo(casa).read_text(encoding="utf-8"))
    return {
        str(e["addr"]): int(e["rank"])
        for e in doc[id_mod.ORDER_FIELD]
        if isinstance(e, dict) and e.get("kind") == kind
    }


def _dualsense_grava(uniq: str) -> ControllerIdentityRegistry:
    r = ControllerIdentityRegistry()
    r.load()
    r.slot_for(uniq)
    r.sync_connected({uniq})
    return r


def _externo_grava(uniq: str) -> ExternalIdentityRegistry:
    r = ExternalIdentityRegistry()
    r.load()
    r.slot_for(uniq)
    r.sync_connected({uniq})
    return r


#: (rótulo, quem grava, o tipo que ele guarda na fila, o primeiro e o segundo controle)
DONOS: list[tuple[str, Callable[[str], Any], str, str, str]] = [
    ("dualsense", _dualsense_grava, id_mod.KIND_DUALSENSE, DS_1, DS_2),
    ("externos", _externo_grava, id_mod.KIND_EXTERNAL, EXT_1, EXT_2),
]
DONO_IDS = [d[0] for d in DONOS]


def _a_escrita_seguinte(
    casa: Path, grava: Callable[[str], Any], uniq: str
) -> list[Any]:
    with structlog.testing.capture_logs() as logs:
        grava(uniq)
    return _avisos(logs)


@pytest.mark.parametrize("dono", DONOS, ids=DONO_IDS)
def test_o_arquivo_truncado_avisa_e_o_original_fica_guardado_ao_lado(
    casa: Path, dono: tuple[str, Callable[[str], Any], str, str, str]
) -> None:
    # D-1610-O-CONTROLLERS-JSON-ILEGIVEL-VAI-PARA-O-LADO
    rotulo, grava, kind, primeiro, segundo = dono
    grava(primeiro)
    inteiro = _arquivo(casa).read_text(encoding="utf-8")
    truncado = inteiro[: len(inteiro) // 2]
    _arquivo(casa).write_text(truncado, encoding="utf-8")

    avisos = _a_escrita_seguinte(casa, grava, segundo)

    assert "identidade_ilegivel" in avisos, f"[{rotulo}] a carga não avisou: {avisos}"
    assert "identidade_ilegivel_guardado" in avisos, f"[{rotulo}] a escrita não avisou: {avisos}"
    guardados = _guardados(casa)
    assert len(guardados) == 1, (
        f"[{rotulo}] o original não ficou ao lado: {sorted(p.name for p in casa.iterdir())}"
    )
    assert guardados[0].name.startswith("controllers.json.ilegivel-")
    assert guardados[0].read_text(encoding="utf-8") == truncado, "o original mudou ao ser guardado"
    assert _fila_no_disco(casa, kind) == {segundo: 1}, (
        f"[{rotulo}] a fila nova não foi gravada"
    )


@pytest.mark.parametrize("dono", DONOS, ids=DONO_IDS)
@pytest.mark.parametrize(
    "bytes_ilegiveis",
    [b'["aabbcc000001", "dualsense"]', b"\xff\xfe\x00{", b"", b"null"],
    ids=["documento-lista", "bytes-sem-texto", "vazio", "null"],
)
def test_documento_que_nao_e_objeto_ou_nao_e_texto_fica_guardado(
    casa: Path,
    dono: tuple[str, Callable[[str], Any], str, str, str],
    bytes_ilegiveis: bytes,
) -> None:
    _rotulo, grava, kind, primeiro, _segundo = dono
    casa.mkdir(parents=True, exist_ok=True)
    _arquivo(casa).write_bytes(bytes_ilegiveis)

    avisos = _a_escrita_seguinte(casa, grava, primeiro)

    assert "identidade_ilegivel" in avisos
    assert [g.read_bytes() for g in _guardados(casa)] == [bytes_ilegiveis]
    assert _fila_no_disco(casa, kind) == {primeiro: 1}


@pytest.mark.parametrize("dono", DONOS, ids=DONO_IDS)
def test_dois_ilegiveis_no_mesmo_segundo_nao_se_apagam(
    casa: Path,
    monkeypatch: pytest.MonkeyPatch,
    dono: tuple[str, Callable[[str], Any], str, str, str],
) -> None:
    _rotulo, grava, _kind, primeiro, _segundo = dono
    monkeypatch.setattr("time.strftime", lambda _fmt: "20261016-120000")
    casa.mkdir(parents=True, exist_ok=True)
    for conteudo in ("{um", "{dois"):
        _arquivo(casa).write_text(conteudo, encoding="utf-8")
        grava(primeiro)

    assert sorted(g.read_text(encoding="utf-8") for g in _guardados(casa)) == ["{dois", "{um"]


@pytest.mark.parametrize("dono", DONOS, ids=DONO_IDS)
def test_sem_poder_guardar_o_ilegivel_nada_se_escreve(
    casa: Path,
    monkeypatch: pytest.MonkeyPatch,
    dono: tuple[str, Callable[[str], Any], str, str, str],
) -> None:
    _rotulo, grava, _kind, primeiro, _segundo = dono
    casa.mkdir(parents=True, exist_ok=True)
    _arquivo(casa).write_text("{quebrado", encoding="utf-8")

    def _recusa(_caminho: Path) -> Path:
        raise PermissionError("somente leitura")

    monkeypatch.setattr(id_mod, "guardar_a_fila_ilegivel", _recusa)
    avisos = _a_escrita_seguinte(casa, grava, primeiro)

    assert "identidade_ilegivel_nao_guardado" in avisos
    assert _arquivo(casa).read_text(encoding="utf-8") == "{quebrado"
    assert _guardados(casa) == []


@pytest.mark.parametrize("dono", DONOS, ids=DONO_IDS)
def test_o_arquivo_ausente_e_o_comeco_limpo_sem_aviso(
    casa: Path, dono: tuple[str, Callable[[str], Any], str, str, str]
) -> None:
    _rotulo, grava, kind, primeiro, _segundo = dono

    avisos = _a_escrita_seguinte(casa, grava, primeiro)

    assert avisos == []
    assert _guardados(casa) == []
    assert _fila_no_disco(casa, kind) == {primeiro: 1}


@pytest.mark.parametrize("dono", DONOS, ids=DONO_IDS)
def test_o_arquivo_legivel_de_outra_versao_segue_descartado_sem_guardar(
    casa: Path, dono: tuple[str, Callable[[str], Any], str, str, str]
) -> None:
    """O que já funcionava: schema velho legível não é ilegível, é descartado."""
    _rotulo, grava, kind, primeiro, _segundo = dono
    casa.mkdir(parents=True, exist_ok=True)
    _arquivo(casa).write_text(
        json.dumps({"version": CONTROLLERS_SCHEMA_VERSION - 1, "slots": {DS_3: 1}}),
        encoding="utf-8",
    )

    avisos = _a_escrita_seguinte(casa, grava, primeiro)

    assert "identidade_ilegivel" not in avisos
    assert _guardados(casa) == []
    assert _fila_no_disco(casa, kind) == {primeiro: 1}


def test_a_fila_legivel_dos_dois_lados_segue_intacta_entre_os_donos(casa: Path) -> None:
    """O que já funcionava: cada dono preserva a fatia do outro no mesmo arquivo."""
    _dualsense_grava(DS_1)
    externo = ExternalIdentityRegistry()
    externo.load()
    externo.slot_for(EXT_1, reserve=1)
    externo.sync_connected({EXT_1})

    assert _fila_no_disco(casa, id_mod.KIND_DUALSENSE) == {DS_1: 1}
    assert _fila_no_disco(casa, id_mod.KIND_EXTERNAL) == {EXT_1: 2}
    assert _guardados(casa) == []


def test_o_ilegivel_guardado_e_memoria_de_controle_que_o_esquecer_leva(casa: Path) -> None:
    """A cópia guarda os endereços dos controles: o «esquecer» tem de achá-la."""
    from fnmatch import fnmatch

    from hefesto_dualsense4unix.utils import memoria_dos_controles as m

    casa.mkdir(parents=True, exist_ok=True)
    _arquivo(casa).write_text('{"version": 3, "order": [{"addr": "aabbcc0000', encoding="utf-8")
    _dualsense_grava(DS_1)
    (guardado,) = _guardados(casa)

    relativo = f"{m.SLUG}/{guardado.name}"
    donos = [lg for lg in m.lugares(m.CONTROLES) if fnmatch(relativo, lg.caminho)]
    assert donos, f"«{relativo}» guarda endereço de controle e não está no inventário"
    assert all(lg.raiz == "config" and lg.ato == m.MOVER for lg in donos)
