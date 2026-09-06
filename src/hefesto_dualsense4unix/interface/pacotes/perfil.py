#!/usr/bin/env python3
"""O PERFIL ATIVO, lido de quem já é dono dele — `profiles/loader.py`.

POR QUE ESTE ARQUIVO EXISTE, e ele nasceu de um erro meu que ela pegou em
01/09/2026 com uma pergunta só: *"vc tá corrigindo na origem esses problemas que
tá relatando né?"*

A resposta era NÃO. Eu tinha escrito dezessete valores `sem_dono` — travessões
na tela, com uma frase explicando que o produto não sabia aquilo. **Doze deles
tinham dono**, e o dono era o perfil:

    triggers.left.mode/params      o modo e os ajustes do L2      5/33 perfis
    triggers.right.mode/params     idem, R2                       5/33 perfis
    leds.lightbar_brightness       o brilho da barra             33/33 perfis
    mouse.speed / scroll_speed     a velocidade do cursor         1/33 perfis
    key_bindings                   os gestos                      1/33 perfis

O ERRO TEVE UMA FORMA SÓ, e é a que o `CLAUDE.md` já nomeia — *a casa sabe e o
produto não faz*: **perguntei só ao `state_full` do daemon.** Ele não publica
gatilho nem brilho; concluí "não tem dono" e escrevi o travessão. O dado estava
no disco dela o tempo todo, e a `gui/aba_*.py` que ela usa hoje já o lê.

O QUE O PERFIL É, e a distinção muda o que a tela deve dizer: ele é o que está
**salvo**, não o que está **aplicado**. Para a cor da barra isso importa — o
daemon publica a cor viva, e ela vence. Para o gatilho não existe escolha: o
DualSense **não devolve** o modo em que está (é comando de ida, e o
`docs/data/mapa-controles.csv` diz o mesmo pela outra ponta). Logo o perfil é a
melhor fonte que existe, e mostrar `Rigid` é mais verdadeiro que mostrar `—`.

QUEM LÊ NÃO ESCREVE. As funções de leitura são puras; **duas** funções no fim do
arquivo escrevem, e as duas moram aqui pela MESMA razão — mais de uma aba
precisou delas, e a segunda cópia é a que esquece um dos tempos:

* `gravar_e_reaplicar()` (01/09/2026) — disco, reaplicar, `launch_env.refresh`;
* `com_a_carona()` (06/09/2026) — o atalho de inicialização que a Steam comeu,
  reposto de carona no gesto que ela já dá. Ver o docstring de cada uma.
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

#: A árvore, para achar o `src/`. Este módulo mora em
#: `src/hefesto_dualsense4unix/interface/pacotes/`, logo a raiz está três níveis acima.
RAIZ = pathlib.Path(__file__).resolve().parents[4]


def _com_o_src() -> Any:
    """Põe o `src/` DESTA árvore no caminho, e devolve o `loader`.

    O `sys.path.insert(0, ...)` é a segunda trava do `.envrc-voo`: sem ele, um
    python chamado por hábito importaria o `hefesto_dualsense4unix` da árvore
    DELA — o defeito que o `CLAUDE.md` mede na seção 2, cujo sintoma é a
    AUSÊNCIA de dado e se lê como "a mudança não pegou".
    """
    src = str(RAIZ / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from hefesto_dualsense4unix.profiles import loader

    return loader


def pasta() -> pathlib.Path | None:
    """A pasta de perfis DESTA variante, perguntada a quem é dono dela.

    É FUNÇÃO E NÃO TEM CACHE, e a razão está escrita no `mesa_viva.py` — que
    aprendeu isto antes de mim: a variante mora em `HEFESTO_VARIANTE`, e um
    valor calculado no import congela o ambiente de quem importou primeiro.

    EU REPETI ESSE ERRO NESTE ARQUIVO, em 01/09/2026: a primeira versão tinha um
    `@lru_cache(maxsize=1)` aqui, e `lista()` devolveu **0 perfis** com 33 no
    disco dela — o processo de teste não tinha a variante posta, e o `None` do
    primeiro chamador ficou valendo para sempre. Com `HEFESTO_VARIANTE=dev` a
    pasta é `hefesto-dev-dualsense4unix/profiles`; sem ela, é a do estável.
    """
    try:
        _com_o_src()
        from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

        return profiles_dir()
    except Exception:
        return None


def ativo(nome: str | None) -> dict[str, Any]:
    """O perfil ativo como dicionário cru, ou `{}` quando não há.

    CRU DE PROPÓSITO, e não um `Profile` do pydantic: quem consome é uma função
    de pacote, que devolve JSON para a tela. Validar aqui só serviria para
    LEVANTAR numa aba inteira por causa de um campo novo que o esquema ainda não
    conhece — e a tela ficaria congelada sem dizer por quê.

    O `{}` faz cada valor virar travessão, que é o que a tela sabe mostrar. Essa
    é a diferença entre "não há perfil agora" e "este valor não tem dono": a
    primeira é um estado, a segunda era um erro meu.
    """
    if not nome:
        return {}
    onde = pasta()
    if onde is None:
        return {}
    #: A PASTA TEM UM DONO SÓ, e é a `pasta()` acima. A primeira versão daqui
    #: chamava `loader._profile_path(nome)`, que resolve o caminho INTEIRO —
    #: pasta e nome — e assim `ativo()` e `lista()` podiam apontar para lugares
    #: diferentes. A régua `test_o_perfil_chega_na_tela.py` pegou isso na
    #: primeira execução: `lista()` achava os dois perfis e `ativo()` devolvia
    #: `{}` para os mesmos.
    #:
    #: Do loader vem só o SLUG — a regra de como um nome vira arquivo, que é
    #: dele e não se digita duas vezes.
    alvo = onde / f"{nome}.json"
    if not alvo.exists():
        try:
            _com_o_src()
            from hefesto_dualsense4unix.profiles.slug import slugify

            alvo = onde / f"{slugify(str(nome))}.json"
        except Exception:
            pass
    if not alvo.exists():
        return {}
    try:
        lido: dict[str, Any] = json.loads(alvo.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return lido


def lista() -> list[dict[str, Any]]:
    """Todos os perfis do disco: nome, prioridade e tipo de casamento.

    A aba Perfis pergunta isto ao daemon por `profile.list`; esta função é a
    mesma resposta sem o socket, para quando o daemon está mudo. **Ela não
    substitui o IPC** — o daemon sabe qual está ATIVO, e o disco não.
    """
    onde = pasta()
    if onde is None or not onde.exists():
        return []
    fora = []
    for p in sorted(onde.glob("*.json")):
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        fora.append({
            "nome": j.get("name") or p.stem,
            "prioridade": j.get("priority", 0),
            "casamento": (j.get("match") or {}).get("type", "criteria"),
            "arquivo": p.name,
        })
    return fora


def gravar_e_reaplicar(prof: Any, ctx: Any, p: Any, *, era: str = "") -> None:
    """Grava o perfil em disco e, se ele for o ATIVO, manda o daemon reaplicá-lo.

    OS TRÊS TEMPOS, e a ordem importa: disco, reaplicar, avisar a antecipação de
    lançamento. Gravar sem reaplicar deixa a tela dizendo uma coisa e o aparelho
    fazendo outra até a próxima troca de perfil.

    A COMPARAÇÃO É POR SLUG, não por string: com "Navegação" no disco e
    "Navegacao" no daemon, um `==` cru diria que são perfis diferentes e o
    reaplicar não aconteceria (R-10, `profiles/slug.py:52`). `era` é o nome
    ANTERIOR — num renomear, é ele que tem de casar com o ativo, porque o daemon
    ainda não ouviu falar do nome novo.

    POR QUE ELA MORA AQUI, e não na aba Perfis onde nasceu: a partir de
    01/09/2026 ela tem DOIS chamadores — o `a10_perfis`, que edita o perfil
    inteiro, e o `a06_navegacao`, que devolve os atalhos de botão ao de fábrica.
    Deixá-la lá obrigaria a segunda aba a importar a primeira (um pacote de aba
    dependendo de outro, que é o oposto do território exclusivo) ou a escrever
    uma segunda cópia dos três tempos — e a segunda cópia é a que esquece o
    `launch_env.refresh` no dia em que alguém mexer numa só.

    O CABEÇALHO DESTE MÓDULO DIZIA *"nada aqui escreve"*. Deixou de valer hoje,
    e a linha foi corrigida em vez de contornada: o que continua verdadeiro é
    que **quem lê** não escreve — as funções de leitura acima seguem puras.

    QUEM ESTÁ VALENDO SE PERGUNTA AO DONO — corrigido em 05/09/2026
    ---------------------------------------------------------------
    Até hoje esta função lia ``ctx.state["active_profile"]`` **cru**. O dono da
    pergunta é `app/actions/profiles_actions.perfil_que_esta_valendo:574`, e a
    docstring dele diz por que o campo cru não serve::

        "Sobrevive ao daemon responder ``active_profile: null``, que é o estado
         da máquina dela hoje"

    Com ``null``, ``ativo_agora`` ficava vazio, o ``if`` era falso e o
    ``profile.switch`` **nunca saía**. O `.json` mudava no disco e o controle
    continuava com o perfil anterior — enquanto a MESMA aba realçava a linha do
    perfil, porque o realce (`a10_perfis._valendo:1043`) já usava o dono certo.

    É o sintoma que ela leu como *"não está salvando"*, e a segunda linha desta
    docstring já o anunciava: *"Gravar sem reaplicar deixa a tela dizendo uma
    coisa e o aparelho fazendo outra"*.

    O dono resolve em duas pernas — o daemon primeiro, o disco declarado depois
    (`session.json` + `active_profile.txt`, pelo mesmo caminho que o daemon usa
    no boot). Perguntar a ele é o que faz o realce e o reaplicar responderem
    sobre o MESMO perfil.

    ELA NÃO CHAMA A CARONA, E A RAZÃO É MEDIDA — 06/09/2026, ONDA5-07-02
    -------------------------------------------------------------------
    Parece o lugar óbvio: na janela estável o funil equivalente
    (`app/actions/profile_writer.py`) carrega UMA chamada de carona que cobre
    três botões. Aqui não serve, e o que muda é a FREQUÊNCIA. Medido: esta
    função tem SEIS chamadores em cinco abas (04, 05, 06, 08 e 10), e a
    interface nova é de AÇÃO IMEDIATA — clicar num tom, num degrau de vibração
    ou num atalho de botão já grava. Pendurar a carona aqui seria uma varredura
    do `localconfig.vdf` **por clique**, que é exatamente a opção (b) que o dono
    da carona pesou e recusou (`app/actions/carona_do_wrapper.py`, "O QUE A
    CARONA REPARA"): *"'sempre' faria uma varredura de disco e duas escritas a
    cada clique"*.

    ONDE ELA ENTRA, então: no gesto de PERFIL — «Ativar» (já pega), os três do
    rodapé (`rodape.py`, 06/09) e o funil `a10_perfis._gravar`, que é o único
    chamador cujos OITO gestos são o perfil inteiro (renomear, prioridade,
    ambiente, estilo, jogo, detectar, novo, duplicar) e não um campo. Esse é o
    que falta, com o `voltar-a-de-ontem` ao lado, e é posse da a10 — está
    relatado em `docs/process/agentes/2026-09-06/ONDA5-07-02.md`.
    """
    loader = _com_o_src()
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        perfil_que_esta_valendo,
    )
    from hefesto_dualsense4unix.profiles.slug import mesmo_slug

    loader.save_profile(prof, origem="interface-nova")
    ativo_agora = perfil_que_esta_valendo(getattr(ctx, "state", None)).nome or ""
    if ativo_agora and mesmo_slug(ativo_agora, era or prof.name):
        p.profile_switch(prof.name)
    # A ANTECIPAÇÃO DE LANÇAMENTO relê o que os jogos vão receber. Sem ela, o
    # perfil novo só chega ao jogo no próximo start do daemon.
    p.chamar("launch_env.refresh")


def com_a_carona(frase: str = "") -> str:
    """Repõe o atalho de inicialização que a Steam comeu, e junta a notícia à frase.

    CARONA-DO-WRAPPER-01 (16/08/2026), e **o desenho é dela**: *"nem precisa ter
    um botão na gui, mas ele se auto corrigir ao clicarmos em aplicar ou salvar
    o perfil seja dentro ou fora da guia de perfis."*

    O QUE ELA CURA: a Steam guarda UMA linha de `LaunchOptions` por jogo, e
    qualquer coisa escrita nela substitui a chamada do `hefesto-launch` em
    silêncio. Sem o atalho, o `launch_env` que o daemon materializa nunca é
    lido — o jogo é instruído a ignorar o vpad que nós criamos para ele. Nas
    palavras dela: *"parou de ser reconhecido no jogo, mas o perfil segue ativo
    no controle com tudo funcionando"*.

    POR QUE AQUI, E NÃO NO PACOTE DE UMA ABA — 06/09/2026, ONDA5-07-02
    ------------------------------------------------------------------
    Ela nasceu em `a10_perfis._com_a_carona`, e o «Ativar» daquela aba era o
    ÚNICO gesto da interface nova que a pegava. O rodapé é das DEZ abas e tem
    três gestos que gravam ou aplicam perfil — `aplicar`, `salvar` e
    `importar` —, e nenhum a pegava. Um pacote de aba importando outro é o
    oposto do território exclusivo; uma segunda cópia é a que esquece um dos
    cuidados abaixo. Este módulo já é o compartilhado do assunto: gravar e
    aplicar perfil.

    POR QUE A FUNÇÃO DE MÓDULO E NÃO O `pegar_carona_no_gesto`: aquele é método
    do `CaronaDoWrapperMixin` e despacha uma thread própria para devolver no
    laço do GTK (`despachar` → `GLib.idle_add`). **O gesto já está em thread**
    (`hefesto_vivo._gesto`, `trabalhar()`), que é exatamente onde `passada()`
    declara ter de rodar — *"Só em thread worker: lê disco e o `/proc`"*. Chamar
    `passada()` daqui é o mesmo trabalho sem a segunda troca de thread.

    `ligada()` É O PORTÃO E NÃO UM `if` MEU: ele é o mesmo que a janela estável
    consulta, e é o que desliga a carona na suíte (a `conftest.py` põe
    `HEFESTO_CARONA_WRAPPER=0`). Uma régua desta casa não vai ao `/proc` dela,
    e não reescreve a biblioteca da máquina em que roda.

    NUNCA LEVANTA. Ela é efeito colateral de um gesto que já deu certo: uma
    exceção aqui transformaria uma gravação bem-sucedida em tarja de recusa.

    O SILÊNCIO É O CASO COMUM, DE PROPÓSITO. `frase` vazia de volta quer dizer
    *não diga nada*: sem nada a repor, `ResultadoDaCarona.frase` é vazia
    (`carona_do_wrapper.py:402`) e quem chamou volta a devolver `None` — o "deu
    certo" é a piscada verde de ~1,5 s (decisão dela, `03-Q4`), **sem palavra
    nova na tela**. A carona só fala quando tem notícia.

    OS DOIS REGISTROS DE CHAMADA, e os dois são legítimos:

    * `com_a_carona(frase)` — quem já tem uma frase de desfecho (o «Ativar» da
      aba Perfis) recebe a notícia GRUDADA nela, com o `·` no meio;
    * `com_a_carona()` — quem não tem (os três gestos do rodapé) recebe a
      notícia sozinha, **sem o separador órfão** que um `f"{''} · …"` deixaria.

    O QUE NÃO VEIO JUNTO, e fica escrito para não sumir: a **vigia**. A janela
    estável arma um tique de 45 s (`_carona_armar_vigia`) que repergunta "a
    Steam já fechou?" até o reparo caber, e a memória do episódio
    (`_carona_ja_avisado`), que impede o mesmo aviso a cada gesto. As duas
    dependem do `GLib.timeout_add` da janela e são território do piloto — não
    deste pacote. Enquanto elas não vierem, um reparo adiado é REDITO a cada
    gesto dela; é ruído conhecido, com endereço, e não defeito novo.
    """
    from hefesto_dualsense4unix.app.actions import carona_do_wrapper as carona

    if not carona.ligada():
        return frase
    try:
        resultado = carona.passada(completa=True)
    except Exception:
        # Nem o log: um pacote de aba não tem logger, e o gesto já deu certo.
        return frase
    if not resultado.frase:
        return frase
    return f"{frase} · {resultado.frase}" if frase else resultado.frase
