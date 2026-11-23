"""O perfil do Minecraft Dungeons II passa ao Modo imersão uma vez, com cópia antes.

O identificador do jogo não mora no pacote: vem da chave ``jogo.chave`` da receita estudada
``minecraft-dungeons-ii.json`` que a extensão imersao instalada leva.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.profiles.schema import MODO_PERSONALIZADO, Profile
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

EXTENSAO = "imersao"
RECEITA_DO_JOGO = ("receitas", "estudadas", "minecraft-dungeons-ii.json")
MODO_DA_EXTENSAO = "extensao:imersao"  # (noqa-acento)
SECOES = ("triggers", "leds", "rumble")
SUFIXO_DA_COPIA = ".antes-do-modo-imersao"
MARCA = ".o_jogo_passou_ao_modo_da_extensao"
ORIGEM = "migracao-ao-modo-da-extensao"


def criterio_do_jogo() -> str | None:
    """A chave ``steam_app_<n>`` da receita do jogo na extensão instalada, sem caixa.

    ``None`` com a receita ausente, ilegível ou sem chave válida, e uma linha no diário.
    """
    from hefesto_dualsense4unix.mods.manifesto import CHAVE_DE_JOGO
    from hefesto_dualsense4unix.utils.xdg_paths import mods_codigo_dir

    receita = mods_codigo_dir().joinpath(EXTENSAO, *RECEITA_DO_JOGO)
    try:
        dados = json.loads(receita.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.info("jogo_sem_receita_da_extensao", receita=receita.name, err=str(exc)[:200])
        return None
    jogo = dados.get("jogo") if isinstance(dados, dict) else None
    chave = jogo.get("chave") if isinstance(jogo, dict) else None
    if not isinstance(chave, str) or not CHAVE_DE_JOGO.match(chave):
        logger.warning("jogo_sem_chave_na_receita", receita=receita.name)
        return None
    return chave.casefold()


def _nomeia_o_jogo(dados: dict[str, Any], alvo: str) -> bool:
    """O critério do perfil nomeia o jogo, sem caixa; o nome do arquivo não conta."""
    from hefesto_dualsense4unix.profiles import loader

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
    gravar, ou a receita do jogo ausente na extensão, não a grava. Não carimba o
    `modificado_em` nem liga a extensão. Devolve `{perfil: seções}`; ``None`` com a marca.
    """
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.utils.xdg_paths import config_dir, profiles_dir

    marca = config_dir(ensure=True) / MARCA
    if marca.exists():
        return None
    alvo = criterio_do_jogo()
    if alvo is None:
        return {}
    passou: dict[str, list[str]] = {}
    falhou = False
    for caminho in sorted(profiles_dir(ensure=True).glob("*.json")):
        dados = loader._dados_crus_do_perfil(caminho)
        if dados is None or loader._e_copia_de_fabrica(caminho, dados):
            continue
        if not _nomeia_o_jogo(dados, alvo):
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
    "EXTENSAO",
    "MARCA",
    "MODO_DA_EXTENSAO",
    "ORIGEM",
    "RECEITA_DO_JOGO",
    "SECOES",
    "SUFIXO_DA_COPIA",
    "criterio_do_jogo",
    "passar_uma_vez",
]
