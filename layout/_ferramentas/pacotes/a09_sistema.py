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
    """As linhas de estado da aba Sistema, com os nomes que a página tem.

    CADA CHAVE É UM `data-campo` do `09-sistema.html`, e eles saem do mesmo
    `ident` que a linha já usava no `data-id`. Até 01/09/2026 esta aba emitia
    oito valores e a página não tinha um só lugar onde pô-los: a `est()` marcava
    a LINHA e não o VALOR, e a pintura escrevia zero sem uma linha de erro.
    """
    st = ctx.state
    jan = {k[len("window_detect_"):]: v for k, v in st.items()
           if k.startswith("window_detect_")}
    n = len(ctx.conectados)
    return {
        # AS LINHAS DE ESTADO, na língua da tela. A regra da maiúscula é a que
        # a `aba09.est` documenta: valor de campo é uma RESPOSTA, e começa
        # maiúsculo.
        "hefesto-estado": "Parado" if st.get("paused") else "Ligado",
        "hefesto-pausa": "Sim, e volta pausado" if st.get("paused") else "Não",
        "hefesto-troca-de-perfil": ("Ligado" if st.get("window_detect_healthy")
                                    else "Sem detector de janela"),
        "hefesto-ambiente": st.get("window_detect_backend") or "—",
        "bateria-impoe": ("Nada é limitado" if not st.get("emulation_suppressed")
                          else "A emulação está contida"),
        # A FRASE CONTA OS CONECTADOS, nunca a mesa: nomear um controle que não
        # está foi o defeito que apareceu cinco vezes nesta casa, e esta linha
        # ("Os 4 controles") foi uma delas.
        "bateria-vale-para": f"O {n} controle" if n == 1 else f"Os {n} controles",
        # O resto continua saindo, para quem consome o pacote fora da tela.
        "versao": _versao(),
        "controles": n,
        "coop": bool(st.get("coop")),
        "steam-input": bool(st.get("steam_input")),
        "modo-nativo": bool(st.get("native_mode")),
        "nativo-origem": st.get("native_mode_origin") or "",
        "janela": jan,
        "janela-saudavel": bool(st.get("window_detect_healthy")),
        "consertos": {
            "motivo": st.get("window_detect_reason") or "",
            "jogo": st.get("window_detect_current_class") or "",
            "backend": st.get("window_detect_backend") or "",
        },
        "sem_dono": {k: {"sem_dono": True, "oque": v} for k, v in SEM_DONO.items()},
        "cobertura": {"pintados": 12 + len(jan), "sem_dono": len(SEM_DONO)},
    }
