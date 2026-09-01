#!/usr/bin/env python3
"""O pacote da aba `10` Perfis.

ESTA ABA JÁ ESTAVA MARCADA, e não por mim: o outro agente pôs **77 endereços**
(`data-hef`) e 11 gestos nela em 31/08, com um esquema de nomes próprio. Os dois
convivem — o nome do atributo não é o contrato; o contrato é este despachante.

O QUE TEM DONO: o perfil em vigor (`active_profile`) e o travamento do
autoswitch (`autoswitch_locked`), que é o que diz se a troca automática está
segurada.

OS DOZE GESTOS MARCADOS, E OS DEZ COM DONO — 01/09/2026, em duas levas:

    selecionar          a célula do nome, na lista. Abre o perfil no editor.
    ativar              `profile.switch`
    voltar-a-de-ontem   `restaurar_do_historico` + reaplicar + `launch_env.refresh`
    ---- a segunda leva ----------------------------------------------------
    editor.nome         renomeia: `save_profile` do nome novo + `delete_profile`
    editor.ambiente     troca a REGRA: `from_simple_choice` + `save_profile`
    editor.jogo         o programa (ou o appid) dentro da regra
    detectar            o jogo da Steam em foco, de `window_detect_last_class`
    novo                um perfil em branco, com a regra do jogo em foco
    duplicar            `model_copy` com "(cópia)" no nome, e o editor abre nela
    remover             `delete_profile`, com a pergunta NO RÓTULO do botão

A SEGUNDA LEVA SÓ FOI POSSÍVEL POR TRÊS CORREÇÕES, e nenhuma é do daemon:

1. o clique passou a trazer `valor` — o `value` do `<input>`/`<select>`. A
   primeira leva parou exatamente aqui: *"o ouvinte manda `texto:
   alvo.textContent`, que num `<input>` é vazio"*;
2. os quatro campos ganharam `data-hef-alvo="valor"` no gerador. Sem isso a
   pintura APAGAVA as opções dos dois `<select>` (medido: 5 → 0 e 15 → 0) e
   deixava os dois `<input>` com o texto do MOCKUP para sempre;
3. `pacote()` passou a mandar `editado=` para o produto. Sem isso o editor
   pintava o perfil ATIVO enquanto os botões agiam sobre o ESCOLHIDO — e ligar
   o campo Nome seria ela renomear um perfil olhando o nome de outro.

OS DOIS QUE CONTINUAM SEM DONO — `recarregar` e `editor.estilo` — estão com o
motivo medido logo acima do `PONTE`, no fim deste arquivo.

O QUE ESTA ABA NÃO SABE FAZER, e é o teto de tudo o que está acima: **o daemon
não tem `profile.save` nem `profile.delete`.** Os 39 métodos que ele atende
trazem só `profile.switch`, `profile.list` e `profile.apply_draft` — gravar e
apagar perfil roda no processo da janela, direto no disco, e por isso todo gesto
que escreve tem de avisar o daemon depois (`profile.switch` para reaplicar,
`launch_env.refresh` para a antecipação por appid).
"""
from __future__ import annotations

import time
from typing import Any

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


def _escolhido(todos: list[dict[str, Any]], ativo: str) -> str:
    """A linha aberta no editor: a última clicada, ou o perfil ativo.

    ELE DEIXA DE VALER SOZINHO quando o perfil sai do disco — apagado por fora,
    renomeado, o `HEFESTO_VARIANTE` trocado. Sem esta queda, "Voltar à de
    ontem" continuaria mirando um arquivo que não existe mais e a mensagem de
    erro falaria de um perfil que ela não vê na lista.

    A SINCRONIZAÇÃO INICIAL É ESCRITA AQUI DE PROPÓSITO, e a guarda é o que a
    torna segura de repetir: só grava quando a lista tem aquele nome. Na régua
    dos botões o `active_profile` é "regua" e nenhum perfil se chama assim,
    então nada é gravado e o estado do módulo continua limpo.

    FATO SUBSTITUÍDO — 01/09/2026, segunda leva. Aqui estava escrito que "numa
    árvore de teste a pasta de perfis é vazia", medido com `perfil.lista()`
    devolvendo `[]`. A medição estava certa e a CONCLUSÃO, errada: `pacote()`
    não chama `perfil.lista()`, chama `load_all_profiles()` — e essa SEMEIA os
    presets de fábrica (`loader._maybe_seed_presets:485`, uma vez por processo).
    Medido no mesmo lar de mentira do `conftest.py`: `perfil.lista()` → 0
    itens, `load_all_profiles()` → **9 perfis** (Ação, Aventura, Corrida,
    Esportes, FPS, Navegação, fallback, meu_perfil, point_and_click). Duas
    funções, duas respostas, a mesma pasta.
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
def pacote(ctx: Contexto) -> dict[str, Any]:
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
def selecionar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
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
def ativar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
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
def voltar_a_de_ontem(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
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


# ---------------------------------------------------------------------------
# OS GESTOS QUE ESCREVEM NO DISCO — 01/09/2026, a segunda leva desta aba.
#
# O TETO CONTINUA SENDO O MESMO, e é o que dá forma a todos eles: **o daemon
# não tem `profile.save` nem `profile.delete`**. Gravar e apagar perfil roda no
# processo da janela, em `profiles/loader.py`, que é puro. Por isso cada um
# destes gestos tem a MESMA forma de três tempos:
#
#     1. escreve no disco       `save_profile` / `delete_profile`
#     2. reaplica, se for o ativo   `profile.switch` — o daemon NÃO relê JSON de
#                               perfil por conta própria (PERFIL-SAVE-APPLY-01)
#     3. avisa a antecipação    `launch_env.refresh` — a regra pode ter mudado,
#                               e com ela o `steam_app_<id>.env`
#
# A ordem é a da janela estável (`footer_actions.py:205`): reaplicar primeiro,
# avisar depois. Invertida, o refresh leria o perfil que ainda não valia.
# ---------------------------------------------------------------------------


def _perfil_do_editor(ctx: Contexto) -> str:
    """O perfil em que o editor está aberto. Vazio é RECUSA, nunca "o primeiro".

    É o mesmo alvo que `pacote()` manda pintar (`editado=`), e tem de ser: um
    gesto que agisse sobre outro perfil faria ela editar o que não está vendo.
    """
    nome = _ESCOLHIDO or str(ctx.state.get("active_profile") or "")
    if not nome:
        raise ValueError("escolha um perfil na lista primeiro — a coluna da "
                         "esquerda; o editor abre na linha que você clicar.")
    return nome


#: O CAMINHO DE VOLTA do rótulo do seletor para a chave do produto. Ele é a
#: INVERSÃO de `perfis_web.AMBIENTE_DO_PRESET`, e não uma segunda tabela: o
#: dono das quatro palavras é aquele módulo, e digitá-las aqui seria a segunda
#: verdade no dia em que uma delas mudasse.
#:
#: "Estilo de Jogo" É A QUINTA OPÇÃO DO DESENHO e não está aqui — não existe
#: preset para ela (`profiles/simple_match.SIMPLE_MATCH_PRESETS` tem sete, e
#: nenhum é estilo). Cair fora desta tabela é o que faz o gesto RECUSAR
#: dizendo, em vez de gravar `MatchAny()` calado — que é o que
#: `from_simple_choice` faz com chave desconhecida (`simple_match.py:248`), e
#: seria a tela rebaixando a regra dela em silêncio.
PRESET_DO_ROTULO = {v: k for k, v in _tela.AMBIENTE_DO_PRESET.items()}


def _gravar(prof: Any, ctx: Contexto, p: Any, *, era: str = "") -> None:
    """Os três tempos: disco, reaplicar se for o ativo, avisar a antecipação.

    O CORPO MUDOU DE CASA em 01/09/2026, e a razão é que ele ganhou um SEGUNDO
    chamador: o `a06_navegacao`, que devolve os atalhos de botão ao de fábrica,
    precisa exatamente destes três tempos. Uma segunda cópia é a que esquece o
    `launch_env.refresh` no dia em que alguém mexer numa só — então o corpo foi
    para `pacotes/perfil.py`, que é o módulo que as abas já compartilham, e este
    nome fica como a porta desta aba.
    """
    perfil.gravar_e_reaplicar(prof, ctx, p, era=era)


def _nome_livre(base: str, todos: Any) -> str:
    """`base`, ou `base 2`, `base 3`… — o primeiro que não colide por SLUG.

    A colisão é por slug e não por nome à vista porque é o slug que vira nome
    de arquivo (`loader.save_profile:1419`): dois nomes que só diferem no
    acento caem no MESMO arquivo, e o segundo apagaria o primeiro sem uma
    palavra na tela — "Acao (cópia)" e "Ação (cópia)".  (noqa-acento: exemplo)
    """
    from hefesto_dualsense4unix.profiles.slug import slugify

    usados = {slugify(x.name) for x in todos}
    if slugify(base) not in usados:
        return base
    n = 2
    while slugify(f"{base} {n}") in usados:
        n += 1
    return f"{base} {n}"


def _so_mudou(o: dict[str, Any]) -> bool:
    """`False` quando o clique foi só um clique — e aí o campo não age.

    MEDIDO NO CHROME em 01/09/2026, injetando o `BOOTSTRAP` do piloto sobre o
    `layout/10-perfis.html` e trocando o `postMessage` por um coletor. Mexer
    nos quatro campos como ela mexeria produziu **treze** mensagens, e quatro
    delas são `evento=click`:

        editor.nome   tipo=input   evento=change  valor='Elden Ring BR'
        editor.jogo   tipo=input   evento=click   valor='1245620'      ← só cliquei
        editor.jogo   tipo=input   evento=change  valor='1599660'
        editor.nome   tipo=input   evento=click   valor='Elden Ring BR' ← só cliquei

    O ouvinte do piloto escuta `click` E `change` (`hefesto_vivo.py:188-200`), e
    **clicar dentro de um campo para pôr o cursor manda o valor que já estava
    lá**. Sem esta guarda, clicar no "Nome do Jogo" de um perfil em "Todos"
    faria o gesto inferir a regra e GRAVAR — uma troca de regra disparada por
    um clique que não mudou nada.

    A guarda é `!= "click"`, e não `== "change"`, de propósito: um clique de
    régua (um dicionário montado à mão, sem `evento`) tem de continuar valendo.
    """
    return str(o.get("evento") or "") != "click"


@gesto("10-perfis.html", "editor.nome")
def editor_nome(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Renomear o perfil aberto no editor. `save_profile` + `delete_profile`.

    O VALOR VEM DE `valor`, E NÃO DE `texto` — foi a causa nomeada na primeira
    leva: *"o ouvinte manda `texto: alvo.textContent`, que num `<input>` é
    vazio"*. Desde 01/09 o clique traz o `value` do campo
    (`hefesto_vivo.py:228`) e o piloto escuta `change` além de `click`, que é o
    único evento que um campo de texto dispara com o valor novo.

    POR QUE RENOMEAR NA HORA, e não guardar num rascunho: decisão dela de
    01/09 — *"clicar na cor já deveria aplicar a cor no controle"* —, e esta aba
    não tem "Salvar" próprio (o do rodapé grava o perfil ATIVO a partir do que
    está valendo no daemon, `rodape.py:114`, e nem olha para este campo). Um
    campo que aceita texto e não guarda nada é o botão que responde calado.

    NÃO HÁ `rename` NO PRODUTO — medido: `profiles/loader.py` tem
    `save_profile`, `delete_profile`, `load_profile` e `restaurar_do_historico`,
    e nenhum renomeia. A janela estável faz a mesma dupla no Salvar, com o
    diálogo do R-10 se oferecendo para apagar o antigo. Aqui a ordem é gravar
    PRIMEIRO e apagar depois: invertida, uma falha no meio perderia o perfil.

    E O ANTIGO NÃO SOME DE VEZ: `delete_profile` arquiva a última versão em
    `profiles/.historico/<slug>/` antes do `unlink` (PERFIL-SEM-RASTRO-01,
    `loader.py:1601`). Um renomear por engano se desfaz com
    `hefesto-dualsense4unix profile restore <nome-antigo>`.

    AS DUAS RECUSAS:

    * nome vazio — apagar o campo não pode virar um arquivo `.json`;
    * nome que já é de OUTRO perfil — o `save_profile` grava por SLUG, então
      renomear "Elden Ring" para "Pragmata" gravaria por cima do Pragmata dela,
      calado. É o mesmo estrago que o `_nome_livre` evita no Duplicar.
    """
    global _ESCOLHIDO
    from hefesto_dualsense4unix.profiles.loader import (
        delete_profile,
        load_all_profiles,
        load_profile,
    )
    from hefesto_dualsense4unix.profiles.slug import slugify

    if not _so_mudou(o):
        return
    novo = str(o.get("valor") or "").strip()
    era = _perfil_do_editor(ctx)
    if not novo:
        raise ValueError("o perfil precisa de um nome — o campo ficou vazio.")
    prof = load_profile(era)
    if prof.name == novo:
        return
    troca_de_arquivo = slugify(novo) != slugify(prof.name)
    if troca_de_arquivo:
        for outro in load_all_profiles():
            if slugify(outro.name) == slugify(novo):
                raise ValueError(
                    f"já existe um perfil chamado “{outro.name}”. Escolha outro "
                    f"nome — gravar este por cima apagaria o dele.")
    _gravar(prof.model_copy(update={"name": novo}), ctx, p, era=era)
    if troca_de_arquivo:
        delete_profile(era)
    _ESCOLHIDO = novo


@gesto("10-perfis.html", "editor.ambiente")
def editor_ambiente(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Funciona em": trocar a REGRA que faz o perfil entrar. `from_simple_choice`.

    QUEM MONTA A REGRA É O PRODUTO, e não este arquivo:
    `profiles/simple_match.from_simple_choice:203` é a mesma função que o Salvar
    da janela estável usa (`profiles_actions._build_profile_from_editor`), com
    as frases de recusa já escritas em português ("Diga o número do jogo na
    Steam (ex.: 1599660)"). Montar um `MatchCriteria` aqui seria a segunda
    verdade sobre o que cada opção significa.

    O `regra_do_disco` NÃO É ENFEITE: para "Jogo da Steam" ele preserva o
    `process_name` do MESMO jogo, que ela nunca viu na tela e portanto nunca
    pediu para tirar (ESCONDER-EM-VEZ-DE-SAIR-01, `simple_match.py:382`).

    AS DUAS RECUSAS, e as duas existem para não REBAIXAR a regra dela:

    * **o seletor travado** — quando o perfil casa por uma regra que esta tela
      não sabe mostrar (`window_title_regex`, lista de classes), o produto abre
      o campo travado com a frase do que fazer (`perfis_web.py:172`). Aceitar a
      troca ali seria o defeito R-12: substituir uma regra fina por "Todos".
      MEDIDO: sete dos nove perfis de fábrica caem nesse estado.
    * **"Estilo de Jogo"** — é a quinta opção do desenho e não tem preset
      nenhum atrás. `from_simple_choice` devolve `MatchAny()` para chave
      desconhecida, sem reclamar (`simple_match.py:248`): escolher "Estilo de
      Jogo" gravaria um catch-all no lugar da regra do jogo dela, em silêncio.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile
    from hefesto_dualsense4unix.profiles.simple_match import from_simple_choice

    if not _so_mudou(o):
        return
    rotulo = str(o.get("valor") or o.get("rotulo") or "").strip()
    nome = _perfil_do_editor(ctx)
    chave = PRESET_DO_ROTULO.get(rotulo)
    if chave is None:
        raise ValueError(
            f"“{rotulo}” não é uma regra que o perfil saiba guardar. O produto "
            f"conhece {', '.join(sorted(PRESET_DO_ROTULO))} — “Estilo de Jogo” "
            f"está desenhado e não tem campo nem preset atrás dele.")
    prof = load_profile(nome)
    editor = _editor_de(prof)
    if editor.get("ambiente_travado"):
        raise ValueError(str(editor.get("ambiente_recado") or ""))
    # O NOME DO JOGO VEM DO DISCO, e não do campo ao lado: o `<input>` pode ter
    # texto que ela digitou e ainda não confirmou (o `change` só dispara quando
    # o foco sai). Ler o disco é ler o que o perfil de fato tem.
    prof.match = from_simple_choice(chave, editor.get("jogo") or "",
                                    regra_do_disco=prof.match)
    _gravar(prof, ctx, p)


@gesto("10-perfis.html", "editor.jogo")
def editor_jogo(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Nome do Jogo": o programa (ou o número da Steam) que faz o perfil entrar.

    ELE SÓ TEM EFEITO EM DUAS DAS CINCO OPÇÕES do "Funciona em":
    `from_simple_choice` só lê o `custom_name` em "game" e "steam_game"
    (`simple_match.py:236-247`). Com o seletor em "Todos" ou "Steam", o texto
    seria descartado sem uma palavra — ela digitaria o nome do jogo, veria o
    campo aceitar, e a regra continuaria a mesma.

    ENTÃO O SELETOR ANDA JUNTO, e isso desfaz um IMPASSE que eu mesmo criei e
    medi antes de entregar: com o perfil em "Todos", escolher "Jogo" no seletor
    recusava por falta de nome (`MSG_JOGO_SEM_NOME`), e digitar o nome recusava
    por o seletor estar em "Todos". **Os dois caminhos fechados, e o perfil
    preso em "Todos" para sempre.** Digitar o nome de um jogo é dizer "este
    perfil é deste jogo": o gesto grava a regra inteira, e o seletor mostra o
    resultado no tique seguinte.

    O PRODUTO JÁ FAZ ISSO, e não é invenção desta tela: o
    `_aplicar_nascimento_com_jogo` (`profiles_actions.py:3128`) chama
    `_select_radio("steam_game")` **e** preenche o campo, no mesmo gesto.

    QUAL DAS DUAS ELE ESCOLHE: `normalize_appid` decide — só dígitos (ou um
    endereço da loja, que ele sabe ler) é "Jogo da Steam"; qualquer outra coisa
    é "Jogo", com o nome do programa. E ele SÓ decide quando o seletor não
    estava numa das duas: com "Jogo" ou "Jogo da Steam" já escolhido por ela,
    a escolha dela manda — digitar "1245620" num perfil que ela pôs em "Jogo"
    não pode virar um perfil da Steam pelas costas dela.

    R-12: o nome do programa vai **como ela digitar**, sem `.lower()` — o
    matcher compara com o basename cru de `/proc/PID/exe`, e
    `Cyberpunk2077.exe` nunca casaria com `cyberpunk2077.exe`.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile
    from hefesto_dualsense4unix.profiles.simple_match import (
        from_simple_choice,
        normalize_appid,
    )

    if not _so_mudou(o):
        return
    texto = str(o.get("valor") or "").strip()
    nome = _perfil_do_editor(ctx)
    prof = load_profile(nome)
    editor = _editor_de(prof)
    if editor.get("ambiente_travado"):
        raise ValueError(str(editor.get("ambiente_recado") or ""))
    chave = PRESET_DO_ROTULO.get(str(editor.get("ambiente") or ""))
    if chave not in ("game", "steam_game"):
        chave = "steam_game" if normalize_appid(texto) is not None else "game"
    prof.match = from_simple_choice(chave, texto, regra_do_disco=prof.match)
    _gravar(prof, ctx, p)


@gesto("10-perfis.html", "detectar")
def detectar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Detectar": pegar o jogo em foco e montar a regra com ele.

    A AFIRMAÇÃO QUE ESTAVA NO PRODUTO ESTÁ ERRADA PELA METADE, e é o que
    destravou este botão. `perfis_web.DONOS_DOS_GESTOS["detectar"]` diz *"o IPC
    NÃO PUBLICA o título nem a classe"* — e daí a primeira leva o deixou sem
    dono. MEDIDO em 01/09/2026, contra o daemon `dev` desta árvore, com
    `ipc_bridge.daemon_state_full()`: das 49 chaves do `state_full`, SETE são
    de detecção de janela, e duas delas são a classe —
    `window_detect_last_class` e `window_detect_current_class`. O TÍTULO é que
    não é publicado. A janela estável já lia exatamente esta chave desde o
    PERFIL-NASCE-CERTO-01 (`profiles_actions._aplicar_nascimento_com_jogo`).

    O QUE ELE FAZ E O QUE AINDA NÃO FAZ:

    * **jogo da Steam** — a classe vem como `steam_app_<id>` e o appid sai dela
      pela fonte única do produto (`profiles/steam_app.steam_appid_from_wm_class`,
      UNIFICA-PREDICADO-01). A regra vira "Jogo da Steam" com aquele número.
    * **jogo de fora da Steam** — RECUSA DIZENDO a classe que viu. A dica dela
      promete *"funciona com jogo de qualquer lugar"* e esta metade não tem
      dono: o detector entrega uma **wm_class**, e o produto só sabe guardá-la
      como `MatchCriteria(window_class=…)`, que é uma regra que este editor não
      sabe MOSTRAR — o perfil abriria travado, com a frase de usar a linha de
      comando. Gravar isso a partir de um botão seria empurrar o perfil dela
      para fora da tela. Escrevê-la como `process_name` seria pior: é outro
      dado (o basename de `/proc/PID/exe`), e casaria por acaso.

    `last_class` ANTES de `current_class`: a primeira é a última classe ÚTIL
    vista (`launch_wrapper_dialog.py:81`) e sobrevive ao foco ir para a janela
    do Hefesto — que é exatamente o que acontece quando ela clica neste botão.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile
    from hefesto_dualsense4unix.profiles.simple_match import from_simple_choice
    from hefesto_dualsense4unix.profiles.steam_app import steam_appid_from_wm_class

    nome = _perfil_do_editor(ctx)
    classe = str(ctx.state.get("window_detect_last_class")
                 or ctx.state.get("window_detect_current_class") or "")
    appid = steam_appid_from_wm_class(classe) if classe else None
    if appid is None:
        visto = f"“{classe}”" if classe and classe != "unknown" else "nenhuma janela"
        raise ValueError(
            f"não achei jogo da Steam em foco — o detector está vendo {visto}. "
            f"Abra o jogo, deixe-o em foco por um instante e clique de novo; "
            f"para jogo de fora da Steam, a regra ainda se escreve pela linha "
            f"de comando (`hefesto-dualsense4unix profile`).")
    prof = load_profile(nome)
    prof.match = from_simple_choice("steam_game", str(appid),
                                    regra_do_disco=prof.match)
    _gravar(prof, ctx, p)


@gesto("10-perfis.html", "novo")
def novo(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Novo": um perfil em branco no disco, já com a regra do jogo em foco.

    NASCE NO DISCO, e não num rascunho, porque esta aba não tem "Salvar"
    próprio — a janela estável só PREENCHE O EDITOR (`on_profile_new:3016`) e
    quem grava é o botão seguinte. Aqui, com a ação imediata que ela pediu, o
    arquivo nasce e a lista o mostra no tique seguinte, já aberto no editor.

    A REGRA DO JOGO EM FOCO É A MESMA DO PRODUTO, e a guarda também: o
    `_aplicar_nascimento_com_jogo` (`profiles_actions.py:3088`) só age quando há
    **appid da Steam**, e devolve `False` calado no resto. É o que este gesto
    faz — com jogo da Steam em foco nasce mirando aquele jogo, sem ele nasce
    catch-all, "que é o certo para um perfil de desktop" (palavras de lá).

    O QUE ELE NÃO CARREGA, e é dívida honesta: a janela estável ainda sobe a
    prioridade acima dos catch-all (`_prioridade_acima_dos_catch_all`), e essa
    conta mora num mixin GTK que depende de widget. Este perfil nasce com a
    prioridade padrão do esquema. Ele NÃO é ativado: nascer não é passar a
    valer.
    """
    global _ESCOLHIDO
    from hefesto_dualsense4unix.profiles.loader import load_all_profiles
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
    from hefesto_dualsense4unix.profiles.simple_match import from_simple_choice
    from hefesto_dualsense4unix.profiles.steam_app import steam_appid_from_wm_class

    classe = str(ctx.state.get("window_detect_last_class")
                 or ctx.state.get("window_detect_current_class") or "")
    appid = steam_appid_from_wm_class(classe) if classe else None
    regra = (from_simple_choice("steam_game", str(appid)) if appid is not None
             else MatchAny())
    nome = _nome_livre("Novo perfil", load_all_profiles())
    _gravar(Profile(name=nome, match=regra), ctx, p)
    _ESCOLHIDO = nome


@gesto("10-perfis.html", "duplicar")
def duplicar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Duplicar": o perfil inteiro numa cópia, e o editor abre nela.

    A DICA DELA DIZ *"Copia o perfil inteiro para o editor, com «(cópia)» no
    nome"*, e as três partes se cumprem — a última por consequência da segunda:
    a cópia nasce no disco e o `_ESCOLHIDO` passa a ser ela, então é ela que o
    editor pinta no tique seguinte.

    "O PERFIL INTEIRO" É LITERAL, e é a diferença para o defeito
    BUG-DUPLICATE-NO-CONFIG-COPY-01, que a janela estável já pagou: a cópia
    tinha só o nome trocado e o resto virava default. O `model_copy` do pydantic
    leva gatilhos, luz, vibração, alto-falante, máscara e os overrides por
    controle — tudo, menos o nome.

    E A CÓPIA NÃO É ATIVADA. Duplicar não é trocar o perfil que está valendo; a
    coluna tem um "Ativar" para isso. Por isso `_gravar` não reaplica aqui: o
    nome novo nunca é o ativo.

    O NÚMERO NO FIM ("(cópia) 2") NÃO É ENFEITE: sem ele, duplicar duas vezes o
    mesmo perfil gravaria a segunda cópia POR CIMA da primeira — `save_profile`
    escreve por slug.
    """
    global _ESCOLHIDO
    from hefesto_dualsense4unix.profiles.loader import load_all_profiles, load_profile

    era = _perfil_do_editor(ctx)
    prof = load_profile(era)
    copia = _nome_livre(f"{prof.name} (cópia)", load_all_profiles())
    _gravar(prof.model_copy(update={"name": copia}), ctx, p)
    _ESCOLHIDO = copia


@gesto("10-perfis.html", "remover")
def remover(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Remover": apagar o perfil do disco. PERGUNTA ANTES, no rótulo do botão.

    É O GESTO MAIS DESTRUTIVO DESTA ABA, e tem TRÊS guardas, nesta ordem:

    1. **precisa de um perfil escolhido.** Sem ele, `_perfil_do_editor` recusa
       — nunca "o primeiro da lista".
    2. **não age sobre o perfil que está VALENDO.** Apagar o ativo deixaria o
       daemon aplicando um arquivo que não existe mais, e o produto já tem uma
       frase para esse risco (`frase_da_remocao_do_perfil_ativo`). Aqui a
       resposta é mais curta: recusa e diz para ativar outro antes.
    3. **pergunta.** O primeiro clique ARMA e levanta; o rótulo do botão vira
       a pergunta no tique seguinte (≤500 ms) e o segundo clique, dentro de
       oito segundos, apaga. Ver `_rotulo_do_remover` para por que a pergunta
       mora no rótulo e não num diálogo.

    O ARMAMENTO É POR PERFIL: escolher outra linha e clicar em Remover não
    aproveita a confirmação da anterior — seria a pior forma de perder o perfil
    errado.

    E O APAGADO TEM VOLTA: `delete_profile` arquiva a última versão em
    `profiles/.historico/<slug>/` antes do `unlink` (PERFIL-SEM-RASTRO-01,
    `loader.py:1601`). O caminho de volta hoje é a linha de comando —
    `hefesto-dualsense4unix profile restore <nome>` —, porque o "Voltar à de
    ontem" desta aba precisa do perfil na LISTA para escolhê-lo.
    """
    global _ARMADO, _ESCOLHIDO
    from hefesto_dualsense4unix.profiles.loader import delete_profile
    from hefesto_dualsense4unix.profiles.slug import mesmo_slug

    nome = _perfil_do_editor(ctx)
    ativo = str(ctx.state.get("active_profile") or "")
    if ativo and mesmo_slug(ativo, nome):
        raise ValueError(
            f"“{nome}” é o perfil que está valendo agora. Ative outro na lista "
            f"antes de apagar este — senão o Hefesto fica aplicando um arquivo "
            f"que não existe mais.")
    agora = time.monotonic()
    armado = (_ARMADO and _ARMADO[0] == nome
              and (agora - _ARMADO[1]) < SEGUNDOS_PARA_CONFIRMAR)
    if not armado:
        _ARMADO = (nome, agora)
        raise RuntimeError(
            f"Apagar “{nome}” do disco? Clique em Remover de novo para "
            f"confirmar — o botão espera oito segundos.")
    _ARMADO = None
    delete_profile(nome)
    _ESCOLHIDO = ""
    # SEM `profile.switch` AQUI, de propósito: o perfil apagado não é o ativo
    # (a guarda 2 garante), então não há o que reaplicar. O `launch_env`
    # precisa saber assim mesmo — o `steam_app_<id>.env` do perfil que morreu
    # fica rançoso se ninguém avisar (DEDUP-04, `profiles_actions.py:3199`).
    p.chamar("launch_env.refresh")


def _editor_de(prof: Any) -> dict[str, Any]:
    """Os campos do editor daquele perfil, pela porta da FRENTE do produto.

    `pacote_da_aba` é a função pública de `perfis_web`, e é a mesma que
    `pacote()` chama a cada tique. Ler `_pacote_do_editor` (privada) daria o
    mesmo dicionário com uma linha a menos e um acoplamento a mais; o que se
    quer daqui é justamente o que a TELA está mostrando, e a tela chama esta.

    O `ambiente_travado` que ela devolve é a válvula do R-12 — a razão de os
    dois gestos do editor consultarem isto antes de gravar.
    """
    editor: dict[str, Any] = _tela.pacote_da_aba(
        [prof], ativo=None, editado=prof)["editor"]
    return editor


#: OS DOIS QUE CONTINUAM SEM DONO, e o motivo de cada um é MEDIDO.
#:
#:   recarregar    NÃO HÁ O QUE CHAMAR. A dica dela diz "Relê a lista do disco.
#:                 Não descarta o que está no editor ao lado" — e a lista já é
#:                 relida do disco a cada tique de 500 ms, em `pacote()`, por
#:                 `load_all_profiles()`. Ligar este botão a um `load_all` extra
#:                 seria um botão que finge trabalho que já está feito. O que
#:                 falta não é motor: é o botão sair do desenho, e isso é dela.
#:   editor.estilo NÃO EXISTE EM LUGAR NENHUM, e o produto já o declara assim:
#:                 `perfis_web.GESTOS_SEM_MOTOR["editor.estilo"]` diz *"não
#:                 existe campo de Estilo de Jogo no perfil, nem preset que o
#:                 resolva"*. Conferido em 01/09/2026: não há campo em
#:                 `profiles/schema.Profile`, não há chave em
#:                 `SIMPLE_MATCH_PRESETS` e os quinze estilos do desenho não têm
#:                 arquivo atrás. Quem lhe dá motor é a ONDA-PERFIS-04.
#:                 A tela não mente mais sobre ele: com `data-hef-alvo="valor"`
#:                 e o valor vazio, o seletor abre em BRANCO em vez de dizer
#:                 "Luta" para todo perfil.
PONTE = {"profile_switch", "chamar"}
METODOS = {"launch_env.refresh"}


PAGINA = "10-perfis.html"
PISO_DA_ABA = 10
#: SÓ UMA PROVA DECLARADA PARA DEZ GESTOS, e a razão é estrutural, não
#: preguiça: os outros nove agem sobre o perfil ESCOLHIDO, e o `ctx` desta
#: régua é fixo — `active_profile="regua"`, sem `_ESCOLHIDO` (um gesto que
#: dependesse do estado deixado por outro teste seria pior que não ter prova).
#: MEDIDO em 01/09/2026, no mesmo lar de mentira que o `conftest.py` monta:
#: `load_all_profiles()` devolve **9 perfis** — os de fábrica, que ela mesma
#: semeia — e nenhum se chama "regua". Cada um dos nove levanta
#: `FileNotFoundError` no `load_profile("regua")`, antes de tocar a ponte.
#:
#: NÃO É "a pasta de perfis é vazia", que foi o que a primeira leva escreveu
#: aqui: essa medição usou `perfil.lista()`, que lê a pasta sem semear. A
#: pasta que `pacote()` enxerga tem nove.
#:
#: ELES FORAM PROVADOS, e não por leitura: com uma pasta de perfis DE VERDADE
#: num diretório temporário, três perfis dela copiados, e um dublê de ponte
#: igual ao desta régua — os números estão no relato desta leva, gesto a gesto,
#: com a mordida de cada um.
PROVAS: list[dict[str, Any]] = [
    {"pagina": PAGINA, "gesto": "ativar", "clique": {"texto": "Ação"},  # (noqa-acento) id
     "chama": [("profile_switch", ["Ação"], {})]},
]

#: O QUE NÃO ECOA NO `state_full`, e são NOVE dos dez. A razão é uma só e está
#: no alto deste arquivo: **o daemon não guarda perfil, o disco guarda**. Ele
#: publica `active_profile` (um nome) e mais nada sobre o conteúdo — renomear,
#: duplicar, apagar, trocar a regra do jogo, restaurar a versão de ontem: nada
#: disso aparece nas 49 chaves que ele devolve. O efeito se vê na LISTA desta
#: aba, que `pacote()` relê do disco a cada tique.
#:
#: `selecionar` é o único que não fala com ninguém, e é de propósito: escolher
#: uma linha muda o ALVO dos botões ao lado, na memória desta janela. Se
#: trocasse o perfil que está valendo, a coluna não precisaria de um "Ativar".
#:
#: E ISSO MUDA A PROVA de quase todos: eles agem sobre o perfil ESCOLHIDO, e
#: uma régua que os clicasse em ordem alfabética — sem `selecionar` antes —
#: veria nove recusas em vez de nove gestos.
SEM_ECO = ("selecionar", "editor.nome", "editor.ambiente", "editor.jogo",
           "detectar", "novo", "duplicar", "remover", "voltar-a-de-ontem")
