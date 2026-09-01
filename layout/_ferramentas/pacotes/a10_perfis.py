#!/usr/bin/env python3
"""O pacote da aba `10` Perfis.

ESTA ABA JÁ ESTAVA MARCADA, e não por mim: o outro agente pôs **77 endereços**
(`data-hef`) e 11 gestos nela em 31/08, com um esquema de nomes próprio. Os dois
convivem — o nome do atributo não é o contrato; o contrato é este despachante.

O QUE TEM DONO: o perfil em vigor (`active_profile`) e o travamento do
autoswitch (`autoswitch_locked`), que é o que diz se a troca automática está
segurada.

O QUE NÃO TEM: a LISTA de perfis e o conteúdo de cada um. Eles vivem em disco e
chegam por `profiles.*` no IPC — outro caminho, que esta aba ainda não abriu.
"""
from __future__ import annotations

from . import Contexto, perfil, registrar

#: CORRIGIDO EM 01/09/2026. Estava escrito que a lista "vem de `profiles.*`, não
#: do state_full" — e daí eu concluí que não tinha dono. `profile.list` é um
#: método vivo do daemon e responde agora; os 33 perfis dela estão em disco, em
#: `profiles_dir()`. Ter outro dono que não o `state_full` não é não ter dono.
SEM_DONO: dict[str, str] = {}


@registrar("10-perfis.html")
def pacote(ctx: Contexto) -> dict:
    st = ctx.state
    ativo = str(st.get("active_profile") or "")
    todos = perfil.lista()
    aberto = perfil.ativo(ativo)
    return {
        "ativo": ativo or "—",
        "travado": bool(st.get("autoswitch_locked")),
        "jogo": st.get("jogo_steam") or "",
        # A LISTA INTEIRA, ordenada como a tela mostra: prioridade primeiro,
        # que é a ordem em que o produto resolve o casamento.
        "lista": sorted(todos, key=lambda x: (-x["prioridade"], x["nome"])),
        "quantos": len(todos),
        # O QUE O PERFIL ABERTO GUARDA — é o que o editor da aba mostra.
        "editor": {
            "gatilhos": bool(aberto.get("triggers")),
            "leds": bool(aberto.get("leds")),
            "rumble": bool(aberto.get("rumble")),
            "mouse": bool(aberto.get("mouse")),
            "prioridade": aberto.get("priority"),
            "casamento": (aberto.get("match") or {}).get("type", ""),
        } if aberto else {},
        "sem_dono": {},
        "cobertura": {"pintados": 5 + len(todos), "sem_dono": len(SEM_DONO)},
    }
