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

QUEM LÊ NÃO ESCREVE. As funções de leitura são puras; a `gravar_e_reaplicar()`
no fim do arquivo é a ÚNICA que escreve, e ela nasceu em 01/09/2026 porque duas
abas passaram a precisar dos mesmos três tempos — ver o docstring dela.
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
    """
    loader = _com_o_src()
    from hefesto_dualsense4unix.profiles.slug import mesmo_slug

    loader.save_profile(prof, origem="interface-nova")
    ativo_agora = str((getattr(ctx, "state", None) or {}).get("active_profile") or "")
    if ativo_agora and mesmo_slug(ativo_agora, era or prof.name):
        p.profile_switch(prof.name)
    # A ANTECIPAÇÃO DE LANÇAMENTO relê o que os jogos vão receber. Sem ela, o
    # perfil novo só chega ao jogo no próximo start do daemon.
    p.chamar("launch_env.refresh")
