"""Utilitários para ler e escrever preferências da GUI em JSON."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.utils import xdg_paths
from hefesto_dualsense4unix.utils.escrita_inteira import escrever_inteiro
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

_PREFS_NOME = "gui_preferences.json"


def _prefs_file() -> Path:
    """Caminho do arquivo de preferências, resolvido NA CHAMADA.

    LUZ-CEGA-01/E8 (25/08/2026) — era constante de módulo
    (``_CONFIG_DIR = xdg_paths.config_dir()``), e constante de módulo é
    avaliada na IMPORTAÇÃO. Sob a suíte isso vaza o ``$HOME`` REAL de quem
    roda: o ``tests/conftest.py`` isola ``XDG_CONFIG_HOME`` numa fixture de
    FUNÇÃO, que só corre DEPOIS da coleta — quando este módulo já congelou o
    caminho verdadeiro. Qualquer ``save_gui_prefs`` num teste escrevia em
    ``~/.config/hefesto-dualsense4unix/gui_preferences.json`` da máquina.

    É exatamente a classe de defeito que o CANARIO-FS-01 (05/08/2026)
    nomeia no próprio texto de reprovação — *"procure constante de módulo
    com Path.home() avaliada no import"* — e que aquele dia curou em
    ``storm_doctor._allowlist_path`` e ``EmulationActionsMixin._wp_dropin_dir``.
    Esta terceira passou. Em produção nada muda: ``config_dir()`` já resolve
    ``XDG_CONFIG_HOME`` a cada chamada.
    """
    return xdg_paths.config_dir() / _PREFS_NOME

_DEFAULTS: dict[str, Any] = {
    "advanced_editor": False,
    "ambiente_corrigido": None,
    "tabelas": {},
}


def _defaults() -> dict[str, Any]:
    """Uma cópia NOVA dos padrões, a cada chamada."""
    return {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v)
            for k, v in _DEFAULTS.items()}


def _copia_boa() -> Path:
    arquivo = _prefs_file()
    return arquivo.with_name(arquivo.name + ".bak")


def _ler(arquivo: Path) -> dict[str, Any] | None:
    """O dicionário do arquivo, ou `None` se ele não existe, não abre ou não é um objeto JSON."""
    try:
        data = json.loads(arquivo.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        logger.warning("gui_prefs: o arquivo não abriu como JSON", arquivo=arquivo.name,
                       erro=str(exc))
        return None
    return data if isinstance(data, dict) else None


def _por_o_torto_de_lado(arquivo: Path) -> None:
    """Tira o arquivo ilegível do caminho, com a data no nome: o que ele guardava não se perde."""
    destino = arquivo.with_name(f"{arquivo.name}.corrompido-{time.strftime('%Y%m%d-%H%M%S')}")
    try:
        os.replace(arquivo, destino)
    except OSError as exc:
        logger.warning("gui_prefs: o arquivo ilegível não saiu do lugar", erro=str(exc))
        return
    logger.warning("gui_prefs: arquivo ilegível guardado ao lado", destino=destino.name)


def load_gui_prefs() -> dict[str, Any]:
    """Carrega preferências da GUI.

    Com o arquivo ilegível, o torto vai para o lado (sufixo de data) e vale a última cópia boa,
    que também volta ao lugar; sem cópia, valem os padrões. Ler não levanta: a cópia que não
    volta ao lugar fica no diário e vale assim mesmo.
    """
    prefs_file = _prefs_file()
    if not prefs_file.exists():
        return _defaults()
    data = _ler(prefs_file)
    if data is None:
        _por_o_torto_de_lado(prefs_file)
        data = _ler(_copia_boa()) if _copia_boa().exists() else None
        if data is None:
            return _defaults()
        try:
            _escrever(prefs_file, data)
        except OSError as exc:
            logger.warning("gui_prefs: a cópia boa não voltou ao lugar", erro=str(exc))
    prefs = _defaults()
    prefs.update(data)
    return prefs


def _escrever(arquivo: Path, prefs: dict[str, Any]) -> None:
    escrever_inteiro(arquivo, json.dumps(prefs, indent=2, ensure_ascii=False))


def save_gui_prefs(prefs: dict[str, Any]) -> None:
    """Persiste preferências da GUI em disco, inteiras ou nada, e levanta `OSError` se falhar.

    O arquivo novo entra por troca atômica (`escrever_inteiro`) e a última versão boa fica numa
    cópia ao lado. Um arquivo ilegível que ainda esteja no lugar vai para o lado antes.
    """
    prefs_file = _prefs_file()
    if prefs_file.exists() and _ler(prefs_file) is None:
        _por_o_torto_de_lado(prefs_file)
    _escrever(prefs_file, prefs)
    _escrever(_copia_boa(), prefs)


def set_pref(key: str, value: Any) -> None:
    """Atalho: carrega, atualiza uma chave e salva.

    Quem chama é a memória da rota de som, uma conveniência: a gravação que falha fica no diário
    e não derruba a troca de saída.
    """
    prefs = load_gui_prefs()
    prefs[key] = value
    try:
        save_gui_prefs(prefs)
    except OSError as exc:
        logger.warning("gui_prefs: falha ao salvar preferencias", erro=str(exc))


_TABELAS = "tabelas"

PISO_DA_COLUNA = 48

TETO_DA_COLUNA = 900


def _tabelas() -> dict[str, Any]:
    bruto = load_gui_prefs().get(_TABELAS)
    return dict(bruto) if isinstance(bruto, dict) else {}


def larguras_da_tabela(tabela: str) -> dict[str, int]:
    """As larguras que o usuário deixou naquela tabela — `{coluna: px}`."""
    bruto = _tabelas().get(tabela) or {}
    larguras = bruto.get("larguras") if isinstance(bruto, dict) else None
    if not isinstance(larguras, dict):
        return {}
    limpas: dict[str, int] = {}
    for coluna, px in larguras.items():
        try:
            valor = int(px)
        except (TypeError, ValueError):
            continue
        limpas[str(coluna)] = max(PISO_DA_COLUNA, min(TETO_DA_COLUNA, valor))
    return limpas


def guardar_largura_de_coluna(tabela: str, coluna: str, px: int) -> int:
    """Grava a largura de UMA coluna e devolve o que foi realmente gravado."""
    valor = max(PISO_DA_COLUNA, min(TETO_DA_COLUNA, int(px)))
    prefs = load_gui_prefs()
    tabelas = dict(prefs.get(_TABELAS) or {})
    desta = dict(tabelas.get(tabela) or {})
    larguras = dict(desta.get("larguras") or {})
    larguras[str(coluna)] = valor
    desta["larguras"] = larguras
    tabelas[str(tabela)] = desta
    prefs[_TABELAS] = tabelas
    save_gui_prefs(prefs)
    return valor


def ordem_da_tabela(tabela: str) -> tuple[str, str]:
    """Por qual coluna aquela tabela está ordenada, e para onde."""
    bruto = _tabelas().get(tabela) or {}
    ordem = bruto.get("ordem") if isinstance(bruto, dict) else None
    if not isinstance(ordem, dict):
        return ("", "")
    coluna = str(ordem.get("coluna") or "")
    sentido = str(ordem.get("sentido") or "")
    return (coluna, sentido if sentido in ("asc", "desc") else "asc")


def guardar_ordem_da_tabela(tabela: str, coluna: str, sentido: str) -> None:
    """Grava a coluna e o sentido. Coluna vazia APAGA a escolha."""
    prefs = load_gui_prefs()
    tabelas = dict(prefs.get(_TABELAS) or {})
    desta = dict(tabelas.get(tabela) or {})
    if not coluna:
        desta.pop("ordem", None)
    else:
        desta["ordem"] = {"coluna": str(coluna),
                          "sentido": "desc" if sentido == "desc" else "asc"}
    tabelas[str(tabela)] = desta
    prefs[_TABELAS] = tabelas
    save_gui_prefs(prefs)


_ADAPTADORES_DE_ANTES = "adaptadores"


def a_ordem_dos_adaptadores_de_antes() -> list[str]:
    """A lista que o usuário deixou aqui antes de 28/09 — chaves de lugar (ou o"""
    bruto = load_gui_prefs().get(_ADAPTADORES_DE_ANTES)
    if not isinstance(bruto, list):
        return []
    vistas: list[str] = []
    for chave in bruto:
        if isinstance(chave, str) and chave and chave not in vistas:
            vistas.append(chave)
    return vistas


def esquecer_a_ordem_dos_adaptadores_de_antes() -> None:
    """Tira a lista de antes do arquivo — chamada depois que o dono a gravou."""
    prefs = load_gui_prefs()
    if _ADAPTADORES_DE_ANTES in prefs:
        del prefs[_ADAPTADORES_DE_ANTES]
        save_gui_prefs(prefs)
