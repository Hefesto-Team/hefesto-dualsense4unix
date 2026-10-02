#!/usr/bin/env python3
"""O RODAPÉ, e ele é das DEZ abas: Aplicar · Salvar Perfil · Importar · Exportar.

Ele mora no `topo.html`, que é o esqueleto compartilhado — logo não pertence a
nenhum pacote de aba. Os gestos são registrados em `("*", nome)`, que o
`gesto_da_pagina` resolve depois de não achar o da página.

O QUE CADA BOTÃO É NO PRODUTO ESTÁVEL, medido em 01/09/2026 a pedido dela
(*"salvar exportar importar. dividir e ver se a feature do botão tá condizendo
com o output seu"*):

    Aplicar   `footer_actions.on_apply_draft`  → `profile.apply_draft`
              (aqui, desde 01/10/2026: `profile.reaplicar`, a cadeia da ativação)
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

A CARONA DO ATALHO DE INICIALIZAÇÃO — QUEM PEGA E QUEM NÃO PEGA (06/09/2026)
---------------------------------------------------------------------------
Decisão dela, `07-Q1`: *"Deve aplicar automaticamente como era no gtk"* — e o
desenho é dela desde 16/08: *"nem precisa ter um botão na gui, mas ele se auto
corrigir ao clicarmos em aplicar ou salvar o perfil seja dentro ou fora da guia
de perfis."* Quem repõe é `perfil.com_a_carona()`, atrás do `carona.ligada()`
do dono. A notícia (quando há) vai ao diário da janela e não à tela — desde
13/09/2026, ver `_recado`.

=========  =======  ==========================================================
gesto      carona?  a razão
=========  =======  ==========================================================
Aplicar    SIM      manda o perfil aos controles; sem o atalho o jogo continua
                    sem enxergar o controle
Salvar     SIM      grava o perfil no disco dela — o "salvar" literal do
                    pedido
Importar   SIM      um perfil novo entra na pasta e passa a valer
Exportar   não      copia um arquivo para FORA (`origem.read_bytes()`) e não
                    toca o perfil ativo: não há nada a repor
=========  =======  ==========================================================

**E a carona não muda o desfecho do gesto**: ela roda DEPOIS do trabalho dar
certo, nunca antes, e `com_a_carona` nunca levanta. Uma exceção ali
transformaria uma gravação bem-sucedida em tarja de recusa.

OS DOIS DE FORA NA JANELA ESTÁVEL CONTINUAM DE FORA AQUI, pelas razões medidas
do dono (`app/actions/carona_do_wrapper.py:62-80`): o **«Aplicar aos jogos da
Steam»** já É a aplicação em massa e tem uma máquina que a sentinela não tem
(pedir consentimento para fechar a Steam) — trocá-la seria regressão; e o
**AUTOSWITCH** aplica perfil exatamente quando o jogo está SUBINDO, que é a
condição em que escrever a linha da Steam é jogar o reparo fora.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

from . import Contexto, gesto, perfil

PAGINA = "*"

def _recado(frase: str) -> None:
    """A notícia da carona vai ao DIÁRIO da janela — e não mais à tela.

    ATÉ 13/09/2026 ELA IA AO CARTÃO, como `{"recado": …}` pelo canal de sucesso
    do piloto (a D-01). Ela mandou tirar, com a foto deste rodapé: *"essas
    frases de status que aparecem no rodapé isso não deveria estar
    aparecendo"*, *"em todas as abas da interface"* (TELA-CALADA-01). Medido no
    piloto oculto antes da cura: o «Aplicar» com um jogo sem o atalho escrevia
    a frase na faixa da 01, no cartão do P1 da 02 — onde ela já chegava vinda
    da 01 — e na faixa da 05.

    QUEM REPÕE O ATALHO É A CARONA, NÃO A FRASE: os três gestos continuam
    chamando `perfil.com_a_carona()` e o `localconfig.vdf` continua consertado.
    O que muda é só a notícia, que sai no `interface.log` como `[relato]`. O
    "deu certo" na tela é a piscada verde de ~1,5 s no botão (decisão dela,
    `03-Q4`).

    UM LUGAR SÓ para os três gestos do rodapé: a terceira cópia de um `print` é
    a que esquece o `strip()` e relata uma linha vazia.
    """
    frase = frase.strip()
    if frase:
        print(f"[relato] rodapé · carona: {frase}", file=sys.stderr)


def _draft_do_ativo(nome: str) -> Any:
    """O `DraftConfig` do perfil `nome`, lido do disco e só dele."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.app.draft_config import DraftConfig
    from hefesto_dualsense4unix.profiles.loader import load_profile

    if not nome:
        return None
    try:
        return DraftConfig.from_profile(load_profile(nome))
    except Exception:
        return None


# dos três lê `ctx.state["active_profile"]` cru. A-PERNA-QUE-FALTA-01,
# deste lado `perfil.nome_do_ativo`). O estado cru só tem a primeira.
# E A SEGUNDA PERNA NÃO É HIPÓTESE: `nome_do_ativo` documenta, medido em
@gesto("*", "aplicar")
def aplicar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O botão verde. Manda o perfil ativo INTEIRO aos controles, sem gravar."""
    from .a04_iluminacao import sem_resposta_do_daemon

    nome = perfil_do_rodape(ctx.state)
    if not nome:
        raise ValueError(
            "aplicar: não há perfil ativo para mandar aos controles. "
            "Escolha um na aba Perfis.")
    if p.profile_reaplicar(nome) is None:
        raise RuntimeError(sem_resposta_do_daemon())
    perfil.a_volta_do_perfil(ctx, p)
    _recado(perfil.com_a_carona())
    return None


@gesto("*", "salvar", grava="gravar_e_reaplicar")
def salvar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Regrava o perfil ATIVO como o disco o tem, normalizado, e roda a carona.

    O MESMO RASCUNHO DO «APLICAR», EM TODA ABA (:func:`_draft_do_ativo`), e
    nunca o aparelho: cada escolha dela já foi ao disco no gesto que a fez
    (decisão D2 de 05/09). O que sobra ao Salvar é a rede de segurança dessa
    decisão: validar, migrar e escrever o arquivo na forma de hoje. Salvar duas
    vezes grava o mesmo arquivo. Decisão `D-2709-O-SALVAR-LE-O-PERFIL`.

    A JANELA ESTÁVEL PERGUNTA O NOME; aqui ele grava no perfil ativo, sem
    perguntar (a interface nova é de ação imediata, decisão dela de 01/09).
    Salvar com outro nome é o "Duplicar" da aba Perfis.

    SEM PERFIL ATIVO E SEM ESCOLHA, RECUSA apontando a aba Perfis
    (:func:`perfil_do_rodape`, sem a perna do Freestyle desde 01/10/2026).

    PELO FUNIL DOS GESTOS DE CAMPO, desde 02/10/2026
    (O-APLICAR-E-O-SALVAR-JA-ATUALIZAM-01): :func:`perfil.gravar_e_reaplicar`
    grava, reaplica o perfil quando ele é o que vale, e avisa o lançamento. Até
    aqui o Salvar ia ao `save_profile` direto e não falava com o daemon: o
    arquivo mudava e o controle seguia com o que tinha. Depois, a volta
    (:func:`perfil.a_volta_do_perfil`), como o «Aplicar» e o «Importar».
    """
    nome = perfil_do_rodape(ctx.state)
    draft = _draft_do_ativo(nome)
    if draft is None:
        raise ValueError("salvar: não há perfil ativo. Escolha um na aba Perfis.")
    perfil.gravar_e_reaplicar(
        draft.to_profile(nome, priority=draft.source_priority), ctx, p)
    perfil.a_volta_do_perfil(ctx, p)
    _recado(perfil.com_a_carona())
    return None


def perfil_do_rodape(state: Any) -> str:
    """O perfil dos três gestos do rodapé: o ativo, ou a escolha dela.

    O-MODO-FREESTYLE-02, 24/09/2026: nasceu `perfil_do_salvar` e servia só ao
    Salvar; agora os três perguntam aqui. `perfil.nome_do_ativo` responde as
    duas pernas: o daemon, depois o disco — e a perna do disco é a escolha dela
    (`utils.session.a_escolha_dela`, pela `perfil_que_esta_valendo`). `""`
    quando as duas dizem "ninguém": a recusa de cada gesto continua dizendo o
    que fazer.

    NOTA DATADA — 01/10/2026, item 10 da `D-2909-O-HEFESTO-ABRE-NA-ESCOLHA-
    DELA`: havia uma terceira perna, o Freestyle (`loader.o_perfil_de_fora_do_
    jogo`), quando as duas calavam. Com «sem escolha» o chip diz «—», e o
    «Aplicar», o «Salvar» e o «Exportar» mirariam o Freestyle — e um «Aplicar»
    que o reativasse poria o Freestyle desligado como o perfil ativo. Saiu.

    NUNCA LEVANTA: as dicas do rodapé perguntam o mesmo a cada tique.
    """
    return perfil.nome_do_ativo(state)


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

    SEM PERFIL ATIVO, EXPORTA O «FREESTYLE» (:func:`perfil_do_rodape`).
    """
    nome = perfil_do_rodape(ctx.state)
    if not nome:
        raise ValueError("exportar: não há perfil ativo para exportar.")
    pasta = perfil.pasta()
    if pasta is None:
        raise RuntimeError("exportar: não achei a pasta de perfis.")
    origem = perfil.arquivo(nome, pasta)
    if origem is None:
        raise FileNotFoundError(f"exportar: não achei o arquivo de {nome!r}.")
    sugestao = str(pathlib.Path.home() / f"hefesto-{origem.name}")
    escolhido = p.salvar_arquivo("Onde guardar o perfil", sugestao=sugestao)
    if not escolhido:
        return
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

    DEPOIS DE GRAVAR, A VOLTA (:func:`perfil.a_volta_do_perfil`, 02/10/2026),
    como o «Salvar»: todo botão do rodapé que grava perfil termina igual (a
    resposta 44 dela na O-APLICAR-E-O-SALVAR-JA-ATUALIZAM-01).
    """
    caminho = p.escolher_arquivo("Escolha o perfil para importar", padrao="*.json")
    if not caminho:
        return None

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
    perfil.a_volta_do_perfil(ctx, p)
    _recado(perfil.com_a_carona())
    return None


PISO_DA_ABA = 4
PROVAS: list[dict[str, Any]] = [
]
PONTE = {"profile_reaplicar", "escolher_arquivo", "salvar_arquivo",
         "chamar", "resultado"}
METODOS: set[str] = {"launch_env.refresh", "coop.sync", "identity.renumber"}
