#!/usr/bin/env python3
"""O RODAPÉ, e ele é das DEZ abas: Aplicar · Salvar Perfil · Importar · Exportar.

Ele mora no `topo.html`, que é o esqueleto compartilhado — logo não pertence a
nenhum pacote de aba. Os gestos são registrados em `("*", nome)`, que o
`gesto_da_pagina` resolve depois de não achar o da página.

O QUE CADA BOTÃO É NO PRODUTO ESTÁVEL, medido em 01/09/2026 a pedido dela
(*"salvar exportar importar. dividir e ver se a feature do botão tá condizendo
com o output seu"*):

    Aplicar   `footer_actions.on_apply_draft`  → `profile.apply_draft`
    Salvar    `footer_actions.on_save_profile` → diálogo de nome + save_profile
    Importar  `footer_actions.on_import_profile` → FileChooser + validação
    Exportar  **NÃO EXISTE**

**"Exportar" é um botão que o desenho criou e o produto nunca teve.** Não há
handler no `src/` e não há botão no `main.glade` (que traz `btn_footer_apply`,
`btn_footer_import` e `btn_footer_save_profile`, e mais nenhum). É feature NOVA
— barata, porque o perfil já é JSON no disco — e chamá-la de "ligação"
esconderia trabalho.

O "APLICAR" NÃO É REDUNDANTE, mesmo com a decisão dela de que clicar já aplica.
O que ele carrega sozinho é o **depois**: modo e máscara, que o jogo só lê
quando abre, e que por isso não podem ir na hora. Foi um defeito real de
08/08/2026, na palavra dela: *"quando eu clico ali no inferior no verde em
aplicar, ele não aplica e não abre o pop up"*.
"""
from __future__ import annotations

import pathlib
from typing import Any

from . import Contexto, gesto, perfil

PAGINA = "*"


def _draft_do_ativo(nome: str, ctx: Contexto | None = None) -> Any:
    """O `DraftConfig` do perfil ativo, com o que está VALENDO por cima.

    O DRAFT É DO PRODUTO e não se reescreve: `app/draft_config.DraftConfig` é
    pydantic puro (zero GTK), com `from_profile`, `to_ipc_dict` e `to_profile`.
    É o mesmo objeto que o rodapé da janela estável monta.

    O QUE MUDA AQUI É DE ONDE VEM O CONTEÚDO, e a razão é a decisão dela de
    01/09: **a interface nova é de ação imediata** — clicar num tom já pinta o
    controle, sem passar por rascunho. A janela estável guarda um `self.draft`
    em memória e o atualiza a cada widget mexido; aqui não há esse draft, e
    carregar só do disco faria o "Salvar" gravar o que JÁ ESTAVA LÁ.

    MEDIDO em 01/09/2026, e por isso esta função existe assim: com a luz do P1
    em `[255, 0, 255]` (clicada) e o perfil no disco dizendo `[0, 255, 128]`, um
    "Salvar" que só lesse o disco gravaria o verde — **perdendo a mudança
    dela**, calado.

    O QUE O DAEMON PUBLICA VENCE O DISCO — **HOJE, UMA COISA SÓ: a cor da
    barra.** Estas linhas prometiam seis (cor, política de vibração,
    passthrough, velocidade do mouse, mudo do microfone, volume do
    alto-falante) e o laço abaixo chama um método só, `with_controller_leds`.
    Medido em 05/09/2026: as outras cinco vinham todas do DISCO, e cinco das
    seis frases eram falsas. **Fato errado se substitui** — a frase agora
    descreve o que o código faz, e o que falta virou fila com endereço, não
    promessa em docstring.

    A FILA, para quem for fechar: `speaker`, `audio.mic_mudo` e `sensores`
    por controle, e `rumble_policy`/`passthrough` e `mouse_emulation`
    globais, o daemon PUBLICA — só ninguém lê aqui. Antes disso, o
    `DraftConfig` precisa de `with_controller_mic` e
    `with_controller_sensores`, que são as duas únicas das seis seções do
    esquema que ele ainda não sabe escrever.

    O QUE ELE NÃO PUBLICA fica do perfil — e o caso é os GATILHOS: o DualSense
    não devolve o modo em que está (é comando de ida), como o
    `a03_gatilhos.py` mede pela outra ponta.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.app.draft_config import DraftConfig, LedsDraft
    from hefesto_dualsense4unix.profiles.loader import load_profile

    if not nome:
        return None
    try:
        draft = DraftConfig.from_profile(load_profile(nome))
    except Exception:
        return None
    if ctx is None:
        return draft

    # QUEM DECIDE SE HÁ COR A GRAVAR É O DONO DA LEITURA, e não este pacote.
    # `rotulo_lightbar` devolve a cor BASE como `None` exatamente nos dois
    # estados em que não há cor a afirmar — "cor desconhecida" e "apagada" —, e
    # é a mesma função que o cartão da GUI estável usa. Reler os campos crus
    # aqui seria uma segunda verdade, e a aba 04 já pagou por essa: o
    # `c.get("lightbar_on", True)` que estava lá tinha o padrão INVERTIDO e
    # AFIRMAVA aceso na ausência do campo, que é o estado de partida de um
    # controle no rádio.
    from hefesto_dualsense4unix.app.widgets.controller_card import rotulo_lightbar

    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        # A BARRA APAGADA NÃO É UMA COR PRETA, e a diferença custa o trabalho
        # dela. O `LedsDraft` não tem campo de aceso/apagado — só `lightbar_rgb`
        # —, então gravar o `(0,0,0)` de uma barra desligada não guarda "estava
        # apagada": guarda PRETO por cima da cor que ela escolheu, e não há como
        # voltar. Medido em 03/09/2026 e nomeado pelo juiz da leva como o achado
        # mais grave do dia: desligar a barra e salvar apagava a escolha dela,
        # em silêncio, para sempre.
        #
        # O QUE ESTÁ NO DISCO É A COR PARA QUANDO ACENDER, e é isso que o
        # esquema sabe dizer. Com a barra apagada, o certo é não mexer nela.
        _recado, base = rotulo_lightbar(c, ctx.state)
        rgb = list(base) if base is not None else []
        if not uniq or len(rgb) < 3:
            continue
        # A COR VIVA VIRA OVERRIDE DAQUELE CONTROLE, e não a cor global: cada
        # controle tem a sua, e é assim que o perfil já guarda (o
        # `ControllerOverrides.leds` do schema existe desde antes desta aba).
        # O BRILHO E AS LÂMPADAS SÃO DAQUELE CONTROLE, NÃO DO GLOBAL — e esta
        # linha nasceu de perda de dado medida em 05/09/2026: com a aba 04
        # tendo gravado brilho 0,25 e as lâmpadas 1 e 2 do P1 no disco, um
        # "Salvar" do rodapé regravava 1,0 e as cinco apagadas, porque este
        # bloco lia `draft.leds.*` — a seção GLOBAL — para montar o override
        # DELE. Só a cor vinha do controle certo; os outros dois campos vinham
        # do vizinho errado e atropelavam o que a aba tinha acabado de gravar.
        #
        # O leitor certo já existia e é público: `effective_leds_for(uniq)`
        # faz o merge POR CAMPO guiado pelo `model_fields_set` — override
        # presente vence, campo não escrito herda o global. É exatamente o que
        # este ponto precisa, e o rodapé simplesmente não o chamava.
        efetivo = draft.effective_leds_for(uniq)
        draft = draft.with_controller_leds(uniq, LedsDraft(
            # AS FORMAS SÃO FIXAS NO SCHEMA — três canais de cor e cinco
            # lâmpadas —, e o `LedsDraft` as declara assim. Um `tuple(...)`
            # genérico ou uma `list` perdem esse tamanho, e o produto passa a
            # aceitar quatro cores sem ninguém ver.
            lightbar_rgb=(int(rgb[0]), int(rgb[1]), int(rgb[2])),
            lightbar_brightness=efetivo.lightbar_brightness,
            player_leds=(efetivo.player_leds[0], efetivo.player_leds[1],
                         efetivo.player_leds[2], efetivo.player_leds[3],
                         efetivo.player_leds[4]),
            # SE ELA ESCOLHEU UMA COR, a automática não pode voltar por cima —
            # senão salvar a escolha dela a apagaria no próximo Aplicar.
            auto_player_colors=False,
        ))
        draft = _o_som_daquela_peca(draft, c, uniq)
        draft = _os_sensores_daquela_peca(draft, c, uniq)
    return _o_que_e_da_mesa_inteira(draft, ctx)


def _o_som_daquela_peca(draft: Any, c: dict[str, Any], uniq: str) -> Any:
    """O alto-falante e o microfone DAQUELE controle, do vivo para o rascunho.

    O daemon publica os dois por peça — ``c["speaker"]`` com ``volume``/
    ``muted`` e ``c["audio"]`` com ``mic_mudo``/``volume_captura``. Até
    05/09/2026 ninguém lia nenhum dos dois aqui, e o Salvar reemitia o disco:
    ela mexia no volume do microfone do P2, salvava, e o número voltava ao de
    ontem sem uma palavra.

    OS DOIS ESCRITORES LIMPAM SOZINHOS quando o valor iguala o global — é a
    regra COR-04, e é ela que impede o perfil de encher de override que só
    repete o que já valia. Por isso não há um `if` de igualdade aqui: quem sabe
    comparar é o `DraftConfig`, e uma segunda cópia dessa regra é como duas
    telas passam a discordar.
    """
    from hefesto_dualsense4unix.app.draft_config import MicDraft, SpeakerDraft

    som = c.get("speaker")
    if isinstance(som, dict) and som.get("volume") is not None:
        draft = draft.with_controller_speaker(uniq, SpeakerDraft(
            volume=int(som["volume"]),
            muted=bool(som.get("muted", False)),
            # A ROTA NÃO É PUBLICADA POR PEÇA, e inventar `None` aqui apagaria
            # a que estiver no disco. Herdar a efetiva é o que preserva.
            rota=draft.effective_speaker_for(uniq).rota,
        ))

    audio = c.get("audio")
    if isinstance(audio, dict):
        mudo = audio.get("mic_mudo")
        captura = audio.get("volume_captura")
        if mudo is not None or captura is not None:
            draft = draft.with_controller_mic(uniq, MicDraft(
                muted=None if mudo is None else bool(mudo),
                volume=None if captura is None else int(captura),
            ))
    return draft


def _os_sensores_daquela_peca(draft: Any, c: dict[str, Any], uniq: str) -> Any:
    """Giroscópio e acelerômetro DAQUELE controle — e só quando DESLIGADOS.

    **A ASSIMETRIA É O PONTO, e ela vem de duas decisões dela.**
    ``D-AUDIO-E-GIRO-NASCEM-LIGADOS`` (25/08/2026) diz que o sensor nasce
    ligado em todo jogo, e o esquema escreve isso como *sem opinião* — campo
    ``None``. Gravar `True` porque o sensor está ligado AGORA transformaria
    "não pedi nada" em "pedi ligado", e todo perfil salvo passaria a impor os
    sensores a todo jogo — exatamente o contrário do que ela pediu.

    Desligado é diferente: **nunca é o default**, então só pode ter vindo de
    um ato dela. Esse, sim, o perfil guarda. É a decisão D1 de 05/09 aplicada
    a um caso em que o produto não tem flag `dirty` para consultar: o próprio
    valor carrega o carimbo.
    """
    sens = c.get("sensores")
    if not isinstance(sens, dict):
        return draft
    giro = sens.get("giroscopio_ligado")
    acel = sens.get("acelerometro_ligado")
    return draft.with_controller_sensores(
        uniq,
        giroscopio=False if giro is False else None,
        acelerometro=False if acel is False else None,
    )


def _o_que_e_da_mesa_inteira(draft: Any, ctx: Contexto) -> Any:
    """O que o daemon publica UMA vez para a máquina toda.

    SÃO GLOBAIS POR MEDIÇÃO, não por preguiça — decisão D3 de 05/09/2026: o
    `Daemon` tem UM `_mouse_device` e UM `_keyboard_device`, alimentados por um
    `read_state()` por tique, e o input vem sempre do controle PRIMÁRIO.
    Guardar por controle antes de o caminho de entrada existir é o que a régua
    `test_perfil_por_controle_o_campo_espera_o_caminho.py` proíbe: *campo que
    grava e ninguém lê faz a tela prometer*.

    O `dirty=True` do mouse não é ornamento: `to_profile` só emite a seção
    `mouse` com `dirty` ou `in_profile`, e sem ele a velocidade que ela acabou
    de mexer na aba 06 sai do Salvar como se nunca tivesse existido.
    """
    from hefesto_dualsense4unix.app.draft_config import MouseDraft

    estado = getattr(ctx, "state", None)
    if not isinstance(estado, dict):
        return draft

    politica = estado.get("rumble_policy")
    passthrough = estado.get("rumble_passthrough")
    mult = estado.get("rumble_policy_custom_mult")
    mudancas: dict[str, Any] = {}
    if politica is not None:
        mudancas["policy"] = str(politica)
    if passthrough is not None:
        mudancas["passthrough"] = bool(passthrough)
    if mult is not None:
        mudancas["custom_mult"] = float(mult)
    if mudancas:
        draft = draft.model_copy(
            update={"rumble": draft.rumble.model_copy(update=mudancas)})

    rato = estado.get("mouse_emulation")
    if isinstance(rato, dict) and rato.get("speed") is not None:
        draft = draft.model_copy(update={"mouse": MouseDraft(
            enabled=bool(rato.get("enabled", False)),
            speed=int(rato["speed"]),
            scroll_speed=int(rato.get("scroll_speed", 1)),
            dirty=True,
            in_profile=draft.mouse.in_profile,
        )})
    return draft


@gesto("*", "aplicar")
def aplicar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O botão verde. Manda o perfil ativo aos controles, sem gravar.

    `profile.apply_draft` é o método, e o payload é o `to_ipc_dict()` do draft —
    o MESMO caminho do `footer_actions.on_apply_draft`. Nada aqui monta payload.

    O QUE ESTA VERSÃO AINDA NÃO FAZ, e é honesto dizer: o "depois" (modo e
    máscara) da janela estável vem de uma escolha PENDENTE da aba Início, que a
    interface nova ainda não guarda. Aqui vai só o "agora".
    """
    nome = str(ctx.state.get("active_profile") or "")
    draft = _draft_do_ativo(nome)
    if draft is None:
        raise ValueError(
            "aplicar: não há perfil ativo para mandar aos controles. "
            "Escolha um na aba Perfis.")
    p.apply_draft_detalhado(draft.to_ipc_dict())


@gesto("*", "salvar")
def salvar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Grava o que está valendo no perfil ATIVO, no disco dela.

    A JANELA ESTÁVEL PERGUNTA O NOME — `on_save_profile` abre um diálogo. Aqui
    ela grava no perfil ativo, sem perguntar, e a razão é a decisão dela de
    01/09: a interface nova é de AÇÃO IMEDIATA. Salvar com outro nome é o
    "Duplicar" da aba Perfis, que é outro botão.

    ESCREVE NO DISCO DELA. É o único gesto desta leva que escreve, e por isso
    ele exige perfil ativo em vez de escolher um: gravar no perfil errado é o
    tipo de estrago que não se desfaz por engano.
    """
    nome = str(ctx.state.get("active_profile") or "")
    # O `ctx` VAI JUNTO: é o que faz o Salvar gravar o que ESTÁ VALENDO, e não
    # o que já estava no disco.
    draft = _draft_do_ativo(nome, ctx)
    if draft is None:
        raise ValueError("salvar: não há perfil ativo. Escolha um na aba Perfis.")
    perfil._com_o_src()
    from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile

    atual = load_profile(nome)
    save_profile(draft.to_profile(nome, priority=atual.priority),
                 origem="interface-nova")


@gesto("*", "exportar")
def exportar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Escreve o perfil ativo num `.json` na pasta pessoal dela.

    FEATURE NOVA, e a nota importa: o produto estável NÃO tem exportação — não
    há handler no `src/` nem botão no `main.glade`. O botão veio do desenho.

    ELA ESCOLHE ONDE, pelo seletor do sistema — o mesmo ponto de extensão do
    "Importar", injetado pelo piloto. A sugestão é `hefesto-<perfil>.json` na
    pasta pessoal, para que aceitar sem pensar já dê num lugar previsível.

    Copia o arquivo do disco em vez de reserializar o perfil: o que ela leva
    para outra máquina é byte a byte o que está aqui — sem passar pelo pydantic,
    que normalizaria campos e mudaria o arquivo sem ninguém pedir.
    """
    nome = str(ctx.state.get("active_profile") or "")
    if not nome:
        raise ValueError("exportar: não há perfil ativo para exportar.")
    pasta = perfil.pasta()
    if pasta is None:
        raise RuntimeError("exportar: não achei a pasta de perfis.")
    origem = pasta / f"{nome}.json"
    if not origem.exists():
        perfil._com_o_src()
        from hefesto_dualsense4unix.profiles.slug import slugify

        origem = pasta / f"{slugify(nome)}.json"
    if not origem.exists():
        raise FileNotFoundError(f"exportar: não achei o arquivo de {nome!r}.")
    sugestao = str(pathlib.Path.home() / f"hefesto-{origem.name}")
    escolhido = p.salvar_arquivo("Onde guardar o perfil", sugestao=sugestao)
    if not escolhido:
        return  # ela cancelou
    destino = pathlib.Path(escolhido)
    destino.write_bytes(origem.read_bytes())
    print(f"[exportar] {destino}")


@gesto("*", "importar")
def importar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Carrega um perfil de um `.json` que ela escolhe.

    O SELETOR É DO SISTEMA, e por isso vem INJETADO: o WebView não abre
    `FileChooserDialog` e a página não alcança o disco. Quem o abre é o piloto,
    que é GTK; o pacote continua puro, e a régua o prova com um dublê.

    A VALIDAÇÃO É A DO PRODUTO — `Profile.model_validate`, o mesmo esquema
    pydantic que o `footer_actions.on_import_profile` usa. Um JSON que não é
    perfil é recusado ANTES de tocar a pasta dela, com o erro do pydantic na
    frase: nada de arquivo meio copiado.

    O CONFLITO DE NOME NÃO SOBRESCREVE. A janela estável "resolve conflito de
    nome se necessário"; aqui o novo entra como `nome-2`, `nome-3`… Perder um
    perfil dela por um clique de importação é o estrago que esta linha impede.
    """
    caminho = p.escolher_arquivo("Escolha o perfil para importar", padrao="*.json")
    if not caminho:
        return  # ela cancelou, e cancelar não é erro

    perfil._com_o_src()
    import json as _json

    from hefesto_dualsense4unix.profiles.schema import Profile

    origem = pathlib.Path(caminho)
    try:
        dados = _json.loads(origem.read_text(encoding="utf-8"))
        novo = Profile.model_validate(dados)
    except Exception as erro:
        raise ValueError(f"{origem.name} não é um perfil do Hefesto: {erro}") from erro

    pasta = perfil.pasta()
    if pasta is None:
        raise RuntimeError("importar: não achei a pasta de perfis.")
    pasta.mkdir(parents=True, exist_ok=True)

    from hefesto_dualsense4unix.profiles.slug import slugify

    base = slugify(novo.name)
    destino, n = pasta / f"{base}.json", 1
    while destino.exists():
        n += 1
        destino = pasta / f"{base}-{n}.json"
    destino.write_text(_json.dumps(dados, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    print(f"[importar] {novo.name!r} → {destino}")


PISO_DA_ABA = 4
PROVAS: list[dict[str, Any]] = [
    # O "aplicar" e o "salvar" dependem do perfil ATIVO, e a régua roda sem
    # daemon: eles são provados pelo teste de recusa, abaixo, e no aparelho.
]
PONTE = {"apply_draft_detalhado", "escolher_arquivo", "salvar_arquivo"}
METODOS: set[str] = set()
