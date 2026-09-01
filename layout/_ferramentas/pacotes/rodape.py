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

from . import Contexto, gesto, perfil

PAGINA = "*"


def _draft_do_ativo(nome: str):
    """O `DraftConfig` do perfil ativo, ou `None`.

    O DRAFT É DO PRODUTO e não se reescreve: `app/draft_config.DraftConfig` é
    pydantic puro (zero GTK), com `from_profile`, `to_ipc_dict` e `to_profile`.
    É o mesmo objeto que o rodapé da janela estável monta.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.app.draft_config import DraftConfig
    from hefesto_dualsense4unix.profiles.loader import load_profile

    if not nome:
        return None
    try:
        return DraftConfig.from_profile(load_profile(nome))
    except Exception:
        return None


@gesto("*", "aplicar")
def aplicar(ctx: Contexto, o: dict, p) -> None:
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
def salvar(ctx: Contexto, o: dict, p) -> None:
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
    draft = _draft_do_ativo(nome)
    if draft is None:
        raise ValueError("salvar: não há perfil ativo. Escolha um na aba Perfis.")
    perfil._com_o_src()
    from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile

    atual = load_profile(nome)
    save_profile(draft.to_profile(nome, priority=atual.priority),
                 origem="interface-nova")


@gesto("*", "exportar")
def exportar(ctx: Contexto, o: dict, p) -> None:
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
        from hefesto_dualsense4unix.profiles.loader import slugify

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
def importar(ctx: Contexto, o: dict, p) -> None:
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

    from hefesto_dualsense4unix.profiles.loader import slugify

    base = slugify(novo.name)
    destino, n = pasta / f"{base}.json", 1
    while destino.exists():
        n += 1
        destino = pasta / f"{base}-{n}.json"
    destino.write_text(_json.dumps(dados, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    print(f"[importar] {novo.name!r} → {destino}")


PISO_DA_ABA = 4
PROVAS = [
    # O "aplicar" e o "salvar" dependem do perfil ATIVO, e a régua roda sem
    # daemon: eles são provados pelo teste de recusa, abaixo, e no aparelho.
]
PONTE = {"apply_draft_detalhado", "escolher_arquivo", "salvar_arquivo"}
METODOS: set[str] = set()
