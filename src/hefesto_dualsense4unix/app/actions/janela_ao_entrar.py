"""A escolha «Abrir a janela ao entrar»: a unit de usuário que abre a janela quando a sessão começa.

A escolha mora no systemd de usuário, no link da unit em `graphical-session.target.wants`. A leitura
olha o link da conta e os do sistema, sem subprocesso; a mudança é `systemctl --user enable` ou
`disable`. Sem a unit em pasta nenhuma do systemd, ligar a copia do modelo da instalação. As pastas
são as que `daemon/service_install.py` declara.
"""
from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.utils.repo_files import como_atualizar_esta_instalacao
from hefesto_dualsense4unix.utils.units_de_usuario import UNIT_DA_JANELA_AO_ENTRAR

ALVO_DA_SESSAO = "graphical-session.target"
PRAZO_DO_SYSTEMCTL_S = 10.0
NAO_MUDOU = "Não consegui mudar a abertura da janela ao entrar"


def _pastas_do_systemd() -> list[Path]:
    """As pastas de unit do systemd de usuário, a da conta primeiro."""
    from hefesto_dualsense4unix.daemon import service_install

    return [service_install.user_unit_dir(), *service_install.SYSTEM_UNIT_DIRS]


def pasta_do_usuario() -> Path:
    """Onde o systemd de usuário guarda as units e os links desta conta."""
    return _pastas_do_systemd()[0]


def links_da_escolha() -> list[Path]:
    """Os links que prendem a unit ao início da sessão: o da conta e os do sistema."""
    return [pasta / f"{ALVO_DA_SESSAO}.wants" / UNIT_DA_JANELA_AO_ENTRAR
            for pasta in _pastas_do_systemd()]


def ligada() -> bool:
    """`True` quando a janela abre sozinha no início da sessão."""
    return any(os.path.lexists(link) for link in links_da_escolha())


def instalada() -> bool:
    """`True` quando o systemd de usuário acha a unit em alguma das pastas dele."""
    return any((pasta / UNIT_DA_JANELA_AO_ENTRAR).is_file() for pasta in _pastas_do_systemd())


def _copiar_o_modelo() -> None:
    from hefesto_dualsense4unix.utils.repo_files import encontrar_arquivo_do_repo

    fonte = encontrar_arquivo_do_repo(f"assets/{UNIT_DA_JANELA_AO_ENTRAR}")
    if fonte is None:
        raise RuntimeError(
            "Não achei o modelo da abertura da janela nesta instalação; "
            f"{como_atualizar_esta_instalacao()}.")
    alvo = pasta_do_usuario() / UNIT_DA_JANELA_AO_ENTRAR
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(fonte.read_text(encoding="utf-8"), encoding="utf-8")


def escolher_a_janela_ao_entrar(ligar: bool, rodar: Callable[..., Any] = subprocess.run) -> None:
    """A chave «Abrir a janela ao entrar»: liga ou desliga a unit e confere que a escolha pegou.

    Levanta `RuntimeError` com a frase da recusa quando o systemd não responde, recusa ou deixa a
    escolha como estava.
    """
    passos = [["enable" if ligar else "disable", UNIT_DA_JANELA_AO_ENTRAR]]
    try:
        if ligar and not instalada():
            _copiar_o_modelo()
            passos.insert(0, ["daemon-reload"])
        for passo in passos:
            feito = rodar(["systemctl", "--user", *passo], capture_output=True, text=True,
                          timeout=PRAZO_DO_SYSTEMCTL_S)
            if feito.returncode != 0:
                detalhe = str(feito.stderr or "").strip()
                raise RuntimeError(f"{NAO_MUDOU}{f': {detalhe}' if detalhe else '.'}")
    except (OSError, subprocess.SubprocessError) as erro:
        raise RuntimeError(f"{NAO_MUDOU}: {erro}.") from erro
    if ligada() is not ligar:
        raise RuntimeError(f"{NAO_MUDOU}.")
