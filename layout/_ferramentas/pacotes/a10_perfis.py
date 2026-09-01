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


#: COMO A TELA CHAMA O QUE O PERFIL GUARDA — `match.type` no disco, uma frase
#: na coluna "Quando usar". A tradução mora aqui e não no JS: é vocabulário do
#: produto, e o desenho dela já fixou as palavras.
QUANDO = {"criteria": "Jogo", "any": "Todos — quando nenhum casa",
          "manual": "Só quando eu escolher"}


@registrar("10-perfis.html")
def pacote(ctx: Contexto) -> dict:
    """A tabela de perfis e o editor, com os nomes que a página tem.

    ESTA ABA ENDEREÇA POR `data-hef`, e são SETENTA E SETE — `perfis.conta`,
    `perfis.linha.nome`, `editor.prioridade`. É o vocabulário do
    `perfis_vivos.py`, o piloto próprio dela, e ele continua valendo: o piloto
    único aceita os três vocabulários das dez páginas em vez de renomear 105
    endereços e quebrar cinco pilotos vivos.

    AS TRÊS COLUNAS SÃO LISTAS, e a tela as distribui pelos catorze blocos de
    mesmo endereço, na ordem. Sem isso o pacote teria de emitir
    `perfis.linha.nome-0`, `-1`… e o gerador teria de saber de antemão quantos
    perfis ela tem — que hoje são 33 no disco e catorze no desenho.
    """
    st = ctx.state
    ativo = str(st.get("active_profile") or "")
    todos = sorted(perfil.lista(), key=lambda x: (-x["prioridade"], x["nome"]))
    aberto = perfil.ativo(ativo)
    return {
        "perfis.conta": f"{len(todos)} perfis",
        "perfis.linha.nome": [p["nome"] for p in todos],
        "perfis.linha.prioridade": [p["prioridade"] for p in todos],
        "perfis.linha.quando": [QUANDO.get(p["casamento"], p["casamento"]) for p in todos],
        "editor.nome": aberto.get("name") or ativo or "—",
        "editor.prioridade": aberto.get("priority"),
        "editor.prioridade.n": aberto.get("priority"),
        "ativo": ativo or "—",
        "travado": bool(st.get("autoswitch_locked")),
        "jogo": st.get("jogo_steam") or "",
        "quantos": len(todos),
        "editor": {
            "gatilhos": bool(aberto.get("triggers")), "leds": bool(aberto.get("leds")),
            "rumble": bool(aberto.get("rumble")), "mouse": bool(aberto.get("mouse")),
            "casamento": (aberto.get("match") or {}).get("type", ""),
        } if aberto else {},
        "sem_dono": {},
        "cobertura": {"pintados": 7 + len(todos) * 3, "sem_dono": len(SEM_DONO)},
    }


# ---------------------------------------------------------------------------
# OS GESTOS — ver o exemplo comentado em `a04_iluminacao.py`
# ---------------------------------------------------------------------------
from . import gesto  # noqa: E402


@gesto("10-perfis.html", "ativar")
def ativar(ctx: Contexto, o: dict, p) -> None:
    """Ativar o perfil selecionado na tabela. `profile.switch`.

    O NOME VEM DO TEXTO DA LINHA, e não de um `data-` novo: a tabela já mostra o
    nome, e é o nome que o `profile.switch` quer. Marcar um segundo endereço com
    o mesmo valor seria a segunda verdade que esta casa persegue.
    """
    nome = str(o.get("texto") or "").strip()
    if not nome:
        raise ValueError("ativar: o clique não trouxe o nome do perfil")
    # `profile_switch` é do `ipc_bridge` — a mesma função que a aba Perfis da
    # GUI estável usa. Nada aqui monta payload.
    p.profile_switch(nome)


PONTE = {"profile_switch"}
METODOS: set[str] = set()
