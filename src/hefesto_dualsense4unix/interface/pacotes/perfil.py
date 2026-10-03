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

O ERRO TEVE UMA FORMA SÓ, a que `portao_a_casa_sabe_e_o_produto_nao_faz.py` nomeia —
*a casa sabe e o produto não faz*: **perguntei só ao `state_full` do daemon.** Ele não publica
gatilho nem brilho; concluí "não tem dono" e escrevi o travessão. O dado estava
no disco dela o tempo todo, e a `gui/aba_*.py` que ela usa hoje já o lê.

O QUE O PERFIL É, e a distinção muda o que a tela deve dizer: ele é o que está
**salvo**, não o que está **aplicado**. Para a cor da barra isso importa — o
daemon publica a cor viva, e ela vence. Para o gatilho não existe escolha: o
DualSense **não devolve** o modo em que está (é comando de ida, e o
`docs/data/mapa-controles.csv` diz o mesmo pela outra ponta). Logo o perfil é a
melhor fonte que existe, e mostrar `Rigid` é mais verdadeiro que mostrar `—`.

QUEM LÊ NÃO ESCREVE PERFIL. As funções de leitura não gravam perfil nenhum: a
memória de `arquivo()` e a do último arquivo lido são do processo, e a única
marca no disco é o `.lock` que a varredura do loader deixa ao lado do arquivo
que lê (o `FileLock` não o apaga, e o daemon deixa os mesmos). **Duas** funções
no fim do arquivo escrevem, e as duas moram aqui pela MESMA razão — mais de uma aba
precisou delas, e a segunda cópia é a que esquece um dos tempos:

* `gravar_e_reaplicar()` (01/09/2026) — disco, reaplicar, `launch_env.refresh`;
* `com_a_carona()` (06/09/2026) — o atalho de inicialização que a Steam comeu,
  reposto de carona no gesto que ela já dá. Ver o docstring de cada uma.

E QUEM RESPONDE "QUAL PERFIL ESTÁ VALENDO" É `nome_do_ativo()` (06/09/2026,
PERFIL-MODO-01): ele pergunta ao dono do §P1 em vez de ler
`state["active_profile"]` cru, e `ativo()` cai nele quando o nome não vem. É a
releitura que faltava para o «Ativar» chegar às outras nove abas.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[4]


def _com_o_src() -> Any:
    """Põe o `src/` DESTA árvore no caminho, e devolve o `loader`."""
    src = str(RAIZ / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from hefesto_dualsense4unix.profiles import loader

    return loader


def pasta() -> pathlib.Path | None:
    """A pasta de perfis DESTA variante, perguntada a quem é dono dela."""
    try:
        _com_o_src()
        from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

        return profiles_dir()
    except Exception:
        return None


def nome_do_ativo(state: Any = None) -> str:
    """Qual perfil está valendo AGORA, perguntado ao dono — `""` quando ninguém.

    PERFIL-MODO-01, Passo 2 (06/09/2026). **É a releitura que o «Ativar» não
    tinha**, e ela mora aqui porque o dono do estado é este módulo — a cura na
    aba Perfis seria uma segunda leitura na aba que já sabe, e as outras nove
    continuariam cegas.

    O DONO DA PERGUNTA É `profiles_actions.perfil_que_esta_valendo` (§P1), e
    ele resolve em DUAS pernas: o daemon primeiro, a escolha dela no disco
    depois (`utils.session.a_escolha_dela`, o mesmo dono que o boot pergunta).
    O ``state.get("active_profile")`` CRU só tem a primeira.

    O QUE ISSO CURA, MEDIDO em 06/09/2026 com um perfil no disco e o daemon
    respondendo ``active_profile: null`` — que é o estado da máquina dela
    descrito em `perfil_que_esta_valendo` e reproduzido em régua::

        perfil.ativo("régua")   ->  {'name': 'régua', …}
        perfil.ativo(None)      ->  {}                      <- as outras abas
        perfil_que_esta_valendo ->  PerfilQueVale('régua', fonte='disco')

    Com o daemon calado, gatilho · brilho · atalhos · teto de vibração viravam
    travessão em TODA aba, e o «Ativar» — que grava os dois marcadores em disco
    pelo `profile.switch` — não mudava nada disso: **nenhum tique relia o
    perfil**, porque o nome nunca chegava. É o sintoma que esta casa chama de
    *ausência de dado lida como "não pegou"*.

    NUNCA LEVANTA: quem chama é pintura de tela a duas vezes por segundo, e uma
    exceção aqui derrubaria a aba inteira por causa de um arquivo de sessão. O
    dono já é best-effort; a garantia final é deste `except`.
    """
    do_daemon = ""
    if isinstance(state, dict):
        do_daemon = str(state.get("active_profile") or "")
    if do_daemon:
        return do_daemon
    try:
        _com_o_src()
        from hefesto_dualsense4unix.app.actions.profiles_actions import (
            perfil_que_esta_valendo,
        )

        return str(perfil_que_esta_valendo(state).nome or "")
    except Exception:
        return ""


def ativo(nome: str | None) -> dict[str, Any]:
    """O perfil ativo como dicionário cru, ou `{}` quando não há.

    CRU DE PROPÓSITO, e não um `Profile` do pydantic: quem consome é uma função
    de pacote, que devolve JSON para a tela. Validar aqui só serviria para
    LEVANTAR numa aba inteira por causa de um campo novo que o esquema ainda não
    conhece — e a tela ficaria congelada sem dizer por quê.

    O `{}` faz cada valor virar travessão, que é o que a tela sabe mostrar. Essa
    é a diferença entre "não há perfil agora" e "este valor não tem dono": a
    primeira é um estado, a segunda era um erro meu.

    NOME VAZIO NÃO É "NÃO HÁ" — 06/09/2026, PERFIL-MODO-01 Passo 2. Todo
    chamador desta função passa ``ctx.state.get("active_profile")``, e esse
    campo é ``null`` sempre que o daemon não sabe dizer. Devolver `{}` ali era a
    tela confundindo *"o daemon não respondeu"* com *"não há perfil"* — a mesma
    distinção que `PerfilQueVale.fonte` existe para carregar. Quando o nome não
    vem, **pergunta-se ao dono** (:func:`nome_do_ativo`); quando nem ele sabe, aí
    sim é `{}`.

    A CURA É AQUI E NÃO EM CADA ABA de propósito: são cinco chamadores em cinco
    pacotes (03, 04, 05, 06 e 08), mais a dica do Salvar do rodapé das dez, e
    cobrir um deixaria os outros remedindo o mesmo defeito — a regra que 05/09
    deixou escrita.

    O ARQUIVO É O QUE O DAEMON LÊ — O-PERFIL-ATIVO-ACHA-O-ARQUIVO-COMO-O-DAEMON-01,
    25/09/2026. Quem acha é :func:`arquivo`, que pergunta ao loader. Esta função
    procurava só pelo nome e pelo slug; o perfil achado só pela varredura por
    `name` ou na subpasta dos Estilos de Jogo virava `{}`, e a aba 03 dizia
    «Desligado» com o daemon mandando o Rígido.

    O ARQUIVO QUE SUMIU COM O PERFIL VALENDO devolve o que esta tela leu dele
    por último (:func:`_lembrar`): o controle segue com o que o daemon aplicou
    até outro perfil entrar, e o que ele aplicou é o que estava no arquivo.
    Sem lembrança (a janela abriu depois de o arquivo sumir), é `{}`: a tela
    não inventa um perfil.
    """
    if not nome:
        nome = nome_do_ativo(None)
    if not nome:
        return {}
    onde = pasta()
    if onde is None:
        return {}
    alvo = arquivo(str(nome), onde)
    if alvo is not None:
        try:
            texto = alvo.read_text(encoding="utf-8")
            lido = json.loads(texto)
        except Exception:
            lido = None
        if isinstance(lido, dict):
            _lembrar(onde, str(nome), texto)
            return lido
    return _o_que_a_tela_leu(onde, str(nome))


def ativo_que_vale(nome: str | None) -> dict[str, Any]:
    """O perfil ativo com o padrão do computador por baixo: o que a tela PINTA."""
    cru = ativo(nome)
    if not cru:
        return cru
    try:
        _com_o_src()
        from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc
        from hefesto_dualsense4unix.profiles.schema import Profile

        computador = opc.o_computador()
        if opc.computador_vazio(computador):
            return cru
        chave = (json.dumps(cru, sort_keys=True), opc.selo_da_maquina())
        lembrado = _VISTA_LIDA.get(str(cru.get("name") or ""))
        if lembrado is not None and lembrado[0] == chave:
            return dict(lembrado[1])
        vista = opc.perfil_que_vale(Profile.model_validate(cru), computador).model_dump(
            mode="json", exclude_unset=True)
        _VISTA_LIDA[str(cru.get("name") or "")] = (chave, vista)
        return dict(vista)
    except Exception:
        return cru


_VISTA_LIDA: dict[str, tuple[Any, dict[str, Any]]] = {}


VALIDADE_DO_ARQUIVO_S = 1.0

CUSTO_QUE_SE_GUARDA_S = 0.001

_ONDE_ACHOU: dict[tuple[str, str], tuple[tuple[Any, ...], float, pathlib.Path | None]] = {}

_LIDO: dict[tuple[str, str], str] = {}


def _carimbo(p: pathlib.Path | None) -> tuple[int, int] | None:
    """`(mtime_ns, tamanho)` de um caminho, ou ``None`` quando ele não está lá."""
    if p is None:
        return None
    try:
        st = p.stat()
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


def _assinatura_da_pasta(onde: pathlib.Path) -> tuple[Any, ...]:
    """O carimbo da pasta e o da subpasta dos Estilos: nasce, some, renomeia."""
    _com_o_src()
    from hefesto_dualsense4unix.profiles.loader import ESTILOS_DE_JOGO_DIR_NAME

    return (_carimbo(onde), _carimbo(onde / ESTILOS_DE_JOGO_DIR_NAME))


def _assinatura(onde: pathlib.Path, achado: pathlib.Path | None) -> tuple[Any, ...]:
    """O que muda quando a resposta de :func:`arquivo` pode ter mudado."""
    return (*_assinatura_da_pasta(onde), _carimbo(achado))


def arquivo(nome: str, onde: pathlib.Path | None = None) -> pathlib.Path | None:
    """O arquivo do perfil `nome`, achado como o DAEMON o acha. ``None`` quando não há.

    O-PERFIL-ATIVO-ACHA-O-ARQUIVO-COMO-O-DAEMON-01, 25/09/2026. «Nome vira
    arquivo» tem UM dono, `profiles.loader.arquivo_do_perfil`, que é o mesmo que
    o `load_profile` do daemon pergunta: o nome direto, o slug, a varredura por
    `name` e a subpasta dos Estilos de Jogo, nessa ordem. Aqui não se digita
    perna nenhuma.

    A PASTA É A DE :func:`pasta` — ela continua a dona da pasta desta tela, e é
    o que mantém `ativo()` e `lista()` olhando o mesmo lugar (a régua
    `test_o_perfil_chega_na_tela.py` pegou os dois divergindo em 01/09). Do
    loader vem a regra de como um nome vira arquivo DENTRO dela.

    A RESPOSTA QUE CUSTOU FICA NA MEMÓRIA (:data:`CUSTO_QUE_SE_GUARDA_S`) por
    :data:`VALIDADE_DO_ARQUIVO_S`, e a assinatura da pasta (:func:`_assinatura`)
    a derruba antes disso.

    Quem chama além de `ativo()`: o «Exportar» do rodapé, que copiava o arquivo
    com a mesma cópia das duas pernas e dizia «não achei o arquivo» sobre o
    perfil que o daemon aplicava.

    NUNCA LEVANTA: um nome que o loader recusa (`ValueError`) é ``None``.
    """
    if onde is None:
        onde = pasta()
    if onde is None or not nome:
        return None
    chave = (str(onde), nome)
    guardado = _ONDE_ACHOU.pop(chave, None)
    if guardado is not None:
        assinatura, quando, achado = guardado
        if ((time.monotonic() - quando) < VALIDADE_DO_ARQUIVO_S
                and _assinatura(onde, achado) == assinatura):
            _ONDE_ACHOU[chave] = guardado
            return achado
    da_pasta = _assinatura_da_pasta(onde)
    inicio = time.perf_counter()
    try:
        loader = _com_o_src()
        achado = loader.arquivo_do_perfil(nome, onde)
    except Exception:
        achado = None
    if time.perf_counter() - inicio >= CUSTO_QUE_SE_GUARDA_S:
        _ONDE_ACHOU[chave] = ((*da_pasta, _carimbo(achado)), time.monotonic(), achado)
    return achado


def _chave_da_lembranca(onde: pathlib.Path, nome: str) -> tuple[str, str]:
    """`(pasta, slug)`: «Navegação» e «Navegacao» são o mesmo perfil (R-10)."""
    try:
        _com_o_src()
        from hefesto_dualsense4unix.profiles.slug import slugify

        return (str(onde), slugify(nome))
    except Exception:
        return (str(onde), nome)


def _lembrar(onde: pathlib.Path, nome: str, texto: str) -> None:
    """Guarda o TEXTO do último arquivo lido deste perfil."""
    _LIDO[_chave_da_lembranca(onde, nome)] = texto


def _o_que_a_tela_leu(onde: pathlib.Path, nome: str) -> dict[str, Any]:
    """O último arquivo lido deste perfil, ou `{}` quando esta tela nunca o leu."""
    texto = _LIDO.get(_chave_da_lembranca(onde, nome))
    if texto is None:
        return {}
    try:
        lido = json.loads(texto)
    except Exception:
        return {}
    return lido if isinstance(lido, dict) else {}


def lista() -> list[dict[str, Any]]:
    """Todos os perfis do disco: nome, prioridade e tipo de casamento."""
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

    O REAPLICAR É O `profile.reaplicar` (01/10/2026,
    O-HEFESTO-ABRE-NO-ULTIMO-PERFIL-E-O-FREESTYLE-DIZ-A-VERDADE-01, item 9 da
    cura): era o `profile.switch`, que é a ativação À MÃO — a cada clique que
    grava, o perfil que vale virava a escolha dela, e com um perfil de jogo
    posto pelo autoswitch ela passava a abrir o Hefesto naquele jogo. O
    `profile.reaplicar` roda a mesma cadeia da ativação sem gravar a escolha
    (O-APLICAR-E-A-ATIVACAO-SAO-UMA-SO-01).

    OS TRÊS TEMPOS, e a ordem importa: disco, reaplicar, avisar a antecipação de
    lançamento. Gravar sem reaplicar deixa a tela dizendo uma coisa e o aparelho
    fazendo outra até a próxima troca de perfil.

    A COMPARAÇÃO É POR SLUG, não por string: com "Navegação" no disco e
    "Navegacao" no daemon, um `==` cru diria que são perfis diferentes e o
    reaplicar não aconteceria (R-10, `profiles/slug.py:37`). `era` é o nome
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
    que **quem lê** não escreve perfil — o cabeçalho diz o que as de leitura
    deixam no disco.

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
    relatado em `ONDA5-07-02`.
    """
    loader = _com_o_src()
    loader.save_profile(prof, origem="interface-nova")
    reaplicar(prof.name, ctx, p, era=era)


def reaplicar(nome: str, ctx: Any, p: Any, *, era: str = "") -> None:
    """Manda o daemon reaplicar o perfil ``nome`` se ele for o ATIVO, e avisa o lançamento."""
    _com_o_src()
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        perfil_que_esta_valendo,
    )
    from hefesto_dualsense4unix.profiles.slug import mesmo_slug

    ativo_agora = perfil_que_esta_valendo(getattr(ctx, "state", None)).nome or ""
    if ativo_agora and mesmo_slug(ativo_agora, era or nome):
        p.profile_reaplicar(nome)
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
    (`carona_do_wrapper.py:317`) e quem chamou volta a devolver `None` — o "deu
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
        return frase
    if not resultado.frase:
        return frase
    return f"{frase} · {resultado.frase}" if frase else resultado.frase


def os_jogadores_de_volta(p: Any) -> tuple[Any, Any]:
    """Os passos 1 e 2 do «Reconectar controles»: devolve ``(sync, renumerou)``."""
    sync = p.resultado("coop.sync")
    try:
        renumerou = p.resultado("identity.renumber")
    except Exception:
        renumerou = None
    return sync, renumerou


def o_radio_de_volta(ctx: Any, *, so_o_elo_morto: bool = False) -> tuple[int, int]:
    """O rádio dos DualSense fora da mesa do Hefesto: ``(voltaram, esperam_o_ps)``.

    Para cada DualSense que o BlueZ conhece (a árvore inteira, todos os
    adaptadores) e que NÃO está entre os controles da mesa, o dono do rádio
    (``gesto_de_reconexao.reconectar``) derruba o elo morto e chama de volta.
    Quem decide se o elo está morto é o kernel, lá dentro: com o HID vivo, o
    controle fica (O-RECONECTAR-SO-DERRUBA-O-ELO-MORTO-01).

    QUEM ESTÁ NA MESA NÃO É TOCADO: mexer no rádio de quem o daemon já enxerga
    trocaria um problema que não existe por segundos sem controle.

    ``so_o_elo_morto`` é a volta do rodapé: só o DualSense que o BlueZ diz
    ``Connected`` (o caso de 22/09). O que ele diz fora, ou que não respondeu,
    fica de fora: é o ``Connect`` de até 12 s que não traz quem está desligado.
    O «Reconectar» chama sem ele, e tenta todos.

    NUNCA LEVANTA: o rádio é acréscimo. Sem o BlueZ, ``(0, 0)``.
    """
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
    from hefesto_dualsense4unix.integrations import gesto_de_reconexao as radio

    na_mesa = {
        norm_mac(str(peca.get("uniq") or "")) or ""
        for peca in (getattr(ctx, "mesa", None) or [])
        if isinstance(peca, dict)
    }
    voltaram = esperam = 0
    try:
        conhecidos = radio.dualsenses_do_radio()
    except Exception:
        return (0, 0)
    for mac, conectado in conhecidos:
        if (norm_mac(mac) or "") in na_mesa:
            continue
        if so_o_elo_morto and conectado is not True:
            continue
        try:
            desfecho = radio.reconectar(mac)
        except Exception:
            continue
        if desfecho.estado == radio.ESTADO_VOLTOU:
            voltaram += 1
        elif desfecho.estado == radio.ESTADO_SO_O_PS:
            esperam += 1
    return (voltaram, esperam)


def _relatar_a_volta(passo: str, motivo: object) -> None:
    """A falha de um passo da volta vai ao diário da janela, nunca à tela."""
    print(f"[relato] volta do perfil · {passo}: {motivo}", file=sys.stderr)


def a_volta_do_perfil(ctx: Any, p: Any) -> None:
    """O fim do «Aplicar», do «Salvar Perfil» e do «Importar» do rodapé.

    O-APLICAR-E-O-SALVAR-JA-ATUALIZAM-01: os três botões que gravam ou mandam
    perfil terminam com a parte do «Atualizar» (aba Sistema) e do «Reconectar
    controles» (aba Jogar) que é do perfil. É a «versão leve» que ela escolheu
    em 29/09 (respostas 42, 43 e 44 da sprint):

    1. ``launch_env.refresh``: os arquivos que a Steam lê ao abrir um jogo. Não
       é o ``daemon.reload``, que para e sobe o leitor dos atalhos (um PS + L3
       no meio cairia no vão);
    2. o rádio só do elo morto (:func:`o_radio_de_volta`, ``so_o_elo_morto``);
    3. ``coop.sync`` e ``identity.renumber`` (:func:`os_jogadores_de_volta`):
       a numeração se compacta a cada Salvar, Aplicar e Importar.

    O rádio vem antes dos jogadores pela razão do «Reconectar»: o controle que
    volta agora é um jogador que o ``coop.sync`` ainda alcança nesta volta. Os
    dois botões de origem ficam como estão, para a volta inteira.

    NUNCA LEVANTA: quando ela começa, o disco e o aparelho já receberam o
    perfil. A falha de um passo vai ao diário com o motivo e não impede o
    seguinte; o botão responde pelo ato dele, e nenhuma frase nova vai à tela.
    """
    try:
        if not p.chamar("launch_env.refresh"):
            _relatar_a_volta("launch_env.refresh", "o serviço não respondeu")
    except Exception as erro:
        _relatar_a_volta("launch_env.refresh", erro)
    o_radio_de_volta(ctx, so_o_elo_morto=True)
    try:
        os_jogadores_de_volta(p)
    except Exception as erro:
        _relatar_a_volta("coop.sync", erro)


#: é o daemon, que aplicou (`Daemon.gravar_o_modo_escolhido`), pela regra do
