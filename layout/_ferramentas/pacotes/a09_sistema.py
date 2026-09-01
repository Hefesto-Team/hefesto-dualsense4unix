#!/usr/bin/env python3
"""O pacote da aba `09` Sistema.

O QUE TEM DONO: o serviço está de pé (o daemon respondeu — se ele calasse, não
haveria pacote), o perfil ativo, a política de bateria (`rumble_policy`, que é o
mesmo dado do Perfil de Bateria desta aba) e quantos controles ela alcança.

O ALCANCE É A LINHA QUE MAIS ERRA, e errou hoje: ela dizia *"Os 4 controles"*
com dois na mesa. Aqui ele sai de `conectados`, e a régua da aba o cobra.

O QUE NÃO TEM: as versões, os plugins e o estado dos consertos automáticos —
tudo isso é do `doctor` e do instalador, não do `state_full`.
"""
from __future__ import annotations

from . import Contexto, perfil, registrar

#: CORRIGIDO EM 01/09/2026. "versoes" e "consertos" tinham dono e viraram
#: pintura. **"plugins" continua sem dono NA TELA, e a razão não é minha** — a
#: `gui/aba_sistema.py:95` já a tinha medido e escrito:
#:
#:     "IPC `plugin.list`/`plugin.reload`. Só a CLI chama
#:      (`cli/cmd_plugin.py`). Não há botão no produto de hoje."
#:
#: O método existe no daemon; o que não existe é quem o chame fora do terminal.
#: Este é o `sem_dono` legítimo desta casa: um valor que a tela mostraria como
#: se funcionasse, e que ninguém atende.
SEM_DONO: dict[str, str] = {
    "plugins": "o IPC `plugin.list` existe e só a CLI o chama — não há botão no "
               "produto de hoje (medido em `gui/aba_sistema.py:95`)",
}


def _versao() -> str:
    try:
        perfil._com_o_src()
        import hefesto_dualsense4unix as h

        return str(getattr(h, "__version__", "") or "")
    except Exception:
        return ""


@registrar("09-sistema.html")
def pacote(ctx: Contexto) -> dict:
    st = ctx.state
    jan = {k[len("window_detect_"):]: v for k, v in st.items()
           if k.startswith("window_detect_")}
    return {
        "versao": _versao(),
        "pausado": bool(st.get("paused")),
        "perfil": st.get("active_profile") or "—",
        "controles": len(ctx.conectados),
        "coop": bool(st.get("coop")),
        "steam-input": bool(st.get("steam_input")),
        "modo-nativo": bool(st.get("native_mode")),
        "nativo-origem": st.get("native_mode_origin") or "",
        # A JANELA: o detector é o que diz se a troca de perfil por jogo
        # funciona. `healthy` falso com `reason` preenchido é o conserto que a
        # aba oferece — e é o que o botão "Refazer os consertos" ataca.
        "janela": jan,
        "janela-saudavel": bool(st.get("window_detect_healthy")),
        "consertos": {
            "motivo": st.get("window_detect_reason") or "",
            "jogo": st.get("window_detect_current_class") or "",
            "backend": st.get("window_detect_backend") or "",
        },
        "sem_dono": {k: {"sem_dono": True, "oque": v} for k, v in SEM_DONO.items()},
        "cobertura": {"pintados": 10 + len(jan), "sem_dono": len(SEM_DONO)},
    }
