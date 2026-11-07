"""A porta do barramento: perguntar ao sistema não acorda nada.

Falar com um nome ativável sobe o serviço dono dele, e o serviço do Hefesto fica no ar antes da
sessão gráfica: quem nasce nessa hora nasce sem ``WAYLAND_DISPLAY``. Toda mensagem do ``jeepney`` a
um nome ativável sai por aqui; o ``scripts/check_os_contratos_de_fora.py`` reprova quem declara
contato ativável sem esta porta. O barramento de sistema, pelo Gio, tem a borda própria em
``bluez_dbus``, e toda chamada ali vai com ``NO_AUTO_START``.
"""
from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

_SYSTEMD = "org.freedesktop.systemd1"
_CAMINHO_DO_SYSTEMD = "/org/freedesktop/systemd1"
_GERENTE = "org.freedesktop.systemd1.Manager"
_DESKTOP = "XDG_CURRENT_DESKTOP"


def sem_ativar(mensagem: Any) -> Any:
    """A mensagem só chega a quem já está de pé."""
    from jeepney import MessageFlag

    mensagem.header.flags |= MessageFlag.no_auto_start
    return mensagem


def tem_o_desktop(ambiente: Sequence[str]) -> bool:
    return any(nome == _DESKTOP and valor
               for nome, _, valor in (item.partition("=") for item in ambiente))


def sessao_de_pe(conexao: Any, prazo_s: float) -> bool:
    """A sessão gráfica existe? Quem ativa é o gerente do usuário, e o ``Manager.Environment`` dele
    diz, lido sem ativar; sem ele no barramento, vale o ambiente deste processo."""
    from jeepney import DBusAddress, MessageType, Properties

    leitura = Properties(DBusAddress(_CAMINHO_DO_SYSTEMD, bus_name=_SYSTEMD,
                                     interface=_GERENTE)).get("Environment")
    resposta = conexao.send_and_get_reply(sem_ativar(leitura), timeout=prazo_s)
    if resposta.header.message_type == MessageType.error:
        return bool(os.environ.get(_DESKTOP))
    return tem_o_desktop(resposta.body[0][1])


def sessao_ainda_nao_subiu(conexao: Any, nome: str, prazo_s: float) -> bool:
    """Verdadeiro só com as duas provas: o ``nome`` sem dono (``NameHasOwner`` não ativa nada) e a
    sessão de pé negada. Com o ``NameHasOwner`` em erro, falso: o pedido segue como era."""
    from jeepney import MessageType
    from jeepney.bus_messages import message_bus

    dono = conexao.send_and_get_reply(message_bus.NameHasOwner(nome), timeout=prazo_s)
    if dono.header.message_type == MessageType.error or dono.body[0]:
        return False
    return not sessao_de_pe(conexao, prazo_s)


__all__ = ["sem_ativar", "sessao_ainda_nao_subiu", "sessao_de_pe", "tem_o_desktop"]
