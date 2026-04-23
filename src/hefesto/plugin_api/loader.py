"""Loader de plugins — importa arquivos .py arbitrarios de um diretório.

Usa importlib.util para carregar cada arquivo como modulo independente,
sem adicionar o diretório ao sys.path de forma permanente. Cada arquivo
deve conter exatamente uma subclasse de Plugin (a primeira encontrada
e instanciada).

Comportamento de falha:
  - ImportError / SyntaxError no arquivo: skip com log warning.
  - Nenhuma subclasse de Plugin encontrada: skip com log warning.
  - Multiplas subclasses no mesmo arquivo: a primeira e usada.
  - Excecao no construtor (__init__): skip com log warning.
"""
from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path

from hefesto.utils.logging_config import get_logger

logger = get_logger(__name__)


def load_plugins_from_dir(path: Path) -> list:
    """Carrega plugins de todos os arquivos .py em `path`.

    Args:
        path: diretório com arquivos .py de plugins.

    Returns:
        Lista de instancias de Plugin carregadas com sucesso.
        Arquivos invalidos sao ignorados (log warning).
    """
    from hefesto.plugin_api.plugin import Plugin

    if not path.exists():
        logger.info("plugins_dir_nao_existe", path=str(path))
        return []

    if not path.is_dir():
        logger.warning("plugins_path_nao_eh_diretorio", path=str(path))
        return []

    instancias: list[Plugin] = []

    for arquivo in sorted(path.glob("*.py")):
        if arquivo.name.startswith("_"):
            continue

        plugin = _carregar_arquivo(arquivo)
        if plugin is not None:
            instancias.append(plugin)

    logger.info("plugins_carregados", total=len(instancias))
    return instancias


def _carregar_arquivo(arquivo: Path) -> object | None:
    """Importa um arquivo .py e instancia a primeira subclasse de Plugin."""
    from hefesto.plugin_api.plugin import Plugin

    modulo_nome = f"hefesto_plugin_{arquivo.stem}"

    try:
        spec = importlib.util.spec_from_file_location(modulo_nome, arquivo)
        if spec is None or spec.loader is None:
            logger.warning("plugin_spec_invalido", arquivo=str(arquivo))
            return None

        modulo = importlib.util.module_from_spec(spec)
        sys.modules[modulo_nome] = modulo
        spec.loader.exec_module(modulo)  # type: ignore[union-attr]
    except Exception as exc:
        logger.warning(
            "plugin_import_falhou",
            arquivo=str(arquivo),
            erro=str(exc),
        )
        return None

    # Encontrar a primeira subclasse concreta de Plugin no modulo.
    classes = [
        obj
        for _, obj in inspect.getmembers(modulo, inspect.isclass)
        if issubclass(obj, Plugin) and obj is not Plugin and not inspect.isabstract(obj)
    ]

    if not classes:
        logger.warning("plugin_sem_subclasse", arquivo=str(arquivo))
        return None

    cls = classes[0]

    if not hasattr(cls, "name") or not cls.name:
        logger.warning("plugin_sem_name", arquivo=str(arquivo), cls=cls.__name__)
        return None

    try:
        instancia = cls()
    except Exception as exc:
        logger.warning(
            "plugin_construtor_falhou",
            arquivo=str(arquivo),
            cls=cls.__name__,
            erro=str(exc),
        )
        return None

    logger.info("plugin_carregado", name=instancia.name, arquivo=str(arquivo))
    return instancia


__all__ = ["load_plugins_from_dir"]
