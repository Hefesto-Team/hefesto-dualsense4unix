#!/usr/bin/env python3
"""O pacote da aba `10` Perfis.

ESTA ABA JÁ ESTAVA MARCADA, e não por mim: o outro agente pôs **77 endereços**
(`data-hef`) e 11 gestos nela em 31/08, com um esquema de nomes próprio. Os dois
convivem — o nome do atributo não é o contrato; o contrato é este despachante.

O QUE TEM DONO: o perfil em vigor (`active_profile`) e o travamento do
autoswitch (`autoswitch_locked`), que é o que diz se a troca automática está
segurada.

OS ONZE GESTOS MARCADOS, E OS TRÊS COM DONO — 01/09/2026, ao ligar os botões:

    selecionar          a célula do nome, na lista. Abre o perfil no editor.
    ativar              `profile.switch`
    voltar-a-de-ontem   `restaurar_do_historico` + reaplicar + `launch_env.refresh`

Os outros NOVE ficaram SEM DONO **de propósito** (os quatro `editor.*` contam
um a um), e o inventário com o motivo medido de cada um está logo acima do
`PONTE`, no fim deste arquivo. O resumo:
esta aba não tem rascunho de editor nem "Salvar" — o rodapé das dez abas é a
fase 3 — e quase todo botão que sobrou depende de um dos dois.

O QUE ESTA ABA NÃO SABE FAZER, e é o teto de tudo o que está acima: **o daemon
não tem `profile.save` nem `profile.delete`.** Os 39 métodos que ele atende
trazem só `profile.switch`, `profile.list` e `profile.apply_draft` — gravar e
apagar perfil roda no processo da janela, direto no disco, e por isso todo gesto
que escreve tem de avisar o daemon depois (`profile.switch` para reaplicar,
`launch_env.refresh` para a antecipação por appid).
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


#: O PERFIL ESCOLHIDO NA LISTA — o que ela clicou por último, e o alvo dos
#: botões da aba. Vive AQUI, no pacote, e não na tela: o clique chega ao Python
#: e a pintura sai dele, então guardar no JS obrigaria o gesto a perguntar de
#: volta ao navegador o que ele acabou de mandar.
#:
#: NÃO É "O PERFIL ATIVO". São duas coisas, e a janela estável já as separa: o
#: ativo é o que está valendo agora no daemon; o escolhido é a linha em que o
#: editor está aberto. Confundi-los faria "Voltar à de ontem" agir sempre sobre
#: o que está valendo, mesmo com outra linha aberta no editor.
_ESCOLHIDO: str = ""


def _escolhido(todos: list[dict], ativo: str) -> str:
    """A linha aberta no editor: a última clicada, ou o perfil ativo.

    ELE DEIXA DE VALER SOZINHO quando o perfil sai do disco — apagado por fora,
    renomeado, o `HEFESTO_VARIANTE` trocado. Sem esta queda, "Voltar à de
    ontem" continuaria mirando um arquivo que não existe mais e a mensagem de
    erro falaria de um perfil que ela não vê na lista.

    A SINCRONIZAÇÃO INICIAL É ESCRITA AQUI DE PROPÓSITO, e a guarda é o que a
    torna segura de repetir: só grava quando a lista tem aquele nome. Numa
    árvore de teste a pasta de perfis é vazia (o `conftest.py` desvia `HOME` e
    os quatro `XDG_*`), então nada é gravado e a régua dos botões continua vendo
    o estado limpo — medido em 01/09/2026, com `perfil.lista()` devolvendo `[]`.
    """
    global _ESCOLHIDO
    nomes = {p["nome"] for p in todos}
    if _ESCOLHIDO and _ESCOLHIDO not in nomes:
        _ESCOLHIDO = ""
    if not _ESCOLHIDO and ativo in nomes:
        _ESCOLHIDO = ativo
    return _ESCOLHIDO or ativo


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
    # O EDITOR MOSTRA O PERFIL ESCOLHIDO NA LISTA, e não o que está valendo — é
    # o que a aba Perfis da janela estável faz desde sempre
    # (`on_profile_selection_changed` → `_populate_editor`,
    # `profiles_actions.py:2984`), e é o que dá alvo aos botões da coluna. A
    # escolha nasce no perfil ATIVO, como lá (`_sync_selection_with_active_
    # profile`, `:1479`), e daí em diante quem manda é o clique dela.
    escolhido = _escolhido(todos, ativo)
    aberto = perfil.ativo(escolhido)
    return {
        "perfis.conta": f"{len(todos)} perfis",
        "perfis.linha.nome": [p["nome"] for p in todos],
        "perfis.linha.prioridade": [p["prioridade"] for p in todos],
        "perfis.linha.quando": [QUANDO.get(p["casamento"], p["casamento"]) for p in todos],
        "editor.nome": aberto.get("name") or escolhido or "—",
        "editor.prioridade": aberto.get("priority"),
        "editor.prioridade.n": aberto.get("priority"),
        "ativo": ativo or "—",
        # A LINHA ABERTA NO EDITOR. Não tem endereço na página ainda — sai aqui
        # para quem consome o pacote fora da tela (a régua, o relato) e para o
        # dia em que a lista souber acender a linha escolhida.
        "selecionado": escolhido or "—",
        "travado": bool(st.get("autoswitch_locked")),
        "jogo": st.get("jogo_steam") or "",
        "quantos": len(todos),
        "editor": {
            "gatilhos": bool(aberto.get("triggers")), "leds": bool(aberto.get("leds")),
            "rumble": bool(aberto.get("rumble")), "mouse": bool(aberto.get("mouse")),
            "casamento": (aberto.get("match") or {}).get("type", ""),
        } if aberto else {},
        "sem_dono": {},
        "cobertura": {"pintados": 8 + len(todos) * 3, "sem_dono": len(SEM_DONO)},
    }


# ---------------------------------------------------------------------------
# OS GESTOS — ver o exemplo comentado em `a04_iluminacao.py`
# ---------------------------------------------------------------------------
from . import gesto  # noqa: E402


@gesto("10-perfis.html", "selecionar")
def selecionar(ctx: Contexto, o: dict, p) -> None:
    """Abrir um perfil no editor. É o clique na CÉLULA DO NOME, na lista.

    ELE NÃO FALA COM O DAEMON, e é o único desta aba que não fala — de
    propósito. Escolher uma linha não muda nada no aparelho; muda o ALVO dos
    botões ao lado, que é o que a janela estável faz no
    `on_profile_selection_changed` (`profiles_actions.py:2984`). Ligar isto ao
    `profile.switch` faria passar o mouse pela lista trocar o perfil que está
    valendo — o oposto da coluna ter um botão "Ativar".

    E ELE NÃO RESPONDE CALADO: o editor ao lado repinta no tique seguinte com a
    prioridade daquele perfil (`editor.prioridade.n`). O campo Nome ainda não
    acompanha, e o motivo está no relato — ele é um `<input>`, e a pintura
    escreve `textContent` nele, que não aparece.

    `texto` é o nome VIVO porque a célula é a mesma que a pintura escreve
    (`perfis.linha.nome`). Ler o `data-hef-perfil` da linha traria o nome do
    MOCKUP: a pintura troca o texto e nunca reescreve o atributo.
    """
    global _ESCOLHIDO
    nome = str(o.get("texto") or "").strip()
    if not nome:
        raise ValueError("selecionar: o clique não trouxe o nome do perfil")
    _ESCOLHIDO = nome


@gesto("10-perfis.html", "ativar")
def ativar(ctx: Contexto, o: dict, p) -> None:
    """Ativar o perfil selecionado na tabela. `profile.switch`.

    O NOME VEM DO TEXTO DA LINHA, e não de um `data-` novo: a tabela já mostra o
    nome, e é o nome que o `profile.switch` quer. Marcar um segundo endereço com
    o mesmo valor seria a segunda verdade que esta casa persegue.

    DUAS CORREÇÕES DE 01/09/2026, ao ligar o resto da aba — e as duas são o
    mesmo defeito, que é o botão dizer "aplicado" sem ter aplicado:

    1. **A LINHA NÃO ERA CLICÁVEL.** O gesto lê o texto da linha, mas nenhum
       elemento da lista tinha endereço — o ouvinte do piloto casa
       `[data-gesto],[data-hef-gesto],…` (`hefesto_vivo.py:190`) e a `<tr>` só
       trazia `data-hef-perfil`. Quem clicava num perfil não mandava nada; quem
       clicava no BOTÃO mandava `texto="Ativar"`, e o gesto pedia ao daemon um
       perfil chamado "Ativar". Agora a célula do nome marca `selecionar`, e o
       botão age sobre o escolhido — o `_ESCOLHIDO` vem primeiro, e o `texto`
       fica como último recurso (é o que a prova declarada exercita).
    2. **A RECUSA DO DAEMON SUMIA.** `profile_switch` devolve `False` quando ele
       não confirmou (`ipc_bridge.py:271`, ATIVAR-NAO-MENTE-01) e o retorno era
       descartado: o piloto imprimia "→ aplicado" sobre uma troca que não
       aconteceu. Levantar aqui é o que faz o botão recusar dizendo.
    """
    nome = _ESCOLHIDO or str(o.get("texto") or "").strip()
    if not nome:
        raise ValueError("ativar: escolha um perfil na lista primeiro")
    # `profile_switch` é do `ipc_bridge` — a mesma função que a aba Perfis da
    # GUI estável usa. Nada aqui monta payload.
    if not p.profile_switch(nome):
        raise RuntimeError(f"o Hefesto não confirmou a troca para {nome!r}")


@gesto("10-perfis.html", "voltar-a-de-ontem")
def voltar_a_de_ontem(ctx: Contexto, o: dict, p) -> None:
    """Desfazer a última gravação do perfil aberto. `profiles/loader.py`.

    O QUE ELE DESFAZ, e o produto já sabia fazer isto pelo terminal:
    `save_profile` copia o arquivo ANTERIOR para `profiles/.historico/<slug>/`
    a cada gravação (PERFIL-SEM-RASTRO-01, `loader.py:1230`), e
    `restaurar_do_historico` devolve a mais recente **byte a byte**
    (`loader.py:1509`). O único chamador até hoje era `profile restore` da CLI
    (`cli/cmd_profile.py:282`) — este é o segundo, e é uma tela.

    POR QUE NÃO PEDE CONFIRMAÇÃO, e é a diferença dele para o "Remover": a
    própria restauração ARQUIVA a versão atual antes de substituí-la, então
    restaurar por engano também tem volta. É o desfazer, não a perda.

    AS DUAS CHAMADAS DEPOIS DO DISCO NÃO SÃO ENFEITE:

    * `profile.switch` — **o daemon não relê JSON de perfil por conta
      própria** (PERFIL-SAVE-APPLY-01, `profiles_actions.py:3508`). Sem ele o
      arquivo volta ao que era e o controle continua com o de agora, que é o
      sintoma que ela leu como "não está salvando". Só quando o perfil restaurado
      é o que está VALENDO: reaplicar outro trocaria o perfil pelas costas dela.
    * `launch_env.refresh` — a regra pode ter mudado, e com ela o
      `steam_app_<id>.env` de antecipação. É o mesmo aviso que o Salvar e o
      Remover da janela estável mandam (`footer_actions.py:205`), e a ordem é a
      de lá: reaplicar primeiro, avisar depois.

    A COMPARAÇÃO É POR SLUG, não por string: com "Navegação" no disco e
    "Navegacao" no daemon, um `==` cru diria que são perfis diferentes e o
    reaplicar não aconteceria (R-10, `profiles/slug.py:52`).
    """
    from hefesto_dualsense4unix.profiles.loader import restaurar_do_historico
    from hefesto_dualsense4unix.profiles.slug import mesmo_slug

    nome = _ESCOLHIDO or str(ctx.state.get("active_profile") or "")
    if not nome:
        raise ValueError("voltar à de ontem: escolha um perfil na lista primeiro")
    # Levanta `FileNotFoundError` quando não há versão guardada, e a frase dela
    # já diz o que houve — o histórico nasce na PRÓXIMA gravação daquele perfil.
    restaurar_do_historico(nome)
    ativo = str(ctx.state.get("active_profile") or "")
    if ativo and mesmo_slug(ativo, nome):
        p.profile_switch(nome)
    p.chamar("launch_env.refresh")


#: OS NOVE QUE FICARAM SEM DONO, e o motivo de cada um está no relato desta
#: leva. Em resumo, e é o mesmo diagnóstico para quase todos: **esta aba não
#: tem rascunho de editor nem um "Salvar"** — o rodapé das dez abas é a fase 3.
#:
#:   novo, duplicar   a janela estável só PREENCHE O EDITOR (`profiles_actions
#:                    .py:3016` e `:3144`); quem grava é o Salvar. A dica da
#:                    própria tela diz "Copia o perfil inteiro **para o
#:                    editor**".
#:   remover          `delete_profile` é puro e reusável, mas a dica dela promete
#:                    "Pergunta antes" e o `on_profile_remove` (`:3162`) o
#:                    esconde atrás de `confirm_delete_profile`
#:                    (BUG-DELETE-NO-CONFIRM-01). Não há diálogo nesta janela.
#:   recarregar       a lista já é relida do disco a cada tique de 500 ms
#:                    (`perfil.lista()`). Não há IPC atrás dele.
#:   detectar         o daemon responde (`daemon.state_full` →
#:                    `window_detect_last_class`), mas a dica promete "monta a
#:                    regra" — e a regra é `match` gravado no perfil, que é o
#:                    Salvar da fase 3.
#:   editor.*         `<input>` e `<select>` marcados como gesto: o clique não
#:                    carrega o valor digitado nem a opção escolhida, e o piloto
#:                    não ouve `change`.
PONTE = {"profile_switch", "chamar"}
METODOS = {"launch_env.refresh"}


PAGINA = "10-perfis.html"
PISO_DA_ABA = 3
#: `voltar-a-de-ontem` NÃO TEM PROVA DECLARADA, e a razão é medida: ele começa
#: por uma escrita em DISCO, e a régua roda com `HOME` e os quatro `XDG_*`
#: desviados para um lar de mentira — a pasta de perfis é vazia, então
#: `restaurar_do_historico` levanta antes de qualquer chamada à ponte. Ele foi
#: provado por medição própria, com uma pasta de perfis de verdade num diretório
#: temporário; o relato desta leva traz o número.
PROVAS = [
    {"pagina": PAGINA, "gesto": "ativar", "clique": {"texto": "Ação"},
     "chama": [("profile_switch", ["Ação"], {})]},
]

#: O QUE NÃO FALA COM O DAEMON, de propósito: `selecionar` muda o ALVO dos
#: botões ao lado, na memória desta janela — escolher uma linha não pode trocar
#: o perfil que está valendo, senão a coluna não precisaria de um "Ativar".
#:
#: E ISSO MUDA A PROVA: `ativar` sozinho não tem o que ativar. A sequência é
#: `selecionar` e ENTÃO `ativar`, e uma régua que os clicasse em ordem
#: alfabética diria "sem efeito" sobre os dois.
SEM_ECO = ("selecionar",)
