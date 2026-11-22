"""O perfil do Minecraft Dungeons II passa ao Modo imersão uma vez, com cópia antes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.profiles.schema import MODO_PERSONALIZADO, Profile
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

CRITERIO_DO_JOGO = "steam_app_1912410"
MODO_DA_EXTENSAO = "extensao:imersao"  # (noqa-acento)
SECOES = ("triggers", "leds", "rumble")
SUFIXO_DA_COPIA = ".antes-do-modo-imersao"
MARCA = ".o_jogo_passou_ao_modo_da_extensao"
ORIGEM = "migracao-ao-modo-da-extensao"


def _nomeia_o_jogo(dados: dict[str, Any]) -> bool:
    """O critério do perfil nomeia o jogo, sem caixa; o nome do arquivo não conta."""
    from hefesto_dualsense4unix.profiles import loader

    alvo = CRITERIO_DO_JOGO.casefold()
    return any(c.casefold() == alvo for c in loader._classes_do_match(dados))


def _secoes_em_personalizado(dados: dict[str, Any]) -> list[str]:
    """As seções cujo `modo` ESCRITO é o personalizado; a ausência de `modo` não conta."""
    return [
        secao for secao in SECOES
        if isinstance(dados.get(secao), dict) and dados[secao].get("modo") == MODO_PERSONALIZADO
    ]


def _passar_o_perfil(caminho: Path, dados: dict[str, Any]) -> list[str] | None:
    """Passa as seções de UM perfil e devolve quais passaram.

    ``None`` quando nada precisa passar (perfil torto, nome fora do arquivo ou nenhuma seção em
    personalizado). Levanta ``OSError`` ou ``ValueError`` quando a cópia ou a gravação falha: a
    passada inteira se tenta no próximo arranque.
    """
    from hefesto_dualsense4unix.profiles import loader

    secoes = _secoes_em_personalizado(dados)
    if not secoes:
        return None
    novos: dict[str, Any] = json.loads(json.dumps(dados))
    for secao in secoes:
        novos[secao]["modo"] = MODO_DA_EXTENSAO
    try:
        perfil = Profile.model_validate(novos)
    except ValueError:
        logger.warning("jogo_pulou_perfil_torto", arquivo=caminho.name)
        return None
    if loader._profile_path(perfil) != caminho:
        logger.warning("jogo_nao_passou_ao_modo_da_extensao", arquivo=caminho.name,
                       err="o nome do perfil não é o do arquivo")
        return None
    copia = caminho.with_name(caminho.name + SUFIXO_DA_COPIA)
    copia.write_bytes(caminho.read_bytes())
    loader.save_profile(perfil, origem=ORIGEM)
    logger.info("perfil_passou_ao_modo_da_extensao", perfil=perfil.name, secoes=secoes,
                copia=copia.name)
    return secoes


def passar_uma_vez() -> dict[str, list[str]] | None:
    """O perfil cujo critério nomeia o Dungeons II passa ao Modo imersão, uma vez por computador.

    Só a seção de `modo` escrito personalizado passa ao modo da extensão; seção em outro modo,
    entrada de `controllers` com `modo` próprio e valores fixos guardados ficam. Antes de
    gravar, o arquivo inteiro vai byte a byte a `<arquivo>.antes-do-modo-imersao`. A marca na
    configuração nasce ao fim da primeira passada, ache ou não o perfil; a falha ao copiar ou
    gravar não a grava. Não carimba o `modificado_em` nem liga a extensão. Devolve
    `{perfil: seções}`; ``None`` quando a marca já existia.
    """
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.utils.xdg_paths import config_dir, profiles_dir

    marca = config_dir(ensure=True) / MARCA
    if marca.exists():
        return None
    passou: dict[str, list[str]] = {}
    falhou = False
    for caminho in sorted(profiles_dir(ensure=True).glob("*.json")):
        dados = loader._dados_crus_do_perfil(caminho)
        if dados is None or loader._e_copia_de_fabrica(caminho, dados):
            continue
        if not _nomeia_o_jogo(dados):
            continue
        gesto = loader.gesto_de_agora.set(None)
        try:
            secoes = _passar_o_perfil(caminho, dados)
        except Exception as exc:
            falhou = True
            logger.warning("jogo_nao_passou_ao_modo_da_extensao", arquivo=caminho.name,
                           err=str(exc)[:200])
            continue
        finally:
            loader.gesto_de_agora.reset(gesto)
        if secoes:
            passou[caminho.stem] = secoes
    if falhou:
        return passou
    try:
        marca.write_text("passada feita\n", encoding="utf-8")
    except OSError as exc:
        logger.warning("jogo_sem_marca_da_passada", err=str(exc)[:200])
    return passou


__all__ = [
    "CRITERIO_DO_JOGO",
    "MARCA",
    "MODO_DA_EXTENSAO",
    "ORIGEM",
    "SECOES",
    "SUFIXO_DA_COPIA",
    "passar_uma_vez",
]
