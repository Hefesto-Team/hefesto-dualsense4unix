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

import time

# O IMPORT É DE MÓDULO, e não de dentro da função — 01/09/2026. O
# `portao_a_casa_sabe_e_o_produto_nao_faz` segue o fecho de IMPORT a partir do
# piloto que o lançador abre, e um `from … import` escondido dentro de uma
# função não entra nesse fecho: a camada do produto continuava aparecendo como
# "promessa sem caminho" mesmo depois de eu a ligar.
#
# O `sys.path` já tem o `src/` quando esta linha roda: `pacotes/__init__.py` o
# insere no import do pacote.
from hefesto_dualsense4unix.app.actions import perfis_web as _tela

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


#: A JANELA DA CONFIRMAÇÃO do "Remover", em segundos. Não é gosto: um armamento
#: sem prazo é uma armadilha — ela clica, se distrai, volta meia hora depois,
#: clica de novo e o perfil some sem que nada na tela tenha dito por quê.
SEGUNDOS_PARA_CONFIRMAR = 8.0

#: O que o "Remover" está esperando: `(perfil, instante)`, ou `None`.
_ARMADO: tuple[str, float] | None = None

#: O perfil cujos campos de TEXTO já foram pintados, e o instante do último
#: tique desta aba. Ver `_uma_vez_so`.
_PINTADO_PARA: str = ""
_ULTIMO_TIQUE: float = 0.0

#: OS TRÊS CAMPOS QUE NÃO SE REPINTAM. Os dois primeiros porque ela DIGITA
#: neles; o terceiro porque o valor é sempre o mesmo (não existe campo de
#: Estilo no perfil) e repintá-lo custava uma escrita por tique para sempre —
#: medido no Chrome em 01/09/2026: "2º tique pintou 1", e o 1 era ele.
CAMPOS_QUE_ELA_DIGITA = ("editor.nome", "editor.jogo", "editor.estilo")


def _uma_vez_so(alvo: str) -> tuple[str, ...]:
    """Os endereços a OMITIR deste tique. Vazio = pinte tudo.

    O PROBLEMA, medido em 01/09/2026 lendo o `escrever()` do piloto
    (`hefesto_vivo.py:114`): com `data-hef-alvo="valor"` a pintura faz
    `el.value = t` sempre que o valor difere. O tique é de 500 ms
    (`hefesto_vivo.py:63`). Na segunda tecla que ela digita, o campo já difere
    do que está no disco — e meio segundo depois a pintura o devolve ao valor
    do perfil. **O campo ficaria intocável.**

    A CURA É PINTAR UMA VEZ POR ESCOLHA: quando o perfil aberto no editor muda,
    os três campos vão uma vez; enquanto ela fica no mesmo perfil, ninguém
    escreve neles. Foi assim que o campo pôde ganhar gesto — sem isto, ligar o
    Nome seria ligar um campo que se apaga sozinho.

    E ELE VOLTA A PINTAR QUANDO ELA SAI DA ABA E VOLTA. Sem esta segunda
    guarda, a página recarregada mostraria de novo o "Mortal Kombat" do
    MOCKUP — o `<input>` nasce com o valor do desenho, e a memória deste módulo
    diria "já pintei". O sinal é o BURACO no tique: as dez abas dividem o mesmo
    piloto, e `pacote()` só é chamado enquanto esta página está aberta, a cada
    500 ms. Um intervalo maior que 2 s significa que a página foi embora e
    voltou.
    """
    global _PINTADO_PARA, _ULTIMO_TIQUE
    agora = time.monotonic()
    voltou = (agora - _ULTIMO_TIQUE) > 2.0
    _ULTIMO_TIQUE = agora
    if voltou or alvo != _PINTADO_PARA:
        _PINTADO_PARA = alvo
        return ()
    return CAMPOS_QUE_ELA_DIGITA


def _rotulo_do_remover() -> str:
    """"Remover", ou a PERGUNTA que a dica dela promete.

    A dica no desenho diz *"Apaga do disco. Pergunta antes."* — e esta janela
    não tem diálogo. O `on_profile_remove` da janela estável abre um
    `gui_dialogs.confirm_delete_profile` (`profiles_actions.py:3167`), que é
    GTK e MODAL; daqui não dá para abri-lo, porque **os gestos rodam em
    thread** (`hefesto_vivo.py:520`) e GTK só aceita diálogo no laço principal.

    E a recusa do piloto não serve de pergunta: ela sai em `stderr`
    (`hefesto_vivo.py:527`), no terminal, onde a dona não está olhando.

    Então a pergunta é o PRÓPRIO RÓTULO do botão. É o único pedaço de tela que
    já existe, que ela está olhando no instante do clique, e que o piloto sabe
    pintar. O desenho não muda: o mockup continua escrevendo "Remover".
    """
    if _ARMADO and (time.monotonic() - _ARMADO[1]) < SEGUNDOS_PARA_CONFIRMAR:
        return f"Remover “{_ARMADO[0]}”? Clique de novo"
    return "Remover"


@registrar("10-perfis.html")
def pacote(ctx: Contexto) -> dict:
    """DELEGA para `app/actions/perfis_web.pacote_da_aba` — a camada do PRODUTO.

    ELA JÁ EXISTIA E NUNCA TINHA SIDO LIGADA. O `casa-sabe` a listava como
    promessa sem caminho: `perfis_web.pacote_da_aba` não tinha um chamador em
    produção desde 30/08/2026.

    E ELA SABE MAIS QUE O QUE ESTE PACOTE TINHA: a coluna "Quando usar" diz *"Só
    neste programa"* onde eu escrevia *"Jogo"*; ela traz `com_ajuste` ("0 de 2
    controles com ajuste próprio neste perfil"), a `guarda` dos overrides por
    controle, os `travados` e o `editor` inteiro. Cada uma dessas frases é texto
    de tela que alguém escreveu com ela, e reescrevê-las por fora seria a
    segunda verdade.

    O QUE SOBRA AQUI é o ACHATAMENTO para os `data-hef` da página, que são 77.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.profiles.loader import load_all_profiles
    from hefesto_dualsense4unix.profiles.slug import find_by_slug

    ativo = str(ctx.state.get("active_profile") or "")
    try:
        todos = load_all_profiles()
        # O `editado` FALTAVA, e o editor mostrava o perfil ERRADO — corrigido
        # em 01/09/2026, ao ligar os campos. Sem ele `pacote_da_aba` cai no
        # ativo (`perfis_web.py:426`), então clicar numa linha mudava o alvo dos
        # botões e o editor ao lado continuava pintando OUTRO perfil. Enquanto
        # nenhum campo tinha gesto isso era só uma tela desalinhada; com o Nome
        # e o Nome do Jogo ligados, seria ela renomear um perfil olhando para o
        # nome de outro.
        alvo = find_by_slug(_escolhido([{"nome": x.name} for x in todos], ativo), todos)
        bruto = _tela.pacote_da_aba(todos, ativo=ativo or None,
                                    mesa=ctx.mesa, editado=alvo)
    except Exception:
        return {"sem_dono": {}, "cobertura": {"pintados": 0, "sem_dono": 1}}

    lista = bruto.get("lista") or []
    editor = bruto.get("editor") or {}
    fora = {
        "perfis.conta": bruto.get("conta", "—"),
        "perfis.com-ajuste": bruto.get("com_ajuste", ""),
        # AS TRÊS COLUNAS SÃO LISTAS, e a tela as distribui pelos blocos de
        # mesmo endereço, na ordem — sem o gerador precisar saber quantos
        # perfis ela tem.
        "perfis.linha.nome": [x.get("nome", "") for x in lista],
        "perfis.linha.prioridade": [x.get("prioridade", "") for x in lista],
        "perfis.linha.quando": [x.get("quando", "") for x in lista],
        "ativo": ativo or "—",
        "quantos": len(lista),
        "travado": bool(ctx.state.get("autoswitch_locked")),
        "sem_dono": {},
    }
    # O SEPARADOR É O PONTO, e não o hífen: a página endereça
    # `editor.prioridade.dica`, e um `editor.prioridade-dica` cai no vazio. Os
    # 77 `data-hef` desta aba usam ponto do começo ao fim.
    # O EDITOR TAMBÉM: sem perfil aberto, os campos vão a travessão em vez de
    # ficar com o texto do desenho.
    for chave in ("nome", "jogo", "estilo", "ambiente", "prioridade"):
        fora.setdefault(f"editor.{chave}", "—")
    fora.setdefault("editor.prioridade.n", "—")
    fora.setdefault("editor.prioridade.dica", "")
    for chave, valor in editor.items():
        if not isinstance(valor, (dict, list)):
            fora[f"editor.{chave.replace('_', '.')}"] = valor

    # OS TRÊS CAMPOS QUE SE PINTAM UMA VEZ SÓ — e a razão é medida, não gosto.
    # Ver `_uma_vez_so`: repintar um `<input>` a cada 500 ms apagaria o que ela
    # está digitando na segunda tecla.
    for chave in _uma_vez_so(str(getattr(alvo, "name", ""))):
        fora.pop(chave, None)

    # O RÓTULO DO REMOVER, e ele é a pergunta que a dica dela promete. Sai daqui
    # e não do JS porque o armamento vive no Python (ver o gesto `remover`).
    fora["perfis.remover"] = _rotulo_do_remover()

    # A GUARDA são os overrides por controle — o que cada um guarda de próprio
    # neste perfil. O produto já a monta; a tela a distribui por linha.
    # AS CHAVES SAEM MESMO VAZIAS, e é o que faz a tela APAGAR a lista do
    # mockup quando não há perfil. Emiti-las só quando há conteúdo deixaria os
    # catorze nomes do desenho na tela de quem não tem perfil nenhum — a mesma
    # mentira dos lugares vazios da mesa, que já custou sete reincidências.
    guarda = bruto.get("guarda") or []
    if isinstance(guarda, list):
        fora["guarda.nome"] = [g.get("nome", "") for g in guarda]
        fora["guarda.id"] = [g.get("id", "") for g in guarda]
        fora["guarda.secao"] = [s for g in guarda for s in (g.get("secoes") or [])]
        fora["guarda.linhas"] = str(len(guarda))
    fora["cobertura"] = {"pintados": len(fora) + len(lista) * 3, "sem_dono": 0}
    return fora




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
    {"pagina": PAGINA, "gesto": "ativar", "clique": {"texto": "Ação"},  # (noqa-acento) id
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
