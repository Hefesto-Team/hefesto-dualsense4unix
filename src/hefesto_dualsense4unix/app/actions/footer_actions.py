"""Handlers do rodapé global: Aplicar, Salvar Perfil, Importar, Restaurar Default."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.profiles.loader import (
    ARQUIVO_ANTIGO_DO_PADRAO,
    ARQUIVO_DO_PADRAO,
    ARQUIVO_DO_PERSONALIZADO,
    NOME_DO_PADRAO,
    _seed_source_file,
)
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


def frase_do_preset_ausente() -> str:
    """A recusa do "Restaurar de fábrica" quando não há preset em lugar nenhum."""
    return _(
        "Não encontrei o perfil de fábrica instalado nesta máquina — sem ele "
        "não há para onde voltar."
    )


def frase_do_restauro(caminho: object = None) -> str:
    """O recibo do "Restaurar de fábrica", com o destino quando há um a dizer."""
    if caminho:
        return _("Pronto — o perfil {nome} voltou ao de fábrica ({destino}).").format(
            nome=NOME_DO_PADRAO, destino=caminho
        )
    return _("Pronto — o perfil {nome} voltou ao de fábrica.").format(
        nome=NOME_DO_PADRAO
    )


def _meu_perfil_asset() -> Path | None:
    """Acha o preset do perfil padrão; ``None`` quando não há em lugar nenhum."""
    return (_seed_source_file(ARQUIVO_DO_PADRAO) or _seed_source_file(
        ARQUIVO_DO_PERSONALIZADO) or _seed_source_file(ARQUIVO_ANTIGO_DO_PADRAO))


_NOMES_DE_SECAO: dict[str, str] = {
    "leds": "luzes",
    "triggers": "gatilhos",
    "rumble": "vibração",
    "mouse": "mouse",
    "keyboard": "teclado",
    "mic": "microfone",
    "speaker": "alto-falante",
    "controllers": "ajustes por controle",
}

_MAX_SECOES_NO_TEXTO = 3


# (`_aplicar_escolha_pendente`) para medir a paridade de IPC entre a Início e a


def _rotulo_do_modo(escolha: dict[str, str]) -> str:
    """"Jogar pelo Hefesto (Xbox 360)" a partir de ``{"modo","mascara"}``."""
    from hefesto_dualsense4unix.app.actions.home_actions import (
        _flavor_label,
        _mode_label,
    )

    alvo = _mode_label(escolha.get("modo"))
    mascara = escolha.get("mascara")
    if mascara:
        alvo = f"{alvo} ({_flavor_label(mascara)})"
    return alvo


def _lista_de_secoes(secoes: Any) -> str:
    """Nomes legíveis das seções, curtos o bastante para a statusbar."""
    if isinstance(secoes, dict):
        chaves: list[Any] = list(secoes)
    elif isinstance(secoes, list):
        chaves = list(secoes)
    else:
        return ""
    nomes = [_(_NOMES_DE_SECAO.get(str(s), str(s))) for s in chaves]
    if not nomes:
        return ""
    if len(nomes) > _MAX_SECOES_NO_TEXTO:
        return _("{primeiras} e mais {resto}").format(
            primeiras=", ".join(nomes[:_MAX_SECOES_NO_TEXTO]),
            resto=len(nomes) - _MAX_SECOES_NO_TEXTO,
        )
    return ", ".join(nomes)


def _mensagem_de_aplicacao(result: Any) -> str:
    """Texto do rodapé para o relato da ativação (``applied`` e ``failed``)."""
    if not isinstance(result, dict):
        return _("Perfil aplicado ao controle.")
    aplicadas = result.get("applied")
    if isinstance(aplicadas, list) and not aplicadas:
        return _("Nada foi aplicado ao controle.")
    nao_entraram = _lista_de_secoes(result.get("failed"))
    if nao_entraram:
        return _("Aplicado, menos: {secoes}.").format(secoes=nao_entraram)
    return _("Perfil aplicado ao controle.")


