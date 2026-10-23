"""A marca do Parar da aba Sistema: o serviço que ela parou segue parado quando a janela reabre.

Dono único da marca. Quem a grava ou apaga é a lógica (a aba Sistema e a bandeja); quem a lê é a
entrada que abre a janela (`interface/abrir.trazer_o_servico`). Mora aqui, e não na entrada da
janela, para a lógica não importar a moldura: a bandeja que importava `interface.abrir` só para
isto arrastava o WebKit para o fecho de quem a importa
(A-LISTA-DO-WEBKIT-DA-SUITE-VOLTA-AO-TAMANHO-REAL-01).
"""
from __future__ import annotations

import contextlib
from pathlib import Path

from hefesto_dualsense4unix.utils.xdg_paths import runtime_dir

#: O Parar da aba Sistema deixa esta marca no runtime da sessão, e abrir a janela a respeita.
MARCA_DO_PARAR = "servico-parado-pela-aba-sistema"


def marca_do_parar() -> Path:
    """Onde mora a marca do Parar: no runtime da sessão, que o logout limpa."""
    return runtime_dir() / MARCA_DO_PARAR


def lembrar_o_parar(parado: bool) -> None:
    """Grava (o Parar da aba Sistema) ou apaga (o serviço que volta, o «Sair») a marca."""
    marca = marca_do_parar()
    with contextlib.suppress(OSError):
        if parado:
            marca.parent.mkdir(parents=True, exist_ok=True)
            marca.touch()
        else:
            marca.unlink(missing_ok=True)
